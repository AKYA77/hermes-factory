"""Fresh generated state for the independent qualified ranking panel.

Seeds one retained experiment with an evaluation record so the panel renders real
rows, then creates an operator token. Generated synthetic records only -- this is
descriptive ranking evidence, not qualification or promotion.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "tests"), str(root / "tests" / "integration")]

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--state", type=Path, required=True)
args = parser.parse_args()
state = args.state
if state.exists() and any(state.iterdir()):
    raise SystemExit("Use a new isolated state; never overwrite earlier browser evidence")

from factory.contracts import ExperimentContract  # noqa: E402
from test_annual_reporting import insert_evaluation  # noqa: E402
from test_improvement import parent_run  # noqa: E402

store, _protocol_hash, row = parent_run(state)
contract = ExperimentContract.model_validate_json(row["contract_json"])
result = json.loads(row["result_json"])
insert_evaluation(store, state, contract, result)

subprocess.run(
    [sys.executable, "-m", "factory.cli", "--state", str(state), "create-admin"],
    check=True,
)
print("GENERATED independent-ranking fixture: one retained evaluation, research paused")
