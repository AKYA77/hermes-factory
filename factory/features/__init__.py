"""Closed-bar features. Candle availability is exclusive of the closing boundary."""

from dataclasses import dataclass
from decimal import Decimal as D
from collections import OrderedDict
import numpy as np
from factory.contracts import TIMEFRAMES, fingerprint


@dataclass(frozen=True)
class Bar:
    end_ns: int
    available_at: int
    close: D
    high: D
    low: D


def closed_bars(quotes, timeframe):
    width = TIMEFRAMES[timeframe] * 10**9
    bucket = None
    values = []
    for q in quotes:
        new = q.event_ts_utc_ns // width
        if bucket is not None and new != bucket:
            end = (bucket + 1) * width
            yield Bar(end, q.event_ts_utc_ns, values[-1], max(values), min(values))
            values = []
        bucket = new
        values.append(D(q.bid_int + q.ask_int) / (2 * q.price_scale))
    # No final bar without a later observation proving its closure.


def feature_key(dataset_hash, spec, code_revision, instrument_hash, time_policy="closed/v1"):
    return fingerprint(
        {
            "dataset": dataset_hash,
            "strategy": spec.strategy_hash,
            "code": code_revision,
            "instrument": instrument_hash,
            "time_policy": time_policy,
            "operator": "features/v1",
        }
    )


class BoundedCache:
    def __init__(self, max_bytes):
        self.max_bytes = max_bytes
        self.bytes = 0
        self.entries = OrderedDict()
        self.hits = self.misses = self.evictions = 0

    def get(self, key):
        if key not in self.entries:
            self.misses += 1
            return None
        self.hits += 1
        self.entries.move_to_end(key)
        return self.entries[key]

    def put(self, key, value):
        value = np.asarray(value).copy()
        value.flags.writeable = False
        if key in self.entries:
            self.bytes -= self.entries.pop(key).nbytes
        if value.nbytes > self.max_bytes:
            return
        while self.bytes + value.nbytes > self.max_bytes:
            _, old = self.entries.popitem(last=False)
            self.bytes -= old.nbytes
            self.evictions += 1
        self.entries[key] = value
        self.bytes += value.nbytes
