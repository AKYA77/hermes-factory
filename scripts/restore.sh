#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${1:?Usage: restore.sh BACKUP DESTINATION (must not exist, outside the backup)}"
: "${2:?Usage: restore.sh BACKUP DESTINATION (must not exist, outside the backup)}"
exec .venv/bin/python -m factory.operations.tools restore "$1" "$2"
