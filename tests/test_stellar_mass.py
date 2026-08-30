# tests/test_stellar_mass.py — CR-11.2 stellar-mass provenance resolver + catalog.
#
# Offline, in-process. Covers the shared resolver (core.stellar_mass), the tier-2 catalog
# loader/matcher (core.stellar_mass_tables), and the offline dossier/compare-stars wiring
# (the Sol reference path + the loud bad-path error). The live dossier/compare-stars anchors
# (Sirius A / Vega / α Cen A/B against SIMBAD) are gated in test_query_stellar_mass_live.py.

import json
import os
import tempfile
import unittest

import core.stellar_mass as sm
import core.stellar_mass_tables as smt


class FlagTest(unittest.TestCase):
    def test_peculiar_from_sp_type(self):
        self.assertTrue(sm.peculiar_from_sp_type("A0mA1Va"))   # Sirius A (Am)
        self.assertTrue(sm.peculiar_from_sp_type("B9pSi"))     # Ap
        self.assertTrue(sm.peculiar_from_sp_type("kA5hF0mF2")) # Am notation
        self.assertTrue(sm.peculiar_from_sp_type("A0p"))
        self.assertFalse(sm.peculiar_from_sp_type("A0Va"))     # Vega — no Am/Ap code
        self.assertFalse(sm.peculiar_from_sp_type("G2V"))
        self.assertFalse(sm.peculiar_from_sp_type("K1V"))
        self.assertFalse(sm.peculiar_from_sp_type("F5V comp"))  # 'comp' must NOT trip it
        self.assertFalse(sm.peculiar_from_sp_type("DA2"))
        self.assertFalse(sm.peculiar_from_sp_type(""))
        self.assertFalse(sm.peculiar_from_sp_type(None))

    def test_hot_upper_ms(self):
        for sp in ("O5V", "B2V", "A0Va", "A0mA1Va", "A1V"):
            self.assertTrue(sm.hot_upper_ms_from_sp_type(sp), sp)
        for sp in ("F5V", "G2V", "K1V", "M3V", "DA2", "T5", "", None):
            self.assertFalse(sm.hot_upper_ms_from_sp_type(sp), sp)


class ResolveTest(unittest.TestCase):
    def setUp(self):
        self.seed = smt.load_mass_catalog(None)

    def test_seed_resolves_four_anchors_to_catalog(self):
        cases = {"* alf CMa": 2.063, "* alf Lyr": 2.135, "* alf Cen A": 1.079, "* alf Cen B": 0.909}
        for mid, mass in cases.items():
            r = sm.resolve_mass(9.9, main_id=mid, designations={"MAIN_ID": mid}, catalog=self.seed)
            self.assertEqual(r["mass_provenance"], "catalog", mid)
            self.assertAlmostEqual(r["mass_solar"], mass, places=3)
            self.assertFalse(r["massL_inversion_caution"], mid)  # catalog source → no caution

    def test_inversion_source_caution_sirius_and_vega(self):
        # Sirius A: peculiar + hot-MS → caution via both; no measured mass available
        r = sm.resolve_mass(2.59, sp_type="A0mA1Va", main_id="X", catalog=None)
        self.assertEqual(r["mass_provenance"], "ms_luminosity_inversion")
        self.assertTrue(r["massL_inversion_caution"])
        self.assertTrue(r["peculiar_star_flag"])
        self.assertEqual(r["mass_solar"], 2.59)   # never null — advisory, not a refusal
        # Vega: caution via the hot-MS path, peculiar flag stays False
        r = sm.resolve_mass(3.17, sp_type="A0Va", main_id="X", catalog=None)
        self.assertTrue(r["massL_inversion_caution"])
        self.assertFalse(r["peculiar_star_flag"])

    def test_well_behaved_no_false_caution(self):
        for sp, m in (("G2V", 1.1), ("K1V", 0.9)):
            r = sm.resolve_mass(m, sp_type=sp, main_id="X", catalog=None)
            self.assertEqual(r["mass_provenance"], "ms_luminosity_inversion")
            self.assertFalse(r["massL_inversion_caution"], sp)
            self.assertFalse(r["peculiar_star_flag"], sp)

    def test_precedence(self):
        # manual > catalog > flame > inversion
        r = sm.resolve_mass(2.5, sp_type="A0mA1Va", main_id="* alf CMa", catalog=self.seed,
                            manual_mass=2.063, flame_mass=1.9)
        self.assertEqual((r["mass_provenance"], r["mass_solar"]), ("manual", 2.063))
        r = sm.resolve_mass(2.5, sp_type="A0mA1Va", main_id="* alf CMa", catalog=self.seed, flame_mass=1.9)
        self.assertEqual(r["mass_provenance"], "catalog")
        r = sm.resolve_mass(2.5, sp_type="G8V", main_id="HD nope", catalog=self.seed, flame_mass=0.95)
        self.assertEqual((r["mass_provenance"], r["mass_solar"]), ("gaia_flame", 0.95))
        r = sm.resolve_mass(1.05, sp_type="G8V", main_id="HD nope", catalog=self.seed)
        self.assertEqual((r["mass_provenance"], r["mass_solar"]), ("ms_luminosity_inversion", 1.05))

    def test_non_ms_no_tier_is_null(self):
        r = sm.resolve_mass(None, sp_type="DA2", main_id="X", catalog=None)
        self.assertIsNone(r["mass_solar"])

    def test_downstream_outputs(self):
        o = sm.mass_dependent_outputs(1.0)
        self.assertAlmostEqual(o["luminosity_from_mass"], 1.0)
        self.assertAlmostEqual(o["main_seq_lifespan_yr"], 1e10)
        self.assertAlmostEqual(o["inner_limit_gravity_au"], 0.2)
        self.assertAlmostEqual(o["outer_limit_au"], 40.0)
        o2 = sm.mass_dependent_outputs(2.0)
        self.assertAlmostEqual(o2["luminosity_from_mass"], 2.0 ** 3.5)
        self.assertAlmostEqual(o2["inner_limit_gravity_au"], 0.4)
        self.assertEqual(sm.mass_dependent_outputs(None)["luminosity_from_mass"], None)


class CatalogTest(unittest.TestCase):
    def test_bad_path_loud_error(self):
        r = smt.load_mass_catalog("/nope/missing-catalog.json")
        self.assertIn("error", r)

    def test_no_stars_array_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"nope": 1}, f)
            path = f.name
        try:
            self.assertIn("error", smt.load_mass_catalog(path))
        finally:
            os.unlink(path)

    def test_replace_semantics_and_match(self):
        cat = {"stars": [{"main_id": "HD 999", "aliases": ["GJ 9"], "mass_solar": 1.5}]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(cat, f)
            path = f.name
        try:
            loaded = smt.load_mass_catalog(path)
            self.assertEqual(len(loaded["stars"]), 1)  # REPLACES the seed (no merge)
            self.assertIsNone(smt.match_mass(loaded, "* alf CMa", {"MAIN_ID": "* alf CMa"}))  # seed gone
            row = smt.match_mass(loaded, "HD 999", {"GJ": "GJ 9"})
            self.assertEqual(row["mass_solar"], 1.5)
        finally:
            os.unlink(path)

    def test_malformed_row_skipped(self):
        cat = {"stars": [{"main_id": "HD 1", "mass_solar": "oops"},   # non-numeric → skip
                         {"main_id": "HD 2", "mass_solar": 0.8}]}
        self.assertIsNone(smt.match_mass(cat, "HD 1"))
        self.assertEqual(smt.match_mass(cat, "HD 2")["mass_solar"], 0.8)

    def test_seed_has_four_verified_anchors(self):
        stars = smt.load_mass_catalog(None)["stars"]
        self.assertEqual(len(stars), 4)
        self.assertEqual({s["id"] for s in stars},
                         {"Sirius A", "Vega", "alpha Centauri A", "alpha Centauri B"})


class DossierWiringOfflineTest(unittest.TestCase):
    """The offline (Sol) dossier + the loud bad-path error — no network."""

    def test_sol_dossier_carries_mass_block(self):
        from core.report import build_system_dossier
        r = build_system_dossier("Sol", sections=["regions"], fmt="json")
        mb = r["data"]["regions"]["mass"]
        self.assertEqual(mb["mass_provenance"], "ms_luminosity_inversion")   # G2V, no measured seed
        self.assertFalse(mb["massL_inversion_caution"])
        self.assertFalse(mb["peculiar_star_flag"])
        self.assertIsNotNone(mb["mass_solar"])

    def test_sol_dossier_manual_mass_override(self):
        from core.report import build_system_dossier
        r = build_system_dossier("Sol", sections=["regions"], fmt="json", mass_solar=1.0)
        mb = r["data"]["regions"]["mass"]
        self.assertEqual((mb["mass_provenance"], mb["mass_solar"]), ("manual", 1.0))
        # downstream recomputes from the preferred mass
        st = r["data"]["regions"]["stellar"]
        self.assertAlmostEqual(st["stellar_mass"], 1.0)
        self.assertAlmostEqual(st["luminosity_from_mass"], 1.0)

    def test_dossier_bad_catalog_path_loud(self):
        from core.report import build_system_dossier
        r = build_system_dossier("Sol", star_mass_catalog="/nope/x.json")
        self.assertIn("error", r)

    def test_compare_stars_bad_catalog_path_loud(self):
        from core.databases import compare_stars
        r = compare_stars(["Sol", "Sun"], star_mass_catalog="/nope/x.json")
        self.assertIn("error", r)

    def test_compare_stars_sol_entry_mass_block(self):
        from core.databases import _sol_compare_entry
        e = _sol_compare_entry(smt.load_mass_catalog(None))
        self.assertEqual(e["mass_provenance"], "ms_luminosity_inversion")
        self.assertEqual(e["mass_solar"], 1.0)
        self.assertFalse(e["massL_inversion_caution"])

    def test_review2_radius_recomputed_from_preferred_mass(self):
        # WB decision B: a catalog Sol mass (1.2, ≠ the ~1.022 inversion) recomputes stellar_radius,
        # calculated_luminosity, and the Calculated-HZ column from it — mass ↔ radius coherent, no
        # disclosure field. The bcLuminosity-based primary HZ (hz_inner/outer) stays unchanged.
        from core.report import build_system_dossier
        base = build_system_dossier("Sol", sections=["regions"], fmt="json")
        base_st = base["data"]["regions"]["stellar"]
        base_hz_inner = base["data"]["regions"]["system_regions"]["hz_inner_au"]
        cat = {"stars": [{"main_id": "Sol", "aliases": ["Sun"], "mass_solar": 1.2}]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(cat, f)
            path = f.name
        try:
            r = build_system_dossier("Sol", sections=["regions"], fmt="json", star_mass_catalog=path)
            st = r["data"]["regions"]["stellar"]
            mb = r["data"]["regions"]["mass"]
            self.assertEqual((mb["mass_provenance"], mb["mass_solar"]), ("catalog", 1.2))
            self.assertNotIn("stellar_radius_basis", mb)          # disclosure dropped under B
            self.assertAlmostEqual(st["stellar_mass"], 1.2)
            self.assertAlmostEqual(st["stellar_radius"], 1.2 ** 0.57)   # radius ↔ preferred mass (coherent)
            self.assertAlmostEqual(st["calculated_luminosity"],
                                   (1.2 ** 0.57) ** 2 * (st["teff"] / 5778.0) ** 4)
            self.assertNotAlmostEqual(st["stellar_radius"], base_st["stellar_radius"])  # actually moved
            # primary bcLuminosity-based HZ is untouched
            self.assertAlmostEqual(r["data"]["regions"]["system_regions"]["hz_inner_au"], base_hz_inner)
        finally:
            os.unlink(path)

    def test_review2_inversion_source_radius_matches_mass(self):
        # Plain inversion source → radius already derived from the same (inversion) mass; no disclosure,
        # and stellar_radius = stellar_mass^0.57 (coherent, byte-unchanged from pre-CR-11.2).
        from core.report import build_system_dossier
        reg = build_system_dossier("Sol", sections=["regions"], fmt="json")["data"]["regions"]
        self.assertNotIn("stellar_radius_basis", reg["mass"])           # disclosure never appears under B
        st = reg["stellar"]
        self.assertAlmostEqual(st["stellar_radius"], st["stellar_mass"] ** 0.57)


class CatalogRowParamTest(unittest.TestCase):
    """Review #4 — resolve_mass honors a pre-matched catalog_row (no double match_mass scan)."""

    def test_explicit_row_used_and_none_forces_miss(self):
        seed = smt.load_mass_catalog(None)
        row = smt.match_mass(seed, "* alf CMa", {"MAIN_ID": "* alf CMa"})
        r = sm.resolve_mass(9.9, sp_type="A0mA1Va", main_id="* alf CMa", catalog=seed, catalog_row=row)
        self.assertEqual((r["mass_provenance"], r["mass_solar"]), ("catalog", 2.063))
        # explicit None = a known miss → skip the catalog tier even though the catalog contains the star
        r2 = sm.resolve_mass(9.9, sp_type="A0mA1Va", main_id="* alf CMa", catalog=seed, catalog_row=None)
        self.assertEqual(r2["mass_provenance"], "ms_luminosity_inversion")


class Cr15Test(unittest.TestCase):
    """CR-15.3 shared Kepler-III SMA helper + CR-15.2 empty-main_id fallback consistency."""

    def test_recompute_sma_kepler3(self):
        # a ∝ M_tot^(1/3): doubling M_tot scales a by 2^(1/3).
        self.assertAlmostEqual(sm.recompute_sma_kepler3(10.0, 1.0, 2.0), 10.0 * 2.0 ** (1.0 / 3.0))
        self.assertEqual(sm.recompute_sma_kepler3(10.0, 2.0, 2.0), 10.0)      # preferred == selected → no-op
        # truthiness guard (Reviewer-2): None/0 sma passes through, no crash
        self.assertIsNone(sm.recompute_sma_kepler3(None, 1.0, 2.0))
        self.assertEqual(sm.recompute_sma_kepler3(0.0, 1.0, 2.0), 0.0)
        self.assertEqual(sm.recompute_sma_kepler3(10.0, 0.0, 2.0), 10.0)      # zero mtot → no-op

    def test_cr152_empty_main_id_fallback_uses_system_name_b(self):
        # CR-15.2: on empty main_id, resolve_binary_components derives comp_id "{system_name} B" — matching
        # exclusion_system._resolve_system_from_star's L533 `f"{star} B"` (unchanged) → identical component-B id.
        from unittest import mock
        sel = {"m1_solar": 1.0, "m2_solar": 0.5, "mass_prov_a": "binary_orbit_m1",
               "mass_prov_b": "binary_orbit_m2", "notes": []}
        seen = []

        def fake_lookup(name):
            seen.append(name)
            return {"error": "not found"}

        with mock.patch("core.databases.compute_simbad_lookup", side_effect=fake_lookup):
            m1, pa, m2, pb, notes = sm.resolve_binary_components(
                {"main_id": "", "sp_type": None, "designations": {}}, sel, None, system_name="Foo")
        self.assertIn("Foo B", seen)          # the B fallback used "{system_name} B", not None (skip)
        self.assertEqual(m2, 0.5)             # bad lookup + no catalog → B falls to the orbit split

    def test_cr152_cross_path_empty_main_id_derives_same_comp_b(self):
        # WB CR-15.2 acceptance: on empty main_id, resolve_binary_components AND
        # exclusion_system._resolve_system_from_star derive the IDENTICAL component-B id ("{name} B") for
        # the same input → the same B mass. (Edge case — not CLI-triggerable; unit-level parity.)
        from unittest import mock
        import core.exclusion_system as ex
        sel = {"m1_solar": 1.0, "m2_solar": 0.5, "mass_prov_a": "binary_orbit_m1",
               "mass_prov_b": "binary_orbit_m2", "sma_au": 23.0, "ecc": 0.5, "mass_basis": "sb2 ratio",
               "notes": [], "ecc_assumed": False}
        seen_rbc, seen_ex = [], []
        with mock.patch("core.databases.compute_simbad_lookup",
                        side_effect=lambda n: (seen_rbc.append(n) or {"error": "x"})):
            r = sm.resolve_binary_components({"main_id": "", "sp_type": "G2V", "designations": {}},
                                             sel, None, system_name="Foo")

        def lk_ex(n):
            seen_ex.append(n)
            return ({"main_id": "", "otype": None, "sp_type": "G2V", "designations": {}}
                    if n == "Foo" else {"error": "x"})
        with mock.patch("core.databases.compute_simbad_lookup", side_effect=lk_ex), \
                mock.patch("core.binary.binary_orbit", return_value={"solutions": [{"s": 1}]}), \
                mock.patch.object(ex, "_select_orbit_masses", return_value=(sel, None)):
            try:
                ex._resolve_system_from_star("Foo", None)   # comp-B id is derived at L533-534 (before
            except Exception:                                # any downstream composition) — that's all we assert
                pass
        self.assertIn("Foo B", seen_rbc)      # resolve_binary_components fallback
        self.assertIn("Foo B", seen_ex)       # exclusion fallback — SAME comp-B id (cross-path parity)
        self.assertEqual(r[2], 0.5)           # both fall to the orbit split (0.5) on the bad B lookup


if __name__ == "__main__":
    unittest.main()
