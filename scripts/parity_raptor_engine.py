"""Parity harness: Python reference engine vs the Rust execution engine.

Generates deterministic fixtures, runs both engines on identical inputs and
reports exact mismatches in fills, trades, P&L and skips.

Usage:
    .venv/bin/python scripts/parity_raptor_engine.py [--cases N] [--seed S]
"""

import argparse
import json
import random
import subprocess
import sys
import tempfile
from decimal import Decimal as D
from fractions import Fraction
from pathlib import Path

from factory.contracts import Signal, StrategySpec
from factory.data import Quote
from factory.instruments import synthetic_profile
from factory.simulation.nautilus import AdverseFillModel
from factory.simulation.runner import replay
from nautilus_trader.model.book import OrderBook
from nautilus_trader.model.data import BookOrder
from nautilus_trader.model.enums import BookType, OrderSide, OrderType


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


ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "rust/raptor-engine/target/release/raptor-engine"

INSTRUMENTS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD", "XAUUSD"]


def make_quotes(instrument, values, step, start, scale):
    return [
        Quote(instrument, start + i * step, b, a, scale, "synthetic", "fixture", i)
        for i, (b, a) in enumerate(values)
    ]


def fraction_parts(value):
    f = Fraction(D(value))
    return int(f.numerator), int(f.denominator)


def normalize_order_states(order_states):
    """Role -> terminal (last submission of a role wins), sorted, id-independent.

    The reference issues a fresh order each time a timeout exit is re-submitted,
    so the same role can appear several times; the engine models one logical
    order per role, so the last state is the one that matters.
    """
    merged = {}
    for state in order_states.values():
        merged[state["role"]] = state.get("terminal")
    return [{"role": role, "terminal": merged[role]} for role in sorted(merged)]


def normalize_python(result, scale):
    fills = []
    for f in result["fills"]:
        fills.append(
            {
                "role": f["role"],
                "ts": f["ts"],
                "qi": f["quote_index"],
                "side": f["side"],
                "price_int": int(D(f["price"]) * scale),
                "size_num": int(Fraction(D(f["size"])).numerator),
                "size_den": int(Fraction(D(f["size"])).denominator),
            }
        )
    trades = []
    for t in result["trades"]:
        ex = t["exit_fill"]
        exact = t.get("pnl_exact") or {}
        trades.append(
            {
                "side": t["side"],
                "entry_ts": t["entry_fill"]["ts"],
                "entry_qi": t["entry_fill"]["quote_index"],
                "exit_ts": ex["ts"] if ex else None,
                "exit_qi": ex["quote_index"] if ex else None,
                "entry_price_int": int(D(t["entry_fill"]["price"]) * scale),
                "exit_price_int": int(D(ex["price"]) * scale) if ex else None,
                "stop_int": int(D(t["stop"]) * scale),
                "target_int": int(D(t["target"]) * scale),
                "flags": t["flags"],
                "exit_reason": t["exit_reason"],
                "exit_reasons": t["exit_reasons"],
                "order_states": normalize_order_states(t.get("order_states") or {}),
                "pnl_num": int(exact.get("numerator", 0)),
                "pnl_den": int(exact.get("denominator", 1)),
                "entered_num": int(Fraction(D(t["entered_quantity"])).numerator),
                "entered_den": int(Fraction(D(t["entered_quantity"])).denominator),
                "requested_num": int(Fraction(D(t["requested_quantity"])).numerator),
                "requested_den": int(Fraction(D(t["requested_quantity"])).denominator),
            }
        )
    open_trade = None
    if result["open_trade"]:
        ot = result["open_trade"]
        exact = ot.get("pnl_exact") or {}
        open_trade = {
            "side": ot["side"],
            "entry_ts": ot["entry_fill"]["ts"],
            "entry_qi": ot["entry_fill"]["quote_index"],
            "exit_ts": None,
            "exit_qi": None,
            "entry_price_int": int(D(ot["entry_fill"]["price"]) * scale),
            "exit_price_int": None,
            "stop_int": int(D(ot["stop"]) * scale),
            "target_int": int(D(ot["target"]) * scale),
            "flags": ot["flags"],
            "exit_reason": None,
            "exit_reasons": [],
            "order_states": normalize_order_states(ot.get("order_states") or {}),
            "pnl_num": int(exact.get("numerator", 0)),
            "pnl_den": int(exact.get("denominator", 1)),
            "entered_num": int(Fraction(D(ot["entered_quantity"])).numerator),
            "entered_den": int(Fraction(D(ot["entered_quantity"])).denominator),
            "requested_num": int(Fraction(D(ot["requested_quantity"])).numerator),
            "requested_den": int(Fraction(D(ot["requested_quantity"])).denominator),
        }
    skips = [s["status"] for s in result["skips"]]
    return {
        "fills": fills,
        "trades": trades,
        "open_trade": open_trade,
        "skips": skips,
        "quote_count": result["quote_count"],
    }


def build_request(profile, spec, quotes, signals, conservative, partial=None):
    return {
        "profile": {
            "instrument": profile.instrument,
            "tick_size": str(profile.tick_size),
            "pip_size": str(profile.pip_size),
            "price_scale": profile.price_scale,
            "base_currency": profile.base_currency,
            "quote_currency": profile.quote_currency,
            "contract_multiplier": str(profile.contract_multiplier),
            "volume_step": str(profile.volume_step),
            "min_volume": str(profile.min_volume),
            "max_volume": str(profile.max_volume),
            "margin_rate": str(profile.margin_rate),
            "min_stop_ticks": profile.min_stop_ticks,
        },
        "spec": {
            "stop_ticks": spec.stop_ticks,
            "target_rr": spec.target_rr,
            "max_hold_seconds": spec.max_hold_seconds,
            "direction": spec.direction,
            "partial": partial,
        },
        "conservative": conservative,
        "quotes": [
            {"ts": q.event_ts_utc_ns, "bid": q.bid_int, "ask": q.ask_int} for q in quotes
        ],
        "signals": [
            {"available_at": s["available_at"], "side": s["side"]} for s in signals
        ],
    }


def run_rust(request, *options):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(request, handle)
        path = handle.name
    try:
        proc = subprocess.run(
            [str(BINARY), path, *options], capture_output=True, text=True, timeout=120
        )
    finally:
        Path(path).unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError(f"rust engine failed: {proc.stderr.strip()}")
    parsed = json.loads(proc.stdout)
    parsed["skips"] = [s["status"] for s in parsed["skips"]]
    for fill in parsed["fills"]:
        fill["size_num"] = int(fill["size_num"])
        fill["size_den"] = int(fill["size_den"])
    for trade in parsed["trades"] + ([parsed["open_trade"]] if parsed["open_trade"] else []):
        for key in ("pnl_num", "pnl_den", "entered_num", "entered_den",
                    "requested_num", "requested_den"):
            trade[key] = int(trade[key])
    return parsed


def diff(label, expected, actual, mismatches):
    if expected == actual:
        return
    mismatches.append({"field": label, "python": expected, "rust": actual})


def compare(py, rs, mismatches):
    diff("fills", py["fills"], rs["fills"], mismatches)
    diff("trades", py["trades"], rs["trades"], mismatches)
    diff("open_trade", py["open_trade"], rs["open_trade"], mismatches)
    diff("skips", py["skips"], rs["skips"], mismatches)
    diff("quote_count", py["quote_count"], rs["quote_count"], mismatches)


def generate_case(rng, instrument):
    profile = synthetic_profile(instrument)
    scale = profile.price_scale
    base = {"EURUSD": 110000, "GBPUSD": 125000, "USDJPY": 149000, "USDCHF": 95000,
            "USDCAD": 135000, "AUDUSD": 65000, "NZDUSD": 60000, "XAUUSD": 230000}[instrument]
    tick = int(profile.tick_size * scale)
    step = rng.choice([10**9, 10**9, 60 * 10**9, 90000 * 10**9])
    count = rng.randint(4, 24)
    spread = rng.choice([tick, 2 * tick, 5 * tick, 10 * tick])
    values = []
    price = base
    for _ in range(count):
        price += rng.randint(-40, 40) * tick
        if price <= 1000:
            price = base
        bid = price
        values.append((bid, bid + spread))
    stop_ticks = rng.choice([20, 50, 100, 200, 400])
    spec = StrategySpec(
        instrument=instrument,
        timeframe="M1",
        signal=Signal(operator="momentum", lookback=2, threshold="1"),
        stop_ticks=stop_ticks,
        max_hold_seconds=rng.choice([3600, 43200, 86400, 86400]),
        direction=rng.choice(["both", "both", "long", "short"]),
    )
    start = 1735689600 * 10**9
    quotes = make_quotes(instrument, values, step, start, profile.price_scale)
    signals = []
    for _ in range(rng.randint(1, 3)):
        idx = rng.randint(0, max(0, count - 2))
        side = rng.choice(["BUY", "SELL"])
        # available_at strictly before a quote timestamp so it becomes eligible
        signals.append({"available_at": start + idx * step, "side": side})
    signals.sort(key=lambda s: s["available_at"])

    # Optionally inject a finite eligible book so orders fill partially.
    partial = None
    fill_model = None
    if rng.random() < 0.35:
        if rng.random() < 0.5:
            limited_side = rng.choice(["BUY", "SELL"])
            partial = {"order_type": "MARKET", "side": limited_side, "divisor": 2}
            fill_model = FiniteEligibleBook(
                profile, OrderType.MARKET, OrderSide.BUY if limited_side == "BUY" else OrderSide.SELL
            )
        else:
            partial = {"order_type": "STOP_MARKET", "side": None, "divisor": 2}
            fill_model = FiniteEligibleBook(profile, OrderType.STOP_MARKET)
    return profile, spec, quotes, signals, partial, fill_model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=40)
    parser.add_argument("--seed", type=int, default=20261112)
    parser.add_argument("--instrument", default="EURUSD")
    args = parser.parse_args()

    if not BINARY.exists():
        print(f"rust binary missing: {BINARY}", file=sys.stderr)
        return 2

    rng = random.Random(args.seed)
    passed = 0
    failures = []
    for case in range(args.cases):
        instrument = args.instrument if args.instrument != "all" else rng.choice(INSTRUMENTS)
        profile, spec, quotes, signals, partial, fill_model = generate_case(rng, instrument)
        scale = profile.price_scale
        conservative = True
        try:
            py_raw = replay(quotes, profile, spec, signals, conservative, fill_model=fill_model)
        except Exception as exc:  # reference rejected the stream
            print(f"case {case}: python rejected: {exc}")
            continue
        py = normalize_python(py_raw, scale)
        request = build_request(profile, spec, quotes, signals, conservative, partial)
        try:
            rs = run_rust(request)
        except Exception as exc:
            failures.append({"case": case, "instrument": instrument, "error": str(exc)})
            continue
        mismatches = []
        compare(py, rs, mismatches)
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
