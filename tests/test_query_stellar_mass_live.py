# tests/test_query_stellar_mass_live.py — CR-11.2 live anchors (dossier + compare-stars).
#
# Hits live SIMBAD (+ Gaia FLAME / NASA). Opt-in: gated on SPACE_APP_RUN_LIVE=1
# (tests/_netcheck.live_enabled) AND host reachability, so a routine `pytest -q` opens no socket.
# Anchors from the CR-11.2 contract §Validation: Sirius A (Am, catalog vs inversion-caution),
# Vega (hot-MS caution), α Cen A/B (well-behaved controls), dossier≡compare-stars parity.

import json
import os
import socket
import tempfile
import unittest

from tests._netcheck import live_enabled
from tests._queryharness import make_env, run_query

_ENV = make_env("cr112_mass_live_throwaway.db")


def _reachable(host="simbad.u-strasbg.fr", port=443, timeout=3.0) -> bool:
    if not live_enabled():
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        try:
            with socket.create_connection(("simbad.cds.unistra.fr", 443), timeout=timeout):
                return True
        except OSError:
            return False


def _run(*args):
    return run_query(*args, env=_ENV, timeout=300)


def _mass_block(star, *extra):
    rc, d, err = _run("dossier", "--star", star, "--sections", "regions", "--fmt", "json", *extra)
    assert rc == 0, err
    return d["data"]["regions"]["mass"]


@unittest.skipUnless(_reachable(), "network not reachable (or SPACE_APP_RUN_LIVE unset)")
class Cr112DossierLive(unittest.TestCase):

    def test_sirius_a_catalog_default(self):                    # §Validation 1 (with catalog) + 7
        mb = _mass_block("Sirius A")
        self.assertEqual(mb["mass_provenance"], "catalog")
        self.assertAlmostEqual(mb["mass_solar"], 2.063, places=2)
        self.assertTrue(mb["peculiar_star_flag"])
        self.assertFalse(mb["massL_inversion_caution"])

    def test_sirius_a_inversion_caution_without_measured(self):  # §Validation 1 (no measured mass)
        # An empty catalog REPLACES the seed → the inversion is the source → the ~2.59 over-read, flagged.
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"stars": []}, f)
            path = f.name
        try:
            mb = _mass_block("Sirius A", "--star-mass-catalog", path)
            self.assertEqual(mb["mass_provenance"], "ms_luminosity_inversion")
            self.assertTrue(mb["massL_inversion_caution"])
            self.assertTrue(mb["peculiar_star_flag"])
            self.assertGreater(mb["mass_solar"], 2.3)   # the over-read (~2.59), never null
        finally:
            os.unlink(path)

    def test_alpha_cen_a_well_behaved(self):                    # §Validation 3
        mb = _mass_block("alf Cen A")
        self.assertFalse(mb["massL_inversion_caution"])
        self.assertFalse(mb["peculiar_star_flag"])

    def test_manual_override(self):                             # §Validation 6
        mb = _mass_block("Sirius A", "--mass-solar", "2.063")
        self.assertEqual((mb["mass_provenance"], mb["mass_solar"]), ("manual", 2.063))


@unittest.skipUnless(_reachable(), "network not reachable (or SPACE_APP_RUN_LIVE unset)")
class Cr112ParityLive(unittest.TestCase):

    def test_dossier_equals_compare_stars(self):                # §Validation 5 (parity)
        star = "Sirius A"
        mb = _mass_block(star)
        rc, d, err = _run("compare-stars", "--stars", star, "Sol")
        self.assertEqual(rc, 0, err)
        entry = next(s for s in d["stars"] if s["mass_solar"] is not None
                     and s["mass_provenance"] == mb["mass_provenance"])
        self.assertAlmostEqual(entry["mass_solar"], mb["mass_solar"], places=3)
        self.assertEqual(entry["mass_provenance"], mb["mass_provenance"])


if __name__ == "__main__":
    unittest.main()
