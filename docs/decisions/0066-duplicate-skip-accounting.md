# ADR0066 — Duplicate-skip accounting coverage

Status: implemented software scope; T17 full acceptance open.

## Problem

T17 requires that a duplicate skip does not count as a detailed run and that a
false-negative sample is evaluated. The dedup path existed — a repeated spec is
recorded as `PRUNED` with reason `EXACT_DUPLICATE_SPEC` — but nothing verified that
the skip produced no job and no experiment, or that the research status counted
it as an exact duplicate.

## Decision

`tests/integration/test_search.py` gains
`test_T17_duplicate_skip_is_not_a_detailed_run`:

- the study is pinned with a monkeypatched `rebuild_study` so two consecutive
  asks propose the same spec;
- the second ask is reported as `duplicate: true` and recorded as `PRUNED` with
  reason `EXACT_DUPLICATE_SPEC`;
- no job and no experiment exist, proving the skip is not a detailed run;
- `research_status` reports `exact_duplicates_skipped == 1`.

## Safeguards

- The pinned study is a test fixture only; production proposal remains the
  deterministic TPE study.
- The test asserts the absence of both a job and an experiment, so a partial
  implementation that enqueues but does not run still fails.
- Counting a duplicate as a detailed run would be a silent evidence inflation;
  the status assertion guards the accounting.

Evidence: docs/milestone-historical-screen-cohorts.md.
