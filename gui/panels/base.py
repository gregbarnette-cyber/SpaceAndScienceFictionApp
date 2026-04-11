# gui/panels/base.py — Shared base class for all feature panels.

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QPushButton,
    QTableView, QTextEdit, QLabel,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt


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
