"""Explicit chronological research summaries; no synthetic/market substitution."""

from datetime import datetime, timezone
from decimal import Decimal as D
from fractions import Fraction
from statistics import median

from scipy.stats import binomtest
from factory.monetary import trade_pnl, decimal_amount


def holm(p_values, alpha):
    if not 0 < alpha < 1 or any(not 0 <= p <= 1 for p in p_values):
        raise ValueError("invalid multiple-testing inputs")
    result = [False] * len(p_values)
    for rank, index in enumerate(sorted(range(len(p_values)), key=lambda i: (p_values[i], i))):
        if p_values[index] > alpha / (len(p_values) - rank):
            break
        result[index] = True
    return result


def outcome_summary(trades, initial=D(20)):
    from factory.reporting import metrics

    summary = metrics(trades, initial)
    pnl = [trade_pnl(t) for t in trades]
    gains = sum((p for p in pnl if p > 0), Fraction(0))
    losses = -sum((p for p in pnl if p < 0), Fraction(0))
    recovery = 0
    longest_recovery = 0
    equity = peak = Fraction(initial)
    for value in pnl:
        equity += value
        recovery = recovery + 1 if equity < peak else 0
        peak = max(peak, equity)
        longest_recovery = max(longest_recovery, recovery)
    summary.update(
        gross_profit=str(decimal_amount(gains)),
        gross_loss=str(decimal_amount(losses)),
        profit_factor=str(decimal_amount(gains / losses)) if losses else None,
        profit_factor_status="FINITE" if losses else "NO_LOSSES" if gains else "NO_TRADES",
        expectancy=str(decimal_amount(sum(pnl, Fraction(0)) / len(pnl))) if pnl else None,
        longest_balance_recovery_trades=longest_recovery,
        unrecovered_at_end=bool(recovery),
        one_sided_win_fraction_pvalue=float(
            binomtest(sum(p > 0 for p in pnl), len(pnl), 0.5, alternative="greater").pvalue
        )
        if pnl
        else None,
        inference_warning="binomial summary assumes independent trade outcomes; not proof of expected profitability",
    )
    return summary


def stability_summary(base, neighbors):
    values = [D(n["ending_balance"]) for n in neighbors if n["completed_trades"]]
    return {
        "neighbor_count": len(neighbors),
        "neighbors_with_trades": len(values),
        "median_ending_balance": str(median(values)) if values else None,
        "min_ending_balance": str(min(values)) if values else None,
        "max_ending_balance": str(max(values)) if values else None,
        "median_absolute_deviation": str(median(abs(x - median(values)) for x in values))
        if values
        else None,
        "isolated_peak": bool(values and D(base["ending_balance"]) > max(values)),
        "source_role": "training_only; never select neighbors from holdout feedback",
    }


def annual_windows(start_ns, end_ns):
    if start_ns >= end_ns:
        raise ValueError("invalid annual span")
    year = datetime.fromtimestamp(start_ns // 10**9, timezone.utc).year
    while True:
        begin = int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp()) * 10**9
        end = int(datetime(year + 1, 1, 1, tzinfo=timezone.utc).timestamp()) * 10**9
        if begin >= end_ns:
            return
        yield {
            "year": year,
            "start_ns": max(start_ns, begin),
            "end_ns": min(end_ns, end),
            "partial": start_ns > begin or end_ns < end,
        }
        year += 1
