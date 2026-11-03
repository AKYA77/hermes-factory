# Hermes operating contract

Current status NOT_READY. No approved release/tag exists. Do not take over
production operations or rewrite this partial system as if C9 were complete.

At the eventual approved handoff: verify exact immutable tag, release manifest,
build/acceptance/benchmark reports and BLUEPRINT source hashes; run doctor,
install, verify in that order; inspect target-host results. Use the Factory API
and durable scheduler. AI absence must not stop deterministic research.

Read BLUEPRINT.md, CODEX_BUILD_PROMPT.md, docs/decisions, scientific gates and
known limitations before changes. Preserve failed experiments and source data.
Hypotheses are typed proposals, not executable strings or claimed metrics.
Evidence claims require actual run/evidence IDs. Core calculation, risk, data,
validation and ranking changes require versioned decisions and owner-approved
release review. Work on branches and PRs; maintain rollback evidence. Never
change holdout independence or fabricate wins, CPU/RAM values or test results.

Use hosted Nous models only when owner authorized, actual catalog and quotas
verified; no paid inference or local models by default. Do not disclose secrets,
expose public endpoints, place brokerage orders or enable real-money trading.


The owner's final amendment separates SOFTWARE_VERIFIED, DATA_READY and
OPERATION_READY. After a genuinely tested software handoff, Hermes acquires and
verifies the remaining source partitions on Contabo. Preserve the eight January
2025 real imports; do not redownload them gratuitously. Do not interpret the
acquisition sequencing change as acceptance of this NOT_READY checkpoint. Use
`hermes-factory --state /path/to/state catalog-compose HASH...` to create ordered
same-instrument multi-period views without copying or rewriting canonical quotes.
`hermes-factory --state /path/to/evidence readiness --evidence gates.json` checks
explicit gate receipt hashes; it does not run tests or authorize operations.
See ADR 0011 and the source amendment before preparing the final handoff.
