"""Dashboard attestations must match a backend literal.

Each report and action endpoint pins its own attestation literal. A panel sending
a different string fails at runtime with 422 and surfaces only as an alert after
the user clicks, which is how the Research reports panel shipped broken: one
generic attestation for three endpoints that each pin their own.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check-dashboard-attestations.py"


def _script():
    spec = importlib.util.spec_from_file_location("check_attestations", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_panel_attestation_has_a_backend_literal():
    module = _script()
    unmatched = {
        literal: names
        for literal, names in module.panel_literals().items()
        if literal not in module.backend_literals()
    }
    assert not unmatched, (
        f"dashboard panels send attestations no backend endpoint accepts: {unmatched}"
    )


def test_the_check_fails_on_a_mismatched_panel(tmp_path, monkeypatch):
    """The check must actually catch a mismatch, not just pass vacuously."""
    module = _script()
    real = module.PANELS
    fake = tmp_path / "lib"
    fake.mkdir()
    (fake / "Broken.svelte").write_text(
        "<button>Go</button>\n"
        "<span>'Report something no endpoint asked for; no qualification'</span>\n"
    )
    monkeypatch.setattr(module, "PANELS", fake)
    assert module.panel_literals(), "fixture panel should declare a literal"
    unmatched = {
        literal: names
        for literal, names in module.panel_literals().items()
        if literal not in module.backend_literals()
    }
    assert unmatched != {}, "a mismatched panel must be reported"
    assert module.PANELS is fake or real  # keep the reference alive for readability


def test_script_exits_zero_on_the_real_tree():
    result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "unmatched panel literals: 0" in result.stdout
