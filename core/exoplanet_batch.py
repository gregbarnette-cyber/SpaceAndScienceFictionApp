"""core/exoplanet_batch.py — CR-8: batch NASA Exoplanet Archive Planetary Systems pull (LIVE network).

One invocation → the full per-planet + per-system field set for **many hosts at once** — the deep
orbital architecture (per-planet inclination + eccentricity, with meaningful nulls and per-value
provenance) that ``planetary-systems --star`` returns only one host at a time. Backs the sibling
worldbuilding repo's ``star_analysis`` 171-card audit.

**Built on the NASA ``ps`` (Planetary Systems) table — NOT ``pscomppars``.** This is the load-bearing
choice and it is *why* CR-8 is satisfiable at all:
  - ``default_flag``            → ``--solution-scope default|all`` (default = the preferred solution)
  - ``pl_refname`` / ``st_refname`` (per-solution reflinks) → the per-value **provenance** CR §4/§5.4 requires
  - ``ps`` preserves the genuine **null / 0 per solution** → un-fabricated ``null`` inclination (RV-only hosts),
    and a reported ``0`` eccentricity (fixed-circular) distinguishable from an unmeasured ``null``.
``pscomppars`` (what single-host ``planetary-systems`` uses) blends solutions and back-fills nulls across
them, so it can do none of the three. The FULFILLED single-host path is left byte-identical — this is a
separate reader.

Two selection modes, identical record shape:
  - **Mode A (host list):** each host resolved through SIMBAD first (``compute_simbad_lookup`` — the project's
    identity authority), then the archive round-trips are batched by name-column ``IN (...)`` lists.
  - **Mode B (filter):** a property/ADQL selection over ``ps``, grouped by hostname.

Contract: ``scifiWorldBuilding-Claude/.../spaceapp-change-request-CR8-batch-exoplanet-archive-pull.md``.
Failure → the app-wide ``{"error", route_tried}`` shape (``shared._route_error``). See
``PHASE_CR8_PLAN.md`` and ``docs/integration.md``.
"""

import re

from core.databases import (_query_tap, compute_simbad_lookup, _adql_quote,
                            compute_oec, oec_statuses, oec_fv, _norm_oec_name)
from core.shared import _network_error_msg, _route_error, spectral_adql

_ROUTE = ["nasa-tap:ps"]
_TABLE = "ps"
_IN_CHUNK = 100          # max name-values per IN(...) list (TAP GET URL-length guard; build item §8.2)

# ── column sets (verified live against ps / TAP_SCHEMA, 2026-08-16) ───────────────────────────────
_HOST_CORE_COLS = [
    "hostname", "st_spectype", "st_teff", "st_mass", "st_rad", "st_met", "sy_dist",
    "sy_vmag", "sy_kmag", "sy_gaiamag", "sy_pnum", "st_refname",
    "hd_name", "hip_name", "tic_id", "gaia_dr3_id",
]
_PLANET_CORE_COLS = [
    "pl_name", "discoverymethod", "pl_orbper", "pl_orbsmax", "pl_orbincl",
    "pl_orbeccen", "pl_orblper", "pl_bmasse", "pl_bmassj", "pl_bmassprov",
    "pl_rade", "tran_flag", "pl_refname",
]
# ── CR-9 Tier-1 disposition / quality (per-planet, all ps) — added to the core SELECT ────────────
# The 10 detection-method flags (tran_flag is already in _PLANET_CORE_COLS; the others are added below).
_DETECTION_FLAG_COLS = ("tran_flag", "rv_flag", "ima_flag", "ast_flag", "micro_flag",
                        "obm_flag", "etv_flag", "ptv_flag", "pul_flag", "dkin_flag")
# Tri-state limit flags (+1 upper / 0 measurement / -1 lower / null) — read with _intval, NEVER _flag.
_LIMIT_COLS = ("pl_bmasselim", "pl_masselim", "pl_msinielim", "pl_radelim", "pl_orbeccenlim",
               "pl_orbincllim", "pl_orbsmaxlim", "pl_orbperlim", "pl_orblperlim",
               "pl_denslim", "pl_impparlim")
_PLANET_T1_COLS = [
    "pl_controv_flag", "soltype", "ttv_flag", "cb_flag",
    "rv_flag", "ima_flag", "ast_flag", "micro_flag", "obm_flag",   # tran_flag already selected
    "etv_flag", "ptv_flag", "pul_flag", "dkin_flag",
    "pl_dens", "pl_imppar", "pl_orbinclerr1", "pl_orbinclerr2",
] + list(_LIMIT_COLS)

# SIMBAD designation key → ps name column, in archive-match priority order (HIP > HD > TIC > Gaia DR3).
_KEY_COLUMNS = [("HIP", "hip_name"), ("HD", "hd_name"), ("TIC", "tic_id"), ("Gaia EDR3", "gaia_dr3_id")]

# reflink HTML: <a refstr=DELREZ_ET_AL_2021 href=https://…/abstract target=ref>Delrez et al. 2021</a>
_REFLINK_RE = re.compile(
    r"refstr=(?P<refstr>\S+)\s+href=(?P<href>\S+?)(?:\s+target=\S+)?>(?P<cite>.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)


# ── value helpers (all None-safe; nulls stay explicit null, never fabricated) ─────────────────────

def _num(v):
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


def _flag(v):
    """1/0 archive flag → bool; None-safe (None stays None, not False)."""
    if v is None or v == "":
        return None
    try:
        return int(v) == 1
    except (TypeError, ValueError):
        return None


def _intval(v):
    """Archive int flag/limit → raw int; None-safe. Unlike _flag() this PRESERVES the value —
    critical for the tri-state *lim columns (+1 upper / 0 measurement / -1 lower / null): a
    consumer coding ``if lim == 1`` must still be able to see the -1 (CR-9 §3/§5.11)."""
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            return int(float(v))                         # tolerate "1.0"-style strings
        except (TypeError, ValueError):
            return None


def _t2_block(row, pairs):
    """Build a Tier-2 sub-block: for each (value_col, lim_col) pair emit the numeric value and its
    tri-state limit flag (lim read with _intval to keep the -1 sign; lim_col=None → value only)."""
    out = {}
    for val_col, lim_col in pairs:
        out[val_col] = _num(row.get(val_col))
        if lim_col:
            out[lim_col] = _intval(row.get(lim_col))
    return out


def _parse_reflink(html):
    """Archive reflink HTML → {citation, refstr, href, raw}; None when absent."""
    if not html:
        return None
    m = _REFLINK_RE.search(html)
    if m:
        cite = m.group("cite").strip()
        return {"citation": cite or None, "refstr": m.group("refstr"),
                "href": m.group("href"), "raw": html}
    text = re.sub(r"<[^>]+>", "", html).strip()      # unrecognised markup → strip tags, keep text
    return {"citation": text or None, "refstr": None, "href": None, "raw": html}


def _mass_kind(prov):
    """pl_bmassprov → the CR mass-kind flag. Keeps 'M-R relationship' as its own value (WB MSG 060):
    a radius-inferred mass is a derived value, neither a measurement nor m·sin i."""
    if not prov:
        return "unknown"
    p = str(prov).strip().lower()
    if p == "mass":
        return "true_mass"
    if "msin" in p:                                  # 'Msini', 'Msin(i)/sin(i)'
        return "msini"
    if "m-r" in p or "relationship" in p:
        return "mass_radius_relation"
    return "unknown"


def _sp(archive_sp, simbad_sp):
    a = (archive_sp or "").strip()
    if a:
        return a, "archive"
    s = (simbad_sp or "").strip()
    if s:
        return s, "simbad"
    return None, None


def _stellar(archive_v, simbad_v):
    a = _num(archive_v)
    if a is not None:
        return a, "archive"
    s = _num(simbad_v)
    if s is not None:
        return s, "simbad"
    return None, None


def _row_sig(row):
    """A hashable signature of a ps row, for deduping identical rows returned via >1 match arm."""
    return tuple(sorted(row.items(), key=lambda kv: kv[0]))


def _host_arms(sl, input_str):
    """CR-9 behavior #2 — the archive-match arms for a resolved host, in two tiers:
      catalog_arms  = [(col, val)] over hd_name/hip_name/tic_id/gaia_dr3_id (the CR-8 priority path);
      hostname_arms = [("hostname", name)] over the bare input + SIMBAD main_id + common designations.
    The NASA-PS table keys some confirmed-planet hosts (e.g. GJ 667 C) under a ``hostname`` whose ps
    rows carry NO hd/hip id, so a catalog-id-only join drops them to zero_planet — the hostname arm
    is the fallback that recovers them. Returns (catalog_arms, hostname_arms)."""
    designations = sl.get("designations", {}) or {}
    catalog = []
    for key, col in _KEY_COLUMNS:                        # HIP > HD > TIC > Gaia DR3
        v = designations.get(key)
        if v:
            catalog.append((col, str(v).strip()))
    names = []
    for cand in (input_str, sl.get("main_id"), designations.get("GJ"),
                 designations.get("HD"), designations.get("HIP"), designations.get("NAME")):
        c = (cand or "").strip()
        if c and c not in names:
            names.append(c)
    return catalog, [("hostname", c) for c in names]


def _fill_arm_rows(records, arm_key, select, default_clause):
    """Query ps for one arm-tier across ``records`` (grouped into one IN(...) query per column) and
    fill each record's ``rows``/``matched_on``, deduping against rows it already holds. Returns a
    route-error dict on network failure, else None."""
    by_col = {}
    for r in records:
        for col, val in r[arm_key]:
            by_col.setdefault(col, set()).add(val)
    rows_by_kv = {}
    for col, vals in by_col.items():
        try:
            rows = _query_ps_in(col, sorted(vals), select, default_clause)
        except Exception as e:
            return _route_error(_network_error_msg(e, "NASA Exoplanet Archive"), _ROUTE)
        for row in rows:
            rows_by_kv.setdefault((col, row.get(col)), []).append(row)
    for r in records:
        seen = {_row_sig(row) for row in r["rows"]}
        for col, val in r[arm_key]:
            arm_rows = rows_by_kv.get((col, val), [])
            if arm_rows and col not in r["matched_on"]:
                r["matched_on"].append(col)
            for row in arm_rows:
                sig = _row_sig(row)
                if sig not in seen:
                    seen.add(sig)
                    r["rows"].append(row)
    return None


# ── record builders ───────────────────────────────────────────────────────────────────────────────

def _planet_record(row, field_scope):
    prov_raw = row.get("pl_bmassprov")
    rec = {
        "name": row.get("pl_name"),
        "discovery_method": row.get("discoverymethod"),
        "period_days": _num(row.get("pl_orbper")),
        "sma_au": _num(row.get("pl_orbsmax")),
        "inclination_deg": _num(row.get("pl_orbincl")),      # null preserved — never defaulted to 90
        "eccentricity": _num(row.get("pl_orbeccen")),        # present 0 vs null = reported-vs-unmeasured
        "arg_periastron_deg": _num(row.get("pl_orblper")),
        "mass_earth": _num(row.get("pl_bmasse")),
        "mass_jupiter": _num(row.get("pl_bmassj")),
        "mass_kind": _mass_kind(prov_raw),
        "mass_prov_raw": prov_raw,
        "radius_earth": _num(row.get("pl_rade")),            # null when non-transiting
        "transiting": _flag(row.get("tran_flag")),
        "default_solution": _flag(row.get("default_flag")),
        "provenance": _parse_reflink(row.get("pl_refname")),
    }
    # ── CR-9 Tier-1 disposition / quality (core; D7 archive-named keys, D6 raw tri-state ints) ──
    rec["disposition"] = {
        "soltype": row.get("soltype"),
        "pl_controv_flag": _intval(row.get("pl_controv_flag")),
        "ttv_flag": _intval(row.get("ttv_flag")),
        "cb_flag": _intval(row.get("cb_flag")),
        "detection": {c: _intval(row.get(c)) for c in _DETECTION_FLAG_COLS},
        # convenience: the archive-stem of every method flag set to 1 (e.g. tran_flag=1 -> "tran")
        "detection_methods": [c[:-5] for c in _DETECTION_FLAG_COLS if _intval(row.get(c)) == 1],
    }
    rec["limits"] = {c: _intval(row.get(c)) for c in _LIMIT_COLS}   # +1 upper / 0 meas / -1 lower / null
    rec["pl_dens"] = _num(row.get("pl_dens"))
    rec["pl_imppar"] = _num(row.get("pl_imppar"))
    rec["pl_orbinclerr1"] = _num(row.get("pl_orbinclerr1"))         # W3 discriminator; null when blank
    rec["pl_orbinclerr2"] = _num(row.get("pl_orbinclerr2"))
    if field_scope == "full":
        # ── CR-9 Tier-2 per-planet enrichment (full only; SELECT is already '*') ──
        rec["transit_geometry"] = _t2_block(row, [
            ("pl_ratdor", "pl_ratdorlim"), ("pl_ratror", "pl_ratrorlim"),
            ("pl_trandep", "pl_trandeplim"), ("pl_trandur", "pl_trandurlim"),
            ("pl_tranmid", "pl_tranmidlim")])
        rec["environment"] = _t2_block(row, [("pl_insol", "pl_insollim"), ("pl_eqt", "pl_eqtlim")])
        rec["obliquity"] = _t2_block(row, [
            ("pl_projobliq", "pl_projobliqlim"), ("pl_trueobliq", "pl_trueobliqlim")])
        rec["ephemeris"] = _t2_block(row, [("pl_orbtper", "pl_orbtperlim")])
        rec["discovery"] = {
            "disc_year": _intval(row.get("disc_year")), "disc_facility": row.get("disc_facility"),
            "disc_telescope": row.get("disc_telescope"), "disc_instrument": row.get("disc_instrument"),
            "disc_pubdate": row.get("disc_pubdate"), "disc_refname": row.get("disc_refname"),
        }
        rec["record"] = {
            "pl_pubdate": row.get("pl_pubdate"), "rowupdate": row.get("rowupdate"),
            "releasedate": row.get("releasedate"),
            "pl_ntranspec": _intval(row.get("pl_ntranspec")), "pl_nespec": _intval(row.get("pl_nespec")),
            "pl_ndispec": _intval(row.get("pl_ndispec")), "pl_nnotes": _intval(row.get("pl_nnotes")),
        }
        rec["raw"] = dict(row)
    return rec


def _host_record(input_str, rows, simbad, field_scope):
    r0 = rows[0]
    sp, sp_src = _sp(r0.get("st_spectype"), simbad.get("sp_type") if simbad else None)
    teff, teff_src = _stellar(r0.get("st_teff"), simbad.get("teff") if simbad else None)
    feh, feh_src = _stellar(r0.get("st_met"), simbad.get("fe_h") if simbad else None)
    mass, mass_src = _stellar(r0.get("st_mass"), None)
    rad, rad_src = _stellar(r0.get("st_rad"), None)
    dist, dist_src = _stellar(r0.get("sy_dist"), simbad.get("parsecs") if simbad else None)

    mags = {}
    for band, col in [("V", "sy_vmag"), ("K", "sy_kmag"), ("Gaia_G", "sy_gaiamag")]:
        v = _num(r0.get(col))
        if v is not None:
            mags[band] = v
    if simbad and "V" not in mags:                           # SIMBAD Johnson V fallback
        v = _num(simbad.get("vmag"))
        if v is not None:
            mags["V"] = v

    cross = {}
    for k, col in [("HD", "hd_name"), ("HIP", "hip_name"), ("TIC", "tic_id"), ("Gaia DR3", "gaia_dr3_id")]:
        if r0.get(col):
            cross[k] = r0.get(col)
    if simbad:
        for k, v in (simbad.get("designations") or {}).items():
            if v and k != "MAIN_ID":
                cross.setdefault(k, v)

    planets = [_planet_record(row, field_scope) for row in rows]
    planets.sort(key=lambda p: (p["sma_au"] is None, p["sma_au"] or 0.0, p["name"] or ""))
    distinct = {p["name"] for p in planets}

    param_src = {k: v for k, v in {
        "spectral_type": sp_src, "teff_k": teff_src, "fe_h_dex": feh_src,
        "mass_solar": mass_src, "radius_solar": rad_src, "distance_pc": dist_src,
    }.items() if v}

    rec = {
        "resolved_host": (simbad.get("main_id") if simbad else r0.get("hostname")),
        "hostname": r0.get("hostname"),
        "cross_ids": cross,
        "spectral_type": sp,
        "teff_k": teff,
        "mass_solar": mass,
        "radius_solar": rad,
        "fe_h_dex": feh,
        "distance_pc": dist,
        "magnitudes": mags,
        "num_planets": len(distinct),
        "sy_pnum": _num(r0.get("sy_pnum")),
        "provenance": _parse_reflink(r0.get("st_refname")),
        "stellar_param_sources": param_src,
        "planets": planets,
    }
    if input_str is not None:
        rec["input"] = input_str
    if field_scope == "full":
        # ── CR-9 Tier-2 per-host enrichment (full only; SELECT is already '*') ──
        rec["stellar_extra"] = _t2_block(r0, [
            ("st_rotp", "st_rotplim"), ("st_vsin", "st_vsinlim"),
            ("st_age", "st_agelim"), ("st_dens", "st_denslim")])
        rec["coverage_counts"] = {c: _intval(r0.get(c)) for c in ("st_nrvc", "st_nphot", "st_nspec")}
        rec["system"] = {"sy_snum": _intval(r0.get("sy_snum")), "sy_mnum": _intval(r0.get("sy_mnum"))}
        rec["kinematics"] = {c: _num(r0.get(c)) for c in (
            "sy_pmra", "sy_pmraerr1", "sy_pmraerr2", "sy_pmdec", "sy_pmdecerr1", "sy_pmdecerr2",
            "sy_pm", "sy_plx", "sy_plxerr1", "sy_plxerr2", "st_radv", "st_radverr1", "st_radverr2")}
        rec["raw"] = dict(r0)
    return rec


# ── ADQL construction ───────────────────────────────────────────────────────────────────────────

def _select_clause(field_scope):
    if field_scope == "full":
        return "*"
    cols = _HOST_CORE_COLS + _PLANET_CORE_COLS + _PLANET_T1_COLS + ["default_flag"]
    return ", ".join(dict.fromkeys(cols))            # order-preserving dedupe


def _build_where(filters):
    """Mode-B property WHERE over ps (mirrors databases.search_exoplanets, on the ps columns)."""
    f = filters or {}
    parts = []

    def _rng(col, vmin, vmax):
        if vmin is not None:
            parts.append(f"{col} >= {float(vmin)}")
        if vmax is not None:
            parts.append(f"{col} <= {float(vmax)}")

    _rng("pl_bmasse", f.get("pl_bmasse_min"), f.get("pl_bmasse_max"))
    _rng("pl_rade",   f.get("pl_rade_min"),   f.get("pl_rade_max"))
    _rng("pl_orbper", f.get("pl_orbper_min"), f.get("pl_orbper_max"))
    _rng("st_teff",   f.get("st_teff_min"),   f.get("st_teff_max"))
    if f.get("sy_dist_max") is not None:
        parts.append(f"sy_dist <= {float(f['sy_dist_max'])}")

    method = (f.get("discoverymethod") or "").strip()
    if method and method.lower() != "any":
        parts.append(f"discoverymethod = '{_adql_quote(method)}'")

    sp = spectral_adql("st_spectype", f.get("spectral_classes"), f.get("spectral_refine", ""))
    if sp:
        parts.append(sp)

    return " AND ".join(parts) if parts else "pl_name IS NOT NULL"


def _default_clause(solution_scope):
    return "" if solution_scope == "all" else "default_flag = 1"


def _query_ps_in(col, values, select, default_clause):
    """One ps query per IN(...) chunk of name-values; concatenated rows."""
    out = []
    for i in range(0, len(values), _IN_CHUNK):
        chunk = values[i:i + _IN_CHUNK]
        quoted = ", ".join(f"'{_adql_quote(v)}'" for v in chunk)
        where = f"{col} IN ({quoted})"
        if default_clause:
            where += f" AND {default_clause}"
        out.extend(_query_tap(_TABLE, where, order_by=f"{col}, pl_name", select=select) or [])
    return out


# ── Mode runners ─────────────────────────────────────────────────────────────────────────────────

def _run_mode_a(hosts, select, default_clause, field_scope):
    resolved, unresolved = [], []
    for h in hosts:
        hs = (h or "").strip()
        if not hs:
            unresolved.append({"input": h, "reason": "blank host string"})
            continue
        try:
            sl = compute_simbad_lookup(hs)
        except Exception as e:                               # a raised SIMBAD failure must not kill the batch
            unresolved.append({"input": hs, "reason": _network_error_msg(e, "SIMBAD")})
            continue
        if "error" in sl:
            unresolved.append({"input": hs, "reason": sl["error"]})
            continue
        catalog_arms, hostname_arms = _host_arms(sl, hs)
        resolved.append({"input": hs, "simbad": sl, "catalog_arms": catalog_arms,
                         "hostname_arms": hostname_arms, "rows": [], "matched_on": []})

    # phase 1 — catalog-id arms (the CR-8 path; byte-identical for a normally-catalogued host)
    err = _fill_arm_rows(resolved, "catalog_arms", select, default_clause)
    if err:
        return err
    # phase 2 (behavior #2) — hostname fallback, ONLY for hosts phase 1 left empty (GJ 667 C class)
    pending = [r for r in resolved if not r["rows"]]
    if pending:
        err = _fill_arm_rows(pending, "hostname_arms", select, default_clause)
        if err:
            return err

    hosts_out, zero_planet, resolution = [], [], []
    for r in resolved:
        main_id = r["simbad"].get("main_id")
        if not r["rows"]:
            zero_planet.append({"input": r["input"], "resolved_host": main_id})
            continue
        hosts_out.append(_host_record(r["input"], r["rows"], r["simbad"], field_scope))
        resolution.append({"input": r["input"], "resolved_host": main_id,
                           "matched_on": r["matched_on"][0] if r["matched_on"] else None})

    coverage = {
        "requested": list(hosts),
        "resolved_count": len(resolved),
        "returned_host_count": len(hosts_out),
        "resolution": resolution,                        # behavior #2: per-host matched_on triage
        "unresolved": unresolved,
        "zero_planet": zero_planet,
        "total_hosts": len(hosts_out),
        "total_planets": sum(len(h["planets"]) for h in hosts_out),
    }
    # behavior #3 (best-effort): planets on OEC-grouped non-primary components — runs over every
    # resolved host, incl. a planetless primary (α Cen A → Proxima); 26 Dra correctly → nothing
    coverage["component_planets"] = _enumerate_component_planets(
        resolved, hosts_out, select, default_clause, field_scope)
    return {"mode": "hosts", "coverage": coverage, "hosts": hosts_out}


def _run_mode_b(filters, archive_query, select, default_clause, field_scope):
    try:
        where = archive_query.strip() if archive_query else _build_where(filters)
    except (TypeError, ValueError):
        return _route_error("Numeric filters must be numbers.", _ROUTE)
    full = f"({where}) AND {default_clause}" if default_clause else where

    try:
        rows = _query_tap(_TABLE, full, order_by="hostname, pl_name", select=select) or []
    except Exception as e:
        return _route_error(_network_error_msg(e, "NASA Exoplanet Archive"), _ROUTE)

    by_host = {}
    for row in rows:
        by_host.setdefault(row.get("hostname"), []).append(row)
    hosts_out = [_host_record(None, rws, None, field_scope) for _, rws in by_host.items()]
    hosts_out.sort(key=lambda h: h["hostname"] or "")

    coverage = {
        "selection_echo": where,
        "total_hosts": len(hosts_out),
        "total_planets": sum(len(h["planets"]) for h in hosts_out),
    }
    return {"mode": "filter", "coverage": coverage, "hosts": hosts_out}


# ── CR-9 full-scope enrichment: pscomppars composite fields + OEC cross-source ───────────────────

# The 8 fields that exist ONLY in pscomppars (verified absent from ps) — angular sep, TSM/ESM, JWST
# observation counts. A blended composite value, NEVER a per-solution measurement, so always tagged.
_COMPOSITE_NUM = ("pl_angsep", "pl_tsm", "pl_esm")
_COMPOSITE_INT = ("pl_angseplim", "pl_nobs_jwst_tran", "pl_nobs_jwst_e", "pl_nobs_jwst_pc", "pl_nobs_jwst_di")
_COMPOSITE_COLS = ("pl_angsep", "pl_angseplim", "pl_tsm", "pl_esm",
                   "pl_nobs_jwst_tran", "pl_nobs_jwst_e", "pl_nobs_jwst_pc", "pl_nobs_jwst_di")


def _composite_pull(planet_names):
    """Fetch the pscomppars-only composite fields for a set of planets, keyed by pl_name.
    Returns {pl_name: {source:'composite', <8 fields>}}. pscomppars is one composite row per planet,
    so no solution scoping. Raises on network failure (the caller degrades it to best-effort)."""
    names = sorted({n for n in planet_names if n})
    out = {}
    sel = ", ".join(("pl_name",) + _COMPOSITE_COLS)
    for i in range(0, len(names), _IN_CHUNK):
        chunk = names[i:i + _IN_CHUNK]
        quoted = ", ".join(f"'{_adql_quote(n)}'" for n in chunk)
        rows = _query_tap("pscomppars", f"pl_name IN ({quoted})", order_by="pl_name", select=sel) or []
        for row in rows:
            block = {"source": "composite"}                  # §5.8: never mistaken for a ps value
            for c in _COMPOSITE_NUM:
                block[c] = _num(row.get(c))
            for c in _COMPOSITE_INT:
                block[c] = _intval(row.get(c))
            out[row.get("pl_name")] = block
    return out


_GLIESE_RE = re.compile(r"^\s*(?:gliese|gj|gl)\s+", re.IGNORECASE)


def _oec_key(name):
    """OEC match key bridging the NASA 'GJ' ↔ OEC 'Gliese' convention (GJ 667 C c ≡ Gliese 667 C c),
    then through the catalogue's own _norm_oec_name (lowercase, strip prefixes + whitespace/-/_/*)."""
    return _norm_oec_name(_GLIESE_RE.sub("gj ", (name or "").strip(), count=1))


def _oec_name_expansions(name):
    """A name plus its GJ/Gliese spelling variants — OEC keys some Gliese stars under the full
    'Gliese' word while NASA/SIMBAD use 'GJ', so a raw candidate can miss the OEC index either way."""
    n = (name or "").strip()
    if not n:
        return []
    out = [n]
    m = _GLIESE_RE.match(n)
    if m:
        rest = n[m.end():]
        out += [f"Gliese {rest}", f"GJ {rest}"]
    return out


def _oec_planet_index(node, out):
    """Recurse an OEC system node → {alias-normalized planet name: planet_node} over every <planet>."""
    if node.get("tag") == "planet":
        for nm in node.get("names", []):
            k = _oec_key(nm)
            if k:
                out.setdefault(k, node)
    for ch in node.get("children", []):
        _oec_planet_index(ch, out)


def _oec_tree(node):
    """Compact stellar/planet hierarchy: tag + first name + child subtrees (the binary nesting)."""
    names = node.get("names") or []
    t = {"tag": node.get("tag"), "name": names[0] if names else None}
    kids = [_oec_tree(c) for c in node.get("children", [])]
    if kids:
        t["children"] = kids
    return t


def _oec_planet_block(pnode):
    """Per-planet OEC block (SECONDARY): <list> membership + OEC metadata, from a planet node's fields."""
    f = pnode.get("fields", {})
    def _fv(key):
        v = oec_fv(f.get(key))
        return v.get("value") if v else None
    return {
        "source": "oec", "authority": "SECONDARY",
        "lists": oec_statuses(f),                            # e.g. "Planets in binary systems, S-type"
        "discoveryyear": _fv("discoveryyear"),
        "lastupdate": _fv("lastupdate"),
        "description": _fv("description"),
    }


def _oec_enrich_host(host):
    """Best-effort OEC cross-source for one host (offline, allow_simbad=False): a per-planet ``oec``
    block (list membership + metadata) and a per-host ``oec_structure`` (binary nesting). No OEC match
    (or a planetless-in-OEC host) → the keys are set to None, never fabricated."""
    raw = [host.get("hostname"), host.get("resolved_host")] + list((host.get("cross_ids") or {}).values())
    candidates = []
    for c in raw:
        for exp in _oec_name_expansions(c):                  # + GJ/Gliese spelling variants
            if exp not in candidates:
                candidates.append(exp)
    system, matched = None, None
    for name in candidates:
        r = compute_oec(name, allow_simbad=False)            # offline: no per-host SIMBAD round-trip
        if "error" not in r:
            system, matched = r["system"], r.get("matched_name")
            break
    if system is None:
        for p in host["planets"]:
            p["oec"] = None
        host["oec_structure"] = None
        return
    pindex = {}
    _oec_planet_index(system, pindex)
    for p in host["planets"]:
        pnode = pindex.get(_oec_key(p.get("name")))
        p["oec"] = _oec_planet_block(pnode) if pnode else None
    host["oec_structure"] = {"source": "oec", "authority": "SECONDARY",
                             "matched_name": matched, "tree": _oec_tree(system)}


def _star_planet_hosts(node, out):
    """Collect OEC star nodes that directly host >=1 planet child (the planet-bearing components)."""
    if node.get("tag") == "star" and any(c.get("tag") == "planet" for c in node.get("children", [])):
        out.append(node)
    for ch in node.get("children", []):
        _star_planet_hosts(ch, out)


def _oec_candidates(simbad, input_str):
    """Broad OEC-resolution candidate names from a SIMBAD result (+ raw input), GJ/Gliese-expanded."""
    names = [input_str] if input_str else []
    if simbad:
        if simbad.get("main_id"):
            names.append(simbad["main_id"])
        desig = simbad.get("designations") or {}
        for k in ("NAME", "HD", "HIP", "GJ", "HR"):
            if desig.get(k):
                names.append(desig[k])
    out = []
    for n in names:
        for e in _oec_name_expansions(n):
            if e not in out:
                out.append(e)
    return out


def _resolve_oec_system_from_simbad(simbad, input_str):
    """OEC system node for a resolved host (offline, GJ/Gliese-aware), or None on miss."""
    for name in _oec_candidates(simbad, input_str):
        r = compute_oec(name, allow_simbad=False)
        if "error" not in r:
            return r["system"]
    return None


def _query_component(comp_name, select, default_clause, field_scope, have):
    """Resolve an OEC component star name via SIMBAD and pull its ps planets (behavior-#2 arms), as
    full records, excluding names already in ``have``. [] on any miss/failure (best-effort)."""
    sl = compute_simbad_lookup(comp_name)
    if "error" in sl:
        rec = {"catalog_arms": [], "hostname_arms": [("hostname", comp_name)], "rows": [], "matched_on": []}
    else:
        cat, host_arms = _host_arms(sl, comp_name)
        rec = {"catalog_arms": cat, "hostname_arms": host_arms, "rows": [], "matched_on": []}
    if _fill_arm_rows([rec], "catalog_arms", select, default_clause):
        return []
    if not rec["rows"] and _fill_arm_rows([rec], "hostname_arms", select, default_clause):
        return []
    recs, seen = [], set()
    for row in rec["rows"]:
        pr = _planet_record(row, field_scope)
        nm = pr.get("name")
        if nm and nm not in have and nm not in seen:
            seen.add(nm)
            recs.append(pr)
    return recs


def _enumerate_component_planets(resolved, hosts_out, select, default_clause, field_scope):
    """Behavior #3 (option A, best-effort — WB MSG 073): surface confirmed planets on OEC-grouped
    NON-primary component stars that a primary-only query drops — INCLUDING when the primary itself is
    planetless (the α Cen A → Proxima case, where the primary is a zero_planet host). SECONDARY
    attribution; the Gaia co-motion binding to a wide *un-catalogued* companion (26 Dra → GJ 685) stays
    the consumer's job (§7#3), so an un-catalogued multiple correctly yields nothing. No-op when OEC is
    unavailable. Runs over every resolved host (not just planet-bearing ones)."""
    # batch-wide exclusion: never re-surface a planet already returned as its own top-level host in this
    # batch (a consumer merging hosts[] + component_planets would otherwise double-count, e.g. querying
    # both "Alpha Cen A" and "Proxima" would list Proxima's planet under both).
    already = {p["name"] for h in hosts_out for p in h["planets"] if p.get("name")}
    out = []
    for r in resolved:
        try:
            simbad, inp = r.get("simbad"), r.get("input")
            system = _resolve_oec_system_from_simbad(simbad, inp)
            if system is None:
                continue
            host_keys = {_oec_key(n) for n in _oec_candidates(simbad, inp)}
            star_hosts = []
            _star_planet_hosts(system, star_hosts)
            for star in star_hosts:
                names = star.get("names", [])
                if not names or any(_oec_key(n) in host_keys for n in names):
                    continue                                  # skip the queried primary itself
                comp_planets = _query_component(names[0], select, default_clause, field_scope, already)
                if comp_planets:
                    out.append({
                        "primary": (simbad.get("main_id") if simbad else None) or inp,
                        "component": names[0], "source": "oec-tree", "authority": "SECONDARY",
                        "note": ("Planet on a wide / non-primary component grouped by OEC; confirming "
                                 "system membership (Gaia co-motion binding) is the consumer's job (§7#3)."),
                        "planets": comp_planets,
                    })
        except Exception:
            continue                                          # best-effort: never fatal
    return out


def _enrich_full(result):
    """CR-9 full-scope enrichment (mutates ``result`` in place). Best-effort — a network/parse failure
    degrades to null with a coverage note, and never fails the primary ps pull:
      * per-planet ``composite`` block (pscomppars, source:composite);
      * per-host/planet OEC cross-source block (SECONDARY / verify-at-primary)."""
    hosts = result.get("hosts", [])
    names = [p["name"] for h in hosts for p in h["planets"] if p.get("name")]
    try:
        comp = _composite_pull(names)
    except Exception as e:                                    # composite is enrichment, not the pull
        comp = {}
        result["coverage"]["composite_error"] = _network_error_msg(e, "NASA Exoplanet Archive (pscomppars)")
    for h in hosts:
        for p in h["planets"]:
            p["composite"] = comp.get(p["name"])             # None = looked up, no pscomppars row
    oec_err = 0
    for h in hosts:
        try:
            _oec_enrich_host(h)
        except Exception:                                    # OEC is SECONDARY enrichment, never fatal
            oec_err += 1
            for p in h["planets"]:
                p["oec"] = None
            h["oec_structure"] = None
    if oec_err:
        result["coverage"]["oec_error_hosts"] = oec_err


# ── public entry point ─────────────────────────────────────────────────────────────────────────

def compute_exoplanet_batch(hosts=None, filters=None, archive_query=None,
                            solution_scope="default", field_scope="core"):
    """Batch NASA Exoplanet Archive Planetary Systems (ps) pull. LIVE network.

    Exactly one of {hosts} vs {filters/archive_query} (Mode A vs Mode B). Returns
    ``{mode, solution_scope, field_scope, coverage, hosts[]}`` or ``{error, route_tried}``.
    """
    if solution_scope not in ("default", "all"):
        return _route_error("--solution-scope must be 'default' or 'all'.", _ROUTE)
    if field_scope not in ("core", "full"):
        return _route_error("--fields must be 'core' or 'full'.", _ROUTE)

    mode_a = hosts is not None
    mode_b = (filters is not None) or (archive_query is not None)
    if mode_a and mode_b:
        return _route_error("Supply exactly one of {host list, selection filter}, not both.", _ROUTE)
    if not mode_a and not mode_b:
        return _route_error("Supply exactly one of {host list, selection filter}.", _ROUTE)

    if mode_a:
        if not isinstance(hosts, (list, tuple)) or not any((h or "").strip() for h in hosts):
            return _route_error("--hosts must be a non-empty list of host designations.", _ROUTE)

    select = _select_clause(field_scope)
    default_clause = _default_clause(solution_scope)

    if mode_a:
        result = _run_mode_a(list(hosts), select, default_clause, field_scope)
    else:
        result = _run_mode_b(filters, archive_query, select, default_clause, field_scope)

    if "error" in result:
        return result
    if field_scope == "full":
        _enrich_full(result)                                 # composite (step 4) + OEC (step 5)
    # stable top-level key order
    return {"mode": result["mode"], "solution_scope": solution_scope, "field_scope": field_scope,
            "coverage": result["coverage"], "hosts": result["hosts"]}
