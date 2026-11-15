# ADR0068 — Failed-child lineage preservation

Status: implemented software scope; T13 full acceptance open.

## Problem

T13 requires that an improved child records exactly what changed and that parent
and failure history are preserved. The lineage registration was tested — a child
carries `parent_id`, non-empty `changed_fields` and a hypothesis — but nothing
verified what happens when the child **fails**: whether the parent experiment
survives and whether the recorded change remains readable.

## Decision

`tests/integration/test_improvement.py` gains
`test_T13_failed_child_preserves_parent_and_lineage`:

- run a parent search cycle and let `Improvement.discover()` commit a plan and
  its child edges;
- record a `FAILED_CHECKS` outcome for one edge;
- assert the parent experiment row is unchanged, the child's `parent_id`,
  `changed_fields` and `hypothesis` are intact, and the outcome is retained as
  `FAILED_CHECKS`.

## Safeguards

- The failed outcome is never rewritten to an improved status; the test asserts
  the stored status directly.
- The parent row is compared for equality, so a failure that mutated or dropped
  parent evidence fails.
- `changed_fields` must be non-empty, so a child that records no change fails.
- These are synthetic fixtures; no market claim is made.

Evidence: docs/milestone-historical-screen-cohorts.md.
