# tests/test_nuclear.py — CR-4 nuclear-fuel & radiogenic inventory (core, offline).
#
# Pins the shared Interface-A solar anchor (present U-235/U-238 ≈ 0.00725), the corrected
# radiogenic BSE anchor (~5e-12 W/kg), and the monotonicity + honest-empty criteria.

import unittest

import core.nuclear as nuclear
import core.nuclear_tables as nt


def _solar():
    return nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=4.567, eu_h=0.0)


class FissileAnchorTest(unittest.TestCase):
    def test_solar_u235_u238_anchor(self):
        f = _solar()["fissile"]
        # The shared Interface-A validation: production(1.35) → formation-epoch → decay → 0.00725.
        self.assertAlmostEqual(f["U235_U238_ratio"], 0.00725, delta=1e-4)

    def test_solar_isotopic_and_actinide_fractions(self):
        f = _solar()["fissile"]
        self.assertAlmostEqual(f["U235_frac"] + f["U238_frac"], 1.0, places=9)
        self.assertAlmostEqual(f["U235_frac"], 0.0072, delta=5e-4)
        self.assertAlmostEqual(f["Th232_frac"], 0.80, delta=0.02)   # Th/U(number) ≈ 4

    def test_younger_star_higher_u235_u238(self):
        young = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=1.0, eu_h=0.0)
        self.assertGreater(young["fissile"]["U235_U238_ratio"], _solar()["fissile"]["U235_U238_ratio"])

    def test_r_process_poor_lower_absolute_same_ratio(self):
        poor = nuclear.compute_nuclear_inventory(fe_h=-0.5, age_gyr=4.567, eu_h=-1.0)
        self.assertLess(poor["fissile"]["u_over_h"], _solar()["fissile"]["u_over_h"])
        # The isotopic ratio is Eu-independent (a ratio) → unchanged by r-process poverty.
        self.assertAlmostEqual(poor["fissile"]["U235_U238_ratio"],
                               _solar()["fissile"]["U235_U238_ratio"], delta=1e-4)

    def test_no_tracer_is_note_not_null(self):
        f = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=4.567)["fissile"]
        self.assertIsNone(f["U235_frac"])
        self.assertIn("note", f)

    def test_eu_fe_equivalent_to_eu_h(self):
        # [Eu/Fe]=−0.5 at [Fe/H]=−0.5 → [Eu/H]=−1.0.
        a = nuclear.compute_nuclear_inventory(fe_h=-0.5, age_gyr=4.567, eu_fe=-0.5)
        b = nuclear.compute_nuclear_inventory(fe_h=-0.5, age_gyr=4.567, eu_h=-1.0)
        self.assertAlmostEqual(a["fissile"]["u_over_h"], b["fissile"]["u_over_h"], places=18)


class RadiogenicTest(unittest.TestCase):
    def test_solar_bse_anchor_order(self):
        q = _solar()["radiogenic_heat_W_per_kg"]
        self.assertTrue(3e-12 < q < 8e-12, f"radiogenic {q} outside 3–8e-12 W/kg BSE band")
        self.assertAlmostEqual(q, 5.03e-12, delta=0.3e-12)

    def test_younger_body_hotter(self):
        young = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=1.0, eu_h=0.0)
        self.assertGreater(young["radiogenic_heat_W_per_kg"], _solar()["radiogenic_heat_W_per_kg"])

    def test_metal_rich_hotter(self):
        rich = nuclear.compute_nuclear_inventory(fe_h=0.3, age_gyr=4.567, eu_h=0.0)
        self.assertGreater(rich["radiogenic_heat_W_per_kg"], _solar()["radiogenic_heat_W_per_kg"])


class FusionTest(unittest.TestCase):
    def test_d_h_astrated_below_primordial(self):
        f = _solar()["fusion"]
        self.assertLess(f["D_over_H"], 2.53e-5)          # astrated below BBN primordial
        self.assertGreater(f["D_over_H"], 1.0e-5)

    def test_d_h_higher_at_lower_metallicity(self):
        poor = nuclear.compute_nuclear_inventory(fe_h=-1.0, age_gyr=4.567, eu_h=-1.0)
        self.assertGreater(poor["fusion"]["D_over_H"], _solar()["fusion"]["D_over_H"])


class ProvenanceAndValidationTest(unittest.TestCase):
    def test_domain_ok_true_solar_false_out_of_range(self):
        self.assertTrue(_solar()["provenance"]["domain_ok"])
        old = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=15.0, eu_h=0.0)
        self.assertFalse(old["provenance"]["domain_ok"])
        self.assertIsNotNone(old["provenance"]["domain_note"])

    def test_provenance_carries_gce_version(self):
        prov = _solar()["provenance"]
        self.assertIn("gce_model_version", prov)
        self.assertEqual(prov["gce_model_version"], "3c-v1.0.0-2026-08-15")   # 3c FINAL swapped in


class Gce3cFinalTest(unittest.TestCase):
    """The 3c FINAL age-dependent uniform-production survival integral (coordination MSG 042)."""

    def test_gce_factor_matches_3c_derived_table(self):
        # g_i(age) reproduces the delivered fissile-fraction-gce-model.json derived_table_validation.
        # The line-28 formula is authoritative; the table is rounded (its steep old-age end, e.g.
        # age-10 U235 0.5118, is ~0.2% off the exact integral) — cross-check to 0.2%, not bit-exact.
        for age, gu235, gu238, gth in [
                (4.567, 0.1452, 0.6105, 0.8458), (0.5, 0.0918, 0.4782, 0.7708),
                (8.0, 0.2770, 0.7687, 0.9172), (10.0, 0.5118, 0.8885, 0.9626)]:
            self.assertAlmostEqual(nt.gce_enrichment_factor("U235", age), gu235, delta=2e-3)
            self.assertAlmostEqual(nt.gce_enrichment_factor("U238", age), gu238, delta=2e-3)
            self.assertAlmostEqual(nt.gce_enrichment_factor("Th232", age), gth, delta=2e-3)

    def test_halo_floor_above_d_eff(self):
        # age ≥ D_eff (11.55) → fresh-production floor g_i = 1.
        for iso in ("U235", "U238", "Th232"):
            self.assertEqual(nt.gce_enrichment_factor(iso, 12.0), 1.0)

    def test_dv2_actinide_boost_voids_domain(self):
        # [Eu/Fe] ≳ +0.7 (r-II star) → domain_ok False, reason names Eu/Fe.
        d = nuclear.compute_nuclear_inventory(fe_h=-1.0, age_gyr=5.0, eu_fe=1.0)
        self.assertFalse(d["provenance"]["domain_ok"])
        self.assertIn("Eu/Fe", d["provenance"]["domain_note"])

    def test_domain_bands_flag_regimes(self):
        young = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=3.0, eu_h=0.0)
        self.assertTrue(any("young band" in b for b in young["provenance"]["bands"]))
        old = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=10.0, eu_h=0.0)
        self.assertTrue(any("ISM-mixing" in b for b in old["provenance"]["bands"]))
        self.assertTrue(any("joint" in b for b in old["provenance"]["bands"]))

    def test_bad_inputs_error(self):
        self.assertIn("error", nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=-1.0))
        self.assertIn("error", nuclear.compute_nuclear_inventory(fe_h=None, age_gyr=4.567))
        self.assertIn("error", nuclear.compute_nuclear_inventory(
            fe_h=0.0, age_gyr=4.567, eu_h=0.0, eu_fe=0.0))
        self.assertIn("error", nuclear.compute_nuclear_inventory(
            fe_h=0.0, age_gyr=4.567, population="disk"))


if __name__ == "__main__":
    unittest.main()
