"""Versioned IOC policy avoids native L1 GTC market-remainder extrapolation."""

from decimal import Decimal as D
import pytest
from nautilus_trader.model.book import OrderBook
from nautilus_trader.model.data import BookOrder
from nautilus_trader.model.enums import BookType, OrderSide, OrderType
from factory.simulation.nautilus import AdverseFillModel
from factory.simulation.runner import replay
from conftest import quotes


class FiniteEligibleBook(AdverseFillModel):
    def __init__(self, profile, limited_type, entry_side):
        super().__init__(profile, True)
        self.limited_type, self.entry_side = limited_type, entry_side

    def get_orderbook_for_fill_simulation(self, instrument, order, best_bid, best_ask):
        if order.order_type != self.limited_type or (
            order.order_type == OrderType.MARKET and order.side != self.entry_side
        ):
            return super().get_orderbook_for_fill_simulation(instrument, order, best_bid, best_ask)
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
        return book


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_ioc_entry_records_partial_and_cancellation_without_extra_tick(profile, spec, side):
    data = quotes([(110000, 110010)] * 5)
    book = FiniteEligibleBook(
        profile, OrderType.MARKET, OrderSide.BUY if side == "BUY" else OrderSide.SELL
    )
    result = replay(
        data,
        profile,
        spec,
        [{"available_at": data[0].event_ts_utc_ns, "side": side}],
        True,
        fill_model=book,
    )
    assert not result["integrity_errors"] and not result["rejections"]
    assert (
        result["entry_time_in_force"]
        == result["stop_time_in_force"]
        == result["market_exit_time_in_force"]
        == "IOC"
    )
    trade = result["trades"][0]
    assert D(trade["entered_quantity"]) < D(trade["requested_quantity"])
    assert trade["entered_quantity"] == trade["exited_quantity"]
    assert trade["order_states"][trade["entry_fill"]["order_id"]]["terminal"] == "CANCELED"
    assert all(f["price"] == f["expected_price"] for f in result["fills"])
    assert (
        D(trade["target"]) - D(trade["intent_entry"])
        == (D(trade["intent_entry"]) - D(trade["stop"])) * 3
    )


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_ioc_stop_partial_retains_actual_stop_role_and_safely_closes_remainder(profile, spec, side):
    values = [(110000, 110010)] * 2 + (
        [(109800, 109810), (109700, 109710)]
        if side == "BUY"
        else [(110300, 110310), (110400, 110410)]
    )
    data = quotes(values)
    book = FiniteEligibleBook(
        profile, OrderType.STOP_MARKET, OrderSide.BUY if side == "BUY" else OrderSide.SELL
    )
    result = replay(
        data,
        profile,
        spec,
        [{"available_at": data[0].event_ts_utc_ns, "side": side}],
        True,
        fill_model=book,
    )
    assert not result["integrity_errors"] and not result["rejections"]
    trade = result["trades"][0]
    assert trade["exit_reason"] == "MIXED"
    assert set(trade["exit_reasons"]) == {"STOP_LOSS", "SAFETY_CLOSE"}
    assert len(trade["exit_fills"]) == 2
    assert trade["entered_quantity"] == trade["exited_quantity"]
    assert all(f["price"] == f["expected_price"] for f in result["fills"])
    assert not result["legacy_gtc_reference"]
