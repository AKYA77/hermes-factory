# Hermes Factory

**NOT_READY — tested development branch, no production release.** Historical
and paper research only; no brokerage execution. The complete supplied v2.0
specification is preserved in [BLUEPRINT.md](BLUEPRINT.md). No historical strategy
performance is claimed.

Latest verification: **384 passing tests**, Ruff lint/format, dashboard type check
and static build. [Import recovery](docs/milestone-import-resume-2026-11-04.md) and
[staging storage controls](docs/milestone-import-staging-2026-11-04.md) now have
SIGKILL/restart, exact parser, quota and canonical-preservation proof. Earlier
[genuine historical rehearsal](docs/milestone-historical-protocols-2026-11-04.md)
remains bounded exploratory evidence, not independent market validation.
Security findings and full software/release requirements remain unresolved.

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


The [owner's final amendment](docs/source/Optimization_Handoff_Amendment_2026-11-03.md)
separates software verification, full data readiness and target operation
readiness. Bulk historical acquisition follows the tested software handoff;
this development branch has not passed that handoff gate. Immutable partition
views and bounded exact feature reuse are described in [ADR 0011](docs/decisions/0011-software-handoff-and-exact-feature-reuse.md).

Earlier development increment: [amendment checkpoint](docs/milestone-amendment-optimization.md),
with 172 tests and actual 1,000-strategy regression/resource evidence. All three
readiness states remain false; this is not a release or completed handoff.

For bounded post-handoff historical acquisition and safe import recovery, use the
[backfill runbook](docs/runbooks/historical-backfill.md). Full acquisition,
provider/calendar acceptance and target-host operation remain separate gates.
