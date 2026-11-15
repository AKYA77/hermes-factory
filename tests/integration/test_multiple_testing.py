"""Multiple-testing corrections over retained candidate evidence."""

from decimal import Decimal as D

import pytest

from factory.contracts import fingerprint
from factory.data import sha256
from factory.experiments import Store
from factory.validation.multiple_testing import (
    ATTESTATION,
    MultipleTesting,
    MultipleTestingRequest,
    benjamini_hochberg,
    bonferroni,
)
from factory.validation.statistics import holm


def test_corrections_shrink_the_pass_set():
    p = [D("0.001"), D("0.01"), D("0.04"), D("0.20"), D("0.50")]
    assert bonferroni(p, D("0.05")) == {0, 1}
    assert benjamini_hochberg(p, D("0.10")) == {0, 1, 2}


def test_corrections_are_order_independent():
    p = [D("0.50"), D("0.001"), D("0.20"), D("0.01"), D("0.04")]
    assert bonferroni(p, D("0.05")) == {1, 3}
    assert benjamini_hochberg(p, D("0.10")) == {1, 3, 4}


def test_report_counts_and_is_immutable(tmp_path):
    ids = tuple(chr(ord("a") + index) * 64 for index in range(5))
    p_values = (D("0.001"), D("0.01"), D("0.04"), D("0.20"), D("0.50"))
    request = MultipleTestingRequest(
        candidate_ids=ids,
        p_values=p_values,
        authorized_by="multiple testing acceptance",
        attestation=ATTESTATION,
    )
    service = MultipleTesting(Store(tmp_path / "factory.sqlite"), tmp_path)
    report = service.report(request)
    assert report["candidates"] == 5
    assert report["uncorrected_passes"] == 3
    assert report["bonferroni_passes"] == 2
    assert report["benjamini_hochberg_passes"] == 3
    assert report["bonferroni_threshold"] == str(D("0.05") / D(5))
    assert report["qualification_authorized"] is False
    assert report["descriptive_only"] is True
    identity = fingerprint(report)
    path = tmp_path / "artifacts" / "multiple-testing" / (identity + ".json")
    assert path.exists() and sha256(path) == identity
    repeated = service.report(request)
    assert fingerprint(repeated) == identity


def test_misaligned_duplicate_or_out_of_range_input_is_refused(tmp_path):
    service = MultipleTesting(Store(tmp_path / "factory.sqlite"), tmp_path)
    with pytest.raises(ValueError, match="must align"):
        service.report(
            MultipleTestingRequest(
                candidate_ids=("a" * 64,),
                p_values=(D("0.1"), D("0.2")),
                authorized_by="x",
                attestation=ATTESTATION,
            )
        )
    with pytest.raises(ValueError, match="duplicate candidate"):
        service.report(
            MultipleTestingRequest(
                candidate_ids=("a" * 64, "a" * 64),
                p_values=(D("0.1"), D("0.2")),
                authorized_by="x",
                attestation=ATTESTATION,
            )
        )
    with pytest.raises(ValueError, match="p-values must lie"):
        service.report(
            MultipleTestingRequest(
                candidate_ids=("a" * 64,),
                p_values=(D("1.5"),),
                authorized_by="x",
                attestation=ATTESTATION,
            )
        )


def test_empty_family_rejects_nothing_consistently():
    """The three corrections must agree on an empty family.

    bonferroni divided by the family size and raised a bare
    decimal.DivisionByZero, while its siblings returned an empty result. The
    inconsistency was a trap for any caller that reached the helpers directly.
    """
    assert bonferroni([], D("0.05")) == set()
    assert benjamini_hochberg([], D("0.10")) == set()
    assert holm([], 0.05) == []
