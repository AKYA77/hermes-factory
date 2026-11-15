# ADR0051 — Instrument profile registry and integrity

Status: implemented software scope; full scientific acceptance open.

## Problem

The blueprint requires a profile API. Nothing listed the known instrument
profiles, their provenance, or a content hash that could be checked for drift.

## Decision

`factory/instruments/registry.py` exposes:

- `registry()` — one entry per known symbol: version, synthetic flag, source,
  tick/pip sizes, price scale, currencies, volume bounds, margin rate, minimum
  stop ticks and a content hash of the profile;
- `detail(symbol)` — one profile, raising `KeyError` for an unknown symbol;
- `integrity()` — recomputes every profile hash and reports drift, the model
  version, and synthetic/non-synthetic counts.

## Safeguards

- Synthetic profiles are test-only and are never broker metadata.
- Gold requires its own reviewed cost-equivalent/units definition.
- Choosing this model does not certify historical broker feasibility.
- A profile is a declared model constraint, not a validated trading spec.

API `GET /api/v1/profiles`, `GET /api/v1/profiles/{symbol}`, `GET
/api/v1/profile-integrity` and CLI `profiles`, `profile-integrity` expose the
reports.

Evidence: docs/milestone-historical-screen-cohorts.md.
