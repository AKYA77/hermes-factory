"""Persistent research uses actual worker artifacts; toy learning is separate."""

from decimal import Decimal as D
import json
import sqlite3
from statistics import median

import pytest
from pydantic import ValidationError

from apps.coordinator.service import cycle
from factory.contracts import InstrumentSpec, Window, serialize
from factory.experiments import Store
from factory.exploration.persistent import Search, SearchProtocol, rebuild_study
from factory.operations.fixtures import seed


def protocol(payload, **changes):
    raw = {
        "dataset_hash": payload["contract"]["dataset_hash"],
        "profile": InstrumentSpec.model_validate(payload["profile"]),
        "window": Window.model_validate(payload["contract"]["windows"][0]),
        "family": "momentum",
        "timeframe": "M1",
        "code_revision": payload["contract"]["code_revision"],
        "seed": 42,
        "max_trials": 8,
    }
    raw.update(changes)
    return SearchProtocol(**raw)


def test_recurring_feedback_restart_and_no_llm(tmp_path, monkeypatch):
    payload = seed(tmp_path, 240)
    store = Store(tmp_path / "factory.sqlite")
    search = Search(store, tmp_path)
    p = protocol(payload)
    identity = search.register(p)
    assert not cycle(store, tmp_path)  # paused: registration is not start permission
    store.pause(False, "test")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    for _ in range(12):
        # A fresh store/coordinator object every cycle, not an in-memory study.
        store = Store(tmp_path / "factory.sqlite")
        cycle(store, tmp_path)
    search = Search(store, tmp_path)
    search.feedback()
    outcomes = store.rows("SELECT * FROM search_outcomes")
    assert len(outcomes) == 8
    assert any(o["outcome"] == "COMPLETE" for o in outcomes)
    assert all(o["cpu_seconds"] > 0 for o in outcomes)
    for o in outcomes:
        if o["outcome"] == "COMPLETE":
            result = json.loads(
                store.rows("SELECT result_json FROM experiments WHERE run_id=?", (o["run_id"],))[0][
                    "result_json"
                ]
            )
            assert o["objective"] == float((D(result["ending_equity"]) - 20) / 20)
    assert search.ask(identity) is None  # finite budget survives restart
    with pytest.raises(sqlite3.IntegrityError, match="immutable search"):
        with store.transaction() as db:
            db.execute("UPDATE search_outcomes SET objective=99")
    assert store.rows("SELECT version FROM schema_migrations ORDER BY version") == [
        {"version": 1},
        {"version": 2},
    ]


def test_durable_ask_recovers_without_duplicate_jobs(tmp_path):
    payload = seed(tmp_path, 120)
    store = Store(tmp_path / "factory.sqlite")
    search = Search(store, tmp_path)
    identity = search.register(protocol(payload, max_trials=2))
    asked = search.ask(identity)
    assert not asked["duplicate"]
    assert not store.rows("SELECT * FROM jobs")
    restarted = Search(Store(tmp_path / "factory.sqlite"), tmp_path)
    restarted.enqueue_pending()
    restarted.enqueue_pending()
    assert len(store.rows("SELECT * FROM jobs")) == 1
    row = store.rows("SELECT * FROM search_trials")[0]
    assert json.loads(row["spec_json"]) == asked["spec"].model_dump(mode="json")


def test_optimizer_rejects_oos_and_tampered_artifact(tmp_path):
    payload = seed(tmp_path, 240)
    original = payload["contract"]["windows"][0]
    with pytest.raises(ValidationError, match="training only"):
        protocol(payload, window=Window(**{**original, "role": "selection_oos"}))
    store = Store(tmp_path / "factory.sqlite")
    search = Search(store, tmp_path)
    identity = search.register(protocol(payload, max_trials=1))
    search.ask(identity)
    search.enqueue_pending()
    store.pause(False, "test")
    cycle(store, tmp_path)
    experiment = store.rows("SELECT * FROM experiments")[0]
    (tmp_path / "artifacts" / f"{experiment['run_id']}.json").write_text("{}")
    with pytest.raises(ValueError, match="artifact integrity"):
        search.feedback()
    assert not store.rows("SELECT * FROM search_outcomes")


def test_sampler_learning_and_restart_determinism_on_labeled_toy(tmp_path):
    # This numerical training objective is NOT a market result or official experiment.
    p = protocol(seed(tmp_path, 60), max_trials=64)
    history = []
    distances = []
    for number in range(48):
        study = rebuild_study(p, history, number)
        study_restart = rebuild_study(p, list(history), number)
        a = study.ask(fixed_distributions=p.distributions()).params
        b = study_restart.ask(fixed_distributions=p.distributions()).params
        assert a == b
        distance = abs(a["lookback"] - 13)
        distances.append(distance)
        history.append(
            {
                "parameters_json": serialize(a),
                "outcome": "COMPLETE",
                "objective": float(-(distance**2)),
            }
        )
    assert median(distances[-12:]) < median(distances[:8])
    assert median(distances[-12:]) <= 3


def test_worker_memory_limit_is_recorded_failure(tmp_path):
    payload = seed(tmp_path, 120)
    store = Store(tmp_path / "factory.sqlite")
    store.enqueue("research", payload, "capacity-test")
    store.pause(False, "test")
    assert cycle(store, tmp_path, memory_limit_bytes=1)
    row = store.rows("SELECT * FROM jobs")[0]
    assert row["state"] == "FAILED_FINAL"
    assert "WORKER_MEMORY_LIMIT" in row["error"]
    assert not store.rows("SELECT * FROM experiments")


def test_obsolete_source_never_enqueues_pending(tmp_path, monkeypatch):
    payload = seed(tmp_path, 120)
    store = Store(tmp_path / "factory.sqlite")
    search = Search(store, tmp_path)
    identity = search.register(protocol(payload))
    search.ask(identity)
    import factory.exploration.persistent as module

    def reject(_):
        raise ValueError("execution source revision mismatch")

    monkeypatch.setattr(module, "require_execution_version", reject)
    assert search.enqueue_pending() == 0
    assert not store.rows("SELECT * FROM jobs")
    assert store.rows("SELECT reason FROM search_outcomes")[0]["reason"] == "STALE_SOURCE"


def test_pause_between_planning_and_claim_prevents_worker_admission(tmp_path, monkeypatch):
    import apps.coordinator.research as module

    payload = seed(tmp_path, 120)
    store = Store(tmp_path / "factory.sqlite")
    store.pause(False, "test")
    store.enqueue("research", payload, "pause-race")
    monkeypatch.setattr(
        module, "maintenance", lambda store, root: store.pause(True, "pause-during-plan")
    )
    assert not cycle(store, tmp_path)
    assert store.rows("SELECT state FROM jobs")[0]["state"] == "QUEUED"
    assert not store.rows("SELECT * FROM attempts")
