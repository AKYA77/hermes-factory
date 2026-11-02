#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${1:?Usage: restore-test.sh BACKUP}"
exec .venv/bin/python -m factory.operations.tools restore-test "$1"
