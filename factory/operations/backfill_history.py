"""Checkpointed free-only monthly structural imports. Never strategy validation.

Plan first; --execute explicitly runs a bounded number of missing partitions.
No provider bypass, paid source, interpolation or overwrite of canonical history.
"""

import argparse
from datetime import date, datetime, timezone
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
from factory.provenance import source_identity


def plan(through, instruments=SYMBOLS):
    last = date.fromisoformat(through + "-01")
    if last.year not in (2025, 2026) or last > date.today().replace(day=1):
        raise ValueError("unsupported/future provider period")
    if (
        not instruments
        or len(set(instruments)) != len(instruments)
        or any(s not in SYMBOLS for s in instruments)
    ):
        raise ValueError("invalid source instruments")
    for year in (2025, 2026):
        for month in range(1, 13):
            if date(year, month, 1) > last:
                return
            for symbol in instruments:
                yield {
                    "instrument": symbol,
                    "year": year,
                    "month": month,
                    "key": f"{symbol}:{year}-{month:02}",
                }


def verify_partition(cat, identity, item):
    m = cat.verify(identity)
    expected = f"https://www.histdata.com/download-free-forex-historical-data/?/ascii/tick-data-quotes/{item['instrument'].lower()}/{item['year']}/{item['month']}"
    if m["instrument"] != item["instrument"] or m["provenance"]["source"] != expected:
        raise ValueError("backfill partition/source identity mismatch")
    return m


def import_partition(partition, archives, catalog, log):
    command = [
        sys.executable,
        "-m",
        "factory.operations.import_history",
        "--instrument",
        partition["instrument"],
        "--year",
        str(partition["year"]),
        "--month",
        str(partition["month"]),
        "--archives",
        str(archives),
        "--catalog",
        str(catalog),
    ]
    with Path(log).open("w") as output:
        env = os.environ.copy()
        env["FACTORY_SUPERVISED_PARENT_PID"] = str(os.getpid())
        child = subprocess.run(command, stdout=output, stderr=output, timeout=1800, env=env)
    if child.returncode:
        raise ValueError("IMPORT_FAILED: see retained log " + str(log))
    receipt = (
        Path(catalog)
        / f"{partition['instrument']}-{partition['year']}{partition['month']:02}-import-report.json"
    )
    report = json.loads(receipt.read_text())
    if report["status"] != "STRUCTURAL_IMPORT_PASS" or not report.get("source_context_unchanged"):
        raise ValueError("import/source context not verified")
    return report


def run(
    through, archives, catalog, checkpoint, max_partitions=4, execute=False, instruments=SYMBOLS
):
    requested = list(plan(through, instruments))
    if not 1 <= max_partitions <= 8:
        raise ValueError("bounded imports per invocation are 1..8")
    checkpoint = Path(checkpoint)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    catalog = Path(catalog)
    archives = Path(archives)
    cat = Catalog(catalog)
    with checkpoint.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = (
            json.loads(checkpoint.read_text())
            if checkpoint.exists()
            else {"schema": "history-backfill/v1", "partitions": {}}
        )
        if state.get("schema") != "history-backfill/v1":
            raise ValueError("unsupported backfill checkpoint")
        attempted = 0
        results = []
        context = source_identity()
        for item in requested:
            known = state["partitions"].get(item["key"])
            if known and known["state"] == "STRUCTURAL_IMPORT_PASS":
                verify_partition(cat, known["dataset_hash"], item)
                continue
            receipt = (
                catalog
                / f"{item['instrument']}-{item['year']}{item['month']:02}-import-report.json"
            )
            if receipt.exists():
                imported = json.loads(receipt.read_text())
                m = verify_partition(cat, imported["dataset"]["dataset_hash"], item)
                source = imported["source"]
                if (
                    source["instrument"] != item["instrument"]
                    or source["year"] != item["year"]
                    or source["month"] != item["month"]
                ):
                    raise ValueError("source receipt identity mismatch")
                state["partitions"][item["key"]] = {
                    "state": "STRUCTURAL_IMPORT_PASS",
                    "dataset_hash": m["dataset_hash"],
                    "rows": m["rows"],
                    "reused_existing_receipt": True,
                }
                continue
            if not execute:
                continue
            if known and known.get("retry_after_utc", 0) > time.time():
                continue
            if attempted >= max_partitions:
                break
            # Reserve for bounded ZIP, retained raw copy, Parquet and failure logs.
            if shutil.disk_usage(catalog).free < 2 * 1024**3:
                results.append({"key": item["key"], "state": "PAUSED_DISK_RESERVE"})
                break
            attempted += 1
            log = (
                checkpoint.parent
                / f"{item['instrument']}-{item['year']}{item['month']:02}-{time.time_ns()}.log"
            )
            state["partitions"][item["key"]] = {
                "state": "IMPORTING",
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "log": str(log),
            }
            atomic_bytes(checkpoint, json.dumps(state, indent=2, sort_keys=True).encode())
            try:
                imported = import_partition(item, archives, catalog, log)
                m = verify_partition(cat, imported["dataset"]["dataset_hash"], item)
                current = {
                    "state": "STRUCTURAL_IMPORT_PASS",
                    "dataset_hash": m["dataset_hash"],
                    "rows": m["rows"],
                    "wall_seconds": imported["wall_seconds"],
                    "cpu_seconds": imported["cpu_seconds"],
                    "peak_rss_bytes": imported["peak_rss_bytes"],
                    "source_sha256": m["source_sha256"],
                    "source_context": imported["source_context"],
                    "log": str(log),
                }
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                # No endless hammering, paid fallback or fake successful partition.
                current = {
                    "state": "BLOCKED",
                    "error": str(exc)[:1000],
                    "log": str(log),
                    "retry_after_utc": time.time() + 3600,
                }
            state["partitions"][item["key"]] = current
            atomic_bytes(checkpoint, json.dumps(state, indent=2, sort_keys=True).encode())
            results.append({"key": item["key"], **current})
            time.sleep(1)  # pacing between provider partitions, not a throughput claim
        unchanged = source_identity() == context
        completed = sum(
            v["state"] == "STRUCTURAL_IMPORT_PASS"
            for k, v in state["partitions"].items()
            if k in {p["key"] for p in requested}
        )
        report = {
            "status": "STRUCTURAL_BACKFILL_PROGRESS",
            "historical_validation": False,
            "free_sources_only": True,
            "through_provider_month": through,
            "requested_partitions": len(requested),
            "structurally_imported_partitions": completed,
            "remaining_partitions": len(requested) - completed,
            "new_partition_attempts": attempted,
            "results": results,
            "dry_run": not execute,
            "source_context": context,
            "source_context_unchanged": unchanged,
            "limitations": [
                "not calendar/source completeness approval",
                "current month and provider outages may be incomplete",
                "source corrections/periodic recaptures and independent-source reconciliation unfinished",
                "failed download bytes remain preserved; manual recovery may be required before retry",
            ],
        }
        if execute:
            atomic_bytes(checkpoint, json.dumps(state, indent=2, sort_keys=True).encode())
            atomic_bytes(
                checkpoint.with_suffix(".report.json"),
                json.dumps(report, indent=2, sort_keys=True).encode(),
            )
        return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--through", default=datetime.now(timezone.utc).strftime("%Y-%m"))
    p.add_argument("--instruments", nargs="+", default=list(SYMBOLS))
    p.add_argument("--archives", type=Path, default=Path(".local/histdata-archives"))
    p.add_argument("--catalog", type=Path, default=Path(".local/historical-catalog"))
    p.add_argument(
        "--checkpoint", type=Path, default=Path(".local/historical-backfill/checkpoint.json")
    )
    p.add_argument("--max-partitions", type=int, default=4)
    p.add_argument("--execute", action="store_true")
    args = p.parse_args()
    print(
        json.dumps(
            run(
                args.through,
                args.archives,
                args.catalog,
                args.checkpoint,
                args.max_partitions,
                args.execute,
                tuple(args.instruments),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
