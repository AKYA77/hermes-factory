"""Bounded exact source-position comparison; no invented alignment or fills.

Positions are the provider's original capture sequence. An inserted row can shift
many subsequent positions: CHANGED is not a claim about market causality.
"""

import hashlib
from itertools import zip_longest
import json
import os
from pathlib import Path
import shutil
import tempfile
import time

from factory.contracts import fingerprint, serialize
from factory.data import atomic_bytes, sha256
from factory.provenance import execution_revision


def compare_sources(versions, left_id, right_id, *, max_events_bytes=64 * 1024**2):
    if type(max_events_bytes) is not int or not 1024 <= max_events_bytes <= 1024**3:
        raise ValueError("source comparison event budget requires 1 KiB..1 GiB")
    left, right = (versions.observation(key) for key in (left_id, right_id))
    if left["slot"] != right["slot"]:
        raise ValueError("source comparison requires the same declared source slot")
    inputs = {
        "schema_version": "source-position-diff/v1",
        "left_observation": left_id,
        "right_observation": right_id,
        "max_events_bytes": max_events_bytes,
        "code_revision": execution_revision(),
    }
    identity = fingerprint(inputs)
    directory = versions.root / "artifacts" / "source-comparisons"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / identity
    cached = versions.store.rows(
        "SELECT * FROM source_comparisons WHERE comparison_id=?", (identity,)
    )
    if cached:
        stored = cached[0]
        if (
            destination.is_symlink()
            or (destination / "events.jsonl").is_symlink()
            or (destination / "report.json").is_symlink()
            or stored["inputs_json"] != serialize(inputs)
            or sha256(destination / "report.json") != stored["report_sha256"]
            or (destination / "report.json").read_text() != stored["report_json"]
            or sha256(destination / "events.jsonl") != stored["events_sha256"]
        ):
            raise ValueError("SOURCE_COMPARISON_ARTIFACT_MISMATCH")
        return json.loads(stored["report_json"])
    if shutil.disk_usage(directory).free < 256 * 1024**2:
        raise ValueError("SOURCE_COMPARISON_DISK_RESERVE")
    staging = Path(tempfile.mkdtemp(prefix=".pending-", dir=directory))
    atomic_bytes(staging / "inputs.json", serialize(inputs).encode())
    counts = {
        "left_rows": 0,
        "right_rows": 0,
        "unchanged_positions": 0,
        "changed_positions": 0,
        "left_only_positions": 0,
        "right_only_positions": 0,
    }
    size = 0

    def exact(q):
        if q is None:
            return None
        # Different archive capture/batch identity alone is not a quote change.
        return {
            "ts": q.event_ts_utc_ns,
            "source_record_order": q.original_record_order,
            "bid_int": q.bid_int,
            "ask_int": q.ask_int,
            "price_scale": q.price_scale,
            "source_id": q.source_id,
            "instrument": q.instrument_id,
            "source_precision": q.source_precision,
            "quality_flags": q.quality_flags,
        }

    try:
        with (staging / "events.jsonl").open("wb") as stream:
            for position, pair in enumerate(
                zip_longest(
                    versions.catalog.read(left["dataset_hash"]),
                    versions.catalog.read(right["dataset_hash"]),
                )
            ):
                a, b = (exact(q) for q in pair)
                counts["left_rows"] += a is not None
                counts["right_rows"] += b is not None
                if a == b:
                    counts["unchanged_positions"] += 1
                    continue
                kind = (
                    "left_only_positions"
                    if b is None
                    else "right_only_positions"
                    if a is None
                    else "changed_positions"
                )
                counts[kind] += 1
                encoded = (serialize({"position": position, "left": a, "right": b}) + "\n").encode()
                if size + len(encoded) > max_events_bytes:
                    raise ValueError("SOURCE_COMPARISON_EVENT_BUDGET")
                if size // 1024**2 != (size + len(encoded)) // 1024**2 and shutil.disk_usage(
                    directory
                ).free < 256 * 1024**2 + len(encoded):
                    raise ValueError("SOURCE_COMPARISON_DISK_RESERVE")
                stream.write(encoded)
                size += len(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        for value, name in ((left, "left_rows"), (right, "right_rows")):
            manifest = versions.catalog.verify(value["dataset_hash"])
            if (
                fingerprint(manifest) != value["manifest_sha256"]
                or counts[name] != manifest["rows"]
            ):
                raise ValueError("SOURCE_COMPARISON_INPUT_CHANGED")
        if execution_revision() != inputs["code_revision"]:
            raise ValueError("SOURCE_COMPARISON_CODE_CHANGED")
        report = {
            "comparison_id": identity,
            "inputs": inputs,
            "counts": counts,
            "complete_comparison": True,
            "events_sha256": sha256(staging / "events.jsonl"),
            "events_bytes": size,
            "alignment": "original capture position; inserted rows can shift subsequent positions",
            "scope": "source comparison, not market causality, data approval or strategy validation",
        }
        encoded = serialize(report)
        atomic_bytes(staging / "report.json", encoded.encode())
        if destination.exists():
            if (destination / "report.json").read_text() != encoded or sha256(
                destination / "events.jsonl"
            ) != report["events_sha256"]:
                raise ValueError("conflicting immutable source comparison")
            shutil.rmtree(staging)
        else:
            os.rename(staging, destination)
        fd = os.open(directory, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        with versions.store.transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO source_comparisons VALUES(?,?,?,?,?,?)",
                (
                    identity,
                    serialize(inputs),
                    encoded,
                    hashlib.sha256(encoded.encode()).hexdigest(),
                    report["events_sha256"],
                    time.time(),
                ),
            )
            versions.store._audit(
                db, "source-comparison", "source_comparison_completed", {"comparison_id": identity}
            )
        return report
    except BaseException as exc:
        atomic_bytes(
            staging / "failure.json",
            serialize(
                {
                    "complete_comparison": False,
                    "counts": counts,
                    "error": type(exc).__name__ + ": " + str(exc),
                }
            ).encode(),
        )
        raise
