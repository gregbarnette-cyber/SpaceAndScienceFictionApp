# tests/test_query_radiation.py — Phase AS (Packet 34) radiation-ceiling query.py contract.
#
# Offline subprocess tests mirroring tests/test_query_active_shield.py: happy-path JSON,
# core parity, and the self-validating exit-code matrix (exit 1 curated / exit 2 argparse).

import unittest

import core.radiation as radiation

from tests._queryharness import make_env, run_query, run_query_inproc

_ENV = make_env("phase_as_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class RadiationCeilingQueryTest(unittest.TestCase):
    def test_happy_and_parity(self):
        rc, d, _ = _run("radiation-ceiling", "--clade", "baseline-human",
                        "--absorbed-dose-gy", "4", "--let-kev-um", "0.3")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["axis_a_deterministic"]["fraction_of_ceiling"], 1.0667, places=3)
        ref = radiation.compute_radiation_ceiling(clade="baseline-human",
                                                  absorbed_dose_gy=4.0, let_kev_um=0.3)
        self.assertAlmostEqual(d["axis_a_deterministic"]["clade_acute_ceiling_gy"],
                               ref["axis_a_deterministic"]["clade_acute_ceiling_gy"], places=9)

    def test_case2_chronic_policy_anchor(self):
        rc, d, _ = _run("radiation-ceiling", "--profile", "chronic",
                        "--absorbed-dose-gy", "0.6", "--let-kev-um", "0.3")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["axis_b_stochastic"]["reid_percent"], 3.0, places=6)
        self.assertFalse(d["axis_a_deterministic"]["applicable"])

    def test_upload_seu_path_no_gy_sv(self):
        rc, d, _ = _run("radiation-ceiling", "--clade", "upload", "--fluence", "1e10",
                        "--memory-bits", "1e12")
        self.assertEqual(rc, 0)
        self.assertFalse(d["axis_a_deterministic"]["applicable"])
        self.assertFalse(d["axis_b_stochastic"]["applicable"])
        self.assertTrue(d["seu_budget"]["different_physical_quantity"])
        self.assertNotIn("acute_equivalent_dose_gy", d["axis_a_deterministic"])

    def test_let_spectrum_composite(self):
        rc, d, _ = _run("radiation-ceiling", "--let-spectrum", "0.3:1e9, 100:1e7")
        self.assertEqual(rc, 0)
        self.assertEqual(d["exposure"]["source_form"], "let_spectrum")
        self.assertGreater(d["exposure"]["q_effective"], 1.0)

    def test_exit1_curated(self):
        for args in (
            ["radiation-ceiling", "--fluence", "1e8"],                                    # no quality
            ["radiation-ceiling", "--absorbed-dose-gy", "1", "--fluence", "1e8",
             "--let-kev-um", "1"],                                                        # two magnitudes
            ["radiation-ceiling", "--clade", "custom", "--lever", "p53",
             "--lever-m-a", "1.5", "--lever-m-b", "0.7",
             "--absorbed-dose-gy", "4", "--let-kev-um", "0.3"],                           # p53 double-improve
            ["radiation-ceiling", "--clade", "custom", "--lever", "repair-fidelity",
             "--lever-m-a", "2000", "--absorbed-dose-gy", "4", "--let-kev-um", "0.3"],    # >5000 Gy no flag
            ["radiation-ceiling", "--let-spectrum", "junk"],                             # malformed spectrum
        ):
            rc, d, _ = run_query_inproc(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_exit2_argparse(self):
        for args in (
            ["radiation-ceiling", "--clade", "martian",                                   # bad choice
             "--absorbed-dose-gy", "4", "--let-kev-um", "0.3"],
            ["radiation-ceiling", "--absorbed-dose-gy", "abc", "--let-kev-um", "0.3"],    # non-numeric
            ["radiation-ceiling", "--profile", "weekly",                                  # bad choice
             "--absorbed-dose-gy", "4", "--let-kev-um", "0.3"],
        ):
            rc, _, err = run_query_inproc(*args)
            self.assertEqual(rc, 2, args)
            self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
