#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${1:?Usage: backup.sh DESTINATION (must not exist, outside state root)}"
exec .venv/bin/python -m factory.operations.tools backup "${FACTORY_STATE:-.local}" "$1"
