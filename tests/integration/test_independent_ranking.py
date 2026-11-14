"""Qualified ranking over independently evaluated candidates."""

import json

from factory.contracts import ExperimentContract, Window, fingerprint, serialize
from factory.data import atomic_bytes, sha256
from factory.ranking.independent import (
    ATTESTATION,
    IndependentRanking,
    IndependentRankingRequest,
)
from test_annual_reporting import insert_evaluation
from test_improvement import parent_run

WINDOWS = (
    Window(start_ns=1748736000 * 10**9, end_ns=1748739600 * 10**9, role="report_only"),
    Window(start_ns=1780272000 * 10**9, end_ns=1780275600 * 10**9, role="report_only"),
)


def insert_experiment(store, root, parent_row, contract, result):
    """TEST_ONLY fixture helper: experiments is append-only by design."""
    payload = root / "artifacts" / "experiments" / (contract.experiment_hash + ".json")
    atomic_bytes(payload, serialize(result).encode())
    with store.transaction() as db:
        db.execute(
            "INSERT OR IGNORE INTO experiments VALUES(?,?,?,?,?,?,?,?,?)",
            (
                contract.experiment_hash,
                contract.experiment_hash,
                parent_row["strategy_id"],
                parent_row["instrument"],
                serialize(contract),
                serialize(result),
                sha256(payload),
                "VALIDATED",
                0.0,
            ),
        )


def seed_evaluation(store, root, parent_row, contract, replay, synthetic):
    result = {
        "contract_hash": contract.experiment_hash,
        "synthetic": synthetic,
        "integrity_errors": [],
        "windows": [{"replay": replay}],
    }
    insert_experiment(store, root, parent_row, contract, replay)
    insert_evaluation(store, root, contract, result)


def test_independent_ranking_ranks_retained_evaluations(tmp_path):
    store, identity, parent = parent_run(tmp_path)
    base = ExperimentContract.model_validate_json(parent["contract_json"])
    replay = json.loads(parent["result_json"])
    for window in WINDOWS:
        seed_evaluation(
            store, tmp_path, parent, base.model_copy(update={"windows": (window,)}), replay, False
        )

    service = IndependentRanking(store, tmp_path)
    report = service.report(
        IndependentRankingRequest(authorized_by="ranking acceptance", attestation=ATTESTATION)
    )
    assert report["evaluations_considered"] == 2
    assert len(report["selected"]) == 2
    assert report["descriptive_only"] is True
    assert report["qualification_authorized"] is False
    digest = fingerprint(report)
    path = tmp_path / "artifacts" / "independent-ranking" / (digest + ".json")
    assert path.exists() and sha256(path) == digest


def test_independent_ranking_excludes_synthetic(tmp_path):
    store, identity, parent = parent_run(tmp_path)
    base = ExperimentContract.model_validate_json(parent["contract_json"])
    replay = json.loads(parent["result_json"])
    seed_evaluation(
        store, tmp_path, parent, base.model_copy(update={"windows": WINDOWS[:1]}), replay, True
    )
    report = IndependentRanking(store, tmp_path).report(
        IndependentRankingRequest(authorized_by="ranking acceptance", attestation=ATTESTATION)
    )
    assert report["evaluations_considered"] == 0
    assert report["selected"] == []
    assert report["diversity_counts"] == {}
