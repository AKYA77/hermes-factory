"""Engineering checkpoints must not hide unfinished blueprint gates."""

import json
from pathlib import Path
import runpy

import pytest


def queue_fixture(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    for name in ["implementation-queue.json", "completion-ledger.json"]:
        (tmp_path / name).write_bytes((root / name).read_bytes())
    queue_path = tmp_path / "implementation-queue.json"
    queue = json.loads(queue_path.read_text())
    queue["tasks"][0]["state"] = "IMPLEMENTING"
    queue["tasks"][1]["state"] = "QUEUED"
    queue_path.write_text(json.dumps(queue))
    namespace = runpy.run_path(str(root / "scripts/completion-queue.py"))
    monkeypatch.setattr(
        namespace["subprocess"],
        "check_output",
        lambda args, **kwargs: "" if "--short" in args else "a" * 40,
    )
    return namespace["inspect"]


def test_queue_reads_all_gates_and_preserves_readiness(tmp_path, monkeypatch):
    inspect = queue_fixture(tmp_path, monkeypatch)
    original = (tmp_path / "completion-ledger.json").read_bytes()
    result = inspect(tmp_path)
    assert result["next_task"]["id"] == "autonomous_discovery"
    assert not result["readiness"]["SOFTWARE_VERIFIED"]
    assert result["unfinished_requirements"]
    assert (tmp_path / "completion-ledger.json").read_bytes() == original


def test_scoped_discovery_checkpoint_selects_shared_features_without_claiming_parent_gates(
    tmp_path, monkeypatch
):
    inspect = queue_fixture(tmp_path, monkeypatch)
    path = tmp_path / "implementation-queue.json"
    queue = json.loads(path.read_text())
    queue["tasks"][0]["state"] = "VERIFIED_SCOPE"
    path.write_text(json.dumps(queue))
    result = inspect(tmp_path)
    assert result["next_task"]["id"] == "shared_indicators"
    assert any(r["id"] == "C4" for r in result["unfinished_requirements"])
    assert not result["readiness"]["SOFTWARE_VERIFIED"]


def test_missing_gate_coverage_is_a_controller_error(tmp_path, monkeypatch):
    inspect = queue_fixture(tmp_path, monkeypatch)
    path = tmp_path / "implementation-queue.json"
    queue = json.loads(path.read_text())
    for t in queue["tasks"]:
        t["requirements"] = [r for r in t["requirements"] if r != "T55"]
    path.write_text(json.dumps(queue))
    with pytest.raises(ValueError, match="exact acceptance ledger"):
        inspect(tmp_path)
