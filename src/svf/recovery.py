"""Recover a completed atomic manifest only when its expired lease and fence match."""

import time
from .storage import read_json, hash_file, child


def reconcile(queue, output_root):
    recovered = []
    for row in queue.status():
        if row["state"] != "running" or row["expires"] >= time.time():
            continue
        with queue.db() as db:
            attempt = db.execute(
                "SELECT * FROM attempts WHERE job=? AND fence=? AND result='running'",
                (row["id"], row["fence"]),
            ).fetchone()
        if not attempt:
            continue
        directory = (
            child(output_root, row["episode"])
            / "attempts"
            / row["stage"]
            / attempt["id"]
        )
        manifest = directory / "manifest.json"
        try:
            record = read_json(manifest)
            if record["attempt_id"] != attempt["id"]:
                continue
            if any(
                hash_file(child(directory, name)) != sha
                for name, sha in record["outputs"].items()
            ):
                continue
            metadata = read_json(directory / "attempt.json")
            if metadata["result"] != "succeeded" or metadata["job_id"] != row["id"]:
                continue
        except (OSError, ValueError, KeyError):
            continue
        with queue.db() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                "UPDATE jobs SET state='succeeded',artifact=?,hash=?,error=NULL WHERE id=? AND fence=? AND state='running' AND expires<?",
                (
                    str(manifest),
                    hash_file(manifest),
                    row["id"],
                    row["fence"],
                    time.time(),
                ),
            ).rowcount
            if changed:
                db.execute(
                    "UPDATE attempts SET result='succeeded',finished=?,seconds=?,error='reconciled after atomic manifest commit' WHERE id=?",
                    (time.time(), metadata["timings"]["wall_seconds"], attempt["id"]),
                )
                recovered.append(row["id"])
    return recovered
