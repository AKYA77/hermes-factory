# ADR0065 — Search fairness across protocols

Status: implemented software scope; T18 full acceptance open.

## Problem

T18 requires that no eligible instrument is starved while the queue has work, and
that timeframe choice is searchable. Pending trials were ordered purely by
`created_at`, so a protocol that generated trials quickly could monopolise the
queue and starve an eligible instrument indefinitely.

## Decision

`Search.fair_pending()` orders pending trials by how much each protocol has
already produced (recorded outcomes), then by arrival:

- a protocol that has produced little gets the next turn;
- ties fall back to `created_at` then `trial_id`, so ordering stays deterministic.

`Search.enqueue_pending()` and the coordinator's enqueue loop both use
`fair_pending()`. `Search.pending()` is unchanged and still returns raw FIFO order.

## Safeguards

- This is scheduling fairness only. It never changes what is searchable, what a
  trial may conclude, or the acceptance of its result.
- The production count comes from immutable `search_outcomes` joined to
  `search_trials`, so a recorded outcome cannot be hidden by re-ordering.
- Timeframe remains a searchable dimension of the registered protocol; fairness
  only decides which pending trial runs next.
- A protocol with no recorded outcomes is never deprioritised for being new.

Evidence: docs/milestone-historical-screen-cohorts.md.
