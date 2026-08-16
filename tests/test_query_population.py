# tests/test_query_population.py — CR-7 population-classify query.py contract (offline).
#
# Subprocess tests mirroring tests/test_query_radiation.py: happy-path JSON, core parity,
# and the self-validating exit-code path (curated {"error"} → exit 1; argparse → exit 2).

import unittest

import core.kinematics as kinematics
from tests._queryharness import make_env, run_query

_ENV = make_env("cr7_population_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class PopulationClassifyQueryTest(unittest.TestCase):
    def test_sun_uvw_thin_and_parity(self):
        rc, d, _ = _run("population-classify", "--u", "0", "--v", "0", "--w", "0")
        self.assertEqual(rc, 0)
        self.assertEqual(d["population"], "thin")
        ref = kinematics.classify_population(u=0.0, v=0.0, w=0.0)
        self.assertAlmostEqual(d["membership_prob"], ref["membership_prob"], places=9)
        self.assertAlmostEqual(d["toomre_velocity_kms"], ref["toomre_velocity_kms"], places=9)

    def test_halo_uvw(self):
        rc, d, _ = _run("population-classify", "--u", "-150", "--v", "-250", "--w", "100")
        self.assertEqual(rc, 0)
        self.assertEqual(d["population"], "halo")

    def test_missing_inputs_curated_error_exit1(self):
        rc, d, _ = _run("population-classify")
        self.assertEqual(rc, 1)
        self.assertIn("error", d)

    def test_non_numeric_argparse_exit2(self):
        rc, d, err = _run("population-classify", "--u", "abc", "--v", "0", "--w", "0")
        self.assertEqual(rc, 2)
        self.assertIsNone(d)


if __name__ == "__main__":
    unittest.main()
