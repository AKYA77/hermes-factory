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
