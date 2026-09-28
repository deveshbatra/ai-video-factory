"""Conservative global GPU authorisation ledger, shared across episode databases."""

import sqlite3
import time
import uuid
from pathlib import Path


class Budget:
    def __init__(self, path, limit_seconds=10800):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.limit = limit_seconds
        with sqlite3.connect(self.path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS reservations(id TEXT PRIMARY KEY,started REAL,reserved REAL,actual REAL,reason TEXT)"
            )

    def reserve(self, seconds, reason):
        with sqlite3.connect(self.path, timeout=30) as db:
            db.execute("BEGIN IMMEDIATE")
            spent = db.execute(
                "SELECT COALESCE(SUM(COALESCE(actual,reserved)),0) FROM reservations"
            ).fetchone()[0]
            allowed = min(seconds, self.limit - spent)
            if allowed <= 0:
                raise RuntimeError("GPU_BUDGET_EXHAUSTED")
            key = str(uuid.uuid4())
            db.execute(
                "INSERT INTO reservations VALUES(?,?,?,?,?)",
                (key, time.time(), allowed, None, reason),
            )
            return key, allowed

    def finish(self, key, actual):
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE reservations SET actual=? WHERE id=?", (actual, key))
