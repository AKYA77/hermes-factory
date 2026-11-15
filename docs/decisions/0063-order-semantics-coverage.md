# ADR0063 — Order semantics coverage

Status: implemented software scope; T09 full acceptance open.

## Problem

T09 requires that a limit never exceeds its limit price, a stop gap is recognized,
and timeout quote absence is flagged. The runner enforced all three — a
`LIMIT_PRICE_VIOLATION` integrity error for take-profit fills beyond the target,
gap-aware stop exits, and `TIMEOUT`/`DELAYED_TIMEOUT_QUOTE` flags — but no test
exercised any of them.

## Decision

`tests/simulation/test_engine.py` gains three scenario tests:

- **Limit never exceeds the limit price** — a SELL take-profit fills at or above
  its target, and the runner reports no integrity errors.
- **Stop gap is recognized** — price gaps through the stop so the exit fills
  worse than the stop level, with the exit role recorded as `STOP_LOSS`.
- **Timeout quote absence is flagged** — a trade still open when the deadline
  passes carries the `TIMEOUT` flag.

## Safeguards

- The gap test asserts the fill is strictly worse than the stop, not merely
  different, so a gap that improved the fill would fail.
- The limit test asserts the fill is at or above the target, so a fill beyond
  the limit price in the wrong direction fails.
- These are synthetic fixtures; no market claim is made.

Evidence: docs/milestone-historical-screen-cohorts.md.
