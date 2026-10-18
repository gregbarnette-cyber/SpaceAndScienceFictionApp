# tests/test_cr30_placement.py — CR-30.6: the hydrogen-burning limit and one placement rule (core/placement.py).
#
# Pure / offline. The contract's CR-30.6 acceptance hand anchors (items 1–12), the T1–T25 rows of WB's test catalog
# (a byte copy in tests/fixtures/cr30/, its md5 checked), Greg's Q18 node rule (61 Cyg B at 0.03 Gyr), the youth cut,
# the over-read factor and the reading, pre-MS (E governs D), the override and its conflict flag, the lifetime by
# status (CR-30.5's range rules), and the r_ex interval / windless alternative on a boundary row.

import hashlib
import json
import math
import os
import unittest

from core import ms_sequence, placement as P, shared

_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "cr30", "cr30_test_mass_catalog.json")
_FIXTURE_MD5 = "efa69ebb41c681cf3c8edc575bbe8cbb"


def _rows():
    with open(_FIXTURE, "rb") as f:
        raw = f.read()
    return hashlib.md5(raw).hexdigest(), {r["test_id"]: r for r in json.loads(raw)["stars"]}


def _age(lo, hi=1.0, basis="membership"):
    return {"lo_gyr": lo, "hi_gyr": hi, "basis": basis}


def _cat(row, call_age=None, otype=None):
    """A test-catalog row placed as the catalog tier places it (place_resolved — the build's own bridge)."""
    return P.place_resolved(row["mass_solar"], "catalog", catalog_row=row, call_age=call_age, otype=otype)


def _inf(x, route, sp=None, age=None, otype=None, lum=None):
    prov = {"mks": "ms_mks_relation", "luminosity": "ms_luminosity_inversion", "type": "spectral_type_table"}[route]
    return P.place_resolved(x, prov, sp_type=sp, call_age=age, otype=otype, lum_lsun=lum)


def _sup(x, sp=None, lum=None):
    return P.place_resolved(x, "manual", sp_type=sp, lum_lsun=lum)


def _s1(sp):
    s1, _p = __import__("core.regions", fromlist=["_lookup_s1"])._lookup_s1(sp)
    return s1["Msun"]


class ConstantsTest(unittest.TestCase):
    def test_the_one_limit(self):
        from core import binary
        self.assertEqual(P.HBL_MSUN, 0.075)
        self.assertIs(binary._STELLAR_MIN_MSUN, P.HBL_MSUN)          # binary reads the one constant
        self.assertEqual((P.BAND_LO_MSUN, P.MARGIN_MSUN, P.PRE_MS_SPLIT_MSUN), (0.067, 0.080, 0.625504))
        self.assertEqual(P.NO_AGE_CUT, 0.309062)
        self.assertEqual(len(P.CUT_NODES), 11)


class CutTest(unittest.TestCase):                                     # acceptance 6
    def test_nodes_and_interpolation(self):
        self.assertEqual(P.cut_at(0.3), 0.095062)
        self.assertEqual(round(P.cut_at(0.251), 4), 0.0997)
        self.assertEqual(round(P.cut_at(0.271), 4), 0.0978)
        self.assertEqual(round(P.cut_at(0.04), 4), 0.1824)
        self.assertEqual(round(P.cut_at(0.79), 4), 0.0834)            # held 0.625–0.8
        self.assertEqual(P.cut_at(0.8), 0.080)
        self.assertEqual(P.cut_at(None), 0.309062)

    def test_hand_over_at_0_8(self):
        self.assertEqual(_inf(0.082, "luminosity", age=_age(0.79))["status"], "boundary")
        self.assertEqual(_inf(0.082, "luminosity", age=_age(0.8))["status"], "stellar")

    def test_inference_x_0_094_is_boundary_at_both_cuts(self):
        for t in (0.251, 0.271):
            pl = _inf(0.0940, "luminosity", age=_age(t))
            self.assertEqual(pl["status"], "boundary", t)
        self.assertEqual(round(_inf(0.0940, "luminosity", age=_age(0.04, 0.05))["cut_msun"], 4), 0.1824)


class BandAndMarginTest(unittest.TestCase):                           # acceptance 1–2
    def test_supplied_band_edges(self):
        self.assertEqual(_sup(0.0669)["status"], "substellar")
        self.assertEqual(_sup(0.067)["status"], "boundary")
        self.assertEqual(_sup(0.075)["status"], "stellar")
        self.assertEqual(_sup(0.076)["status"], "stellar")            # a supplied mass takes no margin
        self.assertFalse(_sup(0.076)["takes_margin"])

    def test_inference_margin(self):
        self.assertAlmostEqual(_s1("M9V"), 0.079, places=6)
        self.assertEqual(_inf(_s1("M9V"), "type", sp="M9V")["status"], "boundary")
        self.assertAlmostEqual(_s1("M8V"), 0.085, places=6)
        self.assertEqual(_inf(_s1("M8V"), "type", sp="M8V")["status"], "stellar")

    def test_mks_margin(self):
        x105 = ms_sequence.mks_mass(10.5)
        x100 = ms_sequence.mks_mass(10.0)
        self.assertEqual(round(x105, 4), 0.0792)
        self.assertEqual(round(x100, 4), 0.0872)
        self.assertEqual(_inf(x105, "mks")["status"], "boundary")
        self.assertEqual(_inf(x100, "mks")["status"], "stellar")


class OverrideTest(unittest.TestCase):                                 # acceptance 3
    def test_type_triggers(self):
        pl = _sup(0.070, sp="T7")
        self.assertEqual((pl["status"], pl["conflict_flag"]), ("substellar", False))
        pl = _sup(0.080, sp="T7")
        self.assertEqual((pl["status"], pl["conflict_flag"], pl["conflict_trigger"]), ("substellar", True, "type:T7"))
        pl = _sup(0.080, sp="L6")
        self.assertEqual((pl["status"], pl["conflict_flag"]), ("substellar", True))
        pl = _sup(0.080, sp="L5")
        self.assertEqual((pl["status"], pl["conflict_flag"]), ("stellar", False))

    def test_luminosity_trigger(self):
        self.assertEqual(_sup(0.070, lum=4.8978e-05)["status"], "substellar")               # log L −4.31
        self.assertEqual(_sup(0.070, lum=5.1286e-05)["status"], "boundary")                 # log L −4.29
        pl = _sup(0.080, lum=4.8978e-05)
        self.assertEqual((pl["status"], pl["conflict_flag"]), ("substellar", True))
        self.assertTrue(pl["conflict_trigger"].startswith("logL<"))

    def test_no_mass(self):
        self.assertEqual(P.place_resolved(None, None, sp_type="L3")["status"], "undetermined_no_mass")
        self.assertEqual(P.place_resolved(None, None, sp_type="T7")["status"], "substellar")
        self.assertEqual(P.place_resolved(None, None)["lifetime"]["ms_lifetime_status"], "mass_null")


class TestCatalogRowsTest(unittest.TestCase):                           # acceptance 1, 4, 5, 7–10, 12 (T1–T25)
    @classmethod
    def setUpClass(cls):
        cls.md5, cls.rows = _rows()

    def test_fixture_is_wbs_byte_copy(self):
        self.assertEqual(self.md5, _FIXTURE_MD5)
        self.assertEqual(len(self.rows), 25)

    def test_rows_with_a_plain_status(self):
        plain = {"T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10", "T11", "T12", "T13", "T14", "T16",
                 "T17", "T22", "T23", "T24", "T25"}
        for tid in sorted(plain):
            row = self.rows[tid]
            with self.subTest(tid):
                self.assertEqual(_cat(row)["status"], row["test_expected"]["status"])

    def test_cut_bearing_rows(self):
        self.assertEqual(_cat(self.rows["T11"])["cut_msun"], 0.095062)
        self.assertEqual(_cat(self.rows["T21"])["cut_msun"], 0.309062)
        self.assertEqual(_cat(self.rows["T23"])["cut_msun"], 0.095062)
        self.assertEqual(_cat(self.rows["T25"])["cut_msun"], 0.080)

    def test_readings(self):
        t9 = _cat(self.rows["T9"])                                          # boundary from t_lo 0.8: X, no ≤
        self.assertEqual(t9["reading"], "x")
        self.assertIsNotNone(t9["youth_caveat"])
        self.assertEqual(_cat(self.rows["T14"])["reading"], "le_x")
        self.assertEqual(_cat(self.rows["T23"])["reading"], "le_x")         # a candidate grade flags
        self.assertEqual(_cat(self.rows["T25"])["reading"], "x")
        t22 = _cat(self.rows["T22"])                                       # model-age-inconsistent: never the rule
        self.assertEqual((t22["reading"], t22["youth_rule_applies"], t22["youth_flag"]), ("interval", False, True))
        self.assertIsNone(t22["youth_caveat"])

    def test_basis_unknown_row(self):                                     # T17 — no new fields
        pl = _cat(self.rows["T17"])
        self.assertEqual((pl["basis"], pl["basis_unknown"]), ("relation", True))

    def test_model_fit_age_never_flags_a_model_row_or_sizes(self):        # T4 / T16
        t16 = _cat(self.rows["T16"])
        self.assertTrue(t16["youth_flag"])
        self.assertFalse(t16["pre_ms"])                                   # a model fit is never a pre-MS signal
        self.assertEqual(t16["cut_msun"], 0.309062)
        self.assertEqual(t16["no_sizing_age_reason"], "a model-fit-only age never sizes the cut")

    def test_t15_tw_hya_pre_ms_stellar(self):
        pl = _cat(self.rows["T15"], otype="TT*")
        self.assertEqual((pl["status"], pl["pre_ms"], pl["reading"]), ("stellar", True, "interval"))
        self.assertEqual(pl["pre_ms_signal"], "simbad_otype:TT*")
        self.assertEqual(pl["lifetime"]["ms_lifetime_status"], "pre_ms")
        self.assertEqual(pl["lifetime"]["ms_lifetime_note"], "pre-MS — not on the main sequence")

    def test_t18_two_sizing_ages_smallest_t_lo(self):
        a = _cat(self.rows["T18"], call_age=_age(0.5))
        self.assertEqual((a["cut_t_lo_gyr"], a["cut_age_source"]), (0.1, "catalog"))
        self.assertEqual(round(a["cut_msun"], 4), 0.129)
        self.assertEqual((a["status"], a["reading"]), ("boundary", "le_x"))
        b = _cat(self.rows["T18"], call_age=_age(0.05))
        self.assertEqual((b["cut_t_lo_gyr"], b["cut_age_source"]), (0.05, "call"))
        self.assertEqual(round(b["cut_msun"], 4), 0.1631)
        self.assertEqual((b["status"], b["reading"]), ("boundary", "le_x"))

    def test_t19_below_every_route(self):
        pl = _cat(self.rows["T19"], call_age=_age(0.5))
        self.assertEqual(round(pl["cut_msun"], 4), 0.0861)
        self.assertEqual((pl["status"], pl["reading"]), ("stellar", "le_x"))
        self.assertTrue(all(v is None for v in pl["overread_factor_by_route"].values()))

    def test_t20_above_every_route(self):
        pl = _cat(self.rows["T20"], call_age=_age(0.1))
        self.assertEqual((pl["status"], pl["reading"]), ("stellar", "x"))
        self.assertEqual(pl["reading_text"], P.TEXT_ABOVE)

    def test_t21_the_boundary_clause(self):
        pl = _cat(self.rows["T21"])
        self.assertEqual((pl["status"], pl["reading"]), ("boundary", "le_x"))
        self.assertEqual(pl["lifetime"]["ms_lifetime_note"].split(" = ")[0], "if stellar, ≥ t(0.25 Msun)")

    def test_lifetimes_by_status(self):
        t14 = _cat(self.rows["T14"])["lifetime"]
        self.assertIsNone(t14["ms_lifetime_yr"])
        self.assertEqual(round(t14["ms_lifetime_if_stellar_ge_yr"] / 1e9, 1), 1380.1)
        self.assertEqual(round(_cat(self.rows["T21"])["lifetime"]["ms_lifetime_if_stellar_ge_yr"] / 1e9, 1), 725.9)
        t24 = _cat(self.rows["T24"])["lifetime"]                           # M_hi from the row's hi, not X
        self.assertEqual(round(t24["ms_lifetime_if_stellar_ge_yr"] / 1e9, 1), 2902.4)
        self.assertEqual(t24["ms_lifetime_status"], "boundary_null")


class FactorTest(unittest.TestCase):                                   # acceptance 11 (hand anchors)
    def test_values(self):
        f = P.overread_factor("mks", 0.195710, 0.1)
        self.assertEqual(round(f["factor"], 6), 1.322797)
        self.assertEqual(round(0.195710 / f["factor"], 6), 0.147952)
        self.assertEqual(round(P.overread_factor("mks", 0.25, 0.1)["factor"], 6), 1.218129)
        self.assertEqual(round(P.overread_factor("mks", 0.25, 0.09)["factor"], 6), 1.287464)
        self.assertEqual(round(P.overread_factor("luminosity", 0.25, 0.15)["factor"], 6), 1.062472)
        self.assertEqual(round(P.overread_factor("type", 0.5, 0.7)["factor"], 6), 0.999442)

    def test_nulls(self):
        f = P.overread_factor("mks", 0.128312, 0.1)
        self.assertIsNone(f["factor"])
        self.assertTrue(any("M_K outside the 4.5 to 10.5 gate" in r for r in f["null_reasons"]))
        f = P.overread_factor("mks", 0.265, 0.01)
        self.assertIsNone(f["factor"])
        self.assertTrue(any("the track ends before 5 Gyr" in r for r in f["null_reasons"]))
        self.assertTrue(any("M_K outside the 4.5 to 10.5 gate" in r for r in f["null_reasons"]))
        f = P.overread_factor("mks", 0.62, 0.03)
        self.assertIsNone(f["factor"])
        self.assertIn("outside the table at the 0.05 Gyr node", f["null_reasons"])
        self.assertIsNone(P.overread_factor("mks", 0.25, 0.9)["factor"])

    def test_q18_61_cyg_b_one_node(self):                              # Greg's Q18 ruling (MSG 361)
        f = P.overread_factor("mks", 0.622420, 0.03)
        self.assertIsNone(f["factor"])
        self.assertEqual(round(f["reading_factor"], 6), 1.127615)
        self.assertEqual(f["reading_node_gyr"], 0.025)
        pl = _inf(0.622420, "mks", age=_age(0.03))
        self.assertEqual((pl["reading"], pl["reading_node_gyr"]), ("le_x", 0.025))

    def test_q18_below_at_either_node(self):                           # 0.14 at 0.09 → below at 0.08 → "≤ X"
        rd = P.reading_for("mks", 0.14, 0.09, placed_boundary=False)
        self.assertEqual(rd["reading"], "le_x")


class ReadingTest(unittest.TestCase):                                  # acceptance 12 (hand anchors)
    def test_over_read(self):
        self.assertEqual(_inf(0.195710, "mks", age=_age(0.1))["reading"], "le_x")

    def test_under_read(self):
        pl = _inf(0.9405, "luminosity", age=_age(0.1))
        self.assertEqual((pl["status"], pl["reading"], pl["reading_text"]), ("stellar", "x", P.TEXT_UNDER))
        self.assertEqual(round(pl["overread_factor"], 6), 0.934112)
        self.assertEqual(round(pl["x_over_factor"], 6), 1.006839)
        self.assertIsNone(pl["lifetime"]["ms_lifetime_direction"])
        self.assertEqual(round(pl["lifetime"]["ms_lifetime_yr"] / 1e9, 2), 11.47)

    def test_deadband(self):
        self.assertEqual(_inf(0.5, "type", age=_age(0.7))["reading_text"], P.TEXT_FLAT)
        self.assertEqual(_inf(0.147951, "mks", age=_age(0.5))["reading_text"], P.TEXT_FLAT)

    def test_no_sizing_age_reads_at_0_01(self):
        rd = P.reading_for("mks", 0.5, P.NO_AGE_T_LO, placed_boundary=False)
        self.assertEqual((rd["reading"], round(rd["overread_factor"], 6)), ("le_x", 2.51245))
        rd = P.reading_for("luminosity", 0.94, P.NO_AGE_T_LO, placed_boundary=False)
        self.assertEqual((rd["reading"], rd["reading_text"]), ("x", P.TEXT_ABOVE))

    def test_route_unknown_every_route_over_reads(self):
        rd = P.reading_for(None, 0.196, 0.1, placed_boundary=False)
        self.assertEqual(rd["reading"], "le_x")
        by = {k: round(v, 6) for k, v in rd["overread_factor_by_route"].items()}
        self.assertEqual(by, {"mks": 1.322249, "luminosity": 1.279088, "type": 1.131414})

    def test_boundary_clause(self):
        rd = P.reading_for("type", 0.249199, 0.01, placed_boundary=True)
        self.assertEqual(rd["reading"], "le_x")
        self.assertEqual(round(rd["overread_factor"], 6), 0.942903)

    def test_from_0_8(self):
        pl = _inf(0.5, "mks", age=_age(0.9))
        self.assertEqual((pl["reading"], pl["reading_text"]), ("x", P.TEXT_OLD))
        self.assertIsNotNone(pl["youth_caveat"])


class GravityDesignationTest(unittest.TestCase):                       # acceptance 6–8
    def _type(self, sp, age=None):
        return _inf(_s1(sp), "type", sp=sp, age=age)

    def test_fld_g_never_flags(self):
        pl = self._type("M8 FLD-G")
        self.assertEqual((pl["status"], pl["youth_flag"]), ("stellar", False))

    def test_low_gravity_flags_no_sizing(self):
        for sp in ("M8 gamma", "M8 beta", "M8 VL-G", "M8 INT-G", "M8 III VL-G"):
            with self.subTest(sp):
                pl = self._type(sp)
                self.assertTrue(pl["youth_flag"])
                self.assertEqual(pl["cut_msun"], 0.309062)
                self.assertEqual(pl["status"], "boundary")

    def test_m7_vl_g_with_a_sizing_age(self):
        pl = self._type("M7 VL-G", age=_age(0.5))
        self.assertEqual(round(pl["cut_msun"], 4), 0.0861)
        self.assertEqual((pl["status"], pl["reading"]), ("stellar", "le_x"))


class PreMsTest(unittest.TestCase):                                   # acceptance 9
    def test_delta(self):
        pl = _inf(_s1("M8 delta"), "type", sp="M8 delta")
        self.assertEqual((pl["pre_ms"], pl["youth_flag"], pl["status"], pl["reading"]),
                         (True, False, "boundary", "le_x"))
        self.assertEqual(round(pl["lifetime"]["ms_lifetime_if_stellar_ge_yr"] / 1e9, 1), 3304.9)

    def test_the_split(self):
        k8 = _inf(_s1("K8 delta"), "type", sp="K8 delta")
        self.assertEqual((k8["status"], k8["reading"]), ("boundary", "le_x"))
        self.assertEqual(round(k8["lifetime"]["ms_lifetime_if_stellar_ge_yr"] / 1e9, 2), 50.31)
        k7 = _inf(_s1("K7 delta"), "type", sp="K7 delta")
        self.assertEqual((k7["status"], k7["status_text"]), ("stellar", "stellar, pre-main-sequence"))
        self.assertEqual(k7["lifetime"]["ms_lifetime_status"], "pre_ms")
        self.assertEqual(_inf(0.6255, "mks", otype="TT*")["status"], "boundary")
        self.assertEqual(_inf(0.6256, "mks", otype="TT*")["status_text"], "stellar, pre-main-sequence")

    def test_tt_star_rx_j0506(self):
        pl = _inf(0.4631, "mks", sp="M4.5V", otype="TT*")
        self.assertEqual((pl["status"], pl["reading"], pl["r_ex_direction"]), ("boundary", "le_x", "upper_bound"))
        self.assertEqual(round(pl["lifetime"]["ms_lifetime_if_stellar_ge_yr"] / 1e9, 1), 109.8)
        e = _inf(0.4631, "mks", sp="M4.5V", otype="TT*", age=_age(0.05, 0.1))   # E governs D
        self.assertEqual(e["cut_t_lo_gyr"], 0.05)
        self.assertEqual((e["status"], e["reading"]), ("boundary", "le_x"))

    def test_tw_hya_above_the_split(self):
        pl = _inf(0.8387, "luminosity", sp="K6Ve", otype="TT*")
        self.assertEqual((pl["status_text"], pl["reading"], pl["r_ex_direction"]),
                         ("stellar, pre-main-sequence", "x", None))

    def test_g44_42_ages(self):
        x = 0.265023
        mem = _inf(x, "mks", sp="M4V", otype="PM*", age=_age(0.005, 0.02))
        self.assertEqual((mem["pre_ms"], mem["pre_ms_signal"], mem["status"], mem["reading"]),
                         (True, "call_age", "boundary", "le_x"))
        self.assertEqual(round(mem["lifetime"]["ms_lifetime_if_stellar_ge_yr"] / 1e9, 2), 618.79)
        fit = _inf(x, "mks", sp="M4V", otype="PM*", age=_age(0.005, 0.02, "model_fit"))
        self.assertEqual((fit["pre_ms"], fit["youth_flag"], fit["cut_msun"]), (False, True, 0.309062))
        old = _inf(x, "mks", sp="M4V", otype="PM*", age=_age(0.005, 5.0))
        self.assertEqual((old["youth_flag"], old["pre_ms"], old["status"], old["r_ex_direction"]),
                         (False, False, "stellar", None))

    def test_pre_ms_never_on_a_measured_row(self):
        pl = P.place(P.mass_reading(0.3, "dynamical"), otype="TT*")
        self.assertTrue(pl["pre_ms"])
        self.assertEqual((pl["status"], pl["reading"]), ("stellar", "x"))


class LifetimeTest(unittest.TestCase):                                 # CR-30.5 range rules
    def test_stellar_below_the_lowest_track(self):
        pl = _sup(0.09)
        self.assertEqual(pl["lifetime"]["ms_lifetime_direction"], "ge")
        self.assertEqual(round(pl["lifetime"]["ms_lifetime_yr"] / 1e9, 1), 3304.9)

    def test_substellar_null(self):
        self.assertEqual(_sup(0.05)["lifetime"]["ms_lifetime_status"], "substellar_null")

    def test_wolf_359_row(self):
        row = {"main_id": "* CN Leo", "mass_solar": 0.1082, "mass_basis": "model",
               "mass_interval": {"lo": 0.0706, "hi": 0.1082, "kind": "wb_derivation"}}
        pl = P.place_resolved(0.1082, "catalog", catalog_row=row)
        self.assertEqual((pl["status"], pl["x_equals_hi"]), ("boundary", True))
        self.assertEqual(round(pl["lifetime"]["ms_lifetime_if_stellar_ge_yr"] / 1e9, 1), 2934.8)

    def test_lp_816_60_t6_stellar(self):
        row = _rows()[1]["T6"]
        self.assertEqual(round(_cat(row)["lifetime"]["ms_lifetime_yr"] / 1e9, 1), 3304.9)   # ≥ t(0.10)


class ExclusionExtrasTest(unittest.TestCase):                           # the boundary's alternative + interval
    def test_wolf_359_interval(self):
        import query
        row = {"mass_solar": 0.1082, "mass_basis": "model",
               "mass_interval": {"lo": 0.0706, "hi": 0.1082, "kind": "wb_derivation"}}
        pl = P.place_resolved(0.1082, "catalog", catalog_row=row)
        r = 47.5 * 0.1082 ** 0.4
        out = query._exclusion_place_extras({"r_ex_au": r, "alpha": 0.4}, pl)
        self.assertEqual(round(r, 2), 19.52)
        self.assertEqual([round(v, 2) for v in out["r_ex_interval_au"]], [16.45, 19.52])
        self.assertEqual(out["windless_alternative"]["domain"], "windless_free_harbor")

    def test_inference_boundary_has_no_interval(self):
        import query
        pl = _inf(0.079, "type", sp="M9V")
        out = query._exclusion_place_extras({"r_ex_au": 18.0, "alpha": 0.4}, pl)
        self.assertIsNone(out["r_ex_interval_au"])
        self.assertIsNotNone(out["windless_alternative"])

    def test_stellar_has_neither(self):
        import query
        out = query._exclusion_place_extras({"r_ex_au": 30.0, "alpha": 0.4}, _sup(0.3))
        self.assertIsNone(out["windless_alternative"])
        self.assertIsNone(out["r_ex_interval_au"])


if __name__ == "__main__":
    unittest.main()
