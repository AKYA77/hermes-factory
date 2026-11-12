# Milestone — RaptorBT-derived Rust execution engine and exact parity

Date: 2026-11-12
Owner directive: `docs/source/Owner_Lean_RaptorBT_Final_Directive_2026-11-12.md` (ADR 0071)
Requirements addressed: R01, R02, R03 (partial evidence; **no gate is claimed PASS**)
Commit: recorded below in `NEXT_ACTION.md`

## What was built

A from-scratch Rust execution engine at `rust/raptor-engine/`, derived to the
project's execution contract rather than adopted from a stock tick runner.

```
rust/raptor-engine/
  Cargo.toml          # pinned deps: serde, serde_json, num-bigint, num-traits
  Cargo.lock          # committed reproducible build
  src/lib.rs          # exact rational, pricing, sizing, ledger, sequential replay
  src/main.rs         # CLI: JSON request -> exact JSON result
```

`scripts/parity_raptor_engine.py` generates deterministic fixtures, runs the
Python reference (`factory/simulation/runner.replay`) and the Rust engine on
identical inputs, and diffs fills, trades, exact P&L fractions, skips, trade
counts and open trades.

## Measured parity

| Corpus | Result | Wall time |
|---|---|---|
| 100 cases, EURUSD, seed 20261112 | **100 / 100 exact** | — |
| 240 cases, all 8 instruments, seed 20261112 | **240 / 240 exact** | — |
| 800 cases, all 8 instruments, seed 777 | **800 / 800 exact** | 29 s |
| 30 genuine acquired catalog partitions | **30 / 30 exact** | 29 s |
| Frozen Nautilus goldens incl. order states | **240 / 240** | — |

The last row reads real published partitions through the production catalog
API (`Catalog.read`) over a bounded quote window, using the project's
`declared_tick_profile` (units measured from the source stream) and real signal
timestamps. It is genuine acquired historical data, but **not** a verified
broker profile — the partitions remain
`STRUCTURAL_PASS_CALENDAR_REVIEW_REQUIRED`.

"Exact" means equal entry/exit event and quote index, direction, role,
stop/target ordering, execution price in integer tick units, fill size as an
exact rational, trade flags, exit reason, and account P&L as an exact
`numerator/denominator` fraction — not a tolerance comparison.

Rust unit tests: 2 passed (`cargo test --release`).

## Reference semantics recovered and reproduced

The parity harness forced the following behaviours, each of which was wrong in
an earlier revision:

1. **A signal becomes eligible at the first quote strictly after
   `available_at`**, and the entry order fills on that same quote.
2. **Take-profit fills at the counterparty price** (the effective bid for a
   long's sell limit, the ask for a short's buy limit), not at the limit price.
3. **A long's stop triggers on the effective bid, a short's on the effective
   ask.**
4. **Per-quote order of operations** is: matching phase (resting protection) →
   deadline close in the strategy callback → signal loop. Protection that has
   passed its deadline is already cancelled by the clock alert, so a quote can
   produce a `TIMEOUT` close rather than a stop fill, and a stop/target close at
   a quote still allows a new position to open at that same quote.
5. **Orders submitted during the callback fill synchronously** against the
   current quote, so a close updates equity before a new position is sized at
   the same quote.
6. **The reference rounds equity to 28 significant digits after every fill**,
   and that rounded value is what sizing uses.

## Defects found and fixed in the Rust engine

- **Units error in sizing and P&L** — tick-integer distances were used where the
  reference uses decimal price distances, making sizes and P&L wrong by the
  price scale.
- **Silently wrapping `i128` rational arithmetic.** The exact decimal28
  conversion rates produce denominators up to 10^27, so products overflow
  `i128`; in release builds Rust wraps silently and a margin comparison returned
  the wrong answer. `Rat` is now arbitrary-precision (`num-bigint`).
- **Off-by-one in `round_sig28`** — the `n < d` branch of the decimal-exponent
  search stopped one power of ten early, rounding conversion rates to 27
  significant digits instead of 28. This produced a 1-ulp difference that
  propagated into every exact P&L on non-USD quote currencies.
- **Equity was never updated after closed trades**, so every position after the
  first was sized on the initial 20 units of equity.
- **Signals were skipped on a quote where a position closed**, dropping
  same-quote re-entries.
- **`conversion_rate` divided by the raw integer price** instead of the decimal
  price, making JPY/CHF/CAD conversion rates ~10^5 too small.

## What this does **not** establish

R01, R02 and R03 remain `NOT_TESTED`. Parity now covers generated fixtures and
genuine acquired historical partitions, but not yet:

- Verified broker instrument profiles (the genuine-partition run uses the
  project's declared source-measured profiles).
- Partial fills and cancellation races (the production fill model supplies
  unbounded L1 depth, so fixtures never partially fill; the reference's finite
  book is test-injected).
- Safety closes after protection is lost.
- Fees/commission (the reference scenario is zero-commission).
- Determinism across restart and different batch sizes.
- The complete parity and discrepancy report the migration gate requires before
  NautilusTrader is removed.

NautilusTrader is therefore still present in the dependency set and remains the
reference engine.

## Evidence

- `rust/raptor-engine/` — engine source and `Cargo.lock`.
- `scripts/parity_raptor_engine.py` — the parity harness.
- Reproduce: `env -u PYTHONPATH .venv/bin/python scripts/parity_raptor_engine.py
  --cases 800 --instrument all --seed 777`
- Build: `cd rust/raptor-engine && cargo build --release`
- Unit tests: `cd rust/raptor-engine && cargo test --release`
