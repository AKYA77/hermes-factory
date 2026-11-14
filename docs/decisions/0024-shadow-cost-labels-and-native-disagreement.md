# Cost-aware feature labels and shadow native calibration

Status: implemented shadow estimate/audit foundation, NOT full Tier0 acceptance.
Authority: owner completion mandates require genuine lightweight cost-aware
screening, reuse of closed features and independently audited rejected candidates.
No financial execution or validation defaults are changed.

cost-horizon-labels/v1 computes fixed-horizon differences of already observable
closed midpoint features for causally generated training signals. One bounded
queue holds at most horizon_bars labels; exact rational sums/variance avoid
summation drift. Only training features may be read. Labels beyond24h elapsed
or sample end are censored, never converted into fictional exits. All three
current operators share the existing interpreter and feature cache.

The explicit hypothetical two-market round-trip proxy subtracts6pips in the
pessimistic scenario (2spread +2entry-market +2exit-market),0in the reference
label convention. This is NOT the cost of every native trade: a TP limit exit
has different costs, actual spreads can be wider, feature closes are not fill
prices, and no risk sizing/SL/TP/positions are simulated here. Mean plus a declared
multiple of population dispersion is a research score, not an IID confidence
interval. Insufficient or overly censored samples cannot suggest rejection.
Every estimate explicitly has pruning_authorized=false.

Explicit search/v3 protocols opt in through research_kind =
synthetic-cost-shadow-training/v1. This kind is already part of both protocol
and experiment identity, so cached ordinary and shadow runs cannot collide.
Ordinary protocols retain the existing cheap screen. In shadow mode the
training worker reuses the estimate's exact signal count/digest to construct
the original exact-zero-screen receipt, avoiding a duplicate feature pass. Its
actual rejection/audit rule is unchanged. A broken exact-zero receipt still
contradicts the real compiler/native replay and is quarantined; the fault test
continues to inject at screen for ordinary mode and also tests from_summary
in shadow mode, preserving both native contradiction checks.

Migration010 records immutable shadow cost/native audits only within official
completion, under its fencing/transaction checks. A cost label is never counted
as a native trade. All native survivors of the exact-zero screen supply measured
feedback; artifact hash, complete experiment/source/profile/window/operator/scenario,
label and trade counts, marked equity and prospective false-negative disagreement
are retained. Shadow scores cannot prune, replace a native objective or validate.

A genuine Nautilus synthetic counterexample proves this safeguard is necessary:
a slowly rising path scores-5.5pips under the five-bar label proxy, yet its native
strategy completes a profitable3R target and has positive final marked equity.
The candidate and disagreement remain recorded. This is a generated software
fixture, never a historical performance claim. No fake fills or monetary metrics
are submitted. Before actual cost-based pruning, implement/freeze the calibrated
policy, ongoing independent rejection audits, fallback/recovery and explicit
selection-bias accounting; those mandatory funnel requirements remain open.

Initial full verification334passed/zero failed/skipped,358 retained third-party
warnings,83.25s pytest, plus lint/format/Svelte check/static build passed before
adding the explicit opt-in regression; final opt-in verification follows. A focused first
attempt exposed the old fault-injection function name; it was updated to the real
new boundary and rerun. Raw failure and successful logs are preserved. A separate
feature-only benchmark measures extra estimator overhead; it must never be
reported as native tick throughput or a compiled-screening acceptance proof.

Measured feature-only benchmark:200,000generated multi-quarter M1 bars per
operator. Momentum cost labels6.243158s vs2.013757s exact screen; mean reversion
7.407512s vs2.443130s; breakout5.968682s vs1.814245s. Peak process RSS51,396,608B;
queue at most5labels; compiler signal digests/counts match. This adds3.03–3.29×
cheap-stage work and is not a speedup. The shadow phase is opt-in to collect
calibration without imposing this overhead on existing protocols. Zero native
replays were benchmarked; no market or compiled-screen throughput is claimed.

Final opt-in verification:337passed,zero failed/skipped,362warnings,89.94s;
Ruff lint/format,Svelte check and static build pass. An actual persisted TPE→
supervised worker→native objective/audit test passes for the new research kind.
Ordinary training is separately checked to retain its original screen and no
shadow metadata. Exact-zero false-negative guards pass in both modes.
