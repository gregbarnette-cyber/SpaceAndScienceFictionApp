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

_REPO = Path(__file__).resolve().parent.parent
# Neither subcommand reads the DB, but pass a throwaway SPACE_APP_DB so a stray
# seed never touches data/space_app.db.
_ENV = {"SPACE_APP_DB": "/tmp/query_exposure_throwaway.db", "PATH": os.environ.get("PATH", "")}


def _run(*cmd_args):
    """Run query.py with args; return (returncode, parsed_stdout_or_None, stderr)."""
    proc = subprocess.run(
        [sys.executable, str(_REPO / "query.py"), *cmd_args],
        capture_output=True, text=True, cwd=str(_REPO), env=_ENV,
    )
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        payload = None
    return proc.returncode, payload, proc.stderr


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
        code, payload, _ = _run("distance-at-acceleration", "--accel-g", "0", "--hours", "24")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)        # raw "division by zero" — not curated

    def test_argparse_exit2(self):
        self.assertEqual(_run("distance-at-acceleration", "--accel-g", "1.0")[0], 2)   # missing --hours
        self.assertEqual(_run("distance-at-acceleration", "--accel-g", "x",
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
        self.assertEqual(_run("star-regions-manual", "--vmag", "5", "--bc", "-0.1",
                              "--teff", "5500")[0], 2)                       # missing --parallax
        self.assertEqual(_run("star-regions-manual", "--vmag", "x", "--bc", "-0.1",
                              "--teff", "5500", "--parallax", "100")[0], 2)  # non-numeric


if __name__ == "__main__":
    unittest.main()
