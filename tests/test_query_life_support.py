# tests/test_query_life_support.py — Phase X life-support query.py contract.
#
# Offline subprocess tests mirroring tests/test_query_spin.py: happy-path JSON shape, core parity
# (subprocess == in-process), and the self-validating exit-code matrix (curated {"error"} -> exit 1;
# argparse -> exit 2). No network / DB / Qt. SPACE_APP_DB throwaway env set for family parity.

import json
import os
import pathlib
import subprocess
import sys
import unittest

import core.life_support as ls

from tests._queryharness import make_env, run_query, run_query_inproc

_REPO = pathlib.Path(__file__).resolve().parent.parent
_ENV = make_env("phase_x_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class HappyPathTest(unittest.TestCase):
    def test_x1_and_parity(self):
        rc, d, _ = _run("life-support", "--crew", "6", "--days", "180")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["per_person_daily"]["o2_kg"], 0.895)
        self.assertAlmostEqual(d["totals"]["food_dry_kg"], 0.800 * 6 * 180)
        self.assertIn("model_note", d)
        ref = ls.compute_life_support(crew=6, days=180)
        self.assertEqual(d["totals"], ref["totals"])

    def test_x1_iss_makeup(self):
        rc, d, _ = _run("life-support", "--closure-scenario", "iss", "--days", "365")
        self.assertEqual(rc, 0)
        self.assertLess(d["makeup_mass_kg"]["water"], 0.2 * d["totals"]["total_water_kg"])

    def test_x2_and_parity(self):
        rc, d, _ = _run("bioregen-area", "--kcal-per-day", "2500", "--crop", "wheat",
                        "--dli-mol", "30", "--artificial")
        self.assertEqual(rc, 0)
        self.assertTrue(30.0 <= d["area_m2_per_person"] <= 50.0)
        self.assertTrue(5000.0 <= d["lighting"]["electrical_power_w_per_person"] <= 15000.0)
        self.assertIn("par_is_input_note", d)
        ref = ls.compute_bioregen_area(kcal_per_day=2500, crop="wheat", dli_mol=30, artificial=True)
        self.assertAlmostEqual(d["area_m2_per_person"], ref["area_m2_per_person"], places=6)

    def test_x2_algae(self):
        rc, d, _ = _run("bioregen-area", "--crop", "chlorella", "--dli-mol", "30")
        self.assertEqual(rc, 0)
        self.assertIsNone(d["photo_efficiency"])
        self.assertIsNotNone(d["crop_gas_exchange"]["o2_kg_day"])

    def test_x2_crops_mix_and_parity(self):
        rc, d, _ = _run("bioregen-area", "--kcal-per-day", "2500",
                        "--crops", "wheat:0.5, white_potato:0.3, soybean:0.2", "--dli-mol", "30")
        self.assertEqual(rc, 0)
        self.assertEqual([c["crop"] for c in d["per_crop_area_m2"]],
                         ["wheat", "white_potato", "soybean"])
        self.assertAlmostEqual(d["area_m2_total"],
                               sum(c["area_m2_total"] for c in d["per_crop_area_m2"]), places=6)
        self.assertIn("linear-programming", d["model_note"])
        ref = ls.compute_bioregen_area(kcal_per_day=2500,
                                       crops="wheat:0.5, white_potato:0.3, soybean:0.2", dli_mol=30)
        self.assertEqual(d, ref)

    def test_x3_and_parity(self):
        rc, d, _ = _run("population-capacity", "--power-w", "1e6", "--per-person-power-w", "1e4")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["sustainable_population"], 100.0)
        self.assertEqual(d["binding_constraint"], "power")

    def test_x3_nitrogen_binding(self):
        rc, d, _ = _run("population-capacity", "--power-w", "1e6", "--per-person-power-w", "1e4",
                        "--fixed-nitrogen-kg-yr", "100")
        self.assertEqual(rc, 0)
        self.assertEqual(d["binding_constraint"], "fixed_nitrogen")


class ExitCodeTest(unittest.TestCase):
    def test_curated_errors_exit_1(self):
        for args in (
            ["life-support", "--crew", "0"],
            ["life-support", "--days", "0"],
            ["life-support", "--water-closure", "1.5"],
            ["bioregen-area", "--dli-mol", "30"],                        # no crop, no HI
            ["bioregen-area", "--crop", "wheat", "--dli-mol", "0"],      # non-positive anchor
            ["bioregen-area", "--crops", "wheat:0.5, soybean:0.6", "--dli-mol", "30"],  # not summing 1
            ["bioregen-area", "--crops", "wheat:0.5, bogus:0.5", "--dli-mol", "30"],    # unknown crop in mix
            ["bioregen-area", "--crops", "nocolon", "--dli-mol", "30"],  # malformed --crops token
            ["bioregen-area", "--crop", "wheat", "--crops", "wheat:1.0", "--dli-mol", "30"],  # both crop+crops
            ["population-capacity"],                                     # no budget
        ):
            rc, d, _ = run_query_inproc(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_argparse_errors_exit_2(self):
        for args in (
            ["life-support", "--closure-scenario", "bogus"],                        # bad choice
            ["life-support", "--crew", "abc"],                                      # non-numeric
            ["bioregen-area", "--crop", "wheat"],                                   # missing light group
            ["bioregen-area", "--crop", "wheat", "--dli-mol", "30", "--ppfd-umol", "500"],  # two anchors
            ["bioregen-area", "--crop", "bogus", "--dli-mol", "30"],                # bad crop choice
            ["bioregen-area", "--crop", "wheat", "--dli-mol", "30", "--star", "Sol"],  # unknown arg
            ["population-capacity", "--power-w", "xyz"],                            # non-numeric
        ):
            rc, _, _ = run_query_inproc(*args)
            self.assertEqual(rc, 2, args)


if __name__ == "__main__":
    unittest.main()
