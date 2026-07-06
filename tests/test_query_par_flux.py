# tests/test_query_par_flux.py — Phase AA par-flux query.py contract.
#
# Offline subprocess tests mirroring tests/test_query_thermal.py: happy-path JSON
# shape, core parity (subprocess == in-process), and the self-validating exit-code
# matrix (curated {"error"} -> exit 1; argparse -> exit 2). The --star SIMBAD
# round-trip is reachability-gated (skips offline).

import json
import os
import pathlib
import subprocess
import sys
import unittest

import core.par_flux as par_flux

from tests._queryharness import make_env, run_query, run_query_inproc

_REPO = pathlib.Path(__file__).resolve().parent.parent
_ENV = make_env("phase_aa_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class HappyPathTest(unittest.TestCase):
    def test_teff_direct_and_parity(self):
        rc, d, _ = _run("par-flux", "--teff-k", "5772", "--insolation-wm2", "1361")
        self.assertEqual(rc, 0)
        self.assertGreaterEqual(d["par_fraction"], 0.36)
        self.assertLessEqual(d["par_fraction"], 0.40)
        self.assertGreater(d["ppfd_umol_m2_s"], 2000.0)
        self.assertAlmostEqual(d["par_deficit_vs_g2"], 1.0, places=3)
        self.assertEqual(d["band_nm"], [400.0, 700.0])
        self.assertIn("blackbody", d["sed_model"].lower())
        self.assertIn("bioregen-area", d["feeds_note"])
        ref = par_flux.compute_par_flux(teff_k=5772, insolation_wm2=1361)
        self.assertAlmostEqual(d["par_fraction"], ref["par_fraction"], places=6)
        self.assertAlmostEqual(d["ppfd_umol_m2_s"], ref["ppfd_umol_m2_s"], places=3)

    def test_luminosity_alias(self):
        # P4.2: --luminosity is an accepted synonym for --luminosity-lsun here.
        rc, d, _ = _run("par-flux", "--teff-k", "5772", "--luminosity", "1", "--distance-au", "1")
        self.assertEqual(rc, 0)
        ref = par_flux.compute_par_flux(teff_k=5772, luminosity_lsun=1, distance_au=1)
        self.assertAlmostEqual(d["par_fraction"], ref["par_fraction"], places=6)

    def test_spectral_type_autoseed(self):
        # The main_sequence_stars table auto-seeds in the throwaway DB.
        rc, d, _ = _run("par-flux", "--spectral-type", "G2V", "--luminosity-lsun", "1",
                        "--distance-au", "1")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["teff_k"], 5770.0, places=1)
        self.assertAlmostEqual(d["insolation_wm2"], 1361.0, delta=2.0)

    def test_m_dwarf_deficit(self):
        rc, d, _ = _run("par-flux", "--teff-k", "2700", "--insolation-wm2", "1361")
        self.assertEqual(rc, 0)
        self.assertGreaterEqual(d["par_deficit_vs_g2"], 6.0)
        self.assertLessEqual(d["par_deficit_vs_g2"], 10.0)

    def test_band_override(self):
        rc, d, _ = _run("par-flux", "--teff-k", "5772", "--insolation-wm2", "1361",
                        "--par-band-nm", "400", "750")
        self.assertEqual(rc, 0)
        self.assertEqual(d["band_nm"], [400.0, 750.0])
        self.assertGreater(d["par_fraction"], 0.40)

    def test_sed_real_and_parity(self):
        # C1: real SED path — 3000 K real f_PAR well below the blackbody value
        rc, d, _ = _run("par-flux", "--teff-k", "3000", "--insolation-wm2", "1361", "--sed", "real")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["par_fraction"], 0.0228, places=4)
        self.assertIn("BT-Settl", d["sed_model"])
        ref = par_flux.compute_par_flux(teff_k=3000, insolation_wm2=1361, sed="real")
        self.assertEqual(d, ref)

    def test_sed_blackbody_is_default(self):
        bare, _, _ = _run("par-flux", "--teff-k", "3000", "--insolation-wm2", "1361")
        expl, _, _ = _run("par-flux", "--teff-k", "3000", "--insolation-wm2", "1361",
                          "--sed", "blackbody")
        self.assertEqual(bare, 0)
        self.assertEqual(expl, 0)


class ExitCodeMatrixTest(unittest.TestCase):
    def test_exit1_curated(self):
        for args in (
            ("par-flux", "--teff-k", "0", "--insolation-wm2", "1361"),
            ("par-flux", "--teff-k", "5772", "--spectral-type", "G2V", "--insolation-wm2", "1361"),
            ("par-flux", "--teff-k", "5772"),                                    # no insolation
            ("par-flux", "--insolation-wm2", "1361"),                            # no Teff
            ("par-flux", "--teff-k", "5772", "--luminosity-lsun", "1", "--distance-au", "0"),
            ("par-flux", "--teff-k", "5772", "--insolation-wm2", "1361", "--par-band-nm", "700", "400"),
            # C1: --sed real with a non-default band (band-fixed table) / off-grid Teff
            ("par-flux", "--teff-k", "3000", "--insolation-wm2", "1361", "--sed", "real",
             "--par-band-nm", "400", "750"),
            ("par-flux", "--teff-k", "2000", "--insolation-wm2", "1361", "--sed", "real"),
        ):
            rc, d, _ = run_query_inproc(*args)
            self.assertEqual(rc, 1, msg=f"{args}")
            self.assertIn("error", d)

    def test_exit2_argparse(self):
        for args in (
            ("par-flux", "--teff-k", "abc", "--insolation-wm2", "1361"),         # non-numeric
            ("par-flux", "--teff-k", "5772", "--insolation-wm2", "1361", "--par-band-nm", "400"),  # 1 band num
            ("par-flux", "--teff-k", "3000", "--insolation-wm2", "1361", "--sed", "bogus"),  # bad --sed choice
        ):
            rc, d, _ = run_query_inproc(*args)
            self.assertEqual(rc, 2, msg=f"{args}")
            self.assertIsNone(d)


@unittest.skipUnless(
    os.environ.get("RUN_NETWORK_TESTS") == "1",
    "network test — set RUN_NETWORK_TESTS=1 to run the SIMBAD --star round-trip",
)
class StarPathLiveTest(unittest.TestCase):
    def test_star_resolves(self):
        rc, d, _ = _run("par-flux", "--star", "Tau Ceti", "--insolation-wm2", "1361")
        self.assertEqual(rc, 0)
        self.assertGreater(d["teff_k"], 0)


if __name__ == "__main__":
    unittest.main()
