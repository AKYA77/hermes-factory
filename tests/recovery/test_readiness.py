from factory.operations.readiness import SOFTWARE_GATES, DATA_GATES, OPERATION_GATES, readiness
from factory.data import sha256


def test_software_handoff_does_not_require_bulk_data(tmp_path):
    receipt = tmp_path / "receipt"
    receipt.write_text("unit fixture verification receipt")
    check = {"status": "PASS", "receipt": "receipt", "sha256": sha256(receipt)}
    evidence = {g: check for g in SOFTWARE_GATES}
    state = readiness(tmp_path, evidence)
    assert state["SOFTWARE_VERIFIED"] and not state["DATA_READY"] and not state["OPERATION_READY"]
    evidence.update({g: check for g in DATA_GATES + OPERATION_GATES})
    assert readiness(tmp_path, evidence)["OPERATION_READY"]
    receipt.write_text("changed")
    assert not readiness(tmp_path, evidence)["SOFTWARE_VERIFIED"]


def test_no_missing_or_unreceipted_gate_is_passed(tmp_path):
    assert not readiness(tmp_path, {})["SOFTWARE_VERIFIED"]
    assert not readiness(tmp_path, {g: {"status": "PASS"} for g in SOFTWARE_GATES})[
        "SOFTWARE_VERIFIED"
    ]
