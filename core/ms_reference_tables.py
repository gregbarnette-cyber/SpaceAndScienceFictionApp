"""CR-30.1 — the WB-owned main-sequence reference tables: md5-checked loader + parsed structures.

The three CSVs in ``data/cr30/`` are **WB-owned** (``scifiWorldBuilding-Claude``
``research/star-analysis-cr-queue/cr30-data/``), vendored **byte-identical** and never edited here — a data change
goes through WB with a new md5 (contract CR-30.1, ruling 2):

* ``cr30_mamajek2022_dwarf_sequence.csv`` — **S1**, Mamajek's "A Modern Mean Dwarf Stellar Color and Effective
  Temperature Sequence", version 2022.04.16; 87 rows O3V–M9.5V.
* ``cr30_mist_v25_ms_lifetime.csv`` — MIST v2.5, [Fe/H] 0, [α/Fe] 0, **non-rotating**; 171 tracks 0.10–300 M☉;
  the main-sequence duration from ZAMS (EEP 202) to the first X_c < 10⁻⁴ (10⁻² below 0.65 M☉).
* ``cr30_bhac15_overread_factor.csv`` — the BHAC15 over-read factor table (888 rows; routes mks / luminosity / type).

S1's raw file sits beside them with ``MANIFEST.txt``; **nothing parses it at run time**.

Every file's bytes are hashed **before** parsing; a missing, md5-mismatched or structurally inconsistent file
raises ``Cr30DataError`` (surfaced by the entry points as a curated ``{"error"}``, exit 1) — never a fallback to
another table (the CR-24 / CR-26 convention). ``#`` comment lines are skipped before parsing; columns are read by
header name; an empty cell is a missing value for that cell only (ruling 69). **The values in use are these
files'** — the DB mirror tables (``core/db.py``) are display copies only and nothing reads a value from them.

Pure: stdlib only, no network, no Qt. ``SPACE_APP_CR30_DATA_DIR`` overrides the directory (tests). The parsed
tables are memoised per resolved directory; ``clear_cr30_cache()`` resets.
"""

import csv
import hashlib
import io
import os

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_DIR = os.path.join(_REPO, "data", "cr30")

S1_FILE = "cr30_mamajek2022_dwarf_sequence.csv"
MIST_FILE = "cr30_mist_v25_ms_lifetime.csv"
FACTOR_FILE = "cr30_bhac15_overread_factor.csv"

# The contract's pinned md5s (CR-30.1) — the re-gate checks these too.
CR30_MD5 = {
    S1_FILE: "2b7746f6339b8b72fb589351c54c0594",
    MIST_FILE: "b212537685cf8d5787df23a03e1f262a",
    FACTOR_FILE: "1ce818caf06a5a1d99b70dfabed9068b",
}
_ROW_COUNTS = {S1_FILE: 87, MIST_FILE: 171, FACTOR_FILE: 888}
_COLUMNS = {
    S1_FILE: ("SpT", "Teff", "B-V", "Mv", "BCv", "logL", "R_Rsun", "Msun", "s1_line"),
    MIST_FILE: ("initial_mass", "ms_duration_yr", "end_point", "t_zams_yr", "t_end_yr", "track_file",
                "zams_eep", "zams_line", "end_eep", "end_line", "end_center_h1"),
    FACTOR_FILE: ("route", "age_gyr", "true_mass", "inferred_read", "old_ref_read", "factor", "null_reason",
                  "input_at_age", "input_at_ref", "iso_line", "ref_iso_line"),
}
FACTOR_ROUTES = ("mks", "luminosity", "type")
# The cut's eleven age nodes (contract CR-30.6 D) — the factor table carries exactly these.
FACTOR_AGE_NODES = (0.01, 0.025, 0.05, 0.08, 0.1, 0.12, 0.2, 0.3, 0.4, 0.5, 0.625)
_MIST_END_POINTS = ("first_Xc_lt_1e-4", "first_Xc_lt_1e-2")


class Cr30DataError(Exception):
    """A CR-30 data file is missing, fails its pinned md5, or fails the structural self-check."""


_CACHE = {}


def data_dir():
    """The resolved data directory (``SPACE_APP_CR30_DATA_DIR`` wins over the repo default)."""
    return os.path.abspath(os.environ.get("SPACE_APP_CR30_DATA_DIR") or _DEFAULT_DIR)


def clear_cr30_cache():
    _CACHE.clear()


def _num(s):
    """An empty cell → ``None``; else a float."""
    s = (s or "").strip()
    return float(s) if s else None


def file_md5(name, d=None):
    """The md5 of a vendored file's bytes (no verification) — for the GUI import / status display."""
    with open(os.path.join(d or data_dir(), name), "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()


def _read_verified(d, name):
    path = os.path.join(d, name)
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as e:
        raise Cr30DataError(f"CR-30 data file missing: {name} ({e.strerror or e})") from None
    got = hashlib.md5(raw).hexdigest()
    if got != CR30_MD5[name]:
        raise Cr30DataError(f"CR-30 data file {name} fails its pinned md5 (got {got}, expected "
                            f"{CR30_MD5[name]}) — the WB-owned files must be vendored byte-identical")
    text = raw.decode("utf-8")
    body = "".join(ln for ln in io.StringIO(text) if not ln.lstrip().startswith("#"))
    reader = csv.DictReader(io.StringIO(body))
    if tuple(reader.fieldnames or ()) != _COLUMNS[name]:
        raise Cr30DataError(f"CR-30 data file {name}: header {reader.fieldnames!r}, expected "
                            f"{list(_COLUMNS[name])!r}")
    rows = list(reader)
    if len(rows) != _ROW_COUNTS[name]:
        raise Cr30DataError(f"CR-30 data file {name}: {len(rows)} rows, expected {_ROW_COUNTS[name]}")
    return rows


def _parse_s1(rows):
    out, seen, masses = [], set(), set()
    for i, r in enumerate(rows):
        spt = r["SpT"].strip()
        if not spt.endswith("V") or spt in seen:
            raise Cr30DataError(f"{S1_FILE}: row {i + 1} SpT {spt!r} is not a unique class-V type")
        seen.add(spt)
        row = {"SpT": spt, "raw": dict(r)}
        for col in ("Teff", "B-V", "Mv", "BCv", "logL", "R_Rsun", "Msun"):
            try:
                row[col] = _num(r[col])
            except ValueError:
                raise Cr30DataError(f"{S1_FILE}: {spt} column {col} is not a number ({r[col]!r})") from None
        if row["Msun"] is None or row["Msun"] in masses:
            raise Cr30DataError(f"{S1_FILE}: {spt} Msun missing or duplicated")
        masses.add(row["Msun"])
        row["s1_line"] = int(r["s1_line"])
        out.append(row)
    if out[0]["SpT"] != "O3V" or out[-1]["SpT"] != "M9.5V":
        raise Cr30DataError(f"{S1_FILE}: expected O3V first and M9.5V last")
    return tuple(out)


def _parse_mist(rows):
    out, last = [], None
    for r in rows:
        try:
            m = float(r["initial_mass"])
            dur, tz, te = float(r["ms_duration_yr"]), float(r["t_zams_yr"]), float(r["t_end_yr"])
        except ValueError:
            raise Cr30DataError(f"{MIST_FILE}: non-numeric row {r!r}") from None
        if last is not None and m <= last:
            raise Cr30DataError(f"{MIST_FILE}: initial_mass not strictly increasing at {m}")
        if r["end_point"] not in _MIST_END_POINTS:
            raise Cr30DataError(f"{MIST_FILE}: {m} end_point {r['end_point']!r} not a known end point")
        if dur <= 0 or abs((te - tz) - dur) > 1e-6 * dur:
            raise Cr30DataError(f"{MIST_FILE}: {m} ms_duration_yr is not t_end_yr - t_zams_yr")
        last = m
        out.append({"initial_mass": m, "ms_duration_yr": dur, "end_point": r["end_point"],
                    "t_zams_yr": tz, "t_end_yr": te})
    return tuple(out)


def _parse_factor(rows):
    out = []
    for r in rows:
        route = r["route"]
        if route not in FACTOR_ROUTES:
            raise Cr30DataError(f"{FACTOR_FILE}: unknown route {route!r}")
        try:
            age = float(r["age_gyr"])
            row = {"route": route, "age_gyr": age, "true_mass": float(r["true_mass"]),
                   "inferred_read": _num(r["inferred_read"]), "old_ref_read": _num(r["old_ref_read"]),
                   "factor": _num(r["factor"]), "null_reason": (r["null_reason"] or "").strip() or None}
        except ValueError:
            raise Cr30DataError(f"{FACTOR_FILE}: non-numeric row {r!r}") from None
        if not any(abs(age - n) < 1e-9 for n in FACTOR_AGE_NODES):
            raise Cr30DataError(f"{FACTOR_FILE}: age {age} is not one of the cut's nodes")
        if row["factor"] is None and row["null_reason"] is None:
            raise Cr30DataError(f"{FACTOR_FILE}: a null factor without a null_reason ({route}, {age})")
        out.append(row)
    return tuple(out)


def _tables(d=None):
    d = d or data_dir()
    t = _CACHE.get(d)
    if t is None:
        t = {"s1": _parse_s1(_read_verified(d, S1_FILE)),
             "mist": _parse_mist(_read_verified(d, MIST_FILE)),
             "factor": _parse_factor(_read_verified(d, FACTOR_FILE))}
        _CACHE[d] = t
    return t


def s1_rows():
    """S1's 87 rows in S1 order (O3V → M9.5V): ``{SpT, Teff, B-V, Mv, BCv, logL, R_Rsun, Msun, s1_line, raw}``
    (floats, ``None`` for an empty cell; ``raw`` = the file's strings, for display)."""
    return _tables()["s1"]


def mist_tracks():
    """MIST v2.5's 171 tracks, ascending mass: ``{initial_mass, ms_duration_yr, end_point, t_zams_yr, t_end_yr}``."""
    return _tables()["mist"]


def factor_rows():
    """The over-read factor table's 888 rows: ``{route, age_gyr, true_mass, inferred_read, old_ref_read, factor,
    null_reason}``."""
    return _tables()["factor"]


def verify_all():
    """Load (and so verify) every file; ``{name: {"md5", "rows"}}``. Raises ``Cr30DataError``."""
    t = _tables()
    return {S1_FILE: {"md5": CR30_MD5[S1_FILE], "rows": len(t["s1"])},
            MIST_FILE: {"md5": CR30_MD5[MIST_FILE], "rows": len(t["mist"])},
            FACTOR_FILE: {"md5": CR30_MD5[FACTOR_FILE], "rows": len(t["factor"])}}
