"""The source-to-restore rehearsal must run its chain and record what it ran."""

import importlib.util
import json
from pathlib import Path

from factory.contracts import ExperimentContract
from factory.experiments import Store
from factory.operations.fixtures import seed


def _load_script():
    path = Path(__file__).resolve().parents[2] / "scripts" / "source_to_restore_rehearsal.py"
    spec = importlib.util.spec_from_file_location("source_to_restore_rehearsal", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _catalog(tmp_path):
    seed(tmp_path, 240)
    return tmp_path / "catalog"


def _state_root(tmp_path):
    root = tmp_path / "state"
    root.mkdir()
    store = Store(root / "factory.sqlite")
    payload = seed(root)
    store.enqueue(
        "research",
        payload,
        ExperimentContract.model_validate(payload["contract"]).experiment_hash,
        actor="rehearsal-test",
    )
    return root


def test_rehearsal_runs_the_chain_and_records_the_receipt(tmp_path):
    rehearsal = _load_script()
    catalog = _catalog(tmp_path)
    state_root = _state_root(tmp_path)
    workdir = tmp_path / "rehearsal"
    receipt = rehearsal.run(catalog=catalog, state_root=state_root, sample_size=1, workdir=workdir)
    assert receipt["schema"] == "source-to-restore-rehearsal/v1"
    assert receipt["stages_run"] == [
        "verify",
        "admit",
        "feature_cache",
        "generate",
        "screen",
        "native_replay",
        "diagnose",
        "independent_evaluation",
        "improve",
        "rank",
        "backup_restore",
    ]
    # The receipt must be explicit about what it did not run.
    assert "dashboard" in receipt["stages_not_run"]
    assert "import" in receipt["stages_not_run"]
    assert receipt["scope"].startswith("Development rehearsal")
    archived = json.loads((workdir / "rehearsal-report.json").read_text())
    assert archived["stages_run"] == receipt["stages_run"]
    assert receipt["measurements"]["wall_seconds"] > 0
    assert receipt["measurements"]["peak_rss_bytes"] > 0


def test_rehearsal_reports_a_monotonic_source(tmp_path):
    rehearsal = _load_script()
    receipt = rehearsal.run(
        catalog=_catalog(tmp_path),
        state_root=_state_root(tmp_path),
        sample_size=1,
        workdir=tmp_path / "rehearsal",
    )
    replay = next(s for s in receipt["stages"] if s["stage"] == "native_replay")
    assert replay["monotonic"] is True
    assert replay["ticks"] == 240


def test_rehearsal_refuses_to_run_without_partitions(tmp_path):
    rehearsal = _load_script()
    empty = tmp_path / "empty-catalog"
    empty.mkdir()
    try:
        rehearsal.run(
            catalog=empty,
            state_root=_state_root(tmp_path),
            sample_size=1,
            workdir=tmp_path / "rehearsal",
        )
    except RuntimeError as exc:
        assert "no acquired partitions" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for an empty catalog")
