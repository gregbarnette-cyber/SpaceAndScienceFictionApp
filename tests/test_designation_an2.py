# tests/test_designation_an2.py — Phase AN2: key insertion and the ripple.
#
# AN1 built the `* ` classifier but shipped no keys, so it was output-inert. AN2 adds
# "Bayer" and "Flamsteed" to core.shared._CSV_DESIG_KEYS — the first INTENDED output
# change of the phase — and pays the two costs that come with it:
#
#   D3 / AN2d  For 16 of the 43 corpus stars SIMBAD's main_id IS the Bayer string, so
#              the naive join renders it twice. _join_designations dedupes by value —
#              which also fixes a PRE-EXISTING duplicate on 13 further stars that have
#              no `* ` id at all (main_id equal to their HD/GJ slot). See
#              MainIdDedupeTest.test_the_dedupe_also_fires_on_stars_with_no_star_id.
#   AN2c-T1    The self-firing D4 trigger: the opt-50 builder must emit the new keys.
#              If it doesn't, the D4 deferral is INVALID — the code is wrong, not just
#              the DB data, and a rebuild would not help. See PHASE_AN_PLAN.md §5.
#
# The classifier itself is tested in test_designation_ids.py; the byte-level baseline
# across all four producers is test_designation_harness.py (whose golden file was
# regenerated for this part, deliberately, in the same commit).

import json
import pathlib
import unittest

import core.databases as databases
import core.shared as shared
import main as cli_main

_CORPUS_PATH = pathlib.Path(__file__).resolve().parent / "fixtures" / "designation_ids.json"


def _corpus():
    with open(_CORPUS_PATH, encoding="utf-8") as fh:
        return json.load(fh)["stars"]


def _star(query):
    return next(s for s in _corpus() if s["query"] == query)


def _ids_for(query):
    return _star(query)["ids"]


def _lookup_shaped(query):
    """Reproduce compute_simbad_lookup's designations dict + desig_str, offline.

    Deliberately NOT the full function: that path needs the DB (gcns/gould blocks) and
    two network monkeypatches, all of which the differential harness already drives.
    What AN2 changes is the key list and the join, so this reproduces exactly the two
    lines that consume them — keys_order and the join — from core/databases.py.
    """
    main_id = str(_star(query)["row"].get("main_id") or query)
    keys_order = ["MAIN_ID"] + list(shared._CSV_DESIG_KEYS)
    desig = {k: None for k in keys_order}
    desig["MAIN_ID"] = main_id
    desig.update(shared._match_designations(_ids_for(query), shared._CSV_DESIG_KEYS))
    return desig, shared._join_designations(desig, keys_order)


class KeyInsertionTest(unittest.TestCase):
    """AN2 + AN2a/AN2b — which key sets gain the keys, and where."""

    def test_the_wide_key_set_carries_bayer_and_flamsteed(self):
        for key in ("Bayer", "Flamsteed"):
            self.assertIn(key, shared._CSV_DESIG_KEYS)

    def test_they_sit_immediately_after_name(self):
        """AN2b: insertion POSITION is wire-visible, not just membership.

        query.py serialises this dict verbatim, so the sibling repo sees the JSON
        object re-ordered rather than merely extended. Pinning the position means a
        future key insertion that shuffles these is a deliberate, reviewed act.
        """
        self.assertEqual(shared._CSV_DESIG_KEYS[:3], ["NAME", "Bayer", "Flamsteed"])

    def test_the_narrow_key_set_does_NOT_carry_them(self):
        """D7 — opts 17/19/20/21 and the seven route planners stay as they are.

        Those tables already render main_id in a separate name column, which for a
        bright star IS the Bayer string; adding the keys would reproduce the AN2d
        duplication on ten more surfaces, and D3's dedupe lives in the compute_simbad_lookup
        join, which this path never reaches.
        """
        for key in ("Bayer", "Flamsteed"):
            self.assertNotIn(key, shared._NARROW_DESIG_KEYS)

    def test_variable_is_still_not_a_key(self):
        """D2 — classified (so promotion stays one line), never shipped."""
        self.assertNotIn("Variable", shared._CSV_DESIG_KEYS)
        self.assertEqual(shared._classify_star_id("V* eps Eri"), "Variable")

    def test_sao_was_declined_as_the_third_candidate_key(self):
        """AN2-SAO — decided against, 2026-07-29. Recorded here, not just in the plan.

        Phase AO left AN a third candidate key with an identical ripple. Measured both
        ways over the same corpus: capturing SAO would append an `SAO nnnnn` token to
        the banner of 22 of the 43 fixture stars, to make 3 stars' Gould lookups
        resolve by an SAO fallback join instead of by HD. Declined on that ratio.
        tests/test_gould.py::test_sao_is_absent_from_the_designation_key_set is the
        tripwire if this is ever revisited; this states that the silence is a decision.
        """
        self.assertNotIn("SAO", {key for _, key in shared._CSV_PREFIX_MAP})
        self.assertNotIn("SAO", shared._CSV_DESIG_KEYS)

    def test_the_designations_dict_gains_the_keys_on_the_lookup_path(self):
        desig, _ = _lookup_shaped("Procyon")
        self.assertEqual(desig["Bayer"], "* alf CMi")
        self.assertEqual(desig["Flamsteed"], "*  10 CMi")


class MainIdDedupeTest(unittest.TestCase):
    """AN2d / D3 — the duplicate is the COMMON case (16 of 43 stars), not an edge.

    Note the plan's headline figure, 22/43, is a DIFFERENT quantity — "main_id is a
    `* `-form string". The count that justifies D3 is "the chosen Bayer equals
    main_id", which is 16. `/code-review` (2026-07-29) caught 22 being reused for both.
    """

    def test_a_star_whose_main_id_is_its_bayer_renders_it_once(self):
        desig, joined = _lookup_shaped("Procyon")
        parts = joined.split(", ")
        self.assertEqual(len(parts), len(set(parts)), f"duplicate token in {joined!r}")
        self.assertEqual(parts.count("* alf CMi"), 1)
        self.assertTrue(joined.startswith("* alf CMi, "), "AN0c: MAIN_ID still leads")
        # Suppressed from the BANNER only — the key still reaches query.py's consumers.
        self.assertEqual(desig["Bayer"], "* alf CMi")

    def test_the_flamsteed_id_is_the_visible_payoff_on_such_a_star(self):
        """§4b: on a `* `-main_id star, D3 eats the Bayer and Flamsteed is the gain.

        `*  10 CMi` is never a main id, so it is new text on the banner. Stated as its
        own test because it reframes what this phase actually shows the user.
        """
        _, joined = _lookup_shaped("Procyon")
        self.assertIn("*  10 CMi", joined)

    def test_a_star_whose_main_id_is_NOT_a_bayer_still_shows_the_bayer(self):
        """Guards the obvious wrong implementation: "always drop Bayer".

        Proxima's main_id is `NAME Proxima Centauri`, so its Bayer id `* alf Cen C` is
        distinct and must render. Without this, suppressing the key unconditionally
        would pass every other assertion in this file.
        """
        desig, joined = _lookup_shaped("Proxima Centauri")
        self.assertEqual(desig["Bayer"], "* alf Cen C")
        self.assertIn("* alf Cen C", joined)
        self.assertTrue(joined.startswith("NAME Proxima Centauri, "))

    def test_the_dedupe_also_fires_on_stars_with_no_star_id(self):
        """The rule is "any repeated value", NOT "drop a Bayer that equals main_id".

        D3's framing is Bayer-specific, but main_id duplicates ordinary catalogue slots
        too: HD 209458's main id IS its HD number, so it used to render
        `HD 209458, HD 209458, HIP 108859, …`. 13 of the 43 corpus stars are deduped on
        this path with no `* ` id involved — a pre-existing display wart AN2 happens to
        fix, and a visible `desig_str` change on stars the Bayer/Flamsteed docs say
        nothing about. Raised by /code-review (2026-07-29); documented in
        docs/integration.md so a token-counting consumer isn't surprised.
        """
        desig, joined = _lookup_shaped("HD 209458")
        self.assertIsNone(desig["Bayer"], "premise: this star has no Bayer id")
        self.assertIsNone(desig["Flamsteed"])
        self.assertEqual(desig["MAIN_ID"], desig["HD"], "premise: main_id IS the HD id")
        self.assertEqual(joined.split(", ").count("HD 209458"), 1)

        affected = [s["query"] for s in _corpus()
                    if self._deduped(s["query"]) and not self._has_star_id(s["query"])]
        self.assertEqual(len(affected), 13, f"count moved — update the docs too: {affected}")

    def _has_star_id(self, query):
        desig, _ = _lookup_shaped(query)
        return bool(desig["Bayer"] or desig["Flamsteed"])

    def _deduped(self, query):
        """True when the dedupe actually removed a token for this star."""
        desig, joined = _lookup_shaped(query)
        keys = ["MAIN_ID"] + list(shared._CSV_DESIG_KEYS)
        naive = ", ".join(str(desig[k]) for k in keys if desig.get(k))
        return naive != joined

    def test_no_corpus_star_renders_any_repeated_token(self):
        for star in _corpus():
            with self.subTest(star=star["query"]):
                _, joined = _lookup_shaped(star["query"])
                parts = [p for p in joined.split(", ") if p]
                self.assertEqual(len(parts), len(set(parts)), joined)

    def test_the_dedupe_is_by_value_and_keeps_the_first_key(self):
        """States the mechanism directly, so a failure localises without a corpus.

        _join_designations knows nothing about MAIN_ID; it drops a repeated VALUE and
        keeps the first key that carried it. Because MAIN_ID leads the only key list
        containing it, that IS D3's "suppress the keyed copy".
        """
        desig = {"MAIN_ID": "* alf CMi", "NAME": "NAME Procyon", "Bayer": "* alf CMi"}
        keys = ["MAIN_ID", "NAME", "Bayer"]
        self.assertEqual(shared._join_designations(desig, keys),
                         "* alf CMi, NAME Procyon")
        # Reverse the order and the SURVIVOR flips — first key wins, not "not-Bayer".
        self.assertEqual(shared._join_designations(desig, ["Bayer", "NAME", "MAIN_ID"]),
                         "* alf CMi, NAME Procyon")

    def test_the_narrow_join_is_unaffected(self):
        """The dedupe must not perturb the ten narrow surfaces (AN0b order intact)."""
        desig = shared._match_designations(_ids_for("Procyon"), shared._NARROW_DESIG_KEYS)
        joined = shared._join_designations(desig, shared._NARROW_DESIG_KEYS)
        # Verbatim SIMBAD spacing, double spaces and component letter included —
        # this path stores raw ids too, and the golden harness pins the same string.
        self.assertEqual(joined, "NAME Procyon, HD  61421, HR  2943, GJ 280 A")


class Opt50BuilderTest(unittest.TestCase):
    """AN2c-T1 — the ONE self-firing trigger of the D4 deferral (plan §5 AN2c-T).

    D4 defers the opt-50 rebuild, so `star_systems.designations` keeps its old content
    until someone runs option 50. That deferral is only valid while the BUILDER is
    right and merely the stored data is stale. If these fail, the deferral is invalid:
    the code is wrong and a rebuild would not fix it. Stop and fix.
    """

    def test_the_shared_opt50_parser_emits_the_new_keys(self):
        joined = shared._parse_designations_from_ids("|".join(_ids_for("Procyon")))
        self.assertIn("* alf CMi", joined)
        self.assertIn("*  10 CMi", joined)

    def test_both_opt50_builders_still_agree(self):
        """CLI opt 50 and GUI opt 50 write the SAME star_systems.designations column.

        AN0 retired main.py's standalone copy for exactly this reason (D1(a)); the
        agreement is asserted over the whole corpus because AN2 is the first change
        that could have split them.
        """
        for star in _corpus():
            ids_string = "|".join(star["ids"])
            with self.subTest(star=star["query"]):
                self.assertEqual(cli_main._parse_designations_from_ids(ids_string),
                                 databases._parse_designations_from_ids(ids_string))

    def test_the_opt50_string_carries_no_main_id_and_so_needs_no_dedupe(self):
        """Why AN2d is a compute_simbad_lookup problem and not an opt-50 one.

        The opt-50 join key set has no MAIN_ID (the main id goes to the separate
        star_name column), so the duplicate D3 fixes cannot arise on this path.
        """
        self.assertNotIn("MAIN_ID", shared._CSV_DESIG_KEYS)
        for star in _corpus():
            parts = [p for p in shared._parse_designations_from_ids(
                "|".join(star["ids"])).split(", ") if p]
            with self.subTest(star=star["query"]):
                self.assertEqual(len(parts), len(set(parts)))

    def test_the_plx_discard_rule_still_sees_an_empty_string_for_an_id_less_star(self):
        """AN2c [R7] — adding keys makes desig_str non-empty for stars that captured
        nothing before, so the opt-50 `PLX ` discard rule keeps rows it used to drop.

        The rule tests `desig_str == ""`. A `* `-family id now produces a NON-empty
        string where it previously produced "", which is the delta AN2c says to
        re-measure at the next rebuild (T2). What must NOT change: a star with no
        capturable id at all still yields exactly "".
        """
        self.assertEqual(shared._parse_designations_from_ids("PLX 1234|Ci 20 1"), "")
        self.assertNotEqual(shared._parse_designations_from_ids("PLX 1234|*  18 Eri"), "")


class EmptyCaseTest(unittest.TestCase):
    """AN2e / D5 — the last §6 drift: copy 2's empty case becomes "" not "N/A".

    Needs the real function (the empty case is a property of compute_simbad_lookup's
    own join, not of the shared helpers), so unlike the rest of this file it drives the
    network + DB seams. Isolation mirrors the harness's _IsolatedDbTest.
    """

    def setUp(self):
        import shutil
        import tempfile
        import core.db as db
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (db._DB_PATH, db._conn, db._auto_seed)
        db._DB_PATH = pathlib.Path(self.tmpdir) / "an2e.db"
        db._conn = None
        db._auto_seed = lambda conn: None
        db.get_conn()
        self._db, self._shutil = db, shutil

    def tearDown(self):
        self._db.close_conn()
        self._db._DB_PATH, self._db._conn, self._db._auto_seed = self._saved
        self._shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _lookup(self, star_name, colnames, values, ids):
        from unittest import mock
        import astroquery.simbad as _aq
        from tests.test_designation_harness import _FakeTable, _FakeIdRow, _StubSimbad
        table = _FakeTable(colnames, values)
        rows = [_FakeIdRow(i) for i in ids]
        with mock.patch.object(databases, "_make_simbad", lambda *a, **k: _StubSimbad(table)), \
             mock.patch.object(_aq.Simbad, "query_objectids", staticmethod(lambda *a, **k: rows)), \
             mock.patch.object(databases, "Simbad", _aq.Simbad, create=True):
            return databases.compute_simbad_lookup(star_name)

    def test_a_star_with_nothing_capturable_yields_an_empty_string(self):
        """The literal "N/A" must never reach a consumer as data.

        Reaching this needs a blank name AND a resolving result — the case is latent,
        which is exactly why D5 called it safe to fix. Built synthetically because no
        real star can produce it.
        """
        out = self._lookup("", [], {}, ["Ci 20 1", "PLX 1234"])
        self.assertEqual(out["desig_str"], "")
        self.assertNotEqual(out["desig_str"], "N/A")

    def test_an_ordinary_star_is_completely_unaffected(self):
        star = _star("Procyon")
        out = self._lookup("Procyon", star["colnames"], star["row"], star["ids"])
        self.assertTrue(out["desig_str"].startswith("* alf CMi, NAME Procyon, "))

    def test_the_opt50_discard_rule_reads_a_DIFFERENT_value(self):
        """Corrects D5's stated rationale — PHASE_AN_PLAN.md [A6].

        D5 justified this fix by claiming the "N/A" defeats the opt-50 `PLX ` discard
        rule's `desig_str == ""` test. It cannot: that rule reads
        `_parse_designations_from_ids` inside `_run_simbad_csv_query`, a value that has
        always been "" and that this change does not touch. Pinned so the false
        mechanism cannot be re-derived from the plan — and so AN2c's "land D5 before
        re-measuring the PLX delta" ordering caveat stays retired.
        """
        self.assertEqual(shared._parse_designations_from_ids(""), "")
        self.assertEqual(shared._parse_designations_from_ids("PLX 1234|Ci 20 1"), "")
        src = pathlib.Path(databases.__file__).read_text(encoding="utf-8")
        rule = 'if main_id.startswith("PLX ") and desig_str == "" and sp_type == "":'
        self.assertIn(rule, src, "the discard rule moved — re-check which value it reads")


class NewKeyConsumerShapeTest(unittest.TestCase):
    """The AN4.5 sibling the plan requires for EVERY new key (§8.5, AO's lesson).

    A differential harness diffs outputs; it cannot see a producer emitting a shape no
    consumer can read. Phase AO shipped exactly that. So for each key AN2 introduces,
    assert that what the producer stores is what the known consumer expects.

    Bayer/Flamsteed have two consumers today and one arriving:
      · _join_designations   — needs a truthy string (covered above)
      · query.py             — needs it JSON-serialisable (a str, verified here)
      · AN3's display layer  — needs the RAW, round-trippable SIMBAD string: the `* `
                               prefix intact and D9's double space NOT stripped, since
                               the plan makes the raw string the identifier (§7a).
    """

    def test_stored_values_are_the_verbatim_simbad_string(self):
        desig, _ = _lookup_shaped("eps Eri")
        self.assertEqual(desig["Flamsteed"], "*  18 Eri", "D9: double space kept verbatim")
        self.assertEqual(desig["Bayer"], "* eps Eri")

    def test_every_stored_value_round_trips_through_the_classifier(self):
        """The producer/consumer contract, stated as an invariant over the corpus.

        Whatever lands in Bayer/Flamsteed must classify back to that same key — which
        is precisely what AN3 will do to decide how to render it.
        """
        for star in _corpus():
            desig, _ = _lookup_shaped(star["query"])
            for key in ("Bayer", "Flamsteed"):
                val = desig[key]
                if val is None:
                    continue
                with self.subTest(star=star["query"], key=key):
                    self.assertIsInstance(val, str)
                    self.assertTrue(val.startswith("* "))
                    self.assertEqual(shared._classify_star_id(val), key)

    def test_the_hd_slot_is_untouched_so_gould_still_resolves(self):
        """AN4.5's own pin lives in the harness; this is the cheap local restatement.

        Inserting keys ahead of HD in the list must not change what the HD slot HOLDS —
        _simbad_gould_block parses the integer back out of "HD 102365".
        """
        desig, _ = _lookup_shaped("HD 102365")
        self.assertEqual(desig["HD"], "HD 102365")


if __name__ == "__main__":
    unittest.main()
