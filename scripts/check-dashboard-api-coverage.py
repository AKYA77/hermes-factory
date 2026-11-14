#!/usr/bin/env python3
"""Check that every dashboard API call has a matching backend route.

Static cross-check between the Svelte frontend and the FastAPI backend. Run
after touching either side:

    env -u PYTHONPATH .venv/bin/python scripts/check-dashboard-api-coverage.py

Exit code is non-zero when a call has no route, so it can gate a commit.

WHY THIS NEEDS CARE: the obvious regex over `request('...')` produces a pile of
false positives, because panels build paths three different ways:

    request('research/status')                      # literal
    request(`experiments/${run_id}`)                # template literal
    request('data/quality/' + identity)             # concatenation

A naive scan captures the trailing slash of the concatenated form as a literal
path segment and reports `data/quality/` as missing, when the real call is
`/api/v1/data/quality/{identity}`. Normalise each call to a (prefix, suffix)
pair before matching, and only report a call that no route satisfies.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD = ROOT / "apps/dashboard/src"
API = ROOT / "apps/api/main.py"

# request('...'), request(`...`), download('...'), download(`...`).
# The optional third group marks a concatenated path such as
# request('research/' + action), which is a prefix of many routes, not one route.
# request/download take a whole path; stop() also takes a whole path.
# control() is different -- it takes an ACTION ('pause'/'resume') that the
# dashboard prefixes with 'research/', so it is handled separately below.
CALL_RE = re.compile(r"\b(?:request|download|stop)\(\s*(?:'([^']+)'|`([^`]+)`)\s*(\+)?")
CONTROL_RE = re.compile(r"\bcontrol\(\s*'([^']+)'\s*\)")
# The view switcher dispatches through a name -> route map, e.g.
# {Overview:'overview', Leaderboards:'leaderboards/'}; those values are real calls.
ROUTES_MAP_RE = re.compile(r"const\s+routes[^=]*=\s*\{(.*?)\}", re.S)
MAP_ENTRY_RE = re.compile(r"['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*:\s*['\"]([^'\"]+)['\"]")
ROUTE_RE = re.compile(r'@\w+\.(?:get|post|put|delete)\(\s*"([^"]+)"')


def split_call(raw: str) -> tuple[str, str]:
    """Return (prefix, suffix) for a call that may contain ${...}.

    'data/quality/${id}/events' -> ('data/quality/', '/events')
    'research/status'           -> ('research/status', '')
    """
    if "${" not in raw:
        return raw.split("?")[0].rstrip("/"), ""
    head, _, rest = raw.partition("${")
    tail = rest.split("}", 1)[1] if "}" in rest else ""
    return head.rstrip("/"), tail


def route_satisfies(route: str, prefix: str, suffix: str, concatenated: bool) -> bool:
    target = f"/api/v1/{prefix.rstrip('/')}"
    if not route.startswith(target):
        return False
    if suffix:
        return route.endswith(suffix)
    # A concatenated call ('strategies/' + id) legitimately prefixes many routes.
    return True if concatenated else route in (target, target + "/")


def main() -> int:
    if not API.exists():
        print(f"API module not found: {API}", file=sys.stderr)
        return 2

    routes = set(ROUTE_RE.findall(API.read_text()))

    calls: set[str] = set()
    for panel in sorted(DASHBOARD.rglob("*.svelte")):
        for match in CALL_RE.finditer(panel.read_text()):
            calls.add(match.group(1) or match.group(2))

    parsed = []
    for panel in sorted(DASHBOARD.rglob("*.svelte")):
        text = panel.read_text()
        for match in CALL_RE.finditer(text):
            raw = match.group(1) or match.group(2)
            parsed.append((raw, split_call(raw), bool(match.group(3))))
        # Routes-map entries are calls too; a trailing slash means the view appends
        # its own suffix (Leaderboards adds the selected symbol).
        for block in ROUTES_MAP_RE.findall(text):
            for _, raw in MAP_ENTRY_RE.findall(block):
                if raw.endswith("/"):
                    # Leaderboards adds the selected symbol, so this prefixes
                    # routes rather than naming one exactly.
                    parsed.append((raw, (raw.rstrip("/"), ""), True))
                else:
                    parsed.append((raw, split_call(raw), False))
        # control('pause') -> POST /api/v1/research/pause
        for action in CONTROL_RE.findall(text):
            raw = f"research/{action}"
            parsed.append((raw, split_call(raw), False))
    calls = {raw for raw, _, _ in parsed}

    missing = []
    for raw, (prefix, suffix), concatenated in sorted(parsed):
        if not any(route_satisfies(r, prefix, suffix, concatenated) for r in routes):
            missing.append(raw)

    print(f"dashboard calls: {len(calls)} | backend routes: {len(routes)}")

    uncalled = sorted(
        route
        for route in routes
        if not any(
            route_satisfies(route, prefix, suffix, concatenated)
            for _, (prefix, suffix), concatenated in parsed
        )
    )
    if "--uncalled" in sys.argv:
        print(f"\nBACKEND ROUTES WITH NO DASHBOARD CALLER ({len(uncalled)}):")
        for route in uncalled:
            print(f"  {route}")
    elif uncalled:
        print(
            f"\n({len(uncalled)} backend routes have no dashboard caller; "
            "pass --uncalled to list them)"
        )

    if missing:
        print("\nNO BACKEND ROUTE:")
        for call in missing:
            print(f"  {call}")
        return 1

    print("all dashboard API calls match a backend route")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
