# tests/test_query_megastructure.py — Phase Z megastructure query.py contract.
#
# Offline subprocess tests mirroring tests/test_query_thermal.py: happy-path JSON shape,
# core parity (subprocess == in-process), and the self-validating exit-code matrix
# (curated {"error"} -> exit 1; argparse -> exit 2). The dyson-collector --star path is
# network-bound and not exercised here (offline).

import json
import os
import pathlib
import subprocess
import sys
import unittest

import core.megastructure as megastructure

from tests._queryharness import make_env, run_query, run_query_inproc

_REPO = pathlib.Path(__file__).resolve().parent.parent
_ENV = make_env("phase_z_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class SpinStressQueryTest(unittest.TestCase):
    def test_happy_and_parity(self):
        rc, d, _ = _run("spin-stress", "--material", "structural-steel",
                        "--target-gravity-g", "1", "--safety-factor", "1")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["max_radius_km"], 5.196, delta=0.02)
        ref = megastructure.compute_spin_stress(material="structural-steel",
                                                target_gravity_g=1, safety_factor=1)
        self.assertAlmostEqual(d["max_tangential_velocity_ms"], ref["max_tangential_velocity_ms"], places=6)

    def test_exit1_curated(self):
        for args in (["spin-stress", "--material", "structural-steel"],                     # no solve form
                     ["spin-stress", "--material", "structural-steel", "--safety-factor", "0.5",
                      "--target-gravity-g", "1"],                                            # SF<1
                     ["spin-stress", "--material", "structural-steel", "--density-kgm3", "1000",
                      "--target-gravity-g", "1"]):                                           # material+explicit
            rc, d, _ = run_query_inproc(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_exit2_argparse(self):
        for args in (["spin-stress", "--material", "steelx", "--target-gravity-g", "1"],     # bad choice
                     ["spin-stress", "--material", "structural-steel", "--target-gravity-g", "x"]):  # non-numeric
            rc, _, err = run_query_inproc(*args)
            self.assertEqual(rc, 2, args)
            self.assertTrue(err)


class TetherTaperQueryTest(unittest.TestCase):
    def test_happy_and_parity(self):
        rc, d, _ = _run("tether-taper", "--material", "cnt-theoretical", "--body", "earth",
                        "--safety-factor", "1")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["taper_ratio"], 1.923, delta=0.02)
        self.assertTrue(d["feasible"])
        ref = megastructure.compute_tether_taper(material="cnt-theoretical", body="earth", safety_factor=1)
        self.assertAlmostEqual(d["taper_ratio"], ref["taper_ratio"], places=6)

    def test_steel_infeasible_is_exit0(self):
        # an infeasible (overflow) taper is a normal result, not an error
        rc, d, _ = _run("tether-taper", "--material", "structural-steel", "--body", "earth")
        self.assertEqual(rc, 0)
        self.assertIsNone(d["taper_ratio"])
        self.assertFalse(d["feasible"])

    def test_exit1_curated(self):
        for args in (["tether-taper", "--material", "kevlar"],                               # no body
                     ["tether-taper", "--material", "kevlar", "--body", "earth",
                      "--surface-gravity-ms2", "9.81"]):                                      # body+explicit
            rc, d, _ = run_query_inproc(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_exit2_argparse(self):
        rc, _, err = _run("tether-taper", "--material", "kevlar", "--body", "pluto")
        self.assertEqual(rc, 2)
        self.assertTrue(err)


class DysonCollectorQueryTest(unittest.TestCase):
    def test_happy_and_parity(self):
        rc, d, _ = _run("dyson-collector", "--luminosity-lsun", "1", "--fraction", "0.01",
                        "--orbit-au", "1")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["intercepted_power_w"], 3.828e24, delta=1e22)
        ref = megastructure.compute_dyson_collector(luminosity_lsun=1, fraction=0.01, orbit_au=1)
        self.assertAlmostEqual(d["collector_area_m2"], ref["collector_area_m2"], places=3)

    def test_exit1_curated(self):
        rc, d, _ = _run("dyson-collector", "--luminosity-lsun", "1", "--fraction", "1.5",
                        "--orbit-au", "1")
        self.assertEqual(rc, 1)
        self.assertIn("error", d)

    def test_exit2_argparse(self):
        for args in (["dyson-collector", "--fraction", "0.01", "--orbit-au", "1"],            # missing L/star mutex
                     ["dyson-collector", "--luminosity-lsun", "1", "--star", "Sol",
                      "--fraction", "0.01", "--orbit-au", "1"],                               # both mutex
                     ["dyson-collector", "--luminosity-lsun", "1", "--orbit-au", "1"]):       # missing required --fraction
            rc, _, err = run_query_inproc(*args)
            self.assertEqual(rc, 2, args)
            self.assertTrue(err)


class OrbitalRingQueryTest(unittest.TestCase):
    def test_happy_and_parity(self):
        rc, d, _ = _run("orbital-ring", "--body", "earth", "--altitude-km", "300",
                        "--ring-mass-per-length-kgm", "100")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["orbital_velocity_kms"], 7.73, delta=0.02)
        self.assertAlmostEqual(d["rotor_velocity_kms"], 10.93, delta=0.02)
        ref = megastructure.compute_orbital_ring(body="earth", altitude_km=300,
                                                 ring_mass_per_length_kgm=100)
        self.assertEqual(d, ref)

    def test_exit1_curated_errors(self):
        for args in (["orbital-ring", "--altitude-km", "300",
                      "--ring-mass-per-length-kgm", "100"],                       # no body anchor
                     ["orbital-ring", "--body", "earth", "--surface-gravity-ms2", "9.81",
                      "--altitude-km", "300", "--ring-mass-per-length-kgm", "100"],  # body + explicit
                     ["orbital-ring", "--surface-gravity-ms2", "9.81",
                      "--altitude-km", "300", "--ring-mass-per-length-kgm", "100"],  # partial explicit
                     ["orbital-ring", "--body", "earth", "--altitude-km", "300",
                      "--ring-mass-per-length-kgm", "0"]):                        # ring λ ≤ 0
            rc, d, _ = run_query_inproc(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_exit2_argparse(self):
        for args in (["orbital-ring", "--body", "bogus", "--altitude-km", "300",
                      "--ring-mass-per-length-kgm", "100"],                       # bad --body choice
                     ["orbital-ring", "--body", "earth", "--ring-mass-per-length-kgm", "100"],  # missing --altitude
                     ["orbital-ring", "--body", "earth", "--altitude-km", "300"],  # missing --ring-mass
                     ["orbital-ring", "--body", "earth", "--altitude-km", "abc",
                      "--ring-mass-per-length-kgm", "100"]):                      # non-numeric
            rc, _, err = run_query_inproc(*args)
            self.assertEqual(rc, 2, args)
            self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
