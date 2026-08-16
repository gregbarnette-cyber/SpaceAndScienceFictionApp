# tests/test_query_multiplicity.py — CR-2 multiplicity query.py contract.
#
# The "requires an identifier" guard precedes any network call, so it runs offline; the live
# anchor is gated.

import unittest

from tests._netcheck import live_enabled, reachable
from tests._queryharness import make_env, run_query

_ENV = make_env("cr2_multiplicity_throwaway.db")
_ONLINE = live_enabled() and reachable("simbad.u-strasbg.fr", 443)


def _run(*cmd_args, **kw):
    return run_query(*cmd_args, env=_ENV, **kw)


class MultiplicityQueryTest(unittest.TestCase):
    def test_no_identifier_curated_exit1_offline(self):
        rc, d, _ = _run("multiplicity")
        self.assertEqual(rc, 1)
        self.assertIn("error", d)


@unittest.skipUnless(_ONLINE, "SIMBAD not reachable / SPACE_APP_RUN_LIVE unset")
class MultiplicityLiveQueryTest(unittest.TestCase):
    def test_alpha_cen_subcommand(self):
        rc, d, _ = _run("multiplicity", "--star", "alpha Centauri", timeout=180)
        self.assertEqual(rc, 0)
        self.assertTrue(d["is_multiple"])


if __name__ == "__main__":
    unittest.main()
