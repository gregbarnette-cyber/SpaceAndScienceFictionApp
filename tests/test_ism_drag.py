# tests/test_ism_drag.py — Phase AC ISM-drag / magnetic-sail core (Group K).
#
# In-process tests: the K1/K2 acceptance anchors, the moment/coil/scoop equivalences,
# the crossover, the full self-validating matrix, near-field warning, bundled-table golden
# pins, and determinism. Pure math — offline, no DB/network/RNG. Mirrors test_propulsion.py.

import math
import unittest

import core.ism_drag as ism
import core.ism_drag_tables as t
from core.equations import _C_MS, _MU_0, _AMU_KG

_C_KMS = _C_MS / 1000.0


class MagsailAnchorTest(unittest.TestCase):
    # request K1 headline anchor: n0.1 / m1.0 / β0.1 / m_dip = I·π·R² (I=1e5,R=1e5).
    # A1: the far-field headline (R_mp ≈ 100 km) now belongs to the MOMENT-ONLY anchor
    # (no coil geometry → far-field dipole); the coil-pair anchor uses the exact loop field.
    _M_DIP = 1e5 * math.pi * (1e5) ** 2

    def _moment(self, **kw):
        base = dict(ism_density_cm3=0.1, ion_mass_amu=1.0, beta=0.1, magnetic_moment_am2=self._M_DIP)
        base.update(kw)
        return ism.compute_magsail(**base)

    def _coil(self, **kw):
        base = dict(ism_density_cm3=0.1, ion_mass_amu=1.0, beta=0.1,
                    coil_radius_m=1e5, coil_current_a=1e5)
        base.update(kw)
        return ism.compute_magsail(**base)

    def test_standoff_drag_deceleration_anchor(self):
        # Moment-only anchor = the far-field headline, byte-identical to Phase AC.
        d = self._moment(vehicle_mass_t=1000)
        self.assertNotIn("error", d)
        self.assertAlmostEqual(d["magnetopause_radius_km"], 100.0, delta=5.0)   # ~100 km
        self.assertTrue(1e3 <= d["drag_force_n"] <= 1e4)                        # ~1–10 kN
        self.assertAlmostEqual(d["deceleration_ms2"], 2.4e-3, delta=5e-4)       # ~10⁻³ for 10³ t
        self.assertAlmostEqual(d["effective_area_km2"], math.pi * d["magnetopause_radius_km"] ** 2,
                               places=3)
        self.assertIn("v^4/3", d["drag_scaling_note"])
        # moment-only → far-field cross-check equals the reported R_mp, no coil geometry
        self.assertAlmostEqual(d["magnetopause_radius_farfield_km"], d["magnetopause_radius_km"],
                               places=9)
        self.assertIsNone(d["coil_radius_m"])
        self.assertIsNone(d["near_field_warning"])

    def test_drag_scales_v_4_3(self):
        # far-field scaling holds on the moment-only anchor
        fast = self._moment()
        slow = self._moment(beta=0.05)
        self.assertAlmostEqual(fast["drag_force_n"] / slow["drag_force_n"],
                               2 ** (4.0 / 3.0), places=3)   # halving β → 2^(4/3) ≈ 2.52×

    def test_standoff_radius_scales_v_neg_1_3(self):
        fast = self._moment()
        slow = self._moment(beta=0.05)
        self.assertAlmostEqual(slow["magnetopause_radius_km"] / fast["magnetopause_radius_km"],
                               2 ** (1.0 / 3.0), places=3)   # R_mp ∝ v^(−1/3)

    def test_moment_only_is_farfield_dipole(self):
        d = self._moment()
        rho = 0.1 * 1e6 * 1.0 * _AMU_KG
        v = 0.1 * _C_MS
        r_mp = (_MU_0 * self._M_DIP ** 2 / (8 * math.pi ** 2 * 1.0 * rho * v ** 2)) ** (1.0 / 6.0)
        self.assertAlmostEqual(d["magnetopause_radius_km"], r_mp / 1000.0, places=6)

    # ── A1 — exact on-axis loop field on the coil-pair anchor ──
    def test_coil_exact_nearfield(self):
        # With R_coil=1e5, I=1e5 the standoff sits INSIDE the coil (exact ≈ 13 km ≪ far-field 100 km).
        c = self._coil()
        self.assertAlmostEqual(c["magnetopause_radius_km"], 13.12, delta=0.2)     # exact near-field
        self.assertAlmostEqual(c["magnetopause_radius_farfield_km"], 100.86, delta=0.5)
        # far-field cross-check of the coil == the moment-only R_mp (same m_dip)
        self.assertAlmostEqual(c["magnetopause_radius_farfield_km"],
                               self._moment()["magnetopause_radius_km"], places=6)
        # a note is present but it is informational, not a correctness caveat
        self.assertIsNotNone(c["near_field_warning"])
        self.assertNotIn("unreliable", c["near_field_warning"])
        self.assertGreater(c["drag_force_n"], 0)

    def test_farfield_agrees_when_rmp_large(self):
        # small coil + large current → R_mp ≳ 3·R_coil → exact and far-field agree < 1%
        c = ism.compute_magsail(ism_density_cm3=0.1, ion_mass_amu=1.0, beta=0.1,
                                coil_radius_m=1e3, coil_current_a=1e8)
        self.assertGreater(c["magnetopause_radius_km"] * 1000.0, 3.0 * 1e3)       # R_mp ≳ 3·R_coil
        self.assertLess(abs(c["magnetopause_radius_km"] / c["magnetopause_radius_farfield_km"] - 1.0),
                        0.01)
        self.assertIsNone(c["near_field_warning"])

    def test_stopping_distance_time(self):
        d = ism.compute_magsail(beta=0.1, coil_radius_m=1e5, coil_current_a=1e5,
                                vehicle_mass_t=1000, velocity_final_kms=1000)
        self.assertGreater(d["stopping_distance_ly"], 0)
        self.assertGreater(d["stopping_time_yr"], 0)
        # slower target → longer distance and time (the long v^(4/3) tail)
        slower = ism.compute_magsail(beta=0.1, coil_radius_m=1e5, coil_current_a=1e5,
                                     vehicle_mass_t=1000, velocity_final_kms=100)
        self.assertGreater(slower["stopping_time_yr"], d["stopping_time_yr"])
        self.assertGreater(slower["stopping_distance_ly"], d["stopping_distance_ly"])

    def test_stopping_needs_mass(self):
        self.assertIn("error", ism.compute_magsail(beta=0.1, magnetic_moment_am2=1e15,
                                                    velocity_final_kms=1000))

    def test_near_field_warning(self):
        # a huge coil with a tiny current → ram pressure overwhelms the field, R_mp clamped
        d = ism.compute_magsail(beta=0.5, coil_radius_m=1e9, coil_current_a=1.0,
                                ism_density_cm3=0.1, ion_mass_amu=1.0)
        self.assertIsNotNone(d["near_field_warning"])

    def test_ionization_note_present(self):
        self.assertIn("ionized", self._moment()["ionization_note"])

    def test_defaults_are_lic(self):
        d = ism.compute_magsail(beta=0.1, magnetic_moment_am2=1e15)
        self.assertEqual(d["ism_density_cm3"], 0.1)
        self.assertEqual(d["ion_mass_amu"], 1.3)
        self.assertEqual(d["standoff_coeff"], 1.0)
        self.assertEqual(d["drag_coeff"], 1.0)

    # ── A3 — ionization fraction ──
    def test_ionization_default_byte_identical(self):
        # x_ion default (1.0) reproduces the Phase-AC anchors byte-identically
        self.assertEqual(self._moment(vehicle_mass_t=1000),
                         self._moment(vehicle_mass_t=1000, ionization_fraction=1.0))

    def test_ionization_reduces_drag(self):
        # only ions couple → less interacting ρ → less drag (field-derived R_mp: drag ∝ ρ^(2/3))
        full = self._moment()
        half = self._moment(ionization_fraction=0.5)
        self.assertLess(half["drag_force_n"], full["drag_force_n"])
        self.assertEqual(half["ionization_fraction"], 0.5)
        self.assertAlmostEqual(half["ism_mass_density_kgm3"],
                               0.5 * full["ism_mass_density_kgm3"], places=30)

    def test_determinism(self):
        self.assertEqual(self._moment(vehicle_mass_t=1000), self._moment(vehicle_mass_t=1000))


class MagsailValidationTest(unittest.TestCase):
    def test_matrix(self):
        bad = [
            dict(coil_radius_m=1e5, coil_current_a=1e5),                       # no velocity
            dict(velocity_kms=100, beta=0.1, magnetic_moment_am2=1e15),        # two velocity
            dict(beta=1.0, magnetic_moment_am2=1e15),                          # β = 1
            dict(beta=0.0, magnetic_moment_am2=1e15),                          # β = 0
            dict(beta=0.1, coil_radius_m=1e5),                                 # partial coil
            dict(beta=0.1, coil_radius_m=1e5, coil_current_a=1e5,
                 magnetic_moment_am2=1e15),                                    # two sail anchors
            dict(beta=0.1, magnetic_moment_am2=1e15, ism_density_cm3=-1),      # neg density
            dict(beta=0.1, magnetic_moment_am2=1e15, ion_mass_amu=0),          # zero ion mass
            dict(beta=0.1, magnetic_moment_am2=-1),                            # neg moment
            dict(beta=0.1, magnetic_moment_am2=1e15, drag_coeff=0),            # C_d ≤ 0
            dict(beta=0.1, magnetic_moment_am2=1e15, standoff_coeff=-1),       # k ≤ 0
            dict(beta=0.1, magnetic_moment_am2=1e15, vehicle_mass_t=-1),       # neg mass
            dict(beta=0.1, magnetic_moment_am2=1e15, velocity_final_kms=1000), # vf no mass
            dict(beta=0.1, magnetic_moment_am2=1e15, vehicle_mass_t=1000,
                 velocity_final_kms=1e9),                                      # vf ≥ v0
            dict(beta=0.1, magnetic_moment_am2=1e15, vehicle_mass_t=1000,
                 velocity_final_kms=-5),                                       # vf ≤ 0
            dict(beta=0.1, magnetic_moment_am2=1e15, ionization_fraction=0),   # x_ion ≤ 0
            dict(beta=0.1, magnetic_moment_am2=1e15, ionization_fraction=1.5), # x_ion > 1
        ]
        for kw in bad:
            self.assertIn("error", ism.compute_magsail(**kw), kw)


class RamscoopAnchorTest(unittest.TestCase):
    def test_pp_ideal_exhaust_velocity(self):
        # ideal p-p: v_e = c·√(2·f), f = 0.0071 → ≈ 0.1192 c
        d = ism.compute_ramscoop(fuel="pp", fusion_efficiency=1.0, beta=0.1,
                                 magnetic_moment_am2=1e15)
        self.assertAlmostEqual(d["exhaust_beta"], math.sqrt(2 * 0.0071), places=4)
        self.assertAlmostEqual(d["exhaust_beta"], 0.1192, delta=0.001)

    def test_pp_default_eta_is_brake(self):
        d = ism.compute_ramscoop(fuel="pp", beta=0.1, coil_radius_m=1e5, coil_current_a=1e5)
        self.assertEqual(d["fusion_efficiency"], 0.1)          # low default
        self.assertEqual(d["verdict"], "brake")
        self.assertLess(d["net_force_n"], 0)

    def test_ideal_margin_exists_but_drag_flips_to_brake(self):
        # the Zubrin & Andrews result: v_e > v (reaction > collection) yet drag → brake
        d = ism.compute_ramscoop(fuel="pp", fusion_efficiency=1.0, beta=0.1,
                                 coil_radius_m=1e5, coil_current_a=1e5)
        self.assertGreater(d["reaction_thrust_n"], d["collection_drag_n"])   # v_e > v margin
        self.assertGreater(d["magnetic_drag_n"], 0)
        self.assertLess(d["net_force_n"], 0)
        self.assertEqual(d["verdict"], "brake")

    def test_drive_at_low_beta_high_eta(self):
        d = ism.compute_ramscoop(fuel="pp", fusion_efficiency=1.0, beta=0.01, scoop_area_km2=1000)
        self.assertEqual(d["verdict"], "drive")
        self.assertGreater(d["net_force_n"], 0)

    def test_crossover_is_ve_over_1_plus_cd_half(self):
        d = ism.compute_ramscoop(fuel="pp", fusion_efficiency=0.1, beta=0.1, scoop_area_km2=1000)
        self.assertAlmostEqual(d["crossover_velocity_kms"],
                               d["exhaust_velocity_kms"] / (1.0 + d["drag_coeff"] / 2.0), places=6)

    def test_explicit_exhaust_velocity(self):
        d = ism.compute_ramscoop(exhaust_velocity_kms=50000, beta=0.05, scoop_area_km2=1000)
        self.assertAlmostEqual(d["exhaust_velocity_kms"], 50000.0, places=6)
        self.assertIsNone(d["fuel"])
        self.assertIsNone(d["fusion_efficiency"])

    def test_mass_flux_and_forces_explicit(self):
        d = ism.compute_ramscoop(exhaust_velocity_kms=100000, velocity_kms=30000,
                                 scoop_area_km2=1000, ism_density_cm3=0.1, ion_mass_amu=1.0,
                                 drag_coeff=1.0)
        rho = 0.1 * 1e6 * 1.0 * _AMU_KG
        v = 30000 * 1000.0
        a_mp = 1000 * 1e6
        m_dot = rho * v * a_mp
        self.assertAlmostEqual(d["collected_mass_flux_kgs"], m_dot, places=6)
        self.assertAlmostEqual(d["reaction_thrust_n"], m_dot * 100000 * 1000.0, places=3)
        self.assertAlmostEqual(d["collection_drag_n"], m_dot * v, places=3)
        self.assertAlmostEqual(d["magnetic_drag_n"], 0.5 * rho * v ** 2 * a_mp, places=3)

    # ── A3 — ionization fraction ──
    def test_ionization_default_byte_identical(self):
        kw = dict(fuel="pp", beta=0.1, scoop_area_km2=1000)
        self.assertEqual(ism.compute_ramscoop(**kw),
                         ism.compute_ramscoop(**kw, ionization_fraction=1.0))

    def test_ionization_halves_drag_and_flux(self):
        # fixed scoop area → drag & collected mass flux ∝ ρ → x_ion=0.5 halves both
        full = ism.compute_ramscoop(fuel="pp", beta=0.1, scoop_area_km2=1000)
        half = ism.compute_ramscoop(fuel="pp", beta=0.1, scoop_area_km2=1000,
                                    ionization_fraction=0.5)
        self.assertAlmostEqual(full["magnetic_drag_n"] / half["magnetic_drag_n"], 2.0, places=6)
        self.assertAlmostEqual(full["collected_mass_flux_kgs"] / half["collected_mass_flux_kgs"],
                               2.0, places=6)
        self.assertEqual(half["ionization_fraction"], 0.5)

    def test_determinism(self):
        kw = dict(fuel="pp", beta=0.1, scoop_area_km2=1000)
        self.assertEqual(ism.compute_ramscoop(**kw), ism.compute_ramscoop(**kw))


class RamscoopValidationTest(unittest.TestCase):
    def test_matrix(self):
        bad = [
            dict(scoop_area_km2=1000),                                          # no velocity
            dict(beta=0.1, fuel="pp"),                                          # no scoop
            dict(beta=0.1, scoop_area_km2=1000),                               # no exhaust
            dict(beta=0.1, scoop_area_km2=1000, fuel="pp",
                 exhaust_velocity_kms=1e4),                                    # two exhaust
            dict(beta=0.1, scoop_area_km2=1000, fuel="xyz"),                   # unknown fuel
            dict(beta=0.1, scoop_area_km2=1000, fuel="pp", fusion_efficiency=2.0),  # η > 1
            dict(beta=0.1, scoop_area_km2=1000, fuel="pp", fusion_efficiency=0),    # η = 0
            dict(beta=0.1, scoop_area_km2=1000, coil_radius_m=1e5,
                 coil_current_a=1e5, fuel="pp"),                              # area + field
            dict(beta=0.1, scoop_area_km2=1000, exhaust_velocity_kms=1e4,
                 fusion_efficiency=0.5),                                       # η with explicit v_e
            dict(beta=0.1, scoop_area_km2=-1, fuel="pp"),                     # neg area
            dict(beta=0.1, scoop_area_km2=1000, exhaust_velocity_kms=-1),      # neg v_e
            dict(beta=0.1, scoop_area_km2=1000, fuel="pp", ism_density_cm3=0), # zero density
            dict(beta=0.1, scoop_area_km2=1000, fuel="pp", ionization_fraction=0),    # x_ion ≤ 0
            dict(beta=0.1, scoop_area_km2=1000, fuel="pp", ionization_fraction=1.1),  # x_ion > 1
        ]
        for kw in bad:
            self.assertIn("error", ism.compute_ramscoop(**kw), kw)


class BundledTableTest(unittest.TestCase):
    def test_fusion_fractions_pinned(self):
        self.assertEqual(t._FUSION["pp"]["f"], 0.0071)
        self.assertEqual(t._FUSION["cno"]["f"], 0.0071)
        self.assertEqual(t._FUSION["dd"]["f"], 0.0038)

    def test_defaults_pinned(self):
        self.assertEqual(t._DEFAULT_N_CM3, 0.1)
        self.assertEqual(t._MEAN_ION_MASS_AMU, 1.3)
        self.assertEqual(t._STANDOFF_COEFF_K, 1.0)
        self.assertEqual(t._DRAG_COEFF_CD, 1.0)
        self.assertEqual(t._DEFAULT_FUSION_EFFICIENCY, 0.1)

    def test_pp_verifiable_from_first_principles(self):
        # p-p chain: 26.73 MeV released / (4 protons × 938.272 MeV) ≈ 0.712%
        self.assertAlmostEqual(t._FUSION["pp"]["f"], 26.73 / (4 * 938.272), delta=2e-4)


class FissionTableTest(unittest.TestCase):
    """R5 (Phase AL) — the _FISSION mass→energy fractions (recoverable) + f·c² ceilings."""

    def test_u235_pinned_and_first_principles(self):
        # ~200 MeV recoverable / (235.04 u × 931.494 MeV/u) ≈ 9.14e-4.
        self.assertAlmostEqual(t._FISSION["u235"]["f"], 9.14e-4, delta=2e-6)
        self.assertAlmostEqual(t._FISSION["u235"]["f"], 200.0 / (235.04 * 931.494), delta=2e-6)

    def test_u235_storage_energy_density(self):
        # f·c² storage ceiling ≈ 8.21e13 J/kg (agrees with 8.31e13 precise within ~1.2%).
        self.assertAlmostEqual(t._FISSION["u235"]["f"] * _C_MS ** 2, 8.21e13, delta=1e11)

    def test_pu239_pinned(self):
        self.assertAlmostEqual(t._FISSION["pu239"]["f"], 9.3e-4, delta=2e-6)

    def test_rows_flag_antineutrino_loss(self):
        for row in t._FISSION.values():
            self.assertIn("antineutrino", row["note"].lower())


if __name__ == "__main__":
    unittest.main()
