# gui/panels/projects.py — Phase S: Project Workspaces (campaign / novel manager).
#
# Master-detail workspace over core.projects: a project list (create / rename /
# delete) + the selected project's member table (Star · Note · Source · Added) with
# inline note editing, per-row Open (real → embedded SIMBAD lookup; generated →
# re-run generate_system(spec), byte-identical) and Remove. Export Project Dossier
# lands in S-C5; the "Add to project" entry points on other panels in S-C6.

import json
import os
import re

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QListWidget,
    QTableWidget, QTableWidgetItem, QInputDialog, QMessageBox, QDialog,
    QAbstractItemView, QHeaderView, QComboBox, QRadioButton, QButtonGroup,
    QCheckBox, QDialogButtonBox, QFileDialog,
)
from PySide6.QtCore import Qt

from gui.panels.base import ResultPanel
import core.projects as projects
import core.generate as generate
import core.report as report

_NOTE_COL = 1
_EXT = {"markdown": "md", "html": "html", "json": "json"}
_Q_SECTIONS = ["identity", "regions", "habitable_zone", "planets", "hypatia", "gcns"]


def _safe_name(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_") or "system"


def choose_and_add(parent, star_name, source="looked_up", seed=None, spec=None):
    """Prompt for a project (existing or new) and add `star_name` to it.

    The shared "Add to project" entry point used by SimbadPanel (real stars) and
    SystemGeneratorPanel (generated systems). Returns the project name added to, or
    None if cancelled / on error.
    """
    star_name = (star_name or "").strip()
    if not star_name:
        return None
    names = [p["name"] for p in projects.list_projects()]
    items = names + ["<New project…>"]
    choice, ok = QInputDialog.getItem(
        parent, "Add to Project", f"Add {star_name!r} to:", items, 0, False)
    if not ok:
        return None
    if choice == "<New project…>":
        name, ok2 = QInputDialog.getText(parent, "New Project", "Project name:")
        name = (name or "").strip()
        if not ok2 or not name:
            return None
        projects.create_project(name)   # "already exists" is fine — we add to it next
        target = name
    else:
        target = choice
    res = projects.add_member(target, star_name, source=source, seed=seed, spec=spec)
    if "error" in res:
        QMessageBox.warning(parent, "Add to Project", res["error"])
        return None
    QMessageBox.information(parent, "Add to Project",
                           f"Added {res['star_name']!r} to {target!r}.")
    return target


class _ExportDialog(QDialog):
    """Format + sections (Q vocabulary, real members) + combined/per-file."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Project Dossier")
        v = QVBoxLayout(self)

        v.addWidget(QLabel("<b>Format</b>"))
        self._fmt = QComboBox()
        self._fmt.addItems(["markdown", "html", "json"])
        v.addWidget(self._fmt)

        v.addWidget(QLabel("<b>Layout</b>"))
        self._combined = QRadioButton("One combined document")
        self._per_file = QRadioButton("One file per system")
        self._combined.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self._combined)
        grp.addButton(self._per_file)
        v.addWidget(self._combined)
        v.addWidget(self._per_file)

        v.addWidget(QLabel("<b>Sections</b> <span style='color:#666'>(real members; "
                           "generated render in full)</span>"))
        self._sec_boxes = {}
        for s in _Q_SECTIONS:
            cb = QCheckBox(s)
            cb.setChecked(True)
            self._sec_boxes[s] = cb
            v.addWidget(cb)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def values(self):
        chosen = [s for s, cb in self._sec_boxes.items() if cb.isChecked()]
        # all checked → None (means "all available", per build_system_dossier)
        sections = None if len(chosen) == len(_Q_SECTIONS) else chosen
        return self._fmt.currentText(), self._combined.isChecked(), sections


class ProjectPanel(ResultPanel):
    """Project workspaces — collect real + generated systems with notes (Phase S)."""

    def build_inputs(self):
        self._current = None                 # selected project name
        self._members_by_name = {}           # star_name -> member dict
        self._loading = False                # guard for the cellChanged note signal
        self._dialogs = []                   # keep Open dialogs alive

        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)

        # ── left: project list ──
        left = QVBoxLayout()
        left.addWidget(QLabel("<b>Projects</b>"))
        self._proj_list = QListWidget()
        self._proj_list.setMaximumWidth(240)
        self._proj_list.currentItemChanged.connect(self._on_project_selected)
        left.addWidget(self._proj_list)
        lbtns = QHBoxLayout()
        for label, slot in (("New", self._new_project), ("Rename", self._rename_project),
                            ("Delete", self._delete_project)):
            b = QPushButton(label)
            b.clicked.connect(slot)
            lbtns.addWidget(b)
        left.addLayout(lbtns)
        lw = QWidget()
        lw.setLayout(left)
        lw.setMaximumWidth(260)
        h.addWidget(lw)

        # ── right: member detail ──
        right = QVBoxLayout()
        self._detail_header = QLabel("Select or create a project.")
        self._detail_header.setStyleSheet("font-weight:600;")
        right.addWidget(self._detail_header)
        self._export_btn = QPushButton("Export Project Dossier")
        self._export_btn.setEnabled(False)   # enabled when the project has members
        self._export_btn.setToolTip("Export the whole project as a dossier "
                                    "(real members via Q; generated re-created from spec).")
        self._export_btn.clicked.connect(self._export)
        right.addWidget(self._export_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        self._members = QTableWidget(0, 5)
        self._members.setHorizontalHeaderLabels(
            ["Star", "Note", "Source", "Added", ""])
        self._members.verticalHeader().setVisible(False)
        self._members.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._members.horizontalHeader().setSectionResizeMode(
            _NOTE_COL, QHeaderView.ResizeMode.Stretch)
        self._members.cellChanged.connect(self._on_cell_changed)
        right.addWidget(self._members)
        rw = QWidget()
        rw.setLayout(right)
        h.addWidget(rw, 1)

        self._layout.addWidget(row)
        self._input_count = self._layout.count()
        self._reload_projects()

    def build_results_area(self):
        pass

    # ── project list ──
    def _reload_projects(self, select=None):
        self._proj_list.blockSignals(True)
        self._proj_list.clear()
        names = [p["name"] for p in projects.list_projects()]
        self._proj_list.addItems(names)
        self._proj_list.blockSignals(False)
        target = select or self._current
        if target in names:
            self._proj_list.setCurrentRow(names.index(target))
        elif names:
            self._proj_list.setCurrentRow(0)
        else:
            self._current = None
            self._show_project(None)

    def _on_project_selected(self, *_):
        item = self._proj_list.currentItem()
        self._current = item.text() if item else None
        self._show_project(self._current)

    def _show_project(self, name):
        if not name:
            self._detail_header.setText("Select or create a project.")
            self._export_btn.setEnabled(False)
            self._set_members([])
            return
        res = projects.get_project(name)
        if "error" in res:
            self.show_error(res["error"])
            return
        desc = res["project"].get("description") or ""
        n = len(res["members"])
        self._detail_header.setText(f"{name} — {n} system(s)"
                                    + (f"  ·  {desc}" if desc else ""))
        self._export_btn.setEnabled(n > 0)
        self._set_members(res["members"])

    def _new_project(self):
        name, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if not ok:
            return
        res = projects.create_project(name)
        if "error" in res:
            self.show_error(res["error"])
            return
        self._reload_projects(select=res["name"])

    def _rename_project(self):
        if not self._current:
            return
        new, ok = QInputDialog.getText(self, "Rename Project", "New name:",
                                       text=self._current)
        if not ok:
            return
        res = projects.rename_project(self._current, new)
        if "error" in res:
            self.show_error(res["error"])
            return
        self._reload_projects(select=res["name"])

    def _delete_project(self):
        if not self._current:
            return
        if QMessageBox.question(self, "Delete Project",
                                f"Delete project {self._current!r} and its members?") \
                != QMessageBox.StandardButton.Yes:
            return
        projects.delete_project(self._current)
        self._current = None
        self._reload_projects()

    # ── members ──
    def _set_members(self, members):
        self._loading = True
        self._members_by_name = {m["star_name"]: m for m in members}
        self._members.setRowCount(0)
        for m in members:
            r = self._members.rowCount()
            self._members.insertRow(r)
            star = QTableWidgetItem(m["star_name"])
            star.setFlags(star.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._members.setItem(r, 0, star)
            note = QTableWidgetItem(m.get("note") or "")   # editable (default flags)
            self._members.setItem(r, _NOTE_COL, note)
            src = m.get("source")
            src_label = (f"generated · seed {m.get('generated_seed')}"
                         if src == "generated" else "looked-up")
            for col, val in ((2, src_label), (3, m.get("added_date") or "")):
                it = QTableWidgetItem(str(val))
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._members.setItem(r, col, it)
            self._members.setCellWidget(r, 4, self._row_actions(m["star_name"]))
        self._loading = False

    def _row_actions(self, star_name):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(2, 0, 2, 0)
        op = QPushButton("Open")
        op.clicked.connect(lambda: self._open_member(star_name))
        rm = QPushButton("Remove")
        rm.clicked.connect(lambda: self._remove_member(star_name))
        lay.addWidget(op)
        lay.addWidget(rm)
        return w

    def _on_cell_changed(self, r, c):
        if self._loading or c != _NOTE_COL or not self._current:
            return
        star = self._members.item(r, 0).text()
        note = self._members.item(r, _NOTE_COL).text()
        res = projects.update_note(self._current, star, note)
        if "error" in res:
            self.show_error(res["error"])
        else:
            self.set_status(f"Note updated for {star}.")

    def _remove_member(self, star_name):
        if not self._current:
            return
        projects.remove_member(self._current, star_name)
        self._show_project(self._current)

    # ── export ──
    def _export(self):
        if not self._current:
            return
        dlg = _ExportDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        fmt, combined, sections = dlg.values()
        ext = _EXT[fmt]
        if combined:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Project Dossier", f"{_safe_name(self._current)}.{ext}",
                f"*.{ext}")
            if not path:
                return
            self._export_target = ("file", path)
        else:
            d = QFileDialog.getExistingDirectory(self, "Choose output folder")
            if not d:
                return
            self._export_target = ("dir", d)
        self._export_fmt = fmt
        self.set_status(f"Exporting {self._current}…")
        self.run_in_background(
            report.build_project_dossier, self._current,
            sections=sections, fmt=fmt, combined=combined,
            on_result=self._on_export_done)

    def _on_export_done(self, result):
        if isinstance(result, dict) and "error" in result:
            self.show_error(result["error"])
            self.set_status(f"Export error: {result['error']}")
            return
        try:
            written = self._write_export(result, *self._export_target)
        except OSError as e:
            self.show_error(str(e))
            return
        warn = result.get("warnings") or []
        msg = f"Exported {written} file(s) to {self._export_target[1]}."
        if warn:
            msg += f" {len(warn)} member(s) skipped."
        self.set_status(msg)

    def _write_export(self, result, kind, target):
        ext = _EXT[self._export_fmt]
        is_json = self._export_fmt == "json"
        if kind == "file":   # combined
            payload = (json.dumps(result.get("data"), indent=2, default=str)
                       if is_json else result.get("document", ""))
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(payload)
            return 1
        # per-file: one file per ok member
        n = 0
        for m in result.get("members", []):
            if not m.get("ok"):
                continue
            payload = (json.dumps(m.get("data"), indent=2, default=str)
                       if is_json else m.get("document", ""))
            fn = os.path.join(target, f"{_safe_name(m['star_name'])}.{ext}")
            with open(fn, "w", encoding="utf-8") as fh:
                fh.write(payload)
            n += 1
        return n

    # ── open ──
    def _open_member(self, star_name):
        m = self._members_by_name.get(star_name)
        if not m:
            return None
        if m.get("source") == "generated":
            return self._open_generated(m)
        return self._open_real(star_name)

    def _open_real(self, name):
        from gui.panels.simbad import SimbadPanel
        dlg = QDialog(self)
        dlg.setWindowTitle(name)
        v = QVBoxLayout(dlg)
        panel = SimbadPanel(self.window)
        if hasattr(panel, "_name_input"):
            panel._name_input.setText(name)
        v.addWidget(panel)
        try:
            panel._search()
        except Exception:
            pass
        dlg.resize(720, 600)
        dlg.setModal(False)
        dlg.show()
        self._dialogs.append(dlg)
        return dlg

    def _open_generated(self, member):
        res = generate.generate_from_spec(member.get("generated_spec")
                                          or {"seed": member.get("generated_seed")})
        dlg = QDialog(self)
        dlg.setWindowTitle(member["star_name"])
        v = QVBoxLayout(dlg)
        if "error" in res:
            v.addWidget(QLabel(f"Could not re-create: {res['error']}"))
        else:
            s = res["star"]
            v.addWidget(QLabel(
                f"<b>{s['name']}</b> — {s.get('spectral_class')} · re-created from "
                f"seed {res.get('seed')} (deterministic)"))
            headers = ["Name", "a (AU)", "Type", "Mass (M⊕)", "Radius (R⊕)",
                       "T_eq (K)", "In HZ", "Source"]
            rows = [[p.get("name"), p.get("a_au"), p.get("type"), p.get("mass_earth"),
                     p.get("radius_earth"), p.get("t_eq_k"),
                     "Yes" if p.get("in_hz") else "No", p.get("source")]
                    for p in res.get("planets", [])]
            v.addWidget(self.make_table(headers, rows))
        dlg.resize(720, 420)
        dlg.setModal(False)
        dlg.show()
        self._dialogs.append(dlg)
        return dlg
