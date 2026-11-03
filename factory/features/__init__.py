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


class BarBuilder:
    """One rolling aggregate, published only by the first subsequent-bucket quote.

    No empty bars or tick volume are fabricated. Equal timestamp source order is
    retained by the input iterator. The closing observation belongs to the next
    bar, and cannot execute a signal that it has just made available.
    """

    def __init__(self, timeframe):
        self.width = TIMEFRAMES[timeframe] * 10**9
        self.bucket = None
        self.close = self.high = self.low = None

    def update(self, q):
        bucket = q.event_ts_utc_ns // self.width
        if self.bucket is not None and bucket < self.bucket:
            raise ValueError("out-of-order bars")
        price = D(q.bid_int + q.ask_int) / (2 * q.price_scale)
        closed = None
        if self.bucket is not None and bucket != self.bucket:
            closed = Bar(
                (self.bucket + 1) * self.width,
                q.event_ts_utc_ns,
                self.close,
                self.high,
                self.low,
            )
        if self.bucket != bucket:
            self.high = self.low = price
        else:
            self.high, self.low = max(self.high, price), min(self.low, price)
        self.bucket, self.close = bucket, price
        return closed


def closed_bar_events(quotes, timeframes):
    builders = {tf: BarBuilder(tf) for tf in timeframes}
    previous = None
    for q in quotes:
        key = (q.event_ts_utc_ns, getattr(q, "sequence", q.original_record_order))
        if previous is not None and key <= previous:
            raise ValueError("invalid quote event ordering")
        previous = key
        published = {}
        for tf, builder in builders.items():
            bar = builder.update(q)
            if bar is not None:
                published[tf] = bar
        if published:
            yield published


def closed_bars(quotes, timeframe):
    for event in closed_bar_events(quotes, (timeframe,)):
        yield event[timeframe]
    # No final bar without a later observation proving its closure.


def feature_key(
    dataset_hash,
    spec,
    code_revision,
    instrument_hash,
    time_policy="closed/v1",
    *,
    source_range=None,
):
    if source_range is not None and (len(source_range) != 2 or source_range[0] >= source_range[1]):
        raise ValueError("invalid feature source range")
    # Entry logic, direction, stops, targets and risk do not change midpoint bars.
    # Indicator transforms have their own parameterized key below.
    return fingerprint(
        {
            "dataset": dataset_hash,
            "source_range": source_range,
            "timeframes": sorted({spec.timeframe, *spec.confirmations}),
            "code": code_revision,
            "instrument": instrument_hash,
            "time_policy": time_policy,
            "operator": "midpoint-bars/v2",
        }
    )


def indicator_key(bar_key, operator, parameters, implementation_version):
    return fingerprint(
        {
            "bars": bar_key,
            "operator": operator,
            "parameters": parameters,
            "implementation": implementation_version,
        }
    )


class BoundedCache:
    def __init__(self, max_bytes, max_entries=256):
        if type(max_bytes) is not int or max_bytes < 0:
            raise ValueError("invalid cache byte budget")
        if type(max_entries) is not int or not 1 <= max_entries <= 65536:
            raise ValueError("invalid cache entry budget")
        self.max_entries = max_entries
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
        if type(key) is not str or len(key) > 128:
            raise ValueError("invalid bounded cache key")
        value = np.asarray(value)
        if value.dtype.kind not in "biufcmM":
            raise ValueError("cache requires fixed-width numeric/time arrays")
        if key in self.entries:
            old = self.entries[key]
            if (
                old.dtype != value.dtype
                or old.shape != value.shape
                or old.tobytes(order="C") != value.tobytes(order="C")
            ):
                raise ValueError("immutable cache key collision")
            self.entries.move_to_end(key)
            return
        # Check size before the immutable copy; never allocate an oversized copy.
        if value.nbytes > self.max_bytes:
            return
        while self.bytes + value.nbytes > self.max_bytes or len(self.entries) >= self.max_entries:
            _, old = self.entries.popitem(last=False)
            self.bytes -= old.nbytes
            self.evictions += 1
        # Immutable bytes backing prevents callers from re-enabling writes.
        frozen = np.frombuffer(value.tobytes(order="C"), dtype=value.dtype).reshape(value.shape)
        self.entries[key] = frozen
        self.bytes += frozen.nbytes
