# ADR0062 — Adverse fill coverage for entry and exit

Status: implemented software scope; T08 full acceptance open.

## Problem

T08 requires that long and short entry and exit adjust exactly two pips where
eligible, using correct units. The unit test covered the pricing function for
entry only; the exit side — where the sign flips and a take-profit limit must
*not* be adjusted — had no coverage, so a regression in exit pricing or in the
runner's exit verification would pass unnoticed.

## Decision

`tests/simulation/test_engine.py` gains two scenario tests:

- **Long and short stop-loss exits.** Entry and exit fills are asserted to the
  exact tick, each carrying `actual_adverse_adjustment` of exactly two pips:
  long entry pays ask + 2 pips, long exit receives bid − 2 pips; short entry
  sells bid − 2 pips, short exit buys ask + 2 pips. The runner's own integrity
  check reports no errors.
- **Take-profit limit exit.** A limit guarantees its price, so the exit fill
  carries no adverse adjustment and the fill trace reports zero slippage, while
  the entry still adjusts two pips.

## Safeguards

- "Where eligible" is honoured: market and stop-market orders adjust; limits do
  not.
- The exact two-pip figure is asserted, not a bound, so a silent drift in the
  slip width fails the test.
- Both directions are covered, so a sign error in either leg fails.
- These are synthetic fixtures; no market claim is made.

Evidence: docs/milestone-historical-screen-cohorts.md.
