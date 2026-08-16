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

from core.databases import _query_tap, compute_simbad_lookup, _adql_quote
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


def _ps_archive_key(designations):
    """(ps name column, value) for a resolved host, priority HIP > HD > TIC > Gaia DR3, else (None, None)."""
    for key, col in _KEY_COLUMNS:
        v = designations.get(key)
        if v:
            return col, v
    return None, None


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
    if field_scope == "full":
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
        rec["raw"] = dict(r0)
    return rec


# ── ADQL construction ───────────────────────────────────────────────────────────────────────────

def _select_clause(field_scope):
    if field_scope == "full":
        return "*"
    cols = _HOST_CORE_COLS + _PLANET_CORE_COLS + ["default_flag"]
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
        sl = compute_simbad_lookup(hs)
        if "error" in sl:
            unresolved.append({"input": hs, "reason": sl["error"]})
            continue
        col, val = _ps_archive_key(sl.get("designations", {}))
        if not col:
            unresolved.append({"input": hs, "resolved_host": sl.get("main_id"),
                               "reason": "no HD/HIP/TIC/Gaia designation available for archive match"})
            continue
        resolved.append({"input": hs, "simbad": sl, "key_col": col, "key_val": val})

    by_col = {}
    for r in resolved:
        by_col.setdefault(r["key_col"], []).append(r["key_val"])

    rows_by_kv = {}
    for col, vals in by_col.items():
        try:
            rows = _query_ps_in(col, sorted(set(vals)), select, default_clause)
        except Exception as e:
            return _route_error(_network_error_msg(e, "NASA Exoplanet Archive"), _ROUTE)
        for row in rows:
            rows_by_kv.setdefault((col, row.get(col)), []).append(row)

    hosts_out, zero_planet = [], []
    for r in resolved:
        rws = rows_by_kv.get((r["key_col"], r["key_val"]), [])
        if not rws:
            zero_planet.append({"input": r["input"], "resolved_host": r["simbad"].get("main_id")})
            continue
        hosts_out.append(_host_record(r["input"], rws, r["simbad"], field_scope))

    coverage = {
        "requested": list(hosts),
        "resolved_count": len(resolved),
        "returned_host_count": len(hosts_out),
        "unresolved": unresolved,
        "zero_planet": zero_planet,
        "total_hosts": len(hosts_out),
        "total_planets": sum(len(h["planets"]) for h in hosts_out),
    }
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
    result["solution_scope"] = solution_scope
    result["field_scope"] = field_scope
    # stable top-level key order
    return {"mode": result["mode"], "solution_scope": solution_scope, "field_scope": field_scope,
            "coverage": result["coverage"], "hosts": result["hosts"]}
