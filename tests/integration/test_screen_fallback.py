"""Native disagreement disables pruning without deleting original rejections."""

import json
import sqlite3

import pytest

from apps.coordinator import worker
from apps.coordinator.service import cycle
from factory.experiments import Store
from factory.screening import screen
from factory.screening.fallback import enqueue_rechecks, status, trip
from test_screening import prepared


def test_real_native_disagreement_trips_once_and_future_jobs_bypass(tmp_path, monkeypatch):
    payload, contract = prepared(tmp_path, True, signals=True)
    store = Store(tmp_path / "factory.sqlite")
    monkeypatch.setattr(worker, "screen", lambda signals, contract: screen([], contract))
    with pytest.raises(ValueError, match="TIER0_FALSE_NEGATIVE"):
        worker.run(payload, tmp_path)
    assert not status(store)["enabled"] and status(store)["incident"]
    evidence = list((tmp_path / "artifacts" / "failed").glob("*.json"))
    assert len(evidence) == 1
    assert not trip(store, contract, "a" * 64)
    assert (
        len(store.rows("SELECT * FROM audit_events WHERE action='tier0_circuit_breaker_tripped'"))
        == 1
    )
    result = worker.run(payload, tmp_path)["result"]
    assert (
        result["fills"]
        and result["tier0_pruning_bypassed"] == "PERSISTENT_NATIVE_AUDIT_CIRCUIT_BREAKER"
    )
    assert not result["integrity_errors"] and "tier0_screen" not in result
    assert evidence[0].exists() and not status(Store(store.path))["enabled"]
    with store.transaction() as db:
        with pytest.raises(sqlite3.IntegrityError, match="immutable audit"):
            db.execute("DELETE FROM audit_events WHERE action='tier0_circuit_breaker_tripped'")


def test_actual_native_recheck_preserves_negative_evidence_pause_and_dedup(tmp_path, monkeypatch):
    payload, contract = prepared(tmp_path, False)
    store = Store(tmp_path / "factory.sqlite")
    original = store.enqueue("research", payload, contract.experiment_hash)
    store.pause(False, "test")
    assert cycle(store, tmp_path)
    prior = store.rows("SELECT * FROM jobs WHERE job_id=?", (original,))[0]
    assert json.loads(prior["result"])["screen"]["decision"] == "PRUNE_NO_SIGNALS"
    broken, _ = prepared(tmp_path, True, signals=True)
    monkeypatch.setattr(worker, "screen", lambda signals, contract: screen([], contract))
    with pytest.raises(ValueError, match="TIER0_FALSE_NEGATIVE"):
        worker.run(broken, tmp_path)
    store.pause(True, "test")
    assert enqueue_rechecks(store, tmp_path) == 0
    store.pause(False, "test")
    assert enqueue_rechecks(store, tmp_path) == 1
    assert enqueue_rechecks(store, tmp_path) == 0
    jobs = store.rows("SELECT * FROM jobs WHERE idempotency_key LIKE 'screen-recheck:%'")
    assert len(jobs) == 1 and json.loads(jobs[0]["payload"])["screen_recheck_of"] == original
    assert cycle(store, tmp_path)
    after = store.rows("SELECT * FROM jobs WHERE job_id=?", (original,))[0]
    assert after == prior
    recovered = store.rows("SELECT * FROM jobs WHERE job_id=?", (jobs[0]["job_id"],))[0]
    assert recovered["state"] == "COMPLETED"
    native = store.rows(
        "SELECT * FROM experiments WHERE experiment_hash=?", (contract.experiment_hash,)
    )
    assert len(native) == 1 and json.loads(native[0]["result_json"])["quote_count"] == 60
    assert enqueue_rechecks(Store(store.path), tmp_path) == 0


def test_corrupt_breaker_fails_closed_and_unknown_policy_still_rejected(tmp_path):
    payload, _ = prepared(tmp_path, False)
    store = Store(tmp_path / "factory.sqlite")
    with store.transaction() as db:
        db.execute("INSERT INTO controls VALUES('tier0_circuit_breaker','bad json')")
    assert not status(store)["enabled"]
    result = worker.run(payload, tmp_path)["result"]
    assert result["quote_count"] == 60 and "tier0_screen" not in result
    payload["screening"] = "unknown policy"
    with pytest.raises(ValueError, match="unsupported screening policy"):
        worker.run(payload, tmp_path)


def test_old_code_rejections_are_not_reauthorized_by_recovery(tmp_path):
    payload, contract = prepared(tmp_path, False)
    store = Store(tmp_path / "factory.sqlite")
    payload["contract"]["code_revision"] = "old-code-not-current"
    original = store.enqueue("research", payload, contract.experiment_hash)
    job = store.claim()
    store.finish(original, job["lease_token"], result={"screen": {"decision": "PRUNE_NO_SIGNALS"}})
    trip(store, contract, "b" * 64)
    store.pause(False, "test")
    assert enqueue_rechecks(store, tmp_path) == 0
    assert len(store.rows("SELECT * FROM jobs")) == 1


def test_disabled_screen_preserves_cost_shadow_labels_and_native_only_policy(tmp_path):
    payload, contract = prepared(tmp_path, False, signals=True)
    payload["contract"]["evaluation_policy"] = "synthetic-cost-shadow-training/v1"
    store = Store(tmp_path / "factory.sqlite")
    trip(store, contract, "c" * 64)
    result = worker.run(payload, tmp_path)["result"]
    assert result["fills"] and result["cost_horizon_labels"]["pruning_authorized"] is False
    assert result["tier0_pruning_bypassed"] and "tier0_screen" not in result


def test_recovery_count_and_measured_cpu_budgets_preserve_disabled_state(tmp_path, monkeypatch):
    from factory.screening import fallback

    payload, contract = prepared(tmp_path, False)
    store = Store(tmp_path / "factory.sqlite")
    store.enqueue("research", payload, contract.experiment_hash)
    store.pause(False, "test")
    assert cycle(store, tmp_path)
    trip(store, contract, "d" * 64)
    monkeypatch.setattr(fallback, "MAX_RECHECKS", 1)
    assert enqueue_rechecks(store, tmp_path) == 1
    assert fallback.recovery_budget(store)["admission_stopped"]
    assert cycle(store, tmp_path)
    budget = fallback.recovery_budget(store)
    assert budget["admitted"] == 1 and budget["measured_cpu_seconds"] > 0
    monkeypatch.setattr(fallback, "MAX_RECHECKS", 64)
    monkeypatch.setattr(fallback, "MAX_RECHECK_CPU_SECONDS", 0)
    assert fallback.recovery_budget(store)["admission_stopped"]
    assert enqueue_rechecks(store, tmp_path) == 0 and not status(store)["enabled"]
