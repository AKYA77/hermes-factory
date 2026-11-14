"""Fresh generated state for the instrument-data-and-profile-status panel.

The panel renders the declared instrument registry, so the fixture only has to
create a clean state and an operator token; the eight synthetic profiles are
declared by ``factory.instruments``. Explicitly synthetic -- not broker metadata,
not verified Gold units, and no profile here is admitted for live use.
"""

import argparse
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--state", type=Path, required=True)
args = parser.parse_args()
if args.state.exists() and any(args.state.iterdir()):
    parser.error("use a fresh isolated state")

subprocess.run(
    [sys.executable, "-m", "factory.cli", "--state", str(args.state), "init"],
    check=True,
)
subprocess.run(
    [sys.executable, "-m", "factory.cli", "--state", str(args.state), "create-admin"],
    check=True,
)
print(
    "GENERATED instrument-status fixture: declared registry seeded, "
    "research paused, operator token created"
)
