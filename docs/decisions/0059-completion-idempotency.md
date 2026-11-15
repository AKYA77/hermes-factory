# ADR0059 — Completion idempotency after worker restart

Status: implemented software scope; T03 full acceptance open.

## Problem

T03 requires that a worker restarted after a partial commit produces no duplicate
run, trade or attempt counts. The fenced-restart path was tested — a stale lease
is rejected and the job is re-claimed — but nothing verified what happens when a
worker dies **after** the experiment row lands and **before** the job is marked
`COMPLETED`. That is exactly the window where a naive retry would duplicate
results.

## Decision

`tests/integration/test_completion_idempotency.py` exercises the window directly:

1. run a full search cycle to a `COMPLETED` job with one experiment and one
   attempt;
2. re-queue the job as if the lease had expired after the experiment row landed;
3. claim it again and call `complete_experiment` with the same contract, result
   and artifact hash.

Assertions: the experiment count is unchanged, the cost-label audit count is
unchanged, exactly one additional attempt is recorded, and the job ends
`COMPLETED`.

## Safeguards

- `complete_experiment` already refuses a stale lease (`STALE_LEASE`) and raises
  `immutable experiment completion conflict` if the stored row differs; this test
  confirms the identical-content path is a no-op rather than a duplicate.
- Attempt counts still increase: a retry is a real attempt, not an invisible one.
- No production rollback or service quiescence is implied.

Evidence: docs/milestone-historical-screen-cohorts.md.
