"""Completion idempotency after a worker restart (T03)."""

import json

from factory.contracts import ExperimentContract, StrategySpec, fingerprint
from test_improvement import parent_run


def test_T03_completion_after_requeue_is_idempotent(tmp_path):
    store, identity, parent = parent_run(tmp_path)
    contract = ExperimentContract.model_validate_json(parent["contract_json"])
    spec = StrategySpec.model_validate_json(
        store.rows(
            "SELECT spec_json FROM strategy_specs WHERE strategy_id=?", (parent["strategy_id"],)
        )[0]["spec_json"]
    )
    result = json.loads(parent["result_json"])
    artifact_hash = fingerprint(result)
    experiments_before = len(store.rows("SELECT * FROM experiments"))
    audits_before = len(store.rows("SELECT * FROM cost_label_audits"))
    attempts_before = len(store.rows("SELECT * FROM attempts"))
    job = store.rows("SELECT * FROM jobs")[0]
    # Simulate a worker killed after the experiment row landed but before the job
    # was marked COMPLETED: the lease expires and the job is re-queued.
    with store.transaction() as db:
        db.execute(
            "UPDATE jobs SET state='QUEUED',lease_token=NULL,lease_until=NULL WHERE job_id=?",
            (job["job_id"],),
        )
    claimed = store.claim()
    assert claimed["job_id"] == job["job_id"]
    store.complete_experiment(
        contract, spec, result, artifact_hash, claimed["job_id"], claimed["lease_token"]
    )
    assert len(store.rows("SELECT * FROM experiments")) == experiments_before
    assert len(store.rows("SELECT * FROM cost_label_audits")) == audits_before
    assert len(store.rows("SELECT * FROM attempts")) == attempts_before + 1
    assert (
        store.rows("SELECT state FROM jobs WHERE job_id=?", (job["job_id"],))[0]["state"]
        == "COMPLETED"
    )
