# ADR0032 — Persistent native screen disagreement fallback

Status: implemented software increment; full screening acceptance remains open.

A failed exact-zero native audit previously quarantined one job while later
candidates could still be pruned. Persist a fail-closed circuit breaker before
raising that failure. Its first incident binds the exact experiment, source
revision and retained failure artifact hash in an immutable audit event. Existing
controls store disablement across process restarts; corrupt state also disables
pruning. There is no automatic reset or public re-enable operation.

New workers bypass exact-zero pruning and use authoritative native replay after
disablement. Optional cost-shadow labels remain unauthorized to prune, and still
reach native audit recording. Unknown screening policies remain rejected. No
signal, fill, risk, cost, scoring, canonical data or scientific threshold changes.

Maintenance, while unpaused, admits linked native rechecks of earlier completed
no-signal rejections. Every original job/receipt/outcome remains byte-identical.
A distinct idempotency key and original-job/incident references preserve lineage;
existing native results are reused through exclusion rather than new independent
claims. Worker admission, source integrity, authorization, code revision and
holdout protection remain mandatory. Old-code contracts are not rewritten or
reauthorized. Quarantined false-negative jobs themselves remain quarantined.

Recovery policy native-recheck-budget/v1 admits at most64jobs over the persisted
state and stops new admission after300measured CPU seconds. Admission uses the
ordinary queue capacity, at most2new jobs/cycle; bounded in-flight work may finish.
This is not a kernel CPU cap or automatic approval to expand an old grant. Counts,
all retry CPU and budget stop state are exposed with breaker status in the API
and graphical Research panel. Pausing never silently resumes or resets budgets.

The old approximate-profitable native counterexample remains a mandatory test.
Frozen calibration and independently sampled rejection cohorts, their selection
safeguards, broader resource acceptance and full scientific screening qualification
remain unfinished. Approximate cost-label rejection is still forbidden. See
 docs/milestone-screen-fallback.md for exact generated/native/browser evidence.
