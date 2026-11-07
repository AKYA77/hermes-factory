# ADR0036 — Frozen screening comparability and selection-bias reporting

Status: implemented software scope; full scientific acceptance open.

## Problem

Screening cohorts are frozen before outcomes (ADR0033/0035), but nothing stated
whether two cohorts could be compared at all, or how much of a sampled frame was
actually observed. Without that, descriptive screening statistics could be
silently pooled across incompatible evaluation semantics, and a small audited
subset could be presented as if it described the whole frame.

## Decision

`screen-comparability/v1` requests name two to sixteen frozen cohorts plus an
actor and an explicit no-pooling attestation. The report:

- re-verifies every cohort body hash and dispatches on `schema_version`;
- compares the frozen subject contract (instrument hash, operator, timeframe,
  confirmations, scenario, code revision, cost-label policy hash) and reports
  pairwise comparability with the exact differing fields;
- reports selection-bias counters: distinct effective experiments, selected for
  native audit, selected and observed, selected but unobserved, unselected
  frame members and the selection ratio;
- is content-addressed, immutable and retained under `artifacts/comparability/`
  with an immutable audit event.

`pooled_claim_authorized` is always false. Comparability is
evaluation-semantics only. It never authorizes pooling screening observations
into a qualification, ranking or performance claim, and it never reinterprets a
consumed native evaluation.

## Safeguards

- Unselected frame members have no native observation and cannot support a
  false-negative estimate; the report states this.
- Correlated strategies and labels are not IID, so descriptive intervals remain
  descriptive.
- Reused cohort identities add no independent observations.
- Approximate pruning stays unauthorized; the report repeats the cohort
  disposition rather than replacing it.

CLI `screen-comparability`, authenticated API
`POST /api/v1/research/screen-comparability` and a dashboard comparability panel
expose the report. No fill, risk, cost, score, canonical data or validation
criterion changes.

Evidence: docs/milestone-historical-screen-cohorts.md.
