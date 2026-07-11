# tests/test_query_warp.py — Phase AH (Group N) query.py contract.
#
# AH·1 checkpoint: N1 alcubierre-energy ('original' only). Offline subprocess tests mirroring
# tests/test_query_active_shield.py: happy-path JSON, core parity, and the exit-code matrix.

import unittest

import core.warp as warp

from tests._queryharness import make_env, run_query, run_query_inproc

_ENV = make_env("phase_ah_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class AlcubierreQueryTest(unittest.TestCase):
    def test_anchor_and_parity(self):
        rc, d, _ = _run("alcubierre-energy", "--bubble-radius-m", "100",
                        "--velocity-c", "1", "--wall-thickness-m", "10")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["energy_j"], -3.373e45, delta=2e42)          # joules
        self.assertAlmostEqual(d["energy_kg_equiv"], -3.753e28, delta=2e25)   # E/c²
        ref = warp.compute_alcubierre_energy(bubble_radius_m=100, velocity_c=1.0, wall_thickness_m=10)
        self.assertEqual(d["energy_j"], ref["energy_j"])
        self.assertEqual(d["energy_kg_equiv"], ref["energy_kg_equiv"])
        self.assertEqual(d["energy_condition_status"], "NEC-violating-exotic")

    def test_exit1_curated(self):
        for args in (
            ["alcubierre-energy", "--velocity-c", "1", "--wall-thickness-m", "10"],   # no radius
            ["alcubierre-energy", "--bubble-radius-m", "100", "--wall-thickness-m", "10"],  # no velocity
            ["alcubierre-energy", "--bubble-radius-m", "100", "--velocity-c", "1"],   # no wall
            ["alcubierre-energy", "--bubble-radius-m", "-1", "--velocity-c", "1", "--wall-thickness-m", "10"],
        ):
            rc, d, _ = run_query_inproc(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_reduction_formulation(self):
        rc, d, _ = _run("alcubierre-energy", "--bubble-radius-m", "10", "--velocity-c", "10",
                        "--wall-thickness-m", "1", "--formulation", "white")
        self.assertEqual(rc, 0)
        self.assertEqual(d["energy_condition_status"], "NEC-violating-exotic")
        self.assertIsNone(d["energy_j"])
        self.assertTrue(d["published_figure"])
        self.assertTrue(d["contested"])
        # subluminal positive-energy framework
        rc2, d2, _ = _run("alcubierre-energy", "--bubble-radius-m", "100", "--velocity-c", "0.5",
                          "--wall-thickness-m", "10", "--formulation", "bobrick-martire")
        self.assertEqual(d2["energy_condition_status"], "positive-energy-possible")

    def test_warp_metric(self):
        rc, d, _ = _run("warp-metric", "--bubble-radius-m", "100", "--wall-thickness-sigma", "0.1",
                        "--velocity-c", "1", "--r-eval-m", "0")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["f_at_r"], 1.0, places=6)
        ref = warp.compute_warp_metric(bubble_radius_m=100, wall_thickness_sigma=0.1, velocity_c=1, r_eval_m=0)
        self.assertEqual(d["wall_outer_m"], ref["wall_outer_m"])
        nat = _run("warp-metric", "--bubble-radius-m", "100", "--wall-thickness-sigma", "0.1",
                   "--velocity-c", "1", "--r-eval-m", "100", "--variant", "natario")[1]
        self.assertEqual(nat["theta_at_r"], 0.0)

    def test_warp_metric_errors(self):
        rc, d, _ = run_query_inproc("warp-metric", "--wall-thickness-sigma", "0.1", "--velocity-c", "1")
        self.assertEqual(rc, 1)                                          # no radius → curated
        self.assertIn("error", d)

    def test_exit2_argparse(self):
        for args in (
            # an unknown --formulation choice → argparse exit 2 (not a curated error)
            ["alcubierre-energy", "--bubble-radius-m", "100", "--velocity-c", "1",
             "--wall-thickness-m", "10", "--formulation", "banana"],
            ["alcubierre-energy", "--bubble-radius-m", "abc", "--velocity-c", "1", "--wall-thickness-m", "10"],
            ["warp-metric", "--bubble-radius-m", "100", "--wall-thickness-sigma", "0.1",
             "--velocity-c", "1", "--variant", "golden"],   # bad variant choice
        ):
            rc, _, err = run_query_inproc(*args)
            self.assertEqual(rc, 2, args)
            self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
