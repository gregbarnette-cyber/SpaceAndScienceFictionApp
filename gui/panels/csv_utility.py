# gui/panels/csv_utility.py — Options 50–56: database utilities.

import os
from pathlib import Path

from PySide6.QtWidgets import QPushButton, QLabel, QProgressBar
from PySide6.QtCore import Qt, Signal, QObject, QThread

from gui.panels.base import ResultPanel
import core.databases

_PROJECT_ROOT = str(Path(__file__).parent.parent.parent)


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
    """Star Systems Database Query panel (option 50)."""

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
        backup  = result.get("backup_table") or "none"

        summary = QLabel(
            f"<b>Complete.</b><br>"
            f"New rows added: {new_cnt}<br>"
            f"Rows discarded (PLX/no-desig/no-sptype): {disc}<br>"
            f"Total rows in star_systems table: {total}<br>"
            f"Previous data backed up to: {backup}"
        )
        summary.setWordWrap(True)
        self.add_result_widget(summary)

    def _on_error_csv(self, msg: str):
        self._gen_btn.setEnabled(True)
        self._progress_bar.setFormat("Error")
        self.show_error(msg)
        self.set_status(f"Error: {msg}")


class ExportStarSystemsPanel(ResultPanel):
    """Export Star Systems to CSV panel (option 51)."""

    def build_inputs(self):
        self._run_btn = QPushButton("Export Star Systems to CSV")
        self._run_btn.setFixedHeight(36)
        self._run_btn.clicked.connect(self._run)
        self._layout.addWidget(self._run_btn)
        self._input_count = self._layout.count()

    def build_results_area(self):
        pass

    def _run(self):
        self._run_btn.setEnabled(False)
        self.clear_results()
        self.set_status("Exporting star systems…")
        self.run_in_background(
            core.databases.export_star_systems_csv,
            _PROJECT_ROOT,
            on_result=self._on_done,
        )

    def _on_done(self, result: dict):
        try:
            self._run_btn.setEnabled(True)
        except RuntimeError:
            return
        if "error" in result:
            self.show_error(result["error"])
            self.set_status(f"Error: {result['error']}")
            return
        lbl = QLabel(
            f"<b>Export complete.</b><br>"
            f"Rows exported: {result['count']}<br>"
            f"Output: {result['path']}"
        )
        lbl.setWordWrap(True)
        self.add_result_widget(lbl)
        self.set_status("Export complete.")


class ImportHwcPanel(ResultPanel):
    """Import HWC Data panel (option 52)."""

    def build_inputs(self):
        self._run_btn = QPushButton("Import hwc.csv into Database")
        self._run_btn.setFixedHeight(36)
        self._run_btn.clicked.connect(self._run)
        self._layout.addWidget(self._run_btn)
        self._input_count = self._layout.count()

    def build_results_area(self):
        pass

    def _run(self):
        self._run_btn.setEnabled(False)
        self.clear_results()
        self.set_status("Importing HWC data…")
        csv_path = os.path.join(_PROJECT_ROOT, "hwc.csv")
        self.run_in_background(
            core.databases.import_hwc_csv,
            csv_path,
            on_result=self._on_done,
        )

    def _on_done(self, result: dict):
        try:
            self._run_btn.setEnabled(True)
        except RuntimeError:
            return
        if "error" in result:
            self.show_error(result["error"])
            self.set_status(f"Error: {result['error']}")
            return
        lbl = QLabel(
            f"<b>Import complete.</b><br>"
            f"Rows imported: {result['count']}<br>"
            f"Source: {result['path']}"
        )
        lbl.setWordWrap(True)
        self.add_result_widget(lbl)
        self.set_status("HWC import complete.")


class ImportMissionExocatPanel(ResultPanel):
    """Import Mission Exocat Data panel (option 53)."""

    def build_inputs(self):
        self._run_btn = QPushButton("Import missionExocat.csv into Database")
        self._run_btn.setFixedHeight(36)
        self._run_btn.clicked.connect(self._run)
        self._layout.addWidget(self._run_btn)
        self._input_count = self._layout.count()

    def build_results_area(self):
        pass

    def _run(self):
        self._run_btn.setEnabled(False)
        self.clear_results()
        self.set_status("Importing Mission Exocat data…")
        csv_path = os.path.join(_PROJECT_ROOT, "missionExocat.csv")
        self.run_in_background(
            core.databases.import_mission_exocat_csv,
            csv_path,
            on_result=self._on_done,
        )

    def _on_done(self, result: dict):
        try:
            self._run_btn.setEnabled(True)
        except RuntimeError:
            return
        if "error" in result:
            self.show_error(result["error"])
            self.set_status(f"Error: {result['error']}")
            return
        lbl = QLabel(
            f"<b>Import complete.</b><br>"
            f"Rows imported: {result['count']}<br>"
            f"Source: {result['path']}"
        )
        lbl.setWordWrap(True)
        self.add_result_widget(lbl)
        self.set_status("Mission Exocat import complete.")


class ImportMainSequencePanel(ResultPanel):
    """Import Main Sequence Star Properties panel (option 54)."""

    def build_inputs(self):
        self._run_btn = QPushButton("Import propertiesOfMainSequenceStars.csv into Database")
        self._run_btn.setFixedHeight(36)
        self._run_btn.clicked.connect(self._run)
        self._layout.addWidget(self._run_btn)
        self._input_count = self._layout.count()

    def build_results_area(self):
        pass

    def _run(self):
        self._run_btn.setEnabled(False)
        self.clear_results()
        self.set_status("Importing main sequence star data…")
        csv_path = os.path.join(_PROJECT_ROOT, "propertiesOfMainSequenceStars.csv")
        self.run_in_background(
            core.databases.import_main_sequence_csv,
            csv_path,
            on_result=self._on_done,
        )

    def _on_done(self, result: dict):
        try:
            self._run_btn.setEnabled(True)
        except RuntimeError:
            return
        if "error" in result:
            self.show_error(result["error"])
            self.set_status(f"Error: {result['error']}")
            return
        lbl = QLabel(
            f"<b>Import complete.</b><br>"
            f"Rows imported: {result['count']}<br>"
            f"Source: {result['path']}"
        )
        lbl.setWordWrap(True)
        self.add_result_widget(lbl)
        self.set_status("Main sequence import complete.")


class ImportSolarSystemPanel(ResultPanel):
    """Import Solar System Data panel (option 55)."""

    def build_inputs(self):
        self._run_btn = QPushButton("Import Solar System CSVs into Database")
        self._run_btn.setFixedHeight(36)
        self._run_btn.clicked.connect(self._run)
        self._layout.addWidget(self._run_btn)
        self._input_count = self._layout.count()

    def build_results_area(self):
        pass

    def _run(self):
        self._run_btn.setEnabled(False)
        self.clear_results()
        self.set_status("Importing solar system data…")
        self.run_in_background(
            core.databases.import_solar_system_csvs,
            _PROJECT_ROOT,
            on_result=self._on_done,
        )

    def _on_done(self, result: dict):
        try:
            self._run_btn.setEnabled(True)
        except RuntimeError:
            return
        if "error" in result:
            self.show_error(result["error"])
            self.set_status(f"Error: {result['error']}")
            return
        lbl = QLabel(
            f"<b>Import complete.</b><br>"
            f"Planets: {result['planets']} rows<br>"
            f"Moons: {result['moons']} rows<br>"
            f"Dwarf planets: {result['dwarf_planets']} rows<br>"
            f"Asteroids: {result['asteroids']} rows"
        )
        lbl.setWordWrap(True)
        self.add_result_widget(lbl)
        self.set_status("Solar system import complete.")


class ImportHonorversePanel(ResultPanel):
    """Import Honorverse Hyper Limits panel (option 56)."""

    def build_inputs(self):
        self._run_btn = QPushButton("Import spTypeHyperLM.csv into Database")
        self._run_btn.setFixedHeight(36)
        self._run_btn.clicked.connect(self._run)
        self._layout.addWidget(self._run_btn)
        self._input_count = self._layout.count()

    def build_results_area(self):
        pass

    def _run(self):
        self._run_btn.setEnabled(False)
        self.clear_results()
        self.set_status("Importing Honorverse hyper limit data…")
        csv_path = os.path.join(_PROJECT_ROOT, "spTypeHyperLM.csv")
        self.run_in_background(
            core.databases.import_honorverse_hyper_csv,
            csv_path,
            on_result=self._on_done,
        )

    def _on_done(self, result: dict):
        try:
            self._run_btn.setEnabled(True)
        except RuntimeError:
            return
        if "error" in result:
            self.show_error(result["error"])
            self.set_status(f"Error: {result['error']}")
            return
        lbl = QLabel(
            f"<b>Import complete.</b><br>"
            f"Rows imported: {result['count']}<br>"
            f"Source: {result['path']}"
        )
        lbl.setWordWrap(True)
        self.add_result_widget(lbl)
        self.set_status("Honorverse hyper limits import complete.")
