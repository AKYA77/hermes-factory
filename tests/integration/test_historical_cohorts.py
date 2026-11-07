"""Historical prospective calibration cohorts; never approximate pruning.

These are generated TEST_ONLY authorization fixtures. They exercise the
historical admission branch and are not genuine market validation.
"""

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import pytest

from apps.coordinator.worker import run
from factory.contracts import (
    ExperimentContract,
    InstrumentSpec,
    Signal,
    StrategySpec,
    Window,
    fingerprint,
)
from factory.data import Catalog, Quote
from factory.data.admission import (
    AdmissionSpec,
    Citation,
    InputRegistry,
    ReferenceReview,
    PROFILE_FIELDS,
    CALENDAR_FIELDS,
    POLICY_PREFIX,
)
from factory.data.source_quality import SourceQuality, SourceQualityPolicy
from factory.instruments import synthetic_profile
from factory.instruments.calendar import CalendarSpec, SessionCalendar
from factory.provenance import execution_revision
from factory.screening.historical import diagnose
from factory.screening.historical_cohorts import (
    HISTORICAL_ATTESTATION,
    HistoricalCohortRequest,
    HistoricalCalibrationPolicy,
    HistoricalCohorts,
)
from factory.simulation.ledger import EXECUTION_VERSION

ATTEST = "I reviewed the captured references and their dated research scope"
DAY = 86400 * 10**9
MINUTE = 60 * 10**9


def long_prepared(root, minutes=3 * 24 * 60 + 240):
    """One reviewed dataset spanning both a calibration and a later prospective window."""
    root = Path(root)
    start = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1e9)
    quotes = []
    for i in range(minutes):
        bid = 110000 + int(220 * math.sin(i / 12))
        quotes.append(
            Quote(
                "EURUSD",
                start + i * MINUTE,
                bid,
                bid + 10,
                100000,
                "synthetic-sine/v1",
                "seed-v1",
                i,
                source_precision="minute-fixture",
            )
        )
    raw = "\n".join(f"{q.event_ts_utc_ns},{q.bid_int},{q.ask_int}" for q in quotes).encode()
    catalog = Catalog(root / "catalog")
    manifest = catalog.commit(
        quotes,
        raw,
        {
            "source": "TEST ONLY generated authorization fixture; not historical observations",
            "license": "project-generated test fixture",
            "synthetic": False,
        },
    )
    profile = synthetic_profile("EURUSD").model_copy(
        update={
            "synthetic": False,
            "source": "TEST ONLY generated profile reference; not approved broker facts",
        }
    )
    document = b"TEST ONLY generated research assumptions, not financial reference evidence"
    doc_hash = hashlib.sha256(document).hexdigest()
    tzif = Path("/usr/share/zoneinfo/UTC").read_bytes()
    window = Window(start_ns=start, end_ns=quotes[-1].event_ts_utc_ns + 1, role="train_only")
    calendar = CalendarSpec(
        instrument="EURUSD",
        version="TEST_ONLY/v1",
        timezone="UTC",
        tzif_sha256=hashlib.sha256(tzif).hexdigest(),
        source_document_sha256=doc_hash,
        source_citation="TEST ONLY 24/7 generated authorization calendar",
        effective_start_ns=window.start_ns,
        effective_end_ns=window.end_ns,
        weekly_sessions=({"start_second": 0, "end_second": 604800},),
        closures=(),
        ambiguous_boundary="reject",
    )
    registry = InputRegistry(root, catalog)
    base = {
        "effective_start_ns": window.start_ns,
        "effective_end_ns": window.end_ns,
        "reviewed_at_ns": 1793750400 * 10**9,
        "reviewer": "TEST_ONLY reviewer",
        "attestation": ATTEST,
    }
    citation = Citation(
        document_sha256=doc_hash,
        source="generated fixture",
        locator="TEST ONLY",
        interpretation="authorization test only",
        basis="explicit_research_assumption",
    )
    profile_id = registry.register_reference(
        ReferenceReview(profile=profile, citations={k: citation for k in PROFILE_FIELDS}, **base),
        {doc_hash: document},
    )
    calendar_id = registry.register_reference(
        ReferenceReview(
            calendar=calendar, citations={k: citation for k in CALENDAR_FIELDS}, **base
        ),
        {doc_hash: document},
        tzif=tzif,
    )
    quality = SourceQuality(root, catalog).run(
        manifest["dataset_hash"],
        SourceQualityPolicy(
            gap_threshold_ns=61 * 10**9,
            unchanged_threshold_ns=600 * 10**9,
            timestamp_quantum_ns=10**9,
            max_examples=2,
            max_events_bytes=1024**2,
            expected_start_ns=window.start_ns,
            expected_end_ns=window.end_ns,
        ),
        profile=profile,
        calendar=SessionCalendar(calendar, tzif),
    )
    spec = AdmissionSpec(
        quality_run_id=quality["run_id"],
        profile_review_id=profile_id,
        calendar_review_id=calendar_id,
        accepted_events_sha256=quality["events_sha256"],
        window=window,
        reviewer="TEST_ONLY reviewer",
        reviewed_at_ns=base["reviewed_at_ns"],
        source_acceptance_notes="Generated authorization fixture, NOT historical verification",
        attestation="I reviewed all source QA events and accept this research input scope",
    )
    identity = registry.register_admission(spec)
    return registry, catalog, manifest, profile, identity, start, quotes


def payload_for(profile, dataset_hash, start_ns, end_ns, seed=123):
    spec = StrategySpec(
        instrument="EURUSD",
        timeframe="M1",
        signal=Signal(operator="momentum", lookback=3, threshold="1"),
        stop_ticks=60,
    )
    contract = ExperimentContract(
        strategy_hash=spec.strategy_hash,
        dataset_hash=dataset_hash,
        instrument_hash=fingerprint(profile),
        engine_version="1.231.0",
        code_revision=execution_revision(),
        fill_version=EXECUTION_VERSION,
        evaluation_policy=POLICY_PREFIX + "0" * 64,
        scenario="historical-pessimistic/v1",
        windows=(Window(start_ns=start_ns, end_ns=end_ns, role="train_only"),),
        seed=seed,
    )
    return {
        "strategy": spec.model_dump(mode="json"),
        "profile": profile.model_dump(mode="json"),
        "contract": contract.model_dump(mode="json"),
    }


def prepared(tmp_path):
    registry, catalog, manifest, profile, admission, start, quotes = long_prepared(tmp_path)
    store = registry.store
    cal_start, cal_end = start, start + 120 * MINUTE
    payload = payload_for(profile, manifest["dataset_hash"], cal_start, cal_end)
    payload["contract"]["evaluation_policy"] = POLICY_PREFIX + admission
    contract = ExperimentContract.model_validate(payload["contract"])
    spec = StrategySpec.model_validate(payload["strategy"])
    native = run(payload, tmp_path)
    store.complete_experiment(contract, spec, native["result"], native["artifact_hash"])
    diagnose(
        tmp_path,
        {
            "experiment_hash": contract.experiment_hash,
            "profile": profile.model_dump(mode="json"),
            "authorized_by": "historical cohort acceptance",
            "attestation": (
                "Authorize training-only feature diagnostics and mandatory native evidence; "
                "no approximate pruning"
            ),
        },
    )
    # Later prospective window on the same admitted dataset, after the 24h embargo.
    pro_start = start + 3 * DAY
    pro_end = pro_start + 120 * MINUTE
    prospective = payload_for(profile, manifest["dataset_hash"], pro_start, pro_end, seed=124)
    prospective["contract"]["evaluation_policy"] = POLICY_PREFIX + admission
    pro_contract = ExperimentContract.model_validate(prospective["contract"])
    job_id = store.enqueue("research", prospective, pro_contract.experiment_hash)
    policy = HistoricalCalibrationPolicy(
        admission_id=admission,
        profile_hash=fingerprint(profile),
        dataset_hash=manifest["dataset_hash"],
        code_revision=execution_revision(),
        training_start_ns=cal_start,
        training_end_ns=cal_end,
    )
    request = HistoricalCohortRequest(
        policy=policy,
        calibration_experiments=(contract.experiment_hash,),
        prospective_job_ids=(job_id,),
        audit_sample_count=1,
        seed=31,
        authorized_by="historical cohort acceptance",
        attestation=HISTORICAL_ATTESTATION,
    )
    return store, request, contract, pro_contract, admission


def test_historical_cohort_freezes_before_outcomes_and_preserves_v1(tmp_path):
    store, request, calibration, prospective, admission = prepared(tmp_path)
    service = HistoricalCohorts(store, tmp_path)
    identity = service.freeze(request)
    assert store.paused() and service.freeze(request) == identity
    report = service.report(identity)
    assert report["historical"] and report["schema_version"] == "historical-screen-cohort/v2"
    assert report["approximate_pruning_authorized"] is False
    assert report["selected_count"] == 1 and report["native_observed"] == 0
    assert report["audit_complete"] is False
    assert report["frozen"]["subject"]["instrument_hash"] == fingerprint(
        InstrumentSpec.model_validate(
            json.loads(store.rows("SELECT * FROM jobs")[0]["payload"])["profile"]
        )
    )
    # v1 remains generated-only and rejects a historical request outright.
    from factory.screening.cohorts import Cohorts, CohortRequest

    with pytest.raises(ValueError, match="historical cohort v2"):
        Cohorts(store, tmp_path).freeze(request.model_dump(mode="json"))
    with pytest.raises(Exception):
        CohortRequest.model_validate(request.model_dump(mode="json"))
    # The generic report route dispatches to the historical report.
    from factory.screening.cohorts import Cohorts as Generic

    assert Generic(store, tmp_path).report(identity)["historical"] is True


def test_historical_cohort_rejects_embargo_admission_and_duplicate(tmp_path):
    store, request, calibration, prospective, admission = prepared(tmp_path)
    service = HistoricalCohorts(store, tmp_path)
    # Prospective window inside the calibration coverage violates the embargo.
    with pytest.raises(ValueError, match="empty/reversed"):
        service.freeze(
            request.model_copy(
                update={
                    "policy": HistoricalCalibrationPolicy.model_validate(
                        {
                            **request.policy.model_dump(mode="json"),
                            "training_start_ns": request.policy.training_end_ns + 1,
                        }
                    )
                }
            )
        )
    # A different admission cannot be bound to this calibration.
    wrong = request.policy.model_copy(update={"admission_id": "1" * 64})
    with pytest.raises(ValueError, match="calibration admission binding mismatch"):
        service.freeze(request.model_copy(update={"policy": wrong}))
    # Freezing once makes the prospective member unavailable to a second cohort.
    service.freeze(request)
    payload = json.loads(
        store.rows("SELECT payload FROM jobs WHERE job_id=?", (request.prospective_job_ids[0],))[0][
            "payload"
        ]
    )
    payload["contract"]["seed"] += 1
    from factory.contracts import ExperimentContract as EC

    alias = store.enqueue(
        "research", payload, EC.model_validate(payload["contract"]).experiment_hash
    )
    with pytest.raises(ValueError, match="duplicate effective"):
        service.freeze(
            request.model_copy(
                update={"prospective_job_ids": (alias,), "audit_sample_count": 1, "seed": 33}
            )
        )
    assert len(store.rows("SELECT * FROM screen_cohorts")) == 1


def test_fenced_completion_produces_the_historical_diagnostic(tmp_path):
    from apps.coordinator.service import cycle

    store, request, calibration, prospective, admission = prepared(tmp_path)
    service = HistoricalCohorts(store, tmp_path)
    identity = service.freeze(request)
    store.pause(False, "test")
    assert cycle(store, tmp_path)
    report = service.report(identity)
    assert report["native_observed"] == 1 and report["audit_complete"]
    assert report["selected_count"] == 1
    assert report["approximate_pruning_authorized"] is False
    # The native artifact is unchanged; the diagnostic is separately hashed.
    result = json.loads(
        store.rows("SELECT result_json FROM experiments WHERE experiment_hash=?", (prospective.experiment_hash,))[0][
            "result_json"
        ]
    )
    assert result["frozen_screen_audit_cohort"] == identity
    events = store.rows(
        "SELECT payload FROM audit_events WHERE action='historical_shadow_completed'"
    )
    assert len(events) == 2  # calibration posthoc + fenced prospective completion


def test_historical_cohort_requires_reviewed_admission_at_freeze(tmp_path):
    store, request, calibration, prospective, admission = prepared(tmp_path)
    # Revoke the reviewed admission: the historical cohort must refuse to freeze.
    store.rows("SELECT 1")
    from factory.data.admission import InputRegistry

    InputRegistry(tmp_path, Catalog(tmp_path / "catalog")).revoke(
        admission, "test reviewer", "authorization withdrawn"
    )
    with pytest.raises(ValueError, match="UNKNOWN_REVIEWED_INPUT|REVOKED"):
        HistoricalCohorts(store, tmp_path).freeze(request)
