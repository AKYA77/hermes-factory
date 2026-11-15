"""Authorization-boundary fixtures only: generated paths/documents are NOT market
validation or genuine broker references. Non-synthetic flags deliberately exercise
the otherwise inaccessible historical admission branch under a test-only reviewer.
"""

import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from apps.coordinator.worker import run
from factory.contracts import ExperimentContract, InstrumentSpec, StrategySpec, Window, fingerprint
from factory.data import Catalog
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
from factory.instruments.calendar import CalendarSpec, SessionCalendar
from factory.operations.fixtures import seed
from factory.validation.evaluate import evaluate

ATTEST = "I reviewed the captured references and their dated research scope"


def prepared(root):
    payload = seed(root, 240)
    catalog = Catalog(root / "catalog")
    data = list(catalog.read(payload["contract"]["dataset_hash"]))
    # Deliberate trust-boundary fixture, never an official historical receipt.
    manifest = catalog.commit(
        data,
        b"TEST ONLY generated authorization fixture",
        {
            "source": "TEST ONLY simulated external source; not historical observations",
            "license": "project-generated test fixture",
            "synthetic": False,
        },
    )
    profile = InstrumentSpec.model_validate(payload["profile"]).model_copy(
        update={
            "synthetic": False,
            "source": "TEST ONLY generated profile reference; not approved broker facts",
        }
    )
    window = Window.model_validate(payload["contract"]["windows"][0])
    document = b"TEST ONLY generated research assumptions, not financial reference evidence"
    doc_hash = hashlib.sha256(document).hexdigest()
    tzif = Path("/usr/share/zoneinfo/UTC").read_bytes()
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
    profile_review = ReferenceReview(
        profile=profile, citations={k: citation for k in PROFILE_FIELDS}, **base
    )
    calendar_review = ReferenceReview(
        calendar=calendar, citations={k: citation for k in CALENDAR_FIELDS}, **base
    )
    profile_id = registry.register_reference(profile_review, {doc_hash: document})
    calendar_id = registry.register_reference(calendar_review, {doc_hash: document}, tzif=tzif)
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
    payload["profile"] = profile.model_dump(mode="json")
    payload["contract"].update(
        {
            "instrument_hash": fingerprint(profile),
            "dataset_hash": manifest["dataset_hash"],
            "evaluation_policy": POLICY_PREFIX + identity,
        }
    )
    return registry, payload, profile_review, calendar_review, spec, document


def test_reviewed_native_training_evaluation_and_fenced_finalization(tmp_path):
    registry, payload, *_ = prepared(tmp_path)
    contract = ExperimentContract.model_validate(payload["contract"])
    result = run(payload, tmp_path)
    assert result["result"]["synthetic"] is False
    assert result["result"]["input_admission"]["admission_id"] in contract.evaluation_policy
    assert not result["result"]["integrity_errors"]
    assert result["result"]["trades"]
    spec = StrategySpec.model_validate(payload["strategy"])
    registry.store.complete_experiment(contract, spec, result["result"], result["artifact_hash"])
    # Fixed-spec exploratory OOS is not independently validated by this API.
    payload["contract"]["windows"][0]["role"] = "selection_oos"
    report = evaluate(tmp_path / "catalog", payload)
    assert report["status"] == "INSUFFICIENT_EVIDENCE" and report["synthetic"] is False
    assert report["input_admission"] == result["result"]["input_admission"]
    assert report["windows"][0]["replay"]["reconciliation"]["native_reference_status"] == "VERIFIED"


def test_unapproved_unknown_or_revoked_historical_input_never_executes(tmp_path):
    registry, payload, _, _, admission, _ = prepared(tmp_path)
    payload["contract"]["evaluation_policy"] = "synthetic-training/v1"
    with pytest.raises(ValueError, match="HISTORICAL_APPROVAL_REQUIRED"):
        run(payload, tmp_path)
    payload["contract"]["evaluation_policy"] = POLICY_PREFIX + "f" * 64
    with pytest.raises(ValueError, match="UNKNOWN_REVIEWED_INPUT"):
        run(payload, tmp_path)
    registry.revoke(admission.profile_review_id, "TEST_ONLY", "reference withdrawn")
    payload["contract"]["evaluation_policy"] = POLICY_PREFIX + fingerprint(admission)
    with pytest.raises(ValueError, match="REVOKED_REVIEWED_INPUT"):
        run(payload, tmp_path)
    assert not registry.store.rows("SELECT * FROM experiments")


def test_completion_checks_revocation_under_same_writer_lock(tmp_path):
    registry, payload, _, _, admission, _ = prepared(tmp_path)
    result = run(payload, tmp_path)
    registry.revoke(fingerprint(admission), "TEST_ONLY", "withdrawn after worker result")
    with pytest.raises(ValueError, match="REVOKED_OR_UNKNOWN"):
        registry.store.complete_experiment(
            ExperimentContract.model_validate(payload["contract"]),
            StrategySpec.model_validate(payload["strategy"]),
            result["result"],
            result["artifact_hash"],
        )
    assert not registry.store.rows("SELECT * FROM experiments")


def test_reference_hash_scope_and_all_field_citations_are_mandatory(tmp_path):
    registry, payload, review, _, spec, document = prepared(tmp_path)
    raw = review.model_dump()
    raw["citations"].pop("pip_size")
    with pytest.raises(ValueError, match="each required specification"):
        ReferenceReview.model_validate(raw)
    key = hashlib.sha256(document).hexdigest()
    with pytest.raises(ValueError, match="DOCUMENT_HASH_MISMATCH"):
        registry.register_reference(review, {key: document + b" changed"})
    with pytest.raises(ValueError, match="REVIEWED_SOURCE_BINDING_MISMATCH"):
        registry.register_admission(spec.model_copy(update={"accepted_events_sha256": "b" * 64}))
    payload["contract"]["windows"][0]["start_ns"] -= 1
    with pytest.raises(ValueError, match="WINDOW_OUTSIDE_ADMISSION"):
        registry.require(ExperimentContract.model_validate(payload["contract"]), review.profile)
    (registry.references / key).write_bytes(document + b" corrupted")
    with pytest.raises(ValueError, match="REFERENCE_BYTES_CHANGED"):
        registry.require(ExperimentContract.model_validate(payload["contract"]), review.profile)


def test_review_records_and_revocations_are_permanent(tmp_path):
    registry, _, review, _, spec, _ = prepared(tmp_path)
    for sql in ("DELETE FROM reviewed_inputs", "UPDATE reviewed_inputs SET kind='forged'"):
        with pytest.raises(sqlite3.IntegrityError, match="immutable reviewed input"):
            with registry.store.transaction() as db:
                db.execute(sql)
    registry.revoke(fingerprint(review), "TEST_ONLY", "retained negative evidence")
    with pytest.raises(sqlite3.IntegrityError, match="immutable input revocation"):
        with registry.store.transaction() as db:
            db.execute("DELETE FROM input_revocations")
    with pytest.raises(ValueError, match="REVOKED"):
        registry.register_admission(spec)


def test_review_cli_list_and_revoke_share_registry(tmp_path):
    import subprocess
    import sys

    registry, _, review, *_ = prepared(tmp_path)

    def command(*args):
        return subprocess.run(
            [sys.executable, "-m", "factory.cli", "--state", str(tmp_path), *args],
            capture_output=True,
            text=True,
            check=True,
        )

    listed = json.loads(command("input-reviews").stdout)
    assert len(listed) == 3
    key = fingerprint(review)
    assert json.loads(
        command("input-revoke", key, "--actor", "TEST_ONLY", "--reason", "withdrawn").stdout
    ) == {"revoked": key}
    assert (
        next(r for r in json.loads(command("input-reviews").stdout) if r["review_id"] == key)[
            "revocation_reason"
        ]
        == "withdrawn"
    )


def test_authenticated_review_api_preserves_exact_bytes_and_dependency_revocations(tmp_path):
    from fastapi.testclient import TestClient
    from apps.api.main import create_app

    registry, _, review, _, spec, _ = prepared(tmp_path)
    (tmp_path / "access.json").write_text(
        json.dumps([{"role": "viewer", "sha256": hashlib.sha256(b"test-viewer").hexdigest()}])
    )
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/v1/input-reviews").status_code == 401
    headers = {"Authorization": "Bearer test-viewer"}
    rows = client.get("/api/v1/input-reviews", headers=headers).json()
    assert len(rows) == 3 and all(isinstance(r["start_ns"], str) for r in rows)
    identity = fingerprint(spec)
    exported = client.get("/api/v1/input-reviews/" + identity, headers=headers)
    stored = registry.store.rows(
        "SELECT body_json FROM reviewed_inputs WHERE review_id=?", (identity,)
    )[0]["body_json"]
    assert exported.status_code == 200 and exported.content == stored.encode()
    assert client.get("/api/v1/input-reviews?limit=201", headers=headers).status_code == 422
    assert client.post("/api/v1/input-reviews", json={}, headers=headers).status_code == 405
    registry.revoke(fingerprint(review), "TEST_ONLY", "reference withdrawn")
    registry.revoke(fingerprint(review), "TEST_ONLY", "reference withdrawn")  # idempotent retry
    blocked = next(
        r
        for r in client.get("/api/v1/input-reviews", headers=headers).json()
        if r["review_id"] == identity
    )
    assert blocked["status"] == "REVOKED" and blocked["revoked_dependencies"] == [
        fingerprint(review)
    ]
    assert client.get("/api/v1/input-reviews/" + identity, headers=headers).status_code == 409


def test_metadata_model_copy_cannot_bypass_review_validation(tmp_path):
    registry, _, review, *_ = prepared(tmp_path)
    changed = review.model_copy(update={"citations": {}})
    with pytest.raises(ValueError, match="each required specification"):
        registry.register_reference(changed, {})
