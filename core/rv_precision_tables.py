"""core/rv_precision_tables.py — CR-10.3 tier-2 per-star RV-precision floor catalog.

A **static per-star lookup** consumed by ``core.detection.compute_detection_completeness`` as its
**tier-2** RV-floor source (precedence: manual ``--rv-precision-ms`` → **this catalog** → generic 3a
default). The tool READS rows; it never computes a fit (evolved-star rows are pre-computed offline by
WB from the Yu 2018 oscillation-jitter fit and stored as plain numbers).

Two catalogs:
  * the **internal seed** below (flag-less default) — anchor-only: **HD 69830 = 0.81 m/s [Lovis 2006]**;
  * an **external WB-owned file** passed via ``--rv-precision-catalog <path>``, which **REPLACES** the
    seed wholesale (WB MSG 097 Q2 — no merge; WB extends/edits that file with no APP round). The
    authoritative file is
    ``scifiWorldBuilding-Claude/design-lab/star-system-analysis/deliverables/rv-precision-catalog.json``.

Match key: the resolved star's ``main_id`` + every ``designations`` value vs a row's ``main_id`` +
``aliases``, whitespace-collapsed + case-insensitive (handles SIMBAD's ``"HD  69830"`` double space).
A bad/unreadable/invalid external path → ``{"error": …}`` (loud, never a silent seed fallback); a
malformed single row inside a valid file is skipped best-effort.
"""

import json

# floor_kind → human phrase for the ``floor_source`` string (fallback: the raw key).
_FLOOR_KIND_PHRASE = {
    "measured_residual_rms": "residual RMS",
    "yu2018_fit": "oscillation-jitter (Yu 2018 fit)",
}

# Internal seed (flag-less default). Anchor-only per the ratified contract; mirrors the WB JSON shape.
_SEED_CATALOG = {
    "schema_version": "1.0.0",
    "source": "internal seed (CR-10.3) — anchor-only; pass --rv-precision-catalog for the WB-owned file",
    "stars": [
        {
            "id": "HD 69830",
            "main_id": "HD  69830",
            "aliases": ["GJ 302", "HIP 40693", "HR 3259", "TIC 307624961",
                        "Gaia DR3 5726982995343100928"],
            "sp_type": "G8:V",
            "rv_precision_ms": 0.81,
            "floor_kind": "measured_residual_rms",
            "citation": "Lovis 2006",
            "source": ("Lovis et al. 2006, Nature 441:305 (arXiv:astro-ph/0703024) — weighted RMS of "
                       "residuals around the best-fit model = 0.81 m/s"),
            "confidence": "known-science",
        },
    ],
}


def _norm(s):
    """Whitespace-collapsed, upper-cased identifier for matching (``"HD  69830"`` → ``"HD 69830"``)."""
    if not s:
        return ""
    return " ".join(str(s).split()).upper()


def load_rv_precision_catalog(path=None):
    """Return the catalog dict ``{"stars": [...]}`` or ``{"error": str}``.

    ``path is None`` → the internal seed. Otherwise read the external JSON, which **replaces** the
    seed wholesale. A missing / unreadable / invalid-JSON / no-``stars``-array file → curated
    ``{"error": …}`` (WB MSG 097 Q2 — never a silent fallback to the seed).
    """
    if path is None:
        return _SEED_CATALOG
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {"error": f"RV-precision catalog not found: {path}"}
    except (OSError, ValueError) as e:  # ValueError covers json.JSONDecodeError
        return {"error": f"could not read RV-precision catalog '{path}': {e}"}
    if not isinstance(data, dict) or not isinstance(data.get("stars"), list):
        return {"error": f"RV-precision catalog '{path}' has no 'stars' array."}
    return data


def match_rv_precision(catalog, main_id, designations=None):
    """First catalog row matching the resolved star, else ``None``.

    Matches a row's ``main_id`` / any ``aliases`` entry against the star's ``main_id`` / any
    ``designations`` value (normalized). A malformed row (no ``main_id``, or a non-numeric
    ``rv_precision_ms``) is skipped best-effort — the primary computation is never touched.
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
        val = row.get("rv_precision_ms")
        if isinstance(val, bool) or not isinstance(val, (int, float)):
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


def catalog_floor_source(row):
    """The ``floor_source`` string for a catalog hit, e.g.
    ``"per-star catalog: HD 69830 residual RMS 0.81 m/s [Lovis 2006]"``.
    """
    name = row.get("id") or row.get("main_id") or "?"
    kind = _FLOOR_KIND_PHRASE.get(row.get("floor_kind"), row.get("floor_kind") or "value")
    val = row.get("rv_precision_ms")
    cite = row.get("citation")
    s = f"per-star catalog: {name} {kind} {val} m/s"
    if cite:
        s += f" [{cite}]"
    return s
