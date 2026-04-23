# gui/panels/base.py — Shared base class for all feature panels.

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QPushButton,
    QTableView, QTextEdit, QLabel, QSizePolicy,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt, QObject, QThread, Signal, QTimer


class Worker(QObject):
    """Run a callable in a QThread and deliver the result via Qt signals.

    Usage:
        worker = Worker(fn, *args, **kwargs)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(callback)   # receives result dict
        worker.error.connect(err_callback)  # receives error str
        worker.progress.connect(status_cb)  # receives intermediate status strings
    """

    finished = Signal(object)   # emits the return value of fn(*args, **kwargs)
    error    = Signal(str)      # emits the exception message on failure
    progress = Signal(str)      # emits intermediate status messages

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn     = fn
        self._args   = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as e:
            # Route exceptions through finished so tab-based panels can display
            # the error inside their own result area instead of triggering
            # _on_error → clear_results() which would destroy the tabs widget.
            result = {"error": f"{type(e).__name__}: {e}"}
        self.finished.emit(result)


class ResultPanel(QWidget):
    """Base class for all feature panels.

    Subclasses build their input form in build_inputs() and implement
    calculate() which calls a core function and passes the result to render().

    Class-level thread registry keeps QThread wrappers alive until the OS
    thread has fully exited — prevents "QThread destroyed while running" GC
    errors that occur when CPython's refcount immediately destroys a wrapper
    while Qt's internal running-flag is still true.

    Layout:
        - build_inputs() places widgets above the results area (form rows,
          calculate button, etc.)
        - build_results_area() creates a QTextEdit in the lower portion
          (panels that prefer QTableView override or supplement this)
    """

    # Class-level registry: keeps thread wrappers alive across all instances.
    # Entries are removed 500 ms after thread.finished, giving the OS thread
    # time to fully exit before Python GC can call QThread::~QThread().
    _live_threads: list = []

    def __init__(self, window):
        super().__init__()
        self.window = window
        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.setSpacing(0)
        self._init_container()

    def _init_container(self):
        """(Re)create the inner container and populate it via build_inputs/build_results_area."""
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(6)
        self._outer_layout.addWidget(self._container)
        self.build_inputs()
        self.build_results_area()
        # Constrain all input buttons to their natural text width.
        for btn in self._container.findChildren(QPushButton):
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def reset(self):
        """Reset panel to its initial load state by rebuilding all content."""
        self._outer_layout.removeWidget(self._container)
        self._container.deleteLater()
        self._init_container()

    # ── Override points ───────────────────────────────────────────────────────

    def build_inputs(self):
        """Override to add input widgets above the results area."""

    def build_results_area(self):
        """Default results area: a read-only monospace QTextEdit."""
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFontFamily("Courier New")
        self._layout.addWidget(self.result_text)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def make_table(self, headers: list, rows: list) -> QTableView:
        """Create a QTableView populated with *headers* (single row) and *rows*.

        Each element of *rows* is a list of values; None is shown as 'N/A'.
        The caller is responsible for adding the returned view to a layout.
        """
        model = QStandardItemModel(len(rows), len(headers))
        model.setHorizontalHeaderLabels(headers)
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                item = QStandardItem(str(val) if val is not None else "N/A")
                item.setEditable(False)
                model.setItem(r, c, item)
        view = QTableView()
        view.setModel(model)
        view.setSortingEnabled(True)
        view.horizontalHeader().setStretchLastSection(True)
        view.resizeColumnsToContents()
        return view

    def clear_results(self):
        """Remove every widget from the layout except those added in build_inputs()."""
        # Widgets added by build_inputs are tracked in self._input_count
        keep = getattr(self, "_input_count", 0)
        while self._layout.count() > keep:
            item = self._layout.takeAt(keep)
            w = item.widget()
            if w:
                w.deleteLater()

    def add_result_widget(self, widget):
        """Append a widget to the results section (below inputs)."""
        self._layout.addWidget(widget)

    def show_error(self, message: str):
        """Display an error message in the results area."""
        self.clear_results()
        label = QLabel(message)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: red;")
        self.add_result_widget(label)

    def set_status(self, msg: str):
        """Update the main window status bar."""
        self.window.statusBar().showMessage(msg)

    # ── Background threading (Phase C+) ──────────────────────────────────────

    def run_in_background(self, fn, *args, on_result=None, on_progress=None, **kwargs):
        """Execute fn(*args, **kwargs) in a QThread.

        Disables run_btn (if present), shows "Working…" in the status bar,
        then delivers the result to on_result (or self.render) on the main
        thread when the worker finishes.

        on_progress: optional callable(str) for intermediate status updates.
          If None, progress messages are shown in the status bar.

        Active threads are kept in self._bg_threads to prevent premature GC.
        Chained calls (e.g. SIMBAD → database) each create their own thread;
        using a list ensures the first thread is not destroyed while it is
        still winding down when the second call overwrites self._thread.
        """
        self.set_status("Working…")
        if hasattr(self, "run_btn"):
            self.run_btn.setEnabled(False)

        thread = QThread()
        worker = Worker(fn, *args, **kwargs)
        worker.moveToThread(thread)

        # Class-level registry keeps BOTH thread and worker alive until the OS
        # thread has fully exited.  Storing only thread is insufficient: if
        # self._worker is overwritten before the thread finishes (e.g. chained
        # SIMBAD → catalog calls), the worker's Python ref-count drops to zero
        # and CPython destroys it.  Destroying the worker disconnects its
        # finished signal, so thread.quit() is never called and the callback
        # is never delivered — the thread idles forever and prints
        # "QThread: Destroyed while thread is still running" on app exit.
        pair = (thread, worker)
        ResultPanel._live_threads.append(pair)

        # Keep per-instance references for callers that inspect them.
        self._thread = thread
        self._worker = worker

        callback    = on_result   if on_result   is not None else self.render
        progress_cb = on_progress if on_progress is not None else self.set_status

        thread.started.connect(worker.run)
        # QueuedConnection ensures callback and error handler are always
        # delivered on the main thread.
        worker.finished.connect(callback,       Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(thread.quit)
        worker.error.connect(self._on_error,    Qt.ConnectionType.QueuedConnection)
        worker.progress.connect(progress_cb,    Qt.ConnectionType.QueuedConnection)
        thread.finished.connect(self._on_thread_done)
        # Remove pair from registry after a 500 ms grace period; by then the
        # OS thread is guaranteed to have fully exited on all platforms.
        thread.finished.connect(
            lambda p=pair: QTimer.singleShot(
                500,
                lambda: (ResultPanel._live_threads.remove(p)
                         if p in ResultPanel._live_threads else None)
            )
        )

        thread.start()

    def _on_error(self, msg: str):
        self.set_status(f"Error: {msg}")
        self.show_error(msg)
        if hasattr(self, "run_btn"):
            try:
                self.run_btn.setEnabled(True)
            except RuntimeError:
                pass  # button was deleted by a reset() while the thread was running

    def _on_thread_done(self):
        self.set_status("Done")
        if hasattr(self, "run_btn"):
            try:
                self.run_btn.setEnabled(True)
            except RuntimeError:
                pass  # button was deleted by a reset() while the thread was running
