# tests/test_query_weapons.py — Phase AT (Packet 38.1) W2/W3/W4 query.py contract.
#
# Offline subprocess tests: happy-path JSON + core parity + the self-validating exit-code matrix
# (exit 1 curated / exit 2 argparse). Mirrors tests/test_query_radiation.py.

import unittest

import core.weapons as weapons

from tests._queryharness import make_env, run_query, run_query_inproc

_ENV = make_env("phase_at_weapons_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class BeamWeaponQueryTest(unittest.TestCase):
    def test_happy_and_parity(self):
        rc, d, _ = _run("beam-weapon-engagement", "--aperture-m", "10", "--wavelength-m", "1e-6",
                        "--power-w", "1e9", "--target-size-m", "1", "--range-m", "1e9",
                        "--kill-fluence-jm2", "1e7")
        self.assertEqual(rc, 0)
        ref = weapons.compute_beam_weapon_engagement(aperture_m=10, wavelength_m=1e-6, power_w=1e9,
                                                     target_size_m=1, range_m=1e9, kill_fluence_jm2=1e7)
        self.assertAlmostEqual(d["dwell_to_kill_s"], ref["dwell_to_kill_s"], places=6)
        self.assertAlmostEqual(d["spot_diameter_m"], 244.0, places=3)

    def test_exit_matrix(self):
        rc, d, _ = run_query_inproc("beam-weapon-engagement", "--aperture-m", "10",
                                    "--wavelength-m", "1e-6", "--power-w", "1e9",
                                    "--target-size-m", "1", "--range-m", "1e9")   # no Φ_kill
        self.assertEqual(rc, 1)
        self.assertIn("error", d)
        rc, _, err = run_query_inproc("beam-weapon-engagement", "--aperture-m", "10",
                                      "--power-w", "1e9", "--target-size-m", "1", "--range-m", "1e9",
                                      "--kill-fluence-jm2", "1e7")                 # no λ/f (required group)
        self.assertEqual(rc, 2)
        self.assertTrue(err)


class KineticKillQueryTest(unittest.TestCase):
    def test_happy_and_parity(self):
        rc, d, _ = _run("kinetic-kill", "--mass-kg", "1", "--velocity-kms", "100",
                        "--target-density-kgm3", "7800")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["ke_classical_j"], 5e9)
        self.assertAlmostEqual(d["tnt_equiv_t"], 5e9 / 4.184e9, places=6)

    def test_whipple(self):
        rc, d, _ = _run("kinetic-kill", "--mass-kg", "0.01", "--velocity-kms", "5",
                        "--target-density-kgm3", "7800", "--target-type", "whipple",
                        "--bumper-areal-density-kgm2", "0.5", "--standoff-m", "0.1",
                        "--rearwall-areal-density-kgm2", "1.0")
        self.assertEqual(rc, 0)
        self.assertTrue(d["whipple"]["impactor_shattered"])

    def test_exit_matrix(self):
        rc, d, _ = run_query_inproc("kinetic-kill", "--mass-kg", "1",
                                    "--target-density-kgm3", "7800")             # no velocity
        self.assertEqual(rc, 2)                                                  # required group
        rc, d, _ = run_query_inproc("kinetic-kill", "--velocity-kms", "100",
                                    "--target-density-kgm3", "7800")             # no impactor
        self.assertEqual(rc, 1)
        self.assertIn("error", d)


class WarheadEffectsQueryTest(unittest.TestCase):
    def test_happy_and_binding(self):
        rc, d, _ = _run("warhead-effects-at-standoff", "--yield-kt", "1", "--warhead-type", "fission",
                        "--standoff-m", "1000", "--threshold-xray-jm2", "1e6")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["channels"]["xray"]["kill_radius_m"], 499.714, places=2)
        self.assertEqual(d["binding_channel"], "xray")

    def test_exit_matrix(self):
        rc, d, _ = run_query_inproc("warhead-effects-at-standoff", "--yield-j", "1e12",
                                    "--standoff-m", "1000", "--f-xray", "0.9", "--f-debris", "0.9")
        self.assertEqual(rc, 1)                                                  # fractions sum > 1
        self.assertIn("error", d)
        rc, _, err = run_query_inproc("warhead-effects-at-standoff", "--warhead-type", "fusion",
                                      "--standoff-m", "1000")                     # no yield (required group)
        self.assertEqual(rc, 2)
        self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
