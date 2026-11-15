"""DEV ONLY: real historical state for the Source quality browser acceptance.

Runs the source-quality scanner over one genuine acquired partition per
instrument, straight from the real catalog, and leaves the receipts in a fresh
isolated state so the dashboard browser smoke can inspect them.

This is the fixture the browser smoke has always needed and never had: until now
the scans could only be produced from synthetic TEST_ONLY data, so the panel was
never exercised against real provider archives. It is still not market evidence:
the scanner reports technical source integrity and declared rules, and
`historical_admission` is always false because no calendar or instrument profile
is supplied.

Not market validation and not DATA_READY.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "tests"), str(root / "tests" / "integration")]

DEFAULT_CATALOG = Path("/var/lib/hermes-factory/catalog")
INSTRUMENTS = (
    "AUDUSD",
    "EURUSD",
    "GBPUSD",
    "NZDUSD",
    "USDCAD",
    "USDCHF",
    "USDJPY",
    "XAUUSD",
)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--state", type=Path, required=True)
parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
parser.add_argument(
    "--year",
    type=int,
    default=2026,
    help="preferred acquisition year when choosing a partition per instrument",
)
args = parser.parse_args()

state = args.state
if state.exists():
    raise SystemExit("Use a new isolated state; never overwrite earlier browser evidence")
if not args.catalog.is_dir():
    raise SystemExit(f"catalog not found: {args.catalog}")

from factory.contracts import fingerprint  # noqa: E402
from factory.data import Catalog  # noqa: E402
from factory.data.source_quality import SourceQuality, SourceQualityPolicy  # noqa: E402

policy = SourceQualityPolicy.model_validate_json(
    (root / "config" / "source-quality-policy.example.json").read_text()
)

catalog = Catalog(args.catalog)
# One genuine partition per instrument. Prefer the requested year, then the most
# recent available, so the smoke always has eight real scans to inspect.
chosen = {}
for instrument in INSTRUMENTS:
    candidates = []
    for entry in args.catalog.iterdir():
        manifest_file = entry / "manifest.json"
        if not entry.is_dir() or not manifest_file.exists():
            continue
        try:
            manifest = json.loads(manifest_file.read_text())
        except (OSError, ValueError):
            continue
        if manifest.get("instrument") != instrument:
            continue
        if manifest.get("provenance", {}).get("synthetic"):
            continue
        first_ns = manifest.get("first_ns") or 0
        candidates.append((first_ns, manifest["dataset_hash"]))
    if not candidates:
        raise SystemExit(f"no real acquired partition for {instrument}")
    candidates.sort(reverse=True)
    match = [h for ns, h in candidates if ns // (10**9 * 86400 * 365) + 1970 == args.year]
    chosen[instrument] = match[0] if match else candidates[0][1]

state.mkdir(parents=True)
subprocess.run(
    [sys.executable, "-m", "factory.cli", "--state", str(state), "create-admin"],
    cwd=root,
    check=True,
    stdout=subprocess.DEVNULL,
)

quality = SourceQuality(state, catalog)
receipts = []
for instrument in INSTRUMENTS:
    dataset_hash = chosen[instrument]
    report = quality.run(dataset_hash, policy)
    receipts.append(
        {
            "instrument": instrument,
            "run_id": report["run_id"],
            "rows_scanned": report["counts"]["rows_scanned"],
            "source_structural_status": report["source_structural_status"],
            "historical_admission": report["historical_admission"],
        }
    )
    print(
        f"  {instrument:<7} {report['counts']['rows_scanned']:>10,} rows  "
        f"{report['source_structural_status']}"
    )

failed = [r for r in receipts if r["source_structural_status"] != "PASS"]
if failed:
    raise SystemExit(f"structural scan did not pass: {failed}")
if len(receipts) != 8:
    raise SystemExit(f"expected eight real scans, got {len(receipts)}")

print(
    f"TEST_ONLY real-source state with {len(receipts)} genuine acquired partitions "
    f"({sum(r['rows_scanned'] for r in receipts):,} rows scanned); "
    "calendar and instrument metadata remain UNKNOWN, so no historical admission "
    "is claimed and no strategy is qualified, ranked or promoted"
)
