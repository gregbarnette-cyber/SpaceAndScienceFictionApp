# tests/test_cr30_consumers.py — CR-30.7: placement's consumers (the exclusion domain, binary.py,
# detection-completeness, the census). Offline: SIMBAD / Gaia / the archive are stubbed; the no-identity paths run
# in-process through query.py.

import json
import os
import tempfile
import unittest
from unittest import mock

import query
from core import binary, detection, exclusion_wall as ew, placement, regions
from tests._queryharness import run_query_inproc
from tests.test_cr23 import _fake_simbad, _run_boundary


def _age(lo, hi=1.0, basis="membership"):
    return {"lo_gyr": lo, "hi_gyr": hi, "basis": basis}


def _comps(out):
    return {c["id"]: c for z in out["zones"] for c in z["components"]}


def _tmp_catalog(rows):
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump({"stars": rows}, f)
    return path


_WOLF_ROW = {"main_id": "* CN Leo", "aliases": ["Wolf 359"], "mass_solar": 0.1082, "mass_basis": "model",
             "mass_interval": {"lo": 0.0706, "hi": 0.1082, "kind": "wb_derivation"}}


# ═══════════════════════════════════ A. the exclusion domain ═══════════════════════════════════════
class ExclusionDomainTest(unittest.TestCase):
    def test_l0_stellar_by_mass_gets_a_standoff(self):                # acceptance 4: 17.18 AU
        code, out, _ = run_query_inproc("exclusion-system", "--alpha", "0.4", "--component",
                                        "id=A,mass=0.07866,type=L0")
        c = _comps(out)["A"]
        self.assertEqual((code, c["domain"], c["placement"]["status"]), (0, ew.MAIN_SEQUENCE, "stellar"))
        self.assertEqual(round(c["r_ex_au"], 2), 17.18)
        self.assertEqual(c["wall_route"], "none_no_wind")                 # an L type: no wall without a wind state

    def test_l2_no_mass_is_undetermined(self):                          # acceptance 4
        code, out, _ = run_query_inproc("exclusion-system", "--component", "id=X,type=L2")
        c = _comps(out)["X"]
        self.assertEqual(code, 0)
        self.assertEqual((c["domain"], c["r_ex_au"], c["wall_route"]),
                         (ew.UNDETERMINED_NO_MASS, None, "none_undetermined"))
        self.assertEqual(c["placement"]["status_text"], "undetermined — no mass")
        self.assertIsNone(out["zones"][0]["forcing_class"])

    def test_band_edges_and_override(self):                              # acceptance 1 / 3
        code, out, _ = run_query_inproc("exclusion-system", "--component", "id=X,mass=0.0669")
        self.assertEqual(_comps(out)["X"]["domain"], ew.WINDLESS)
        code, out, _ = run_query_inproc("exclusion-system", "--alpha", "0.4", "--component", "id=X,mass=0.067")
        c = _comps(out)["X"]
        self.assertEqual((c["domain"], round(c["r_ex_au"], 2)), (ew.MAIN_SEQUENCE, 16.11))
        self.assertEqual(c["placement"]["windless_alternative"]["domain"], ew.WINDLESS)
        code, out, _ = run_query_inproc("exclusion-system", "--component", "id=X,mass=0.080,type=T7")
        c = _comps(out)["X"]
        self.assertEqual((c["domain"], c["placement"]["conflict_flag"]), (ew.WINDLESS, True))

    def test_exclusion_boundary_spectral_type_paths(self):               # §13.5 M8
        code, out, _ = run_query_inproc("exclusion-boundary", "--spectral-type", "L3")
        self.assertEqual((code, out["domain"], out["r_ex_au"]), (0, ew.UNDETERMINED_NO_MASS, None))
        self.assertIn("domain_note", out)
        code, out, _ = run_query_inproc("exclusion-boundary", "--spectral-type", "T7")
        self.assertEqual((out["domain"], out["placement"]["status"], out["placement"]["conflict_trigger"]),
                         (ew.WINDLESS, "substellar", "type:T7"))
        code, out, _ = run_query_inproc("exclusion-boundary", "--mass-msun", "0.05")
        self.assertEqual((out["domain"], out["mass_msun"], out["placement"]["status"]),
                         (ew.WINDLESS, 0.05, "substellar"))

    def test_presets_and_wd_unchanged(self):                              # §13.5 M8: byte-identical early returns
        code, out, _ = run_query_inproc("exclusion-boundary", "--object", "sun")
        self.assertEqual((out["r_ex_au"], out["wall_au"]), (47.5, 6.0))
        code, out, _ = run_query_inproc("exclusion-boundary", "--object", "brown-dwarf")
        self.assertEqual(out["domain"], ew.WINDLESS)
        self.assertNotIn("placement", out)
        code, out, _ = run_query_inproc("exclusion-boundary", "--spectral-type", "DA2")
        self.assertEqual(out["domain"], ew.WINDLESS)
        self.assertNotIn("placement", out)

    def _star(self, simbad, catalog=None, flame=None, **kw):
        cat = _tmp_catalog(catalog) if catalog is not None else None
        try:
            with mock.patch("core.databases.compute_simbad_lookup", _fake_simbad(simbad)), \
                    mock.patch("core.regions.compute_star_system_regions_from_simbad",
                               lambda sl, **k: {"bcLuminosity": 0.001}), \
                    mock.patch("core.binary.gaia_source_id_from_designations", lambda d: "1" if flame else None), \
                    mock.patch("core.catalog.gaia_astrophysical",
                               lambda **k: {"parameters": {"mass_flame": flame}}):
                return _run_boundary(star=list(simbad)[0], alpha=0.4, star_mass_catalog=cat, **kw)
        finally:
            if cat:
                os.unlink(cat)

    def test_wolf_359_boundary_row(self):                                 # acceptance 4 / CR-30.6 acceptance 10
        r = self._star({"Wolf 359": {"main_id": "* CN Leo", "sp_type": "M6.5Ve", "otype": "Fl*",
                                     "designations": {"NAME": "Wolf 359"}}}, catalog=[_WOLF_ROW])
        pl = r["placement"]
        self.assertEqual((r["domain"], pl["status"], pl["x_equals_hi"]), (ew.MAIN_SEQUENCE, "boundary", True))
        self.assertEqual(round(r["r_ex_au"], 2), 19.52)
        self.assertEqual([round(v, 2) for v in pl["r_ex_interval_au"]], [16.45, 19.52])
        self.assertEqual(pl["windless_alternative"]["domain"], ew.WINDLESS)
        self.assertIsNone(pl["lifetime"]["ms_lifetime_yr"])

    def test_star_l_type_without_a_mass_is_undetermined(self):
        r = self._star({"DENIS X": {"main_id": "DENIS X", "sp_type": "L1.5", "otype": "BD*",
                                    "designations": {}}})
        self.assertEqual((r["domain"], r["r_ex_au"], r["placement"]["status"]),
                         (ew.UNDETERMINED_NO_MASS, None, "undetermined_no_mass"))
        self.assertIsNone(r.get("mass_msun"))                             # no inference route for an L type

    def test_star_t_type_runs_the_ladder_for_the_conflict_flag(self):
        r = self._star({"GJ 229 B": {"main_id": "GJ 229 B", "sp_type": "T7pec", "otype": "BD*",
                                     "designations": {}}},
                       catalog=[{"main_id": "GJ 229 B", "mass_solar": 0.08, "mass_basis": "dynamical"}])
        self.assertEqual(r["domain"], ew.WINDLESS)
        self.assertIsNone(r["r_ex_au"])
        self.assertEqual((r["placement"]["status"], r["placement"]["conflict_flag"]), ("substellar", True))


# ═══════════════════════════════════ B. binary.py ═══════════════════════════════════════════════════
class BinaryClassifierTest(unittest.TestCase):
    def test_sb1_minimums(self):                                          # acceptance 1
        cm = binary.companion_mass_from_sb1(6.0, 9.9448, 0.25, binary.m1_from_spectral_type("F2V"))
        self.assertEqual(round(cm["m2_solar"], 6), 0.078188)              # i Cen at S1's 1.46
        c = binary._with_class(cm)
        self.assertEqual(c["class"], "stellar")
        self.assertIn("true M₂ ≥ this", c["caveat"])
        self.assertEqual(binary.classify_companion(0.044186, minimum=True)["class"], binary.CLASS_MIN_UNDETERMINED)
        self.assertEqual(binary.classify_companion(0.075331, minimum=True)["class"], "stellar")   # alf Tri
        self.assertEqual(binary.classify_companion(0.070400)["class"], binary.CLASS_BOUNDARY)     # LP 120-4

    def test_flagged_primary_sb1_hand_anchor(self):                       # acceptance 2: ≤ 0.0766, min mass
        m1 = binary.m1_from_spectral_type("M7V")
        self.assertEqual(m1, 0.09)
        pl = binary.primary_placement(m1, "spectral_type_table", sp_type="M7 VL-G")
        self.assertEqual(pl["reading"], "le_x")
        comp = binary.flag_companion(binary._with_class(binary.companion_mass_from_sb1(25, 10, 0.0, m1)), pl)
        self.assertEqual(round(comp["m2_solar"], 4), 0.0766)
        self.assertEqual((comp["class"], comp["m2_direction"], comp["sb1_caveat_withheld"]),
                         (binary.CLASS_MIN_UNDETERMINED, "le", True))
        self.assertNotIn("true M₂ ≥ this", comp["caveat"])

    def test_flagged_primary_true_mass(self):
        pl = binary.primary_placement(0.184, "spectral_type_table", sp_type="M4.5 VL-G")
        comp = binary.flag_companion({"method": "astrom", "m1_solar": 0.184, "m2_solar": 0.0704,
                                      **binary.classify_companion(0.0704)}, pl)
        self.assertEqual((comp["class"], comp["substellar"]), ("undetermined — at most " + binary.CLASS_BOUNDARY,
                                                               False))
        pre = binary.primary_placement(0.8, "spectral_type_table", sp_type="K0 delta")
        comp = binary.flag_companion({"method": "astrom", "m2_solar": 0.3, **binary.classify_companion(0.3)}, pre)
        self.assertEqual(comp["class"], binary.CLASS_PRE_MS_PRIMARY)

    def test_m1_from_s1_anchors(self):                                     # acceptance 3
        for sp, m in (("O9.5II-III(n)", 18.7), ("O7Iafpvar", 28.0), ("B3V", 5.4), ("B2IV-V", 7.3),
                      ("dM4.5", 0.184), ("F5III", 1.33)):
            self.assertEqual(binary.m1_from_spectral_type(sp), m, sp)

    def test_null_m1_reasons_and_caveats(self):
        for reason in ("letter_only_type", "unreadable_type", "outside_s1_mass_span", "no_simbad_lookup"):
            c = binary._m1_unknown_companion("spec-min", reason)
            self.assertEqual((c["class"], c["m1_null_reason"]), ("unknown", reason))
            self.assertNotEqual(c["caveat"], binary._NOTE_M1_UNKNOWN)
        self.assertEqual(binary._m1_unknown_companion("astrom")["caveat"], binary._NOTE_M1_UNKNOWN)

    def test_census_row_null_m1_is_kept_unknown(self):                    # §13.5 M6
        c = binary._companion_from_row(10.0, 0.1, (None,) * 4, 5.0, None, 20.0, None, m1_reason="letter_only_type")
        self.assertEqual((c["class"], c["m1_null_reason"]), ("unknown", "letter_only_type"))

    def _nss(self, sp, rows, bmass=(None, None)):
        with mock.patch("core.catalog.gaia_tap", return_value={"rows": rows}), \
                mock.patch("core.catalog.gaia_binary_masses", return_value=bmass):
            return binary._nss_two_body_solutions("1", sp, 10.0)[0]

    def test_nss_letter_only_primary(self):                               # HD 198812 / BD-01 1701 shapes
        row = {"period": 100.0, "eccentricity": 0.1, "semi_amplitude_primary": 5.0, "parallax": 10.0}
        comp = self._nss("A", [row])[0]["companion"]
        self.assertEqual((comp["m1_solar"], comp["class"], comp["m1_null_reason"]),
                         (None, "unknown", "letter_only_type"))
        filled = self._nss("M", [row], ({"m1": None, "m2": 0.363172}, None))[0]["companion"]
        self.assertEqual((filled["m2_solar"], filled["class"]), (0.363172, "stellar"))

    def test_source_id_names_no_lookup(self):
        row = {"period": 100.0, "eccentricity": 0.1, "semi_amplitude_primary": 5.0, "parallax": 10.0}
        with mock.patch("core.catalog.gaia_tap", return_value={"rows": [row]}), \
                mock.patch("core.catalog.gaia_binary_masses", return_value=(None, None)):
            sols = binary._nss_two_body_solutions("1", None, 10.0, m1_reason="no_simbad_lookup")[0]
        self.assertEqual(sols[0]["companion"]["m1_null_reason"], "no_simbad_lookup")

    def test_census_nss_m1_assumed_note(self):                             # §13.5 C16
        row = {"source_id": 1, "period": 50.0, "eccentricity": 0.0, "semi_amplitude_primary": 5.0,
               "parallax": 50.0, "nss_solution_type": "SB1", "significance": 10, "ra": 1.0, "dec": 2.0}
        with mock.patch("core.catalog.gaia_tap", return_value={"rows": [row]}):
            rows, _err = binary._census_nss(10, 1000)
        self.assertEqual(rows[0]["m1_assumed_note"], binary._NOTE_CENSUS_M1)


class StabilityDirectionsTest(unittest.TestCase):
    def _out(self, m1, m2, prov_b):
        return {"elements": {"m1_solar": m1, "m2_solar": m2, "mass_provenance_a": "binary_orbit_m1",
                             "mass_provenance_b": prov_b}}

    def test_hip_76901_flagged_sb1(self):                                 # acceptance 2
        out = binary.apply_primary_directions(self._out(0.184, 0.044186, "binary_orbit_sb1_min"), "dM4.5", None,
                                              _age(0.1), None)
        el = out["elements"]
        self.assertEqual(round(out["placement_a"]["overread_factor"], 5), 1.17797)
        self.assertEqual((el["m1_direction"], el["m2_direction"], el["m2_class"], el["sb1_caveat_withheld"]),
                         ("le", "le", binary.CLASS_MIN_UNDETERMINED, True))
        self.assertEqual(out["age_input"], _age(0.1))

    def test_lp_120_4_flagged_true_mass(self):
        out = binary.apply_primary_directions(self._out(0.184, 0.0704, "binary_orbit_m2"), "M4.5Ve", None,
                                              _age(0.1), None)
        self.assertEqual(out["elements"]["m2_class"], "undetermined — at most " + binary.CLASS_BOUNDARY)

    def test_i_cen_flagged_without_le(self):                               # pre-fire ruling 21 D2
        out = binary.apply_primary_directions(self._out(1.46, 0.078188, "binary_orbit_sb1_min"), "F2V", None,
                                              _age(0.1), None)
        self.assertEqual(out["placement_a"]["reading"], "x")
        self.assertNotIn("m2_direction", out["elements"])

    def test_measured_m1_takes_no_direction(self):                         # Q32
        out = {"elements": {"m1_solar": 0.184, "m2_solar": 0.05, "mass_provenance_a": "catalog",
                            "mass_provenance_b": "binary_orbit_sb1_min"}}
        binary.apply_primary_directions(out, "M4.5V", {"mass_solar": 0.184, "mass_basis": "dynamical"},
                                        _age(0.1), None)
        self.assertNotIn("m1_direction", out["elements"])

    def test_null_m1_no_masses_result(self):                               # R-6 / Q34
        sols = [{"source": "gaia-nss:two_body_orbit", "period_d": 100.0, "eccentricity": 0.1,
                 "companion": binary._m1_unknown_companion("spec-min", "no_simbad_lookup")}]
        stab = binary.stability_from_solutions("X", {"sp_type": None}, sols, ["gaia-nss"])
        out = binary.apply_primary_directions(stab, None, None, None, "no_simbad_lookup")
        self.assertIsNone(out["elements"])
        self.assertIsNone(out["stype_critical_au"])
        self.assertEqual(out["m1_null_reason"], "no_simbad_lookup")
        self.assertIn("M₁ is null", out["note"])


# ═══════════════════════════════════ C. detection-completeness ══════════════════════════════════════
class DetectionTest(unittest.TestCase):
    def _star(self, simbad, arch=None, catalog=None, extra=()):
        cat = _tmp_catalog(catalog) if catalog is not None else None
        try:
            with mock.patch("core.databases.compute_simbad_lookup", return_value=simbad), \
                    mock.patch("core.exoplanet_batch.fetch_archive_stellar_mass", return_value=arch):
                args = ["detection-completeness", "--star", "X"] + (["--star-mass-catalog", cat] if cat else [])
                return run_query_inproc(*args, *extra)[1]
        finally:
            if cat:
                os.unlink(cat)

    def _sl(self, sp, otype="PM*", vmag=12.0):
        return {"main_id": "X", "sp_type": sp, "otype": otype, "vmag": vmag, "parsecs": 5.0, "designations": {}}

    def test_type_only_branches(self):                                     # acceptance 5
        cases = {("M9V",): ("boundary", 0.079), ("L3beta",): ("undetermined_no_mass", None),
                 ("M5 VL-G",): ("boundary", 0.162)}
        for (sp,), (st, m) in cases.items():
            code, out, _ = run_query_inproc("detection-completeness", "--sp-type", sp, "--distance-pc", "10",
                                            "--app-mag", "15")
            with self.subTest(sp):
                self.assertEqual(code, 0)
                self.assertEqual((out["host_class"], out["star_placement"]["status"], out["star_mass_solar"],
                                  out["star_radius_solar"]), (None, st, m, None))
                self.assertTrue(all(not x["applicable"] for x in out["methods"]))
                self.assertTrue(out["assumptions"]["out_of_domain"])
                self.assertIn("--star-mass-solar", out["methods"][0]["note"])

    def test_lhs_288_s1_radius(self):
        code, out, _ = run_query_inproc("detection-completeness", "--sp-type", "M5.5V", "--distance-pc", "4.8",
                                        "--app-mag", "13.9")
        self.assertEqual(out["star_radius_solar"], 0.156)

    def test_wolf_359_catalog_tier_computes(self):                         # acceptance 5 (cross-subcommand)
        out = self._star(self._sl("M6.5Ve", "Fl*"), catalog=[dict(_WOLF_ROW, aliases=["X"])])
        self.assertEqual((out["star_mass_provenance"], out["star_placement"]["status"]), ("catalog", "boundary"))
        self.assertTrue(out["methods"][0]["applicable"])                   # a tier mass computes

    def test_trappist_archive_youth(self):                                 # acceptance 5: archive youth rule
        out = self._star(self._sl("M8V"), arch={"mass_solar": 0.0898, "radius_solar": 0.1192}, catalog=[],
                         extra=["--age-lo-gyr", "0.3", "--age-hi-gyr", "1", "--age-basis", "membership"])
        pl = out["star_placement"]
        self.assertEqual((pl["basis"], pl["basis_unknown"], pl["cut_msun"], pl["status"], pl["reading"]),
                         ("archive", True, 0.095062, "boundary", "le_x"))
        self.assertEqual(out["star_radius_solar"], 0.1192)                 # ruling 95: the archive radius
        self.assertTrue(all(m.get("limit_direction") == "upper_bound" for m in out["methods"]))
        self.assertEqual(out["star_radius_bound_note"], detection.NOTE_RADIUS_NO_BOUND)
        self.assertIn(query.NOTE_DC_ARCHIVE_BASIS, out["notes"])

    def test_denis_archive_null_radius_branch(self):
        out = self._star(self._sl("L1.5", "BD*", vmag=None), arch={"mass_solar": 0.075, "radius_solar": None},
                         catalog=[], extra=["--app-mag", "15"])
        self.assertEqual((out["host_class"], out["star_mass_solar"], out["star_placement"]["status"]),
                         (None, 0.075, "boundary"))
        self.assertTrue(all(not m["applicable"] for m in out["methods"]))

    def test_au_mic_activity_young_no_flag(self):
        out = self._star(self._sl("M1VeBa1"), arch={"mass_solar": 0.635, "radius_solar": 0.75}, catalog=[],
                         extra=["--activity", "young"])
        self.assertEqual((out["star_placement"]["status"], out["star_placement"]["youth_flag"]), ("stellar", False))

    def test_procyon_catalog_not_applied(self):                             # pre-fire ruling 7
        out = self._star(self._sl("F5IV-V+DQZ", "SB*"),
                         catalog=[{"main_id": "X", "mass_solar": 1.478, "mass_basis": "dynamical"}])
        self.assertEqual((out["host_class"], out["star_mass_solar"], out["catalog_mass_not_applied"]),
                         ("subgiant", None, True))
        self.assertIn(query.NOTE_DC_CATALOG_NOT_APPLIED, out["notes"])

    def test_tt_star_pre_ms_branch(self):                                  # RX J0506.2+0439
        out = self._star(self._sl("M4.5V", "TT*"), catalog=[])
        self.assertEqual((out["star_placement"]["pre_ms"], out["star_placement"]["status"], out["star_mass_solar"]),
                         (True, "boundary", 0.184))
        self.assertTrue(all(not m["applicable"] for m in out["methods"]))

    def test_seed_is_the_default_catalog(self):
        sl = {"main_id": "* alf CMa", "sp_type": "A0mA1Va", "otype": "SB*", "vmag": -1.46, "parsecs": 2.64,
              "designations": {"NAME": "Sirius"}}
        out = self._star(sl)
        self.assertEqual((out["star_mass_provenance"], out["star_mass_solar"]), ("catalog", 2.063))


# ═══════════════════════════════════ D. the census ══════════════════════════════════════════════════
class CensusTest(unittest.TestCase):
    def test_status_by_type(self):                                         # acceptance 6
        from core import shared
        for sp, exp in (("L6.5", True), ("L5V", False), ("L3.5", False), ("L5gamma", False), ("M8V", False),
                        ("L7", True), ("L9pec", True), ("T6", True), ("Y0", True), ("M7", False), ("DA2", False)):
            self.assertEqual(placement.is_substellar_type(shared.parse_spectral_type(sp)), exp, sp)

    def test_label_and_note(self):
        from core import databases
        self.assertIn("L6", databases.NOTE_CENSUS_PLACEMENT.replace("later than L5", "L6"))
        self.assertIn("by spectral type", databases.NOTE_CENSUS_PLACEMENT)


if __name__ == "__main__":
    unittest.main()


class ComposedAlphaCenTest(unittest.TestCase):                             # §13.5 M9
    """The composed α Cen A / B standoffs through the S1-M₁ orbit selection and recompute_sma_kepler3: the catalog
    masses keep the standoffs byte-identical; the SMA rests only on the preferred masses (a ∝ M_tot^(1/3) at the
    observed period), so S1's M₁ moves it by floating point at most (WB's R7: relative ≤ 1e-12)."""

    def test_standoffs_and_sma(self):
        import math
        from core import exclusion_system as es, stellar_mass_tables as smt
        sols = [{"companion": {"mass_ratio_q": 0.84}, "period_d": 29174.0, "eccentricity": 0.524,
                 "source": "sb9", "grade": "b"}]
        m = {"alpha Centauri": {"main_id": "* alf Cen", "sp_type": "G2V", "designations": {"HD": "HD 128620"}},
             "* alf Cen B": {"main_id": "* alf Cen B", "sp_type": "K1V", "otype": "star",
                             "designations": {"HD": "HD 128621"}}}
        with mock.patch("core.databases.compute_simbad_lookup", _fake_simbad(m)), \
                mock.patch("core.binary.binary_orbit", lambda **k: {"solutions": sols}), \
                mock.patch("core.databases.fetch_star_otypes", lambda *a, **k: None):
            comps, _notes, _meta = es._resolve_system_from_star("alpha Centauri", smt.load_mass_catalog(None))
        r = es.compose_exclusion_system(comps, alpha=0.4)
        rex = {c["id"]: c["r_ex_au"] for z in r["zones"] for c in z["components"]}
        self.assertEqual(rex["* alf Cen"], 48.966852301574924)
        self.assertEqual(rex["* alf Cen B"], 45.72136239364217)
        sma = comps[0]["sma_au"]
        expect = ((1.079 + 0.909) * (29174.0 / 365.25) ** 2) ** (1.0 / 3.0)
        self.assertTrue(math.isclose(sma, expect, rel_tol=1e-12), (sma, expect))


class BinaryIdentityTest(unittest.TestCase):                                # §13.5 C14
    def _orbit(self, sp):
        sl = {"main_id": "HD X", "sp_type": sp, "ra": 1.0, "dec": 2.0, "plx_value": 2.0, "designations": {}}
        with mock.patch("core.databases.simbad_lookup_ex", return_value=(sl, False)), \
                mock.patch("core.binary._sb9_solutions", lambda *a, **k: ([], None)), \
                mock.patch("core.binary._wds_orb6_solutions", lambda *a, **k: []):
            return binary.binary_orbit(star="HD X")["identity"]

    def test_class_token_and_flag(self):
        ident = self._orbit("O9.5II-III(n)")                                 # HD 37737
        self.assertEqual((ident["lum_class_token"], ident["s1_class_v_flag"], ident["m1_null_reason"]),
                         ("II-III", True, None))
        ident = self._orbit("O7Iafpvar")                                     # 29 CMa
        self.assertEqual((ident["lum_class_token"], ident["s1_class_v_flag"]), ("Ia", True))
        ident = self._orbit("G2V")
        self.assertEqual((ident["s1_class_v_flag"], ident["lum_class_token"]), (True, "V"))
        self.assertEqual(self._orbit("DA2")["s1_class_v_flag"], False)
        self.assertEqual(self._orbit("A")["m1_null_reason"], "letter_only_type")


class Cp5FixesTest(unittest.TestCase):
    """CP5 (`/code-review high`, 2026-10-16) findings, pinned."""

    def test_undetermined_member_merges_without_a_type_error(self):      # #1
        code, out, _ = run_query_inproc("exclusion-system", "--component", "id=A,mass=1.0,sp_type=G2V,pair=AB,sma=5",
                                        "--component", "id=B,sp_type=L3,pair=AB,sma=5")
        self.assertEqual(code, 0, out)
        c = _comps(out)
        self.assertEqual(c["B"]["domain"], ew.UNDETERMINED_NO_MASS)
        self.assertIsNotNone(c["A"]["r_ex_au"])

    def test_log_l_override_reroutes_every_path(self):                  # #2 / #10
        code, out, _ = run_query_inproc("exclusion-boundary", "--spectral-type", "M9V", "--luminosity-lsun", "1e-5")
        self.assertEqual((out["domain"], out["r_ex_au"], out["placement"]["status"]),
                         (ew.WINDLESS, None, "substellar"))
        self.assertIs(query._WINDLESS_PLACED_KW["domain"], ew.WINDLESS)
        self.assertIsNone(ew.placed_domain_kw({"status": "boundary"}))

    def test_undetermined_tier_matches_across_subcommands(self):         # #3
        code, out, _ = run_query_inproc("exclusion-system", "--component", "id=B,sp_type=L3,mass_loss_msun_yr=1e-14")
        self.assertEqual(_comps(out)["B"]["mass_loss_tier"], "noncoronal_row")

    def test_no_orbit_note_kept(self):                                    # #4
        stab = binary.stability_from_solutions("X", {"sp_type": None}, [], ["gaia-nss", "sb9"])
        out = binary.apply_primary_directions(stab, None, None, None, "no_simbad_lookup")
        self.assertTrue(out["note"].startswith("no orbital solution found"))
        self.assertNotIn("m1_null_reason", out)

    def test_l_component_lum_is_not_an_inference_route(self):             # #5
        code, out, _ = run_query_inproc("exclusion-system", "--component", "id=B,sp_type=L3,lum=0.01")
        c = _comps(out)["B"]
        self.assertEqual((c["domain"], c["mass_solar"], c["r_ex_au"]), (ew.UNDETERMINED_NO_MASS, None, None))

    def test_a_otype_one_lookup_and_disclosed_fallback(self):            # #7
        from core import exclusion_system as es
        head = {"main_id": "GJ 65", "otype": "**"}
        with mock.patch.object(es, "resolve_star_identity",
                               return_value=({"main_id": "GJ 65 A", "otype": "TT*"}, {"main_id": "GJ 65"}, None,
                                             None)) as m:
            ot, pre, note = es._a_otype(head)
        self.assertEqual((ot, note, m.call_count), ("TT*", None, 1))
        self.assertEqual((pre["candidate"], pre["answer"][0]["main_id"]), ("GJ 65 A", "GJ 65 A"))
        with mock.patch.object(es, "resolve_star_identity",
                               return_value=(None, None, None, {"error": "x", "component_a_status": "timeout"})):
            ot, pre, note = es._a_otype(head)
        self.assertEqual((ot, pre), ("**", None))
        self.assertIn("did not resolve", note)

    def test_t_dwarf_flame_degrade_surfaced(self):                         # #8
        sim = {"GJ 229 B": {"main_id": "GJ 229 B", "sp_type": "T7pec", "otype": "BD*", "designations": {}}}
        with mock.patch("core.databases.compute_simbad_lookup", _fake_simbad(sim)), \
                mock.patch("core.binary.gaia_source_id_from_designations", lambda d: "1"), \
                mock.patch("core.catalog.gaia_astrophysical",
                           lambda **k: {"error": "x", "gaia_bound_reason": "timeout"}):
            r = _run_boundary(star="GJ 229 B", alpha=0.4)
        self.assertEqual((r["domain"], r["flame_status"]), (ew.WINDLESS, "timeout"))

    def test_detection_branch_names_its_cause(self):                       # #9
        code, out, _ = run_query_inproc("detection-completeness", "--sp-type", "Q9", "--distance-pc", "10",
                                        "--app-mag", "10")
        self.assertEqual(code, 1)
        code, out, _ = run_query_inproc("detection-completeness", "--sp-type", "O3V", "--star-mass-solar", "70",
                                        "--distance-pc", "10", "--app-mag", "10")
        self.assertTrue(out["methods"][0]["note"].startswith("host radius null"))
        code, out, _ = run_query_inproc("detection-completeness", "--sp-type", "M", "--distance-pc", "10",
                                        "--app-mag", "10")
        self.assertIn("letter-only", out["methods"][0]["note"])


class Cp6FixesTest(unittest.TestCase):
    """CP6 (`/code-review high`, the whole diff, 2026-10-16) findings, pinned."""

    def test_mks_lazy_and_marker_only_when_reached(self):               # #1
        from core import stellar_mass, stellar_mass_tables as smt
        calls = {"n": 0}

        def _mks():
            calls["n"] += 1
            return {"status": "unreachable", "mass": None}
        md = {}
        m, prov, _n = stellar_mass.resolve_component_mass(
            {"name": "* alf Cen B", "designations": {"x": "* alf Cen B"}, "mks": _mks},
            smt.load_mass_catalog(None), allow_flame=False, detail_out=md)
        self.assertEqual((m, prov, calls["n"]), (0.909, "catalog", 0))
        self.assertNotIn("twomass_status", md)
        md = {}
        m, prov, note = stellar_mass.resolve_component_mass({"name": "X", "sp_type": "M4V", "mks": _mks},
                                                            None, allow_flame=False, detail_out=md)
        self.assertEqual((m, calls["n"], md.get("twomass_status")), (None, 1, "unreachable"))

    def test_planetary_minimum_stays_out_of_multiplicity(self):         # #2
        hot_jupiter = binary._with_class(binary.companion_mass_from_sb1(0.1, 3.0, 0.0, 1.0))
        self.assertEqual(hot_jupiter["class"], binary.CLASS_MIN_UNDETERMINED)
        self.assertTrue(binary.is_planetary_companion(hot_jupiter))
        sol = {"source": "sb9", "companion": hot_jupiter}
        self.assertFalse(binary.is_orbit_solution(sol))
        self.assertFalse(binary.is_planetary_companion(binary._with_class(
            binary.companion_mass_from_sb1(6.0, 9.9448, 0.25, 1.46))))

    def test_mirror_warning_goes_to_stderr(self):                         # #4
        import contextlib
        import io
        from core import db, ms_reference_tables as mrt
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(mrt, "s1_rows", side_effect=mrt.Cr30DataError("x")), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(db.seed_cr30_mirrors(None), {})
        self.assertEqual(out.getvalue(), "")
        self.assertIn("CR-30 mirror seed skipped", err.getvalue())

    def test_no_parallax_no_2mass_lookup(self):                            # #5
        from core import twomass
        with mock.patch.object(twomass, "resolve", side_effect=AssertionError("2MASS looked up")):
            r = regions.compute_star_system_regions_from_simbad(
                {"main_id": "X", "sp_type": "M4V", "teff": 3200.0, "vmag": 12.0, "plx_value": None})
        self.assertNotIn("twomass_status", r)
        self.assertIn("error", r)

    def test_exclusion_system_log_l_override_reads_the_region_l(self):    # #6
        from core import exclusion_system as es
        self.assertIsNone(es._override_lum({"sp_type": "K1V"}))
        with mock.patch("core.regions.compute_star_system_regions_from_simbad",
                        return_value={"bcLuminosity": 3e-5}):
            self.assertEqual(es._override_lum({"main_id": "X", "sp_type": "M9.5V"}), 3e-5)
        c = {"id": "X", "mass_solar": 0.08, "mass_provenance": "catalog", "sp_type": "M9.5V",
             "_cr30": {"catalog_row": {"mass_solar": 0.08, "mass_basis": "dynamical"}, "lum": 3e-5}}
        pl = es._component_placement(c, None)
        self.assertEqual((pl["status"], pl["conflict_flag"]), ("substellar", True))

    def test_exclusion_system_topics_per_call(self):                      # #10
        code, out, _ = run_query_inproc("exclusion-system", "--component", "id=A,mass=0.3")
        self.assertEqual(list(out["cr30_disclosures"]), ["hbl"])
        code, out, _ = run_query_inproc("exclusion-system", "--component", "id=A,mass=0.3,class=M4V")
        self.assertEqual(len(out["cr30_disclosures"]), 6)


class LivePrecheckFixesTest(unittest.TestCase):
    """Stage-6 live pre-check (plan §10, 2026-10-16) findings, pinned."""

    def test_pre_ms_reports_the_sized_cut(self):                          # RX J0506.2+0439 at 0.05–0.1 Gyr
        pl = placement.place_resolved(0.4631, "spectral_type_table", sp_type="M4.5V", otype="TT*",
                                      otype_source="simbad", call_age=_age(0.05, 0.1))
        self.assertEqual((pl["pre_ms"], pl["status"], pl["reading"], pl["cut_t_lo_gyr"]),
                         (True, "boundary", "le_x", 0.05))
        self.assertAlmostEqual(pl["cut_msun"], 0.163074, places=6)

    def test_flagged_sb1_withholds_the_caveat_on_every_surface(self):     # HIP 76901 at 0.1 Gyr
        comp = binary._with_class(binary.companion_mass_from_sb1(18.6, 10.0, 0.26, 0.184))
        out = {"elements": {"m1_solar": 0.184, "m2_solar": comp["m2_solar"], "mass_provenance_a": "binary_orbit_m1",
                            "mass_provenance_b": "binary_orbit_sb1_min"},
               "selected_solution": {"source": "sb9", "companion": comp},
               "resolution_notes": [binary.NOTE_SB1_MIN_RESOLUTION]}
        binary.apply_primary_directions(out, "dM4.5", None, _age(0.1), None)
        c = out["selected_solution"]["companion"]
        self.assertEqual((c["class"], c["sb1_caveat_withheld"], c["m2_direction"]),
                         (binary.CLASS_MIN_UNDETERMINED, True, "le"))
        self.assertNotIn("true M₂ ≥", c["caveat"])
        self.assertEqual(out["resolution_notes"], [binary.NOTE_SB1_MIN_RESOLUTION_FLAGGED])
        self.assertIn("true M₂ ≥", comp["caveat"])                          # the input orbit is not mutated

    def test_flagged_true_mass_class_on_the_selected_solution(self):      # LP 120-4 at 0.1 Gyr
        comp = {"method": "astrom", "m2_solar": 0.0704, "class": binary.CLASS_BOUNDARY}
        out = {"elements": {"m1_solar": 0.184, "m2_solar": 0.0704, "mass_provenance_a": "binary_orbit_m1",
                            "mass_provenance_b": "binary_orbit_m2"},
               "selected_solution": {"source": "gaia-nss:orbital", "companion": comp}}
        binary.apply_primary_directions(out, "M4.5Ve", None, _age(0.1), None)
        self.assertEqual(out["selected_solution"]["companion"]["class"], out["elements"]["m2_class"])

    def test_unflagged_primary_leaves_the_selected_solution(self):
        comp = {"method": "spec-min", "m2_solar": 0.078188, "caveat": "x", "class": "stellar"}
        sol = {"source": "sb9", "companion": comp}
        out = {"elements": {"m1_solar": 1.46, "m2_solar": 0.078188, "mass_provenance_a": "binary_orbit_m1",
                            "mass_provenance_b": "binary_orbit_sb1_min"},
               "selected_solution": sol, "resolution_notes": [binary.NOTE_SB1_MIN_RESOLUTION]}
        binary.apply_primary_directions(out, "F2V", None, _age(0.1), None)
        self.assertEqual(out["selected_solution"]["companion"], comp)
        self.assertEqual(out["resolution_notes"], [binary.NOTE_SB1_MIN_RESOLUTION])

    def test_denis_branch_note_names_the_placement(self):                 # CR-30.7 C, DENIS-P J082303.1-491201
        out = DetectionTest()._star({"main_id": "X", "sp_type": "L1.5", "otype": "BD*", "vmag": None,
                                     "parsecs": 5.0, "designations": {}},
                                    arch={"mass_solar": 0.075, "radius_solar": None}, catalog=[],
                                    extra=["--app-mag", "15"])
        note = out["methods"][0]["note"]
        self.assertTrue(note.startswith("host placement: "), note)
        self.assertIn("boundary", note)
        self.assertIn("host radius null", note)

    def _dossier(self, reg, **kw):
        from core import report
        from tests.test_report import _patched
        with _patched(regions_result=reg):
            return report.build_system_dossier("Tau Ceti", sections=["identity", "regions"], fmt="json", **kw)

    def _proxima_reg(self):
        from core import twomass
        from tests.test_cr30_luminosity import _PROXIMA, _PROXIMA_ID, _tm
        tm = _tm(5.357, 4.384, ids=(_PROXIMA_ID,))
        with mock.patch.object(twomass, "resolve", return_value=tm):
            return regions.compute_star_system_regions_from_simbad(dict(_PROXIMA))

    def test_dossier_regions_name_the_route(self):                         # CR-30.3 / 30.4 (Lalande 21185)
        reg = self._proxima_reg()
        r = self._dossier(reg)["data"]["regions"]
        self.assertEqual(r["lum_route"], reg["lum_route"])
        for k in ("lum_route_reason", "sp_type_read", "s1_rows", "twomass", "v_minus_j"):
            if k in reg:
                self.assertEqual(r[k], reg[k], k)
        mb = r["mass"]
        self.assertEqual((mb["mass_provenance"], mb["mass_route"], mb["mass_relation"], mb["m_ks"]),
                         ("ms_mks_relation", "mks", "Mann2019_n5", reg["m_ks"]))
        self.assertIn("mks_binary_disclosure", mb)
        self.assertEqual(r["stellar"]["radius_from_mass_relation"], "S1_sorted_by_mass")

    def test_dossier_manual_mass_outside_spans_names_the_nulls(self):     # tau Cet --mass-solar 0.077 / 60
        for m in (0.077, 60.0):
            with self.subTest(m=m):
                r = self._dossier(self._proxima_reg(), mass_solar=m)["data"]["regions"]
                st = r["stellar"]
                self.assertIsNone(st["stellar_radius"])
                self.assertTrue(st["radius_from_mass_null_reason"])
                self.assertIsNone(st["luminosity_from_mass"])
                self.assertTrue(st["luminosity_from_mass_null_reason"])
                self.assertEqual(r["mass"]["mass_provenance"], "manual")
                self.assertIsNone(r["mass"]["mass_route"])                # a tier above inference

    def test_stellar_evolution_labels_the_lifetime_end_point(self):       # CR-30.5 acceptance 1
        from core import equations
        r = equations.compute_stellar_evolution(0.62)
        self.assertAlmostEqual(r["t_ms_gyr"], 50.31, places=2)
        self.assertEqual(r["ms_lifetime_end_point"], "interpolated_1e-2_to_1e-4")
        self.assertEqual(equations.compute_stellar_evolution(1.0)["ms_lifetime_end_point"], "first_Xc_lt_1e-4")

    def test_dossier_failed_region_step_names_the_mks_route(self):        # SCR J1845-6357 (no Teff)
        from core import report, stellar_mass
        out = report._dossier_mass_route_fields(
            {"mass_solar": 0.07925, "mass_provenance": stellar_mass.MS_MKS},
            {"error": "Temperature not available", "m_ks": 10.4948, "mks": {"mass": 0.07925, "m_ks": 10.4948}})
        self.assertEqual((out["mass_route"], out["mass_relation"], out["m_ks"]), ("mks", "Mann2019_n5", 10.4948))
        self.assertIn("mks_binary_disclosure", out)
        catalog = report._dossier_mass_route_fields({"mass_solar": 0.39, "mass_provenance": "catalog"},
                                                    {"mass_route": "luminosity", "mass_relation": "Eker2018_inverted"})
        self.assertEqual((catalog["mass_route"], catalog["mass_relation"]), (None, None))


class RegateFixesTest(unittest.TestCase):
    """WB's re-gate (MSG 366, 2026-10-17) findings F-1 … F-9, pinned."""

    _HIP = {"main_id": "HIP 76901", "sp_type": "M4.5V", "plx_value": 50.0, "teff": 3100.0, "vmag": 12.0,
            "designations": {}}
    _SB1_SEL = {"m1_solar": 0.184, "m2_solar": 0.044186, "mass_prov_a": "binary_orbit_m1",
                "mass_prov_b": "binary_orbit_sb1_min", "notes": [binary.NOTE_SB1_MIN_RESOLUTION],
                "selected_solution": {"source": "sb9", "companion": {"method": "spec-min",
                                                                     "mass_function": 0.0016567908}}}

    def test_sb1_m2_resolved_at_the_settled_m1(self):                      # F-1 (b), Greg's ruling
        self.assertAlmostEqual(binary.sb1_m2_at(self._SB1_SEL, 0.25865), 0.0545752, places=6)
        self.assertEqual(binary.sb1_m2_at(self._SB1_SEL, 0.184), 0.044186)       # the orbit's own M₁: unchanged
        self.assertEqual(binary.sb1_m2_at(dict(self._SB1_SEL, mass_prov_b="binary_orbit_m2"), 0.25865), 0.044186)

    def test_reduced_record_takes_the_mks_tier(self):                       # F-1 (a): HIP 76901
        from core import stellar_mass

        def _sl(name):
            return dict(self._HIP) if name == "HIP 76901" else {"error": "No results found for 'x'"}
        mks = {"status": "ok", "mass": 0.25865, "m_ks": 8.0, "ks": 6.5}
        with mock.patch("core.databases.compute_simbad_lookup", side_effect=_sl) as look, \
                mock.patch("core.regions.mks_route", return_value=mks) as route:
            m1, prov_a, m2, prov_b, _n = stellar_mass.resolve_binary_components(
                {"main_id": "HIP 76901", "sp_type": "M4.5V", "designations": {}}, self._SB1_SEL, None,
                allow_flame=False)
        self.assertEqual((m1, prov_a, prov_b), (0.25865, stellar_mass.MS_MKS, "binary_orbit_sb1_min"))
        self.assertAlmostEqual(m2, 0.0545752, places=6)
        self.assertEqual(route.call_args.args[0]["plx_value"], 50.0)            # the widened record reached it
        self.assertIn(mock.call("HIP 76901"), look.call_args_list)

    def test_non_ms_class_keeps_heads_dossier(self):                        # F-5: Sirius B (DA1.9)
        from core import report
        from tests.test_report import _patched
        sb = {"main_id": "* alf CMa B", "sp_type": "DA1.9", "teff": 25000.0, "vmag": 8.44, "plx_value": 374.5,
              "designations": {}}
        not_ms = {"error": "Spectral type 'DA1.9' is not a main-sequence class (O B A F G K M) — cannot "
                           "determine star system region."}
        with _patched(simbad=sb, regions_result=not_ms):
            d = report.build_system_dossier("Sirius B", sections=["identity", "regions"], fmt="json",
                                            mass_solar=1.018)["data"]
        self.assertNotIn("stellar", d.get("regions") or {})
        self.assertFalse((d.get("regions") or {}).get("region_step_failed"))
        with _patched(simbad=dict(sb, sp_type="M4V"), regions_result={"error": regions.ERR_NO_TEFF}):
            d = report.build_system_dossier("X", sections=["identity", "regions"], fmt="json",
                                            mass_solar=0.2)["data"]
        self.assertTrue(d["regions"]["region_step_failed"])                    # a missing input still reports

    def test_compare_stars_mks_never_moves_the_archive(self):               # F-2: GJ 1061
        from core import databases as dbs
        sl = {"main_id": "GJ 1061", "sp_type": "M5.5V", "teff": 2950.0, "vmag": 13.03, "plx_value": 271.9,
              "designations": {}}
        with mock.patch.object(dbs, "compute_simbad_lookup", return_value=sl), \
                mock.patch.object(dbs, "_get_archive_query_params", return_value=("hostname", "GJ 1061")), \
                mock.patch.object(dbs, "_query_tap", return_value=[{"st_teff": None, "st_rad": 0.156,
                                                                    "st_mass": 0.12, "st_lum": None}]), \
                mock.patch("core.regions.compute_star_system_regions_from_simbad",
                           return_value={"error": regions.ERR_NO_TEFF, "mass_mks_solar": 0.12759}), \
                mock.patch.object(dbs, "_flame_mass_for", return_value=(None, None)), \
                mock.patch.object(dbs, "compute_hypatia_data", return_value={}):
            s = dbs.compare_stars(["GJ 1061", "Sol"])["stars"][0]
        self.assertEqual((s["mass"], s["radius"]), (0.12, 0.156))
        self.assertEqual((s["mass_solar"], s["mass_provenance"]), (0.12759, "ms_mks_relation"))

    def test_mks_single_body_keeps_the_region_l(self):                      # F-9: EZ Aqr at β 0.5
        from core import exclusion_system as es, stellar_mass
        sl = {"main_id": "EZ Aqr", "sp_type": "M5V", "otype": "Fl*", "designations": {}}
        with mock.patch.object(es, "_mks_for", return_value={"status": "ok", "mass": 0.1, "m_ks": 9.0}), \
                mock.patch("core.regions.compute_star_system_regions_from_simbad",
                           return_value={"bcLuminosity": 0.0036345}), \
                mock.patch.object(es, "resolve_star_wind", return_value={"otypes": None, "status": None,
                                                                          "cls_kw": {"wind_otype_source": None}}), \
                mock.patch.object(es, "_cr26_identity", return_value={}), \
                mock.patch.object(es, "a_prefetch", return_value=None):
            comp, mass, domain, _n = es._single_body_component(sl, None, "EZ Aqr", status_out={})
        self.assertEqual((mass, comp["mass_provenance"], domain), (0.1, stellar_mass.MS_MKS, ew.MAIN_SEQUENCE))
        self.assertEqual(comp["luminosity_lsun"], 0.0036345)

    def test_null_mass_names_its_reason(self):                              # F-3: acc-4.3
        code, out, _ = run_query_inproc("exclusion-system", "--component", "id=X,lum=0.0001")
        self.assertEqual(code, 1)
        self.assertIn("below S1's last row (M9.5V, log L -3.57)", out["error"])
        self.assertIn("never clamped", out["error"])
        self.assertNotIn("lum=<L☉>", out["error"])

    def test_l_type_no_mass_carries_the_type_read(self):                    # F-6: acc-2.5b
        code, out, _ = run_query_inproc("exclusion-boundary", "--spectral-type", "L3beta", "--alpha", "0.4")
        self.assertEqual(code, 0)
        self.assertEqual((out["sp_type_raw"], out["sp_type_read"], out["gravity_designation"]),
                         ("L3beta", "L3", "beta"))

    def test_detection_explicit_branch_keeps_heads_fields(self):            # F-7: acc-2.5c
        code, out, _ = run_query_inproc("detection-completeness", "--sp-type", "L3beta", "--distance-pc", "10",
                                        "--app-mag", "15")
        self.assertEqual(code, 0)
        a = out["assumptions"]
        for k in ("albedo", "mag_domain", "monotonicity", "sma_grid_au"):
            self.assertIsNotNone(a.get(k), k)
        self.assertEqual(a["monotonicity"], detection._MONOTONICITY)
        by = {m["method"]: m for m in out["methods"]}
        self.assertFalse(any(m["applicable"] for m in by.values()))
        self.assertIsNotNone(by["rv"]["baseline_yr"])
        self.assertIsNotNone(by["astrometry"]["baseline_yr"])
        self.assertIn("contrast_band", by["imaging"])
        self.assertIn("mechanism_caveat", by["imaging"])

    def test_forced_2mass_failure_withholds_only_the_region_l(self):        # F-8: acc-3.4b
        from core import databases, twomass
        from tests.test_cr30_luminosity import _PROXIMA
        with mock.patch.object(twomass, "resolve", return_value={"status": "unreachable", "ids": [], "jks": None}), \
                mock.patch.object(databases, "compute_simbad_lookup", return_value=dict(_PROXIMA)), \
                mock.patch.object(databases, "compute_hypatia_data", return_value={"h": 1}):
            code, out, _ = run_query_inproc("star-regions", "--star", "Proxima Centauri")
        self.assertEqual((code, out["twomass_status"], out["bcLuminosity"]), (0, "unreachable", None))
        ref = regions.compute_star_system_regions(11.13, -2.0, 3000.0, 768.0665)
        for k in ("plx", "trigParallax", "parsecs", "lightYears", "vmag", "absMagnitude", "bond_albedo",
                  "sunlight_intensity", "planetaryTemperature", "planetaryTemperatureC", "planetaryTemperatureF",
                  "temp"):
            self.assertEqual(out[k], ref[k], k)
        self.assertEqual((out["spectral_type"], out["hypatia"]), ("M5.5Ve", {"h": 1}))
        self.assertNotIn("hzil", out)

    def test_2mass_degrade_dossier_keeps_the_mass(self):                   # CP (MSG 366 fold) #2
        from core import report, twomass
        from tests.test_report import _patched
        deg = {"error": twomass.NOTE_DEGRADE["unreachable"], **twomass.degrade_fields("unreachable")}
        with _patched(simbad=dict(self._HIP), regions_result=deg):
            d = report.build_system_dossier("X", sections=["identity", "regions"], fmt="json",
                                            mass_solar=0.2)["data"]
        self.assertTrue(d["regions"]["region_step_failed"])
        self.assertTrue(regions.is_input_failure(deg))
        self.assertFalse(regions.is_input_failure({"error": "Spectral type 'DA1.9' is not a main-sequence class"}))

    def test_printed_companion_follows_the_resolved_m2(self):              # CP (MSG 366 fold) #3
        comp = binary._with_class(binary.companion_mass_from_sb1(18.6, 10.0, 0.26, 0.184))
        m2 = binary.sb1_m2_at(dict(self._SB1_SEL, selected_solution={"companion": comp}), 0.25865)
        out = {"elements": {"m1_solar": 0.25865, "m2_solar": m2, "mass_provenance_a": "ms_mks_relation",
                            "mass_provenance_b": "binary_orbit_sb1_min"},
               "selected_solution": {"source": "sb9", "companion": comp}}
        binary.apply_primary_directions(out, "M4.5V", None, None, None)
        c = out["selected_solution"]["companion"]
        self.assertEqual((c["m1_solar"], c["m2_solar"]), (0.25865, m2))
        self.assertEqual(c["class"], binary.classify_companion(m2, minimum=True)["class"])
        self.assertEqual(comp["m1_solar"], 0.184)                              # the input orbit is not mutated

    def test_every_no_mass_spectral_type_output_carries_the_type_read(self):  # CP (MSG 366 fold) #5
        for sp in ("K0III", "DA2", "T5"):
            with self.subTest(sp):
                code, out, _ = run_query_inproc("exclusion-boundary", "--spectral-type", sp, "--alpha", "0.4")
                self.assertEqual((code, out["sp_type_raw"]), (0, sp))


class SimbadFailLoudTest(unittest.TestCase):
    """WB's re-gate of the fix round (MSG 368) O-1: a failed SIMBAD lookup on the binary paths fails loud (CR-30.3's
    convention) — never the orbit's mass in silence; SIMBAD's own "no results" stays as before."""

    _SEL = RegateFixesTest._SB1_SEL
    _REDUCED = {"main_id": "HIP 76901", "sp_type": "M4.5V", "designations": {}}
    _FAIL = {"error": "SIMBAD query failed after 3 attempts: timed out"}
    _NONE = {"error": "No results found for 'HIP 76901 B'"}

    def _resolve(self, a, b, catalog=None):
        from core import stellar_mass
        st = {}
        with mock.patch("core.databases.compute_simbad_lookup",
                        side_effect=lambda n: b if n.endswith(" B") else a), \
                mock.patch("core.regions.mks_route", return_value={"status": "ok", "mass": 0.25865}):
            res = stellar_mass.resolve_binary_components(self._REDUCED, self._SEL, catalog, allow_flame=False,
                                                         status_out=st)
        return res, st

    def test_failed_primary_widening_is_marked(self):
        (m1, prov_a, m2, _pb, _n), st = self._resolve(self._FAIL, self._NONE)
        self.assertEqual((m1, prov_a, m2), (0.184, "binary_orbit_m1", 0.044186))     # the orbit's, now marked
        self.assertEqual((st.get("not_authoritative"), st.get("simbad_status_a")), (True, "failed"))
        self.assertNotIn("simbad_status_b", st)                                      # "no results" stays as before

    def test_failed_companion_lookup_is_marked(self):
        _res, st = self._resolve(dict(RegateFixesTest._HIP), self._FAIL)
        self.assertEqual((st.get("not_authoritative"), st.get("simbad_status_b")), (True, "failed"))
        self.assertNotIn("simbad_status_a", st)

    def test_a_measured_companion_mass_needs_no_marker(self):
        cat = _tmp_catalog([{"main_id": "HIP 76901 B", "mass_solar": 0.09, "mass_basis": "dynamical"}])
        from core import stellar_mass_tables
        _res, st = self._resolve(dict(RegateFixesTest._HIP), self._FAIL,
                                 catalog=stellar_mass_tables.load_mass_catalog(cat))
        self.assertEqual(_res[3], "catalog")
        self.assertNotIn("simbad_status_b", st)
        self.assertNotIn("not_authoritative", st)

    def test_no_results_everywhere_stays_unmarked(self):
        _res, st = self._resolve(dict(RegateFixesTest._HIP), self._NONE)
        self.assertFalse({"not_authoritative", "simbad_status_a", "simbad_status_b"} & set(st))

    def test_binary_stability_auto_carries_the_marker(self):
        sol = {"source": "sb9", "period_d": 10.0, "eccentricity": 0.26, "grade": 4,
               "companion": {"method": "spec-min", "m1_solar": 0.184, "m2_solar": 0.044186,
                             "mass_function": 0.0016567908}}
        fake = {"query": "HIP 76901", "identity": dict(self._REDUCED, ra=1.0, dec=2.0), "solutions": [sol],
                "route_tried": ["sb9"]}
        with mock.patch("core.binary.binary_orbit", return_value=fake), \
                mock.patch("core.databases.compute_simbad_lookup",
                           side_effect=lambda n: self._NONE if n.endswith(" B") else self._FAIL), \
                mock.patch("core.catalog.gaia_astrophysical", return_value={"parameters": None}):
            out = binary.binary_stability_auto(star="HIP 76901")
        self.assertEqual((out["elements"]["m1_solar"], out["not_authoritative"], out["simbad_status_a"]),
                         (0.184, True, "failed"))

    def _es(self, b_answer):
        from core import exclusion_system as es, stellar_mass_tables as smt
        sols = [{"companion": {"mass_ratio_q": 0.84}, "period_d": 29174.0, "eccentricity": 0.524,
                 "source": "sb9", "grade": "b"}]
        a = {"main_id": "* alf Cen", "sp_type": "G2V", "designations": {"HD": "HD 128620"}}

        def _sl(name):
            return b_answer if name.endswith(" B") else dict(a)
        with mock.patch("core.databases.compute_simbad_lookup", side_effect=_sl), \
                mock.patch("core.binary.binary_orbit", lambda **k: {"solutions": sols}), \
                mock.patch("core.databases.fetch_star_otypes", lambda *a, **k: None):
            return es._resolve_system_from_star("alpha Centauri", smt.load_mass_catalog(None))

    def test_exclusion_system_companion_failure_is_marked(self):
        from core import exclusion_system as es
        # B's record also carries its WD / BD class here, so a failed lookup fails loud whatever tier gave the mass
        for patch_cat in (False, True):
            with self.subTest(catalog_mass=not patch_cat):
                if patch_cat:
                    with mock.patch("core.stellar_mass_tables.match_mass", return_value=None):
                        comps, notes, meta = self._es(self._FAIL)
                else:
                    comps, notes, meta = self._es(self._FAIL)
                    self.assertEqual(comps[1]["mass_provenance"], "catalog")
                self.assertEqual((meta.get("not_authoritative"), meta.get("simbad_status_b")), (True, "failed"))
                self.assertIn(es.NOTE_SIMBAD_FAILED_B.format(comp="* alf Cen B"), notes)
                self.assertFalse(any(n.startswith("companion nature not confirmed") for n in notes))
        _comps, notes, meta = self._es({"error": "No results found for '* alf Cen B'"})  # no record: as before
        self.assertNotIn("simbad_status_b", meta)
        self.assertTrue(any(n.startswith("companion nature not confirmed") for n in notes))

    def test_dossier_multiplicity_carries_the_marker(self):
        from core import report
        from tests.test_report import _patched
        sol = {"source": "sb9", "period_d": 10.0, "eccentricity": 0.26, "grade": 4,
               "companion": {"method": "spec-min", "m1_solar": 0.184, "m2_solar": 0.044186,
                             "mass_function": 0.0016567908}}
        bo = {"query": "HIP 76901", "identity": dict(self._REDUCED, ra=1.0, dec=2.0), "solutions": [sol],
              "route_tried": ["sb9"]}
        with _patched(simbad=dict(RegateFixesTest._HIP), binary_orbit_result=bo), \
                mock.patch("core.databases.compute_simbad_lookup",
                           side_effect=lambda n: self._FAIL if n.endswith(" B") else dict(RegateFixesTest._HIP)):
            d = report.build_system_dossier("HIP 76901", sections=["identity", "multiplicity"], fmt="json")["data"]
        m = d["multiplicity"]
        self.assertEqual((m.get("not_authoritative"), m.get("simbad_status_b")), (True, "failed"))

    def test_coordinate_input_failed_primary_lookup_is_marked(self):     # review #2
        sol = {"source": "sb9", "period_d": 10.0, "eccentricity": 0.26, "grade": 4,
               "companion": {"method": "spec-min", "m1_solar": 0.184, "m2_solar": 0.044186}}
        fake = {"query": "x", "identity": {"main_id": "HIP 76901", "sp_type": "M4.5V", "ra": 1.0, "dec": 2.0},
                "solutions": [sol], "route_tried": ["sb9"]}
        with mock.patch("core.binary.binary_orbit", return_value=fake), \
                mock.patch("core.databases.compute_simbad_lookup", return_value=self._FAIL):
            out = binary.binary_stability_auto(ra=1.0, dec=2.0)
        self.assertEqual((out["not_authoritative"], out["simbad_status_a"]), (True, "failed"))

    def test_a_raising_widening_lookup_is_marked(self):                  # review #8
        from core import stellar_mass
        st = {}
        with mock.patch("core.databases.compute_simbad_lookup",
                        side_effect=lambda n: self._NONE if n.endswith(" B") else (_ for _ in ()).throw(OSError("x"))):
            stellar_mass.resolve_binary_components(self._REDUCED, self._SEL, None, allow_flame=False, status_out=st)
        self.assertEqual(st.get("simbad_status_a"), "failed")
