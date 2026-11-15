"""Generated discovery grants; no historical-market approval is invented."""

from dataclasses import asdict, replace
import hashlib
import json
import signal
import sqlite3
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from apps.coordinator.service import cycle
from factory.contracts import InstrumentSpec, Window, serialize
from factory.data import Catalog
from factory.experiments import Store
from factory.exploration.discovery import Discovery, DiscoveryPolicy, Family, safe_windows
from factory.exploration.persistent import Search
from factory.operations.fixtures import seed
from factory.validation.access import Holdouts, HoldoutSpec, record_use


ATTEST = (
    "I authorize training-only discovery within these bounds, never evaluation or holdout reuse"
)


def grant(payload, **changes):
    w = payload["contract"]["windows"][0]
    values = dict(
        profiles=(InstrumentSpec.model_validate(payload["profile"]),),
        training_windows=(
            Window(
                start_ns=w["start_ns"], end_ns=w["end_ns"] + 3 * 86400 * 10**9, role="train_only"
            ),
        ),
        families=(Family(operator="momentum"),),
        timeframes=("M1", "M5"),
        higher_confirmations=False,
        code_revision=payload["contract"]["code_revision"],
        seed=42,
        max_regions=4,
        max_active_regions=1,
        trials_per_region=1,
        cpu_seconds_per_region=60,
        total_cpu_seconds=600,
        authorized_by="generated acceptance fixture",
        attestation=ATTEST,
    )
    values.update(changes)
    return DiscoveryPolicy(**values)


def complete_regions(root, count):
    store = Store(root / "factory.sqlite")
    for _ in range(count * 3 + 4):
        cycle(Store(root / "factory.sqlite"), root)
        if (
            len(store.rows("SELECT 1 FROM discovery_region_controls WHERE state='EXHAUSTED'"))
            >= count
        ):
            return
    raise AssertionError(Discovery(store, root).status())


def test_continuous_expansion_after_exhaustion_and_new_dataset_without_region_registration(
    tmp_path, monkeypatch
):
    payload = seed(tmp_path, 240)
    store = Store(tmp_path / "factory.sqlite")
    manager = Discovery(store, tmp_path)
    identity = manager.register(grant(payload))
    assert manager.advance()["reason"] == "PAUSED"
    assert not store.rows("SELECT * FROM discovery_regions")
    store.pause(False, "test")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    complete_regions(tmp_path, 2)
    assert len(store.rows("SELECT * FROM discovery_regions")) == 2
    assert Discovery(Store(tmp_path / "factory.sqlite"), tmp_path).advance()["registered"] == 0
    old = store.rows("SELECT * FROM search_outcomes")
    catalog = Catalog(tmp_path / "catalog")
    q = list(catalog.read(payload["contract"]["dataset_hash"]))
    q = [
        replace(
            x,
            event_ts_utc_ns=x.event_ts_utc_ns + 86400 * 10**9,
            ingest_batch_id="new generated day",
        )
        for x in q
    ]
    new = catalog.commit(
        q,
        serialize([asdict(x) for x in q]).encode(),
        {"source": "new generated day", "license": "fixture only", "synthetic": True},
    )
    complete_regions(tmp_path, 4)
    regions = store.rows("SELECT * FROM discovery_regions")
    assert len(regions) == 4
    assert {json.loads(r["protocol_json"])["dataset_hash"] for r in regions} == {
        payload["contract"]["dataset_hash"],
        new["dataset_hash"],
    }
    assert store.rows("SELECT * FROM search_outcomes")[: len(old)] == old
    assert sum(r["outcome"] == "COMPLETE" for r in store.rows("SELECT * FROM search_outcomes")) >= 1
    assert len(store.rows("SELECT * FROM jobs")) == 4
    assert len(store.rows("SELECT * FROM discovery_policies")) == 1
    assert manager.status()["policies"][0]["policy_id"] == identity


def test_holdout_aliases_are_subtracted_before_registration(tmp_path):
    payload = seed(tmp_path, 240)
    store = Store(tmp_path / "factory.sqlite")
    start = payload["contract"]["windows"][0]["start_ns"]
    end = payload["contract"]["windows"][0]["end_ns"]
    holdout = HoldoutSpec(
        dataset_hash=payload["contract"]["dataset_hash"],
        profile=payload["profile"],
        window=Window(start_ns=start + 120 * 60 * 10**9, end_ns=end, role="final_holdout_unseen"),
        code_revision=payload["contract"]["code_revision"],
        external_use_declaration="NO_PRIOR_USE_DECLARED",
        declaration_notes="Fresh generated fixture only",
    )
    Holdouts(tmp_path).register(holdout)
    manager = Discovery(store, tmp_path)
    manager.register(grant(payload))
    store.pause(False, "test")
    assert manager.advance()["registered"] == 1
    p = Search(store, tmp_path).protocol(
        store.rows("SELECT protocol_hash FROM discovery_regions")[0]["protocol_hash"]
    )
    assert p.window.end_ns == holdout.window.start_ns
    with store.transaction() as db:
        windows = safe_windows(db, p.profile, start, end)
    assert windows == [(start, holdout.window.start_ns)]
    assert not store.rows("SELECT * FROM holdout_consumptions")


def test_unknown_evaluation_footprint_cannot_be_reused_as_training(tmp_path):
    payload = seed(tmp_path, 240)
    store = Store(tmp_path / "factory.sqlite")
    w = Window.model_validate(payload["contract"]["windows"][0])
    with store.transaction() as db:
        record_use(
            db,
            "EURUSD",
            "synthetic",
            payload["contract"]["dataset_hash"],
            w.start_ns,
            w.end_ns,
            "evaluation-with-past-only-warmup",
            "unknown external/direct evaluation",
        )
    manager = Discovery(store, tmp_path)
    manager.register(grant(payload))
    store.pause(False, "test")
    assert manager.advance()["registered"] == 0
    assert not store.rows("SELECT * FROM search_trials")


def test_sigkill_after_durable_plan_recovers_same_region(tmp_path):
    payload = seed(tmp_path, 120)
    store = Store(tmp_path / "factory.sqlite")
    manager = Discovery(store, tmp_path)
    manager.register(grant(payload))
    store.pause(False, "test")
    code = """
import os,signal,sys
from pathlib import Path
from factory.experiments import Store
from factory.exploration.discovery import Discovery
Discovery._register=lambda *args:os.kill(os.getpid(),signal.SIGKILL)
Discovery(Store(Path(sys.argv[1])/'factory.sqlite'),Path(sys.argv[1])).advance()
"""
    child = subprocess.run([sys.executable, "-c", code, str(tmp_path)], timeout=20)
    assert child.returncode == -signal.SIGKILL
    planned = store.rows("SELECT * FROM discovery_regions")
    assert len(planned) == 1 and not store.rows("SELECT * FROM search_protocols")
    assert manager.advance()["registered"] == 1
    assert store.rows("SELECT * FROM discovery_regions") == planned
    assert len(store.rows("SELECT * FROM search_protocols")) == 1
    with pytest.raises(sqlite3.IntegrityError, match="immutable discovery"):
        with store.transaction() as db:
            db.execute("UPDATE discovery_regions SET protocol_json='{}'")


def test_bad_catalog_metadata_is_retained_without_starving_valid_source(tmp_path):
    payload = seed(tmp_path, 120)
    store = Store(tmp_path / "factory.sqlite")
    broken = tmp_path / "catalog" / ("a" * 64)
    broken.mkdir()
    (broken / "manifest.json").write_text("broken fixture")
    manager = Discovery(store, tmp_path)
    manager.register(grant(payload))
    store.pause(False, "test")
    assert manager.advance()["registered"] == 1
    assert store.rows("SELECT * FROM discovery_source_rejections")
    assert (broken / "manifest.json").read_text() == "broken fixture"


def test_disable_and_source_revision_are_durable(tmp_path, monkeypatch):
    payload = seed(tmp_path, 120)
    store = Store(tmp_path / "factory.sqlite")
    manager = Discovery(store, tmp_path)
    identity = manager.register(grant(payload))
    store.pause(False, "test")
    result = manager.advance()
    manager.disable(identity)
    assert not Search(store, tmp_path).ask(result["protocol_hash"])
    assert manager.advance()["registered"] == 0
    other = grant(payload, seed=43)
    manager.register(other)
    monkeypatch.setattr(
        "factory.exploration.discovery.execution_revision", lambda: "different source"
    )
    assert manager.advance()["registered"] == 0
    control = store.rows("SELECT * FROM discovery_controls WHERE policy_id=?", (other.policy_id,))[
        0
    ]
    assert control["enabled"] == 0 and control["reason"] == "STALE_SOURCE"


def test_discovery_api_authorization_pause_and_pagination(tmp_path):
    payload = seed(tmp_path, 120)
    (tmp_path / "access.json").write_text(
        json.dumps(
            [
                {"role": "operator", "sha256": hashlib.sha256(b"test-operator").hexdigest()},
                {"role": "viewer", "sha256": hashlib.sha256(b"test-viewer").hexdigest()},
            ]
        )
    )
    client = TestClient(create_app(tmp_path))
    policy = grant(payload)
    url = "/api/v1/research/discovery"
    assert client.get(url).status_code == 401
    assert (
        client.post(
            url,
            json=policy.model_dump(mode="json"),
            headers={"Authorization": "Bearer test-viewer"},
        ).status_code
        == 403
    )
    headers = {"Authorization": "Bearer test-operator"}
    response = client.post(url, json=policy.model_dump(mode="json"), headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["paused"] is True
    status = client.get(url, headers=headers).json()
    assert len(status["policies"]) == 1 and not status["regions"]
    assert client.get(url + "?limit=201", headers=headers).status_code == 422
    assert (
        client.post(url + "/" + policy.policy_id + "/disable", headers=headers).status_code == 200
    )


def test_historical_discovery_requires_live_admission(tmp_path):
    from test_reviewed_inputs import prepared

    registry, payload, _, _, _, _ = prepared(tmp_path)
    store = Store(tmp_path / "factory.sqlite")
    manager = Discovery(store, tmp_path)
    # Generated TEST_ONLY external-source authorization, never market evidence.
    manager.register(grant(payload))
    store.pause(False, "test")
    first = manager.advance()
    assert first["registered"] == 1
    protocol = Search(store, tmp_path).protocol(first["protocol_hash"])
    assert not protocol.profile.synthetic and protocol.admission_id is not None
    registry.revoke(protocol.admission_id, "test", "fixture admission withdrawn")
    with pytest.raises(ValueError, match="REVOKED"):
        Search(store, tmp_path).ask(first["protocol_hash"])
    manager.block_protocol(first["protocol_hash"], "ADMISSION_REVOKED")
    assert not store.rows("SELECT * FROM search_trials")
    assert manager.sources(grant(payload), "") == []


def test_region_breadth_covers_instruments_and_families_before_repetition(tmp_path):
    from factory.instruments import synthetic_profile

    payload = seed(tmp_path, 120)
    catalog = Catalog(tmp_path / "catalog")
    quotes = [
        replace(q, instrument_id="GBPUSD")
        for q in catalog.read(payload["contract"]["dataset_hash"])
    ]
    catalog.commit(
        quotes,
        b"generated second instrument",
        {"source": "generated second instrument", "license": "fixture", "synthetic": True},
    )
    store = Store(tmp_path / "factory.sqlite")
    manager = Discovery(store, tmp_path)
    p = grant(
        payload,
        profiles=(synthetic_profile("EURUSD"), synthetic_profile("GBPUSD")),
        families=(Family(operator="momentum"), Family(operator="trend")),
        timeframes=("M1",),
        max_regions=4,
        max_active_regions=4,
    )
    manager.register(p)
    store.pause(False, "test")
    for _ in range(4):
        assert manager.advance()["registered"] == 1
    dimensions = {
        (
            json.loads(r["protocol_json"])["profile"]["instrument"],
            json.loads(r["protocol_json"])["family"],
        )
        for r in store.rows("SELECT protocol_json FROM discovery_regions")
    }
    assert dimensions == {(s, f) for s in ["EURUSD", "GBPUSD"] for f in ["momentum", "trend"]}
