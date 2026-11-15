"""Reproducible exact-feature comparison on an unmodified canonical source window.

This measures feature compilation only, never Nautilus/research throughput.
"""

import argparse
import hashlib
from itertools import islice
import json
from pathlib import Path
import resource
import time

from factory.contracts import Signal, StrategySpec, fingerprint, serialize
from factory.data import Catalog, atomic_bytes
from factory.features.disk import BarCache
from factory.provenance import source_identity
from factory.strategies import iter_bar_signals, iter_signals


def digest(signals):
    value = hashlib.sha256()
    count = 0
    for signal in signals:
        value.update(serialize(signal).encode() + b"\n")
        count += 1
    return {"sha256": value.hexdigest(), "count": count}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--rows", type=int, default=200000)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.rows <= 10000000:
        parser.error("rows must be in 1..10000000")
    if args.cache.exists() and any(args.cache.iterdir()):
        parser.error("use an empty dedicated cache directory for the build measurement")
    context = source_identity()
    revision = context["git_commit"] + "@source-sha256:" + context["source_sha256"]
    cat = Catalog(args.catalog)
    manifest = cat.verify(args.dataset, deep=True)
    last = None
    for last in islice(cat.read(args.dataset), args.rows):
        pass
    if last is None:
        raise ValueError("empty dataset")
    # Include ALL source records at the last selected timestamp, never cut a tie.
    end_ns = last.event_ts_utc_ns + 1
    rows = sum(1 for _ in cat.read(args.dataset, end_ns=end_ns))
    specs = [
        StrategySpec(
            instrument=manifest["instrument"],
            timeframe=tf,
            signal=Signal(operator=op, lookback=8 + n, threshold="1"),
            confirmations=("H1",),
            stop_ticks=100,
        )
        for n, (tf, op) in enumerate(
            (
                ("M1", "momentum"),
                ("M1", "mean_reversion"),
                ("M1", "breakout"),
                ("M5", "momentum"),
                ("M5", "mean_reversion"),
                ("M5", "breakout"),
            )
        )
    ]
    cache = BarCache(args.cache)
    results = {}

    def read():
        return cat.read(args.dataset, end_ns=end_ns)

    for mode in ("direct", "cache_build", "cache_reuse"):
        wall, cpu = time.perf_counter(), time.process_time()
        hashes = []
        for spec in specs:
            if mode == "direct":
                hashes.append(digest(iter_signals(read(), spec)))
            else:
                with cache.events(
                    cat,
                    args.dataset,
                    "source-units-only-no-monetary-profile",
                    revision,
                    (spec.timeframe, *spec.confirmations),
                    end_ns=end_ns,
                ) as events:
                    hashes.append(digest(iter_bar_signals(events, spec)))
        results[mode] = {
            "wall_seconds": time.perf_counter() - wall,
            "cpu_seconds": time.process_time() - cpu,
            "process_peak_rss_bytes_cumulative": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            * 1024,
            "signal_digests": hashes,
            "cache_stats_cumulative": dict(cache.stats),
        }
    equal = all(
        results[m]["signal_digests"] == results["direct"]["signal_digests"]
        for m in ("cache_build", "cache_reuse")
    )
    report = {
        "source": context,
        "source_context_unchanged": source_identity() == context,
        "dataset_hash": args.dataset,
        "rows": rows,
        "end_ns_exclusive": end_ns,
        "synthetic": manifest["provenance"].get("synthetic", False),
        "operation": "six exact signal compilations only; NO native replay or financial validation",
        "specs": [s.model_dump(mode="json") for s in specs],
        "results": results,
        "signal_digest_parity": equal,
        "cache_disk_bytes": sum(p.stat().st_size for p in args.cache.rglob("*") if p.is_file()),
        "os_page_cache": "uncontrolled; no cold disk assertion",
        "rss_scope": "cumulative process high-water mark, includes setup; not independent per-mode peaks",
        "report_identity": fingerprint(
            {"dataset": args.dataset, "revision": revision, "end_ns": end_ns}
        ),
    }
    if not equal or not report["source_context_unchanged"]:
        raise ValueError("feature parity or source identity failed")
    atomic_bytes(args.output, json.dumps(report, indent=2, sort_keys=True).encode())
    print(json.dumps({k: v for k, v in report.items() if k not in ("specs", "results")}, indent=2))


if __name__ == "__main__":
    main()
