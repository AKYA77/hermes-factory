"""Checkpointed HistData decoding; only StreamingCatalog publishes datasets.

ZIP deflate cannot provide constant-time compressed seeks. A retry rechecks the
retained raw prefix without parsing it, then decodes only uncheckpointed rows.
Staged chunks are untrusted until checksummed/read back and the complete stream
passes the existing catalog verifier. They are never selectable datasets.
"""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid
import zipfile

import pyarrow as pa
import pyarrow.parquet as pq

from factory.contracts import fingerprint, serialize
from factory.data import Quote, SCHEMA, atomic_bytes, sha256
from factory.data import histdata
from factory.data.streaming import StreamingCatalog


def _save(path, state):
    encoded = serialize({"payload": state, "sha256": fingerprint(state)}).encode()
    if len(encoded) > 16 * 1024**2:
        raise ValueError("import checkpoint exceeds budget; increase batch rows in a new import")
    atomic_bytes(path, encoded)


def _load(path, intent):
    if path.stat().st_size > 16 * 1024**2:
        raise ValueError("import checkpoint exceeds budget")
    envelope = json.loads(path.read_text())
    state = envelope["payload"]
    if envelope["sha256"] != fingerprint(state) or state["intent"] != intent:
        raise ValueError("import checkpoint identity/checksum mismatch")
    if type(state["complete"]) is not bool or not isinstance(state["chunks"], list):
        raise ValueError("invalid import checkpoint")
    return state


def _read_lines(source, count):
    """Bound each read, including during raw prefix verification."""
    for _ in range(count):
        line = source.readline(4097)
        if not line:
            return
        if len(line) > 4096 or not line.strip():
            raise ValueError("source row exceeds cap or is empty")
        yield line


def _chunk_rows(path, expected_hash, expected_rows, start):
    if sha256(path) != expected_hash:
        raise ValueError("staged import chunk checksum mismatch")
    parquet = pq.ParquetFile(path)
    if parquet.schema_arrow != SCHEMA or parquet.metadata.num_rows != expected_rows:
        raise ValueError("staged import chunk schema/count mismatch")
    count = 0
    for batch in parquet.iter_batches(batch_size=8192):
        for raw in batch.to_pylist():
            q = Quote(**raw)
            if q.original_record_order != start + count:
                raise ValueError("staged import source sequence mismatch")
            count += 1
            yield q


def _write_chunk(root, rows):
    # A death before checkpoint publication leaves an orphan, never a prefix.
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=root)
    os.close(fd)
    path = Path(temporary)
    pq.write_table(
        pa.Table.from_pylist([q.__dict__ for q in rows], schema=SCHEMA),
        path,
        compression="zstd",
        compression_level=1,
    )
    with path.open("rb") as stream:
        os.fsync(stream.fileno())
    digest = sha256(path)
    destination = root / (digest + ".parquet")
    if destination.exists():
        if sha256(destination) != digest:
            raise ValueError("staged import content collision")
        path.unlink()
    else:
        os.rename(path, destination)
    # _save fsyncs this directory before making the checkpoint authoritative.
    return digest


def import_archive(catalog, manifest, provenance, batch_rows=8192):
    """Resume a retained archive. Return (unchanged data/v2 manifest, metrics)."""
    if type(batch_rows) is not int or not 1 <= batch_rows <= 65536:
        raise ValueError("batch_rows must be 1..65536")
    if not provenance.get("source") or not provenance.get("license"):
        raise ValueError("source/usage provenance is required")
    path = Path(manifest["archive"])
    if sha256(path) != manifest["sha256"]:
        raise ValueError("source checksum mismatch")
    member = histdata.inspect_archive(
        path, manifest["instrument"], manifest["year"], manifest["month"]
    )
    intent = {
        "schema": "histdata-import-checkpoint/v1",
        "source_sha256": manifest["sha256"],
        "member": member,
        "parser_version": histdata.PARSER_VERSION,
        "parser_source_sha256": sha256(histdata.__file__),
        "staging_source_sha256": sha256(__file__),
        "provenance": provenance,
        "batch_rows": batch_rows,
    }
    cat = StreamingCatalog(catalog)
    root = cat.root / ".imports" / fingerprint(intent)
    root.mkdir(parents=True, exist_ok=True)
    with (root / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        checkpoint = root / "checkpoint.json"
        state = (
            _load(checkpoint, intent)
            if checkpoint.exists()
            else {"intent": intent, "chunks": [], "complete": False}
        )
        if not checkpoint.exists():
            _save(checkpoint, state)
        reused = decoded = 0
        try:
            with zipfile.ZipFile(path) as archive, archive.open(member) as source:
                member_size = archive.getinfo(member).file_size
                previous = None
                for chunk in state["chunks"]:
                    count = chunk["rows"]
                    end = chunk["end_offset"]
                    digest = chunk["parquet_sha256"]
                    if (
                        type(count) is not int
                        or not 1 <= count <= batch_rows
                        or type(end) is not int
                        or not source.tell() < end <= member_size
                        or not isinstance(digest, str)
                        or len(digest) != 64
                        or any(c not in "0123456789abcdef" for c in digest)
                    ):
                        raise ValueError("invalid import chunk descriptor")
                    raw_hash = hashlib.sha256()
                    raw_count = 0
                    for line in _read_lines(source, count):
                        raw_hash.update(line)
                        raw_count += 1
                    if (
                        raw_count != count
                        or source.tell() != end
                        or raw_hash.hexdigest() != chunk["raw_sha256"]
                    ):
                        raise ValueError("import raw prefix mismatch")
                    for q in _chunk_rows(root / (digest + ".parquet"), digest, count, reused):
                        if previous and q.event_ts_utc_ns < previous.event_ts_utc_ns:
                            raise ValueError("staged import timestamp ordering mismatch")
                        previous = q
                    reused += count
                if state["complete"] and source.tell() != member_size:
                    raise ValueError("incomplete import marked complete")
                while not state["complete"]:
                    if shutil.disk_usage(cat.root).free < 256 * 1024**2:
                        raise ValueError("insufficient disk headroom; import prefix retained")
                    rows = []
                    raw_hash = hashlib.sha256()
                    for line in _read_lines(source, batch_rows):
                        q = histdata.parse_line(
                            line.decode("ascii"),
                            manifest["instrument"],
                            reused + decoded + len(rows),
                            manifest["sha256"],
                            (manifest["year"], manifest["month"]),
                        )
                        if q.bid_int > q.ask_int or (
                            previous and q.event_ts_utc_ns < previous.event_ts_utc_ns
                        ):
                            raise ValueError("QUARANTINED source spread/order")
                        raw_hash.update(line)
                        rows.append(q)
                        previous = q
                    if rows:
                        digest = _write_chunk(root, rows)
                        state["chunks"].append(
                            {
                                "rows": len(rows),
                                "end_offset": source.tell(),
                                "raw_sha256": raw_hash.hexdigest(),
                                "parquet_sha256": digest,
                            }
                        )
                        decoded += len(rows)
                    state["complete"] = source.tell() == member_size
                    _save(checkpoint, state)
            if sha256(path) != manifest["sha256"]:
                raise ValueError("raw source changed during checkpointed import")

            def staged_quotes():
                start = 0
                for chunk in state["chunks"]:
                    digest = chunk["parquet_sha256"]
                    yield from _chunk_rows(
                        root / (digest + ".parquet"), digest, chunk["rows"], start
                    )
                    start += chunk["rows"]

            result = cat.commit(
                staged_quotes(),
                path,
                provenance,
                batch_rows,
                expected_source_hash=manifest["sha256"],
            )
            return result, {
                "checkpoint_id": root.name,
                "rows_reused": reused,
                "rows_decoded": decoded,
                "chunks": len(state["chunks"]),
                "raw_prefix_rechecked": True,
                "http_range_resume": False,
            }
        except BaseException as exc:
            atomic_bytes(
                root / ("failure-" + uuid.uuid4().hex + ".json"),
                serialize(
                    {
                        "error": type(exc).__name__,
                        "reason": str(exc)[:1000],
                        "checkpoint_sha256": sha256(checkpoint),
                        "source_sha256": manifest["sha256"],
                    }
                ).encode(),
            )
            raise
