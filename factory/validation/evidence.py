"""Validation admission checks over verified native artifacts, never new P&L."""

from decimal import Decimal as D, InvalidOperation
from fractions import Fraction

from factory.monetary import VERSION as MONEY_VERSION
from factory.simulation.ledger import EXECUTION_VERSION


def replay_quality(replay, policy):
    if replay is None:
        return {"status": "DATA_UNAVAILABLE", "reasons": ["NO_NATIVE_REPLAY"]}
    if not isinstance(replay, dict):
        return {"status": "FAILED_CHECKS", "reasons": ["INVALID_NATIVE_REPLAY_SHAPE"]}
    checks, failed, insufficient = [], [], []
    required = (
        replay.get("engine") == "nautilus_trader",
        replay.get("accounting_version") == EXECUTION_VERSION,
        replay.get("account_sum_policy") == MONEY_VERSION,
        type(replay.get("quote_count")) is int and replay["quote_count"] > 0,
        type(replay.get("native_quote_event_count")) is int,
        isinstance(replay.get("fills"), list),
        isinstance(replay.get("trades"), list)
        and all(isinstance(t, dict) for t in replay["trades"]),
        isinstance(replay.get("integrity_errors"), list) and not replay["integrity_errors"],
        isinstance(replay.get("rejections"), list) and not replay["rejections"],
    )
    if not all(required):
        return {"status": "FAILED_CHECKS", "reasons": ["MISSING_OR_INVALID_NATIVE_EVIDENCE"]}
    reconciliation = replay.get("reconciliation") or {}
    if not isinstance(reconciliation, dict):
        return {"status": "FAILED_CHECKS", "reasons": ["INVALID_RECONCILIATION_SHAPE"]}
    if (
        reconciliation.get("native_reference_status") != "VERIFIED"
        or reconciliation.get("issues") != []
    ):
        checks.append("NATIVE_ACCOUNTING_NOT_VERIFIED")
    if reconciliation.get("native_fill_count") != len(replay["fills"]):
        checks.append("NATIVE_FILL_COUNT_MISMATCH")
    currency = reconciliation.get("quote_currency")
    expected_events = replay["quote_count"] * (1 if currency == "USD" else 2)
    if not currency or replay.get("native_quote_event_count") != expected_events:
        checks.append("NATIVE_SOURCE_CONTEXT_COUNT_MISMATCH")
    equity = replay.get("equity") or {}
    if not isinstance(equity, dict):
        return {"status": "FAILED_CHECKS", "reasons": ["INVALID_EQUITY_SHAPE"]}
    if equity.get("status") not in ("EXACT_USD_QUOTE_VALUATION", "DATED_USD_ACCOUNT_VALUATION"):
        checks.append("MARKED_VALUATION_UNAVAILABLE")
    if equity.get("quote_observations") != replay["quote_count"] or equity.get(
        "fill_observations"
    ) != len(replay["fills"]):
        checks.append("MARKED_SOURCE_COUNT_MISMATCH")
    if type(equity.get("insolvent_at_any_observation")) is not bool:
        checks.append("INSOLVENCY_OBSERVATION_MISSING")
    elif equity["insolvent_at_any_observation"]:
        failed.append("MARKED_INSOLVENCY")
    try:
        drawdown = D(equity["max_mark_to_market_drawdown"])
        if not drawdown.is_finite() or drawdown < 0:
            raise ValueError("invalid drawdown")
        if drawdown > policy.max_marked_drawdown:
            failed.append("MARKED_DRAWDOWN_LIMIT")
    except (KeyError, ValueError, TypeError, InvalidOperation):
        checks.append("INVALID_MARKED_DRAWDOWN")
        drawdown = None
    try:
        ending_marked = D(equity["ending_marked_equity"])
        if not ending_marked.is_finite():
            raise ValueError("nonfinite marked equity")
    except (KeyError, ValueError, TypeError, InvalidOperation):
        ending_marked = None
        checks.append("ENDING_MARKED_EQUITY_MISSING")
    if any(trade.get("closed") is not True for trade in replay["trades"]):
        checks.append("UNFINISHED_TRADE_COUNTED_CLOSED")
    opened = replay.get("open_trade")
    censored = 0
    if opened is not None:
        try:
            quantity = D(opened["open_quantity"])
            if not quantity.is_finite() or quantity <= 0:
                raise ValueError("invalid open inventory")
            censored = 1
        except (KeyError, TypeError, ValueError, InvalidOperation):
            checks.append("INVALID_OPEN_INVENTORY")
    total = len(replay["trades"]) + censored
    if len(replay["fills"]) < len(replay["trades"]) * 2 + censored:
        checks.append("INSUFFICIENT_FILLS_FOR_DECLARED_TRADES")
    fraction = Fraction(censored, total) if total else Fraction(0)
    if fraction > Fraction(D(str(policy.max_censored_fraction))):
        insufficient.append("BOUNDARY_CENSORING_LIMIT")
    return {
        "status": "FAILED_CHECKS"
        if checks
        else "INSUFFICIENT_EVIDENCE"
        if insufficient
        else "OOS_FAILED"
        if failed
        else "PASS",
        "reasons": checks + failed + insufficient,
        "closed_trades": len(replay["trades"]),
        "censored_positions": censored,
        "observed_opportunities": total,
        "marked_drawdown": str(drawdown) if drawdown is not None else None,
        "ending_marked_equity": str(ending_marked) if ending_marked is not None else None,
    }


def aggregate_quality(items):
    for status in ("FAILED_CHECKS", "DATA_UNAVAILABLE", "INSUFFICIENT_EVIDENCE", "OOS_FAILED"):
        if any(item["status"] == status for item in items):
            return status
    return "PASS"
