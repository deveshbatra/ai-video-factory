"""Local SQLite WAL queue. Fenced leases plus OS GPU lock held by execution process."""

import sqlite3
import time
import uuid
import contextlib
import fcntl
from pathlib import Path


class Queue:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        with self.db() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in [0, 1]:
                raise ValueError(
                    "unsupported database schema version; migration required"
                )
            db.executescript("""PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,episode TEXT,stage TEXT,ordinal INTEGER,state TEXT DEFAULT 'queued',owner TEXT, fence INTEGER DEFAULT 0,expires REAL DEFAULT 0,attempts INTEGER DEFAULT 0,error TEXT,artifact TEXT,hash TEXT);
            CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY,job TEXT,fence INTEGER,started REAL,finished REAL,result TEXT,seconds REAL,error TEXT);
            CREATE TABLE IF NOT EXISTS resources(name TEXT PRIMARY KEY,owner TEXT,fence INTEGER DEFAULT 0,expires REAL DEFAULT 0);
            INSERT OR IGNORE INTO resources(name) VALUES ('gpu');
            CREATE TABLE IF NOT EXISTS decisions(id TEXT PRIMARY KEY,episode TEXT,stage TEXT,payload TEXT);
            PRAGMA user_version=1;""")

    @contextlib.contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def enqueue(self, episode, stages):
        with self.db() as db:
            for i, s in enumerate(stages):
                db.execute(
                    "INSERT OR IGNORE INTO jobs(id,episode,stage,ordinal) VALUES(?,?,?,?)",
                    (episode + ":" + s, episode, s, i),
                )

    def claim(self, owner, lease, cap, episode=None):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE attempts SET finished=?,result='interrupted',seconds=?-started,error='lease expired' WHERE result='running' AND job IN (SELECT id FROM jobs WHERE state='running' AND expires<?)",
                (time.time(), time.time(), time.time()),
            )
            db.execute(
                "UPDATE jobs SET state=CASE WHEN attempts>=? THEN 'failed' ELSE 'queued' END,error='lease expired' WHERE state='running' AND expires<?",
                (cap, time.time()),
            )
            db.execute(
                "UPDATE jobs SET state='blocked',error='ATTEMPT_LIMIT_EXHAUSTED: create a new episode version' WHERE state='queued' AND attempts>=?",
                (cap,),
            )
            row = db.execute(
                "SELECT * FROM jobs j WHERE state='queued' AND attempts<? AND (? IS NULL OR episode=?) AND NOT EXISTS(SELECT 1 FROM jobs d WHERE d.episode=j.episode AND d.ordinal<j.ordinal AND d.state!='succeeded') ORDER BY rowid LIMIT 1",
                (cap, episode, episode),
            ).fetchone()
            if not row:
                return None
            db.execute(
                "UPDATE jobs SET state='running',owner=?,fence=fence+1,expires=?,attempts=attempts+1 WHERE id=?",
                (owner, time.time() + lease, row["id"]),
            )
            row = dict(
                db.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()
            )
            row["attempt_id"] = str(uuid.uuid4())
            db.execute(
                "INSERT INTO attempts(id,job,fence,started,result) VALUES(?,?,?,?,?)",
                (row["attempt_id"], row["id"], row["fence"], time.time(), "running"),
            )
            return row

    def heartbeat(self, job, lease):
        with self.db() as db:
            n = db.execute(
                "UPDATE jobs SET expires=? WHERE id=? AND owner=? AND fence=? AND state='running' AND expires>?",
                (
                    time.time() + lease,
                    job["id"],
                    job["owner"],
                    job["fence"],
                    time.time(),
                ),
            ).rowcount
            if not n:
                raise RuntimeError("lost lease or cancelled")
            db.execute(
                "UPDATE resources SET expires=? WHERE owner=?",
                (time.time() + lease, job["owner"]),
            )

    def finish(self, job, state, artifact=None, sha=None, error=None):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            n = db.execute(
                "UPDATE jobs SET state=?,artifact=?,hash=?,error=? WHERE id=? AND owner=? AND fence=? AND state='running' AND expires>?",
                (
                    state,
                    artifact,
                    sha,
                    error,
                    job["id"],
                    job["owner"],
                    job["fence"],
                    time.time(),
                ),
            ).rowcount
            if not n:
                raise RuntimeError("stale completion rejected")
            db.execute(
                "UPDATE attempts SET finished=?,seconds=?-started,result=?,error=? WHERE id=?",
                (time.time(), time.time(), state, error, job["attempt_id"]),
            )

    def status(self, episode=None):
        with self.db() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM jobs WHERE (? IS NULL OR episode=?) ORDER BY episode,ordinal",
                    (episode, episode),
                )
            ]

    def cancel(self, episode):
        with self.db() as db:
            db.execute(
                "UPDATE attempts SET result='cancelled',finished=?,seconds=?-started,error='cancellation requested' WHERE result='running' AND job IN (SELECT id FROM jobs WHERE episode=?)",
                (time.time(), time.time(), episode),
            )
            db.execute(
                "UPDATE jobs SET state='cancelled',fence=fence+1 WHERE episode=? AND state IN ('running','queued','blocked')",
                (episode,),
            )

    @contextlib.contextmanager
    def gpu(self, job, lease, wait=False):
        # Kernel lock never expires while its process (or inherited child) lives.
        with open(self.path + ".gpu.lock", "a") as f:
            while True:
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if not wait:
                        raise RuntimeError("GPU_BUSY")
                    self.heartbeat(job, lease)
                    time.sleep(0.5)
            with self.db() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "UPDATE resources SET owner=?,fence=fence+1,expires=? WHERE name='gpu'",
                    (job["owner"], time.time() + lease),
                )
            try:
                yield f.fileno()
            finally:
                with self.db() as db:
                    db.execute(
                        "UPDATE resources SET owner=NULL,expires=0 WHERE name='gpu' AND owner=?",
                        (job["owner"],),
                    )
                fcntl.flock(f, fcntl.LOCK_UN)
