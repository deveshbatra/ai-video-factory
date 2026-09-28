"""Content-addressed local asset registry with verified lookup."""

import shutil
import sqlite3
from pathlib import Path
from .schemas import Asset
from .storage import hash_file, write_json, child, canonical


class AssetRegistry:
    def __init__(self, root, database):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = str(database)
        with sqlite3.connect(self.database) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS assets(id TEXT,version INTEGER,sha256 TEXT,file_ref TEXT,metadata TEXT,PRIMARY KEY(id,version),UNIQUE(id,sha256))"
            )

    def register(self, asset, source):
        if hash_file(source) != asset.sha256:
            raise ValueError("asset hash mismatch")
        with sqlite3.connect(self.database) as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT metadata FROM assets WHERE id=? AND sha256=?",
                (asset.id, asset.sha256),
            ).fetchone()
            if existing:
                return Asset.model_validate_json(existing[0])
            version = db.execute(
                "SELECT COALESCE(MAX(version),0)+1 FROM assets WHERE id=?", (asset.id,)
            ).fetchone()[0]
            relative = f"{asset.id}/{version}-{asset.sha256}.png"
            destination = child(self.root, relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            record = asset.model_copy(update={"version": version, "file_ref": relative})
            write_json(destination.with_suffix(".json"), record)
            db.execute(
                "INSERT INTO assets VALUES(?,?,?,?,?)",
                (
                    record.id,
                    version,
                    record.sha256,
                    relative,
                    canonical(record).decode(),
                ),
            )
            return record

    def get(self, asset_id, version):
        with sqlite3.connect(self.database) as db:
            row = db.execute(
                "SELECT metadata FROM assets WHERE id=? AND version=?",
                (asset_id, version),
            ).fetchone()
        if not row:
            raise KeyError(asset_id)
        record = Asset.model_validate_json(row[0])
        if hash_file(child(self.root, record.file_ref)) != record.sha256:
            raise ValueError("registered asset changed")
        return record
