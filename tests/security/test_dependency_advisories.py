"""Dependency reachability checks for the disclosed security advisories.

These tests codify the measured disposition in
docs/security-advisories-2026-11-07.md so a future dependency or Nautilus
upgrade that makes an advisory sink reachable fails CI instead of silently
changing the risk.
"""

import subprocess
import sys
from pathlib import Path

import nautilus_trader
from factory.simulation import runner

ROOT = Path(__file__).resolve().parents[2]


def test_fsspec_reference_sink_is_not_imported():
    """GHSA-27vj-qcqg-25rc lives in fsspec.implementations.reference."""
    assert "fsspec.implementations.reference" not in sys.modules
    assert not any(name.startswith("fsspec.implementations.reference") for name in sys.modules)


def test_project_and_nautilus_never_use_the_reference_filesystem():
    project = subprocess.run(
        ["grep", "-rn", "ReferenceFileSystem", str(ROOT / "factory"), str(ROOT / "apps")],
        capture_output=True,
        text=True,
    )
    assert project.returncode != 0, "project code began using ReferenceFileSystem"
    nautilus_root = Path(nautilus_trader.__file__).resolve().parent
    installed = subprocess.run(
        ["grep", "-rn", "ReferenceFileSystem", str(nautilus_root)],
        capture_output=True,
        text=True,
    )
    assert installed.returncode != 0, "Nautilus began using ReferenceFileSystem"


def test_fsspec_remains_an_exact_nautilus_pin():
    """A newer fsspec would silently override an upstream exact pin."""
    from importlib.metadata import requires

    pins = [r for r in requires("nautilus_trader") or [] if r.lower().startswith("fsspec")]
    assert pins == ["fsspec (==2026.2.0)"], pins


def test_runner_import_is_sufficient_to_load_simulation_stack():
    """Guard against the reachability check passing on an unimported runner."""
    assert callable(runner.replay)
