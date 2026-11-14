HERMES FACTORY — CONTINUE UNTIL FULL COMPLETION

Continue working on the existing Hermes Factory repository:

Repository: https://github.com/AKYA77/hermes-factory
Branch: build/initial-factory
Pull request: #1
Last externally audited commit: e42714ee66948a6ff03497035320302a7f7150ea

You are continuing the existing project, NOT starting over.

1. Your primary objective

Complete the entire Hermes Factory according to the latest owner directive, approved blueprint, architecture, and all 79 acceptance requirements.

The last audit showed:

* 51 requirements PASS.
* 28 requirements NOT_TESTED.
* All three readiness gates FALSE.
* Rust execution parity substantially demonstrated.
* Rust not yet integrated as the primary factory executor.
* No verified Rust-versus-NautilusTrader performance benchmark.
* Major outstanding work in native Rust generation, TickFirstHitIndex, Arrow data access, historical data verification, performance validation, and operational readiness.

Your priority is now real implementation, integration, testing, and measurable performance—not simply finding ways to mark more requirements PASS.

First inspect the current Git HEAD. Do not assume the externally audited commit remains the latest.

2. Fix the strict 50% win-rate gate

The current ValidationCriteria.min_win_rate defaults to 0.5 but permits configuration down to zero.

The owner directive requires an absolute minimum of 50% verified post-cost win rate for qualification.

Fix this properly:

1. Ensure production research qualification can NEVER reduce the minimum below 50%.
2. Allow thresholds above 50%.
3. Keep exactly 50.00% inclusive.
4. Calculate win rate using exact closed-trade counts after applicable trading costs.
5. Reject unmeasured, insufficient, malformed, or below-threshold evidence.
6. Apply the gate consistently across qualifying decisions, including forward and final validation.
7. Preserve compatibility with immutable historical evidence and existing protocol versions without silently weakening the new policy.
8. Add positive, negative, boundary, integration, restart, and persistence tests.

If synthetic test fixtures need different thresholds, keep them explicitly isolated from production research and incapable of authorizing real historical qualification.

Do not mark the correction complete without passing tests.

3. Finish the Rust execution engine

Prioritize the remaining R01/R02 requirements.

Complete the Rust engine’s missing functionality, including:

* Exact equity and drawdown accounting.
* Open-position mark-to-market valuation.
* Correct fee, spread, and adverse-slippage accounting.
* Gold, JPY, and cross-currency conversion behavior.
* Accurate handling of order states, partial fills, gaps, stops, targets, timeouts, and restarts.
* Verified instrument and broker profile requirements.

Use NautilusTrader’s frozen reference results and the existing parity harnesses to protect execution accuracy.

Do not replace or remove NautilusTrader until its replacement is fully integrated and independently verified.

Resolve the reference-oracle problem by implementing an independent, non-Nautilus reference for the declared execution semantics, validating it against the frozen reference goldens and suitable independently calculated cases. Retain the evidence required to detect future regressions.

Then connect the Rust engine to the actual factory execution pipeline through a stable, versioned interface.

The factory must use the Rust executor for its intended primary historical/paper-research execution path—not merely invoke it from test scripts.

Preserve all existing scientific safeguards and evidence contracts.

4. Benchmark Rust against NautilusTrader

Perform a fair, reproducible comparison using identical datasets, strategy signals, execution assumptions, and workloads.

Measure separately:

* Data reading and decoding.
* Signal compilation.
* Sequential execution.
* End-to-end workload runtime.
* CPU time and wall time.
* Peak memory consumption.
* Disk I/O.
* Cold-cache and warm-cache performance.
* Restart and recovery overhead.

Include small, medium, and large genuine historical workloads where source quality permits.

Enforce the target 4-vCPU / 8-GiB resource envelope rather than relying on the VPS’s larger unrestricted capacity.

Report actual results in a committed benchmark report, with methodology and commands sufficient to reproduce them.

Never invent speedup factors, extrapolate synthetic results to historical throughput without evidence, or describe combined harness time as isolated Rust execution time.

5. Implement the remaining performance architecture

Work through these components in dependency order.

R10 — Native data pipeline

Eliminate unnecessary Python object materialization and expensive to_pylist() processing from performance-critical paths.

Use bounded Arrow/native buffers, streaming, caching, and efficient memory layouts.

Preserve exact decimal/tick precision, event order, timestamps, data identity, and restart equivalence.

Benchmark before and after.

R04 — TickFirstHitIndex

Implement the exact first-hit indexing design.

Prove its results are identical to authoritative sequential quote replay across edge cases, including spread, slippage, gaps, simultaneous conditions, and stop/target ordering.

Benchmark construction cost, memory overhead, cache reuse, and repeated-query speedup.

Use indexing only where exact equivalence is demonstrated and measurements justify it. Keep sequential Rust execution as the fallback.

R08 — Native Rust strategy generator

Implement the typed strategy grammar required by the owner directive, covering the nine approved strategy families.

Support parameter mutation, structural mutation, crossover, deterministic fingerprints, deduplication, novelty tracking, bounded batch evaluation, and shared caches.

Preserve existing Optuna capabilities where useful.

The generator must integrate with the real research workflow and produce reproducible, valid strategy specifications.

Do not build a second competing execution pipeline.

6. Finish historical data readiness

Inspect the actual persistent VPS dataset inventory first.

The previous audit reported 22 months across eight instruments, with November and December 2024 missing.

Determine the exact remaining gaps before downloading anything.

Acquire only genuinely missing data, using bounded, resumable operations.

Do not redownload verified existing partitions unnecessarily.

Verify:

* Source provenance.
* Timestamp ordering and session calendars.
* Bid/ask integrity.
* Tick sizes and instrument precision.
* Broker profiles and currency conversions.
* Missing periods and anomalous quotes.
* Raw-to-canonical consistency.
* Partition hashes and recovery.
* Source acceptance across the full approved 24-month window.

Preserve raw data and quarantine evidence.

Never classify structural import alone as source acceptance or mark DATA_READY before all requirements are demonstrated.

7. Complete the factory’s actual operational workflow

Finish the remaining scientific, dashboard, reliability, and autonomy requirements.

The final research workflow should support:

Historical data → native strategy generation → closed-bar signal compilation → exact Rust execution → independent validation → qualification → per-instrument ranking → retained research evidence → dashboard.

Requirements include:

* Strict 50% qualification, with 70% remaining an aspirational research target.
* Up to five genuinely qualified strategies per instrument.
* No fabricated candidates to fill empty leaderboard slots.
* Proper chronological training, out-of-sample testing, walk-forward evaluation, and protected holdouts.
* Duplicate detection and rejection evidence retention.
* Persistent research state and resumable work.
* Bounded CPU, RAM, disk, and model usage.
* Deterministic continuation when model APIs are unavailable.
* Complete dashboard visibility and truthful status reporting.
* Recovery, restart, failure injection, security checks, and reproducible installation.

This system is for historical and paper research. Do not add live order placement or broker execution.

8. Repair the project management files

NEXT_ACTION.md currently contains outdated instructions that describe already completed tasks as not implemented.

implementation-queue.json also has stale task states, including the Rust execution task.

Correct these problems.

Make the active next action unambiguous, while retaining historical milestone records separately.

Synchronize:

* NEXT_ACTION.md
* implementation-queue.json
* completion-ledger.json
* development-state.json
* Architecture and relevant runbooks

Do not delete historical evidence merely to simplify documentation.

Every requirement must remain accounted for.

Never mark a requirement PASS solely because some supporting tests exist. Verify every clause of its acceptance criteria.

If AGENTS.md conflicts with the latest approved owner directive, reconcile it where authorized; otherwise record the exact permission blocker without ignoring the governing directive.

9. Mandatory continuous execution loop

You are authorized to continue independently within the existing approved repository scope.

DO NOT STOP after completing one task.

Repeat this loop:

1. Read the latest owner directive, NEXT_ACTION.md, implementation queue, completion ledger, and development state.
2. Inspect the actual repository, branch, current HEAD, and latest CI status.
3. Identify the highest-priority unfinished requirement or dependency.
4. Implement the smallest meaningful complete milestone.
5. Run focused tests.
6. Run broader regression, parity, build, formatting, and security checks as appropriate.
7. Fix failures before claiming success.
8. Update evidence, acceptance status, benchmarks, and documentation truthfully.
9. Commit the tested changes.
10. Push to build/initial-factory.
11. Verify the exact remote commit SHA and associated CI results.
12. Update NEXT_ACTION.md with the next unfinished task.
13. RE-READ NEXT_ACTION.md AFTER THE UPDATE.
14. Continue immediately to the next unfinished task.

Repeat until all requirements are genuinely complete or an actual external blocker or session/tool limit prevents further work.

Do not end a response or execution cycle merely because a milestone was committed.

Do not repeatedly re-audit already accepted requirements while major unimplemented features remain.

Prioritize completing engineering work over increasing the PASS count.

If an external blocker exists, document it precisely, complete other independent tasks, and continue.

If the session or tool budget is exhausted, leave a tested, pushed checkpoint and an exact, executable next action. Do not claim work will continue outside an active execution mechanism.

10. Rules you must follow

* Preserve existing working functionality and source evidence.
* Do not rebuild the project from scratch.
* Do not make unsupported performance or accuracy claims.
* Do not weaken risk, spread, slippage, validation, or data-quality requirements to make tests pass.
* Do not fabricate benchmarks, historical results, or acceptance evidence.
* Do not silently delete failing tests.
* Do not commit credentials or secrets.
* Do not merge PR #1, create a release, or deploy production changes without explicit authorization.
* Do not mark software, data, or operations ready prematurely.
* Preserve the existing repository, branch, and approved architecture.
* Keep the implementation lean, fast, resource-efficient, and maintainable.
* Prefer existing proven components and verified optimizations rather than unnecessary complexity.

11. Completion conditions

You may declare the project fully complete only when:

1. All 79 requirements pass their full acceptance criteria.
2. The primary Rust execution path is integrated and independently verified.
3. The native generator and data pipeline operate correctly.
4. Indexed execution meets exactness requirements, with a sequential fallback.
5. The required historical dataset has passed source acceptance.
6. Scientific qualification and leaderboards work end to end.
7. The dashboard and resumable autonomous research workflow function correctly.
8. Target hardware benchmarks and required recovery/soak tests pass.
9. All required GitHub CI checks pass on the final exact SHA.
10. SOFTWARE_VERIFIED, DATA_READY, and OPERATION_READY can truthfully be set to TRUE.

Start now. Inspect the latest HEAD, correct the 50% gate, and continue directly into the Rust execution migration and performance work. Keep looping through NEXT_ACTION.md until the complete factory satisfies its requirements.