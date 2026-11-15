# ADR0058 — Calendar gap classification

Status: implemented software scope; T11 full acceptance open.

## Problem

T11 requires that a missing executable quote is classified rather than invented.
The import reported `STRUCTURAL_IMPORT_PASS` while listing "calendar gaps
unclassified" as a standing limitation, so an operator could not distinguish a
genuinely covered month from one with silent holes.

## Decision

`factory/data/gaps.py` classifies every UTC calendar day of the declared period
from observed tick counts only:

- `MISSING` — zero ticks;
- `PARTIAL` — fewer than half the median observed day;
- `COVERED` — otherwise.

The median is taken over **observed** days only, so a period with widespread
outages is not normalised to "covered". `classify_quotes` buckets a quote stream
by UTC day and reports day, tick, covered, partial and missing counts plus a
per-day breakdown.

`factory/operations/import_history.py` now classifies the committed partition
after import and includes the result as `calendar_gaps` in the import report. The
"calendar gaps unclassified" limitation is replaced.

## Safeguards

- Classification is descriptive and uses UTC calendar days only.
- A missing day is reported, never filled with an invented quote;
  `synthesized_quotes` is always 0.
- Weekends and provider holidays appear as `MISSING` unless ticks exist.
- Classification never changes import acceptance and implies no validation.

Observed on a real partition (USDJPY, March 2025, 3.9M ticks): 21 covered, 5
partial (the Sundays, when forex opens) and 5 missing (the Saturdays).

Evidence: docs/milestone-historical-screen-cohorts.md.
