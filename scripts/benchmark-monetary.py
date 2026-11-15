#!/usr/bin/env python3
"""All-eight synthetic native worker resource probe; not historical or VPS evidence."""

import argparse
import hashlib
import json
from pathlib import Path
import resource
import time
from decimal import Decimal as D

from apps.coordinator.service import cycle
from factory.contracts import (
    SYMBOLS,
    ExperimentContract,
    Signal,
    StrategySpec,
    Window,
    fingerprint,
    serialize,
)
from factory.data import Catalog, Quote, atomic_bytes
from factory.experiments import Store
from factory.instruments import synthetic_profile
from factory.provenance import source_identity, execution_revision
from factory.simulation.ledger import EXECUTION_VERSION


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rows", type=int, default=100000)
    args = parser.parse_args()
    if args.state.exists() or not 720 <= args.rows <= 1000000:
        parser.error("new isolated state and rows in 720..1000000 required")
    wall_start = time.perf_counter()
    own_start = resource.getrusage(resource.RUSAGE_SELF)
    child_start = resource.getrusage(resource.RUSAGE_CHILDREN)
    context = source_identity()
    args.state.mkdir(parents=True)
    catalog = Catalog(args.state / "catalog")
    store = Store(args.state / "factory.sqlite")
    start = 1735689600 * 10**9
    prepared = []
    for symbol in SYMBOLS:
        profile = synthetic_profile(symbol)
        base = 150 if symbol == "USDJPY" else 2000 if symbol == "XAUUSD" else D("1.1")
        center = int(D(base) * profile.price_scale)

        def quotes():
            for index in range(args.rows):
                phase = index % 1200
                bid = center + (phase if phase < 600 else 1200 - phase) - 300
                # Source spread alternates below/above the conservative floor.
                ask = bid + 5 + (index // 1000) % 30
                yield Quote(
                    symbol,
                    start + index * 10**9,
                    bid,
                    ask,
                    profile.price_scale,
                    "synthetic-integer-triangle/v1",
                    "monetary-resource-probe",
                    index,
                    source_precision="second-fixture",
                )

        manifest = catalog.commit(
            quotes(),
            serialize(
                {
                    "generator": "integer-triangle/v1",
                    "symbol": symbol,
                    "rows": args.rows,
                    "center": center,
                    "start_ns": start,
                }
            ).encode(),
            {
                "source": "synthetic integer triangle resource fixture",
                "synthetic": True,
                "license": "project-generated software test fixture",
            },
        )
        spec = StrategySpec(
            instrument=symbol,
            timeframe="M1",
            signal=Signal(operator="momentum", lookback=3, threshold="1"),
            stop_ticks=100,
        )
        contract = ExperimentContract(
            strategy_hash=spec.strategy_hash,
            dataset_hash=manifest["dataset_hash"],
            instrument_hash=fingerprint(profile),
            engine_version="1.231.0",
            fill_version=EXECUTION_VERSION,
            code_revision=execution_revision(),
            evaluation_policy="synthetic-monetary-resource/v1",
            scenario="historical-pessimistic/v1",
            seed=6123,
            windows=(
                Window(
                    start_ns=start, end_ns=start + (args.rows - 1) * 10**9 + 1, role="train_only"
                ),
            ),
        )
        payload = {
            "strategy": spec.model_dump(mode="json"),
            "profile": profile.model_dump(mode="json"),
            "contract": contract.model_dump(mode="json"),
        }
        store.register_strategy(spec)
        store.enqueue(
            "research", payload, contract.experiment_hash, actor="synthetic-resource-probe"
        )
        prepared.append(
            {
                "instrument": symbol,
                "experiment_hash": contract.experiment_hash,
                "dataset_hash": manifest["dataset_hash"],
            }
        )
    prepared_wall = time.perf_counter()
    store.pause(False, "synthetic-resource-probe")
    for _ in SYMBOLS:
        if not cycle(store, args.state):
            raise RuntimeError("expected next supervised monetary worker")
    rows = store.rows("SELECT instrument,result_json FROM experiments")
    jobs = store.rows("SELECT state,error FROM jobs")
    resources = [
        json.loads(r["resources_json"])
        for r in store.rows("SELECT resources_json FROM attempt_resources")
    ]
    summaries = []
    for row in rows:
        result = json.loads(row["result_json"])
        summaries.append(
            {
                "instrument": row["instrument"],
                "source_quotes": result["quote_count"],
                "native_quote_events": result["native_quote_event_count"],
                "closed_trades": len(result["trades"]),
                "ending_equity": result["ending_equity"],
                "open_inventory": result["open_trade"] is not None,
                "integrity_errors": result["integrity_errors"],
                "native_reference_status": result["reconciliation"]["native_reference_status"],
            }
        )
    unchanged = context == source_identity()
    passed = (
        len(rows) == len(SYMBOLS) == len(jobs)
        and unchanged
        and all(j["state"] == "COMPLETED" for j in jobs)
        and all(
            not r["integrity_errors"]
            and r["native_reference_status"] == "VERIFIED"
            and r["closed_trades"] > 0
            and r["source_quotes"] == args.rows
            for r in summaries
        )
    )
    own = resource.getrusage(resource.RUSAGE_SELF)
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    report = {
        "status": "PASS_BOUNDED_SYNTHETIC_MONETARY" if passed else "FAIL",
        "scope": "8 isolated native synthetic training jobs; no historical validation, target-VPS throughput or soak claim",
        "software_verified": False,
        "data_ready": False,
        "operation_ready": False,
        "source_context": context,
        "source_unchanged": unchanged,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "engine": "nautilus_trader/1.231.0",
        "execution_version": EXECUTION_VERSION,
        "rows_per_instrument": args.rows,
        "datasets_and_experiments": prepared,
        "results": summaries,
        "jobs": jobs,
        "preparation_wall_seconds": prepared_wall - wall_start,
        "supervised_workers_wall_seconds": time.perf_counter() - prepared_wall,
        "total_wall_seconds": time.perf_counter() - wall_start,
        "parent_plus_children_cpu_seconds": own.ru_utime
        + own.ru_stime
        - own_start.ru_utime
        - own_start.ru_stime
        + child.ru_utime
        + child.ru_stime
        - child_start.ru_utime
        - child_start.ru_stime,
        "measured_worker_cpu_seconds": sum(r.get("cpu_seconds", 0) for r in resources),
        "parent_peak_rss_bytes": own.ru_maxrss * 1024,
        "max_worker_peak_rss_bytes": max(
            (r.get("peak_rss_bytes") or 0 for r in resources), default=0
        ),
        "max_worker_sampled_rss_bytes": max(
            (r.get("peak_rss_bytes_sampled") or 0 for r in resources), default=0
        ),
        "disk_state_bytes": sum(p.stat().st_size for p in args.state.rglob("*") if p.is_file()),
        "cgroup_cpu_max": Path("/sys/fs/cgroup/cpu.max").read_text().strip(),
        "cgroup_memory_max": Path("/sys/fs/cgroup/memory.max").read_text().strip(),
        "warnings": [
            "Synthetic broker conventions only",
            "OS cache uncontrolled",
            "CPU excludes process imports before main",
            "Memory is per-process RSS, not summed simultaneous memory or a forced 8-GB proof",
            "The three non-USD quote feeds have explicit additional conversion-context events",
        ],
    }
    atomic_bytes(args.output, json.dumps(report, indent=2, sort_keys=True).encode())
    print(json.dumps(report))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
