"""The acquisition driver must forward the staging budget to each import."""

import importlib.util
from pathlib import Path
import subprocess

import pytest


def _load_driver():
    path = Path(__file__).resolve().parents[2] / "scripts" / "acquire_history.py"
    spec = importlib.util.spec_from_file_location("acquire_history", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _item():
    return {"instrument": "EURUSD", "year": 2026, "month": 4, "key": "EURUSD:2026-04"}


def _prepare(tmp_path):
    for name in ("archives", "catalog", "logs"):
        (tmp_path / name).mkdir()
    return tmp_path / "archives", tmp_path / "catalog", tmp_path / "logs"


def test_import_one_forwards_the_staging_budget(tmp_path, monkeypatch):
    driver = _load_driver()
    archives, catalog, logs = _prepare(tmp_path)
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    driver.import_one(_item(), archives, catalog, logs, 60, 17179869184)
    command = captured["command"]
    assert command[command.index("--staging-budget-bytes") + 1] == "17179869184"


def test_import_one_omits_the_budget_when_not_configured(tmp_path, monkeypatch):
    driver = _load_driver()
    archives, catalog, logs = _prepare(tmp_path)
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    driver.import_one(_item(), archives, catalog, logs, 60)
    assert "--staging-budget-bytes" not in captured["command"]


def test_supervisor_exposes_the_budget_option(monkeypatch, capsys):
    driver = _load_driver()
    monkeypatch.setattr("sys.argv", ["acquire_history.py", "--help"])
    with pytest.raises(SystemExit) as exc:
        driver.main()
    assert exc.value.code == 0
    assert "--staging-budget-bytes" in capsys.readouterr().out
