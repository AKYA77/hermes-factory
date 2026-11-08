# ADR0069 — Purge/embargo fold geometry coverage

Status: implemented software scope; T15 full acceptance open.

## Problem

T15 requires separate annual and WFO-quarter splits with purge/embargo and
holdout state. `quarter_folds` and `purge` had unit tests and the protocol test
asserted fold counts, but nothing verified that a configured purge and embargo
actually shrink **every** fold, that the folds stay non-overlapping, or that the
holdout window is left untouched.

## Decision

`tests/integration/test_scientific_protocol.py` gains
`test_T15_purge_and_embargo_shrink_every_fold`:

- build a protocol with `purge_seconds=86400` and `embargo_seconds=3600`;
- assert every fold has `train_end == oos_start - (purge + embargo)`;
- assert each fold still has a non-empty train span and out-of-sample span;
- assert consecutive folds meet exactly at the embargo boundary, so no
  out-of-sample period overlaps or leaves an unaccounted gap;
- assert the holdout start equals the final fold's out-of-sample end, so
  purge/embargo never shrink the holdout.

## Safeguards

- The gap assertion uses the configured purge plus embargo exactly, so a silent
  change to either constant fails.
- The holdout assertion is independent of the purge/embargo values, so a fold
  change that encroaches on the holdout fails.
- These are synthetic multi-quarter fixtures; no market claim is made.

Evidence: docs/milestone-historical-screen-cohorts.md.
