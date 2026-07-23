"""tests/test_catalog_live.py — LIVE-network gated tests for the Phase AM catalog-access tier.

Gated on CDS / ESA reachability (like the existing *_live.py suite), so a checkout with no network
skips cleanly. Every expected value was fetched live from the authority 2026-07-23; tolerances are
loose (catalogue drift on counts, precision on periods/masses). Each anchor is independence-labelled
per skill v0.1.32 — a green run against a *different* product than the one under test.

Test IDs map to the spec §6.2 table (T1–T8). Gateway anchors (T6, T8) live here; the binary-orbit /
census anchors (T1–T5) and gaia-astrophysical (T7) are added with those phases.
"""

import unittest

from tests._netcheck import cds_reachable, esa_gaia_reachable, reachable

_CDS = cds_reachable()
_GAIA = esa_gaia_reachable()
_HEASARC = reachable("heasarc.gsfc.nasa.gov")


@unittest.skipUnless(_CDS, "CDS (VizieR) unreachable")
class VizierGatewayLiveTest(unittest.TestCase):
    def test_T6_ritter_kolb_cv_reachable(self):
        # [catalogue] Ritter & Kolb CVs — GK Per Orb.Per = 1.996803 d (the §7.3 CV population).
        from core import catalog
        r = catalog.vizier_query(catalog="B/cb/cbdata",
                                 filters=["Name = GK Per"], row_limit=5)
        self.assertNotIn("error", r)
        self.assertGreaterEqual(r["count"], 1)
        row = r["rows"][0]
        self.assertEqual(row.get("Name"), "GK Per")
        self.assertAlmostEqual(row.get("Orb.Per"), 1.996803, places=5)

    def test_sb9_main_pull(self):
        from core import catalog
        r = catalog.vizier_query(catalog="B/sb9/main", row_limit=5)
        self.assertNotIn("error", r)
        self.assertEqual(r["count"], 5)
        self.assertTrue(r["truncated"])          # 5 rows == row_limit → flagged truncated

    def test_bad_catalog_returns_error_shape(self):
        from core import catalog
        r = catalog.vizier_query(catalog="Z/nonexistent/table", row_limit=1)
        # Either an explicit error or an empty result — never an exception / bad shape.
        self.assertTrue("error" in r or r.get("count") == 0)


@unittest.skipUnless(_CDS, "CDS (X-Match) unreachable")
class XMatchLiveTest(unittest.TestCase):
    def test_T8_capella_to_hipparcos(self):
        # [independent-tool] CDS X-Match — Capella → HIP 24608, Plx 76.2 mas, sep < 1".
        from core import catalog
        r = catalog.xmatch_query(
            [{"ra": 79.1723, "dec": 45.9980, "myid": "capella"}],
            cat2="vizier:I/311/hip2", max_arcsec=5.0)
        self.assertNotIn("error", r)
        self.assertGreaterEqual(r["count"], 1)
        row = r["rows"][0]
        self.assertEqual(int(row["HIP"]), 24608)
        self.assertAlmostEqual(float(row["Plx"]), 76.2, delta=0.5)
        self.assertLess(float(row["angDist"]), 1.0)


@unittest.skipUnless(_GAIA, "ESA Gaia TAP unreachable")
class GaiaGatewayLiveTest(unittest.TestCase):
    def test_by_id_sync(self):
        from core import catalog
        r = catalog.gaia_tap(
            adql="SELECT source_id, parallax FROM gaiadr3.gaia_source "
                 "WHERE source_id=425040000962559616")
        self.assertNotIn("error", r)
        self.assertEqual(r["count"], 1)
        self.assertGreater(r["rows"][0]["parallax"], 100.0)   # η Cas is nearby (~168 mas)

    def test_structured_mode_builds_adql(self):
        from core import catalog
        r = catalog.gaia_tap(table="gaiadr3.gaia_source",
                             columns=["source_id", "parallax"],
                             where="source_id=425040000962559616")
        self.assertNotIn("error", r)
        self.assertEqual(r["count"], 1)


def _by_source(result, source_prefix):
    return [s for s in result.get("solutions", [])
            if str(s.get("source", "")).startswith(source_prefix)]


@unittest.skipUnless(_CDS and _GAIA, "CDS + ESA Gaia both required for binary-orbit")
class BinaryOrbitLiveTest(unittest.TestCase):
    def test_T1_delta_trianguli_sb9(self):
        # [catalogue] SB9 — δ Tri P = 10.020 d, grade 4 (Abt & Levy 1976); class stellar.
        from core import binary
        r = binary.binary_orbit(star="delta Trianguli")
        self.assertNotIn("error", r)
        self.assertIn("gaia-nss:two_body_orbit", r["route_tried"])   # route attempted
        sb9 = _by_source(r, "sb9")
        self.assertTrue(sb9, "expected an SB9 solution for delta Tri")
        gr4 = [s for s in sb9 if s.get("grade") == 4]
        self.assertTrue(gr4)
        self.assertAlmostEqual(gr4[0]["period_d"], 10.020, delta=0.01)
        self.assertEqual(gr4[0]["companion"]["class"], "stellar")

    def test_T2_gj876_planet_filter(self):
        # [literature] GJ 876 b — the 61.36 d NSS solution must classify as planet, not binary.
        from core import binary
        r = binary.binary_orbit(star="GJ 876")
        self.assertNotIn("error", r)
        nss = _by_source(r, "gaia-nss")
        self.assertTrue(nss, "expected a Gaia NSS solution for GJ 876")
        s = min(nss, key=lambda x: abs((x.get("period_d") or 0) - 61.36))
        self.assertAlmostEqual(s["period_d"], 61.36, delta=0.2)
        self.assertEqual(s["companion"]["class"], "planet")
        self.assertLess(s["companion"]["m2_mjup"], 13.0)             # sub-planetary boundary

    def test_T3_hd110833_method_correctness(self):
        # [independent-tool] the a₀→mass method → ~0.16 M☉, matching Gaia binary_masses.m2=0.171.
        from core import binary
        r = binary.binary_orbit(star="HD 110833")
        self.assertNotIn("error", r)
        astrom = [s for s in _by_source(r, "gaia-nss")
                  if (s.get("companion") or {}).get("method") == "astrom"]
        self.assertTrue(astrom, "expected an astrometric NSS solution for HD 110833")
        comp = astrom[0]["companion"]
        m2 = comp["m2_solar"]
        self.assertAlmostEqual(m2, 0.16, delta=0.03)                 # within ~ Gaia's 0.171
        self.assertEqual(comp["class"], "stellar")
        # §3.3 fix #3 — the independent Gaia binary_masses cross-check is attached (m2=0.171).
        bm = comp.get("binary_masses")
        self.assertIsNotNone(bm, "expected the Gaia binary_masses cross-check block")
        self.assertAlmostEqual(bm["m2_solar"], 0.171, delta=0.01)
        self.assertLess(bm["agreement_pct"], 15.0)                   # our method agrees to <15 %

    def test_T4_capella_bright_route(self):
        # [catalogue] SB9 — Capella 104.02 d grade 5, distance 42.8 ly; Gaia NSS saturates (skipped).
        from core import binary
        r = binary.binary_orbit(star="Capella")
        self.assertNotIn("error", r)
        self.assertAlmostEqual(r["identity"]["distance_ly"], 42.8, delta=1.5)
        sb9 = _by_source(r, "sb9")
        gr5 = [s for s in sb9 if s.get("grade") == 5]
        self.assertTrue(gr5)
        self.assertAlmostEqual(gr5[0]["period_d"], 104.02, delta=0.05)
        self.assertEqual(gr5[0]["companion"]["class"], "stellar")    # SB2 double-lined

    def test_wds_rows_are_deduped(self):
        # WDS carries one row per observation epoch; the orchestrator must collapse duplicate
        # epochs to one entry per (WDS id, component). Distinct components (Capella's Aa,Ab / AB /
        # AC …) are legitimately kept — the invariant is that no (id, component) key repeats.
        from core import binary
        r = binary.binary_orbit(star="Capella")
        wds = _by_source(r, "wds")
        keys = [(s.get("primary_ref"), s.get("component")) for s in wds]
        self.assertEqual(len(keys), len(set(keys)), "duplicate (WDS id, component) epoch rows leaked")


@unittest.skipUnless(_CDS and _GAIA, "CDS + ESA Gaia both required for the census")
class CloseBinaryCensusLiveTest(unittest.TestCase):
    # Slow (async NSS + full SB9 pull + X-Match). T5's exact §11 count lives in the sister repo;
    # here the assertions are tolerant (structure + the planet-filter behaviour that must hold).
    def test_T5_census_65ly_365d(self):
        from core import binary
        r = binary.close_binary_census(dist_max_ly=65, period_max_d=365)
        self.assertNotIn("error", r)
        self.assertGreater(r["count"], 30)                    # ~50 new + ~13 known, tolerant
        self.assertGreater(r["counts_by_class"].get("stellar", 0), 20)
        self.assertIn("brown-dwarf", r["counts_by_class"])
        # GJ 876 (15 ly, 61 d NSS "orbit" = the planet) must be excluded, not counted as a binary.
        gj = [e for e in r["excluded_planets"]
              if e.get("source_id") == "2603090003484152064"]
        self.assertTrue(gj, "GJ 876 b must be filtered into excluded_planets")
        self.assertTrue(r["coverage"]["notes"])               # honest coverage block, never empty

    def test_census_validates_inputs(self):
        from core import binary
        self.assertIn("error", binary.close_binary_census(dist_max_ly=0, period_max_d=365))
        self.assertIn("error", binary.close_binary_census(dist_max_ly=65, period_max_d=-1))


@unittest.skipUnless(_GAIA, "ESA Gaia TAP unreachable")
class GaiaAstrophysicalLiveTest(unittest.TestCase):
    def test_T7_eta_cas_a_flame(self):
        # [catalogue] Gaia astrophysical_parameters — η Cas A FLAME age 10.06 [8.90–11.19] Gyr,
        # mass 0.96, radius 1.14, Teff 5726 K (source 425040000962559616).
        from core import catalog
        r = catalog.gaia_astrophysical(source_id=425040000962559616)
        self.assertNotIn("error", r)
        p = r["parameters"]
        self.assertAlmostEqual(p["teff_gspphot"], 5726, delta=30)
        self.assertAlmostEqual(p["mass_flame"], 0.96, delta=0.05)
        self.assertAlmostEqual(p["radius_flame"], 1.14, delta=0.05)
        self.assertAlmostEqual(p["age_flame"], 10.06, delta=0.3)
        self.assertIn("age_flame", r["caveats"])              # model-dependence caveat always emitted


@unittest.skipUnless(_HEASARC, "HEASARC unreachable")
class HeasarcGatewayLiveTest(unittest.TestCase):
    def test_cone_smoke(self):
        from core import catalog
        # RASS bright-source cone around Capella — just assert a well-formed, non-error result.
        r = catalog.heasarc_query(catalog="rassbsc", cone="79.1723 45.998 0.5")
        self.assertNotIn("error", r)
        self.assertIn("rows", r)


if __name__ == "__main__":
    unittest.main()
