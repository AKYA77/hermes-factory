"""Lossless canonical quote storage. Immutable source bytes and exact integers."""

from dataclasses import dataclass, asdict
from collections import OrderedDict
from pathlib import Path
import hashlib
import json
import os
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq

from factory.contracts import fingerprint, serialize


@dataclass(frozen=True)
class Quote:
    instrument_id: str
    event_ts_utc_ns: int
    bid_int: int
    ask_int: int
    price_scale: int
    source_id: str
    ingest_batch_id: str
    original_record_order: int
    source_precision: str = "millisecond"
    quality_flags: str = ""

    def __post_init__(self):
        if self.price_scale <= 0 or self.event_ts_utc_ns < 0:
            raise ValueError("invalid scale/time")


SCHEMA = pa.schema(
    [
        ("instrument_id", pa.string()),
        ("event_ts_utc_ns", pa.int64()),
        ("bid_int", pa.int64()),
        ("ask_int", pa.int64()),
        ("price_scale", pa.int64()),
        ("source_id", pa.string()),
        ("ingest_batch_id", pa.string()),
        ("original_record_order", pa.int64()),
        ("source_precision", pa.string()),
        ("quality_flags", pa.string()),
    ]
)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        dfd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def quality(quotes):
    issues = []
    previous = None
    seen = set()
    for q in quotes:
        key = (q.event_ts_utc_ns, q.original_record_order)
        if q.bid_int > q.ask_int or q.bid_int <= 0 or q.quality_flags:
            issues.append({"order": q.original_record_order, "reason": "CORRUPT_QUOTE"})
        if previous is not None and key < previous:
            issues.append({"order": q.original_record_order, "reason": "OUT_OF_ORDER"})
        if key in seen:
            issues.append({"order": q.original_record_order, "reason": "DUPLICATE_SEQUENCE"})
        seen.add(key)
        previous = key
    return issues


class Catalog:
    def __init__(self, root, *, proof_cache_size=32):
        if not 0 <= proof_cache_size <= 128:
            raise ValueError("invalid verification proof cache budget")
        self.proof_cache_size = proof_cache_size
        self._verification_proofs = OrderedDict()
        self.verification_cache_hits = self.verification_scans = 0
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def commit(self, quotes, source_bytes, provenance):
        quotes = list(quotes)
        if not quotes:
            raise ValueError("empty partition")
        issues = quality(quotes)
        if issues:
            key = fingerprint(
                {"source": hashlib.sha256(source_bytes).hexdigest(), "issues": issues}
            )
            atomic_bytes(self.root / "quarantine" / f"{key}.json", json.dumps(issues).encode())
            raise ValueError(f"QUARANTINED: {issues}")
        if len({(q.instrument_id, q.price_scale, q.source_precision) for q in quotes}) != 1:
            raise ValueError("partition units mixed")
        if not provenance.get("license") or not provenance.get("source"):
            raise ValueError("source/license metadata required")
        raw_hash = hashlib.sha256(source_bytes).hexdigest()
        identity = fingerprint(
            {
                "quotes": [asdict(q) for q in quotes],
                "raw": raw_hash,
                "provenance": provenance,
                "schema": "quotes/v1",
            }
        )
        dest = self.root / identity
        manifest_path = dest / "manifest.json"
        if manifest_path.exists():
            return self.verify(identity)
        dest.mkdir(exist_ok=True)
        atomic_bytes(dest / "source.bin", source_bytes)
        tmp = dest / "quotes.parquet.pending"
        pq.write_table(
            pa.Table.from_pylist([asdict(q) for q in quotes], schema=SCHEMA),
            tmp,
            compression="zstd",
            compression_level=1,
        )
        with tmp.open("rb") as f:
            os.fsync(f.fileno())
        if pq.read_table(tmp).to_pylist() != [asdict(q) for q in quotes]:
            raise ValueError("roundtrip mismatch")
        os.replace(tmp, dest / "quotes.parquet")
        manifest = {
            "schema_version": "data/v1",
            "dataset_hash": identity,
            "source_sha256": raw_hash,
            "parquet_sha256": sha256(dest / "quotes.parquet"),
            "rows": len(quotes),
            "first_ns": quotes[0].event_ts_utc_ns,
            "latest_verified_ns": quotes[-1].event_ts_utc_ns,
            "instrument": quotes[0].instrument_id,
            "provenance": provenance,
            "fidelity": "SYNTHETIC" if provenance.get("synthetic") else "REAL_BID_ASK",
        }
        atomic_bytes(manifest_path, json.dumps(manifest, sort_keys=True).encode())
        return self.verify(identity)

    def verify(self, identity, *, deep=False):
        if len(identity) != 64 or any(c not in "0123456789abcdef" for c in identity):
            raise ValueError("invalid dataset hash")
        dest = self.root / identity
        if dest.is_symlink() or any(
            (dest / name).is_symlink() for name in ("manifest.json", "source.bin", "quotes.parquet")
        ):
            raise ValueError("canonical source symlink forbidden")
        manifest_bytes = (dest / "manifest.json").read_bytes()
        m = json.loads(manifest_bytes)
        if m.get("dataset_hash") != identity or m.get("schema_version") not in (
            "data/v1",
            "data/v2",
        ):
            raise ValueError("dataset manifest identity mismatch")
        raw_hash, parquet_hash = sha256(dest / "source.bin"), sha256(dest / "quotes.parquet")
        if raw_hash != m["source_sha256"] or parquet_hash != m["parquet_sha256"]:
            raise ValueError("CORRUPT_PARTITION")
        # Every lookup rehashes ALL input bytes. A prior semantic proof applies
        # only to the identical namespace + manifest + raw + Parquet byte tuple.
        # Do not replace this with an mtime-only fast path or persisted trust flag.
        proof_key = (identity, hashlib.sha256(manifest_bytes).hexdigest(), raw_hash, parquet_hash)
        needs_semantics = deep or m["schema_version"] == "data/v1"
        cached = self._verification_proofs.get(proof_key)
        if cached is not None and (cached or not needs_semantics):
            self.verification_cache_hits += 1
            self._verification_proofs.move_to_end(proof_key)
            return m
        self.verification_scans += 1
        source = pq.ParquetFile(dest / "quotes.parquet")
        if source.metadata.num_rows != m["rows"] or not m["rows"]:
            raise ValueError("row count mismatch")
        if not source.schema_arrow.equals(SCHEMA):
            raise ValueError("canonical quote schema mismatch")
        if m["schema_version"] == "data/v2":
            expected = fingerprint(
                {
                    "schema": "data/v2",
                    "source": m["source_sha256"],
                    "quotes": m["quote_stream_sha256"],
                    "provenance": m["provenance"],
                }
            )
            if expected != identity:
                raise ValueError("dataset content/provenance identity mismatch")
            if deep:
                from factory.data.streaming import row_bytes, row_metadata

                metadata = None
                digest = None
                for batch in source.iter_batches(batch_size=8192):
                    for row in batch.to_pylist():
                        q = Quote(**row)
                        if metadata is None:
                            metadata = row_metadata(q)
                            digest = hashlib.sha256(serialize(metadata).encode())
                        if row_metadata(q) != metadata or q.quality_flags:
                            raise ValueError("canonical quote metadata mismatch")
                        digest.update(row_bytes(q))
                if digest.hexdigest() != m["quote_stream_sha256"]:
                    raise ValueError("canonical quote stream identity mismatch")
        else:
            # Reproduce quotes/v1's canonical object without materializing its
            # quotes array. This also binds legacy provenance to the dataset ID.
            digest = hashlib.sha256(
                b'{"provenance":' + serialize(m["provenance"]).encode() + b',"quotes":['
            )
            first = True
            for batch in source.iter_batches(batch_size=8192):
                for row in batch.to_pylist():
                    if not first:
                        digest.update(b",")
                    digest.update(serialize(row).encode())
                    first = False
            digest.update(
                b'],"raw":' + serialize(m["source_sha256"]).encode() + b',"schema":"quotes/v1"}'
            )
            if digest.hexdigest() != identity:
                raise ValueError("legacy dataset content/provenance identity mismatch")
        if self.proof_cache_size:
            self._verification_proofs[proof_key] = needs_semantics
            self._verification_proofs.move_to_end(proof_key)
            while len(self._verification_proofs) > self.proof_cache_size:
                self._verification_proofs.popitem(last=False)
        return m

    def read(self, identity, *, start_ns=None, end_ns=None, batch_rows=8192):
        """Verified bounded reads with row-group pruning and exact half-open bounds."""
        if not 1 <= batch_rows <= 65536:
            raise ValueError("invalid read batch size")
        if start_ns is not None and end_ns is not None and start_ns >= end_ns:
            raise ValueError("empty/reversed read range")
        self.verify(identity)
        source = pq.ParquetFile(self.root / identity / "quotes.parquet")
        column = SCHEMA.get_field_index("event_ts_utc_ns")
        groups = []
        for index in range(source.metadata.num_row_groups):
            statistics = source.metadata.row_group(index).column(column).statistics
            if statistics and statistics.has_min_max:
                if start_ns is not None and statistics.max < start_ns:
                    continue
                if end_ns is not None and statistics.min >= end_ns:
                    continue
            groups.append(index)
        for batch in source.iter_batches(batch_size=batch_rows, row_groups=groups):
            for row in batch.to_pylist():
                ts = row["event_ts_utc_ns"]
                if (start_ns is None or ts >= start_ns) and (end_ns is None or ts < end_ns):
                    yield Quote(**row)
