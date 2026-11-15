"""Measure generated import/checkpoint work, never historical replay throughput."""

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import resource
import tempfile
import time
import zipfile

from factory.data import sha256
from factory.data.histdata import quotes_from_archive
from factory.data.resume import import_archive
from factory.data.streaming import StreamingCatalog
from factory.provenance import source_identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=50000)
    parser.add_argument("--state", type=Path, default=Path(".local"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.rows <= 1000000:
        parser.error("rows must be 1..1000000")
    args.state.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="import-resume-benchmark-", dir=args.state))
    path = root / "generated.zip"
    start = datetime(2025, 1, 2)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        with z.open("DAT_ASCII_EURUSD_T_202501.csv", "w") as stream:
            for i in range(args.rows):
                stamp = (start + timedelta(milliseconds=i)).strftime("%Y%m%d %H%M%S")
                stream.write((stamp + f"{i % 1000:03},1.123450,1.123460,0\n").encode())
    source = {
        "archive": str(path),
        "sha256": sha256(path),
        "instrument": "EURUSD",
        "year": 2025,
        "month": 1,
    }
    provenance = {
        "source": "generated benchmark fixture",
        "license": "test only",
        "synthetic": True,
    }
    results = {}
    for name, action in [
        (
            "uninterrupted",
            lambda: StreamingCatalog(root / "baseline").commit(
                quotes_from_archive(source), path, provenance
            ),
        ),
        ("checkpointed_first", lambda: import_archive(root / "resumed", source, provenance)),
        ("verified_prefix_reuse", lambda: import_archive(root / "resumed", source, provenance)),
    ]:
        started, cpu = time.perf_counter(), time.process_time()
        result = action()
        manifest = result[0] if isinstance(result, tuple) else result
        results[name] = {
            "wall_seconds": time.perf_counter() - started,
            "cpu_seconds": time.process_time() - cpu,
            "process_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
            "dataset_hash": manifest["dataset_hash"],
        }
        if isinstance(result, tuple):
            results[name]["resume"] = result[1]
    if len({r["dataset_hash"] for r in results.values()}) != 1:
        raise AssertionError("checkpointed and uninterrupted identity differ")
    receipt = {
        "fixture": f"{args.rows} generated millisecond EURUSD rows, not historical market data",
        "results": results,
        "disk_bytes": sum(p.stat().st_size for p in root.rglob("*") if p.is_file()),
        "source_context": source_identity(),
        "limitations": [
            "Uncontrolled OS page cache; no cold-cache or target-host claim.",
            "Prefix reuse still decompresses and verifies raw prefix and full canonical stream.",
            "RSS is process high-water mark, not an isolated per-stage peak.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
