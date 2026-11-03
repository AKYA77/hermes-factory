# Hermes Factory

**NOT_READY — tested development branch, no production release.** Historical
and paper research only; no brokerage execution. The complete supplied v2.0
specification is preserved in [BLUEPRINT.md](BLUEPRINT.md). No historical market
results are claimed.

Latest progress: [bounded replay and directive reconciliation](docs/milestone-bounded-replay.md)
and [machine-readable evidence](milestone-report.json). Free January 2025 EURUSD
and Gold ticks have lossless, memory-bounded structural imports. This is not
historical strategy validation. The current suite has 115 passing tests; security
findings and the full release gates remain unresolved. Previous v1 synthetic
campaign reports are retained in history, not treated as current v2 evidence.

Implemented: typed immutable strategy/experiment contracts; fingerprints; exact
integer quote Parquet storage with raw hashes and quarantine; leased durable job
queue; isolated NautilusTrader replay with fixed adverse-fill extension;
closed-bar mean-reversion/momentum/breakout signals; measured MFE/MAE diagnostics;
bounded child proposals; frozen-window replay helper; basic metrics and separate
instrument boards; authenticated API and connected dashboard state inspector;
backup/restore rehearsal and release-pointer test harness.

Not yet complete: full real-source coverage/calendar acceptance, Gold profiles and cross-
currency conversion, autonomous discovery/improvement/data-update scheduling,
full OOS/WFO/annual/independent evidence, all metrics/charts/exports, complete
security/recovery/installer/update/rollback gates, Contabo benchmarks and release.
The full [acceptance matrix](docs/acceptance-matrix.md) remains the contract.

Development host tested: Debian 13 x86_64, Python 3.12.14, Node 24.19.0; cgroup
4 CPU quota and 32 GiB RAM. Target Ubuntu 4 vCPU/8GB has not been tested.

```bash
bash scripts/install.sh        # local development only; no system deployment
bash scripts/create-admin.sh   # secret written to a local 0600 token file
bash scripts/seed-fixtures.sh  # explicitly synthetic data/job; research stays paused
.venv/bin/python -m factory.cli serve
# in another terminal from this checkout:
.venv/bin/python -m factory.cli coordinator
```

The local API/dashboard uses port 8088 on loopback. Access through an authorized
SSH tunnel on a remote host; do not expose publicly. Connect using the generated
token privately, then Resume to run queued research or Pause to finish the current
job and stop admission. State is under `.local/` by default. All eight boards begin
empty; a synthetic test run never proves historical profitability or validation.
The current inspector shows real JSON state, not the completed C7 dashboard.

After a reboot, restart both development commands; production systemd templates
are not installed or verified. Find job failures and audit events in the dashboard.
A failed ready/doctor check is expected while release prerequisites remain unmet.
Full exports and owner-friendly research reports are pending.

```bash
bash scripts/verify.sh
bash scripts/benchmark.sh
bash scripts/doctor.sh  # nonzero while NOT_READY
```

See [operator guide](docs/operator-guide.md), [implementation plan](docs/implementation-plan.md),
[known limitations](known-limitations.md), and [Hermes instructions](HERMES_AGENT_INSTRUCTIONS.md).
No approved tag or production handoff exists. Remaining owner inputs: owner-reviewed instrument specifications,
GitHub management access/private visibility verification, and authorized VPS test access.
