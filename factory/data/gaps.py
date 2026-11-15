"""Calendar gap classification for imported partitions.

A gap is classified from observed tick counts only. Missing days are reported as
missing; no quote is ever synthesised, interpolated or invented to fill them.
"""

from datetime import date, datetime, timezone
import statistics

MISSING = "MISSING"
PARTIAL = "PARTIAL"
COVERED = "COVERED"
PARTIAL_FRACTION = 0.5


def classify_days(counts_by_day, year, month):
    """Classify each calendar day of the declared period.

    `counts_by_day` maps an ISO date string to its observed tick count. Days with
    no ticks are MISSING. A day below half the median observed day is PARTIAL.
    The median is taken over observed days only, so a period with widespread
    outages is not silently normalised to "covered".
    """
    observed = [count for count in counts_by_day.values() if count > 0]
    threshold = statistics.median(observed) * PARTIAL_FRACTION if observed else 0
    rows = []
    for day in range(1, 32):
        try:
            stamp = date(year, month, day)
        except ValueError:
            break
        count = counts_by_day.get(stamp.isoformat(), 0)
        if count == 0:
            state = MISSING
        elif count < threshold:
            state = PARTIAL
        else:
            state = COVERED
        rows.append({"date": stamp.isoformat(), "ticks": count, "state": state})
    return rows


def classify_quotes(instrument, year, month, quotes):
    """Bucket a quote stream by UTC calendar day and classify the period."""
    counts = {}
    for quote in quotes:
        day = datetime.fromtimestamp(quote.event_ts_utc_ns / 1e9, timezone.utc).date()
        key = day.isoformat()
        counts[key] = counts.get(key, 0) + 1
    rows = classify_days(counts, year, month)
    return {
        "instrument": instrument,
        "year": year,
        "month": month,
        "days": len(rows),
        "ticks": sum(counts.values()),
        "covered": sum(1 for row in rows if row["state"] == COVERED),
        "partial": sum(1 for row in rows if row["state"] == PARTIAL),
        "missing": sum(1 for row in rows if row["state"] == MISSING),
        "partial_threshold_ticks": statistics.median(
            [count for count in counts.values() if count > 0]
        )
        * PARTIAL_FRACTION
        if any(count > 0 for count in counts.values())
        else 0,
        "rows": rows,
        "synthesized_quotes": 0,
        "limitations": [
            "Classification is descriptive and uses UTC calendar days only",
            "A missing day is reported, never filled with an invented quote",
            "Weekends and provider holidays appear as MISSING unless ticks exist",
            "A period with widespread outages is not normalised to covered",
        ],
    }
