# Hermes handoff — build/initial-factory

Status: NOT_READY. Readiness flags `SOFTWARE_VERIFIED`, `DATA_READY` and
`OPERATION_READY` are all false. **52 of 79 completion requirements PASS, 27
NOT_TESTED.** This runbook hands the next operator the facts needed to continue
without re-deriving them.

## Layout

- Checkout: `/opt/hermes-factory`, branch `build/initial-factory`, PR #1
  (`NOT_READY`). Handoff written at HEAD `f9ceb19`; always re-check with
  `git log --oneline -1` before acting.
- Persistent project state: `/var/lib/hermes-factory` (SQLite, catalog,
  artifacts).
- Acquisition checkpoint: `/var/lib/hermes-factory/backfill/checkpoint.json`.
- Live Hermes WebUI runs from a separate service on `127.0.0.1:8787`; leave it
  alone.

## Hard environment facts

- **GitHub write access WORKS.** `gh` is authenticated as `AKYA77` (OAuth device
  flow; scopes `repo`, `read:org`, `gist`, `workflow`), credentials in
  `/root/.config/gh/hosts.yml`. Pushes to `build/initial-factory` succeed. An
  earlier revision of this runbook claimed there were no credentials — that is
  obsolete. Never paste tokens into chat or logs.
- The shell exports `PYTHONPATH` pointing at Hermes's Python 3.14 site-packages,
  which shadows the project venv and breaks `import pydantic_core`. Always run
  project Python as `env -u PYTHONPATH .venv/bin/python ...` (same for pytest,
  ruff, uv).
- The project needs Python 3.12 (host default is 3.14, no pip). Build with
  `uv venv --python 3.12 .venv && uv sync --frozen`.
- Node is at `/root/.hermes/tools/node-26.7.0-linux-x64/bin` and
  `/root/.hermes/tools/npm-12.0.2-linux-x64/bin`; not on non-interactive PATH.
- Rust 1.100.0 is installed via rustup; `$HOME/.cargo/bin` is off the default
  PATH. The engine builds from `rust/raptor-engine`.
- HistData free tick downloads **are** reachable from this host. The mandate's
  proxy-403 premise is outdated.
- **The target 4-vCPU / 8-GiB envelope CANNOT be enforced here.** cgroup v2
  controllers are not delegated: `/sys/fs/cgroup/cpu.max` is absent at the root
  and `systemd-run --scope -p CPUQuota=400% -p MemoryMax=8G` yields a scope
  reporting `CPUQuotaPerSecUSec=infinity` and `MemoryMax=infinity`. Verify with
  `systemctl show <scope> -p CPUQuotaPerSecUSec -p MemoryMax`. Do not report
  unrestricted-capacity measurements as target-envelope results, and do not mark
  R11/T31/T35 from them.

## Commands

```
env -u PYTHONPATH .venv/bin/pytest -q                 # full suite
bash scripts/verify.sh                                # ruff + pytest + svelte + build
env -u PYTHONPATH .venv/bin/python scripts/completion-queue.py
env -u PYTHONPATH .venv/bin/python -m factory.cli --state /var/lib/hermes-factory doctor
```

Engine parity (run after any execution change):

```
env -u PYTHONPATH .venv/bin/python scripts/parity_raptor_engine.py --cases 200 --instrument all --seed 20261112
env -u PYTHONPATH .venv/bin/python scripts/parity_raptor_engine.py --cases 300 --instrument all --seed 4242
env -u PYTHONPATH .venv/bin/python scripts/parity_raptor_equity.py --cases 80 --seed 4242 --instrument EURUSD
env -u PYTHONPATH .venv/bin/python scripts/verify_raptor_goldens.py
env -u PYTHONPATH .venv/bin/python scripts/verify_goldens_without_nautilus.py
```

Acquisition is driven by `scripts/acquire_history.py` with a supervisor log at
`/var/lib/hermes-factory/backfill/supervisor.log` and a checkpoint.

## Verified state at handoff

- Ledger: **52 PASS / 27 NOT_TESTED** of 79. All three readiness gates false.
- Rust execution parity: goldens **240/240**, direct parity 200/200 (seed
  20261112) and 300/300 (seed 4242), restart/batch 120/120, genuine partitions
  7/7, and realized-equity parity 80/80 via `scripts/parity_raptor_equity.py`.
- New artifacts this cycle: `scripts/benchmark_raptor_vs_reference.py` +
  `reports/raptor-vs-reference-benchmark.json` (no computed speedup ratio,
  synthetic-only, envelope labelled not enforced); peak RSS per case via
  `/usr/bin/time -v`. `scripts/benchmark_compression_cache.py` +
  `reports/compression-cache-benchmark.json` (ZSTD levels 1/3/6/9).
- R07 win-rate gate is absolute: `min_win_rate` is bounded `ge=0.5, le=1`.
- Catalog on disk is ~12 GB under `/var/lib/hermes-factory/catalog` (sharded
  parquet). Re-run `factory.cli refresh` for authoritative row counts rather than
  trusting this number.
- ADRs are committed under `docs/decisions/`; each increment's evidence is
  recorded in `NEXT_ACTION.md`.

## Hazards

- **Never commit while pytest is running.** `factory.provenance.execution_revision()`
  binds to git HEAD and the scientific source hash, so a mid-run commit
  invalidates every contract's `code_revision` and causes spurious
  `require_execution_version` failures. Wait for the suite, then commit.
- **Never call the Python reference directly with hand-built arguments.**
  `replay()` takes the finite-book configuration through the keyword-only
  `fill_model`; passing the request dict positionally as `conservative` silently
  drops it and manufactures a convincing false divergence. Always go through
  `scripts/parity_raptor_engine.py`'s `generate_case`/`build_request` pair.
- **Adding fields to the Rust result breaks the frozen goldens** -- the verifier
  hashes the whole JSON. Put reporting-only data behind `--emit-equity` with
  `skip_serializing_if`, never re-freeze the goldens.
- `tests/integration/test_search.py` pins the exact `schema_migrations` list.
  Every new `migrations/NNN_*.sql` must extend that expected list.
- One wall-time-sensitive test remains (`test_search.py::test_recurring_feedback_restart_and_no_llm`);
  re-run in isolation before treating a failure as real.
- Pause the acquisition with `process_manage(action='kill')`, not
  `pkill -f acquire_history` -- pkill also matches the invoking shell and is
  blocked as destructive. Wait for the child `import_history` process to exit
  before running the suite.
- `store.rows()` returns a list of dicts, not tuples -- index by column name.
- `AGENTS.md` is write-protected in this environment; record blockers in
  `NEXT_ACTION.md` instead.

## Continuation loop

1. Read `NEXT_ACTION.md` and `implementation-queue.json`.
2. Pick the next dependency-aware task; implement it in the smallest coherent
   unit with a typed request, content-addressed immutable artifact, audit event
   and an explicit attestation.
3. Add tests, run ruff, run the full suite to green.
4. Record the increment in `NEXT_ACTION.md`, then commit.
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
