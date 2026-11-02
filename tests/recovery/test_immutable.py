import sqlite3
import pytest
from factory.experiments import Store
from factory.operations.fixtures import seed
from factory.contracts import ExperimentContract, StrategySpec
from apps.coordinator.worker import run


def test_completion_cannot_be_overwritten(tmp_path):
    payload = seed(tmp_path, 120)
    store = Store(tmp_path / "factory.sqlite")
    contract = ExperimentContract.model_validate(payload["contract"])
    spec = StrategySpec.model_validate(payload["strategy"])
    result = run(payload, tmp_path)
    store.complete_experiment(contract, spec, result["result"], result["artifact_hash"])
    store.complete_experiment(contract, spec, result["result"], result["artifact_hash"])
    assert len(store.rows("SELECT * FROM experiments")) == 1
    with pytest.raises(sqlite3.IntegrityError):
        with store.transaction() as db:
            db.execute("UPDATE experiments SET result_json='{}'")


def test_stale_worker_cannot_commit_result(tmp_path):
    import time

    payload = seed(tmp_path, 120)
    store = Store(tmp_path / "factory.sqlite")
    contract = ExperimentContract.model_validate(payload["contract"])
    spec = StrategySpec.model_validate(payload["strategy"])
    result = run(payload, tmp_path)
    job_id = store.enqueue("research", payload, contract.experiment_hash)
    job = store.claim()
    with store.transaction() as db:
        db.execute("UPDATE jobs SET lease_until=? WHERE job_id=?", (time.time() - 1, job_id))
    with pytest.raises(ValueError, match="STALE_LEASE"):
        store.complete_experiment(
            contract, spec, result["result"], result["artifact_hash"], job_id, job["lease_token"]
        )
    assert not store.rows("SELECT * FROM experiments")
