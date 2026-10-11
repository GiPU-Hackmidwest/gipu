#!/usr/bin/env bash
# Freeze the Python image worker into a standalone folder the desktop app ships.
# Model weights are not included; the app downloads them on an explicit request.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/.cache/desktop-worker-build"
OUT="$ROOT/apps/web/src-tauri/resources/worker"
PYINSTALLER_VERSION="${PYINSTALLER_VERSION:-6.22.3}"

command -v uv >/dev/null || { echo "uv is required: https://docs.astral.sh/uv/" >&2; exit 1; }

# A separate environment keeps PyInstaller out of the worker's development venv.
uv venv --quiet --allow-existing --python 3.12 "$BUILD/venv"
uv pip install --quiet --python "$BUILD/venv/bin/python" \
  -r "$ROOT/workers/python/requirements.txt" "pyinstaller==$PYINSTALLER_VERSION"

# Diffusers and Transformers import pipelines lazily and check package versions at
# runtime, so their submodules and distribution metadata must be collected explicitly.
"$BUILD/venv/bin/pyinstaller" --noconfirm --clean --log-level WARN \
  --onedir --name pocketgrid-worker \
  --distpath "$BUILD/dist" --workpath "$BUILD/work" --specpath "$BUILD" \
  --collect-submodules diffusers --collect-data diffusers \
  --collect-submodules transformers --collect-data transformers \
  --recursive-copy-metadata diffusers --recursive-copy-metadata transformers \
  --copy-metadata torch --copy-metadata accelerate --copy-metadata safetensors \
  --exclude-module tkinter --exclude-module matplotlib --exclude-module IPython \
  --exclude-module pytest --exclude-module tensorboard \
  "$ROOT/workers/python/worker.py"

rm -rf "$OUT"
mkdir -p "$(dirname "$OUT")"
cp -R "$BUILD/dist/pocketgrid-worker" "$OUT"

# Fail the build here rather than in the app if the frozen worker cannot start.
"$OUT/pocketgrid-worker" --help >/dev/null
echo "Frozen worker: $OUT ($(du -sh "$OUT" | cut -f1))"
