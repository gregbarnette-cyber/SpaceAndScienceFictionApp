"""One-off generator: produces stars_within_15ly.html, a 2D X-Y grid plot of
every star in the star_systems DB table within 15 ly of Sol. Each star is
labeled with its name and Z-axis coordinate in parentheses."""

import html
import os
from core.calculators import compute_stars_within_distance_of_sol
from core.viz import _SPECTRAL_COLORS

LIMIT_LY = 15.0
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stars_within_15ly.html")

# SVG canvas in CSS pixels. The plotting area is a square inside the canvas.
CANVAS = 1400
MARGIN = 80
PLOT = CANVAS - 2 * MARGIN          # inner square side
HALF = LIMIT_LY                     # axis range: -15..+15 ly
SCALE = PLOT / (2 * HALF)           # px per ly


def to_px(ly_x, ly_y):
    """Convert (x_ly, y_ly) → (px_x, px_y) inside the canvas (SVG y grows downward)."""
    cx = MARGIN + (ly_x + HALF) * SCALE
    cy = MARGIN + (HALF - ly_y) * SCALE
    return cx, cy


def short_name(name):
    # Trim common prefixes that clutter labels.
    for prefix in ("NAME ", "* ", "V* "):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return name


def spectral_color(sp):
    return _SPECTRAL_COLORS.get(sp[:1].upper(), "#AAAAAA") if sp else "#AAAAAA"


def build_svg(stars):
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CANVAS} {CANVAS}" '
             f'width="{CANVAS}" height="{CANVAS}" style="background:#0b1020;font-family:Segoe UI, Arial, sans-serif">']

    # Grid lines (every 1 ly, with major emphasis every 5 ly).
    for i in range(-int(HALF), int(HALF) + 1):
        x_px = MARGIN + (i + HALF) * SCALE
        y_px = MARGIN + (HALF - i) * SCALE
        major = (i % 5 == 0)
        stroke = "#2a3868" if major else "#1a2448"
        width = 1.2 if major else 0.6
        parts.append(f'<line x1="{x_px}" y1="{MARGIN}" x2="{x_px}" y2="{CANVAS - MARGIN}" '
                     f'stroke="{stroke}" stroke-width="{width}"/>')
        parts.append(f'<line x1="{MARGIN}" y1="{y_px}" x2="{CANVAS - MARGIN}" y2="{y_px}" '
                     f'stroke="{stroke}" stroke-width="{width}"/>')

    # Axes through origin.
    ox, oy = to_px(0, 0)
    parts.append(f'<line x1="{MARGIN}" y1="{oy}" x2="{CANVAS - MARGIN}" y2="{oy}" '
                 f'stroke="#4a6a99" stroke-width="1.8"/>')
    parts.append(f'<line x1="{ox}" y1="{MARGIN}" x2="{ox}" y2="{CANVAS - MARGIN}" '
                 f'stroke="#4a6a99" stroke-width="1.8"/>')

    # Axis labels every 5 ly.
    for i in range(-int(HALF), int(HALF) + 1, 5):
        if i == 0:
            continue
        x_px, _ = to_px(i, 0)
        _, y_px = to_px(0, i)
        parts.append(f'<text x="{x_px}" y="{oy + 16}" fill="#8aa4d4" font-size="12" '
                     f'text-anchor="middle">{i:+d}</text>')
        parts.append(f'<text x="{ox - 8}" y="{y_px + 4}" fill="#8aa4d4" font-size="12" '
                     f'text-anchor="end">{i:+d}</text>')

    # Axis titles.
    parts.append(f'<text x="{CANVAS - MARGIN}" y="{oy - 8}" fill="#cfd8ec" font-size="14" '
                 f'text-anchor="end">X (ly) →</text>')
    parts.append(f'<text x="{ox + 8}" y="{MARGIN + 14}" fill="#cfd8ec" font-size="14">↑ Y (ly)</text>')

    # Title.
    parts.append(f'<text x="{CANVAS / 2}" y="{MARGIN / 2 + 6}" fill="#ffffff" font-size="20" '
                 f'font-weight="600" text-anchor="middle">Star Systems within {LIMIT_LY:g} Light Years of Sol — '
                 f'X–Y projection (label Z in parentheses)</text>')

    # Distance rings at 5, 10, 15 ly.
    for r_ly in (5, 10, 15):
        parts.append(f'<circle cx="{ox}" cy="{oy}" r="{r_ly * SCALE}" '
                     f'fill="none" stroke="#3a5a8a" stroke-dasharray="4 6" stroke-width="0.8"/>')
        parts.append(f'<text x="{ox + r_ly * SCALE - 4}" y="{oy - 4}" fill="#6f8fc4" '
                     f'font-size="11" text-anchor="end">{r_ly} ly</text>')

    # Sol marker (gold star at origin).
    parts.append(f'<circle cx="{ox}" cy="{oy}" r="6" fill="#FFD700" stroke="#fff8a0" stroke-width="1.5"/>')
    parts.append(f'<text x="{ox + 9}" y="{oy - 9}" fill="#FFD700" font-size="13" '
                 f'font-weight="600">Sol (Z=0.000)</text>')

    # Plot each star + label.
    # Cluster Alpha Centauri-class points by jittering labels slightly to reduce overlap.
    placed = []  # list of (cx, cy) already placed labels for collision nudge
    for s in stars:
        if s["x"] is None or s["y"] is None:
            continue
        if abs(s["x"]) > HALF or abs(s["y"]) > HALF:
            # Inside 15 ly sphere but outside the X-Y projection square — skip.
            continue
        cx, cy = to_px(s["x"], s["y"])
        color = spectral_color(s["Spectral Type"])
        name = html.escape(short_name(s["Star Name"]))
        z = s["z"]
        label = f"{name} (Z={z:+.3f})"
        tooltip = (f'{name} — Sp: {html.escape(s["Spectral Type"] or "—")} — '
                   f'd: {s["Light Years"]:.3f} ly — '
                   f'x: {s["x"]:+.3f}, y: {s["y"]:+.3f}, z: {z:+.3f}')

        parts.append(f'<circle cx="{cx}" cy="{cy}" r="4.5" fill="{color}" stroke="#000" '
                     f'stroke-width="0.6"><title>{html.escape(tooltip)}</title></circle>')

        # Label placement: default to upper-right of the dot, nudge if close to a prior label.
        lx, ly_ = cx + 7, cy - 7
        for px, py in placed:
            if abs(lx - px) < 90 and abs(ly_ - py) < 12:
                ly_ += 13  # push down
        placed.append((lx, ly_))

        parts.append(f'<text x="{lx}" y="{ly_}" fill="#e6ecf7" font-size="11" '
                     f'style="paint-order:stroke;stroke:#0b1020;stroke-width:2.5;stroke-linejoin:round">'
                     f'{label}</text>')

    parts.append('</svg>')
    return "\n".join(parts)


def build_legend():
    items = []
    for sp_letter in ("O", "B", "A", "F", "G", "K", "M", "L", "T", "D"):
        c = _SPECTRAL_COLORS[sp_letter]
        items.append(
            f'<span style="display:inline-flex;align-items:center;gap:6px;margin-right:14px">'
            f'<span style="width:12px;height:12px;border-radius:50%;background:{c};'
            f'border:1px solid #000;display:inline-block"></span>{sp_letter}</span>'
        )
    return ('<div style="margin:10px 0 4px;color:#cfd8ec;font:13px Segoe UI,Arial">'
            'Spectral class: ' + "".join(items) + '</div>')


def main():
    result = compute_stars_within_distance_of_sol(LIMIT_LY)
    if "error" in result:
        raise SystemExit(result["error"])

    stars = result["stars"]
    svg = build_svg(stars)
    legend = build_legend()

    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Stars within {LIMIT_LY:g} ly of Sol — X–Y projection</title>
<style>
  body {{ background:#070b18; color:#e6ecf7; font:14px Segoe UI, Arial, sans-serif;
         margin:18px; }}
  .meta {{ color:#9fb0d0; margin-bottom:8px; }}
  .wrap {{ display:inline-block; background:#0b1020; padding:10px; border:1px solid #1a2448;
           border-radius:6px; }}
</style>
</head>
<body>
  <h1 style="margin:0 0 6px;font-size:20px">Star Systems within {LIMIT_LY:g} Light Years of Sol</h1>
  <div class="meta">2D grid of the X-Y plane (looking down the Z axis from galactic north).
    Each label shows the star name with its Z coordinate (in ly) in parentheses.
    {result["count"]} stars in DB ≤ {LIMIT_LY:g} ly; only those whose |X| and |Y| are ≤ {LIMIT_LY:g} ly are shown on this projection.</div>
  {legend}
  <div class="wrap">{svg}</div>
</body>
</html>
"""

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"Wrote {OUT_PATH} ({len(stars)} stars within {LIMIT_LY:g} ly)")


if __name__ == "__main__":
    main()
