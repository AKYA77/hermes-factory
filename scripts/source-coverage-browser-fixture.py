"""DEV ONLY: real source-coverage state for the dashboard browser acceptance.

The Source coverage panel reports observed acquired partitions per instrument
and the canonical storage footprint. This fixture builds an isolated state that
carries the genuine source observations and points at the real catalog, so the
panel is exercised against real coverage rather than a generated fixture.

It copies the observation database rather than re-deriving it, and symlinks the
catalog read-only in effect: nothing here writes to the acquired data. The
panel reports coverage for review; it does not select or admit anything.
"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "tests"), str(root / "tests" / "integration")]

DEFAULT_STATE = Path("/var/lib/hermes-factory")
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
parser.add_argument("--source", type=Path, default=DEFAULT_STATE)
args = parser.parse_args()

state = args.state
if state.exists():
    raise SystemExit("Use a new isolated state; never overwrite earlier browser evidence")
if not (args.source / "factory.sqlite").exists():
    raise SystemExit(f"source state not found: {args.source}")
if not (args.source / "catalog").is_dir():
    raise SystemExit(f"source catalog not found: {args.source / 'catalog'}")

state.mkdir(parents=True)
# The observation ledger is copied, never shared, so the smoke cannot mutate it.
shutil.copy2(args.source / "factory.sqlite", state / "factory.sqlite")
# The catalog is linked, not copied: it is read-only for this purpose and a
# copy would be gigabytes. Nothing in the coverage path writes to it.
os.symlink((args.source / "catalog").resolve(), state / "catalog")

subprocess.run(
    [sys.executable, "-m", "factory.cli", "--state", str(state), "create-admin"],
    cwd=root,
    check=True,
    stdout=subprocess.DEVNULL,
)

print(
    f"TEST_ONLY source-coverage state with the genuine observation ledger and "
    f"real catalog linked read-only; no period is selected or admitted"
)
