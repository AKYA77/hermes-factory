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
import time
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


def _load(path, intent=None):
    if path.stat().st_size > 16 * 1024**2:
        raise ValueError("import checkpoint exceeds budget")
    envelope = json.loads(path.read_text())
    state = envelope["payload"]
    if envelope["sha256"] != fingerprint(state) or (
        intent is not None and state["intent"] != intent
    ):
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


def _payload_bytes(root):
    """Count retained payload, including interrupted writes; never follow links."""
    total = count = 0
    for folder, directories, files in os.walk(root):
        for name in directories + files:
            path = Path(folder) / name
            if path.is_symlink():
                raise ValueError("staging symlink requires operator review")
            count += 1
            if count > 100000:
                raise ValueError("staging inventory exceeds entry budget")
        for name in files:
            # atomic_bytes can leave an unnamed temporary on SIGKILL. Count
            # unknown retained files conservatively, not just known suffixes.
            if not name.endswith(".json") and name not in ("lock", "payload-budget.lock"):
                total += (Path(folder) / name).stat().st_size
    return total


def _budgeted_chunk(root, rows, budget):
    # Serialize payload admission across all import intents in this catalog.
    with (root.parent / "payload-budget.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        sink = pa.BufferOutputStream()
        pq.write_table(
            pa.Table.from_pylist([q.__dict__ for q in rows], schema=SCHEMA),
            sink,
            compression="zstd",
            compression_level=1,
        )
        data = sink.getvalue()
        digest = hashlib.sha256(data).hexdigest()
        destination = root / (digest + ".parquet")
        if destination.exists():
            if sha256(destination) != digest:
                raise ValueError("staged import content collision")
            return digest
        if _payload_bytes(root.parent) + len(data) > budget:
            raise ValueError("staging payload budget exceeded; verified prefixes retained")
        # Known bounded compressed bytes are checked before writing. Audit and
        # checkpoint metadata are separately capped and not evicted by this quota.
        atomic_bytes(destination, data.to_pybytes())
        return digest


def _published(catalog, state):
    receipt = state.get("published")
    if not state["complete"] or not isinstance(receipt, dict):
        raise ValueError("staging has no verified publication receipt")
    identity = receipt.get("dataset_hash", "")
    if (
        not isinstance(identity, str)
        or len(identity) != 64
        or any(c not in "0123456789abcdef" for c in identity)
    ):
        raise ValueError("invalid published dataset identity")
    manifest = catalog.catalog.verify(identity, deep=True)
    if (
        manifest["source_sha256"] != state["intent"]["source_sha256"]
        or manifest["provenance"] != state["intent"]["provenance"]
        or sha256(catalog.root / identity / "manifest.json") != receipt["manifest_sha256"]
    ):
        raise ValueError("staged publication evidence mismatch")
    return manifest


def reclaim(catalog, checkpoint_id):
    """Explicitly reclaim verified duplicate chunks; preserve source and failures.

    The durable marker precedes unlink, so a crash during reclamation is safe to
    retry. No uncheckpointed orphan, failure evidence or canonical file is removed.
    """
    if (
        not isinstance(checkpoint_id, str)
        or len(checkpoint_id) != 64
        or any(c not in "0123456789abcdef" for c in checkpoint_id)
    ):
        raise ValueError("invalid import checkpoint identity")
    cat = StreamingCatalog(catalog)
    root = cat.root / ".imports" / checkpoint_id
    if root.parent.is_symlink() or root.is_symlink():
        raise ValueError("staging symlink requires operator review")
    with (root / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        checkpoint = root / "checkpoint.json"
        state = _load(checkpoint)
        if fingerprint(state["intent"]) != checkpoint_id:
            raise ValueError("import checkpoint namespace mismatch")
        result = _published(cat, state)
        paths = []
        for chunk in state["chunks"]:
            digest = chunk["parquet_sha256"]
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)
            ):
                raise ValueError("invalid staged chunk identity")
            path = root / (digest + ".parquet")
            if path.is_symlink():
                raise ValueError("staging symlink requires operator review")
            if path.exists():
                if sha256(path) != digest:
                    raise ValueError("corrupt staged chunk retained for review")
                paths.append(path)
            elif not state.get("chunks_reclaimed"):
                raise ValueError("missing staged chunk retained for review")
        request_id = uuid.uuid4().hex
        atomic_bytes(
            root / ("reclaim-request-" + request_id + ".json"),
            serialize(
                {
                    "request_id": request_id,
                    "requested_at_ns": time.time_ns(),
                    "dataset_hash": result["dataset_hash"],
                    "checkpoint_sha256": sha256(checkpoint),
                    "planned_chunks": len(paths),
                    "actor": "trusted-local-operator",
                }
            ).encode(),
        )
        state["chunks_reclaimed"] = True
        _save(checkpoint, state)
        removed = 0
        with (root.parent / "payload-budget.lock").open("a") as budget_lock:
            fcntl.flock(budget_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for path in paths:
                removed += path.stat().st_size
                path.unlink()
        fd = os.open(root, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        receipt = {
            "request_id": request_id,
            "checkpoint_id": checkpoint_id,
            "dataset_hash": result["dataset_hash"],
            "reclaimed_payload_bytes": removed,
            "removed_chunks": len(paths),
            "canonical_source_and_evidence_preserved": True,
        }
        atomic_bytes(root / ("reclaim-result-" + request_id + ".json"), serialize(receipt).encode())
        return receipt


def import_archive(catalog, manifest, provenance, batch_rows=8192, *, staging_budget_bytes=2**31):
    """Resume a retained archive. Return (unchanged data/v2 manifest, metrics)."""
    if type(batch_rows) is not int or not 1 <= batch_rows <= 65536:
        raise ValueError("batch_rows must be 1..65536")
    if type(staging_budget_bytes) is not int or not 1 <= staging_budget_bytes <= 128 * 1024**3:
        raise ValueError("staging payload budget must be 1..128GiB")
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
    if root.parent.is_symlink() or root.is_symlink():
        raise ValueError("staging symlink requires operator review")
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
            if state.get("chunks_reclaimed"):
                result = _published(cat, state)
                return result, {
                    "checkpoint_id": root.name,
                    "rows_reused": result["rows"],
                    "rows_decoded": 0,
                    "chunks": len(state["chunks"]),
                    "staging_reclaimed": True,
                    "raw_prefix_rechecked": False,
                    "canonical_deep_verified": True,
                    "staging_payload_budget_bytes": staging_budget_bytes,
                    "http_range_resume": False,
                }
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
                        digest = _budgeted_chunk(root, rows, staging_budget_bytes)
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
            state["published"] = {
                "dataset_hash": result["dataset_hash"],
                "manifest_sha256": sha256(cat.root / result["dataset_hash"] / "manifest.json"),
            }
            _save(checkpoint, state)
            return result, {
                "checkpoint_id": root.name,
                "rows_reused": reused,
                "rows_decoded": decoded,
                "chunks": len(state["chunks"]),
                "raw_prefix_rechecked": True,
                "staging_payload_budget_bytes": staging_budget_bytes,
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
