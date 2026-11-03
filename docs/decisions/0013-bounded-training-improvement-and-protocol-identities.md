# ADR 0013 — Durable training improvement and restart identities

The blueprint §9.6 requires retaining and improving unsuccessful strategies;
§9.7 preserves intended fixed 3R and recalculates native risk for each stop.
This increment adds a bounded autonomous training round for explicitly registered
search regions. It does not change risk, costs, source data or independent
validation rules. Original C4/C5 and T13–T18 remain incomplete at full scope.

An immutable improvement policy references an existing authorized training search
protocol. Registration does not resume paused research. Defaults permit at most
eight parent plans, four children per parent and 300 worker CPU seconds, with
admission additionally limited to a quarter of the region's measured search CPU
(one initial second permits a first measurement). Budgets are soft checks between
jobs; one job can overshoot. Only one improvement job is active at once within the
existing two-job admission buffer and single-heavy-worker lock. Active policy
capacity is 128; disabling preserves all historical policies and evidence.

The offline coordinator discovers actual verified native training results from
that region. It reads no OOS/holdout results. Each immutable plan records parent
artifact identity, measured diagnostic tags/counts, training metrics and the
reason to mutate or retain. Empty closed-trade sets are retained without inventing
an economic diagnosis. Fixed-size stop/context/confirmation hypotheses prioritize
FAST_STOP, FAVORABLE_THEN_STOP and TARGET_NEAR_MISS evidence. These are testable
questions, not proven explanations. All child strategies, changed fields and
multiple-parent experiment edges persist, including reused specifications.
Plans and their edges commit atomically; restart cannot lose an unsubmitted child.

Children inherit the exact parent dataset, spans, engine/source revision, cost,
seed, equity and risk contract. Only strategy identity changes. Stop variants
retain the intended 3R target and go through the native sizing/fill ledger.
Result feedback rechecks artifact hashes and frozen contract equality. Paired
reports retain the entire trade sets, counts, shared/unshared filled signal keys,
Wilson intervals, balance drawdown and equity delta. Shared entries are a
descriptive comparison, not a paired significance test. Samples below the policy
minimum of 50 closed trades, excessive count reduction, open/censored positions
or inconclusive paths prevent a claim of training improvement. Qualifying gains
receive only TRAIN_IMPROVED_ONLY; negative and inconclusive hypotheses persist.
No experiment or leaderboard is promoted to VALIDATED by this subsystem.

This is one bounded round per parent/policy. Recursive descendant expansion,
complete regime/session cohorts, learning-based diversity/stopping and independent
OOS/WFO confirmation remain work. Disabled regions/policies admit no new children;
queued jobs retain normal explicit cancellation controls. Corrupt or stale parents
block and disable their policy with an append-only reason; they are not rebased.

A restart test exposed numeric default identity drift: a float CPU-budget field
had an integer default, and JSON reload changed its fingerprint. New search/v2
protocols normalize that field. Legacy search/v1 lookup restores the original
serialized number representation, verifies its original hash, and preserves all
existing IDs. No old protocol/result is rewritten. Improvement/v1 uses a float
default and verifies JSON round-trip identity in tests.

Worker CPU now has an explicit originating trial or improvement-edge identity in
new queue payloads. Reused exact jobs are charged once across multiple protocols
or parent policies. Legacy pending jobs use their earliest matching trial as a
deterministic owner. Existing immutable historical outcomes are retained; their
older accounting is not retroactively rewritten. The attempt-resource ledger
remains the authoritative measurement, and tests check conservation against it.

SQLite migration 004 stores immutable policies, plans, edges and outcomes, with
separate enable controls. The wheel includes the migration. Authenticated APIs,
CLI policy registration/status/disable, dashboard counts, policy controls, paired
child evidence and cancellation all use those components. Full browser/target-host
acceptance is separate from the scoped tests and local UI rehearsal.

Completion-boundary follow-up: the registry now verifies the worker result's
canonical checksum and rejects execution integrity errors before completing an
experiment. A repeated experiment identity must match the previously stored
contract/result/checksum exactly; conflicting completions fail explicitly.
Failed attempts retain their strategy and normal fenced job error/resource path.
Tests inject modified worker output, integrity failures and an idempotency conflict
and verify that the original stored experiment survives unchanged.
