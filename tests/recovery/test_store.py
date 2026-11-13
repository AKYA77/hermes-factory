import json
import sqlite3
import time
import pytest
from factory.experiments import Store
from factory.operations import backup, verify_backup


def test_T03_fenced_restart(tmp_path):
    s = Store(tmp_path / "factory.sqlite")
    job = s.enqueue("test", {}, "one")
    assert job == s.enqueue("test", {}, "one")
    a = s.claim(lease_seconds=1)
    with s.transaction() as db:
        db.execute("UPDATE jobs SET lease_until=? WHERE job_id=?", (time.time() - 5, job))
    b = s.claim()
    assert b["job_id"] == a["job_id"]
    assert b["lease_token"] != a["lease_token"]
    with pytest.raises(ValueError, match="STALE_LEASE"):
        s.finish(job, a["lease_token"])
    s.finish(job, b["lease_token"], {"ok": True})
    assert s.claim() is None
    assert len(s.rows("SELECT * FROM jobs")) == 1
    assert len(s.rows("SELECT * FROM attempts")) == 2


def test_T23_backup(tmp_path):
    root = tmp_path / "state"
    root.mkdir()
    s = Store(root / "factory.sqlite")
    s.enqueue("test", {}, "one")
    (root / "artifacts").mkdir()
    (root / "artifacts" / "sample.json").write_text("{}")
    dest = tmp_path / "backup"
    backup(root, dest)
    verify_backup(dest)
    with sqlite3.connect(dest / "factory.sqlite") as db:
        assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
    (dest / "artifacts" / "sample.json").write_text("corrupted")
    with pytest.raises(ValueError):
        verify_backup(dest)


def test_T27_immutable_audit(tmp_path):
    s = Store(tmp_path / "db")
    s.audit("test", "test", {})
    with pytest.raises(sqlite3.IntegrityError):
        with s.transaction() as db:
            db.execute("UPDATE audit_events SET actor='forged'")


def test_backup_verification_is_read_only(tmp_path):
    from factory.data import sha256
    import subprocess
    import sys

    root = tmp_path / "state"
    root.mkdir()
    s = Store(root / "factory.sqlite")
    s.enqueue("test", {}, "one")
    dest = tmp_path / "backup"
    backup(root, dest)
    original = {p.name: sha256(p) for p in dest.iterdir() if p.is_file()}
    for _ in range(3):
        verify_backup(dest)
    assert {p.name: sha256(p) for p in dest.iterdir() if p.is_file()} == original
    assert not list(dest.glob("*-wal")) and not list(dest.glob("*-shm"))
    proc = subprocess.run(
        [sys.executable, "-m", "factory.operations.tools", "restore-test", str(dest)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["jobs"] == 1


def test_T23_restore_keeps_jobs_artifacts_and_manifests_byte_consistent(tmp_path):
    """Restore must reproduce the backed-up state exactly, not merely open it."""
    from factory.experiments import Store
    from factory.operations import backup, restore
    from factory.operations.fixtures import seed

    root = tmp_path / "state"
    seed(root, 120)
    store = Store(root / "factory.sqlite")
    jobs_before = store.rows("SELECT * FROM jobs ORDER BY job_id")
    attempts_before = store.rows("SELECT * FROM attempts ORDER BY attempt_id")
    strategy_specs_before = store.rows(
        "SELECT * FROM strategy_specs ORDER BY strategy_id"
    )
    experiments_before = store.rows("SELECT * FROM experiments ORDER BY experiment_hash")
    artifacts_before = sorted(
        (path.relative_to(root), path.read_bytes())
        for path in (root / "artifacts").rglob("*")
        if path.is_file()
    ) if (root / "artifacts").exists() else []

    dest = tmp_path / "backup"
    backup(root, dest)
    restored = tmp_path / "restored"
    restore(dest, restored)

    restored_store = Store(restored / "factory.sqlite")
    assert restored_store.rows("SELECT * FROM jobs ORDER BY job_id") == jobs_before
    assert restored_store.rows("SELECT * FROM attempts ORDER BY attempt_id") == attempts_before
    assert (
        restored_store.rows("SELECT * FROM strategy_specs ORDER BY strategy_id")
        == strategy_specs_before
    )
    assert (
        restored_store.rows("SELECT * FROM experiments ORDER BY experiment_hash")
        == experiments_before
    )
    artifacts_after = sorted(
        (path.relative_to(restored), path.read_bytes())
        for path in (restored / "artifacts").rglob("*")
        if path.is_file()
    ) if (restored / "artifacts").exists() else []
    assert artifacts_after == artifacts_before
