# ADR0061 — Source coverage report

Status: implemented software scope; T05 full acceptance open.

## Problem

T05 requires that a quarantined quote cannot be selected and that a new partition
updates coverage and invalidation. Quarantine enforcement existed in
`reject_quarantined`, but nothing reported source coverage, so an operator could
not see which periods were observed, which were selected, or which observations
were blocked by an unresolved quarantine.

## Decision

`SourceVersions.coverage()` reports, per instrument:

- observed, selected and unresolved-quarantined counts;
- each observation's period (`start_ns`/`end_ns`), dataset hash, selection state
  and quarantine state.

`selected` is derived from the latest selection per slot, so a re-selection
updates coverage. `unresolved_quarantined` counts only quarantines without a
resolution, so a resolved quarantine stops blocking.

API `GET /api/v1/source-coverage` and CLI `source-coverage` expose the report.

## Safeguards

- Coverage describes immutable source observations; it is not historical
  approval or complete market coverage.
- A quarantine is reflected only while unresolved.
- A selection is an operator choice and is reported as such.
- No partition is auto-selected or approved by this report.

Observed on the live state root: EURUSD has 5 observed monthly periods, none
selected and none quarantined.

Evidence: docs/milestone-historical-screen-cohorts.md.
