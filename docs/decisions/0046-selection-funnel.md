# ADR0046 — Global candidate-selection funnel

Status: implemented software scope; full scientific acceptance open.

## Problem

The blueprint requires global candidate-selection controls. Counts existed in
several places — search trials, cohort memberships, improvement outcomes — but no
single funnel showed how many distinct effective candidates were considered,
selected for native audit, observed and promoted.

## Decision

`selection-funnel/v1` reports, over the retained state:

- search trials and distinct trial configurations;
- distinct effective cohort candidates;
- candidates selected for native audit;
- selected candidates with a retained native observation;
- training promotions and how many of those retain an improvement edge;
- a `funnel_complete` flag that is true only when every selected candidate was
  observed.

Reports are content-addressed, immutable and retained under
`artifacts/selection-funnel/` with an immutable audit event. Repeated identical
requests return the same report.

## Safeguards

- `qualification_authorized` is always false and `descriptive_only` always true.
- Counts are not independent observations; correlated candidates overlap.
- A promotion is a training-only label, not independent validation.
- The funnel never qualifies, ranks or promotes a strategy.
- Global regime and source validation remain separate gates.

CLI `selection-funnel` and authenticated API
`POST /api/v1/research/selection-funnel` expose the report.

Evidence: docs/milestone-historical-screen-cohorts.md.
