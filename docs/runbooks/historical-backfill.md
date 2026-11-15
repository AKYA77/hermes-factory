# Bounded free historical backfill and import recovery

Historical research/paper simulation only. Structural import is not source
calendar acceptance, historical strategy validation or DATA_READY. Do not start
full acquisition during development handoff. Hermes performs it on the authorized
VPS after release/host checks. No paid provider route is used.

Use the installed release's working directory and Python environment. The
examples below use this development checkout, with retained state under `.local`.
On an installed host explicitly map archives, catalog and checkpoint to its
protected persistent state volume. Preserve these paths across service restarts.

1. Check free space, backup policy and provider usage terms. The supported source
   is HistData ASCII bid/ask ticks, fixed UTC-05:00 without DST. Never treat quote
   precision as a broker specification or the fourth column as observed volume.
2. Choose the latest offered provider month. Example2026-10 below is a planning
   example, not proof those partitions are available. Current-month captures can
   be incomplete and must be labeled as such.
3. Plan without downloading:

```bash
.venv/bin/python -m factory.operations.backfill_history \
  --through 2026-10 \
  --archives .local/histdata-archives \
  --catalog .local/historical-catalog \
  --checkpoint .local/historical-backfill/checkpoint.json
```

4. When authorized, use the same command with `--execute --max-partitions 1`.
   Each invocation imports at most the stated bound (1..8), pacing requests and
   preserving blocked attempts with a one-hour cooldown. Repeat bounded calls
   until every requested partition has a verified structural receipt. Respect
   cooldowns; do not spin or delete a failure checkpoint to force retries. A
   zero process exit alone does not establish completeness: inspect
   `remaining_partitions`, every failure and current-month limitations.
5. Interrupted imports reuse retained ZIPs and durable decoded chunks. The import
   CLI performs this automatically; it never selects incomplete data. HTTP
   capture interruption preserves failed bytes and reacquires; HTTP Range resume
   is not certified. Source/parser/provenance changes have distinct identities.
6. The per-catalog default staging payload budget is2GiB. For a direct bounded
   import an explicit operational budget can be supplied, for example:

```bash
.venv/bin/python -m factory.operations.import_history \
  --instrument EURUSD --year 2025 --month 1 \
  --archives .local/histdata-archives \
  --catalog .local/historical-catalog \
  --registry-state .local --staging-budget-bytes 2147483648
```

   That command is an example, not permission to recapture/research an existing
   held-out period. On payload-budget or disk-reserve failures, preserve state,
   investigate storage and increase a budget only after measuring headroom.
   Audit metadata is outside the payload quota. Never delete raw or canonical
   evidence to make an import pass.
7. After successful publication, `import_resume.checkpoint_id` in the immutable
   import receipt identifies duplicate staging that may be reclaimed explicitly:

```bash
.venv/bin/python -m factory.operations.import_staging \
  --catalog .local/historical-catalog --checkpoint-id CHECKPOINT_SHA256
```

   This deeply verifies the published canonical source and manifest, then removes
   only its verified duplicate chunks. It preserves failures, orphan writes and
   all canonical files. A failed/interrupted cleanup can be rerun; no broad
   `rm -rf` cleanup is part of the workflow. Corrupt canonical or staging bytes
   stop cleanup and need a separate investigated restore.
8. `--refresh-source` on the direct import command creates a separately retained
   provider capture, new immutable receipt and source observation. Never overwrite
   the old capture or assume changed bytes are automatically approved corrections.
   Use `source-compare`, `source-quality`, `source-select` and `source-snapshot`
   with explicit slots/reviewed scope (ADR0023). Selection is compare-and-swap;
   quarantine blocks affected aliases and finalization. Preserve all older versions.
9. Run the complete source-quality scan with captured calendar/profile inputs.
   Review every gap and boundary event; no interpolation or invented market
   closure. Register exact primary references and explicit research assumptions,
   then scoped admission through the existing reference-register/source-admit
   interfaces (ADR0022). Do not approve unknown Gold/broker conventions or reuse
   technically explored periods as untouched final holdout.
10. Verify the selected multi-period catalog, completeness, source revisions,
    approved profiles and backups before declaring DATA_READY. Import count is
    not calendar/fidelity acceptance. The final production scheduler, general
    archival retention/compaction and complete Data Center UI remain unfinished;
    this runbook does not claim those software gates passed.

Recovery evidence and tests: ADR0027/0028 and reports/milestones. The generated
recovery/benchmark fixtures are never historical market-performance evidence.
