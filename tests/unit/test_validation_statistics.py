"""Independent arithmetic and deliberately labeled decision fixtures."""

from datetime import datetime, timezone
from decimal import Decimal as D

from factory.validation.statistics import outcome_summary, holm, annual_windows, stability_summary
from factory.validation.protocol import decide
from types import SimpleNamespace
from factory.validation.protocol import ValidationCriteria


def test_holm_stepdown_and_empty_trade_semantics():
    assert holm([0.01, 0.04, 0.03], 0.05) == [True, False, False]
    assert holm([0.001, 0.002, 0.003], 0.05) == [True, True, True]
    summary = outcome_summary([{"pnl": "2"}, {"pnl": "-1"}, {"pnl": "0"}, {"pnl": "3"}])
    assert summary["profit_factor"] == "5" and summary["expectancy"] == "1"
    assert summary["completed_trades"] == 4 and summary["breakeven"] == 1
    assert outcome_summary([])["profit_factor_status"] == "NO_TRADES"
    assert outcome_summary([])["one_sided_win_fraction_pvalue"] is None
    assert stability_summary(
        {"ending_balance": "30"}, [{"ending_balance": "25", "completed_trades": 5}]
    )["isolated_peak"]


def test_annual_windows_do_not_round_nanoseconds_across_year():
    boundary = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()) * 10**9
    years = list(annual_windows(boundary - 1, boundary + 1))
    assert [y["year"] for y in years] == [2025, 2026]
    assert years[0]["end_ns"] == boundary == years[1]["start_ns"]
    assert all(y["partial"] for y in years)


def test_controlled_positive_negative_and_small_sample_decisions(tmp_path):
    p = SimpleNamespace(
        criteria=ValidationCriteria(
            min_oos_closed_trades=50,
            min_full_folds=2,
            min_annual_closed_trades=50,
            min_wilson_lower=0.5,
            min_net_profit=0,
            max_losing_streak=5,
            familywise_alpha=0.05,
            min_neighborhoods_with_trades=1,
            require_research_targets=False,
        )
    )
    # Explicitly constructed reference outcomes test the decision function only.
    # They are never inserted into experiments, reports or a market leaderboard.
    good = outcome_summary([{"pnl": "1"} for _ in range(80)])
    bad = outcome_summary([{"pnl": "-1"} for _ in range(80)])
    folds = [
        {"fold": {"partial": False}, "result": {"windows": [{"replay": {"trades": []}}]}}
        for _ in range(2)
    ]
    annual = [{"result": {"windows": [{"metrics": {"completed_trades": 80}}]}}]
    assert decide(p, folds, [good, good], good, annual, [good])["status"] == "VALIDATED_REFERENCE"
    assert decide(p, folds, [good, bad], good, annual, [good])["status"] == "OOS_FAILED"
    small = outcome_summary([{"pnl": "1"} for _ in range(4)])
    assert (
        decide(p, folds, [small, good], good, annual, [good])["status"] == "INSUFFICIENT_EVIDENCE"
    )
    assert good["ending_balance"] == str(D(100))
