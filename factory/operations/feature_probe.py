"""Comparable real-source feature compilation probe, never a backtest."""

import argparse
from itertools import islice
import json
from pathlib import Path
import resource
import time

from factory.contracts import Signal, StrategySpec, fingerprint
from factory.data import Catalog, atomic_bytes
from factory.provenance import source_identity
from factory.strategies import compile_signals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--rows", type=int, default=200000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.rows <= 10000000:
        parser.error("rows must be in 1..10000000")
    cat = Catalog(args.catalog)
    manifest = cat.verify(args.dataset)
    spec = StrategySpec(
        instrument=manifest["instrument"],
        timeframe="M1",
        signal=Signal(operator="momentum", lookback=8, threshold="1"),
        confirmations=("M5", "H1"),
        stop_ticks=100,
    )
    context = source_identity()
    wall = time.perf_counter()
    cpu = time.process_time()
    signals = compile_signals(islice(cat.read(args.dataset), args.rows), spec)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    report = {
        "source": context,
        "source_context_unchanged": source_identity() == context,
        "dataset_hash": args.dataset,
        "rows": min(args.rows, manifest["rows"]),
        "instrument": spec.instrument,
        "synthetic": bool(manifest["provenance"].get("synthetic")),
        "operation": "signal compilation only; no simulation/validation",
        "spec": spec.model_dump(mode="json"),
        "signal_hash": fingerprint(signals),
        "signal_count": len(signals),
        "wall_seconds": time.perf_counter() - wall,
        "cpu_seconds": time.process_time() - cpu,
        "peak_rss_bytes": usage.ru_maxrss * 1024,
        "cache_state": "OS page cache uncontrolled; no cold-cache assertion",
    }
    if not report["source_context_unchanged"]:
        raise ValueError("source changed during feature probe")
    atomic_bytes(args.output, json.dumps(report, indent=2, sort_keys=True).encode())
    print(json.dumps(report))


if __name__ == "__main__":
    main()
