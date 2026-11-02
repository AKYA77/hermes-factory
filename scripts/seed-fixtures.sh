#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python -m factory.operations.tools seed "${FACTORY_STATE:-.local}"
