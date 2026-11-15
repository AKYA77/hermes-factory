# ADR0045 — Annual and pooled evaluation reporting

Status: implemented software scope; full scientific acceptance open.

## Problem

The blueprint requires separate yearly reports plus annual and pooled reporting.
Retained independent evaluations carried per-window results, but nothing
aggregated them by calendar year or pooled, so yearly comparisons could not be
read from retained evidence.

## Decision

`annual-pooled-reporting/v1` aggregates retained `evaluation_results` by the UTC
year of each contract window start and pooled:

- evaluation count, window count, completed trades, wins, losses and win rate;
- summed ending equity.

Reports are content-addressed, immutable and retained under
`artifacts/annual-reporting/` with an immutable audit event. Repeated identical
requests return the same report. An empty evaluation set yields empty buckets and
a null pooled win rate rather than an invented figure.

## Safeguards

- `qualification_authorized` is always false and `descriptive_only` always true.
- Calendar-year buckets are UTC window starts, not broker reporting periods.
- Pooled figures are not a paired or significance-tested comparison.
- No protected evaluation or holdout window is reinterpreted.
- Aggregates never qualify, rank or promote a strategy.

CLI `annual-reporting` and authenticated API
`POST /api/v1/research/annual-reporting` expose the report.

Evidence: docs/milestone-historical-screen-cohorts.md.
