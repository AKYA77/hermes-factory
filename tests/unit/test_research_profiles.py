"""Research assumptions remain distinct from broker facts."""

from decimal import Decimal

import pytest

from factory.instruments.research_profiles import generic_fx_profile


@pytest.mark.parametrize("symbol,pip", [("EURUSD", ".0001"), ("USDJPY", ".01")])
def test_generic_units_are_explicit_and_do_not_infer_pips_from_precision(symbol, pip):
    profile = generic_fx_profile(symbol, 1_000_000, ".000001")
    assert profile.pip_size == Decimal(pip)
    assert profile.tick_size == Decimal(".000001")
    assert profile.contract_multiplier == profile.min_volume == profile.max_volume == 1
    assert profile.margin_rate == 1 and not profile.synthetic
    assert "GENERIC_RESEARCH_NOT_BROKER" in profile.source


def test_gold_requires_independent_units_and_cost_equivalent():
    with pytest.raises(ValueError, match="UNKNOWN_SPEC"):
        generic_fx_profile("XAUUSD", 1_000_000, ".001")
