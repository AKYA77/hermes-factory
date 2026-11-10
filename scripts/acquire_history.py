"""Bounded concurrent historical acquisition supervisor.

Drives the existing ``factory.operations.import_history`` CLI. This is a
deterministic download/import driver, never a second importer, parser, matching
engine or scoring convention.

Design constraints (see docs/runbooks/historical-backfill.md):
  * free provider source only; no paid route, no provider bypass;
  * bounded concurrency appropriate to the measured host;
  * checkpointed, resumable, paced, with explicit retry cooldowns;
  * every partition is structurally verified from retained bytes before it is
    counted; a zero exit code alone is never treated as completeness;
  * the supervisor stops on completion, on repeated no-progress, or on a
    resource budget rather than spinning forever.

Structural import is not calendar/source acceptance, historical strategy
validation or DATA_READY.
"""

import argparse
import concurrent.futures as futures
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from factory.contracts import SYMBOLS
from factory.data import Catalog, atomic_bytes
from factory.operations.backfill_history import plan, verify_partition

SCHEMA = "history-backfill/v1"
RETRY_COOLDOWN_SECONDS = 3600
DISK_RESERVE_BYTES = 2 * 1024**3


def load_state(path):
    if path.exists():
        state = json.loads(path.read_text())
        if state.get("schema") != SCHEMA:
            raise ValueError("unsupported backfill checkpoint")
        state.setdefault("partitions", {})
        return state
    return {"schema": SCHEMA, "partitions": {}}


def save_state(path, state):
    atomic_bytes(path, json.dumps(state, indent=2, sort_keys=True).encode())


def receipt_path(catalog, item):
    return (
        catalog
        / f"{item['instrument']}-{item['year']}{item['month']:02}-import-report.json"
    )


def classify(item, catalog, state):
    """Return (status, detail) for one planned partition."""
    known = state["partitions"].get(item["key"])
    if known and known.get("state") == "STRUCTURAL_IMPORT_PASS":
        return "PASS", known
    if known and known.get("state") == "BLOCKED":
        if float(known.get("retry_after_utc", 0)) > time.time():
            return "COOLDOWN", known
        return "RETRY", known
    receipt = receipt_path(catalog, item)
    if receipt.exists():
        try:
            report = json.loads(receipt.read_text())
        except (OSError, ValueError):
            return "RETRY", known
        if report.get("status") != "STRUCTURAL_IMPORT_PASS":
            return "RETRY", known
        return "RECEIPT", report
    return "NEW", None


def import_one(item, archives, catalog, log_dir, timeout, staging_budget_bytes=None):
    log = log_dir / f"{item['instrument']}-{item['year']}{item['month']:02}-{time.time_ns()}.log"
    command = [
        sys.executable,
        "-m",
        "factory.operations.import_history",
        "--instrument",
        item["instrument"],
        "--year",
        str(item["year"]),
        "--month",
        str(item["month"]),
        "--archives",
        str(archives),
        "--catalog",
        str(catalog),
    ]
    if staging_budget_bytes:
        command += ["--staging-budget-bytes", str(staging_budget_bytes)]
    env = os.environ.copy()
    started = time.time()
    try:
        with log.open("w") as output:
            proc = subprocess.run(
                command, stdout=output, stderr=output, timeout=timeout, env=env, check=False
            )
        return item, proc.returncode, log, time.time() - started
    except subprocess.TimeoutExpired:
        return item, None, log, time.time() - started


def run(args):
    through = args.through
    archives = Path(args.archives)
    catalog = Path(args.catalog)
    checkpoint = Path(args.checkpoint)
    log_dir = checkpoint.parent / "logs"
    archives.mkdir(parents=True, exist_ok=True)
    catalog.mkdir(parents=True, exist_ok=True)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    requested = list(plan(through, tuple(args.instruments)))
    requested_keys = {item["key"] for item in requested}
    cat = Catalog(catalog)
    deadline = time.time() + args.max_wall_seconds if args.max_wall_seconds else None

    with checkpoint.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = load_state(checkpoint)
        state["partitions"] = {
            k: v for k, v in state["partitions"].items() if k in requested_keys
        }
        started = time.time()
        rounds = 0
        no_progress = 0
        total_attempts = 0
        while rounds < args.max_rounds:
            rounds += 1
            if deadline and time.time() > deadline:
                print(json.dumps({"status": "PAUSED_WALL_BUDGET", "rounds": rounds}))
                break
            todo = []
            for item in requested:
                status, detail = classify(item, catalog, state)
                if status == "PASS":
                    continue
                if status == "COOLDOWN":
                    continue
                if status == "RECEIPT":
                    try:
                        report = detail
                        m = verify_partition(
                            cat, report["dataset"]["dataset_hash"], item
                        )
                        state["partitions"][item["key"]] = {
                            "state": "STRUCTURAL_IMPORT_PASS",
                            "dataset_hash": m["dataset_hash"],
                            "rows": m["rows"],
                            "source_sha256": m["source_sha256"],
                            "reused_existing_receipt": True,
                            "verified_at_utc": time.strftime(
                                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                            ),
                        }
                        save_state(checkpoint, state)
                        continue
                    except (OSError, ValueError) as exc:
                        state["partitions"].pop(item["key"], None)
                todo.append(item)
            if not todo:
                print(json.dumps({"status": "ALL_STRUCTURALLY_IMPORTED", "rounds": rounds}))
                break
            if shutil.disk_usage(catalog).free < DISK_RESERVE_BYTES:
                print(json.dumps({"status": "PAUSED_DISK_RESERVE", "rounds": rounds}))
                break
            # Prefer partitions that have never been attempted. A run of blocked
            # partitions at the head of the queue must not consume the whole
            # no-progress budget and stall the remaining work.
            untried = [i for i in todo if i["key"] not in state["partitions"]]
            retryable = [i for i in todo if i["key"] in state["partitions"]]
            wave = (untried or retryable)[: args.workers]
            before = sum(
                1
                for item in requested
                if state["partitions"].get(item["key"], {}).get("state")
                == "STRUCTURAL_IMPORT_PASS"
            )
            attempts = []
            if args.dry_run:
                print(
                    json.dumps(
                        {
                            "status": "DRY_RUN_WAVE",
                            "would_attempt": [i["key"] for i in wave],
                            "remaining": len(todo),
                        }
                    )
                )
                break
            with futures.ThreadPoolExecutor(max_workers=len(wave)) as pool:
                results = list(
                    pool.map(
                        lambda i: import_one(
                            i, archives, catalog, log_dir, args.partition_timeout,
                            args.staging_budget_bytes,
                        ),
                        wave,
                    )
                )
            for item, code, log, elapsed in results:
                total_attempts += 1
                if code == 0:
                    try:
                        report = json.loads(receipt_path(catalog, item).read_text())
                        m = verify_partition(cat, report["dataset"]["dataset_hash"], item)
                        state["partitions"][item["key"]] = {
                            "state": "STRUCTURAL_IMPORT_PASS",
                            "dataset_hash": m["dataset_hash"],
                            "rows": m["rows"],
                            "source_sha256": m["source_sha256"],
                            "wall_seconds": round(elapsed, 3),
                            "verified_at_utc": time.strftime(
                                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                            ),
                        }
                        attempts.append({"key": item["key"], "state": "PASS"})
                    except (OSError, ValueError, KeyError) as exc:
                        state["partitions"][item["key"]] = {
                            "state": "BLOCKED",
                            "error": f"verify failed: {exc}"[:1000],
                            "log": str(log),
                            "retry_after_utc": time.time() + RETRY_COOLDOWN_SECONDS,
                        }
                        attempts.append({"key": item["key"], "state": "VERIFY_BLOCKED"})
                else:
                    state["partitions"][item["key"]] = {
                        "state": "BLOCKED",
                        "error": f"import exit {code}",
                        "log": str(log),
                        "retry_after_utc": time.time() + RETRY_COOLDOWN_SECONDS,
                    }
                    attempts.append({"key": item["key"], "state": f"BLOCKED_{code}"})
            # Staging is cumulative: without reclamation the payload budget is
            # eventually exhausted and further imports block even though their
            # canonical data is already published. Reclaim only published
            # checkpoints, and only when staging is actually pressing on the
            # budget -- reclaim_all re-verifies every retained chunk, so
            # calling it unconditionally after each wave stalls the supervisor.
            try:
                from factory.data.resume import _payload_bytes, reclaim_all

                staging_root = Path(catalog) / ".imports"
                pressure = _payload_bytes(staging_root) / max(
                    args.staging_budget_bytes or 2**31, 1
                )
                if pressure >= 0.5:
                    reclaimed = reclaim_all(catalog)
            except Exception:
                reclaimed = []
            save_state(checkpoint, state)
            after = sum(
                1
                for item in requested
                if state["partitions"].get(item["key"], {}).get("state")
                == "STRUCTURAL_IMPORT_PASS"
            )
            progress = after - before
            no_progress = 0 if progress else no_progress + 1
            print(
                json.dumps(
                    {
                        "round": rounds,
                        "attempted": [a["key"] for a in attempts],
                        "results": attempts,
                        "completed": after,
                        "remaining": len(requested) - after,
                        "no_progress_rounds": no_progress,
                        "elapsed_seconds": round(time.time() - started, 1),
                    }
                ),
                flush=True,
            )
            if no_progress >= args.stop_on_no_progress:
                print(
                    json.dumps(
                        {
                            "status": "STOPPED_NO_PROGRESS",
                            "rounds": rounds,
                            "remaining": len(requested) - after,
                        }
                    )
                )
                break
            time.sleep(args.pace_seconds)
        completed = sum(
            1
            for item in requested
            if state["partitions"].get(item["key"], {}).get("state")
            == "STRUCTURAL_IMPORT_PASS"
        )
        report = {
            "status": "STRUCTURAL_BACKFILL_PROGRESS",
            "historical_validation": False,
            "free_sources_only": True,
            "through_provider_month": through,
            "requested_partitions": len(requested),
            "structurally_imported_partitions": completed,
            "remaining_partitions": len(requested) - completed,
            "rounds": rounds,
            "total_attempts": total_attempts,
            "wall_seconds": round(time.time() - started, 1),
            "dry_run": args.dry_run,
            "limitations": [
                "not calendar/source completeness approval",
                "current month and provider outages may be incomplete",
                "source corrections/periodic recaptures and independent-source reconciliation unfinished",
                "failed download bytes remain preserved; manual recovery may be required before retry",
            ],
        }
        save_state(checkpoint, state)
        atomic_bytes(
            checkpoint.with_suffix(".report.json"),
            (json.dumps(report, indent=2, sort_keys=True) + "\n").encode(),
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--through", default="2026-10")
    p.add_argument("--instruments", nargs="+", default=list(SYMBOLS))
    p.add_argument("--archives", type=Path, default=Path("/var/lib/hermes-factory/archives"))
    p.add_argument("--catalog", type=Path, default=Path("/var/lib/hermes-factory/catalog"))
    p.add_argument(
        "--checkpoint",
        type=Path,
        default=Path("/var/lib/hermes-factory/backfill/checkpoint.json"),
    )
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--pace-seconds", type=float, default=2.0)
    p.add_argument("--partition-timeout", type=int, default=3600)
    p.add_argument(
        "--staging-budget-bytes",
        type=int,
        default=None,
        help=(
            "Per-import staging payload budget. Defaults to the import's own "
            "2 GiB guard. Raise it on a host with ample free disk when retained "
            "prefixes for quarantined partitions legitimately accumulate."
        ),
    )
    p.add_argument("--max-rounds", type=int, default=400)
    p.add_argument("--max-wall-seconds", type=int, default=0)
    p.add_argument("--stop-on-no-progress", type=int, default=3)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if not 1 <= args.workers <= 6:
        raise SystemExit("workers must be 1..6 for this host")
    run(args)


if __name__ == "__main__":
    main()
