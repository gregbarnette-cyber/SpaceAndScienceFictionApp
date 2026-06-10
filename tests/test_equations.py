# tests/test_equations.py — offline coverage for the pure-math equation core.
#
# Covers core/equations.py (HZ, planetary orbit, moon orbital distance via
# Kepler's third law, the three centrifugal-gravity functions) and the two
# shared helpers core/shared._kopparapu_seff and core/shared._format_travel_time.
# No network, no Qt, no DB.

import math
import unittest

from core import equations
from core import shared


class KopparapuSeffTest(unittest.TestCase):
    """shared._kopparapu_seff — all six zone keys."""

    ZONE_KEYS = ["rv", "rg5", "rg01", "rg", "mg", "em"]

    def test_all_six_keys_at_solar_teff(self):
        # At teff = 5780 K, tS = 0, so Seff == the SeffSUN coefficient exactly.
        expected_seffsun = {
            "rv": 1.776, "rg5": 1.188, "rg01": 0.99,
            "rg": 1.107, "mg": 0.356, "em": 0.320,
        }
        for key in self.ZONE_KEYS:
            self.assertAlmostEqual(
                shared._kopparapu_seff(5780.0, key), expected_seffsun[key], places=9,
                msg=f"zone {key}",
            )

    def test_shared_matches_equations_copy(self):
        # The two Kopparapu coefficient tables (shared.py + equations.py) must agree.
        for key in self.ZONE_KEYS:
            for teff in (3500.0, 4900.0, 5780.0, 6500.0):
                self.assertAlmostEqual(
                    shared._kopparapu_seff(teff, key),
                    equations._kopparapu_seff(teff, key),
                    places=12,
                    msg=f"zone {key} @ {teff}K",
                )

    def test_teff_dependence(self):
        # Seff varies with temperature (non-zero tS term), so a hotter star
        # should not reproduce the solar value.
        self.assertNotAlmostEqual(
            shared._kopparapu_seff(7000.0, "rg"),
            shared._kopparapu_seff(5780.0, "rg"),
            places=4,
        )


class HabitableZoneTest(unittest.TestCase):
    """equations.compute_habitable_zone."""

    def test_returns_six_zones_in_order(self):
        zones = equations.compute_habitable_zone(5778.0, 1.0)
        self.assertEqual(len(zones), 6)
        self.assertEqual(
            [z["key"] for z in zones],
            ["rv", "rg5", "rg", "rg01", "mg", "em"],
        )

    def test_known_good_solar_boundaries(self):
        # At teff = 5780 K (tS = 0) and L = 1.0, au = sqrt(1 / SeffSUN).
        zones = {z["key"]: z for z in equations.compute_habitable_zone(5780.0, 1.0)}
        self.assertAlmostEqual(zones["rv"]["au"], math.sqrt(1.0 / 1.776), places=6)
        self.assertAlmostEqual(zones["rg"]["au"], math.sqrt(1.0 / 1.107), places=6)
        self.assertAlmostEqual(zones["mg"]["au"], math.sqrt(1.0 / 0.356), places=6)
        self.assertAlmostEqual(zones["em"]["au"], math.sqrt(1.0 / 0.320), places=6)
        # Light-minutes column is AU × 8.3167.
        self.assertAlmostEqual(zones["rg"]["lm"], zones["rg"]["au"] * 8.3167, places=6)

    def test_inner_is_closer_than_outer(self):
        # Recent Venus (rv, hottest/innermost) must sit inside Early Mars (em).
        zones = {z["key"]: z for z in equations.compute_habitable_zone(5778.0, 1.0)}
        self.assertLess(zones["rv"]["au"], zones["em"]["au"])

    def test_luminosity_scaling(self):
        # au ∝ sqrt(L): quadrupling L doubles every boundary distance.
        z1 = {z["key"]: z["au"] for z in equations.compute_habitable_zone(4900.0, 0.15)}
        z2 = {z["key"]: z["au"] for z in equations.compute_habitable_zone(4900.0, 0.60)}
        for key in z1:
            self.assertAlmostEqual(z2[key] / z1[key], 2.0, places=6, msg=key)

    def test_cool_dwarf_structure(self):
        zones = equations.compute_habitable_zone(3500.0, 0.02)
        for z in zones:
            self.assertGreater(z["au"], 0.0)
            self.assertGreater(z["seff"], 0.0)

    def test_bad_input_raises(self):
        # Negative luminosity → math domain error (query.py's top-level handler
        # turns this into an {"error": ...} dict; the core function itself raises).
        with self.assertRaises(ValueError):
            equations.compute_habitable_zone(5778.0, -1.0)


class OrbitPeriastronApastronTest(unittest.TestCase):
    """equations.compute_orbit_periastron_apastron (opt 33)."""

    def test_circular_orbit(self):
        r = equations.compute_orbit_periastron_apastron(1.0, 0.0)
        self.assertAlmostEqual(r["periastron"], 1.0)
        self.assertAlmostEqual(r["apastron"], 1.0)
        self.assertAlmostEqual(r["ecc_au"], 0.0)

    def test_eccentric_orbit(self):
        r = equations.compute_orbit_periastron_apastron(2.0, 0.5)
        self.assertAlmostEqual(r["periastron"], 1.0)   # 2 × (1 - 0.5)
        self.assertAlmostEqual(r["apastron"], 3.0)     # 2 × (1 + 0.5)
        self.assertAlmostEqual(r["ecc_au"], 1.0)       # 2 × 0.5
        # periastron + apastron == 2 × sma always.
        self.assertAlmostEqual(r["periastron"] + r["apastron"], 2.0 * 2.0)


class MoonOrbitalDistanceTest(unittest.TestCase):
    """equations.compute_moon_orbital_distance (opts 34/35) — Kepler's third law."""

    def _expected_km(self, mass_earth, day_hours):
        EARTH_MASS_KG = 5.972e24
        G = 6.674e-11
        T = day_hours * 3600.0
        r_m = (G * mass_earth * EARTH_MASS_KG * T ** 2 / (4.0 * math.pi ** 2)) ** (1.0 / 3.0)
        return r_m / 1000.0

    def test_earth_24h(self):
        r = equations.compute_moon_orbital_distance(1.0, 24.0)
        self.assertAlmostEqual(r["orbital_distance_km"], self._expected_km(1.0, 24.0), places=2)

    def test_longer_day_is_farther(self):
        short = equations.compute_moon_orbital_distance(1.0, 24.0)["orbital_distance_km"]
        long_ = equations.compute_moon_orbital_distance(1.0, 48.0)["orbital_distance_km"]
        self.assertGreater(long_, short)
        # Period scaling: r ∝ T^(2/3); doubling T multiplies r by 2^(2/3).
        self.assertAlmostEqual(long_ / short, 2.0 ** (2.0 / 3.0), places=6)

    def test_more_massive_planet_is_farther(self):
        light = equations.compute_moon_orbital_distance(1.0, 24.0)["orbital_distance_km"]
        heavy = equations.compute_moon_orbital_distance(8.0, 24.0)["orbital_distance_km"]
        # r ∝ M^(1/3); 8× mass → 2× distance.
        self.assertAlmostEqual(heavy / light, 2.0, places=6)


class CentrifugalGravityTest(unittest.TestCase):
    """equations centrifugal-gravity functions (opts 36/37/38) + mutual inverses."""

    def test_acceleration_known_value(self):
        # ω = rpm·2π/60; a = ω²·r. At 2 rpm, r = 100 m.
        rpm, r = 2.0, 100.0
        omega = rpm * 2.0 * math.pi / 60.0
        out = equations.compute_centrifugal_gravity_acceleration(rpm, r)
        self.assertAlmostEqual(out["accel_ms2"], omega ** 2 * r, places=9)

    def test_distance_is_inverse_of_acceleration(self):
        rpm, r = 2.0, 100.0
        a = equations.compute_centrifugal_gravity_acceleration(rpm, r)["accel_ms2"]
        r_back = equations.compute_centrifugal_gravity_distance(rpm, a)["radius_m"]
        self.assertAlmostEqual(r_back, r, places=6)

    def test_rpm_is_inverse_of_acceleration(self):
        rpm, r = 2.0, 100.0
        a = equations.compute_centrifugal_gravity_acceleration(rpm, r)["accel_ms2"]
        rpm_back = equations.compute_centrifugal_gravity_rpm(a, r)["rpm"]
        self.assertAlmostEqual(rpm_back, rpm, places=6)

    def test_full_mutual_inverse_cycle(self):
        # rpm → accel → distance → rpm should round-trip.
        rpm0, r0 = 3.5, 56.0
        a = equations.compute_centrifugal_gravity_acceleration(rpm0, r0)["accel_ms2"]
        r1 = equations.compute_centrifugal_gravity_distance(rpm0, a)["radius_m"]
        rpm1 = equations.compute_centrifugal_gravity_rpm(a, r1)["rpm"]
        self.assertAlmostEqual(r1, r0, places=6)
        self.assertAlmostEqual(rpm1, rpm0, places=6)


class StarLuminosityTest(unittest.TestCase):
    """equations.compute_star_luminosity (opt 41)."""

    def test_solar_reference(self):
        # R = 1 R☉, teff = 5778 K → L ≈ 1.0 Lsun (5778 is the reference temp).
        out = equations.compute_star_luminosity(1.0, 5778.0)
        self.assertAlmostEqual(out["luminosity"], 1.0, places=9)

    def test_radius_and_temp_scaling(self):
        # L = R² × (T/5778)⁴.
        out = equations.compute_star_luminosity(2.0, 11556.0)  # 2 R☉, 2× temp
        self.assertAlmostEqual(out["luminosity"], 4.0 * 16.0, places=6)


class FormatTravelTimeTest(unittest.TestCase):
    """shared._format_travel_time — boundary cases."""

    def test_zero(self):
        self.assertEqual(shared._format_travel_time(0.0), "0 Seconds")

    def test_sub_minute_shows_seconds(self):
        # 0.0001 h = 0.36 s — under a minute, so seconds are shown.
        self.assertEqual(shared._format_travel_time(0.0001), "0.36 Seconds")

    def test_exactly_one_year_singular(self):
        self.assertEqual(shared._format_travel_time(shared.HOURS_PER_YEAR), "1 Year")

    def test_two_years_plural(self):
        self.assertEqual(shared._format_travel_time(2.0 * shared.HOURS_PER_YEAR), "2 Years")

    def test_mixed_days_and_hours(self):
        self.assertEqual(shared._format_travel_time(25.0), "1 Day, 1 Hour")

    def test_hours_and_minutes(self):
        self.assertEqual(shared._format_travel_time(1.5), "1 Hour, 30 Minutes")

    def test_minutes_only_no_trailing_seconds(self):
        # 5 minutes exactly — seconds should NOT appear (parts non-empty and
        # total_hours >= 1 minute).
        self.assertEqual(shared._format_travel_time(5.0 / 60.0), "5 Minutes")


if __name__ == "__main__":
    unittest.main()
