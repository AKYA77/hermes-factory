# ADR 0011 — Software handoff, immutable partition views and exact feature reuse

Owner authority: [3 November amendment](../source/Optimization_Handoff_Amendment_2026-11-03.md).
The original PDF remains the scientific specification. No cost, risk, ranking,
validation split or source quote is changed by this decision.

Full source acquisition is a DATA_READY requirement after tested software handoff,
not a prerequisite for finishing implementation. SOFTWARE_VERIFIED requires all
software gates, representative real-source integration and synthetic chronology
fixtures. OPERATION_READY additionally requires full verified data, actual target
installation/stress/recovery/soak and the approved workflow. All are currently
false. No release/tag or production guard is relaxed by this checkpoint.

`factory.operations.readiness` evaluates explicit named gate receipts. PASS alone
is insufficient: a relative receipt inside the evidence root and matching SHA256
are required. Receipts need human review for substantive acceptance; hashing a
file is not proof that its claims are true. Missing gates fail closed. The CLI
`readiness` reports all missing gates and exits nonzero until OPERATION_READY.

`Catalog.compose` creates flat `data/view-v1` descriptors over 1–512 ordered,
distinct immutable leaves of the same instrument, integer units, provider and
precision. Real/synthetic mixing, overlaps and nested views are rejected. Equal
timestamp boundary records are both retained in caller-declared leaf order.
Leaves, source bytes, ingest IDs and original row orders do not change. A located
quote adds its partition identity and global physical sequence, including under
range pruning. A view is structural composition, not calendar/revision approval.

Bare-leaf replay remains 32 bytes per spool row. Views use 48 bytes to retain leaf
index/global sequence alongside original row order; compact paths use
`canonical-view-path/v1`, with source references on fills/path points and exact
reconstruction. No second matching engine is introduced.

`BarCache` is a local disk L2 with a process lock, 512 MiB/256-entry default caps
and 1,024-row buffers. Cache keys bind dataset/view, exact half-open source range,
instrument identity, source revision, timeframe and publication policy. Stop,
risk and signal parameters do not affect midpoint bars. Missing timeframes share
one canonical quote pass. Decimal strings preserve the reference arithmetic;
Parquet uses lossless Zstandard level 1. Simultaneously published timeframes are
merged before the existing signal interpreter runs. No terminal unclosed bar is
published. This is not a competing backtester or an approximate promotion path.

Canonical bytes and cache checksums are reverified, including on hits; no mtime
trust fast path. Hard budgets fail explicitly, never truncate. Incomplete builds
are discarded under the lock and rebuilt after interruption. Committed cache
corruption fails the job for investigation. Eviction removes only unprotected
cache entries, never canonical sources or experiments. Cache read locking is
serialized, suitable for the existing single-heavy-worker coordinator.

Training retains its existing within-window warm-up policy. Fixed-window
validation retains past-only history through each window end, with cache keys
including that boundary. Neither implementation is complete WFO refitting.
Persistent indicator transforms, Tier 0 rejection/audit and append/revision
acceptance remain separate work; this increment does not claim them implemented.
