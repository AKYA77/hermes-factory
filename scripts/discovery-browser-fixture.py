"""Fresh generated state for authenticated discovery browser acceptance."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

from factory.operations.fixtures import seed

parser = argparse.ArgumentParser()
parser.add_argument("--state", type=Path, required=True)
args = parser.parse_args()
if args.state.exists() and any(args.state.iterdir()):
    raise ValueError("Use fresh state; never overwrite retained browser evidence")
args.state.mkdir(parents=True, exist_ok=True)
payload = seed(args.state, 240)
(args.state / "profile.json").write_text(json.dumps(payload["profile"], indent=2) + "\n")
subprocess.run(
    [sys.executable, "-m", "factory.cli", "--state", str(args.state), "create-admin"], check=True
)
print(
    json.dumps(
        {
            "state": str(args.state),
            "fixture": "generated quotes and synthetic profile; research paused",
        }
    )
)
