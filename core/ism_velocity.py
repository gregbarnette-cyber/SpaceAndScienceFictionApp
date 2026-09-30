"""CR-24 — the per-star V_ISM for ``exclusion-boundary`` / ``exclusion-system``.

V_ISM = |v★ − v_cloud| (both heliocentric Galactic) instead of the fixed 26 km/s, except that a star with a Wood-measured
wind rate takes the V_ISM that rate was inferred at (D1). V_ISM feeds only the research-grade WALL (its route test) —
never the standoff, never a wind rate. Contract: the WB spec ``spaceapp-change-request-CR24-exclusion-vism-vectorial-
derive.md``; plan ``completed_plans/PHASE_CR24_31_32_PLAN.md`` §3.

Layers (pure unless marked):
- **velocity math** (§CR-24.1): SIMBAD PM + parallax + RV → astropy ``Galactic`` (heliocentric — NOT LSR) (U, V, W);
  the RV gate (grades D/E; |v★| > 1000 km/s); the sky-plane lower bound |P⊥(v★_t − v_cloud)| when no RV passes;
  the ⚑1 primary-RV fallback; an unusable PM/parallax (F4: the RV-0 speed or the floor ≥ 1000 km/s).
- **precedence** (§CR-24.2, ⚑8): supplied → LB cavity → ``--cloud`` → the measured row → the LIC derive within
  ``--clic-max-pc`` → 26 ``assumed``.
- **range evaluation** (DQ2 cloud set; DQ3 lower bound — exact, at the route boundaries).
- **application** (``apply_v_ism``) — the one helper both subcommands call on their computed wall (plan §3.5b).
- **network** (marked): the bounded SIMBAD velocity lookup by a RAW resolved ``main_id``, the head → A-record
  resolution through CR-26's own identity resolver, and the test hooks.
"""

import math
import os

from core import exclusion_wall as ew
from core import ism_velocity_tables as ivt
from core import shared

V_MAX = 1000.0                      # the RV gate's ceiling = the DQ3 interval's top (ruled session 57)
V_ISM_ASSUMED = ew._V_ISM_DEF       # the wall model's own default (never re-declared)
CONVENTION = "astropy Galactic, heliocentric, U→GC"
_EPS = 1e-9                         # the one-sided offset at a route boundary (relative)

# ── notes (words a card can quote) ──────────────────────────────────────────────────────────────────────────────
NOTE_RV_GRADE = "SIMBAD RV {rv:g} km/s, quality {g}, not used"
NOTE_RV_CEILING = "SIMBAD RV {rv:g} km/s (quality {g}) gives |v★| {v:.1f} km/s, above 1000, not used"
NOTE_RV_NO_GRADE = "SIMBAD RV {rv:g} km/s has no quality grade — used (only grades D and E are gated)"
NOTE_RV0_CEILING = ("the heliocentric speed at RV 0 is {v:.1f} km/s, above 1000 — PM/parallax not used "
                    "(no RV could pass the ceiling)")
NOTE_FLOOR_CEILING = "sky-plane speed {v:.1f} km/s above 1000 — PM/parallax not used"
NOTE_NO_ASTROM = "SIMBAD gives '{mid}' no {what} — no space velocity"
NOTE_PRIMARY_RV = ("no usable RV of its own — its primary '{pid}' RV {rv:g} km/s (quality {g}) is used with its own "
                   "proper motion and parallax (a borrowed-RV vector: its error is of order the pair's orbital motion)")
NOTE_LOOKUP_FAILED = "the SIMBAD velocity lookup for '{mid}' failed ({st}) — no space velocity"
NOTE_NO_RECORD = "SIMBAD has no record '{mid}' for the velocity lookup — no space velocity"
NOTE_A_FAILED = ("the SIMBAD identity lookup for the A candidate '{cand}' failed ({st}) — no space velocity (the "
                 "system record '{head}' is not used)")
NOTE_HEAD_A = "the letterless head '{head}' takes its velocity from its A component '{a}'"
NOTE_DC1 = ("the primary '{mid}' is the target's own SIMBAD record (no separate A component resolves) — its own RV is "
            "used; it may be a blend")
NOTE_BEYOND_CUT = "beyond --clic-max-pc ({d:.2f} pc > {cut:g} pc) — V_ISM assumed 26"
NOTE_BEYOND_7PC = ("the host lies beyond 7 pc ({d:.2f} pc): Wood 2021 justifies one universal ISM vector, and the warm "
                   "partly neutral medium the wall model assumes, within 7 pc only — the derived V_ISM is less certain")
NOTE_OVERRIDE_ROW = ("the measured rate was inferred at V_ISM {n:g} km/s (Wood 2021 Table 3); this run uses {how}")
NOTE_CLOUD_FLOOR_ROW = ("--cloud {c} gives only a lower bound ({f:.1f} km/s, no usable RV) — the measured row's V_ISM "
                        "{n:g} km/s (Wood 2021 Table 3) is kept")
NOTE_IGNORED_NO_LOOKUP = "{flag} ignored: no velocity lookup runs on this path"
NOTE_IGNORED_BY_STEP = "{flag} ignored: {by} set V_ISM, so no velocity derive runs"
NOTE_LB_IGNORED = "--lb-cavity ignored: no identity on this path"
NOTE_ROUTE_XCHECK = ("the derived V_ISM {d:.1f} km/s would set route {r1}; the wall uses {v:g} km/s ({prov}) → {r2}")
NOTE_LB = ("V_ISM is a lower bound (no usable RV) — {route_clause}; the wall is the largest the bound allows; "
           "v_ism_kms, m_f and r_ap_au are at the floor ({f:.1f} km/s), the wall and its band at {v:.1f} km/s")
NOTE_LB_ZONE = ("the zone's medium member '{mid}' has a lower-bound V_ISM (no usable RV) — {route_clause}; the "
                "combined-wind wall is the largest the bound allows (the floor {f:.1f} km/s, the wall at {v:.1f} km/s)")
_ROUTE_PROV = "the route is provisional"
_ROUTE_NOT_PROV = "no bow-shock route is possible above the floor"
NOTE_LOWER_EDGE_VMAX = ("the range's lower edge, {w:.4g} AU, is the wall at V_max = 1000 km/s ({route}) — the RV gate's "
                        "ceiling, not a physical minimum")
NOTE_LOWER_EDGE_BURIAL = ("the range's lower edge, {w:.4g} AU, is the wall just under the burial speed {vb:.1f} km/s "
                          "({route})")
NOTE_LOWER_EDGE_OTHER = "the range's lower edge, {w:.4g} AU, is the wall at {v:.1f} km/s ({route})"
NOTE_CLOUD_SET = ("the route branch changes across the LIC-like cloud set (R&L 2008 clouds within 15 km/s of the LIC "
                  "vector, each at the default medium — a spread, not a bound): {names} give {branch}")
NOTE_ISM_MEASURED = ("A measured Ṁ was inferred at the V_ISM Wood 2021 Table 3 lists for this star ({n:g} km/s); this "
                     "run uses {v:g} km/s ({prov}).")

_BOW = ("bow_shock", "bow_shock_marginal")


# ── velocity math (pure) ───────────────────────────────────────────────────────────────────────────────────────
def _norm(v):
    return math.sqrt(sum(x * x for x in v))


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def space_velocity(ra, dec, plx_mas, pmra, pmdec, rv):
    """Heliocentric Galactic (U, V, W) km/s — astropy ``Galactic`` (U → the Galactic centre), never LSR."""
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    c = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, distance=(1000.0 / plx_mas) * u.pc,
                 pm_ra_cosdec=pmra * u.mas / u.yr, pm_dec=pmdec * u.mas / u.yr,
                 radial_velocity=rv * u.km / u.s, frame="icrs")
    d = c.galactic.velocity
    return (float(d.d_x.to_value(u.km / u.s)), float(d.d_y.to_value(u.km / u.s)), float(d.d_z.to_value(u.km / u.s)))


def los_unit(ra, dec):
    """The heliocentric Galactic line-of-sight unit vector toward (ra, dec)."""
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    g = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs").galactic
    lr, br = g.l.radian, g.b.radian
    return (math.cos(br) * math.cos(lr), math.cos(br) * math.sin(lr), math.sin(br))


def sky_plane_floor(v_rv0, v_cloud, los):
    """min over the unknown RV of |v★ − v_cloud| = |P⊥(v★_t − v_cloud)| = √(|d|² − (d·l̂)²), d = v★(RV 0) − v_cloud
    (v★(RV) = v★(RV 0) + RV·l̂ exactly) — NOT the naive |v★_t − v_cloud|."""
    d = _sub(v_rv0, v_cloud)
    dl = sum(x * y for x, y in zip(d, los))
    return math.sqrt(max(0.0, sum(x * x for x in d) - dl * dl))


def _num(x):
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _rv_gate(rv, grade, vec):
    """``(passes, note)`` — the §CR-24.1 gate (D3, DQ5; F3): grade D/E, or |v★| > 1000, is treated as missing; a null
    grade passes the grade rule with a note."""
    if rv is None:
        return False, None
    g = (grade or "").strip().upper() or None
    if g in ("D", "E"):
        return False, NOTE_RV_GRADE.format(rv=rv, g=g)
    speed = _norm(vec)
    if speed > V_MAX:
        return False, NOTE_RV_CEILING.format(rv=rv, g=g or "none", v=speed)
    return True, (NOTE_RV_NO_GRADE.format(rv=rv) if g is None else None)


def resolve_velocity(rec, primary=None):
    """One SIMBAD velocity record (``{main_id, ra, dec, pmra, pmdec, plx_value, rvz_radvel, rvz_qual}``) → the
    velocity dict ``{provenance, space_velocity, v0, v, los, d_pc, record, notes}``. ``primary`` (a component's
    ⚑1 fallback, exclusion-system only): ``{main_id, rv, grade}`` — the A record's own RV, borrowed only if the
    component's own RV is missing or gated and the borrowed vector passes the gate."""
    notes = []
    mid = (rec or {}).get("main_id")
    ra, dec = _num((rec or {}).get("ra")), _num((rec or {}).get("dec"))
    pmra, pmdec, plx = (_num((rec or {}).get(k)) for k in ("pmra", "pmdec", "plx_value"))
    missing = [w for w, v in (("position", ra if dec is not None else None), ("proper motion",
               pmra if pmdec is not None else None)) if v is None]
    if plx is None or plx <= 0:
        missing.append("positive parallax")
    if missing:
        notes.append(NOTE_NO_ASTROM.format(mid=mid, what=" / ".join(missing)))
        return _unavailable(notes, record=mid)
    v0 = space_velocity(ra, dec, plx, pmra, pmdec, 0.0)
    if _norm(v0) > V_MAX:                                      # F4 (WB MSG 326): no RV could pass the ceiling
        notes.append(NOTE_RV0_CEILING.format(v=_norm(v0)))
        return _unavailable(notes, record=mid)
    los = los_unit(ra, dec)
    rv, grade = _num(rec.get("rvz_radvel")), (rec.get("rvz_qual") or None)
    own_vec = space_velocity(ra, dec, plx, pmra, pmdec, rv) if rv is not None else None
    ok, gnote = _rv_gate(rv, grade, own_vec) if rv is not None else (False, None)
    if gnote:
        notes.append(gnote)
    sv = {"pmra": pmra, "pmdec": pmdec, "plx": plx, "rv": rv, "rv_grade": grade, "rv_used": bool(ok),
          "rv_source": None, "convention": CONVENTION}
    vec, prov = None, "tangential_lower_bound"
    if ok:
        vec, prov, sv["rv_source"] = own_vec, "uvw", "own"
    elif primary and primary.get("rv") is not None:
        p_vec = space_velocity(ra, dec, plx, pmra, pmdec, primary["rv"])
        p_ok, _pn = _rv_gate(primary["rv"], primary.get("grade"), p_vec)
        if p_ok:
            vec, prov, sv["rv_source"] = p_vec, "uvw", "primary"
            notes.append(NOTE_PRIMARY_RV.format(pid=primary.get("main_id"), rv=primary["rv"],
                                                g=primary.get("grade") or "none"))
    shown = vec if vec is not None else v0
    sv.update({"U": shown[0], "V": shown[1], "W": shown[2], "total": _norm(shown)})
    return {"provenance": prov, "space_velocity": sv, "v0": v0, "v": vec, "los": los, "d_pc": 1000.0 / plx,
            "record": mid, "notes": notes}


def _unavailable(notes, record=None):
    return {"provenance": "unavailable", "space_velocity": None, "v0": None, "v": None, "los": None, "d_pc": None,
            "record": record, "notes": list(notes)}


def v_ism_from(vel, cloud):
    """``(V_ISM, provenance)`` against a named cloud: ``uvw`` → |v★ − v_cloud| (``derived``); the sky-plane floor
    (``derived_tangential_lower_bound``); ``None`` when v★ is unavailable or the floor reaches 1000 km/s (F4)."""
    if not vel or vel["provenance"] == "unavailable":
        return None
    vc = ivt.cloud_vector(cloud)
    if vel["provenance"] == "uvw":
        return _norm(_sub(vel["v"], vc)), "derived"
    f = sky_plane_floor(vel["v0"], vc, vel["los"])
    if f >= V_MAX:
        return None
    return f, "derived_tangential_lower_bound"


# ── the precedence (§CR-24.2, ⚑8) — pure ─────────────────────────────────────────────────────────────────────────
def resolve_v_ism(*, path, supplied=None, lb_cavity=False, cloud=None, clic_max_pc=15.0, measured_row_key=None,
                  vel=None, floor_hook=None):
    """The V_ISM decision. ``path`` ∈ {``star`` (a lookup ran — ``vel`` is its result, possibly ``unavailable``),
    ``component`` (``exclusion-system --component`` — no lookup; steps 1, 2, 4, 6 + the zone floor test hook),
    ``none`` (``--spectral-type`` / bare ``--mass-msun`` / ``--object`` — steps 1, 6)}. ``measured_row_key``: the CR-26
    measured row whose rate is IN USE (the model's used tier is ``measured``), else None.

    Returns ``{v_ism_kms, v_ism_provenance, v_cloud_used, v_cloud_chi2, v_ism_derived_kms, clic_domain, mode,
    v_ism_range_kms, cloud_points, derived_xcheck, notes}`` — ``mode`` ∈ {point, lower_bound}; ``cloud_points`` =
    ``[(cloud, V)]`` over the DQ2 set for a ``derived`` V_ISM; ``derived_xcheck`` = the measured star's derive
    ``(V, provenance)`` for the different-route note."""
    notes = []
    row_v = ivt.measured_row_vism(measured_row_key) if measured_row_key else None
    usable = bool(vel) and vel.get("provenance") not in (None, "unavailable")
    if usable and vel["provenance"] == "tangential_lower_bound":
        # F4 (WB MSG 326): a sky-plane floor reaching 1000 km/s against the cloud in use → PM / parallax unusable:
        # velocity_provenance ``unavailable`` and no other derive (precedence falls through to step 4 or 6)
        cname = cloud or ivt.DEFAULT_CLOUD
        f = sky_plane_floor(vel["v0"], ivt.cloud_vector(cname), vel["los"])
        if f >= V_MAX:
            notes.append(NOTE_FLOOR_CEILING.format(v=f))
            vel.update(provenance="unavailable", space_velocity=None, v=None)
            usable = False
    d_pc = vel.get("d_pc") if usable else None

    cloud_d = v_ism_from(vel, cloud) if (path == "star" and cloud and usable) else None
    within = usable and d_pc is not None and d_pc <= clic_max_pc
    lic_d = v_ism_from(vel, ivt.DEFAULT_CLOUD) if (path == "star" and within) else None

    out = {"v_ism_kms": V_ISM_ASSUMED, "v_ism_provenance": "assumed", "v_cloud_used": None, "v_cloud_chi2": None,
           "v_ism_derived_kms": None, "clic_domain": None, "mode": "point", "v_ism_range_kms": None,
           "cloud_points": None, "derived_xcheck": None, "notes": notes}

    def _derived(val, prov, cname):
        out.update({"v_ism_kms": val, "v_ism_provenance": prov, "v_cloud_used": cname,
                    "v_cloud_chi2": ivt.cloud_chi2(cname),
                    "clic_domain": ("within_7pc" if d_pc <= 7.0 else "beyond_7pc") if d_pc is not None else None})
        if d_pc is not None and d_pc > 7.0:
            notes.append(NOTE_BEYOND_7PC.format(d=d_pc))
        if prov == "derived_tangential_lower_bound":
            out["mode"], out["v_ism_range_kms"] = "lower_bound", [val, V_MAX]
        else:
            pts = [(c, v_ism_from(vel, c)[0]) for c in ivt.cloud_set()]
            out["cloud_points"] = pts
            vs = [v for _c, v in pts]
            out["v_ism_range_kms"] = [min(vs), max(vs)]

    # the measured star's own derive (Q2 — whichever step sets V_ISM; null beyond the cut with no --cloud)
    if row_v is not None and path == "star":
        xd = cloud_d if cloud else lic_d
        if xd is not None:
            out["v_ism_derived_kms"], out["derived_xcheck"] = xd[0], xd

    if supplied is not None:                                               # step 1
        out.update({"v_ism_kms": float(supplied), "v_ism_provenance": "supplied"})
        if row_v is not None:
            notes.append(NOTE_OVERRIDE_ROW.format(n=row_v, how=f"the supplied --v-ism {float(supplied):g} km/s"))
        return out
    if lb_cavity and path in ("star", "component"):                        # step 2
        if row_v is not None:
            notes.append(NOTE_OVERRIDE_ROW.format(n=row_v, how="26 km/s (--lb-cavity: a Local-Bubble-cavity host)"))
        return out
    if cloud_d is not None:                                                # step 3
        if row_v is not None and cloud_d[1] != "derived":                  # D-W3-2: a floor keeps the row
            notes.append(NOTE_CLOUD_FLOOR_ROW.format(c=cloud, f=cloud_d[0], n=row_v))
        else:
            _derived(cloud_d[0], cloud_d[1], cloud)
            if row_v is not None:
                notes.append(NOTE_OVERRIDE_ROW.format(n=row_v, how=f"the caller's cloud ({cloud})"))
            return out
    if row_v is not None:                                                  # step 4
        out.update({"v_ism_kms": float(row_v), "v_ism_provenance": "measured_row"})
        return out
    if lic_d is not None:                                                  # step 5
        _derived(lic_d[0], lic_d[1], ivt.DEFAULT_CLOUD)
        return out
    if path == "component" and floor_hook is not None:                     # the zone test hook (Q5) — below step 4
        out.update({"v_ism_kms": float(floor_hook), "v_ism_provenance": "derived_tangential_lower_bound",
                    "v_cloud_used": ivt.DEFAULT_CLOUD, "v_cloud_chi2": ivt.cloud_chi2(ivt.DEFAULT_CLOUD),
                    "mode": "lower_bound", "v_ism_range_kms": [float(floor_hook), V_MAX]})
        return out
    if path == "star" and usable and d_pc is not None and d_pc > clic_max_pc:   # step 6
        notes.append(NOTE_BEYOND_CUT.format(d=d_pc, cut=clic_max_pc))
    return out


# ── range evaluation — exact, at the route boundaries (DQ2 / DQ3; plan §3.5) ───────────────────────────────────
def _kw(inputs, r_ex, wind_class):
    return dict(v_wind=inputs["v_wind"], c_ms=inputs["c_ms"], n_cloud=inputs["n_cloud"], r_ex=r_ex,
                wind_class=wind_class, t_phase=inputs["t_phase"], f_shock=inputs["f_shock"],
                m_shock_min=inputs["m_shock_min"], c_ms_band=inputs["c_ms_band"])


def wall_at(inputs, v_ism, r_ex, wind_class=None, wdot=None):
    return ew.compute_wall(wdot=(inputs["wdot"] if wdot is None else wdot), v_ism=v_ism,
                           **_kw(inputs, r_ex, wind_class))


def _apex_k(inputs, wdot):
    """K in r_ap = K / V_ISM — read off the wall model itself (``compute_wall``'s ``r_ap_au`` × V_ISM at a reference
    V), so the breakpoints can never drift from the model they bracket."""
    ref = ew._V_ISM_ANCHOR
    return wall_at(inputs, ref, None, wdot=wdot)["r_ap_au"] * ref


def burial_speed(inputs, wdot, r_ex):
    """The V_ISM at which f·r_ap = r_ex (above it the apex is buried and the wind term stands); None with no standoff."""
    if not r_ex or r_ex <= 0 or not wdot or wdot <= 0:
        return None
    return inputs["f_shock"] * _apex_k(inputs, wdot) / r_ex


def breakpoints(inputs, wdot, r_ex):
    """The route-change speeds: the shock threshold M_shock_min·c_ms, r_ap = r_ex, and the burial speed. Every cap
    onset / edge crossing is a continuous kink (no extremum) — the CP0 math review."""
    bps = [inputs["m_shock_min"] * inputs["c_ms"]]
    if r_ex and r_ex > 0 and wdot and wdot > 0:
        k = _apex_k(inputs, wdot)
        bps += [k / r_ex, inputs["f_shock"] * k / r_ex]
    return bps


def extremes(fn, extract, a, b, bps):
    """Max / min of ``extract(fn(V))`` over [a, b]: the model is non-increasing on each route piece, so the extremes
    sit at a, b and one-sidedly at each boundary. Returns ``(max, min)`` — each ``(value, V, wall_dict)``; the max's
    V is the LOWEST that gives it (O-2)."""
    pts = [a, b]
    for bp in bps:
        for v in (bp * (1 - _EPS), bp * (1 + _EPS)):
            if a < v < b:
                pts.append(v)
    evals = [(extract(w), v, w) for v in sorted(set(pts)) for w in (fn(v),)]
    evals = [e for e in evals if e[0] is not None]
    if not evals:
        return None, None
    top = max(e[0] for e in evals)
    hi = min((e for e in evals if e[0] == top), key=lambda e: e[1])
    lo = min(evals, key=lambda e: (e[0], -e[1]))
    return hi, lo


def provisional(inputs, wdot, r_ex, floor):
    """DQ3 / D-W3-1 closed form (+ WB MSG 328): a bow-shock route is possible within [floor, V_max] — the burial speed
    exceeds both the floor and M_shock_min·c_ms, and that threshold lies below V_max."""
    vb = burial_speed(inputs, wdot, r_ex)
    thr = max(floor, inputs["m_shock_min"] * inputs["c_ms"])
    return bool(vb is not None and vb > thr and thr < V_MAX)


def _band0(w):
    return (w.get("wall_band_au") or [None, None])[0]


def _band1(w):
    return (w.get("wall_band_au") or [None, None])[1]


def lower_bound_wall(inputs, r_ex, wind_class, floor, wdot=None):
    """DQ3 for one wall (a single star, or a zone's combined wall at ``wdot`` against its comparator). Returns
    ``{wall (the dict at the max's V), v_at, range, provisional, lower_kind, lower_note}``."""
    wdot = inputs["wdot"] if wdot is None else wdot
    fn = (lambda v: wall_at(inputs, v, r_ex, wind_class, wdot))
    hi, lo = extremes(fn, lambda w: w.get("wall_au"), floor, V_MAX, breakpoints(inputs, wdot, r_ex))
    if hi is None:
        return None
    prov = provisional(inputs, wdot, r_ex, floor)
    vb = burial_speed(inputs, wdot, r_ex)
    lo_route = lo[2]["wall_route"]
    if lo[1] == V_MAX:
        kind, note = "at_vmax", NOTE_LOWER_EDGE_VMAX.format(w=lo[0], route=lo_route)
    elif vb is not None and abs(lo[1] - vb * (1 - _EPS)) <= 1e-12 * vb:
        kind, note = "just_under_burial", NOTE_LOWER_EDGE_BURIAL.format(w=lo[0], vb=vb, route=lo_route)
    else:
        kind, note = "other", NOTE_LOWER_EDGE_OTHER.format(w=lo[0], v=lo[1], route=lo_route)
    return {"wall": hi[2], "v_at": hi[1], "range": [lo[0], hi[0]], "provisional": prov, "lower_kind": kind,
            "lower_note": note}


def lower_bound_band_edges(inputs, r_ex, wind_class, floor, lo_wdot, hi_wdot):
    """D-C3: each wind-band edge at its largest value over [floor, V_max], with its own route at that V."""
    out = []
    for wdot, ex in ((lo_wdot, _band0), (hi_wdot, _band1)):
        fn = (lambda v, _w=wdot: wall_at(inputs, v, r_ex, wind_class, _w))
        hi, _lo = extremes(fn, ex, floor, V_MAX, breakpoints(inputs, wdot, r_ex))
        out.append((hi[0], hi[2]["wall_route"]) if hi else (None, None))
    return out


def _branch(w):
    """The route BRANCH before the astropause / windtime cap (F2): ``bow`` or ``wind_term``."""
    return "bow" if w.get("wall_route_precap", w.get("wall_route")) in _BOW else "wind_term"


# ── the one application helper (plan §3.5b) ─────────────────────────────────────────────────────────────────────
def star_v_ism(fetch, *, supplied=None, lb_cavity=False, cloud=None, clic_max_pc=None, model=None,
               has_wall=True):
    """The one ``--star`` V_ISM decision both subcommands use (CP5): the measured row in use (the CR-26 model's used
    tier ``measured``), Q2's skip rule (no lookup only when ``--v-ism`` / ``--lb-cavity`` sets V_ISM on a
    non-measured star with a wall), the lookup (``fetch()`` → a velocity dict or None), the precedence, and the
    ignored-flag notes of a skipped lookup. A windless / unmodeled body gets its velocity and no V_ISM
    (``path="none"``). Returns ``(vres, vel)``."""
    row_key = ((model["wind_model"].get("measured") or {}).get("row_key")
               if (model and model.get("mass_loss_tier") == "measured") else None)
    if not has_wall:
        return resolve_v_ism(path="none", supplied=supplied), fetch()
    skip = (supplied is not None or lb_cavity) and row_key is None
    vel = None if skip else fetch()
    vres = resolve_v_ism(path="star", supplied=supplied, lb_cavity=bool(lb_cavity), cloud=cloud,
                         clic_max_pc=(clic_max_pc or 15.0), measured_row_key=row_key, vel=vel)
    if skip:                                   # the flags a skipped lookup never used — noted, never silent
        by = "--v-ism" if supplied is not None else "--lb-cavity"
        for flag, val in (("--cloud", cloud), ("--clic-max-pc", clic_max_pc)):
            if val is not None:
                vres["notes"].append(NOTE_IGNORED_BY_STEP.format(flag=flag, by=by))
        if supplied is not None and lb_cavity:
            vres["notes"].append(NOTE_IGNORED_BY_STEP.format(flag="--lb-cavity", by="--v-ism"))
    return vres, vel


def apply_v_ism(wall, inputs, r_ex, wind_class, vres, *, band_rate=None, band_dex=None, band_upper=False):
    """Apply the resolved V_ISM to a wall already computed at ``inputs["v_ism"]`` (the point, or the floor). Returns
    ``(wall, extra, band_override, notes)``:
    - ``wall``: the reported wall dict — the point's, or DQ3's largest (O-2: its wall / band / route / reason at the
      lowest V_ISM that gives it; ``r_ap_au`` kept at the floor; ``verdict_marginal`` from the floor's triggers + CR-24's);
    - ``extra``: the CR-24 fields (``m_f``, ``wall_range_vism_au``, ``wall_route_provisional``,
      ``verdict_marginal_reasons``) — the V_ISM fields from ``vres`` are merged by the caller;
    - ``band_override``: DQ3's per-edge wind band (D-C3), or None;
    - ``notes``."""
    notes = []
    floor_wall = wall
    reasons = list(floor_wall.get("verdict_marginal_reasons") or [])
    extra = {"m_f": inputs["v_ism"] / inputs["c_ms"] if inputs.get("c_ms") else None,
             "wall_range_vism_au": None, "wall_route_provisional": False}
    band_override = None
    if not inputs.get("wdot") or wall.get("wall_au") is None or vres is None:
        extra["verdict_marginal_reasons"] = reasons
        return wall, extra, band_override, notes

    if vres["mode"] == "lower_bound":
        floor = vres["v_ism_kms"]
        lb = lower_bound_wall(inputs, r_ex, wind_class, floor)
        rep = dict(lb["wall"])
        rep["r_ap_au"] = floor_wall.get("r_ap_au")
        wall = rep
        extra["wall_range_vism_au"] = lb["range"]
        extra["wall_route_provisional"] = lb["provisional"]
        if lb["provisional"]:
            reasons.append("lower_bound_provisional")
        notes.append(NOTE_LB.format(route_clause=(_ROUTE_PROV if lb["provisional"] else _ROUTE_NOT_PROV),
                                    f=floor, v=lb["v_at"]))
        notes.append(lb["lower_note"])
        if band_rate is not None and band_dex and not band_upper:
            (lo_v, lo_r), (hi_v, hi_r) = lower_bound_band_edges(
                inputs, r_ex, wind_class, floor, band_rate * 10.0 ** band_dex[0], band_rate * 10.0 ** band_dex[1])
            if lo_v is not None and hi_v is not None:
                band_override = {"wall_band_wind_au": [lo_v, hi_v],
                                 "wall_band_wind_exceeds_standoff": (bool(hi_v > r_ex) if r_ex is not None
                                                                     else None)}
                if lo_r != hi_r:
                    band_override["wall_band_wind_routes"] = [lo_r, hi_r]
    elif vres.get("cloud_points"):
        walls = [(c, wall_at(inputs, v, r_ex, wind_class)) for c, v in vres["cloud_points"]]
        vals = [w["wall_au"] for _c, w in walls if w.get("wall_au") is not None]
        if vals:
            extra["wall_range_vism_au"] = [min(vals), max(vals)]
        point_branch = _branch(floor_wall)
        other = [c for c, w in walls if _branch(w) != point_branch]
        if other:
            reasons.append("cloud_set_branch")
            other_branch = "a bow-shock route" if point_branch == "wind_term" else "the wind term"
            notes.append(NOTE_CLOUD_SET.format(names=", ".join(other), branch=other_branch))

    order = ("c_ms_straddle", "bow_shock_marginal", "apex_near_standoff", "cloud_set_branch",
             "lower_bound_provisional")
    reasons = [r for r in order if r in reasons]
    extra["verdict_marginal_reasons"] = reasons
    wall = dict(wall)
    wall["verdict_marginal"] = bool(reasons)

    # the measured star's different-route cross-check (a derived — not floor — value only)
    xd = vres.get("derived_xcheck")
    if xd and xd[1] == "derived" and vres["v_ism_provenance"] != "derived":
        xw = wall_at(inputs, xd[0], r_ex, wind_class)
        if xw.get("wall_route") != floor_wall.get("wall_route"):
            notes.append(NOTE_ROUTE_XCHECK.format(d=xd[0], r1=xw["wall_route"], v=vres["v_ism_kms"],
                                                  prov=vres["v_ism_provenance"], r2=floor_wall["wall_route"]))
    return wall, extra, band_override, notes


def v_ism_fields(vres):
    """The emitted V_ISM field block (with the medium block) — ``v_ism_kms`` / ``v_ism_provenance`` ride in the echo."""
    return {"v_cloud_used": vres["v_cloud_used"], "v_cloud_chi2": vres["v_cloud_chi2"],
            "v_ism_derived_kms": vres["v_ism_derived_kms"], "v_ism_range_kms": vres["v_ism_range_kms"],
            "clic_domain": vres["clic_domain"]}


def velocity_fields(vel):
    """The emitted velocity block (on every result): ``velocity_provenance``, ``velocity_status``, ``space_velocity``."""
    if vel is None:
        return {"velocity_provenance": None, "velocity_status": "not_run", "space_velocity": None}
    return {"velocity_provenance": vel["provenance"], "velocity_status": vel.get("status", "ok"),
            "space_velocity": vel["space_velocity"]}


def ism_measured_note(row_key, v_ism, prov):
    """⚑4: the replacement for CR-26's measured-tier ISM note (filled once V_ISM is known)."""
    n = ivt.measured_row_vism(row_key) if row_key else None
    if n is None:
        return None
    return NOTE_ISM_MEASURED.format(n=n, v=v_ism, prov=prov)


# ── network (bounded; every call through a module-level seam conftest stubs) ────────────────────────────────────
def _velocity_seam(main_id):
    from core import databases
    return databases.simbad_velocity(main_id)


def _identity_seam(ident):
    from core import xray_catalog
    return xray_catalog._identity_lookup(ident)


def _parse_inject(env):
    """``SPACE_APP_CR24_INJECT_RV``: ``"<rv>[:<g>]"`` (every lookup) or ``"<main_id>=<rv>[:<g>][,…]"`` (per record,
    whitespace-collapsed match). Returns ``(global, {collapsed_id: (rv, g)})``."""
    glob, per = None, {}
    for part in (env or "").split(","):
        part = part.strip()
        if not part:
            continue
        key, val = (part.rsplit("=", 1) if "=" in part else (None, part))
        rv_s, _, g = val.partition(":")
        try:
            item = (float(rv_s), (g.strip() or "A"))
        except ValueError:
            continue
        if key is None:
            glob = item
        else:
            per[shared.collapse_ws(key)] = item
    return glob, per


def fetch_velocity_record(main_id):
    """``(record, status)`` — status ∈ {ok, timeout, unreachable, error}; ``record`` None when SIMBAD answered no
    object (status ok) or on a failure. Hooks: ``SPACE_APP_SIMBAD_VELOCITY_FORCE_UNREACHABLE`` (this lookup only — A7)
    and ``SPACE_APP_CR24_INJECT_RV`` (replaces the RV + grade after the fetch, before the gate)."""
    if os.environ.get("SPACE_APP_SIMBAD_VELOCITY_FORCE_UNREACHABLE"):
        return None, "unreachable"
    rec, st = _velocity_seam(main_id)
    if st:
        return None, st
    if rec is None:
        return None, "ok"
    rec = dict(rec)
    glob, per = _parse_inject(os.environ.get("SPACE_APP_CR24_INJECT_RV"))
    hit = per.get(shared.collapse_ws(rec.get("main_id"))) or glob
    if hit:
        rec["rvz_radvel"], rec["rvz_qual"] = hit
    return rec, "ok"


def resolve_a_record(head_main_id, reuse=None):
    """The head → A-record resolution (§CR-24.1; Q1; CP0 F-A1/F-A4) through CR-26's own identity resolver
    (``_identity_lookup`` — astroquery ``query_object``, which normalises SIMBAD's double-spaced ids). Returns
    ``(kind, record_or_None, status_or_None, candidate)`` — kind ∈ {``own`` (not a letterless head), ``a`` (a distinct A
    record), ``same`` (the candidate resolves to the head's own record), ``empty`` (answered: no such record),
    ``failed``}. ``reuse`` = a ``(record, status)`` CR-26 already fetched for the same candidate."""
    from core import xray_catalog
    cand = xray_catalog.a_candidate(head_main_id) if head_main_id else None
    if not cand:
        return "own", None, None, None
    rec, st = reuse if reuse is not None else _identity_seam(cand)
    if st:
        return "failed", None, st, cand
    if rec is None:
        return "empty", None, None, cand
    if shared.collapse_ws(rec.get("main_id")) == shared.collapse_ws(head_main_id):
        return "same", rec, None, cand
    return "a", rec, None, cand


def lookup_velocity(main_id, *, primary=None):
    """Fetch + resolve one record's velocity; ``status`` attached."""
    rec, st = fetch_velocity_record(main_id)
    if st != "ok":
        v = _unavailable([NOTE_LOOKUP_FAILED.format(mid=main_id, st=st)], record=main_id)
        v["status"] = st
        return v
    if rec is None:
        v = _unavailable([NOTE_NO_RECORD.format(mid=main_id)], record=main_id)
        v["status"] = "ok"
        return v
    v = resolve_velocity(rec, primary=primary)
    v["status"] = "ok"
    return v


def target_velocity(main_id, *, reuse=None):
    """A ``--star`` target's (or a single component's) velocity: a letterless head takes its A record (kind ``a``);
    a failed A lookup → ``unavailable`` (never the head's record); anything else uses its own record. Returns
    ``(vel, kind, a_record)``."""
    kind, arec, st, cand = resolve_a_record(main_id, reuse)
    if kind == "failed":
        v = _unavailable([NOTE_A_FAILED.format(cand=cand, st=st, head=main_id)], record=None)
        v["status"] = st
        return v, kind, None
    rec_id = arec.get("main_id") if kind == "a" else main_id
    v = lookup_velocity(rec_id)
    if kind == "a":
        v["notes"].insert(0, NOTE_HEAD_A.format(head=main_id, a=rec_id))
    return v, kind, arec


def primary_rv_of(vel):
    """The ⚑1 fallback source: the primary's (A record's) OWN RV, when it passed the gate."""
    sv = (vel or {}).get("space_velocity") or {}
    if sv.get("rv_used") and sv.get("rv_source") == "own":
        return {"main_id": vel.get("record"), "rv": sv.get("rv"), "grade": sv.get("rv_grade")}
    return None
