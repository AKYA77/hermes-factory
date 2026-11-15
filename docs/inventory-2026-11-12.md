# Repository and VPS inventory — 2026-11-12

Produced for Phase 0 of the owner directive
`docs/source/Owner_Lean_RaptorBT_Final_Directive_2026-11-12.md`. Every value below
was measured on the VPS or read from the repository at commit
`6a5bbe05a5575c7e71a936845eaaa098aa151503` unless explicitly marked as a prior
record. Nothing here is assumed from the handoff.

## 1. Host

| Item | Observed | Directive expectation | Status |
|---|---|---|---|
| OS | Linux 6.8.0-147-generic | — | — |
| CPU | 6 vCPU (`nproc`) | ~4 vCPU | differs; target envelope must be enforced |
| RAM | 11 GiB total, 9.8 GiB available | ~8 GiB | differs; target envelope must be enforced |
| cgroup limits | none published (`memory.max`, `cpu.max` empty) | — | no container cap in effect |
| Disk | 96 GiB, 34 GiB used, 62 GiB free | — | adequate |
| Python (host) | 3.14.9, no pip module | 3.12 project env | use project venv |
| Python (project) | 3.12.3 in `.venv` | 3.12 | matches |
| Rust | `rustc 1.100.0`, `cargo 1.100.0` (installed 2026-11-12) | required for Phase 1 | **was absent; now present** |
| Node | v26.12.1 | — | present |
| uv | 0.13.7 | — | present |
| Network | `static.rust-lang.org` 200, `github.com` 200 | — | open |
| Hermes WebUI | PID 1851749, port 8787, running since Nov 6 | must not be disrupted | untouched |
| Acquisition supervisor | not running | — | idle |

## 2. Repository

| Item | Observed |
|---|---|
| HEAD | `6a5bbe05a5575c7e71a936845eaaa098aa151503` |
| Branch | `build/initial-factory` (only local branch; `origin/main` exists) |
| Working tree | clean |
| Remote | `https://github.com/AKYA77/hermes-factory.git` |
| PR #1 | open; CI `audit`, `dashboard`, `python`, `verify` all pass |
| Ledger | `completion-ledger.json`, schema `completion-ledger/v1`, 67 requirements |
| Ledger status | 6 `PASS`, 61 `NOT_TESTED` |
| Readiness | `SOFTWARE_VERIFIED=false`, `DATA_READY=false`, `OPERATION_READY=false` |
| Last verification | 684 passed, 0 failed, 0 skipped; lint PASS; frontend PASS |
| Nautilus references | 27 files (code, tests, docs) |
| RaptorBT references | 0 in code; 4 in historical docs only |
| Rust artifacts | none before 2026-11-12 |

## 3. Data

| Item | Observed |
|---|---|
| Catalog location | `/var/lib/hermes-factory/catalog` |
| Catalog entries | 372 top-level: 196 directories, 176 import-report files |
| Partition manifests | 182 parsed |
| Instruments | 8: EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, AUDUSD, NZDUSD, XAUUSD |
| Months per instrument | 22 each, 2025-01 → 2026-10 |
| Total coverage | 22 distinct months |
| Missing for 24-month window | 2024-11, 2024-12 (16 partitions) |
| Parquet files | 32,681 files, 9.35 GB |
| Source archives | 704 files, 2.5 GiB |
| Quality status | 177 `STRUCTURAL_PASS_CALENDAR_REVIEW_REQUIRED`, 3 leaf-only, 2 `None` |
| Source-accepted data | **none** — no partition has completed calendar/source acceptance |
| Fidelity | 180 `SOURCE_BID_ASK`, 1 `REAL_BID_ASK`, 1 `SYNTHETIC` |
| Known defect | USDCAD 2026-07 crossed quotes, 353 rows, quarantined lossily under `source-quality-quarantine/v1` |
| Catalog DB | `/var/lib/hermes-factory/factory.sqlite`, 827 KB |
| Backfill state | `/var/lib/hermes-factory/backfill/` with supervisor log, checkpoint and per-partition logs |

Data status is **not** `DATA_READY`: structural import is complete for the 22
acquired months, but calendar/source acceptance, the instrument profile registry
and the missing two months remain open.

## 4. Component classification

Classification vocabulary: **complete-verified**, **implemented-migration**,
**partial**, **missing**, **unverified**, **externally-blocked**.

| Component | Files / lines | Classification | Basis |
|---|---|---|---|
| `factory/data/` | 13 / 3,415 | implemented-migration | Acquisition, catalog, quarantine, source-order correction and resume work and are tested; Python row materialization (`to_pylist()`) still on hot paths; source acceptance incomplete |
| `factory/features/` | 4 / 808 | partial | Closed-bar shared indicators and bounded compilation exist; dynamic M1–D1 selection and cache-identity extension unfinished |
| `factory/strategies/` | 1 / 145 | partial | Nine families and typed expressions exist; native Rust generator missing |
| `factory/simulation/` | 8 / 1,624 | implemented-migration | Exact Decimal ledger, adverse-fill model, bracket replay, reconciliation and streaming spool are implemented and tested against Nautilus 1.231.0; matching is Nautilus-owned and must move to Rust |
| `factory/exploration/` | 4 / 1,502 | partial | Persistent TPE, registered cells and fairness allocation tested; continuous region discovery and full-space fairness open |
| `factory/screening/` | 7 / 1,591 | partial | Historical prospective cohorts, CLI/API and comparability contracts implemented; full source-to-restore historical gate open |
| `factory/ranking/` | 4 / 476 | partial | Per-instrument boards and retention rules exist; strict 50% gate and full ranking/diversity regression open |
| `factory/validation/` | 10 / 2,250 | partial | Holdout reservation, purge/embargo, WFO geometry and multiple-testing helpers tested; full protocol acceptance and independent reconciliation open |
| `factory/diagnostics/` | 3 / 485 | partial | MFE/MAE, stop taxonomy and excursion diagnostics tested; recursive/session/regime cohorts open |
| `factory/operations/` | 22 / 2,474 | partial | Release pointer, backup rehearsal, doctor, campaign and benchmark tooling exist; production installer, systemd, quotas and update/rollback open |
| `factory/instruments/` | 4 / 520 | unverified | Profile registry exists; real dated broker metadata remain `UNKNOWN_SPEC`/`UNKNOWN_CALENDAR` |
| `factory/experiments/` | 1 / 396 | complete-verified (scoped) | Registry, immutable evidence and aliases tested |
| `factory/reporting/` | 2 / 222 | partial | Equity summary and receipts exist; full reporting surface open |
| `factory/contracts/` | 1 / 225 | complete-verified (scoped) | Typed proposals, fingerprints and comparability contracts tested |
| `factory/config/` | 1 / 27 | partial | Config loader exists; target-envelope and Rust build config missing |
| `apps/api/` | — | partial | Authenticated typed API tested; new execution/generator endpoints missing |
| `apps/coordinator/` | — | partial | Leased queue and isolated workers tested; continuous autonomous replenishment and resource admission open |
| `apps/dashboard/` | — | partial | SvelteKit build and browser smokes pass; new execution/index/performance panels missing |
| `tests/` | — | partial | 684 tests pass; Rust parity, target-envelope and soak suites missing |
| `scripts/` | — | partial | Queue inspector, verify gate, browser smokes and rehearsal scripts exist; Rust build/parity scripts missing |
| `deploy/` | — | partial | Release harness exists; systemd units and target-host deployment open |
| `migrations/` | 12 SQL | partial | 001–012 applied; later schema needs open |
| `docs/` | — | partial | Extensive milestone records; architecture docs predate this directive |

## 5. Baseline measurements

| Measurement | Value | Source |
|---|---|---|
| Full test suite | 684 passed, 0 failed, 0 skipped | `reports/runtime/test-results.xml` via `development-state.json` |
| Suite wall time | 1,305 s | same |
| Lint | PASS | same |
| Frontend build/check | PASS | same |
| CI at HEAD | 4/4 contexts pass | `gh pr checks 1` |

No performance baseline for the Rust engine exists yet because the engine does
not exist. The Python/Nautilus baseline is the reference for Phase 1 parity.

## 6. Known blockers

| Blocker | Type | Effect |
|---|---|---|
| Instrument profiles `UNKNOWN_SPEC` / calendars `UNKNOWN_CALENDAR` | externally-blocked | Prevents source acceptance and `DATA_READY`; needs authoritative broker metadata or owner decision |
| 2024-11 and 2024-12 absent | implementable | 24-month window incomplete; acquisition is authorized and the source path is open |
| No Rust engine | implementable (started) | Phase 1 core deliverable |
| Target-envelope proof not run | implementable | 4-vCPU / 8-GiB soak unrun on this host |
| Approximate candle screen still present in parts of the funnel | implementable | Must not be used to prune; exact execution is authoritative |

## 7. Preservation list

The following are evidence and must not be deleted, reset or overwritten:

- `/var/lib/hermes-factory/catalog/**` (partition data and manifests)
- `/var/lib/hermes-factory/archives/**` (raw source bytes)
- `/var/lib/hermes-factory/factory.sqlite` and `backfill/factory.sqlite`
- `/var/lib/hermes-factory/backfill/**` (checkpoints, logs, artifacts)
- `reports/**` (milestone reports, manifests, browser receipts)
- `docs/milestone-*.md`, `docs/source/*.md`, `docs/decisions/*.md`
- All failed candidates and their diagnostics
- Historical Nautilus-era results and execution identities
