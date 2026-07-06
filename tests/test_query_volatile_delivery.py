# tests/test_query_volatile_delivery.py — Phase AD (C5) volatile-delivery query.py contract.
#
# Offline subprocess tests mirroring tests/test_query_megastructure.py: happy-path JSON shape,
# core parity (subprocess == in-process), and the self-validating exit-code matrix
# (curated {"error"} -> exit 1; argparse -> exit 2).

import json
import os
import pathlib
import subprocess
import sys
import unittest

import core.volatile_delivery as volatile_delivery

from tests._queryharness import make_env, run_query, run_query_inproc

_REPO = pathlib.Path(__file__).resolve().parent.parent
_ENV = make_env("phase_ad_volatile_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class VolatileDeliveryQueryTest(unittest.TestCase):
    def test_happy_and_parity(self):
        rc, d, _ = _run("volatile-delivery", "--body-mass-kg", "1e15", "--volatile-fraction", "0.5",
                        "--impact-velocity-kms", "20", "--target-atmosphere-mass-kg", "5.15e18")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["delivered_volatile_mass_kg"], 5e14, places=0)
        self.assertAlmostEqual(d["impact_energy_j"], 2e23, delta=1e18)
        self.assertAlmostEqual(d["bodies_needed"], 10300, delta=1)
        ref = volatile_delivery.compute_volatile_delivery(
            body_mass_kg=1e15, volatile_fraction=0.5, impact_velocity_kms=20,
            target_atmosphere_mass_kg=5.15e18)
        self.assertEqual(d, ref)

    def test_redirect_mass_ratio(self):
        rc, d, _ = _run("volatile-delivery", "--body-mass-kg", "1e15",
                        "--delta-v-kms", "1", "--fuel", "fusion-dt")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["redirect_mass_ratio"], 1.0001, delta=0.001)
        self.assertIsNone(d["impact_energy_j"])
        self.assertIsNone(d["bodies_needed"])

    def test_exit1_curated_errors(self):
        for args in (["volatile-delivery", "--body-mass-kg", "0"],                        # M ≤ 0
                     ["volatile-delivery", "--body-mass-kg", "1e15",
                      "--volatile-fraction", "1.5"],                                       # fraction > 1
                     ["volatile-delivery", "--body-mass-kg", "1e15", "--delta-v-kms", "1"],  # Δv no exhaust
                     ["volatile-delivery", "--body-mass-kg", "1e15", "--fuel", "fusion-dt"],  # fuel no Δv
                     ["volatile-delivery", "--body-mass-kg", "1e15",
                      "--target-atmosphere-mass-kg", "0"]):                                # target ≤ 0
            rc, d, _ = run_query_inproc(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_exit2_argparse(self):
        for args in (["volatile-delivery", "--body-mass-kg", "1e15",
                      "--delta-v-kms", "1", "--fuel", "bogus"],                            # bad --fuel choice
                     ["volatile-delivery", "--volatile-fraction", "0.5"],                  # missing required M
                     ["volatile-delivery", "--body-mass-kg", "abc"]):                      # non-numeric
            rc, _, err = run_query_inproc(*args)
            self.assertEqual(rc, 2, args)
            self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
