# Continuous completion loop — NOT_READY

Continue `/opt/hermes-factory`, branch `build/initial-factory`, PR #1:
https://github.com/AKYA77/hermes-factory/pull/1. The owner authorizes each tested
milestone commit/push and exact-SHA PR/CI verification. No merge, repository
visibility change, production deployment, release tag or readiness claim.

Read the latest owner directive first:
`docs/source/Owner_Lean_RaptorBT_Final_Directive_2026-11-12.md` (ADR 0071), then
AGENTS.md, the complete authority/blueprint and
`docs/source/Continuous_Autonomous_Completion_Loop.md`. Then inspect Git HEAD/tree,
completion-ledger.json, development-state.json, implementation-queue.json and run:
`.venv/bin/python scripts/completion-queue.py`. Continue without asking what to do.
Scoped task verification never implies its parent gates pass. Final reconciliation
explicitly maps every one of the 79 requirements (67 original plus R01–R12); none may
disappear behind a scoped checkpoint. SOFTWARE_VERIFIED/DATA_READY/OPERATION_READY
remain false.

## ACTIVE — read this first (owner directive 2026-11-14)

The governing directive is now
`docs/source/Owner_Hermes_Factory_Full_Completion_Directive_2026-11-14.md`, which
supersedes the 2026-11-12 text wherever they differ. It prioritises real
implementation over raising the PASS count and names these outstanding bodies of
work, in order:

1. **Rust execution migration (R01/R02)** — exact equity/drawdown and
   open-position mark-to-market accounting in Rust; verified instrument/broker
   profiles; an independent **non-Nautilus** reference oracle validated against
   the frozen goldens; then connect the engine to the factory's primary
   historical/paper execution path through a stable versioned interface. Do not
   remove NautilusTrader until the replacement is integrated and independently
   verified.
2. **Rust-vs-Nautilus benchmark** — identical datasets, signals and assumptions;
   separate data-read, signal-compile, sequential-execution and end-to-end
   timings plus CPU, wall, peak memory and disk I/O; cold and warm cache;
   restart overhead; enforced 4-vCPU / 8-GiB envelope. No invented speedup
   factors and no extrapolating synthetic results to historical throughput.
3. **R10 native data pipeline**, then **R04 TickFirstHitIndex** (with sequential
   fallback), then **R08 native strategy generator**.
4. Historical data readiness for the approved 24-month window; source acceptance,
   never structural import alone.
5. Dashboard/performance/supervisor panels and the resumable autonomous research
   workflow.
6. Repair and keep synchronised NEXT_ACTION.md, implementation-queue.json,
   completion-ledger.json and development-state.json.

**Unfinished gate states must stay false.** SOFTWARE_VERIFIED, DATA_READY and
OPERATION_READY are FALSE and must not be set true on scoped evidence.

### Last audit checkpoint

Externally audited commit `e42714ee66948a6ff03497035320302a7f7150ea`: 51 PASS /
28 NOT_TESTED, all three readiness gates false, Rust parity substantially
demonstrated but not integrated as the primary executor, no verified
Rust-versus-Nautilus performance benchmark.

---

## Owner directive 2026-11-12 — Phase 0 complete

The owner's latest design directive is recorded at
`docs/source/Owner_Lean_RaptorBT_Final_Directive_2026-11-12.md` with ADR 0071 and the
measured inventory at `docs/inventory-2026-11-12.md`. It supersedes the
NautilusTrader matching mandate, the blanket M1 signal loop, the two-stage
approximate-then-full backtest and the absence of an absolute win-rate gate.

Phase 0 deliverables in this commit:

- Versioned owner amendment, ADR 0071 and measured VPS/repository inventory.
- Twelve new acceptance requirements R01–R12 added to `completion-ledger.json`
  (79 total: 6 `PASS`, 73 `NOT_TESTED`). None is claimed passed.
- New queue task `raptorbt_execution` (priority 25) owns R01–R12 and is the
  selected next task.
- `ARCHITECTURE.md` now carries the target architecture with the historical
  description retained below it.

Measured facts that change the plan:

- Catalog holds **182** partition manifests, 8 instruments × 22 months
  (2025-01 → 2026-10). **2024-11 and 2024-12 are missing for all eight
  instruments** — 16 partitions, not a full re-download.
- No partition is source-accepted; all remain
  `STRUCTURAL_PASS_CALENDAR_REVIEW_REQUIRED`. `DATA_READY` stays false.
- Host is 6 vCPU / 11 GiB, larger than the 4 vCPU / 8 GiB target; target-envelope
  evidence must be measured under enforced limits.
- **No Rust toolchain existed.** `rustc 1.100.0` / `cargo 1.100.0` were installed
  on 2026-11-12; the toolchain must be pinned and CI-built (R12).

**Next action:** begin Phase 1 — scaffold the RaptorBT-derived Rust execution
crate, port the exact bid/ask pricing and bracket semantics from
`factory/simulation/`, and prove parity against the frozen Nautilus goldens
before any Nautilus removal.

**Known blocker:** `AGENTS.md` is write-protected in this environment; the
approval prompt timed out, so the builder contract still names NautilusTrader as
the matching engine. The new directive and `ARCHITECTURE.md` carry the governing
text. Owner action is required to update `AGENTS.md` itself.

## Phase 1 — Rust execution engine, exact parity demonstrated

A from-scratch Rust engine now exists at `rust/raptor-engine/` with a committed
`Cargo.lock`, and `scripts/parity_raptor_engine.py` proves it reproduces the
Python reference exactly.

Measured results (exact = equal prices, quote indices, roles, flags, exit
reasons, sizes and account P&L as an exact rational):

| Corpus | Result | Wall |
|---|---|---|
| 100 cases, EURUSD | 100 / 100 | — |
| 240 cases, all 8 instruments | 240 / 240 | — |
| 800 cases, all 8 instruments, fresh seed | 800 / 800 | 29 s |

Six reference behaviours were recovered empirically and are now reproduced:
signal eligibility at the first quote strictly after `available_at` with a
same-quote entry fill; take-profit filling at the counterparty price; bid/ask
side-specific stop triggers; the per-quote order (matching phase → deadline
close → signal loop) including deadline-cancelled protection; synchronous
callback fills; and 28-significant-digit equity rounding after each fill.

Six real Rust defects were found and fixed, including a silently wrapping
`i128` rational comparison (exact decimal28 conversion rates give denominators
up to 10^27, so `Rat` is now arbitrary-precision) and an off-by-one in
`round_sig28` that rounded conversion rates to 27 digits instead of 28.

**R01, R02 and R03 remain `NOT_TESTED`.** The corpus is generated synthetic
fixtures. Partial fills, cancellation races, safety closes, fees, genuine
acquired historical periods, and determinism across restart and batch sizes are
not yet demonstrated, so NautilusTrader stays installed and remains the
reference. Full detail and the reproduction commands:
`docs/milestone-raptor-engine-parity-2026-11-12.md`.

**Next action:** extend parity to genuine acquired catalog partitions, then
implement partial fills, cancellation races, safety closes and fee accounting.
After that, freeze the Nautilus goldens and write the migration parity report.

### Phase 1b — migration parity report and frozen goldens

`reports/raptor-migration-goldens.json` freezes the NautilusTrader 1.231.0 /
adverse-fill v4 reference output over a fixed 240-case all-instrument corpus,
and `scripts/verify_raptor_goldens.py` confirms the Rust engine reproduces every
golden digest exactly (**240/240**).

`docs/milestone-raptor-migration-parity-2026-11-12.md` records the discrepancy
report (six root-caused defects, none open), the determinism argument, and the
remaining migration-gate gaps: order-state emission, partial fills, verified
broker profiles and genuine-period restart/batch evidence. **NautilusTrader is not
removed and R02 remains `NOT_TESTED`.**

### Phase 1 publication record

Pushed at `78c4ba4a5a91f3c71bf0126a73a1452aa5637276` (supersedes the earlier
`62182c2` record; local `git rev-parse HEAD` matches `git ls-remote`) (local `git rev-parse HEAD`
matches `git ls-remote origin refs/heads/build/initial-factory`). CI contexts
`audit`, `dashboard`, `python` and the new `rust` all **pass**; the rust job ran
`cargo test --release --locked` (2 passed) and
`scripts/parity_raptor_engine.py --cases 200 --instrument all` (**200/200**).
Full local suite: **709 passed, 0 failed** in 1375 s. CI contexts `audit`,
`dashboard`, `python` and `rust` all pass for this commit.

### Phase 1c — order states and partial fills

The Rust engine now emits the order state machine (ENTRY/STOP_LOSS/TAKE_PROFIT/
TIMEOUT registration and terminal transitions, with the filling order `FILLED`
and the sibling protection `CANCELED`), and reproduces partial fills against a
finite eligible book:

| Behaviour | Reference detail reproduced |
|---|---|
| Size-increment rounding | The order quantity is rounded before the book cap and the capped quantity again, using Python `round(binary64, precision)` — banker's rounding on the binary64 value, not decimal half-even |
| Partial entry | The IOC remainder is cancelled; cancelling the parent cancels the attached protection → `PROTECTION_LOST` and a `SAFETY_CLOSE` at a later quote |
| Partial protection/timeout exit | Only the remainder is cancelled; the position stays open and the exit is re-submitted, so a thin book shrinks it geometrically |
| Cancelled protection | No longer triggers in the matching phase |
| Multi-fill exit | Quantity-weighted average exit price and the last exit's timestamp/quote index; no exit price for a position that never closed |

Verified exact: **240/240** finite-book fixtures (seed 20261112, ≈35% inject a
half-depth book), **800/800** unbounded fixtures (seed 777), **30/30** genuine
acquired partitions, and the refrozen goldens (**240/240**, artifact sha256
`29e0f43417d71c6921df38cc333da989cae784f39a318715bcf8b791489fad0a`).
Twelve discrepancies were root-caused and fixed; none remains open.

**R02 remains `NOT_TESTED`.** Verified broker profiles and genuine-period
restart/batch evidence are still missing, so NautilusTrader stays installed and
remains the reference. Full detail:
`docs/milestone-raptor-migration-parity-2026-11-12.md` (§3 discrepancy table,
§4a partial fills).

**Next action:** obtain verified broker profiles and record restart/batch
equivalence evidence. Only then may the NautilusTrader removal begin.

### Phase 1d — restart and batch-size equivalence

The replay loop was factored into a resumable `Replayer`: its state (equity, open
position, signal cursor, consumed-quote index, every fill/trade/skip) is a pure
function of the quotes consumed and serializes to JSON exactly. The CLI gained
`--batch-size N`, `--dump-state` and `--resume-from`.

`scripts/parity_raptor_restart.py` proves that batch sizes 1/2/3/7/64 and a
cross-process restart at a quote boundary all reproduce the single-pass result
exactly, **and** that result still matches the Python reference — **240/240**
exact (seed 20261112, all eight instruments, ≈35% finite-book). Added to the CI
rust job at 120 cases.

This closes migration-gate item 7. **R02 remains `NOT_TESTED`.** Gate items 1–8
are now demonstrated; only item 9 (removing NautilusTrader) remains.

### Phase 1e — Nautilus-free golden verification

Case generation, normalization and comparison moved to `scripts/raptor_cases.py`,
which imports nothing from NautilusTrader. `scripts/verify_raptor_goldens.py`
now imports only that module, so the frozen-golden evidence survives Nautilus
removal: running the verifier with a meta-path hook that raises on any
`nautilus_trader` import still reports **240/240**.

The direct parity, restart and genuine-partition harnesses still invoke the
Nautilus-backed Python reference and so do not survive removal.

**Next action — owner decision required.** Gate items 1–8 are demonstrated; only
item 9 (removing NautilusTrader) remains. Removing it would also remove the
oracle every parity result is checked against, because the Python reference
(`factory/simulation/runner.py`) imports
`nautilus_trader.backtest.engine.BacktestEngine`. Either build an independent
non-Nautilus reference and verify it against the frozen goldens first, or confirm
in writing that the Nautilus-backed runner is accepted as the item-2 reference.
Full reasoning and the measured removal inventory:
`docs/milestone-raptor-migration-parity-2026-11-12.md` §5a.

## Environment change observed this session

The prior checkpoint recorded histdata.com/oanda.com/six-group.com as proxy-denied
(CONNECT 403). On this host those providers now return HTTP 200 and the free
HistData ASCII tick form is reachable for every month 2025-01 through 2026-10
(2026-11 is the current partial month and has no issued token). The historical
source path is therefore **open**, not blocked. Verify actual reachability again
before assuming either state; do not bypass a proxy or dump secrets.

The project virtualenv was absent on this host. It was rebuilt from the committed
lockfile with `uv venv --python 3.12` + `uv sync --frozen` (Python 3.12.3). The
host runs 3.14 and has no system pip/ensurepip; use `.venv/bin/python`.

## Latest tested source

Recorded in completion-ledger.json `latest_verified_source` and
development-state.json `last_verification`. Full-suite and focused results are
updated at each tested checkpoint. Do not use prior CI as proof for a later commit.

## Completed this continuation

### 2026-11-14 — owner directive, absolute win-rate floor, stale blocker cleanup

**New governing directive.** `Owner_Hermes_Factory_Full_Completion_Directive_2026-11-14.md`
is now recorded and is the active authority; it supersedes the 2026-11-12 text where
they differ. It explicitly prioritises real implementation over raising the PASS
count, and orders the remaining work: Rust execution migration, an independent
non-Nautilus reference oracle, a Rust-vs-Nautilus benchmark under a 4-vCPU/8-GiB
envelope, then R10, R04 and R08, then data readiness and the dashboard.

**R07 corrected to an absolute floor.** The first implementation let any caller
configure the threshold down to zero. `ValidationCriteria.min_win_rate` is now
bounded `ge=0.5, le=1`, so neither production research qualification nor a
synthetic rehearsal can lower it; thresholds above 50% stay configurable.
`win_rate_gate()` additionally rejects malformed evidence (missing, non-integer,
negative or impossible counts) instead of defaulting to a favourable answer, and
raises if handed a floor below the absolute minimum. Tests added for malformed
input, sub-50% refusal in both directions, exact-50% inclusivity, legacy specs
that predate the field keeping the 50% default, and the end-to-end pipeline.

**Two more stale blockers closed:** R06 (one accurate testing pipeline -- no
OHLC or approximate-pruning path exists; the cohort estimates are report-only)
and R05 (per-strategy timeframe selection -- asserted directly, proving a D1
strategy builds no M1 bars). Both had been recorded as unfinished although the
behaviour was already implemented.

**Project management repaired.** `implementation-queue.json`'s `raptorbt_execution`
task no longer describes Phase 0 as the next step; it now records the achieved
parity evidence and what remains. NEXT_ACTION.md carries an unambiguous ACTIVE
section at the top pointing at the 2026-11-14 directive and the ordered
outstanding work, with the older milestone sections retained below it.

### 2026-11-13 — acceptance audit, nine more requirements evidenced, fee accounting

Ledger moved from 21 PASS to **48 PASS / 31 NOT_TESTED**. Commits pushed to
`build/initial-factory`; CI green on `tests`, `dependency-review`, `dashboard`.

**Requirements newly demonstrated with clause-level evidence:** T05, T29, T30,
T52, C1, C3, C5, C6, T42. The productive pattern was auditing criteria whose
clauses were implemented and exercised but never asserted, then writing the
missing test rather than accepting "partial": proof-cache parity over 1,000
calls (T36 earlier), cancel/diagnostics audit rows (T28 earlier), rollback
byte-intactness (T22), restore row and artifact equality (T23), exact 1:3 risk
geometry (T10), UTC bucket-edge bar availability (T06), cross-instrument and
cross-timeframe search fairness (T18), profile-aware search bounds (T53),
annual/WFO split reporting (T15).

**Two stale blockers corrected:**

- `scripts/benchmark.sh` runs on this host; the recorded "cgroup v1"
  FileNotFoundError was already handled by `cgroup_limit`. `benchmark.py` now
  also emits a `source_urls` block so the generated report carries the project's
  provider endpoints plus an explicit synthetic-fixture note (T29).
- `SourceQuality.orphans()` already existed and was tested; the automatic
  orphan inventory half of T52 was evidenced against it.

**Real implementation (R01 fees):** no fee model existed anywhere. Added
`InstrumentSpec.commission_per_unit` (default zero = no fee model, negatives
rejected), charged it in the Rust engine on every fill entry and exit in quote
currency (unit-tested at exactly -1000 / -1999), and made the Python runner
derive the fill commission from the same field so a configured fee makes
`replay()` refuse loudly with `UNSUPPORTED_NATIVE_REFERENCE_COMMISSION` instead
of silently ignoring it. Re-verified afterwards: goldens 240/240, direct parity
200/200, restart/batch 120/120, genuine partitions 7/7.

**Attempted and reverted:** emitting equity/drawdown from the Rust engine.
Keeping an exact running balance instead of rounding per fill dropped the
parity corpus from 800/800 to 22/80 with fills and trades disagreeing; reverted
and re-verified 80/80. R01 stays open on equity/drawdown emission and verified
broker profiles. The trap is recorded in the `hermes-factory` skill.

**Exact next action:** the remaining 31 are externally blocked or unimplemented
majors. Resume with the highest-priority unimplemented requirement the queue owns:
**R07** (strict 50.00% post-cost win-rate qualification gate, rechecked on any
execution-model or data change) — no absolute gate exists yet
(`factory/validation/protocol.py` enforces 0.7 only for other metrics). Then R04
(indexed execution), R05 (per-strategy timeframe selection), R08 (native
generator). External inputs still required: real acquired metadata/calendar and
profile admission (T32/T37/T43/T44/T46/T47/T49/T51), target 4-vCPU/8-GiB hardware
(T31/T35), and owner review/sign-off (T41/T54).

**All 176 partitions are imported and the catalog is consistent.** Structural
acquisition went from 129 to **176 of 176**; `refresh` reports 182 datasets
verified, 0 missing, 0 mismatched, consistent. The final three blocks were three
different causes, found by reading the recorded failure files rather than
re-running the importer:

- **Crossed quotes** (USDCAD 2026-07) — 353 rows where `bid > ask`, an arbitrage
  that cannot persist, crossing by 1-7 pips. Blocking the partition withheld
  1,226,059 good rows for 353 bad ones (0.029%), so
  `source-quality-quarantine/v1` removes them whole and records the count,
  magnitude histogram and bounded positions. The receipt states plainly that
  this policy is **lossy**, unlike the lossless ordering correction.
- **Lock contention** (AUDUSD 2026-10, XAUUSD 2026-09) — the non-blocking budget
  lock fails fast when two workers collide. Running one worker at a time clears
  it; the fail-fast guard itself is intentional.
- **Staging never reclaimed** (AUDUSD 2026-10) — `reclaim_all` existed, was
  tested and was exposed via the tools CLI, but the acquisition driver never
  called it. Its own docstring predicted exactly this: *"without reclamation the
  payload budget is eventually exhausted and further imports block even though
  their canonical data is already published."* 3.38 GiB had accumulated across
  269 intents. The driver now reclaims, but only when staging exceeds half the
  budget — calling it unconditionally re-verifies every chunk and stalled the
  supervisor for 15 minutes with no import running.

**The Source quality panel has been verified against real archives in a real
browser.** A new fixture (`scripts/source-quality-browser-fixture.py`) runs the
scanner over one genuine partition per instrument from the real catalog; the
existing smoke then drives authenticated loopback Chromium against the served
dashboard. Receipt: **PASS**, 8 source receipts, **20,165,841 real rows**, XAUUSD
inspected, `source_metadata_blocked` true (calendar `UNKNOWN_CALENDAR`, profile
`UNKNOWN_SPEC` throughout), exact full-event export byte-identical to the API
response, no page errors, no mobile overflow at 390 px. Until now the panel had
only ever been exercised against generated TEST_ONLY fixtures.

Two defects surfaced on the way, both worth recording:

- **The scanner reported its own correction as damage.** It flagged 48,065
  `SOURCE_RECORD_SEQUENCE_GAP` and 15,533 `SOURCE_CHRONOLOGY_MISMATCH` across the
  eight instruments. Both were false positives: the lossless correction publishes
  a *permutation*, so the timeline is monotonic while `original_record_order`
  stops being consecutive. Measured directly, the published EURUSD partition has
  **0 timestamp inversions** and 331 sequence gaps in 1,805,682 rows — the gaps
  are the reordered rows. Chronology now compares timestamps only, and sequence
  now detects a *repeated* position, which is the real defect.
- **A gap is no longer treated as a defect, and that is a limitation.** After
  reordering and quarantine a gap is indistinguishable from a correctly removed
  row unless the source row count is known, and the manifest records none. A
  duplicated row is detectable without it.

**Source-to-restore rehearsal added over genuine data.**
`scripts/source_to_restore_rehearsal.py` runs the stages exercisable on this
host against the real acquired catalog in one chain: verify (deep
`Catalog.verify`), feature_cache (closed M5 bars), native_replay (full tick
stream with a monotonicity check), rank, and backup_restore (backup plus the
restore rehearsal). Measured over a genuine 2,032,079-tick partition: 6,333 M5
bars, 24,405 files backed up, 13 migrations re-applied, 129 catalog partitions
re-verified after restore, 345.6 s wall, 1.48 GB peak RSS. The receipt lists the
nine stages it did **not** run — import, admit, catalog, generate, screen,
diagnose, improve, independent_evaluation, dashboard — and never claims them.

**All six dashboard browser-acceptance smokes pass.** `scripts/run-browser-smoke.sh`
starts the dashboard **and** a coordinator against one isolated TEST_ONLY state,
waits for the API, runs a smoke in real Chromium, and tears both down. All six
pass with zero page errors and no mobile overflow: discovery, historical screen
cohort, reviewed inputs, screen cohort, screen fallback and validation. Eight
harness defects were found and fixed first — five smokes pointed at a nonexistent
`/usr/bin/chromium`; `serve` started no coordinator so job-driven workflows never
completed; the historical smoke polled at 250 ms against a 120 req/60 s limiter and
always tripped 429; the discovery smoke used an ambiguous page-global
`Authorized by` locator; the reviewed-inputs fixture accepted `--state` but
hardcoded its path; its smoke hardcoded both the state path and URL; its
revocation step inherited an ambient `PYTHONPATH` that broke `pydantic_core`; and
the wrapper pre-created a state directory some fixtures require to be absent. See
`docs/browser-acceptance-findings.md`. All runs use generated TEST_ONLY fixtures,
not market data.

**Correction: the dashboard smoke was missed.** The paragraph above recorded the
hardcoded-Chromium defect as fixed in five smokes, but `dashboard-smoke.cjs`
still launched `/usr/bin/chromium` and so could never run — it had been silently
failing. It now uses the same resolver as the other seven. A second defect sat
next to it: `reviewed-inputs-browser-smoke.cjs` wrote
`browser: 'Chromium /usr/bin/chromium'` into its receipt even though it launched
through the resolver, a false statement in an evidence artifact. It now records
the real version.

All eight smokes now pass: the six above, the dashboard smoke, and the Source
quality smoke over real acquired archives.

**The 47 blocked partitions can now be imported.** All 47 were recorded as
`import exit 1` with no diagnosis. Reproducing two of them from the immutable
archives, sha256-verified before parsing, showed **two distinct provider defects**:

- **Exact duplicate block** — EURUSD October 2025: 1,494 rows re-emitted verbatim,
  one backward jump of −3,598.189 s. The duplicate carries no information.
- **Isolated out-of-order rows** — AUDUSD June 2026: 10 rows each exactly −1.000 s,
  visible in the raw CSV as a row stamped `172222000` appearing after one stamped
  `172223000`. The provider's timestamp is the record; the file order is an
  assembly artifact.

`factory/data/source_order.py` (`source-order-correction/v1`) corrects both
losslessly: an exact duplicate is dropped, out-of-order rows are stable-sorted by
the provider's own timestamp. **No timestamp, price, scale or instrument field is
rewritten**, `original_record_order` is preserved on every retained row, the raw
archive is untouched, and the receipt records each removed block's extent and the
duplicate's original position. A repeated timestamp with *different* prices is a
genuine re-quote and is preserved.

Wired into the checkpointed import path, with `original_record_order` uniqueness
replacing the consecutive-sequence requirement (a corrected stream is a
permutation). Verified end to end: **AUDUSD 2026-06 now imports with
`STRUCTURAL_IMPORT_PASS`, 1,723,025 rows, `readback_exact` true, 26 rows
reordered, no residual disorder.** See `docs/source-quality-findings.md` §7.

**C0 closed; `verify.sh` runs on this host; `main` is protected.** Three changes:

- **`PYTHONPATH` guard.** All 14 shell scripts that invoke the venv now clear
  `PYTHONPATH` first. `verify.sh` previously could not run on this host at all — it
  passed ruff check and format, then died loading the pytest conftest with
  `ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'`, because the
  ambient `PYTHONPATH` points at a Python 3.14 site-packages tree and shadows the
  venv's Python 3.12. CI is green because runners don't set it. `verify.sh` now runs
  bare end to end: ruff check, ruff format check, **679 tests passing**, Svelte check
  and the dashboard build.
- **Branch protection applied to `main`** (owner-authorized). Strict status checks
  on the four measured CI contexts (`audit`, `dashboard`, `python`, `verify`);
  force-pushes and deletions disallowed; `enforce_admins` false and no review or
  push restrictions, so owner maintenance is not blocked.
- **ADR 0070** records the owner's PUBLIC-repository decision, superseding C0's
  original private-repository expectation. The original blueprint text is preserved
  unchanged. **The ledger now shows 6 PASS / 61 NOT_TESTED / 0 FAIL.**

**Dashboard attestation check added.** Every report and action endpoint pins its own
attestation literal, and a panel sending a different string fails at runtime with
`422`, surfacing only as an alert after the user clicks — how the Research reports
panel shipped broken. `scripts/check-dashboard-attestations.py` compares the
literals in `apps/dashboard/src/lib/*.svelte` against every literal defined under
`factory/`, including inline `Literal[...]` definitions. Current result: **7 panel
literals, 19 backend literals, 0 unmatched.** `tests/integration/test_dashboard_attestations.py`
runs it and proves it fails on a deliberately mismatched panel, so it cannot pass
vacuously.

**Source scans no longer abort on a narrow requested window.** A retained
source-quality attempt failed with `SOURCE_QUALITY_EVENT_BUDGET` after 2,495 rows:
the policy asked for a 38-hour window over a monthly partition, and
`REQUESTED_PERIOD_MISMATCH` was emitted **once per out-of-window row** — 2,494 of
them, 1,048,486 bytes of events. The window mismatch is a property of the request,
not of each row, and its magnitude was already carried by
`counts.outside_requested_period_rows`. Per-row mismatch events are now bounded by
`max_examples`; the scan completes and reports the mismatch as a status plus a
count. Genuine per-row defects still emit per row and can still exhaust a
deliberately tiny budget. See `docs/source-quality-findings.md` section 6.

**Research reports panel fixed; seventh browser smoke added.** The panel rendered
and its controls worked, but **all three report actions returned 422** — each
endpoint pins its own attestation literal while the panel sent one generic string,
so every click surfaced only as an alert. Measured in real Chromium before the fix:
`Error: 422 ... Input should be 'Report a descriptive global candidate-selection
funnel only; ...'`. The panel now sends the matching attestation per action. The new
`research-reports-browser-smoke.cjs` asserts the actions are attestation-gated, all
three reports render, the funnel counts match the API, and the receipt records that
these are descriptive aggregates which do not qualify, rank or promote a strategy.
The Screen comparability panel's attestation was verified to already match its
endpoint. The existing source-quality smoke expects eight real historical scans
against a state directory absent on this host, so it cannot run here.

**`refresh` no longer reports a consistent catalog as inconsistent.** `factory.cli
refresh` re-verifies every partition's parquet digest against its manifest. It
reported `consistent: false` with three partitions "missing" — they were composed
views (`data/view-v1`), which by design have no `quotes.parquet` of their own.
`refresh` treated every manifest as a leaf. It now verifies a view through its
leaves and still reports a view with no parts or with a missing/mismatched leaf.
Real catalog: `verified: 134`, `mismatched: []`, `missing: []`, `consistent: true`.
See `docs/source-quality-findings.md` section 5.

**Source-to-restore rehearsal: all thirteen stages run over genuine acquired data.**
`scripts/source_to_restore_rehearsal.py` runs verify, catalog, admit, feature_cache,
generate, screen, native_replay, diagnose, independent_evaluation, improve, rank,
dashboard and backup_restore in one chain. Against the **real acquired catalog**
with a fresh scratch state root: **13 stages run, 0 blocked**, 318.4 s wall, 1.30 GB
peak RSS. The catalog stage composes 4 AUDUSD partitions into one 7,456,481-row
ordered view. Five genuine coverage gaps were closed, each found by measuring rather
than assuming: profile units (`price_scale=1000000`, not the fixture's `1000`),
timestamp precision (millisecond, not whole-second), calendar coverage (a declared
FX session replacing the 24/7 fixture), instrument identity (single-instrument
sample with the strategy instrument and `strategy_hash` recomputed), and
**idempotency** — `independent_evaluation` recorded an
`evaluation-with-past-only-warmup` use for the sampled window, which discovery then
treated as an excluded interval, so a second run failed its own diagnose stage; the
rehearsal now refuses a state root it would pollute. Only the **import** stage
remains unrun, blocked on the quarantine correction policy. See
`docs/source-quality-findings.md` section 4.

**T03 process-kill recovery tested against a real kill.** T03 recorded
"process-kill recovery pending". `test_T03_fenced_restart` rewound `lease_until`
by hand and `test_supervision` covered the kernel parent-death binding, so
neither killed a real process and then exercised recovery.
`tests/recovery/test_process_kill_recovery.py` now starts a holder process that
claims a job on a short lease, SIGKILLs it mid-job, waits for the lease to lapse
and verifies the next claim expires the lease, re-claims the same job and
records `LEASE_EXPIRED`. A second test asserts a claim while the recovered lease
is live returns `None`, so recovery cannot duplicate live work. Note the actual
design: **the lease does not self-transition on expiry** — expiry is evaluated
by the next claim, which is how a coordinator crash presents itself.

**Restore rehearsal added.** T22 records "migration/live process recovery
pending" and T23 records "full source/state/board production rehearsal pending".
`restore-test` only verified an isolated copy, so `factory.operations.rehearse_restore`
now restores a verified backup into a fresh root, opens the store read-write so
every migration applies, then reads every partition back out of the restored
catalog with `Catalog.verify`. It refuses a workdir that already exists or sits
inside the backup, cleans up after itself, and never touches the backup or any
live state root. Wired as `restore-rehearsal` with a
`scripts/restore-rehearsal.sh` wrapper; receipt `restore-rehearsal/v1`. Scope is
an isolated development rehearsal over a fixture state root, not a production
recovery claim — a production rehearsal over a genuine state root with stopped
services remains separate work.

**Staging budget is now operator-sized.** Nine partitions were blocked with
`staging payload budget exceeded` even after `reclaim-staging` cleared published
staging. Two causes were measured: published staging (reclaimable, 2.1 GB → under
200 MB) and retained prefixes for partitions that cannot succeed — `reclaim_all`
deliberately touches only published checkpoints, so 43 quarantined partitions
keep the partial prefixes they decoded (193 staging dirs, 1.8 GB, five largest
105–142 MB). That is resumability working as designed, not a leak, but it consumes
the budget. `scripts/acquire_history.py` now exposes
`--staging-budget-bytes` and forwards it to each import; the supervisor runs with
17179869184 (16 GiB) on this host, which has 75 GB free. The guard still bounds
growth and relaxes no data-quality check. `tests/integration/test_acquire_history.py`
pins the passthrough.

**T24 enforced soak (ADR0048 extended).** `scripts/enforced_soak.py` runs the
bounded synthetic soak inside a `systemd-run --scope` with `MemoryMax=8G`,
`CPUQuota=400%` and `MemorySwapMax=0`, and records the cgroup values the kernel
actually applied rather than the requested ones. Measured on this host:
`cpu_max 400000 100000` (4.0 CPUs), `memory_max 8589934592` (exactly 8 GiB),
`swap_max 0`. Run: 8 iterations x 50,000 rows, peak sampled RSS 559,689,728 bytes,
`within_limits` true, `oom_detected` false, `uncontrolled_swap` false, report
archived at `reports/soak/enforced-soak-report.json`. `factory/operations/soak.py`
now takes a `rows` parameter so the workload is sized explicitly. Scope is
unchanged: synthetic fixture only, not VPS equivalence, not historical validation
and not market validation.

**Two distinct source defects, not one.** `docs/source-quality-findings.md` now
records both. (a) 2025-10 duplicates a whole hour: the sequence reaches
`2025-10-27T00:59:58Z` then restarts at `00:00:00Z`, in three instruments at the
same UTC instant. (b) Many other months contain single ticks one second out of
order at a second boundary — measured in AUDUSD 2026-09 (row 120,721),
EURUSD 2026-08 (row 757) and XAUUSD 2026-07 (row 5,402). Both trip the same
monotonicity gate. 38 partitions across 11 months are quarantined. The gate was
not relaxed, no row was reordered and no timestamp was nudged.

**Budget lock restored to the documented fail-fast guard.** The previous
increment replaced the non-blocking payload-budget lock with a waiting lock.
`NEXT_ACTION.md` and the skill both record that lock as a deliberate fail-fast
guard, not a bug: concurrent imports must fail rather than queue so the budget
problem is visible immediately. It is reverted, the supervisor runs with a
single worker, and `tests/integration/test_import_resume.py` now pins the
fail-fast behaviour deterministically instead of asserting the reverted behaviour.

**C0 branch rules — measured, not applied.** `docs/branch-protection.md` records
that the repository is PUBLIC while C0 requires an authorized private repository,
that neither branch has protection, and the exact `gh api` call that would
require the four current CI jobs on `main`. Repository governance settings are
outside the standing authorization, so the configuration is left to the owner.

ADR0035 historical prospective calibration cohorts v2:
`historical-calibration-policy/v1` immutable typed policy bound to reviewed
admission, exact profile/dataset/code/training coverage and a literal no-pruning
flag; `historical-screen-cohort/v2` freeze/report; calibration members must carry
a retained ADR0034 posthoc diagnostic whose artifact/body hashes are reverified
against immutable audit events; prospective members must be unattempted queued
jobs under an approved-policy admission with a 24h post-calibration embargo,
subject equality, global effective-experiment dedup, canonical/quarantine/holdout/
training-scope and active-admission rechecks; deterministic pre-outcome selection;
fenced completion produces the historical diagnostic natively without mutating the
native artifact. CLI `historical-screen-cohort-freeze`, authenticated API
`POST /api/v1/research/historical-screen-cohorts`. Generated-only v1 is unchanged
and rejects a v2 request. Approximate historical pruning stays disabled and the
known profitable native counterexample/all-native fallback are preserved.

See docs/milestone-historical-screen-cohorts.md and ADR0035.

ADR0036 adds frozen screening comparability and selection-bias reporting:
`screen-comparability/v1` re-verifies cohort bodies, compares the frozen subject
contract pairwise with the exact differing fields, reports selection-bias
counters (distinct effective experiments, selected, observed,
selected-but-unobserved, unselected, selection ratio) and is content-addressed
and immutable. `pooled_claim_authorized` is always false; comparability never
authorizes pooling screening observations into a qualification, ranking or
performance claim. CLI `screen-comparability`, authenticated API
`POST /api/v1/research/screen-comparability` and a dashboard comparability panel.

Authenticated dashboard workflow for v2 is implemented and browser-verified:
`HistoricalScreenCohortsPanel.svelte` derives the immutable policy from the
selected calibration evidence, blocks incompatible selections and embargo
violations before submit, freezes, shows actual native feedback and exports the
exact cohort evidence. Playwright Chromium acceptance at 1280x900 and 390x844
froze before outcomes, preserved pause, observed 1 fenced native feedback,
disabled approximate pruning, exported byte-exact evidence, and reported no
mobile overflow or page errors.

## Historical data acquisition (owner-authorized, in progress)

`scripts/acquisition_watchdog.py` is a deterministic `no_agent` Hermes cron job
(`085932ae4c7b`, hourly, deliver origin) that prints only when the backfill needs
attention — supervisor not running, blocked partitions, low disk reserve, a
stalled completion count, or completion. Empty stdout means healthy, so the
scheduler stays silent. The scheduler copy lives at
`~/.hermes/scripts/acquisition_watchdog.py`; keep it in sync with the repository
copy when the watchdog changes. The watchdog does not import the scientific
stack, so it keeps running when the model or network is unavailable.

`scripts/acquire_history.py` is a bounded, checkpointed, resumable driver around
the existing `factory.operations.import_history` CLI. It never imports, parses or
scores data itself. It runs **sequentially by design**: `factory/data/resume.py`
takes a catalog-wide non-blocking payload-budget lock, so concurrent imports fail
fast rather than queue. Do not "fix" that lock to gain speed; it is a deliberate
budget guard.

State is on the protected persistent volume, not in the checkout:
`/var/lib/hermes-factory/{archives,catalog,backfill}`. Raw provider archives,
canonical Parquet/ZSTD datasets, receipts and checkpoint are retained. Progress is
in `/var/lib/hermes-factory/backfill/supervisor.log` and `checkpoint.json`.
Structural import is not calendar/source acceptance or DATA_READY.

## Exact next implementation

### Section 3 — Rust equity/drawdown (next engineering increment)

**Symptom to explain first.** The Rust engine's internal realized equity does not
always equal the Python reference's `self.equity`, even though fills, trades,
order states, flags and P&L match exactly on the whole parity corpus. A probe
comparing per-trade `equity_after` values across 80 generated cases found value
divergences and, in some configurations, a different number of closed trades
(Rust closes via `SAFETY_CLOSE` where the reference leaves an open position with
`NO_EXECUTABLE_EXIT_QUOTE`).

**Prime suspect.** The reference ledger computes the average-cost basis with a
Decimal division (`basis = self.cost / self.quantity`), which rounds to the
28-significant-digit context at every partial exit, then forms
`delta = (price - basis) * size * sign`. The Rust engine carries the same basis
as an exact rational. After any partial fill whose average cost is a repeating
decimal, the two deltas differ by a rounding residue, and `self.equity =
decimal_amount(self.account_cash_exact)` diverges from that point on. P&L parity
still holds because both sides' reported P&L comes from the same ledger math.

**How to confirm.** Reproduce case 11 from `random.Random(4242)` over 80
`generate_case_params(rng, "EURUSD")` draws with `conservative=True`; compare the
per-fill account delta as an exact rational against
`Fraction(delta_decimal) * Fraction(conv)`. If the residues trace to the rounded
basis, the fix is to make the Rust exit branch round the basis the way
`decimal_amount` does before forming the delta -- not to change the accumulator,
which caused the 800/800 -> 22/80 regression when attempted as a blanket
exact-accumulator change.

**Then.** Emit `equity_before`/`equity_after` per trade and a run-level
`ending_equity`, and port `factory/reporting/equity.py` (marked equity, peak,
minimum, max mark-to-market drawdown, insolvency flag, bounded display envelope)
with its identical rounding chain. Re-run goldens 240/240, direct parity 200/200,
restart/batch 120/120, genuine partitions 7/7 after every step, plus multiple
`--seed` variants.

### R07 — strict 50% post-cost win-rate gate (IMPLEMENTED and PASS)

Read this before writing code; it is the highest-priority unimplemented
requirement and the queue's `raptorbt_execution` task owns it.

Status: implemented this continuation and marked PASS. `ValidationCriteria.min_win_rate` defaults to 0.5; `win_rate_gate()` compares an exact Fraction of wins/completed_trades against `Fraction(minimum)`; the gate runs in both `qualify_forward` and `decide`, reporting `win_rate_gate_passed` and `min_win_rate`. Evidence: tests/unit/test_win_rate_gate.py, tests/unit/test_validation_statistics.py (direct decision/forward outcomes) and tests/integration/test_win_rate_qualification.py (end-to-end pipeline wiring). The notes below describe the original hook point and remain useful for changing the threshold.

**Where the gate belongs.**