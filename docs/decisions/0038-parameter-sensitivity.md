# ADR0038 — Parameter sensitivity for controlled improvements

Status: implemented software scope; full scientific acceptance open.

## Problem

`improvement/v1` already runs bounded controlled children and records the changed
fields, hypothesis and outcome per edge. But nothing summarized how training
outcomes varied with those controlled parameter changes, so a parent with many
children could not be read as a sensitivity profile.

## Decision

`improvement-sensitivity/v1` reports, per improvement policy:

- comparisons grouped by the exact changed-field set;
- outcome status counts per group;
- mean/min/max `ending_equity_delta` per group;
- hypothesis counts across the policy.

Reports are content-addressed, immutable and retained under
`artifacts/sensitivity/` with an immutable audit event. Repeated identical
requests return the same report. A policy with no retained outcomes is refused.

## Safeguards

- `descriptive_only` and `independently_validated: false` are always set.
- A parameter change is not a causal estimate: correlated settings move together
  and only a small number of children are generated per parent.
- Small comparison counts cannot support a stability claim, and the report says
  so.
- No protected evaluation or holdout window is read. Sensitivity never ranks,
  qualifies or promotes a strategy, and it does not feed the optimizer.
- Training-only evidence only; no recursive runaway is possible because the
  report reads retained edges and never generates children.

CLI `improvement-sensitivity` and authenticated API
`POST /api/v1/research/improvement-sensitivity` expose the report.

Evidence: docs/milestone-historical-screen-cohorts.md.
