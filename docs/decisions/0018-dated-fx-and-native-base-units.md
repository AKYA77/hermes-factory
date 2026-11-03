# Execution v4: dated FX, native base units and exact risk feasibility

Status: scoped software verification passed; not complete release readiness.
Authority: blueprint sections 6.3, 8 and 9; owner monetary-correctness directive.
The original $20, 10%, intended 1:3, minimum two-pip effective spread and eligible
two-pip adverse adjustment remain unchanged. Matching remains in Nautilus.

## Dated quote-to-USD conversion

USD-quote instruments use identity conversion. USDJPY, USDCHF and USDCAD derive
quote-to-USD from the same dated effective executable quote. A SELL fill uses the
inverse ask (quote/USD BID); BUY uses inverse bid (quote/USD ASK), matching the
pinned native account's fill-side policy for gains and losses. No midpoint or
extra slippage is added to this conversion. The raw source quote stays preserved;
conversion explicitly uses the declared effective spread-floor quote. Reciprocal
research rates use Decimal precision 28 / HALF_EVEN, separately from native
binary64/currency Money. Native rate behavior is checked independently.

A supported-API native probe confirmed protective fills see the previous main
cached quote because exchange matching precedes main data-cache processing. The
adapter now registers an auxiliary non-traded instrument for the same currency
pair, then feeds an exact copied effective quote immediately before each main
quote, at the same time. The context instrument is registered last so the pinned
cache pair map uses its current quote. It receives no orders/signals. Batches do
not pre-populate cache. No event is moved earlier in source time; equal-time
source order is preserved. Actual fill conversions include context bid/ask/time
and source identity; replay checks them against the exact source quote index.
Both actual main-quote counts and native iteration counts must match, including
the three additional context feeds. This is an engine integration adapter, not
another matcher, new canonical data or learned strategy signal.

## Profile volumes versus native base units

Contract multipliers describe base units per profile volume. Native CurrencyPair
quantities, increments, fills and ledger inventory are base units. Sizing still
computes profile volume and includes the multiplier once. Orders multiply that
volume once; ledger P&L/risk uses actual base-unit fills without a second
multiplier. Metadata retains requested profile volume, multiplier, base-unit
quantity and units policy. Native min/max are conservatively aligned to the
legal step; an empty or unrepresentable grid fails explicitly.

All eight synthetic instruments have native long/short stop and limit goldens.
The two synthetic Gold profiles (unit versus 100-unit lot) have identical actual
native fills, equity and economic risk. A separate synthetic 0.001 Gold grid
preserves the third decimal. These are declared software scenarios, not verified
broker facts. Historical admission remains blocked pending dated verified
profiles, calendars and the remaining scientific gates.

## Exact feasibility and reproducible account totals

A regression reproduced rounded theoretical size 10000 at a repeating conversion
boundary even though its exact modeled loss exceeds $2. Sizing now calculates
loss, step flooring, risk and margin feasibility with Fraction on the declared
finite Decimal inputs. It chooses 9999.999 in that case. No epsilon and no
above-budget rounding is accepted. Risk/margin receipts retain exact numerators
and denominators. Intended stop/target price distances are unchanged; gaps and
future FX movement can exceed initial modeled risk and can cause insolvency.

Account totals preserve exact rational sums of finite Decimal fill deltas and
declared conversion rates. A fixed precision-28 presentation is separate from
those immutable receipts. Trade, whole-run and statistical summaries consume the
same exact receipts, avoiding non-associative sums of rounded trade displays.
The independent native reference still checks each position in quote currency
and each account close after native quote-Money and USD-Money conversion. Native
position quote P&L is never subtracted from USD balances as though units matched.

Marked equity independently reconstructs actual base-unit inventory and realized
cash, marks open exposure at the current liquidation-side quote and converts
unrealized P&L with that same dated side. It checks cash/inventory invariants and
uses every quote/fill for drawdown; its bounded envelope remains display-only.
Extreme synthetic FX gaps explicitly report insolvency, not a fictitious capped
loss or closing fill. Synthetic training, search and validation workers may now
exercise all eight instruments; real profile admission stays closed.

New outputs require adverse-fill/v4 plus the actual source identity. Previous
v1/v2/v3 evidence remains readable; it is not re-executed or relabeled v4.

Verification: bash scripts/verify.sh — 259 passed, zero failures/skips, 322
recorded third-party warnings, 71.96 seconds; lint and dashboard check/build
passed. Includes actual supervised USDJPY training and protected confirmation.
Resource benchmark is separate and has not yet been claimed.
