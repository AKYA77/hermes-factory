"""Bounded reversible numeric replay spool; canonical archives remain immutable.

A transient 32-byte record per quote avoids keeping Python Quote/QuoteTick objects
for an entire history. It also supplies exact source offsets for forensic reads.
Nautilus' supported data iterator consumes bounded batches without splitting its
single event loop at timestamp ties. This is not a matching implementation.
"""

from decimal import Decimal as D
import struct
import shutil
import tempfile

RECORD = struct.Struct("<qqqq")  # UTC ns, exact bid/ask integers, original row order


class QuoteSpool:
    def __init__(self, quotes, profile, *, directory=None, max_bytes=4 * 1024**3):
        if max_bytes < RECORD.size:
            raise ValueError("invalid spool budget")
        disk = directory or tempfile.gettempdir()
        if shutil.disk_usage(disk).free < 256 * 1024**2:
            raise ValueError("REPLAY_DISK_RESERVE")
        self.file = tempfile.TemporaryFile(dir=directory)
        self.count = 0
        self.first_ns = self.last_ns = None
        self.scale = profile.price_scale
        previous = None
        units = None
        tick_int = profile.tick_size * profile.price_scale
        try:
            block = bytearray()
            for q in quotes:
                key = (q.event_ts_utc_ns, q.original_record_order)
                identity = (q.source_id, q.ingest_batch_id, q.source_precision)
                if units is None:
                    units = identity
                if (
                    q.instrument_id != profile.instrument
                    or q.price_scale != self.scale
                    or units != identity
                ):
                    raise ValueError("quote units/source mismatch")
                if (
                    q.bid_int <= 0
                    or q.bid_int > q.ask_int
                    or q.quality_flags
                    or q.original_record_order < 0
                    or (previous is not None and key <= previous)
                ):
                    raise ValueError("invalid quote stream")
                if D(q.bid_int) % tick_int or D(q.ask_int) % tick_int:
                    raise ValueError("quote off instrument tick grid; rounding forbidden")
                previous = key
                block.extend(
                    RECORD.pack(q.event_ts_utc_ns, q.bid_int, q.ask_int, q.original_record_order)
                )
                if self.first_ns is None:
                    self.first_ns = q.event_ts_utc_ns
                self.last_ns = q.event_ts_utc_ns
                self.count += 1
                if self.count * RECORD.size > max_bytes:
                    raise ValueError("REPLAY_SPOOL_BUDGET")
                if len(block) >= RECORD.size * 8192:
                    if shutil.disk_usage(disk).free < len(block) + 256 * 1024**2:
                        raise ValueError("REPLAY_DISK_RESERVE")
                    self.file.write(block)
                    block.clear()
            if block:
                self.file.write(block)
            if not self.count:
                raise ValueError("no quotes")
            self.file.flush()
        except BaseException:
            self.file.close()
            raise

    def row(self, index):
        if not 0 <= index < self.count:
            raise IndexError(index)
        self.file.seek(index * RECORD.size)
        return RECORD.unpack(self.file.read(RECORD.size))

    def rows(self, start=0, stop=None, *, batch_rows=8192):
        stop = self.count if stop is None else stop
        if not 0 <= start <= stop <= self.count or not 1 <= batch_rows <= 65536:
            raise ValueError("invalid spool range/batch")
        for offset in range(start, stop, batch_rows):
            self.file.seek(offset * RECORD.size)
            block = self.file.read(min(batch_rows, stop - offset) * RECORD.size)
            yield from RECORD.iter_unpack(block)

    def close(self):
        self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class BoundedRecords(list):
    """Fail explicitly before unbounded result/native-order growth, never truncate.

    The scheduler must partition a job or report its capacity failure. It may not
    mark a partially simulated history complete. Limits are not pruning rules.
    """

    def __init__(self, limit=50000):
        super().__init__()
        self.limit = limit

    def append(self, value):
        if len(self) >= self.limit:
            raise ValueError("REPLAY_RESULT_BUDGET")
        super().append(value)
