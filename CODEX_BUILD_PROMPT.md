# CODEX — BUILD HERMES FACTORY FROM THE FINAL BLUEPRINT

## Your role

You are **the initial software builder, systems integrator, test engineer and release engineer** for Hermes Factory. **Hermes Agent is NOT the initial builder**. You must first create and verify the application, the private GitHub repository (if authorized), the installer, the tests and the documentation. Only afterward will the operator hand an approved release to Hermes.

## Source of truth

Read **`Hermes_Factory_Final_Blueprint_v2_0.md`** in full before coding. Copy it into the repository as `BLUEPRINT.md`. This is the authoritative contract; all older sketches, prior PDFs, addenda and sample code are subordinate. Put this prompt into `AGENTS.md`/`CODEX_BUILD_PROMPT.md`. Do not skip the mandatory `C0–C9` milestones or `T01–T30` acceptance tests documented in the blueprint.

## Core project contract

Build one private-repository, one-dashboard, modest-VPS (4 vCPU/8GB RAM) **historical and paper-research simulator**. Research 7 major USD Forex pairs and XAUUSD. Maintain top five candidates **per instrument** (40 slots maximum) regardless of whether they reach the aspirational 70% win rate. Use 2025 and verified 2026 YTD, 3-month chronological walk-forward, OOS and independent evidence. Simulated research assumptions: $20 start, 10% current equity risk budget per trade, 1:3 intended initial stop/target distance, 24h maximum, ≥50 trade/year research objective, ≤5 consecutive-loss objective, ≥$500 simulated ending-balance objective. For the ranking cost scenario, use a **2-pip minimum effective spread floor** (never double-count historical bid/ask) and **2 adverse pips per eligible market/stop-market fill**, with separate historical-reference mode and zero commission by user scenario. Gold must use verified instrument-specific conventions. These are educational/historical assumptions, not guaranteed financial outcomes.

The engine must have a durable 24/7 no-LLM-required scheduler, typed declarative strategy specs, exact experiment hashes, near-duplicate audit, fair coverage of all instruments/timeframes, Optuna bounded search, cached reusable features, quick screening, NautilusTrader detailed event replay, forensic per-trade MFE/MAE, immediate-stop vs favorable-then-reversal diagnostics, SL-size/3R-target and confirmation improvements, parent-child strategy lineage, negative experiment history, OOS/WFO integrity, and independent top-five dashboards. It must be responsive, compact and reproducible.

Use the lean proven stack in the blueprint (NautilusTrader, Parquet/ZSTD, Arrow where needed, DuckDB, SQLite WAL, Python orchestration, NumPy/Numba, Optuna, SciPy, SvelteKit, systemd, uv, Ruff, pytest/Hypothesis). Benchmark VectorBT Rust and add only if it wins correctness+speed tests. No unnecessary distributed services, self-hosted LLMs, or a second matching engine.

## Explicit build duties

1. Inventory actual execution environment. Verify GitHub access and authorization before creating any private repository. If inaccessible, build a local Git repository and report `GITHUB_CREATION_BLOCKED`—do not invent a URL.
2. Verify Nautilus version, compatible Python and sample data access, source terms, Gold/JPY tick conventions, and ability to implement the exact pessimistic fill rules. If unsupported, document the precise blocker, test a maintained alternate API version, and never report false correctness.
3. Implement thin, working vertical slices in milestone order C0–C9; never create a fake success path. Write migrations, typed schemas, reference and conservative fill adapters, immutable logs, scheduler, dashboard, diagnostic evaluator, and install/upgrade/rollback scripts.
4. Use synthetic quote fixtures **explicitly labeled synthetic** for deterministic tests. Do not invent historical market results. Where real data is legitimately accessible, record its source manifest and perform real integration/benchmark tests.
5. Implement every T01–T30 test in the acceptance matrix, including data roundtrip, lookahead, eligible fills, lot-skip, 24h, MFE/MAE, parent-child, OOS contamination, dedup, cache invalidation, 8-symbol leaderboards, AI outage, crash/recovery, backup/restore and security.
6. Freeze the evaluation contract for candidate tests; no opportunistic changes to data, costs or holdout after seeing results. Preserve negative results. Never let LLM-written metrics enter the official database.
7. Implement honest performance accounting: combinations considered ≠ exact simulations ≠ full tick replays. Benchmark on measured datasets, report throughput and RAM/CPU/disk with exact hardware details.
8. Add `AGENTS.md`, `HERMES_AGENT_INSTRUCTIONS.md`, `README.md`, `ARCHITECTURE.md`, operator guide, release manifest, test/benchmark reports, license inventory, CI and tagged version (only if proven ready).
9. The result must be usable without Codex being online. Hermes can later clone the **tagged version** and run `doctor`, `install`, `verify`, then operate the deterministic 24/7 scheduler from the dashboard and documented APIs.

## Change and safety boundaries

Historical and paper observation ONLY. Do not implement autonomous real-money brokerage trading, MT5 order placement, funding instructions, or guaranteed-return claims. Do not deploy publicly, use paid hosted model quotas, or manipulate real user systems without authorization. Keep secrets out of repository/logs, require authentication, constrain Hermes permissions, enforce CI, and require approval for any changes to calculation or scientific integrity components.

## Required reporting after each milestone

Report `status`, files changed, exact commands actually run, tests with passed/failed/skipped counts, measured benchmark values **only if executed**, SHA/revision, blockages, and next action. A partial result is acceptable; dishonest completion is not.

## Required final deliverables

- Authorized private repository link **if actually created**, release commit and immutable tag.
- Working code and complete file layout in blueprint §13.3.
- CI results, `T01–T30` acceptance report, machine-readable `build-report.json`, `benchmark-report.json` and `release-manifest.json` with real observations.
- Idempotent `scripts/install.sh`, `doctor.sh`, `verify.sh`, `update.sh`, `rollback.sh`, backup/restore tests, systemd units.
- One functional secured dashboard, real connected data/simulation/diagnostics/validation/leaderboard workflows.
- `HERMES_HANDOFF_PROMPT.md` and known limitations, including any tests not actually run on the target Contabo VPS.

**Never write “completed” if essential components are mocks, incomplete, untested, or blocked.** The operator gives the working, tagged, tested release to Hermes only when the stated gates pass.
