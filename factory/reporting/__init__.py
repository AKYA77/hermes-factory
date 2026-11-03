from decimal import Decimal as D
from fractions import Fraction
from factory.validation import wilson
from factory.monetary import trade_pnl, decimal_amount


def metrics(trades, initial=D(20)):
    pnl = [trade_pnl(t) for t in trades]
    wins = sum(p > 0 for p in pnl)
    losses = sum(p < 0 for p in pnl)
    losing = winning = max_loss = max_win = 0
    equity = peak = Fraction(initial)
    max_dd = Fraction(0)
    for p in pnl:
        losing = losing + 1 if p < 0 else 0
        winning = winning + 1 if p > 0 else 0
        max_loss = max(max_loss, losing)
        max_win = max(max_win, winning)
        equity += p
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak > 0 else Fraction(0))
    return {
        "completed_trades": len(pnl),
        "wins": wins,
        "losses": losses,
        "breakeven": len(pnl) - wins - losses,
        "win_rate": wins / len(pnl) if pnl else None,
        "wilson_95": wilson(wins, len(pnl)),
        "ending_balance": str(decimal_amount(equity)),
        "balance_drawdown": str(decimal_amount(max_dd)),
        "max_losing_streak": max_loss,
        "max_winning_streak": max_win,
        "insolvent": equity <= 0,
        "warning": "Balance drawdown only; executable quote mark-to-market is reported separately when available",
    }
