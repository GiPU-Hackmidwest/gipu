"""Generate GiPU brand SVGs from one set of geometry constants."""
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent
INK, LIGHT, ORANGE = "#1C1E21", "#F1F3F6", "#FF5A09"
CANVAS, DARK = "#F4F6F8", "#1C1E21"

# All glyphs live on a 56-unit cap height, stroke 10, round caps.
MARK_ARC = "M45.619 13.216A23 23 0 1 0 51 28"
MARK_DOT = (34, 28, 7.5)
BOLD_ARC = "M44.087 14.501A21 21 0 1 0 49 28"
BOLD_DOT = (31, 28, 8.5)
WORD = ("M45.619 13.216A23 23 0 1 0 51 28H38"   # G
        "M69 25V51"                             # i stem
        "M88 51V5H100A12.5 12.5 0 0 1 100 30H88"  # P
        "M131.5 5V36A15 15 0 0 0 161.5 36V5")   # U
WORD_DOT = (69, 6.5, 6.5)


def stroke(d, color, width):
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


def dot(c, color):
    x, y, r = c
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>'


def mark(color, dot_color=ORANGE, bold=False):
    if bold:
        return stroke(BOLD_ARC, color, 14) + dot(BOLD_DOT, dot_color)
    return stroke(MARK_ARC, color, 10) + dot(MARK_DOT, dot_color)


def placed(inner, size, box):
    """Center the 56-unit mark at `size` units inside a square `box`."""
    s = size / 56
    t = (box - size) / 2
    return f'<g transform="translate({t:g} {t:g}) scale({s:.4f})">{inner}</g>'


def svg(name, view, body, title="GiPU"):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    w, h = view
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img"><title>{title}</title>{body}</svg>\n')


svg("gipu-mark.svg", (56, 56), mark(INK))
svg("gipu-mark-on-dark.svg", (56, 56), mark(LIGHT))
svg("gipu-mark-small.svg", (56, 56), mark(INK, bold=True))
svg("gipu-wordmark.svg", (166.5, 56), stroke(WORD, INK, 10) + dot(WORD_DOT, ORANGE))
svg("gipu-wordmark-on-dark.svg", (166.5, 56), stroke(WORD, LIGHT, 10) + dot(WORD_DOT, ORANGE))

# Full-bleed squares: iOS, Android legacy, Windows and the `tauri icon` source.
svg("gipu-app-icon.svg", (1024, 1024),
    f'<rect width="1024" height="1024" fill="{CANVAS}"/>' + placed(mark(INK), 512, 1024))
svg("gipu-app-icon-dark.svg", (1024, 1024),
    f'<rect width="1024" height="1024" fill="{DARK}"/>' + placed(mark(LIGHT), 512, 1024))
# macOS draws no mask: ship the rounded tile on Apple's 824px grid.
svg("gipu-app-icon-macos.svg", (1024, 1024),
    f'<rect x="100" y="100" width="824" height="824" rx="185" fill="{CANVAS}"/>'
    + placed(mark(INK), 428, 1024))
svg("gipu-favicon.svg", (32, 32),
    f'<rect width="32" height="32" rx="7" fill="{CANVAS}"/>' + placed(mark(INK, bold=True), 19, 32))

# Android adaptive icon layers on the 108dp canvas; keep the mark inside the 66dp safe zone.
svg("android/ic_launcher_foreground.svg", (108, 108), placed(mark(INK), 46, 108))
svg("android/ic_launcher_background.svg", (108, 108), f'<rect width="108" height="108" fill="{CANVAS}"/>')
svg("android/ic_launcher_monochrome.svg", (108, 108), placed(mark(INK, INK), 46, 108))
# Status-bar notification icon: white silhouette, bold weight for 24dp.
svg("android/ic_stat_gipu.svg", (24, 24), placed(mark("#FFFFFF", "#FFFFFF", bold=True), 20, 24))
# Legacy launcher icons (Android 7, before adaptive icons) on the 48dp canvas.
svg("android/ic_launcher_legacy.svg", (48, 48),
    f'<rect x="2" y="2" width="44" height="44" rx="9" fill="{CANVAS}"/>' + placed(mark(INK), 24, 48))
svg("android/ic_launcher_round.svg", (48, 48),
    f'<circle cx="24" cy="24" r="22" fill="{CANVAS}"/>' + placed(mark(INK), 22, 48))
