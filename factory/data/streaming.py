"""Memory-bounded structural verification and atomic canonical quote import.

This certifies reversible storage, not market completeness or strategy validity.
"""

from decimal import Decimal as D
import hashlib
import json
from math import gcd
import os
from pathlib import Path
import shutil
import struct
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq

from factory.contracts import fingerprint, serialize
from factory.data import Catalog, Quote, SCHEMA, atomic_bytes, sha256


def row_bytes(q):
    return struct.pack(">qqqq", q.event_ts_utc_ns, q.bid_int, q.ask_int, q.original_record_order)


def row_metadata(q):
    return {
        "instrument": q.instrument_id,
        "scale": q.price_scale,
        "source": q.source_id,
        "batch": q.ingest_batch_id,
        "precision": q.source_precision,
    }


class StreamingCatalog:
    def __init__(self, root):
        self.root = Path(root)
        self.catalog = Catalog(root)

    def commit(self, quotes, source_path, provenance, batch_rows=8192):
        if not 1 <= batch_rows <= 65536:
            raise ValueError("batch_rows must be 1..65536")
        if not provenance.get("source") or not provenance.get("license"):
            raise ValueError("source/usage provenance is required")
        if shutil.disk_usage(self.root).free < 256 * 1024**2:
            raise ValueError("insufficient disk headroom")
        source_path = Path(source_path)
        source_hash = sha256(source_path)
        pending = Path(tempfile.mkdtemp(prefix=".pending-", dir=self.root))
        writer = None
        try:
            digest = hashlib.sha256()
            count = 0
            rows = []
            previous = first = None
            metadata = None
            duplicates = gaps = 0
            gap_sample = []
            quantum = 0
            for q in quotes:
                if any(
                    type(v) is not int
                    for v in (
                        q.event_ts_utc_ns,
                        q.bid_int,
                        q.ask_int,
                        q.original_record_order,
                        q.price_scale,
                    )
                ):
                    raise ValueError("canonical integer fields required")
                if q.quality_flags or q.bid_int <= 0 or q.bid_int > q.ask_int:
                    raise ValueError(
                        f"QUARANTINED row {q.original_record_order}: invalid bid/ask/quality"
                    )
                if metadata is None:
                    metadata = row_metadata(q)
                    digest.update(serialize(metadata).encode())
                    first = q
                    writer = pq.ParquetWriter(
                        pending / "quotes.parquet", SCHEMA, compression="zstd", compression_level=1
                    )
                elif row_metadata(q) != metadata:
                    raise ValueError("mixed source/instrument units")
                if previous:
                    if (
                        q.original_record_order != previous.original_record_order + 1
                        or q.event_ts_utc_ns < previous.event_ts_utc_ns
                    ):
                        raise ValueError(
                            f"QUARANTINED row {q.original_record_order}: ordering/source sequence"
                        )
                    if (q.event_ts_utc_ns, q.bid_int, q.ask_int) == (
                        previous.event_ts_utc_ns,
                        previous.bid_int,
                        previous.ask_int,
                    ):
                        duplicates += 1
                    delta = q.event_ts_utc_ns - previous.event_ts_utc_ns
                    if delta > 60 * 10**9:
                        gaps += 1
                        if len(gap_sample) < 100:
                            gap_sample.append(
                                {
                                    "from_ns": previous.event_ts_utc_ns,
                                    "to_ns": q.event_ts_utc_ns,
                                    "status": "UNCLASSIFIED; calendar review required",
                                }
                            )
                quantum = gcd(quantum, gcd(q.bid_int, q.ask_int))
                digest.update(row_bytes(q))
                rows.append(q.__dict__)
                count += 1
                previous = q
                if len(rows) == batch_rows:
                    writer.write_table(
                        pa.Table.from_pylist(rows, schema=SCHEMA), row_group_size=batch_rows
                    )
                    rows.clear()
            if not count:
                raise ValueError("empty source partition")
            if rows:
                writer.write_table(
                    pa.Table.from_pylist(rows, schema=SCHEMA), row_group_size=batch_rows
                )
            writer.close()
            writer = None
            with (pending / "quotes.parquet").open("rb") as f:
                os.fsync(f.fileno())
            roundtrip = hashlib.sha256(serialize(metadata).encode())
            decoded_count = 0
            for batch in pq.ParquetFile(pending / "quotes.parquet").iter_batches(
                batch_size=batch_rows
            ):
                for raw in batch.to_pylist():
                    q = Quote(**raw)
                    if row_metadata(q) != metadata or q.quality_flags:
                        raise ValueError("roundtrip metadata mismatch")
                    roundtrip.update(row_bytes(q))
                    decoded_count += 1
            if count != decoded_count or roundtrip.hexdigest() != digest.hexdigest():
                raise ValueError("lossless roundtrip mismatch")
            with source_path.open("rb") as src, (pending / "source.bin").open("xb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
                dst.flush()
                os.fsync(dst.fileno())
            if sha256(pending / "source.bin") != source_hash:
                raise ValueError("raw source changed during import")
            identity = fingerprint(
                {
                    "schema": "data/v2",
                    "source": source_hash,
                    "quotes": digest.hexdigest(),
                    "provenance": provenance,
                }
            )
            manifest = {
                "schema_version": "data/v2",
                "dataset_hash": identity,
                "source_sha256": source_hash,
                "parquet_sha256": sha256(pending / "quotes.parquet"),
                "quote_stream_sha256": digest.hexdigest(),
                "rows": count,
                "first_ns": first.event_ts_utc_ns,
                "latest_verified_ns": previous.event_ts_utc_ns,
                "instrument": first.instrument_id,
                "provenance": provenance,
                "fidelity": "SYNTHETIC" if provenance.get("synthetic") else "SOURCE_BID_ASK",
                "price_scale": first.price_scale,
                "source_precision": first.source_precision,
                "source_id": first.source_id,
                "ingest_batch_id": first.ingest_batch_id,
                "batch_rows": batch_rows,
                "parquet_row_groups": pq.read_metadata(pending / "quotes.parquet").num_row_groups,
                "consecutive_exact_duplicates_retained": duplicates,
                "observed_price_quantum": str(D(quantum) / first.price_scale),
                "quantum_caveat": "empirical quote grid, not a verified instrument tick/pip specification",
                "gap_count_over_60s": gaps,
                "gap_sample": gap_sample,
                "quality_status": "STRUCTURAL_PASS_CALENDAR_REVIEW_REQUIRED",
                "readback_exact": True,
            }
            atomic_bytes(pending / "manifest.json", json.dumps(manifest, sort_keys=True).encode())
            destination = self.root / identity
            if destination.exists():
                existing = self.catalog.verify(identity)
                if existing["quote_stream_sha256"] != digest.hexdigest():
                    raise ValueError("immutable source collision")
                shutil.rmtree(pending)
                return existing
            os.rename(pending, destination)
            fd = os.open(self.root, os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            return self.catalog.verify(identity)
        except BaseException as exc:
            if writer is not None:
                writer.close()
            # Preserve partial output/source reference; no committed manifest exists.
            atomic_bytes(
                pending / "failure.json",
                json.dumps(
                    {"error": type(exc).__name__, "reason": str(exc), "source_sha256": source_hash}
                ).encode(),
            )
            raise
