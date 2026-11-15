"""Exact past-only indicator primitives shared by all declarative operators.

Groups depend on closed history and lookback only, never thresholds, direction,
stops, costs, labels or future observations. Arithmetic order preserves Signal1/2.
"""

from decimal import getcontext


def decimal_policy():
    c = getcontext()
    return {
        **{k: getattr(c, k) for k in ("prec", "rounding", "Emin", "Emax", "capitals", "clamp")},
        "traps": sorted(k.__name__ for k, value in c.traps.items() if value),
    }


GROUPS = {
    "mean_reversion": ("moments",),
    "momentum": ("changes",),
    "session": ("changes",),
    "trend": ("changes", "slope"),
    "reversal": ("changes",),
    "breakout": ("envelope",),
    "range": ("envelope", "changes"),
    "volatility": ("range_mean", "changes"),
}
FIELDS = {
    "moments": ("mean", "variance"),
    "changes": ("first", "last", "change_scale"),
    "slope": ("slope",),
    "envelope": ("low", "high"),
    "range_mean": ("range_mean",),
}
VERSION = "past-decimal-primitives/v1"


def groups_for(signal):
    operators = signal.components if signal.operator == "confluence" else (signal.operator,)
    return tuple(sorted({group for op in operators for group in GROUPS[op]}))


def primitives(history, groups):
    n = len(history)
    if n < 2:
        raise ValueError("indicator history requires at least two closed bars")
    prices = [b.close for b in history]
    result = {}
    for group in groups:
        if group == "moments":
            mean = sum(prices) / n
            result.update(mean=mean, variance=sum((p - mean) ** 2 for p in prices) / n)
        elif group == "changes":
            result.update(
                first=prices[0],
                last=prices[-1],
                change_scale=sum(abs(b - a) for a, b in zip(prices, prices[1:])) / (n - 1),
            )
        elif group == "slope":
            result["slope"] = (
                6 * sum((2 * i - n + 1) * p for i, p in enumerate(prices)) / (n * (n * n - 1))
            )
        elif group == "envelope":
            result.update(low=min(b.low for b in history), high=max(b.high for b in history))
        elif group == "range_mean":
            result["range_mean"] = sum(b.high - b.low for b in history) / n
        else:
            raise ValueError("unknown indicator primitive")
    return result
