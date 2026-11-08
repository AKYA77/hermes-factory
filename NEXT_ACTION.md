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
coverage (ADR0064). Do not stop at one milestone or repeat expensive campaigns
merely to increase counts.

## Publication blocker

This host has **no GitHub credentials** (no `gh`, no SSH keys, no tokens) and no
GitHub connector is attached to the Hermes profile. Read access to the public
repository works; **push requires owner-supplied repository-scoped credentials**.
Do not paste tokens into chat or logs. Until credentials exist, commits stay local
and no remote SHA/CI claim is made.

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
