# Classification of the 61 outstanding acceptance requirements

Owner authorization, 2026-11-11: the agent may choose experimental design,
prioritize remaining work, and run bounded experiments without per-task
approval. This document classifies every `NOT_TESTED` requirement in
`completion-ledger.json` against the seven categories the owner specified, so
that each can be routed to the correct acceptance procedure.

The point of the classification is to avoid wasting a market-research campaign
on a requirement that deterministic tests can settle.

## Category 1 — Missing implementation

Can be built and verified now, without market data.

| Req | Gap |
|---|---|
| T33 | Shared indicator transforms / append acceptance |
| T52 | Automatic orphan inventory and fenced QA |
| T53 | search/v3 legacy v1/v2 range option |
| T56 | Frozen calibrated shortlist policy, rejection cohorts, selection-bias integration |
| C3 | Finite-depth exact pricing, JPY/Gold monetary profiles |
| C4 | Durable automatic discovery, full-space CPU fairness |
| C7 | Full blueprint dashboard charts/actions/exports |

## Category 2 — Missing integration

| Req | Gap |
|---|---|
| T30 | Full vertical: the import stage was blocked on the quarantine correction policy, which now exists |

## Category 3 — Missing deterministic verification

Tests, no market data required.

T02, T06, T09, T11, T16, T20, T27, T28, T45, T47

## Category 4 — Missing genuine-data experiment

Requires running the real acquired catalog.

T12, T13, T14, T15, T17, T18, T19, T25, T34, T36, T39, T40, T41, T42, T43,
T48, T49, T51, C5, C6

## Category 5 — Missing VPS operational verification

Needs the target host rather than a scoped test.

T03, T21, T22, T23, T31, T35, C1, C8

C8 spans this category and category 7: its remaining work is "actual
VPS/fault/soak/CI/security release gates". It is listed once here rather than
twice, and its security-release element is routed through category 7 below.
Splitting one requirement across two buckets would misreport the ledger.

## Category 6 — Missing external authoritative reference

Cannot be self-certified; needs a reviewed external source.

T05, T08, T10, T26, T32, T37, T44, T46, T50, T54, T55, C2

## Category 7 — Missing release or security evidence

T29, C9

C8's security-release element is routed here; the requirement itself is counted
once, in category 5.

## Dependent requirement — not independently actionable

**T38 (Independent readiness states)** was omitted from the first classification.
It is the meta-gate: `SOFTWARE_VERIFIED`, `DATA_READY` and `OPERATION_READY`
must all be true, each established by its own requirements above. It has no
independent work item and cannot be worked in parallel with its dependencies —
it is satisfied when they are. Counting it as a separate workstream would
overstate the actionable backlog by one.

## Routing

Category 1 and 3 items are executed first: they are deterministic, bounded, and
do not consume the experimental budget. Category 4 items consume the authorized
CPU budget in staged batches. Category 5 needs host time. Category 6 is blocked
on external material and must not be self-certified. Category 7 closes last.

The highest-priority implementable item is **T56** (queue priority 30, task
`safe_screening`): implement the frozen calibrated shortlist policy and its
rejection-cohort accounting.
