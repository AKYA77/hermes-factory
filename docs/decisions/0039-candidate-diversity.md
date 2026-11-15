# ADR0039 — Diversity-aware candidate reporting

Status: implemented software scope; full scientific acceptance open.

## Problem

The search loop generates many trials, but nothing reported how broadly those
trials covered the parameter space. A search that collapsed onto a few
near-duplicate parameter sets would look productive by trial count while actually
exploring a tiny region.

## Decision

`candidate-diversity/v1` reports, for one registered search protocol:

- trial counts by outcome (COMPLETE / PRUNED / FAIL / PENDING);
- distinct parameter sets and the largest single-set share;
- a `concentrated` flag when the largest set exceeds half the trials;
- distinct strategy lookbacks, operator and timeframe distributions;
- per-field distinct-value counts and coarse coverage buckets for lookback,
  threshold and stop distance.

Reports are content-addressed, immutable and retained under
`artifacts/diversity/` with an immutable audit event. Repeated identical
requests return the same report. A protocol with no retained trials is refused.

## Safeguards

- `descriptive_only` is always true.
- A concentrated sample is explicitly **not** evidence that a region is
  unproductive; the report says so.
- Distinct parameter counts do not measure statistical independence.
- No protected evaluation or holdout window is read.
- Diversity never ranks, qualifies or promotes a candidate and never feeds the
  optimizer.

CLI `candidate-diversity` and authenticated API
`POST /api/v1/research/candidate-diversity` expose the report.

Evidence: docs/milestone-historical-screen-cohorts.md.
