# tests/test_relativity.py — Phase AF (Group L) core calculators.
#
# Offline golden-pin tests for core.relativity: the corrected acceptance anchors + the
# self-validating error matrix. No network, no Qt, no DB.

import math
import unittest

import core.relativity as r


class TimeDilationTest(unittest.TestCase):
    def test_special_anchors(self):
        self.assertAlmostEqual(r.compute_time_dilation(velocity_c=0.866)["gamma"], 2.000, delta=0.001)
        self.assertAlmostEqual(r.compute_time_dilation(velocity_c=0.99)["gamma"], 7.089, delta=0.001)

    def test_time_solve(self):
        d = r.compute_time_dilation(velocity_c=0.866, proper_time=1.0)
        self.assertAlmostEqual(d["coordinate_time"], 2.000, delta=0.001)
        d2 = r.compute_time_dilation(velocity_c=0.866, coordinate_time=2.0)
        self.assertAlmostEqual(d2["proper_time"], 1.0, delta=0.001)

    def test_gravitational_anchor(self):
        d = r.compute_time_dilation(body="earth")
        self.assertAlmostEqual(1.0 - d["gravitational_factor"], 6.95e-10, delta=1e-11)
        self.assertEqual(d["gamma"], 1.0)

    def test_combined(self):
        d = r.compute_time_dilation(velocity_c=0.5, body="earth", combined=True)
        self.assertIsNotNone(d["combined_factor"])
        self.assertAlmostEqual(d["combined_factor"], d["gamma"] / d["gravitational_factor"], places=12)

    def test_errors(self):
        self.assertIn("error", r.compute_time_dilation())                                  # nothing
        self.assertIn("error", r.compute_time_dilation(velocity_c=1.0))                     # β≥1
        self.assertIn("error", r.compute_time_dilation(velocity_c=0.5, combined=True))      # combined w/o grav
        self.assertIn("error", r.compute_time_dilation(velocity_c=0.5, proper_time=1, coordinate_time=1))
        self.assertIn("error", r.compute_time_dilation(velocity_c=0.5, velocity_kms=1))     # 2 velocity units


class LengthContractionTest(unittest.TestCase):
    def test_anchor(self):
        d = r.compute_length_contraction(velocity_c=0.866, proper_length=1.0)
        self.assertAlmostEqual(d["contracted_length"], 0.5, delta=0.001)
        self.assertAlmostEqual(d["contraction_factor"], 1.0 / d["gamma"], places=12)

    def test_inverse_solve(self):
        d = r.compute_length_contraction(velocity_c=0.866, contracted_length=0.5)
        self.assertAlmostEqual(d["proper_length"], 1.0, delta=0.001)

    def test_errors(self):
        self.assertIn("error", r.compute_length_contraction())                             # no velocity
        self.assertIn("error", r.compute_length_contraction(velocity_c=0.5, proper_length=-1))


class VelocityAdditionTest(unittest.TestCase):
    def test_anchors(self):
        self.assertAlmostEqual(r.compute_velocity_addition(0.75, 0.75)["combined_velocity_c"], 0.96, delta=1e-9)
        self.assertAlmostEqual(r.compute_velocity_addition(1.0, 0.5)["combined_velocity_c"], 1.0, delta=1e-12)

    def test_luminal_gamma_null(self):
        self.assertIsNone(r.compute_velocity_addition(1.0, 0.5)["gamma_combined"])

    def test_perpendicular_sublight(self):
        d = r.compute_velocity_addition(0.9, 0.9, perpendicular=True)
        self.assertLess(d["combined_velocity_c"], 1.0)

    def test_errors(self):
        self.assertIn("error", r.compute_velocity_addition(None, 0.5))
        self.assertIn("error", r.compute_velocity_addition(1.5, 0.5))


class DopplerTest(unittest.TestCase):
    def test_anchors(self):
        self.assertAlmostEqual(r.compute_relativistic_doppler(velocity_c=0.6, approach=True)["doppler_factor"], 2.0, delta=1e-9)
        self.assertAlmostEqual(r.compute_relativistic_doppler(velocity_c=0.6, approach=True)["redshift_z"], -0.5, delta=1e-9)
        self.assertAlmostEqual(r.compute_relativistic_doppler(velocity_c=0.6, angle_deg=90)["doppler_factor"], 0.8, delta=1e-9)
        self.assertAlmostEqual(r.compute_relativistic_doppler(velocity_c=0.6, recede=True)["doppler_factor"], 0.5, delta=1e-9)

    def test_wavelength_frequency(self):
        d = r.compute_relativistic_doppler(velocity_c=0.6, approach=True, rest_wavelength_nm=500.0)
        self.assertAlmostEqual(d["observed_wavelength_nm"], 250.0, delta=1e-6)
        d2 = r.compute_relativistic_doppler(velocity_c=0.6, approach=True, rest_frequency_hz=1e9)
        self.assertAlmostEqual(d2["observed_frequency_hz"], 2e9, delta=1e3)

    def test_errors(self):
        self.assertIn("error", r.compute_relativistic_doppler(velocity_c=0.6))                    # no direction
        self.assertIn("error", r.compute_relativistic_doppler(velocity_c=0.6, approach=True, recede=True))
        self.assertIn("error", r.compute_relativistic_doppler(velocity_c=0.6, approach=True,
                                                              rest_wavelength_nm=1, rest_frequency_hz=1))


class RapidityTest(unittest.TestCase):
    def test_anchors(self):
        self.assertAlmostEqual(r.compute_rapidity(velocity_c=0.6)["rapidity"], 0.6931, delta=1e-4)
        d = r.compute_rapidity(add=[0.6, 0.6, 0.6])
        self.assertAlmostEqual(d["rapidity"], 2.0794, delta=1e-4)
        self.assertAlmostEqual(d["composed_velocity_c"], 0.9695, delta=1e-3)

    def test_rapidity_input(self):
        d = r.compute_rapidity(rapidity=0.6931471805599453)
        self.assertAlmostEqual(d["velocity_c"], 0.6, delta=1e-6)

    def test_errors(self):
        self.assertIn("error", r.compute_rapidity())                                       # nothing
        self.assertIn("error", r.compute_rapidity(velocity_c=0.6, rapidity=0.7))           # two sources
        self.assertIn("error", r.compute_rapidity(add=[0.6, 1.0]))                         # β≥1 in list


class EnergyMomentumTest(unittest.TestCase):
    def test_anchor(self):
        d = r.compute_relativistic_energy_momentum(mass_mev=938.272, velocity_c=0.99)
        self.assertAlmostEqual(d["gamma"], 7.089, delta=0.001)
        # KE ≈ 5.72 GeV
        self.assertAlmostEqual(d["kinetic_energy_j"], 5.72e9 * 1.602176634e-19, delta=2e-11)

    def test_state_equivalence(self):
        # gamma from velocity vs from KE should agree
        a = r.compute_relativistic_energy_momentum(mass_kg=1.6726e-27, velocity_c=0.99)
        b = r.compute_relativistic_energy_momentum(mass_kg=1.6726e-27, kinetic_energy_j=a["kinetic_energy_j"])
        self.assertAlmostEqual(a["velocity_c"], b["velocity_c"], places=9)
        c = r.compute_relativistic_energy_momentum(mass_kg=1.6726e-27, momentum=a["momentum_kgms"])
        self.assertAlmostEqual(a["gamma"], c["gamma"], places=9)

    def test_errors(self):
        self.assertIn("error", r.compute_relativistic_energy_momentum(velocity_c=0.5))            # no mass
        self.assertIn("error", r.compute_relativistic_energy_momentum(mass_kg=1, mass_mev=1, velocity_c=0.5))
        self.assertIn("error", r.compute_relativistic_energy_momentum(mass_kg=1))                 # no state
        self.assertIn("error", r.compute_relativistic_energy_momentum(mass_kg=1, gamma=0.5))      # γ<1


class LorentzTransformTest(unittest.TestCase):
    def test_anchor(self):
        d = r.compute_lorentz_transform(velocity_c=0.6, t_yr=0.0, x_ly=1.0)
        self.assertAlmostEqual(d["t_prime"], -0.75, delta=1e-9)
        self.assertAlmostEqual(d["x_prime"], 1.25, delta=1e-9)

    def test_inverse_roundtrip(self):
        fwd = r.compute_lorentz_transform(velocity_c=0.6, t_yr=1.0, x_ly=2.0)
        back = r.compute_lorentz_transform(velocity_c=0.6, t_yr=fwd["t_prime"], x_ly=fwd["x_prime"],
                                           inverse=True)
        self.assertAlmostEqual(back["t_prime"], 1.0, delta=1e-9)
        self.assertAlmostEqual(back["x_prime"], 2.0, delta=1e-9)

    def test_simultaneity(self):
        d = r.compute_lorentz_transform(velocity_c=0.6, t_yr=0.0, x_ly=0.0, event2_t=0.0, event2_x=1.0)
        # Δt' = -γβΔx = -1.25*0.6*1 = -0.75
        self.assertAlmostEqual(d["simultaneity_offset"], -0.75, delta=1e-9)

    def test_errors(self):
        self.assertIn("error", r.compute_lorentz_transform(velocity_c=1.0, t_yr=0, x_ly=1))       # β≥1
        self.assertIn("error", r.compute_lorentz_transform(velocity_c=0.6, t_yr=0))               # missing x
        self.assertIn("error", r.compute_lorentz_transform(velocity_c=0.6, t=0, x=1, t_yr=0, x_ly=1))  # mixed units
        self.assertIn("error", r.compute_lorentz_transform(velocity_c=0.6, t_yr=0, x_ly=1, event2_t=0))  # partial event2


class CausalityCheckTest(unittest.TestCase):
    def test_anchors(self):
        a = r.compute_causality_check(signal_speed_c=2.0, frame_velocity_c=0.6)
        self.assertTrue(a["loop_possible"])
        self.assertAlmostEqual(a["condition_value"], 1.2, delta=1e-9)
        self.assertAlmostEqual(a["critical_frame_velocity_c"], 0.5, delta=1e-9)
        self.assertFalse(r.compute_causality_check(signal_speed_c=2.0, frame_velocity_c=0.4)["loop_possible"])
        self.assertTrue(r.compute_causality_check(instant=True, frame_velocity_c=0.01)["loop_possible"])

    def test_instant_and_preferred(self):
        i = r.compute_causality_check(instant=True, frame_velocity_c=0.01)
        self.assertIsNone(i["condition_value"])
        self.assertEqual(i["critical_frame_velocity_c"], 0.0)
        p = r.compute_causality_check(signal_speed_c=2.0, frame_velocity_c=0.6, preferred_frame=True)
        self.assertTrue(p["preferred_frame_safe"])

    def test_no_loop_at_zero_frame(self):
        self.assertFalse(r.compute_causality_check(instant=True, frame_velocity_c=0.0)["loop_possible"])

    def test_errors(self):
        self.assertIn("error", r.compute_causality_check(frame_velocity_c=0.5))                   # no signal mode
        self.assertIn("error", r.compute_causality_check(signal_speed_c=2, instant=True, frame_velocity_c=0.5))
        self.assertIn("error", r.compute_causality_check(signal_speed_c=2))                       # no frame vel
        self.assertIn("error", r.compute_causality_check(signal_speed_c=2, frame_velocity_c=1.0)) # β≥1
        self.assertIn("error", r.compute_causality_check(signal_speed_c=-1, frame_velocity_c=0.5))


if __name__ == "__main__":
    unittest.main()
