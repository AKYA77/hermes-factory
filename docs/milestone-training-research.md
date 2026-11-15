# Persistent training research increment

Status **NOT_READY**. Tested source `6728371ddaf4721594608d02f58f92b12a26ac02`.
The full original project remains the objective. See completion-backlog.md;
no C0–C9 milestone or T01–T30 contract is waived or replaced by this increment.

Actual implementation: additive search/resource migration; immutable protocols,
trials/outcomes; persistent TPE reconstruction and measured artifact feedback;
recurring registered-region generation/recovery; CPU-ledger allocation; bounded
queue; operator/viewer API and CLI; cancel fencing, heartbeat/process lock, Linux
parent-death binding, sampled RSS guard and cgroup-aware admission. Template-only
proposals no longer masquerade as completed/pruned optimization. ADR 0009 defines
scope and limitations. No new dependencies or second matching engine.

Verification actually executed:

- `bash scripts/verify.sh`: 125 passed, zero failures/errors/skips, 146 retained
  warnings; Ruff and dashboard typecheck/build pass.
- Tests execute actual native workers, persist measured objectives, restart store/
  study objects, reject OOS/holdout/source mismatch and corrupt artifacts, retain
  immutable failures, check API roles and cancellation. Labeled toy optimization
  demonstrates deterministic learning, not market efficacy.
- Actual Linux kernel parent-death kill passes. A first test-harness run failed
  on a missing import; fixed and rerun. This is not a full reboot/soak proof.
- `uv build --wheel` succeeded; both 001/002 SQL migrations are packaged. Official
  installed-wheel scientific execution remains gated on release provenance.
- Fresh 16-trial/2,000-synthetic-quotes research probe: 17 cycles, 15 unique native
  replays (30,000 events), 12 objective observations, three no-closed-trade prunes,
  one exact duplicate skipped. Pause and finite budget verified. 24.421s wall,
  23.733 parent+children CPU seconds, 128,237,568-byte parent / 295,387,136-byte
  worker peak RSS, 12,741,669-byte state. System RAM peak not measured.
- Backup/isolated restore verifies 19 files, 15 jobs, 15 experiments and SQLite
  integrity. Existing artifacts/results remain preserved.

The first longer probe aborted at a duplicate-only idle cycle because its harness
incorrectly treated idle as completion. Service behavior was to continue. Failed
state `.local/directive-recurring-probe` is retained; the fixed harness used a new
state and completed. This is recorded in milestone-report.json.

```
.venv/bin/python -m factory.operations.research_probe --state .local/new-research-probe --trials 16 --rows 2000 --output reports/runtime/new-research-probe.json
```

Earlier 1,000-candidate synthetic campaign and full real-quote no-order feed probes
remain source-bound in milestone-report.json; their source is 39e52bb, not this
optimizer commit. None establishes historical profitability or VPS throughput.

Real historical monetary research is still blocked on calendars/profiles/currency
rounding. Complete automatic data/region discovery, all families, cohort-guided
improvement/OOS lineage decisions, independent validation/stability, full dashboard,
installation/recovery, source backfill and actual Ubuntu 4-vCPU/8-GB multi-day soak
remain unfinished. Both security audits fail; no production tag.
