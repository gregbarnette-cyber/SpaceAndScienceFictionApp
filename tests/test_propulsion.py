# tests/test_propulsion.py — Phase Y STL mission energetics core (in-process).
#
# Covers core/propulsion.py (compute_rocket_equation, compute_beam_sail) against the
# combined request's Group-G acceptance anchors, all two-of-three anchor solves, the
# legs multiplier, the fuel presets + table integrity, and the self-validating ({"error"})
# matrix. No network/DB/RNG/Qt.

import math
import unittest

import core.propulsion as propulsion
from core import propulsion_tables
from core.equations import _C_MS, _STANDARD_GRAVITY

R = propulsion.compute_rocket_equation
B = propulsion.compute_beam_sail
_C_KMS = _C_MS / 1000.0


class RocketAcceptanceTest(unittest.TestCase):
    def test_classical_anchor(self):
        d = R(delta_v_kms=30, exhaust_velocity_kms=30)
        self.assertAlmostEqual(d["mass_ratio"], math.e, places=4)          # ≈ 2.718
        self.assertAlmostEqual(d["propellant_fraction"], 1 - 1 / math.e, places=4)  # ≈ 0.632
        self.assertFalse(d["relativistic"])
        self.assertIsNone(d["beta"])

    def test_relativistic_flyby_and_rendezvous(self):
        d = R(beta=0.1, exhaust_velocity_kms=0.1 * _C_KMS)
        self.assertAlmostEqual(d["mass_ratio"], 2.727, places=2)
        self.assertTrue(d["relativistic"])
        self.assertAlmostEqual(d["beta"], 0.1, places=6)
        # rendezvous squares the single-burn MR
        d2 = R(beta=0.1, exhaust_velocity_kms=0.1 * _C_KMS, legs="rendezvous")
        self.assertAlmostEqual(d2["mass_ratio"], d["mass_ratio"] ** 2, places=4)
        self.assertAlmostEqual(d2["mass_ratio"], 7.44, places=1)

    def test_fusion_marginal_generation_ship(self):
        # β 0.1, fusion-dt (v_e≈0.03c) → MR≈28 flyby, ~800 rendezvous
        d = R(beta=0.1, fuel="fusion-dt")
        self.assertAlmostEqual(d["mass_ratio"], 28.35, delta=0.3)
        d2 = R(beta=0.1, fuel="fusion-dt", legs="rendezvous")
        self.assertAlmostEqual(d2["mass_ratio"], d["mass_ratio"] ** 2, places=2)
        self.assertAlmostEqual(d2["mass_ratio"], 803.5, delta=10)

    def test_photon_rocket(self):
        # β 0.1, v_e=c → MR = √((1+β)/(1−β)) ≈ 1.105
        d = R(beta=0.1, exhaust_velocity_kms=_C_KMS)
        self.assertAlmostEqual(d["mass_ratio"], math.sqrt(1.1 / 0.9), places=5)
        self.assertAlmostEqual(d["mass_ratio"], 1.1055, places=3)

    def test_round_trip_is_fourth_power(self):
        base = R(delta_v_kms=30, exhaust_velocity_kms=30)["mass_ratio_single_burn"]
        d = R(delta_v_kms=30, exhaust_velocity_kms=30, legs="round-trip")
        self.assertAlmostEqual(d["mass_ratio"], base ** 4, places=4)


class RocketSolveFormsTest(unittest.TestCase):
    def test_solve_exhaust_from_velocity_and_mass_ratio(self):
        d = R(delta_v_kms=30, mass_ratio=math.e)
        self.assertAlmostEqual(d["exhaust_velocity_kms"], 30, places=4)

    def test_solve_velocity_from_exhaust_and_mass_ratio(self):
        d = R(exhaust_velocity_kms=30, mass_ratio=math.e)
        self.assertAlmostEqual(d["delta_v_kms"], 30, places=4)

    def test_solve_exhaust_relativistic(self):
        d = R(beta=0.1, mass_ratio=28.35)
        self.assertAlmostEqual(d["exhaust_velocity_kms"], 0.03 * _C_KMS, delta=0.02 * 0.03 * _C_KMS)
        self.assertTrue(d["relativistic"])

    def test_solve_velocity_relativistic_flag(self):
        # exhaust + mass_ratio, no velocity: --relativistic emits β (else classical Δv only)
        classical = R(exhaust_velocity_kms=0.1 * _C_KMS, mass_ratio=2.727)
        self.assertIsNone(classical["beta"])
        rel = R(exhaust_velocity_kms=0.1 * _C_KMS, mass_ratio=2.727, relativistic=True)
        self.assertAlmostEqual(rel["beta"], 0.1, places=2)

    def test_isp_anchor(self):
        # v_e = Isp·g₀; 30 km/s ↔ Isp = 30000/9.80665 ≈ 3058.85 s
        isp = 30_000.0 / _STANDARD_GRAVITY
        d = R(delta_v_kms=30, isp_s=isp)
        self.assertAlmostEqual(d["mass_ratio"], math.e, places=3)
        self.assertAlmostEqual(d["isp_s"], isp, places=2)

    def test_payload_mass_budget(self):
        d = R(delta_v_kms=30, exhaust_velocity_kms=30, payload_mass_t=100)
        self.assertAlmostEqual(d["wet_mass_t"], 100 * math.e, places=2)
        self.assertAlmostEqual(d["propellant_mass_t"], 100 * (math.e - 1), places=2)


class RocketValidationTest(unittest.TestCase):
    def _err(self, **kw):
        d = R(**kw)
        self.assertIn("error", d, kw)
        return d

    def test_matrix(self):
        self._err(delta_v_kms=30)                                   # one anchor
        self._err(delta_v_kms=30, beta=0.1, exhaust_velocity_kms=30)  # too many groups / both velocity
        self._err(exhaust_velocity_kms=30, isp_s=3000, mass_ratio=2)  # two exhaust forms
        self._err(beta=1.0, exhaust_velocity_kms=30)                 # β not sublight
        self._err(beta=-0.1, exhaust_velocity_kms=30)               # β negative
        self._err(delta_v_kms=-5, exhaust_velocity_kms=30)          # non-positive Δv
        self._err(delta_v_kms=30, exhaust_velocity_kms=-1)          # non-positive v_e
        self._err(delta_v_kms=30, mass_ratio=0.5)                   # MR < 1
        self._err(delta_v_kms=30, mass_ratio=1.0)                   # MR = 1
        self._err(delta_v_kms=30, fuel="unobtanium")               # unknown fuel
        self._err(delta_v_kms=30, exhaust_velocity_kms=30, legs="orbit")  # bad legs
        self._err(delta_v_kms=30, relativistic=True, exhaust_velocity_kms=30)  # rel + Δv
        self._err(delta_v_kms=30, exhaust_velocity_kms=30, structure_fraction=1.0)  # sf out of range
        self._err(delta_v_kms=30, exhaust_velocity_kms=30, payload_mass_t=0)  # non-positive payload

    def test_determinism(self):
        a = R(beta=0.1, fuel="fusion-dt", legs="rendezvous")
        b = R(beta=0.1, fuel="fusion-dt", legs="rendezvous")
        self.assertEqual(a, b)


class BeamSailTest(unittest.TestCase):
    def test_thrust_anchor(self):
        # 100 GW, reflective (R=1) → F = 2P/c ≈ 666.7 N
        d = B(beam_power_w=100e9, reflectivity=1.0, sail_mass_kg=1000, payload_mass_kg=0)
        self.assertAlmostEqual(d["thrust_n"], 2 * 100e9 / _C_MS, places=3)
        self.assertAlmostEqual(d["thrust_n"], 666.67, delta=1.0)
        self.assertAlmostEqual(d["acceleration_ms2"], d["thrust_n"] / 1000, places=6)

    def test_absorptive_limit(self):
        d = B(beam_power_w=100e9, reflectivity=0.0, sail_mass_kg=1000)
        self.assertAlmostEqual(d["thrust_n"], 100e9 / _C_MS, places=3)  # P/c

    def test_areal_mass_and_final_velocity(self):
        d = B(beam_power_w=100e9, sail_area_m2=1e6, areal_mass_gm2=1.0,
              payload_mass_kg=100, accel_time_days=10)
        self.assertAlmostEqual(d["sail_mass_kg"], 1000.0, places=6)  # 1 g/m² × 1e6 m²
        # v = a·t, positive; β = v/c
        self.assertGreater(d["final_velocity_kms"], 0)
        self.assertAlmostEqual(d["beta"], d["final_velocity_kms"] * 1000 / _C_MS, places=9)

    def test_accel_distance_energy(self):
        d = B(beam_power_w=1e12, sail_mass_kg=100, accel_distance_au=1.0)
        self.assertGreater(d["final_velocity_kms"], 0)
        self.assertGreater(d["beam_energy_j"], 0)

    def test_beam_range_note(self):
        d = B(beam_power_w=1e12, sail_area_m2=1e6, areal_mass_gm2=1.0,
              wavelength_nm=1000, transmit_aperture_m=1000)
        self.assertIn("Diffraction", d["beam_range_note"])

    def _err(self, **kw):
        self.assertIn("error", B(**kw), kw)

    def test_validation_matrix(self):
        self._err(beam_power_w=0, sail_mass_kg=10)                  # non-positive power
        self._err(beam_power_w=1e9, reflectivity=1.5, sail_mass_kg=10)  # reflectivity > 1
        self._err(beam_power_w=1e9)                                 # no mass source
        self._err(beam_power_w=1e9, areal_mass_gm2=1.0)             # areal mass without area
        self._err(beam_power_w=1e9, sail_mass_kg=10, payload_mass_kg=-1)  # negative payload
        self._err(beam_power_w=1e9, sail_mass_kg=10, accel_distance_au=1, accel_time_days=1)  # both accel
        self._err(beam_power_w=1e9, sail_mass_kg=10, wavelength_nm=1000)  # aperture missing
        self._err(beam_power_w=1e9, sail_mass_kg=10, sail_area_m2=-5)     # bad area


class TableIntegrityTest(unittest.TestCase):
    def test_fuel_presets_golden(self):
        # Drift guard on the bundled ideal exhaust velocities (like Phase V's NIST pin).
        f = propulsion_tables._FUELS
        self.assertEqual(set(f), {"chemical", "fission-thermal", "fusion-dt",
                                  "fusion-catalyzed", "antimatter"})
        self.assertAlmostEqual(f["chemical"]["v_e_kms"], 4.4, places=6)
        self.assertAlmostEqual(f["fission-thermal"]["v_e_kms"], 9.0, places=6)
        self.assertAlmostEqual(f["fusion-dt"]["v_e_kms"], 0.03 * _C_KMS, places=3)
        self.assertAlmostEqual(f["fusion-catalyzed"]["v_e_kms"], 0.10 * _C_KMS, places=3)
        self.assertAlmostEqual(f["antimatter"]["v_e_kms"], 0.30 * _C_KMS, places=3)
        for v in f.values():
            self.assertIn("note", v)


# ── C2 (Phase AD) — pellet-stream drive ───────────────────────────────────────

P = propulsion.compute_pellet_stream


class PelletStreamTest(unittest.TestCase):
    def test_drive_anchor(self):
        # v_s 30000 km/s, ṁ 1 kg/s, β 0.05 (v ≈ 14989.6 km/s), reflect (g=2):
        # u ≈ 15010 km/s → F = 2·1·u ≈ 3.0×10⁷ N; verdict drive.
        d = P(stream_velocity_kms=30000, mass_flow_rate_kgs=1, beta=0.05)
        self.assertAlmostEqual(d["relative_velocity_kms"], 30000 - 0.05 * _C_KMS, places=3)
        self.assertAlmostEqual(d["relative_velocity_kms"], 15010.4, delta=0.5)
        self.assertAlmostEqual(d["thrust_n"], 3.0e7, delta=5e4)
        self.assertEqual(d["verdict"], "drive")
        self.assertEqual(d["coupling"], "reflect")
        self.assertEqual(d["crossover_velocity_kms"], 30000)
        # power ½·ṁ·u² self-consistent
        u_ms = d["relative_velocity_kms"] * 1000.0
        self.assertAlmostEqual(d["delivered_power_w"], 0.5 * 1 * u_ms ** 2, places=0)
        # thrust core-parity: F = g·ṁ·u
        self.assertAlmostEqual(d["thrust_n"], 2 * 1 * u_ms, places=3)

    def test_no_thrust_at_crossover(self):
        # v = v_s → u = 0 → no push (clean-negative, not an error)
        d = P(stream_velocity_kms=30000, mass_flow_rate_kgs=1, velocity_kms=30000)
        self.assertEqual(d["verdict"], "no-thrust")
        self.assertEqual(d["thrust_n"], 0.0)
        self.assertEqual(d["delivered_power_w"], 0.0)
        self.assertNotIn("error", d)
        # v > v_s also no-thrust
        d2 = P(stream_velocity_kms=30000, mass_flow_rate_kgs=1, velocity_kms=40000)
        self.assertEqual(d2["verdict"], "no-thrust")
        self.assertEqual(d2["thrust_n"], 0.0)

    def test_absorb_is_half_reflect(self):
        kw = dict(stream_velocity_kms=30000, mass_flow_rate_kgs=1, beta=0.05)
        refl = P(coupling="reflect", **kw)
        absb = P(coupling="absorb", **kw)
        self.assertAlmostEqual(absb["thrust_n"], refl["thrust_n"] / 2.0, places=6)
        self.assertEqual(absb["coupling"], "absorb")

    def test_pellet_mass_rate_matches_mass_flow(self):
        # ṁ = pellet_mass · rate; the two mass-flow anchors agree
        a = P(stream_velocity_kms=30000, mass_flow_rate_kgs=2.0, beta=0.05)
        b = P(stream_velocity_kms=30000, pellet_mass_kg=0.5, pellet_rate_hz=4.0, beta=0.05)
        self.assertAlmostEqual(a["mass_flow_rate_kgs"], b["mass_flow_rate_kgs"], places=9)
        self.assertAlmostEqual(a["thrust_n"], b["thrust_n"], places=3)

    def test_acceleration_optional(self):
        base = dict(stream_velocity_kms=30000, mass_flow_rate_kgs=1, beta=0.05)
        self.assertIsNone(P(**base)["acceleration_ms2"])
        d = P(vehicle_mass_t=1000, **base)
        self.assertAlmostEqual(d["acceleration_ms2"], d["thrust_n"] / (1000 * 1000.0), places=9)

    def test_vehicle_at_rest_allowed(self):
        d = P(stream_velocity_kms=30000, mass_flow_rate_kgs=1, velocity_kms=0)
        self.assertEqual(d["verdict"], "drive")
        self.assertAlmostEqual(d["relative_velocity_kms"], 30000, places=6)

    def _err(self, **kw):
        self.assertIn("error", P(**kw), kw)

    def test_validation_matrix(self):
        self._err(stream_velocity_kms=0, mass_flow_rate_kgs=1, beta=0.05)          # v_s ≤ 0
        self._err(stream_velocity_kms=30000, beta=0.05)                            # no mass anchor
        self._err(stream_velocity_kms=30000, pellet_mass_kg=1, beta=0.05)          # partial pellet
        self._err(stream_velocity_kms=30000, mass_flow_rate_kgs=1,
                  pellet_rate_hz=2, beta=0.05)                                     # two mass anchors
        self._err(stream_velocity_kms=30000, mass_flow_rate_kgs=1)                 # no velocity anchor
        self._err(stream_velocity_kms=30000, mass_flow_rate_kgs=1, beta=1.0)       # β ∉ (0,1)
        self._err(stream_velocity_kms=30000, mass_flow_rate_kgs=1,
                  beta=0.05, vehicle_mass_t=0)                                     # mass ≤ 0
        self._err(stream_velocity_kms=30000, mass_flow_rate_kgs=1,
                  beta=0.05, coupling="bogus")                                     # bad coupling

    def test_determinism(self):
        kw = dict(stream_velocity_kms=30000, pellet_mass_kg=0.5, pellet_rate_hz=4,
                  beta=0.05, vehicle_mass_t=1000, coupling="absorb")
        self.assertEqual(P(**kw), P(**kw))


if __name__ == "__main__":
    unittest.main()
