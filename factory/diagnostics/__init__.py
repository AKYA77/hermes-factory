"""Executable-side excursion measurements; flags survive incomplete paths."""

from decimal import Decimal as D


def summarize_path(path, side, entry_price):
    """One-pass sufficient statistics; exact values/tie policy match inline paths."""
    direction = D(1) if side == "BUY" else D(-1)
    points = 0
    mfe = mae = None
    mfe_time = mae_time = None
    peak = retracement = D(0)
    for point in path:
        move = (
            D(point["bid"] if side == "BUY" else point["ask"])
            - D(point.get("entry_reference", entry_price))
        ) * direction
        if mfe is None or move > mfe:
            mfe, mfe_time = move, point["ts"]
        if mae is None or move < mae:
            mae, mae_time = move, point["ts"]
        peak = max(peak, move)
        retracement = max(retracement, peak - move)
        points += 1
    return {
        "points": points,
        "mfe": str(max(D(0), mfe)) if mfe is not None else None,
        "mae": str(min(D(0), mae)) if mae is not None else None,
        "mfe_ts": mfe_time,
        "mae_ts": mae_time,
        "max_retracement": str(retracement),
    }


def diagnose_trade(
    trade, tick_size, fast_stop_seconds=60, favorable_r=D(".25"), near_target=D(".9")
):
    entry = trade["entry_fill"]
    side = trade["side"]
    direction = D(1) if side == "BUY" else D(-1)
    price = D(entry["price"]) if entry else D(0)
    summary = trade.get("path_summary")
    if summary is None:
        summary = summarize_path(trade.get("path", ()), side, price)
    if not summary["points"]:
        return {"status": "INCONCLUSIVE", "tags": ["UNRESOLVED_PATH"], "points": 0}
    stop_distance = D(trade.get("intended_stop_distance", abs(price - D(trade["stop"]))))
    if stop_distance <= 0:
        raise ValueError("INVALID_INTENDED_STOP_DISTANCE")
    mfe, mae = D(summary["mfe"]), D(summary["mae"])
    mfe_time, mae_time = summary["mfe_ts"], summary["mae_ts"]
    tags = list(trade["flags"])
    exit_fill = trade.get("exit_fill")
    if exit_fill:
        duration = (exit_fill["ts"] - entry["ts"]) / 1e9
        realized = (D(exit_fill["price"]) - price) * direction
        stop_fills = [f for f in trade.get("exit_fills", ()) if f.get("role") == "STOP_LOSS"]
        known_exits = trade.get("exit_fills", ())
        stopped = bool(stop_fills) if known_exits else trade.get("exit_reason") == "STOP_LOSS"
        if known_exits and trade.get("exit_reason") == "STOP_LOSS" and not stop_fills:
            tags.append("EXIT_REASON_ROLE_MISMATCH")
        if stop_fills:
            duration = (min(f["ts"] for f in stop_fills) - entry["ts"]) / 1e9
            if trade.get("exit_reason") == "MIXED":
                tags.append("PARTIAL_STOP_LOSS_EXIT")
        if trade.get("exit_reason") is None:
            tags.append("EXIT_CAUSE_UNKNOWN")
        if (
            stopped
            and realized < 0
            and duration <= fast_stop_seconds
            and mfe < stop_distance * favorable_r
        ):
            tags.append("FAST_STOP")
        if stopped and realized < 0 and mfe >= stop_distance * favorable_r:
            tags.append("FAVORABLE_THEN_STOP")
        target_filled = (
            any(f.get("role") == "TAKE_PROFIT" for f in trade.get("exit_fills", []))
            or trade.get("exit_reason") == "TAKE_PROFIT"
        )
        if (
            not target_filled
            and realized < stop_distance * 3
            and mfe >= stop_distance * 3 * near_target
        ):
            tags.append("TARGET_NEAR_MISS")
    incomplete = any(
        x in tags
        for x in (
            "NO_EXECUTABLE_EXIT_QUOTE",
            "UNRESOLVED_PATH",
            "DELAYED_TIMEOUT_QUOTE",
            "EXIT_REASON_ROLE_MISMATCH",
        )
    )
    return {
        "status": "INCONCLUSIVE" if incomplete else "MEASURED",
        "diagnostic_version": "diagnostics/v2-stop-role-cohorts",
        "stop_fill_count": sum(f.get("role") == "STOP_LOSS" for f in trade.get("exit_fills", ())),
        "stop_filled_quantity": str(
            sum(
                (D(f["size"]) for f in trade.get("exit_fills", ()) if f.get("role") == "STOP_LOSS"),
                D(0),
            )
        ),
        "points": summary["points"],
        "mfe": str(mfe),
        "mae": str(mae),
        "mfe_ts": mfe_time,
        "mae_ts": mae_time,
        "mfe_ticks": str(mfe / tick_size),
        "mae_ticks": str(mae / tick_size),
        "mfe_r": str(mfe / stop_distance),
        "mae_r": str(mae / stop_distance),
        "target_fraction": str(mfe / (3 * stop_distance)),
        "max_retracement": summary["max_retracement"],
        "tags": sorted(set(tags)),
    }
