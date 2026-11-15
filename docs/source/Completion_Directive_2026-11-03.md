# HERMES FACTORY — CONSOLIDATED CODEX COMPLETION DIRECTIVE

**Review date:** 2026-11-03  
**Repository:** `AKYA77/hermes-factory`  
**Reviewed branch:** `build/initial-factory`  
**Reviewed commit:** `2f1e50517f71eed123e4b0f9712d19a3f56d1eca`  
**Authoritative product specification:** `docs/source/Factory.pdf` (Hermes Factory Master Blueprint v2.0), plus the preserved acceptance contract and existing accepted decisions.  
**Project boundary:** historical data research, hypothetical strategy simulation, scientific validation, and paper observation. No brokerage execution, real-money automation, paid services without authorization, or claims that historical results predict live profitability.

> **Codex: treat this document as an audited completion backlog and implementation request, not as permission to overwrite the original blueprint.** It adds findings and specific acceptance tests; where it conflicts with the original scientific contract, identify the conflict and request an explicit owner decision. Preserve all current functioning work, current data hashes, previous experiment results, and historical test reports. Continue on a development branch/PR; do not merge or tag a production release while gates remain open.

## A. What is ALREADY implemented — do not build twice

This branch already contains substantial work. Retain and improve rather than restart:

1. Typed, immutable Pydantic `StrategySpec`, `ExperimentContract`, `InstrumentSpec`, and canonical SHA-256 strategy/experiment identities in `factory/contracts/`.
2. SQLite WAL experiment/job registry, fenced leases, immutable experiment/audit triggers, and basic per-instrument coverage in `factory/experiments/` and `migrations/001_initial.sql`.
3. A functioning synthetic NautilusTrader integration, versioned pessimistic spread/slippage extension, and **new `adverse-fill/v2` order-aware execution ledger**, including entry/exit order IDs, partial fills, actual exit reasons, some safety-close and timestamp tests. Keep v1 historical records separately and immutable.
4. Real bid/ask HistData pilots for **January 2025 EURUSD and XAUUSD**. The reports claim 2,283,239 and 5,798,226 structurally verified quote rows, exact integer price round-trip, 8,192-row streaming Parquet/ZSTD writes, original source archive hashes, fixed UTC-05:00 source time handling, and no paid downloads. These are **data-import tests, not valid strategy results**.
5. Three current signal operators (mean reversion, momentum, breakout), basic closed-bar confirmations, controlled proposal generation, basic MFE/MAE diagnostics, and child strategy lineage. These are partial implementations, not the complete autonomous discovery/improvement engine.
6. FastAPI authenticated loopback API, a basic connected SvelteKit JSON state inspector, source hashes, scripts and partial CI/recovery setup.
7. Reported 84 passing regression tests and a 1,000-candidate **synthetic** campaign. GitHub Python-test and dashboard jobs pass for the reviewed commit; **dependency-security workflow still fails**. The 1,000 runs use 480 synthetic quotes each, and their throughput is not a two-year tick benchmark.

Do not regress these checks. Retain explicit `NOT_READY` until C0–C9, T01–T30, and the release gates pass. The source review is not equivalent to independently running every benchmark. Re-run tests under the exact commit you ship.

## B. P0 — correctness, evidence integrity, and unfinished prerequisites

### B1. Fix the current security release blockers without hiding failures

**Files:** `.github/workflows/dependency-review.yml`, `uv.lock`, `pyproject.toml`, `apps/dashboard/package-lock.json`, `docs/decisions/0007-dependency-security-assessment.md`, `SECURITY.md`.

- Current GitHub audit fails on Python `fsspec` through pinned NautilusTrader and a JavaScript `deepmerge` transitive dependency chain, per Codex's logged assessment. Recheck upstream versions and exact advisories **at implementation time**; don't blindly assume the currently documented versions remain latest.
- Prefer compatible upstream fixes or a specifically reviewed, supported patch. Keep dependency metadata coherent and run the entire golden suite afterward. Never silently violate a dependency pin, disable audits, change severity, or suppress CVEs to get a green CI badge. Record any owner-approved risk acceptance explicitly and keep release gates honest.
- Add trusted-build/config tests, dependency lock integrity, minimal GitHub Actions permissions, branch rules and credential hygiene. No secret or raw private market-data archive in Git.
- **Exit:** audit is appropriately resolved or transparently blocks release; exact workflow result and decision recorded. No automatic `OPERATION_READY` while an unresolved blocker exists.

### B2. Complete native fill accounting and independent reference tests

**Files:** `factory/simulation/{runner.py,ledger.py,nautilus.py,pricing.py}`, `factory/contracts/`, `factory/instruments/`, `tests/simulation/`.

- Preserve the new ledger; cover opening/closing partial fills, repeated/late fills, cancel-fill races, rejected/denied/expired orders, stop/limit gaps, exact timestamp ties, duplicate quote timestamps, missing quotes, partial protection and safety close, and session boundaries.
- Independently reconcile inventory quantity, order IDs, the Nautilus position/account ledger, filled cash flows, recorded fees, and final simulated equity. Require per-trade and aggregate **P&L conservation invariants**, so a close cannot be counted twice; test long/short symmetry and correct executable side (buy at ask, sell at bid).
- Fix or explicitly gate **finite-liquidity exact-price mismatch** noted in ADR 0005. Never rewrite real engine fill prices or certify an unexplained extra-tick fill as exact two-pip adverse slippage. If a policy permits an alternative execution outcome, version that policy and assess it separately, not under the original exact-cost contract.
- Distinguish *intended* 1:3 stop/target price distance from **realized** reward/risk after gaps and execution effects; report both. No invented actual 1:3 realized outcome.
- Handle base/quote/account conversions from dated quotes, price/tick grids, broker-like minimum volume/step/margin constraints and Gold-specific metadata. No invented pip-value constants or implicit Gold conventions. Use fixed-point/Decimal and explicit rounding policies.
- Implement independent golden cases: favorable target, adverse stop, price gaps, unavailable exit, near-TP reversal, partial fill, and quote-timeout; compare against a small transparent reference computation (not another production matching engine). No silent lookahead.
- **Exit:** T07–T12, T26 and related C3 evidence pass for supported real instrument profiles and both sides, with no unexplained reconciliation differences.

### B3. Explicit causality/event-order invariants

**Files:** `factory/features/`, `factory/strategies/`, simulation and validation tests.

- Enforce `signal information available_at <= decision time < eligible execution observation` according to the **versioned** event policy. A signal may not trade the quote it learned from. Test data arrival, bar close vs bar availability, next eligible quote, equal timestamps with source ordering, missing quotes, DST, session boundaries, stale data, and optional modeled latency.
- Any higher-timeframe confirmation must use only fully closed and actually available bars. Avoid treating a candle-end timestamp as its guaranteed publication time.
- Reject single-price or OHLC-only data for final **bid/ask quote replay**. Candle screening is allowed only as clearly labeled approximate screening, never tick-equivalent evidence.
- Distinguish true stop-order exit from negative time exit, cancellations and safety liquidation; use recorded order roles rather than infer causation from P&L sign.
- Avoid overclaiming that any assumed latency or deterministic fill model exactly matches future market execution.
- **Exit:** deterministic equal-timestamp and sparse-quote corpora verify zero same-information fills and correctly censored observations.

### B4. Finish the real-source historical data coverage

**Files:** `factory/data/histdata.py`, `factory/data/streaming.py`, `factory/data/__init__.py`, `factory/instruments/`, CLI operations and dataset registry.

- Retain **free-only** and usage/terms restrictions. Expand approved sources or source months without bypassing providers, assuming redistribution rights, or using paid endpoints. Deal with provider outages and rate limits through bounded retries and persisted checkpoints.
- Obtain 2025 and **2026-to-latest available as of the run** for all seven Forex majors plus XAUUSD. Clearly mark actual provider coverage and incomplete periods. Import source bytes once and derive approved timeframes from immutable canonical bid/ask ticks.
- Complete market calendar/session awareness, gap classification (weekend/holiday vs suspicious/unknown), DST/source timezone tests, tied timestamps, duplicate ordering, invalid spreads, data revisions, source reconciliation, source outage detection, and no interpolation or fake volume.
- Distinguish empirical price quantum from official instrument tick, pip, contract multiplier, margin, volume and quote-to-account conversion specifications. If some monetary profile cannot be verified, block money-valued validation of that instrument while retaining structural data.
- Add incremental updates, manifest lineage, content hash changes, fine-grained invalidation, compaction, data retention, disk-budget alarms, source integrity restore, and an independently checked day/week comparison. Use out-of-core writes and reads (do not turn a full year into a Python list).
- **Exit:** source-by-source provenance and all available 2025/2026 partitions are verified in bounded memory, with calendars and instrument-specific profiles accepted; missing data is reported, not silently ignored.

## C. P0 — complete the Factory rather than just its components

### C1. Full autonomous 24/7 offline-capable coordinator

**Files:** `apps/coordinator/service.py`, `apps/coordinator/worker.py`, `factory/exploration/`, `factory/improvement/`, `factory/experiments/`, `config/research-budget.yaml`.

- Current coordinator only consumes **explicitly enqueued training-only jobs**. Build a deterministic recurring state machine: discover newly imported partitions → select research budget → generate candidate hypotheses → check spec/experiment fingerprints → run fast screen → select detailed simulation → run diagnostics → test controlled modifications → run independent evaluation → rank/update reports → checkpoint → repeat while enabled and resources permit.
- Implement durable scheduled-job state, single-writer DB transactions, leases/heartbeats, idempotency, retry categories, pause/resume, cancel, archive, recovery after SIGKILL/reboot, disk-full/low-memory recovery and stale code/source rejection. No reliance on continuous LLM availability; **no billing or hosted-model access required for baseline deterministic research**.
- Allocate fair **CPU-time**, not just proposal-count, across eight instruments, strategy families, entry timeframes, confirmations, stop distances and parameter regions. Keep coverage of untried and previously rejected regions. Set explicit bounded budgets to avoid permanent CPU saturation.
- Record actual time spent, candidates proposed, exact duplicates skipped, cheap screens completed, full Nautilus replays completed and independently validated variants **as separate counters**. Never call a parameter suggestion a full backtest.
- Ensure no infinite self-optimization of unchanging OOS samples. Store the historical window roles that influenced each proposal.
- **Exit:** an unattended bounded multi-day synthetic/paper-service soak, simulated restarts, pause/resume and state-recovery tests pass with persistent, reproducible progress.

### C2. Make Optuna a real search optimizer, not a random-only adapter

**Current observation:** `factory/exploration/__init__.py` uses `RandomSampler`, constructs a new study, and marks each trial PRUNED without returning a measured objective. Thus it **cannot learn from experiment outcomes**.

- Implement persistent, reproducible studies, objective feedback from **authorized training observations only**, constrained and categorical search (instrument, family, timeframe, confirmations), trial accounting and time/CPU budget limits. Avoid concurrent direct SQLite optimization storage where not supported; use journal storage or coordinated optimization and keep Factory SQLite as registry.
- Separate candidate generation from trial evaluation; store all trial outcomes, pruning reasons, timeout reasons and optimizer version/seed. Keep full experiment identities and cache reuse.
- Use initial broad coverage followed by targeted investigation; tune 1:3-compatible stop distances without altering the core risk scenario.
- **Optional** typed genetic/tree-rule mutation and crossover for genuinely new strategy structures. Adopt only if a controlled equal-CPU, equal-data benchmark outperforms or meaningfully diversifies baseline Optuna proposals. Limit tree depth, number of indicators, confirmation complexity and survivor count. Don't install commercial StrategyQuant X or a second optimizer just for its branding.
- **Exit:** tests demonstrate measurable study learning, persistence across restart, no leakage from OOS, and deterministic replay with identical seed/inputs.

### C3. Mandatory Strategy Diagnostic & Improvement Factory

**Files:** `factory/diagnostics/`, `factory/improvement/`, `factory/strategies/`, `factory/experiments/`, UI/API.

- Keep the existing MFE/MAE and exit-role accounting. Extend to precise stop-hit vs negative timeout vs safety-close, immediate stop-outs, favorable move then reversal to SL, near-target reversals, no-exit within 24h, sessions, trend/volatility conditions, spread sensitivity, entry lag, price gap and clustered loss streaks.
- Classify every closed trade and flagged incomplete trade, using the correct executable side; store MFE/MAE magnitude/time, max retracement, percent of intended TP reached, realized R, path data/quality flags and exposure duration. Include partial-fill handling and minimum path sample thresholds.
- Measure **cohort-level** patterns and uncertainty, not just one trade's narrative. A diagnosis is a testable hypothesis, not a demonstrated causal explanation.
- Generate bounded, typed **child strategies**: confirmation add/remove, alternate available timeframe, entry criterion, legitimate session/volatility filter, indicator/lookback threshold and stop distances with fixed intended 3R target. Compare parent and child on comparable *training and designated selection* data, keep same cost assumptions and trade-frequency reporting; do not optimize on final holdout.
- Store original candidate, parent-child links, exact changed fields, hypothesis, evidence, reasons rejected/retained, run identities and previous attempts. Negative findings must survive restart and guide research-budget allocation.
- Stop wasting research CPU on unsuccessful families after a measured budget; never guarantee that a 40% WR strategy can be fixed.
- **Exit:** verified parent→diagnosis→child→training comparison→OOS decision→lineage trace, including an explicitly unsuccessful case that is not forgotten.

### C4. Complete independent statistical evaluation

**Files:** `factory/validation/`, `factory/ranking/`, `factory/reporting/`, data windows contracts.

- Complete 2025 and 2026 individual-year and combined reporting, chronologically sound **three-month walk-forward**, purging/embargo where outcomes overlap, separate training/selection/final holdout roles, no refitting on supposed holdout. Release final holdout metrics once per declared protocol and record consumption.
- Make OOS failure disqualify the **validated** view but preserve the candidate and its negative evidence in the all-candidates view. Maintain top five per instrument (up to 40), without inventing a minimum score threshold or insisting 70% be reached.
- Implement rate/trade count per year, incomplete 2026 coverage flags, streaks, maximum drawdown, realized/censored trades, precise stop/target semantics, calibrated intervals and broad robustness tests. Include uncertainty from many attempted candidates (multiple-testing/overfitting cautions).
- **New from friend's architecture, strongly recommended:** Parameter Stability Laboratory. Probe controlled neighboring parameters, stop distances and supported timeframes on permitted development/selection data. Record median results, dispersion, stability plateaus, isolated peaks, sensitivity to spread/slippage, and changes in number of trades. Version neighborhood definitions and ensure newly tested variants count as experiments.
- Add **walk-forward matrix/robustness overview as a concept**, not commercial StrategyQuant X installation. Report fold results and stability; do not use Monte Carlo or simulated perturbations as replacements for genuinely unseen markets.
- Distinguish per-strategy stand-alone hypothetical equity from any combined-instrument simulated portfolio. Implement an explicit accounting contract for overlapping positions if portfolio mode is included.
- **Exit:** isolated train/selection/holdout/forward-window tests, annual and WFO reports, stable ranking under equal comparison windows, and no false verified tags.

## D. P1 — high-throughput, ultra-light engineering without losing validated fidelity

### D1. Shared features and multi-tier caching — implement, don't just declare

**Concrete code issue:** `factory/features.feature_key()` currently includes the **entire** `spec.strategy_hash`. Different strategies using identical candles/indicators therefore cannot share a feature cache key effectively. `BoundedCache` exists but comprehensive cache use is not yet wired into the complete research pipeline.

- Distinguish feature identity (source data revision + instrument + timeframe + exact feature operator/parameters + publication-time policy + implementation version) from strategy identity and experiment identity. A change in only stop distance must not recompute unchanged indicator arrays.
- L1 bounded immutable RAM cache; L2 disk-backed feature/aggregated-timeframe cache only where measured beneficial; persistent L3 immutable experiment outputs; OS page cache managed by Linux. Cache metadata: size, hit/miss, build time, version, integrity and dependencies; exact invalidation on data correction/code/precision/time policy changes.
- Incrementally append new feature values with correct warm-up/overlap, not recompute two years for every data update. Never cache an unclosed higher-timeframe bar as if final.
- Precompute/resample supported candles, ATR/trend/session masks and reusable arrays once per data version and relevant parameter set. **Concrete hot-path issue:** `closed_bars()` in `factory/features/__init__.py` currently stores every within-bar midpoint in a Python `values` list just to compute open/close/high/low; replace with bounded rolling OHLC aggregates preserving exact event ordering. `compile_signals()` currently filters the entire higher-timeframe bar list for each entry bar; replace with a monotonic cursor or indexed as-of alignment, with equal-timestamp golden tests. Use shared read-only buffers/Arrow memory maps only when cross-process benchmarks show an actual benefit. Do not transmit tick arrays in JSON.
- Reuse a single decoded read for batches of compatible candidate screening; avoid stale index masks after filtering dates/instruments. Check data and instrument identity in every cache and sweep result.
- **Exit:** equal outputs under cache on/off, stale-cache rejection, reproducible invalidation and measured hit-rate/storage/RAM benefits.

### D2. Remove whole-dataset materialization from production replay

**Concrete code issue:** `apps/coordinator/worker.py` does `quotes=list(catalog.read(...))`; `factory/simulation/runner.py` likewise does `quotes=list(quotes)`, creates a second full `ticks` list, and reconstructs per-trade price paths by scanning quote/tick arrays. These approaches are unsuitable for full multi-million-tick periods on 8 GB RAM.

- Use NautilusTrader-supported chunking/Parquet catalog APIs and bounded streaming; benchmark supported repeated simulations with loaded data **only where state-reset semantics are correct**. Respect its process isolation and do not create a second matching engine.
- For diagnostics, write bounded event/path references or compressed columnar forensic traces rather than embedding every per-trade quote path into SQLite JSON. Keep immutable, reconstructable quote offsets and dataset hashes. Verify MFE/MAE from exactly the eligible executable-side path.
- Use out-of-core DuckDB/Parquet range queries for reports. Store small metadata/status in SQLite and large immutable artifacts outside the DB, indexed by content hash. Avoid redundant raw archives inside both cache and persistent catalog unless deduplicated, verified and permitted by the provenance policy.
- Benchmark ZSTD levels 1–3 against read bandwidth/storage on representative Forex and Gold samples; select on **total CPU + I/O + storage**, not compression ratio alone. Preserve exact integer prices, timestamps and original bytes.
- Control thread oversubscription, page-cache reserve, import-vs-sim job admission, on-disk quotas, profile memory and worker lifetime.
- **Exit:** process and system memory limits enforced at 8 GB, sustained bounded read/replay, no OOM, and exact reference equality for streaming and in-memory fixtures.

### D3. Fast screening, calibrated against authoritative replay

**From uploaded ZIPs:** a lean signal-plugin interface, compiled Numba kernels and a documented replay-bug catalog are useful *ideas*. Their standalone backtester, candle TP-first fill assumptions, one-minute latency quantization and alternate risk/cost models are **not** authoritative for Hermes.

- Benchmark current NumPy kernels against a small isolated Numba or optional VectorBT implementation on identical signals/data. Keep the fastest *correct* implementation measured on the actual CPU/RAM envelope; do not install all options by default.
- Screening may use vectorized bar arrays and approximate outcomes, but never claim final bid/ask event accuracy or mark `VALIDATED`. Keep all screens' IDs and threshold/prune reasons. Periodically run a stratified sample of rejects through Nautilus to estimate false-negative pruning.
- **New ZIP regression cases:** P&L conservation/no double close, short exits on ask, quote-currency conversion, per-pair data-grid identity, date-filtered event-mask recalculation, stop/TP conflict conservatism in OHLC screening, stop/target slippage placement, no lookahead on MTF, correct minimum lot/risk rejection, stale/mixed cache invalidation, duplicate experiment suppression and interrupted-process recovery.
- Never multiply theoretical Numba/Parquet/GPU speedup factors. Report CPU seconds, wall time, memory, source rows, unique candidates, batches and full replay count on common corpus.
- Do not execute ZIP-provided plugins or scripts as trusted code, and do not copy them unless rights/licenses are checked. Independently reimplement tested algorithmic ideas only.
- **Exit:** benchmark report with accurate distinct throughput tiers, comparable accuracy and resource data, rejection-audit results, and a clearly justified decision on optional packages.

### D4. Resource-aware 4-vCPU/8-GB optimization and communication

- One modular monolith, one coordinated SQLite writer, a bounded number of isolated heavy workers, and no Kafka/Redis/Kubernetes/Ray/GPU/Ollama/second Rust/C++ backtester. Use job descriptors and artifact references; avoid interservice transmission of millions of quotes.
- Start with one memory-heavy Nautilus worker and bounded lighter screens; tune thread counts/cgroups against measured peak RSS, aggregate RAM, filesystem I/O and user-interface latency. Profile hot paths before writing custom Rust.
- Use versioned typed interfaces (schema docs/OpenAPI and integration contracts), input/output checksums, worker-side schema validation and failure propagation. On schema evolution, create additive versioned database migrations and state upgrade/rollback tests, not silent table modification.
- A proposed speedup is accepted only if scientific outputs match the declared reference invariants and objective benchmarks demonstrate a useful gain. No claim of 'billions of full tick backtests/hour' on one VPS.
- **Exit:** comparable measured throughput/latency/CPU/RAM/disk benchmarks on the actual 4-vCPU/8-GB host, plus multi-day soak under bounded resources.

## E. P1 — dashboard, operations, API, full UX

**Current observation:** `apps/dashboard/src/routes/+page.svelte` is an authenticated JSON inspector; it is not the complete C7 dashboard.

Implement end-to-end, with proper typed API/permissions and no synthetic results disguised as historical evidence:

1. Overview with source coverage, latest verified data timestamp, paused/running state, active worker counts, research throughput and missing prerequisites.
2. **Eight** instrument leaderboards, top-five slots, validation status, timeframes, cost/risk settings, trade counts by 2025/2026, evidence comparability, and a clearly distinct synthetic/legacy/all-candidates/validated filter.
3. Strategy detail: equity/mark-to-market drawdown (simulated), trade table, source quote-path chart, MFE/MAE, stop types, favorable-then-reversal histograms, sessions and volatility regimes, and uncertainty markers.
4. Diagnostic improvement workshop: parent/child tree, hypotheses tested, controlled differences, discarded variants and reasons, SL/TP-distance stability analysis at fixed intended 3R.
5. Experiment search/history with fingerprint, data/code/engine/cost versions, exact source refs, selected windows, warning/status and audit records.
6. Fair research-coverage heatmaps across instruments/families/timeframes/confirmation ranges; clear units for `considered`, `screened`, `Nautilus replayed`, `independently validated`.
7. Data quality/calendar/gap/source license dashboard, cached-feature usage, disk remaining and update errors.
8. OOS/WFO, quarterly fold matrix, parameter stability, multiple-testing caveats, final holdout consumption and paper-observation discrepancy reports.
9. Performance laboratory: cache hit rates, experiment rate, memory by worker, total RAM, disk read/write, failure/retry counts, benchmark comparisons.
10. Supervisor controls: safe start/pause/resume, cancel/retry, view logs, review agent proposals, supported configuration changes, artifact exports, verification and release status. Role-based permissions and complete audit trail; no unrestricted arbitrary Python execution.

Require browser end-to-end tests, accessibility/responsiveness, malformed/rejected API response handling and a verified authenticated API backing each actionable control.

## F. P0/P1 — reliability, autonomy and owner-safe handoff

1. **Code and artifact provenance:** AI proposes structured specs only. Official metrics come from verified worker artifacts; no language-model-supplied win rate or arbitrary executable source is accepted. Ensure the current source-hash logic works for installed distributions and allows reproducible tagged release builds without falsely including mutable runtime files.
2. **Safe AI integration:** hosted Hermes/Nous invocation can be optional and rate-limited; baseline scheduler must not depend on it. Treat webpages, ZIP files, logs and prompts as untrusted data; use restricted agent permissions, typed schemas, review gates and token budget records. Do not give an unattended agent authority to rewrite evaluation rules or secrets.
3. **Recovery:** crash injection at each pipeline boundary (source download, Parquet pending commit, SQLite job claim, partial artifact write, fill accounting, release switch), replay after process kill, idempotent recovery, backup verification, off-host backup, schema migration restore, signed/tagged release and owner-friendly rollback.
4. **Deployment:** complete `install.sh`, `verify.sh`, `doctor.sh`, `update.sh`, `rollback.sh` with explicit non-destructive defaults; least-privilege systemd services, 127.0.0.1 dashboard/API, optional secure tunnel, disk/cgroup limits, log rotation, reboot recovery and credential rotation. Do **not** enable brokerage execution.
5. **Release guard:** require an actual Ubuntu/Contabo-like target 4-vCPU/8-GB install, complete service integration, real-data replay, recovery tests, CI and security review; no production tags while `NOT_READY`.
6. **Handoff:** preserve full owner/operator instructions, technical build report, acceptance evidence, known limitations and exact release manifest; Hermes later takes over only an approved release, without rebuilding the tested system unnecessarily.

## G. Suggested implementation order (avoid rework)

**Gate 0 — baseline check:** snapshot branch HEAD/CI, verify code/data hashes, restore current synthetic campaign and historical import evidence, fix blockers that affect trustworthy code execution, update backlog. Do not claim tests executed unless actually run.

**Gate 1 — correct foundations:** security blockers; verified instrument/Gold monetary specs; stronger fill/position/reference tests; causal and gap/time correctness; calendar+source integrity. Preserve the v2 ledger and working importer.

**Gate 2 — memory-safe execution:** finish large dataset streaming to authoritative Nautilus, context-aware feature caches, content-addressed large artifacts, replay/feature comparators and 8-GB bounds.

**Gate 3 — autonomous laboratory:** research scheduler, full Optuna feedback, complete typed strategy families/confirmations, fair budgets, dedup/negative evidence/false-negative audits, parent-child diagnostics and controlled improvement.

**Gate 4 — scientific evidence:** formal training/OOS/WFO/holdout/fold policy, annual reports, parameter stability, multi-testing checks, ranking comparability and paper-forward observational evidence.

**Gate 5 — owner product:** full dashboard/API, installation and operations, documentation, source updates, backups and recovery.

**Gate 6 — target-host acceptance:** independent golden fixtures, real January 2025 pilot with approved profiles then full available 2025/2026 import+replay, actual 4-vCPU/8-GB stress and soak, security and CI, acceptance-matrix evidence, release tag only after every mandatory gate.

For each gate: implement in small commits, update `docs/implementation-plan.md`, `known-limitations.md`, `docs/acceptance-matrix.md` and machine-readable `build-report.json`/`milestone-report.json` with `PASS`, `FAIL`, `BLOCKED` or `NOT_TESTED` and evidence links. Carry source SHA, tool versions, commands, exit codes, data hashes, actual tested window and hardware. New enhancement tests must not replace original T01–T30; add labeled T31+ only where appropriate.

## H. Explicit non-adoptions and non-goals

- **Do not replace** NautilusTrader with `best-tester.zip`, `backtester-skill.zip`, Backtrader, Backtesting.py, StrategyQuant X, forex-precision-backtester, RaptorBT, nanoback, RLXBT or another matching engine.
- **Do not install** those untrusted ZIPs as skills or execute them automatically. Their licensing/redistribution status is unclear. Borrow independently implemented ideas and tests, not unreviewed scripts or purported result data.
- **Do not adopt** multi-node clusters, Ray, Kafka, Kubernetes, GPU/CUDA or a new Rust engine on the present 4-vCPU/8-GB VPS without a measured, approved need.
- **Do not promise** billions of *full tick* backtests per hour, guaranteed >70% win rate, a $500 ending balance, or future parity. Distinguish cheap proposals/screens from scientifically evaluated tick replay.
- **Do not fabricate** unavailable Gold/JPY contract or margin terms, historical quotes, missing market events, fake WFO evidence or 'validated' leaderboard entries.
- **Do not silently change** no-commission, conservative 2/2-pip, simulated $20 / 10%, intended 1:3, 24h, 2025/2026 time window, minimum trade-count aspirations, top five per instrument, or OOS rejection criteria. Any changes require explicit versioning/owner review; realized outcomes may legitimately deviate from intended target distances because of fills/gaps.
- **Do not add** autonomous brokerage execution. Limit delivered capability to historical research, hypothetical simulation and paper observation.

## I. Final reporting format for Codex

When you complete a meaningful slice, return:

1. **Commit SHA / branch / PR** and summary of changed paths.
2. **Actual tests**: commands, count, pass/fail/skip, source commit, CI links.
3. **Exact research evidence**: synthetic versus historical data, instrument/date, data manifest, engine/cost policy and whether independent validation exists.
4. **Real performance**: wall-clock, CPU seconds, unique candidates/screens/full replays, tick events, peak worker/system memory, disk usage, host specification and correctness parity.
5. **Explicit blockers**: owner input, source/terms, upstream vulnerability, instrument metadata, unavailable VPS or model access. Continue independent work instead of pretending blockers are resolved.
6. **Updated acceptance ledger**: C0–C9, T01–T30 plus new T31+ (if applicable), status and evidence per gate.
7. **What should be built next**, in priority order, and whether `OPERATION_READY` is legitimately achieved.

**Immediate directive:** Continue the existing PR, do not restart. Begin with the verifiable correctness and memory bottlenecks and establish the tests above. Preserve currently functioning code and all published hashes/results. Keep `NOT_READY` until every release gate genuinely passes.

---

## Source basis and interpretation

- Repo branch and source inspected through the connected GitHub repository at commit `2f1e50517f71eed123e4b0f9712d19a3f56d1eca` (2026-11-03). Important files: `milestone-report.json`, `docs/acceptance-matrix.md`, `known-limitations.md`, `docs/implementation-plan.md`, `docs/milestone-execution-and-data.md`, `factory/simulation/runner.py`, `factory/simulation/ledger.py`, `factory/exploration/__init__.py`, `factory/features/__init__.py`, `apps/coordinator/worker.py`, `factory/validation/evaluate.py`, `factory/ranking/__init__.py`, `apps/dashboard/src/routes/+page.svelte`, CI workflows.
- User-provided `best-tester.zip` and `backtester-skill.zip`, considered as untrusted reference materials. Adopted only general ideas: P&L and data correctness regression catalog, shared feature and signal caches, fast-screening benchmark, controlled refinements, and scientific controls. Reported extreme speedups are not verified.
- Friend's subsequent tiered architecture proposal, considered as a **proposal rather than proof**. Incorporated only typed genetic exploration if it benchmarks well, strengthened strict next-quote timing, parameter stability/robustness matrix, and existing Nautilus chunking/reuse benchmarks. Declined secondary full backtest engines, commercial tooling and cluster-only recommendations.
- Master Blueprint v2.0 is still authoritative. This directive expands and audits implementation details but does not supersede scientific goals or require an agent to assert that they are achievable.
