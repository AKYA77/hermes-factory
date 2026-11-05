"""Bounded synthetic recurring-research benchmark. Not historical/VPS/soak evidence."""

import argparse
import json
from pathlib import Path
import resource
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--trials", type=int, default=16)
    p.add_argument("--rows", type=int, default=2000)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if not 8 <= args.trials <= 64 or not 120 <= args.rows <= 20000:
        p.error("trials 8..64 and synthetic rows 120..20000 required")
    if args.state.exists():
        p.error("use a new isolated state directory")
    wall = time.perf_counter()
    self_before = resource.getrusage(resource.RUSAGE_SELF)
    children_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    from factory.operations.fixtures import seed
    from factory.experiments import Store
    from factory.exploration.persistent import Search, SearchProtocol, status
    from factory.provenance import source_identity
    from factory.data import atomic_bytes
    from apps.coordinator.service import cycle

    context = source_identity()
    args.state.mkdir(parents=True)
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
    paused = not cycle(store, args.state)
    store.pause(False, "probe")
    cycles = 0
    while cycles < args.trials + 4:
        # Object restart exercises durable state. This is not an OS/reboot soak.
        store = Store(args.state / "factory.sqlite")
        worked = cycle(store, args.state)
        cycles += 1
        if (
            not worked
            and len(store.rows("SELECT trial_id FROM search_trials")) >= args.trials
            and not Search(store, args.state).pending()
        ):
            break
    Search(store, args.state).feedback()
    state = status(store)
    experiments = store.rows("SELECT result_json FROM experiments")
    events = sum(json.loads(r["result_json"])["quote_count"] for r in experiments)
    outputs = store.rows("SELECT * FROM search_outcomes")
    metrics = [
        json.loads(r["resources_json"])
        for r in store.rows("SELECT resources_json FROM attempt_resources")
    ]
    failed = store.rows("SELECT count(*) n FROM jobs WHERE state!='COMPLETED'")[0]["n"]
    own = resource.getrusage(resource.RUSAGE_SELF)
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    unchanged = source_identity() == context
    if (
        state["trials_considered"] != args.trials
        or len(outputs) != args.trials
        or failed
        or not paused
        or not unchanged
    ):
        raise ValueError("bounded research workflow failed; inspect retained isolated state")
    report = {
        "status": "PASS_BOUNDED_SYNTHETIC_RESEARCH",
        "operation_ready": False,
        "source_context": context,
        "source_context_unchanged": unchanged,
        "scope": "synthetic training only; no independent evaluation, target VPS or multi-day soak",
        "protocol_hash": identity,
        "dataset_hash": protocol.dataset_hash,
        "rows_per_replay": args.rows,
        "instrument": protocol.profile.instrument,
        "window": protocol.window.model_dump(mode="json"),
        "engine": "nautilus_trader/1.231.0",
        "fill_policy": payload["contract"]["fill_version"],
        "budgeted_trials": args.trials,
        "cycles": cycles,
        "paused_admission_verified": paused,
        "state": state,
        "full_successful_native_replays": len(experiments),
        "quote_events_replayed": events,
        "independent_validations": 0,
        "wall_seconds": time.perf_counter() - wall,
        "total_parent_plus_children_cpu_seconds": own.ru_utime
        + own.ru_stime
        - self_before.ru_utime
        - self_before.ru_stime
        + child.ru_utime
        + child.ru_stime
        - children_before.ru_utime
        - children_before.ru_stime,
        "parent_peak_rss_bytes": own.ru_maxrss * 1024,
        "worker_peak_rss_bytes": max((m.get("peak_rss_bytes") or 0 for m in metrics), default=0),
        "peak_system_memory_bytes": None,
        "disk_state_bytes": sum(f.stat().st_size for f in args.state.rglob("*") if f.is_file()),
        "cgroup_memory_max": Path("/sys/fs/cgroup/memory.max").read_text().strip(),
        "cgroup_cpu_max": Path("/sys/fs/cgroup/cpu.max").read_text().strip(),
        "warnings": [
            "CPU includes measured benchmark parent and subprocesses, excluding CLI startup before main",
            "OS page cache uncontrolled",
            "monetary fixtures are synthetic",
            "budgets do not constitute an 8GB enforcement/soak proof",
        ],
    }
    atomic_bytes(args.output, json.dumps(report, indent=2, sort_keys=True).encode())
    print(json.dumps(report))


if __name__ == "__main__":
    main()
