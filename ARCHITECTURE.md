# Hermes Factory development architecture

> **Superseded in part.** The owner directive of 2026-11-12
> (`docs/source/Owner_Lean_RaptorBT_Final_Directive_2026-11-12.md`, ADR 0071)
> replaces NautilusTrader with one RaptorBT-derived Rust execution engine,
> introduces dynamic M1–D1 signal selection, one accurate testing pipeline, a
> strict 50% verified win-rate gate and a native Rust strategy generator. The
> historical description below is retained for traceability; where it conflicts
> with the directive, the directive governs.

## Current target architecture (2026-11-12)

One Python control plane and one SvelteKit static dashboard. SQLite WAL stores
metadata, queue leases and audit events; canonical quotes are checksummed
Parquet/ZSTD plus immutable source bytes outside Git.

```
verified tick archive
  -> cached M1-D1 features (only the timeframes a strategy requires)
  -> Rust strategy generator (typed declarative expressions)
  -> RaptorBT-derived Rust execution (indexed mode | sequential quote replay)
  -> scientific qualification (strict 50% verified win-rate gate)
  -> diagnostics
  -> next research generation
```

One execution engine, one canonical data source, one shared feature pipeline,
one native generator, one experiment registry, one persistent scheduler and one
validation/ranking system. Python owns orchestration, APIs, persistence,
experiment registration and reporting; Rust owns computation-heavy work. There
are no per-tick Python callbacks in the hot path.

## Historical architecture (directive commit)

One Python control plane and one SvelteKit static dashboard. SQLite WAL stores
metadata, queue leases and audit events; canonical quotes are checksummed
Parquet/ZSTD plus source bytes outside Git. A single sequential coordinator
launches isolated Nautilus workers. All writes use short serialized SQLite
transactions; workers stage content-hashed artifacts and do not write SQLite.

Implemented flow:

```
authenticated typed proposal -> verified dataset + hash checks -> durable job
 -> isolated worker -> shared closed-bar signal interpreter -> Nautilus replay
 -> executable-side diagnostics -> immutable experiment -> per-instrument board
```

The Nautilus stage is the migration target, not the final state. It is removed
only after the parity gate in directive §4 passes.

The API is under /api/v1, documented by generated schemas and OpenAPI in schemas/.
No route accepts official metric values. The dashboard shows exact responses,
including empty boards and unavailable historical data. It does not show fake
historical results. It is an initial state inspector, not the full C7 dashboard.

The queue defaults paused. It is independent of an AI connection and processes
explicit jobs; autonomous source watching, generation and repair loops are still
pending. No Nous calls or paid services are used. See known-limitations.md and
implementation-plan.md for every incomplete milestone. No release gate is waived.
