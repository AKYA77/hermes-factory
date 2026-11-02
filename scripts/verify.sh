#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p reports
.venv/bin/ruff check factory apps tests
.venv/bin/ruff format --check factory apps tests
.venv/bin/pytest -q --junitxml=reports/runtime/test-results.xml
npm --prefix apps/dashboard run check
npm --prefix apps/dashboard run build
