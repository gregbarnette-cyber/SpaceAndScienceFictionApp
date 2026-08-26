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

# Internal seed (flag-less default). The four CR-11.2 anchors, verified-at-primary 2026-08-26,
# mirroring the WB JSON shape. Sirius A / Vega are precisely the bright stars Gaia FLAME saturates
# on, so the catalog — not FLAME — is their authoritative measured-mass source.
_SEED_CATALOG = {
    "schema_version": "1.0.0",
    "source": ("internal seed (CR-11.2) — the four verified anchors; pass --star-mass-catalog "
               "for the WB-owned file (rows-are-data, REPLACE semantics)"),
    "stars": [
        {
            "id": "Sirius A", "main_id": "* alf CMa",
            "aliases": ["HD 48915A", "HD 48915", "HIP 32349", "GJ 244 A", "HR 2491"],
            "sp_type": "A0mA1Va", "mass_solar": 2.063, "mass_uncertainty_solar": 0.023,
            "mass_kind": "dynamical", "citation": "Bond et al. 2017",
            "source": "Bond et al. 2017, ApJ 840:70 (arXiv:1703.10625) — visual+astrometric dynamical orbit",
        },
        {
            "id": "Vega", "main_id": "* alf Lyr",
            "aliases": ["HD 172167", "HIP 91262", "HR 7001", "GJ 721"],
            "sp_type": "A0Va", "mass_solar": 2.135, "mass_uncertainty_solar": 0.074,
            "mass_kind": "gravity-darkened Roche model", "citation": "Yoon et al. 2010",
            "source": "Yoon, Peterson & Kurucz 2010, ApJ 708:71 — NPOI Roche-model fit",
        },
        {
            "id": "alpha Centauri A", "main_id": "* alf Cen A",
            "aliases": ["HD 128620", "HIP 71683", "GJ 559 A", "HR 5459"],
            "sp_type": "G2V", "mass_solar": 1.079, "mass_uncertainty_solar": 0.0029,
            "mass_kind": "dynamical", "citation": "Akeson et al. 2021",
            "source": "Akeson et al. 2021, AJ 162:14 (arXiv:2104.10086) Table 8 'Present work' m_A=1.0788",
        },
        {
            "id": "alpha Centauri B", "main_id": "* alf Cen B",
            "aliases": ["HD 128621", "HIP 71681", "GJ 559 B", "HR 5460"],
            "sp_type": "K1V", "mass_solar": 0.909, "mass_uncertainty_solar": 0.0025,
            "mass_kind": "dynamical", "citation": "Akeson et al. 2021",
            "source": "Akeson et al. 2021, AJ 162:14 (arXiv:2104.10086) Table 8 'Present work' m_B=0.9092",
        },
    ],
}


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
    return data


def match_mass(catalog, main_id, designations=None):
    """First catalog row matching the resolved star, else ``None``.

    Matches a row's ``main_id`` / any ``aliases`` entry against the star's ``main_id`` / any
    ``designations`` value (normalized). A malformed row (no ``main_id``, or a non-numeric
    ``mass_solar``) is skipped best-effort — the primary computation is never touched.
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
        if isinstance(val, bool) or not isinstance(val, (int, float)) or val <= 0:
            continue  # malformed / missing measurement — skip best-effort
        keys = set()
        if row.get("main_id"):
            keys.add(_norm(row["main_id"]))
        for a in row.get("aliases") or []:
            if a:
                keys.add(_norm(a))
        if keys & ids:
            return row
    return None
