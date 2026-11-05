# Known limitations — NOT_READY

No requirement below is waived. Current code is a partial development checkpoint.
Passing local tests is not completion of T01–T30 or gates A–M.

## External prerequisites

- Owner confirmed Factory.pdf is the original v2.0 blueprint referred to by the
  Markdown filename. It is preserved verbatim; consult it for extracted typography.
- GitHub currently reports PUBLIC visibility (owner decision pending); push and API
  access are verified. Earlier private-visibility reports are superseded. Branch protection
  and production release gates remain unverified. See campaign-report.json for latest tests.
- Dukascopy's offered route requires AWS Requester Pays; owner requires free sources.
  Free HistData web tick downloads now work. January 2025 archives for all eight
  instruments plus February EURUSD have bounded structural imports
  (23,399,003 quotes). No billed access is used.
- Whole-source empirical price grids are verified, but Gold monetary pip/tick/
  contract/margin/volume conventions remain UNKNOWN_SPEC. Provider calendar gaps,
  all-eight-instrument and 2025/2026 coverage and independent evidence are unfinished.
- No Contabo access or target Ubuntu/8GB installation, reboot, stress or soak test.
- Hosted Nous/Hermes credentials/model catalog/quotas unavailable and integration
  not installed. No model calls are required by the current deterministic queue.

## Incomplete product implementation

- C0 is partial: repository is currently public, contrary to the blueprint; owner
  visibility decision is pending. Branch-protection API previously returned HTTP
  403 for the configured integration, so branch rules remain unverified. Comparative
  real-strategy engine/security release gates remain open.
- C1 partial: typed defaults/API/queue/UI available. Production least-privilege
  installation, complete schema evolution and service lifecycle are not implemented.
  Additive migrations 002–004 preserve immutable search/resources and improvement
  policy/plan/edge/outcome history.
- C2 partial: free HistData ASCII ticks now have a bounded download/parser and
  8,192-row Parquet import/readback path; original ZIP bytes/notices/checksums,
  fixed EST -> UTC, millisecond precision and exact integer prices are retained.
  All-eight January 2025 plus February EURUSD imports pass structural checks;
  175 of184 planned provider-month partitions through November2026 remain.
  Captured declared calendars, lossless QA, reviewed-input eligibility and source
  version/selection/diff/quarantine/restoration software now exist. Legitimate
  reference review, automatic source workflows, intra-partition checkpoint resume,
  operational quotas/compaction, independent-source comparison and full coverage
  remain pending.
- C3 partial: order-aware v4 accounting tracks partial fills, order/trade IDs,
  cancellation races, protection-loss safety closes and deadline quote availability.
  Diagnostics use actual stop order identity and per-fill/quote entry bases.
  Source/version guards reject stale execution contexts; default boards distinguish legacy v1/v2/v3 from v4.
  Nautilus StandardMarginModel now matches profile-rate arithmetic. Finite-liquidity
  L1 GTC fallback can add one tick; v4 retains v3 explicit IOC for market remainders,
  retaining actual partials/cancellations and safety closes (ADR 0016). Full broker constraints, verified dated account-currency
  profiles and verified Gold monetary conventions
  remain release gates. Native position/fill/inventory/cash conservation checks
  now run. Native Money account/position paths now have independent tested
  references (ADRs 0017–0018); differences from exact research sums remain
  explicit. Ordered conversion context now fixes the stale protective-fill
  FX path in all-eight synthetic goldens, including ties/chunk boundaries.
  Profile lot volume maps to native base units once; synthetic Gold equivalence
  and exact-rational feasibility are tested. These are software fixture proofs,
  not verified broker conventions or historical strategy validation. Real historical strategy evaluation stays blocked until
  those profiles, calendar checks and evaluation contracts are approved.
- C4 partial: three initial operators, exact bounded RAM/disk bar caches,
  persistent training TPE, recurring registered regions and exact-zero Tier 0
  rejection/native audits are implemented. Flat immutable multi-partition inputs
  preserve leaf/source row references. Full blueprint families, automatic new-data/
  region discovery, shared indicator transforms and full-space fairness remain
  unfinished. A versioned opt-in cost-label shadow stage now records native
  disagreements; actual calibrated approximate pruning remains disabled. Spool/result caps fail explicitly; large-artifact
  APIs and actual target-host throughput are unverified.
- C5 partial: MFE/MAE, stop-role failure tags and bounded registered-region training
  improvement now run with durable plans, multiple-parent edges, paired complete-
  trade-set reports, CPU reservations and retained negative/inconclusive decisions.
  Full cohort/session/regime analysis, cost sensitivity, recursive/diversity-aware
  improvement and independent confirmation remain unfinished. Mid-engine crash
  forensics are incomplete; failed execution traces remain quarantined.
- C6 partial: protected one-time managed holdouts, chronological quarterly refits,
  v2 pre-confirmation qualification, native annual resets/pooled/cost/neighborhood
  reports and marked equity have scoped native software proof. Full historical
  admission propagation, global selection/multiple-testing/regime inference,
  complete comparability/validated boards and full protocol acceptance remain
  unfinished. Validated boards remain empty. The original first200,000January
  EURUSD quotes and now January/February technical feature rehearsal must not be
  retrospectively declared wholly untouched; scoped input-use evidence is retained.
- C7 partial: connected research/audit counts, bounded improvement controls,
  paired child evidence, cancellation and pause/resume are implemented. A real
  Chromium loopback rehearsal passed these controls and mobile overflow checks;
  it exposed and fixed a CSP bootstrap failure. Connected validation protocols, forward marked-equity curves, annual/pooled
  tables, protected states and exact-byte API exports now have real browser proof.
  Full forensic charts, cohort diagnostics, exports/PDF,
  supervisor console and all blueprint browser workflows remain unfinished.
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
large-artifact API or all source/currency gates. Exact disk bars and immutable
partition views were added afterward in ADR 0011.

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
expansion and recursive/regime-aware improvement, full independent validation, full dashboard and deployment
still require work. Existing unresolved security/monetary-profile/target gates
are unchanged. See ADR 0011 and docs/completion-backlog.md.

Exact-zero-signal Tier 0 now runs in persistent research and recovery, with
immutable receipts, PRUNED feedback and native rejection audits. It does not
perform approximate profitability screening or confer scientific validation.

Latest actual evidence: docs/milestone-monetary-validation-2026-11-04.md and
reports/milestones/2026-11-04-monetary-validation/manifest.json. Scientific protocol v2 now requires forward/training/neighborhood qualification
before final consumption and checks marked/native evidence (ADR 0019). Legacy v1
is read-only. Explicit synthetic software rehearsal can consume weak evidence
for integration testing but cannot certify. Full source completeness/calendar,
regime/global inference and historical profile gates remain open. Empty custom
books can cause native unadjusted-price fallback; such evidence is rejected,
not accepted as complete finite-depth fidelity. No historical promotion is enabled.

Real source-quality streaming has now been measured across all 21,345,746
existing January quotes, with actual connected browser checks. All eight remain
UNKNOWN_SPEC/UNKNOWN_CALENDAR and historical admission is false. Full calendar,
metadata approval, revisions and automated admission are unfinished; the QA
benchmark is not strategy performance or a target-VPS reliability benchmark.


Latest correctness increment: Decimal fingerprint encoding no longer rounds with
arithmetic context.42state/32,450retained typed-value comparisons were unchanged;
this does not recover any precision old software may have discarded. Existing
signed-zero semantics remain. Canonical decimal expansion is bounded before
formatting. Source bytes and existing results/IDs were not rewritten.

Cost labels are feature-only estimates, not orders/risk/equity simulations. A
supervised generated native counterexample shows a proxy reject can complete a
profitable3R target. Exact-zero pruning and native objectives stay authoritative;
actual cost-based pruning needs frozen calibration/ongoing audits/fallback and
selection-bias integration. Feature-only measured overhead is3.03–3.29×the old
cheap screen, so shadow mode is explicit opt-in. No speedup or tick throughput
is claimed. See ADRs0024/0025 and the latest milestone manifest.

## Admission-bound historical checkpoint, 4 November 2026

ADR0026 supersedes earlier synthetic-only search/validation limitations:
search/v4, protected-holdout/v2 and scientific-validation/v3 propagate approved
inputs and revocations. A complete generated positive chronological reference and
a bounded genuine EURUSD generic-unit native rehearsal now pass. Earlier claims
that no real-source strategy replay has ever run are historical, not current.
This does not certify broker profiles: the one-unit FX model/calendar is explicitly
a research assumption; Gold and provider gap/holiday fidelity remain unfinished.
Jan/Feb prior technical use excludes a final-unseen claim. Both replay windows
have censored positions and tiny native Money rounding; no historical promotion.
Global-selection/regime/diversified-ranking and all full C0–C9 exit gates remain.
Full verification346passed; actual measurements are in the milestone report.
Latest directive authorizes tested milestone pushes; historical push holds are
superseded. No merge, visibility change, ready tag or production deployment.

ADR0027 now implements retained-ZIP intra-partition import recovery. Earlier
statements that all intra-partition recovery is absent are superseded for this
specific path. HTTP range recovery remains unsupported; full downloads still
preserve failed bytes and reacquire. Staging adds disk use and intentionally
retains failure/orphan evidence pending explicit safe retention software. Parser
v2 fixes Decimal-context rounding on overprecise source prices; canonical values
alone cannot prove what a prior parser discarded. No old archive is rewritten or
retroactively certified. Scientific/operational/release gates remain unchanged.

ADR0028 supersedes the duplicate-staging-cleanup gap only: a catalog-wide payload
budget and explicit deeply verified chunk reclamation now exist. JSON audit
metadata is outside that payload quota. Canonical archive retention/compaction,
scheduled source refresh and full data APIs/UI remain unfinished. A new bounded
historical-profile run also needs provider/reference access: current proxy denies
HistData/OANDA/SIX. Additive domain requirements are saved as an unapplied draft.
The prior genuine raw archives were not restored in this fresh environment;
existing Git receipts are retained and are not a new local historical run.

ADR0029 supersedes the three-operator-only entry-framework limitation: explicit
Signal2 now supports trend/reversal/range/volatility/session/confluence with
Search5/scientific-validation4 propagation and generated native/causality tests.
Existing identities remain. This does not implement autonomous new-region
discovery, shared indicator transforms, full calibrated Tier0 or recursive cohort
improvement; new-family full historical qualification and graphical workflows
remain unfinished. SOFTWARE_VERIFIED stays false after463passing tests.
