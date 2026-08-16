# tests/test_kinematics.py — CR-7 kinematics / population classification (core, offline).
#
# Offline tests drive core.kinematics.classify_population with U/V/W directly (pure-math,
# self-validating). One live-gated anchor exercises the --star SIMBAD→Hypatia path
# (SPACE_APP_RUN_LIVE=1 + Hypatia reachable), mirroring tests/test_hypatia_live.py.

import math
import unittest

import core.kinematics as kinematics
from tests._netcheck import hypatia_reachable, live_enabled

_ONLINE = live_enabled() and hypatia_reachable()


class ClassifyPopulationTest(unittest.TestCase):
    def test_sun_is_thin_disk(self):
        # Heliocentric U/V/W ≈ 0 → LSR = the solar motion → clearly thin, high probability.
        d = kinematics.classify_population(u=0.0, v=0.0, w=0.0)
        self.assertNotIn("error", d)
        self.assertEqual(d["population"], "thin")
        self.assertGreater(d["membership_prob"], 0.9)

    def test_lsr_correction_and_toomre_math(self):
        # Sun: total = |solar motion| = √(11.1²+12.24²+7.25²); Toomre = √((0+11.1)²+(0+7.25)²).
        d = kinematics.classify_population(u=0.0, v=0.0, w=0.0)
        self.assertAlmostEqual(d["total_velocity_kms"],
                               math.sqrt(11.1 ** 2 + 12.24 ** 2 + 7.25 ** 2), places=6)
        self.assertAlmostEqual(d["toomre_velocity_kms"],
                               math.hypot(11.1, 7.25), places=6)

    def test_thick_disk_anchor(self):
        # A moderate-lag, moderate-dispersion star (total ~108 km/s) → thick.
        d = kinematics.classify_population(u=-60.0, v=-90.0, w=50.0)
        self.assertEqual(d["population"], "thick")

    def test_halo_anchor(self):
        # Large retrograde V + high U/W (total ~296 km/s) → halo.
        d = kinematics.classify_population(u=-150.0, v=-250.0, w=100.0)
        self.assertEqual(d["population"], "halo")
        self.assertGreater(d["membership_prob"], 0.9)

    def test_probabilities_normalise_and_argmax(self):
        d = kinematics.classify_population(u=-60.0, v=-90.0, w=50.0)
        probs = d["probabilities"]
        self.assertEqual(set(probs), {"thin", "thick", "halo"})
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=9)
        self.assertEqual(d["population"], max(probs, key=probs.get))
        self.assertAlmostEqual(d["membership_prob"], probs[d["population"]], places=12)

    def test_pinned_output_keys_present(self):
        d = kinematics.classify_population(u=10.0, v=-20.0, w=5.0)
        for k in ("star", "u_vel_kms", "v_vel_kms", "w_vel_kms",
                  "toomre_velocity_kms", "population", "membership_prob"):
            self.assertIn(k, d)
        self.assertIn(d["population"], ("thin", "thick", "halo"))

    def test_explicit_uvw_wins_over_star_no_network(self):
        # Both given → uses U/V/W (no network); star name is echoed through.
        d = kinematics.classify_population(u=0.0, v=0.0, w=0.0, star="Whatever")
        self.assertEqual(d["population"], "thin")
        self.assertEqual(d["star"], "Whatever")

    def test_missing_all_inputs_errors(self):
        d = kinematics.classify_population()
        self.assertIn("error", d)

    def test_partial_uvw_errors(self):
        # Only two of three components → error (not silently dropped).
        d = kinematics.classify_population(u=10.0, v=20.0)
        self.assertIn("error", d)

    def test_partial_uvw_with_star_errors_not_silently_dropped(self):
        # Partial explicit velocities + --star must ERROR, never silently discard the supplied
        # numbers and fall back to the catalogue lookup (no network — errors before resolving).
        d = kinematics.classify_population(u=10.0, v=-20.0, star="Whatever")
        self.assertIn("error", d)

    def test_non_numeric_uvw_errors(self):
        d = kinematics.classify_population(u="x", v="y", w="z")
        self.assertIn("error", d)


@unittest.skipUnless(_ONLINE, "Hypatia Catalog not reachable / SPACE_APP_RUN_LIVE unset")
class ClassifyPopulationLiveTest(unittest.TestCase):
    def test_star_path_returns_valid_verdict(self):
        # HD 122563 is a textbook metal-poor halo star; if Hypatia carries its U/V/W the
        # verdict should be halo/thick (not thin). Skip gracefully if the catalog lacks it.
        d = kinematics.classify_population(star="HD 122563")
        if "error" in d:
            self.skipTest(f"no U/V/W for HD 122563: {d['error']}")
        for k in ("star", "u_vel_kms", "v_vel_kms", "w_vel_kms",
                  "toomre_velocity_kms", "population", "membership_prob"):
            self.assertIn(k, d)
        self.assertIn(d["population"], ("thick", "halo"))


if __name__ == "__main__":
    unittest.main()
