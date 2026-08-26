# tests/test_query_exclusion_system_live.py — CR-11.3 live --star anchor (Sirius).
#
# Hits live SIMBAD + binary-orbit. Opt-in: gated on SPACE_APP_RUN_LIVE=1 AND host reachability.
# The Sirius WD-guard behavior is the key live anchor: A resolves main-sequence off its catalog
# mass, B is auto-detected out-of-domain (white dwarf) and contributes no sphere, and the two merge
# into one A-dominated zone whose barycenter still uses B's real mass. Exact long-axis numbers track
# the LIVE binary-orbit elements (which differ from the card's a=19.8/e=0.59); the α Cen + Proxima
# triple needs the --component path (no catalogued Proxima orbit) and is covered offline.

import socket
import unittest

from tests._netcheck import live_enabled
from tests._queryharness import make_env, run_query

_ENV = make_env("cr113_excl_live_throwaway.db")


def _reachable(host="simbad.u-strasbg.fr", port=443, timeout=3.0) -> bool:
    if not live_enabled():
        return False
    for h in (host, "simbad.cds.unistra.fr"):
        try:
            with socket.create_connection((h, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def _run(*args):
    return run_query(*args, env=_ENV, timeout=300)


@unittest.skipUnless(_reachable(), "network not reachable (or SPACE_APP_RUN_LIVE unset)")
class Cr113StarSiriusLive(unittest.TestCase):

    def test_sirius_wd_guard_merged(self):
        rc, d, err = _run("exclusion-system", "--star", "Sirius")
        self.assertEqual(rc, 0, err)
        self.assertEqual(d["n_zones"], 1)
        z = d["zones"][0]
        self.assertEqual(z["status"], "merged")
        self.assertEqual(len(z["members"]), 2)
        domains = {c["domain"] for c in z["components"]}
        self.assertEqual(domains, {"main_sequence", "out_of_domain"})   # A MS, B WD-guarded
        wd = next(c for c in z["components"] if c["domain"] == "out_of_domain")
        self.assertIsNone(wd["r_ex_au"])                                # sphere withheld
        ms = next(c for c in z["components"] if c["domain"] == "main_sequence")
        self.assertGreater(ms["r_ex_au"], 55.0)                         # A's sphere (measured ~2.06 M☉)
        # the zone is larger than any single component and breathes
        self.assertGreater(z["long_axis_au"]["apastron"], ms["r_ex_au"])


if __name__ == "__main__":
    unittest.main()
