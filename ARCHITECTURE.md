# Hermes Factory development architecture

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

The API is under /api/v1, documented by generated schemas and OpenAPI in schemas/.
No route accepts official metric values. The dashboard shows exact responses,
including empty boards and unavailable historical data. It does not show fake
historical results. It is an initial state inspector, not the full C7 dashboard.

The queue defaults paused. It is independent of an AI connection and processes
explicit jobs; autonomous source watching, generation and repair loops are still
pending. No Nous calls or paid services are used. See known-limitations.md and
implementation-plan.md for every incomplete milestone. No release gate is waived.
