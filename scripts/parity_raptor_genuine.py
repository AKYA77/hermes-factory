"""Parity over genuine acquired catalog partitions.

Reads real published partitions through the production catalog API, generates
signals over a bounded quote window, and compares the Python reference engine
with the Rust engine exactly.

Usage:
    .venv/bin/python scripts/parity_raptor_genuine.py [--partitions N] [--window N]
"""

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import parity_raptor_engine as harness
from factory.contracts import Signal, StrategySpec
from factory.data import Catalog
from factory.instruments import declared_tick_profile

STATE_ROOT = Path("/var/lib/hermes-factory")
CATALOG_DIR = STATE_ROOT / "catalog"


def partitions():
    out = []
    for entry in sorted(CATALOG_DIR.iterdir()):
        manifest = entry / "manifest.json"
        if entry.is_dir() and manifest.exists():
            try:
                out.append(json.loads(manifest.read_text()))
            except Exception:
                continue
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--partitions", type=int, default=8)
    parser.add_argument("--window", type=int, default=4000, help="quote window in seconds")
    parser.add_argument("--seed", type=int, default=20261112)
    args = parser.parse_args()

    if not harness.BINARY.exists():
        print(f"rust binary missing: {harness.BINARY}", file=sys.stderr)
        return 2

    catalog = Catalog(CATALOG_DIR)
    manifests = partitions()
    rng = random.Random(args.seed)
    rng.shuffle(manifests)

    passed = 0
    failures = []
    checked = 0
    for manifest in manifests[: args.partitions]:
        identity = manifest["dataset_hash"]
        instrument = manifest["instrument"]
        scale = int(manifest["price_scale"])
        precision = manifest.get("source_precision", "millisecond")
        profile = declared_tick_profile(
            instrument, scale, precision, "declared/v1"
        )
        first_ns = int(manifest["first_ns"])
        last_ns = int(manifest["latest_verified_ns"])
        span = last_ns - first_ns
        if span <= 0:
            continue
        start = first_ns + rng.randint(0, max(0, span - 1))
        window_ns = rng.randint(args.window // 2, args.window) * 10**9
        end = start + min(span, window_ns)
        quotes = list(catalog.read(identity, start_ns=start, end_ns=end))
        if len(quotes) < 8:
            continue
        step = max(1, len(quotes) // 8)
        signals = []
        for index in range(1, 8):
            position = min(len(quotes) - 1, index * step)
            signals.append(
                {
                    "available_at": quotes[position].event_ts_utc_ns - 1,
                    "side": rng.choice(["BUY", "SELL"]),
                }
            )
        signals.sort(key=lambda s: s["available_at"])
        spec = StrategySpec(
            instrument=instrument,
            timeframe="M1",
            signal=Signal(operator="momentum", lookback=2, threshold="1"),
            stop_ticks=rng.choice([50, 100, 200]),
            max_hold_seconds=86400,
            direction="both",
        )
        try:
            raw = harness.replay(quotes, profile, spec, signals, True)
        except Exception as exc:
            failures.append({"instrument": instrument, "error": f"reference: {exc}"})
            continue
        py = harness.normalize_python(raw, scale)
        request = harness.build_request(profile, spec, quotes, signals, True)
        try:
            rs = harness.run_rust(request)
        except Exception as exc:
            failures.append({"instrument": instrument, "error": f"rust: {exc}"})
            continue
        mismatches = []
        harness.compare(py, rs, mismatches)
        checked += 1
        if mismatches:
            failures.append(
                {
                    "instrument": instrument,
                    "quotes": len(quotes),
                    "stop_ticks": spec.stop_ticks,
                    "mismatches": mismatches[:6],
                }
            )
        else:
            passed += 1

    print(f"genuine partitions passed {passed}/{checked}")
    for failure in failures[:5]:
        print(json.dumps(failure, indent=1)[:3000])
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
