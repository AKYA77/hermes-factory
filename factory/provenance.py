"""Scientific source identity, including dirty/untracked source content.

Development execution requires the actual editable checkout. Wheel/release
installation needs the separate signed release provenance gate (not yet ready).
"""

import hashlib
import json
from pathlib import Path
import subprocess


def source_identity():
    root = Path(__file__).resolve().parents[1]
    actual = Path(
        subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"], text=True
        ).strip()
    ).resolve()
    if actual != root:
        raise ValueError("scientific source checkout unavailable")
    commit = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    files = [root / "pyproject.toml", root / "uv.lock"]
    for folder, pattern in [
        ("factory", "*.py"),
        ("apps/api", "*.py"),
        ("apps/coordinator", "*.py"),
        ("config", "*.yaml"),
        ("migrations", "*.sql"),
    ]:
        files.extend((root / folder).rglob(pattern))
    entries = []
    for path in sorted(files):
        if path.is_symlink():
            raise ValueError("scientific source symlink requires review")
        digest = hashlib.sha256()
        with path.open("rb") as src:
            for chunk in iter(lambda: src.read(65536), b""):
                digest.update(chunk)
        entries.append([path.relative_to(root).as_posix(), digest.hexdigest()])
    tree = hashlib.sha256(json.dumps(entries, separators=(",", ":")).encode()).hexdigest()
    return {"git_commit": commit, "source_sha256": tree}


def execution_revision():
    identity = source_identity()
    return identity["git_commit"] + "@source-sha256:" + identity["source_sha256"]
