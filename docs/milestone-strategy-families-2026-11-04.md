# Versioned family/compiler integration — NOT_READY

Baseline published commit:b31f6cd111c5ae1852c1db303242cd29b29ff6e3.
Tested scientific source SHA256:
`76e12da7ccfafe27dcd78bf1ec2d1f01b84e349a16cbaec5e9a183e4e1629c36`.
ADR0029 documents the exact entry definitions. These are generated software
hypotheses and acceptance fixtures, not historical strategy-performance claims.

## Implemented behavior

Explicit Signal2 adds trend, reversal, range, volatility, UTC-session momentum
and flat unanimous confluence. Mean reversion, momentum and breakout remain.
Each family uses the same bounded past-only interpreter for exact screening and
Nautilus entry proposals. Confluence accepts two/three distinct non-nested
operators sharing lookback/threshold; permutations have the same canonical ID.
Sessions require explicit unique integer UTC publication hours. No arbitrary code
is accepted; no matching engine, fill policy, $20/10% sizing, stop/3R convention,
accounting or validation threshold was changed.

A valid declarative signal example (a hypothesis, not a trading recommendation):

```json
{"operator":"confluence","version":"2","lookback":12,"threshold":"1","components":["momentum","trend"],"session_hours":[]}
```

Search5 carries the family/components/hours through durable proposals/restart,
existing dedup/CPU accounting, synthetic safe screening or reviewed historical
admission and actual workers. Scientific-validation4 propagates the fixed
hypothesis into prior-only Search5 refits and existing independent stages.
Legacy signal/search/validation JSON shapes, hashes and sampling versions remain;
older versions reject implicit new-family upgrades. No holdout criterion is
relaxed and historical promotion stays disabled pending remaining gates.

Coverage additively records9categories across8instruments/7timeframes, preserving
existing counters. API and strategy schemas were regenerated from actual typed
models, including earlier routes absent from the stale OpenAPI snapshot.

## Actual verification

- `bash scripts/verify.sh`: exit0,463passed/0failed/0skipped,374 third-party
  warnings; pytest165.545s; Ruff lint/format, Svelte check/build pass.
- New family focused suite:79passed/12warnings/3.31s. Hand references cover
  long/short trend/reversal/range/volatility, session publication time and
  confluence agreement/conflict. Every new category has nonempty future-suffix
  causality checks on all7timeframes. A sparse MTF fixture rejects a higher bar
  ending after the current entry bar despite simultaneous publication.
- All6new categories generated actual native fills with no integrity/rejection
  errors; completed trades executed strictly after their compiled signal times.
  Durable v5 proposals/recovery and coverage accounting pass. An actual
  supervised session-strategy worker completes and persists native objective/CPU
  feedback with an invalid network proxy. v4 refits register v5 in earlier
  training windows and consume no protected holdout.
- Legacy-focused contracts/compiler/search/historical suite:47passed. The exact
  original serialized strategy shape/hash remains. Existing full-suite accounting,
  source, leakage, native counterexample and protected-holdout tests all pass.
- Real loopback HTTP smoke passed: dashboard HTML, anonymous401, authenticated
  paused overview. This is not browser rendering or full C7 acceptance.
- Full verification wrapper169.792246s wall/167.241421s child CPU,
  maximum child-process RSS951,996,416B. Host4CPU quota/32GiB, Python3.12.14,
  Node24.22.1. This is not a target8GB benchmark, aggregate RSS or throughput claim.

An initial reversal activity fixture failed7of63cases because its small bounce
did not meet the predeclared threshold. Its original levels and failure are
retained. The generated path was extended with explicit threshold-size reversals;
no formula/threshold/assertion was weakened. Successful final cases still require
nonempty activity. This preserves the distinction between a test design failure
and a false no-lookahead pass from an empty signal set.

[Hashed evidence](../reports/milestones/2026-11-04-strategy-families/manifest.json)
contains XML, full/focused logs, failure summary, resources, host and prior
published-CI observations. The following commit packages this tested source.

## Remaining mandate and publication boundary

This is not full C4/C5/C6/C7 or SOFTWARE_VERIFIED. Automatic discovery of new
approved regions, full-space allocation, shared indicator transforms, calibrated
safe shortlist/audits, recursive cohort diagnosis/improvement, global/regime
qualification and full graphical workflows remain. The new v4 propagation test
is scoped to prior-only refit; it is not a new full successful historical
walk-forward/holdout result. Genuine new-profile/Gold integration still needs
reference/source access and reviewed assumptions. No full backfill ran.

The prior b31f6cd remote and PR head were verified. Its exact push CI
41930487012(Python)/41930487165(dashboard) passed; PR dependency review41930497759
failed. fsspec/deepmerge remain unresolved; no gate was disabled. New current-head
CI is checked after pushing this source, never inferred from those prior runs.
Primary-source/GitHub-API allowlist additions remain saved but unapplied in the
environment draft. Historical DATA_READY and actual target OPERATION_READY
remain separate false states. No release/tag/main merge/deployment was made.
