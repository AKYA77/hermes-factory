# Admission-bound historical shadow diagnostics — NOT_READY

ADR0034 adds a typed CLI request over an existing official native historical
training experiment. It checks the exact profile/code, native artifact, canonical
source bytes, active source/profile/calendar admission, protected reservations and
recorded evaluation influence before feature access and final publication. The
existing shared causal compiler and fixed estimator produce a separate immutable
hash-bound diagnostic artifact; native results and their hashes remain unchanged.
Started/completed audit events preserve authorization and lineage. Approximate
pruning remains forbidden; posthoc diagnostics are not prospective calibration.

Actual TEST_ONLY reviewed-input fixture checks exercise native replay, diagnostic
idempotency, unchanged native bytes, admission revocation, source/native corruption
and generated-profile rejection. These simulated external-source flags test the
trust boundary only; no genuine historical/provider/reference claim is made.

The complete historical screening task remains IMPLEMENTING: prospective cohort
v2 support, immutable worker policy binding and API/dashboard integration remain
missing. All subsequent diagnostics/science/source/lifecycle/security/release
requirements remain active. No readiness flag is promoted.

Actual verification: {"passed": 566, "warnings": 430, "pytest_seconds": 188.3, "failed": 0, "skipped": 0, "lint": "PASS", "format": "PASS", "frontend_check": "PASS", "frontend_build": "PASS", "log": "reports/milestones/historical-shadow/historical-shadow-full.log"}. Focused4passed/8warnings. Tested source: {"git_commit": "fabf4828893d59ea0f32a9c0d00dd07af3d967e1", "source_sha256": "115fe5e58823ac6ca6e3dca02b291efbde91d113b077554e834c8896c045aba9"}.
