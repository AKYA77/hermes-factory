# Owner Lean RaptorBT Final Directive — 2026-11-12

- Status: **ACTIVE** — authoritative for all current development
- Directive date: 2026-11-12
- Repository: https://github.com/AKYA77/hermes-factory
- Branch: `build/initial-factory`
- Pull request: https://github.com/AKYA77/hermes-factory/pull/1
- Owner authority: explicit owner master directive, 2026-11-12
- Recording artifact: this document (`docs/source/Owner_Lean_RaptorBT_Final_Directive_2026-11-12.md`)

This is the owner's latest project-design directive. It **supersedes directly
conflicting architectural decisions** in `BLUEPRINT.md`, `ARCHITECTURE.md`,
`AGENTS.md`, `HERMES_AGENT_INSTRUCTIONS.md`, `NEXT_ACTION.md`, and the older
source directives in `docs/source/`. Those documents remain preserved as
historical records; they must not be used to justify reverting to the legacy
design.

This is an implementation mandate. It is not a request for another blueprint.

## 1. Conflict resolution

The following prior decisions are **superseded**. Each is recorded here so the
change is auditable and the older text is not silently deleted.

| # | Superseded decision | Prior source | New decision |
|---|---|---|---|
| 1 | NautilusTrader is the matching engine; "do not build another matching engine" | `AGENTS.md`; `docs/source/Completion_Directive_2026-11-03.md` | One RaptorBT-derived Rust execution engine replaces NautilusTrader after verified parity migration |
| 2 | "Do not replace NautilusTrader with … RaptorBT … or another matching engine" | `docs/source/Completion_Directive_2026-11-03.md` §209 | Superseded by line 1 above; RaptorBT-derived execution is now the mandated path |
| 3 | "Evaluate RaptorBT only if its measured behavior … justify its installation" | `docs/source/End_to_End_Completion_Mandate_2026-11-03.md` | RaptorBT-derived execution is required, not optional |
| 4 | "Benchmark NumPy/Numba against RaptorBT if appropriate" | `docs/source/Optimization_Handoff_Amendment_2026-11-03.md` | RaptorBT-derived Rust execution is the target; benchmarking is for parity and throughput proof |
| 5 | Two-stage approximate-candle screen followed by a separate full historical tick backtest of the same candidate | `docs/milestone-*` screen/cohort design | One accurate testing pipeline: generate → compile signals → exact indexed or sequential execution → evaluate → qualify/reject |
| 6 | Every strategy is evaluated through a complete M1 signal loop | Legacy multi-timeframe implementation | Dynamic M1–D1 selection: evaluate only the smallest timeframe a strategy actually requires, plus its confirmed higher timeframes |
| 7 | Indexed tick execution is not permitted | Conservative reading of the original execution contract | Indexed execution is permitted only where mathematically and empirically equivalent to sequential quote replay; sequential replay remains the authoritative fallback |
| 8 | No absolute win-rate gate | Original blueprint scoring | Absolute 50.00% verified win-rate minimum for qualification, applied per instrument |

Not superseded, and explicitly preserved:

- All original acceptance obligations that remain relevant (the 67 ledger
  requirements, C0–C9 and T01–T57).
- Scientific independence, source evidence, immutable experiment records,
  security requirements and existing protections.
- The pessimistic cost scenario, risk model, instrument set and holding policy
  in §4 and §9 below.
- Historical Nautilus-era results, which keep their original execution
  identities and are never overwritten to manufacture compatibility.

## 2. Verified present state at directive time

Measured on the VPS 2026-11-12, not assumed from prior records. Full detail is in
`docs/inventory-2026-11-12.md`.

| Item | Observed |
|---|---|
| Git HEAD | `6a5bbe05a5575c7e71a936845eaaa098aa151503` |
| Working tree | clean |
| Branch / remote | `build/initial-factory` → `origin` (HTTPS, `AKYA77/hermes-factory`) |
| PR #1 | open; CI contexts `audit`, `dashboard`, `python`, `verify` all pass |
| Acceptance ledger | 67 requirements: 6 `PASS`, 61 `NOT_TESTED` |
| Last full suite | 684 passed, 0 failed, 0 skipped; lint and frontend PASS |
| Readiness | `SOFTWARE_VERIFIED`, `DATA_READY`, `OPERATION_READY` all false |
| Python | project venv 3.12.3; host interpreter 3.14.9 |
| Rust | **absent at directive time**; installed 2026-11-12 as `rustc 1.100.0` / `cargo 1.100.0` |
| CPU / RAM | 6 vCPU, 11 GiB RAM (directive expected 4 vCPU / 8 GiB) |
| Disk | 96 GiB total, 62 GiB free |
| Catalog | 182 partition manifests across 8 instruments |
| Coverage | 22 months per instrument, 2025-01 → 2026-10 |
| Quality status | all 182 partitions `STRUCTURAL_PASS_CALENDAR_REVIEW_REQUIRED` (or leaf-only); none source-accepted |
| Acquisition | no supervisor running; 704 source archives, 2.5 GiB |

Consequences that change the work plan:

1. **The 24-month window is not yet covered.** The latest complete 24-month
   window ending 2026-10 is 2024-11 → 2026-10. The catalog begins 2025-01, so
   **2024-11 and 2024-12 are missing for all eight instruments (16 partitions)**.
   Only those periods need acquisition; the existing 22 months are reused.
2. **No Rust toolchain existed.** It is now installed and pinned (§11).
3. **The host is larger than the directive's target.** Performance evidence
   must still be produced under the *target* 4-vCPU / 8-GiB envelope, not only
   on the larger development host.

## 3. Target architecture

The smallest maintainable architecture that satisfies the requirements:

```
verified tick archive
  → cached M1–D1 features
  → Rust strategy generator
  → RaptorBT-based execution (indexed mode | sequential quote replay)
  → scientific qualification
  → diagnostics
  → next research generation
```

Rules:

- **One execution engine.** Indexed and sequential are two algorithms inside
  that single engine, not two competing backtesting systems.
- **One canonical data source.** Immutable Parquet/ZSTD plus original raw
  archives. No redundant copies, no unverified custom storage format.
- **One shared feature pipeline.** Indicators are computed once and reused
  across strategies, parameter variants and experiments.
- **One native strategy generator.** Typed declarative expressions, never
  generated arbitrary Python.
- **One experiment registry**, one persistent scheduler, one validation and
  ranking system.
- **Python** is used for orchestration, APIs, persistence, experiment
  registration and reporting.
- **Rust** is used for computation-heavy operations. No per-tick Python
  callbacks in the hot path.

## 4. Execution engine — RaptorBT migration

RaptorBT's stock tick runner is **not** assumed to satisfy this project. Its
simplified tick path uses last-traded prices for certain stop/target behaviour
and is not a bid/ask Forex/Gold model. A pinned MIT-compatible RaptorBT-derived
Rust adapter/fork is implemented to the following contract.

Required behaviour:

- Exact historical **bid/ask** quote processing; long and short.
- Correct executable-side entry and exit prices.
- Exact quote-event sequence, including equal timestamps.
- Original nanosecond timestamps where available.
- Exact instrument tick/pip grids.
- Market, limit, stop and stop-market behaviour; partial fills; order state.
- Cancellations, deadlines and safety exits.
- Quote gaps and stale data.
- Correct fee/commission, currency conversion and monetary accounting.
- Correct position sizing and margin rules.
- Correct equity, realized P&L, drawdown and diagnostics.
- No artificial last-traded-price events manufactured from bid/ask quotes.
- No silent conversion between incompatible price representations.
- No unnoticed whole-history truncation or trade-count early termination.

### Preserved pessimistic cost scenario

Recovered from the existing implementation and fixtures; the Rust engine must
reproduce it exactly:

- Minimum effective spread: **2 pips**; if the observed spread is wider, the
  wider spread is preserved.
- Separate adverse slippage: **2 pips** on eligible market and stop-market
  fills.
- Correct outward price rounding on the instrument tick grid.
- Limit orders keep distinct behaviour and are not charged slippage.
- The 2-pip spread floor and the 2-pip slippage are **separate charges** and
  must never be merged or applied twice.

Current reference semantics (Python, `factory/simulation/`):

- `effective_quotes` — spread floor plus outward tick rounding.
- `eligible_price` — side-adjusted slippage plus outward tick rounding.
- `size_position` — 10% equity risk budget, loss per unit includes the adverse
  stop excursion.
- `TradeLedger` — exact `Fraction` accounting with `Decimal` reporting.

### Preserved research configuration

- Reward/risk target **3:1**.
- Existing hypothetical risk and initial-equity configuration.
- Existing maximum holding-duration policy.
- Eight configured instruments.

This is historical/paper research software. No live brokerage execution and no
real-money performance claims.

### Migration acceptance gate

NautilusTrader is removed only after **all** of the following:

1. Its existing golden test results are frozen.
2. Independent reference calculations are created.
3. Supported orders and fills are reproduced in the Rust engine.
4. Prices, quantities, timestamps, order states and P&L are verified.
5. Gaps, spreads, slippage, partial fills, timeout, Gold, JPY and
   cross-currency cases are verified.
6. Results are verified across genuine historical periods.
7. Deterministic execution is verified across restart and batch sizes.
8. A complete parity and discrepancy report is recorded.
9. Only then is NautilusTrader removed from active code, dependencies, tests,
   installers and documentation.

## 5. Data optimization

Keep immutable Parquet/ZSTD and original raw archives. Do not replace proven
storage with a custom format without measurement.

Remove the biggest known overhead first: `factory/data/__init__.py` currently
materializes Python rows (`to_pylist()`) on important paths. Python row
dictionaries and per-event Python object creation must leave performance-critical
historical research.

Required properties: fixed-point bid/ask prices; immutable source IDs and
original ordering; bounded native streaming; direct columnar access; shared
decoded quote buffers when safe; minimal intermediate copying; no repeated
Parquet decoding for related experiments; bounded cache reuse; reproducible
source and execution identities; no unsupported precision loss; no memory growth
proportional to the entire corpus.

A compressed native execution tape is permitted **only** if benchmarks show it is
worthwhile. Candidate techniques (integer timestamp deltas, delta-of-delta,
bid-price differences, ask reconstruction from exact spread integers, ZigZag,
bit-packing, ZSTD/LZ4, independently decodable blocks, memory mapping,
block-level metadata) are options, not obligations. Build the simplest solution,
measure it, and retain only demonstrated improvements. Exact round-trip
identity with the accepted canonical quote stream must be proven.

## 6. Dynamic M1–D1 multi-timeframe research

Seven supported timeframes: **M1, M5, M15, M30, H1, H4, D1**. Candle datasets are
derived from verified tick data, not downloaded separately.

Core rule: for each strategy, calculate signals using the **smallest timeframe
actually required by that strategy**, plus its confirmed higher timeframes.

- M1 entry + M15 confirmation → M1 and completed M15.
- M5 entry + H1 confirmation → M5 and completed H1.
- M15 entry + H4 confirmation → M15 and completed H4.
- H1 entry + H4/D1 confirmation → H1 and completed H4/D1.
- D1-only strategy → D1 only.

Do not force every H1/D1 strategy through a complete M1 loop. Do not use H1
signals to approximate a strategy that requires M1 information.

Candle requirements: derived from original quotes; correctly defined bid/ask
OHLC; legacy signal semantics preserved where parity requires; precise session
and timezone alignment; actual market closures; no fabricated empty candles;
source order and genuine price gaps preserved; completed higher-timeframe
candles only; no future information exposed to past signals; entry only at
eligible future execution events after signal availability.

Shared feature cache: extend the existing cache. Compute each indicator once,
reuse across strategies/variants/experiments, use native numeric arrays and
bounded caches, and include data, code, price model, timeframe, indicator and
scientific policy versions in the cache identity so stale entries cannot be
reused after a model change.

## 7. TickFirstHitIndex

Implement a minimal, reusable first-crossing index answering: given an exact
position/order state and a historical starting event, what is the earliest
subsequent eligible quote event that changes that state?

It must use information derived from the actual ordered tick events. An M1
candle's high and low are **insufficient** to determine which of SL/TP occurred
first.

For supported fixed-barrier strategies it may skip intervals it proves cannot
change execution. For strategies with unsupported dynamic state, complex order
interactions or tick-dependent signals, it must fall back to sequential replay.
No strategy is forced into the index shortcut.

Acceptance: indexed execution must equal complete sequential quote replay on
entry event/timestamp, exit event/timestamp, direction, stop/target ordering,
execution prices, spread and slippage, fees and account P&L, trade count,
MFE/MAE, deadline and gap behaviour, determinism, and complete historical
coverage. Any unsupported or ambiguous case falls back to sequential replay or
is reported unresolved. An index result is never labelled tick-accurate without
proof.

Speed: benchmark against the minimal sequential Rust engine on identical
genuine workloads. If indexing does not improve relevant throughput, or costs too
much RAM/disk, it is not activated.

## 8. One accurate testing pipeline

The mandated pipeline:

```
generate → compile signals → exact indexed or sequential execution
  → evaluate verified result → qualify/reject → independent scientific validation
```

The accurate execution itself provides the historical outcome. A cheap early
screen is retained only for invalid expressions, duplicate fingerprints,
contradictory conditions, provably no eligible signals, and mathematically
established impossibilities. Approximate OHLC win rates are never authoritative
grounds to reject a potentially valid strategy.

The accurate evaluation covers the full intended historical period and resolves
all eligible trades. Scientific walk-forward and protected-holdout assessment
remain separate obligations; independent validation is not eliminated.

## 9. Strict 50% win-rate qualification and leaderboards

A strategy must achieve **at least 50.00% verified win rate** to qualify for an
instrument.

- Win rate is calculated from properly resolved closed trades.
- A win reflects positive net trade P&L after applicable costs.
- Exactly 50.00% passes the numerical gate; anything below fails.
- No lower threshold may be substituted.
- The gate is applied separately per instrument.
- Adequate evidence/trade count is required before a result is called qualified.
- Unresolved or insufficient-evidence results are not passes.
- Qualification is rechecked after any execution-model or data change.

Rejected candidates are rejected from **qualification, not from the
research/evidence database**. Failed candidates and their diagnostics are
preserved so the search can learn from them.

Research ambition: continue searching for 70%+ verified win-rate strategies.
70% is an ambition, not a guarantee. No candidate is fabricated, no cost is
lowered to reach it, out-of-sample independence is not sacrificed, and win rate
alone does not rank otherwise-qualified strategies.

Eight separate qualified leaderboards, each holding up to five genuinely
eligible candidates. If only three pass, three are shown. Disqualified
strategies are never inserted to fill slots. Ranking uses verified net win rate,
independent validation status, trade count, net expectancy after costs,
drawdown and stability, performance across periods and regimes, parameter
robustness, strategy diversity, and complete comparable evidence versions.

Concept identity is separate from instrument-specific experiment identity. A
concept is evaluated across all eight instruments; each instrument receives its
own result and qualification. A concept is not called universally tested until
all required instrument-specific evaluations are complete.

## 10. Native Rust strategy generator

Add a minimal native generator while preserving the existing Optuna optimizer,
experiment registry and improvement systems. No giant new AI-agent architecture.

- Typed declarative strategy expressions, never arbitrary generated Python.
- Preserve the nine strategy families: mean reversion, momentum, breakout,
  trend, reversal, range, volatility, session, confluence.
- Extend operators only where they create meaningful, testable hypotheses.
- Support parameter variants, indicator lookbacks/thresholds, long and short
  signals, independent confirmations, M1–D1 combinations, rule combinations and
  simple logical expressions, bounded structural mutation, parameter mutation,
  controlled crossover, exact semantic fingerprints, candidate deduplication,
  measured novelty and diversity, and causal completed-candle evaluation.
- Keep the rule grammar small and interpretable initially.
- Add genetic programming, MAP-Elites or advanced evolutionary search only when
  benchmarking shows measurable research benefit.
- Evaluate compatible strategies in batches; share data buffers, indicators,
  signal primitives, timeframe features, boolean masks/bitsets and cached exact
  results.
- Do not create thousands of separate strategy files or Python objects.
- Preserve the persistent Optuna optimizer; do not replace working code until a
  simpler or faster alternative proves superior and deterministic restart
  behaviour remains intact.

## 11. Performance, hardware and honesty

The owner's aspirational target is extremely high throughput, ideally billions
of fully evaluated two-year strategies per hour. This is a goal requiring proof,
not a guaranteed capability. Hardware, event volume and execution complexity
impose real limits.

Count separately: generated variants, unique strategies, rejected duplicates,
cheap signal screens, reused cached evidence, indexed full-history evaluations,
sequential full-history evaluations, complete eight-instrument concept
evaluations, and independent validations. A cached result is reused but never
counted as a newly executed backtest.

A strategy is "fully two-year tested" only when its required data, signal
evolution, eligible trades, execution and accounting have all been evaluated
correctly.

Benchmark the actual VPS: generated variants/s, unique valid concepts/s, signal
conditions/s, sequential quote evaluations/s, indexed complete evaluations/h,
complete eight-instrument concepts/h, CPU and wall time, peak RAM, disk
reads/writes and temporary storage, cache hit/miss, index construction time and
size, performance by complexity and trade frequency, and recovery/restart cost.
Use the same datasets and workloads for before/after comparison. Publish no
unsupported speedup estimate. Do not overfit the engine to a benchmark
containing only no-trade strategies.

Development rule for every optimization: **benchmark → implement → verify
parity → benchmark again → retain or revert.**

### Hardware envelope

Target the Contabo environment: approximately **4 vCPU and 8 GiB RAM**. The
development host measured here has 6 vCPU and 11 GiB, so target-envelope
evidence must be produced by measurement under enforced limits, not by running
only on the larger host.

Implement bounded worker count, adaptive native batch sizes, coordinated
Rust/Python parallelism, CPU and memory admission controls, bounded source and
feature caches, disk staging quotas, memory-pressure monitoring, worker failure
isolation, restart-safe leases, automatic recovery, and continuous queue
replenishment. More workers are not always faster; benchmark configurations
rather than maximizing worker count.

### Rust toolchain reproducibility

The Rust toolchain is pinned and recorded. At directive time the host toolchain
is `rustc 1.100.0` / `cargo 1.100.0`. The build must be reproducible from a
committed `Cargo.lock` and a pinned toolchain declaration, and CI must build
the Rust components.

## 12. Operations, dashboard and security

Preserve and finish: authentication and least-privilege operation; secure secret
storage; pinned reproducible dependencies; safe GitHub authentication; database
migrations; backups and verified restores; crash/reboot recovery; disk quota
enforcement; update and rollback procedures; systemd supervision and health
checks; full integration tests; target-host performance and soak tests.

The dashboard is completed and extended, not replaced with another frontend
framework without demonstrated reason. It must show factory/readiness state,
data coverage and source quality, generator activity, queue and active jobs,
generated-versus-tested throughput, indexed-versus-sequential usage, exact
execution performance, RAM/CPU/storage/disk I/O, all eight Top-5 leaderboards,
full strategy specifications, instrument/timeframe details, trade and failure
diagnostics, validation and scientific evidence, data gaps and unresolved
profile issues, errors/retries/restarts/recovery, and current Git commit and
software versions. Only genuine metrics backed by stored evidence are shown.

No unauthenticated dashboard or API. Do not interfere with the existing Hermes
WebUI service. No real-money execution. Do not deploy or mark the factory
production-ready until actual readiness requirements pass.

## 13. New acceptance requirements

Added to `completion-ledger.json` under owner authority. None is `PASS`; all are
`NOT_TESTED` until demonstrated.

| ID | Requirement | Acceptance criterion |
|---|---|---|
| R01 | RaptorBT-based Rust execution engine | One production Rust engine processes exact bid/ask quotes, long and short, with correct executable-side entry/exit prices, order states, partial fills, cancellations, deadlines, safety exits, gaps, fees, conversion, sizing, margin, equity and drawdown |
| R02 | NautilusTrader migration parity | Frozen Nautilus goldens plus independent references are reproduced by the Rust engine; a complete parity/discrepancy report is recorded; only then is NautilusTrader removed from active code, dependencies, tests, installers and docs |
| R03 | Pessimistic cost semantics preserved | Exact 2-pip spread floor, wider-spread preservation, separate 2-pip adverse slippage on market/stop-market fills, outward tick rounding, distinct limit behaviour, for Forex, JPY and XAUUSD |
| R04 | TickFirstHitIndex equivalence | Indexed execution equals sequential quote replay on entry/exit event and timestamp, direction, stop/target ordering, prices, spread, slippage, fees, P&L, trade count, MFE/MAE, deadline and gap behaviour, determinism and full coverage; unsupported cases fall back |
| R05 | Dynamic M1–D1 signal selection | Each strategy evaluates only its required smallest timeframe plus confirmed higher timeframes, with no look-ahead, completed candles only, and no M1 loop forced on higher-timeframe strategies |
| R06 | One accurate testing pipeline | Generation → signal compilation → exact execution → verified evaluation → qualification, with approximation unauthorized to prune and independent validation retained |
| R07 | Strict 50% win-rate gate | Verified win rate ≥ 50.00% after costs, applied per instrument, with adequate trade count; exactly 50.00% passes; rechecked after model or data change |
| R08 | Native Rust strategy generator | Typed declarative grammar covering the nine families, parameter mutation, structural mutation, crossover, fingerprints, deduplication and novelty, with batch evaluation and shared caches |
| R09 | Verified 24-month coverage | An explicitly approved complete 24-month window per instrument, source-quality accepted, with no invented or misaligned periods |
| R10 | Native data-access optimization | No Python row materialization in performance-critical paths; bounded native buffers; measured improvement with exact round-trip identity |
| R11 | Target-envelope performance evidence | Real 4-vCPU / 8-GiB measurements of throughput, CPU/wall time, peak RAM, disk and cache behaviour on the actual VPS |
| R12 | Rust build reproducibility | Pinned toolchain, committed `Cargo.lock`, CI builds the Rust components, deterministic rebuild |

## 14. Preserved obligations

- All 67 existing requirements remain accounted for. None is reset, deleted,
  renamed away or reduced to appear finished.
- Passing scoped tests never completes an entire acceptance requirement.
- `SOFTWARE_VERIFIED`, `DATA_READY` and `OPERATION_READY` remain false until
  complete verification evidence supports them.
- The repository remains **public** by owner decision (ADR 0070). No visibility
  change, no merge of PR #1, no release tag, no production deployment and no
  readiness claim without required authorization and verification.
- Failed candidates, raw source bytes, receipts, catalogs, caches, holdouts,
  experiment logs and failed research artifacts are preserved. No destructive
  reset, broad `git clean`, database recreation, catalog replacement or mass
  redownload is permitted as a shortcut.

## 15. Recorded conflicts

| Conflict | Resolution |
|---|---|
| Older directives forbid RaptorBT; the new directive mandates it | New directive prevails for architecture; older text preserved as history |
| Existing ledger statuses vs. new requirements | Existing 67 requirements untouched; new R01–R12 added, all `NOT_TESTED` |
| Directive expects 4 vCPU / 8 GiB; host has 6 vCPU / 11 GiB | Target-envelope evidence must be measured under enforced limits; host size recorded |
| Directive says 176 partitions; catalog holds 182 | Catalog measured directly: 182 manifests, 8 instruments × 22 months; the 176 figure is the planned monthly set, the remainder are additional/re-import datasets |
| 24-month window vs. 22 months of coverage | 2024-11 and 2024-12 are genuinely missing for all eight instruments; only those periods need acquisition |
| Rust toolchain absent | Installed and pinned (§11) |

## 16. Implementation phases

Phase 0 — audit and authority update (inventory, this amendment, queue and
acceptance update, baseline tests and benchmarks).

Phase 1 — minimal accurate RaptorBT migration (freeze Nautilus goldens,
bid/ask-native Rust execution, long/short, 2/2-pip model, order and accounting
semantics, parity tests, then remove NautilusTrader).

Phase 2 — native data-access optimization (eliminate Python quote objects from
critical loops, bounded native buffers, benchmark, reject unnecessary formats).

Phase 3 — shared dynamic multi-timeframe features.

Phase 4 — exact tick-index acceleration with an automatic indexed/sequential
selector.

Phase 5 — Rust generator and batched testing, preserving Optuna.

Phase 6 — qualification and ranking with the strict 50% gate.

Phase 7 — complete data and scientific evidence (reuse history, acquire only
missing periods, approve source quality, finish validation).

Phase 8 — operations and dashboard.

Phase 9 — whole-system acceptance on the target envelope.

Each phase is executed through the standing loop: inspect → read queue →
implement the smallest correct change → focused tests → regression/parity →
benchmark → revert or repair → update documentation and ledgers → commit →
push → verify remote SHA and CI → reinspect → begin the next task.
