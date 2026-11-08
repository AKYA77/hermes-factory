# ADR0054 — Installed-operations doctor report

Status: implemented software scope; full operational acceptance open.

## Problem

`factory.cli doctor` reported only OS, Python, CPU, RAM and free disk, then
exited 1. It could not show whether the installed state was actually sound, so
an operator had no pre-flight view of the database, catalog or toolchain.

## Decision

`doctor` now reports, in one JSON document:

- host: OS, machine, logical CPUs, RAM bytes, free disk bytes;
- toolchain: Python version against the required 3.12, and the resolved Node
  version (or null when unavailable);
- database: presence, `PRAGMA integrity_check`, job and experiment counts, and the
  highest applied schema migration;
- catalog: partition, row and byte totals from the source registry;
- source fidelity labels present in the catalog;
- `operation_ready: false` with the standing reason.

The command still exits 1: it is a pre-flight report, not a readiness claim.

## Safeguards

- Read-only; nothing is mutated or repaired.
- A missing Node or database is reported as absent, never fatal.
- `operation_ready` stays false until the release gates pass.
- No production release exists yet.

Observed on this host: Python 3.12.3, Node v26.7.0, 6 CPUs, 12.5 GB RAM, 87 GB
free, database integrity ok with 13 migrations, 32 catalog partitions holding
92.4M rows and 1.2 GB, fidelity `SOURCE_BID_ASK`.

Evidence: docs/milestone-historical-screen-cohorts.md.
