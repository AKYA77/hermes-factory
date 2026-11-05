"""Actual multi-quarter refitting, separate OOS/annual/pooled native runs and memory."""

from dataclasses import replace, asdict
from datetime import datetime, timezone
import json
import pytest

from apps.coordinator.service import cycle
from factory.contracts import Window, serialize, fingerprint
from factory.data import Catalog
from factory.experiments import Store
from factory.operations.fixtures import seed
from factory.validation.access import HoldoutSpec, Holdouts
from factory.validation.protocol import (
    ValidationController,
    ValidationProtocol,
    ValidationCriteria,
    ValidationEvidencePolicy,
)


def protocol_fixture(root, purpose="research_qualification"):
    payload = seed(root, 480)
    cat = Catalog(root / "catalog")
    original = list(cat.read(payload["contract"]["dataset_hash"]))
    partitions = []
    start = end = holdout_start = None
    for month in (1, 4, 7, 10):
        timestamp = int(datetime(2025, month, 1, tzinfo=timezone.utc).timestamp()) * 10**9
        if start is None:
            start = timestamp
        if month == 10:
            holdout_start = timestamp
        data = [
            replace(
                q,
                event_ts_utc_ns=timestamp + i * 60 * 10**9,
                ingest_batch_id="quarter-" + str(month),
            )
            for i, q in enumerate(original)
        ]
        m = cat.commit(
            data,
            serialize([asdict(q) for q in data]).encode(),
            {
                "source": "synthetic multi-quarter protocol reference",
                "license": "project acceptance fixture",
                "synthetic": True,
            },
        )
        partitions.append(m["dataset_hash"])
        end = data[-1].event_ts_utc_ns + 1
    view = cat.compose(partitions)
    holdout = HoldoutSpec(
        dataset_hash=view["dataset_hash"],
        profile=payload["profile"],
        window=Window(start_ns=holdout_start, end_ns=end, role="final_holdout_unseen"),
        code_revision=payload["contract"]["code_revision"],
        external_use_declaration="NO_PRIOR_USE_DECLARED",
        declaration_notes="Fresh multi-quarter synthetic software fixture, never historical market evidence",
    )
    p = ValidationProtocol(
        purpose=purpose,
        evidence_policy=ValidationEvidencePolicy(
            max_censored_fraction=0.1,
            max_marked_drawdown=".95",
            min_neighbor_closed_trades=50,
            min_neighbor_acceptable_fraction=0.5,
        ),
        holdout=holdout,
        start_ns=start,
        family="momentum",
        timeframe="M1",
        seed=42,
        trials_per_refit=1,
        cpu_seconds_per_refit=60,
        purge_seconds=86400,
        embargo_seconds=0,
        criteria=ValidationCriteria(
            min_oos_closed_trades=50,
            min_full_folds=2,
            min_annual_closed_trades=50,
            min_wilson_lower=0.5,
            min_net_profit=0,
            max_losing_streak=5,
            familywise_alpha=0.05,
            min_neighborhoods_with_trades=1,
            require_research_targets=False,
        ),
    )
    return p


def test_full_controlled_chronological_research_survives_restart(tmp_path, monkeypatch):
    protocol = protocol_fixture(tmp_path, purpose="synthetic_software_rehearsal")
    store = Store(tmp_path / "factory.sqlite")
    identity = ValidationController(store, tmp_path).register(protocol)
    assert not cycle(store, tmp_path)
    store.pause(False, "test")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    reports = []
    for _ in range(48):
        cycle(Store(tmp_path / "factory.sqlite"), tmp_path)
        reports = store.rows(
            "SELECT * FROM validation_protocol_reports WHERE protocol_id=?", (identity,)
        )
        if reports:
            break
    assert len(reports) == 1
    result = json.loads(reports[0]["report_json"])
    assert result["status"] != "FAILED_CHECKS", result.get("reason")
    assert result["status"] in ("INSUFFICIENT_EVIDENCE", "OOS_FAILED", "VALIDATED_REFERENCE")
    assert result["eligible_for_historical_validated_board"] is False
    assert result["independently_validated"] is False
    assert result["holdout_consumed_by_protocol"] is True
    assert result["protocol"]["purpose"] == "synthetic_software_rehearsal"
    assert len(result["folds"]) == 2 and len(result["annual"]) == 1
    assert result["pooled_retrospective"]["evaluation_id"] != result["annual"][0]["evaluation_id"]
    regions = store.rows(
        "SELECT * FROM validation_training_regions WHERE protocol_id=?", (identity,)
    )
    assert len(regions) == 3  # two independent chronological refits + final past-only refit
    for region in regions:
        p = json.loads(
            store.rows(
                "SELECT protocol_json FROM search_protocols WHERE protocol_hash=?",
                (region["search_protocol_hash"],),
            )[0]["protocol_json"]
        )
        assert p["window"]["role"] == "train_only"
        assert p["window"]["end_ns"] < protocol.holdout.window.start_ns
    assert len(store.rows("SELECT * FROM holdout_consumptions")) == 1
    assert len(store.rows("SELECT * FROM jobs WHERE state!='COMPLETED'")) == 0
    before = len(store.rows("SELECT * FROM evaluation_results"))
    assert not cycle(Store(tmp_path / "factory.sqlite"), tmp_path)
    assert len(store.rows("SELECT * FROM evaluation_results")) == before


def test_weak_forward_qualification_preserves_final_window_and_skips_final_refit(tmp_path):
    protocol = protocol_fixture(tmp_path)
    store = Store(tmp_path / "factory.sqlite")
    identity = ValidationController(store, tmp_path).register(protocol)
    store.pause(False, "test")
    reports = []
    for _ in range(24):
        cycle(Store(tmp_path / "factory.sqlite"), tmp_path)
        reports = store.rows(
            "SELECT * FROM validation_protocol_reports WHERE protocol_id=?", (identity,)
        )
        if reports:
            break
    assert len(reports) == 1
    report = json.loads(reports[0]["report_json"])
    assert report["status"] == "INSUFFICIENT_EVIDENCE"
    assert report["holdout"] is None and report["holdout_consumed_by_protocol"] is False
    assert report["qualification"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert report["independently_validated"] is False
    assert not store.rows("SELECT * FROM holdout_consumptions")
    assert not store.rows("SELECT * FROM holdout_selections")
    assert not store.rows("SELECT * FROM validation_training_regions WHERE fold_index=-1")
    count = len(store.rows("SELECT * FROM jobs"))
    assert not cycle(Store(tmp_path / "factory.sqlite"), tmp_path)
    assert len(store.rows("SELECT * FROM jobs")) == count


def test_v2_requires_explicit_thresholds_and_v1_identity_remains_read_only(tmp_path):
    protocol = protocol_fixture(tmp_path)
    raw = protocol.model_dump()
    raw.pop("evidence_policy")
    with pytest.raises(ValueError, match="explicit evidence thresholds"):
        ValidationProtocol.model_validate(raw)
    raw["schema_version"] = "scientific-validation/v1"
    raw.pop("purpose")
    expected = fingerprint(raw)
    legacy = ValidationProtocol.model_validate(raw)
    assert legacy.protocol_id == expected
    store = Store(tmp_path / "factory.sqlite")
    controller = ValidationController(store, tmp_path)
    with pytest.raises(ValueError, match="LEGACY_VALIDATION_PROTOCOL_READ_ONLY"):
        controller.register(legacy)
    # Reproduce a legitimate restored pre-v2 registration, preserving its bytes.
    held = Holdouts(tmp_path).register(legacy.holdout)
    with store.transaction() as db:
        db.execute(
            "INSERT INTO validation_protocols VALUES(?,?,?,?)", (expected, serialize(raw), held, 0)
        )
        db.execute("INSERT INTO validation_controls VALUES(?,1,0)", (expected,))
    assert controller.protocol(expected).protocol_id == expected
    store.pause(False, "test")
    assert controller.advance()
    report = json.loads(
        store.rows("SELECT report_json FROM validation_protocol_reports")[0]["report_json"]
    )
    assert (
        report["status"] == "FAILED_CHECKS"
        and report["reason"] == "LEGACY_VALIDATION_PROTOCOL_READ_ONLY"
    )
    assert not store.rows("SELECT * FROM jobs")
    assert not store.rows("SELECT * FROM holdout_consumptions")
