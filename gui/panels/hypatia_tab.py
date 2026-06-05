# gui/panels/hypatia_tab.py — Shared Hypatia Catalog tab builder.
#
# Used by any panel that shows a "Hypatia" data tab.

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableView, QSizePolicy, QScrollArea,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QStandardItemModel, QStandardItem

from core.hypatia_elements import CATEGORIES, category_label, display_symbol


def _tbl(headers, rows) -> QTableView:
    model = QStandardItemModel(len(rows), len(headers))
    model.setHorizontalHeaderLabels(headers)
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            item = QStandardItem(str(val) if val is not None else "N/A")
            item.setEditable(False)
            model.setItem(r, c, item)
    view = QTableView()
    view.setModel(model)
    view.setSortingEnabled(False)
    view.horizontalHeader().setStretchLastSection(True)
    view.resizeColumnsToContents()
    view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return view


def fit_table_height(view: QTableView) -> None:
    """Set view to exact height of header + all rows (no dead space, no scrollbar)."""
    def _apply():
        try:
            view.resizeRowsToContents()
            h = view.horizontalHeader().height() + view.verticalHeader().length()
            h += view.frameWidth() * 2
            sb = view.horizontalScrollBar()
            if sb.isVisible():
                h += sb.sizeHint().height()
            view.setFixedHeight(h)
        except RuntimeError:
            pass
    _apply()
    QTimer.singleShot(0, _apply)
    QTimer.singleShot(50, _apply)


def build_hypatia_tab(hypatia: dict) -> QScrollArea:
    """Return a QScrollArea with Stellar Properties, Kinematics, and Abundances tables."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    layout.setSpacing(6)
    layout.setContentsMargins(8, 8, 8, 8)

    if "error" in hypatia:
        lbl = QLabel(hypatia["error"])
        lbl.setStyleSheet("color: #888888; font-style: italic;")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        scroll.setWidget(content)
        return scroll

    props = hypatia.get("properties", {})
    abundances = hypatia.get("abundances", [])

    def _fmts(v, dp):
        if v is None:
            return "N/A"
        try:
            return f"{float(v):.{dp}f}"
        except (TypeError, ValueError):
            return str(v) if v else "N/A"

    def _fmtsign(v, dp):
        if v is None:
            return "N/A"
        try:
            return f"{float(v):+.{dp}f}"
        except (TypeError, ValueError):
            return "N/A"

    teff = props.get("teff")
    teff_s = str(int(teff)) if teff is not None else "N/A"

    # ── Stellar Properties ────────────────────────────────────────────────────
    layout.addWidget(QLabel("<b>Stellar Properties</b>"))
    t_props = _tbl(
        ["T_eff (K)", "log g", "Spectral Type", "V mag", "B-V", "Distance (pc)", "Disk"],
        [[
            teff_s,
            _fmts(props.get("logg"), 3),
            props.get("spectral_type") or "N/A",
            _fmts(props.get("vmag"), 3),
            _fmts(props.get("bv"), 3),
            _fmts(props.get("distance_pc"), 2),
            props.get("disk") or "N/A",
        ]],
    )
    layout.addWidget(t_props)
    fit_table_height(t_props)

    # ── Kinematics ────────────────────────────────────────────────────────────
    layout.addWidget(QLabel("<b>Kinematics</b>"))
    t_kin = _tbl(
        ["U (km/s)", "V (km/s)", "W (km/s)", "PM RA (mas/yr)", "PM Dec (mas/yr)"],
        [[
            _fmts(props.get("u_vel"), 2),
            _fmts(props.get("v_vel"), 2),
            _fmts(props.get("w_vel"), 2),
            _fmts(props.get("pm_ra"), 3),
            _fmts(props.get("pm_dec"), 3),
        ]],
    )
    layout.addWidget(t_kin)
    fit_table_height(t_kin)

    # ── Elemental Abundances (grouped by nucleosynthetic family) ───────────────
    layout.addWidget(QLabel("<b>Elemental Abundances  (Lodders 2009)</b>"))
    if abundances:
        headers = ["Element", "Name", "[X/H] Mean", "±Std", "Min", "Max", "# Catalogs"]
        # Bucket the measured species by their category, preserving parser order.
        by_cat = {}
        for a in abundances:
            by_cat.setdefault(a.get("category", ""), []).append(a)

        for key, label, _color in CATEGORIES:
            group = by_cat.get(key)
            if not group:
                continue
            hdr = QLabel(f"<b>{label}</b>")
            hdr.setStyleSheet("color: #555555; margin-top: 4px;")
            layout.addWidget(hdr)
            rows = []
            for a in group:
                rows.append([
                    display_symbol(a["element"]),
                    a.get("name", ""),
                    _fmtsign(a.get("mean"), 3),
                    _fmts(a.get("std"), 3),
                    _fmtsign(a.get("min"), 3),
                    _fmtsign(a.get("max"), 3),
                    str(a["n"]) if a.get("n") is not None else "N/A",
                ])
            t_abund = _tbl(headers, rows)
            layout.addWidget(t_abund)
            fit_table_height(t_abund)
    else:
        layout.addWidget(QLabel("No elemental abundance data available for this star."))

    scroll.setWidget(content)
    return scroll
