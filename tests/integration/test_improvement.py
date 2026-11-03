"""Actual autonomous controlled children, durable evidence and conservative labels."""

from decimal import Decimal as D
import json
import sqlite3

import pytest

from apps.coordinator.service import cycle
from factory.contracts import ExperimentContract, StrategySpec
from factory.experiments import Store
from factory.exploration.persistent import Search, SearchProtocol, rebuild_study
from factory.improvement.service import Improvement, ImprovementPolicy, compare
from factory.operations.fixtures import seed


def parent_run(root):
    payload = seed(root, 240)
    for seed_value in range(128):
        protocol = SearchProtocol(
            dataset_hash=payload["contract"]["dataset_hash"],
            profile=payload["profile"],
            window=payload["contract"]["windows"][0],
            family="momentum",
            timeframe="M1",
            code_revision=payload["contract"]["code_revision"],
            seed=seed_value,
            max_trials=1,
        )
        params = (
            rebuild_study(protocol, [], 0).ask(fixed_distributions=protocol.distributions()).params
        )
        if params["stop_ticks"] >= 60 and params["lookback"] <= 20:
            break
    store = Store(root / "factory.sqlite")
    search = Search(store, root)
    identity = search.register(protocol)
    search.ask(identity)
    search.enqueue_pending()
    store.pause(False, "test")
    assert cycle(store, root)
    assert search.feedback() == 1
    rows = store.rows("SELECT * FROM experiments")
    assert len(rows) == 1 and json.loads(rows[0]["result_json"])["trades"]
    return store, identity, rows[0]


def test_offline_controlled_improvement_restart_budget_and_lineage(tmp_path, monkeypatch):
    store, identity, parent = parent_run(tmp_path)
    policy = ImprovementPolicy(search_protocol_hash=identity, max_parent_plans=1, max_children=2)
    service = Improvement(store, tmp_path)
    policy_hash = service.register(policy)
    assert service.discover() == 1 and service.discover() == 0
    plans = store.rows("SELECT * FROM improvement_plans")
    edges = store.rows("SELECT * FROM improvement_edges")
    assert len(plans) == 1 and len(edges) == 2
    parent_contract = ExperimentContract.model_validate_json(parent["contract_json"])
    for edge in edges:
        payload = json.loads(edge["payload_json"])
        child = StrategySpec.model_validate(payload["strategy"])
        contract = ExperimentContract.model_validate(payload["contract"])
        assert child.target_rr == "3" and contract.windows == parent_contract.windows
        left, right = parent_contract.model_dump(), contract.model_dump()
        left.pop("strategy_hash")
        right.pop("strategy_hash")
        assert left == right
        assert json.loads(edge["changed_fields_json"]) and edge["hypothesis"]
    store.pause(True, "test")
    assert not service.admit() and not cycle(store, tmp_path)
    store.pause(False, "test")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    for _ in range(5):
        cycle(Store(tmp_path / "factory.sqlite"), tmp_path)
    service = Improvement(Store(tmp_path / "factory.sqlite"), tmp_path)
    service.feedback()
    outcomes = store.rows("SELECT * FROM improvement_outcomes")
    assert outcomes and len(outcomes) <= 2
    assert all(row["status"] == "INCONCLUSIVE" for row in outcomes)  # tiny fixture, never promoted
    assert all(row["cpu_seconds"] > 0 for row in outcomes)
    assert store.rows("SELECT * FROM experiments WHERE run_id=?", (parent["run_id"],)) == [parent]
    assert service.status()["measured_worker_cpu_seconds"] > 0
    with pytest.raises(sqlite3.IntegrityError, match="immutable improvement"):
        with store.transaction() as db:
            db.execute("UPDATE improvement_outcomes SET status='TRAIN_IMPROVED_ONLY'")
    service.disable(policy_hash)
    assert service.admit() == 0
    assert len(store.rows("SELECT * FROM improvement_edges")) == 2  # no recursive runaway


def test_corrupt_parent_disables_policy_and_preserves_failure_reason(tmp_path):
    store, identity, parent = parent_run(tmp_path)
    service = Improvement(store, tmp_path)
    policy = ImprovementPolicy(search_protocol_hash=identity)
    service.register(policy)
    (tmp_path / "artifacts" / (parent["run_id"] + ".json")).write_text("{}")
    assert service.discover() == 0
    assert not service.policies()
    assert not store.rows("SELECT * FROM improvement_edges")
    events = store.rows("SELECT payload FROM audit_events WHERE action='improvement_disabled'")
    assert "integrity mismatch" in json.loads(events[0]["payload"])["reason"]


def test_small_sample_selectivity_and_censoring_cannot_claim_improved():
    policy = ImprovementPolicy(search_protocol_hash="0" * 64)

    def result(n, pnl, *, open_trade=None):
        return {
            "trades": [
                {"pnl": str(pnl), "signal": {"available_at": i}, "side": "BUY"} for i in range(n)
            ],
            "ending_equity": str(D(20) + n * D(pnl)),
            "diagnostics": [],
            "open_trade": open_trade,
        }

    parent, child = result(100, ".01"), result(4, "1")
    status, evidence = compare(parent, child, policy)
    assert status == "INCONCLUSIVE" and evidence["selectivity_warning"]
    assert compare(result(60, "-.01"), result(60, ".01"), policy)[0] == "TRAIN_IMPROVED_ONLY"
    assert compare(result(60, ".02"), result(60, ".01"), policy)[0] == "TRAIN_NOT_IMPROVED"
    assert (
        compare(parent, result(100, ".1", open_trade={"censored": True}), policy)[0]
        == "INCONCLUSIVE"
    )


def test_shared_child_job_has_one_cpu_owner_across_policies(tmp_path):
    store, identity, _ = parent_run(tmp_path)
    service = Improvement(store, tmp_path)
    for cap in (1, 2):
        service.register(
            ImprovementPolicy(search_protocol_hash=identity, max_parent_plans=cap, max_children=1)
        )
    assert service.discover() == 1 and service.discover() == 1
    edges = store.rows("SELECT * FROM improvement_edges")
    assert (
        len(edges) == 2 and edges[0]["child_experiment_hash"] == edges[1]["child_experiment_hash"]
    )
    assert service.admit() == 1
    assert cycle(store, tmp_path)
    assert service.feedback() == 2
    outcomes = store.rows("SELECT * FROM improvement_outcomes")
    assert sorted(o["cpu_seconds"] > 0 for o in outcomes) == [False, True]
    job = store.rows(
        "SELECT job_id FROM jobs WHERE idempotency_key=?", (edges[0]["child_experiment_hash"],)
    )[0]
    measured = store.rows(
        "SELECT resources_json FROM attempt_resources r JOIN attempts a USING(token) WHERE a.job_id=?",
        (job["job_id"],),
    )
    assert sum(o["cpu_seconds"] for o in outcomes) == sum(
        json.loads(r["resources_json"])["cpu_seconds"] for r in measured
    )
