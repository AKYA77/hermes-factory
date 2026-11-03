"""One operator interpreter for screening and engine proposals; no dynamic code."""

from collections import deque

from factory.features import closed_bar_events


def iter_signals(quotes, spec):
    """Single-pass past-only compiler, bounded by lookback and confirmation count.

    Higher bars are aligned monotonically by both end and publication time. A
    sparse source may publish several timeframes together; a higher bar ending
    after the entry bar must remain pending until a later eligible entry bar.
    """
    history = deque(maxlen=spec.signal.lookback)
    pending = {tf: deque() for tf in spec.confirmations}
    eligible = {tf: deque(maxlen=2) for tf in spec.confirmations}
    n = spec.signal.lookback
    threshold = spec.signal.threshold
    for event in closed_bar_events(quotes, (spec.timeframe, *spec.confirmations)):
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
        prices = [b.close for b in history]
        mean = sum(prices) / n
        side = None
        if spec.signal.operator == "mean_reversion":
            variance = sum((p - mean) ** 2 for p in prices) / n
            if variance:
                score = (current.close - mean) / variance.sqrt()
                side = "SELL" if score >= threshold else "BUY" if score <= -threshold else None
        elif spec.signal.operator == "momentum":
            delta = current.close - prices[0]
            scale = sum(abs(b - a) for a, b in zip(prices, prices[1:])) / (n - 1)
            if scale and abs(delta) >= threshold * scale:
                side = "BUY" if delta > 0 else "SELL"
        elif spec.signal.operator == "breakout":
            side = (
                "BUY"
                if current.close > max(b.high for b in history)
                else "SELL"
                if current.close < min(b.low for b in history)
                else None
            )
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
