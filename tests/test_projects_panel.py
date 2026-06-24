# tests/test_projects_panel.py — Phase S-C4: ProjectPanel GUI smoke (offscreen).
# Skipped if PySide6 is absent. Uses a tmp DB with auto-seed ON so the generated-
# member "Open" path can run generate_system against the seeded main_sequence_stars.

import os
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QDialog
    _GUI_OK = True
except Exception:
    _GUI_OK = False

import json

import core.db as db
import core.projects as projects
import core.report as report


class _FakeNav:
    def show(self): pass
    def hide(self): pass


class _FakeWindow:
    def __init__(self):
        self.nav_tree = _FakeNav()

    def statusBar(self):
        class _SB:
            def showMessage(self, *a): pass
        return _SB()


@unittest.skipUnless(_GUI_OK, "PySide6 not available")
class ProjectPanelSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (db._DB_PATH, db._conn)
        db._DB_PATH = pathlib.Path(self.tmpdir) / "p.db"
        db._conn = None
        db.get_conn()   # auto-seed ON → reference tables for generate_system

    def tearDown(self):
        db.close_conn()
        db._DB_PATH, db._conn = self._saved
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _panel(self):
        from gui.panels.projects import ProjectPanel
        return ProjectPanel(_FakeWindow())

    def test_constructs_empty(self):
        p = self._panel()
        self.assertEqual(p._proj_list.count(), 0)
        self.assertFalse(p._export_btn.isEnabled())

    def test_create_via_handler_selects(self):
        p = self._panel()
        with mock.patch("gui.panels.projects.QInputDialog.getText",
                        return_value=("Novel", True)):
            p._new_project()
        self.assertEqual(p._proj_list.count(), 1)
        self.assertEqual(p._current, "Novel")
        self.assertIn("Novel", p._detail_header.text())

    def test_select_populates_members(self):
        projects.create_project("P")
        projects.add_member("P", "Tau Ceti", note="capital")
        projects.add_member("P", "Gen-88", source="generated", seed=88,
                            spec={"seed": 88, "spectral_class": "K2V", "n_planets": 5})
        p = self._panel()
        p._reload_projects(select="P")
        self.assertEqual(p._members.rowCount(), 2)
        self.assertTrue(p._export_btn.isEnabled())
        # source labels
        labels = {p._members.item(r, 0).text(): p._members.item(r, 2).text()
                  for r in range(p._members.rowCount())}
        self.assertEqual(labels["Tau Ceti"], "looked-up")
        self.assertIn("generated", labels["Gen-88"])

    def test_inline_note_edit_persists(self):
        projects.create_project("P")
        projects.add_member("P", "Sol", note="old")
        p = self._panel()
        p._reload_projects(select="P")
        p._members.item(0, 1).setText("new note")     # fires cellChanged
        self.assertEqual(projects.get_project("P")["members"][0]["note"], "new note")

    def test_remove_member(self):
        projects.create_project("P")
        projects.add_member("P", "Sol")
        p = self._panel()
        p._reload_projects(select="P")
        self.assertEqual(p._members.rowCount(), 1)
        p._remove_member("Sol")
        self.assertEqual(p._members.rowCount(), 0)
        self.assertEqual(len(projects.get_project("P")["members"]), 0)

    def test_open_generated_recreates(self):
        projects.create_project("P")
        spec = {"seed": 88, "mode": "synthetic", "spectral_class": "K2V", "n_planets": 5}
        projects.add_member("P", "Gen-88", source="generated", seed=88, spec=spec)
        p = self._panel()
        p._reload_projects(select="P")
        dlg = p._open_member("Gen-88")
        self.assertIsInstance(dlg, QDialog)
        self.assertIn(dlg, p._dialogs)

    def test_open_real_dispatches_without_network(self):
        projects.create_project("P")
        projects.add_member("P", "Tau Ceti")
        p = self._panel()
        p._reload_projects(select="P")
        with mock.patch.object(p, "_open_real") as m:
            p._open_member("Tau Ceti")
            m.assert_called_once_with("Tau Ceti")

    def test_rename_via_handler(self):
        projects.create_project("Old")
        p = self._panel()
        p._reload_projects(select="Old")
        with mock.patch("gui.panels.projects.QInputDialog.getText",
                        return_value=("New", True)):
            p._rename_project()
        self.assertEqual(p._current, "New")
        self.assertEqual({x["name"] for x in projects.list_projects()}, {"New"})

    def test_delete_via_handler(self):
        projects.create_project("Doomed")
        p = self._panel()
        p._reload_projects(select="Doomed")
        from gui.panels.projects import QMessageBox
        with mock.patch("gui.panels.projects.QMessageBox.question",
                        return_value=QMessageBox.StandardButton.Yes):
            p._delete_project()
        self.assertEqual(projects.list_projects(), [])
        self.assertEqual(p._proj_list.count(), 0)

    def test_nav_and_export(self):
        from gui.nav import NAVIGATION
        cats = dict(NAVIGATION)
        self.assertIn("Projects", cats)
        self.assertIn(("Project Workspace", "ProjectPanel"), cats["Projects"])
        import gui.panels as panels
        self.assertTrue(hasattr(panels, "ProjectPanel"))

    # ── S-C5 export ──
    def test_export_dialog_values(self):
        from gui.panels.projects import _ExportDialog
        d = _ExportDialog()
        fmt, combined, sections = d.values()
        self.assertEqual(fmt, "markdown")
        self.assertTrue(combined)
        self.assertIsNone(sections)                 # all checked → None (= all)
        d._sec_boxes["gcns"].setChecked(False)
        _, _, secs = d.values()
        self.assertIn("identity", secs)
        self.assertNotIn("gcns", secs)

    def test_write_export_combined_file(self):
        p = self._panel()
        p._export_fmt = "markdown"
        out = os.path.join(self.tmpdir, "out.md")
        n = p._write_export({"document": "# hi"}, "file", out)
        self.assertEqual(n, 1)
        with open(out, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "# hi")

    def test_write_export_combined_json(self):
        p = self._panel()
        p._export_fmt = "json"
        out = os.path.join(self.tmpdir, "out.json")
        p._write_export({"data": {"x": 1}}, "file", out)
        with open(out, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), {"x": 1})

    def test_write_export_per_file_skips_failed(self):
        p = self._panel()
        p._export_fmt = "markdown"
        d = os.path.join(self.tmpdir, "outdir")
        os.makedirs(d)
        result = {"members": [
            {"star_name": "Tau Ceti", "ok": True, "document": "a"},
            {"star_name": "Bad/Name", "ok": False, "error": "nope"},
        ]}
        n = p._write_export(result, "dir", d)
        self.assertEqual(n, 1)
        self.assertTrue(os.path.exists(os.path.join(d, "Tau_Ceti.md")))

    def test_export_schedules_build(self):
        projects.create_project("P")
        projects.add_member("P", "Tau Ceti")
        p = self._panel()
        p._reload_projects(select="P")
        out = os.path.join(self.tmpdir, "o.md")
        with mock.patch("gui.panels.projects._ExportDialog") as D, \
             mock.patch("gui.panels.projects.QFileDialog.getSaveFileName",
                        return_value=(out, "")), \
             mock.patch.object(p, "run_in_background") as rib:
            inst = D.return_value
            inst.exec.return_value = QDialog.DialogCode.Accepted
            inst.values.return_value = ("markdown", True, None)
            p._export()
            rib.assert_called_once()
            self.assertIs(rib.call_args.args[0], report.build_project_dossier)
            self.assertEqual(rib.call_args.args[1], "P")


@unittest.skipUnless(_GUI_OK, "PySide6 not available")
class AddToProjectAndStatus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._saved = (db._DB_PATH, db._conn)
        db._DB_PATH = pathlib.Path(self.tmpdir) / "p.db"
        db._conn = None
        db.get_conn()

    def tearDown(self):
        db.close_conn()
        db._DB_PATH, db._conn = self._saved
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ── choose_and_add helper ──
    def test_choose_and_add_existing(self):
        from gui.panels.projects import choose_and_add
        projects.create_project("P")
        with mock.patch("gui.panels.projects.QInputDialog.getItem",
                        return_value=("P", True)), \
             mock.patch("gui.panels.projects.QMessageBox.information"):
            out = choose_and_add(None, "Tau Ceti", source="looked_up")
        self.assertEqual(out, "P")
        self.assertEqual(len(projects.get_project("P")["members"]), 1)

    def test_choose_and_add_new(self):
        from gui.panels.projects import choose_and_add
        with mock.patch("gui.panels.projects.QInputDialog.getItem",
                        return_value=("<New project…>", True)), \
             mock.patch("gui.panels.projects.QInputDialog.getText",
                        return_value=("Fresh", True)), \
             mock.patch("gui.panels.projects.QMessageBox.information"):
            out = choose_and_add(None, "Sol", source="looked_up")
        self.assertEqual(out, "Fresh")
        self.assertEqual(projects.get_project("Fresh")["members"][0]["star_name"], "Sol")

    def test_choose_and_add_cancel(self):
        from gui.panels.projects import choose_and_add
        with mock.patch("gui.panels.projects.QInputDialog.getItem",
                        return_value=("", False)):
            self.assertIsNone(choose_and_add(None, "Sol"))

    # ── SimbadPanel entry point ──
    def test_simbad_add_button(self):
        from gui.panels.simbad import SimbadPanel
        p = SimbadPanel(_FakeWindow())
        self.assertFalse(p._add_proj_btn.isEnabled())
        p.render({"error": "no match"})
        self.assertFalse(p._add_proj_btn.isEnabled())
        p.render({"main_id": "Vega", "desig_str": "Vega", "designations": {}})
        self.assertTrue(p._add_proj_btn.isEnabled())
        with mock.patch("gui.panels.projects.choose_and_add") as m:
            p._add_to_project()
            m.assert_called_once()
            self.assertEqual(m.call_args.args[1], "Vega")
            self.assertEqual(m.call_args.kwargs.get("source"), "looked_up")

    # ── SystemGeneratorPanel entry point ──
    def test_generator_add_button(self):
        from gui.panels.generator import SystemGeneratorPanel
        p = SystemGeneratorPanel(_FakeWindow())
        self.assertFalse(p._add_proj_btn.isEnabled())
        p._seed.setText("88")
        p._chips["K"].setChecked(True); p._on_chip("K"); p._subtype.setText("2V")
        p._planets.setValue(4)
        p._generate()
        self.assertTrue(p._add_proj_btn.isEnabled())
        with mock.patch("gui.panels.projects.choose_and_add") as m:
            p._add_to_project()
            m.assert_called_once()
            self.assertEqual(m.call_args.kwargs.get("source"), "generated")
            self.assertEqual(m.call_args.kwargs.get("seed"), 88)
            spec = m.call_args.kwargs.get("spec")
            self.assertEqual(spec["spectral_class"], "K2V")
            self.assertEqual(spec["n_planets"], 4)

    # ── DbStatus shows the project tables ──
    def test_dbstatus_lists_project_tables(self):
        from gui.panels.csv_utility import DbStatusPanel
        p = DbStatusPanel(_FakeWindow())
        p._run()   # must not raise; reads get_table_status + dust + research-priors
        labels = {r["table"] for r in db.get_table_status()}
        self.assertIn("Projects", labels)
        self.assertIn("Project Members", labels)


if __name__ == "__main__":
    unittest.main()
