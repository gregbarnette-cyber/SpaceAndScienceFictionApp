"""CR-30.3 / 30.4 — the star's 2MASS J / Ks for the M-dwarf colour route and the M_Ks mass route.

**The identifier** comes from SIMBAD (the same ``query_objectids`` call ``compute_simbad_lookup`` already makes):
an identifier listed under the acronym ``2MASS`` (``2MASS J…``) — never ``2MASSI`` / ``2MASSW`` (pre-fire ruling
21 D7). ``compute_simbad_lookup``'s output dict is **unchanged**: the raw ``2MASS J…`` strings travel out-of-band
through ``databases.simbad_twomass_ids(main_id)`` (a process memo keyed by SIMBAD main_id). Exactly one identifier
→ the J / Ks lookup; none → no route (the subtype / L route, disclosed); more than one → no route, disclosed as
``twomass_ids_multiple`` (pre-fire ruling 14 — a disclosure, never a degrade).

**The photometry** is VizieR **II/246** (the 2MASS All-Sky PSC) by designation — ``Jmag`` / ``e_Jmag`` / ``Kmag``
/ ``e_Kmag`` / ``Qflg`` (``ph_qual``) / ``Rflg`` (``rd_flg``) (Q6). Fetched once per designation per process and
shared by both routes.

**Fails loud** (CR-30.3; F4): a SIMBAD-listed identifier whose II/246 lookup is empty (``empty``) or errors after
retries (``unreachable``), or an empty identifier query for a K / M star SIMBAD resolved (``ids_failed``) →
``twomass_status`` + ``not_authoritative`` on the output, **never** a silent switch to the subtype or L route.
``SPACE_APP_2MASS_FORCE_UNREACHABLE=1`` forces ``unreachable`` at the seam (F3) — no network.

Every network call goes through the module-level seam ``_ii246_seam`` so ``tests/conftest.py`` can stub it.
"""

import os
import threading
import time

FORCE_ENV = "SPACE_APP_2MASS_FORCE_UNREACHABLE"
DEGRADE_STATUSES = ("unreachable", "empty", "ids_failed")

NOTE_NO_ID = "no 2MASS identifier in SIMBAD — the 2MASS routes (colour / M_Ks) are not taken"
NOTE_MULTIPLE = ("SIMBAD lists more than one 2MASS identifier — the 2MASS routes (colour / M_Ks) are not taken "
                 "(pre-fire ruling 14)")
NOTE_DEGRADE = {
    "unreachable": "the 2MASS J/Ks lookup (VizieR II/246) failed after retries — not authoritative; the "
                   "subtype / L route is NOT substituted (CR-30.3)",
    "empty": "SIMBAD lists a 2MASS identifier but VizieR II/246 returned no row — not authoritative; the "
             "subtype / L route is NOT substituted (CR-30.3)",
    "ids_failed": "SIMBAD's identifier query returned nothing for a star it resolved — not authoritative; never "
                  "read as 'no 2MASS identifier' (CR-30.3, pre-fire ruling 26)",
}

# Sentinel: the identifier memo holds nothing for this star (the lookup was stubbed / never ran) — no route,
# no marker. Distinct from an EMPTY identifier query (``ids_failed``).
NOT_LOOKED_UP = "not_looked_up"

_JKS_MEMO = {}
_LOCK = threading.Lock()
# A failed lookup is memoised too (both routes share one attempt per call — CP1), but only for a short while so a
# long-lived GUI process retries a transient VizieR failure later.
_FAIL_TTL_S = 300.0


def twomass_ids_from_rows(ids):
    """The identifiers under the acronym ``2MASS`` (``2MASS J…``) among SIMBAD's raw id strings."""
    out = []
    for s in ids or ():
        t = " ".join(str(s).split())
        if t.startswith("2MASS J"):
            out.append(t)
    return out


def _ii246_seam(designation):
    """VizieR II/246 by 2MASS designation (``J…`` → the catalogue's ``2MASS`` column) → the raw rows or a
    ``{"error"}`` dict (``core.catalog.vizier_query``'s shape)."""
    from core import catalog
    key = designation.split("J", 1)[1] if "J" in designation else designation
    return catalog.vizier_query("II/246/out", columns=["2MASS", "Jmag", "e_Jmag", "Kmag", "e_Kmag", "Qflg", "Rflg"],
                                filters=[f"2MASS={key}"], row_limit=5)


def _num(v):
    """A 2MASS magnitude / error at the catalogue's published precision (3 decimals — VizieR serves them as
    float32, e.g. 5.35699987 for 2MASS's 5.357)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f, 3) if f == f else None


def fetch_jks(designation):
    """``{"status": "ok" | "unreachable" | "empty", "designation", "j", "e_j", "ks", "e_ks", "ph_qual",
    "rd_flg", "quality_below_a"}`` — memoised per designation (both routes share one fetch)."""
    if os.environ.get(FORCE_ENV):                    # the hook wins over the memo and is never memoised (CP2)
        return {"status": "unreachable", "designation": designation}
    with _LOCK:
        hit = _JKS_MEMO.get(designation)
    if hit is not None and (hit[0] is None or time.monotonic() - hit[0] < _FAIL_TTL_S):
        return dict(hit[1])
    try:
        raw = _ii246_seam(designation)
    except Exception:
        raw = {"error": "exception"}
    if not isinstance(raw, dict) or "error" in raw:
        res = {"status": "unreachable", "designation": designation}
    elif not raw.get("rows"):
        res = {"status": "empty", "designation": designation}
    else:
        r = raw["rows"][0]
        qf = str(r.get("Qflg") or "")
        rf = str(r.get("Rflg") or "")
        j, ks = _num(r.get("Jmag")), _num(r.get("Kmag"))
        if j is None or ks is None:
            res = {"status": "empty", "designation": designation}
        else:
            below = [b for b, q in zip(("J", "H", "Ks"), qf) if q != "A"] if len(qf) == 3 else []
            res = {"status": "ok", "designation": designation, "j": j, "e_j": _num(r.get("e_Jmag")),
                   "ks": ks, "e_ks": _num(r.get("e_Kmag")), "ph_qual": qf or None, "rd_flg": rf or None,
                   "quality_below_a": [b for b in below if b in ("J", "Ks")]}
    with _LOCK:
        _JKS_MEMO[designation] = (None if res["status"] == "ok" else time.monotonic(), dict(res))
    return dict(res)


def resolve(simbad_result):
    """The star's 2MASS resolution for the colour / M_Ks routes →

    ``{"status": "not_looked_up" | "no_id" | "multiple" | "ok" | "unreachable" | "empty" | "ids_failed",
    "ids": [...], "jks": {...} | None}``.

    Only a type letter K or M (letter-only included) reaches the identifier rules; any other star → ``no_id``-
    equivalent ``not_applicable`` (no route, no marker). The identifier memo (``databases.simbad_twomass_ids``)
    distinguishes an empty identifier query (``ids_failed`` — fails loud) from a lookup that never ran
    (``not_looked_up`` — a stubbed test lookup; no route, no marker)."""
    from core import databases, shared
    p = shared.parse_spectral_type((simbad_result or {}).get("sp_type"))
    if p.letter not in ("K", "M"):
        return {"status": "not_applicable", "ids": [], "jks": None}
    ids = databases.simbad_twomass_ids((simbad_result or {}).get("main_id"))
    if ids == NOT_LOOKED_UP:
        return {"status": "not_looked_up", "ids": [], "jks": None}
    if ids == "ids_failed":
        return {"status": "ids_failed", "ids": [], "jks": None}
    if not ids:
        return {"status": "no_id", "ids": [], "jks": None}
    if len(ids) > 1:
        return {"status": "multiple", "ids": list(ids), "jks": None}
    jks = fetch_jks(ids[0])
    return {"status": jks["status"], "ids": list(ids), "jks": jks if jks["status"] == "ok" else None}


_MARKER_KEYS = ("not_authoritative", "twomass_status", "twomass_note")


def degrade_marker(res):
    """The marker triplet (``not_authoritative``, ``twomass_status``, ``twomass_note``) from a region-step result
    that failed on a 2MASS degrade, else ``{}`` — the one builder every carrier uses (CP2)."""
    if not (isinstance(res, dict) and res.get("twomass_status") in DEGRADE_STATUSES):
        return {}
    return {"not_authoritative": True, "twomass_status": res["twomass_status"],
            "twomass_note": res.get("twomass_note") or res.get("error")}


def degrade_fields(status):
    """The output's marker fields for a 2MASS degrade (present ONLY on a degrade — F4), else ``{}``."""
    if status in DEGRADE_STATUSES:
        return {"twomass_status": status, "not_authoritative": True}
    return {}


def clear_memo():
    with _LOCK:
        _JKS_MEMO.clear()
