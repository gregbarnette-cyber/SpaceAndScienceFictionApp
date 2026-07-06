# tests/test_query_active_shield.py — Phase AD (C8) active-shield query.py contract.
#
# Offline subprocess tests mirroring tests/test_query_thermal.py: happy-path JSON,
# core parity, and the self-validating exit-code matrix (exit 1 curated / exit 2 argparse).

import json
import os
import pathlib
import subprocess
import sys
import unittest

import core.active_shield as ashield

from tests._queryharness import make_env, run_query, run_query_inproc

_REPO = pathlib.Path(__file__).resolve().parent.parent
_ENV = make_env("phase_ad_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class ActiveShieldQueryTest(unittest.TestCase):
    def test_happy_and_parity(self):
        rc, d, _ = _run("active-shield", "--shield-radius-m", "6.371e6",
                        "--magnetic-moment-am2", "8e22")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["rigidity_cutoff_gv"], 14.8, delta=0.3)
        ref = ashield.compute_active_shield(shield_radius_m=6.371e6, magnetic_moment_am2=8e22)
        self.assertAlmostEqual(d["rigidity_cutoff_gv"], ref["rigidity_cutoff_gv"], places=6)

    def test_deflected_fraction(self):
        rc, d, _ = _run("active-shield", "--shield-radius-m", "10",
                        "--field-tesla", "5", "--field-radius-m", "10",
                        "--spectrum-characteristic-rigidity-gv", "1.0")
        self.assertEqual(rc, 0)
        self.assertGreater(d["deflected_fraction"], 0.0)
        self.assertLess(d["deflected_fraction"], 1.0)

    def test_exit1_curated(self):
        for args in (
            ["active-shield", "--shield-radius-m", "10"],                              # no field source
            ["active-shield", "--shield-radius-m", "10", "--magnetic-moment-am2", "1e10",
             "--coil-current-a", "1", "--coil-radius-m", "1"],                         # two sources
            ["active-shield", "--shield-radius-m", "10", "--coil-current-a", "1"],     # partial coil
            ["active-shield", "--shield-radius-m", "10", "--magnetic-moment-am2", "-1"],  # neg moment
            ["active-shield", "--shield-radius-m", "0", "--magnetic-moment-am2", "1e10"],  # radius ≤0
        ):
            rc, d, _ = run_query_inproc(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_exit2_argparse(self):
        for args in (
            ["active-shield", "--magnetic-moment-am2", "1e10"],                         # missing required radius
            ["active-shield", "--shield-radius-m", "abc", "--magnetic-moment-am2", "1e10"],  # non-numeric
        ):
            rc, _, err = run_query_inproc(*args)
            self.assertEqual(rc, 2, args)
            self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
