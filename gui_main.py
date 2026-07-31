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

# The Windows 8pt look is the target on every platform. Linux/WSL was previously
# left at the Qt default (Sans Serif 9pt -> Noto Sans, 12px @96 DPI), which
# rendered noticeably larger than Windows (Segoe UI 8pt, ~10.7px @96 DPI), so
# match the point size here. Segoe UI is not installed on Linux, so the default
# family is kept and only the size is set (Noto Sans 8pt -> 11px, the closest
# available match). Set this to None to restore the old Linux default.
_LINUX_FONT_POINT_SIZE = 8


def _apply_app_font(app):
    """Normalize the app font so Linux/WSL matches the Windows look."""
    if sys.platform == "win32":
        app.setFont(QFont("Segoe UI", _WINDOWS_FONT_POINT_SIZE))
    elif _LINUX_FONT_POINT_SIZE is not None:
        font = app.font()
        font.setPointSize(_LINUX_FONT_POINT_SIZE)
        app.setFont(font)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    _apply_app_font(app)

    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())
