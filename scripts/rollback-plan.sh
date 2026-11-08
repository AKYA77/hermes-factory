#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${1:?Usage: rollback-plan.sh BACKUP TARGET (plan only; never switches live state)}"
: "${2:?Usage: rollback-plan.sh BACKUP TARGET (plan only; never switches live state)}"
exec .venv/bin/python -m factory.operations.tools rollback-plan "$1" "$2" \
  --services-stopped --previous-release-verified
