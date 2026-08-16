# tests/test_query_nuclear.py — CR-4 nuclear-inventory query.py contract (offline).

import unittest

import core.nuclear as nuclear
from tests._queryharness import make_env, run_query

_ENV = make_env("cr4_nuclear_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class NuclearInventoryQueryTest(unittest.TestCase):
    def test_solar_anchor_and_parity(self):
        rc, d, _ = _run("nuclear-inventory", "--fe-h", "0", "--age-gyr", "4.567", "--eu-h", "0")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["fissile"]["U235_U238_ratio"], 0.00725, delta=1e-4)
        self.assertTrue(3e-12 < d["radiogenic_heat_W_per_kg"] < 8e-12)
        ref = nuclear.compute_nuclear_inventory(fe_h=0.0, age_gyr=4.567, eu_h=0.0)
        self.assertAlmostEqual(d["radiogenic_heat_W_per_kg"],
                               ref["radiogenic_heat_W_per_kg"], places=18)

    def test_no_tracer_note_not_null(self):
        rc, d, _ = _run("nuclear-inventory", "--fe-h", "0", "--age-gyr", "4.567")
        self.assertEqual(rc, 0)
        self.assertIsNone(d["fissile"]["U235_frac"])
        self.assertIn("note", d["fissile"])

    def test_eu_fe_and_eu_h_mutually_exclusive_exit2(self):
        rc, d, _ = _run("nuclear-inventory", "--fe-h", "0", "--age-gyr", "4.567",
                        "--eu-h", "0", "--eu-fe", "0")
        self.assertEqual(rc, 2)          # argparse mutually-exclusive group
        self.assertIsNone(d)

    def test_bad_age_curated_exit1(self):
        rc, d, _ = _run("nuclear-inventory", "--fe-h", "0", "--age-gyr", "-1", "--eu-h", "0")
        self.assertEqual(rc, 1)
        self.assertIn("error", d)


if __name__ == "__main__":
    unittest.main()
