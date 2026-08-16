# tests/test_query_binary_stability.py — CR-3 binary-stability-auto query.py contract.
#
# The test_sma_au<=0 guard fires BEFORE any network call, so these run offline; the live 36 Oph
# anchor is gated.

import unittest

from tests._netcheck import live_enabled, reachable
from tests._queryharness import make_env, run_query

_ENV = make_env("cr3_binstab_throwaway.db")
_ONLINE = live_enabled() and reachable("simbad.u-strasbg.fr", 443)


def _run(*cmd_args, **kw):
    return run_query(*cmd_args, env=_ENV, **kw)


class BinaryStabilityAutoQueryTest(unittest.TestCase):
    def test_bad_test_sma_curated_exit1_offline(self):
        # The ≤0 guard precedes the network call → curated error, exit 1, no socket.
        rc, d, _ = _run("binary-stability-auto", "--star", "X", "--test-sma-au", "0")
        self.assertEqual(rc, 1)
        self.assertIn("error", d)

    def test_non_numeric_test_sma_argparse_exit2(self):
        rc, d, _ = _run("binary-stability-auto", "--star", "X", "--test-sma-au", "abc")
        self.assertEqual(rc, 2)
        self.assertIsNone(d)


@unittest.skipUnless(_ONLINE, "SIMBAD/VizieR not reachable / SPACE_APP_RUN_LIVE unset")
class BinaryStabilityAutoLiveQueryTest(unittest.TestCase):
    def test_36_oph_subcommand_honest_null_or_card(self):
        # 36 Oph returns an honest null live (no period-bearing orbit reachable); the anchor numbers
        # are pinned offline + by WB's manual byte-match. Accept either correct outcome.
        rc, d, _ = _run("binary-stability-auto", "--star", "36 Ophiuchi", "--test-sma-au", "1.0",
                        timeout=180)
        self.assertEqual(rc, 0)
        if d.get("elements") is None:
            self.assertIsNotNone(d.get("note"))
        else:
            self.assertEqual(d["test_verdict"], "unstable")


if __name__ == "__main__":
    unittest.main()
