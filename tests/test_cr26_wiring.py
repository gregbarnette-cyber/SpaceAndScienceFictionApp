"""CR-26 — the entry-point wiring (plan §3, §5; test group 13). In-process (argparse Namespace, the conftest
forces the network off) + offline ``query.py`` subprocess runs (``--spectral-type`` / ``--component`` /
bare mass / ``--object`` only — never ``--star``, which would need the network)."""

import argparse
import math
import os
import unittest
from unittest import mock

import pytest

from core import exclusion_boundary as eb
from core import stellar_wind as sw
from tests._queryharness import run_query

M = 2e-14


def _wall(mdot_sun):
    return 6.0 * math.sqrt(mdot_sun)


def _b(*args):
    code, payload, err = run_query("exclusion-boundary", *args)
    return code, payload, err


def _ns(**overrides):
    args = argparse.Namespace(
        mass_msun=None, object=None, star=None, spectral_type=None, luminosity_lsun=None,
        mass_loss_msun_yr=None, wind_state=None, wind_speed=None, v_ism=None, c_ms=None,
        b_field=None, n_cloud=None, cloud_temp=None, wind_phase_yr=None, f_shock=None,
        m_shock_min=None, mass_loss_source=None, dial=None, calibration_au=47.5,
        alpha=1.0 / 3.0, beta=0.0, gamma=0.0, scan_alpha=False, star_mass_catalog=None,
        gaia_timeout=None, radius_rsun=None, log_fx=None, log_fx_limit=None, prot_days=None)
    for k, v in overrides.items():
        setattr(args, k, v)
    return args


def _inproc(**kw):
    import query
    cap = {}
    with mock.patch("query._out", lambda r: cap.__setitem__("r", r)):
        query.cmd_exclusion_boundary(_ns(**kw))
    return cap["r"]


class BoundaryAnchorsSubprocessTest(unittest.TestCase):
    """Offline query.py anchors (spec MED-4): the --spectral-type wiring for every CR-26 flag."""

    def test_a3b_row1(self):
        code, d, _ = _b("--spectral-type", "K2V", "--radius-rsun", "0.755", "--log-fx", "6.5", "--prot-days", "0.4")
        self.assertEqual(code, 0)
        self.assertEqual((d["mass_loss_tier"], d["wind_model"]["xray"]["rung"]), ("xray", "supplied"))
        self.assertAlmostEqual(d["mass_loss_msun_yr"] / M, 7.7427, places=4)
        self.assertAlmostEqual(d["mass_loss_band_dex"][0], -1.244, places=3)
        self.assertAlmostEqual(d["mass_loss_band_dex"][1], 2.027, places=3)
        self.assertAlmostEqual(d["wall_au"], 16.70, places=2)
        self.assertEqual([round(x, 2) for x in d["wall_band_au"]], [11.13, 22.26])
        self.assertAlmostEqual(d["wall_band_wind_au"][0], 2.66, places=2)
        self.assertAlmostEqual(d["wall_band_wind_au"][1], 229.6, places=1)
        self.assertEqual(set(d["wind_model"]["flags"]), {"active_bimodal", "fast_rotator"})

    def test_a3b_row2(self):
        code, d, _ = _b("--spectral-type", "M3V", "--radius-rsun", "0.3305", "--log-fx", "7.3")
        self.assertAlmostEqual(d["mass_loss_msun_yr"] / M, 4.4151, places=4)
        self.assertAlmostEqual(d["wall_au"], 12.61, places=2)
        self.assertAlmostEqual(d["wall_band_wind_au"][0], 1.91, places=2)
        self.assertAlmostEqual(d["wall_band_wind_au"][1], 179.0, places=0)
        self.assertEqual(set(d["wind_model"]["flags"]), {"active_bimodal", "above_fit_range"})

    def test_a4b_row2(self):
        code, d, _ = _b("--spectral-type", "K1V", "--radius-rsun", "0.833", "--log-fx-limit", "4.094")
        self.assertEqual(d["mass_loss_tier"], "xray_nondetection")
        self.assertAlmostEqual(d["mass_loss_msun_yr"] / M, 0.3548, places=4)
        self.assertAlmostEqual(d["wall_au"], 3.57, places=2)
        self.assertTrue(d["mass_loss_upper_limit"] and d["wall_is_upper_bound"])
        self.assertIsNone(d["wall_band_wind_au"])
        self.assertEqual(d["wind_model"]["log_fx_kind"], "survey_limit")

    def test_a5_k2v(self):
        code, d, _ = _b("--spectral-type", "K2V")
        self.assertEqual((d["mass_loss_tier"], d["mass_loss_provenance"], d["wind_class"]),
                         ("class_default", "class_default", "solar"))
        self.assertLess(abs(math.log10(d["mass_loss_msun_yr"] / M / 1.1373)), 0.001)     # WB MSG 311 A5
        self.assertAlmostEqual(d["wall_au"], 6.40, places=2)
        self.assertEqual(d["wind_speed_provenance"], "astrosphere_wood_forced")

    def test_a0_bare_mass_and_objects(self):
        _, d, _ = _b("--mass-msun", "1.0", "--alpha", "0.4", "--wind-state", "solar")
        self.assertEqual((d["mass_loss_tier"], d["mass_loss_msun_yr"], d["wall_au"], d["r_ex_au"]),
                         ("legacy_row", 2e-14, 6.0, 47.5))
        _, d, _ = _b("--mass-msun", "0.3", "--wind-state", "quiet")
        self.assertEqual((d["mass_loss_tier"], d["mass_loss_msun_yr"]), ("legacy_row", 1e-16))
        _, d, _ = _b("--mass-msun", "0.3")
        self.assertEqual((d["mass_loss_tier"], d["wall_au"]), ("none", None))
        _, d, _ = _b("--mass-msun", "0.3", "--mass-loss-msun-yr", "1e-13")
        self.assertEqual(d["mass_loss_tier"], "supplied")
        for obj, rate, wall in (("sun", 2e-14, 6.0), ("m-dwarf", 1e-13, 13.42), ("o-star", 1e-6, None)):
            _, d, _ = _b("--object", obj)
            self.assertEqual((d["mass_loss_tier"], d["mass_loss_msun_yr"]), ("object_preset", rate), obj)
            if wall:
                self.assertAlmostEqual(d["wall_au"], wall, places=2)
        _, d, _ = _b("--object", "brown-dwarf")
        self.assertEqual(d["mass_loss_tier"], "object_preset")

    def test_ignored_inputs_noted(self):
        _, d, _ = _b("--mass-msun", "1.0", "--log-fx", "5", "--radius-rsun", "1")
        self.assertEqual(sum("ignored" in n for n in d["wind_model"]["notes"]), 2)
        _, d, _ = _b("--spectral-type", "A0V", "--log-fx", "5")
        self.assertEqual(d["mass_loss_tier"], "noncoronal_row")
        self.assertTrue(any("ignored" in n for n in d["wind_model"]["notes"]))

    def test_g14_exit_codes(self):
        for bad in (("--radius-rsun", "0"), ("--radius-rsun", "2000.1"), ("--radius-rsun", "nan"),
                    ("--log-fx", "-0.1"), ("--log-fx", "12.1"), ("--log-fx-limit", "inf"),
                    ("--prot-days", "0"), ("--prot-days", "1e5.5"), ("--prot-days", "100001")):
            code, _, _ = _b("--spectral-type", "K2V", *bad)
            self.assertEqual(code, 2, bad)
        for ok in (("--radius-rsun", "2000"), ("--log-fx", "0"), ("--log-fx", "12"), ("--prot-days", "1e5")):
            code, _, _ = _b("--spectral-type", "K2V", *ok)
            self.assertEqual(code, 0, ok)
        code, _, _ = _b("--spectral-type", "K2V", "--log-fx", "5", "--log-fx-limit", "4")
        self.assertEqual(code, 2)

    def test_stderr_once(self):
        code, d, err = _b("--spectral-type", "K2V", "--log-fx", "5", "--wind-state", "active")
        self.assertEqual(code, 0)
        self.assertEqual(err.count("did not set the wind rate"), 1)
        self.assertEqual(d["wind_class"], "active")              # the label still carries the selected state
        code, d, err = _b("--spectral-type", "K2V", "--wind-state", "active")
        self.assertEqual(err.count("did not set the wind rate"), 0)


class BoundaryInprocTest(unittest.TestCase):
    def test_q1_gamma_feeds_the_tier_rate(self):
        g0 = _inproc(spectral_type="K2V")
        g1 = _inproc(spectral_type="K2V", gamma=0.5)
        self.assertAlmostEqual(g1["r_ex_au"], g0["r_ex_au"] * (g0["mass_loss_msun_yr"] / M) ** 0.5, places=9)
        # an upper-bound rate → the standoff is an upper bound (note)
        u = _inproc(spectral_type="K1V", radius_rsun=0.833, log_fx_limit=4.094, gamma=0.5)
        self.assertIn(sw.NOTE_Q1_UPPER, u["wind_model"]["notes"])
        # an unused --wind-state does not set the standoff either
        a = _inproc(spectral_type="K2V", log_fx=5.0, wind_state="active", gamma=0.5)
        x = _inproc(spectral_type="K2V", log_fx=5.0, gamma=0.5)
        self.assertEqual(a["r_ex_au"], x["r_ex_au"])

    def test_h3_subtype_unknown(self):
        # an in-scope M star with no subtype digit (reached on --star / --component; `--spectral-type "M V"`
        # has no main-sequence table row and errors there, as before): tier none, a null wall; at γ>0 a
        # --wind-state still feeds the standoff through the legacy map (H3), and with no wind input it errors.
        def run(**kw):
            m = sw.resolve_wind_model(sw.StarWindInputs(sp_type="M V", wind_state=kw.get("wind_state")))
            return eb.compute_two_layer_boundary(mass_msun=0.3, sp_type="M V", wind_model=m, **kw)
        self.assertIn("wind exponent set without", run(gamma=0.5)["error"])
        q = run(gamma=0.5, wind_state="quiet")
        self.assertEqual((q["mass_loss_tier"], q["wall_au"], q["mass_loss_msun_yr"]), ("none", None, None))
        self.assertIn(sw.NOTE_H3, q["wind_model"]["notes"])
        self.assertAlmostEqual(q["r_ex_au"], run()["r_ex_au"] * (1e-16 / M) ** 0.5, places=9)

    def test_r10_speed_forced(self):
        d = _inproc(spectral_type="K2V", wind_speed=700.0, mass_loss_source="recipe")
        self.assertEqual((d["wind_speed_kms"], d["wind_speed_provenance"]), (400.0, "astrosphere_wood_forced"))
        self.assertEqual(d["mass_loss_source"], "astrosphere_wood")
        n = d["wind_model"]["notes"]
        self.assertIn(sw.NOTE_IGNORED_SPEED.format(v=700.0), n)
        self.assertIn(sw.NOTE_IGNORED_SOURCE.format(src="recipe"), n)

    def test_g11_supplied_f_dwarf_keeps_its_row(self):
        d = _inproc(spectral_type="F5V", mass_loss_msun_yr=1e-13)
        self.assertEqual((d["mass_loss_tier"], d["wind_speed_kms"]), ("supplied", 500.0))
        self.assertEqual(d["wind_class"], "solar")                # the CR-26 label only

    def test_h7(self):
        d = _inproc(spectral_type="kA5hF0mF2")
        self.assertEqual((d["mass_loss_tier"], d["wind_class"]), ("noncoronal_row", "a_dwarf"))
        self.assertIn(sw.NOTE_H7.format(letter="A"), d["wind_model"]["notes"])
        s = _inproc(spectral_type="A0mA1")
        self.assertEqual(s["wind_class"], "a_dwarf")

    def test_m6_checks_keep_todays_exit_codes(self):
        self.assertNotIn("error", _inproc(spectral_type="DA", alpha=-1.0))
        self.assertNotIn("error", _inproc(spectral_type="DA", beta=1.0, luminosity_lsun=0.0))
        self.assertNotIn("error", _inproc(spectral_type="K2V", mass_loss_msun_yr=1e-13, wind_state="loud"))
        e = _inproc(spectral_type="K2V", wind_state="loud")
        self.assertIn("Unknown --wind-state 'loud'", e["error"])
        e = _inproc(spectral_type="K2V", mass_loss_msun_yr=-1.0)
        self.assertEqual(e["error"], "--mass-loss-msun-yr must be > 0.")

    def test_star_mass_loss_negative_never_reaches_cr26(self):
        from tests.test_cr25 import _star_mocks
        ps = _star_mocks()
        for p in ps:
            p.start()
        try:
            with mock.patch("core.xray_catalog.resolve_star_wind_inputs",
                            side_effect=AssertionError("CR-26 reached")):
                e = _inproc(star="EV Lac", mass_loss_msun_yr=-1.0)
        finally:
            for p in reversed(ps):
                p.stop()
        self.assertEqual(e["error"], "--mass-loss-msun-yr must be > 0.")

    def test_direct_call_tier_derivation(self):
        self.assertEqual(eb.compute_two_layer_boundary(mass_msun=1.0)["mass_loss_tier"], "none")
        self.assertEqual(eb.compute_two_layer_boundary(mass_msun=1.0, wind_state="solar")["mass_loss_tier"],
                         "legacy_row")
        self.assertEqual(eb.compute_two_layer_boundary(mass_msun=1.0, sp_type="G2V")["mass_loss_tier"],
                         "legacy_row")                                # a coarse F/G/K/M bin (M-7)
        self.assertEqual(eb.compute_two_layer_boundary(mass_msun=2.0, sp_type="A0V")["mass_loss_tier"],
                         "noncoronal_row")
        self.assertEqual(eb.compute_two_layer_boundary(mass_msun=1.0, mass_loss_msun_yr=1e-13)["mass_loss_tier"],
                         "supplied")
        d = eb.compute_two_layer_boundary(mass_msun=1.0)
        self.assertEqual(d["wind_model"], sw.skeleton())

    def test_every_path_emits_every_field(self):
        keys = {"mass_loss_tier", "mass_loss_band_msun_yr", "mass_loss_band_dex", "mass_loss_upper_limit",
                "wall_band_wind_au", "wall_band_wind_exceeds_standoff", "wall_is_upper_bound", "wind_model"}
        for kw in (dict(mass_msun=1.0), dict(object="sun"), dict(object="brown-dwarf"), dict(spectral_type="K2V"),
                   dict(spectral_type="DA"), dict(spectral_type="K0III"), dict(spectral_type="sdB1"),
                   dict(spectral_type="A0V")):
            d = _inproc(**kw)
            self.assertLessEqual(keys, set(d), kw)


def _s(*args):
    return run_query("exclusion-system", *args)


def _comps(d):
    return {c["id"]: c for z in d["zones"] for c in z["components"]}


GJ65 = ["--component", "id=A,mass=0.1225,class=M5.5V,radius_rsun=0.165,log_fx=6.04,otype=Er*,pair=AB,sma=5.51,ecc=0.6185",
        "--component", "id=B,mass=0.1195,class=M6V,radius_rsun=0.159,log_fx=6.04,otype=Er*,pair=AB,sma=5.51,ecc=0.6185"]


class SystemAnchorsSubprocessTest(unittest.TestCase):
    def test_a6_gj65_zone(self):
        code, d, _ = _s(*GJ65)
        self.assertEqual(code, 0)
        c = _comps(d)
        self.assertAlmostEqual(c["A"]["mass_loss_msun_yr"] / M, 0.1975, places=4)
        self.assertAlmostEqual(c["B"]["mass_loss_msun_yr"] / M, 0.1834, places=4)
        self.assertAlmostEqual(c["A"]["wall_au"], 2.67, places=2)
        self.assertEqual([round(x, 2) for x in c["A"]["wall_band_wind_au"]], [0.43, 14.87])
        self.assertEqual([round(x, 2) for x in c["B"]["wall_band_wind_au"]], [0.41, 14.33])
        for x in c.values():
            self.assertEqual(set(x["wind_model"]["flags"]), {"active_bimodal", "extrapolated"})
            self.assertAlmostEqual(x["mass_loss_band_dex"][1], 1.243, places=3)
        z = d["wall_zones"][0]
        self.assertAlmostEqual(z["combined_wind_wall_band_wind_au"][0], 0.590, places=3)
        self.assertAlmostEqual(z["combined_wind_wall_band_wind_au"][1], 20.65, places=2)
        self.assertEqual((z["combined_wind_band_exceeds_standoff"], z["combined_wind_phase"],
                          z["combined_wind_wall_is_upper_bound"]), (True, "periastron", False))
        self.assertAlmostEqual(max(x["r_ex_au"] for x in c.values()), 20.51, places=2)
        for x in c.values():
            self.assertIn(sw.DISCLOSURES[15], x["wind_model"]["notes"])

    def test_a4b_row1_component(self):
        _, d, _ = _s("--component", "id=X,mass=0.82,class=K2V,radius_rsun=0.824,log_fx_limit=4.735")
        x = _comps(d)["X"]
        self.assertAlmostEqual(x["mass_loss_msun_yr"] / M, 0.4612, places=4)
        self.assertAlmostEqual(x["wall_au"], 4.07, places=2)
        self.assertEqual([round(v, 2) for v in x["wall_band_wind_au"]], [1.53, 7.76])
        self.assertEqual((x["wind_model"]["xray"]["limit_survey"], x["wind_model"]["log_fx_kind"]),
                         ("supplied", "conditional_below_limit"))

    def test_a5_otype_component(self):
        _, d, _ = _s("--component", "id=M,mass=0.2,class=M4V,otype=Er*")
        x = _comps(d)["M"]
        self.assertEqual((x["wind_class"], x["wind_class_provenance"], x["mass_loss_tier"]),
                         ("active", "otype_auto", "class_default"))
        self.assertIn(sw.DISCLOSURES[14], x["wind_model"]["notes"])

    def test_a6_eps_eri_main_id(self):
        _, d, _ = _s("--component", "id=E,mass=0.82,class=K2V,main_id=* eps Eri")
        e = _comps(d)["E"]
        self.assertEqual(e["mass_loss_tier"], "measured")
        self.assertAlmostEqual(e["wall_au"], 32.86, places=2)
        self.assertEqual([round(v, 2) for v in e["wall_band_wind_au"]], [15.8, 43.82])
        self.assertAlmostEqual(e["r_ex_au"], 47.5 * 0.82 ** 0.4, places=9)       # 43.875 > 43.818
        self.assertFalse(e["wall_band_wind_exceeds_standoff"])
        t = e["wind_model"]["tiers"]
        self.assertEqual((t["xray"]["status"], t["xray_nondetection"]["status"]), ("not_reachable", "not_reachable"))

    def test_a6_61cyg_and_edges(self):
        _, d, _ = _s("--component", "id=A,mass=0.63,main_id=* 61 Cyg A,pair=AB,sma=84,ecc=0.4",
                     "--component", "id=B,mass=0.6,class=K7V,main_id=* 61 Cyg B,log_fx=4.79,radius_rsun=0.69,"
                     "pair=AB,sma=84,ecc=0.4")
        c = _comps(d)
        self.assertEqual((c["A"]["mass_loss_tier"], c["B"]["mass_loss_tier"]), ("measured", "xray"))
        self.assertIn("method_mixed", c["A"]["wind_model"]["flags"])
        self.assertEqual(d["measured_system_edges"],
                         [{"members": ["A", "B"], "system_upper_edge_mdot_sun": 9.6, "source": "kislyakova2024"}])

    def test_system_wind_state_and_stderr(self):
        code, d, err = _s("--wind-state", "quiet", "--component", "id=C,mass=0.8,class=K2V",
                          "--component", "id=E,mass=0.82,class=K2V,main_id=* eps Eri")
        c = _comps(d)
        self.assertEqual((c["C"]["mass_loss_tier"], c["C"]["wind_model"]["state"]), ("class_default", "quiet"))
        self.assertEqual(c["E"]["mass_loss_tier"], "measured")
        self.assertTrue(any("did not set the wind rate" in n for n in c["E"]["wind_model"]["notes"]))
        self.assertEqual(err.count("did not set the wind rate"), 1)
        self.assertIn(" E ", err)
        self.assertNotIn("_cr26_system_ws_unused", d)

    def test_prot_days_reach(self):
        _, d, _ = _s("--prot-days", "0.3", "--component", "id=A,mass=0.8,class=K2V,log_fx=5",
                     "--component", "id=B,mass=0.8,class=K2V,log_fx=5,prot_days=3")
        c = _comps(d)
        self.assertIn("fast_rotator", c["A"]["wind_model"]["flags"])
        self.assertNotIn("fast_rotator", c["B"]["wind_model"]["flags"])      # the component key wins

    def test_component_exit_codes(self):
        for bad in ("radius_rsun=0", "log_fx=13", "prot_days=-1", "log_fx=5,log_fx_limit=4", "log_fx_limit=nan"):
            code, _, _ = _s("--component", f"id=A,mass=0.8,class=K2V,{bad}")
            self.assertEqual(code, 2, bad)
        code, _, _ = _s("--component", "id=A,mass=0.8,class=K2V,bogus=1")
        self.assertEqual(code, 1)                                           # unknown keys keep exit 1
        code, _, _ = _s("--component", "id=A,mass=abc,class=K2V")
        self.assertEqual(code, 1)
        code, _, _ = _s("--prot-days", "0", "--component", "id=A,mass=0.8,class=K2V")
        self.assertEqual(code, 2)


class SystemInprocTest(unittest.TestCase):
    def _c(self, specs, **kw):
        from core import exclusion_system as es
        r = es.compute_exclusion_system(component_specs=specs, **kw)
        return r, ({c["id"]: c for z in r["zones"] for c in z["components"]} if "zones" in r else {})

    def test_h4(self):
        r, c = self._c(["id=E,mass=0.82,class=M4V,main_id=* eps Eri"])
        self.assertTrue(any("disagrees with the measured row" in n for n in c["E"]["wind_model"]["notes"]))
        r, c = self._c(["id=P,main_id=* del Pav"])                         # lone evolved row, no mass
        self.assertEqual((c["P"]["domain"], c["P"]["mass_loss_tier"], c["P"]["mass_provenance"]),
                         ("evolved", "measured", "unresolved_out_of_domain"))
        self.assertAlmostEqual(c["P"]["wall_au"], 18.97, places=2)

    def test_g8_legacy_row(self):
        r, c = self._c(["id=X,mass=0.3,wind_state=quiet"])
        self.assertEqual((c["X"]["mass_loss_tier"], c["X"]["mass_loss_msun_yr"]), ("legacy_row", 1e-16))

    def test_r11_h8_point_mass(self):
        specs = ["id=A,mass=0.8,class=K2V,pair=AB,sma=2,ecc=0", "id=B,mass=0.3,wind_state=active,pair=AB,sma=2,ecc=0"]
        r0, c0 = self._c(specs)
        r1, c1 = self._c(specs, gamma=0.5)
        rate_a = c1["A"]["mass_loss_msun_yr"]
        zone = [z for z in r1["zones"] if "A" in z["members"]][0]
        z0 = [z for z in r0["zones"] if "A" in z["members"]][0]
        self.assertAlmostEqual(zone["point_mass_r_ex_au"],
                               z0["point_mass_r_ex_au"] * ((rate_a + 1e-13) / M) ** 0.5, places=9)
        up = ["id=A,mass=0.8,class=K1V,radius_rsun=0.833,log_fx_limit=4.094,pair=AB,sma=2,ecc=0",
              "id=B,mass=0.8,class=K2V,pair=AB,sma=2,ecc=0"]
        r, c = self._c(up, gamma=0.5)
        self.assertTrue(any("point_mass_r_ex_au" in n for n in c["A"]["wind_model"]["notes"]))

    def test_combined_null_rules(self):
        up = ["id=A,mass=0.8,class=K2V,log_fx_limit=3.9,pair=AB,sma=3,ecc=0", "id=B,mass=0.8,class=K2V,pair=AB,sma=3,ecc=0"]
        r, c = self._c(up)
        z = r["wall_zones"][0]
        self.assertEqual((z["combined_wind_wall_band_wind_au"], z["combined_wind_band_exceeds_standoff"],
                          z["combined_wind_wall_is_upper_bound"]), (None, None, True))
        self.assertNotIn(sw.DISCLOSURES[15], c["B"]["wind_model"]["notes"])
        # a supplied (no-band) member contributes its point to both sums
        sup = ["id=A,mass=0.8,class=K2V,mass_loss_msun_yr=2e-14,pair=AB,sma=3,ecc=0",
               "id=B,mass=0.8,class=K2V,pair=AB,sma=3,ecc=0"]
        r, c = self._c(sup)
        z = r["wall_zones"][0]
        b = c["B"]
        lo = 2e-14 + b["mass_loss_msun_yr"] * 10 ** b["mass_loss_band_dex"][0]
        hi = 2e-14 + b["mass_loss_msun_yr"] * 10 ** b["mass_loss_band_dex"][1]
        self.assertAlmostEqual(z["combined_wind_wall_band_wind_au"][0], 4 * (lo / M) ** 0.5, places=9)
        self.assertAlmostEqual(z["combined_wind_wall_band_wind_au"][1], 8 * (hi / M) ** 0.5, places=9)
        self.assertIn(sw.DISCLOSURES[15], c["A"]["wind_model"]["notes"])

    def test_own_bad_wind_state_rejected_at_gamma(self):
        # the γ>0 variant of test_cr25.py:1237 — a ladder tier must not hide a bad own wind_state
        for g in (0.0, 0.5):
            r, _ = self._c(["id=A,class=K2V,mass=0.8,wind_state=loud"], gamma=g)
            self.assertIn("Unknown --wind-state 'loud'", r["error"], g)
        r, _ = self._c(["id=A,class=K2V,mass=0.8,wind_state=loud,mass_loss_msun_yr=1e-13"], gamma=0.5)
        self.assertNotIn("error", r)                                    # a supplied rate: the frozen condition

    def test_star_cheap_checks_before_the_orchestrator(self):
        from core import exclusion_system as es
        comps = [{"id": "X", "sp_type": "K2V", "mass_solar": 0.8, "_cr26_identity": {"main_id": "X"}}]
        with mock.patch.object(es, "_resolve_system_from_star", return_value=(comps, [], {})), \
                mock.patch("core.xray_catalog.resolve_star_wind_inputs", side_effect=AssertionError("network")):
            r = es.compute_exclusion_system(star="X", dial=-1.0)
        self.assertEqual(r["error"], "component 'X': --dial must be > 0.")
        wd = [{"id": "W", "sp_type": "DA2", "class": "wd", "mass_solar": 0.6, "_cr26_identity": {"main_id": "W"}}]
        with mock.patch.object(es, "_resolve_system_from_star", return_value=(wd, [], {})):
            self.assertNotIn("error", es.compute_exclusion_system(star="W", dial=-1.0))   # all-windless: exit 0

    def test_component_path_never_networks(self):
        # the socket guard (conftest) is active in this file; the component path must never call a fetcher
        from core import exclusion_system as es
        r = es.compute_exclusion_system(component_specs=GJ65[1::2])
        self.assertNotIn("error", r)


class Cp4FixesTest(unittest.TestCase):
    """CP4 review findings, pinned."""

    def test_h1_failed_b_supplies_the_class(self):
        from core import xray_catalog as xc
        inp = xc.resolve_star_wind_inputs({"sp_type": None, "main_id": None, "candidate": "* alf Cen B",
                                           "sl_failed": True, "domain": "main_sequence"}, {}, allow_network=False)
        r = sw.resolve_wind_model(inp)
        self.assertEqual((inp.sp_type, r["mass_loss_tier"]), ("K1V", "measured"))

    def test_zone_fields_always_present(self):
        from core import exclusion_system as es
        r = es.compute_exclusion_system(component_specs=[
            "id=A,mass=0.8,class=K2V,pair=AB,sma=3,ecc=0", "id=B,mass=0.6,class=wd,pair=AB,sma=3,ecc=0"])
        for z in r["wall_zones"]:
            self.assertLessEqual({"combined_wind_wall_band_wind_au", "combined_wind_band_exceeds_standoff",
                                  "combined_wind_wall_is_upper_bound"}, set(z))

    def test_system_prot_days_noted_on_out_of_scope(self):
        from core import exclusion_system as es
        r = es.compute_exclusion_system(component_specs=["id=A,mass=2.0,class=A0V"], prot_days=2.0)
        c = r["zones"][0]["components"][0]
        self.assertTrue(any("--prot-days" in n and "ignored" in n for n in c["wind_model"]["notes"]))

    def test_h7_compose_parity(self):
        from core import exclusion_system as es
        r = es.compute_exclusion_system(component_specs=["id=A,mass=2.0,class=kA5hF0mF2,wind_state=active"])
        c = r["zones"][0]["components"][0]
        self.assertEqual((c["wind_class"], c["wind_class_provenance"]), ("active", "manual"))
        r = es.compute_exclusion_system(component_specs=["id=A,mass=2.0,class=kA5hF0mF2"])
        self.assertEqual(r["zones"][0]["components"][0]["wind_class"], "a_dwarf")


class Cp5FixesTest(unittest.TestCase):
    """CP5 review findings, pinned."""

    def test_windless_with_a_rate_parity_and_note(self):
        from core import exclusion_system as es
        from core import exclusion_boundary as eb2
        d = _inproc(spectral_type="DA2", mass_loss_msun_yr=1e-14)
        r = es.compute_exclusion_system(component_specs=["id=W,class=DA2,mass=0.6,mass_loss_msun_yr=1e-14"])
        c = r["zones"][0]["components"][0]
        self.assertEqual((d["mass_loss_tier"], c["mass_loss_tier"]), ("noncoronal_row", "noncoronal_row"))
        self.assertIn(eb2.NOTE_RATE_UNUSED, d["wind_model"]["notes"])
        self.assertIn(eb2.NOTE_RATE_UNUSED, c["wind_model"]["notes"])
        self.assertEqual(_inproc(object="rogue-planet", mass_loss_msun_yr=1e-14)["mass_loss_tier"], "object_preset")

    def test_footprint_null_when_not_evaluated(self):
        r = sw.resolve_wind_model(sw.StarWindInputs(
            sp_type="K2V", network=True, d_pc=10.0, astrom_status="timeout",
            rungs=[{"rung": x, "status": "not_queried", "cand": None} for x in sw.RUNGS]))
        self.assertIsNone(r["wind_model"]["xray"]["erass1_footprint"])

    def test_no_identity_is_not_run(self):
        from core import xray_catalog as xc
        with mock.patch.object(xc, "star_astrometry", side_effect=AssertionError("network")):
            inp = xc.resolve_star_wind_inputs({"sp_type": "K2V", "main_id": None, "domain": "main_sequence",
                                               "d_pc": 10.0}, {}, allow_network=True)
        self.assertEqual(inp.not_run_reason, "no_identity")

    def test_r11_note_not_on_a_lone_zone(self):
        from core import exclusion_system as es
        from core import exclusion_system as esm
        r = es.compute_exclusion_system(component_specs=["id=P,mass=0.12,class=M5.5V,main_id=NAME Proxima Centauri"],
                                        gamma=1.0)
        notes = r["zones"][0]["components"][0]["wind_model"]["notes"]
        self.assertIn(sw.NOTE_Q1_UPPER, notes)
        self.assertNotIn(esm._NOTE_R11, notes)

    def test_gaia_banner_goes_to_stderr_inside_the_attempt(self):
        import contextlib
        import io
        import sys
        import types
        from core import catalog
        mod = types.ModuleType("astroquery.gaia")

        class _G:
            def __init__(self, **kw):
                print("In preparation for Gaia DR4 (banner)")

            def launch_job(self, q):
                from astropy.table import Table
                return types.SimpleNamespace(get_results=lambda: Table({"x": [1]}))
        mod.GaiaClass = _G
        out = io.StringIO()
        with mock.patch.dict(sys.modules, {"astroquery.gaia": mod}), \
                mock.patch.dict(os.environ, {"SPACE_APP_CATALOG_CACHE": "0"}), contextlib.redirect_stdout(out):
            catalog.reset_gaia_sync_circuit()
            res = catalog.gaia_tap(adql="SELECT 1")
        self.assertNotIn("error", res)
        self.assertEqual(out.getvalue(), "")


class Cp3FixesTest(unittest.TestCase):
    """CP3 review findings, pinned."""

    def test_h7_keeps_an_explicit_wind_state(self):
        d = _inproc(spectral_type="kA5hF0mF2", wind_state="active")
        self.assertEqual((d["wind_class"], d["wind_class_provenance"]), ("active", "manual"))
        d = _inproc(spectral_type="kA5hF0mF2", mass_loss_msun_yr=1e-13)
        self.assertEqual((d["mass_loss_tier"], d["wind_class"]), ("supplied", "a_dwarf"))
        self.assertEqual(d["wind_model"]["tiers"]["noncoronal_row"]["mass_loss_msun_yr"], 1e-14)   # the a_dwarf row

    def test_ignored_inputs_on_supplied_out_of_scope(self):
        d = _inproc(spectral_type="A0V", mass_loss_msun_yr=1e-13, log_fx=5.0)
        self.assertEqual(d["mass_loss_tier"], "supplied")
        self.assertTrue(any("ignored" in n for n in d["wind_model"]["notes"]))

    def test_typeless_keeps_todays_path(self):
        m = sw.resolve_wind_model(sw.StarWindInputs(sp_type=None, wind_state="active"))
        d = eb.compute_two_layer_boundary(mass_msun=0.5, wind_state="active", wind_model=m)
        self.assertEqual((d["mass_loss_tier"], d["mass_loss_msun_yr"]), ("legacy_row", 1e-13))

    def test_object_with_user_rate_is_supplied(self):
        self.assertEqual(_inproc(object="sun", mass_loss_msun_yr=1e-12)["mass_loss_tier"], "supplied")
        self.assertEqual(_inproc(object="sun")["mass_loss_tier"], "object_preset")

    def test_windless_keeps_notes(self):
        d = _inproc(spectral_type="DA", log_fx=5.0)
        self.assertTrue(any("ignored" in n for n in d["wind_model"]["notes"]))

    def test_one_ladder_tuple(self):
        from core import exclusion_wall as ew
        self.assertIs(ew.CR26_LADDER_TIERS, sw.LADDER_TIERS)


class ReGateWiringTest(unittest.TestCase):
    """WB re-gate MSG 311 — RG2 / RG5, pinned."""

    def test_rg2_h4_note_on_letter_or_domain(self):
        from core import exclusion_system as es
        for cl, noted in (("G8V", True), ("G5V", True), ("K2V", True), ("G8IV", False)):
            spec = es._h4_inject({"id": "D", "main_id": "* del Pav", "class": cl})
            self.assertEqual(bool(spec.get("cr26_notes")), noted, cl)

    def test_rg2_h4_domain_uses_the_components_otype(self):
        # an AGB otype classes a G8V component evolved — the row's own domain, so no disagreement note
        from core import exclusion_system as es
        self.assertEqual(es._component_domain(None, "G8V", "AB*")[0], "evolved")
        spec = es._h4_inject({"id": "D", "main_id": "* del Pav", "class": "G8V", "otype": "AB*"})
        self.assertFalse(spec.get("cr26_notes"))

    def test_rg5_not_authoritative_reaches_the_output(self):
        from core import exclusion_system as es
        comps = [{"id": "B", "name": None, "sp_type": None, "mass_solar": 0.8,
                  "_cr26_identity": {"sp_type": None, "main_id": None, "candidate": "* eta CrB B",
                                     "sl_failed": True, "domain": "main_sequence"}}]
        with mock.patch.object(es, "_resolve_system_from_star", return_value=(comps, [], {})):
            r = es.compute_exclusion_system(star="eta CrB")
        c = r["zones"][0]["components"][0]
        self.assertEqual(c["mass_loss_tier"], "none")
        self.assertIn("not_authoritative", c["wind_model"]["flags"])

    def test_rg5_failed_only_when_the_lookup_blocked_the_ladder(self):
        # a failed identity lookup that did NOT stop the ladder (no distance / network off) is not the cause
        for why in ("no_distance", "network_disabled"):
            inp = sw.StarWindInputs(sp_type="K1V", measured_ids=["* alf Cen B"], identity_failed=True,
                                    not_run_reason=why)
            self.assertEqual(sw.resolve_wind_model(inp)["wind_model"]["tiers"]["xray"]["status"], "not_reachable")
        inp = sw.StarWindInputs(sp_type="K1V", measured_ids=["* alf Cen B"], identity_failed=True,
                                not_run_reason="no_identity")
        self.assertEqual(sw.resolve_wind_model(inp)["wind_model"]["tiers"]["xray"]["status"], "failed")

    def test_rg9_h1_miss_flag_on_noncoronal_and_evolved(self):
        # Sirius-shape: an MS non-coronal star whose H1 string match found no row
        inp = sw.StarWindInputs(sp_type="A1V", measured_miss_not_authoritative=True, identity_failed=True)
        r = sw.resolve_wind_model(inp)
        self.assertEqual(r["mass_loss_tier"], "noncoronal_row")
        self.assertIn("not_authoritative", r["wind_model"]["flags"])
        self.assertNotIn("not_authoritative",
                         sw.resolve_wind_model(sw.StarWindInputs(sp_type="A1V"))["wind_model"]["flags"])
        # exclusion-boundary's evolved --star branch discards a non-measured model; the flag rides on cr26_flags
        d = eb.compute_two_layer_boundary(mass_msun=1.1, luminosity_lsun=170.0, sp_type="K1.5III",
                                          cr26_notes=["h1 note"], cr26_flags=["not_authoritative"])
        self.assertEqual((d["domain"], d["wind_model"]["flags"]), ("evolved", ["not_authoritative"]))
        self.assertIn("h1 note", d["wind_model"]["notes"])

    def test_rg9_g10_bypass_keeps_the_flag(self):
        inp = sw.StarWindInputs(sp_type="K2V", wind_class="a_dwarf", measured_miss_not_authoritative=True)
        r = sw.resolve_wind_model(inp)
        self.assertEqual(r["mass_loss_tier"], "noncoronal_row")
        self.assertIn("not_authoritative", r["wind_model"]["flags"])

    def test_rg9_exclusion_system_evolved_h1_miss(self):
        from core import exclusion_system as es
        comps = [{"id": "K", "name": None, "sp_type": "K1.5III", "mass_solar": 1.1,
                  "_cr26_identity": {"sp_type": "K1.5III", "main_id": None, "candidate": "* alf Boo",
                                     "sl_failed": True, "domain": "evolved"}}]
        with mock.patch.object(es, "_resolve_system_from_star", return_value=(comps, [], {})):
            r = es.compute_exclusion_system(star="Arcturus")
        c = r["zones"][0]["components"][0]
        self.assertEqual(c["domain"], "evolved")
        self.assertIn("not_authoritative", c["wind_model"]["flags"])
        self.assertTrue(any("identity lookup" in n for n in c["wind_model"]["notes"]))

    def test_rg5_failed_b_lookup(self):
        from core import xray_catalog as xc
        # α Cen B: the string hit sets measured; the tiers the failed lookup blocked read `failed`
        inp = xc.resolve_star_wind_inputs({"sp_type": None, "main_id": None, "candidate": "* alf Cen B",
                                           "sl_failed": True, "domain": "main_sequence"}, {}, allow_network=True)
        r = sw.resolve_wind_model(inp)
        t = r["wind_model"]["tiers"]
        self.assertEqual((r["mass_loss_tier"], t["xray"]["status"], t["xray_nondetection"]["status"]),
                         ("measured", "failed", "failed"))
        # η CrB B: no row, no class → `none`, and the miss is not authoritative
        inp = xc.resolve_star_wind_inputs({"sp_type": None, "main_id": None, "candidate": "* eta CrB B",
                                           "sl_failed": True, "domain": "main_sequence"}, {}, allow_network=True)
        r = sw.resolve_wind_model(inp)
        self.assertEqual(r["mass_loss_tier"], "none")
        self.assertIn("not_authoritative", r["wind_model"]["flags"])
        # a resolved B that simply never reaches the ladder (no distance) keeps `not_reachable`
        inp = xc.resolve_star_wind_inputs({"sp_type": "K1V", "main_id": "* alf Cen B", "domain": "main_sequence"},
                                          {}, allow_network=True)
        self.assertEqual(sw.resolve_wind_model(inp)["wind_model"]["tiers"]["xray"]["status"], "not_reachable")


@pytest.mark.cr26_network
class ReGateQueryEvolvedTest(unittest.TestCase):
    """RG9 through query.py's evolved --star branch (marked so the conftest leaves allow_network alone; every
    seam the branch reaches is mocked — an evolved star never reaches the catalog ladder)."""

    def _arcturus(self, ident_fail):
        from core import databases, stellar_mass
        from core import xray_catalog as xc
        sl = {"main_id": "* alf Boo", "sp_type": "K1.5IIIFe-0.5", "otype": "RG*", "plx_value": 88.83,
              "designations": {}, "ra": 213.9, "dec": 19.2}
        with mock.patch.object(databases, "compute_simbad_lookup", return_value=sl), \
                mock.patch.object(stellar_mass, "resolve_component_mass", return_value=(1.08, "catalog", None)), \
                mock.patch.object(xc, "_identity_lookup",
                                  return_value=((None, "unreachable") if ident_fail else (None, None))):
            return _inproc(star="Arcturus")

    def test_rg9_query_evolved_star_branch(self):
        d = self._arcturus(True)
        self.assertEqual((d["domain"], d["mass_loss_tier"]), ("evolved", "noncoronal_row"))
        self.assertIn("not_authoritative", d["wind_model"]["flags"])
        self.assertTrue(any("identity lookup" in n for n in d["wind_model"]["notes"]))
        d = self._arcturus(False)                                            # unforced → unchanged
        self.assertNotIn("not_authoritative", d["wind_model"]["flags"])
        self.assertFalse(any("identity lookup" in n for n in d["wind_model"]["notes"]))


@pytest.mark.cr26_network
class StarLogFxRunsRadiusTest(unittest.TestCase):
    def test_star_log_fx_runs_radius_family_only(self):
        from core import xray_catalog as xc
        from tests.test_cr25 import _star_mocks
        ps = _star_mocks()
        for p in ps:
            p.start()
        try:
            with mock.patch.object(xc, "radius_candidates",
                                   return_value=([{"source": "tic", "value": 0.33}], {}, False, False)) as rc, \
                    mock.patch.object(xc, "xray_ladder", side_effect=AssertionError("ladder")), \
                    mock.patch.object(xc, "_identity_lookup", return_value=(None, None)), \
                    mock.patch("core.databases.compute_simbad_lookup",
                               lambda name: {"main_id": "V* EV Lac", "sp_type": "M4.0Ve", "otype": "PM*",
                                             "designations": {}, "plx_value": 198.0, "ra": 341.7, "dec": 44.3}):
                d = _inproc(star="EV Lac", log_fx=6.5)
        finally:
            for p in reversed(ps):
                p.stop()
        rc.assert_called_once()
        self.assertEqual(d["mass_loss_tier"], "measured")        # EV Lac is measured; tiers.xray uses the flux
        e = d["wind_model"]["tiers"]["xray"]
        self.assertEqual(e["log_fx"], 6.5)
        self.assertEqual(d["wind_model"]["radius"]["radius_source"], "tic")


if __name__ == "__main__":
    unittest.main()
