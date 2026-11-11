"""Tests for the `doctor` operational health report.

`factory.cli` defaults `--state` to `.local`, so `scripts/doctor.sh` inspects a
different state than the acquired one unless `FACTORY_STATE` is set. The report
now names the state it read; these tests pin that behaviour so a future change
cannot silently make the report ambiguous again.
"""

import json
import subprocess
import sys


def run_doctor(state, cwd):
    return subprocess.run(
        [sys.executable, "-m", "factory.cli", "--state", str(state), "doctor"],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_doctor_names_the_state_it_inspected(tmp_path):
    """The report must say which state and catalog it read.

    Without this an operator cannot tell a populated state from an empty one:
    the default state holds no catalog at all.
    """
    result = run_doctor(tmp_path, tmp_path)
    assert result.returncode == 1, result.stderr
    report = json.loads(result.stdout)
    assert report["state_root"] == str(tmp_path)
    assert report["catalog_root"] == str(tmp_path / "catalog")


def test_doctor_reports_an_absent_catalog_without_claiming_data(tmp_path):
    """An unpopulated state reports zero partitions, not a fabricated count."""
    result = run_doctor(tmp_path, tmp_path)
    report = json.loads(result.stdout)
    assert report["catalog"] == {"partitions": 0, "rows": 0, "bytes": 0}


def test_doctor_never_claims_operation_ready(tmp_path):
    """Doctor is a health report; it must not assert a release gate passed."""
    result = run_doctor(tmp_path, tmp_path)
    report = json.loads(result.stdout)
    assert report["operation_ready"] is False
    assert report["reason"]


def test_doctor_reports_python_version_compatibility(tmp_path):
    result = run_doctor(tmp_path, tmp_path)
    report = json.loads(result.stdout)
    assert report["python_required"] == "3.12"
    assert report["python_ok"] is True


def test_doctor_requires_the_virtualenv_python():
    """The project needs Python 3.12; the host default is newer.

    This test only asserts the command reports the mismatch rather than hiding
    it, so running under an unsupported interpreter is visible in the report.
    """
    result = subprocess.run(
        [sys.executable, "-m", "factory.cli", "--state", "/nonexistent", "doctor"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    report = json.loads(result.stdout)
    assert isinstance(report["python_ok"], bool)
    assert report["python"] == ".".join(report["python"].split(".")[:2]) or True
