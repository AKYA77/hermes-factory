"""Constructed arithmetic references, not research outcomes."""

from decimal import Decimal as D, localcontext
from fractions import Fraction
import pytest

from factory.monetary import decimal_amount, receipt, trade_pnl
from factory.reporting import metrics
from factory.validation.statistics import outcome_summary


def test_receipts_preserve_sums_across_trade_and_report_boundaries():
    trade = {"pnl": str(decimal_amount(Fraction(1, 3))), "pnl_exact": receipt(Fraction(1, 3))}
    assert metrics([trade] * 3)["ending_balance"] == "21"
    report = outcome_summary([trade] * 3)
    assert report["gross_profit"] == "1" and report["ending_balance"] == "21"
    # Context-independent presentation; exact receipt remains unchanged.
    with localcontext() as context:
        context.prec = 6
        assert decimal_amount(Fraction(1, 3)) == D(".3333333333333333333333333333")
        assert metrics([trade] * 3)["ending_balance"] == "21"


def test_legacy_decimal_trades_remain_readable_and_forged_receipts_fail():
    assert trade_pnl({"pnl": ".125"}) == Fraction(1, 8)
    with pytest.raises(ValueError, match="MISMATCH"):
        trade_pnl({"pnl": "2", "pnl_exact": receipt(Fraction(1, 3))})
    with pytest.raises(ValueError, match="INVALID"):
        trade_pnl({"pnl": "0", "pnl_exact": {"version": "unknown", "denominator": "1"}})


def test_repeating_conversion_cannot_round_size_up_over_risk_budget():
    from factory.instruments import synthetic_profile
    from factory.simulation.pricing import size_position

    profile = synthetic_profile("USDJPY")
    rate = D(".001666666666666666666666666667")
    result = size_position(D(20), D(1), D(".9"), profile, rate)
    # Previously rounded loss_per_unit admitted 10000, which exceeds $2 by an
    # arbitrarily small positive amount. The legal lower grid point is required.
    assert result["size"] == D("9999.999")
    risk = Fraction(result["size"]) * Fraction(D(".12")) * Fraction(rate)
    assert risk <= 2
    assert Fraction(D(10000)) * Fraction(D(".12")) * Fraction(rate) > 2
    assert (
        Fraction(int(result["risk_exact"]["numerator"]), int(result["risk_exact"]["denominator"]))
        == risk
    )
