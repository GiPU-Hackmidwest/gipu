#!/bin/sh
# Regenerate the Tauri desktop, Windows, iOS and Android app icons and the web favicons from brand/ (macOS only).
# Run export_pngs.sh first if any SVG master changed.
set -e
BRAND="$(cd "$(dirname "$0")/.." && pwd)"
WEB="$BRAND/../apps/web"
ICONS="$WEB/src-tauri/icons"
RES="$WEB/src-tauri/gen/android/app/src/main/res"
BIN="${TMPDIR:-/tmp}/gipu-svg2png"
MAC="$(mktemp -d)"
swiftc -O "$BRAND/tools/svg2png.swift" -o "$BIN"

cd "$WEB"
# Full-bleed square for iOS and Windows tiles; separate layers for the Android adaptive icon.
npx tauri icon "$BRAND/tauri-icon.json"
# macOS draws no mask, so the desktop set uses the rounded tile with transparent margin.
npx tauri icon "$BRAND/png/gipu-app-icon-macos-1024.png" -o "$MAC"
for f in icon.icns icon.ico icon.png 32x32.png 64x64.png 128x128.png 128x128@2x.png; do
  cp "$MAC/$f" "$ICONS/$f"
done
rm -rf "$MAC"
# Android 7 legacy launcher icons need their own padding; tauri icon crops the adaptive layers too tightly.
for p in mdpi:48 hdpi:72 xhdpi:96 xxhdpi:144 xxxhdpi:192; do
  "$BIN" "$BRAND/android/ic_launcher_legacy.svg" "$RES/mipmap-${p%:*}/ic_launcher.png" "${p#*:}"
  "$BIN" "$BRAND/android/ic_launcher_round.svg" "$RES/mipmap-${p%:*}/ic_launcher_round.png" "${p#*:}"
done
# Web favicons, served from apps/web/public.
cp "$BRAND/gipu-favicon.svg" "$WEB/public/favicon.svg"
cp "$BRAND/png/gipu-favicon-32.png" "$WEB/public/favicon-32.png"
cp "$BRAND/png/apple-touch-icon-180.png" "$WEB/public/apple-touch-icon.png"
