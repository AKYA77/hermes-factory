"""Independent accounting reference for the pinned native floating Money policy.

No matching and no native accounting calls. Exact research arithmetic stays in
the Decimal ledger. This reference intentionally uses binary64 at the same
documented boundaries as Nautilus 1.231.0, including its high precision build.
"""

from decimal import Decimal as D
from math import copysign, isfinite, modf

VERSION = "nautilus-money-reference/1.231.0-v2"
FIXED_SCALAR = 10**16


def fixed_float(value):
    """Model native raw fixed integer / binary64 scalar conversion exactly."""
    raw = D(value) * FIXED_SCALAR
    if not raw.is_finite() or raw != raw.to_integral_value():
        raise ValueError("UNREPRESENTABLE_NATIVE_FIXED_VALUE")
    return float(int(raw)) / float(FIXED_SCALAR)


def money_round(value, precision):
    """Native constructor: binary64 scaling then nearest, ties away from zero.

    Money.from_str uses a different Decimal policy and is not the constructor
    invoked by the pinned position/account implementation. Do not substitute it.
    """
    if isinstance(precision, bool) or not isinstance(precision, int) or not 0 <= precision <= 16:
        raise ValueError("INVALID_CURRENCY_PRECISION")
    scaled = float(value) * 10**precision
    if not isfinite(scaled):
        raise ValueError("NONFINITE_NATIVE_MONEY")
    fraction, integer = modf(scaled)
    units = int(integer) + (int(copysign(1, scaled)) if abs(fraction) >= 0.5 else 0)
    return D(units).scaleb(-precision)


def position_reference(
    fills, *, currency_precision, size_precision, account_precision=None, conversion_rate=None
):
    """Zero-commission linear native-base-unit inventory, in quote currency.

    Account P&L rounds each closing fill. Position P&L rounds its prior rounded
    balance plus each unrounded binary64 closing delta; those are different
    operations. Commissions, reversals and inverse contracts require separate
    policies and are explicitly refused rather than silently approximated.
    """
    quantity = 0.0
    average = 0.0
    entry_side = None
    position_pnl = account_pnl = D(0)
    account_converted_pnl = D(0)
    closing_fills = 0
    for fill in fills:
        if D(fill["commission"]) != 0:
            raise ValueError("UNSUPPORTED_NATIVE_REFERENCE_COMMISSION")
        size, price = fixed_float(fill["size"]), fixed_float(fill["price"])
        if size <= 0 or price <= 0 or fill["side"] not in ("BUY", "SELL"):
            raise ValueError("INVALID_NATIVE_REFERENCE_FILL")
        if entry_side is None:
            entry_side = fill["side"]
            average = price
            quantity = size
            continue
        if quantity == 0:
            raise ValueError("NATIVE_REFERENCE_LIFETIME_REOPENED")
        if fill["side"] == entry_side:
            average = (average * quantity + price * size) / (quantity + size)
            quantity = round(quantity + size, size_precision)
        else:
            if round(size - quantity, size_precision) > 0:
                raise ValueError("NATIVE_REFERENCE_REVERSAL")
            points = price - average if entry_side == "BUY" else average - price
            # Native linear Position._calculate_pnl multiplication order.
            delta = min(size, quantity) * 1.0 * points
            quote_delta = money_round(delta, currency_precision)
            account_pnl += quote_delta
            if conversion_rate is not None:
                if account_precision is None:
                    raise ValueError("MISSING_ACCOUNT_PRECISION")
                rate = conversion_rate(fill)
                if not isfinite(rate) or rate <= 0:
                    raise ValueError("INVALID_NATIVE_REFERENCE_CONVERSION")
                account_converted_pnl += money_round(
                    fixed_float(quote_delta) * rate, account_precision
                )
            position_pnl = money_round(fixed_float(position_pnl) + delta, currency_precision)
            quantity = round(quantity - size, size_precision)
            closing_fills += 1
    return {
        "version": VERSION,
        "position_quote_pnl": str(position_pnl),
        "account_quote_pnl": str(account_pnl),
        "account_converted_pnl": str(account_converted_pnl)
        if conversion_rate is not None
        else None,
        "open_quantity": str(D(str(quantity))),
        "closing_fills": closing_fills,
    }
