#!/bin/sh
# Rebuild brand/png from the SVG masters (macOS only: renders with AppKit, keeping transparency).
set -e
cd "$(dirname "$0")/.."
BIN="${TMPDIR:-/tmp}/gipu-svg2png"
swiftc -O tools/svg2png.swift -o "$BIN"
"$BIN" gipu-app-icon.svg png/gipu-app-icon-1024.png 1024
"$BIN" gipu-app-icon-dark.svg png/gipu-app-icon-dark-1024.png 1024
"$BIN" gipu-app-icon-macos.svg png/gipu-app-icon-macos-1024.png 1024
"$BIN" gipu-app-icon.svg png/apple-touch-icon-180.png 180
"$BIN" gipu-favicon.svg png/gipu-favicon-32.png 32
"$BIN" gipu-mark.svg png/gipu-mark-512.png 512
"$BIN" gipu-wordmark.svg png/gipu-wordmark-1200.png 1200
"$BIN" gipu-wordmark-on-dark.svg png/gipu-wordmark-on-dark-1200.png 1200
for l in foreground background monochrome; do
  "$BIN" android/ic_launcher_$l.svg png/android-$l-1024.png 1024
done
