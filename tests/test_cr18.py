"""CR-18 — bound-companion detection via the GCNS pairing layer + neighbourhood transverse separation.

Offline. The mock-based classes exercise the multiplicity / dossier logic by patching
``compute_gcns_system`` / ``compute_simbad_lookup`` / ``binary_orbit``; the within-star classes seed a
minimal GCNS + star_systems fixture into a tmp DB (the ``test_gcns.py`` pattern). The exact live
anchor values (ζ¹ Ret, GJ 9588) are re-gated by WB on the sister venv and pinned in the *_live files.
"""
import math
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

import core.db as db
import core.binary as binary
import core.report as report
import core.shared as shared
import core.databases as databases
import core.calculators as calculators


# Real 19-digit Gaia source_ids — the multiplicity/dossier path resolves the queried star's id via
# binary.gaia_source_id_from_designations, whose _GAIA_ID_RE requires ≥5 digits, so toy ids won't parse.
_G1 = 4722111590409480064   # * zet01 Ret
_G2 = 4722135642226902656   # * zet02 Ret
_DESIG1 = {"Gaia EDR3": f"Gaia DR3 {_G1}"}

# A synthetic ζ Ret system (a clean 2-component BOUND pair, no orbit) reused by several classes.
_ZET = {"system": {"n_components": 2,
        "pairs": [{"source_id1": _G1, "source_id2": _G2, "proj_sep_au": 3721.8,
                   "separation_arcsec": 309.1, "bound": True, "bin": True}],
        "members": [{"gaia_source_id": _G1, "star_name": "* zet01 Ret"},
                    {"gaia_source_id": _G2, "star_name": "* zet02 Ret"}]}}


class Cr18MathTest(unittest.TestCase):
    """The shared pure-math helpers (no DB)."""

    def test_transverse_arcsec_times_pc_is_au(self):
        # 5.9173" along RA at dec 0, ×23.0989 pc ≈ 136.7 AU (the GJ 9588 pair).
        au = shared.transverse_separation_au(0.0, 0.0, 5.9173 / 3600.0, 0.0, 23.0989)
        self.assertAlmostEqual(au, 5.9173 * 23.0989, places=1)

    def test_transverse_none_on_missing_input(self):
        self.assertIsNone(shared.transverse_separation_au(1, 2, 3, 4, None))

    def test_radial_dominated_true_when_within_errors(self):
        # radial ~0.29 ly ≫ transverse ~0.002 ly, Δϖ within combined 1σ → noise-dominated.
        self.assertTrue(shared.radial_parallax_dominated(23.10, 23.01, 136.7,
                                                         43.259, 43.450, 0.356, 0.131))

    def test_radial_not_dominated_when_transverse_larger(self):
        self.assertFalse(shared.radial_parallax_dominated(23.10, 23.10, 1e6))

    def test_radial_base_rule_without_errors(self):
        self.assertTrue(shared.radial_parallax_dominated(23.10, 23.01, 136.7))

    def test_radial_real_offset_beyond_errors_not_flagged(self):
        # Δϖ 5 mas ≫ combined error → a genuine radial separation, not noise.
        self.assertFalse(shared.radial_parallax_dominated(23.10, 40.0, 136.7,
                                                          43.0, 25.0, 0.2, 0.2))

    def test_radial_none_on_missing(self):
        self.assertIsNone(shared.radial_parallax_dominated(None, 23.0, 136.7))

    def test_neighbor_separation_bound_pair(self):
        out = shared.gcns_neighbor_separation(0, 0, 23.1, 0, 0, 23.0,
                                              {"bound": True, "proj_sep_au": 136.7, "separation_arcsec": 5.9})
        self.assertEqual(out["transverse_sep_au"], 136.7)
        self.assertTrue(out["bound"])
        self.assertTrue(out["is_bound_companion"])
        self.assertEqual(out["sep_method"], "gcns_proj_sep")

    def test_neighbor_separation_optical_is_not_a_companion(self):
        out = shared.gcns_neighbor_separation(0, 0, 23.1, 0, 0, 23.0,
                                              {"bound": False, "proj_sep_au": 900.0, "separation_arcsec": 40})
        self.assertFalse(out["bound"])
        self.assertFalse(out["is_bound_companion"])       # optical → not a bound companion

    def test_neighbor_separation_not_co_systemed_computes_transverse(self):
        out = shared.gcns_neighbor_separation(100.0, 20.0, 23.1, 100.0, 20.1, 23.0, None)
        self.assertIsNone(out["bound"])                   # tri-state: unknown, NOT unbound
        self.assertFalse(out["is_bound_companion"])
        self.assertEqual(out["sep_method"], "computed_angular")
        self.assertIsNotNone(out["transverse_sep_au"])    # F4: computed even off-GCNS


class Cr18HelperTest(unittest.TestCase):
    """binary.gcns_bound_companions — incident-only, guards, name fallback."""

    def test_incident_pairs_only(self):
        # A 3-star chain 111-222 and 222-333: querying 111 emits ONLY 222, not the non-incident 333.
        sysd = {"system": {"n_components": 3, "pairs": [
            {"source_id1": 111, "source_id2": 222, "proj_sep_au": 100, "separation_arcsec": 1, "bound": True},
            {"source_id1": 222, "source_id2": 333, "proj_sep_au": 200, "separation_arcsec": 2, "bound": True}],
            "members": [{"gaia_source_id": 111, "star_name": "A"},
                        {"gaia_source_id": 222, "star_name": "B"},
                        {"gaia_source_id": 333, "star_name": "C"}]}}
        with mock.patch("core.databases.compute_gcns_system", return_value=sysd):
            n, comps = binary.gcns_bound_companions("111")
        self.assertEqual(n, 3)
        self.assertEqual([c["source_id"] for c in comps], [222])
        self.assertEqual(comps[0]["basis"], "gcns_cpm")
        self.assertTrue(comps[0]["bound"])

    def test_no_gaia_id(self):
        self.assertEqual(binary.gcns_bound_companions(None), (None, []))

    def test_bad_id_guarded(self):
        self.assertEqual(binary.gcns_bound_companions("not-an-int"), (None, []))

    def test_not_in_a_system(self):
        with mock.patch("core.databases.compute_gcns_system", return_value={"error": "no system"}):
            self.assertEqual(binary.gcns_bound_companions("111"), (None, []))

    def test_star_name_fallback_to_source_id(self):
        sysd = {"system": {"n_components": 2, "pairs": [
            {"source_id1": 1, "source_id2": 2, "proj_sep_au": 5, "separation_arcsec": 1, "bound": True}],
            "members": [{"gaia_source_id": 1, "star_name": "A"}]}}   # member 2 uncross-matched
        with mock.patch("core.databases.compute_gcns_system", return_value=sysd):
            _, comps = binary.gcns_bound_companions("1")
        self.assertEqual(comps[0]["star_name"], "2")


class Cr18MultiplicityTest(unittest.TestCase):
    """The `multiplicity` subcommand (binary.multiplicity_summary)."""

    def test_zet_ret_gcns_cpm_component(self):
        with mock.patch("core.databases.compute_simbad_lookup",
                        return_value={"main_id": "* zet01 Ret", "multiplicity": None,
                                      "designations": _DESIG1}), \
             mock.patch("core.binary.binary_orbit",
                        return_value={"solutions": [], "route_tried": ["nss", "sb9", "wds"], "note": "no orbit"}), \
             mock.patch("core.databases.compute_gcns_system", return_value=_ZET):
            out = binary.multiplicity_summary(star="* zet01 Ret")
        self.assertTrue(out["is_multiple"])
        self.assertEqual(out.get("multiplicity_basis"), "gcns_cpm")
        gc = [c for c in out["components"] if c["basis"] == "gcns_cpm"]
        self.assertEqual(len(gc), 1)
        self.assertTrue(gc[0]["bound"])
        self.assertEqual(gc[0]["proj_sep_au"], 3721.8)
        self.assertEqual(gc[0]["star_name"], "* zet02 Ret")
        self.assertEqual(gc[0]["source_id"], _G2)         # F4: unified fields on both surfaces
        self.assertNotIn("visual", [c["basis"] for c in out["components"]])

    def test_eps_eri_visual_basis_untouched(self):
        # ε Eri: a WDS visual pair, gcns_n null → no relabel, no bound field, no gcns_cpm.
        with mock.patch("core.databases.compute_simbad_lookup",
                        return_value={"main_id": "* eps Eri",
                                      "multiplicity": {"is_multiple": True, "basis": "visual", "otype": "BY*"},
                                      "designations": {"Gaia EDR3": "Gaia DR3 5164707970261890560"}}), \
             mock.patch("core.binary.binary_orbit",
                        return_value={"solutions": [{"source": "wds", "companion": {}}], "route_tried": ["wds"]}), \
             mock.patch("core.databases.compute_gcns_system", return_value={"error": "not resolved"}):
            out = binary.multiplicity_summary(star="* eps Eri")
        bases = [c["basis"] for c in out["components"]]
        self.assertIn("visual", bases)
        self.assertNotIn("gcns_cpm", bases)
        self.assertIsNone(out.get("multiplicity_basis"))


class Cr18DedupTest(unittest.TestCase):
    """WB MSG 197 — a companion confirmed by BOTH an orbit route and the GCNS layer is ONE entry."""

    def _gcns(self, bound=True, proj=108.0):
        return {"system": {"n_components": 2,
                "pairs": [{"source_id1": _G1, "source_id2": _G2, "proj_sep_au": proj,
                           "separation_arcsec": 5.0, "bound": bound}],
                "members": [{"gaia_source_id": _G1, "star_name": "A"},
                            {"gaia_source_id": _G2, "star_name": "B"}]}}

    def _run(self, orbit):
        with mock.patch("core.databases.compute_simbad_lookup",
                        return_value={"main_id": "A", "multiplicity": None, "designations": _DESIG1}), \
             mock.patch("core.binary.binary_orbit", return_value=orbit), \
             mock.patch("core.databases.compute_gcns_system", return_value=self._gcns()):
            return binary.multiplicity_summary(star="A")

    def test_dual_confirmed_visual_merges_to_one_entry(self):
        orbit = {"solutions": [{"source": "wds", "companion": {}, "separation_au": 110.0}],
                 "route_tried": ["wds"]}
        out = self._run(orbit)
        self.assertEqual(len(out["components"]), 1)           # not double-listed (61 Cyg-style)
        c = out["components"][0]
        self.assertEqual(c["basis"], "visual")                # keeps the orbit basis (carries a/e/mass)
        self.assertTrue(c["bound"])                           # GCNS signal merged onto the same entry
        self.assertTrue(c["gcns_confirmed"])
        self.assertEqual(c["proj_sep_au"], 108.0)
        self.assertEqual(c["sep_au"], 110.0)                  # orbit separation retained
        self.assertEqual(c["source_id"], _G2)                 # GCNS-resolved identity added
        self.assertEqual(c["star_name"], "B")

    def test_close_sb_plus_wide_gcns_stay_two_entries(self):
        # An SB (unresolved close pair) is a DIFFERENT companion than a wide Gaia-resolved one → not merged.
        orbit = {"solutions": [{"source": "sb9", "companion": {"method": "SB2"}}], "route_tried": ["sb9"]}
        out = self._run(orbit)
        self.assertEqual(sorted(c["basis"] for c in out["components"]), ["SB2", "gcns_cpm"])
        sb = [c for c in out["components"] if c["basis"] == "SB2"][0]
        self.assertIsNone(sb.get("gcns_confirmed"))           # the close pair is untouched
        gc = [c for c in out["components"] if c["basis"] == "gcns_cpm"][0]
        self.assertTrue(gc["bound"])

    def test_wide_gcns_not_merged_onto_inconsistent_close_visual(self):
        # DR-1: a close resolved inner pair (sep 5 AU) + a distinct wide GCNS bound companion (5000 AU)
        # must stay TWO entries — the separations are a factor 1000 apart, not the same companion.
        with mock.patch("core.databases.compute_simbad_lookup",
                        return_value={"main_id": "A", "multiplicity": None, "designations": _DESIG1}), \
             mock.patch("core.binary.binary_orbit",
                        return_value={"solutions": [{"source": "wds", "companion": {}, "separation_au": 5.0}],
                                      "route_tried": ["wds"]}), \
             mock.patch("core.databases.compute_gcns_system", return_value=self._gcns(proj=5000.0)):
            out = binary.multiplicity_summary(star="A")
        self.assertEqual(sorted(c["basis"] for c in out["components"]), ["gcns_cpm", "visual"])
        vis = [c for c in out["components"] if c["basis"] == "visual"][0]
        self.assertIsNone(vis.get("gcns_confirmed"))          # the close pair kept its own separation
        self.assertEqual(vis["sep_au"], 5.0)


class Cr18DossierTest(unittest.TestCase):
    """The dossier multiplicity section (report._multiplicity_data_star / _augment_gcns_multiplicity)."""

    def _run(self, simbad, orbit, gcns):
        with mock.patch("core.binary.binary_orbit", return_value=orbit), \
             mock.patch("core.databases.compute_gcns_system", return_value=gcns):
            return report._multiplicity_data_star(simbad, simbad.get("main_id") or "star")

    def test_zet_ret_verdict_and_no_fabrication(self):
        simbad = {"main_id": "* zet01 Ret", "multiplicity": {}, "designations": _DESIG1}
        data = self._run(simbad, {"solutions": [], "route_tried": ["nss"]}, _ZET)
        self.assertTrue(data["is_multiple"])
        self.assertEqual(data["multiplicity_basis"], "gcns_cpm")
        self.assertNotIn("elements", data)                 # no fabricated a/e/mass
        self.assertIn("gcns_companions", data)
        self.assertIn("not computable", data.get("note", ""))

    def test_agreement_with_subcommand(self):
        # Same star, same helper + gate → dossier verdict == multiplicity subcommand verdict.
        simbad = {"main_id": "* zet01 Ret", "multiplicity": {}, "designations": _DESIG1}
        with mock.patch("core.databases.compute_simbad_lookup", return_value=simbad), \
             mock.patch("core.binary.binary_orbit", return_value={"solutions": [], "route_tried": ["nss"]}), \
             mock.patch("core.databases.compute_gcns_system", return_value=_ZET):
            sub = binary.multiplicity_summary(star="* zet01 Ret")
            dos = report._multiplicity_data_star(simbad, "* zet01 Ret")
        self.assertEqual(dos["is_multiple"], sub["is_multiple"])

    def test_pure_optical_grouping_no_bound_claim(self):
        # n_components=2 but the pair is optical (bound=0): is_multiple stays yes via co-membership
        # (Q4a monotonic), but NO gcns_cpm basis / bound claim, companion bound=False.
        optical = {"system": {"n_components": 2, "pairs": [
            {"source_id1": _G1, "source_id2": _G2, "proj_sep_au": 900, "separation_arcsec": 50, "bound": False}],
            "members": [{"gaia_source_id": _G1, "star_name": "A"}, {"gaia_source_id": _G2, "star_name": "B"}]}}
        simbad = {"main_id": "A", "multiplicity": {}, "designations": _DESIG1}
        data = self._run(simbad, {"solutions": [], "route_tried": ["nss"]}, optical)
        self.assertTrue(data["is_multiple"])               # co-membership (monotonic)
        self.assertNotEqual(data.get("multiplicity_basis"), "gcns_cpm")
        self.assertNotIn("note", data)                     # no "bound companion" note
        self.assertFalse(data["gcns_companions"][0]["bound"])

    def test_augment_preserves_orbit_basis(self):
        # An orbit-detected system: the augmentation must NOT overwrite the orbit multiplicity_basis,
        # must NOT add the no-fab note (elements present), and must still add gcns_companions.
        data = {"is_multiple": True, "multiplicity_basis": "SB9 seq 815 (P=79.9 d)",
                "elements": {"m1_solar": 1.1}}
        simbad = {"designations": _DESIG1}
        with mock.patch("core.databases.compute_gcns_system", return_value=_ZET):
            report._augment_gcns_multiplicity(data, simbad)
        self.assertEqual(data["multiplicity_basis"], "SB9 seq 815 (P=79.9 d)")
        self.assertIn("gcns_companions", data)
        self.assertNotIn("note", data)

    def test_render_gcns_companion_row(self):
        data = {"is_multiple": True, "sb_flag": False, "basis": None, "otype": "PM*",
                "multiplicity_basis": "gcns_cpm",
                "gcns_companions": [{"star_name": "* zet02 Ret", "source_id": 222,
                                     "bound": True, "proj_sep_au": 3721.8}]}
        _title, blocks = report._blocks_multiplicity(data)
        kv = dict(blocks[0][1])
        self.assertEqual(kv["Multiple?"], "yes")
        self.assertIn("GCNS common-proper-motion", kv["Multiplicity basis"])
        self.assertIn("3721.8 AU, bound", kv["GCNS companion"])


class _WithinStarBase(unittest.TestCase):
    """Tmp-DB scaffold (the test_gcns.py pattern) for the within-star fixtures."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (db._DB_PATH, db._conn, db._auto_seed)
        db._DB_PATH = pathlib.Path(self.tmpdir) / "test.db"
        db._conn = None
        db._auto_seed = lambda conn: None
        self.conn = db.get_conn()

    def tearDown(self):
        db.close_conn()
        db._DB_PATH, db._conn, db._auto_seed = self._saved
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _seed_gcns_star(self, **cols):
        keys = list(cols)
        self.conn.execute(
            f"INSERT INTO gcns_stars ({', '.join(keys)}) VALUES ({', '.join('?' for _ in keys)})",
            tuple(cols[k] for k in keys))

    def _seed_pair(self, system_id, s1, s2, sep_arcsec, proj_sep_au, bound):
        self.conn.execute(
            "INSERT INTO gcns_system_pairs (system_id, source_id1, source_id2, separation_arcsec, "
            "mag_diff, proj_sep_au, bin, bound) VALUES (?, ?, ?, ?, 0.5, ?, 1, ?)",
            (system_id, s1, s2, sep_arcsec, proj_sep_au, bound))

    def _seed_star_system(self, star_name, designations, parallax, ra, dec, sp="M1V", mag=10.0):
        self.conn.execute(
            "INSERT INTO star_systems (star_name, designations, spectral_type, parallax, "
            "light_years, app_magnitude, ra, dec) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (star_name, designations, sp, parallax, 1000.0 / parallax * 3.26156, mag, ra, dec))


class Cr18WithinStarB1Test(_WithinStarBase):
    """gcns-stars-within-star (databases.compute_gcns_stars_within_star)."""

    def _seed_gj9588(self):
        # Centre G 19-16 (111) + bound companion G 19-16 B (222), same system 10; pair bound, 136.68 AU.
        self._seed_gcns_star(gaia_source_id=111, ra=100.0, dec=20.0, light_years=75.05, dist_pc=23.010,
                             parallax=43.46, parallax_error=0.356, system_id=10, n_components=2,
                             star_name="G 19-16", in_gcns=1, in_simbad=0,
                             distance_method="gcns_bayesian", gcns_table="main")
        self._seed_gcns_star(gaia_source_id=222, ra=100.0, dec=20.09, light_years=75.38, dist_pc=23.111,
                             parallax=43.27, parallax_error=0.131, system_id=10, n_components=2,
                             star_name="G 19-16B", in_gcns=1, in_simbad=0,
                             distance_method="gcns_bayesian", gcns_table="main")
        self._seed_pair(10, 111, 222, 5.9173, 136.68, 1)
        self.conn.commit()

    def test_bound_companion_transverse_and_flag(self):
        self._seed_gj9588()
        out = databases.compute_gcns_stars_within_star(source_id=111, limit_ly=1.0)
        self.assertEqual(out["count"], 1)
        comp = out["stars"][0]
        self.assertEqual(comp["gaia_source_id"], 222)
        self.assertAlmostEqual(comp["transverse_sep_au"], 136.68, places=2)
        self.assertTrue(comp["bound"])
        self.assertTrue(comp["is_bound_companion"])
        self.assertEqual(comp["sep_method"], "gcns_proj_sep")
        self.assertTrue(comp["radial_parallax_dominated"])   # 3D ~0.33 ly is noise-inflated
        self.assertLess(comp["Distance"], 1.0)               # the bare 3D value is still present

    def test_sol_row_carries_cr18_keys(self):
        # A centre 0.5 ly out → the synthetic Sol row appears and must carry the new keys.
        self._seed_gcns_star(gaia_source_id=111, ra=100.0, dec=20.0, light_years=0.5, dist_pc=0.153,
                             parallax=6524.0, parallax_error=1.0, system_id=None, n_components=None,
                             star_name="Nearby", in_gcns=1, in_simbad=0,
                             distance_method="gcns_bayesian", gcns_table="main")
        self.conn.commit()
        out = databases.compute_gcns_stars_within_star(source_id=111, limit_ly=1.0)
        sol = [s for s in out["stars"] if s.get("distance_method") == "synthetic_sol_origin"]
        self.assertEqual(len(sol), 1)
        for k in ("transverse_sep_au", "transverse_sep_ly", "bound", "is_bound_companion",
                  "sep_method", "radial_parallax_dominated"):
            self.assertIn(k, sol[0])
        self.assertIsNone(sol[0]["bound"])


class Cr18WithinStarB2Test(_WithinStarBase):
    """stars-within-star (calculators.compute_stars_within_distance_of_star, SIMBAD path)."""

    def _seed(self):
        # Centre G 19-16 is in gcns_stars (for the system_id + pair map); the companion + a control are
        # star_systems rows carrying Gaia ids in their designations text.
        self._seed_gcns_star(gaia_source_id=111, ra=100.0, dec=20.0, light_years=75.05, dist_pc=23.010,
                             parallax=43.46, parallax_error=0.356, system_id=10, n_components=2,
                             star_name="G 19-16", in_gcns=1, in_simbad=1,
                             distance_method="gcns_bayesian", gcns_table="main")
        self._seed_pair(10, 111, 222, 5.9173, 136.68, 1)
        # companion (bound, Gaia 222) + a control field star (no shared system, Gaia 777).
        self._seed_star_system("G 19-16B", "GJ 660.1 B, Gaia DR3 222", 43.27, "06 40 00.0000", "+20 05 24.00")
        self._seed_star_system("Field Star", "HD 1, Gaia DR3 777", 44.0, "06 40 30.0000", "+20 20 00.00")
        self.conn.commit()

    def _center_lookup(self, name):
        return {"name": "G 19-16", "ra_deg": 100.0, "dec_deg": 20.0, "ly": 75.05, "sp_type": "M1V"}

    def test_bound_companion_and_control(self):
        self._seed()
        with mock.patch("core.calculators.compute_lookup_star_for_distance", side_effect=self._center_lookup), \
             mock.patch("core.databases.compute_simbad_lookup",
                        return_value={"designations": {"Gaia EDR3": "Gaia DR3 111"}}):
            out = calculators.compute_stars_within_distance_of_star("G 19-16", 1.0)
        by_name = {s["Star Name"]: s for s in out["stars"]}
        comp = by_name["G 19-16B"]
        self.assertAlmostEqual(comp["transverse_sep_au"], 136.68, places=2)
        self.assertTrue(comp["bound"])
        self.assertTrue(comp["is_bound_companion"])
        self.assertEqual(comp["sep_method"], "gcns_proj_sep")
        # the control field star: not co-systemed → transverse computed, bound tri-state None.
        if "Field Star" in by_name:
            fs = by_name["Field Star"]
            self.assertIsNone(fs["bound"])
            self.assertFalse(fs["is_bound_companion"])
            self.assertEqual(fs["sep_method"], "computed_angular")
            self.assertIsNotNone(fs["transverse_sep_au"])

    def test_neighbor_without_gaia_id_bound_null(self):
        self._seed()
        self._seed_star_system("No Gaia", "HD 2", 43.5, "06 40 05.0000", "+20 06 00.00")  # no Gaia token
        self.conn.commit()
        with mock.patch("core.calculators.compute_lookup_star_for_distance", side_effect=self._center_lookup), \
             mock.patch("core.databases.compute_simbad_lookup",
                        return_value={"designations": {"Gaia EDR3": "Gaia DR3 111"}}):
            out = calculators.compute_stars_within_distance_of_star("G 19-16", 1.0)
        ng = [s for s in out["stars"] if s["Star Name"] == "No Gaia"]
        if ng:
            self.assertIsNone(ng[0]["bound"])              # best-effort: unknown, not "unbound"


if __name__ == "__main__":
    unittest.main()
