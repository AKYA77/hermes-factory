"""A restored state root must be usable, not merely byte-identical."""

import pytest

from factory.contracts import ExperimentContract
from factory.data.histdata import parse_line
from factory.data.streaming import StreamingCatalog
from factory.experiments import Store
from factory.operations import backup, rehearse_restore, restore
from factory.operations.fixtures import seed


def _state_root(tmp_path):
    root = tmp_path / "state"
    root.mkdir()
    store = Store(root / "factory.sqlite")
    payload = seed(root)
    store.enqueue(
        "research",
        payload,
        ExperimentContract.model_validate(payload["contract"]).experiment_hash,
        actor="rehearsal-fixture",
    )
    catalog = root / "catalog"
    catalog.mkdir(exist_ok=True)
    source = root / "source.csv"
    line = "20250102 010000001,1.123450,1.123460,0"
    source.write_text((line + "\n") * 4)

    def stream():
        for i in range(4):
            yield parse_line(line, "EURUSD", i, "raw")

    StreamingCatalog(catalog).commit(
        stream(),
        source,
        {"source": "synthetic rehearsal fixture", "license": "test only", "synthetic": True},
        batch_rows=2,
    )
    (root / "artifacts").mkdir(exist_ok=True)
    (root / "artifacts" / "note.txt").write_text("fixture artifact")
    return root


def test_rehearse_restore_exercises_the_recovery_path(tmp_path):
    root = _state_root(tmp_path)
    archive = tmp_path / "backup"
    backup(root, archive)
    workdir = tmp_path / "rehearsal" / "restored"
    receipt = rehearse_restore(archive, workdir)
    assert receipt["schema"] == "restore-rehearsal/v1"
    assert receipt["migrations_applied"] > 0
    assert receipt["jobs"] == 1
    assert receipt["experiments"] == 0
    assert receipt["catalog_partitions"] >= 1
    assert receipt["scope"] == "isolated rehearsal; backup and live state unchanged"
    # The rehearsal cleans up after itself and never touches the backup.
    assert not workdir.exists()
    assert archive.exists()
    assert (archive / "backup-manifest.json").exists()


def test_rehearse_restore_refuses_to_overwrite_an_existing_workdir(tmp_path):
    root = _state_root(tmp_path)
    archive = tmp_path / "backup"
    backup(root, archive)
    workdir = tmp_path / "rehearsal"
    workdir.mkdir()
    with pytest.raises(ValueError, match="must not exist"):
        rehearse_restore(archive, workdir)


def test_rehearse_restore_refuses_a_workdir_inside_the_backup(tmp_path):
    root = _state_root(tmp_path)
    archive = tmp_path / "backup"
    backup(root, archive)
    with pytest.raises(ValueError, match="outside the backup"):
        rehearse_restore(archive, archive / "nested")


def test_restore_into_a_fresh_root_is_unaffected_by_the_rehearsal(tmp_path):
    root = _state_root(tmp_path)
    archive = tmp_path / "backup"
    backup(root, archive)
    restored = tmp_path / "restored"
    receipt = restore(archive, restored)
    assert receipt["schema"] == "restore/v1"
    store = Store(restored / "factory.sqlite")
    assert store.rows("SELECT COUNT(*) AS n FROM jobs")[0]["n"] == 1
