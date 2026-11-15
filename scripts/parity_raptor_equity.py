#!/usr/bin/env python3
"""Verify the Rust engine's opt-in equity report against the Python reference.

Realized equity is reporting-only data, so it cannot disturb the frozen golden
contract (see the `--emit-equity` flag). This harness proves it nonetheless:
for every generated case the per-trade equity observed when an order was created
and after it settled must equal the reference exactly, and the reported ending
equity must equal the reference's own ending balance.

Run it through this script rather than hand-building `replay()` arguments --
`replay` takes the finite-book configuration through the keyword-only
`fill_model`, and calling it positionally with the request dict silently drops
the partial book and manufactures false discrepancies.

    env -u PYTHONPATH .venv/bin/python scripts/parity_raptor_equity.py \
        --cases 80 --seed 4242 --instrument EURUSD
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from factory.simulation.runner import replay  # noqa: E402

import raptor_cases as cases  # noqa: E402
from parity_raptor_engine import generate_case  # noqa: E402


def frac(value):
    return None if value is None else Fraction(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, default=80)
    parser.add_argument("--seed", type=int, default=4242)
    parser.add_argument("--instrument", default="EURUSD")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    checked = value_mismatches = count_mismatches = 0
    failures = []

    for index in range(args.cases):
        profile, spec, quotes, signals, partial, fill_model = generate_case(rng, args.instrument)
        conservative = True
        reference = replay(quotes, profile, spec, signals, conservative, fill_model=fill_model)
        request = cases.build_request(profile, spec, quotes, signals, conservative, partial)
        rust = cases.run_rust(request, "--emit-equity")

        closed = list(reference["trades"])
        if reference.get("open_trade"):
            closed.append(reference["open_trade"])
        expected = [(t.get("equity_before"), t.get("equity_after")) for t in closed]

        equity = rust.get("equity")
        if equity is None:
            failures.append({"case": index, "field": "equity", "reason": "report absent"})
            continue
        observed = [
            (
                Fraction(int(row["before"]["n"]), int(row["before"]["d"])),
                Fraction(int(row["after"]["n"]), int(row["after"]["d"])),
            )
            for row in equity["trades"]
        ]

        if len(expected) != len(observed):
            count_mismatches += 1
            failures.append(
                {
                    "case": index,
                    "field": "trade_count",
                    "python": len(expected),
                    "rust": len(observed),
                }
            )
            continue

        bad = []
        for row, ((before, after), (rusted_before, rusted_after)) in enumerate(
            zip(expected, observed)
        ):
            if frac(before) != rusted_before:
                bad.append(
                    {
                        "row": row,
                        "side": "before",
                        "python": str(before),
                        "rust": str(rusted_before),
                    }
                )
            # The still-open trade has no settled equity_after in the reference.
            if after is not None and frac(after) != rusted_after:
                bad.append(
                    {"row": row, "side": "after", "python": str(after), "rust": str(rusted_after)}
                )
        if bad:
            value_mismatches += 1
            failures.append({"case": index, "field": "equity", "rows": bad[:3]})

        ending = Fraction(int(equity["ending_equity"]["n"]), int(equity["ending_equity"]["d"]))
        if ending != Fraction(reference["ending_equity"]):
            value_mismatches += 1
            failures.append(
                {
                    "case": index,
                    "field": "ending_equity",
                    "python": str(reference["ending_equity"]),
                    "rust": str(ending),
                }
            )
        checked += 1

    print(f"equity cases checked {checked}/{args.cases}")
    print(f"value mismatches {value_mismatches}, count mismatches {count_mismatches}")
    if failures:
        print(json.dumps(failures[:5], indent=1))
        return 1
    print(f"equity parity passed {checked}/{checked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
