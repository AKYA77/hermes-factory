"""Pytest front-end for the Rust execution engine parity evidence.

These tests exercise the real CLI entry points (not internal helpers) so the
R01-R12 verification command `.venv/bin/pytest tests/parity` reproduces the same
evidence the migration report records.

The corpora are bounded so the suite stays fast; the full corpora remain in
`scripts/parity_*.py` and run in CI.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"

FIXTURE_CASES = 40
RESTART_CASES = 24


def run_script(name: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=900,
    )


def test_frozen_goldens_reproduce() -> None:
    """The Rust engine reproduces every frozen NautilusTrader golden digest."""
    result = run_script("verify_raptor_goldens.py")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "goldens verified 240/240" in result.stdout


def test_goldens_reproduce_without_nautilus_trader() -> None:
    """The golden evidence does not depend on NautilusTrader being installed."""
    result = run_script("verify_goldens_without_nautilus.py")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "goldens verified 240/240" in result.stdout


def test_generated_fixture_parity() -> None:
    """Direct comparison against the Python reference on generated fixtures."""
    result = run_script(
        "parity_raptor_engine.py",
        "--cases",
        str(FIXTURE_CASES),
        "--instrument",
        "all",
        "--seed",
        "20261112",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"passed {FIXTURE_CASES}/{FIXTURE_CASES}" in result.stdout


def test_restart_and_batch_equivalence() -> None:
    """Batching and cross-process restart reproduce the single-pass result."""
    result = run_script(
        "parity_raptor_restart.py",
        "--cases",
        str(RESTART_CASES),
        "--instrument",
        "all",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "restart/batch parity passed" in result.stdout


def test_rust_engine_binary_exists() -> None:
    """The crate builds to the binary the harnesses invoke."""
    assert (ROOT / "rust/raptor-engine/target/release/raptor-engine").exists()
