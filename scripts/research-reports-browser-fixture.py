"""DEV ONLY: generated state for the Research reports browser acceptance.

Creates a fresh isolated state with a small retained research history so the
descriptive report actions have something to aggregate. Not market evidence.
"""

import argparse
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "tests"), str(root / "tests" / "integration")]

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--state", type=Path, required=True)
args = parser.parse_args()
state = args.state
if state.exists():
    raise SystemExit("Use a new isolated state; never overwrite earlier browser evidence")

# The report actions aggregate retained evidence, so seed a small history rather
# than an empty store. Imported late so the test helpers can add their own paths.
from test_historical_cohorts import prepared  # noqa: E402

store, _request, _calibration, _prospective, _admission = prepared(state)
registry = type("R", (), {"store": store})()
subprocess.run(
    [sys.executable, "-m", "factory.cli", "--state", str(state), "create-admin"],
    cwd=root,
    check=True,
    stdout=subprocess.DEVNULL,
)
print(
    f"TEST_ONLY research-report state with "
    f"{len(registry.store.rows('SELECT * FROM research_input_uses'))} retained input "
    "use(s); no strategy is qualified, ranked or promoted"
)
