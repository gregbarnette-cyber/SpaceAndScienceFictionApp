#!/usr/bin/env python3
"""GUI entry point for the Space & Science Fiction App."""

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from gui.app import MainWindow

# Windows defaults to Segoe UI 9pt, whose taller metrics make the UI less dense
# than the Linux/WSL default ("Sans Serif" 9pt). Drop Windows to 8pt so both
# platforms render at a similar density. Tune this if 8pt is too small.
_WINDOWS_FONT_POINT_SIZE = 8


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    if sys.platform == "win32":
        app.setFont(QFont("Segoe UI", _WINDOWS_FONT_POINT_SIZE))

    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())
