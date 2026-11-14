# ADR0034 — Admission-bound posthoc historical training diagnostics

Typed historical-shadow-diagnostics/v1 requests bind an existing officially
completed native experiment, exact reviewed profile, actor and no-pruning
attestation. The CLI historical-shadow produces a separate content-addressed
artifact without changing the native artifact, experiment, fills or scoring.

Current code/profile, actual canonical bytes, active reviewed admission, protected
holdouts and recorded evaluation influence are checked before feature access and
again at final publication under the database write lock. Shared causal features
and the existing fixed cost-label policy supply descriptive training estimates.
Native/estimate hashes and immutable started/completed audit events retain lineage.
Repeated identical requests preserve evidence and do not count as new native runs.

This is posthoc diagnostics, not prospective independent calibration or permission
to prune. Historical cohort v2, worker-integrated prospective diagnostics and the
API/dashboard workflow remain open. Existing generated cohort v1 is unchanged.
The TEST_ONLY reviewed-input fixtures are authorization software tests, never
historical data/reference acceptance. No financial or validation rule changed.
