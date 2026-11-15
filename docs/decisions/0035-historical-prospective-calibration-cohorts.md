# ADR0035 — Historical prospective calibration cohorts (v2)

Status: implemented v2 software scope; full historical/scientific acceptance open.

ADR0033 fixed generated-only v1 cohorts. v1 deliberately refuses historical
calibration. This ADR adds an explicit second version that supports historical
prospective calibration under reviewed admission, without relaxing any v1
identity or restriction and without authorizing approximate pruning.

## Immutable typed policy

`HistoricalCalibrationPolicy` (`historical-calibration-policy/v1`) binds:

- `admission_id` — the reviewed input admission identity;
- `profile_hash`, `dataset_hash` — exact reviewed profile and canonical dataset;
- `code_revision` — must equal the current execution revision at freeze;
- `training_start_ns`, `training_end_ns` — calibration coverage bounds;
- `no_pruning` — literal `true`; a request without it is rejected.

The policy is part of the frozen request hash. It cannot be changed after
freezing without creating a different cohort.

## Calibration membership

Calibration members must be retained native experiments that already carry a
`historical-shadow` posthoc diagnostic (ADR0034). Freeze re-verifies, for every
calibration member:

- the diagnostic artifact hash and body hash against the immutable
  `historical_shadow_completed` audit event;
- the diagnostic's experiment binding, profile, dataset, code revision and
  admission identity against the policy;
- `approximate_pruning_authorized is False`;
- the native artifact hash against the retained experiment row;
- a single `train_only` window inside the policy coverage bounds.

Calibration is descriptive posthoc evidence. It is never relabeled independent
evaluation, OOS or strategy qualification.

## Prospective membership

Prospective members must be unattempted queued research jobs, frozen before any
native outcome exists. Freeze enforces the v1 safeguards plus the historical
ones:

- exact reviewed profile, dataset, code revision and admission identity;
- `historical-approved/v1|v2` evaluation policy whose admission identity matches
  the policy;
- a single `train_only` window starting at least 24h after the calibration
  coverage ends, covering the estimator's maximum label elapsed time;
- subject equality with the calibration set (instrument, operator, timeframe,
  confirmations, scenario, code, cost-label policy);
- no prior native outcome, no prior prospective cohort membership, and global
  effective-experiment dedup excluding seed-only copies;
- canonical source verification, source quarantine rejection, protected-holdout
  and evaluation-window exclusion checks, and active reviewed admission.

Selection is a deterministic hash-seeded sample fixed before outcomes. Repeated
identical requests retrieve the same immutable cohort.

## Worker and fenced completion

Fenced completion of a selected historical cohort member produces the
`historical-shadow` diagnostic natively. The native artifact is never mutated;
the diagnostic is a separate content-addressed artifact with its own hash and
immutable started/completed audit lineage. The diagnostic rechecks reviewed
admission, quarantine, protected holdout, source and code scope before feature
access and again at publication. A blocked diagnostic is recorded as an
immutable audit event and never reinterprets the consumed native evaluation.

## Reporting

The v2 report exposes the frozen frame, selected count, observed diagnostics,
rejected count, false negatives, a descriptive Wilson interval, known
counterexamples and the persistent no-pruning disposition. The generic cohort
report route dispatches on `schema_version`, so v1 and v2 bodies remain
distinguishable and v1 code paths are unchanged.

Approximate historical pruning stays disabled. The known profitable native
counterexample and the all-native fallback are preserved. No fill, risk, cost,
score, canonical data or validation criterion changes.

Evidence: docs/milestone-historical-screen-cohorts.md.
