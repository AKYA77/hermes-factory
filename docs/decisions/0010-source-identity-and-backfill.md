# Source identity, exact volume caps and resumable free backfill

Status: development increment, NOT_READY. No real monetary profile approved.

Catalog verification now checks schema/dataset namespace and cryptographically
binds provenance to the declared content identity. Legacy quotes/v1 identity is
recomputed in bounded batches rather than assembling its quote array. data/v2
supports bounded deep stream rehashing; worker/evaluation intake requests it.
This detects a changed provenance label or changed canonical values even when
someone also updates the Parquet file checksum. Original dataset IDs are retained.
This is integrity checking, not provider authenticity or a defense against a
malicious local writer controlling the entire trusted application/OS.

InstrumentSpec now rejects base/quote currency labels inconsistent with its symbol.
A valid mismatched profile still reaches the separate worker instrument-identity
check. Maximum-volume capping happens before rounding size down to the permitted
step; a cap between steps must not create an off-step quantity. Risk remains
10%/$20 and intended target distance remains 3R. This corrects feasibility without
changing the scenario. Modeled unlimited L1 liquidity is explicitly labeled as an
assumption, not observed source volume. Finite-liquidity exact pricing is still gated.

Backfill plans provider-local months across eight instruments, preserves checkpoints,
reuses verified import receipts, paces requests and limits new partitions per run.
Free HistData is the only source. No paid route, provider bypass or price synthesis.
Transient HTTP/network downloads get at most three attempts; blocked partitions
retain logs and a one-hour cooldown. Per-source locks avoid concurrent duplicate
fetches. Interrupted/unreceipted bytes are quarantined with hash and unverified
provenance, never adopted as a successful capture or deleted. Fresh acquisition
creates a real new receipt. Immutable receipt copies survive latest-report updates.
An importer is parent-death bound and externally timed out; disk reserve pauses
admission. Backfill never activates historical strategy evaluation.

Only structural imports are certified. Source calendars, gap categories, independent
provider comparisons, corrections/current-month recapture and complete coverage
remain mandatory. The present replay interface supports a single immutable source
partition; a multi-month dataset-view/forensic mapping contract is still required
for complete annual/multi-year research. Record/spool capacity failures are explicit,
not silent truncation. These limits prevent a false full-period completion claim.

## Reusing verified content proofs

Catalog now keeps at most 32 in-process verification proofs (configurable down to
zero for the comparator). Every call still hashes the complete source, Parquet and
manifest bytes; no mtime-only shortcut. A semantic proof is reused only for the
same dataset namespace and all three SHA256 identities. A shallow data/v2 check
cannot satisfy a requested deep check. Changed bytes invalidate the proof before
any cached success. Worker intake and final checks request deep proof. Returned
manifests are fresh objects; the cache holds proof keys/booleans, not mutable data.
The cache does not persist across workers or replace source authenticity review.

RAM array caches now bound entry count and key size as well as data bytes, reject
object arrays and conflicting immutable keys, and use immutable bytes backing.
An oversized value is checked before copying. Full shared-feature/L2 integration
remains unfinished. Tests cover zero-length metadata entries and attempted writes.

Coordinator claim checks pause inside its write transaction. A pause arriving
between planning and claim prevents worker admission. The lower-level test-harness
claim primitive remains explicit about bypassing pause; the application always
requests the guarded path. A native gap/insolvency fixture confirms actual loss may
exceed intended modeled risk, reconciles cash, and refuses new risk at negative equity.

## Failure evidence and boundary constraints

Proposed and preflight-valid strategies enter the immutable registry before
execution; failed attempts remain discoverable. Additive migration 003 forbids
strategy deletion. Engine-contract mismatches write content-addressed quarantined
artifacts with the complete contract/spec/profile and actual returned engine
trace, then fail the job. They are never official result artifacts or objective
feedback. Exceptions before a replay result exists still retain the descriptor/job
error; full mid-engine crash forensics remains a recovery gate.

Supported currency instruments reject nonpositive protective levels before order
submission. Quarter construction floors integer seconds instead of rounding a
nanosecond across a quarter boundary. Feature cache identity can name its exact
source range; stop/risk-only changes still share bars. Full scientific window
consumption/comparison and shared-feature implementation remain unfinished.
