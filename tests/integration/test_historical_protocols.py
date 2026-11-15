"""Generated TEST_ONLY reference fixtures test historical authorization paths.
These are not genuine market validation; real-source rehearsal is separate.
"""

import json

import pytest

from apps.coordinator.service import cycle
from factory.contracts import ExperimentContract, Window, fingerprint, serialize
from factory.data.admission import admission_identity, approved_policy
from factory.exploration.persistent import Search, SearchProtocol
from factory.validation.access import HoldoutSpec, Holdouts
from test_reviewed_inputs import prepared


def historical_setup(root):
    registry, payload, profile_review, _, admission, _ = prepared(root)
    full = Window.model_validate(payload["contract"]["windows"][0])
    cut = full.start_ns + 120 * 60 * 10**9
    hold = HoldoutSpec(
        schema_version="protected-holdout/v2",
        admission_id=fingerprint(admission),
        dataset_hash=payload["contract"]["dataset_hash"],
        profile=payload["profile"],
        window=Window(start_ns=cut, end_ns=full.end_ns, role="final_holdout_unseen"),
        code_revision=payload["contract"]["code_revision"],
        external_use_declaration="NO_PRIOR_USE_DECLARED",
        declaration_notes="Fresh TEST_ONLY authorization fixture, not genuine market evidence",
    )
    holds = Holdouts(root)
    hid = holds.register(hold)
    protocol = SearchProtocol(
        schema_version="search/v4",
        admission_id=fingerprint(admission),
        research_kind="historical-training/v1",
        dataset_hash=hold.dataset_hash,
        profile=hold.profile,
        window=Window(start_ns=full.start_ns, end_ns=cut, role="train_only"),
        family="breakout",
        timeframe="M1",
        seed=42,
        max_trials=1,
        code_revision=hold.code_revision,
    )
    search = Search(registry.store, root)
    identity = search.register(protocol)
    trial = search.ask(identity)
    search.enqueue_pending()
    registry.store.pause(False, "test")
    assert cycle(registry.store, root)
    search.feedback()
    native = registry.store.rows("SELECT * FROM experiments")[0]
    assert json.loads(native["result_json"])["synthetic"] is False
    return registry, search, protocol, holds, hid, hold, native, trial


def test_historical_tpe_freeze_confirm_restart_and_one_consumption(tmp_path):
    registry, search, protocol, holds, hid, hold, native, trial = historical_setup(tmp_path)
    assert admission_identity(trial["contract"].evaluation_policy) == protocol.admission_id
    assert protocol.screening_policy is None
    frozen = holds.freeze(hid, native["run_id"])
    final = ExperimentContract.model_validate(frozen["contract"])
    assert final.evaluation_policy != trial["contract"].evaluation_policy
    assert admission_identity(final.evaluation_policy) == protocol.admission_id
    queued = holds.enqueue(hid)
    assert cycle(registry.store, tmp_path)
    report = json.loads(
        registry.store.rows("SELECT result_json FROM evaluation_results")[0]["result_json"]
    )
    assert (
        report["synthetic"] is False
        and report["input_admission"]["admission_id"] == hold.admission_id
    )
    assert report["managed_holdout"]["state"] == "HOLDOUT_CONSUMED"
    assert Holdouts(tmp_path).enqueue(hid)["evaluation_id"] == queued["evaluation_id"]
    assert len(registry.store.rows("SELECT * FROM holdout_consumptions")) == 1
    assert len(registry.store.rows("SELECT * FROM evaluation_results")) == 1
    with pytest.raises(ValueError, match="PROTECTED_HOLDOUT_ACCESS"):
        search.register(
            protocol.model_copy(
                update={
                    "window": Window(
                        start_ns=protocol.window.start_ns,
                        end_ns=hold.window.end_ns,
                        role="train_only",
                    )
                }
            )
        )


def test_revoked_reference_prevents_confirmation_before_consumption(tmp_path):
    registry, _, protocol, holds, hid, _, native, _ = historical_setup(tmp_path)
    holds.freeze(hid, native["run_id"])
    admission = registry._load(protocol.admission_id, "admission")
    registry.revoke(admission["profile_review_id"], "TEST_ONLY", "withdrawn before final attempt")
    with pytest.raises(ValueError, match="REVOKED_REVIEWED_INPUT"):
        holds.enqueue(hid)
    assert not registry.store.rows("SELECT * FROM holdout_consumptions")


def test_versioned_policy_and_legacy_serialization_are_explicit(tmp_path):
    registry, payload, _, _, admission, _ = prepared(tmp_path)
    pid = fingerprint(admission)
    a, b = approved_policy(pid, {"stage": "a"}), approved_policy(pid, {"stage": "b"})
    assert a != b and admission_identity(a) == admission_identity(b) == pid
    with pytest.raises(ValueError):
        admission_identity("historical-approved/v1:" + pid + ":unversioned-scope")
    base = dict(
        dataset_hash=payload["contract"]["dataset_hash"],
        profile=payload["profile"],
        window=payload["contract"]["windows"][0],
        family="momentum",
        timeframe="M1",
        code_revision=payload["contract"]["code_revision"],
        seed=0,
    )
    with pytest.raises(ValueError, match="legacy search"):
        SearchProtocol(**base)
    legacy = SearchProtocol(**{**base, "profile": {**payload["profile"], "synthetic": True}})
    assert "admission_id" not in json.loads(serialize(legacy))
    assert (
        legacy.protocol_hash == SearchProtocol.model_validate_json(serialize(legacy)).protocol_hash
    )
    assert "admission_id" not in legacy.model_dump()


def test_historical_validation_v3_refits_and_reports_without_synthetic_promotion(tmp_path):
    from factory.data import Catalog
    from factory.data.admission import (
        AdmissionSpec,
        ReferenceReview,
        Citation,
        InputRegistry,
        PROFILE_FIELDS,
        CALENDAR_FIELDS,
    )
    from factory.data.source_quality import SourceQuality, SourceQualityPolicy
    from factory.instruments.calendar import CalendarSpec, SessionCalendar
    from factory.validation.protocol import ValidationController, ValidationProtocol
    from test_scientific_protocol import protocol_fixture
    from pathlib import Path
    import hashlib

    original = protocol_fixture(tmp_path)
    catalog = Catalog(tmp_path / "catalog")
    old = catalog.verify(original.holdout.dataset_hash)
    parts = []
    for leaf in old["parts"]:
        data = list(catalog.read(leaf["dataset_hash"]))
        m = catalog.commit(
            data,
            ("TEST_ONLY:" + leaf["dataset_hash"]).encode(),
            {
                "source": "TEST_ONLY generated authorization fixture, not actual market history",
                "license": "project test fixture",
                "synthetic": False,
            },
        )
        parts.append(m["dataset_hash"])
    view = catalog.compose(parts)
    profile = original.holdout.profile.model_copy(
        update={"synthetic": False, "source": "TEST_ONLY generated profile, not a broker reference"}
    )
    doc = b"TEST_ONLY generated quarterly admission evidence, never market facts"
    sha = hashlib.sha256(doc).hexdigest()
    tzif = Path("/usr/share/zoneinfo/UTC").read_bytes()
    cal = CalendarSpec(
        instrument="EURUSD",
        version="TEST_ONLY/v1",
        timezone="UTC",
        tzif_sha256=hashlib.sha256(tzif).hexdigest(),
        source_document_sha256=sha,
        source_citation="TEST_ONLY generated quarterly observations",
        effective_start_ns=original.start_ns,
        effective_end_ns=original.holdout.window.end_ns,
        weekly_sessions=({"start_second": 0, "end_second": 604800},),
        closures=(),
        ambiguous_boundary="reject",
    )
    registry = InputRegistry(tmp_path, catalog)
    cite = Citation(
        document_sha256=sha,
        source="TEST_ONLY",
        locator="generated fixture",
        interpretation="authorization-branch software test only",
        basis="explicit_research_assumption",
    )
    common = dict(
        effective_start_ns=original.start_ns,
        effective_end_ns=original.holdout.window.end_ns,
        reviewer="TEST_ONLY",
        reviewed_at_ns=1793750400 * 10**9,
        attestation="I reviewed the captured references and their dated research scope",
    )
    pid = registry.register_reference(
        ReferenceReview(profile=profile, citations={k: cite for k in PROFILE_FIELDS}, **common),
        {sha: doc},
    )
    cid = registry.register_reference(
        ReferenceReview(calendar=cal, citations={k: cite for k in CALENDAR_FIELDS}, **common),
        {sha: doc},
        tzif=tzif,
    )
    qa = SourceQuality(tmp_path, catalog).run(
        view["dataset_hash"],
        SourceQualityPolicy(
            gap_threshold_ns=60 * 10**9,
            unchanged_threshold_ns=600 * 10**9,
            timestamp_quantum_ns=10**9,
            max_examples=1,
            max_events_bytes=1024**2,
            expected_start_ns=original.start_ns,
            expected_end_ns=original.holdout.window.end_ns,
        ),
        profile=profile,
        calendar=SessionCalendar(cal, tzif),
    )
    aid = registry.register_admission(
        AdmissionSpec(
            quality_run_id=qa["run_id"],
            profile_review_id=pid,
            calendar_review_id=cid,
            accepted_events_sha256=qa["events_sha256"],
            window=Window(
                start_ns=original.start_ns, end_ns=original.holdout.window.end_ns, role="train_only"
            ),
            reviewer="TEST_ONLY",
            reviewed_at_ns=common["reviewed_at_ns"],
            source_acceptance_notes="All gaps are generated test boundaries; not real source acceptance",
            attestation="I reviewed all source QA events and accept this research input scope",
        )
    )
    raw = original.model_dump()
    raw["schema_version"] = "scientific-validation/v3"
    raw["holdout"].update(
        schema_version="protected-holdout/v2",
        admission_id=aid,
        dataset_hash=view["dataset_hash"],
        profile=profile.model_dump(),
    )
    p = ValidationProtocol.model_validate(raw)
    controller = ValidationController(registry.store, tmp_path)
    identity = controller.register(p)
    registry.store.pause(False, "TEST_ONLY")
    for _ in range(32):
        cycle(registry.store, tmp_path)
        reports = registry.store.rows(
            "SELECT report_json FROM validation_protocol_reports WHERE protocol_id=?", (identity,)
        )
        if reports:
            break
    assert reports
    report = json.loads(reports[0]["report_json"])
    assert report["synthetic"] is False and report["independently_validated"] is False
    assert report["status"] in ("INSUFFICIENT_EVIDENCE", "REJECTED_OOS")
    assert not registry.store.rows("SELECT * FROM holdout_consumptions")
    regions = registry.store.rows("SELECT protocol_json FROM search_protocols")
    assert regions and all(
        json.loads(r["protocol_json"])["schema_version"] == "search/v4" for r in regions
    )
    assert all(json.loads(r["protocol_json"])["admission_id"] == aid for r in regions)
