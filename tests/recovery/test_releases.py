import json
import os
import subprocess
import sys
import pytest
from factory.data import sha256
from factory.operations.releases import switch_release


def test_T22_pointer_health_failure(tmp_path):
    # Synthetic release manifests exercise pointer mechanics only, not release acceptance.
    old = tmp_path / "releases" / "fixture-old"
    old.mkdir(parents=True)
    new = tmp_path / "releases" / "fixture-new"
    new.mkdir()
    for release in (old, new):
        (release / "fixture").write_text("synthetic deployment fixture")
        (release / "release-manifest.json").write_text(
            json.dumps(
                {
                    "status": "OPERATION_READY",
                    "commit": "synthetic",
                    "tag": release.name,
                    "files": {"fixture": sha256(release / "fixture")},
                }
            )
        )
    os.symlink(old, tmp_path / "current")
    with pytest.raises(subprocess.CalledProcessError):
        switch_release(tmp_path, new, [sys.executable, "-c", "raise SystemExit(1)"])
    assert (tmp_path / "current").resolve() == old
    switch_release(tmp_path, new, [sys.executable, "-c", "raise SystemExit(0)"])
    assert (tmp_path / "current").resolve() == new
    assert (tmp_path / "previous").resolve() == old
