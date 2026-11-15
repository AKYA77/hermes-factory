# ADR0041 — Improvement lineage reconstruction

Status: implemented software scope; full scientific acceptance open.

## Problem

`improvement/v1` persists immutable plans, edges and outcomes, but nothing
reconstructed the parent-to-child tree. A policy with many parents and children
could not be read as a lineage, so it was hard to see which hypotheses were
tested, on which parents, and with what result.

## Decision

`improvement-lineage/v1` reconstructs the retained tree for one improvement
policy:

- plans with their parent run and measured generation CPU;
- each plan's children with child strategy hash, child experiment hash, the
  stated hypothesis, the exact changed fields, the parameter summary and the
  outcome status;
- aggregate counts: plans, distinct parents, children and outcome status
  distribution.

Reports are content-addressed, immutable and retained under
`artifacts/lineage/` with an immutable audit event. Repeated identical requests
return the same report. A policy with no retained plans is refused.

## Safeguards

- `descriptive_only` and `independently_validated: false` are always set.
- Every child is explicitly marked `training_only`.
- A child marked `TRAIN_IMPROVED_ONLY` is not independently validated; the report
  says so.
- Correlated settings move together, so changed fields are not causal effects.
- No protected evaluation or holdout window is read.
- Lineage never ranks, qualifies or promotes a strategy.

CLI `improvement-lineage` and authenticated API
`POST /api/v1/research/improvement-lineage` expose the report.

Evidence: docs/milestone-historical-screen-cohorts.md.
