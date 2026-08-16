# tests/test_query_exoplanet_batch_live.py — CR-8 live anchor for planetary-systems-batch.
#
# Hits the live NASA Exoplanet Archive TAP (`ps` table) + SIMBAD. Opt-in: gated on
# SPACE_APP_RUN_LIVE=1 (tests/_netcheck.live_enabled) AND host reachability, so a routine
# `pytest -q` opens no network socket. Pins CR-8 §5:
#   * §5.1 batch≡single — HD 136352 → b/c/d at incl 88.49/88.571/89.73 citing Delrez et al. 2021,
#     default_flag-scoped, IDENTICAL to `planetary-systems --star "HD 136352"`.
#   * §5.2 meaningful nulls — an RV-only host (tau Ceti / HD 10700) returns inclination null.
#   * §5.3 coverage — an unresolvable designation + a resolvable planet-less star are both flagged.
#
# Gate-adjudication (WB MSG 060): HD 136352 must be identical (ps-default == pscomppars there);
# a *different* host could diverge on a pscomppars back-filled field — that is ps-wins/pass-with-note,
# not tested here (this file only anchors the identical case).

import socket
import unittest

from tests._netcheck import live_enabled
from tests._queryharness import make_env, run_query

_ENV = make_env("cr8_batch_live_throwaway.db")


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
class Cr8BatchLiveTest(unittest.TestCase):

    def test_hd136352_anchor_and_coverage(self):
        rc, out, err = _run("planetary-systems-batch",
                            "--hosts", "HD 136352", "HD 10700", "Vega", "NotAStarXYZ123")
        self.assertEqual(rc, 0, err)
        self.assertEqual(out["mode"], "hosts")
        self.assertEqual(out["solution_scope"], "default")

        cov = out["coverage"]
        self.assertEqual([u["input"] for u in cov["unresolved"]], ["NotAStarXYZ123"])
        self.assertEqual([z["input"] for z in cov["zero_planet"]], ["Vega"])   # resolves, no planets

        hosts = {h["input"]: h for h in out["hosts"]}
        self.assertIn("HD 136352", hosts)

        # §5.1 anchor: b/c/d inclinations + Delrez 2021, default solution.
        planets = {p["name"]: p for p in hosts["HD 136352"]["planets"]}
        anchors = {"HD 136352 b": 88.49, "HD 136352 c": 88.571, "HD 136352 d": 89.73}
        for name, incl in anchors.items():
            self.assertAlmostEqual(planets[name]["inclination_deg"], incl, places=2)
            self.assertEqual(planets[name]["provenance"]["citation"], "Delrez et al. 2021")
            self.assertIs(planets[name]["default_solution"], True)
            self.assertEqual(planets[name]["mass_kind"], "true_mass")

        # §5.2 meaningful null: an RV-only host returns inclination null (not fabricated to 90).
        for p in hosts["HD 10700"]["planets"]:
            self.assertIsNone(p["inclination_deg"])
            self.assertEqual(p["mass_kind"], "msini")

    def test_batch_equals_single_host(self):
        # §5.1 no-degradation: batch value == single-host planetary-systems (pscomppars agrees here).
        rc_b, batch, _ = _run("planetary-systems-batch", "--hosts", "HD 136352")
        rc_s, single, _ = _run("planetary-systems", "--star", "HD 136352")
        self.assertEqual((rc_b, rc_s), (0, 0))
        batch_incl = {p["name"]: p["inclination_deg"]
                      for p in batch["hosts"][0]["planets"]}
        single_incl = {p["pl_name"]: p["pl_orbincl"] for p in single["planets"]}
        for name in ("HD 136352 b", "HD 136352 c", "HD 136352 d"):
            self.assertAlmostEqual(batch_incl[name], single_incl[name], places=3)


if __name__ == "__main__":
    unittest.main()
