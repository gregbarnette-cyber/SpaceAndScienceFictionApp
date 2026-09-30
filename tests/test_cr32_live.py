# tests/test_cr32_live.py — CR-32 acceptance 1–3, live (opt-in: SPACE_APP_RUN_LIVE=1 + ESA Gaia reachable).
#
# A forced Gaia timeout (--gaia-timeout 0.001 / SPACE_APP_GAIA_TIMEOUT=0.001) during the archive-client build must
# leave the JSON — with its top-level gaia_status "timeout" — on stdout; a reachable run's stdout parses with no
# preamble (the ESA banner stays on stderr).

import json
import unittest

from tests._netcheck import esa_gaia_reachable, live_enabled
from tests._queryharness import make_env, run_query

_ENV = make_env("cr32_live_throwaway.db", SPACE_APP_CATALOG_CACHE="0")


def _live():
    return live_enabled() and esa_gaia_reachable()


@unittest.skipUnless(_live(), "live Gaia (set SPACE_APP_RUN_LIVE=1)")
class Cr32LiveTest(unittest.TestCase):

    def _stdout_json(self, *args, env=None):
        code, payload, err = run_query(*args, env=env or _ENV, timeout=600)
        self.assertEqual(code, 0, err[-2000:])
        self.assertIsNotNone(payload, "stdout did not parse as JSON")
        return payload, err

    def test_forced_timeout_keeps_json_on_stdout(self):
        for star in ("Ross 128", "Lacaille 9352"):
            with self.subTest(star=star):
                p, err = self._stdout_json("exclusion-system", "--star", star, "--alpha", "0.4",
                                           "--gaia-timeout", "0.001")
                self.assertEqual(p.get("gaia_status"), "timeout")
                self.assertNotIn('"gaia_status"', err)

    def test_forced_timeout_env_form(self):
        env = dict(_ENV, SPACE_APP_GAIA_TIMEOUT="0.001")
        p, _ = self._stdout_json("multiplicity", "--star", "Ross 128", env=env)
        self.assertIn("gaia_status", json.dumps(p))

    def test_forced_timeout_every_gateway_subcommand(self):
        """CR-32 acc 2 (Q10 enumeration): each Gaia-reaching subcommand keeps its JSON on stdout under a forced
        timeout (--gaia-timeout where the subcommand takes it, else SPACE_APP_GAIA_TIMEOUT)."""
        env = dict(_ENV, SPACE_APP_GAIA_TIMEOUT="0.001")
        cases = [("exclusion-boundary", "--star", "Ross 128", "--alpha", "0.4"),
                 ("dossier", "--star", "Ross 128", "--fmt", "json"),
                 ("compare-stars", "--stars", "Ross 128", "Wolf 359"),
                 ("binary-orbit", "--star", "alpha Centauri"),
                 ("binary-stability-auto", "--star", "alpha Centauri"),
                 ("multiplicity", "--star", "Ross 128"),
                 ("gaia-tap", "--adql", "SELECT TOP 1 source_id FROM gaiadr3.gaia_source"),
                 ("gaia-astrophysical", "--star", "Ross 128")]
        for args in cases:
            with self.subTest(cmd=args[0]):
                code, payload, err = run_query(*args, env=env, timeout=600)
                self.assertIsNotNone(payload, f"{args[0]}: stdout did not parse as JSON")

    def test_reachable_run_has_no_preamble(self):
        """CR-32 acc 3 + WB MSG 326: reachable runs parse with no preamble; close-binary-census's async path no
        longer leaks astroquery's "INFO: Query finished." line onto stdout."""
        self._stdout_json("close-binary-census", "--dist-max-ly", "10", "--period-max-d", "30")
        self._stdout_json("gaia-tap", "--adql", "SELECT TOP 1 source_id FROM gaiadr3.gaia_source")
        self._stdout_json("dossier", "--star", "Ross 128", "--fmt", "json", "--gaia-timeout", "120")


if __name__ == "__main__":
    unittest.main()
