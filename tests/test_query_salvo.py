# tests/test_query_salvo.py — Phase AT (Packet 38.1) salvo-exchange query.py contract.
#
# Offline subprocess tests: happy-path JSON + core parity + the self-validating exit-code matrix
# (exit 1 curated / exit 2 argparse). Mirrors tests/test_query_radiation.py.

import unittest

import core.salvo as salvo

from tests._queryharness import make_env, run_query, run_query_inproc

_ENV = make_env("phase_at_salvo_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class SalvoExchangeQueryTest(unittest.TestCase):
    def test_v1_happy_and_parity(self):
        rc, d, _ = _run("salvo-exchange", "--a-force", "10", "--b-force", "10",
                        "--alpha", "3", "--beta", "3", "--a1-staying", "2", "--b1-staying", "2",
                        "--a3-defense", "2", "--b3-defense", "2")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["delta_a"], 5.0)
        self.assertAlmostEqual(d["delta_b"], 5.0)
        ref = salvo.compute_salvo_exchange(a_force=10, b_force=10, alpha=3, beta=3,
                                           a1_staying=2, b1_staying=2, a3_defense=2, b3_defense=2)
        self.assertAlmostEqual(d["delta_a"], ref["delta_a"], places=9)

    def test_solve_force(self):
        rc, d, _ = _run("salvo-exchange", "--mode", "solve-force", "--a-force", "7",
                        "--a1-staying", "1", "--b1-staying", "1", "--a3-defense", "1",
                        "--beta", "3.88", "--alpha", "1", "--solve-for", "b",
                        "--target-delta", "7", "--target-side", "a")
        self.assertEqual(rc, 0)
        self.assertEqual(d["integer_wave"], 4)

    def test_layered_defense(self):
        rc, d, _ = _run("salvo-exchange", "--mode", "layered-defense", "--inbound-salvo", "100",
                        "--rings", "1:30:0.1, 1:30:0.1, 1:30:0.1")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["survivors_to_target"], 10.0)

    def test_resolved_inputs_echo(self):
        rc, d, _ = _run("salvo-exchange", "--a-force", "10", "--b-force", "10", "--alpha", "3",
                        "--beta", "3", "--a1-staying", "2", "--b1-staying", "2")
        self.assertEqual(rc, 0)
        self.assertIn("resolved_inputs", d)          # R3 transparency
        self.assertEqual(d["resolved_inputs"]["sigma_a"], 1.0)

    def test_exit1_curated(self):
        for args in (
            ["salvo-exchange", "--mode", "simultaneous", "--a-force", "10", "--b-force", "10",
             "--alpha", "3"],                                                     # no staying
            ["salvo-exchange", "--a-force", "1", "--b-force", "1", "--alpha", "3",
             "--a-salvo", "6", "--a-hitprob", "0.5", "--beta", "1",
             "--a1-staying", "1", "--b1-staying", "1"],                           # both striking forms
            ["salvo-exchange", "--mode", "layered-defense", "--inbound-salvo", "100",
             "--rings", "junk"],                                                  # malformed rings
        ):
            rc, d, _ = run_query_inproc(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_exit2_argparse(self):
        for args in (
            ["salvo-exchange", "--mode", "nuke", "--a-force", "10", "--b-force", "10"],  # bad choice
            ["salvo-exchange", "--a-force", "abc", "--b-force", "10"],                   # non-numeric
        ):
            rc, _, err = run_query_inproc(*args)
            self.assertEqual(rc, 2, args)
            self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
