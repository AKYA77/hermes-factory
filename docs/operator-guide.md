# Development operator guide — NOT_READY

This is a partial initial implementation. Do not install it as a production
24/7 research service or hand it to Hermes as a completed release.

From the checkout, install Python 3.12, uv 0.12.23 and Node 24.19.0 from verified
sources, then run `bash scripts/install.sh`. The script installs the locked local
environment and builds the dashboard, without system users, production directories
or systemd. `--system` deliberately refuses because release gates have not passed.
It preserves existing .local state. `bash scripts/doctor.sh` reports actual
resources and exits nonzero while readiness is false.

For local development:

```
bash scripts/create-admin.sh
bash scripts/seed-fixtures.sh
.venv/bin/python -m factory.cli serve
# separate terminal, same checkout:
.venv/bin/python -m factory.cli coordinator
```

API and dashboard bind to port 8088 on loopback. Use the generated local token file
privately to connect. No default credentials. Do not paste tokens into chat or logs.
The dashboard starts empty unless deterministic work has been queued and run.
Fixtures are explicitly synthetic, not sample market returns. Press Resume to
process the seeded job. Pause stops admission after the current job. Do not assume
processes survive reboot; no production units have been installed.

Read-only checks: doctor, API GETs, verify-backup. State-changing actions: init,
credential creation, seeding, pause/resume, proposals and backup destination writes.
`bash scripts/verify.sh` runs actual tests and dashboard build; requires local
socket support for the HTTP TestClient. `bash scripts/benchmark.sh` records small
synthetic timings; it does not measure historical/VPS throughput.

`FACTORY_STATE=/path/to/state bash scripts/backup.sh /other/path/new-backup`
creates a consistent SQLite snapshot and copies catalog/artifacts. Run
`bash scripts/restore-test.sh /other/path/new-backup` for an isolated restore copy
and checksum test. Stop research/imports before backups: filesystem artifacts and
SQLite are not currently captured under one global snapshot lock. Tokens are
excluded; provision fresh credentials after recovery. No automatic retention,
encryption, off-host transport or production restore is claimed.

Win rate alone never grants validation. Current synthetic training runs are
SIMULATED, with a separate validated-only view that remains empty. A 70% goal is
not a promised return. Independent annual equity, OOS/WFO robustness, full report
exports, charts, autonomous family search and the full operator controls remain
unfinished. A missing Gold profile or source data must remain visible.

VPS installation: pending C8/C9. Required target is Ubuntu LTS 4 vCPU/8GB; no target
access has been supplied. Do not run unfinished update/rollback scripts on a VPS.

## Bounded recurring synthetic training laboratory

The coordinator can now generate and evaluate candidates repeatedly inside an
explicit registered training protocol, without an AI or network connection. It
starts paused. This is development research, not the finished autonomous Factory.
Real monetary profiles and historical evaluation remain blocked.

Create a separate synthetic laboratory and protocol from the current source:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from factory.operations.fixtures import seed
from factory.exploration.persistent import SearchProtocol
from factory.contracts import serialize
root = Path('.local/training-lab')
payload = seed(root, 2000)
protocol = SearchProtocol(
    dataset_hash=payload['contract']['dataset_hash'], profile=payload['profile'],
    window=payload['contract']['windows'][0], family='momentum', timeframe='M1',
    code_revision=payload['contract']['code_revision'], seed=42, max_trials=16,
)
(root / 'protocol.json').write_text(serialize(protocol))
PY
.venv/bin/python -m factory.cli --state .local/training-lab research-register .local/training-lab/protocol.json
.venv/bin/python -m factory.cli --state .local/training-lab resume
.venv/bin/python -m factory.cli --state .local/training-lab coordinator
```

In another terminal, `research-status` reads counters; `pause` stops admission;
`research-disable <protocol_hash>` disables a region. These commands all use the
same `--state .local/training-lab` prefix. The coordinator idles when a finite
protocol budget is exhausted. No claim of endless family expansion is made.
Source changes invalidate old protocols; register a new version instead of editing
old experiments. Keep the original training/selection/holdout boundaries.

Authenticated API routes: GET research/status, research/protocols and research/trials;
POST research/protocols, research/protocols/{hash}/disable and jobs/{id}/cancel.
Viewer tokens cannot execute writes. Cancelled job completion is fenced; an
already running process stops at the next control check. Official objectives come
from worker artifacts, never from a supplied win-rate/objective field.

## Free historical structural backfill

Plan coverage without fetching data:

```
.venv/bin/python -m factory.operations.backfill_history --through 2026-11
```

Run at most four missing provider-month imports, preserving checkpoints and raw
source/receipts (state-changing, free web source only):

```
.venv/bin/python -m factory.operations.backfill_history --through 2026-11 --execute --max-partitions 4
```

Repeat only within disk/provider budgets; the program skips verified partitions,
paces requests and cools down failures. Its source, Parquet and raw archive hashes
must remain intact. A successful structural import does not approve a calendar,
broker profile, monetary evaluation or source completeness. Current-month recapture,
correction reconciliation and complete annual dataset views remain unfinished.
Defaults use .local/historical-catalog, deliberately separate from active synthetic
research. Do not relabel these imports as independently validated strategy results.
