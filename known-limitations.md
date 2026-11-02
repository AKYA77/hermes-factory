# Known limitations — NOT_READY

No requirement below is waived. Current code is a partial development checkpoint.
Passing local tests is not completion of T01–T30 or gates A–M.

## External prerequisites

- Named Markdown blueprint is absent. Factory.pdf is preserved verbatim; text
  extraction garbles some formulas. BLUEPRINT.md is an explicit source index.
- GitHub Git read works; metadata API returns Forbidden. Existing remote is
  AKYA77/hermes-factory. Privacy, write rights, branch rules, PR and CI unverified.
  No duplicate repository created and no remote push performed before privacy check.
- Proposed provider terms page and datafeed HEAD returned proxy 403. Network draft
  adds api.github.com, www.dukascopy.com, datafeed.dukascopy.com; saving did not apply.
- Provider market-data usage approval, actual latest 2026 ticks, source limits and
  verified Gold conventions/contract/margin/volume profiles are missing.
- No Contabo access or target Ubuntu/8GB installation, reboot, stress or soak test.
- Hosted Nous/Hermes credentials/model catalog/quotas unavailable and integration
  not installed. No model calls are required by the current deterministic queue.

## Incomplete product implementation

- C0 is partial: no private/branch-rule confirmation; no comparative real-data
  engine benchmark; dependency security remediations still tracked in audit reports.
- C1 partial: typed defaults/API/queue/UI available. Production least-privilege
  installation, complete schema evolution and service lifecycle are not implemented.
- C2 partial: synthetic canonical storage only. No permanent provider importer,
  incremental reconciliation, calendars/gap detection, tick-grid/session/DST checks,
  lossless full-year streaming, atomic compaction, storage quotas or backfill.
  Current commit/replay loads one test partition into memory; do not use it on full
  year ticks. Manifests are filesystem artifacts, not the full required SQL registry.
- C3 partial: market/bracket/stop/limit/timeout fixtures run in Nautilus. Production
  instrument conversion, partial fills/liquidity restrictions, ambiguous OHLC paths,
  full event traces and complete engine/reference agreement remain unverified.
  Only unit and synthetic USD-quoted integration profiles are supported. A missing
  deadline quote can produce a later engine fill flagged DELAYED_TIMEOUT_QUOTE;
  such results cannot count as validated precise-24h evidence.
- C4 partial: 3 initial operators, typed proposals, seeded Optuna proposal adapter,
  proposal-count coverage allocation, hash keys, bounded RAM cache. No complete
  eight-family search, time/CPU-budget fairness, L2 disk cache, persisted optimizer,
  screened-out false-negative audit or automatic discovery pipeline. Confirmation
  interpreter currently scans higher bars; production throughput needs profiling.
- C5 partial: MFE/MAE and several measured failure tags, bounded children and basic
  lineage exist. Full cohort/regime analysis, cost sensitivity, paired comparisons,
  controlled auto-improvement, and negative hypothesis decisions remain unfinished.
- C6 partial: Wilson intervals, quarter split helper, purge helper, frozen train/OOS
  replay exist. No full annual reset/pooled/marked-equity/regime reports, deflated
  Sharpe/multiple-testing evaluation, final holdout-use workflow, WFO refitting,
  sensitivity gates or automated validation promotion. All validated boards empty.
- C7 partial: responsive authenticated API inspector reads real state and executes
  pause/resume; no full forensic charts, improvement workshop, exports/PDF, performance
  panels, supervisor console or complete typed action surface. No browser E2E run.
- C8 partial: actual small synthetic benchmark, backup-copy rehearsal, lease recovery,
  auth/payload/rate-limit tests and pointer rollback harness. No real-data benchmarks,
  forced-8GB soak, actual worker SIGKILL/reboot/disk-full recovery, full release
  migration rollback, signed provenance, backup retention/encryption/off-host restore
  or security release review. CI definitions exist; GitHub CI has not run.
- C9 blocked: no verified release/tag. Install script is development-only; update and
  rollback refuse production deployment explicitly. This is not a production installer.
- Paper-forward collection/discrepancy measurement is not implemented.

## Evidence interpretation

The small benchmark uses 2,000 synthetic minute-spaced quote records, not 2025/2026
historical ticks. OS page cache was not flushed. Worker RSS was sampled every 10ms;
shorter peaks may be missed. Two trials do not establish a speedup or steady-state
throughput. Raw reports are local ignored artifacts, with sanitized summaries kept
in the checkpoint report. Third-party deprecation warnings are retained.
