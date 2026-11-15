# ADR0053 — State restore and rollback planning

Status: implemented software scope; full operational acceptance open.

## Problem

`factory/operations` provided `backup` and `verify_backup`, and
`tools.py restore-test` copied a backup and re-verified it, but nothing restored a
verified backup into a fresh state root. `scripts/rollback.sh` was a stub that
refused, so no rehearsed rollback path existed.

## Decision

- `restore(backup_path, state_root)` verifies the backup, then copies it into a
  target that **must not exist** and **must sit outside the backup**, and
  re-verifies the copy. A restore can therefore never overwrite live state or the
  backup it came from.
- `rollback_plan(backup_path, state_root, services_stopped,
  previous_release_verified)` describes a rollback and returns a plan with
  `applied: false`. It refuses unless the caller affirms that services are
  stopped and the previous release is verified.
- CLI actions `restore` and `rollback-plan`, exposed as `scripts/restore.sh` and
  `scripts/rollback-plan.sh`. `scripts/rollback.sh` remains a refusal stub
  because no production release exists yet.

## Safeguards

- A rollback is a plan, never a live-state switch.
- Restoring into an existing or nested target is refused.
- Both affirmations are required; neither is inferred.
- No production release exists yet, so no rollback is ever applied.
- A rehearsal must restore into a fresh root and re-run verification.

Evidence: docs/milestone-historical-screen-cohorts.md.
