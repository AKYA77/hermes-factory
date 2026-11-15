# ADR0031 — Exact shared causal indicator primitives

Status: implemented software scope; overall acceptance NOT_READY.

Extract the existing arithmetic, preserving operation order, into named past-only
primitive groups: moments, changes, regression slope, price envelope and mean
range. Declarative operators and unanimous confluence share these groups through
the same compiler. Thresholds, stops, risk, direction and higher confirmations
remain outside primitive identity. No native matching, financial convention,
strategy score or scientific threshold is changed.

Indicator L2 identity includes the underlying canonical dataset/profile/code/
timeframe/range/closed-publication policy, lookback, group/formula version and
Decimal arithmetic context. Bar identity also includes Decimal context, because
midpoint arithmetic depends on it. Context changes during indicator consumption
fail closed. Exact Decimal strings and end/publication timestamps are persisted
in bounded Parquet row groups, with checksummed immutable input manifests.

Default indicator disk budget256MiB, entries256, batch1024; lookback remains at
most500 and buffers at most8192rows/group. Reuse existing bar-cache reservation
and disposable-entry eviction. Never evict canonical quotes or scientific results.
Lock order indicator→bars avoids inversion. Manifest is the publication boundary;
actual SIGKILL between data move and manifest leaves an incomplete entry that is
rebuilt once. Source bytes are reverified on hits and after construction. The
compiler checks exact temporal alignment and rejects checksum/context failures.

Measured generated feature-only comparisons found short histories slower under
L2. Automatic adoption is restricted to mean reversion/trend with lookback≥64.
Other cases use direct shared primitives; explicit IndicatorCache supports every
category. The same adapter serves exact-zero screening, optional shadow labels,
training native replay and frozen evaluation, with original causal higher-bar
alignment and strictly later native execution unchanged. This is an engineering
choice, not a performance guarantee or a candidate-quality filter.

Generated benchmark receipts distinguish bar-only, first indicator build and
warm reuse, three threshold variants, an uncontrolled OS page cache and cumulative
process RSS. No feature-only timing is represented as native throughput, target
host performance or historical evidence. See docs/milestone-shared-indicators.md.
