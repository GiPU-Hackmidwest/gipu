#!/usr/bin/env bash
# Exercise wrapper artifact selection without freezing Python or building Tauri.
set -euo pipefail
SOURCE="$(cd "$(dirname "$0")" && pwd)/build-desktop-app.sh"
FIXTURE="$(mktemp -d)"
trap 'rm -rf "$FIXTURE"' EXIT
mkdir -p "$FIXTURE/scripts" "$FIXTURE/apps/web" "$FIXTURE/bin"
cp "$SOURCE" "$FIXTURE/scripts/build-desktop-app.sh"
cat > "$FIXTURE/scripts/build-desktop-worker.sh" <<'WORKER'
#!/usr/bin/env bash
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/apps/web/src-tauri/resources/worker"
echo frozen > "$ROOT/apps/web/src-tauri/resources/worker/probe"
WORKER
cat > "$FIXTURE/bin/npx" <<'TAURI'
#!/usr/bin/env bash
set -eu
if [[ "${SKIP_BUNDLE:-false}" != true ]]; then
  mkdir -p "$EXPECTED_APP/Contents/Resources/worker"
  echo expanded > "$EXPECTED_APP/Contents/Resources/worker/probe"
  touch "$EXPECTED_APP/Contents/Resources/worker"
fi
TAURI
chmod +x "$FIXTURE/scripts/build-desktop-worker.sh" "$FIXTURE/bin/npx"
export PATH="$FIXTURE/bin:$PATH"
WEB="$FIXTURE/apps/web"
check() {
  local expected="$1"; shift
  EXPECTED_APP="$expected" bash "$FIXTURE/scripts/build-desktop-app.sh" "$@" >/dev/null
  [[ "$(cat "$expected/Contents/Resources/worker/probe")" = frozen ]]
}
unset CARGO_TARGET_DIR
check "$WEB/src-tauri/target/release/bundle/macos/GiPU.app"
# A later debug build must leave an existing release artifact alone.
echo stale > "$WEB/src-tauri/target/release/bundle/macos/GiPU.app/Contents/Resources/worker/probe"
check "$WEB/src-tauri/target/debug/bundle/macos/GiPU.app" --debug
[[ "$(cat "$WEB/src-tauri/target/release/bundle/macos/GiPU.app/Contents/Resources/worker/probe")" = stale ]]
export CARGO_TARGET_DIR="$FIXTURE/custom target"
check "$CARGO_TARGET_DIR/aarch64-apple-darwin/debug/bundle/macos/GiPU.app" -d --target aarch64-apple-darwin
check "$CARGO_TARGET_DIR/x86_64-apple-darwin/release/bundle/macos/GiPU.app" --target=x86_64-apple-darwin
export CARGO_TARGET_DIR=relative-target
check "$WEB/src-tauri/relative-target/aarch64-apple-darwin/release/bundle/macos/GiPU.app" -t aarch64-apple-darwin
# No-bundle and successful invocations that did not create this app cannot mutate it.
APP="$WEB/src-tauri/relative-target/aarch64-apple-darwin/release/bundle/macos/GiPU.app"
echo stale > "$APP/Contents/Resources/worker/probe"
SKIP_BUNDLE=true EXPECTED_APP="$APP" bash "$FIXTURE/scripts/build-desktop-app.sh" --target=aarch64-apple-darwin --no-bundle >/dev/null
[[ "$(cat "$APP/Contents/Resources/worker/probe")" = stale ]]
SKIP_BUNDLE=true EXPECTED_APP="$APP" bash "$FIXTURE/scripts/build-desktop-app.sh" --target=aarch64-apple-darwin >/dev/null
[[ "$(cat "$APP/Contents/Resources/worker/probe")" = stale ]]
echo 'Desktop build wrapper: 7 artifact-selection checks passed.'
