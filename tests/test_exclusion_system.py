# tests/test_exclusion_system.py — CR-11.3 binary/multi-star exclusion-boundary composition.
#
# Offline, in-process (the --component deterministic core). Covers the Sirius (WD-guard, merged) and
# α Cen (AB-merged + Proxima-separate) hand-card anchors, the domain guard, merge-grouping, the
# prolate envelope, the in-domain-only point-mass, the degenerate single-star reproduction of
# exclusion-boundary, and validation. The live --star path is gated in test_query_exclusion_system_live.py.

import unittest
from unittest import mock

import core.exclusion_boundary as eb
import core.exclusion_system as es


def _sirius(**over):
    specs = [
        {"id": "A", "mass_solar": 2.063, "mass_provenance": "catalog", "luminosity_lsun": 25.4,
         "sp_type": "A0mA1Va", "pair": "AB", "sma_au": 19.8, "ecc": 0.59},
        {"id": "B", "mass_solar": 1.018, "mass_provenance": "catalog", "class": "wd",
         "pair": "AB", "sma_au": 19.8, "ecc": 0.59},
    ]
    return es.compose_exclusion_system(specs, **over)


def _alpha_cen(**over):
    specs = [
        {"id": "A", "mass_solar": 1.079, "luminosity_lsun": 1.5, "sp_type": "G2V",
         "pair": "AB", "sma_au": 23.6, "ecc": 0.52},
        {"id": "B", "mass_solar": 0.909, "luminosity_lsun": 0.5, "sp_type": "K1V",
         "pair": "AB", "sma_au": 23.6, "ecc": 0.52},
        {"id": "Proxima", "mass_solar": 0.122, "luminosity_lsun": 0.0017, "sp_type": "M5.5V",
         "orbits": "AB", "sma_au": 13000, "ecc": 0.5},
    ]
    return es.compose_exclusion_system(specs, **over)


class DomainGuardTest(unittest.TestCase):
    def test_class_tags_and_sp_types(self):
        self.assertEqual(es._component_domain(class_tag="wd")[0], "out_of_domain")
        self.assertEqual(es._component_domain(class_tag="brown-dwarf")[0], "out_of_domain")
        self.assertEqual(es._component_domain(class_tag="rogue")[0], "out_of_domain")
        self.assertEqual(es._component_domain(class_tag="giant")[0], "out_of_domain")
        self.assertEqual(es._component_domain(sp_type="DA2")[0], "out_of_domain")   # WD
        self.assertEqual(es._component_domain(sp_type="T5")[0], "out_of_domain")    # BD
        self.assertEqual(es._component_domain(sp_type="K0III")[0], "out_of_domain") # giant
        self.assertEqual(es._component_domain(sp_type="A0mA1Va")[0], "main_sequence")
        self.assertEqual(es._component_domain(sp_type="G2V")[0], "main_sequence")
        self.assertEqual(es._component_domain(sp_type=None)[0], "main_sequence")    # no info → MS


class SiriusAnchorTest(unittest.TestCase):
    def test_one_merged_zone_wd_guarded(self):
        r = _sirius()
        self.assertEqual(r["n_zones"], 1)
        z = r["zones"][0]
        self.assertEqual(z["status"], "merged")
        self.assertEqual(sorted(z["members"]), ["A", "B"])
        comps = {c["id"]: c for c in z["components"]}
        self.assertEqual(comps["B"]["domain"], "out_of_domain")   # WD guard withholds the sphere
        self.assertIsNone(comps["B"]["r_ex_au"])
        self.assertAlmostEqual(comps["A"]["r_ex_au"], 63.46, places=1)

    def test_prolate_envelope_breathes(self):
        r = _sirius()
        la = r["zones"][0]["long_axis_au"]
        self.assertAlmostEqual(la["periastron"], 66.1, places=0)
        self.assertAlmostEqual(la["apastron"], 73.9, places=0)
        self.assertLess(la["periastron"], la["apastron"])   # breathes with separation

    def test_point_mass_degenerates_to_A(self):
        # in-domain members only = A alone → its own sphere (the all-mass 74.5 erratum is NOT used)
        r = _sirius()
        z = r["zones"][0]
        self.assertAlmostEqual(z["point_mass_r_ex_au"], 63.46, places=1)

    def test_barycenter_uses_the_wd_real_mass(self):
        # If B's real mass were dropped the A offset (and thus long_axis) would change; check it against
        # the hand geometry offset a_A = d·M_B/(M_A+M_B) at periastron.
        r = _sirius()
        d_peri = 19.8 * (1 - 0.59)
        off_a = d_peri * 1.018 / (2.063 + 1.018)
        self.assertAlmostEqual(r["zones"][0]["long_axis_au"]["periastron"], off_a + 63.46, places=1)


class AlphaCenAnchorTest(unittest.TestCase):
    def test_two_zones_ab_merged_proxima_separate(self):
        r = _alpha_cen()
        self.assertEqual(r["n_zones"], 2)
        by_members = {tuple(sorted(z["members"])): z for z in r["zones"]}
        self.assertIn(("A", "B"), by_members)
        self.assertIn(("Proxima",), by_members)
        self.assertEqual(by_members[("A", "B")]["status"], "merged")
        self.assertEqual(by_members[("Proxima",)]["status"], "separate")

    def test_ab_per_body_and_point_mass(self):
        r = _alpha_cen()
        ab = next(z for z in r["zones"] if sorted(z["members"]) == ["A", "B"])
        comps = {c["id"]: c for c in ab["components"]}
        self.assertAlmostEqual(comps["A"]["r_ex_au"], 48.97, places=1)   # measured 1.079
        self.assertAlmostEqual(comps["B"]["r_ex_au"], 45.72, places=1)   # measured 0.909
        self.assertAlmostEqual(ab["point_mass_r_ex_au"], 62.53, places=1)  # in-domain 1.079+0.909
        self.assertAlmostEqual(ab["long_axis_au"]["periastron"], 54.1, places=0)
        self.assertAlmostEqual(ab["long_axis_au"]["apastron"], 65.4, places=0)
        self.assertAlmostEqual(ab["minor_axis_au"], 48.97, places=1)

    def test_proxima_separate_own_sphere(self):
        r = _alpha_cen()
        px = next(z for z in r["zones"] if z["members"] == ["Proxima"])
        self.assertAlmostEqual(px["point_mass_r_ex_au"],
                               eb.compute_exclusion_boundary(0.122, alpha=0.4)["r_ex_au"], places=3)


class DegenerateAndValidationTest(unittest.TestCase):
    def test_single_star_reproduces_exclusion_boundary(self):
        r = es.compose_exclusion_system([{"id": "Sol", "mass_solar": 1.0, "sp_type": "G2V"}])
        self.assertEqual(r["n_zones"], 1)
        z = r["zones"][0]
        self.assertEqual(z["status"], "separate")
        ref = eb.compute_exclusion_boundary(1.0, alpha=0.4)["r_ex_au"]
        self.assertAlmostEqual(z["long_axis_au"]["periastron"], ref, places=6)
        self.assertAlmostEqual(z["point_mass_r_ex_au"], ref, places=6)
        # and on a non-unit mass, with the same alpha
        r2 = es.compose_exclusion_system([{"id": "x", "mass_solar": 1.5, "sp_type": "F5V"}], alpha=0.45)
        self.assertAlmostEqual(r2["zones"][0]["point_mass_r_ex_au"],
                               eb.compute_exclusion_boundary(1.5, alpha=0.45)["r_ex_au"], places=6)

    def test_validation(self):
        self.assertIn("error", es.compose_exclusion_system([]))
        self.assertIn("error", es.compose_exclusion_system([{"id": "A", "mass_solar": -1}]))
        self.assertIn("error", es.compose_exclusion_system([{"id": "A", "mass_solar": 1}], alpha=0.9))
        self.assertIn("error", es.compose_exclusion_system([{"id": "A", "mass_solar": 1}], phase="bad"))

    def test_out_of_domain_component_never_sums_into_point_mass(self):
        # Sirius point-mass is A alone (2.063), NOT A+B (3.081): a windless WD mass is never summed in.
        r = _sirius()
        all_mass = eb.compute_exclusion_boundary(2.063 + 1.018, alpha=0.4)["r_ex_au"]
        self.assertNotAlmostEqual(r["zones"][0]["point_mass_r_ex_au"], all_mass, places=1)

    def test_alpha_scan_shifts_all_components(self):
        lo = _alpha_cen(alpha=1.0 / 3.0)
        hi = _alpha_cen(alpha=0.5)
        ab_lo = next(z for z in lo["zones"] if sorted(z["members"]) == ["A", "B"])
        ab_hi = next(z for z in hi["zones"] if sorted(z["members"]) == ["A", "B"])
        a_lo = next(c for c in ab_lo["components"] if c["id"] == "A")["r_ex_au"]
        a_hi = next(c for c in ab_hi["components"] if c["id"] == "A")["r_ex_au"]
        self.assertGreater(a_hi, a_lo)   # A > 1 M☉ → larger exponent → larger r_ex


class ComponentSpecTest(unittest.TestCase):
    def test_parse_and_end_to_end(self):
        r = es.compute_exclusion_system(component_specs=[
            "id=A,mass=2.063,lum=25.4,class=A0mA1Va,pair=AB,sma=19.8,ecc=0.59",
            "id=B,mass=1.018,class=wd,pair=AB,sma=19.8,ecc=0.59"])
        self.assertEqual(r["n_zones"], 1)
        self.assertAlmostEqual(r["zones"][0]["long_axis_au"]["apastron"], 73.9, places=0)

    def test_catalog_resolves_component_by_name(self):
        r = es.compute_exclusion_system(component_specs=[
            "id=Sirius A,name=* alf CMa,class=A0mA1Va,lum=25.4"])
        c = r["zones"][0]["components"][0]
        self.assertAlmostEqual(c["mass_solar"], 2.063, places=3)
        self.assertEqual(c["mass_provenance"], "catalog")

    def test_spec_errors(self):
        self.assertIn("error", es.compute_exclusion_system(component_specs=["id=A,foo=1"]))
        self.assertIn("error", es.compute_exclusion_system(component_specs=["id=A,mass=x"]))
        self.assertIn("error", es.compute_exclusion_system(component_specs=["id=A,class=G2V"]))  # no mass
        self.assertIn("error", es.compute_exclusion_system(star="Sirius",
                                                           component_specs=["id=A,mass=1"]))
        self.assertIn("error", es.compute_exclusion_system())  # neither

    def test_bad_catalog_path_loud(self):
        self.assertIn("error", es.compute_exclusion_system(
            component_specs=["id=A,mass=1"], star_mass_catalog="/nope/x.json"))


class ReviewFixTest(unittest.TestCase):
    """Regressions for the CR-11.3 code-review fixes (#1 envelope, #3 domain guard, #5 point-mass)."""

    def test_fix1_out_of_domain_offset_never_sets_long_axis(self):
        # A tiny WD on a wide orbit: its bare barycentric offset (d·M_A/M_tot) EXCEEDS the MS
        # primary's reach, but it has no sphere → long_axis must be the primary's reach, not the offset.
        r = es.compose_exclusion_system([
            {"id": "A", "mass_solar": 2.0, "sp_type": "B5V", "pair": "AB", "sma_au": 50, "ecc": 0.5},
            {"id": "B", "mass_solar": 0.1, "class": "wd", "pair": "AB", "sma_au": 50, "ecc": 0.5}])
        z = r["zones"][0]
        rA = eb.compute_exclusion_boundary(2.0, alpha=0.4)["r_ex_au"]
        d_apo = 50 * 1.5
        off_A = d_apo * 0.1 / 2.1
        off_B = d_apo * 2.0 / 2.1
        self.assertGreater(off_B, off_A + rA)                          # the trap the old code fell into
        self.assertAlmostEqual(z["long_axis_au"]["apastron"], off_A + rA, places=1)  # in-domain reach only

    def test_fix3_hot_subdwarf_out_of_domain(self):
        self.assertEqual(es._component_domain(sp_type="sdB")[0], "out_of_domain")
        self.assertEqual(es._component_domain(sp_type="sdO")[0], "out_of_domain")
        self.assertEqual(es._component_domain(sp_type="sdM3.0")[0], "main_sequence")  # cool subdwarf ~MS
        self.assertEqual(es._component_domain(sp_type="K0IV")[0], "out_of_domain")    # subgiant

    def test_fix5_point_mass_survives_beta_and_gamma(self):
        beta = es.compose_exclusion_system([
            {"id": "A", "mass_solar": 1.0, "luminosity_lsun": 1.0, "sp_type": "G2V",
             "pair": "AB", "sma_au": 20, "ecc": 0.3},
            {"id": "B", "mass_solar": 0.8, "luminosity_lsun": 0.4, "sp_type": "K2V",
             "pair": "AB", "sma_au": 20, "ecc": 0.3}], beta=0.5)
        self.assertIsNotNone(beta["zones"][0]["point_mass_r_ex_au"])   # not silently dropped
        gamma = es.compose_exclusion_system([
            {"id": "A", "mass_solar": 1.0, "luminosity_lsun": 1.0, "sp_type": "G2V",
             "mass_loss_msun_yr": 2e-14, "pair": "AB", "sma_au": 20, "ecc": 0.3},
            {"id": "B", "mass_solar": 0.8, "luminosity_lsun": 0.4, "sp_type": "K2V",
             "mass_loss_msun_yr": 1e-14, "pair": "AB", "sma_au": 20, "ecc": 0.3}], gamma=0.5)
        self.assertIsNotNone(gamma["zones"][0]["point_mass_r_ex_au"])


# ── CR-13: --star live-resolution robustness (offline; the live cases are gated in
#    test_query_exclusion_system_live.py). These cover the pure decision helpers + the
#    _resolve_system_from_star integration with compute_simbad_lookup / binary_orbit / regions mocked.
_CR13_CAT = {"stars": [
    {"main_id": "* alf Cen A", "aliases": ["HD 128620", "GJ 559 A"], "mass_solar": 1.079, "citation": "t"},
    {"main_id": "* alf Cen B", "aliases": ["HD 128621", "GJ 559 B"], "mass_solar": 0.909, "citation": "t"},
    {"main_id": "* alf CMa A", "aliases": ["HD 48915", "HD 48915A"], "mass_solar": 2.063, "citation": "t"},
    {"main_id": "* alf CMa B", "aliases": ["HD 48915B", "GJ 244 B"], "mass_solar": 1.018, "citation": "Bond 2017"},
    {"main_id": "NAME Proxima Centauri", "aliases": ["* alf Cen C", "GJ 551"], "mass_solar": 0.1221,
     "citation": "Kervella 2017"},
]}


def _fake_simbad(mapping):
    return lambda name: mapping.get(name, {"error": f"No results for '{name}'"})


class Cr13SecondaryDetectorTest(unittest.TestCase):
    def test_is_secondary_component(self):
        self.assertTrue(es._is_secondary_component("* alf CMa B"))            # letter suffix
        self.assertTrue(es._is_secondary_component("* alf Cen C"))            # Proxima component id
        self.assertTrue(es._is_secondary_component("* alf CMa", otype="white dwarf"))  # off-MS otype
        self.assertTrue(es._is_secondary_component("WD 0642-166", sp_type="DA2"))      # off-MS sp_type
        self.assertFalse(es._is_secondary_component("* alf Cen A"))           # primary-named — NOT caught
        self.assertFalse(es._is_secondary_component("* alf Cen"))             # system head
        self.assertFalse(es._is_secondary_component("NAME Proxima Centauri"))
        self.assertFalse(es._is_secondary_component("Sol"))
        self.assertFalse(es._is_secondary_component(None))

    def test_classify_off_ms(self):
        self.assertEqual(es._classify_off_ms("white dwarf", None), "wd")
        self.assertEqual(es._classify_off_ms(None, "DA2"), "wd")
        self.assertEqual(es._classify_off_ms(None, "T6"), "brown-dwarf")
        self.assertEqual(es._classify_off_ms("brown dwarf", None), "brown-dwarf")
        self.assertIsNone(es._classify_off_ms(None, "G2V"))
        self.assertIsNone(es._classify_off_ms(None, None))


class Cr13CandidateIdsTest(unittest.TestCase):
    def test_component_candidate_ids_strips_trailing_letter(self):   # WB plan-review M4
        self.assertEqual(es._component_candidate_ids("* alf Cen", "A"), {"* alf Cen A"})
        self.assertEqual(es._component_candidate_ids("* alf Cen", "B"), {"* alf Cen B"})
        self.assertEqual(es._component_candidate_ids("* alf Cen A", "B"), {"* alf Cen B"})  # not "…A B"
        self.assertEqual(es._component_candidate_ids("* alf CMa", "B"), {"* alf CMa B"})
        self.assertEqual(es._component_candidate_ids("", "A"), set())
        self.assertEqual(es._component_candidate_ids(None, "A"), set())

    def test_augment_designations_injects_matchable_values(self):
        d = es._augment_designations({"HD": "HD 128620"}, {"* alf Cen A"})
        self.assertIn("* alf Cen A", d.values())
        self.assertIn("HD 128620", d.values())
        # match_mass sees the injected value → resolves the per-component row
        import core.stellar_mass_tables as smt
        row = smt.match_mass(_CR13_CAT, "* alf Cen", d)
        self.assertIsNotNone(row)
        self.assertEqual(row["mass_solar"], 1.079)


class Cr13SolutionSelectionTest(unittest.TestCase):
    def _sb2(self, q, p_d=29174.0, e=0.52):
        return {"companion": {"mass_ratio_q": q}, "period_d": p_d, "eccentricity": e,
                "source": "sb9", "grade": "a"}

    def _sb1(self, m1, m2, p_d=18300.0, e=0.59):
        return {"companion": {"m1_solar": m1, "m2_solar": m2, "method": "spec-min",
                              "caveat": "SB1 minimum mass (sin i = 1 lower bound); true M₂ ≥ this"},
                "period_d": p_d, "eccentricity": e, "source": "sb9", "grade": "a"}

    def test_degenerate_q_filtered_real_ratio_wins(self):
        sel, _ = es._select_orbit_masses([self._sb2(1.0), self._sb2(0.84)], "G2V")
        self.assertAlmostEqual(sel["m2_solar"] / sel["m1_solar"], 0.84, places=5)
        self.assertEqual(sel["mass_prov_a"], "binary_orbit_m1")
        self.assertEqual(sel["mass_prov_b"], "binary_orbit_m2")   # real ratio → clean

    def test_all_degenerate_q_flagged(self):
        sel, _ = es._select_orbit_masses([self._sb2(1.0)], "G2V")
        self.assertEqual(sel["mass_prov_b"], "binary_orbit_equal_split_unresolved")
        self.assertTrue(sel["notes"])

    def test_sb1_minimum_flagged(self):
        sel, _ = es._select_orbit_masses([self._sb1(2.06, 0.458)], "A1V")
        self.assertEqual(sel["mass_prov_b"], "binary_orbit_sb1_min")

    def test_competing_tier1_sb1_does_not_preempt_real_sb2(self):   # WB plan-review M2
        # An SB1 (tier-1: carries both masses) alongside a real-ratio SB2 (tier-2): the filter must
        # drop the tier-1 row so _extract lands on the real SB2, not the SB1 minimum.
        sel, _ = es._select_orbit_masses([self._sb1(1.0, 0.5), self._sb2(0.84)], "G2V")
        self.assertAlmostEqual(sel["m2_solar"] / sel["m1_solar"], 0.84, places=5)
        self.assertEqual(sel["mass_prov_b"], "binary_orbit_m2")

    def test_cr14_4_clean_astrometric_abs_kept_over_sb2(self):   # CR-14.4 (b) — exclusion delegate
        # A clean astrometric abs-mass row (method != "spec-min") alongside a real SB2: CR-14.4 keeps
        # the clean measurement (tier-1) over the SB2-ratio estimate. This pins the ONE exclusion-path
        # behavior change vs CR-13.3 OFFLINE (its live anchors don't carry this co-occurrence — the
        # "anchors unchanged" claim needs an offline guard; code-review finding 4).
        astrom = {"companion": {"m1_solar": 1.0, "m2_solar": 0.5, "method": "astrom"},
                  "period_d": 9000.0, "eccentricity": 0.1, "source": "gaia-nss", "grade": 50.0}
        sel, _ = es._select_orbit_masses([astrom, self._sb2(0.84)], "G2V")
        self.assertAlmostEqual(sel["m2_solar"] / sel["m1_solar"], 0.5, places=5)   # clean abs wins
        # And an α Cen-like set (degenerate q=1.0 + real SB2, NO clean abs) is UNCHANGED by (b):
        sel2, _ = es._select_orbit_masses([self._sb2(1.0), self._sb2(0.84)], "G2V")
        self.assertAlmostEqual(sel2["m2_solar"] / sel2["m1_solar"], 0.84, places=5)

    def test_no_usable_orbit_returns_none(self):
        sel, note = es._select_orbit_masses([], "G2V")
        self.assertIsNone(sel)
        self.assertTrue(note)

    def test_mass_flags_tier3_equal_mass(self):
        import core.binary as binary   # CR-14: _mass_flags hoisted to core.binary (single copy)
        prov_a, prov_b, notes = binary._mass_flags(
            {"mass_basis": "primary spectral type; equal-mass assumption (secondary mass unknown)",
             "m1_solar": 1.0, "m2_solar": 1.0})
        self.assertEqual(prov_b, "binary_orbit_equal_split_unresolved")
        self.assertTrue(any("equal-mass" in n for n in notes))


class Cr13ComposeToleranceTest(unittest.TestCase):
    """C1 → Option (A): a lone out-of-domain component with an unresolved mass is inert → r_ex null +
    unresolved_out_of_domain, NOT an error."""

    def test_lone_out_of_domain_unresolved_mass_ok(self):
        r = es.compose_exclusion_system([{"id": "Sirius B", "class": "wd"}], alpha=0.4)
        self.assertNotIn("error", r)
        c = r["zones"][0]["components"][0]
        self.assertIsNone(c["r_ex_au"])
        self.assertIsNone(c["mass_solar"])
        self.assertEqual(c["mass_provenance"], "unresolved_out_of_domain")
        self.assertEqual(c["class_note"], "white dwarf")

    def test_in_domain_unresolved_mass_still_errors(self):
        r = es.compose_exclusion_system([{"id": "x", "sp_type": "G2V"}], alpha=0.4)   # MS, no mass
        self.assertIn("error", r)

    def test_multi_component_unresolved_mass_still_errors(self):
        # the tolerance is for a LONE body only — a 2-body with an unresolved mass still errors
        r = es.compose_exclusion_system(
            [{"id": "A", "mass_solar": 1.0, "sp_type": "G2V", "pair": "AB", "sma_au": 20, "ecc": 0.3},
             {"id": "B", "class": "wd", "pair": "AB", "sma_au": 20, "ecc": 0.3}], alpha=0.4)
        self.assertIn("error", r)

    def test_component_path_lone_out_of_domain_reaches_tolerance(self):   # plan-review F2 (parity)
        r = es.compute_exclusion_system(component_specs=["id=B,class=wd"])   # no mass, lone WD
        self.assertNotIn("error", r)
        c = r["zones"][0]["components"][0]
        self.assertIsNone(c["r_ex_au"])
        self.assertEqual(c["mass_provenance"], "unresolved_out_of_domain")

    def test_component_path_multi_missing_mass_still_errors(self):        # F2 must not over-reach
        r = es.compute_exclusion_system(
            component_specs=["id=A,mass=1.0,type=G2V,pair=AB,sma=20,ecc=0.3",
                             "id=B,class=wd,pair=AB,sma=20,ecc=0.3"])   # B has no mass, but 2 bodies
        self.assertIn("error", r)


class Cr13ResolverTest(unittest.TestCase):
    """_resolve_system_from_star with the network mocked (SIMBAD / binary_orbit / regions)."""

    def _run(self, star, catalog, simbad_map, solutions=None, bclum=None, no_flame=False):
        patches = [mock.patch("core.databases.compute_simbad_lookup", _fake_simbad(simbad_map)),
                   mock.patch("core.binary.binary_orbit", lambda **k: {"solutions": solutions or []})]
        if no_flame:
            patches.append(mock.patch("core.binary.gaia_source_id_from_designations", lambda d: None))
        if bclum is not None:
            patches.append(mock.patch("core.regions.compute_star_system_regions_from_simbad",
                                      lambda sl: {"bcLuminosity": bclum}))
        for p in patches:
            p.start()
        try:
            return es._resolve_system_from_star(star, catalog)
        finally:
            for p in reversed(patches):
                p.stop()

    def test_sirius_b_secondary_single_wd_with_catalog(self):   # CR-13.1 crit-2(a), no "Sirius B B"
        m = {"Sirius B": {"main_id": "* alf CMa B", "sp_type": "DA2", "otype": "white dwarf",
                          "designations": {"HD": "HD 48915B"}}}
        comps, notes = self._run("Sirius B", _CR13_CAT, m)
        self.assertEqual(len(comps), 1)
        self.assertEqual(comps[0]["mass_solar"], 1.018)
        self.assertEqual(comps[0]["mass_provenance"], "catalog")
        r = es.compose_exclusion_system(comps, alpha=0.4)
        self.assertIsNone(r["zones"][0]["components"][0]["r_ex_au"])
        self.assertNotIn("* alf CMa B B", str(r["zones"][0]["members"]))
        self.assertNotIn("Sirius B B", str(r["zones"][0]["members"]))

    def test_sirius_b_secondary_bare_unresolved(self):          # CR-13.1 crit-2 bare (C1→A)
        m = {"Sirius B": {"main_id": "* alf CMa B", "sp_type": "DA2", "otype": "white dwarf",
                          "designations": {"HD": "HD 48915B"}}}
        comps, notes = self._run("Sirius B", None, m, no_flame=True)
        r = es.compose_exclusion_system(comps, alpha=0.4)
        c = r["zones"][0]["components"][0]
        self.assertIsNone(c["r_ex_au"])
        self.assertEqual(c["mass_provenance"], "unresolved_out_of_domain")

    def test_proxima_wide_member_single_body_catalog(self):     # CR-13.1/13.2 crit-1 with catalog
        m = {"Proxima Centauri": {"main_id": "NAME Proxima Centauri", "sp_type": "M5.5Ve",
                                  "otype": "high proper-motion Star", "designations": {"GJ": "GJ 551"}}}
        comps, notes = self._run("Proxima Centauri", _CR13_CAT, m, solutions=[])
        self.assertEqual(len(comps), 1)
        self.assertEqual(comps[0]["mass_solar"], 0.1221)
        self.assertEqual(comps[0]["mass_provenance"], "catalog")
        r = es.compose_exclusion_system(comps, alpha=0.4)
        self.assertAlmostEqual(r["zones"][0]["components"][0]["r_ex_au"], 20.4824, places=3)

    def test_proxima_bare_uses_bolometric_inversion(self):      # CR-13.2 / Q2 no-catalog
        m = {"Proxima Centauri": {"main_id": "NAME Proxima Centauri", "sp_type": "M5.5Ve",
                                  "otype": "star", "designations": {"GJ": "GJ 551"}}}
        bclum = 0.139 ** (1.0 / 0.2632)
        comps, notes = self._run("Proxima Centauri", None, m, solutions=[], bclum=bclum, no_flame=True)
        self.assertAlmostEqual(comps[0]["mass_solar"], 0.139, places=3)
        self.assertEqual(comps[0]["mass_provenance"], "ms_luminosity_inversion")
        r = es.compose_exclusion_system(comps, alpha=0.4)
        self.assertAlmostEqual(r["zones"][0]["components"][0]["r_ex_au"], 21.5725, places=3)

    def test_proxima_component_id_form_also_single_body(self):  # WB plan-review m7
        m = {"Proxima Centauri": {"main_id": "* alf Cen C", "sp_type": "M5.5Ve", "otype": "star",
                                  "designations": {"GJ": "GJ 551"}}}
        comps, notes = self._run("Proxima Centauri", _CR13_CAT, m, solutions=[])
        self.assertEqual(len(comps), 1)          # secondary-detector branch → still single body
        self.assertEqual(comps[0]["mass_solar"], 0.1221)

    def test_alpha_cen_binary_both_via_catalog(self):           # CR-13.2 crit-1
        sols = [{"companion": {"mass_ratio_q": 1.0}, "period_d": 29174.0, "eccentricity": 0.524,
                 "source": "sb9", "grade": "a"},
                {"companion": {"mass_ratio_q": 0.84}, "period_d": 29174.0, "eccentricity": 0.524,
                 "source": "sb9", "grade": "b"}]
        m = {"alpha Centauri": {"main_id": "* alf Cen", "sp_type": "G2V", "designations": {"HD": "HD 128620"}},
             "* alf Cen B": {"main_id": "* alf Cen B", "sp_type": "K1V", "otype": "star",
                             "designations": {"HD": "HD 128621"}}}
        comps, notes = self._run("alpha Centauri", _CR13_CAT, m, solutions=sols)
        by = {c["id"]: c for c in comps}
        self.assertEqual(by["* alf Cen"]["mass_solar"], 1.079)
        self.assertEqual(by["* alf Cen"]["mass_provenance"], "catalog")
        self.assertEqual(by["* alf Cen B"]["mass_solar"], 0.909)
        self.assertEqual(by["* alf Cen B"]["mass_provenance"], "catalog")
        r = es.compose_exclusion_system(comps, alpha=0.4)
        z = r["zones"][0]
        self.assertAlmostEqual(z["long_axis_au"]["periastron"], 54.0, delta=1.0)
        self.assertAlmostEqual(z["long_axis_au"]["apastron"], 65.0, delta=1.0)
        self.assertAlmostEqual(z["point_mass_r_ex_au"], 62.5, delta=1.0)

    def test_sirius_binary_no_catalog_flags_sb1_min(self):      # CR-13.3 crit-2
        sols = [{"companion": {"m1_solar": 2.06, "m2_solar": 0.458, "method": "spec-min",
                               "caveat": "SB1 minimum mass (sin i = 1 lower bound); true M₂ ≥ this"},
                 "period_d": 18300.0, "eccentricity": 0.59, "source": "sb9", "grade": "a"}]
        m = {"Sirius": {"main_id": "* alf CMa", "sp_type": "A0mA1Va", "designations": {"HD": "HD 48915"}},
             "* alf CMa B": {"main_id": "* alf CMa B", "sp_type": "DA2", "otype": "white dwarf",
                             "designations": {"HD": "HD 48915B"}}}
        comps, notes = self._run("Sirius", None, m, solutions=sols, no_flame=True)
        b = [c for c in comps if c["id"] == "* alf CMa B"][0]
        self.assertEqual(b["mass_provenance"], "binary_orbit_sb1_min")
        self.assertTrue(any("SB1 minimum" in n for n in notes))

    def test_primary_named_input_not_caught_as_secondary(self):  # WB MSG 126 regression watch
        sols = [{"companion": {"mass_ratio_q": 0.84}, "period_d": 29174.0, "eccentricity": 0.52,
                 "source": "sb9", "grade": "a"}]
        m = {"alpha Cen A": {"main_id": "* alf Cen A", "sp_type": "G2V", "designations": {"HD": "HD 128620"}},
             "* alf Cen B": {"main_id": "* alf Cen B", "sp_type": "K1V", "otype": "star",
                             "designations": {"HD": "HD 128621"}}}
        comps, notes = self._run("alpha Cen A", _CR13_CAT, m, solutions=sols)
        # primary-named → NOT single-body-secondary; composes the system, A resolves from catalog
        self.assertEqual(len(comps), 2)
        by = {c["id"]: c for c in comps}
        self.assertEqual(by["* alf Cen A"]["mass_solar"], 1.079)

    def test_lone_hot_subdwarf_not_given_fabricated_inversion_mass(self):   # plan-review F1
        # A parseable sdB (regions could invert it as a "B star"), but compose's guard flags it
        # out-of-domain — so the single-body path must NOT hand it an ms_luminosity_inversion mass.
        m = {"Feige X": {"main_id": "HD 900001", "sp_type": "sdB1", "otype": "hot subdwarf",
                         "designations": {"HD": "HD 900001"}}}
        bclum = 5.0   # a luminosity the OLD code would have inverted into a fabricated mass
        comps, notes = self._run("Feige X", None, m, solutions=[], bclum=bclum, no_flame=True)
        self.assertEqual(len(comps), 1)
        self.assertNotIn("mass_solar", comps[0])          # no fabricated mass
        r = es.compose_exclusion_system(comps, alpha=0.4)
        c = r["zones"][0]["components"][0]
        self.assertIsNone(c["r_ex_au"])
        self.assertEqual(c["mass_provenance"], "unresolved_out_of_domain")

    def test_unresolvable_ms_single_body_names_target_and_remedy(self):   # CR-13.1 crit-3
        m = {"Wolf 9999": {"main_id": "GJ 9999", "sp_type": "M4V", "otype": "star", "designations": {}}}
        out = self._run("Wolf 9999", None, m, solutions=[], no_flame=True)  # no catalog, regions absent
        self.assertIsInstance(out, dict)
        self.assertIn("error", out)
        self.assertIn("GJ 9999", out["error"])
        self.assertIn("--component", out["error"])


if __name__ == "__main__":
    unittest.main()
