# ADR0067 — MFE/MAE path coverage

Status: implemented software scope; T12 full acceptance open.

## Problem

T12 requires that immediate stop, favorable-then-stop, near-miss, timeout, missing
path and both long and short directions all measure correctly. Only the
favorable-then-stop path had a test; the remaining paths were unexercised, so a
regression in the excursion tags or the R-multiples would pass unnoticed.

## Decision

`tests/simulation/test_engine.py` gains four tests:

- **Immediate stop** — a stop hit within the fast-stop window with zero
  favourable excursion is tagged `FAST_STOP` and reports `MEASURED`.
- **Near miss threshold** — a trade reaching 93% of its target is tagged
  `TARGET_NEAR_MISS`, while one reaching 87% is not; both remain
  `FAVORABLE_THEN_STOP`. This pins the 90% boundary rather than a loose check.
- **Timeout and short paths** — a deadline exit carries `TIMEOUT`, and a short
  stop-loss produces a negative MAE with `FAST_STOP`.
- **Missing path** — an empty path is `INCONCLUSIVE` with `UNRESOLVED_PATH` and
  zero points, never a fabricated measurement.

## Safeguards

- The near-miss test asserts both sides of the threshold, so moving the
  boundary in either direction fails.
- A missing path must never produce a numeric excursion; the test asserts the
  inconclusive status and the unresolved tag.
- These are synthetic fixtures; no market claim is made.

Evidence: docs/milestone-historical-screen-cohorts.md.
