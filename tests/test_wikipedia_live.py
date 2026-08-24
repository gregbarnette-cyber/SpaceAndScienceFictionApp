"""Live-network tests for core.wikipedia — gated on SPACE_APP_RUN_LIVE=1 + reachability.

Skipped by a routine ``pytest -q`` (no socket opened). Run with:

    SPACE_APP_RUN_LIVE=1 venv/bin/python -m pytest tests/test_wikipedia_live.py
"""
import unittest

import core.wikipedia as wiki
from tests import _netcheck

_LIVE = _netcheck.live_enabled() and _netcheck.reachable("en.wikipedia.org", 443)


@unittest.skipUnless(_LIVE, "live network disabled (set SPACE_APP_RUN_LIVE=1) or Wikipedia unreachable")
class WikipediaLiveTest(unittest.TestCase):
    def test_proper_name(self):
        res = wiki.resolve_and_fetch({"NAME": "NAME Tau Ceti"})
        self.assertTrue(res.get("found"), res)
        self.assertEqual(res["title"], "Tau Ceti")
        self.assertIn("/wiki/Tau_Ceti", res["url"])
        self.assertTrue(any(w in (res["summary_text"] + res["description"]).lower()
                            for w in ("star", "dwarf")))

    def test_catalog_id_redirects_to_article(self):
        # "HD 10700" redirects to "Tau Ceti" on Wikipedia — the resolver follows it.
        res = wiki.resolve_and_fetch({"HD": "HD 10700"})
        self.assertTrue(res.get("found"), res)
        self.assertEqual(res["title"], "Tau Ceti")

    def test_bayer_spelled(self):
        res = wiki.resolve_and_fetch({"Bayer": "* eps Eri"})
        self.assertTrue(res.get("found"), res)
        self.assertEqual(res["title"], "Epsilon Eridani")

    def test_name_path_end_to_end(self):
        res = wiki.resolve_and_fetch(name="Vega")
        self.assertTrue(res.get("found"), res)
        self.assertIn("Vega", res["title"])

    def test_unresolvable_is_not_found_not_error(self):
        res = wiki.resolve_and_fetch({"HD": "HD 999999999"})
        self.assertNotIn("error", res)
        self.assertFalse(res.get("found"))

    def test_thumbnail_bytes(self):
        res = wiki.resolve_and_fetch({"NAME": "NAME Sirius"})
        self.assertTrue(res.get("found"), res)
        if res.get("thumbnail_url"):
            data = wiki.fetch_thumbnail(res["thumbnail_url"])
            self.assertIsInstance(data, (bytes, bytearray))
            self.assertGreater(len(data), 0)


if __name__ == "__main__":
    unittest.main()
