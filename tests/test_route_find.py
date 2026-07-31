# tests/test_route_find.py — the O18 Find-Star box on the 7 Route Planning panels
# (ROUTE_FIND_PLAN.md).
#
# The route-chart refactor put all seven planners on the shared opt-18/19
# `_build_iso_chart_tab`, which gave them the O16 legend filter, the O17 isochrone
# control and the 3D presets — but not the O18 Find box, which stayed behind in
# distance_stars.py. This file covers the move + the behaviour it needed to work
# on route results.
#
# The load-bearing difference from opts 18/19: **the searchable set is the route
# star list (`panel._find_rows`), not the result table.** Four of the seven panels
# have leg-shaped `From|To` tables with no per-star row and pass no `link_view` at
# all, so the old table-driven find would have matched nothing there — and the ring
# was previously only ever a side effect of table selection, so those panels would
# have panned with no ring. Hence the direct `highlight_star` call (D3a).
#
# Every ring assertion also checks for a real ring ARTIST: the empty-plot canvas
# branch attaches an inert `highlight_star` that records the name while drawing
# nothing, so `highlighted_star()` alone is a false positive.

import os
# Qt must run headless under the test runner. Set before any PySide6 import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time
import unittest


def _mpl_available() -> bool:
    try:
        from gui.visualizations.plot_helpers import mpl_available
        return mpl_available()
    except Exception:
        return False


# ── fixtures ─────────────────────────────────────────────────────────────────

def _star(name, x, y, z, sp="G2V", color="#fff4c2", desig=""):
    import math
    return {"name": name, "desig": desig, "sp_type": sp, "color": color,
            "ly": math.sqrt(x * x + y * y + z * z), "x": x, "y": y, "z": z}


_SOL = _star("Sol", 0.0, 0.0, 0.0)
_ACEN = _star("Alpha Centauri", 3.0, 0.0, 0.0, "G2V", "#fff4c2", "GJ 559")
_BARNARD = _star("Barnard's Star", 3.0, 4.0, 0.0, "M4V", "#ff9d6c", "GJ 699")


def _legs(names):
    """Leg rows for the From|To-shaped panels (values are never asserted on)."""
    return [{"leg": i + 1, "origin": a, "dest": b, "distance_ly": 3.0,
             "ly_hr": 1.0, "times_c": 8765.8128, "hours": 3.0,
             "cumulative_hours": 3.0 * (i + 1), "travel_time": "3 Hours",
             "cumulative_time": "3 Hours"}
            for i, (a, b) in enumerate(zip(names, names[1:]))]


def _multi_stop(stars=None, names=None):
    stars = stars or [_SOL, _ACEN, _BARNARD]
    names = names or [s["name"] for s in stars]
    return {"legs": _legs(names), "total_ly": 7.0, "total_hours": 6.0,
            "total_time": "6 Hours", "stars": stars}


def _optimal_tour():
    return {**_multi_stop(), "naive_total_ly": 9.0, "optimized_total_ly": 7.0,
            "saved_ly": 2.0, "saved_pct": 22.2, "closed": False}


def _chain(stopped_early=False):
    return {
        "start_name": "Sol", "total_ly": 7.0, "stopped_early": stopped_early,
        "chain": [
            {"hop": 1, "step": 1, "star_name": "Alpha Centauri", "desig": "GJ 559",
             "sp_type": "G2V", "dist_from_prev_ly": 3.0, "cumulative_ly": 3.0,
             "sep_to_visited_ly": 3.0, "dist_from_start_ly": 3.0, "ly_from_sol": 3.0},
            {"hop": 2, "step": 2, "star_name": "Barnard's Star", "desig": "GJ 699",
             "sp_type": "M4V", "dist_from_prev_ly": 4.0, "cumulative_ly": 7.0,
             "sep_to_visited_ly": 4.0, "dist_from_start_ly": 5.0, "ly_from_sol": 5.0},
        ],
        "stars": [_SOL, _ACEN, _BARNARD],
    }


def _farthest_first(stopped_early=False):
    return {**_chain(stopped_early), "widest_ly": 5.0,
            "tree_edges": [{"from_index": 0, "to_index": 1},
                           {"from_index": 1, "to_index": 2}]}


def _mst():
    stars = [_SOL, _ACEN, _BARNARD]
    return {
        "nodes": [{"name": s["name"], "x": s["x"], "y": s["y"], "z": s["z"],
                   "sp_type": s["sp_type"], "desig": s["desig"]} for s in stars],
        "edges": [{"from": "Sol", "to": "Alpha Centauri", "distance_ly": 3.0},
                  {"from": "Alpha Centauri", "to": "Barnard's Star",
                   "distance_ly": 4.0}],
        "total_ly": 7.0, "stars": stars,
    }


def _jump_route(reachable=True):
    if not reachable:
        return {"origin_info": {"name": "Sol"}, "dest_info": {"name": "Vega"},
                "reachable": False, "optimize": "distance", "jumps": 0,
                "total_ly": 0.0, "direct_ly": 25.0, "route": [],
                "max_jump_ly": 2.0,
                "stars": [_SOL, _star("Vega", 25.0, 0.0, 0.0, "A0V", "#cad7ff")]}
    return {
        "origin_info": {"name": "Sol"}, "dest_info": {"name": "Barnard's Star"},
        "reachable": True, "optimize": "distance", "jumps": 2, "total_ly": 7.0,
        "direct_ly": 5.0, "max_jump_ly": 5.0,
        "route": [{"jump": 1, "from": "Sol", "to": "Alpha Centauri",
                   "jump_ly": 3.0, "cumulative_ly": 3.0},
                  {"jump": 2, "from": "Alpha Centauri", "to": "Barnard's Star",
                   "jump_ly": 4.0, "cumulative_ly": 7.0}],
        "stars": [_SOL, _ACEN, _BARNARD],
    }


def _jump_network(n_extra=0):
    """Tier-coloured nodes. `n_extra` pads the pool for the scale test."""
    stars = [_star("Sol", 0.0, 0.0, 0.0, "G2V", "#FFD700"),
             _star("Alpha Centauri", 3.0, 0.0, 0.0, "G2V", "#44cc88", "GJ 559"),
             _star("Barnard's Star", 3.0, 4.0, 0.0, "M4V", "#44cc88", "GJ 699")]
    tier1 = [{"star_name": "Alpha Centauri", "desig": "GJ 559", "sp_type": "G2V",
              "dist_from_start_ly": 3.0, "ly_from_sol": 3.0},
             {"star_name": "Barnard's Star", "desig": "GJ 699", "sp_type": "M4V",
              "dist_from_start_ly": 5.0, "ly_from_sol": 5.0}]
    for i in range(n_extra):
        nm = f"Filler {i}"
        stars.append(_star(nm, 6.0 + (i % 40) * 0.1, (i % 37) * 0.1,
                           (i % 29) * 0.1, "K3V", "#44cc88", f"GJ {9000 + i}"))
        tier1.append({"star_name": nm, "desig": f"GJ {9000 + i}", "sp_type": "K3V",
                      "dist_from_start_ly": 6.0, "ly_from_sol": 6.0})
    return {
        "start_name": "Sol", "max_jump_ly": 5.0, "max_jumps": None, "max_tier": 1,
        "reachable_count": len(stars), "total_in_pool": len(stars),
        "unreachable_count": 0,
        "tiers": [{"jumps": 0, "stars": [
                      {"star_name": "Sol", "desig": "", "sp_type": "G2V",
                       "dist_from_start_ly": 0.0, "ly_from_sol": 0.0}]},
                  {"jumps": 1, "stars": tier1}],
        "stars": stars,
    }


class _FakeNav:
    def show(self):
        pass

    def hide(self):
        pass


class _StubWindow:
    def __init__(self):
        self.nav_tree = _FakeNav()
        self._status = ""

    def statusBar(self):
        outer = self

        class _S:
            def showMessage(self, m):
                outer._status = m
        return _S()


# ── helpers ──────────────────────────────────────────────────────────────────

def _ring_artists(canvas):
    """The gold hollow highlight rings currently drawn on a canvas.

    Identified by the two properties `_attach_highlight_2d`/`_3d` give the ring
    and nothing else on these charts: zorder 30 and a gold edge colour. Checking
    for the artist — not just `highlighted_star()` — is what makes the assertion
    real: the empty-plot canvas branch attaches an inert highlighter that records
    a name while drawing no ring."""
    import matplotlib.colors as mcolors
    from gui.visualizations.plot_helpers import _HL_GOLD
    gold = mcolors.to_hex(_HL_GOLD).lower()
    out = []
    for ax in canvas.figure.axes:
        for coll in ax.collections:
            if coll.get_zorder() != 30:
                continue
            edges = coll.get_edgecolor()
            if len(edges) and mcolors.to_hex(edges[0]).lower() == gold:
                out.append(coll)
    return out


@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class _RouteFindBase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self, cls_name):
        import gui.panels as panels
        return getattr(panels, cls_name)(_StubWindow())

    def _rendered(self, cls_name, result):
        p = self._panel(cls_name)
        p._render(result)
        return p

    def _find(self, p, q):
        from gui.panels.diagram_tabs import _find_on_map
        p._find_input.setText(q)
        _find_on_map(p)

    def assertRinged(self, p, name):
        """Every registered canvas rings `name` — recorded, drawn AND visible.

        The visibility check is not padding: `_attach_highlight_2d/_3d` end with
        `ring.set_visible(name_cls.get(name) not in hidden)`, so a ring whose class
        is legend-filtered off exists as an artist but shows nothing — which is
        exactly the D6 failure mode (the start ★ is drawn outside the per-class
        scatter but IS in `name_cls`)."""
        self.assertTrue(p._link_canvases)
        for c in p._link_canvases:
            self.assertEqual(c.highlighted_star(), name)
            rings = _ring_artists(c)
            self.assertEqual(len(rings), 1)
            self.assertTrue(rings[0].get_visible())

    def assertNoRing(self, p):
        for c in p._link_canvases:
            self.assertIsNone(c.highlighted_star())
            self.assertEqual(_ring_artists(c), [])


# ─────────────────────────────────────────────────────────────────────────────
# The seven panels
# ─────────────────────────────────────────────────────────────────────────────

_CASES = [
    ("MultiStopJourneyPanel", _multi_stop),
    ("OptimalTourPanel", _optimal_tour),
    ("NearestNeighborPanel", _chain),
    ("FarthestFirstPanel", _farthest_first),
    ("JumpRoutePanel", _jump_route),
    ("JumpNetworkPanel", _jump_network),
    ("TradeRoutePlannerPanel", _mst),
]

# The three with one table row per star; the other four are From|To-shaped and
# pass no link_view, which is exactly why the ring cannot come from selection.
_LINKED = {"NearestNeighborPanel", "FarthestFirstPanel", "JumpNetworkPanel"}


class RouteFindBoxTest(_RouteFindBase):

    def test_every_panel_gets_a_find_box(self):
        for cls_name, fixture in _CASES:
            with self.subTest(cls_name):
                p = self._rendered(cls_name, fixture())
                self.assertIsNotNone(getattr(p, "_find_widget", None))
                self.assertIsNotNone(getattr(p, "_find_input", None))
                self.assertIs(p._find_widget.parent(), p._viz_container)

    def test_find_rings_every_canvas_on_every_panel(self):
        """Gate 1 — the ring is applied directly, so it lands on the four panels
        with no linked table too."""
        for cls_name, fixture in _CASES:
            with self.subTest(cls_name):
                p = self._rendered(cls_name, fixture())
                self._find(p, "barnard")
                self.assertRinged(p, "Barnard's Star")
                self.assertEqual(p._find_readout.text(), "Found: Barnard's Star")

    def test_clear_drops_the_ring_on_every_panel(self):
        """Gate 2."""
        from gui.panels.diagram_tabs import _clear_find
        for cls_name, fixture in _CASES:
            with self.subTest(cls_name):
                p = self._rendered(cls_name, fixture())
                self._find(p, "barnard")
                self.assertRinged(p, "Barnard's Star")
                _clear_find(p)
                self.assertNoRing(p)
                self.assertEqual(p._find_input.text(), "")
                self.assertEqual(p._find_readout.text(), "")
                self.assertEqual(p._find_matches, [])

    def test_find_pans_both_charts_to_the_star(self):
        """`center_on` is what makes find useful on a busy chart; assert it on the
        3D canvas too, whose centring is a separate implementation."""
        p = self._rendered("TradeRoutePlannerPanel", _mst())
        before = [(c.figure.axes[0].get_xlim(), c.figure.axes[0].get_ylim())
                  for c in p._link_canvases]
        self._find(p, "barnard")
        after = [(c.figure.axes[0].get_xlim(), c.figure.axes[0].get_ylim())
                 for c in p._link_canvases]
        self.assertEqual(len(before), 2)                  # 2D chart + 3D chart
        for b, a in zip(before, after):
            self.assertNotEqual(b, a)

    def test_designation_match(self):
        """The route star dicts carry `desig`, so designations are searchable on
        the leg-shaped panels too — where no table column holds them."""
        p = self._rendered("TradeRoutePlannerPanel", _mst())
        self._find(p, "gj 699")
        self.assertRinged(p, "Barnard's Star")

    def test_find_also_selects_the_row_when_a_table_is_linked(self):
        """D3 — table selection is an additive extra on the star-per-row panels."""
        for cls_name, fixture in _CASES:
            with self.subTest(cls_name):
                p = self._rendered(cls_name, fixture())
                self._find(p, "barnard")
                view = getattr(p, "_link_view", None)
                if cls_name not in _LINKED:
                    self.assertIsNone(view)
                    continue
                self.assertIsNotNone(view)
                sel = view.selectionModel().selectedRows()
                self.assertTrue(sel)
                row = sel[0].row()
                self.assertEqual(
                    view.model().item(row, p._link_name_col).text(),
                    "Barnard's Star")

    def test_no_match_sets_status_and_keeps_the_ring(self):
        p = self._rendered("TradeRoutePlannerPanel", _mst())
        self._find(p, "barnard")
        self._find(p, "zzzzz")
        self.assertEqual(p._find_readout.text(), "No match")
        self.assertIn("No star matching", p.window._status)
        self.assertRinged(p, "Barnard's Star")      # unchanged, not cleared

    def test_start_star_is_not_findable(self):
        """D6 — stars[0] (the gold ★) is excluded, matching opts 18/19 where the
        centre star has no table row. It is drawn outside the O16 per-class
        scatter but IS in the ring's name→class map, so a legend filter would
        suppress its ring while the ★ stayed visible."""
        for cls_name, fixture in _CASES:
            with self.subTest(cls_name):
                p = self._rendered(cls_name, fixture())
                self.assertNotIn("Sol", [n for n, _ in p._find_rows])
                self._find(p, "Sol")
                self.assertEqual(p._find_readout.text(), "No match")


class RouteFindEdgeCaseTest(_RouteFindBase):

    def test_multi_stop_revisit_dedupes(self):
        """Gate 6 / D2 — Sol → Sirius → Sol is one node per typed stop, but the
        canvases' coord maps are name-keyed, so the duplicate collapses to one
        dot. Without dedupe a find would read '1 of 2' and centre twice on it."""
        sirius = _star("Sirius", 8.6, 0.0, 0.0, "A1V", "#cad7ff")
        # A revisited non-start star: it appears twice in `stars`, one dot.
        p = self._rendered("MultiStopJourneyPanel",
                           _multi_stop(stars=[_SOL, sirius, _ACEN, sirius],
                                       names=["Sol", "Sirius", "Alpha Centauri",
                                              "Sirius"]))
        self.assertEqual([n for n, _ in p._find_rows],
                         ["Sirius", "Alpha Centauri"])
        self._find(p, "sirius")
        self.assertEqual(p._find_readout.text(), "Found: Sirius")
        self.assertNotIn("of 2", p._find_readout.text())

        # A route that RETURNS to its start: the start recurs at a later index,
        # but it is the gold ★ either way, so it stays out (D6 by name, not index).
        p2 = self._rendered("MultiStopJourneyPanel",
                            _multi_stop(stars=[_SOL, sirius, _SOL],
                                        names=["Sol", "Sirius", "Sol"]))
        self.assertEqual([n for n, _ in p2._find_rows], ["Sirius"])

    def test_unreachable_jump_route_has_no_find_box(self):
        """Gate 4 / D7 — the unreachable shape builds no table and charts just the
        two endpoints; nothing to find, same reasoning as opts 17/20/21."""
        p = self._rendered("JumpRoutePanel", _jump_route(reachable=False))
        self.assertTrue(p._viz_tabs_widget.count() > 0)   # charts still built
        self.assertEqual(p._find_rows, [])
        self.assertIsNone(getattr(p, "_find_widget", None))

    def test_a_result_with_no_find_box_hides_the_previous_one(self):
        """`_viz_container` and `_find_widget` both outlive a render, so a result
        that builds charts but no find box (reachable Jump Route → unreachable one)
        must not leave the previous run's box on screen carrying its old query over
        an empty searchable set. `_prepare_render` hides it; `_add_find_box` shows
        it again for results that have one.

        Note `assertEqual(p._find_rows, [])` alone would be a tautology here —
        `_prepare_render` empties it on every render regardless — so the widget's
        visibility is the load-bearing assertion."""
        p = self._rendered("JumpRoutePanel", _jump_route(reachable=True))
        self._find(p, "barnard")
        self.assertFalse(p._find_widget.isHidden())
        self.assertTrue(p._find_input.text())

        p._render(_jump_route(reachable=False))
        self.assertTrue(p._viz_tabs_widget.count() > 0)   # charts, but no box
        self.assertTrue(p._find_widget.isHidden())
        self.assertEqual(p._find_rows, [])

        p._render(_jump_route(reachable=True))            # …and back again
        self.assertFalse(p._find_widget.isHidden())
        self.assertEqual(p._find_input.text(), "")        # reuse branch cleared it
        self.assertEqual(p._find_readout.text(), "")

    def test_rerender_reuses_the_same_box_and_clears_it(self):
        """The normal path — every Run renders twice — takes `_add_find_box`'s
        reuse branch, which must keep the widget and wipe the stale query/readout."""
        p = self._rendered("TradeRoutePlannerPanel", _mst())
        first = p._find_widget
        self._find(p, "barnard")
        p._render(_mst())
        self.assertIs(p._find_widget, first)              # reused, not rebuilt
        self.assertFalse(p._find_widget.isHidden())
        self.assertEqual(p._find_input.text(), "")
        self.assertEqual(p._find_readout.text(), "")

    def test_prepare_render_clears_the_whole_cycle(self):
        p = self._rendered("TradeRoutePlannerPanel", _mst())
        self._find(p, "a")
        self.assertTrue(p._find_matches)
        p._render({"error": "nope"})
        self.assertEqual(p._find_rows, [])
        self.assertEqual(p._find_matches, [])
        self.assertEqual(p._find_idx, 0)

    def test_find_with_an_empty_searchable_set_is_a_no_op(self):
        """The `_find_rows` guard. Unreachable through the UI once the box is
        hidden, but it is what keeps `_find_on_map` off the `deleteLater`'d
        canvases `_link_canvases` still points at after an error render."""
        from gui.panels.diagram_tabs import _find_on_map
        p = self._rendered("TradeRoutePlannerPanel", _mst())
        readout = p._find_readout
        p._render({"error": "nope"})
        p._find_input.setText("barnard")
        _find_on_map(p)                                   # must not raise
        self.assertEqual(readout.text(), "")

    def test_stopped_early_chain_is_still_findable(self):
        """Gate 4 — stopped_early is a normal result, not an error."""
        for cls_name, fixture in [("NearestNeighborPanel", _chain),
                                  ("FarthestFirstPanel", _farthest_first)]:
            with self.subTest(cls_name):
                p = self._rendered(cls_name, fixture(True))
                self._find(p, "barnard")
                self.assertRinged(p, "Barnard's Star")

    def test_empty_chain_gets_no_chart_and_no_find_box(self):
        p = self._rendered("NearestNeighborPanel", {**_chain(), "chain": []})
        self.assertEqual(p._viz_tabs_widget.count(), 0)
        self.assertIsNone(getattr(p, "_find_widget", None))

    def test_error_render_clears_the_searchable_set(self):
        """`_prepare_render` drops `_find_rows`: every error path returns before
        the chart tabs are built, so a stale set would otherwise survive."""
        p = self._rendered("TradeRoutePlannerPanel", _mst())
        self.assertTrue(p._find_rows)
        p._render({"error": "nope"})
        self.assertEqual(p._find_rows, [])
        self.assertEqual(p._viz_tabs_widget.count(), 0)

    def test_second_render_replaces_the_searchable_set(self):
        p = self._rendered("TradeRoutePlannerPanel", _mst())
        other = _star("Vega", 25.0, 0.0, 0.0, "A0V", "#cad7ff")
        p._render({**_mst(), "stars": [_SOL, other],
                   "nodes": [{"name": "Sol", "x": 0.0, "y": 0.0, "z": 0.0,
                              "sp_type": "G2V", "desig": ""},
                             {"name": "Vega", "x": 25.0, "y": 0.0, "z": 0.0,
                              "sp_type": "A0V", "desig": ""}],
                   "edges": [{"from": "Sol", "to": "Vega", "distance_ly": 25.0}]})
        self.assertEqual([n for n, _ in p._find_rows], ["Vega"])
        self._find(p, "barnard")
        self.assertEqual(p._find_readout.text(), "No match")

    def test_render_after_reset_survives_stale_find_widget(self):
        """Gate 5 — the `_add_find_box` stale-reference guard, on a route panel."""
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QApplication
        p = self._rendered("TradeRoutePlannerPanel", _mst())
        stale, old_container = p._find_widget, p._container
        p.reset()
        QApplication.sendPostedEvents(old_container, QEvent.Type.DeferredDelete)
        p._render(_mst())                               # must not raise
        self.assertTrue(p._viz_tabs_widget.count() > 0)
        self.assertFalse(p._show_diagrams_btn.isHidden())
        self.assertIsNot(p._find_widget, stale)


class RouteFindIsochroneTest(_RouteFindBase):
    """Gate 3 / D9 — an isochrone Apply swaps the canvas and gives it a fresh
    `view0`, so a find cycle left in flight would make the next identical Find
    advance instead of re-centring, and a later Clear would silently fail to
    restore the view."""

    def _iso_buttons(self, p, tab_name="Star Chart"):
        from PySide6.QtWidgets import QLineEdit, QPushButton
        for i in range(p._viz_tabs_widget.count()):
            if p._viz_tabs_widget.tabText(i) != tab_name:
                continue
            w = p._viz_tabs_widget.widget(i)
            vel = w.findChildren(QLineEdit)[0]
            btns = {b.text(): b for b in w.findChildren(QPushButton)}
            return vel, btns
        self.fail(f"no {tab_name} tab")

    def test_apply_resets_the_find_cycle(self):
        p = self._rendered("MultiStopJourneyPanel", _multi_stop())
        self._find(p, "a")                        # matches both non-start stars
        self.assertIn("1 of 2", p._find_readout.text())
        first = p._find_matches[0]

        vel, btns = self._iso_buttons(p)
        vel.setText("10")
        btns["Apply"].click()
        self.assertEqual(p._find_matches, [])
        self.assertEqual(p._find_idx, 0)

        self._find(p, "a")                        # re-centres, does NOT advance
        self.assertIn("1 of 2", p._find_readout.text())
        self.assertRinged(p, first)

    def test_apply_clears_the_stale_readout(self):
        """The readout must go with the cycle state. The rebuilt canvas is at its
        default un-centred view and `_find_idx` is back at 0, so a leftover
        "2 of 2 matches — X" would describe a state that no longer exists — and the
        next Find with that query re-centres match **1** while the label claimed 2."""
        p = self._rendered("MultiStopJourneyPanel", _multi_stop())
        self._find(p, "a")
        self._find(p, "a")
        self.assertIn("2 of 2", p._find_readout.text())
        vel, btns = self._iso_buttons(p)
        vel.setText("10")
        btns["Apply"].click()
        self.assertEqual(p._find_readout.text(), "")
        self.assertEqual(p._find_input.text(), "a")   # the query itself survives

    def test_isochrone_clear_also_resets_the_find_cycle(self):
        """The isochrone Clear button routes through the same `_rebuild`, so it
        swaps the canvas too and must reset the cycle for the same reason Apply
        does."""
        p = self._rendered("MultiStopJourneyPanel", _multi_stop())
        vel, btns = self._iso_buttons(p)
        vel.setText("10")
        btns["Apply"].click()
        self._find(p, "a")
        self.assertTrue(p._find_matches)
        btns["Clear"].click()
        self.assertEqual(p._find_matches, [])
        self.assertEqual(p._find_idx, 0)

    def test_clear_after_apply_restores_the_rebuilt_view(self):
        from gui.panels.diagram_tabs import _clear_find
        p = self._rendered("MultiStopJourneyPanel", _multi_stop())
        vel, btns = self._iso_buttons(p)
        vel.setText("10")
        btns["Apply"].click()
        chart = next(c for c in p._link_canvases
                     if "3d" not in type(c.figure.axes[0]).__name__.lower())
        before = (chart.figure.axes[0].get_xlim(), chart.figure.axes[0].get_ylim())
        self._find(p, "barnard")
        self.assertNotEqual((chart.figure.axes[0].get_xlim(),
                             chart.figure.axes[0].get_ylim()), before)
        _clear_find(p)
        self.assertEqual((chart.figure.axes[0].get_xlim(),
                          chart.figure.axes[0].get_ylim()), before)


class RouteFindLegendTest(_RouteFindBase):
    """Gate 7 — a find must never un-hide a legend-filtered class it did not
    match. (The reveal step is keyed off the matched star's own class.)"""

    def _chart(self, p):
        return next(c for c in p._link_canvases
                    if c.figure.axes[0].get_legend() is not None
                    and "3d" not in type(c.figure.axes[0]).__name__.lower())

    def test_find_only_reveals_the_matched_stars_class(self):
        from matplotlib.backend_bases import PickEvent, MouseEvent
        p = self._rendered("TradeRoutePlannerPanel", _mst())
        sc = self._chart(p)
        ax = sc.figure.axes[0]
        leg = ax.get_legend()
        texts = [t.get_text() for t in leg.get_texts()]
        self.assertIn("Class M", texts)             # Barnard
        self.assertIn("Class G", texts)             # Alpha Cen
        handle = leg.legend_handles[texts.index("Class G")]
        me = MouseEvent("button_press_event", sc, 0, 0)
        sc.callbacks.process("pick_event", PickEvent("pick_event", sc, me, handle))
        self.assertIn("G", _hidden_classes(ax))

        self._find(p, "barnard")                    # an M star
        self.assertIn("G", _hidden_classes(ax))     # G stays hidden
        self.assertRinged(p, "Barnard's Star")

    def test_find_reveals_the_matched_stars_own_hidden_class(self):
        from matplotlib.backend_bases import PickEvent, MouseEvent
        p = self._rendered("TradeRoutePlannerPanel", _mst())
        sc = self._chart(p)
        ax = sc.figure.axes[0]
        leg = ax.get_legend()
        texts = [t.get_text() for t in leg.get_texts()]
        handle = leg.legend_handles[texts.index("Class M")]
        me = MouseEvent("button_press_event", sc, 0, 0)
        sc.callbacks.process("pick_event", PickEvent("pick_event", sc, me, handle))
        self.assertIn("M", _hidden_classes(ax))
        self._find(p, "barnard")
        self.assertNotIn("M", _hidden_classes(ax))

    def test_jump_network_has_no_legend_reveal_and_still_finds(self):
        """D8 — JumpNetworkPanel passes legend_filter=False (its dots are
        per-TIER coloured), so `_o16_reveal_class` does not exist. The getattr
        guard covers it and find still works."""
        p = self._rendered("JumpNetworkPanel", _jump_network())
        for c in p._link_canvases:
            self.assertIsNone(getattr(c, "_o16_reveal_class", None))
        self._find(p, "barnard")
        self.assertRinged(p, "Barnard's Star")


class RouteFindScaleTest(_RouteFindBase):
    """Gate 8 — Jump Network is the only planner that can return thousands of
    nodes. Find is a linear scan over `_find_rows`, so it must stay trivial."""

    def test_find_over_a_thousand_nodes(self):
        p = self._rendered("JumpNetworkPanel", _jump_network(n_extra=1200))
        self.assertGreaterEqual(len(p._find_rows), 1000)
        t0 = time.perf_counter()
        self._find(p, "filler 1100")                  # a unique late-pool match
        elapsed = time.perf_counter() - t0
        self.assertEqual(p._find_readout.text(), "Found: Filler 1100")
        self.assertRinged(p, "Filler 1100")
        # A linear scan of ~1200 short strings is sub-millisecond; the canvas
        # centring dominates. 0.5 s still fails an accidentally quadratic scan
        # (~1.4M comparisons) by a wide margin while tolerating slow CI.
        self.assertLess(elapsed, 0.5)


# ─────────────────────────────────────────────────────────────────────────────
# Opts 18/19 — must come out byte-identical: the searchable set is now built from
# the table via `_link_name_col`, which is 0 there (the hardcoded item(r, 0) /
# item(r, 1) it replaces).
# ─────────────────────────────────────────────────────────────────────────────
@unittest.skipUnless(_mpl_available(), "matplotlib/PySide6 not available")
class OptEighteenNineteenUnchangedTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self):
        import gui.panels as panels
        from gui.panels.distance_stars import _add_map_tabs
        p = panels.StarsWithinDistanceSolPanel(_StubWindow())
        view = p.make_table(
            ["Star Name", "Star Designations", "Spectral Type", "Distance (LY)"],
            [["*  61 Cyg A", "GJ 820 A", "K5V", "11.40"],
             ["NAME Barnard's star", "GJ 699", "M4V", "5.96"]])
        p._link_view = view
        map_stars = [
            {"name": "Sol", "desig": "", "sp_type": "G2V", "color": "#fff4c2",
             "ly": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"name": "*  61 Cyg A", "desig": "GJ 820 A", "sp_type": "K5V",
             "color": "#ffd2a1", "ly": 11.4, "x": 6.5, "y": 6.1, "z": 7.1},
            {"name": "NAME Barnard's star", "desig": "GJ 699", "sp_type": "M4V",
             "color": "#ff9d6c", "ly": 5.96, "x": -0.06, "y": 5.94, "z": 0.49},
        ]
        _add_map_tabs(p, map_stars, 15.0, "title", {"stars": []})
        return p

    def test_the_moved_names_still_resolve_from_distance_stars(self):
        """D1's re-export. `_norm_find` / `_find_on_map` / `_clear_find` have no
        in-module use in distance_stars — they exist purely so
        `test_viz_phase_o.py::O18FindTest` can keep importing them from there, so
        an "unused import" cleanup would silently break four tests with nothing
        else to catch it."""
        import gui.panels.distance_stars as ds
        import gui.panels.diagram_tabs as dt
        for name in ("_norm_find", "_find_on_map", "_clear_find", "_add_find_box"):
            self.assertIs(getattr(ds, name), getattr(dt, name), name)

    def test_duplicate_table_names_collapse_to_one_entry(self):
        """The one place opts 18/19 are NOT byte-identical: `_find_rows_from_table`
        dedupes, so two rows sharing a Star Name used to read "1 of 2" and cycle
        between them. That was already a lie — the canvases' coord maps are
        name-keyed, so both cycle steps centred the same dot."""
        import gui.panels as panels
        from gui.panels.distance_stars import _add_map_tabs
        from gui.panels.diagram_tabs import _find_on_map
        p = panels.StarsWithinDistanceSolPanel(_StubWindow())
        view = p.make_table(
            ["Star Name", "Star Designations", "Spectral Type", "Distance (LY)"],
            [["*  61 Cyg A", "GJ 820 A", "K5V", "11.40"],
             ["*  61 Cyg A", "GJ 820 A", "K5V", "11.41"]])   # same name twice
        p._link_view = view
        _add_map_tabs(p, [
            {"name": "Sol", "desig": "", "sp_type": "G2V", "color": "#fff4c2",
             "ly": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"name": "*  61 Cyg A", "desig": "GJ 820 A", "sp_type": "K5V",
             "color": "#ffd2a1", "ly": 11.4, "x": 6.5, "y": 6.1, "z": 7.1},
        ], 15.0, "title", {"stars": []})
        self.assertEqual(len(p._find_rows), 1)
        p._find_input.setText("61 Cyg")
        _find_on_map(p)
        self.assertEqual(p._find_readout.text(), "Found: *  61 Cyg A")

    def test_cycle_order_follows_a_user_sort(self):
        """`make_table` enables sorting and `QStandardItemModel.sort` physically
        reorders rows, so the old live table scan cycled matches in the order the
        user is actually looking at. A render-time snapshot would cycle in render
        order instead — hence `_find_rows_live` re-derives on every find. Route
        panels have no per-star table to follow, so they keep the snapshot."""
        from PySide6.QtCore import Qt
        from gui.panels.diagram_tabs import _find_on_map
        import gui.panels as panels
        from gui.panels.distance_stars import _add_map_tabs
        p = panels.StarsWithinDistanceSolPanel(_StubWindow())
        rows = [["Alpha Y", "GJ 1", "G2V", "3.00"],
                ["Alpha Z", "GJ 2", "K5V", "2.00"],
                ["Alpha X", "GJ 3", "M4V", "1.00"]]
        view = p.make_table(
            ["Star Name", "Star Designations", "Spectral Type", "Distance (LY)"],
            rows)
        p._link_view = view
        _add_map_tabs(p, [
            {"name": "Sol", "desig": "", "sp_type": "G2V", "color": "#fff4c2",
             "ly": 0.0, "x": 0.0, "y": 0.0, "z": 0.0}] + [
            {"name": r[0], "desig": r[1], "sp_type": r[2], "color": "#ffd2a1",
             "ly": float(r[3]), "x": float(r[3]), "y": 0.0, "z": 0.0}
            for r in rows], 15.0, "title", {"stars": []})
        self.assertTrue(p._find_rows_live)

        view.sortByColumn(3, Qt.SortOrder.AscendingOrder)   # by distance
        p._find_input.setText("alpha")
        _find_on_map(p)
        self.assertEqual(p._find_readout.text(),
                         "1 of 3 matches — Alpha X")        # nearest, i.e. row 0

    def test_route_panels_do_not_re_derive_from_a_table(self):
        p = self._panel_route()
        self.assertFalse(getattr(p, "_find_rows_live", False))

    def _panel_route(self):
        import gui.panels as panels
        p = panels.NearestNeighborPanel(_StubWindow())
        p._render(_chain())
        return p

    def test_find_rows_come_from_the_table_with_name_col_zero(self):
        p = self._panel()
        self.assertEqual(p._link_name_col, 0)
        self.assertEqual(p._find_rows,
                         [("*  61 Cyg A", "GJ 820 A"),
                          ("NAME Barnard's star", "GJ 699")])

    def test_find_still_works_by_name_and_designation(self):
        from gui.panels.diagram_tabs import _find_on_map
        p = self._panel()
        p._find_input.setText("61 Cyg A")           # single-space vs stored double
        _find_on_map(p)
        self.assertEqual(p._find_readout.text(), "Found: *  61 Cyg A")
        p._find_input.setText("gj 699")
        _find_on_map(p)
        self.assertEqual(p._find_readout.text(), "Found: NAME Barnard's star")


def _hidden_classes(ax):
    """The set of spectral classes whose per-class scatter is currently hidden."""
    out = set()
    leg = ax.get_legend()
    if leg is None:
        return out
    for txt in leg.get_texts():
        if txt.get_alpha() not in (None, 1.0):
            out.add(txt.get_text().replace("Class ", ""))
    return out


if __name__ == "__main__":
    unittest.main()
