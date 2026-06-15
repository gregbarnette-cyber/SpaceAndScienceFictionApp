"""Phase O F2 — reusable help-dialog component (GUI layer; pure presentation).

``show_help_dialog(parent, title, html)`` opens a non-modal ``QDialog`` with a
scrollable ``QTextBrowser``; ``info_button(title, html, parent)`` returns an
"ℹ What is this?" push-button wired to it.

No ``core``/DB dependency. First consumer: O11 (Toomre Kinematics) — see
``gui/help_text.py``. Reusable by any panel that wants an inline explanation.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox, QPushButton,
)
from PySide6.QtCore import Qt

# Hold references so non-modal dialogs aren't garbage-collected before the user
# closes them (WA_DeleteOnClose frees the underlying widget on close).
_open_help_dialogs = []

_INFO_LABEL = "ℹ What is this?"   # ℹ


def show_help_dialog(parent, title: str, html: str) -> QDialog:
    """Open a non-modal help dialog showing ``html`` (rich text). Returns the dialog."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumSize(560, 460)
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.Window)

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(12, 12, 12, 10)
    layout.setSpacing(8)

    browser = QTextBrowser()
    browser.setOpenExternalLinks(True)
    browser.setHtml(html)
    layout.addWidget(browser)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dlg.close)
    buttons.accepted.connect(dlg.close)
    layout.addWidget(buttons)

    _open_help_dialogs.append(dlg)
    dlg.destroyed.connect(lambda *_: _forget(dlg))
    dlg.show()
    dlg.raise_()
    return dlg


def _forget(dlg) -> None:
    """Drop a closed dialog from the keep-alive list (best-effort)."""
    try:
        _open_help_dialogs.remove(dlg)
    except (ValueError, RuntimeError):
        pass


def info_button(title: str, html: str, parent=None,
                label: str = _INFO_LABEL) -> QPushButton:
    """Return an info push-button that opens ``show_help_dialog`` on click.

    The dialog's parent is resolved at click time (``btn.window()``) when ``parent``
    is None, so it centres on the host window.
    """
    btn = QPushButton(label, parent)
    btn.setToolTip(title)
    btn.clicked.connect(
        lambda: show_help_dialog(parent or btn.window(), title, html)
    )
    return btn
