# ADR0049 — Qualified ranking over independent evaluations

Status: implemented software scope; full scientific acceptance open.

## Problem

The blueprint requires qualified ranking. ADR0044 ranked training experiments
descriptively, but nothing ranked the candidates that had actually passed through
retained non-synthetic independent evaluation.

## Decision

`independent-qualified-ranking/v1` ranks retained non-synthetic independent
evaluations:

- joins `evaluation_results` to `experiments` on the evaluation identity, so only
  evaluations with a retained experiment are ranked;
- excludes synthetic evaluations;
- ranks by ending equity, then strategy and evaluation identity;
- applies the same `(operator, timeframe)` diversity guard as ADR0044, reporting
  `DIVERSITY_LIMIT` and `SLOT_LIMIT` exclusions.

Reports are content-addressed, immutable and retained under
`artifacts/independent-ranking/` with an immutable audit event.

## Safeguards

- `qualification_authorized` is always false and `descriptive_only` always true.
- Diversity is by operator and timeframe only, not by parameter distance.
- A ranked candidate is not qualified or validated.
- Pooled equity is not a paired or significance-tested comparison.
- Protected holdout and regime gates remain separate.

CLI `independent-ranking` and authenticated API
`POST /api/v1/research/independent-ranking` expose the report.

Evidence: docs/milestone-historical-screen-cohorts.md.
