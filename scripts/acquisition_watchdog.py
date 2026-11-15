"""Acquisition watchdog: prints a message only when attention is needed.

A ``no_agent`` scheduler delivers stdout verbatim, so a healthy run prints
nothing and stays silent. The watchdog is deterministic and never imports the
scientific stack, so it keeps running even when the model or network is
unavailable.
"""

import json
from pathlib import Path
import shutil
import subprocess

STATE = Path("/var/lib/hermes-factory")
CHECKPOINT = STATE / "backfill" / "checkpoint.json"
MARKER = STATE / "backfill" / "watchdog.json"
TOTAL_PARTITIONS = 176
STALL_HOURS = 3.0
DISK_RESERVE_BYTES = 2 * 1024**3


def supervisor_alive():
    try:
        result = subprocess.run(
            ["pgrep", "-f", "scripts/acquire_history[.]py"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return bool(result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return False


def main():
    if not CHECKPOINT.exists():
        print(f"ACQUISITION NEEDS ATTENTION: checkpoint missing at {CHECKPOINT}")
        return
    state = json.loads(CHECKPOINT.read_text())
    partitions = state.get("partitions", {})
    passed = sorted(k for k, v in partitions.items() if v.get("state") == "STRUCTURAL_IMPORT_PASS")
    blocked = sorted(k for k, v in partitions.items() if v.get("state") == "BLOCKED")
    remaining = TOTAL_PARTITIONS - len(passed)
    if remaining <= 0:
        print(
            f"ACQUISITION COMPLETE: {len(passed)}/{TOTAL_PARTITIONS} partitions structurally "
            "imported. Verify receipts and calendar coverage before any DATA_READY claim."
        )
        return
    problems = []
    alive = supervisor_alive()
    if not alive:
        problems.append(
            f"supervisor not running; {remaining} partitions remain "
            f"({len(passed)}/{TOTAL_PARTITIONS} done)"
        )
    if blocked:
        problems.append(f"{len(blocked)} blocked partitions: " + ", ".join(blocked[:5]))
    free = shutil.disk_usage(STATE).free
    if free < DISK_RESERVE_BYTES:
        problems.append(f"disk reserve low: {free} bytes free on {STATE}")
    marker = {}
    if MARKER.exists():
        try:
            marker = json.loads(MARKER.read_text())
        except ValueError:
            marker = {}
    previous = marker.get("completed")
    if previous is not None and len(passed) <= previous and alive:
        problems.append(
            f"no partition completed since the previous check "
            f"({len(passed)}/{TOTAL_PARTITIONS}); inspect supervisor.log"
        )
    MARKER.write_text(json.dumps({"completed": len(passed), "remaining": remaining}) + "\n")
    if problems:
        print("ACQUISITION NEEDS ATTENTION: " + "; ".join(problems))


if __name__ == "__main__":
    main()
