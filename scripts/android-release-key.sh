#!/usr/bin/env bash
# Create the Android release signing key once, outside the repository, and print the
# commands that store it as GitHub Actions secrets. Keep both files backed up privately:
# Android only accepts updates signed with the same key.
set -euo pipefail
DIR="${1:-$HOME/.gipu-release}"
KEYSTORE="$DIR/gipu-release.jks"
SECRETS="$DIR/gipu-release.env"
ALIAS=gipu
[[ -e "$KEYSTORE" ]] && { echo "A key already exists at $KEYSTORE; refusing to replace it." >&2; exit 1; }
command -v keytool >/dev/null || { echo "keytool not found; install JDK 17 and put it on PATH." >&2; exit 1; }
mkdir -p "$DIR" && chmod 700 "$DIR"
PASSWORD="$(openssl rand -hex 24)"
keytool -genkeypair -keystore "$KEYSTORE" -alias "$ALIAS" -keyalg RSA -keysize 4096 -validity 10000 \
  -storepass "$PASSWORD" -keypass "$PASSWORD" -dname "CN=GiPU" >/dev/null
printf 'ANDROID_KEYSTORE_PASSWORD=%s\nANDROID_KEY_ALIAS=%s\nANDROID_KEY_PASSWORD=%s\n' "$PASSWORD" "$ALIAS" "$PASSWORD" > "$SECRETS"
chmod 600 "$KEYSTORE" "$SECRETS"
cat <<MSG
Created $KEYSTORE and $SECRETS (back both up privately; never commit them).
To store them as repository secrets, run from the repository:

  base64 -i "$KEYSTORE" | gh secret set ANDROID_KEYSTORE_BASE64
  gh secret set -f "$SECRETS"
MSG
