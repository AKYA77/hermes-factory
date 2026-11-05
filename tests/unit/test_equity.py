"""Transparent cash + inventory golden cases; no matching implementation."""

from decimal import Decimal as D
import pytest
from factory.reporting.equity import equity_summary, Envelope


def fill(index, side, size, price, identity):
    return {
        "quote_index": index,
        "ts": index + 1,
        "order_id": identity,
        "trade_id": identity,
        "side": side,
        "size": str(size),
        "price": str(price),
        "commission": "0",
    }


def test_marked_equity_long_short_and_adverse_execution(profile):
    rows = [(1, 110000, 110010, 0), (2, 108000, 108010, 1)]
    fills = [fill(0, "BUY", 100, "1.1001", "entry"), fill(1, "SELL", 100, "1.0798", "exit")]
    result = equity_summary(
        iter(rows),
        100000,
        profile,
        {"fills": fills, "ending_equity": "17.97", "open_trade": None},
        False,
    )
    assert D(result["ending_marked_equity"]) == D("17.97")
    assert D(result["max_mark_to_market_drawdown"]) == D("2.03") / 20
    assert result["fill_observations"] == 2 and result["quote_observations"] == 2
    rows = [(1, 110000, 110010, 0), (2, 112000, 112010, 1)]
    fills = [fill(0, "SELL", 100, "1.1", "entry"), fill(1, "BUY", 100, "1.1203", "exit")]
    other = equity_summary(
        iter(rows),
        100000,
        profile,
        {"fills": fills, "ending_equity": "17.97", "open_trade": None},
        False,
    )
    assert D(other["ending_marked_equity"]) == D(result["ending_marked_equity"])
    assert D(other["max_mark_to_market_drawdown"]) == D(result["max_mark_to_market_drawdown"])


def test_open_partial_inventory_is_marked_and_never_fabricated_closed(profile):
    rows = [(1, 110000, 110010, 0), (2, 108000, 108010, 1)]
    fills = [fill(0, "BUY", 100, "1.1001", "entry"), fill(1, "SELL", 40, "1.0798", "partial")]
    # Realized loss = 40*(1.0798-1.1001) = -.812; remaining 60 mark at 1.08.
    value = equity_summary(
        iter(rows),
        100000,
        profile,
        {
            "fills": fills,
            "ending_equity": "19.188",
            "open_trade": {"open_quantity": "60", "side": "BUY"},
        },
        False,
    )
    assert D(value["ending_marked_equity"]) == D("17.982")
    assert D(value["unrealized_pnl"]) == D("-1.206")
    assert value["signed_open_quantity"] == "60"
    with pytest.raises(ValueError, match="duplicate equity fill"):
        equity_summary(
            iter(rows),
            100000,
            profile,
            {"fills": fills[:1] + fills, "ending_equity": "0", "open_trade": None},
            False,
        )


def test_display_envelope_is_bounded_and_keeps_stream_extremes():
    envelope = Envelope(64)
    for i in range(10000):
        envelope.add({"ts": i, "equity": str((i % 111) - 20)})
    values = envelope.points()
    assert len(values) <= 64 and min(D(p["equity"]) for p in values) == -20
    assert max(D(p["equity"]) for p in values) == 90
    assert values[0]["ts"] == 0 and values[-1]["ts"] == 9999
