# tests/test_query_propulsion.py — Phase Y STL-energetics query.py contract.
#
# Offline subprocess tests mirroring tests/test_query_thermal.py: happy-path JSON shape,
# core parity (subprocess == in-process), and the self-validating exit-code matrix
# (curated {"error"} -> exit 1; argparse -> exit 2).

import json
import math
import os
import pathlib
import subprocess
import sys
import unittest

import core.propulsion as propulsion
from core.equations import _C_MS

_REPO = pathlib.Path(__file__).resolve().parent.parent
_ENV = {"SPACE_APP_DB": "/tmp/phase_y_throwaway.db", "PATH": os.environ.get("PATH", "")}
_C_KMS = _C_MS / 1000.0


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


class RocketEquationQueryTest(unittest.TestCase):
    def test_classical_happy_and_parity(self):
        rc, d, _ = _run("rocket-equation", "--delta-v-kms", "30", "--exhaust-velocity-kms", "30")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["mass_ratio"], math.e, places=4)
        self.assertAlmostEqual(d["propellant_fraction"], 1 - 1 / math.e, places=4)
        ref = propulsion.compute_rocket_equation(delta_v_kms=30, exhaust_velocity_kms=30)
        self.assertAlmostEqual(d["mass_ratio"], ref["mass_ratio"], places=9)

    def test_fusion_rendezvous(self):
        rc, d, _ = _run("rocket-equation", "--beta", "0.1", "--fuel", "fusion-dt",
                        "--legs", "rendezvous")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["mass_ratio"], 803.5, delta=10)
        self.assertAlmostEqual(d["mass_ratio_single_burn"], 28.35, delta=0.3)
        self.assertTrue(d["relativistic"])

    def test_exit1_curated_errors(self):
        for args in (["rocket-equation", "--delta-v-kms", "30"],                       # one anchor
                     ["rocket-equation", "--beta", "1.0", "--exhaust-velocity-kms", "30"],  # β=1
                     ["rocket-equation", "--delta-v-kms", "30", "--mass-ratio", "0.5"],     # MR<1
                     ["rocket-equation", "--delta-v-kms", "30", "--relativistic",
                      "--exhaust-velocity-kms", "30"]):                                # rel+Δv
            rc, d, _ = _run(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_exit2_argparse(self):
        for args in (["rocket-equation", "--delta-v-kms", "30", "--fuel", "nope"],       # bad choice
                     ["rocket-equation", "--delta-v-kms", "30", "--exhaust-velocity-kms",
                      "30", "--legs", "orbit"],                                          # bad legs
                     ["rocket-equation", "--beta", "abc", "--exhaust-velocity-kms", "30"]):  # non-numeric
            rc, _, err = _run(*args)
            self.assertEqual(rc, 2, args)
            self.assertTrue(err)


class BeamSailQueryTest(unittest.TestCase):
    def test_happy_and_parity(self):
        rc, d, _ = _run("beam-sail", "--beam-power-w", "100e9", "--reflectivity", "1.0",
                        "--sail-mass-kg", "1000")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["thrust_n"], 2 * 100e9 / _C_MS, places=3)
        ref = propulsion.compute_beam_sail(beam_power_w=100e9, reflectivity=1.0, sail_mass_kg=1000)
        self.assertAlmostEqual(d["thrust_n"], ref["thrust_n"], places=9)

    def test_exit1_curated_errors(self):
        for args in (["beam-sail", "--beam-power-w", "0", "--sail-mass-kg", "10"],       # power=0
                     ["beam-sail", "--beam-power-w", "1e9", "--reflectivity", "1.5",
                      "--sail-mass-kg", "10"],                                           # reflectivity
                     ["beam-sail", "--beam-power-w", "1e9"]):                            # no mass source
            rc, d, _ = _run(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_exit2_argparse(self):
        # missing required --beam-power-w; mutex accel group; non-numeric
        for args in (["beam-sail", "--sail-mass-kg", "10"],
                     ["beam-sail", "--beam-power-w", "1e9", "--sail-mass-kg", "10",
                      "--accel-distance-au", "1", "--accel-time-days", "1"],
                     ["beam-sail", "--beam-power-w", "abc", "--sail-mass-kg", "10"]):
            rc, _, err = _run(*args)
            self.assertEqual(rc, 2, args)
            self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
