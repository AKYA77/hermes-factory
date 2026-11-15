# ADR0057 — Cache identity covers code and fill version

Status: implemented software scope; T02 full acceptance open.

## Problem

T02 requires that a data, code, fill or fold version change invalidates the cache
while an exact rerun reuses the result. `BarCache` keyed its entries on dataset,
instrument, revision, timeframe, range, policy and decimal policy — but **not** on
code revision or fill version. A commit or an execution-version bump could
therefore silently reuse bars compiled under different code.

## Decision

`BarCache._input` now includes `code_revision` and `fill_version` in the cached
identity, defaulting to `factory.provenance.execution_revision()` and
`factory.simulation.ledger.EXECUTION_VERSION`. `BarCache.events` and
`IndicatorCache.events` accept optional `code_revision` / `fill_version`
overrides so a caller can pin a known identity.

The data revision and timeframe/range/policy dimensions are unchanged.

## Safeguards

- An exact rerun with the same identity still hits the cache; only a genuine
  version change misses.
- The default revision is the running source identity, so a commit cannot reuse
  a stale bar cache.
- Cached bar checksums and chronology are still revalidated on every hit; the
  identity change only adds dimensions, it does not weaken verification.
- Cache failures still fail the job rather than substituting canonical evidence.

Evidence: docs/milestone-historical-screen-cohorts.md.
