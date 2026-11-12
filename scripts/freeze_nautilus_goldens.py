"""Freeze the NautilusTrader reference goldens for the RaptorBT migration.

Runs the Python reference engine over a fixed deterministic corpus and writes a
committed artifact containing, per case, the exact result digest plus the
reference engine identity. The RaptorBT migration must reproduce these digests
exactly before NautilusTrader is removed.

Usage:
    .venv/bin/python scripts/freeze_nautilus_goldens.py [--cases N] [--output PATH]
"""

import argparse
import hashlib
import json
import random
import sys
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import parity_raptor_engine as harness


def digest(result, scale):
    normalized = harness.normalize_python(result, scale)
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=240)
    parser.add_argument("--seed", type=int, default=20261112)
    parser.add_argument(
        "--output",
        default="reports/raptor-migration-goldens.json",
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)
    cases = []
    for case in range(args.cases):
        instrument = rng.choice(harness.INSTRUMENTS)
        profile, spec, quotes, signals = harness.generate_case(rng, instrument)
        scale = profile.price_scale
        try:
            result = harness.replay(quotes, profile, spec, signals, True)
        except Exception as exc:
            cases.append({"case": case, "instrument": instrument, "rejected": str(exc)})
            continue
        cases.append(
            {
                "case": case,
                "instrument": instrument,
                "stop_ticks": spec.stop_ticks,
                "direction": spec.direction,
                "max_hold_seconds": spec.max_hold_seconds,
                "quote_count": len(quotes),
                "signal_count": len(signals),
                "result_sha256": digest(result, scale),
                "trade_count": len(result["trades"]),
                "fill_count": len(result["fills"]),
            }
        )

    artifact = {
        "schema_version": "raptor-migration-goldens/v1",
        "reference_engine": "nautilus_trader",
        "reference_engine_version": version("nautilus_trader"),
        "fill_version": "adverse-fill/v4",
        "corpus": {"seed": args.seed, "cases": args.cases},
        "cases": cases,
    }
    payload = json.dumps(artifact, indent=2, sort_keys=True).encode()
    artifact["artifact_sha256"] = hashlib.sha256(payload).hexdigest()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    print(f"wrote {out} ({len(cases)} cases, {artifact['artifact_sha256'][:16]}...)")


if __name__ == "__main__":
    raise SystemExit(main())
