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


def log_viz_error(context: str) -> None:
    """Print the active exception traceback to stderr with a context label.

    Used by panel viz-tab builders in place of a bare ``except Exception: pass`` so
    a diagram that fails to render is dropped gracefully (the rest of the panel
    still works) but the failure is no longer invisible.
    """
    import sys
    import traceback
    print(f"[viz] {context} failed to render:", file=sys.stderr)
    traceback.print_exc()


def wrap_scrollable(parent, canvas, toolbar):
    """Wrap a (canvas, toolbar) pair in a widget whose canvas can scroll vertically.

    The toolbar stays pinned at the top; the canvas sits in a QScrollArea sized to
    the figure's natural pixel height. For short figures this looks identical to
    embedding the canvas directly; for tall ones (e.g. an abundance chart with 50+
    bars) the chart keeps its readable per-bar height and the user scrolls instead
    of the bars being squashed to fit the tab.
    """
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea

    if canvas is None:
        return None

    container = QWidget(parent)
    lay = QVBoxLayout(container)
    lay.setContentsMargins(4, 4, 4, 4)
    lay.setSpacing(2)
    if toolbar is not None:
        lay.addWidget(toolbar)

    try:
        fig = canvas.figure
        px_h = int(fig.get_size_inches()[1] * fig.dpi)
        canvas.setMinimumHeight(px_h)
    except Exception:
        pass

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(canvas)
    lay.addWidget(scroll)
    return container


def _disable_zoom_rect(toolbar):
    """Remove the rectangle-zoom tool from a 3D toolbar.

    Zoom-to-rectangle doesn't work correctly in 3D — the 2D screen rectangle
    can't be cleanly mapped back to tilted 3D data coordinates, so the result
    always shifts off-centre. Scroll-wheel zoom is the correct tool for 3D.
    """
    for action in toolbar.actions():
        if action.text() == "Zoom":
            toolbar.removeAction(action)
            break


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


def _attach_ring_click(canvas, ax, info_box, click_zones, r_to_au, eeid_au=None,
                       markers=None):
    """Wire a click handler onto a concentric-ring diagram.

    click_zones : list of {inner_au, outer_au, title, body}  innermost → outermost.
                  Set outer_au=float("inf") for the unbounded exterior zone.
    r_to_au     : callable(visual_r) → AU — inverse of the diagram's scale mapping.
    eeid_au     : AU of the EEID circle (optional).
    markers     : list of {label, au, color, body} for extra named circles (optional).
    """
    EEID_TOL = 0.06  # fraction tolerance for snapping to named circles

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

        if markers:
            for m in markers:
                m_au = m.get("au", 0)
                if m_au > 0 and abs(au - m_au) < m_au * EEID_TOL:
                    info_box.set_text(
                        f"{m['label']}\n"
                        f"  {m_au:.4f} AU  ·  {m_au * 8.3167:.4f} LM\n\n"
                        f"{m['body']}"
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
                   eeid_au: float = None, markers: list = None):
    """Concentric ring HZ diagram.

    zones:   list of dicts {label, outer, color} ordered inner→outer.
    eeid_au: if given, draw a solid circle at this AU (Earth Equiv. Insolation).
    markers: optional list of {label, au, color, body} for extra named circles
             (e.g. Tidal Lock, Abiogenesis, Snow Line).
    Returns (canvas, toolbar).
    """
    valid_markers = [m for m in (markers or []) if m.get("au") and m["au"] > 0]
    if valid_markers:
        max_marker_au = max(m["au"] for m in valid_markers)
        if max_marker_au > max_au * 0.85:
            max_au = max_marker_au * 1.2

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

    # Extra named marker circles (Tidal Lock, Abiogenesis, Snow Line, etc.)
    for m in valid_markers:
        ax.add_patch(Circle((0, 0), m["au"],
                            fill=False, edgecolor=m["color"],
                            linewidth=1.2, linestyle="-.", alpha=0.8, zorder=5))
        ax.text(-m["au"] * 0.717, -m["au"] * 0.717,
                f"{m['label']}\n{m['au']:.3f} AU",
                color=m["color"], fontsize=6.5, ha="right", va="top",
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
    for m in valid_markers:
        handles.append(mpatches.Patch(facecolor="none", edgecolor=m["color"],
                                       linewidth=1.5, label=f"{m['label']}  ({m['au']:.3f} AU)"))
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
                       r_to_au=lambda r: r, eeid_au=eeid_au,
                       markers=valid_markers if valid_markers else None)

    fig.tight_layout(pad=1.0)
    toolbar = NavToolbar(canvas, parent)
    return canvas, toolbar


# ── Orbital Diagram ────────────────────────────────────────────────────────────

def make_orbits_canvas(parent, orbits: list, hz_zones: list,
                       max_au: float, star_name: str = "",
                       eeid_au: float = None, markers: list = None):
    """Keplerian ellipse orbital diagram with HZ annulus overlay.

    orbits:  list of dicts {name, x_pts, y_pts, color, peri, sma, apo, ecc}.
    hz_zones: list of dicts {label, outer, color} ordered inner→outer.
    markers: optional list of {label, au, color, body} for extra named circles.
    Returns (canvas, toolbar).
    """
    valid_markers = [m for m in (markers or []) if m.get("au") and m["au"] > 0]
    if valid_markers:
        max_marker_au = max(m["au"] for m in valid_markers)
        if max_marker_au > max_au * 0.85:
            max_au = max_marker_au * 1.2

    fig = Figure(figsize=(6.5, 6.5), facecolor=_SPACE_BG)
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111, aspect="equal", facecolor=_SPACE_BG)

    # HZ zone fills and boundary lines (matching HZ diagram style)
    if hz_zones:
        for zone in reversed(hz_zones):
            ax.add_patch(Circle((0, 0), zone["outer"],
                                color=zone["color"], alpha=0.55, zorder=1))
        for zone in hz_zones:
            ax.add_patch(Circle((0, 0), zone["outer"],
                                fill=False, edgecolor="#555555",
                                linewidth=0.8, linestyle="--", alpha=0.45, zorder=2))

    # Earth Equiv. Insolation marker
    if eeid_au and eeid_au > 0:
        ax.add_patch(Circle((0, 0), eeid_au,
                            fill=False, edgecolor="#006644",
                            linewidth=1.2, linestyle="-", alpha=0.7, zorder=3))

    # Extra named marker circles (Tidal Lock, Abiogenesis, Snow Line, etc.)
    for m in valid_markers:
        ax.add_patch(Circle((0, 0), m["au"],
                            fill=False, edgecolor=m["color"],
                            linewidth=1.2, linestyle="-.", alpha=0.8, zorder=3))
        ax.text(-m["au"] * 0.717, -m["au"] * 0.717,
                f"{m['label']}\n{m['au']:.3f} AU",
                color=m["color"], fontsize=6.5, ha="right", va="top",
                alpha=0.9, zorder=4)

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

    # Note any planets whose entire orbit falls inside the star circle
    hidden = [orb for orb in orbits if orb["apo"] < star_r]
    if hidden:
        lines = ["Not shown (inside star circle at this scale):"]
        lines += [f"  {o['name']}  (a = {o['sma']:.4f} AU)" for o in hidden]
        ax.text(0.02, 0.02, "\n".join(lines), transform=ax.transAxes,
                color="#FFAA44", fontsize=7, va="bottom", ha="left",
                bbox=dict(facecolor="#1a1a1a", alpha=0.75,
                          edgecolor="#FFAA44", boxstyle="round,pad=3"))

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
    for m in valid_markers:
        hz_legend.append(Line2D(
            [0], [0], color=m["color"], linewidth=1.2, linestyle="-.",
            alpha=0.8, label=f"{m['label']}  ({m['au']:.3f} AU)",
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

        # Priority 3: named marker circles
        for m in valid_markers:
            m_au = m.get("au", 0)
            if m_au > 0 and abs(click_au - m_au) < m_au * EEID_TOL:
                _orb_box.set_text(
                    f"{m['label']}\n"
                    f"  {m_au:.4f} AU  ·  {m_au * 8.3167:.4f} LM\n\n"
                    f"{m['body']}"
                )
                _orb_box.set_visible(True)
                canvas.draw_idle()
                return

        # Priority 4: HZ background zone
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

# ── O-3 capability layer (additive): highlight_star + on_star_click ────────────
# Gives the opt-18/19 panels a way to (a) ring a star from a table-row selection
# and (b) be notified when a star is clicked on the map. Strictly additive: no
# ring artist exists until highlight_star is called, and callers that pass no
# on_star_click keep the inline info box — so opts 18/19 / GCNS / Phase-I renders
# are byte-identical until a panel opts in. The legend-filter split (O16) and
# isochrone rings (O17) land in their own later steps.
_HL_GOLD = "#FFD700"


def _attach_highlight_2d(canvas, ax, coord_map, hidden=None, name_cls=None):
    """Attach canvas.highlight_star(name|None) → hollow gold ring at the named
    star on a 2D axes. coord_map maps name → (x, y); an unknown name or None
    clears the ring. The ring is (re)created lazily, so a canvas that is never
    asked to highlight draws no extra artist (default render unchanged).

    When `hidden` (the shared legend-filter set) and `name_cls` (name → spectral
    class) are supplied, the ring tracks its star's class visibility: it is
    hidden while that class is legend-filtered off, and canvas.refresh_highlight()
    re-applies that rule after a legend toggle so the ring never lingers over a
    hidden dot."""
    holder = {"ring": None, "name": None}

    def _ring_visible(name):
        if not hidden or name_cls is None:
            return True
        return name_cls.get(name) not in hidden

    def _highlight(name):
        holder["name"] = name
        if holder["ring"] is not None:
            holder["ring"].remove()
            holder["ring"] = None
        xy = coord_map.get(name) if name else None
        if xy is not None:
            holder["ring"] = ax.scatter(
                [xy[0]], [xy[1]], s=260, facecolors="none",
                edgecolors=_HL_GOLD, linewidths=2.0, zorder=30)
            holder["ring"].set_visible(_ring_visible(name))
        canvas.draw_idle()

    def _refresh_highlight():
        if holder["ring"] is not None:
            holder["ring"].set_visible(_ring_visible(holder["name"]))
            canvas.draw_idle()

    view0 = {"lims": None}   # view captured just before the first find-centering

    def _center_on(name):
        """O18: centre the 2D view on `name` at half-range min(current, 15) ly so
        labels appear. No-op (returns False) for an unknown / null-coord star."""
        xy = coord_map.get(name)
        if xy is None:
            return False
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        if view0["lims"] is None:
            view0["lims"] = ((x0, x1), (y0, y1))   # remember the pre-find view
        half = min(max(abs(x1 - x0), abs(y1 - y0)) / 2.0, 15.0) or 15.0
        ax.set_xlim(xy[0] - half, xy[0] + half)
        ax.set_ylim(xy[1] - half, xy[1] + half)
        canvas.draw_idle()
        return True

    def _reset_view():
        """O18 Clear: restore the view captured before the first center_on."""
        if view0["lims"] is None:
            return False
        (x0, x1), (y0, y1) = view0["lims"]
        view0["lims"] = None
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        canvas.draw_idle()
        return True

    canvas.highlight_star = _highlight
    canvas.highlighted_star = lambda: holder["name"]
    canvas.refresh_highlight = _refresh_highlight
    canvas.center_on = _center_on
    canvas.reset_view = _reset_view
    canvas._o16_name_cls = name_cls or {}


def _attach_highlight_3d(canvas, ax, coord_map, hidden=None, name_cls=None):
    """3D companion to _attach_highlight_2d. coord_map maps name → (x, y, z).
    The ring is recreated on each call (3D collections lack a clean offset
    setter); none exists until highlight_star is first called. `hidden` /
    `name_cls` give the ring the same legend-filter awareness as the 2D version
    (hidden while its class is filtered off; canvas.refresh_highlight() re-applies)."""
    holder = {"ring": None, "name": None}

    def _ring_visible(name):
        if not hidden or name_cls is None:
            return True
        return name_cls.get(name) not in hidden

    def _highlight(name):
        holder["name"] = name
        if holder["ring"] is not None:
            holder["ring"].remove()
            holder["ring"] = None
        xyz = coord_map.get(name) if name else None
        if xyz is not None:
            holder["ring"] = ax.scatter(
                [xyz[0]], [xyz[1]], [xyz[2]], s=320, facecolors="none",
                edgecolors=_HL_GOLD, linewidths=2.0, depthshade=False, zorder=30)
            holder["ring"].set_visible(_ring_visible(name))
        canvas.draw_idle()

    def _refresh_highlight():
        if holder["ring"] is not None:
            holder["ring"].set_visible(_ring_visible(holder["name"]))
            canvas.draw_idle()

    view0 = {"lims": None}   # view captured just before the first find-centering

    def _center_on(name):
        """O18: centre the 3D view on `name` at half-range min(current, 15) ly.
        No-op (returns False) for an unknown / null-coord star."""
        xyz = coord_map.get(name)
        if xyz is None:
            return False
        x0, x1 = ax.get_xlim3d()
        y0, y1 = ax.get_ylim3d()
        z0, z1 = ax.get_zlim3d()
        if view0["lims"] is None:
            view0["lims"] = ((x0, x1), (y0, y1), (z0, z1))
        half = min(max(abs(x1 - x0), abs(y1 - y0), abs(z1 - z0)) / 2.0, 15.0) or 15.0
        ax.set_xlim3d(xyz[0] - half, xyz[0] + half)
        ax.set_ylim3d(xyz[1] - half, xyz[1] + half)
        ax.set_zlim3d(xyz[2] - half, xyz[2] + half)
        canvas.draw_idle()
        return True

    def _reset_view():
        """O18 Clear: restore the view captured before the first center_on."""
        if view0["lims"] is None:
            return False
        (x0, x1), (y0, y1), (z0, z1) = view0["lims"]
        view0["lims"] = None
        ax.set_xlim3d(x0, x1)
        ax.set_ylim3d(y0, y1)
        ax.set_zlim3d(z0, z1)
        canvas.draw_idle()
        return True

    canvas.highlight_star = _highlight
    canvas.highlighted_star = lambda: holder["name"]
    canvas.refresh_highlight = _refresh_highlight
    canvas.center_on = _center_on
    canvas.reset_view = _reset_view
    canvas._o16_name_cls = name_cls or {}


# ── O16 capability: opt-in per-spectral-class split + pickable legend filter ──
# Engaged only when a caller passes legend_filter=True (opts 18/19). GCNS / Phase-I
# pass the default False and keep the single-scatter path, so their render is
# unchanged (guarded by the O3 structural-regression test). When on, the body
# scatter becomes one PathCollection per spectral class; clicking a legend entry
# toggles that class (dots + labels) and dims the entry; the returned hit-test
# skips hidden classes so a filtered-out star can't be hovered/clicked.
def _legend_filter_2d(canvas, ax, xs, ys, colors, sp_types, sizes,
                      scatter_kw, legend_kw, hidden,
                      label_groups=None, label_state=None):
    """Draw per-class scatters + a pickable legend; return hit(event)->index|None.

    `hidden` is a shared set the caller's zoom/label logic also reads. The "?"
    (unknown-type) class is drawn but gets no legend entry — it is never
    filterable and stays visible, per the O-3 edge-case decisions."""
    from matplotlib.lines import Line2D

    groups = {}
    for i, sp in enumerate(sp_types):
        cls = (sp[0].upper() if sp else "?")
        groups.setdefault(cls, []).append(i)

    all_colls, index_maps, toggle = {}, {}, []
    for cls in sorted(groups):
        idxs = groups[cls]
        coll = ax.scatter([xs[i] for i in idxs], [ys[i] for i in idxs],
                          c=[colors[i] for i in idxs],
                          s=[sizes[i] for i in idxs], **scatter_kw)
        all_colls[cls] = coll
        index_maps[cls] = idxs
        if cls != "?":
            toggle.append(cls)

    handles = [Line2D([], [], marker="o", linestyle="", markersize=6,
                      markerfacecolor=colors[index_maps[cls][0]],
                      markeredgecolor="none", label=f"Class {cls}")
               for cls in toggle]
    legend = ax.legend(handles=handles, **legend_kw) if handles else None
    art2cls = {}
    if legend is not None:
        for legline, cls in zip(legend.legend_handles, toggle):
            legline.set_picker(6)
            art2cls[legline] = cls

    def _apply_labels(cls):
        if label_groups is None:
            return
        shown = (label_state or {}).get("shown", True)
        for txt in label_groups.get(cls, ()):
            txt.set_visible(shown and cls not in hidden)

    def _on_pick(event):
        cls = art2cls.get(event.artist)
        if cls is None:
            return
        coll = all_colls[cls]
        vis = not coll.get_visible()
        coll.set_visible(vis)
        event.artist.set_alpha(1.0 if vis else 0.3)
        for txt, h in zip(legend.get_texts(), legend.legend_handles):
            if h is event.artist:
                txt.set_alpha(1.0 if vis else 0.3)
        hidden.discard(cls) if vis else hidden.add(cls)
        _apply_labels(cls)
        # Hide/show the selection ring too if it sits on this class (O15 highlight
        # must not linger over a now-hidden dot). refresh_highlight is attached
        # later in the canvas builder, so resolve it lazily.
        refresh = getattr(canvas, "refresh_highlight", None)
        if refresh is not None:
            refresh()
        canvas.draw_idle()

    if legend is not None:
        canvas.mpl_connect("pick_event", _on_pick)

    def _reveal_class(cls):
        """O18: un-hide a legend-filtered class so find never centres on an
        invisible dot. No-op when the class is already shown / not filterable."""
        if cls not in hidden:
            return
        coll = all_colls.get(cls)
        if coll is not None:
            coll.set_visible(True)
        hidden.discard(cls)
        if legend is not None:
            for legline, txt, c in zip(legend.legend_handles,
                                       legend.get_texts(), toggle):
                if c == cls:
                    legline.set_alpha(1.0)
                    txt.set_alpha(1.0)
        _apply_labels(cls)
        refresh = getattr(canvas, "refresh_highlight", None)
        if refresh is not None:
            refresh()
        canvas.draw_idle()

    canvas._o16_reveal_class = _reveal_class

    def _hit(event):
        for cls, coll in all_colls.items():
            if not coll.get_visible():
                continue
            cont, ind = coll.contains(event)
            if cont:
                return index_maps[cls][ind["ind"][0]]
        return None

    return _hit


# ── O16 (CP3) capability: per-spectral-class split + pickable legend in 3D ─────
# 3D companion to _legend_filter_2d. Same opt-in contract (engaged only when a
# caller passes legend_filter=True; GCNS / Phase-I keep the single-scatter path,
# so their render is unchanged — guarded by the structural-regression test). The
# only differences are the z coordinate on each scatter and that the per-class
# PathCollections live on a 3D axes. Toggling visibility on 3D collections is
# best-effort (depthshade ordering aside), but set_visible / get_visible behave
# the same, so the pick-toggle + hidden-class hit guard work as in 2D.
def _legend_filter_3d(canvas, ax, xs, ys, zs, colors, sp_types, sizes,
                      scatter_kw, legend_kw, hidden,
                      label_groups=None, label_state=None):
    """Draw per-class 3D scatters + a pickable legend; return hit(event)->index|None.

    `hidden` is a shared set the caller's zoom/label logic also reads. The "?"
    (unknown-type) class is drawn but gets no legend entry — never filterable,
    always visible — matching the 2D helper and the O-3 edge-case decisions."""
    from matplotlib.lines import Line2D

    groups = {}
    for i, sp in enumerate(sp_types):
        cls = (sp[0].upper() if sp else "?")
        groups.setdefault(cls, []).append(i)

    all_colls, index_maps, toggle = {}, {}, []
    for cls in sorted(groups):
        idxs = groups[cls]
        coll = ax.scatter([xs[i] for i in idxs], [ys[i] for i in idxs],
                          [zs[i] for i in idxs],
                          c=[colors[i] for i in idxs],
                          s=[sizes[i] for i in idxs], **scatter_kw)
        all_colls[cls] = coll
        index_maps[cls] = idxs
        if cls != "?":
            toggle.append(cls)

    handles = [Line2D([], [], marker="o", linestyle="", markersize=6,
                      markerfacecolor=colors[index_maps[cls][0]],
                      markeredgecolor="none", label=f"Class {cls}")
               for cls in toggle]
    legend = ax.legend(handles=handles, **legend_kw) if handles else None
    art2cls = {}
    if legend is not None:
        for legline, cls in zip(legend.legend_handles, toggle):
            legline.set_picker(6)
            art2cls[legline] = cls

    def _apply_labels(cls):
        if label_groups is None:
            return
        shown = (label_state or {}).get("shown", True)
        for txt in label_groups.get(cls, ()):
            txt.set_visible(shown and cls not in hidden)

    def _on_pick(event):
        cls = art2cls.get(event.artist)
        if cls is None:
            return
        coll = all_colls[cls]
        vis = not coll.get_visible()
        coll.set_visible(vis)
        event.artist.set_alpha(1.0 if vis else 0.3)
        for txt, h in zip(legend.get_texts(), legend.legend_handles):
            if h is event.artist:
                txt.set_alpha(1.0 if vis else 0.3)
        hidden.discard(cls) if vis else hidden.add(cls)
        _apply_labels(cls)
        # Hide/show the selection ring too if it sits on this class (O15 highlight
        # must not linger over a now-hidden dot). refresh_highlight is attached
        # later in the canvas builder, so resolve it lazily.
        refresh = getattr(canvas, "refresh_highlight", None)
        if refresh is not None:
            refresh()
        canvas.draw_idle()

    if legend is not None:
        canvas.mpl_connect("pick_event", _on_pick)

    def _reveal_class(cls):
        """O18: un-hide a legend-filtered class so find never centres on an
        invisible dot. No-op when the class is already shown / not filterable."""
        if cls not in hidden:
            return
        coll = all_colls.get(cls)
        if coll is not None:
            coll.set_visible(True)
        hidden.discard(cls)
        if legend is not None:
            for legline, txt, c in zip(legend.legend_handles,
                                       legend.get_texts(), toggle):
                if c == cls:
                    legline.set_alpha(1.0)
                    txt.set_alpha(1.0)
        _apply_labels(cls)
        refresh = getattr(canvas, "refresh_highlight", None)
        if refresh is not None:
            refresh()
        canvas.draw_idle()

    canvas._o16_reveal_class = _reveal_class

    def _hit(event):
        for cls, coll in all_colls.items():
            if not coll.get_visible():
                continue
            cont, ind = coll.contains(event)
            if cont:
                return index_maps[cls][ind["ind"][0]]
        return None

    return _hit


def make_star_map_canvas(parent, stars: list, title: str = "",
                         xk: str = "x", yk: str = "y",
                         xlabel: str = "X (ly)", ylabel: str = "Y (ly)",
                         bg: str = _SPACE_BG, on_star_click=None,
                         legend_filter=False):
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

    fig = Figure(figsize=(6, 6), facecolor=bg)
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111, facecolor=bg)

    hidden = set()
    if legend_filter:
        sc = None
        hit = _legend_filter_2d(
            canvas, ax, xs, ys, colors,
            [s.get("sp_type", "") for s in stars], sizes,
            scatter_kw=dict(linewidths=0, alpha=0.85, zorder=3),
            legend_kw=dict(loc="upper right", fontsize=7, framealpha=0.85,
                           labelcolor="#333333", facecolor="#ffffff",
                           edgecolor="#aaaaaa"),
            hidden=hidden,
        )
    else:
        sc = ax.scatter(xs, ys, c=colors, s=sizes, linewidths=0, alpha=0.85,
                        picker=True, pickradius=4, zorder=3)

        def hit(event):
            cont, ind = sc.contains(event)
            return ind["ind"][0] if cont else None

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

    # Spectral class legend — default path only (legend_filter builds its own
    # pickable legend inside _legend_filter_2d).
    if not legend_filter:
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
        idx = hit(event)
        if idx is not None:
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
        idx = hit(event)
        if idx is not None:
            if on_star_click is not None:
                on_star_click(names[idx])
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
        else:
            # Clicked empty space inside the chart → clear the table selection
            # (deselect), which clears the ring on every canvas.
            if on_star_click is not None:
                on_star_click(None)
            if _sm_box.get_visible():
                _sm_box.set_visible(False)
        canvas.draw_idle()

    canvas.mpl_connect("button_press_event", _on_sm_click)

    coord_map = {s["name"]: (s[xk], s[yk]) for s in stars
                 if s.get(xk) is not None and s.get(yk) is not None}
    name_cls = {s["name"]: ((s.get("sp_type") or "")[:1].upper() or "?")
                for s in stars}
    _attach_highlight_2d(canvas, ax, coord_map, hidden=hidden, name_cls=name_cls)

    fig.tight_layout(pad=1.0)
    toolbar = NavToolbar(canvas, parent)
    return canvas, toolbar


# ── Star Map 3D ────────────────────────────────────────────────────────────────

def make_star_map_3d_canvas(parent, stars: list, title: str = "",
                            bg: str = _SPACE_BG, on_star_click=None,
                            legend_filter=False):
    """3D scatter star map with drag-to-rotate.

    stars: list of dicts {name, color, ly, x, y, z}.
    First star is treated as the origin/center (highlighted with a star marker).
    Returns (canvas, toolbar, ax) — caller uses ax to bind viewpoint preset buttons.
    """
    import matplotlib as _mpl
    _mpl.rcParams['axes3d.mouserotationstyle'] = 'azel'
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 — registers 3d projection

    xs     = [s["x"]     for s in stars]
    ys     = [s["y"]     for s in stars]
    zs     = [s["z"]     for s in stars]
    colors = [s["color"] for s in stars]
    names  = [s["name"]  for s in stars]
    sizes  = [80 if i == 0 else 12 for i in range(len(stars))]

    fig = Figure(figsize=(6, 6), facecolor=bg)
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor(bg)
    fig.patch.set_facecolor(bg)

    # Body scatter + hit-test. Default: a single scatter (all stars, incl. the
    # centre at index 0). With legend_filter (O16/CP3), one PathCollection per
    # spectral class + a pickable legend; hit(event) skips legend-hidden classes.
    hidden = set()
    if legend_filter:
        sc = None
        hit = _legend_filter_3d(
            canvas, ax, xs, ys, zs, colors,
            [s.get("sp_type", "") for s in stars], sizes,
            scatter_kw=dict(alpha=0.85, depthshade=True, zorder=3),
            legend_kw=dict(loc="upper left", fontsize=7, framealpha=0.85,
                           labelcolor="#333333", facecolor="#ffffff",
                           edgecolor="#aaaaaa"),
            hidden=hidden,
        )
    else:
        sc = ax.scatter(xs, ys, zs, c=colors, s=sizes, alpha=0.85,
                        depthshade=True, picker=True, pickradius=5, zorder=3)

        def hit(event):
            cont, ind = sc.contains(event)
            return ind["ind"][0] if cont else None

    # Highlight center star with a star marker
    ax.scatter([xs[0]], [ys[0]], [zs[0]], c=[colors[0]], s=100,
               marker="*", zorder=5, edgecolors="#333333", linewidths=0.5,
               depthshade=False)

    ax.set_xlabel("X (ly)", color=_LABEL_CLR, fontsize=9)
    ax.set_ylabel("Y (ly)", color=_LABEL_CLR, fontsize=9)
    ax.set_zlabel("Z (ly)", color=_LABEL_CLR, fontsize=9)
    ax.tick_params(axis="x", colors=_LABEL_CLR, labelsize=7)
    ax.tick_params(axis="y", colors=_LABEL_CLR, labelsize=7)
    ax.tick_params(axis="z", colors=_LABEL_CLR, labelsize=7)
    ax.set_title(title, color=_LABEL_CLR, fontsize=10, pad=8)

    for axis in [ax.xaxis, ax.yaxis, ax.zaxis]:
        axis.pane.fill = False
        axis.pane.set_edgecolor(_GRID_CLR)
    ax.grid(True, color=_GRID_CLR, linewidth=0.4, linestyle=":")
    ax.view_init(elev=30, azim=-60)

    # Spectral class legend — default path only (legend_filter builds its own
    # pickable legend inside _legend_filter_3d).
    if not legend_filter:
        seen = {}
        for s in stars:
            cls = (s["sp_type"][0].upper() if s.get("sp_type") else "?")
            if cls not in seen:
                seen[cls] = s["color"]
        handles = [mpatches.Patch(color=c, label=f"Class {k}")
                   for k, c in sorted(seen.items()) if k != "?"]
        if handles:
            ax.legend(handles=handles, loc="upper left", fontsize=7,
                      framealpha=0.85, labelcolor="#333333",
                      facecolor="#ffffff", edgecolor="#aaaaaa")

    # Hover tooltip — fixed top-right so it doesn't overlap the upper-left legend
    hover_text = ax.text2D(0.98, 0.97, "", transform=ax.transAxes,
                           fontsize=8, color=_LABEL_CLR, va="top", ha="right",
                           bbox=dict(boxstyle="round,pad=0.3", fc="#f8f8f0",
                                     ec="#2266cc", lw=0.8, alpha=0.9),
                           visible=False, zorder=10)

    def _on_motion(event):
        if event.inaxes != ax:
            if hover_text.get_visible():
                hover_text.set_visible(False)
                canvas.draw_idle()
            return
        idx = hit(event)
        if idx is not None:
            ly_val = stars[idx].get("ly", 0)
            hover_text.set_text(f"{names[idx]}\n{ly_val:.2f} ly")
            hover_text.set_visible(True)
        else:
            if hover_text.get_visible():
                hover_text.set_visible(False)
        canvas.draw_idle()

    canvas.mpl_connect("motion_notify_event", _on_motion)

    # Scroll-wheel zoom — matplotlib 3.10 removed the native Axes3D scroll handler
    def _on_scroll(event):
        if event.inaxes != ax:
            return
        scale = 0.9 if event.button == "up" else 1.0 / 0.9
        ax._zoom_data_limits(scale, scale, scale)
        canvas.draw_idle()

    canvas.mpl_connect("scroll_event", _on_scroll)

    # Click info box — fixed bottom-left corner
    info_text = ax.text2D(0.02, 0.02, "", transform=ax.transAxes,
                          fontsize=8, color=_LABEL_CLR,
                          bbox=dict(boxstyle="round,pad=0.4", fc=bg,
                                    ec=_GRID_CLR, lw=0.8, alpha=0.9),
                          visible=False, zorder=10)

    # Press tracking so a deselect (empty-space click) is distinguished from a
    # rotate-drag: clearing happens on release only when the pointer didn't move.
    _press = {"xy": None, "empty": False}

    def _on_click(event):
        if event.inaxes is not ax or event.xdata is None:
            _press["xy"] = None
            if info_text.get_visible():
                info_text.set_visible(False)
                canvas.draw_idle()
            return
        _press["xy"] = (event.x, event.y)
        idx = hit(event)
        _press["empty"] = idx is None
        if idx is not None:
            if on_star_click is not None:
                on_star_click(names[idx])
            s     = stars[idx]
            desig = (s.get("desig") or "").strip()
            sp    = (s.get("sp_type") or "").strip()
            dist  = s.get("ly", s.get("Distance", 0.0))
            lines = [names[idx]]
            if desig:
                lines.append(f"  Designations : {desig}")
            if sp:
                lines.append(f"  Spectral Type: {sp}")
            if dist:
                lines.append(f"  Distance     : {dist:.4f} ly")
            info_text.set_text("\n".join(lines))
            info_text.set_visible(True)
        elif info_text.get_visible():
            info_text.set_visible(False)
        canvas.draw_idle()

    def _on_release(event):
        # Empty-space click (not a rotate-drag) → clear the table selection
        # (deselect). A drag moves the pointer, so compare press vs release px.
        press = _press["xy"]
        empty = _press["empty"]
        _press["xy"] = None
        if press is None or not empty or on_star_click is None:
            return
        if (event.x is not None and abs(event.x - press[0]) <= 3
                and abs(event.y - press[1]) <= 3):
            on_star_click(None)

    canvas.mpl_connect("button_release_event", _on_release)

    canvas.mpl_connect("button_press_event", _on_click)

    coord_map = {s["name"]: (s["x"], s["y"], s["z"]) for s in stars
                 if s.get("x") is not None and s.get("y") is not None
                 and s.get("z") is not None}
    name_cls = {s["name"]: ((s.get("sp_type") or "")[:1].upper() or "?")
                for s in stars}
    _attach_highlight_3d(canvas, ax, coord_map, hidden=hidden, name_cls=name_cls)

    fig.tight_layout(pad=1.0)
    toolbar = NavToolbar(canvas, parent)
    _disable_zoom_rect(toolbar)
    toolbar.push_current()   # seed nav stack so Home can restore initial zoom/angles
    return canvas, toolbar, ax


# ── Star Chart (labeled 2D X-Y projection, dark theme) ────────────────────────

# Dark navy palette mirroring generate_star_map_html.py.
_SC_FIG_BG       = "#070b18"
_SC_PLOT_BG      = "#0b1020"
_SC_GRID_MINOR   = "#1a2448"
_SC_GRID_MAJOR   = "#2a3868"
_SC_AXIS         = "#4a6a99"
_SC_TICK_LBL     = "#8aa4d4"
_SC_AXIS_TITLE   = "#cfd8ec"
_SC_RING         = "#3a5a8a"
_SC_RING_LBL     = "#6f8fc4"
_SC_STAR_LBL     = "#e6ecf7"
_SC_SOL          = "#FFD700"
_SC_ROUTE        = "#7fd3ff"   # dashed ordered-route legs (I1/I2)
_SC_MST          = "#7fe0a0"   # solid MST edges (I3)
_SC_ROUTE_LBL    = "#cfe3ff"   # per-segment route labels


def _star_chart_steps(limit_ly: float):
    """Pick (minor, major) grid spacing and ring step based on the axis range.

    Mirrors the HTML script's 1/5 ly default and scales sensibly upward."""
    if limit_ly <= 20:
        minor, major = 1.0, 5.0
    elif limit_ly <= 50:
        minor, major = 2.0, 10.0
    elif limit_ly <= 100:
        minor, major = 5.0, 25.0
    else:
        minor, major = 10.0, 50.0
    return minor, major


# ── O17: travel-time isochrone rings (Star Chart 2D + 3D) ─────────────────────
# When a caller passes isochrone={"ly_hr": float, "label_unit": str} the chart's
# distance rings are replaced by travel-time contours at d = ly_hr × t for the
# nice time steps below (week … 50 yr). ×c → ly/hr uses the canonical hours/year.
_ISO_HOURS_PER_YEAR  = 8765.8128            # Julian year (365.25 × 24)
_ISO_HOURS_PER_DAY   = 24.0
_ISO_HOURS_PER_WEEK  = 168.0
_ISO_HOURS_PER_MONTH = _ISO_HOURS_PER_YEAR / 12.0
# Hour/day steps at the fine end so fast velocities (where even "1 week" overshoots
# a small chart) still get rings; year steps at the coarse end for slow velocities.
_ISO_STEPS = [
    ("1 hour",   1.0),
    ("6 hours",  6.0),
    ("1 day",    _ISO_HOURS_PER_DAY),
    ("3 days",   3 * _ISO_HOURS_PER_DAY),
    ("1 week",   _ISO_HOURS_PER_WEEK),
    ("1 month",  _ISO_HOURS_PER_MONTH),
    ("3 months", 3 * _ISO_HOURS_PER_MONTH),
    ("6 months", 6 * _ISO_HOURS_PER_MONTH),
    ("1 year",   _ISO_HOURS_PER_YEAR),
    ("2 years",  2 * _ISO_HOURS_PER_YEAR),
    ("5 years",  5 * _ISO_HOURS_PER_YEAR),
    ("10 years", 10 * _ISO_HOURS_PER_YEAR),
    ("25 years", 25 * _ISO_HOURS_PER_YEAR),
    ("50 years", 50 * _ISO_HOURS_PER_YEAR),
]
_ISO_MIN_RING_FRAC = 0.05                   # drop rings smaller than 5% of the range


def _isochrone_rings(ly_hr, limit_ly):
    """Travel-time rings for a velocity in ly/hr → [(radius_ly, duration_label), …].

    Rings are the nice time steps (`_ISO_STEPS`) whose radius (= ly_hr × hours)
    fits within limit_ly; rings smaller than 5% of the range are dropped (too
    small to read / clutter the centre) and if more than 6 remain the 6 largest
    are kept. A non-positive / non-finite velocity — or a velocity so fast that
    even the 1-hour ring overshoots the range — yields no rings (the panel then
    shows distance rings and flags the out-of-range velocity in the status bar)."""
    if ly_hr is None or not math.isfinite(ly_hr) or ly_hr <= 0 or limit_ly <= 0:
        return []
    min_r = limit_ly * _ISO_MIN_RING_FRAC
    rings = [(ly_hr * hrs, lbl) for lbl, hrs in _ISO_STEPS
             if min_r <= ly_hr * hrs <= limit_ly * 1.02]
    if len(rings) > 6:
        rings = rings[-6:]
    return rings


def make_star_chart_canvas(parent, stars: list, limit_ly: float, routes=None,
                           on_star_click=None, legend_filter=False, isochrone=None):
    """Labeled 2D X-Y star chart in the dark navy style of stars_within_15ly.html.

    stars:     list of dicts {name, color, sp_type, ly, x, y, z, desig}.
               The first entry is treated as the origin/center star (highlighted).
    limit_ly:  axis range ± value (e.g. 15 → axes span -15..+15 ly).
    routes:    optional list of {x1,y1,z1,x2,y2,z2,label,style} edge dicts
               (Phase I route overlay) — dashed for ordered legs, solid for MST
               edges; per-segment labels follow the same zoom-driven visibility
               as the star labels.

    Stars whose |X| or |Y| > limit_ly are excluded (they're in the sphere but
    off the projected square — same rule as generate_star_map_html.py).

    Provides Map 3D-style interactivity: hover tooltip, click info box, and
    scroll-wheel zoom. The standard matplotlib toolbar (Home/Pan/Zoom) is also
    returned so users can pan/zoom precisely.

    Returns (canvas, toolbar).
    """
    minor_step, major_step = _star_chart_steps(limit_ly)
    # Labels are only shown when the visible half-range is ≤ LABEL_MAX_LY.
    # Beyond that the dots/text cluster too tightly to read. The same threshold
    # drives the initial visibility AND the zoom callback below.
    LABEL_MAX_LY = 15.0
    initial_show_labels = limit_ly <= LABEL_MAX_LY

    fig = Figure(figsize=(8, 8), facecolor=_SC_FIG_BG)
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111, facecolor=_SC_PLOT_BG)
    ax.set_aspect("equal", adjustable="box", anchor="C")
    ax.set_xlim(-limit_ly, limit_ly)
    ax.set_ylim(-limit_ly, limit_ly)

    # Minor + major grid lines.
    def _ticks(step):
        n = int(math.floor(limit_ly / step))
        return [i * step for i in range(-n, n + 1)]

    minor_ticks = _ticks(minor_step)
    major_ticks = _ticks(major_step)
    for v in minor_ticks:
        if v in major_ticks:
            continue
        ax.axvline(v, color=_SC_GRID_MINOR, linewidth=0.4, zorder=1)
        ax.axhline(v, color=_SC_GRID_MINOR, linewidth=0.4, zorder=1)
    for v in major_ticks:
        if v == 0:
            continue
        ax.axvline(v, color=_SC_GRID_MAJOR, linewidth=0.8, zorder=1)
        ax.axhline(v, color=_SC_GRID_MAJOR, linewidth=0.8, zorder=1)

    # Origin axes.
    ax.axvline(0, color=_SC_AXIS, linewidth=1.2, zorder=2)
    ax.axhline(0, color=_SC_AXIS, linewidth=1.2, zorder=2)

    # Major-tick numeric labels along the origin axes.
    for v in major_ticks:
        if v == 0:
            continue
        ax.text(v, -limit_ly * 0.018, f"{int(v):+d}",
                color=_SC_TICK_LBL, fontsize=7, ha="center", va="top", zorder=4,
                clip_on=True)
        ax.text(-limit_ly * 0.012, v, f"{int(v):+d}",
                color=_SC_TICK_LBL, fontsize=7, ha="right", va="center", zorder=4,
                clip_on=True)

    ax.text(limit_ly * 0.985, -limit_ly * 0.04, "X (ly) →",
            color=_SC_AXIS_TITLE, fontsize=9, ha="right", va="top", zorder=4,
            clip_on=True)
    ax.text(limit_ly * 0.018, limit_ly * 0.985, "↑ Y (ly)",
            color=_SC_AXIS_TITLE, fontsize=9, ha="left", va="top", zorder=4,
            clip_on=True)

    # Rings: distance rings every `major_step` ly out to limit (default), OR
    # travel-time isochrone rings when isochrone={"ly_hr","label_unit"} is given
    # (O17). Same dashed-circle styling; isochrone labels read "6 months @ …".
    iso_rings = (_isochrone_rings(isochrone.get("ly_hr"), limit_ly)
                 if isochrone else [])
    if iso_rings:
        iso_unit = isochrone.get("label_unit") or f"{isochrone['ly_hr']:.4f} ly/hr"
        for r, dur in iso_rings:
            ax.add_patch(Circle((0, 0), r, fill=False,
                                edgecolor=_SC_RING, linewidth=0.6,
                                linestyle=(0, (4, 6)), alpha=0.85, zorder=2))
            ax.text(r - limit_ly * 0.005, -limit_ly * 0.008, f"{dur} @ {iso_unit}",
                    color=_SC_RING_LBL, fontsize=7, ha="right", va="top", zorder=3,
                    clip_on=True)
    else:
        n_rings = int(math.floor(limit_ly / major_step))
        for i in range(1, n_rings + 1):
            r = i * major_step
            ax.add_patch(Circle((0, 0), r, fill=False,
                                edgecolor=_SC_RING, linewidth=0.6,
                                linestyle=(0, (4, 6)), alpha=0.85, zorder=2))
            ax.text(r - limit_ly * 0.005, -limit_ly * 0.008, f"{int(r)} ly",
                    color=_SC_RING_LBL, fontsize=7, ha="right", va="top", zorder=3,
                    clip_on=True)

    # Star plot — exclude points outside the projected square.
    plotted = []
    for s in stars:
        x, y = s.get("x"), s.get("y")
        if x is None or y is None:
            continue
        if abs(x) > limit_ly or abs(y) > limit_ly:
            continue
        plotted.append(s)

    if not plotted:
        fig.subplots_adjust(left=0.04, right=0.96, top=0.96, bottom=0.04)
        _attach_highlight_2d(canvas, ax, {})
        return canvas, NavToolbar(canvas, parent)

    xs     = [s["x"]     for s in plotted]
    ys     = [s["y"]     for s in plotted]
    colors = [s["color"] for s in plotted]
    names  = [s["name"]  for s in plotted]

    # Origin/center star (first entry) painted as a gold star marker.
    center = plotted[0]
    is_center_origin = (abs(center["x"]) < 1e-6 and abs(center["y"]) < 1e-6
                        and abs(center.get("z", 0)) < 1e-6)
    sol_label = None
    if is_center_origin:
        ax.scatter([0], [0], c=_SC_SOL, s=140, marker="*",
                   edgecolors="#fff8a0", linewidths=1.0, zorder=6)
        # Fixed PIXEL offset keeps the label glued to the ★ at any zoom level
        # (a data-space offset drifts off the marker as you zoom in).
        sol_label = ax.annotate(
            f"{center['name']} (Z={center.get('z', 0.0):+.3f})",
            xy=(0, 0), xytext=(6.0, 5.0), textcoords="offset points",
            color=_SC_SOL, fontsize=9, fontweight="600",
            ha="left", va="bottom", zorder=7, annotation_clip=True, clip_on=True,
        )
        sol_label.set_visible(initial_show_labels)
        body_stars = plotted[1:]
        body_xs    = xs[1:]
        body_ys    = ys[1:]
        body_cols  = colors[1:]
        body_names = names[1:]
    else:
        body_stars, body_xs, body_ys = plotted, xs, ys
        body_cols, body_names = colors, names

    # O16: per-class split state (shared with the legend pick handler + the
    # zoom-driven label logic below). Empty/unused on the default path.
    hidden = set()
    _label_state = {"shown": initial_show_labels}
    label_groups = {}   # spectral class -> [label artists], for legend filtering

    # Per-star labels "Name (Z=±X.XXX)". Anchored to each star with a fixed
    # PIXEL offset (textcoords="offset points") so the label stays glued to its
    # dot at any zoom level — a data-space offset drifts apart on zoom-in.
    # Collision-nudging pushes initially-overlapping labels downward in screen
    # space (points). Visibility is governed by the xlim/ylim callback below
    # (shown when zoomed in past LABEL_MAX_LY, hidden on zoom-out / Home).
    LABEL_DX_PT, LABEL_DY_PT, NUDGE_PT = 6.0, 5.0, 11.0
    nudge_x_tol = limit_ly * 0.10   # data-space proximity ⇒ on-screen overlap
    nudge_y_tol = limit_ly * 0.04

    star_labels = []  # collected for the zoom-callback to toggle
    placed = []       # (x, y) data anchors already placed
    for s, x, y in zip(body_stars, body_xs, body_ys):
        nm = s["name"]
        for prefix in ("NAME ", "* ", "V* "):
            if nm.startswith(prefix):
                nm = nm[len(prefix):]
                break
        z = s.get("z", 0.0)
        lbl = f"{nm} (Z={z:+.3f})"
        dy_pt = LABEL_DY_PT
        for px, py in placed:
            if abs(x - px) < nudge_x_tol and abs(y - py) < nudge_y_tol:
                dy_pt -= NUDGE_PT
        placed.append((x, y))
        txt = ax.annotate(
            lbl, xy=(x, y), xytext=(LABEL_DX_PT, dy_pt),
            textcoords="offset points",
            color=_SC_STAR_LBL, fontsize=7, ha="left", va="bottom",
            zorder=8, annotation_clip=True, clip_on=True,
        )
        txt.set_path_effects([_path_stroke(linewidth=2.5, color=_SC_PLOT_BG)])
        txt.set_visible(initial_show_labels)
        cls = (s.get("sp_type") or "")[:1].upper() or "?"
        txt._o16_cls = cls
        label_groups.setdefault(cls, []).append(txt)
        star_labels.append(txt)

    # Route overlay (Phase I) — dashed ordered legs (I1/I2) or solid MST edges
    # (I3), drawn under the dots. Lines stay visible at all zooms; the small
    # per-segment labels follow the same zoom-driven visibility as star labels.
    for e in (routes or []):
        solid = e.get("style") == "solid"
        ax.plot([e["x1"], e["x2"]], [e["y1"], e["y2"]],
                color=(_SC_MST if solid else _SC_ROUTE), linewidth=1.6,
                linestyle="-" if solid else "--", alpha=0.9, zorder=3)
        lbl = e.get("label")
        if lbl:
            mx, my = (e["x1"] + e["x2"]) / 2.0, (e["y1"] + e["y2"]) / 2.0
            rtxt = ax.annotate(
                str(lbl), xy=(mx, my), xytext=(0, 0), textcoords="offset points",
                color=_SC_ROUTE_LBL, fontsize=7, ha="center", va="center",
                zorder=9, annotation_clip=True, clip_on=True,
            )
            rtxt.set_path_effects([_path_stroke(linewidth=2.5, color=_SC_PLOT_BG)])
            rtxt.set_visible(initial_show_labels)
            star_labels.append(rtxt)

    # Tick spines/border styling — hide the tick numbers (we draw our own along
    # the origin axes) but keep a faint border to frame the plot.
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_edgecolor(_SC_GRID_MAJOR)
        spine.set_linewidth(0.8)

    # Body-star scatter + hit-test. On the default path a single scatter; with
    # legend_filter, one PathCollection per spectral class + a pickable dark-theme
    # legend (O16). `hit(event)` returns the body-index under the cursor, skipping
    # legend-hidden classes.
    if legend_filter:
        sc = None
        hit = _legend_filter_2d(
            canvas, ax, body_xs, body_ys, body_cols,
            [s.get("sp_type", "") for s in body_stars],
            [36] * len(body_stars),
            scatter_kw=dict(edgecolors="#000000", linewidths=0.4, zorder=5),
            legend_kw=dict(loc="upper right", fontsize=7, framealpha=0.85,
                           labelcolor=_SC_STAR_LBL, facecolor=_SC_PLOT_BG,
                           edgecolor=_SC_GRID_MAJOR),
            hidden=hidden, label_groups=label_groups, label_state=_label_state,
        )
    else:
        sc = ax.scatter(body_xs, body_ys, c=body_cols, s=36,
                        edgecolors="#000000", linewidths=0.4,
                        picker=True, pickradius=5, zorder=5)

        def hit(event):
            cont, ind = sc.contains(event)
            return ind["ind"][0] if cont else None

    # Hover tooltip (offset annotation, follows the cursor).
    annot = ax.annotate(
        "", xy=(0, 0), xytext=(12, 12), textcoords="offset points",
        bbox=dict(boxstyle="round,pad=0.3", fc="#f8f8f0", ec="#2266cc",
                  lw=0.8, alpha=0.92),
        arrowprops=dict(arrowstyle="->", color="#2266cc", lw=0.8),
        color="#222222", fontsize=7, zorder=20,
    )
    annot.set_visible(False)

    def _on_motion(event):
        if event.inaxes != ax:
            if annot.get_visible():
                annot.set_visible(False)
                canvas.draw_idle()
            return
        idx = hit(event)
        if idx is not None:
            s = body_stars[idx]
            annot.xy = (body_xs[idx], body_ys[idx])
            annot.set_text(f"{body_names[idx]}\n{s.get('ly', 0):.3f} ly")
            annot.set_visible(True)
        elif annot.get_visible():
            annot.set_visible(False)
        canvas.draw_idle()

    canvas.mpl_connect("motion_notify_event", _on_motion)

    # Click info box — bottom-left corner, dismiss by clicking empty space.
    info_box = ax.text(
        0.02, 0.02, "",
        transform=ax.transAxes,
        color="#222222", fontsize=7, va="bottom", ha="left",
        multialignment="left",
        bbox=dict(boxstyle="round,pad=0.45", fc="#f8f8f0", ec="#2266cc",
                  lw=1.0, alpha=0.93),
        zorder=21, visible=False,
    )

    def _on_click(event):
        if event.inaxes is not ax or event.xdata is None:
            if info_box.get_visible():
                info_box.set_visible(False)
                canvas.draw_idle()
            return
        idx = hit(event)
        if idx is not None:
            if on_star_click is not None:
                on_star_click(body_names[idx])
            s     = body_stars[idx]
            desig = (s.get("desig") or "").strip()
            sp    = (s.get("sp_type") or "").strip()
            lines = [body_names[idx]]
            if desig:
                lines.append(f"  Designations : {desig}")
            if sp:
                lines.append(f"  Spectral Type: {sp}")
            lines.append(f"  Distance     : {s.get('ly', 0.0):.4f} ly")
            lines.append(f"  X / Y / Z    : "
                         f"{s['x']:+.3f}, {s['y']:+.3f}, {s.get('z', 0.0):+.3f} ly")
            info_box.set_text("\n".join(lines))
            info_box.set_visible(True)
        else:
            # Clicked empty space inside the chart → clear the table selection
            # (deselect), which clears the ring on every canvas.
            if on_star_click is not None:
                on_star_click(None)
            if info_box.get_visible():
                info_box.set_visible(False)
        canvas.draw_idle()

    canvas.mpl_connect("button_press_event", _on_click)

    # Scroll-wheel zoom around the cursor.
    def _on_scroll(event):
        if event.inaxes is not ax or event.xdata is None:
            return
        scale = 0.9 if event.button == "up" else 1.0 / 0.9
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        cx, cy = event.xdata, event.ydata
        ax.set_xlim(cx + (x0 - cx) * scale, cx + (x1 - cx) * scale)
        ax.set_ylim(cy + (y0 - cy) * scale, cy + (y1 - cy) * scale)
        canvas.draw_idle()

    canvas.mpl_connect("scroll_event", _on_scroll)

    # Zoom-driven label visibility — recomputed on every xlim/ylim change
    # (covers toolbar zoom, scroll-wheel zoom, pan, and Home reset). A label whose
    # class is legend-hidden (O16) stays hidden even when zoomed in. `_label_state`
    # is defined above (shared with the legend pick handler).
    def _refresh_label_visibility(_event_ax=None):
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        half_range = max((x1 - x0) / 2.0, (y1 - y0) / 2.0)
        should_show = half_range <= LABEL_MAX_LY
        if should_show == _label_state["shown"]:
            return
        _label_state["shown"] = should_show
        for txt in star_labels:
            cls = getattr(txt, "_o16_cls", None)
            txt.set_visible(should_show and (cls is None or cls not in hidden))
        if sol_label is not None:
            sol_label.set_visible(should_show)
        canvas.draw_idle()

    ax.callbacks.connect("xlim_changed", _refresh_label_visibility)
    ax.callbacks.connect("ylim_changed", _refresh_label_visibility)

    coord_map = {s["name"]: (s["x"], s["y"]) for s in plotted}
    name_cls = {s["name"]: ((s.get("sp_type") or "")[:1].upper() or "?")
                for s in plotted}
    _attach_highlight_2d(canvas, ax, coord_map, hidden=hidden, name_cls=name_cls)

    # Symmetric margins keep the (aspect=equal, anchor=C) square axes truly
    # centered in the figure horizontally and vertically.
    fig.subplots_adjust(left=0.04, right=0.96, top=0.96, bottom=0.04)
    toolbar = NavToolbar(canvas, parent)
    _shrink_toolbar(toolbar)
    toolbar.push_current()   # seed nav stack so Home restores the initial view
    return canvas, toolbar


# ── Star Chart 3D (labeled 3D scatter, dark theme) ────────────────────────────

def make_star_chart_3d_canvas(parent, stars: list, limit_ly: float, routes=None,
                              on_star_click=None, legend_filter=False, isochrone=None):
    """3D companion to make_star_chart_canvas.

    Same dark navy palette, spectral-class star dots, gold ★ origin marker,
    faint wireframe reference spheres at the same intervals the 2D chart uses
    for rings, and per-star "Name (Z=±X.XXX)" labels that appear when the user
    zooms in (visible half-range ≤ 15 ly along the dominant axis) and disappear
    on Home / zoom-out.

    Returns (canvas, toolbar, ax) — caller binds viewpoint preset buttons via ax.
    """
    import matplotlib as _mpl
    _mpl.rcParams['axes3d.mouserotationstyle'] = 'azel'
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 — registers 3d projection

    _, major_step = _star_chart_steps(limit_ly)
    LABEL_MAX_LY = 15.0
    initial_show_labels = limit_ly <= LABEL_MAX_LY

    fig = Figure(figsize=(8, 8), facecolor=_SC_FIG_BG)
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor(_SC_PLOT_BG)
    fig.patch.set_facecolor(_SC_FIG_BG)

    ax.set_xlim(-limit_ly, limit_ly)
    ax.set_ylim(-limit_ly, limit_ly)
    ax.set_zlim(-limit_ly, limit_ly)

    # Enlarge the 3D content within the axes box (matplotlib 3.6+ `zoom` arg).
    # Falls back to a no-op on older versions where `zoom` isn't supported.
    try:
        ax.set_box_aspect((1, 1, 1), zoom=1.35)
    except TypeError:
        ax.set_box_aspect((1, 1, 1))

    # Hide the cube — no pane fills, no pane edges, no grid lines. The
    # wireframe distance spheres provide all the depth/orientation reference.
    # Tick labels and X/Y/Z axis labels are kept for numeric scale reference.
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        try:
            axis.pane.fill = False
            axis.pane.set_edgecolor((0, 0, 0, 0))
        except Exception:
            pass
    ax.grid(False)
    ax.tick_params(axis="x", colors=_SC_TICK_LBL, labelsize=7)
    ax.tick_params(axis="y", colors=_SC_TICK_LBL, labelsize=7)
    ax.tick_params(axis="z", colors=_SC_TICK_LBL, labelsize=7)
    ax.set_xlabel("X (ly)", color=_SC_AXIS_TITLE, fontsize=9)
    ax.set_ylabel("Y (ly)", color=_SC_AXIS_TITLE, fontsize=9)
    ax.set_zlabel("Z (ly)", color=_SC_AXIS_TITLE, fontsize=9)
    ax.view_init(elev=30, azim=-60)

    # Faint wireframe reference spheres: distance spheres every `major_step` ly
    # (default), OR travel-time isochrone spheres when isochrone={"ly_hr",…} is
    # given (O17). Each isochrone sphere gets a "6 months @ …" label on the +X axis.
    import numpy as _np
    iso_rings = (_isochrone_rings(isochrone.get("ly_hr"), limit_ly)
                 if isochrone else [])
    sphere_radii = [r for r, _dur in iso_rings] if iso_rings else [
        i * major_step for i in range(1, int(math.floor(limit_ly / major_step)) + 1)]
    if sphere_radii:
        _u = _np.linspace(0, 2 * _np.pi, 28)
        _v = _np.linspace(0, _np.pi, 14)
        _su = _np.sin(_v)
        _cu = _np.cos(_v)
        _x_unit = _np.outer(_np.cos(_u), _su)
        _y_unit = _np.outer(_np.sin(_u), _su)
        _z_unit = _np.outer(_np.ones_like(_u), _cu)
        for r in sphere_radii:
            ax.plot_wireframe(
                _x_unit * r, _y_unit * r, _z_unit * r,
                color=_SC_RING, linewidth=0.4, alpha=0.18, zorder=1,
            )
    if iso_rings:
        iso_unit = isochrone.get("label_unit") or f"{isochrone['ly_hr']:.4f} ly/hr"
        for r, dur in iso_rings:
            ax.text(r, 0, 0, f"{dur} @ {iso_unit}", color=_SC_RING_LBL,
                    fontsize=6, ha="left", va="bottom", zorder=3)

    # Filter stars to within the cubic axis range (a star may be inside the
    # sphere but outside one of the axis ranges — match the 2D chart's rule).
    plotted = []
    for s in stars:
        x, y, z = s.get("x"), s.get("y"), s.get("z")
        if x is None or y is None or z is None:
            continue
        if abs(x) > limit_ly or abs(y) > limit_ly or abs(z) > limit_ly:
            continue
        plotted.append(s)

    if not plotted:
        _attach_highlight_3d(canvas, ax, {})
        toolbar = NavToolbar(canvas, parent)
        _shrink_toolbar(toolbar)
        _disable_zoom_rect(toolbar)
        return canvas, toolbar, ax

    xs     = [s["x"]     for s in plotted]
    ys     = [s["y"]     for s in plotted]
    zs     = [s["z"]     for s in plotted]
    colors = [s["color"] for s in plotted]
    names  = [s["name"]  for s in plotted]

    # Center star (first entry) drawn as a gold ★; the rest as small dots.
    center = plotted[0]
    is_center_origin = (abs(center["x"]) < 1e-6 and abs(center["y"]) < 1e-6
                        and abs(center.get("z", 0)) < 1e-6)
    sol_label = None
    if is_center_origin:
        ax.scatter([0], [0], [0], c=_SC_SOL, s=160, marker="*",
                   edgecolors="#fff8a0", linewidths=1.0, zorder=6,
                   depthshade=False)
        # Anchor the label at the ★'s exact point (left/bottom aligned) so it
        # tracks the marker on rotation and zoom instead of drifting on a fixed
        # data-space offset.
        sol_label = ax.text(
            0.0, 0.0, 0.0,
            f"{center['name']} (Z={center.get('z', 0.0):+.3f})",
            color=_SC_SOL, fontsize=9, fontweight="600", zorder=7,
            ha="left", va="bottom",
        )
        sol_label.set_visible(initial_show_labels)
        body_stars = plotted[1:]
        body_xs, body_ys, body_zs = xs[1:], ys[1:], zs[1:]
        body_cols, body_names = colors[1:], names[1:]
    else:
        body_stars = plotted
        body_xs, body_ys, body_zs = xs, ys, zs
        body_cols, body_names = colors, names

    # O16/CP3 per-class split state (shared with the legend pick handler + the
    # zoom-driven label logic below). Empty/unused on the default path.
    hidden = set()
    _label_state = {"shown": initial_show_labels}
    label_groups = {}   # spectral class -> [label artists], for legend filtering

    # Body scatter + hit-test. Default: a single scatter. With legend_filter
    # (O16/CP3), one PathCollection per spectral class + a pickable legend;
    # hit(event) returns the body-index under the cursor, skipping hidden classes.
    if legend_filter:
        sc = None
        hit = _legend_filter_3d(
            canvas, ax, body_xs, body_ys, body_zs, body_cols,
            [s.get("sp_type", "") for s in body_stars],
            [28] * len(body_stars),
            scatter_kw=dict(edgecolors="#000000", linewidths=0.4, alpha=0.92,
                            depthshade=True, zorder=5),
            legend_kw=dict(loc="upper left", fontsize=7, framealpha=0.85,
                           labelcolor=_SC_STAR_LBL, facecolor=_SC_PLOT_BG,
                           edgecolor=_SC_GRID_MAJOR),
            hidden=hidden, label_groups=label_groups, label_state=_label_state,
        )
    else:
        sc = ax.scatter(body_xs, body_ys, body_zs, c=body_cols, s=28,
                        edgecolors="#000000", linewidths=0.4, alpha=0.92,
                        depthshade=True, picker=True, pickradius=5, zorder=5)

        def hit(event):
            cont, ind = sc.contains(event)
            return ind["ind"][0] if cont else None

    # Per-star labels anchored at each star's exact 3D point (left/bottom
    # aligned) so the label tracks its dot precisely on rotation and zoom — a
    # fixed data-space offset drifts off the dot when the view changes.
    # Visibility is toggled by the zoom callback; a legend-hidden class (O16)
    # keeps its labels hidden via the `_o16_cls` tag + the `hidden` set.
    star_labels = []
    for s, x, y, z in zip(body_stars, body_xs, body_ys, body_zs):
        nm = s["name"]
        for prefix in ("NAME ", "* ", "V* "):
            if nm.startswith(prefix):
                nm = nm[len(prefix):]
                break
        lbl = f"{nm} (Z={s.get('z', 0.0):+.3f})"
        txt = ax.text(x, y, z, lbl, color=_SC_STAR_LBL, fontsize=7, zorder=8,
                      ha="left", va="bottom")
        txt.set_path_effects([_path_stroke(linewidth=2.0, color=_SC_PLOT_BG)])
        txt.set_visible(initial_show_labels)
        cls = (s.get("sp_type") or "")[:1].upper() or "?"
        txt._o16_cls = cls
        label_groups.setdefault(cls, []).append(txt)
        star_labels.append(txt)

    # Route overlay (Phase I) — dashed ordered legs / solid MST edges in 3D.
    for e in (routes or []):
        solid = e.get("style") == "solid"
        ax.plot([e["x1"], e["x2"]], [e["y1"], e["y2"]], [e["z1"], e["z2"]],
                color=(_SC_MST if solid else _SC_ROUTE), linewidth=1.6,
                linestyle="-" if solid else "--", alpha=0.9, zorder=4)
        lbl = e.get("label")
        if lbl:
            mx = (e["x1"] + e["x2"]) / 2.0
            my = (e["y1"] + e["y2"]) / 2.0
            mz = (e["z1"] + e["z2"]) / 2.0
            rtxt = ax.text(mx, my, mz, str(lbl), color=_SC_ROUTE_LBL,
                           fontsize=7, zorder=9, ha="center", va="center")
            rtxt.set_path_effects([_path_stroke(linewidth=2.0, color=_SC_PLOT_BG)])
            rtxt.set_visible(initial_show_labels)
            star_labels.append(rtxt)

    # Hover tooltip (top-right text2D — stays fixed under rotation).
    hover_text = ax.text2D(
        0.98, 0.97, "", transform=ax.transAxes,
        fontsize=7, color="#222222", va="top", ha="right",
        bbox=dict(boxstyle="round,pad=0.3", fc="#f8f8f0", ec="#2266cc",
                  lw=0.8, alpha=0.92),
        visible=False, zorder=10,
    )

    def _on_motion(event):
        if event.inaxes != ax:
            if hover_text.get_visible():
                hover_text.set_visible(False)
                canvas.draw_idle()
            return
        idx = hit(event)
        if idx is not None:
            s = body_stars[idx]
            hover_text.set_text(f"{body_names[idx]}\n{s.get('ly', 0):.3f} ly")
            hover_text.set_visible(True)
        elif hover_text.get_visible():
            hover_text.set_visible(False)
        canvas.draw_idle()

    canvas.mpl_connect("motion_notify_event", _on_motion)

    # Click info box (bottom-left text2D).
    info_box = ax.text2D(
        0.02, 0.02, "", transform=ax.transAxes,
        fontsize=7, color="#222222", va="bottom", ha="left",
        multialignment="left",
        bbox=dict(boxstyle="round,pad=0.45", fc="#f8f8f0", ec="#2266cc",
                  lw=1.0, alpha=0.93),
        visible=False, zorder=11,
    )

    # Press tracking so a deselect (empty-space click) is distinguished from a
    # rotate-drag: clearing happens on release only when the pointer didn't move.
    _press = {"xy": None, "empty": False}

    def _on_click(event):
        if event.inaxes is not ax or event.xdata is None:
            _press["xy"] = None
            if info_box.get_visible():
                info_box.set_visible(False)
                canvas.draw_idle()
            return
        _press["xy"] = (event.x, event.y)
        idx = hit(event)
        _press["empty"] = idx is None
        if idx is not None:
            if on_star_click is not None:
                on_star_click(body_names[idx])
            s     = body_stars[idx]
            desig = (s.get("desig") or "").strip()
            sp    = (s.get("sp_type") or "").strip()
            lines = [body_names[idx]]
            if desig:
                lines.append(f"  Designations : {desig}")
            if sp:
                lines.append(f"  Spectral Type: {sp}")
            lines.append(f"  Distance     : {s.get('ly', 0.0):.4f} ly")
            lines.append(f"  X / Y / Z    : "
                         f"{s['x']:+.3f}, {s['y']:+.3f}, {s.get('z', 0.0):+.3f} ly")
            info_box.set_text("\n".join(lines))
            info_box.set_visible(True)
        elif info_box.get_visible():
            info_box.set_visible(False)
        canvas.draw_idle()

    def _on_release(event):
        # Empty-space click (not a rotate-drag) → clear the table selection
        # (deselect). A drag moves the pointer, so compare press vs release px.
        press = _press["xy"]
        empty = _press["empty"]
        _press["xy"] = None
        if press is None or not empty or on_star_click is None:
            return
        if (event.x is not None and abs(event.x - press[0]) <= 3
                and abs(event.y - press[1]) <= 3):
            on_star_click(None)

    canvas.mpl_connect("button_press_event", _on_click)
    canvas.mpl_connect("button_release_event", _on_release)

    # Scroll-wheel zoom — matches Map 3D's behaviour (matplotlib 3.10+ removed
    # the native Axes3D scroll handler).
    def _on_scroll(event):
        if event.inaxes != ax:
            return
        scale = 0.9 if event.button == "up" else 1.0 / 0.9
        ax._zoom_data_limits(scale, scale, scale)
        canvas.draw_idle()

    canvas.mpl_connect("scroll_event", _on_scroll)

    # Zoom-driven label visibility — for 3D we drive off the largest visible
    # half-range across X/Y/Z so any kind of zoom-in (toolbar, scroll wheel,
    # Home reset) reliably toggles the labels. A label whose class is
    # legend-hidden (O16) stays hidden even when zoomed in. `_label_state` /
    # `hidden` are defined above (shared with the legend pick handler).
    def _refresh_label_visibility(_event_ax=None):
        x0, x1 = ax.get_xlim3d()
        y0, y1 = ax.get_ylim3d()
        z0, z1 = ax.get_zlim3d()
        half_range = max((x1 - x0) / 2.0,
                         (y1 - y0) / 2.0,
                         (z1 - z0) / 2.0)
        should_show = half_range <= LABEL_MAX_LY
        if should_show == _label_state["shown"]:
            return
        _label_state["shown"] = should_show
        for txt in star_labels:
            cls = getattr(txt, "_o16_cls", None)
            txt.set_visible(should_show and (cls is None or cls not in hidden))
        if sol_label is not None:
            sol_label.set_visible(should_show)
        canvas.draw_idle()

    ax.callbacks.connect("xlim_changed", _refresh_label_visibility)
    ax.callbacks.connect("ylim_changed", _refresh_label_visibility)
    ax.callbacks.connect("zlim_changed", _refresh_label_visibility)

    # Very tight subplot margins — the axes-pane "cube" is hidden so we can
    # safely push the axes nearly to the figure edges; axis labels still fit
    # because matplotlib places them inside the axes rect, not outside.
    coord_map = {s["name"]: (s["x"], s["y"], s["z"]) for s in plotted}
    name_cls = {s["name"]: ((s.get("sp_type") or "")[:1].upper() or "?")
                for s in plotted}
    _attach_highlight_3d(canvas, ax, coord_map, hidden=hidden, name_cls=name_cls)

    fig.subplots_adjust(left=0.0, right=1.0, top=1.0, bottom=0.0)
    toolbar = NavToolbar(canvas, parent)
    _shrink_toolbar(toolbar)
    _disable_zoom_rect(toolbar)
    toolbar.push_current()
    return canvas, toolbar, ax


def _shrink_toolbar(toolbar, icon_px: int = 14, max_h: int = 22):
    """Reduce a matplotlib NavToolbar's visual footprint.

    Shrinks the icon size and caps the widget height so the toolbar takes
    less vertical room above the canvas.
    """
    from PySide6.QtCore import QSize
    toolbar.setIconSize(QSize(icon_px, icon_px))
    toolbar.setMaximumHeight(max_h)
    toolbar.setStyleSheet(
        "QToolBar { spacing: 1px; padding: 0px; margin: 0px; border: 0px; }"
        "QToolButton { padding: 1px; margin: 0px; }"
    )


def _path_stroke(linewidth: float, color: str):
    """Small wrapper around matplotlib.patheffects.withStroke for text outlines."""
    import matplotlib.patheffects as pe
    return pe.withStroke(linewidth=linewidth, foreground=color)


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


# ── Solar System Travel Diagram ────────────────────────────────────────────────

def _build_solar_travel_elements(ax, data: dict):
    """Draw planet orbits, planets, Sun, origin, destination, and travel line.

    Returns (scatter_artists, origin_pt, dest_pt) for click-to-info wiring.
    """
    import math as _math

    max_au = data["max_au"]

    # Reference orbit circles (thin dashed rings)
    for orb in data.get("planet_orbits", []):
        ax.add_patch(Circle((0, 0), orb["sma_au"],
                            fill=False, edgecolor=orb["color"],
                            linewidth=0.6, linestyle="--", alpha=0.35, zorder=1))

    # Planet dots
    planet_artists = []
    for p in data.get("planets", []):
        sc = ax.scatter([p["x"]], [p["y"]], color=p["color"],
                        s=60, zorder=4, picker=6)
        sc._body_info = p
        planet_artists.append(sc)
        # label offset: nudge away from the Sun
        r = _math.sqrt(p["x"] ** 2 + p["y"] ** 2) or 0.01
        ox_lbl = p["x"] / r * max_au * 0.04
        oy_lbl = p["y"] / r * max_au * 0.04
        ax.text(p["x"] + ox_lbl, p["y"] + oy_lbl, p["name"],
                color=_LABEL_CLR, fontsize=6.5, ha="center", va="center",
                alpha=0.85, zorder=5)

    # Sun
    ax.scatter([0], [0], color="#FFD700", s=120, marker="*", zorder=6)
    ax.text(0, max_au * 0.04, "Sun",
            color="#CC8800", fontsize=7, ha="center", va="bottom",
            alpha=0.9, zorder=7)

    # Dashed travel path line
    ox_, oy_, _ = data["origin_xyz"]
    dx_, dy_, _ = data["dest_xyz"]
    ax.plot([ox_, dx_], [oy_, dy_],
            color="#888888", linewidth=1.5, linestyle="--",
            alpha=0.75, zorder=3)

    # Origin marker
    orig_sc = ax.scatter([ox_], [oy_], color="#FF8800", s=120,
                         marker="*", zorder=8, picker=8)
    orig_sc._body_info = {"name": data["origin_name"],
                          "x": ox_, "y": oy_, "z": data["origin_xyz"][2],
                          "horizons_id": data.get("origin_id", "")}
    ax.text(ox_ + max_au * 0.04, oy_ + max_au * 0.04,
            f"Origin\n{data['origin_name']}",
            color="#FF8800", fontsize=7, ha="left", va="bottom",
            alpha=0.95, zorder=9)

    # Destination marker
    dest_sc = ax.scatter([dx_], [dy_], color="#00CCCC", s=100,
                         marker="s", zorder=8, picker=8)
    dest_sc._body_info = {"name": data["dest_name"],
                          "x": dx_, "y": dy_, "z": data["dest_xyz"][2],
                          "horizons_id": data.get("dest_id", "")}
    ax.text(dx_ + max_au * 0.04, dy_ - max_au * 0.04,
            f"Dest\n{data['dest_name']}",
            color="#00CCCC", fontsize=7, ha="left", va="top",
            alpha=0.95, zorder=9)

    return planet_artists + [orig_sc, dest_sc]


def _wire_solar_travel_click(canvas, ax, artists, on_body_click=None):
    """Click-to-info: clicking a body shows its name + position.

    on_body_click(body_info): optional callback invoked on pick; if provided,
    the inline info_box is skipped and the callback handles display instead.
    """
    info_box = _make_info_box(ax)

    def _on_pick(event):
        art = event.artist
        if not hasattr(art, "_body_info"):
            return
        p = art._body_info
        import math as _m
        dist_sun = _m.sqrt(p["x"] ** 2 + p["y"] ** 2 + p.get("z", 0) ** 2)
        if on_body_click is not None:
            on_body_click(p)
        else:
            info_box.set_text(
                f"{p['name']}\n"
                f"X: {p['x']:.4f} AU   Y: {p['y']:.4f} AU\n"
                f"Distance from Sun: {dist_sun:.4f} AU"
            )
            info_box.set_visible(True)
            canvas.draw_idle()

    def _on_click(event):
        if event.inaxes != ax:
            return
        if not getattr(event, "artist", None):
            if info_box.get_visible():
                info_box.set_visible(False)
                canvas.draw_idle()

    canvas.mpl_connect("pick_event", _on_pick)
    canvas.mpl_connect("button_press_event", _on_click)


def make_abundance_canvas(parent, abundances_data: dict, star_name: str = ""):
    """Horizontal bar chart of [X/H] elemental abundances for a single star.

    abundances_data: return value of core.viz.prepare_abundance_profile().
    Returns (canvas, toolbar).
    """
    if not _MPL_OK:
        return None, None

    def _error_canvas(msg):
        fig = Figure(figsize=(8, 3), dpi=100, facecolor=_SPACE_BG)
        cv  = FigureCanvas(fig)
        ax  = fig.add_subplot(111)
        ax.set_facecolor(_SPACE_BG)
        ax.text(0.5, 0.5, msg, transform=ax.transAxes,
                ha="center", va="center", color=_LABEL_CLR, fontsize=11)
        ax.axis("off")
        return cv, NavToolbar(cv, parent)

    if not abundances_data or "error" in abundances_data:
        return _error_canvas(abundances_data.get("error", "No abundance data") if abundances_data else "No abundance data")

    elements   = abundances_data.get("elements", [])
    means      = abundances_data.get("means", [])
    stds       = abundances_data.get("stds", [])
    categories = abundances_data.get("categories", [])
    bar_colors = abundances_data.get("colors", [])

    if not elements:
        return _error_canvas("No measurable abundances found")

    n = len(elements)
    # Error bars must be non-negative: matplotlib raises ValueError on negative
    # xerr. Clamp defensively so one bad spread value never drops the whole tab.
    safe_stds = [max(float(s), 0.0) if s is not None else 0.0 for s in stds]
    # Colour bars by nucleosynthetic-family category; fall back to sign colouring
    # if no category info was supplied.
    if bar_colors and len(bar_colors) == n:
        colors = list(bar_colors)
    else:
        colors = ["#e06c4a" if m >= 0 else "#4a90d9" for m in means]

    # Lay bars bottom-to-top in list order, inserting a one-row gap between
    # categories so the groups read as distinct blocks.
    cats = categories if len(categories) == n else [""] * n
    y_pos, gap = [], 0
    for i in range(n):
        if i > 0 and cats[i] != cats[i - 1]:
            gap += 1
        y_pos.append(i + gap)
    span = (y_pos[-1] if y_pos else 0) + 1

    fig_h = max(4.0, span * 0.34 + 1.8)
    fig   = Figure(figsize=(8, fig_h), dpi=100, facecolor=_SPACE_BG)
    canvas = FigureCanvas(fig)
    fig.subplots_adjust(left=0.13, right=0.96, top=0.93, bottom=0.07)

    ax = fig.add_subplot(111)
    ax.set_facecolor(_SPACE_BG)

    ax.barh(y_pos, means, xerr=safe_stds, color=colors,
            ecolor=_LABEL_CLR, capsize=3, alpha=0.88, height=0.62)

    ax.axvline(0, color=_LABEL_CLR, linewidth=0.9, alpha=0.55, zorder=3)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(elements, fontsize=9, color=_LABEL_CLR)
    ax.set_ylim(-0.8, span - 0.2)
    ax.set_xlabel("[X/H]  (Lodders 2009)", color=_LABEL_CLR, fontsize=9)
    ax.tick_params(axis="x", colors=_LABEL_CLR, labelsize=8)
    ax.tick_params(axis="y", colors=_LABEL_CLR)

    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("bottom", "left"):
        ax.spines[spine].set_color(_GRID_CLR)

    ax.grid(axis="x", color=_GRID_CLR, alpha=0.5, linewidth=0.7, linestyle="--")
    ax.set_axisbelow(True)

    # Legend mapping colour → category label (only the categories actually shown).
    try:
        from matplotlib.patches import Patch
        from core.hypatia_elements import category_label, category_color
        seen, handles = [], []
        for c in cats:
            if c and c not in seen:
                seen.append(c)
                handles.append(Patch(facecolor=category_color(c), label=category_label(c)))
        if handles:
            leg = ax.legend(handles=handles, loc="lower right", fontsize=7,
                            framealpha=0.85, facecolor=_SPACE_BG, edgecolor=_GRID_CLR)
            for txt in leg.get_texts():
                txt.set_color(_LABEL_CLR)
    except Exception:
        pass

    title = "[X/H] Elemental Abundances"
    if star_name:
        title += f"  —  {star_name}"
    ax.set_title(title, color=_LABEL_CLR, fontsize=10, pad=8)

    toolbar = NavToolbar(canvas, parent)
    return canvas, toolbar


def make_abundance_comparison_canvas(parent, data: dict):
    """Grouped horizontal [X/H] bar chart comparing 1–4 stars (Phase L1).

    data: return value of core.viz.prepare_abundance_comparison().
    Returns (canvas, toolbar).
    """
    if not _MPL_OK:
        return None, None

    def _error_canvas(msg):
        fig = Figure(figsize=(8, 3), dpi=100, facecolor=_SPACE_BG)
        cv  = FigureCanvas(fig)
        ax  = fig.add_subplot(111)
        ax.set_facecolor(_SPACE_BG)
        ax.text(0.5, 0.5, msg, transform=ax.transAxes,
                ha="center", va="center", color=_LABEL_CLR, fontsize=11)
        ax.axis("off")
        return cv, NavToolbar(cv, parent)

    if not data or "error" in data:
        return _error_canvas(data.get("error", "No abundance data") if data else "No abundance data")

    star_names = data.get("star_names", [])
    colors     = data.get("colors", [])
    elements   = data.get("elements", [])
    matrix     = data.get("matrix", [])
    n_stars    = len(star_names)
    n_elem     = len(elements)
    if not n_stars or not n_elem:
        return _error_canvas("No measurable abundances found")

    import numpy as np
    base    = np.arange(n_elem)              # one group per element
    group_h = 0.8
    bar_h   = group_h / n_stars

    fig_h = max(4.0, n_elem * 0.42 + 1.6)
    fig   = Figure(figsize=(8, fig_h), dpi=100, facecolor=_SPACE_BG)
    canvas = FigureCanvas(fig)
    fig.subplots_adjust(left=0.13, right=0.96, top=0.93, bottom=0.07)

    ax = fig.add_subplot(111)
    ax.set_facecolor(_SPACE_BG)

    for j in range(n_stars):
        ys   = base + group_h / 2 - (j + 0.5) * bar_h
        vals = [matrix[i][j] if matrix[i][j] is not None else 0.0 for i in range(n_elem)]
        color = colors[j] if j < len(colors) else None
        ax.barh(ys, vals, height=bar_h * 0.92, color=color,
                alpha=0.9, label=star_names[j])

    ax.axvline(0, color=_LABEL_CLR, linewidth=0.9, alpha=0.55, zorder=3)
    ax.set_yticks(base)
    ax.set_yticklabels(elements, fontsize=9, color=_LABEL_CLR)
    ax.set_ylim(-0.6, n_elem - 0.4)
    ax.invert_yaxis()                        # first element at top
    ax.set_xlabel("[X/H]  (Lodders 2009)", color=_LABEL_CLR, fontsize=9)
    ax.tick_params(axis="x", colors=_LABEL_CLR, labelsize=8)
    ax.tick_params(axis="y", colors=_LABEL_CLR)

    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("bottom", "left"):
        ax.spines[spine].set_color(_GRID_CLR)
    ax.grid(axis="x", color=_GRID_CLR, alpha=0.5, linewidth=0.7, linestyle="--")
    ax.set_axisbelow(True)

    leg = ax.legend(loc="lower right", fontsize=8, framealpha=0.85,
                    facecolor=_SPACE_BG, edgecolor=_GRID_CLR)
    for txt in leg.get_texts():
        txt.set_color(_LABEL_CLR)

    ax.set_title("[X/H] Elemental Abundances — Comparison",
                 color=_LABEL_CLR, fontsize=10, pad=8)

    toolbar = NavToolbar(canvas, parent)
    return canvas, toolbar


def make_evolution_canvas(parent, data: dict):
    """Horizontal stacked-bar stellar-evolution timeline (Phase L3).

    data: return value of core.viz.prepare_evolution_diagram().
    Returns (canvas, toolbar).
    """
    if not _MPL_OK:
        return None, None

    def _error_canvas(msg):
        fig = Figure(figsize=(8, 2.2), dpi=100, facecolor=_SPACE_BG)
        cv  = FigureCanvas(fig)
        ax  = fig.add_subplot(111)
        ax.set_facecolor(_SPACE_BG)
        ax.text(0.5, 0.5, msg, transform=ax.transAxes,
                ha="center", va="center", color=_LABEL_CLR, fontsize=11)
        ax.axis("off")
        return cv, NavToolbar(cv, parent)

    if not data or "error" in data:
        return _error_canvas(data.get("error", "No evolution data") if data else "No evolution data")

    stages = data.get("stages", [])
    if not stages:
        return _error_canvas("No evolution stages to plot")

    x_max = data.get("x_max_gyr") or 1.0
    age   = data.get("current_age_gyr")
    mass  = data.get("mass_solar")

    fig = Figure(figsize=(9, 3.4), dpi=100, facecolor=_SPACE_BG)
    canvas = FigureCanvas(fig)
    fig.subplots_adjust(left=0.06, right=0.97, top=0.84, bottom=0.34)
    ax = fig.add_subplot(111)
    ax.set_facecolor(_SPACE_BG)

    y = 0
    for s in stages:
        ax.barh(y, s["duration_gyr"], left=s["start_gyr"], height=0.6,
                color=s["color"], edgecolor=_SPACE_BG, alpha=0.92)
        # Label the segment in-place only if it's wide enough to fit text; every
        # stage is identifiable via the legend below regardless of width.
        if s["duration_gyr"] / x_max > 0.07:
            ax.text(s["start_gyr"] + s["duration_gyr"] / 2, y, s["name"],
                    ha="center", va="center", fontsize=7.5, color="#332b00")

    if age is not None:
        ax.axvline(age, color="#b03030", linewidth=1.6, linestyle="--", zorder=5)
        ax.text(age, 0.42, f"  Current Age: {age:.2f} Gyr",
                color="#b03030", fontsize=8, fontweight="bold",
                ha="left", va="bottom")

    ax.set_xlim(0, x_max)
    ax.set_ylim(-0.5, 0.6)
    ax.set_yticks([0])
    ax.set_yticklabels([f"{mass:g} M☉" if mass is not None else ""],
                       fontsize=9, color=_LABEL_CLR)
    ax.set_xlabel("Time (Gyr)", color=_LABEL_CLR, fontsize=9)
    ax.tick_params(axis="x", colors=_LABEL_CLR, labelsize=8)
    ax.tick_params(axis="y", colors=_LABEL_CLR)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(_GRID_CLR)
    ax.set_title("Stellar Evolution Timeline", color=_LABEL_CLR, fontsize=10, pad=8)

    # Legend: every stage colour → name, so the narrow segments (Pre-MS, RGB, HB,
    # AGB) that can't fit an in-bar label are still identifiable.
    from matplotlib.patches import Patch
    handles = [Patch(facecolor=s["color"], label=s["name"]) for s in stages]
    leg = ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.22),
                    ncol=min(len(handles), 6), fontsize=7.5, framealpha=0.9,
                    facecolor=_SPACE_BG, edgecolor=_GRID_CLR)
    for txt in leg.get_texts():
        txt.set_color(_LABEL_CLR)

    toolbar = NavToolbar(canvas, parent)
    return canvas, toolbar


def make_solar_travel_canvas(parent, data: dict, on_body_click=None):
    """2D top-down solar system travel path diagram (XY ecliptic plane).

    data: prepared by core.viz.prepare_solar_travel_diagram().
    on_body_click(body_info): optional callback invoked when a body is clicked.
    Returns (canvas, toolbar).
    """
    max_au = data["max_au"]
    title = f"{data['origin_name']}  →  {data['dest_name']}"

    fig = Figure(figsize=(6.5, 6.5), facecolor=_SPACE_BG)
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111, aspect="equal", facecolor=_SPACE_BG)

    artists = _build_solar_travel_elements(ax, data)
    _style_ax(ax, max_au, title)
    _wire_solar_travel_click(canvas, ax, artists, on_body_click=on_body_click)

    fig.tight_layout(pad=1.0)
    toolbar = NavToolbar(canvas, parent)
    return canvas, toolbar


def make_solar_travel_canvas_3d(parent, data: dict, on_body_click=None):
    """3D solar system travel path diagram.

    on_body_click(body_info): optional callback invoked when a body is clicked.
    Returns (canvas, toolbar, ax) — caller binds viewpoint preset buttons via ax.
    Body names are shown as floating 3D text labels anchored to each point.
    Hover shows a tooltip; click shows a detail box or calls on_body_click.
    """
    import math as _math
    import matplotlib as _mpl
    _mpl.rcParams['axes3d.mouserotationstyle'] = 'azel'
    try:
        from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 registers projection
    except ImportError:
        pass

    max_au = data["max_au"]
    title = f"{data['origin_name']}  →  {data['dest_name']}"

    fig = Figure(figsize=(6.5, 6.5), facecolor=_SPACE_BG)
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor(_SPACE_BG)
    fig.patch.set_facecolor(_SPACE_BG)

    # Reference orbit circles (thin dashed rings in the Z=0 plane)
    import numpy as _np
    _thetas = _np.linspace(0, 2 * _np.pi, 120)
    for orb in data.get("planet_orbits", []):
        xs = orb["sma_au"] * _np.cos(_thetas)
        ys = orb["sma_au"] * _np.sin(_thetas)
        zs = _np.zeros_like(_thetas)
        ax.plot(xs, ys, zs, color=orb["color"],
                linewidth=0.5, linestyle="--", alpha=0.3)

    # Planet dots with floating 3D name labels
    _all_bodies = []
    for p in data.get("planets", []):
        sc = ax.scatter([p["x"]], [p["y"]], [p["z"]],
                        color=p["color"], s=60, zorder=4,
                        picker=True, pickradius=6)
        sc._body_info = p
        _all_bodies.append(sc)
        r = _math.sqrt(p["x"] ** 2 + p["y"] ** 2) or 0.01
        ox_lbl = p["x"] / r * max_au * 0.04
        oy_lbl = p["y"] / r * max_au * 0.04
        ax.text(p["x"] + ox_lbl, p["y"] + oy_lbl, p["z"],
                p["name"], color=_LABEL_CLR, fontsize=6.5,
                ha="center", va="center", alpha=0.85, zorder=5)

    # Sun
    sun_sc = ax.scatter([0], [0], [0], color="#FFD700", s=140,
                        marker="*", zorder=6, picker=True, pickradius=8)
    sun_sc._body_info = {"name": "Sun", "x": 0.0, "y": 0.0, "z": 0.0}
    ax.text(0, max_au * 0.04, 0, "Sun",
            color="#CC8800", fontsize=7, ha="center", va="bottom",
            alpha=0.9, zorder=7)

    # Travel path line
    ox_, oy_, oz_ = data["origin_xyz"]
    dx_, dy_, dz_ = data["dest_xyz"]
    ax.plot([ox_, dx_], [oy_, dy_], [oz_, dz_],
            color="#888888", linewidth=1.5, linestyle="--", alpha=0.75)

    # Origin marker with label
    orig_sc = ax.scatter([ox_], [oy_], [oz_], color="#FF8800", s=140,
                         marker="*", zorder=8, picker=True, pickradius=8)
    orig_sc._body_info = {"name": f"Origin: {data['origin_name']}",
                          "x": ox_, "y": oy_, "z": oz_,
                          "horizons_id": data.get("origin_id", "")}
    ax.text(ox_ + max_au * 0.04, oy_ + max_au * 0.04, oz_,
            f"Origin\n{data['origin_name']}",
            color="#FF8800", fontsize=7, ha="left", va="bottom",
            alpha=0.95, zorder=9)

    # Destination marker with label
    dest_sc = ax.scatter([dx_], [dy_], [dz_], color="#00CCCC", s=110,
                         marker="s", zorder=8, picker=True, pickradius=8)
    dest_sc._body_info = {"name": f"Destination: {data['dest_name']}",
                          "x": dx_, "y": dy_, "z": dz_,
                          "horizons_id": data.get("dest_id", "")}
    ax.text(dx_ + max_au * 0.04, dy_ - max_au * 0.04, dz_,
            f"Dest\n{data['dest_name']}",
            color="#00CCCC", fontsize=7, ha="left", va="top",
            alpha=0.95, zorder=9)

    ax.set_xlim(-max_au, max_au)
    ax.set_ylim(-max_au, max_au)
    ax.set_zlim(-max_au * 0.4, max_au * 0.4)
    ax.set_xlabel("X (AU)", color=_LABEL_CLR, fontsize=8)
    ax.set_ylabel("Y (AU)", color=_LABEL_CLR, fontsize=8)
    ax.set_zlabel("Z (AU)", color=_LABEL_CLR, fontsize=8)
    ax.tick_params(colors=_LABEL_CLR, labelsize=7)
    ax.set_title(title, color=_LABEL_CLR, fontsize=9, pad=6)
    ax.view_init(elev=30, azim=-60)

    # Small legend strip (top-left) — colour key only, names now on the map
    legend_txt = "★  Origin    ■  Dest    ●  Planets (click for details)"
    ax.text2D(0.02, 0.97, legend_txt,
              transform=ax.transAxes,
              fontsize=7, color=_LABEL_CLR, va="top",
              bbox=dict(boxstyle="round,pad=0.35", fc="#f8f8f0",
                        ec="#aaaaaa", lw=0.8, alpha=0.88),
              zorder=10)

    # Hover tooltip (top-right, text2D — stays fixed regardless of rotation)
    hover_text = ax.text2D(0.98, 0.97, "", transform=ax.transAxes,
                           fontsize=8, color=_LABEL_CLR, va="top", ha="right",
                           bbox=dict(boxstyle="round,pad=0.3", fc="#f8f8f0",
                                     ec="#2266cc", lw=0.8, alpha=0.9),
                           visible=False, zorder=10)

    # Click info box (bottom-left, text2D)
    info_text = ax.text2D(0.02, 0.02, "", transform=ax.transAxes,
                          fontsize=8, color=_LABEL_CLR,
                          bbox=dict(boxstyle="round,pad=0.4", fc=_SPACE_BG,
                                    ec=_GRID_CLR, lw=0.8, alpha=0.9),
                          visible=False, zorder=10)

    _pickable = _all_bodies + [sun_sc, orig_sc, dest_sc]

    def _on_motion(event):
        if event.inaxes != ax:
            if hover_text.get_visible():
                hover_text.set_visible(False)
                canvas.draw_idle()
            return
        for sc in _pickable:
            cont, ind = sc.contains(event)
            if cont:
                p = sc._body_info
                hover_text.set_text(p["name"])
                hover_text.set_visible(True)
                canvas.draw_idle()
                return
        if hover_text.get_visible():
            hover_text.set_visible(False)
            canvas.draw_idle()

    def _on_pick(event):
        sc = event.artist
        if not hasattr(sc, "_body_info"):
            return
        p = sc._body_info
        dist = _math.sqrt(p["x"] ** 2 + p["y"] ** 2 + p.get("z", 0) ** 2)
        if on_body_click is not None:
            on_body_click(p)
        else:
            info_text.set_text(
                f"{p['name']}\n"
                f"X: {p['x']:.4f} AU   Y: {p['y']:.4f} AU\n"
                f"Distance from Sun: {dist:.4f} AU"
            )
            info_text.set_visible(True)
            canvas.draw_idle()

    def _on_click(event):
        if event.inaxes is not ax or event.xdata is None:
            if info_text.get_visible():
                info_text.set_visible(False)
                canvas.draw_idle()

    canvas.mpl_connect("motion_notify_event", _on_motion)
    canvas.mpl_connect("pick_event", _on_pick)
    canvas.mpl_connect("button_press_event", _on_click)

    toolbar = NavToolbar(canvas, parent)
    _disable_zoom_rect(toolbar)
    return canvas, toolbar, ax


# ── Exoplanet System Map (top-down, per-planet positions on a given date) ─────

def make_exoplanet_system_canvas(parent, data: dict, on_planet_click=None):
    """2D top-down map of an exoplanet system at a given epoch.

    data: prepared by core.viz.prepare_exoplanet_system_diagram().
    on_planet_click(planet_info): optional callback invoked when a planet is
    clicked.  When omitted, click shows an inline info box on the canvas.
    Returns (canvas, toolbar).
    """
    max_au    = data["max_au"]
    star_name = data.get("star_name", "")
    epoch_iso = data.get("epoch_iso") or ""
    title = "Exoplanet System Map"
    if star_name:
        title += f"  —  {star_name}"
    if epoch_iso:
        title += f"   ({epoch_iso})"

    fig = Figure(figsize=(6.5, 6.5), facecolor=_SPACE_BG)
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111, aspect="equal", facecolor=_SPACE_BG)

    # Orbit ellipses (dashed)
    for orb in data.get("orbits", []):
        ax.plot(orb["x_pts"], orb["y_pts"],
                color=orb["color"], linewidth=0.8, linestyle="--",
                alpha=0.55, zorder=2)

    # Planet markers
    planet_artists = []
    for p in data.get("planets", []):
        sc = ax.scatter([p["x"]], [p["y"]], color=p["color"],
                        s=70, zorder=4, picker=6, edgecolor="#222222",
                        linewidth=0.5)
        sc._body_info = p
        planet_artists.append(sc)
        r = math.sqrt(p["x"] ** 2 + p["y"] ** 2) or 0.01
        ox_lbl = p["x"] / r * max_au * 0.045
        oy_lbl = p["y"] / r * max_au * 0.045
        ax.text(p["x"] + ox_lbl, p["y"] + oy_lbl, p["name"],
                color=_LABEL_CLR, fontsize=7, ha="center", va="center",
                alpha=0.9, zorder=5)

    # Host star at origin (gold ★)
    star_sc = ax.scatter([0], [0], color="#FFD700", s=160, marker="*",
                         zorder=6, picker=8, edgecolor="#aa8800", linewidth=0.6)
    star_sc._body_info = {"name": star_name or "Host Star",
                          "x": 0.0, "y": 0.0, "z": 0.0,
                          "is_star": True}
    ax.text(0, max_au * 0.04, star_name or "Star",
            color="#cc8800", fontsize=8, ha="center", va="bottom",
            alpha=0.95, zorder=7)

    _style_ax(ax, max_au, title)

    # Legend strip (top-left)
    legend_txt = "★  Host Star    ●  Planets (click for details)"
    if any(not p.get("epoch_known", True) for p in data.get("planets", [])):
        legend_txt += "    ·  open-ring = epoch unknown (planet at periastron)"
    ax.text(0.02, 0.98, legend_txt, transform=ax.transAxes,
            fontsize=7, color=_LABEL_CLR, va="top",
            bbox=dict(boxstyle="round,pad=0.35", fc="#f8f8f0",
                      ec="#aaaaaa", lw=0.8, alpha=0.88),
            zorder=10)

    # Mark planets without known epoch with an open ring overlay
    for art in planet_artists:
        p = art._body_info
        if not p.get("epoch_known", True):
            ax.scatter([p["x"]], [p["y"]], facecolor="none",
                       edgecolor="#222222", s=180, linewidth=0.8,
                       zorder=3, alpha=0.6)

    # Hover tooltip + click info
    hover_text = ax.text(0.98, 0.98, "", transform=ax.transAxes,
                         fontsize=8, color=_LABEL_CLR, va="top", ha="right",
                         bbox=dict(boxstyle="round,pad=0.3", fc="#f8f8f0",
                                   ec="#2266cc", lw=0.8, alpha=0.9),
                         visible=False, zorder=10)
    info_box = _make_info_box(ax)

    _pickable = planet_artists + [star_sc]

    def _on_motion(event):
        if event.inaxes != ax:
            if hover_text.get_visible():
                hover_text.set_visible(False)
                canvas.draw_idle()
            return
        for sc in _pickable:
            cont, _ind = sc.contains(event)
            if cont:
                p = sc._body_info
                hover_text.set_text(p["name"])
                hover_text.set_visible(True)
                canvas.draw_idle()
                return
        if hover_text.get_visible():
            hover_text.set_visible(False)
            canvas.draw_idle()

    def _on_pick(event):
        art = event.artist
        if not hasattr(art, "_body_info"):
            return
        p = art._body_info
        if p.get("is_star"):
            return  # star click is a no-op
        if on_planet_click is not None:
            on_planet_click(p)
        else:
            dist = math.sqrt(p["x"] ** 2 + p["y"] ** 2)
            info_box.set_text(
                f"{p['name']}\n"
                f"X: {p['x']:.4f} AU   Y: {p['y']:.4f} AU\n"
                f"Distance from star: {dist:.4f} AU"
            )
            info_box.set_visible(True)
            canvas.draw_idle()

    def _on_click(event):
        if event.inaxes != ax:
            return
        if not getattr(event, "artist", None):
            if info_box.get_visible():
                info_box.set_visible(False)
                canvas.draw_idle()

    canvas.mpl_connect("motion_notify_event", _on_motion)
    canvas.mpl_connect("pick_event", _on_pick)
    canvas.mpl_connect("button_press_event", _on_click)

    fig.tight_layout(pad=1.0)
    toolbar = NavToolbar(canvas, parent)
    return canvas, toolbar


def make_esi_bar_canvas(parent, data: dict):
    """Horizontal top-N planets-by-ESI bar chart (Phase L2).

    data: return value of core.viz.prepare_esi_bar_chart(). Bars are colored by
    the habitable flag (green = habitable, gray = not). Returns (canvas, toolbar).
    """
    if not _MPL_OK:
        return None, None

    def _error_canvas(msg):
        fig = Figure(figsize=(8, 2.2), dpi=100, facecolor=_SPACE_BG)
        cv  = FigureCanvas(fig)
        ax  = fig.add_subplot(111)
        ax.set_facecolor(_SPACE_BG)
        ax.text(0.5, 0.5, msg, transform=ax.transAxes,
                ha="center", va="center", color=_LABEL_CLR, fontsize=11)
        ax.axis("off")
        return cv, NavToolbar(cv, parent)

    if not data or "error" in data:
        return _error_canvas(data.get("error", "No ranking data") if data else "No ranking data")

    names = data["names"]
    esi   = data["esi"]
    hab   = data["habitable"]
    n = len(names)

    # Height scales with bar count so labels never overlap; cap the figure so
    # very long result sets stay scrollable (wrap_scrollable handles overflow).
    fig_h = max(2.6, min(0.32 * n + 1.0, 16.0))
    fig = Figure(figsize=(8.5, fig_h), dpi=100, facecolor=_SPACE_BG)
    canvas = FigureCanvas(fig)
    fig.subplots_adjust(left=0.30, right=0.96, top=0.92, bottom=0.10)
    ax = fig.add_subplot(111)
    ax.set_facecolor(_SPACE_BG)

    y = list(range(n))
    colors = ["#3a9a4a" if h else "#9aa0a6" for h in hab]
    ax.barh(y, esi, color=colors, edgecolor=_SPACE_BG, height=0.74)
    for yi, v in zip(y, esi):
        ax.text(v + 0.005, yi, f"{v:.3f}", va="center", ha="left",
                fontsize=7.5, color=_LABEL_CLR)

    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=8, color=_LABEL_CLR)
    ax.invert_yaxis()                       # highest ESI at the top
    ax.set_xlim(min(0.5, min(esi) - 0.05) if esi else 0.0, 1.0)
    ax.set_xlabel("Earth Similarity Index (ESI)", color=_LABEL_CLR, fontsize=9)
    ax.tick_params(axis="x", colors=_LABEL_CLR, labelsize=8)
    ax.tick_params(axis="y", colors=_LABEL_CLR)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(_GRID_CLR)
    ax.grid(axis="x", color=_GRID_CLR, linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    shown, total = data.get("shown", n), data.get("total", n)
    title = f"Top {shown} planets by ESI" + (f"  (of {total})" if total > shown else "")
    ax.set_title(title, color=_LABEL_CLR, fontsize=10, pad=8)

    from matplotlib.patches import Patch
    handles = [Patch(facecolor="#3a9a4a", label="Habitable"),
               Patch(facecolor="#9aa0a6", label="Not flagged")]
    leg = ax.legend(handles=handles, loc="lower right", fontsize=7.5,
                    framealpha=0.9, facecolor=_SPACE_BG, edgecolor=_GRID_CLR)
    for txt in leg.get_texts():
        txt.set_color(_LABEL_CLR)

    toolbar = NavToolbar(canvas, parent)
    return canvas, toolbar


def make_scatter_canvas(parent, data: dict):
    """Generic 2D scatter with a hover tooltip (Phase L4 abundance search).

    data: return value of core.viz.prepare_hypatia_scatter() — {xs, ys, labels,
    x_label, y_label, count}. Hovering a point shows its label at the upper-left.
    Returns (canvas, toolbar).
    """
    if not _MPL_OK:
        return None, None

    def _error_canvas(msg):
        fig = Figure(figsize=(7, 5), dpi=100, facecolor=_SPACE_BG)
        cv  = FigureCanvas(fig)
        ax  = fig.add_subplot(111)
        ax.set_facecolor(_SPACE_BG)
        ax.text(0.5, 0.5, msg, transform=ax.transAxes,
                ha="center", va="center", color=_LABEL_CLR, fontsize=11)
        ax.axis("off")
        return cv, NavToolbar(cv, parent)

    if not data or "error" in data:
        return _error_canvas(data.get("error", "No data") if data else "No data")

    xs, ys, labels = data["xs"], data["ys"], data["labels"]

    fig = Figure(figsize=(7.5, 6), dpi=100, facecolor=_SPACE_BG)
    canvas = FigureCanvas(fig)
    fig.subplots_adjust(left=0.12, right=0.96, top=0.93, bottom=0.10)
    ax = fig.add_subplot(111)
    ax.set_facecolor(_SPACE_BG)

    ax.scatter(xs, ys, s=18, c="#3a6ea5", alpha=0.6, edgecolors="none", picker=False)
    ax.set_xlabel(data.get("x_label", ""), color=_LABEL_CLR, fontsize=9)
    ax.set_ylabel(data.get("y_label", ""), color=_LABEL_CLR, fontsize=9)
    ax.tick_params(colors=_LABEL_CLR, labelsize=8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(_GRID_CLR)
    ax.grid(color=_GRID_CLR, linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    ax.set_title(f"{data.get('y_label','')} vs {data.get('x_label','')}  "
                 f"({data.get('count', len(xs))} stars)",
                 color=_LABEL_CLR, fontsize=10, pad=8)

    tip = ax.annotate("", xy=(0, 0), xytext=(0.02, 0.98), textcoords="axes fraction",
                      ha="left", va="top", fontsize=8, color="#111",
                      bbox=dict(boxstyle="round", fc="#ffffe0", ec="#888", alpha=0.95),
                      visible=False)

    def _on_motion(event):
        if event.inaxes is not ax:
            if tip.get_visible():
                tip.set_visible(False)
                canvas.draw_idle()
            return
        # Nearest point in display space.
        best_i, best_d = None, None
        for i, (xv, yv) in enumerate(zip(xs, ys)):
            px, py = ax.transData.transform((xv, yv))
            d = (px - event.x) ** 2 + (py - event.y) ** 2
            if best_d is None or d < best_d:
                best_d, best_i = d, i
        if best_i is not None and best_d is not None and best_d <= 144:  # within 12 px
            tip.set_text(f"{labels[best_i]}\n{data.get('x_label','')}={xs[best_i]:g}, "
                         f"{data.get('y_label','')}={ys[best_i]:g}")
            tip.set_visible(True)
        elif tip.get_visible():
            tip.set_visible(False)
        canvas.draw_idle()

    canvas.mpl_connect("motion_notify_event", _on_motion)

    toolbar = NavToolbar(canvas, parent)
    return canvas, toolbar


# ── Phase O O-2: Star-Map Data Products ───────────────────────────────────────

# Dark-navy sky palette (the Star-Chart look, per the Phase-O star-map convention).
_SKY_FIG = "#070b18"
_SKY_BG  = "#0b1020"
_SKY_GRID = "#1a2448"
_SKY_TXT = "#cfe3ff"


def make_hr_canvas(parent, data: dict, overlay_points=None):
    """HR / colour–magnitude diagram (Phase O · O2).

    data: core.viz.prepare_hr_main_sequence() → {points:[{label,teff,abs_mag,...}]}.
    overlay_points: optional list from core.viz.prepare_hr_from_stars()["points"]
      (result stars) drawn as scatter over the main-sequence reference line.
    x = Teff (K, log, inverted — hot left); y = absolute visual mag (inverted — bright
    top); a secondary top axis labels spectral-class letters at their Teff. Light theme.
    Returns (canvas, toolbar).
    """
    if not _MPL_OK:
        return None, None

    def _error_canvas(msg):
        fig = Figure(figsize=(7, 5), dpi=100, facecolor=_SPACE_BG)
        cv = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        ax.set_facecolor(_SPACE_BG)
        ax.text(0.5, 0.5, msg, transform=ax.transAxes, ha="center", va="center",
                color=_LABEL_CLR, fontsize=11)
        ax.axis("off")
        return cv, NavToolbar(cv, parent)

    if not data or "error" in data:
        return _error_canvas(data.get("error", "No data") if data else "No data")
    points = data.get("points") or []
    if not points:
        return _error_canvas("No main-sequence points to plot.")

    fig = Figure(figsize=(7.5, 6), dpi=100, facecolor=_SPACE_BG)
    canvas = FigureCanvas(fig)
    fig.subplots_adjust(left=0.11, right=0.96, top=0.88, bottom=0.10)
    ax = fig.add_subplot(111)
    ax.set_facecolor(_SPACE_BG)

    teffs = [p["teff"] for p in points]
    mags = [p["abs_mag"] for p in points]

    # Main-sequence reference line + colored points.
    ax.plot(teffs, mags, color="#4a6a55", linewidth=1.6, zorder=2)
    ax.scatter(teffs, mags, s=26, c=[p["color"] for p in points],
               edgecolors="#444", linewidths=0.4, zorder=3)
    for i, p in enumerate(points):
        if i % 2 == 0 and p["label"]:
            ax.annotate(p["label"], (p["teff"], p["abs_mag"]),
                        textcoords="offset points", xytext=(4, -2),
                        fontsize=6.5, color="#789", zorder=4)

    # Overlay (O2b): result stars as red dots; the reference anchor (Sol / the queried
    # centre star, flagged "highlight") as a gold ★ so it's easy to locate.
    overlay_points = overlay_points or []
    _normal = [p for p in overlay_points if not p.get("highlight")]
    _refs = [p for p in overlay_points if p.get("highlight")]
    if _normal:
        ax.scatter([p["teff"] for p in _normal], [p["abs_mag"] for p in _normal],
                   s=42, marker="o", c="#b03030", edgecolors="#fff", linewidths=0.5,
                   zorder=5, label="result stars")
        for p in _normal:
            ax.annotate(p.get("name", ""), (p["teff"], p["abs_mag"]),
                        textcoords="offset points", xytext=(6, 3),
                        fontsize=7, color="#7a1414", zorder=6)
    for p in _refs:
        ax.scatter([p["teff"]], [p["abs_mag"]], s=240, marker="*", c="#FFD700",
                   edgecolors="#7a5c00", linewidths=0.8, zorder=7,
                   label=p.get("name", "reference"))
        ax.annotate(p.get("name", ""), (p["teff"], p["abs_mag"]),
                    textcoords="offset points", xytext=(8, 4), fontsize=8,
                    fontweight="bold", color="#7a5c00", zorder=8)

    ax.set_xscale("log")
    ax.set_xlim(max(teffs) * 1.15, min(teffs) * 0.87)   # inverted: hot left
    ax.invert_yaxis()                                    # bright top
    ax.set_xlabel("Effective temperature (K) — hot left, log", color=_LABEL_CLR, fontsize=9)
    ax.set_ylabel("Absolute visual magnitude — bright up", color=_LABEL_CLR, fontsize=9)
    ax.tick_params(colors=_LABEL_CLR, labelsize=8)
    ax.grid(color=_GRID_CLR, linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    ax.set_title("HR / Colour–Magnitude Diagram", color=_LABEL_CLR, fontsize=10, pad=22)
    if overlay_points:
        ax.legend(loc="lower left", fontsize=8)

    # Secondary top axis: spectral-class letters at their Teff positions.
    anchors, seen = [], set()
    for p in points:
        letter = (p["label"][:1].upper() if p["label"] else "")
        if letter and letter not in seen:
            seen.add(letter)
            anchors.append((p["teff"], letter))
    trans = ax.get_xaxis_transform()  # x in data coords, y in axes fraction
    for teff, letter in anchors:
        ax.text(teff, 1.02, letter, transform=trans, ha="center", va="bottom",
                fontsize=8, color="#3a73ad", clip_on=False)

    toolbar = NavToolbar(canvas, parent)
    return canvas, toolbar


def make_sky_canvas(parent, data: dict):
    """Night-sky (RA/Dec) view from a vantage star (Phase O · O1).

    data: core.viz.prepare_sky_from_star() → {vantage_name, mag_limit, skipped_no_mag,
    stars:[{name, ra_deg, dec_deg, mag, sp_class, color}]}. Rectangular RA/Dec plot
    (RA reversed, sky convention), dark-navy Star-Chart palette; marker size by
    brightness; hover shows name + apparent magnitude. Returns (canvas, toolbar).
    """
    if not _MPL_OK:
        return None, None

    def _error_canvas(msg, bg=_SPACE_BG, fg=_LABEL_CLR):
        fig = Figure(figsize=(7, 4.6), dpi=100, facecolor=bg)
        cv = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        ax.set_facecolor(bg)
        ax.text(0.5, 0.5, msg, transform=ax.transAxes, ha="center", va="center",
                color=fg, fontsize=11)
        ax.axis("off")
        return cv, NavToolbar(cv, parent)

    if not data or "error" in data:
        return _error_canvas(data.get("error", "No data") if data else "No data")
    stars = data.get("stars") or []
    if not stars:
        return _error_canvas("No stars above the magnitude limit in range.",
                             bg=_SKY_FIG, fg=_SKY_TXT)

    fig = Figure(figsize=(8, 4.8), dpi=100, facecolor=_SKY_FIG)
    canvas = FigureCanvas(fig)
    fig.subplots_adjust(left=0.08, right=0.97, top=0.90, bottom=0.12)
    ax = fig.add_subplot(111)
    ax.set_facecolor(_SKY_BG)

    ras = [s["ra_deg"] for s in stars]
    decs = [s["dec_deg"] for s in stars]
    mags = [s["mag"] for s in stars]
    mmin = min(mags)
    sizes = [max(4.0, min(180.0, 60.0 * (10.0 ** (-0.4 * (m - mmin))))) for m in mags]
    colors = [s["color"] for s in stars]

    ax.scatter(ras, decs, s=sizes, c=colors, edgecolors="#05080d",
               linewidths=0.4, zorder=3)
    for s, sz in zip(stars, sizes):
        if sz > 28:
            ax.annotate(s["name"], (s["ra_deg"], s["dec_deg"]),
                        textcoords="offset points", xytext=(5, 3),
                        fontsize=7, color="#9fb8d8", zorder=4)

    ax.set_xlim(360, 0)   # RA reversed (sky convention)
    ax.set_ylim(-90, 90)
    ax.set_xticks(range(0, 361, 60))
    ax.set_yticks(range(-90, 91, 30))
    ax.set_xlabel("Right ascension (°)", color=_SKY_TXT, fontsize=9)
    ax.set_ylabel("Declination (°)", color=_SKY_TXT, fontsize=9)
    ax.tick_params(colors=_SKY_TXT, labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(_SKY_GRID)
    ax.grid(color=_SKY_GRID, linewidth=0.6, alpha=0.8)
    ax.set_axisbelow(True)
    title = f"Night sky from {data.get('vantage_name', '?')} (to m={data.get('mag_limit', 6.5):g})"
    if data.get("skipped_no_mag"):
        title += f"   ·   {data['skipped_no_mag']} omitted (no V mag)"
    ax.set_title(title, color=_SKY_TXT, fontsize=10, pad=8)

    # Hover tooltip anchored to the hovered star (follows the point, like the 2D maps).
    annot = ax.annotate(
        "", xy=(0, 0), xytext=(12, 12), textcoords="offset points",
        bbox=dict(boxstyle="round,pad=0.3", fc="#f8f8f0", ec="#2266cc", lw=0.8, alpha=0.95),
        arrowprops=dict(arrowstyle="->", color="#2266cc", lw=0.8),
        color="#222", fontsize=8, zorder=10, visible=False,
    )

    def _on_motion(event):
        if event.inaxes is not ax:
            if annot.get_visible():
                annot.set_visible(False)
                canvas.draw_idle()
            return
        best_i, best_d = None, None
        for i, (rv, dv) in enumerate(zip(ras, decs)):
            px, py = ax.transData.transform((rv, dv))
            d = (px - event.x) ** 2 + (py - event.y) ** 2
            if best_d is None or d < best_d:
                best_d, best_i = d, i
        if best_i is not None and best_d <= 144:
            s = stars[best_i]
            annot.xy = (ras[best_i], decs[best_i])
            annot.set_text(f"{s['name']}\nm'={s['mag']:.2f}")
            annot.set_visible(True)
        elif annot.get_visible():
            annot.set_visible(False)
        canvas.draw_idle()

    canvas.mpl_connect("motion_notify_event", _on_motion)
    toolbar = NavToolbar(canvas, parent)
    return canvas, toolbar
