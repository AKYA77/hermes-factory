# ADR0029 — Versioned declarative families and shared causal entry compiler

Status: implemented development hypotheses; not software or market readiness.
Authority: blueprint §§2.3/7/9.6 and final completion request §§4/6/7.

Signal version1 retains its three operators, serialized fields and arithmetic.
Signal version2 explicitly adds trend, reversal, range, volatility, session and
confluence. New operators reject version1. The same past-only compiler supplies
screening and Nautilus order proposals; no alternate execution or P&L engine is
introduced. Risk, stop search, initial3R target, execution4 and validation
thresholds are unchanged. The new definitions are research hypotheses, not claims
of market efficacy or broker specifications.

All formulas consume n already closed historical bars and the current published
closed bar. No current unclosed candle or future higher candle is visible.

- trend: least-squares slope of prior closes, normalized by prior mean absolute
  one-bar close change; current close must continue in the slope direction.
- reversal: a current close move opposite the prior endpoint trend, at least
  threshold times the prior mean absolute change.
- range: a bounce inside the prior low/high envelope, within an edge zone of
  span*threshold/(2*(1+threshold)); current close must move away from that edge.
- volatility: current closed-bar range at least threshold times the prior mean
  range, with direction given by current versus previous close.
- session: the original normalized momentum hypothesis, admitted only at an
  explicit unique set of UTC publication hours. Publication time handles sparse
  delayed observations. These are time-of-day hypotheses, not market calendars.
- confluence: two or three distinct, non-nested registered operators must all
  emit the same nonempty side. They share the declared lookback and threshold;
  session components require explicit UTC hours. No arbitrary executable code,
  recursive expressions, contradictory-side vote or hidden best-component
  selection is accepted. Component/hour ordering has commutative canonical IDs.

Existing mean-reversion/momentum/breakout definitions move into the common pure
interpreter with unchanged operations/order. Legacy Signal JSON omits the newly
introduced empty fields; original strategy hashes remain. Session hours reject
bools, floats, out-of-range and duplicate values. Each history remains <=500bars;
confluence has at most3components. Existing higher-timeframe queues still require
both end_ns and available_at eligibility, and native execution remains strictly
later than signal publication.

Search/v5 explicitly carries these families/components/hours and emits Signal2.
Earlier search versions reject the new semantics, retain their old serialized
shape/IDs and sampling ranges. v5 retains the declared-pip stop distribution and
bounded durable TPE objective/CPU accounting. Synthetic inputs may use the exact
zero-signal screen; historical inputs still require reviewed admission and do
not inherit synthetic screening. Approximate pruning remains disabled.

Scientific-validation/v4 propagates the new fixed family definition through
strictly prior-only Search/v5 refits and existing independent evaluation stages.
Legacy scientific v1/v2/v3 IDs/refit versions remain unchanged; no holdout or
qualification criterion is relaxed. Existing neighborhood and improvement
proposals perturb shared lookback/threshold/stop values under the same contract.
Historical promotion remains disabled pending global/regime/source requirements.

Coverage initialization additively records all nine family categories across
8instruments/7timeframes, preserving existing counters. This does NOT implement
automatic discovery/registration of new eligible regions, full-space allocation,
shared indicator transforms, calibrated shortlisting, recursive diagnostics or
the complete graphical family editor. Those remain explicit C4/C5/C7 gates.

Evidence: independent hand arithmetic, exact legacy JSON/hash, seven-timeframe
future-suffix causality with nonempty signals, sparse higher-bar publication,
all six new categories producing actual native fills, durable v5 proposal/restart,
actual no-network supervised session worker feedback and v4 prior-only refit
propagation without holdout consumption. Fixtures are generated, never historical
market evidence. A first reversal fixture lacked a large enough reversal at its
frozen threshold; the activity assertion failed7cases and is retained. The fixture
was corrected to include the declared boundary; no scientific threshold changed.
