# Persistent training optimization and recurring coordinator

Status: development increment; NOT_READY. No OOS/holdout/real-profile gate waived.

The old template helper no longer creates an unmeasured Optuna study or marks
unevaluated suggestions PRUNED. It is explicitly a seeded template proposer.
Actual optimization is Search/SearchProtocol with Optuna 4.5.0 TPE, 8 startup
observations, fixed bounded/categorical distributions and training-net-return/v1.
Objective = float((exact realized hypothetical ending equity - 20)/20), derived
only from a verified training worker artifact. It is exploratory optimization,
not an independently validated metric or a change to leaderboard ranking rules.
Open trades remain censored, native currency-rounding differences remain visible.

Additive migration 002 records immutable protocols, parameter trials, outcomes
and per-attempt measured resources. The existing registry remains the coordinated
SQLite writer; Optuna has no competing SQLite storage. Each ask reconstructs a
bounded in-memory study from ordered persisted history and a deterministic
protocol-seed/trial-number seed. Same history yields the same proposal after
restart. Running/failed/pruned/duplicate trials remain present. This costs O(number
of trials) per ask and is capped at 256 trials/protocol; persistent journal storage
is unnecessary for this bounded serialized workload. No new dependencies.

Only explicit registered synthetic-training regions are supported in this version.
Nontraining roles, real datasets/profiles, unsupported currencies, obsolete source,
source/profile mismatches and out-of-range windows fail closed. An immutable code
revision change requires a new protocol, not silently rebasing old queued jobs.
Future historical approval and complete window-influence/holdout protocols remain
separate mandatory work. Registration does not resume a paused installation.

The recurring coordinator collects feedback, recovers persisted proposals after
ask/enqueue interruption, admits bounded new candidates and runs one isolated heavy
worker. It continues without a model/network. Selection uses measured worker CPU
plus proposal CPU, first by instrument and then cell; count tie-breaks retain breadth.
Explicitly registered regions only; full eight-instrument coverage, screen/reject
sampling, family/region expansion and controlled child/OOS loops are unfinished.
Soft CPU budgets are checked between jobs: one job may overshoot; this is not a
hard per-study CPU quota or a multi-day fairness/soak acceptance result.

Duplicate specs within a protocol are retained as PRUNED/EXACT_DUPLICATE_SPEC,
not independent outcomes. Existing exact jobs/results are reused and consume no
new replay CPU. Feedback verifies contract, artifact checksum/canonical content,
source label and execution integrity. Failed experiments are not forgotten; no
API accepts supplied objectives or official metric values. No automatic VALIDATED
promotion exists. Artifact corruption blocks feedback and emits an audit alert.

The coordinator has a process lock, fenced heartbeat/completion, sampled worker
RSS limit and external timeout. Linux parent-death binding kills a supervised
worker when the coordinator dies. Cgroup-aware conservative admission considers
host availability and current cgroup allowance; kernel systemd memory limits remain
a template until installed/tested. RSS sampling is not a hard RSS guarantee.
Cancel fences jobs immediately; running workers are checked every 0.5s. Actual
kernel kill and lease/restart tests supplement, not replace, target reboot/soak.

CLI/API registration, status, paginated protocol/trial history, disable and cancel
are connected to the actual registry with operator/viewer permissions. The full
C7 dashboard, retry workflow and automatic improvement remain incomplete.
