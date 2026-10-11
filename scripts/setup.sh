#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/python.sh
"$PYTHON" -m venv .venv
.venv/bin/pip install -r services/coordinator/requirements.lock
npm --prefix apps/web ci
npm --prefix apps/web run build
echo 'Ready. Start coordinator: ./scripts/server.sh'
echo 'For image generation on this laptop: ./scripts/setup-worker.sh'
