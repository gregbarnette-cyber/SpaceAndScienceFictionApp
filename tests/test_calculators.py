# tests/test_calculators.py — offline coverage for core/calculators.py.
#
# Covers velocity conversions, distance-traveled, the three brachistochrone
# profiles (compute_distance_at_acceleration, compute_travel_time_system_au/lm),
# the RA/DEC sexagesimal formatting + 3D Cartesian distance math, and the
# Sol/Sun origin special case. No network, no Qt, no DB.

import math
import unittest

from core import calculators as calc

HJY = 8765.8128  # hours in a Julian year (the ly/hr ↔ ×c constant)


class VelocityConversionTest(unittest.TestCase):

    def test_ly_hr_to_times_c(self):
        out = calc.compute_ly_hr_to_times_c(0.01)
        self.assertAlmostEqual(out["times_c"], 0.01 * HJY, places=9)

    def test_times_c_to_ly_hr(self):
        out = calc.compute_speed_of_light_to_ly_hr(100.0)
        self.assertAlmostEqual(out["ly_hr"], 100.0 / HJY, places=12)

    def test_round_trip(self):
        ly_hr = 0.0123
        c = calc.compute_ly_hr_to_times_c(ly_hr)["times_c"]
        back = calc.compute_speed_of_light_to_ly_hr(c)["ly_hr"]
        self.assertAlmostEqual(back, ly_hr, places=12)

    def test_distance_traveled_ly_hr(self):
        out = calc.compute_distance_traveled_ly_hr(0.5, 10.0)
        self.assertAlmostEqual(out["distance_ly"], 5.0)

    def test_distance_traveled_times_c(self):
        out = calc.compute_distance_traveled_times_c(HJY, 2.0)  # HJY ×c == 1 ly/hr
        self.assertAlmostEqual(out["ly_hr"], 1.0, places=9)
        self.assertAlmostEqual(out["distance_ly"], 2.0, places=9)


class TravelTimeLyTest(unittest.TestCase):

    def test_time_to_travel(self):
        out = calc.compute_travel_time_ly_hr(10.0, 0.5)  # 10 ly at 0.5 ly/hr
        self.assertAlmostEqual(out["total_hours"], 20.0)
        self.assertAlmostEqual(out["times_c"], 0.5 * HJY, places=6)


class RaDecFormattingTest(unittest.TestCase):
    """_fmt_ra / _fmt_dec degrees → sexagesimal, plus a manual round-trip."""

    def test_fmt_ra_zero(self):
        self.assertEqual(calc._fmt_ra(0.0), "00 00 00.0000")

    def test_fmt_ra_known(self):
        # 180° / 15 = 12h exactly.
        self.assertEqual(calc._fmt_ra(180.0), "12 00 00.0000")
        # 15° = 1h.
        self.assertEqual(calc._fmt_ra(15.0), "01 00 00.0000")

    def test_fmt_dec_sign_and_value(self):
        self.assertEqual(calc._fmt_dec(0.0), "+00 00 00.000")
        self.assertEqual(calc._fmt_dec(45.5), "+45 30 00.000")
        self.assertEqual(calc._fmt_dec(-45.5), "-45 30 00.000")

    def test_ra_round_trip(self):
        # Format a degree value to HMS, then parse it back the way opt 19 does.
        for deg in (12.3456, 87.5, 200.125, 359.999):
            hms = calc._fmt_ra(deg)
            h, m, s = (float(x) for x in hms.split())
            back = (h + m / 60.0 + s / 3600.0) * 15.0
            self.assertAlmostEqual(back, deg, places=4)

    def test_dec_round_trip(self):
        for deg in (-62.6761, -0.5, 0.0, 41.2319, 89.9):
            dms = calc._fmt_dec(deg)
            sign = -1.0 if dms.startswith("-") else 1.0
            d, m, s = (float(x) for x in dms.lstrip("+-").split())
            back = sign * (d + m / 60.0 + s / 3600.0)
            self.assertAlmostEqual(back, deg, places=3)


class CartesianDistanceTest(unittest.TestCase):
    """_to_cartesian + 3D Euclidean distance."""

    def test_origin(self):
        self.assertEqual(calc._to_cartesian(123.0, -45.0, 0.0), (0.0, 0.0, 0.0))

    def test_radial_distance_preserved(self):
        # A point's distance from the origin equals its input ly regardless of angle.
        x, y, z = calc._to_cartesian(217.0, -62.0, 4.25)
        self.assertAlmostEqual(math.sqrt(x*x + y*y + z*z), 4.25, places=9)

    def test_two_synthetic_stars(self):
        # Star A on the +x axis at 3 ly, star B on the +y axis at 4 ly.
        ax, ay, az = calc._to_cartesian(0.0, 0.0, 3.0)    # (3, 0, 0)
        bx, by, bz = calc._to_cartesian(90.0, 0.0, 4.0)   # (~0, 4, 0)
        dist = math.sqrt((bx-ax)**2 + (by-ay)**2 + (bz-az)**2)
        self.assertAlmostEqual(dist, 5.0, places=6)       # 3-4-5 triangle


class SolSpecialCaseTest(unittest.TestCase):
    """compute_lookup_star_for_distance Sol/Sun origin (no SIMBAD query)."""

    def test_sol(self):
        out = calc.compute_lookup_star_for_distance("Sol")
        self.assertEqual((out["ra_deg"], out["dec_deg"], out["ly"]), (0.0, 0.0, 0.0))
        self.assertNotIn("error", out)

    def test_sun_case_insensitive(self):
        for name in ("sun", "SUN", "  Sol  "):
            out = calc.compute_lookup_star_for_distance(name)
            self.assertEqual(out["ly"], 0.0, msg=name)

    def test_sol_carries_spectral_type(self):
        """The additive sp_type key (O8 star-chart dot colours) — G2V for Sol."""
        out = calc.compute_lookup_star_for_distance("Sol")
        self.assertEqual(out["sp_type"], "G2V")


class BrachistochroneProfilesTest(unittest.TestCase):
    """_brachistochrone_profiles via compute_travel_time_system_au/lm."""

    G = 9.80665
    C = 299_792_458.0
    M_PER_AU = 149_597_870_700.0
    M_PER_LM = 299_792_458.0 * 60.0

    def test_profile1_closed_form(self):
        # Profile 1: t = 2·√(d/a). Use 1 g over 1 AU.
        a = 1.0 * self.G
        d = 1.0 * self.M_PER_AU
        out = calc.compute_travel_time_system_au(1.0, 1.0)
        p1 = out["profiles"][0]
        expected_hours = (2.0 * math.sqrt(d / a)) / 3600.0
        self.assertAlmostEqual(p1["hours"], expected_hours, places=6)
        self.assertEqual(p1["max_vel"], "N/A")

    def test_profile2_closed_form(self):
        # Profile 2: t = √(16d/(3a)).
        a = 1.0 * self.G
        d = 1.0 * self.M_PER_AU
        out = calc.compute_travel_time_system_au(1.0, 1.0)
        p2 = out["profiles"][1]
        expected_hours = math.sqrt((16.0 * d) / (3.0 * a)) / 3600.0
        self.assertAlmostEqual(p2["hours"], expected_hours, places=6)
        self.assertEqual(p2["max_vel"], "N/A")

    def test_profile3_cap_reached_on_long_haul(self):
        # 100,000 AU at 1 g easily exceeds the 3% c cap → Profile 3 'Y'.
        out = calc.compute_travel_time_system_au(1.0, 100_000.0)
        p3 = out["profiles"][2]
        self.assertEqual(p3["max_vel"], "Y")
        self.assertNotIn("cap not reached", p3["label"])

    def test_profile3_cap_not_reached_on_short_hop(self):
        # 0.001 AU at 1 g never reaches 3% c → Profile 3 'N' and falls back to
        # the Profile 1 time.
        out = calc.compute_travel_time_system_au(1.0, 0.001)
        p1, p3 = out["profiles"][0], out["profiles"][2]
        self.assertEqual(p3["max_vel"], "N")
        self.assertIn("cap not reached", p3["label"])
        self.assertAlmostEqual(p3["hours"], p1["hours"], places=9)

    def test_au_and_lm_agree_for_same_distance(self):
        # 1 AU expressed in light-minutes must give identical profiles.
        au_out = calc.compute_travel_time_system_au(1.0, 1.0)
        lm = self.M_PER_AU / self.M_PER_LM
        lm_out = calc.compute_travel_time_system_lm(1.0, lm)
        for pa, pl in zip(au_out["profiles"], lm_out["profiles"]):
            self.assertAlmostEqual(pa["hours"], pl["hours"], places=6)
        self.assertAlmostEqual(lm_out["distance_au"], 1.0, places=9)


class DistanceAtAccelerationTest(unittest.TestCase):
    """compute_distance_at_acceleration (opt 24) — distance given time."""

    G = 9.80665
    C = 299_792_458.0
    M_PER_AU = 149_597_870_700.0

    def test_profile1_continuous(self):
        # Profile 1 here is continuous accel for the whole window: d = ½·a·t².
        accel_g, hours = 1.0, 10.0
        out = calc.compute_distance_at_acceleration(accel_g, hours)
        a = accel_g * self.G
        t = hours * 3600.0
        expected_au = (0.5 * a * t ** 2) / self.M_PER_AU
        self.assertAlmostEqual(out["profiles"][0]["distance_au"], expected_au, places=6)

    def test_profile2_three_sixteenths(self):
        # Profile 2: d = 3·a·t²/16.
        accel_g, hours = 1.0, 10.0
        out = calc.compute_distance_at_acceleration(accel_g, hours)
        a = accel_g * self.G
        t = hours * 3600.0
        expected_au = (3.0 * a * t ** 2 / 16.0) / self.M_PER_AU
        self.assertAlmostEqual(out["profiles"][1]["distance_au"], expected_au, places=6)

    def test_profile3_cap_not_reached_matches_profile1(self):
        # Short window at low g: 3% c never reached → Profile 3 == ½·a·t² and 'N'.
        out = calc.compute_distance_at_acceleration(0.001, 0.01)
        p1, p3 = out["profiles"][0], out["profiles"][2]
        self.assertEqual(p3["max_vel"], "N")
        self.assertAlmostEqual(p3["distance_au"], p1["distance_au"], places=9)


if __name__ == "__main__":
    unittest.main()
