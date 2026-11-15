# ADR0043 — Multiple-testing safeguards for candidate selection

Status: implemented software scope; full scientific acceptance open.

## Problem

The blueprint requires multiple-testing safeguards and global
candidate-selection controls. Nothing counted the candidate family or applied a
correction, so an uncorrected descriptive pass count could be read as stronger
evidence than the family size supports.

## Decision

`multiple-testing/v1` reports, for a supplied candidate family:

- the number of candidates;
- uncorrected passes at the family-wise alpha;
- Bonferroni passes and the corrected threshold;
- Benjamini-Hochberg passes at the requested false discovery rate.

`benjamini_hochberg` and `bonferroni` are pure exact-rational functions over the
supplied p-values. Candidate ids and p-values must align, ids must be distinct
effective experiments, and p-values must lie in [0,1].

Reports are content-addressed, immutable and retained under
`artifacts/multiple-testing/` with an immutable audit event. Repeated identical
requests return the same report.

## Safeguards

- `qualification_authorized` is always false and `descriptive_only` always true.
- Correction applies only to the supplied family; it is not a global correction
  across every experiment ever run.
- Correlated candidates and labels are not independent tests.
- A corrected pass is not qualification, ranking or promotion, and remains
  evidence about the sampled historical period.

CLI `multiple-testing` and authenticated API
`POST /api/v1/research/multiple-testing` expose the report.

Evidence: docs/milestone-historical-screen-cohorts.md.
