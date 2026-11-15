"""Independent arithmetic and deliberately labeled decision fixtures."""

from datetime import datetime, timezone
from decimal import Decimal as D

from factory.validation.statistics import outcome_summary, holm, annual_windows, stability_summary
from factory.validation.protocol import decide
from types import SimpleNamespace
from factory.validation.protocol import ValidationCriteria, ValidationEvidencePolicy
from factory.simulation.ledger import EXECUTION_VERSION
from factory.monetary import VERSION as MONEY_VERSION
from factory.validation.evidence import replay_quality
from factory.validation.protocol import qualify_forward, assess_neighbors


def constructed_replay(pnl):
    """Deliberately constructed decision inputs, never stored as experiment evidence."""
    trades = [{"pnl": str(value), "closed": True} for value in pnl]
    summary = outcome_summary(trades)
    count = max(1, len(trades) * 2)
    return {
        "engine": "nautilus_trader",
        "accounting_version": EXECUTION_VERSION,
        "account_sum_policy": MONEY_VERSION,
        "trades": trades,
        "fills": [{} for _ in range(len(trades) * 2)],
        "open_trade": None,
        "quote_count": count,
        "native_quote_event_count": count,
        "integrity_errors": [],
        "rejections": [],
        "reconciliation": {
            "native_reference_status": "VERIFIED",
            "issues": [],
            "native_fill_count": len(trades) * 2,
            "quote_currency": "USD",
        },
        "equity": {
            "status": "EXACT_USD_QUOTE_VALUATION",
            "quote_observations": count,
            "fill_observations": len(trades) * 2,
            "insolvent_at_any_observation": summary["insolvent"],
            "max_mark_to_market_drawdown": summary["balance_drawdown"],
            "ending_marked_equity": summary["ending_balance"],
        },
    }


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
        evidence_policy=ValidationEvidencePolicy(
            max_censored_fraction=0.1,
            max_marked_drawdown=".95",
            min_neighbor_closed_trades=50,
            min_neighbor_acceptable_fraction=0.5,
        ),
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
        ),
    )
    # Explicitly constructed reference outcomes test the decision function only.
    # They are never inserted into experiments, reports or a market leaderboard.
    good = outcome_summary([{"pnl": "1"} for _ in range(80)])
    bad = outcome_summary([{"pnl": "-1"} for _ in range(80)])

    def run(summaries):
        values = [[1] * s["wins"] + [-1] * s["losses"] for s in summaries]
        folds = [
            {"fold": {"partial": False}, "result": {"windows": [{"replay": constructed_replay(v)}]}}
            for v in values
        ]
        reference = constructed_replay([1] * 80)
        annual = [
            {"result": {"windows": [{"metrics": {"completed_trades": 80}, "replay": reference}]}}
        ]
        return decide(
            p,
            folds,
            summaries,
            good,
            annual,
            [good],
            holdout_replay=reference,
            pooled_replay=reference,
            neighborhood_replays=[reference],
        )

    assert run([good, good])["status"] == "VALIDATED_REFERENCE"
    assert run([good, bad])["status"] == "OOS_FAILED"
    small = outcome_summary([{"pnl": "1"} for _ in range(4)])
    assert run([small, good])["status"] == "INSUFFICIENT_EVIDENCE"
    assert good["ending_balance"] == str(D(100))


def test_win_rate_floor_gates_the_decision_and_forward_qualification():
    """R07: a verified post-cost win rate below the floor must never validate."""
    criteria = ValidationCriteria(
        min_oos_closed_trades=50,
        min_full_folds=2,
        min_annual_closed_trades=50,
        min_wilson_lower=0.5,
        min_net_profit=D(0),
        max_losing_streak=5,
        familywise_alpha=0.05,
        min_neighborhoods_with_trades=1,
        require_research_targets=False,
        min_win_rate=D("0.5"),
    )
    policy = ValidationEvidencePolicy(
        max_censored_fraction=0.1,
        max_marked_drawdown=".95",
        min_neighbor_closed_trades=50,
        min_neighbor_acceptable_fraction=0.5,
    )
    p = SimpleNamespace(criteria=criteria, evidence_policy=policy)
    reference = constructed_replay([1] * 80)
    losing = constructed_replay([-1] * 80)
    good = outcome_summary(reference["trades"])
    bad = outcome_summary(losing["trades"])

    def fold(replay):
        return {"fold": {"partial": False}, "result": {"windows": [{"replay": replay}]}}

    annual = [{"result": {"windows": [{"metrics": {"completed_trades": 80}, "replay": reference}]}}]

    def run(summaries, folds):
        return decide(
            p,
            folds,
            summaries,
            good,
            annual,
            [good],
            holdout_replay=reference,
            pooled_replay=reference,
            neighborhood_replays=[reference],
        )

    result = run([bad, good], [fold(losing), fold(reference)])
    assert result["status"] == "OOS_FAILED", result
    assert result["win_rate_gate_passed"] is False
    assert result["min_win_rate"] == str(D("0.5"))

    # A stricter floor still fails on the same evidence: 60% cannot be met by a
    # half-winning candidate, so raising the threshold is effective.
    strict = SimpleNamespace(
        criteria=p.criteria.model_copy(update={"min_win_rate": D("1")}),
        evidence_policy=policy,
    )
    raised = decide(
        strict,
        [fold(losing), fold(reference)],
        [bad, good],
        good,
        annual,
        [good],
        holdout_replay=reference,
        pooled_replay=reference,
        neighborhood_replays=[reference],
    )
    assert raised["win_rate_gate_passed"] is False
    assert raised["min_win_rate"] == str(D("1"))

    # The absolute floor cannot be configured away.
    import pytest

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
            require_research_targets=False,
            min_win_rate=D("0.49"),
        )

    # Forward qualification fails below the floor and passes at or above it.
    below = qualify_forward(p, [fold(losing), fold(losing)], [bad, bad])
    assert below["status"] == "OOS_FAILED", below
    assert below["win_rate_gate_passed"] is False
    passes = qualify_forward(p, [fold(reference), fold(reference)], [good, good])
    assert passes["status"] == "QUALIFIED_FOR_FINAL", passes
    assert passes["win_rate_gate_passed"] is True


def test_open_loss_censoring_and_failed_neighbors_block_qualification():
    # Constructed reference inputs exercise decision rules only, not the engine.
    criteria = ValidationCriteria(
        min_oos_closed_trades=50,
        min_full_folds=1,
        min_annual_closed_trades=50,
        min_wilson_lower=0.5,
        min_net_profit=0,
        max_losing_streak=5,
        familywise_alpha=0.05,
        min_neighborhoods_with_trades=1,
        require_research_targets=False,
    )
    policy = ValidationEvidencePolicy(
        max_censored_fraction=0.1,
        max_marked_drawdown=".95",
        min_neighbor_closed_trades=50,
        min_neighbor_acceptable_fraction=0.5,
    )
    p = SimpleNamespace(criteria=criteria, evidence_policy=policy)
    reference = constructed_replay([1] * 80)
    good = outcome_summary(reference["trades"])

    def fold(replay):
        return {"fold": {"partial": False}, "result": {"windows": [{"replay": replay}]}}

    assert qualify_forward(p, [fold(reference)], [good])["status"] == "QUALIFIED_FOR_FINAL"
    reference["open_trade"] = {"open_quantity": "1"}
    reference["fills"].append({})
    reference["reconciliation"]["native_fill_count"] += 1
    reference["equity"]["fill_observations"] += 1
    strict = policy.model_copy(update={"max_censored_fraction": 0.01})
    assert replay_quality(reference, strict)["status"] == "INSUFFICIENT_EVIDENCE"
    assert replay_quality(reference, policy)["status"] == "PASS"
    reference["equity"]["ending_marked_equity"] = "19"
    reference["equity"]["max_mark_to_market_drawdown"] = ".81"
    assert qualify_forward(p, [fold(reference)], [good])["status"] == "OOS_FAILED"
    assert assess_neighbors(p, [good], [reference])["status"] == "OOS_FAILED"
    small = constructed_replay([1] * 4)
    assert (
        assess_neighbors(p, [outcome_summary(small["trades"])], [small])["status"]
        == "INSUFFICIENT_EVIDENCE"
    )
