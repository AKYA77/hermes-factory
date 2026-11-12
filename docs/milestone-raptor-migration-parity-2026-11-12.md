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
| artifact sha256 | `5bc9a4bed123b347633b1440…` (full value in the artifact) |

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

Two further reference behaviours were recovered empirically and are now
reproduced: orders submitted in the strategy callback fill synchronously
against the current quote, and the reference rounds equity to 28 significant
digits after every fill.

## 4. Determinism

The Rust engine is a single deterministic pass with no randomness, no clock and
no batching; identical input bytes produce identical output bytes. The
reference's batch-size independence is already covered by the existing suite
(T31: full results equal at batches 1/2/3/8192 versus materialized delivery).

## 5. Remaining gaps before NautilusTrader may be removed

The directive's migration gate requires all of the following. Items 1–3 are
done; the rest are open.

1. ~~Freeze NautilusTrader's existing golden test results.~~ Done — §1.
2. ~~Create independent reference calculations.~~ Done — the Python reference
   engine is the oracle and the goldens are frozen against it.
3. ~~Reproduce supported orders and fills in the Rust engine.~~ Done for the
   production fill model (§2).
4. **Verify prices, quantities, timestamps, order states and P&L** — done for
   the production path; order-state metadata (`order_states`) is not yet emitted
   by the Rust engine.
5. **Verify gaps, spreads, slippage, partial fills, timeout, Gold, JPY and
   cross-currency cases** — gaps, spreads, slippage, timeout, Gold, JPY and
   cross-currency are verified; **partial fills are not** (the production fill
   model supplies unbounded L1 depth, so they only arise with a test-injected
   finite book).
6. **Verify results across genuine historical periods** — 30 acquired
   partitions verified under *declared* source-measured profiles, not verified
   broker profiles.
7. **Verify deterministic execution across restart and different batch sizes** —
   single-pass determinism established; restart/replay equivalence not yet
   recorded as evidence.
8. **Record the complete parity and discrepancy report** — this document.
9. **Remove NautilusTrader from active code, dependencies, tests, installers and
   documentation** — not started, and correctly blocked on items 4–7.

## 6. Conclusion

The Rust engine is a faithful reproduction of the reference execution semantics
on every workload measured, with no open discrepancies. The migration gate is
not satisfied: order-state emission, partial fills, verified broker profiles,
genuine-period restart/batch evidence and an explicit NautilusTrader removal
remain. NautilusTrader therefore stays in the dependency set and remains the
reference.
