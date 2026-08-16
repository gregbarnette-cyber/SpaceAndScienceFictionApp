# tests/test_query_debris.py — CR-1 debris-disk query.py contract.

import unittest

from tests._netcheck import live_enabled, reachable
from tests._queryharness import make_env, run_query

_ENV = make_env("cr1_debris_throwaway.db")
_ONLINE = live_enabled() and reachable("simbad.u-strasbg.fr", 443)


def _run(*cmd_args, **kw):
    return run_query(*cmd_args, env=_ENV, **kw)


class DebrisDiskQueryTest(unittest.TestCase):
    def test_no_target_curated_exit1_offline(self):
        # No --star / --ra-dec → the coord guard fires before any network call.
        rc, d, _ = _run("debris-disk")
        self.assertEqual(rc, 1)
        self.assertIn("error", d)


@unittest.skipUnless(_ONLINE, "SIMBAD/VizieR not reachable / SPACE_APP_RUN_LIVE unset")
class DebrisDiskLiveQueryTest(unittest.TestCase):
    def test_vega_detected(self):
        rc, d, _ = _run("debris-disk", "--star", "Vega", timeout=180)
        self.assertEqual(rc, 0)
        self.assertEqual(d["detection"], "detected")

    def test_disk_free_upper_limit(self):
        rc, d, _ = _run("debris-disk", "--star", "18 Scorpii", timeout=180)
        self.assertEqual(rc, 0)
        self.assertEqual(d["detection"], "upper_limit")
        self.assertIsNotNone(d["upper_limit_L_IR_over_Lstar"])


if __name__ == "__main__":
    unittest.main()
