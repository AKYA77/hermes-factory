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

## 3. Genuine tick data did not satisfy the synthetic fixture profile

Measured by running the twelve-stage source-to-restore rehearsal against the
real acquired catalog (`/var/lib/hermes-factory/catalog`) with a scratch state
root. **All twelve stages now complete with zero blocked.** This section
records the four defects that had to be fixed to get there, because each was a
genuine gap rather than a fixture mismatch.

| Defect | Measured symptom | Fix |
|---|---|---|
| Profile units | `profile_status = DECLARED_UNITS_MISMATCH` | Added `declared_tick_profile()`, which derives the tick and scale from the measured stream (`price_scale=1000000`, not the fixture's `1000`) |
| Timestamp precision | 124,125 structural issue rows | The source-quality policy now derives `timestamp_quantum_ns` from the observed `source_precision` (millisecond) instead of assuming whole seconds |
| Calendar coverage | `calendar_status = UNRESOLVED_CALENDAR` | A 24/7 fixture cannot classify real weekend gaps. The rehearsal now declares a session (Sun 22:00 UTC → Fri 22:00 UTC) for the sampled instrument |
| Instrument identity | `CALENDAR_INSTRUMENT_MISMATCH`, then `instrument identity mismatch`, then `contract mismatch` | The sample is now taken from a single instrument, and the admitted payload's strategy instrument and `strategy_hash` are recomputed to match |

**Interpretation.** These are all profile- and fixture-coverage gaps, not defects
in the provider's stream and not parser faults. Genuine tick data needs declared
units, precision, session and identity that match it; the fixture assumed a
minute-scale, whole-second, 24/7, single-instrument world.

**Consequence for the rehearsal.** A blocked stage is recorded explicitly with
its reason instead of aborting, so a receipt distinguishes "did not run by
design" from "could not run, and why". That is what made the shared cause
visible rather than stopping at the first failure.

**Still open.** The declared session is a TEST_ONLY rehearsal assumption, not
verified broker metadata. The ADR0051 instrument profile registry remains the
proper home for reviewed instrument metadata, and `DATA_READY` stays false.

## 4. The rehearsal was not idempotent against a reused state root

Found while adding the `catalog` stage. A second run against the same state root
failed its own `diagnose` stage with `DISCOVERY_EVALUATION_WINDOW_EXCLUDED`.

The cause is a feedback loop between two stages:

1. `independent_evaluation` records a `research_input_uses` row with purpose
   `evaluation-with-past-only-warmup` for the sampled window.
2. Discovery's `excluded_intervals` treats that purpose as an excluded evaluation
   interval, so the next run's `diagnose` refuses the same window.

The first run therefore silently poisons the state root for the second. Measured:
14 accumulated `research_input_uses` rows for one instrument and one identical
window, across repeated runs.

**Fix.** The rehearsal now refuses a state root that already has an
`evaluation-with-past-only-warmup` use for the sampled instrument, with a message
naming the cause and the remedy. A test pins it. Only that purpose is checked: a
`training-enqueue` use is legitimate prior state and does not cause exclusion.

**Consequence.** Run the rehearsal against a fresh `--state-root` each time, as
the browser smokes do. The guard turns a confusing downstream failure into an
immediate, accurate one.

## 5. `refresh` reported a consistent catalog as inconsistent

`factory.cli refresh` re-verifies every partition's parquet digest against its
manifest. On this host it reported `consistent: false` with three partitions
listed as `missing`, which reads as data loss.

The three were not missing. They were **composed views** (`data/view-v1`), which
by design have no `quotes.parquet` of their own — a view is a descriptor over
leaf partitions. `refresh` treated every manifest as a leaf, so it looked for a
parquet beside each view, found none, and reported the view as missing.

Measured on the real catalog: 129 `data/v2` leaves with parquet, 3 `data/view-v1`
without, 2 `data/v1` leaves with parquet, plus 14 working directories
(`.pending-*`, `.imports`) that carry no manifest and are correctly skipped.

**Fix.** `refresh` now verifies a view through its leaves: each referenced leaf
must exist and match its recorded `parquet_sha256`. A view with no parts, or with
a missing or mismatched leaf, is still reported. Result on the real catalog:
`verified: 134`, `mismatched: []`, `missing: []`, `consistent: true`.

**Why it matters.** A false integrity alarm is worse than no alarm: it trains the
operator to distrust the receipt, and a real missing partition would then be
dismissed as the known false positive. The test pins both directions — a view over
intact leaves passes, and a view whose leaf is deleted still fails.

## 6. A narrow requested window failed the whole source scan

A completed source-quality attempt on this host failed with
`SOURCE_QUALITY_EVENT_BUDGET` after scanning 2,495 rows. The policy asked for a
38-hour window; the dataset is a monthly partition. `REQUESTED_PERIOD_MISMATCH`
was emitted **once per out-of-window row** — 2,494 of them — so a condition that
is a property of the request exhausted the event budget and aborted the scan.

Measured from the retained partial artifact:
`{REQUESTED_PERIOD_MISMATCH: 2494, ROW_ISSUE: 2494, LEADING_UNQUOTED_INTERVAL: 1}`,
1,048,486 bytes of events, `complete_source_scan: false`.

**Interpretation.** The window mismatch is a relationship between the request and
the dataset, not a defect in each row. Reporting it per row is disproportionate:
the magnitude is already carried by `counts.outside_requested_period_rows`, which
also drives `requested_period_status`.

**Fix.** Per-row `REQUESTED_PERIOD_MISMATCH` events are now bounded by
`max_examples`; the count carries the magnitude. A test pins both directions —
the scan completes with `outside_requested_period_rows == 31` on a 32-row fixture
under a 1 KB budget, and the emitted mismatch events stay within `max_examples`.

**Consequence.** A scan whose window does not match its data now completes and
reports the mismatch as a status plus a count, instead of failing outright. A
genuine per-row defect (a bad quote, an off-grid tick) still emits per row and can
still exhaust a deliberately tiny budget — that behaviour is unchanged and covered
by `test_event_budget_retains_incomplete_attempt_and_never_registers_complete_receipt`.

## Disposition

`DATA_READY` remains false. These findings are exactly the class of defect the
source-quality gate exists to catch, and recording them is preferable to
importing non-monotonic evidence.
