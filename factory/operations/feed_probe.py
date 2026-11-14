"""Real-quote native delivery/memory probe with NO orders and NO strategy evidence.

The source grid is empirical. Monetary profile fields are unused fixture scaffolding,
not verified Gold/Forex broker terms. This command never queues an experiment,
calculates profitability, or enables historical evaluation.
"""

import argparse
from decimal import Decimal as D
from itertools import islice
import json
from pathlib import Path
import platform
import resource
import time


def main():
    started = time.perf_counter()
    from factory.contracts import Signal, StrategySpec, fingerprint
    from factory.data import Catalog, atomic_bytes
    from factory.instruments import synthetic_profile
    from factory.provenance import source_identity
    from factory.simulation.runner import replay

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog", required=True, type=Path)
    p.add_argument("--dataset", required=True)
    p.add_argument("--rows", type=int)
    p.add_argument("--materialized-reference", action="store_true")
    p.add_argument("--batch-rows", type=int, default=8192)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    if args.rows is not None and args.rows < 1:
        p.error("rows must be positive")
    if args.materialized_reference and (args.rows is None or args.rows > 500000):
        p.error("materialized fixture reference requires --rows <= 500000")
    context = source_identity()
    cat = Catalog(args.catalog)
    m = cat.verify(args.dataset)
    profile = synthetic_profile(m["instrument"]).model_copy(
        update={
            "tick_size": D(m["observed_price_quantum"]),
            "price_scale": m["price_scale"],
            "source": "UNAPPROVED source-grid feed probe; monetary fixture fields unused; NO ORDERS",
        }
    )
    spec = StrategySpec(
        instrument=m["instrument"],
        timeframe="M1",
        signal=Signal(operator="momentum", lookback=2, threshold="1"),
        stop_ticks=100,
    )
    q = cat.read(args.dataset)
    if args.rows:
        q = islice(q, args.rows)
    result = replay(
        q,
        profile,
        spec,
        (),
        False,
        batch_rows=args.batch_rows,
        inline_paths=False,
        dataset_hash=args.dataset,
        _materialized_reference=args.materialized_reference,
    )
    if result["fills"] or result["trades"] or result["open_trade"] or result["integrity_errors"]:
        raise ValueError("feed probe must not create orders or certify financial results")
    unchanged = source_identity() == context
    if not unchanged:
        raise ValueError("source changed during probe")
    usage = resource.getrusage(resource.RUSAGE_SELF)
    report = {
        "status": "PASS_FEED_PLUMBING_ONLY",
        "source_context": context,
        "source_context_unchanged": unchanged,
        "scope": "real quote delivery through native Nautilus; NO ORDERS, NO historical strategy validation",
        "dataset_hash": args.dataset,
        "source_sha256": m["source_sha256"],
        "parquet_sha256": m["parquet_sha256"],
        "source_first_ns": m["first_ns"],
        "source_last_ns": m["latest_verified_ns"],
        "instrument": m["instrument"],
        "synthetic_source": bool(m["provenance"].get("synthetic")),
        "engine": "nautilus_trader/1.231.0",
        "cost_mode": "historical-reference/v1, unused by orders",
        "monetary_profile_approved": False,
        "rows": result["quote_count"],
        "delivery": "materialized reference"
        if args.materialized_reference
        else "native chunk iterator",
        "batch_rows": args.batch_rows,
        "parameter_proposals": 0,
        "signal_screens": 0,
        "full_strategy_replays": 0,
        "native_feed_replays": 1,
        "actual_fills": 0,
        "wall_seconds": time.perf_counter() - started,
        "cpu_seconds": usage.ru_utime + usage.ru_stime,
        "peak_rss_bytes": usage.ru_maxrss * 1024,
        "spool_bytes": result["quote_count"] * 32,
        "result_hash": fingerprint(result),
        "os_page_cache": "uncontrolled; no cold-cache claim",
        "host": {
            "platform": platform.platform(),
            "cpu_quota": Path("/sys/fs/cgroup/cpu.max").read_text().strip(),
            "memory_limit_bytes": Path("/sys/fs/cgroup/memory.max").read_text().strip(),
        },
        "target_8gb_vps_verified": False,
    }
    atomic_bytes(args.output, json.dumps(report, indent=2, sort_keys=True).encode())
    print(json.dumps(report))


if __name__ == "__main__":
    main()
