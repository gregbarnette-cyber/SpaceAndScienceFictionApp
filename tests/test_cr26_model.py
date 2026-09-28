"""CR-26 — the pure wind model + the WB data loader (plan §1–§2; test groups 1–11).

Offline, no network, no Qt. Anchors are the WB spec's (``spaceapp-change-request-CR26-xray-tier-wind-model.md``
§Acceptance A1–A5) and the channel rulings (MSG 287–302).
"""

import hashlib
import math
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from core import shared
from core import stellar_wind as sw
from core import stellar_wind_tables as swt
from core.stellar_wind import StarWindInputs as I, MDOT_SUN, PC_CM, RSUN_CM

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data" / "cr26"


def _dex(a, b):
    return abs(math.log10(a / b))


def _f_x(x_sys, rsq, d_pc=10.0):
    """The at-Earth fit-scale flux that gives system log F_X ``x_sys`` over ΣR² ``rsq`` at ``d_pc``."""
    return 10 ** x_sys * rsq * RSUN_CM ** 2 / (d_pc * PC_CM) ** 2


def _rungs(det_rung="2RXS", cand=None, others=None):
    st = {"2RXS": "no_detection", "eRASS1": "out_of_footprint", "XMM": "no_detection"}
    st.update(others or {})
    if det_rung:
        st[det_rung] = "detection"
    return [{"rung": r, "status": st[r], "cand": (cand if r == det_rung else None)} for r in sw.RUNGS]


def _run(**kw):
    kw.setdefault("measured_ids", [kw["main_id"]] if kw.get("main_id") else [])
    return sw.resolve_wind_model(I(**kw))


class TablesTest(unittest.TestCase):
    """Group 1 — the md5-checked loader."""

    def setUp(self):
        swt.clear_cr26_cache()
        self.addCleanup(swt.clear_cr26_cache)

    def test_repo_copies_match_pinned_md5s(self):
        for name, md5 in swt.CR26_MD5.items():
            raw = (DATA / name).read_bytes()
            self.assertEqual(hashlib.md5(raw).hexdigest(), md5, name)
            self.assertNotIn(b"\r", raw, f"{name} carries CR bytes — .gitattributes -text must hold")

    def test_gitattributes_unsets_text(self):
        if not shutil.which("git"):
            self.skipTest("git not available")
        out = subprocess.run(["git", "check-attr", "text", "data/cr26/cr26_measured_tier.csv"],
                             cwd=REPO, capture_output=True, text=True)
        if out.returncode != 0:
            self.skipTest("not a git checkout")
        self.assertIn("text: unset", out.stdout)

    def test_md5_mismatch_raises(self):
        with tempfile.TemporaryDirectory() as d:
            for name in swt.CR26_MD5:
                shutil.copy(DATA / name, d)
            with open(os.path.join(d, "cr26_line_halfwidth.csv"), "ab") as fh:
                fh.write(b"\n")
            os.environ["SPACE_APP_CR26_DATA_DIR"] = d
            try:
                with self.assertRaises(swt.Cr26DataError) as cm:
                    swt.load_cr26_tables()
                self.assertIn("md5", str(cm.exception))
            finally:
                del os.environ["SPACE_APP_CR26_DATA_DIR"]

    def test_missing_file_raises(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["SPACE_APP_CR26_DATA_DIR"] = d
            try:
                with self.assertRaises(swt.Cr26DataError):
                    swt.load_cr26_tables()
            finally:
                del os.environ["SPACE_APP_CR26_DATA_DIR"]

    def test_structure(self):
        t = swt.load_cr26_tables()
        self.assertEqual(len(t["MEASURED"]), 36)
        self.assertEqual(len(t["CLASS_STATES"]), 17)
        self.assertEqual(set(t["FORK8"]), set(swt.CLASS_BINS))
        self.assertIn("M0–M3.5", t["FORK8"])                    # the en dash
        self.assertEqual(sum(len(v) for v in t["FORK9"].values()), 455)
        self.assertEqual(len(t["SUBTYPE_R"]), 40)
        self.assertEqual(len(t["HW"]), 601)
        # fork-9 top rows equal the fork-8 typical point + band (the spec's file consistency check)
        for b in swt.CLASS_BINS:
            top = t["FORK9"][b][160]
            self.assertAlmostEqual(top["point_log"], t["FORK8"][b]["point_log"], places=3)
            self.assertEqual((top["band_lo"], top["band_hi"]),
                             (t["FORK8"][b]["band_lo"], t["FORK8"][b]["band_hi"]))
        # rule ↔ scope
        for r in t["MEASURED"].values():
            self.assertEqual(r["measured_rule"] == "point_combined", r["wood_scope"] == "combined_unsplit")

    def test_hw_pins(self):
        self.assertEqual([sw.hw(x) for x in (4.0, 5.0, 6.0, 7.0)], [0.2190, 0.1385, 0.2475, 0.4169])
        self.assertEqual(sw.hw(6.04), 0.2539)
        self.assertEqual(sw.hw(1.0), sw.hw(2.0))          # clamped
        self.assertEqual(sw.hw(9.0), sw.hw(8.0))


class ParsingTest(unittest.TestCase):
    """Group 2 — parse_sp, scope, bins."""

    def test_pins(self):
        for sp, want in [("dM6", ("M", 6.0, False)), ("K2+V", ("K", 2.0, False)), ("M4.0Ve", ("M", 4.0, False)),
                         ("K7-M0", ("K", 7.0, False)), ("F1-F2V", ("F", 1.0, False)),
                         ("sdM1", ("M", 1.0, True)), ("esdK7", ("K", 7.0, True)), ("M", ("M", None, False)),
                         ("M V", ("M", None, False)), ("kA5hF0mF2", ("A", 5.0, False)),
                         ("A0mA1", ("A", 0.0, False))]:
            self.assertEqual(sw.parse_sp(sp), want, sp)

    def test_prefix_constant_is_a_subset_of_the_one_parser(self):
        self.assertTrue(set(shared._SP_DWARF_SUBDWARF_PREFIXES) <= set(shared._SP_CLASS_PREFIXES))
        self.assertNotIn("k", shared._SP_DWARF_SUBDWARF_PREFIXES)      # H7: Am prefixes are not dwarf markers

    def test_bins(self):
        self.assertEqual(sw.class_bin("M", 3.5), "M0–M3.5")
        self.assertEqual(sw.class_bin("M", 4.0), "M4+")
        self.assertIsNone(sw.class_bin("M", None))
        self.assertEqual(sw.class_bin("K", None), "K")
        self.assertIsNone(sw.class_bin("A", 0))

    def test_subtype_unknown(self):
        r = _run(sp_type="M V")
        self.assertEqual(r["mass_loss_tier"], "none")
        self.assertIn("subtype_unknown", r["wind_model"]["flags"])
        self.assertEqual(r["wind_model"]["tiers"], {})

    def test_subdwarf_note(self):
        r = _run(sp_type="sdM1")
        self.assertIn(sw.NOTE_SUBDWARF, r["wind_model"]["notes"])

    def test_h7_am_string(self):
        r = _run(sp_type="kA5hF0mF2", cr25_letter="K")
        self.assertEqual(r["mass_loss_tier"], "noncoronal_row")
        self.assertEqual(r["h7_letter"], "A")
        self.assertIn(sw.NOTE_H7.format(letter="A"), r["wind_model"]["notes"])
        r = _run(sp_type="A0mA1", cr25_letter="A")
        self.assertIsNone(r["h7_letter"])


class RelationTest(unittest.TestCase):
    """Group 3 — relation, bands, widening, flags."""

    def test_a1(self):
        for x, want in [(4.0, -0.347), (4.42, -0.098), (5.0, 0.245), (6.0, 0.837), (7.0, 1.429)]:
            self.assertAlmostEqual(sw.per_area_log(x), want, places=3)
        lo, hi = sw.regime_band(5.0)
        self.assertAlmostEqual(lo, -0.861, places=3)
        self.assertAlmostEqual(hi, 1.208, places=3)
        self.assertAlmostEqual(sw.regime_band(6.04)[1], 1.227, places=3)

    def test_regime_edges(self):
        self.assertEqual([sw.regime_of(x) for x in (4.84, 4.86, 5.99, 6.01)], ["quiet", "mid", "mid", "active"])

    def test_widening_examples(self):
        # F typical class default −0.99 → −1.62
        lo, hi, ext = sw.widen(-0.99, 1.05, 5.3137, "F", 5)
        self.assertAlmostEqual(lo, -1.62, places=2)
        self.assertEqual(ext, "f_dwarf")
        # a fast rotator at log F_X 7.3 → upper ≈ +2.05
        lo, hi, _ = sw.widen(*sw.regime_band(7.3), 7.3, "K", 2, fast_rotator=True)
        self.assertAlmostEqual(hi, 2.05, places=2)
        # GJ 65 (active 6.04, ±1.227) → ±1.243
        lo, hi, ext = sw.widen(*sw.regime_band(6.04), 6.04, "M", 5.5)
        self.assertAlmostEqual(hi, 1.243, places=3)
        self.assertAlmostEqual(lo, -1.243, places=3)
        self.assertEqual(ext, "late_m")

    def test_fast_rotator_boundary(self):
        self.assertIn("fast_rotator", _run(sp_type="K2V", log_fx=5.0, prot_days=0.5)["wind_model"]["flags"])
        self.assertNotIn("fast_rotator", _run(sp_type="K2V", log_fx=5.0, prot_days=0.51)["wind_model"]["flags"])

    def test_above_fit_range_strict(self):
        self.assertNotIn("above_fit_range", _run(sp_type="M3V", log_fx=7.2)["wind_model"]["flags"])
        self.assertIn("above_fit_range", _run(sp_type="M3V", log_fx=7.21)["wind_model"]["flags"])

    def test_below_fit_range(self):
        self.assertIn("below_fit_range", _run(sp_type="G2V", wind_state="quiet")["wind_model"]["flags"])  # 3.9947
        self.assertIn("below_fit_range", _run(sp_type="G2V", log_fx=3.90)["wind_model"]["flags"])
        self.assertNotIn("below_fit_range", _run(sp_type="G2V", log_fx=4.03)["wind_model"]["flags"])
        # a fork-9 conditional below 4.03 (F 3.90 row, conditional 3.90)
        r = _run(sp_type="F5V", log_fx_limit=3.92)
        self.assertEqual(r["wind_model"]["log_fx"], 3.90)
        self.assertIn("below_fit_range", r["wind_model"]["flags"])
        # H5: upper_limit_only with a limit < 4.03
        r = _run(sp_type="K1V", log_fx_limit=4.0)
        self.assertTrue(r["upper"])
        self.assertIn("below_fit_range", r["wind_model"]["flags"])

    def test_regime_edge_note(self):
        def has_edge(r):
            return any("regime edge" in n for n in r["wind_model"]["notes"])
        self.assertTrue(has_edge(_run(sp_type="F5V", wind_state="active")))       # F active 5.9449
        self.assertTrue(has_edge(_run(sp_type="G2V", wind_state="active")))       # G active 6.1355
        self.assertFalse(has_edge(_run(sp_type="K2V")))                           # typical mixture: never
        self.assertFalse(has_edge(_run(sp_type="K2V", log_fx_limit=4.735)))       # truncated mixture: never
        self.assertTrue(has_edge(_run(sp_type="K2V", log_fx=5.9)))


class MeasuredTest(unittest.TestCase):
    """Group 4 — A2."""

    def _m(self, mid, **kw):
        kw.setdefault("sp_type", "K2V")
        r = _run(main_id=mid, **kw)
        self.assertEqual(r["mass_loss_tier"], "measured", mid)
        return r

    def test_a2_points(self):
        for mid, want in [("V* EV Lac", 1.0), ("* eps Eri", 30), ("* 70 Oph A", 55.7), ("* 70 Oph B", 44.3),
                          ("* alf Cen A", 0.46), ("* alf Cen B", 1.54), ("* 61 Cyg A", 0.5),
                          ("NAME Proxima Centauri", 0.2), ("* tau Cet", 0.1), ("HD 1326", 8.2569),
                          ("HD 1326B", 1.7431), ("HD 239960A", 0.0832), ("HD 239960B", 0.0668),
                          ("HD 79210", 0.25), ("* ksi Boo A", 0.5), ("* 36 Oph A", 8.5)]:
            r = self._m(mid)
            self.assertAlmostEqual(r["rate"] / MDOT_SUN, want, places=4, msg=mid)

    def test_whitespace_collapse(self):
        self.assertAlmostEqual(self._m("HD   1326")["rate"] / MDOT_SUN, 8.2569, places=4)
        self.assertAlmostEqual(self._m("HD  95735")["rate"] / MDOT_SUN, 0.1, places=6)

    def test_span_bands(self):
        r = self._m("* eps Eri")
        self.assertAlmostEqual(r["band_dex"][0], -0.284, places=3)
        self.assertEqual(r["band_dex"][1], 0.0)
        self.assertEqual(r["wind_model"]["band_construction"], "measured_span")
        r = self._m("* 70 Oph A")
        self.assertAlmostEqual(r["band"][0] / MDOT_SUN, 37.04, places=2)
        r = self._m("* 70 Oph B")
        self.assertAlmostEqual(r["band"][0] / MDOT_SUN, 29.46, places=2)

    def test_rules_and_flags(self):
        self.assertIn("method_conflict", self._m("* alf Cen A")["wind_model"]["flags"])
        r = self._m("* 61 Cyg A")
        self.assertIn("method_mixed", r["wind_model"]["flags"])
        self.assertEqual(r["wind_model"]["measured"]["system_upper_edge_mdot_sun"], 9.6)
        self.assertIn(sw.NOTE_SYSTEM_EDGE.format(edge=9.6), r["wind_model"]["notes"])
        r = self._m("NAME Proxima Centauri")
        self.assertTrue(r["upper"])
        self.assertIn("measured_upper_limit", r["wind_model"]["flags"])
        self.assertIn("measured_combined_split", self._m("HD 1326")["wind_model"]["flags"])
        wm = self._m("V* EV Lac")["wind_model"]
        for k in ("per_area_log", "log_fx", "regime", "state"):
            self.assertIsNone(wm[k], k)

    def test_t12_direction_note(self):
        # Proxima: an X-ray point below the 0.2 limit → the "below" note
        f = _f_x(5.5, 0.14 ** 2)
        r = _run(sp_type="M5.5Ve", main_id="NAME Proxima Centauri", network=True, d_pc=10.0,
                 rungs=_rungs("2RXS", {"f_x": f}), radius_candidates=[{"source": "tic", "value": 0.14}])
        self.assertEqual(r["mass_loss_tier"], "measured")
        self.assertTrue(any("lies below the Wood upper limit" in n for n in r["wind_model"]["notes"]))
        self.assertEqual(r["wind_model"]["tiers"]["xray"]["status"], "ok")

    def test_evolved_host(self):
        r = _run(sp_type="G8IV", domain="evolved", main_id="* del Pav", noncoronal_rate=5e-14)
        self.assertEqual(r["mass_loss_tier"], "measured")
        self.assertAlmostEqual(r["rate"] / MDOT_SUN, 10.0)
        self.assertIsNone(r["label"])
        self.assertEqual(list(r["wind_model"]["tiers"]), ["noncoronal_row"])
        self.assertIn(sw.DISCLOSURE_MEASURED["evolved_v400"], r["wind_model"]["notes"])


class ClassDefaultTest(unittest.TestCase):
    """Group 5 — A5 (±0.001 dex; the spec's A5 values use the fork-8 3-dp point). Re-pinned to WB's MSG 311 A5
    table after the class-statistics re-vendor (the spec's printed A5 values are superseded — §4 ruling 21)."""

    def test_a5(self):
        for sp, want, lo, hi in [("F5V", 5.7702, -1.62, 1.05), ("G2V", 1.2597, -0.74, 1.14),
                                 ("K2V", 1.1373, -0.81, 1.11), ("M3V", 0.1903, -0.75, 1.10),
                                 ("M4V", 0.1477, -0.94, 1.27), ("M5V", 0.0879, -0.961, 1.286)]:
            r = _run(sp_type=sp)
            self.assertEqual(r["mass_loss_tier"], "class_default")
            self.assertLess(_dex(r["rate"] / MDOT_SUN, want), 0.001 + 1e-9, sp)
            self.assertAlmostEqual(r["band_dex"][0], lo, delta=0.006)
            self.assertAlmostEqual(r["band_dex"][1], hi, delta=0.006)
            self.assertEqual(r["label"], "solar")
            self.assertEqual(r["wind_model"]["state"], "typical")
            self.assertEqual(r["wind_model"]["band_construction"], "class_mixture")
            self.assertIsNotNone(r["wind_model"]["regime"])            # G5: set on the mixtures too

    def test_states(self):
        r = _run(sp_type="G2V", wind_state="quiet")
        self.assertAlmostEqual(r["rate"] / MDOT_SUN, 0.4474, places=4)
        self.assertIn("marginal_state", r["wind_model"]["flags"])
        self.assertEqual(r["label"], "quiet")
        self.assertIn(sw.DISCLOSURES[8], r["wind_model"]["notes"])
        self.assertAlmostEqual(_run(sp_type="K2V", wind_state="quiet")["rate"] / MDOT_SUN, 0.3944, places=4)
        r = _run(sp_type="K2V", wind_state="active")
        self.assertAlmostEqual(r["rate"] / MDOT_SUN, 2.8595, places=4)
        self.assertEqual(r["label"], "active")

    def test_modes(self):
        r = _run(sp_type="M4V")
        self.assertIn("bimodal_class", r["wind_model"]["flags"])
        m = {x["name"]: x for x in r["wind_model"]["modes"]}
        self.assertAlmostEqual(m["inactive"]["weight"], 0.4644)
        self.assertAlmostEqual(m["inactive"]["mass_loss_msun_yr"] / MDOT_SUN, 0.0553, places=4)
        self.assertAlmostEqual(m["saturated"]["mass_loss_msun_yr"] / MDOT_SUN, 0.4892, places=4)
        self.assertIn("extrapolated", _run(sp_type="M5V")["wind_model"]["flags"])

    def test_g10_state_selector(self):
        r = _run(sp_type="K2V", wind_class="solar", wind_state="active")
        self.assertEqual(r["wind_model"]["state"], "typical")
        r = _run(sp_type="F5V", wind_class="f_dwarf")
        self.assertEqual(r["mass_loss_tier"], "noncoronal_row")
        self.assertIn(sw.NOTE_G10_BYPASS.format(wc="f_dwarf"), r["wind_model"]["notes"])

    def test_hot(self):
        r = _run(sp_type="K2V", wind_state="hot")
        self.assertEqual(r["mass_loss_tier"], "noncoronal_row")
        self.assertTrue(r["hot"])
        # hot under a data tier: unused, label falls through (J2)
        r = _run(sp_type="K2V", wind_state="hot", log_fx=5.0)
        self.assertEqual(r["mass_loss_tier"], "xray")
        self.assertEqual(r["label"], "solar")

    def test_otype_auto(self):
        r = _run(sp_type="M4V", active_otype=True)
        self.assertEqual(r["label"], "active")
        self.assertEqual(r["state_source"], "otype_auto")
        self.assertIn(sw.DISCLOSURES[14], r["wind_model"]["notes"])
        self.assertEqual(_run(sp_type="G2V", active_otype=True)["label"], "solar")     # K/M only

    def test_subtype_unknown_branches(self):
        # detection + catalog radius → X-ray tier, radius_unchecked, no late-M widening
        f = _f_x(5.5, 0.2 ** 2)
        r = _run(sp_type="M", network=True, d_pc=10.0, rungs=_rungs("2RXS", {"f_x": f}),
                 radius_candidates=[{"source": "tic", "value": 0.2}])
        self.assertEqual(r["mass_loss_tier"], "xray")
        self.assertIn("radius_unchecked", r["wind_model"]["flags"])
        self.assertIn("subtype_unknown", r["wind_model"]["flags"])
        self.assertIsNone(r["wind_model"]["extrapolation_class"])
        self.assertEqual(r["wind_model"]["tiers"]["class_default"]["status"], "not_reachable")
        # a limit only → none
        r = _run(sp_type="M", network=True, d_pc=10.0, rungs=_rungs(None),
                 limit={"status": None, "f_limit": 1e-13, "survey": "RASS"},
                 radius_candidates=[{"source": "tic", "value": 0.2}])
        self.assertEqual(r["mass_loss_tier"], "none")
        # a failed rung → none + not_authoritative
        r = _run(sp_type="M", network=True, d_pc=10.0, rungs=_rungs(None, others={"2RXS": "timeout"}),
                 radius_candidates=[{"source": "tic", "value": 0.2}])
        self.assertEqual(r["mass_loss_tier"], "none")
        self.assertIn("not_authoritative", r["wind_model"]["flags"])
        # --wind-state → the H3 note
        r = _run(sp_type="M", wind_state="quiet")
        self.assertIn(sw.NOTE_H3, r["wind_model"]["notes"])


class NonDetectionTest(unittest.TestCase):
    """Group 6 — A4 / A4b."""

    def test_a4b(self):
        r = _run(sp_type="K2V", radius_rsun=0.824, log_fx_limit=4.735)
        self.assertEqual(r["mass_loss_tier"], "xray_nondetection")
        self.assertAlmostEqual(r["rate"] / MDOT_SUN, 0.4612, places=4)
        self.assertEqual(r["band_dex"], [-0.50, 0.31])
        wm = r["wind_model"]
        self.assertEqual((wm["log_fx"], wm["log_fx_kind"], wm["xray"]["limit_survey"]),
                         (4.30, "conditional_below_limit", "supplied"))
        self.assertIn("xray_upper_limit", wm["flags"])
        r = _run(sp_type="K1V", radius_rsun=0.833, log_fx_limit=4.094)
        self.assertAlmostEqual(r["rate"] / MDOT_SUN, 0.3548, places=4)
        self.assertTrue(r["upper"])
        self.assertIsNone(r["band"])
        self.assertEqual(r["wind_model"]["log_fx_kind"], "survey_limit")

    def test_a4_back_derived(self):
        # HD 349726 (M2V) limit 4.866 → the 4.85 row, conditional 4.58, Ṁ 0.1116 (R ≈ 0.336)
        r = _run(sp_type="M2V", radius_rsun=0.336, log_fx_limit=4.866)
        self.assertEqual(r["wind_model"]["log_fx"], 4.58)
        self.assertLess(_dex(r["rate"] / MDOT_SUN, 0.1116), 0.005)
        # ρ CrB (G0V) limit 4.357 → conditional 4.07, Ṁ 0.8587 (R ≈ 1.318)
        r = _run(sp_type="G0V", radius_rsun=1.318, log_fx_limit=4.357)
        self.assertEqual(r["wind_model"]["log_fx"], 4.07)
        self.assertLess(_dex(r["rate"] / MDOT_SUN, 0.8587), 0.005)
        # LEHPM 3396 (M9) 5.325 → 5.30 row, conditional 4.66, late-M widened −0.67/+0.64, no bimodal_class
        r = _run(sp_type="M9V", log_fx_limit=5.325)
        self.assertEqual(r["wind_model"]["log_fx"], 4.66)
        self.assertAlmostEqual(r["band_dex"][0], -0.67, delta=0.006)
        self.assertAlmostEqual(r["band_dex"][1], 0.64, delta=0.006)
        self.assertNotIn("bimodal_class", r["wind_model"]["flags"])

    def test_grid_edges(self):
        # a limit exactly on a grid value (4.70) reads that row, not the one below (float-safe floor)
        r = _run(sp_type="K2V", radius_rsun=0.824, log_fx_limit=4.7)
        self.assertEqual(r["wind_model"]["log_fx"], 4.30)
        r = _run(sp_type="K2V", radius_rsun=0.824, log_fx_limit=0.47 * 10)
        self.assertEqual(r["wind_model"]["log_fx"], 4.30)
        self.assertTrue(_run(sp_type="K2V", log_fx_limit=3.49)["upper"])            # below 3.50
        r = _run(sp_type="K2V", log_fx_limit=9.0)                                   # above 8.00 → 8.00 row
        self.assertEqual(r["wind_model"]["log_fx"], 5.09)

    def test_bimodal_gate(self):
        self.assertNotIn("bimodal_class", _run(sp_type="M5V", log_fx_limit=6.25)["wind_model"]["flags"])
        r = _run(sp_type="M5V", log_fx_limit=6.2633)
        self.assertIn("bimodal_class", r["wind_model"]["flags"])
        self.assertEqual(len(r["wind_model"]["modes"]), 2)


class RadiusTest(unittest.TestCase):
    """Group 7 — the radius chain."""

    def test_chain(self):
        r = sw.select_radius("K", 2, candidates=[{"source": "tic", "value": 2.0},
                                                 {"source": "gaia_flame", "value": 0.80}])
        self.assertEqual((r["radius_source"], r["radius_rsun"]), ("gaia_flame", 0.80))
        self.assertEqual(r["rejected"], [{"source": "tic", "value": 2.0}])
        r = sw.select_radius("K", 2)
        self.assertEqual(r["radius_source"], "subtype_median")
        self.assertEqual(r["radius_rsun"], 0.755)

    def test_vb10(self):
        r = sw.select_radius("M", 8, candidates=[{"source": "tic", "value": 1.746}])
        self.assertEqual((r["radius_source"], r["radius_rsun"]), ("subtype_median_replaced_outlier", 0.1275))

    def test_pair_ambiguous(self):
        # α Cen A — subtype median → no flag
        r = sw.select_radius("G", 2, main_id="* alf Cen A")
        self.assertNotIn("radius_pair_ambiguous", r["flags"])
        r = sw.select_radius("K", 5, candidates=[{"source": "tic", "value": 0.69}], main_id="* 61 Cyg B")
        self.assertIn("radius_pair_ambiguous", r["flags"])
        r = sw.select_radius("K", 0, candidates=[{"source": "tic", "value": 0.882}], main_id="* 70 Oph A")
        self.assertIn("radius_pair_ambiguous", r["flags"])
        self.assertTrue(sw.lettered_main_id("HD 156384C"))
        self.assertTrue(sw.lettered_main_id("GJ 1245 B"))
        self.assertFalse(sw.lettered_main_id("* eps Eri"))
        r = sw.select_radius("K", 2, candidates=[{"source": "tic", "value": 0.75}], main_id="* eps Eri",
                             cone_other=True)
        self.assertIn("radius_pair_ambiguous", r["flags"])

    def test_unchecked_and_off_median(self):
        r = sw.select_radius("M", None, candidates=[{"source": "tic", "value": 0.9}])
        self.assertEqual(r["radius_rsun"], 0.9)
        self.assertIn("radius_unchecked", r["flags"])
        r = sw.select_radius("K", 2, supplied=2.0)
        self.assertEqual(r["radius_source"], "supplied")
        self.assertEqual(len(r["notes"]), 1)

    def test_k2_no_digit(self):
        r = sw.select_radius("K", None, candidates=[{"source": "tic", "value": 2.0}])
        self.assertEqual(r["radius_source"], "class_median")
        self.assertEqual(r["radius_rsun"], 0.7090)
        self.assertIsNone(r["subtype_median_rsun"])
        self.assertEqual(r["rejected"], [{"source": "tic", "value": 2.0}])
        r = sw.select_radius("G", None, supplied=3.0)
        self.assertTrue(r["notes"] and "class median" in r["notes"][0])

    def test_failed_families_recorded(self):
        r = sw.select_radius("K", 2, statuses={"tic": "timeout"})
        self.assertEqual(r["status"], {"tic": "timeout"})


class Cp1FixesTest(unittest.TestCase):
    """CP1 review findings, pinned."""

    def test_out_of_scope_supplied_rate(self):
        r = _run(sp_type="A0V", supplied_rate=1e-13, noncoronal_rate=1e-14)
        self.assertEqual(r["mass_loss_tier"], "supplied")
        self.assertEqual(list(r["wind_model"]["tiers"]), ["noncoronal_row"])

    def test_no_spectral_type_is_none(self):
        self.assertEqual(_run(sp_type=None)["mass_loss_tier"], "none")

    def test_supplied_limit_never_runs_the_ladder(self):
        f = _f_x(5.5, 0.2 ** 2)
        r = _run(sp_type="M V", log_fx_limit=4.5, network=True, d_pc=10.0, rungs=_rungs("2RXS", {"f_x": f}),
                 radius_candidates=[{"source": "tic", "value": 0.2}])
        self.assertEqual(r["mass_loss_tier"], "none")
        self.assertEqual(r["wind_model"]["xray"]["limit_survey"], "supplied")
        self.assertNotEqual(r["wind_model"]["xray"]["rung"], "2RXS")

    def test_missing_sum_flag_demotes(self):
        self.assertEqual(sw.xmm_guard(10.0, None, 20, 5.0), "xmm_guard_demoted")

    def test_hw_rounds_half_up(self):
        self.assertEqual(sw.hw(4.125), sw.hw(4.13))

    def test_item9_verbatim(self):
        self.assertEqual(sw.DISCLOSURES[9],
                         "The typical point sits above the class's predicted-rate median by 0.08–0.27 dex.")

    def test_subtype_unknown_note_once(self):
        f = _f_x(5.5, 0.2 ** 2)
        r = _run(sp_type="M", network=True, d_pc=10.0, rungs=_rungs("2RXS", {"f_x": f}),
                 radius_candidates=[{"source": "tic", "value": 0.2}])
        self.assertEqual(sum(sw.NOTE_SUBTYPE_UNKNOWN in n for n in r["wind_model"]["notes"]), 1)

    def test_one_ws_normaliser(self):
        from core import databases
        self.assertIs(swt.collapse_ws, shared.collapse_ws)
        self.assertEqual(databases._wskey("HD  95735"), shared.collapse_ws("HD  95735"))


class LadderOutcomeTest(unittest.TestCase):
    """Group 8 — the §26.1 partial-failure rule."""

    def _o(self, sts, **kw):
        return sw.ladder_outcome(list(zip(sw.RUNGS, sts)), **kw)

    def test_table(self):
        cases = [
            (("detection", "no_detection", "no_detection"), {}, ("detection", "2RXS", "ok", False)),
            (("timeout", "detection", "no_detection"), {}, ("detection", "eRASS1", "timeout", True)),
            (("detection", "timeout", "error"), {}, ("detection", "2RXS", "ok", False)),
            (("no_detection", "out_of_footprint", "no_detection"), {}, ("nondetection", None, "ok", False)),
            (("no_detection", "unreachable", "no_detection"), {}, ("failed", None, "unreachable", True)),
            (("no_detection", "no_detection", "no_detection"), {"limit_status": "timeout"},
             ("failed", None, "timeout", True)),
            (("no_detection", "no_detection", "detection"), {"xmm_result": "kept"},
             ("detection", "XMM", "ok", False)),
            (("no_detection", "no_detection", "detection"), {"xmm_result": "xmm_guard_demoted"},
             ("nondetection", None, "ok", False)),
            (("no_detection", "no_detection", "detection"), {"xmm_result": "unreachable"},     # H6
             ("failed", None, "unreachable", True)),
        ]
        for sts, kw, (path, used, status, na) in cases:
            o = self._o(sts, **kw)
            self.assertEqual((o["path"], o["used"], o["status"], o["not_authoritative"]),
                             (path, used, status, na), (sts, kw))

    def test_demoted_reads_detection(self):
        o = self._o(("no_detection", "no_detection", "detection"), xmm_result="xmm_floor_demoted")
        self.assertEqual(o["rungs"][2]["status"], "detection")
        o = self._o(("no_detection", "no_detection", "detection"), xmm_result="timeout")
        self.assertEqual(o["rungs"][2]["status"], "timeout")

    def test_astrometry_failed(self):
        o = self._o(("detection", "detection", "detection"), astrom_status="unreachable")
        self.assertEqual(o["path"], "failed")
        self.assertEqual([r["status"] for r in o["rungs"]], ["not_queried"] * 3)

    def test_guard_order(self):
        self.assertEqual(sw.xmm_guard(5.2, 0, 50, 2.49), "xmm_guard_demoted")    # ρ CrB: guard first
        self.assertEqual(sw.xmm_guard(None, 0, 50, 5.0), "xmm_guard_demoted")    # no G
        self.assertEqual(sw.xmm_guard(12.0, 2, 50, 5.0), "xmm_guard_demoted")
        self.assertEqual(sw.xmm_guard(12.0, 0, 1.5, 5.0), "xmm_guard_demoted")
        self.assertEqual(sw.xmm_guard(12.0, 0, 50, 3.126), "xmm_floor_demoted")
        self.assertEqual(sw.xmm_guard(14.0, 0, 96, 4.168), "kept")


class TiersTest(unittest.TestCase):
    """Group 9 — tiers (Q4 + G2 + K1) and the schema."""

    WM_KEYS = {"model", "per_area_log", "log_fx", "log_fx_kind", "regime", "band_construction", "class_bin",
               "state", "flags", "extrapolation_class", "modes", "xray", "radius", "measured", "tiers", "notes"}
    XRAY_KEYS = {"status", "rung", "detection", "source_id", "epoch", "separation_arcsec", "flux_fit_scale",
                 "log_fx", "system_log_fx", "limit_log_fx", "limit_survey", "erass1_footprint",
                 "blended_source", "rungs"}
    ENTRY_KEYS = {"mass_loss_msun_yr", "mass_loss_band_msun_yr", "used", "status", "log_fx", "flags"}

    def _schema(self, r):
        wm = r["wind_model"]
        self.assertEqual(set(wm), self.WM_KEYS)
        self.assertLessEqual(self.XRAY_KEYS, set(wm["xray"]))
        self.assertLessEqual(set(wm["xray"]) - self.XRAY_KEYS, {"xmm_guard"})
        self.assertIn(wm["xray"]["status"], ("ok", "timeout", "unreachable", "error", "not_run"))
        for f in wm["flags"]:
            self.assertIn(f, sw.FLAGS)
        self.assertIn(wm["log_fx_kind"], (None, "detection", "supplied", "conditional_below_limit",
                                          "survey_limit", "class_state"))
        self.assertIn(wm["regime"], (None, "quiet", "mid", "active"))
        self.assertIn(wm["band_construction"], (None, "regime", "class_mixture", "truncated_mixture",
                                                "measured_span"))
        self.assertIn(wm["class_bin"], (None,) + swt.CLASS_BINS)
        self.assertIn(wm["state"], (None, "quiet", "typical", "active"))
        self.assertIn(wm["extrapolation_class"], (None, "f_dwarf", "late_m"))
        self.assertIn(r["mass_loss_tier"], sw.MASS_LOSS_TIERS)
        for rr in wm["xray"]["rungs"]:
            self.assertIn(rr["status"], ("detection", "no_detection", "timeout", "unreachable", "error",
                                         "not_queried", "out_of_footprint"))
        for t, e in wm["tiers"].items():
            self.assertEqual(set(e), self.ENTRY_KEYS, t)
            self.assertIn(e["status"], ("ok", "upper_limit_only", "failed", "not_reachable"))
            self.assertFalse(e["used"])
            for f in e["flags"]:
                self.assertIn(f, sw.FLAGS)

    def test_schema_every_path(self):
        f = _f_x(5.5, 0.755 ** 2)
        for kw in [dict(sp_type="K2V"), dict(sp_type="K2V", log_fx=6.5), dict(sp_type="K2V", log_fx_limit=4.735),
                   dict(sp_type="K1V", log_fx_limit=4.094), dict(sp_type="M4V"), dict(sp_type="M V"),
                   dict(sp_type="K2V", main_id="* eps Eri"), dict(sp_type="K2V", supplied_rate=1e-13),
                   dict(sp_type="K2V", network=True, d_pc=10.0, rungs=_rungs("2RXS", {"f_x": f})),
                   dict(sp_type="K2V", network=True, d_pc=10.0, rungs=_rungs(None, others={"2RXS": "error"})),
                   dict(sp_type="K2V", network=True, d_pc=10.0, astrom_status="timeout", rungs=_rungs(None))]:
            r = _run(**kw)
            if r["mass_loss_tier"] != "noncoronal_row":
                self._schema(r)

    def test_a3b_row3_supplied_star(self):
        r = _run(sp_type="K2V", main_id="* eps Eri", supplied_rate=1e-13)
        self.assertEqual(r["mass_loss_tier"], "supplied")
        e = r["wind_model"]["tiers"]["measured"]
        self.assertAlmostEqual(e["mass_loss_msun_yr"] / MDOT_SUN, 30.0)
        self.assertEqual((e["used"], e["status"]), (False, "ok"))

    def test_upper_limit_only_entry(self):
        # a 107 Psc-type non-detection bound under a supplied rate
        r = _run(sp_type="K1V", radius_rsun=0.833, log_fx_limit=4.094, supplied_rate=1e-13)
        self.assertEqual(r["wind_model"]["tiers"]["xray_nondetection"]["status"], "upper_limit_only")

    def test_g2_entry_level_not_authoritative(self):
        # measured star; a rung above the X-ray detection failed → tiers.xray ok + its own not_authoritative,
        # top level unflagged (the used measured value did not depend on it)
        f = _f_x(5.5, 0.74 ** 2)
        r = _run(sp_type="K2V", main_id="* eps Eri", network=True, d_pc=10.0,
                 rungs=_rungs("eRASS1", {"f_x": f}, others={"2RXS": "timeout"}),
                 radius_candidates=[{"source": "tic", "value": 0.74}])
        e = r["wind_model"]["tiers"]["xray"]
        self.assertEqual(e["status"], "ok")
        self.assertIn("not_authoritative", e["flags"])
        self.assertNotIn("not_authoritative", r["wind_model"]["flags"])
        # no detection + a failed rung → tiers.xray / xray_nondetection failed with no value
        r = _run(sp_type="K2V", main_id="* eps Eri", network=True, d_pc=10.0,
                 rungs=_rungs(None, others={"2RXS": "timeout"}))
        self.assertEqual(r["wind_model"]["tiers"]["xray"]["status"], "failed")
        self.assertIsNone(r["wind_model"]["tiers"]["xray"]["mass_loss_msun_yr"])

    def test_k1_offline_not_reachable(self):
        r = _run(sp_type="K2V", main_id="* eps Eri", network=False, not_run_reason="network_disabled")
        t = r["wind_model"]["tiers"]
        self.assertEqual((t["xray"]["status"], t["xray_nondetection"]["status"]),
                         ("not_reachable", "not_reachable"))
        self.assertEqual(t["class_default"]["status"], "ok")
        self.assertEqual(r["wind_model"]["xray"]["status"], "not_run")

    def test_failed_lookup_is_not_a_nondetection(self):
        r = _run(sp_type="K2V", network=True, d_pc=10.0, rungs=_rungs(None, others={"eRASS1": "unreachable"}),
                 limit={"status": None, "f_limit": 1e-13, "survey": "RASS"})
        self.assertEqual(r["mass_loss_tier"], "class_default")
        self.assertEqual(r["wind_model"]["xray"]["status"], "unreachable")
        self.assertIn("not_authoritative", r["wind_model"]["flags"])
        # a failed limit query (N4)
        r = _run(sp_type="K2V", network=True, d_pc=10.0, rungs=_rungs(None),
                 limit={"status": "timeout", "f_limit": None, "survey": None})
        self.assertEqual(r["mass_loss_tier"], "class_default")
        self.assertIsNone(r["wind_model"]["xray"]["limit_log_fx"])
        self.assertEqual(r["wind_model"]["xray"]["status"], "timeout")

    def test_skeleton(self):
        s = sw.skeleton(["n"])
        self.assertEqual((s["model"], s["xray"]["status"], s["flags"], s["tiers"], s["notes"]),
                         ("cr26", "not_run", [], {}, ["n"]))


class DisclosureTest(unittest.TestCase):
    """Group 10 — R8 token fidelity + the G7 selection."""

    SPEC = (Path(__file__).parent / "data" / "cr26_spec_disclosures.txt").read_text(encoding="utf-8")

    def _items(self):
        body = self.SPEC.split("\n", 1)[1]
        body = body.split("The measured tier carries:")[0]
        parts = re.split(r"\n(?=\d{1,2}\. )", "\n" + body)
        items = {}
        for p in parts:
            m = re.match(r"(\d{1,2})\. (.*)", p.strip(), re.S)
            if m:
                items[int(m.group(1))] = " ".join(m.group(2).split())
        return items

    @staticmethod
    def _norm(s):
        s = re.sub(r"\(?§CR-26\.\d[\d.]*\)?", "", s)
        s = re.sub(r"W6 fork \w+|CP1 ruling \d|\(W6 fork F5\)", "", s)
        return s.replace("**", "").replace("`", "")

    def test_numbers_and_qualifiers(self):
        items = self._items()
        self.assertEqual(sorted(items), list(range(1, 16)))
        emitted = {i: t for i, t in sw.DISCLOSURES.items()}
        emitted[1] = " ".join(sw.DISCLOSURE_WHAT.values())
        emitted[11] = " ".join(sw.FLAG_TEXT.values())
        # WB MSG 311 / §4 ruling 22: the re-vendored class statistics supersede item 9's printed range (the spec
        # text — and this verbatim copy of it — stays the frozen benchmark)
        superseded = {9: ("0.09–0.27", "0.08–0.27")}
        for i, text in items.items():
            spec = self._norm(text)
            if i in superseded:
                spec = spec.replace(*superseded[i])
            got = emitted[i]
            for num in re.findall(r"\d+(?:\.\d+)?", spec):
                if num in ("26",):
                    continue
                self.assertIn(num, got, f"item {i}: number {num} missing")
            for q in ("up to", "≈", "≲", "never", "not", "conservative", "untested", "unpinned"):
                if q in spec:
                    self.assertIn(q, got, f"item {i}: qualifier {q!r} missing")

    def test_measured_set(self):
        spec = " ".join(self.SPEC.split("The measured tier carries:")[1].split())
        got = " ".join(sw.DISCLOSURE_MEASURED.values())
        for tok in ("×2", "combined astrospheres", "charge-exchange", "400", "a factor of a few", "LIC",
                    "CR-24", "lower-main-sequence"):
            self.assertIn(tok, spec)
            self.assertIn(tok, got)

    def test_selection(self):
        n = _run(sp_type="K2V")["wind_model"]["notes"]
        for i in (2, 3, 4, 5, 6, 7, 9, 10):
            self.assertIn(sw.DISCLOSURES[i], n)
        self.assertIn(sw.DISCLOSURE_WHAT["class_default"], n)
        for i in (8, 12, 13, 14, 15):
            self.assertNotIn(sw.DISCLOSURES[i], n)
        n = _run(sp_type="K2V", main_id="* eps Eri")["wind_model"]["notes"]
        self.assertIn(sw.DISCLOSURE_MEASURED["kislyakova"], n)
        self.assertNotIn(sw.DISCLOSURES[2], n)
        self.assertEqual(_run(sp_type="K2V", supplied_rate=1e-13)["wind_model"]["notes"], [])


class A3OfflineTest(unittest.TestCase):
    """Group 11 — each A3 row given its rung, flux, distance, radius and partners."""

    def _x(self, sp, x_sys, r, *, main_id="X", rung="2RXS", partners=(), cand_extra=None, **kw):
        rsq = r ** 2 + sum(p["r"] ** 2 for p in partners)
        cand = {"f_x": _f_x(x_sys, rsq), "rung_label": rung, **(cand_extra or {})}
        if partners:
            cand["blend"] = {"status": None, "partners": [
                {"name": p["name"], "sp_type": p["sp"], "radius_candidates": [{"source": "tic", "value": p["r"]}]}
                for p in partners]}
        kw.setdefault("radius_candidates", [{"source": "tic", "value": r}])
        return _run(sp_type=sp, main_id=main_id, network=True, d_pc=10.0, rungs=_rungs(rung, cand), **kw)

    def _check(self, r, mdot, lo=None, hi=None, flags=()):
        self.assertEqual(r["mass_loss_tier"], "xray")
        self.assertLess(_dex(r["rate"] / MDOT_SUN, mdot), 0.003, r["rate"] / MDOT_SUN)
        if lo is not None:
            self.assertAlmostEqual(r["band_dex"][0], lo, delta=0.006)
            self.assertAlmostEqual(r["band_dex"][1], hi, delta=0.006)
        for f in flags:
            self.assertIn(f, r["wind_model"]["flags"])

    def test_simple_rows(self):
        self._check(self._x("dM6", 5.932, 0.135, main_id="V* CN Leo"), 0.1141, -0.91, 1.24, ["extrapolated"])
        self._check(self._x("dM4", 5.385, 0.210), 0.1310, -0.87, 1.21)
        self._check(self._x("M5.5V", 5.849, 0.172, radius_candidates=[]), 0.1654, -0.90, 1.24, ["extrapolated"])
        self._check(self._x("K0V", 5.196, 0.799), 1.4661, -0.86, 1.21)
        self._check(self._x("dM3", 6.782, 0.422), 3.5504, -1.26, 1.26, ["active_bimodal"])
        r = self._x("F7V", 5.010, 1.548)
        self._check(r, 4.2722, -1.49, 1.21, ["extrapolated"])
        self.assertEqual(r["wind_model"]["extrapolation_class"], "f_dwarf")

    def test_vb10(self):
        r = self._x("M8V", 5.607, 0.1275, radius_candidates=[{"source": "tic", "value": 1.746}])
        self._check(r, 0.0654, -0.89, 1.23, ["extrapolated"])
        self.assertEqual(r["wind_model"]["radius"]["radius_source"], "subtype_median_replaced_outlier")

    def test_denis_kept_xmm(self):
        rsq = 0.1275 ** 2
        cand = {"f_x": _f_x(4.168, rsq), "rung_label": "XMM", "sum_flag": 0, "det_ml": 96}
        r = _run(sp_type="M8.5V", main_id="DENIS J1048-3956", network=True, d_pc=10.0,
                 rungs=_rungs("XMM", cand), g_mag=14.0)
        self._check(r, 0.0092, -0.54, 0.36, ["xmm_rung", "extrapolated"])
        self.assertEqual(r["wind_model"]["xray"]["xmm_guard"]["result"], "kept")
        self.assertIn(sw.DISCLOSURES[12], r["wind_model"]["notes"])

    def test_blend_61cyg_b(self):
        r = self._x("K7V", 4.790, 0.690, main_id="* 61 Cyg B",
                    partners=[{"name": "* 61 Cyg A", "sp": "K5V", "r": 0.665}])
        self._check(r, 0.6290, -0.50, 0.30, ["blended_source", "radius_pair_ambiguous"])
        self.assertNotIn("blend_mixed_class", r["wind_model"]["flags"])
        self.assertEqual(r["wind_model"]["xray"]["blended_source"], ["* 61 Cyg A"])
        self.assertAlmostEqual(r["wind_model"]["xray"]["system_log_fx"], 4.790, places=6)
        self.assertLess(r["wind_model"]["xray"]["system_log_fx"], r["wind_model"]["xray"]["log_fx"])

    def test_alf_cen_a_tiers_xray(self):
        r = self._x("G2V", 4.520, 1.001, main_id="* alf Cen A", radius_candidates=[],
                    partners=[{"name": "* alf Cen B", "sp": "K1V", "r": 0.86}])
        self.assertEqual(r["mass_loss_tier"], "measured")
        e = r["wind_model"]["tiers"]["xray"]
        self.assertLess(_dex(e["mass_loss_msun_yr"] / MDOT_SUN, 0.9156), 0.003)
        self.assertIn("blended_source", e["flags"])
        self.assertIn("blend_mixed_class", e["flags"])

    def test_70oph_a_tiers_xray(self):
        r = self._x("K0V", 5.523, 0.882, main_id="* 70 Oph A",
                    partners=[{"name": "* 70 Oph B", "sp": "K4V", "r": 0.67}])
        e = r["wind_model"]["tiers"]["xray"]
        self.assertLess(_dex(e["mass_loss_msun_yr"] / MDOT_SUN, 2.7883), 0.003)
        self.assertIn("radius_pair_ambiguous", e["flags"])
        self.assertIn("blended_source", e["flags"])

    def test_blend_flags(self):
        # a class-less partner is not "mixed" (H2) + unchecked radius; a missing radius keeps own-area F_X
        r = self._x("K2V", 5.0, 0.755, partners=[{"name": "WD 1", "sp": None, "r": 0.01}])
        self.assertIn("blend_partner_radius_unchecked", r["wind_model"]["flags"])
        self.assertNotIn("blend_mixed_class", r["wind_model"]["flags"])
        cand = {"f_x": _f_x(5.0, 0.755 ** 2), "blend": {"status": None, "partners": [
            {"name": "P", "sp_type": None, "radius_candidates": []}], "field_stars": ["FS 1"]}}
        r = _run(sp_type="K2V", network=True, d_pc=10.0, rungs=_rungs("2RXS", cand),
                 radius_candidates=[{"source": "tic", "value": 0.755}])
        f = r["wind_model"]["flags"]
        self.assertIn("blend_partner_radius_missing", f)
        self.assertIn("field_star_in_beam", f)
        self.assertAlmostEqual(r["wind_model"]["log_fx"], 5.0, places=6)          # own-area F_X kept
        # a failed blend family → not_authoritative
        cand = {"f_x": _f_x(5.0, 0.755 ** 2), "blend": {"status": "failed", "notes": ["blend lookup failed"]}}
        r = _run(sp_type="K2V", network=True, d_pc=10.0, rungs=_rungs("2RXS", cand))
        self.assertIn("not_authoritative", r["wind_model"]["flags"])

    def test_xmm_floor_on_system_fx(self):
        # G3b: the floor is tested on the system F_X of a blend
        rsq = 0.3 ** 2 + 0.3 ** 2
        cand = {"f_x": _f_x(3.45, rsq), "rung_label": "XMM", "sum_flag": 0, "det_ml": 50,
                "blend": {"status": None, "partners": [{"name": "B", "sp_type": "M3V",
                                                        "radius_candidates": [{"source": "tic", "value": 0.3}]}]}}
        r = _run(sp_type="M3V", network=True, d_pc=10.0, rungs=_rungs("XMM", cand), g_mag=12.0,
                 limit={"status": None, "f_limit": _f_x(4.0, 0.09), "survey": "RASS"},
                 radius_candidates=[{"source": "tic", "value": 0.3}])
        self.assertEqual(r["wind_model"]["xray"]["xmm_guard"]["result"], "xmm_floor_demoted")
        self.assertEqual(r["mass_loss_tier"], "xray_nondetection")
        self.assertIn("xmm_floor_demoted", r["wind_model"]["flags"])


if __name__ == "__main__":
    unittest.main()
