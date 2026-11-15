# Shared exact indicator reuse — NOT_READY

The canonical signal compiler now shares exact past-only moments/change/slope/
envelope/range primitives. Confluence shares groups without recursively rebuilding
them. Disk keys exclude threshold/stops/risk/direction and include canonical
source/profile/code/range/timeframe/lookback/formula and Decimal arithmetic
context. The underlying bar key also includes context. ADR0031 defines storage,
lock ordering, integrity checks and conservative adoption policy.

All nine categories on all seven timeframes have exact cached/raw decision and
prefix/future-suffix parity tests. Threshold/stop variants reuse entries. Tests
cover higher confirmations, precision changes, checksum/source corruption,
code/profile/lookback/range invalidation, restart, eviction and over-budget
failure. An actual child SIGKILL before manifest publication recovers exactly once.
Native training tests for both automatically cached categories compare complete
worker output with caching enabled/disabled, including exact-zero screening and
actual fills. Frozen evaluation in separate generated OOS states also matches
exactly. No historical qualification or favorable outcome is inferred.

The first test collection used a nonexistent Signal2 Python class (the contract
is Signal(version="2")); the failure is retained. The first native fixture used
an invalid OOS enum and a trend threshold that emitted no signals; corrected
fixtures use the real selection_oos role and an explicitly declared0.01 trend
test threshold. Production formula/threshold policy was not changed. Final tests
require nonempty native fills; empty activity is not treated as parity proof.

Final generated benchmark compares three threshold variants over20,000quotes:
bar-only vs indicator first-build vs warm reuse. Actual measurements, source
identity and digests are in the evidence manifest. Short lookbacks regress, so
automatic reuse is limited to mean-reversion/trend lookback≥64. This measurement
covers feature compilation only, with prewarmed bar cache and uncontrolled OS page
cache; it is not an independent target4-vCPU/8GB native throughput benchmark.

[Evidence manifest](../reports/milestones/shared-indicators/manifest.json) records
verification, resources and exact source identity. Parent full-system cache,
source invalidation, global scientific/scalability/release gates remain open.
All readiness flags remain false. Next executable stream: frozen scientifically
safe screening/audit/fallback, retaining the known profitable native counterexample
and keeping cost-horizon approximation unauthorized to prune.

Actual full verification:544passed/0failed/0skipped,390 third-party warnings; pytest184.0s. Lint/format/Svelte check/build passed. Wrapper188.984s wall/185.908s child CPU; maximum child-process RSS964,083,712B (not aggregate). Final tested sourcea502f6a49ac4ad7ea785526f4442946baaed168fa155f5bffb41dc3fc0349aac. Warm mean-reversion64:0.5247s→0.3001s; trend64:0.5102s→0.3254s. Indicator disk1,033,791B; cumulative benchmark process peakRSS217,518,080B.
