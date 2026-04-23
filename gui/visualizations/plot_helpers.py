# gui/visualizations/plot_helpers.py — Shared matplotlib rendering helpers (Phase E).
#
# Each function accepts prepared data dicts (from core.viz) and returns
# (FigureCanvas, NavToolbar) ready to be inserted into any Qt layout.

import math

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavToolbar
    from matplotlib.figure import Figure
    from matplotlib.patches import Circle
    import matplotlib.patches as mpatches
    _MPL_OK = True
except ImportError:
    _MPL_OK = False

_SPACE_BG  = "#03030f"
_LABEL_CLR = "#cccccc"
_GRID_CLR  = "#1a1a3a"


def mpl_available() -> bool:
    return _MPL_OK


# ── HZ Diagram ─────────────────────────────────────────────────────────────────

def make_hz_canvas(parent, zones: list, max_au: float, title: str = "",
                   eeid_au: float = None):
    """Concentric ring HZ diagram.

    zones: list of dicts {label, outer, color} ordered inner→outer.
    eeid_au: if given, draw a dashed white circle at this AU (Earth Equiv. Insolation).
    Returns (canvas, toolbar).
    """
    fig = Figure(figsize=(6, 6), facecolor=_SPACE_BG)
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111, aspect="equal", facecolor=_SPACE_BG)

    # Paint zones from outside-in (layering trick)
    for zone in reversed(zones):
        ax.add_patch(Circle((0, 0), zone["outer"],
                            color=zone["color"], alpha=0.55, zorder=2))

    # Boundary dashed lines + AU labels
    for zone in zones:
        ax.add_patch(Circle((0, 0), zone["outer"],
                            fill=False, edgecolor="white",
                            linewidth=0.8, linestyle="--", alpha=0.45, zorder=3))
        lx = zone["outer"] * 0.717
        ly_ = zone["outer"] * 0.717
        ax.text(lx, ly_, f"{zone['outer']:.3f} AU",
                color="white", fontsize=6.5, ha="left", va="bottom",
                alpha=0.85, zorder=4)

    # Earth Equivalent Insolation Distance marker
    if eeid_au and eeid_au > 0:
        ax.add_patch(Circle((0, 0), eeid_au,
                            fill=False, edgecolor="#00FFAA",
                            linewidth=1.5, linestyle="-", alpha=0.85, zorder=5))
        ax.text(eeid_au * 0.717, -eeid_au * 0.717,
                f"EEID\n{eeid_au:.3f} AU",
                color="#00FFAA", fontsize=6.5, ha="left", va="top",
                alpha=0.9, zorder=6)

    # Star
    star_r = max_au * 0.018
    ax.add_patch(Circle((0, 0), star_r, color="#FFEE55", zorder=10))

    _style_ax(ax, max_au, title)

    handles = [mpatches.Patch(facecolor=z["color"], edgecolor="white",
                               alpha=0.7, label=z["label"]) for z in zones]
    handles.append(mpatches.Patch(facecolor=_SPACE_BG, edgecolor="white",
                                   alpha=0.7, label="Too Cold  (> Early Mars)"))
    if eeid_au and eeid_au > 0:
        handles.append(mpatches.Patch(facecolor="none", edgecolor="#00FFAA",
                                       linewidth=1.5, label="Earth Equiv. Insolation Dist"))
    ax.legend(handles=handles, loc="upper left", fontsize=6.5,
              framealpha=0.25, labelcolor="white",
              facecolor="#111133", edgecolor="#444466")

    fig.tight_layout(pad=1.0)
    toolbar = NavToolbar(canvas, parent)
    return canvas, toolbar


# ── Orbital Diagram ────────────────────────────────────────────────────────────

def make_orbits_canvas(parent, orbits: list, hz_zones: list,
                       max_au: float, star_name: str = "",
                       eeid_au: float = None):
    """Keplerian ellipse orbital diagram with HZ annulus overlay.

    orbits: list of dicts {name, x_pts, y_pts, color, peri, sma, apo, ecc}.
    hz_zones: list of dicts {label, outer, color} ordered inner→outer.
    Returns (canvas, toolbar).
    """
    fig = Figure(figsize=(6.5, 6.5), facecolor=_SPACE_BG)
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111, aspect="equal", facecolor=_SPACE_BG)

    # HZ annulus (faint background)
    if hz_zones:
        for zone in reversed(hz_zones):
            ax.add_patch(Circle((0, 0), zone["outer"],
                                color=zone["color"], alpha=0.15, zorder=1))
        ax.add_patch(Circle((0, 0), hz_zones[-1]["outer"],
                            fill=False, edgecolor="#4499FF",
                            linewidth=0.8, linestyle=":", alpha=0.5, zorder=2))
        ax.add_patch(Circle((0, 0), hz_zones[0]["outer"],
                            fill=False, edgecolor="#CC3300",
                            linewidth=0.8, linestyle=":", alpha=0.5, zorder=2))

    # Earth Equiv. Insolation marker
    if eeid_au and eeid_au > 0:
        ax.add_patch(Circle((0, 0), eeid_au,
                            fill=False, edgecolor="#00FFAA",
                            linewidth=1.2, linestyle="-", alpha=0.7, zorder=3))

    # Planet orbits
    for orb in orbits:
        ax.plot(orb["x_pts"], orb["y_pts"],
                color=orb["color"], linewidth=1.2, zorder=3,
                label=f"{orb['name']}  (a={orb['sma']:.3f} AU)")
        ax.scatter([orb["peri"]], [0], color=orb["color"], s=18, zorder=4)

    # Star
    star_r = max_au * 0.015
    ax.add_patch(Circle((0, 0), star_r, color="#FFEE55", zorder=10))
    if star_name:
        ax.text(0, star_r * 1.8, star_name,
                color="#FFEE55", fontsize=7, ha="center", va="bottom",
                alpha=0.85, zorder=11)

    _style_ax(ax, max_au, "Planetary Orbits")

    ax.legend(loc="upper right", fontsize=7, framealpha=0.25,
              labelcolor="white", facecolor="#111133", edgecolor="#444466")

    fig.tight_layout(pad=1.0)
    toolbar = NavToolbar(canvas, parent)
    return canvas, toolbar


# ── Star Map ───────────────────────────────────────────────────────────────────

def make_star_map_canvas(parent, stars: list, title: str = "",
                         xk: str = "x", yk: str = "y",
                         xlabel: str = "X (ly)", ylabel: str = "Y (ly)"):
    """2D scatter star map.

    stars: list of dicts {name, color, ly, x, y, z}.
    The first star in the list is treated as the origin/center star (highlighted).
    Returns (canvas, toolbar).
    """
    xs     = [s[xk]    for s in stars]
    ys     = [s[yk]    for s in stars]
    colors = [s["color"] for s in stars]
    names  = [s["name"]  for s in stars]
    sizes  = [60 if i == 0 else 12 for i in range(len(stars))]

    fig = Figure(figsize=(6, 6), facecolor=_SPACE_BG)
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111, facecolor=_SPACE_BG)

    sc = ax.scatter(xs, ys, c=colors, s=sizes, linewidths=0, alpha=0.85,
                    picker=True, pickradius=4, zorder=3)

    # Highlight center star
    ax.scatter([xs[0]], [ys[0]], c=[colors[0]], s=90, marker="*",
               zorder=5, edgecolors="white", linewidths=0.5)

    ax.set_xlabel(xlabel, color=_LABEL_CLR, fontsize=9)
    ax.set_ylabel(ylabel, color=_LABEL_CLR, fontsize=9)
    ax.tick_params(colors=_LABEL_CLR, labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor(_GRID_CLR)
    ax.grid(True, color=_GRID_CLR, linewidth=0.5, linestyle=":")
    ax.set_title(title, color=_LABEL_CLR, fontsize=10, pad=8)

    # Spectral class legend
    seen = {}
    for s in stars:
        cls = (s["sp_type"][0].upper() if s.get("sp_type") else "?")
        if cls not in seen:
            seen[cls] = s["color"]
    handles = [mpatches.Patch(color=c, label=f"Class {k}")
               for k, c in sorted(seen.items()) if k != "?"]
    if handles:
        ax.legend(handles=handles, loc="upper right", fontsize=7,
                  framealpha=0.25, labelcolor="white",
                  facecolor="#111133", edgecolor="#444466")

    # Hover tooltip
    annot = ax.annotate(
        "", xy=(0, 0), xytext=(12, 12), textcoords="offset points",
        bbox=dict(boxstyle="round,pad=0.3", fc="#111133", ec="#4488ff",
                  lw=0.8, alpha=0.9),
        arrowprops=dict(arrowstyle="->", color="#4488ff", lw=0.8),
        color="white", fontsize=8, zorder=10,
    )
    annot.set_visible(False)

    def _on_motion(event):
        if event.inaxes != ax:
            if annot.get_visible():
                annot.set_visible(False)
                canvas.draw_idle()
            return
        cont, ind = sc.contains(event)
        if cont:
            idx = ind["ind"][0]
            annot.xy = (xs[idx], ys[idx])
            ly_val = stars[idx].get("ly", 0)
            annot.set_text(f"{names[idx]}\n{ly_val:.2f} ly")
            annot.set_visible(True)
        else:
            annot.set_visible(False)
        canvas.draw_idle()

    canvas.mpl_connect("motion_notify_event", _on_motion)
    fig.tight_layout(pad=1.0)
    toolbar = NavToolbar(canvas, parent)
    return canvas, toolbar


# ── System Regions Diagram ─────────────────────────────────────────────────────

def make_system_regions_canvas(parent, data: dict):
    """Log-scale radial ruler showing system region boundaries.

    data: result of core.viz.prepare_system_regions_diagram().
    Returns (canvas, toolbar).
    """
    regions  = data["regions"]
    hz_zones = data["hz_zones"]
    eeid_au  = data.get("eeid_au", 0.0)

    # Gather all AU values and filter out zero/negative
    all_aus = [r["au"] for r in regions if r["au"] > 0]
    if not all_aus:
        return None, None

    max_au = max(all_aus) * 1.1
    min_au = min(r["au"] for r in hz_zones if r.get("outer", 0) > 0) * 0.5 \
             if hz_zones else 0.05

    fig = Figure(figsize=(7, 4.5), facecolor=_SPACE_BG)
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111, facecolor=_SPACE_BG)

    y_star = 0.6
    y_hz   = 0.4

    # Draw the HZ annuli as horizontal colored bands
    prev_au = min_au
    for zone in hz_zones:
        outer = zone["outer"]
        if outer > 0 and outer > prev_au:
            ax.barh(y_hz, math.log10(outer) - math.log10(max(prev_au, min_au)),
                    left=math.log10(max(prev_au, min_au)), height=0.12,
                    color=zone["color"], alpha=0.5)
        prev_au = outer

    # Draw the EEID marker
    if eeid_au and eeid_au > 0:
        ax.axvline(math.log10(eeid_au), color="#00FFAA",
                   linewidth=1.5, linestyle="-", alpha=0.8, zorder=5)
        ax.text(math.log10(eeid_au), y_hz + 0.09, "EEID",
                color="#00FFAA", fontsize=7, ha="center", va="bottom")

    # System region boundary markers
    for r in regions:
        if r["au"] <= 0:
            continue
        log_au = math.log10(r["au"])
        ax.axvline(log_au, color=r["color"], linewidth=1.2,
                   linestyle="--", alpha=0.85, zorder=4)
        ax.text(log_au, y_star + 0.06, f"{r['au']:.2f}",
                color=r["color"], fontsize=6.5, ha="center", va="bottom",
                rotation=45)
        ax.text(log_au, y_star - 0.06, r["label"],
                color=r["color"], fontsize=6, ha="right", va="top",
                rotation=45)

    # Style
    log_min = math.log10(min_au)
    log_max = math.log10(max_au)
    ax.set_xlim(log_min, log_max)
    ax.set_ylim(0.0, 1.0)

    tick_vals = [v for v in [0.01, 0.1, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500]
                 if min_au <= v <= max_au * 1.1]
    ax.set_xticks([math.log10(v) for v in tick_vals])
    ax.set_xticklabels([f"{v:g} AU" for v in tick_vals],
                       color=_LABEL_CLR, fontsize=7, rotation=30)
    ax.set_yticks([])
    ax.tick_params(colors=_LABEL_CLR)
    for spine in ax.spines.values():
        spine.set_edgecolor(_GRID_CLR)
    ax.grid(True, axis="x", color=_GRID_CLR, linewidth=0.5, linestyle=":")
    ax.set_title("System Regions  (log AU scale)", color=_LABEL_CLR,
                 fontsize=10, pad=8)

    # Legend for HZ band
    handles = [mpatches.Patch(facecolor=z["color"], alpha=0.6,
                               label=z["label"]) for z in hz_zones]
    ax.legend(handles=handles, loc="upper right", fontsize=6.5,
              framealpha=0.25, labelcolor="white",
              facecolor="#111133", edgecolor="#444466")

    fig.tight_layout(pad=1.0)
    toolbar = NavToolbar(canvas, parent)
    return canvas, toolbar


# ── Internal helpers ───────────────────────────────────────────────────────────

def _style_ax(ax, max_au: float, title: str):
    ax.set_xlim(-max_au, max_au)
    ax.set_ylim(-max_au, max_au)
    ax.set_xlabel("AU", color=_LABEL_CLR, fontsize=9)
    ax.set_ylabel("AU", color=_LABEL_CLR, fontsize=9)
    ax.tick_params(colors=_LABEL_CLR, labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor(_GRID_CLR)
    ax.grid(True, color=_GRID_CLR, linewidth=0.5, linestyle=":")
    if title:
        ax.set_title(title, color=_LABEL_CLR, fontsize=10, pad=8)
