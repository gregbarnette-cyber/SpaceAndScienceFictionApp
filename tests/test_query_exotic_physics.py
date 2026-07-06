# tests/test_query_exotic_physics.py — Phase AG (Group M) query.py contract.
#
# Offline subprocess tests mirroring tests/test_query_active_shield.py: happy-path JSON,
# core parity, and the self-validating exit-code matrix (exit 1 curated / exit 2 argparse).

import unittest

import core.exotic_physics as exotic_physics

from tests._queryharness import make_env, run_query, run_query_inproc

_ENV = make_env("phase_ag_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class ExoticPhysicsQueryTest(unittest.TestCase):
    def test_casimir_parity(self):
        rc, d, _ = _run("casimir", "--separation-nm", "1000")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["pressure_pa"], 1.30e-3, delta=1e-5)
        ref = exotic_physics.compute_casimir(separation_nm=1000)
        self.assertAlmostEqual(d["energy_density_j_m3"], ref["energy_density_j_m3"], places=18)

    def test_vacuum_energy(self):
        rc, d, _ = _run("vacuum-energy")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["rho_lambda_j_m3"], 5.3e-10, delta=2e-11)
        self.assertTrue(1e121 < d["catastrophe_ratio"] < 1e124)

    def test_schwinger(self):
        rc, d, _ = _run("schwinger-limit")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["critical_field_vm"], 1.32e18, delta=1e16)

    def test_hubble_flow(self):
        rc, d, _ = _run("hubble-flow", "--distance-mpc", "100")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["recession_velocity_kms"], 6740, delta=1)
        rc2, d2, _ = _run("hubble-flow", "--mass-msun", "3e12", "--radius-mpc", "1")
        self.assertEqual(rc2, 0)
        self.assertTrue(d2["bound"])

    def test_exit1_curated(self):
        for args in (
            ["casimir"],                                                     # no separation
            ["casimir", "--separation-nm", "100", "--geometry", "sphere-plate"],  # no radius
            ["vacuum-energy", "--omega-lambda", "2.0"],                     # Ω_Λ > 1
            ["vacuum-energy", "--cutoff", "banana"],                        # bad cutoff string
            ["schwinger-limit", "--field-vm", "1e18", "--intensity-wcm2", "1e29"],  # both
            ["hubble-flow"],                                                # neither mode
            ["hubble-flow", "--distance-mpc", "100", "--mass-msun", "1e12"],  # both modes
        ):
            rc, d, _ = run_query_inproc(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_exit2_argparse(self):
        for args in (
            ["casimir", "--geometry", "nope"],                              # bad choice
            ["casimir", "--separation-nm", "abc"],                          # non-numeric
            ["hubble-flow", "--mass-msun", "xyz"],                          # non-numeric
        ):
            rc, _, err = run_query_inproc(*args)
            self.assertEqual(rc, 2, args)
            self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
