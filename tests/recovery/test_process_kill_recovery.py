"""T03: a coordinator killed mid-job must not strand the job.

`test_T03_fenced_restart` covers lease expiry by rewinding `lease_until` by
hand. This test kills a real holder process instead, so the recovery path is
exercised the way a coordinator crash presents it: the lease simply stops being
renewed and expires on its own.
"""

import json
import subprocess
import sys
import time

import pytest

from factory.experiments import Store

HOLDER = """
import sys, time
from factory.experiments import Store
store = Store(sys.argv[1])
job = store.claim(lease_seconds=2)
if job is None:
    raise SystemExit(3)
print(job["job_id"], flush=True)
time.sleep(60)
"""


def _wait_for(predicate, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_T03_process_kill_recovers_the_leased_job(tmp_path):
    store = Store(tmp_path / "factory.sqlite")
    job = store.enqueue("test", {}, "kill-recovery")
    holder = subprocess.Popen(
        [sys.executable, "-c", HOLDER, str(tmp_path / "factory.sqlite")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert _wait_for(
            lambda: store.rows("SELECT state FROM jobs WHERE job_id=?", (job,))[0]["state"]
            == "RUNNING"
        ), "holder never claimed the job"
        assert holder.stdout is not None
        claimed_id = holder.stdout.readline().strip()
        assert claimed_id == job
        holder.kill()
        holder.wait(timeout=10)
        # Nothing renews the lease; the next claim is what expires it.
        assert _wait_for(
            lambda: store.rows("SELECT lease_until FROM jobs WHERE job_id=?", (job,))[0][
                "lease_until"
            ]
            <= time.time(),
            timeout=15,
        ), "lease never expired after the holder was killed"
        recovered = store.claim()
        assert recovered is not None
        assert recovered["job_id"] == job
        attempts = store.rows("SELECT outcome FROM attempts WHERE job_id=?", (job,))
        assert "LEASE_EXPIRED" in [a["outcome"] for a in attempts]
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=10)
        holder.stderr.close()


def test_T03_killed_coordinator_does_not_duplicate_work(tmp_path):
    """Recovery must re-run the job once, not leave two live attempts."""
    store = Store(tmp_path / "factory.sqlite")
    job = store.enqueue("test", {}, "kill-recovery-once")
    holder = subprocess.Popen(
        [sys.executable, "-c", HOLDER, str(tmp_path / "factory.sqlite")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        assert _wait_for(
            lambda: store.rows("SELECT state FROM jobs WHERE job_id=?", (job,))[0]["state"]
            == "RUNNING"
        )
        holder.kill()
        holder.wait(timeout=10)
        assert _wait_for(
            lambda: store.rows("SELECT lease_until FROM jobs WHERE job_id=?", (job,))[0][
                "lease_until"
            ]
            <= time.time(),
            timeout=15,
        ), "lease never expired after the holder was killed"
        first = store.claim()
        assert first is not None
        # A second claim while the first lease is live must not hand out the job.
        assert store.claim() is None
        running = store.rows("SELECT state FROM jobs WHERE job_id=?", (job,))[0]["state"]
        assert running == "RUNNING"
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=10)


@pytest.mark.parametrize("outcome", ["LEASE_EXPIRED"])
def test_T03_expiry_outcome_is_persisted(tmp_path, outcome):
    store = Store(tmp_path / "factory.sqlite")
    job = store.enqueue("test", {}, "expiry-outcome")
    claimed = store.claim(lease_seconds=1)
    assert claimed is not None
    with store.transaction() as db:
        db.execute(
            "UPDATE jobs SET lease_until=? WHERE job_id=?",
            (time.time() - 1, job),
        )
    assert store.claim()["job_id"] == job
    outcomes = [a["outcome"] for a in store.rows("SELECT outcome FROM attempts")]
    assert outcome in outcomes
    assert json.loads(json.dumps({"ok": True})) == {"ok": True}
