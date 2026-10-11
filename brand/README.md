# GiPU brand

The product name is **GiPU**: capital G, P and U with a lowercase i. Use GiPU in user-visible copy and app names. Bundle identifiers, environment variables and source paths stay unchanged, as agreed in `AGENTS.md`.

## Mark

The icon is a geometric G whose crossbar is an orange **live dot**. The same dot sits on the i in the wordmark. The dot appears once per lockup and is never recoloured. It is part of the static brand; sharing state is shown separately by the app controls.

| File | Use |
| --- | --- |
| `gipu-wordmark.svg`, `gipu-wordmark-on-dark.svg` | Name lockups: README, website, splash |
| `gipu-mark.svg`, `gipu-mark-on-dark.svg` | Standalone mark, 24px and larger |
| `gipu-mark-small.svg` | Heavier stroke and larger dot for sizes below 24px |
| `gipu-app-icon.svg`, `gipu-app-icon-dark.svg` | Full-bleed 1024 square: iOS, Windows, `tauri icon` source |
| `gipu-app-icon-macos.svg` | macOS tile on Apple's 824px grid with transparent margin |
| `gipu-favicon.svg` | Browser tab (uses the small mark) |
| `android/ic_launcher_{foreground,background,monochrome}.svg` | Adaptive icon layers on the 108dp canvas; mark stays inside the 66dp safe zone |
| `android/ic_launcher_legacy.svg`, `android/ic_launcher_round.svg` | Android 7 launcher icons on the 48dp canvas |
| `android/ic_stat_gipu.svg` | White 24dp status-bar notification icon |
| `png/` | Rendered PNGs of the above |
| `tauri-icon.json` | `tauri icon` manifest: full-bleed default plus Android adaptive layers |

## Colours

| Token | Hex |
| --- | --- |
| Live orange | `#FF5A09` |
| Ink | `#1C1E21` |
| Ink on dark | `#F1F3F6` |
| Light tile | `#F4F6F8` |

Brand orange stays `#FF5A09`. The accessible action colour is the deeper `#C34400` with white labels; see [native UI design](../docs/native-ui-design.md).

## Usage

- Keep clear space around the mark of at least the dot's diameter.
- Use the small mark below 24px; the regular dot disappears at 16px.
- Do not add gradients, shadows or outlines, rotate the mark, or set the wordmark in a typeface. The letters are drawn, not typed.
- Monochrome contexts (Android themed icons, notifications) render the dot in the same colour as the G.

## Editing

All glyphs share one 56-unit grid with a stroke of 10 and round caps. Change geometry in `tools/generate_svgs.py`, then regenerate:

```sh
python3 brand/tools/generate_svgs.py
brand/tools/export_pngs.sh   # macOS; renders PNGs with AppKit to keep transparency
```

## App icons

`apps/web/src-tauri/icons/` and the Android launcher icons in `apps/web/src-tauri/gen/android/app/src/main/res/` are generated from this folder. Do not edit them by hand. After exporting PNGs, run this from a checkout with `apps/web/node_modules` installed:

```sh
brand/tools/update_app_icons.sh
```

It runs `tauri icon` with `tauri-icon.json` (iOS, Windows tiles and the Android adaptive and monochrome layers). It then replaces the desktop set (`icon.icns`, `icon.ico`, `icon.png` and the sized PNGs) with the macOS tile, since macOS applies no mask, and draws the Android 7 legacy icons with their own padding. Re-running it gives identical images; `icon.icns` may still differ byte-for-byte because of how it is packed.

The native iOS app in `apps/ios` has no icon set yet; it is not generated here.
