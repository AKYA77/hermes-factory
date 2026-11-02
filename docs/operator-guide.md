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
