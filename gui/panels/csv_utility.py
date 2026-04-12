# gui/panels/csv_utility.py — Option 50: Star Systems Database CSV generator.

from PySide6.QtWidgets import (
    QVBoxLayout, QPushButton, QLabel, QProgressBar,
)
from PySide6.QtCore import Qt, Signal, QObject, QThread

from gui.panels.base import ResultPanel, Worker
import core.databases


class _CsvWorker(QObject):
    """Specialized worker for the CSV generation task that exposes progress."""

    finished = Signal(object)
    error    = Signal(str)
    progress = Signal(str)

    def run(self):
        def cb(msg):
            self.progress.emit(msg)
        try:
            result = core.databases.compute_star_systems_csv(progress_callback=cb)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class CsvUtilityPanel(ResultPanel):
    """Star Systems CSV Query panel (option 50)."""

    def build_inputs(self):
        self._gen_btn = QPushButton("Generate Star Systems Database")
        self._gen_btn.setFixedHeight(36)
        self._gen_btn.clicked.connect(self._generate)
        self._layout.addWidget(self._gen_btn)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 17)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("Ready")
        self._layout.addWidget(self._progress_bar)

        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._layout.addWidget(self._status_lbl)

        self._input_count = self._layout.count()

    def build_results_area(self):
        pass  # results added dynamically

    def _generate(self):
        self._gen_btn.setEnabled(False)
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("Starting…")
        self._status_lbl.setText("")
        self.clear_results()
        self.set_status("Generating star systems database…")

        self._thread = QThread()
        self._worker = _CsvWorker()
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress, Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._on_done,     Qt.ConnectionType.QueuedConnection)
        self._worker.error.connect(self._on_error_csv,   Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _on_progress(self, msg: str):
        self._status_lbl.setText(msg)
        self.set_status(msg)
        # Parse "Query N/17" to advance progress bar
        import re
        m = re.search(r"Query\s+(\d+)/(\d+)", msg)
        if m:
            current = int(m.group(1))
            total   = int(m.group(2))
            self._progress_bar.setRange(0, total)
            self._progress_bar.setValue(current)
            self._progress_bar.setFormat(f"Query {current} / {total}")

    def _on_done(self, result: dict):
        self._gen_btn.setEnabled(True)
        if "error" in result:
            self._progress_bar.setFormat("Error")
            self.show_error(result["error"])
            self.set_status(f"Error: {result['error']}")
            return

        self._progress_bar.setValue(self._progress_bar.maximum())
        self._progress_bar.setFormat("Done")
        self.set_status("Star Systems database generation complete.")

        total   = result["total_rows"]
        new_cnt = result["total_new"]
        disc    = result["total_discarded"]
        outfile = result["output_file"]

        summary = QLabel(
            f"<b>Complete.</b><br>"
            f"New rows added: {new_cnt}<br>"
            f"Rows discarded (PLX/no-desig/no-sptype): {disc}<br>"
            f"Total rows in starSystems.csv: {total}<br>"
            f"Output: {outfile}"
        )
        summary.setWordWrap(True)
        self.add_result_widget(summary)

    def _on_error_csv(self, msg: str):
        self._gen_btn.setEnabled(True)
        self._progress_bar.setFormat("Error")
        self.show_error(msg)
        self.set_status(f"Error: {msg}")
