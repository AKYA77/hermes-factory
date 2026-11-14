"""Exact closed-bar L2 cache; no approximate prices, signals or execution.

All missing timeframes share one canonical quote pass. Readers/writers hold a
local process lock; buffers, entry count and total disk use have hard budgets.
Cache failures fail the job rather than silently replacing canonical evidence.
"""

from contextlib import contextmanager
from decimal import Decimal
import fcntl
import heapq
import json
import os
from pathlib import Path
import shutil
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq

from factory.contracts import TIMEFRAMES, fingerprint, serialize
from factory.data import atomic_bytes, sha256
from factory.features import Bar, closed_bar_events
from factory.features.transforms import decimal_policy
from factory.provenance import execution_revision
from factory.simulation.ledger import EXECUTION_VERSION

SCHEMA = pa.schema(
    [
        ("end_ns", pa.int64()),
        ("available_at", pa.int64()),
        ("close", pa.string()),
        ("high", pa.string()),
        ("low", pa.string()),
    ]
)
POLICY = "midpoint-decimal-closed-first-later-bucket/v2"


class BarCache:
    def __init__(self, root, *, max_bytes=512 * 1024**2, max_entries=256, batch_rows=1024):
        if type(max_bytes) is not int or max_bytes < 4096:
            raise ValueError("invalid bar cache disk budget")
        if not 1 <= max_entries <= 4096 or not 1 <= batch_rows <= 8192:
            raise ValueError("invalid bar cache buffer/entry budget")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_bytes, self.max_entries, self.batch_rows = max_bytes, max_entries, batch_rows
        self.stats = {"hits": 0, "misses": 0, "evictions": 0, "quote_passes": 0}

    def _input(self, dataset, instrument, revision, timeframe, start_ns, end_ns, identity):
        if timeframe not in TIMEFRAMES or not all((dataset, instrument, revision)):
            raise ValueError("invalid bar cache identity")
        if start_ns is not None and end_ns is not None and start_ns >= end_ns:
            raise ValueError("invalid bar cache range")
        return {
            "dataset": dataset,
            "instrument": instrument,
            "revision": revision,
            "timeframe": timeframe,
            "start_ns": start_ns,
            "end_ns": end_ns,
            "policy": POLICY,
            "decimal": decimal_policy(),
            "code_revision": identity["code_revision"],
            "fill_version": identity["fill_version"],
        }

    def _verify(self, key, inputs):
        path = self.root / key
        if path.is_symlink() or any(
            (path / p).is_symlink() for p in ("bars.parquet", "manifest.json")
        ):
            raise ValueError("bar cache symlink forbidden")
        manifest = json.loads((path / "manifest.json").read_bytes())
        if manifest["inputs"] != inputs or fingerprint(manifest["inputs"]) != key:
            raise ValueError("bar cache identity mismatch")
        if sha256(path / "bars.parquet") != manifest["sha256"]:
            raise ValueError("bar cache checksum mismatch")
        source = pq.ParquetFile(path / "bars.parquet")
        if source.metadata.num_rows != manifest["rows"] or not source.schema_arrow.equals(SCHEMA):
            raise ValueError("bar cache schema/count mismatch")
        return manifest

    def _reserve(self, protected, staging_bytes=0, extra_entries=0):
        entries = [p for p in self.root.iterdir() if len(p.name) == 64 and p.is_dir()]
        if any(p.is_symlink() for p in entries):
            raise ValueError("bar cache symlink forbidden")
        sizes = {p: sum(f.stat().st_size for f in p.iterdir()) for p in entries}
        total = sum(sizes.values()) + staging_bytes
        count = len(entries) + extra_entries
        for path in sorted(entries, key=lambda p: (p.stat().st_mtime_ns, p.name)):
            if total <= self.max_bytes and count <= self.max_entries:
                break
            if path.name in protected:
                continue
            shutil.rmtree(path)
            total -= sizes[path]
            count -= 1
            self.stats["evictions"] += 1
        if total > self.max_bytes or count > self.max_entries:
            raise ValueError("BAR_CACHE_BUDGET: requested working set exceeds configured limit")

    @contextmanager
    def events(
        self,
        catalog,
        dataset,
        instrument,
        revision,
        timeframes,
        *,
        start_ns=None,
        end_ns=None,
        code_revision=None,
        fill_version=None,
    ):
        # Revalidate canonical bytes even for a cache hit, never trust mtimes.
        catalog.verify(dataset)
        frames = sorted(set(timeframes))
        if not frames or len(frames) > len(TIMEFRAMES):
            raise ValueError("invalid bar cache timeframes")
        # A data, code, fill or fold version change invalidates the cache; an
        # exact rerun reuses it. The revision defaults to the running source
        # identity so a commit cannot silently reuse a stale bar cache.
        identity = {
            "code_revision": code_revision or execution_revision(),
            "fill_version": fill_version or EXECUTION_VERSION,
        }
        inputs = {
            tf: self._input(dataset, instrument, revision, tf, start_ns, end_ns, identity)
            for tf in frames
        }
        keys = {tf: fingerprint(value) for tf, value in inputs.items()}
        with (self.root / ".lock").open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            # A killed builder publishes no manifest. Its private staging data
            # is disposable; authoritative quotes and previous entries survive.
            for stale in self.root.glob(".building-*"):
                if stale.is_symlink():
                    raise ValueError("bar cache symlink forbidden")
                shutil.rmtree(stale)
            missing = []
            for tf, key in keys.items():
                incomplete = self.root / key
                if (
                    incomplete.is_dir()
                    and not incomplete.is_symlink()
                    and not (incomplete / "manifest.json").exists()
                ):
                    shutil.rmtree(incomplete)
                if (self.root / key).exists():
                    self._verify(key, inputs[tf])
                    self.stats["hits"] += 1
                else:
                    missing.append(tf)
                    self.stats["misses"] += 1
            if missing:
                self._build(catalog, dataset, inputs, keys, missing, start_ns, end_ns)
            self._reserve(set(keys.values()))
            stream = self._merge(keys)
            try:
                yield stream
            finally:
                stream.close()

    def _build(self, catalog, dataset, inputs, keys, missing, start_ns, end_ns):
        self.stats["quote_passes"] += 1
        with tempfile.TemporaryDirectory(prefix=".building-", dir=self.root) as staging:
            stage = Path(staging)
            buffers = {tf: [] for tf in missing}
            rows = {tf: 0 for tf in missing}
            writers = {
                tf: pq.ParquetWriter(
                    stage / (tf + ".parquet"), SCHEMA, compression="zstd", compression_level=1
                )
                for tf in missing
            }

            def flush(tf):
                if buffers[tf]:
                    writers[tf].write_table(pa.Table.from_pylist(buffers[tf], schema=SCHEMA))
                    rows[tf] += len(buffers[tf])
                    buffers[tf].clear()
                self._reserve(
                    set(keys.values()), sum(p.stat().st_size for p in stage.iterdir()), len(missing)
                )

            try:
                for event in closed_bar_events(
                    catalog.read(dataset, start_ns=start_ns, end_ns=end_ns), missing
                ):
                    for tf, bar in event.items():
                        buffers[tf].append(
                            {
                                "end_ns": bar.end_ns,
                                "available_at": bar.available_at,
                                "close": str(bar.close),
                                "high": str(bar.high),
                                "low": str(bar.low),
                            }
                        )
                        if len(buffers[tf]) >= self.batch_rows:
                            flush(tf)
                for tf in missing:
                    flush(tf)
            finally:
                for writer in writers.values():
                    writer.close()
            self._reserve(
                set(keys.values()),
                sum(p.stat().st_size for p in stage.iterdir()) + 4096 * len(missing),
                len(missing),
            )
            catalog.verify(dataset)
            for tf in missing:
                dest = self.root / keys[tf]
                dest.mkdir()
                source = stage / (tf + ".parquet")
                with source.open("rb") as raw:
                    os.fsync(raw.fileno())
                # Manifest is the commit point. An interrupted move is removed
                # before reuse, rather than accepted as a complete cache entry.
                source.replace(dest / "bars.parquet")
                atomic_bytes(
                    dest / "manifest.json",
                    serialize(
                        {
                            "inputs": inputs[tf],
                            "rows": rows[tf],
                            "sha256": sha256(dest / "bars.parquet"),
                        }
                    ).encode(),
                )
                self._verify(keys[tf], inputs[tf])

    def _bars(self, key):
        previous = None
        for batch in pq.ParquetFile(self.root / key / "bars.parquet").iter_batches(
            batch_size=self.batch_rows
        ):
            for row in batch.to_pylist():
                bar = Bar(
                    row["end_ns"],
                    row["available_at"],
                    Decimal(row["close"]),
                    Decimal(row["high"]),
                    Decimal(row["low"]),
                )
                if (
                    previous is not None and bar.available_at <= previous
                ) or bar.end_ns > bar.available_at:
                    raise ValueError("invalid cached bar chronology")
                if (
                    not all(p.is_finite() for p in (bar.close, bar.high, bar.low))
                    or not bar.low <= bar.close <= bar.high
                ):
                    raise ValueError("invalid cached bar price")
                previous = bar.available_at
                yield bar

    def _merge(self, keys):
        heap = []
        readers = {tf: self._bars(key) for tf, key in keys.items()}
        for tf, reader in readers.items():
            bar = next(reader, None)
            if bar is not None:
                heapq.heappush(heap, (bar.available_at, tf, bar))
        while heap:
            timestamp = heap[0][0]
            event = {}
            while heap and heap[0][0] == timestamp:
                _, tf, bar = heapq.heappop(heap)
                event[tf] = bar
                bar = next(readers[tf], None)
                if bar is not None:
                    heapq.heappush(heap, (bar.available_at, tf, bar))
            yield event
