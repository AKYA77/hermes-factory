"""Measure existing bounded TPE reconstruction before changing persistence.

Histories are labeled synthetic optimizer inputs, never market experiment results.
"""

import argparse
import json
from pathlib import Path
import resource
import time

import optuna

from factory.contracts import serialize
from factory.data import atomic_bytes
from factory.exploration.persistent import SearchProtocol, rebuild_study
from factory.instruments import synthetic_profile
from factory.provenance import source_identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    context = source_identity()
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    p = SearchProtocol(
        dataset_hash="0" * 64,
        profile=synthetic_profile("EURUSD"),
        window={"start_ns": 1, "end_ns": 2, "role": "train_only"},
        family="momentum",
        timeframe="M1",
        code_revision="no-execution-benchmark",
        seed=42,
        max_trials=256,
    )
    results = []
    for size in (0, 16, 64, 256):
        # Valid discrete search-grid parameters; fabricated objective is explicitly
        # a toy kernel cost input. It never enters the Factory registry/leaderboard.
        history = [
            {
                "parameters_json": serialize(
                    {
                        "lookback": 2 + i % 47,
                        "threshold_tenths": 5 + i % 26,
                        "stop_ticks": 20 + (i % 19) * 10,
                        "confirmation": "none",
                    }
                ),
                "outcome": "COMPLETE",
                "objective": -float(abs(2 + i % 47 - 13)),
            }
            for i in range(size)
        ]
        timings = []
        proposals = []
        for _ in range(5):
            wall, cpu = time.perf_counter(), time.process_time()
            study = rebuild_study(p, history, size)
            value = study.ask(fixed_distributions=p.distributions()).params
            timings.append(
                {
                    "wall_seconds": time.perf_counter() - wall,
                    "cpu_seconds": time.process_time() - cpu,
                }
            )
            proposals.append(value)
        if not all(v == proposals[0] for v in proposals):
            raise ValueError("optimizer reconstruction changed its proposal")
        results.append(
            {
                "history_rows": size,
                "repeats": timings,
                "deterministic_proposal": proposals[0],
                "deterministic": True,
            }
        )
    report = {
        "source": context,
        "source_context_unchanged": source_identity() == context,
        "scope": "labeled synthetic histories, no replay or strategy result; bounded protocol max 256 trials",
        "results": results,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "decision": "retain serialized registry reconstruction; this probe does not authorize a persistence change",
    }
    if not report["source_context_unchanged"]:
        raise ValueError("source changed during optimizer probe")
    atomic_bytes(args.output, json.dumps(report, indent=2, sort_keys=True).encode())
    print(json.dumps(report))


if __name__ == "__main__":
    main()
