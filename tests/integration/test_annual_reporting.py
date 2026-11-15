"""Annual and pooled reporting over retained independent evaluations."""

import json


from factory.contracts import ExperimentContract, Window, fingerprint
from factory.data import atomic_bytes, sha256, serialize
from factory.validation.annual import ATTESTATION, AnnualReporting, AnnualReportingRequest
from test_improvement import parent_run


def insert_evaluation(store, root, contract, result):
    """TEST_ONLY fixture helper: evaluation_results is append-only by design."""
    encoded = serialize(result).encode()
    atomic_bytes(root / "artifacts" / "evaluations" / (contract.experiment_hash + ".json"), encoded)
    digest = sha256(root / "artifacts" / "evaluations" / (contract.experiment_hash + ".json"))
    with store.transaction() as db:
        db.execute(
            "INSERT OR IGNORE INTO evaluation_results VALUES(?,?,?,?,?,?)",
            (contract.experiment_hash, serialize(contract), serialize(result), digest, None, 0.0),
        )


def test_annual_and_pooled_aggregates(tmp_path):
    store, identity, parent = parent_run(tmp_path)
    row = store.rows("SELECT contract_json, result_json FROM experiments")[0]
    base = ExperimentContract.model_validate_json(row["contract_json"])
    replay = json.loads(row["result_json"])
    windows = (
        Window(start_ns=1748736000 * 10**9, end_ns=1748739600 * 10**9, role="report_only"),
        Window(start_ns=1780272000 * 10**9, end_ns=1780275600 * 10**9, role="report_only"),
    )
    for window in windows:
        contract = base.model_copy(update={"windows": (window,)})
        result = {
            "contract_hash": contract.experiment_hash,
            "synthetic": False,
            "integrity_errors": [],
            "windows": [{"replay": replay}],
        }
        insert_evaluation(store, tmp_path, contract, result)

    service = AnnualReporting(store, tmp_path)
    report = service.report(
        AnnualReportingRequest(authorized_by="annual reporting acceptance", attestation=ATTESTATION)
    )
    assert report["evaluations"] == 2
    assert set(report["by_year"]) == {"2025", "2026"}
    assert report["by_year"]["2025"]["windows"] == 1
    assert report["by_year"]["2026"]["windows"] == 1
    assert report["pooled"]["windows"] == 2
    assert report["pooled"]["trades"] == sum(year["trades"] for year in report["by_year"].values())
    assert report["pooled"]["win_rate"] is not None
    assert report["qualification_authorized"] is False
    assert report["descriptive_only"] is True
    digest = fingerprint(report)
    path = tmp_path / "artifacts" / "annual-reporting" / (digest + ".json")
    assert path.exists() and sha256(path) == digest
    assert (
        fingerprint(
            service.report(
                AnnualReportingRequest(
                    authorized_by="annual reporting acceptance", attestation=ATTESTATION
                )
            )
        )
        == digest
    )


def test_annual_reporting_handles_no_evaluations(tmp_path):
    store, identity, parent = parent_run(tmp_path)
    report = AnnualReporting(store, tmp_path).report(
        AnnualReportingRequest(authorized_by="annual reporting acceptance", attestation=ATTESTATION)
    )
    assert report["evaluations"] == 0 and report["by_year"] == {}
    assert report["pooled"]["trades"] == 0
    assert report["pooled"]["win_rate"] is None
