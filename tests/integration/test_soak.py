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
