"""Prospective audit membership is immutable and cannot authorize approximation."""

from dataclasses import replace
import json
from decimal import Decimal
import sqlite3

import pytest

from apps.coordinator.worker import run
from apps.coordinator.service import cycle
from factory.contracts import ExperimentContract, StrategySpec, Window
from factory.data import Catalog
from factory.experiments import Store
from factory.screening.cohorts import ATTESTATION, CohortRequest, Cohorts
from test_cost_label_native_audit import counterexample


def prepared(tmp_path):
    payload, data = counterexample(tmp_path)
    native = run(payload, tmp_path)
    store = Store(tmp_path / "factory.sqlite")
    contract = ExperimentContract.model_validate(payload["contract"])
    spec = StrategySpec.model_validate(payload["strategy"])
    store.complete_experiment(contract, spec, native["result"], native["artifact_hash"])
    later = [
        replace(
            q,
            event_ts_utc_ns=q.event_ts_utc_ns + 3 * 86400 * 10**9,
            ingest_batch_id="prospective-unseen-native",
        )
        for q in data
    ]
    manifest = Catalog(tmp_path / "catalog").commit(
        later,
        b"GENERATED later training audit",
        {
            "synthetic": True,
            "source": "generated chronological audit fixture",
            "license": "test only",
        },
    )
    jobs = []
    for stop in (60, 80):
        candidate = spec.model_copy(update={"stop_ticks": stop})
        c = contract.model_copy(
            update={
                "strategy_hash": candidate.strategy_hash,
                "dataset_hash": manifest["dataset_hash"],
                "windows": (
                    Window(
                        start_ns=later[0].event_ts_utc_ns,
                        end_ns=later[-1].event_ts_utc_ns + 1,
                        role="train_only",
                    ),
                ),
            }
        )
        proposal = {
            **payload,
            "strategy": candidate.model_dump(mode="json"),
            "contract": c.model_dump(mode="json"),
        }
        jobs.append(store.enqueue("research", proposal, c.experiment_hash))
    request = CohortRequest(
        calibration_experiments=(contract.experiment_hash,),
        prospective_job_ids=tuple(jobs),
        audit_sample_count=1,
        seed=31,
        authorized_by="generated cohort acceptance",
        attestation=ATTESTATION,
    )
    return store, request


def test_frozen_frame_random_audit_native_feedback_and_counterexample_fallback(tmp_path):
    store, request = prepared(tmp_path)
    service = Cohorts(store, tmp_path)
    identity = service.freeze(request)
    assert store.paused() and service.freeze(request) == identity
    first = service.report(identity)
    assert first["known_counterexamples"] == 1 and first["native_observed"] == 0
    assert first["disposition"] == "ALL_NATIVE_FALLBACK_COUNTEREXAMPLE"
    assert not first["approximate_pruning_authorized"]
    assert len(first["frozen"]["frame"]) == 2 and len(first["frozen"]["selected"]) == 1
    assert Cohorts(Store(store.path), tmp_path).report(identity) == first
    store.pause(False, "test")
    assert cycle(store, tmp_path) and cycle(store, tmp_path)
    report = service.report(identity)
    assert report["audit_complete"] and report["native_observed"] == 1
    assert report["prospective_rejections_audited"] == 1 and report["false_negatives"] == 1
    assert (
        report["descriptive_wilson_95"] is not None and not report["approximate_pruning_authorized"]
    )
    selected = report["frozen"]["selected"][0]
    result = json.loads(
        store.rows("SELECT result_json FROM experiments WHERE experiment_hash=?", (selected,))[0][
            "result_json"
        ]
    )
    assert result["frozen_screen_audit_cohort"] == identity and result["fills"]
    assert service.freeze(request) == identity  # restart retrieval does not manufacture new samples
    with store.transaction() as db:
        with pytest.raises(sqlite3.IntegrityError, match="immutable screen cohort"):
            db.execute("DELETE FROM screen_cohort_members WHERE cohort_id=?", (identity,))


def test_outcome_peeking_duplicate_sampling_and_embargo_are_rejected(tmp_path):
    store, request = prepared(tmp_path)
    # Start an attempt before freezing: no retrospective independent audit claim.
    assert store.claim() is not None
    with pytest.raises(ValueError, match="before any native attempt"):
        Cohorts(store, tmp_path).freeze(request)
    assert not store.rows("SELECT * FROM screen_cohorts")


def test_different_seed_cannot_reuse_prospective_membership(tmp_path):
    store, request = prepared(tmp_path)
    service = Cohorts(store, tmp_path)
    service.freeze(request)
    with pytest.raises(ValueError, match="already frozen"):
        service.freeze(request.model_copy(update={"seed": 32}))
    assert len(store.rows("SELECT * FROM screen_cohorts")) == 1


@pytest.mark.parametrize(
    "failure", ["embargo", "duplicate_effective", "artifact", "policy", "influenced"]
)
def test_unsafe_freeze_is_rejected_atomically(tmp_path, failure):
    from factory.screening.labels import CostHorizonPolicy
    from factory.validation.access import record_use

    store, request = prepared(tmp_path)
    if failure == "artifact":
        path = tmp_path / "artifacts" / (request.calibration_experiments[0] + ".json")
        with path.open("ab") as f:
            f.write(b"corrupt")
        match = "artifact integrity"
    elif failure == "policy":
        request = request.model_copy(update={"policy": CostHorizonPolicy(horizon_bars=6)})
        match = "current worker estimator"
    elif failure == "duplicate_effective":
        payload = json.loads(
            store.rows(
                "SELECT payload FROM jobs WHERE job_id=?", (request.prospective_job_ids[0],)
            )[0]["payload"]
        )
        payload["contract"]["seed"] += 1
        c = ExperimentContract.model_validate(payload["contract"])
        duplicate = store.enqueue("research", payload, c.experiment_hash)
        request = request.model_copy(
            update={"prospective_job_ids": (request.prospective_job_ids[0], duplicate)}
        )
        match = "duplicate effective"
    elif failure == "embargo":
        with store.transaction() as db:
            for identity in request.prospective_job_ids:
                payload = json.loads(
                    db.execute("SELECT payload FROM jobs WHERE job_id=?", (identity,)).fetchone()[0]
                )
                payload["contract"]["windows"][0]["start_ns"] = 1735689600 * 10**9
                db.execute(
                    "UPDATE jobs SET payload=? WHERE job_id=?", (json.dumps(payload), identity)
                )
        match = "24h label embargo"
    else:
        payload = json.loads(
            store.rows(
                "SELECT payload FROM jobs WHERE job_id=?", (request.prospective_job_ids[0],)
            )[0]["payload"]
        )
        c = ExperimentContract.model_validate(payload["contract"])
        w = c.windows[0]
        with store.transaction() as db:
            record_use(
                db,
                "EURUSD",
                "synthetic",
                c.dataset_hash,
                w.start_ns,
                w.end_ns,
                "evaluation-with-past-only-warmup",
                "external-evaluation-fixture",
            )
        match = "EVALUATION_WINDOW_EXCLUDED"
    with pytest.raises(ValueError, match=match):
        Cohorts(store, tmp_path).freeze(request)
    assert not store.rows("SELECT * FROM screen_cohorts")
    assert not store.rows("SELECT * FROM screen_cohort_members")


def test_api_roles_freeze_pause_and_report(tmp_path):
    import hashlib
    from fastapi.testclient import TestClient
    from apps.api.main import create_app

    store, request = prepared(tmp_path)
    (tmp_path / "access.json").write_text(
        json.dumps(
            [
                {"role": r, "sha256": hashlib.sha256(("test-" + r).encode()).hexdigest()}
                for r in ("viewer", "operator")
            ]
        )
    )
    client = TestClient(create_app(tmp_path))
    url = "/api/v1/research/screen-cohorts"
    assert client.get(url).status_code == 401
    assert (
        client.post(
            url,
            json=request.model_dump(mode="json"),
            headers={"Authorization": "Bearer test-viewer"},
        ).status_code
        == 403
    )
    headers = {"Authorization": "Bearer test-operator"}
    response = client.post(url, json=request.model_dump(mode="json"), headers=headers)
    assert response.status_code == 200, response.text
    identity = response.json()["cohort_id"]
    assert (
        store.paused()
        and client.get(url, headers=headers).json()["cohorts"][0]["cohort_id"] == identity
    )
    report = client.get(url + "/" + identity, headers=headers).json()
    assert not report["approximate_pruning_authorized"] and report["known_counterexamples"] == 1
    assert client.get(url + "?limit=101", headers=headers).status_code == 422
    assert (
        client.get("/api/v1/research/screen-cohort-inputs?limit=101", headers=headers).status_code
        == 422
    )


def test_selected_exact_zero_candidate_still_gets_authoritative_native_audit(tmp_path):
    store, request = prepared(tmp_path)
    for identity in request.prospective_job_ids:
        payload = json.loads(
            store.rows("SELECT payload FROM jobs WHERE job_id=?", (identity,))[0]["payload"]
        )
        spec = StrategySpec.model_validate(payload["strategy"])
        spec = spec.model_copy(
            update={"signal": spec.signal.model_copy(update={"threshold": Decimal("20")})}
        )
        payload["strategy"] = spec.model_dump(mode="json")
        payload["contract"]["strategy_hash"] = spec.strategy_hash
        # The fixture updates an unattempted descriptor before its cohort exists.
        with store.transaction() as db:
            db.execute("UPDATE jobs SET payload=? WHERE job_id=?", (json.dumps(payload), identity))
    service = Cohorts(store, tmp_path)
    identity = service.freeze(request)
    selected = service.report(identity)["frozen"]["selected"][0]
    store.pause(False, "test")
    assert cycle(store, tmp_path) and cycle(store, tmp_path)
    assert service.report(identity)["audit_complete"]
    result = json.loads(
        store.rows("SELECT result_json FROM experiments WHERE experiment_hash=?", (selected,))[0][
            "result_json"
        ]
    )
    assert result["frozen_screen_audit_cohort"] == identity and result["quote_count"] == 400
    assert result["tier0_screen"]["signal_count"] == 0 and result["tier0_audit"]["passed"]
    assert not result["fills"] and not result["cost_horizon_labels"]["pruning_authorized"]


def test_seed_only_copy_cannot_be_new_independent_observation_in_another_cohort(tmp_path):
    store, request = prepared(tmp_path)
    service = Cohorts(store, tmp_path)
    service.freeze(request)
    payload = json.loads(
        store.rows("SELECT payload FROM jobs WHERE job_id=?", (request.prospective_job_ids[0],))[0][
            "payload"
        ]
    )
    payload["contract"]["seed"] += 1
    c = ExperimentContract.model_validate(payload["contract"])
    alias = store.enqueue("research", payload, c.experiment_hash)
    with pytest.raises(ValueError, match="duplicate effective"):
        service.freeze(
            request.model_copy(
                update={"prospective_job_ids": (alias,), "audit_sample_count": 1, "seed": 33}
            )
        )
    assert len(store.rows("SELECT * FROM screen_cohorts")) == 1
    assert len(store.rows("SELECT * FROM screen_cohort_effective_inputs")) == 2
