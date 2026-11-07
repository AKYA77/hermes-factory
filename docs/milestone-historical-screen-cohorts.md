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

Full verification at this checkpoint: 570 passed / 0 failed / 0 skipped
(566 baseline + 4 new), ruff check/format clean, svelte-check 0 errors and
0 warnings, vite build OK. Exact receipts:
[manifest.json](../reports/milestones/historical-screen-cohorts/manifest.json).

These are generated TEST_ONLY authorization fixtures. They exercise the
historical admission branch and are **not** genuine market validation, broker
execution or independent strategy qualification.

## Remaining

Worker-native prospective diagnostics for cohorts frozen before this increment,
API/dashboard graphical workflow for v2, screening comparability and
selection-bias safeguards, and the full source-to-restore historical gate.
All three readiness flags stay false; no merge, visibility change or production
deployment occurred.
