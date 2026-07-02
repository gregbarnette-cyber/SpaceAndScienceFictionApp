# tests/test_query_spin.py — Phase W spin-comfort query.py contract.
#
# Offline subprocess tests mirroring tests/test_query_thermal.py: happy-path JSON shape,
# core parity (subprocess == in-process), and the self-validating exit-code matrix
# (curated {"error"} -> exit 1; argparse -> exit 2).

import json
import os
import pathlib
import subprocess
import sys
import unittest

import core.spin as spin

_REPO = pathlib.Path(__file__).resolve().parent.parent
_ENV = {"SPACE_APP_DB": "/tmp/phase_w_throwaway.db", "PATH": os.environ.get("PATH", "")}


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


class HappyPathTest(unittest.TestCase):
    def test_case_a_and_parity(self):
        rc, d, _ = _run("spin-comfort", "--radius-m", "224", "--rpm", "2.0")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["gravity_g"], 1.0019, places=3)
        self.assertAlmostEqual(d["tangential_velocity_ms"], 46.91, places=1)
        self.assertAlmostEqual(d["coriolis_ratio_pct"], 4.26, places=2)
        self.assertEqual(d["anchors"], ["radius_m", "rpm"])
        self.assertIs(d["criteria"]["conservative"]["pass"], True)
        self.assertIn("model_note", d)
        ref = spin.compute_spin_comfort(radius_m=224, rpm=2.0)
        self.assertAlmostEqual(d["accel_ms2"], ref["accel_ms2"], places=6)
        self.assertAlmostEqual(d["gravity_gradient_pct"], ref["gravity_gradient_pct"], places=6)

    def test_gravity_g_form(self):
        rc, d, _ = _run("spin-comfort", "--radius-m", "10", "--gravity-g", "1.0")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["rpm"], 9.457, places=2)
        self.assertIs(d["criteria"]["conservative"]["pass"], False)

    def test_single_tier(self):
        rc, d, _ = _run("spin-comfort", "--radius-m", "56", "--rpm", "4.0", "--criteria", "moderate")
        self.assertEqual(rc, 0)
        self.assertEqual(set(d["criteria"].keys()), {"moderate"})


class ExitCodeTest(unittest.TestCase):
    def test_curated_errors_exit_1(self):
        for args in (
            ["spin-comfort", "--radius-m", "0", "--rpm", "2"],                     # non-positive anchor
            ["spin-comfort", "--radius-m", "10", "--rpm", "2", "--occupant-height-m", "12"],  # h >= r
            ["spin-comfort", "--radius-m", "10"],                                  # one anchor
            ["spin-comfort", "--radius-m", "10", "--rpm", "2", "--tangential-velocity-ms", "5"],  # three
            ["spin-comfort", "--radius-m", "10", "--rpm", "2", "--max-rpm", "0"],  # bad override
        ):
            rc, d, _ = _run(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_argparse_errors_exit_2(self):
        for args in (
            ["spin-comfort", "--radius-m", "10", "--gravity-g", "1", "--accel-ms2", "9.8"],  # gravity mutex
            ["spin-comfort", "--radius-m", "10", "--rpm", "2", "--criteria", "bogus"],        # bad choice
            ["spin-comfort", "--radius-m", "abc", "--rpm", "2"],                              # non-numeric
        ):
            rc, _, _ = _run(*args)
            self.assertEqual(rc, 2, args)


if __name__ == "__main__":
    unittest.main()
