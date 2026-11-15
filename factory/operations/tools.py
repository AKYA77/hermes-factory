"""Inspect-only backup restore rehearsal and labeled development fixture setup."""

import argparse
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from factory.contracts import ExperimentContract
from factory.experiments import Store
from factory.operations import backup, restore, rollback_plan, verify_backup
from factory.operations.fixtures import seed


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "action",
        choices=[
            "seed",
            "backup",
            "restore-test",
            "restore",
            "restore-rehearsal",
            "rollback-plan",
            "reclaim-staging",
        ],
    )
    p.add_argument("path")
    p.add_argument("destination", nargs="?")
    p.add_argument("--services-stopped", action="store_true")
    p.add_argument("--previous-release-verified", action="store_true")
    args = p.parse_args()
    if args.action == "seed":
        root = Path(args.path)
        store = Store(root / "factory.sqlite")
        payload = seed(root)
        job = store.enqueue(
            "research",
            payload,
            ExperimentContract.model_validate(payload["contract"]).experiment_hash,
            actor="fixture-seeder",
        )
        print(json.dumps({"synthetic": True, "job_id": job, "paused": store.paused()}))
    elif args.action == "backup":
        if not args.destination:
            p.error("destination required")
        files = backup(args.path, args.destination)
        print(json.dumps({"verified_files": len(files), "backup": args.destination}))
    elif args.action == "reclaim-staging":
        from factory.data.resume import reclaim_all

        receipts = reclaim_all(args.path)
        print(
            json.dumps(
                {
                    "reclaimed_checkpoints": len(receipts),
                    "reclaimed_payload_bytes": sum(r["reclaimed_payload_bytes"] for r in receipts),
                    "removed_chunks": sum(r["removed_chunks"] for r in receipts),
                },
                indent=2,
            )
        )
    elif args.action == "restore":
        if not args.destination:
            p.error("destination required")
        receipt = restore(args.path, args.destination)
        print(json.dumps(receipt))
    elif args.action == "restore-rehearsal":
        if not args.destination:
            p.error("destination required")
        from factory.operations import rehearse_restore

        print(json.dumps(rehearse_restore(args.path, args.destination), indent=2))
    elif args.action == "rollback-plan":
        if not args.destination:
            p.error("destination required")
        print(
            json.dumps(
                rollback_plan(
                    args.path,
                    args.destination,
                    args.services_stopped,
                    args.previous_release_verified,
                )
            )
        )
    else:
        verify_backup(args.path)
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "restored"
            shutil.copytree(args.path, dest)
            manifest = verify_backup(dest)
            with closing(
                sqlite3.connect(
                    (dest / "factory.sqlite").as_uri() + "?mode=ro&immutable=1", uri=True
                )
            ) as db:
                jobs = db.execute("SELECT count(*) FROM jobs").fetchone()[0]
                experiments = db.execute("SELECT count(*) FROM experiments").fetchone()[0]
            print(
                json.dumps(
                    {
                        "restore_verified": True,
                        "files": len(manifest["files"]),
                        "jobs": jobs,
                        "experiments": experiments,
                        "scope": "isolated copy; active state unchanged",
                    }
                )
            )


if __name__ == "__main__":
    main()
