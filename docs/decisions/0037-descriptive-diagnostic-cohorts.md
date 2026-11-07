# ADR0037 — Descriptive diagnostic cohort aggregation

Status: implemented software scope; full scientific acceptance open.

## Problem

Per-trade diagnostics existed (`diagnostics/v2-stop-role-cohorts`), but nothing
aggregated them into the session, side, path-excursion, failure-pattern and
recovery cohorts the research workflow needs. Without aggregation, a retained
training result could only be read one trade at a time.

## Decision

`factory/diagnostics/cohorts.py` aggregates one retained, verified, training-only
native result into a `diagnostic-cohorts/v1` report:

- declared UTC hour session buckets (ASIA/EUROPE/AMERICAS/OFFSHORE);
- long/short side cohorts;
- stop and timeout class counts plus failure-pattern grouping;
- MFE/MAE excursion means in stop-distance R;
- hold-duration mean/median/max;
- equity max drawdown and recovery-event count;
- closed/open/unresolved trade counts.

The report is content-addressed, immutable, retained under
`artifacts/cohorts/` with an immutable audit event. Repeated identical requests
return the same report.

## Safeguards

- Only retained experiments with an intact artifact hash are aggregated; a
  corrupted or failed-checks artifact is refused.
- Only `train_only` windows are accepted. Protected evaluation and holdout
  windows are never read.
- Session buckets are declared UTC hour ranges, explicitly **not** a verified
  broker calendar; captured TZif session rules remain the authority.
- Cost sensitivity is reported as not measured: it requires repeated native
  replay under varied cost policies, not one training result.
- `descriptive_only` is always true. Aggregation never qualifies, ranks or
  promotes a strategy, and never replaces authoritative native replay.

CLI `diagnose-cohorts` and authenticated API
`POST /api/v1/research/diagnostic-cohorts` expose the report.

Evidence: docs/milestone-historical-screen-cohorts.md.
