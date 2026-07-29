# tests/test_designation_harness.py — AN4.1, the Phase AN differential harness.
#
# PURPOSE: prove that AN0's consolidation of the six drifted designation parsers
# (PHASE_AN_PLAN.md §2) is byte-identical, at the four in-scope call sites — of
# which THREE have zero coverage today (§8). This is the phase's primary safety
# net; the plan is explicit that AN0 must not start without it, because it cannot
# be built after the refactor it exists to verify.
#
# HOW IT WORKS
#   1. tests/fixtures/designation_ids.json (AN4.0) holds 43 real SIMBAD id lists,
#      captured live once. Nothing here touches the network.
#   2. Fake astropy-shaped table/row objects replay those into the REAL parsers —
#      the point is to execute each copy's own inline loop, not a reimplementation.
#   3. Every producer's output is recorded into a single dict and compared against
#      the committed golden baseline, tests/fixtures/designation_golden.json.
#
# REGENERATING THE BASELINE
#       AN_REGEN_GOLDEN=1 venv/bin/python -m pytest tests/test_designation_harness.py
#   Do this ONLY when a diff is an intended, adjudicated §6 decision — then commit
#   the regenerated file IN THE SAME COMMIT as the code change, so review sees both.
#   A silent regen defeats the entire harness.
#
# WHAT THIS CANNOT CATCH (read before trusting it — PHASE_AN_PLAN.md [A2]):
#   A change that leaves these outputs identical but breaks a DOWNSTREAM consumer's
#   assumed input shape. Phase AO shipped exactly that class of bug (an unreachable
#   SAO branch, green tests, working feature). AN4.5 below is the counter-measure
#   for the one known case; add a sibling for each new key AN introduces.

import copy
import json
import os
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

import core.calculators as calculators
import core.databases as databases
import core.db as db
import core.shared as shared

_FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
_CORPUS_PATH = _FIXTURES / "designation_ids.json"
_GOLDEN_PATH = _FIXTURES / "designation_golden.json"
_GOULD_CSV = pathlib.Path(__file__).resolve().parents[1] / "gouldDesignations.csv"

_REGEN = os.environ.get("AN_REGEN_GOLDEN") == "1"


# ── Fake astropy shapes ───────────────────────────────────────────────────────
# Deliberately hand-rolled rather than pickled astropy Tables: the parsers only
# need .colnames, len(), [0] and row[col], and a pickle would couple the corpus to
# an astropy version. A captured None means "masked or sentinel" — the capture
# script already applied the same _safe() rules the parsers use.

class _FakeRow:
    def __init__(self, values):
        self._values = values

    def __getitem__(self, col):
        v = self._values.get(col)
        return "" if v is None else v


class _FakeTable:
    """Supports BOTH indexing styles the copies use — this is not incidental.

    shared._parse_designations reads column-first (`result["main_id"][0]`, astropy
    Table semantics); databases and calculators read row-first (`result[0]` then
    `row[col]`). A fake that supported only one would silently exclude a copy from
    the harness.
    """

    def __init__(self, colnames, values):
        self.colnames = list(colnames)
        self._values = dict(values)
        self._row = _FakeRow(values)

    def __len__(self):
        return 1

    def __getitem__(self, idx):
        if isinstance(idx, str):            # column-first: result["main_id"] -> [value]
            v = self._values.get(idx)
            return ["" if v is None else v]
        if idx == 0:                        # row-first: result[0] -> row
            return self._row
        raise IndexError(idx)


class _FakeIdRow:
    def __init__(self, id_str):
        self._id = id_str

    def __getitem__(self, key):
        if key == "id":
            return self._id
        raise KeyError(key)


def _load_corpus():
    with open(_CORPUS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _tables_for(star):
    """(result, ids_result, ids_string) for one corpus entry."""
    result = _FakeTable(star["colnames"], star["row"])
    ids_result = [_FakeIdRow(i) for i in star["ids"]]
    ids_string = "|".join(star["ids"])
    return result, ids_result, ids_string


class _StubSimbad:
    """Stands in for the object _make_simbad returns."""

    def __init__(self, table):
        self._table = table

    def query_object(self, name, *a, **kw):
        return self._table

    def add_votable_fields(self, *a, **kw):
        pass


def _record_for_star(star):
    """Run every in-scope producer over one fixture star."""
    result, ids_result, ids_string = _tables_for(star)
    rec = {}

    # ── Copy 1 — core/shared.py, the canonical pair ──────────────────────────
    rec["shared_parse_designations"] = shared._parse_designations(result, ids_result)
    rec["shared_parse_from_ids"] = shared._parse_designations_from_ids(ids_string)

    # ── Copy 2 — databases.compute_simbad_lookup's inline map (:315-365) ─────
    # Patched at the two network seams so the REAL parser body executes.
    import astroquery.simbad as _aq

    with mock.patch.object(databases, "_make_simbad", lambda *a, **k: _StubSimbad(result)), \
         mock.patch.object(_aq.Simbad, "query_objectids", staticmethod(lambda *a, **k: ids_result)), \
         mock.patch.object(databases, "Simbad", _aq.Simbad, create=True):
        out = databases.compute_simbad_lookup(star["query"])
    rec["simbad_lookup_designations"] = out.get("designations")
    rec["simbad_lookup_desig_str"] = out.get("desig_str")
    rec["simbad_lookup_main_id"] = out.get("main_id")
    rec["simbad_lookup_error"] = out.get("error")

    # ── Copy 4 — calculators.compute_lookup_star_for_distance (narrow) ───────
    with mock.patch.object(calculators, "_make_simbad", lambda *a, **k: _StubSimbad(result)), \
         mock.patch.object(_aq.Simbad, "query_objectids", staticmethod(lambda *a, **k: ids_result)):
        out4 = calculators.compute_lookup_star_for_distance(star["query"])
    rec["calculators_desig_str"] = out4.get("desig_str")
    rec["calculators_error"] = out4.get("error")

    # ── Copy 5 — main.py's standalone opt-50 parser (in scope per D1(a)) ─────
    # main.py has NO test coverage at all today (§8); this is its first.
    import main as cli_main
    rec["main_opt50_parse_from_ids"] = cli_main._parse_designations_from_ids(ids_string)

    return rec


def _build_all():
    corpus = _load_corpus()
    return {s["query"]: _record_for_star(s) for s in corpus["stars"]}


class _IsolatedDbTest(unittest.TestCase):
    """compute_simbad_lookup reads the DB (gcns + gould blocks) — isolate it.

    Static seeding is disabled, so both blocks find empty/missing tables and return
    None. That is the correct baseline for a DESIGNATION harness: it must diff the
    parser, not the DB contents. AN4.5 below seeds deliberately, for the opposite
    reason.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (db._DB_PATH, db._conn, db._auto_seed)
        db._DB_PATH = pathlib.Path(self.tmpdir) / "harness.db"
        db._conn = None
        db._auto_seed = lambda conn: None
        db.get_conn()

    def tearDown(self):
        db.close_conn()
        db._DB_PATH, db._conn, db._auto_seed = self._saved
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class DesignationDifferentialTest(_IsolatedDbTest):
    """AN4.1 — the byte-identical baseline. Replay after every AN0 commit."""

    def test_all_producers_match_the_golden_baseline(self):
        actual = _build_all()

        if _REGEN:
            payload = {
                "_comment": (
                    "AN4.1 golden baseline — outputs of every in-scope designation "
                    "producer over tests/fixtures/designation_ids.json. Regenerate ONLY "
                    "for an adjudicated change (PHASE_AN_PLAN.md §6) and commit the diff "
                    "alongside the code change: AN_REGEN_GOLDEN=1 python -m pytest "
                    "tests/test_designation_harness.py"
                ),
                "star_count": len(actual),
                "results": actual,
            }
            with open(_GOLDEN_PATH, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=1, ensure_ascii=False)
                fh.write("\n")
            self.skipTest(f"regenerated golden baseline ({len(actual)} stars)")

        self.assertTrue(
            _GOLDEN_PATH.exists(),
            "golden baseline missing — run with AN_REGEN_GOLDEN=1 once, then commit it",
        )
        with open(_GOLDEN_PATH, encoding="utf-8") as fh:
            golden = json.load(fh)["results"]

        self.assertEqual(
            sorted(golden), sorted(actual),
            "fixture corpus and golden baseline disagree on which stars they cover",
        )
        for name in sorted(golden):
            with self.subTest(star=name):
                self.assertEqual(
                    golden[name], actual[name],
                    f"designation output changed for {name!r} — if this is an intended "
                    f"§6 decision, regenerate the baseline in the same commit",
                )

    def test_corpus_covers_every_shape_an1_must_classify(self):
        """A shrunken corpus would weaken the harness silently. Pin the coverage."""
        corpus = _load_corpus()
        seen = {"bayer": 0, "flamsteed": 0, "double": 0, "variable": 0}
        for star in corpus["stars"]:
            for i in star["ids"]:
                if i.startswith("** "):
                    seen["double"] += 1
                elif i.startswith("V* "):
                    seen["variable"] += 1
                elif i.startswith("* "):
                    tok = i[2:].split()
                    seen["flamsteed" if tok and tok[0].isdigit() else "bayer"] += 1
        self.assertGreaterEqual(len(corpus["stars"]), 40)
        for shape, n in seen.items():
            with self.subTest(shape=shape):
                self.assertGreater(n, 0, f"corpus has no {shape} ids — AN1 would be untested")


class NarrowCopyOrderTest(_IsolatedDbTest):
    """AN0b [R4] — the narrow copies' key ORDER, which a naive fix reorders.

    calculators.py:284 joins dict VALUES, so order is desig_found's insertion order
    (NAME, HD, HR, GJ, Wolf). Deriving it by filtering shared._CSV_PREFIX_MAP would
    yield NAME, GJ, HD, HR, Wolf — moving GJ 4th→2nd on ten surfaces. The plan says
    to pass an explicit ordered key list; this fails if anyone does it the easy way.
    """

    def test_narrow_desig_str_order_is_name_hd_hr_gj_wolf(self):
        corpus = _load_corpus()
        star = next(s for s in corpus["stars"] if s["query"] == "Procyon")
        result, ids_result, _ = _tables_for(star)
        import astroquery.simbad as _aq

        with mock.patch.object(calculators, "_make_simbad", lambda *a, **k: _StubSimbad(result)), \
             mock.patch.object(_aq.Simbad, "query_objectids",
                               staticmethod(lambda *a, **k: ids_result)):
            out = calculators.compute_lookup_star_for_distance("Procyon")

        parts = [p.split()[0] for p in out["desig_str"].split(", ") if p]
        order = [p for p in parts if p in ("NAME", "HD", "HR", "GJ", "Wolf")]
        self.assertEqual(order, sorted(order, key=["NAME", "HD", "HR", "GJ", "Wolf"].index))
        self.assertLess(parts.index("HD"), parts.index("GJ"),
                        "HD must precede GJ in the narrow copies (AN0b [R4])")


class SharedMapGuardTest(unittest.TestCase):
    """AN0a [R3] — the hard ordering constraint, as an executable pin.

    Copies 2/3/5 match with no `key in designations` guard, so a new entry in the
    shared map raises KeyError in any copy pointed at it. shared's own parsers ARE
    guarded; this proves it, so AN0's convergence has a target to preserve.
    """

    def test_shared_parsers_survive_a_new_prefix_entry(self):
        synthetic = ("Bayer* ", "SyntheticAN0aKey")
        patched = list(shared._CSV_PREFIX_MAP) + [synthetic]
        ids = "Bayer* zzz|HD 1|NAME Test"

        with mock.patch.object(shared, "_CSV_PREFIX_MAP", patched):
            out = shared._parse_designations_from_ids(ids)
            table = _FakeTable(["main_id"], {"main_id": "* zzz"})
            rows = [_FakeIdRow(i) for i in ids.split("|")]
            desig = shared._parse_designations(table, rows)

        self.assertIn("HD 1", out)
        self.assertNotIn("SyntheticAN0aKey", desig,
                         "the new key must be skipped, not inserted, by the guard")

    def test_unguarded_copies_are_still_unguarded(self):
        """Documents the hazard rather than asserting it away.

        If this starts failing, a copy grew a guard — good news, and the AN0a
        ordering constraint may be relaxable. Verify before deleting.
        """
        import inspect
        src = inspect.getsource(databases.compute_simbad_lookup)
        self.assertIn("and designations[key] is None", src)
        self.assertNotIn("key in designations and", src,
                         "databases copy #2 grew a guard — revisit AN0a")


class GouldConsumerPinTest(unittest.TestCase):
    """AN4.5 — the producer/consumer pin the differential harness CANNOT provide.

    _simbad_gould_block reads designations["HD"] and parses the integer out of the
    "HD 102365" string form. An AN0 refactor that stores a bare 102365 there would
    return None for every Gould lookup: no exception, no output diff in the harness
    (designations itself is unchanged), no failing test. This asserts the DOWNSTREAM
    effect instead — the shape of check that would have caught Phase AO's dead SAO
    branch. Seeds the real catalogue, unlike the harness fixtures above.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (db._DB_PATH, db._conn, db._auto_seed)
        db._DB_PATH = pathlib.Path(self.tmpdir) / "gould.db"
        db._conn = None
        db._auto_seed = lambda conn: None
        self.conn = db.get_conn()
        db._seed_gould(self.conn, _GOULD_CSV)
        self.conn.commit()

    def tearDown(self):
        db.close_conn()
        db._DB_PATH, db._conn, db._auto_seed = self._saved
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _lookup(self, query):
        star = next(s for s in _load_corpus()["stars"] if s["query"] == query)
        result, ids_result, _ = _tables_for(star)
        import astroquery.simbad as _aq
        with mock.patch.object(databases, "_make_simbad", lambda *a, **k: _StubSimbad(result)), \
             mock.patch.object(_aq.Simbad, "query_objectids",
                               staticmethod(lambda *a, **k: ids_result)):
            return databases.compute_simbad_lookup(query)

    def test_gould_still_resolves_through_the_designations_dict(self):
        for query, expected in (("HD 102365", "66 G. Centauri"),
                                ("HD 100623", "289 G. Hydrae")):
            with self.subTest(star=query):
                out = self._lookup(query)
                gould = out.get("gould")
                self.assertIsNotNone(
                    gould,
                    f"{query}: gould went None — AN0 likely changed the SHAPE of "
                    f"designations['HD'] (the block parses the int out of 'HD 102365'). "
                    f"The differential harness cannot see this; see PHASE_AN_PLAN.md [A2]",
                )
                self.assertEqual(gould["display"], expected)

    def test_the_hd_slot_still_holds_the_prefixed_string_form(self):
        """States the contract directly, so the failure message is unambiguous."""
        out = self._lookup("HD 102365")
        self.assertEqual(out["designations"]["HD"], "HD 102365")


if __name__ == "__main__":
    unittest.main()
