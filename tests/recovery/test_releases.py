import json
import os
import subprocess
import sys
import pytest
from factory.data import sha256
from factory.operations.releases import switch_release, verify_release


def write_release(
    root, name, fixture, *, status="OPERATION_READY", commit="abc123", tag=None, files=None
):
    release = root / "releases" / name
    release.mkdir(parents=True)
    (release / "fixture").write_text(fixture)
    manifest = {
        "status": status,
        "commit": commit,
        "tag": tag if tag is not None else name,
        "files": files if files is not None else {"fixture": sha256(release / "fixture")},
    }
    (release / "release-manifest.json").write_text(json.dumps(manifest))
    return release


def test_verify_release_accepts_a_consistent_manifest(tmp_path):
    release = write_release(tmp_path, "ok", "synthetic deployment fixture")
    manifest = verify_release(release)
    assert manifest["status"] == "OPERATION_READY"
    assert manifest["commit"] == "abc123"


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"status": "NOT_READY"}, "release gates not passed"),
        ({"commit": ""}, "release gates not passed"),
        ({"tag": ""}, "release gates not passed"),
        ({"files": {}}, "empty release manifest"),
    ],
)
def test_verify_release_refuses_incomplete_manifests(tmp_path, kwargs, match):
    release = write_release(tmp_path, "bad", "fixture", **kwargs)
    with pytest.raises(ValueError, match=match):
        verify_release(release)


def test_verify_release_refuses_a_checksum_mismatch(tmp_path):
    release = write_release(tmp_path, "tampered", "original")
    (release / "fixture").write_text("tampered")
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify_release(release)


def test_verify_release_refuses_paths_escaping_the_release_root(tmp_path):
    release = write_release(tmp_path, "escape", "fixture")
    outside = tmp_path / "outside"
    outside.write_text("outside")
    (release / "release-manifest.json").write_text(
        json.dumps(
            {
                "status": "OPERATION_READY",
                "commit": "abc123",
                "tag": "escape",
                "files": {"../outside": sha256(outside)},
            }
        )
    )
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify_release(release)


def test_T22_pointer_health_failure(tmp_path):
    # Synthetic release manifests exercise pointer mechanics only, not release acceptance.
    old = write_release(tmp_path, "fixture-old", "synthetic deployment fixture")
    new = write_release(tmp_path, "fixture-new", "synthetic deployment fixture")
    os.symlink(old, tmp_path / "current")
    with pytest.raises(subprocess.CalledProcessError):
        switch_release(tmp_path, new, [sys.executable, "-c", "raise SystemExit(1)"])
    assert (tmp_path / "current").resolve() == old
    switch_release(tmp_path, new, [sys.executable, "-c", "raise SystemExit(0)"])
    assert (tmp_path / "current").resolve() == new
    assert (tmp_path / "previous").resolve() == old
