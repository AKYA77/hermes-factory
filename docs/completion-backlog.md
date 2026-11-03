# Completion directive reconciliation — 3 November 2026

Status **NOT_READY**. Source: [owner-supplied directive](source/Completion_Directive_2026-11-03.md),
reviewed against `2f1e50517f71eed123e4b0f9712d19a3f56d1eca`.
The original Factory.pdf remains authoritative. No scientific defaults are waived.

## Retained evidence, removed from the implementation backlog

The contracts/hashes, WAL registry/fenced leases, v2 order-role ledger, January
EURUSD/XAUUSD structural importer, three signal operators, basic child lineage,
authenticated API and connected inspector already exist. Do not implement them
again. Their remaining acceptance work stays below; passing a component test does
not complete its blueprint milestone.

Gate 0 baseline executed: `bash scripts/verify.sh` — 84 passed, zero failures or
skips, Ruff and dashboard typecheck/build passed. Source archive and canonical
Parquet hashes for both historical pilots reverified; isolated restore again
verified 1,016 files/1,000 jobs/1,000 experiments. Existing results were not changed.

## Active gates

| Gate | Remaining implementation / proof | Status |
|---|---|---|
| 0 | Latest upstream audit, code/data/backup evidence and backlog reconciliation | PASS for bounded baseline; security FAIL |
| 1 | Position/account/P&L golden reconciliation; currencies/Gold; calendar/source integrity; security | IN_PROGRESS; upstream and profile gates BLOCKED |
| 2 | Bounded bars/MTF alignment, feature identity/cache use, native chunked replay, columnar forensic references, measured parity/resource limits | IN_PROGRESS |
| 3 | Persistent training TPE and recurring registered-region admission tested; automatic new-data/region discovery, full diagnostics/improvement, rejection audit and multi-day fairness/soak unfinished | IN_PROGRESS |
| 4 | Independent annual/OOS/WFO/holdout; stability; ranking comparability; paper observation | NOT_TESTED / unfinished |
| 5 | Full dashboard/API; installation, updates/rollback/recovery and Hermes handoff | NOT_TESTED / unfinished |
| 6 | Full available 2025/2026 eight-instrument import, real validation, actual Ubuntu 4-vCPU/8-GB install/stress/multi-day soak and all original gates | BLOCKED / unfinished |

Fresh PyPI/npm metadata still reports Nautilus 1.231.0 with exact fsspec2026.2.0
pin; latest fsspec2026.9.0; deepmerge4.3.1 and vite-plugin-svelte7.3.1 unchanged.
Fresh pip-audit and npm audit exit 1. No overrides, severity changes or ignores.
Finite L1 mismatch remains rejected; missing profile metadata is not invented.
No target VPS, off-host backup destination or brokerage authority is inferred.

Optional Numba/VectorBT/genetic packages are not installed. Only independently
implemented, measured improvements belong in production. New tests supplement,
not replace, original C0–C9 and T01–T30. See acceptance-matrix.md and
implementation-plan.md for original milestones.

## Latest checkpoint

Final code e75c0ba: 144 tests pass; eight January real-source partitions contain
21,345,746 structurally verified quotes. Persistent training TPE and registered-
region recurrence are tested; full autonomous discovery/improvement remains active
work. Byte-bound proof reuse and failed-evidence retention are implemented.

Do not rebuild these increments. Next: monetary/reference/calendar gates; source calendar/monetary corrections; large artifacts/
shared indicator transforms; full autonomous diagnostics/improvement; independent validation;
full dashboard/deployment/target-host gates. See milestone-source-integrity.md and
milestone-report.json. Unresolved security is still a release blocker.


## Owner amendment reconciliation

The [final optimization/handoff amendment](source/Optimization_Handoff_Amendment_2026-11-03.md)
supersedes the earlier gate-6 acquisition ordering: the remaining 176 monthly
partitions are a post-software-handoff DATA_READY task. Preserve the eight real
January imports. Representative real periods and explicitly labeled synthetic
multi-quarter fixtures are sufficient inputs for software verification, subject
to all other software gates. Target 8-GB installation/soak remains an operation
gate. This is sequencing authorization, not acceptance of unfinished software.

Implemented increments: immutable multi-period view composition/source-row
references, bounded exact disk bar cache wired to training/fixed-window workers,
and independent readiness receipt evaluation. Do not rebuild these components.
Their scoped tests do not complete C0–C9/T01–T30. Next: Tier 0 and rejection audits,
shared indicator transforms/optimizer measurement, autonomous discovery and
controlled improvement, full independent scientific validation, dashboard and
installation/handoff. Security/profile/reference blockers remain active.
