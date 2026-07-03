# tests/test_dust_impact.py — Phase AD (C3) hypervelocity dust-impact energetics (in-process).
#
# Covers core/dust_impact.py (compute_dust_impact) against the corrected acceptance anchors
# (the plan's 1.9e2 J / 40 mg figures were computed at v=c, not β 0.1 — see PHASE_AD_PLAN.md
# and the build note below), the relativistic auto-switch, the cumulative-fluence set, and the
# self-validating ({"error"}) matrix. No network/DB/RNG/Qt.
#
# Build note (verified 2026-07-03): a 1 µm / 1000 kg·m⁻³ grain is m ≈ 4.19e-15 kg; at β 0.1 the
# kinetic energy is ½mv² ≈ 1.88 J (≈1.9e0 J), TNT-equivalent ≈ 0.45 mg (1 kg TNT = 4.184e6 J).
# The plan's "1.9e2 J / 40 mg" correspond to v = c. The relativistic KE/momentum form engages
# once β > 0.1 (the plan prose said ~0.01, but its own test cases require false@0.05 / true@0.2).

import math
import unittest

import core.dust_impact as dust_impact
from core.equations import _C_MS

D = dust_impact.compute_dust_impact
_TNT = dust_impact._TNT_J_PER_KG


class DustImpactAcceptanceTest(unittest.TestCase):
    def test_grain_mass_and_energy_anchor(self):
        d = D(grain_radius_um=1, grain_density_kgm3=1000, beta=0.1)
        m_expect = (4.0 / 3.0) * math.pi * (1e-6) ** 3 * 1000
        self.assertAlmostEqual(d["grain_mass_kg"], m_expect, places=20)
        self.assertAlmostEqual(d["grain_mass_kg"], 4.19e-15, delta=1e-17)
        self.assertFalse(d["relativistic"])                       # β 0.1 is NOT > 0.1
        v = 0.1 * _C_MS
        self.assertAlmostEqual(d["impact_energy_j"], 0.5 * m_expect * v ** 2, places=12)
        self.assertAlmostEqual(d["impact_energy_j"], 1.88, delta=0.02)
        self.assertAlmostEqual(d["impact_energy_tnt_kg"], d["impact_energy_j"] / _TNT, places=20)
        self.assertAlmostEqual(d["momentum_kgms"], m_expect * v, places=18)
        self.assertEqual(d["lorentz_factor"], 1.0)

    def test_explicit_mass_matches_geometry(self):
        m = (4.0 / 3.0) * math.pi * (1e-6) ** 3 * 1000
        geom = D(grain_radius_um=1, grain_density_kgm3=1000, beta=0.05)
        expl = D(grain_mass_kg=m, beta=0.05)
        self.assertAlmostEqual(geom["impact_energy_j"], expl["impact_energy_j"], places=15)
        self.assertAlmostEqual(geom["momentum_kgms"], expl["momentum_kgms"], places=18)

    def test_relativistic_auto_switch(self):
        # false at β 0.05, true at β 0.2 (the auto-switch boundary at β > 0.1)
        self.assertFalse(D(grain_radius_um=1, grain_density_kgm3=1000, beta=0.05)["relativistic"])
        d = D(grain_radius_um=1, grain_density_kgm3=1000, beta=0.2)
        self.assertTrue(d["relativistic"])
        gamma = 1.0 / math.sqrt(1.0 - 0.2 ** 2)
        self.assertAlmostEqual(d["lorentz_factor"], gamma, places=9)
        m = d["grain_mass_kg"]
        self.assertAlmostEqual(d["impact_energy_j"], (gamma - 1.0) * m * _C_MS ** 2, places=9)
        self.assertAlmostEqual(d["momentum_kgms"], gamma * m * 0.2 * _C_MS, places=15)

    def test_velocity_kms_and_beta_agree(self):
        vk = D(grain_radius_um=1, grain_density_kgm3=1000, velocity_kms=0.05 * _C_MS / 1000.0)
        bt = D(grain_radius_um=1, grain_density_kgm3=1000, beta=0.05)
        self.assertAlmostEqual(vk["impact_energy_j"], bt["impact_energy_j"], places=12)


class DustImpactCumulativeTest(unittest.TestCase):
    def test_cumulative_present_and_null(self):
        base = D(grain_radius_um=1, grain_density_kgm3=1000, beta=0.2)
        self.assertIsNone(base["impacts_total"])
        self.assertIsNone(base["energy_fluence_j_m2"])
        d = D(grain_radius_um=1, grain_density_kgm3=1000, beta=0.2,
              dust_density_m3=1e-6, frontal_area_m2=100, path_length_ly=4)
        self.assertIsNotNone(d["impacts_total"])
        # fluence = N·E/A, self-consistent
        self.assertAlmostEqual(d["energy_fluence_j_m2"],
                               d["impacts_total"] * d["impact_energy_j"] / 100, places=3)

    def test_impacts_and_fluence_scale_with_path(self):
        kw = dict(grain_radius_um=1, grain_density_kgm3=1000, beta=0.2,
                  dust_density_m3=1e-6, frontal_area_m2=100)
        a = D(path_length_ly=4, **kw)
        b = D(path_length_ly=8, **kw)
        self.assertAlmostEqual(b["impacts_total"], 2 * a["impacts_total"], places=3)
        self.assertAlmostEqual(b["energy_fluence_j_m2"], 2 * a["energy_fluence_j_m2"], places=3)

    def test_impacts_scale_with_density(self):
        kw = dict(grain_radius_um=1, grain_density_kgm3=1000, beta=0.2,
                  frontal_area_m2=100, path_length_ly=4)
        a = D(dust_density_m3=1e-6, **kw)
        b = D(dust_density_m3=2e-6, **kw)
        self.assertAlmostEqual(b["impacts_total"], 2 * a["impacts_total"], places=3)


class DustImpactHandoffTest(unittest.TestCase):
    def test_no_penetration_key_but_handoff_note(self):
        d = D(grain_radius_um=1, grain_density_kgm3=1000, beta=0.1)
        self.assertIn("penetration_handoff_note", d)
        self.assertTrue(d["penetration_handoff_note"])
        # No penetration depth/crater key is emitted (deliberately handed off)
        leaked = [k for k in d if k.startswith("penetration_") and k != "penetration_handoff_note"]
        self.assertEqual(leaked, [])
        self.assertIn("shielding-attenuation", d["penetration_handoff_note"])


class DustImpactValidationTest(unittest.TestCase):
    def _err(self, **kw):
        self.assertIn("error", D(**kw), kw)

    def test_matrix(self):
        self._err(beta=0.1)                                                   # no grain anchor
        self._err(grain_radius_um=1, grain_density_kgm3=1000,
                  grain_mass_kg=1, beta=0.1)                                  # two grain anchors
        self._err(grain_radius_um=1, beta=0.1)                               # radius w/o density
        self._err(grain_radius_um=0, grain_density_kgm3=1000, beta=0.1)      # radius ≤ 0
        self._err(grain_radius_um=1, grain_density_kgm3=0, beta=0.1)         # density ≤ 0
        self._err(grain_mass_kg=0, beta=0.1)                                 # mass ≤ 0
        self._err(grain_radius_um=1, grain_density_kgm3=1000)               # no velocity anchor
        self._err(grain_radius_um=1, grain_density_kgm3=1000,
                  velocity_kms=1000, beta=0.1)                               # two velocity anchors
        self._err(grain_radius_um=1, grain_density_kgm3=1000, beta=1.0)      # β ∉ (0,1)
        self._err(grain_radius_um=1, grain_density_kgm3=1000, velocity_kms=0)  # velocity ≤ 0
        # partial cumulative set (need all three or none)
        self._err(grain_radius_um=1, grain_density_kgm3=1000, beta=0.1,
                  frontal_area_m2=100)
        self._err(grain_radius_um=1, grain_density_kgm3=1000, beta=0.1,
                  dust_density_m3=1e-6, frontal_area_m2=100)
        # non-positive cumulative members
        self._err(grain_radius_um=1, grain_density_kgm3=1000, beta=0.1,
                  dust_density_m3=0, frontal_area_m2=100, path_length_ly=4)
        self._err(grain_radius_um=1, grain_density_kgm3=1000, beta=0.1,
                  dust_density_m3=1e-6, frontal_area_m2=0, path_length_ly=4)
        self._err(grain_radius_um=1, grain_density_kgm3=1000, beta=0.1,
                  dust_density_m3=1e-6, frontal_area_m2=100, path_length_ly=0)

    def test_determinism(self):
        kw = dict(grain_radius_um=1, grain_density_kgm3=1000, beta=0.2,
                  dust_density_m3=1e-6, frontal_area_m2=100, path_length_ly=4)
        self.assertEqual(D(**kw), D(**kw))


if __name__ == "__main__":
    unittest.main()
