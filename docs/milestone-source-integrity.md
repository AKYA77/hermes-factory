# Eight-instrument source integrity and failure-evidence increment

Status **NOT_READY**. Final code `e75c0bafdac3d7815645437710895592464a7325`.
This continues the original Factory; no required gate is waived. The authoritative
blueprint and full completion directive remain preserved. Source-bound detailed
measurements/commands/hashes are in milestone-report.json.

## Actual historical data

Free HistData ASCII downloads and bounded lossless imports now cover January 2025
for all eight instruments, **21,345,746 quotes**:

| Instrument | Quotes | Observed source grid |
|---|---:|---:|
| EURUSD | 2,283,239 | 0.00001 |
| GBPUSD | 2,660,109 | 0.00001 |
| USDJPY | 3,467,097 | 0.001 |
| USDCHF | 1,627,731 | 0.00001 |
| USDCAD | 2,494,413 | 0.00001 |
| AUDUSD | 1,668,426 | 0.00001 |
| NZDUSD | 1,346,505 | 0.00001 |
| XAUUSD | 5,798,226 | 0.001 |

Every import retains raw archives/notices, exact integers, UTC/source-time semantics,
original ordering, row-stream and file hashes, and full structural readback. No raw
market data is committed. Source quote grids are not approved broker/pip/margin
conventions. Gaps remain unclassified. This is not historical strategy validation.

The through-November-2026 plan has 184 provider-month partitions: eight imported,
176 still pending. Current-month availability/completeness is unverified. This is
a plan, not a claim all those months are obtainable or complete.

## Implemented correctness and resource work

- Canonical dataset/provenance identity and deep stream verification, with cached
  proofs bound to full manifest/source/Parquet SHA256. All bytes are rehashed on
  every lookup; a changed input invalidates the semantic proof.
- Resumable/paced/free-only backfills with retries/cooldown, disk reserve, per-source
  locks, retained interrupted captures, immutable receipts and parent-death handling.
- Currency-label validation, maximum volume rounded down after capping, positive
  protective levels, exact quarter-boundary handling and range-aware feature keys.
- Bounded immutable RAM arrays, including metadata-entry limits, collision rejection
  and prevention of writable aliases. Full shared-feature/L2 wiring remains pending.
- Atomic pause-at-claim, immutable failed-strategy registration (migration 003), and
  content-addressed quarantined engine evidence. Failed metrics are not official.

ADR 0010 defines scope; ADR 0009 covers the persistent TPE/recurring training loop.
Source partitions are still single-partition replay inputs. A multi-month view and
source-mapped artifact contract remains necessary for full annual research.

## Verification actually run

`bash scripts/verify.sh` on final code: **144 passed, zero failures/errors/skips**;
152 upstream warnings retained. Ruff and dashboard typecheck/build pass.
`uv pip check`: 49 packages compatible. Wheel build passed and includes all three
SQL migrations; installed-distribution scientific provenance is still unapproved.

Additional actual evidence:

- 1,000 distinct synthetic candidates on 32fe84f: 480,000 events, no assertion
  failures, 192.334s wall / 163.325 batch-worker CPU seconds / 302,632,960-byte peak
  worker RSS. CPU excludes parent setup/verification. Short synthetic replay does
  not establish historical/VPS throughput.
- Before proof reuse (2279e14): 229.627s / 200.246 CPU seconds / 301,445,120-byte RSS.
  All 1,000 scientific results compare exactly after excluding only recorded runtime
  provenance (different actual code revisions). Baseline overlapped source imports;
  no blanket speedup or production rate is asserted.
- Alternating proof-cache on/off comparator: same manifests; 100 verification calls
  take 0.713/0.753s without reuse versus 0.020/0.018s with 99 hits. This is a 480-row
  verification microbenchmark, not a backtest-rate claim. Every call still hashes
  all file bytes. Cache off/on code is identical apart from the entry budget.
- New monthly-import peaks range 150,536,192–182,874,112 bytes. USDJPY 3,467,097 rows:
  85.54s wall / 83.52 pipeline CPU seconds. Download wall is included; startup CPU
  is not. No target 8-GB host or total-system RAM peak measured.
- Authenticated API reads all 1,000 runs; anonymous access rejected; validated views
  empty. Backup/isolated restore verifies 1,016 files, 1,000 jobs and experiments.
- Isolated schema2→3 restore preserves 15 strategies and 15 experiments, leaving
  the source backup unchanged. This is not live release migration rollback.
- Actual gap/insolvency, partial/cancel, stale source, corrupted artifact and kernel
  parent-death cases supplement the original tests. Fault-injection quarantine
  testing is labeled; it supplies no official result or historical performance.

Fresh Python/npm audits still fail on fsspec/deepmerge. No finding/check is ignored.
Private GitHub access is verified; branch-protection reads return integration HTTP403.
Final-head CI must be observed separately; passing tests does not clear security.

## Remaining original product work

Calendars/full 2025–2026 source coverage/revisions; approved monetary profiles and
currency/account reference agreement; multi-month views and large artifacts/shared
features; automatic discovery/full families/cohort-guided child improvement;
independent annual/OOS/WFO/holdout/stability/robustness and comparable boards; full
browser dashboard; production install/update/rollback/off-host backup, paper
observation and actual Ubuntu 4-vCPU/8-GB multi-day soak all remain mandatory.
No production tag or completed C0–C9 claim exists. See the acceptance matrix and
completion backlog; new scoped T31+ tests supplement T01–T30.
