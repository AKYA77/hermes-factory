"""Fresh reviewed-admission historical calibration plus unattempted prospective frame.

Development acceptance helper; imports the independent TEST_ONLY authorization
fixture. Not genuine market evidence.
"""

import argparse
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "tests"), str(root / "tests" / "integration")]
from test_historical_cohorts import prepared

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--state", type=Path, required=True)
args = parser.parse_args()
if args.state.exists() and any(args.state.iterdir()):
    parser.error("use fresh isolated state")
store, request, calibration, prospective, admission = prepared(args.state)
assert store.paused()
subprocess.run(
    [sys.executable, "-m", "factory.cli", "--state", str(args.state), "create-admin"],
    check=True,
)
print(
    "TEST_ONLY reviewed-admission historical calibration and later prospective frame; "
    "paused, no cohort frozen yet"
)
