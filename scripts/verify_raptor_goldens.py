"""Verify the Rust engine against the frozen NautilusTrader goldens.

Reads `reports/raptor-migration-goldens.json`, regenerates the same deterministic
corpus, runs the Rust engine and compares each case's exact result digest.

Usage:
    .venv/bin/python scripts/verify_raptor_goldens.py [--goldens PATH]
"""

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import parity_raptor_engine as harness


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--goldens", default="reports/raptor-migration-goldens.json")
    args = parser.parse_args()

    if not harness.BINARY.exists():
        print(f"rust binary missing: {harness.BINARY}", file=sys.stderr)
        return 2
    artifact = json.loads(Path(args.goldens).read_text())
    cases = artifact["cases"]
    rng = random.Random(artifact["corpus"]["seed"])

    passed = 0
    failures = []
    for entry in cases:
        instrument = rng.choice(harness.INSTRUMENTS)
        profile, spec, quotes, signals, partial, fill_model = harness.generate_case(
            rng, instrument
        )
        if "rejected" in entry:
            continue
        scale = profile.price_scale
        request = harness.build_request(profile, spec, quotes, signals, True, partial)
        rs = harness.run_rust(request)
        payload = json.dumps(rs, sort_keys=True, separators=(",", ":"))
        import hashlib

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
