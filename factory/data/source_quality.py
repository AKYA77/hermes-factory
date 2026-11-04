"""Lossless bounded source QA; every issue/gap is retained, not just examples.

Declared profiles/calendars are not verified broker evidence. These receipts
never authorize historical strategy execution or certify source completeness.
"""

from collections import Counter
from decimal import Decimal as D
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import tempfile
import time
from typing import Literal
import uuid

from pydantic import Field, model_validator

from factory.contracts import Contract, InstrumentSpec, fingerprint, serialize
from factory.data import atomic_bytes, sha256
from factory.data.streaming import row_bytes, row_metadata
from factory.experiments import Store
from factory.instruments.calendar import Nanoseconds, classify_gap
from factory.provenance import execution_revision


class SourceQualityPolicy(Contract):
    schema_version: Literal["source-quality-policy/v1"] = "source-quality-policy/v1"
    gap_threshold_ns: Nanoseconds = Field(gt=0)
    unchanged_threshold_ns: Nanoseconds = Field(gt=0)
    timestamp_quantum_ns: Nanoseconds = Field(gt=0)
    max_examples: int = Field(ge=0, le=1000, strict=True)
    max_events_bytes: int = Field(ge=1024, le=1024**3, strict=True)
    expected_start_ns: Nanoseconds | None = None
    expected_end_ns: Nanoseconds | None = None

    @model_validator(mode="after")
    def period(self):
        if (self.expected_start_ns is None) != (self.expected_end_ns is None):
            raise ValueError("expected source period requires both boundaries")
        if self.expected_start_ns is not None and self.expected_start_ns >= self.expected_end_ns:
            raise ValueError("empty expected source period")
        return self


class SourceQuality:
    def __init__(self, root, catalog):
        self.root = Path(root)
        self.catalog = catalog
        self.store = Store(self.root / "factory.sqlite")
        self.directory = self.root / "artifacts" / "source-quality"
        self.directory.mkdir(parents=True, exist_ok=True)

    def verify(self, identity):
        if len(identity) != 64 or any(c not in "0123456789abcdef" for c in identity):
            raise ValueError("invalid source quality identity")
        rows = self.store.rows("SELECT * FROM source_quality_receipts WHERE run_id=?", (identity,))
        if not rows:
            raise ValueError("unknown source quality receipt")
        row = rows[0]
        report = self.directory / identity / "report.json"
        events = self.directory / identity / "events.jsonl"
        if report.is_symlink() or events.is_symlink() or report.parent.is_symlink():
            raise ValueError("source quality symlink forbidden")
        if (
            sha256(report) != row["report_sha256"]
            or sha256(events) != row["events_sha256"]
            or report.read_text() != row["report_json"]
            or fingerprint(json.loads(row["inputs_json"])) != identity
        ):
            raise ValueError("SOURCE_QUALITY_ARTIFACT_MISMATCH")
        value = json.loads(row["report_json"])
        if (
            value.get("run_id") != identity
            or serialize(value.get("inputs")) != row["inputs_json"]
            or value.get("events_sha256") != row["events_sha256"]
        ):
            raise ValueError("SOURCE_QUALITY_RECEIPT_BINDING_MISMATCH")
        if value["inputs"]["calendar_hash"] is not None:
            from factory.instruments.calendar import CalendarSpec

            spec_file = report.parent / "calendar.json"
            tzif_file = report.parent / "timezone.tzif"
            if spec_file.is_symlink() or tzif_file.is_symlink():
                raise ValueError("source quality input symlink forbidden")
            spec = CalendarSpec.model_validate_json(spec_file.read_text())
            if (
                spec.calendar_hash != value["inputs"]["calendar_hash"]
                or sha256(tzif_file) != spec.tzif_sha256
            ):
                raise ValueError("SOURCE_QUALITY_CALENDAR_INPUT_MISMATCH")
        if value["inputs"]["profile_hash"] is not None:
            profile_file = report.parent / "profile.json"
            if profile_file.is_symlink():
                raise ValueError("source quality input symlink forbidden")
            profile = InstrumentSpec.model_validate_json(profile_file.read_text())
            if fingerprint(profile) != value["inputs"]["profile_hash"]:
                raise ValueError("SOURCE_QUALITY_PROFILE_INPUT_MISMATCH")
        return value

    def run(self, dataset_hash, policy, *, calendar=None, profile=None):
        policy = SourceQualityPolicy.model_validate(policy)
        profile = InstrumentSpec.model_validate(profile) if profile is not None else None
        try:
            manifest = self.catalog.verify(dataset_hash)
            leaves = (
                [p["dataset_hash"] for p in manifest["parts"]]
                if manifest["schema_version"] == "data/view-v1"
                else [dataset_hash]
            )
            descriptors = {key: self.catalog.verify(key) for key in leaves}
            for key, leaf in descriptors.items():
                if leaf["schema_version"] == "data/v1":
                    self.catalog.verify(key, deep=True)
            scale = manifest.get("price_scale")
            if scale is None:
                scale = next(self.catalog.read(dataset_hash)).price_scale
        except (ValueError, OSError) as exc:
            self.store.audit(
                "source-quality",
                "source_quality_preflight_failed",
                {
                    "requested_identity_sha256": hashlib.sha256(
                        str(dataset_hash).encode()
                    ).hexdigest(),
                    "error": type(exc).__name__ + ": " + str(exc),
                    "complete_source_scan": False,
                },
            )
            raise
        revision = execution_revision()
        inputs = {
            "schema": "source-quality/v1",
            "dataset_hash": dataset_hash,
            "manifest_hash": fingerprint(manifest),
            "canonical_price_scale": scale,
            "policy": policy.model_dump(),
            "calendar_hash": calendar.calendar_hash if calendar else None,
            "profile_hash": fingerprint(profile) if profile else None,
            "code_revision": revision,
        }
        identity = fingerprint(inputs)
        if self.store.rows(
            "SELECT run_id FROM source_quality_receipts WHERE run_id=?", (identity,)
        ):
            return self.verify(identity)
        if shutil.disk_usage(self.directory).free < 256 * 1024**2:
            raise ValueError("SOURCE_QUALITY_DISK_RESERVE")
        attempt = uuid.uuid4().hex
        staging = Path(tempfile.mkdtemp(prefix=".pending-", dir=self.directory))
        if calendar:
            atomic_bytes(staging / "calendar.json", serialize(calendar.spec).encode())
            atomic_bytes(staging / "timezone.tzif", calendar.tzif_bytes)
        if profile:
            atomic_bytes(staging / "profile.json", serialize(profile).encode())
        started = time.perf_counter()
        usage = resource.getrusage(resource.RUSAGE_SELF)
        counts = Counter(
            {
                name: 0
                for name in (
                    "rows_scanned",
                    "events",
                    "gaps",
                    "structural_issue_rows",
                    "off_declared_tick_grid",
                    "unchanged_runs",
                    "consecutive_exact_duplicates_retained",
                    "calendar_rows_OPEN",
                    "calendar_rows_CLOSED",
                    "calendar_rows_UNKNOWN",
                    "outside_requested_period_rows",
                    "boundary_intervals",
                )
            }
        )
        examples = []
        sizes = 0
        previous = None
        unchanged = None
        session_run = None
        digests = {}
        metadata = {}
        leaf_counts = Counter()
        leaf_orders = {}
        calendar_error = None
        coverage = None
        profile_errors = []
        if calendar:
            if calendar.spec.instrument != manifest["instrument"]:
                calendar_error = "CALENDAR_INSTRUMENT_MISMATCH"
            else:
                try:
                    coverage = calendar.prepare(
                        min(
                            manifest["first_ns"],
                            policy.expected_start_ns
                            if policy.expected_start_ns is not None
                            else manifest["first_ns"],
                        ),
                        max(
                            manifest["latest_verified_ns"] + 1,
                            policy.expected_end_ns
                            if policy.expected_end_ns is not None
                            else manifest["latest_verified_ns"] + 1,
                        ),
                    )
                except ValueError as exc:
                    calendar_error = str(exc)
        if profile:
            if profile.instrument != manifest["instrument"]:
                profile_errors.append("PROFILE_INSTRUMENT_MISMATCH")
            if profile.price_scale != scale:
                profile_errors.append("PROFILE_SCALE_MISMATCH")
        tick_int = profile.tick_size * scale if profile and not profile_errors else None
        if tick_int is not None and tick_int != tick_int.to_integral_value():
            profile_errors.append("UNREPRESENTABLE_DECLARED_TICK")
            tick_int = None
        events = (staging / "events.jsonl").open("wb")

        def reference(q):
            return {
                "ts": q.event_ts_utc_ns,
                "sequence": getattr(q, "sequence", q.original_record_order),
                "leaf_hash": getattr(q, "partition_hash", dataset_hash),
                "source_record_order": q.original_record_order,
            }

        def emit(kind, payload):
            nonlocal sizes
            record = {"type": kind, **payload}
            encoded = (serialize(record) + "\n").encode()
            if sizes + len(encoded) > policy.max_events_bytes:
                raise ValueError("SOURCE_QUALITY_EVENT_BUDGET")
            if sizes // (1024 * 1024) != (sizes + len(encoded)) // (
                1024 * 1024
            ) and shutil.disk_usage(self.directory).free < 256 * 1024**2 + len(encoded):
                raise ValueError("SOURCE_QUALITY_DISK_RESERVE")
            events.write(encoded)
            sizes += len(encoded)
            counts["events"] += 1
            if len(examples) < policy.max_examples:
                examples.append(record)

        def close_unchanged():
            if (
                unchanged
                and unchanged["last"]["ts"] - unchanged["first"]["ts"]
                >= policy.unchanged_threshold_ns
            ):
                counts["unchanged_runs"] += 1
                emit(
                    "UNCHANGED_OBSERVATION_RUN",
                    {
                        "first": unchanged["first"],
                        "last": unchanged["last"],
                        "rows": unchanged["rows"],
                        "price_pair_hash": fingerprint(
                            {
                                "bid_int": unchanged["bid"],
                                "ask_int": unchanged["ask"],
                                "scale": scale,
                            }
                        ),
                    },
                )

        def close_session():
            if session_run:
                emit("DECLARED_SESSION_RUN", session_run)

        def boundary(kind, start, end, quote):
            gap = classify_gap(start, end, coverage)
            if calendar_error:
                gap["status"] = "UNRESOLVED_CALENDAR"
                gap["reason"] = calendar_error
            counts["boundary_intervals"] += 1
            emit(kind, {"start_ns": start, "end_ns": end, "observed_quote": quote, "calendar": gap})

        try:
            for q in self.catalog.read(dataset_hash, batch_rows=8192):
                counts["rows_scanned"] += 1
                ref = reference(q)
                key = ref["leaf_hash"]
                current_metadata = row_metadata(q)
                if key not in descriptors:
                    raise ValueError("unexpected source leaf")
                if key not in metadata:
                    metadata[key] = current_metadata
                    digests[key] = hashlib.sha256(serialize(current_metadata).encode())
                if current_metadata != metadata[key]:
                    raise ValueError("source leaf metadata changed")
                digests[key].update(row_bytes(q))
                leaf_counts[key] += 1
                reasons = []
                if policy.expected_start_ns is not None:
                    if previous is None and ref["ts"] > policy.expected_start_ns:
                        boundary(
                            "LEADING_UNQUOTED_INTERVAL", policy.expected_start_ns, ref["ts"], ref
                        )
                    if not policy.expected_start_ns <= ref["ts"] < policy.expected_end_ns:
                        counts["outside_requested_period_rows"] += 1
                        emit("REQUESTED_PERIOD_MISMATCH", {"quote": ref})
                if q.instrument_id != manifest["instrument"] or q.price_scale != scale:
                    reasons.append("CANONICAL_UNITS_MISMATCH")
                if q.bid_int <= 0 or q.ask_int < q.bid_int or q.quality_flags:
                    reasons.append("INVALID_QUOTE")
                if q.original_record_order < 0:
                    reasons.append("INVALID_SOURCE_ORDER")
                if key in leaf_orders and q.original_record_order != leaf_orders[key] + 1:
                    reasons.append("SOURCE_RECORD_SEQUENCE_GAP")
                leaf_orders[key] = q.original_record_order
                if q.event_ts_utc_ns % policy.timestamp_quantum_ns:
                    reasons.append("SOURCE_TIMESTAMP_PRECISION_MISMATCH")
                if previous and (
                    ref["ts"] < previous["ts"] or ref["sequence"] <= previous["sequence"]
                ):
                    reasons.append("SOURCE_CHRONOLOGY_MISMATCH")
                if tick_int is not None and (D(q.bid_int) % tick_int or D(q.ask_int) % tick_int):
                    counts["off_declared_tick_grid"] += 1
                    emit("DECLARED_TICK_GRID_MISMATCH", {"quote": ref})
                if reasons:
                    counts["structural_issue_rows"] += 1
                    emit("ROW_ISSUE", {"quote": ref, "reasons": reasons})
                if previous:
                    delta = ref["ts"] - previous["ts"]
                    if delta > policy.gap_threshold_ns:
                        gap = classify_gap(previous["ts"], ref["ts"], coverage)
                        if calendar_error:
                            gap["reason"] = calendar_error
                            gap["status"] = "UNRESOLVED_CALENDAR"
                        counts["gaps"] += 1
                        counts["gap_" + gap["status"]] += 1
                        emit("GAP", {"from": previous, "to": ref, "calendar": gap})
                    if (
                        previous["ts"] == ref["ts"]
                        and unchanged
                        and unchanged["bid"] == q.bid_int
                        and unchanged["ask"] == q.ask_int
                    ):
                        counts["consecutive_exact_duplicates_retained"] += 1
                if unchanged and unchanged["bid"] == q.bid_int and unchanged["ask"] == q.ask_int:
                    unchanged["last"] = ref
                    unchanged["rows"] += 1
                else:
                    close_unchanged()
                    unchanged = {
                        "first": ref,
                        "last": ref,
                        "rows": 1,
                        "bid": q.bid_int,
                        "ask": q.ask_int,
                    }
                opened = coverage.is_open(ref["ts"]) if coverage else None
                state = "UNKNOWN" if opened is None else "OPEN" if opened else "CLOSED"
                counts["calendar_rows_" + state] += 1
                if session_run and session_run["state"] == state:
                    session_run["last"] = ref
                    session_run["rows"] += 1
                else:
                    close_session()
                    session_run = {"state": state, "first": ref, "last": ref, "rows": 1}
                previous = ref
            close_unchanged()
            close_session()
            if (
                previous
                and policy.expected_end_ns is not None
                and previous["ts"] + 1 < policy.expected_end_ns
            ):
                boundary(
                    "TRAILING_UNQUOTED_INTERVAL", previous["ts"], policy.expected_end_ns, previous
                )
            if counts["rows_scanned"] != manifest["rows"]:
                raise ValueError("SOURCE_QUALITY_ROW_COUNT_MISMATCH")
            for key, leaf in descriptors.items():
                if leaf_counts[key] != leaf["rows"]:
                    raise ValueError("SOURCE_QUALITY_LEAF_COUNT_MISMATCH")
                if (
                    leaf["schema_version"] == "data/v2"
                    and digests[key].hexdigest() != leaf["quote_stream_sha256"]
                ):
                    raise ValueError("SOURCE_QUALITY_LEAF_STREAM_MISMATCH")
            if (
                fingerprint(self.catalog.verify(dataset_hash)) != inputs["manifest_hash"]
                or execution_revision() != revision
            ):
                raise ValueError("SOURCE_QUALITY_INPUT_OR_CODE_CHANGED")
            events.flush()
            os.fsync(events.fileno())
            events.close()
            report = {
                "run_id": identity,
                "inputs": inputs,
                "instrument": manifest["instrument"],
                "synthetic": bool(manifest["provenance"].get("synthetic")),
                "complete_source_scan": True,
                "counts": dict(counts),
                "examples": examples,
                "events_sha256": sha256(staging / "events.jsonl"),
                "events_bytes": sizes,
                "source_structural_status": "PASS"
                if not counts["structural_issue_rows"]
                else "FAILED_CHECKS",
                "calendar_status": "UNKNOWN_CALENDAR"
                if calendar is None
                else "UNRESOLVED_CALENDAR"
                if calendar_error
                else "DECLARED_RULES_ONLY",
                "calendar_error": calendar_error,
                "profile_status": "UNKNOWN_SPEC"
                if profile is None
                else "DECLARED_UNITS_MISMATCH"
                if profile_errors or counts["off_declared_tick_grid"]
                else "DECLARED_UNITS_ONLY",
                "profile_errors": profile_errors,
                "requested_period_status": "UNDECLARED"
                if policy.expected_start_ns is None
                else "OBSERVED_OUTSIDE_REQUESTED_PERIOD"
                if counts["outside_requested_period_rows"]
                else "OBSERVED_WITHIN_REQUESTED_PERIOD",
                "historical_admission": False,
                "scope": "technical source integrity and declared rules; not verified broker metadata or historical strategy performance",
                "unchanged_warning": "unchanged observed prices, including gaps, are not proof of stale executable market data",
                "gap_warning": "long interarrival/boundary intervals are observations, not proof that a market tick is missing",
                "source_precision_policy": "exact nanosecond divisibility; canonical timestamps/prices unchanged",
            }
            encoded = serialize(report)
            atomic_bytes(staging / "report.json", encoded.encode())
            destination = self.directory / identity
            if destination.exists():
                if (destination / "report.json").read_text() != encoded or sha256(
                    destination / "events.jsonl"
                ) != report["events_sha256"]:
                    raise ValueError("conflicting immutable source quality artifact")
                shutil.rmtree(staging)
            else:
                os.rename(staging, destination)
            directory_fd = os.open(self.directory, os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            with self.store.transaction() as db:
                db.execute(
                    "INSERT OR IGNORE INTO source_quality_receipts VALUES(?,?,?,?,?,?)",
                    (
                        identity,
                        serialize(inputs),
                        encoded,
                        hashlib.sha256(encoded.encode()).hexdigest(),
                        report["events_sha256"],
                        time.time(),
                    ),
                )
                self.store._audit(
                    db,
                    "source-quality",
                    "source_quality_completed",
                    {
                        "run_id": identity,
                        "dataset_hash": dataset_hash,
                        "historical_admission": False,
                    },
                )
            verified = self.verify(identity)
            self._attempt(
                attempt,
                identity,
                "COMPLETED",
                counts["rows_scanned"],
                destination,
                None,
                started,
                usage,
            )
            return verified
        except BaseException as exc:
            if not events.closed:
                events.close()
            # Retain every partial event and the exact incomplete failure state.
            atomic_bytes(
                staging / "failure.json",
                serialize(
                    {
                        "run_id": identity,
                        "complete_source_scan": False,
                        "rows_scanned": counts["rows_scanned"],
                        "error": type(exc).__name__ + ": " + str(exc),
                    }
                ).encode(),
            )
            self._attempt(
                attempt,
                identity,
                "FAILED_INCOMPLETE",
                counts["rows_scanned"],
                staging,
                str(exc),
                started,
                usage,
            )
            raise

    def _attempt(self, attempt, identity, outcome, rows, directory, error, started, usage):
        after = resource.getrusage(resource.RUSAGE_SELF)
        metrics = {
            "wall_seconds": time.perf_counter() - started,
            "cpu_seconds": after.ru_utime + after.ru_stime - usage.ru_utime - usage.ru_stime,
            "process_peak_rss_bytes": after.ru_maxrss * 1024,
        }
        with self.store.transaction() as db:
            db.execute(
                "INSERT INTO source_quality_attempts VALUES(?,?,?,?,?,?,?,?)",
                (
                    attempt,
                    identity,
                    outcome,
                    rows,
                    str(directory.relative_to(self.directory)),
                    error,
                    serialize(metrics),
                    time.time(),
                ),
            )
