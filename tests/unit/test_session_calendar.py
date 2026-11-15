"""Independent UTC/DST interval references, explicitly synthetic calendar rules."""

from datetime import datetime, timezone
import hashlib
from pathlib import Path

import pytest

from factory.instruments.calendar import CalendarSpec, SessionCalendar, classify_gap

SECOND = 10**9
HOUR = 3600 * SECOND
DAY = 24 * HOUR


def ns(text):
    stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    delta = stamp - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (delta.days * 86400 + delta.seconds) * SECOND + delta.microseconds * 1000


def calendar(
    zone="America/New_York", sessions=None, closures=(), start=None, end=None, ambiguous="reject"
):
    tzif = (Path("/usr/share/zoneinfo") / zone).read_bytes()
    spec = CalendarSpec(
        instrument="EURUSD",
        version="synthetic-calendar/v1",
        timezone=zone,
        tzif_sha256=hashlib.sha256(tzif).hexdigest(),
        source_document_sha256=hashlib.sha256(b"synthetic calendar reference").hexdigest(),
        source_citation="Explicitly synthetic calendar test; not a verified brokerage schedule",
        effective_start_ns=ns(start or "2025-01-01T00:00:00Z"),
        effective_end_ns=ns(end or "2026-01-01T00:00:00Z"),
        weekly_sessions=sessions
        or ({"start_second": 6 * 86400 + 17 * 3600, "end_second": 4 * 86400 + 17 * 3600},),
        closures=closures,
        ambiguous_boundary=ambiguous,
    )
    return SessionCalendar(spec, tzif)


def test_spring_and_autumn_weekend_durations_follow_captured_timezone_rules():
    c = calendar()
    spring = c.availability(ns("2025-03-07T22:00:00Z"), ns("2025-03-09T21:00:00Z"))
    autumn = c.availability(ns("2025-10-31T21:00:00Z"), ns("2025-11-02T22:00:00Z"))
    assert spring["open_ns"] == autumn["open_ns"] == 0
    assert spring["closed_ns"] == 47 * HOUR and autumn["closed_ns"] == 49 * HOUR
    mixed = classify_gap(ns("2025-03-07T21:00:00Z"), ns("2025-03-09T22:00:00Z"), c)
    assert mixed["status"] == "MIXED_OPEN_CLOSED_GAP"
    assert mixed["open_ns"] == 2 * HOUR and mixed["closed_ns"] == 47 * HOUR
    assert mixed["unknown_ns"] == 0


def test_nanosecond_boundary_and_overlapping_sessions_are_exact():
    c = calendar()
    opened = ns("2025-03-09T21:00:00Z")
    result = c.availability(opened - 1, opened + 1)
    assert result["open_ns"] == 1 and result["closed_ns"] == 1
    full = calendar(
        "UTC",
        sessions=(
            {"start_second": 0, "end_second": 604800},
            {"start_second": 0, "end_second": 86400},
        ),
    )
    result = full.availability(ns("2025-01-06T00:00:00Z"), ns("2025-01-07T00:00:00Z"))
    assert result["open_ns"] == DAY and result["closed_ns"] == 0


def test_declared_holiday_closures_use_union_without_double_counting():
    start, end = ns("2025-01-02T00:00:00Z"), ns("2025-01-03T00:00:00Z")
    c = calendar(
        closures=(
            {"start_ns": start, "end_ns": end, "reason": "synthetic holiday"},
            {"start_ns": start + 12 * HOUR, "end_ns": end, "reason": "overlap reference"},
        )
    )
    result = c.availability(start - 1, end + 1)
    assert result["closed_ns"] == DAY and result["open_ns"] == 2 and result["unknown_ns"] == 0
    assert classify_gap(start, end, c)["status"] == "DECLARED_CLOSED_ONLY"


def test_missing_and_out_of_date_calendar_remains_unknown_not_weekend_assumption():
    left, right = ns("2025-03-07T22:00:00Z"), ns("2025-03-09T21:00:00Z")
    missing = classify_gap(left, right)
    assert missing["status"] == "UNKNOWN_CALENDAR" and missing["unknown_ns"] == 47 * HOUR
    c = calendar(
        "UTC",
        sessions=({"start_second": 0, "end_second": 604800},),
        start="2025-01-01T00:00:00Z",
        end="2025-01-03T00:00:00Z",
    )
    result = classify_gap(ns("2024-12-31T00:00:00Z"), ns("2025-01-02T00:00:00Z"), c)
    assert result["status"] == "UNKNOWN_EFFECTIVE_PERIOD"
    assert result["unknown_ns"] == DAY and result["open_ns"] == DAY
    assert result["closed_ns"] == 0


def test_ambiguous_and_nonexistent_boundaries_are_not_silently_invented():
    sessions = ({"start_second": 6 * 86400 + 90 * 60, "end_second": 6 * 86400 + 150 * 60},)
    left, right = ns("2025-11-02T05:00:00Z"), ns("2025-11-02T08:00:00Z")
    assert classify_gap(left, right, calendar(sessions=sessions))["status"] == "UNRESOLVED_CALENDAR"
    early = calendar(sessions=sessions, ambiguous="earliest").availability(left, right)
    late = calendar(sessions=sessions, ambiguous="latest").availability(left, right)
    assert early["open_ns"] == 2 * HOUR and late["open_ns"] == HOUR
    nonexistent = calendar(
        sessions=({"start_second": 6 * 86400 + 150 * 60, "end_second": 6 * 86400 + 4 * 3600},)
    )
    result = classify_gap(ns("2025-03-09T06:00:00Z"), ns("2025-03-09T09:00:00Z"), nonexistent)
    assert result["status"] == "UNRESOLVED_CALENDAR"
    assert result["reason"] == "NONEXISTENT_LOCAL_SESSION_BOUNDARY"


def test_timezone_bytes_and_integer_inputs_are_bound_and_budgeted():
    c = calendar()
    with pytest.raises(ValueError, match="TZIF_HASH"):
        SessionCalendar(c.spec, b"not the declared timezone database")
    raw = c.spec.model_dump()
    raw["effective_start_ns"] = str(raw["effective_start_ns"])
    assert CalendarSpec.model_validate(raw).calendar_hash == c.spec.calendar_hash
    for invalid in (True, 1.0):
        raw["effective_start_ns"] = invalid
        with pytest.raises(ValueError, match="exact integer"):
            CalendarSpec.model_validate(raw)
    for cal in (None, c):
        with pytest.raises(ValueError, match="invalid gap"):
            classify_gap(2, 1, cal)
    with pytest.raises(ValueError, match="QUERY_BUDGET"):
        c.availability(0, 4 * 366 * DAY)
