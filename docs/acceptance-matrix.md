# Mandatory acceptance ledger

Status NOT_READY. All T01–T30 remain required. A scoped synthetic/unit test with a
T number in its name does not imply full gate acceptance. No unit count is
substituted for VPS_SMOKE_PASS, VPS_SOAK_PASS or OPERATION_READY.

| ID | Requirement | Current evidence / remaining work |
|---|---|---|
| T01 | Canonical strategy identity | Unit normalization/differences tested; broader operator semantic coverage pending |
| T02 | Full experiment hash/cache | Hash inputs and exact API cache reuse tested; full L2/invalidation graph pending |
| T03 | Unique restart completion | Fenced lease expiry/idempotent completion tested; process-kill recovery pending |
| T04 | Data round-trip | All-eight January 2025 structural round trips (21,345,746 rows), provenance/deep identity and bounded fixtures passed; calendar/source/instrument acceptance remains |
| T05 | Gaps and updates | Quarantine/corruption/checkpoint/retry/capture recovery tested; sessions/current-month recapture/revisions pending |
| T06 | Closed MTF availability | Independent sparse/tied-quote multi-timeframe compiler reference passes; strict later-time execution tested; full session/stale/latency cases pending |
| T07 | Spread floor | Property fixtures and native all-eight synthetic long/short corpus pass; verified real profile/source gates remain |
| T08 | Adverse eligible fills | Native all-eight synthetic market/stop/limit and 0.001 Gold grid goldens pass; verified production units remain pending |
| T09 | Order semantics | Native partial entries/exits, cancellation races, safety closes and deadlines tested; v4 retains v3 IOC policy and cancels exhausted market remainders without extra-tick fills in BUY/SELL native fixtures; full constraints pending |
| T10 | Hypothetical risk | Budget/min-volume/max-cap and exact-rational repeating-FX boundary regression pass; dated synthetic cross-currency sizing tested; verified broker profiles pending |
| T11 | 24h deadline | Exact quote timeout and missing-exit flag tested; delayed-gap policy further review |
| T12 | MFE/MAE paths | Compact summary/inline equality and canonical forensic reconstruction pass alongside stop/partial/tied-quote tests; full cohort/golden suite pending |
| T13 | Parent-child | Changes, parent preservation, immutable multiple-parent edges and complete-trade-set paired training reports tested; full independent cohort confirmation pending |
| T14 | Reject vs remember | OOS failure status helper tested; bounded persistent training hypothesis decisions now tested; independent failure/holdout workflow pending |
| T15 | Annual/WFO splits | Exact nanosecond quarter boundary/purge/frozen windows tested; annual/pooled/holdout and WFO refit pending |
| T16 | Eight independent boards | Empty boards + synthetic populated board tested; full ranking/diversity/archive regression pending |
| T17 | Dedup + screen audit | Cached proposal and execution/source version guards tested; exact-zero-signal rejection with persisted receipts, deterministic native audits, false-negative quarantine and TPE PRUNED feedback passes scoped tests; broader staged/approximate cohorts pending |
| T18 | Search fairness | Measured CPU-based registered-cell allocation and bounded persistent TPE tested; full-space fairness/continuous expansion/soak pending |
| T19 | Reproducibility | Synthetic replay artifact hashes identical; tagged historical reproduction pending |
| T20 | API/dashboard | Auth, pagination, roles and state tested; scoped actual Chromium policy/cancellation/auth/mobile rehearsal passes; full C7 workflows pending |
| T21 | Agent offline | Recurring registered-region loop and actual workers run with invalid network proxy and no model; full 24/7 multi-day services pending |
| T22 | Rollback | Synthetic atomic pointer health-failure test only; migration/live process recovery pending |
| T23 | Backup recovery | SQLite + artifact copy/checksum corruption tested; full source/state/board production rehearsal pending |
| T24 | 8GB performance + soak | Small synthetic wall/CPU/RSS benchmark measured; target VPS/soak unrun |
| T25 | Scientific independence | Persistent alias-safe holdout reservation, input-use enforcement, candidate freeze, consumption-before-execution and supervised native confirmation/restart tested; full WFO/validation decision workflow in progress |
| T26 | Instrument units | Real Gold source grid retained at 0.001; synthetic 0.001 native fills, lot/base-unit equivalence and JPY conversion pass; real dated metadata remain blocked |
| T27 | Immutable evidence | SQL triggers/failed registry/quarantined execution evidence/no metric-write API/idempotent completion tested; worker checksum/integrity and conflicting-completion rejection now pass; full provenance/adversarial suite pending |
| T28 | User actions | Pause/resume/proposal/queue/audit, research registration/disable/history and cancellation API tested; diagnosis/retry/export/browser workflows pending |
| T29 | Provenance | Local command/test/benchmark/lock reports recorded; signed/tagged release evidence pending |
| T30 | Full vertical | Synthetic API→queue→Nautilus→diagnose→board tested; real Forex→validation→browser acceptance blocked/pending |

Additional directive gates supplement the original acceptance contract:

| ID | Requirement | Current evidence / remaining work |
|---|---|---|
| T31 | Bounded native delivery parity | PASS scoped fixtures: full results equal at batches 1/2/3/8192 vs materialized native delivery; real feed-only months received all quotes; target-host strategy stress remains NOT_TESTED |
| T32 | Independent cash/native inventory reconciliation | PASS scoped USD fixtures for fill sets, signed inventory and cash conservation; USD/native quote-account references and all-eight synthetic dated FX/Gold lot-base-unit goldens pass; real metadata validation remains open |
| T33 | Shared feature identity and bounded compilation | PASS scoped oracle/hash parity and stop-independent bar keys; exact disk cache, code/range invalidation, three-operator parity, recovery and budget checks pass; indicator transforms/append acceptance unfinished |

| T34 | Persistent training optimizer | PASS scoped actual worker feedback/restart/immutability/leakage rejection; labeled toy TPE learning, no market efficacy claim |
| T35 | Worker supervision/resources | PASS scoped actual kernel parent-death, stale fencing, memory-failure and cgroup arithmetic tests; real 8-GB reboot/soak NOT_TESTED |

| T36 | Proof-cache parity | PASS scoped: full-byte invalidation, bounded cache and identical outputs across 1,000 strategies; no production-throughput claim |

No mandatory gate is marked OPERATION_READY. See known-limitations.md for the
complete implementation gaps, external blockers and scope of measured evidence.


Owner amendment gates (no original requirement is removed):

| ID | Requirement | Current evidence / remaining work |
|---|---|---|
| T37 | Immutable multi-period inputs | PASS scoped synthetic cross-quarter, boundary-tie, exact row/leaf references, native forensic reconstruction, overlap/mixed-instrument/tamper rejection; real multi-period calendar/revision acceptance pending |
| T38 | Independent readiness states | PASS scoped receipt/hash/missing-gate tests; SOFTWARE_VERIFIED, DATA_READY and OPERATION_READY all false in current project evidence |

Full bulk acquisition is a post-handoff DATA_READY task under the owner's final
amendment. Software gates still require representative real-source integration,
all implementation requirements, full scientific workflows and tested handoff.

| T39 | Controlled training improvement | PASS scoped actual offline parent/child workers, immutable plans/edges/outcomes, identical non-strategy contracts, CPU budgets, small-sample/selectivity/censoring guards; full regime/independent confirmation pending |
| T40 | Restart identity and CPU conservation | PASS scoped search/v2 JSON defaults, preserved legacy v1 IDs and shared-job CPU attribution across protocols/policies; prior immutable accounting retained |
| T41 | Static dashboard execution | PASS scoped exact bootstrap CSP hashes, injected-script rejection and real Chromium controls; full blueprint UI acceptance pending |

| T42 | Protected managed holdout | Scoped native confirmation/restart, alias-view training denial, prospective reservation/legacy influence rejection, immutable selection/consumption and forged-authorization rejection pass; not full C6 acceptance |

| T43 | Chronological native protocol | Scoped multi-quarter separate TPE refits, frozen forward candidates, final confirmation, native annual/pooled/cost and training sensitivity stages pass; historical monetary/global inference/regime gates remain open |
| T44 | Exact marked equity | Scoped full-quote/fill USD cash/inventory valuation, partial-open marking, drawdown and bounded display envelope goldens pass; v2 also marks synthetic dated cross-currency/base-unit lot positions; real profile admission remains blocked |
| T45 | Canonical native profile representation | Decimal-padded equal-fingerprint profiles now produce identical native geometry and complete outputs; numeric cost/risk defaults unchanged |

| T46 | Pinned native Money policy | Actual USD/JPY/CHF constructor boundary checks and all-eight synthetic quote-P&L partial-entry/exit lifetimes pass; USD replay checks both native account and position references. Dated FX and verified broker units remain open |

| T47 | Dated native conversion and base units | Scoped all-eight long/short stop/target native goldens, FX tie/chunk/materialized parity, synthetic Gold lot equivalence/third-decimal grid, gap insolvency, exact-risk boundary and actual JPY training/confirmation pass. Real metadata/calendar gates remain open |

| T48 | Connected validation laboratory | Actual Chromium registration/pause/exact-nanosecond export, native staged report/curve/annual/pooled views, protected status and protocol stop pass; desktop/mobile plus previous control regression pass. Full C7 workflows remain unfinished |

| T49 | Qualification before final observation | Actual weak-forward native restart ends before final refit/selection/consumption; declared censor/DD/neighbor policy, marked insolvency/open-loss and missing native evidence guards pass; v1 IDs stay read-only; global regime/source validation remains open |

| T50 | Captured declared session rules | Exact DST/holiday/one-nanosecond/ambiguous-boundary and immutable TZif goldens pass; declarations do not verify actual broker calendars |
| T51 | Lossless full-event source QA | Scoped all-gap/view/tie/reference/precision/order/byte/cache/budget/restart/captured-input/API/CLI tests pass; Actual clean df70 scan of 21,345,746 real rows and authenticated browser/export/mobile pass; historical admission remains false pending reviewed metadata/revisions and full coverage |

| T52 | Abrupt source QA death | Actual SIGKILL child retains fsynced attempt/input identity, creates no complete receipt; full retry preserves orphan and checks all rows. Automatic orphan inventory/fenced QA remains open |
| T53 | Profile-aware search bounds | search/v3 exact declared-pip bounds, all-eight units, native Gold low/high BUY/SELL risk and 3R, legacy v1/v2 identity/range and restart checks pass. Existing scientific v1/v2 retains old range pending new protocol opt-in |
