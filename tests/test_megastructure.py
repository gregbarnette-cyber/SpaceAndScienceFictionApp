# tests/test_megastructure.py — Phase Z megastructure-scale core (in-process).
#
# Covers core/megastructure.py (compute_spin_stress, compute_tether_taper,
# compute_dyson_collector) against the Group-H acceptance anchors, the researched
# material table + taper closed form (validated: steel→impossible, CNT→~1.9), the
# bundled-table integrity, and the self-validating ({"error"}) matrix. No network/DB/RNG/Qt.

import math
import unittest

import core.megastructure as megastructure
from core import materials_tables

S = megastructure.compute_spin_stress
T = megastructure.compute_tether_taper
D = megastructure.compute_dyson_collector


class SpinStressTest(unittest.TestCase):
    def test_steel_anchor(self):
        # steel (σ 400 MPa, ρ 7850), SF 1, 1 g → v_max ≈ 226 m/s, r_max ≈ 5.2 km
        d = S(material="structural-steel", target_gravity_g=1, safety_factor=1)
        self.assertAlmostEqual(d["max_tangential_velocity_ms"], 225.7, delta=0.5)
        self.assertAlmostEqual(d["max_radius_km"], 5.196, delta=0.02)

    def test_carbon_fiber_anchor(self):
        # carbon-fiber (σ 4000, ρ 1600) → v_max ≈ 1580 m/s, r_max ≈ 254 km
        d = S(material="carbon-fiber", target_gravity_g=1, safety_factor=1)
        self.assertAlmostEqual(d["max_tangential_velocity_ms"], 1581, delta=5)
        self.assertAlmostEqual(d["max_radius_km"], 254.8, delta=1.0)

    def test_radius_form_gives_max_gravity(self):
        d = S(material="structural-steel", radius_m=1000, safety_factor=1)
        self.assertAlmostEqual(d["max_gravity_g"], 5.196, delta=0.02)
        self.assertIsNone(d["max_radius_km"])

    def test_rpm_form_hoop_stress_and_margin(self):
        d = S(material="structural-steel", rpm=2, radius_m=100, safety_factor=1)
        # v = ω r = (2·2π/60)·100 = 20.94 m/s; σ = ρv² = 7850·438.6 = 3.44 MPa
        self.assertAlmostEqual(d["hoop_stress_mpa"], 3.443, delta=0.01)
        self.assertAlmostEqual(d["margin"], 400 / 3.443, delta=0.5)

    def test_explicit_equals_material(self):
        a = S(material="structural-steel", target_gravity_g=1, safety_factor=1)
        b = S(density_kgm3=7850, tensile_strength_mpa=400, target_gravity_g=1, safety_factor=1)
        self.assertAlmostEqual(a["max_radius_km"], b["max_radius_km"], places=6)

    def test_default_safety_factor_shrinks(self):
        sf1 = S(material="structural-steel", target_gravity_g=1, safety_factor=1)["max_radius_km"]
        sf3 = S(material="structural-steel", target_gravity_g=1)["max_radius_km"]  # SF=3 default
        self.assertAlmostEqual(sf3, sf1 / 3.0, delta=0.01)

    def _err(self, **kw):
        self.assertIn("error", S(**kw), kw)

    def test_validation_matrix(self):
        self._err(material="steelx", target_gravity_g=1)                 # unknown material
        self._err(target_gravity_g=1)                                    # no material
        self._err(density_kgm3=1000, target_gravity_g=1)                 # explicit missing σ
        self._err(material="structural-steel", density_kgm3=1000, target_gravity_g=1)  # both
        self._err(material="structural-steel", safety_factor=0.5, target_gravity_g=1)  # SF<1
        self._err(material="structural-steel")                           # no solve form
        self._err(material="structural-steel", target_gravity_g=1, radius_m=5)  # two forms
        self._err(material="structural-steel", rpm=2)                    # rpm without radius
        self._err(material="structural-steel", target_gravity_g=-1)      # non-positive g
        self._err(material="structural-steel", radius_m=0)               # non-positive radius


class TetherTaperTest(unittest.TestCase):
    def test_cnt_earth_canonical(self):
        # CNT@100 GPa, Earth, SF 1 → taper ≈ 1.9 (the canonical "modest taper" result)
        d = T(material="cnt-theoretical", body="earth", safety_factor=1)
        self.assertAlmostEqual(d["taper_ratio"], 1.923, delta=0.02)
        self.assertTrue(d["feasible"])

    def test_graphene_earth(self):
        d = T(material="graphene-theoretical", body="earth", safety_factor=1)
        self.assertAlmostEqual(d["taper_ratio"], 2.27, delta=0.05)
        self.assertTrue(d["feasible"])

    def test_steel_earth_impossible(self):
        d = T(material="structural-steel", body="earth", safety_factor=1)
        self.assertIsNone(d["taper_ratio"])       # overflow → ∞
        self.assertFalse(d["feasible"])

    def test_kevlar_impractical(self):
        d = T(material="kevlar", body="earth", safety_factor=1)
        self.assertIsNotNone(d["taper_ratio"])
        self.assertGreater(d["taper_ratio"], 10)  # ≫10 → impractical
        self.assertFalse(d["feasible"])

    def test_explicit_body_matches_bundled_earth(self):
        a = T(material="cnt-theoretical", body="earth", safety_factor=1)
        b = T(material="cnt-theoretical", surface_gravity_ms2=9.81, surface_radius_km=6371,
              geo_radius_km=42164, safety_factor=1)
        self.assertAlmostEqual(a["taper_ratio"], b["taper_ratio"], places=4)

    def test_moon_carries_caveat(self):
        d = T(material="cnt-theoretical", body="moon", safety_factor=1)
        self.assertTrue(any("Hill sphere" in n for n in d["notes"]))

    def _err(self, **kw):
        self.assertIn("error", T(**kw), kw)

    def test_validation_matrix(self):
        self._err(material="steelx", body="earth")                       # unknown material
        self._err(body="earth")                                          # no material
        self._err(material="kevlar", body="pluto")                       # unknown body
        self._err(material="kevlar")                                     # no body
        self._err(material="kevlar", body="earth", surface_gravity_ms2=9.81)  # body+explicit
        self._err(material="kevlar", surface_gravity_ms2=9.81, geo_radius_km=42164)  # explicit missing R
        self._err(material="kevlar", surface_gravity_ms2=9.81, surface_radius_km=6371, geo_radius_km=100)  # Rs≤R
        self._err(material="kevlar", body="earth", safety_factor=0.5)    # SF<1


class DysonCollectorTest(unittest.TestCase):
    def test_sun_anchor(self):
        # Sun, f 0.01, 1 AU → P ≈ 3.8e24 W, area ≈ 2.8e21 m²
        d = D(luminosity_lsun=1.0, fraction=0.01, orbit_au=1.0)
        self.assertAlmostEqual(d["intercepted_power_w"], 3.828e24, delta=1e22)
        self.assertAlmostEqual(d["collector_area_m2"], 2.812e21, delta=1e19)
        self.assertAlmostEqual(d["incident_flux_wm2"], 1361, delta=5)   # solar constant

    def test_mass_and_area_scaling(self):
        d = D(luminosity_lsun=1.0, fraction=0.5, orbit_au=2.0, areal_mass_kgm2=0.02)
        self.assertAlmostEqual(d["collector_mass_kg"], d["collector_area_m2"] * 0.02, places=3)
        # full sphere at 2 AU: area = f·4π(2·AU)² → 4× the 1 AU sphere at same f
        ref = D(luminosity_lsun=1.0, fraction=0.5, orbit_au=1.0)
        self.assertAlmostEqual(d["collector_area_m2"], ref["collector_area_m2"] * 4, delta=1e18)

    def _err(self, **kw):
        self.assertIn("error", D(**kw), kw)

    def test_validation_matrix(self):
        self._err(luminosity_lsun=0, fraction=0.01, orbit_au=1)          # L ≤ 0
        self._err(luminosity_lsun=1, fraction=1.5, orbit_au=1)           # fraction > 1
        self._err(luminosity_lsun=1, fraction=0, orbit_au=1)             # fraction = 0
        self._err(luminosity_lsun=1, fraction=0.01, orbit_au=0)          # orbit ≤ 0
        self._err(luminosity_lsun=1, fraction=0.01, orbit_au=1, areal_mass_kgm2=0)  # areal mass ≤ 0


class TableIntegrityTest(unittest.TestCase):
    def test_materials_golden(self):
        m = materials_tables._MATERIALS
        self.assertEqual(set(m), {"structural-steel", "titanium-alloy", "aluminium-alloy",
                                  "carbon-fiber", "kevlar", "uhmwpe", "basalt-fiber",
                                  "silicon-carbide", "cnt-theoretical", "graphene-theoretical"})
        self.assertEqual((m["structural-steel"]["rho"], m["structural-steel"]["sigma_mpa"]), (7850, 400))
        self.assertEqual((m["carbon-fiber"]["rho"], m["carbon-fiber"]["sigma_mpa"]), (1600, 4000))
        self.assertEqual(m["cnt-theoretical"]["sigma_mpa"], 100000)      # researched theoretical
        self.assertEqual(m["graphene-theoretical"]["sigma_mpa"], 130000)
        # brittle + nanomaterial + raw-fiber flags present
        self.assertIn("BRITTLE", m["silicon-carbide"]["flag"])
        self.assertIn("RAW FILAMENT", m["carbon-fiber"]["flag"])
        for k in ("cnt-theoretical", "graphene-theoretical"):
            self.assertIn("MTA", m[k]["flag"])

    def test_bodies_golden(self):
        b = materials_tables._BODIES
        self.assertEqual(set(b), {"earth", "mars", "moon", "ceres"})
        self.assertEqual((b["earth"]["R_km"], b["earth"]["Rs_km"], b["earth"]["g0"]), (6371, 42164, 9.81))

    def test_determinism(self):
        a = T(material="cnt-theoretical", body="earth")
        c = T(material="cnt-theoretical", body="earth")
        self.assertEqual(a, c)


if __name__ == "__main__":
    unittest.main()
