#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# The project venv is self-contained. An ambient PYTHONPATH (for example a
# host-wide Python 3.14 site-packages) shadows the venv interpreter and breaks
# imports such as pydantic_core, so clear it for every venv invocation.
unset PYTHONPATH
mkdir -p reports
.venv/bin/ruff check factory apps tests
.venv/bin/ruff format --check factory apps tests
.venv/bin/pytest -q --junitxml=reports/runtime/test-results.xml
npm --prefix apps/dashboard run check
npm --prefix apps/dashboard run build
