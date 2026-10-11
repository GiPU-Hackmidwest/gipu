#!/usr/bin/env bash
# Create a local Android signing key. Never upload or commit these files.
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEY_DIR="${1:-$HOME/.gipu-release}"
PROPERTIES="$ROOT/apps/web/src-tauri/gen/android/keystore.properties"
[[ -e "$KEY_DIR/gipu-release.jks" || -e "$KEY_DIR/keystore.properties" || -e "$PROPERTIES" ]] && {
  echo 'Signing files already exist; refusing to replace them.' >&2; exit 1;
}
command -v keytool >/dev/null || { echo 'Install JDK 17 and put keytool on PATH.' >&2; exit 1; }
command -v python3 >/dev/null || { echo 'Python 3 is required.' >&2; exit 1; }
mkdir -p "$KEY_DIR"
KEY_DIR="$(cd "$KEY_DIR" && pwd)"
chmod 700 "$KEY_DIR"
export GIPU_SIGNING_PASSWORD="$(openssl rand -hex 24)"
keytool -genkeypair -keystore "$KEY_DIR/gipu-release.jks" -alias gipu -keyalg RSA -keysize 4096 -validity 10000 \
  -storepass:env GIPU_SIGNING_PASSWORD -keypass:env GIPU_SIGNING_PASSWORD -dname 'CN=GiPU' >/dev/null
python3 - "$KEY_DIR" "$PROPERTIES" <<'PY'
import os, pathlib, sys
folder = pathlib.Path(sys.argv[1])
def escape(value):
    return value.replace('\\', '\\\\').replace(':', '\\:').replace(' ', '\\ ').replace('=', '\\=').replace('\n', '\\n').replace('\r', '\\r')
password = os.environ['GIPU_SIGNING_PASSWORD']
text = f'storeFile={escape(str(folder / "gipu-release.jks"))}\nstorePassword={password}\nkeyAlias=gipu\nkeyPassword={password}\n'
for path in (folder / 'keystore.properties', pathlib.Path(sys.argv[2])):
    with path.open('x') as handle:
        handle.write(text)
    path.chmod(0o600)
(folder / 'gipu-release.jks').chmod(0o600)
PY
unset GIPU_SIGNING_PASSWORD
printf 'Local signing configured. Back up %s privately; never commit it.\n' "$KEY_DIR"
