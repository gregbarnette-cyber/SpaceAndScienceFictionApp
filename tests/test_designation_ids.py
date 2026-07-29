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

    def test_flamsteed_with_no_bayer_is_stable_rather_than_first(self):
        """Changed by the 2026-07-29 census reopen — was "first candidate wins".

        With no Bayer, clause (ii) has nothing to key off, so the old rule returned
        `candidates[0]` — SIMBAD's ordering. 12 catalogue objects are in this state.
        The pick is still arbitrary (both are real designations) but it is now
        *fixed*, which is the only property actually achievable here.
        """
        for order in (["*  79 Aqr", "*  24 PsA"], ["*  24 PsA", "*  79 Aqr"]):
            with self.subTest(order=order):
                desig = shared._match_designations(order, _KEYS_WITH_STAR)
                self.assertEqual(desig["Flamsteed"], "*  24 PsA")

    def test_bayer_prefers_the_superscript_over_the_bare_form(self):
        """D8(i-b), added by the census reopen — 49 catalogue objects.

        Neither candidate is wrong (no `* ` id is attached to more than one object,
        0 of 6293), so this is decided on informativeness: in 47 of the 49 a
        numbered SIBLING star exists, so the bare form does not say which is meant.
        """
        for ids, want in ((["* kap Cet", "* kap01 Cet"], "* kap01 Cet"),
                          (["* kap01 Cet", "* kap Cet"], "* kap01 Cet"),
                          (["* ksi Cap", "* ksi02 Cap"], "* ksi02 Cap")):
            with self.subTest(ids=ids):
                self.assertEqual(
                    shared._match_designations(ids, _KEYS_WITH_STAR)["Bayer"], want
                )

    def test_the_component_clause_beats_the_superscript_clause(self):
        """Ordering of (i) before (i-b) — α Cen A is why it matters.

        Its ids are "* alf Cen A" + "* alf01 Cen". Both clauses happen to select
        the superscript here, but only because the other candidate is component-
        suffixed; if (i-b) ran first on a star carrying "* xxx01 Cst A" alongside
        "* xxx Cst", it would pick the component form. Pinned so the key order in
        `_preferred_star_id` cannot be swapped silently.
        """
        self.assertEqual(
            shared._preferred_star_id(["* alf01 Cen A", "* alf Cen"], "Bayer"),
            "* alf Cen",
        )

    def test_flamsteed_prefers_the_component_less_form(self):
        """D8(ii)'s component clause — the LARGEST shape, and it had no rule at all.

        Clause (i) was written Bayer-only, so "*   4 Cen" vs "*   4 Cen A" fell to
        SIMBAD's ordering on 47 objects. Justified by the catalogue rather than by
        symmetry with Bayer: 46 of those 48 objects have a `main_id` carrying no
        component letter (4 Cen's is "* h Cen", a system).
        """
        for order in (["*   4 Cen", "*   4 Cen A"], ["*   4 Cen A", "*   4 Cen"]):
            with self.subTest(order=order):
                self.assertEqual(
                    shared._preferred_star_id(order, "Flamsteed", "* h Cen"), "*   4 Cen"
                )

    def test_the_constellation_clause_still_resolves_13_objects(self):
        """The component clause must not shadow clause (ii). Fomalhaut is the pin."""
        self.assertEqual(
            shared._preferred_star_id(["*  79 Aqr", "*  24 PsA"], "Flamsteed", "* alf PsA"),
            "*  24 PsA",
        )

    def test_ties_no_clause_can_separate_are_deterministic(self):
        """Alpheratz: α And AND δ Peg — both legitimate, so only stability is possible.

        Formerly `test_ties_are_stable_on_the_first_candidate`, which asserted the
        weaker property that the pick did not depend on dict/set iteration order.
        It now must not depend on SIMBAD's *input* order either.
        """
        for order in (["* alf And", "* del Peg"], ["* del Peg", "* alf And"]):
            with self.subTest(order=order):
                desig = shared._match_designations(order, _KEYS_WITH_STAR)
                self.assertEqual(desig["Bayer"], "* alf And")
        for _ in range(5):
            self.assertEqual(
                shared._match_designations(["* bet Ori", "* gam Ori"],
                                           _KEYS_WITH_STAR)["Bayer"], "* bet Ori")


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


class D8TieCensusTest(unittest.TestCase):
    """The measured size of D8's unresolved-tie residue (census, 2026-07-29).

    `_preferred_star_id` breaks a tie with `candidates[0]` — SIMBAD's own id
    ordering, the dependency D8 exists to remove. Its docstring said the residual
    bare-vs-superscript case had **no corpus example**, which was true of the
    43-star fixture and false of the catalogue: a TAP census over all 4690 objects
    carrying a `* ` id found **49** of them.

    These pins are deliberately about SHAPE COUNTS, not about which candidate
    wins. Nothing here asserts the current pick is correct — it isn't decided —
    only that the size and composition of the problem stay as measured, so a D8
    reopen argues from numbers instead of re-deriving them. Regenerate the census
    with `venv/bin/python -m tests._capture_designation_ties`.

    Offline: reads the committed artifact. The live half is
    test_designation_live.py::D8TieShapesStillExistTest.
    """

    @classmethod
    def setUpClass(cls):
        path = pathlib.Path(__file__).resolve().parent / "fixtures" / "designation_ties.json"
        with open(path, encoding="utf-8") as fh:
            cls.census = json.load(fh)

    def test_the_bayer_residue_is_dominated_by_the_shape_d8_left_open(self):
        by_shape = self.census["bayer_by_shape"]
        self.assertEqual(sum(by_shape.values()), 60)
        self.assertEqual(by_shape["bare_vs_superscript"], 49)

    def test_the_largest_unruled_shape_is_flamsteed_bare_vs_component(self):
        """The gap the plan never named — clause (i) is Bayer-ONLY.

        `*   4 Cen` vs `*   4 Cen A` is the same shape clause (i) was written for,
        on the other designation system, where no clause applies. At 47 objects it
        is larger than the bare-vs-superscript residue D8 documented, so a reopen
        that fixes only the documented case would leave the bigger half untouched.
        """
        by_shape = self.census["flamsteed_by_shape"]
        self.assertEqual(sum(by_shape.values()), 74)
        self.assertEqual(by_shape["bare_vs_component"], 47)

    def test_clause_ii_is_earning_its_keep(self):
        # 13 objects genuinely resolved by the constellation match — the clause is
        # not dead weight, which matters if a reopen proposes replacing it.
        self.assertEqual(self.census["flamsteed_by_shape"]["resolved_by_clause_ii"], 13)

    def test_a_bayer_cross_constellation_duplicate_exists_and_has_no_clause(self):
        """Fomalhaut's problem, on the Bayer side, where clause (ii) has no sibling.

        Alpheratz is α Andromedae AND δ Pegasi; Elnath is β Tauri AND γ Aurigae.
        Only two stars, but they are the case where the CURRENT rule cannot be
        right by construction: both candidates are legitimate designations of the
        same star in different constellations, so ordering decides.
        """
        cross = [e["candidates"] for e in self.census["bayer"]
                 if e["shape"] == "cross_constellation"]
        self.assertEqual(len(cross), 2)
        self.assertIn(["* alf And", "* del Peg"], cross)

    def test_the_bare_form_is_not_the_primary_which_is_why_i_b_prefers_superscript(self):
        """The measurement that killed the obvious alternative rule.

        "Prefer the bare form, it names the primary" is the natural reading, and it
        is false: the bare id sits on the lowest-numbered member for 25 objects and
        on a HIGHER-numbered one for 22 (α Cap is on α² Cap, ξ Cap on ξ² Cap). The
        unnumbered name followed the *brighter* star; the numbering runs by RA.
        """
        import re
        lowest = higher = 0
        for entry in self.census["bayer"]:
            if entry["shape"] != "bare_vs_superscript":
                continue
            nums = sorted(m.group(1) for m in
                          (re.search(r"^\S*?(\d+)$", c.split()[1]) for c in entry["candidates"])
                          if m)
            bare = [c for c in entry["candidates"]
                    if not re.search(r"\d$", c.split()[1])]
            if not bare or not nums:
                continue
            if nums[0] == "01":
                lowest += 1
            else:
                higher += 1
        self.assertGreater(higher, 15, "the bare form is NOT systematically the primary")
        self.assertGreater(lowest, 15)

    def test_the_census_used_the_shipped_helpers(self):
        # Guards the measurement itself: every recorded `chosen` must still be what
        # _preferred_star_id returns today, so a change to the rule invalidates the
        # census loudly instead of leaving stale numbers to be argued from.
        for entry in self.census["bayer"]:
            self.assertEqual(
                shared._preferred_star_id(entry["candidates"], "Bayer"), entry["chosen"]
            )


if __name__ == "__main__":
    unittest.main()
