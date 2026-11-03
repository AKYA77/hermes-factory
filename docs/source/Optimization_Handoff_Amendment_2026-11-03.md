## Hermes Factory — Final Optimization and Handoff Amendment

Continue working on the existing `AKYA77/hermes-factory` repository and `build/initial-factory` branch.

The original Hermes Factory v2.0 blueprint and completion directive remain authoritative, except for the following approved clarification regarding full historical-data acquisition.

**Important change: You do NOT need to download the entire 2025–2026 historical dataset before completing the software and preparing the handoff.**

Hermes Agent will perform the bulk historical-data download, verification and catalog preparation on the Contabo VPS after receiving the tested software.

Your responsibility is to finish and thoroughly verify the complete software system.

### 1. Historical data and testing requirements

- Preserve the existing real-data importer, source provenance, exact integer quote storage and Parquet/ZSTD pipeline.
- Use the real January 2025 data already imported for all eight instruments as a starting point.
- Obtain only additional representative real-data periods when necessary to verify cross-period ingestion, event processing, simulation and validation.
- Use carefully designed synthetic multi-month and multi-quarter fixtures for complete chronological, walk-forward, restart, gap-handling and source-revision tests.
- Verify that the importer can resume, retry, repair, validate and incrementally extend historical catalogs without duplicating or corrupting records.
- Implement all necessary functionality for Hermes to download the complete 2025–2026 dataset autonomously on the VPS.
- Keep downloaded data outside Git.
- Do not manufacture broker metadata, Gold pip conventions or cross-currency conversion values.
- Do not mark full market-history coverage as complete until Hermes has actually verified those datasets.

Full dataset acquisition is now a **post-handoff data-readiness gate**, not a prerequisite for verifying the software implementation.

### 2. Fast screening and optimization

Implement a lightweight, bounded Tier 0 screening stage before expensive NautilusTrader replay.

- Benchmark NumPy/Numba against RaptorBT if appropriate.
- Use only the implementation that demonstrates measurable improvements and passes equivalence tests.
- Avoid installing multiple competing backtesting engines.
- Preserve NautilusTrader as the authoritative detailed simulation engine.
- Integrate the screener with persistent Optuna TPE and the existing experiment registry.
- Cache repeated evaluations and deduplicate candidates.
- Precompute and reuse indicators with identical data, timeframe, lookback and feature settings.
- Use bounded caches instead of precomputing every possible configuration.
- Benchmark Optuna study reconstruction. Change persistence only if there is a demonstrated bottleneck and deterministic restart behavior is preserved.
- Prevent the optimizer from promoting candidates solely because an approximate screener assigns a high score.
- Audit rejected candidates to measure whether the screener incorrectly discards promising strategies.

Do not implement unnecessary large genetic frameworks or distributed computing infrastructure.

### 3. Lossless performance improvements

- Keep canonical bid/ask prices as exact integers.
- Preserve every original quote, source order and timestamp-tie ordering.
- Benchmark supported lossless Parquet compression and integer encodings.
- Investigate column pruning, predicate pushdown, row-group selection and appropriate memory mapping.
- Keep bounded native streaming and compact forensic references.
- Preserve the existing source hashes, result hashes and immutable experiment identities.
- Never downsample real quote data or introduce float32 price storage to improve reported speed.
- Measure compressed size, read throughput, decode CPU, peak RSS and replay correctness together.

Do not replace the existing Parquet store with another TSDB unless there is substantial, independently reproduced evidence of better end-to-end performance and a clear maintenance benefit.

### 4. Execution accuracy and causality

- Strengthen event-ordering tests, especially for equal timestamps and tied source records.
- Prevent a strategy from acting on information that was not available at its decision point.
- Verify order submission and fill eligibility against the appropriate future event sequence.
- Support versioned latency assumptions only when their meaning and granularity are explicit; do not hardcode an arbitrary 50–200 ms latency and describe it as observed reality.
- Verify adverse stop fills, take-profit limit semantics, gaps, partial fills, cancellations and position accounting.
- Preserve the agreed pessimistic spread/slippage research scenario and intended fixed 1:3 stop/target ratio.
- Maintain independent financial reconciliation and deterministic regression tests.

### 5. Complete the remaining Factory functionality

Do not stop after the optimization work. Finish:

- Autonomous discovery across supported strategy families, instruments and timeframes.
- Strategy diagnostics, root-cause hypotheses and controlled automatic improvements.
- Complete strategy parent-child lineage and retained failed hypotheses.
- Parameter Stability Laboratory and paired comparative analysis.
- Independent OOS, three-month walk-forward, annual and pooled evaluation.
- Holdout protection, multiple-testing safeguards and validation status management.
- The complete visual dashboard, including diagnostic charts, research coverage, performance reports and full controls.
- Reproducible installation, authenticated operation, backups, restart recovery, updates and rollback.
- Controlled Hermes Agent integration and handoff documentation.

### 6. New release and handoff criteria

Separate the release states:

**SOFTWARE_VERIFIED:** All implementation-level acceptance tests pass on representative real data and controlled fixtures. All modules are integrated, documented and reproducible.

**DATA_READY:** The complete historical dataset has actually been downloaded, reconciled and verified on the target VPS.

**OPERATION_READY:** Target VPS installation, stress and recovery tests pass, full data are ready, and the historical research workflow has been validated under the approved scientific rules.

Do not misrepresent a partial installation as a fully operational system.

Codex may prepare the tested software handoff before DATA_READY, provided that all software verification requirements are satisfied and outstanding environmental or data-dependent gates are explicitly identified.

The original C0–C9 and T01–T30 requirements remain in force. Record which requirements are proven during software development and which require subsequent VPS/data acceptance. Do not silently waive them.

### 7. Final testing evidence

Before handoff, provide:

- Tested commit and immutable release candidate.
- Test matrix showing every mandatory requirement and its evidence.
- Genuine real-data end-to-end test results.
- Deterministic reference fixtures covering all execution rules.
- Crash, restart, resource-limit and restore tests.
- Actual benchmark results with CPU, memory and disk metrics.
- Unresolved security findings and their release disposition.
- Reproducible installation and verification instructions.
- Hermes Agent handoff and full historical-backfill instructions.
- Honest lists of passed, failed, blocked and untested requirements.

Do not claim the system is guaranteed bug-free, guarantee future market outcomes, or declare OPERATION_READY before its prerequisites are met.

**Main objective: Finish and verify the software architecture completely. Hermes will handle bulk historical-data acquisition on the VPS afterward.**

Preserve all correct existing work, continue from the latest branch, and prioritize functionality, correctness, reproducibility, efficiency and maintainability over unsupported throughput claims.

The system remains restricted to historical research and paper simulation.