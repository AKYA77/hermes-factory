"""Executable-side excursion measurements; flags survive incomplete paths."""

from decimal import Decimal as D


def diagnose_trade(
    trade, tick_size, fast_stop_seconds=60, favorable_r=D(".25"), near_target=D(".9")
):
    entry = trade["entry_fill"]
    path = trade["path"]
    if not path:
        return {"status": "INCONCLUSIVE", "tags": ["UNRESOLVED_PATH"], "points": 0}
    side = trade["side"]
    direction = D(1) if side == "BUY" else D(-1)
    price = D(entry["price"])
    stop_distance = abs(price - D(trade["stop"]))
    moves = [
        (p["ts"], (D(p["bid"] if side == "BUY" else p["ask"]) - price) * direction) for p in path
    ]
    mfe_time, mfe = max(moves, key=lambda v: v[1])
    mae_time, mae = min(moves, key=lambda v: v[1])
    mfe, mae = max(D(0), mfe), min(D(0), mae)
    tags = list(trade["flags"])
    exit_fill = trade.get("exit_fill")
    if exit_fill:
        duration = (exit_fill["ts"] - entry["ts"]) / 1e9
        realized = (D(exit_fill["price"]) - price) * direction
        if realized < 0 and duration <= fast_stop_seconds and mfe < stop_distance * favorable_r:
            tags.append("FAST_STOP")
        if realized < 0 and mfe >= stop_distance * favorable_r:
            tags.append("FAVORABLE_THEN_STOP")
        if realized < stop_distance * 3 and mfe >= stop_distance * 3 * near_target:
            tags.append("TARGET_NEAR_MISS")
    incomplete = any(
        x in tags for x in ("NO_EXECUTABLE_EXIT_QUOTE", "UNRESOLVED_PATH", "DELAYED_TIMEOUT_QUOTE")
    )
    peak = D(0)
    retracement = D(0)
    for _, move in moves:
        peak = max(peak, move)
        retracement = max(retracement, peak - move)
    return {
        "status": "INCONCLUSIVE" if incomplete else "MEASURED",
        "points": len(path),
        "mfe": str(mfe),
        "mae": str(mae),
        "mfe_ts": mfe_time,
        "mae_ts": mae_time,
        "mfe_ticks": str(mfe / tick_size),
        "mae_ticks": str(mae / tick_size),
        "mfe_r": str(mfe / stop_distance),
        "mae_r": str(mae / stop_distance),
        "target_fraction": str(mfe / (3 * stop_distance)),
        "max_retracement": str(retracement),
        "tags": sorted(set(tags)),
    }
