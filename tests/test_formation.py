# tests/test_formation.py — Phase AJ (Group P) core calculators.
#
# Offline golden-pin tests for core.formation: the acceptance anchors from the request spec
# (formation-calculators-request.md) + the frozen follow-up rulings (formation-calculators-
# followup-1.md) + the self-validating error matrix. No network, no Qt, no DB, no numpy.
#
# AJ-1 (P1 disk-model, P2 isolation-mass) here; P3–P6 added in AJ-2.

import unittest

import core.formation as f


class DiskModelTest(unittest.TestCase):
    def test_mmsn_anchor_1au(self):
        d = f.compute_disk_model(r_au=1.0)
        self.assertAlmostEqual(d["sigma_gas_gcm2"], 1700.0, places=6)      # exact by construction
        self.assertAlmostEqual(d["temp_k"], 280.0, places=6)              # exact by construction
        self.assertAlmostEqual(d["aspect_ratio_hr"], 0.0334, delta=0.001)
        self.assertAlmostEqual(d["sigma_solid_gcm2"], 22.78, delta=0.05)  # Z_⊙·1700, interior
        self.assertTrue(d["interior_to_snowline"])
        self.assertIn("model_note", d)

    def test_anchor_5_2au(self):
        d = f.compute_disk_model(r_au=5.2)
        self.assertAlmostEqual(d["sigma_gas_gcm2"], 143.4, delta=0.5)
        self.assertAlmostEqual(d["temp_k"], 122.8, delta=0.5)
        self.assertFalse(d["interior_to_snowline"])

    def test_snowline_default_and_scaling(self):
        # Ruling 2 / Option A: own T-law, 170 K → 2.71 AU at L=1, ∝ L^(1/2)
        self.assertAlmostEqual(f.compute_disk_model(r_au=1.0)["snowline_au"], 2.713, delta=0.01)
        self.assertAlmostEqual(f.compute_disk_model(r_au=1.0, lstar_lsun=4.0)["snowline_au"], 5.43, delta=0.01)
        self.assertAlmostEqual(f.compute_disk_model(r_au=1.0, lstar_lsun=0.1)["snowline_au"], 0.858, delta=0.01)
        # f_ice steps exactly at the snow line
        self.assertTrue(f.compute_disk_model(r_au=2.5)["interior_to_snowline"])
        self.assertFalse(f.compute_disk_model(r_au=3.0)["interior_to_snowline"])

    def test_ice_factor_bumps_solid_density(self):
        inner = f.compute_disk_model(r_au=2.5)     # interior → f_ice = 1
        outer = f.compute_disk_model(r_au=3.0)     # exterior → f_ice = 2 (default)
        # Σ_solid = Z·f_ice·Σ_gas; at the step the factor-2 jump dominates the Σ_gas falloff
        self.assertAlmostEqual(outer["sigma_solid_gcm2"] / outer["sigma_gas_gcm2"],
                               2.0 * inner["sigma_solid_gcm2"] / inner["sigma_gas_gcm2"], places=9)

    def test_metallicity_and_snowline_overrides(self):
        # --feh scales Z by 10^[Fe/H]
        base = f.compute_disk_model(r_au=1.0)["sigma_solid_gcm2"]
        rich = f.compute_disk_model(r_au=1.0, feh=0.3)["sigma_solid_gcm2"]
        self.assertAlmostEqual(rich, base * 10.0 ** 0.3, delta=0.05)
        # explicit --z
        self.assertAlmostEqual(f.compute_disk_model(r_au=1.0, z=0.01)["sigma_solid_gcm2"],
                               0.01 * 1700.0, delta=0.01)
        # --snowline-au override moves the f_ice step
        d = f.compute_disk_model(r_au=1.5, snowline_au=1.0)
        self.assertFalse(d["interior_to_snowline"])
        self.assertAlmostEqual(d["snowline_au"], 1.0, places=6)
        # --snowline-temp-k 150 → canon's ~3.5 AU
        self.assertAlmostEqual(f.compute_disk_model(r_au=1.0, snowline_temp_k=150.0)["snowline_au"],
                               3.48, delta=0.02)

    def test_disk_mass_and_ms_luminosity(self):
        # disk-mass scaling is linear in Σ_gas
        self.assertAlmostEqual(f.compute_disk_model(r_au=1.0, disk_mass_mmsn=3.0)["sigma_gas_gcm2"],
                               3.0 * 1700.0, places=3)
        # --disk-mass-msun 0.02 = 2 MMSN
        self.assertAlmostEqual(f.compute_disk_model(r_au=1.0, disk_mass_msun=0.02)["sigma_gas_gcm2"],
                               2.0 * 1700.0, places=3)
        # --ms-luminosity: L = M^3.5 → snow line ∝ L^(1/2) = M^1.75
        d = f.compute_disk_model(r_au=1.0, mstar_msun=2.0, ms_luminosity=True)
        self.assertAlmostEqual(d["snowline_au"], 2.713 * (2.0 ** 3.5) ** 0.5, delta=0.05)

    def test_grid_mode(self):
        g = f.compute_disk_model(r_grid=(1.0, 30.0, 5))
        self.assertEqual(len(g["radii"]), 5)
        self.assertAlmostEqual(g["radii"][0]["r_au"], 1.0, places=6)
        self.assertAlmostEqual(g["radii"][-1]["r_au"], 30.0, places=6)
        # log-spaced: monotonically increasing radii
        rs = [row["r_au"] for row in g["radii"]]
        self.assertEqual(rs, sorted(rs))
        self.assertIn("snowline_au", g)

    def test_errors(self):
        self.assertIn("error", f.compute_disk_model())                               # no radius
        self.assertIn("error", f.compute_disk_model(r_au=1.0, r_grid=(1, 2, 3)))      # both radius modes
        self.assertIn("error", f.compute_disk_model(r_au=-1.0))                       # negative radius
        self.assertIn("error", f.compute_disk_model(r_au=1.0, mstar_msun=0))          # non-positive M★
        self.assertIn("error", f.compute_disk_model(r_au=1.0, mu=0))                  # non-positive μ
        self.assertIn("error", f.compute_disk_model(r_au=1.0, feh=0.1, z=0.02))       # both metallicity
        self.assertIn("error", f.compute_disk_model(r_au=1.0, disk_mass_mmsn=1, disk_mass_msun=0.01))  # both disk mass
        self.assertIn("error", f.compute_disk_model(r_au=1.0, lstar_lsun=1, ms_luminosity=True))  # both L modes
        self.assertIn("error", f.compute_disk_model(r_au=1.0, snowline_au=-1))        # negative snow line
        self.assertIn("error", f.compute_disk_model(r_grid=(30, 1, 5)))               # HI < LO
        self.assertIn("error", f.compute_disk_model(r_grid=(1, 30, 1)))               # N < 2


class IsolationMassTest(unittest.TestCase):
    def test_anchors(self):
        # F2 pinned quotes: terrestrial 0.07 M⊕, Jupiter-core 9 M⊕ (Σ_p=10, C=2√3, M⊙)
        self.assertAlmostEqual(f.compute_isolation_mass(sigma_p_gcm2=10.0, a_au=1.0)["isolation_mass_mearth"],
                               0.0659, delta=0.001)
        self.assertAlmostEqual(f.compute_isolation_mass(sigma_p_gcm2=10.0, a_au=5.2)["isolation_mass_mearth"],
                               9.27, delta=0.05)

    def test_default_convention_and_units(self):
        import math
        d = f.compute_isolation_mass(sigma_p_gcm2=10.0, a_au=1.0)
        self.assertEqual(d["convention"], "half-width-C")
        self.assertAlmostEqual(d["feeding_zone_width_hill"], 2.0 * math.sqrt(3.0), places=6)
        # M_earth and M_jup describe the same mass
        self.assertAlmostEqual(d["isolation_mass_mearth"] * 5.972e24 / 1.898e27,
                               d["isolation_mass_mjup"], places=9)

    def test_scaling_laws(self):
        # M_iso ∝ Σ_p^(3/2) · a^3 · M★^(−1/2)
        base = f.compute_isolation_mass(sigma_p_gcm2=10.0, a_au=1.0)["isolation_mass_mearth"]
        self.assertAlmostEqual(f.compute_isolation_mass(sigma_p_gcm2=40.0, a_au=1.0)["isolation_mass_mearth"],
                               base * 8.0, delta=base * 0.01)     # 4^1.5 = 8
        self.assertAlmostEqual(f.compute_isolation_mass(sigma_p_gcm2=10.0, a_au=2.0)["isolation_mass_mearth"],
                               base * 8.0, delta=base * 0.01)     # 2^3 = 8
        self.assertAlmostEqual(f.compute_isolation_mass(sigma_p_gcm2=10.0, a_au=1.0, mstar_msun=4.0)["isolation_mass_mearth"],
                               base * 0.5, delta=base * 0.01)     # 4^(−0.5) = 0.5

    def test_feeding_zone_b_convention(self):
        d = f.compute_isolation_mass(sigma_p_gcm2=10.0, a_au=1.0, feeding_zone_b=10.0)
        self.assertEqual(d["convention"], "full-width-b")
        self.assertEqual(d["feeding_zone_width_hill"], 10.0)
        self.assertGreater(d["isolation_mass_mearth"], 0)

    def test_errors(self):
        self.assertIn("error", f.compute_isolation_mass(a_au=1.0))                        # no sigma
        self.assertIn("error", f.compute_isolation_mass(sigma_p_gcm2=10.0))               # no a
        self.assertIn("error", f.compute_isolation_mass(sigma_p_gcm2=-1.0, a_au=1.0))     # neg sigma
        self.assertIn("error", f.compute_isolation_mass(sigma_p_gcm2=10.0, a_au=0))       # non-pos a
        self.assertIn("error", f.compute_isolation_mass(sigma_p_gcm2=10.0, a_au=1.0, mstar_msun=0))
        self.assertIn("error", f.compute_isolation_mass(sigma_p_gcm2=10.0, a_au=1.0,
                                                        feeding_zone_c=3, feeding_zone_b=10))  # both conventions


class PebbleIsolationMassTest(unittest.TestCase):
    def test_anchors(self):
        self.assertAlmostEqual(f.compute_pebble_isolation_mass(hr=0.05)["pebble_isolation_mass_mearth"],
                               25.0, delta=0.1)
        self.assertAlmostEqual(f.compute_pebble_isolation_mass(hr=0.05, simple=True)["pebble_isolation_mass_mearth"],
                               20.0, delta=0.1)
        self.assertAlmostEqual(f.compute_pebble_isolation_mass(hr=0.03)["pebble_isolation_mass_mearth"],
                               5.4, delta=0.05)     # 25·0.6³

    def test_f_fit_and_modes(self):
        d = f.compute_pebble_isolation_mass(hr=0.05, alpha=1e-3)
        self.assertAlmostEqual(d["f_fit"], 1.0, places=6)     # α = α₃ = 0.001 → f_fit = 1
        self.assertEqual(d["mode"], "bitsch2018")
        self.assertEqual(f.compute_pebble_isolation_mass(hr=0.05, simple=True)["mode"], "lambrechts2014")
        # higher α → f_fit > 1 (more mass); lower α → f_fit < 1 (Bitsch 2018: ×2–3 low→high α)
        self.assertLess(f.compute_pebble_isolation_mass(hr=0.05, alpha=1e-4)["f_fit"], 1.0)
        self.assertGreater(f.compute_pebble_isolation_mass(hr=0.05, alpha=1e-2)["f_fit"], 1.0)

    def test_hr_derivation(self):
        # H/r derived from (T, M★, a) should match a direct --hr run at the same H/r
        direct = f.compute_pebble_isolation_mass(hr=0.0334)["pebble_isolation_mass_mearth"]
        derived = f.compute_pebble_isolation_mass(temp_k=280.0, mstar_msun=1.0, a_au=1.0)
        self.assertAlmostEqual(derived["hr"], 0.0334, delta=0.001)
        self.assertAlmostEqual(derived["pebble_isolation_mass_mearth"], direct, delta=0.5)

    def test_errors(self):
        self.assertIn("error", f.compute_pebble_isolation_mass())                                   # no H/r input
        self.assertIn("error", f.compute_pebble_isolation_mass(hr=0.05, temp_k=280))                # both hr modes
        self.assertIn("error", f.compute_pebble_isolation_mass(temp_k=280, mstar_msun=1))           # incomplete derive
        self.assertIn("error", f.compute_pebble_isolation_mass(hr=-0.05))                           # negative hr
        self.assertIn("error", f.compute_pebble_isolation_mass(hr=0.05, alpha=0))                   # non-pos α


class GapOpeningMassTest(unittest.TestCase):
    def test_crida_case1_threshold(self):
        # Frozen ruling: --hr 0.05 --nu-code 3.162e-6 → q≈4.98e-4, ≈0.52 M_Jup at M⊙, P=1.000
        d = f.compute_gap_opening_mass(hr=0.05, nu_code=3.162e-6, mstar_msun=1.0, a_au=5.2)
        self.assertAlmostEqual(d["threshold_q"], 4.978e-4, delta=3e-6)
        self.assertAlmostEqual(d["gap_opening_mass_mjup"], 0.52, delta=0.01)
        self.assertAlmostEqual(d["p_value_at_threshold"], 1.000, delta=1e-3)

    def test_criterion_unit_check(self):
        # Case-1 clear-gap cross-check: P(q=1e-3) = 0.699 (< 1 → a clear gap opens)
        self.assertAlmostEqual(f._crida_p(1e-3, 0.05, 1.0 / 3.162e-6), 0.699, delta=1e-3)

    def test_p_target_and_reynolds_equivalence(self):
        # --reynolds R = 1/nu_code reproduces the --nu-code run
        by_nu = f.compute_gap_opening_mass(hr=0.05, nu_code=3.162e-6, mstar_msun=1.0, a_au=5.2)
        by_re = f.compute_gap_opening_mass(hr=0.05, reynolds=1.0 / 3.162e-6, mstar_msun=1.0, a_au=5.2)
        self.assertAlmostEqual(by_nu["threshold_q"], by_re["threshold_q"], places=9)
        # a higher p_target (looser criterion) admits a larger threshold mass
        loose = f.compute_gap_opening_mass(hr=0.05, nu_code=3.162e-6, mstar_msun=1.0, a_au=5.2, p_target=1.2)
        self.assertLess(loose["threshold_q"], by_nu["threshold_q"])  # P higher → smaller q

    def test_errors(self):
        base = dict(mstar_msun=1.0, a_au=5.2)
        self.assertIn("error", f.compute_gap_opening_mass(nu_code=3.162e-6, **base))                # no H/r
        self.assertIn("error", f.compute_gap_opening_mass(hr=0.05, **base))                         # no viscosity
        self.assertIn("error", f.compute_gap_opening_mass(hr=0.05, nu_code=1e-6, alpha=1e-3, **base))  # two viscosity
        self.assertIn("error", f.compute_gap_opening_mass(hr=0.05, nu_code=3.162e-6, a_au=5.2))     # no M★
        self.assertIn("error", f.compute_gap_opening_mass(hr=0.05, nu_code=3.162e-6, mstar_msun=1)) # no a
        self.assertIn("error", f.compute_gap_opening_mass(hr=0.05, temp_k=280, nu_code=1e-6, **base))  # both hr modes


class ToomreQTest(unittest.TestCase):
    def test_mmsn_stable_anchor(self):
        # MMSN at 30 AU (Σ≈10.35 g/cm², T≈51.1 K) → Q ≈ 23.7, stable
        d = f.compute_toomre_q(sigma_gcm2=1700 * 30 ** -1.5, temp_k=280 * 30 ** -0.5,
                               mstar_msun=1.0, a_au=30.0)
        self.assertAlmostEqual(d["toomre_q"], 23.7, delta=0.5)
        self.assertFalse(d["unstable"])
        self.assertGreater(d["lambda_crit_au"], 0)
        self.assertGreater(d["fragment_mass_mjup"], 0)

    def test_instability_flag_and_cs_modes(self):
        # a ~2-orders-more-massive disk goes unstable
        d = f.compute_toomre_q(sigma_gcm2=1000.0, temp_k=51.0, mstar_msun=1.0, a_au=30.0)
        self.assertTrue(d["unstable"])
        # --cs-ms matches a --temp-k run at the same c_s
        ref = f.compute_toomre_q(sigma_gcm2=10.0, temp_k=51.1, mstar_msun=1.0, a_au=30.0)
        by_cs = f.compute_toomre_q(sigma_gcm2=10.0, cs_ms=ref["sound_speed_ms"], mstar_msun=1.0, a_au=30.0)
        self.assertAlmostEqual(by_cs["toomre_q"], ref["toomre_q"], places=6)

    def test_errors(self):
        self.assertIn("error", f.compute_toomre_q(mstar_msun=1, a_au=30, temp_k=51))         # no sigma
        self.assertIn("error", f.compute_toomre_q(sigma_gcm2=10, mstar_msun=1, a_au=30))     # no c_s mode
        self.assertIn("error", f.compute_toomre_q(sigma_gcm2=10, temp_k=51, cs_ms=200,
                                                  mstar_msun=1, a_au=30))                     # two c_s modes
        self.assertIn("error", f.compute_toomre_q(sigma_gcm2=10, temp_k=51, a_au=30))        # no M★
        self.assertIn("error", f.compute_toomre_q(sigma_gcm2=10, temp_k=51, mstar_msun=1))   # no a


class CriticalCoreMassTest(unittest.TestCase):
    def test_anchors(self):
        self.assertAlmostEqual(f.compute_critical_core_mass()["critical_core_mass_mearth"], 12.0, places=6)
        self.assertAlmostEqual(f.compute_critical_core_mass(mdot_core=1e-7)["critical_core_mass_mearth"],
                               6.75, delta=0.05)
        self.assertAlmostEqual(f.compute_critical_core_mass(opacity=0.1)["critical_core_mass_mearth"],
                               6.75, delta=0.05)

    def test_index_and_norm_overrides(self):
        # index sensitivity (±0.05): a bigger index steepens the Ṁ dependence
        hi = f.compute_critical_core_mass(mdot_core=1e-7, index=0.30)["critical_core_mass_mearth"]
        lo = f.compute_critical_core_mass(mdot_core=1e-7, index=0.20)["critical_core_mass_mearth"]
        self.assertLess(hi, lo)   # (0.1)^0.30 < (0.1)^0.20
        self.assertAlmostEqual(f.compute_critical_core_mass(crit_norm=10.0)["critical_core_mass_mearth"],
                               10.0, places=6)

    def test_errors(self):
        self.assertIn("error", f.compute_critical_core_mass(mdot_core=0))
        self.assertIn("error", f.compute_critical_core_mass(opacity=-1))
        self.assertIn("error", f.compute_critical_core_mass(crit_norm=0))


if __name__ == "__main__":
    unittest.main()
