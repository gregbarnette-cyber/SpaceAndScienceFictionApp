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


class SalvoDoctrineCrQueryTest(unittest.TestCase):
    """Packet 38.2 CR-A saturation-stream + CR-B light-lag query.py contract."""

    def test_saturation_stream_happy_and_parity(self):
        rc, d, _ = _run("salvo-exchange", "--mode", "saturation-stream", "--stream-total", "400",
                        "--dwell-intervals", "4", "--stream-rings", "20:20:0")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["cumulative_leak"], 320.0)
        self.assertAlmostEqual(d["equivalent_pulse_leak"], 380.0)
        self.assertAlmostEqual(d["duration_advantage"], 60.0)
        ref = salvo.compute_salvo_exchange(mode="saturation-stream", stream_total=400,
                                           dwell_intervals=4, stream_rings="20:20:0")
        self.assertAlmostEqual(d["cumulative_leak"], ref["cumulative_leak"], places=9)

    def test_light_lag_force_keys(self):
        rc, d, _ = _run("salvo-exchange", "--mode", "simultaneous", "--a-force", "10", "--b-force", "10",
                        "--alpha", "3", "--beta", "3", "--a1-staying", "2", "--b1-staying", "2",
                        "--a3-defense", "2", "--b3-defense", "2", "--light-lag", "on",
                        "--range-a-m", "1e6", "--range-b-m", "1e9")
        self.assertEqual(rc, 0)
        for k in ("sigma_effective", "delta_effective", "tau_s", "light_travel_time_s",
                  "first_mover_advantage"):
            self.assertIn(k, d)
        self.assertIn("light_lag", d["resolved_inputs"])          # R3 echo of the CR-B flags

    def test_light_lag_off_is_clean(self):
        rc, d, _ = _run("salvo-exchange", "--mode", "simultaneous", "--a-force", "10", "--b-force", "10",
                        "--alpha", "3", "--beta", "3", "--a1-staying", "2", "--b1-staying", "2")
        self.assertEqual(rc, 0)
        self.assertNotIn("sigma_effective", d)                    # off → byte-identical
        self.assertNotIn("light_lag", d["resolved_inputs"])

    def test_cr_ab_exit1_curated(self):
        for args in (
            ["salvo-exchange", "--mode", "saturation-stream", "--stream-total", "400",
             "--stream-rings", "20:20:0"],                                             # missing dwell
            ["salvo-exchange", "--mode", "saturation-stream", "--arrival-rate", "100",
             "--stream-total", "400", "--dwell-intervals", "4", "--stream-rings", "20:20:0"],  # both forms
            ["salvo-exchange", "--mode", "break-even", "--a-force", "1", "--b-force", "1",
             "--alpha", "2", "--beta", "1", "--a1-staying", "2", "--b1-staying", "1",
             "--a3-defense", "2", "--b3-defense", "1", "--light-lag", "on", "--range-m", "1e8"],  # rejected mode
            ["salvo-exchange", "--mode", "simultaneous", "--a-force", "10", "--b-force", "10",
             "--alpha", "3", "--beta", "3", "--a1-staying", "2", "--b1-staying", "2",
             "--light-lag", "on"],                                                     # light-lag, no range
        ):
            rc, d, _ = run_query_inproc(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_cr_ab_exit2_argparse(self):
        for args in (
            ["salvo-exchange", "--mode", "saturation-stream", "--profile", "bogus",
             "--stream-total", "400", "--dwell-intervals", "4", "--stream-rings", "20:20:0"],  # bad choice
            ["salvo-exchange", "--mode", "simultaneous", "--light-lag", "maybe"],      # bad --light-lag choice
        ):
            rc, _, err = run_query_inproc(*args)
            self.assertEqual(rc, 2, args)
            self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
