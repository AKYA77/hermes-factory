"""Tier 0 is durable negative evidence, independent of native result promotion."""

import json

import pytest

from apps.coordinator import worker
from apps.coordinator.service import cycle
from factory.contracts import ExperimentContract, InstrumentSpec, StrategySpec, Window
from factory.experiments import Store
from factory.exploration.persistent import Search, SearchProtocol, rebuild_study, status
from factory.operations.fixtures import seed
from factory.screening import SCREEN_POLICY, screen, selected_for_audit, verify_pruned


def choose_contract(payload, audited):
    original = ExperimentContract.model_validate(payload["contract"])
    for value in range(1024):
        candidate = original.model_copy(update={"seed": value})
        if selected_for_audit(candidate) == audited:
            return candidate
    raise AssertionError("could not find requested deterministic audit fixture")


def prepared(tmp_path, audited, *, signals=False):
    payload = seed(tmp_path, 240 if signals else 60)
    if not signals:
        spec = StrategySpec.model_validate(payload["strategy"]).model_copy(
            update={"timeframe": "H1"}
        )
        payload["strategy"] = spec.model_dump(mode="json")
        payload["contract"]["strategy_hash"] = spec.strategy_hash
    contract = choose_contract(payload, audited)
    payload["contract"] = contract.model_dump(mode="json")
    payload["screening"] = SCREEN_POLICY
    return payload, contract


def test_no_signal_prune_creates_no_native_experiment(tmp_path, monkeypatch):
    payload, contract = prepared(tmp_path, False)

    def forbidden(*args, **kwargs):
        raise AssertionError("a proven no-signal rejection must not invoke native replay")

    monkeypatch.setattr(worker, "replay", forbidden)
    first = worker.run(payload, tmp_path)
    assert first == worker.run(payload, tmp_path)  # restart receipt is identical
    receipt = verify_pruned(tmp_path, contract, first)
    assert receipt.signal_count == 0 and receipt.scientific_status == "SCREEN_ONLY_NOT_VALIDATED"
    assert not (tmp_path / "artifacts" / f"{contract.experiment_hash}.json").exists()
    store = Store(tmp_path / "factory.sqlite")
    store.enqueue("research", payload, contract.experiment_hash)
    store.pause(False, "test")
    assert cycle(store, tmp_path)  # actual supervised child, not the monkeypatch
    assert store.rows("SELECT state FROM jobs") == [{"state": "COMPLETED"}]
    assert not store.rows("SELECT * FROM experiments")
    assert status(store)["screening"]["pruned_completed_jobs"] == 1
    assert store.rows("SELECT * FROM attempt_resources")
    (tmp_path / "artifacts" / "screens" / f"{contract.experiment_hash}.json").write_text("{}")
    with pytest.raises(ValueError, match="integrity mismatch"):
        verify_pruned(tmp_path, contract, first)


def test_selected_rejection_runs_authoritative_native_audit(tmp_path):
    payload, contract = prepared(tmp_path, True)
    value = worker.run(payload, tmp_path)
    result = value["result"]
    assert result["tier0_screen"]["decision"] == "AUDIT_NO_SIGNALS"
    assert result["tier0_audit"] == {"passed": True, "false_negative": False}
    assert not result["fills"] and not result["trades"] and result["quote_count"] == 60
    with pytest.raises(ValueError, match="native replay"):
        verify_pruned(tmp_path, contract, {"screen": result["tier0_screen"]})


def test_false_negative_is_quarantined_never_promoted(tmp_path, monkeypatch):
    payload, contract = prepared(tmp_path, True, signals=True)
    # Inject a broken screen. Real compiler + real Nautilus must contradict it.
    monkeypatch.setattr(worker, "screen", lambda signals, contract: screen([], contract))
    with pytest.raises(ValueError, match="TIER0_FALSE_NEGATIVE"):
        worker.run(payload, tmp_path)
    failed = list((tmp_path / "artifacts" / "failed").glob("*.json"))
    assert len(failed) == 1
    evidence = json.loads(failed[0].read_text())
    assert evidence["result"]["tier0_audit"]["false_negative"]
    assert not (tmp_path / "artifacts" / f"{contract.experiment_hash}.json").exists()


def test_training_feedback_prunes_without_an_objective_or_run(tmp_path):
    payload = seed(tmp_path, 60)
    base = dict(
        dataset_hash=payload["contract"]["dataset_hash"],
        profile=InstrumentSpec.model_validate(payload["profile"]),
        window=Window.model_validate(payload["contract"]["windows"][0]),
        family="momentum",
        timeframe="H1",
        code_revision=payload["contract"]["code_revision"],
        max_trials=1,
    )
    for seed_value in range(1024):
        p = SearchProtocol(**base, seed=seed_value)
        params = rebuild_study(p, [], 0).ask(fixed_distributions=p.distributions()).params
        if not selected_for_audit(p.contract(p.strategy(params))):
            break
    else:
        raise AssertionError("missing non-audited deterministic protocol")
    store = Store(tmp_path / "factory.sqlite")
    search = Search(store, tmp_path)
    identity = search.register(p)
    trial = search.ask(identity)
    search.enqueue_pending()
    store.pause(False, "test")
    assert cycle(store, tmp_path)
    assert search.feedback() == 1
    outcome = store.rows("SELECT * FROM search_outcomes")[0]
    assert outcome["outcome"] == "PRUNED" and outcome["reason"] == "EXACT_NO_SIGNALS_TIER0"
    assert outcome["objective"] is None and outcome["run_id"] is None and outcome["cpu_seconds"] > 0
    assert not store.rows("SELECT * FROM experiments")
    assert (
        store.rows("SELECT strategy_id FROM strategy_specs")[0]["strategy_id"]
        == trial["spec"].strategy_hash
    )
    assert not Search(Store(tmp_path / "factory.sqlite"), tmp_path).pending()


def test_oos_and_forged_positive_rejection_are_rejected(tmp_path):
    payload, contract = prepared(tmp_path, False)
    w = contract.windows[0].model_copy(update={"role": "selection_oos"})
    with pytest.raises(ValueError, match="training-only"):
        screen([], contract.model_copy(update={"windows": (w,)}))
    receipt = screen([{"available_at": contract.windows[0].start_ns, "side": "BUY"}], contract)
    assert receipt.decision == "PASS_TO_NATIVE"
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="cannot prune"):
        type(receipt).model_validate({**receipt.model_dump(), "decision": "PRUNE_NO_SIGNALS"})
