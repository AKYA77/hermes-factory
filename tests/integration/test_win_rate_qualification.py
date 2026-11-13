"""R07 end to end: an absolute post-cost win-rate floor gates qualification."""

from decimal import Decimal as D
import json

from factory.experiments import Store
from apps.coordinator.service import cycle
from test_positive_validation_reference import positive_reference


def _run_to_report(tmp_path):
    store = Store(tmp_path / "factory.sqlite")
    from factory.validation.protocol import ValidationController

    identity = ValidationController(store, tmp_path).register(positive_reference(tmp_path))
    store.pause(False, "win-rate-gate-test")
    for _ in range(80):
        cycle(Store(tmp_path / "factory.sqlite"), tmp_path, timeout=120)
        rows = store.rows(
            "SELECT report_json FROM validation_protocol_reports WHERE protocol_id=?", (identity,)
        )
        if rows:
            break
    return identity, (json.loads(rows[0]["report_json"]) if rows else None), store


def test_default_floor_is_reported_by_the_real_pipeline(tmp_path):
    """The default 50% floor reaches the stored decision without disturbing a reference."""
    _, report, _ = _run_to_report(tmp_path)
    assert report is not None
    decision = report["decision"]
    assert decision["min_win_rate"] == str(D("0.5"))
    assert decision["win_rate_gate_passed"] is True
    assert report["status"] == "VALIDATED_REFERENCE", report


def test_candidates_and_rejection_records_remain_queryable(tmp_path):
    """A registered protocol and its report survive; nothing is deleted on rejection."""
    identity, report, store = _run_to_report(tmp_path)
    assert report is not None
    assert store.rows("SELECT * FROM validation_protocols WHERE protocol_id=?", (identity,)), (
        "the candidate disappeared from the evidence database"
    )
    assert store.rows(
        "SELECT * FROM validation_protocol_reports WHERE protocol_id=?", (identity,)
    ), "the decision record disappeared"
