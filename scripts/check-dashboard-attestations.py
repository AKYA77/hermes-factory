#!/usr/bin/env python3
"""Check that every dashboard attestation matches a backend literal.

Each report and action endpoint pins its own attestation literal. A panel that
sends a different string fails at runtime with 422 and surfaces only as an alert
after the user clicks, which is how the Research reports panel shipped broken.

This compares the literals declared in apps/dashboard/src/lib/*.svelte against
every attestation literal defined under factory/, so the mismatch is caught before
it reaches a browser. Backend literals with no panel are reported separately:
those endpoints are reached through the CLI or API rather than the dashboard.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANELS = ROOT / "apps/dashboard/src/lib"
FACTORY = ROOT / "factory"

PANEL_PATTERN = re.compile(r"['\"]((?:Report|Rank|Compare|Freeze|I authorize)[^'\"]{25,})['\"]")


def backend_literals():
    found = {}
    for path in sorted(FACTORY.rglob("*.py")):
        text = path.read_text()
        candidates = []
        for match in re.finditer(r"ATTESTATION\s*=\s*\(([^)]*)\)", text, re.S):
            candidates.append("".join(re.findall(r'"([^"]*)"', match.group(1))))
        for match in re.finditer(r'ATTESTATION\s*=\s*"([^"]*)"', text):
            candidates.append(match.group(1))
        # Inline form: attestation: Literal["..."] or a multi-line Literal[...].
        for match in re.finditer(r"attestation:\s*Literal\[([^\]]*)\]", text, re.S):
            candidates.append("".join(re.findall(r'"([^"]*)"', match.group(1))))
        for literal in candidates:
            if literal:
                found.setdefault(literal, []).append(str(path.relative_to(ROOT)))
    return found


def panel_literals():
    found = {}
    for path in sorted(PANELS.glob("*.svelte")):
        for literal in set(PANEL_PATTERN.findall(path.read_text())):
            found.setdefault(literal, []).append(path.name)
    return found


def main():
    backend = backend_literals()
    panels = panel_literals()

    unmatched = {literal: names for literal, names in panels.items() if literal not in backend}
    for literal, names in sorted(unmatched.items()):
        print(f"NO BACKEND MATCH: {', '.join(sorted(names))}")
        print(f"    {literal}")

    print(f"panel literals: {len(panels)} | backend literals: {len(backend)}")
    print(f"unmatched panel literals: {len(unmatched)}")

    unreferenced = sorted(set(backend) - set(panels))
    if unreferenced:
        print(f"\nbackend literals with no panel ({len(unreferenced)}), reached via CLI/API:")
        for literal in unreferenced:
            print(f"  {literal[:90]}  <- {backend[literal][0]}")

    return 1 if unmatched else 0


if __name__ == "__main__":
    sys.exit(main())
