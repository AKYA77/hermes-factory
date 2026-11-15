#!/usr/bin/env python3
"""Verify the Rust engine against the frozen NautilusTrader goldens.

Reads `reports/raptor-migration-goldens.json`, regenerates the same deterministic
corpus, runs the Rust engine and compares each case's exact result digest.

This script imports only the Nautilus-free ``raptor_cases`` module, so the frozen
goldens stay verifiable after NautilusTrader is removed.

Usage:
    .venv/bin/python scripts/verify_raptor_goldens.py [--goldens PATH]
"""

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import raptor_cases as cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--goldens", default="reports/raptor-migration-goldens.json")
    args = parser.parse_args()

    if not cases.BINARY.exists():
        print(f"rust binary missing: {cases.BINARY}", file=sys.stderr)
        return 2
    artifact = json.loads(Path(args.goldens).read_text())
    entries = artifact["cases"]
    rng = random.Random(artifact["corpus"]["seed"])

    passed = 0
    failures = []
    for entry in entries:
        instrument = rng.choice(cases.INSTRUMENTS)
        profile, spec, quotes, signals, partial = cases.generate_case_params(
            rng, instrument
        )
        if "rejected" in entry:
            continue
        request = cases.build_request(profile, spec, quotes, signals, True, partial)
        rs = cases.run_rust(request)
        payload = json.dumps(rs, sort_keys=True, separators=(",", ":"))

        digest = hashlib.sha256(payload.encode()).hexdigest()
        if digest == entry["result_sha256"]:
            passed += 1
        else:
            failures.append(
                {
                    "case": entry["case"],
                    "instrument": entry["instrument"],
                    "expected": entry["result_sha256"],
                    "actual": digest,
                }
            )

    print(f"goldens verified {passed}/{passed + len(failures)}")
    for failure in failures[:5]:
        print(json.dumps(failure, indent=1))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
