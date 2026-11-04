# ADR0028 — Import staging payload budgets and verified reclamation

Status: scoped data-operations software, NOT_READY.
Authority: blueprint §§6.4/6.7/15.5 and owner final completion request §9.

Imports now share a default2GiB staging payload admission budget within a
catalog. The CLI accepts `--staging-budget-bytes`; raising/lowering the operational
budget does not change source or scientific identities. Payloads are encoded in
a bounded batch buffer before a write. A catalog-wide lock serializes inventory
and admission across different import intents. Known Parquet chunks, interrupted
writes and unknown retained files count conservatively. JSON audit/checkpoint
metadata and lockfiles are excluded: this is a payload quota, not a filesystem
hard quota. Individual checkpoints remain capped at16MiB, inventory at100,000
entries, source/archive/row bounds remain, and disk reserve checks still apply.
No quota event deletes a verified prefix, orphan, source or result. A larger
budget can resume the same prefix. Symlinked staging roots/entries fail closed.

After publication the checkpoint durably binds the canonical dataset and exact
manifest hash. The explicit trusted-local `factory.operations.import_staging`
command deeply verifies that dataset, checks the source/provenance/manifest
binding, then removes only the checkpoint's checksum-matching duplicate chunks.
It never removes canonical source/Parquet/manifests, uncheckpointed orphan files,
failure records, other import intents or research evidence. Corrupt/missing
unreclaimed chunks and corrupt canonical data require review rather than cleanup.

An immutable request receipt and `chunks_reclaimed` marker are fsynced before
unlink. A crash leaves a retryable request without a success receipt. A new
attempt checks canonical evidence again and removes remaining verified duplicate
chunks. Result receipts retain actual bytes/counts removed. Once reclaimed,
import reuse verifies the canonical dataset deeply rather than recreating
staging. Legacy checkpoints lacking a publication receipt are not automatically
reclaimed; they require their matching importer to finish/verify first. Older
parser/staging source bytes retain distinct intents and are never overwritten.

Generated tests exercise quota rejection/retry, other-intent/orphan accounting,
shared locks, CLI integration, repeated cleanup, interruption after the first
unlink, corrupt source/chunk refusal, symlink/path containment and identical
canonical bytes. The earlier actual SIGKILL import proof remains. No actual
Contabo, filesystem-hard-quota, general archive retention/compaction, scheduled
refresh or complete Data Center UI acceptance is claimed.
