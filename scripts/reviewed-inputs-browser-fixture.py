"""DEV ONLY: generated admission-boundary browser fixture, NOT market evidence."""
from pathlib import Path
import sys
import subprocess
import json

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "tests" / "integration"))
from test_reviewed_inputs import prepared  # noqa: E402

state = root / ".local" / "reviewed-inputs-browser"
if state.exists():
    raise SystemExit("Use a new isolated state; never overwrite earlier browser evidence")
state.mkdir(parents=True)
registry, _, profile, _, admission, _ = prepared(state)
subprocess.run([sys.executable, "-m", "factory.cli", "--state", str(state), "create-admin"],
               cwd=root, check=True, stdout=subprocess.DEVNULL)
print(json.dumps({"state": str(state), "scope": "TEST_ONLY generated authorization fixture; NOT historical validation",
                  "records": len(registry.store.rows("SELECT * FROM reviewed_inputs"))}))
