# core/databases.py — Star database query functions (SIMBAD, NASA, HWC, Mission Exocat)
# Phase C: compute_simbad_lookup() added.
# Phase D: remaining query functions added.

import csv
import math
import os
import re
import threading

from .shared import (_make_simbad, _network_error_msg, _timeout_ctx, _with_retries,
                     _escape_like, spectral_where, spectral_adql, LY_PER_PC,
                     _SP_CLASS_PREFIXES,
                     _fval, _fmt,  # _fval/_fmt: one canonical copy (P4.6)
                     _parse_designations_from_ids as _parse_designations_from_ids_shared,
                     _CSV_DESIG_KEYS as _CSV_DESIG_KEYS_SHARED,
                     # AN0: the canonical designation matcher/joiner (was re-typed
                     # inline inside compute_simbad_lookup).
                     _match_designations, _join_designations,
                     _designation_ids_from_rows,
                     constellation_genitive)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BASE_DIR, "..")

# Module-level caches (+ per-cache locks for the GUI worker threads that build them
# lazily; double-checked locking in the _load_* helpers — P6.4). _OEC_DATA backs the
# retained _load_oec scaffolding kept for the OEC rebuild (see below).
_HWC_DATA      = None
_OEC_DATA      = None
_MISSION_EXOCAT = None
_HWC_LOCK      = threading.Lock()
_MISSION_EXOCAT_LOCK = threading.Lock()
_OEC_LOCK      = threading.Lock()


# ── Shared numeric helpers ────────────────────────────────────────────────────

# _fval/_fmt are imported from core.shared (P4.6 — one canonical copy).


_CSV_HEADER_RE = re.compile(r"[A-Za-z0-9_ .\-/()%]+")


def _validate_csv_headers(headers):
    """Return None if every CSV header is a safe column identifier, else an ``{"error"}``
    dict (P6.3). Guards the CSV-header→DDL/DML interpolation in the HWC / Mission-Exocat
    importers (the real files use only ``[A-Za-z0-9_]``; the allowed set is a small
    superset that still excludes quotes and control chars, so no injection via a column
    name)."""
    for h in headers:
        if not h or not _CSV_HEADER_RE.fullmatch(h):
            return {"error": f"invalid column header: {h!r}"}
    return None


def _adql_quote(value) -> str:
    """Escape a value for safe inclusion inside a single-quoted ADQL string literal
    (P6.2): strip control characters, then double any single quotes. The caller keeps
    the surrounding quotes. For a normal designation (no quotes/control chars) the
    output is byte-identical to the raw value, so existing built queries are unchanged."""
    s = "" if value is None else str(value)
    s = "".join(ch for ch in s if ord(ch) >= 32)
    return s.replace("'", "''")


def compute_habitable_zone(st_teff, st_lum_log10=None, st_rad=None):
    """Compute Kopparapu et al. habitable zone boundaries.

    Returns list of (zone_name, au_value) tuples, or [] if insufficient data.
    Luminosity source: prefers (st_rad² × (teff/5778)⁴); falls back to 10**st_lum_log10.

    P4.6: thin adapter over ``equations.compute_habitable_zone`` — resolves the
    st_rad/st_lum_log10 luminosity here (databases-specific), then maps the dict
    zones → the (zone_name, au) tuple shape three GUI panels consume. The Kopparapu
    math now lives in exactly one place; zone names/order/values are unchanged.
    """
    teff = _fval(st_teff)
    if teff is None:
        return []

    lum = None
    if st_rad is not None:
        r = _fval(st_rad)
        if r is not None:
            lum = r ** 2 * (teff / 5778) ** 4
    if lum is None and st_lum_log10 is not None:
        lv = _fval(st_lum_log10)
        if lv is not None:
            lum = 10 ** lv
    if lum is None:
        return []

    from core.equations import compute_habitable_zone as _hz_dicts
    return [(z["zone_name"], z["au"]) for z in _hz_dicts(teff, lum)]


def _simbad_gcns_block(designations):
    """Optional GCNS cross-reference for a SIMBAD result (Phase M5).

    Parses the Gaia EDR3/DR3 source_id from *designations* and returns the matching
    gcns_stars row (Bayesian dist_pc + dist_lo_pc/dist_hi_pc, distance_method, Gaia
    G/BP/RP photometry, astrom_reliable_prob, wd_prob, system_id/n_components) — the
    same shape as gcns-source's "star". Returns None when there is no Gaia id, the id
    is absent from GCNS, the table is empty/missing, or any error occurs: non-fatal
    and silent, exactly like opt 1's optional HWO/Hypatia sub-sections.
    """
    try:
        gaia_raw = (designations or {}).get("Gaia EDR3")
        if not gaia_raw:
            return None
        m = _GCNS_GAIA_ID_RE.search(str(gaia_raw))
        if not m:
            return None
        r = compute_gcns_by_source_id(int(m.group(1)))
        if "error" in r:
            return None
        return r["star"]
    except Exception:
        return None


_GOULD_ID_RE = re.compile(r"(\d+)")
_GOULD_SOURCE = "VizieR V/135A (Gould 1879)"


def _gould_catalog_number(designations, key):
    """Integer catalogue number out of a designation string ('HD 102365' → 102365)."""
    raw = (designations or {}).get(key)
    if not raw:
        return None
    m = _GOULD_ID_RE.search(str(raw))
    return int(m.group(1)) if m else None


def _gould_format(g_number, cst):
    """(66, 'Cen') → ('66 G. Cen', '66 G. Centauri').

    AO3b: built from g_number + cst rather than reusing the catalogue's own
    `Name` column ('66G Cen'), so the spacing/punctuation is ours and identical
    everywhere. `display` falls back to the raw abbreviation when the
    constellation is unknown — never invents a name.
    """
    designation = f"{g_number} G. {cst}" if cst else f"{g_number} G."
    genitive = constellation_genitive(cst)
    display = f"{g_number} G. {genitive}" if genitive else designation
    return designation, display


def _simbad_gould_block(designations):
    """Optional Gould designation for a SIMBAD result (Phase AO2).

    SIMBAD carries NO Gould identifiers (verified against the live `ident`
    table — PHASE_AO_PLAN.md §0), so this reads the bundled Uranometria
    Argentina catalogue instead, joining on HD (primary) then SAO (fallback).

    Returns None when the star has no HD number, is absent from the catalogue,
    or the table is empty/missing, and on any error: non-fatal and silent,
    exactly like _simbad_gcns_block above. Coverage is intentionally partial —
    Gould listed bright *southern* stars only, so None is the normal answer for
    most stars and does not indicate a failure (AO4a).

    **Joins on HD only.** The plan specified an SAO fallback, and it was built —
    but `designations` can never carry an "SAO" key: the shared
    `_CSV_PREFIX_MAP` captures no SAO ids, so
    the branch was unreachable in production and its test passed only against a
    hand-built dict shape the pipeline never produces (code review, 2026-07-29).
    It is removed rather than left as dead code. Making it reachable means adding
    SAO to the designation key set, which also injects "SAO nnnnn" into
    `desig_str` on all four GUI banners and into the query.py contract — a
    product decision belonging to Phase AN's AN2 "key insertion + ripple", which
    is already going to touch this exact map. Payoff if AN takes it up: 26
    catalogue rows carry an SAO number but no HD, of which only **3** have a
    Gould number. The `sao` column is retained in the schema and echoed below.
    """
    try:
        from core.db import get_conn, table_exists
        # AO2 [R4]: an existence check, NOT the GCNS block's SELECT COUNT(*)
        # seeded-guard — that is an O(n) scan used only to test emptiness, and
        # this covers the missing-table case more directly. An empty table
        # simply matches nothing below.
        if not table_exists("gould_designations"):
            return None
        number = _gould_catalog_number(designations, "HD")
        if number is None:
            return None
        # AO2a: 11 HD values sit on two rows (multi-component systems); lowest
        # Gould number wins, resolved in SQL so the tie-break is deterministic.
        # The IS NOT NULL filter is load-bearing: SQLite sorts NULL FIRST, so
        # without it an un-numbered row sharing the HD would win (AO2a [B3]).
        row = get_conn().execute(
            """SELECT g_number, cst, hd, sao FROM gould_designations
               WHERE hd = ? AND g_number IS NOT NULL
               ORDER BY g_number LIMIT 1""",
            (number,),
        ).fetchone()
        if row is None:
            return None
        designation, display = _gould_format(row["g_number"], row["cst"])
        return {
            "g_number":      row["g_number"],
            "cst":           row["cst"],
            "constellation": constellation_genitive(row["cst"]),
            "designation":   designation,
            "display":       display,
            "hd":            row["hd"],
            "sao":           row["sao"],
            "matched_on":    "hd",
            "source":        _GOULD_SOURCE,
        }
    except Exception:
        return None


def compute_simbad_lookup(star_name: str) -> dict:
    """Query SIMBAD for a star by name or designation.

    Returns a dict with keys:
        main_id      — str: SIMBAD primary identifier
        ra           — float | None: right ascension in decimal degrees
        dec          — float | None: declination in decimal degrees
        sp_type      — str | None: spectral type string
        plx_value    — float | None: parallax in mas (> 0 if present)
        teff         — float | None: effective temperature in K
        vmag         — float | None: apparent V magnitude
        ly           — float | None: distance in light years (4 dp)
        parsecs      — float | None: distance in parsecs (4 dp)
        designations — dict: {key: id_str | None} for MAIN_ID, NAME, GJ, HD, HIP, …
        desig_str    — str: comma-separated designation list for display

    Returns {"error": str} on any failure (no match, network error, etc.).
    """
    from astroquery.simbad import Simbad

    try:
        with _timeout_ctx(30):
            # _make_simbad lazily hits SIMBAD's TAP capabilities endpoint (via
            # add_votable_fields), so it must be inside the try — otherwise a
            # capabilities/connection failure escapes as a raw DALServiceError
            # instead of the friendly _network_error_msg classification.
            custom_simbad = _make_simbad("sp_type", "plx_value", "V", "mesfe_h", "otype")
            result     = _with_retries(custom_simbad.query_object, star_name)
            ids_result = _with_retries(Simbad.query_objectids, star_name)
    except Exception as e:
        return {"error": _network_error_msg(e, "SIMBAD")}

    if result is None or len(result) == 0:
        return {"error": f"No results found for '{star_name}'"}

    row = result[0]
    col_names = result.colnames

    def _safe(col):
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

    # .strip() is load-bearing for AN2's D3 dedupe, not cosmetic: _match_designations
    # strips every id it stores, so an unstripped main_id would compare unequal to its
    # own keyed copy and _join_designations would re-emit the duplicate token D3 exists
    # to remove. Reachable two ways — a padded/fixed-width SIMBAD main_id, or the AN0d
    # fallback to a user query string with stray whitespace — and the offline corpus
    # cannot catch either, because the capture script applies _safe() normalisation.
    # Raised by /code-review 2026-07-29.
    main_id = str(_safe("main_id") or star_name).strip()

    ra_raw = _safe("ra")
    dec_raw = _safe("dec")
    ra = float(ra_raw) if ra_raw is not None else None
    dec = float(dec_raw) if dec_raw is not None else None

    sp_raw = _safe("sp_type")
    sp_type = str(sp_raw).strip() if sp_raw is not None else None

    plx_raw = _safe("plx_value")
    plx = None
    ly = None
    parsecs = None
    if plx_raw is not None:
        try:
            plx_f = float(plx_raw)
            if plx_f > 0:
                plx = plx_f
                parsecs = round(1000.0 / plx_f, 4)
                ly = round(parsecs * 3.26156, 4)
        except (ValueError, ZeroDivisionError):
            pass

    teff_raw = _safe("mesfe_h.teff")
    teff = None
    if teff_raw is not None:
        try:
            teff = float(teff_raw)
        except (ValueError, TypeError):
            pass

    vmag_raw = _safe("V")
    vmag = None
    if vmag_raw is not None:
        try:
            vmag = float(vmag_raw)
        except (ValueError, TypeError):
            pass

    # Metallicity [Fe/H] from the mesfe_h table (already fetched for teff). Additive
    # key — None when SIMBAD has no value. Consumed by the R3-V2 real-anchor
    # metallicity-conditioned generation path (occurrence_by_metallicity).
    feh_raw = _safe("mesfe_h.fe_h")
    fe_h = None
    if feh_raw is not None:
        try:
            fe_h = float(feh_raw)
        except (ValueError, TypeError):
            pass

    # ── Designation parsing ───────────────────────────────────────────────────
    # Phase AN0: this was an inline re-typing of core.shared's prefix map + match
    # loop (the P4.6 consolidation reached the opt-50 builder below but never got
    # here). It now delegates, so a new prefix entry — Phase AN1's `* ` Bayer /
    # Flamsteed classifier — lands on this path automatically.
    #
    # Two properties are load-bearing and must not be "simplified":
    #   AN0c — MAIN_ID leads the join key list. Passing _CSV_DESIG_KEYS alone would
    #          strip the main id from all four GUI designation banners.
    #   AN0d — MAIN_ID falls back to the query string when SIMBAD masks the column,
    #          where shared._parse_designations leaves it None. Deliberate, and
    #          wire-visible through query.py.
    keys_order = ["MAIN_ID"] + list(_CSV_DESIG_KEYS_SHARED)
    designations = {k: None for k in keys_order}
    designations["MAIN_ID"] = main_id
    designations.update(
        _match_designations(_designation_ids_from_rows(ids_result), _CSV_DESIG_KEYS_SHARED)
    )

    # AN2e / D5: the empty case is "" — this was the last of the five §6 drifts, and the
    # only one judged a bug rather than a deliberate difference. Three of the five copies
    # (shared, calculators, the opt-50 builder) already returned ""; this one alone
    # substituted the literal string "N/A", which no consumer wants — it would reach a DB
    # column, the query.py contract, and four GUI banners as data.
    #
    # It fires on 0 of the 43 corpus stars and is effectively unreachable: MAIN_ID leads
    # this join and falls back to `star_name`, so an empty result needs a caller passing
    # a blank name that SIMBAD nevertheless resolved. Latent, not active — which is why
    # this is a safe change, not a risky one.
    #
    # NOTE the plan's stated reason for the fix is WRONG and is corrected there ([A6]):
    # D5 says the "only reachable path" is the opt-50 `desig_str == ""` discard rule.
    # That rule reads `_parse_designations_from_ids` in _run_simbad_csv_query (:1358),
    # never this value, so a literal "N/A" could not have defeated it — and AN2c's
    # "land D5 before re-measuring the PLX delta" ordering caveat is therefore moot.
    desig_str = _join_designations(designations, keys_order)

    result = {
        "main_id":      main_id,
        "ra":           ra,
        "dec":          dec,
        "sp_type":      sp_type,
        "plx_value":    plx,
        "teff":         teff,
        "vmag":         vmag,
        "fe_h":         fe_h,
        "ly":           ly,
        "parsecs":      parsecs,
        "designations": designations,
        "desig_str":    desig_str,
    }
    # Phase M5: optional GCNS cross-reference (Bayesian distance + uncertainty).
    # Non-fatal and silent — None when there is no Gaia id / the source is not in
    # GCNS / the table is empty/missing. Lives here so query.py's simbad-lookup
    # gains the "gcns" key for free (cmd_simbad_lookup serializes this dict verbatim).
    result["gcns"] = _simbad_gcns_block(designations)
    # Phase AO2: optional Gould designation (Uranometria Argentina 1879), kept as
    # its own top-level key rather than folded into `designations` — that dict
    # means "what SIMBAD returned", and SIMBAD has no Gould ids at all, so folding
    # a VizieR-sourced value in would make desig_str misattribute provenance and
    # put a non-SIMBAD string into star_systems.designations semantics (AO3a).
    # Same free ride for query.py's simbad-lookup as the "gcns" key.
    result["gould"] = _simbad_gould_block(designations)
    # CR-2: multiplicity flag surfaced in the standard lookup path. Cheap otype-derived hint
    # (no extra network) — the authoritative per-component summary is the `multiplicity`
    # subcommand (binary.multiplicity_summary, which composes this + binary-orbit + GCNS).
    _ot = _safe("otype")
    result["otype"] = str(_ot).strip() if _ot is not None else None
    result["multiplicity"] = _simbad_multiplicity_block(result["otype"])
    return result


# SIMBAD otype codes that imply multiplicity, mapped to a coarse basis hint. `**` is the generic
# double/multiple; the SB*/eclipsing families carry a spectroscopic / eclipsing basis. This is a
# HINT (SIMBAD lists a star's most-specific type, so a wide-binary member may show `PM*` not `**`);
# the binary-orbit tool-split is the authoritative source (CR-2 Layer B).
_OTYPE_SPECTROSCOPIC = {"SB*", "SB?", "RS*", "El*"}
_OTYPE_ECLIPSING = {"EB*", "Al*", "bL*", "WU*", "EB?"}
_OTYPE_VISUAL_MULTIPLE = {"**", "**?"}


def _simbad_multiplicity_block(otype):
    """Coarse otype-derived multiplicity hint for the standard lookup path (CR-2 Layer A).

    Returns ``{is_multiple, sb_flag, basis, source:"simbad-otype", otype}`` — always present so the
    lookup surfaces a multiplicity status either way (unlike the gcns/gould blocks, which are None
    when absent). ``None`` only when SIMBAD returned no otype at all."""
    if not otype:
        return None
    ot = str(otype).strip()
    if ot in _OTYPE_SPECTROSCOPIC:
        return {"is_multiple": True, "sb_flag": True, "basis": "spectroscopic",
                "source": "simbad-otype", "otype": ot}
    if ot in _OTYPE_ECLIPSING:
        return {"is_multiple": True, "sb_flag": False, "basis": "eclipsing",
                "source": "simbad-otype", "otype": ot}
    if ot in _OTYPE_VISUAL_MULTIPLE:
        return {"is_multiple": True, "sb_flag": False, "basis": "visual/multiple",
                "source": "simbad-otype", "otype": ot}
    return {"is_multiple": False, "sb_flag": False, "basis": None,
            "source": "simbad-otype", "otype": ot}


# ── NASA Exoplanet Archive helpers ────────────────────────────────────────────

def _get_archive_query_params(designations):
    """Return (field, value) for pscomppars. Priority: HIP > HD > TIC > Gaia EDR3."""
    if designations.get("HIP"):
        return "hip_name", designations["HIP"]
    if designations.get("HD"):
        return "hd_name", designations["HD"]
    if designations.get("TIC"):
        return "tic_id", designations["TIC"]
    if designations.get("Gaia EDR3"):
        return "gaia_id", designations["Gaia EDR3"]
    return None, None


def _get_hwo_query_params(designations):
    """Return (field, value) for di_stars_exep. Priority: HIP > HD > TIC > HR > GJ."""
    if designations.get("HIP"):
        return "hip_name", designations["HIP"]
    if designations.get("HD"):
        return "hd_name", designations["HD"]
    if designations.get("TIC"):
        return "tic_id", designations["TIC"]
    if designations.get("HR"):
        return "hr_name", designations["HR"]
    if designations.get("GJ"):
        return "gj_name", designations["GJ"]
    return None, None


def _query_tap(table, where, order_by=None, timeout=60, top=None, select="*"):
    """Query NASA Exoplanet Archive TAP endpoint; return list of row dicts.

    top: optional ADQL row cap (SELECT TOP N). select: column list (default '*').
    Defaults preserve the original `SELECT * FROM table WHERE where` behaviour.
    """
    import requests
    top_clause = f"TOP {int(top)} " if top else ""
    q = f"SELECT {top_clause}{select} FROM {table} WHERE {where}"
    if order_by:
        q += f" ORDER BY {order_by}"

    def _do_get():
        resp = requests.get(
            "https://exoplanetarchive.ipac.caltech.edu/TAP/sync",
            params={"query": q, "format": "json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()

    return _with_retries(_do_get)


# ── Option 2: NASA Exoplanet Archive All Tables ───────────────────────────────

def compute_exoplanet_archive(simbad_result: dict,
                               progress_callback=None) -> dict:
    """Query NASA pscomppars + HWO ExEP + Mission Exocat.

    Returns {simbad, planets, hwo, exocat} or {"error": str}.
    """
    if "error" in simbad_result:
        return simbad_result

    designations = simbad_result["designations"]

    field, value = _get_archive_query_params(designations)
    if not field:
        return {"error": "No usable designation (HIP, HD, TIC, Gaia) found for NASA Exoplanet Archive."}

    if progress_callback:
        progress_callback(f"Querying NASA Exoplanet Archive ({value})…")
    try:
        planets = _query_tap("pscomppars", f"{field}='{_adql_quote(value)}'", "pl_orbsmax")
    except Exception as e:
        return {"error": _network_error_msg(e, "NASA Exoplanet Archive")}

    if not planets:
        return {"error": f"No exoplanet data found for '{value}' in NASA Exoplanet Archive."}

    # HWO ExEP (optional)
    hwo = None
    hwo_field, hwo_value = _get_hwo_query_params(designations)
    if hwo_field:
        if progress_callback:
            progress_callback(f"Querying HWO ExEP archive ({hwo_value})…")
        try:
            rows = _query_tap("di_stars_exep", f"{hwo_field}='{_adql_quote(hwo_value)}'", "sy_dist")
            if rows:
                hwo = rows
        except Exception:
            pass

    # Mission Exocat (optional)
    if progress_callback:
        progress_callback("Searching Mission Exocat…")
    exocat = _query_mission_exocat_by_designations(designations)

    return {
        "simbad": simbad_result,
        "planets": planets,
        "hwo":    hwo,
        "exocat": exocat,
    }


# ── Option 3: Planetary Systems Composite ────────────────────────────────────

def compute_planetary_systems_composite(simbad_result: dict,
                                         progress_callback=None) -> dict:
    """Query NASA pscomppars only.

    Returns {simbad, planets} or {"error": str}.
    """
    if "error" in simbad_result:
        return simbad_result

    designations = simbad_result["designations"]
    field, value = _get_archive_query_params(designations)
    if not field:
        return {"error": "No usable designation (HIP, HD, TIC, Gaia) found for NASA Exoplanet Archive."}

    if progress_callback:
        progress_callback(f"Querying NASA Exoplanet Archive ({value})…")
    try:
        planets = _query_tap("pscomppars", f"{field}='{_adql_quote(value)}'", "pl_orbsmax")
    except Exception as e:
        return {"error": _network_error_msg(e, "NASA Exoplanet Archive")}

    if not planets:
        return {"error": f"No exoplanet data found for '{value}'."}

    return {"simbad": simbad_result, "planets": planets}


# ── Option 4: HWO ExEP ───────────────────────────────────────────────────────

def compute_hwo_exep(simbad_result: dict,
                      progress_callback=None) -> dict:
    """Query HWO ExEP archive only.

    Returns {simbad, hwo} or {"error": str}.
    """
    if "error" in simbad_result:
        return simbad_result

    designations = simbad_result["designations"]
    field, value = _get_hwo_query_params(designations)
    if not field:
        return {"error": "No usable designation (HIP, HD, TIC, HR, GJ) found for HWO ExEP archive."}

    if progress_callback:
        progress_callback(f"Querying HWO ExEP archive ({value})…")
    try:
        rows = _query_tap("di_stars_exep", f"{field}='{_adql_quote(value)}'", "sy_dist")
    except Exception as e:
        return {"error": _network_error_msg(e, "HWO ExEP archive")}

    if not rows:
        return {"error": f"No HWO ExEP data found for '{value}'."}

    return {"simbad": simbad_result, "hwo": rows}


# ── Option 5: Mission Exocat ─────────────────────────────────────────────────
# (the module-level _MISSION_EXOCAT cache + its lock are declared at the top — P6.4
# removed a duplicate `_MISSION_EXOCAT = None` that shadowed the canonical one here.)


def _load_mission_exocat():
    """Load mission_exocat table; return (hip_idx, hd_idx, gj_idx) case-insensitive dicts."""
    global _MISSION_EXOCAT
    if _MISSION_EXOCAT is not None:
        return _MISSION_EXOCAT
    with _MISSION_EXOCAT_LOCK:
        if _MISSION_EXOCAT is not None:      # re-check under the lock
            return _MISSION_EXOCAT
        from core.db import get_conn, table_exists
        hip_idx, hd_idx, gj_idx = {}, {}, {}
        try:
            if table_exists("mission_exocat"):
                for row in get_conn().execute("SELECT * FROM mission_exocat").fetchall():
                    row = dict(row)
                    for idx, key in [(hip_idx, "hip_name"), (hd_idx, "hd_name"), (gj_idx, "gj_name")]:
                        v = (row.get(key) or "").strip().upper()
                        if v:
                            idx.setdefault(v, row)
        except Exception:
            pass
        _MISSION_EXOCAT = (hip_idx, hd_idx, gj_idx)
        return _MISSION_EXOCAT


def _query_mission_exocat_by_designations(designations):
    """Search Mission Exocat by HIP → HD → GJ; return row dict or None."""
    hip_idx, hd_idx, gj_idx = _load_mission_exocat()
    for desig_key, idx in [("HIP", hip_idx), ("HD", hd_idx), ("GJ", gj_idx)]:
        val = (designations.get(desig_key) or "").strip().upper()
        if val and val in idx:
            return idx[val]
    return None


def compute_mission_exocat(simbad_result: dict) -> dict:
    """Search missionExocat.csv for the star.

    Returns {simbad, exocat} or {"error": str}.
    """
    if "error" in simbad_result:
        return simbad_result
    row = _query_mission_exocat_by_designations(simbad_result["designations"])
    if row is None:
        return {"error": "Star not found in Mission Exocat."}
    return {"simbad": simbad_result, "exocat": row}


# ── Option 6: Habitable Worlds Catalog ───────────────────────────────────────

def _load_hwc():
    """Load hwc table; return (hip_idx, hd_idx, name_idx)."""
    global _HWC_DATA
    if _HWC_DATA is not None:
        return _HWC_DATA
    with _HWC_LOCK:
        if _HWC_DATA is not None:             # re-check under the lock
            return _HWC_DATA
        from core.db import get_conn, table_exists
        hip_idx, hd_idx, name_idx = {}, {}, {}
        try:
            if table_exists("hwc"):
                for row in get_conn().execute("SELECT * FROM hwc").fetchall():
                    row = dict(row)
                    for idx, col in [(hip_idx, "S_NAME_HIP"), (hd_idx, "S_NAME_HD"), (name_idx, "S_NAME")]:
                        k = (row.get(col) or "").strip().upper()
                        if k:
                            idx.setdefault(k, []).append(row)
        except Exception:
            pass
        _HWC_DATA = (hip_idx, hd_idx, name_idx)
        return _HWC_DATA


def compute_hwc(simbad_result: dict) -> dict:
    """Search hwc.csv (Habitable Worlds Catalog) for the star.

    Returns {simbad, star_row, planet_rows (sorted by semi-major axis)}
    or {"error": str}.
    """
    if "error" in simbad_result:
        return simbad_result

    designations = simbad_result["designations"]
    hip_idx, hd_idx, name_idx = _load_hwc()

    hip  = (designations.get("HIP")  or "").strip().upper()
    hd   = (designations.get("HD")   or "").strip().upper()
    raw  = (designations.get("NAME") or "").strip()
    name = (raw[5:].strip() if raw.upper().startswith("NAME ") else raw).upper()

    rows = None
    for k, idx in [(hip, hip_idx), (hd, hd_idx), (name, name_idx)]:
        if k:
            rows = idx.get(k)
            if rows:
                break

    if not rows:
        return {"error": "Star not found in Habitable Worlds Catalog."}

    try:
        rows = sorted(rows, key=lambda r: float(r.get("P_SEMI_MAJOR_AXIS") or "inf"))
    except Exception:
        pass

    return {"simbad": simbad_result, "star_row": rows[0], "planet_rows": rows}


# ── Open Exoplanet Catalogue (Phase OEC rebuild) ─────────────────────────────
# OEC is a recursive system → binary → star → planet → satellite tree (NOT a flat
# table like the other Star Databases options). See completed_plans/PHASE_OEC_PLAN.md. This layer:
#   _norm_oec_name  — normalized alias key
#   _load_oec       — disk-cached fetch + normalized name→system index
#   _oec_num/_oec_node — generic complete field capture (D7); every reader must use a
#                     first-or-list accessor since ANY field may repeat (e.g. <list> on
#                     a planet in a binary carries 2+ statuses — mockup lesson §F.1)
#   compute_oec / compute_oec_planet — resolution entry points

_OEC_URL = "https://github.com/OpenExoplanetCatalogue/oec_gzip/raw/master/systems.xml.gz"
_OEC_CACHE_DIR = os.path.join(_BASE_DIR, "..", "data", "oec")
_OEC_CACHE_FILE = os.path.join(_OEC_CACHE_DIR, "systems.xml.gz")
_OEC_CACHE_MAX_AGE_DAYS = 7          # tunable (D6)
_OEC_MIN_SYSTEMS = 1000              # gate: real catalogue ~4081; reject a short download
_OEC_CONTAINERS = frozenset(("system", "binary", "star", "planet", "satellite"))
_OEC_PLANET_LETTER_RE = re.compile(r"\s+[a-z]$")


def _norm_oec_name(name):
    """Normalized alias key: lowercase, strip V*/* prefixes and all whitespace/-/_/*."""
    if not name:
        return ""
    s = name.strip()
    for pre in ("V* ", "* ", "NAME "):
        if s.upper().startswith(pre.upper()):
            s = s[len(pre):]
            break
    return re.sub(r"[\s\-_*]", "", s.lower())


def _oec_name_variants(name):
    """A name plus a trailing-planet-letter-stripped variant (so 'HD 209458 b'
    also resolves to its system)."""
    name = (name or "").strip()
    out = [name]
    m = _OEC_PLANET_LETTER_RE.search(name)
    if m:
        out.append(name[:m.start()])
    return out


def _oec_parse_root(raw_bytes):
    import gzip, io
    import xml.etree.ElementTree as ET
    return ET.parse(gzip.GzipFile(fileobj=io.BytesIO(raw_bytes))).getroot()


def _oec_fetch_bytes():
    """Download systems.xml.gz (requests + shared retry/timeout)."""
    import requests
    def _get():
        with _timeout_ctx(60):
            r = requests.get(_OEC_URL, timeout=60)
            r.raise_for_status()
            return r.content
    return _with_retries(_get)


def _oec_get_root(force_refresh=False):
    """Return the parsed OEC root Element, using data/oec/systems.xml.gz with 7-day
    staleness. Validate-before-cache; fall back to a stale cache on network failure."""
    import time
    # 1. fresh cache
    if (not force_refresh and os.path.exists(_OEC_CACHE_FILE)
            and (time.time() - os.path.getmtime(_OEC_CACHE_FILE)) / 86400.0 < _OEC_CACHE_MAX_AGE_DAYS):
        try:
            with open(_OEC_CACHE_FILE, "rb") as f:
                return _oec_parse_root(f.read())
        except Exception:
            pass  # corrupt cache → fall through to re-download
    # 2. (re)download, validate, cache atomically
    try:
        raw = _oec_fetch_bytes()
        root = _oec_parse_root(raw)
        if len(root) < _OEC_MIN_SYSTEMS:
            raise ValueError(f"OEC download had only {len(root)} systems (< {_OEC_MIN_SYSTEMS}); not caching.")
        os.makedirs(_OEC_CACHE_DIR, exist_ok=True)
        tmp = _OEC_CACHE_FILE + ".tmp"
        with open(tmp, "wb") as f:
            f.write(raw)
        os.replace(tmp, _OEC_CACHE_FILE)
        return root
    except Exception:
        # 3. stale-cache fallback
        if os.path.exists(_OEC_CACHE_FILE):
            with open(_OEC_CACHE_FILE, "rb") as f:
                return _oec_parse_root(f.read())
        raise


def _load_oec(force_refresh=False):
    """Return (root, index) where index maps a normalized alias → system Element.
    Disk-cached + memoized (double-checked locking, P6.4)."""
    global _OEC_DATA
    if _OEC_DATA is not None and not force_refresh:
        return _OEC_DATA
    with _OEC_LOCK:
        if _OEC_DATA is not None and not force_refresh:
            return _OEC_DATA
        root = _oec_get_root(force_refresh)
        index = {}
        for system in root:
            for elem in system.iter("name"):
                if elem.text:
                    k = _norm_oec_name(elem.text)
                    if k and k not in index:       # first-wins
                        index[k] = system
        _OEC_DATA = (root, index)
        return _OEC_DATA


def _oec_num(elem):
    """A numeric/text OEC field → {value, errorminus, errorplus, upperlimit,
    lowerlimit, unit, type} (only present keys), or None if empty."""
    if elem is None:
        return None
    text = (elem.text or "").strip()
    if not text and not elem.attrib:
        return None
    d = {"value": text}
    for a in ("errorminus", "errorplus", "upperlimit", "lowerlimit", "unit", "type"):
        if a in elem.attrib:
            d[a] = elem.attrib[a]
    return d


def _oec_fields(elem):
    """Generic complete field capture (D7): every non-container child → a field;
    a repeated tag collapses to a list (separation AU+arcsec; <list> multi-status)."""
    fields = {}
    for ch in elem:
        if ch.tag in _OEC_CONTAINERS or ch.tag == "name":
            continue
        v = _oec_num(ch)
        if v is None:
            continue
        if ch.tag in fields:
            if not isinstance(fields[ch.tag], list):
                fields[ch.tag] = [fields[ch.tag]]
            fields[ch.tag].append(v)
        else:
            fields[ch.tag] = v
    return fields


def _oec_names(elem):
    return [e.text.strip() for e in elem.findall("name") if e.text and e.text.strip()]


def _oec_node(elem, shallow=False):
    """Recursively convert an OEC element into {tag, names[], fields{}, children[]}.
    shallow=True omits children (used for the oec-planet host chain)."""
    node = {"tag": elem.tag, "names": _oec_names(elem), "fields": _oec_fields(elem)}
    if not shallow:
        children = [_oec_node(c) for c in elem if c.tag in _OEC_CONTAINERS]
        if children:
            node["children"] = children
    return node


def _oec_candidates_from_simbad(simbad):
    """Ordered OEC lookup candidates from a SIMBAD-lookup result's designations."""
    desig = simbad.get("designations", {}) or {}
    out = []
    for key in ("HIP", "HD", "GJ", "HR", "NAME", "MAIN_ID"):
        v = desig.get(key)
        if v:
            out.append(str(v))
    mid = simbad.get("main_id")
    if mid:
        out.append(str(mid))
    return out


def _oec_resolve(index, names):
    """Return (system_elem, matched_name) for the first name (or letter-stripped
    variant) that hits the normalized index, else (None, None)."""
    for name in names:
        for variant in _oec_name_variants(name):
            k = _norm_oec_name(variant)
            if k and k in index:
                return index[k], name
    return None, None


def _oec_not_found(query):
    return {"error": f"'{query}' is not in the Open Exoplanet Catalogue "
                     f"(which lists only systems with planets or planet candidates)."}


def compute_oec(target, progress_callback=None, allow_simbad=True):
    """Resolve a name (str) or a compute_simbad_lookup result (dict) to its OEC system
    tree. Direct-alias-first, SIMBAD-fallback (D1).

    ``allow_simbad=False`` disables the on-miss SIMBAD lookup (the offline query.py path).

    Returns {"query", "matched_name", "system": <node>, ["simbad": ...]} or {"error": str}.
    """
    simbad = None
    if isinstance(target, dict):
        simbad = target
        if "error" in simbad:
            return simbad
        names = _oec_candidates_from_simbad(simbad)
        query = str(simbad.get("main_id") or (names[0] if names else "")).strip()
    else:
        query = str(target or "").strip()
        names = [query] if query else []
    if not names:
        return {"error": "No name provided for Open Exoplanet Catalogue lookup."}

    if progress_callback:
        progress_callback("Loading Open Exoplanet Catalogue (first use downloads ~1 MB)…")
    try:
        _, index = _load_oec()
    except Exception as e:
        return {"error": _network_error_msg(e, "Open Exoplanet Catalogue")}

    system_elem, matched = _oec_resolve(index, names)

    # SIMBAD fallback: only when the caller passed a raw string and it missed directly.
    if system_elem is None and simbad is None and allow_simbad:
        if progress_callback:
            progress_callback("Not found directly — trying SIMBAD to resolve designations…")
        sl = compute_simbad_lookup(query)
        if "error" not in sl:
            simbad = sl
            system_elem, matched = _oec_resolve(index, _oec_candidates_from_simbad(sl))

    if system_elem is None:
        return _oec_not_found(query)

    result = {"query": query, "matched_name": matched, "system": _oec_node(system_elem)}
    if simbad is not None:
        result["simbad"] = simbad
    return result


def compute_oec_planet(name):
    """Resolve a planet name to its planet node + host chain (system→…→immediate parent)
    and where it attaches. Returns {"query", "planet", "attached_to", "host_chain",
    "system_name"} or {"error": str}."""
    q = str(name or "").strip()
    if not q:
        return {"error": "No planet name provided."}
    try:
        _, index = _load_oec()
    except Exception as e:
        return {"error": _network_error_msg(e, "Open Exoplanet Catalogue")}
    system_elem, _ = _oec_resolve(index, [q])
    if system_elem is None:
        return _oec_not_found(q)

    want = {_norm_oec_name(v) for v in _oec_name_variants(q)}
    parent = {c: p for p in system_elem.iter() for c in p}
    planet_elem = None
    for pl in system_elem.iter("planet"):
        if want & {_norm_oec_name(e.text) for e in pl.findall("name") if e.text}:
            planet_elem = pl
            break
    if planet_elem is None:
        return {"error": f"'{q}' resolves to a system but not a specific planet — use oec-system."}

    par = parent.get(planet_elem)
    attached_to = par.tag if par is not None else "system"
    chain = []
    cur = par
    while cur is not None:
        chain.append(_oec_node(cur, shallow=True))
        cur = parent.get(cur)
    chain.reverse()   # system → … → immediate parent
    return {"query": q, "planet": _oec_node(planet_elem), "attached_to": attached_to,
            "host_chain": chain, "system_name": (system_elem.findtext("name") or "")}


# ── Phase 4: structural search + census over the whole catalogue (query.py) ──────
# Tier-2 `oec-search` / Tier-3 `oec-census` / `oec-status`. These read the parsed
# ElementTree directly (not the node dicts) so a catalogue-wide scan over ~4k systems
# stays cheap. Self-validating (Phase-H/P contract: bad input → {"error"} exit 1).

_OEC_SEARCH_CAP = 300

_OEC_PLANET_FILTER_KEYS = (
    "status", "discovery_method", "discovery_year_min", "discovery_year_max",
    "mass_min", "mass_max", "radius_min", "radius_max",
    "period_min", "period_max", "sma_min", "sma_max",
)


def _oec_elem_num(elem, tag):
    """First direct child <tag>'s text as float, or None."""
    e = elem.find(tag)
    if e is None:
        return None
    try:
        return float((e.text or "").strip())
    except (TypeError, ValueError):
        return None


def _oec_elem_int(elem, tag):
    v = _oec_elem_num(elem, tag)
    return int(v) if v is not None else None


def _oec_elem_text(elem, tag):
    e = elem.find(tag)
    t = (e.text or "").strip() if e is not None else ""
    return t or None


def _oec_max_binary_depth(system_elem):
    """Deepest <binary> nesting level (1 = a top-level binary, 2 = binary-in-binary),
    0 for a system with no binary — matches the PHASE_OEC_PLAN §A.2 depth census."""
    best = 0

    def walk(elem, depth):
        nonlocal best
        d = depth + 1 if elem.tag == "binary" else depth
        if elem.tag == "binary" and d > best:
            best = d
        for c in elem:
            walk(c, d)

    walk(system_elem, 0)
    return best


def _oec_planet_row(pl):
    """Compact per-planet summary for oec-search results (mass/radius in Jupiter units,
    period in days, sma in AU — OEC's native units; a consumer feeding Earth-unit tools
    must convert). `status` carries every <list> tag (a binary planet has 2+)."""
    mass_e = pl.find("mass")
    return {
        "name": (pl.findtext("name") or "").strip() or None,
        "mass": _oec_elem_num(pl, "mass"),
        "mass_type": mass_e.get("type") if mass_e is not None else None,
        "radius": _oec_elem_num(pl, "radius"),
        "period": _oec_elem_num(pl, "period"),
        "sma": _oec_elem_num(pl, "semimajoraxis"),
        "eccentricity": _oec_elem_num(pl, "eccentricity"),
        "discovery_method": _oec_elem_text(pl, "discoverymethod"),
        "discovery_year": _oec_elem_int(pl, "discoveryyear"),
        "status": [(e.text or "").strip() for e in pl.findall("list")
                   if e.text and e.text.strip()],
    }


def _oec_system_row(system_elem):
    """Topology summary of one system (counts, spectral types, distance) + its planet
    rows (under the internal `_planets` key, filtered/renamed by the caller)."""
    stars = system_elem.findall(".//star")
    planets = system_elem.findall(".//planet")
    attach = {"star": 0, "binary": 0, "system": 0}
    for parent_elem in system_elem.iter():
        for child in parent_elem:
            if child.tag == "planet" and parent_elem.tag in attach:
                attach[parent_elem.tag] += 1
    spectral = sorted({(s.findtext("spectraltype") or "").strip()
                       for s in stars if (s.findtext("spectraltype") or "").strip()})
    return {
        "name": (system_elem.findtext("name") or "").strip() or None,
        "n_stars": len(stars),
        "n_planets": len(planets),
        "n_binaries": len(system_elem.findall(".//binary")),
        "n_satellites": len(system_elem.findall(".//satellite")),
        "max_binary_depth": _oec_max_binary_depth(system_elem),
        "circumbinary": attach["binary"] > 0,
        "rogue": attach["system"] > 0,
        "spectral_types": spectral,
        "distance_pc": _oec_elem_num(system_elem, "distance"),
        "_planets": [_oec_planet_row(pl) for pl in planets],
    }


def _oec_planet_passes(p, pf):
    """A single planet row against the set planet-level filters (conjunction)."""
    if pf["status"] and not any(pf["status"].lower() in (st or "").lower()
                                for st in p["status"]):
        return False
    if pf["discovery_method"] and (pf["discovery_method"].lower()
                                   not in (p["discovery_method"] or "").lower()):
        return False
    dy = p["discovery_year"]
    if pf["discovery_year_min"] is not None and (dy is None or dy < pf["discovery_year_min"]):
        return False
    if pf["discovery_year_max"] is not None and (dy is None or dy > pf["discovery_year_max"]):
        return False
    for key, mn, mx in (("mass", "mass_min", "mass_max"),
                        ("radius", "radius_min", "radius_max"),
                        ("period", "period_min", "period_max"),
                        ("sma", "sma_min", "sma_max")):
        v = p[key]
        if pf[mn] is not None and (v is None or v < pf[mn]):
            return False
        if pf[mx] is not None and (v is None or v > pf[mx]):
            return False
    return True


def compute_oec_search(min_stars=None, max_stars=None, status=None, circumbinary=False,
                       discovery_method=None, discovery_year_min=None, discovery_year_max=None,
                       mass_min=None, mass_max=None, radius_min=None, radius_max=None,
                       period_min=None, period_max=None, sma_min=None, sma_max=None,
                       spectral_type=None, limit=None):
    """Structural search over the whole catalogue (Tier 2). A system matches when it
    passes the system-level filters (star count, circumbinary, host spectral type) AND —
    when any planet-level filter is set — carries ≥1 planet passing all of them.

    All filters optional. Ranges are inclusive; unit conventions match `oec-search`'s
    per-planet rows (mass/radius in Jupiter units, period days, sma AU). `spectral_type`
    is a case-insensitive **prefix** on a host star's spectral type ("G" → G0V…G9V, "DA"
    → white dwarfs). Returns {"count", "capped", "cap", "filters", "systems": [row, …]}
    or {"error": str}. Self-validating: an inverted min/max range or limit < 1 → error."""
    for lo, hi, label in ((min_stars, max_stars, "stars"),
                          (discovery_year_min, discovery_year_max, "discovery-year"),
                          (mass_min, mass_max, "mass"), (radius_min, radius_max, "radius"),
                          (period_min, period_max, "period"), (sma_min, sma_max, "sma")):
        if lo is not None and hi is not None and lo > hi:
            return {"error": f"{label} min ({lo}) exceeds max ({hi})."}
    cap = _OEC_SEARCH_CAP
    if limit is not None:
        if limit < 1:
            return {"error": "--limit must be >= 1."}
        cap = limit

    try:
        root, _ = _load_oec()
    except Exception as e:
        return {"error": _network_error_msg(e, "Open Exoplanet Catalogue")}

    pf = {"status": status, "discovery_method": discovery_method,
          "discovery_year_min": discovery_year_min, "discovery_year_max": discovery_year_max,
          "mass_min": mass_min, "mass_max": mass_max,
          "radius_min": radius_min, "radius_max": radius_max,
          "period_min": period_min, "period_max": period_max,
          "sma_min": sma_min, "sma_max": sma_max}
    has_pf = any(pf[k] is not None for k in _OEC_PLANET_FILTER_KEYS)
    sp_q = spectral_type.strip().upper() if spectral_type else None

    matches = []
    for system_elem in root:
        row = _oec_system_row(system_elem)
        if min_stars is not None and row["n_stars"] < min_stars:
            continue
        if max_stars is not None and row["n_stars"] > max_stars:
            continue
        if circumbinary and not row["circumbinary"]:
            continue
        if sp_q and not any(sp.upper().startswith(sp_q) for sp in row["spectral_types"]):
            continue
        planets = row.pop("_planets")
        if has_pf:
            planets = [p for p in planets if _oec_planet_passes(p, pf)]
            if not planets:
                continue
        row["planets"] = planets
        matches.append(row)

    return {
        "count": len(matches),
        "capped": len(matches) > cap,
        "cap": cap,
        "filters": {k: v for k, v in (
            ("min_stars", min_stars), ("max_stars", max_stars), ("status", status),
            ("circumbinary", circumbinary or None), ("discovery_method", discovery_method),
            ("discovery_year_min", discovery_year_min), ("discovery_year_max", discovery_year_max),
            ("mass_min", mass_min), ("mass_max", mass_max),
            ("radius_min", radius_min), ("radius_max", radius_max),
            ("period_min", period_min), ("period_max", period_max),
            ("sma_min", sma_min), ("sma_max", sma_max),
            ("spectral_type", spectral_type)) if v is not None},
        "systems": matches[:cap],
    }


def compute_oec_census():
    """Catalogue-wide topology statistics (Tier 3) — the PHASE_OEC_PLAN §A structural
    evaluation computed live: per-system distributions of star / planet counts and
    binary nesting depth, planet-attachment breakdown (star / binary / system),
    circumbinary / rogue / planetless counts, and discovery-method + status histograms.
    Returns the stats dict or {"error": str}."""
    try:
        root, index = _load_oec()
    except Exception as e:
        return {"error": _network_error_msg(e, "Open Exoplanet Catalogue")}

    stars_dist, planets_dist, depth_dist = {}, {}, {}
    attach = {"star": 0, "binary": 0, "system": 0}
    methods, statuses = {}, {}
    tot = {"stars": 0, "planets": 0, "binaries": 0, "satellites": 0, "names": 0}
    circumbinary_systems = rogue_systems = planetless = 0

    for system_elem in root:
        planets = system_elem.findall(".//planet")
        n_stars = len(system_elem.findall(".//star"))
        n_planets = len(planets)
        tot["stars"] += n_stars
        tot["planets"] += n_planets
        tot["binaries"] += len(system_elem.findall(".//binary"))
        tot["satellites"] += len(system_elem.findall(".//satellite"))
        tot["names"] += len(system_elem.findall(".//name"))
        stars_dist[n_stars] = stars_dist.get(n_stars, 0) + 1
        planets_dist[n_planets] = planets_dist.get(n_planets, 0) + 1
        depth = _oec_max_binary_depth(system_elem)
        depth_dist[depth] = depth_dist.get(depth, 0) + 1
        sys_circ = sys_rogue = False
        for parent_elem in system_elem.iter():
            for child in parent_elem:
                if child.tag == "planet" and parent_elem.tag in attach:
                    attach[parent_elem.tag] += 1
                    sys_circ = sys_circ or parent_elem.tag == "binary"
                    sys_rogue = sys_rogue or parent_elem.tag == "system"
        circumbinary_systems += sys_circ
        rogue_systems += sys_rogue
        planetless += (n_planets == 0)
        for pl in planets:
            dm = _oec_elem_text(pl, "discoverymethod")
            if dm:
                methods[dm] = methods.get(dm, 0) + 1
            for e in pl.findall("list"):
                st = (e.text or "").strip()
                if st:
                    statuses[st] = statuses.get(st, 0) + 1

    def _by_key(d):
        return {str(k): d[k] for k in sorted(d)}

    def _by_count(d):
        return dict(sorted(d.items(), key=lambda kv: (-kv[1], kv[0])))

    return {
        "n_systems": len(root),
        "n_stars": tot["stars"],
        "n_planets": tot["planets"],
        "n_binaries": tot["binaries"],
        "n_satellites": tot["satellites"],
        "n_name_tags": tot["names"],
        "n_alias_keys": len(index),
        "stars_per_system": _by_key(stars_dist),
        "planets_per_system": _by_key(planets_dist),
        "binary_depth": _by_key(depth_dist),
        "planet_attachment": attach,
        "circumbinary_systems": circumbinary_systems,
        "rogue_systems": rogue_systems,
        "planetless_systems": planetless,
        "discovery_methods": _by_count(methods),
        "status_counts": _by_count(statuses),
    }


def compute_oec_status():
    """Catalogue snapshot / cache state (Tier 3) — a lightweight freshness + counts
    check without the full census walk. Reports the local `systems.xml.gz` cache
    presence / size / age against the 7-day staleness window and the top-level element
    counts. Returns the status dict or {"error": str}."""
    import time
    import datetime as _dt
    cached = os.path.exists(_OEC_CACHE_FILE)
    size = os.path.getsize(_OEC_CACHE_FILE) if cached else None
    mtime = os.path.getmtime(_OEC_CACHE_FILE) if cached else None
    age_days = (time.time() - mtime) / 86400.0 if mtime is not None else None
    iso = (_dt.datetime.fromtimestamp(mtime, _dt.timezone.utc).isoformat()
           if mtime is not None else None)

    try:
        root, index = _load_oec()
    except Exception as e:
        return {"error": _network_error_msg(e, "Open Exoplanet Catalogue")}

    return {
        "source": _OEC_URL,
        "cache_path": os.path.abspath(_OEC_CACHE_FILE),
        "cached": cached,
        "cache_size_bytes": size,
        "cache_mtime_utc": iso,
        "cache_age_days": round(age_days, 3) if age_days is not None else None,
        "staleness_window_days": _OEC_CACHE_MAX_AGE_DAYS,
        "stale": (age_days is not None and age_days >= _OEC_CACHE_MAX_AGE_DAYS),
        "n_systems": len(root),
        "n_stars": sum(1 for _ in root.iter("star")),
        "n_planets": sum(1 for _ in root.iter("planet")),
        "n_binaries": sum(1 for _ in root.iter("binary")),
        "n_name_tags": sum(1 for _ in root.iter("name")),
        "n_alias_keys": len(index),
    }


# ── OEC display helpers (shared by the CLI and the GUI; pure, no I/O) ──────────
# Any field may be a list (repeated tag), so ALWAYS go through oec_fv — never read
# field["value"] directly (completed_plans/PHASE_OEC_PLAN.md §F.1).

def oec_fv(field):
    """First-or-list accessor → the primary value dict, or None."""
    if field is None:
        return None
    return field[0] if isinstance(field, list) else field


def oec_format_field(field, unit=""):
    """Format an OEC numeric/text field: 'value ±err unit', with bound markers.
    `upperlimit`/`lowerlimit` carry the numeric bound in the attribute (the text is
    usually empty), so a bound-only field renders as '<= N' / '>= N'."""
    fv = oec_fv(field)
    if fv is None:
        return ""
    s = fv.get("value", "")
    em, ep = fv.get("errorminus"), fv.get("errorplus")
    if em is not None or ep is not None:
        s += f" ±{ep}" if em == ep else f" +{ep or 0}/-{em or 0}"
    ul, ll = fv.get("upperlimit"), fv.get("lowerlimit")
    if not s:                                   # bound-only: number is in the attribute
        if ul is not None:
            s = f"<= {ul}"
        elif ll is not None:
            s = f">= {ll}"
    else:                                       # measured value + an extra bound
        if ul is not None:
            s += f" (<= {ul})"
        elif ll is not None:
            s += f" (>= {ll})"
    u = fv.get("unit") or unit
    return f"{s} {u}" if u else s


def oec_statuses(fields):
    """All <list> status strings for a planet node (a planet in a binary carries 2+)."""
    lst = fields.get("list")
    if not lst:
        return []
    return [x.get("value") for x in lst] if isinstance(lst, list) else [lst.get("value")]


def oec_binary_label(node):
    """A display name for a (possibly unnamed) binary — synthesized from components."""
    if node.get("names"):
        return node["names"][0]
    comp = []
    for c in node.get("children", []):
        nm = (c["names"][0] if c.get("names")
              else (oec_binary_label(c) if c.get("tag") == "binary" else "?"))
        comp.append(nm.split(" ")[-1] if nm else "?")
    return f"Binary ({' + '.join(comp)})" if comp else "Binary"


# ── Option 50: Star Systems CSV Query ────────────────────────────────────────

# The opt-50 key set is now the canonical shared one (which leads with "NAME").
#
# History: P4.6 kept a deliberately NAME-less copy here to preserve opt-50's historical
# output, which meant SIMBAD's common name (e.g. "NAME Chara" for * bet CVn) was parsed
# out of the `ids` field and then dropped — so no `star_systems.designations` value ever
# carried one, and every table fed by that column (opts 18/19, opt 51's CSV, the Route
# Planning tables, the Star Chart click-info box, the G1 search) showed catalog ids only.
# The drift is retired: NAME is captured and listed FIRST. Do not re-introduce a local
# key set here — `core.shared._CSV_DESIG_KEYS` is the single source of truth.
#
# Note: `star_systems` rows written before this change have no NAME token; re-run
# option 50 to rebuild the table with them.
_CSV_DESIG_KEYS = _CSV_DESIG_KEYS_SHARED


def _parse_designations_from_ids(ids_string: str) -> str:
    """Parse a pipe-separated SIMBAD ids string into a comma-separated designation string.
    Delegates to the canonical shared parser (NAME first, then the catalog ids)."""
    return _parse_designations_from_ids_shared(ids_string)


def _masked_to_none(val):
    """Return None if val is a numpy/astropy masked element, otherwise val."""
    try:
        if hasattr(val, "mask") and val.mask:
            return None
    except Exception:
        pass
    return val


def _run_simbad_csv_query(simbad, criteria, query_num, total_queries,
                           existing_ids, progress_callback=None):
    """Run one SIMBAD criteria query; return (new_rows, discarded)."""
    import warnings
    if progress_callback:
        progress_callback(f"Query {query_num}/{total_queries}: running SIMBAD query…")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = simbad.query_criteria(criteria)
    except Exception as e:
        return [], 0

    if result is None or len(result) == 0:
        return [], 0

    seen_main_ids = {}
    new_rows  = []
    discarded = 0

    for row in result:
        main_id = str(row["main_id"]).strip() if row["main_id"] is not None else ""
        ids_str = str(row["ids"]).strip()     if row["ids"]     is not None else ""
        sp_type = str(row["sp_type"]).strip() if row["sp_type"] is not None else ""
        if sp_type.lower() in ("", "none", "--"):
            sp_type = ""
        desig_str = _parse_designations_from_ids(ids_str)

        if main_id.startswith("PLX ") and desig_str == "" and sp_type == "":
            discarded += 1
            continue
        if main_id in seen_main_ids or main_id in existing_ids:
            continue

        try:
            plx_raw = _masked_to_none(row["plx_value"])
            plx_f   = float(plx_raw)
            plx     = f"{plx_f:.4f}"
            # P6.5: write None (→ SQL NULL) not "" for the REAL columns on a failed/
            # degenerate parse, so a blank cell is a true NULL rather than an empty
            # string papered over by NULLIF later.
            parsecs = f"{1000.0 / plx_f:.3f}" if plx_f > 0 else None
            ly      = f"{1000.0 / plx_f * 3.26156:.3f}" if plx_f > 0 else None
        except (TypeError, ValueError, ZeroDivisionError):
            plx = parsecs = ly = None

        try:
            v_raw = _masked_to_none(row['V'])
            vmag  = f"{float(v_raw):.3f}"
        except (TypeError, ValueError):
            vmag = None

        try:
            ra_raw = _masked_to_none(row["ra"])
            ra_deg = float(ra_raw)
            ra_h   = int(ra_deg / 15)
            ra_m   = int((ra_deg / 15 - ra_h) * 60)
            ra_s   = ((ra_deg / 15 - ra_h) * 60 - ra_m) * 60
            ra     = f"{ra_h:02d} {ra_m:02d} {ra_s:07.4f}"
        except (TypeError, ValueError):
            ra = ""

        try:
            dec_raw  = _masked_to_none(row["dec"])
            dec_deg  = float(dec_raw)
            dec_sign = "-" if dec_deg < 0 else "+"
            dec_abs  = abs(dec_deg)
            dec_d    = int(dec_abs)
            dec_m    = int((dec_abs - dec_d) * 60)
            dec_s    = ((dec_abs - dec_d) * 60 - dec_m) * 60
            dec      = f"{dec_sign}{dec_d:02d} {dec_m:02d} {dec_s:06.3f}"
        except (TypeError, ValueError):
            dec = ""

        seen_main_ids[main_id] = len(new_rows)
        existing_ids.add(main_id)
        new_rows.append({
            "Star Name":          main_id,
            "Star Designations":  desig_str,
            "Spectral Type":      sp_type,
            "Parallax":           plx,
            "Parsecs":            parsecs,
            "Light Years":        ly,
            "Apparent Magnitude": vmag,
            "RA":                 ra,
            "DEC":                dec,
        })

    if progress_callback:
        progress_callback(
            f"Query {query_num}/{total_queries} — {len(new_rows)} new stars ({discarded} discarded)"
        )
    return new_rows, discarded


def compute_star_systems_csv(progress_callback=None) -> dict:
    """Run 17 SIMBAD criteria queries and write results to the star_systems DB table.

    Calls progress_callback(msg) after each query.
    Returns {total_rows, queries_run, backup_table, total_new, total_discarded}
    or {"error": str}.
    """
    from astroquery.simbad import Simbad
    from datetime import datetime
    from core.db import get_conn

    simbad = Simbad()
    simbad.TIMEOUT = 480
    simbad.add_votable_fields("sp_type", "plx_value", "V", "ids")

    conn = get_conn()

    # Back up existing rows to a dated table, then clear for fresh run.
    backup_table = None
    existing_count = conn.execute("SELECT COUNT(*) FROM star_systems").fetchone()[0]
    if existing_count > 0:
        date_stamp   = datetime.now().strftime("%Y%m%d")
        backup_table = f"star_systems_backup_{date_stamp}"
        with conn:
            conn.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM star_systems")
            conn.execute("DELETE FROM star_systems")

    existing_ids = set()

    queries = [
        "plx > 25.99 & otype = 'Star' & maintype != 'Planet' & maintype != 'Planet?'",
        "plx > 20.99 & plx < 26 & otype = 'Star' & maintype != 'Planet' & maintype != 'Planet?'",
        "plx > 17.99 & plx < 21 & otype = 'Star' & (maintype != 'Planet' & maintype != 'Planet?')",
        "plx > 16.49 & plx < 18 & otype = 'Star' & (maintype != 'Planet' & maintype != 'Planet?')",
        "plx > 15.49 & plx < 16.5 & otype = 'Star' & (maintype != 'Planet' & maintype != 'Planet?')",
        "plx > 14.49 & plx < 15.5 & otype = 'Star' & (maintype != 'Planet' & maintype != 'Planet?')",
        "plx > 13.99 & plx < 14.5 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
        "plx > 13.49 & plx < 14 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
        "plx > 12.99 & plx < 13.5 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
        "plx > 12.49 & plx < 13 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
        "plx > 11.99 & plx < 12.5 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
        "plx > 11.49 & plx < 12 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
        "plx > 11.09 & plx < 11.5 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
        "plx > 10.79 & plx < 11.1 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
        "plx > 10.49 & plx < 10.8 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
        "plx > 10.29 & plx < 10.5 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
        "plx > 9.99 & plx < 10.3 & otype = 'Star' & (maintype != 'Pl' & maintype != 'Pl?')",
    ]

    all_new_rows    = []
    total_discarded = 0
    total_queries   = len(queries)

    for i, criteria in enumerate(queries, start=1):
        new_rows, discarded = _run_simbad_csv_query(
            simbad, criteria, i, total_queries, existing_ids, progress_callback
        )
        all_new_rows.extend(new_rows)
        total_discarded += discarded

    all_new_rows.sort(key=lambda r: float(r["Light Years"]) if r["Light Years"] else float("inf"))

    try:
        with conn:
            conn.executemany(
                """INSERT INTO star_systems
                   (star_name, designations, spectral_type, parallax,
                    parsecs, light_years, app_magnitude, ra, dec)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        r["Star Name"],
                        r["Star Designations"],
                        r["Spectral Type"],
                        r["Parallax"],
                        r["Parsecs"],
                        r["Light Years"],
                        r["Apparent Magnitude"],
                        r["RA"],
                        r["DEC"],
                    )
                    for r in all_new_rows
                ],
            )
    except Exception as e:
        return {"error": f"Could not write to star_systems table: {e}"}

    # Prune old dated backups — keep the 3 newest (including the one just made).
    from core.db import prune_star_systems_backups
    prune = prune_star_systems_backups(keep_n=3)

    return {
        "total_rows":      len(all_new_rows),
        "queries_run":     total_queries,
        "backup_table":    backup_table,
        "total_new":       len(all_new_rows),
        "total_discarded": total_discarded,
        "backups_dropped": prune["dropped"],
        "backups_kept":    prune["kept"],
    }


# ── Option 51: Export Star Systems to CSV ────────────────────────────────────

def export_star_systems_csv(output_dir: str) -> dict:
    """Read the star_systems table and write starSystems.csv to output_dir.

    Returns {"path": str, "count": int} or {"error": str}.
    """
    from core.db import get_conn

    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM star_systems ORDER BY light_years ASC"
    ).fetchall()

    if not rows:
        return {"error": "star_systems table is empty. Run option 50 first."}

    path = os.path.join(output_dir, "starSystems.csv")
    fieldnames = [
        "Star Name", "Star Designations", "Spectral Type", "Parallax",
        "Parsecs", "Light Years", "Apparent Magnitude", "RA", "DEC",
    ]

    try:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow({
                    "Star Name":          r["star_name"],
                    "Star Designations":  r["designations"],
                    "Spectral Type":      r["spectral_type"],
                    "Parallax":           r["parallax"],
                    "Parsecs":            r["parsecs"],
                    "Light Years":        r["light_years"],
                    "Apparent Magnitude": r["app_magnitude"],
                    "RA":                 r["ra"],
                    "DEC":                r["dec"],
                })
    except Exception as e:
        return {"error": f"Could not write starSystems.csv: {e}"}

    return {"path": path, "count": len(rows)}


# ── Options 52–56: Import functions ──────────────────────────────────────────

def import_hwc_csv(csv_path: str) -> dict:
    """Replace the hwc table with data from csv_path.

    Returns {"count": int, "path": str} or {"error": str}.
    """
    from core.db import get_conn

    if not os.path.exists(csv_path):
        return {"error": f"File not found: {csv_path}"}

    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = list(reader)
    except Exception as e:
        return {"error": f"Could not read file: {e}"}

    required = {"P_NAME", "S_NAME", "S_NAME_HIP", "S_NAME_HD"}
    missing = required - set(headers)
    if missing:
        return {"error": f"Missing required columns: {', '.join(sorted(missing))}"}

    bad = _validate_csv_headers(headers)
    if bad:
        return bad

    conn = get_conn()
    cols_ddl = ", ".join(f'"{col}" TEXT' for col in headers)
    placeholders = ", ".join("?" for _ in headers)

    try:
        col_list = ", ".join(f'"{col}"' for col in headers)
        with conn:
            conn.execute("DROP TABLE IF EXISTS hwc")
            conn.execute(f"CREATE TABLE hwc ({cols_ddl})")
            conn.executemany(
                f"INSERT INTO hwc ({col_list}) VALUES ({placeholders})",
                [tuple(r.get(col, "") for col in headers) for r in rows],
            )
    except Exception as e:
        return {"error": f"Database error: {e}"}

    global _HWC_DATA
    with _HWC_LOCK:                          # flush the lazy cache under its lock (P6.4)
        _HWC_DATA = None

    return {"count": len(rows), "path": csv_path}


def import_mission_exocat_csv(csv_path: str) -> dict:
    """Replace the mission_exocat table with data from csv_path.

    Returns {"count": int, "path": str} or {"error": str}.
    """
    from core.db import get_conn

    if not os.path.exists(csv_path):
        return {"error": f"File not found: {csv_path}"}

    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = list(reader)
    except Exception as e:
        return {"error": f"Could not read file: {e}"}

    required = {"star_name", "hip_name", "hd_name", "gj_name"}
    missing = required - set(headers)
    if missing:
        return {"error": f"Missing required columns: {', '.join(sorted(missing))}"}

    bad = _validate_csv_headers(headers)
    if bad:
        return bad

    conn = get_conn()
    # First column is rowid (INTEGER PRIMARY KEY); remaining are TEXT.
    rest = [col for col in headers if col != "rowid"]
    cols_ddl = '"rowid" INTEGER PRIMARY KEY, ' + ", ".join(f'"{col}" TEXT' for col in rest)
    all_cols = ["rowid"] + rest
    placeholders = ", ".join("?" for _ in all_cols)

    try:
        col_list = ", ".join(f'"{col}"' for col in all_cols)
        with conn:
            conn.execute("DROP TABLE IF EXISTS mission_exocat")
            conn.execute(f"CREATE TABLE mission_exocat ({cols_ddl})")
            conn.executemany(
                f"INSERT INTO mission_exocat ({col_list}) VALUES ({placeholders})",
                [tuple(r.get(col, "") for col in all_cols) for r in rows],
            )
    except Exception as e:
        return {"error": f"Database error: {e}"}

    global _MISSION_EXOCAT
    with _MISSION_EXOCAT_LOCK:               # flush the lazy cache under its lock (P6.4)
        _MISSION_EXOCAT = None

    return {"count": len(rows), "path": csv_path}


def import_main_sequence_csv(csv_path: str) -> dict:
    """Replace main_sequence_stars table with data from csv_path.

    Returns {"count": int, "path": str} or {"error": str}.
    """
    from core.db import get_conn

    if not os.path.exists(csv_path):
        return {"error": f"File not found: {csv_path}"}

    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = list(reader)
    except Exception as e:
        return {"error": f"Could not read file: {e}"}

    required = {"Spectral Class", "Bolo. Corr. (BC)"}
    missing = required - set(headers)
    if missing:
        return {"error": f"Missing required columns: {', '.join(sorted(missing))}"}

    conn = get_conn()
    try:
        with conn:
            conn.execute("DELETE FROM main_sequence_stars")
            conn.executemany(
                """INSERT INTO main_sequence_stars
                   (spectral_class, b_v, teff_k, abs_mag_vis, abs_mag_bol, bc,
                    lum, radius, mass, density, lifetime)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        r.get("Spectral Class", ""),
                        r.get("B-V", ""),
                        r.get("Teeff(K)", ""),
                        r.get("AbsMag Vis.", ""),
                        r.get("AbsMag Bol.", ""),
                        r.get("Bolo. Corr. (BC)", ""),
                        r.get("Lum", ""),
                        r.get("R", ""),
                        r.get("M", ""),
                        r.get("p (g/cm3)", ""),
                        r.get("Lifetime (years)", ""),
                    )
                    for r in rows
                ],
            )
    except Exception as e:
        return {"error": f"Database error: {e}"}

    return {"count": len(rows), "path": csv_path}


def import_solar_system_csvs(data_dir: str) -> dict:
    """Replace planets, moons, dwarf_planets, and asteroids tables from CSV files in data_dir.

    Validates all four files exist before replacing anything.
    Returns {"planets": N, "moons": N, "dwarf_planets": N, "asteroids": N} or {"error": str}.
    """
    from core.db import get_conn

    files = {
        "planets":      "planetInfo.csv",
        "moons":        "moonInfo.csv",
        "dwarf_planets": "dwarfPlanetInfo.csv",
        "asteroids":    "asteroidsInfo.csv",
    }
    paths = {key: os.path.join(data_dir, fname) for key, fname in files.items()}
    missing = [fname for key, fname in files.items() if not os.path.exists(paths[key])]
    if missing:
        return {"error": f"File(s) not found: {', '.join(missing)}"}

    def _read(path):
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    try:
        planet_rows      = _read(paths["planets"])
        moon_rows        = _read(paths["moons"])
        dwarf_rows       = _read(paths["dwarf_planets"])
        asteroid_rows    = _read(paths["asteroids"])
    except Exception as e:
        return {"error": f"Could not read file: {e}"}

    conn = get_conn()
    try:
        with conn:
            conn.execute("DELETE FROM planets")
            conn.executemany(
                """INSERT INTO planets
                   (planet_name, mass, diameter, period, periastron,
                    semimajor_axis, apastron, eccentricity, moons)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(r.get("Planet",""), r.get("Mass",""), r.get("Diameter",""),
                  r.get("Period",""), r.get("Periastron",""), r.get("Semimajor Axis",""),
                  r.get("Apastron",""), r.get("Eccentricity",""), r.get("Moons",""))
                 for r in planet_rows],
            )

            conn.execute("DELETE FROM moons")
            conn.executemany(
                """INSERT INTO moons
                   (satellite_name, planet_name, diameter_km, mean_radius_km, mass_kg,
                    perigee_km, apogee_km, semimajor_axis_km, eccentricity,
                    period_days, gravity, escape_velocity)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(r.get("Satellite Name",""), r.get("Planet Name",""), r.get("Diameter (km)",""),
                  r.get("Mean Radius (km)",""), r.get("Mass (kg)",""), r.get("Perigee (km)",""),
                  r.get("Apogee (km)",""), r.get("SemiMajor Axis (km)",""), r.get("Eccentricity",""),
                  r.get("Period (days)",""), r.get("Gravity (m/s^2)",""), r.get("Escape Velocity (km/s)",""))
                 for r in moon_rows],
            )

            conn.execute("DELETE FROM dwarf_planets")
            conn.executemany(
                """INSERT INTO dwarf_planets
                   (name, periastron, semimajor_axis, apastron, eccentricity,
                    period, mass, diameter, moons)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(r.get("Name",""), r.get("Periastron",""), r.get("Semimajor Axis",""),
                  r.get("Apastron",""), r.get("Eccentricity",""), r.get("Period",""),
                  r.get("Mass",""), r.get("Diameter",""), r.get("Moons",""))
                 for r in dwarf_rows],
            )

            conn.execute("DELETE FROM asteroids")
            conn.executemany(
                """INSERT INTO asteroids
                   (name, periastron, semimajor_axis, apastron, eccentricity, period, diameter)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [(r.get("Name",""), r.get("Periastron",""), r.get("Semimajor Axis",""),
                  r.get("Apastron",""), r.get("Eccentricity",""), r.get("Period",""),
                  r.get("Diameter",""))
                 for r in asteroid_rows],
            )
    except Exception as e:
        return {"error": f"Database error: {e}"}

    return {
        "planets":      len(planet_rows),
        "moons":        len(moon_rows),
        "dwarf_planets": len(dwarf_rows),
        "asteroids":    len(asteroid_rows),
    }


# ── Hypatia Catalog ────────────────────────────────────────────────────────────

_HYPATIA_BASE = "https://hypatiacatalog.com/hypatia/api/v2"

# All 104 Hypatia species (incl. ionized) and their names/atomic numbers/categories
# live in core.hypatia_elements — the single source of truth shared with the GUI and CLI.
from core.hypatia_elements import (
    HYPATIA_REQUEST_SYMBOLS,
    SPECIES_BY_SYMBOL,
    SPECIES_ORDER,
)

# The Hypatia server caps the GET request line at ~4094 bytes, so the 104 species can't be
# requested in one call — fetch in chunks small enough to stay well under that limit.
_HYPATIA_COMPOSITION_CHUNK = 30


def _parse_hypatia_star(data: list) -> dict:
    """Parse /star JSON response into a normalized properties dict.

    Field names are confirmed against the live API.  Additional fallback keys
    handle any minor naming variations across API versions.
    """
    if not data:
        return {}
    s = data[0]

    def _f(key, *fallbacks):
        for k in (key,) + fallbacks:
            v = s.get(k)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
        return None

    return {
        "teff":          _f("temperature", "teff", "t_eff"),
        "logg":          _f("logg", "log_g"),
        "spectral_type": s.get("spectral_type") or s.get("spectraltype") or s.get("sptype"),
        "vmag":          _f("vmag", "v_mag"),
        "bmag":          _f("bmag", "b_mag"),
        "bv":            _f("bv", "b_v", "color_bv"),
        "distance_pc":   _f("dist", "distance", "distance_pc"),
        "disk":          s.get("disk") or s.get("disk_membership"),
        "u_vel":         _f("u", "u_vel", "uvel"),
        "v_vel":         _f("v", "v_vel", "vvel"),
        "w_vel":         _f("w", "w_vel", "wvel"),
        "pm_ra":         _f("pm_ra", "pmra", "proper_motion_ra"),
        "pm_dec":        _f("pm_dec", "pmdec", "proper_motion_dec"),
    }


def _parse_hypatia_composition(data: list) -> list:
    """Parse /composition JSON response into a list of element abundance dicts.

    Omits species for which no mean value is available. Preserves the species'
    casing as returned by the API (e.g. "Fe", "Ba_II"), attaches the full element
    name / atomic number / nucleosynthetic-family category from the master table,
    and orders the result by that table's display order.
    """
    results = []

    for item in data:
        el_raw = item.get("element") or item.get("name") or ""
        el = el_raw.strip()
        key = el.lower()

        mean = None
        for k in ("mean", "average", "median"):
            v = item.get(k)
            if v is not None:
                try:
                    mean = float(v)
                    break
                except (TypeError, ValueError):
                    pass
        if mean is None:
            continue

        def _f2(k, *fallbacks):
            for kk in (k,) + fallbacks:
                v = item.get(kk)
                if v is not None:
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        pass
            return None

        n_raw = item.get("n") or item.get("catalog_count") or item.get("num_catalogs")
        try:
            n = int(n_raw) if n_raw is not None else None
        except (TypeError, ValueError):
            n = None
        # The API has no explicit catalog count, but lists per-catalog values in
        # "catalogs_linear" — use its length as the "# Catalogs" value when present.
        if n is None:
            cl = item.get("catalogs_linear")
            if isinstance(cl, dict):
                n = len(cl)

        species = SPECIES_BY_SYMBOL.get(key, {})

        # Hypatia's "plusminus" is the symmetric spread in dex ([X/H]) and is the
        # value the catalog plots as an error bar. The API's own "std" field is the
        # log of the linear-space scatter — it is negative for almost every element
        # and is NOT a usable dex uncertainty, so prefer "plusminus" here.
        results.append({
            "element":  el or species.get("symbol", ""),  # API casing, e.g. "Ba_II"
            "name":     species.get("name", ""),
            "z":        species.get("z"),
            "category": species.get("category", ""),
            "mean":     mean,
            "std":      _f2("plusminus", "std", "sigma", "stdev"),
            "min":      _f2("min", "minimum"),
            "max":      _f2("max", "maximum"),
            "n":        n,
            "_order":   SPECIES_ORDER.get(key, 999),
        })

    results.sort(key=lambda x: x["_order"])
    for r in results:
        del r["_order"]
    return results


def compute_hypatia_data(simbad_result: dict) -> dict:
    """Fetch stellar properties and elemental abundances from Hypatia Catalog API.

    Uses HIP → HD → MAIN_ID from the SIMBAD result for name resolution.
    Returns {"star_name": str, "properties": dict, "abundances": list}
    or {"error": str}.
    """
    import requests

    desig = simbad_result.get("designations", {})
    star_name = (
        desig.get("HIP")
        or desig.get("HD")
        or simbad_result.get("main_id", "")
    )
    if not star_name:
        return {"error": "No usable designation for Hypatia Catalog lookup"}

    # ── /star endpoint ────────────────────────────────────────────────────────
    try:
        def _get_star():
            r = requests.get(
                f"{_HYPATIA_BASE}/star",
                params={"name": [star_name]},
                timeout=30,
            )
            r.raise_for_status()
            return r.json()
        star_data = _with_retries(_get_star)
    except Exception as e:
        return {"error": _network_error_msg(e, "Hypatia Catalog")}

    if not star_data:
        return {"error": f"No Hypatia data for '{star_name}'"}

    properties = _parse_hypatia_star(star_data)

    # ── /composition endpoint ─────────────────────────────────────────────────
    # All 104 species are requested, but the server caps the GET request line at
    # ~4094 bytes, so they're fetched in chunks and the responses concatenated.
    abundances = []
    try:
        comp_data = []
        for i in range(0, len(HYPATIA_REQUEST_SYMBOLS), _HYPATIA_COMPOSITION_CHUNK):
            chunk = HYPATIA_REQUEST_SYMBOLS[i:i + _HYPATIA_COMPOSITION_CHUNK]
            nch = len(chunk)
            comp_params = {
                "name":      [star_name] * nch,
                "element":   chunk,
                "solarnorm": ["lodders09"] * nch,
            }

            def _get_comp(params=comp_params):
                r = requests.get(
                    f"{_HYPATIA_BASE}/composition",
                    params=params,
                    timeout=30,
                )
                r.raise_for_status()
                return r.json()
            comp_data.extend(_with_retries(_get_comp))
        abundances = _parse_hypatia_composition(comp_data)
    except Exception:
        pass  # return properties with empty abundances rather than failing entirely

    return {
        "star_name":  star_name,
        "properties": properties,
        "abundances": abundances,
    }


# ── Hypatia Catalog bulk cache (Phase L4) ─────────────────────────────────────
#
# The /star and /composition endpoints are per-star, so cross-star abundance
# SEARCH ("every star with Fe/H < -0.3 and Mg/H > 0") is impossible against the
# live API. import_hypatia_cache pulls the WHOLE catalog into a local two-table
# EAV cache via the bulk GET /data endpoint: one call per axis returns
# {star_name: value} for every star carrying that quantity (~8 stellar-property
# axes + 104 element axes). /data carries only the catalog-averaged [X/H] MEAN
# (the search filter key); the spread (std/min/max/n) and UVW kinematics are NOT
# bulk-available (the u/v/w /data axes collide with the U/V/W element symbols),
# so those columns stay NULL — the live per-star compute_hypatia_data still
# serves the full detail. Import flow mirrors compute_gcns_ingest (validate-
# before-destroy gate + atomic replace).

_HYPATIA_USER_AGENT = "SpaceAndScienceFictionApp/1.0 (greg.barnette@gmail.com)"
_HYPATIA_SOURCE = ("Hypatia Catalog (Hinkel et al. 2014, AJ 148, 54; "
                   "arXiv:1712.04944) via hypatiacatalog.com /data API")

# /data stellar-property axis -> hypatia_cache column.
_HYPATIA_DATA_PROP_AXES = {
    "teff":   "teff",
    "logg":   "logg",
    "vmag":   "vmag",
    "bv":     "bv",
    "dist":   "distance_pc",
    "disk":   "disk",
    "pm_ra":  "pm_ra",
    "pm_dec": "pm_dec",
}

# Floor below which the Fe pull is treated as truncated/incomplete (catalog is
# ~6k stars; Fe is the most-measured element). Guards the atomic replace from
# wiping a good cache with a short download. Sits well under the known count.
_HYPATIA_MIN_STARS = 1000

# Polite serial inter-request delay (Stage 0a throttle envelope).
_HYPATIA_REQUEST_DELAY = 0.5


def _norm_hypatia_name(name: str) -> str:
    """Collapse internal whitespace in a Hypatia /data star name.

    /data right-justifies the catalog number ("*   1 Aqr"); collapsing to single
    spaces ("* 1 Aqr") yields the canonical SIMBAD main_id form, which is also
    how star_systems stores names — so the G1 fe_h JOIN can match on star_name.
    """
    return " ".join((name or "").split())


def _hypatia_data_fetch(axis: str) -> dict:
    """GET /data for one axis; return {normalized_star_name: value}.

    Serial + polite (Stage 0a envelope): a short inter-request delay,
    _with_retries backoff on failure, and honoring a Retry-After header on
    429/503. Raises on exhausted retries (caller classifies via
    _network_error_msg).
    """
    import time
    import requests

    def _get():
        r = requests.get(
            f"{_HYPATIA_BASE}/data/",
            params={"xaxis1": axis},
            headers={"User-Agent": _HYPATIA_USER_AGENT},
            timeout=60,
        )
        if r.status_code in (429, 503):
            retry_after = r.headers.get("Retry-After")
            if retry_after:
                try:
                    time.sleep(min(float(retry_after), 30.0))
                except ValueError:
                    pass
        r.raise_for_status()
        return r.json()

    data = _with_retries(_get)
    time.sleep(_HYPATIA_REQUEST_DELAY)

    out = {}
    for v in (data.get("values") or []):
        name = _norm_hypatia_name(v.get("name", ""))
        val = v.get("xaxis")
        if name and val is not None:
            out[name] = val
    return out


def import_hypatia_cache(progress_callback=None) -> dict:
    """Pull the whole Hypatia Catalog into the local EAV cache (replace-in-place).

    Flow (mirrors compute_gcns_ingest — a short/truncated download leaves the
    existing cache intact):
      1. bulk-fetch every stellar-property axis + every element axis into memory
      2. Gate 1 (BEFORE any DB write): abort if the [Fe/H] star count is below
         the floor
      3. assemble star rows (props + denormalized fe_h + precomputed light_years)
         and (star, element) abundance rows
      4. replace-in-place: DELETE + bulk INSERT both tables in ONE transaction
      5. Gate 2 (post-commit) + provenance into hypatia_meta

    Returns {inserted, abundance_rows, fe_h_count, errors, total_candidates,
    snapshot_date, source} or {"error": str}.
    """
    from datetime import datetime
    from core.db import get_conn
    from core.hypatia_elements import HYPATIA_REQUEST_SYMBOLS

    def _progress(msg):
        if progress_callback:
            progress_callback(msg)

    star_props = {}   # normalized name -> {column: value}

    def _ensure(name):
        d = star_props.get(name)
        if d is None:
            d = {}
            star_props[name] = d
        return d

    n_axes = len(_HYPATIA_DATA_PROP_AXES) + len(HYPATIA_REQUEST_SYMBOLS)
    done = 0

    # ── 1. Stellar-property axes ─────────────────────────────────────────────
    for axis, col in _HYPATIA_DATA_PROP_AXES.items():
        done += 1
        _progress(f"Fetching star property '{axis}' ({done}/{n_axes})…")
        try:
            vals = _hypatia_data_fetch(axis)
        except Exception as e:
            return {"error": _network_error_msg(e, f"Hypatia Catalog (/data {axis})")}
        for name, v in vals.items():
            _ensure(name)[col] = v

    # ── 1b. Element axes ─────────────────────────────────────────────────────
    abund = {}   # normalized name -> {element: mean}
    errors = 0
    for sym in HYPATIA_REQUEST_SYMBOLS:
        done += 1
        _progress(f"Fetching element '{sym}' ({done}/{n_axes})…")
        try:
            vals = _hypatia_data_fetch(sym)
        except Exception:
            errors += 1   # one element axis failing is non-fatal
            continue
        for name, v in vals.items():
            abund.setdefault(name, {})[sym] = v
            if sym == "Fe":
                _ensure(name)["fe_h"] = v

    # ── 2. Gate 1 (before any DB write) ──────────────────────────────────────
    fe_count = sum(1 for d in star_props.values() if d.get("fe_h") is not None)
    if fe_count < _HYPATIA_MIN_STARS:
        return {"error": (f"Hypatia /data returned only {fe_count:,} stars with "
                          f"[Fe/H] (expected >= {_HYPATIA_MIN_STARS:,}). Likely an "
                          "incomplete download; aborted before writing. Existing "
                          "hypatia_cache left intact.")}

    # ── 3. Assemble rows ─────────────────────────────────────────────────────
    snapshot_date = datetime.now().strftime("%Y-%m-%d")
    all_names = set(star_props) | set(abund)
    cache_rows = []
    for name in all_names:
        d = star_props.get(name, {})
        dist_pc = _fval(d.get("distance_pc"))
        ly = dist_pc * _LY_PER_PC if dist_pc is not None else None
        disk = d.get("disk")
        if isinstance(disk, float) and disk.is_integer():
            disk = int(disk)
        disk_s = str(disk) if disk is not None else None
        cache_rows.append((
            name, None, None,
            _fval(d.get("teff")), _fval(d.get("logg")), _fval(d.get("vmag")),
            _fval(d.get("bv")), dist_pc, disk_s,
            None, None, None,                       # u_vel / v_vel / w_vel
            _fval(d.get("pm_ra")), _fval(d.get("pm_dec")),
            _fval(d.get("fe_h")), ly, snapshot_date,
        ))

    abund_rows = []
    for name, elems in abund.items():
        for sym, v in elems.items():
            fv = _fval(v)
            if fv is None:
                continue
            abund_rows.append((name, sym, fv, None, None, None, None))

    # ── 4. Replace-in-place (one transaction) ────────────────────────────────
    _progress(f"Writing {len(cache_rows):,} stars / {len(abund_rows):,} abundances…")
    conn = get_conn()
    try:
        with conn:
            conn.execute("DELETE FROM hypatia_abundance")
            conn.execute("DELETE FROM hypatia_cache")
            conn.executemany(
                "INSERT INTO hypatia_cache (star_name, hip, hd, teff, logg, vmag, "
                "bv, distance_pc, disk, u_vel, v_vel, w_vel, pm_ra, pm_dec, fe_h, "
                "light_years, fetched_date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                cache_rows,
            )
            conn.executemany(
                "INSERT INTO hypatia_abundance (star_name, element, mean, std, "
                "min, max, n) VALUES (?,?,?,?,?,?,?)",
                abund_rows,
            )
    except Exception as e:
        return {"error": f"Could not write Hypatia cache tables: {e}"}

    # ── 5. Gate 2 (post-commit) + provenance ─────────────────────────────────
    final = conn.execute("SELECT COUNT(*) FROM hypatia_cache").fetchone()[0]
    if final < _HYPATIA_MIN_STARS:
        return {"error": (f"Post-commit check failed: hypatia_cache holds {final:,} "
                          f"rows (expected >= {_HYPATIA_MIN_STARS:,}).")}
    final_abund = conn.execute("SELECT COUNT(*) FROM hypatia_abundance").fetchone()[0]

    meta = {
        "snapshot_date":   snapshot_date,
        "source":          _HYPATIA_SOURCE,
        "simbad_norm":     "lodders09",
        "star_count":      str(final),
        "abundance_count": str(final_abund),
        "fe_h_count":      str(fe_count),
        "axis_errors":     str(errors),
    }
    with conn:
        conn.executemany(
            "INSERT OR REPLACE INTO hypatia_meta (key, value) VALUES (?, ?)",
            list(meta.items()),
        )

    _progress(f"Done — {final:,} stars, {final_abund:,} abundance rows "
              f"({fe_count:,} with [Fe/H]).")
    return {
        "inserted":         final,
        "abundance_rows":   final_abund,
        "fe_h_count":       fe_count,
        "errors":           errors,
        "total_candidates": len(all_names),
        "snapshot_date":    snapshot_date,
        "source":           _HYPATIA_SOURCE,
    }


def _hypatia_meta_dict() -> dict:
    """Return the hypatia_meta key/value pairs as a dict (empty if unbuilt)."""
    from core.db import get_conn
    conn = get_conn()
    try:
        rows = conn.execute("SELECT key, value FROM hypatia_meta").fetchall()
        return {r["key"]: r["value"] for r in rows}
    except Exception:
        return {}


def import_honorverse_hyper_csv(csv_path: str) -> dict:
    """Replace honorverse_hyper table with data from csv_path (headerless CSV).

    Returns {"count": int, "path": str} or {"error": str}.
    """
    from core.db import get_conn

    if not os.path.exists(csv_path):
        return {"error": f"File not found: {csv_path}"}

    rows = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            for line in csv.reader(f):
                if len(line) < 2:
                    continue
                sp_class = line[0].strip().strip('"')
                try:
                    lm = float(line[1])
                except ValueError:
                    continue
                rows.append((sp_class, lm))
    except Exception as e:
        return {"error": f"Could not read file: {e}"}

    if not rows:
        return {"error": "No valid rows found in file."}

    conn = get_conn()
    try:
        with conn:
            conn.execute("DELETE FROM honorverse_hyper")
            conn.executemany(
                "INSERT INTO honorverse_hyper (spectral_class, lm) VALUES (?, ?)",
                rows,
            )
    except Exception as e:
        return {"error": f"Database error: {e}"}

    return {"count": len(rows), "path": csv_path}


# ── Option 58: Gaia Catalogue of Nearby Stars (GCNS) ─────────────────────────
#
# Ingests the GCNS (Smart et al. 2021) into the isolated `gcns_stars` DB table
# as the astrometric/completeness backbone, with Bayesian distances + their
# uncertainties — data the SIMBAD-built star_systems table lacks. The SIMBAD
# identity layer (spectral type / common name / Johnson V) is attached by an
# exact-key cross-match against star_systems (Gaia source_id → 2MASS → name);
# never fabricated, never positionally guessed. See docs/star-databases.md.

_GCNS_TAP_URL          = "https://dc.g-vo.org/tap"
_GCNS_VERSION          = ("GCNS / Smart et al. 2021 A&A 649 A6 (VizieR J/A+A/649/A6) "
                          "via GAVO gcns.main + gcns.missing_10mas + gcns.resolvedss")
_GCNS_MAXREC           = 400_000   # must exceed the total row count AND the 20k default cap
_GCNS_MAIN_MIN_ROWS    = 330_000   # known 331,312 — floor sits just under to tolerate version drift
_GCNS_MISSING_MIN_ROWS = 1_200     # known 1,259
_GCNS_RESOLVED_MIN_ROWS = 19_000   # known 19,176 resolved pairs
_LY_PER_PC             = LY_PER_PC   # single-sourced from core.shared
_KPC_TO_PC             = 1000.0

_GCNS_MAIN_ADQL = """SELECT source_id, ra, dec, parallax, parallax_error,
       dist_16, dist_50, dist_84,
       phot_g_mean_mag, phot_bp_mean_mag, phot_rp_mean_mag,
       adoptedrv, wd_prob, gcns_prob, name_2mass
  FROM gcns.main"""

_GCNS_MISSING_ADQL = """SELECT main_id, otype, ra, dec, plx_value
  FROM gcns.missing_10mas"""

# gcns.resolvedss is PAIR-keyed: one row per resolved pair, no system identifier.
# source_id1/source_id2 are Gaia EDR3 source_ids; separation in arcsec, proj_sep
# in AU; bin = probable >2-star system; bound = probable gravitationally bound.
_GCNS_RESOLVED_ADQL = """SELECT source_id1, source_id2, separation, mag_diff,
       proj_sep, bin, bound
  FROM gcns.resolvedss"""


def _ni(v):
    """Coerce a TAP value to int, or None if missing/masked."""
    try:
        if v is None:
            return None
        return int(v)
    except (TypeError, ValueError):
        return None


def _norm_2mass(s: str) -> str:
    """Normalise a 2MASS designation to its bare coordinate core for joining.

    star_systems stores '2MASS J14294291-6240465'; GCNS name_2mass stores
    '14294291-6240465'. Strip the '2MASS'/'J' prefixes and whitespace so both
    forms compare equal.
    """
    if not s:
        return ""
    s = str(s).strip()
    if s.upper().startswith("2MASS"):
        s = s[5:].strip()
    if s[:1] in ("J", "j"):
        s = s[1:]
    return s.strip()


def _build_simbad_crossmatch():
    """Build exact-match lookup tables from star_systems for the SIMBAD layer.

    Returns (by_gaia, by_2mass, by_name) where each maps a key to a dict of
    {spectral_type, star_name, app_magnitude}. Keys:
      - by_gaia : int Gaia EDR3/DR3 source_id parsed from `designations`
                  (DR2 ids are deliberately excluded — they differ from EDR3/DR3)
      - by_2mass: normalised 2MASS core
      - by_name : exact star_name (used for missing_10mas rows)
    Empty dicts if star_systems is empty or carries no usable keys.
    """
    from core.db import get_conn

    by_gaia, by_2mass, by_name = {}, {}, {}
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT star_name, designations, spectral_type, app_magnitude "
            "FROM star_systems"
        ).fetchall()
    except Exception:
        return by_gaia, by_2mass, by_name

    gaia_re  = re.compile(r"Gaia\s+E?DR3\s+(\d+)")  # EDR3 or DR3 only — not DR2
    twomass_re = re.compile(r"2MASS\s+J?\s*([0-9+\-.]+)")

    for r in rows:
        sp   = (r["spectral_type"] or "").strip() or None
        name = (r["star_name"] or "").strip() or None
        vmag = _fval(r["app_magnitude"])
        payload = {"spectral_type": sp, "star_name": name, "app_magnitude": vmag}
        desig = r["designations"] or ""

        m = gaia_re.search(desig)
        if m:
            by_gaia.setdefault(int(m.group(1)), payload)
        tm = twomass_re.search(desig)
        if tm:
            by_2mass.setdefault(_norm_2mass(tm.group(1)), payload)
        if name:
            by_name.setdefault(name, payload)

    return by_gaia, by_2mass, by_name


def _gcns_fetch(adql: str, maxrec: int):
    """Run an async TAP query against GAVO; return the pyvo result set.

    Uses async (1 hr execution window) because the result far exceeds the 20k
    sync cap. Deletes the UWS job afterward. Wrapped in the shared retry/timeout
    helpers. Raises on exhausted retries (caller classifies the error).
    """
    import pyvo

    def _do():
        svc = pyvo.dal.TAPService(_GCNS_TAP_URL)
        job = svc.submit_job(adql, maxrec=maxrec)
        try:
            job.run()
            job.wait(phases={"COMPLETED", "ERROR", "ABORTED"}, timeout=3000.0)
            job.raise_if_error()
            return job.fetch_result()
        finally:
            try:
                job.delete()
            except Exception:
                pass

    with _timeout_ctx(300):
        return _with_retries(_do, retries=3, base_delay=5.0)


def _gcns_check_overflow(result, n_rows: int) -> bool:
    """True if the TAP result was truncated (server OVERFLOW or hit maxrec)."""
    try:
        status = str(getattr(result, "query_status", "") or "")
        if "overflow" in status.lower():
            return True
    except Exception:
        pass
    return n_rows >= _GCNS_MAXREC


def _gcns_build_systems(resolved_rows, gcns_star_ids):
    """Derive resolved systems from gcns.resolvedss pair rows.

    The source table has no system id — each row is a resolved PAIR
    (source_id1, source_id2). Systems are connected components over the pair
    graph (union-find). system_id is synthetic and deterministic: components are
    sorted by their smallest member source_id and numbered from 1.

    `gcns_star_ids` is the set of source_ids present in gcns_stars (i.e. the
    gcns.main ids), used to flag which members link to an existing gcns_stars row.

    Returns (systems_rows, members_rows, pair_rows, sid_info, n_multi,
    n_members_in_stars):
      - systems_rows: tuples for gcns_systems
      - members_rows: tuples for gcns_system_members
      - pair_rows:    tuples for gcns_system_pairs
      - sid_info:     {source_id: (system_id, n_components)} for gcns_stars enrich
      - n_multi:      systems with n_components > 2
      - n_members_in_stars: members whose source_id is in gcns_stars
    """
    from collections import defaultdict

    parent = {}

    def find(x):
        parent.setdefault(x, x)
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    pairs = []
    for row in resolved_rows:
        s1 = _ni(row["source_id1"])
        s2 = _ni(row["source_id2"])
        if s1 is None or s2 is None:
            continue
        union(s1, s2)
        pairs.append({
            "s1":   s1,
            "s2":   s2,
            "sep":  _fval(row["separation"]),
            "magd": _fval(row["mag_diff"]),
            "proj": _fval(row["proj_sep"]),
            "bin":  _ni(row["bin"]),
            "bound": _ni(row["bound"]),
        })

    # Group source_ids into connected components.
    comps = defaultdict(set)
    for x in list(parent):
        comps[find(x)].add(x)

    # Deterministic system_id: order components by smallest member id.
    comp_list = sorted(comps.values(), key=min)
    sid_to_sysid = {}
    n_components = {}
    for i, members in enumerate(comp_list, start=1):
        n_components[i] = len(members)
        for sid in members:
            sid_to_sysid[sid] = i

    # Members + per-system in-gcns_stars counts.
    members_rows = []
    sys_in_stars = defaultdict(int)
    n_members_in_stars = 0
    for sid, sysid in sid_to_sysid.items():
        in_stars = 1 if sid in gcns_star_ids else 0
        members_rows.append((sysid, sid, in_stars))
        sys_in_stars[sysid] += in_stars
        n_members_in_stars += in_stars

    # Pairs grouped per system for aggregates.
    pair_rows = []
    sys_pairs = defaultdict(list)
    for p in pairs:
        sysid = sid_to_sysid[p["s1"]]
        sys_pairs[sysid].append(p)
        pair_rows.append((sysid, p["s1"], p["s2"], p["sep"], p["magd"],
                          p["proj"], p["bin"], p["bound"]))

    systems_rows = []
    n_multi = 0
    for sysid in sorted(n_components):
        nc = n_components[sysid]
        if nc > 2:
            n_multi += 1
        ps = sys_pairs.get(sysid, [])
        projs  = [p["proj"]  for p in ps if p["proj"]  is not None]
        bins   = [p["bin"]   for p in ps if p["bin"]   is not None]
        bounds = [p["bound"] for p in ps if p["bound"] is not None]
        systems_rows.append((
            sysid,
            nc,
            len(ps),
            1 if any(b == 1 for b in bins) else 0,
            1 if any(b == 1 for b in bounds) else 0,
            1 if (bounds and all(b == 1 for b in bounds)) else 0,
            max(projs) if projs else None,
            min(projs) if projs else None,
            sys_in_stars[sysid],
        ))

    sid_info = {sid: (sysid, n_components[sysid]) for sid, sysid in sid_to_sysid.items()}
    return systems_rows, members_rows, pair_rows, sid_info, n_multi, n_members_in_stars


def compute_gcns_ingest(progress_callback=None) -> dict:
    """Pull the GCNS into the gcns_stars table (replace-in-place) with check gates.

    Flow (validate-before-destroy — a short/truncated download leaves the
    existing tables intact):
      1. async-fetch gcns.main, gcns.missing_10mas, and gcns.resolvedss into
         memory (one snapshot)
      2. Gate 1 (per table, BEFORE any DB write): fail on OVERFLOW or row count
         below the configured floor
      3. transform (kpc->pc, ly, SIMBAD cross-match) + derive resolved systems
         (connected components over the resolvedss pair graph)
      4. replace-in-place: DELETE + bulk INSERT of gcns_stars, gcns_systems,
         gcns_system_members, gcns_system_pairs in ONE transaction
      5. Gate 2 (post-commit): assert final counts meet floors; record provenance

    Returns a stats dict on success or {"error": str}.
    """
    from datetime import datetime
    from core.db import get_conn

    def _progress(msg):
        if progress_callback:
            progress_callback(msg)

    # ── 1. Fetch ────────────────────────────────────────────────────────────
    _progress("Querying GAVO TAP for gcns.main (331,312 rows; this takes a few minutes)…")
    try:
        main_res = _gcns_fetch(_GCNS_MAIN_ADQL, _GCNS_MAXREC)
    except Exception as e:
        return {"error": _network_error_msg(e, "GAVO TAP (gcns.main)")}
    main_rows = list(main_res)
    n_main = len(main_rows)
    _progress(f"gcns.main returned {n_main:,} rows.")

    # ── 2. Gate 1 (gcns.main) — before touching the DB ──────────────────────
    if _gcns_check_overflow(main_res, n_main):
        return {"error": ("gcns.main result was TRUNCATED (TAP OVERFLOW / hit "
                          f"maxrec={_GCNS_MAXREC:,}). Aborted before writing; "
                          "existing gcns_stars table left intact.")}
    if n_main < _GCNS_MAIN_MIN_ROWS:
        return {"error": (f"gcns.main returned only {n_main:,} rows (expected "
                          f">= {_GCNS_MAIN_MIN_ROWS:,}). Likely an incomplete "
                          "download; aborted before writing.")}

    _progress("Querying GAVO TAP for gcns.missing_10mas…")
    try:
        miss_res = _gcns_fetch(_GCNS_MISSING_ADQL, _GCNS_MAXREC)
    except Exception as e:
        return {"error": _network_error_msg(e, "GAVO TAP (gcns.missing_10mas)")}
    miss_rows = list(miss_res)
    n_miss = len(miss_rows)
    _progress(f"gcns.missing_10mas returned {n_miss:,} rows.")

    if _gcns_check_overflow(miss_res, n_miss):
        return {"error": ("gcns.missing_10mas result was TRUNCATED. Aborted "
                          "before writing; existing gcns_stars left intact.")}
    if n_miss < _GCNS_MISSING_MIN_ROWS:
        return {"error": (f"gcns.missing_10mas returned only {n_miss:,} rows "
                          f"(expected >= {_GCNS_MISSING_MIN_ROWS:,}); aborted "
                          "before writing.")}

    _progress("Querying GAVO TAP for gcns.resolvedss (resolved multiples)…")
    try:
        resolved_res = _gcns_fetch(_GCNS_RESOLVED_ADQL, _GCNS_MAXREC)
    except Exception as e:
        return {"error": _network_error_msg(e, "GAVO TAP (gcns.resolvedss)")}
    resolved_rows = list(resolved_res)
    n_resolved = len(resolved_rows)
    _progress(f"gcns.resolvedss returned {n_resolved:,} pairs.")

    if _gcns_check_overflow(resolved_res, n_resolved):
        return {"error": ("gcns.resolvedss result was TRUNCATED. Aborted before "
                          "writing; existing GCNS tables left intact.")}
    if n_resolved < _GCNS_RESOLVED_MIN_ROWS:
        return {"error": (f"gcns.resolvedss returned only {n_resolved:,} pairs "
                          f"(expected >= {_GCNS_RESOLVED_MIN_ROWS:,}); aborted "
                          "before writing.")}

    # ── 3. Transform + cross-match ──────────────────────────────────────────
    _progress("Cross-matching against star_systems (SIMBAD layer)…")
    by_gaia, by_2mass, by_name = _build_simbad_crossmatch()

    # Derive resolved systems (connected components over the resolvedss pairs).
    # Membership links by Gaia source_id; the in_gcns_stars flag is computed
    # against the gcns.main source_ids (missing_10mas rows have no source_id).
    _progress("Deriving resolved systems (connected components)…")
    main_source_ids = {sid for sid in (_ni(r["source_id"]) for r in main_rows)
                       if sid is not None}
    (systems_rows, members_rows, pair_rows, sid_info,
     n_multi, n_members_in_stars) = _gcns_build_systems(resolved_rows, main_source_ids)
    n_systems = len(systems_rows)

    matched = 0
    insert_rows = []

    for row in main_rows:
        sid   = _ni(row["source_id"])
        d50   = _fval(row["dist_50"])
        d16   = _fval(row["dist_16"])
        d84   = _fval(row["dist_84"])
        dist_pc    = d50 * _KPC_TO_PC if d50 is not None else None
        dist_lo_pc = d16 * _KPC_TO_PC if d16 is not None else None
        dist_hi_pc = d84 * _KPC_TO_PC if d84 is not None else None
        ly = dist_pc * _LY_PER_PC if dist_pc is not None else None

        sim = None
        if sid is not None and sid in by_gaia:
            sim = by_gaia[sid]
        else:
            key2 = _norm_2mass(row["name_2mass"])
            if key2 and key2 in by_2mass:
                sim = by_2mass[key2]
        if sim is not None:
            matched += 1

        info = sid_info.get(sid) if sid is not None else None
        system_id    = info[0] if info else None
        n_components = info[1] if info else None

        insert_rows.append((
            sid,
            _fval(row["ra"]), _fval(row["dec"]),
            _fval(row["parallax"]), _fval(row["parallax_error"]),
            dist_pc, dist_lo_pc, dist_hi_pc, ly,
            _fval(row["phot_g_mean_mag"]), _fval(row["phot_bp_mean_mag"]),
            _fval(row["phot_rp_mean_mag"]),
            _fval(row["adoptedrv"]), _fval(row["wd_prob"]), _fval(row["gcns_prob"]),
            sim["spectral_type"] if sim else None,
            sim["star_name"] if sim else None,
            sim["app_magnitude"] if sim else None,
            1,                       # in_gcns
            1 if sim else 0,         # in_simbad
            "gcns_bayesian",
            "main",
            system_id,
            n_components,
        ))

    # missing_10mas: parallax-only objects Gaia EDR3 missed — no source_id, no
    # Bayesian distance, no Gaia photometry. Distance via 1/plx inversion, flagged.
    for row in miss_rows:
        plx = _fval(row["plx_value"])
        dist_pc = (1000.0 / plx) if (plx and plx > 0) else None
        ly = dist_pc * _LY_PER_PC if dist_pc is not None else None
        main_id = (str(row["main_id"]).strip() if row["main_id"] is not None else None)

        sim = by_name.get(main_id) if main_id else None
        if sim is not None:
            matched += 1

        insert_rows.append((
            None,                                  # gaia_source_id
            _fval(row["ra"]), _fval(row["dec"]),
            plx, None,                             # parallax, parallax_error
            dist_pc, None, None, ly,               # dist_pc, lo, hi, ly
            None, None, None,                      # G, BP, RP
            None, None, None,                      # rv, wd_prob, astrom_reliable
            sim["spectral_type"] if sim else None,
            sim["star_name"] if sim else main_id,  # keep GCNS main_id as the name
            sim["app_magnitude"] if sim else None,
            1,                                     # in_gcns
            1 if sim else 0,                       # in_simbad
            "gcns_missing_plx_inversion",
            "missing_10mas",
            None,                                  # system_id (no source_id to join)
            None,                                  # n_components
        ))

    # ── 4. Replace-in-place (one transaction) ───────────────────────────────
    _progress(f"Writing {len(insert_rows):,} stars and {n_systems:,} resolved "
              "systems…")
    conn = get_conn()
    try:
        with conn:
            conn.execute("DELETE FROM gcns_stars")
            conn.execute("DELETE FROM gcns_systems")
            conn.execute("DELETE FROM gcns_system_members")
            conn.execute("DELETE FROM gcns_system_pairs")
            conn.executemany(
                """INSERT OR IGNORE INTO gcns_stars
                   (gaia_source_id, ra, dec, parallax, parallax_error,
                    dist_pc, dist_lo_pc, dist_hi_pc, light_years,
                    phot_g_mean_mag, phot_bp_mean_mag, phot_rp_mean_mag,
                    rv_kms, wd_prob, astrom_reliable_prob,
                    spectral_type, star_name, app_magnitude,
                    in_gcns, in_simbad, distance_method, gcns_table,
                    system_id, n_components)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                insert_rows,
            )
            conn.executemany(
                """INSERT INTO gcns_systems
                   (system_id, n_components, n_pairs, any_bin, any_bound,
                    all_bound, max_proj_sep_au, min_proj_sep_au, n_in_gcns_stars)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                systems_rows,
            )
            conn.executemany(
                """INSERT INTO gcns_system_members
                   (system_id, gaia_source_id, in_gcns_stars)
                   VALUES (?, ?, ?)""",
                members_rows,
            )
            conn.executemany(
                """INSERT INTO gcns_system_pairs
                   (system_id, source_id1, source_id2, separation_arcsec,
                    mag_diff, proj_sep_au, bin, bound)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                pair_rows,
            )
    except Exception as e:
        return {"error": f"Could not write GCNS tables: {e}"}

    # ── 5. Gate 2 (post-commit) + provenance ────────────────────────────────
    final = conn.execute("SELECT COUNT(*) FROM gcns_stars").fetchone()[0]
    if final < _GCNS_MAIN_MIN_ROWS:
        return {"error": (f"Post-commit check failed: gcns_stars holds {final:,} "
                          f"rows (expected >= {_GCNS_MAIN_MIN_ROWS:,}). The table "
                          "may be incomplete — investigate before relying on it.")}
    final_pairs = conn.execute("SELECT COUNT(*) FROM gcns_system_pairs").fetchone()[0]
    if final_pairs < _GCNS_RESOLVED_MIN_ROWS:
        return {"error": (f"Post-commit check failed: gcns_system_pairs holds "
                          f"{final_pairs:,} rows (expected >= "
                          f"{_GCNS_RESOLVED_MIN_ROWS:,}). The resolved-systems "
                          "tables may be incomplete — investigate before relying "
                          "on them.")}

    snapshot_date = datetime.now().strftime("%Y-%m-%d")
    meta = {
        "snapshot_date":         snapshot_date,
        "gcns_version":          _GCNS_VERSION,
        "gcns_main_count":       str(n_main),
        "gcns_missing_count":    str(n_miss),
        "total_count":           str(final),
        "simbad_matched":        str(matched),
        "gcns_resolved_pairs":   str(n_resolved),
        "gcns_systems_count":    str(n_systems),
        "gcns_systems_multi":    str(n_multi),
        "gcns_members_in_stars": str(n_members_in_stars),
    }
    with conn:
        conn.executemany(
            "INSERT OR REPLACE INTO gcns_meta (key, value) VALUES (?, ?)",
            list(meta.items()),
        )

    _progress(f"Done — {final:,} GCNS rows ({matched:,} SIMBAD-matched); "
              f"{n_systems:,} resolved systems ({n_multi:,} with >2 components).")
    return {
        "total_rows":       final,
        "main_count":       n_main,
        "missing_count":    n_miss,
        "simbad_matched":   matched,
        "resolved_pairs":   n_resolved,
        "systems_count":    n_systems,
        "systems_multi":    n_multi,
        "members_in_stars": n_members_in_stars,
        "snapshot_date":    snapshot_date,
        "gcns_version":     _GCNS_VERSION,
    }


def _gcns_meta_dict() -> dict:
    """Return the gcns_meta key/value pairs as a dict (empty if unbuilt)."""
    from core.db import get_conn
    conn = get_conn()
    try:
        rows = conn.execute("SELECT key, value FROM gcns_meta").fetchall()
        return {r["key"]: r["value"] for r in rows}
    except Exception:
        return {}


_GCNS_ROW_COLS = [
    "gaia_source_id", "ra", "dec", "parallax", "parallax_error",
    "dist_pc", "dist_lo_pc", "dist_hi_pc", "light_years",
    "phot_g_mean_mag", "phot_bp_mean_mag", "phot_rp_mean_mag",
    "rv_kms", "wd_prob", "astrom_reliable_prob",
    "spectral_type", "star_name", "app_magnitude",
    "in_gcns", "in_simbad", "distance_method", "gcns_table",
    "system_id", "n_components",
]


def _gcns_row_to_dict(row) -> dict:
    """Convert a gcns_stars DB row to the public JSON shape (snake_case keys)."""
    d = {c: row[c] for c in _GCNS_ROW_COLS}
    d["in_gcns"]   = bool(row["in_gcns"])
    d["in_simbad"] = bool(row["in_simbad"])
    return d


def compute_gcns_within_sol(limit_ly: float, wd_prob_min: float = None,
                            wd_prob_max: float = None) -> dict:
    """All GCNS stars within limit_ly light years of Sol (Bayesian distances).

    Reads the gcns_stars DB table only — no network. Returns
    {limit_ly, count, snapshot_date, gcns_version, stars[]} or {"error": str}.
    Each star carries heliocentric x/y/z (ly) for map parity with stars-within-sol.

    Optional white-dwarf census filter: ``wd_prob_min`` / ``wd_prob_max`` restrict
    to sources whose GCNS white-dwarf probability (``wd_prob``) falls in the given
    range (rows with NULL wd_prob are excluded once either bound is set). Both
    None → byte-identical to the unfiltered census. A min > max simply matches
    nothing (not an error), consistent with the other range filters.
    """
    import math as _math
    from core.db import get_conn

    if limit_ly is None or limit_ly <= 0:
        return {"error": "Distance limit must be greater than 0."}

    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM gcns_stars").fetchone()[0]
    except Exception as e:
        return {"error": f"Error reading gcns_stars table: {e}"}
    if total == 0:
        return {"error": "gcns_stars table is empty — run option 58 (Import GCNS Data) first."}

    where = ["light_years IS NOT NULL", "light_years <= ?"]
    params = [limit_ly]
    if wd_prob_min is not None:
        where.append("wd_prob IS NOT NULL AND wd_prob >= ?")
        params.append(wd_prob_min)
    if wd_prob_max is not None:
        where.append("wd_prob IS NOT NULL AND wd_prob <= ?")
        params.append(wd_prob_max)

    rows = conn.execute(
        f"SELECT {', '.join(_GCNS_ROW_COLS)} FROM gcns_stars "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY light_years ASC",
        tuple(params),
    ).fetchall()

    stars = []
    for row in rows:
        d = _gcns_row_to_dict(row)
        ra, dec, ly = row["ra"], row["dec"], row["light_years"]
        if ra is not None and dec is not None and ly is not None:
            rr, dr = _math.radians(ra), _math.radians(dec)
            d["x"] = ly * _math.cos(dr) * _math.cos(rr)
            d["y"] = ly * _math.cos(dr) * _math.sin(rr)
            d["z"] = ly * _math.sin(dr)
        else:
            d["x"] = d["y"] = d["z"] = None
        stars.append(d)

    meta = _gcns_meta_dict()
    return {
        "limit_ly":      limit_ly,
        "count":         len(stars),
        "snapshot_date": meta.get("snapshot_date"),
        "gcns_version":  meta.get("gcns_version"),
        "stars":         stars,
    }


def compute_gcns_by_source_id(source_id: int) -> dict:
    """Single GCNS row by Gaia EDR3/DR3 source_id (the join key). No network.

    Returns {snapshot_date, gcns_version, star} or {"error": str}.
    """
    from core.db import get_conn

    sid = _ni(source_id)
    if sid is None:
        return {"error": "source_id must be an integer Gaia EDR3/DR3 id."}

    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM gcns_stars").fetchone()[0]
    except Exception as e:
        return {"error": f"Error reading gcns_stars table: {e}"}
    if total == 0:
        return {"error": "gcns_stars table is empty — run option 58 (Import GCNS Data) first."}

    row = conn.execute(
        f"SELECT {', '.join(_GCNS_ROW_COLS)} FROM gcns_stars WHERE gaia_source_id = ?",
        (sid,),
    ).fetchone()
    if row is None:
        return {"error": f"No GCNS source found with source_id {sid}."}

    meta = _gcns_meta_dict()
    return {
        "snapshot_date": meta.get("snapshot_date"),
        "gcns_version":  meta.get("gcns_version"),
        "star":          _gcns_row_to_dict(row),
    }


def _gcns_bool(v):
    """0/1/None -> bool/None (membership/pair flags may be NULL)."""
    return bool(v) if v is not None else None


def compute_gcns_system(source_id: int) -> dict:
    """Resolved multiple-star system containing a Gaia source_id. No network.

    Looks up which derived resolved system (connected component of gcns.resolvedss
    pairs) the component belongs to, then returns the system record, every member's
    source_id with a thin summary joined from gcns_stars where available, and the
    raw pair edges. A source_id that is in no resolved system (a single/unresolved
    object) returns {"error": ...}.

    Returns {snapshot_date, gcns_version, query_source_id, system} or {"error": str}.
    """
    from core.db import get_conn

    sid = _ni(source_id)
    if sid is None:
        return {"error": "source_id must be an integer Gaia EDR3/DR3 id."}

    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM gcns_systems").fetchone()[0]
    except Exception as e:
        return {"error": f"Error reading gcns_systems table: {e}"}
    if total == 0:
        return {"error": "gcns_systems table is empty — run option 58 (Import GCNS Data) first."}

    mrow = conn.execute(
        "SELECT system_id FROM gcns_system_members WHERE gaia_source_id = ?",
        (sid,),
    ).fetchone()
    if mrow is None:
        return {"error": (f"Gaia source_id {sid} is not part of any GCNS resolved "
                          "system (single or unresolved object).")}
    sysid = mrow["system_id"]

    srow = conn.execute(
        """SELECT system_id, n_components, n_pairs, any_bin, any_bound, all_bound,
                  max_proj_sep_au, min_proj_sep_au, n_in_gcns_stars
           FROM gcns_systems WHERE system_id = ?""",
        (sysid,),
    ).fetchone()

    member_rows = conn.execute(
        "SELECT gaia_source_id, in_gcns_stars FROM gcns_system_members "
        "WHERE system_id = ? ORDER BY gaia_source_id",
        (sysid,),
    ).fetchall()
    # P2.3: one batched lookup instead of a per-member SELECT (N+1). Members not
    # present in gcns_stars (in_gcns_stars = 0) simply miss the dict → None fields,
    # matching the prior retained-member behavior. Ordering follows member_rows.
    msids = [m["gaia_source_id"] for m in member_rows]
    star_by_id = {}
    if msids:
        placeholders = ",".join("?" * len(msids))
        for star in conn.execute(
            "SELECT gaia_source_id, star_name, spectral_type, dist_pc, light_years "
            f"FROM gcns_stars WHERE gaia_source_id IN ({placeholders})",
            msids,
        ).fetchall():
            star_by_id[star["gaia_source_id"]] = star

    members = []
    for m in member_rows:
        msid = m["gaia_source_id"]
        star = star_by_id.get(msid)
        members.append({
            "gaia_source_id": msid,
            "in_gcns_stars":  _gcns_bool(m["in_gcns_stars"]),
            "is_query":       msid == sid,
            "star_name":      star["star_name"]     if star else None,
            "spectral_type":  star["spectral_type"] if star else None,
            "dist_pc":        star["dist_pc"]        if star else None,
            "light_years":    star["light_years"]    if star else None,
        })

    pairs = [{
        "source_id1":        p["source_id1"],
        "source_id2":        p["source_id2"],
        "separation_arcsec": p["separation_arcsec"],
        "mag_diff":          p["mag_diff"],
        "proj_sep_au":       p["proj_sep_au"],
        "bin":               _gcns_bool(p["bin"]),
        "bound":             _gcns_bool(p["bound"]),
    } for p in conn.execute(
        "SELECT source_id1, source_id2, separation_arcsec, mag_diff, proj_sep_au, "
        "bin, bound FROM gcns_system_pairs WHERE system_id = ? ORDER BY proj_sep_au",
        (sysid,),
    ).fetchall()]

    meta = _gcns_meta_dict()
    return {
        "snapshot_date":   meta.get("snapshot_date"),
        "gcns_version":    meta.get("gcns_version"),
        "query_source_id": sid,
        "system": {
            "system_id":       srow["system_id"],
            "n_components":    srow["n_components"],
            "n_pairs":         srow["n_pairs"],
            "any_bin":         _gcns_bool(srow["any_bin"]),
            "any_bound":       _gcns_bool(srow["any_bound"]),
            "all_bound":       _gcns_bool(srow["all_bound"]),
            "max_proj_sep_au": srow["max_proj_sep_au"],
            "min_proj_sep_au": srow["min_proj_sep_au"],
            "n_in_gcns_stars": srow["n_in_gcns_stars"],
            "members":         members,
            "pairs":           pairs,
        },
    }


# ── GCNS-backed pairwise calculators (distance / travel-time / within-star) ────
#
# GCNS-sourced versions of the SIMBAD-based calculators in core/calculators.py.
# Coordinates and Bayesian distances come from the gcns_stars table; the existing
# SIMBAD-based subcommands are left unchanged. _to_cartesian / _fmt_ra / _fmt_dec /
# format_travel_time / HOURS_PER_JULIAN_YEAR are imported lazily from core.calculators
# inside the function bodies (neither module imports the other at top level).

_GCNS_GAIA_ID_RE = re.compile(r"Gaia\s+E?DR3\s+(\d+)")  # EDR3 or DR3 only — same source_id


def _resolve_gcns_row(*, star=None, source_id=None) -> dict:
    """Resolve a star to a single gcns_stars row, by Gaia source_id or by name.

    Exactly one of `star` / `source_id` must be supplied.

    Resolution order:
      - source_id (offline): direct gcns_stars fetch by gaia_source_id. missing_10mas
        rows have NULL gaia_source_id and are therefore not addressable this way.
      - star (network): SIMBAD lookup → extract the Gaia EDR3/DR3 id from its
        designations → fetch by id. If SIMBAD itself errors, that error propagates.
        If the id is absent from gcns_stars, fall through to an exact star_name match
        (case-insensitive) — this is how missing_10mas rows (Alpha Cen A/B, …) resolve.

    Returns the bare _gcns_row_to_dict shape, or {"error": str}. Never falls back to
    the SIMBAD star_systems table; an unmatched star is an error, not a silent
    substitution.
    """
    from core.db import get_conn

    if (star is None) == (source_id is None):
        return {"error": "Supply exactly one of star or source_id."}

    # ── source_id path (offline) ──────────────────────────────────────────────
    if source_id is not None:
        r = compute_gcns_by_source_id(source_id)
        if "error" in r:
            return r
        return r["star"]

    # ── star path (network via SIMBAD) ────────────────────────────────────────
    simbad = compute_simbad_lookup(star)
    if "error" in simbad:
        return simbad  # network / no-match — fatal, do not fall back

    gaia_raw = (simbad.get("designations") or {}).get("Gaia EDR3")
    if gaia_raw:
        m = _GCNS_GAIA_ID_RE.search(str(gaia_raw))
        if m:
            r = compute_gcns_by_source_id(int(m.group(1)))
            if "error" not in r:
                return r["star"]
            # id not in gcns_stars — fall through to name match (do not propagate)

    # ── name fallback (missing_10mas and any id-miss) ─────────────────────────
    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM gcns_stars").fetchone()[0]
    except Exception as e:
        return {"error": f"Error reading gcns_stars table: {e}"}
    if total == 0:
        return {"error": "gcns_stars table is empty — run option 58 (Import GCNS Data) first."}

    rows = conn.execute(
        f"SELECT {', '.join(_GCNS_ROW_COLS)} FROM gcns_stars "
        "WHERE star_name = ? COLLATE NOCASE",
        (str(star).strip(),),
    ).fetchall()
    if len(rows) == 1:
        return _gcns_row_to_dict(rows[0])
    if len(rows) > 1:
        cands = []
        for row in rows:
            sid = row["gaia_source_id"]
            cands.append(str(sid) if sid is not None
                         else f"<missing_10mas: {row['star_name']}>")
        return {"error": (f"'{star}' is ambiguous in the GCNS catalog — matches "
                          f"{len(rows)} rows: {', '.join(cands)}. Query by --id instead.")}

    return {"error": (f"'{star}' is not in the GCNS catalog "
                      "(no Gaia EDR3 id or name match).")}


def _gcns_endpoint_xyz(row, label):
    """(_to_cartesian of a resolved GCNS row, or an error dict). Guards null coords."""
    from core.calculators import _to_cartesian

    ra, dec, ly = row.get("ra"), row.get("dec"), row.get("light_years")
    if ra is None or dec is None or ly is None:
        name = row.get("star_name") or row.get("gaia_source_id") or label
        return None, {"error": f"GCNS row for {name} has incomplete coordinates "
                               "(ra/dec/light_years); cannot compute a 3D position."}
    return _to_cartesian(ra, dec, ly), None


def _gcns_info_block(row):
    """A resolved GCNS row plus its sexagesimal ra_hms / dec_dms (mirrors *_info)."""
    from core.calculators import _fmt_ra, _fmt_dec

    info = dict(row)
    info["ra_hms"]  = _fmt_ra(row["ra"])
    info["dec_dms"] = _fmt_dec(row["dec"])
    return info


def compute_gcns_distance(star1=None, id1=None, star2=None, id2=None) -> dict:
    """3D Euclidean distance in light years between two GCNS stars.

    Each endpoint accepts a name (star1/star2, via SIMBAD) or a Gaia source_id
    (id1/id2, offline). Mirrors compute_distance_between_stars' output, plus the
    GCNS provenance fields in each endpoint info block and snapshot_date/gcns_version
    at top level.

    Returns {star1_info, star2_info, distance_ly, distance_au, snapshot_date,
    gcns_version} or {"error": str}.
    """
    s1 = _resolve_gcns_row(star=star1, source_id=id1)
    if "error" in s1:
        return s1
    s2 = _resolve_gcns_row(star=star2, source_id=id2)
    if "error" in s2:
        return s2

    xyz1, err = _gcns_endpoint_xyz(s1, "star1")
    if err:
        return err
    xyz2, err = _gcns_endpoint_xyz(s2, "star2")
    if err:
        return err

    (x1, y1, z1), (x2, y2, z2) = xyz1, xyz2
    distance_ly = math.sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)

    meta = _gcns_meta_dict()
    return {
        "star1_info":    _gcns_info_block(s1),
        "star2_info":    _gcns_info_block(s2),
        "distance_ly":   distance_ly,
        "distance_au":   distance_ly * 63241.077 if distance_ly < 0.5 else None,
        "snapshot_date": meta.get("snapshot_date"),
        "gcns_version":  meta.get("gcns_version"),
    }


def compute_gcns_travel_time(star1=None, id1=None, star2=None, id2=None,
                             ly_hr=None, times_c=None) -> dict:
    """GCNS-backed travel time between two stars. Supply exactly one of ly_hr/times_c.

    Distance comes from the GCNS census (see compute_gcns_distance); the velocity
    conversion and travel-time formatting mirror compute_travel_time_between_stars.

    Returns {origin_info, dest_info, distance_ly, ly_hr, times_c, total_hours,
    travel_time_str, snapshot_date, gcns_version} or {"error": str}.
    """
    from core.calculators import HOURS_PER_JULIAN_YEAR, format_travel_time

    if ly_hr is None and times_c is None:
        return {"error": "Must supply ly_hr or times_c."}
    if ly_hr is not None and times_c is not None:
        return {"error": "Supply only one of ly_hr or times_c."}

    s1 = _resolve_gcns_row(star=star1, source_id=id1)
    if "error" in s1:
        return s1
    s2 = _resolve_gcns_row(star=star2, source_id=id2)
    if "error" in s2:
        return s2

    xyz1, err = _gcns_endpoint_xyz(s1, "origin")
    if err:
        return err
    xyz2, err = _gcns_endpoint_xyz(s2, "destination")
    if err:
        return err

    (x1, y1, z1), (x2, y2, z2) = xyz1, xyz2
    distance_ly = math.sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)

    if ly_hr is not None:
        v_ly_hr   = ly_hr
        v_times_c = ly_hr * HOURS_PER_JULIAN_YEAR
    else:
        v_times_c = times_c
        v_ly_hr   = times_c / HOURS_PER_JULIAN_YEAR

    if v_ly_hr <= 0:
        return {"error": "Velocity must be greater than 0."}

    total_hours = distance_ly / v_ly_hr

    meta = _gcns_meta_dict()
    return {
        "origin_info":     _gcns_info_block(s1),
        "dest_info":       _gcns_info_block(s2),
        "distance_ly":     distance_ly,
        "ly_hr":           v_ly_hr,
        "times_c":         v_times_c,
        "total_hours":     total_hours,
        "travel_time_str": format_travel_time(total_hours),
        "snapshot_date":   meta.get("snapshot_date"),
        "gcns_version":    meta.get("gcns_version"),
    }


def compute_gcns_stars_within_star(star=None, source_id=None, limit_ly=None) -> dict:
    """All GCNS stars within limit_ly light years of a center star (Bayesian distances).

    The center is resolved by name (SIMBAD) or Gaia source_id (offline). The center
    itself is excluded precisely — by gaia_source_id when it has one, plus a Distance
    < 1e-9 exact-self skip for a missing_10mas center (no id) — so Gaia-resolved close
    companions remain in the results.

    A synthetic **Sol** row is appended when the centre lies within limit_ly of the
    origin — Gaia does not observe the Sun, so the catalogue has no row for it. It
    carries `in_gcns = False` and `distance_method = "synthetic_sol_origin"`.

    Returns {center, center_x, center_y, center_z, limit_ly, count, snapshot_date,
    gcns_version, stars[]} (each star = gcns-within-sol row shape + 'Distance') or
    {"error": str}.
    """
    from core.calculators import (_to_cartesian, _SOL_NAME, _SOL_SP_TYPE,
                                  _SOL_APP_MAG)
    from core.db import get_conn

    if limit_ly is None or limit_ly <= 0:
        return {"error": "Distance limit must be greater than 0."}

    center = _resolve_gcns_row(star=star, source_id=source_id)
    if "error" in center:
        return center

    center_xyz, err = _gcns_endpoint_xyz(center, "center")
    if err:
        return err
    cx, cy, cz = center_xyz
    center_ly  = center["light_years"]
    center_sid = center.get("gaia_source_id")

    conn = get_conn()
    # Radial pre-filter: 3D separation >= |radial difference|, so anything outside
    # [center_ly - limit, center_ly + limit] cannot be within limit_ly. Lossless.
    rows = conn.execute(
        f"SELECT {', '.join(_GCNS_ROW_COLS)} FROM gcns_stars "
        "WHERE light_years IS NOT NULL AND light_years BETWEEN ? AND ?",
        (center_ly - limit_ly, center_ly + limit_ly),
    ).fetchall()

    matches = []
    for row in rows:
        ra, dec, ly = row["ra"], row["dec"], row["light_years"]
        if ra is None or dec is None or ly is None:
            continue
        if center_sid is not None and row["gaia_source_id"] == center_sid:
            continue  # the center's own row (precise exclusion)
        x, y, z = _to_cartesian(ra, dec, ly)
        dist = math.sqrt((x - cx)**2 + (y - cy)**2 + (z - cz)**2)
        if dist < 1e-9:
            continue  # exact self (covers a no-id missing_10mas center)
        if dist <= limit_ly:
            d = _gcns_row_to_dict(row)
            d["x"], d["y"], d["z"] = x, y, z
            d["Distance"] = dist
            matches.append(d)

    # Gaia does not observe the Sun, so `gcns_stars` has no Sol row — synthesize one
    # at the origin, the same gap `compute_stars_within_distance_of_star` fills for
    # `star_systems` (see `core.calculators._sol_result_row`). It is flagged
    # `in_gcns = False` with `distance_method = "synthetic_sol_origin"` so a consumer
    # can never mistake it for catalogue astrometry.
    sol_dist = math.sqrt(cx * cx + cy * cy + cz * cz)
    if 1e-9 < sol_dist <= limit_ly:
        sol = {c: None for c in _GCNS_ROW_COLS}
        sol.update({
            "star_name":       _SOL_NAME,
            "spectral_type":   _SOL_SP_TYPE,
            "app_magnitude":   _SOL_APP_MAG,
            "dist_pc":         0.0,
            "light_years":     0.0,
            "in_gcns":         False,
            "in_simbad":       False,
            "distance_method": "synthetic_sol_origin",
            "x": 0.0, "y": 0.0, "z": 0.0,
            "Distance":        sol_dist,
        })
        matches.append(sol)

    matches.sort(key=lambda r: r["Distance"])

    center_out = dict(center)
    center_out["x"], center_out["y"], center_out["z"] = cx, cy, cz

    meta = _gcns_meta_dict()
    return {
        "center":        center_out,
        "center_x":      cx,
        "center_y":      cy,
        "center_z":      cz,
        "limit_ly":      limit_ly,
        "count":         len(matches),
        "snapshot_date": meta.get("snapshot_date"),
        "gcns_version":  meta.get("gcns_version"),
        "stars":         matches,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Phase G — Interactive search / filtering (GUI-only)
#
# Three filter functions backing the Search & Filter panels. star_systems and
# hwc are read directly from the local SQLite store (no network); exoplanets
# hits the live NASA pscomppars TAP endpoint. All three return a dict
# {count, capped, cap, stars[]} or {"error": str}.
# ═══════════════════════════════════════════════════════════════════════════

_SEARCH_CAP     = 500    # star_systems / hwc row cap
_EXO_SEARCH_CAP = 200    # NASA pscomppars row cap


def _range_clause(col, vmin, vmax, params, cast=False):
    """Append SQL >= / <= range predicates to *params*; return the clause list.

    cast=True wraps the (TEXT) column in CAST(... AS REAL) with a non-empty guard
    so a blank cell is excluded rather than treated as 0.0 (hwc stores all TEXT).
    """
    expr = f"CAST({col} AS REAL)" if cast else col
    guard = f"NULLIF({col}, '') IS NOT NULL AND " if cast else ""
    out = []
    if vmin is not None:
        out.append(f"({guard}{expr} >= ?)")
        params.append(vmin)
    if vmax is not None:
        out.append(f"({guard}{expr} <= ?)")
        params.append(vmax)
    return out


def search_star_systems(filters: dict) -> dict:
    """Filter the local star_systems table (Phase G1). No network.

    Filter keys (all optional): spectral_classes (list), spectral_refine (str),
    ly_min/ly_max, mag_min/mag_max (floats), designation_prefix (str).
    Returns {count, capped, cap, stars[]} sorted by light_years asc, capped at
    _SEARCH_CAP, or {"error": str} if the table is empty.
    """
    from core.db import get_conn

    f = filters or {}
    clauses, params = [], []

    sp, sp_params = spectral_where(
        "ss.spectral_type", f.get("spectral_classes"), f.get("spectral_refine", ""))
    if sp:
        clauses.append(sp)
        params.extend(sp_params)

    clauses += _range_clause("ss.light_years",   f.get("ly_min"),  f.get("ly_max"),  params)
    clauses += _range_clause("ss.app_magnitude", f.get("mag_min"), f.get("mag_max"), params)

    prefix = (f.get("designation_prefix") or "").strip()
    if prefix:
        esc = _escape_like(prefix)
        clauses.append(
            "(ss.star_name LIKE ? ESCAPE '\\' "
            "OR ss.designations LIKE ? ESCAPE '\\' "
            "OR ss.designations LIKE ? ESCAPE '\\')"
        )
        params += [f"{esc}%", f"{esc}%", f"%, {esc}%"]

    # Phase L4: an fe_h filter JOINs the Hypatia abundance cache (there is no JOIN
    # otherwise). An empty/unbuilt cache simply yields no matches for that filter.
    fe_h_min, fe_h_max = f.get("fe_h_min"), f.get("fe_h_max")
    join = ""
    if fe_h_min is not None or fe_h_max is not None:
        join = " JOIN hypatia_cache hc ON ss.star_name = hc.star_name"
        clauses += _range_clause("hc.fe_h", fe_h_min, fe_h_max, params)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        "SELECT ss.star_name, ss.designations, ss.spectral_type, ss.parallax, "
        "ss.parsecs, ss.light_years, ss.app_magnitude, ss.ra, ss.dec "
        "FROM star_systems ss"
        f"{join}{where} ORDER BY ss.light_years ASC LIMIT ?"
    )
    params.append(_SEARCH_CAP + 1)

    try:
        conn = get_conn()
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        # P2.5: the empty-table probe must be inside the guarded region so a
        # failure returns {"error"} per contract instead of raising.
        if not rows and conn.execute("SELECT COUNT(*) FROM star_systems").fetchone()[0] == 0:
            return {"error": "star_systems table is empty — run option 50 first to populate it."}
    except Exception as e:
        return {"error": f"Error reading star_systems table: {e}"}

    capped = len(rows) > _SEARCH_CAP
    if capped:
        rows = rows[:_SEARCH_CAP]
    return {"count": len(rows), "capped": capped, "cap": _SEARCH_CAP, "stars": rows}


def search_hwc(filters: dict) -> dict:
    """Filter the local hwc table (Phase G2). No network.

    hwc columns are all TEXT, so numeric predicates CAST to REAL with a non-empty
    guard (a blank cell must not match as 0). Filter keys (all optional): esi_min,
    habitable / habzone_con / habzone_opt (bool), mass_min/max (P_MASS),
    radius_min/max (P_RADIUS), temp_min/max (P_TEMP_EQUIL), spectral_classes /
    spectral_refine (S_TYPE), ly_max (S_DISTANCE pc * 3.26156). Sorted by ESI desc,
    capped at _SEARCH_CAP. Returns {count, capped, cap, stars[]} or {"error": str}.
    """
    from core.db import get_conn, table_exists

    if not table_exists("hwc"):
        return {"error": "hwc table is empty — run option 52 (Import HWC Data) first."}

    f = filters or {}
    clauses, params = [], []

    esi_min = f.get("esi_min")
    if esi_min is not None:
        clauses.append("(NULLIF(P_ESI,'') IS NOT NULL AND CAST(P_ESI AS REAL) >= ?)")
        params.append(esi_min)

    for key, col in [("habitable", "P_HABITABLE"),
                     ("habzone_con", "P_HABZONE_CON"),
                     ("habzone_opt", "P_HABZONE_OPT")]:
        if f.get(key):
            clauses.append(f"{col} = '1'")

    clauses += _range_clause("P_MASS",       f.get("mass_min"),   f.get("mass_max"),   params, cast=True)
    clauses += _range_clause("P_RADIUS",     f.get("radius_min"), f.get("radius_max"), params, cast=True)
    clauses += _range_clause("P_TEMP_EQUIL", f.get("temp_min"),   f.get("temp_max"),   params, cast=True)

    sp, sp_params = spectral_where("S_TYPE", f.get("spectral_classes"), f.get("spectral_refine", ""))
    if sp:
        clauses.append(sp)
        params.extend(sp_params)

    ly_max = f.get("ly_max")
    if ly_max is not None:
        clauses.append(
            f"(NULLIF(S_DISTANCE,'') IS NOT NULL AND CAST(S_DISTANCE AS REAL) * {_LY_PER_PC} <= ?)")
        params.append(ly_max)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        "SELECT P_NAME, P_ESI, P_HABITABLE, P_HABZONE_CON, P_HABZONE_OPT, "
        "P_MASS, P_RADIUS, P_TEMP_EQUIL, S_NAME, S_NAME_HD, S_NAME_HIP, "
        "S_TYPE, S_DISTANCE FROM hwc"
        f"{where} ORDER BY CAST(NULLIF(P_ESI,'') AS REAL) DESC LIMIT ?"
    )
    params.append(_SEARCH_CAP + 1)

    try:
        conn = get_conn()
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    except Exception as e:
        return {"error": f"Error reading hwc table: {e}"}

    capped = len(rows) > _SEARCH_CAP
    if capped:
        rows = rows[:_SEARCH_CAP]
    return {"count": len(rows), "capped": capped, "cap": _SEARCH_CAP, "stars": rows}


def search_exoplanets(filters: dict) -> dict:
    """Live NASA pscomppars search (Phase G3). Builds an ADQL WHERE from filters,
    caps at _EXO_SEARCH_CAP rows sorted by pl_orbsmax asc.

    Filter keys (all optional): pl_bmasse_min/max, pl_rade_min/max,
    pl_orbper_min/max, st_teff_min/max (floats), sy_dist_max (pc),
    discoverymethod (exact, 'Any' ignored), spectral_classes / spectral_refine
    (st_spectype). A set radius bound excludes null-radius rows (ADQL semantics).
    Returns {count, capped, cap, stars[]} or {"error": str}.
    """
    f = filters or {}
    parts = []

    def _rng(col, vmin, vmax):
        if vmin is not None:
            parts.append(f"{col} >= {float(vmin)}")
        if vmax is not None:
            parts.append(f"{col} <= {float(vmax)}")

    try:
        _rng("pl_bmasse", f.get("pl_bmasse_min"), f.get("pl_bmasse_max"))
        _rng("pl_rade",   f.get("pl_rade_min"),   f.get("pl_rade_max"))
        _rng("pl_orbper", f.get("pl_orbper_min"), f.get("pl_orbper_max"))
        _rng("st_teff",   f.get("st_teff_min"),   f.get("st_teff_max"))
        if f.get("sy_dist_max") is not None:
            parts.append(f"sy_dist <= {float(f['sy_dist_max'])}")
    except (TypeError, ValueError):
        return {"error": "Numeric filters must be numbers."}

    method = (f.get("discoverymethod") or "").strip()
    if method and method.lower() != "any":
        parts.append(f"discoverymethod = '{method.replace(chr(39), chr(39) * 2)}'")

    sp = spectral_adql("st_spectype", f.get("spectral_classes"), f.get("spectral_refine", ""))
    if sp:
        parts.append(sp)

    where = " AND ".join(parts) if parts else "pl_name IS NOT NULL"
    select = ("pl_name, hostname, pl_bmasse, pl_rade, pl_orbper, pl_orbsmax, "
              "st_spectype, discoverymethod, st_teff, sy_dist")

    try:
        # Fetch cap+1 so an exact-cap match isn't misreported as "cap reached"
        # (mirrors search_star_systems / search_hwc).
        rows = _query_tap("pscomppars", where, order_by="pl_orbsmax",
                          top=_EXO_SEARCH_CAP + 1, select=select)
    except Exception as e:
        return {"error": _network_error_msg(e, "NASA Exoplanet Archive")}

    rows = rows or []
    capped = len(rows) > _EXO_SEARCH_CAP
    if capped:
        rows = rows[:_EXO_SEARCH_CAP]
    return {"count": len(rows), "capped": capped, "cap": _EXO_SEARCH_CAP, "stars": rows}


def search_hypatia_cache(filters: dict) -> dict:
    """Filter the local Hypatia abundance cache (Phase L4). No network.

    Filter keys (all optional): fe_h_min/fe_h_max, teff_min/teff_max, ly_max
    (light_years), disk (exact match), and element + element_min/element_max (an
    EXISTS subquery on hypatia_abundance for that species' [X/H] mean). Sorted by
    fe_h DESC (NULL fe_h last), capped at _SEARCH_CAP. Returns
    {count, capped, cap, stars[]} or {"error": str}. Each star carries the cache
    columns plus pivoted mg_h / si_h / o_h convenience values.
    """
    from core.db import get_conn, table_exists

    if not table_exists("hypatia_cache"):
        return {"error": "hypatia_cache table is empty — run the Import Hypatia Cache utility first."}

    f = filters or {}
    clauses, params = [], []

    clauses += _range_clause("fe_h", f.get("fe_h_min"), f.get("fe_h_max"), params)
    clauses += _range_clause("teff", f.get("teff_min"), f.get("teff_max"), params)

    ly_max = f.get("ly_max")
    if ly_max is not None:
        clauses.append("(light_years IS NOT NULL AND light_years <= ?)")
        params.append(ly_max)

    disk = f.get("disk")
    if disk is not None and str(disk).strip() != "":
        clauses.append("disk = ?")
        params.append(str(disk).strip())

    element = (f.get("element") or "").strip()
    if element:
        sub, subp = ["a.star_name = hc.star_name", "a.element = ?"], [element]
        if f.get("element_min") is not None:
            sub.append("a.mean >= ?"); subp.append(f.get("element_min"))
        if f.get("element_max") is not None:
            sub.append("a.mean <= ?"); subp.append(f.get("element_max"))
        clauses.append(
            "EXISTS (SELECT 1 FROM hypatia_abundance a WHERE " + " AND ".join(sub) + ")")
        params.extend(subp)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        "SELECT hc.star_name, hc.hip, hc.hd, hc.teff, hc.logg, hc.vmag, hc.bv, "
        "hc.distance_pc, hc.disk, hc.fe_h, hc.light_years, "
        "(SELECT mean FROM hypatia_abundance WHERE star_name = hc.star_name AND element = 'Mg') AS mg_h, "
        "(SELECT mean FROM hypatia_abundance WHERE star_name = hc.star_name AND element = 'Si') AS si_h, "
        "(SELECT mean FROM hypatia_abundance WHERE star_name = hc.star_name AND element = 'O')  AS o_h "
        "FROM hypatia_cache hc"
        f"{where} ORDER BY hc.fe_h IS NULL, hc.fe_h DESC LIMIT ?"
    )
    params.append(_SEARCH_CAP + 1)

    try:
        conn = get_conn()
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    except Exception as e:
        return {"error": f"Error reading hypatia_cache table: {e}"}

    if not rows and conn.execute("SELECT COUNT(*) FROM hypatia_cache").fetchone()[0] == 0:
        return {"error": "hypatia_cache table is empty — run the Import Hypatia Cache utility first."}

    capped = len(rows) > _SEARCH_CAP
    if capped:
        rows = rows[:_SEARCH_CAP]
    return {"count": len(rows), "capped": capped, "cap": _SEARCH_CAP, "stars": rows}


# ── Phase T1c · census-filter presets (solar analogs / substellar) ───────────
# Convenience presets over the existing census tables. Each carries its
# population/completeness caveat as a JSON field (the consumer reads JSON, not
# docs, at query time). No new datasets; self-validating (Phase-H/P).

_SUN_TEFF = 5772.0   # IAU nominal solar effective temperature (K)
_SUN_LOGG = 4.44     # solar surface gravity (log g, cgs)
_SUN_FEH  = 0.0      # solar [Fe/H] (Lodders 2009 zero-point)

# Tolerance boxes around the solar values: tight "twin" vs looser "analog".
_SOLAR_ANALOG_PRESETS = {
    "twin":   {"teff": 100.0, "logg": 0.1, "feh": 0.1},
    "analog": {"teff": 500.0, "logg": 0.4, "feh": 0.3},
}

_SOLAR_POP_NOTE = ("Solar analogs are drawn from the ~14k Hypatia-cached stars (those with "
                   "measured abundances); this is not a complete solar-neighbourhood census.")

_SUBSTELLAR_NOTE = ("GCNS (Gaia-only) substellar completeness falls off beyond ~10–25 pc; "
                    "L/T/Y dwarfs are too faint for Gaia farther out, and only "
                    "SIMBAD-cross-matched rows carry a spectral type — this list is a lower bound.")


def _attach_gcns_distance(conn, rows):
    """Best-effort attach a GCNS Bayesian distance (dist_pc_gcns) to hypatia rows.

    Cross-match chain: hypatia_cache.star_name → star_systems.designations →
    Gaia EDR3/DR3 id (via _GCNS_GAIA_ID_RE) → gcns_stars.dist_pc. Sets
    dist_pc_gcns=None wherever any hop breaks; returns the number matched. Lossy by
    design (it only resolves where star_systems carries a Gaia id for that name).
    """
    from core.db import table_exists
    for r in rows:
        r["dist_pc_gcns"] = None
    names = [r["star_name"] for r in rows if r.get("star_name")]
    if not names or not table_exists("star_systems") or not table_exists("gcns_stars"):
        return 0

    qmarks = ",".join("?" * len(names))
    try:
        desig = {row["star_name"]: row["designations"] for row in conn.execute(
            f"SELECT star_name, designations FROM star_systems WHERE star_name IN ({qmarks})", names)}
    except Exception:
        return 0

    name_to_gid, gids = {}, set()
    for name, d in desig.items():
        if not d:
            continue
        m = _GCNS_GAIA_ID_RE.search(str(d))
        if m:
            gid = int(m.group(1))
            name_to_gid[name] = gid
            gids.add(gid)
    if not gids:
        return 0

    gid_list = list(gids)
    gq = ",".join("?" * len(gid_list))
    try:
        gid_to_dist = {row["gaia_source_id"]: row["dist_pc"] for row in conn.execute(
            f"SELECT gaia_source_id, dist_pc FROM gcns_stars WHERE gaia_source_id IN ({gq})", gid_list)}
    except Exception:
        return 0

    matched = 0
    for r in rows:
        gid = name_to_gid.get(r.get("star_name"))
        if gid is not None and gid in gid_to_dist:
            r["dist_pc_gcns"] = gid_to_dist[gid]
            matched += 1
    return matched


def compute_solar_analogs(mode="twin", teff_tol=None, logg_tol=None, feh_tol=None,
                          ly_max=None, gcns_distance=False) -> dict:
    """Solar twins/analogs from the Hypatia cache by a tolerance box (Phase T1c E2).

    Filters hypatia_cache around the solar values (Teff 5772 K, log g 4.44, [Fe/H] 0);
    `mode="twin"` is a tight box (±100/±0.1/±0.1), `mode="analog"` a looser one
    (±500/±0.4/±0.3); any explicit *_tol overrides that axis. `ly_max` filters
    light_years; `gcns_distance=True` best-effort attaches a GCNS Bayesian distance.

    Returns {mode, criteria, population, count, capped, cap, stars[]} or {"error": str}.
    The `population` block (source + size + caveat note) is mandatory so a short list
    is never read as a complete census (Hypatia-cache-limited to ~14k abundance stars).
    """
    from core.db import get_conn, table_exists

    if mode not in _SOLAR_ANALOG_PRESETS:
        return {"error": f"Unknown mode '{mode}' (expected 'twin' or 'analog')."}
    if not table_exists("hypatia_cache"):
        return {"error": "hypatia_cache table is empty — run the Import Hypatia Cache utility first."}

    preset = _SOLAR_ANALOG_PRESETS[mode]
    tt = preset["teff"] if teff_tol is None else teff_tol
    lt = preset["logg"] if logg_tol is None else logg_tol
    ft = preset["feh"]  if feh_tol  is None else feh_tol
    for label, val in (("teff_tol", tt), ("logg_tol", lt), ("feh_tol", ft)):
        if val <= 0:
            return {"error": f"{label} must be positive."}
    if ly_max is not None and ly_max <= 0:
        return {"error": "ly_max must be positive."}

    clauses, params = [], []
    clauses += _range_clause("teff", _SUN_TEFF - tt, _SUN_TEFF + tt, params)
    clauses += _range_clause("logg", _SUN_LOGG - lt, _SUN_LOGG + lt, params)
    clauses += _range_clause("fe_h", _SUN_FEH - ft, _SUN_FEH + ft, params)
    if ly_max is not None:
        clauses.append("(light_years IS NOT NULL AND light_years <= ?)")
        params.append(ly_max)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        "SELECT hc.star_name, hc.hip, hc.hd, hc.teff, hc.logg, hc.vmag, hc.bv, "
        "hc.distance_pc, hc.disk, hc.fe_h, hc.light_years, "
        "(SELECT mean FROM hypatia_abundance WHERE star_name = hc.star_name AND element = 'Mg') AS mg_h, "
        "(SELECT mean FROM hypatia_abundance WHERE star_name = hc.star_name AND element = 'Si') AS si_h, "
        "(SELECT mean FROM hypatia_abundance WHERE star_name = hc.star_name AND element = 'O')  AS o_h "
        "FROM hypatia_cache hc"
        f"{where} ORDER BY hc.fe_h IS NULL, hc.fe_h DESC LIMIT ?"
    )
    params.append(_SEARCH_CAP + 1)

    try:
        conn = get_conn()
        total = conn.execute("SELECT COUNT(*) FROM hypatia_cache").fetchone()[0]
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    except Exception as e:
        return {"error": f"Error reading hypatia_cache table: {e}"}
    if total == 0:
        return {"error": "hypatia_cache table is empty — run the Import Hypatia Cache utility first."}

    capped = len(rows) > _SEARCH_CAP
    if capped:
        rows = rows[:_SEARCH_CAP]

    gcns_matched = _attach_gcns_distance(conn, rows) if gcns_distance else None

    return {
        "mode": mode,
        "criteria": {
            "teff_center": _SUN_TEFF, "teff_tol": tt,
            "logg_center": _SUN_LOGG, "logg_tol": lt,
            "feh_center":  _SUN_FEH,  "feh_tol":  ft,
            "ly_max": ly_max,
        },
        "population": {
            "source": "hypatia_cache",
            "total_in_cache": total,
            "returned": len(rows),
            "gcns_distance_matched": gcns_matched,
            "note": _SOLAR_POP_NOTE,
        },
        "count": len(rows),
        "capped": capped,
        "cap": _SEARCH_CAP,
        "stars": rows,
    }


def compute_substellar_census(ly_max=None, include_late_m=False, classes=None) -> dict:
    """Substellar (L/T/Y) census from gcns_stars by spectral-type prefix (Phase T1c E3).

    Selects gcns_stars whose SIMBAD-cross-matched `spectral_type` begins with one of
    the substellar classes (default L/T/Y; `include_late_m` adds M7/M8/M9; `classes`
    overrides). `ly_max` filters light_years. Sorted by light_years; capped at
    _SEARCH_CAP. Returns {classes, ly_max, count, capped, cap, completeness_note,
    population, snapshot_date, gcns_version, stars[]} or {"error": str}.

    The `completeness_note` is mandatory: GCNS substellar completeness falls off
    beyond ~10–25 pc and only cross-matched rows carry a spectral type, so the result
    is an explicit lower bound (never read a short list as complete).
    """
    from core.db import get_conn

    if ly_max is not None and ly_max <= 0:
        return {"error": "ly_max must be positive."}

    if classes:
        prefixes = [str(c).strip().upper() for c in classes if str(c).strip()]
    else:
        prefixes = ["L", "T", "Y"]
    if include_late_m:
        prefixes = prefixes + ["M7", "M8", "M9"]
    if not prefixes:
        return {"error": "No spectral classes given."}
    # A class token is concatenated into a GLOB pattern below, and SQLite's GLOB has
    # no ESCAPE clause — so `--classes '*'` would expand to GLOB '*' and match every
    # typed row, returning arbitrary G/K/M stars dressed as a substellar census.
    # Restrict to real class tokens (letter + optional subtype, e.g. L, T, M7, M7.5).
    bad = [p for p in prefixes if not re.fullmatch(r"[A-Z][0-9]*(?:\.[0-9]+)?", p)]
    if bad:
        return {"error": "Invalid spectral class "
                         + ", ".join(repr(b) for b in bad)
                         + " — expected a class letter with an optional subtype "
                           "(e.g. L, T, Y, M7, M7.5)."}

    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM gcns_stars").fetchone()[0]
    except Exception as e:
        return {"error": f"Error reading gcns_stars table: {e}"}
    if total == 0:
        return {"error": "gcns_stars table is empty — run option 58 (Import GCNS Data) first."}

    # Case-sensitive GLOB, not LIKE: SQLite's LIKE is case-INSENSITIVE for ASCII, so
    # `--classes D` under LIKE returned 4,918 rows = 2,561 real white dwarfs (D*)
    # FUSED WITH 2,357 lowercase-d M dwarfs (dM6, dM4.0 …). GLOB keeps them apart.
    # Each requested class is also matched under the `_SP_CLASS_PREFIXES` luminosity
    # prefixes, so `--classes L` now finds sdL0/esdL7 and `--include-late-m` finds
    # dM7/sdM7.0 (73 rows the prefix-blind form silently missed).
    or_parts, params = [], []
    for pfx in prefixes:
        for sp in _SP_CLASS_PREFIXES:
            or_parts.append("spectral_type GLOB ?")
            params.append(f"{sp}{pfx}*")
    clauses = ["spectral_type IS NOT NULL", "(" + " OR ".join(or_parts) + ")"]
    if ly_max is not None:
        clauses.append("(light_years IS NOT NULL AND light_years <= ?)")
        params.append(ly_max)
    where = " WHERE " + " AND ".join(clauses)

    rows = conn.execute(
        f"SELECT {', '.join(_GCNS_ROW_COLS)} FROM gcns_stars{where} "
        "ORDER BY light_years IS NULL, light_years ASC LIMIT ?",
        tuple(params + [_SEARCH_CAP + 1]),
    ).fetchall()
    stars = [_gcns_row_to_dict(r) for r in rows]
    capped = len(stars) > _SEARCH_CAP
    if capped:
        stars = stars[:_SEARCH_CAP]

    with_type = conn.execute(
        "SELECT COUNT(*) FROM gcns_stars WHERE spectral_type IS NOT NULL").fetchone()[0]
    meta = _gcns_meta_dict()
    return {
        "classes": prefixes,
        "ly_max": ly_max,
        "count": len(stars),
        "capped": capped,
        "cap": _SEARCH_CAP,
        "completeness_note": _SUBSTELLAR_NOTE,
        "population": {
            "total_in_gcns": total,
            "with_spectral_type": with_type,
            "returned": len(stars),
        },
        "snapshot_date": meta.get("snapshot_date"),
        "gcns_version": meta.get("gcns_version"),
        "stars": stars,
    }


# ── Star comparison (Phase L1) ───────────────────────────────────────────────

def _sun_hypatia_baseline() -> dict:
    """The Sun's Hypatia-shaped reference block (no network).

    Under the Lodders (2009) solar normalisation Hypatia uses, every [X/H]_sun ≡ 0
    by definition, so the Sun is the natural zero-point baseline; the synthetic
    abundance rows carry n=0 (no catalog) to mark them as the reference rather than
    measurements. U/V/W are heliocentric galactic space velocities, so the Sun (the
    frame origin) has U/V/W ≡ 0 — the same "Sun = reference" basis as [X/H] ≡ 0 and
    distance ≡ 0. Shared by the L1 Sun comparison entry and the Phase Q Sol dossier
    so the baseline can't drift between them.
    """
    from core.hypatia_elements import HYPATIA_SPECIES

    abundances = [{
        "element": s["symbol"], "name": s["name"], "z": s["z"],
        "category": s["category"], "mean": 0.0, "std": 0.0,
        "min": 0.0, "max": 0.0, "n": 0,
    } for s in HYPATIA_SPECIES]
    return {
        "star_name": "Sun",
        "properties": {"logg": 4.44, "disk": "thin disk",
                       "u_vel": 0.0, "v_vel": 0.0, "w_vel": 0.0},
        "abundances": abundances,
    }


def _sol_compare_entry() -> dict:
    """Reference-constant comparison entry for the Sun.

    The Sun is not a SIMBAD catalog object — "Sol"/"Sun" don't resolve — so its
    textbook values are injected directly. The Hypatia block is the shared solar
    zero-point baseline (_sun_hypatia_baseline).
    """
    from core.equations import compute_habitable_zone

    zmap = {z["key"]: z["au"] for z in compute_habitable_zone(5778.0, 1.0)}
    return {
        "name": "Sun", "sp_type": "G2V", "teff": 5778.0, "luminosity": 1.0,
        "mass": 1.0, "radius": 1.0,
        "hz_inner_au": zmap.get("rg"), "hz_outer_au": zmap.get("mg"),
        "ly": 0.0, "app_magnitude": -26.74,
        "hypatia": _sun_hypatia_baseline(),
        "error": None,
    }


def compare_stars(names: list) -> dict:
    """Side-by-side comparison of 2–4 stars.

    Per star: a SIMBAD lookup, an optional NASA pscomppars supplement to fill
    radius / mass / (teff/lum) that SIMBAD lacks, computed conservative HZ
    inner/outer bounds, and Hypatia Catalog data. **Per-star failures are
    isolated** — each star carries its own "error" key (None on success) and
    missing numeric fields are None; the only top-level error is the arg-count
    check. Reuses compute_simbad_lookup / compute_hypatia_data / the archive
    helpers / equations.compute_habitable_zone verbatim.

    Returns {"stars": [ {name, sp_type, teff, luminosity, mass, radius,
    hz_inner_au, hz_outer_au, ly, app_magnitude, hypatia, error}, ... ]}
    or {"error": str}.
    """
    from core.equations import compute_habitable_zone

    if not names or len([n for n in names if (n or "").strip()]) < 2:
        return {"error": "Enter at least 2 stars to compare."}
    if len(names) > 4:
        return {"error": "A maximum of 4 stars can be compared at once."}

    stars = []
    for raw in names:
        name = (raw or "").strip()
        entry = {
            "name": name, "sp_type": None, "teff": None, "luminosity": None,
            "mass": None, "radius": None, "hz_inner_au": None, "hz_outer_au": None,
            "ly": None, "app_magnitude": None, "hypatia": None, "error": None,
        }
        if not name:
            entry["error"] = "Empty star name."
            stars.append(entry)
            continue

        if name.lower() in ("sol", "sun"):
            stars.append(_sol_compare_entry())
            continue

        sl = compute_simbad_lookup(name)
        if isinstance(sl, dict) and "error" in sl:
            entry["error"] = sl["error"]
            stars.append(entry)
            continue

        entry["name"]          = sl.get("main_id") or name
        entry["sp_type"]       = sl.get("sp_type")
        entry["ly"]            = sl.get("ly")
        entry["app_magnitude"] = sl.get("vmag")

        teff   = _fval(sl.get("teff"))
        radius = None
        mass   = None
        lum    = None

        # NASA pscomppars supplement: SIMBAD never carries radius/mass, so fetch
        # them (and teff/lum if missing). Best-effort — never fatal.
        field, value = _get_archive_query_params(sl.get("designations", {}))
        if field and value:
            try:
                rows = _query_tap("pscomppars", f"{field}='{_adql_quote(value)}'",
                                  order_by="pl_orbsmax", top=1,
                                  select="st_teff,st_rad,st_mass,st_lum")
                if rows:
                    row = rows[0]
                    if teff is None:
                        teff = _fval(row.get("st_teff"))
                    radius = _fval(row.get("st_rad"))
                    mass   = _fval(row.get("st_mass"))
                    st_lum = _fval(row.get("st_lum"))
                    if st_lum is not None:
                        lum = 10 ** st_lum            # archive st_lum is log10(L/Lsun)
            except Exception:
                pass

        # Photometric fallback: NASA pscomppars only carries planet-HOST stars, so
        # most stars miss it. Derive mass/radius/luminosity from V mag + parallax +
        # teff + bolometric correction — the same method as the Star System Regions
        # feature — which works for any main-sequence star.
        if radius is None or mass is None:
            try:
                from core.regions import compute_star_system_regions_from_simbad
                reg = compute_star_system_regions_from_simbad(sl)
                if isinstance(reg, dict) and "error" not in reg:
                    if mass is None:
                        mass = reg.get("stellarMass")
                    if radius is None:
                        radius = reg.get("stellarRadius")
                    if lum is None:
                        lum = reg.get("bcLuminosity")
            except Exception:
                pass

        # Luminosity: prefer radius²·(teff/5778)⁴; else the archive/regions value.
        if radius is not None and teff is not None:
            lum = radius ** 2 * (teff / 5778.0) ** 4

        entry["teff"]       = teff
        entry["radius"]     = radius
        entry["mass"]       = mass
        entry["luminosity"] = lum

        # Conservative HZ inner (Runaway Greenhouse 'rg') / outer (Max Greenhouse 'mg').
        if teff is not None and lum is not None and lum > 0:
            try:
                zmap = {z["key"]: z["au"] for z in compute_habitable_zone(teff, lum)}
                entry["hz_inner_au"] = zmap.get("rg")
                entry["hz_outer_au"] = zmap.get("mg")
            except Exception:
                pass

        # Hypatia (per-star, non-fatal).
        try:
            entry["hypatia"] = compute_hypatia_data(sl)
        except Exception as e:
            entry["hypatia"] = {"error": str(e)}

        stars.append(entry)

    return {"stars": stars}
