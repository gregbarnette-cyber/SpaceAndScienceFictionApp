# tests/test_query_sensing.py — Phase AP (Group S) query.py contract.
#
# Offline subprocess tests (mirroring tests/test_query_power.py): happy-path JSON shape + core
# parity + the self-validating exit-code matrix (curated {"error"} → exit 1; argparse → exit 2) for
# the three Phase-AP subcommands (S2 angular-resolution, S1 point-source-detection, S3 radar-range).

import unittest

import core.sensing as sensing
from tests._queryharness import make_env, run_query

_ENV = make_env("phase_ap_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class HappyPathTest(unittest.TestCase):
    def test_angular_resolution(self):
        rc, d, _ = _run("angular-resolution", "--aperture-m", "1", "--wavelength-m", "10e-6",
                        "--range-m", "1.496e11")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["angular_resolution_arcsec"], 2.5164306332, places=6)
        ref = sensing.compute_angular_resolution(aperture_m=1, wavelength_m=10e-6, range_m=1.496e11)
        self.assertAlmostEqual(d["linear_resolution_m"], ref["linear_resolution_m"], places=3)

    def test_point_source_flux_floor(self):
        rc, d, _ = _run("point-source-detection", "--source-temp-k", "300",
                        "--source-area-m2", "1000", "--rx-aperture-m", "1",
                        "--flux-floor-w-m2", "1e-19")
        self.assertEqual(rc, 0)
        self.assertEqual(d["detection_regime"], "flux-floor")
        self.assertAlmostEqual(d["max_detection_range_m"] / 1.496e11, 4.04, places=2)  # WB pin

    def test_point_source_snr_at_range(self):
        rc, d, _ = _run("point-source-detection", "--source-power-w", "4.593e5",
                        "--rx-aperture-m", "1", "--range-m", "1.496e11",
                        "--wavelength-m", "10e-6", "--nep-w-rthz", "1e-19")
        self.assertEqual(rc, 0)
        self.assertEqual(d["detection_regime"], "detector-limited")
        self.assertIsNotNone(d["snr"])
        self.assertAlmostEqual(d["photon_rate_hz"], 51.66, delta=0.1)

    def test_radar_range(self):
        rc, d, _ = _run("radar-range", "--tx-power-w", "1e9", "--tx-aperture-m", "10",
                        "--wavelength-m", "0.03", "--target-rcs-m2", "100", "--range-m", "1e9")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["received_power_w"], 5.45415391e-20, delta=1e-28)

    def test_radar_max_range(self):
        rc, d, _ = _run("radar-range", "--tx-power-w", "1e9", "--tx-aperture-m", "10",
                        "--wavelength-m", "0.03", "--target-rcs-m2", "100",
                        "--min-detectable-power-w", "1e-18")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["max_range_m"], 4.83261110e8, delta=10.0)


class ExitCodeMatrixTest(unittest.TestCase):
    def test_curated_error_exit_1(self):
        rc, d, _ = _run("angular-resolution", "--aperture-m", "-1", "--wavelength-m", "1e-6")
        self.assertEqual(rc, 1)
        self.assertIn("error", d)

    def test_flux_floor_and_nep_conflict_exit_1(self):
        rc, d, _ = _run("point-source-detection", "--source-power-w", "1e5", "--rx-aperture-m", "1",
                        "--flux-floor-w-m2", "1e-19", "--nep-w-rthz", "1e-19")
        self.assertEqual(rc, 1)
        self.assertIn("error", d)

    def test_argparse_missing_required_exit_2(self):
        rc, _d, _ = _run("angular-resolution", "--wavelength-m", "1e-6")   # no --aperture-m
        self.assertEqual(rc, 2)

    def test_argparse_mutually_exclusive_exit_2(self):
        rc, _d, _ = _run("radar-range", "--tx-power-w", "1e9", "--tx-aperture-m", "10",
                         "--wavelength-m", "0.03", "--target-rcs-m2", "100",
                         "--range-m", "1e9", "--min-detectable-power-w", "1e-18")
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
