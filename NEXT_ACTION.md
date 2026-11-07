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

## Historical data acquisition (owner-authorized, in progress)

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

1. Authenticated dashboard workflow for v2 (eligible calibration/prospective
   inputs, freeze, actual native feedback, exact export), desktop and mobile.
2. Screening comparability and selection safeguards (frozen comparability
   contracts across cohorts; explicit selection-bias reporting).
3. Worker-native prospective diagnostics for cohorts frozen before this
   increment, if any are retained.

Then continue the dependency-aware queue: recursive session/regime/MFE/MAE
diagnostics, global independent qualification, source/profile/refresh/storage/data
APIs, full dashboard, installed provenance/Ubuntu/systemd/update/rollback/backup/
restore, security remediation and full source-to-restore/release/Hermes handoff.
Do not stop at one milestone or repeat expensive campaigns merely to increase
counts.

## Publication blocker

This host has **no GitHub credentials** (no `gh`, no SSH keys, no tokens) and no
GitHub connector is attached to the Hermes profile. Read access to the public
repository works; **push requires owner-supplied repository-scoped credentials**.
Do not paste tokens into chat or logs. Until credentials exist, commits stay local
and no remote SHA/CI claim is made.

## Environment and evidence constraints

Run focused tests for changes, then `bash scripts/verify.sh` when warranted.
API/full pytest can hang inside sandbox networking; run those checks outside it.
Keep scientific source unchanged during provenance-bound runs.

fsspec 2026.2.0 exact Nautilus pin and compatible deepmerge advisories remain
release-blocking; audits stay active. Do not force incompatible pins or suppress
failures. Native finite-empty-book fallback remains quarantined, not waived.

Preserve local credentials, failed attempts, raw/canonical/source vault bytes,
receipts and hashes; never blindly git-clean or delete evidence. Earlier genuine
EURUSD archives are absent from this checkout; prior versioned genuine receipts
are retained but restoration is not reverified. Jan/Feb prior technical use cannot
be relabeled wholly untouched final holdout.

If a real session/tool limit intervenes, leave a clean tested pushed checkpoint
and exact next action here, in the ledger and development state. Do not promise
execution after the session without an execution mechanism. Resume the loop from
the highest-priority unfinished requirement, rather than rebuilding prior work.
