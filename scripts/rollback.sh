#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
printf '%s\n' 'NOT_READY: production rollback requires stopped services, a verified previous release and a rehearsed state restore. No production release exists yet.' >&2
exit 2
