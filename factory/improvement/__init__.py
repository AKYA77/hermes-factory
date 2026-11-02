"""Bounded controlled variants; no OOS selection or implicit trailing stops."""

from factory.contracts import StrategySpec


def children(parent, max_children=4):
    candidates = []
    for ticks in sorted({max(1, parent.stop_ticks // 2), parent.stop_ticks * 2}):
        candidates.append(({"stop_ticks": ticks}, "test stop distance with fixed 3R target"))
    candidates.append(
        (
            {
                "signal": parent.signal.model_copy(
                    update={"lookback": min(500, parent.signal.lookback + 2)}
                )
            },
            "test later signal context",
        )
    )
    if not parent.confirmations and parent.timeframe != "D1":
        candidates.append(({"confirmations": ("D1",)}, "test closed daily trend confirmation"))
    for changes, reason in candidates[:max_children]:
        raw = parent.model_dump()
        raw.update(changes)
        child = StrategySpec.model_validate(raw)
        if child.strategy_hash != parent.strategy_hash:
            yield child, reason
