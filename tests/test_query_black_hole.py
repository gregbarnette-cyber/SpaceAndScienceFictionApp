# tests/test_query_black_hole.py — Phase AI (Group O) query.py contract.
#
# Offline subprocess tests mirroring tests/test_query_active_shield.py: happy-path JSON,
# core parity, and the self-validating exit-code matrix (exit 1 curated / exit 2 argparse).

import unittest

import core.black_hole as black_hole

from tests._queryharness import make_env, run_query, run_query_inproc

_ENV = make_env("phase_ai_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class BlackHoleQueryTest(unittest.TestCase):
    def test_all_happy_and_parity(self):
        rc, d, _ = _run("schwarzschild-radius", "--mass-msun", "1")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["schwarzschild_radius_km"], 2.953, delta=0.002)
        ref = black_hole.compute_schwarzschild_radius(mass_msun=1)
        self.assertAlmostEqual(d["schwarzschild_radius_m"], ref["schwarzschild_radius_m"], places=6)

        self.assertAlmostEqual(_run("hawking-temperature", "--mass-msun", "1")[1]["hawking_temperature_k"], 6.17e-8, delta=1e-10)
        self.assertAlmostEqual(_run("black-hole-evaporation", "--mass-msun", "1")[1]["lifetime_yr"], 2.1e67, delta=1e65)
        self.assertAlmostEqual(_run("bekenstein-hawking-entropy", "--mass-msun", "1")[1]["entropy_over_kb"], 1.05e77, delta=1e75)
        self.assertAlmostEqual(_run("isco", "--mass-msun", "1")[1]["binding_efficiency"], 0.0572, delta=1e-3)
        self.assertAlmostEqual(_run("isco", "--mass-msun", "1", "--spin", "1")[1]["binding_efficiency"], 0.4226, delta=1e-3)
        self.assertTrue(_run("kerr-horizon", "--mass-msun", "1", "--spin", "1")[1]["extremal"])
        self.assertAlmostEqual(_run("bh-tidal-force", "--mass-msun", "10")[1]["tidal_gees"], 1.89e7, delta=1e6)
        self.assertAlmostEqual(_run("eddington-luminosity", "--mass-msun", "1")[1]["eddington_luminosity_w"], 1.26e31, delta=1e29)
        self.assertAlmostEqual(_run("unruh-temperature", "--acceleration-ms2", "2.47e20")[1]["unruh_temperature_k"], 1.0, delta=0.01)
        self.assertAlmostEqual(_run("bekenstein-bound", "--radius-m", "0.1", "--mass-kg", "1")[1]["max_information_bits"], 2.58e42, delta=1e40)

    def test_object_preset(self):
        rc, d, _ = _run("schwarzschild-radius", "--object", "m87-star")
        self.assertEqual(rc, 0)
        self.assertEqual(d["object"], "M87*")

    def test_inverse_modes(self):
        self.assertAlmostEqual(_run("hawking-temperature", "--temperature-k", "2.725")[1]["mass_kg"], 4.5e22, delta=1e21)
        self.assertAlmostEqual(_run("black-hole-evaporation", "--lifetime-yr", "1.38e10")[1]["mass_kg"], 1.73e11, delta=2e9)
        self.assertAlmostEqual(_run("unruh-temperature", "--temperature-k", "1")[1]["acceleration_ms2"], 2.47e20, delta=1e18)

    def test_exit1_curated(self):
        for args in (
            ["schwarzschild-radius"],                                        # no mass
            ["schwarzschild-radius", "--mass-msun", "1", "--object", "sun"], # both
            ["hawking-temperature", "--mass-msun", "1", "--temperature-k", "1"],
            ["black-hole-evaporation"],                                      # no mass/lifetime
            ["bekenstein-hawking-entropy", "--mass-msun", "1", "--radius-m", "1"],
            ["isco", "--mass-msun", "1", "--spin", "1.5"],                   # spin out of range
            ["kerr-horizon", "--mass-msun", "1", "--spin", "2"],
            ["bh-tidal-force", "--mass-msun", "10", "--distance-m", "1e4", "--distance-rs", "1"],
            ["eddington-luminosity", "--mass-msun", "1", "--efficiency", "2"],
            ["unruh-temperature"],                                           # nothing
            ["bekenstein-bound", "--radius-m", "1"],                         # no energy/mass
        ):
            rc, d, _ = run_query_inproc(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_exit2_argparse(self):
        for args in (
            ["schwarzschild-radius", "--object", "nope"],                    # bad preset choice
            ["schwarzschild-radius", "--mass-msun", "abc"],                  # non-numeric
            ["bekenstein-bound", "--mass-kg", "1"],                          # missing required --radius-m
        ):
            rc, _, err = run_query_inproc(*args)
            self.assertEqual(rc, 2, args)
            self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
