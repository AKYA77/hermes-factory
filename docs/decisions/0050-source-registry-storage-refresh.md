# ADR0050 — Data source registry, storage inventory and refresh

Status: implemented software scope; full scientific acceptance open.

## Problem

The blueprint requires source/profile/refresh/storage data APIs. The API exposed
data manifest and quality endpoints, but nothing listed committed partitions as
sources, reported storage inventory, or re-verified partition digests on demand.

## Decision

`factory/data/sources.py` provides a read-only `SourceRegistry` over the catalog:

- `list()` — one record per committed partition: dataset hash, instrument, rows,
  first/latest timestamps, fidelity, provenance and parquet bytes;
- `detail(identity)` — one source, raising `KeyError` for an unknown hash;
- `storage()` — partition, row and byte totals plus a per-instrument breakdown;
- `refresh()` — re-verifies every partition's parquet digest against its manifest
  and returns a receipt with verified count, mismatches and missing partitions.

A refresh never mutates catalog data.

## Safeguards

- Read-only over committed partitions; a refresh verifies but does not rewrite.
- Corrupt or missing partitions are reported, not repaired.
- Synthetic fixtures are labelled by their manifest fidelity.
- No source is promoted to a validated or market-ready claim.

API `GET /api/v1/sources`, `GET /api/v1/sources/{identity}`, `GET
/api/v1/storage`, `POST /api/v1/refresh` and CLI `sources`, `storage`, `refresh`
expose the reports.

Evidence: docs/milestone-historical-screen-cohorts.md.
