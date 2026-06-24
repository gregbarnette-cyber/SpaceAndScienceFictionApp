# tests/test_projects.py — Phase S-C1: project workspaces CRUD (core/projects.py).
#
# Offline, against a tmp DB (the test_db_backups.py isolation pattern: monkeypatch
# core.db._DB_PATH/_conn/_auto_seed). The projects/project_members tables are
# created by _create_schema regardless of auto-seed. The generated-member
# round-trip class leaves auto-seed ON so generate_system has its main-sequence
# reference table.

import pathlib
import shutil
import tempfile
import unittest

import core.db as db
import core.projects as projects


class _TmpDbCase(unittest.TestCase):
    AUTO_SEED = False

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (db._DB_PATH, db._conn, db._auto_seed)
        db._DB_PATH = pathlib.Path(self.tmpdir) / "test.db"
        db._conn = None
        if not self.AUTO_SEED:
            db._auto_seed = lambda conn: None
        db.get_conn()

    def tearDown(self):
        db.close_conn()
        db._DB_PATH, db._conn, db._auto_seed = self._saved
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class ProjectCrudTest(_TmpDbCase):

    def test_create_and_list(self):
        r = projects.create_project("Novel", "a setting")
        self.assertNotIn("error", r)
        self.assertEqual(r["name"], "Novel")
        self.assertEqual(r["member_count"], 0)
        lst = projects.list_projects()
        self.assertEqual([p["name"] for p in lst], ["Novel"])
        self.assertEqual(lst[0]["member_count"], 0)

    def test_create_blank_and_duplicate(self):
        self.assertIn("error", projects.create_project("   "))
        projects.create_project("Dup")
        self.assertIn("error", projects.create_project("Dup"))

    def test_list_sorted_caseinsensitive(self):
        for n in ["zeta", "Alpha", "mu"]:
            projects.create_project(n)
        self.assertEqual([p["name"] for p in projects.list_projects()],
                         ["Alpha", "mu", "zeta"])

    def test_add_member_and_get(self):
        projects.create_project("P")
        r = projects.add_member("P", "Tau Ceti", note="capital")
        self.assertEqual(r["star_name"], "Tau Ceti")
        got = projects.get_project("P")
        self.assertEqual(got["project"]["name"], "P")
        self.assertEqual(len(got["members"]), 1)
        m = got["members"][0]
        self.assertEqual(m["star_name"], "Tau Ceti")
        self.assertEqual(m["note"], "capital")
        self.assertEqual(m["source"], "looked_up")
        self.assertEqual(projects.list_projects()[0]["member_count"], 1)

    def test_add_member_unknown_project_and_blank_star(self):
        self.assertIn("error", projects.add_member("Nope", "Tau Ceti"))
        projects.create_project("P")
        self.assertIn("error", projects.add_member("P", "   "))
        self.assertIn("error", projects.add_member("P", "x", source="bogus"))

    def test_add_member_idempotent_update(self):
        # Re-adding the same logical member updates note/spec, no duplicate.
        projects.create_project("P")
        projects.add_member("P", "Tau Ceti", note="v1")
        projects.add_member("P", "Tau Ceti", note="v2")
        got = projects.get_project("P")
        self.assertEqual(len(got["members"]), 1)
        self.assertEqual(got["members"][0]["note"], "v2")

    def test_collision_suffix_for_distinct_generated(self):
        # Two DIFFERENT generated members named Gen-88 (different seed) → suffix.
        projects.create_project("P")
        r1 = projects.add_member("P", "Gen-88", source="generated", seed=88,
                                 spec={"seed": 88})
        r2 = projects.add_member("P", "Gen-88", source="generated", seed=99,
                                 spec={"seed": 99})
        self.assertEqual(r1["star_name"], "Gen-88")
        self.assertEqual(r2["star_name"], "Gen-88 (2)")
        self.assertEqual(len(projects.get_project("P")["members"]), 2)

    def test_generated_same_seed_is_idempotent(self):
        projects.create_project("P")
        projects.add_member("P", "Gen-88", source="generated", seed=88, spec={"seed": 88})
        r = projects.add_member("P", "Gen-88", source="generated", seed=88, spec={"seed": 88})
        self.assertEqual(r["star_name"], "Gen-88")
        self.assertEqual(len(projects.get_project("P")["members"]), 1)

    def test_update_note(self):
        projects.create_project("P")
        projects.add_member("P", "Sol")
        self.assertNotIn("error", projects.update_note("P", "Sol", "home"))
        self.assertEqual(projects.get_project("P")["members"][0]["note"], "home")
        self.assertIn("error", projects.update_note("P", "Nobody", "x"))
        self.assertIn("error", projects.update_note("Nope", "Sol", "x"))

    def test_remove_member_idempotent(self):
        projects.create_project("P")
        projects.add_member("P", "Sol")
        self.assertTrue(projects.remove_member("P", "Sol")["removed"])
        self.assertFalse(projects.remove_member("P", "Sol")["removed"])   # no-op, no error
        self.assertEqual(len(projects.get_project("P")["members"]), 0)

    def test_rename_project(self):
        projects.create_project("Old")
        projects.create_project("Taken")
        self.assertIn("error", projects.rename_project("Old", "Taken"))   # duplicate
        self.assertIn("error", projects.rename_project("Old", "  "))      # blank
        self.assertIn("error", projects.rename_project("Ghost", "New"))   # unknown
        self.assertEqual(projects.rename_project("Old", "New")["name"], "New")
        self.assertEqual({p["name"] for p in projects.list_projects()}, {"New", "Taken"})

    def test_delete_project_cascades(self):
        projects.create_project("P")
        projects.add_member("P", "Sol")
        projects.add_member("P", "Tau Ceti")
        self.assertIn("error", projects.delete_project("Ghost"))
        self.assertTrue(projects.delete_project("P")["deleted"])
        self.assertEqual(projects.list_projects(), [])
        # members are gone too (cascade)
        conn = db.get_conn()
        n = conn.execute("SELECT COUNT(*) FROM project_members").fetchone()[0]
        self.assertEqual(n, 0)

    def test_get_unknown_project(self):
        self.assertIn("error", projects.get_project("Nope"))

    def test_table_status_lists_projects(self):
        labels = {r["table"] for r in db.get_table_status()}
        self.assertIn("Projects", labels)
        self.assertIn("Project Members", labels)


class GeneratedMemberRoundTrip(_TmpDbCase):
    AUTO_SEED = True   # generate_system needs the seeded main_sequence_stars table

    def _gen(self, spec):
        from core.generate import generate_system
        return generate_system(
            spec["seed"], anchor_star=spec.get("anchor_star"),
            spectral_class=spec.get("spectral_class"), n_planets=spec.get("n_planets"),
            research_policy=spec.get("research_policy", "permissive"))

    def test_spec_round_trips_and_regenerates_identically(self):
        spec = {"seed": 88, "mode": "synthetic", "spectral_class": "K2V",
                "n_planets": 5, "anchor_star": None, "constraints": None,
                "companion": None, "research_policy": "permissive"}
        original = self._gen(spec)
        self.assertNotIn("error", original)

        projects.create_project("P")
        projects.add_member("P", original["star"]["name"], source="generated",
                            seed=spec["seed"], spec=spec)
        stored = projects.get_project("P")["members"][0]["generated_spec"]
        # (a) the spec survives the DB JSON round-trip intact
        self.assertEqual(stored, spec)
        # (b) re-generating from the stored spec is byte-identical (R determinism)
        self.assertEqual(self._gen(stored), original)


if __name__ == "__main__":
    unittest.main()
