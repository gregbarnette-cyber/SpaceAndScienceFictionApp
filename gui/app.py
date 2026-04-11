# gui/app.py — Main application window.

from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QTreeWidget, QStackedWidget, QLabel,
)
from PySide6.QtCore import Qt


class MainWindow(QMainWindow):
    """Top-level window.

    Layout:
      Left  (~220 px, fixed) : QTreeWidget navigation panel
      Right (stretches)      : QStackedWidget holding all feature panels

    Panels are created lazily on first use and cached in self._panels.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Space & Science Fiction App")
        self.setMinimumSize(1100, 700)

        self._panels: dict = {}   # panel_class → widget instance

        # ── Navigation tree ───────────────────────────────────────────────────
        self.nav_tree = QTreeWidget()
        self.nav_tree.setFixedWidth(220)
        self.nav_tree.setHeaderHidden(True)

        # ── Content stack ─────────────────────────────────────────────────────
        self.stack = QStackedWidget()
        placeholder = QLabel("Select a feature from the left panel")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(placeholder)

        # ── Splitter ──────────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.nav_tree)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        # ── Populate nav tree ─────────────────────────────────────────────────
        from gui.nav import populate_nav
        populate_nav(self.nav_tree, self)

    # ── Public API ────────────────────────────────────────────────────────────

    def show_panel(self, panel_class) -> None:
        """Create (if needed) and display the panel for panel_class."""
        if panel_class not in self._panels:
            panel = panel_class(self)
            self._panels[panel_class] = panel
            self.stack.addWidget(panel)
        self.stack.setCurrentWidget(self._panels[panel_class])

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Clean up the SQLite connection on exit (no-op until Phase F)."""
        import core.db
        core.db.close_conn()
        event.accept()
