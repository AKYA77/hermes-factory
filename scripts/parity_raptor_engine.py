#!/usr/bin/env python3
"""Direct parity between the Rust execution engine and the Python reference.

The reference is the NautilusTrader-backed ``factory/simulation/runner.py``;
case generation, normalization and comparison come from the Nautilus-free
``raptor_cases`` module so the golden verifier does not need this import.

Usage:
    python scripts/parity_raptor_engine.py --cases N --instrument all --seed S
"""

from __future__ import annotations

import argparse
import json
import random
import sys

from nautilus_trader.model.book import OrderBook
from nautilus_trader.model.data import BookOrder
from nautilus_trader.model.enums import BookType, OrderSide, OrderType

from factory.simulation.nautilus import AdverseFillModel
from factory.simulation.runner import replay

import raptor_cases as cases
from raptor_cases import (  # re-exported for the sibling harnesses
    BINARY,
    INSTRUMENTS,
    build_request,
    compare,
    generate_case_params,
    make_quotes,
    normalize_python,
    run_rust,
)

__all__ = [
    "BINARY",
    "FiniteEligibleBook",
    "INSTRUMENTS",
    "build_fill_model",
    "build_request",
    "compare",
    "generate_case",
    "generate_case_params",
    "main",
    "make_quotes",
    "normalize_python",
    "replay",
    "run_rust",
]


class FiniteEligibleBook(AdverseFillModel):
    """Mirrors the reference test's finite eligible book.

    For the configured order type (and, for MARKET, the configured side) the
    simulated book only supplies half the order quantity, so the order fills
    partially and its remainder is cancelled. Other orders keep the reference
    adverse fill model, including its conservative slippage.
    """

    def __init__(self, profile, limited_type, entry_side=None):
        super().__init__(profile, True)
        self.limited_type = limited_type
        self.entry_side = entry_side

    def get_orderbook_for_fill_simulation(self, instrument, order, best_bid, best_ask):
        if order.order_type != self.limited_type or (
            order.order_type == OrderType.MARKET and order.side != self.entry_side
        ):
            return super().get_orderbook_for_fill_simulation(
                instrument, order, best_bid, best_ask
            )
        book = OrderBook(instrument.id, BookType.L2_MBP)
        quantity = instrument.make_qty(order.quantity.as_decimal() / 2)
        slip = 2 * self.profile.pip_size
        book.add(
            BookOrder(
                OrderSide.BUY, instrument.make_price(best_bid.as_decimal() - slip), quantity, 1
            ),
            0,
            0,
        )
        book.add(
            BookOrder(
                OrderSide.SELL, instrument.make_price(best_ask.as_decimal() + slip), quantity, 2
            ),
            0,
            0,
        )
        self.trace.append(
            {
                "order_id": str(order.client_order_id),
                "order_type": str(order.order_type),
                "side": str(order.side),
                "bid": str(best_bid),
                "ask": str(best_ask),
                "slippage": str(slip),
                "quantity": str(quantity),
                "model": "finite-eligible-book/v1",
            }
        )
        return book


def build_fill_model(profile, partial):
    """The NautilusTrader fill model for a case, or None for unbounded depth."""
    if partial is None:
        return None
    if partial["order_type"] == "MARKET":
        side = OrderSide.BUY if partial.get("side") == "BUY" else OrderSide.SELL
        return FiniteEligibleBook(profile, OrderType.MARKET, side)
    return FiniteEligibleBook(profile, OrderType.STOP_MARKET)


def generate_case(rng, instrument):
    """Case parameters plus the NautilusTrader fill model the reference needs."""
    profile, spec, quotes, signals, partial = cases.generate_case_params(rng, instrument)
    return profile, spec, quotes, signals, partial, build_fill_model(profile, partial)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=40)
    parser.add_argument("--seed", type=int, default=20261112)
    parser.add_argument("--instrument", default="EURUSD")
    args = parser.parse_args()

    if not cases.BINARY.exists():
        print(f"rust binary missing: {cases.BINARY}", file=sys.stderr)
        return 2

    rng = random.Random(args.seed)
    passed = 0
    failures = []
    for case in range(args.cases):
        instrument = args.instrument if args.instrument != "all" else rng.choice(cases.INSTRUMENTS)
        profile, spec, quotes, signals, partial, fill_model = generate_case(rng, instrument)
        scale = profile.price_scale
        conservative = True
        try:
            py_raw = replay(quotes, profile, spec, signals, conservative, fill_model=fill_model)
        except Exception as exc:  # reference rejected the stream
            print(f"case {case}: python rejected: {exc}")
            continue
        py = cases.normalize_python(py_raw, scale)
        request = cases.build_request(profile, spec, quotes, signals, conservative, partial)
        try:
            rs = cases.run_rust(request)
        except Exception as exc:
            failures.append({"case": case, "instrument": instrument, "error": str(exc)})
            continue
        mismatches = []
        cases.compare(py, rs, mismatches)
        if mismatches:
            failures.append(
                {
                    "case": case,
                    "instrument": instrument,
                    "stop_ticks": spec.stop_ticks,
                    "direction": spec.direction,
                    "max_hold": spec.max_hold_seconds,
                    "quote_count": len(quotes),
                    "signal_count": len(signals),
                    "mismatches": mismatches[:8],
                }
            )
        else:
            passed += 1

    print(f"passed {passed}/{args.cases}")
    if failures:
        print(f"failures: {len(failures)}")
        for failure in failures[:5]:
            print(json.dumps(failure, indent=1)[:4000])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
