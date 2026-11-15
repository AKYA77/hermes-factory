"""Reproducible account sums, with explicit Decimal presentation boundaries."""

from decimal import Decimal as D, localcontext, ROUND_HALF_EVEN
from fractions import Fraction

VERSION = "account-sums/rational-decimal28-v1"


def decimal_amount(value):
    value = Fraction(value)
    with localcontext() as context:
        context.prec = 28
        context.rounding = ROUND_HALF_EVEN
        return D(value.numerator) / D(value.denominator)


def receipt(value):
    value = Fraction(value)
    return {
        "version": VERSION,
        "numerator": str(value.numerator),
        "denominator": str(value.denominator),
    }


def trade_pnl(trade):
    exact = trade.get("pnl_exact")
    if exact is None:
        return Fraction(D(trade["pnl"]))
    if exact.get("version") != VERSION or int(exact["denominator"]) <= 0:
        raise ValueError("INVALID_ACCOUNT_PNL_RECEIPT")
    value = Fraction(int(exact["numerator"]), int(exact["denominator"]))
    if decimal_amount(value) != D(trade["pnl"]):
        raise ValueError("ACCOUNT_PNL_RECEIPT_MISMATCH")
    return value
