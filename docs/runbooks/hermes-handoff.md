# Hermes handoff — build/initial-factory

Status: NOT_READY. Readiness flags `SOFTWARE_VERIFIED`, `DATA_READY` and
`OPERATION_READY` are all false. 63 of 67 completion requirements remain
unfinished. This runbook hands the next operator the facts needed to continue
without re-deriving them.

## Layout

- Checkout: `/opt/hermes-factory`, branch `build/initial-factory`, PR #1
  (`NOT_READY`). Inherited HEAD `c36c1f39c410847cff6d18c33ad45cf1f639b08a`.
- Persistent project state: `/var/lib/hermes-factory` (SQLite, catalog,
  artifacts).
- Acquisition checkpoint: `/var/lib/hermes-factory/backfill/checkpoint.json`.
- Live Hermes WebUI runs from a separate service on `127.0.0.1:8787`; leave it
  alone.

## Hard environment facts

- **No GitHub credentials on this host.** No `gh`, no SSH key, no token. Pushes
  fail with `could not read Username for 'https://github.com'`. Read access to
  the public repo works. Requirement C0 is FAIL for this reason. A
  repository-scoped SSH deploy key or a fine-grained token for
  `AKYA77/hermes-factory` is required — obtain it out of band, never paste it into
  chat.
- The shell exports `PYTHONPATH` pointing at Hermes's Python 3.14 site-packages,
  which shadows the project venv and breaks `import pydantic_core`. Always run
  project Python as `env -u PYTHONPATH .venv/bin/python ...` (same for pytest,
  ruff, uv).
- The project needs Python 3.12 (host default is 3.14, no pip). Build with
  `uv venv --python 3.12 .venv && uv sync --frozen`.
- Node is at `/root/.hermes/tools/node-26.7.0-linux-x64/bin` and
  `/root/.hermes/tools/npm-12.0.2-linux-x64/bin`; not on non-interactive PATH.
- HistData free tick downloads **are** reachable from this host. The mandate's
  proxy-403 premise is outdated.

## Commands

```
env -u PYTHONPATH .venv/bin/pytest -q                 # full suite
bash scripts/verify.sh                                # ruff + pytest + svelte + build
env -u PYTHONPATH .venv/bin/python scripts/completion-queue.py
env -u PYTHONPATH .venv/bin/python -m factory.cli --state /var/lib/hermes-factory doctor
```

Acquisition is driven by `scripts/acquire_history.py` with a supervisor log at
`/var/lib/hermes-factory/backfill/supervisor.log` and a checkpoint. A Hermes cron
job (`085932ae4c7b`, hourly, `no_agent`) runs `scripts/acquisition_watchdog.py`
and only prints when attention is needed.

## Verified state

- Full suite: **620 passed / 0 failed / 0 skipped**; ruff check and format clean;
  svelte-check 0 errors / 0 warnings; dashboard production build succeeds.
- Live state root: database `PRAGMA integrity_check` ok, 13 migrations, 32
  catalog partitions holding 92.4M rows and 1.2 GB at `SOURCE_BID_ASK` fidelity.
- Acquisition: 31 of 176 partitions, 15 GB of 82 GB free, watchdog active.
- ADRs 0001–0056 are committed under `docs/decisions/`; each increment's
  evidence is recorded in `docs/milestone-historical-screen-cohorts.md`.

## Hazards

- **Never commit while pytest is running.** `factory.provenance.execution_revision()`
  binds to git HEAD and the scientific source hash, so a mid-run commit
  invalidates every contract's `code_revision` and causes spurious
  `require_execution_version` failures. Wait for the suite, then commit.
- `tests/integration/test_search.py` pins the exact `schema_migrations` list.
  Every new `migrations/NNN_*.sql` must extend that expected list.
- Two tests are wall-time sensitive and flake under load:
  `test_supervision.py::test_bound_worker_dies_with_coordinator` and
  `test_search.py::test_recurring_feedback_restart_and_no_llm`. Re-run in
  isolation before treating a failure as real.
- Pause the acquisition with `process_manage(action='kill')`, not
  `pkill -f acquire_history` — pkill also matches the invoking shell and is
  blocked as destructive. Wait for the child `import_history` process to exit
  before running the suite.
- `store.rows()` returns a list of dicts, not tuples — index by column name.

## Continuation loop

1. Read `NEXT_ACTION.md` and `implementation-queue.json`.
2. Pick the next dependency-aware task; implement it in the smallest coherent
   unit with a typed request, content-addressed immutable artifact, audit event
   and an explicit attestation.
3. Add tests, run ruff, run the full suite to green.
4. Record the increment in `docs/milestone-historical-screen-cohorts.md` and
   `NEXT_ACTION.md`, then commit.
5. Do not stop at one milestone, and do not repeat expensive campaigns merely to
   increase counts.

## Standing constraints

- No merge, visibility change or production deployment.
- Readiness stays `NOT_READY`.
- All work is `TEST_ONLY` authorization fixtures; not market validation or
  `DATA_READY`.
- No auditing was disabled and no pin was overridden. Where an advisory has no
  compatible fix, the disposition is documented in
  `docs/security-advisories-2026-11-07.md`.
- Do not add an LLM-driven recurring engineering job; the acquisition watchdog is
  deterministic and sufficient.
