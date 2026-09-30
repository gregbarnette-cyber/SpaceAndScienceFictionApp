"""CR-24 — the WB-owned V_ISM data file (Wood 2021 Table 3) + the R&L 2008 Table 16 cloud vectors.

``data/cr24/cr24_wood2021_vism.csv`` is **WB-owned** (``scifiWorldBuilding-Claude``
``research/exclusion-boundary-medium-physics/cr24-data/``), vendored **byte-identical** and never edited here —
a data change is a model change that goes through WB with a new md5 (CR-24 spec §Units, D1 / ⚑7). Its bytes are
md5-hashed before parsing; a missing, mismatched or structurally inconsistent file raises ``Cr24DataError``
(surfaced by the entry points as a curated ``{"error"}``, exit 1). The file is keyed by the SAME ``row_key`` /
``simbad_main_id`` as CR-26's measured table — cross-checked at load.

The 15 cloud vectors are Redfield & Linsky 2008 Table 16 (downwind heliocentric V0, l0, b0 and the rigid-vector
fit χ²), transcribed from the spec's §Units table; Cartesian (U, V, W) are computed from (V0, l0, b0) — never a
rounded triple. The DQ2 cloud set (the clouds within 15 km/s of the LIC vector) is derived here and asserted.

Pure: stdlib only, no network, no Qt. ``SPACE_APP_CR24_DATA_DIR`` overrides the directory (tests).
"""

import csv
import hashlib
import io
import math
import os

from core import shared

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_DIR = os.path.join(_REPO, "data", "cr24")

CR24_FILE = "cr24_wood2021_vism.csv"
CR24_MD5 = {CR24_FILE: "ffd164238d055d9134fe65bb9f9df097"}
_ROW_COUNT = 36

# R&L 2008 Table 16 (spec §Units): name → (V0 km/s, l0 deg, b0 deg, χ²). LIC is the default vector (D2).
CLOUDS = {
    "LIC": (23.84, 187.0, -13.5, 2.2), "G": (29.6, 184.5, -20.6, 1.3), "Blue": (13.89, 205.5, -21.7, 2.4),
    "Aql": (58.6, 187.0, -50.8, 2.6), "Eri": (24.1, 196.7, -17.7, 0.3), "Aur": (25.22, 212.0, -16.4, 2.1),
    "Hyades": (14.69, 164.2, -42.8, 1.3), "Mic": (28.45, 203.0, -3.3, 0.5), "Oph": (32.25, 217.7, 0.8, 3.9),
    "Gem": (36.3, 207.2, -1.2, 1.7), "NGP": (37.0, 189.8, -5.4, 3.8), "Leo": (23.5, 191.3, -8.9, 1.5),
    "Dor": (52.94, 157.3, -47.93, 0.8), "Vel": (45.2, 195.4, -19.1, 0.8), "Cet": (60.0, 197.11, -8.72, 8.9),
}
DEFAULT_CLOUD = "LIC"
CLOUD_SET_RADIUS_KMS = 15.0            # DQ2: the contract's cut (the gap between Hyades 14.57 and Gem 17.28)
CLOUD_SET_EXPECTED = ("LIC", "Leo", "Eri", "G", "Mic", "Aur", "Blue", "NGP", "Hyades")


class Cr24DataError(Exception):
    """The CR-24 data file is missing, fails its pinned md5, or fails the structural / cross-table check."""


def cloud_vector(name):
    """Heliocentric Galactic Cartesian (U, V, W) km/s of a Table 16 cloud: U = V0 cos b cos l, V = V0 cos b sin l,
    W = V0 sin b (U toward the Galactic centre, V toward rotation, W toward the NGP)."""
    v0, l0, b0, _chi2 = CLOUDS[name]
    lr, br = math.radians(l0), math.radians(b0)
    return (v0 * math.cos(br) * math.cos(lr), v0 * math.cos(br) * math.sin(lr), v0 * math.sin(br))


def cloud_chi2(name):
    return CLOUDS[name][3]


def cloud_names():
    """The 15 valid ``--cloud`` names (for the usage error)."""
    return tuple(CLOUDS)


def _dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def cloud_set():
    """DQ2: the clouds whose vector lies within 15 km/s of the LIC vector, ordered by that distance."""
    lic = cloud_vector(DEFAULT_CLOUD)
    ds = sorted(((_dist(cloud_vector(n), lic), n) for n in CLOUDS), key=lambda t: t[0])
    return tuple(n for d, n in ds if d <= CLOUD_SET_RADIUS_KMS)


if set(cloud_set()) != set(CLOUD_SET_EXPECTED):              # the spec's nine — a transcription guard
    raise Cr24DataError(f"CR-24 cloud set {cloud_set()} ≠ the spec's {CLOUD_SET_EXPECTED}")


_CACHE = {}


def data_dir():
    return os.path.abspath(os.environ.get("SPACE_APP_CR24_DATA_DIR") or _DEFAULT_DIR)


def clear_cr24_cache():
    _CACHE.clear()


def _parse(d):
    path = os.path.join(d, CR24_FILE)
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as e:
        raise Cr24DataError(f"CR-24 data file missing: {CR24_FILE} ({e.strerror or e})") from None
    got = hashlib.md5(raw).hexdigest()
    if got != CR24_MD5[CR24_FILE]:
        raise Cr24DataError(f"CR-24 data file {CR24_FILE} fails its pinned md5 (got {got}, expected "
                            f"{CR24_MD5[CR24_FILE]}) — the WB-owned file must be vendored byte-identical")
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    if len(rows) != _ROW_COUNT:
        raise Cr24DataError(f"CR-24 data file {CR24_FILE}: {len(rows)} rows, expected {_ROW_COUNT}")
    by_key = {}
    for r in rows:
        k = r["row_key"]
        if k in by_key:
            raise Cr24DataError(f"{CR24_FILE}: duplicate row_key {k!r}")
        try:
            vism, theta = float(r["wood2021_vism_kms"]), float(r["wood2021_theta_deg"])
        except (TypeError, ValueError):
            raise Cr24DataError(f"{CR24_FILE}: {k} — non-numeric V_ISM / θ") from None
        if not (vism > 0 and math.isfinite(vism)):
            raise Cr24DataError(f"{CR24_FILE}: {k} — V_ISM must be finite and > 0")
        by_key[k] = {"row_key": k, "simbad_main_id": r["simbad_main_id"], "wood2021_row": r["wood2021_row"],
                     "wood2021_star": r["wood2021_star"], "vism_kms": vism, "theta_deg": theta}
    # the cross-check: keyed by the same row_key / simbad_main_id as CR-26's measured table
    from core import stellar_wind_tables as swt
    cr26 = {v["row_key"]: v["simbad_main_id"] for v in swt.load_cr26_tables()["MEASURED"].values()}
    if set(cr26) != set(by_key):
        raise Cr24DataError(f"{CR24_FILE}: row_keys differ from CR-26's measured table "
                            f"(only here: {sorted(set(by_key) - set(cr26))}; only CR-26: "
                            f"{sorted(set(cr26) - set(by_key))})")
    for k, r in by_key.items():
        if shared.collapse_ws(r["simbad_main_id"]) != shared.collapse_ws(cr26[k]):
            raise Cr24DataError(f"{CR24_FILE}: {k} simbad_main_id {r['simbad_main_id']!r} ≠ CR-26's {cr26[k]!r}")
    return by_key


def load_cr24_table():
    """``{row_key: {vism_kms, theta_deg, …}}`` — md5-verified, cross-checked, memoised per directory."""
    d = data_dir()
    if d not in _CACHE:
        _CACHE[d] = _parse(d)
    return _CACHE[d]


def measured_row_vism(row_key):
    """Wood 2021 Table 3's V_ISM (float km/s) for a CR-26 measured ``row_key``, or ``None``."""
    r = load_cr24_table().get(row_key)
    return r["vism_kms"] if r else None
