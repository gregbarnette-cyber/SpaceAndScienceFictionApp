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

_REPO = pathlib.Path(__file__).resolve().parent.parent
_ENV = {"SPACE_APP_DB": "/tmp/phase_z_throwaway.db", "PATH": os.environ.get("PATH", "")}


def _run(*cmd_args):
    proc = subprocess.run(
        [sys.executable, str(_REPO / "query.py"), *cmd_args],
        capture_output=True, text=True, cwd=str(_REPO), env=_ENV,
    )
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        payload = None
    return proc.returncode, payload, proc.stderr


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
            rc, d, _ = _run(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_exit2_argparse(self):
        for args in (["spin-stress", "--material", "steelx", "--target-gravity-g", "1"],     # bad choice
                     ["spin-stress", "--material", "structural-steel", "--target-gravity-g", "x"]):  # non-numeric
            rc, _, err = _run(*args)
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
            rc, d, _ = _run(*args)
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
            rc, _, err = _run(*args)
            self.assertEqual(rc, 2, args)
            self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
