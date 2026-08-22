# tests/test_query_dossier_live.py — CR-10.5 live anchors for the `dossier` robustness bundle.
#
# Hits live SIMBAD + Gaia + NASA + VizieR. Opt-in: gated on SPACE_APP_RUN_LIVE=1
# (tests/_netcheck.live_enabled) AND host reachability, so a routine `pytest -q` opens no socket.
# Part 1 (luminosity-class region guard): Polaris/Betelgeuse refused-inverted (L_bol null via FLAME),
# Pollux token-boundary III. Part 2 (multiplicity cross-check): Spica's SB9 orbit caught despite a
# variability otype. The FLAME-covered >2× consistency anchor is Cr105ConsistencyAnchor below.

import socket
import unittest

from tests._netcheck import live_enabled
from tests._queryharness import make_env, run_query

_ENV = make_env("cr105_dossier_live_throwaway.db")


def _reachable(host="exoplanetarchive.ipac.caltech.edu", port=443, timeout=3.0) -> bool:
    if not live_enabled():
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _run(*args):
    return run_query(*args, env=_ENV, timeout=300)


@unittest.skipUnless(_reachable(), "network not reachable (or SPACE_APP_RUN_LIVE unset)")
class Cr105Part1EvolvedGuardLive(unittest.TestCase):

    def _regions(self, star):
        rc, d, err = _run("dossier", "--star", star, "--sections", "regions", "--fmt", "json")
        self.assertEqual(rc, 0, err)
        return d["data"].get("regions", {})

    def test_polaris_supergiant_refused(self):                 # validation #1
        reg = self._regions("Polaris")
        self.assertTrue(reg.get("evolved_star_flag"))
        self.assertTrue(reg.get("ms_inversion_withheld"))
        self.assertIn("I", reg.get("luminosity_class") or "")   # a class-I supergiant token
        # FLAME does not cover this saturated supergiant → L_bol null, no fabricated ratio (#4-iii)
        self.assertIsNone(reg["luminosity_consistency"]["L_bol"])

    def test_betelgeuse_supergiant_refused(self):              # validation #1 + #4-iii
        reg = self._regions("Betelgeuse")
        self.assertTrue(reg.get("evolved_star_flag"))
        self.assertTrue(reg.get("ms_inversion_withheld"))

    def test_pollux_giant_token_boundary(self):                # validation #2
        reg = self._regions("Pollux")
        self.assertEqual(reg.get("luminosity_class"), "III")   # not Ib
        self.assertTrue(reg.get("evolved_star_flag"))

    def test_ms_dwarf_no_regression(self):                     # validation #3
        reg = self._regions("HD 20794")
        self.assertFalse(reg.get("evolved_star_flag"))
        self.assertIn("stellar", reg)                          # real MS region values present


@unittest.skipUnless(_reachable(), "network not reachable (or SPACE_APP_RUN_LIVE unset)")
class Cr105Part2MultiplicityLive(unittest.TestCase):

    def test_spica_variability_primary_sb_caught(self):        # validation #5
        rc, d, err = _run("dossier", "--star", "HD 116658", "--sections", "multiplicity", "--fmt", "json")
        self.assertEqual(rc, 0, err)
        mp = d["data"]["multiplicity"]
        self.assertTrue(mp["is_multiple"] and mp["sb_flag"])
        self.assertTrue(mp.get("multiplicity_basis"))          # names the SB9 orbit (~4.01 d)

    def test_single_star_no_regression(self):                  # validation #6
        rc, d, err = _run("dossier", "--star", "HD 20794", "--sections", "multiplicity", "--fmt", "json")
        self.assertEqual(rc, 0, err)
        self.assertFalse(d["data"]["multiplicity"]["is_multiple"])


@unittest.skipUnless(_reachable(), "network not reachable (or SPACE_APP_RUN_LIVE unset)")
class Cr105ConsistencyAnchorLive(unittest.TestCase):
    """CR-10.5 Part 1 validation #4-i (Q3-amended): the APP-named FLAME-covered anchor.

    HD 185351 (G8.5 III/IV asteroseismic subgiant-giant) IS covered by Gaia FLAME (L_bol ≈ 14.8 L☉),
    and its MS-inversion calc_L (≈1.16 L☉) disagrees with L_bol by >2× (ratio ≈ 0.08), so the
    luminosity_consistency flag fires — the diagnostic's real protective case (an evolved star FLAME
    genuinely covers), distinct from Polaris/Betelgeuse where FLAME is null (#4-iii)."""

    def test_hd185351_consistency_flag_trips(self):
        rc, d, err = _run("dossier", "--star", "HD 185351", "--sections", "regions", "--fmt", "json")
        self.assertEqual(rc, 0, err)
        lc = d["data"]["regions"]["luminosity_consistency"]
        self.assertIsNotNone(lc["L_bol"])          # FLAME covers it
        self.assertTrue(lc["flagged"])             # calc_L vs L_bol > 2×
        self.assertTrue(d["data"]["regions"]["evolved_star_flag"])


if __name__ == "__main__":
    unittest.main()
