# Profile-aware stop search, without changing execution mathematics

Status: implementing search/v3; historical profiles remain unapproved.

The universal legacy 20..200-tick sampling range can be entirely infeasible for
Gold when a declared 0.001 tick coexists with a 0.1 pip. Source decimal precision
cannot establish pip size. Search/v3 samples in exact declared pip increments,
with a lower bound that accommodates the conservative minimum spread, entry
slippage, one possible outward rounding tick and the declared stop-level minimum.
This changes parameter proposal coverage only. It does not change spread or
slippage, exact 1:3 intended distances, risk sizing, fills or matching ownership.

Let P = declared pip_size / tick_size, an exact positive integer, and M be the
minimum stop in ticks. In the pessimistic scenario F = M + 4P + 1; in reference
F = M. L = ceil(max(2P, F) / P) * P. H = max(20P, L + 18P), capped at the
StrategySpec maximum 1,000,000 ticks and rounded down to the L + kP grid. Empty
ranges reject. Pessimistic lower bounds account for a two-pip spread floor and
two-pip adverse entry execution plus at most one tick of outward rounding.
Actual wider observed spreads, gaps, execution restrictions, volume and margin
remain checked per entry. The range does not guarantee every proposal executes.

New standalone searches default to search/v3; its schema makes identities distinct.
Explicit legacy v1/v2 retain their exact former distributions, JSON and hashes.
Existing scientific-validation/v1 and v2 protocols explicitly continue creating
search/v2 refits: changing a new default must not change an unfinished frozen
scientific protocol. A future scientific protocol version must explicitly opt
into v3 before profile-aware refits are used in that workflow. Those existing
protocols retain their known Gold coverage limitation; no migration rewrites
trials, failed hypotheses, results or consumed holdouts.

Synthetic Gold with declared 0.001 tick and 0.1 pip now samples 500..2300 ticks
in 100-tick increments. This is a software fixture, not an assertion about any
broker's Gold convention. Authoritative execution remains NautilusTrader.

Verification: full scripts/verify.sh passed 302 tests, zero failures/skips,
348 warnings, 82.08s pytest time, plus lint/format and frontend check/build.
Actual native Gold BUY/SELL goldens at both bounds preserve exact 3R and modeled
risk <=$2. Legacy identity/range and optimizer restart tests pass. Evidence:
reports/milestones/2026-11-04-source-recovery-search/manifest.json.
