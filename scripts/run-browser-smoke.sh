#!/usr/bin/env bash
# Run a dashboard browser-acceptance smoke script end to end.
#
# The smoke scripts drive a real Chromium against the served dashboard, but the
# dashboard's `serve` command does not start a coordinator, so any workflow that
# needs a job to actually run (freeze a cohort, native audit, export) silently
# never completes. This wrapper starts both processes against one isolated
# TEST_ONLY state, waits for the API, runs the smoke script, and tears everything
# down.
#
# Usage: scripts/run-browser-smoke.sh <fixture.py> <smoke.cjs> [state-dir]
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

# The project venv is self-contained. An ambient PYTHONPATH (for example a
# host-wide Python 3.14 site-packages) shadows the venv interpreter and breaks
# imports such as pydantic_core, so clear it for every venv invocation.
unset PYTHONPATH

fixture="${1:?fixture script required}"
smoke="${2:?smoke script required}"
state="${3:-/var/lib/browser-smoke-state}"
port="${FACTORY_BROWSER_PORT:-8102}"

if [ -d "$state" ] && [ -n "$(ls -A "$state" 2>/dev/null)" ]; then
  echo "refusing non-empty state: $state" >&2
  exit 2
fi
# Deliberately do not create the state directory: some fixtures require it to be
# absent entirely ("new isolated state required") while others create it
# themselves. The fixture owns that decision.

cleanup() {
  [ -n "${coordinator_pid:-}" ] && kill "$coordinator_pid" 2>/dev/null || true
  [ -n "${server_pid:-}" ] && kill "$server_pid" 2>/dev/null || true
}
trap cleanup EXIT

export PATH="/root/.hermes/tools/node-26.7.0-linux-x64/bin:$PATH"
export NODE_PATH="$root/apps/dashboard/node_modules"

# `serve` serves the static build, so a source change is invisible until the
# dashboard is rebuilt. Without this the smokes silently test the previous
# build, which is how a new panel can appear to do nothing.
if [ "${FACTORY_BROWSER_SKIP_BUILD:-}" != "1" ]; then
  (cd "$root/apps/dashboard" && npm run build >/dev/null) || {
    echo "dashboard build failed" >&2
    exit 1
  }
fi

env -u PYTHONPATH .venv/bin/python "scripts/$fixture" --state "$state"

env -u PYTHONPATH .venv/bin/python -m factory.cli --state "$state" serve --port "$port" &
server_pid=$!
env -u PYTHONPATH .venv/bin/python -m factory.cli --state "$state" coordinator &
coordinator_pid=$!

for _ in $(seq 1 60); do
  if curl -sf -o /dev/null "http://127.0.0.1:$port/"; then break; fi
  sleep 0.5
done
curl -sf -o /dev/null "http://127.0.0.1:$port/" || {
  echo "dashboard did not come up on port $port" >&2
  exit 1
}

FACTORY_BROWSER_STATE="$state" FACTORY_BROWSER_URL="http://127.0.0.1:$port" \
  node "scripts/$smoke"
