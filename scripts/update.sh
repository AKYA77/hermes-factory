#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${1:?Usage: update.sh STAGED_RELEASE_DIRECTORY}"
# Current development checkpoint cannot deploy. A real release's own verifier must
# pass before an administrator can stage or activate it; no mutable remote script.
.venv/bin/python - "$1" <<'PY'
import sys
from factory.operations.releases import verify_release
verify_release(sys.argv[1])
raise SystemExit('NOT_READY: service quiescence and production migration rehearsal have not passed; activation refused.')
PY
