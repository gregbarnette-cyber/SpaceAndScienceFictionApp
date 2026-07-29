# tests/test_designation_ids.py — Phase AN1: the `* ` Bayer/Flamsteed classifier.
#
# AN1 adds _classify_star_id + the D8 precedence rule to core/shared.py and wires
# them into _match_designations. It is deliberately OUTPUT-INERT: "Bayer" and
# "Flamsteed" are not designation keys until AN2, so the guard skips them and every
# existing call site is byte-identical. tests/test_designation_harness.py proves
# that half; this file proves the classifier itself is right, by driving the key
# set AN2 will introduce.
#
# Real ids come from tests/fixtures/designation_ids.json (AN4.0, captured live).
# Hand-written strings are used only for shapes the corpus cannot supply.

import json
import pathlib
import unittest

import core.shared as shared

_CORPUS_PATH = pathlib.Path(__file__).resolve().parent / "fixtures" / "designation_ids.json"

# The key set AN2 will ship. Passing it here lets AN1 be tested at full strength
# while remaining inert in production.
_KEYS_WITH_STAR = list(shared._CSV_DESIG_KEYS) + ["Bayer", "Flamsteed"]


def _corpus():
    with open(_CORPUS_PATH, encoding="utf-8") as fh:
        return json.load(fh)["stars"]


def _ids_for(query):
    return next(s for s in _corpus() if s["query"] == query)["ids"]


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


class InertnessTest(unittest.TestCase):
    """AN1 ships the classifier but NOT the keys — production output must not move."""

    def test_the_shipped_key_sets_do_not_carry_the_new_keys_yet(self):
        for name, keys in (("_CSV_DESIG_KEYS", shared._CSV_DESIG_KEYS),
                           ("_NARROW_DESIG_KEYS", shared._NARROW_DESIG_KEYS)):
            with self.subTest(key_set=name):
                self.assertNotIn("Bayer", keys, "AN2 adds these, not AN1")
                self.assertNotIn("Flamsteed", keys)

    def test_every_corpus_star_is_unchanged_under_the_shipped_keys(self):
        """The classifier must be invisible until AN2 turns the keys on.

        The differential harness asserts this across all producers; this states it
        directly at the matcher, so a failure here localises instantly.
        """
        for star in _corpus():
            with self.subTest(star=star["query"]):
                got = shared._match_designations(star["ids"], shared._CSV_DESIG_KEYS)
                self.assertEqual(set(got), set(shared._CSV_DESIG_KEYS))
                captured = [v for v in got.values() if v]
                self.assertFalse(
                    [v for v in captured if v.startswith(("* ", "V* ", "** "))],
                    "a `* `-family id reached a shipped key — AN1 must stay inert",
                )

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
