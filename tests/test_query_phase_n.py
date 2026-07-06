# tests/test_query_phase_n.py — Phase N query.py subcommand contracts.
#
# Phase N adds five query.py subcommands, each a thin verbatim wrapper over an
# existing core function (no core/GUI/CLI/DB changes). These tests lock:
#   * the happy-path JSON contract (keys + a known anchor value) for N1–N4,
#   * output parity with the wrapped core function (N1),
#   * the exit-code matrix — exit 1 for out-of-range numerics (raw exception
#     messages, since N1–N4 wrap non-self-validating legacy functions), exit 0
#     for star-luminosity's no-error-path, exit 2 for argparse rejection,
#   * N5's dispatcher wiring (arg mapping; progress_callback never passed) via a
#     mock — no network,
#   * an optional live N5 round-trip, gated on JPL Horizons reachability.
#
# Pattern mirrors tests/test_gcns.py::GcnsQueryCliTest (subprocess against
# query.py with cwd=_REPO and a throwaway SPACE_APP_DB).

import argparse
import contextlib
import io
import json
import os
import socket
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from tests._queryharness import make_env, run_query, run_query_inproc

_REPO = Path(__file__).resolve().parent.parent

# Phase N subcommands are pure-compute / network; none reads the DB, but we pass
# a throwaway SPACE_APP_DB so a stray seed never touches data/space_app.db.
_ENV = make_env("phase_n_throwaway.db")


def _run(*cmd_args):
    """Run query.py with args; return (returncode, parsed_stdout_or_None, stderr)."""
    return run_query(*cmd_args, env=_ENV)


def _horizons_reachable(host="ssd.jpl.nasa.gov", port=443, timeout=3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ── N1–N4 happy-path contract ────────────────────────────────────────────────

class PhaseNHappyPathTest(unittest.TestCase):

    def test_n1_hz_sma_contract(self):
        code, payload, _ = _run("habitable-zone-sma", "--teff", "5778",
                                "--luminosity", "1", "--sma", "1")
        self.assertEqual(code, 0)
        self.assertEqual(set(payload), {"zones", "planet_seff", "verdict"})
        self.assertEqual(len(payload["zones"]), 6)
        for z in payload["zones"]:
            self.assertEqual(set(z), {"zone_name", "key", "au", "lm", "seff"})
        self.assertAlmostEqual(payload["planet_seff"], 1.0, places=9)
        self.assertIn("Conservative Habitable Zone", payload["verdict"])

    def test_n2_star_luminosity_contract(self):
        code, payload, _ = _run("star-luminosity", "--radius", "1", "--teff", "5778")
        self.assertEqual(code, 0)
        self.assertEqual(set(payload), {"radius", "temp", "luminosity"})
        self.assertAlmostEqual(payload["luminosity"], 1.0, places=9)

    def test_n3_brachistochrone_au_contract(self):
        code, payload, _ = _run("brachistochrone-au", "--accel-g", "1", "--au", "1")
        self.assertEqual(code, 0)
        self.assertEqual(set(payload), {"accel_g", "distance_au", "distance_lm", "profiles"})
        self.assertEqual(len(payload["profiles"]), 3)
        for prof in payload["profiles"]:
            self.assertEqual(set(prof), {"label", "hours", "travel_time_str", "max_vel"})
        self.assertAlmostEqual(payload["distance_lm"], 8.3167, places=3)

    def test_n4_brachistochrone_lm_contract(self):
        code, payload, _ = _run("brachistochrone-lm", "--accel-g", "1", "--lm", "8.3167")
        self.assertEqual(code, 0)
        self.assertEqual(set(payload), {"accel_g", "distance_au", "distance_lm", "profiles"})
        self.assertEqual(len(payload["profiles"]), 3)
        self.assertAlmostEqual(payload["distance_au"], 1.0, places=4)


# ── Parity: subcommand output == wrapped core function ───────────────────────

class PhaseNParityTest(unittest.TestCase):
    """One parity check proves the dispatcher adds/loses nothing vs. the core fn."""

    def test_n1_parity(self):
        import core.equations as equations
        core_result = equations.compute_habitable_zone_sma(5778.0, 1.0, 1.0)
        # Round-trip the core dict through the same serializer query.py uses, so
        # the comparison is value-for-value after JSON normalization.
        expected = json.loads(json.dumps(core_result, default=str))
        code, payload, _ = _run("habitable-zone-sma", "--teff", "5778",
                                "--luminosity", "1", "--sma", "1")
        self.assertEqual(code, 0)
        self.assertEqual(payload, expected)


# ── Exit-code matrix (the documented Phase N decision) ───────────────────────

class PhaseNExitCodeTest(unittest.TestCase):

    def test_n1_sma_zero_exit1(self):
        code, payload, _ = run_query_inproc("habitable-zone-sma", "--teff", "5778",
                                            "--luminosity", "1", "--sma", "0")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)

    def test_n1_negative_lum_exit1(self):
        code, payload, _ = run_query_inproc("habitable-zone-sma", "--teff", "5778",
                                            "--luminosity", "-1", "--sma", "1")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)

    def test_n3_accel_zero_exit1(self):
        code, payload, _ = run_query_inproc("brachistochrone-au", "--accel-g", "0", "--au", "1")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)

    def test_n2_negative_radius_is_not_an_error(self):
        # star-luminosity has no error path beyond argparse: radius is squared,
        # so a negative radius yields a valid positive luminosity, exit 0.
        code, payload, _ = _run("star-luminosity", "--radius", "-1", "--teff", "5778")
        self.assertEqual(code, 0)
        self.assertAlmostEqual(payload["luminosity"], 1.0, places=9)

    def test_missing_required_exit2(self):
        code, payload, stderr = run_query_inproc("habitable-zone-sma", "--teff", "5778",
                                                 "--luminosity", "1")  # no --sma
        self.assertEqual(code, 2)
        self.assertIsNone(payload)       # argparse error → nothing on stdout
        self.assertTrue(stderr.strip())  # message on stderr

    def test_n5_missing_origin_exit2(self):
        code, _payload, stderr = run_query_inproc("travel-time-solar",
                                                  "--destination", "Mars", "--accel-g", "1")
        self.assertEqual(code, 2)
        self.assertTrue(stderr.strip())


# ── N5 dispatcher wiring (mocked — no network) ───────────────────────────────

class PhaseNTravelTimeSolarWiringTest(unittest.TestCase):

    def test_n5_dispatch_wiring(self):
        import query
        sentinel = {"origin": "Earth", "destination": "Mars", "ok": True}
        captured = {}

        def recorder(*a, **k):
            captured["args"] = a
            captured["kwargs"] = k
            return sentinel

        ns = argparse.Namespace(
            origin="Earth", destination="Mars", accel_g=1.0,
            v_cap_pct=3.0, date="2027-03-15",
        )
        buf = io.StringIO()
        with mock.patch.object(query.calculators,
                               "compute_travel_time_solar_objects", recorder):
            with contextlib.redirect_stdout(buf):
                with self.assertRaises(SystemExit) as cm:
                    query.cmd_travel_time_solar(ns)

        self.assertEqual(cm.exception.code, 0)
        # positional args: (origin, destination, accel_g)
        self.assertEqual(captured["args"], ("Earth", "Mars", 1.0))
        # --date → departure_date, --v-cap-pct → v_cap_pct
        self.assertEqual(captured["kwargs"],
                         {"v_cap_pct": 3.0, "departure_date": "2027-03-15"})
        # progress_callback is GUI-only — must never be passed
        self.assertNotIn("progress_callback", captured["kwargs"])
        # stdout carries the serialized core result, exit 0
        self.assertEqual(json.loads(buf.getvalue()), sentinel)


# ── N5 live round-trip (gated on JPL Horizons reachability) ──────────────────

class PhaseNTravelTimeSolarLiveTest(unittest.TestCase):

    @unittest.skipUnless(_horizons_reachable(),
                         "JPL Horizons (ssd.jpl.nasa.gov) not reachable")
    def test_n5_earth_mars_live(self):
        code, payload, _ = _run("travel-time-solar", "--origin", "Earth",
                                "--destination", "Mars", "--accel-g", "1")
        self.assertEqual(code, 0)
        self.assertIn("profiles", payload)
        self.assertEqual(len(payload["profiles"]), 3)
        self.assertGreater(payload["distance_au"], 0.0)


if __name__ == "__main__":
    unittest.main()
