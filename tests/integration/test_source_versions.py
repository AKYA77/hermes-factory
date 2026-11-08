"""Generated source-revision/recovery fixtures; never real market corrections."""

from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from conftest import quotes
from apps.coordinator.worker import run
from factory.contracts import ExperimentContract, StrategySpec
from factory.data import Catalog
from factory.data.streaming import StreamingCatalog
from factory.data.versions import SourceSlot, SourceVersions
from factory.operations.fixtures import seed


def capture(root, data, raw_bytes, version="test/v1"):
    root.mkdir(parents=True, exist_ok=True)
    path = root / "test-source.bin"
    path.write_bytes(raw_bytes)
    return StreamingCatalog(root / "catalog").commit(
        data,
        path,
        {
            "source": "generated source revision fixture",
            "license": "project test",
            "synthetic": True,
            "parser_version": version,
        },
    )


def slot(data):
    return SourceSlot(
        source_id=data[0].source_id,
        instrument=data[0].instrument_id,
        start_ns=data[0].event_ts_utc_ns,
        end_ns=data[-1].event_ts_utc_ns + 1,
        synthetic=True,
    )


def test_revision_history_never_silently_selects_or_overwrites_inputs(tmp_path):
    data = quotes([(110000, 110010)] * 4)
    a = capture(tmp_path, data, b"generated capture A")
    changed = [replace(q, bid_int=q.bid_int + 1) for q in data]
    b = capture(tmp_path, changed, b"generated corrected capture B")
    versions = SourceVersions(tmp_path, Catalog(tmp_path / "catalog"))
    scope = slot(data)
    first = versions.observe(scope, a["dataset_hash"])
    assert versions.observe(scope, a["dataset_hash"]) == first
    assert versions.current(scope) is None
    second = versions.observe(scope, b["dataset_hash"])
    record = versions.observation(second)
    assert record["change"] == "SOURCE_BYTES_CHANGED" and record["parent_observation_id"] == first
    chosen_a = versions.select(first, actor="test", reason="explicit initial source")
    old = versions.snapshot([scope])
    assert versions.current(scope)["observation_id"] == first
    with pytest.raises(ValueError, match="STALE_SOURCE_SELECTION"):
        versions.select(second, actor="test", reason="stale view")
    chosen_b = versions.select(
        second, actor="test", reason="reviewed correction", expected_selection_id=chosen_a
    )
    new = versions.snapshot([scope])
    assert new["dataset_hash"] != old["dataset_hash"]
    assert new["selection_ids"] == [chosen_b] and old["selection_ids"] == [chosen_a]
    # Retrying the original request returns its original receipt, not an old pointer.
    assert versions.select(first, actor="test", reason="explicit initial source") == chosen_a
    assert versions.current(scope)["selection_id"] == chosen_b
    assert list(versions.catalog.read(old["dataset_hash"]))[0].bid_int == 110000
    assert list(versions.catalog.read(new["dataset_hash"]))[0].bid_int == 110001
    assert (tmp_path / "artifacts/source-snapshots" / (old["snapshot_id"] + ".json")).exists()


def test_unchanged_archive_reimport_is_not_called_a_market_quote_correction(tmp_path):
    data = quotes([(110000, 110010)] * 3)
    a = capture(tmp_path, data, b"same generated original", "test/parser1")
    b = capture(tmp_path, data, b"same generated original", "test/parser2")
    versions = SourceVersions(tmp_path, Catalog(tmp_path / "catalog"))
    versions.observe(slot(data), a["dataset_hash"])
    second = versions.observe(slot(data), b["dataset_hash"])
    assert versions.observation(second)["change"] == "REIMPORT_OR_PARSER_CHANGE"
    assert a["quote_stream_sha256"] == b["quote_stream_sha256"]


def test_cross_year_snapshot_keeps_tied_records_and_explicit_missing_period(tmp_path):
    first = quotes([(110000, 110010)] * 3, start=1767225598 * 10**9)
    second = quotes([(110000, 110010)] * 3, start=1767225600 * 10**9)
    versions = SourceVersions(tmp_path, Catalog(tmp_path / "catalog"))
    with pytest.raises(ValueError, match="PERIOD_NOT_SELECTED"):
        versions.snapshot([slot(first)])
    for data, raw in (
        (first, b"generated December boundary"),
        (second, b"generated January boundary"),
    ):
        m = capture(tmp_path, data, raw)
        observed = versions.observe(slot(data), m["dataset_hash"])
        versions.select(observed, actor="test", reason="cross-year capture")
    snapshot = versions.snapshot([slot(first), slot(second)])
    rows = list(versions.catalog.read(snapshot["dataset_hash"]))
    assert len(rows) == 6 and rows[2].event_ts_utc_ns == rows[3].event_ts_utc_ns
    assert rows[2].sequence == 2 and rows[3].sequence == 3


def test_quarantined_leaf_blocks_alias_execution_and_completion_after_worker(tmp_path):
    payload = seed(tmp_path, 120)
    catalog = Catalog(tmp_path / "catalog")
    data = list(catalog.read(payload["contract"]["dataset_hash"]))
    versions = SourceVersions(tmp_path, catalog)
    observed = versions.observe(slot(data), payload["contract"]["dataset_hash"])
    result = run(payload, tmp_path)
    assert not result["result"]["integrity_errors"]
    episode = versions.quarantine(observed, "test", "reviewed source fault")
    assert versions.quarantine(observed, "test", "reviewed source fault") == episode
    with pytest.raises(ValueError, match="QUARANTINED_SOURCE_VERSION"):
        versions.store.complete_experiment(
            ExperimentContract.model_validate(payload["contract"]),
            StrategySpec.model_validate(payload["strategy"]),
            result["result"],
            result["artifact_hash"],
        )
    alias = catalog.compose([payload["contract"]["dataset_hash"]])
    payload["contract"]["dataset_hash"] = alias["dataset_hash"]
    with pytest.raises(ValueError, match="QUARANTINED_SOURCE_VERSION"):
        run(payload, tmp_path)
    assert not versions.store.rows("SELECT * FROM experiments")


def test_corrupt_known_bytes_can_be_quarantined_and_only_exact_restoration_resolves(tmp_path):
    data = quotes([(110000, 110010)] * 4)
    m = capture(tmp_path, data, b"generated original")
    versions = SourceVersions(tmp_path, Catalog(tmp_path / "catalog"))
    observed = versions.observe(slot(data), m["dataset_hash"])
    versions.select(observed, actor="test", reason="initial capture")
    path = tmp_path / "catalog" / m["dataset_hash"] / "source.bin"
    original = path.read_bytes()
    path.write_bytes(b"corrupt disk bytes")
    episode = versions.quarantine(observed, "test", "corruption detected")
    with pytest.raises(ValueError):
        versions.resolve(episode, "test", "unverified repair")
    path.write_bytes(original)  # Test-only simulated restore from verified original backup.
    with pytest.raises(ValueError, match="QUARANTINED_SOURCE_VERSION"):
        versions.snapshot([slot(data)])
    resolution = versions.resolve(episode, "test", "exact original restored and reverified")
    assert resolution and versions.snapshot([slot(data)])["dataset_hash"]
    next_episode = versions.quarantine(observed, "test", "new incident retained")
    assert next_episode != episode
    with pytest.raises(ValueError, match="QUARANTINED_SOURCE_VERSION"):
        versions.snapshot([slot(data)])
    for table in (
        "source_quarantines",
        "source_quarantine_resolutions",
        "source_observations",
        "source_selections",
    ):
        with pytest.raises(sqlite3.IntegrityError, match="immutable source"):
            with versions.store.transaction() as db:
                db.execute("DELETE FROM " + table)


def test_source_scope_and_snapshot_concurrent_selection_changes_reject(tmp_path, monkeypatch):
    data = quotes([(110000, 110010)] * 3)
    m = capture(tmp_path, data, b"generated source")
    versions = SourceVersions(tmp_path, Catalog(tmp_path / "catalog"))
    raw = slot(data).model_dump()
    raw["instrument"] = "XAUUSD"
    with pytest.raises(ValueError, match="SLOT_BINDING"):
        versions.observe(raw, m["dataset_hash"])
    observed = versions.observe(slot(data), m["dataset_hash"])
    versions.select(observed, actor="test", reason="original")
    original_compose = versions.catalog.compose

    def changing(leaves):
        current = versions.current(slot(data))
        versions.select(
            observed,
            actor="test",
            reason="concurrent source review",
            expected_selection_id=current["selection_id"],
        )
        return original_compose(leaves)

    monkeypatch.setattr(versions.catalog, "compose", changing)
    with pytest.raises(ValueError, match="SELECTION_CHANGED_DURING_SNAPSHOT"):
        versions.snapshot([slot(data)])


def test_source_observation_cli_uses_registry_and_preserves_selection(tmp_path):
    data = quotes([(110000, 110010)] * 3)
    m = capture(tmp_path, data, b"generated CLI source")
    slot_file = tmp_path / "slot.json"
    slot_file.write_text(slot(data).model_dump_json())
    command = [sys.executable, "-m", "factory.cli", "--state", str(tmp_path)]
    observed = json.loads(
        subprocess.check_output(
            command + ["source-observe", str(slot_file), m["dataset_hash"]], text=True
        )
    )
    chosen = json.loads(
        subprocess.check_output(
            command
            + ["source-select", observed, "--actor", "test", "--reason", "explicit CLI selection"],
            text=True,
        )
    )
    versions = SourceVersions(tmp_path, Catalog(tmp_path / "catalog"))
    assert versions.current(slot(data))["selection_id"] == chosen
    assert versions.observation(observed)["dataset_hash"] == m["dataset_hash"]


def test_refresh_capture_retains_original_and_retries_same_isolated_capture(tmp_path, monkeypatch):
    import urllib.error
    from factory.data import histdata

    original = tmp_path / "EURUSD-202501-ticks.zip"
    original.write_bytes(b"original successful test capture")
    visited = []

    def fake_download(root, instrument, year, month):
        visited.append(root)
        if len(visited) == 1:
            raise urllib.error.URLError("generated retry fault")
        path = root / "test-recapture.zip"
        path.write_bytes(b"generated new capture")
        return {"archive": str(path)}

    monkeypatch.setattr(histdata, "_download", fake_download)
    monkeypatch.setattr(histdata.time, "sleep", lambda seconds: None)
    result = histdata.download(tmp_path, "EURUSD", 2025, 1, refresh=True)
    assert len(visited) == 2 and visited[0] == visited[1] != tmp_path
    assert original.read_bytes() == b"original successful test capture"
    assert Path(result["archive"]).read_bytes() == b"generated new capture"


def test_exact_position_diff_retains_changes_additions_and_hash_verified_cache(tmp_path):
    from factory.data.reconcile import compare_sources

    data = quotes([(110000, 110010)] * 8)
    scope = slot(data)
    extra = replace(data[-1], original_record_order=8)  # Retain same-timestamp appended quote.
    new = [replace(q, bid_int=q.bid_int + (1 if n == 2 else 0)) for n, q in enumerate(data)] + [
        extra
    ]
    a = capture(tmp_path, data, b"generated original comparison")
    b = capture(tmp_path, new, b"generated changed and appended comparison")
    versions = SourceVersions(tmp_path, Catalog(tmp_path / "catalog"))
    left, right = [versions.observe(scope, m["dataset_hash"]) for m in (a, b)]
    report = compare_sources(versions, left, right)
    assert report["counts"] == {
        "left_rows": 8,
        "right_rows": 9,
        "unchanged_positions": 7,
        "changed_positions": 1,
        "left_only_positions": 0,
        "right_only_positions": 1,
    }
    assert compare_sources(versions, left, right) == report
    events = tmp_path / "artifacts/source-comparisons" / report["comparison_id"] / "events.jsonl"
    decoded = [json.loads(line) for line in events.read_text().splitlines()]
    assert decoded[0]["left"]["bid_int"] == 110000 and decoded[0]["right"]["bid_int"] == 110001
    assert decoded[1]["left"] is None and decoded[1]["right"]["source_record_order"] == 8
    events.write_bytes(events.read_bytes() + b"forged")
    with pytest.raises(ValueError, match="ARTIFACT_MISMATCH"):
        compare_sources(versions, left, right)


def test_source_diff_budget_preserves_incomplete_events_without_complete_receipt(tmp_path):
    from factory.data.reconcile import compare_sources

    data = quotes([(110000, 110010)] * 32)
    a = capture(tmp_path, data, b"generated left budget source")
    b = capture(
        tmp_path,
        [replace(q, bid_int=q.bid_int + 1) for q in data],
        b"generated right budget source",
    )
    versions = SourceVersions(tmp_path, Catalog(tmp_path / "catalog"))
    left, right = [versions.observe(slot(data), m["dataset_hash"]) for m in (a, b)]
    with pytest.raises(ValueError, match="EVENT_BUDGET"):
        compare_sources(versions, left, right, max_events_bytes=1024)
    assert not versions.store.rows("SELECT * FROM source_comparisons")
    pending = list((tmp_path / "artifacts/source-comparisons").glob(".pending-*"))
    assert len(pending) == 1 and (pending[0] / "inputs.json").exists()
    assert not json.loads((pending[0] / "failure.json").read_text())["complete_comparison"]
    assert (pending[0] / "events.jsonl").stat().st_size > 0


def test_source_coverage_reports_observed_selected_and_quarantined(tmp_path):
    data = quotes([(110000, 110010)] * 4)
    a = capture(tmp_path, data, b"generated capture A")
    changed = [replace(q, bid_int=q.bid_int + 1) for q in data]
    b = capture(tmp_path, changed, b"generated corrected capture B")
    versions = SourceVersions(tmp_path, Catalog(tmp_path / "catalog"))
    scope = slot(data)
    versions.observe(scope, a["dataset_hash"])
    second = versions.observe(scope, b["dataset_hash"])
    chosen = versions.select(second, actor="test", reason="reviewed correction")

    report = versions.coverage()
    assert report["schema_version"] == "source-coverage/v1"
    assert report["observed"] == 2
    assert report["selected"] == 1
    assert report["unresolved_quarantined"] == 0
    entry = report["instruments"]["EURUSD"]
    assert entry["observed"] == 2 and entry["selected"] == 1
    assert len(entry["periods"]) == 2
    selected = [p for p in entry["periods"] if p["selected"]]
    assert len(selected) == 1 and selected[0]["observation_id"] == second
    assert selected[0]["dataset_hash"] == b["dataset_hash"]
    assert chosen

    versions.quarantine(second, "test", "reviewed quarantine")
    report = versions.coverage()
    assert report["unresolved_quarantined"] == 1
    assert report["instruments"]["EURUSD"]["unresolved_quarantined"] == 1
    assert report["instruments"]["EURUSD"]["periods"][1]["unresolved_quarantined"] is True
    assert report["instruments"]["EURUSD"]["selected"] == 1


def test_resolved_quarantine_stops_blocking_coverage(tmp_path):
    data = quotes([(110000, 110010)] * 4)
    a = capture(tmp_path, data, b"generated capture A")
    versions = SourceVersions(tmp_path, Catalog(tmp_path / "catalog"))
    scope = slot(data)
    observed = versions.observe(scope, a["dataset_hash"])
    versions.select(observed, actor="test", reason="initial")
    quarantine_id = versions.quarantine(observed, "test", "reviewed quarantine")
    assert versions.coverage()["unresolved_quarantined"] == 1
    versions.resolve(quarantine_id, "test", "reviewed restoration")
    report = versions.coverage()
    assert report["unresolved_quarantined"] == 0
    assert report["instruments"]["EURUSD"]["unresolved_quarantined"] == 0
