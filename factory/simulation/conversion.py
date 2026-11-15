"""Dated quote-to-USD policy for the blueprint's eight linear instruments.

No midpoint conversion or external cross-rate guesses. Inverted base-USD quotes
use the opposite executable side, following the declared native fill-side policy.
"""

from decimal import Decimal as D, localcontext, ROUND_HALF_EVEN
from factory.simulation.native_money import fixed_float

VERSION = "dated-executable-fx/decimal28-v1"


def quote_to_usd(profile, bid, ask, side):
    bid, ask = D(bid), D(ask)
    if not bid.is_finite() or not ask.is_finite() or bid <= 0 or ask < bid:
        raise ValueError("INVALID_CONVERSION_QUOTE")
    if side not in ("BUY", "SELL"):
        raise ValueError("INVALID_CONVERSION_SIDE")
    if profile.quote_currency == "USD":
        return D(1)
    if profile.base_currency != "USD":
        raise ValueError("UNKNOWN_CONVERSION")
    with localcontext() as context:
        context.prec = 28
        context.rounding = ROUND_HALF_EVEN
        return D(1) / (ask if side == "SELL" else bid)


def native_rate_reference(profile, bid, ask, side):
    """Independent reference for cache fixed-price -> binary64 -> rate behavior."""
    if profile.quote_currency == "USD":
        return 1.0
    # Cache constructs its table from Price.as_f64, not canonical Decimal prices.
    return float(quote_to_usd(profile, D(str(fixed_float(bid))), D(str(fixed_float(ask))), side))
