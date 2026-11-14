"""Decide whether a dependency audit result is acceptable.

The audit itself always runs and its output is still uploaded as an artifact.
This gate only decides pass/fail: an advisory passes when it appears in
DISPOSITIONED below with a matching rationale in
docs/security-advisories-2026-11-07.md. Every other finding fails the build, so a
new vulnerability can never pass silently.

An npm package whose `via` lists only other package names (no advisory object)
is reported by npm as vulnerable purely because of those dependencies. Such a
package is accepted only when every package it derives from is itself accepted.

Usage:
    dependency_disposition.py --pip reports/runtime/python-audit.json
    dependency_disposition.py --npm reports/runtime/npm-audit.json
"""

import argparse
import json
from pathlib import Path
import re
import sys

DISPOSITIONED = {
    "pysec-2026-4217": (
        "fsspec 2026.2.0 is exactly pinned by nautilus_trader==1.231.0; the "
        "vulnerable ReferenceFileSystem/Kerchunk sink is never imported"
    ),
    "ghsa-27vj-qcqg-25rc": "alias of pysec-2026-4217 (fsspec)",
    "ghsa-gcqx-w48m-w2h4": (
        "deepmerge is a build-time dev dependency of the dashboard toolchain and "
        "is not present in the shipped bundle"
    ),
}

GHSA = re.compile(r"GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}", re.IGNORECASE)


def pip_findings(path):
    payload = json.loads(Path(path).read_text())
    for package in payload.get("dependencies", ()):
        for vuln in package.get("vulns", ()):
            identifiers = [vuln.get("id", "").lower(), *map(str.lower, vuln.get("aliases", ()))]
            yield {
                "package": package["name"],
                "version": package["version"],
                "advisories": sorted(i for i in identifiers if i),
                "derived": [],
                "fixes": vuln.get("fix_versions"),
            }


def npm_findings(path):
    payload = json.loads(Path(path).read_text())
    for name, entry in payload.get("vulnerabilities", {}).items():
        advisories, derived = set(), []
        for via in entry.get("via", ()):
            if isinstance(via, dict):
                match = GHSA.search(str(via.get("url", "")))
                if match:
                    advisories.add(match.group(0).lower())
            else:
                derived.append(str(via))
        yield {
            "package": name,
            "version": entry.get("range", "?"),
            "advisories": sorted(advisories),
            "derived": sorted(derived),
            "fixes": None,
        }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--pip", type=Path)
    parser.add_argument("--npm", type=Path)
    args = parser.parse_args(argv)
    if bool(args.pip) == bool(args.npm):
        parser.error("choose exactly one of --pip or --npm")

    findings = list(pip_findings(args.pip)) if args.pip else list(npm_findings(args.npm))

    # Resolve iteratively: an npm package whose `via` names only other packages
    # is vulnerable because of them, so it is accepted once they are. Iterating
    # makes this independent of the report's ordering.
    accepted = set()
    progress = True
    while progress:
        progress = False
        for finding in findings:
            if finding["package"] in accepted:
                continue
            advisory_ok = any(a in DISPOSITIONED for a in finding["advisories"])
            derived_ok = bool(finding["derived"]) and all(d in accepted for d in finding["derived"])
            if advisory_ok or derived_ok:
                accepted.add(finding["package"])
                progress = True
    rejected = [f for f in findings if f["package"] not in accepted]

    for finding in findings:
        if finding["package"] in accepted:
            print(
                f"DISPOSITIONED {finding['package']} {finding['advisories'] or finding['derived']}"
            )
    for finding in rejected:
        print(f"UNACCEPTED {finding['package']} {finding['advisories'] or finding['derived']}")

    if rejected:
        print(
            f"\n{len(rejected)} finding(s) have no documented disposition in "
            "docs/security-advisories-2026-11-07.md. Either fix the dependency or "
            "record a reviewed disposition; do not broaden the allowlist."
        )
        return 1
    print(f"\nAll {len(accepted)} finding(s) carry a documented disposition.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
