# gui/panels/csv_utility.py — Options 50–57: database utilities.

import os
from pathlib import Path

from PySide6.QtWidgets import (QPushButton, QLabel, QProgressBar, QComboBox,
                               QHBoxLayout, QWidget, QGroupBox, QVBoxLayout,
                               QPlainTextEdit, QApplication, QLineEdit, QFileDialog)
from PySide6.QtCore import Qt, Signal, QObject, QThread

from gui.panels.base import ResultPanel
import core.databases
import core.db
import core.dust
import core.research_priors

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
        dropped = result.get("backups_dropped") or []
        kept    = result.get("backups_kept") or []

        backups_line = ""
        if dropped:
            backups_line += (
                f"Old backup tables dropped (kept newest 3): {', '.join(dropped)}<br>"
            )
        backups_line += (
            f"Backup tables retained: {', '.join(kept) if kept else 'none'}"
        )

        summary = QLabel(
            f"<b>Complete.</b><br>"
            f"New rows added: {new_cnt}<br>"
            f"Rows discarded (PLX/no-desig/no-sptype): {disc}<br>"
            f"Total rows in star_systems table: {total}<br>"
            f"Previous data backed up to: {backup}<br>"
            f"{backups_line}"
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


class DbStatusPanel(ResultPanel):
    """Database Table Status panel (option 57)."""

    def build_inputs(self):
        self._run_btn = QPushButton("Check Database Status")
        self._run_btn.setFixedHeight(36)
        self._run_btn.clicked.connect(self._run)
        self._layout.addWidget(self._run_btn)
        self._input_count = self._layout.count()

    def build_results_area(self):
        pass

    def _run(self):
        self.clear_results()
        self.set_status("Checking database table status…")
        try:
            rows = core.db.get_table_status()
        except Exception as e:
            self.show_error(str(e))
            self.set_status(f"Error: {e}")
            return

        table_rows = [
            [r["table"], f"{r['rows']:,}", "Populated" if r["populated"] else "Empty"]
            for r in rows
        ]

        # Dust maps are cached FILES (not DB tables); append their presence/size
        # so the one status view covers the whole data store (Phase T2).
        for d in core.dust.get_dust_map_status():
            size = f"{d['size_mb']:,.1f} MB" if d["present"] else "—"
            table_rows.append(
                [d["label"], size, "Present" if d["present"] else "Missing"])

        # Research-priors cache (a versioned JSON document, not a DB table) — Phase R3.
        rp = core.research_priors.get_research_priors_status()
        if rp["loaded"]:
            table_rows.append([f"research priors ({rp['dataset_version']})",
                               f"schema {rp['schema_version']}", "Loaded"])
        else:
            table_rows.append(["research priors", "—", "Missing"])

        view = self.make_table(["Table / File", "Rows / Size", "Status"], table_rows)
        self.add_result_widget(view)
        self.set_status("Database status check complete.")


class _GcnsWorker(QObject):
    """Worker for the GCNS ingest task; relays progress messages to the UI."""

    finished = Signal(object)
    error    = Signal(str)
    progress = Signal(str)

    def run(self):
        def cb(msg):
            self.progress.emit(msg)
        try:
            result = core.databases.compute_gcns_ingest(progress_callback=cb)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ImportGcnsPanel(ResultPanel):
    """Import GCNS Data panel (option 58)."""

    def build_inputs(self):
        self._gen_btn = QPushButton("Import GCNS Data (download ~331k sources)")
        self._gen_btn.setFixedHeight(36)
        self._gen_btn.clicked.connect(self._run)
        self._layout.addWidget(self._gen_btn)

        info = QLabel(
            "Downloads the Gaia Catalogue of Nearby Stars from the GAVO TAP "
            "service and replaces the gcns_stars table. Takes several minutes "
            "and needs a network connection. Existing data is kept until the "
            "new download passes its size checks."
        )
        info.setWordWrap(True)
        self._layout.addWidget(info)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("Ready")
        self._layout.addWidget(self._progress_bar)

        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._layout.addWidget(self._status_lbl)

        self._input_count = self._layout.count()

    def build_results_area(self):
        pass

    def _run(self):
        self._gen_btn.setEnabled(False)
        self._progress_bar.setRange(0, 0)   # busy/indeterminate
        self._progress_bar.setFormat("Downloading…")
        self._status_lbl.setText("")
        self.clear_results()
        self.set_status("Importing GCNS data…")

        self._thread = QThread()
        self._worker = _GcnsWorker()
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress, Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._on_done,     Qt.ConnectionType.QueuedConnection)
        self._worker.error.connect(self._on_error_gcns,  Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _on_progress(self, msg: str):
        self._status_lbl.setText(msg)
        self.set_status(msg)

    def _on_done(self, result: dict):
        try:
            self._gen_btn.setEnabled(True)
        except RuntimeError:
            return
        self._progress_bar.setRange(0, 1)
        if "error" in result:
            self._progress_bar.setValue(0)
            self._progress_bar.setFormat("Error")
            self.show_error(result["error"])
            self.set_status(f"Error: {result['error']}")
            return

        self._progress_bar.setValue(1)
        self._progress_bar.setFormat("Done")
        self.set_status("GCNS import complete.")
        lbl = QLabel(
            f"<b>Import complete.</b><br>"
            f"Snapshot date: {result['snapshot_date']}<br>"
            f"gcns.main rows: {result['main_count']:,}<br>"
            f"gcns.missing_10mas rows: {result['missing_count']:,}<br>"
            f"Total rows in gcns_stars: {result['total_rows']:,}<br>"
            f"SIMBAD cross-matched: {result['simbad_matched']:,}<br>"
            f"Resolved pairs: {result['resolved_pairs']:,}<br>"
            f"Resolved systems: {result['systems_count']:,} "
            f"({result['systems_multi']:,} with &gt;2 components)<br>"
            f"System members in gcns_stars: {result['members_in_stars']:,}"
        )
        lbl.setWordWrap(True)
        self.add_result_widget(lbl)

    def _on_error_gcns(self, msg: str):
        try:
            self._gen_btn.setEnabled(True)
        except RuntimeError:
            return
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("Error")
        self.show_error(msg)
        self.set_status(f"Error: {msg}")


class _HypatiaWorker(QObject):
    """Worker for the Hypatia cache import; relays progress messages to the UI."""

    finished = Signal(object)
    error    = Signal(str)
    progress = Signal(str)

    def run(self):
        def cb(msg):
            self.progress.emit(msg)
        try:
            result = core.databases.import_hypatia_cache(progress_callback=cb)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ImportHypatiaPanel(ResultPanel):
    """Import Hypatia Cache panel (Phase L4) — mirrors ImportGcnsPanel.

    Bulk-pulls the whole Hypatia Catalog into the local hypatia_cache /
    hypatia_abundance tables (~112 throttled GET /data calls), enabling the
    Hypatia Abundance Search + the Star Systems search Fe/H filter.
    """

    def build_inputs(self):
        self._gen_btn = QPushButton("Import Hypatia Cache (download ~6k stars)")
        self._gen_btn.setFixedHeight(36)
        self._gen_btn.clicked.connect(self._run)
        self._layout.addWidget(self._gen_btn)

        info = QLabel(
            "Downloads the whole Hypatia Catalog of stellar abundances from "
            "hypatiacatalog.com (~112 throttled requests, a minute or two) and "
            "replaces the hypatia_cache / hypatia_abundance tables. This powers "
            "the Hypatia Abundance Search and the Fe/H filter in Star Systems "
            "Search. Existing data is kept until the new download passes its size "
            "check. Bulk data carries the [X/H] mean per element; per-star spread "
            "(σ/min/max) stays in the live SIMBAD Lookup view."
        )
        info.setWordWrap(True)
        self._layout.addWidget(info)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("Ready")
        self._layout.addWidget(self._progress_bar)

        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._layout.addWidget(self._status_lbl)

        self._input_count = self._layout.count()

    def build_results_area(self):
        pass

    def _run(self):
        self._gen_btn.setEnabled(False)
        self._progress_bar.setRange(0, 0)   # busy/indeterminate
        self._progress_bar.setFormat("Downloading…")
        self._status_lbl.setText("")
        self.clear_results()
        self.set_status("Importing Hypatia cache…")

        self._thread = QThread()
        self._worker = _HypatiaWorker()
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress, Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._on_done,     Qt.ConnectionType.QueuedConnection)
        self._worker.error.connect(self._on_error_hyp,   Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _on_progress(self, msg: str):
        self._status_lbl.setText(msg)
        self.set_status(msg)

    def _on_done(self, result: dict):
        try:
            self._gen_btn.setEnabled(True)
        except RuntimeError:
            return
        self._progress_bar.setRange(0, 1)
        if "error" in result:
            self._progress_bar.setValue(0)
            self._progress_bar.setFormat("Error")
            self.show_error(result["error"])
            self.set_status(f"Error: {result['error']}")
            return

        self._progress_bar.setValue(1)
        self._progress_bar.setFormat("Done")
        self.set_status("Hypatia cache import complete.")
        lbl = QLabel(
            f"<b>Import complete.</b><br>"
            f"Snapshot date: {result['snapshot_date']}<br>"
            f"Stars in hypatia_cache: {result['inserted']:,}<br>"
            f"Abundance rows: {result['abundance_rows']:,}<br>"
            f"Stars with [Fe/H]: {result['fe_h_count']:,}<br>"
            f"Element axes that failed (skipped): {result['errors']}<br>"
            f"Source: {result['source']}"
        )
        lbl.setWordWrap(True)
        self.add_result_widget(lbl)

    def _on_error_hyp(self, msg: str):
        try:
            self._gen_btn.setEnabled(True)
        except RuntimeError:
            return
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("Error")
        self.show_error(msg)
        self.set_status(f"Error: {msg}")


class _DustFetchWorker(QObject):
    """Worker for the dust-map fetch / cache-status task (CLI option 59)."""

    finished = Signal(object)
    error    = Signal(str)
    progress = Signal(str)

    def __init__(self, map_sel: str, check_only: bool):
        super().__init__()
        self._map_sel = map_sel
        self._check_only = check_only

    def run(self):
        import core.dust

        def cb(msg):
            self.progress.emit(msg)
        try:
            result = core.dust.compute_dust_fetch(
                map_sel=self._map_sel, check_only=self._check_only,
                progress_callback=cb)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class FetchDustMapPanel(ResultPanel):
    """Fetch Dust Map Data panel — the GUI surface of CLI option 59.

    Downloads the 3D dust map data (Leike 2020 + Edenhofer 2024) into the
    gitignored data/dust/ cache that the query.py dust-* subcommands read.
    WSL/Linux only — the optional 'dust' extra (dustmaps + healpy) has no native
    Windows pip wheel, so on a checkout without it the controls are disabled with
    an install hint rather than a broken entry (mirrors the import-utility
    pattern of ImportGcnsPanel)."""

    def build_inputs(self):
        info = QLabel(
            "Downloads the 3D dust map data into <code>data/dust/</code> "
            "(gitignored, fetch-once, offline thereafter). The dust query path "
            "(<code>query.py dust-sightline / dust-between</code> and the route "
            "planners' <code>--weight dust</code>) reads this cache. Files are "
            "large: Leike 2020 ~2.4 GB, Edenhofer 2024 ~3.2 GB (auto = both, "
            "~5.6 GB); Zenodo can be slow. <b>WSL/Linux only</b> — needs the "
            "optional 'dust' extra (<code>pip install -r requirements-dust.txt</code>)."
        )
        info.setWordWrap(True)
        self._layout.addWidget(info)

        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(QLabel("Map:"))
        self._map_combo = QComboBox()
        self._map_combo.addItem("Auto (both)", "auto")
        self._map_combo.addItem("Near-field (Leike 2020)", "near-field")
        self._map_combo.addItem("Edenhofer 2024", "edenhofer")
        rl.addWidget(self._map_combo)
        self._check_btn = QPushButton("Check Status")
        self._fetch_btn = QPushButton("Fetch (download)")
        self._check_btn.clicked.connect(lambda: self._run(check_only=True))
        self._fetch_btn.clicked.connect(lambda: self._run(check_only=False))
        rl.addWidget(self._check_btn)
        rl.addWidget(self._fetch_btn)
        rl.addStretch(1)
        self._layout.addWidget(row)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("Ready")
        self._layout.addWidget(self._progress_bar)

        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._layout.addWidget(self._status_lbl)

        self._layout.addWidget(self._build_manual_group())

        # Gate: disable on a checkout without the optional dust extra.
        import core.dust
        if not core.dust._dustmaps_available():
            self._check_btn.setEnabled(False)
            self._fetch_btn.setEnabled(False)
            self._progress_bar.setFormat("Unavailable")
            self._status_lbl.setText(
                "The optional 'dust' extra is not installed. In the WSL/Linux "
                "venv:  pip install -r requirements-dust.txt")

        self._input_count = self._layout.count()

    # ── Manual download (the in-app fetch is slow — see the explanation) ──────

    def _build_manual_group(self) -> QGroupBox:
        """A copyable 'manual download' box: why the in-app fetch is slow, plus
        resumable wget/aria2c commands (aimed at the real cache dir)."""
        box = QGroupBox("Download is slow? Manual download (recommended for the big files)")
        v = QVBoxLayout(box)

        why = QLabel(
            "The maps are hosted on <b>Zenodo</b> (CERN's open-data repository). "
            "Zenodo <b>bandwidth-throttles</b> large anonymous file downloads "
            "(often ~0.5 MB/s), so the in-app <i>Fetch</i> of the 2.4 GB / 3.2 GB "
            "files can take well over an hour — and it <b>cannot resume</b> a "
            "broken transfer (it verifies an md5 and restarts from zero on "
            "failure). For a faster, <b>resumable</b> one-time download, run the "
            "commands below in the WSL/Linux venv, then click <i>Check Status</i> "
            "above — dustmaps verifies the md5 and uses the cached file. The fetch "
            "is one-time; the cache is offline thereafter."
        )
        why.setWordWrap(True)
        v.addWidget(why)

        self._cmd_box = QPlainTextEdit()
        self._cmd_box.setReadOnly(True)
        self._cmd_box.setPlainText(self._manual_commands())
        self._cmd_box.setStyleSheet(
            "font-family: Consolas, 'DejaVu Sans Mono', monospace; font-size: 11px;")
        self._cmd_box.setMinimumHeight(190)
        self._cmd_box.setProperty("no_width_cap", True)
        v.addWidget(self._cmd_box)

        copy_btn = QPushButton("Copy commands")
        copy_btn.clicked.connect(self._copy_commands)
        v.addWidget(copy_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        return box

    def _manual_commands(self) -> str:
        import core.dust as d
        leike_dir = d._DUST_CACHE_DIR / d._MAP_FILE["leike2020"][0]
        eden_dir = d._DUST_CACHE_DIR / d._MAP_FILE["edenhofer2023"][0]
        return (
            "# One-time resumable download into the dust cache, then click 'Check\n"
            "# Status' above. aria2c (-c resume, -x4 parallel connections) is\n"
            "# usually faster past Zenodo's per-connection throttle; wget -c also\n"
            "# resumes. Run in the WSL/Linux venv.\n"
            "\n"
            "# Leike 2020  (~2.4 GB, md5 1ea998fdaef58f53da639356362223ba)\n"
            f"aria2c -c -x4 -d '{leike_dir}' \\\n"
            "  'https://zenodo.org/record/3993082/files/mean_std.h5'\n"
            "\n"
            "# Edenhofer 2024  (~3.2 GB, md5 10c823a5fcf81b47b6e15530bcdf54dc)\n"
            f"aria2c -c -x4 -d '{eden_dir}' \\\n"
            "  'https://zenodo.org/record/8187943/files/mean_and_std_healpix.fits'\n"
            "\n"
            "# No aria2c? Resumable wget equivalents:\n"
            f"# wget -c -P '{leike_dir}' \\\n"
            "#   'https://zenodo.org/record/3993082/files/mean_std.h5'\n"
            f"# wget -c -P '{eden_dir}' \\\n"
            "#   'https://zenodo.org/record/8187943/files/mean_and_std_healpix.fits'\n"
        )

    def _copy_commands(self):
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(self._cmd_box.toPlainText())
            self.set_status("Manual-download commands copied to clipboard.")

    def build_results_area(self):
        pass

    def _run(self, check_only: bool):
        map_sel = self._map_combo.currentData()
        self._check_btn.setEnabled(False)
        self._fetch_btn.setEnabled(False)
        self._progress_bar.setRange(0, 0)   # busy/indeterminate
        self._progress_bar.setFormat("Checking…" if check_only else "Downloading…")
        self._status_lbl.setText("")
        self.clear_results()
        self.set_status("Checking dust cache…" if check_only else "Fetching dust maps…")

        self._thread = QThread()
        self._worker = _DustFetchWorker(map_sel, check_only)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress, Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._on_done,     Qt.ConnectionType.QueuedConnection)
        self._worker.error.connect(self._on_error_dust,  Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _reenable(self) -> bool:
        try:
            self._check_btn.setEnabled(True)
            self._fetch_btn.setEnabled(True)
            return True
        except RuntimeError:
            return False

    def _on_progress(self, msg: str):
        self._status_lbl.setText(msg)
        self.set_status(msg)

    def _on_done(self, result: dict):
        if not self._reenable():
            return
        self._progress_bar.setRange(0, 1)
        if "error" in result:
            self._progress_bar.setValue(0)
            self._progress_bar.setFormat("Error")
            self.show_error(result["error"])
            self.set_status(f"Error: {result['error']}")
            return

        self._progress_bar.setValue(1)
        self._progress_bar.setFormat("Done")
        self.set_status("Dust map fetch complete.")
        rows = []
        for f in result.get("fetched", []):
            size = f"{f['size_mb']:,.1f}" if f.get("size_mb") is not None else "—"
            rows.append([f["map"], f["status"], size, f["path"]])
        self.add_result_widget(QLabel(f"<b>Cache dir:</b> {result['cache_dir']}"))
        self.add_result_widget(
            self.make_table(["Map", "Status", "Size (MB)", "Path"], rows))

    def _on_error_dust(self, msg: str):
        if not self._reenable():
            return
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("Error")
        self.show_error(msg)
        self.set_status(f"Error: {msg}")


class _ResearchPriorsWorker(QObject):
    """Worker for the research-priors contract import (validate-before-store)."""

    finished = Signal(object)
    error    = Signal(str)
    progress = Signal(str)

    def __init__(self, path):
        super().__init__()
        self._path = path

    def run(self):
        def cb(msg):
            self.progress.emit(msg)
        try:
            result = core.research_priors.compute_research_priors_ingest(
                path=self._path or None, progress_callback=cb)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ImportResearchPriorsPanel(ResultPanel):
    """Import Research Priors panel (Phase R3) — mirrors ImportGcnsPanel/Hypatia.

    Validates a versioned formation-priors data contract and caches it (validate-
    before-store). Once ingested, `generate-system` / the System Generator's
    research_policy='strict' draws research-calibrated priors from it. The shipped
    default is the committed synthetic SAMPLE; a consumer with real priors Browses
    to their own contract file. See docs/research-priors-contract.md.
    """

    def build_inputs(self):
        info = QLabel(
            "Validates a formation-priors data contract (a single versioned JSON "
            "document) and stores it in the gitignored data/research_priors/ cache. "
            "Then System Generator / query.py generate-system with research policy "
            "'strict' draws research-calibrated priors from it (re-tagging emitted "
            "fields grounding=research-calibrated). The default file is the committed "
            "synthetic SAMPLE — Browse to a real contract when one exists. A malformed "
            "contract is rejected and the existing cache is left intact."
        )
        info.setWordWrap(True)
        self._layout.addWidget(info)

        path_w = QWidget()
        path_row = QHBoxLayout(path_w)
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.addWidget(QLabel("Contract file:"))
        self._path_edit = QLineEdit(str(core.research_priors._SAMPLE_CONTRACT_PATH))
        self._path_edit.setProperty("no_width_cap", True)
        path_row.addWidget(self._path_edit)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        path_row.addWidget(browse)
        self._layout.addWidget(path_w)

        btn_w = QWidget()
        btn_row = QHBoxLayout(btn_w)
        btn_row.setContentsMargins(0, 0, 0, 0)
        self._check_btn = QPushButton("Check Status")
        self._check_btn.clicked.connect(self._check)
        self._import_btn = QPushButton("Import")
        self._import_btn.setFixedHeight(32)
        self._import_btn.clicked.connect(self._run)
        btn_row.addWidget(self._check_btn)
        btn_row.addWidget(self._import_btn)
        btn_row.addStretch()
        self._layout.addWidget(btn_w)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("Ready")
        self._layout.addWidget(self._progress_bar)

        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._layout.addWidget(self._status_lbl)

        self._input_count = self._layout.count()

    def build_results_area(self):
        pass

    def _browse(self):
        fn, _ = QFileDialog.getOpenFileName(
            self, "Select research-priors contract", "", "JSON files (*.json);;All files (*)")
        if fn:
            self._path_edit.setText(fn)

    def _check(self):
        self.clear_results()
        st = core.research_priors.get_research_priors_status()
        if st["loaded"]:
            lbl = QLabel(
                f"<b>Research priors loaded.</b><br>"
                f"Dataset: {st['dataset_version']}<br>"
                f"Schema: {st['schema_version']}<br>"
                f"Origin contexts calibrated: {st['origin_contexts']}<br>"
                f"Stored at: {st['stored_at']}")
        else:
            lbl = QLabel("No research priors ingested — research_policy='strict' will "
                         "return a curated error until you Import a contract.")
        lbl.setWordWrap(True)
        self.add_result_widget(lbl)
        self.set_status("Research-priors cache status checked.")

    def _run(self):
        self._import_btn.setEnabled(False)
        self._progress_bar.setRange(0, 0)   # busy
        self._progress_bar.setFormat("Importing…")
        self._status_lbl.setText("")
        self.clear_results()
        self.set_status("Importing research priors…")

        self._thread = QThread()
        self._worker = _ResearchPriorsWorker(self._path_edit.text().strip())
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress, Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._on_done,     Qt.ConnectionType.QueuedConnection)
        self._worker.error.connect(self._on_error_rp,    Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_progress(self, msg: str):
        self._status_lbl.setText(msg)
        self.set_status(msg)

    def _on_done(self, result: dict):
        try:
            self._import_btn.setEnabled(True)
        except RuntimeError:
            return
        self._progress_bar.setRange(0, 1)
        if "error" in result:
            self._progress_bar.setValue(0)
            self._progress_bar.setFormat("Error")
            self.show_error(result["error"])
            self.set_status(f"Error: {result['error']}")
            return
        self._progress_bar.setValue(1)
        self._progress_bar.setFormat("Done")
        self.set_status("Research-priors import complete.")
        lbl = QLabel(
            f"<b>Import complete.</b><br>"
            f"Dataset: {result['dataset_version']}<br>"
            f"Schema: {result['schema_version']}<br>"
            f"Sampling axes loaded: {result['axes_loaded']}<br>"
            f"Origin contexts calibrated: {result['origin_contexts']}<br>"
            f"Source: {result['source']}<br>"
            f"Cached at: {result['cache_dir']}")
        lbl.setWordWrap(True)
        self.add_result_widget(lbl)

    def _on_error_rp(self, msg: str):
        try:
            self._import_btn.setEnabled(True)
        except RuntimeError:
            return
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("Error")
        self.show_error(msg)
        self.set_status(f"Error: {msg}")
