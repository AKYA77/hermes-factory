"""TEST_ONLY admission fixtures; never genuine historical verification."""

import pytest
from apps.coordinator.worker import run
from factory.contracts import ExperimentContract, StrategySpec
from factory.experiments import Store
from factory.screening.historical import ATTESTATION, HistoricalShadowRequest, diagnose
from test_reviewed_inputs import prepared


def test_admitted_shadow_preserves_native_and_is_idempotent(tmp_path):
    registry, payload, *_ = prepared(tmp_path)
    native = run(payload, tmp_path)
    c = ExperimentContract.model_validate(payload["contract"])
    s = StrategySpec.model_validate(payload["strategy"])
    store = Store(tmp_path / "factory.sqlite")
    store.complete_experiment(c, s, native["result"], native["artifact_hash"])
    path = tmp_path / "artifacts" / f"{c.experiment_hash}.json"
    before = path.read_bytes()
    req = HistoricalShadowRequest(
        experiment_hash=c.experiment_hash,
        profile=payload["profile"],
        authorized_by="TEST_ONLY",
        attestation=ATTESTATION,
    )
    body = diagnose(tmp_path, req)
    assert body == diagnose(tmp_path, req) and path.read_bytes() == before
    assert not body["approximate_pruning_authorized"] and body["estimate"]["signal_count"] > 0
    assert store.paused()
    assert (
        len(store.rows("SELECT * FROM audit_events WHERE action='historical_shadow_completed'"))
        == 1
    )
    admission = body["input_admission"]["admission_id"]
    registry.revoke(admission, "TEST_ONLY", "test revocation")
    with pytest.raises(ValueError):
        diagnose(tmp_path, req)


@pytest.mark.parametrize("corruption", ["native", "profile", "source"])
def test_diagnostic_rejects_changed_evidence(tmp_path, corruption):
    _, payload, *_ = prepared(tmp_path)
    native = run(payload, tmp_path)
    c = ExperimentContract.model_validate(payload["contract"])
    s = StrategySpec.model_validate(payload["strategy"])
    Store(tmp_path / "factory.sqlite").complete_experiment(
        c, s, native["result"], native["artifact_hash"]
    )
    req = HistoricalShadowRequest(
        experiment_hash=c.experiment_hash,
        profile=payload["profile"],
        authorized_by="TEST_ONLY",
        attestation=ATTESTATION,
    )
    if corruption == "profile":
        req = req.model_copy(update={"profile": req.profile.model_copy(update={"synthetic": True})})
    else:
        path = (
            tmp_path / "artifacts" / f"{c.experiment_hash}.json"
            if corruption == "native"
            else tmp_path / "catalog" / c.dataset_hash / "source.bin"
        )
        with path.open("ab") as f:
            f.write(b"corrupt")
    with pytest.raises(ValueError):
        diagnose(tmp_path, req)
    assert not (tmp_path / "artifacts" / "historical-shadow").exists()
