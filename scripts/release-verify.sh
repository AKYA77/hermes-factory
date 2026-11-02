#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python - "$PWD" <<'PY'
import sys
from factory.operations.releases import verify_release
verify_release(sys.argv[1])
print('Release file hashes and manifest status verified. Check signatures and target-host evidence separately.')
PY
