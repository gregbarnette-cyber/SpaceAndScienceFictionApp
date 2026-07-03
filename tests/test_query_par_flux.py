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

_REPO = pathlib.Path(__file__).resolve().parent.parent
_ENV = {"SPACE_APP_DB": "/tmp/phase_aa_throwaway.db", "PATH": os.environ.get("PATH", "")}


def _run(*cmd_args):
    proc = subprocess.run(
        [sys.executable, str(_REPO / "query.py"), *cmd_args],
        capture_output=True, text=True, cwd=str(_REPO), env=_ENV,
    )
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        payload = None
    return proc.returncode, payload, proc.stderr


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


class ExitCodeMatrixTest(unittest.TestCase):
    def test_exit1_curated(self):
        for args in (
            ("par-flux", "--teff-k", "0", "--insolation-wm2", "1361"),
            ("par-flux", "--teff-k", "5772", "--spectral-type", "G2V", "--insolation-wm2", "1361"),
            ("par-flux", "--teff-k", "5772"),                                    # no insolation
            ("par-flux", "--insolation-wm2", "1361"),                            # no Teff
            ("par-flux", "--teff-k", "5772", "--luminosity-lsun", "1", "--distance-au", "0"),
            ("par-flux", "--teff-k", "5772", "--insolation-wm2", "1361", "--par-band-nm", "700", "400"),
        ):
            rc, d, _ = _run(*args)
            self.assertEqual(rc, 1, msg=f"{args}")
            self.assertIn("error", d)

    def test_exit2_argparse(self):
        for args in (
            ("par-flux", "--teff-k", "abc", "--insolation-wm2", "1361"),         # non-numeric
            ("par-flux", "--teff-k", "5772", "--insolation-wm2", "1361", "--par-band-nm", "400"),  # 1 band num
        ):
            rc, d, _ = _run(*args)
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
