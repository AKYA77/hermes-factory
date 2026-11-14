# ADR0042 — Independent confirmation of training improvements

Status: implemented software scope; full scientific acceptance open.

## Problem

`improvement/v1` labels a child `TRAIN_IMPROVED_ONLY` when it improves on its
parent's training span. Nothing bound that label to an independent evaluation,
so a training gain could be mistaken for independent evidence.

## Decision

`improvement-confirmation/v1` binds one improvement edge to one retained
independent evaluation. Confirmation is refused unless:

- the edge outcome is `TRAIN_IMPROVED_ONLY` (only promotions need confirmation);
- the evaluation exists and its artifact hash verifies;
- the evaluation is not the training experiment itself;
- no evaluation window overlaps any training window;
- the evaluation uses the same admitted canonical dataset.

The report records the training and evaluation windows, the disjointness and
dataset checks, whether the evaluation's marked equity exceeded the initial
equity, and a `confirmed` boolean. Reports are content-addressed, immutable and
retained under `artifacts/confirmations/` with an immutable audit event.

## Safeguards

- `qualification_authorized` is always false and `descriptive_only` is always
  true. Confirmation is not qualification, ranking or promotion.
- Only window disjointness and dataset identity are checked; the protected
  evaluation itself is not reinterpreted.
- Correlated settings and overlapping market conditions are not independent.
- Independent confirmation does not satisfy global regime or source validation.

CLI `improvement-confirmation` and authenticated API
`POST /api/v1/research/improvement-confirmation` expose the report.

Evidence: docs/milestone-historical-screen-cohorts.md.
