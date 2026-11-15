"""Independent confirmation binds a training improvement to a disjoint evaluation."""

import json

import pytest

from apps.coordinator.service import cycle
from factory.contracts import ExperimentContract, fingerprint
from factory.data import atomic_bytes, sha256, serialize
from factory.experiments import Store
from factory.improvement.confirmation import ATTESTATION, Confirmation, ConfirmationRequest
from factory.improvement.service import Improvement, ImprovementPolicy
from test_improvement import parent_run


def insert_evaluation(store, root, contract, result):
    """TEST_ONLY fixture helper: evaluation_results is append-only by design."""
    encoded = serialize(result).encode()
    atomic_bytes(root / "artifacts" / "evaluations" / (contract.experiment_hash + ".json"), encoded)
    digest = sha256(root / "artifacts" / "evaluations" / (contract.experiment_hash + ".json"))
    with store.transaction() as db:
        db.execute(
            "INSERT OR IGNORE INTO evaluation_results VALUES(?,?,?,?,?,?)",
            (
                contract.experiment_hash,
                serialize(contract),
                serialize(result),
                digest,
                None,
                0.0,
            ),
        )


def synthetic_improved_edge(store, edge, plan_hash):
    """TEST_ONLY fixture: force a promoted outcome so the evaluation guards run."""
    identity = "e" * 64
    with store.transaction() as db:
        db.execute(
            "INSERT OR IGNORE INTO improvement_edges VALUES(?,?,?,?,?,?,?,?)",
            (
                identity,
                plan_hash,
                edge["child_strategy_hash"],
                "f" * 64,
                edge["payload_json"],
                "TEST_ONLY forced promotion",
                "[]",
                0.0,
            ),
        )
        db.execute(
            "INSERT OR IGNORE INTO improvement_outcomes VALUES(?,?,?,?,?)",
            (identity, "TRAIN_IMPROVED_ONLY", "{}", 1.0, 0.0),
        )
    return identity


def evaluation_result(contract):
    return {
        "contract_hash": contract.experiment_hash,
        "synthetic": False,
        "windows": [],
        "ending_equity": "21",
        "integrity_errors": [],
    }


def test_confirmation_requires_disjoint_independent_evaluation(tmp_path):
    store, identity, parent = parent_run(tmp_path)
    policy = ImprovementPolicy(search_protocol_hash=identity, max_parent_plans=1, max_children=2)
    service = Improvement(store, tmp_path)
    service.register(policy)
    assert service.discover() == 1
    for _ in range(5):
        cycle(Store(tmp_path / "factory.sqlite"), tmp_path)
    service = Improvement(Store(tmp_path / "factory.sqlite"), tmp_path)
    service.feedback()
    edge = store.rows("SELECT * FROM improvement_edges")[0]
    plan_hash = edge["plan_hash"]
    payload = json.loads(edge["payload_json"])
    child = ExperimentContract.model_validate(payload["contract"])
    confirmation = Confirmation(store, tmp_path)

    # A tiny fixture never promotes, so a real outcome cannot be confirmed.
    with pytest.raises(ValueError, match="TRAIN_IMPROVED_ONLY"):
        confirmation.confirm(
            ConfirmationRequest(
                edge_id=edge["edge_id"],
                evaluation_id="a" * 64,
                authorized_by="confirmation acceptance",
                attestation=ATTESTATION,
            )
        )
    with pytest.raises(ValueError, match="unknown improvement edge"):
        confirmation.confirm(
            ConfirmationRequest(
                edge_id="a" * 64,
                evaluation_id="a" * 64,
                authorized_by="confirmation acceptance",
                attestation=ATTESTATION,
            )
        )

    promoted = synthetic_improved_edge(store, edge, plan_hash)

    # A self-evaluation is refused: insert it, then confirm it cannot be used.
    self_evaluation = child.model_copy(update={"windows": child.windows})
    insert_evaluation(store, tmp_path, self_evaluation, evaluation_result(self_evaluation))
    with pytest.raises(ValueError, match="cannot confirm its own training experiment"):
        confirmation.confirm(
            ConfirmationRequest(
                edge_id=promoted,
                evaluation_id=child.experiment_hash,
                authorized_by="confirmation acceptance",
                attestation=ATTESTATION,
            )
        )
    # Unknown evaluation is refused.
    with pytest.raises(ValueError, match="unknown independent evaluation"):
        confirmation.confirm(
            ConfirmationRequest(
                edge_id=promoted,
                evaluation_id="d" * 64,
                authorized_by="confirmation acceptance",
                attestation=ATTESTATION,
            )
        )

    # A disjoint evaluation on the SAME admitted dataset confirms.
    later = child.windows[0].end_ns + 86400 * 10**9
    disjoint = child.model_copy(
        update={
            "windows": (
                type(child.windows[0])(
                    start_ns=later, end_ns=later + 60 * 10**9, role="report_only"
                ),
            )
        }
    )
    insert_evaluation(store, tmp_path, disjoint, evaluation_result(disjoint))
    report = confirmation.confirm(
        ConfirmationRequest(
            edge_id=promoted,
            evaluation_id=disjoint.experiment_hash,
            authorized_by="confirmation acceptance",
            attestation=ATTESTATION,
        )
    )
    assert report["windows_disjoint"] and report["same_admitted_dataset"]
    assert report["confirmed"] is True and report["qualification_authorized"] is False
    assert report["descriptive_only"] is True
    digest = fingerprint(report)
    path = tmp_path / "artifacts" / "confirmations" / (digest + ".json")
    assert path.exists() and sha256(path) == digest

    # An overlapping evaluation is refused.
    overlapping = child.model_copy(
        update={
            "windows": (
                type(child.windows[0])(
                    start_ns=child.windows[0].start_ns,
                    end_ns=child.windows[0].end_ns,
                    role="report_only",
                ),
            )
        }
    )
    insert_evaluation(store, tmp_path, overlapping, evaluation_result(overlapping))
    with pytest.raises(ValueError, match="overlaps the training window"):
        confirmation.confirm(
            ConfirmationRequest(
                edge_id=promoted,
                evaluation_id=overlapping.experiment_hash,
                authorized_by="confirmation acceptance",
                attestation=ATTESTATION,
            )
        )

    # An evaluation on a different canonical dataset is refused.
    other = disjoint.model_copy(update={"dataset_hash": "f" * 64})
    insert_evaluation(store, tmp_path, other, evaluation_result(other))
    with pytest.raises(ValueError, match="same admitted canonical dataset"):
        confirmation.confirm(
            ConfirmationRequest(
                edge_id=promoted,
                evaluation_id=other.experiment_hash,
                authorized_by="confirmation acceptance",
                attestation=ATTESTATION,
            )
        )
