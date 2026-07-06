# tests/test_query_relativity.py — Phase AF (Group L) query.py contract.
#
# Offline subprocess tests mirroring tests/test_query_active_shield.py: happy-path JSON,
# core parity, and the self-validating exit-code matrix (exit 1 curated / exit 2 argparse),
# plus the --add / --event2 string-parsing wrappers.

import unittest

import core.relativity as relativity

from tests._queryharness import make_env, run_query, run_query_inproc

_ENV = make_env("phase_af_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class RelativityQueryTest(unittest.TestCase):
    def test_time_dilation_parity(self):
        rc, d, _ = _run("time-dilation", "--velocity-c", "0.866", "--proper-time", "1")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["coordinate_time"], 2.0, delta=1e-3)
        ref = relativity.compute_time_dilation(velocity_c=0.866, proper_time=1.0)
        self.assertAlmostEqual(d["gamma"], ref["gamma"], places=9)

    def test_length_velocity_doppler(self):
        self.assertAlmostEqual(_run("length-contraction", "--velocity-c", "0.866",
                                    "--proper-length", "1")[1]["contracted_length"], 0.5, delta=1e-3)
        self.assertAlmostEqual(_run("velocity-addition", "--u-c", "0.75", "--v-c", "0.75")[1]["combined_velocity_c"], 0.96, delta=1e-9)
        self.assertAlmostEqual(_run("relativistic-doppler", "--velocity-c", "0.6", "--approach")[1]["doppler_factor"], 2.0, delta=1e-9)

    def test_rapidity_add_string(self):
        rc, d, _ = _run("rapidity", "--add", "0.6,0.6,0.6")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["composed_velocity_c"], 0.9695, delta=1e-3)

    def test_energy_momentum(self):
        rc, d, _ = _run("relativistic-energy-momentum", "--mass-mev", "938.272", "--velocity-c", "0.99")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["gamma"], 7.089, delta=1e-3)

    def test_lorentz_transform_anchor(self):
        rc, d, _ = _run("lorentz-transform", "--velocity-c", "0.6", "--t-yr", "0", "--x-ly", "1")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["t_prime"], -0.75, delta=1e-9)
        self.assertAlmostEqual(d["x_prime"], 1.25, delta=1e-9)

    def test_lorentz_transform_event2(self):
        # events (0,0) and (0,1) simultaneous in the unprimed frame → Δt' = -γβΔx = -0.75
        rc, d, _ = _run("lorentz-transform", "--velocity-c", "0.6", "--t-yr", "0", "--x-ly", "0",
                        "--event2", "0,1")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["simultaneity_offset"], -0.75, delta=1e-9)

    def test_causality_check(self):
        rc, d, _ = _run("causality-check", "--signal-speed-c", "2", "--frame-velocity-c", "0.6")
        self.assertEqual(rc, 0)
        self.assertTrue(d["loop_possible"])
        self.assertAlmostEqual(d["critical_frame_velocity_c"], 0.5, delta=1e-9)

    def test_exit1_curated(self):
        for args in (
            ["time-dilation"],                                              # nothing
            ["time-dilation", "--velocity-c", "1.0"],                       # β≥1
            ["length-contraction", "--velocity-c", "0.5", "--proper-length", "-1"],
            ["velocity-addition", "--u-c", "1.5", "--v-c", "0.5"],          # β>1
            ["relativistic-doppler", "--velocity-c", "0.6"],               # no direction
            ["rapidity"],                                                   # no source
            ["relativistic-energy-momentum", "--velocity-c", "0.5"],       # no mass
            ["lorentz-transform", "--velocity-c", "0.6", "--t-yr", "0"],    # missing x
            ["causality-check", "--signal-speed-c", "2"],                  # no frame vel
        ):
            rc, d, _ = run_query_inproc(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_exit1_bad_add_string(self):
        rc, d, _ = run_query_inproc("rapidity", "--add", "0.6,foo")
        self.assertEqual(rc, 1)
        self.assertIn("error", d)

    def test_exit2_argparse(self):
        for args in (
            ["velocity-addition", "--u-c", "0.5"],                          # missing required --v-c
            ["time-dilation", "--velocity-c", "abc"],                       # non-numeric
            ["lorentz-transform", "--t-yr", "0", "--x-ly", "1"],            # missing required --velocity-c
        ):
            rc, _, err = run_query_inproc(*args)
            self.assertEqual(rc, 2, args)
            self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
