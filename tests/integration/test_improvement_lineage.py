"""Descriptive improvement lineage reconstruction."""

import pytest

from apps.coordinator.service import cycle
from factory.contracts import fingerprint
from factory.data import sha256
from factory.experiments import Store
from factory.improvement.lineage import ATTESTATION, Lineage, LineageRequest
from factory.improvement.service import Improvement, ImprovementPolicy
from test_improvement import parent_run


def test_improvement_lineage_reconstructs_the_retained_tree(tmp_path):
    store, identity, parent = parent_run(tmp_path)
    policy = ImprovementPolicy(search_protocol_hash=identity, max_parent_plans=1, max_children=2)
    service = Improvement(store, tmp_path)
    policy_hash = service.register(policy)
    assert service.discover() == 1
    for _ in range(5):
        cycle(Store(tmp_path / "factory.sqlite"), tmp_path)
    service = Improvement(Store(tmp_path / "factory.sqlite"), tmp_path)
    service.feedback()

    lineage = Lineage(store, tmp_path)
    report = lineage.report(
        LineageRequest(
            policy_hash=policy_hash,
            authorized_by="lineage acceptance",
            attestation=ATTESTATION,
        )
    )
    assert report["descriptive_only"] is True and report["independently_validated"] is False
    assert report["plans"] == 1 and report["parents"] == 1
    assert report["children"] >= 1
    assert sum(report["outcome_statuses"].values()) == report["children"]
    assert report["lineage"][0]["parent_run_id"] == parent["run_id"]
    assert all(child["training_only"] for child in report["lineage"][0]["children"])
    assert all(child["changed_fields"] for child in report["lineage"][0]["children"])
    identity2 = fingerprint(report)
    path = tmp_path / "artifacts" / "lineage" / (identity2 + ".json")
    assert path.exists() and sha256(path) == identity2
    repeated = lineage.report(
        LineageRequest(
            policy_hash=policy_hash,
            authorized_by="lineage acceptance",
            attestation=ATTESTATION,
        )
    )
    assert fingerprint(repeated) == identity2
    with pytest.raises(ValueError, match="no retained improvement plans"):
        lineage.report(
            LineageRequest(
                policy_hash="b" * 64,
                authorized_by="lineage acceptance",
                attestation=ATTESTATION,
            )
        )
