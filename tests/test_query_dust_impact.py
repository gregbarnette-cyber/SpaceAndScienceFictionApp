# tests/test_query_dust_impact.py — Phase AD (C3) dust-impact query.py contract.
#
# Offline subprocess tests mirroring tests/test_query_propulsion.py: happy-path JSON shape,
# core parity (subprocess == in-process), and the self-validating exit-code matrix
# (curated {"error"} -> exit 1; argparse -> exit 2).

import json
import os
import pathlib
import subprocess
import sys
import unittest

import core.dust_impact as dust_impact

from tests._queryharness import make_env, run_query, run_query_inproc

_REPO = pathlib.Path(__file__).resolve().parent.parent
_ENV = make_env("phase_ad_dust_impact_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class DustImpactQueryTest(unittest.TestCase):
    def test_happy_and_parity(self):
        rc, d, _ = _run("dust-impact", "--grain-radius-um", "1",
                        "--grain-density-kgm3", "1000", "--beta", "0.1")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["impact_energy_j"], 1.88, delta=0.02)
        self.assertFalse(d["relativistic"])
        self.assertIn("penetration_handoff_note", d)
        ref = dust_impact.compute_dust_impact(grain_radius_um=1, grain_density_kgm3=1000, beta=0.1)
        self.assertEqual(d, ref)

    def test_relativistic_and_cumulative(self):
        rc, d, _ = _run("dust-impact", "--grain-radius-um", "1", "--grain-density-kgm3", "1000",
                        "--beta", "0.2", "--dust-density-m3", "1e-6",
                        "--frontal-area-m2", "100", "--path-length-ly", "4")
        self.assertEqual(rc, 0)
        self.assertTrue(d["relativistic"])
        self.assertIsNotNone(d["impacts_total"])
        self.assertIsNotNone(d["energy_fluence_j_m2"])

    def test_exit1_curated_errors(self):
        for args in (["dust-impact", "--beta", "0.1"],                              # no grain anchor
                     ["dust-impact", "--grain-radius-um", "1", "--beta", "0.1"],    # radius w/o density
                     ["dust-impact", "--grain-radius-um", "1",
                      "--grain-density-kgm3", "1000"],                              # no velocity
                     ["dust-impact", "--grain-radius-um", "1",
                      "--grain-density-kgm3", "1000", "--beta", "1.0"],             # β=1
                     ["dust-impact", "--grain-radius-um", "1", "--grain-density-kgm3", "1000",
                      "--beta", "0.1", "--frontal-area-m2", "100"]):                # partial cumulative
            rc, d, _ = run_query_inproc(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_exit2_argparse(self):
        for args in (["dust-impact", "--grain-radius-um", "1", "--grain-mass-kg", "1",
                      "--beta", "0.1"],                                             # grain mutex
                     ["dust-impact", "--grain-radius-um", "1", "--grain-density-kgm3", "1000",
                      "--velocity-kms", "1000", "--beta", "0.1"],                   # velocity mutex
                     ["dust-impact", "--grain-radius-um", "abc",
                      "--grain-density-kgm3", "1000", "--beta", "0.1"]):            # non-numeric
            rc, _, err = run_query_inproc(*args)
            self.assertEqual(rc, 2, args)
            self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
