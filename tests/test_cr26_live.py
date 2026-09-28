# tests/test_cr26_live.py — CR-26 per-star wind model: LIVE anchors (HEASARC + SIMBAD + Gaia + VizieR TIC).
#
# Opt-in: gated on SPACE_APP_RUN_LIVE=1 AND HEASARC + SIMBAD reachability (tests/_netcheck). query.py runs as a
# subprocess against the REAL DB (the GCNS blend partners need the populated gcns_stars table — skipped if it is
# empty), with the catalog cache OFF (SPACE_APP_CATALOG_CACHE=0) and the WB mass catalog on every --star call.
# Anchors: the WB spec §Acceptance A0/A2/A3/A4/A6 — [WB-ref] values at ±0.05 dex (Ṁ, log F_X) / ±6 % (walls);
# [lit]/[hand] at ±0.02 dex; the α-tagged standoffs exact.

import math
import os
import socket
import sqlite3
import unittest
from pathlib import Path

import pytest

from tests._netcheck import live_enabled
from tests._queryharness import make_env, run_query

REPO = Path(__file__).resolve().parent.parent
_DB = REPO / "data" / "space_app.db"
_WB_CAT = os.environ.get("SPACE_APP_WB_MASS_CATALOG") or (
    "/home/greg/Claude/scifiWorldBuilding-Claude/design-lab/star-system-analysis/deliverables/"
    "stellar-mass-catalog.json")
M = 2e-14


def _reachable():
    if not live_enabled():
        return False
    for host in ("heasarc.gsfc.nasa.gov", "simbad.cds.unistra.fr"):
        try:
            with socket.create_connection((host, 443), timeout=3.0):
                pass
        except OSError:
            return False
    return True


def _gcns_ok():
    try:
        con = sqlite3.connect(f"{_DB.resolve().as_uri()}?mode=ro", uri=True)
        try:
            return (con.execute("SELECT COUNT(*) FROM gcns_stars").fetchone()[0] or 0) > 0
        finally:
            con.close()
    except Exception:
        return False


_LIVE = _reachable() and _gcns_ok() and os.path.isfile(_WB_CAT)
_ENV = make_env(db_path=str(_DB), SPACE_APP_CATALOG_CACHE="0", HOME=os.environ.get("HOME", ""))


def _b(star, *extra):
    code, d, err = run_query("exclusion-boundary", "--star", star, "--star-mass-catalog", _WB_CAT,
                             "--gaia-timeout", "120", *extra, env=_ENV, timeout=600)
    assert code == 0 and d is not None, (star, code, err[-500:])
    return d


def _s(star, *extra):
    code, d, err = run_query("exclusion-system", "--star", star, "--star-mass-catalog", _WB_CAT,
                             "--gaia-timeout", "120", *extra, env=_ENV, timeout=900)
    assert code == 0 and d is not None, (star, code, err[-500:])
    return {c["id"]: c for z in d["zones"] for c in z["components"]}, d


def _dex(a, b):
    return abs(math.log10(a / b))


@pytest.mark.cr26_network
@unittest.skipUnless(_LIVE, "live CR-26 anchors: set SPACE_APP_RUN_LIVE=1 (HEASARC + SIMBAD reachable, GCNS populated)")
class Cr26LiveA3Test(unittest.TestCase):
    """A3 — the X-ray tier [WB-ref] (±0.05 dex; walls ±6 %)."""

    def _x(self, star, mdot, wall=None, flags=(), rung=None):
        d = _b(star)
        self.assertEqual(d["mass_loss_tier"], "xray", star)
        self.assertLess(_dex(d["mass_loss_msun_yr"] / M, mdot), 0.05, (star, d["mass_loss_msun_yr"] / M))
        if wall:
            self.assertLess(abs(d["wall_au"] / wall - 1), 0.06, star)
        for f in flags:
            self.assertIn(f, d["wind_model"]["flags"], star)
        if rung:
            self.assertEqual(d["wind_model"]["xray"]["rung"], rung, star)
        self.assertEqual(d["wind_model"]["xray"]["status"], "ok", star)
        return d

    def test_single_stars(self):
        self._x("Wolf 359", 0.1141, 2.03, ["extrapolated"])
        self._x("Ross 128", 0.1310, 2.17)
        self._x("sig Dra", 1.4661, 7.26)
        self._x("AD Leo", 3.5504, 11.31, ["active_bimodal"])
        self._x("iot Psc", 4.2722, 12.40, ["extrapolated"])
        # Ross 248: `exclusion-boundary --star` stops before CR-26 on a pre-existing "no V magnitude" regions gap —
        # the exclusion-system mass chain reaches it
        c, _ = _s("Ross 248")
        r = next(iter(c.values()))
        self.assertEqual(r["mass_loss_tier"], "xray")
        self.assertLess(_dex(r["mass_loss_msun_yr"] / M, 0.1654), 0.05)
        # VB 10 / DENIS J1048-3956 / LEHPM 3396 (A3/A4): no catalogued mass, no FLAME, no usable luminosity → the
        # pre-existing mass-resolution gap errors on both subcommands before CR-26 runs; their CR-26 values are
        # pinned offline (test_cr26_model A3OfflineTest / NonDetectionTest).

    def test_61_cyg_b_blend(self):
        d = self._x("61 Cyg B", 0.6290, 4.76, ["blended_source", "radius_pair_ambiguous"])
        self.assertTrue(any("61 Cyg A" in n for n in d["wind_model"]["xray"]["blended_source"]))

    def test_tiers_xray_blends(self):
        a = _b("alf Cen A")
        self.assertEqual(a["mass_loss_tier"], "measured")
        e = a["wind_model"]["tiers"]["xray"]
        self.assertLess(_dex(e["mass_loss_msun_yr"] / M, 0.9156), 0.05)
        self.assertTrue({"blended_source", "blend_mixed_class"} <= set(e["flags"]))
        c, _ = _s("70 Oph")          # `exclusion-boundary --star "70 Oph A"` hits the pre-existing no-V regions gap
        o = next(v for v in c.values() if (v["wind_model"].get("measured") or {}).get("row_key") == "70_oph_a")
        e = o["wind_model"]["tiers"]["xray"]
        self.assertLess(_dex(e["mass_loss_msun_yr"] / M, 2.7883), 0.05)
        self.assertIn("blended_source", e["flags"])


@pytest.mark.cr26_network
@unittest.skipUnless(_LIVE, "live CR-26 anchors")
class Cr26LiveA4Test(unittest.TestCase):
    """A4 — the non-detection path (the live limits are [WB-ref])."""

    def _n(self, star, mdot, flags=(), upper=False):
        c, _ = _s(star)              # the exclusion-system mass chain (ρ CrB has no SIMBAD V for the regions path)
        d = next(iter(c.values()))
        self.assertEqual(d["mass_loss_tier"], "xray_nondetection", star)
        self.assertLess(_dex(d["mass_loss_msun_yr"] / M, mdot), 0.05, (star, d["mass_loss_msun_yr"] / M))
        self.assertEqual(d["mass_loss_upper_limit"], upper, star)
        for f in ("xray_upper_limit",) + tuple(flags):
            self.assertIn(f, d["wind_model"]["flags"], star)
        return d

    def test_rows(self):
        self._n("HD 349726", 0.1116, ["xmm_floor_demoted"])
        self._n("rho CrB", 0.8587, ["xmm_guard_demoted"])
        self._n("HD 192310", 0.461)
        self._n("107 Psc", 0.355, upper=True)


@pytest.mark.cr26_network
@unittest.skipUnless(_LIVE, "live CR-26 anchors")
class Cr26LiveA2A0Test(unittest.TestCase):
    """A2 via --star + the A0 standoffs (α-tagged, exact) + A6 61 Cyg."""

    def test_eps_eri_both_subcommands(self):
        c, _ = _s("eps Eri", "--alpha", "0.4")
        e = next(v for v in c.values())
        self.assertEqual(e["mass_loss_tier"], "measured")
        self.assertAlmostEqual(e["r_ex_au"], 43.69, places=2)
        self.assertTrue(e["wall_band_wind_exceeds_standoff"])            # 43.82 > 43.69 (α 0.4)
        d = _b("eps Eri")
        self.assertAlmostEqual(d["r_ex_au"], 44.30, places=2)
        self.assertFalse(d["wall_band_wind_exceeds_standoff"])           # 43.82 < 44.30 (α 1/3)

    def test_measured_hosts(self):
        p = _b("del Pav")
        self.assertEqual((p["mass_loss_tier"], p["wind_speed_kms"]), ("measured", 400.0))
        self.assertAlmostEqual(p["wall_au"], 18.97, places=2)
        x = _b("Proxima Centauri")
        self.assertEqual(x["mass_loss_tier"], "measured")
        self.assertTrue(x["wall_is_upper_bound"])
        self.assertTrue(any("Wood upper limit" in n for n in x["wind_model"]["notes"]))       # T12
        ev = _b("EV Lac")
        e = ev["wind_model"]["tiers"]["xray"]
        self.assertLess(abs(e["log_fx"] - 7.155), 0.05)
        self.assertLess(_dex(e["mass_loss_msun_yr"] / M, 3.77), 0.05)

    def test_a0_standoffs(self):
        c, _ = _s("alpha Centauri", "--alpha", "0.4")
        rex = sorted(round(v["r_ex_au"], 4) for v in c.values() if v["r_ex_au"])
        self.assertEqual(rex, [45.7214, 48.9669])
        c, _ = _s("Proxima Centauri", "--alpha", "0.4")
        self.assertAlmostEqual(next(iter(c.values()))["r_ex_au"], 20.4824, places=4)
        c, _ = _s("EV Lac", "--alpha", "0.4")
        self.assertAlmostEqual(next(iter(c.values()))["r_ex_au"], 30.38, places=2)
        pr = _b("Procyon", "--alpha", "0.4")
        self.assertEqual((pr["mass_loss_tier"], pr["domain"], pr["wind_class"]),
                         ("noncoronal_row", "evolved", "subgiant_mild"))
        self.assertAlmostEqual(pr["r_ex_au"], 55.53, places=2)

    @unittest.skip("`61 Cyg` / `61 Cygni` have no SIMBAD system object (pre-existing identity behaviour); A6's 61 Cyg "
                   "composition is pinned offline (test_cr26_wiring.SystemAnchorsSubprocessTest.test_a6_61cyg_and_edges) "
                   "and 61 Cyg B's blend live in Cr26LiveA3Test")
    def test_a6_61_cyg(self):
        c, d = _s("61 Cyg", "--alpha", "0.4")
        by = {v["wind_model"]["measured"]["row_key"] if v["wind_model"].get("measured") else k: v
              for k, v in c.items()}
        a = by.get("61_cyg_a")
        self.assertIsNotNone(a)
        self.assertAlmostEqual(a["mass_loss_msun_yr"] / M, 0.5, places=6)
        b = [v for v in c.values() if v is not a][0]
        self.assertEqual(b["mass_loss_tier"], "xray")
        self.assertLess(_dex(b["mass_loss_msun_yr"] / M, 0.6290), 0.05)
        self.assertEqual(d["measured_system_edges"][0]["system_upper_edge_mdot_sun"], 9.6)


if __name__ == "__main__":
    unittest.main()
