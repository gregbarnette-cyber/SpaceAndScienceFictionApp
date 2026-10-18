"""CR-30.4 + 30.5 — the mass / luminosity / radius relations (Eker 2018, S1, Mann 2019) and the MIST v2.5 lifetime.

Hand anchors on the relations' grid values; in-process calls on the reachable paths with stubbed SIMBAD / 2MASS.
"""
import unittest
from unittest import mock

from core import equations, ms_sequence as ms, regions, stellar_mass, twomass
from tests._queryharness import run_query_inproc


def _mass(log_l):
    return ms.mass_from_luminosity(10 ** log_l)


class MassFromLuminosityTest(unittest.TestCase):
    def test_breaks(self):
        self.assertAlmostEqual(_mass(-0.80)["mass"], 0.7036, places=4)
        self.assertAlmostEqual(_mass(-0.78)["mass"], 0.7335, places=4)
        self.assertEqual(_mass(3.48)["mass"], 7.0)
        self.assertAlmostEqual(ms.SWITCH_072, -0.790308, places=6)
        self.assertAlmostEqual(ms.SWITCH_105, 0.108209, places=6)
        self.assertAlmostEqual(ms.SWITCH_240, 1.628616, places=6)
        self.assertAlmostEqual(ms.GAP7_LO, 3.4455, places=4)
        self.assertAlmostEqual(ms.GAP7_HI, 3.5262, places=4)

    def test_105_and_240_breaks_and_interiors(self):
        for lg, m in ((0.10, 1.0438), (0.12, 1.0603), (1.62, 2.3546), (1.64, 2.4545), (0.5, 1.2977),
                      (2.0, 3.0249), (4.0, 10.244)):
            self.assertAlmostEqual(_mass(lg)["mass"], m, places=3 if m > 10 else 4, msg=lg)

    def test_switch_and_s1(self):
        self.assertAlmostEqual(_mass(-2.50)["mass"], 0.1655, places=4)
        self.assertEqual(_mass(-2.50)["relation"], "S1_sequence")
        self.assertAlmostEqual(_mass(-1.066)["mass"], 0.615391, places=5)
        self.assertAlmostEqual(_mass(0.0)["mass"], 1.0028, places=4)
        self.assertAlmostEqual(_mass(5.5)["mass"], 40.93, places=2)
        self.assertEqual(_mass(5.5)["relation"], "S1_sequence")

    def test_no_clamp(self):
        r = ms.mass_from_luminosity(1e-4)
        self.assertIsNone(r["mass"])
        self.assertIn("never clamped", r["reason"])


class LuminosityAndRadiusFromMassTest(unittest.TestCase):
    def test_l_of_m_on_both_sides_of_each_break(self):
        for m, l in ((0.72, 0.17609), (0.7201, 0.14928), (1.05, 1.3022), (1.0501, 1.2645), (2.4, 45.283),
                     (2.4001, 39.936), (7.0, 2789.4), (7.001, 3360.3), (0.30, 0.011227)):
            self.assertAlmostEqual(ms.luminosity_from_mass(m)["lum"] / l, 1.0, places=4, msg=m)
        self.assertAlmostEqual(ms.luminosity_from_mass(40)["lum"] / 3.0304e5, 1.0, places=4)

    def test_r_of_m(self):
        self.assertAlmostEqual(ms.radius_from_mass(1.0)["radius"], 1.012, places=6)
        self.assertAlmostEqual(ms.radius_from_mass(1.80)["radius"], 1.7477, places=4)
        self.assertAlmostEqual(ms.radius_from_mass(1.90)["radius"], 1.7886, places=4)
        self.assertAlmostEqual(ms.radius_from_mass(2.063)["radius"], 2.1418, places=4)
        self.assertAlmostEqual(ms.radius_from_mass(0.30)["radius"], 0.3192, places=4)

    def test_outside_span_null_with_reason(self):
        for m in (0.077, 60):
            self.assertIsNone(ms.radius_from_mass(m)["radius"])
            self.assertIsNone(ms.luminosity_from_mass(m)["lum"])
            self.assertIn("outside S1's mass span", ms.radius_from_mass(m)["reason"])


class MksRouteTest(unittest.TestCase):
    def test_hand_anchors(self):
        self.assertAlmostEqual(ms.mks_mass(6.0), 0.4404, places=4)
        self.assertIsNone(ms.mks_mass(3.5))
        self.assertIsNone(ms.mks_mass(10.8))
        self.assertAlmostEqual(ms.mks_mass(10.5), 0.0792, places=4)
        self.assertAlmostEqual(ms.mks_mass(10.0), 0.0872, places=4)

    def _tm(self, ks):
        return {"status": "ok", "ids": ["2MASS JX"],
                "jks": {"status": "ok", "designation": "2MASS JX", "j": ks + 0.9, "e_j": 0.02, "ks": ks,
                        "e_ks": 0.02, "ph_qual": "AAA", "rd_flg": "222", "quality_below_a": []}}

    def test_region_path_takes_mks(self):
        sl = {"main_id": "G 113-20", "sp_type": "M2V", "teff": 3500.0, "vmag": 11.0, "plx_value": 111.8698}
        with mock.patch.object(twomass, "resolve", return_value=self._tm(5.766)):
            r = regions.compute_star_system_regions_from_simbad(sl)
        self.assertAlmostEqual(r["stellarMass"], 0.4389, places=4)
        self.assertEqual(r["mass_route"], "mks")
        self.assertAlmostEqual(r["m_ks"], 6.0096, places=4)
        self.assertIsNotNone(r["mass_lroute_solar"])

    def test_outside_gate_takes_l_route(self):
        sl = {"main_id": "HD 219134", "sp_type": "K3V", "teff": 4800.0, "vmag": 5.57, "plx_value": 153.08}
        with mock.patch.object(twomass, "resolve", return_value=self._tm(3.261)):
            r = regions.compute_star_system_regions_from_simbad(sl)
        self.assertEqual(r["mass_route"], "luminosity")
        self.assertEqual(r["mks"]["status"], "outside_gate")

    def test_no_v_still_reports_mks(self):
        sl = {"main_id": "SCR J1845-6357", "sp_type": "M8.5V", "teff": None, "vmag": None, "plx_value": 249.6651}
        with mock.patch.object(twomass, "resolve", return_value=self._tm(8.508)):
            r = regions.compute_star_system_regions_from_simbad(sl)
        self.assertIn("error", r)
        self.assertAlmostEqual(r["mks"]["mass"], 0.0793, places=4)

    def test_resolver_tier_order(self):
        mks = {"status": "ok", "mass": 0.44, "m_ks": 6.0}
        md = {}
        m, prov, _ = stellar_mass.resolve_component_mass(
            {"name": "X", "sp_type": "M2V", "luminosity_lsun": 0.02, "mks": mks}, None, allow_flame=False,
            detail_out=md)
        self.assertEqual((m, prov), (0.44, "ms_mks_relation"))
        self.assertEqual(md["mass_route"], "mks")
        self.assertIsNotNone(md["mass_lroute_solar"])
        # a catalog-free spec without mks → the luminosity route (Eker 2018 / S1)
        m, prov, _ = stellar_mass.resolve_component_mass(
            {"name": "X", "sp_type": "M2V", "luminosity_lsun": 0.022272}, None, allow_flame=False)
        self.assertEqual(prov, "ms_luminosity_inversion")
        self.assertAlmostEqual(m, 0.3975, places=4)                     # Lalande 21185's L route

    def test_degraded_mks_never_falls_to_the_l_route(self):
        m, prov, note = stellar_mass.resolve_component_mass(
            {"name": "X", "sp_type": "M2V", "luminosity_lsun": 0.02, "mks": {"status": "unreachable", "mass": None}},
            None, allow_flame=False)
        self.assertIsNone(m)
        self.assertIn("not authoritative", note)

    def test_no_caution_on_mks(self):
        b = stellar_mass.resolve_mass(None, sp_type="M2V", mks_mass=0.44)
        self.assertFalse(b["massL_inversion_caution"])
        self.assertIn("Mann et al. 2019", b["note"])

    def test_caution_only_for_o_b(self):
        self.assertTrue(stellar_mass.resolve_mass(5.0, sp_type="B3V")["massL_inversion_caution"])
        self.assertFalse(stellar_mass.resolve_mass(2.0, sp_type="A1V")["massL_inversion_caution"])


class InversionCallTest(unittest.TestCase):
    """CR-30.4 acceptance 1–3 on ``exclusion-system --component id=X,lum=…`` (offline)."""

    def _m(self, lum):
        code, out, _ = run_query_inproc("exclusion-system", "--component", f"id=X,lum={lum}")
        self.assertEqual(code, 0, out)
        return out["zones"][0]["components"][0]["mass_solar"]

    def test_breaks_live_path(self):
        self.assertAlmostEqual(self._m(10 ** -0.80), 0.7036, places=4)
        self.assertAlmostEqual(self._m(10 ** -0.78), 0.7335, places=4)
        self.assertAlmostEqual(self._m(10 ** 3.48), 7.0, places=6)
        self.assertAlmostEqual(self._m(10 ** -2.50), 0.1655, places=4)

    def test_no_clamp_live_path(self):
        code, out, _ = run_query_inproc("exclusion-system", "--component", "id=X,lum=0.0001")
        self.assertNotEqual(code, 0)


class LifetimeTest(unittest.TestCase):
    def test_mist_anchors(self):
        self.assertAlmostEqual(ms.ms_lifetime(1.0)["yr"] / 1e9, 8.894, places=3)
        self.assertAlmostEqual(ms.ms_lifetime(1.25)["yr"] / 1e9, 4.092, places=3)
        self.assertAlmostEqual(ms.ms_lifetime(1.16)["yr"] / ms.ms_lifetime(1.15)["yr"], 1.064, places=3)
        self.assertAlmostEqual(ms.ms_lifetime(0.30)["yr"] / 1e9, 440.86, places=2)
        r = ms.ms_lifetime(0.62)
        self.assertAlmostEqual(r["yr"] / 1e9, 50.31, places=2)
        self.assertEqual(r["end_point"], "interpolated_1e-2_to_1e-4")
        self.assertAlmostEqual(ms.ms_lifetime(300)["yr"] / 1e6, 2.304, places=3)
        self.assertIsNone(ms.ms_lifetime(301)["yr"])
        self.assertEqual(ms.ms_lifetime(301)["status"], "above_300")
        self.assertAlmostEqual(ms.ms_lifetime(0.10)["yr"], 3.3049e12, delta=1e9)

    def test_log_log_not_linear_at_0125(self):
        from core import ms_reference_tables
        tr = ms_reference_tables.mist_tracks()
        lo = next(t for t in tr if t["initial_mass"] == 0.10)
        hi = next(t for t in tr if t["initial_mass"] == 0.15)
        lin = lo["ms_duration_yr"] + (0.125 - 0.10) / 0.05 * (hi["ms_duration_yr"] - lo["ms_duration_yr"])
        self.assertAlmostEqual(lin / ms.ms_lifetime(0.125)["yr"], 1.080, places=3)

    def test_stellar_evolution(self):
        r = equations.compute_stellar_evolution(1.0)
        self.assertAlmostEqual(r["ms_end_gyr"], 8.983, places=3)
        r = equations.compute_stellar_evolution(1.478, 2.7)
        self.assertAlmostEqual(r["ms_end_gyr"], 2.473, places=3)
        self.assertEqual(r["current_stage"], "Subgiant Branch")
        self.assertAlmostEqual(equations.compute_stellar_evolution(0.62)["ms_end_gyr"], 50.82, places=2)

    def test_sol_lifetime_and_pinned_mass(self):
        r = regions.compute_sol_regions()
        self.assertEqual(r["stellarMass"], 1.0)
        self.assertAlmostEqual(r["mainSeqLifeSpan"] / 1e9, 8.894, places=3)

    def test_l_of_m_at_one_is_s12(self):
        self.assertAlmostEqual(ms.luminosity_from_mass(1.0)["lum"], 10 ** -0.007, places=6)


class NullMassPrintTest(unittest.TestCase):
    def test_region_with_no_mass_is_null_not_a_crash(self):
        # an L below M9.5V's: the L-route mass is null and every mass-derived field with it
        r = regions.compute_star_system_regions(vmag=20.0, boloLum=-6.0, temp=2300.0, plx=100.0)
        self.assertIsNone(r["stellarMass"])
        for k in ("stellarRadius", "luminosityFromMass", "mainSeqLifeSpan", "planetaryYear", "sysilGrav", "sysol",
                  "calculatedLuminosity"):
            self.assertIsNone(r[k], k)
        self.assertTrue(r["mass_null_reason"])
        from core.shared import fmt_num
        self.assertEqual(fmt_num(r["stellarMass"], ".4f"), "—")


if __name__ == "__main__":
    unittest.main()


class Cp3FixesTest(unittest.TestCase):
    """CP3 (2026-10-15) findings, pinned."""

    def test_switch_band_on_both_sides(self):
        for lg, band in ((-0.80, "0.72"), (-0.77, "0.72"), (0.105, "1.05"), (0.11, "1.05"), (1.61, "2.40"),
                         (1.64, "2.40"), (0.5, None), (-1.0, None)):
            self.assertEqual(ms.mass_from_luminosity(10 ** lg)["switch_band"], band, lg)

    def test_stellar_evolution_nan_is_an_error(self):
        self.assertIn("error", equations.compute_stellar_evolution(float("nan")))

    def test_mks_activity_caveat(self):
        tm = {"status": "ok", "ids": ["x"], "jks": {"status": "ok", "designation": "x", "j": 7.0, "ks": 6.0,
                                                     "e_j": 0, "e_ks": 0, "ph_qual": "AAA", "rd_flg": "222",
                                                     "quality_below_a": []}}
        sl = {"main_id": "EV Lac", "sp_type": "M4.0Ve", "otype": "BY*", "plx_value": 198.0}
        self.assertIn("2 %", regions.mks_route(sl, tm=tm)["activity_caveat"])
        self.assertNotIn("activity_caveat", regions.mks_route(dict(sl, otype="PM*"), tm=tm))

    def test_null_mass_region_diagram_does_not_crash(self):
        from core import viz
        r = regions.compute_star_system_regions(vmag=20.0, boloLum=-6.0, temp=2300.0, plx=100.0)
        d = viz.prepare_system_regions_diagram(r)
        self.assertGreater(d["max_au"], 0)
        self.assertEqual(d["hz_zones"], [])

    def test_composed_2mass_degrade_marks_the_result(self):
        sel = {"m1_solar": 0.4, "m2_solar": 0.3, "mass_prov_a": "binary_orbit_m1", "mass_prov_b": "x", "notes": []}
        deg = {"status": "unreachable", "mass": None}
        fs = {}
        with mock.patch.object(regions, "mks_route", return_value=deg), \
                mock.patch("core.databases.compute_simbad_lookup", return_value={"error": "x"}):
            stellar_mass.resolve_binary_components({"main_id": "X", "sp_type": "M3V", "designations": {},
                                                    "plx_value": 100.0}, sel, None, allow_flame=False,
                                                   status_out=fs)
        self.assertTrue(fs["not_authoritative"])
        self.assertEqual(fs["twomass_status_a"], "unreachable")
