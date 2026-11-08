# Historical prospective calibration cohorts — NOT_READY

Baseline remote: `c36c1f39c410847cff6d18c33ad45cf1f639b08a`.
ADR0035 defines the v2 boundary. This is a continuation of `safe_screening`;
the full historical and scientific acceptance remains open.

## Implemented

- `HistoricalCalibrationPolicy` (`historical-calibration-policy/v1`): immutable
  typed binding of reviewed admission, exact profile, canonical dataset, current
  code revision, calibration coverage window and a literal no-pruning flag.
- `HistoricalCohortRequest` (`historical-screen-cohort/v2`): calibration members
  must already carry a retained `historical-shadow` posthoc diagnostic
  (ADR0034); prospective members must be unattempted queued jobs.
- Freeze re-verifies diagnostic artifact/body hashes against the immutable
  `historical_shadow_completed` audit events, the diagnostic experiment binding,
  profile/dataset/code/admission identity, `approximate_pruning_authorized is
  False`, and the native artifact hash.
- Prospective safeguards: approved-policy admission identity, single
  `train_only` window at least 24h after calibration coverage, subject equality,
  no prior outcome, no prior prospective membership, global effective-experiment
  dedup, canonical source verification, quarantine rejection, protected-holdout
  and evaluation-window exclusion, and active reviewed admission.
- Deterministic hash-seeded pre-outcome selection; repeated identical requests
  retrieve the same immutable cohort.
- Fenced completion produces the historical diagnostic natively for selected
  members. The native artifact is never mutated; the diagnostic is a separate
  content-addressed artifact with its own hash and audit lineage, and it
  rechecks admission, quarantine, holdout, source and code scope before feature
  access and again at publication.
- v1 remains generated-only and rejects a v2 request; the generic report route
  dispatches on `schema_version`.
- CLI `historical-screen-cohort-freeze`; authenticated API
  `POST /api/v1/research/historical-screen-cohorts`.
- ADR0036 screening comparability and selection-bias reporting:
  `screen-comparability/v1` re-verifies cohort bodies, compares the frozen
  subject contract pairwise with exact differing fields, reports
  selection-bias counters (distinct effective experiments, selected, observed,
  selected-but-unobserved, unselected), and is content-addressed and immutable.
  `pooled_claim_authorized` is always false. CLI `screen-comparability`,
  authenticated API `POST /api/v1/research/screen-comparability` and a
  dashboard comparability panel.
- ADR0037 descriptive diagnostic cohort aggregation: session/side/stop-class/
  failure-pattern/excursion/hold-duration/drawdown-recovery cohorts from one
  retained verified training-only result, content-addressed and immutable, with
  declared UTC hour buckets (not a broker calendar) and cost sensitivity
  explicitly not measured. CLI `diagnose-cohorts` and authenticated API
  `POST /api/v1/research/diagnostic-cohorts`.
- ADR0038 parameter sensitivity for controlled improvements:
  `improvement-sensitivity/v1` groups retained parent-child outcomes by the exact
  changed-field set with outcome counts and mean/min/max equity deltas, plus
  hypothesis counts. Content-addressed and immutable; descriptive only and never
  independently validated. CLI `improvement-sensitivity` and authenticated API
  `POST /api/v1/research/improvement-sensitivity`.
- ADR0039 diversity-aware candidate reporting: `candidate-diversity/v1` reports
  trial outcomes, distinct parameter sets and the largest single-set share with a
  concentration flag, operator/timeframe distributions and per-field coverage
  buckets. Content-addressed and immutable; descriptive only and never feeds the
  optimizer. CLI `candidate-diversity` and authenticated API
  `POST /api/v1/research/candidate-diversity`.
- ADR0040 market volatility regime cohorts: canonical M1 midpoints over the
  experiment's own admitted window produce a trailing 60-minute realized
  volatility classifier mapped to LOW / NORMAL / HIGH by window percentiles.
  Regimes are relative to the reviewed window, never broker-calendar
  classifications; a missing dataset yields null rather than an invented label.
  ADR0040 documents the thresholds and safeguards.
- ADR0041 improvement lineage: `improvement-lineage/v1` reconstructs the retained
  parent-to-child tree for one improvement policy with plans, distinct parents,
  children, changed fields, hypotheses, parameter summaries and outcome statuses.
  Content-addressed and immutable; every child is explicitly training-only and a
  `TRAIN_IMPROVED_ONLY` child is not independently validated. CLI
  `improvement-lineage` and authenticated API
  `POST /api/v1/research/improvement-lineage`.
- ADR0042 independent confirmation of training improvements:
  `improvement-confirmation/v1` binds a `TRAIN_IMPROVED_ONLY` edge to a retained
  independent evaluation, refusing self-evaluation, overlapping windows or a
  different canonical dataset. `qualification_authorized` is always false.
  CLI `improvement-confirmation` and authenticated API
  `POST /api/v1/research/improvement-confirmation`.
- ADR0043 multiple-testing safeguards: `multiple-testing/v1` reports uncorrected,
  Bonferroni and Benjamini-Hochberg pass counts for a supplied candidate family,
  with the corrected threshold. Content-addressed and immutable;
  `qualification_authorized` is always false. CLI `multiple-testing` and
  authenticated API `POST /api/v1/research/multiple-testing`.
- ADR0044 diversity-aware qualified shortlist: `qualified-ranking/v1` applies a
  greedy `(operator, timeframe)` diversity guard over the tier-ranked candidate
  list, reporting DIVERSITY_LIMIT and SLOT_LIMIT exclusions plus per-key counts.
  Content-addressed and immutable; `qualification_authorized` is always false.
  CLI `qualified-ranking` and authenticated API
  `POST /api/v1/research/qualified-ranking`.
- ADR0045 annual and pooled evaluation reporting:
  `annual-pooled-reporting/v1` aggregates retained independent evaluations by
  UTC window-start year and pooled, with evaluation, window, trade, win/loss,
  win-rate and ending-equity counts. Content-addressed and immutable;
  `qualification_authorized` is always false. CLI `annual-reporting` and
  authenticated API `POST /api/v1/research/annual-reporting`.
- ADR0046 global candidate-selection funnel: `selection-funnel/v1` reports search
  trials, distinct trial configurations, distinct effective cohort candidates,
  candidates selected for native audit, selected-and-observed counts, training
  promotions and a `funnel_complete` flag. Content-addressed and immutable;
  `qualification_authorized` is always false. CLI `selection-funnel` and
  authenticated API `POST /api/v1/research/selection-funnel`.
- ADR0047 typed comparability contracts: `comparability-contract/v1` registers a
  typed assertion of which peer context hashes an evaluation window is comparable
  with, plus protected windows it must never enter. Stored in migration
  `013_comparability_contracts.sql` (immutable by trigger) and retained under
  `artifacts/comparability-contracts/`; `qualification_authorized` is always false.
  CLI `comparability-contract` and authenticated API
  `POST /api/v1/research/comparability-contract`.
- ADR0048 bounded synthetic soak: `factory/operations/soak.py` repeats a bounded
  synthetic generation-plus-replay cycle, sampling RSS and swap against
  `max_rss_bytes` (default 8 GiB) and `max_wall_seconds`, archiving peak RSS, peak
  swap, `within_limits`, `oom_detected` and `uncontrolled_swap`. Scope is
  `NOT VPS / NOT HISTORICAL / NOT MARKET VALIDATION`. CLI `soak`.
- ADR0049 qualified ranking over independent evaluations:
  `independent-qualified-ranking/v1` joins retained evaluation results to their
  experiments, excludes synthetic evaluations, ranks by ending equity and applies
  the same `(operator, timeframe)` diversity guard. Content-addressed and
  immutable; `qualification_authorized` is always false. CLI
  `independent-ranking` and authenticated API
  `POST /api/v1/research/independent-ranking`.
- ADR0050 data source registry, storage inventory and refresh:
  `factory/data/sources.py` lists committed partitions as sources, reports
  per-instrument storage totals, and re-verifies every partition parquet digest
  against its manifest on refresh without mutating catalog data. API
  `GET /api/v1/sources`, `GET /api/v1/sources/{identity}`, `GET
  `GET /api/v1/storage`, `POST /api/v1/refresh`; CLI `sources`, `storage`, `refresh`.
- ADR0051 instrument profile registry and integrity:
  `factory/instruments/registry.py` lists every known symbol with version,
  synthetic flag, source, sizes, currencies, volume bounds, margin rate and a
  content hash, plus a drift-checking integrity report. API `GET
  /api/v1/profiles`, `GET /api/v1/profiles/{symbol}`, `GET
  `/api/v1/profile-integrity`; CLI `profiles`, `profile-integrity`.
- ADR0052 research reports dashboard panel:
  `apps/dashboard/src/lib/ResearchReportsPanel.svelte` surfaces the selection
  funnel, annual/pooled reporting, independent qualified ranking, storage
  inventory, instrument profiles and committed data sources under the Research
  view. Every report action requires a named authorizer and the descriptive-use
  attestation; buttons stay disabled until both are supplied. svelte-check
  reports 0 errors and 0 warnings and the production build succeeds.
- ADR0053 state restore and rollback planning:
  `factory/operations.restore` verifies a backup and copies it into a target that
  must not exist and must sit outside the backup, then re-verifies the copy.
  `rollback_plan` returns a plan with `applied: false` and refuses unless
  services-stopped and previous-release-verified are both affirmed. CLI actions
  `restore` and `rollback-plan`; `scripts/restore.sh` and
  `scripts/rollback-plan.sh`. `scripts/rollback.sh` remains a refusal stub
  because no production release exists yet.
- ADR0054 installed-operations doctor report: `factory.cli doctor` now reports host
  inventory, Python-against-3.12 and resolved Node version, database presence,
  `PRAGMA integrity_check`, job/experiment counts and highest schema migration,
  catalog partition/row/byte totals, source fidelity labels, and the standing
  `operation_ready: false`. Read-only; still exits 1 as a pre-flight report.
  Observed here: Python 3.12.3, Node v26.7.0, 6 CPUs, 12.5 GB RAM, 87 GB free,
  integrity ok with 13 migrations, 32 catalog partitions holding 92.4M rows and
  1.2 GB at `SOURCE_BID_ASK` fidelity.

## Preserved

- Approximate historical pruning stays disabled; the v1 shortlist keeps all
  candidates for native work except the existing exact-zero rule.
- The known profitable native counterexample and the all-native fallback remain.
- Generated-only v1 cohort identities, membership immutability and restrictions
  are unchanged.

## Evidence

Focused acceptance: `tests/integration/test_historical_cohorts.py` —
4 passed / 0 failed, covering freeze-before-outcomes, v1 preservation,
embargo/admission/duplicate rejection, reviewed-admission revocation, and
fenced-completion diagnostic production.

Full verification at this checkpoint: 571 passed / 0 failed / 0 skipped
(566 baseline + 5 new), ruff check/format clean, svelte-check 0 errors and
0 warnings, vite build OK. Exact receipts:
[manifest.json](../reports/milestones/historical-screen-cohorts/manifest.json).

## Authenticated browser acceptance

`scripts/historical-screen-cohort-browser-fixture.py` builds a fresh paused
TEST_ONLY reviewed-admission fixture and `scripts/historical-screen-cohort-browser-smoke.cjs`
drives the real dashboard and API in Chromium at 1280x900 and 390x844. Observed:
authenticated session, cohort frozen before any prospective outcome, pause
preserved, actual fenced native feedback (1 selected observation), approximate
pruning disabled, byte-exact export matching the API response, no mobile
overflow and zero page errors. Receipts:
`reports/runtime/completion/historical-cohort-{desktop,mobile}.png` and
`historical-cohort-browser-export.json`.

These are generated TEST_ONLY authorization fixtures. They exercise the
historical admission branch and are **not** genuine market validation, broker
execution or independent strategy qualification.

## Remaining

Worker-native prospective diagnostics for cohorts frozen before this increment,
API/dashboard graphical workflow for v2, screening comparability and
selection-bias safeguards, and the full source-to-restore historical gate.
All three readiness flags stay false; no merge, visibility change or production
deployment occurred.
