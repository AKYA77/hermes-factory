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
