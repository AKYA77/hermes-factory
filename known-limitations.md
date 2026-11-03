# Known limitations — NOT_READY

No requirement below is waived. Current code is a partial development checkpoint.
Passing local tests is not completion of T01–T30 or gates A–M.

## External prerequisites

- Owner confirmed Factory.pdf is the original v2.0 blueprint referred to by the
  Markdown filename. It is preserved verbatim; consult it for extracted typography.
- GitHub private visibility, push and API access are now verified; branch protection
  and production release gates remain unverified. See campaign-report.json for latest tests.
- Dukascopy's offered route requires AWS Requester Pays; owner requires free sources.
  Free HistData web tick downloads now work. January 2025 archives for all eight
  instruments have exact bounded structural imports (21,345,746 quotes). No billed access is used.
- Whole-source empirical price grids are verified, but Gold monetary pip/tick/
  contract/margin/volume conventions remain UNKNOWN_SPEC. Provider calendar gaps,
  all-eight-instrument and 2025/2026 coverage and independent evidence are unfinished.
- No Contabo access or target Ubuntu/8GB installation, reboot, stress or soak test.
- Hosted Nous/Hermes credentials/model catalog/quotas unavailable and integration
  not installed. No model calls are required by the current deterministic queue.

## Incomplete product implementation

- C0 is partial: private repository is verified. Branch-protection API returns HTTP
  403 for the configured integration, so branch rules remain unverified. Comparative
  real-strategy engine/security release gates remain open.
- C1 partial: typed defaults/API/queue/UI available. Production least-privilege
  installation, complete schema evolution and service lifecycle are not implemented.
  Additive migration 002 now preserves immutable search/outcome/attempt-resource history.
- C2 partial: free HistData ASCII ticks now have a bounded download/parser and
  8,192-row Parquet import/readback path; original ZIP bytes/notices/checksums,
  fixed EST -> UTC, millisecond precision and exact integer prices are retained.
  All-eight January 2025 imports pass structural checks; 176 planned 2025/2026
  provider-month partitions remain pending. Calendar gap classification,
  source correction reconciliation, operational quotas, compaction/backfill,
  independent-source comparison and full period coverage remain pending.
- C3 partial: order-aware v2 accounting tracks partial fills, order/trade IDs,
  cancellation races, protection-loss safety closes and deadline quote availability.
  Diagnostics use actual stop order identity and per-fill/quote entry bases.
  Source/version guards reject stale execution contexts; default boards separate v1/v2.
  Nautilus StandardMarginModel now matches profile-rate arithmetic. Finite-liquidity
  L1 GTC fallback can add one tick; exact-price mismatches are reported and blocked
  by the worker rather than relabeled correct. Full broker constraints, account-currency
  rounding/reference agreement, JPY conversion and verified Gold monetary profiles
  remain release gates. Native position/fill/inventory/cash conservation checks
  now run; native rounded USD vs exact Decimal residuals remain explicit
  DIFFERENCE_REQUIRES_POLICY. Real historical strategy evaluation stays blocked until
  those profiles, calendar checks and evaluation contracts are approved.
- C4 partial: 3 initial operators, typed proposals, seeded Optuna proposal adapter,
  proposal-count coverage allocation, hash keys, bounded RAM cache. No complete
  eight-family search, full time/CPU-budget fairness or L2 disk cache. Persistent
  training-only TPE feedback and recurring registered-region admission now exist;
  screened-out false-negative audit and automatic new-source/region discovery
  remain unfinished. Confirmation interpreter now uses bounded bars and monotonic publication alignment. Native
  delivery/compact forensic paths are bounded; full-period strategy/VPS throughput
  remains unverified. Replay currently accepts one source partition, not an annual
  composite; multi-month views and source-mapped large artifacts remain required.
  Result/spool limits fail explicitly instead of truncating research.
- C5 partial: MFE/MAE and several measured failure tags, bounded children and basic
  lineage exist. Full cohort/regime analysis, cost sensitivity, paired comparisons,
  controlled auto-improvement, and paired negative hypothesis decisions remain unfinished.
  Failed strategies and returned engine-contract traces are now preserved in the
  registry/quarantine; full mid-engine crash forensics still need implementation.
- C6 partial: Wilson intervals, quarter split helper, purge helper, frozen train/OOS
  replay exist. No full annual reset/pooled/marked-equity/regime reports, deflated
  Sharpe/multiple-testing evaluation, final holdout-use workflow, WFO refitting,
  sensitivity gates or automated validation promotion. All validated boards empty.
  The first 200,000 January EURUSD quotes were used for a feature-compilation
  benchmark; do not retrospectively claim that interval wholly untouched.
- C7 partial: responsive authenticated API inspector reads real state and executes
  pause/resume; no full forensic charts, improvement workshop, exports/PDF, performance
  panels, supervisor console or complete typed action surface. No browser E2E run.
- C8 partial: actual small synthetic benchmark, backup-copy rehearsal, lease recovery,
  auth/payload/rate-limit tests and pointer rollback harness. Real-source feed-only
  probes (no orders) now exist; no historical strategy benchmark,
  forced-8GB soak, full coordinator/reboot/disk-full recovery, full release
  migration rollback, signed provenance, backup retention/encryption/off-host restore
  or security release review. Prior GitHub Python/dashboard CI passed; security
  CI fails. Exact current-head CI results must be checked independently.
- C9 blocked: no verified release/tag. Install script is development-only; update and
  rollback refuse production deployment explicitly. This is not a production installer.
- Paper-forward collection/discrepancy measurement is not implemented.

## Latest completion-directive increment

The complete owner directive is preserved in docs/source/Completion_Directive_2026-11-03.md.
See docs/completion-backlog.md and docs/decisions/0008-bounded-replay-and-causal-features.md.
Production quote/signal reads and native delivery now stream; transient spools and
result records fail explicitly at resource budgets. Compact path summaries retain
canonical reconstruction references; this does not complete a forced-8GB soak,
large-artifact API, L2 feature cache or all source/currency gates.

## Earlier correctness and historical-import increments

See milestone-report.json and docs/milestone-execution-and-data.md for the current
v2 increment. v1 campaign reports remain historical development evidence and are
not automatically rerun or ranked as v2. Security findings are assessed in ADR 0007;
both audit gates remain active/failing. No C0–C9 milestone is declared fully complete.
The latest registered-region training probe, controls and supervision evidence are
in docs/milestone-training-research.md; this is not complete C4/C8 autonomy.

## Earlier software campaign

See campaign-report.json and docs/campaign-1000.md. Two 1,000-strategy synthetic
campaigns exercise the implemented four USD-quoted Forex pairs, three operators,
M1/M5, and fixed pessimistic execution. These do not establish historical or VPS
readiness. Earlier 2,000-quote benchmark evidence predates the already-triggered
stop correction; it is retained as historical development evidence, not current
execution-correctness proof. Stop feasibility and read-only backup verification
bugs were reproduced and corrected; no claim is made that all blueprint work is done.

## Evidence interpretation

The small benchmark uses 2,000 synthetic minute-spaced quote records, not 2025/2026
historical ticks. OS page cache was not flushed. Worker RSS was sampled every 10ms;
shorter peaks may be missed. Two trials do not establish a speedup or steady-state
throughput. Raw reports are local ignored artifacts, with sanitized summaries kept
in the checkpoint report. Third-party deprecation warnings are retained.


## Final amendment checkpoint

Full acquisition is now a post-software-handoff DATA_READY task, not a software
implementation blocker. Software, data and operation readiness remain false.
Flat immutable multi-partition views and exact disk closed-bar reuse are now
implemented; shared indicator transforms, richer screening/audit cohorts, automatic region
expansion/improvement, full independent validation, full dashboard and deployment
still require work. Existing unresolved security/monetary-profile/target gates
are unchanged. See ADR 0011 and docs/completion-backlog.md.

Exact-zero-signal Tier 0 now runs in persistent research and recovery, with
immutable receipts, PRUNED feedback and native rejection audits. It does not
perform approximate profitability screening or confer scientific validation.
