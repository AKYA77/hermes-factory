"""Operational helpers: consistent SQLite backups and checked artifact copies."""

import json
from contextlib import closing
from pathlib import Path
import shutil
import sqlite3

from factory.data import atomic_bytes, sha256


def backup(state_root, destination):
    root = Path(state_root).resolve()
    dest = Path(destination).resolve()
    if dest == root or root in dest.parents:
        raise ValueError("backup must be outside state root")
    dest.mkdir(parents=True, exist_ok=False)
    source = root / "factory.sqlite"
    with (
        closing(sqlite3.connect(source)) as src,
        closing(sqlite3.connect(dest / "factory.sqlite")) as out,
    ):
        src.backup(out)
        out.execute("PRAGMA journal_mode=DELETE")
    for folder in ("catalog", "artifacts"):
        if (root / folder).exists():
            shutil.copytree(root / folder, dest / folder)
    files = {str(p.relative_to(dest)): sha256(p) for p in dest.rglob("*") if p.is_file()}
    atomic_bytes(
        dest / "backup-manifest.json",
        json.dumps({"schema": "backup/v1", "files": files}, sort_keys=True).encode(),
    )
    verify_backup(dest)
    return files


def verify_backup(path):
    path = Path(path)
    manifest = json.loads((path / "backup-manifest.json").read_text())
    if not manifest["files"]:
        raise ValueError("empty backup")
    for name, digest in manifest["files"].items():
        target = (path / name).resolve()
        if path.resolve() not in target.parents or sha256(target) != digest:
            raise ValueError("backup checksum mismatch")
    with closing(
        sqlite3.connect(
            (path / "factory.sqlite").resolve().as_uri() + "?mode=ro&immutable=1", uri=True
        )
    ) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("corrupt backup database")
    return manifest
