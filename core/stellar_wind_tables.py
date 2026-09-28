"""CR-26 — the WB-owned wind-model data files: md5-checked loader + parsed structures.

The six CSVs in ``data/cr26/`` are **WB-owned** (``scifiWorldBuilding-Claude``
``research/exclusion-boundary-medium-physics/cr26-w5-data/``), vendored **byte-identical** and never
edited here — a data change is a model change that goes through WB with a new md5 (spec "Units, symbols,
and the WB data files"). This is the first runtime md5 check in ``core/``: every file's bytes are hashed
**before** parsing, and a mismatched or missing file raises ``Cr26DataError`` (surfaced by the entry points
as a curated ``{"error"}``, exit 1) — the model never computes from an unverified table.

Pure: stdlib only (hashlib/csv/os), no network, no Qt. ``SPACE_APP_CR26_DATA_DIR`` overrides the
directory (tests). The parsed tables are memoised per resolved directory; ``clear_cr26_cache()`` resets.
"""

import csv
import hashlib
import io
import os

from core import shared

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_DIR = os.path.join(_REPO, "data", "cr26")

# The spec's pinned md5s (spec table "WB-owned data files") — the re-gate checks these too. The three
# class-statistics files were re-vendored per WB MSG 311 (the shared-source grouping-key fix; Greg's §4 ruling 21).
CR26_MD5 = {
    "cr26_measured_tier.csv": "5b74d08beef2384770e14c319de3b4ff",
    "cr26_class_states.csv": "0502174c6ef86e33d88ecd5fc59247de",
    "cr26_fork8_class_bands.csv": "c5e900c5df8af25eda4d39cb4bed0b4d",
    "cr26_fork9_limit_tables.csv": "1e333643da1adb0fd317698590b5cf49",
    "cr26_subtype_radius.csv": "0aed02ad1af5bec4506623db4c6d6549",
    "cr26_line_halfwidth.csv": "5636c4d7bf2aa0e01247c36185154aee",
}
_ROW_COUNTS = {
    "cr26_measured_tier.csv": 36, "cr26_class_states.csv": 17, "cr26_fork8_class_bands.csv": 5,
    "cr26_fork9_limit_tables.csv": 455, "cr26_subtype_radius.csv": 40, "cr26_line_halfwidth.csv": 601,
}

# The five class bins. ``M0–M3.5`` carries an EN DASH (U+2013) in every file and in the output enum.
BIN_M_EARLY = "M0–M3.5"
BIN_M_LATE = "M4+"
CLASS_BINS = ("F", "G", "K", BIN_M_EARLY, BIN_M_LATE)

_FORK9_LO, _FORK9_HI = 70, 160         # grid index round(limit × 20): 3.50 … 8.00 in 0.05 steps
_HW_LO, _HW_HI = 200, 800              # grid index round(logFX × 100): 2.00 … 8.00 in 0.01 steps


class Cr26DataError(Exception):
    """A CR-26 data file is missing, fails its pinned md5, or fails the structural self-check."""


_CACHE = {}


def data_dir():
    """The resolved data directory (``SPACE_APP_CR26_DATA_DIR`` wins over the repo default)."""
    return os.path.abspath(os.environ.get("SPACE_APP_CR26_DATA_DIR") or _DEFAULT_DIR)


def clear_cr26_cache():
    _CACHE.clear()


def _num(s):
    """An empty cell → ``None``; else a float."""
    s = (s or "").strip()
    return float(s) if s else None


def _read_verified(d, name):
    path = os.path.join(d, name)
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as e:
        raise Cr26DataError(f"CR-26 data file missing: {name} ({e.strerror or e})") from None
    got = hashlib.md5(raw).hexdigest()
    if got != CR26_MD5[name]:
        raise Cr26DataError(f"CR-26 data file {name} fails its pinned md5 (got {got}, expected "
                            f"{CR26_MD5[name]}) — the WB-owned files must be vendored byte-identical")
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    if len(rows) != _ROW_COUNTS[name]:
        raise Cr26DataError(f"CR-26 data file {name}: {len(rows)} rows, expected {_ROW_COUNTS[name]}")
    return rows


collapse_ws = shared.collapse_ws            # the one SIMBAD-id normaliser (core.shared)


def _parse(d):
    measured_rows = _read_verified(d, "cr26_measured_tier.csv")
    states_rows = _read_verified(d, "cr26_class_states.csv")
    f8_rows = _read_verified(d, "cr26_fork8_class_bands.csv")
    f9_rows = _read_verified(d, "cr26_fork9_limit_tables.csv")
    sub_rows = _read_verified(d, "cr26_subtype_radius.csv")
    hw_rows = _read_verified(d, "cr26_line_halfwidth.csv")

    measured = {}
    for r in measured_rows:
        key = collapse_ws(r["simbad_main_id"])
        if key in measured:
            raise Cr26DataError(f"cr26_measured_tier.csv: duplicate simbad_main_id {key!r}")
        if (r["measured_rule"] == "point_combined") != (r["wood_scope"] == "combined_unsplit"):
            raise Cr26DataError(f"cr26_measured_tier.csv: {r['row_key']} — measured_rule point_combined "
                                "must coincide with wood_scope combined_unsplit")
        measured[key] = {
            "row_key": r["row_key"], "system": r["system"], "component": r["component"],
            "simbad_main_id": r["simbad_main_id"], "sp_type_simbad": r["sp_type_simbad"],
            "wood_mdot_sun": _num(r["wood_mdot_sun"]), "wood_limit": r["wood_limit"] or None,
            "wood_scope": r["wood_scope"] or None, "wood_radius_rsun": _num(r["wood_radius_rsun"]),
            "kislyakova_mdot_sun": _num(r["kislyakova_mdot_sun"]),
            "kislyakova_limit": r["kislyakova_limit"] or None,
            "kislyakova_scope": r["kislyakova_scope"] or None,
            "measured_rule": r["measured_rule"],
        }

    states = {}
    for r in states_rows:
        if r["class"] not in CLASS_BINS:
            raise Cr26DataError(f"cr26_class_states.csv: unknown class bin {r['class']!r}")
        states[(r["class"], r["state"])] = {
            "log_fx": _num(r["logFX"]), "point_log": _num(r["point_log_Mdot_per_A"]),
            "regime": r["regime"], "band_lo": _num(r["band_lo_dex"]), "band_hi": _num(r["band_hi_dex"]),
            "weight": _num(r["weight"]), "marginal": r["marginal"].strip() == "True",
            "class_median_r": _num(r["class_median_R_rsun"]),
        }
    for b in CLASS_BINS:
        for st in ("quiet", "typical", "active"):
            if (b, st) not in states:
                raise Cr26DataError(f"cr26_class_states.csv: missing ({b}, {st})")
    for st in ("mode_inactive", "mode_saturated"):
        if (BIN_M_LATE, st) not in states:
            raise Cr26DataError(f"cr26_class_states.csv: missing (M4+, {st})")

    fork8 = {}
    for r in f8_rows:
        fork8[r["class"]] = {"point_log": _num(r["point_log_Mdot_per_A"]),
                             "band_lo": _num(r["band_lo_dex"]), "band_hi": _num(r["band_hi_dex"]),
                             "typical_log_fx": _num(r["typical_logFX"])}
    if set(fork8) != set(CLASS_BINS):
        raise Cr26DataError("cr26_fork8_class_bands.csv: the class bins are not F/G/K/M0–M3.5/M4+")

    fork9 = {b: {} for b in CLASS_BINS}
    for r in f9_rows:
        b = r["class"]
        if b not in fork9:
            raise Cr26DataError(f"cr26_fork9_limit_tables.csv: unknown class bin {b!r}")
        idx = int(round(float(r["limit_logFX"]) * 20))
        fork9[b][idx] = {"limit": float(r["limit_logFX"]), "status": r["status"],
                         "conditional_log_fx": _num(r["conditional_logFX"]),
                         "point_log": _num(r["point_log_Mdot_per_A"]),
                         "band_lo": _num(r["band_lo_dex"]), "band_hi": _num(r["band_hi_dex"])}
    for b, rows in fork9.items():
        if sorted(rows) != list(range(_FORK9_LO, _FORK9_HI + 1)):
            raise Cr26DataError(f"cr26_fork9_limit_tables.csv: the {b} grid is not contiguous 3.50–8.00")

    subtype_r = {}
    for r in sub_rows:
        subtype_r[(r["class"], int(r["subtype"]))] = float(r["median_R_rsun"])

    hw = {}
    for r in hw_rows:
        hw[int(round(float(r["logFX"]) * 100))] = float(r["halfwidth_dex"])
    if sorted(hw) != list(range(_HW_LO, _HW_HI + 1)):
        raise Cr26DataError("cr26_line_halfwidth.csv: the grid is not contiguous 2.00–8.00")

    return {"MEASURED": measured, "CLASS_STATES": states, "FORK8": fork8, "FORK9": fork9,
            "SUBTYPE_R": subtype_r, "HW": hw}


def load_cr26_tables():
    """The parsed, md5-verified CR-26 tables (memoised per directory). Raises ``Cr26DataError``."""
    d = data_dir()
    if d not in _CACHE:
        _CACHE[d] = _parse(d)
    return _CACHE[d]
