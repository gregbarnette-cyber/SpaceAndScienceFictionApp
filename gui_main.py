#!/usr/bin/env python3
"""GUI entry point for the Space & Science Fiction App."""

import sys

from PySide6.QtWidgets import QApplication

from gui.app import MainWindow


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())
