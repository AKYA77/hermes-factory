"""Exact scenario arithmetic; matching remains entirely in Nautilus."""

from decimal import Decimal as D, ROUND_FLOOR, ROUND_CEILING


def round_tick(value, tick, up):
    return (value / tick).to_integral_value(rounding=ROUND_CEILING if up else ROUND_FLOOR) * tick


def effective_quotes(bid, ask, profile, conservative):
    if bid > ask:
        raise ValueError("inverted quote")
    if not conservative:
        return bid, ask
    spread = max(ask - bid, 2 * profile.pip_size)
    mid = (bid + ask) / 2
    # Outward tick rounding is explicit; odd half-ticks may widen the floor further.
    return (
        round_tick(mid - spread / 2, profile.tick_size, False),
        round_tick(mid + spread / 2, profile.tick_size, True),
    )


def eligible_price(price, side, order_type, profile, conservative, limit=None):
    slip = (
        2 * profile.pip_size if conservative and order_type in ("MARKET", "STOP_MARKET") else D(0)
    )
    result = round_tick(
        price + (slip if side == "BUY" else -slip), profile.tick_size, side == "BUY"
    )
    if limit is not None and (
        (side == "BUY" and result > limit) or (side == "SELL" and result < limit)
    ):
        raise ValueError("limit not executable")
    return result


def size_position(equity, entry, stop, profile, quote_to_account, conservative=True):
    if quote_to_account <= 0:
        raise ValueError("UNKNOWN_CONVERSION")
    distance = abs(entry - stop)
    if distance < profile.min_stop_ticks * profile.tick_size:
        return {"status": "SKIPPED_STOP_LEVEL"}
    # Include adverse stop execution in projected loss. Entry already includes its fill cost.
    loss_per_unit = (
        (distance + (2 * profile.pip_size if conservative else 0))
        * profile.contract_multiplier
        * quote_to_account
    )
    risk_budget = max(D(0), equity) * D(".1")
    raw = min(risk_budget / loss_per_unit, profile.max_volume)
    size = (raw / profile.volume_step).to_integral_value(rounding=ROUND_FLOOR) * profile.volume_step
    if size < profile.min_volume:
        return {"status": "SKIPPED_MIN_VOLUME"}
    margin = size * entry * profile.contract_multiplier * quote_to_account * profile.margin_rate
    if margin > equity:
        return {"status": "SKIPPED_MARGIN"}
    return {
        "status": "ELIGIBLE",
        "size": size,
        "risk": size * loss_per_unit,
        "risk_budget": risk_budget,
        "margin": margin,
    }
