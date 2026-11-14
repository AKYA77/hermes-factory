"""Descriptive candidate diversity for a registered search protocol."""

import pytest

from factory.contracts import fingerprint
from factory.data import sha256
from factory.exploration.diversity import ATTESTATION, Diversity, DiversityRequest
from test_improvement import parent_run


def test_candidate_diversity_reports_coverage(tmp_path):
    store, identity, parent = parent_run(tmp_path)
    service = Diversity(store, tmp_path)
    report = service.report(
        DiversityRequest(
            protocol_hash=identity,
            authorized_by="diversity acceptance",
            attestation=ATTESTATION,
        )
    )
    assert report["descriptive_only"] is True
    assert report["trials"] == 1
    assert report["outcomes"].get("COMPLETE") == 1
    assert report["distinct_parameter_sets"] == 1
    assert report["concentrated"] is True  # a single trial is 100% of the sample
    assert report["operators"] and report["timeframes"]
    assert report["parameter_coverage"]
    identity2 = fingerprint(report)
    path = tmp_path / "artifacts" / "diversity" / (identity2 + ".json")
    assert path.exists() and sha256(path) == identity2
    repeated = service.report(
        DiversityRequest(
            protocol_hash=identity,
            authorized_by="diversity acceptance",
            attestation=ATTESTATION,
        )
    )
    assert fingerprint(repeated) == identity2
    with pytest.raises(ValueError, match="no retained trials"):
        service.report(
            DiversityRequest(
                protocol_hash="c" * 64,
                authorized_by="diversity acceptance",
                attestation=ATTESTATION,
            )
        )
