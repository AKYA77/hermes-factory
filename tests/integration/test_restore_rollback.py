"""Backup restore and rollback planning."""

import pytest

from factory.operations import backup, restore, rollback_plan, verify_backup
from factory.operations.fixtures import seed
from factory.experiments import Store


def prepared_state(tmp_path):
    root = tmp_path / "state"
    Store(root / "factory.sqlite")
    seed(root, 240)
    return root


def test_restore_into_fresh_root_round_trips(tmp_path):
    state = prepared_state(tmp_path)
    snapshot = tmp_path / "backup"
    files = backup(state, snapshot)
    assert files
    verify_backup(snapshot)
    restored = tmp_path / "restored"
    receipt = restore(snapshot, restored)
    assert receipt["schema"] == "restore/v1"
    assert receipt["files"] == len(files)
    assert (restored / "factory.sqlite").exists()
    verify_backup(restored)
    # The restore target is a copy; the source backup is untouched.
    assert (snapshot / "backup-manifest.json").exists()


def test_restore_refuses_existing_or_nested_targets(tmp_path):
    state = prepared_state(tmp_path)
    snapshot = tmp_path / "backup"
    backup(state, snapshot)
    with pytest.raises(ValueError, match="must not exist"):
        restore(snapshot, state)
    with pytest.raises(ValueError, match="outside the backup"):
        restore(snapshot, snapshot / "nested")


def test_rollback_plan_requires_affirmations(tmp_path):
    state = prepared_state(tmp_path)
    snapshot = tmp_path / "backup"
    backup(state, snapshot)
    with pytest.raises(ValueError, match="stopped services"):
        rollback_plan(snapshot, tmp_path / "target", False, True)
    with pytest.raises(ValueError, match="verified previous release"):
        rollback_plan(snapshot, tmp_path / "target", True, False)
    plan = rollback_plan(snapshot, tmp_path / "target", True, True)
    assert plan["schema"] == "rollback-plan/v1"
    assert plan["applied"] is False
    assert plan["services_stopped"] is True
    assert not (tmp_path / "target").exists()
