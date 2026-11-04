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
| 2 | Shared indicator transforms, append/revision cache acceptance, large artifact APIs and actual target resource gates; bounded bars/disk reuse/native streaming are implemented | IN_PROGRESS |
| 3 | Persistent training TPE and recurring registered-region admission tested; automatic new-data/region discovery, full regime/recursive improvement, richer reject auditing and multi-day fairness/soak unfinished | IN_PROGRESS |
| 4 | Independent annual/OOS/WFO/holdout; stability; ranking comparability; paper observation | NOT_TESTED / unfinished |
| 5 | Full dashboard/API; installation, updates/rollback/recovery and Hermes handoff | NOT_TESTED / unfinished |
| 6 | Post-handoff DATA_READY acquisition; real validation and actual Ubuntu 4-vCPU/8-GB install/stress/multi-day soak; all original gates retained | BLOCKED / unfinished |

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
Their scoped tests do not complete C0–C9/T01–T30. Exact-zero Tier 0/rejection-audit integration is now implemented (ADR 0012).
Next: richer screening/audit cohorts,
shared indicator transforms/optimizer measurement, autonomous discovery and
full regime/recursive improvement, full independent scientific validation, dashboard and
installation/handoff. Security/profile/reference blockers remain active.

Bounded diagnosis-driven training improvement is now implemented (ADR 0013),
including persistent negative decisions and paired evidence. New search/v2 hashes
fix CPU-default round-trip drift; legacy IDs remain unchanged. Browser rehearsal
found/fixed CSP bootstrap blocking. Full C5/C7 completion is still not claimed.


## End-to-end completion mandate (latest owner request)

Source: source/End_to_End_Completion_Mandate_2026-11-03.md, read completely.
Compared with current HEAD 9034cbc. Existing tested components in ADRs 0011–0013
remain retained; the active backlog excludes rebuilding them. The goal is a full
SOFTWARE_VERIFIED candidate, not another component completion announcement.

Current implementation gaps: dated conversion/monetary/reference and calendar
software; genuine approximate cost-aware screening/shortlist and calibrated
reject cohorts; shared indicators/projection/append/revision optimization; full
families/automatic region expansion/repeated diagnostic improvement; scientific
OOS/WFO refitting/annual/holdout/stability/robustness/comparable boards; full
non-JSON dashboard and exports; installed provenance, installer/lifecycle/recovery
and complete integrated rehearsal. Security and repository visibility need real
resolution; target-host tests need executable procedures and separate evidence.

Current GitHub API observation: repository PUBLIC. Prior private-visibility claims
are not current evidence. Await owner visibility instruction; do independent
implementation locally meanwhile. First implementation: persistent global holdout
reservation/use enforcement across training, evaluation and alias dataset views;
then chronological evaluation/refitting and validation reporting/UI integration.
No readiness state has passed.

Protected managed holdout enforcement is now implemented (ADR 0014/migration005),
with actual supervised confirmation and separate immutable evaluation results.
Baseline plus new tests: 176 passed, 170 recorded third-party warnings. This is
intermediate evidence; continue into WFO refitting/annual reporting/robustness and
full validation integration. Visibility remains public pending owner instruction.

Chronological validation stage execution and marked equity are now implemented
in ADR 0015/migration006. The full verification command passed 186 tests with
174 recorded third-party warnings plus lint/frontend checks. Actual multi-quarter
native run remained INSUFFICIENT_EVIDENCE (forward counts 28 and 1, holdout 23);
no false promotion. This is not a full C6/product completion announcement.
Next: dated currency conversion/native money/contract-unit reconciliation and
verified-profile admission; then calibrated approximate screening/full discovery,
regime/cohort robustness and complete laboratory/UI/lifecycle integration.

Execution v3 IOC remainder correction now has native BUY/SELL partial-entry
and partial-stop regression goldens (ADR 0016). Full suite: 190 passed, 182
third-party warnings, 66.77 seconds; Ruff/frontend passed. Currency, contract
units and native money reconciliation remain next; no readiness promotion.

Independent pinned native Money/account/position reference is implemented (ADR
0017). Full suite: 212 passed, 182 warnings, 71.12 seconds; lint/frontend passed.
Dated cross-currency conversion-context timing and native broker-unit conversion
remain active monetary work. All readiness states remain false.

ADR 0018 execution v4 now fixes dated native FX cache timing, profile volume to
base units, account sum receipts and exact-risk volume flooring. All-eight
synthetic long/short native cost/order goldens, tied-source/chunk parity, Gold
lot equivalence/0.001 grid and actual JPY training/protected confirmation pass.
Full verification: 259 tests, zero failures/skips, 322 third-party warnings,
71.96 seconds; lint/frontend passed. Benchmark next. Verified real profiles,
calendar integrity and full C0–C9/product gates remain active; NOT_READY.

New measured v4 milestone: docs/milestone-monetary-validation-2026-11-04.md.
Eight supervised 100k-quote synthetic jobs and 1,000 distinct short-fixture
strategies pass with measured CPU/RSS. Connected Validation Lab passes real
browser/API checks; no historical performance/production-throughput claim.
Next correctness work: pre-confirmation qualification and marked-equity/data
checks; verified profile/calendar/revision software; then complete approximate
screening/shared indicators/discovery/recursive diagnostics/product lifecycle.
Both dependency gates still fail. All readiness states remain false.

ADR 0019 scientific protocol v2 now qualifies forward/training/neighborhood
evidence before final consumption, and requires marked/native/censoring checks.
Legacy v1 remains read-only; explicit synthetic software rehearsal cannot certify.
Full suite: 271 passed, 340 warnings, 73.22 seconds; lint/frontend passed.
Next: clean-source browser verification for v2, then verified profile/calendar/
revision software and full approximate screening/discovery/diagnostics/lifecycle.

Clean-source a530de5 browser/coordinator proof now passes: v2 weak forward
qualification ends after six actual native jobs, no final observation consumed;
actual report/curve/exact export/mobile/stop checked. Separate explicit rehearsal
registration passes. Next: verified dated metadata/calendar, lossless quality/
revision receipts, richer Tier 0 and full autonomous/product/reliability gates.
Instrument-specific stop search bounds must handle a 0.001 Gold grid with a
verified larger pip unit; a universal 20..200 tick search can be wholly infeasible.

ADR 0020 adds captured declared calendars and full-event bounded source quality
(migration007), with CLI/API/connected Market data evidence. Full suite 287
passes, 340 warnings, 79.66 seconds; lint/frontend passed. Next: clean-source
real January scan/resource proof and real browser data-panel verification; then
reviewed metadata/admission, revisions, cache/approximate research and remaining
scientific/product/lifecycle gates. Unknown broker facts still block real research.

Clean df70 source QA/browser milestone: all eight real January sources,
21,345,746 quotes, structurally scanned in 171.809645s wall / 175.536930s CPU,
184,852,480B peak RSS, 1,935,328B generated QA state. Actual Chromium Gold
inspection/exact export/mobile checks pass. This is not historical strategy,
broker/calendar, Contabo or complete C2/C7 evidence. All readiness remains false.
Next reliability fix: identify retained partial source scans after uncatchable
process death; then reviewed metadata/admission and remaining mandatory work.

Abrupt QA process-kill/retry test now passes: durable attempt/input/code markers
precede source reads; SIGKILL cannot create a completed receipt; retry rescans
all rows and preserves old partial evidence. Orphan inventory/fenced scheduling
remain open. Next correctness fix: versioned instrument-aware search bounds so
Gold's observed precision never implies a broker pip or an infeasible universal
20..200 tick stop region.

Profile-aware search/v3 now passes native Gold endpoint eligibility/risk/3R,
all-eight declared-pip unit checks and legacy identity/range/restart checks
(ADR 0021). Existing scientific v1/v2 refits explicitly retain old search/v2;
new scientific opt-in remains versioned future work. Combined full verification:
302 passed, zero failed/skipped, 348 warnings, 82.08s; lint/format/frontend pass.
Milestone: docs/milestone-source-quality-recovery-search-2026-11-04.md.
Next: reviewed dated metadata/calendar admission and source revisions, then
remaining real screening/discovery/diagnostics/scientific/product/lifecycle work.
Do not mark C2/C4/C6 complete, publish a ready release or weaken security checks.

Owner Persistent Software Completion Goal archived verbatim. completion-ledger.json
tracks C0–C9/T01–T53 without treating scoped tests as complete milestones.
ADR0022/migration008 adds captured reviewed profile/calendar/source admissions,
permanent revocations and an approved-input branch in native workers/evaluator.
Full verification310passed/354warnings/85.15s plus frontend/lint/format pass.
Generated authorization fixtures are NOT genuine historical market validation.
Next clean-source browser proof, source revisions, historical scientific/search
propagation, cost-aware screen/shared indicators/full discovery and remaining gates.

ADR0023/migration009 now implements explicit source versions/selections/snapshots,
full bounded positional comparisons and permanent quarantine/restoration episodes.
New source IDs invalidate new-view caches while frozen prior history stays intact.
All320tests pass;356warnings/91.45s plus lint/format/frontend pass. Actual native
alias and same-lock completion quarantine tests pass. Genuine additional-period
proof next. Intra-partition import checkpoint resume, full data UI/admission/search
propagation and other original gates still remain. Both security scans still exit1;
latest upstream native still pins vulnerable fsspec. GitHub remains PUBLIC and
latest CI covers9034 only, not these unpushed commits. No readiness promotion.
