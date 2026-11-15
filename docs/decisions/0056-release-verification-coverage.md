# ADR0056 — Release manifest verification coverage

Status: implemented software scope; full release acceptance open.

## Problem

`factory.operations.releases.verify_release` enforces the release gates —
`OPERATION_READY` status, a commit and tag, a non-empty file list, and a
per-file checksum confined to the release root — but no test exercised it. Only
`switch_release` pointer mechanics were covered, and the existing fixture wrote
`OPERATION_READY` manifests directly, bypassing the gate it was meant to test.

## Decision

`tests/recovery/test_releases.py` now covers `verify_release` directly:

- a consistent manifest is accepted;
- `NOT_READY` status, an empty commit, an empty tag and an empty file list are
  each refused;
- a tampered file is refused as a checksum mismatch;
- a manifest entry pointing outside the release root is refused;
- the pointer health-failure rollback test is retained, with a shared
  `write_release` helper so every fixture is a well-formed release.

## Safeguards

- Test fixtures are synthetic release manifests exercising pointer mechanics
  only, never release acceptance.
- A release is never activated; `scripts/update.sh` and `scripts/rollback.sh`
  remain refusals because no production release exists.
- `OPERATION_READY` is asserted as a gate input, not assumed by the fixture
  helper when the test intends to exercise refusal.

Evidence: docs/milestone-historical-screen-cohorts.md.
