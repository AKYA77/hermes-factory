# Persistent native screen fallback — NOT_READY

Baseline published shared-indicator checkpoint:
`8ce57c9f2ab84bf77455ffe0d545c6f473a83e76`. This increment closes the failure
recovery gap identified during the next safe_screening cycle; it does not complete
that entire engineering stream or any broader readiness gate.

A deliberately broken screen is contradicted by actual native fills. The worker
retains its quarantined evidence, durably disables pruning and records one
immutable incident. Subsequent candidates use native replay. Previously completed
rejections receive separate linked native jobs, preserving their original rows
and receipts. Exact source/code/training scope remains mandatory; old-code
contracts are not rewritten. Recovery admits at most64jobs/300measured CPU seconds
and obeys pause, ordinary queue capacity and idempotency. Bounded in-flight work
may finish; no automatic reset occurs. ADR0032 specifies the engineering policy.

Focused tests exercise actual native fault injection, persistent breaker and
immutable incident, actual supervised recheck, pause/dedup/original-row preservation,
corrupt-state fail-closed behavior, stale-code rejection, unknown-policy rejection,
cost-shadow labels staying native-only, and both count/CPU admission budgets.
The profitable approximate-label counterexample still passes unchanged.

An authenticated actual Chromium desktop/mobile check shows the disabled alert
and finite budget status against a fresh generated/native fault-injection state,
preserves pause, and observes no page errors or390px overflow. An initial browser
harness used the wrong preinstalled Playwright module path; its failure is retained.
The first full run was deliberately stopped when review identified the missing
total recovery budget; that incomplete run is not counted as passed.

[Evidence](../reports/milestones/screen-fallback/manifest.json) records final
source, test results, resource measurements and browser proof. These are generated
software fixtures, not successful historical strategies or target-host acceptance.

Continue safe_screening with frozen calibration, preselected independent rejection
cohorts, confidence/false-negative tracking and selection safeguards. Cost-horizon
approximation remains unauthorized to prune. Recursive diagnostics, global
qualification, source/profile/data operations, full dashboard, installation/
restore/security and release acceptance remain in the complete durable queue.
SOFTWARE_VERIFIED, DATA_READY and OPERATION_READY all remain false.

Actual final verification:550passed/0failed/0skipped,400third-party warnings, pytest182.32s; lint/format/Svelte/build passed. Additional4queue tests passed, including a new final-ledger reconciliation regression added after full-suite collection. Wrapper186.863s wall/181.788s childCPU; maximum child-process RSS964,423,680B, not aggregate/target-host proof. Tested sourcea566eed517a77229d2c620e39fc0437778808e6c54af6f2e87ddbb5247015c98. The queue controller caught four unfinished parent gates losing coverage after shared-indicator scope completion; final reconciliation now explicitly covers all67requirements.
