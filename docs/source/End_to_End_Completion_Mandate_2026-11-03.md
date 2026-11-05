# HERMES FACTORY — FINAL END-TO-END COMPLETION MANDATE

## Your mission

You are the lead software engineer, systems architect, integration engineer, test engineer, performance engineer, and release engineer for **Hermes Factory**.

Your task is to **finish the complete Hermes Factory software**, starting from the existing GitHub repository.

**Repository:** `AKYA77/hermes-factory`  
**Development branch:** `build/initial-factory`  
**Last externally reviewed commit:** `9034cbcf4cba91af2a193f518b935af27c1c9dc2`

The original **Hermes Factory Final Master Blueprint v2.0** is the authoritative specification. The repository also contains the subsequent completion directive and optimization/handoff amendment.

Read those documents and the current implementation completely.

Your objective is NOT to produce another partial development checkpoint.

Your objective is to implement, integrate, test, debug, optimize, document, and prepare the **complete SOFTWARE_VERIFIED release candidate** that Hermes Agent can subsequently install and operate on the Contabo VPS.

The application is a fully autonomous **historical market-research and paper-simulation platform**. It must not contain autonomous real-money brokerage execution.

---

# 1. CRITICAL INSTRUCTIONS

## 1.1 Do not restart

Preserve every existing correct implementation.

The repository already contains substantial working functionality, including:

- NautilusTrader simulation integration.
- Order-aware execution accounting.
- Conservative execution assumptions.
- Immutable strategy and experiment contracts.
- Source and experiment fingerprints.
- Lossless integer quote storage.
- Parquet/ZSTD ingestion.
- Immutable multi-period dataset views.
- Bounded streaming and forensic references.
- Shared disk-based closed-bar caching.
- SQLite persistent jobs and research history.
- Persistent Optuna TPE optimization.
- Initial Tier 0 screening and rejection audits.
- Basic autonomous training research.
- Initial automatic strategy improvement.
- Parent-child strategy lineage.
- Authentication and dashboard controls.
- Backup/restore foundations.
- Existing automated tests and CI workflows.

Reuse and extend these components.

Do not replace NautilusTrader, introduce a second authoritative matching engine, rewrite the storage system, or add unnecessary infrastructure.

## 1.2 Implement, do not merely plan

Do not respond only with an architecture description, checklist, suggestions, or explanation.

**Write the required code, tests, migrations, frontend components, scripts, configuration, documentation, and integration interfaces.**

Run the tests.

Fix the bugs.

Commit working milestones.

Continue through the remaining implementation backlog.

A milestone is complete only when its functionality and acceptance evidence exist.

## 1.3 Preserve scientific correctness

Never:

- Fabricate market data.
- Fabricate simulation results.
- Invent broker specifications.
- Mix synthetic and real historical evidence.
- Introduce lookahead bias.
- Double-count spreads or transaction costs.
- Silently change execution assumptions.
- Hide failed experiments.
- Optimize using independent holdout outcomes.
- Promote training-only improvements as validated results.
- Describe approximate screening as a full tick backtest.
- Claim a benchmark that was not measured.
- Claim the application is bug-free or that future outcomes are guaranteed.

Scientific correctness takes priority over speed.

## 1.4 Continue across development sessions

This project is too large to assume that one development session will be sufficient.

Maintain durable, repository-backed progress so subsequent Codex sessions can continue without rebuilding completed work.

At the end of each milestone:

1. Commit the changes.
2. Run the relevant tests.
3. Record test results and failures.
4. Update the completion backlog.
5. Update the acceptance matrix.
6. Update known limitations.
7. Record the next unfinished task.

Do not repeatedly stop at intermediate achievements and present them as completion.

If a session ends, leave precise continuation instructions and the repository in a consistent state.

---

# 2. AUTHORITATIVE REQUIREMENTS AND PRIORITY

Read and reconcile:

1. `BLUEPRINT.md`
2. `docs/source/Factory.pdf`
3. `CODEX_BUILD_PROMPT.md`
4. `docs/source/Completion_Directive_2026-11-03.md`
5. `docs/source/Optimization_Handoff_Amendment_2026-11-03.md`
6. `docs/completion-backlog.md`
7. `docs/acceptance-matrix.md`
8. `docs/implementation-plan.md`
9. `known-limitations.md`
10. All applicable architecture decision records.

Use the original v2.0 blueprint for scientific rules, architecture, and acceptance requirements.

Use the later owner-approved amendments for the revised software/data handoff sequence and performance enhancements.

Do not silently waive mandatory requirements when conflicts arise. Record the conflict, its proposed resolution, and the resulting tests.

The original C0–C9 milestones and T01–T30 acceptance requirements remain mandatory.

Additional acceptance tests T31–T41 and subsequent tests are supplementary, not replacements.

---

# 3. REVISED CODEX → HERMES RESPONSIBILITIES

This is important.

**Codex does NOT need to download the entire 2025–2026 dataset before completing the software.**

Hermes Agent will perform the bulk historical-data acquisition on the VPS afterward.

However, this does not excuse incomplete data-ingestion software, missing validation functionality, or an untested research workflow.

There are three independent readiness states.

## SOFTWARE_VERIFIED

Codex is responsible for achieving this state.

Requirements:

- Complete application implementation.
- Complete integrated autonomous historical-research workflow.
- Representative real historical data successfully processed.
- Deterministic synthetic fixtures exercising every relevant period, instrument, and execution scenario.
- Fully implemented OOS, walk-forward, annual, holdout, and robustness workflows.
- Working diagnostic and strategy-improvement engine.
- Working candidate screening and optimization.
- Complete dashboard and API.
- Working installation, backup, update, rollback, and recovery software.
- Reproducible package and verified dependencies.
- Passing required software acceptance tests.
- Explicitly documented environmental and data-dependent gates.

## DATA_READY

Hermes is responsible for this stage after software handoff.

Requirements:

- Complete available 2025–2026 source acquisition.
- Verified source archives, timestamps, bid/ask records, and instrument identities.
- Calendar and market-session gap review.
- Complete and consistent dataset manifests.
- Valid multi-period catalog views.
- Correct incremental updates and corrections.

## OPERATION_READY

This is the subsequent target-host acceptance stage.

Requirements:

- Approved software installed on the VPS.
- Actual 4-vCPU/8-GB resource testing.
- Service startup and recovery verified.
- Real dataset ready.
- End-to-end historical research demonstrated on the installed system.
- Backup and restore verified.
- Required reliability and security controls passed.

Do not confuse these three states.

**Your immediate mission is SOFTWARE_VERIFIED.**

Finish everything that can reasonably be implemented and tested in Codex's environment.

When a test specifically requires the real Contabo VPS, create the executable test, document the prerequisites, and mark that environmental acceptance separately.

Do not claim you executed a target-host test without access to the target host.

---

# 4. COMPLETE HISTORICAL DATA SOFTWARE

Finish the entire data-management subsystem.

Required features:

- Free historical-data source adapters.
- All seven major Forex pairs plus XAUUSD.
- 2025 and 2026 historical-date support.
- Resumable acquisition.
- Retry and cooldown policies.
- Rate limiting and bounded downloads.
- Source correction and revision detection.
- Partial download recovery.
- Checkpointed batch ingestion.
- Exact timestamp conversion.
- Original source-record ordering.
- Equal-timestamp event ordering.
- Exact integer bid/ask prices.
- Reversible lossless compression.
- Source SHA256 verification.
- Dataset and partition fingerprints.
- Corrupted partition quarantine.
- Duplicate-detection policies that do not silently discard original events.
- Gap detection and calendar classification.
- Missing period reports.
- Immutable dataset-version history.
- Multi-month and multi-year dataset views.
- Incremental source updates.
- Storage quotas.
- Compaction where safe.
- Cache invalidation after source revisions.
- Safe recovery following interrupted imports.
- Data provenance and licensing metadata.
- Accurate dataset status in the dashboard.

Use existing Parquet/ZSTD storage.

Do not replace it merely because a newer codec or database claims better compression.

Preserve canonical source event ordering.

Use representative real historical data to verify ingestion and processing.

Use controlled synthetic multi-month and multi-quarter fixtures to test all calendar boundaries, gaps, source revisions, and restart behavior.

Provide Hermes with a documented, reproducible command or supported workflow for downloading the complete historical dataset after handoff.

The data manager must be able to continue incrementally without destroying previously verified data.

---

# 5. FINISH INSTRUMENT AND MONETARY CORRECTNESS

This is a critical blocker in the current implementation.

Complete the software supporting:

- EURUSD
- GBPUSD
- USDJPY
- USDCHF
- USDCAD
- AUDUSD
- NZDUSD
- XAUUSD

Implement verified instrument-profile handling for:

- Price precision.
- Pip and tick definitions.
- Quote-currency conventions.
- Contract multiplier.
- Minimum and maximum simulated position sizes.
- Quantity increments.
- Simulated margin feasibility.
- Currency conversions using dated quotes.
- Monetary rounding.
- Account-currency P&L.
- Unrealized and realized equity.
- Cash and position reconciliation.
- Broker-profile feasibility where verified specifications are available.

Keep the canonical hypothetical research scenario:

- $20 starting balance.
- 10% of current simulated equity as the requested per-trade risk budget.
- Intended 1:3 stop-to-target price distance.
- Conservative effective two-pip spread floor.
- Two-pip adverse slippage assumptions for eligible fills under the versioned policy.
- No commission in the selected scenario.
- Maximum intended 24-hour holding period.

Do not assume all instruments have identical monetary characteristics.

In particular, do not infer Gold contract or tick value from its historical quote precision.

When required reference specifications are unavailable, support explicit UNKNOWN_SPEC or INSUFFICIENT_REFERENCE states.

Provide deterministic tests for USD-quoted pairs, JPY pairs, Gold, rounding boundaries, margin constraints, gaps, partial fills, and equity conservation.

Resolve the documented native rounding and finite-liquidity discrepancies without fabricating matching prices or rewriting actual engine fills.

An unresolved engine/reference mismatch must remain visible.

---

# 6. IMPLEMENT THE COMPLETE TWO-STAGE RESEARCH FUNNEL

The current exact-zero-signal Tier 0 screening implementation is a good foundation but is insufficient as the final screening engine.

Implement a genuine lightweight screening stage.

## Tier 0 — Fast approximate research screening

Requirements:

- Bounded and deterministic computation.
- Reuse already-computed closed-bar features.
- Candidate-specific signal evaluation.
- Basic cost-aware hypothetical outcome estimates.
- Ranking of candidates for expensive replay.
- Conservative assumptions.
- Bounded numerical memory usage.
- Clear distinction between approximate and authoritative outcomes.
- Persistent screening receipts.
- Training-only optimization.
- Screening CPU-time accounting.
- Duplicate and redundant-candidate elimination.
- Configurable shortlist policy.
- Validation of the screening policy against independent authoritative replay samples.

Benchmark a lean NumPy/Numba implementation.

Evaluate RaptorBT only if its measured behavior, maintenance burden, and correctness justify its installation.

Do not install multiple competing engines by default.

## Tier 2 — Authoritative detailed simulation

Preserve NautilusTrader as the authoritative detailed event simulator.

Only candidates admitted by the configured research policy need full replay, except for deliberate rejection audits.

The detailed engine must use genuine bid/ask quote events and the canonical versioned execution assumptions.

It must preserve:

- Strict event causality.
- No future-data leakage.
- Deterministic order submission and execution ordering.
- Stop-loss and take-profit semantics.
- Partial fills.
- Cancellation races.
- Missing quotes.
- Gaps.
- Infeasible simulated position sizes.
- Holding deadlines.
- Execution traces.
- Reproducible P&L.

## Screening false-negative auditing

This is mandatory.

The screener must not become an unchecked source of scientific bias.

Maintain a versioned policy that periodically takes a controlled sample of screened-out candidates through NautilusTrader.

Compare screening decisions with authoritative results.

Record false-negative behavior, disagreements, and source revisions.

If the screening policy becomes unreliable, prevent its unverified use for scientific promotion and retain an auditable failure report.

Never claim a screened candidate received a complete detailed backtest unless it actually did.

---

# 7. COMPLETE SHARED FEATURES AND PERFORMANCE OPTIMIZATION

Finish the cache and high-throughput architecture without sacrificing accuracy.

Implement:

- Shared closed-bar storage.
- Shared indicator outputs.
- Reuse across strategies with identical feature parameters.
- Cache keys that exclude irrelevant strategy parameters.
- Dataset and source-version invalidation.
- Code-version invalidation.
- Timeframe and source-boundary identity.
- Exact warm-up policies.
- Bounded RAM and disk cache budgets.
- Read-only sharing where appropriate.
- Streaming computations.
- Parquet column pruning.
- Row-group filtering and predicate pushdown.
- Efficient disk reads.
- Cache hit, miss, eviction, and reuse metrics.
- Immutable experiment-result reuse.
- Accurate resource accounting.

Preserve exact integer quote storage.

Do not alter source event ordering to improve compression.

Benchmark lossless compression choices without changing source semantics.

If a compiled kernel is faster, retain it only after deterministic parity and memory tests pass.

If an optimization produces no meaningful improvement, document the result and do not add unnecessary complexity.

Measure:

- Wall-clock time.
- CPU time.
- Peak worker RSS.
- Total memory consumption where measurable.
- Disk usage.
- Cache effectiveness.
- Screening throughput.
- Authoritative replay throughput.
- Data-import throughput.
- Recovery and restart overhead.

Never multiply unrelated benchmark ratios to claim a theoretical overall speedup.

---

# 8. FINISH THE AUTONOMOUS STRATEGY DISCOVERY SYSTEM

The Factory must be able to perform historical research continuously after initialization, without needing a person or an AI model to manually submit every new strategy.

Complete the research scheduler and discovery policy.

Support the strategy families required by the blueprint, including:

- Mean reversion.
- Trend.
- Momentum.
- Breakout.
- Reversal.
- Volatility/range.
- Session-aware hypotheses.
- Controlled multi-family combinations.

Support the specified entry timeframes and valid higher-timeframe confirmations.

The research controller must:

1. Identify available research instruments and historical training regions.
2. Allocate bounded research budgets.
3. Generate valid candidate strategies.
4. Deduplicate equivalent proposals.
5. Compute or retrieve shared features.
6. Perform fast screening.
7. Queue promising candidates for authoritative replay.
8. Collect actual results.
9. Store immutable experiment evidence.
10. Update optimizer feedback.
11. Identify unsuccessful or fragile candidates.
12. Trigger controlled diagnostics and improvement.
13. Perform scientific validation when candidates qualify.
14. Maintain independently comparable leaderboards.
15. Continue exploring new permitted hypotheses after previous batches finish.

Make all research scheduling recoverable after process crashes and restarts.

Do not repeatedly evaluate identical specifications without justification.

Maintain resource fairness across instruments, families, timeframes, and exploration stages.

Avoid unlimited concurrent workers.

Honor the actual VPS resource budgets.

No local LLM, Redis, Kubernetes, Kafka, Ray cluster, or additional infrastructure is required unless independently justified.

---

# 9. COMPLETE OPTUNA AND STRATEGY INNOVATION

Preserve existing persistent Optuna TPE.

Finish:

- Training-only optimization objectives.
- Bounded hyperparameter spaces.
- Stable resumption after restart.
- Duplicate proposal prevention.
- Experiment-result cache reuse.
- Correct treatment of in-flight proposals.
- Correct accounting of unsuccessful trials.
- Deterministic random seeds.
- CPU-based budget enforcement.
- Search-space expansion under versioned policies.
- Full trial lineage.
- Objective and validation separation.

Do not optimize on OOS or untouched holdout results.

Investigate a small typed evolutionary proposal method only if a controlled benchmark suggests it produces more useful and diverse hypotheses at a comparable computational cost.

Do not install a large genetic programming framework solely because evolutionary search is mentioned in the blueprint.

Any automatically generated strategy must conform to a validated declarative strategy specification.

Do not execute unrestricted AI-generated Python or arbitrary code inside trusted simulation workers.

An optional hosted Hermes/N​​ous agent may propose hypotheses and explanations, but it must not supply authoritative results, edit immutable metrics, or bypass validation.

The deterministic Factory must remain functional when the hosted model is unavailable.

---

# 10. COMPLETE THE STRATEGY DIAGNOSTIC & IMPROVEMENT ENGINE

This is one of the most important unfinished components.

A strategy that performs poorly must not simply disappear from the research system.

Implement a comprehensive autonomous diagnostic workflow.

## Trade-level forensics

For each completed simulated trade, analyze:

- Entry timestamp and source event.
- Entry-side quote.
- Exit-side quote.
- Actual execution prices.
- Stop-loss distance.
- Take-profit distance.
- Holding duration.
- Maximum favorable excursion.
- Maximum adverse excursion.
- Timing of MFE and MAE.
- Actual exit reason.
- Spread exposure.
- Slippage exposure.
- Partial fills.
- Gaps and delayed executions.
- Infeasible or skipped opportunities.
- Censored positions.
- Immediate stop events.
- Favorable movement followed by a stop.
- Near-target misses.
- Timeout outcomes.
- Session and market-regime classifications.
- Long/short differences.
- Losing streak patterns.
- Recovery patterns.

## Cohort analysis

Group outcomes by:

- Instrument.
- Strategy family.
- Timeframe.
- Market session.
- Volatility regime.
- Trend/range regime.
- Direction.
- Stop distance.
- Confirmation type.
- Entry condition.
- Year and chronological validation window.

Distinguish observed associations from proven causes.

## Automatic improvement

Use measured training evidence to propose controlled variants.

Examples include:

- Alternative confirmation conditions.
- Different entry filters.
- Different closed-bar lookbacks.
- Different supported timeframes.
- Different stop distances while retaining intended 1:3.
- Different volatility or session conditions.
- Controlled strategy-family combinations.

Each proposed child must have:

- A permanent strategy identity.
- Parent strategy identity.
- Specific changed fields.
- Explicit hypothesis.
- Reason supported by observed training diagnostics.
- Experiment contract.
- Frozen evaluation cohort.
- Resource budget.
- Actual simulation evidence.
- Result status.
- Independent validation status.

Never rewrite the parent strategy.

Never delete negative results.

Never mark a child as independently better based only on a training improvement.

Implement repeated improvement rounds under bounded budgets, diversity controls, and diminishing-return safeguards.

Ensure failed, inconclusive, censored, and rejected variants remain queryable in the dashboard.

---

# 11. COMPLETE SCIENTIFIC VALIDATION

Implement the complete validation workflow from the original blueprint.

This includes:

- Separate evaluation of 2025 and 2026.
- Chronological combined-period reporting.
- Three-month walk-forward cycles.
- Explicit training and evaluation windows.
- Proper purging and embargo where needed.
- Closed-timeframe signal availability.
- No future information leakage.
- WFO parameter selection or refitting using permitted past data only.
- Independent OOS evaluation.
- Protected final holdout workflow.
- Holdout-consumption records.
- Annual trade counts.
- Censored-position treatment.
- Drawdown and simulated insolvency metrics.
- Maximum losing streak.
- Maximum winning streak.
- Recovery behavior.
- Profit factor and expectancy.
- Confidence intervals.
- Multiple-testing safeguards.
- Parameter sensitivity and stability analysis.
- Robustness across regimes and instruments.
- Cost sensitivity under separately labeled research scenarios.
- Reproducible validation decisions.
- Permanent negative evidence.

## Parameter Stability Laboratory

Implement neighborhood analysis around selected strategy parameters.

Report:

- Whether performance depends on a narrow isolated optimum.
- Median results across nearby settings.
- Dispersion and stability of nearby outcomes.
- Sensitivity to stop distance.
- Sensitivity to lookback and threshold.
- Timeframe and confirmation sensitivity.
- Regime-dependent instability.

Do not use independent holdout feedback to optimize parameter neighborhoods.

## Validation outcomes

Use explicit statuses such as:

- VALIDATED
- OOS_FAILED
- FAILED_CHECKS
- INSUFFICIENT_EVIDENCE
- DATA_UNAVAILABLE
- EXECUTION_INVALID

Only promote independently validated results to validated leaderboards.

Never combine incompatible datasets, execution versions, or evaluation periods into a misleading ranking.

Support five leaderboard positions per instrument, with separate all-candidates and validated views.

Keep the original hypothetical performance objectives as research filters rather than guaranteed outcomes.

If no candidate qualifies, report that truthfully.

---

# 12. COMPLETE THE DASHBOARD

The existing dashboard is a useful beginning, but the final application must not remain primarily a raw JSON inspector.

Build the complete responsive dashboard specified in the blueprint.

Required areas:

## Overview

Show actual system state, research activity, completed simulations, resource use, data readiness, active jobs, failures, and validation status.

## Eight instrument leaderboards

Separate tables for the seven major Forex pairs and Gold.

Show the top five candidates per instrument, with correct eligibility, provenance, ranking policy and validation labels.

## Strategy detail

Show strategy identity, family, parameters, timeframes, confirmations, fixed stop/target policy, experiment history, validation outcomes and performance.

## Simulation analytics

Include:

- Hypothetical equity curve.
- Drawdown.
- Win/loss distribution.
- Trade frequency.
- Holding duration.
- Annual results.
- Cost sensitivity.
- Winning and losing streaks.
- Risk and feasibility warnings.

## Diagnostic laboratory

Include:

- MFE/MAE charts.
- Stop-loss failure categories.
- Near-target outcomes.
- Session/regime distributions.
- Skipped trade explanations.
- Quote and execution-event inspection.
- Source-backed forensic views.

## Strategy Improvement Workshop

Show:

- Parent strategy.
- Proposed child.
- Changed parameters.
- Hypothesis.
- Actual test results.
- Controlled comparison.
- Lineage tree.
- Improvement history.
- Negative and inconclusive evidence.

## Scientific Validation Laboratory

Show chronological windows, OOS results, walk-forward folds, parameter stability, holdout status and validation failures.

## Research and coverage

Show family/instrument/timeframe coverage, attempted hypotheses, optimizer state, screening decisions and CPU-budget allocation.

## Market Data Center

Show source manifests, verified periods, missing periods, gaps, source corrections and download/recovery status.

## Operations and Hermes console

Show services, queue, workers, resource limits, logs, pause/resume, safe cancellation, backups and authenticated operations.

## Exports

Provide usable JSON/CSV and appropriate report exports with source identities and clear synthetic/historical labels.

Use real API data.

Do not create fake performance charts.

Implement accessible states for loading, missing data, errors, insufficient evidence and failed operations.

Include browser-level end-to-end tests for the important user workflows.

---

# 13. SECURITY AND DEPENDENCY RELEASE GATES

The latest GitHub dependency-review workflow is failing.

Investigate and resolve the remaining advisories associated with the pinned `fsspec` dependency and dashboard `deepmerge` chain.

Do not:

- Disable audit workflows.
- Ignore vulnerabilities without a reviewed disposition.
- Force incompatible dependencies.
- Install unmaintained replacements without evaluation.
- Silently downgrade security.
- Break the NautilusTrader integration.

Prefer supported and compatible upstream fixes.

Where a supported fix is unavailable, document the vulnerability, affected dependency, reachability, mitigating controls, remaining exposure and required approval.

A security review must not falsely become a passing audit.

Additionally:

- Review repository visibility. The repository has been reported as public even though the blueprint requested private visibility.
- Never commit API tokens, access credentials, private keys or confidential environment files.
- Scan repository contents and history for accidental secrets.
- Preserve role-based API authorization.
- Keep the application bound to loopback by default.
- Use secure authenticated remote access.
- Validate file paths, uploads, exports and downloads.
- Preserve immutable scientific and audit records.
- Keep untrusted strategy suggestions isolated from executable application code.
- Enforce network and worker permissions.
- Review the full software supply chain and locked dependencies.

Do not change GitHub ownership or repository visibility without appropriate owner authorization.

---

# 14. COMPLETE INSTALLATION AND SERVICE MANAGEMENT

Finish the production-grade installation and lifecycle software.

Required capabilities:

- Supported Ubuntu installation verification.
- Hardware and environment checks.
- Dependency and runtime verification.
- Reproducible Python package installation.
- Dashboard build and serving.
- Controlled application configuration.
- Least-privilege service account.
- Systemd service management.
- Automatic restart after process failure.
- Restart after machine reboot.
- State-directory permissions.
- Resource limits.
- Log management.
- Health and readiness endpoints.
- Disk-space checks.
- Backup scheduling.
- Restore verification.
- Controlled updates.
- Database migration checks.
- Rollback procedures.
- Source and artifact integrity verification.
- Safe application shutdown.
- Recovery from interrupted jobs.
- Recovery from interrupted source imports.
- Corrupted-state detection.
- Avoidance of duplicate simulation completion.
- No accidental destructive reinitialization.

A fresh installation must not require manually editing source code.

An update must preserve previous immutable experiment history.

Rollback must not silently corrupt state or pretend an incompatible database migration was reversed.

Test installation and recovery in supported isolated environments.

Prepare target-VPS acceptance procedures that Hermes can execute after handoff.

---

# 15. TEST THE COMPLETE SYSTEM, NOT JUST INDIVIDUAL MODULES

Build and run comprehensive automated tests covering the full product.

At minimum, test:

### Data correctness

- Exact bid/ask round-trip.
- Duplicate and tied timestamp events.
- Source revision invalidation.
- Gap detection and classification.
- Incremental import.
- Interrupted import recovery.
- Multi-period views.
- Catalog corruption rejection.

### Execution correctness

- Long and short orders.
- Correct bid/ask usage.
- Spread floor without double-counting.
- Adverse slippage.
- Stop gaps.
- Take-profit limits.
- Partial fills.
- Cancellation races.
- Missing quotes.
- Position feasibility.
- Margin feasibility.
- P&L conservation.
- Currency conversion.
- Monetary rounding.
- Trade deadlines.
- Equal-timestamp causal ordering.

### Research correctness

- All implemented families.
- Every supported timeframe.
- Multi-timeframe confirmations.
- Canonical fingerprints.
- Duplicate suppression.
- Tier 0 screening.
- Screening false-negative audits.
- Optuna persistence.
- Restart-safe optimization.
- CPU budget enforcement.
- Failed-hypothesis retention.

### Improvement correctness

- Correct diagnostic classification.
- Parent preservation.
- Child identity.
- Controlled changes.
- Frozen cohorts.
- Inconclusive comparisons.
- Failed children.
- Repeated improvement.
- Independent validation separation.

### Scientific validation

- Multi-quarter chronological splits.
- Annual reporting.
- Walk-forward refitting.
- Purging and embargo.
- Holdout leakage prevention.
- OOS failure rejection.
- Parameter stability.
- Multiple-testing handling.
- Correct validated rankings.

### Operational reliability

- Worker crash.
- Coordinator crash.
- Restart.
- Duplicate job attempts.
- Memory exhaustion.
- Disk exhaustion.
- Network interruption.
- Source-provider failure.
- Backup.
- Restore.
- Update.
- Rollback.
- Reproducible release packaging.

### Browser and API

- Authentication.
- Role permissions.
- API error responses.
- User controls.
- Strategy inspection.
- Charts.
- Improvement workflow.
- Validation reports.
- Data Center.
- Research status.
- Exports.
- Mobile layout.

Use independent reference implementations or golden fixtures for critical numerical calculations.

Passing a unit test does not automatically prove that an entire original blueprint acceptance gate has passed.

Maintain explicit evidence for each acceptance requirement.

---

# 16. REQUIRED FULL END-TO-END REHEARSAL

Before claiming SOFTWARE_VERIFIED, execute a complete controlled research workflow.

Use representative verified real bid/ask data and deterministic synthetic multi-quarter fixtures where needed.

The rehearsal must demonstrate:

**Import → Verify → Catalog → Features → Generate → Screen → Replay → Diagnose → Improve → Compare → Validate → Rank → Dashboard → Restart → Resume → Backup → Restore**

Verify each stage.

Do not substitute an isolated happy-path unit test for this complete workflow.

The test should exercise:

1. An initial set of candidate strategies.
2. At least one rejected screening candidate.
3. At least one authoritative replay.
4. A completed trade history.
5. Diagnostic classification.
6. At least one proposed improvement.
7. Actual child-strategy evaluation.
8. Parent-child comparison.
9. An independently evaluated chronological window.
10. A failed or insufficiently evidenced candidate.
11. A correctly promoted eligible candidate using controlled reference fixtures, if the acceptance rules are satisfied.
12. Queryable leaderboard results.
13. Browser presentation of the real results.
14. Coordinator restart without lost or duplicated evidence.
15. Backup and restored-state verification.

Any artificially constructed reference outcome must remain clearly labeled as a test fixture, never as a real historical market result.

A working full vertical pipeline is mandatory.

---

# 17. PERFORMANCE ACCEPTANCE

The intended hardware is:

- 4 vCPU.
- 8 GB RAM.
- CPU-only.
- Limited disk resources.
- Continuous research operations.

Build a performance test suite that exercises the relevant resource limits.

Measure both cold and warm conditions where possible.

Measure genuine data-import and full replay workloads separately from synthetic screening workloads.

Test under an enforced 8-GB memory limit where supported.

Record exact environmental differences when development hardware does not match the target VPS.

Do not invent throughput targets or imply billions of full tick backtests per hour.

Optimize only measured bottlenecks.

Preserve determinism and scientific parity after every optimization.

The priority is **correctness, stable memory usage, reliability, and efficient use of the available CPU**.

---

# 18. REPRODUCIBLE BUILD AND RELEASE CANDIDATE

Once the full software implementation is complete:

1. Run the complete test suite.
2. Run lint and formatting checks.
3. Run frontend type checks and build.
4. Run API and browser integration tests.
5. Run dependency security checks.
6. Verify all migrations.
7. Verify package contents.
8. Verify source fingerprints.
9. Build reproducible release artifacts.
10. Verify backup and restoration.
11. Verify that all required software gates have actual evidence.
12. Produce a complete build report.

Provide:

- Exact Git commit.
- Release candidate identifier.
- Actual dependency versions.
- OS/runtime information.
- Exact commands executed.
- Exit codes.
- Passing tests.
- Failed tests.
- Skipped tests.
- Unresolved blockers.
- Resource benchmarks.
- Security results.
- Source and artifact hashes.
- Installation documentation.
- Hermes handoff instructions.

A GitHub pull request is not itself a release.

Do not create a misleading production tag.

Only mark SOFTWARE_VERIFIED when the approved software acceptance criteria genuinely pass.

If software verification is blocked by unavailable credentials, host access, upstream defects or security decisions, distinguish those blockers explicitly rather than treating them as completed.

---

# 19. FINISH THE HERMES HANDOFF

Prepare documentation allowing Hermes Agent to take over the tested Factory without rewriting it.

Hermes must be able to:

- Verify the release identity.
- Install the application.
- Diagnose configuration problems.
- Verify environment prerequisites.
- Configure authorized data sources.
- Download the complete available historical dataset.
- Resume interrupted backfills.
- Verify source quality.
- Build annual and combined historical views.
- Run historical research.
- Monitor the scheduler.
- Examine failed experiments.
- Review strategy improvements.
- Inspect scientific validation.
- Use dashboard controls.
- Monitor resource usage.
- Restart services safely.
- Back up and restore state.
- Verify updates before applying them.
- Recover from common failures.
- Produce truthful operational reports.

Document the exact responsibilities of Codex, Hermes and the repository owner.

The Hermes handoff must include the known limitations, especially any unfinished target-host acceptance checks.

No autonomous real-money execution functionality belongs in this release.

---

# 20. FINAL RULE: DO NOT STOP AT ANOTHER PARTIAL MILESTONE

Your previous development checkpoints have been valuable, but they have repeatedly ended before the complete project was implemented.

This time, work toward the **full SOFTWARE_VERIFIED objective**.

Do not stop merely because:

- Another 20 tests pass.
- Another synthetic campaign succeeds.
- A new module exists.
- A data importer works.
- A new optimizer is installed.
- A dashboard page renders.
- Another benchmark improves.

Those are intermediate achievements, not the final objective.

Continue with the remaining work in priority order.

If progress must span multiple sessions, preserve exact resumable state in Git.

Never claim completion merely because you have exhausted the current session.

If an external issue genuinely prevents completion, report:

- What is blocked.
- Why it is blocked.
- What you attempted.
- What independent work is complete.
- What evidence exists.
- What owner action is required.

Do not silently weaken the acceptance criteria.

---

# 21. REQUIRED FINAL RESPONSE

When you believe the software is complete, provide a clear final report containing:

**A. Repository status**

- Current commit.
- Pull request.
- Release candidate.
- Repository visibility.
- Clean working tree status.

**B. Implementation status**

- Complete module inventory.
- All mandatory original features.
- Every accepted optimization.
- Every remaining limitation.

**C. Scientific verification**

- Data integrity.
- Execution correctness.
- Research automation.
- Screening.
- Diagnostics.
- Improvement.
- OOS.
- Walk-forward.
- Holdout.
- Annual results.
- Leaderboards.

**D. Test evidence**

- Exact commands.
- Test totals.
- CI results.
- Browser test results.
- Integration and end-to-end results.
- Failure and recovery tests.

**E. Performance**

- Actual CPU usage.
- Peak RAM.
- Storage usage.
- Tier 0 throughput.
- Detailed simulation throughput.
- Cache efficiency.
- Hardware limitations.

**F. Security**

- Dependency audit results.
- Remaining advisories.
- Credentials/secret checks.
- Deployment restrictions.

**G. Handoff**

- Installation requirements.
- Hermes setup instructions.
- Full historical-backfill procedure.
- Target-host acceptance commands.
- Known blockers.

**H. Readiness**

Explicitly report:

- `SOFTWARE_VERIFIED`
- `DATA_READY`
- `OPERATION_READY`

Do not set any of these to true without passing their actual defined gates.

---

# BEGIN IMPLEMENTATION NOW

Start by examining the latest repository state rather than assuming commit `9034cbc` is still current.

Perform a code-versus-blueprint gap analysis.

Update the active backlog to exclude functions that are already correctly implemented and tested.

Then implement the highest-priority remaining work.

Continue through correctness, real-data integration, autonomous research, diagnostics, independent validation, complete dashboard, security, reliability and reproducible handoff.

**Do not create another partial-finish announcement. The objective is the complete, tested Hermes Factory SOFTWARE_VERIFIED release candidate, with bulk historical-data acquisition reserved for Hermes on the VPS.**

Preserve the existing architecture and evidence.

Build, test, fix and integrate the actual software.

Historical and paper-simulation research only.