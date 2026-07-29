# tests/test_designation_ids.py — Phase AN1: the `* ` Bayer/Flamsteed classifier.
#
# AN1 adds _classify_star_id + the D8 precedence rule to core/shared.py and wires
# them into _match_designations. When AN1 shipped it was deliberately OUTPUT-INERT
# ("Bayer"/"Flamsteed" were not yet keys, so the guard skipped them), and this file
# carried an `InertnessTest` class asserting exactly that. **AN2 turned the keys on**,
# so those assertions were retired — they asserted the absence of the very thing the
# next part ships, and no correct AN2 could keep them green. What they were protecting
# now lives in tests/test_designation_an2.py, which asserts the keys' PRESENCE and the
# D3 dedupe; the corpus-shape counters they shared moved to CorpusCoverageTest below.
#
# This file's remaining job is unchanged: prove the classifier and the D8 tie-break
# are right, independently of which key set is shipped.
#
# Real ids come from tests/fixtures/designation_ids.json (AN4.0, captured live).
# Hand-written strings are used only for shapes the corpus cannot supply.

import json
import pathlib
import unittest

import core.shared as shared

_CORPUS_PATH = pathlib.Path(__file__).resolve().parent / "fixtures" / "designation_ids.json"

# AN1 defined this as `_CSV_DESIG_KEYS + ["Bayer", "Flamsteed"]` so the classifier
# could be tested at full strength while the shipped keys stayed inert. AN2 added both
# keys to the shipped list, so the concatenation would now merely DUPLICATE them.
# Kept as a named alias rather than inlined: these tests are about the classifier, and
# the name still says which property of the key set they depend on.
_KEYS_WITH_STAR = list(shared._CSV_DESIG_KEYS)


def _corpus():
    with open(_CORPUS_PATH, encoding="utf-8") as fh:
        return json.load(fh)["stars"]


def _ids_for(query):
    return next(s for s in _corpus() if s["query"] == query)["ids"]


def _corpus_row(query):
    return next(s for s in _corpus() if s["query"] == query)["row"]


class ClassifierTest(unittest.TestCase):
    """§4 steps 1–4. Step ORDER is the load-bearing part."""

    def test_double_star_ids_never_classify(self):
        """D2: `**` is a double-SYSTEM id, never a name for the star being queried."""
        for raw in ("** LDS 6248A", "** SHB    1A", "** RHD    1A", "** STF 4002A"):
            with self.subTest(id=raw):
                self.assertIsNone(shared._classify_star_id(raw))

    def test_the_double_star_branch_guards_a_looser_implementation(self):
        """Corrects PHASE_AN_PLAN.md §4 step 1 — see [A4].

        The plan says `** LDS 6248A` "also satisfies startswith('* ')" and calls the
        `** `-before-`* ` ordering load-bearing. **It does not, and it is not**: two
        asterisks then a space never matches asterisk-then-space, so the `* ` branch
        could not claim a `**` id even if it ran first. This test states the true
        premise so nobody re-derives the false one.

        The branch still earns its place: it is a real guard against the OTHER
        obvious ways to write this — testing `startswith("*")`, or stripping
        asterisks first — both of which would read "** SHB    1A" as a Bayer id.
        """
        raw = "** SHB    1A"
        self.assertFalse(raw.startswith("* "), "the plan's stated premise is false")
        self.assertTrue(raw.startswith("*"), "a single-asterisk test WOULD match")
        self.assertEqual(raw.lstrip("*").strip().split()[0], "SHB",
                         "an asterisk-stripping test WOULD read this as a Bayer letter")
        self.assertIsNone(shared._classify_star_id(raw))

    def test_flamsteed_is_a_bare_integer_first_token(self):
        for raw, expect in (("*  18 Eri", "Flamsteed"), ("*  20 Crt", "Flamsteed"),
                            ("*  10 CMi", "Flamsteed"), ("*   9 CMa", "Flamsteed")):
            with self.subTest(id=raw):
                self.assertEqual(shared._classify_star_id(raw), expect)

    def test_bayer_covers_plain_component_and_superscript_forms(self):
        for raw in ("* alf CMi", "* alf CMi A", "* alf01 Cen", "* zet01 Ret", "* omi02 Eri"):
            with self.subTest(id=raw):
                self.assertEqual(shared._classify_star_id(raw), "Bayer")

    def test_variable_is_classified_but_is_not_a_key(self):
        """D2: `V*` is dropped as a key, yet still classified.

        Keeping the classification means promoting it to a key later is one line and
        needs no re-classification — so this asserts BOTH halves.
        """
        self.assertEqual(shared._classify_star_id("V* eps Eri"), "Variable")
        desig = shared._match_designations(["V* eps Eri", "* eps Eri"], _KEYS_WITH_STAR)
        self.assertNotIn("Variable", desig)
        self.assertEqual(desig["Bayer"], "* eps Eri")

    def test_promoting_variable_to_a_key_needs_no_other_change(self):
        """The stated rationale for classifying `V*` at all — now actually true.

        As first written, _match_designations bucketed only Bayer and Flamsteed, so a
        `V* ` id fell through to the prefix loop, matched nothing, and was stored
        nowhere: adding "Variable" to a key set would have yielded a key that was
        silently always None — no error, no failing test. Found by /code-review
        reading the docstring against the code (2026-07-29). This asserts the claim
        instead of restating it.
        """
        keys = _KEYS_WITH_STAR + ["Variable"]
        desig = shared._match_designations(_ids_for("Betelgeuse"), keys)
        self.assertEqual(desig["Variable"], "V* alf Ori")
        self.assertEqual(desig["Bayer"], "* alf Ori", "promoting Variable must not disturb Bayer")

    def test_lookalikes_that_must_not_classify(self):
        """Traps found while surveying the corpus, plus ordinary catalogue ids."""
        for raw in ("VVO 20", "VVO 21", "V645 Cen",      # 'V' but not 'V* '
                    "HD 61421", "NAME Procyon", "GJ 280", "2MASS J07393591+0513512",
                    "*", "* ", "**", ""):                 # degenerate/short
            with self.subTest(id=raw):
                self.assertIsNone(shared._classify_star_id(raw))

    def test_double_space_is_not_required_and_not_stripped(self):
        """D9: the raw string is the identifier, stored verbatim (double space kept)."""
        desig = shared._match_designations(["*  18 Eri"], _KEYS_WITH_STAR)
        self.assertEqual(desig["Flamsteed"], "*  18 Eri")


class D8PrecedenceTest(unittest.TestCase):
    """D8 — the tie-break, against real corpus ids (PHASE_AN_PLAN.md §4b)."""

    def _pick(self, query):
        return shared._match_designations(_ids_for(query), _KEYS_WITH_STAR)

    def test_bayer_prefers_the_component_less_form_regardless_of_simbad_order(self):
        """The case first-match-wins got wrong.

        Procyon lists '* alf CMi' BEFORE '* alf CMi A'; Sirius lists
        '* alf CMa A' BEFORE '* alf CMa'. Both must resolve to the component-less
        form, so this fails for any implementation that trusts SIMBAD's ordering.
        """
        self.assertEqual(self._pick("Procyon")["Bayer"], "* alf CMi")
        self.assertEqual(self._pick("Sirius")["Bayer"], "* alf CMa")

        procyon, sirius = _ids_for("Procyon"), _ids_for("Sirius")
        self.assertLess(procyon.index("* alf CMi"), procyon.index("* alf CMi A"))
        self.assertLess(sirius.index("* alf CMa A"), sirius.index("* alf CMa"),
                        "premise: Sirius orders these opposite to Procyon")

    def test_alpha_cen_a_resolves_to_the_superscript_form(self):
        """The one star where D8 was a product decision, not a mechanical fallout.

        α Cen A's MAIN_ID is '* alf Cen A'. Choosing that form would make D3
        suppress it as a duplicate and the star would gain nothing from the phase;
        '* alf01 Cen' (α¹ Cen) differs from MAIN_ID and survives. Decided by the
        maintainer 2026-07-29 — see PHASE_AN_PLAN.md §4b.
        """
        picked = self._pick("alf Cen A")["Bayer"]
        self.assertEqual(picked, "* alf01 Cen")
        self.assertIn("* alf Cen A", _ids_for("alf Cen A"), "premise: both forms exist")

    def test_flamsteed_prefers_the_constellation_matching_the_bayer(self):
        """Fomalhaut carries TWO Flamsteed numbers in different constellations.

        Its Bayer is '* alf PsA', so 24 PsA wins over 79 Aqr — Flamsteed's
        historical cross-boundary duplicate.
        """
        picked = self._pick("Fomalhaut")
        self.assertEqual(picked["Bayer"], "* alf PsA")
        self.assertEqual(picked["Flamsteed"], "*  24 PsA")

    def test_system_level_query_of_a_multiple_keeps_the_bare_form(self):
        """Algol: the bare form IS this object's own designation, and equals MAIN_ID.

        Its id list carries `* bet Per` plus A/B/C components. The corpus queries the
        SYSTEM (main_id `* bet Per`), so clause (i) selects `* bet Per` — correct, and
        D3 will then suppress it as a MAIN_ID duplicate. Recorded because
        /code-review raised the neighbouring COMPONENT-level case, which behaves
        differently and is an open AN2 question — see the docstring below.
        """
        picked = self._pick("Algol")
        self.assertEqual(picked["Bayer"], "* bet Per")
        self.assertEqual(picked["Flamsteed"], "*  26 Per")
        self.assertEqual(_corpus_row("Algol")["main_id"], "* bet Per",
                         "premise: this is a system-level query")

    def test_no_component_query_in_the_corpus_carries_a_bare_system_form(self):
        """Why D8 clause (i) needs no MAIN_ID-aware refinement (PHASE_AN_PLAN.md §4b).

        /code-review (2026-07-29) observed that clause (i) prefers the component-less
        form unconditionally, so a COMPONENT-level query whose ids also carry the bare
        SYSTEM form would take the system's designation. Real mechanism — but the
        combination requires a distinct component object that ALSO lists its parent's
        bare Bayer id, and SIMBAD does not do that: where a component is its own
        object, the parent's bare form is absent from its ids.

        This asserts the offline half over every component-level query in the corpus.
        The live half — that `bet Per A` resolves to the SYSTEM object, so its pick
        equals MAIN_ID and D3 suppresses it — is in test_designation_live.py, because
        it is a claim about an external catalogue that this frozen fixture cannot
        detect changing.
        """
        checked = 0
        for star in _corpus():
            main_id = str(star["row"].get("main_id") or "")
            if not (main_id.startswith("* ") and shared._COMPONENT_SUFFIX_RE.search(main_id)):
                continue
            checked += 1
            bare = main_id[:-2].strip()          # "* alf Cen A" -> "* alf Cen"
            with self.subTest(star=star["query"]):
                self.assertNotIn(
                    bare, star["ids"],
                    f"{star['query']} is a component object that also lists the bare "
                    f"system form {bare!r} — the combination §4b measured as absent. "
                    f"D8 clause (i) would attribute the system id to a component.",
                )
        self.assertGreaterEqual(checked, 5, "corpus lost its component-level queries")

    def test_flamsteed_falls_back_to_first_when_there_is_no_bayer(self):
        desig = shared._match_designations(["*  79 Aqr", "*  24 PsA"], _KEYS_WITH_STAR)
        self.assertEqual(desig["Flamsteed"], "*  79 Aqr")

    def test_ties_are_stable_on_the_first_candidate(self):
        """Equal-shaped candidates must not depend on set/dict iteration order."""
        for _ in range(5):
            desig = shared._match_designations(["* bet Ori", "* gam Ori"], _KEYS_WITH_STAR)
            self.assertEqual(desig["Bayer"], "* bet Ori")


class NarrowPathTest(unittest.TestCase):
    """D7 + the AN0→AN1 sweep's Hazard 1 — the KeyError a naive pre-pass causes."""

    def test_the_narrow_key_set_neither_raises_nor_leaks(self):
        """opts 17/19/20/21 + the seven route planners.

        _NARROW_DESIG_KEYS deliberately has no Bayer/Flamsteed (D7: those panels
        already show MAIN_ID in a separate name column, which for bright stars IS
        the Bayer string, and D3's dedupe cannot reach that path). A pre-pass that
        assigned without re-spelling the guard raises KeyError: 'Bayer' here.
        """
        desig = shared._match_designations(_ids_for("Procyon"), shared._NARROW_DESIG_KEYS)
        self.assertEqual(set(desig), set(shared._NARROW_DESIG_KEYS))
        self.assertEqual(desig["NAME"], "NAME Procyon")
        joined = shared._join_designations(desig, shared._NARROW_DESIG_KEYS)
        for leaked in ("* alf CMi", "*  10 CMi"):
            self.assertNotIn(leaked, joined)

    def test_no_prefix_map_entry_shadows_the_star_family(self):
        """Pins the invariant that lets the classifier claim `* `/`V* ` ids outright.

        _match_designations `continue`s past a classified id without consulting
        _CSV_PREFIX_MAP. That is only sound while no prefix could have matched one;
        verified true today, and one map entry away from being false.
        """
        offenders = [p for p, _ in shared._CSV_PREFIX_MAP
                     if p.startswith("*") or p.startswith("V")]
        self.assertEqual(offenders, [])


class CorpusCoverageTest(unittest.TestCase):
    """A silent corpus shrink would hollow this whole file out."""

    def test_no_star_family_id_ever_reaches_a_NON_star_key(self):
        """The classifier's `continue` must not starve the prefix loop, or feed it.

        AN1's InertnessTest asserted that NO shipped key held a `* `-family id, which
        AN2 deliberately ends. The durable half of that assertion survives here: a
        `* `/`V* `/`** ` id may now land in Bayer or Flamsteed, and NOWHERE ELSE. That
        catches both directions of a regression — a prefix entry growing to shadow the
        family, and the classifier leaking a `** ` id it is supposed to reject.
        """
        star_keys = {"Bayer", "Flamsteed"}
        for star in _corpus():
            with self.subTest(star=star["query"]):
                got = shared._match_designations(star["ids"], shared._CSV_DESIG_KEYS)
                self.assertEqual(set(got), set(shared._CSV_DESIG_KEYS))
                strays = {k: v for k, v in got.items()
                          if v and k not in star_keys and v.startswith(("* ", "V* ", "** "))}
                self.assertFalse(strays, f"`* `-family id reached a non-star key: {strays}")

    def test_the_corpus_actually_exercises_every_branch(self):
        """A silent corpus shrink would hollow this file out. Count the shapes."""
        seen = {"Bayer": 0, "Flamsteed": 0, "Variable": 0, "rejected_double": 0}
        for star in _corpus():
            for raw in star["ids"]:
                kind = shared._classify_star_id(raw)
                if kind:
                    seen[kind] += 1
                elif raw.startswith("** "):
                    seen["rejected_double"] += 1
        for shape, n in seen.items():
            with self.subTest(shape=shape):
                self.assertGreater(n, 0, f"corpus exercises no {shape} ids")


if __name__ == "__main__":
    unittest.main()
