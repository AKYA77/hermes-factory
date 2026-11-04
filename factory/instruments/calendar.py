"""Exact session availability from captured TZif bytes and dated declared rules.

Rules are not verified broker facts merely because this model parses them.
A separate reviewed metadata receipt is required for historical admission.
"""

from datetime import datetime, timedelta, timezone
from bisect import bisect_right
import hashlib
import io
from typing import Literal, Annotated
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator, BeforeValidator

from factory.contracts import Contract, SYMBOLS, fingerprint

SECOND = 10**9
DAY_SECONDS = 86400
WEEK_SECONDS = DAY_SECONDS * 7
MAX_QUERY_NS = 3 * 366 * DAY_SECONDS * SECOND
UTC = timezone.utc


def exact_ns(value):
    if type(value) is int:
        return value
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    raise ValueError("exact integer nanoseconds or decimal string required")


Nanoseconds = Annotated[int, BeforeValidator(exact_ns), Field(ge=0, le=2**63 - 1)]


class WeeklySession(Contract):
    # Monday 00:00 is zero. An end before start wraps into next week.
    start_second: int = Field(ge=0, lt=WEEK_SECONDS, strict=True)
    end_second: int = Field(ge=0, le=WEEK_SECONDS, strict=True)

    @model_validator(mode="after")
    def nonempty(self):
        if self.start_second == self.end_second:
            raise ValueError("empty weekly session; full week is 0..604800")
        return self


class CalendarClosure(Contract):
    start_ns: Nanoseconds
    end_ns: Nanoseconds = Field(gt=0)
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def ordered(self):
        if self.start_ns >= self.end_ns:
            raise ValueError("empty calendar closure")
        return self


class CalendarSpec(Contract):
    schema_version: Literal["session-calendar/v1"] = "session-calendar/v1"
    instrument: str
    version: str = Field(min_length=1, max_length=100)
    timezone: str = Field(min_length=1, max_length=100)
    tzif_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_document_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_citation: str = Field(min_length=1, max_length=2000)
    effective_start_ns: Nanoseconds
    effective_end_ns: Nanoseconds = Field(gt=0)
    weekly_sessions: tuple[WeeklySession, ...] = Field(min_length=1, max_length=64)
    closures: tuple[CalendarClosure, ...] = Field(max_length=2048)
    ambiguous_boundary: Literal["reject", "earliest", "latest"]

    @model_validator(mode="after")
    def coherent(self):
        if self.instrument not in SYMBOLS or self.effective_start_ns >= self.effective_end_ns:
            raise ValueError("invalid instrument/calendar period")
        if any(
            c.start_ns < self.effective_start_ns or c.end_ns > self.effective_end_ns
            for c in self.closures
        ):
            raise ValueError("closure outside declared effective period")
        return self

    @property
    def calendar_hash(self):
        return fingerprint(self)


def merge_spans(spans):
    merged = []
    for start, end in sorted(spans):
        if start >= end:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def subtract_spans(opened, closed):
    """Linear set subtraction of sorted disjoint half-open intervals."""
    index = 0
    for start, end in opened:
        while index < len(closed) and closed[index][1] <= start:
            index += 1
        cursor, other = start, index
        while other < len(closed) and closed[other][0] < end:
            left, right = closed[other]
            if cursor < left:
                yield cursor, min(left, end)
            cursor = max(cursor, right)
            if cursor >= end:
                break
            other += 1
        if cursor < end:
            yield cursor, end


class SessionCalendar:
    def __init__(self, spec, tzif_bytes):
        self.spec = CalendarSpec.model_validate(spec)
        if hashlib.sha256(tzif_bytes).hexdigest() != self.spec.tzif_sha256:
            raise ValueError("CALENDAR_TZIF_HASH_MISMATCH")
        self.tzif_bytes = bytes(tzif_bytes)
        # Never silently use the target host's current timezone database.
        self.zone = ZoneInfo.from_file(io.BytesIO(tzif_bytes), key=self.spec.timezone)
        self.closures = merge_spans((c.start_ns, c.end_ns) for c in self.spec.closures)
        self.calendar_hash = self.spec.calendar_hash

    def _boundary(self, monday, second):
        wall = datetime.combine(monday, datetime.min.time()) + timedelta(seconds=second)
        candidates = set()
        for fold in (0, 1):
            utc = wall.replace(tzinfo=self.zone, fold=fold).astimezone(UTC)
            if utc.astimezone(self.zone).replace(tzinfo=None) == wall:
                # Whole-second schedule boundary; no timestamp float conversion.
                delta = utc - datetime(1970, 1, 1, tzinfo=UTC)
                candidates.add((delta.days * DAY_SECONDS + delta.seconds) * SECOND)
        if not candidates:
            raise ValueError("NONEXISTENT_LOCAL_SESSION_BOUNDARY")
        if len(candidates) > 1 and self.spec.ambiguous_boundary == "reject":
            raise ValueError("AMBIGUOUS_LOCAL_SESSION_BOUNDARY")
        return max(candidates) if self.spec.ambiguous_boundary == "latest" else min(candidates)

    def _known_spans(self, start_ns, end_ns):
        first = datetime.fromtimestamp(start_ns // SECOND, UTC).astimezone(self.zone).date()
        last = datetime.fromtimestamp((end_ns - 1) // SECOND, UTC).astimezone(self.zone).date()
        monday = first - timedelta(days=first.weekday() + 7)
        final_monday = last - timedelta(days=last.weekday())
        spans = []
        while monday <= final_monday:
            for session in self.spec.weekly_sessions:
                end = session.end_second
                if end <= session.start_second:
                    end += WEEK_SECONDS
                left = self._boundary(monday, session.start_second)
                right = self._boundary(monday, end)
                if right <= left:
                    raise ValueError("INVALID_UTC_SESSION_INTERVAL")
                spans.append((max(start_ns, left), min(end_ns, right)))
            monday += timedelta(days=7)
        return list(subtract_spans(merge_spans(spans), self.closures))

    def availability(self, start_ns, end_ns):
        return self.prepare(start_ns, end_ns).availability(start_ns, end_ns)

    def prepare(self, start_ns, end_ns):
        if type(start_ns) is not int or type(end_ns) is not int or not 0 <= start_ns < end_ns:
            raise ValueError("invalid calendar query interval")
        if end_ns - start_ns > MAX_QUERY_NS:
            raise ValueError("CALENDAR_QUERY_BUDGET; query in bounded chunks")
        known_start = max(start_ns, self.spec.effective_start_ns)
        known_end = min(end_ns, self.spec.effective_end_ns)
        spans = self._known_spans(known_start, known_end) if known_end > known_start else []
        return CalendarCoverage(self, start_ns, end_ns, spans)


class CalendarCoverage:
    """One bounded session expansion; subsequent source queries use prefix sums."""

    def __init__(self, calendar, start_ns, end_ns, spans):
        self.calendar = calendar
        self.start_ns, self.end_ns = start_ns, end_ns
        self.spans = tuple(spans)
        self.starts = tuple(start for start, _ in spans)
        total = 0
        prefix = []
        for start, end in spans:
            prefix.append(total)
            total += end - start
        self.prefix = tuple(prefix)

    def _measure(self, ts):
        index = bisect_right(self.starts, ts) - 1
        if index < 0:
            return 0
        start, end = self.spans[index]
        return self.prefix[index] + min(ts - start, end - start)

    def is_open(self, ts):
        if type(ts) is not int or not self.start_ns <= ts < self.end_ns:
            raise ValueError("quote outside prepared calendar interval")
        spec = self.calendar.spec
        if not spec.effective_start_ns <= ts < spec.effective_end_ns:
            return None
        return self._measure(ts + 1) - self._measure(ts) == 1

    def availability(self, start_ns, end_ns):
        if (
            type(start_ns) is not int
            or type(end_ns) is not int
            or not self.start_ns <= start_ns < end_ns <= self.end_ns
        ):
            raise ValueError("gap outside prepared calendar interval")
        spec = self.calendar.spec
        known = max(0, min(end_ns, spec.effective_end_ns) - max(start_ns, spec.effective_start_ns))
        opened = self._measure(end_ns) - self._measure(start_ns)
        return {
            "calendar_hash": self.calendar.calendar_hash,
            "start_ns": start_ns,
            "end_ns": end_ns,
            "open_ns": opened,
            "closed_ns": known - opened,
            "unknown_ns": end_ns - start_ns - known,
            "basis": "captured-TZif/dated-declared-rules; not metadata verification",
        }


def classify_gap(start_ns, end_ns, calendar=None):
    if type(start_ns) is not int or type(end_ns) is not int or not 0 <= start_ns < end_ns:
        raise ValueError("invalid gap interval")
    if calendar is None:
        return {
            "status": "UNKNOWN_CALENDAR",
            "start_ns": start_ns,
            "end_ns": end_ns,
            "open_ns": 0,
            "closed_ns": 0,
            "unknown_ns": end_ns - start_ns,
        }
    try:
        result = calendar.availability(start_ns, end_ns)
    except ValueError as exc:
        return {
            "status": "UNRESOLVED_CALENDAR",
            "reason": str(exc),
            "start_ns": start_ns,
            "end_ns": end_ns,
            "open_ns": 0,
            "closed_ns": 0,
            "unknown_ns": end_ns - start_ns,
        }
    status = (
        "UNKNOWN_EFFECTIVE_PERIOD"
        if result["unknown_ns"]
        else "DECLARED_CLOSED_ONLY"
        if not result["open_ns"]
        else "DECLARED_OPEN_GAP"
        if not result["closed_ns"]
        else "MIXED_OPEN_CLOSED_GAP"
    )
    return {**result, "status": status}
