#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${1:?Usage: restore-rehearsal.sh BACKUP WORKDIR (must not exist, outside the backup)}"
: "${2:?Usage: restore-rehearsal.sh BACKUP WORKDIR (must not exist, outside the backup)}"
exec .venv/bin/python -m factory.operations.tools restore-rehearsal "$1" "$2"
