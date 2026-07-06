# tests/test_query_gravitation.py — Phase AE (Group K) query.py contract.
#
# Offline subprocess tests mirroring tests/test_query_active_shield.py: happy-path JSON,
# core parity, and the self-validating exit-code matrix (exit 1 curated / exit 2 argparse).

import unittest

import core.gravitation as gravitation

from tests._queryharness import make_env, run_query, run_query_inproc

_ENV = make_env("phase_ae_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class GravitationQueryTest(unittest.TestCase):
    def test_escape_velocity_happy_and_parity(self):
        rc, d, _ = _run("escape-velocity", "--body", "earth")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["escape_velocity_kms"], 11.19, delta=0.01)
        ref = gravitation.compute_escape_velocity(body="earth")
        self.assertAlmostEqual(d["escape_velocity_kms"], ref["escape_velocity_kms"], places=9)
        self.assertIn("model_note", d)

    def test_potential_happy(self):
        rc, d, _ = _run("gravitational-potential", "--body", "sun", "--r-from-m", "6.957e8")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["well_depth_j_per_kg"], 1.91e11, delta=1e9)

    def test_soi_happy(self):
        rc, d, _ = _run("sphere-of-influence", "--body-mass-mearth", "1",
                        "--primary", "sun", "--semimajor-au", "1")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["soi_laplace_au"], 0.00618, delta=1e-4)

    def test_hyperbolic_happy(self):
        rc, d, _ = _run("hyperbolic-approach", "--body", "earth",
                        "--v-infinity-kms", "3", "--periapsis-km", "6771")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["capture_delta_v_kms"], 3.59, delta=0.02)

    def test_exit1_curated(self):
        for args in (
            ["escape-velocity"],                                              # nothing supplied
            ["escape-velocity", "--body", "earth", "--mass-kg", "1"],         # body + explicit
            ["escape-velocity", "--mass-mearth", "1"],                        # no radius
            ["gravitational-potential", "--body", "earth"],                   # no r-from
            ["sphere-of-influence", "--body-mass-mearth", "1", "--primary", "sun"],  # no sma
            ["hyperbolic-approach", "--body", "earth", "--periapsis-km", "6771"],    # no v mode
            ["hyperbolic-approach", "--body", "earth", "--v-infinity-kms", "3"],     # no periapsis
        ):
            rc, d, _ = run_query_inproc(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_exit2_argparse(self):
        for args in (
            ["escape-velocity", "--body", "nope"],                            # bad preset choice
            ["escape-velocity", "--mass-kg", "abc"],                          # non-numeric
            ["hyperbolic-approach", "--body", "earth", "--target", "hyperbolic",
             "--v-infinity-kms", "3", "--periapsis-km", "6771"],             # bad target choice
        ):
            rc, _, err = run_query_inproc(*args)
            self.assertEqual(rc, 2, args)
            self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
