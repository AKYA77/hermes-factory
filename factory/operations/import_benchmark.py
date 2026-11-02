"""Measure one real source structural import in a fresh process on Linux."""

import argparse
import json
from pathlib import Path
import resource
import subprocess
import sys
import time
from factory.provenance import source_identity


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--instrument", required=True)
    p.add_argument("--year", required=True, type=int)
    p.add_argument("--month", required=True, type=int)
    args = p.parse_args()
    prefix = Path("reports/runtime") / f"{args.instrument}-{args.year}{args.month:02}"
    prefix.parent.mkdir(parents=True, exist_ok=True)
    context = source_identity()
    started = time.perf_counter()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    with prefix.with_suffix(".log").open("w") as log:
        child = subprocess.run(
            [
                sys.executable,
                "-m",
                "factory.operations.import_history",
                "--instrument",
                args.instrument,
                "--year",
                str(args.year),
                "--month",
                str(args.month),
            ],
            stdout=log,
            stderr=log,
        )
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    report = {
        "scope": "real HistData source structural import; not historical strategy validation or VPS throughput",
        "source_context": context,
        "source_context_unchanged": source_identity() == context,
        "exit_code": child.returncode,
        "wall_seconds": time.perf_counter() - started,
        "cpu_seconds": after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
        "peak_rss_bytes": after.ru_maxrss * 1024,
        "memory_method": "Linux getrusage fresh child maxrss",
        "source_report": f".local/historical-catalog/{args.instrument}-{args.year}{args.month:02}-import-report.json",
    }
    prefix.with_suffix(".resources.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    raise SystemExit(child.returncode)


if __name__ == "__main__":
    main()
