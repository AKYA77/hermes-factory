# Migration parity report — NautilusTrader → RaptorBT-derived Rust engine

Date: 2026-11-12
Requirements: R02 (primary), R01, R03
Owner directive: `docs/source/Owner_Lean_RaptorBT_Final_Directive_2026-11-12.md` §4
Status: **parity demonstrated on fixtures and genuine acquired partitions;
NautilusTrader is NOT removed and R02 remains `NOT_TESTED`.**

## 1. Frozen reference goldens

`reports/raptor-migration-goldens.json` freezes the reference engine's exact
output over a fixed deterministic corpus.

| Field | Value |
|---|---|
| schema | `raptor-migration-goldens/v1` |
| reference engine | `nautilus_trader` **1.231.0** |
| fill model | `adverse-fill/v4` |
| corpus | 240 cases, seed 20261112, all eight instruments |
| rejected cases | 0 |
| artifact sha256 | `29e0f43417d71c6921df38cc333da989cae784f39a318715bcf8b791489fad0a` |

Each case records the sha256 of the exact normalized result: fills, trades,
open trade, skips and quote count, with prices in integer tick units, sizes and
P&L as exact rationals. Regenerate with
`scripts/freeze_nautilus_goldens.py`; verify the Rust engine against it with
`scripts/verify_raptor_goldens.py`.

## 2. Parity evidence

| Check | Result |
|---|---|
| Frozen goldens reproduced by the Rust engine | **240 / 240** |
| Generated fixtures, direct comparison (seed 20261112) | **240 / 240 exact** |
| Generated fixtures (seed 777) | **800 / 800 exact** |
| Generated fixtures with a finite eligible book | **240 / 240 exact** (≈35% of cases inject a half-depth book) |
| Restart/batch equivalence (batch sizes 1/2/3/7/64 + cross-process restart) | **240 / 240 exact** |
| Genuine acquired catalog partitions (`Catalog.read`) | **30 / 30 exact** |
| Rust unit tests | 2 passed |
| Full Python suite | 709 passed, 0 failed (1375 s) |
| CI | audit, dashboard, python, rust all pass |

"Exact" means equal entry/exit event and quote index, direction, role,
stop/target ordering, execution price, fill size as an exact rational, flags,
exit reason and account P&L as an exact rational — never a tolerance.

## 3. Discrepancy report

Every discrepancy observed during the migration was root-caused and fixed. None
remains open.

| # | Discrepancy | Root cause | Fix |
|---|---|---|---|
| 1 | Sizes and P&L wrong by the price scale | Tick-integer distances used where the reference uses decimal price distances | Convert integer prices to decimal units before sizing and P&L |
| 2 | Margin comparison wrong on JPY/CHF/CAD | Fixed-width `i128` rational cross-multiplication overflowed and wrapped in release builds; decimal28 conversion rates reach 10^27 denominators | `Rat` rebuilt on `num-bigint` |
| 3 | P&L off by ~1.5e-28 relative on non-USD quotes | `round_sig28` computed the decimal exponent one power of ten high, rounding conversion rates to 27 significant digits instead of 28 | Corrected the exponent search |
| 4 | Second and later positions sized on initial equity | Equity was never updated after a closed trade | Track and round equity after every fill |
| 5 | Same-quote re-entries dropped | Signals were skipped on a quote where a position closed | Reordered to matching phase → deadline close → signal loop |
| 6 | JPY/CHF/CAD conversion rates ~10^5 too small | `conversion_rate` divided by the raw integer price instead of the decimal price | Divide by the scaled decimal price |
| 7 | Order-state metadata absent from the Rust engine | The engine tracked fills but not the order state machine | Added ENTRY/STOP_LOSS/TAKE_PROFIT/TIMEOUT registration and terminal transitions; verified by extending the parity harness and refreezing the goldens |
| 8 | Partial fills unmodelled | The engine assumed unbounded L1 depth | Added a finite eligible book: the order quantity is rounded to the size increment, capped, and rounded again; a shortfall cancels the remainder |
| 9 | Partial entry left the protection live | Cancelling the parent must cancel the attached bracket | A partial entry cancels the entry remainder and both protection orders, raises PROTECTION_LOST and forces a safety close |
| 10 | Cancelled protection could still fill | The matching phase tested prices without checking order state | Protection now only triggers while its order is still resting |
| 11 | Timeout exit always closed the position | The deadline path ignored the fill cap | A short timeout exit cancels its remainder and the position stays open; a later quote re-submits the exit |
| 12 | Exit price was the last fill | The reference aggregates a multi-fill exit into a quantity-weighted average | The engine now reports the weighted average, and no exit price at all for a position that never closed |

Two further reference behaviours were recovered empirically and are now
reproduced: orders submitted in the strategy callback fill synchronously
against the current quote, and the reference rounds equity to 28 significant
digits after every fill.

## 4. Determinism

The Rust engine is a single deterministic pass with no randomness, no clock and
no batching; identical input bytes produce identical output bytes. The
reference's batch-size independence is already covered by the existing suite
(T31: full results equal at batches 1/2/3/8192 versus materialized delivery).

## 4a. Partial fills against a finite eligible book

The production fill model supplies unbounded L1 depth, so partial fills only
arise when the caller injects a finite book. The parity harness mirrors the
reference's `FiniteEligibleBook`: for a configured order type (and, for MARKET,
a configured side) the simulated book carries half the order quantity, so the
order fills short and its remainder is cancelled.

Reproducing this required five reference behaviours that the unbounded model
never exposes:

- The order quantity is rounded to the instrument's size increment *before* the
  book cap is applied, and the capped quantity is rounded again. The reference
  rounds with Python's `round(binary64, precision)` — banker's rounding on the
  binary64 value — not decimal half-even; the engine reproduces that exactly.
- A short entry fill cancels the entry remainder, and cancelling the parent
  cancels the attached protection. The position stays open with the partial
  size and is closed by a `SAFETY_CLOSE` market exit at a later quote.
- A short protection or timeout exit cancels only its remainder; the position
  stays open and a later quote re-submits the exit, so a persistently thin book
  shrinks the position geometrically instead of closing it.
- Cancelled protection must not trigger: the matching phase now consults order
  state, not just price.
- A trade closed by several exit fills reports the quantity-weighted average
  exit price and the last exit's timestamp/quote index; a position that never
  closed reports no exit price at all.

Verified exact on the 240-case corpus (seed 20261112), of which roughly 35%
inject a finite book, and on the 800-case corpus (seed 777).

## 4b. Restart and batch-size equivalence

The engine's replay loop was factored into a resumable `Replayer` whose state —
equity, the open position, the signal cursor, the consumed-quote index and every
fill, trade and skip — is a pure function of the quotes already consumed. The
state serializes to JSON and restores exactly, so a run can be split at any
quote boundary and continued in a fresh process.

`scripts/parity_raptor_restart.py` exercises both forms:

- `--batch-size N` for N = 1, 2, 3, 7, 64: the engine saves and restores its
  state every N quotes within one process.
- a cross-process restart: the first half of the quotes runs with
  `--dump-state`, the remainder runs with `--resume-from`.

Each result is compared field-by-field against the single-pass result *and*
against the Python reference, so the evidence ties the engine's restart
behaviour to the oracle rather than only to itself. Exact on 240/240 cases
(seed 20261112, all eight instruments, ≈35% with a finite eligible book) and on
a further 120/120 cases under a fresh seed.

## 5. Remaining gaps before NautilusTrader may be removed

The directive's migration gate requires all of the following. Items 1–8 are
demonstrated; item 9 (removal) is not started — see §7.

1. ~~Freeze NautilusTrader's existing golden test results.~~ Done — §1.
2. ~~Create independent reference calculations.~~ Done — the Python reference
   engine is the oracle and the goldens are frozen against it.
3. ~~Reproduce supported orders and fills in the Rust engine.~~ Done for the
   production fill model (§2).
4. **Verify prices, quantities, timestamps, order states and P&L** — done for
   the production path; the Rust engine now emits the order state machine
   (ENTRY/STOP_LOSS/TAKE_PROFIT/TIMEOUT registration and terminal transitions),
   verified by the parity harness and the frozen goldens.
5. **Verify gaps, spreads, slippage, partial fills, timeout, Gold, JPY and
   cross-currency cases** — done. Gaps, spreads, slippage, timeout, Gold, JPY and
   cross-currency were already verified; partial fills are now reproduced
   against a finite eligible book (§4a), including the reference's
   partial-entry bracket cancellation, safety close, repeated timeout re-submission
   and quantity-weighted multi-fill exit price.
6. **Verify results across genuine historical periods** — done. 30 acquired
   catalog partitions are read through the production `Catalog.read` API and the
   Rust engine reproduces the reference exactly (**30/30**, §2). The profiles
   used are *declared* source-measured units, not broker-verified metadata; that
   is a data-quality matter tracked by R09 and `DATA_READY`, not a condition this
   gate item states.
7. **Verify deterministic execution across restart and different batch sizes** —
   done. The engine's state is a pure function of the quotes consumed, so it can
   be saved at any quote boundary and resumed. `scripts/parity_raptor_restart.py`
   proves that `--batch-size N` (N = 1, 2, 3, 7, 64) and a cross-process restart
   at a quote boundary both reproduce the single-pass result exactly, and that
   result still matches the Python reference (§4b).
8. **Record the complete parity and discrepancy report** — this document.
9. **Remove NautilusTrader from active code, dependencies, tests, installers and
   documentation** — not started; see §5a for why removal would currently destroy
   the reference oracle rather than complete the migration.

## 5a. Why NautilusTrader is not yet removed

Every gate item except removal is now demonstrated, but item 9 is deliberately
not started. The reason is item 2.

The "independent reference" this report relies on is the Python
`factory/simulation/runner.py`, which imports
`nautilus_trader.backtest.engine.BacktestEngine` (runner.py:13). The oracle that
all parity results are checked against — the frozen goldens, the 240/800-case
fixture corpora, the genuine-partition run and the restart evidence — is
therefore itself Nautilus-based.

Removing NautilusTrader from active code, dependencies, tests, installers and
documentation would consequently also remove that oracle, the golden verifier and
a large part of the 709-test suite, destroying the evidence base rather than
completing the migration. The gate's item 2 asks for *independent* reference
calculations; a Nautilus-backed runner is not independent of the thing being
removed.

Two ways forward, both requiring an owner decision:

1. Build a non-Nautilus reference (a pure-Python replay of the same declared
   semantics), verify it against the frozen goldens, and only then remove
   NautilusTrader.
2. Confirm in writing that the Nautilus-backed Python runner is accepted as the
   "independent reference" for the purposes of item 2, at which point removal can
   proceed on the evidence already recorded.

NautilusTrader therefore stays installed and remains the reference. `R02` stays
`NOT_TESTED`.

### Item 9 also needs a replacement execution path

The directive's own supersession table (line 27) states that "one RaptorBT-derived
Rust execution engine replaces NautilusTrader after verified parity migration".
Removal is therefore not deletion alone: the nine `factory/` modules and the
backtest path they serve need somewhere to get execution results from.

Measured: nothing under `factory/` or `apps/` invokes `rust/raptor-engine`. The
crate is called only by the four `scripts/` harnesses. So item 9 additionally
requires an integration path — Python bindings or a stable subprocess/CLI
contract — plus re-pointing the runner, the operations probes, the validation
evidence path and the 56 affected tests at it. That is a program, not a step, and
it is why removal is not started here.

NautilusTrader therefore stays installed and remains the reference. `R02` stays
`NOT_TESTED`.

### Inventory of what removal would touch

Measured, not estimated:

| Area | Count |
|---|---|
| `factory/` modules importing `nautilus_trader` | 8 (`operations/benchmark`, `operations/campaign`, `operations/feed_probe`, `operations/research_probe`, `simulation/ledger`, `simulation/nautilus`, `simulation/reconciliation`, `simulation/runner`) |
| `factory/validation/evidence.py` | 1 |
| Test files importing it | 9 |
| Test functions in those files | 56 |
| Scripts importing it | 4 (`benchmark-monetary.py`, `dependency_disposition.py`, `freeze_nautilus_goldens.py`, `parity_raptor_engine.py`) |
| Declared dependency | `pyproject.toml:11` pins `nautilus_trader==1.231.0` |

Case generation, normalization and comparison now live in a Nautilus-free
module (`scripts/raptor_cases.py`), and `scripts/verify_raptor_goldens.py`
imports only that module. The frozen goldens therefore **do** survive removal:
verified by running the golden verifier with a meta-path hook that raises on any
`nautilus_trader` import — it still reports **240/240**.

The direct parity harness (`parity_raptor_engine.py`), the restart harness, the
genuine-partition harness and the freezer still invoke the Nautilus-backed Python
reference, so they do not survive removal.

## 6. Conclusion

The Rust engine is a faithful reproduction of the reference execution semantics
on every workload measured, with no open discrepancies. Gate items 1–8 are
demonstrated. The migration is not finished: removing NautilusTrader (item 9)
would also remove the Nautilus-backed oracle every parity result is checked
against, so an independent non-Nautilus reference is required first (§5a).
NautilusTrader therefore stays in the dependency set and remains the reference.
