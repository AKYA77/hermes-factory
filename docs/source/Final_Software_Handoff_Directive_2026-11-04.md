# HERMES FACTORY — FINAL SOFTWARE COMPLETION & HERMES HANDOFF DIRECTIVE

## MISSION

Complete the entire Hermes Factory software implementation and prepare an independently verifiable release candidate for Hermes Agent.

**Repository:** `AKYA77/hermes-factory`  
**Branch:** `build/initial-factory`  
**Last externally audited commit:** `e6a2a6c070c3ee9c9f8743ad4a709af2c8078262`

The original Hermes Factory v2.0 blueprint, accepted completion directives, and software-handoff amendment remain authoritative.

This task is not to produce another partial milestone.

**The target is a fully implemented, tested, documented, reproducible historical-research and paper-simulation system.**

Do not add real-money brokerage execution.

Do not rewrite correctly implemented components.

Do not declare completion merely because unit tests pass.

---

## 1. AUDIT AND PRESERVE THE CURRENT WORK

Start by reading the latest remote branch and verifying the current HEAD.

Read:

- `AGENTS.md`
- `BLUEPRINT.md`
- `docs/source/Factory.pdf`
- `CODEX_BUILD_PROMPT.md`
- All owner completion directives under `docs/source/`
- `completion-ledger.json`
- `development-state.json`
- `NEXT_ACTION.md`
- `docs/acceptance-matrix.md`
- `docs/implementation-plan.md`
- `known-limitations.md`
- `release-manifest.json`
- Current milestone reports and architecture decision records.

Inspect actual source code and verification evidence rather than trusting summaries.

Reconcile the full backlog against current code.

Preserve the verified implementation of:

- Execution accounting v4.
- Native monetary and dated FX reference adapters.
- Immutable source and experiment identities.
- Multi-period dataset catalogs.
- Historical source-quality and revision tracking.
- Reviewed input admission and revocation.
- Persistent Optuna search.
- Shared disk-based closed-bar caching.
- Strict zero-signal screening and native rejection audits.
- Protected holdout lifecycle.
- Scientific validation protocol v2.
- Annual/pooled reporting components.
- Existing bounded automatic improvement.
- Dashboard validation and source panels.
- Existing API security and recovery safeguards.

Do not repeat expensive regression campaigns unless code changes or verification requirements justify them.

Create a prioritized, executable remaining-work plan, then implement it.

Every requirement needs actual evidence, not just an implementation claim.

---

## 2. FINISH THE SCIENTIFIC DATA AND INSTRUMENT SOFTWARE

Complete the software necessary to accept genuine historical data safely.

Specifically finish:

1. Primary-reference research and verification for supported instrument conventions.
2. Accurate account-currency, contract-size, volume, margin, pip/tick, Gold and JPY handling.
3. Calendar and trading-session acceptance.
4. Independent reconciliation of source gaps and corrections.
5. Source-review and admission propagation through research workers.
6. Source-version-aware experiment invalidation.
7. Interrupted intra-partition download/import resume.
8. Source refresh and revision scheduling.
9. Quotas, retention, compaction and cleanup safeguards.
10. Complete market-data management APIs and user interface.

Use documented authoritative reference sources wherever possible.

Do not assume observed quote precision establishes broker contract specifications.

If multiple legitimate profile conventions exist, implement explicit versioned profiles and expose their assumptions.

Never silently select one speculative profile as a universal truth.

Where real broker-specific information is genuinely unavailable, clearly separate verified generic research profiles from provider-specific assumptions.

Do not make the entire software project depend on an unnecessary human-only approval if the software can support explicit, reviewable reference profiles.

Keep the final research-results status appropriately restricted until the required reference assumptions are accepted.

### Historical acquisition boundary

Do NOT spend this task downloading the entire available 2025–2026 dataset.

The approved division of responsibility is:

- Codex completes the downloader, catalog manager, validators, scientific workflows and tests.
- Hermes performs the full historical backfill on the VPS after software handoff.

Use existing January 2025 all-instrument data, February EURUSD data, and bounded additional real samples when necessary.

Use deterministic multi-quarter and cross-year fixtures for full software acceptance.

The handoff must include a tested full-backfill workflow with resume, gap review, source corrections and incremental updates.

---

## 3. COMPLETE THE AUTONOMOUS DISCOVERY ENGINE

Finish all supported strategy families and combinations required by the blueprint.

The current mean-reversion, momentum and breakout implementation is insufficient for final acceptance.

Add complete declarative, causally correct implementations for the remaining required families and valid combinations.

Support the required timeframes, higher-timeframe confirmations, parameter ranges and versioned stop-distance searches.

Implement automatic discovery of new eligible research regions.

The scheduler must autonomously:

- Identify available approved training datasets.
- Allocate research budgets fairly.
- Generate candidate specifications.
- Deduplicate equivalent strategies.
- Retrieve shared features.
- Run Tier 0 screening.
- Queue selected candidates for NautilusTrader.
- Collect and verify results.
- Update persistent Optuna feedback.
- Trigger diagnostics and improvements.
- Propose controlled new families/confirmations.
- Retain negative hypotheses.
- Submit eligible frozen candidates to independent validation.
- Update comparable research leaderboards.

This must work without an AI model being continuously available.

Optional Hermes-generated hypotheses must be accepted only through validated declarative contracts.

Never execute arbitrary generated source code inside trusted research workers.

Complete durable scheduling, interruption recovery, CPU fairness and bounded-memory behavior.

Demonstrate that the research system continues after previously registered regions are exhausted, rather than repeatedly idling until a person manually registers new ones.

---

## 4. COMPLETE TIER 0 SCREENING AND SHARED INDICATORS

The current exact-zero screening is correct but too limited.

The new cost-label shadow mode is informative, but it has already demonstrated a real false-negative counterexample in controlled tests.

Do not enable unconditional approximate pruning.

Implement:

- Shared, reusable indicator transforms.
- Feature identity independent of unrelated stop/target settings.
- Versioned feature and dataset invalidation.
- Bounded compiled screening where benchmarks justify it.
- Conservative candidate scoring.
- Frozen calibration protocols.
- Explicit shortlist and rejection policies.
- Authoritative NautilusTrader audit cohorts.
- False-negative detection and retention.
- Policy rollback/fallback.
- Selection-bias accounting.
- Independent policy performance measurements.
- Persistent screening provenance.
- Correct screening CPU attribution.

A cost-based rejection policy must pass its defined false-negative safeguards before use.

If it cannot satisfy the scientific requirements, keep it disabled and use a safe shortlist policy that does not falsely certify rejected candidates.

Optimize measured bottlenecks, not theoretical throughput.

Do not install another authoritative backtesting engine.

Do not replace exact integer storage with floating-point approximations.

---

## 5. COMPLETE THE DIAGNOSTIC AND IMPROVEMENT ENGINE

Extend the existing bounded parent-child functionality into the full blueprint-required system.

Implement:

- Complete MFE/MAE forensic analysis.
- Session-aware diagnostics.
- Market regime classification.
- Volatility and trend/range cohorts.
- Long/short comparisons.
- Immediate stop and favorable-then-stop cohorts.
- Near-target and timeout analysis.
- Cost and stop-distance sensitivity.
- Entry and confirmation effectiveness.
- Consecutive-loss behavior.
- Simulated equity recovery patterns.
- Controlled iterative child generation.
- Parent and child complete-trade-set comparisons.
- Statistical uncertainty and insufficient-sample warnings.
- Diversity-aware variant selection.
- Recursive exploration with strict resource limits.
- Immutable parent/child history.
- Permanent failed and inconclusive hypothesis retention.
- Independent confirmation of improvements.

Keep original contracts immutable.

Separate training diagnosis from independent validation.

Never use protected holdout information to select new variants.

Provide actual API and dashboard views for all major diagnostic evidence.

---

## 6. FINISH INDEPENDENT VALIDATION END TO END

The existing validation protocol and holdout infrastructure are valuable foundations. Now connect them into a complete, independently verified scientific workflow.

Implement and demonstrate:

1. Training and frozen candidate selection.
2. Prior-only chronological parameter refitting.
3. Three-month walk-forward cycles.
4. Complete OOS evaluation.
5. Separate 2025 and 2026 annual reports.
6. Correct pooled analysis.
7. Protected final holdout reservation and one-time consumption.
8. Parameter Stability Laboratory.
9. Sensitivity to cost assumptions.
10. Session and market-regime robustness.
11. Multiple-testing and global selection safeguards.
12. Candidate comparability and diversification checks.
13. Correct validated top-five rankings per supported instrument.
14. Explicit failure, rejection and insufficient-evidence outcomes.
15. Immutable validation provenance.

Fix any remaining nonauthoritative helper paths that only return INSUFFICIENT_EVIDENCE instead of integrating with the full evaluation state machine.

Implement independent reference fixtures to prove correct promotion and rejection logic.

Test cases must include:

- Strong training performance but failed OOS.
- Successful chronological validation using a labeled reference fixture.
- Insufficient sample size.
- Incompatible datasets.
- Different execution versions.
- Censored positions.
- Repeated holdout access.
- Holdout leakage attempts.
- Historical source revision.
- Instrument conversion failures.
- Parameter fragility.
- Multiple-testing inflation.

Synthetic fixtures can prove software correctness, but may never become actual historical strategy results.

Also perform a genuine approved real-source native simulation rehearsal once reference and admission prerequisites are satisfied.

A successful real-data import or feature-compilation benchmark alone is not sufficient.

---

## 7. COMPLETE THE DASHBOARD

The dashboard must become the complete research control plane defined by the blueprint.

Finish the following connected experiences:

**Overview:** Status, jobs, active research, instrument coverage, warnings, resource usage and readiness.

**Strategy Explorer:** Families, rules, parameters, confirmations, experiment history and provenance.

**Leaderboards:** Validated and exploratory rankings separated by instrument, with correct comparability and diversity controls.

**Performance:** Equity, drawdown, win/loss, expectancy, frequency, annual results, streaks, costs and holding-time charts.

**Diagnostics:** MFE/MAE, execution paths, stop categories, sessions, regimes, trade cohorts and failure explanations.

**Improvement Workshop:** Parent-child lineage, hypotheses, comparative outcomes, rejected variants and pending improvements.

**Scientific Validation:** Walk-forward folds, OOS results, holdout states, annual/pooled analysis, parameter stability and robustness.

**Research Coverage:** Families, timeframes, confirmation combinations, optimizers, screening audits and CPU allocation.

**Data Center:** Source reviews, missing periods, gaps, revisions, quarantine, restoration, resume and incremental download controls.

**Operations:** Services, workers, resource budgets, logs, pause/resume, safe cancellation, recovery, backup, update status and authenticated supervisor controls.

**Exports:** Complete usable JSON/CSV/report exports with immutable experiment identity and explicit synthetic/real labels.

Implement actual interactive charts and controls, not raw JSON as the primary user experience.

Run real-browser end-to-end tests covering navigation, roles, error states, missing evidence, exports, desktop and mobile.

Do not fabricate historical profitability charts or validated rankings.

---

## 8. FINISH INSTALLATION, RELIABILITY AND RECOVERY

The existing `scripts/install.sh` is development-only. Complete the operational software without falsely claiming that deployment has already been verified on Contabo.

Finish:

- Supported Ubuntu environment checks.
- Reproducible installation.
- Least-privilege service account.
- Systemd unit installation and validation.
- API/dashboard configuration.
- Secure secret handling.
- Process resource limits.
- Boot recovery.
- Crash recovery.
- Worker kill/restart handling.
- Disk-full behavior.
- Source download interruption handling.
- Database migration safety.
- Atomic release activation.
- Updates.
- Safe rollback.
- Full backup.
- Restore verification.
- Backup retention and appropriate encryption.
- Off-host backup configuration interfaces.
- Immutable research-state preservation.
- Health and readiness checks.
- Complete operator and Hermes runbooks.

Test these components inside suitable isolated Linux environments.

Where actual target VPS access is unavailable, create executable acceptance commands and clearly mark the target-only results as pending.

Do not mark OPERATION_READY without real target-host verification.

---

## 9. SECURITY MUST BE ADDRESSED

The currently unresolved dependency findings are:

- PYSEC-2026-4217, associated with the pinned fsspec dependency.
- GHSA-gcqx-w48m-w2h4 in the dashboard dependency chain.

Investigate currently supported fixes and compatible dependency alternatives.

If a supported upstream fix is available, apply and test it.

If the vulnerability is unpatched or a compatible fix is unavailable, document the full threat model, reachability, mitigations, remaining risk and required release decision.

Do not disable auditing or override incompatible dependency pins merely to turn CI green.

The source repository currently appears PUBLIC, whereas the original requirement specified PRIVATE.

Check source and history for accidental credentials.

Report the visibility mismatch clearly to the owner. Do not make an unauthorized visibility change.

Finish API authorization, path safety, export safety, content security policies, worker isolation and supply-chain verification.

Security acceptance must be supported by reviewed evidence.

---

## 10. FULL SOFTWARE VERIFICATION

Stop treating increasing unit-test counts as the final achievement.

Create and execute complete software acceptance workflows.

The mandatory end-to-end path is:

SOURCE → IMPORT → VERIFY → ADMIT → MULTI-PERIOD DATASET → FEATURES → GENERATE → SCREEN → NAUTILUS SIMULATION → DIAGNOSE → IMPROVE → INDEPENDENT VALIDATION → RANK → DASHBOARD → RESTART → BACKUP → RESTORE.

Test with representative genuine bid/ask history and labeled deterministic reference fixtures.

Include failure cases and source revisions.

Require exact scientific identity and independent numerical reference agreement.

Test every supported instrument, family and timeframe at the appropriate unit, integration and system levels.

Test the complete historical research workflow under resource constraints.

Use enforced 4-vCPU/8-GB-equivalent environments where possible.

Record actual CPU, memory, disk and elapsed-time measurements.

Do not invent production performance figures.

---

## 11. MAKE COMPLETION EVIDENCE CONSISTENT

There are currently stale repository documents and manifests.

For example, `README.md` still describes older test counts and unfinished historical components without reflecting all of the latest implementation.

`release-manifest.json` also references an old code commit.

Correct these inconsistencies when preparing the final software release candidate.

Rebuild all current-head reports and release evidence from actual tests.

Ensure:

- Current Git HEAD matches the declared release candidate.
- Scientific source identity matches tested source.
- Package contents match the tested files.
- All required migrations are included.
- Test receipts exist and are verifiable.
- Lockfiles match actual dependencies.
- Release hashes are current.
- README and operator documentation match functionality.
- Handoff instructions work from a fresh environment.
- Known limitations remain honest.
- Historical evidence is preserved rather than rewritten.

Do not mark the release ready merely because a JSON field was changed.

---

## 12. CODEX MUST FINISH BEFORE REQUESTING ANOTHER GENERAL REVIEW

This is a continuation of the existing persistent completion goal.

Do not ask the owner to repeat previously established requirements.

Do not send another generic architectural plan.

Do not respond with only a successful development milestone.

Implement the remaining software in descending priority:

**Priority 1:** Scientific correctness, historical evaluation admission and independent validation.

**Priority 2:** Complete autonomous search, strategy families, calibrated screening, diagnosis and improvement.

**Priority 3:** Complete dashboard, data operations and real end-to-end browser workflows.

**Priority 4:** Production installation software, recovery, security and reproducible packaging.

**Priority 5:** Final integration, performance verification, acceptance reconciliation and Hermes handoff.

Continue across development sessions using `NEXT_ACTION.md`, `completion-ledger.json` and committed test receipts.

If you reach a task-budget or session limit, make a clean checkpoint and preserve the exact next action.

Do not characterize that checkpoint as final completion.

If an external prerequisite is genuinely unavailable, complete all independent work first, document the smallest needed owner action, and preserve the blocker.

Do not invent approval, credentials, actual broker specifications, or VPS access.

---

## 13. PUBLISH ALL COMPLETED WORK

The previous Codex task completed substantial local work without initially publishing it to GitHub.

Prevent that problem from recurring.

At each verified milestone:

1. Commit completed changes.
2. Push to the authorized `build/initial-factory` branch or use the supported GitHub publishing workflow.
3. Verify the remote commit SHA.
4. Verify PR #1 reflects the commit.
5. Review CI checks against that exact SHA.
6. Preserve all existing results and source history.

Do not assume clicking Publish succeeded.

Do not claim remote publication from a local commit.

Do not merge, change repository visibility, or create a production deployment without authorization.

---

## 14. EXACT FINAL HANDOFF CRITERIA

The objective is SOFTWARE_VERIFIED, not premature OPERATION_READY.

SOFTWARE_VERIFIED requires:

- Complete mandatory software implementation.
- Actual tested real-data research integration.
- Full deterministic validation workflow.
- Complete autonomous research and improvement.
- Fully connected dashboard.
- Installation, backup, update and recovery software.
- Satisfactory and documented security disposition.
- Reproducible release artifacts.
- Complete Hermes operating instructions.
- All software acceptance gates passed with verifiable receipts.

DATA_READY requires full historical-data preparation on the VPS after handoff.

OPERATION_READY requires actual target-host installation, data acceptance, resilience testing and final operational validation.

Do not waive either of the latter requirements.

If any software criterion fails, SOFTWARE_VERIFIED remains false.

If all software criteria pass, produce a complete verified release-candidate package and state the remaining external acceptance steps separately.

---

## 15. REQUIRED FINAL RESPONSE

When the software is genuinely ready, report:

1. Exact verified GitHub commit and PR URL.
2. Current repository and CI status.
3. Complete implementation inventory.
4. Original C0–C9 and T01–T30 acceptance results.
5. Additional acceptance-gate results.
6. Genuine historical-data integration evidence.
7. Scientific reference and execution agreement.
8. Autonomous discovery, diagnosis and improvement proof.
9. OOS/WFO and protected-holdout proof.
10. Dashboard browser and API evidence.
11. Security findings and approved dispositions.
12. Installation, restart, backup and rollback test evidence.
13. Actual performance/resource measurements.
14. Reproducible release artifact and hashes.
15. Complete Hermes handoff and VPS backfill instructions.
16. Honest SOFTWARE_VERIFIED, DATA_READY and OPERATION_READY statuses.

Never change readiness fields without the corresponding verified evidence.

## BEGIN IMPLEMENTATION

Resume from the latest GitHub HEAD.

Preserve completed work.

Finish the remaining scientific, autonomous, graphical and operational software.

Run the required tests and fix failures.

Publish every verified implementation milestone.

Prepare the complete SOFTWARE_VERIFIED release candidate for Hermes Agent.

**Do not stop after another partial checkpoint and call it finished.**