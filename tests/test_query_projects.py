# tests/test_query_projects.py — Phase S-C3: query.py project-list / project-get.
#
# Read-only subprocess contract (mutations are GUI-only). Each test seeds a tmp
# DB in-process (via core.projects, pointing core.db._DB_PATH at the file), then
# runs query.py against the same DB via SPACE_APP_DB. Mirrors the
# tests/test_query_generate.py harness.

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from tests._queryharness import run_query

_REPO = pathlib.Path(__file__).resolve().parent.parent


class _QueryProjectsCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db = str(pathlib.Path(self.tmpdir) / "proj.db")
        self.env = {"SPACE_APP_DB": self.db, "PATH": os.environ.get("PATH", ""),
                    "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _seed(self, fn):
        """Run fn() with core.db pointed at our tmp DB (auto-seed off)."""
        import core.db as db
        saved = (db._DB_PATH, db._conn, db._auto_seed)
        db._DB_PATH = pathlib.Path(self.db)
        db._conn = None
        db._auto_seed = lambda conn: None
        try:
            import core.projects as projects   # get_conn reads core.db's patched globals
            fn(projects)
        finally:
            db.close_conn()
            db._DB_PATH, db._conn, db._auto_seed = saved

    def _run(self, *args):
        return run_query(*args, env=self.env)


class ProjectList(_QueryProjectsCase):
    def test_empty(self):
        code, payload, _ = self._run("project-list")
        self.assertEqual(code, 0)
        self.assertEqual(payload, {"projects": []})

    def test_lists_with_member_count(self):
        def seed(projects):
            projects.create_project("Novel", "a setting")
            projects.add_member("Novel", "Tau Ceti", note="capital")
            projects.create_project("Campaign")
        self._seed(seed)
        code, payload, _ = self._run("project-list")
        self.assertEqual(code, 0)
        names = {p["name"]: p for p in payload["projects"]}
        self.assertEqual(set(names), {"Novel", "Campaign"})
        self.assertEqual(names["Novel"]["member_count"], 1)
        self.assertEqual(names["Campaign"]["member_count"], 0)


class ProjectGet(_QueryProjectsCase):
    def test_happy_with_parsed_spec(self):
        spec = {"seed": 88, "mode": "synthetic", "spectral_class": "K2V", "n_planets": 5}

        def seed(projects):
            projects.create_project("P")
            projects.add_member("P", "Tau Ceti", note="real one")
            projects.add_member("P", "Gen-88", note="proc", source="generated",
                                seed=88, spec=spec)
        self._seed(seed)
        code, payload, _ = self._run("project-get", "--name", "P")
        self.assertEqual(code, 0)
        self.assertEqual(payload["project"]["name"], "P")
        members = {m["star_name"]: m for m in payload["members"]}
        self.assertEqual(set(members), {"Tau Ceti", "Gen-88"})
        self.assertEqual(members["Tau Ceti"]["source"], "looked_up")
        gen = members["Gen-88"]
        self.assertEqual(gen["source"], "generated")
        # generated_spec echoed as a parsed JSON object (not a string)
        self.assertIsInstance(gen["generated_spec"], dict)
        self.assertEqual(gen["generated_spec"], spec)

    def test_unknown_name_exit1(self):
        code, payload, _ = self._run("project-get", "--name", "Ghost")
        self.assertEqual(code, 1)
        self.assertIn("error", payload)

    def test_missing_name_exit2(self):
        code, payload, err = self._run("project-get")
        self.assertEqual(code, 2)
        self.assertIsNone(payload)


if __name__ == "__main__":
    unittest.main()
