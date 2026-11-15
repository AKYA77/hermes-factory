"""Typed comparability contracts attached to retained evidence."""

import pytest

from factory.contracts import fingerprint
from factory.data import sha256
from factory.validation.comparability_contract import (
    ATTESTATION,
    ComparabilityContractRequest,
    ComparabilityContracts,
)
from test_improvement import parent_run

PEER = "a" * 64


def test_contract_registers_and_is_idempotent(tmp_path):
    store, identity, parent = parent_run(tmp_path)
    service = ComparabilityContracts(store, tmp_path)
    request = ComparabilityContractRequest(
        instrument="EURUSD",
        dataset_hash="b" * 64,
        evaluation_start_ns=1748736000 * 10**9,
        evaluation_end_ns=1748739600 * 10**9,
        comparable_with=(PEER,),
        authorized_by="comparability acceptance",
        attestation=ATTESTATION,
    )
    report = service.report(request)
    assert report["already_registered"] is False
    assert report["comparable_with"] == [PEER]
    assert report["protected_windows"] == []
    assert report["descriptive_only"] is True
    assert report["qualification_authorized"] is False
    digest = fingerprint(report)
    path = tmp_path / "artifacts" / "comparability-contracts" / (digest + ".json")
    assert path.exists() and sha256(path) == digest
    second = service.report(request)
    assert second["already_registered"] is True
    assert second["context_hash"] == report["context_hash"]
    rows = store.rows("SELECT contract_hash FROM comparability_contracts")
    assert [row["contract_hash"] for row in rows] == [report["context_hash"]]


def test_contract_refuses_protected_window_overlap(tmp_path):
    store, identity, parent = parent_run(tmp_path)
    with pytest.raises(ValueError, match="overlaps a protected window"):
        ComparabilityContractRequest(
            instrument="EURUSD",
            dataset_hash="b" * 64,
            evaluation_start_ns=100,
            evaluation_end_ns=200,
            protected_windows=((150, 300),),
            authorized_by="comparability acceptance",
            attestation=ATTESTATION,
        )
    with pytest.raises(ValueError, match="must end after it starts"):
        ComparabilityContractRequest(
            instrument="EURUSD",
            dataset_hash="b" * 64,
            evaluation_start_ns=200,
            evaluation_end_ns=100,
            authorized_by="comparability acceptance",
            attestation=ATTESTATION,
        )
