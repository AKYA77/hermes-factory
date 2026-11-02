# C3 increment: order-aware execution accounting v2

Status: implemented increment, not completion of C3 or production release.

The former adapter used the first fill as the whole entry and the second as the
whole exit. It could therefore close accounting on an entry remainder, attribute
a losing timeout to a stop, and mix a corrected run with old results.

Nautilus still owns all matching, contingent order lifecycle and account events.
A small TradeLedger now registers immutable entry/stop/target/close order roles,
consumes identified venue fills, deduplicates exact repeats, rejects conflicting
repeats/unknown IDs/side mismatches/overfills, and aggregates executed quantity,
cash, fees and weighted prices. Partial entry cancellation preserves actual
exposure. A cancellation intent does not erase fills that win a cancellation
race. Only flat inventory with terminal entry can become a completed trade.
Terminal events remain in its trace and admission waits for related order cleanup.
Loss of protection schedules an identified reduce-only SAFETY_CLOSE on an actual
subsequent quote, not a stop-loss classification or invented stale fill.

Intended stop and 3R target remain anchored to the original modeled entry and
legal tick distance. Reports distinguish intended entry/distance, requested risk,
modeled stop risk for the actually filled quantity, and realized net R. Native
StandardMarginModel now implements the profile's notional × margin_rate; the
previous default LeveragedMarginModel divided that rate by leverage again.
Stop-level eligibility is checked against the current liquidation-side quote.
These correct accounting/feasibility, not search targets or cost assumptions.

A timer cancels protection at the holding deadline without submitting a market
close against stale quotes. Exact-deadline quotes may execute protective orders
on the deadline (Nautilus processes equal-time data before timers); otherwise the
strategy closes from that quote. Later quotes produce a flagged delayed timeout.
Quote indices, not timestamps alone, bound forensic paths with equal-time ticks.
Per-point entry basis uses only entry fills available at that point.

The producer/consumer execution contract is adverse-fill/v2. Legacy v1 inputs
are rejected for new execution/evaluation; their stored evidence remains readable.
Default leaderboards filter by execution version, with an explicit read-only
legacy view and no legacy independently validated view. Dataset/fold comparisons
still need the full C6 protocol. Strategy identities are not rewritten.

## Important observed engine limitation

Supported synthetic fill-book fixtures produce genuine multi-event Nautilus
fills and IOC cancellation races. Under an exhausted L1 book, Nautilus can fill
a GTC remainder one extra tick away, or cancel partially activated protection.
The ledger records actual events; it never rewrites their prices to make a test
pass. Each eligible fill is checked against the declared two-pip adjustment and
limits. A discrepancy, unexpected commission or engine rejection is an integrity
error and cannot become a completed official experiment through the worker.
Default unlimited L1 quote-profile tests retain the exact floor/slippage rules;
finite-liquidity fidelity and actual broker restrictions remain a C3 release gate.
IOC and limited-depth fixtures are engine integration tests, not newly enabled
strategy-spec order types or historical evidence.
