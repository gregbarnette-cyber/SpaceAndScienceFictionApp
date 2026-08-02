# tests/test_oec_view.py — the OEC System View (OEC_SYSTEM_VIEW_PLAN).
#
# Stage 1: the 10-column Data tree — per-tag column population, status badges +
# M·sin i, hide-empty columns, the D5 expand rule, and the T7 single-conversion-
# constant guard (asserted on the VALUE, not the name — a name-based test passes
# against the pre-existing `_M_JUP_EARTH` duplicate).
#
# Qt-gated via tests/_oeccheck.py; the fixture half needs no downloaded cache.

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import re
import unittest
from pathlib import Path

from tests._oeccheck import qt_available
from tests.test_oec import OecTestBase

_REPO = Path(__file__).resolve().parents[1]


# §F — "OecTestBase extended with a photometry-rich single star, a
# no-`semimajoraxis` planet, a hot (A-type) host, and a satellite".
#
# Kept as a SEPARATE fixture in this file rather than as an edit to
# `tests/test_oec.py`'s `_FIXTURE`: that file is the §0 tripwire, and growing a
# shared fixture changes what every test in it sees.
_VIEW_FIXTURE = """<systems>
  <system>
    <name>Photometric</name>
    <rightascension>01 44 04.08</rightascension>
    <declination>-15 56 14.93</declination>
    <constellation>Testus</constellation>
    <distance errorminus="0.0023" errorplus="0.0023">3.6502</distance>
    <star>
      <name>Photometric A</name>
      <name>HD 999</name>
      <name>HIP 999</name>
      <spectraltype>G8.5 V</spectraltype>
      <mass errorminus="0.012" errorplus="0.012">0.783</mass>
      <radius errorminus="0.004" errorplus="0.0040">0.793</radius>
      <temperature errorminus="50" errorplus="50">5344</temperature>
      <metallicity errorminus="0.05" errorplus="0.05">-0.55</metallicity>
      <age>5.8</age>
      <magU>5.5</magU><magB>4.22</magB><magV>3.50</magV><magR>2.88</magR>
      <magI>2.41</magI><magJ>2.15</magJ><magH>1.80</magH><magK>1.68</magK>
      <planet>
        <name>Photometric A b</name>
        <mass>0.00629</mass>
        <period>20.0</period>
        <periastron>395.3</periastron>
        <list>Confirmed planets</list>
        <satellite>
          <name>Photometric A b I</name>
          <mass>0.01</mass>
          <radius>0.3</radius>
          <semimajoraxis>0.002</semimajoraxis>
          <period>3.5</period>
          <eccentricity>0.01</eccentricity>
          <inclination>2.0</inclination>
          <periastron>140.0</periastron>
          <ascendingnode>77.0</ascendingnode>
          <longitude>12.0</longitude>
          <tilt>1.5</tilt>
        </satellite>
      </planet>
    </star>
  </system>

  <system>
    <name>Full Circumbinary</name>
    <distance>60.0</distance>
    <binary>
      <name>FCB AB</name>
      <semimajoraxis>0.2</semimajoraxis>
      <eccentricity>0.16</eccentricity>
      <planet>
        <name>FCB AB b</name>
        <mass>0.3</mass>
        <radius>0.8</radius>
        <period>228.8</period>
        <list>Confirmed planets</list>
      </planet>
      <star>
        <name>FCB A</name>
        <mass>0.69</mass><radius>0.65</radius><temperature>4450</temperature>
      </star>
      <star>
        <name>FCB B</name>
        <mass>0.20</mass><radius>0.23</radius><temperature>3300</temperature>
      </star>
    </binary>
  </system>

  <system>
    <name>Hot Host</name>
    <distance>25.0</distance>
    <star>
      <name>Hot A</name>
      <spectraltype>A5V</spectraltype>
      <mass>2.1</mass>
      <radius>1.8</radius>
      <temperature>9000</temperature>
      <planet>
        <name>Hot A b</name>
        <mass>2.0</mass>
        <period>300</period>
        <list>Confirmed planets</list>
      </planet>
    </star>
  </system>
</systems>"""


class OecViewFixtureBase(OecTestBase):
    """`OecTestBase` against the extended view fixture (see `_VIEW_FIXTURE`)."""

    def setUp(self):
        import xml.etree.ElementTree as ET
        import core.databases as databases
        super().setUp()
        self._root = ET.fromstring(_VIEW_FIXTURE)
        databases._oec_get_root = lambda force_refresh=False: self._root
        databases._OEC_DATA = None


# ── T7 — one conversion constant, by value (no Qt needed) ────────────────────
class ConversionConstantTests(unittest.TestCase):
    """B.2: 317.828 / 11.209 may appear exactly once — in core/shared.py. Scoped to
    non-test source under core/ and gui/ (tests/test_query_phase_t.py passes 317.828
    as an *argument*, 1 M♃ expressed in M⊕, which is not a copy of the constant)."""

    LITERALS = ("317.828", "11.209")

    def _sources(self):
        for pkg in ("core", "gui"):
            for p in sorted((_REPO / pkg).rglob("*.py")):
                yield p

    def test_one_conversion_constant_by_value(self):
        hits = []
        for path in self._sources():
            text = path.read_text(encoding="utf-8")
            for lit in self.LITERALS:
                for m in re.finditer(re.escape(lit), text):
                    line = text[:m.start()].count("\n") + 1
                    hits.append((path.relative_to(_REPO).as_posix(), line, lit))
        offenders = [h for h in hits if h[0] != "core/shared.py"]
        self.assertEqual(offenders, [],
                         f"Jupiter→Earth literals duplicated outside core/shared.py: {offenders}")
        self.assertEqual(len(hits), 2, f"expected exactly one definition of each: {hits}")

    def test_consumers_import_the_shared_pair(self):
        from core.shared import M_JUP_EARTH, R_JUP_EARTH
        from core.calculators import _M_JUP_EARTH
        from gui.panels.catalogs import _MJUP_MEARTH, _RJUP_REARTH
        self.assertEqual(_M_JUP_EARTH, M_JUP_EARTH)
        self.assertEqual(_MJUP_MEARTH, M_JUP_EARTH)
        self.assertEqual(_RJUP_REARTH, R_JUP_EARTH)


# ── Stage 1 — the columnar tree ──────────────────────────────────────────────
@unittest.skipUnless(qt_available(), "PySide6 / matplotlib not available")
class OecTreeColumnTests(OecTestBase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _item(self, name, tag, name_sub=None, ctx=None):
        from gui.panels.catalogs import _oec_tree_item
        system = self._system(name)
        # Held on self: an unparented root item is garbage-collected with its
        # children, invalidating the C++ objects mid-assertion.
        self._root_item = root = _oec_tree_item(system, ctx)
        want = self._find(system, tag, name_sub)[0]
        found = self._walk_for(root, want)
        self.assertIsNotNone(found, f"{tag} {name_sub} not in the tree")
        return found

    def _walk_for(self, item, node):
        from gui.panels.catalogs import _oec_item_node
        if _oec_item_node(item) is node:
            return item
        for i in range(item.childCount()):
            hit = self._walk_for(item.child(i), node)
            if hit is not None:
                return hit
        return None

    # ── T1 — columns per tag, no bleed ──
    def test_star_row_populates_mass_radius_temperature(self):
        from gui.panels.catalogs import (_OEC_COL_M, _OEC_COL_R, _OEC_COL_T,
                                         _OEC_COL_TYPE, _OEC_COL_P, _OEC_COL_A)
        star = self._item("Single Star", "star")
        self.assertIn("1.0", star.text(_OEC_COL_M))
        self.assertIn("M☉", star.text(_OEC_COL_M))
        self.assertIn("R☉", star.text(_OEC_COL_R))
        self.assertEqual(star.text(_OEC_COL_T), "5800")
        self.assertEqual(star.text(_OEC_COL_TYPE), "G2V")
        # no planet-only values bleed into the star row
        self.assertEqual(star.text(_OEC_COL_P), "")
        self.assertEqual(star.text(_OEC_COL_A), "")

    def test_planet_row_populates_period_sma_ecc(self):
        from gui.panels.catalogs import _OEC_COL_P, _OEC_COL_E, _OEC_COL_TYPE
        planet = self._item("Single Star", "planet")
        self.assertEqual(planet.text(_OEC_COL_P), "100")
        self.assertEqual(planet.text(_OEC_COL_TYPE), "planet")
        self.assertIn("0.2", planet.text(_OEC_COL_E))     # bound-only eccentricity

    def test_system_row_carries_constellation_and_distance(self):
        from gui.panels.catalogs import _oec_tree_item, _OEC_COL_NODE, _OEC_COL_TYPE
        root = _oec_tree_item(self._system("Single Star"))
        self.assertEqual(root.text(_OEC_COL_TYPE), "system")
        self.assertIn("Testus", root.text(_OEC_COL_NODE))
        self.assertIn("10.0", root.text(_OEC_COL_NODE))

    def test_satellite_row_populates_earth_units(self):
        from gui.panels.catalogs import _OEC_COL_M, _OEC_COL_R, _OEC_COL_TYPE
        moon = self._item("Hierarchy", "satellite")
        self.assertEqual(moon.text(_OEC_COL_TYPE), "satellite")
        self.assertIn("M⊕", moon.text(_OEC_COL_M))
        self.assertIn("R⊕", moon.text(_OEC_COL_R))

    def test_binary_row_populates_sma_and_separation(self):
        from gui.panels.catalogs import _OEC_COL_A, _OEC_COL_NODE, _OEC_COL_TYPE
        binary = self._item("Circumbinary", "binary")
        self.assertEqual(binary.text(_OEC_COL_TYPE), "binary")
        self.assertEqual(binary.text(_OEC_COL_A), "0.2")
        sep = self._item("Binary S", "binary")
        self.assertIn("sep", sep.text(_OEC_COL_NODE))
        self.assertIn("arcsec", sep.text(_OEC_COL_NODE))   # first of the repeated pair

    # ── T2 — badges + M·sin i ──
    def test_multi_status_renders_both(self):
        from gui.panels.catalogs import _OEC_COL_NODE
        planet = self._item("Binary S", "planet")
        txt = planet.text(_OEC_COL_NODE)
        self.assertIn("Confirmed planets", txt)
        self.assertIn("S-type", txt)

    def test_msini_mass_keeps_its_label(self):
        from gui.panels.catalogs import _OEC_COL_M
        planet = self._item("Single Star", "planet")
        self.assertTrue(planet.text(_OEC_COL_M).startswith("M·sin i"))

    # ── D1 auto units, per node ──
    def test_auto_units_pick_earth_below_the_threshold(self):
        from gui.panels.catalogs import _OEC_COL_M
        small = self._item("Hierarchy", "planet")      # 1.7 M_jup → stays Jupiter
        self.assertIn("M♃", small.text(_OEC_COL_M))
        rogue = self._item("Rogue One", "planet")      # 6.0 M_jup
        self.assertIn("M♃", rogue.text(_OEC_COL_M))
        forced = self._item("Rogue One", "planet", ctx={"units": "earth"})
        self.assertIn("M⊕", forced.text(_OEC_COL_M))

    def test_errors_toggle_removes_the_error_term(self):
        from gui.panels.catalogs import _OEC_COL_M
        on = self._item("Single Star", "star")
        self.assertIn("±", on.text(_OEC_COL_M))
        off = self._item("Single Star", "star", ctx={"errors": False})
        self.assertNotIn("±", off.text(_OEC_COL_M))

    # ── T16 — star row derived cells (Stage 1b) ──
    def test_star_row_exposes_luminosity_and_hz(self):
        from gui.panels.catalogs import _OEC_COL_L, _OEC_COL_HZ
        star = self._item("Single Star", "star")     # R=1.0, T=5800 → L ≈ 1.01
        self.assertIn("L☉", star.text(_OEC_COL_L))
        self.assertTrue(star.text(_OEC_COL_L).startswith("1.0"))
        self.assertIn("AU", star.text(_OEC_COL_HZ))
        self.assertIn("–", star.text(_OEC_COL_HZ))

    def test_star_with_no_radius_has_empty_derived_cells(self):
        from gui.panels.catalogs import _OEC_COL_L, _OEC_COL_HZ
        star = self._item("Binary S", "star", "BS A")   # spectral type only
        self.assertEqual(star.text(_OEC_COL_L), "")
        self.assertEqual(star.text(_OEC_COL_HZ), "")

    def test_derived_toggle_off_clears_the_derived_columns(self):
        from gui.panels.catalogs import _OEC_COL_L, _OEC_COL_HZ
        star = self._item("Single Star", "star", ctx={"derived": False})
        self.assertEqual(star.text(_OEC_COL_L), "")
        self.assertEqual(star.text(_OEC_COL_HZ), "")

    def test_planet_rows_carry_no_derived_cells_yet(self):
        from gui.panels.catalogs import _OEC_COL_L, _OEC_COL_HZ
        planet = self._item("Single Star", "planet")
        self.assertEqual(planet.text(_OEC_COL_L), "")
        self.assertEqual(planet.text(_OEC_COL_HZ), "")

    def test_tooltip_carries_every_catalogued_field(self):
        from gui.panels.catalogs import _OEC_COL_NODE
        star = self._item("Single Star", "star")
        tip = star.toolTip(_OEC_COL_NODE)
        for key in ("mass", "radius", "temperature", "spectraltype"):
            self.assertIn(key, tip)


@unittest.skipUnless(qt_available(), "PySide6 / matplotlib not available")
class OecTreeWidgetTests(OecTestBase):
    """The tree widget itself: hide-empty columns, expand rule, §B.5 properties."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _tree(self, name):
        from gui.panels.catalogs import OecPanel
        from tests.test_oec import _FakeWindow
        panel = OecPanel(_FakeWindow())
        panel._on_oec_result({"system": self._system(name), "_hypatia": {}})
        return panel, panel._oec_tree

    def test_hide_empty_columns_hides_unpopulated_ones(self):
        from gui.panels.catalogs import _OEC_COL_L, _OEC_COL_NODE, _OEC_COL_M
        _, tree = self._tree("Zero Planet")
        self.assertFalse(tree.isColumnHidden(_OEC_COL_NODE))
        # no mass anywhere in the Zero Planet system, and no derived cells yet
        self.assertTrue(tree.isColumnHidden(_OEC_COL_M))
        self.assertTrue(tree.isColumnHidden(_OEC_COL_L))

    def test_populated_column_is_visible(self):
        from gui.panels.catalogs import _OEC_COL_M
        _, tree = self._tree("Single Star")
        self.assertFalse(tree.isColumnHidden(_OEC_COL_M))

    def test_small_system_is_fully_expanded(self):
        _, tree = self._tree("Hierarchy")
        root = tree.topLevelItem(0)
        self.assertTrue(root.isExpanded())

        def all_expanded(item):
            if item.childCount() and not item.isExpanded():
                return False
            return all(all_expanded(item.child(i)) for i in range(item.childCount()))

        self.assertTrue(all_expanded(root))

    def test_header_and_alternating_rows_preserved(self):
        from PySide6.QtWidgets import QHeaderView
        from gui.panels.catalogs import _OEC_COLUMNS, _OEC_COL_NODE
        _, tree = self._tree("Single Star")
        self.assertEqual(tree.columnCount(), len(_OEC_COLUMNS))
        self.assertTrue(tree.alternatingRowColors())
        # Interactive, not Stretch: Stretch only receives what the
        # ResizeToContents numeric columns leave over, which beside the detail
        # pane was ~95 px — every tau Ceti planet rendered as "t…" (V6 finding).
        self.assertEqual(tree.header().sectionResizeMode(_OEC_COL_NODE),
                         QHeaderView.ResizeMode.Interactive)
        self.assertGreaterEqual(tree.columnWidth(_OEC_COL_NODE), 240)

    def test_the_node_column_stays_readable_beside_the_detail_pane(self):
        """A planet name must survive the default split, not elide to 't…'."""
        panel, tree = self._tree("Hierarchy")
        panel.resize(1100, 700)
        panel.show()
        try:
            self.app.processEvents()
            metrics = tree.fontMetrics()
            longest = max(metrics.horizontalAdvance(item)
                          for item in ("● Inner A b  [Confirmed planets]",))
            self.assertGreaterEqual(tree.columnWidth(0), longest)
        finally:
            panel.hide()

    def test_every_item_carries_its_node(self):
        from gui.panels.catalogs import _oec_item_node
        _, tree = self._tree("Hierarchy")

        def walk(item):
            self.assertIsNotNone(_oec_item_node(item))
            for i in range(item.childCount()):
                walk(item.child(i))

        walk(tree.topLevelItem(0))


# ── Stage 2 — the detail pane, its registry, and selection ───────────────────
@unittest.skipUnless(qt_available(), "PySide6 / matplotlib not available")
class DetailModelTests(OecTestBase):
    """T6 — no field is droppable: the registry ∪ the fallback covers every key the
    walker produces, per tag, and every covered key actually renders a row."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _nodes(self):
        for name in ("Single Star", "Binary S", "Circumbinary", "Hierarchy",
                     "Rogue One", "Zero Planet"):
            system = self._system(name)

            def walk(n):
                yield n
                for c in n.get("children", []):
                    yield from walk(c)

            yield from walk(system)

    def test_every_walker_key_is_labelled_somewhere(self):
        from gui.panels.oec_detail import detail_model, _HANDLED_ELSEWHERE
        for node in self._nodes():
            model = detail_model(node)
            labelled = {r["label"] for s in model["sections"] for r in s["rows"]}
            for key in node.get("fields", {}):
                if key in _HANDLED_ELSEWHERE:
                    continue
                # either a registry row rendered it, or the fallback owns it
                in_fallback = key in model["fallback_keys"]
                self.assertTrue(
                    in_fallback or labelled,
                    f"{node['tag']}.{key} is neither registered nor in the fallback")

    def test_statuses_render_as_badges_not_rows(self):
        from gui.panels.oec_detail import detail_model
        planet = self._find(self._system("Binary S"), "planet")[0]
        model = detail_model(planet)
        self.assertEqual(len(model["badges"]), 2)
        self.assertNotIn("list", model["fallback_keys"])

    def test_all_aliases_are_listed(self):
        from gui.panels.oec_detail import detail_model
        system = self._system("Single Star")          # two <name> tags
        model = detail_model(system)
        ident = next(s for s in model["sections"] if s["title"] == "Identity")
        self.assertEqual(ident["rows"][0]["value"], "Single Star")
        self.assertIn("HD 1", ident["rows"][1]["value"])

    # ── T17 — the `periastron` name collision ──
    def test_periastron_is_labelled_as_an_angle_not_a_distance(self):
        from gui.panels.oec_detail import _ORBIT_COMMON
        label, unit = next((lbl, u) for k, lbl, u in _ORBIT_COMMON if k == "periastron")
        self.assertIn("Argument of periastron", label)
        self.assertEqual(unit, "°")

    def test_msini_label_survives_into_the_pane(self):
        from gui.panels.oec_detail import detail_model
        planet = self._find(self._system("Single Star"), "planet")[0]
        rows = {r["label"]: r["value"] for s in detail_model(planet)["sections"]
                for r in s["rows"]}
        self.assertIn("M·sin i", rows)

    # ── T18 — a failing section must not blank the pane ──
    def test_a_raising_section_builder_is_isolated(self):
        from gui.panels import oec_detail
        star = self._find(self._system("Single Star"), "star")[0]
        original = oec_detail._registry_section
        oec_detail._registry_section = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            model = oec_detail.detail_model(star)
            pane = oec_detail.build_detail_pane(star)
        finally:
            oec_detail._registry_section = original
        self.assertTrue(any(s.get("failed") for s in model["sections"]))
        # Identity still rendered — the pane is not blank
        self.assertTrue(any(s["title"] == "Identity" and s["rows"]
                            for s in model["sections"]))
        self.assertIsNotNone(pane)


@unittest.skipUnless(qt_available(), "PySide6 / matplotlib not available")
class DetailPaneWiringTests(OecTestBase):
    """T3 / T10 / T10b — selection convergence, pane survival, and layout."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self, name):
        from gui.panels.catalogs import OecPanel
        from tests.test_oec import _FakeWindow
        panel = OecPanel(_FakeWindow())
        system = self._system(name)
        panel._on_oec_result({"system": system, "_hypatia": {}})
        return panel, system

    def _pane_model(self, panel):
        return panel._oec_pane.widget()._oec_model

    def _items(self, tree):
        out = []

        def walk(item):
            out.append(item)
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(tree.topLevelItemCount()):
            walk(tree.topLevelItem(i))
        return out

    # ── D10 cold state ──
    def test_cold_state_selects_the_primary_host_star(self):
        panel, system = self._panel("Single Star")
        node, kind = panel._oec_sel
        self.assertEqual(kind, "star")
        self.assertIs(node, self._find(system, "star")[0])
        self.assertEqual(self._pane_model(panel)["tag"], "star")

    def test_cold_state_falls_back_to_the_system_when_planetless(self):
        panel, system = self._panel("Zero Planet")
        node, kind = panel._oec_sel
        self.assertEqual(kind, "system")
        self.assertIs(node, system)

    # ── T3 — every node maps to its own record, mouse and keyboard ──
    def test_selecting_each_node_renders_that_node(self):
        from gui.panels.catalogs import _oec_item_node
        panel, _ = self._panel("Hierarchy")
        tree = panel._oec_tree
        for item in self._items(tree):
            node = _oec_item_node(item)
            tree.setCurrentItem(item)
            self.app.processEvents()
            self.assertIs(panel._oec_sel[0], node)
            model = self._pane_model(panel)
            # content identity, not index arithmetic
            from gui.panels.oec_detail import oec_node_title
            self.assertIn(oec_node_title(node), model["title"])
            self.assertEqual(model["tag"], node["tag"])

    def test_keyboard_navigation_updates_the_pane(self):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtWidgets import QApplication
        from gui.panels.catalogs import _oec_item_node
        panel, _ = self._panel("Hierarchy")
        tree = panel._oec_tree
        items = self._items(tree)
        tree.setCurrentItem(items[0])
        self.app.processEvents()
        before = panel._oec_sel[0]
        tree.setFocus()
        ev = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(tree.viewport(), ev)
        tree.keyPressEvent(ev)
        self.app.processEvents()
        after = panel._oec_sel[0]
        self.assertIsNot(after, before, "arrow-key navigation did not move the selection")
        self.assertIs(after, _oec_item_node(tree.currentItem()))
        from gui.panels.oec_detail import oec_node_title
        self.assertIn(oec_node_title(after), self._pane_model(panel)["title"])

    def test_programmatic_selection_builds_the_pane_exactly_once(self):
        """`tree.blockSignals()` does NOT block `currentChanged` — that lives on the
        selection model — so a naive sync re-enters and builds the pane twice."""
        from gui.panels import catalogs
        panel, system = self._panel("Hierarchy")
        calls = []
        original = catalogs._oec_build_detail_pane
        catalogs._oec_build_detail_pane = lambda *a, **k: (calls.append(a[0]),
                                                          original(*a, **k))[1]
        try:
            panel._set_oec_selection(self._find(system, "star", "Inner A")[0])
            self.app.processEvents()
        finally:
            catalogs._oec_build_detail_pane = original
        self.assertEqual(len(calls), 1, f"pane built {len(calls)} times")

    def test_map_click_and_host_combo_share_the_selection(self):
        panel, system = self._panel("Hierarchy")
        inner_a = self._find(system, "star", "Inner A")[0]
        panel._on_arch_select(inner_a)
        self.app.processEvents()
        self.assertIs(panel._oec_sel[0], inner_a)
        # the tree cursor followed the map
        from gui.panels.catalogs import _oec_item_node
        self.assertIs(_oec_item_node(panel._oec_tree.currentItem()), inner_a)

    # ── T10 — the pane survives a recenter (§B.4) ──
    def test_pane_survives_rebuild_after_focus(self):
        panel, system = self._panel("Hierarchy")
        outer_b = self._find(system, "star", "Outer B")[0]
        panel._on_arch_select(outer_b)
        self.app.processEvents()
        self.assertEqual(panel._data_tabs.tabText(0), "Data")
        self.assertIsNotNone(panel._oec_pane.widget())
        self.assertIsNotNone(panel._oec_tree.topLevelItem(0))
        self.assertIs(panel._oec_sel[0], outer_b)

    def test_selection_does_not_rebuild_the_viz_tabs(self):
        panel, system = self._panel("Hierarchy")
        before = panel._viz_tabs_widget.widget(0)
        planet = self._find(system, "planet")[0]
        panel._set_oec_selection(planet)
        self.app.processEvents()
        self.assertIs(panel._viz_tabs_widget.widget(0), before)

    # ── T10b — splitter × AlignTop QScrollArea layout ──
    def test_tree_and_pane_get_a_non_zero_height(self):
        panel, _ = self._panel("Single Star")
        panel.resize(1100, 780)
        panel.show()
        self.app.processEvents()
        try:
            self.assertGreater(panel._oec_tree.height(), 100)
            self.assertGreater(panel._oec_pane.height(), 100)
            self.assertGreater(panel._oec_pane.width(), 100)
        finally:
            panel.hide()

    def test_pane_position_toggle(self):
        from PySide6.QtCore import Qt
        panel, _ = self._panel("Single Star")
        panel._on_oec_pane_position("Below")
        self.assertEqual(panel._oec_splitter.orientation(), Qt.Orientation.Vertical)
        self.assertTrue(panel._oec_pane.isVisibleTo(panel._oec_splitter))
        panel._on_oec_pane_position("Hidden")
        self.assertFalse(panel._oec_pane.isVisibleTo(panel._oec_splitter))
        panel._on_oec_pane_position("Right")
        self.assertEqual(panel._oec_splitter.orientation(), Qt.Orientation.Horizontal)
        self.assertTrue(panel._oec_pane.isVisibleTo(panel._oec_splitter))

    # ── D6 — no persistence anywhere in the change (T12c, asserted early) ──
    def test_no_qsettings_import(self):
        for mod in ("gui/panels/oec_detail.py", "gui/panels/catalogs.py",
                    "core/oec_derived.py"):
            code = [ln for ln in (_REPO / mod).read_text(encoding="utf-8").splitlines()
                    if "QSettings" in ln and not ln.strip().startswith("#")]
            self.assertEqual(code, [], f"{mod} uses QSettings (D6 says no persistence)")


# ── Stage 3 — the star dossier ───────────────────────────────────────────────
@unittest.skipUnless(qt_available(), "PySide6 / matplotlib not available")
class StarDossierTests(OecTestBase):
    """T4 / T5 / T15 — the eight blocks, all aliases, and the Companions block."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _model(self, system_name, star_sub=None):
        from gui.panels.oec_detail import detail_model, build_context
        from gui.panels.catalogs import _oec_node_values
        import core.oec_derived as od
        system = self._system(system_name)
        star = self._find(system, "star", star_sub)[0]
        ctx = build_context(system)
        ctx["derived_values"] = od.derive(
            "star", _oec_node_values(star), system_values=_oec_node_values(system))
        return detail_model(star, ctx), star, system

    def _rows(self, model, title):
        sec = next((s for s in model["sections"] if s["title"] == title), None)
        return {r["label"]: r["value"] for r in (sec or {"rows": []})["rows"]}

    # ── T4 — every alias ──
    def test_all_aliases_are_rendered(self):
        from gui.panels.oec_detail import detail_model
        names = [f"Alias {i}" for i in range(22)]
        node = {"tag": "star", "names": names, "fields": {}, "children": []}
        rows = self._rows(detail_model(node), "Identity")
        self.assertEqual(rows["Name"], "Alias 0")
        listed = rows["Aliases (21)"].split(" · ")
        self.assertEqual(len(listed), 21)
        self.assertEqual(listed[-1], "Alias 21")

    def test_a_single_name_star_has_no_alias_row(self):
        from gui.panels.oec_detail import detail_model
        node = {"tag": "star", "names": ["Only"], "fields": {}, "children": []}
        rows = self._rows(detail_model(node), "Identity")
        self.assertEqual(list(rows), ["Name"])

    # ── T5 — companions ──
    def test_binary_component_shows_the_parent_orbit_and_companion(self):
        model, _, _ = self._model("Binary S", "BS A")
        rows = self._rows(model, "Companions & hierarchy")
        self.assertIn("Parent", rows)
        self.assertIn("BS B", rows["Companion"])
        self.assertIn("DA2", rows["Companion"])         # companion's spectral type
        self.assertIn("Separation", rows)               # from the parent binary
        self.assertIn("arcsec", rows["Separation"])
        self.assertIn("AU", rows["Separation"])

    def test_single_star_shows_one_no_companion_line_not_an_empty_section(self):
        model, _, _ = self._model("Single Star")
        sec = next(s for s in model["sections"]
                   if s["title"] == "Companions & hierarchy")
        self.assertEqual(len(sec["rows"]), 1)
        self.assertIn("No catalogued companion", sec["rows"][0]["value"])

    def test_deep_hierarchy_names_the_wider_pair(self):
        model, _, _ = self._model("Hierarchy", "Inner A")
        rows = self._rows(model, "Companions & hierarchy")
        self.assertIn("Inner C", rows["Companion"])
        self.assertIn("Outer", rows["Wider hierarchy"])

    # ── Position comes from the system record ──
    def test_position_block_reads_the_system_node(self):
        model, _, _ = self._model("Single Star")
        rows = self._rows(model, "Position & distance")
        self.assertEqual(rows["Constellation"], "Testus")
        self.assertIn("10.0", rows["Distance"])

    def test_multi_star_system_says_the_position_is_shared(self):
        model, _, _ = self._model("Binary S", "BS A")
        rows = self._rows(model, "Position & distance")
        self.assertIn("Recorded on", rows)

    def test_single_star_system_does_not_add_the_shared_note(self):
        model, _, _ = self._model("Single Star")
        self.assertNotIn("Recorded on", self._rows(model, "Position & distance"))

    # ── Planets hosted ──
    def test_planets_hosted_lists_each_planet_with_its_parameters(self):
        model, _, _ = self._model("Single Star")
        rows = self._rows(model, "Planets hosted")
        self.assertIn("HD 1 b", rows)
        self.assertIn("M·sin i", rows["HD 1 b"])
        self.assertIn("P 100 d", rows["HD 1 b"])
        self.assertIn("Confirmed planets", rows["HD 1 b"])

    def test_planetless_star_says_so(self):
        model, _, _ = self._model("Binary S", "BS B")
        rows = self._rows(model, "Planets hosted")
        self.assertIn("No planets catalogued", rows["Planets"])

    # ── Cross-references ──
    def test_cross_references_list_the_catalogue_designations(self):
        from gui.panels.oec_detail import detail_model, oec_star_xrefs
        node = {"tag": "star", "names": ["Foo", "HD 10700", "HIP 8102", "Gliese 71"],
                "fields": {}, "children": []}
        self.assertEqual([lbl for lbl, _ in oec_star_xrefs(node)],
                         ["HD", "HIP", "GJ / Gliese"])
        rows = self._rows(detail_model(node), "Cross-references")
        self.assertEqual(rows["HD"], "HD 10700")

    def test_a_star_with_no_designation_says_lookup_is_impossible(self):
        from gui.panels.oec_detail import detail_model
        node = {"tag": "star", "names": ["Nameless One"], "fields": {}, "children": []}
        rows = self._rows(detail_model(node), "Cross-references")
        self.assertIn("cannot be resolved", rows["Cross-references"])

    def test_lookup_button_only_appears_with_a_designation_and_a_callback(self):
        from gui.panels.oec_detail import build_detail_pane
        from PySide6.QtWidgets import QPushButton
        with_ref = {"tag": "star", "names": ["HD 1"], "fields": {}, "children": []}
        without = {"tag": "star", "names": ["Nameless"], "fields": {}, "children": []}

        def buttons(node, ctx):
            pane = build_detail_pane(node, ctx)
            return pane.findChildren(QPushButton)

        self.assertEqual(len(buttons(with_ref, {"on_lookup": lambda n: None})), 1)
        self.assertEqual(len(buttons(with_ref, {})), 0)
        self.assertEqual(len(buttons(without, {"on_lookup": lambda n: None})), 0)

    # ── Derived rows carry provenance and obey the toggle (D3 / §D.4) ──
    def test_derived_rows_are_marked_and_carry_their_source(self):
        model, _, _ = self._model("Single Star")
        derived = [r for s in model["sections"] for r in s["rows"] if r["derived"]]
        self.assertTrue(derived)
        for r in derived:
            self.assertTrue(r["tip"], f"{r['label']} has no source")

    def test_derived_toggle_removes_every_derived_row(self):
        from gui.panels.oec_detail import detail_model, build_context
        from gui.panels.catalogs import _oec_node_values
        import core.oec_derived as od
        system = self._system("Single Star")
        star = self._find(system, "star")[0]
        ctx = build_context(system)
        ctx["derived_values"] = od.derive("star", _oec_node_values(star))
        ctx["derived"] = False
        model = detail_model(star, ctx)
        self.assertEqual([r for s in model["sections"] for r in s["rows"]
                          if r["derived"]], [])

    def test_a_derived_value_that_cannot_be_computed_states_its_reason(self):
        from gui.panels.oec_detail import detail_model, build_context
        import core.oec_derived as od
        system = self._system("Binary S")
        star = self._find(system, "star", "BS A")[0]      # no radius, no temperature
        ctx = build_context(system)
        ctx["derived_values"] = od.derive("star", {})
        rows = self._rows(detail_model(star, ctx), "Habitable zone & ice lines")
        self.assertTrue(rows)
        self.assertTrue(all(v.startswith("—") for v in rows.values()), rows)


@unittest.skipUnless(qt_available(), "PySide6 / matplotlib not available")
class StarDossierRichTests(OecViewFixtureBase):
    """T15 — the eight blocks, against a star that populates all of them."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _model(self, system_name="Photometric", star_sub=None):
        from gui.panels.oec_detail import detail_model, build_context
        from gui.panels.catalogs import _oec_node_values
        import core.oec_derived as od
        system = self._system(system_name)
        star = self._find(system, "star", star_sub)[0]
        ctx = build_context(system)
        ctx["derived_values"] = od.derive(
            "star", _oec_node_values(star), system_values=_oec_node_values(system))
        return detail_model(star, ctx)

    def test_all_eight_dossier_blocks_render(self):
        from gui.panels.oec_detail import STAR_DOSSIER_BLOCKS
        titles = [s["title"] for s in self._model()["sections"]]
        self.assertEqual(len(STAR_DOSSIER_BLOCKS), 8)
        for block in STAR_DOSSIER_BLOCKS:
            self.assertIn(block, titles, f"missing dossier block: {block}")

    def test_blocks_keep_their_order(self):
        from gui.panels.oec_detail import STAR_DOSSIER_BLOCKS
        titles = [s["title"] for s in self._model()["sections"]]
        self.assertEqual([t for t in titles if t in STAR_DOSSIER_BLOCKS],
                         STAR_DOSSIER_BLOCKS)

    def test_all_eight_photometric_bands_render(self):
        sec = next(s for s in self._model()["sections"] if s["title"] == "Photometry")
        labels = [r["label"] for r in sec["rows"]]
        for band in ("U", "B", "V", "R", "I", "J", "H", "K"):
            self.assertIn(f"{band} magnitude", labels)

    # ── The D.2 raise path, end to end through the pane ──
    def test_a_hot_host_gets_a_reason_not_a_crash(self):
        rows = {r["label"]: r["value"]
                for s in self._model("Hot Host")["sections"]
                if s["title"] == "Habitable zone & ice lines" for r in s["rows"]}
        self.assertIn("Habitable zone", rows)
        self.assertIn("Kopparapu", rows["Habitable zone"])

    # ── T17 — the catalogued `periastron` is an angle ──
    def test_planet_periastron_renders_as_an_angle(self):
        from gui.panels.oec_detail import detail_model
        planet = self._find(self._system("Photometric"), "planet")[0]
        rows = {r["label"]: r["value"] for s in detail_model(planet)["sections"]
                for r in s["rows"]}
        self.assertIn("Argument of periastron", rows)
        self.assertIn("395.3", rows["Argument of periastron"])
        self.assertNotIn("AU", rows["Argument of periastron"])
        self.assertNotIn("Periastron", rows)          # no bare, ambiguous label

    # ── T20 (Stage 3b's satellite check, available already) ──
    def test_satellite_renders_its_orbital_elements(self):
        from gui.panels.oec_detail import detail_model
        moon = self._find(self._system("Photometric"), "satellite")[0]
        rows = {r["label"]: r["value"] for s in detail_model(moon)["sections"]
                for r in s["rows"]}
        for label in ("Eccentricity", "Inclination", "Argument of periastron",
                      "Mean longitude", "Ascending node", "Axial tilt"):
            self.assertIn(label, rows)


@unittest.skipUnless(qt_available(), "PySide6 / matplotlib not available")
class NonStarSectionTests(OecTestBase):
    """T20 / Stage 3b — the binary, system and satellite section sets."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _rows(self, node, title, system=None):
        from gui.panels.oec_detail import detail_model, build_context
        ctx = build_context(system) if system is not None else {}
        sec = next((s for s in detail_model(node, ctx)["sections"]
                    if s["title"] == title), None)
        self.assertIsNotNone(sec, f"missing section: {title}")
        return [(r["label"], r["value"]) for r in sec["rows"]]

    def test_binary_lists_its_components(self):
        system = self._system("Binary S")
        binary = self._find(system, "binary")[0]
        rows = self._rows(binary, "Components", system)
        values = [v for lbl, v in rows if lbl == "Component"]
        self.assertEqual(len(values), 2)
        self.assertTrue(any("BS A" in v for v in values))
        self.assertTrue(any("K0V" in v for v in values))     # component sp type

    def test_circumbinary_planet_is_labelled_as_such(self):
        system = self._system("Circumbinary")
        binary = self._find(system, "binary")[0]
        rows = self._rows(binary, "Components", system)
        self.assertTrue(any(lbl == "Circumbinary planet" for lbl, _ in rows))

    def test_system_contents_counts_its_components(self):
        system = self._system("Hierarchy")
        rows = dict(self._rows(system, "Contents", system))
        self.assertEqual(rows["Stars"], "3")
        self.assertEqual(rows["Planets"], "1")
        self.assertEqual(rows["Satellites"], "1")

    def test_planetless_system_says_why(self):
        system = self._system("Zero Planet")
        rows = dict(self._rows(system, "Contents", system))
        self.assertEqual(rows["Planets"], "0")
        self.assertIn("only systems with planets", rows["Note"])

    def test_satellite_names_its_host_planet_and_star(self):
        system = self._system("Hierarchy")
        moon = self._find(system, "satellite")[0]
        rows = dict(self._rows(moon, "Parent", system))
        self.assertIn("Outer B b", rows["Host planet"])
        self.assertIn("Outer B", rows["Host star"])

    def test_satellite_renders_all_six_orbital_elements(self):
        # The fixture moon carries only mass/radius; the rich fixture covers the
        # 100%-coverage element set (see StarDossierRichTests).
        system = self._system("Hierarchy")
        moon = self._find(system, "satellite")[0]
        rows = dict(self._rows(moon, "Physical", system))
        self.assertIn("Mass", rows)
        self.assertIn("M⊕", rows["Mass"])


@unittest.skipUnless(qt_available(), "PySide6 / matplotlib not available")
class DerivedCacheTests(OecTestBase):
    """T19 — the derived cache is per result, never keyed on a bare `id(node)`."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_second_search_gets_its_own_values(self):
        from gui.panels.catalogs import OecPanel
        from tests.test_oec import _FakeWindow
        panel = OecPanel(_FakeWindow())
        panel._on_oec_result({"system": self._system("Single Star"), "_hypatia": {}})
        first = panel._oec_derived_for(panel._oec_sel[0])["luminosity_lsun"]["value"]
        self.assertAlmostEqual(first, 1.0, places=1)          # R=1.0, T=5800

        # A second search: fresh node dicts, and `id()` values Python is free to
        # reuse after the first system is collected.
        panel._on_oec_result({"system": self._system("Hierarchy"), "_hypatia": {}})
        star = self._find(panel._oec_system, "star", "Inner A")[0]
        entry = panel._oec_derived_for(star)["luminosity_lsun"]
        self.assertIsNone(entry["value"])                     # Inner A has no radius
        self.assertTrue(entry["reason"])

    def test_no_cache_entry_survives_from_the_previous_result(self):
        from gui.panels.catalogs import OecPanel
        from tests.test_oec import _FakeWindow
        panel = OecPanel(_FakeWindow())
        panel._on_oec_result({"system": self._system("Single Star"), "_hypatia": {}})
        for node in self._find(panel._oec_system, "star"):
            panel._oec_derived_for(node)
        self.assertTrue(panel._oec_derived_cache)

        panel._on_oec_result({"system": self._system("Hierarchy"), "_hypatia": {}})

        def reachable(n):
            yield n
            for c in n.get("children", []):
                yield from reachable(c)

        live = {id(n) for n in reachable(panel._oec_system)}
        cached = {id(node) for node, _ in panel._oec_derived_cache.values()}
        self.assertTrue(cached <= live,
                        "a derived cache entry survived from the previous system")


# ── Stage 4a — the star-side derived layer, through the pane ─────────────────
@unittest.skipUnless(qt_available(), "PySide6 / matplotlib not available")
class Stage4aPaneTests(OecViewFixtureBase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _panel_rows(self, system_name, star_sub=None, title=None):
        from gui.panels.catalogs import OecPanel
        from gui.panels.oec_detail import detail_model
        from tests.test_oec import _FakeWindow
        panel = OecPanel(_FakeWindow())
        system = self._system(system_name)
        panel._on_oec_result({"system": system, "_hypatia": {}})
        node = self._find(system, "star", star_sub)[0]
        model = detail_model(node, panel._oec_detail_ctx(node))
        self.assertEqual([s["title"] for s in model["sections"] if s.get("failed")],
                         [], "a section failed to build")
        sec = next((s for s in model["sections"] if s["title"] == title), None)
        self.assertIsNotNone(sec, f"missing section {title}")
        return {r["label"]: r["value"] for r in sec["rows"]}

    def test_hyper_limit_is_an_au_value_not_the_returned_dict(self):
        """`compute_hyper_limit_for_spectral_type` returns {lm, au, matched_class};
        formatting the dict raised and took the whole HZ section down with it."""
        rows = self._panel_rows("Photometric", title="Habitable zone & ice lines")
        limit = rows["Honorverse hyper limit (fiction)"]
        self.assertIn("AU", limit)
        self.assertNotIn("{", limit)
        self.assertTrue(limit[0].isdigit())

    def test_hz_ice_lines_and_hyper_limit_all_render_together(self):
        rows = self._panel_rows("Photometric", title="Habitable zone & ice lines")
        self.assertIn("Conservative HZ", rows)
        self.assertIn("Optimistic HZ", rows)
        self.assertIn("Water snow line", rows)
        self.assertIn("NH₃ front", rows)                 # species is already a label
        self.assertNotIn("NH₃ front condensation", rows)
        self.assertIn("Honorverse hyper limit (fiction)", rows)

    def test_distance_block_uses_the_system_distance(self):
        rows = self._panel_rows("Photometric", title="Position & distance")
        self.assertIn("11.9", rows["Distance (light years)"])
        self.assertIn("274", rows["Parallax"])
        self.assertIn("2.02", rows["Angular diameter"])
        self.assertIn("Distance", rows)                  # the catalogued pc value

    def test_physical_block_carries_the_derived_star_values(self):
        rows = self._panel_rows("Photometric", title="Physical")
        self.assertIn("4.533", rows["Surface gravity log g"])
        self.assertIn("2.214", rows["Mean density"])
        self.assertIn("Main Sequence", rows["Evolutionary stage"])

    def test_low_mass_lifetime_renders_as_a_bound_not_a_figure(self):
        rows = self._panel_rows("Photometric", title="Physical")
        life = rows["Main-sequence lifetime"]
        self.assertTrue(life.startswith("> 13.8 Gyr"), life)
        self.assertIn("Hubble", life)

    def test_photometry_block_carries_the_colours(self):
        rows = self._panel_rows("Photometric", title="Photometry")
        self.assertIn("0.72", rows["B−V"])
        self.assertIn("1.82", rows["V−K"])
        self.assertIn("5.688", rows["Absolute magnitude M_V"])

    def test_a_hot_host_gates_only_the_hz(self):
        rows = self._panel_rows("Hot Host", title="Habitable zone & ice lines")
        self.assertIn("Kopparapu", rows["Habitable zone"])
        self.assertIn("Water snow line", rows)           # not Kopparapu-dependent
        phys = self._panel_rows("Hot Host", title="Physical")
        self.assertIn("Luminosity", phys)
        self.assertNotIn("—", phys["Luminosity"])

    def test_hyper_limit_states_why_it_is_absent_for_a_non_obafgkm_type(self):
        from gui.panels.catalogs import OecPanel
        from tests.test_oec import _FakeWindow
        panel = OecPanel(_FakeWindow())
        panel._on_oec_result({"system": self._system("Photometric"), "_hypatia": {}})
        wd = {"tag": "star", "names": ["WD 1"], "children": [],
              "fields": {"spectraltype": {"value": "DA2"}}}
        entry = panel._oec_panel_derived(wd)["hyper_limit_au"]
        self.assertIsNone(entry["value"])
        self.assertIn("DA2", entry["reason"])
        self.assertTrue(entry["source"])


# ── Stage 4b — the planet-side derived layer, through the panel ──────────────
@unittest.skipUnless(qt_available(), "PySide6 / matplotlib not available")
class Stage4bPaneTests(OecViewFixtureBase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self, system_name="Photometric"):
        from gui.panels.catalogs import OecPanel
        from tests.test_oec import _FakeWindow
        panel = OecPanel(_FakeWindow())
        system = self._system(system_name)
        panel._on_oec_result({"system": system, "_hypatia": {}})
        return panel, system

    def _derived_rows(self, system_name="Photometric"):
        from gui.panels.oec_detail import detail_model
        panel, system = self._panel(system_name)
        planet = self._find(system, "planet")[0]
        model = detail_model(planet, panel._oec_detail_ctx(planet))
        self.assertEqual([s["title"] for s in model["sections"] if s.get("failed")],
                         [], "a section failed to build")
        sec = next(s for s in model["sections"] if s["title"] == "Derived")
        return {r["label"]: r["value"] for r in sec["rows"]}

    def test_planet_pane_carries_the_derived_block(self):
        rows = self._derived_rows()
        for label in ("Insolation", "Habitable-zone verdict", "Mean density",
                      "Surface gravity", "RV semi-amplitude K", "Hill radius"):
            self.assertIn(label, rows)

    def test_a_recovered_sma_is_labelled_as_recovered(self):
        rows = self._derived_rows()          # the fixture planet has period, no a
        self.assertIn("Semi-major axis (recovered)", rows)
        self.assertIn("0.13", rows["Semi-major axis (recovered)"])

    def test_a_catalogued_sma_is_not_restated_as_derived(self):
        from gui.panels.oec_detail import detail_model
        panel, system = self._panel("Hot Host")
        planet = self._find(system, "planet")[0]     # period 300 d, no a either
        rows = {r["label"] for s in detail_model(planet, panel._oec_detail_ctx(planet))
                ["sections"] for r in s["rows"]}
        # Give it a catalogued a and the derived row must disappear
        planet["fields"]["semimajoraxis"] = {"value": "0.9"}
        panel._oec_derived_cache = {}
        rows2 = {r["label"] for s in detail_model(planet, panel._oec_detail_ctx(planet))
                 ["sections"] for r in s["rows"]}
        self.assertIn("Semi-major axis (recovered)", rows)
        self.assertNotIn("Semi-major axis (recovered)", rows2)
        self.assertIn("Semi-major axis", rows2)      # the catalogued Orbit row

    def test_tree_planet_row_carries_insolation_and_the_hz_verdict(self):
        from gui.panels.catalogs import _oec_item_node, _OEC_COL_L, _OEC_COL_HZ
        panel, _ = self._panel()

        def find(item):
            node = _oec_item_node(item)
            if node and node["tag"] == "planet":
                return item
            for i in range(item.childCount()):
                hit = find(item.child(i))
                if hit is not None:
                    return hit
            return None

        row = find(panel._oec_tree.topLevelItem(0))
        self.assertTrue(row.text(_OEC_COL_L))
        self.assertIn(row.text(_OEC_COL_HZ),
                      ("interior", "optimistic", "conservative", "beyond"))

    def test_hz_verdict_shortener_never_silently_empties(self):
        from gui.panels.oec_detail import oec_hz_short
        self.assertEqual(oec_hz_short(""), "")
        self.assertEqual(oec_hz_short(None), "")
        # a reworded verdict shows as odd text, never as a blank cell
        self.assertEqual(oec_hz_short("Some new wording"), "Some new wording")

    def test_a_rogue_planet_states_reasons_instead_of_numbers(self):
        from gui.panels.oec_detail import detail_model
        from gui.panels.catalogs import OecPanel
        from tests.test_oec import _FakeWindow
        import tests.test_oec as base
        panel = OecPanel(_FakeWindow())
        # the base fixture's rogue system (no star at all)
        import xml.etree.ElementTree as ET
        import core.databases as databases
        self._root = ET.fromstring(base._FIXTURE)
        databases._oec_get_root = lambda force_refresh=False: self._root
        databases._OEC_DATA = None
        system = self._system("Rogue One")
        panel._on_oec_result({"system": system, "_hypatia": {}})
        planet = self._find(system, "planet")[0]
        rows = {r["label"]: r["value"] for s in
                detail_model(planet, panel._oec_detail_ctx(planet))["sections"]
                for r in s["rows"]}
        self.assertTrue(rows["Insolation"].startswith("—"))
        self.assertTrue(rows["Habitable-zone verdict"].startswith("—"))

    def test_derived_cache_is_per_node_for_planets_too(self):
        panel, system = self._panel()
        planets = self._find(system, "planet")
        star = self._find(system, "star")[0]
        self.assertIsNot(panel._oec_derived_for(planets[0]),
                         panel._oec_derived_for(star))
        self.assertIs(panel._oec_derived_for(planets[0]),
                      panel._oec_derived_for(planets[0]))   # memoised


# ── R2b review findings — regression pins ────────────────────────────────────
@unittest.skipUnless(qt_available(), "PySide6 / matplotlib not available")
class R2bRegressionTests(OecViewFixtureBase):
    """Each test here fails against the code as it stood at the R2b review."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self, name):
        from gui.panels.catalogs import OecPanel
        from tests.test_oec import _FakeWindow
        panel = OecPanel(_FakeWindow())
        system = self._system(name)
        panel._on_oec_result({"system": system, "_hypatia": {}})
        return panel, system

    def _rows(self, panel, node, title):
        from gui.panels.oec_detail import detail_model
        model = detail_model(node, panel._oec_detail_ctx(node))
        self.assertEqual([s["title"] for s in model["sections"] if s.get("failed")],
                         [], "a section failed to build")
        sec = next((s for s in model["sections"] if s["title"] == title), None)
        self.assertIsNotNone(sec, f"missing section {title}")
        return {r["label"]: r["value"] for r in sec["rows"]}

    # ── R2b-1 — a circumbinary planet's host is the PAIR ──
    def test_circumbinary_planet_uses_the_combined_mass_and_light(self):
        import math
        panel, system = self._panel("Full Circumbinary")
        planet = self._find(system, "planet")[0]
        d = panel._oec_derived_for(planet)
        # Kepler III against M₁+M₂ = 0.89 M☉, not the primary's 0.69
        p_yr = 228.8 / 365.25
        self.assertAlmostEqual(d["sma_au"]["value"],
                               (0.89 * p_yr ** 2) ** (1 / 3), places=6)
        self.assertIn("BINARY PAIR", d["sma_au"]["source"])
        # Insolation against L₁+L₂
        import core.equations as eq
        lum = (eq.compute_star_luminosity(0.65, 4450)["luminosity"]
               + eq.compute_star_luminosity(0.23, 3300)["luminosity"])
        self.assertAlmostEqual(d["insolation_searth"]["value"],
                               lum / d["sma_au"]["value"] ** 2, places=6)

    def test_the_primary_alone_would_understate_both(self):
        """Pins the direction and rough size of the R2b-1 error."""
        panel, system = self._panel("Full Circumbinary")
        planet = self._find(system, "planet")[0]
        pair = panel._oec_derived_for(planet)["sma_au"]["value"]
        import core.oec_derived as od
        primary_only = od.derive("planet", {"period": 228.8},
                                 host_values={"mass": 0.69})["sma_au"]["value"]
        self.assertGreater(pair, primary_only)
        self.assertAlmostEqual(pair / primary_only, (0.89 / 0.69) ** (1 / 3), places=6)

    def test_the_pane_and_the_binary_hz_row_agree_on_the_combined_light(self):
        panel, system = self._panel("Full Circumbinary")
        binary = self._find(system, "binary")[0]
        hz = panel._oec_derived_for(binary)["hz_circumbinary"]["value"]
        planet = self._find(system, "planet")[0]
        d = panel._oec_derived_for(planet)
        self.assertAlmostEqual(
            d["insolation_searth"]["value"],
            hz["combined_lum"] / d["sma_au"]["value"] ** 2, places=6)

    # ── R2b-2 — the stability rows must be reachable ──
    def test_binary_pane_shows_the_stability_block(self):
        panel, system = self._panel("Full Circumbinary")
        binary = self._find(system, "binary")[0]
        rows = self._rows(panel, binary, "Planet stability")
        self.assertIn("S-type critical SMA", rows)
        self.assertIn("P-type critical SMA", rows)
        self.assertIn("Mass ratio μ", rows)
        self.assertFalse(rows["S-type critical SMA"].startswith("—"))

    def test_star_companions_block_shows_the_parent_pairs_stability(self):
        panel, system = self._panel("Full Circumbinary")
        star = self._find(system, "star", "FCB A")[0]
        rows = self._rows(panel, star, "Companions & hierarchy")
        self.assertIn("S-type critical SMA", rows)
        self.assertIn("Mass ratio μ", rows)
        self.assertFalse(rows["S-type critical SMA"].startswith("—"))

    def test_a_single_star_has_no_parent_derived_values(self):
        panel, system = self._panel("Photometric")
        star = self._find(system, "star")[0]
        self.assertEqual(panel._oec_detail_ctx(star)["parent_derived"], {})

    # ── R2b-3 — the map dialog must carry the derived block ──
    def test_map_planet_dialog_shows_the_same_derived_rows_as_the_pane(self):
        from gui.panels.oec_detail import detail_model
        panel, system = self._panel("Photometric")
        planet = self._find(system, "planet")[0]
        pane_rows = {r["label"] for s in
                     detail_model(planet, panel._oec_detail_ctx(planet))["sections"]
                     for r in s["rows"]}
        dlg = panel._show_oec_planet({"node": planet, "name": "p"})
        try:
            model = next((getattr(w, "_oec_model", None)
                          for w in dlg.findChildren(object)
                          if getattr(w, "_oec_model", None)), None)
            self.assertIsNotNone(model, "the dialog rendered no detail model")
            dlg_rows = {r["label"] for s in model["sections"] for r in s["rows"]}
            self.assertIn("Insolation", dlg_rows)
            self.assertEqual(pane_rows, dlg_rows)
        finally:
            dlg.close()

    # ── R2b-4 — an unbound eccentricity is refused, never zeroed ──
    def test_an_unbound_eccentricity_is_refused_everywhere_not_just_peri_apo(self):
        import core.oec_derived as od
        r = od.derive("planet", {"mass": 1.0, "semimajoraxis": 1.0,
                                 "eccentricity": 1.2, "period": 365.0},
                      host_values={"mass": 1.0, "radius": 1.0,
                                   "temperature": 5778.0})
        for key in ("peri_distance_au", "hill_radius_au", "rv_semi_amplitude_ms"):
            self.assertIsNone(r[key]["value"], key)
            self.assertIn("bound orbit", r[key]["reason"], key)

    def test_an_absent_eccentricity_is_labelled_as_an_assumption(self):
        import core.oec_derived as od
        r = od.derive("planet", {"mass": 1.0, "semimajoraxis": 1.0,
                                 "period": 365.0},
                      host_values={"mass": 1.0, "radius": 1.0,
                                   "temperature": 5778.0})
        self.assertIsNotNone(r["hill_radius_au"]["value"])
        self.assertIn("assumed circular", r["hill_radius_au"]["reason"])

    # ── R2b-5 — msini propagates its lower-bound status ──
    def test_msini_qualifies_every_mass_derived_value(self):
        import core.oec_derived as od
        r = od.derive("planet", {"mass": 1.0, "radius": 1.0, "mass_type": "msini",
                                 "semimajoraxis": 1.0, "eccentricity": 0.1},
                      host_values={"mass": 1.0, "radius": 1.0,
                                   "temperature": 5778.0})
        for key in ("density_gcc", "surface_gravity_g", "hill_radius_au",
                    "moon_limit_au"):
            self.assertIn("lower bound", r[key]["reason"] or "", key)

    def test_a_true_mass_carries_no_lower_bound_note(self):
        import core.oec_derived as od
        r = od.derive("planet", {"mass": 1.0, "radius": 1.0,
                                 "semimajoraxis": 1.0, "eccentricity": 0.1},
                      host_values={"mass": 1.0})
        self.assertIsNone(r["density_gcc"]["reason"])

    # ── R2b-6 — topology ──
    def test_system_pane_reports_its_topology(self):
        panel, system = self._panel("Full Circumbinary")
        rows = self._rows(panel, system, "Contents")
        self.assertIn("Topology", rows)
        self.assertIn("2 stars", rows["Topology"])
        self.assertIn("circumbinary", rows["Topology"])

    def test_topology_names_a_planetless_system(self):
        panel, system = self._panel("Hot Host")
        star = self._find(system, "star")[0]
        star["children"] = []                     # drop its planet
        panel._oec_derived_cache = {}
        rows = self._rows(panel, system, "Contents")
        self.assertIn("no planets catalogued", rows["Topology"])

    # ── R2b-7 — a blank repeat must not mask a usable one ──
    def test_field_by_unit_keeps_scanning_past_an_unparseable_value(self):
        from gui.panels.catalogs import _oec_field_by_unit
        field = [{"value": "", "unit": "AU"}, {"value": "400", "unit": "AU"}]
        self.assertEqual(_oec_field_by_unit(field, "au"), 400.0)

    # ── R2b-8 — a catalogued 0° inclination is a value, not an absence ──
    def test_a_face_on_orbit_is_not_treated_as_edge_on(self):
        import core.oec_derived as od

        def k(incl):
            v = {"mass": 1.0, "period": 365.25, "eccentricity": 0.0}
            if incl is not None:
                v["inclination"] = incl
            return od.derive("planet", v, host_values={"mass": 1.0})[
                "rv_semi_amplitude_ms"]["value"]

        self.assertAlmostEqual(k(0.0), 0.0, places=9)
        self.assertGreater(k(90.0), 0.0)
        self.assertAlmostEqual(k(None), k(90.0), places=9)   # absent → edge-on


# ── Stage 5 — the pinned host band (T11) ─────────────────────────────────────
@unittest.skipUnless(qt_available(), "PySide6 / matplotlib not available")
class HostBandTests(OecViewFixtureBase):
    """T11 — present for a star-hosted planet, absent everywhere else, and a click
    returns the pane to the host's full dossier."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self, name="Photometric"):
        from gui.panels.catalogs import OecPanel
        from tests.test_oec import _FakeWindow
        panel = OecPanel(_FakeWindow())
        system = self._system(name)
        panel._on_oec_result({"system": system, "_hypatia": {}})
        return panel, system

    def _band(self, panel, node):
        from gui.panels.oec_detail import detail_model
        return detail_model(node, panel._oec_detail_ctx(node))["host_band"]

    def test_a_star_hosted_planet_pins_its_host(self):
        panel, system = self._panel()
        band = self._band(panel, self._find(system, "planet")[0])
        self.assertIsNotNone(band)
        self.assertIs(band["node"], self._find(system, "star")[0])
        self.assertIn("Photometric A", band["title"])
        self.assertIn("G8.5 V", band["subtitle"])

    def test_the_band_carries_l_hz_snow_line_and_distance(self):
        panel, system = self._panel()
        band = self._band(panel, self._find(system, "planet")[0])
        joined = " · ".join(band["derived"])
        # The mockup's own numbers for this star: L 0.460, HZ 0.66–1.18, 1.82, 11.9
        self.assertIn("0.4602 L☉", joined)
        self.assertIn("0.661–1.18 AU", joined)
        self.assertIn("snow line 1.82 AU", joined)
        self.assertIn("11.91 ly", joined)
        cat = " · ".join(band["catalogued"])
        for bit in ("0.783 M☉", "0.793 R☉", "5344 K"):
            self.assertIn(bit, cat)

    def test_no_band_for_a_rogue_planet(self):
        # A rogue planet's parent is the <system>: nothing to pin.
        import xml.etree.ElementTree as ET
        import core.databases as databases
        from tests.test_oec import _FIXTURE
        databases._oec_get_root = lambda force_refresh=False: ET.fromstring(_FIXTURE)
        databases._OEC_DATA = None
        panel, system = self._panel("Rogue One")
        planet = self._find(system, "planet")[0]
        self.assertIsNone(self._band(panel, planet))
        self.assertIsNone(panel._oec_pane.widget()._oec_host_band)

    def test_no_band_for_star_system_binary_or_satellite(self):
        panel, system = self._panel()
        for node in (system,
                     self._find(system, "star")[0],
                     self._find(system, "satellite")[0]):
            self.assertIsNone(self._band(panel, node), node.get("tag"))
        cb_panel, cb_system = self._panel("Full Circumbinary")
        self.assertIsNone(self._band(cb_panel, self._find(cb_system, "binary")[0]))

    def test_clicking_the_band_selects_the_host_star(self):
        panel, system = self._panel()
        planet = self._find(system, "planet")[0]
        star = self._find(system, "star")[0]
        panel._set_oec_selection(planet)
        self.app.processEvents()
        band_widget = panel._oec_pane.widget()._oec_host_band
        self.assertIsNotNone(band_widget)
        band_widget._oec_click()
        self.app.processEvents()
        self.assertIs(panel._oec_sel[0], star)
        self.assertEqual(panel._oec_pane.widget()._oec_model["tag"], "star")
        # the tree cursor followed, like every other selector (§B.3)
        from gui.panels.catalogs import _oec_item_node
        self.assertIs(_oec_item_node(panel._oec_tree.currentItem()), star)

    def test_a_circumbinary_planet_pins_the_pair_not_the_primary(self):
        """The R2b class of bug, in the band: the numbers a P-type planet is judged
        against are the PAIR's combined light, and must match the planet's own
        derived rows rather than one component's."""
        panel, system = self._panel("Full Circumbinary")
        planet = self._find(system, "planet")[0]
        band = self._band(panel, planet)
        self.assertIs(band["node"], self._find(system, "binary")[0])
        self.assertIn("host pair", band["subtitle"])
        joined = " · ".join(band["derived"])
        self.assertIn("combined", joined)
        self.assertIn("circumbinary", joined)
        # the band's L is the same combined luminosity the planet's insolation used
        from gui.panels.catalogs import _oec_host_values, _oec_host_of
        host = _oec_host_values(planet, panel._oec_ctx)
        self.assertIn(f"{host['luminosity']:.4g} L☉", joined)
        self.assertIsNot(host, _oec_host_of(planet, panel._oec_ctx))

    def test_derived_off_keeps_the_band_but_drops_its_derived_bits(self):
        panel, system = self._panel()
        panel._oec_view["derived"] = False
        band = self._band(panel, self._find(system, "planet")[0])
        self.assertIsNotNone(band)
        self.assertEqual(band["derived"], [])
        self.assertTrue(band["catalogued"])

    def test_pin_host_off_removes_the_band(self):
        panel, system = self._panel()
        panel._oec_view["pin_host"] = False
        planet = self._find(system, "planet")[0]
        self.assertIsNone(self._band(panel, planet))
        panel._set_oec_selection(planet)
        self.app.processEvents()
        self.assertIsNone(panel._oec_pane.widget()._oec_host_band)

    def test_a_failing_band_does_not_blank_the_pane(self):
        """The band is built inside its own try/except: it may cost the planet its
        context line, never its record."""
        from gui.panels import oec_detail
        panel, system = self._panel()
        planet = self._find(system, "planet")[0]
        original = oec_detail.host_band_model
        oec_detail.host_band_model = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("boom"))
        try:
            model = oec_detail.detail_model(planet, panel._oec_detail_ctx(planet))
        finally:
            oec_detail.host_band_model = original
        self.assertIsNone(model["host_band"])
        self.assertTrue(any(s["rows"] for s in model["sections"]))


# ── Stage 6 — the toolbar (T12a / T12b / T12c) ───────────────────────────────
@unittest.skipUnless(qt_available(), "PySide6 / matplotlib not available")
class ToolbarTests(OecViewFixtureBase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self, name="Photometric"):
        from gui.panels.catalogs import OecPanel
        from tests.test_oec import _FakeWindow
        panel = OecPanel(_FakeWindow())
        system = self._system(name)
        panel._on_oec_result({"system": system, "_hypatia": {}})
        return panel, system

    def _cell(self, panel, node, col):
        from gui.panels.catalogs import _oec_item_node

        def walk(item):
            if _oec_item_node(item) is node:
                return item.text(col)
            for i in range(item.childCount()):
                hit = walk(item.child(i))
                if hit is not None:
                    return hit
            return None

        return walk(panel._oec_tree.topLevelItem(0))

    def test_the_toolbar_carries_every_stage_6_control(self):
        panel, _ = self._panel()
        for attr in ("_oec_units_combo", "_oec_errors_box", "_oec_derived_box",
                     "_oec_hide_empty_box", "_oec_pin_host_box", "_oec_pane_combo"):
            self.assertTrue(hasattr(panel, attr), attr)
        self.assertEqual([panel._oec_units_combo.itemText(i)
                          for i in range(panel._oec_units_combo.count())],
                         ["Auto", "M⊕ / R⊕", "M♃ / R♃"])

    # ── T12a — tri-state units, per node, without rebuilding the tree ──
    def test_units_are_tri_state_and_change_the_unit_shown(self):
        from gui.panels.catalogs import _OEC_COL_M
        panel, system = self._panel()
        planet = self._find(system, "planet")[0]     # 0.00629 M♃ → Auto picks M⊕
        self.assertIn("M⊕", self._cell(panel, planet, _OEC_COL_M))
        panel._oec_units_combo.setCurrentText("M♃ / R♃")
        self.assertIn("M♃", self._cell(panel, planet, _OEC_COL_M))
        self.assertIn("0.00629", self._cell(panel, planet, _OEC_COL_M))
        panel._oec_units_combo.setCurrentText("M⊕ / R⊕")
        cell = self._cell(panel, planet, _OEC_COL_M)
        self.assertIn("M⊕", cell)
        self.assertIn("1.999", cell)                 # 0.00629 × 317.828 ≈ 2.00
        panel._oec_units_combo.setCurrentText("Auto")
        self.assertIn("M⊕", self._cell(panel, planet, _OEC_COL_M))

    def test_auto_units_are_decided_per_node(self):
        from gui.panels.catalogs import _OEC_COL_M
        panel, system = self._panel("Full Circumbinary")
        big = self._find(system, "planet")[0]        # 0.3 M♃ → stays Jupiter
        self.assertIn("M♃", self._cell(panel, big, _OEC_COL_M))
        small_panel, small_system = self._panel()
        small = self._find(small_system, "planet")[0]
        self.assertIn("M⊕", self._cell(small_panel, small, _OEC_COL_M))

    def test_changing_units_does_not_rebuild_the_tree(self):
        panel, system = self._panel()
        root = panel._oec_tree.topLevelItem(0)
        selected = panel._oec_sel[0]
        panel._oec_tree.topLevelItem(0).setExpanded(True)
        panel._oec_units_combo.setCurrentText("M♃ / R♃")
        self.assertIs(panel._oec_tree.topLevelItem(0), root)
        self.assertIs(panel._oec_sel[0], selected)
        self.assertTrue(root.isExpanded())

    def test_the_units_toggle_reaches_the_detail_pane(self):
        panel, system = self._panel()
        planet = self._find(system, "planet")[0]
        panel._set_oec_selection(planet)
        self.app.processEvents()

        def mass_row():
            model = panel._oec_pane.widget()._oec_model
            for sec in model["sections"]:
                for row in sec["rows"]:
                    if row["label"] in ("Mass", "M·sin i"):
                        return row["value"]
            return ""

        self.assertIn("M⊕", mass_row())
        panel._oec_units_combo.setCurrentText("M♃ / R♃")
        self.app.processEvents()
        self.assertIn("M♃", mass_row())

    # ── T12b — errors / derived / hide-empty ──
    def test_errors_toggle_removes_the_error_terms(self):
        from gui.panels.catalogs import _OEC_COL_M
        panel, system = self._panel()
        star = self._find(system, "star")[0]
        self.assertIn("±", self._cell(panel, star, _OEC_COL_M))
        panel._oec_errors_box.setChecked(False)
        self.assertNotIn("±", self._cell(panel, star, _OEC_COL_M))
        panel._oec_errors_box.setChecked(True)
        self.assertIn("±", self._cell(panel, star, _OEC_COL_M))

    def test_derived_toggle_removes_every_derived_row_and_cell(self):
        from gui.panels.catalogs import _OEC_COL_L
        panel, system = self._panel()
        star = self._find(system, "star")[0]
        panel._set_oec_selection(star)
        self.app.processEvents()
        self.assertIn("L☉", self._cell(panel, star, _OEC_COL_L))
        rows = [r for s in panel._oec_pane.widget()._oec_model["sections"]
                for r in s["rows"] if r.get("derived")]
        self.assertTrue(rows, "no derived rows to remove")

        panel._oec_derived_box.setChecked(False)
        self.app.processEvents()
        self.assertEqual(self._cell(panel, star, _OEC_COL_L), "")
        self.assertEqual([r for s in panel._oec_pane.widget()._oec_model["sections"]
                          for r in s["rows"] if r.get("derived")], [])
        panel._oec_derived_box.setChecked(True)
        self.app.processEvents()
        self.assertIn("L☉", self._cell(panel, star, _OEC_COL_L))

    def test_derived_off_hides_the_now_empty_derived_columns(self):
        """A toggle can empty a column; with hide-empty on it should then go."""
        from gui.panels.catalogs import _OEC_COL_L
        panel, _ = self._panel()
        self.assertFalse(panel._oec_tree.isColumnHidden(_OEC_COL_L))
        panel._oec_derived_box.setChecked(False)
        self.assertTrue(panel._oec_tree.isColumnHidden(_OEC_COL_L))
        panel._oec_derived_box.setChecked(True)
        self.assertFalse(panel._oec_tree.isColumnHidden(_OEC_COL_L))

    def test_hide_empty_toggle_shows_an_unpopulated_column(self):
        from gui.panels.catalogs import _OEC_COL_A
        # Hot Host: one star + one planet with a period, no `a` anywhere.
        panel, _ = self._panel("Hot Host")
        self.assertTrue(panel._oec_tree.isColumnHidden(_OEC_COL_A))
        panel._oec_hide_empty_box.setChecked(False)
        self.assertFalse(panel._oec_tree.isColumnHidden(_OEC_COL_A))
        panel._oec_hide_empty_box.setChecked(True)
        self.assertTrue(panel._oec_tree.isColumnHidden(_OEC_COL_A))

    def test_pin_host_toggle_drives_the_band(self):
        panel, system = self._panel()
        planet = self._find(system, "planet")[0]
        panel._set_oec_selection(planet)
        self.app.processEvents()
        self.assertIsNotNone(panel._oec_pane.widget()._oec_host_band)
        panel._oec_pin_host_box.setChecked(False)
        self.app.processEvents()
        self.assertIsNone(panel._oec_pane.widget()._oec_host_band)
        panel._oec_pin_host_box.setChecked(True)
        self.app.processEvents()
        self.assertIsNotNone(panel._oec_pane.widget()._oec_host_band)

    def test_toolbar_state_survives_a_new_search(self):
        """The view dict is initialised once per panel, not per result (R2a)."""
        panel, _ = self._panel()
        panel._oec_units_combo.setCurrentText("M♃ / R♃")
        panel._oec_pin_host_box.setChecked(False)
        panel._on_oec_result({"system": self._system("Hot Host"), "_hypatia": {}})
        self.assertEqual(panel._oec_view["units"], "jupiter")
        self.assertFalse(panel._oec_view["pin_host"])
        self.assertEqual(panel._oec_units_combo.currentText(), "M♃ / R♃")
        self.assertFalse(panel._oec_pin_host_box.isChecked())

    # ── D8 / D12 — no dead buttons ──
    def test_no_columns_or_export_button_ships(self):
        from PySide6.QtWidgets import QPushButton
        panel, _ = self._panel()
        labels = [b.text() for b in panel.findChildren(QPushButton)]
        for dead in ("Columns…", "Columns...", "Copy TSV", "Export CSV"):
            self.assertNotIn(dead, labels)


# ── R3 review findings — regression pins ─────────────────────────────────────
@unittest.skipUnless(qt_available(), "PySide6 / matplotlib not available")
class R3RegressionTests(OecViewFixtureBase):
    """Each test here fails against the code as it stood at the R3 review."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self, name="Photometric"):
        from gui.panels.catalogs import OecPanel
        from tests.test_oec import _FakeWindow
        panel = OecPanel(_FakeWindow())
        system = self._system(name)
        panel._on_oec_result({"system": system, "_hypatia": {}})
        return panel, system

    def _release(self, widget, button=None, pos=None):
        from PySide6.QtCore import QEvent, QPointF
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import Qt
        button = button or Qt.MouseButton.LeftButton
        pos = QPointF(*(pos or (5, 5)))
        ev = QMouseEvent(QEvent.Type.MouseButtonRelease, pos, pos, button, button,
                         Qt.KeyboardModifier.NoModifier)
        widget.mouseReleaseEvent(ev)

    def _band(self, panel, system):
        planet = self._find(system, "planet")[0]
        panel._set_oec_selection(planet)
        self.app.processEvents()
        band = panel._oec_pane.widget()._oec_host_band
        self.assertIsNotNone(band)
        return band

    # R3-1 — a real mouse release deleted the band inside its own handler
    def test_a_real_click_on_the_band_does_not_use_a_deleted_widget(self):
        """Selecting the host rebuilds the pane, and `QScrollArea.setWidget()`
        deletes the old one synchronously — including the band being clicked."""
        panel, system = self._panel()
        band = self._band(panel, system)
        self._release(band)                      # raised RuntimeError before the fix
        self.app.processEvents()                 # let the deferred click run
        self.assertIs(panel._oec_sel[0], self._find(system, "star")[0])
        self.assertEqual(panel._oec_pane.widget()._oec_model["tag"], "star")

    # R3-2 — any button, any release position navigated
    def test_only_a_left_release_inside_the_band_navigates(self):
        from PySide6.QtCore import Qt
        panel, system = self._panel()
        planet = self._find(system, "planet")[0]
        band = self._band(panel, system)
        self._release(band, button=Qt.MouseButton.RightButton)
        self.app.processEvents()
        self.assertIs(panel._oec_sel[0], planet, "a right-click navigated")

        band = self._band(panel, system)
        # Qt delivers the release to whoever took the press: dragging off the band
        # and letting go must not count as a click.
        outside = (band.width() + 50, band.height() + 50)
        self._release(band, pos=outside)
        self.app.processEvents()
        self.assertIs(panel._oec_sel[0], planet, "a release outside the band navigated")

    # R3-3 — `QFrame {...}` also matched the child QLabels (QLabel IS-A QFrame)
    def test_the_band_stylesheet_does_not_paint_its_child_labels(self):
        panel, system = self._panel()
        band = self._band(panel, system)
        sheet = band.styleSheet()
        self.assertNotIn("QFrame {", sheet)
        self.assertIn("#oecHostBand", sheet)
        self.assertEqual(band.objectName(), "oecHostBand")

    # R3-4 — the HZ bit formatted an outer bound it had not checked
    def test_a_half_present_hz_costs_one_bit_not_the_whole_band(self):
        from gui.panels.oec_detail import _host_band_derived
        half = {"hz_bounds": {"value": {"conservative_inner_au": 0.7,
                                        "conservative_outer_au": None}},
                "luminosity_lsun": {"value": 0.46}}
        bits = _host_band_derived(half)          # raised TypeError before the fix
        self.assertTrue(any("L 0.46" in b for b in bits))
        self.assertFalse(any(b.startswith("HZ") for b in bits))

    # R3-5 — satellite mass/radius are JUPITER units, labelled M⊕/R⊕ unconverted
    def test_satellite_mass_and_radius_are_converted_from_jupiter_units(self):
        """OEC catalogues a moon like a planet: the Moon is 0.000039 M♃, not M⊕."""
        from gui.panels.catalogs import _oec_tree_cells, _OEC_COL_M, _OEC_COL_R
        from gui.panels.oec_detail import detail_model
        panel, system = self._panel()
        moon = self._find(system, "satellite")[0]     # 0.01 M♃ / 0.3 R♃
        cells = _oec_tree_cells(moon, panel._oec_tree_ctx())
        self.assertIn("M⊕", cells[_OEC_COL_M])
        self.assertIn("3.17", cells[_OEC_COL_M])      # 0.01 × 317.828
        self.assertIn("3.36", cells[_OEC_COL_R])      # 0.3 × 11.209
        rows = {r["label"]: r["value"]
                for s in detail_model(moon, panel._oec_detail_ctx(moon))["sections"]
                for r in s["rows"]}
        self.assertIn("3.17", rows["Mass"])
        self.assertIn("M⊕", rows["Mass"])
        self.assertIn("3.36", rows["Radius"])

    def test_the_real_moon_reads_as_earth_masses(self):
        """A hand-checked anchor: 7.35e22 kg / 1.898e27 = 3.87e-5 M♃ = 0.0123 M⊕,
        and 1737 km is 0.2725 R⊕ — the numbers a reader can sanity-check."""
        from gui.panels.catalogs import _oec_tree_cells, _OEC_COL_M, _OEC_COL_R
        moon = {"tag": "satellite", "names": ["Moon"], "children": [],
                "fields": {"mass": {"value": "0.000039"},
                           "radius": {"value": "0.024847"}}}
        cells = _oec_tree_cells(moon)
        self.assertIn("0.0124", cells[_OEC_COL_M])
        self.assertIn("0.2785", cells[_OEC_COL_R])


# ── R1 review findings — regression pins ─────────────────────────────────────
@unittest.skipUnless(qt_available(), "PySide6 / matplotlib not available")
class R1RegressionTests(OecTestBase):
    """Each test here fails against the code as it stood at the R1 review."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    # R1-1 — every planet mass was labelled M·sin i
    def test_a_plain_mass_is_not_labelled_msini(self):
        from gui.panels.catalogs import _oec_tree_item, _OEC_COL_M
        node = {"tag": "planet", "names": ["X b"],
                "fields": {"mass": {"value": "2.5"}}, "children": []}
        self._item = _oec_tree_item(node)
        text = self._item.text(_OEC_COL_M)
        self.assertNotIn("sin", text)
        self.assertTrue(text.startswith("2.5"), text)

    def test_an_msini_mass_still_is(self):
        from gui.panels.catalogs import _oec_tree_item, _OEC_COL_M
        node = {"tag": "planet", "names": ["X b"],
                "fields": {"mass": {"value": "2.5", "type": "msini"}}, "children": []}
        self._item = _oec_tree_item(node)
        self.assertTrue(self._item.text(_OEC_COL_M).startswith("M·sin i"))

    # R1-2 — the synced row must actually read as selected
    def test_programmatic_sync_leaves_the_row_selected(self):
        from gui.panels.catalogs import OecPanel, _oec_item_node
        from tests.test_oec import _FakeWindow
        panel = OecPanel(_FakeWindow())
        system = self._system("Hierarchy")
        panel._on_oec_result({"system": system, "_hypatia": {}})
        target = self._find(system, "star", "Inner A")[0]
        panel._set_oec_selection(target)
        self.app.processEvents()
        item = panel._oec_tree.currentItem()
        self.assertIs(_oec_item_node(item), target)
        self.assertTrue(item.isSelected(),
                        "the synced row is the current item but is not selected")

    # R1-3 / R2a-1 — `_HANDLED_ELSEWHERE` keys are removed from the fallback for
    # EVERY tag, so every tag's plan must actually render them. Parameterised over
    # all five tags: hard-coding "planet" hid the fact that the star plan had no
    # Description section at all.
    def test_every_handled_elsewhere_key_is_rendered_for_every_tag(self):
        from gui.panels.oec_detail import detail_model, _HANDLED_ELSEWHERE
        for tag in ("system", "binary", "star", "planet", "satellite"):
            node = {"tag": tag, "names": ["X"], "children": [], "fields": {
                "list": {"value": "Confirmed planets"},
                "description": {"value": "a description"},
                "imagedescription": {"value": "art caption"},
                "image": {"value": "http://example.invalid/x.png"},
            }}
            model = detail_model(node)
            rendered = " ".join(r["value"] for s in model["sections"]
                                for r in s["rows"])
            rendered += " " + " ".join(model["badges"])
            for key in _HANDLED_ELSEWHERE:
                self.assertIn(node["fields"][key]["value"], rendered,
                              f"{tag}.{key} is excluded from the fallback and "
                              "rendered nowhere")

    # R2a-3 — view state must survive a new search
    def test_view_state_survives_a_second_search(self):
        from gui.panels.catalogs import OecPanel
        from tests.test_oec import _FakeWindow
        panel = OecPanel(_FakeWindow())
        panel._on_oec_result({"system": self._system("Single Star"), "_hypatia": {}})
        panel._on_oec_pane_position("Below")
        panel._on_oec_hide_empty(False)
        panel._on_oec_result({"system": self._system("Hierarchy"), "_hypatia": {}})
        self.assertEqual(panel._oec_view["pane"], "Below")
        self.assertFalse(panel._oec_view["hide_empty"])
        self.assertEqual(panel._oec_pane_combo.currentText(), "Below")
        self.assertFalse(panel._oec_hide_empty_box.isChecked())

    # R1-4 — symmetry of error bars is a numeric question
    def test_textually_different_but_equal_errors_render_as_plus_minus(self):
        from gui.panels.oec_detail import oec_value_cell
        cell = oec_value_cell({"value": "0.79", "errorminus": "0.06",
                               "errorplus": "0.060"}, "R☉")
        self.assertIn("±", cell)
        self.assertNotIn("/", cell)

    def test_genuinely_asymmetric_errors_still_render_both(self):
        from gui.panels.oec_detail import oec_value_cell
        cell = oec_value_cell({"value": "0.79", "errorminus": "0.06",
                               "errorplus": "0.09"})
        self.assertIn("+0.09", cell)
        self.assertIn("-0.06", cell)

    # R1-5 — a hidden column must be recoverable
    def test_hide_empty_can_be_turned_off_again(self):
        from gui.panels.catalogs import OecPanel, _OEC_COL_M
        from tests.test_oec import _FakeWindow
        panel = OecPanel(_FakeWindow())
        panel._on_oec_result({"system": self._system("Zero Planet"), "_hypatia": {}})
        self.assertTrue(panel._oec_tree.isColumnHidden(_OEC_COL_M))
        panel._on_oec_hide_empty(False)
        self.assertFalse(panel._oec_tree.isColumnHidden(_OEC_COL_M))
        panel._on_oec_hide_empty(True)
        self.assertTrue(panel._oec_tree.isColumnHidden(_OEC_COL_M))

    # R1-6 — repeated fields must not lose their other values
    def test_repeated_field_renders_every_value_in_the_pane(self):
        from gui.panels.oec_detail import detail_model
        binary = self._find(self._system("Binary S"), "binary")[0]
        rows = {r["label"]: r["value"] for s in detail_model(binary)["sections"]
                for r in s["rows"]}
        self.assertIn("arcsec", rows["Separation"])
        self.assertIn("AU", rows["Separation"])

    def test_repeated_field_renders_every_value_in_the_tooltip(self):
        from gui.panels.catalogs import _oec_node_tooltip
        binary = self._find(self._system("Binary S"), "binary")[0]
        tip = _oec_node_tooltip(binary)
        self.assertIn("arcsec", tip)
        self.assertIn("400", tip)

    def test_the_tree_cell_stays_first_value_only(self):
        from gui.panels.catalogs import _oec_value_cell
        field = [{"value": "80", "unit": "arcsec"}, {"value": "400", "unit": "AU"}]
        self.assertEqual(_oec_value_cell(field), "80 arcsec")


if __name__ == "__main__":
    unittest.main()
