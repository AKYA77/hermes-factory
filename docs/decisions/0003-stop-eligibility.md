# Stop eligibility correction

The 24-strategy synthetic campaign on the initial branch found engine rejections
in every run when a stop distance was already crossed at submission after the
pessimistic spread and adverse entry fill. An immediate stop could close a parent
before Nautilus activated its take-profit sibling. This was a real integration
failure, not a strategy loss to hide.

Before bracket submission, reject a long whose stop >= current effective bid, or
a short whose stop <= effective ask, as SKIPPED_STOP_LEVEL. This implements the
blueprint's infeasible-stop rule without altering spread, slippage, risk or 3R.
Both directions have regression tests. The campaign keeps those infeasible
strategies in its count, with zero trades and explicit skips; it does not silently
replace them with profitable or feasible candidates.

The campaign runs actual Nautilus quote replays, in small process-isolated batches
for import amortization. It is a test harness, not a change to production worker
isolation. Synthetic training data and software checks cannot grant historical,
OOS, WFO, VPS or OPERATION_READY acceptance.
