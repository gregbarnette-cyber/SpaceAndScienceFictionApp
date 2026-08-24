# gui/panels/search_common.py — Shared widgets for the Phase G Search & Filter panels.
#
# Two reusable pieces:
#   SpectralClassControl — the O B A F G K M / Other chip row + refine box used by
#       all three search panels (mirrors core.shared.spectral_where / spectral_adql).
#   SearchPanelBase      — a ResultPanel with an inner QTabWidget hosting a
#       persistent "Search Results" tab plus closable detail tabs, so the user can
#       open multiple stars/planets at once and switch between them. Opening an
#       already-open item re-focuses its tab.

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QLineEdit,
    QTabWidget, QSizePolicy, QTableView, QTabBar,
)
from PySide6.QtCore import Qt, Signal

from gui.panels.base import ResultPanel

_CHIP_LETTERS = ["O", "B", "A", "F", "G", "K", "M", "Other"]


class SpectralClassControl(QWidget):
    """Multi-select spectral-class chips + a substring refine box.

    .classes() -> list[str]   selected chip letters (subset of _CHIP_LETTERS)
    .refine()   -> str        the refine text (stripped)
    .is_empty() -> bool       True when nothing is selected and refine is blank
    changed                   Signal emitted on any selection/text change
    """

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        for letter in _CHIP_LETTERS:
            btn = QPushButton(letter)
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn.setMaximumWidth(60)
            btn.toggled.connect(lambda _checked: self.changed.emit())
            self._buttons[letter] = btn
            layout.addWidget(btn)
        self._refine = QLineEdit()
        self._refine.setPlaceholderText("refine e.g. 2V, V")
        self._refine.setMaximumWidth(110)
        self._refine.setProperty("no_width_cap", True)
        self._refine.textChanged.connect(lambda _t: self.changed.emit())
        layout.addWidget(self._refine)
        layout.addStretch()

    def classes(self) -> list:
        return [l for l, b in self._buttons.items() if b.isChecked()]

    def refine(self) -> str:
        return self._refine.text().strip()

    def is_empty(self) -> bool:
        return not self.classes() and not self.refine()

    def clear(self):
        for b in self._buttons.values():
            b.setChecked(False)
        self._refine.clear()


class SearchPanelBase(ResultPanel):
    """ResultPanel with a persistent 'Search Results' tab + closable detail tabs.

    Subclasses implement:
        build_search_ui(layout)  — populate the Search Results page (form, then
                                    call self._build_results_scaffold(layout)).
    and use:
        self._render_table(headers, display_rows, records, open_label, on_open, noun)
        self.open_detail_tab(key, title, factory)
    """

    def build_inputs(self):
        pass  # all inputs live inside the Search Results tab

    def build_results_area(self):
        self._open_details = {}     # key -> page widget
        self._sel_record = None

        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(False)
        self._tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._tabs.tabCloseRequested.connect(self._on_tab_close)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._results_page = QWidget()
        results_layout = QVBoxLayout(self._results_page)
        results_layout.setContentsMargins(2, 2, 2, 2)
        results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._tabs.addTab(self._results_page, "Search Results")
        # The Search Results tab is permanent — strip its close button.
        for side in (QTabBar.ButtonPosition.RightSide, QTabBar.ButtonPosition.LeftSide):
            self._tabs.tabBar().setTabButton(0, side, None)

        self._layout.addWidget(self._tabs, 1)
        # Only the tabs widget lives directly in _layout; record the boundary so
        # an inherited clear_results()/show_error() can never delete it.
        self._input_count = self._layout.count()
        self.build_search_ui(results_layout)

    def _make_detail(self, panel_cls, name_attr, value):
        """Construct an embedded detail panel, prefill its name field, and search.

        Shared by the leaf panels' _open_* handlers so the G1/G2/G3 drill-down
        wiring isn't copy-pasted three times.
        """
        p = panel_cls(self.window)
        getattr(p, name_attr).setText(value)
        p._search()
        return p

    # ── results-page scaffold ────────────────────────────────────────────────

    def _build_results_scaffold(self, layout):
        """Create the count label, table holder, footer, and selection bar."""
        self._count_lbl = QLabel("No search run yet.")
        self._count_lbl.setStyleSheet("color: #777;")
        layout.addWidget(self._count_lbl)

        self._table_holder = QWidget()
        self._table_layout = QVBoxLayout(self._table_holder)
        self._table_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._table_holder, 1)

        self._footer_lbl = QLabel("")
        self._footer_lbl.setStyleSheet("color: #a06a00; font-size: 11px;")
        self._footer_lbl.setVisible(False)
        layout.addWidget(self._footer_lbl)

        sel_row = QHBoxLayout()
        self._on_open = None
        self._on_wiki = None
        self._open_btn = QPushButton("Open in new tab →")
        self._open_btn.setVisible(False)
        self._open_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._open_btn.clicked.connect(self._open_clicked)
        sel_row.addWidget(self._open_btn)
        # Sibling "Wikipedia" button — shown on row selection only when a subclass opts in by
        # passing on_wiki to _render_table (so G2/G3/L4 stay unaffected until they wire it).
        self._wiki_btn = QPushButton("📖 Open in Wikipedia →")
        self._wiki_btn.setVisible(False)
        self._wiki_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._wiki_btn.clicked.connect(self._wiki_clicked)
        sel_row.addWidget(self._wiki_btn)
        sel_row.addStretch()
        layout.addLayout(sel_row)

    def _open_clicked(self):
        if self._on_open is not None and self._sel_record is not None:
            self._on_open(self._sel_record)

    def _wiki_clicked(self):
        if self._on_wiki is not None and self._sel_record is not None:
            self._on_wiki(self._sel_record)

    def _clear_table(self):
        while self._table_layout.count():
            item = self._table_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _render_table(self, headers, display_rows, records, open_label, on_open, noun,
                      on_wiki=None):
        """Populate the results table, wire row selection, and the Open button(s)."""
        self._sel_record = None
        self._on_open = on_open
        self._on_wiki = on_wiki
        self._clear_table()
        self._open_btn.setVisible(False)
        self._wiki_btn.setVisible(False)

        self._count_lbl.setStyleSheet("color: #222; font-weight: 600;")
        self._count_lbl.setText(f"{len(records)} {noun}{'' if len(records) == 1 else 's'} found.")

        view = self.make_table(headers, display_rows)
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        model = view.model()
        for i, rec in enumerate(records):
            model.item(i, 0).setData(rec, Qt.ItemDataRole.UserRole)

        def _on_sel(*_):
            idxs = view.selectionModel().selectedRows()
            if not idxs:
                return
            item = model.itemFromIndex(idxs[0].siblingAtColumn(0))
            self._sel_record = item.data(Qt.ItemDataRole.UserRole)
            self._open_btn.setText(open_label)
            self._open_btn.setVisible(True)
            if self._on_wiki is not None:
                self._wiki_btn.setVisible(True)

        view.selectionModel().selectionChanged.connect(_on_sel)
        self._table_layout.addWidget(view)

    def _set_footer(self, capped, cap):
        if capped:
            self._footer_lbl.setText(f"Showing first {cap} results (result cap reached).")
            self._footer_lbl.setVisible(True)
        else:
            self._footer_lbl.setVisible(False)

    def _show_search_error(self, msg):
        self._sel_record = None
        self._clear_table()
        self._open_btn.setVisible(False)
        self._wiki_btn.setVisible(False)
        self._footer_lbl.setVisible(False)
        self._count_lbl.setStyleSheet("color: #b03030; font-weight: 600;")
        self._count_lbl.setText(msg)

    # ── detail tabs ──────────────────────────────────────────────────────────

    def open_detail_tab(self, key, title, factory):
        """Focus an existing detail tab for *key*, else create one from factory()."""
        existing = self._open_details.get(key)
        if existing is not None and self._tabs.indexOf(existing) != -1:
            self._tabs.setCurrentWidget(existing)
            return
        widget = factory()
        idx = self._tabs.addTab(widget, title)
        self._open_details[key] = widget
        self._tabs.setCurrentIndex(idx)

    def _on_tab_changed(self, _index):
        # The search panel itself is never in full-screen diagram mode, so the
        # app nav tree should be visible whenever the user switches tabs. An
        # embedded detail panel's "Show Diagrams" hides window.nav_tree; without
        # this, switching away from that tab (instead of closing it) would leave
        # the nav stranded hidden.
        nav = getattr(self.window, "nav_tree", None)
        if nav is not None:
            nav.show()

    def _on_tab_close(self, index):
        if index == 0:
            return  # Search Results is permanent
        widget = self._tabs.widget(index)
        self._tabs.removeTab(index)
        for k, w in list(self._open_details.items()):
            if w is widget:
                del self._open_details[k]
        if widget:
            widget.deleteLater()
        # A detail panel may have been closed while in full-screen diagram mode
        # (which hides the app nav tree). Restore it defensively.
        nav = getattr(self.window, "nav_tree", None)
        if nav is not None:
            nav.show()
