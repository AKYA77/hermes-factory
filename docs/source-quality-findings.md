# Source quality findings — measured, not inferred

Each finding below was measured against the actual downloaded provider archives
on this host. A quarantine is the quality gate refusing to commit data; it is a
result, not a failure of the pipeline.

## 1. Non-monotonic tick sequences (38 partitions, 11 months)

`factory/data/resume.py` raises `QUARANTINED source spread/order` and the
partition is not committed. The streaming replay model requires a monotonic
source sequence, so this data cannot be admitted as-is. Two distinct defects
were measured; both trip the same gate.

### 1a. Duplicated hour — 2025-10

In the October 2025 archives the timestamp sequence reaches the end of an hour
and then restarts at the top of the same hour:

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

The same duplicated hour appears in three independent instruments at the same
UTC instant, which points to a provider-side artifact rather than a parser
fault.

### 1b. Single ticks out of order by ~1 second — many months

A second, distinct defect appears across many other months: a single tick whose
timestamp is one second earlier than its predecessor, at a second boundary.
Measured examples:

| Instrument / month | Row | Previous timestamp (UTC) | Timestamp (UTC) |
|---|---|---|---|
| AUDUSD 2026-09 | 120,721 | 2026-09-03T13:30:02Z | 2026-09-03T13:30:01Z |
| EURUSD 2026-08 | 757 | 2026-08-02T23:00:04Z | 2026-08-02T23:00:03Z |
| XAUUSD 2026-07 | 5,402 | 2026-07-01T05:37:34Z | 2026-07-01T05:37:33Z |

Months with at least one quarantined partition: 2025-10 (all 8 instruments),
2025-11, 2025-12, 2026-01, 2026-02, 2026-03, 2026-06, 2026-07, 2026-08,
2026-09, 2026-10.

**Reachability of the defects.** The parser is not implicated: identical
archives parse deterministically and every other imported month is monotonic.
The defects are in the provider's own timestamp sequence.

**Not done, deliberately.** The gate is not relaxed, the repeated hour is not
silently dropped, no rows are reordered and no timestamp is nudged to force
monotonicity. Any of those would turn a measured source defect into silently
altered evidence.

**Required review.** A reviewed correction must either remove the disorder under
an explicit, recorded correction policy, or accept the partitions with a
documented owner decision and a dataset version that records the defect. Until
then these partitions stay blocked and are reported as blocked.

## 2. Staging payload budget (operational, managed)

The cumulative staging footprint is bounded by `--staging-budget-bytes`
(default 2 GiB). Staging is retained after publication, so the budget is
eventually exhausted and further imports block with
`staging payload budget exceeded` even though their canonical data was already
published.

Two distinct causes were measured:

- **Published staging.** `reclaim-staging` reclaims it while preserving
  canonical data and evidence. Measured effect: 2.1 GB reduced to under 200 MB.
- **Retained prefixes for partitions that cannot succeed.** `reclaim_all`
  deliberately touches only published checkpoints, so a quarantined partition
  keeps the partial prefix it decoded. With 43 quarantined partitions that
  dead weight accumulates: 193 staging directories totalling 1.8 GB, with the
  five largest holding 105–142 MB each. This is resumability working as
  designed, not a leak — but it does consume the budget.

`scripts/acquire_history.py` now exposes `--staging-budget-bytes` so the
operator can size the guard for the host instead of editing the default. The
supervisor runs with 17179869184 (16 GiB) on this host, which has 75 GB free;
the guard still bounds growth, it no longer blocks legitimate imports. Raising
the budget does not relax any data-quality check.

## Disposition

`DATA_READY` remains false. These findings are exactly the class of defect the
source-quality gate exists to catch, and recording them is preferable to
importing non-monotonic evidence.
