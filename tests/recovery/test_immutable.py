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
