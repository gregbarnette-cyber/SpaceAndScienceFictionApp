# gui/panels/reports.py — Phase Q: System Dossier Export (GUI-only).
#
# DossierExportPanel composes the existing readers into a Markdown/HTML/JSON dossier via
# core.report.build_system_dossier (pure). The panel adds two GUI-only enrichments that
# never touch core/:
#   - HTML preview/save gets the HZ-ring + abundance figures spliced in as inline base64
#     <img> (decision #5, option A) — built from the Qt canvases when matplotlib is present.
#   - Batch mode: a newline list of stars → one file each.
#
# A single fetch runs build_system_dossier(fmt="json") in the background (it runs the
# network readers); the document + figures are then rendered from that one envelope.

import base64
import io
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QLabel, QCheckBox, QRadioButton, QButtonGroup, QTextBrowser, QFileDialog,
    QDialog, QPlainTextEdit, QGroupBox,
)
from PySide6.QtCore import Qt

import core.report as report

# Default section set (the opt-in "moons" is offered as an extra checkbox).
_SECTIONS = ["identity", "regions", "habitable_zone", "planets", "hypatia", "gcns"]
_SECTION_LABELS = {
    "identity": "Identity", "regions": "Regions", "habitable_zone": "Habitable Zone",
    "planets": "Planets", "hypatia": "Hypatia", "gcns": "GCNS",
}


def _mpl_ok():
    try:
        from gui.visualizations.plot_helpers import mpl_available
        return mpl_available()
    except Exception:
        return False


def _figures_html(data):
    """Build inline base64 <img> blocks for the HZ ring + abundance chart from a json
    envelope's `data` (GUI-only; option A). Returns an HTML string ('' if nothing renders).

    Off the Qt canvases: render each figure to PNG via figure.savefig, base64-encode, and
    wrap in a data: URI <img>. Defensive — any failure yields no image, never an exception
    that would break the text dossier."""
    if not _mpl_ok():
        return ""
    from gui.visualizations import plot_helpers as ph
    import core.viz as viz

    imgs = []

    def _encode(canvas, alt):
        try:
            buf = io.BytesIO()
            canvas.figure.savefig(buf, format="png", dpi=110, bbox_inches="tight")
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            imgs.append(f'<h3>{alt}</h3><img alt="{alt}" '
                        f'src="data:image/png;base64,{b64}" style="max-width:100%">')
        except Exception:
            pass

    # HZ ring — from the regions stellar teff + calculated luminosity.
    reg = data.get("regions")
    if reg:
        teff = reg["stellar"].get("teff")
        lum = reg["stellar"].get("calculated_luminosity")
        if teff and lum:
            hz = viz.prepare_hz_diagram(teff, lum)
            if "error" not in hz:
                try:
                    canvas, _ = ph.make_hz_canvas(None, hz["zones"], hz["max_au"],
                                                  title="Habitable Zone")
                    _encode(canvas, "Habitable Zone")
                except Exception:
                    pass

    # Abundance bar chart — from the hypatia abundances list.
    hyp = data.get("hypatia")
    if hyp and hyp.get("abundances"):
        prof = viz.prepare_abundance_profile(
            {"star_name": hyp.get("star_name"), "abundances": hyp["abundances"]})
        if "error" not in prof:
            try:
                canvas, _ = ph.make_abundance_canvas(None, prof, hyp.get("star_name") or "")
                _encode(canvas, "Elemental Abundances")
            except Exception:
                pass

    if not imgs:
        return ""
    return ('<h2>Diagrams</h2>'
            '<p><em>Figures rendered in the GUI (not included in query.py output).</em></p>'
            + "\n".join(imgs))


def _splice_figures(html_doc, figures_html):
    """Insert the figures block just before the dossier footer (or before </body>)."""
    if not figures_html:
        return html_doc
    marker = "<footer>"
    if marker in html_doc:
        return html_doc.replace(marker, figures_html + "\n" + marker, 1)
    return html_doc.replace("</body>", figures_html + "\n</body>", 1)


class DossierExportPanel(QWidget):
    """System Dossier export panel (Phase Q). Inherits QWidget directly (not ResultPanel)
    so the large preview pane owns the layout; threading is borrowed via a small inline
    worker mirroring ResultPanel.run_in_background."""

    def __init__(self, window):
        super().__init__()
        self.window = window
        self._last = None          # (fmt, document) for Save
        self._build()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)

        form = QFormLayout()
        self._star = QLineEdit()
        self._star.setPlaceholderText("Star name, or 'Sol' / 'Sun' for the Solar System")
        self._star.setMaximumWidth(320)
        self._star.returnPressed.connect(self._generate)
        form.addRow("Star:", self._star)
        root.addLayout(form)

        # Section checkboxes
        secbox = QGroupBox("Sections")
        secrow = QHBoxLayout(secbox)
        self._sec_checks = {}
        for key in _SECTIONS:
            cb = QCheckBox(_SECTION_LABELS[key])
            cb.setChecked(True)
            self._sec_checks[key] = cb
            secrow.addWidget(cb)
        self._moons_check = QCheckBox("Moons (Sol only)")
        self._moons_check.setChecked(False)
        secrow.addWidget(self._moons_check)
        secrow.addStretch()
        root.addWidget(secbox)

        # Format radio
        fmtrow = QHBoxLayout()
        fmtrow.addWidget(QLabel("Format:"))
        self._fmt_group = QButtonGroup(self)
        self._rb_md = QRadioButton("Markdown")
        self._rb_html = QRadioButton("HTML")
        self._rb_md.setChecked(True)
        self._fmt_group.addButton(self._rb_md)
        self._fmt_group.addButton(self._rb_html)
        fmtrow.addWidget(self._rb_md)
        fmtrow.addWidget(self._rb_html)
        fmtrow.addStretch()
        root.addLayout(fmtrow)

        # Buttons
        btnrow = QHBoxLayout()
        self.run_btn = QPushButton("Generate")
        self.run_btn.clicked.connect(self._generate)
        self._save_btn = QPushButton("Save to file…")
        self._save_btn.clicked.connect(self._save)
        self._save_btn.setEnabled(False)
        self._batch_btn = QPushButton("Batch…")
        self._batch_btn.clicked.connect(self._batch)
        btnrow.addWidget(self.run_btn)
        btnrow.addWidget(self._save_btn)
        btnrow.addWidget(self._batch_btn)
        btnrow.addStretch()
        root.addLayout(btnrow)

        self._status = QLabel("")
        self._status.setStyleSheet("color: #aa4400;")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        self._preview = QTextBrowser()
        self._preview.setOpenExternalLinks(False)
        root.addWidget(self._preview, 1)

    def reset(self):
        """Nav switch hook — clear preview + transient state (no rebuild needed)."""
        self._last = None
        self._save_btn.setEnabled(False)
        self._status.setText("")
        self._preview.clear()

    # ── helpers ────────────────────────────────────────────────────────────────

    def _selected_sections(self):
        secs = [k for k in _SECTIONS if self._sec_checks[k].isChecked()]
        if self._moons_check.isChecked():
            secs.append("moons")
        return secs

    def _fmt(self):
        return "html" if self._rb_html.isChecked() else "markdown"

    # ── generate (single) ────────────────────────────────────────────────────────

    def _generate(self):
        star = self._star.text().strip()
        if not star:
            self._status.setText("Enter a star name.")
            return
        self._status.setText("Working…")
        self.run_btn.setEnabled(False)
        self._save_btn.setEnabled(False)
        # Fetch the structured envelope once (runs the network readers); render the
        # document + figures from it. Reuse ResultPanel's thread plumbing via the window's
        # helper would couple classes; a tiny local thread keeps this panel self-contained.
        from gui.panels.base import ResultPanel, Worker
        from PySide6.QtCore import QThread, QTimer
        thread = QThread()
        worker = Worker(report.build_system_dossier, star,
                        sections=self._selected_sections(), fmt="json")
        worker.moveToThread(thread)
        pair = (thread, worker)
        ResultPanel._live_threads.append(pair)
        worker._on_result_cb = lambda env: self._on_generated(env, self._fmt())
        thread.started.connect(worker.run)
        worker.finished.connect(self._deliver, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(thread.quit)
        thread.finished.connect(lambda: self.run_btn.setEnabled(True))
        thread.finished.connect(
            lambda p=pair: QTimer.singleShot(
                500, lambda: (ResultPanel._live_threads.remove(p)
                              if p in ResultPanel._live_threads else None)))
        thread.start()

    def _deliver(self, env):
        worker = self.sender()
        cb = getattr(worker, "_on_result_cb", None)
        if cb:
            try:
                cb(env)
            except RuntimeError:
                pass

    def _on_generated(self, env, fmt):
        if not env or "error" in env:
            msg = env.get("error", "Unknown error") if env else "No result"
            self._status.setText(f"Error: {msg}")
            self._preview.clear()
            return
        document = report.render_document(env, fmt)
        warn = env.get("warnings", [])
        note = env.get("notes", [])
        bits = []
        if warn:
            bits.append(f"{len(warn)} warning(s)")
        if note:
            bits.append(f"{len(note)} note(s)")
        self._status.setText("Generated · " + (", ".join(bits) if bits else "no warnings"))
        if fmt == "html":
            document = _splice_figures(document, _figures_html(env.get("data", {})))
            self._preview.setHtml(document)
        else:
            self._preview.setPlainText(document)
        self._last = (fmt, document, env.get("star", "dossier"))
        self._save_btn.setEnabled(True)

    # ── save ─────────────────────────────────────────────────────────────────────

    def _save(self):
        if not self._last:
            return
        fmt, document, star = self._last
        ext = "html" if fmt == "html" else "md"
        safe = "".join(c if c.isalnum() else "_" for c in star).strip("_") or "dossier"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Dossier", f"{safe}_dossier.{ext}",
            "HTML (*.html)" if fmt == "html" else "Markdown (*.md)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(document)
            self._status.setText(f"Saved: {path}")
        except OSError as e:
            self._status.setText(f"Save failed: {e}")

    # ── batch ────────────────────────────────────────────────────────────────────

    def _batch(self):
        dlg = _BatchDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        stars = dlg.stars()
        out_dir = dlg.directory()
        if not stars or not out_dir:
            return
        fmt = self._fmt()
        sections = self._selected_sections()
        ext = "html" if fmt == "html" else "md"
        results = []
        for star in stars:
            env = report.build_system_dossier(star, sections=sections, fmt="json")
            if not env or "error" in env:
                results.append(f"✗ {star}: {env.get('error', 'error') if env else 'error'}")
                continue
            document = report.render_document(env, fmt)
            if fmt == "html":
                document = _splice_figures(document, _figures_html(env.get("data", {})))
            safe = "".join(c if c.isalnum() else "_" for c in star).strip("_") or "dossier"
            path = os.path.join(out_dir, f"{safe}_dossier.{ext}")
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(document)
                w = len(env.get("warnings", []))
                results.append(f"✓ {star}: {os.path.basename(path)}"
                               + (f" ({w} warning(s))" if w else ""))
            except OSError as e:
                results.append(f"✗ {star}: {e}")
        self._status.setText(f"Batch complete: {len(stars)} star(s)")
        self._preview.setPlainText("\n".join(results))
        self._save_btn.setEnabled(False)


class _BatchDialog(QDialog):
    """Newline list of stars + an output directory picker."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Dossier Export")
        self._dir = ""
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("One star per line (use 'Sol' for the Solar System):"))
        self._edit = QPlainTextEdit()
        lay.addWidget(self._edit, 1)

        dirrow = QHBoxLayout()
        self._dir_lbl = QLabel("(no directory chosen)")
        pick = QPushButton("Choose directory…")
        pick.clicked.connect(self._pick)
        dirrow.addWidget(pick)
        dirrow.addWidget(self._dir_lbl, 1)
        lay.addLayout(dirrow)

        btns = QHBoxLayout()
        ok = QPushButton("Export")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(ok)
        btns.addWidget(cancel)
        lay.addLayout(btns)

    def _pick(self):
        d = QFileDialog.getExistingDirectory(self, "Output directory")
        if d:
            self._dir = d
            self._dir_lbl.setText(d)

    def stars(self):
        return [s.strip() for s in self._edit.toPlainText().splitlines() if s.strip()]

    def directory(self):
        return self._dir
