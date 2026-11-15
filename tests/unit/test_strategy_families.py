"""Versioned entry hypotheses; generated references are not market evidence."""

from decimal import Decimal as D
from dataclasses import replace

import pytest
from pydantic import ValidationError

from factory.contracts import Signal, StrategySpec, TIMEFRAMES, serialize, fingerprint
from factory.features import Bar
from factory.strategies import operator_side, compile_signals, iter_bar_signals
from factory.data import Quote


def bar(close, low=None, high=None, hour=12):
    return Bar(
        10,
        hour * 3600 * 10**9,
        D(str(close)),
        D(str(high if high is not None else close)),
        D(str(low if low is not None else close)),
    )


@pytest.mark.parametrize(
    "operator,history,current,expected",
    [
        ("trend", [bar(1), bar(2), bar(3)], bar(4), "BUY"),
        ("trend", [bar(3), bar(2), bar(1)], bar(0.5), "SELL"),
        ("reversal", [bar(3), bar(2), bar(1)], bar(2), "BUY"),
        ("reversal", [bar(1), bar(2), bar(3)], bar(2), "SELL"),
        ("range", [bar(5, 0, 10), bar(1), bar(0.5)], bar(1), "BUY"),
        ("range", [bar(5, 0, 10), bar(9), bar(9.5)], bar(9), "SELL"),
        ("volatility", [bar(1, 0.5, 1.5), bar(2, 1.5, 2.5), bar(3, 2.5, 3.5)], bar(4, 2, 6), "BUY"),
        (
            "volatility",
            [bar(3, 2.5, 3.5), bar(2, 1.5, 2.5), bar(1, 0.5, 1.5)],
            bar(0.5, 0.1, 4.1),
            "SELL",
        ),
    ],
)
def test_independent_hand_arithmetic(operator, history, current, expected):
    signal = Signal(operator=operator, lookback=3, threshold="1", version="2")
    assert operator_side(history, current, signal) == expected


def test_session_uses_actual_closed_bar_publication_hour():
    signal = Signal(operator="session", lookback=3, threshold="1", version="2", session_hours=(12,))
    history = [bar(1), bar(2), bar(3)]
    current = bar(4, hour=12)
    assert operator_side(history, current, signal) == "BUY"
    # Identical bar end/close published after a sparse gap is outside the session.
    assert operator_side(history, replace(current, available_at=13 * 3600 * 10**9), signal) is None


def test_confluence_unanimity_and_commutative_identity():
    common = dict(operator="confluence", lookback=3, threshold="1", version="2")
    a = Signal(**common, components=("trend", "momentum"))
    b = Signal(**common, components=("momentum", "trend"))
    assert fingerprint(a) == fingerprint(b)
    assert operator_side([bar(1), bar(2), bar(3)], bar(4), a) == "BUY"
    c = Signal(**common, components=("trend", "mean_reversion"))
    assert operator_side([bar(1), bar(2), bar(3)], bar(4), c) is None
    assert operator_side([bar(1), bar(1), bar(1)], bar(1), a) is None


@pytest.mark.parametrize(
    "changes",
    [
        {"operator": "trend"},
        {"operator": "session", "version": "2"},
        {"operator": "session", "version": "2", "session_hours": (True,)},
        {"operator": "session", "version": "2", "session_hours": (24,)},
        {"operator": "session", "version": "2", "session_hours": (12, 12)},
        {"operator": "momentum", "version": "2", "session_hours": (12,)},
        {"operator": "confluence", "version": "2", "components": ("trend",)},
        {"operator": "confluence", "version": "2", "components": ("trend", "trend")},
        {"operator": "confluence", "version": "2", "components": ("confluence", "trend")},
        {"operator": "trend", "version": "2", "components": ("momentum", "trend")},
    ],
)
def test_ambiguous_or_legacy_semantic_upgrade_rejected(changes):
    with pytest.raises(ValidationError):
        Signal(**{"operator": "momentum", "lookback": 3, "threshold": "1", **changes})


def test_legacy_serialized_shape_and_hash_remain_exact(spec):
    expected = {
        "schema_version": "strategy/v1",
        "instrument": "EURUSD",
        "timeframe": "M1",
        "signal": {"operator": "momentum", "lookback": 2, "threshold": "1", "version": "1"},
        "confirmations": [],
        "stop_ticks": 100,
        "target_rr": "3",
        "max_hold_seconds": 86400,
        "direction": "both",
        "semantic_version": "1",
    }
    assert serialize(spec) == serialize(expected)
    assert spec.strategy_hash == fingerprint(expected)


def generated_quotes(timeframe="M1", bars=32):
    step = TIMEFRAMES[timeframe] * 10**9
    levels = [
        110100,
        110000,
        109990,
        110000,
        110100,
        110200,
        110210,
        110200,
        110300,
        110200,
        110100,
        110200,
        110300,
        110400,
        110300,
        110200,
    ]
    for i in range(bars):
        width = 20 if i % 7 == 0 else 5
        for j, offset in enumerate((-width, width, 0)):
            bid = levels[i % len(levels)] + offset
            yield Quote(
                "EURUSD",
                1735689600 * 10**9 + i * step + j * step // 3,
                bid,
                bid + 10,
                100000,
                "generated-family-test",
                "v1",
                i * 3 + j,
            )


@pytest.mark.parametrize("timeframe", list(TIMEFRAMES))
@pytest.mark.parametrize(
    "operator", ["trend", "reversal", "range", "volatility", "session", "confluence"]
)
def test_future_suffix_cannot_change_past_new_family_signals(timeframe, operator):
    signal = Signal(
        operator=operator,
        lookback=3,
        threshold="1",
        version="2",
        session_hours=tuple(range(24)) if operator == "session" else (),
        components=("momentum", "trend") if operator == "confluence" else (),
    )
    spec = StrategySpec(instrument="EURUSD", timeframe=timeframe, signal=signal, stop_ticks=100)
    original = list(generated_quotes(timeframe))
    cut = original[48].event_ts_utc_ns
    changed = [
        q
        if q.event_ts_utc_ns <= cut
        else replace(q, bid_int=q.bid_int + 5000, ask_int=q.ask_int + 5000)
        for q in original
    ]
    a = [s for s in compile_signals(original, spec) if s["available_at"] <= cut]
    b = [s for s in compile_signals(changed, spec) if s["available_at"] <= cut]
    assert a == b
    assert a, (operator, timeframe)


def test_new_family_confirmation_cannot_use_later_ending_higher_bar():
    def timed(end, available, close):
        return Bar(end * 10**9, available * 10**9, D(close), D(close), D(close))

    spec = StrategySpec(
        instrument="EURUSD",
        timeframe="M1",
        confirmations=("H1",),
        stop_ticks=100,
        signal=Signal(operator="trend", lookback=2, threshold="1", version="2"),
    )
    events = [
        {"M1": timed(3600, 3600, "1"), "H1": timed(3600, 3600, "1")},
        {"M1": timed(3660, 3660, "2")},
        # A sparse quote publishes both, but H1 ends after this entry bar.
        {"M1": timed(3720, 7300, "3"), "H1": timed(7200, 7300, "2")},
        {"M1": timed(7360, 7360, "4")},
    ]
    assert list(iter_bar_signals(events, spec)) == [
        {"available_at": 7360 * 10**9, "bar_end_ns": 7360 * 10**9, "side": "BUY"}
    ]
