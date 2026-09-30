"""CR-26 — the network layer of the per-star wind model: astrometry, the X-ray ladder, the survey limit,
the radius candidates, the blend partners and the identity lookups, plus the orchestrator that turns a
resolved star into a ``stellar_wind.StarWindInputs``.

**CR-19 discipline on every resolve family** (spec §CR-26.9): a bounded wall-clock timeout, retry once
(``shared._bounded_call(retries=2)``; an answered error is never retried), a per-family circuit breaker
(trips on a timeout only, auto re-arms), the catalog cache for answers only (``{"answered": True,
"sources": [...]}`` — an answered-empty result is cached, a failure never is), and a surfaced status —
never a silent degrade. One force-unreachable hook per family (checked before the cache and any network):

| family | hook | timeout |
|---|---|---|
| X-ray rungs | ``SPACE_APP_XRAY_FORCE_UNREACHABLE`` (a ``2RXS,eRASS1,XMM`` list fails just those) | ``SPACE_APP_XRAY_TIMEOUT`` |
| survey limit | ``SPACE_APP_XRAY_LIMIT_FORCE_UNREACHABLE`` | ``SPACE_APP_XRAY_TIMEOUT`` |
| astrometry | ``SPACE_APP_XRAY_ASTROM_FORCE_UNREACHABLE`` (``=g``: the SIMBAD-G fetch only — H6) | CR-19 / SIMBAD |
| radius: TIC + SIMBAD cone | ``SPACE_APP_TIC_FORCE_UNREACHABLE`` | ``SPACE_APP_TIC_TIMEOUT`` |
| radius: Gaia | ``SPACE_APP_GAIA_RADIUS_FORCE_UNREACHABLE`` | CR-19 |
| blend partners | ``SPACE_APP_BLEND_FORCE_UNREACHABLE`` | SIMBAD |
| identity | ``SPACE_APP_SIMBAD_IDENT_FORCE_UNREACHABLE`` | SIMBAD |

Every catalog / Gaia / SIMBAD / mass call CR-26 makes goes through a module-level seam here
(``_heasarc_tap``, ``_tic_query``, ``_gaia_astrom_seam``, ``_gaia_radius_seam``, ``_partner_mass_seam``,
``_identity_lookup``) or through ``databases._simbad_cr26_tap`` — the offline test conftest patches exactly
these. Imports of the network stacks are lazy.
"""

import math
import os
import time

from core import stellar_wind as sw
from core import stellar_wind_tables as swt

HEASARC_TAP_URL = "https://heasarc.gsfc.nasa.gov/xamin/vo/tap"
_TIMEOUT_DEFAULT = 30.0
_COOLDOWN_S = 60.0
_BACKOFF = 0.5
_MJD_J2000 = 51544.5

# rung → (HEASARC table, columns, reference epoch of the pre-filter centre, match radius ″, epoch span yr)
_RUNG_CONF = {
    "2RXS": ("rass2rxs", "name, ra, dec, count_rate, onerxs_count_rate, exposure, time", 1990.8, 60.0, 1.0),
    "eRASS1": ("erass1main", "name, ra, dec, b1_flux, b1_count_rate, b1_exposure, time", 2020.2, 15.0, 1.0),
    "XMM": ("xmmssc", "srcid, name, ra, dec, ep_1_flux, ep_2_flux, ep_3_flux, ep_det_ml, sum_flag, time, "
                      "end_time", 2011.0, 10.0, 13.0),
}
_PREFILTER_MARGIN = 20.0            # ″
_XMM_SPAN_MAX = 25.0                # yr — the widest (end − time) a 5XMM row can span, for the pre-filter
_CONV = {"2RXS_1RXS": 6e-12, "2RXS": 10 ** -0.063 * 6e-12, "eRASS1": 10 ** 0.052, "XMM": 10 ** 0.087}
_RASS_EXP_DEFAULT = 380.15          # s — the W4 sample's median (no 2RXS source within 1°)
_BLEND_DEDUP_ARCSEC = 2.0
_GCNS_NEIGHBOUR_ARCSEC = 5.0
_TIC_RADIUS_ARCSEC = 5.0

_down = {}                          # family → (reason, tripped_monotonic)


class _Answered(Exception):
    """The service answered with a query error — deterministic, never retried (status ``error``)."""


class _IdentityFailed(Exception):
    """compute_simbad_lookup reported a network failure (not an answered 'no such object')."""


def reset_cr26_circuits():
    _down.clear()


def _warn(msg):
    from core.shared import _stderr_warn
    _stderr_warn("cr26", msg)


def _timeout(env):
    from core.shared import _env_timeout
    return _env_timeout(env, _TIMEOUT_DEFAULT)


def _breaker_open(family):
    d = _down.get(family)
    if d is None:
        return False
    if time.monotonic() - d[1] >= _COOLDOWN_S:
        _down.pop(family, None)
        return False
    return True


def _family_call(family, service, params, fn, timeout_env):
    """``(answer, None)`` or ``(None, code)`` — the CR-19 wrapper shared by the HEASARC and TIC families."""
    from core import catalog_cache
    from core.shared import _bounded_call, _WatchdogTimeout
    if _breaker_open(family):
        hit = catalog_cache.cache_get(catalog_cache.cache_key(service, params))
        return (hit, None) if hit is not None else (None, "timeout")
    try:
        return catalog_cache.cached(service, params, lambda: _bounded_call(
            fn, timeout=_timeout(timeout_env), retries=2, backoff=_BACKOFF, fatal=(_Answered,))), None
    except _WatchdogTimeout:
        _down[family] = ("timeout", time.monotonic())
        _warn(f"{family} bounded (timeout) — degrading")
        return None, "timeout"
    except _Answered:
        return None, "error"
    except Exception:
        _warn(f"{family} bounded (unreachable) — degrading")
        return None, "unreachable"


def _hook(name):
    v = os.environ.get(name)
    return v if v else None


def _plain(v):
    try:
        if hasattr(v, "mask") and v.mask:
            return None
    except Exception:
        pass
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, bytes):
        v = v.decode("utf-8", "replace")
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


# ── seams (the conftest patches every one of these) ─────────────────────────────
def _heasarc_tap(adql):
    """One HEASARC TAP query → ``{"answered": True, "sources": [row dicts]}`` (a fresh pyvo service)."""
    from pyvo.dal import TAPService, DALQueryError
    try:
        t = TAPService(baseurl=HEASARC_TAP_URL).run_sync(adql).to_table()
    except DALQueryError as e:
        raise _Answered(str(e)) from e
    return {"answered": True, "sources": [{c: _plain(r[c]) for c in t.colnames} for r in t]}


def _tic_query(ra, dec):
    """TIC v8.2 (VizieR IV/39/tic82) at J2000.0 within 5″ → ``{"answered": True, "sources": [{rad, sep}]}``."""
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    from astroquery.vizier import Vizier
    v = Vizier(columns=["TIC", "GAIA", "Rad", "_r"], row_limit=50)
    res = v.query_region(SkyCoord(ra, dec, unit="deg", frame="icrs"), radius=_TIC_RADIUS_ARCSEC * u.arcsec,
                         catalog="IV/39/tic82", cache=False)
    rows = []
    if res is not None and len(res):
        t = res[0]
        for r in t:
            rows.append({"rad": _plain(r["Rad"]) if "Rad" in t.colnames else None,
                         "sep": _plain(r["_r"]) if "_r" in t.colnames else None,
                         "tic": str(_plain(r["TIC"])) if "TIC" in t.colnames and _plain(r["TIC"]) else None,
                         "gaia": str(_plain(r["GAIA"])) if "GAIA" in t.colnames and _plain(r["GAIA"]) else None})
    return {"answered": True, "sources": rows}


def _gaia_astrom_seam(sid):
    from core import catalog
    return catalog.gaia_tap(adql=("SELECT source_id, ra, dec, pmra, pmdec, parallax, parallax_error, "
                                  f"phot_g_mean_mag FROM gaiadr3.gaia_source WHERE source_id={int(sid)}"))


def _gaia_radius_seam(sid):
    from core import catalog
    return catalog.gaia_astrophysical(source_id=str(sid))


def _partner_mass_seam(spec, catalog):
    from core import stellar_mass
    return stellar_mass.resolve_component_mass(spec, catalog)


def _identity_lookup(ident):
    """M-4 adapter over ``databases.compute_simbad_lookup`` (which never raises): ``(record, None)`` on a
    hit, ``(None, None)`` when SIMBAD answered "no such object", ``(None, code)`` on a failure. Bounded by
    ``SPACE_APP_SIMBAD_TIMEOUT`` (one outer attempt — the lookup retries internally); hook
    ``SPACE_APP_SIMBAD_IDENT_FORCE_UNREACHABLE``."""
    if _hook("SPACE_APP_SIMBAD_IDENT_FORCE_UNREACHABLE"):
        return None, "unreachable"
    if _breaker_open("identity"):
        return None, "timeout"
    from core import databases
    from core.shared import _bounded_call, _WatchdogTimeout

    def _go():
        sl = databases.compute_simbad_lookup(ident)
        if isinstance(sl, dict) and "error" in sl:
            if str(sl["error"]).startswith(databases.SIMBAD_NO_RESULTS_PREFIX):
                return None
            raise _IdentityFailed(sl["error"])
        return sl
    try:
        return _bounded_call(_go, timeout=_timeout("SPACE_APP_SIMBAD_TIMEOUT"), retries=1), None
    except _WatchdogTimeout:
        _down["identity"] = ("timeout", time.monotonic())
        return None, "timeout"
    except Exception:
        return None, "unreachable"


# ── geometry ─────────────────────────────────────────────────────────────────────
def mjd_to_year(mjd):
    return 2000.0 + (float(mjd) - _MJD_J2000) / 365.25


def propagate(ra, dec, pmra, pmdec, ep0, ep):
    """Linear proper-motion propagation (pmra = μα*, mas/yr)."""
    dt = ep - ep0
    dec2 = dec + (pmdec or 0.0) * dt / 3.6e6
    ra2 = ra + (pmra or 0.0) * dt / 3.6e6 / max(math.cos(math.radians(dec)), 1e-9)
    return ra2 % 360.0, dec2


def sep_arcsec(ra1, dec1, ra2, dec2):
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    c = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(r1 - r2)
    return math.degrees(math.acos(max(-1.0, min(1.0, c)))) * 3600.0


def galactic_l(ra, dec):
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    return float(SkyCoord(ra=ra * u.deg, dec=dec * u.deg).galactic.l.deg)


def _cone(table, cols, ra, dec, r_arcsec):
    return (f"SELECT {cols} FROM {table} WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), "
            f"CIRCLE('ICRS', {ra:.8f}, {dec:.8f}, {r_arcsec / 3600.0:.8f}))")


# ── 4.1 astrometry ───────────────────────────────────────────────────────────────
def _gcns_connect(db_path=None):
    """A read-only connection to the GCNS DB (a proper file URI — safe for any path on any OS), or None."""
    import pathlib
    import sqlite3
    from core import db
    path = pathlib.Path(db_path or db._DB_PATH)
    if not path.is_file():
        return None
    try:
        return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    except sqlite3.Error:
        return None


def _gcns_row_by_sid(sid, db_path=None):
    import sqlite3
    con = _gcns_connect(db_path)
    if con is None:
        return None
    try:
        con.row_factory = sqlite3.Row
        r = con.execute("SELECT ra, dec, pmra, pmdec, parallax, parallax_error, phot_g_mean_mag, system_id "
                        "FROM gcns_stars "
                        "WHERE gaia_source_id = ? AND gcns_table = 'main'", (int(sid),)).fetchone()
        return dict(r) if r else None
    except sqlite3.Error:
        return None
    finally:
        con.close()


def star_astrometry(identity, *, db_path=None):
    """Astrometry for the ladder: GCNS main row → live Gaia DR3 → SIMBAD (J2000). Returns a dict
    ``{ra, dec, epoch, pmra, pmdec, plx, plx_err, g, g_status, oid, status, notes}``; ``status`` is a
    failure code only when every applicable step failed."""
    from core import databases
    hook = _hook("SPACE_APP_XRAY_ASTROM_FORCE_UNREACHABLE")
    g_only = bool(hook) and hook.strip().lower() == "g"
    fail_all = bool(hook) and not g_only
    sid = identity.get("gaia_sid")
    notes = []
    a = None
    fails = []
    if sid:
        row = _gcns_row_by_sid(sid, db_path=db_path)
        if row and row.get("ra") is not None:
            a = {"ra": row["ra"], "dec": row["dec"], "epoch": 2016.0, "pmra": row["pmra"],
                 "pmdec": row["pmdec"], "plx": row["parallax"], "plx_err": row["parallax_error"],
                 "g": row["phot_g_mean_mag"]}
        if a is None:
            if fail_all:
                fails.append("unreachable")
            else:
                res = _gaia_astrom_seam(sid)
                if isinstance(res, dict) and "error" not in res and res.get("rows"):
                    r = res["rows"][0]
                    a = {"ra": r.get("ra"), "dec": r.get("dec"), "epoch": 2016.0, "pmra": r.get("pmra"),
                         "pmdec": r.get("pmdec"), "plx": r.get("parallax"), "plx_err": r.get("parallax_error"),
                         "g": r.get("phot_g_mean_mag")}
                elif isinstance(res, dict) and "error" in res:
                    fails.append(res.get("gaia_bound_reason") or "unreachable")
                    notes.append("live Gaia DR3 astrometry failed — SIMBAD's J2000.0 astrometry used instead")
    simbad = None
    s_status = None
    need_simbad = a is None or a.get("g") is None or a.get("pmra") is None
    if need_simbad and identity.get("main_id"):
        if fail_all:
            s_status = "unreachable"
        else:
            simbad, s_status = databases.simbad_astrometry(identity["main_id"], family="astrometry")
    if a is None:
        if simbad is None:
            # every applicable step failed (or SIMBAD answered with no object for a star with no Gaia row)
            return {"status": s_status or (fails[0] if fails else "error"), "notes": notes}
        a = {"ra": simbad.get("ra"), "dec": simbad.get("dec"), "epoch": 2000.0, "pmra": simbad.get("pmra"),
             "pmdec": simbad.get("pmdec"), "plx": simbad.get("plx_value"), "plx_err": simbad.get("plx_err"),
             "g": None}
    a["oid"] = simbad.get("oid") if simbad else None
    # G for the XMM guard: Gaia, else SIMBAD flux G (G3a); a FAILED SIMBAD-G fetch → g_status (H6)
    a["g_status"] = None
    if a.get("g") is None:
        if g_only:
            a["g_status"] = "unreachable"
        elif simbad is not None:
            a["g"] = simbad.get("g")
        elif s_status:
            a["g_status"] = s_status
    if a.get("pmra") is None or a.get("pmdec") is None:
        if simbad is not None and simbad.get("pmra") is not None and simbad.get("pmdec") is not None:
            a["pmra"], a["pmdec"] = simbad.get("pmra"), simbad.get("pmdec")   # PM is epoch-independent
        else:
            a["pmra"], a["pmdec"] = a.get("pmra") or 0.0, a.get("pmdec") or 0.0
            notes.append("the astrometry lookup answered with no proper motion — zero proper motion assumed")
    a["status"] = None
    a["notes"] = notes
    return a


# ── 4.2 the ladder ───────────────────────────────────────────────────────────────
def _pm_arcsec(a):
    return math.hypot(a.get("pmra") or 0.0, a.get("pmdec") or 0.0) / 1000.0


def _rung_hook():
    v = _hook("SPACE_APP_XRAY_FORCE_UNREACHABLE")
    if not v:
        return set()
    names = {x.strip().lower() for x in v.split(",") if x.strip()}
    known = {r.lower(): r for r in sw.RUNGS}
    if names and names <= set(known):
        return {known[n] for n in names}
    return set(sw.RUNGS)


def xray_ladder(a):
    """Query every rung (G6). Returns ``[{rung, status, cand}]`` — ``cand`` for a detection: the nearest
    matched source ``{f_x, rung_label, source_id, epoch, separation_arcsec, sum_flag, det_ml, ra, dec,
    match_radius}``."""
    forced = _rung_hook()
    pm = _pm_arcsec(a)
    out = []
    for rung in sw.RUNGS:
        table, cols, ref, match, span = _RUNG_CONF[rung]
        if rung == "eRASS1":
            if galactic_l(*propagate(a["ra"], a["dec"], a["pmra"], a["pmdec"], a["epoch"], 2020.2)) < 180.0:
                out.append({"rung": rung, "status": "out_of_footprint", "cand": None})
                continue
        if rung in forced:
            out.append({"rung": rung, "status": "unreachable", "cand": None})
            continue
        ra0, dec0 = propagate(a["ra"], a["dec"], a["pmra"], a["pmdec"], a["epoch"], ref)
        extra = pm * (span if rung != "XMM" else _XMM_SPAN_MAX)
        radius = match + extra + _PREFILTER_MARGIN + (pm * _XMM_SPAN_MAX / 2 if rung == "XMM" else 0.0)
        adql = _cone(table, cols, ra0, dec0, radius)
        res, st = _family_call("xray", "cr26_heasarc", {"adql": adql}, lambda q=adql: _heasarc_tap(q),
                               "SPACE_APP_XRAY_TIMEOUT")
        if st:
            out.append({"rung": rung, "status": st, "cand": None})
            continue
        best = None
        for r in res["sources"]:
            if r.get("ra") is None or r.get("time") is None:
                continue
            if rung == "XMM":
                e0 = mjd_to_year(r["time"])
                e1 = mjd_to_year(r["end_time"]) if r.get("end_time") is not None else e0
                ep, tol = 0.5 * (e0 + e1), match + pm * (e1 - e0) / 2.0
            else:
                ep, tol = mjd_to_year(r["time"]), match
            ra_s, dec_s = propagate(a["ra"], a["dec"], a["pmra"], a["pmdec"], a["epoch"], ep)
            s = sep_arcsec(ra_s, dec_s, r["ra"], r["dec"])
            if s <= tol and (best is None or s < best[0]):
                best = (s, r, ep, tol)
        if best is None:
            out.append({"rung": rung, "status": "no_detection", "cand": None})
            continue
        s, r, ep, tol = best
        if rung == "2RXS":
            usable = (r.get("onerxs_count_rate") or 0) > 0 or (r.get("count_rate") or 0) > 0
        elif rung == "eRASS1":
            usable = (r.get("b1_flux") or 0) > 0
        else:
            usable = sum(float(r.get(k) or 0.0) for k in ("ep_1_flux", "ep_2_flux", "ep_3_flux")) > 0
        if not usable:
            _warn(f"{rung}: the matched source {r.get('name')} carries no usable flux — rung reads 'error'")
            out.append({"rung": rung, "status": "error", "cand": None})
            continue
        cand = {"separation_arcsec": s, "epoch": ep, "ra": r["ra"], "dec": r["dec"], "match_radius": tol,
                "source_id": str(r.get("name") or r.get("srcid") or "")}
        if rung == "2RXS":
            if r.get("onerxs_count_rate") is not None and r["onerxs_count_rate"] > 0:
                cand.update(f_x=r["onerxs_count_rate"] * _CONV["2RXS_1RXS"], rung_label="2RXS_1RXS")
            else:
                cand.update(f_x=(r.get("count_rate") or 0.0) * _CONV["2RXS"], rung_label="2RXS")
        elif rung == "eRASS1":
            cand.update(f_x=(r.get("b1_flux") or 0.0) * _CONV["eRASS1"], rung_label="eRASS1")
        else:
            soft = sum(float(r.get(k) or 0.0) for k in ("ep_1_flux", "ep_2_flux", "ep_3_flux"))
            cand.update(f_x=soft * _CONV["XMM"], rung_label="XMM", sum_flag=r.get("sum_flag"),
                        det_ml=r.get("ep_det_ml"))
        out.append({"rung": rung, "status": "detection", "cand": cand})
    return out


# ── 4.3 the survey limit ─────────────────────────────────────────────────────────
def survey_limit(a, in_footprint):
    """The deeper of the RASS and eRASS1 local-exposure limits (at-Earth fit-scale flux). Returns
    ``{status, f_limit, survey}`` — ``status`` a failure code (no limit — N4) or ``None``."""
    if _hook("SPACE_APP_XRAY_LIMIT_FORCE_UNREACHABLE"):
        return {"status": "unreachable", "f_limit": None, "survey": None}
    ra0, dec0 = propagate(a["ra"], a["dec"], a["pmra"], a["pmdec"], a["epoch"], 1990.8)
    adql = _cone("rass2rxs", "exposure", ra0, dec0, 3600.0)
    res, st = _family_call("xray_limit", "cr26_heasarc", {"adql": adql}, lambda: _heasarc_tap(adql),
                           "SPACE_APP_XRAY_TIMEOUT")
    if st:
        return {"status": st, "f_limit": None, "survey": None}
    exps = sorted(float(r["exposure"]) for r in res["sources"] if r.get("exposure"))
    e_rass = _median(exps) if exps else _RASS_EXP_DEFAULT
    limits = [(6.0 / e_rass * _CONV["2RXS"], "RASS")]
    if in_footprint:
        ra1, dec1 = propagate(a["ra"], a["dec"], a["pmra"], a["pmdec"], a["epoch"], 2020.2)
        adql = _cone("erass1main", "b1_exposure, b1_flux, b1_count_rate", ra1, dec1, 1800.0)
        res, st = _family_call("xray_limit", "cr26_heasarc", {"adql": adql}, lambda: _heasarc_tap(adql),
                               "SPACE_APP_XRAY_TIMEOUT")
        if st:
            return {"status": st, "f_limit": None, "survey": None}
        rows = res["sources"]
        e = [float(r["b1_exposure"]) for r in rows if r.get("b1_exposure")]
        ecf = [float(r["b1_flux"]) / float(r["b1_count_rate"]) for r in rows
               if r.get("b1_flux") is not None and r.get("b1_count_rate") and float(r["b1_count_rate"]) > 0]
        if e and ecf:
            limits.append((6.0 / _median(sorted(e)) * _median(sorted(ecf)) * _CONV["eRASS1"], "eRASS1"))
    f, survey = min(limits)
    return {"status": None, "f_limit": f, "survey": survey}


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


# ── 4.4 radius candidates ────────────────────────────────────────────────────────
def radius_candidates(a, gaia_sid, *, oid=None, main_id=None, db_path=None, own_names=(), degraded=False):
    """TIC → Gaia FLAME → Gaia GSP-Phot candidates + the R12 ambiguity inputs. Returns
    ``(candidates, statuses, cone_other, gcns_neighbour)`` — a failed family is recorded only."""
    statuses, cands = {}, []
    ra2k, dec2k = propagate(a["ra"], a["dec"], a["pmra"], a["pmdec"], a["epoch"], 2000.0)
    tic_hook = _hook("SPACE_APP_TIC_FORCE_UNREACHABLE")
    if tic_hook:
        statuses["tic"] = "unreachable"
    else:
        res, st = _family_call("tic", "cr26_tic", {"ra": round(ra2k, 6), "dec": round(dec2k, 6)},
                               lambda: _tic_query(ra2k, dec2k), "SPACE_APP_TIC_TIMEOUT")
        if st:
            statuses["tic"] = st
        else:
            rows = [r for r in res["sources"] if r.get("rad")]
            if rows:
                best = min(rows, key=lambda r: (r.get("sep") if r.get("sep") is not None else 0.0))
                cands.append({"source": "tic", "value": float(best["rad"]), "tic": best.get("tic"),
                              "gaia": best.get("gaia")})
    if gaia_sid:
        if _hook("SPACE_APP_GAIA_RADIUS_FORCE_UNREACHABLE"):
            statuses["gaia"] = "unreachable"
        else:
            res = _gaia_radius_seam(gaia_sid)
            if isinstance(res, dict) and "error" in res:
                statuses["gaia"] = res.get("gaia_bound_reason") or "unreachable"
            else:
                p = (res or {}).get("parameters") or {}
                if p.get("radius_flame"):
                    cands.append({"source": "gaia_flame", "value": float(p["radius_flame"])})
                if p.get("radius_gspphot"):
                    cands.append({"source": "gaia_gspphot", "value": float(p["radius_gspphot"])})
    cone_other = None
    if tic_hook:
        statuses["simbad_cone"] = "unreachable"
    else:
        from core import databases
        stars, st = databases.simbad_cone_stars(ra2k, dec2k, _TIC_RADIUS_ARCSEC, exclude_oid=oid,
                                                exclude_main_id=main_id, family="radius")
        if st:
            statuses["simbad_cone"] = st
        else:
            cone_other = bool(stars)
    gn = _gcns_neighbour(a, gaia_sid, main_id, db_path=db_path, own_names=own_names, degraded=degraded)
    return cands, statuses, cone_other, gn


def _gcns_rows_near(ra, dec, r_arcsec, db_path=None):
    """GCNS rows in a dec band + a wrap-safe RA window around (ra, dec) — bound SQL parameters."""
    import sqlite3
    con = _gcns_connect(db_path)
    if con is None:
        return None
    r_deg = r_arcsec / 3600.0
    ddec = r_deg
    dra = min(180.0, r_deg / max(math.cos(math.radians(min(89.9, abs(dec) + r_deg))), 1e-6))
    lo, hi = ra - dra, ra + dra
    cols = ("gaia_source_id, ra, dec, parallax, parallax_error, pmra, pmdec, phot_g_mean_mag, dist_pc, "
            "wd_prob, spectral_type, star_name, gcns_table, system_id")
    try:
        con.row_factory = sqlite3.Row
        if lo < 0 or hi >= 360:
            q = (f"SELECT {cols} FROM gcns_stars WHERE dec BETWEEN ? AND ? AND (ra >= ? OR ra <= ?)")
            args = (dec - ddec, dec + ddec, lo % 360.0, hi % 360.0)
        else:
            q = f"SELECT {cols} FROM gcns_stars WHERE dec BETWEEN ? AND ? AND ra BETWEEN ? AND ?"
            args = (dec - ddec, dec + ddec, lo, hi)
        return [dict(r) for r in con.execute(q, args).fetchall()]
    except sqlite3.Error:
        return None
    finally:
        con.close()


def _own_name_matcher(names, degraded=False):
    """The target's own-name test (G13's name half). ``names`` = its main_id (+ the head on a degraded H1 path);
    on that degraded path only, K3 despacing applies to both sides (``HD 239960 A`` ≡ ``HD 239960A``)."""
    own = {swt.collapse_ws(n) for n in names if n}
    own.discard("")
    if degraded:
        own |= {_k3_variant(n) for n in own}

    def is_own(n):
        n = swt.collapse_ws(n)
        return bool(n) and (n in own or (degraded and _k3_variant(n) in own))
    return is_own


def _gcns_neighbour(a, sid, main_id, db_path=None, *, own_names=(), degraded=False):
    rows = _gcns_rows_near(*propagate(a["ra"], a["dec"], a["pmra"], a["pmdec"], a["epoch"], 2016.0),
                           _GCNS_NEIGHBOUR_ARCSEC + 5.0, db_path=db_path)
    if rows is None:
        return None
    is_own = _own_name_matcher([main_id, *own_names], degraded)
    for r in rows:
        if r["gcns_table"] == "main":
            if sid and r.get("gaia_source_id") and int(r["gaia_source_id"]) == int(sid):
                continue                                  # the target itself
            if not sid and is_own(r.get("star_name")):
                continue                                  # a no-sid target's own main row, by name
        elif is_own(r.get("star_name")):
            continue                                      # the target's missing_10mas copy
        ep = 2016.0 if r["gcns_table"] == "main" else 2000.0
        ra_t, dec_t = propagate(a["ra"], a["dec"], a["pmra"], a["pmdec"], a["epoch"], ep)
        if sep_arcsec(ra_t, dec_t, r["ra"], r["dec"]) > _GCNS_NEIGHBOUR_ARCSEC:
            continue
        if r["gcns_table"] != "main" and _not_another_star(r, is_own):
            continue                                      # RG3 (S1) / G13: a system entry, or the target's own copy
        return True
    return False


def _not_another_star(r, is_own):
    """RG3 / S1 — a ``missing_10mas`` row named ``** …``, or resolving in SIMBAD to otype ``**``, is a system
    entry; one resolving to the target's own main_id is the target's copy (G13's identity half). The lookup is
    a radius-family call, so the TIC/cone hook suppresses it; a failed or suppressed lookup (or no name) keeps
    the row a star, so ``radius_pair_ambiguous`` errs toward the flag."""
    from core import databases
    name = r.get("star_name") or ""
    if name.startswith("** "):
        return True
    if not name or _hook("SPACE_APP_TIC_FORCE_UNREACHABLE"):
        return False
    info, st = databases.simbad_astrometry(name, family="radius")
    if st or not info:
        return False
    return (info.get("otype") or "").strip() == "**" or is_own(info.get("main_id"))


# ── 4.5 blend partners ───────────────────────────────────────────────────────────
_REACH = {}


def gcns_reach(db_path=None):
    """The GCNS table's maximum ``dist_pc`` (memoised per DB path); ``None`` for an empty / missing table."""
    import sqlite3
    from core import db
    path = str(db_path or db._DB_PATH)
    if path in _REACH:
        return _REACH[path]
    con = _gcns_connect(db_path)
    if con is None:
        return None
    val = None
    try:
        row = con.execute("SELECT MAX(dist_pc) FROM gcns_stars").fetchone()
        val = row[0] if row else None
    except sqlite3.Error:
        val = None
    finally:
        con.close()
    if val:
        _REACH[path] = val                       # an empty / missing table is not memoised (it can be imported)
    return val


def _letter_pair(a_name, b_name):
    """(S) — identifiers that differ only by a component letter (``HD 156384`` / ``HD 156384C``)."""
    import re
    a, b = swt.collapse_ws(a_name), swt.collapse_ws(b_name)
    if not a or not b or a == b:
        return False
    strip = lambda s: re.sub(r"\s?[A-D]$", "", s)
    return strip(a) == strip(b) and (strip(a) != a or strip(b) != b)


def blend_partners(a, cand, d_pc, target, catalog, *, db_path=None):
    """The §26.3.4 partner search for a matched source ``cand``. ``target`` = ``{main_id, sid, mass}``.
    Returns the ``blend`` dict the model consumes: ``{status, partners, field_stars, notes, partial}``."""
    from core import databases
    notes = []
    if _hook("SPACE_APP_BLEND_FORCE_UNREACHABLE"):
        return {"status": "failed", "partners": [], "field_stars": [], "partial": False,
                "notes": ["blend-partner lookup failed (unreachable) — no blend processing"]}
    reach = gcns_reach(db_path)
    if not reach:
        return {"status": "failed", "partners": [], "field_stars": [], "partial": False,
                "notes": ["blend-partner lookup failed: the local GCNS table is empty or missing — no blend "
                          "processing (run option 58)"]}
    if d_pc is not None and d_pc > reach:
        return {"status": "not_run", "partners": [], "field_stars": [], "partial": False,
                "notes": [f"the target ({d_pc:.1f} pc) lies beyond the local GCNS table's reach ({reach:.1f} pc)"
                          " — blend detection not run"]}
    ep = cand["epoch"]
    radius = cand["match_radius"]
    ra_c, dec_c = propagate(a["ra"], a["dec"], a["pmra"], a["pmdec"], a["epoch"], 2016.0)
    rows = _gcns_rows_near(ra_c, dec_c, radius + 300.0, db_path=db_path)
    if rows is None:
        return {"status": "failed", "partners": [], "field_stars": [], "partial": False,
                "notes": ["blend-partner lookup failed: the GCNS table could not be read — no blend processing"]}
    partial = False
    # missing_10mas rows: J2000 position + SIMBAD PM / parallax (G1)
    cands = []
    for r in rows:
        if r["gcns_table"] == "main":
            if r.get("ra") is None:
                continue
            p = propagate(r["ra"], r["dec"], r.get("pmra") or 0.0, r.get("pmdec") or 0.0, 2016.0, ep)
            cands.append(dict(r, _pos=p, _ep0=2016.0, _name=swt.collapse_ws(r.get("star_name"))))
        else:
            info, st = (databases.simbad_astrometry(r["star_name"], family="blend") if r.get("star_name")
                        else (None, None))
            if st:
                partial = True
                notes.append(f"a partner SIMBAD lookup failed ({st}) for GCNS row {r.get('star_name')}")
            info = info or {}
            rr = dict(r, _simbad_failed=bool(st), _simbad_otype=(info.get("otype") or "").strip(),
                      pmra=info.get("pmra"), pmdec=info.get("pmdec"),
                      parallax=info.get("plx_value") or r.get("parallax"), parallax_error=info.get("plx_err"),
                      phot_g_mean_mag=info.get("g"), _simbad_main_id=info.get("main_id"))
            p = propagate(r["ra"], r["dec"], rr.get("pmra") or 0.0, rr.get("pmdec") or 0.0, 2000.0, ep)
            cands.append(dict(rr, _pos=p, _ep0=2000.0, _name=swt.collapse_ws(r.get("star_name"))))
    inside = [c for c in cands if sep_arcsec(c["_pos"][0], c["_pos"][1], cand["ra"], cand["dec"]) <= radius]
    # dedup FIRST (G13: a missing_10mas copy merges into its main row — the target's own included), then
    # remove the target: by source_id when it has one (L1 — never on a name match against another main
    # row, which can be a real companion carrying the same cross-matched name); a no-source_id target by
    # the G13 test against its own main_id (a name match, or the missing row's SIMBAD main_id).
    uniq, na_dedup = _dedup(inside, notes)
    partial = partial or na_dedup
    tsid = target.get("sid")
    tname = swt.collapse_ws(target.get("main_id"))
    # RG4: on a degraded H1 path the name half also takes the head, with K3 despacing both sides
    is_own = _own_name_matcher([tname, *(target.get("alt_names") or ())], bool(target.get("degraded")))
    kept = []
    for c in uniq:
        if c["gcns_table"] != "main":
            # G13 in full for every target (RG1 — a source_id target with no main row keeps its missing_10mas copy
            # here, since the dedup had no main row to merge it into)
            if is_own(c["_name"]) or is_own(c.get("_simbad_main_id")):
                continue
        elif tsid:
            if c.get("gaia_source_id") and int(c["gaia_source_id"]) == int(tsid):
                continue
        elif tname and c.get("gaia_source_id"):
            # L1 (MSG 306): a main row is the no-source_id target only by identity — its Gaia DR3 id resolves to
            # the target's own main_id (never by a name match)
            rec, st = databases.simbad_astrometry(f"Gaia DR3 {c['gaia_source_id']}", family="blend")
            if st:
                partial = True
                notes.append("a target-removal identity lookup failed — the GCNS row is kept as a partner")
            elif rec and swt.collapse_ws(rec.get("main_id")) == tname:
                continue
        kept.append(c)
    uniq = kept
    partners, field = [], []
    # S3: every Gaia source already in the blend (the target + each star in the beam)
    blend_gaia = {str(x["gaia_source_id"]) for x in uniq if x.get("gaia_source_id")}
    if tsid:
        blend_gaia.add(str(tsid))
    for c in uniq:
        verdict = _partner_tests(a, c, d_pc, target, catalog, notes)
        if verdict.get("failed_lookup"):
            partial = True
        name = verdict.get("main_id") or c.get("star_name") or f"Gaia DR3 {c.get('gaia_source_id')}"
        if verdict["partner"]:
            partners.append({"name": name, "sp_type": verdict.get("sp_type") or c.get("spectral_type"),
                             "radius_candidates": _partner_radius(c, verdict, blend_gaia, target.get("tic"),
                                                                  name=name, notes=notes),
                             "by_designation": verdict["by_s_only"],
                             "wd": bool((c.get("wd_prob") or 0) >= 0.5 or verdict.get("otype") == "WD*")})
        else:
            field.append(name)
    return {"status": None, "partners": partners, "field_stars": field, "notes": notes, "partial": partial}


def _dedup(rows, notes):
    """A star never blends with itself. GCNS **main** rows are distinct Gaia DR3 sources and are never merged
    (L1 — a shared cross-matched ``star_name`` or a twin under 2″ is a real companion). A ``missing_10mas`` row
    merges into a main row within 2″ at J2000 when the collapsed names match, or both resolve to the same
    SIMBAD ``main_id`` (G13 — a bounded blend-family lookup, only for such a pair; a failed lookup → distinct +
    ``not_authoritative``). Returns ``(unique_rows, not_authoritative)``."""
    from core import databases
    mains = [r for r in rows if r["gcns_table"] == "main"]
    miss = [r for r in rows if r["gcns_table"] != "main"]
    out, na = list(mains), False
    for r in miss:
        dup = False
        for o in mains:
            if sep_arcsec(r["ra"], r["dec"], *propagate(o["ra"], o["dec"], o.get("pmra") or 0.0,
                                                        o.get("pmdec") or 0.0, 2016.0, 2000.0)) > _BLEND_DEDUP_ARCSEC:
                continue
            if r["_name"] and r["_name"] == o["_name"]:
                dup = True
                break
            if (r.get("star_name") or "").startswith("** ") or r.get("_simbad_otype") == "**":
                dup = True                                # S1: the row is this star's SYSTEM entry, not a star
                break
            mid_m = r.get("_simbad_main_id")                 # already fetched (G1) for the missing row
            rec_o, st_o = (databases.simbad_astrometry(f"Gaia DR3 {o['gaia_source_id']}", family="blend")
                           if o.get("gaia_source_id") else (None, None))
            if st_o or r.get("_simbad_failed"):
                na = True
                notes.append("a duplicate-row identity lookup failed — the two GCNS rows are treated as distinct")
                continue
            if mid_m and rec_o and swt.collapse_ws(mid_m) == swt.collapse_ws(rec_o.get("main_id")):
                dup = True
                break
        if not dup:
            out.append(r)
    return out, na


def _partner_tests(a, c, d_pc, target, catalog, notes):
    """(P) / (M) / (S) for one GCNS star inside the beam (+ its SIMBAD identity)."""
    from core import databases
    v = {"partner": False, "by_s_only": False}
    ident = f"Gaia DR3 {c['gaia_source_id']}" if c.get("gaia_source_id") else c.get("star_name")
    info = None
    if ident:
        info, st = databases.simbad_astrometry(ident, family="blend")
        if st:
            v["failed_lookup"] = True
            notes.append(f"a partner SIMBAD lookup failed ({st}) for {ident}")
    if info:
        v.update(main_id=info.get("main_id"), sp_type=info.get("sp_type"), otype=(info.get("otype") or "").strip(),
                 oid=info.get("oid"))
    # (P)
    p_ok = None
    p1, e1, p2, e2 = a.get("plx"), a.get("plx_err"), c.get("parallax"), c.get("parallax_error")
    if None not in (p1, e1, p2, e2) and p1 > 0 and p2 > 0:
        p_ok = abs(p1 - p2) <= 3.0 * math.hypot(e1, e2)
    # (M)
    m_ok = None
    if c.get("pmra") is not None and c.get("pmdec") is not None and d_pc:
        s_arc = sep_arcsec(*propagate(a["ra"], a["dec"], a["pmra"], a["pmdec"], a["epoch"], 2016.0),
                           *propagate(c["ra"], c["dec"], c["pmra"], c["pmdec"], c["_ep0"], 2016.0))
        s_au = max(s_arc * d_pc, 1e-6)
        mt = target.get("mass")
        mp = None
        if info and info.get("main_id"):
            spec = {"name": info["main_id"], "sp_type": info.get("sp_type"),
                    "designations": ({"Gaia EDR3": f"Gaia DR3 {c['gaia_source_id']}"} if c.get("gaia_source_id")
                                     else {})}
            try:
                mp = (_partner_mass_seam(spec, catalog) or (None,))[0]
            except Exception:
                mp = None
        if mt is None or mp is None:
            m_tot = 2.0
            notes.append(f"the (M) proper-motion test used the 2 M☉ total-mass fallback for "
                         f"{(info or {}).get('main_id') or ident}")
        else:
            m_tot = mt + mp
        dmu = math.hypot((a["pmra"] or 0.0) - c["pmra"], (a["pmdec"] or 0.0) - c["pmdec"])
        m_ok = dmu <= 1000.0 * 42.12 * math.sqrt(m_tot / s_au) / (4.74047 * d_pc)
    # (S)
    s_ok = False
    if c.get("system_id") is not None and target.get("system_id") is not None and \
            c["system_id"] == target["system_id"]:
        s_ok = True
    elif _letter_pair(target.get("main_id"), (info or {}).get("main_id") or c.get("star_name")):
        s_ok = True
    elif info and info.get("main_id") and target.get("main_id"):
        pa, st1 = databases.simbad_parent(target["main_id"], family="blend")
        pb, st2 = databases.simbad_parent(info["main_id"], family="blend")
        if st1 or st2:
            v["failed_lookup"] = True
            notes.append("a SIMBAD parent lookup failed — the (S) test could not complete")
        elif pa and pb and set(pa) & set(pb):
            s_ok = True
    v["partner"] = bool(p_ok or m_ok or s_ok)
    v["by_s_only"] = bool(s_ok and not p_ok and not m_ok)
    return v


NOTE_PARTNER_RADIUS = ("blend partner '{name}': {fam} radius lookup failed ({st}) — that source was skipped in the "
                       "partner's radius chain (its next available source, or none, was used)")


def _partner_radius(c, verdict, blend_gaia=(), target_tic=None, *, name=None, notes=None):
    """The partner's radius candidates (TIC + Gaia) — a failed family degrades to its own chain, never silently:
    RG8 (MSG 315) — each failure (a failed / timed-out call, or a family forced unreachable) adds a ``notes`` entry
    naming the partner, the family and the status (status only, no flag). S3 (MSG 306): a TIC match that is the
    target's own object (its TIC or Gaia id) or another star already in the blend is rejected — the partner then
    has no catalog radius (a class-less partner → ``blend_partner_radius_missing``)."""
    own = str(c["gaia_source_id"]) if c.get("gaia_source_id") else None
    cands = []
    failed = (lambda fam, st: notes.append(NOTE_PARTNER_RADIUS.format(name=name, fam=fam, st=st))
              if notes is not None else None)
    if c.get("gaia_source_id"):
        if _hook("SPACE_APP_GAIA_RADIUS_FORCE_UNREACHABLE"):
            failed("Gaia", "unreachable")
        else:
            res = _gaia_radius_seam(c["gaia_source_id"])
            if isinstance(res, dict) and "error" in res:
                failed("Gaia", res.get("gaia_bound_reason") or "unreachable")
            elif isinstance(res, dict):
                p = res.get("parameters") or {}
                for k, src in (("radius_flame", "gaia_flame"), ("radius_gspphot", "gaia_gspphot")):
                    if p.get(k):
                        cands.append({"source": src, "value": float(p[k])})
    if _hook("SPACE_APP_TIC_FORCE_UNREACHABLE"):
        failed("TIC", "unreachable")
    else:
        ra2k, dec2k = propagate(c["ra"], c["dec"], c.get("pmra") or 0.0, c.get("pmdec") or 0.0, c["_ep0"], 2000.0)
        res, st = _family_call("tic", "cr26_tic", {"ra": round(ra2k, 6), "dec": round(dec2k, 6)},
                               lambda: _tic_query(ra2k, dec2k), "SPACE_APP_TIC_TIMEOUT")
        if st:
            failed("TIC", st)
        else:
            rows = [r for r in res["sources"] if r.get("rad")]
            if rows:
                best = min(rows, key=lambda r: r.get("sep") or 0)
                foreign = ((best.get("gaia") and best["gaia"] in blend_gaia and best["gaia"] != own)
                           or (target_tic and best.get("tic") == target_tic))
                if not foreign:
                    cands.insert(0, {"source": "tic", "value": float(best["rad"])})
    return cands


# ── 4.7 the orchestrator ─────────────────────────────────────────────────────────
def binary_sid(designations):
    from core import binary
    return binary.gaia_source_id_from_designations(designations)


def a_candidate(main_id):
    """G12 — the A-component candidate of a LETTERLESS head (``* alf Cen`` → ``* alf Cen A``); ``None`` for a
    main_id that already names a component (``* 61 Cyg B``, ``HD 239960A``)."""
    import re
    from core import stellar_mass
    mid = swt.collapse_ws(main_id)
    if not mid or re.search(r"[\s\d][A-Z]$", mid):
        return None
    return next(iter(sorted(stellar_mass.component_candidate_ids(mid, "A"))), None)


def cr26_supplied(args_or_spec, *, getter=None):
    """The CR-26 supplied inputs from an argparse Namespace (``getattr``) or a component spec dict."""
    g = getter or (lambda k: getattr(args_or_spec, k, None))
    return {k: g(k) for k in ("log_fx", "log_fx_limit", "radius_rsun", "prot_days")}


def ignored_input_notes(sup):
    """§26.7 — a valid CR-26 input on a path / star where no CR-26 tier can use it → a note, never silent."""
    names = {"log_fx": "--log-fx / log_fx=", "log_fx_limit": "--log-fx-limit / log_fx_limit=",
             "radius_rsun": "--radius-rsun / radius_rsun=", "prot_days": "--prot-days / prot_days="}
    return [sw.NOTE_IGNORED_INPUT.format(name=names[k]) for k in names if (sup or {}).get(k) is not None]
def _k3_variant(s):
    import re
    s = swt.collapse_ws(s)
    return re.sub(r"\s([A-D])$", r"\1", s)


def resolve_star_wind_inputs(identity, supplied, *, catalog=None, allow_network=True, db_path=None):
    """Resolve one star's CR-26 inputs → ``stellar_wind.StarWindInputs``.

    ``identity``: ``{sp_type, main_id, domain, cr25_letter, designations, sl_failed, candidate, plx,
    d_pc, mass, system_id, measured_candidates, noncoronal_rate}`` — the strings the caller holds (all SIMBAD
    identity resolution for CR-26 happens here, behind ``allow_network``). ``supplied``: the CR-26 inputs +
    the state selectors. ``allow_network=False`` (``--component``, ``--spectral-type``, the offline conftest)
    calls no fetcher."""
    from core import binary
    inp = sw.StarWindInputs(
        sp_type=identity.get("sp_type"), main_id=identity.get("main_id"),
        domain=identity.get("domain") or "main_sequence", cr25_letter=identity.get("cr25_letter"),
        noncoronal_rate=identity.get("noncoronal_rate"), **{k: supplied.get(k) for k in (
            "supplied_rate", "log_fx", "log_fx_limit", "radius_rsun", "prot_days", "wind_state",
            "wind_class", "mass_loss_source", "wind_speed")},
        active_otype=bool(supplied.get("active_otype")))
    notes = list(identity.get("notes") or [])
    inp.identity_failed = bool(identity.get("sl_failed"))
    letter, _sub, _sd = sw.parse_sp(inp.sp_type)
    scope = sw.in_scope(inp.domain, letter)

    blend_target = None          # S2 (MSG 306): the blend's target is the resolved A component, never the head
    # ── exclusion-system component A: its own identity through the A candidate (G12: else the head) ──
    if identity.get("component_a") and identity.get("candidate") and (scope or inp.domain == "evolved"):
        head, cand_a = identity.get("main_id"), identity["candidate"]
        rec, st = _identity_lookup(cand_a) if allow_network else (None, None)
        if allow_network:
            inp.a_record = (rec, st)                    # CR-24 reuses it (the head → A record for the velocity)
        if rec and swt.collapse_ws(rec.get("main_id")) != swt.collapse_ws(head):
            plx = rec.get("plx_value")
            identity = dict(identity, main_id=rec.get("main_id"), designations=rec.get("designations"),
                            ra=rec.get("ra"), dec=rec.get("dec"),
                            d_pc=(1000.0 / plx if (plx and plx > 0) else identity.get("d_pc")),
                            candidate=None, extra_ids=[head])
            if not (plx and plx > 0) and identity.get("d_pc"):
                notes.append("component A has no parallax of its own — the system head's parallax is used")
            inp.main_id = identity["main_id"]
        elif st:
            identity = dict(identity, sl_failed=True, extra_ids=[head])
            inp.main_id = head
            # S2: the candidate string serves the name half; RG4: the head's own source_id still removes its row
            blend_target = {"main_id": cand_a, "sid": binary_sid(identity.get("designations")),
                            "degraded": True, "alt_names": [head]}
        else:
            # answered with no distinct object (or offline): the head is A; offline keeps the pure string try
            identity = dict(identity, candidate=(None if allow_network else cand_a), extra_ids=[])
            if allow_network:
                notes.append(f"component A has no distinct SIMBAD object ('{cand_a}') — the system "
                             f"head '{head}' is read as A; the X-ray ladder runs at the head's own position")

    # ── measured-table identity (§26.2; G12 / H1 / K3) ──
    t = swt.load_cr26_tables()["MEASURED"]
    ids = [x for x in [identity.get("main_id")] + list(identity.get("extra_ids") or []) if x]
    hit = any(swt.collapse_ws(x) in t for x in ids)
    cand = identity.get("candidate")
    if not hit and identity.get("sl_failed"):
        # H1: the component's own identity lookup failed → match the table on the candidate string
        ids_try = [x for x in (cand, _k3_variant(cand) if cand else None) if x]
        found = next((x for x in ids_try if swt.collapse_ws(x) in t), None)
        notes.append(f"the SIMBAD identity lookup for '{cand}' failed — the measured table was matched on the "
                     "candidate string" + ("" if found else " (no row found)"))
        if found:
            ids.append(found)
            hit = True
            if not inp.sp_type:                         # the row supplies the class (as H4 does for main_id=)
                inp.sp_type = t[swt.collapse_ws(found)]["sp_type_simbad"]
                letter, _sub, _sd = sw.parse_sp(inp.sp_type)
                scope = sw.in_scope(inp.domain, letter)
        else:
            inp.measured_miss_not_authoritative = True
    if not hit and cand and not identity.get("sl_failed"):
        rec, st = (_identity_lookup(cand) if allow_network else (None, None))
        if allow_network:
            inp.a_record = (rec, st)                    # CR-24 reuses it (the head → A record for the velocity)
        if rec and swt.collapse_ws(rec.get("main_id")) != swt.collapse_ws(identity.get("main_id")):
            blend_target = {"main_id": rec.get("main_id"),
                            "sid": binary_sid(rec.get("designations"))}     # S2: the resolved A is the target
        elif st:
            # S2: the candidate string (H1) serves the name half; RG4: the star's own source_id removes its row
            blend_target = {"main_id": cand, "sid": binary_sid(identity.get("designations")),
                            "degraded": True, "alt_names": [identity.get("main_id")]}
        if rec:
            ids.append(rec.get("main_id"))
            hit = swt.collapse_ws(rec.get("main_id")) in t
            if hit:
                notes.append(f"the letterless head '{identity.get('main_id')}' was read as its A component "
                             f"'{rec.get('main_id')}' for the measured table; the X-ray ladder runs at the head's "
                             "own position")
        elif st or not allow_network:
            ids_try = [x for x in (cand, _k3_variant(cand)) if x]
            found = next((x for x in ids_try if swt.collapse_ws(x) in t), None)
            if st:
                notes.append(f"the SIMBAD identity lookup for '{cand}' failed — the measured table was matched on "
                             "the candidate string" + ("" if found else " (no row found)"))
            if found:
                ids.append(found)
                hit = True
                if not st:
                    notes.append(f"the letterless head '{identity.get('main_id')}' was read as its A component "
                                 f"'{found}' for the measured table")
            elif st:
                inp.measured_miss_not_authoritative = True
    inp.measured_ids = ids

    # which lookups the star needs
    evolved_only = inp.domain == "evolved"
    if not scope or evolved_only:
        inp.not_run_reason = "out_of_scope"
        inp.notes = notes
        return inp
    if not allow_network:
        inp.not_run_reason = "network_disabled" if identity.get("main_id") else "no_identity"
        inp.notes = notes
        return inp
    supplied_fx = inp.log_fx is not None or inp.log_fx_limit is not None
    d_pc = identity.get("d_pc")
    # the target's own names for the 5″ neighbour test (the resolved A / the degraded H1 candidate + head)
    own_kw = ({"own_names": [blend_target["main_id"], *blend_target.get("alt_names", [])],
               "degraded": bool(blend_target.get("degraded"))} if blend_target else {})
    sid = binary.gaia_source_id_from_designations(identity.get("designations"))

    if supplied_fx:
        inp.not_run_reason = "supplied"
        if inp.radius_rsun is None and identity.get("ra") is not None:
            # the target's position for the radius-ambiguity tests: its local GCNS row (J2016 + PM) when it has
            # one, else SIMBAD's J2000 (no astrometry lookup on this path — CP5)
            gro = _gcns_row_by_sid(sid, db_path=db_path) if sid else None
            if gro and gro.get("ra") is not None:
                a = {"ra": gro["ra"], "dec": gro["dec"], "epoch": 2016.0, "pmra": gro.get("pmra") or 0.0,
                     "pmdec": gro.get("pmdec") or 0.0}
            else:
                a = {"ra": identity["ra"], "dec": identity["dec"], "epoch": 2000.0, "pmra": 0.0, "pmdec": 0.0}
            c, s, co, gn = radius_candidates(a, sid, main_id=inp.main_id, db_path=db_path, **own_kw)
            inp.radius_candidates, inp.radius_status, inp.cone_other, inp.gcns_neighbour = c, s, co, gn
        inp.notes = notes
        return inp
    if not inp.main_id and not sid:
        inp.not_run_reason = "no_identity"           # nothing to query (e.g. a B with no SIMBAD object — CP5)
        inp.notes = notes
        return inp
    if not d_pc:
        inp.not_run_reason = "no_distance"
        inp.notes = notes
        return inp

    a = star_astrometry({"main_id": inp.main_id, "gaia_sid": sid}, db_path=db_path)
    notes.extend(a.get("notes") or [])
    inp.network = True
    inp.d_pc = d_pc
    if a.get("status") or a.get("ra") is None:
        inp.astrom_status = a.get("status") or "error"
        inp.rungs = [{"rung": r, "status": "not_queried", "cand": None} for r in sw.RUNGS]
        if inp.radius_rsun is None:                   # RG7: the radius chain was not attempted either
            inp.radius_status = {k: "not_queried" for k in ("tic", "gaia", "simbad_cone")}
        inp.notes = notes
        return inp
    inp.g_mag, inp.g_status = a.get("g"), a.get("g_status")
    if inp.radius_rsun is None:
        c, s, co, gn = radius_candidates(a, sid, oid=a.get("oid"), main_id=inp.main_id, db_path=db_path, **own_kw)
        inp.radius_candidates, inp.radius_status, inp.cone_other, inp.gcns_neighbour = c, s, co, gn
    rungs = xray_ladder(a)
    in_fp = not any(r["rung"] == "eRASS1" and r["status"] == "out_of_footprint" for r in rungs)
    survey_det = any(r["status"] == "detection" and r["rung"] != "XMM" for r in rungs)
    if not survey_det:
        inp.limit = survey_limit(a, in_fp)
    # the blend for the first-detection rung's matched source (and XMM when it is the candidate)
    bt = blend_target or {"main_id": inp.main_id, "sid": sid}
    gro = _gcns_row_by_sid(bt["sid"], db_path=db_path) if bt["sid"] else None
    tic = next((c.get("tic") for c in inp.radius_candidates or [] if c.get("source") == "tic"), None)
    target = {"main_id": bt["main_id"], "sid": bt["sid"], "mass": identity.get("mass"), "tic": tic,
              "system_id": identity.get("system_id") or (gro or {}).get("system_id"),
              "degraded": bt.get("degraded", False), "alt_names": bt.get("alt_names", [])}
    for rr in rungs:
        if rr["status"] == "detection":
            rr["cand"]["blend"] = blend_partners(a, rr["cand"], d_pc, target, catalog, db_path=db_path)
            break
    inp.rungs = rungs
    inp.notes = notes
    return inp
