# Source quality findings — measured, not inferred

Each finding below was measured against the actual downloaded provider archives
on this host. A quarantine is the quality gate refusing to commit data; it is a
result, not a failure of the pipeline.

## 1. October 2025 — duplicated hour (EURUSD, GBPUSD, USDJPY)

**Measured.** In all three October 2025 archives the timestamp sequence reaches
the end of an hour and then restarts at the top of the same hour:

```
2025-10-27T00:59:58.437Z
2025-10-27T00:00:00.248Z   <- sequence restarts at the top of the hour
2025-10-27T00:00:00.508Z
```

First offending row, measured by scanning the archives with the production
parser:

| Instrument | Row | Timestamp (UTC) | Previous timestamp (UTC) |
|---|---|---|---|
| EURUSD | 1,185,416 | 2025-10-27T00:00:00.248Z | 2025-10-27T00:59:58.437Z |
| GBPUSD | 1,409,261 | 2025-10-27T00:00:00.244Z | 2025-10-27T00:59:59.370Z |
| USDJPY | 1,881,006 | 2025-10-27T00:00:00.245Z | 2025-10-27T00:59:59.693Z |

**Effect.** `factory/data/resume.py` raises `QUARANTINED source spread/order` and
the partition is not committed. The streaming replay model requires a
monotonic source sequence, so this data cannot be admitted as-is.

**Reachability of the defect.** The same duplicated hour appears in three
independent instruments at the same UTC instant, which points to a provider-side
artifact rather than a parser fault. The parser is not implicated: identical
archives parse deterministically and every other imported month is monotonic.

**Not done, deliberately.** The gate is not relaxed, the repeated hour is not
silently dropped, and no rows are reordered to force monotonicity. Any of those
would turn a measured source defect into silently altered evidence.

**Required review.** A reviewed correction must either remove the duplicated hour
under an explicit, recorded correction policy, or accept the partition with a
documented owner decision and a dataset version that records the defect. Until
then these partitions stay blocked and are reported as blocked.

## 2. Staging payload budget (resolved)

The cumulative staging footprint is bounded by `--staging-budget-bytes`
(default 2 GiB). Staging was retained after publication, so the budget was
eventually exhausted and further imports blocked with
`staging payload budget exceeded` even though their canonical data was already
published. The fix is `python -m factory.operations.tools reclaim-staging
<catalog>`, which reclaims staging for every published checkpoint while
preserving canonical data and evidence. Measured effect on this host: 2.1 GB
reduced to under 200 MB.

## Disposition

`DATA_READY` remains false. These findings are exactly the class of defect the
source-quality gate exists to catch, and recording them is preferable to
importing non-monotonic evidence.
