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
        {"version": 3},
        {"version": 4},
        {"version": 5},
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


def test_failed_execution_preserves_strategy_registry(tmp_path):
    payload = seed(tmp_path, 120)
    store = Store(tmp_path / "factory.sqlite")
    store.enqueue("research", payload, "failure-preservation")
    store.pause(False, "test")
    cycle(store, tmp_path, memory_limit_bytes=1)
    assert (
        store.rows("SELECT strategy_id FROM strategy_specs")[0]["strategy_id"]
        == payload["contract"]["strategy_hash"]
    )
    with pytest.raises(sqlite3.IntegrityError, match="immutable strategy"):
        with store.transaction() as db:
            db.execute("DELETE FROM strategy_specs")


def test_protocol_hash_survives_json_defaults_and_preserves_legacy_ids(tmp_path):
    from factory.contracts import fingerprint

    payload = seed(tmp_path, 60)
    store = Store(tmp_path / "factory.sqlite")
    search = Search(store, tmp_path)
    modern = protocol(payload)
    roundtrip = SearchProtocol.model_validate_json(serialize(modern))
    assert modern.protocol_hash == roundtrip.protocol_hash == fingerprint(modern)
    assert modern.schema_version == "search/v2"
    legacy = protocol(payload, schema_version="search/v1").model_copy(
        update={"cpu_budget_seconds": 600}
    )
    assert type(legacy.cpu_budget_seconds) is int  # original v1 default representation
    identity = search.register(legacy)
    restored = search.protocol(identity)
    assert restored.protocol_hash == identity == fingerprint(legacy)
    assert serialize(restored) == serialize(legacy)
    assert (
        search.ask(identity)["contract"].windows
        == legacy.contract(
            legacy.strategy(
                {"lookback": 2, "threshold_tenths": 5, "stop_ticks": 60, "confirmation": "none"}
            )
        ).windows
    )


def test_reused_native_job_cpu_is_attributed_once_across_protocols(tmp_path):
    payload = seed(tmp_path, 240)
    store = Store(tmp_path / "factory.sqlite")
    search = Search(store, tmp_path)
    a = search.register(protocol(payload, max_trials=1))
    b = search.register(protocol(payload, max_trials=2))
    left, right = search.ask(a), search.ask(b)
    assert left["contract"].experiment_hash == right["contract"].experiment_hash
    search.enqueue_pending()
    shared = store.rows(
        "SELECT * FROM jobs WHERE idempotency_key=?", (left["contract"].experiment_hash,)
    )
    assert len(shared) == 1
    store.pause(False, "test")
    assert cycle(store, tmp_path)
    search.feedback()
    outcomes = store.rows(
        "SELECT * FROM search_outcomes WHERE trial_id IN (?,?)",
        (left["trial_id"], right["trial_id"]),
    )
    assert len(outcomes) == 2
    assert sorted(o["cpu_seconds"] > 0 for o in outcomes) == [False, True]
    measured = store.rows(
        "SELECT resources_json FROM attempt_resources r JOIN attempts a USING(token) WHERE a.job_id=?",
        (shared[0]["job_id"],),
    )
    assert sum(o["cpu_seconds"] for o in outcomes) == sum(
        json.loads(r["resources_json"])["cpu_seconds"] for r in measured
    )
