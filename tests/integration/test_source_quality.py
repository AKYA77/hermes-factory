"""Full lossless QA artifacts and restart/cache/failure behavior on labeled fixtures."""

from dataclasses import replace, asdict
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import signal

import pytest

from conftest import quotes
from factory.contracts import serialize
from factory.data import Catalog
from factory.data.streaming import StreamingCatalog
from factory.data.source_quality import SourceQuality, SourceQualityPolicy
from factory.instruments import synthetic_profile
from factory.instruments.calendar import CalendarSpec, SessionCalendar


def policy(**changes):
    return SourceQualityPolicy(
        gap_threshold_ns=60 * 10**9,
        unchanged_threshold_ns=120 * 10**9,
        timestamp_quantum_ns=10**6,
        max_examples=2,
        max_events_bytes=10 * 1024**2,
        **changes,
    )


def commit(root, data):
    raw = root / "input.json"
    root.mkdir(parents=True, exist_ok=True)
    raw.write_text(serialize([asdict(q) for q in data]))
    return StreamingCatalog(root / "catalog").commit(
        data,
        raw,
        {
            "source": "explicitly synthetic source QA fixture",
            "license": "project-generated software test",
            "synthetic": True,
        },
    )


def full_calendar():
    tzif = Path("/usr/share/zoneinfo/UTC").read_bytes()
    spec = CalendarSpec(
        instrument="EURUSD",
        version="synthetic/v1",
        timezone="UTC",
        tzif_sha256=hashlib.sha256(tzif).hexdigest(),
        source_document_sha256=hashlib.sha256(b"synthetic declaration").hexdigest(),
        source_citation="synthetic 24/7 software fixture; not verified broker facts",
        effective_start_ns=1735689600 * 10**9,
        effective_end_ns=1767225600 * 10**9,
        weekly_sessions=({"start_second": 0, "end_second": 604800},),
        closures=(),
        ambiguous_boundary="reject",
    )
    return SessionCalendar(spec, tzif)


def test_all_gaps_persist_beyond_examples_and_no_unreviewed_metadata_approval(tmp_path):
    data = quotes([(110000, 110010)] * 256, step=121 * 10**9)
    manifest = commit(tmp_path, data)
    scanner = SourceQuality(tmp_path, Catalog(tmp_path / "catalog"))
    result = scanner.run(
        manifest["dataset_hash"],
        policy(),
        calendar=full_calendar(),
        profile=synthetic_profile("EURUSD"),
    )
    assert result["complete_source_scan"] and result["counts"]["rows_scanned"] == 256
    assert result["counts"]["gaps"] == 255 and len(result["examples"]) == 2
    assert result["counts"]["calendar_rows_OPEN"] == 256
    assert (
        result["calendar_status"] == "DECLARED_RULES_ONLY"
        and result["profile_status"] == "DECLARED_UNITS_ONLY"
    )
    assert result["source_structural_status"] == "PASS" and result["historical_admission"] is False
    events = tmp_path / "artifacts/source-quality" / result["run_id"] / "events.jsonl"
    decoded = [json.loads(line) for line in events.read_text().splitlines()]
    gaps = [e for e in decoded if e["type"] == "GAP"]
    assert len(gaps) == 255 and all(g["calendar"]["status"] == "DECLARED_OPEN_GAP" for g in gaps)
    assert gaps[-1]["to"]["source_record_order"] == 255
    assert any(e["type"] == "UNCHANGED_OBSERVATION_RUN" and e["rows"] == 256 for e in decoded)
    assert scanner.verify(result["run_id"]) == result


def test_view_gap_and_equal_timestamp_duplicate_keep_exact_leaf_references(tmp_path):
    first = quotes([(110000, 110010)] * 2)
    second = quotes([(110000, 110010)] * 2, start=first[-1].event_ts_utc_ns, step=121 * 10**9)
    a, b = (commit(tmp_path, data)["dataset_hash"] for data in (first, second))
    catalog = Catalog(tmp_path / "catalog")
    view = catalog.compose([a, b])
    scanner = SourceQuality(tmp_path, catalog)
    result = scanner.run(view["dataset_hash"], policy())
    assert result["counts"]["rows_scanned"] == 4 and result["counts"]["gaps"] == 1
    assert result["counts"]["consecutive_exact_duplicates_retained"] == 1
    assert result["counts"]["structural_issue_rows"] == 0
    assert (
        result["counts"]["calendar_rows_UNKNOWN"] == 4
        and result["calendar_status"] == "UNKNOWN_CALENDAR"
    )
    records = [
        json.loads(line)
        for line in (scanner.directory / result["run_id"] / "events.jsonl").read_text().splitlines()
    ]
    gap = next(e for e in records if e["type"] == "GAP")
    assert gap["from"]["leaf_hash"] == b and gap["from"]["source_record_order"] == 0
    assert gap["from"]["sequence"] == 2 and gap["to"]["sequence"] == 3
    run = next(e for e in records if e["type"] == "DECLARED_SESSION_RUN")
    assert run["first"]["leaf_hash"] == a and run["last"]["leaf_hash"] == b


def test_cached_receipt_does_not_rescan_and_tampering_or_metric_writes_fail(tmp_path, monkeypatch):
    manifest = commit(tmp_path, quotes([(110000, 110010)] * 3))
    scanner = SourceQuality(tmp_path, Catalog(tmp_path / "catalog"))
    result = scanner.run(manifest["dataset_hash"], policy())

    def forbidden(*args, **kwargs):
        raise AssertionError("cached semantic scan repeated")

    monkeypatch.setattr(scanner.catalog, "read", forbidden)
    assert scanner.run(manifest["dataset_hash"], policy()) == result
    assert len(scanner.store.rows("SELECT * FROM source_quality_attempts")) == 1
    with pytest.raises(sqlite3.IntegrityError, match="immutable source quality"):
        with scanner.store.transaction() as db:
            db.execute("DELETE FROM source_quality_receipts")
    events = scanner.directory / result["run_id"] / "events.jsonl"
    events.write_bytes(events.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="ARTIFACT_MISMATCH"):
        scanner.verify(result["run_id"])


def test_window_narrower_than_dataset_reports_count_without_exhausting_budget(tmp_path):
    """A requested window narrower than the data is a property of the request.

    Every row used to emit a REQUESTED_PERIOD_MISMATCH event, so a window that
    barely overlaps a partition exhausted the event budget on a systematic
    condition and failed the whole scan. The count must carry the magnitude while
    the events stay bounded.
    """
    # Step inside the gap threshold so the only systematic condition is the
    # out-of-window mismatch, isolating it from budget consumed by gaps.
    data = quotes([(110000, 110010)] * 32, step=10**9)
    manifest = commit(tmp_path, data)
    scanner = SourceQuality(tmp_path, Catalog(tmp_path / "catalog"))
    first = data[0].event_ts_utc_ns
    narrow = policy().model_copy(
        update={
            "max_examples": 2,
            "max_events_bytes": 1024,
            "expected_start_ns": first,
            "expected_end_ns": first + 1000,
        }
    )
    receipt = scanner.run(manifest["dataset_hash"], narrow)
    assert receipt["counts"]["rows_scanned"] == 32
    assert receipt["counts"]["outside_requested_period_rows"] == 31
    assert receipt["requested_period_status"] == "OBSERVED_OUTSIDE_REQUESTED_PERIOD"
    events = [
        json.loads(line)
        for line in (scanner.directory / receipt["run_id"] / "events.jsonl")
        .read_text()
        .splitlines()
    ]
    # Bounded by max_examples, not one per out-of-window row.
    assert len([e for e in events if e["type"] == "REQUESTED_PERIOD_MISMATCH"]) <= 2


def test_event_budget_retains_incomplete_attempt_and_never_registers_complete_receipt(tmp_path):
    manifest = commit(tmp_path, quotes([(110000, 110010)] * 32, step=121 * 10**9))
    scanner = SourceQuality(tmp_path, Catalog(tmp_path / "catalog"))
    limited = policy().model_copy(update={"max_events_bytes": 1024})
    with pytest.raises(ValueError, match="EVENT_BUDGET"):
        scanner.run(manifest["dataset_hash"], limited)
    assert not scanner.store.rows("SELECT * FROM source_quality_receipts")
    attempts = scanner.store.rows("SELECT * FROM source_quality_attempts")
    assert len(attempts) == 1 and attempts[0]["outcome"] == "FAILED_INCOMPLETE"
    directory = scanner.directory / attempts[0]["artifact_directory"]
    failed = json.loads((directory / "failure.json").read_text())
    assert failed["complete_source_scan"] is False and 0 < failed["rows_scanned"] < 32
    assert (directory / "events.jsonl").exists()
    succeeded = scanner.run(manifest["dataset_hash"], policy())
    assert succeeded["counts"]["rows_scanned"] == 32
    assert len(scanner.store.rows("SELECT * FROM source_quality_attempts")) == 2


def test_sigkill_retains_exact_attempt_inputs_and_retry_does_full_scan(tmp_path):
    manifest = commit(tmp_path, quotes([(110000, 110010)] * 32, step=121 * 10**9))
    # The child dies inside the real scan, after reading its first real source
    # row. No Python cleanup/failure handler can manufacture recovery evidence.
    child_code = """
import json, os, signal, sys
from pathlib import Path
from factory.data import Catalog
from factory.data.source_quality import SourceQuality
root = Path(sys.argv[1])
catalog = Catalog(root / 'catalog')
original = catalog.read
def interrupted(*args, **kwargs):
    for row in original(*args, **kwargs):
        yield row
        os.kill(os.getpid(), signal.SIGKILL)
catalog.read = interrupted
SourceQuality(root, catalog).run(sys.argv[2], json.loads(sys.argv[3]))
"""
    killed = subprocess.run(
        [
            sys.executable,
            "-c",
            child_code,
            str(tmp_path),
            manifest["dataset_hash"],
            policy().model_dump_json(),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert killed.returncode == -signal.SIGKILL, killed.stderr
    scanner = SourceQuality(tmp_path, Catalog(tmp_path / "catalog"))
    pending = list(scanner.directory.glob(".pending-*"))
    assert len(pending) == 1
    marker_bytes = (pending[0] / "attempt.json").read_bytes()
    marker = json.loads(marker_bytes)
    assert not marker["complete_source_scan"]
    assert marker["inputs"]["dataset_hash"] == manifest["dataset_hash"]
    assert marker["inputs"]["policy"] == policy().model_dump()
    assert not (pending[0] / "report.json").exists()
    assert not scanner.store.rows("SELECT * FROM source_quality_receipts")
    assert not scanner.store.rows("SELECT * FROM source_quality_attempts")
    result = scanner.run(manifest["dataset_hash"], policy())
    assert result["complete_source_scan"] and result["counts"]["rows_scanned"] == 32
    assert result["run_id"] == marker["run_id"]
    assert (pending[0] / "attempt.json").read_bytes() == marker_bytes
    assert len(scanner.store.rows("SELECT * FROM source_quality_receipts")) == 1


def test_declared_off_grid_profile_does_not_round_source_or_grant_admission(tmp_path):
    data = quotes([(110001, 110011)] * 3)
    manifest = commit(tmp_path, data)
    catalog = Catalog(tmp_path / "catalog")
    scanner = SourceQuality(tmp_path, catalog)
    profile = synthetic_profile("EURUSD").model_copy(
        update={"tick_size": D("0.0001"), "pip_size": D("0.001")}
    )
    result = scanner.run(manifest["dataset_hash"], policy(), profile=profile.model_dump())
    assert result["counts"]["off_declared_tick_grid"] == 3
    assert (
        result["profile_status"] == "DECLARED_UNITS_MISMATCH"
        and result["historical_admission"] is False
    )
    assert [(q.bid_int, q.ask_int) for q in catalog.read(manifest["dataset_hash"])] == [
        (110001, 110011)
    ] * 3


def test_source_record_sequence_gap_is_an_issue_not_silently_repaired(tmp_path):
    # quotes/v1 accepts a sparse supplied source order; the new scanner diagnoses it.
    data = quotes([(110000, 110010)] * 3)
    data[1] = replace(data[1], original_record_order=4)
    catalog = Catalog(tmp_path / "catalog")
    manifest = catalog.commit(
        data,
        b"explicitly synthetic malformed-order reference",
        {"source": "synthetic QA fault fixture", "license": "project test", "synthetic": True},
    )
    result = SourceQuality(tmp_path, catalog).run(manifest["dataset_hash"], policy())
    assert result["complete_source_scan"] and result["source_structural_status"] == "FAILED_CHECKS"
    assert result["counts"]["structural_issue_rows"] == 2
    assert result["historical_admission"] is False


def test_captured_calendar_and_profile_inputs_are_required_for_reproducible_receipt(tmp_path):
    manifest = commit(tmp_path, quotes([(110000, 110010)] * 3))
    scanner = SourceQuality(tmp_path, Catalog(tmp_path / "catalog"))
    result = scanner.run(
        manifest["dataset_hash"],
        policy(),
        calendar=full_calendar(),
        profile=synthetic_profile("EURUSD"),
    )
    directory = scanner.directory / result["run_id"]
    assert (directory / "calendar.json").exists() and (directory / "profile.json").exists()
    assert (directory / "timezone.tzif").read_bytes() == full_calendar().tzif_bytes
    (directory / "timezone.tzif").write_bytes(b"changed timezone database")
    with pytest.raises(ValueError, match="CALENDAR_INPUT_MISMATCH"):
        scanner.verify(result["run_id"])


def test_requested_boundary_intervals_are_preserved_without_invented_quote_points(tmp_path):
    data = quotes([(110000, 110010)] * 3)
    manifest = commit(tmp_path, data)
    scanner = SourceQuality(tmp_path, Catalog(tmp_path / "catalog"))
    p = policy(
        expected_start_ns=data[0].event_ts_utc_ns - 60 * 10**9,
        expected_end_ns=data[-1].event_ts_utc_ns + 60 * 10**9,
    )
    result = scanner.run(manifest["dataset_hash"], p)
    assert result["counts"]["boundary_intervals"] == 2 and result["counts"]["rows_scanned"] == 3
    events = [
        json.loads(line)
        for line in (scanner.directory / result["run_id"] / "events.jsonl").read_text().splitlines()
    ]
    leading = next(e for e in events if e["type"] == "LEADING_UNQUOTED_INTERVAL")
    trailing = next(e for e in events if e["type"] == "TRAILING_UNQUOTED_INTERVAL")
    assert (
        leading["start_ns"] == p.expected_start_ns
        and leading["observed_quote"]["source_record_order"] == 0
    )
    assert (
        trailing["end_ns"] == p.expected_end_ns
        and trailing["observed_quote"]["source_record_order"] == 2
    )
    assert leading["calendar"]["unknown_ns"] == trailing["calendar"]["unknown_ns"] == 60 * 10**9
    assert result["requested_period_status"] == "OBSERVED_WITHIN_REQUESTED_PERIOD"
    narrower = p.model_copy(
        update={
            "expected_start_ns": data[1].event_ts_utc_ns,
            "expected_end_ns": data[-1].event_ts_utc_ns,
        }
    )
    wrong = scanner.run(manifest["dataset_hash"], narrower)
    assert wrong["requested_period_status"] == "OBSERVED_OUTSIDE_REQUESTED_PERIOD"
    assert (
        wrong["counts"]["outside_requested_period_rows"] == 2
        and wrong["historical_admission"] is False
    )


def test_source_quality_cli_and_status_share_the_documented_receipt_interface(tmp_path):
    manifest = commit(tmp_path, quotes([(110000, 110010)] * 3))
    path = tmp_path / "policy.json"
    path.write_text(policy().model_dump_json())
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "factory.cli",
            "--state",
            str(tmp_path),
            "source-quality",
            manifest["dataset_hash"],
            str(path),
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    result = json.loads(completed.stdout)
    assert result["complete_source_scan"] and result["counts"]["rows_scanned"] == 3
    assert result["historical_admission"] is False and result["profile_status"] == "UNKNOWN_SPEC"
    status = subprocess.run(
        [sys.executable, "-m", "factory.cli", "--state", str(tmp_path), "source-quality-status"],
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(status.stdout)[0]["run_id"] == result["run_id"]
    wrong = policy(
        expected_start_ns=manifest["first_ns"] + 1,
        expected_end_ns=manifest["latest_verified_ns"] + 1,
    )
    path.write_text(wrong.model_dump_json())
    failed = subprocess.run(
        [
            sys.executable,
            "-m",
            "factory.cli",
            "--state",
            str(tmp_path),
            "source-quality",
            manifest["dataset_hash"],
            str(path),
        ],
        text=True,
        capture_output=True,
    )
    assert failed.returncode == 1
    assert (
        json.loads(failed.stdout)["requested_period_status"] == "OBSERVED_OUTSIDE_REQUESTED_PERIOD"
    )
