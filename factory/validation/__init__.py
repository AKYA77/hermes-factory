"""Time-ordered evaluation tools; no inferred validation from training metrics."""

from datetime import datetime, timezone
from math import sqrt


def wilson(wins, n, z=1.959963984540054):
    if n == 0:
        return None
    p = wins / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [max(0, center - half), min(1, center + half)]


def quarter_folds(start_ns, end_ns):
    dt = datetime.fromtimestamp(start_ns / 1e9, timezone.utc)
    quarter = (dt.month - 1) // 3 * 3 + 1
    boundary = datetime(dt.year, quarter, 1, tzinfo=timezone.utc)
    train_start = start_ns
    while True:
        year = boundary.year + (boundary.month + 2) // 12
        month = (boundary.month + 2) % 12 + 1
        boundary = datetime(year, month, 1, tzinfo=timezone.utc)
        cut = int(boundary.timestamp() * 1e9)
        if cut >= end_ns:
            break
        year = boundary.year + (boundary.month + 2) // 12
        month = (boundary.month + 2) % 12 + 1
        next_end = int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp() * 1e9)
        yield {
            "train_start": train_start,
            "train_end": cut,
            "oos_start": cut,
            "oos_end": min(next_end, end_ns),
            "partial": next_end > end_ns,
        }


def purge(trades, start_ns, end_ns, embargo_ns=0):
    return [
        t
        for t in trades
        if t["entry_fill"]["ts"] >= start_ns + embargo_ns
        and t.get("exit_fill")
        and t["exit_fill"]["ts"] < end_ns
    ]


def evidence_status(training_count, oos_count, oos_pass, integrity, holdout_consumed):
    if not integrity:
        return "FAILED_CHECKS"
    if oos_pass is False:
        return "OOS_FAILED"
    if training_count < 50 or oos_count < 50 or holdout_consumed or oos_pass is None:
        return "INSUFFICIENT_EVIDENCE"
    # Full promotion also needs independently stored WFO/robustness evidence.
    return "VALIDATION_PENDING"
