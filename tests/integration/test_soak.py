"""Bounded synthetic soak run under resource limits."""

import json

import pytest

from factory.operations.soak import DEFAULT_MAX_RSS_BYTES, run


def test_soak_completes_within_limits(tmp_path):
    output = tmp_path / "soak.json"
    report = run(output, iterations=2)
    assert report["status"] == "BOUNDED_SYNTHETIC_SOAK"
    assert report["iterations_completed"] == 2
    assert report["within_limits"] is True
    assert report["oom_detected"] is False
    assert report["limits"]["max_rss_bytes"] == DEFAULT_MAX_RSS_BYTES
    assert output.exists()
    archived = json.loads(output.read_text())
    assert archived["peak_rss_bytes_sampled"] > 0
    assert archived["iterations_completed"] == 2


def test_soak_reports_a_tiny_memory_limit_as_breached(tmp_path):
    output = tmp_path / "soak.json"
    report = run(output, iterations=1, max_rss_bytes=1)
    assert report["oom_detected"] is True
    assert report["within_limits"] is False
    assert report["records"][0]["status"] == "STOPPED_RSS_LIMIT"


def test_soak_rejects_invalid_limits(tmp_path):
    with pytest.raises(ValueError, match="at least one iteration"):
        run(tmp_path / "s.json", iterations=0)
    with pytest.raises(ValueError, match="must be positive"):
        run(tmp_path / "s.json", max_rss_bytes=0)
    with pytest.raises(ValueError, match="must be positive"):
        run(tmp_path / "s.json", max_wall_seconds=0)
    with pytest.raises(ValueError, match="at least one row"):
        run(tmp_path / "s.json", rows=0)


def test_soak_records_rows_per_iteration(tmp_path):
    output = tmp_path / "soak.json"
    report = run(output, iterations=1, rows=500)
    assert report["rows_per_iteration"] == 500
    assert report["iterations_completed"] == 1


def _load_wrapper():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "scripts" / "enforced_soak.py"
    spec = importlib.util.spec_from_file_location("enforced_soak", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_enforced_soak_requires_systemd_run(tmp_path, monkeypatch):
    wrapper = _load_wrapper()
    monkeypatch.setattr(
        "pathlib.Path.exists",
        lambda self: False if self.name == "systemd-run" else True,
    )
    with pytest.raises(RuntimeError, match="systemd-run is required"):
        wrapper.run(tmp_path / "s.json", iterations=1, rows=100)


def test_enforced_soak_records_observed_cgroup_limits(tmp_path, monkeypatch):
    """The wrapper must record the limits the kernel applied, not the requested ones."""
    import subprocess

    wrapper = _load_wrapper()
    output = tmp_path / "soak.json"
    limits_path = output.with_suffix(".cgroup-limits.json")

    real_run = subprocess.run

    def fake_run(command, **kwargs):
        if isinstance(command, list) and command and command[0] == "systemd-run":
            limits_path.write_text(
                json.dumps(
                    {
                        "cgroup_path": "0::/system.slice/run-test.scope",
                        "memory_max": "8589934592",
                        "cpu_max": "400000 100000",
                        "swap_max": "0",
                    }
                )
            )
            run(output, iterations=1, rows=500)
            return subprocess.CompletedProcess(command, 0, "", "")
        return real_run(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)
    report = wrapper.run(output, iterations=1, rows=500)
    enforcement = report["enforcement"]
    assert enforcement["requested"] == {
        "MemoryMax": "8G",
        "CPUQuota": "400%",
        "MemorySwapMax": "0",
    }
    assert enforcement["observed"]["memory_max"] == "8589934592"
    assert enforcement["observed"]["cpu_max"] == "400000 100000"
    assert enforcement["observed"]["swap_max"] == "0"
    assert enforcement["host"]["nproc"]
    assert report["within_limits"] is True
