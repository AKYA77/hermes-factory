#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# The project venv is self-contained. An ambient PYTHONPATH (for example a
# host-wide Python 3.14 site-packages) shadows the venv interpreter and breaks
# imports such as pydantic_core, so clear it for every venv invocation.
unset PYTHONPATH
if [[ ${1:-} == --system ]]; then
  echo 'NOT_READY: system installation is gated on verified release, supported Ubuntu host and remaining acceptance tests.' >&2
  exit 2
fi
command -v uv >/dev/null
command -v npm >/dev/null
uv sync --frozen
npm --prefix apps/dashboard ci --ignore-scripts --no-audit --no-fund
npm --prefix apps/dashboard run check
npm --prefix apps/dashboard run build
.venv/bin/python -m factory.cli init
printf '%s\n' 'Development dependencies and dashboard installed; research remains paused on fresh state.' 'This is not a production release or completed C9 installer.'
