# tests/test_query_detection_live.py — CR-10.4 live anchor for detection-completeness archive M★.
#
# Hits the live NASA Exoplanet Archive TAP (`ps`) + SIMBAD. Opt-in: gated on SPACE_APP_RUN_LIVE=1
# (tests/_netcheck.live_enabled) AND host reachability, so a routine `pytest -q` opens no socket.
# Pins CR-10.4 §5: detection-completeness --star "HD 69830" reports star_mass_solar = 0.86
# (star_mass_provenance="archive"), EQUAL to what planetary-systems-batch reports (self-consistency,
# WB Q5) — read through the same ps + default_flag=1 aggregation, never hard-coded.

import socket
import unittest

from tests._netcheck import live_enabled
from tests._queryharness import make_env, run_query

_ENV = make_env("cr10_detection_live_throwaway.db")


def _archive_reachable(host="exoplanetarchive.ipac.caltech.edu", port=443, timeout=3.0) -> bool:
    if not live_enabled():
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _run(*args):
    return run_query(*args, env=_ENV, timeout=240)


@unittest.skipUnless(_archive_reachable(),
                     "NASA Exoplanet Archive not reachable (or SPACE_APP_RUN_LIVE unset)")
class Cr104ArchiveMassLiveTest(unittest.TestCase):

    def test_hd69830_archive_mass_matches_batch(self):
        rc, det, err = _run("detection-completeness", "--star", "HD 69830", "--methods", "rv")
        self.assertEqual(rc, 0, err)
        self.assertEqual(det["star_mass_provenance"], "archive")
        self.assertAlmostEqual(det["star_mass_solar"], 0.86, places=2)

        # self-consistency with planetary-systems-batch (same ps + default_flag=1 aggregation).
        rc_b, batch, err_b = _run("planetary-systems-batch", "--hosts", "HD 69830", "--fields", "core")
        self.assertEqual(rc_b, 0, err_b)
        self.assertAlmostEqual(det["star_mass_solar"], batch["hosts"][0]["mass_solar"], places=6)

    def test_no_archive_star_falls_back_to_sp_type_estimate(self):
        # A star SIMBAD resolves with a sp-type but that the NASA ps table does not carry (not a planet
        # host) → the generic sp_type→mass estimate, no regression.
        rc, det, err = _run("detection-completeness", "--star", "18 Sco", "--methods", "rv")
        self.assertEqual(rc, 0, err)
        self.assertEqual(det["star_mass_provenance"], "sp_type_estimate")


@unittest.skipUnless(_archive_reachable(),
                     "SIMBAD/NASA not reachable (or SPACE_APP_RUN_LIVE unset)")
class Cr103RvCatalogLiveTest(unittest.TestCase):
    """CR-10.3 §5: HD 69830 (in the internal seed at 0.81 m/s) → the tier-2 catalog floor, resolved
    live via SIMBAD (main_id/aliases match). A star not in the catalog → generic-3a (no regression)."""

    def test_hd69830_catalog_floor(self):
        rc, det, err = _run("detection-completeness", "--star", "HD 69830", "--methods", "rv")
        self.assertEqual(rc, 0, err)
        rv = [m for m in det["methods"] if m["method"] == "rv"][0]
        self.assertEqual(rv["floor_provenance"], "catalog")
        self.assertIn("Lovis 2006", rv["floor_source"])

    def test_non_catalog_star_generic_3a(self):
        rc, det, err = _run("detection-completeness", "--star", "18 Sco", "--methods", "rv")
        self.assertEqual(rc, 0, err)
        rv = [m for m in det["methods"] if m["method"] == "rv"][0]
        self.assertEqual(rv["floor_provenance"], "generic-3a")

    def test_manual_supersedes_catalog(self):
        rc, det, err = _run("detection-completeness", "--star", "HD 69830", "--methods", "rv",
                            "--rv-precision-ms", "0.5")
        self.assertEqual(rc, 0, err)
        rv = [m for m in det["methods"] if m["method"] == "rv"][0]
        self.assertEqual(rv["floor_provenance"], "manual")


if __name__ == "__main__":
    unittest.main()
