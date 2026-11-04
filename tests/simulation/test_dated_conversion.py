"""Native all-instrument monetary software goldens, never broker/market evidence."""

from dataclasses import replace
from decimal import Decimal as D
from fractions import Fraction

import pytest
from factory.contracts import SYMBOLS, Signal, StrategySpec
from factory.data import Quote
from factory.instruments import synthetic_profile
from factory.simulation.conversion import quote_to_usd
from factory.simulation.runner import replay, make_instrument


def inputs(symbol, side, outcome="stop"):
    profile = synthetic_profile(symbol)
    spec = StrategySpec(
        instrument=symbol,
        timeframe="M1",
        signal=Signal(operator="momentum", lookback=2, threshold="1"),
        stop_ticks=100,
    )
    base = 150 if symbol == "USDJPY" else 2000 if symbol == "XAUUSD" else D("1.1")
    center = int(D(base) * profile.price_scale)
    shift = (
        (-200 if side == "BUY" else 300) if outcome == "stop" else (400 if side == "BUY" else -400)
    )
    data = [
        Quote(
            symbol,
            1735689600 * 10**9 + index * 10**9,
            bid,
            bid + 10,
            profile.price_scale,
            "synthetic",
            "monetary-fixture",
            index,
        )
        for index, bid in enumerate([center, center, center + shift, center + shift])
    ]
    signal = [{"available_at": data[0].event_ts_utc_ns, "side": side}]
    return profile, spec, data, signal


@pytest.mark.parametrize("symbol", sorted(SYMBOLS))
@pytest.mark.parametrize("side", ["BUY", "SELL"])
@pytest.mark.parametrize("outcome", ["stop", "target"])
def test_native_all_instruments_cost_risk_currency_and_order_identity(symbol, side, outcome):
    profile, spec, data, signal = inputs(symbol, side, outcome)
    result = replay(iter(data), profile, spec, signal, True, batch_rows=1)
    assert not result["integrity_errors"] and not result["rejections"]
    assert result["reconciliation"]["native_reference_status"] == "VERIFIED"
    assert result["quote_count"] == len(data)
    assert result["native_quote_event_count"] == len(data) * (
        1 if profile.quote_currency == "USD" else 2
    )
    assert len(result["trades"]) == 1
    trade = result["trades"][0]
    assert trade["exit_reason"] == ("STOP_LOSS" if outcome == "stop" else "TAKE_PROFIT")
    entry, stop, target = (D(trade[k]) for k in ("intent_entry", "stop", "target"))
    assert abs(target - entry) == 3 * abs(stop - entry)
    assert D(trade["risk"]) <= D(trade["risk_budget"]) == 2
    assert D(trade["modeled_stop_risk_for_filled_quantity"]) == D(trade["risk"])
    for fill in result["fills"]:
        bid, ask = D(fill["effective_bid"]), D(fill["effective_ask"])
        assert ask - bid >= 2 * profile.pip_size
        assert D(fill["quote_to_account"]) == quote_to_usd(profile, bid, ask, fill["side"])
        if profile.quote_currency != "USD":
            assert fill["conversion_ts"] == fill["ts"]
            assert fill["conversion_source"] == f"{symbol}-FX.SIM"
        if fill["role"] != "TAKE_PROFIT":
            assert D(fill["actual_adverse_adjustment"]) == 2 * profile.pip_size
    assert D(result["equity"]["ending_marked_equity"]) == D(result["ending_equity"])
    assert not result["open_trade"]


@pytest.mark.parametrize("symbol", ["USDJPY", "USDCHF", "USDCAD"])
@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_conversion_context_is_current_across_ties_and_batch_boundaries(symbol, side):
    profile, spec, data, signal = inputs(symbol, side)
    data[2] = replace(data[2], event_ts_utc_ns=data[1].event_ts_utc_ns)
    expected = replay(data, profile, spec, signal, True, _materialized_reference=True)
    assert not expected["integrity_errors"]
    for batch in (1, 2, 3, 8192):
        actual = replay(iter(data), profile, spec, signal, True, batch_rows=batch)
        assert actual == expected
    stop = expected["fills"][-1]
    assert stop["quote_index"] == 2 and stop["conversion_bid"] == stop["effective_bid"]


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_gold_lots_and_base_units_have_identical_economic_execution(side):
    profile, spec, data, signal = inputs("XAUUSD", side)
    lots = profile.model_copy(
        update={
            "version": "synthetic-lots/v1",
            "contract_multiplier": D(100),
            "volume_step": D(".00001"),
            "min_volume": D(".00001"),
            "max_volume": D(1000),
            "source": "synthetic 100-unit lot golden; not broker metadata",
        }
    )
    left, right = make_instrument(profile), make_instrument(lots)
    assert left.size_increment == right.size_increment and left.min_quantity == right.min_quantity
    a, b = (replay(data, p, spec, signal, True) for p in (profile, lots))
    assert not a["integrity_errors"] and not b["integrity_errors"]
    assert a["fills"] == b["fills"] and a["ending_equity"] == b["ending_equity"]
    assert a["equity"] == b["equity"]
    first, second = a["trades"][0], b["trades"][0]
    assert D(first["requested_profile_volume"]) == D(second["requested_profile_volume"]) * 100
    assert D(first["requested_quantity"]) == D(second["requested_quantity"])
    assert D(first["risk"]) == D(second["risk"])


def test_gold_third_decimal_source_grid_is_preserved_in_native_fills():
    profile, spec, data, signal = inputs("XAUUSD", "BUY")
    profile = profile.model_copy(
        update={
            "tick_size": D(".001"),
            "pip_size": D(".01"),
            "price_scale": 1000,
            "margin_rate": D(".0001"),
            "source": "synthetic 0.001 price grid; not broker metadata",
        }
    )
    values = [(2000001, 2000011), (2000001, 2000011), (1999801, 1999811)]
    data = [
        replace(data[min(n, 3)], bid_int=bid, ask_int=ask, price_scale=1000)
        for n, (bid, ask) in enumerate(values)
    ]
    result = replay(data, profile, spec, signal, True)
    assert not result["integrity_errors"] and len(result["trades"]) == 1
    assert D(result["fills"][0]["price"]) == D("2000.036")
    assert D(result["fills"][1]["price"]) == D("1999.776")


def test_open_jpy_inventory_uses_current_quote_and_reports_gap_insolvency():
    profile, spec, data, signal = inputs("USDJPY", "BUY")
    # A small favorable movement leaves inventory open; no fabricated close.
    data = data[:2] + [replace(data[2], bid_int=150050, ask_int=150060)]
    result = replay(data, profile, spec, signal, True)
    trade = result["open_trade"]
    assert trade and not result["trades"] and not result["integrity_errors"]
    fill = result["fills"][0]
    # Effective current bid/ask 150.045/150.065, entry 150.035.
    expected = Fraction(20) + Fraction(
        D(trade["open_quantity"]) * (D("150.045") - D(fill["price"]))
    ) * Fraction(D(1) / D("150.065"))
    assert D(result["equity"]["ending_marked_equity"]) == D(expected.numerator) / D(
        expected.denominator
    )
    assert result["ending_equity"] == "20"
    _, _, gap, _ = inputs("USDJPY", "BUY")
    gap[2] = replace(gap[2], bid_int=120000, ask_int=120010)
    gap[3] = replace(gap[3], bid_int=120000, ask_int=120010)
    insolvent = replay(gap, profile, spec, signal, True)
    assert not insolvent["integrity_errors"]
    assert D(insolvent["ending_equity"]) < 0 and insolvent["equity"]["insolvent_at_any_observation"]


def test_native_volume_bounds_are_rounded_to_legal_grid_without_rounding_up_risk():
    profile = synthetic_profile("EURUSD").model_copy(
        update={"min_volume": D(".015"), "max_volume": D("1.005"), "volume_step": D(".01")}
    )
    instrument = make_instrument(profile)
    assert instrument.min_quantity.as_decimal() == D(".02")
    assert instrument.max_quantity.as_decimal() == D("1")
    with pytest.raises(ValueError, match="NO_LEGAL_NATIVE_VOLUME"):
        make_instrument(profile.model_copy(update={"max_volume": D(".019")}))


@pytest.mark.parametrize("side", ["BUY", "SELL"])
@pytest.mark.parametrize("endpoint", ["low", "high"])
def test_v3_gold_search_bounds_with_distinct_declared_pip_are_native_eligible(side, endpoint):
    from factory.exploration.persistent import SearchProtocol
    from factory.contracts import Window

    profile, _, data, signal = inputs("XAUUSD", side)
    profile = profile.model_copy(
        update={
            "tick_size": D(".001"),
            "pip_size": D(".1"),
            "price_scale": 1000,
            "margin_rate": D(".0001"),
            "source": "synthetic declared .1 pip / .001 tick search test; not broker metadata",
        }
    )
    p = SearchProtocol(
        dataset_hash="a" * 64,
        profile=profile,
        family="momentum",
        timeframe="M1",
        window=Window(
            start_ns=data[0].event_ts_utc_ns, end_ns=data[-1].event_ts_utc_ns + 1, role="train_only"
        ),
        code_revision="synthetic native stop search golden",
        seed=42,
    )
    spec = p.strategy(
        {
            "lookback": 2,
            "threshold_tenths": 10,
            "stop_ticks": getattr(p.stop_distribution(), endpoint),
            "confirmation": "none",
        }
    )
    # A deliberately large adverse jump exercises stop fills for both endpoints.
    values = [2_000_001, 2_000_001, 1_996_001 if side == "BUY" else 2_004_001]
    data = [
        replace(data[i], bid_int=bid, ask_int=bid + 10, price_scale=1000)
        for i, bid in enumerate(values)
    ]
    result = replay(data, profile, spec, signal, True)
    assert not result["integrity_errors"] and not result["rejections"]
    assert len(result["trades"]) == 1 and not result["open_trade"]
    trade = result["trades"][0]
    assert trade["exit_reason"] == "STOP_LOSS"
    entry, stop, target = (D(trade[k]) for k in ("intent_entry", "stop", "target"))
    assert abs(entry - stop) == spec.stop_ticks * profile.tick_size
    assert abs(target - entry) == 3 * abs(stop - entry)
    assert D(trade["risk"]) <= D(trade["risk_budget"]) == 2
