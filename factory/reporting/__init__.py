from decimal import Decimal as D
from factory.validation import wilson


def metrics(trades, initial=D(20)):
    pnl = [D(t["pnl"]) for t in trades]
    wins = sum(p > 0 for p in pnl)
    losses = sum(p < 0 for p in pnl)
    losing = winning = max_loss = max_win = 0
    equity = peak = initial
    max_dd = D(0)
    for p in pnl:
        losing = losing + 1 if p < 0 else 0
        winning = winning + 1 if p > 0 else 0
        max_loss = max(max_loss, losing)
        max_win = max(max_win, winning)
        equity += p
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak > 0 else D(0))
    return {
        "completed_trades": len(pnl),
        "wins": wins,
        "losses": losses,
        "breakeven": len(pnl) - wins - losses,
        "win_rate": wins / len(pnl) if pnl else None,
        "wilson_95": wilson(wins, len(pnl)),
        "ending_balance": str(equity),
        "balance_drawdown": str(max_dd),
        "max_losing_streak": max_loss,
        "max_winning_streak": max_win,
        "insolvent": equity <= 0,
        "warning": "Balance drawdown only; executable quote mark-to-market is reported separately when available",
    }
