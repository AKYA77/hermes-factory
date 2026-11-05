"""Independent bounded-feature parity oracle; deliberately slow on tiny corpora."""

from dataclasses import replace
from decimal import Decimal as D
import itertools

import pytest
from factory.contracts import TIMEFRAMES, Signal
from factory.features import Bar, closed_bars, feature_key, indicator_key
from factory.strategies import compile_signals, iter_signals
from conftest import quotes


def reference_bars(data, tf):
    width = TIMEFRAMES[tf] * 10**9
    out, active, bucket = [], [], None
    for q in data:
        new = q.event_ts_utc_ns // width
        if bucket is not None and new != bucket:
            out.append(
                Bar((bucket + 1) * width, q.event_ts_utc_ns, active[-1], max(active), min(active))
            )
            active = []
        bucket = new
        active.append(D(q.bid_int + q.ask_int) / (2 * q.price_scale))
    return out


def reference_signals(data, spec):
    bars = reference_bars(data, spec.timeframe)
    higher = {tf: reference_bars(data, tf) for tf in spec.confirmations}
    out = []
    for i in range(spec.signal.lookback, len(bars)):
        current, history = bars[i], bars[i - spec.signal.lookback : i]
        prices = [b.close for b in history]
        mean = sum(prices) / len(prices)
        side = None
        if spec.signal.operator == "momentum":
            delta = current.close - prices[0]
            scale = sum(abs(b - a) for a, b in zip(prices, prices[1:])) / (len(prices) - 1)
            if scale and abs(delta) >= spec.signal.threshold * scale:
                side = "BUY" if delta > 0 else "SELL"
        elif spec.signal.operator == "mean_reversion":
            variance = sum((p - mean) ** 2 for p in prices) / len(prices)
            if variance:
                z = (current.close - mean) / variance.sqrt()
                side = (
                    "SELL"
                    if z >= spec.signal.threshold
                    else "BUY"
                    if z <= -spec.signal.threshold
                    else None
                )
        else:
            side = (
                "BUY"
                if current.close > max(b.high for b in history)
                else "SELL"
                if current.close < min(b.low for b in history)
                else None
            )
        for hb in higher.values():
            usable = [
                b
                for b in hb
                if b.end_ns <= current.end_ns and b.available_at <= current.available_at
            ]
            if (
                len(usable) < 2
                or (side == "BUY" and usable[-1].close <= usable[-2].close)
                or (side == "SELL" and usable[-1].close >= usable[-2].close)
            ):
                side = None
                break
        if side and (
            spec.direction == "both" or spec.direction == ("long" if side == "BUY" else "short")
        ):
            out.append(
                {"available_at": current.available_at, "bar_end_ns": current.end_ns, "side": side}
            )
    return out


@pytest.mark.parametrize("operator", ["momentum", "mean_reversion", "breakout"])
@pytest.mark.parametrize("confirmations", [(), ("M5",), ("M5", "H1")])
def test_reference_signals_sparse_and_equal_timestamp(spec, operator, confirmations):
    data = quotes(
        [
            (110000 + (i % 71) * 8 - (i % 13) * 5, 110010 + (i % 71) * 8 - (i % 13) * 5)
            for i in range(900)
        ],
        step=37 * 10**9,
    )
    # Long gaps and tied timestamps, with stable original row order retained.
    data = [
        replace(q, event_ts_utc_ns=q.event_ts_utc_ns + (i // 200) * 7200 * 10**9)
        for i, q in enumerate(data)
    ]
    data[90] = replace(data[90], event_ts_utc_ns=data[89].event_ts_utc_ns)
    s = spec.model_copy(
        update={
            "signal": Signal(operator=operator, lookback=4, threshold="1"),
            "confirmations": confirmations,
        }
    )
    assert compile_signals(iter(data), s) == reference_signals(data, s)
    for tf in ("M1", "M5", "H1"):
        assert list(closed_bars(iter(data), tf)) == reference_bars(data, tf)


def test_lazy_compiler_does_not_read_tail(spec):
    def source():
        for i in itertools.count():
            if i > 20:
                raise AssertionError("compiler eagerly consumed data")
            yield replace(
                quotes([(110000 + i * 10, 110010 + i * 10)])[0],
                event_ts_utc_ns=1735689600 * 10**9 + i * 60 * 10**9,
                original_record_order=i,
            )

    first = next(iter_signals(source(), spec))
    assert first["side"] == "BUY"


def test_bar_feature_identity_excludes_trade_and_signal_settings(spec):
    key = feature_key("data", spec, "source", "profile")
    changed = spec.model_copy(
        update={
            "stop_ticks": spec.stop_ticks + 1,
            "direction": "short",
            "signal": Signal(operator="breakout", lookback=13, threshold="2"),
        }
    )
    assert key == feature_key("data", changed, "source", "profile")
    for data, code, profile, policy in [
        ("other", "source", "profile", "closed/v1"),
        ("data", "other", "profile", "closed/v1"),
        ("data", "source", "other", "closed/v1"),
        ("data", "source", "profile", "closed/v2"),
    ]:
        assert key != feature_key(data, spec, code, profile, policy)
    assert indicator_key(key, "atr", {"lookback": 3}, "1") != indicator_key(
        key, "atr", {"lookback": 4}, "1"
    )


def test_bar_rejects_regressing_source_order():
    data = quotes([(110000, 110010)] * 3)
    data[2] = replace(data[2], event_ts_utc_ns=data[0].event_ts_utc_ns)
    with pytest.raises(ValueError, match="ordering"):
        list(closed_bars(data, "M1"))


def test_ram_cache_rejects_mutation_collision_and_object_arrays():
    import numpy as np
    from factory.features import BoundedCache

    cache = BoundedCache(32)
    original = np.array([1, 2], dtype=np.int64)
    cache.put("a", original)
    original[0] = 99
    assert cache.get("a").tolist() == [1, 2]
    with pytest.raises(ValueError):
        cache.get("a").setflags(write=True)
    with pytest.raises(ValueError, match="collision"):
        cache.put("a", original)
    with pytest.raises(ValueError, match="fixed-width"):
        cache.put("object", np.array([{}], dtype=object))
    cache.put("too-large", np.arange(1000))
    assert cache.bytes == 16 and cache.get("too-large") is None


def test_empty_array_metadata_obeys_entry_budget():
    import numpy as np
    from factory.features import BoundedCache

    cache = BoundedCache(0, max_entries=2)
    for key in ("a", "b", "c"):
        cache.put(key, np.array([], dtype=np.int64))
    assert len(cache.entries) == 2 and cache.bytes == 0 and cache.evictions == 1


def test_feature_range_changes_identity(spec):
    assert feature_key("data", spec, "code", "profile", source_range=(1, 10)) != feature_key(
        "data", spec, "code", "profile", source_range=(2, 10)
    )
