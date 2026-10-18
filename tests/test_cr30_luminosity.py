"""CR-30.3 — the region luminosity on S1's zero point, Sol, and the M-dwarf colour route (+ the 2MASS markers).

Offline: SIMBAD records are dicts; the 2MASS resolution is stubbed (``twomass.resolve`` by the conftest default, or
the II/246 seam + identifier memo in the ``cr30_twomass``-marked tests).
"""
import json
import math
import os
import unittest
from unittest import mock

import pytest

from core import databases, ms_sequence, regions, twomass
from tests._queryharness import run_query_inproc

_PROXIMA = {"main_id": "Proxima Centauri", "sp_type": "M5.5Ve", "teff": 3000.0, "vmag": 11.13,
            "plx_value": 768.0665}
_PROXIMA_ID = "2MASS J14294291-6240465"


def _tm(j, ks, qual="AAA", status="ok", ids=("2MASS JX",)):
    return {"status": status, "ids": list(ids),
            "jks": {"status": "ok", "designation": ids[0], "j": j, "e_j": 0.02, "ks": ks, "e_ks": 0.03,
                    "ph_qual": qual, "rd_flg": "222",
                    "quality_below_a": [b for b, q in zip(("J", "H", "Ks"), qual) if q != "A" and b != "H"]}}


def _reg(sl, tm):
    with mock.patch.object(twomass, "resolve", return_value=tm):
        return regions.compute_star_system_regions_from_simbad(sl)


class ZeroPointTest(unittest.TestCase):
    def test_sol_is_one(self):
        r = regions.compute_sol_regions()
        self.assertAlmostEqual(r["bcLuminosity"], 1.0, places=12)
        self.assertAlmostEqual(r["bcAbsMagnitude"], 4.74, places=12)

    def test_sol_regions_subcommand(self):
        code, out, _ = run_query_inproc("sol-regions")
        self.assertEqual(code, 0)
        self.assertAlmostEqual(out["bcLuminosity"], 1.0000, places=4)

    def test_star_regions_manual_lacaille(self):
        code, out, _ = run_query_inproc("star-regions-manual", "--vmag", "7.39", "--bc", "-1.47", "--teff", "3690",
                                        "--parallax", "304.14")
        self.assertEqual(code, 0)
        self.assertAlmostEqual(out["bcLuminosity"], 0.03646, places=5)
        self.assertAlmostEqual(out["absMagnitude"], 9.8054, places=4)

    def test_exact_step(self):
        self.assertAlmostEqual(ms_sequence.luminosity_from_mbol(4.74 - 2.5), 10.0, places=12)


class ColourRouteTest(unittest.TestCase):
    def test_proxima(self):
        r = _reg(_PROXIMA, _tm(5.357, 4.384, "AAE", ids=(_PROXIMA_ID,)))
        self.assertEqual(r["lum_route"], "colour")
        self.assertAlmostEqual(r["bcLuminosity"], 0.001572, places=6)
        self.assertAlmostEqual(r["lum_colour_paths"]["bc_v"], 0.0015246, places=7)
        self.assertAlmostEqual(r["lum_colour_paths"]["bc_k"], 0.0016195, places=7)
        self.assertAlmostEqual(r["lum_subtype_lsun"], 0.001274, places=6)
        self.assertAlmostEqual(r["bcLuminosity"] / r["lum_subtype_lsun"], 1.234, places=3)
        self.assertFalse(r["lum_route_disagreement"])
        self.assertEqual(r["twomass"]["quality_below_a"], ["Ks"])
        self.assertNotIn("twomass_status", r)
        # BC_V check: V − J 5.773 → −3.760
        self.assertAlmostEqual(ms_sequence.colour_route_luminosity(11.13, 5.357, 4.384, 768.0665)["bc_v"],
                               -3.760, places=3)

    def test_upper_gate_vb10(self):
        sl = {"main_id": "VB 10", "sp_type": "M8V", "teff": 2600.0, "vmag": 17.30, "plx_value": 168.9537}
        r = _reg(sl, _tm(9.908, 8.765))
        self.assertEqual(r["lum_route"], "subtype")
        self.assertAlmostEqual(r["bcLuminosity"], 0.0006032, places=7)
        self.assertAlmostEqual(r["absMagnitude"], 18.4388, places=4)
        self.assertIn("outside", r["lum_route_reason"])
        # a build without the upper gate would read 0.0004585
        self.assertAlmostEqual(ms_sequence.colour_route_luminosity(17.30, 9.908, 8.765, 168.9537)["lum"],
                               0.0004585, places=7)

    def test_out_of_span_k_star(self):
        sl = {"main_id": "HD 4628", "sp_type": "K2.5V", "teff": 5000.0, "vmag": 5.74, "plx_value": 134.5}
        r = _reg(sl, _tm(5.74 - 1.373, 3.7, "DDD"))
        self.assertEqual(r["lum_route"], "subtype")

    def test_giant_takes_subtype_route(self):
        sl = {"main_id": "Aldebaran", "sp_type": "K5+III", "teff": 3900.0, "vmag": 0.86, "plx_value": 48.94}
        with mock.patch.object(twomass, "resolve", side_effect=AssertionError("no 2MASS lookup for a giant")):
            r = regions.compute_star_system_regions_from_simbad(sl)
        self.assertEqual(r["lum_route"], "subtype")
        self.assertEqual(r["lum_class_token"], "III")
        self.assertIn("giant", r["lum_route_reason"])

    def test_disagreement_flag_threshold(self):
        # the flag fires above a ratio of 1.40, not at 1.338 (BD-11 3759's)
        self.assertEqual(ms_sequence.COLOUR_DISAGREE_RATIO, 1.40)
        r = _reg(_PROXIMA, _tm(5.357, 4.384))
        sub = r["lum_subtype_lsun"]
        for ratio, flag in ((1.338, False), (1.469, True), (6.009, True)):
            with mock.patch.object(ms_sequence, "colour_route_luminosity",
                                   return_value={"lum": sub * ratio, "bc_v_path_lum": sub * ratio,
                                                 "bc_k_path_lum": sub * ratio, "bc_v": 0, "bc_k": 0, "m_v": 0,
                                                 "m_ks": 0, "v_minus_j": 5.0}):
                self.assertEqual(_reg(_PROXIMA, _tm(5.357, 4.384))["lum_route_disagreement"], flag, ratio)

    def test_letter_only_m_takes_colour_route_in_span(self):
        sl = dict(_PROXIMA, sp_type="M")
        r = _reg(sl, _tm(5.357, 4.384))
        self.assertEqual(r["lum_route"], "colour")
        self.assertTrue(r["subtype_unknown"])
        # no 2MASS → the letter-only M fails with the curated reason
        r = _reg(sl, {"status": "no_id", "ids": [], "jks": None})
        self.assertIn("S1 needs a subtype", r["error"])

    def test_multiple_ids_is_a_disclosure_not_a_degrade(self):
        r = _reg(dict(_PROXIMA, sp_type="M2V"), {"status": "multiple", "ids": ["2MASS J1", "2MASS J2"],
                                                  "jks": None})
        self.assertEqual(r["lum_route"], "subtype")
        self.assertEqual(r["twomass_ids_multiple"], ["2MASS J1", "2MASS J2"])
        self.assertNotIn("twomass_status", r)
        self.assertNotIn("not_authoritative", r)

    def test_degrades_fail_loud(self):
        for st in ("unreachable", "empty", "ids_failed"):
            r = _reg(_PROXIMA, {"status": st, "ids": [], "jks": None})
            self.assertIn("error", r, st)
            self.assertEqual(r["twomass_status"], st)
            self.assertTrue(r["not_authoritative"])
            self.assertNotIn("bcLuminosity", r)

    def test_not_looked_up_takes_subtype_quietly(self):
        r = _reg(_PROXIMA, {"status": twomass.NOT_LOOKED_UP, "ids": [], "jks": None})
        self.assertEqual(r["lum_route"], "subtype")
        self.assertNotIn("twomass_status", r)


@pytest.mark.cr30_twomass
class TwomassResolutionTest(unittest.TestCase):
    """The real resolution: the identifier memo + the II/246 seam (stubbed here)."""

    def _remember(self, main_id, ids):
        databases._remember_twomass_ids(main_id, ids)

    def test_acronym_2mass_only(self):
        self.assertEqual(twomass.twomass_ids_from_rows(["2MASS J10481463-3956062", "2MASSI J1048147-395606",
                                                        "2MASSW J1"]), ["2MASS J10481463-3956062"])

    def test_empty_identifier_query_is_ids_failed_for_km(self):
        self._remember("Star K", [])
        self.assertEqual(twomass.resolve({"main_id": "Star K", "sp_type": "K2V"})["status"], "ids_failed")
        self._remember("Star G", [])
        self.assertEqual(twomass.resolve({"main_id": "Star G", "sp_type": "G2V"})["status"], "not_applicable")

    def test_one_id_fetches_and_shares(self):
        self._remember("Proxima Centauri", ["NAME Proxima", _PROXIMA_ID])
        calls = []

        def _seam(d):
            calls.append(d)
            return {"rows": [{"2MASS": "14294291-6240465", "Jmag": 5.35699987, "e_Jmag": 0.023, "Kmag": 4.38399982,
                              "e_Kmag": 0.033, "Qflg": "AAE", "Rflg": "111"}]}
        with mock.patch.object(twomass, "_ii246_seam", _seam):
            a = twomass.resolve(_PROXIMA)
            b = twomass.resolve(_PROXIMA)
        self.assertEqual(a["status"], "ok")
        self.assertEqual((a["jks"]["j"], a["jks"]["ks"]), (5.357, 4.384))       # 2MASS's published precision
        self.assertEqual(b["jks"], a["jks"])
        self.assertEqual(len(calls), 1)                                         # once per designation

    def test_empty_and_unreachable(self):
        self._remember("S1", [_PROXIMA_ID])
        with mock.patch.object(twomass, "_ii246_seam", return_value={"rows": []}):
            self.assertEqual(twomass.resolve({"main_id": "S1", "sp_type": "M4V"})["status"], "empty")
        twomass.clear_memo()
        with mock.patch.object(twomass, "_ii246_seam", return_value={"error": "boom"}):
            self.assertEqual(twomass.resolve({"main_id": "S1", "sp_type": "M4V"})["status"], "unreachable")

    def test_forced_failure_hook_makes_no_call(self):
        self._remember("S2", [_PROXIMA_ID])
        os.environ[twomass.FORCE_ENV] = "1"
        try:
            with mock.patch.object(twomass, "_ii246_seam", side_effect=AssertionError("network")):
                self.assertEqual(twomass.resolve({"main_id": "S2", "sp_type": "M4V"})["status"], "unreachable")
        finally:
            os.environ.pop(twomass.FORCE_ENV, None)

    def test_two_ids_are_multiple(self):
        self._remember("Lalande", ["2MASS J11032027+3558203", "2MASS J11032023+3558117"])
        r = twomass.resolve({"main_id": "Lalande", "sp_type": "M2+V"})
        self.assertEqual(r["status"], "multiple")

    def test_not_looked_up(self):
        self.assertEqual(twomass.resolve({"main_id": "Never Looked Up", "sp_type": "M4V"})["status"],
                         twomass.NOT_LOOKED_UP)


class MarkerCarrierTest(unittest.TestCase):
    """Every caller of the region step surfaces a 2MASS degrade (exit 0, not_authoritative) — plan §13.2 C1."""
    _DEG = {"status": "unreachable", "ids": [_PROXIMA_ID], "jks": None}

    def _patch(self):
        return mock.patch.object(twomass, "resolve", return_value=self._DEG)

    def _sl(self):
        return mock.patch.object(databases, "compute_simbad_lookup", return_value=dict(_PROXIMA))

    def test_star_regions(self):
        with self._patch(), self._sl():
            code, out, _ = run_query_inproc("star-regions", "--star", "Proxima Centauri")
        self.assertEqual(code, 0)
        self.assertEqual((out["twomass_status"], out["not_authoritative"], out["bcLuminosity"]),
                         ("unreachable", True, None))

    def test_circumbinary_hz(self):
        with self._patch(), self._sl():
            code, out, _ = run_query_inproc("circumbinary-hz", "--star1", "Proxima Centauri", "--star2",
                                            "Proxima Centauri")
        self.assertEqual(code, 0)
        self.assertTrue(out["not_authoritative"])
        self.assertEqual(out["stars"][0]["twomass_status"], "unreachable")

    def test_dyson_collector(self):
        with self._patch(), self._sl():
            code, out, _ = run_query_inproc("dyson-collector", "--star", "Proxima Centauri", "--fraction", "0.5",
                                            "--orbit-au", "0.05")
        self.assertEqual(code, 0)
        self.assertEqual(out["twomass_status"], "unreachable")
        self.assertNotIn("Could not derive", json.dumps(out))

    def test_par_flux(self):
        from core import par_flux
        with self._patch(), self._sl():
            r = par_flux.compute_par_flux(star="Proxima Centauri", insolation_wm2=1361)
        self.assertEqual(r["twomass_status"], "unreachable")
        self.assertEqual(r["teff_k"], 3000.0)                    # SIMBAD's teff — no value moves

    def test_generate_real_anchor(self):
        from core import generate
        with self._patch(), mock.patch.object(generate, "compute_simbad_lookup", return_value=dict(_PROXIMA)):
            r = generate.generate_system(1, anchor_star="Proxima Centauri")
        self.assertEqual(r["twomass_status"], "unreachable")
        self.assertTrue(r["not_authoritative"])

    def test_dossier(self):
        from core import report
        from tests.test_report import _patched
        deg = {"error": twomass.NOTE_DEGRADE["unreachable"], "twomass_status": "unreachable",
               "not_authoritative": True}
        with _patched(regions_result=deg):
            r = report.build_system_dossier("Tau Ceti", sections=["identity", "regions"], fmt="json")
        self.assertEqual(r["twomass_status"], "unreachable")
        self.assertTrue(r["not_authoritative"])

    def test_dossier_gates_the_2mass_lookup_on_regions(self):
        from core import report
        from tests.test_report import _patched
        with _patched():
            with mock.patch("core.regions.compute_star_system_regions_from_simbad",
                            wraps=lambda sl, **kw: {"error": "x"}) as m:
                report.build_system_dossier("Tau Ceti", sections=["identity"], fmt="json")
                self.assertEqual(m.call_args.kwargs.get("twomass_lookup"), False)
                report.build_system_dossier("Tau Ceti", sections=["identity", "regions"], fmt="json")
                self.assertEqual(m.call_args.kwargs.get("twomass_lookup"), True)

    def test_compare_stars_per_star(self):
        from core import databases as dbs
        with self._patch(), self._sl(), mock.patch.object(dbs, "_flame_mass_for", return_value=(None, None)):
            r = dbs.compare_stars(["Proxima Centauri", "Sol"])
        prox = [s for s in r["stars"] if s.get("twomass_status")]
        self.assertTrue(prox)
        self.assertTrue(prox[0]["not_authoritative"])


if __name__ == "__main__":
    unittest.main()


class Cp2FixesTest(unittest.TestCase):
    """CP2 (2026-10-15) findings, pinned."""

    def test_force_hook_wins_over_a_cached_ok(self):
        twomass._JKS_MEMO["2MASS JZ"] = (None, {"status": "ok", "designation": "2MASS JZ", "j": 1, "ks": 1})
        os.environ[twomass.FORCE_ENV] = "1"
        try:
            self.assertEqual(twomass.fetch_jks("2MASS JZ")["status"], "unreachable")
        finally:
            os.environ.pop(twomass.FORCE_ENV, None)
        self.assertEqual(twomass.fetch_jks("2MASS JZ")["status"], "ok")       # never memoised

    def test_generate_degrade_is_an_error_with_the_marker(self):
        from core import generate
        with mock.patch.object(twomass, "resolve", return_value={"status": "unreachable", "ids": [], "jks": None}), \
                mock.patch.object(generate, "compute_simbad_lookup", return_value=dict(_PROXIMA)):
            r = generate.generate_system(1, anchor_star="Proxima Centauri")
        self.assertIn("error", r)
        self.assertEqual(r["twomass_status"], "unreachable")

    def test_exclusion_boundary_beta_error_keeps_the_marker(self):
        deg = {"status": "unreachable", "ids": [_PROXIMA_ID], "jks": None}
        with mock.patch.object(twomass, "resolve", return_value=deg), \
                mock.patch.object(databases, "compute_simbad_lookup",
                                  return_value=dict(_PROXIMA, designations={}, otype="BY*")), \
                mock.patch("core.stellar_mass.resolve_component_mass", return_value=(0.1221, "catalog", "n")):
            code, out, _ = run_query_inproc("exclusion-boundary", "--star", "Proxima Centauri", "--beta", "0.5")
        self.assertEqual(out.get("twomass_status"), "unreachable")
        self.assertTrue(out.get("not_authoritative"))

    def test_circumbinary_reports_a_hard_error_on_star2(self):
        deg = {"status": "unreachable", "ids": [_PROXIMA_ID], "jks": None}

        def _sl(name):
            return dict(_PROXIMA) if name == "Proxima Centauri" else {"error": "No results found for 'Nope'"}
        with mock.patch.object(twomass, "resolve", return_value=deg), \
                mock.patch.object(databases, "compute_simbad_lookup", side_effect=_sl):
            code, out, _ = run_query_inproc("circumbinary-hz", "--star1", "Proxima Centauri", "--star2", "Nope")
        self.assertEqual(code, 1)
        self.assertIn("No results", out["error"])

