"""Synthetic import-control tests; no fake historical results or network access."""

import json
import urllib.error

import pytest
from factory.operations.backfill_history import plan, run
from factory.data.histdata import download


def test_period_plan_is_fair_by_month_and_bounded():
    rows = list(plan("2025-02", ("EURUSD", "USDJPY")))
    assert [r["key"] for r in rows] == [
        "EURUSD:2025-01",
        "USDJPY:2025-01",
        "EURUSD:2025-02",
        "USDJPY:2025-02",
    ]
    with pytest.raises(ValueError):
        list(plan("2027-01"))
    with pytest.raises(ValueError):
        list(plan("2025-01", ("INVALID",)))


def test_backfill_failure_checkpoint_and_cooldown(tmp_path, monkeypatch):
    import factory.operations.backfill_history as module

    called = []

    def fail(*args):
        called.append(True)
        raise ValueError("fixture provider outage")

    monkeypatch.setattr(module, "import_partition", fail)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    args = ("2025-01", tmp_path / "archives", tmp_path / "catalog", tmp_path / "checkpoint.json")
    first = run(*args, max_partitions=1, execute=True, instruments=("EURUSD",))
    assert first["structurally_imported_partitions"] == 0
    assert first["results"][0]["state"] == "BLOCKED"
    second = run(*args, max_partitions=1, execute=True, instruments=("EURUSD",))
    assert second["new_partition_attempts"] == 0 and len(called) == 1
    assert (
        json.loads((tmp_path / "checkpoint.json").read_text())["partitions"]["EURUSD:2025-01"][
            "state"
        ]
        == "BLOCKED"
    )


def test_failed_pending_bytes_preserved_and_retried(tmp_path, monkeypatch):
    import factory.data.histdata as module

    pending = tmp_path / "EURUSD-202501-ticks.pending"
    pending.write_bytes(b"incomplete synthetic bytes")
    calls = []

    class Outage:
        def open(self, *args, **kwargs):
            calls.append(True)
            raise urllib.error.URLError("synthetic network outage")

    monkeypatch.setattr(module.urllib.request, "build_opener", lambda *args: Outage())
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    with pytest.raises(urllib.error.URLError):
        download(tmp_path, "EURUSD", 2025, 1)
    assert len(calls) == 3
    preserved = [p for p in (tmp_path / "failed-captures").iterdir() if p.suffix != ".json"]
    assert len(preserved) == 1 and preserved[0].read_bytes() == b"incomplete synthetic bytes"
    assert not (tmp_path / "EURUSD-202501-ticks.manifest.json").exists()
