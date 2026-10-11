#!/usr/bin/env bash
# Build the desktop app with the frozen Python worker bundled as a resource.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB="$ROOT/apps/web"
WORKER="$WEB/src-tauri/resources/worker"

PROFILE=release
TARGET=""
BUNDLE=true
NEXT_TARGET=false
for ARG in "$@"; do
  if [[ "$NEXT_TARGET" = true ]]; then
    TARGET="$ARG"; NEXT_TARGET=false; continue
  fi
  case "$ARG" in
    --debug|-d) PROFILE=debug ;;
    --target|-t) NEXT_TARGET=true ;;
    --target=*|-t=*) TARGET="${ARG#*=}" ;;
    --no-bundle) BUNDLE=false ;;
    --) break ;;
  esac
done
[[ "$NEXT_TARGET" = false ]] || { echo "--target needs a target triple" >&2; exit 1; }
TARGET_DIR="${CARGO_TARGET_DIR:-$WEB/src-tauri/target}"
# Cargo resolves a relative target directory from its invocation directory.
[[ "$TARGET_DIR" = /* ]] || TARGET_DIR="$WEB/src-tauri/$TARGET_DIR"
APP="$TARGET_DIR${TARGET:+/$TARGET}/$PROFILE/bundle/macos/GiPU.app"

# Only post-process a bundle recreated by this invocation, never a stale release.
BUILD_STAMP="$(mktemp)"
trap 'rm -f "$BUILD_STAMP"' EXIT

"$ROOT/scripts/build-desktop-worker.sh"
touch "$BUILD_STAMP"
(cd "$WEB" && npx tauri build --config src-tauri/tauri.bundled-worker.conf.json "$@")

# Tauri copies resources by following symlinks, which duplicates the PyTorch
# libraries PyInstaller links into _internal (about 400 MB). Restore the links.
# The bundle is not code-signed yet, so replacing a resource folder is safe here;
# a signed build must re-sign after this step.
if [[ "$BUNDLE" = true && -d "$APP/Contents/Resources/worker" ]] \
  && [[ -n "$(find "$APP/Contents/Resources/worker" -prune -newer "$BUILD_STAMP" -print)" ]]; then
  rm -rf "$APP/Contents/Resources/worker"
  cp -R "$WORKER" "$APP/Contents/Resources/worker"
  echo "Desktop app: $APP ($(du -sh "$APP" | cut -f1))"
fi
