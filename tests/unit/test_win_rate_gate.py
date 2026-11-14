"""R07: the absolute post-cost win-rate qualification floor."""

from decimal import Decimal as D

import pytest

from factory.validation.protocol import ValidationCriteria, win_rate_gate


def _summary(wins, trades):
    return {"wins": wins, "completed_trades": trades}


def test_exactly_fifty_percent_passes():
    """The threshold is inclusive: exactly 50.00% qualifies."""
    assert win_rate_gate(_summary(25, 50), D("0.5")) is True
    assert win_rate_gate(_summary(1, 2), D("0.5")) is True


def test_just_below_fifty_percent_fails():
    assert win_rate_gate(_summary(49, 100), D("0.5")) is False
    assert win_rate_gate(_summary(0, 100), D("0.5")) is False


def test_a_candidate_above_the_floor_still_qualifies():
    assert win_rate_gate(_summary(51, 100), D("0.5")) is True


def test_unmeasured_win_rate_never_passes():
    """No closed trades, or no recorded wins, must not slip past the gate."""
    assert win_rate_gate({"wins": None, "completed_trades": 0}, D("0.5")) is False
    assert win_rate_gate({"wins": 0, "completed_trades": 0}, D("0.5")) is False
    assert win_rate_gate({}, D("0.5")) is False


def test_boundary_is_an_exact_rational_not_a_float_rounding():
    """A binary64 division could round 0.49999999999999994 up to 0.5; counts cannot."""
    # 1/3 is safely below the floor either way, so use a count pair whose true
    # fraction is just under one half by exactly one trade.
    assert win_rate_gate(_summary(499, 1000), D("0.5")) is False
    assert win_rate_gate(_summary(500, 1000), D("0.5")) is True


def test_malformed_or_insufficient_evidence_never_passes():
    """Missing, non-integer, negative or impossible counts must all fail closed."""
    assert win_rate_gate(None, D("0.5")) is False
    assert win_rate_gate([], D("0.5")) is False
    assert win_rate_gate({"wins": "25", "completed_trades": 50}, D("0.5")) is False
    assert win_rate_gate({"wins": 25.0, "completed_trades": 50}, D("0.5")) is False
    assert win_rate_gate({"wins": True, "completed_trades": 50}, D("0.5")) is False
    assert win_rate_gate({"wins": -1, "completed_trades": 50}, D("0.5")) is False
    assert win_rate_gate({"wins": 51, "completed_trades": 50}, D("0.5")) is False


def test_a_floor_below_the_absolute_minimum_is_refused():
    """Even a caller holding the helper cannot lower the floor below 50%."""
    import pytest

    with pytest.raises(ValueError, match="absolute 50%"):
        win_rate_gate(_summary(0, 100), D("0.499"))
    with pytest.raises(ValueError, match="absolute 50%"):
        win_rate_gate(_summary(0, 100), D("0.0"))


def test_criteria_default_and_bounds():
    criteria = ValidationCriteria(
        min_oos_closed_trades=50,
        min_full_folds=2,
        min_annual_closed_trades=50,
        min_wilson_lower=0.5,
        min_net_profit=D(0),
        max_losing_streak=5,
        familywise_alpha=0.05,
        min_neighborhoods_with_trades=1,
        require_research_targets=True,
    )
    assert criteria.min_win_rate == D("0.5")
    with pytest.raises(ValueError):
        ValidationCriteria(
            min_oos_closed_trades=50,
            min_full_folds=2,
            min_annual_closed_trades=50,
            min_wilson_lower=0.5,
            min_net_profit=D(0),
            max_losing_streak=5,
            familywise_alpha=0.05,
            min_neighborhoods_with_trades=1,
            require_research_targets=True,
            min_win_rate=D("1.5"),
        )
    # The absolute floor cannot be configured away, in either direction of abuse.
    for refused in (D("-0.1"), D("0"), D("0.499"), D("0.499999999999999999999")):
        with pytest.raises(ValueError):
            ValidationCriteria(
                min_oos_closed_trades=50,
                min_full_folds=2,
                min_annual_closed_trades=50,
                min_wilson_lower=0.5,
                min_net_profit=D(0),
                max_losing_streak=5,
                familywise_alpha=0.05,
                min_neighborhoods_with_trades=1,
                require_research_targets=True,
                min_win_rate=refused,
            )
    # Thresholds above 50% remain configurable.
    for allowed in (D("0.5"), D("0.7"), D("1")):
        criteria = ValidationCriteria(
            min_oos_closed_trades=50,
            min_full_folds=2,
            min_annual_closed_trades=50,
            min_wilson_lower=0.5,
            min_net_profit=D(0),
            max_losing_streak=5,
            familywise_alpha=0.05,
            min_neighborhoods_with_trades=1,
            require_research_targets=True,
            min_win_rate=allowed,
        )
        assert criteria.min_win_rate == allowed
