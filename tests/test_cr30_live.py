# tests/test_cr30_live.py — CR-30: LIVE anchors (SIMBAD + VizieR II/246 + Gaia), plan §13.6 T13.
#
# Opt-in: gated on SPACE_APP_RUN_LIVE=1 AND SIMBAD reachability (tests/_netcheck). Runs query.py as a subprocess
# with the catalog cache OFF (SPACE_APP_CATALOG_CACHE=0). The offline suite covers the same logic with stubs; these
# pin the live values the contract quotes (re-checked against a fresh read first if a catalog drifts — plan §11).
# `--star-mass-catalog`: $SPACE_APP_WB_MASS_CATALOG, else the sister repo's deliverable if present.

import os
import socket
import unittest

from tests._netcheck import live_enabled
from tests._queryharness import make_env, run_query

_ENV = make_env("cr30_live_throwaway.db", SPACE_APP_CATALOG_CACHE="0", HOME=os.environ.get("HOME", ""))
_WB_CAT = os.environ.get("SPACE_APP_WB_MASS_CATALOG") or (
    "/home/greg/Claude/scifiWorldBuilding-Claude/design-lab/star-system-analysis/deliverables/"
    "stellar-mass-catalog.json")
_HAVE_CAT = os.path.isfile(_WB_CAT)
_G = ("--gaia-timeout", "120")


def _reachable(host="simbad.cds.unistra.fr", port=443, timeout=3.0) -> bool:
    if not live_enabled():
        return False
    for h in (host, "simbad.u-strasbg.fr"):
        try:
            with socket.create_connection((h, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def _ok(*args, env=None):
    rc, d, err = run_query(*args, env=env or _ENV, timeout=600)
    assert rc == 0 and d is not None and "error" not in d, (args, d, err[-400:])
    return d


@unittest.skipUnless(_reachable(), "network not reachable (or SPACE_APP_RUN_LIVE unset)")
class Cr30LuminosityLive(unittest.TestCase):
    def test_proxima_colour_route(self):                                  # CR-30.3 (live check 2026-10-15)
        d = _ok("star-regions", "--star", "Proxima Centauri")
        self.assertAlmostEqual(d["bcLuminosity"], 0.0015721, places=6)
        self.assertNotIn("twomass_status", d)

    def test_forced_failure_marker(self):
        env = make_env("cr30_live_throwaway.db", SPACE_APP_CATALOG_CACHE="0", HOME=os.environ.get("HOME", ""),
                       SPACE_APP_2MASS_FORCE_UNREACHABLE="1")
        d = _ok("star-regions", "--star", "Proxima Centauri", env=env)
        self.assertEqual((d["twomass_status"], d["not_authoritative"], d["bcLuminosity"]), ("unreachable", True, None))


@unittest.skipUnless(_reachable() and _HAVE_CAT, "network not reachable / no WB catalog (or SPACE_APP_RUN_LIVE unset)")
class Cr30MassAndPlacementLive(unittest.TestCase):
    def test_g113_20_mks_route(self):                                     # CR-30.4 (ruling 164)
        d = _ok("exclusion-boundary", "--star", "G 113-20", "--star-mass-catalog", _WB_CAT, "--alpha", "0.4", *_G)
        self.assertEqual(d["mass_provenance"], "ms_mks_relation")
        self.assertAlmostEqual(d["mass_msun"], 0.43888, places=4)

    def test_wolf_359_boundary(self):                                      # CR-30.6 acceptance 10
        d = _ok("exclusion-boundary", "--star", "Wolf 359", "--star-mass-catalog", _WB_CAT, "--alpha", "0.4", *_G)
        self.assertEqual(d["placement"]["status"], "boundary")
        self.assertAlmostEqual(d["r_ex_au"], 19.52, places=2)
        self.assertEqual([round(v, 2) for v in d["placement"]["r_ex_interval_au"]], [16.45, 19.52])

    def test_proxima_standoff_byte_identical(self):                       # §8 byte-identical list
        d = _ok("exclusion-boundary", "--star", "Proxima Centauri", "--star-mass-catalog", _WB_CAT,
                "--alpha", "0.4", *_G)
        self.assertEqual(d["r_ex_au"], 20.482354346604538)

    def test_g44_42_membership_pre_ms(self):                               # CR-30.6 acceptance 9
        d = _ok("exclusion-boundary", "--star", "G 44-42", "--star-mass-catalog", _WB_CAT, "--alpha", "0.4", *_G,
                "--age-lo-gyr", "0.005", "--age-hi-gyr", "0.02", "--age-basis", "membership")
        pl = d["placement"]
        self.assertEqual((pl["pre_ms"], pl["status"], pl["reading"]), (True, "boundary", "le_x"))


@unittest.skipUnless(_reachable(), "network not reachable (or SPACE_APP_RUN_LIVE unset)")
class Cr30ConsumersLive(unittest.TestCase):
    def test_hip_76901_sb1_minimum(self):                                   # CR-30.7 acceptance 1
        d = _ok("binary-orbit", "--star", "HIP 76901")
        sb9 = [s for s in d["solutions"] if s["source"] == "sb9" and (s.get("companion") or {}).get("m2_solar")]
        self.assertTrue(sb9)
        c = sb9[0]["companion"]
        self.assertEqual(c["m1_solar"], 0.184)
        self.assertAlmostEqual(c["m2_solar"], 0.044186, places=5)
        self.assertEqual(c["class"], "undetermined (minimum mass)")

    def test_lhs_288_s1_radius(self):                                      # CR-30.7 acceptance 5
        d = _ok("detection-completeness", "--star", "LHS 288")
        self.assertEqual(d["star_radius_solar"], 0.156)


if __name__ == "__main__":
    unittest.main()
