# ADR0027 — Checkpointed retained-archive import

Status: development implementation; no software/release readiness claim.
Authority: Factory blueprint §§6.1/6.5/6.6/11.5, final completion request §9.

The existing streaming catalog remains the only publisher of canonical data/v2.
HistData decoding now stages bounded Parquet chunks with a fsynced checkpoint.
The checkpoint binds raw ZIP SHA256, exact member/period, parser and staging
source bytes, provenance and batch size. Each descriptor retains original-row
count, uncompressed source offset, raw prefix SHA256 and staged Parquet SHA256.
A nonblocking process lock serializes a particular import intent. Different
source bytes, provenance, parser code or batch size produce a new intent; no
old source, completed partition, admission or experiment is mutated.

On retry, every checkpointed chunk and corresponding raw source prefix is
rehashed and checked for exact row counts, offsets, schema and source sequence.
Only remaining source rows are parsed. ZIP deflate still requires decompression
of the prefix: no constant-time compressed seek or HTTP Range resume is claimed.
An interrupted HTTP capture continues to follow the older preserve-and-reacquire
policy, because a verified provider range/validator contract is unavailable.

A chunk written before checkpoint publication is retained as an orphan, not
adopted by scanning filenames. Checkpoints and failure receipts are written
atomically; SIGKILL may leave an orphan with no cleanup receipt. Disk pressure
stops before another chunk. Failed final publication keeps the entire decoded
prefix so retry does not parse it again. No canonical manifest is published
until the original complete streaming verifier checks ordering, exact quote
bytes, source copy, roundtrip and identity. Chunk memory is <= batch_rows
(1..65536); checkpoint size is capped at 16MiB. Tiny batch settings may reach
that cap; restarting with a larger batch starts a distinct intent. Retained
staging consumes additional disk and is not silently removed; safe retention
and complete operational storage policy remain separate open gates.

The import CLI uses recovery automatically, returns rows_reused/rows_decoded and
checkpoint identity, and preserves immutable import receipts/source observations.
Selection, calendar acceptance and historical admission remain explicit separate
operations. Canonical source bytes, duplicate rows, timestamps, integer prices,
existing data/v2 hashes and scientific/financial formulas are unchanged.

Tests use generated ZIP files, including Gold-shaped decimal values, not genuine
historical samples. They cover SIGKILL/restart, zero-prefix decode on retry,
identity parity, source/checkpoint/chunk corruption, forged cursor, invalid
spread, disk reserve, orphan preservation, concurrent locking, final publication
failure and CLI/source-observation integration. They do not certify all C2 or
provider calendars, source completeness, 8GB operation, scheduled source refresh,
full UI, HTTP byte-range recovery or historical strategy performance.

## Exact parser conversion and publication source binding

A reproduced v1 parser defect accepted a bid of
1.1234500000000000000000000000000001 at scale1000000 by rounding during Decimal
multiplication. The source is not representable at that scale. Parser v2 first
bounds nonfinite/extreme values, then uses as_integer_ratio and integer divmod,
independent of Decimal precision. Valid legal quotes retain their exact values;
o historical source or result is rewritten. New parser-version provenance creates
new import identities rather than recertifying an old parser's output. Context
2/6/28/60 and extreme-exponent regressions are retained. Previously discarded
precision cannot be recovered from canonical values; only retained original bytes
can establish whether an old capture is affected.

Final catalog publication also accepts an expected raw-source hash. A source
swap between staged-prefix verification and catalog intake now fails before any
canonical directory can be published. The original during-copy hash verification
remains. This binds the resumed quote stream to the original archived bytes.
