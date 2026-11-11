"""DEV ONLY: generated state for the four record-browser dashboard panels.

Seeds one retained synthetic experiment, two retained evaluation records, a
child strategy spec (so lineage is non-empty) and one exploratory trial, so the
qualified-ranking, validation-evaluation, strategy-lineage and research-trial
panels render real responses. Explicitly synthetic test fixture; not market
evidence and not a qualification, ranking or promotion claim.
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

from factory.contracts import ExperimentContract, StrategySpec, Window  # noqa: E402
from test_annual_reporting import insert_evaluation  # noqa: E402
from test_improvement import parent_run  # noqa: E402

store, protocol_hash, row = parent_run(state)
contract = ExperimentContract.model_validate_json(row["contract_json"])
result = json.loads(row["result_json"])

# Two retained evaluation records over different windows, so the evaluation
# list has real rows and the detail route has a real identity to append.
insert_evaluation(store, state, contract, result)
second_window = Window(
    start_ns=contract.windows[0].end_ns + 60 * 10**9,
    end_ns=contract.windows[0].end_ns + 3600 * 10**9,
    role="report_only",
)
second = contract.model_copy(update={"windows": (second_window,)})
second_result = {
    "contract_hash": second.experiment_hash,
    "synthetic": False,
    "integrity_errors": [],
    "windows": [{"replay": result}],
}
insert_evaluation(store, state, second, second_result)

# A child strategy spec so the lineage route returns a real parent/child pair.
parent_id = row["strategy_id"]
parent_spec = StrategySpec.model_validate_json(
    store.rows("SELECT spec_json FROM strategy_specs WHERE strategy_id=?", (parent_id,))[0][
        "spec_json"
    ]
)
child = parent_spec.model_copy(update={"stop_ticks": parent_spec.stop_ticks + 30})
store.register_strategy(
    child,
    parent=parent_id,
    hypothesis=(
        "Widen the stop to test robustness; training diagnostic only, with no "
        "independent selection evidence."
    ),
)

subprocess.run(
    [sys.executable, "-m", "factory.cli", "--state", str(state), "create-admin"],
    cwd=root,
    check=True,
    stdout=subprocess.DEVNULL,
)
counts = {
    table: store.rows(f"SELECT count(*) n FROM {table}")[0]["n"]
    for table in (
        "experiments",
        "strategy_specs",
        "evaluation_results",
        "search_trials",
        "search_outcomes",
    )
}
print(
    json.dumps(
        {
            "state": str(state),
            "fixture": "generated synthetic quotes and profile; research records retained",
            "protocol_hash": protocol_hash,
            "parent_strategy_id": parent_id,
            "child_strategy_id": child.strategy_hash,
            "counts": counts,
        },
        indent=2,
    )
)
# Smoke scripts read qa.json for stable identifiers. Write it last, after the
# store is fully seeded, so a reader never sees a half-built fixture.
Path(state / "qa.json").write_text(
    json.dumps(
        {
            "protocol_hash": protocol_hash,
            "parent_strategy_id": parent_id,
            "child_strategy_id": child.strategy_hash,
            "counts": counts,
            "fixture": "generated synthetic; not market evidence",
        },
        indent=2,
    )
    + "\n"
)
