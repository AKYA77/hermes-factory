# Mandatory acceptance ledger

Status NOT_READY. All T01–T30 remain required. A scoped synthetic/unit test with a
T number in its name does not imply full gate acceptance. No unit count is
substituted for VPS_SMOKE_PASS, VPS_SOAK_PASS or OPERATION_READY.

| ID | Requirement | Current evidence / remaining work |
|---|---|---|
| T01 | Canonical strategy identity | Unit normalization/differences tested; broader operator semantic coverage pending |
| T02 | Full experiment hash/cache | Hash inputs and exact API cache reuse tested; full L2/invalidation graph pending |
| T03 | Unique restart completion | Fenced lease expiry/idempotent completion tested; process-kill recovery pending |
| T04 | Data round-trip | Real Forex/Gold month structural round trips and bounded synthetic fixtures passed; calendar/source/instrument acceptance remains |
| T05 | Gaps and updates | Quarantine/corruption tested; session gaps/incremental updates pending |
| T06 | Closed MTF availability | Independent sparse/tied-quote multi-timeframe compiler reference passes; strict later-time execution tested; full session/stale/latency cases pending |
| T07 | Spread floor | Property fixtures and Nautilus USD-profile quotes tested; JPY/Gold engine corpus pending |
| T08 | Adverse eligible fills | Arithmetic sides and Nautilus market/stop fixtures tested; all production units pending |
| T09 | Order semantics | Native partial entries/exits, cancellation races, safety closes and deadlines tested; finite-L1 exact-pricing mismatch blocked, full constraints pending |
| T10 | Hypothetical risk | Budget and min-volume tested; dated cross-currency/broker profiles pending |
| T11 | 24h deadline | Exact quote timeout and missing-exit flag tested; delayed-gap policy further review |
| T12 | MFE/MAE paths | Compact summary/inline equality and canonical forensic reconstruction pass alongside stop/partial/tied-quote tests; full cohort/golden suite pending |
| T13 | Parent-child | Changes and parent preservation tested; paired cohort evidence pending |
| T14 | Reject vs remember | OOS failure status helper tested; complete persisted hypothesis decision workflow pending |
| T15 | Annual/WFO splits | Quarter/purge/frozen windows tested; annual/pooled/holdout and WFO refit pending |
| T16 | Eight independent boards | Empty boards + synthetic populated board tested; full ranking/diversity/archive regression pending |
| T17 | Dedup + screen audit | Cached proposal and execution/source version guards tested; screened-out audit not implemented |
| T18 | Search fairness | Seeded bounded proposal-count allocation tested; CPU-budget fairness/endless exploration pending |
| T19 | Reproducibility | Synthetic replay artifact hashes identical; tagged historical reproduction pending |
| T20 | API/dashboard | Auth, pagination, roles and state tested; browser full C7 workflows pending |
| T21 | Agent offline | Deterministic worker has no model dependency; offline job fixture in current suite; full 24/7 services pending |
| T22 | Rollback | Synthetic atomic pointer health-failure test only; migration/live process recovery pending |
| T23 | Backup recovery | SQLite + artifact copy/checksum corruption tested; full source/state/board production rehearsal pending |
| T24 | 8GB performance + soak | Small synthetic wall/CPU/RSS benchmark measured; target VPS/soak unrun |
| T25 | Scientific independence | Window identity changes tested; consumed holdout-use workflow pending |
| T26 | Instrument units | Real Gold source grid retained at 0.001 without rounding; monetary Gold/JPY specifications remain blocked |
| T27 | Immutable evidence | SQL triggers/no metric-write API/idempotent completion tested; full provenance/adversarial injection suite pending |
| T28 | User actions | Pause/resume/proposal/queue/audit tested; diagnosis/cancel/retry/export actions pending |
| T29 | Provenance | Local command/test/benchmark/lock reports recorded; signed/tagged release evidence pending |
| T30 | Full vertical | Synthetic API→queue→Nautilus→diagnose→board tested; real Forex→validation→browser acceptance blocked/pending |

Additional directive gates supplement the original acceptance contract:

| ID | Requirement | Current evidence / remaining work |
|---|---|---|
| T31 | Bounded native delivery parity | PASS scoped fixtures: full results equal at batches 1/2/3/8192 vs materialized native delivery; real feed-only months received all quotes; target-host strategy stress remains NOT_TESTED |
| T32 | Independent cash/native inventory reconciliation | PASS scoped USD fixtures for fill sets, signed inventory and cash conservation; native rounding difference is explicit and monetary policy BLOCKED |
| T33 | Shared feature identity and bounded compilation | PASS scoped oracle/hash parity and stop-independent bar keys; persistent cache/invalidation/append integration unfinished |

No mandatory gate is marked OPERATION_READY. See known-limitations.md for the
complete implementation gaps, external blockers and scope of measured evidence.
