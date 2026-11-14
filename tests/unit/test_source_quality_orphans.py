"""A retained partial source scan must be discoverable.

A scan stages into a .pending-* directory and only records an attempt once it
has something to record. An uncatchable kill, or a store re-created afterwards,
leaves a directory that no command could find: source_quality_attempts and
source_quality_receipts both come back empty for it.
"""

from pathlib import Path

import pytest

from factory.data import Catalog
from factory.data.source_quality import SourceQuality


@pytest.fixture
def quality(tmp_path):
    return SourceQuality(tmp_path, Catalog(tmp_path / "catalog"))


def write_json(path: Path, payload) -> None:
    path.write_text(__import__("json").dumps(payload) + "\n")


def test_no_orphans_when_nothing_was_staged(quality):
    assert quality.orphans() == []


def test_orphan_with_no_attempt_row_is_reported(quality):
    staging = quality.directory / ".pending-abc123"
    staging.mkdir()
    write_json(staging / "attempt.json", {"attempt_id": "f" * 32})
    write_json(staging / "failure.json", {"error": "ValueError: SIGKILL"})
    (staging / "events.jsonl").write_text("{}\n")

    found = quality.orphans()
    assert len(found) == 1
    assert found[0]["attempt_id"] == "f" * 32
    assert found[0]["recorded"] is False
    assert found[0]["receipt"] is False
    assert found[0]["failure"] == "ValueError: SIGKILL"
    assert found[0]["bytes"] > 0


def test_recorded_failure_is_not_misreported_as_an_orphan(quality):
    """attempt.json carries the attempt_id; the store keys attempts by it.

    Comparing against run_id instead would report every recorded failure as an
    orphan, which is how this method was first written.
    """
    attempt_id = "a" * 32
    run_id = "b" * 32
    with quality.store.transaction() as db:
        db.execute(
            "INSERT INTO source_quality_attempts VALUES(?,?,?,?,?,?,?,?)",
            (attempt_id, run_id, "FAILED_INCOMPLETE", 1, ".pending-x", "ValueError: x", "{}", 0.0),
        )
    staging = quality.directory / ".pending-x"
    staging.mkdir()
    write_json(staging / "attempt.json", {"attempt_id": attempt_id})
    write_json(staging / "failure.json", {"error": "ValueError: x"})

    found = quality.orphans()
    assert len(found) == 1
    assert found[0]["recorded"] is True
    assert found[0]["receipt"] is False


def test_completed_receipt_is_reported_as_such(quality):
    run_id = "c" * 32
    with quality.store.transaction() as db:
        db.execute(
            "INSERT INTO source_quality_receipts VALUES(?,?,?,?,?,?)",
            (run_id, "{}", "{}", "0" * 64, "0" * 64, 0.0),
        )
    staging = quality.directory / ".pending-done"
    staging.mkdir()
    write_json(staging / "attempt.json", {"attempt_id": run_id})

    found = quality.orphans()
    assert len(found) == 1
    assert found[0]["receipt"] is True


def test_unreadable_metadata_does_not_crash_the_inventory(quality):
    staging = quality.directory / ".pending-bad"
    staging.mkdir()
    (staging / "attempt.json").write_bytes(b"\xff\xfe not json")
    (staging / "failure.json").write_bytes(b"")

    found = quality.orphans()
    assert len(found) == 1
    assert found[0]["attempt_id"] is None
    assert found[0]["recorded"] is False
    assert found[0]["failure"] is None


def test_non_directory_entries_are_ignored(quality):
    (quality.directory / ".pending-file").write_text("not a scan")
    assert quality.orphans() == []
