"""Calendar gap classification for imported partitions."""

from datetime import datetime, timezone

from factory.data import Quote
from factory.data.gaps import COVERED, MISSING, PARTIAL, classify_days, classify_quotes


def tick(ns):
    return Quote("EURUSD", ns, 100000, 100010, 1000000, "HistData.com", "batch", 0)


def test_missing_days_are_reported_not_filled():
    counts = {f"2025-01-{day:02}": 1000 for day in range(1, 11)}
    rows = classify_days(counts, 2025, 1)
    assert len(rows) == 31
    assert [row["state"] for row in rows[:10]] == [COVERED] * 10
    assert sum(1 for row in rows if row["state"] == MISSING) == 21
    assert all(row["ticks"] == 0 for row in rows if row["state"] == MISSING)


def test_partial_days_are_classified_separately():
    counts = {f"2025-01-{day:02}": 1000 for day in range(1, 11)}
    counts["2025-01-05"] = 10
    rows = classify_days(counts, 2025, 1)
    assert rows[4]["state"] == PARTIAL
    assert rows[0]["state"] == COVERED


def test_all_missing_period_is_not_normalised():
    rows = classify_days({}, 2025, 2)
    assert len(rows) == 28
    assert all(row["state"] == MISSING for row in rows)


def test_classify_quotes_buckets_by_utc_day():
    first = int(datetime(2025, 1, 2, 10, 0, tzinfo=timezone.utc).timestamp() * 1e9)
    second = int(datetime(2025, 1, 3, 10, 0, tzinfo=timezone.utc).timestamp() * 1e9)
    quotes = [tick(first)] * 1000 + [tick(second)] * 10
    report = classify_quotes("EURUSD", 2025, 1, quotes)
    assert report["ticks"] == 1010
    assert report["covered"] == 1
    assert report["partial"] == 1
    assert report["missing"] == 29
    assert report["synthesized_quotes"] == 0
    assert report["days"] == 31
