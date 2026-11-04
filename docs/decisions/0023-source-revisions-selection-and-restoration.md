# Immutable source revisions, selected snapshots and quarantine recovery

Status: scoped source software; full C2, historical approval and release remain open.
Authority: blueprint §§6.2–6.6; Persistent Software Completion Goal §§2/8.

Migration009 retains source observations by explicit provider/instrument/UTC scope,
parent capture identity, original archive hash and canonical dataset hash. Repeated
observation is idempotent. Changed source bytes are classified SOURCE_BYTES_CHANGED,
not asserted to be market corrections; unchanged bytes with changed import identity
are REIMPORT_OR_PARSER_CHANGE. Originals and old canonical partitions remain intact.
Selection is a separate audited append-only compare-and-swap operation. Observing
new data does not silently select it, invalidate frozen research by mutation, or
approve its quality. Replaying an old selection request returns its old receipt
without reactivating an obsolete pointer.

Selected source snapshots require every requested slot, retain every leaf and
equal-time source row, reject selection changes while building, and preserve exact
selection IDs beside the immutable view. New leaves/views get new dataset and
feature/experiment identities. Old caches/evidence remain reproducible and cannot
serve the new dataset identity. Missing slots fail explicitly, never silently skip.

Quarantine episodes preserve the observation and reason even when current source
bytes are corrupt. Current selection does not automatically fall back to another
revision. Worker admission, alias leaves, source approval and official finalization
reject quarantined sources. Finalization checks run under its SQLite writer lock.
Exact restoration may explicitly resolve an episode only after original manifest,
raw bytes, Parquet, count and semantic identity verification. The quarantine and
restoration evidence remain immutable. A later incident creates a new episode.
No file is silently repaired, interpolated, deleted or overwritten by this registry.

Source comparison performs a bounded original-position pass over both captures,
retaining every changed/added/removed position in a hashed JSONL artifact. This is
not optimal edit alignment: one insertion can shift subsequent positions. Scope
and counts disclose that limitation; no market causality or execution is inferred.
Budget exhaustion retains pending inputs/events/failure without a completed receipt.
Cached reports/events are byte-checked against immutable SQL hashes. Raw provider
comparison events remain local and subject to original data usage restrictions.

Explicit --refresh-source creates a separately retained HistData capture and uses
bounded retries within it. It never overwrites the successful original capture.
Normal imports keep the existing cache. Import receipts now automatically register
the source observation under --registry-state (default catalog parent); selection
and quality approval remain separate. Original fixed EST month boundaries use
integer time arithmetic. This does not claim HTTP byte-range resume support or
checkpointed intra-partition import resume: those remain unfinished.

Supported local commands, prefixed by `.venv/bin/python -m factory.cli --state STATE`:

- source-observe SLOT.json DATASET --catalog VAULT
- source-select OBSERVATION --catalog VAULT --actor OPERATOR --reason REASON
  [--expected-selection PRIOR_SELECTION]
- source-snapshot ORDERED_SLOTS.json --catalog VAULT
- source-compare LEFT_OBSERVATION RIGHT_OBSERVATION --catalog VAULT
  [--max-events-bytes 67108864]
- source-quarantine OBSERVATION --actor OPERATOR --reason REASON
- source-resolve QUARANTINE_ID --catalog VAULT --actor OPERATOR --reason REASON

SourceSlot JSON is explicit provider source_id, instrument, start_ns/end_ns and
synthetic flag. Use actual provider period/timezone boundaries, not a guessed UTC
month. Quarantine needs no file repair permission; resolve verifies but does not
write source files. Use the separate tested backup/restore workflow for repairs.

Verification: full scripts/verify.sh exit0,320passed/zero failed/skipped,
356 retained third-party warnings,91.45s pytest; lint/format/frontend check/build
pass. Tests cover two-year boundary ties, correction vs reimport, preserved old
views, stale selection, idempotent request replay, changed-source snapshots,
corrupt-source quarantine/restoration/new incident, alias/native/completion
quarantine guards, exact diffs/cache tampering/budget failure, CLI and refresh retry
retention. No original gate or security check was disabled. Genuine multi-period
source run and resource measurements follow on a clean code commit.
