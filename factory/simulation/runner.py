"""Bounded quote replay with engine-managed brackets and one open position."""

from decimal import Decimal as D, ROUND_FLOOR, ROUND_CEILING
from fractions import Fraction
from itertools import islice

from factory.simulation.streaming import QuoteSpool, BoundedRecords
from factory.contracts import InstrumentSpec, serialize
from factory.monetary import decimal_amount, VERSION as MONEY_VERSION
from factory.diagnostics import summarize_path
from factory.simulation.reconciliation import reconcile

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.accounting.margin_models import StandardMarginModel
from nautilus_trader.common.config import LoggingConfig
from nautilus_trader.model.currencies import Currency, USD
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import AccountType, OmsType, OrderSide, TimeInForce, PriceType
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue, ClientOrderId
from nautilus_trader.model.instruments import CurrencyPair
from nautilus_trader.model.objects import Money, Price, Quantity
from nautilus_trader.trading.strategy import Strategy

from factory.simulation.nautilus import AdverseFillModel
from factory.simulation.ledger import Fill, TradeLedger, EXECUTION_VERSION
from factory.simulation.pricing import effective_quotes, eligible_price, size_position
from factory.simulation.conversion import VERSION as FX_VERSION, quote_to_usd, native_rate_reference


def make_instrument(p, *, conversion_context=False):
    precision = max(0, -p.tick_size.normalize().as_tuple().exponent)
    native_step = p.volume_step * p.contract_multiplier
    size_precision = max(0, -native_step.normalize().as_tuple().exponent)
    if size_precision > 16:
        raise ValueError("UNREPRESENTABLE_NATIVE_SIZE_INCREMENT")
    native_min = (p.min_volume / p.volume_step).to_integral_value(
        rounding=ROUND_CEILING
    ) * native_step
    native_max = (p.max_volume / p.volume_step).to_integral_value(
        rounding=ROUND_FLOOR
    ) * native_step
    if native_min > native_max:
        raise ValueError("NO_LEGAL_NATIVE_VOLUME")
    return CurrencyPair(
        instrument_id=InstrumentId.from_str(
            f"{p.instrument}{'-FX' if conversion_context else ''}.SIM"
        ),
        raw_symbol=Symbol(p.instrument + ("-FX" if conversion_context else "")),
        base_currency=Currency.from_str(p.base_currency),
        quote_currency=Currency.from_str(p.quote_currency),
        price_precision=precision,
        size_precision=size_precision,
        price_increment=Price(p.tick_size, precision),
        size_increment=Quantity(native_step, size_precision),
        min_quantity=Quantity(native_min, size_precision),
        max_quantity=Quantity(native_max, size_precision),
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
        self.instrument, self.profile, self.spec = instrument, profile, spec
        self.signals = iter(signals)
        self.next_signal = next(self.signals, None)
        self.conservative = conservative
        self.entry_tif = TimeInForce.IOC
        self.stop_tif = TimeInForce.IOC
        self.market_exit_tif = TimeInForce.IOC
        self.fills, self.trades, self.skips, self.rejections = (BoundedRecords() for _ in range(4))
        self.current = None
        self.order_ledgers = {}
        self.completed = set()
        self.equity = D("20")
        self.account_cash_exact = Fraction(20)
        self.last_ts = None
        self.quote_count = 0
        self.in_quote = False
        self.deadlines = {}
        self.expired = set()
        self.safety_pending = set()
        self.empty_completed = set()
        self.cleanup_in_progress = set()
        self.conversion_context_id = None

    def on_start(self):
        self.subscribe_quote_ticks(self.instrument.id)

    def _cancel_related(self, ledger):
        marker = id(ledger)
        if marker in self.cleanup_in_progress:
            return
        self.cleanup_in_progress.add(marker)
        try:
            for order_id in list(ledger.orders):
                order = self.cache.order(ClientOrderId(order_id))
                if order is not None and not order.is_closed:
                    self.cancel_order(order)
        finally:
            self.cleanup_in_progress.remove(marker)

    def _settle(self, ledger):
        if ledger.closed:
            self._cancel_related(ledger)
            marker = id(ledger)
            if marker not in self.completed:
                self.completed.add(marker)
                ledger.metadata["equity_after"] = str(self.equity)
                self.trades.append(ledger)
            if all(o["terminal"] for o in ledger.orders.values()):
                if self.current is ledger:
                    self.current = None
        elif ledger.entry_terminal and not ledger.entered:
            if id(ledger) not in self.empty_completed:
                self.empty_completed.add(id(ledger))
                self.skips.append(
                    {
                        "ts": self.clock.timestamp_ns(),
                        "status": "SKIPPED_UNFILLED_ENTRY",
                        "signal": ledger.metadata["signal"],
                        "order_states": ledger.snapshot()["order_states"],
                    }
                )
            self._cancel_related(ledger)
            if all(o["terminal"] for o in ledger.orders.values()):
                if self.current is ledger:
                    self.current = None

    def _terminal(self, event, status):
        order_id = str(event.client_order_id)
        ledger = self.order_ledgers.get(order_id)
        if ledger is None:
            raise ValueError("UNKNOWN_TERMINAL_ORDER")
        ledger.terminal(order_id, status)
        if (
            ledger.orders[order_id]["role"] in ("STOP_LOSS", "TAKE_PROFIT")
            and ledger.quantity
            and id(ledger) not in self.expired
            and status != "FILLED"
        ):
            if "PROTECTION_LOST" not in ledger.metadata["flags"]:
                ledger.metadata["flags"].append("PROTECTION_LOST")
            self.safety_pending.add(id(ledger))
            self._cancel_related(ledger)
        self._settle(ledger)

    def on_order_cancel_rejected(self, event):
        order_id = str(event.client_order_id)
        ledger = self.order_ledgers.get(order_id)
        if ledger is None:
            raise ValueError("UNKNOWN_CANCEL_ORDER")
        ledger.events.append(
            {"order_id": order_id, "status": "CANCEL_REJECTED", "reason": str(event.reason)}
        )
        if not ledger.orders[order_id]["terminal"] and ledger.quantity:
            self.safety_pending.add(id(ledger))
            if "ORDER_CANCEL_REJECTED" not in ledger.metadata["flags"]:
                ledger.metadata["flags"].append("ORDER_CANCEL_REJECTED")

    def on_order_canceled(self, event):
        self._terminal(event, "CANCELED")

    def on_order_expired(self, event):
        self._terminal(event, "EXPIRED")

    def on_order_rejected(self, event):
        self.rejections.append(str(event))
        self._terminal(event, "REJECTED")

    def on_order_denied(self, event):
        self.rejections.append(str(event))
        self._terminal(event, "DENIED")

    def on_order_filled(self, event):
        order_id = str(event.client_order_id)
        ledger = self.order_ledgers.get(order_id)
        if ledger is None:
            raise ValueError("UNKNOWN_FILL_ORDER")
        side = "BUY" if event.order_side == OrderSide.BUY else "SELL"
        conversion, conversion_ts, conversion_source = D(1), None, "USD_IDENTITY"
        conversion_bid = conversion_ask = None
        if self.profile.quote_currency != "USD":
            quote = self.cache.quote_tick(self.conversion_context_id)
            if quote is None or quote.ts_event != event.ts_event:
                raise ValueError("MISSING_DATED_CONVERSION_QUOTE")
            conversion_bid, conversion_ask = (
                quote.bid_price.as_decimal(),
                quote.ask_price.as_decimal(),
            )
            conversion = quote_to_usd(self.profile, conversion_bid, conversion_ask, side)
            conversion_ts, conversion_source = int(quote.ts_event), str(quote.instrument_id)
            native_rate = self.cache.get_xrate(
                Venue("SIM"),
                self.instrument.quote_currency,
                USD,
                PriceType.BID if side == "SELL" else PriceType.ASK,
            )
            if native_rate != native_rate_reference(
                self.profile, conversion_bid, conversion_ask, side
            ):
                raise ValueError("NATIVE_DATED_CONVERSION_MISMATCH")
        size = event.last_qty.as_decimal()
        fill = Fill(
            order_id=order_id,
            trade_id=str(event.trade_id),
            ts=int(event.ts_event),
            side=side,
            size=size,
            price=event.last_px.as_decimal(),
            # The fee model comes from the instrument profile, not from the venue
            # event: an unconfigured commission is zero and means no fee model.
            commission=self.profile.commission_per_unit * size,
            quote_index=max(0, self.quote_count - 1 if self.in_quote else self.quote_count),
            quote_to_account=conversion,
            conversion_ts=conversion_ts,
            conversion_source=conversion_source,
            conversion_bid=conversion_bid,
            conversion_ask=conversion_ask,
        )
        was_empty = not ledger.entered
        prior = len(ledger.fills)
        ledger.apply(fill)
        if len(ledger.fills) == prior:
            return
        self.account_cash_exact += ledger.last_account_delta_exact
        self.equity = decimal_amount(self.account_cash_exact)
        self.fills.append({**fill.json(), "role": ledger.orders[order_id]["role"]})
        if was_empty and ledger.entered:
            name = "deadline-" + order_id
            self.deadlines[name] = ledger
            self.clock.set_time_alert_ns(
                name,
                fill.ts + self.spec.max_hold_seconds * 10**9,
                callback=self._deadline,
                allow_past=False,
            )
        order = self.cache.order(event.client_order_id)
        if order is not None and order.is_closed:
            ledger.terminal(order_id, "FILLED")
        # An exiting trade must not retain an unfilled opening remainder.
        if ledger.orders[order_id]["role"] != "ENTRY":
            for entry_id, state in ledger.orders.items():
                if state["role"] == "ENTRY" and not state["terminal"]:
                    entry_order = self.cache.order(ClientOrderId(entry_id))
                    if entry_order is not None and not entry_order.is_closed:
                        self.cancel_order(entry_order)
        self._settle(ledger)

    def _deadline(self, event):
        ledger = self.deadlines.pop(event.name)
        if not ledger.closed and ledger.quantity:
            self.expired.add(id(ledger))
            # Cancel protection at the deadline; submit no market fill against
            # a stale book. Only a subsequent actual quote can execute expiry.
            self._cancel_related(ledger)

    def _time_exit(self, ledger, now, reason="TIMEOUT"):
        if any(
            o["role"] in ("TIMEOUT", "SAFETY_CLOSE") and not o["terminal"]
            for o in ledger.orders.values()
        ):
            return
        entry_ts = ledger.aggregate(True)["ts"]
        flag = (
            "TIMEOUT"
            if now == entry_ts + self.spec.max_hold_seconds * 10**9
            else "DELAYED_TIMEOUT_QUOTE"
        )
        if reason == "SAFETY_CLOSE":
            flag = "SAFETY_CLOSE"
        if flag not in ledger.metadata["flags"]:
            ledger.metadata["flags"].append(flag)
        order = self.order_factory.market(
            self.instrument.id,
            OrderSide.SELL if ledger.metadata["side"] == "BUY" else OrderSide.BUY,
            self.instrument.make_qty(ledger.quantity),
            reduce_only=True,
            time_in_force=self.market_exit_tif,
        )
        ledger.register(str(order.client_order_id), reason)
        self.order_ledgers[str(order.client_order_id)] = ledger
        self.submit_order(order)

    def on_quote_tick(self, tick):
        self.quote_count += 1
        self.in_quote = True
        try:
            self._on_quote(tick)
        finally:
            self.in_quote = False

    def _on_quote(self, tick):
        now = int(tick.ts_event)
        self.last_ts = now
        if self.current and self.current.quantity:
            deadline = self.current.aggregate(True)["ts"] + self.spec.max_hold_seconds * 10**9
            if now >= deadline:
                self.expired.add(id(self.current))
                self._cancel_related(self.current)
                self._time_exit(self.current, now)
        if self.current and self.current.quantity and id(self.current) in self.safety_pending:
            self._time_exit(self.current, now, reason="SAFETY_CLOSE")
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
            if stop <= 0 or target <= 0:
                self.skips.append(
                    {
                        "ts": now,
                        "status": "SKIPPED_PRICE_LEVEL",
                        "reason": "nonpositive stop/target for supported currency instruments",
                    }
                )
                continue
            # A stop already crossed at submission is infeasible, not a valid
            # bracket: it can close the parent while siblings are still activating.
            liquidation = (
                tick.bid_price.as_decimal() if side == "BUY" else tick.ask_price.as_decimal()
            )
            if (liquidation - stop) * sign < self.profile.min_stop_ticks * self.profile.tick_size:
                self.skips.append(
                    {
                        "ts": now,
                        "status": "SKIPPED_STOP_LEVEL",
                        "reason": "stop violates current executable-side minimum distance",
                    }
                )
                continue
            # Project risk/margin at the currently dated closing-side rate. A
            # future gap or FX change can exceed intended loss and remains visible.
            risk_conversion = quote_to_usd(
                self.profile,
                tick.bid_price.as_decimal(),
                tick.ask_price.as_decimal(),
                "SELL" if side == "BUY" else "BUY",
            )
            sizing = size_position(
                self.equity, entry, stop, self.profile, risk_conversion, self.conservative
            )
            if sizing["status"] != "ELIGIBLE":
                self.skips.append({"ts": now, **{k: str(v) for k, v in sizing.items()}})
                continue
            metadata = {
                "signal": signal,
                "side": side,
                "intent_entry": str(entry),
                "stop": str(stop),
                "target": str(target),
                "intended_stop_distance": str(distance),
                "risk": str(sizing["risk"]),
                "risk_exact": sizing["risk_exact"],
                "modeled_stop_fill": str(
                    stop - sign * (2 * self.profile.pip_size if self.conservative else 0)
                ),
                "risk_budget": str(sizing["risk_budget"]),
                "projected_margin": str(sizing["margin"]),
                "projected_margin_exact": sizing["margin_exact"],
                "equity_before": str(self.equity),
                "risk_conversion_rate": str(risk_conversion),
                "risk_conversion_ts": now,
                "quote_currency": self.profile.quote_currency,
                "requested_profile_volume": str(sizing["size"]),
                "contract_multiplier": str(self.profile.contract_multiplier),
                "execution_quantity_unit": "base_currency_units",
                "flags": [],
            }
            native_size = sizing["size"] * self.profile.contract_multiplier
            self.current = TradeLedger(metadata, native_size)
            bracket = self.order_factory.bracket(
                self.instrument.id,
                OrderSide.BUY if side == "BUY" else OrderSide.SELL,
                self.instrument.make_qty(native_size),
                time_in_force=self.entry_tif,
                sl_time_in_force=self.stop_tif,
                sl_trigger_price=self.instrument.make_price(stop),
                tp_price=self.instrument.make_price(target),
                tp_post_only=False,
            )
            for order, role in zip(bracket.orders, ("ENTRY", "STOP_LOSS", "TAKE_PROFIT")):
                self.current.register(str(order.client_order_id), role)
                self.order_ledgers[str(order.client_order_id)] = self.current
            self.submit_order_list(bracket)


def replay(
    quotes,
    profile,
    spec,
    signals,
    conservative,
    *,
    fill_model=None,
    batch_rows=8192,
    inline_paths=True,
    dataset_hash=None,
    spool_directory=None,
    _materialized_reference=False,
    _legacy_gtc_reference=False,
):
    """Stream into Nautilus and reconstruct paths from bounded disk ranges.

    inline_paths is for small fixture/inspection callers. Production stores exact
    canonical source references plus sufficient statistics, not tick JSON. The
    materialized reference switch exists only for equivalence tests/benchmarks.
    """
    # Profile fingerprints canonicalize Decimal representations. Use that same
    # representation for native precision, sizing and forensic strings.
    profile = InstrumentSpec.model_validate_json(serialize(profile))
    if profile.instrument != spec.instrument:
        raise ValueError("instrument identity mismatch")
    if not 1 <= batch_rows <= 65536:
        raise ValueError("invalid replay batch size")
    if not inline_paths and (
        not dataset_hash
        or len(dataset_hash) != 64
        or any(c not in "0123456789abcdef" for c in dataset_hash)
    ):
        raise ValueError("canonical dataset identity required for path references")
    with QuoteSpool(quotes, profile, directory=spool_directory) as spool:
        return _replay_spool(
            spool,
            profile,
            spec,
            signals,
            conservative,
            fill_model=fill_model,
            batch_rows=batch_rows,
            inline_paths=inline_paths,
            dataset_hash=dataset_hash,
            materialized_reference=_materialized_reference,
            legacy_gtc_reference=_legacy_gtc_reference,
        )


def _replay_spool(
    spool,
    profile,
    spec,
    signals,
    conservative,
    *,
    fill_model,
    batch_rows,
    inline_paths,
    dataset_hash,
    materialized_reference,
    legacy_gtc_reference,
):
    instrument = make_instrument(profile)
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(bypass_logging=True)))
    fill = fill_model if fill_model is not None else AdverseFillModel(profile, conservative)
    engine.add_venue(
        Venue("SIM"),
        OmsType.NETTING,
        AccountType.MARGIN,
        [Money(20, USD)],
        base_currency=USD,
        default_leverage=D(1000),
        fill_model=fill,
        margin_model=StandardMarginModel(),
        use_message_queue=False,
        reject_stop_orders=False,
    )
    engine.add_instrument(instrument)
    conversion_instrument = None
    if profile.quote_currency != "USD":
        conversion_instrument = make_instrument(profile, conversion_context=True)
        # Register last so the cache's pair table uses this fresh context feed.
        # It receives no orders, signals or tradable strategy subscriptions.
        engine.add_instrument(conversion_instrument)
    strategy = ReplayStrategy(instrument, profile, spec, signals, conservative)
    strategy.conversion_context_id = conversion_instrument.id if conversion_instrument else None
    if legacy_gtc_reference:
        strategy.entry_tif = strategy.stop_tif = strategy.market_exit_tif = TimeInForce.GTC
    engine.add_strategy(strategy)

    def tick_from_row(row):
        return make_quote_tick(row, spool.scale, instrument, profile, conservative)

    def native_events(row):
        tick = tick_from_row(row)
        if conversion_instrument is not None:
            # Same source quote/time, stable context-before-execution ordering.
            # Never pre-populate the cache from a future batched source record.
            yield QuoteTick(
                conversion_instrument.id,
                tick.bid_price,
                tick.ask_price,
                tick.bid_size,
                tick.ask_size,
                tick.ts_event,
                tick.ts_init,
            )
        yield tick

    def batches():
        source = iter(spool.rows())
        while rows := list(islice(source, batch_rows)):
            yield [tick for row in rows for tick in native_events(row)]

    try:
        if materialized_reference:
            # Deliberately bounded by tests/benchmark caller, never worker input.
            engine.add_data([tick for row in spool.rows() for tick in native_events(row)])
            engine.run()
        else:
            engine.add_data_iterator("canonical-quotes", batches())
            # One native event loop, including ties across chunk boundaries.
            engine.run(start=spool.first_ns, end=spool.last_ns, streaming=True)
            engine.end()
        if strategy.quote_count != spool.count:
            raise ValueError("INCOMPLETE_NATIVE_REPLAY")
        if engine.iteration != spool.count * (2 if conversion_instrument else 1):
            raise ValueError("INCOMPLETE_NATIVE_CONTEXT_REPLAY")
        open_trade = (
            strategy.current.snapshot()
            if strategy.current and not strategy.current.closed
            else None
        )
        if open_trade:
            open_trade["flags"] = list(open_trade["flags"]) + ["NO_EXECUTABLE_EXIT_QUOTE"]
        trades = [ledger.snapshot() for ledger in strategy.trades]
        for trade in trades + ([open_trade] if open_trade else []):
            if not trade["entry_fill"]:
                trade["flags"].append("ENTRY_NOT_FILLED")
                trade["path"] = []
                continue
            start = trade["entry_fill"]["quote_index"]
            end = trade["exit_fill"]["quote_index"] if trade["exit_fill"] else spool.count - 1
            path = iter_trade_path(spool, trade, tick_from_row)
            if inline_paths:
                trade["path"] = list(islice(path, 100001))
                if len(trade["path"]) > 100000:
                    raise ValueError("INLINE_PATH_LIMIT: use canonical path references")
            else:
                trade["path_summary"] = summarize_path(
                    path, trade["side"], trade["entry_fill"]["price"]
                )
                trade["path_ref"] = {
                    "version": "canonical-view-path/v1" if spool.view else "canonical-path/v1",
                    "dataset_hash": dataset_hash,
                    "first_source_record_order": spool.row(start)[3],
                    "last_source_record_order": spool.row(end)[3],
                    "start_quote_index": start,
                    "end_quote_index": end,
                    "basis": "ordered execution fills",
                    "quote_policy": "effective-quotes/v1",
                }
                if spool.view:
                    trade["path_ref"].update(
                        first_sequence=spool.row(start)[4],
                        last_sequence=spool.row(end)[4],
                        first_source_ref=spool.source_ref(spool.row(start)),
                        last_source_ref=spool.source_ref(spool.row(end)),
                    )
            if (
                trade["exit_fill"]
                and trade["exit_fill"]["ts"]
                > trade["entry_fill"]["ts"] + spec.max_hold_seconds * 10**9
            ):
                if "DELAYED_TIMEOUT_QUOTE" not in trade["flags"]:
                    trade["flags"].append("DELAYED_TIMEOUT_QUOTE")
        integrity_errors = []
        if strategy.rejections:
            integrity_errors.append(
                {
                    "reason": "ENGINE_ORDER_REJECTION",
                    "count": len(strategy.rejections),
                    "sample": [r[:1000] for r in strategy.rejections[:3]],
                }
            )
        for f in strategy.fills:
            if D(f["commission"]) != 0:
                integrity_errors.append(
                    {"trade_id": f["trade_id"], "reason": "COMMISSION_SCENARIO_MISMATCH"}
                )
            row = spool.row(f["quote_index"])
            tick = tick_from_row(row)
            f["source_record_order"] = row[3]
            if spool.view:
                f["source_ref"] = spool.source_ref(row)
            f["effective_bid"] = str(tick.bid_price)
            f["effective_ask"] = str(tick.ask_price)
            expected_conversion = quote_to_usd(
                profile, tick.bid_price.as_decimal(), tick.ask_price.as_decimal(), f["side"]
            )
            if D(f["quote_to_account"]) != expected_conversion or (
                profile.quote_currency != "USD"
                and (
                    f["conversion_ts"] != f["ts"]
                    or D(f["conversion_bid"]) != tick.bid_price.as_decimal()
                    or D(f["conversion_ask"]) != tick.ask_price.as_decimal()
                )
            ):
                integrity_errors.append(
                    {"trade_id": f["trade_id"], "reason": "DATED_CONVERSION_SOURCE_MISMATCH"}
                )
            if f["role"] == "TAKE_PROFIT":
                ledger = strategy.order_ledgers[f["order_id"]]
                limit = D(ledger.metadata["target"])
                if (f["side"] == "SELL" and D(f["price"]) < limit) or (
                    f["side"] == "BUY" and D(f["price"]) > limit
                ):
                    integrity_errors.append(
                        {"trade_id": f["trade_id"], "reason": "LIMIT_PRICE_VIOLATION"}
                    )
            else:
                book_price = (
                    tick.ask_price.as_decimal()
                    if f["side"] == "BUY"
                    else tick.bid_price.as_decimal()
                )
                expected = eligible_price(book_price, f["side"], "MARKET", profile, conservative)
                f["expected_price"] = str(expected)
                f["actual_adverse_adjustment"] = str(
                    (D(f["price"]) - book_price) * (1 if f["side"] == "BUY" else -1)
                )
                if D(f["price"]) != expected:
                    integrity_errors.append(
                        {
                            "trade_id": f["trade_id"],
                            "reason": "ELIGIBLE_FILL_PRICE_MISMATCH",
                            "expected": str(expected),
                            "actual": f["price"],
                        }
                    )
        reconciliation = reconcile(engine, strategy, instrument)
        integrity_errors.extend(reconciliation["issues"])
        result = {
            "reconciliation": reconciliation,
            "engine": "nautilus_trader",
            "trades": trades,
            "fills": strategy.fills,
            "skips": strategy.skips,
            "open_trade": open_trade,
            "accounting_version": EXECUTION_VERSION,
            "integrity_errors": integrity_errors,
            "entry_time_in_force": strategy.entry_tif.name,
            "stop_time_in_force": strategy.stop_tif.name,
            "market_exit_time_in_force": strategy.market_exit_tif.name,
            "legacy_gtc_reference": bool(legacy_gtc_reference),
            "conversion_policy": FX_VERSION,
            "account_sum_policy": MONEY_VERSION,
            "conversion_context": str(conversion_instrument.id) if conversion_instrument else None,
            "execution_quantity_unit": "base_currency_units",
            "profile_contract_multiplier": str(profile.contract_multiplier),
            "margin_model": "standard_fixed_profile_rate",
            "rejections": strategy.rejections,
            "fill_trace": fill.trace,
            "ending_equity": str(strategy.equity),
            "quote_count": spool.count,
            "native_quote_event_count": engine.iteration,
            "synthetic": profile.synthetic,
            "commission_assumption": 0,
            "liquidity_assumption": (
                "test-injected fill book; no observed source volume"
                if fill_model is not None
                else "modeled unlimited L1 quote depth; source volume not supplied"
            ),
            "unmodeled": ["swap", "financing", "broker-specific execution"],
        }
        from factory.reporting.equity import equity_summary

        result["equity"] = equity_summary(spool.rows(), spool.scale, profile, result, conservative)
        return result
    finally:
        engine.dispose()


def iter_trade_path(spool, trade, tick_from_row, index_offset=0):
    start = trade["entry_fill"]["quote_index"] - index_offset
    end = (
        trade["exit_fill"]["quote_index"] - index_offset if trade["exit_fill"] else spool.count - 1
    )
    fills = trade["execution_fills"]
    pos = 0
    quantity = cost = D(0)
    basis = D(trade["entry_fill"]["price"])
    for i, row in enumerate(spool.rows(start, end + 1), start + index_offset):
        t = tick_from_row(row)
        last_point_index = None

        def point(fill=None, phase="quote"):
            return {
                "ts": int(t.ts_event),
                "quote_index": i,
                "source_record_order": row[3],
                "bid": str(t.bid_price),
                "ask": str(t.ask_price),
                "entry_reference": str(basis),
                "fill_trade_id": fill["trade_id"] if fill else None,
                "phase": phase,
                **({"source_ref": spool.source_ref(row)} if spool.view else {}),
            }

        while pos < len(fills) and fills[pos]["quote_index"] <= i:
            f = fills[pos]
            q, price = D(f["size"]), D(f["price"])
            if f["role"] == "ENTRY":
                cost += q * price
                quantity += q
                basis = cost / quantity
                yield point(f, "after_entry_fill")
            else:
                yield point(f, "before_exit_fill")
                cost -= basis * q
                quantity -= q
            last_point_index = i
            pos += 1
        if quantity and last_point_index != i:
            yield point()


def make_quote_tick(row, scale, instrument, profile, conservative):
    ts, bid_int, ask_int = row[:3]
    bid, ask = effective_quotes(D(bid_int) / scale, D(ask_int) / scale, profile, conservative)
    return QuoteTick(
        instrument.id,
        instrument.make_price(bid),
        instrument.make_price(ask),
        instrument.make_qty(1000000),
        instrument.make_qty(1000000),
        ts,
        ts,
    )


def reconstruct_path(catalog, trade, profile, conservative):
    """Re-read immutable canonical offsets; never interpolate a forensic path.

    This returns a generator. Callers paginate/export it rather than serializing
    a complete multi-million-quote path into a metadata record.
    """
    ref = trade["path_ref"]
    if (
        ref["version"] not in ("canonical-path/v1", "canonical-view-path/v1")
        or ref["quote_policy"] != "effective-quotes/v1"
    ):
        raise ValueError("unsupported path reference policy")
    manifest = catalog.verify(ref["dataset_hash"])
    if manifest["instrument"] != profile.instrument:
        raise ValueError("path instrument mismatch")
    view = ref["version"] == "canonical-view-path/v1"
    first, last = (
        (ref["first_sequence"], ref["last_sequence"])
        if view
        else (ref["first_source_record_order"], ref["last_source_record_order"])
    )
    from itertools import takewhile

    def position(q):
        return q.sequence if view else q.original_record_order

    source = takewhile(
        lambda q: position(q) <= last,
        catalog.read(ref["dataset_hash"], start_ns=trade["entry_fill"]["ts"]),
    )
    source = (q for q in source if position(q) >= first)
    with QuoteSpool(source, profile) as spool:
        if spool.count != ref["end_quote_index"] - ref["start_quote_index"] + 1:
            raise ValueError("forensic source range mismatch")
        instrument = make_instrument(profile)
        yield from iter_trade_path(
            spool,
            trade,
            lambda row: make_quote_tick(row, spool.scale, instrument, profile, conservative),
            index_offset=ref["start_quote_index"],
        )
