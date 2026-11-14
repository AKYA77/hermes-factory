"""Bounded offline synthetic research/improvement rehearsal, not market validation."""

import argparse
import json
import os
from pathlib import Path
import resource
import time

from apps.coordinator.service import cycle
from factory.data import atomic_bytes
from factory.experiments import Store
from factory.exploration.persistent import Search, SearchProtocol, status
from factory.improvement.service import Improvement, ImprovementPolicy
from factory.operations.fixtures import seed
from factory.provenance import source_identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=8)
    parser.add_argument("--rows", type=int, default=2000)
    args = parser.parse_args()
    if args.state.exists() or not 4 <= args.trials <= 32 or not 240 <= args.rows <= 10000:
        parser.error("new state, 4..32 trials and 240..10000 rows required")
    context = source_identity()
    wall = time.perf_counter()
    own_start = resource.getrusage(resource.RUSAGE_SELF)
    child_start = resource.getrusage(resource.RUSAGE_CHILDREN)
    payload = seed(args.state, args.rows)
    store = Store(args.state / "factory.sqlite")
    protocol = SearchProtocol(
        dataset_hash=payload["contract"]["dataset_hash"],
        profile=payload["profile"],
        window=payload["contract"]["windows"][0],
        family="momentum",
        timeframe="M1",
        code_revision=payload["contract"]["code_revision"],
        seed=42,
        max_trials=args.trials,
        cpu_budget_seconds=3600,
    )
    identity = Search(store, args.state).register(protocol)
    policy = ImprovementPolicy(search_protocol_hash=identity, max_parent_plans=4, max_children=2)
    Improvement(store, args.state).register(policy)
    paused_admission = not cycle(store, args.state)
    store.pause(False, "bounded-probe")
    os.environ["HTTPS_PROXY"] = os.environ["HTTP_PROXY"] = "http://127.0.0.1:1"
    idle = 0
    cycles = 0
    for _ in range(args.trials * 4 + 40):
        store = Store(args.state / "factory.sqlite")
        worked = cycle(store, args.state)
        cycles += 1
        idle = 0 if worked else idle + 1
        if idle >= 3 and len(store.rows("SELECT * FROM search_outcomes")) == args.trials:
            break
    search = Search(store, args.state)
    search.feedback()
    improvement = Improvement(store, args.state)
    improvement.feedback()
    experiments = store.rows("SELECT result_json FROM experiments")
    measurements = [
        json.loads(r["resources_json"])
        for r in store.rows("SELECT resources_json FROM attempt_resources")
    ]
    failed = store.rows("SELECT job_id,error FROM jobs WHERE state!='COMPLETED'")
    snapshot = improvement.status()
    if (
        not paused_admission
        or failed
        or len(store.rows("SELECT * FROM search_outcomes")) != args.trials
        or not snapshot["children"]
        or not snapshot["outcomes"]
        or source_identity() != context
    ):
        raise ValueError("bounded workflow failed; preserve and inspect isolated state")
    own = resource.getrusage(resource.RUSAGE_SELF)
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    report = {
        "source": context,
        "source_context_unchanged": True,
        "scope": "synthetic training and one controlled round; invalid network proxy; no target-host/market/soak claim",
        "status": "PASS_BOUNDED_SYNTHETIC_WORKFLOW",
        "operation_ready": False,
        "wall_seconds": time.perf_counter() - wall,
        "cpu_seconds_parent_plus_children": own.ru_utime
        + own.ru_stime
        - own_start.ru_utime
        - own_start.ru_stime
        + child.ru_utime
        + child.ru_stime
        - child_start.ru_utime
        - child_start.ru_stime,
        "parent_peak_rss_bytes": own.ru_maxrss * 1024,
        "worker_peak_rss_bytes": max(m["peak_rss_bytes"] for m in measurements),
        "rows_per_native_replay": args.rows,
        "native_replays": len(experiments),
        "native_quote_events": sum(
            json.loads(e["result_json"])["quote_count"] for e in experiments
        ),
        "cycles": cycles,
        "paused_admission_verified": paused_admission,
        "research": status(store),
        "improvement": snapshot,
        "pending_edges_preserved": store.rows(
            "SELECT count(*) n FROM improvement_edges e LEFT JOIN improvement_outcomes o USING(edge_id) WHERE o.edge_id IS NULL"
        )[0]["n"],
        "pending_note": "soft CPU reservation can leave children pending; this is retained budget state, not discarded hypotheses",
    }
    atomic_bytes(args.output, json.dumps(report, indent=2, sort_keys=True).encode())
    print(json.dumps(report))


if __name__ == "__main__":
    main()
