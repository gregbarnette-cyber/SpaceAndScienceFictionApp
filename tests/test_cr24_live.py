# tests/test_cr24_live.py — CR-24 live anchors (opt-in: SPACE_APP_RUN_LIVE=1 + SIMBAD reachable). Subprocess runs
# (the conftest's in-process velocity defaults never apply). A1: the resolver against Wood 2021 Table 3 under the
# LIC vector — 24 of 24 within ±3 km/s and median |Δ| ≤ 0.7 (WB MSG 335); A2 / A3 / A5 spot checks.

import csv
import os
import statistics
import unittest

from tests._netcheck import live_enabled, simbad_reachable
from tests._queryharness import make_env, run_query

_ENV = make_env("cr24_live_throwaway.db", SPACE_APP_CATALOG_CACHE="0")
_CAT = os.environ.get("SPACE_APP_WB_MASS_CATALOG", "/home/greg/Claude/scifiWorldBuilding-Claude/design-lab/"
                      "star-system-analysis/deliverables/stellar-mass-catalog.json")
_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cr24",
                    "cr24_wood2021_vism.csv")
# A1's exclusions, with the contract's reasons (G-vector sight line; a visual binary; unexplained grade-A misses;
# a gated own RV)
_A1_EXCLUDED = {"alf_cen_a", "alf_cen_b", "prox_cen", "ksi_boo_a", "gj_588", "pi1_uma", "gj_860_a", "gj_860_b",
                "70_oph_b"}
# WB MSG 335: A1 scores the stars that reach the wall — 24 of 24. GJ 338 A / B and GJ 892 never reach V_ISM (a
# pre-existing star-regions error, CR-27.3's root cause); 70 Oph A is scored through exclusion-system (own record).
_A1_BLOCKED = {"gj_338_a", "gj_338_b", "gj_892"}
_A1_VIA_SYSTEM = {"70_oph_a"}


def _live():
    return live_enabled() and simbad_reachable()


def _cat_args():
    return ["--star-mass-catalog", _CAT] if os.path.exists(_CAT) else []


@unittest.skipUnless(_live(), "live SIMBAD (set SPACE_APP_RUN_LIVE=1)")
class Cr24LiveTest(unittest.TestCase):

    def _eb(self, *args):
        code, p, err = run_query("exclusion-boundary", "--alpha", "0.4", "--gaia-timeout", "120", *_cat_args(),
                                 *args, env=_ENV, timeout=600)
        self.assertIsNotNone(p, err[-1500:])
        return p

    def test_a1_resolver_against_wood_2021(self):
        with open(_CSV, encoding="utf-8") as fh:
            rows = [r for r in csv.DictReader(fh) if r["row_key"] not in _A1_EXCLUDED | _A1_BLOCKED]
        self.assertEqual(len(rows), 24)
        deltas, misses = [], []
        for r in rows:
            if r["row_key"] in _A1_VIA_SYSTEM:
                code, s, err = run_query("exclusion-system", "--star", r["simbad_main_id"], "--cloud", "LIC",
                                         "--alpha", "0.4", "--gaia-timeout", "120", *_cat_args(), env=_ENV,
                                         timeout=600)
                p = next((c for z in s["zones"] for c in z["components"]
                          if c["id"].split() == r["simbad_main_id"].split()), {"error": "component missing"})
            else:
                p = self._eb("--star", r["simbad_main_id"], "--cloud", "LIC")
            if "error" in p:
                misses.append((r["row_key"], p["error"][:80]))
                continue
            self.assertEqual((p["v_ism_provenance"], p["v_cloud_used"]), ("derived", "LIC"), r["row_key"])
            d = p["v_ism_kms"] - float(r["wood2021_vism_kms"])
            deltas.append(abs(d))
            if abs(d) > 3.0:
                misses.append((r["row_key"], round(d, 2)))
        self.assertEqual(misses, [])
        self.assertLessEqual(statistics.median(deltas), 0.7)

    def test_a3_ez_aqr_lower_bound(self):
        code, p, err = run_query("exclusion-system", "--star", "EZ Aquarii", "--alpha", "0.4", "--gaia-timeout", "120",
                                 *_cat_args(), env=_ENV, timeout=600)
        c = p["zones"][0]["components"][0]
        self.assertEqual(c["v_ism_provenance"], "derived_tangential_lower_bound")
        self.assertAlmostEqual(c["v_ism_kms"], 34.9, delta=1.0)
        self.assertAlmostEqual(c["wall_au"], 2.632, delta=0.01 * 2.632)
        self.assertEqual(c["verdict_marginal_reasons"], ["lower_bound_provisional"])

    def test_a3_70_oph_head_on_exclusion_boundary(self):
        p = self._eb("--star", "70 Oph")
        self.assertEqual((p["v_ism_kms"], p["v_ism_provenance"], p["wall_route"]), (37.0, "measured_row", "bow_shock"))
        self.assertAlmostEqual(p["wall_au"], 30.67, delta=0.01 * 30.67)
        self.assertAlmostEqual(p["v_ism_derived_kms"], 36.4, delta=1.0)

    def test_a5_derive_and_cloud_set(self):
        p = self._eb("--star", "Wolf 359")
        self.assertAlmostEqual(p["v_ism_kms"], 46.0, delta=1.0)
        self.assertEqual((p["wall_route"], p["clic_domain"], p["verdict_marginal_reasons"]),
                         ("bow_shock", "within_7pc", []))
        s = self._eb("--star", "Sirius")
        self.assertEqual(s["verdict_marginal_reasons"], ["cloud_set_branch"])
        h = self._eb("--star", "HD 69830")
        self.assertEqual(h["clic_domain"], "beyond_7pc")
        self.assertAlmostEqual(h["v_ism_kms"], 78.0, delta=1.0)


if __name__ == "__main__":
    unittest.main()
