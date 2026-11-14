#!/usr/bin/env python3
"""Cold/warm cache and ZSTD compression measurements on a generated partition.

The owner directive asks for warm/cold/compression benchmarks. This script
measures them explicitly instead of leaving the clause to be inferred from other
work, and it states what it cannot do:

* True cold-cache numbers require dropping the OS page cache. That needs
  ``/proc/sys/vm/drop_caches`` write access, which a container normally denies,
  so this script reports **first read after writing** (prefix reuse plus decode)
  versus **second read with the page cache warm**, and labels both rather than
  claiming a genuine cold measurement.
* Compression is measured as encoded size against raw row bytes at several ZSTD
  levels, together with encode wall time. It does not claim a target-host number.

    env -u PYTHONPATH .venv/bin/python scripts/benchmark_compression_cache.py \
        --rows 200000 --output reports/compression-cache-benchmark.json
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from factory.data import Quote  # noqa: E402



def _quotes(rows: int):
    """Generated quotes; same shape as the pytest fixture, without importing it."""
    return [
        Quote(
            "EURUSD",
            1735689600 * 10**9 + i * 10**9,
            110000 + ((i * 37) % 113) * 10,
            110012 + ((i * 37) % 113) * 10,
            100000,
            "synthetic",
            "benchmark",
            i,
        )
        for i in range(rows)
    ]


def _table(rows: int) -> pa.Table:
    q = _quotes(rows)
    return pa.table({
        "event_ts_utc_ns": pa.array([x.event_ts_utc_ns for x in q], pa.int64()),
        "bid_int": pa.array([x.bid_int for x in q], pa.int64()),
        "ask_int": pa.array([x.ask_int for x in q], pa.int64()),
        "price_scale": pa.array([x.price_scale for x in q], pa.int64()),
        "original_record_order": pa.array(
            [x.original_record_order for x in q], pa.int64()
        ),
    })


def measure_compression(table: pa.Table) -> list[dict]:
    raw = table.nbytes
    rows = []
    for level in (1, 3, 6, 9):
        buffer = io.BytesIO()
        start = time.perf_counter()
        pq.write_table(table, buffer, compression="zstd", compression_level=level)
        elapsed = time.perf_counter() - start
        size = buffer.tell()
        rows.append({
            "zstd_level": level,
            "encoded_bytes": size,
            "raw_bytes": raw,
            "ratio": round(raw / size, 4),
            "encode_wall_seconds": round(elapsed, 6),
        })
    return rows


def measure_cache(tmp_path: Path, rows: int) -> dict:
    """First read after writing versus subsequent reads on a warm page cache."""
    table = _table(rows)
    target = tmp_path / "partition.parquet"
    pq.write_table(table, target, compression="zstd", compression_level=1)

    timings = []
    counts = []
    for _ in range(3):
        start = time.perf_counter()
        counts.append(pq.read_table(target).num_rows)
        timings.append(time.perf_counter() - start)
    assert all(count == rows for count in counts), counts
    return {
        "rows": rows,
        "first_read_wall_seconds": round(timings[0], 6),
        "second_read_wall_seconds": round(timings[1], 6),
        "third_read_wall_seconds": round(timings[2], 6),
        "interpretation": "the first read follows a fresh write (no guaranteed cold "
                          "page cache); a genuine cold measurement needs "
                          "/proc/sys/vm/drop_caches access, which containers usually deny",
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=200000)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    import tempfile

    table = _table(args.rows)
    compression = measure_compression(table)
    with tempfile.TemporaryDirectory() as directory:
        cache = measure_cache(Path(directory), args.rows)

    report = {
        "schema_version": "compression-cache-benchmark/v1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rows": args.rows,
        "raw_row_bytes": table.nbytes,
        "compression": compression,
        "cache": cache,
        "envelope": {
            "target": "4 vCPU / 8 GiB",
            "enforced": False,
            "reason": "cgroup v2 controllers are not delegated on this host",
        },
        "synthetic_only": True,
        "notes": [
            "Generated quote rows, not acquired history.",
            "Compression ratios are Arrow/ZSTD artifacts of this schema, not a "
            "data-reduction guarantee.",
        ],
    }
    text = json.dumps(report, indent=1)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")
        print(f"wrote {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
