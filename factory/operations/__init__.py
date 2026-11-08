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


def restore(backup_path, state_root):
    """Restore a verified backup into a fresh state root.

    The target must not exist and must sit outside the backup, so a restore can
    never overwrite live state or the backup it came from.
    """
    manifest = verify_backup(backup_path)
    source = Path(backup_path).resolve()
    root = Path(state_root).resolve()
    if root.exists():
        raise ValueError("restore target must not exist")
    if root == source or source in root.parents or root in source.parents:
        raise ValueError("restore target must be outside the backup")
    shutil.copytree(source, root)
    verify_backup(root)
    return {
        "schema": "restore/v1",
        "files": len(manifest["files"]),
        "restored_to": str(root),
        "backup": str(source),
    }


def rollback_plan(backup_path, state_root, services_stopped, previous_release_verified):
    """Describe a rollback without performing it.

    A rollback is refused unless the caller affirms that services are stopped and
    the previous release is verified. No production release exists yet, so this
    never switches live state.
    """
    manifest = verify_backup(backup_path)
    if not services_stopped:
        raise ValueError("rollback requires stopped services")
    if not previous_release_verified:
        raise ValueError("rollback requires a verified previous release")
    return {
        "schema": "rollback-plan/v1",
        "backup": str(Path(backup_path).resolve()),
        "target": str(Path(state_root).resolve()),
        "files": len(manifest["files"]),
        "services_stopped": True,
        "previous_release_verified": True,
        "applied": False,
        "limitations": [
            "Plan only; live state is never switched by this call",
            "No production release exists yet",
            "A rehearsal must restore into a fresh root and re-run verification",
        ],
    }


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
