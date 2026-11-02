import sqlite3
import time
import pytest
from factory.experiments import Store
from factory.operations import backup, verify_backup


def test_T03_fenced_restart(tmp_path):
    s = Store(tmp_path / "factory.sqlite")
    job = s.enqueue("research", {}, "one")
    assert job == s.enqueue("research", {}, "one")
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
