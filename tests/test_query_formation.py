# tests/test_query_formation.py — Phase AJ (Group P) query.py contract.
#
# Offline subprocess tests mirroring tests/test_query_gravitation.py: happy-path JSON,
# core parity, and the self-validating exit-code matrix (exit 1 curated / exit 2 argparse).
#
# AJ-1 (disk-model, isolation-mass) here; P3–P6 added in AJ-2.

import unittest

import core.formation as formation

from tests._queryharness import make_env, run_query, run_query_inproc

_ENV = make_env("phase_aj_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class FormationQueryTest(unittest.TestCase):
    def test_disk_model_happy_and_parity(self):
        rc, d, _ = _run("disk-model", "--r-au", "1.0")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["sigma_gas_gcm2"], 1700.0, places=6)
        self.assertAlmostEqual(d["temp_k"], 280.0, places=6)
        self.assertAlmostEqual(d["aspect_ratio_hr"], 0.0334, delta=0.001)
        ref = formation.compute_disk_model(r_au=1.0)
        self.assertAlmostEqual(d["snowline_au"], ref["snowline_au"], places=9)
        self.assertIn("model_note", d)

    def test_disk_model_grid(self):
        rc, d, _ = _run("disk-model", "--r-grid", "1", "30", "4")
        self.assertEqual(rc, 0)
        self.assertEqual(len(d["radii"]), 4)
        self.assertAlmostEqual(d["radii"][-1]["r_au"], 30.0, places=6)

    def test_isolation_mass_happy(self):
        rc, d, _ = _run("isolation-mass", "--sigma-p-gcm2", "10", "--a-au", "5.2")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["isolation_mass_mearth"], 9.27, delta=0.05)
        self.assertEqual(d["convention"], "half-width-C")

    def test_isolation_mass_feeding_zone_b(self):
        rc, d, _ = _run("isolation-mass", "--sigma-p-gcm2", "10", "--a-au", "1",
                        "--feeding-zone-b", "10")
        self.assertEqual(rc, 0)
        self.assertEqual(d["convention"], "full-width-b")

    def test_pebble_isolation_mass_happy(self):
        rc, d, _ = _run("pebble-isolation-mass", "--hr", "0.05")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["pebble_isolation_mass_mearth"], 25.0, delta=0.1)
        rc, d, _ = _run("pebble-isolation-mass", "--hr", "0.05", "--simple")
        self.assertAlmostEqual(d["pebble_isolation_mass_mearth"], 20.0, delta=0.1)
        self.assertEqual(d["mode"], "lambrechts2014")

    def test_gap_opening_mass_happy_and_parity(self):
        rc, d, _ = _run("gap-opening-mass", "--hr", "0.05", "--nu-code", "3.162e-6",
                        "--mstar-msun", "1", "--a-au", "5.2")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["threshold_q"], 4.978e-4, delta=3e-6)
        self.assertAlmostEqual(d["gap_opening_mass_mjup"], 0.52, delta=0.01)
        ref = formation.compute_gap_opening_mass(hr=0.05, nu_code=3.162e-6, mstar_msun=1.0, a_au=5.2)
        self.assertAlmostEqual(d["threshold_q"], ref["threshold_q"], places=12)

    def test_toomre_q_happy(self):
        rc, d, _ = _run("toomre-q", "--sigma-gcm2", "10.346", "--temp-k", "51.12",
                        "--mstar-msun", "1", "--a-au", "30")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["toomre_q"], 23.7, delta=0.5)
        self.assertFalse(d["unstable"])

    def test_critical_core_mass_happy(self):
        rc, d, _ = _run("critical-core-mass")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["critical_core_mass_mearth"], 12.0, places=6)

    def test_exit1_curated(self):
        for args in (
            ["disk-model"],                                                    # no radius
            ["disk-model", "--r-au", "1", "--r-grid", "1", "30", "4"],         # both radius modes
            ["disk-model", "--r-au", "-1"],                                    # negative radius
            ["disk-model", "--r-au", "1", "--feh", "0.1", "--z", "0.02"],      # both metallicity
            ["isolation-mass", "--a-au", "1"],                                 # no sigma
            ["isolation-mass", "--sigma-p-gcm2", "10"],                        # no a
            ["isolation-mass", "--sigma-p-gcm2", "10", "--a-au", "1",
             "--feeding-zone-c", "3", "--feeding-zone-b", "10"],              # both conventions
            ["pebble-isolation-mass"],                                         # no H/r input
            ["pebble-isolation-mass", "--hr", "0.05", "--temp-k", "280"],      # both hr modes
            ["gap-opening-mass", "--hr", "0.05", "--mstar-msun", "1", "--a-au", "5.2"],  # no viscosity
            ["gap-opening-mass", "--hr", "0.05", "--nu-code", "3.162e-6", "--a-au", "5.2"],  # no M★
            ["toomre-q", "--sigma-gcm2", "10", "--mstar-msun", "1", "--a-au", "30"],     # no c_s mode
            ["critical-core-mass", "--mdot-core", "0"],                        # non-positive
        ):
            rc, d, _ = run_query_inproc(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_exit2_argparse(self):
        for args in (
            ["disk-model", "--r-au", "abc"],                 # non-numeric
            ["disk-model", "--r-grid", "1", "30"],           # wrong nargs
            ["isolation-mass", "--sigma-p-gcm2"],            # missing value
            ["gap-opening-mass", "--hr"],                    # missing value
            ["formation-nope"],                              # unknown subcommand
        ):
            rc, _, _ = run_query_inproc(*args)
            self.assertEqual(rc, 2, args)


if __name__ == "__main__":
    unittest.main()
