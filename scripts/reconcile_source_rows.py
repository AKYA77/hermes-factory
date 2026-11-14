"""Reconcile every acquired partition's row counts against its source archive.

The invariant is:

    source_rows_read == published_rows + duplicates_dropped + crossed_removed

`source_rows_read` is `rows_decoded + rows_reused`. Reading `rows_decoded` alone
is wrong: a resumable import reuses earlier checkpointed chunks, so a partition
imported over several attempts reports only the rows decoded in its final run.
That makes published rows look larger than the archive count, which reads as
invented data when it is really resumability working.

Run:  env -u PYTHONPATH .venv/bin/python scripts/reconcile_source_rows.py
Exit 0 when every successful import reconciles, 1 otherwise.
"""

import argparse
import collections
import json
from pathlib import Path
import sys

DEFAULT_LOGS = Path("/var/lib/hermes-factory/backfill/logs")


def load(log_dir: Path):
    records = []
    for path in sorted(log_dir.glob("*.log")):
        try:
            report = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if report.get("status") != "STRUCTURAL_IMPORT_PASS":
            continue
        dataset = report.get("dataset") or {}
        resume = report.get("import_resume") or {}
        correction = resume.get("source_order_correction") or {}
        quarantine = resume.get("source_quality_quarantine") or {}
        records.append(
            {
                "instrument": dataset.get("instrument"),
                "log": path.name,
                # Older receipts predate source_rows_read; derive it.
                "read": resume.get(
                    "source_rows_read",
                    (resume.get("rows_decoded") or 0) + (resume.get("rows_reused") or 0),
                ),
                "published": dataset.get("rows") or 0,
                "duplicates": sum(
                    block.get("rows", 0)
                    for block in correction.get("duplicate_blocks_removed", [])
                ),
                "crossed": quarantine.get("crossed_quotes_removed", 0),
            }
        )
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs", type=Path, default=DEFAULT_LOGS)
    args = parser.parse_args()

    records = load(args.logs)
    if not records:
        print("no successful import receipts found", file=sys.stderr)
        return 1

    mismatched = [
        r for r in records if r["read"] != r["published"] + r["duplicates"] + r["crossed"]
    ]

    per_instrument = collections.defaultdict(
        lambda: {"partitions": 0, "read": 0, "published": 0, "duplicates": 0, "crossed": 0}
    )
    for r in records:
        bucket = per_instrument[r["instrument"]]
        bucket["partitions"] += 1
        bucket["read"] += r["read"]
        bucket["published"] += r["published"]
        bucket["duplicates"] += r["duplicates"]
        bucket["crossed"] += r["crossed"]

    print(f"imports reconciled: {len(records)}")
    print(f"mismatches: {len(mismatched)}")
    for r in mismatched:
        print(
            f"  {r['instrument']} read={r['read']:,} published={r['published']:,} "
            f"duplicates={r['duplicates']:,} crossed={r['crossed']:,} ({r['log']})"
        )
    print()
    print("instrument  parts     source_rows_read   published_rows   duplicates  crossed")
    totals = collections.Counter()
    for instrument in sorted(per_instrument):
        b = per_instrument[instrument]
        print(
            f"  {instrument:<8} {b['partitions']:>5} {b['read']:>17,} "
            f"{b['published']:>16,} {b['duplicates']:>11,} {b['crossed']:>7,}"
        )
        for key, value in b.items():
            totals[key] += value
    print(
        f"  {'TOTAL':<8} {totals['partitions']:>5} {totals['read']:>17,} "
        f"{totals['published']:>16,} {totals['duplicates']:>11,} {totals['crossed']:>7,}"
    )
    return 1 if mismatched else 0


if __name__ == "__main__":
    raise SystemExit(main())
