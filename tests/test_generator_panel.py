# tests/test_generator_panel.py — Phase R1 R1-C5: SystemGeneratorPanel GUI smoke tests.
# Headless (offscreen). Skipped if PySide6 is absent. Synthetic mode is offline/pure
# (it reads the auto-seeded main_sequence_stars table), so no network/mocking is needed.

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    _GUI_OK = True
except Exception:
    _GUI_OK = False


class _FakeNav:
    def show(self): pass
    def hide(self): pass


class _FakeWindow:
    def __init__(self):
        self.nav_tree = _FakeNav()

    def statusBar(self):
        class _SB:
            def showMessage(self, *a): pass
        return _SB()


@unittest.skipUnless(_GUI_OK, "PySide6 not available")
class GeneratorPanelSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self):
        from gui.panels.generator import SystemGeneratorPanel
        return SystemGeneratorPanel(_FakeWindow())

    def test_constructs_in_synthetic_mode(self):
        p = self._panel()
        self.assertTrue(p._rb_synth.isChecked())
        self.assertFalse(p._copy_btn.isEnabled())
        # Synthetic mode: anchor disabled, chips enabled.
        self.assertFalse(p._anchor.isEnabled())
        self.assertTrue(p._chips["K"].isEnabled())

    def test_mode_toggle_enables_anchor_disables_chips(self):
        p = self._panel()
        p._rb_anchor.setChecked(True)
        self.assertTrue(p._anchor.isEnabled())
        self.assertFalse(p._chips["K"].isEnabled())
        self.assertFalse(p._subtype.isEnabled())

    def test_chip_single_select(self):
        p = self._panel()
        p._chips["G"].setChecked(True)
        p._on_chip("G")
        p._chips["K"].setChecked(True)
        p._on_chip("K")
        self.assertFalse(p._chips["G"].isChecked())
        self.assertEqual(p._selected_class(), "K")
        self.assertEqual(p._build_spectral_class(), "K")
        p._subtype.setText("2V")
        self.assertEqual(p._build_spectral_class(), "K2V")

    def test_synthetic_generate_builds_table_and_viz(self):
        p = self._panel()
        p._seed.setText("4173")
        p._chips["G"].setChecked(True); p._on_chip("G")
        p._subtype.setText("2V")
        p._planets.setValue(5)
        p._generate()

        # Result captured, planet table built.
        self.assertIsNotNone(p._last_result)
        self.assertEqual(p._last_result["mode"], "synthetic")
        self.assertEqual(len(p._last_result["planets"]), 5)
        self.assertEqual(p._planet_table.model().rowCount(), 5)
        self.assertTrue(p._copy_btn.isEnabled())

        # Viz tabs: Orbit Diagram + HZ Ring (only when matplotlib is present).
        from gui.visualizations.plot_helpers import mpl_available
        if mpl_available():
            labels = [p._viz_tabs_widget.tabText(i)
                      for i in range(p._viz_tabs_widget.count())]
            self.assertIn("Orbit Diagram", labels)
            self.assertIn("HZ Ring", labels)

    def test_auto_planet_count_uses_sampling(self):
        # Spinner minimum (-1) reads as Auto → n_planets=None (sampled, not an error).
        p = self._panel()
        p._planets.setValue(-1)
        p._seed.setText("88")
        p._generate()
        self.assertIsNotNone(p._last_result)
        self.assertNotIn("error", p._last_result)

    def test_bad_seed_shows_error_no_result(self):
        p = self._panel()
        p._seed.setText("not-an-int")
        p._generate()
        self.assertIsNone(p._last_result)
        self.assertFalse(p._copy_btn.isEnabled())

    def test_error_result_surfaces_and_disables_copy(self):
        p = self._panel()
        # O-class is rejected by the engine → curated error rendered, no Copy.
        p._render({"error": "Spectral class O is not supported for generation."})
        self.assertFalse(p._copy_btn.isEnabled())
        self.assertIsNone(p._last_result)

    def test_panel_in_nav(self):
        from gui.nav import NAVIGATION
        cats = dict(NAVIGATION)
        self.assertIn("Generator", cats)
        self.assertIn(("System Generator", "SystemGeneratorPanel"), cats["Generator"])

    def test_panel_exported(self):
        import gui.panels as panels
        self.assertTrue(hasattr(panels, "SystemGeneratorPanel"))


@unittest.skipUnless(_GUI_OK, "PySide6 not available")
class GeneratorPanelFeasibility(unittest.TestCase):
    """R2-C7 — the constraint builder + four-layer feasibility render."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self):
        from gui.panels.generator import SystemGeneratorPanel
        return SystemGeneratorPanel(_FakeWindow())

    def test_add_and_remove_constraint_rows(self):
        p = self._panel()
        r1 = p._add_constraint_row()
        p._add_constraint_row()
        self.assertEqual(len(p._constraint_rows), 2)
        p._remove_constraint_row(r1)
        self.assertEqual(len(p._constraint_rows), 1)

    def test_constraint_row_to_spec_each_type(self):
        from gui.panels.generator import _CONSTRAINT_TYPES
        p = self._panel()
        row = p._add_constraint_row()
        for t in _CONSTRAINT_TYPES:
            row._type.setCurrentText(t)
            spec = row.to_spec()
            self.assertEqual(spec["type"], t)
        # Default planet_at_location row builds a usable in_hz location spec.
        row._type.setCurrentText("planet_at_location")
        spec = row.to_spec()
        self.assertEqual(spec["location"]["kind"], "in_hz")
        self.assertEqual(spec["planet_type"], "terrestrial")
        self.assertAlmostEqual(spec["mass_earth"], 1.0)

    def test_feasibility_generate_builds_cards(self):
        p = self._panel()
        p._seed.setText("7")
        p._chips["G"].setChecked(True); p._on_chip("G")
        p._subtype.setText("2V")
        p._planets.setValue(5)
        p._add_constraint_row()   # default planet_at_location, in_hz
        p._generate()
        # Feasibility envelope captured + a 4-layer card builds without error.
        self.assertIn("constraints", p._last_result)
        self.assertIn("feasible", p._last_result)
        self.assertEqual(len(p._last_result["constraints"]), 1)
        card = p._make_constraint_card(p._last_result["constraints"][0], 0)
        self.assertIsNotNone(card)
        # The satisfied system still renders (table + viz tabs).
        self.assertEqual(p._planet_table.model().rowCount(), 5)
        self.assertTrue(p._copy_btn.isEnabled())

    def test_zero_constraints_keeps_r1_path(self):
        p = self._panel()
        p._seed.setText("7")
        p._chips["G"].setChecked(True); p._on_chip("G"); p._subtype.setText("2V")
        p._planets.setValue(4)
        p._generate()                         # no constraint rows
        self.assertNotIn("constraints", p._last_result)
        self.assertEqual(p._last_result["mode"], "synthetic")

    def test_apply_alternative_reruns_deterministically(self):
        p = self._panel()
        # Seed the params + active specs directly, then apply a location patch.
        p._last_params = {"mode": "synthetic", "seed": 7, "anchor": None,
                          "spectral_class": "G2V", "n_planets": 5, "require": False,
                          "nbody": False}
        p._apply_depth = 0
        p._active_specs = [{"type": "planet_at_location", "planet_type": "terrestrial",
                            "mass_earth": 1.0, "location": {"kind": "at", "au": 0.3}}]
        p._apply_alternative(0, {"location": {"kind": "in_hz"}}, "→ HZ")
        self.assertEqual(p._apply_depth, 1)
        self.assertIn("constraints", p._last_result)
        self.assertEqual(p._active_specs[0]["location"]["kind"], "in_hz")

    def test_apply_alternative_depth_capped(self):
        p = self._panel()
        p._last_params = {"mode": "synthetic", "seed": 7, "anchor": None,
                          "spectral_class": "G2V", "n_planets": 3, "require": False,
                          "nbody": False}
        p._active_specs = [{"type": "planet_at_location", "planet_type": "terrestrial",
                            "mass_earth": 1.0, "location": {"kind": "in_hz"}}]
        p._apply_depth = 6
        p._apply_alternative(0, {"mass_earth": 0.1}, "shrink")   # over the cap → no-op
        self.assertEqual(p._apply_depth, 6)

    def test_nbody_checkbox_present(self):
        p = self._panel()
        self.assertFalse(p._nbody_chk.isChecked())


# ── R3-C7 · research-policy selector + Import Research Priors panel ───────────
import shutil
import tempfile
from unittest import mock

from core.research_priors import compute_research_priors_ingest

_RP_SAMPLE = os.path.join(os.path.dirname(__file__), "fixtures", "research_priors_sample.json")


@unittest.skipUnless(_GUI_OK, "PySide6 not available")
class GeneratorPanelResearchPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache, ignore_errors=True)

    def _panel(self):
        from gui.panels.generator import SystemGeneratorPanel
        return SystemGeneratorPanel(_FakeWindow())

    def test_policy_selector_default_permissive(self):
        p = self._panel()
        self.assertEqual(p._policy.currentText(), "permissive")
        self.assertEqual(p._priors_pill.text(), "DEFAULTS")

    def test_strict_no_cache_surfaces_error(self):
        p = self._panel()
        p._seed.setText("1")
        p._chips["K"].setChecked(True); p._on_chip("K"); p._subtype.setText("2V")
        p._policy.setCurrentText("strict")
        with mock.patch("core.priors._DEFAULT_CACHE_DIR", self.cache):
            p._generate()                      # empty cache → curated error
        self.assertIsNone(p._last_result)
        self.assertFalse(p._copy_btn.isEnabled())

    def test_strict_with_cache_flips_grounding(self):
        compute_research_priors_ingest(path=_RP_SAMPLE, cache_dir=self.cache)
        p = self._panel()
        p._seed.setText("42")
        p._chips["G"].setChecked(True); p._on_chip("G"); p._subtype.setText("2V")
        p._planets.setValue(5)
        with mock.patch("core.priors._DEFAULT_CACHE_DIR", self.cache), \
             mock.patch("core.research_priors._DEFAULT_CACHE_DIR", self.cache):
            p._policy.setCurrentText("strict")        # fires the pill update
            self.assertIn("RESEARCH", p._priors_pill.text())
            p._generate()
        self.assertIsNotNone(p._last_result)
        self.assertEqual(p._last_result["star"]["grounding"], "research-calibrated")


@unittest.skipUnless(_GUI_OK, "PySide6 not available")
class ImportResearchPriorsPanelSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self):
        from gui.panels.csv_utility import ImportResearchPriorsPanel
        return ImportResearchPriorsPanel(_FakeWindow())

    def test_prefills_the_discovered_default_contract_path(self):
        # v2.11.0: the panel prefills default_priors_source() — the sister repo's live
        # research_priors_v2.json when it sits beside this repo, else the committed sample.
        import core.research_priors as rp
        p = self._panel()
        self.assertEqual(p._path_edit.text(), str(rp.default_priors_source()))
        self.assertTrue(p._path_edit.text().endswith(".json"))

    def test_prefill_falls_back_to_sample_without_a_sibling(self):
        from unittest import mock
        import core.research_priors as rp
        with mock.patch.object(rp, "_discover_sister_contract", return_value=None):
            p = self._panel()
            self.assertTrue(p._path_edit.text().endswith("research_priors_sample.json"))

    def test_on_done_summary(self):
        p = self._panel()
        p._on_done({"dataset_version": "sample-2026-06-24", "schema_version": "1.0",
                    "axes_loaded": 6, "origin_contexts": 10, "source": "s", "cache_dir": "c"})
        self.assertEqual(p._progress_bar.format(), "Done")

    def test_on_done_error(self):
        p = self._panel()
        p._on_done({"error": "research-priors contract: bad"})
        self.assertEqual(p._progress_bar.format(), "Error")

    def test_on_error(self):
        p = self._panel()
        p._on_error_rp("boom")
        self.assertEqual(p._progress_bar.format(), "Error")

    def test_check_with_no_cache_renders(self):
        p = self._panel()
        with mock.patch("core.research_priors._DEFAULT_CACHE_DIR", self.tmp()):
            p._check()        # must not raise; renders the "no priors" label

    def tmp(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        return d

    def test_nav_and_export(self):
        from gui.nav import NAVIGATION
        cats = dict(NAVIGATION)
        self.assertIn(("Import Research Priors", "ImportResearchPriorsPanel"),
                      cats["Utilities"])
        import gui.panels as panels
        self.assertTrue(hasattr(panels, "ImportResearchPriorsPanel"))


if __name__ == "__main__":
    unittest.main()
