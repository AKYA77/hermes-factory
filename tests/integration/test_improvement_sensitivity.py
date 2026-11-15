"""Descriptive parameter sensitivity for controlled parent-child comparisons."""

import pytest

from apps.coordinator.service import cycle
from factory.contracts import fingerprint
from factory.data import sha256
from factory.experiments import Store
from factory.improvement.service import Improvement, ImprovementPolicy
from factory.improvement.sensitivity import (
    ATTESTATION,
    Sensitivity,
    SensitivityRequest,
)
from test_improvement import parent_run


def test_parameter_sensitivity_reports_descriptive_grouping(tmp_path):
    store, identity, parent = parent_run(tmp_path)
    policy = ImprovementPolicy(search_protocol_hash=identity, max_parent_plans=1, max_children=2)
    service = Improvement(store, tmp_path)
    policy_hash = service.register(policy)
    assert service.discover() == 1
    for _ in range(5):
        cycle(Store(tmp_path / "factory.sqlite"), tmp_path)
    service = Improvement(Store(tmp_path / "factory.sqlite"), tmp_path)
    service.feedback()
    report = Sensitivity(store, tmp_path).report(
        SensitivityRequest(
            policy_hash=policy_hash,
            authorized_by="sensitivity acceptance",
            attestation=ATTESTATION,
        )
    )
    assert report["descriptive_only"] is True and report["independently_validated"] is False
    assert report["comparisons"] >= 1
    assert report["by_changed_field"]
    assert (
        sum(v["comparisons"] for v in report["by_changed_field"].values()) == report["comparisons"]
    )
    assert set(report["hypotheses"]) <= {
        "test stop distance with fixed 3R target",
        "test later signal context",
        "test closed daily trend confirmation",
        "test whether the last confirmation suppresses training opportunities",
    }
    identity2 = fingerprint(report)
    path = tmp_path / "artifacts" / "sensitivity" / (identity2 + ".json")
    assert path.exists() and sha256(path) == identity2
    repeated = Sensitivity(store, tmp_path).report(
        SensitivityRequest(
            policy_hash=policy_hash,
            authorized_by="sensitivity acceptance",
            attestation=ATTESTATION,
        )
    )
    assert fingerprint(repeated) == identity2
    with pytest.raises(ValueError, match="no retained improvement outcomes"):
        Sensitivity(store, tmp_path).report(
            SensitivityRequest(
                policy_hash="d" * 64,
                authorized_by="sensitivity acceptance",
                attestation=ATTESTATION,
            )
        )
