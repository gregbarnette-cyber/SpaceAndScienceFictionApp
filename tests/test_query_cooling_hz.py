# tests/test_query_cooling_hz.py — Phase U `cooling-hz` query.py subcommand contract.
#
# Offline subprocess tests mirroring tests/test_query_phase_t.py: the three-mode
# happy-path JSON shape, core parity (subprocess == in-process), and the
# self-validating exit-code matrix (curated {"error"} -> exit 1; argparse -> exit 2).

import json
import os
import pathlib
import subprocess
import sys
import unittest

import core.cooling as cooling

_REPO = pathlib.Path(__file__).resolve().parent.parent
_ENV = {"SPACE_APP_DB": "/tmp/phase_u_throwaway.db", "PATH": os.environ.get("PATH", "")}


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
    def test_mode1_snapshot(self):
        rc, d, _ = _run("cooling-hz", "--track", "wd", "--teff", "5000")
        self.assertEqual(rc, 0)
        self.assertEqual(d["mode"], "snapshot")
        for k in ("teff_k", "lum_lsun", "radius_rsun", "zones", "out_of_range_teff",
                  "any_out_of_range", "hz_model_valid_teff_k", "model_note"):
            self.assertIn(k, d)
        self.assertEqual(len(d["zones"]), 6)

    def test_mode2_residence(self):
        rc, d, _ = _run("cooling-hz", "--track", "wd", "--sma-au", "0.01",
                        "--hz-edge", "optimistic")
        self.assertEqual(rc, 0)
        self.assertEqual(d["mode"], "residence")
        self.assertTrue(d["ever_habitable"])
        # parity with the in-process core
        ref = cooling.compute_cooling_hz("wd", mass_solar=0.6, sma_au=0.01,
                                         hz_edge="optimistic")
        self.assertAlmostEqual(d["residence_gyr"], ref["residence_gyr"], places=4)

    def test_mode3_chz_default(self):
        rc, d, _ = _run("cooling-hz", "--track", "wd", "--mass-solar", "0.6")
        self.assertEqual(rc, 0)
        self.assertEqual(d["mode"], "chz")
        for k in ("chz_inner_au", "chz_outer_au", "inner_edge_roche_limited",
                  "roche_limit_au", "chz_threshold_gyr"):
            self.assertIn(k, d)
        self.assertLess(d["chz_inner_au"], d["chz_outer_au"])


class ExitCodeMatrixTest(unittest.TestCase):
    def test_curated_errors_exit_1(self):
        for args in (
            ("cooling-hz", "--track", "wd", "--mass-solar", "2.0"),    # off-grid WD
            ("cooling-hz", "--track", "wd", "--sma-au", "0"),          # sma <= 0
            ("cooling-hz", "--track", "bd", "--mass-mjup", "200"),     # off-grid BD
        ):
            rc, d, _ = _run(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d)

    def test_bd_track_happy_path(self):
        rc, d, _ = _run("cooling-hz", "--track", "bd", "--mass-mjup", "52.4",
                        "--sma-au", "0.05")
        self.assertEqual(rc, 0)
        self.assertEqual(d["mode"], "residence")
        self.assertTrue(d["ever_habitable"])
        self.assertIn("ATMO 2020", d["model_note"])

    def test_argparse_exit_2(self):
        for args in (
            ("cooling-hz",),                                              # missing --track
            ("cooling-hz", "--track", "xx"),                             # bad track
            ("cooling-hz", "--track", "wd", "--teff", "5000", "--sma-au", "0.01"),  # 2 modes
            ("cooling-hz", "--track", "wd", "--mass-solar", "0.6", "--mass-mjup", "600"),  # 2 mass
            ("cooling-hz", "--track", "wd", "--teff", "abc"),           # non-numeric
            ("cooling-hz", "--track", "wd", "--hz-edge", "bogus"),      # bad choice
        ):
            rc, d, err = _run(*args)
            self.assertEqual(rc, 2, args)
            self.assertIsNone(d)


class DistillationPauseTest(unittest.TestCase):
    """Phase AD A0 — the `--cooling-delay-gyr` distillation pause via the subprocess CLI."""

    def test_pause_happy_path_and_parity(self):
        rc, d, _ = _run("cooling-hz", "--track", "wd", "--mass-solar", "0.6",
                        "--chz-threshold-gyr", "6", "--cooling-delay-gyr", "8")
        self.assertEqual(rc, 0)
        self.assertEqual(d["mode"], "chz")
        for k in ("cooling_delay_gyr", "distillation_teff_k", "pause_teff_k",
                  "pause_hz_inner_au", "pause_hz_outer_au", "effective_age_max_gyr"):
            self.assertIn(k, d)
        self.assertAlmostEqual(d["pause_teff_k"], 5500.0, delta=5.0)
        ref = cooling.compute_cooling_hz("wd", mass_solar=0.6, chz_threshold_gyr=6.0,
                                         cooling_delay_gyr=8.0)
        self.assertAlmostEqual(d["chz_outer_au"], ref["chz_outer_au"], places=5)

    def test_delta_zero_matches_no_flag(self):
        rc1, d1, _ = _run("cooling-hz", "--track", "wd", "--sma-au", "0.012")
        rc2, d2, _ = _run("cooling-hz", "--track", "wd", "--sma-au", "0.012",
                          "--cooling-delay-gyr", "0")
        self.assertEqual(rc1, 0)
        self.assertEqual(d1, d2)                    # byte-identical through the CLI too

    def test_exit_1_matrix(self):
        for args in (
            ("cooling-hz", "--track", "wd", "--cooling-delay-gyr", "-1"),        # neg delay
            ("cooling-hz", "--track", "wd", "--cooling-delay-gyr", "5",
             "--distillation-teff-k", "200000"),                                 # distil Teff off track
            ("cooling-hz", "--track", "bd", "--mass-mjup", "52.4",
             "--sma-au", "0.05", "--cooling-delay-gyr", "5"),                    # bd + delay
        ):
            rc, d, _ = _run(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d)

    def test_exit_2_non_numeric(self):
        rc, d, _ = _run("cooling-hz", "--track", "wd", "--cooling-delay-gyr", "abc")
        self.assertEqual(rc, 2)
        self.assertIsNone(d)


if __name__ == "__main__":
    unittest.main()
