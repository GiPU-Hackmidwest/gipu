#!/usr/bin/env bash
# Build the desktop app with the frozen Python worker bundled as a resource.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB="$ROOT/apps/web"
WORKER="$WEB/src-tauri/resources/worker"

"$ROOT/scripts/build-desktop-worker.sh"
(cd "$WEB" && npx tauri build --config src-tauri/tauri.bundled-worker.conf.json "$@")

# Tauri copies resources by following symlinks, which duplicates the PyTorch
# libraries PyInstaller links into _internal (about 400 MB). Restore the links.
# The bundle is not code-signed yet, so replacing a resource folder is safe here;
# a signed build must re-sign after this step.
APP="$WEB/src-tauri/target/release/bundle/macos/PocketGrid.app"
if [[ -d "$APP" ]]; then
  rm -rf "$APP/Contents/Resources/worker"
  cp -R "$WORKER" "$APP/Contents/Resources/worker"
  echo "Desktop app: $APP ($(du -sh "$APP" | cut -f1))"
fi
