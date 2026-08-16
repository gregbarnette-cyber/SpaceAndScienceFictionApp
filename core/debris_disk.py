"""core/debris_disk.py — CR-1: observed debris-disk / IR-excess data (LIVE network).

Nothing else in query.py carries observed circumstellar-dust data (``disk-model`` is a theoretical
MMSN profile). CR-1 cross-matches a star against published IR-excess catalogues and, on a
non-detection, returns a per-star **upper limit** (never null) so downstream "non-detection ≠
absence" reads work.

Data sources (VizieR, via ``core.catalog`` — lazy astroquery, result-cached, ``_route_error`` shape):
  - **Chen et al. 2014** (``J/ApJS/211/25/catalog``) — Spitzer IRS+MIPS two-temperature fits with
    **per-component** L_IR/L*, grain temperature, disk radius (AU). Primary (richest per-component).
  - **Cotten & Song 2016** (``J/ApJS/225/15/table3``) — WISE+IRAS+**Herschel PACS/SPIRE** fits: warm
    (Td1/Rd1) + cold (Tdt2/Rd2) + total τ=L_IR/L*. Fills the **cold far-IR** component Spitzer can miss.
  - Non-detection: an AllWISE (``II/328/allwise``) W4 photospheric-subtraction **warm-dust** upper
    limit; a documented survey floor when the star lacks WISE photometry. Both regime-tagged, never null.
"""

import math

from core.shared import _network_error_msg, _route_error

_CONE_DEG = 0.0028             # ~10″ match radius (debris catalogues are one precise row per star)
_WARM_COLD_K = 130.0           # warm (~150–400 K) vs cold (Kuiper-analog, ≲130 K) split
_DUST_W4_FRACTION = 0.20       # fraction of a warm (~150 K) blackbody's luminosity in the WISE W4 band
_FLOOR_UPPER_LIMIT = 1.0e-4    # documented warm-dust WISE sensitivity floor (fallback, no per-star W4)

# CODATA (radiation constants) for the Planck band-fraction of the upper-limit calc.
_H, _C, _KB, _SIGMA = 6.62607015e-34, 2.99792458e8, 1.380649e-23, 5.670374419e-8
_W4_BAND_M = (20.5e-6, 23.5e-6)


def _planck_band_fraction(teff, lam1=_W4_BAND_M[0], lam2=_W4_BAND_M[1], n=40):
    """Fraction of a Teff blackbody's bolometric flux emitted in [lam1, lam2] (Simpson integral)."""
    total = _SIGMA * teff ** 4 / math.pi          # ∫ B_λ dλ over all λ
    dl = (lam2 - lam1) / n
    s = 0.0
    for i in range(n + 1):
        lam = lam1 + i * dl
        x = _H * _C / (lam * _KB * teff)
        b_lam = (2 * _H * _C ** 2 / lam ** 5) / (math.expm1(x))
        w = 1 if i in (0, n) else (4 if i % 2 else 2)
        s += w * b_lam
    return (dl / 3.0) * s / total


def _num(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _r(v, n):
    """Round a float (trims VizieR float32 noise like 59.900001525878906); None-safe."""
    return round(v, n) if v is not None else None


def _classify(t):
    return "warm" if t is not None and t >= _WARM_COLD_K else "cold"


def _chen_components(row):
    """Chen et al. 2014 row → warm/cold (or single) components with per-component L_IR/L* (direct)."""
    ref, band = "Chen et al. 2014 (J/ApJS/211/25)", "Spitzer IRS + MIPS"
    t1, t2 = _num(row.get("Tgr1")), _num(row.get("Tgr2"))
    if t1 is not None and t2 is not None:
        return [
            {"type": "warm", "L_IR_over_Lstar": _r(_num(row.get("LIR/L*1")), 8), "T_dust_K": _r(t1, 1),
             "R_disk_au": _r(_num(row.get("D1")), 3), "band": band, "ref": ref},
            {"type": "cold", "L_IR_over_Lstar": _r(_num(row.get("LIR2/L*")), 8), "T_dust_K": _r(t2, 1),
             "R_disk_au": _r(_num(row.get("D2")), 3), "band": band, "ref": ref},
        ]
    t = _num(row.get("Tgr"))
    if t is not None:
        return [{"type": _classify(t), "L_IR_over_Lstar": _r(_num(row.get("LIR/L*")), 8),
                 "T_dust_K": _r(t, 1), "R_disk_au": _r(_num(row.get("D")), 3),
                 "band": band, "ref": ref}]
    return []


def _cotten_components(row):
    """Cotten & Song 2016 row → warm/cold components. `Tau` is L_IR/L* in units of 1e-4 (pinned live
    against β Pic/Fomalhaut/Vega/HR 8799/HD 69830); it is the SYSTEM total, not split per component."""
    ref, band = "Cotten & Song 2016 (J/ApJS/225/15)", "WISE + IRAS/MIPS + Herschel PACS/SPIRE"
    tau_raw = _num(row.get("Tau"))
    tau = _r(tau_raw * 1e-4, 8) if tau_raw is not None else None   # column unit is 10^-4
    td1, rd1 = _num(row.get("Td1")), _num(row.get("Rd1"))
    td2, rd2 = _num(row.get("Tdt2")), _num(row.get("Rd2"))
    comps = []
    if td1 is not None and td2 is not None:                        # two-belt fit
        comps.append({"type": "warm", "T_dust_K": _r(td1, 1), "R_disk_au": _r(rd1, 3),
                      "L_IR_over_Lstar": None, "band": band, "ref": ref,
                      "note": f"system total L_IR/L*={tau} (Cotten τ not split per component)"})
        comps.append({"type": "cold", "T_dust_K": _r(td2, 1), "R_disk_au": _r(rd2, 3),
                      "L_IR_over_Lstar": None, "band": band, "ref": ref,
                      "note": f"cold far-IR (Herschel PACS/SPIRE); system total L_IR/L*={tau}"})
    elif td1 is not None:                                          # single component → classify by T
        comps.append({"type": _classify(td1), "T_dust_K": _r(td1, 1), "R_disk_au": _r(rd1, 3),
                      "L_IR_over_Lstar": tau, "band": band, "ref": ref})
    return comps, tau


def _match_row(catalog, cat_id, ra, dec):
    """First VizieR row within the cone, or (None, error_or_None)."""
    res = catalog.vizier_query(catalog=cat_id, columns=["**"], cone=f"{ra} {dec} {_CONE_DEG}")
    if "error" in res:
        return None, res["error"]
    rows = res.get("rows") or []
    return (rows[0] if rows else None), None


def _wise_upper_limit(catalog, ra, dec, teff):
    """Per-star AllWISE W4 warm-dust 3σ upper limit on L_IR/L* (photospheric-subtraction estimate)."""
    res = catalog.vizier_query(catalog="II/328/allwise", columns=["W1mag", "W4mag", "e_W4mag"],
                               cone=f"{ra} {dec} {_CONE_DEG}")
    teff = teff or 5778.0
    frac_star_w4 = _planck_band_fraction(teff)
    if "error" not in res and res.get("rows"):
        sigma_w4 = _num(res["rows"][0].get("e_W4mag")) or 0.03
        f_excess = 10.0 ** (0.4 * 3.0 * sigma_w4) - 1.0
        ul = f_excess * frac_star_w4 / _DUST_W4_FRACTION
        basis = f"AllWISE W4 3σ (σ_W4={sigma_w4:.3f} mag), photospheric-subtraction estimate"
    else:
        ul = _FLOOR_UPPER_LIMIT
        basis = "documented WISE warm-dust survey floor (no per-star W4 photometry)"
    return {
        "detection": "upper_limit",
        "upper_limit_L_IR_over_Lstar": ul,
        "upper_limit_basis": basis,
        "upper_limit_regime": ("warm dust (~150–400 K); cold Kuiper-analog dust (≲70 K) is "
                               "invisible to WISE and needs far-IR — not constrained by this limit"),
        "provenance": "present-datapoint (order-of-magnitude; warm-regime only)",
    }


def debris_disk(star=None, source_id=None, ra=None, dec=None):
    """CR-1: observed debris-disk / IR-excess for one star. See module docstring.

    Output: ``{star, components:[{type, L_IR_over_Lstar, T_dust_K, R_disk_au, band, ref}], detection:
    detected|upper_limit, upper_limit_L_IR_over_Lstar, system_L_IR_over_Lstar?, ...}`` or
    ``{"error", route_tried}``."""
    import core.catalog as catalog
    from core import databases

    main_id, teff = None, None
    if star:
        sl = databases.compute_simbad_lookup(star)
        if "error" in sl:
            return _route_error(sl["error"], ["simbad"])
        ra, dec, teff, main_id = sl.get("ra"), sl.get("dec"), sl.get("teff"), sl.get("main_id")
    if ra is None or dec is None:
        return _route_error("debris-disk requires --star (SIMBAD-resolvable) or --ra/--dec",
                            ["debris-disk"])
    main_id = main_id or f"{ra},{dec}"

    try:
        chen_row, chen_err = _match_row(catalog, "J/ApJS/211/25/catalog", ra, dec)
        cotten_row, cotten_err = _match_row(catalog, "J/ApJS/225/15/table3", ra, dec)
    except Exception as e:                                 # defensive — catalog layer already curates
        return _route_error(_network_error_msg(e, "CDS VizieR"), ["debris-disk"])

    # Report BOTH catalogues' components, each ref-tagged — the two surveys can fit different
    # components/values for the same star (e.g. HD 69830: Chen cold vs Cotten warm), so suppressing
    # one loses a real component. Provenance (ref/band) lets the consumer see which survey said what.
    chen_comps = _chen_components(chen_row) if chen_row else []
    system_lir = None
    cotten_comps = []
    if cotten_row:
        cotten_comps, system_lir = _cotten_components(cotten_row)
    components = chen_comps + cotten_comps
    catalogs_matched = ([c[0]["ref"] for c in ([chen_comps] if chen_comps else [])]
                        + [c[0]["ref"] for c in ([cotten_comps] if cotten_comps else [])])

    route_tried = ["vizier:J/ApJS/211/25 (Chen 2014)", "vizier:J/ApJS/225/15 (Cotten & Song 2016)"]
    if components:
        out = {
            "star": main_id, "components": components, "detection": "detected",
            "upper_limit_L_IR_over_Lstar": None, "system_L_IR_over_Lstar": system_lir,
            "catalogs_matched": catalogs_matched, "route_tried": route_tried,
        }
        errs = [e for e in (chen_err, cotten_err) if e]
        if errs:
            out["route_errors"] = errs
        return out

    # Non-detection → per-star upper limit (never null).
    ul = _wise_upper_limit(catalog, ra, dec, teff)
    return {"star": main_id, "components": [], **ul,
            "route_tried": route_tried + ["vizier:II/328/allwise (upper limit)"]}
