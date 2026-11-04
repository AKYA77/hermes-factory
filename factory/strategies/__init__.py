"""One operator interpreter for screening and engine proposals; no dynamic code."""

from collections import deque

from factory.features import closed_bar_events


def operator_side(history, current, signal, operator=None):
    """One past-only interpreter used by screening and authoritative replay.

    v2 confluence requires unanimous nonempty sides, sharing explicit lookback
    and threshold. Session hours refer to UTC publication time, not broker hours.
    """
    operator = operator or signal.operator
    if operator == "confluence":
        sides = [operator_side(history, current, signal, op) for op in signal.components]
        return sides[0] if sides and sides[0] and len(set(sides)) == 1 else None
    n, threshold = signal.lookback, signal.threshold
    prices = [b.close for b in history]
    mean = sum(prices) / n
    if operator == "mean_reversion":
        variance = sum((p - mean) ** 2 for p in prices) / n
        if variance:
            score = (current.close - mean) / variance.sqrt()
            return "SELL" if score >= threshold else "BUY" if score <= -threshold else None
    elif operator in ("momentum", "session"):
        if (
            operator == "session"
            and (current.available_at // (3600 * 10**9)) % 24 not in signal.session_hours
        ):
            return None
        delta = current.close - prices[0]
        scale = sum(abs(b - a) for a, b in zip(prices, prices[1:])) / (n - 1)
        if scale and abs(delta) >= threshold * scale:
            return "BUY" if delta > 0 else "SELL"
    elif operator == "breakout":
        return (
            "BUY"
            if current.close > max(b.high for b in history)
            else "SELL"
            if current.close < min(b.low for b in history)
            else None
        )
    elif operator == "trend":
        slope = 6 * sum((2 * i - n + 1) * p for i, p in enumerate(prices)) / (n * (n * n - 1))
        scale = sum(abs(b - a) for a, b in zip(prices, prices[1:])) / (n - 1)
        if scale and abs(slope) >= threshold * scale:
            if slope > 0 and current.close >= prices[-1]:
                return "BUY"
            if slope < 0 and current.close <= prices[-1]:
                return "SELL"
    elif operator == "reversal":
        scale = sum(abs(b - a) for a, b in zip(prices, prices[1:])) / (n - 1)
        delta, previous_trend = current.close - prices[-1], prices[-1] - prices[0]
        if scale and previous_trend < 0 and delta >= threshold * scale:
            return "BUY"
        if scale and previous_trend > 0 and delta <= -threshold * scale:
            return "SELL"
    elif operator == "range":
        low, high = min(b.low for b in history), max(b.high for b in history)
        zone = (high - low) * threshold / (2 * (1 + threshold))
        if low <= current.close <= high and high > low:
            if current.close <= low + zone and current.close > prices[-1]:
                return "BUY"
            if current.close >= high - zone and current.close < prices[-1]:
                return "SELL"
    elif operator == "volatility":
        scale = sum(b.high - b.low for b in history) / n
        if scale and current.high - current.low >= threshold * scale:
            return (
                "BUY"
                if current.close > prices[-1]
                else "SELL"
                if current.close < prices[-1]
                else None
            )
    return None


def iter_signals(quotes, spec):
    yield from iter_bar_signals(
        closed_bar_events(quotes, (spec.timeframe, *spec.confirmations)), spec
    )


def iter_bar_signals(events, spec):
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
        side = operator_side(history, current, spec.signal)
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
