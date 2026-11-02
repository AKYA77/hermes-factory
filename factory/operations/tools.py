"""Inspect-only backup restore rehearsal and labeled development fixture setup."""

import argparse
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from factory.contracts import fingerprint
from factory.experiments import Store
from factory.operations import backup, verify_backup
from factory.operations.fixtures import seed


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["seed", "backup", "restore-test"])
    p.add_argument("path")
    p.add_argument("destination", nargs="?")
    args = p.parse_args()
    if args.action == "seed":
        root = Path(args.path)
        store = Store(root / "factory.sqlite")
        payload = seed(root)
        job = store.enqueue("research", payload, fingerprint(payload), actor="fixture-seeder")
        print(json.dumps({"synthetic": True, "job_id": job, "paused": store.paused()}))
    elif args.action == "backup":
        if not args.destination:
            p.error("destination required")
        files = backup(args.path, args.destination)
        print(json.dumps({"verified_files": len(files), "backup": args.destination}))
    else:
        verify_backup(args.path)
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "restored"
            shutil.copytree(args.path, dest)
            manifest = verify_backup(dest)
            with sqlite3.connect(dest / "factory.sqlite") as db:
                jobs = db.execute("SELECT count(*) FROM jobs").fetchone()[0]
            print(
                json.dumps(
                    {
                        "restore_verified": True,
                        "files": len(manifest["files"]),
                        "jobs": jobs,
                        "scope": "isolated copy; active state unchanged",
                    }
                )
            )


if __name__ == "__main__":
    main()
