"""CR-27.1 / CR-27.2 — the SIMBAD lookup resolves a zero-flux object, and per-measurement fields read row 0, else the
median of the non-null rows (plan §1, §2). Offline: the REAL ``compute_simbad_lookup`` body runs on fakes
(``tests/_cr27fakes.py``)."""
import json
import os
import unittest

from core import databases
from tests._cr27fakes import PRECHANGE_CASES, patched_lookup, row

_FIX = os.path.join(os.path.dirname(__file__), "fixtures", "cr27_simbad_prechange.json")


def _zero_flux_row():
    return {"main_id": "*  61 Cyg", "ra": 316.7, "dec": 38.75, "sp_type": None, "plx_value": None,
            "mesfe_h.teff": None, "mesfe_h.fe_h": None, "otype": "**"}


class ZeroFluxRetryTest(unittest.TestCase):
    """CR-27.1 (plan §1.1)."""

    def test_zero_flux_object_resolves_with_null_fields(self):           # acc 1 (T1.1)
        with patched_lookup([], [_zero_flux_row()], ids=("*  61 Cyg", "GJ 820")) as st:
            res, via = databases.simbad_lookup_ex("61 Cyg")
        self.assertNotIn("error", res)
        self.assertTrue(via)
        self.assertEqual(res["main_id"], "*  61 Cyg")
        self.assertEqual(res["otype"], "**")
        for k in ("vmag", "sp_type", "plx_value", "ly", "parsecs", "teff", "fe_h"):
            self.assertIsNone(res[k], k)
        self.assertEqual(st.script["calls"], ["query_object", "query_objectids", "query_object_noV"])

    def test_resolving_object_takes_one_query_and_is_byte_identical(self):   # acc 2 (T1.2)
        with open(_FIX, encoding="utf-8") as fh:
            pre = json.load(fh)
        for name, rows in PRECHANGE_CASES.items():
            with self.subTest(case=name):
                with patched_lookup(rows) as st:
                    res, via = databases.simbad_lookup_ex("X")
                self.assertFalse(via)
                self.assertEqual(json.loads(json.dumps(res)), pre[name]["result"])
                self.assertEqual(st.script["calls"], ["query_object", "query_objectids"])

    def test_unknown_name_no_retry_same_error(self):                      # T1.3 + plan F-B4 (no extra query)
        with patched_lookup([], [], ids=()) as st:
            res = databases.compute_simbad_lookup("No Such Star 123")
        self.assertTrue(res["error"].startswith(databases.SIMBAD_NO_RESULTS_PREFIX))
        self.assertEqual(st.script["calls"], ["query_object", "query_objectids"])

    def test_retry_failure_is_the_network_error_not_no_results(self):      # T1.4
        import requests
        with patched_lookup([], no_v_raise=requests.exceptions.ConnectionError("down")):
            res = databases.compute_simbad_lookup("61 Cyg")
        self.assertIn("error", res)
        self.assertFalse(res["error"].startswith(databases.SIMBAD_NO_RESULTS_PREFIX))
        self.assertIn("SIMBAD", res["error"])

    def test_retry_answers_empty_is_no_results(self):
        with patched_lookup([], [], ids=("X",)):
            res, via = databases.simbad_lookup_ex("X")
        self.assertTrue(res["error"].startswith(databases.SIMBAD_NO_RESULTS_PREFIX))
        self.assertFalse(via)

    def test_compute_simbad_lookup_is_the_first_element(self):            # T1.8
        with patched_lookup([], [_zero_flux_row()], ids=("*  61 Cyg",)):
            a = databases.compute_simbad_lookup("61 Cyg")
        with patched_lookup([], [_zero_flux_row()], ids=("*  61 Cyg",)):
            b, _via = databases.simbad_lookup_ex("61 Cyg")
        self.assertEqual(a, b)


class PerMeasurementMedianTest(unittest.TestCase):
    """CR-27.2 (plan §2)."""

    def _lookup(self, rows):
        with patched_lookup(rows):
            return databases.compute_simbad_lookup("X")

    def test_vega_shape_teff_median_feh_row0(self):                       # acc 1 (T2.1)
        teffs = [None] + [float(t) for t in range(9000, 9000 + 47 * 20, 20)]
        rows = [row(teff=t, feh=(-0.30000001192092896 if i == 0 else -0.5)) for i, t in enumerate(teffs)]
        res = self._lookup(rows)
        import statistics
        self.assertEqual(res["teff"], statistics.median(teffs[1:]))
        self.assertEqual(res["fe_h"], -0.30000001192092896)

    def test_vb10_odd_count(self):                                        # acc 3 (T2.2)
        res = self._lookup([row(teff=t) for t in (None, 4008.0, 2700.0, 2745.0)])
        self.assertEqual(res["teff"], 2745.0)

    def test_even_count_mean_of_central_values(self):                     # acc 7 (T2.3)
        vals = [-0.2, -0.1, -0.07000000029802322, -0.05000000074505806, 0.0, 0.1]
        res = self._lookup([row(teff=4001.0, feh=None)] + [row(teff=None, feh=v) for v in vals])
        self.assertEqual(res["fe_h"], -0.06000000052154064)
        self.assertEqual(res["teff"], 4001.0)

    def test_fields_independent(self):                                    # T2.4 (Procyon shape, acc 5)
        res = self._lookup([row(teff=6615.0, feh=None), row(teff=6500.0, feh=0.0), row(teff=None, feh=0.0)])
        self.assertEqual(res["teff"], 6615.0)
        self.assertEqual(res["fe_h"], 0.0)

    def test_no_value_anywhere_is_null(self):                             # T2.5
        res = self._lookup([row(teff=None, feh=None), row(teff=None, feh=None)])
        self.assertIsNone(res["teff"])
        self.assertIsNone(res["fe_h"])

    def test_row0_wins_over_a_different_median(self):                     # T2.6 (acc 2)
        res = self._lookup([row(teff=4450.0), row(teff=9000.0), row(teff=9100.0)])
        self.assertEqual(res["teff"], 4450.0)

    def test_masked_and_sentinel_cells_skipped(self):                     # T2.7
        res = self._lookup([row(teff=None), row(teff="--"), row(teff="nan"), row(teff=3000.0)])
        self.assertEqual(res["teff"], 3000.0)


if __name__ == "__main__":
    unittest.main()


# ── §1.3 callers on a zero-flux record (Q7; WB MSG 346) ─────────────────────────────────────────────────────────────
from unittest import mock  # noqa: E402

_NULL_SL = {"main_id": "*  61 Cyg", "ra": 316.7, "dec": 38.75, "sp_type": None, "plx_value": None, "teff": None,
            "vmag": None, "fe_h": None, "ly": None, "parsecs": None, "otype": "**",
            "designations": {"MAIN_ID": "*  61 Cyg", "GJ": "GJ 820"}, "desig_str": "*  61 Cyg, GJ 820",
            "gcns": None, "gould": None, "multiplicity": None}


def _via(flag):
    """Patch databases.simbad_lookup_ex → (the null record, flag)."""
    return mock.patch.object(databases, "simbad_lookup_ex", lambda name: (dict(_NULL_SL), flag))


class DebrisDiskZeroFluxTest(unittest.TestCase):
    """T1.5 — the curated error at the upper-limit branch, never the 5778 K default."""

    def _run(self, flag, chen=None):
        from core import debris_disk
        ul = mock.MagicMock(return_value={"detection": "upper_limit", "upper_limit_L_IR_over_Lstar": 1e-4})
        with _via(flag), \
             mock.patch.object(debris_disk, "_match_row", side_effect=[(chen, None), (None, None)]), \
             mock.patch.object(debris_disk, "_wise_upper_limit", ul), \
             mock.patch.object(debris_disk, "_chen_components",
                               lambda r: [{"type": "cold", "ref": "Chen 2014"}]):
            return debris_disk.debris_disk(star="61 Cyg"), ul

    def test_retry_record_gets_curated_error(self):
        res, ul = self._run(True)
        self.assertIn("error", res)
        self.assertIn("has no Teff in SIMBAD and no flux row", res["error"])
        self.assertIn("vizier:J/ApJS/211/25 (Chen 2014)", res["route_tried"])          # CP1: the routes that ran
        self.assertNotIn("No results found", res["error"])
        ul.assert_not_called()

    def test_today_resolving_null_record_keeps_5778_path(self):          # WB's IR-only case: byte-identical
        res, ul = self._run(False)
        self.assertNotIn("error", res)
        ul.assert_called_once()
        self.assertIsNone(ul.call_args[0][3])                             # teff None → _wise_upper_limit's 5778

    def test_detection_still_reported_on_retry_record(self):             # plan F-B9: guard only at the UL branch
        res, ul = self._run(True, chen={"x": 1})
        self.assertEqual(res["detection"], "detected")
        ul.assert_not_called()


class BinaryNssZeroFluxTest(unittest.TestCase):
    """T1.6 — the NSS route leaves m1-dependent masses null (+ caveat) on a retry record; tier 1 skips."""

    _TI_ROW = {"period": 3000.0, "eccentricity": 0.3, "a_thiele_innes": 5.0, "b_thiele_innes": 2.0,
               "f_thiele_innes": -1.0, "g_thiele_innes": 4.0, "parallax": 286.0, "nss_solution_type": "Orbital",
               "significance": 40.0}

    def _orbit(self, flag, sp=None, rows=None, bmass=None, sb9=None):
        from core import binary, catalog
        sl = dict(_NULL_SL, sp_type=sp,
                  designations={"MAIN_ID": "*  61 Cyg", "Gaia EDR3": "Gaia DR3 1872046574983497216"})

        def _vq(catalog=None, **k):                                       # SB9: main cone → orbits
            if sb9 is None:
                return {"rows": []}
            return {"rows": [sb9[0]]} if catalog == "B/sb9/main" else {"rows": sb9[1]}
        with mock.patch.object(databases, "simbad_lookup_ex", lambda name: (dict(sl), flag)), \
             mock.patch.object(catalog, "gaia_tap", return_value={"rows": rows or [dict(self._TI_ROW)]}), \
             mock.patch.object(catalog, "gaia_binary_masses", return_value=(bmass, None)), \
             mock.patch.object(catalog, "vizier_query", side_effect=_vq), \
             mock.patch.object(binary, "_wds_orb6_solutions", return_value=[]):
            return binary.binary_orbit(star="61 Cyg")

    def _nss(self, res):
        return [s for s in res["solutions"] if s["source"] == "gaia-nss:two_body_orbit"]

    def test_gaia_binary_masses_still_fill(self):                        # CP1 #1
        res = self._orbit(True, bmass={"m1": 0.7, "m2": 0.63})
        comp = self._nss(res)[0]["companion"]
        self.assertEqual(comp["method"], "gaia-binary-masses")
        self.assertEqual(comp["m2_solar"], 0.63)

    def test_gaia_m1_only_cross_check_kept_on_placeholder(self):       # CP4 #2
        comp = self._nss(self._orbit(True, bmass={"m1": 0.7, "m2": None}))[0]["companion"]
        self.assertIsNone(comp["m2_solar"])
        self.assertEqual(comp["binary_masses"]["m1_solar"], 0.7)

    def test_sb9_sb1_blank_sp1_null_masses(self):                         # CP1 #2
        from core import binary
        sb9 = ({"Seq": 1, "Sp1": ""}, [{"Per": 100.0, "e": 0.1, "K1": 10.0, "Grade": 3, "Ref": "x"}])
        comp = [s for s in self._orbit(True, sb9=sb9)["solutions"] if s["source"] == "sb9"][0]["companion"]
        self.assertIsNone(comp["m2_solar"])
        self.assertEqual(comp["caveat"], binary._NOTE_M1_UNKNOWN)
        sb9k = ({"Seq": 1, "Sp1": "K5V"}, sb9[1])                       # Sp1 decodes → computed as today
        comp = [s for s in self._orbit(True, sb9=sb9k)["solutions"] if s["source"] == "sb9"][0]["companion"]
        self.assertIsNotNone(comp["m2_solar"])

    def test_undecodable_sp_type_counts_as_unknown(self):                # CP1 #3
        comp = self._nss(self._orbit(True, sp="DA"))[0]["companion"]
        self.assertIsNone(comp["m2_solar"])
        comp = self._nss(self._orbit(True, sp="K5V"))[0]["companion"]    # decodes → computed
        self.assertIsNotNone(comp["m2_solar"])

    def test_sb1_row_without_parallax_labelled_spec_min(self):           # CP1 #6 / #7
        row = dict(self._TI_ROW, parallax=None, semi_amplitude_primary=12.0)
        comp = self._nss(self._orbit(True, rows=[row]))[0]["companion"]
        self.assertEqual(comp["method"], "spec-min")
        self.assertEqual(comp["class"], "unknown")
        self.assertIs(comp["low_significance"], False)

    def test_retry_record_null_masses_and_caveat(self):
        from core import binary
        res = self._orbit(True)
        nss = [s for s in res["solutions"] if s["source"] == "gaia-nss:two_body_orbit"]
        self.assertEqual(len(nss), 1)
        comp = nss[0]["companion"]
        self.assertIsNone(comp["m1_solar"])
        self.assertIsNone(comp["m2_solar"])
        self.assertEqual(comp["caveat"], binary._NOTE_M1_UNKNOWN)
        self.assertEqual(nss[0]["period_d"], 3000.0)                      # elements kept
        self.assertNotIn("_zero_flux_retry", res["identity"])            # never emitted
        sel = binary._extract_stability_elements_full(res["solutions"], res["identity"])
        self.assertIsNone(sel[0])                                         # tier 1 (and 2/3) skip

    def test_normal_record_unchanged(self):
        res = self._orbit(False)
        comp = [s for s in res["solutions"] if s["source"] == "gaia-nss:two_body_orbit"][0]["companion"]
        self.assertEqual(comp["m1_solar"], 1.0)                           # today's sp-less default, unchanged
        self.assertIsNotNone(comp["m2_solar"])


class DossierZeroFluxTest(unittest.TestCase):
    """T1.7 — the dossier on an all-null record: exit 0, identity rendered, sections give curated warnings."""

    def test_dossier_all_null_record(self):
        from core import regions, report
        from tests.test_report import _patched
        reg = regions.compute_star_system_regions_from_simbad(dict(_NULL_SL))
        self.assertIn("error", reg)                                       # the curated missing-field error
        with _patched(simbad=dict(_NULL_SL), regions_result=reg):
            r = report.build_system_dossier("61 Cyg", fmt="json")
        self.assertNotIn("error", r)
        self.assertEqual(r["data"]["identity"]["primary_name"], "*  61 Cyg")


class CompareStarsZeroFluxTest(unittest.TestCase):
    """Behaviour change (a): compare-stars gives an all-null entry (error None), never "No results found"."""

    def test_compare_all_null_entry(self):
        rec = {"* alf Cen A": dict(_NULL_SL, main_id="* alf Cen A", sp_type="G2V", teff=5790.0),
               "61 Cyg": dict(_NULL_SL)}
        with mock.patch.object(databases, "compute_simbad_lookup", lambda n: dict(rec[n])), \
             mock.patch.object(databases, "_query_tap", return_value=[]), \
             mock.patch.object(databases, "_flame_mass_for", return_value=(None, None)), \
             mock.patch.object(databases, "compute_hypatia_data", return_value={"error": "none"}):
            res = databases.compare_stars(["* alf Cen A", "61 Cyg"])
        e = [s for s in res["stars"] if s["name"] == "*  61 Cyg"][0]
        self.assertIsNone(e["error"])
        for k in ("sp_type", "ly", "app_magnitude", "teff", "mass", "luminosity"):
            self.assertIsNone(e[k], k)


class BatchModeAZeroFluxTest(unittest.TestCase):
    """Behaviour change (a): planetary-systems-batch mode A resolves a zero-flux host (→ zero_planet), not unresolved."""

    def test_zero_flux_host_resolves(self):
        from core import exoplanet_batch as eb
        with mock.patch.object(eb, "compute_simbad_lookup", lambda n: dict(_NULL_SL)), \
             mock.patch.object(eb, "_fill_arm_rows", return_value=None):
            res = eb._run_mode_a(["61 Cyg"], "*", "default_flag=1", "core")
        cov = res.get("coverage", res)
        self.assertEqual(cov["unresolved"], [])
        self.assertEqual(cov["zero_planet"], [{"input": "61 Cyg", "resolved_host": "*  61 Cyg"}])
