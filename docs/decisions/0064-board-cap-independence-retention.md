# ADR0064 — Board cap, independence and retention coverage

Status: implemented software scope; T16 full acceptance open.

## Problem

T16 requires eight separate boards, at most five candidates per instrument, fewer
than 70% of candidates retained, and empty slots left empty. Only the empty-board
case was tested. Nothing verified the five-slot cap on a populated board, that
boards are independent, or the retention ratio — so an off-by-one in the cap or a
leak of candidates across instruments would pass unnoticed.

## Decision

`tests/integration/test_boards.py` adds three tests against `factory.ranking.leaderboard`:

- **Cap and slots** — after inserting eight candidates for one instrument, the
  board returns exactly `max_slots` (5) candidates and reports no
  other-execution exclusions.
- **Independence** — candidates added for EURUSD and GBPUSD appear only on their
  own boards, and the two boards' strategy-id sets are disjoint.
- **Retention below 70%** — with eleven candidates the board returns five, a
  retention ratio strictly below 0.7.

## Safeguards

- The cap test asserts the exact slot count, not an upper bound, so an
  under-filled board fails.
- Independence is asserted by disjoint strategy-id sets, so a candidate leaking
  across instruments fails.
- Retention is asserted strictly below 70%, matching the requirement.
- These are synthetic fixtures; no market claim is made.

Evidence: docs/milestone-historical-screen-cohorts.md.
