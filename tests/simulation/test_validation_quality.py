"""Actual native software paths and explicit corrupt-evidence rejection."""

from copy import deepcopy
from decimal import Decimal as D

import pytest
from nautilus_trader.model.book import OrderBook
from nautilus_trader.model.enums import BookType

from conftest import quotes
from factory.simulation.nautilus import AdverseFillModel
from factory.simulation.runner import replay
from factory.validation.evidence import replay_quality
from factory.validation.protocol import ValidationEvidencePolicy


def policy():
    return ValidationEvidencePolicy(
        max_censored_fraction=0.1,
        max_marked_drawdown=".99",
        min_neighbor_closed_trades=50,
        min_neighbor_acceptable_fraction=0.5,
    )


class NoLiquidityDuringGap(AdverseFillModel):
    def get_orderbook_for_fill_simulation(self, instrument, order, best_bid, best_ask):
        if best_bid.as_decimal() < 1:
            return OrderBook(instrument.id, BookType.L2_MBP)
        return super().get_orderbook_for_fill_simulation(instrument, order, best_bid, best_ask)


def test_native_profitable_final_balance_cannot_hide_marked_insolvency(profile, spec, monkeypatch):
    import factory.simulation.runner as module

    data = quotes([(110000, 110010), (110000, 110010), (90000, 90010), (110400, 110410)])

    class FaultedProtection(module.ReplayStrategy):
        """Fault injection only: lose protection and miss one safety-close callback."""

        def _on_quote(self, tick):
            super()._on_quote(tick)
            if self.quote_count == 2 and self.current:
                self._cancel_related(self.current)

        def _time_exit(self, ledger, now, reason="TIMEOUT"):
            if now == data[2].event_ts_utc_ns:
                return
            return super()._time_exit(ledger, now, reason)

    monkeypatch.setattr(module, "ReplayStrategy", FaultedProtection)
    result = replay(
        data,
        profile,
        spec,
        [{"available_at": data[0].event_ts_utc_ns, "side": "BUY"}],
        True,
    )
    assert not result["integrity_errors"] and not result["rejections"]
    assert len(result["trades"]) == 1 and D(result["ending_equity"]) > 20
    assert result["trades"][0]["exit_reason"] == "SAFETY_CLOSE"
    assert result["equity"]["insolvent_at_any_observation"] is True
    assert D(result["equity"]["minimum_marked_equity"]) < 0
    decision = replay_quality(result, policy())
    assert decision["status"] == "OOS_FAILED" and "MARKED_INSOLVENCY" in decision["reasons"]


def test_empty_custom_book_native_fallback_is_rejected_not_repriced(profile, spec):
    data = quotes([(110000, 110010), (110000, 110010), (90000, 90010), (110400, 110410)])
    result = replay(
        data,
        profile,
        spec,
        [{"available_at": data[0].event_ts_utc_ns, "side": "BUY"}],
        True,
        fill_model=NoLiquidityDuringGap(profile, True),
    )
    assert any(e["reason"] == "ELIGIBLE_FILL_PRICE_MISMATCH" for e in result["integrity_errors"])
    assert replay_quality(result, policy())["status"] == "FAILED_CHECKS"


@pytest.mark.parametrize(
    "change",
    [
        "unknown_valuation",
        "missing_insolvency",
        "mismatched_marks",
        "native_account",
        "missing_fills",
        "missing_context",
        "bad_drawdown",
    ],
)
def test_corrupted_native_evidence_cannot_pass_quality(profile, spec, change):
    data = quotes([(110000, 110010), (110000, 110010), (110400, 110410)])
    native = replay(
        data, profile, spec, [{"available_at": data[0].event_ts_utc_ns, "side": "BUY"}], True
    )
    assert replay_quality(native, policy())["status"] == "PASS"
    damaged = deepcopy(native)
    if change == "unknown_valuation":
        damaged["equity"]["status"] = "UNKNOWN_CONVERSION"
    elif change == "missing_insolvency":
        damaged["equity"].pop("insolvent_at_any_observation")
    elif change == "mismatched_marks":
        damaged["equity"]["quote_observations"] -= 1
    elif change == "native_account":
        damaged["reconciliation"]["native_reference_status"] = "MISMATCH"
    elif change == "missing_fills":
        damaged.pop("fills")
    elif change == "missing_context":
        damaged["native_quote_event_count"] -= 1
    elif change == "bad_drawdown":
        damaged["equity"]["max_mark_to_market_drawdown"] = "NaN"
    assert replay_quality(damaged, policy())["status"] == "FAILED_CHECKS"
