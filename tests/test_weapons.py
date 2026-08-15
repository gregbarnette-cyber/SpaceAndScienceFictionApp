# tests/test_weapons.py — Phase AT (Packet 38.1) W2/W3/W4 weapon-physics core acceptance.
#
# W2 beam-weapon-engagement, W3 kinetic-kill, W4 warhead-effects-at-standoff. Hand-derived
# identities + cross-tool anchors (θ vs angular-resolution; (γ−1)mc² vs relativistic-energy-momentum)
# + the validation matrix. Each calculator carries ≥1 anchor independent of its own computation.

import math
import unittest

from core.weapons import (compute_beam_weapon_engagement as BW,
                          compute_kinetic_kill as KK,
                          compute_warhead_effects as WH)
from core.sensing import compute_angular_resolution as AR
from core.relativity import compute_relativistic_energy_momentum as REM

_C = 299_792_458.0


class BeamWeaponTest(unittest.TestCase):
    def test_theta_matches_angular_resolution(self):
        bw = BW(aperture_m=10, wavelength_m=1e-6, power_w=1e9, target_size_m=1, range_m=1e9,
                kill_fluence_jm2=1e7)
        ar = AR(aperture_m=10, wavelength_m=1e-6)
        self.assertAlmostEqual(bw["diffraction_half_angle_rad"], ar["angular_resolution_rad"], places=15)

    def test_spot_intensity_dwell_identities(self):
        bw = BW(aperture_m=10, wavelength_m=1e-6, power_w=1e9, target_size_m=1, range_m=1e9,
                kill_fluence_jm2=1e7)
        self.assertAlmostEqual(bw["spot_diameter_m"], 2 * 1.22e-7 * 1e9, places=6)
        # I = f_on·P/A_target and t_kill = Φ/I are exact identities.
        a_t = math.pi * 0.25
        self.assertAlmostEqual(bw["intensity_on_target_wm2"],
                               bw["frac_power_on_target_tophat"] * 1e9 / a_t, places=6)
        self.assertAlmostEqual(bw["dwell_to_kill_s"], 1e7 / bw["intensity_on_target_wm2"], places=9)

    def test_effective_range_spot(self):
        bw = BW(aperture_m=10, wavelength_m=1e-6, power_w=1e9, target_size_m=1, range_m=1e9,
                kill_fluence_jm2=1e7)
        theta = bw["diffraction_half_angle_rad"]
        self.assertAlmostEqual(bw["effective_range_spot_m"], 1.0 / (2 * theta), places=3)

    def test_material_kill_fluence(self):
        # Φ_kill = enthalpy × areal density.
        bw = BW(aperture_m=10, wavelength_m=1e-6, power_w=1e9, target_size_m=1, range_m=1e6,
                target_material_enthalpy_jkg=1e7, target_areal_density_kgm2=10)
        self.assertAlmostEqual(bw["kill_fluence_jm2"], 1e8)

    def test_encircled_and_beam_quality(self):
        bw = BW(aperture_m=10, wavelength_m=1e-6, power_w=1e9, target_size_m=1, range_m=1e9,
                kill_fluence_jm2=1e7, beam_quality_m2=2.0)
        # M²=2 doubles the half-angle → doubles the spot.
        self.assertAlmostEqual(bw["spot_diameter_m"], 2 * 2 * 1.22e-7 * 1e9, places=6)
        self.assertTrue(0.0 < bw["frac_power_on_target_encircled"] <= 1.0)

    def test_peak_spot_intensity_close_range(self):
        # Close range: spot (~0.024 m) far smaller than the 1 m target → peak ≫ target-averaged I.
        bw = BW(aperture_m=10, wavelength_m=1e-6, power_w=1e9, target_size_m=1, range_m=1e5,
                kill_fluence_jm2=1e7)
        self.assertTrue(bw["spot_smaller_than_target"])
        self.assertGreater(bw["peak_spot_intensity_wm2"], bw["intensity_on_target_wm2"])
        # In the spill regime they coincide.
        far = BW(aperture_m=10, wavelength_m=1e-6, power_w=1e9, target_size_m=1, range_m=1e9,
                 kill_fluence_jm2=1e7)
        self.assertFalse(far["spot_smaller_than_target"])
        self.assertAlmostEqual(far["peak_spot_intensity_wm2"], far["intensity_on_target_wm2"], places=3)

    def test_validation(self):
        for kw in (
            dict(aperture_m=0, wavelength_m=1e-6, power_w=1e9, target_size_m=1, range_m=1e9, kill_fluence_jm2=1),
            dict(aperture_m=10, power_w=1e9, target_size_m=1, range_m=1e9, kill_fluence_jm2=1),   # no λ/f
            dict(aperture_m=10, wavelength_m=1e-6, frequency_hz=3e14, power_w=1e9, target_size_m=1,
                 range_m=1e9, kill_fluence_jm2=1),                                                # both λ and f
            dict(aperture_m=10, wavelength_m=1e-6, power_w=1e9, target_size_m=1, range_m=1e9),    # no Φ_kill
            dict(aperture_m=10, wavelength_m=1e-6, power_w=1e9, target_size_m=1, range_m=1e9,
                 kill_fluence_jm2=1, target_material_enthalpy_jkg=1e7, target_areal_density_kgm2=10),  # both
        ):
            self.assertIn("error", BW(**kw), kw)


class KineticKillTest(unittest.TestCase):
    def test_classical_ke_tnt(self):
        r = KK(mass_kg=1, velocity_kms=100, target_density_kgm3=7800)
        self.assertAlmostEqual(r["ke_classical_j"], 5e9)
        self.assertAlmostEqual(r["tnt_equiv_t"], 5e9 / 4.184e9, places=6)
        self.assertEqual(r["regime"], "classical")
        self.assertAlmostEqual(r["specific_energy_jkg"], 5e9)

    def test_relativistic_matches_rem(self):
        r = KK(mass_kg=0.001, beta=0.5, target_density_kgm3=7800)
        rem = REM(mass_kg=0.001, velocity_c=0.5)
        self.assertAlmostEqual(r["ke_relativistic_j"], rem["kinetic_energy_j"], places=3)
        self.assertAlmostEqual(r["momentum_kgms"], rem["momentum_kgms"], places=3)
        self.assertEqual(r["regime"], "relativistic")
        self.assertEqual(r["ke_j"], r["ke_relativistic_j"])

    def test_hydrodynamic_penetration(self):
        # P = L·√(ρ_i/ρ_t); tungsten rod (19000) into steel (7800). 10 km/s > 5 km/s sound speed.
        r = KK(length_m=1.0, diameter_m=0.05, density_kgm3=19000, velocity_kms=10,
               target_density_kgm3=7800, target_sound_speed_ms=5000)
        self.assertAlmostEqual(r["penetration_depth_m"], 1.0 * math.sqrt(19000 / 7800), places=6)
        self.assertIsNotNone(r["crater_penetration_m"])
        self.assertEqual(r["penetration_regime"], "hydrodynamic")

    def test_crater_out_of_domain_strength_regime(self):
        # v below the target sound speed → strength-dominated → crater form withheld with a reason.
        r = KK(length_m=1.0, diameter_m=0.05, density_kgm3=19000, velocity_kms=3,
               target_density_kgm3=7800, target_sound_speed_ms=5000)
        self.assertEqual(r["penetration_regime"], "strength-dominated")
        self.assertIsNone(r["crater_penetration_m"])
        self.assertIn("out of domain", r["crater_reason"])
        self.assertIsNotNone(r["penetration_depth_m"])       # long-rod headline still reported

    def test_mass_only_no_penetration(self):
        r = KK(mass_kg=1, velocity_kms=100, target_density_kgm3=7800)
        self.assertIsNone(r["penetration_depth_m"])
        self.assertIn("rod length", r["penetration_reason"])

    def test_monolithic_perforates(self):
        r = KK(length_m=1.0, diameter_m=0.05, density_kgm3=19000, velocity_kms=10,
               target_density_kgm3=7800, target_type="monolithic", armor_thickness_m=0.5)
        self.assertTrue(r["perforates"])          # ~1.56 m > 0.5 m
        r2 = KK(length_m=1.0, diameter_m=0.05, density_kgm3=19000, velocity_kms=10,
                target_density_kgm3=7800, target_type="monolithic", armor_thickness_m=5.0)
        self.assertFalse(r2["perforates"])

    def test_whipple_shatter_and_wall(self):
        r = KK(mass_kg=0.01, velocity_kms=5, target_density_kgm3=7800, target_type="whipple",
               bumper_areal_density_kgm2=0.5, standoff_m=0.1, rearwall_areal_density_kgm2=1.0)
        self.assertTrue(r["whipple"]["impactor_shattered"])      # 5 > 3 km/s
        self.assertFalse(r["whipple"]["impactor_vaporized"])     # 5 < 7 km/s
        self.assertIn(r["whipple"]["rearwall_defeated"], (True, False))
        # Below shatter threshold → intact impactor defeats the wall.
        r2 = KK(mass_kg=0.01, velocity_kms=2, target_density_kgm3=7800, target_type="whipple",
                bumper_areal_density_kgm2=0.5, standoff_m=0.1, rearwall_areal_density_kgm2=1e9)
        self.assertFalse(r2["whipple"]["impactor_shattered"])
        self.assertTrue(r2["whipple"]["rearwall_defeated"])

    def test_validation(self):
        for kw in (
            dict(velocity_kms=100, target_density_kgm3=7800),                                   # no impactor
            dict(mass_kg=1, length_m=1, velocity_kms=100, target_density_kgm3=7800),            # both anchors
            dict(mass_kg=1, target_density_kgm3=7800),                                          # no velocity
            dict(mass_kg=1, velocity_kms=100, beta=0.1, target_density_kgm3=7800),              # both velocities
            dict(mass_kg=1, velocity_kms=100),                                                  # no target density
            dict(mass_kg=1, velocity_kms=100, target_density_kgm3=7800, target_type="whipple"), # whipple missing
        ):
            self.assertIn("error", KK(**kw), kw)


class WarheadEffectsTest(unittest.TestCase):
    def test_fluence_and_kill_radius(self):
        r = WH(yield_kt=1, warhead_type="fission", standoff_m=1000, threshold_xray_jm2=1e6)
        y = 4.184e12
        self.assertAlmostEqual(r["channels"]["xray"]["fluence_jm2"],
                               0.75 * y / (4 * math.pi * 1e6), places=3)
        self.assertAlmostEqual(r["channels"]["xray"]["kill_radius_m"],
                               math.sqrt(0.75 * y / (4 * math.pi * 1e6)), places=6)
        self.assertEqual(r["binding_channel"], "xray")

    def test_killed_at_range(self):
        # Inside the x-ray kill radius (~500 m) → killed; far outside → not.
        near = WH(yield_kt=1, warhead_type="fission", standoff_m=100, threshold_xray_jm2=1e6)
        far = WH(yield_kt=1, warhead_type="fission", standoff_m=10000, threshold_xray_jm2=1e6)
        self.assertTrue(near["killed_at_range"])
        self.assertFalse(far["killed_at_range"])

    def test_partition_override_and_source(self):
        r = WH(yield_j=1e12, warhead_type="fusion", f_xray=0.9, f_neutron=0.0, f_debris=0.1,
               f_gamma=0.0, standoff_m=1000)
        self.assertEqual(r["channels"]["xray"]["fraction_source"], "override")
        self.assertAlmostEqual(r["partition_fractions"]["xray"], 0.9)

    def test_antimatter_escaping_fraction(self):
        r = WH(yield_j=1e12, warhead_type="antimatter", standoff_m=1000)
        self.assertGreater(r["escaping_fraction"], 0.0)          # ~0.2 escapes as neutrinos
        self.assertIn("gamma", r["channels"])
        self.assertNotIn("xray", r["channels"])                  # fraction 0 → channel omitted

    def test_zero_fraction_channel_threshold_not_silently_dropped(self):
        # antimatter has f_xray=0; a supplied x-ray threshold must surface as an inactive channel.
        r = WH(yield_j=1e12, warhead_type="antimatter", standoff_m=1000, threshold_xray_jm2=1e6)
        self.assertIn("xray", r["channels"])
        self.assertIsNotNone(r["channels"]["xray"]["note"])
        self.assertFalse(r["channels"]["xray"]["killed_at_range"])
        self.assertAlmostEqual(r["channels"]["xray"]["fluence_jm2"], 0.0)

    def test_yield_kt_conversion(self):
        r = WH(yield_kt=1, standoff_m=1000)
        self.assertAlmostEqual(r["yield_j"], 4.184e12)

    def test_validation(self):
        for kw in (
            dict(warhead_type="fusion", standoff_m=1000),                          # no yield
            dict(yield_j=1e12, yield_kt=1, standoff_m=1000),                        # both yields
            dict(yield_j=1e12, warhead_type="nuke", standoff_m=1000),              # bad type
            dict(yield_j=1e12, standoff_m=0),                                       # bad standoff
            dict(yield_j=1e12, standoff_m=1000, f_xray=0.9, f_debris=0.9),          # sum > 1
        ):
            self.assertIn("error", WH(**kw), kw)


if __name__ == "__main__":
    unittest.main()
