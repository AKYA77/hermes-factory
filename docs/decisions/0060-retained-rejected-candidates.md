# ADR0060 — Retained rejected candidates

Status: implemented software scope; T14 full acceptance open.

## Problem

T14 requires that a poor training score is retained, a failed out-of-sample run
is not validated, and nothing is silently discarded. The instrument leaderboard
skips rows whose `scenario` is not `historical-pessimistic/v1` or whose
`fill_version` differs, and deduplicates by `strategy_id` keeping only the most
recent row. Those candidates vanished without a trace.

## Decision

`factory/ranking/retained.py` — `retained-rejected-candidates/v1` reports **every**
experiment row for an instrument with:

- its status, synthetic flag and metrics;
- the list of exclusion reasons (`EXECUTION_VERSION_MISMATCH`,
  `NON_PESSIMISTIC_SCENARIO`, `FAILED_CHECKS`, `INSUFFICIENT_EVIDENCE`);
- a `leaderboard_eligible` flag;
- aggregate counts by reason.

Reports are content-addressed, immutable and retained under
`artifacts/retained-candidates/` with an immutable audit event.

## Safeguards

- Every candidate row is retained and reported, never discarded.
- A poor training score stays visible with its metrics.
- A failed out-of-sample run is not validated and is not dropped.
- Exclusion reasons describe leaderboard eligibility only; they are not a
  scientific judgement.
- `qualification_authorized` is always false and `descriptive_only` always true.

CLI `retained-candidates` and authenticated API
`POST /api/v1/research/retained-candidates` expose the report.

Evidence: docs/milestone-historical-screen-cohorts.md.
