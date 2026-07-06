# tests/test_query_exposure_additions.py — query.py exposure-gap subcommands.
#
# Two subcommands added after a coverage audit, each a thin verbatim wrapper over
# an existing (non-self-validating) core function — so they follow the Phase-N
# contract: exit 0 on success, raw-exception {"error": str(e)} (exit 1) for an
# out-of-range numeric, argparse exit 2 for a missing/non-numeric arg.
#
#   * distance-at-acceleration → calculators.compute_distance_at_acceleration
#       (opt 24: accel + travel time → distance for the three profiles)
#   * star-regions-manual      → regions.compute_star_system_regions
#       (opt 10: manual vmag/BC/teff/parallax → full region values, no SIMBAD)
#
# Subprocess pattern mirrors tests/test_query_phase_n.py.

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

import core.calculators as calculators
import core.regions as regions

from tests._queryharness import make_env, run_query, run_query_inproc

_REPO = Path(__file__).resolve().parent.parent
# Neither subcommand reads the DB, but pass a throwaway SPACE_APP_DB so a stray
# seed never touches data/space_app.db.
_ENV = make_env("query_exposure_throwaway.db")


def _run(*cmd_args):
    """Run query.py with args; return (returncode, parsed_stdout_or_None, stderr)."""
    return run_query(*cmd_args, env=_ENV)


class DistanceAtAccelerationTest(unittest.TestCase):

    def test_happy_path_contract_and_parity(self):
        code, payload, _ = _run("distance-at-acceleration", "--accel-g", "1.0", "--hours", "24")
        self.assertEqual(code, 0)
        self.assertEqual(set(payload), {"accel_g", "hours", "travel_time_str", "profiles"})
        self.assertEqual(len(payload["profiles"]), 3)
        for p in payload["profiles"]:
            self.assertEqual(set(p), {"label", "distance_au", "distance_lm", "max_vel"})
        # max_vel: N/A for profiles 1 & 2, Y/N for profile 3.
        self.assertEqual([p["max_vel"] for p in payload["profiles"]][:2], ["N/A", "N/A"])
        self.assertIn(payload["profiles"][2]["max_vel"], ("Y", "N"))
        # Parity with the wrapped core function.
        expected = calculators.compute_distance_at_acceleration(1.0, 24.0)
        self.assertEqual(payload["travel_time_str"], expected["travel_time_str"])
        for got, exp in zip(payload["profiles"], expected["profiles"]):
            self.assertAlmostEqual(got["distance_au"], exp["distance_au"], places=6)
            self.assertAlmostEqual(got["distance_lm"], exp["distance_lm"], places=6)

    def test_zero_accel_is_raw_exception_exit1(self):
        code, payload, _ = run_query_inproc("distance-at-acceleration", "--accel-g", "0", "--hours", "24")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)        # raw "division by zero" — not curated

    def test_argparse_exit2(self):
        self.assertEqual(run_query_inproc("distance-at-acceleration", "--accel-g", "1.0")[0], 2)   # missing --hours
        self.assertEqual(run_query_inproc("distance-at-acceleration", "--accel-g", "x",
                                          "--hours", "24")[0], 2)                                   # non-numeric


class StarRegionsManualTest(unittest.TestCase):

    def test_happy_path_contract_and_parity(self):
        code, payload, _ = _run("star-regions-manual", "--vmag", "5.5", "--bc", "-0.1",
                                "--teff", "5500", "--parallax", "100")
        self.assertEqual(code, 0)
        # Inputs echoed + the full region-values dict (same shape as sol-regions).
        for k in ("vmag", "boloLum", "temp", "plx", "sunlight_intensity", "bond_albedo",
                  "stellarMass", "bcLuminosity", "hzil", "hzol", "snowLine", "distAU",
                  "ffInner", "phOuter", "calculatedLuminosity"):
            self.assertIn(k, payload)
        # Parity with the wrapped core function.
        expected = regions.compute_star_system_regions(5.5, -0.1, 5500.0, 100.0)
        for k in ("stellarMass", "bcLuminosity", "hzil", "hzol", "distAU"):
            self.assertAlmostEqual(payload[k], expected[k], places=6)

    def test_defaults_applied(self):
        _, payload, _ = _run("star-regions-manual", "--vmag", "5", "--bc", "-0.1",
                             "--teff", "5500", "--parallax", "100")
        self.assertEqual(payload["sunlight_intensity"], 1.0)
        self.assertEqual(payload["bond_albedo"], 0.3)

    def test_overrides_applied(self):
        _, payload, _ = _run("star-regions-manual", "--vmag", "5", "--bc", "-0.1",
                             "--teff", "5500", "--parallax", "100",
                             "--sunlight-intensity", "1.0", "--bond-albedo", "0.9")
        self.assertEqual(payload["bond_albedo"], 0.9)

    def test_zero_parallax_is_raw_exception_exit1(self):
        code, payload, _ = _run("star-regions-manual", "--vmag", "5", "--bc", "-0.1",
                                "--teff", "5500", "--parallax", "0")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)        # raw "division by zero"

    def test_negative_parallax_is_raw_exception_exit1(self):
        # parsecs < 0 → log10 domain error (still a raw exception, exit 1).
        code, payload, _ = _run("star-regions-manual", "--vmag", "5", "--bc", "-0.1",
                                "--teff", "5500", "--parallax", "-10")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)

    def test_argparse_exit2(self):
        self.assertEqual(run_query_inproc("star-regions-manual", "--vmag", "5", "--bc", "-0.1",
                                          "--teff", "5500")[0], 2)                       # missing --parallax
        self.assertEqual(run_query_inproc("star-regions-manual", "--vmag", "x", "--bc", "-0.1",
                                          "--teff", "5500", "--parallax", "100")[0], 2)  # non-numeric


class VelocityTravelConvertersTest(unittest.TestCase):
    """Group-A converters (opts 25–28, 31, 32): thin wrappers over the simple
    constant-velocity calculators. Same Phase-N contract — the conversion /
    distance wrappers have no error path; the two travel-time wrappers raise on a
    zero velocity (exit 1); argparse rejects missing/non-numeric args (exit 2)."""

    def test_ly_hr_to_times_c(self):
        code, payload, _ = _run("ly-hr-to-times-c", "--ly-hr", "0.01")
        self.assertEqual(code, 0)
        self.assertEqual(set(payload), {"ly_hr", "times_c"})
        self.assertAlmostEqual(payload["times_c"], 87.658128, places=4)
        self.assertEqual(payload, calculators.compute_ly_hr_to_times_c(0.01))

    def test_times_c_to_ly_hr(self):
        code, payload, _ = _run("times-c-to-ly-hr", "--times-c", "100")
        self.assertEqual(code, 0)
        self.assertEqual(payload, calculators.compute_speed_of_light_to_ly_hr(100.0))

    def test_distance_traveled_ly_hr_and_times_c(self):
        code, payload, _ = _run("distance-traveled-ly-hr", "--ly-hr", "0.01", "--hours", "100")
        self.assertEqual(code, 0)
        self.assertEqual(payload, calculators.compute_distance_traveled_ly_hr(0.01, 100.0))
        self.assertAlmostEqual(payload["distance_ly"], 1.0, places=9)
        code, payload, _ = _run("distance-traveled-times-c", "--times-c", "100", "--hours", "50")
        self.assertEqual(code, 0)
        self.assertEqual(payload, calculators.compute_distance_traveled_times_c(100.0, 50.0))

    def test_travel_time_ly_hr_and_times_c(self):
        code, payload, _ = _run("travel-time-ly-hr", "--distance-ly", "4.37", "--ly-hr", "0.01")
        self.assertEqual(code, 0)
        self.assertEqual(set(payload),
                         {"distance_ly", "ly_hr", "times_c", "total_hours", "travel_time_str"})
        self.assertEqual(payload, calculators.compute_travel_time_ly_hr(4.37, 0.01))
        code, payload, _ = _run("travel-time-times-c", "--distance-ly", "4.37", "--times-c", "100")
        self.assertEqual(code, 0)
        self.assertEqual(payload, calculators.compute_travel_time_times_c(4.37, 100.0))

    def test_zero_velocity_is_exit_1(self):
        # Travel-time pair: division by zero → raw-exception {"error"} exit 1.
        code, payload, _ = run_query_inproc("travel-time-ly-hr", "--distance-ly", "4.37", "--ly-hr", "0")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)
        code, payload, _ = run_query_inproc("travel-time-times-c", "--distance-ly", "4.37", "--times-c", "0")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)

    def test_argparse_exit_2(self):
        self.assertEqual(run_query_inproc("distance-traveled-ly-hr", "--ly-hr", "0.01")[0], 2)   # missing --hours
        self.assertEqual(run_query_inproc("ly-hr-to-times-c", "--ly-hr", "abc")[0], 2)           # non-numeric
        self.assertEqual(run_query_inproc("travel-time-ly-hr", "--ly-hr", "0.01")[0], 2)         # missing --distance-ly


if __name__ == "__main__":
    unittest.main()
