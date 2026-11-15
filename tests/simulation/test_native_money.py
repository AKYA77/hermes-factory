"""Independent native Money/Position goldens; synthetic software evidence only."""

from decimal import Decimal as D
from random import Random

import pytest
from nautilus_trader.accounting.accounts.margin import MarginAccount
from nautilus_trader.common.component import TestClock
from nautilus_trader.common.factories import OrderFactory
from nautilus_trader.model.currencies import USD, JPY, CHF
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import TraderId, StrategyId, PositionId, TradeId
from nautilus_trader.model.objects import Money
from nautilus_trader.model.position import Position
from nautilus_trader.test_kit.stubs.events import TestEventStubs

from factory.simulation.native_money import fixed_float, money_round, position_reference
from factory.simulation.runner import make_instrument
from factory.instruments import synthetic_profile
from factory.contracts import SYMBOLS


@pytest.mark.parametrize("currency", [USD, JPY, CHF])
def test_constructor_rounding_matches_native_at_signed_boundaries(currency):
    rng = Random(918)
    # All signed tenth-of-minor-unit values over a continuous range, plus
    # reproducible random amounts. Native Money is the external oracle here.
    values = [D(i).scaleb(-currency.precision - 1) for i in range(-10000, 10001)]
    values += [D(str(rng.uniform(-10000, 10000))) for _ in range(2000)]
    for value in values:
        assert money_round(value, currency.precision) == Money(value, currency).as_decimal()
    assert money_round(D("1.005"), 2) == D("1.00")
    assert money_round(D("-.005"), 2) == D("-.01")


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_actual_native_position_and_account_use_different_rounding_paths(profile, side):
    instrument = make_instrument(profile)
    factory = OrderFactory(TraderId("TEST-001"), StrategyId("MONEY-001"), TestClock())
    account = MarginAccount(TestEventStubs.margin_account_state())
    records = []
    position = None
    account_pnl = D(0)
    # Profit .03 followed by loss -.015 is a signed rounding-order boundary.
    levels = [
        (".09", "1"),
        (".06", "1.5" if side == "BUY" else ".5"),
        (".03", ".5" if side == "BUY" else "1.5"),
    ]
    for index, (quantity, price) in enumerate(levels):
        fill_side = side if index == 0 else ("SELL" if side == "BUY" else "BUY")
        order = factory.market(
            instrument.id,
            OrderSide.BUY if fill_side == "BUY" else OrderSide.SELL,
            instrument.make_qty(quantity),
        )
        fill = TestEventStubs.order_filled(
            order,
            instrument,
            position_id=PositionId("P-1"),
            trade_id=TradeId(str(index)),
            last_qty=instrument.make_qty(quantity),
            last_px=instrument.make_price(price),
            commission=Money(0, USD),
            ts_event=index,
        )
        # Native account calculates its delta from the pre-fill position.
        account_pnl += sum(
            (p.as_decimal() for p in account.calculate_pnls(instrument, fill, position)), D(0)
        )
        if position is None:
            position = Position(instrument, fill)
        else:
            position.apply(fill)
        records.append({"side": fill_side, "size": quantity, "price": price, "commission": "0"})
    reference = position_reference(
        records, currency_precision=USD.precision, size_precision=instrument.size_precision
    )
    assert position.is_closed
    assert D(reference["account_quote_pnl"]) == account_pnl == D(".01")
    assert D(reference["position_quote_pnl"]) == position.realized_pnl.as_decimal() == D(".02")
    assert reference["open_quantity"] == "0.0"


def test_reference_refuses_unsupported_policies_and_nonfinite_values():
    for value in ("NaN", "Infinity", "-Infinity"):
        with pytest.raises(ValueError):
            money_round(value, 2)
    with pytest.raises(ValueError, match="UNREPRESENTABLE"):
        fixed_float("0.000000000000000001")
    with pytest.raises(ValueError, match="COMMISSION"):
        position_reference([{"commission": ".1"}], currency_precision=2, size_precision=3)


@pytest.mark.parametrize("symbol", sorted(SYMBOLS))
@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_native_quote_currency_reference_all_instruments_partial_entry_and_exit(symbol, side):
    """Quote-P&L only; this deliberately does not claim USD FX conversion."""
    instrument = make_instrument(synthetic_profile(symbol))
    factory = OrderFactory(TraderId("TEST-001"), StrategyId("MONEY-001"), TestClock())
    account = MarginAccount(TestEventStubs.margin_account_state())
    rng = Random(6123)
    for lifetime in range(20):
        position = None
        account_pnl = D(0)
        records = []
        # Two entries with a different basis, then three exits with both signs.
        sizes = [D("1.001"), D("2.002"), D(".501"), D("1.001"), D("1.501")]
        for index, size in enumerate(sizes):
            price = instrument.make_price(
                D(rng.randrange(75000, 150001)) * instrument.price_increment.as_decimal()
            )
            fill_side = side if index < 2 else ("SELL" if side == "BUY" else "BUY")
            order = factory.market(
                instrument.id,
                OrderSide.BUY if fill_side == "BUY" else OrderSide.SELL,
                instrument.make_qty(size),
            )
            fill = TestEventStubs.order_filled(
                order,
                instrument,
                position_id=PositionId(f"P-{lifetime}"),
                trade_id=TradeId(f"{lifetime}-{index}"),
                last_px=price,
                commission=Money(0, instrument.quote_currency),
                ts_event=index,
            )
            account_pnl += sum(
                (p.as_decimal() for p in account.calculate_pnls(instrument, fill, position)), D(0)
            )
            if position is None:
                position = Position(instrument, fill)
            else:
                position.apply(fill)
            records.append(
                {"side": fill_side, "size": str(size), "price": str(price), "commission": "0"}
            )
        reference = position_reference(
            records,
            currency_precision=instrument.quote_currency.precision,
            size_precision=instrument.size_precision,
        )
        assert position.is_closed
        assert D(reference["position_quote_pnl"]) == position.realized_pnl.as_decimal()
        assert D(reference["account_quote_pnl"]) == account_pnl
