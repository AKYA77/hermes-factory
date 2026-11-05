#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/python -m factory.operations.benchmark "${1:-reports/benchmark-report.json}"
