#!/usr/bin/env python3
"""Restart and batch-size equivalence for the Rust execution engine.

The migration gate requires evidence that execution is deterministic across
restart and different batch sizes. For each case this script checks that:

1. ``--batch-size N`` for several N produces exactly the single-pass result
   (the engine saves and restores its state every N quotes), and
2. a run split at a quote boundary -- first half with ``--dump-state``, second
   half with ``--resume-from`` -- produces exactly the single-pass result.

Each of those results is also compared against the Python reference, so the
evidence ties the engine's restart behaviour to the oracle rather than only to
itself.

Usage:
    python scripts/parity_raptor_restart.py [--cases N] [--instrument NAME]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "rust/raptor-engine/target/release/raptor-engine"
sys.path.insert(0, str(ROOT / "scripts"))

import parity_raptor_engine as harness  # noqa: E402

BATCH_SIZES = (1, 2, 3, 7, 64)


def run_engine(request: dict, *options: str) -> dict:
    return harness.run_rust(request, *options)


def split_request(profile, spec, quotes, signals, conservative, partial, boundary: int):
    """A request for the first `boundary` quotes and one for the remainder."""
    prefix = harness.build_request(profile, spec, quotes[:boundary], signals, conservative, partial)
    suffix = harness.build_request(profile, spec, quotes[boundary:], signals, conservative, partial)
    return prefix, suffix


def compare_equity(label: str, baseline: dict, other: dict, failures: list) -> None:
    """Restart/batch equivalence must cover the opt-in equity report too."""
    left, right = baseline.get("equity"), other.get("equity")
    if left is None or right is None:
        failures.append({"label": label, "reason": "equity report missing"})
        return
    if left != right:
        failures.append(
            {
                "label": label,
                "reason": "equity report differs after restart/batching",
                "baseline_trades": len(left.get("trades", [])),
                "other_trades": len(right.get("trades", [])),
                "baseline_ending": str(left.get("ending_equity")),
                "other_ending": str(right.get("ending_equity")),
            }
        )


def compare_results(label: str, expected: dict, actual: dict, failures: list) -> None:
    mismatches: list = []
    harness.compare(expected, actual, mismatches)
    if mismatches:
        failures.append({"label": label, "mismatches": mismatches[:5]})


def check_case(case: int, instrument: str, rng: random.Random, failures: list) -> bool:
    profile, spec, quotes, signals, partial, fill_model = harness.generate_case(rng, instrument)
    scale = profile.price_scale
    try:
        reference = harness.normalize_python(
            harness.replay(quotes, profile, spec, signals, True, fill_model=fill_model),
            scale,
        )
    except Exception as exc:  # reference rejected the stream
        print(f"case {case}: reference rejected: {exc}")
        return False

    request = harness.build_request(profile, spec, quotes, signals, True, partial)
    single = run_engine(request)
    compare_results(f"case {case} single-pass vs reference", reference, single, failures)

    # Equity reporting is opt-in; exercise it explicitly so restart and batching
    # are proven not to perturb per-trade observations or the ending balance.
    equity_single = run_engine(request, "--emit-equity")

    # 1. Batching with an in-process state save/restore every N quotes.
    for size in BATCH_SIZES:
        batched = run_engine(request, "--batch-size", str(size))
        compare_results(f"case {case} batch-size {size} vs single-pass", single, batched, failures)
        batched_equity = run_engine(request, "--batch-size", str(size), "--emit-equity")
        compare_equity(
            f"case {case} batch-size {size} equity vs single-pass",
            equity_single,
            batched_equity,
            failures,
        )

    # 2. A genuine cross-process restart at a quote boundary.
    for boundary in sorted({1, max(1, len(quotes) // 2), max(1, len(quotes) - 1)}):
        if boundary >= len(quotes):
            continue
        prefix, suffix = split_request(profile, spec, quotes, signals, True, partial, boundary)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            state_path = handle.name
        run_engine(prefix, "--dump-state", state_path, "--emit-equity")
        restarted = run_engine(suffix, "--resume-from", state_path, "--emit-equity")
        Path(state_path).unlink()
        compare_results(
            f"case {case} restart at quote {boundary} vs single-pass",
            single,
            restarted,
            failures,
        )
        compare_equity(
            f"case {case} restart at quote {boundary} equity vs single-pass",
            equity_single,
            restarted,
            failures,
        )
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=60)
    parser.add_argument("--instrument", default="all")
    parser.add_argument("--seed", type=int, default=20261112)
    args = parser.parse_args()

    instruments = harness.INSTRUMENTS if args.instrument == "all" else [args.instrument]
    rng = random.Random(args.seed)
    failures: list = []
    checked = 0
    for case in range(args.cases):
        instrument = rng.choice(instruments)
        if check_case(case, instrument, rng, failures):
            checked += 1

    print(f"restart/batch cases checked {checked}/{args.cases}")
    if failures:
        print(f"failures: {len(failures)}")
        for failure in failures[:5]:
            print(json.dumps(failure)[:2000])
        return 1
    print("restart/batch parity passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
