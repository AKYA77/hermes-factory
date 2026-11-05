"""Native synthetic counterexample: an approximate reject can be profitable.

This is an accuracy regression fixture, NOT a historical performance claim.
"""

from dataclasses import replace
from decimal import Decimal as D
import json
import sqlite3

import pytest

from apps.coordinator.worker import run
from factory.contracts import ExperimentContract, StrategySpec
from factory.data import Catalog
from factory.experiments import Store
from factory.operations.fixtures import seed
from factory.screening import SCREEN_POLICY, screen, from_summary
from factory.screening.labels import CostHorizonPolicy, estimate_labels
from factory.features import closed_bar_events
from factory.strategies import iter_bar_signals


def counterexample(root):
    payload = seed(root, 400)
    catalog = Catalog(root / "catalog")
    data = [
        replace(
            q,
            bid_int=110000 + n,
            ask_int=110010 + n,
            source_id="generated-linear-shadow-counterexample",
            ingest_batch_id="linear/v1",
        )
        for n, q in enumerate(catalog.read(payload["contract"]["dataset_hash"]))
    ]
    manifest = catalog.commit(
        data,
        b"generated linear synthetic cost-estimator counterexample",
        {
            "source": "generated linear native shadow counterexample",
            "license": "project test",
            "synthetic": True,
        },
    )
    payload["contract"]["dataset_hash"] = manifest["dataset_hash"]
    payload["screening"] = SCREEN_POLICY
    payload["contract"]["evaluation_policy"] = "synthetic-cost-shadow-training/v1"
    return payload, data


def test_native_positive_counterexample_is_preserved_and_not_approximately_pruned(tmp_path):
    payload, data = counterexample(tmp_path)
    native = run(payload, tmp_path)
    result = native["result"]
    estimate = result["cost_horizon_labels"]
    assert estimate["rejection_suggested"] and estimate["pruning_authorized"] is False
    assert D(estimate["mean_net_label_pips"]) == D("-5.5")
    assert not result["integrity_errors"] and result["trades"]
    assert D(result["equity"]["ending_marked_equity"]) > 20
    contract = ExperimentContract.model_validate(payload["contract"])
    spec = StrategySpec.model_validate(payload["strategy"])
    store = Store(tmp_path / "factory.sqlite")
    store.complete_experiment(contract, spec, result, native["artifact_hash"])
    store.complete_experiment(contract, spec, result, native["artifact_hash"])
    rows = store.rows("SELECT * FROM cost_label_audits")
    assert len(rows) == 1
    audit = json.loads(rows[0]["body_json"])
    assert audit["observed_false_negative"] and audit["native_positive_marked_with_closed_trades"]
    assert audit["approximate_pruning_enabled"] is False
    assert audit["native_artifact_hash"] == native["artifact_hash"]
    assert audit["native_closed_trades"] == len(result["trades"])
    assert audit["feature_label_count"] != audit["native_closed_trades"]
    with pytest.raises(sqlite3.IntegrityError, match="immutable cost label audit"):
        with store.transaction() as db:
            db.execute("DELETE FROM cost_label_audits")


def test_legacy_exact_zero_receipt_is_identical_when_reusing_label_signal_digest(tmp_path):
    payload, data = counterexample(tmp_path)
    from factory.contracts import InstrumentSpec

    spec = StrategySpec.model_validate(payload["strategy"])
    profile = InstrumentSpec.model_validate(payload["profile"])
    contract = ExperimentContract.model_validate(payload["contract"])
    events = list(closed_bar_events(data, (spec.timeframe, *spec.confirmations)))
    legacy = screen(iter_bar_signals(iter(events), spec), contract)
    labels = estimate_labels(iter(events), spec, profile, contract, CostHorizonPolicy())
    assert from_summary(labels["signal_count"], labels["signal_sha256"], contract) == legacy


def test_shadow_mode_keeps_native_exact_zero_false_negative_guard(tmp_path, monkeypatch):
    import apps.coordinator.worker as worker
    from factory.screening import selected_for_audit

    payload, _ = counterexample(tmp_path)
    for seed_value in range(10000):
        payload["contract"]["seed"] = seed_value
        if selected_for_audit(ExperimentContract.model_validate(payload["contract"])):
            break
    else:
        raise AssertionError("no deterministic audit fixture found")
    monkeypatch.setattr(
        worker, "from_summary", lambda count, digest, contract: screen([], contract)
    )
    with pytest.raises(ValueError, match="TIER0_FALSE_NEGATIVE"):
        worker.run(payload, tmp_path)
    assert not Store(tmp_path / "factory.sqlite").rows("SELECT * FROM experiments")


def test_ordinary_training_keeps_original_cheap_screen_and_no_shadow_metadata(tmp_path):
    payload, _ = counterexample(tmp_path)
    payload["contract"]["evaluation_policy"] = "synthetic-training/v1"
    result = run(payload, tmp_path)["result"]
    assert "cost_horizon_labels" not in result
    assert result["tier0_screen"]["decision"] == "PASS_TO_NATIVE"


def test_explicit_shadow_kind_flows_through_durable_tpe_and_native_feedback(tmp_path):
    from apps.coordinator.service import cycle
    from factory.contracts import Window
    from factory.exploration.persistent import Search, SearchProtocol

    payload, _ = counterexample(tmp_path)
    base = dict(
        dataset_hash=payload["contract"]["dataset_hash"],
        profile=payload["profile"],
        window=Window.model_validate(payload["contract"]["windows"][0]),
        family="breakout",
        timeframe="M1",
        code_revision=payload["contract"]["code_revision"],
        seed=42,
        max_trials=1,
    )
    ordinary = SearchProtocol(**base)
    shadow = SearchProtocol(**base, research_kind="synthetic-cost-shadow-training/v1")
    assert ordinary.protocol_hash != shadow.protocol_hash
    store = Store(tmp_path / "factory.sqlite")
    search = Search(store, tmp_path)
    identity = search.register(shadow)
    trial = search.ask(identity)
    assert trial["contract"].evaluation_policy == shadow.research_kind
    assert trial["contract"].experiment_hash != ordinary.contract(trial["spec"]).experiment_hash
    search.enqueue_pending()
    store.pause(False, "test")
    assert cycle(store, tmp_path)
    search.feedback()
    native = json.loads(store.rows("SELECT result_json FROM experiments")[0]["result_json"])
    assert native["cost_horizon_labels"]["pruning_authorized"] is False
    assert len(store.rows("SELECT * FROM cost_label_audits")) == 1
    outcome = store.rows("SELECT * FROM search_outcomes")[0]
    assert outcome["objective"] == (
        float((D(native["ending_equity"]) - 20) / 20) if native["trades"] else None
    )
