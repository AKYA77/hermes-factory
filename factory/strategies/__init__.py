"""One operator interpreter for screening and engine proposals; no dynamic code."""

from collections import deque

from factory.features import closed_bar_events
from factory.features.transforms import groups_for, primitives


def operator_side(history, current, signal, operator=None, transforms=None):
    """One past-only interpreter used by screening and authoritative replay.

    v2 confluence requires unanimous nonempty sides, sharing explicit lookback
    and threshold. Session hours refer to UTC publication time, not broker hours.
    """
    operator = operator or signal.operator
    if transforms is None:
        transforms = primitives(history, groups_for(signal))
    if operator == "confluence":
        sides = [
            operator_side(history, current, signal, op, transforms) for op in signal.components
        ]
        return sides[0] if sides and sides[0] and len(set(sides)) == 1 else None
    threshold = signal.threshold
    if operator == "mean_reversion":
        mean, variance = transforms["mean"], transforms["variance"]
        if variance:
            score = (current.close - mean) / variance.sqrt()
            return "SELL" if score >= threshold else "BUY" if score <= -threshold else None
    elif operator in ("momentum", "session"):
        if (
            operator == "session"
            and (current.available_at // (3600 * 10**9)) % 24 not in signal.session_hours
        ):
            return None
        delta = current.close - transforms["first"]
        scale = transforms["change_scale"]
        if scale and abs(delta) >= threshold * scale:
            return "BUY" if delta > 0 else "SELL"
    elif operator == "breakout":
        return (
            "BUY"
            if current.close > transforms["high"]
            else "SELL"
            if current.close < transforms["low"]
            else None
        )
    elif operator == "trend":
        slope = transforms["slope"]
        scale = transforms["change_scale"]
        if scale and abs(slope) >= threshold * scale:
            if slope > 0 and current.close >= transforms["last"]:
                return "BUY"
            if slope < 0 and current.close <= transforms["last"]:
                return "SELL"
    elif operator == "reversal":
        scale = transforms["change_scale"]
        delta, previous_trend = (
            current.close - transforms["last"],
            transforms["last"] - transforms["first"],
        )
        if scale and previous_trend < 0 and delta >= threshold * scale:
            return "BUY"
        if scale and previous_trend > 0 and delta <= -threshold * scale:
            return "SELL"
    elif operator == "range":
        low, high = transforms["low"], transforms["high"]
        zone = (high - low) * threshold / (2 * (1 + threshold))
        if low <= current.close <= high and high > low:
            if current.close <= low + zone and current.close > transforms["last"]:
                return "BUY"
            if current.close >= high - zone and current.close < transforms["last"]:
                return "SELL"
    elif operator == "volatility":
        scale = transforms["range_mean"]
        if scale and current.high - current.low >= threshold * scale:
            return (
                "BUY"
                if current.close > transforms["last"]
                else "SELL"
                if current.close < transforms["last"]
                else None
            )
    return None


def iter_signals(quotes, spec):
    yield from iter_bar_signals(
        closed_bar_events(quotes, (spec.timeframe, *spec.confirmations)), spec
    )


def iter_bar_signals(events, spec, *, transform_lookup=None):
    """Single-pass past-only compiler, bounded by lookback and confirmation count.

    Higher bars are aligned monotonically by both end and publication time. A
    sparse source may publish several timeframes together; a higher bar ending
    after the entry bar must remain pending until a later eligible entry bar.
    """
    history = deque(maxlen=spec.signal.lookback)
    pending = {tf: deque() for tf in spec.confirmations}
    eligible = {tf: deque(maxlen=2) for tf in spec.confirmations}
    n = spec.signal.lookback
    for event in events:
        for tf in spec.confirmations:
            if tf in event:
                pending[tf].append(event[tf])
        current = event.get(spec.timeframe)
        if current is None:
            continue
        for tf in spec.confirmations:
            while pending[tf] and (
                pending[tf][0].end_ns <= current.end_ns
                and pending[tf][0].available_at <= current.available_at
            ):
                eligible[tf].append(pending[tf].popleft())
        if len(history) < n:
            history.append(current)
            continue
        transforms = transform_lookup(current) if transform_lookup is not None else None
        side = operator_side(history, current, spec.signal, transforms=transforms)
        for higher in eligible.values():
            if (
                len(higher) < 2
                or (side == "BUY" and higher[-1].close <= higher[-2].close)
                or (side == "SELL" and higher[-1].close >= higher[-2].close)
            ):
                side = None
                break
        history.append(current)
        if side and (
            spec.direction == "both" or spec.direction == ("long" if side == "BUY" else "short")
        ):
            yield {"available_at": current.available_at, "bar_end_ns": current.end_ns, "side": side}


def compile_signals(quotes, spec):
    """Small-call compatibility API; production replay consumes iter_signals directly."""
    return list(iter_signals(quotes, spec))


def behavior_similarity(left, right):
    # Advisory only on a named training reference; not exact identity.
    a = {(s["available_at"], s["side"]) for s in left}
    b = {(s["available_at"], s["side"]) for s in right}
    return len(a & b) / len(a | b) if a | b else None
