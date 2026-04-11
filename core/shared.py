# core/shared.py — Shared constants and helper functions used across core modules.

import csv
import math
import os
import re

# ─── Physical Constants ───────────────────────────────────────────────────────

G_MS2        = 9.80665                # 1 g in m/s²
C_MS         = 299_792_458.0          # speed of light in m/s
V_CAP_MS     = 0.03 * C_MS           # 3% of c in m/s
M_PER_AU     = 149_597_870_700.0      # metres per AU
M_PER_LM     = C_MS * 60.0           # metres per light-minute
HOURS_PER_YEAR  = 365.25 * 24        # 8765.82  (Julian year)
HOURS_PER_MONTH = HOURS_PER_YEAR / 12

# ─── Spectral Class Helpers ───────────────────────────────────────────────────

# Negative lookbehind prevents matching the OBAFGKM letter when preceded by
# another uppercase letter (e.g. the 'A' in 'DA1.9' white-dwarf types).
_SP_PATTERN = re.compile(r"(?<![A-Z])([OBAFGKM])(\d+(?:\.\d+)?)")

_LETTER_SEQUENCE = ["O", "B", "A", "F", "G", "K", "M"]

# ─── CSV Designation Helpers ──────────────────────────────────────────────────

_CSV_PREFIX_MAP = [
    ("NAME ",       "NAME"),
    ("GJ ",         "GJ"),
    ("HD ",         "HD"),
    ("HIP ",        "HIP"),
    ("HR ",         "HR"),
    ("Wolf ",       "Wolf"),
    ("LHS ",        "LHS"),
    ("BD+",         "BD"),
    ("BD-",         "BD"),
    ("BD ",         "BD"),
    ("K2 ",         "K2"),
    ("Kepler-",     "Kepler"),
    ("Kepler ",     "Kepler"),
    ("KOI-",        "KOI"),
    ("KOI ",        "KOI"),
    ("TOI-",        "TOI"),
    ("TOI ",        "TOI"),
    ("CoRoT-",      "CoRoT"),
    ("CoRoT ",      "CoRoT"),
    ("COCONUTS-",   "COCONUTS"),
    ("HAT-P-",      "HAT_P"),
    ("WASP-",       "WASP"),
    ("TIC ",        "TIC"),
    ("Gaia EDR3 ",  "Gaia EDR3"),
    ("2MASS J",     "2MASS"),
    ("2MASS ",      "2MASS"),
]

_CSV_DESIG_KEYS = [
    "NAME", "GJ", "HD", "HIP", "HR", "Wolf", "LHS", "BD",
    "K2", "Kepler", "KOI", "TOI", "CoRoT", "COCONUTS", "HAT_P", "WASP",
    "TIC", "Gaia EDR3", "2MASS",
]

# ─── Module-level cache for main sequence data ────────────────────────────────

_MAIN_SEQUENCE_DATA = None


# ─── Helper Functions ─────────────────────────────────────────────────────────

def _format_travel_time(total_hours):
    """Break total_hours into years, months, days, hours, minutes, seconds.
    Only includes units that are >= 1 (or seconds if < 1 minute)."""
    HOURS_PER_DAY = 24.0
    HOURS_PER_MIN = 1 / 60.0

    remaining = total_hours

    years = int(remaining / HOURS_PER_YEAR)
    remaining -= years * HOURS_PER_YEAR

    months = int(remaining / HOURS_PER_MONTH)
    remaining -= months * HOURS_PER_MONTH

    days = int(remaining / HOURS_PER_DAY)
    remaining -= days * HOURS_PER_DAY

    hours = int(remaining)
    remaining -= hours

    minutes = int(remaining * 60)
    remaining -= minutes / 60

    seconds = remaining * 3600

    parts = []
    if years:
        parts.append(f"{years} Year{'s' if years != 1 else ''}")
    if months:
        parts.append(f"{months} Month{'s' if months != 1 else ''}")
    if days:
        parts.append(f"{days} Day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} Hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} Minute{'s' if minutes != 1 else ''}")
    if seconds >= 0.005 and (not parts or total_hours < HOURS_PER_MIN):
        parts.append(f"{seconds:.2f} Second{'s' if seconds != 1.0 else ''}")

    return ", ".join(parts) if parts else "0 Seconds"


def _fval(v):
    """Convert to float; return None if missing or NaN."""
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def _fmt(v, decimals=3, default="N/A"):
    """Format value to fixed-decimal string, or return default."""
    f = _fval(v)
    return f"{f:.{decimals}f}" if f is not None else default


def _safe_get(row, col_names, col):
    """Return a column value, or None if missing/masked/blank."""
    if col not in col_names:
        return None
    val = row[col]
    try:
        if hasattr(val, "mask") and val.mask:
            return None
    except Exception:
        pass
    s = str(val).strip()
    if s in ("", "--", "N/A", "nan", "None"):
        return None
    return val


def _parse_designations(result, ids_result):
    """Extract and organise star designations from SIMBAD results."""
    keys_order = [
        "MAIN_ID", "NAME", "GJ", "HD", "HIP", "HR", "Wolf", "LHS", "BD",
        "K2", "Kepler", "KOI", "TOI", "CoRoT", "COCONUTS", "HAT_P", "WASP",
        "TIC", "Gaia EDR3", "2MASS",
    ]
    designations = {k: None for k in keys_order}

    if result is not None and "main_id" in result.colnames:
        designations["MAIN_ID"] = str(result["main_id"][0])

    if ids_result is None:
        return designations

    prefix_map = [
        ("NAME ",       "NAME"),
        ("GJ ",         "GJ"),
        ("HD ",         "HD"),
        ("HIP ",        "HIP"),
        ("HR ",         "HR"),
        ("Wolf ",       "Wolf"),
        ("LHS ",        "LHS"),
        ("BD+",         "BD"),
        ("BD-",         "BD"),
        ("BD ",         "BD"),
        ("K2 ",         "K2"),
        ("Kepler-",     "Kepler"),
        ("Kepler ",     "Kepler"),
        ("KOI-",        "KOI"),
        ("KOI ",        "KOI"),
        ("TOI-",        "TOI"),
        ("TOI ",        "TOI"),
        ("CoRoT-",      "CoRoT"),
        ("CoRoT ",      "CoRoT"),
        ("COCONUTS-",   "COCONUTS"),
        ("HAT-P-",      "HAT_P"),
        ("WASP-",       "WASP"),
        ("TIC ",        "TIC"),
        ("Gaia EDR3 ",  "Gaia EDR3"),
        ("2MASS J",     "2MASS"),
        ("2MASS ",      "2MASS"),
    ]

    for row in ids_result:
        id_str = str(row["id"]).strip()
        for prefix, key in prefix_map:
            if id_str.startswith(prefix) and designations[key] is None:
                designations[key] = id_str
                break

    return designations


def _parse_designations_from_ids(ids_string):
    """Parse a pipe-separated SIMBAD ids string into a comma-separated designation string.

    Returns a string of found designations (excluding MAIN_ID), or an empty string.
    """
    desig = {k: None for k in _CSV_DESIG_KEYS}
    if not ids_string:
        return ""
    for id_str in ids_string.split("|"):
        id_str = id_str.strip()
        for prefix, key in _CSV_PREFIX_MAP:
            if id_str.startswith(prefix) and desig[key] is None:
                desig[key] = id_str
                break
    parts = [desig[k] for k in _CSV_DESIG_KEYS if desig[k] is not None]
    return ", ".join(parts)


def _parse_spectral_class(sp_str):
    """Extract primary class letter and numeric subtype from a SIMBAD spectral string.

    Returns (letter, subtype_float) or (None, None) if no OBAFGKM class found.
    Uses search so prefixes like 'sd' in 'sdG5' are skipped transparently.
    """
    if not sp_str or sp_str in ("N/A", "None", ""):
        return None, None
    m = _SP_PATTERN.search(sp_str)
    if not m:
        return None, None
    return m.group(1), float(m.group(2))


def _lookup_spectral_type(sp_str):
    """Return (row_dict, key_used_str) for the nearest ceiling entry in the CSV.

    Ceiling rule: smallest available subtype number >= requested subtype.
    Within-class fallthrough: if all entries are cooler than requested (e.g. F9
    with entries only up to F7), advance to the next cooler letter class and
    return its hottest (lowest subtype) entry (e.g. G0).
    Falls back to the last entry in the final available class if no next class exists.
    Returns (None, None) if class letter not found in data.
    """
    letter, subtype = _parse_spectral_class(sp_str)
    if letter is None:
        return None, None

    data = _load_main_sequence_data()

    try:
        start_idx = _LETTER_SEQUENCE.index(letter)
    except ValueError:
        return None, None

    for idx in range(start_idx, len(_LETTER_SEQUENCE)):
        current_letter = _LETTER_SEQUENCE[idx]
        entries = data.get(current_letter)
        if not entries:
            continue

        if idx == start_idx:
            for entry_subtype, row in entries:
                if entry_subtype >= subtype:
                    return row, row.get("Spectral Class", "").strip()
        else:
            row = entries[0][1]
            return row, row.get("Spectral Class", "").strip()

    entries = data.get(letter)
    if entries:
        row = entries[-1][1]
        return row, row.get("Spectral Class", "").strip()
    return None, None


def _load_main_sequence_data():
    """Load propertiesOfMainSequenceStars.csv into a per-class lookup structure."""
    global _MAIN_SEQUENCE_DATA
    if _MAIN_SEQUENCE_DATA is not None:
        return _MAIN_SEQUENCE_DATA

    filepath = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "propertiesOfMainSequenceStars.csv",
    )
    data = {}

    try:
        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sc = row.get("Spectral Class", "").strip()
                m = _SP_PATTERN.match(sc)
                if not m:
                    continue
                letter  = m.group(1)
                subtype = float(m.group(2))
                data.setdefault(letter, []).append((subtype, row))
        for letter in data:
            data[letter].sort(key=lambda t: t[0])
    except Exception as e:
        print(f"Warning: Could not load propertiesOfMainSequenceStars.csv: {e}")
        data = {}

    _MAIN_SEQUENCE_DATA = data
    return _MAIN_SEQUENCE_DATA


def _kopparapu_seff(teff, zone):
    """Return Seff boundary (Kopparapu et al. 2014) for the given zone key."""
    tS = teff - 5780.0
    params = {
        "rv":   (1.776,  2.136e-4,  2.533e-8,  -1.332e-11, -3.097e-15),
        "rg5":  (1.188,  1.433e-4,  1.707e-8,  -8.968e-12, -2.084e-15),
        "rg01": (0.99,   1.209e-4,  1.404e-8,  -7.418e-12, -1.713e-15),
        "rg":   (1.107,  1.332e-4,  1.580e-8,  -8.308e-12, -1.931e-15),
        "mg":   (0.356,  6.171e-5,  1.698e-9,  -3.198e-12, -5.575e-16),
        "em":   (0.320,  5.547e-5,  1.526e-9,  -2.874e-12, -5.011e-16),
    }
    SeffSUN, a, b, c, d = params[zone]
    return SeffSUN + a*tS + b*tS**2 + c*tS**3 + d*tS**4
