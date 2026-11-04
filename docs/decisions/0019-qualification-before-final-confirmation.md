# Scientific protocol v2: qualification before final consumption

Status: scoped native/unit verification passed; browser verification of the new
v2 fields follows the code commit. Full C6 and SOFTWARE_VERIFIED remain open.
Authority: blueprint independent-evaluation, insolvency and robustness rules;
owner completion mandate. Native execution/risk/cost assumptions are unchanged.

The previous v1 synthetic protocol consumed its final observation even after weak
forward evidence and could base decisions on closed-trade balances without
requiring full marked valuation. V1 stored identities and reports remain readable;
new v1 execution/registration is explicitly read-only. Its fingerprint excludes
new v2 fields, and a restored legacy fixture verifies original identity preservation.
No historical result is retrospectively upgraded.

New scientific-validation/v2 defaults to research_qualification. Every forward
fold must satisfy the declared sample, confidence, economic and loss-run criteria
before final refitting or confirmation. The forward Holm gate reserves the final
test in its family before seeing it. A failed forward gate writes immutable
linked evidence and ends that protocol without freezing/consuming the final
window or running an unnecessary final refit. Final training and its predeclared
sensitivity neighborhood must also pass their gates before confirmation.

Native evidence admission now requires current execution/account-sum policies,
verified accounting, source/context counts, complete marked observations and
finite valuation. Unknown/malformed evidence fails closed. Any observed marked
insolvency always fails, even if ending balance is profitable. Profit/target
checks use the lower of the closed-trade balance and actual final marked equity,
so an open loss cannot disappear from qualification. Boundary-open inventory is
counted explicitly; it is not fabricated closed.

The v2 evidence policy requires explicit maximum censoring fraction, maximum
marked drawdown, minimum neighbor sample and minimum acceptable neighbor
fraction. There are no API defaults for those thresholds. They are preserved in
the protocol ID and exposed as visible editable UI inputs. Neighborhood acceptance
requires actual adequate native results, acceptable valuation and economic/loss-
run criteria; merely running several neighboring parameter sets is insufficient.
These controls do not correct all researcher discretion or complete regime/global
multiple-testing analysis. Real monetary/calendar admission remains closed.

A separate explicit synthetic_software_rehearsal purpose may exercise later
stages after weak forward evidence, solely to verify software integration. It
requires synthetic input and can never set independently_validated. A successful
rehearsal is not strategy certification. The default research path has no such
bypass; the GUI explains the distinction before registration.

Actual verification: bash scripts/verify.sh — 271 passed, zero failures/skips,
340 third-party warnings, 73.22 seconds, Ruff/frontend check/build passed.
An actual restartable native protocol with weak OOS ends with
INSUFFICIENT_EVIDENCE, no final refit, no selection and zero holdout consumption.
The explicit synthetic rehearsal still executes actual native later stages and
remains uncertified. A fault-injected native protection/close failure produces a
profitable final close after negative marked equity; validation rejects it.
Corrupt/unknown valuation, source counts and native reference states also reject.

An empty custom fill-book probe revealed another native fallback: an unshifted
quote fill violating the declared adverse adjustment. Existing execution checks
reject it, and the new validation quality gate also rejects that evidence.
Do not relabel it correct or claim complete finite-depth fidelity. The default
transparent unlimited L1 scenario is unchanged; real historical L2 liquidity is
not present in these sources. Security and remaining release gates stay red.
