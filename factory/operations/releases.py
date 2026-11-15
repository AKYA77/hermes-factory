"""Atomic release pointer changes with explicit manifest and health gates.

This does not claim production migration rollback: state migrations require a
separate restored snapshot and stopped services before activating a prior binary.
"""

import json
import os
from pathlib import Path
import subprocess
import uuid
from factory.data import atomic_bytes, sha256


def verify_release(path):
    root = Path(path).resolve()
    m = json.loads((root / "release-manifest.json").read_text())
    if m.get("status") != "OPERATION_READY" or not m.get("commit") or not m.get("tag"):
        raise ValueError("release gates not passed")
    if not m.get("files"):
        raise ValueError("empty release manifest")
    for name, digest in m["files"].items():
        p = (root / name).resolve()
        if root not in p.parents or sha256(p) != digest:
            raise ValueError("release checksum mismatch")
    return m


def switch_release(install_root, candidate, health_command):
    root = Path(install_root).resolve()
    candidate = Path(candidate).resolve()
    if candidate.parent != root / "releases":
        raise ValueError("candidate outside release directory")
    verify_release(candidate)
    current = root / "current"
    previous = current.resolve() if current.is_symlink() else None
    if current.exists() and not current.is_symlink():
        raise ValueError("current is not a symlink")
    temp = root / ("switch-" + uuid.uuid4().hex)
    os.symlink(candidate, temp)
    os.replace(temp, current)
    try:
        subprocess.run(
            health_command,
            cwd=candidate,
            check=True,
            timeout=60,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except BaseException:
        if previous:
            os.symlink(previous, temp)
            os.replace(temp, current)
        else:
            current.unlink()
        atomic_bytes(
            root / "last-switch.json",
            json.dumps({"status": "ROLLED_BACK", "failed": candidate.name}).encode(),
        )
        raise
    if previous:
        prev = root / "previous"
        os.symlink(previous, temp)
        os.replace(temp, prev)
    atomic_bytes(
        root / "last-switch.json",
        json.dumps(
            {
                "status": "ACTIVE",
                "release": candidate.name,
                "previous": previous.name if previous else None,
            }
        ).encode(),
    )
