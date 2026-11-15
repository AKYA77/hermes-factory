"""Inspect the durable engineering queue without manufacturing acceptance.

The active agent performs implementation cycles. This script does not execute
generated code, change gate results, or promise work after a session ends.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def inspect(root):
    ledger_path = root / "completion-ledger.json"
    ledger = json.loads(ledger_path.read_text())
    queue = json.loads((root / "implementation-queue.json").read_text())
    if queue["schema_version"] != "engineering-queue/v1":
        raise ValueError("unsupported engineering queue")
    requirements = {r["requirement_id"]: r for r in ledger["requirements"]}
    tasks = {t["id"]: t for t in queue["tasks"]}
    if len(tasks) != len(queue["tasks"]):
        raise ValueError("duplicate engineering task")
    mapped = {r for t in tasks.values() for r in t["requirements"]}
    if mapped != set(requirements):
        raise ValueError("engineering queue does not cover the exact acceptance ledger")
    states = {"QUEUED", "IMPLEMENTING", "VERIFIED_SCOPE", "EXTERNAL_ONLY"}
    for task in tasks.values():
        if task["state"] not in states:
            raise ValueError("unknown engineering task state")
        if any(d not in tasks for d in task.get("depends_on", [])):
            raise ValueError("unknown task prerequisite")
    unresolved = [r for r in requirements.values() if r["status"] != "PASS"]
    pending = [t for t in tasks.values() if t["state"] in ("QUEUED", "IMPLEMENTING")]
    covered = {
        r for t in tasks.values() if t["state"] != "VERIFIED_SCOPE" for r in t["requirements"]
    }
    if any(r["requirement_id"] not in covered for r in unresolved):
        raise ValueError("unfinished gate lost behind a scoped checkpoint")
    eligible = [
        t
        for t in pending
        if all(tasks[d]["state"] == "VERIFIED_SCOPE" for d in t.get("depends_on", []))
    ]
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    status = subprocess.check_output(
        ["git", "-C", str(root), "status", "--short"], text=True
    ).splitlines()
    return {
        "head": head,
        "working_tree_changes": status,
        "ledger_sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
        "next_task": min(eligible, key=lambda t: (t["priority"], t["id"])) if eligible else None,
        "unfinished_requirements": [
            {
                "id": r["requirement_id"],
                "status": r["status"],
                "next_required_action": r.get("next_required_action"),
            }
            for r in unresolved
        ],
        "readiness": ledger["readiness"],
        "scope": "Queue coverage and next action only; no acceptance result is inferred from task state or report presence.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--snapshot", type=Path)
    args = parser.parse_args()
    report = inspect(args.root)
    encoded = json.dumps(report, indent=2) + "\n"
    if args.snapshot:
        args.snapshot.parent.mkdir(parents=True, exist_ok=True)
        args.snapshot.write_text(encoded)
    print(encoded)
