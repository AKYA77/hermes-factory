"""Global candidate-selection funnel over retained evidence."""

from factory.contracts import fingerprint
from factory.data import sha256
from factory.screening.historical_cohorts import HistoricalCohorts
from factory.validation.selection_funnel import (
    ATTESTATION,
    SelectionFunnel,
    SelectionFunnelRequest,
)
from test_historical_cohorts import prepared
from test_improvement import parent_run


def test_selection_funnel_reports_retained_counts(tmp_path):
    store, identity, parent = parent_run(tmp_path)
    service = SelectionFunnel(store, tmp_path)
    report = service.report(
        SelectionFunnelRequest(authorized_by="funnel acceptance", attestation=ATTESTATION)
    )
    assert report["descriptive_only"] is True
    assert report["qualification_authorized"] is False
    assert report["search_trials"] >= 1
    assert report["distinct_effective_cohort_candidates"] == 0
    assert report["selected_for_native_audit"] == 0
    assert report["funnel_complete"] is False
    digest = fingerprint(report)
    path = tmp_path / "artifacts" / "selection-funnel" / (digest + ".json")
    assert path.exists() and sha256(path) == digest
    assert (
        fingerprint(
            service.report(
                SelectionFunnelRequest(authorized_by="funnel acceptance", attestation=ATTESTATION)
            )
        )
        == digest
    )


def test_selection_funnel_counts_retained_cohort_members(tmp_path):
    store, request, calibration, prospective, admission = prepared(tmp_path)
    HistoricalCohorts(store, tmp_path).freeze(request)
    report = SelectionFunnel(store, tmp_path).report(
        SelectionFunnelRequest(authorized_by="funnel acceptance", attestation=ATTESTATION)
    )
    assert report["distinct_effective_cohort_candidates"] == 1
    assert report["selected_for_native_audit"] == 1
    assert report["selected_and_observed"] == 0
    assert report["funnel_complete"] is False
    assert report["training_promotions"] == 0
