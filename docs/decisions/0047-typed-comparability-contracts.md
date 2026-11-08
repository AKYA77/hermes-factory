# ADR0047 — Typed comparability contracts

Status: implemented software scope; full scientific acceptance open.

## Problem

The blueprint requires comparability contracts before candidates are compared.
ADR0036 compared two cohorts pairwise, but nothing recorded a durable, typed
assertion of which evaluation contexts a candidate's evidence may be compared
against.

## Decision

`comparability-contract/v1` registers a typed contract naming:

- the instrument, dataset hash and evaluation window;
- the peer context hashes the window is comparable with;
- any protected windows that must never be entered.

The contract is stored in a new migration `013_comparability_contracts.sql`
(`comparability_contracts` and `comparability_contract_peers`, both immutable by
trigger), and its report is content-addressed and retained under
`artifacts/comparability-contracts/`. Re-registering an identical context is
idempotent and reports `already_registered`.

## Safeguards

- `qualification_authorized` is always false and `descriptive_only` always true.
- A contract is a guard, not a licence: it asserts only that two contexts may be
  compared.
- An evaluation window that overlaps a protected window is refused at validation.
- Comparability is not evidence that a candidate would persist.
- The contract never qualifies, ranks or promotes a strategy.

CLI `comparability-contract` and authenticated API
`POST /api/v1/research/comparability-contract` expose the report.

Evidence: docs/milestone-historical-screen-cohorts.md.
