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

`scripts/acquire_history.py` exposes `--staging-budget-bytes` so the operator can
size the guard for the host. The supervisor runs with 17179869184 (16 GiB) on
this host, which has 63 GB free.

**Root cause of the final three blocks.** The budget was not a sizing problem.
`reclaim_all` existed, was tested and was exposed through the tools CLI, but the
acquisition driver never called it — so *published* staging was never reclaimed.
Measured after 173 partitions were published: **3.38 GiB retained across 269
intents**, of which **zero** were reclaimable by inspection at the time the
reclamation finally ran, because the published checkpoints were still present
and verifiable. The largest partitions then had less headroom than they needed
and failed with `staging payload budget exceeded`.

The driver now calls `reclaim_all` after each wave. It touches only published
checkpoints with verified chunks; failed and in-progress intents are left
untouched, so resumability is preserved. Raising the budget alone would have
only delayed the same failure.

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

## 7. Provider source-order defects and their lossless correction

The 47 blocked partitions were all recorded as `import exit 1`, which said nothing
about cause. Reproducing them from the immutable archives
(`sha256`-verified before parsing) showed **two distinct provider defects**, not
one: eight partitions carry a duplicated hour and the other 39 carry isolated
out-of-order rows.

### 7.1 Exact duplicate block — all eight instruments, October 2025

A duplicated hour affects **every instrument for October 2025** — eight
partitions, not a subset. Each shows exactly one backward jump:

| Partition | Backward jump |
|---|---|
| EURUSD 2025-10 | −3,598.2 s |
| GBPUSD 2025-10 | −3,599.1 s |
| NZDUSD 2025-10 | −3,599.2 s |
| USDCAD 2025-10 | −3,599.2 s |
| USDCHF 2025-10 | −3,597.8 s |
| USDJPY 2025-10 | −3,599.4 s |
| XAUUSD 2025-10 | −3,599.9 s |
| AUDUSD 2025-10 | same class |

The block after the jump is a verbatim re-emission of an earlier block: the first
50 rows of each are identical on timestamp, bid and ask, and the EURUSD block is
**1,494 rows** long. The duplicate carries no information.

The uniformity across all eight instruments on the same UTC instant is itself
evidence that this is a provider-side archive-assembly defect, not eight
independent market events.

### 7.2 Isolated out-of-order rows — every other blocked partition

The remaining 39 blocked partitions carry isolated out-of-order rows rather than
a duplicated block. AUDUSD June 2026 has 10 backward jumps in 1,723,025 rows, each
exactly **−1.000 s**; the raw CSV shows why, with a row stamped `20260628 172222000`
appearing *after* one stamped `20260628 172223000`. The provider's timestamp
records when the tick occurred; the file order is an assembly artifact.

Measured counts range from 2 rows (EURUSD 2026-06, NZDUSD 2026-06) to 15,084 rows
(XAUUSD 2026-10). Gold shows the largest counts by a wide margin, consistent with
its higher tick rate.

### 7.3 Crossed quotes — USDCAD July 2026

A third defect is a **crossed quote**: `bid > ask`, an arbitrage that cannot
persist in a real market. Measured in USDCAD July 2026: **353 crossed quotes in
1,226,412 rows (0.029%)**, crossing by 1-7 pips at the provider's 1e5 scale.

| Crossing | Rows |
|---|---|
| 10 units (0.00010) | 179 |
| 20 units (0.00020) | 83 |
| 30 units (0.00030) | 50 |
| 40 units (0.00040) | 19 |
| 50 units (0.00050) | 16 |
| 60 units (0.00060) | 4 |
| 70 units (0.00070) | 2 |

This defect is handled differently from the other two because it is **lossy**.
`source-order-correction/v1` is lossless: it reorders or drops exact duplicates,
so no observation is lost. A crossed quote cannot be repaired — the value is
wrong — so the choices are to drop the row or to drop the partition.

Dropping the partition was the previous behaviour, and it withheld 1,226,059 good
rows because of 353 bad ones. `source-quality-quarantine/v1` removes the crossed
row whole and records the count, the magnitude histogram and bounded positions.
The receipt states plainly that the policy is lossy.

Nothing is rewritten: no price, timestamp, scale or instrument field is
adjusted, `original_record_order` survives on every retained row, and the raw
archive is untouched. The post-hoc scanner already reports crossed quotes as
`INVALID_QUOTE`, so a quarantined partition remains visible in QA.

A non-positive price remains an immediate failure; that is a different defect.

### 7.4 The scanner reported its own correction as a defect

Once the partitions imported, the source-quality scanner was run over the real
archives for the first time. Every instrument came back `FAILED_CHECKS`:

| Reason | Rows |
|---|---|
| `SOURCE_RECORD_SEQUENCE_GAP` | 48,065 |
| `SOURCE_CHRONOLOGY_MISMATCH` | 15,533 |

Both were false positives with one cause. The lossless source-order correction
publishes a **permutation** of the source rows: the timeline becomes monotonic
while `original_record_order` stops being consecutive. The scanner still
assumed published order equals source order.

Measured directly on the published EURUSD partition: **0 timestamp inversions**
and 331 sequence gaps in 1,805,682 rows. The timeline is correct; the 331 gaps
are the reordered rows.

The fix separates two different questions:

- **Chronology** now compares timestamps only. A source-position comparison
  there conflated "reordered" with "out of order".
- **Sequence** now detects a *repeated* `original_record_order`, which is the
  real defect: one source row published twice.

A gap is no longer treated as a defect, and that is a deliberate limitation
rather than an oversight: after reordering and quarantine, a gap is
indistinguishable from a correctly removed row unless the source row count is
known, and the manifest does not record one. A duplicated row is detectable
without it.

All eight instruments now scan `PASS` over 20,163,841 real rows, with
`synthetic=false` and `historical_admission=false` throughout and calendar and
instrument metadata still `UNKNOWN`.

### Correction policy `source-order-correction/v1`

`factory/data/source_order.py` applies both corrections. Neither rewrites a
timestamp, price, scale or instrument field.

| Defect | Correction | Lossless because |
|---|---|---|
| Exact duplicate block | drop the later block | every dropped row is byte-identical to a retained row |
| Isolated out-of-order row | stable sort by timestamp | the timestamp is unchanged; only sequence changes |

`original_record_order` is preserved on every retained row, so the mapping back
to the source archive stays exact, and the receipt records each removed block's
extent and the duplicate's original position. The raw archive is never modified.

A repeated timestamp with *different* prices is a genuine re-quote, not a
duplicate, and is explicitly preserved — `test_a_repeated_timestamp_with_different_prices_is_not_collapsed`.

Measured on the real archives:

| Partition | Rows in | Rows out | Duplicate block | Rows reordered | Residual disorder |
|---|---|---|---|---|---|
| EURUSD 2025-10 | 1,483,175 | 1,481,681 | 1,494 at idx 1,185,416 | 0 | none |
| AUDUSD 2026-06 | 1,723,025 | 1,723,025 | none | 26 | none |

Both corrected streams are monotonic. Anything the module cannot correct
losslessly is left in place and reported rather than asserted away.

## Disposition

`DATA_READY` remains false. These findings are exactly the class of defect the
source-quality gate exists to catch, and recording them is preferable to
importing non-monotonic evidence.
