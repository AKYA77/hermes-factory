import pytest
from fastapi.testclient import TestClient
from apps.api.main import create_app
from apps.coordinator.worker import run
from factory.operations.fixtures import seed
from factory.validation.evaluate import evaluate


def test_old_execution_contracts_not_reinterpreted(tmp_path):
    payload = seed(tmp_path, 120)
    payload["contract"]["fill_version"] = "adverse-fill/v1"
    with pytest.raises(ValueError, match="legacy contracts are read-only"):
        run(payload, tmp_path)
    with pytest.raises(ValueError, match="legacy contracts are read-only"):
        evaluate(tmp_path / "catalog", payload)


def test_api_rejects_obsolete_execution_before_queue(tmp_path):
    import hashlib
    import json

    payload = seed(tmp_path, 120)
    payload["contract"]["fill_version"] = "adverse-fill/v1"
    (tmp_path / "access.json").write_text(
        json.dumps([{"role": "operator", "sha256": hashlib.sha256(b"fixture").hexdigest()}])
    )
    app = create_app(tmp_path)
    with TestClient(app) as c:
        response = c.post(
            "/api/v1/research/propose", json=payload, headers={"Authorization": "Bearer fixture"}
        )
        assert response.status_code == 422
    assert not app.state.store.rows("SELECT * FROM jobs")


def test_mislabeled_instrument_does_not_get_official_result(tmp_path):
    from factory.contracts import InstrumentSpec, fingerprint

    payload = seed(tmp_path, 120)
    from factory.instruments import synthetic_profile

    payload["profile"] = synthetic_profile("GBPUSD").model_dump(mode="json")
    payload["contract"]["instrument_hash"] = fingerprint(
        InstrumentSpec.model_validate(payload["profile"])
    )
    with pytest.raises(ValueError, match="instrument identity mismatch"):
        run(payload, tmp_path)


def test_current_boards_exclude_legacy_runs_but_history_remains(tmp_path):
    from factory.contracts import ExperimentContract, StrategySpec, fingerprint
    from factory.experiments import Store
    from factory.ranking import leaderboard

    payload = seed(tmp_path, 120)
    store = Store(tmp_path / "factory.sqlite")
    spec = StrategySpec.model_validate(payload["strategy"])
    current = ExperimentContract.model_validate(payload["contract"])
    old = ExperimentContract.model_validate(
        {**payload["contract"], "fill_version": "adverse-fill/v1"}
    )
    # Explicit synthetic empty-result fixtures test view selection, not metrics.
    empty = {"synthetic": True, "trades": []}
    store.complete_experiment(old, spec, empty, fingerprint(empty))
    assert leaderboard(store, "EURUSD")["candidates"] == []
    legacy = leaderboard(store, "EURUSD", execution_version="adverse-fill/v1")
    assert len(legacy["candidates"]) == 1 and legacy["legacy_evidence"]
    assert (
        leaderboard(store, "EURUSD", True, execution_version="adverse-fill/v1")["candidates"] == []
    )
    store.complete_experiment(current, spec, empty, fingerprint(empty))
    board = leaderboard(store, "EURUSD")
    assert (
        len(board["candidates"]) == 1
        and board["candidates"][0]["run_id"] == current.experiment_hash
    )
    assert board["excluded_other_execution_runs"] == 1
    assert len(store.rows("SELECT * FROM experiments")) == 2


def test_source_claim_must_match_actual_checkout_content(tmp_path):
    payload = seed(tmp_path, 120)
    payload["contract"]["code_revision"] = "invented-git-commit"
    with pytest.raises(ValueError, match="source revision mismatch"):
        run(payload, tmp_path)


def test_integrity_failure_preserves_quarantined_evidence(tmp_path, monkeypatch):
    """Fault-injection fixture: injected results must never become official metrics."""
    import json
    import apps.coordinator.worker as module

    payload = seed(tmp_path, 120)
    from factory.contracts import ExperimentContract

    identity = ExperimentContract.model_validate(payload["contract"]).experiment_hash
    monkeypatch.setattr(
        module,
        "replay",
        lambda *args, **kwargs: {
            "integrity_errors": [{"reason": "FAULT_INJECTION"}],
            "trades": [],
            "fills": [],
            "quote_count": 0,
            "synthetic": True,
        },
    )
    with pytest.raises(ValueError, match="quarantined_artifact_sha256"):
        run(payload, tmp_path)
    assert not (tmp_path / "artifacts" / f"{identity}.json").exists()
    files = list((tmp_path / "artifacts" / "failed").glob("*.json"))
    assert len(files) == 1
    quarantine = json.loads(files[0].read_text())
    assert quarantine["experiment_hash"] == identity
    assert quarantine["status"] == "QUARANTINED_EXECUTION_CONTRACT_MISMATCH"
