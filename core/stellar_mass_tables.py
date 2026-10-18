"""core/stellar_mass_tables.py — CR-11.2 tier-2 per-star measured-mass catalog.

A **static per-star lookup** consumed by ``core.stellar_mass.resolve_mass`` as its **tier-2**
mass source (precedence: manual ``--mass-solar`` → **this catalog** → Gaia DR3 FLAME → the
``L^0.2632`` mass–luminosity inversion). The tool READS rows; it never computes a fit — the
measured masses are dynamical / interferometric / asteroseismic values pinned by WB from a
primary source and stored as plain numbers.

Two catalogs (mirrors the CR-10.3 rv-precision-catalog architecture exactly):
  * the **internal seed** below (flag-less default) — the four verified anchor rows so the
    default dossier resolves Sirius A → 2.063 M☉ (provenance ``catalog``);
  * an **external WB-owned file** passed via ``--star-mass-catalog <path>``, which **REPLACES**
    the seed wholesale (no merge — WB extends/edits that file with no APP round). Authoritative
    file: ``scifiWorldBuilding-Claude/design-lab/star-system-analysis/deliverables/stellar-mass-catalog.json``.

Match key: the resolved star's ``main_id`` + every ``designations`` value vs a row's ``main_id``
+ ``aliases``, whitespace-collapsed + case-insensitive (handles SIMBAD's ``"* alf CMa"`` /
``"HD  48915"`` double space). A bad/unreadable/invalid external path → ``{"error": …}`` (loud,
never a silent seed fallback); a malformed single row inside a valid file is skipped best-effort.
"""

import json
import math

# Internal seed (flag-less default). The four CR-11.2 anchors, verified-at-primary 2026-08-26,
# mirroring the WB JSON shape. Sirius A / Vega are precisely the bright stars Gaia FLAME saturates
# on, so the catalog — not FLAME — is their authoritative measured-mass source.
_SEED_CATALOG = {
    "schema_version": "1.1.0",      # CR-30.6 C: mass_basis / mass_interval (pre-fire ruling 19 R-10); no age
    "source": ("internal seed (CR-11.2) — the four verified anchors; pass --star-mass-catalog "
               "for the WB-owned file (rows-are-data, REPLACE semantics)"),
    "stars": [
        {
            "id": "Sirius A", "main_id": "* alf CMa",
            "aliases": ["HD 48915A", "HD 48915", "HIP 32349", "GJ 244 A", "HR 2491"],
            "sp_type": "A0mA1Va", "mass_solar": 2.063, "mass_uncertainty_solar": 0.023,
            "mass_kind": "dynamical", "citation": "Bond et al. 2017",
            "mass_basis": "dynamical", "mass_interval": {"lo": 2.040, "hi": 2.086, "kind": "sigma_1"},
            "source": "Bond et al. 2017, ApJ 840:70 (arXiv:1703.10625) — visual+astrometric dynamical orbit",
        },
        {
            "id": "Vega", "main_id": "* alf Lyr",
            "aliases": ["HD 172167", "HIP 91262", "HR 7001", "GJ 721"],
            "sp_type": "A0Va", "mass_solar": 2.135, "mass_uncertainty_solar": 0.074,
            "mass_kind": "gravity-darkened Roche model", "citation": "Yoon et al. 2010",
            "mass_basis": "interferometric", "mass_interval": {"lo": 2.061, "hi": 2.209, "kind": "sigma_1"},
            "source": "Yoon, Peterson & Kurucz 2010, ApJ 708:71 — NPOI Roche-model fit",
        },
        {
            "id": "alpha Centauri A", "main_id": "* alf Cen A",
            "aliases": ["HD 128620", "HIP 71683", "GJ 559 A", "HR 5459"],
            "sp_type": "G2V", "mass_solar": 1.079, "mass_uncertainty_solar": 0.0029,
            "mass_kind": "dynamical", "citation": "Akeson et al. 2021",
            "mass_basis": "dynamical", "mass_interval": {"lo": 1.0761, "hi": 1.0819, "kind": "sigma_1"},
            "source": "Akeson et al. 2021, AJ 162:14 (arXiv:2104.10086) Table 8 'Present work' m_A=1.0788",
        },
        {
            "id": "alpha Centauri B", "main_id": "* alf Cen B",
            "aliases": ["HD 128621", "HIP 71681", "GJ 559 B", "HR 5460"],
            "sp_type": "K1V", "mass_solar": 0.909, "mass_uncertainty_solar": 0.0025,
            "mass_kind": "dynamical", "citation": "Akeson et al. 2021",
            "mass_basis": "dynamical", "mass_interval": {"lo": 0.9065, "hi": 0.9115, "kind": "sigma_1"},
            "source": "Akeson et al. 2021, AJ 162:14 (arXiv:2104.10086) Table 8 'Present work' m_B=0.9092",
        },
    ],
}


def is_positive_finite(x):
    """CR-22.6: the one "usable mass" predicate — a real number (not a bool), > 0 and finite. NaN fails ``> 0``;
    ±inf fails ``isfinite``. Shared by ``match_mass``, ``stellar_mass.resolve_mass`` / ``resolve_component_mass``,
    ``exclusion_system.compose_exclusion_system`` and the dossier mass block so the rule cannot drift per copy."""
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0 and math.isfinite(x)


def _norm(s):
    """Whitespace-collapsed, upper-cased identifier for matching (``"HD  48915"`` → ``"HD 48915"``)."""
    if not s:
        return ""
    return " ".join(str(s).split()).upper()


def load_mass_catalog(path=None):
    """Return the catalog dict ``{"stars": [...]}`` or ``{"error": str}``.

    ``path is None`` → the internal seed. Otherwise read the external JSON, which **replaces** the
    seed wholesale. A missing / unreadable / invalid-JSON / no-``stars``-array file → curated
    ``{"error": …}`` (loud, never a silent fallback — mirrors CR-10.3).
    """
    if path is None:
        return _SEED_CATALOG
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {"error": f"stellar-mass catalog not found: {path}"}
    except (OSError, ValueError) as e:   # ValueError covers json.JSONDecodeError
        return {"error": f"could not read stellar-mass catalog '{path}': {e}"}
    if not isinstance(data, dict) or not isinstance(data.get("stars"), list):
        return {"error": f"stellar-mass catalog '{path}' has no 'stars' array."}
    err = validate_cr30_fields(data)
    if err:
        return {"error": f"stellar-mass catalog '{path}': {err}"}
    return data


# CR-30.6 C: the contract's enums — one source (core.placement), sorted for the error text (CP4 #7)
from core import placement as _placement   # noqa: E402 (pure; imports only the vendored-table loader)
_MASS_BASES = tuple(sorted(_placement.CATALOG_BASES))
_INTERVAL_KINDS = tuple(sorted(_placement.INTERVAL_KINDS))
_AGE_BASES = tuple(sorted(_placement.AGE_BASES))
_AGE_GRADES = tuple(sorted(_placement.AGE_GRADES))


def validate_cr30_fields(catalog):
    """CR-30.6 C (Q24): the new structured fields, checked when present — an unknown ``mass_basis`` / interval
    ``kind`` / age ``basis`` / ``grade``, ``lo > hi``, X outside ``[lo, hi]`` or ``lo_gyr > hi_gyr`` → the error text
    naming the row and field (a loud load error — WB owns the catalog; REPLACE semantics would place every row on
    a silent misread). A row without the fields is valid (read as relation / ± σ / no age). ``None`` when clean."""
    for i, row in enumerate(catalog.get("stars") or []):
        if not isinstance(row, dict):
            continue
        rid = row.get("main_id") or row.get("id") or f"row {i + 1}"
        sig = row.get("mass_uncertainty_solar")
        if sig is not None and not (isinstance(sig, (int, float)) and not isinstance(sig, bool)
                                    and math.isfinite(sig) and sig >= 0):
            return f"{rid}: mass_uncertainty_solar must be a finite number >= 0 (got {sig!r})"
        b = row.get("mass_basis")
        if b is not None and b not in _MASS_BASES:
            return f"{rid}: mass_basis {b!r} is not one of {', '.join(_MASS_BASES)}"
        iv = row.get("mass_interval")
        if iv is not None:
            if not isinstance(iv, dict) or iv.get("kind") not in _INTERVAL_KINDS:
                return f"{rid}: mass_interval.kind must be one of {', '.join(_INTERVAL_KINDS)}"
            lo, hi, x = iv.get("lo"), iv.get("hi"), row.get("mass_solar")
            if not (is_positive_finite(lo) and is_positive_finite(hi)) or lo > hi:
                return f"{rid}: mass_interval needs finite 0 < lo <= hi (got {lo!r}, {hi!r})"
            if is_positive_finite(x) and not (lo - 1e-12 <= x <= hi + 1e-12):
                return f"{rid}: mass_solar {x} lies outside mass_interval [{lo}, {hi}]"
        ag = row.get("age_interval")
        if ag is not None:
            if not isinstance(ag, dict):
                return f"{rid}: age_interval must be an object"
            lo_g, hi_g = ag.get("lo_gyr"), ag.get("hi_gyr")
            for nm, v in (("lo_gyr", lo_g), ("hi_gyr", hi_g)):
                if v is not None and not (isinstance(v, (int, float)) and not isinstance(v, bool)
                                          and math.isfinite(v) and v >= 0):
                    return f"{rid}: age_interval.{nm} must be a finite number >= 0 or null"
            if lo_g is not None and hi_g is not None and lo_g > hi_g:
                return f"{rid}: age_interval lo_gyr {lo_g} > hi_gyr {hi_g}"
            if ag.get("basis") not in _AGE_BASES:
                return f"{rid}: age_interval.basis must be one of {', '.join(_AGE_BASES)}"
            if ag.get("grade") not in _AGE_GRADES:
                return f"{rid}: age_interval.grade must be one of {', '.join(_AGE_GRADES)}"
    return None


def match_mass(catalog, main_id, designations=None):
    """First catalog row matching the resolved star, else ``None``.

    Matches a row's ``main_id`` / any ``aliases`` entry against the star's ``main_id`` / any
    ``designations`` value (normalized). A malformed row (no ``main_id``, or a non-numeric,
    non-positive or non-finite ``mass_solar``) is skipped best-effort — the primary computation is never
    touched, and resolution falls through to the next tier.
    """
    ids = set()
    if main_id:
        ids.add(_norm(main_id))
    if designations:
        for v in designations.values():
            if v:
                ids.add(_norm(v))
    if not ids:
        return None
    for row in catalog.get("stars", []):
        if not isinstance(row, dict):
            continue
        val = row.get("mass_solar")
        if not is_positive_finite(val):
            # malformed / missing measurement — skip best-effort. CR-22.6: json.load accepts the NaN /
            # Infinity tokens, so a non-finite mass is skipped like a ≤ 0 one (falls through to the next tier).
            continue
        keys = set()
        if row.get("main_id"):
            keys.add(_norm(row["main_id"]))
        for a in row.get("aliases") or []:
            if a:
                keys.add(_norm(a))
        if keys & ids:
            return row
    return None
