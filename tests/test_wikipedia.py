"""Offline unit tests for core.wikipedia (resolver + guard + candidate generation).

No network: _fetch_summary and compute_simbad_lookup are monkeypatched. The live fetch is
covered by tests/test_wikipedia_live.py (gated on SPACE_APP_RUN_LIVE=1).
"""
import unittest
from unittest import mock

import core.wikipedia as wiki


# ── Bayer → Wikipedia title spelling ─────────────────────────────────────────
class BayerTitleTest(unittest.TestCase):
    def test_simple_bayer(self):
        self.assertEqual(wiki._bayer_wikipedia_title("* tau Cet"), "Tau Ceti")
        self.assertEqual(wiki._bayer_wikipedia_title("* eps Eri"), "Epsilon Eridani")

    def test_superscript_numeral_dropped(self):
        self.assertEqual(wiki._bayer_wikipedia_title("* alf01 Cen"), "Alpha Centauri")

    def test_component_letter_dropped(self):
        self.assertEqual(wiki._bayer_wikipedia_title("* alf Cen A"), "Alpha Centauri")

    def test_padded_greek_forms(self):
        # SIMBAD pads mu/nu/pi with a trailing period.
        self.assertEqual(wiki._bayer_wikipedia_title("* mu. Cet"), "Mu Ceti")
        # Genitive carries the diaeresis, matching Wikipedia's own title "Xi Boötis".
        self.assertEqual(wiki._bayer_wikipedia_title("* ksi Boo"), "Xi Boötis")

    def test_extension_letter_is_not_greek(self):
        self.assertIsNone(wiki._bayer_wikipedia_title("* b Vel"))

    def test_double_system_id_rejected(self):
        self.assertIsNone(wiki._bayer_wikipedia_title("** LDS 6248A"))

    def test_flamsteed_shape_rejected(self):
        # First token is numeric — not a Bayer letter.
        self.assertIsNone(wiki._bayer_wikipedia_title("*  10 CMi"))

    def test_unknown_constellation_rejected(self):
        self.assertIsNone(wiki._bayer_wikipedia_title("* alf Xyz"))

    def test_blank(self):
        self.assertIsNone(wiki._bayer_wikipedia_title(""))
        self.assertIsNone(wiki._bayer_wikipedia_title(None))


class BayerCandidatesTest(unittest.TestCase):
    def test_numbered_yields_numbered_then_bare(self):
        # τ¹ Eridani is its own article ("Tau1 Eridani"), so try that before the system name.
        self.assertEqual(wiki._bayer_candidates("* tau01 Eri"), ["Tau1 Eridani", "Tau Eridani"])
        self.assertEqual(wiki._bayer_candidates("* alf01 Cen"), ["Alpha1 Centauri", "Alpha Centauri"])

    def test_bare_when_no_numeral(self):
        self.assertEqual(wiki._bayer_candidates("* tau Cet"), ["Tau Ceti"])

    def test_empty_for_non_bayer(self):
        self.assertEqual(wiki._bayer_candidates("** LDS 6248A"), [])
        self.assertEqual(wiki._bayer_candidates("*  10 CMi"), [])


# ── Candidate generation ─────────────────────────────────────────────────────
class BuildCandidatesTest(unittest.TestCase):
    def _queries(self, cands):
        return [q for q, _ in cands]

    def test_name_first_then_designations(self):
        d = {
            "MAIN_ID": "* tau Cet", "NAME": "NAME Tau Ceti", "Bayer": "* tau Cet",
            "HD": "HD 10700", "HR": "HR 509", "GJ": "GJ 71", "HIP": "HIP 8102",
        }
        qs = self._queries(wiki.build_candidates(d))
        self.assertEqual(qs[0], "Tau Ceti")                 # NAME wins
        # Bayer spelling is deduped against the identical NAME, so the next distinct
        # candidates are the catalogue ids in order.
        self.assertIn("HR 509", qs)
        self.assertIn("HD 10700", qs)
        self.assertLess(qs.index("HR 509"), qs.index("HD 10700"))
        self.assertLess(qs.index("HD 10700"), qs.index("HIP 8102"))

    def test_gj_emits_both_forms(self):
        qs = self._queries(wiki.build_candidates({"GJ": "GJ 71"}))
        self.assertIn("GJ 71", qs)
        self.assertIn("Gliese 71", qs)
        self.assertLess(qs.index("GJ 71"), qs.index("Gliese 71"))

    def test_flamsteed_rendered(self):
        qs = self._queries(wiki.build_candidates({"Flamsteed": "*  10 CMi"}))
        self.assertIn("10 Canis Minoris", qs)

    def test_bayer_when_no_name(self):
        qs = self._queries(wiki.build_candidates({"Bayer": "* eps Eri", "HD": "HD 22049"}))
        self.assertEqual(qs[0], "Epsilon Eridani")
        self.assertIn("HD 22049", qs)

    def test_dedup_case_insensitive(self):
        d = {"NAME": "NAME Vega", "MAIN_ID": "Vega"}
        qs = self._queries(wiki.build_candidates(d))
        self.assertEqual(qs.count("Vega"), 1)

    def test_name_only_fallback(self):
        qs = self._queries(wiki.build_candidates(None, name="Barnard's Star"))
        self.assertEqual(qs, ["Barnard's Star"])

    def test_empty(self):
        self.assertEqual(wiki.build_candidates({}), [])
        self.assertEqual(wiki.build_candidates(None), [])


# ── Star-ness guard ──────────────────────────────────────────────────────────
class IsStarArticleTest(unittest.TestCase):
    def test_star_description(self):
        self.assertTrue(wiki._is_star_article(
            {"type": "standard", "description": "star in the constellation Cetus", "extract": "…"}))

    def test_star_in_extract_only(self):
        self.assertTrue(wiki._is_star_article(
            {"type": "standard", "description": "", "extract": "It is a red dwarf near the Sun."}))

    def test_disambiguation_rejected(self):
        self.assertFalse(wiki._is_star_article(
            {"type": "disambiguation", "description": "star system", "extract": "may refer to"}))

    def test_unrelated_topic_rejected(self):
        self.assertFalse(wiki._is_star_article(
            {"type": "standard", "description": "genus of moth", "extract": "a genus of moths"}))

    def test_constellation_not_a_keyword(self):
        # "constellation" alone must NOT pass the guard (would match a constellation article).
        self.assertFalse(wiki._is_star_article(
            {"type": "standard", "description": "constellation in the northern sky",
             "extract": "one of the 88 modern constellations"}))

    def test_star_description_mentioning_constellation_is_accepted(self):
        # A real star's description reads "star in the constellation …" — must still pass.
        self.assertTrue(wiki._is_star_article(
            {"type": "standard", "description": "star in the constellation Lyra", "extract": "…"}))

    def test_constellation_article_rejected_despite_star_in_extract(self):
        # Description is decisive: no star word in the description → rejected, even though the
        # extract mentions a star (the constellation false-positive finding #1 guards against).
        self.assertFalse(wiki._is_star_article(
            {"type": "standard", "description": "constellation in the northern sky",
             "extract": "Its brightest star is Deneb."}))

    def test_generic_desc_hard_disqualifier_in_extract_rejected(self):
        # Review-fix #4: a GENERIC/absent description that would fall through to the extract, whose
        # extract carries a *non-astronomy* hard disqualifier (film/company/genus/…) AND a star word,
        # is rejected — a name collision (e.g. a film "that stars an actor") no longer surfaces.
        self.assertFalse(wiki._is_star_article(
            {"type": "standard", "description": "",
             "extract": "a 2019 film that stars an actor; a rising star of cinema"}))
        self.assertFalse(wiki._is_star_article(
            {"type": "standard", "description": "",
             "extract": "a genus of moths; the type species; a star-shaped marking"}))

    def test_generic_desc_star_with_constellation_still_accepted(self):
        # But "constellation" is NOT a hard extract disqualifier (real stars mention it), so a star
        # whose only description is generic and whose extract says "star in the constellation …"
        # is still accepted — the fix must not over-reject real stars.
        self.assertTrue(wiki._is_star_article(
            {"type": "standard", "description": "",
             "extract": "an orange dwarf star in the constellation Eridanus"}))

    def test_word_boundary_not_substring(self):
        # "star" inside "restart" / "stellar" inside "interstellar" must NOT match.
        self.assertFalse(wiki._is_star_article(
            {"type": "standard", "description": "", "extract": "a restart of the franchise"}))
        self.assertFalse(wiki._is_star_article(
            {"type": "standard", "description": "", "extract": "the film Interstellar (2014)"}))

    def test_generic_description_falls_back_to_extract(self):
        # A real star whose Wikidata description lacks a star word is still recognised via extract.
        self.assertTrue(wiki._is_star_article(
            {"type": "standard", "description": "astronomical X-ray source",
             "extract": "It is a nearby red dwarf star."}))

    def test_disqualifier_word_in_description_rejects(self):
        self.assertFalse(wiki._is_star_article(
            {"type": "standard", "description": "1985 song by a rock band",
             "extract": "a song that mentions a star"}))

    def test_none(self):
        self.assertFalse(wiki._is_star_article(None))


# ── resolve_and_fetch loop (network mocked) ──────────────────────────────────
def _summary(title, desc="star in the constellation Cetus", extract="A star."):
    return {
        "type": "standard", "title": title, "description": desc, "extract": extract,
        "extract_html": "<p>{}</p>".format(extract),
        "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")}},
        "thumbnail": {"source": "https://upload.example/thumb.jpg"},
    }


class ResolveAndFetchTest(unittest.TestCase):
    def setUp(self):
        # The found path now also fetches the full article body; stub it out (no network) by
        # default so these tests exercise only the resolution loop.
        p = mock.patch.object(wiki, "_fetch_extract", return_value=None)
        p.start()
        self.addCleanup(p.stop)

    def test_full_extract_upgrades_body(self):
        with mock.patch.object(wiki, "_fetch_summary", return_value=_summary("Tau Ceti")), \
             mock.patch.object(wiki, "_fetch_extract",
                               return_value="<h2>Tau Ceti</h2><p>full multi-paragraph body</p>"):
            res = wiki.resolve_and_fetch({"NAME": "NAME Tau Ceti"})
        self.assertTrue(res["found"])
        self.assertIn("full multi-paragraph body", res["extract_html"])

    def test_full_extract_failure_keeps_summary(self):
        # _fetch_extract returns None (default stub) → keep the REST-summary lead.
        with mock.patch.object(wiki, "_fetch_summary", return_value=_summary("Tau Ceti")):
            res = wiki.resolve_and_fetch({"NAME": "NAME Tau Ceti"})
        self.assertTrue(res["found"])
        self.assertIn("<p>", res["extract_html"])

    def test_first_candidate_hits(self):
        with mock.patch.object(wiki, "_fetch_summary", return_value=_summary("Tau Ceti")):
            res = wiki.resolve_and_fetch({"NAME": "NAME Tau Ceti", "HD": "HD 10700"})
        self.assertTrue(res["found"])
        self.assertEqual(res["title"], "Tau Ceti")
        self.assertEqual(res["matched_on"], "NAME Tau Ceti")
        self.assertEqual(res["thumbnail_url"], "https://upload.example/thumb.jpg")
        self.assertIn("/wiki/Tau_Ceti", res["url"])

    def test_skips_non_star_then_hits(self):
        def fake(title):
            if title == "Tau Ceti":
                return {"type": "standard", "description": "genus of moth", "extract": "a moth"}
            if title == "HD 10700":
                return _summary("HD 10700")
            return None
        with mock.patch.object(wiki, "_fetch_summary", side_effect=fake):
            res = wiki.resolve_and_fetch({"NAME": "NAME Tau Ceti", "HD": "HD 10700"})
        self.assertTrue(res["found"])
        self.assertEqual(res["matched_on"], "HD 10700")

    def test_skips_404_then_hits(self):
        def fake(title):
            return None if title == "Vega" else _summary("Alpha Lyrae")
        with mock.patch.object(wiki, "_fetch_summary", side_effect=fake):
            res = wiki.resolve_and_fetch({"NAME": "NAME Vega", "Bayer": "* alf Lyr"})
        self.assertTrue(res["found"])

    def test_all_miss(self):
        with mock.patch.object(wiki, "_fetch_summary", return_value=None):
            res = wiki.resolve_and_fetch({"NAME": "NAME Nowhere", "HD": "HD 999999"})
        self.assertFalse(res["found"])
        self.assertIn("Nowhere", res["tried"])
        self.assertIn("HD 999999", res["tried"])

    def test_connection_error_fails_fast(self):
        import requests
        calls = {"n": 0}

        def fake(_title):
            calls["n"] += 1
            raise requests.exceptions.ConnectionError("down")
        with mock.patch.object(wiki, "_fetch_summary", side_effect=fake):
            res = wiki.resolve_and_fetch({"NAME": "NAME X", "HD": "HD 1", "HIP": "HIP 2"})
        self.assertIn("error", res)
        self.assertIn("Wikipedia", res["error"])
        self.assertEqual(calls["n"], 1)   # a full outage stops after the first candidate

    def test_transient_error_then_hits_next_candidate(self):
        import requests
        calls = {"n": 0}

        def fake(title):
            calls["n"] += 1
            if calls["n"] == 1:
                raise requests.exceptions.Timeout("slow")   # transient, title-specific
            return _summary(title)
        with mock.patch.object(wiki, "_fetch_summary", side_effect=fake):
            res = wiki.resolve_and_fetch({"NAME": "NAME Tau Ceti", "HD": "HD 10700"})
        self.assertTrue(res["found"])
        self.assertEqual(res["matched_on"], "HD 10700")

    def test_all_transient_errors_returns_error(self):
        import requests
        with mock.patch.object(wiki, "_fetch_summary",
                               side_effect=requests.exceptions.Timeout("slow")):
            res = wiki.resolve_and_fetch({"NAME": "NAME X", "HD": "HD 1"})
        self.assertIn("error", res)

    def test_transient_error_then_clean_misses_is_calm_not_found(self):
        # A transient error on the strongest candidate, then every other candidate cleanly 404s
        # (Wikipedia reachable, no such article) → the calm "not found", NOT a scary error.
        import requests
        calls = {"n": 0}

        def fake(title):
            calls["n"] += 1
            if calls["n"] == 1:
                raise requests.exceptions.Timeout("slow")   # transient on the strongest name
            return None                                     # clean 404 miss on the rest
        with mock.patch.object(wiki, "_fetch_summary", side_effect=fake):
            res = wiki.resolve_and_fetch({"NAME": "NAME X", "HD": "HD 1", "HIP": "HIP 2"})
        self.assertNotIn("error", res)
        self.assertFalse(res["found"])

    def test_name_path_uses_simbad_designations(self):
        fake_simbad = {"designations": {"NAME": "NAME Tau Ceti", "HD": "HD 10700"},
                       "main_id": "* tau Cet"}
        with mock.patch("core.databases.compute_simbad_lookup", return_value=fake_simbad), \
             mock.patch.object(wiki, "_fetch_summary", return_value=_summary("Tau Ceti")):
            res = wiki.resolve_and_fetch(name="Tau Ceti")
        self.assertTrue(res["found"])
        self.assertEqual(res["matched_on"], "NAME Tau Ceti")

    def test_name_path_simbad_error_falls_back_to_name(self):
        with mock.patch("core.databases.compute_simbad_lookup", return_value={"error": "no"}), \
             mock.patch.object(wiki, "_fetch_summary", return_value=_summary("Barnards Star")):
            res = wiki.resolve_and_fetch(name="Barnards Star")
        self.assertTrue(res["found"])
        self.assertEqual(res["matched_on"], "Barnards Star")


if __name__ == "__main__":
    unittest.main()
