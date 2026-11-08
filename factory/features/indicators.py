"""Bounded exact indicator L2, with source verification and atomic publication.

Lock order is indicator -> bar. Only disposable feature entries are evicted;
canonical quotes, experiment results and source evidence are never removed.
"""

from collections import deque
from contextlib import contextmanager
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import shutil
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq

from factory.contracts import fingerprint, serialize
from factory.data import atomic_bytes, sha256
from factory.features.disk import BarCache
from factory.features.transforms import FIELDS, VERSION, decimal_policy, groups_for, primitives
from factory.provenance import execution_revision
from factory.simulation.ledger import EXECUTION_VERSION

SCHEMA = pa.schema(
    [("end_ns", pa.int64()), ("available_at", pa.int64()), ("values", pa.list_(pa.string()))]
)


class IndicatorCache(BarCache):
    """Reuse bar-cache bounded disk reservation; manifests/schema are independent."""

    def __init__(self, root, *, max_bytes=256 * 1024**2, max_entries=256, batch_rows=1024):
        super().__init__(root, max_bytes=max_bytes, max_entries=max_entries, batch_rows=batch_rows)
        self.stats = {"hits": 0, "misses": 0, "evictions": 0, "bar_passes": 0}

    def _verify(self, key, inputs):
        path = self.root / key
        if path.is_symlink() or any(
            (path / p).is_symlink() for p in ("values.parquet", "manifest.json")
        ):
            raise ValueError("indicator cache symlink forbidden")
        manifest = json.loads((path / "manifest.json").read_bytes())
        if manifest["inputs"] != inputs or fingerprint(inputs) != key:
            raise ValueError("indicator cache identity mismatch")
        if sha256(path / "values.parquet") != manifest["sha256"]:
            raise ValueError("indicator cache checksum mismatch")
        source = pq.ParquetFile(path / "values.parquet")
        if source.metadata.num_rows != manifest["rows"] or not source.schema_arrow.equals(SCHEMA):
            raise ValueError("indicator cache schema/count mismatch")
        return manifest

    @contextmanager
    def events(
        self,
        catalog,
        dataset,
        instrument,
        revision,
        spec,
        bar_cache,
        *,
        start_ns=None,
        end_ns=None,
        code_revision=None,
        fill_version=None,
    ):
        catalog.verify(dataset)
        context = decimal_policy()
        groups = groups_for(spec.signal)
        identity = {
            "code_revision": code_revision or execution_revision(),
            "fill_version": fill_version or EXECUTION_VERSION,
        }
        inputs = {
            group: {
                "bars": bar_cache._input(
                    dataset, instrument, revision, spec.timeframe, start_ns, end_ns, identity
                ),
                "group": group,
                "lookback": spec.signal.lookback,
                "formula": VERSION,
                "decimal": context,
            }
            for group in groups
        }
        keys = {group: fingerprint(value) for group, value in inputs.items()}
        with (self.root / ".lock").open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            for stale in self.root.glob(".building-*"):
                if stale.is_symlink():
                    raise ValueError("indicator cache symlink forbidden")
                shutil.rmtree(stale)
            missing = []
            for group, key in keys.items():
                path = self.root / key
                if (
                    path.is_dir()
                    and not path.is_symlink()
                    and not (path / "manifest.json").exists()
                ):
                    shutil.rmtree(path)
                if path.exists():
                    self._verify(key, inputs[group])
                    self.stats["hits"] += 1
                else:
                    missing.append(group)
                    self.stats["misses"] += 1
            if missing:
                self._build(
                    catalog,
                    dataset,
                    instrument,
                    revision,
                    spec,
                    bar_cache,
                    inputs,
                    keys,
                    missing,
                    start_ns,
                    end_ns,
                )
            self._reserve(set(keys.values()))
            readers = {group: self._values(key, group) for group, key in keys.items()}

            def lookup(bar):
                if decimal_policy() != context:
                    raise ValueError("indicator Decimal context changed")
                values = {}
                for group, reader in readers.items():
                    row = next(reader, None)
                    if row is None or row[0] != (bar.end_ns, bar.available_at):
                        raise ValueError("indicator chronology/alignment mismatch")
                    values.update(row[1])
                return values

            try:
                with bar_cache.events(
                    catalog,
                    dataset,
                    instrument,
                    revision,
                    (spec.timeframe, *spec.confirmations),
                    start_ns=start_ns,
                    end_ns=end_ns,
                ) as events:
                    yield events, lookup
            finally:
                for reader in readers.values():
                    reader.close()

    def _build(
        self,
        catalog,
        dataset,
        instrument,
        revision,
        spec,
        bar_cache,
        inputs,
        keys,
        missing,
        start_ns,
        end_ns,
    ):
        self.stats["bar_passes"] += 1
        with tempfile.TemporaryDirectory(prefix=".building-", dir=self.root) as staging:
            stage = Path(staging)
            buffers, rows = {g: [] for g in missing}, {g: 0 for g in missing}
            writers = {
                g: pq.ParquetWriter(
                    stage / (g + ".parquet"), SCHEMA, compression="zstd", compression_level=1
                )
                for g in missing
            }

            def flush(group):
                if buffers[group]:
                    writers[group].write_table(pa.Table.from_pylist(buffers[group], schema=SCHEMA))
                    rows[group] += len(buffers[group])
                    buffers[group].clear()
                self._reserve(
                    set(keys.values()), sum(p.stat().st_size for p in stage.iterdir()), len(missing)
                )

            history = deque(maxlen=spec.signal.lookback)
            try:
                with bar_cache.events(
                    catalog,
                    dataset,
                    instrument,
                    revision,
                    (spec.timeframe,),
                    start_ns=start_ns,
                    end_ns=end_ns,
                ) as events:
                    for event in events:
                        bar = event[spec.timeframe]
                        if len(history) == history.maxlen:
                            values = primitives(history, missing)
                            for group in missing:
                                buffers[group].append(
                                    {
                                        "end_ns": bar.end_ns,
                                        "available_at": bar.available_at,
                                        "values": [str(values[k]) for k in FIELDS[group]],
                                    }
                                )
                                if len(buffers[group]) >= self.batch_rows:
                                    flush(group)
                        history.append(bar)
                for group in missing:
                    flush(group)
            finally:
                for writer in writers.values():
                    writer.close()
            self._reserve(
                set(keys.values()),
                sum(p.stat().st_size for p in stage.iterdir()) + 4096 * len(missing),
                len(missing),
            )
            catalog.verify(dataset)
            for group in missing:
                dest = self.root / keys[group]
                dest.mkdir()
                source = stage / (group + ".parquet")
                with source.open("rb") as raw:
                    os.fsync(raw.fileno())
                source.replace(dest / "values.parquet")
                atomic_bytes(
                    dest / "manifest.json",
                    serialize(
                        {
                            "inputs": inputs[group],
                            "rows": rows[group],
                            "sha256": sha256(dest / "values.parquet"),
                        }
                    ).encode(),
                )
                self._verify(keys[group], inputs[group])

    def _values(self, key, group):
        previous = None
        source = pq.ParquetFile(self.root / key / "values.parquet")
        try:
            for batch in source.iter_batches(batch_size=self.batch_rows):
                for row in batch.to_pylist():
                    timestamp = row["end_ns"], row["available_at"]
                    values = [Decimal(v) for v in row["values"]]
                    if len(values) != len(FIELDS[group]) or not all(v.is_finite() for v in values):
                        raise ValueError("invalid cached indicator values")
                    if timestamp[0] > timestamp[1] or (
                        previous is not None
                        and (timestamp[0] <= previous[0] or timestamp[1] <= previous[1])
                    ):
                        raise ValueError("invalid cached indicator chronology")
                    previous = timestamp
                    yield timestamp, dict(zip(FIELDS[group], values, strict=True))
        finally:
            source.close()


def use_indicator_cache(spec):
    """Conservative feature-only adoption policy from the generated benchmark.

    Short histories were slower, so retain direct primitives. This is an
    engineering choice, never a candidate-quality filter or a throughput promise.
    """
    return spec.signal.lookback >= 64 and spec.signal.operator in ("mean_reversion", "trend")


@contextmanager
def compiler_events(
    bar_cache, catalog, dataset, instrument, revision, spec, *, start_ns=None, end_ns=None
):
    if use_indicator_cache(spec):
        cache = IndicatorCache(bar_cache.root.parent / "indicators")
        with cache.events(
            catalog,
            dataset,
            instrument,
            revision,
            spec,
            bar_cache,
            start_ns=start_ns,
            end_ns=end_ns,
        ) as result:
            yield result
    else:
        with bar_cache.events(
            catalog,
            dataset,
            instrument,
            revision,
            (spec.timeframe, *spec.confirmations),
            start_ns=start_ns,
            end_ns=end_ns,
        ) as events:
            yield events, None
