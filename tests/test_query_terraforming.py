# tests/test_query_terraforming.py — Phase AB terraforming query.py contract.
#
# Offline subprocess tests mirroring tests/test_query_thermal.py: happy-path JSON
# shape, core parity (subprocess == in-process), and the self-validating exit-code
# matrix (curated {"error"} -> exit 1; argparse -> exit 2). No network, no DB.

import json
import os
import pathlib
import subprocess
import sys
import unittest

import core.terraforming as tf

_REPO = pathlib.Path(__file__).resolve().parent.parent
_ENV = {"SPACE_APP_DB": "/tmp/phase_ab_throwaway.db", "PATH": os.environ.get("PATH", "")}


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


class EquilibriumTempTest(unittest.TestCase):
    def test_happy_and_parity(self):
        rc, d, _ = _run("equilibrium-temp", "--insolation-wm2", "1361", "--albedo", "0.3",
                        "--greenhouse-delta-k", "33")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["t_eq_k"], 255.0, delta=1.0)
        self.assertAlmostEqual(d["t_surface_k"], 288.0, delta=1.0)
        ref = tf.compute_equilibrium_temp(insolation_wm2=1361, albedo=0.3, greenhouse_delta_k=33)
        self.assertAlmostEqual(d["t_eq_k"], ref["t_eq_k"], places=6)

    def test_inverse(self):
        rc, d, _ = _run("equilibrium-temp", "--insolation-wm2", "1361", "--target-surface-k", "288")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["required_forcing"]["greenhouse_delta_k"], 33.0, delta=1.0)


class InsolationShiftTest(unittest.TestCase):
    def test_happy(self):
        rc, d, _ = _run("insolation-shift", "--planet-radius-km", "3390",
                        "--delta-insolation-wm2", "20", "--solar-flux-wm2", "589")
        self.assertEqual(rc, 0)
        self.assertEqual(d["mode"], "mirror")
        ref = tf.compute_insolation_shift(planet_radius_km=3390, delta_insolation_wm2=20,
                                          solar_flux_wm2=589)
        self.assertAlmostEqual(d["mirror_area_m2"], ref["mirror_area_m2"], places=0)

    def test_shade_sign(self):
        rc, d, _ = _run("insolation-shift", "--planet-radius-km", "3390",
                        "--delta-insolation-wm2", "-20", "--solar-flux-wm2", "589")
        self.assertEqual(rc, 0)
        self.assertEqual(d["mode"], "shade")


class AtmosphereMassTest(unittest.TestCase):
    def test_mars_anchor_and_parity(self):
        rc, d, _ = _run("atmosphere-mass", "--planet-radius-km", "3390",
                        "--surface-gravity-ms2", "3.71", "--pressure-bar", "1")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["atmosphere_mass_kg"], 3.9e18, delta=0.1e18)
        self.assertAlmostEqual(d["atmosphere_mass_earth_atm"], 0.76, delta=0.02)
        ref = tf.compute_atmosphere_mass(planet_radius_km=3390, surface_gravity_ms2=3.71,
                                         pressure_bar=1)
        self.assertAlmostEqual(d["atmosphere_mass_kg"], ref["atmosphere_mass_kg"], places=0)


class ExitCodeMatrixTest(unittest.TestCase):
    def test_exit1_curated(self):
        for args in (
            ("equilibrium-temp", "--insolation-wm2", "1361", "--albedo", "1.0", "--greenhouse-delta-k", "33"),
            ("equilibrium-temp", "--insolation-wm2", "1361", "--greenhouse-delta-k", "33", "--optical-depth", "0.5"),
            ("equilibrium-temp", "--insolation-wm2", "1361"),                       # no forcing
            ("equilibrium-temp", "--greenhouse-delta-k", "33"),                     # no insolation
            ("insolation-shift", "--planet-radius-km", "3390", "--delta-insolation-wm2", "0",
             "--solar-flux-wm2", "589"),
            ("atmosphere-mass", "--planet-radius-km", "3390", "--surface-gravity-ms2", "3.71"),   # no P/m
            ("atmosphere-mass", "--planet-radius-km", "3390", "--surface-gravity-ms2", "3.71",
             "--planet-mass-earth", "0.1", "--pressure-bar", "1"),                  # two gravity
        ):
            rc, d, _ = _run(*args)
            self.assertEqual(rc, 1, msg=f"{args}")
            self.assertIn("error", d)

    def test_exit2_argparse(self):
        for args in (
            ("equilibrium-temp", "--insolation-wm2", "abc", "--greenhouse-delta-k", "33"),   # non-numeric
            ("atmosphere-mass", "--planet-radius-km", "3390", "--surface-gravity-ms2", "3.71",
             "--pressure-bar", "1", "--species", "argon"),                          # bad choice
            ("insolation-shift", "--delta-insolation-wm2", "20", "--solar-flux-wm2", "589"),  # missing required
        ):
            rc, d, _ = _run(*args)
            self.assertEqual(rc, 2, msg=f"{args}")
            self.assertIsNone(d)


if __name__ == "__main__":
    unittest.main()
