# tests/test_volatile_delivery.py — Phase AD (C5) volatile-delivery core (in-process).
#
# Covers core/volatile_delivery.py (compute_volatile_delivery) against the acceptance anchors
# (delivered mass, impact energy + TNT, bodies-needed, the rocket-equation redirect mass ratio),
# the optional-add-on null behaviour, and the self-validating ({"error"}) matrix. No net/DB/RNG.

import math
import unittest

import core.volatile_delivery as volatile_delivery
from core import propulsion

V = volatile_delivery.compute_volatile_delivery
_TNT = volatile_delivery._TNT_J_PER_KG


class VolatileDeliveryAcceptanceTest(unittest.TestCase):
    def test_delivered_impact_and_bodies_anchor(self):
        # M 1e15, f 0.5, v_impact 20 km/s → delivered 5e14 kg; E=½Mv²=2e23 J;
        # target 5.15e18 → bodies ≈ 10300.
        d = V(body_mass_kg=1e15, volatile_fraction=0.5, impact_velocity_kms=20,
              target_atmosphere_mass_kg=5.15e18)
        self.assertAlmostEqual(d["delivered_volatile_mass_kg"], 5e14, places=0)
        self.assertAlmostEqual(d["impact_energy_j"], 2e23, delta=1e18)
        self.assertAlmostEqual(d["impact_energy_j"], 0.5 * 1e15 * 20000 ** 2, places=0)
        self.assertAlmostEqual(d["impact_energy_tnt_kg"], d["impact_energy_j"] / _TNT, places=3)
        self.assertAlmostEqual(d["bodies_needed"], 5.15e18 / 5e14, places=6)
        self.assertAlmostEqual(d["bodies_needed"], 10300, delta=1)

    def test_redirect_mass_ratio_from_fuel(self):
        # Δv 1 km/s with fusion-dt (v_e≈0.03c ≈ 8993.8 km/s) → modest MR ≈ 1.0001
        d = V(body_mass_kg=1e15, delta_v_kms=1, fuel="fusion-dt")
        ref = propulsion.compute_rocket_equation(delta_v_kms=1, fuel="fusion-dt")
        self.assertAlmostEqual(d["redirect_mass_ratio"], ref["mass_ratio"], places=12)
        self.assertAlmostEqual(d["redirect_mass_ratio"], 1.0001, delta=0.001)
        self.assertGreater(d["redirect_mass_ratio"], 1.0)

    def test_redirect_mass_ratio_from_explicit_ve(self):
        d = V(body_mass_kg=1e15, delta_v_kms=5, exhaust_velocity_kms=10)
        self.assertAlmostEqual(d["redirect_mass_ratio"], math.exp(5 / 10), places=9)

    def test_add_ons_null_when_omitted(self):
        d = V(body_mass_kg=1e15)               # only delivered mass
        self.assertAlmostEqual(d["delivered_volatile_mass_kg"], 5e14, places=0)
        self.assertIsNone(d["redirect_mass_ratio"])
        self.assertIsNone(d["impact_energy_j"])
        self.assertIsNone(d["impact_energy_tnt_kg"])
        self.assertIsNone(d["bodies_needed"])

    def test_volatile_fraction_scales_delivered_and_bodies(self):
        a = V(body_mass_kg=1e15, volatile_fraction=0.5, target_atmosphere_mass_kg=5e18)
        b = V(body_mass_kg=1e15, volatile_fraction=0.25, target_atmosphere_mass_kg=5e18)
        self.assertAlmostEqual(b["delivered_volatile_mass_kg"],
                               a["delivered_volatile_mass_kg"] / 2, places=0)
        self.assertAlmostEqual(b["bodies_needed"], a["bodies_needed"] * 2, places=3)

    def _err(self, **kw):
        self.assertIn("error", V(**kw), kw)

    def test_validation_matrix(self):
        self._err(body_mass_kg=0)                                             # M ≤ 0
        self._err(body_mass_kg=1e15, volatile_fraction=1.5)                   # fraction > 1
        self._err(body_mass_kg=1e15, volatile_fraction=0)                     # fraction ≤ 0
        self._err(body_mass_kg=1e15, impact_velocity_kms=0)                   # v_impact ≤ 0
        self._err(body_mass_kg=1e15, target_atmosphere_mass_kg=0)             # target ≤ 0
        self._err(body_mass_kg=1e15, delta_v_kms=0, fuel="fusion-dt")         # Δv ≤ 0
        self._err(body_mass_kg=1e15, delta_v_kms=1)                           # Δv, no exhaust anchor
        self._err(body_mass_kg=1e15, delta_v_kms=1, fuel="fusion-dt",
                  exhaust_velocity_kms=10)                                    # Δv, two exhaust anchors
        self._err(body_mass_kg=1e15, fuel="fusion-dt")                        # fuel without Δv
        self._err(body_mass_kg=1e15, exhaust_velocity_kms=10)                 # v_e without Δv
        self._err(body_mass_kg=1e15, delta_v_kms=1, fuel="bogus")            # unknown fuel

    def test_determinism(self):
        kw = dict(body_mass_kg=1e15, volatile_fraction=0.5, delta_v_kms=2, fuel="chemical",
                  impact_velocity_kms=20, target_atmosphere_mass_kg=5.15e18)
        self.assertEqual(V(**kw), V(**kw))


if __name__ == "__main__":
    unittest.main()
