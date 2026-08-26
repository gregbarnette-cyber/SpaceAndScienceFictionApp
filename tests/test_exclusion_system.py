# tests/test_exclusion_system.py — CR-11.3 binary/multi-star exclusion-boundary composition.
#
# Offline, in-process (the --component deterministic core). Covers the Sirius (WD-guard, merged) and
# α Cen (AB-merged + Proxima-separate) hand-card anchors, the domain guard, merge-grouping, the
# prolate envelope, the in-domain-only point-mass, the degenerate single-star reproduction of
# exclusion-boundary, and validation. The live --star path is gated in test_query_exclusion_system_live.py.

import unittest

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


if __name__ == "__main__":
    unittest.main()
