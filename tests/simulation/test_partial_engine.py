from decimal import Decimal as D
from nautilus_trader.model.data import BookOrder
from nautilus_trader.model.enums import OrderType, OrderSide
from factory.simulation.nautilus import AdverseFillModel
from factory.simulation.runner import replay
from conftest import quotes


class PartialBook(AdverseFillModel):
    """Synthetic limited-liquidity fixture using the supported fill-book API."""

    def __init__(self, profile, order_type):
        super().__init__(profile, True)
        self.limited_type = order_type

    def get_orderbook_for_fill_simulation(self, instrument, order, best_bid, best_ask):
        book = super().get_orderbook_for_fill_simulation(instrument, order, best_bid, best_ask)
        if order.order_type == self.limited_type and (
            order.order_type != OrderType.MARKET or order.side == OrderSide.BUY
        ):
            q = instrument.make_qty(order.quantity.as_decimal() / 2)
            bid = instrument.make_price(
                best_bid.as_decimal()
                - (2 * self.profile.pip_size if order.order_type == OrderType.MARKET else 0)
            )
            ask = instrument.make_price(
                best_ask.as_decimal()
                + (2 * self.profile.pip_size if order.order_type == OrderType.MARKET else 0)
            )
            book.update(BookOrder(OrderSide.BUY, bid, q, 1), 0, 0)
            book.update(BookOrder(OrderSide.SELL, ask, q, 2), 0, 0)
        return book


def test_native_partial_entry_uses_actual_quantity(profile, spec):
    q = quotes([(110000, 110010), (110000, 110010), (110400, 110410), (110500, 110510)])
    result = replay(
        q,
        profile,
        spec,
        [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}],
        True,
        fill_model=PartialBook(profile, OrderType.MARKET),
    )
    assert not result["rejections"], result
    assert len(result["trades"]) == 1, result
    trade = result["trades"][0]
    assert D(trade["entered_quantity"]) == D(trade["requested_quantity"])
    assert trade["entered_quantity"] == trade["exited_quantity"]
    assert trade["exit_reason"] == "TAKE_PROFIT"
    assert len(trade["entry_fills"]) == 2
    assert trade["entry_fill"]["fill_count"] == 2
    assert all(v["terminal"] for v in trade["order_states"].values())


def test_native_partial_target_does_not_close_early(profile, spec):
    q = quotes(
        [(110000, 110010), (110000, 110010), (110400, 110410), (110500, 110510), (110600, 110610)]
    )
    result = replay(
        q,
        profile,
        spec,
        [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}],
        True,
        fill_model=PartialBook(profile, OrderType.LIMIT),
    )
    assert not result["rejections"], result
    assert len(result["trades"]) == 1, result
    t = result["trades"][0]
    assert len(t["exit_fills"]) == 2
    assert t["exit_fill"]["ts"] == q[2].event_ts_utc_ns
    assert t["entered_quantity"] == t["exited_quantity"]
    pnl = sum(
        (D(f["size"]) * (D(f["price"]) - D(t["entry_fill"]["price"])) for f in t["exit_fills"]),
        D(0),
    )
    assert D(t["pnl"]) == pnl
    assert t["exit_reason"] == "TAKE_PROFIT"


def test_native_cancel_racing_with_entry_keeps_all_fills_accounted(profile, spec, monkeypatch):
    import factory.simulation.runner as module

    original = module.ReplayStrategy

    class CancelRemainder(original):
        def on_order_filled(self, event):
            super().on_order_filled(event)
            ledger = self.order_ledgers[str(event.client_order_id)]
            if (
                ledger.orders[str(event.client_order_id)]["role"] == "ENTRY"
                and ledger.entered < ledger.requested
            ):
                order = self.cache.order(event.client_order_id)
                if not order.is_closed:
                    self.cancel_order(order)

    monkeypatch.setattr(module, "ReplayStrategy", CancelRemainder)
    q = quotes([(110000, 110010), (110000, 110010), (110400, 110410), (110500, 110510)])
    result = module.replay(
        q,
        profile,
        spec,
        [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}],
        True,
        fill_model=PartialBook(profile, OrderType.MARKET),
    )
    assert not result["rejections"], result
    assert len(result["trades"]) == 1, result
    t = result["trades"][0]
    assert D(t["entered_quantity"]) == D(t["requested_quantity"])
    assert len(t["entry_fills"]) == 2
    assert t["entered_quantity"] == t["exited_quantity"]
    entry_id = t["entry_fill"]["order_id"]
    assert t["order_states"][entry_id]["terminal"] == "FILLED"
    assert all(o["terminal"] for o in t["order_states"].values())


def test_native_ioc_partial_entry_cancels_remainder(profile, spec, monkeypatch):
    import factory.simulation.runner as module
    from nautilus_trader.model.enums import TimeInForce

    original = module.ReplayStrategy

    class IOCFixture(original):
        def __init__(self, *args):
            super().__init__(*args)
            self.entry_tif = TimeInForce.IOC

    monkeypatch.setattr(module, "ReplayStrategy", IOCFixture)
    q = quotes([(110000, 110010), (110000, 110010), (110400, 110410), (110500, 110510)])
    result = module.replay(
        q,
        profile,
        spec,
        [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}],
        True,
        fill_model=PartialBook(profile, OrderType.MARKET),
    )
    assert not result["rejections"], result
    assert len(result["trades"]) == 1, result
    t = result["trades"][0]
    assert D(t["entered_quantity"]) < D(t["requested_quantity"])
    assert t["entered_quantity"] == t["exited_quantity"]
    assert t["order_states"][t["entry_fill"]["order_id"]]["terminal"] == "CANCELED"
    assert result["entry_time_in_force"] == "IOC"


def test_l1_remainder_extra_tick_is_reported_not_hidden(profile, spec):
    q = quotes([(110000, 110010), (110000, 110010), (110400, 110410)])
    result = replay(
        q,
        profile,
        spec,
        [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}],
        True,
        fill_model=PartialBook(profile, OrderType.MARKET),
    )
    # Nautilus L1 GTC replenishes exhausted market liquidity one tick away.
    # Account for the actual fill, but never certify it as exact 2-pip pricing.
    assert len(result["trades"]) == 1
    assert result["integrity_errors"]
    assert result["integrity_errors"][0]["reason"] == "ELIGIBLE_FILL_PRICE_MISMATCH"


def test_canceled_protection_uses_safety_exit_not_stop_tag(profile, spec, monkeypatch):
    import factory.simulation.runner as module
    from factory.diagnostics import diagnose_trade
    from nautilus_trader.model.identifiers import ClientOrderId

    original = module.ReplayStrategy

    class LoseProtection(original):
        def on_quote_tick(self, tick):
            super().on_quote_tick(tick)
            if (
                self.current
                and self.current.quantity
                and not getattr(self, "requested_cancel", False)
            ):
                self.requested_cancel = True
                for oid, state in self.current.orders.items():
                    if state["role"] == "STOP_LOSS":
                        self.cancel_order(self.cache.order(ClientOrderId(oid)))
                        break

    monkeypatch.setattr(module, "ReplayStrategy", LoseProtection)
    q = quotes([(110000, 110010), (110000, 110010), (109980, 109990), (109980, 109990)])
    result = module.replay(
        q, profile, spec, [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}], True
    )
    assert len(result["trades"]) == 1, result
    t = result["trades"][0]
    assert t["exit_reason"] == "SAFETY_CLOSE"
    assert D(t["pnl"]) < 0
    d = diagnose_trade(t, profile.tick_size)
    assert "FAST_STOP" not in d["tags"] and "FAVORABLE_THEN_STOP" not in d["tags"]
    assert "PROTECTION_LOST" in d["tags"]


def test_ioc_partial_filled_risk_uses_actual_quantity(profile, spec, monkeypatch):
    import factory.simulation.runner as module
    from nautilus_trader.model.enums import TimeInForce

    original = module.ReplayStrategy

    class IOCFixture(original):
        def __init__(self, *args):
            super().__init__(*args)
            self.entry_tif = TimeInForce.IOC

    monkeypatch.setattr(module, "ReplayStrategy", IOCFixture)
    q = quotes([(110000, 110010), (110000, 110010), (110400, 110410)])
    result = module.replay(
        q,
        profile,
        spec,
        [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}],
        True,
        fill_model=PartialBook(profile, OrderType.MARKET),
    )
    t = result["trades"][0]
    assert not result["integrity_errors"]
    assert D(t["modeled_stop_risk_for_filled_quantity"]) == D(t["risk"]) / 2
    assert D(t["realized_net_r"]) == D(t["pnl"]) / D(t["modeled_stop_risk_for_filled_quantity"])


def test_partial_entry_path_does_not_use_later_fill_basis(profile, spec):
    q = quotes([(110000, 110010), (110000, 110010), (110400, 110410)])
    result = replay(
        q,
        profile,
        spec,
        [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}],
        True,
        fill_model=PartialBook(profile, OrderType.MARKET),
    )
    t = result["trades"][0]
    entries = [p for p in t["path"] if p["phase"] == "after_entry_fill"]
    assert len(entries) == 2
    assert entries[0]["entry_reference"] == t["entry_fills"][0]["price"]
    assert D(entries[1]["entry_reference"]) == D(t["entry_fill"]["price"])
    assert entries[0]["source_record_order"] == entries[1]["source_record_order"] == 1
