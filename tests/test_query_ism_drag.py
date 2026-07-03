# tests/test_query_ism_drag.py — Phase AC ISM-drag query.py contract (Group K).
#
# Offline subprocess tests mirroring tests/test_query_propulsion.py: happy-path JSON shape,
# core parity (subprocess == in-process), and the self-validating exit-code matrix
# (curated {"error"} → exit 1; argparse → exit 2).

import json
import os
import pathlib
import subprocess
import sys
import unittest

import core.ism_drag as ism

_REPO = pathlib.Path(__file__).resolve().parent.parent
_ENV = {"SPACE_APP_DB": "/tmp/phase_ac_throwaway.db", "PATH": os.environ.get("PATH", "")}


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


class MagsailQueryTest(unittest.TestCase):
    def test_happy_and_parity(self):
        # A1: the R_mp ≈ 100 km / ~kN headline now belongs to the moment-only (far-field) anchor.
        import math
        m_dip = 1e5 * math.pi * (1e5) ** 2
        rc, d, _ = _run("magsail", "--ism-density-cm3", "0.1", "--ion-mass-amu", "1.0",
                        "--beta", "0.1", "--magnetic-moment-am2", repr(m_dip),
                        "--vehicle-mass-t", "1000")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["magnetopause_radius_km"], 100.0, delta=5.0)
        self.assertTrue(1e3 <= d["drag_force_n"] <= 1e4)
        self.assertIn("v^4/3", d["drag_scaling_note"])
        ref = ism.compute_magsail(ism_density_cm3=0.1, ion_mass_amu=1.0, beta=0.1,
                                  magnetic_moment_am2=m_dip, vehicle_mass_t=1000)
        self.assertAlmostEqual(d["drag_force_n"], ref["drag_force_n"], places=6)

    def test_coil_exact_and_ionization(self):
        # A1: coil-pair anchor → exact near-field R_mp + far-field cross-check echoed.
        rc, d, _ = _run("magsail", "--ism-density-cm3", "0.1", "--ion-mass-amu", "1.0",
                        "--beta", "0.1", "--coil-radius-m", "100000", "--coil-current-a", "100000")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["magnetopause_radius_km"], 13.12, delta=0.2)
        self.assertAlmostEqual(d["magnetopause_radius_farfield_km"], 100.86, delta=0.5)
        # A3: --ionization-fraction 0.5 halves the interacting density
        rc2, h, _ = _run("magsail", "--ism-density-cm3", "0.1", "--ion-mass-amu", "1.0",
                         "--beta", "0.1", "--magnetic-moment-am2", "1e15",
                         "--ionization-fraction", "0.5")
        self.assertEqual(rc2, 0)
        self.assertEqual(h["ionization_fraction"], 0.5)

    def test_stopping(self):
        rc, d, _ = _run("magsail", "--beta", "0.1", "--coil-radius-m", "100000",
                        "--coil-current-a", "100000", "--vehicle-mass-t", "1000",
                        "--velocity-final-kms", "1000")
        self.assertEqual(rc, 0)
        self.assertGreater(d["stopping_distance_ly"], 0)
        self.assertGreater(d["stopping_time_yr"], 0)

    def test_exit1_curated(self):
        for args in (["magsail", "--coil-radius-m", "100000", "--coil-current-a", "100000"],  # no vel
                     ["magsail", "--beta", "1.0", "--magnetic-moment-am2", "1e15"],            # β=1
                     ["magsail", "--beta", "0.1", "--coil-radius-m", "100000"],                # partial coil
                     ["magsail", "--beta", "0.1", "--magnetic-moment-am2", "1e15",
                      "--velocity-final-kms", "1000"],                                          # vf no mass
                     ["magsail", "--beta", "0.1", "--magnetic-moment-am2", "1e15",
                      "--ionization-fraction", "1.5"],                                          # x_ion>1
                     ["magsail", "--beta", "0.1", "--magnetic-moment-am2", "-1"]):              # neg moment
            rc, d, _ = _run(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_exit2_argparse(self):
        for args in (["magsail", "--velocity-kms", "100", "--beta", "0.1",
                      "--magnetic-moment-am2", "1e15"],                       # velocity mutex
                     ["magsail", "--beta", "abc", "--magnetic-moment-am2", "1e15"]):  # non-numeric
            rc, _, err = _run(*args)
            self.assertEqual(rc, 2, args)
            self.assertTrue(err)


class RamscoopQueryTest(unittest.TestCase):
    def test_happy_brake_and_parity(self):
        rc, d, _ = _run("ramscoop", "--fuel", "pp", "--beta", "0.1",
                        "--coil-radius-m", "100000", "--coil-current-a", "100000")
        self.assertEqual(rc, 0)
        self.assertEqual(d["verdict"], "brake")
        self.assertLess(d["net_force_n"], 0)
        ref = ism.compute_ramscoop(fuel="pp", beta=0.1, coil_radius_m=1e5, coil_current_a=1e5)
        self.assertAlmostEqual(d["net_force_n"], ref["net_force_n"], places=6)

    def test_drive_low_beta(self):
        rc, d, _ = _run("ramscoop", "--fuel", "pp", "--fusion-efficiency", "1.0",
                        "--beta", "0.01", "--scoop-area-km2", "1000")
        self.assertEqual(rc, 0)
        self.assertEqual(d["verdict"], "drive")
        self.assertGreater(d["crossover_velocity_kms"], 0)

    def test_exit1_curated(self):
        for args in (["ramscoop", "--beta", "0.1", "--scoop-area-km2", "1000"],       # no exhaust
                     ["ramscoop", "--beta", "0.1", "--scoop-area-km2", "1000",
                      "--fuel", "pp", "--exhaust-velocity-kms", "10000"],             # two exhaust
                     ["ramscoop", "--beta", "0.1", "--scoop-area-km2", "1000",
                      "--fuel", "pp", "--fusion-efficiency", "2.0"],                   # η > 1
                     ["ramscoop", "--beta", "0.1", "--scoop-area-km2", "1000",
                      "--coil-radius-m", "100000", "--coil-current-a", "100000",
                      "--fuel", "pp"],                                                # area + field
                     ["ramscoop", "--fuel", "pp", "--scoop-area-km2", "1000"]):       # no velocity
            rc, d, _ = _run(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_exit2_argparse(self):
        for args in (["ramscoop", "--beta", "0.1", "--scoop-area-km2", "1000", "--fuel", "xyz"],  # bad choice
                     ["ramscoop", "--velocity-kms", "100", "--beta", "0.1",
                      "--scoop-area-km2", "1000", "--fuel", "pp"],                                 # velocity mutex
                     ["ramscoop", "--beta", "0.1", "--scoop-area-km2", "abc", "--fuel", "pp"]):    # non-numeric
            rc, _, err = _run(*args)
            self.assertEqual(rc, 2, args)
            self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
