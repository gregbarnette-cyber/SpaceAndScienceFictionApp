# gui/panels/base.py — Shared base class for all feature panels.

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QPushButton,
    QTableView, QTextEdit, QLabel,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt, QObject, QThread, Signal


class Worker(QObject):
    """Run a callable in a QThread and deliver the result via Qt signals.

    Usage:
        worker = Worker(fn, *args, **kwargs)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(callback)   # receives result dict
        worker.error.connect(err_callback)  # receives error str
    """

    finished = Signal(object)   # emits the return value of fn(*args, **kwargs)
    error    = Signal(str)      # emits the exception message on failure

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn     = fn
        self._args   = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ResultPanel(QWidget):
    """Base class for all feature panels.

    Subclasses build their input form in build_inputs() and implement
    calculate() which calls a core function and passes the result to render().

    Layout:
        - build_inputs() places widgets above the results area (form rows,
          calculate button, etc.)
        - build_results_area() creates a QTextEdit in the lower portion
          (panels that prefer QTableView override or supplement this)
    """

    def __init__(self, window):
        super().__init__()
        self.window = window
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(6)
        self.build_inputs()
        self.build_results_area()

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

    def run_in_background(self, fn, *args, on_result=None, **kwargs):
        """Execute fn(*args, **kwargs) in a QThread.

        Disables run_btn (if present), shows "Working…" in the status bar,
        then delivers the result to on_result (or self.render) on the main
        thread when the worker finishes.

        Stores self._thread and self._worker to prevent premature GC.
        """
        self.set_status("Working…")
        if hasattr(self, "run_btn"):
            self.run_btn.setEnabled(False)

        self._thread = QThread()
        self._worker = Worker(fn, *args, **kwargs)
        self._worker.moveToThread(self._thread)

        callback = on_result if on_result is not None else self.render

        self._thread.started.connect(self._worker.run)
        # QueuedConnection ensures callback and error handler are always
        # delivered on the main thread, even if the worker signal fires
        # from the worker thread (PySide6 can use DirectConnection for
        # plain Python callables with AutoConnection, which would crash
        # because Qt widgets must only be touched from the main thread).
        self._worker.finished.connect(callback,          Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.error.connect(self._on_error,       Qt.ConnectionType.QueuedConnection)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._on_thread_done)

        self._thread.start()

    def _on_error(self, msg: str):
        self.set_status(f"Error: {msg}")
        self.show_error(msg)
        if hasattr(self, "run_btn"):
            self.run_btn.setEnabled(True)

    def _on_thread_done(self):
        self.set_status("Done")
        if hasattr(self, "run_btn"):
            self.run_btn.setEnabled(True)
