"""Native confirmation and irreversible, alias-safe managed holdout influence."""

import copy
import json
import sqlite3

import pytest

from apps.coordinator.service import cycle
from apps.coordinator.worker import run
from factory.contracts import ExperimentContract, StrategySpec, Window
from factory.data import Catalog
from factory.experiments import Store
from factory.exploration.persistent import Search, SearchProtocol
from factory.operations.fixtures import seed
from factory.validation.access import Holdouts, HoldoutSpec
from factory.validation.evaluate import evaluate


def prepared(root):
    payload = seed(root, 240)
    full = payload["contract"]["windows"][0]
    cut = full["start_ns"] + 120 * 60 * 10**9
    final = Window(start_ns=cut, end_ns=full["end_ns"], role="final_holdout_unseen")
    spec = HoldoutSpec(
        dataset_hash=payload["contract"]["dataset_hash"],
        profile=payload["profile"],
        window=final,
        code_revision=payload["contract"]["code_revision"],
        external_use_declaration="NO_PRIOR_USE_DECLARED",
        declaration_notes="Fresh labeled synthetic acceptance fixture, no prior research",
    )
    holdouts = Holdouts(root)
    identity = holdouts.register(spec)
    train = copy.deepcopy(payload)
    train["contract"]["windows"][0]["end_ns"] = cut
    return holdouts, identity, train, payload, spec


def complete_training(root, payload):
    result = run(payload, root)
    contract = ExperimentContract.model_validate(payload["contract"])
    store = Store(root / "factory.sqlite")
    store.complete_experiment(
        contract,
        StrategySpec.model_validate(payload["strategy"]),
        result["result"],
        result["artifact_hash"],
    )
    return contract.experiment_hash


def test_native_confirmation_restart_and_one_independent_observation(tmp_path):
    holdouts, identity, training, _, spec = prepared(tmp_path)
    assert holdouts.register(spec) == identity
    run_id = complete_training(tmp_path, training)
    frozen = holdouts.freeze(identity, run_id)
    assert holdouts.status()[0]["status"] == "CANDIDATE_FROZEN"
    queued = holdouts.enqueue(identity)
    assert holdouts.status()[0]["status"] == "HOLDOUT_CONSUMED"
    assert Holdouts(tmp_path).enqueue(identity) == queued
    store = Store(tmp_path / "factory.sqlite")
    assert len(store.rows("SELECT * FROM holdout_consumptions")) == 1
    store.pause(False, "test")
    assert cycle(store, tmp_path)
    rows = store.rows("SELECT * FROM evaluation_results")
    assert len(rows) == 1
    report = json.loads(rows[0]["result_json"])
    assert report["synthetic"] and report["status"] == "INSUFFICIENT_EVIDENCE"
    assert (
        report["managed_holdout"]["independent_observation_id"]
        == queued["independent_observation_id"]
    )
    assert report["windows"][0]["replay"]["quote_count"] == 120
    assert all(
        t["entry_fill"]["ts"] >= spec.window.start_ns
        for t in report["windows"][0]["replay"]["trades"]
    )
    assert (
        len(store.rows("SELECT * FROM experiments")) == 1
    )  # no optimizer training objective from confirmation
    assert Holdouts(tmp_path).enqueue(identity) == queued
    assert not cycle(store, tmp_path)  # exact job/result reused
    with pytest.raises(sqlite3.IntegrityError, match="immutable holdout"):
        with store.transaction() as db:
            db.execute("DELETE FROM holdout_consumptions")
    assert frozen["contract"]["windows"][0]["role"] == "final_holdout_unseen"


def test_queue_worker_and_optimizer_cannot_bypass_with_alias_view(tmp_path):
    holdouts, identity, training, full, _ = prepared(tmp_path)
    view = Catalog(tmp_path / "catalog").compose([full["contract"]["dataset_hash"]])
    full["contract"]["dataset_hash"] = view["dataset_hash"]
    store = Store(tmp_path / "factory.sqlite")
    with pytest.raises(ValueError, match="PROTECTED_HOLDOUT_ACCESS"):
        store.enqueue("research", full, "alias-cannot-bypass")
    with pytest.raises(ValueError, match="PROTECTED_HOLDOUT_ACCESS"):
        run(full, tmp_path)
    p = SearchProtocol(
        dataset_hash=view["dataset_hash"],
        profile=full["profile"],
        window=full["contract"]["windows"][0],
        family="momentum",
        timeframe="M1",
        code_revision=full["contract"]["code_revision"],
        seed=42,
    )
    with pytest.raises(ValueError, match="PROTECTED_HOLDOUT_ACCESS"):
        Search(store, tmp_path).register(p)
    with pytest.raises(ValueError, match="requires one frozen"):
        forged = copy.deepcopy(full)
        forged["contract"]["windows"][0]["role"] = "final_holdout_unseen"
        evaluate(tmp_path / "catalog", forged)
    assert holdouts.status()[0]["status"] == "RESERVED_UNSEEN"
    assert not store.rows("SELECT * FROM experiments")
    assert complete_training(tmp_path, training)


def test_retroactive_unseen_claim_rejected_for_legacy_history(tmp_path):
    payload = seed(tmp_path, 240)
    store = Store(tmp_path / "factory.sqlite")
    store.enqueue("research", payload, "observed-before-reservation")
    # Remove the supplemental use ledger to reproduce a pre-migration database.
    # Deletion is forbidden: create a legacy result directly through normal store.
    w = Window.model_validate({**payload["contract"]["windows"][0], "role": "final_holdout_unseen"})
    spec = HoldoutSpec(
        dataset_hash=payload["contract"]["dataset_hash"],
        profile=payload["profile"],
        window=w,
        code_revision=payload["contract"]["code_revision"],
        external_use_declaration="NO_PRIOR_USE_DECLARED",
        declaration_notes="Cannot override already recorded influences",
    )
    with pytest.raises(ValueError, match="HOLDOUT_ALREADY_INFLUENCED"):
        Holdouts(tmp_path).register(spec)
    with pytest.raises(sqlite3.IntegrityError, match="immutable input use"):
        with store.transaction() as db:
            db.execute("DELETE FROM research_input_uses")


def test_consumption_before_worker_failure_and_frozen_candidate_cannot_change(tmp_path):
    holdouts, identity, training, _, _ = prepared(tmp_path)
    run_id = complete_training(tmp_path, training)
    holdouts.freeze(identity, run_id)
    receipt = holdouts.authorize(identity)  # process could die here, before enqueue
    assert Holdouts(tmp_path).authorize(identity) == receipt
    assert holdouts.status()[0]["status"] == "HOLDOUT_CONSUMED"
    changed = copy.deepcopy(training)
    changed["strategy"]["stop_ticks"] *= 2
    spec = StrategySpec.model_validate(changed["strategy"])
    changed["contract"]["strategy_hash"] = spec.strategy_hash
    other_run = complete_training(tmp_path, changed)
    with pytest.raises(ValueError, match="immutable holdout candidate"):
        holdouts.freeze(identity, other_run)
    forged = copy.deepcopy(receipt)
    forged["holdout_authorization"] = "0" * 64
    with pytest.raises(ValueError, match="mismatched holdout authorization"):
        evaluate(tmp_path / "catalog", forged)
