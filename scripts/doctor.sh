#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# The project venv is self-contained. An ambient PYTHONPATH (for example a
# host-wide Python 3.14 site-packages) shadows the venv interpreter and breaks
# imports such as pydantic_core, so clear it for every venv invocation.
unset PYTHONPATH
exec .venv/bin/python -m factory.cli doctor
