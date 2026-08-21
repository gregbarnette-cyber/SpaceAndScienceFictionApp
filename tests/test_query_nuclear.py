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

    def test_cq3c1_radiogenic_heat_withheld_without_eu(self):
        # CQ-7-3c-1: no r-process tracer → the heat headline is JSON null, with the detail block.
        rc, d, _ = _run("nuclear-inventory", "--fe-h", "0.3", "--age-gyr", "4.567")
        self.assertEqual(rc, 0)
        self.assertIsNone(d["radiogenic_heat_W_per_kg"])
        self.assertFalse(d["radiogenic_heat"]["computable"])
        self.assertIsNone(d["provenance"]["domain_ok"])   # tri-state: unevaluable

    def test_cq3c2_dv3_ba_eu_and_age_soft_flags(self):
        rc, d, _ = _run("nuclear-inventory", "--fe-h", "0", "--age-gyr", "5", "--eu-h", "0",
                        "--ba-eu", "0.7", "--age-soft")
        self.assertEqual(rc, 0)
        self.assertTrue(d["provenance"]["flags"]["s_process"])
        self.assertTrue(d["provenance"]["flags"]["age_soft"])
        self.assertIn("per_output", d["provenance"])

    def test_cr102_feh_soft_flag_not_void(self):
        # CR-10.2: [Fe/H] > +0.5 flags feh_extrapolation on the heat channel; fissile fraction stays
        # valid; domain_ok not False from [Fe/H] alone.
        rc, d, _ = _run("nuclear-inventory", "--fe-h", "0.60", "--age-gyr", "5", "--eu-fe", "0.2")
        self.assertEqual(rc, 0)
        self.assertTrue(d["provenance"]["per_output"]["feh_extrapolation"])
        self.assertTrue(d["radiogenic_heat"]["provenance"]["feh_extrapolation"])
        self.assertIsNotNone(d["fissile"]["U235_U238_ratio"])
        self.assertNotEqual(d["provenance"]["domain_ok"], False)

    def test_cr102_fraction_parity_045_055(self):
        rc45, a, _ = _run("nuclear-inventory", "--fe-h", "0.45", "--age-gyr", "5", "--eu-h", "0")
        rc55, b, _ = _run("nuclear-inventory", "--fe-h", "0.55", "--age-gyr", "5", "--eu-h", "0")
        self.assertEqual((rc45, rc55), (0, 0))
        self.assertEqual(a["fissile"], b["fissile"])   # [Fe/H]-independent fraction, not voided


if __name__ == "__main__":
    unittest.main()
