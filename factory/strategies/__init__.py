"""One operator interpreter for screening and engine proposals; no dynamic code."""

from factory.features import closed_bars


def compile_signals(quotes, spec):
    quotes = list(quotes)
    bars = list(closed_bars(quotes, spec.timeframe))
    confirmations = {tf: list(closed_bars(quotes, tf)) for tf in spec.confirmations}
    signals = []
    n = spec.signal.lookback
    threshold = spec.signal.threshold
    for i in range(n, len(bars)):
        current = bars[i]
        history = bars[i - n : i]
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
            scale = sum(abs(b.close - a.close) for a, b in zip(history, history[1:])) / (n - 1)
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
        for tf, higher in confirmations.items():
            eligible = [
                b
                for b in higher
                if b.end_ns <= current.end_ns and b.available_at <= current.available_at
            ]
            if (
                len(eligible) < 2
                or (side == "BUY" and eligible[-1].close <= eligible[-2].close)
                or (side == "SELL" and eligible[-1].close >= eligible[-2].close)
            ):
                side = None
                break
        if side and (
            spec.direction == "both" or spec.direction == ("long" if side == "BUY" else "short")
        ):
            signals.append(
                {"available_at": current.available_at, "bar_end_ns": current.end_ns, "side": side}
            )
    return signals


def behavior_similarity(left, right):
    # Advisory only on a named training reference; not exact identity.
    a = {(s["available_at"], s["side"]) for s in left}
    b = {(s["available_at"], s["side"]) for s in right}
    return len(a & b) / len(a | b) if a | b else None
