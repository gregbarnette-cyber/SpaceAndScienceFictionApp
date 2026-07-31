# tests/test_route_chart_tabs.py — the Route-Chart refactor (completed_plans/ROUTE_CHART_REFACTOR_PLAN.md).
#
# The seven Route Planning panels render into the same canvases as the opt-18/19
# star charts but reached them by a private path, so they missed the shared
# builder's features. Phase 1 routes them through `_build_iso_chart_tab` via an
# additive `routes=` passthrough; Phase 2 turns on the parity features.
#
# Phase-1 tests are behaviour-neutral PINS: they pass against the pre-refactor
# code too (that is the proof the seam changed nothing). Phase-2 tests fail
# before the refactor and pass after. Before this file, route-chart tab
# construction had NO test coverage at all — only the `prepare_route_map` core
# prep (test_route_planning*.py) and the two-star maps (test_viz_phase_o.py).

import os
# Qt must run headless under the test runner. Set before any PySide6 import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest


def _mpl_available() -> bool:
    try:
        from gui.visualizations.plot_helpers import mpl_available
        return mpl_available()
    except Exception:
        return False


# ── fixtures ─────────────────────────────────────────────────────────────────
# Hand-built result dicts in the shapes `core.viz.prepare_route_map` branches on
# (see its docstring). Geometry is trivially hand-checkable; no DB, no network.

def _star(name, x, y, z, sp="G2V", color="#fff4c2", desig=""):
    import math
    return {"name": name, "desig": desig, "sp_type": sp, "color": color,
            "ly": math.sqrt(x * x + y * y + z * z), "x": x, "y": y, "z": z}


def _chain_result():
    """I2 — nearest-neighbor chain (dashed ordered legs)."""
    stars = [_star("Sol", 0.0, 0.0, 0.0),
             _star("Alpha Centauri", 3.0, 0.0, 0.0, "G2V"),
             _star("Barnard's Star", 3.0, 4.0, 0.0, "M4V", "#ff9d6c")]
    return {
        "start_name": "Sol", "total_ly": 7.0, "stopped_early": False,
        "chain": [
            {"hop": 1, "star_name": "Alpha Centauri", "desig": "", "sp_type": "G2V",
             "dist_from_prev_ly": 3.0, "cumulative_ly": 3.0, "ly_from_sol": 3.0},
            {"hop": 2, "star_name": "Barnard's Star", "desig": "", "sp_type": "M4V",
             "dist_from_prev_ly": 4.0, "cumulative_ly": 7.0, "ly_from_sol": 5.0},
        ],
        "stars": stars,
    }


def _tiers_result():
    """C — jump network: tier-COLOURED nodes, no edges."""
    stars = [_star("Sol", 0.0, 0.0, 0.0, "G2V", "#FFD700"),
             _star("Alpha Centauri", 3.0, 0.0, 0.0, "G2V", "#44cc88"),
             _star("Barnard's Star", 3.0, 4.0, 0.0, "M4V", "#44cc88")]
    return {
        "start_name": "Sol", "max_jump_ly": 5.0, "max_jumps": None, "max_tier": 1,
        "reachable_count": 3, "total_in_pool": 3, "unreachable_count": 0,
        "tiers": [
            {"jumps": 0, "stars": [
                {"star_name": "Sol", "desig": "", "sp_type": "G2V",
                 "dist_from_start_ly": 0.0, "ly_from_sol": 0.0}]},
            {"jumps": 1, "stars": [
                {"star_name": "Alpha Centauri", "desig": "", "sp_type": "G2V",
                 "dist_from_start_ly": 3.0, "ly_from_sol": 3.0},
                {"star_name": "Barnard's Star", "desig": "", "sp_type": "M4V",
                 "dist_from_start_ly": 5.0, "ly_from_sol": 5.0}]},
        ],
        "stars": stars,
    }


def _mst_result():
    """I3 — trade-route MST (solid edges, keyed by name)."""
    stars = [_star("Sol", 0.0, 0.0, 0.0),
             _star("Alpha Centauri", 3.0, 0.0, 0.0),
             _star("Barnard's Star", 3.0, 4.0, 0.0, "M4V", "#ff9d6c")]
    return {
        "nodes": [{"name": s["name"], "x": s["x"], "y": s["y"], "z": s["z"],
                   "sp_type": s["sp_type"], "desig": ""} for s in stars],
        "edges": [{"from": "Sol", "to": "Alpha Centauri", "distance_ly": 3.0},
                  {"from": "Alpha Centauri", "to": "Barnard's Star",
                   "distance_ly": 4.0}],
        "total_ly": 7.0, "stars": stars,
    }


def _unreachable_jump_route():
    """B — jump route with no path: two endpoints, zero edges.

    Carries the always-present waypoint keys (`via`/`via_legs`/`unreachable_leg`)
    added with `via=` support; with no waypoints `unreachable_leg` is just the
    origin/destination pair.
    """
    return {
        "origin_info": {"name": "Sol"}, "dest_info": {"name": "Vega"},
        "reachable": False, "optimize": "distance", "jumps": 0,
        "total_ly": 0.0, "direct_ly": 25.0, "route": [], "max_jump_ly": 2.0,
        "stars": [_star("Sol", 0.0, 0.0, 0.0),
                  _star("Vega", 25.0, 0.0, 0.0, "A0V", "#cad7ff")],
        "via": [], "via_legs": [],
        "unreachable_leg": {"from": "Sol", "to": "Vega"},
    }


def _unreachable_via_jump_route():
    """B — the waypoint case: three terminals, and the leg that failed is
    Sol→Vega (the waypoint), not Sol→the destination."""
    return {
        "origin_info": {"name": "Sol"}, "dest_info": {"name": "Procyon"},
        "reachable": False, "optimize": "distance", "jumps": 0,
        "total_ly": 0.0, "direct_ly": 11.4, "route": [], "max_jump_ly": 2.0,
        "stars": [_star("Sol", 0.0, 0.0, 0.0),
                  _star("Vega", 25.0, 0.0, 0.0, "A0V", "#cad7ff"),
                  _star("Procyon", 11.4, 0.0, 0.0, "F5IV", "#f8f7ff")],
        "via": ["Vega"], "via_legs": [],
        "unreachable_leg": {"from": "Sol", "to": "Vega"},
    }


def _via_jump_route():
    """B — a reachable waypointed route that RE-VISITS Sol (Sol→Wz→Sol→P)."""
    stars = [_star("Sol", 0.0, 0.0, 0.0),
             _star("Wz", 0.0, 0.0, 3.0, "M3V", "#FF8D3F"),
             _star("Sol", 0.0, 0.0, 0.0),
             _star("Procyon", 3.0, 0.0, 0.0, "F5IV", "#f8f7ff")]
    route = [
        {"jump": 1, "from": "Sol", "to": "Wz", "jump_ly": 3.0,
         "cumulative_ly": 3.0, "waypoint": True},
        {"jump": 2, "from": "Wz", "to": "Sol", "jump_ly": 3.0,
         "cumulative_ly": 6.0, "waypoint": False},
        {"jump": 3, "from": "Sol", "to": "Procyon", "jump_ly": 3.0,
         "cumulative_ly": 9.0, "waypoint": False},
    ]
    return {
        "origin_info": {"name": "Sol"}, "dest_info": {"name": "Procyon"},
        "reachable": True, "optimize": "distance", "jumps": 3,
        "total_ly": 9.0, "direct_ly": 3.0, "route": route, "max_jump_ly": 4.0,
        "stars": stars, "via": ["Wz"],
        "via_legs": [{"from": "Sol", "to": "Wz", "jumps": 1, "ly": 3.0},
                     {"from": "Wz", "to": "Procyon", "jumps": 2, "ly": 6.0}],
        "unreachable_leg": None,
    }


class _FakeNav:
    """Minimal nav-tree stand-in — ResultPanel.{_prepare,_enter,_exit}_render
    show/hide it (the `_FakeNav` pattern used by test_oec.py etc.)."""
    def show(self):
        pass

    def hide(self):
        pass


class _StubWindow:
    def __init__(self):
        self.nav_tree = _FakeNav()


def _route_line_count(canvas):
    """Route-overlay Line2D artists (dashed legs / solid MST), by their colours."""
    from gui.visualizations.plot_helpers import _SC_ROUTE, _SC_MST
    import matplotlib.colors as mcolors
    want = {mcolors.to_hex(_SC_ROUTE).lower(), mcolors.to_hex(_SC_MST).lower()}
    ax = canvas.figure.axes[0]
    return sum(1 for ln in ax.lines
               if mcolors.to_hex(ln.get_color()).lower() in want)


def _panel_canvases(panel):
    """Both chart canvases the route tabs registered (2D first, then 3D)."""
    return list(getattr(panel, "_link_canvases", ()))


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 — the seam. These pin behaviour that must survive the conversion, so
# they pass BEFORE the refactor as well as after.
# ─────────────────────────────────────────────────────────────────────────────
@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class RouteChartSeamTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self, cls_name):
        import gui.panels as panels
        return getattr(panels, cls_name)(_StubWindow())

    def test_every_panel_gets_the_two_named_tabs(self):
        """All 7 Route Planning panels build "Star Chart" + "Star Chart 3D"."""
        from gui.panels.route_planning import _add_route_chart_tabs
        cases = [
            ("MultiStopJourneyPanel", _chain_result()),
            ("NearestNeighborPanel", _chain_result()),
            ("OptimalTourPanel", {**_chain_result(), "closed": False}),
            ("FarthestFirstPanel", {
                **_chain_result(),
                "tree_edges": [{"from_index": 0, "to_index": 1},
                               {"from_index": 1, "to_index": 2}]}),
            ("JumpRoutePanel", _unreachable_jump_route()),
            ("JumpNetworkPanel", _tiers_result()),
            ("TradeRoutePlannerPanel", _mst_result()),
        ]
        for cls_name, result in cases:
            with self.subTest(cls_name):
                p = self._panel(cls_name)
                n0 = p._viz_tabs_widget.count()
                _add_route_chart_tabs(p, result)
                self.assertEqual(p._viz_tabs_widget.count(), n0 + 2)
                self.assertEqual(p._viz_tabs_widget.tabText(n0), "Star Chart")
                self.assertEqual(p._viz_tabs_widget.tabText(n0 + 1),
                                 "Star Chart 3D")

    def test_route_edges_reach_both_canvases(self):
        """The route overlay is the reason these charts bypassed the shared
        builder — it must still be drawn, in 2D and 3D."""
        from gui.visualizations.plot_helpers import (
            make_star_chart_canvas, make_star_chart_3d_canvas)
        import core.viz
        from gui.panels.route_planning import _centered
        stars, edges, limit = _centered(core.viz.prepare_route_map(_chain_result()))
        self.assertEqual(len(edges), 2)          # Sol→AlphaCen→Barnard

        canvas, _ = make_star_chart_canvas(None, stars, limit_ly=limit,
                                           routes=edges)
        self.assertEqual(_route_line_count(canvas), 2)
        canvas3d, _, _ = make_star_chart_3d_canvas(None, stars, limit_ly=limit,
                                                   routes=edges)
        ax3d = canvas3d.figure.axes[0]
        self.assertGreaterEqual(len(ax3d.lines), 2)

    def test_mst_edges_are_solid_and_still_drawn(self):
        import core.viz
        from gui.panels.route_planning import _centered
        from gui.visualizations.plot_helpers import make_star_chart_canvas
        rm = core.viz.prepare_route_map(_mst_result())
        self.assertEqual(rm["edge_style"], "solid")
        stars, edges, limit = _centered(rm)
        canvas, _ = make_star_chart_canvas(None, stars, limit_ly=limit,
                                           routes=edges)
        self.assertEqual(_route_line_count(canvas), 2)

    def test_3d_tab_keeps_viewpoint_presets(self):
        """The private _route_chart_3d_tab is deleted by the refactor; the shared
        _build_star_chart_3d_tab must supply the same three preset buttons."""
        from PySide6.QtWidgets import QPushButton
        from gui.panels.route_planning import _add_route_chart_tabs
        p = self._panel("NearestNeighborPanel")
        n0 = p._viz_tabs_widget.count()
        _add_route_chart_tabs(p, _chain_result())
        tab3d = p._viz_tabs_widget.widget(n0 + 1)
        labels = {b.text() for b in tab3d.findChildren(QPushButton)}
        for want in ("Top View", "Side View", "3D Perspective"):
            self.assertIn(want, labels)

    def test_unreachable_jump_route_builds_with_no_edges(self):
        from gui.panels.route_planning import _add_route_chart_tabs
        import core.viz
        rm = core.viz.prepare_route_map(_unreachable_jump_route())
        self.assertEqual(rm["edges"], [])
        p = self._panel("JumpRoutePanel")
        n0 = p._viz_tabs_widget.count()
        _add_route_chart_tabs(p, _unreachable_jump_route())
        self.assertEqual(p._viz_tabs_widget.count(), n0 + 2)

    def test_error_and_empty_results_add_no_tabs(self):
        from gui.panels.route_planning import _add_route_chart_tabs
        p = self._panel("NearestNeighborPanel")
        n0 = p._viz_tabs_widget.count()
        _add_route_chart_tabs(p, {"error": "nope"})
        _add_route_chart_tabs(p, {"stars": [], "chain": []})
        self.assertEqual(p._viz_tabs_widget.count(), n0)

    def test_centering_puts_the_start_at_the_origin(self):
        """The gold ★ contract: stars[0] must land exactly at (0,0,0)."""
        import core.viz
        from gui.panels.route_planning import _centered
        r = _chain_result()
        r["stars"] = [_star("Alpha Centauri", 3.0, 0.0, 0.0),
                      _star("Sol", 0.0, 0.0, 0.0)]
        stars, _, limit = _centered(core.viz.prepare_route_map(r))
        self.assertEqual((stars[0]["x"], stars[0]["y"], stars[0]["z"]),
                         (0.0, 0.0, 0.0))
        self.assertEqual((stars[1]["x"], stars[1]["y"], stars[1]["z"]),
                         (-3.0, 0.0, 0.0))
        self.assertAlmostEqual(limit, 3.0 * 1.1)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — feature parity. These FAIL before the refactor.
# ─────────────────────────────────────────────────────────────────────────────
@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class RouteChartParityTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self, cls_name):
        import gui.panels as panels
        return getattr(panels, cls_name)(_StubWindow())

    def _built(self, cls_name, result, **kw):
        from gui.panels.route_planning import _add_route_chart_tabs
        p = self._panel(cls_name)
        p._route_tab0 = p._viz_tabs_widget.count()
        _add_route_chart_tabs(p, result, **kw)
        return p

    def test_both_tabs_have_the_isochrone_control(self):
        """O17 — the control the shared builder supplies. Rings are centred on
        the chart origin, which _centered puts at the route's start, so they read
        as travel time FROM the start."""
        from PySide6.QtWidgets import QLineEdit
        p = self._built("NearestNeighborPanel", _chain_result())
        for i in (p._route_tab0, p._route_tab0 + 1):
            tab = p._viz_tabs_widget.widget(i)
            placeholders = [w.placeholderText() for w in tab.findChildren(QLineEdit)]
            self.assertIn("blank = distance", placeholders,
                          msg=p._viz_tabs_widget.tabText(i))

    def test_legend_filter_is_on_for_spectral_coloured_panels(self):
        """O16 — per-class legend (Class G / Class M for this fixture)."""
        p = self._built("NearestNeighborPanel", _chain_result())
        canvas = _panel_canvases(p)[0]
        legend = canvas.figure.axes[0].get_legend()
        self.assertIsNotNone(legend)
        labels = {t.get_text() for t in legend.get_texts()}
        self.assertEqual(labels, {"Class G", "Class M"})

    def test_jump_network_suppresses_the_legend_filter(self):
        """JumpNetworkPanel paints per-TIER colours (compute_jump_network sets
        stars[].color), but the legend groups by spectral class and takes its
        swatch from that colour — so a legend here would read "Class M" with a
        tier swatch. It is suppressed; the panel's own tier legend stands.

        Driven through the panel's _render so this pins the CALL SITE, not just
        the mechanism — passing legend_filter=False from the test would pass even
        if the panel forgot to."""
        p = self._panel("JumpNetworkPanel")
        p._render(_tiers_result())
        canvas = _panel_canvases(p)[0]
        self.assertIsNone(canvas.figure.axes[0].get_legend())

    def test_spectral_panels_keep_the_legend_through_their_render(self):
        """The mirror of the Jump Network case: a spectral-coloured panel's own
        _render must NOT suppress the legend."""
        p = self._panel("NearestNeighborPanel")
        p._render(_chain_result())
        canvas = _panel_canvases(p)[0]
        self.assertIsNotNone(canvas.figure.axes[0].get_legend())

    def test_routes_survive_an_isochrone_rebuild(self):
        """Applying a velocity tears down and rebuilds the canvas — the route
        overlay must be re-passed, not lost."""
        from PySide6.QtWidgets import QLineEdit, QPushButton
        p = self._built("NearestNeighborPanel", _chain_result())
        tab = p._viz_tabs_widget.widget(p._route_tab0)
        self.assertEqual(_route_line_count(_panel_canvases(p)[0]), 2)

        vel = next(w for w in tab.findChildren(QLineEdit)
                   if w.placeholderText() == "blank = distance")
        apply_btn = next(b for b in tab.findChildren(QPushButton)
                         if b.text() == "Apply")
        vel.setText("0.5")            # ly/hr-ish; unit combo defaults to × c
        apply_btn.click()
        self.assertEqual(_route_line_count(_panel_canvases(p)[0]), 2)

    def test_row_map_linking_reads_the_star_name_column(self):
        """O15 — every route table leads with an INDEX column (Hop #, Step,
        Jumps), so linking must be told which column holds the name. Column 0
        would select on "1"/"2" and never match."""
        from gui.panels.diagram_tabs import _selected_star_name, _star_click_select
        from PySide6.QtCore import QItemSelectionModel
        # Through the panel's own _render, so this pins the call site: the panel
        # must hand its table over AND the name column must be right.
        p = self._panel("NearestNeighborPanel")
        p._render(_chain_result())
        self.assertIsNotNone(p._link_view)
        self.assertEqual(p._link_name_col, 1)
        self.assertTrue(p._link_canvases)

        view = p._link_view
        model = view.model()
        self.assertEqual(model.horizontalHeaderItem(1).text(), "Star Name")
        view.selectionModel().setCurrentIndex(
            model.index(1, 0),
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows)
        self.assertEqual(_selected_star_name(view, 1), "Barnard's Star")

        # …and a map click selects the row whose NAME column matches.
        _star_click_select(p, "Alpha Centauri")
        self.assertEqual(view.selectionModel().currentIndex().row(), 0)

    def test_default_name_col_is_still_column_zero(self):
        """The name_col seam is additive: opts 18/19 / the two-star maps pass
        nothing and keep reading column 0."""
        from gui.panels.diagram_tabs import _selected_star_name
        from PySide6.QtCore import QItemSelectionModel
        p = self._panel("NearestNeighborPanel")
        view = p.make_table(["Star Name", "Dist"], [["Vega", "25.0"]])
        view.selectionModel().setCurrentIndex(
            view.model().index(0, 0),
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows)
        self.assertEqual(_selected_star_name(view), "Vega")


# ─────────────────────────────────────────────────────────────────────────────
# JumpRoutePanel waypoints (JUMP_ROUTE_WAYPOINTS_PLAN Phase 2): the Via field,
# the ◆ marker + visit-order line, and the unreachable branch naming the leg.
# ─────────────────────────────────────────────────────────────────────────────
class JumpRouteViaPanelTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self):
        import gui.panels as panels
        return panels.JumpRoutePanel(_StubWindow())

    def _labels(self, panel):
        from PySide6.QtWidgets import QLabel
        return [w.text() for w in panel._tables_widget.findChildren(QLabel)]

    def _table_rows(self, panel):
        from PySide6.QtWidgets import QTableView
        view = panel._tables_widget.findChild(QTableView)
        m = view.model()
        return [[m.index(r, c).data() for c in range(m.columnCount())]
                for r in range(m.rowCount())]

    def test_via_field_exists_and_splits_on_commas(self):
        captured = {}
        p = self._panel()
        p._origin.setText("Sol")
        p._dest.setText("Procyon")
        p._max.setText("9")
        p._via.setText(" 70 Vir , , 61 Vir ")
        p.run_in_background = lambda fn, *a, **kw: captured.update(args=a)
        p._search()
        # blanks dropped, entries stripped, passed as the 5th positional.
        self.assertEqual(captured["args"][4], ["70 Vir", "61 Vir"])

    def test_blank_via_is_the_off_switch(self):
        captured = {}
        p = self._panel()
        p._origin.setText("Sol")
        p._dest.setText("Procyon")
        p._max.setText("9")
        p.run_in_background = lambda fn, *a, **kw: captured.update(args=a)
        p._search()
        self.assertEqual(captured["args"][4], [])

    def test_reachable_via_route_marks_waypoints_and_lists_visit_order(self):
        p = self._panel()
        p._render(_via_jump_route())
        rows = self._table_rows(p)
        self.assertEqual([r[2] for r in rows], ["◆ Wz", "Sol", "Procyon"])
        joined = " ".join(self._labels(p))
        self.assertIn("Via (in the visit order chosen", joined)
        self.assertIn("Wz", joined)
        self.assertIn("re-visits a star", joined)   # this fixture repeats Sol

    def test_plain_route_has_no_via_line_and_no_markers(self):
        p = self._panel()
        r = _via_jump_route()
        r = {**r, "via": [], "via_legs": [],
             "route": [{**h, "waypoint": False} for h in r["route"]]}
        p._render(r)
        self.assertEqual([row[2] for row in self._table_rows(p)],
                         ["Wz", "Sol", "Procyon"])
        joined = " ".join(self._labels(p))
        self.assertNotIn("Via (in the visit order chosen", joined)

    def test_unreachable_names_the_failed_leg_not_the_endpoints(self):
        p = self._panel()
        p._render(_unreachable_via_jump_route())
        joined = " ".join(self._labels(p))
        self.assertIn("No route from Sol to Vega", joined)   # the waypoint leg
        self.assertNotIn("No route from Sol to Procyon", joined)
        self.assertIn("Sol → Procyon route fails because of that leg", joined)

    def test_plain_unreachable_wording_unchanged(self):
        p = self._panel()
        p._render(_unreachable_jump_route())
        joined = " ".join(self._labels(p))
        self.assertIn("No route from Sol to Vega", joined)
        self.assertNotIn("because of that leg", joined)

    @unittest.skipUnless(_mpl_available(), "matplotlib not available")
    def test_find_box_appears_only_when_the_failed_chart_has_waypoints(self):
        from PySide6.QtWidgets import QLineEdit

        def _find_boxes(panel):
            # The O18 box lives on the viz container, above the tabs widget.
            w = getattr(panel, "_find_widget", None)
            return [] if w is None or not w.isVisibleTo(panel._viz_container) \
                else w.findChildren(QLineEdit)

        plain = self._panel()
        plain._render(_unreachable_jump_route())
        self.assertEqual(_find_boxes(plain), [])     # just the two endpoints

        withvia = self._panel()
        withvia._render(_unreachable_via_jump_route())
        self.assertTrue(_find_boxes(withvia))        # three terminals to find


_ROUTE_PANELS = ["MultiStopJourneyPanel", "OptimalTourPanel",
                 "NearestNeighborPanel", "FarthestFirstPanel",
                 "JumpRoutePanel", "JumpNetworkPanel",
                 "TradeRoutePlannerPanel"]


# ─────────────────────────────────────────────────────────────────────────────
# Per-panel description box: hidden by default, toggled by a Show/Hide
# Description button, rendered in the results pane and NOT wiped by a run.
# ─────────────────────────────────────────────────────────────────────────────
class RouteDescriptionTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self, cls_name):
        import gui.panels as panels
        return getattr(panels, cls_name)(_StubWindow())

    def test_every_panel_has_a_description_hidden_by_default(self):
        for cls_name in _ROUTE_PANELS:
            with self.subTest(cls_name):
                p = self._panel(cls_name)
                self.assertTrue(p._desc_box.text().strip(),
                                "panel has no DESCRIPTION text")
                self.assertTrue(p._desc_box.isHidden())
                self.assertEqual(p._desc_btn.text(), "Show Description")

    def test_button_toggles_visibility_and_label(self):
        for cls_name in _ROUTE_PANELS:
            with self.subTest(cls_name):
                p = self._panel(cls_name)
                p._desc_btn.click()
                self.assertFalse(p._desc_box.isHidden())
                self.assertEqual(p._desc_btn.text(), "Hide Description")
                p._desc_btn.click()
                self.assertTrue(p._desc_box.isHidden())
                self.assertEqual(p._desc_btn.text(), "Show Description")

    def test_description_lives_in_the_results_pane_and_survives_a_run(self):
        """It sits at the top of _tables_widget (where the data is drawn), and
        _clear_tables_layout must skip it — otherwise a Run would delete it and
        leave the toggle button pointing at a dead widget."""
        from gui.panels.route_planning import _clear_tables_layout
        for cls_name in _ROUTE_PANELS:
            with self.subTest(cls_name):
                p = self._panel(cls_name)
                self.assertIs(p._tables_layout.itemAt(0).widget(), p._desc_box)
                p._desc_btn.click()
                _clear_tables_layout(p)
                self.assertEqual(p._tables_layout.count(), 1)
                self.assertIs(p._tables_layout.itemAt(0).widget(), p._desc_box)
                self.assertFalse(p._desc_box.isHidden())   # stays shown

    def test_description_survives_a_full_render(self):
        p = self._panel("NearestNeighborPanel")
        p._desc_btn.click()
        p._render(_chain_result())
        self.assertIs(p._tables_layout.itemAt(0).widget(), p._desc_box)
        self.assertFalse(p._desc_box.isHidden())

    def test_error_render_keeps_the_description(self):
        p = self._panel("JumpRoutePanel")
        p._desc_btn.click()
        p._render({"error": "nope"})
        self.assertIs(p._tables_layout.itemAt(0).widget(), p._desc_box)
        self.assertFalse(p._desc_box.isHidden())


if __name__ == "__main__":
    unittest.main()
