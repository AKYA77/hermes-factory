# ADR 0071 — Lean RaptorBT execution, dynamic M1–D1, strict 50% gate

- Status: accepted
- Date: 2026-11-12
- Supersedes: the NautilusTrader matching-engine mandate in `AGENTS.md`; the
  "do not replace NautilusTrader with … RaptorBT" instruction in
  `docs/source/Completion_Directive_2026-11-03.md`; the conditional RaptorBT
  evaluation language in `docs/source/End_to_End_Completion_Mandate_2026-11-03.md`
  and `docs/source/Optimization_Handoff_Amendment_2026-11-03.md`
- Owner authority: explicit owner master directive, 2026-11-12
- Recording document: `docs/source/Owner_Lean_RaptorBT_Final_Directive_2026-11-12.md`

## Context

The project's execution path is built on NautilusTrader 1.231.0. The matching
engine, order state machine, partial fills, cancellations, deadlines, FX
conversion and money accounting all run inside a Python native engine, and the
quote replay path materializes Python row objects. The owner has decided that
this is heavier and slower than the research requires, and that a single
RaptorBT-derived Rust execution engine with exact bid/ask semantics is the
correct target.

Prior directives explicitly forbade replacing NautilusTrader with RaptorBT. The
owner's new directive reverses that decision. Both texts are retained: the old
one as history, the new one as authority.

The catalog at directive time holds 182 partitions covering 2025-01 through
2026-10 for all eight instruments, all still flagged
`STRUCTURAL_PASS_CALENDAR_REVIEW_REQUIRED`. No partition is source-accepted, so
`DATA_READY` remains false. The 24-month window requires 2024-11 and 2024-12.

## Decision

1. **One RaptorBT-derived Rust execution engine** replaces NautilusTrader after
   a verified parity migration. Indexed and sequential quote replay are two
   algorithms inside that one engine.
2. **Exact bid/ask semantics** are the contract. No last-traded-price
   substitution, no manufactured events, no silent representation conversion.
3. **The pessimistic cost scenario is preserved exactly**: 2-pip minimum
   effective spread, wider observed spreads preserved, separate 2-pip adverse
   slippage on market and stop-market fills, outward tick rounding, distinct
   limit behaviour.
4. **Dynamic M1–D1 timeframe selection** replaces the blanket M1 signal loop.
5. **One accurate testing pipeline** replaces the approximate-candle screen
   followed by a second full backtest. Approximation may not prune candidates.
6. **An absolute 50.00% verified win-rate gate** applies per instrument for
   qualification. Rejected candidates stay in the evidence database.
7. **A native Rust strategy generator** with a typed declarative grammar is
   added, preserving Optuna and the nine strategy families.
8. **TickFirstHitIndex** is permitted only with proven equivalence to
   sequential replay, and only where it measurably helps.
9. **New acceptance requirements R01–R12** are added to the ledger. The existing
   67 requirements are untouched.
10. **The Rust toolchain is pinned** (`rustc 1.100.0` / `cargo 1.100.0` at
    directive time) with a committed `Cargo.lock` and CI build.

## Consequences

- NautilusTrader removal is gated on parity evidence, not scheduled. Until the
  gate passes, Nautilus remains in the dependency set and its results remain
  the reference.
- Performance claims must be measured on the target 4-vCPU / 8-GiB envelope,
  not only on the larger development host.
- The data acquisition plan changes: only 2024-11 and 2024-12 are missing, so
  16 partitions are acquired rather than re-downloading 22 months.
- The architecture and handoff documents are updated so a future session cannot
  revert to the legacy design.

## Alternatives considered

- **Keep NautilusTrader.** Rejected by owner decision; it is the heaviest
  component and the least aligned with the throughput goal.
- **Approximate candle pre-screen retained as an authority.** Rejected: it can
  reject valid candidates and duplicates the accurate evaluation.
- **Indexed execution everywhere.** Rejected: equivalence must be proven per
  supported strategy class, with sequential replay as the fallback.

## Compliance

This ADR does not waive any existing acceptance requirement, does not change
repository visibility (ADR 0070), does not merge PR #1, and does not mark the
project production-ready.
