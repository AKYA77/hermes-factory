"""Bounded quote replay with engine-managed brackets and one open position."""

from decimal import Decimal as D

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.common.config import LoggingConfig
from nautilus_trader.model.currencies import Currency, USD
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import AccountType, OmsType, OrderSide
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import CurrencyPair
from nautilus_trader.model.objects import Money, Price, Quantity
from nautilus_trader.trading.strategy import Strategy

from factory.simulation.nautilus import AdverseFillModel
from factory.simulation.pricing import effective_quotes, eligible_price, size_position


def make_instrument(p):
    if p.contract_multiplier != 1:
        raise ValueError("UNSUPPORTED_CONTRACT_MULTIPLIER: version gate required")
    precision = max(0, -p.tick_size.as_tuple().exponent)
    size_precision = max(0, -p.volume_step.as_tuple().exponent)
    return CurrencyPair(
        instrument_id=InstrumentId.from_str(f"{p.instrument}.SIM"),
        raw_symbol=Symbol(p.instrument),
        base_currency=Currency.from_str(p.base_currency),
        quote_currency=Currency.from_str(p.quote_currency),
        price_precision=precision,
        size_precision=size_precision,
        price_increment=Price(p.tick_size, precision),
        size_increment=Quantity(p.volume_step, size_precision),
        min_quantity=Quantity(p.min_volume, size_precision),
        max_quantity=Quantity(p.max_volume, size_precision),
        margin_init=p.margin_rate,
        margin_maint=p.margin_rate,
        maker_fee=D(0),
        taker_fee=D(0),
        ts_event=0,
        ts_init=0,
    )


class ReplayStrategy(Strategy):
    def __init__(self, instrument, profile, spec, signals, conservative):
        super().__init__()
        self.instrument = instrument
        self.profile = profile
        self.spec = spec
        self.signals = iter(signals)
        self.next_signal = next(self.signals, None)
        self.conservative = conservative
        self.fills = []
        self.trades = []
        self.skips = []
        self.current = None
        self.equity = D("20")
        self.last_ts = None
        self.rejections = []

    def on_start(self):
        self.subscribe_quote_ticks(self.instrument.id)

    def on_order_rejected(self, event):
        self.rejections.append(str(event))

    def on_order_filled(self, event):
        fill = {
            "order_id": str(event.client_order_id),
            "ts": int(event.ts_event),
            "price": str(event.last_px),
            "size": str(event.last_qty),
            "side": str(event.order_side),
            "commission": str(event.commission),
        }
        self.fills.append(fill)
        if self.current is None:
            return
        if self.current["entry_fill"] is None:
            self.current["entry_fill"] = fill
            return
        self.current["exit_fill"] = fill
        c = self.current
        signed = 1 if c["side"] == "BUY" else -1
        pnl = (D(fill["price"]) - D(c["entry_fill"]["price"])) * signed * D(fill["size"])
        self.equity += pnl
        c["pnl"] = str(pnl)
        c["equity_after"] = str(self.equity)
        self.trades.append(c)
        self.current = None

    def on_quote_tick(self, tick):
        now = int(tick.ts_event)
        self.last_ts = now
        if self.current and self.current["entry_fill"]:
            c = self.current
            c["path"].append({"ts": now, "bid": str(tick.bid_price), "ask": str(tick.ask_price)})
            deadline = c["entry_fill"]["ts"] + self.spec.max_hold_seconds * 10**9
            if now >= deadline and not c.get("timeout_submitted"):
                c["flags"].append("TIMEOUT" if now == deadline else "DELAYED_TIMEOUT_QUOTE")
                c["timeout_submitted"] = True
                self.cancel_all_orders(self.instrument.id)
                self.close_all_positions(self.instrument.id)
        while self.next_signal and self.next_signal["available_at"] < now:
            signal = self.next_signal
            self.next_signal = next(self.signals, None)
            if self.current or not self.portfolio.is_flat(self.instrument.id):
                self.skips.append({"ts": now, "status": "SKIPPED_OVERLAP"})
                continue
            side = signal["side"]
            if self.spec.direction != "both" and self.spec.direction != (
                "long" if side == "BUY" else "short"
            ):
                continue
            price = tick.ask_price.as_decimal() if side == "BUY" else tick.bid_price.as_decimal()
            entry = eligible_price(price, side, "MARKET", self.profile, self.conservative)
            distance = self.spec.stop_ticks * self.profile.tick_size
            sign = 1 if side == "BUY" else -1
            stop = entry - sign * distance
            target = entry + sign * distance * 3
            # USD quote acceptance profile. Other currency conversions require dated cross quotes.
            if self.profile.quote_currency != "USD":
                self.skips.append({"ts": now, "status": "UNKNOWN_CONVERSION"})
                continue
            sizing = size_position(self.equity, entry, stop, self.profile, D(1), self.conservative)
            if sizing["status"] != "ELIGIBLE":
                self.skips.append({"ts": now, **{k: str(v) for k, v in sizing.items()}})
                continue
            self.current = {
                "signal": signal,
                "side": side,
                "entry_fill": None,
                "stop": str(stop),
                "target": str(target),
                "risk": str(sizing["risk"]),
                "equity_before": str(self.equity),
                "path": [],
                "flags": [],
            }
            bracket = self.order_factory.bracket(
                self.instrument.id,
                OrderSide.BUY if side == "BUY" else OrderSide.SELL,
                self.instrument.make_qty(sizing["size"]),
                sl_trigger_price=self.instrument.make_price(stop),
                tp_price=self.instrument.make_price(target),
                tp_post_only=False,
            )
            self.submit_order_list(bracket)


def replay(quotes, profile, spec, signals, conservative):
    quotes = list(quotes)
    if not quotes:
        raise ValueError("no quotes")
    from factory.data import quality

    if quality(quotes):
        raise ValueError("invalid quote stream")
    if any(
        q.instrument_id != profile.instrument or q.price_scale != profile.price_scale
        for q in quotes
    ):
        raise ValueError("quote units mismatch")
    instrument = make_instrument(profile)
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(bypass_logging=True)))
    fill = AdverseFillModel(profile, conservative)
    engine.add_venue(
        Venue("SIM"),
        OmsType.NETTING,
        AccountType.MARGIN,
        [Money(20, USD)],
        base_currency=USD,
        default_leverage=D(1000),
        fill_model=fill,
        use_message_queue=False,
        reject_stop_orders=False,
    )
    engine.add_instrument(instrument)
    strategy = ReplayStrategy(instrument, profile, spec, signals, conservative)
    engine.add_strategy(strategy)
    ticks = []
    for q in quotes:
        bid, ask = effective_quotes(
            D(q.bid_int) / q.price_scale, D(q.ask_int) / q.price_scale, profile, conservative
        )
        ticks.append(
            QuoteTick(
                instrument.id,
                instrument.make_price(bid),
                instrument.make_price(ask),
                instrument.make_qty(1000000),
                instrument.make_qty(1000000),
                q.event_ts_utc_ns,
                q.event_ts_utc_ns,
            )
        )
    try:
        engine.add_data(ticks)
        engine.run()
        if strategy.current:
            strategy.current["flags"].append("NO_EXECUTABLE_EXIT_QUOTE")
        # The matching engine may fill before strategy quote callbacks. Reconstruct
        # the complete executable-side path from the exact stream fed to the engine.
        for trade in strategy.trades + ([strategy.current] if strategy.current else []):
            if not trade["entry_fill"]:
                trade["flags"].append("ENTRY_NOT_FILLED")
                continue
            start = trade["entry_fill"]["ts"]
            end = trade.get("exit_fill", {}).get("ts", ticks[-1].ts_event)
            trade["path"] = [
                {"ts": int(t.ts_event), "bid": str(t.bid_price), "ask": str(t.ask_price)}
                for t in ticks
                if start <= t.ts_event <= end
            ]
            if end > start + spec.max_hold_seconds * 10**9:
                trade["flags"].append("DELAYED_TIMEOUT_QUOTE")
        return {
            "engine": "nautilus_trader",
            "trades": strategy.trades,
            "fills": strategy.fills,
            "skips": strategy.skips,
            "open_trade": strategy.current,
            "rejections": strategy.rejections,
            "fill_trace": fill.trace,
            "ending_equity": str(strategy.equity),
            "quote_count": len(quotes),
            "synthetic": profile.synthetic,
            "commission_assumption": 0,
            "unmodeled": ["swap", "financing", "broker-specific execution"],
        }
    finally:
        engine.dispose()
