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
    from matplotlib.path import Path
    from matplotlib.lines import Line2D
    import matplotlib.patches as mpatches
    _MPL_OK = True
except ImportError:
    _MPL_OK = False

_SPACE_BG  = "#f5f5f5"
_LABEL_CLR = "#333333"
_GRID_CLR  = "#cccccc"


def mpl_available() -> bool:
    return _MPL_OK


# ── Click-to-info shared helpers ───────────────────────────────────────────────

def _make_info_box(ax):
    """Invisible details text box pinned to the bottom-left corner of the axes.

    Becomes visible and updates its text when the user clicks a diagram element.
    A second click on empty space dismisses it.
    """
    return ax.text(
        0.02, 0.02, "",
        transform=ax.transAxes,
        color="#333333", fontsize=7.5, va="bottom", ha="left",
        multialignment="left",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#fafaf0",
                  edgecolor="#2266cc", linewidth=1.2, alpha=0.93),
        zorder=20, visible=False,
    )


def _attach_ring_click(canvas, ax, info_box, click_zones, r_to_au, eeid_au=None):
    """Wire a click handler onto a concentric-ring diagram.

    click_zones : list of {inner_au, outer_au, title, body}  innermost → outermost.
                  Set outer_au=float("inf") for the unbounded exterior zone.
    r_to_au     : callable(visual_r) → AU — inverse of the diagram's scale mapping.
    eeid_au     : AU of the EEID circle (optional).
    """
    EEID_TOL = 0.06  # fraction tolerance for snapping to the EEID circle

    def _on_click(event):
        if event.inaxes is not ax or event.xdata is None:
            if info_box.get_visible():
                info_box.set_visible(False)
                canvas.draw_idle()
            return

        au = r_to_au(math.sqrt(event.xdata ** 2 + event.ydata ** 2))

        if eeid_au and eeid_au > 0 and abs(au - eeid_au) < eeid_au * EEID_TOL:
            info_box.set_text(
                "Earth Equivalent Insolation Distance (EEID)\n"
                f"  {eeid_au:.4f} AU  ·  {eeid_au * 8.3167:.4f} LM\n\n"
                "The orbital distance that receives the same stellar\n"
                "flux as Earth receives from the Sun (1 S☉)."
            )
            info_box.set_visible(True)
            canvas.draw_idle()
            return

        for z in click_zones:
            if z["inner_au"] <= au < z["outer_au"]:
                outer_str = (f"{z['outer_au']:.4f} AU"
                             if z["outer_au"] < 1e9 else "∞")
                info_box.set_text(
                    f"{z['title']}\n"
                    f"  {z['inner_au']:.4f} – {outer_str}\n\n"
                    f"{z['body']}"
                )
                info_box.set_visible(True)
                canvas.draw_idle()
                return

        if info_box.get_visible():
            info_box.set_visible(False)
            canvas.draw_idle()

    canvas.mpl_connect("button_press_event", _on_click)


# ── HZ Diagram ─────────────────────────────────────────────────────────────────

def make_hz_canvas(parent, zones: list, max_au: float, title: str = "",
                   eeid_au: float = None):
    """Concentric ring HZ diagram.

    zones: list of dicts {label, outer, color} ordered inner→outer.
    eeid_au: if given, draw a dashed circle at this AU (Earth Equiv. Insolation).
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
                            fill=False, edgecolor="#555555",
                            linewidth=0.8, linestyle="--", alpha=0.45, zorder=3))
        lx = zone["outer"] * 0.717
        ly_ = zone["outer"] * 0.717
        ax.text(lx, ly_, f"{zone['outer']:.3f} AU",
                color="#333333", fontsize=6.5, ha="left", va="bottom",
                alpha=0.85, zorder=4)

    # Earth Equivalent Insolation Distance marker
    if eeid_au and eeid_au > 0:
        ax.add_patch(Circle((0, 0), eeid_au,
                            fill=False, edgecolor="#006644",
                            linewidth=1.5, linestyle="-", alpha=0.85, zorder=5))
        ax.text(eeid_au * 0.717, -eeid_au * 0.717,
                f"EEID\n{eeid_au:.3f} AU",
                color="#006644", fontsize=6.5, ha="left", va="top",
                alpha=0.9, zorder=6)

    # Star
    star_r = max_au * 0.018
    ax.add_patch(Circle((0, 0), star_r, color="#FFEE55", zorder=10))

    _style_ax(ax, max_au, title)

    handles = [mpatches.Patch(facecolor=z["color"], edgecolor="#555555",
                               alpha=0.7, label=z["label"]) for z in zones]
    handles.append(mpatches.Patch(facecolor=_SPACE_BG, edgecolor="#555555",
                                   alpha=0.7, label="Too Cold  (> Early Mars)"))
    if eeid_au and eeid_au > 0:
        handles.append(mpatches.Patch(facecolor="none", edgecolor="#006644",
                                       linewidth=1.5, label="Earth Equiv. Insolation Dist"))
    ax.legend(handles=handles, loc="upper left", fontsize=6.5,
              framealpha=0.85, labelcolor="#333333",
              facecolor="#ffffff", edgecolor="#aaaaaa")

    # ── Click-to-info ─────────────────────────────────────────────────────────
    _hz_bodies = {
        "rv":   ("Too close — runaway greenhouse effect.\n"
                 "All surface water evaporated. Venus lies just inside\n"
                 "this boundary."),
        "rg5":  ("Optimistic Inner HZ.\n"
                 "Between Recent Venus and the 5-Earth-mass Runaway\n"
                 "Greenhouse limit. Possibly habitable under specific\n"
                 "atmospheric conditions."),
        "rg":   ("Conservative Inner HZ.\n"
                 "Between the 5-Earth-mass and standard Runaway Greenhouse\n"
                 "limits. Marginal — heavier worlds retain water more easily."),
        "rg01": ("Conservative Inner HZ.\n"
                 "Between the standard and 0.1-Earth-mass Runaway Greenhouse\n"
                 "limits. Good habitability range for rocky planets."),
        "mg":   ("Conservative Habitable Zone.\n"
                 "Between the Runaway Greenhouse and Maximum Greenhouse\n"
                 "boundaries. Best estimate for Earth-like liquid water.\n"
                 "Earth's zone equivalent."),
        "em":   ("Optimistic Outer HZ.\n"
                 "Between Maximum Greenhouse and Early Mars limits.\n"
                 "Requires strong CO2 greenhouse warming. Mars orbit\n"
                 "lies near this boundary."),
    }
    _hz_click = []
    _prev = 0.0
    for z in zones:
        _hz_click.append({
            "inner_au": _prev, "outer_au": z["outer"],
            "title": z["label"],
            "body": _hz_bodies.get(z["key"], "Habitable zone region."),
        })
        _prev = z["outer"]
    _hz_click.append({
        "inner_au": _prev, "outer_au": float("inf"),
        "title": "Too Cold  (Beyond Outer HZ)",
        "body": ("Beyond the Early Mars boundary.\n"
                 "Too cold for liquid water without extreme\n"
                 "greenhouse gas warming."),
    })
    _attach_ring_click(canvas, ax, _make_info_box(ax), _hz_click,
                       r_to_au=lambda r: r, eeid_au=eeid_au)

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
                            fill=False, edgecolor="#006644",
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
                color="#CC8800", fontsize=7, ha="center", va="bottom",
                alpha=0.85, zorder=11)

    _style_ax(ax, max_au, "Planetary Orbits")

    # ── Legend: orbit lines + HZ boundary lines ────────────────────────────────
    orbit_handles, _ = ax.get_legend_handles_labels()
    hz_legend = []
    if hz_zones:
        hz_legend.append(Line2D(
            [0], [0], color="#CC3300", linewidth=0.8, linestyle=":",
            alpha=0.8, label=f"Inner HZ Boundary  ({hz_zones[0]['outer']:.3f} AU)",
        ))
        hz_legend.append(Line2D(
            [0], [0], color="#4499FF", linewidth=0.8, linestyle=":",
            alpha=0.8, label=f"Outer HZ Boundary  ({hz_zones[-1]['outer']:.3f} AU)",
        ))
    if eeid_au and eeid_au > 0:
        hz_legend.append(Line2D(
            [0], [0], color="#006644", linewidth=1.2, linestyle="-",
            alpha=0.8, label=f"Earth Equiv. Insolation  ({eeid_au:.3f} AU)",
        ))
    ax.legend(handles=orbit_handles + hz_legend, loc="upper right", fontsize=7,
              framealpha=0.85, labelcolor="#333333",
              facecolor="#ffffff", edgecolor="#aaaaaa")

    # ── Click-to-info: planet orbits take priority; HZ zones as fallback ───────
    _hz_bodies = {
        "rv":   ("Too close — runaway greenhouse effect.\n"
                 "All surface water evaporated. Venus lies just inside\n"
                 "this boundary."),
        "rg5":  ("Optimistic Inner HZ.\n"
                 "Between Recent Venus and the 5-Earth-mass Runaway\n"
                 "Greenhouse limit. Possibly habitable under specific\n"
                 "atmospheric conditions."),
        "rg":   ("Conservative Inner HZ.\n"
                 "Between the 5-Earth-mass and standard Runaway Greenhouse\n"
                 "limits. Marginal — heavier worlds retain water more easily."),
        "rg01": ("Conservative Inner HZ.\n"
                 "Between the standard and 0.1-Earth-mass Runaway Greenhouse\n"
                 "limits. Good habitability range for rocky planets."),
        "mg":   ("Conservative Habitable Zone.\n"
                 "Between the Runaway Greenhouse and Maximum Greenhouse\n"
                 "boundaries. Best estimate for Earth-like liquid water.\n"
                 "Earth's zone equivalent."),
        "em":   ("Optimistic Outer HZ.\n"
                 "Between Maximum Greenhouse and Early Mars limits.\n"
                 "Requires strong CO2 greenhouse warming. Mars orbit\n"
                 "lies near this boundary."),
    }
    _hz_click = []
    _prev_au = 0.0
    for z in hz_zones:
        _hz_click.append({
            "inner_au": _prev_au, "outer_au": z["outer"],
            "title": z["label"],
            "body": _hz_bodies.get(z["key"], "Habitable zone region."),
        })
        _prev_au = z["outer"]
    _hz_click.append({
        "inner_au": _prev_au, "outer_au": float("inf"),
        "title": "Too Cold  (Beyond Outer HZ)",
        "body": ("Beyond the Early Mars boundary.\n"
                 "Too cold for liquid water without extreme\n"
                 "greenhouse gas warming."),
    })

    _orb_box = _make_info_box(ax)
    EEID_TOL = 0.06

    def _on_orb_click(event):
        if event.inaxes is not ax or event.xdata is None:
            if _orb_box.get_visible():
                _orb_box.set_visible(False)
                canvas.draw_idle()
            return
        cx, cy = event.xdata, event.ydata

        # Priority 1: planet orbit
        best, best_d = None, float("inf")
        for orb in orbits:
            d = min(math.sqrt((cx - px) ** 2 + (cy - py) ** 2)
                    for px, py in zip(orb["x_pts"], orb["y_pts"]))
            if d < best_d:
                best_d, best = d, orb
        if best is not None and best_d < max_au * 0.08:
            o = best
            hz_note = ""
            if hz_zones:
                hz_in  = hz_zones[0]["outer"]
                hz_out = hz_zones[-1]["outer"]
                if o["peri"] <= hz_out and o["apo"] >= hz_in:
                    hz_note = "\n  Orbit intersects the Habitable Zone"
            _orb_box.set_text(
                f"{o['name']}\n"
                f"  Semi-Major Axis  : {o['sma']:.4f} AU\n"
                f"  Periastron       : {o['peri']:.4f} AU"
                f"  ({o['peri'] * 8.3167:.3f} LM)\n"
                f"  Apastron         : {o['apo']:.4f} AU"
                f"  ({o['apo'] * 8.3167:.3f} LM)\n"
                f"  Eccentricity     : {o['ecc']:.4f}"
                f"{hz_note}"
            )
            _orb_box.set_visible(True)
            canvas.draw_idle()
            return

        # Priority 2: EEID circle
        click_au = math.sqrt(cx ** 2 + cy ** 2)
        if eeid_au and eeid_au > 0 and abs(click_au - eeid_au) < eeid_au * EEID_TOL:
            _orb_box.set_text(
                "Earth Equivalent Insolation Distance (EEID)\n"
                f"  {eeid_au:.4f} AU  ·  {eeid_au * 8.3167:.4f} LM\n\n"
                "The orbital distance that receives the same stellar\n"
                "flux as Earth receives from the Sun (1 S☉)."
            )
            _orb_box.set_visible(True)
            canvas.draw_idle()
            return

        # Priority 3: HZ background zone
        for z in _hz_click:
            if z["inner_au"] <= click_au < z["outer_au"]:
                outer_str = (f"{z['outer_au']:.4f} AU"
                             if z["outer_au"] < 1e9 else "∞")
                _orb_box.set_text(
                    f"{z['title']}\n"
                    f"  {z['inner_au']:.4f} – {outer_str}\n\n"
                    f"{z['body']}"
                )
                _orb_box.set_visible(True)
                canvas.draw_idle()
                return

        if _orb_box.get_visible():
            _orb_box.set_visible(False)
        canvas.draw_idle()

    canvas.mpl_connect("button_press_event", _on_orb_click)

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
               zorder=5, edgecolors="#333333", linewidths=0.5)

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
                  framealpha=0.85, labelcolor="#333333",
                  facecolor="#ffffff", edgecolor="#aaaaaa")

    # Hover tooltip
    annot = ax.annotate(
        "", xy=(0, 0), xytext=(12, 12), textcoords="offset points",
        bbox=dict(boxstyle="round,pad=0.3", fc="#f8f8f0", ec="#2266cc",
                  lw=0.8, alpha=0.9),
        arrowprops=dict(arrowstyle="->", color="#2266cc", lw=0.8),
        color="#333333", fontsize=8, zorder=10,
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

    # Click for detailed star info
    _sm_box = _make_info_box(ax)

    def _on_sm_click(event):
        if event.inaxes is not ax or event.xdata is None:
            if _sm_box.get_visible():
                _sm_box.set_visible(False)
                canvas.draw_idle()
            return
        cont, ind = sc.contains(event)
        if cont:
            idx  = ind["ind"][0]
            s    = stars[idx]
            desig = (s.get("desig") or "").strip()
            sp    = (s.get("sp_type") or "").strip()
            ly_val = s.get("ly", 0.0)
            lines  = [names[idx]]
            if desig:
                lines.append(f"  Designations : {desig}")
            if sp:
                lines.append(f"  Spectral Type: {sp}")
            lines.append(f"  Distance     : {ly_val:.4f} ly")
            _sm_box.set_text("\n".join(lines))
            _sm_box.set_visible(True)
        elif _sm_box.get_visible():
            _sm_box.set_visible(False)
        canvas.draw_idle()

    canvas.mpl_connect("button_press_event", _on_sm_click)

    fig.tight_layout(pad=1.0)
    toolbar = NavToolbar(canvas, parent)
    return canvas, toolbar


# ── System Regions Diagram ─────────────────────────────────────────────────────

# Zone fill colors for the area between consecutive region boundaries,
# ordered innermost (core) → outermost.
_SR_ZONE_FILLS = [
    "#5C0000",  # core → sysilGrav:           forbidden (gravity)
    "#992200",  # sysilGrav → sysilSunlight:  inner limit
    "#CC6600",  # sysilSunlight → hzil:       warm inner zone
    "#1C7A40",  # hzil → hzol:                habitable zone
    "#1A4472",  # hzol → snowLine:            cool outer zone
    "#1A1050",  # snowLine → lh2Line:         ice zone
    "#04040C",  # lh2Line → sysol:            deep outer
]

_SR_ZONE_NAMES = [
    "Forbidden (Gravity)",
    "Inner Limit Zone",
    "Inner Warm Zone",
    "Habitable Zone",
    "Outer Cool Zone",
    "Ice Zone",
    "Deep Outer Zone",
]


def make_system_regions_canvas(parent, data: dict):
    """Concentric ring diagram (√AU scale) showing star system region boundaries.

    Regions are painted as colored tori from the star outward, with √AU compression
    so all zones from the inner gravity limit to the system outer limit are visible.

    data: result of core.viz.prepare_system_regions_diagram().
    Returns (canvas, toolbar) or (None, None) on failure.
    """
    regions = data.get("regions", [])
    eeid_au = data.get("eeid_au", 0.0)

    valid = [r for r in regions if r.get("au", 0) > 0]
    if not valid:
        return None, None

    sysol_au = valid[-1]["au"]  # outermost boundary (System Outer Limit)

    def au_to_r(au):
        """Map AU → visual radius using √ compression; sysol → 1.0."""
        return math.sqrt(au / sysol_au)

    MAX_R  = 1.06
    STAR_R = MAX_R * 0.016

    fig = Figure(figsize=(7, 7), facecolor=_SPACE_BG)
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111, aspect="equal", facecolor=_SPACE_BG)
    ax.set_xlim(-MAX_R, MAX_R)
    ax.set_ylim(-MAX_R, MAX_R)
    ax.axis("off")

    # Paint solid disks from outside in; each smaller disk overwrites the interior,
    # leaving only the annulus between consecutive boundaries visible as a colored ring.
    for i in range(len(valid) - 1, -1, -1):
        fill = _SR_ZONE_FILLS[i] if i < len(_SR_ZONE_FILLS) else "#04040C"
        ax.add_patch(Circle((0, 0), au_to_r(valid[i]["au"]), color=fill, zorder=2))

    # Dashed boundary circles
    for r_dict in valid:
        ax.add_patch(Circle(
            (0, 0), au_to_r(r_dict["au"]),
            fill=False, edgecolor=r_dict["color"],
            linewidth=0.9, linestyle="--", alpha=0.75, zorder=5,
        ))

    # AU labels at staggered angles (50° apart starting at 20°) to avoid overlap
    for i, r_dict in enumerate(valid):
        r   = au_to_r(r_dict["au"])
        ang = math.radians(20 + i * 50)
        lx  = r * math.cos(ang) * 1.08
        ly  = r * math.sin(ang) * 1.08
        ax.text(lx, ly, f"{r_dict['label']}\n{r_dict['au']:.2f} AU",
                color=r_dict["color"], fontsize=6, ha="center", va="center",
                alpha=0.9, zorder=6)

    # Earth Equivalent Insolation Distance marker
    if eeid_au and 0 < eeid_au < sysol_au:
        r_e = au_to_r(eeid_au)
        ax.add_patch(Circle((0, 0), r_e,
                            fill=False, edgecolor="#006644",
                            linewidth=1.5, linestyle="-", alpha=0.85, zorder=7))
        ax.text(r_e * 0.717, -r_e * 0.717, f"EEID\n{eeid_au:.3f} AU",
                color="#006644", fontsize=6, ha="left", va="top", zorder=8)

    # Star
    ax.add_patch(Circle((0, 0), STAR_R, color="#FFEE55", zorder=10))

    ax.set_title("Star System Regions  (√AU scale)", color=_LABEL_CLR,
                 fontsize=10, pad=8)

    # Legend: one entry per zone (fill + zone name + boundary AU)
    handles = []
    for i, r_dict in enumerate(valid):
        fill  = _SR_ZONE_FILLS[i] if i < len(_SR_ZONE_FILLS) else "#04040C"
        zname = _SR_ZONE_NAMES[i] if i < len(_SR_ZONE_NAMES) else ""
        handles.append(mpatches.Patch(
            facecolor=fill, edgecolor=r_dict["color"],
            linewidth=0.7, alpha=0.85,
            label=f"{r_dict['label']}  ·  {zname}  ({r_dict['au']:.2f} AU)",
        ))
    if eeid_au and 0 < eeid_au < sysol_au:
        handles.append(mpatches.Patch(
            facecolor="none", edgecolor="#006644", linewidth=1.5,
            label=f"Earth Equiv. Insolation  ({eeid_au:.3f} AU)",
        ))
    ax.legend(handles=handles, loc="upper right", fontsize=6,
              framealpha=0.85, labelcolor="#333333",
              facecolor="#ffffff", edgecolor="#aaaaaa",
              borderpad=0.6, labelspacing=0.35)

    # ── Click-to-info ─────────────────────────────────────────────────────────
    _sr_bodies = [
        ("No stable planetary orbits possible here.\n"
         "Inside the gravitational inner stability limit."),
        ("Between the gravity and sunlight inner limits.\n"
         "Extreme irradiation — surface temperatures\n"
         "reach thousands of degrees."),
        ("Inside the circumstellar HZ inner limit.\n"
         "Too hot for water-based life. Possible for\n"
         "hot biochemistries (fluorosilicone, fluorocarbon)."),
        ("Between the HZ inner and outer limits.\n"
         "Favourable for liquid water and Earth-like\n"
         "biochemistry. The classical habitable zone."),
        ("Beyond the HZ outer limit, inside the snow line.\n"
         "Too cold for liquid water. Ice-covered surfaces.\n"
         "Ammonia-based biochemistry possible."),
        ("Between the snow line and the LH2 line.\n"
         "Water ice, CO2 and other volatiles condense.\n"
         "Region favoured for gas giant formation."),
        ("Between the LH2 line and the system outer limit.\n"
         "Liquid hydrogen/helium near absolute zero.\n"
         "Theoretical polylipid-hydrogen biochemistry region."),
    ]
    _sr_click = []
    _sr_prev = 0.0
    for i, r_dict in enumerate(valid):
        name = _SR_ZONE_NAMES[i] if i < len(_SR_ZONE_NAMES) else r_dict["label"]
        body = _sr_bodies[i] if i < len(_sr_bodies) else ""
        _sr_click.append({
            "inner_au": _sr_prev, "outer_au": r_dict["au"],
            "title": name, "body": body,
        })
        _sr_prev = r_dict["au"]
    _sr_click.append({
        "inner_au": _sr_prev, "outer_au": float("inf"),
        "title": "Beyond System Outer Limit",
        "body": ("Outside the gravitational outer stability limit.\n"
                 "No stable planetary orbits expected\n"
                 "beyond this distance."),
    })
    _attach_ring_click(canvas, ax, _make_info_box(ax), _sr_click,
                       r_to_au=lambda r: r * r * sysol_au,
                       eeid_au=eeid_au if 0 < eeid_au < sysol_au else None)

    fig.tight_layout(pad=0.5)
    toolbar = NavToolbar(canvas, parent)
    return canvas, toolbar


# ── Alternate HZ Diagram ───────────────────────────────────────────────────────

def _annulus_path(r_inner: float, r_outer: float, n: int = 120):
    """Compound matplotlib Path for a filled annulus (outer disk with inner hole).

    Outer ring is wound counterclockwise, inner ring clockwise — correct for the
    non-zero winding fill rule so only the band between the two radii is filled.
    """
    thetas_fwd = [2 * math.pi * k / n for k in range(n)]
    thetas_rev = thetas_fwd[::-1]
    outer = [(r_outer * math.cos(t), r_outer * math.sin(t)) for t in thetas_fwd]
    inner = [(r_inner * math.cos(t), r_inner * math.sin(t)) for t in thetas_rev]
    verts = outer + [outer[0]] + inner + [inner[0]]
    codes = ([Path.MOVETO] + [Path.LINETO] * (n - 1) + [Path.CLOSEPOLY] +
             [Path.MOVETO] + [Path.LINETO] * (n - 1) + [Path.CLOSEPOLY])
    return Path(verts, codes)


def make_alt_hz_canvas(parent, zones: list, max_au: float, title: str = "",
                       eeid_au: float = None):
    """Concentric ring diagram for alternate biochemistry habitable zones (⁴√AU scale).

    zones: list of dicts {label, inner_au, outer_au, color} ordered hot→cold.
    ⁴√AU (quartic-root) compression keeps all six zone rings simultaneously visible
    despite spanning three orders of magnitude in AU.
    Returns (canvas, toolbar).
    """
    def au_to_r(au):
        """Quartic-root compression: outermost zone outer edge → r = 1.0."""
        return (au / max_au) ** 0.25

    MAX_R  = 1.06
    STAR_R = MAX_R * 0.016

    fig = Figure(figsize=(7, 7), facecolor=_SPACE_BG)
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111, aspect="equal", facecolor=_SPACE_BG)
    ax.set_xlim(-MAX_R, MAX_R)
    ax.set_ylim(-MAX_R, MAX_R)
    ax.axis("off")

    # Paint annuli hot→cold (innermost first); each zone's PathPatch is an independent
    # donut so overlapping zones blend via alpha compositing rather than overwriting.
    for i, zone in enumerate(zones):
        r_inner = au_to_r(zone["inner_au"])
        r_outer = au_to_r(zone["outer_au"])
        ax.add_patch(mpatches.PathPatch(
            _annulus_path(r_inner, r_outer),
            facecolor=zone["color"], edgecolor="#555555",
            linewidth=0.5, alpha=0.62, zorder=3 + i,
        ))

    # Boundary dashed circles for each zone's inner and outer edge
    for zone in zones:
        for r_au in (zone["inner_au"], zone["outer_au"]):
            ax.add_patch(Circle(
                (0, 0), au_to_r(r_au),
                fill=False, edgecolor=zone["color"],
                linewidth=0.6, linestyle="--", alpha=0.5, zorder=9,
            ))

    # EEID marker
    if eeid_au and 0 < eeid_au < max_au:
        r_e = au_to_r(eeid_au)
        ax.add_patch(Circle((0, 0), r_e,
                            fill=False, edgecolor="#006644",
                            linewidth=1.5, linestyle="-", alpha=0.85, zorder=10))
        ax.text(r_e * 0.717, -r_e * 0.717, f"EEID\n{eeid_au:.3f} AU",
                color="#006644", fontsize=6, ha="left", va="top", zorder=11)

    # Star
    ax.add_patch(Circle((0, 0), STAR_R, color="#FFEE55", zorder=12))

    ax.set_title(title or "Alternate HZ Regions  (⁴√AU scale)",
                 color=_LABEL_CLR, fontsize=10, pad=8)

    # Legend: zone name + AU range
    handles = [
        mpatches.Patch(
            facecolor=z["color"], edgecolor="#555555",
            linewidth=0.7, alpha=0.75,
            label=f"{z['label']}  ({z['inner_au']:.3f} – {z['outer_au']:.3f} AU)",
        )
        for z in zones
    ]
    if eeid_au and 0 < eeid_au < max_au:
        handles.append(mpatches.Patch(
            facecolor="none", edgecolor="#006644", linewidth=1.5,
            label=f"Earth Equiv. Insolation  ({eeid_au:.3f} AU)",
        ))
    ax.legend(handles=handles, loc="upper right", fontsize=6,
              framealpha=0.85, labelcolor="#333333",
              facecolor="#ffffff", edgecolor="#aaaaaa",
              borderpad=0.6, labelspacing=0.35)

    # ── Click-to-info ─────────────────────────────────────────────────────────
    _alt_bodies = {
        "Fluorosilicone-Fluorosilicone":
            ("Solvent: Fluorosilicone oils  (Si-F based)\n"
             "Very high temperature biochemistry (~700 K+).\n"
             "Analogous to life near volcanic vents or very hot stars."),
        "Fluorocarbon-Sulfur":
            ("Solvent: Liquid sulfur / fluorocarbon compounds\n"
             "High temperature biochemistry.\n"
             "Possible for thermophilic worlds too hot for water life."),
        "Protein-Water":
            ("Solvent: Liquid water  (bp 100 C, mp 0 C)\n"
             "Standard Earth-like biochemistry — the Goldilocks zone.\n"
             "Best-studied and most widely accepted HZ definition."),
        "Protein-Ammonia":
            ("Solvent: Liquid ammonia  (bp -33 C, mp -78 C)\n"
             "Cold-zone analog to water-based life.\n"
             "Proposed for worlds too cold for the water HZ."),
        "Polylipid-Methane":
            ("Solvent: Liquid methane  (bp -161 C, mp -182 C)\n"
             "Very cold biochemistry — analogous to Titan's surface.\n"
             "Polylipid membranes replace phospholipid cell walls."),
        "Polylipid-Hydrogen":
            ("Solvent: Liquid hydrogen  (bp -253 C, mp -259 C)\n"
             "Extreme cold biochemistry near absolute zero.\n"
             "Highly speculative — theoretical outer HZ limit."),
    }
    _alt_click = [
        {
            "inner_au": z["inner_au"], "outer_au": z["outer_au"],
            "title": z["label"],
            "body": _alt_bodies.get(z["label"], "Alternate biochemistry HZ."),
        }
        for z in zones
    ]
    _attach_ring_click(canvas, ax, _make_info_box(ax), _alt_click,
                       r_to_au=lambda r: (r ** 4) * max_au,
                       eeid_au=eeid_au if eeid_au and 0 < eeid_au < max_au else None)

    fig.tight_layout(pad=0.5)
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
