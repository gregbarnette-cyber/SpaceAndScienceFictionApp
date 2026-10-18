# tests/test_cr30_age_input.py — CR-30.6: the age input (ruling 141; F2; Q23 / Q39), the catalog's new fields
# (C; Q24) and the internal seed's bases, and `placement` on every Stage-4 carrier.
#
# Offline (no sockets): validation runs before any network; the --star paths stub SIMBAD / the region step /
# Gaia exactly as tests/test_cr23.py and tests/test_report.py do.

import argparse
import json
import os
import tempfile
import unittest
from unittest import mock

import query
from core import placement, stellar_mass_tables as smt
from tests._queryharness import run_query_inproc

_BAD = ["--age-lo-gyr", "0.5", "--age-hi-gyr", "0.4", "--age-basis", "lithium"]

# each of the seven subcommands' minimal argument path (CR-30.6 acceptance 8 — "on each of its seven subcommands")
_SEVEN = {
    "exclusion-boundary": ["exclusion-boundary", "--spectral-type", "M1V"],
    "exclusion-system": ["exclusion-system", "--component", "id=X,mass=0.3"],
    "dossier": ["dossier", "--star", "G 44-42"],
    "star-regions": ["star-regions", "--star", "G 44-42"],
    "detection-completeness": ["detection-completeness", "--sp-type", "M4V", "--distance-pc", "5", "--app-mag", "10"],
    "binary-stability-auto": ["binary-stability-auto", "--star", "HIP 76901"],
}


def _age(lo, hi=1.0, basis="membership"):
    return {"lo_gyr": lo, "hi_gyr": hi, "basis": basis}


class AgeInputUnitTest(unittest.TestCase):
    def test_nothing_given(self):
        self.assertEqual(placement.age_input(None, None, None), (None, None))

    def test_valid(self):
        self.assertEqual(placement.age_input(None, 1, "membership"), (_age(None, 1.0), None))
        self.assertEqual(placement.age_input("0.1", "0.5", "lithium"), (_age(0.1, 0.5, "lithium"), None))
        self.assertEqual(placement.age_input(0.5, 0.5, "model_fit")[0], _age(0.5, 0.5, "model_fit"))

    def test_errors(self):
        cases = [((0.5, None, "lithium"), "upper bound"), ((None, 1.0, None), "needs its basis"),
                 ((None, 1.0, "rotation"), "not one of"), ((0.6, 0.5, "lithium"), "lo 0.6 Gyr > hi 0.5"),
                 ((-0.1, 0.5, "lithium"), "finite number >= 0"), ((None, float("nan"), "lithium"), "finite"),
                 ((None, float("inf"), "lithium"), "finite"), ((None, "abc", "lithium"), "not a number"),
                 ((True, 1.0, "lithium"), "finite")]
        for args, frag in cases:
            with self.subTest(args):
                age, err = placement.age_input(*args)
                self.assertIsNone(age)
                self.assertTrue(err.startswith(placement.AGE_INPUT_ERROR_PREFIX))
                self.assertIn(frag, err)


class SevenSubcommandsTest(unittest.TestCase):
    """The flags exist on all seven subcommands and a bad age is a curated error (exit 1) before any network."""

    def test_bad_age_is_exit_1_on_each(self):
        for name, argv in _SEVEN.items():
            with self.subTest(name), mock.patch("core.databases.compute_simbad_lookup",
                                                side_effect=AssertionError("network before validation")):
                code, out, _ = run_query_inproc(*argv, *_BAD)
                self.assertEqual(code, 1, out)
                self.assertTrue(out["error"].startswith("age input:"), out)

    def test_compare_stars_star_age(self):
        with mock.patch("core.databases.compute_simbad_lookup", side_effect=AssertionError("network")):
            code, out, _ = run_query_inproc("compare-stars", "--stars", "Sol", "GJ 1061",
                                            "--star-age", "GJ 1061", "0.5", "0.4", "lithium")
            self.assertEqual((code, out["error"].split(":")[0]), (1, "age input"))
            code, out, _ = run_query_inproc("compare-stars", "--stars", "Sol", "GJ 1061",
                                            "--star-age", "Vega", "none", "1", "lithium")
            self.assertEqual(code, 1)
            self.assertIn("not one of the --stars entries", out["error"])
            code, out, _ = run_query_inproc("compare-stars", "--stars", "Sol", "GJ 1061",
                                            "--star-age", "Sol", "none", "1", "lithium",
                                            "--star-age", "sol", "none", "1", "lithium")
            self.assertIn("given twice", out["error"])

    def test_star_ages_parse(self):
        ages, err = query._star_ages(["Sol", "GJ 1061"], [["gj 1061", "none", "1", "membership"]])
        self.assertIsNone(err)
        self.assertEqual(ages, {"gj 1061": _age(None, 1.0)})

    def test_basis_choices_are_argparse(self):
        code, _out, err = run_query_inproc("exclusion-boundary", "--spectral-type", "M1V", "--age-hi-gyr", "1",
                                           "--age-basis", "rotation")
        self.assertEqual(code, 2)
        self.assertIn("--age-basis", err)

    def test_supplied_mass_or_preset_refuses_an_age(self):
        for src in (["--mass-msun", "0.3"], ["--object", "sun"]):
            code, out, _ = run_query_inproc("exclusion-boundary", *src, "--age-hi-gyr", "1", "--age-basis",
                                            "lithium")
            self.assertEqual(code, 1)
            self.assertIn("--age-* apply to --star / --spectral-type", out["error"])


class ExclusionBoundaryPlacementTest(unittest.TestCase):
    def test_spectral_type_with_an_age(self):                         # acceptance 11 / 12: type X 0.5 at 0.7
        code, out, _ = run_query_inproc("exclusion-boundary", "--spectral-type", "M1V", "--alpha", "0.4",
                                        "--age-lo-gyr", "0.7", "--age-hi-gyr", "1", "--age-basis", "membership")
        self.assertEqual(code, 0)
        self.assertEqual(out["age_input"], _age(0.7, 1.0))
        pl = out["placement"]
        self.assertEqual((pl["basis"], pl["overread_route"], pl["reading_text"]),
                         ("inference", "type", placement.TEXT_FLAT))
        self.assertEqual(round(pl["overread_factor"], 6), 0.999442)

    def test_no_age_no_echo(self):
        code, out, _ = run_query_inproc("exclusion-boundary", "--spectral-type", "M1V")
        self.assertNotIn("age_input", out)
        self.assertEqual(out["placement"]["status"], "stellar")

    def test_supplied_mass_placed_by_band_byte_identical(self):        # §13.5 C6
        code, out, _ = run_query_inproc("exclusion-boundary", "--mass-msun", "0.3", "--alpha", "0.4")
        self.assertEqual(out["r_ex_au"], 29.345540401952064)
        self.assertEqual((out["placement"]["status"], out["placement"]["basis"]), ("stellar", "supplied"))
        code, out, _ = run_query_inproc("exclusion-boundary", "--mass-msun", "0.07")
        pl = out["placement"]
        self.assertEqual(pl["status"], "boundary")
        self.assertEqual(pl["windless_alternative"]["domain"], "windless_free_harbor")
        self.assertIsNotNone(out["r_ex_au"])                            # the operative standoff unchanged

    def test_object_preset_not_placed(self):
        code, out, _ = run_query_inproc("exclusion-boundary", "--object", "sun")
        self.assertNotIn("placement", out)

    def test_delta_and_gravity_types(self):                              # acceptance 8 / 9 live analogues
        code, out, _ = run_query_inproc("exclusion-boundary", "--spectral-type", "M8 delta", "--alpha", "0.4")
        pl = out["placement"]
        self.assertEqual((pl["pre_ms"], pl["status"], pl["r_ex_direction"]), (True, "boundary", "upper_bound"))
        self.assertEqual(round(out["r_ex_au"], 2), 17.72)
        code, out, _ = run_query_inproc("exclusion-boundary", "--spectral-type", "M7 VL-G", "--alpha", "0.4",
                                        "--age-lo-gyr", "0.5", "--age-hi-gyr", "1", "--age-basis", "membership")
        self.assertEqual((out["placement"]["status"], out["placement"]["reading"]), ("stellar", "le_x"))


class ExclusionSystemPlacementTest(unittest.TestCase):
    def _comps(self, out):
        return {c["id"]: c for z in out["zones"] for c in z["components"]}

    def test_component_lum_route_with_the_call_age(self):            # acceptance 11: luminosity X 0.25 at 0.15
        code, out, _ = run_query_inproc("exclusion-system", "--component", "id=X,lum=0.008264229206",
                                        "--age-lo-gyr", "0.15", "--age-hi-gyr", "1", "--age-basis", "membership")
        self.assertEqual(code, 0, out)
        pl = self._comps(out)["X"]["placement"]
        self.assertEqual((pl["overread_route"], round(pl["overread_factor"], 6)), ("luminosity", 1.062472))
        self.assertEqual(out["age_input"], _age(0.15, 1.0))

    def test_the_cut_by_the_call_age(self):                            # acceptance 6: X 0.0940 at 0.251 / 0.271
        for t in ("0.251", "0.271"):
            code, out, _ = run_query_inproc("exclusion-system", "--component", "id=X,lum=0.000820151337850115",
                                            "--age-lo-gyr", t, "--age-hi-gyr", "1", "--age-basis", "membership")
            with self.subTest(t):
                self.assertEqual(self._comps(out)["X"]["placement"]["status"], "boundary")

    def test_under_read(self):                                          # acceptance 12: X 0.9405 at 0.1
        code, out, _ = run_query_inproc("exclusion-system", "--component", "id=X,lum=0.6918303142",
                                        "--age-lo-gyr", "0.1", "--age-hi-gyr", "1", "--age-basis", "membership")
        pl = self._comps(out)["X"]["placement"]
        self.assertEqual((pl["reading"], pl["reading_text"]), ("x", placement.TEXT_UNDER))

    def test_component_age_replaces_the_call_age(self):                 # Q39
        code, out, _ = run_query_inproc(
            "exclusion-system", "--component", "id=A,lum=0.008264229206",
            "--component", "id=B,lum=0.008264229206,pair=AB,sma=50,ecc=0,age_lo=0.1,age_hi=5,age_basis=lithium",
            "--age-lo-gyr", "0.1", "--age-hi-gyr", "1", "--age-basis", "membership")
        c = self._comps(out)
        self.assertTrue(c["A"]["placement"]["youth_flag"])
        self.assertFalse(c["B"]["placement"]["youth_flag"])               # its own hi 5 Gyr: no youth signal
        self.assertEqual(c["B"]["placement"]["age_input"], _age(0.1, 5.0, "lithium"))

    def test_component_otype_pre_ms(self):                               # Q21
        code, out, _ = run_query_inproc("exclusion-system", "--component", "id=X,lum=0.008264229206,otype=TT*|PM*")
        pl = self._comps(out)["X"]["placement"]
        self.assertEqual((pl["pre_ms"], pl["pre_ms_signal"]), (True, "component_otype:TT*"))

    def test_component_age_error(self):
        code, out, _ = run_query_inproc("exclusion-system", "--component", "id=A,mass=0.3,age_lo=2,age_hi=1,"
                                                                           "age_basis=lithium")
        self.assertEqual(code, 1)
        self.assertEqual(out["error"], "component 'A': age input: lo 2 Gyr > hi 1 Gyr")

    def test_supplied_band_and_overrides(self):                          # acceptance 1 / 3
        exp = {"mass=0.0669": ("substellar", False), "mass=0.067": ("boundary", False),
               "mass=0.070,type=T7": ("substellar", False), "mass=0.080,type=T7": ("substellar", True),
               "mass=0.080,type=L5": ("stellar", False), "mass=0.080,lum=4.8978e-05": ("substellar", True)}
        for spec, (st, flag) in exp.items():
            code, out, _ = run_query_inproc("exclusion-system", "--component", f"id=X,{spec}")
            with self.subTest(spec):
                self.assertEqual(code, 0, out)
                pl = self._comps(out)["X"]["placement"]
                self.assertEqual((pl["status"], pl["conflict_flag"]), (st, flag))

    def test_white_dwarf_not_placed(self):
        code, out, _ = run_query_inproc("exclusion-system", "--component", "id=W,mass=0.6,class=wd")
        self.assertIsNone(self._comps(out)["W"]["placement"])


class StarRegionsPlacementTest(unittest.TestCase):
    _SL = {"main_id": "G 44-42", "sp_type": "M4V", "otype": "PM*", "designations": {}}

    def _reg(self, x):
        from core import ms_sequence
        life = ms_sequence.ms_lifetime(x)
        return {"stellarMass": x, "mass_route": "mks", "bcLuminosity": 0.0085, "mainSeqLifeSpan": life["yr"],
                "ms_lifetime_status": life["status"], "ms_lifetime_note": life["note"],
                "ms_lifetime_end_point": life["end_point"]}

    def _run(self, *extra, x=0.265023):
        with mock.patch("core.databases.compute_simbad_lookup", return_value=dict(self._SL)), \
                mock.patch("core.regions.compute_star_system_regions_from_simbad", return_value=self._reg(x)), \
                mock.patch("core.databases.compute_hypatia_data", return_value={"error": "x"}):
            return run_query_inproc("star-regions", "--star", "G 44-42", *extra)

    def test_membership_pre_ms(self):                                    # acceptance 9 (star-regions carrier)
        code, out, _ = self._run("--age-lo-gyr", "0.005", "--age-hi-gyr", "0.02", "--age-basis", "membership")
        self.assertEqual(code, 0)
        pl = out["placement"]
        self.assertEqual((pl["basis"], pl["pre_ms"], pl["status"], pl["reading"]),
                         ("inference", True, "boundary", "le_x"))      # E governs D: no factor read
        self.assertIsNone(out["mainSeqLifeSpan"])                         # #26: boundary → null
        self.assertEqual(round(out["ms_lifetime_if_stellar_ge_yr"] / 1e9, 2), 618.79)
        self.assertEqual(out["age_input"], _age(0.005, 0.02))

    def test_unflagged_keeps_the_lifetime(self):
        code, out, _ = self._run()
        self.assertEqual(out["placement"]["status"], "stellar")
        from core import ms_sequence
        self.assertEqual(out["mainSeqLifeSpan"], ms_sequence.ms_lifetime(0.265023)["yr"])
        self.assertNotIn("age_input", out)


class DossierPlacementTest(unittest.TestCase):
    def test_regions_mass_placement_and_lifetime(self):
        from core import report
        from tests.test_report import _patched
        with _patched():
            r = report.build_system_dossier("Tau Ceti", sections=["identity", "regions"], fmt="json",
                                            age=_age(None, 0.5))
        mb = r["data"]["regions"]["mass"]
        pl = mb["placement"]
        self.assertEqual(pl["age_input"], _age(None, 0.5))
        self.assertTrue(pl["youth_flag"])
        self.assertEqual(pl["status"], "stellar")                        # G8V: far above the no-age cut
        st = r["data"]["regions"]["stellar"]
        self.assertEqual(st["ms_lifetime_status"], pl["lifetime"]["ms_lifetime_status"])

    def test_cli_age_reaches_the_dossier(self):
        from tests.test_report import _patched
        with _patched():
            code, out, _ = run_query_inproc("dossier", "--star", "Tau Ceti", "--sections", "identity", "regions",
                                            "--fmt", "json", "--age-hi-gyr", "0.5", "--age-basis", "lithium")
        self.assertEqual(code, 0)
        self.assertEqual(out["data"]["regions"]["mass"]["placement"]["age_input"], _age(None, 0.5, "lithium"))

    def test_markdown_renders_a_non_plain_placement(self):
        from core import report
        from tests.test_report import _patched
        with _patched():
            r = report.build_system_dossier("Tau Ceti", sections=["identity", "regions"], fmt="markdown",
                                            age=_age(None, 0.5))
        self.assertIn("Placement: stellar", r["document"])


class CompareStarsPlacementTest(unittest.TestCase):
    def test_per_star_placement_and_age(self):
        from core import databases as dbs
        sl = {"main_id": "G 44-42", "sp_type": "M4V", "otype": "PM*", "designations": {}}
        reg = {"stellarMass": 0.265023, "mass_lroute_solar": 0.25, "mass_mks_solar": 0.265023,
               "stellarRadius": 0.27, "bcLuminosity": 0.0085}
        with mock.patch.object(dbs, "compute_simbad_lookup", return_value=sl), \
                mock.patch("core.regions.compute_star_system_regions_from_simbad", return_value=reg), \
                mock.patch.object(dbs, "_flame_mass_for", return_value=(None, None)), \
                mock.patch.object(dbs, "compute_hypatia_data", return_value={"error": "x"}), \
                mock.patch.object(dbs, "_get_archive_query_params", return_value=(None, None)):
            r = dbs.compare_stars(["G 44-42", "Sol"], ages={"g 44-42": _age(0.005, 0.02)})
        g, sol = r["stars"]
        self.assertEqual((g["placement"]["pre_ms"], g["placement"]["status"]), (True, "boundary"))
        self.assertEqual(g["age_input"], _age(0.005, 0.02))
        self.assertEqual(sol["placement"]["status"], "stellar")
        self.assertNotIn("age_input", sol)


class CatalogFieldsTest(unittest.TestCase):                              # C; Q24
    def _load(self, row):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            json.dump({"stars": [dict({"main_id": "* X", "mass_solar": 0.1}, **row)]}, f)
        try:
            return smt.load_mass_catalog(path)
        finally:
            os.unlink(path)

    def test_errors_name_the_row_and_field(self):
        cases = [({"mass_basis": "guess"}, "mass_basis"),
                 ({"mass_interval": {"lo": 0.09, "hi": 0.11, "kind": "range"}}, "mass_interval.kind"),
                 ({"mass_interval": {"lo": 0.12, "hi": 0.11, "kind": "sigma_1"}}, "lo <= hi"),
                 ({"mass_interval": {"lo": 0.11, "hi": 0.12, "kind": "sigma_1"}}, "outside mass_interval"),
                 ({"age_interval": {"lo_gyr": 0.5, "hi_gyr": 0.4, "basis": "membership", "grade": "member"}},
                  "lo_gyr 0.5 > hi_gyr 0.4"),
                 ({"age_interval": {"lo_gyr": None, "hi_gyr": 1, "basis": "rotation", "grade": "member"}},
                  "age_interval.basis"),
                 ({"age_interval": {"lo_gyr": None, "hi_gyr": 1, "basis": "membership", "grade": "maybe"}},
                  "age_interval.grade"),
                 ({"age_interval": {"lo_gyr": -1, "hi_gyr": 1, "basis": "membership", "grade": "member"}},
                  "age_interval.lo_gyr")]
        for row, frag in cases:
            with self.subTest(frag):
                err = self._load(row)
                self.assertIn("error", err)
                self.assertIn("* X:", err["error"])
                self.assertIn(frag, err["error"])

    def test_a_row_without_the_fields_loads(self):
        self.assertNotIn("error", self._load({}))

    def test_wb_test_catalog_loads_clean(self):
        path = os.path.join(os.path.dirname(__file__), "fixtures", "cr30", "cr30_test_mass_catalog.json")
        cat = smt.load_mass_catalog(path)
        self.assertNotIn("error", cat)
        self.assertEqual(len(cat["stars"]), 25)

    def test_a_catalog_error_is_exit_1_on_the_star_path(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            json.dump({"stars": [{"main_id": "* X", "mass_solar": 0.1, "mass_basis": "guess"}]}, f)
        try:
            code, out, _ = run_query_inproc("exclusion-system", "--component", "id=X,mass=0.3",
                                            "--star-mass-catalog", path)
        finally:
            os.unlink(path)
        self.assertEqual(code, 1)
        self.assertIn("mass_basis", out["error"])


class SeedBasesTest(unittest.TestCase):                                  # C; ruling 19 R-10
    def test_seed_rows(self):
        seed = {r["id"]: r for r in smt.load_mass_catalog(None)["stars"]}
        self.assertEqual({k: v["mass_basis"] for k, v in seed.items()},
                         {"Sirius A": "dynamical", "Vega": "interferometric", "alpha Centauri A": "dynamical",
                          "alpha Centauri B": "dynamical"})
        for r in seed.values():
            iv = r["mass_interval"]
            self.assertEqual(iv["kind"], "sigma_1")
            self.assertAlmostEqual(iv["lo"], r["mass_solar"] - r["mass_uncertainty_solar"], places=4)
            self.assertAlmostEqual(iv["hi"], r["mass_solar"] + r["mass_uncertainty_solar"], places=4)
            self.assertNotIn("age_interval", r)

    def test_sirius_a_dynamical_on_exclusion_boundary(self):            # acceptance 3 (offline)
        from tests.test_cr23 import _SEED_SIRIUS_A, _fake_simbad, _run_boundary
        with mock.patch("core.databases.compute_simbad_lookup", _fake_simbad(_SEED_SIRIUS_A)), \
                mock.patch("core.regions.compute_star_system_regions_from_simbad",
                           lambda sl, **kw: {"bcLuminosity": 25.4}), \
                mock.patch("core.binary.gaia_source_id_from_designations", lambda d: None):
            r = _run_boundary(star="Sirius A", alpha=0.4)
        self.assertEqual(r["mass_provenance"], "catalog")
        pl = r["placement"]
        self.assertEqual((pl["basis"], pl["basis_unknown"], pl["status"]), ("dynamical", False, "stellar"))
        self.assertEqual(pl["interval"], {"lo": 2.040, "hi": 2.086, "kind": "sigma_1"})
        self.assertAlmostEqual(r["r_ex_au"], 63.45901120705829, places=9)


if __name__ == "__main__":
    unittest.main()


class Cp4FixesTest(unittest.TestCase):
    """CP4 (`/code-review high`, 2026-10-16) findings, pinned."""

    def test_sigma_interval_floors_at_zero(self):                       # #1
        row = {"main_id": "* X", "mass_solar": 0.072, "mass_uncertainty_solar": 0.08}
        pl = placement.place_resolved(0.072, "catalog", catalog_row=row)
        self.assertEqual(pl["interval"]["lo"], 0.0)
        out = placement.boundary_extras(pl, 20.0, 0.4)
        self.assertEqual(out["r_ex_interval_au"][0], 0.0)
        self.assertTrue(all(isinstance(v, float) for v in out["r_ex_interval_au"]))

    def test_orbit_provenances(self):                                    # #2
        m1 = placement.place_resolved(0.3, "binary_orbit_m1", sp_type="M3V")
        self.assertEqual((m1["basis"], m1["takes_margin"]), ("inference", True))
        m2 = placement.place_resolved(0.3, "binary_orbit_m2")
        self.assertEqual((m2["basis"], m2["basis_unknown"]), ("relation", True))
        lo = placement.place_resolved(0.05, "binary_orbit_sb1_min")
        self.assertEqual((lo["status"], lo["status_text"], lo["reading"]),
                         ("boundary", "undetermined (minimum mass)", "ge_x"))
        self.assertIsNone(placement.boundary_extras(lo, 20.0, 0.4)["windless_alternative"])
        hi = placement.place_resolved(0.078, "binary_orbit_sb1_min")
        self.assertEqual((hi["status"], hi["reading"], hi["lifetime"]["ms_lifetime_direction"]),
                         ("stellar", "ge_x", "le"))
        unk = placement.place_resolved(0.3, "something_new")
        self.assertEqual((unk["basis"], unk["basis_unknown"]), ("relation", True))

    def test_sigma_validated_at_load(self):                              # #3
        for bad in ("n/a", -0.1, float("inf"), True):
            with self.subTest(bad):
                err = smt.validate_cr30_fields({"stars": [{"main_id": "* X", "mass_solar": 0.1,
                                                           "mass_uncertainty_solar": bad}]})
                self.assertIn("mass_uncertainty_solar", err)

    def test_duplicate_component_ids_keep_their_own_placement(self):    # #4
        code, out, _ = run_query_inproc("exclusion-system", "--component", "id=A,mass=0.07",
                                        "--component", "id=A,mass=1.0,pair=AB,sma=500,ecc=0")
        self.assertEqual(code, 0, out)
        got = sorted((c["mass_solar"], c["placement"]["status"]) for z in out["zones"] for c in z["components"])
        self.assertEqual(got, [(0.07, "boundary"), (1.0, "stellar")])

    def test_bare_compose_has_no_placement_key(self):
        from core import exclusion_system as es
        r = es.compose_exclusion_system([{"id": "A", "mass_solar": 0.3}])
        self.assertNotIn("placement", r["zones"][0]["components"][0])

    def test_binary_a_otype_reads_component_a(self):                    # #5 (re-pinned at CP5 #7: one lookup)
        from core import exclusion_system as es
        head = {"main_id": "* sys", "otype": "**"}
        with mock.patch.object(es, "resolve_star_identity",
                               return_value=({"main_id": "* sys A", "otype": "TT*"}, {"main_id": "* sys"}, None,
                                             None)):
            self.assertEqual(es._a_otype(head)[0], "TT*")
        with mock.patch.object(es, "resolve_star_identity", return_value=(None, None, None, {"error": "x"})):
            self.assertEqual(es._a_otype(head)[0], "**")

    def test_sol_dossier_is_placed(self):                                # #6
        from core import report
        from tests.test_report import _patched_sol
        with _patched_sol():
            r = report.build_system_dossier("Sol", sections=["regions"], fmt="json", age=_age(None, 4.6, "model_fit"))
        pl = r["data"]["regions"]["mass"]["placement"]
        self.assertEqual((pl["status"], pl["youth_flag"]), ("stellar", False))
        self.assertEqual(pl["age_input"], _age(None, 4.6, "model_fit"))

    def test_one_enum_source(self):                                      # #7
        self.assertEqual(set(smt._MASS_BASES), placement.CATALOG_BASES)
        self.assertEqual(set(smt._AGE_BASES), placement.AGE_BASES)
        self.assertEqual(set(smt._AGE_GRADES), placement.AGE_GRADES)
        self.assertEqual(set(smt._INTERVAL_KINDS), placement.INTERVAL_KINDS)

    def test_catalog_matched_once(self):                                 # #9
        from core import stellar_mass
        calls = {"n": 0}
        real = smt.match_mass

        def _count(*a, **k):
            calls["n"] += 1
            return real(*a, **k)
        with mock.patch.object(smt, "match_mass", _count):
            md = {}
            stellar_mass.resolve_component_mass({"name": "* alf CMa", "designations": {"x": "* alf CMa"}},
                                                smt.load_mass_catalog(None), allow_flame=False, detail_out=md)
        self.assertEqual(calls["n"], 1)
        self.assertEqual(md["catalog_row"]["id"], "Sirius A")
