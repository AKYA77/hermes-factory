"""Market volatility regime classification from canonical M1 midpoints.

Regimes are descriptive and relative to the reviewed training window. They are
not broker session, news-event or calendar classifications, and they never
qualify or promote a strategy.
"""

from decimal import Decimal as D
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

MINUTE_NS = 60 * 10**9


def load_m1_midpoints(catalog_root, dataset_hash, start_ns, end_ns):
    """Last midpoint of each whole UTC minute inside the reviewed window."""
    path = Path(catalog_root) / dataset_hash / "quotes.parquet"
    if not path.exists():
        return None
    table = pq.read_table(path, columns=["event_ts_utc_ns", "bid_int", "ask_int"])
    ts = table.column("event_ts_utc_ns").to_numpy()
    bid = table.column("bid_int").to_numpy()
    ask = table.column("ask_int").to_numpy()
    mask = (ts >= start_ns) & (ts < end_ns)
    ts, bid, ask = ts[mask], bid[mask], ask[mask]
    if not len(ts):
        return None
    minute = ts // MINUTE_NS
    order = np.argsort(minute, kind="stable")
    minute = minute[order]
    mid = (bid[order] + ask[order]) / 2
    last = np.ones(len(minute), dtype=bool)
    last[:-1] = minute[1:] != minute[:-1]
    return minute[last], mid[last]


def realized_volatility(mid, window):
    """Trailing standard deviation of log returns over `window` minutes."""
    if len(mid) < window + 2:
        return None
    returns = np.diff(np.log(mid))
    vol = np.full(len(returns), np.nan)
    for index in range(window - 1, len(returns)):
        vol[index] = returns[index - window + 1 : index + 1].std()
    return vol


def regime_classifier(minute, vol, window, quantiles=(D("0.33"), D("0.67"))):
    """Map each minute to LOW / NORMAL / HIGH relative to the window quantiles."""
    finite = vol[np.isfinite(vol)]
    if not len(finite):
        return None
    low = D(str(np.quantile(finite, float(quantiles[0]))))
    high = D(str(np.quantile(finite, float(quantiles[1]))))
    lookup = {}
    for index, value in enumerate(vol):
        if not np.isfinite(value):
            continue
        current = D(str(value))
        label = "LOW" if current <= low else "HIGH" if current >= high else "NORMAL"
        lookup[int(minute[index])] = label
    return {"lookup": lookup, "low_threshold": str(low), "high_threshold": str(high)}


def regime_of(classifier, entry_ns, sessions=None):
    if not classifier:
        return None
    minute = int(entry_ns) // MINUTE_NS
    lookup = classifier["lookup"]
    if minute in lookup:
        return lookup[minute]
    # The trailing window needs preceding minutes; the first bar has no regime.
    for candidate in range(minute - 1, minute - 5, -1):
        if candidate in lookup:
            return lookup[candidate]
    return None
