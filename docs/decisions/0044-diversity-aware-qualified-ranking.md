# ADR0044 — Diversity-aware qualified shortlist selection

Status: implemented software scope; full scientific acceptance open.

## Problem

The blueprint requires a diversity-aware top-five report. The existing
instrument leaderboard returned the first five candidates by tier ordering with
no diversity constraint, so a single operator/timeframe could fill every slot.

## Decision

`qualified-ranking/v1` applies a greedy diversity guard over the already-ranked
candidate list for one instrument:

- candidates are ordered by the existing tier-then-metrics policy;
- a candidate is selected while slots remain and its `(operator, timeframe)` key
  has not reached `per_key_limit`;
- candidates rejected by the key limit are reported as `DIVERSITY_LIMIT` and those
  rejected by slots as `SLOT_LIMIT`, with the per-key counts.

Reports are content-addressed, immutable and retained under
`artifacts/qualified-ranking/` with an immutable audit event. Repeated identical
requests return the same report. An empty shortlist is valid.

## Safeguards

- `qualification_authorized` is always false and `descriptive_only` always true.
- Diversity is by operator and timeframe only, not by parameter distance.
- Selection does not qualify, promote or validate a strategy.
- Dataset and evaluation-window comparability remains a separate gate.
- Candidates are retained training experiments under the current execution
  version and the pessimistic scenario only.

CLI `qualified-ranking` and authenticated API
`POST /api/v1/research/qualified-ranking` expose the report.

Evidence: docs/milestone-historical-screen-cohorts.md.
