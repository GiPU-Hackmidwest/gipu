#!/usr/bin/env bash
# Prepare this laptop to generate images: Python environment plus the pinned
# Tiny-SD weights (about 1 GB, downloaded once into workers/python/.cache).
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/python.sh
"$PYTHON" -m venv workers/python/.venv
workers/python/.venv/bin/pip install -r workers/python/requirements-dev.txt
workers/python/.venv/bin/python workers/python/worker.py prepare
echo 'Ready. Run the worker as shown in README.md.'
