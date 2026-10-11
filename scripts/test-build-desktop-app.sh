#!/usr/bin/env bash
# Exercise artifact selection and final bundle signing without Python or Tauri builds.
set -euo pipefail
SOURCE="$(cd "$(dirname "$0")" && pwd)/build-desktop-app.sh"
FIXTURE="$(mktemp -d)"
trap 'rm -rf "$FIXTURE"' EXIT
mkdir -p "$FIXTURE/scripts" "$FIXTURE/apps/web" "$FIXTURE/bin"
cp "$SOURCE" "$FIXTURE/scripts/build-desktop-app.sh"
if [[ "$(uname -s)" = Darwin && -x /usr/bin/codesign ]]; then
  export REAL_CODESIGN=/usr/bin/codesign
else
  export REAL_CODESIGN=''
  # Keep artifact-selection checks useful on non-Mac development hosts.
  printf '#!/usr/bin/env bash\nexit 0\n' > "$FIXTURE/bin/codesign"
  chmod +x "$FIXTURE/bin/codesign"
fi
cat > "$FIXTURE/scripts/build-desktop-worker.sh" <<'WORKER'
#!/usr/bin/env bash
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/apps/web/src-tauri/resources/worker"
echo frozen > "$ROOT/apps/web/src-tauri/resources/worker/probe"
if [[ -n "$REAL_CODESIGN" ]]; then
  cp /usr/bin/true "$ROOT/apps/web/src-tauri/resources/worker/pocketgrid-worker"
  "$REAL_CODESIGN" --force --sign - "$ROOT/apps/web/src-tauri/resources/worker/pocketgrid-worker" 2>/dev/null
fi
mkdir -p "$ROOT/apps/web/src-tauri/resources/worker/libraries"
echo library > "$ROOT/apps/web/src-tauri/resources/worker/libraries/probe"
ln -sf libraries/probe "$ROOT/apps/web/src-tauri/resources/worker/library-link"
WORKER
cat > "$FIXTURE/bin/npx" <<'TAURI'
#!/usr/bin/env bash
set -eu
if [[ "${SKIP_BUNDLE:-false}" != true ]]; then
  rm -rf "$EXPECTED_APP"
  mkdir -p "$EXPECTED_APP/Contents/Resources/worker"
  echo expanded > "$EXPECTED_APP/Contents/Resources/worker/probe"
  # Simulate Tauri's already signed app with expanded resource symlinks.
  if [[ -n "$REAL_CODESIGN" ]]; then
    mkdir -p "$EXPECTED_APP/Contents/MacOS"
    cp /usr/bin/true "$EXPECTED_APP/Contents/MacOS/fixture"
    cat > "$EXPECTED_APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>fixture</string>
<key>CFBundleIdentifier</key><string>dev.gipu.packaging-fixture</string>
<key>CFBundleName</key><string>GiPU</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleVersion</key><string>1</string>
</dict></plist>
PLIST
    "$REAL_CODESIGN" --force --sign - "$EXPECTED_APP" 2>/dev/null
    "$REAL_CODESIGN" --verify --deep --strict "$EXPECTED_APP" 2>/dev/null
  fi
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
  [[ -L "$expected/Contents/Resources/worker/library-link" ]]
  if [[ -n "$REAL_CODESIGN" ]]; then
    "$REAL_CODESIGN" --verify --deep --strict "$expected" 2>/dev/null
    "$REAL_CODESIGN" --verify --strict "$expected/Contents/Resources/worker/pocketgrid-worker" 2>/dev/null
  fi
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
if [[ -z "$REAL_CODESIGN" ]]; then
  echo 'Real macOS signing regression checks skipped: macOS codesign is unavailable.'
  exit 0
fi

# A genuine resource seal must reject changes after the wrapper succeeds.
unset CARGO_TARGET_DIR
APP="$WEB/src-tauri/target/release/bundle/macos/GiPU.app"
check "$APP"
echo tampered > "$APP/Contents/Resources/worker/probe"
if "$REAL_CODESIGN" --verify --deep --strict "$APP" >/dev/null 2>&1; then
  echo 'Tampering unexpectedly passed bundle verification.' >&2
  exit 1
fi

expect_failure() {
  local output="$FIXTURE/failure.log"
  if EXPECTED_APP="$APP" /bin/bash "$FIXTURE/scripts/build-desktop-app.sh" >"$output" 2>&1; then
    cat "$output" >&2
    echo 'The wrapper unexpectedly reported success.' >&2
    exit 1
  fi
  if grep -q 'Desktop app:' "$output"; then
    cat "$output" >&2
    echo 'The wrapper announced an app despite failed signing.' >&2
    exit 1
  fi
}

# A failed signer and a failed verification must both fail the build.
cat > "$FIXTURE/bin/codesign" <<'SIGNER'
#!/usr/bin/env bash
for argument in "$@"; do
  if [[ "$argument" = --sign && "${FAIL_SIGN:-false}" = true ]]; then exit 31; fi
  if [[ "$argument" = --verify && "${FAIL_VERIFY:-false}" = true ]]; then exit 32; fi
done
exec "$REAL_CODESIGN" "$@"
SIGNER
chmod +x "$FIXTURE/bin/codesign"
FAIL_SIGN=true expect_failure
FAIL_VERIFY=true expect_failure
rm "$FIXTURE/bin/codesign"

# Use a PATH with the wrapper's tools but no codesign to prove a missing signer
# also fails. The mock Tauri uses the absolute real signer to create its fixture.
mkdir "$FIXTURE/missing-signer-bin"
for tool in bash dirname mktemp find touch cp rm du cut mkdir cat uname chmod file xattr grep sed awk; do
  ln -s "$(command -v "$tool")" "$FIXTURE/missing-signer-bin/$tool"
done
ln -s "$FIXTURE/bin/npx" "$FIXTURE/missing-signer-bin/npx"
PATH="$FIXTURE/missing-signer-bin" expect_failure

# Explicit certificate signing may not be silently downgraded to ad-hoc.
APPLE_SIGNING_IDENTITY='Developer ID Application: fixture only' expect_failure
# Simulate a certificate-signed result supplied through Tauri configuration,
# independently of APPLE_SIGNING_IDENTITY. No real certificate is needed here.
cat > "$FIXTURE/bin/codesign" <<'AUTHORITY'
#!/usr/bin/env bash
for argument in "$@"; do
  case "$argument" in
    -d*|--display)
      echo 'Authority=Developer ID Application: fixture only' >&2
      exit 0
      ;;
  esac
done
exec "$REAL_CODESIGN" "$@"
AUTHORITY
chmod +x "$FIXTURE/bin/codesign"
expect_failure
echo 'Desktop build wrapper: resource tampering, failed signing, failed verification, missing signer and both identity guards passed.'
