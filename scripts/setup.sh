#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${POCKETGRID_PYTHON:-python3.11}"
"$PYTHON" -m venv .venv
.venv/bin/pip install -r services/coordinator/requirements.lock
npm --prefix apps/web ci
npm --prefix apps/web run build
echo 'Ready. Start coordinator: ./scripts/server.sh'
echo 'For image generation, follow workers/python/README.md on each contributing laptop.'
