# Requirement audit — 2026-11-13

Scope: the 73 requirements that were `NOT_TESTED` at the start of this session.
Method: each criterion was compared against the tests that demonstrate it, the
tests were executed, and only criteria whose every clause is covered by passing
evidence were moved to `PASS`. Nothing was marked `PASS` on a scoped reading.

## Moved to PASS (21 total, 12 new this session)

| ID | Criterion demonstrated | Evidence |
|---|---|---|
| T03 | Restart after partial commit is idempotent; no duplicate run/trade/attempt counts | 5 tests: requeue idempotency, process-kill recovery, coordinator death, persisted expiry, fenced restart |
| T08 | Long/short entry and exit adjust exactly 2 pips where eligible, correct units | 3 tests asserting `actual_adverse_adjustment == 0.0002` on both sides and zero slippage on limit exits |
| T09 | Limit never exceeds limit price; stop gap recognized; timeout absence flagged | 3 tests, one per clause |
| T12 | Immediate stop, favourable→SL, near-miss, timeout, missing path, long/short | 5 tests |
| T13 | Improved child records exactly what changed and preserves parent/failure history | 2 tests |
| T14 | Poor training score retained; failed OOS not validated; not silently discarded | `test_T14_negative_evidence` + `test_retained_candidates.py` |
| T16 | Max five per instrument, eight boards, <70% retained, empty slots empty | 4 tests |
| T20 | Unauthenticated access rejected, typed pagination, correct status/error transitions | `test_T20_auth_pagination` (401/422/403/NOT_READY) |
| T21 | Hosted LLM disabled; deterministic queue continues and resumes | `test_T21_no_model_or_network_dependency` blackholes proxies and removes API keys |
| T25 | Changing the OOS sample changes the contract and invalidates the claim | `test_T25_window_change_identity` |
| T26 | JPY and Gold reject ambiguous pip/contract metadata | `test_T26_unknown_units`, `test_currency_identity_cannot_disguise_jpy_as_usd`, `test_gold_requires_independent_units_and_cost_equivalent` |
| T27 | Overwriting a completed run or injecting AI statistics fails | `test_T27_immutable_audit` plus immutable search/strategy/discovery/holdout guards |
| R03 | 2-pip floor with wider spreads preserved, separate 2-pip slippage, outward rounding, distinct limit behaviour, all eight instruments | 240/240 and 800/800 exact parity; frozen goldens 240/240 |
| R12 | Pinned toolchain, committed Cargo.lock, CI build, deterministic clean rebuild | Fresh clone built a byte-identical binary (sha256 `e9f9c845…`) |
| T55 | Immutable revision history, explicit selection, missing periods, quarantine, byte-proven restoration | 12 tests in `tests/integration/test_source_versions.py` |

## Partial coverage recorded, still NOT_TESTED

T02, T05, T06, T10, T11, T15, T17, T22, T23, T28 — each has named, passing
tests that cover only part of its criterion. The exact missing clause is now
recorded in `supporting_evidence_scope` for each.

## Blocked, not merely untested

These cannot be closed by more work in this repository alone:

- **Real acquired data**: R09 (24-month source-accepted coverage), T05, T30, T32,
  T44, T51, T54, T56.
- **Target hardware**: R11, T31, T35 (4 vCPU / 8 GiB envelope).
- **Owner policy decisions**: R01's fee term (the reference explicitly refuses
  commissions), the NautilusTrader replacement path (§5a of the parity report),
  T30's quarantine correction policy.
- **Major new implementations**: R04 (indexed TickFirstHitIndex execution),
  R08 (native Rust strategy generator), R10 (native data-access buffers).
- **Release/deployment**: T29, T22, T23, C9.

## New verification path

`tests/parity/` now exists, so the R01–R12 verification command
`.venv/bin/pytest tests/parity` runs for real: frozen goldens, the
Nautilus-blocked golden check, fixture parity, restart/batch equivalence and the
engine binary (5 tests, ~20 s).
