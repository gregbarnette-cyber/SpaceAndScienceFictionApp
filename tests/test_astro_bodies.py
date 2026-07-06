# tests/test_astro_bodies.py — Phase 0 (AE–AI) shared mass/radius/preset resolver.
#
# Offline unit tests for core.astro_bodies: the exactly-one multi-unit gate, positivity,
# unit conversions, and the body/object preset tables. No network, no Qt, no DB.

import math
import unittest

import core.astro_bodies as ab
from core.equations import (
    _SOLAR_MASS_KG, _EARTH_MASS_KG, _JUP_MASS_KG,
    _SUN_RADIUS_M, _EARTH_RADIUS_M, _M_PER_AU,
    _HBAR, _PLANCK_H,
)


class ConstantsTest(unittest.TestCase):
    def test_hbar_derived(self):
        self.assertAlmostEqual(_HBAR, _PLANCK_H / (2.0 * math.pi), places=45)
        self.assertAlmostEqual(_HBAR, 1.054571817e-34, delta=1e-42)


class ResolveMassTest(unittest.TestCase):
    def test_each_unit(self):
        self.assertEqual(ab.resolve_mass(kg=5.0), (5.0, "kg"))
        self.assertEqual(ab.resolve_mass(msun=1.0), (_SOLAR_MASS_KG, "msun"))
        self.assertEqual(ab.resolve_mass(mearth=1.0), (_EARTH_MASS_KG, "mearth"))
        self.assertEqual(ab.resolve_mass(mjup=1.0), (_JUP_MASS_KG, "mjup"))

    def test_none_supplied(self):
        r = ab.resolve_mass()
        self.assertIsInstance(r, dict)
        self.assertIn("error", r)

    def test_two_supplied(self):
        r = ab.resolve_mass(kg=1.0, msun=1.0)
        self.assertIsInstance(r, dict)
        self.assertIn("error", r)

    def test_nonpositive(self):
        for bad in (0.0, -1.0):
            r = ab.resolve_mass(kg=bad)
            self.assertIsInstance(r, dict)
            self.assertIn("error", r)

    def test_custom_name_in_message(self):
        r = ab.resolve_mass(name="primary mass")
        self.assertIn("primary mass", r["error"])


class ResolveRadiusTest(unittest.TestCase):
    def test_each_unit(self):
        self.assertEqual(ab.resolve_radius(m=2.0), (2.0, "m"))
        self.assertEqual(ab.resolve_radius(rsun=1.0), (_SUN_RADIUS_M, "rsun"))
        self.assertEqual(ab.resolve_radius(rearth=1.0), (_EARTH_RADIUS_M, "rearth"))
        self.assertEqual(ab.resolve_radius(au=1.0), (_M_PER_AU, "au"))

    def test_gate_and_positivity(self):
        self.assertIn("error", ab.resolve_radius())
        self.assertIn("error", ab.resolve_radius(m=1.0, au=1.0))
        self.assertIn("error", ab.resolve_radius(m=-1.0))


class PresetTest(unittest.TestCase):
    def test_body_preset_earth(self):
        e = ab.body_preset("earth")
        self.assertEqual(e["mass_kg"], _EARTH_MASS_KG)
        self.assertEqual(e["radius_m"], _EARTH_RADIUS_M)
        self.assertEqual(e["display"], "Earth")

    def test_body_preset_unknown(self):
        self.assertIn("error", ab.body_preset("nope"))

    def test_object_preset_sgr_a(self):
        o = ab.object_preset("sgr-a-star")
        self.assertAlmostEqual(o["mass_kg"], 4.15e6 * _SOLAR_MASS_KG, delta=1e30)

    def test_preset_keys_sorted(self):
        self.assertEqual(ab.BODY_PRESET_KEYS, sorted(ab.BODY_PRESET_KEYS))
        self.assertIn("jupiter", ab.BODY_PRESET_KEYS)
        self.assertIn("m87-star", ab.OBJECT_PRESET_KEYS)

    def test_returned_dict_is_copy(self):
        # mutating the returned dict must not corrupt the table
        e = ab.body_preset("mars")
        e["mass_kg"] = 0
        self.assertNotEqual(ab.body_preset("mars")["mass_kg"], 0)


if __name__ == "__main__":
    unittest.main()
