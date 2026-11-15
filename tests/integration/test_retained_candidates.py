"""Retained rejected candidates; nothing is silently discarded."""

import json

import pytest

from factory.contracts import ExperimentContract, fingerprint
from factory.data import sha256
from factory.ranking.retained import (
    ATTESTATION,
    RetainedCandidates,
    RetainedCandidatesRequest,
)
from test_improvement import parent_run


def test_every_candidate_is_retained_with_its_reason(tmp_path):
    store, identity, parent = parent_run(tmp_path)
    service = RetainedCandidates(store, tmp_path)
    report = service.report(
        RetainedCandidatesRequest(
            instrument="EURUSD",
            authorized_by="retention acceptance",
            attestation=ATTESTATION,
        )
    )
    assert report["total"] == 1
    assert report["eligible"] == 1
    assert report["retained_rejected"] == 0
    assert report["candidates"][0]["strategy_id"] == parent["strategy_id"]
    assert report["candidates"][0]["metrics"]["completed_trades"] >= 0
    assert report["descriptive_only"] is True
    assert report["qualification_authorized"] is False
    digest = fingerprint(report)
    path = tmp_path / "artifacts" / "retained-candidates" / (digest + ".json")
    assert path.exists() and sha256(path) == digest


def test_rejected_candidates_are_not_silently_discarded(tmp_path):
    store, identity, parent = parent_run(tmp_path)
    # A candidate under a different scenario and an older fill version.
    contract = ExperimentContract.model_validate_json(parent["contract_json"])
    altered = contract.model_copy(
        update={
            "scenario": "synthetic-training/v1",
            "fill_version": "legacy-fill/v0",
        }
    )
    result = json.loads(parent["result_json"])
    with store.transaction() as db:
        db.execute(
            "INSERT OR IGNORE INTO experiments VALUES(?,?,?,?,?,?,?,?,?)",
            (
                altered.experiment_hash + "x",
                altered.experiment_hash + "x",
                parent["strategy_id"],
                parent["instrument"],
                json.dumps(altered.model_dump(mode="json")),
                json.dumps(result),
                "0" * 64,
                "FAILED_CHECKS",
                1.0,
            ),
        )
    report = RetainedCandidates(store, tmp_path).report(
        RetainedCandidatesRequest(
            instrument="EURUSD",
            authorized_by="retention acceptance",
            attestation=ATTESTATION,
        )
    )
    assert report["total"] == 2
    assert report["retained_rejected"] == 1
    rejected = report["candidates"][0]
    assert rejected["leaderboard_eligible"] is False
    assert rejected["status"] == "FAILED_CHECKS"
    assert set(rejected["exclusion_reasons"]) == {
        "EXECUTION_VERSION_MISMATCH",
        "NON_PESSIMISTIC_SCENARIO",
        "FAILED_CHECKS",
    }
    assert report["exclusion_reason_counts"]["FAILED_CHECKS"] == 1
    # The poor training score is still reported with its metrics.
    assert "metrics" in rejected


def test_unknown_instrument_is_refused(tmp_path):
    store, identity, parent = parent_run(tmp_path)
    with pytest.raises(ValueError, match="unknown instrument"):
        RetainedCandidates(store, tmp_path).report(
            RetainedCandidatesRequest(
                instrument="NOPE",
                authorized_by="retention acceptance",
                attestation=ATTESTATION,
            )
        )
