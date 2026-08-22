"""core/catalog.py — Phase AM Tier-1 generic archive gateways (VizieR / Gaia TAP / HEASARC)
plus the CDS X-Match helper and the Tier-3 gaia-astrophysical per-source pull.

LIVE NETWORK. Every astroquery/astropy import is lazy (inside the functions) so a non-catalog
`query.py` invocation never pays the astroquery import cost and stays importable offline — the
same rationale as the lazily-imported dust modules. All public functions return the standard
JSON shape (``{"service", …, "count", "rows":[…]}``) on success and the
``{"error", "route_tried"}`` shape (via ``shared._route_error``) on any failure — never a bare
exception. Successful, non-empty results are cached by (service + query-hash) with a TTL
(``core.catalog_cache``); errors/empties are never cached.

**`catalog_cache` is the single cache authority — astroquery's OWN HTTP cache is disabled** (``cache=False``
on the Vizier / Heasarc.query_region / XMatch calls) because it caches *transiently-empty* / throttled
responses for ~7 days, silently masking real rows and contradicting this layer's "never cache empties" rule
(observed 2026-08-22: a throttled SB9 cone returned empty, got cached, and made a real orbit look absent).
Simbad + Gaia are TAP-based with no astroquery HTTP cache (``cache_location`` is ``None``), so they need no
change. ``core.catalog_cache.clear_all()`` (CLI: ``query.py catalog-cache-clear``) wipes both this layer and
any residual astroquery cache dir.

Row limits / async discipline (spec §5): VizieR defaults to a finite ROW_LIMIT (``--row-limit -1``
lifts it); Gaia's synchronous ``launch_job`` caps at 2000 rows, so *population* pulls must pass
``use_async=True`` (``launch_job_async``, no cap) with a timeout + retry.

API forms verified live against astroquery 0.4.11 on 2026-07-23:
  - VizieR whole/filtered catalog → ``Vizier(...).query_constraints(catalog=<id>)`` (B/cb/cbdata
    Name='GK Per' → Orb.Per = 1.996803 d).
  - Gaia → ``Gaia.launch_job(<ADQL>).get_results()``.
  - X-Match → ``XMatch.query(cat1=<Table>, cat2='vizier:I/311/hip2', max_distance=N*u.arcsec,
    colRA1='ra', colDec1='dec')`` (Capella → HIP 24608, Plx 76.2 mas).
"""

import math
import re

from core import catalog_cache
from core.shared import _network_error_msg, _route_error, _with_retries, _timeout_ctx

_GAIA_SYNC_ROW_CAP = 2000    # the ESA Gaia sync endpoint MAXREC (spec §5) — informational flag


# ── result-shaping helpers (astropy Table → JSON-safe rows) ───────────────────

def _cell(v):
    """One table cell → a JSON-safe Python scalar (masked/NaN → None)."""
    import numpy as np
    try:
        if v is None or v is np.ma.masked or np.ma.is_masked(v):
            return None
    except Exception:
        pass
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        f = float(v)
        return None if math.isnan(f) else f
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, np.str_):
        return str(v)
    if isinstance(v, float):
        return None if math.isnan(v) else v
    return v


def _table_to_rows(t, limit=None):
    """astropy Table → list of dicts, up to `limit` rows."""
    n = len(t) if limit is None else min(len(t), limit)
    cols = list(t.colnames)
    out = []
    for i in range(n):
        out.append({c: _cell(t[c][i]) for c in cols})
    return out


def _column_units(t):
    """{column: unit_str} for columns that carry a unit — the per-field provenance (spec §5)."""
    units = {}
    for c in t.colnames:
        u = getattr(t[c], "unit", None)
        if u is not None and str(u):
            units[c] = str(u)
    return units


def _parse_cone(cone):
    """'ra dec radius' (all degrees) → (ra, dec, radius) floats."""
    parts = str(cone).replace(",", " ").split()
    if len(parts) != 3:
        raise ValueError("--cone must be 'ra dec radius' in decimal degrees")
    return float(parts[0]), float(parts[1]), float(parts[2])


def _parse_vizier_filters(filters):
    """['col op val', …] → the Vizier column_filters dict form {'Per': '<365', 'Name': 'GK Per'}."""
    out = {}
    if not filters:
        return out
    for f in filters:
        m = re.match(r"\s*([\w./+\-]+)\s*(<=|>=|!=|<|>|=)\s*(.+?)\s*$", f)
        if m:
            col, op, val = m.group(1), m.group(2), m.group(3).strip()
            out[col] = val if op == "=" else f"{op}{val}"
        elif ":" in f:                    # raw 'col:constraint' passthrough (native Vizier syntax)
            k, v = f.split(":", 1)
            out[k.strip()] = v.strip()
        else:
            raise ValueError(f"Cannot parse filter '{f}' (expected \"col op val\")")
    return out


# ── Tier-1 gateway: VizieR ────────────────────────────────────────────────────

def vizier_query(catalog, columns=None, filters=None, cone=None, row_limit=2000, timeout=60):
    """Any VizieR catalog by id → JSON rows. Reuse targets: B/sb9, B/wds, B/orb6, B/cb/cbdata
    (Ritter & Kolb CVs), B/gcvs, I/311/hip2. `filters` is a list of 'col op val' strings;
    `cone` is 'ra dec radius' (deg); `row_limit=-1` lifts the finite default."""
    if not catalog:
        return _route_error("vizier-query requires --catalog", ["vizier-query"])

    def _run():
        from astroquery.vizier import Vizier
        import astropy.units as u
        from astropy.coordinates import SkyCoord
        col_filters = _parse_vizier_filters(filters)
        v = Vizier(columns=columns or ["*"], column_filters=col_filters,
                   row_limit=row_limit, timeout=timeout)
        with _timeout_ctx(timeout + 10):
            if cone:
                ra, dec, rad = _parse_cone(cone)
                # cache=False: bypass astroquery's OWN 7-day HTTP cache (it caches throttle-induced
                # empties, masking real rows for days — 2026-08-22). The app's catalog_cache layer is
                # the single cache authority and never caches empties/errors.
                res = _with_retries(v.query_region, SkyCoord(ra, dec, unit="deg"),
                                    radius=rad * u.deg, catalog=catalog, cache=False)
            else:
                res = _with_retries(v.query_constraints, catalog=catalog, cache=False)
        if not res or len(res) == 0:
            return {"service": "vizier", "catalog": catalog, "count": 0,
                    "truncated": False, "rows": []}
        t = res[0]
        truncated = bool(row_limit and row_limit > 0 and len(t) >= row_limit)
        return {"service": "vizier", "catalog": catalog, "count": len(t),
                "row_limit": row_limit, "truncated": truncated,
                "column_units": _column_units(t), "rows": _table_to_rows(t)}

    try:
        params = {"catalog": catalog, "columns": columns, "filters": filters,
                  "cone": cone, "row_limit": row_limit}
        return catalog_cache.cached("vizier", params, _run)
    except Exception as e:
        return _route_error(_network_error_msg(e, "CDS VizieR"), ["vizier-query"])


# ── Tier-1 gateway: Gaia TAP ──────────────────────────────────────────────────

def _build_gaia_adql(table, columns, where, cone, row_limit):
    cols = ", ".join(columns) if columns else "*"
    top = f"TOP {row_limit} " if (row_limit and row_limit > 0) else ""
    clauses = []
    if where:
        clauses.append(f"({where})")
    if cone:
        ra, dec, rad = _parse_cone(cone)
        clauses.append(f"1=CONTAINS(POINT('ICRS',ra,dec),"
                       f"CIRCLE('ICRS',{ra},{dec},{rad}))")
    wsql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return f"SELECT {top}{cols} FROM {table}{wsql}"


def gaia_tap(adql=None, table=None, columns=None, where=None, cone=None,
             row_limit=2000, use_async=False, timeout=300):
    """Any Gaia DR3 table by ADQL (`adql=`) or structured (`table`/`columns`/`where`/`cone`).
    `use_async=True` uses launch_job_async (no 2000-row cap) for population pulls; sync results
    hitting 2000 rows are flagged `truncated` (spec §5)."""
    if not adql and not table:
        return _route_error("gaia-tap requires --adql or --table", ["gaia-tap"])

    def _run():
        from astroquery.gaia import Gaia
        q = adql or _build_gaia_adql(table, columns, where, cone, row_limit)
        with _timeout_ctx(timeout):
            if use_async:
                prev = Gaia.ROW_LIMIT
                Gaia.ROW_LIMIT = row_limit if (row_limit and row_limit > 0) else -1
                try:
                    job = _with_retries(Gaia.launch_job_async, q, retries=3, base_delay=3.0)
                finally:
                    Gaia.ROW_LIMIT = prev
            else:
                job = _with_retries(Gaia.launch_job, q)
            t = job.get_results()
        truncated = bool(not use_async and len(t) >= _GAIA_SYNC_ROW_CAP)
        return {"service": "gaia", "query": q, "count": len(t),
                "async": bool(use_async), "truncated": truncated,
                "column_units": _column_units(t), "rows": _table_to_rows(t)}

    try:
        params = {"adql": adql, "table": table, "columns": columns, "where": where,
                  "cone": cone, "row_limit": row_limit, "async": use_async}
        return catalog_cache.cached("gaia", params, _run)
    except Exception as e:
        return _route_error(_network_error_msg(e, "ESA Gaia TAP"), ["gaia-tap"])


# ── Tier-1 gateway: HEASARC (X-ray) ───────────────────────────────────────────

def heasarc_query(catalog, cone=None, radius=0.1, adql=None, row_limit=2000, timeout=120):
    """A HEASARC X-ray catalog (e.g. rass2rxs, chanmaster, xmmssc) by cone (`cone='ra dec radius'`,
    or `catalog` + `radius` around a `cone` centre) or raw TAP (`adql=`). Serves the binary
    activity/flare + CV/compact-object identification story (spec §9 / §4.3)."""
    if not catalog and not adql:
        return _route_error("heasarc-query requires --catalog (with --cone) or --adql",
                            ["heasarc-query"])

    def _run():
        from astroquery.heasarc import Heasarc
        import astropy.units as u
        from astropy.coordinates import SkyCoord
        h = Heasarc()
        with _timeout_ctx(timeout):
            if adql:
                t = _with_retries(h.query_tap, adql, maxrec=row_limit if row_limit > 0 else None)
                if hasattr(t, "to_table"):
                    t = t.to_table()
            elif cone:
                ra, dec, rad = _parse_cone(cone) if len(str(cone).split()) == 3 else \
                    (*_parse_cone(f"{cone} {radius}")[:2], radius)
                t = _with_retries(h.query_region, SkyCoord(ra, dec, unit="deg"),
                                  catalog=catalog, radius=rad * u.deg, cache=False)  # bypass astroquery HTTP cache
            else:
                raise ValueError("heasarc-query requires --cone or --adql")
        return {"service": "heasarc", "catalog": catalog or "(adql)", "count": len(t),
                "column_units": _column_units(t), "rows": _table_to_rows(t)}

    try:
        params = {"catalog": catalog, "cone": cone, "radius": radius,
                  "adql": adql, "row_limit": row_limit}
        return catalog_cache.cached("heasarc", params, _run)
    except Exception as e:
        return _route_error(_network_error_msg(e, "HEASARC"), ["heasarc-query"])


# ── X-Match helper (census cross-match engine — not a subcommand) ─────────────

def xmatch_query(coords_rows, cat2="vizier:I/311/hip2", max_arcsec=5.0,
                 ra_key="ra", dec_key="dec", timeout=120):
    """Bulk positional cross-match of a local coordinate list against a VizieR catalog via the
    CDS X-Match service (the standard bulk matcher — replaces a hand-rolled SkyCoord match, §4.3).

    `coords_rows` is a list of dicts each carrying `ra_key`/`dec_key` (deg) plus any passthrough
    ids. Returns the matched rows (X-Match appends the cat2 columns + an `angDist` arcsec column)."""
    if not coords_rows:
        return {"service": "xmatch", "cat2": cat2, "count": 0, "rows": []}

    def _run():
        import astropy.units as u
        from astropy.table import Table
        from astroquery.xmatch import XMatch
        ras = [float(r[ra_key]) for r in coords_rows]
        decs = [float(r[dec_key]) for r in coords_rows]
        idx = list(range(len(coords_rows)))
        tbl = Table({"_idx": idx, ra_key: ras, dec_key: decs})
        with _timeout_ctx(timeout):
            xm = _with_retries(XMatch.query, cat1=tbl, cat2=cat2,
                               max_distance=max_arcsec * u.arcsec,
                               colRA1=ra_key, colDec1=dec_key, cache=False)  # bypass astroquery HTTP cache
        return {"service": "xmatch", "cat2": cat2, "max_arcsec": max_arcsec,
                "count": len(xm), "column_units": _column_units(xm),
                "rows": _table_to_rows(xm)}

    try:
        params = {"cat2": cat2, "max_arcsec": max_arcsec,
                  "coords": [(round(float(r[ra_key]), 6), round(float(r[dec_key]), 6))
                             for r in coords_rows]}
        return catalog_cache.cached("xmatch", params, _run)
    except Exception as e:
        return _route_error(_network_error_msg(e, "CDS X-Match"), ["xmatch"])


# ── Tier-3: gaia-astrophysical (per-source GSP-Phot + FLAME) ──────────────────

_ASTROPHYS_COLS = (
    "source_id, teff_gspphot, logg_gspphot, mh_gspphot, radius_gspphot, "
    "mass_flame, radius_flame, lum_flame, age_flame, age_flame_lower, age_flame_upper, "
    "evolstage_flame"
)


def gaia_astrophysical(star=None, source_id=None):
    """Gaia DR3 astrophysical_parameters (GSP-Phot Teff/logg/[M/H]/radius + FLAME
    mass/radius/lum/age/evolstage) for one source, queried **by source_id** (the table has no
    ra/dec). Serves the sister project's T8 per-star age anchor. **Every FLAME age carries the
    model-dependence caveat** (spec §4.4.1 / test T7)."""
    ident = {}
    sid = source_id
    if star and not sid:
        from core import databases, binary
        sl = databases.compute_simbad_lookup(star)
        if "error" in sl:
            return _route_error(sl["error"], ["simbad"])
        sid = binary.gaia_source_id_from_designations(sl.get("designations"))
        ident = {"main_id": sl.get("main_id"), "sp_type": sl.get("sp_type")}
        if not sid:
            return _route_error(f"no Gaia source_id resolved for '{star}'", ["simbad"])
    if not sid:
        return _route_error("gaia-astrophysical requires --star or --source-id", ["gaia-astrophysical"])

    res = gaia_tap(adql=(f"SELECT {_ASTROPHYS_COLS} FROM gaiadr3.astrophysical_parameters "
                         f"WHERE source_id={sid}"))
    if "error" in res:
        return res
    rows = res.get("rows", [])
    out = {
        "query": star or str(sid), "source_id": str(sid), "identity": ident,
        "parameters": rows[0] if rows else None,
        "caveats": {"age_flame": ("FLAME ages are model-dependent and carry known systematics — "
                                  "this reproduces the catalogue value, not astrophysical truth "
                                  "(e.g. η Cas A age_flame ≈ 10 Gyr vs ~5–6 Gyr literature)")},
        "units": {"teff_gspphot": "K", "mh_gspphot": "dex", "radius_gspphot": "R_sun",
                  "mass_flame": "M_sun", "radius_flame": "R_sun", "lum_flame": "L_sun",
                  "age_flame": "Gyr", "age_flame_lower": "Gyr", "age_flame_upper": "Gyr"},
    }
    if not rows:
        out["note"] = "no astrophysical_parameters row for this source_id"
    return out


# ── Gaia binary_masses (the §3.3 independent companion-mass cross-check) ───────

def gaia_binary_masses(source_id):
    """Gaia `gaiadr3.binary_masses` row for one source — the independent mass cross-check for the
    §3.3 companion classifier. **Per-source query** (a single-source `WHERE`; an IN-list / JOIN 500s
    server-side — spec §3.3), and `gaia_tap` already wraps it in retries so a transient 500 is retried,
    not treated as "no data". Returns the row dict (`m1`/`m2` +bounds, `fluxratio`, `combination_method`,
    `m1_ref`, `flag`) or `None` when there is no row or both `m1`/`m2` are null. **`m2` is frequently
    NULL even when `m1` is present** (Gaia derived only the primary), which is exactly why the
    Thiele-Innes computation stays primary and this only fills/cross-checks."""
    if not source_id:
        return None
    res = gaia_tap(adql=(
        "SELECT m1, m1_lower, m1_upper, m2, m2_lower, m2_upper, fluxratio, "
        "combination_method, m1_ref, flag FROM gaiadr3.binary_masses "
        f"WHERE source_id={source_id}"))
    if "error" in res or not res.get("rows"):
        return None
    row = res["rows"][0]
    if row.get("m1") is None and row.get("m2") is None:
        return None
    return row
