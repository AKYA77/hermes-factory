# Continuous completion loop — NOT_READY

Continue `/opt/hermes-factory`, branch `build/initial-factory`, PR #1:
https://github.com/AKYA77/hermes-factory/pull/1. The owner authorizes each tested
milestone commit/push and exact-SHA PR/CI verification. No merge, repository
visibility change, production deployment, release tag or readiness claim.

Read AGENTS.md, the complete authority/blueprint and latest owner directive:
`docs/source/Continuous_Autonomous_Completion_Loop.md`. Then inspect Git HEAD/tree,
completion-ledger.json, development-state.json, implementation-queue.json and run:
`.venv/bin/python scripts/completion-queue.py`. Continue without asking what to do.
Scoped task verification never implies its parent gates pass. Final reconciliation
explicitly maps every one of the 67 requirements; none may disappear behind a
scoped checkpoint. SOFTWARE_VERIFIED/DATA_READY/OPERATION_READY remain false.

## Environment change observed this session

The prior checkpoint recorded histdata.com/oanda.com/six-group.com as proxy-denied
(CONNECT 403). On this host those providers now return HTTP 200 and the free
HistData ASCII tick form is reachable for every month 2025-01 through 2026-10
(2026-11 is the current partial month and has no issued token). The historical
source path is therefore **open**, not blocked. Verify actual reachability again
before assuming either state; do not bypass a proxy or dump secrets.

The project virtualenv was absent on this host. It was rebuilt from the committed
lockfile with `uv venv --python 3.12` + `uv sync --frozen` (Python 3.12.3). The
host runs 3.14 and has no system pip/ensurepip; use `.venv/bin/python`.

## Latest tested source

Recorded in completion-ledger.json `latest_verified_source` and
development-state.json `last_verification`. Full-suite and focused results are
updated at each tested checkpoint. Do not use prior CI as proof for a later commit.

## Completed this continuation

**Source-to-restore rehearsal added over genuine data.**
`scripts/source_to_restore_rehearsal.py` runs the stages exercisable on this
host against the real acquired catalog in one chain: verify (deep
`Catalog.verify`), feature_cache (closed M5 bars), native_replay (full tick
stream with a monotonicity check), rank, and backup_restore (backup plus the
restore rehearsal). Measured over a genuine 2,032,079-tick partition: 6,333 M5
bars, 24,405 files backed up, 13 migrations re-applied, 129 catalog partitions
re-verified after restore, 345.6 s wall, 1.48 GB peak RSS. The receipt lists the
nine stages it did **not** run — import, admit, catalog, generate, screen,
diagnose, improve, independent_evaluation, dashboard — and never claims them.

**All six dashboard browser-acceptance smokes pass.** `scripts/run-browser-smoke.sh`
starts the dashboard **and** a coordinator against one isolated TEST_ONLY state,
waits for the API, runs a smoke in real Chromium, and tears both down. All six
pass with zero page errors and no mobile overflow: discovery, historical screen
cohort, reviewed inputs, screen cohort, screen fallback and validation. Eight
harness defects were found and fixed first — five smokes pointed at a nonexistent
`/usr/bin/chromium`; `serve` started no coordinator so job-driven workflows never
completed; the historical smoke polled at 250 ms against a 120 req/60 s limiter and
always tripped 429; the discovery smoke used an ambiguous page-global
`Authorized by` locator; the reviewed-inputs fixture accepted `--state` but
hardcoded its path; its smoke hardcoded both the state path and URL; its
revocation step inherited an ambient `PYTHONPATH` that broke `pydantic_core`; and
the wrapper pre-created a state directory some fixtures require to be absent. See
`docs/browser-acceptance-findings.md`. All runs use generated TEST_ONLY fixtures,
not market data.

**Research reports panel fixed; seventh browser smoke added.** The panel rendered
and its controls worked, but **all three report actions returned 422** — each
endpoint pins its own attestation literal while the panel sent one generic string,
so every click surfaced only as an alert. Measured in real Chromium before the fix:
`Error: 422 ... Input should be 'Report a descriptive global candidate-selection
funnel only; ...'`. The panel now sends the matching attestation per action. The new
`research-reports-browser-smoke.cjs` asserts the actions are attestation-gated, all
three reports render, the funnel counts match the API, and the receipt records that
these are descriptive aggregates which do not qualify, rank or promote a strategy.
The Screen comparability panel's attestation was verified to already match its
endpoint. The existing source-quality smoke expects eight real historical scans
against a state directory absent on this host, so it cannot run here.

**`refresh` no longer reports a consistent catalog as inconsistent.** `factory.cli
refresh` re-verifies every partition's parquet digest against its manifest. It
reported `consistent: false` with three partitions "missing" — they were composed
views (`data/view-v1`), which by design have no `quotes.parquet` of their own.
`refresh` treated every manifest as a leaf. It now verifies a view through its
leaves and still reports a view with no parts or with a missing/mismatched leaf.
Real catalog: `verified: 134`, `mismatched: []`, `missing: []`, `consistent: true`.
See `docs/source-quality-findings.md` section 5.

**Source-to-restore rehearsal: all thirteen stages run over genuine acquired data.**
`scripts/source_to_restore_rehearsal.py` runs verify, catalog, admit, feature_cache,
generate, screen, native_replay, diagnose, independent_evaluation, improve, rank,
dashboard and backup_restore in one chain. Against the **real acquired catalog**
with a fresh scratch state root: **13 stages run, 0 blocked**, 318.4 s wall, 1.30 GB
peak RSS. The catalog stage composes 4 AUDUSD partitions into one 7,456,481-row
ordered view. Five genuine coverage gaps were closed, each found by measuring rather
than assuming: profile units (`price_scale=1000000`, not the fixture's `1000`),
timestamp precision (millisecond, not whole-second), calendar coverage (a declared
FX session replacing the 24/7 fixture), instrument identity (single-instrument
sample with the strategy instrument and `strategy_hash` recomputed), and
**idempotency** — `independent_evaluation` recorded an
`evaluation-with-past-only-warmup` use for the sampled window, which discovery then
treated as an excluded interval, so a second run failed its own diagnose stage; the
rehearsal now refuses a state root it would pollute. Only the **import** stage
remains unrun, blocked on the quarantine correction policy. See
`docs/source-quality-findings.md` section 4.

**T03 process-kill recovery tested against a real kill.** T03 recorded
"process-kill recovery pending". `test_T03_fenced_restart` rewound `lease_until`
by hand and `test_supervision` covered the kernel parent-death binding, so
neither killed a real process and then exercised recovery.
`tests/recovery/test_process_kill_recovery.py` now starts a holder process that
claims a job on a short lease, SIGKILLs it mid-job, waits for the lease to lapse
and verifies the next claim expires the lease, re-claims the same job and
records `LEASE_EXPIRED`. A second test asserts a claim while the recovered lease
is live returns `None`, so recovery cannot duplicate live work. Note the actual
design: **the lease does not self-transition on expiry** — expiry is evaluated
by the next claim, which is how a coordinator crash presents itself.

**Restore rehearsal added.** T22 records "migration/live process recovery
pending" and T23 records "full source/state/board production rehearsal pending".
`restore-test` only verified an isolated copy, so `factory.operations.rehearse_restore`
now restores a verified backup into a fresh root, opens the store read-write so
every migration applies, then reads every partition back out of the restored
catalog with `Catalog.verify`. It refuses a workdir that already exists or sits
inside the backup, cleans up after itself, and never touches the backup or any
live state root. Wired as `restore-rehearsal` with a
`scripts/restore-rehearsal.sh` wrapper; receipt `restore-rehearsal/v1`. Scope is
an isolated development rehearsal over a fixture state root, not a production
recovery claim — a production rehearsal over a genuine state root with stopped
services remains separate work.

**Staging budget is now operator-sized.** Nine partitions were blocked with
`staging payload budget exceeded` even after `reclaim-staging` cleared published
staging. Two causes were measured: published staging (reclaimable, 2.1 GB → under
200 MB) and retained prefixes for partitions that cannot succeed — `reclaim_all`
deliberately touches only published checkpoints, so 43 quarantined partitions
keep the partial prefixes they decoded (193 staging dirs, 1.8 GB, five largest
105–142 MB). That is resumability working as designed, not a leak, but it consumes
the budget. `scripts/acquire_history.py` now exposes
`--staging-budget-bytes` and forwards it to each import; the supervisor runs with
17179869184 (16 GiB) on this host, which has 75 GB free. The guard still bounds
growth and relaxes no data-quality check. `tests/integration/test_acquire_history.py`
pins the passthrough.

**T24 enforced soak (ADR0048 extended).** `scripts/enforced_soak.py` runs the
bounded synthetic soak inside a `systemd-run --scope` with `MemoryMax=8G`,
`CPUQuota=400%` and `MemorySwapMax=0`, and records the cgroup values the kernel
actually applied rather than the requested ones. Measured on this host:
`cpu_max 400000 100000` (4.0 CPUs), `memory_max 8589934592` (exactly 8 GiB),
`swap_max 0`. Run: 8 iterations x 50,000 rows, peak sampled RSS 559,689,728 bytes,
`within_limits` true, `oom_detected` false, `uncontrolled_swap` false, report
archived at `reports/soak/enforced-soak-report.json`. `factory/operations/soak.py`
now takes a `rows` parameter so the workload is sized explicitly. Scope is
unchanged: synthetic fixture only, not VPS equivalence, not historical validation
and not market validation.

**Two distinct source defects, not one.** `docs/source-quality-findings.md` now
records both. (a) 2025-10 duplicates a whole hour: the sequence reaches
`2025-10-27T00:59:58Z` then restarts at `00:00:00Z`, in three instruments at the
same UTC instant. (b) Many other months contain single ticks one second out of
order at a second boundary — measured in AUDUSD 2026-09 (row 120,721),
EURUSD 2026-08 (row 757) and XAUUSD 2026-07 (row 5,402). Both trip the same
monotonicity gate. 38 partitions across 11 months are quarantined. The gate was
not relaxed, no row was reordered and no timestamp was nudged.

**Budget lock restored to the documented fail-fast guard.** The previous
increment replaced the non-blocking payload-budget lock with a waiting lock.
`NEXT_ACTION.md` and the skill both record that lock as a deliberate fail-fast
guard, not a bug: concurrent imports must fail rather than queue so the budget
problem is visible immediately. It is reverted, the supervisor runs with a
single worker, and `tests/integration/test_import_resume.py` now pins the
fail-fast behaviour deterministically instead of asserting the reverted behaviour.

**C0 branch rules — measured, not applied.** `docs/branch-protection.md` records
that the repository is PUBLIC while C0 requires an authorized private repository,
that neither branch has protection, and the exact `gh api` call that would
require the four current CI jobs on `main`. Repository governance settings are
outside the standing authorization, so the configuration is left to the owner.

ADR0035 historical prospective calibration cohorts v2:
`historical-calibration-policy/v1` immutable typed policy bound to reviewed
admission, exact profile/dataset/code/training coverage and a literal no-pruning
flag; `historical-screen-cohort/v2` freeze/report; calibration members must carry
a retained ADR0034 posthoc diagnostic whose artifact/body hashes are reverified
against immutable audit events; prospective members must be unattempted queued
jobs under an approved-policy admission with a 24h post-calibration embargo,
subject equality, global effective-experiment dedup, canonical/quarantine/holdout/
training-scope and active-admission rechecks; deterministic pre-outcome selection;
fenced completion produces the historical diagnostic natively without mutating the
native artifact. CLI `historical-screen-cohort-freeze`, authenticated API
`POST /api/v1/research/historical-screen-cohorts`. Generated-only v1 is unchanged
and rejects a v2 request. Approximate historical pruning stays disabled and the
known profitable native counterexample/all-native fallback are preserved.

See docs/milestone-historical-screen-cohorts.md and ADR0035.

ADR0036 adds frozen screening comparability and selection-bias reporting:
`screen-comparability/v1` re-verifies cohort bodies, compares the frozen subject
contract pairwise with the exact differing fields, reports selection-bias
counters (distinct effective experiments, selected, observed,
selected-but-unobserved, unselected, selection ratio) and is content-addressed
and immutable. `pooled_claim_authorized` is always false; comparability never
authorizes pooling screening observations into a qualification, ranking or
performance claim. CLI `screen-comparability`, authenticated API
`POST /api/v1/research/screen-comparability` and a dashboard comparability panel.

Authenticated dashboard workflow for v2 is implemented and browser-verified:
`HistoricalScreenCohortsPanel.svelte` derives the immutable policy from the
selected calibration evidence, blocks incompatible selections and embargo
violations before submit, freezes, shows actual native feedback and exports the
exact cohort evidence. Playwright Chromium acceptance at 1280x900 and 390x844
froze before outcomes, preserved pause, observed 1 fenced native feedback,
disabled approximate pruning, exported byte-exact evidence, and reported no
mobile overflow or page errors.

## Historical data acquisition (owner-authorized, in progress)

`scripts/acquisition_watchdog.py` is a deterministic `no_agent` Hermes cron job
(`085932ae4c7b`, hourly, deliver origin) that prints only when the backfill needs
attention — supervisor not running, blocked partitions, low disk reserve, a
stalled completion count, or completion. Empty stdout means healthy, so the
scheduler stays silent. The scheduler copy lives at
`~/.hermes/scripts/acquisition_watchdog.py`; keep it in sync with the repository
copy when the watchdog changes. The watchdog does not import the scientific
stack, so it keeps running when the model or network is unavailable.

`scripts/acquire_history.py` is a bounded, checkpointed, resumable driver around
the existing `factory.operations.import_history` CLI. It never imports, parses or
scores data itself. It runs **sequentially by design**: `factory/data/resume.py`
takes a catalog-wide non-blocking payload-budget lock, so concurrent imports fail
fast rather than queue. Do not "fix" that lock to gain speed; it is a deliberate
budget guard.

State is on the protected persistent volume, not in the checkout:
`/var/lib/hermes-factory/{archives,catalog,backfill}`. Raw provider archives,
canonical Parquet/ZSTD datasets, receipts and checkpoint are retained. Progress is
in `/var/lib/hermes-factory/backfill/supervisor.log` and `checkpoint.json`.
Structural import is not calendar/source acceptance or DATA_READY.

## Exact next implementation

Remain in `safe_screening` (IMPLEMENTING). Historical cohort v2 policy, freeze,
report, CLI, API and fenced-completion diagnostics are implemented and tested.
Remaining in this task:

1. Worker-native prospective diagnostics for cohorts frozen before this
   increment, if any are retained.

`recursive_diagnostics` is now substantially complete (ADR0037 descriptive cohort
aggregation, ADR0038 parameter sensitivity, ADR0039 candidate diversity, ADR0040
market volatility regimes, ADR0041 improvement lineage, ADR0042 independent
confirmation of improvements). Remaining there: controlled recursive child
generation is provided by `improvement/v1`; global regime/source validation stays
open under `scientific_selection`.

Then continue the dependency-aware queue: `scientific_selection` has begun
(ADR0043 multiple-testing safeguards, ADR0044 diversity-aware qualified
shortlist, ADR0045 annual and pooled reporting, ADR0046 global selection funnel,
(ADR0047 typed comparability contracts), T24 has a bounded synthetic soak
(ADR0048), and `scientific_selection` now has qualified ranking over independent
evaluations (ADR0049), data source/storage/refresh APIs (ADR0050) and instrument
profile registry/integrity (ADR0051) and a research reports dashboard panel
(ADR0052), state restore and rollback planning (ADR0053), and an
installed-operations doctor report (ADR0054), and a restrictive security header
policy (ADR0055), and release manifest verification coverage (ADR0056).
Remaining: full source-to-restore/release/Hermes handoff —
`docs/runbooks/hermes-handoff.md` now records the environment facts, verified
state, hazards and continuation loop, and is linked from `docs/operator-guide.md`.
T02 has begun: the bar/indicator cache identity now covers code and fill version
(ADR0057), T11 has begun with calendar gap classification (ADR0058), and T03 has
begun with completion idempotency after worker restart (ADR0059), and T14 has
begun with retained rejected candidates (ADR0060), and T05 has begun with a
source coverage report (ADR0061), and T08 has begun with adverse fill coverage
for entry and exit (ADR0062), and T09 has begun with order semantics coverage
(ADR0063), and T16 has begun with board cap, independence and retention
coverage (ADR0064), and T18 has begun with search fairness across protocols
(ADR0065), and T17 has begun with duplicate-skip accounting coverage (ADR0066),
and T12 has begun with MFE/MAE path coverage (ADR0067), and T13 has begun with
failed-child lineage preservation (ADR0068), and T15 has begun with purge/embargo
fold geometry (ADR0069). Do not stop at one milestone or repeat expensive
campaigns merely to increase counts.

## Publication blocker — RESOLVED

GitHub write access is now available: `gh` is authenticated as `AKYA77` with the
`repo` and `workflow` scopes, and pushes to `build/initial-factory` succeed.
Earlier checkpoints recorded the host as having no GitHub credentials; that is
no longer true. Never paste tokens into chat or logs — the credential lives in
`/root/.config/gh/hosts.yml`.

## Environment and evidence constraints

Run focused tests for changes, then `bash scripts/verify.sh` when warranted.
**Always run project Python as `env -u PYTHONPATH .venv/bin/...`.** The shell
exports `PYTHONPATH` pointing at Hermes's Python 3.14 site-packages, which
shadows the 3.12 venv and breaks `import pydantic_core` with
`ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'`.
**Never commit while pytest is running**: `execution_revision()` binds to git HEAD
and the scientific source hash, so a mid-run commit invalidates every contract's
`code_revision` and produces spurious `require_execution_version` failures. Wait
for the suite to finish, then commit.
API/full pytest can hang inside sandbox networking; run those checks outside it.
Keep scientific source unchanged during provenance-bound runs.

fsspec 2026.2.0 exact Nautilus pin and compatible deepmerge advisories are now
dispositioned with measured reachability evidence in
`docs/security-advisories-2026-11-07.md`; reachability and pin regression tests
live in `tests/security/test_dependency_advisories.py`. Neither sink is
reachable in this system and no compatible fix exists, so no pin was overridden
and no auditing was disabled. Re-run those tests on every Nautilus or dashboard
dependency upgrade.

Preserve local credentials, failed attempts, raw/canonical/source vault bytes,
receipts and hashes; never blindly git-clean or delete evidence. Earlier genuine
EURUSD archives are absent from this checkout; prior versioned genuine receipts
are retained but restoration is not reverified. Jan/Feb prior technical use cannot
be relabeled wholly untouched final holdout.

If a real session/tool limit intervenes, leave a clean tested pushed checkpoint
and exact next action here, in the ledger and development state. Do not promise
execution after the session without an execution mechanism. Resume the loop from
the highest-priority unfinished requirement, rather than rebuilding prior work.
