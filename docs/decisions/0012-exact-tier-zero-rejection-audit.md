# ADR 0012 — Exact Tier 0 rejection and deterministic native audit

The owner amendment authorizes a bounded screener before Nautilus. Production
research now uses `exact-zero-signals-audit/16/v1`. It shares exact cached bars
and the existing Decimal signal compiler. It can prune only a training hypothesis
with zero signals. A positive count always reaches Nautilus; there is no profit
estimate, approximate ranking, alternative matcher or validation promotion.

A SHA256 cohort selection over experiment identity and policy sends one hash
bucket in sixteen of the zero-signal contracts through full native replay. The
realized fraction is reported, not assumed to equal exactly 1/16 in small samples.
Native fills, trades, an open position or any generated signal contradicting a
zero-signal audit cause quarantine and FAILED_FINAL, never successful promotion.
The audit is a compiler/execution integrity check, not a profitability estimate.

Typed immutable screen receipts bind experiment/dataset/strategy/source revision,
publication policy, signal count/hash, decision and explicit SCREEN_ONLY status.
Receipts survive restarts and live under artifacts/screens, outside Git. A
screened-out completed job has no experiments row, native run ID or objective.
Persistent Optuna records PRUNED with the receipt's exact rejection reason and
actual worker CPU. Failed hypotheses and strategies remain registered. Only
verified native training artifacts can supply a numeric optimizer objective.

The existing fenced job/resource ledger and append-only audit preserve rejection
identity and accounting. The coordinator revalidates receipt bytes/hash and its
contract before completion; optimizer feedback repeats that check. Both normal
recurrence and durable-proposal recovery enable the same fixed policy. Explicit
legacy single-replay/campaign requests retain their full-replay behavior.

Research status distinguishes pruned jobs, passed native rejection audits and
failed jobs containing a false-negative error. Its observed fraction counts only
persisted job outcomes, not ad hoc direct worker probes. Full staged/approximate
screeners, richer rejection strata, indicator transforms and full-space research
coverage remain unfinished. No claim of full T17/C4 acceptance is made.

Verification includes actual supervised no-signal completion with no experiment,
restart-identical receipts, native audit of rejected signals, injected bad-screen
quarantine using the real compiler/engine, tamper/OOS rejection, and persistent
PRUNED feedback with no objective/run ID. No security check was disabled; fresh
pip/npm audits still fail on the findings in ADR 0007.
