"""Generated ZIP fixtures, never historical market-performance evidence."""

import json
from pathlib import Path
import signal
import subprocess
import sys
import zipfile

import pytest

from factory.data import Catalog, sha256
from factory.data import resume
from factory.data.histdata import quotes_from_archive
from factory.data.streaming import StreamingCatalog


PROVENANCE = {"source": "generated ZIP fixture", "license": "test only", "synthetic": True}


def archive_fixture(root, instrument="EURUSD", count=19, suffix=""):
    path = root / (instrument + suffix + ".zip")
    prices = "2650.123000,2650.234000" if instrument == "XAUUSD" else "1.123450,1.123460"
    # Keep repeated equal timestamps and exact duplicate quotes across chunks.
    lines = [f"20250102 0100{i // 2:02}001,{prices},0\r\n" for i in range(count)]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"DAT_ASCII_{instrument}_T_202501.csv", "".join(lines))
    return {
        "archive": str(path),
        "sha256": sha256(path),
        "instrument": instrument,
        "year": 2025,
        "month": 1,
    }


def checkpoint(root):
    return next((root / ".imports").glob("*/checkpoint.json"))


@pytest.mark.parametrize("symbol", ["EURUSD", "USDJPY", "XAUUSD"])
@pytest.mark.parametrize("batch_rows", [1, 4, 19])
def test_checkpointed_import_preserves_existing_dataset_identity(tmp_path, symbol, batch_rows):
    source = archive_fixture(tmp_path, symbol)
    expected = StreamingCatalog(tmp_path / "old").commit(
        quotes_from_archive(source), source["archive"], PROVENANCE, batch_rows
    )
    actual, first = resume.import_archive(tmp_path / "new", source, PROVENANCE, batch_rows)
    assert actual == expected
    assert first["rows_decoded"] == 19 and first["rows_reused"] == 0
    again, second = resume.import_archive(tmp_path / "new", source, PROVENANCE, batch_rows)
    assert again == actual and second["rows_decoded"] == 0 and second["rows_reused"] == 19
    assert list(Catalog(tmp_path / "new").read(actual["dataset_hash"])) == list(
        quotes_from_archive(source)
    )


def test_abrupt_process_death_resumes_only_verified_prefix(tmp_path, monkeypatch):
    source = archive_fixture(tmp_path)
    root = tmp_path / "catalog"
    code = """
import os, signal, sys, json
from factory.data import resume
original = resume._save
def crash(path, state):
    original(path, state)
    if state['chunks']:
        os.kill(os.getpid(), signal.SIGKILL)
resume._save = crash
resume.import_archive(sys.argv[1], json.loads(sys.argv[2]), json.loads(sys.argv[3]), 4)
"""
    child = subprocess.run(
        [sys.executable, "-c", code, str(root), json.dumps(source), json.dumps(PROVENANCE)],
        timeout=20,
    )
    assert child.returncode == -signal.SIGKILL
    cp = checkpoint(root)
    prefix = cp.read_bytes()
    assert not list(root.glob("*/manifest.json"))
    orders = []
    original = resume.histdata.parse_line

    def observe(*args, **kwargs):
        orders.append(args[2])
        return original(*args, **kwargs)

    monkeypatch.setattr(resume.histdata, "parse_line", observe)
    result, metrics = resume.import_archive(root, source, PROVENANCE, 4)
    assert orders == list(range(4, 19))  # rechecked raw prefix was not re-parsed
    assert metrics["rows_reused"] == 4 and metrics["rows_decoded"] == 15
    assert cp.read_bytes() != prefix
    assert result["rows"] == 19 and result["consecutive_exact_duplicates_retained"] == 9
    assert Catalog(root).verify(result["dataset_hash"], deep=True) == result


def test_uncheckpointed_chunk_is_retained_but_not_adopted(tmp_path, monkeypatch):
    source = archive_fixture(tmp_path)
    root = tmp_path / "catalog"
    original = resume._save

    def fail(path, state):
        if state["chunks"]:
            raise OSError("injected checkpoint failure")
        return original(path, state)

    monkeypatch.setattr(resume, "_save", fail)
    with pytest.raises(OSError, match="checkpoint failure"):
        resume.import_archive(root, source, PROVENANCE, 4)
    orphan = next((root / ".imports").glob("*/*.parquet"))
    before = orphan.read_bytes()
    monkeypatch.setattr(resume, "_save", original)
    result, metrics = resume.import_archive(root, source, PROVENANCE, 4)
    assert result["rows"] == 19 and metrics["rows_reused"] == 0
    assert orphan.read_bytes() == before
    assert list(orphan.parent.glob("failure-*.json"))


def test_staged_corruption_and_checkpoint_corruption_fail_closed(tmp_path):
    source = archive_fixture(tmp_path)
    root = tmp_path / "catalog"
    resume.import_archive(root, source, PROVENANCE, 4)
    cp = checkpoint(root)
    original = cp.read_bytes()
    data = json.loads(original)
    data["payload"]["chunks"][0]["end_offset"] += 1
    cp.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="checkpoint identity/checksum"):
        resume.import_archive(root, source, PROVENANCE, 4)
    cp.write_bytes(original)
    digest = data["payload"]["chunks"][0]["parquet_sha256"]
    staged = cp.parent / (digest + ".parquet")
    staged.write_bytes(b"damaged staged bytes")
    with pytest.raises(ValueError, match="chunk checksum"):
        resume.import_archive(root, source, PROVENANCE, 4)
    assert cp.read_bytes() == original


def test_source_change_is_not_accepted_under_old_checkpoint(tmp_path):
    source = archive_fixture(tmp_path)
    root = tmp_path / "catalog"
    original, _ = resume.import_archive(root, source, PROVENANCE, 4)
    Path(source["archive"]).write_bytes(b"changed source")
    with pytest.raises(ValueError, match="source checksum"):
        resume.import_archive(root, source, PROVENANCE, 4)
    assert (root / original["dataset_hash"] / "source.bin").exists()


def test_final_publication_failure_keeps_complete_prefix(tmp_path, monkeypatch):
    source = archive_fixture(tmp_path)
    root = tmp_path / "catalog"
    original = StreamingCatalog.commit

    def fail(*args, **kwargs):
        raise OSError("injected disk full during publication")

    monkeypatch.setattr(StreamingCatalog, "commit", fail)
    with pytest.raises(OSError, match="disk full"):
        resume.import_archive(root, source, PROVENANCE, 4)
    assert json.loads(checkpoint(root).read_text())["payload"]["complete"]
    assert not list(root.glob("*/manifest.json"))
    monkeypatch.setattr(StreamingCatalog, "commit", original)
    result, metrics = resume.import_archive(root, source, PROVENANCE, 4)
    assert result["rows"] == 19 and metrics["rows_decoded"] == 0


def test_source_swap_before_final_publication_cannot_bind_old_quotes(tmp_path, monkeypatch):
    source = archive_fixture(tmp_path)
    root = tmp_path / "catalog"
    original = StreamingCatalog.commit

    def swap(self, quotes, path, provenance, batch_rows, **kwargs):
        Path(path).write_bytes(b"different raw source")
        return original(self, quotes, path, provenance, batch_rows, **kwargs)

    monkeypatch.setattr(StreamingCatalog, "commit", swap)
    with pytest.raises(ValueError, match="raw source changed before"):
        resume.import_archive(root, source, PROVENANCE, 4)
    assert not list(root.glob("*/manifest.json"))


def test_exclusive_import_lock_and_scope_separation(tmp_path):
    import fcntl

    source = archive_fixture(tmp_path)
    root = tmp_path / "catalog"
    resume.import_archive(root, source, PROVENANCE, 4)
    cp = checkpoint(root)
    with (cp.parent / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            resume.import_archive(root, source, PROVENANCE, 4)
    changed = {**PROVENANCE, "license": "different test scope"}
    _, metrics = resume.import_archive(root, source, changed, 4)
    assert metrics["rows_reused"] == 0
    assert len(list((root / ".imports").glob("*/checkpoint.json"))) == 2


def test_invalid_rows_cannot_be_checkpointed_or_published(tmp_path):
    source = archive_fixture(tmp_path)
    with zipfile.ZipFile(source["archive"], "w") as z:
        z.writestr(
            "DAT_ASCII_EURUSD_T_202501.csv",
            "20250102 010000001,1.2,1.3,0\n" * 4 + "20250102 010000002,1.4,1.3,0\n",
        )
    source["sha256"] = sha256(source["archive"])
    root = tmp_path / "catalog"
    with pytest.raises(ValueError, match="QUARANTINED"):
        resume.import_archive(root, source, PROVENANCE, 4)
    state = json.loads(checkpoint(root).read_text())["payload"]
    assert sum(c["rows"] for c in state["chunks"]) == 4 and not state["complete"]
    assert not list(root.glob("*/manifest.json"))


def test_prefix_cursor_cannot_skip_raw_rows(tmp_path):
    source = archive_fixture(tmp_path)
    root = tmp_path / "catalog"
    resume.import_archive(root, source, PROVENANCE, 4)
    cp = checkpoint(root)
    state = json.loads(cp.read_text())["payload"]
    state["chunks"][0]["end_offset"] += 1
    resume._save(cp, state)
    with pytest.raises(ValueError, match="raw prefix mismatch"):
        resume.import_archive(root, source, PROVENANCE, 4)


def test_disk_pressure_does_not_destroy_verified_prefix(tmp_path, monkeypatch):
    source = archive_fixture(tmp_path)
    root = tmp_path / "catalog"
    real_save = resume._save
    real_usage = resume.shutil.disk_usage

    def exhaust_after_first_chunk(path, state):
        real_save(path, state)
        if state["chunks"]:
            from collections import namedtuple

            usage = namedtuple("usage", "total used free")
            monkeypatch.setattr(resume.shutil, "disk_usage", lambda _: usage(1000, 1000, 0))

    monkeypatch.setattr(resume, "_save", exhaust_after_first_chunk)
    with pytest.raises(ValueError, match="disk headroom"):
        resume.import_archive(root, source, PROVENANCE, 4)
    assert not list(root.glob("*/manifest.json"))
    monkeypatch.setattr(resume, "_save", real_save)
    monkeypatch.setattr(resume.shutil, "disk_usage", real_usage)
    result, metrics = resume.import_archive(root, source, PROVENANCE, 4)
    assert result["rows"] == 19 and metrics["rows_reused"] == 4


def test_import_command_uses_recovery_and_retains_observation_receipts(
    tmp_path, monkeypatch, capsys
):
    from factory.operations import import_history

    source = archive_fixture(tmp_path)
    source.update(
        page_url="generated ZIP fixture", usage="test only", source_timezone="UTC-05:00 fixed"
    )
    monkeypatch.setattr(import_history, "download", lambda *args, **kwargs: source)
    root = tmp_path / "catalog"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "import_history",
            "--instrument",
            "EURUSD",
            "--year",
            "2025",
            "--month",
            "1",
            "--catalog",
            str(root),
            "--batch-rows",
            "4",
            "--registry-state",
            str(tmp_path / "state"),
        ],
    )
    import_history.main()
    first = json.loads(capsys.readouterr().out)
    import_history.main()
    second = json.loads(capsys.readouterr().out)
    assert first["dataset"] == second["dataset"]
    assert first["source_observation_id"] == second["source_observation_id"]
    assert second["import_resume"]["rows_decoded"] == 0
    assert second["import_resume"]["rows_reused"] == 19
    assert len(list((root / "import-receipts").glob("*.json"))) == 2


def test_payload_quota_stops_before_write_and_can_resume_with_new_budget(tmp_path):
    source = archive_fixture(tmp_path)
    root = tmp_path / "catalog"
    with pytest.raises(ValueError, match="payload budget exceeded"):
        resume.import_archive(root, source, PROVENANCE, 4, staging_budget_bytes=1)
    assert not list((root / ".imports").glob("*/*.parquet"))
    assert not list(root.glob("*/manifest.json"))
    result, metrics = resume.import_archive(root, source, PROVENANCE, 4)
    assert result["rows"] == 19 and metrics["rows_decoded"] == 19


def test_quota_counts_other_imports_and_orphans_without_deleting_them(tmp_path):
    source = archive_fixture(tmp_path)
    root = tmp_path / "catalog"
    orphan = root / ".imports" / "old-scope" / ".pending-retained"
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b"retained failure" * 1000)
    with pytest.raises(ValueError, match="payload budget exceeded"):
        resume.import_archive(root, source, PROVENANCE, 4, staging_budget_bytes=1000)
    assert orphan.read_bytes() == b"retained failure" * 1000


def test_reclaim_only_verified_duplicate_chunks_and_idempotent_retry(tmp_path):
    source = archive_fixture(tmp_path)
    root = tmp_path / "catalog"
    result, metrics = resume.import_archive(root, source, PROVENANCE, 4)
    cp = checkpoint(root)
    canonical = root / result["dataset_hash"]
    before = {p.name: p.read_bytes() for p in canonical.iterdir()}
    orphan = cp.parent / ".pending-orphan"
    orphan.write_bytes(b"retain incomplete failed payload")
    failure = cp.parent / "failure-retained.json"
    failure.write_text('{"error":"retained failure evidence"}')
    first = resume.reclaim(root, metrics["checkpoint_id"])
    assert first["removed_chunks"] == 5 and first["reclaimed_payload_bytes"] > 0
    assert orphan.exists() and failure.exists()
    assert not list(cp.parent.glob("*.parquet"))
    assert before == {p.name: p.read_bytes() for p in canonical.iterdir()}
    second = resume.reclaim(root, metrics["checkpoint_id"])
    assert second["removed_chunks"] == second["reclaimed_payload_bytes"] == 0
    again, reused = resume.import_archive(root, source, PROVENANCE, 4)
    assert again == result and reused["staging_reclaimed"]
    assert reused["canonical_deep_verified"] and reused["rows_decoded"] == 0
    assert len(list(cp.parent.glob("reclaim-request-*.json"))) == 2
    assert len(list(cp.parent.glob("reclaim-result-*.json"))) == 2


def test_reclaim_refuses_unpublished_or_corrupt_data(tmp_path, monkeypatch):
    source = archive_fixture(tmp_path)
    root = tmp_path / "catalog"
    real = StreamingCatalog.commit
    monkeypatch.setattr(
        StreamingCatalog, "commit", lambda *a, **k: (_ for _ in ()).throw(OSError("injected"))
    )
    with pytest.raises(OSError):
        resume.import_archive(root, source, PROVENANCE, 4)
    cp = checkpoint(root)
    with pytest.raises(ValueError, match="publication receipt"):
        resume.reclaim(root, cp.parent.name)
    assert list(cp.parent.glob("*.parquet"))
    monkeypatch.setattr(StreamingCatalog, "commit", real)
    result, metrics = resume.import_archive(root, source, PROVENANCE, 4)
    (root / result["dataset_hash"] / "source.bin").write_bytes(b"corrupt canonical source")
    with pytest.raises(ValueError):
        resume.reclaim(root, metrics["checkpoint_id"])
    assert list(cp.parent.glob("*.parquet"))


def test_reclaim_interruption_restarts_without_recreating_or_losing_source(tmp_path, monkeypatch):
    source = archive_fixture(tmp_path)
    root = tmp_path / "catalog"
    result, metrics = resume.import_archive(root, source, PROVENANCE, 4)
    real = Path.unlink
    removed = []

    def interrupted(path, *args, **kwargs):
        if path.suffix == ".parquet":
            if removed:
                raise OSError("injected interrupted reclamation")
            removed.append(path)
        return real(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", interrupted)
    with pytest.raises(OSError, match="interrupted reclamation"):
        resume.reclaim(root, metrics["checkpoint_id"])
    cp = checkpoint(root)
    assert json.loads(cp.read_text())["payload"]["chunks_reclaimed"]
    monkeypatch.setattr(Path, "unlink", real)
    receipt = resume.reclaim(root, metrics["checkpoint_id"])
    assert receipt["removed_chunks"] == 4
    assert Catalog(root).verify(result["dataset_hash"], deep=True) == result
    assert len(list(cp.parent.glob("reclaim-request-*.json"))) == 2
    assert len(list(cp.parent.glob("reclaim-result-*.json"))) == 1


def test_corrupt_staging_or_links_are_preserved_not_reclaimed(tmp_path):
    source = archive_fixture(tmp_path)
    root = tmp_path / "catalog"
    _, metrics = resume.import_archive(root, source, PROVENANCE, 4)
    chunk = next(checkpoint(root).parent.glob("*.parquet"))
    chunk.write_bytes(b"damaged staging evidence")
    with pytest.raises(ValueError, match="corrupt staged chunk"):
        resume.reclaim(root, metrics["checkpoint_id"])
    assert chunk.read_bytes() == b"damaged staging evidence"
    outside = tmp_path / "outside"
    outside.write_bytes(b"do not delete")
    chunk.unlink()
    chunk.symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        resume.reclaim(root, metrics["checkpoint_id"])
    assert outside.read_bytes() == b"do not delete"


def test_shared_payload_admission_lock_and_reclamation_cli(tmp_path):
    import fcntl

    source = archive_fixture(tmp_path)
    root = tmp_path / "catalog"
    imports = root / ".imports"
    imports.mkdir(parents=True)
    with (imports / "payload-budget.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            resume.import_archive(root, source, PROVENANCE, 4)
    result, metrics = resume.import_archive(root, source, PROVENANCE, 4)
    child = subprocess.run(
        [
            sys.executable,
            "-m",
            "factory.operations.import_staging",
            "--catalog",
            str(root),
            "--checkpoint-id",
            metrics["checkpoint_id"],
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert child.returncode == 0, child.stderr
    receipt = json.loads(child.stdout)
    assert receipt["dataset_hash"] == result["dataset_hash"] and receipt["removed_chunks"] == 5


def test_staging_directory_link_cannot_escape_catalog(tmp_path):
    source = archive_fixture(tmp_path)
    root = tmp_path / "catalog"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / ".imports").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        resume.import_archive(root, source, PROVENANCE)
    with pytest.raises(ValueError, match="symlink"):
        resume.reclaim(root, "a" * 64)
    assert not list(outside.iterdir())


def test_reclaim_all_frees_published_staging_and_preserves_canonical(tmp_path):
    source = archive_fixture(tmp_path)
    root = tmp_path / "catalog"
    manifest, _ = resume.import_archive(root, source, PROVENANCE, 4)
    staging = root / ".imports"
    before = sum(p.stat().st_size for p in staging.rglob("*.parquet"))
    assert before > 0
    receipts = resume.reclaim_all(root)
    assert len(receipts) == 1
    assert receipts[0]["reclaimed_payload_bytes"] == before
    assert receipts[0]["canonical_source_and_evidence_preserved"] is True
    assert not list(staging.rglob("*.parquet"))
    # Canonical data and the checkpoint evidence are preserved.
    assert list(Catalog(root).read(manifest["dataset_hash"])) == list(quotes_from_archive(source))
    assert list(staging.glob("*/checkpoint.json"))
    # A second pass removes nothing further.
    assert [r["reclaimed_payload_bytes"] for r in resume.reclaim_all(root)] == [0]


def test_budget_lock_fails_fast_under_contention(tmp_path):
    """The catalog-wide budget lock is a deliberate fail-fast guard.

    A second non-blocking attempt must raise rather than queue, so the budget
    problem is visible immediately instead of becoming a silent backlog. The
    supervisor therefore runs with a single worker by design.
    """
    import fcntl

    lock_path = tmp_path / "payload-budget.lock"
    with lock_path.open("a") as first, lock_path.open("a") as second:
        fcntl.flock(first, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_single_worker_import_is_uncontended(tmp_path):
    """A single sequential import holds the budget lock only for its own chunk."""
    source = archive_fixture(tmp_path, "EURUSD")
    root = tmp_path / "catalog"
    result = resume.import_archive(root, source, PROVENANCE, 4)
    assert result[0]["rows"] > 0
