"""core/detection.py — CR-6: per-target detection-completeness map (pure-math composition).

Self-validating (Phase-H/P contract). Composes the four existing forward detection calculators
(``calculators.compute_rv_semi_amplitude`` / ``compute_transit_signal`` /
``compute_astrometric_signal`` / ``compute_direct_imaging``), **inverted**, into the minimum
detectable planet (mass M⊕ or radius R⊕) vs orbital SMA per method — a completeness map.

Survey capability comes from a per-star override or, absent that, the WB 3a survey-completeness
reference (``detection_tables._DETECTION_DEFAULTS``, provisional now; swap when 3a lands).

Monotonicity is **per-method** (domain review 2026-08-15): RV/transit get harder at wider SMA;
astrometry & direct imaging get *easier* at wider SMA — astrometry until a period > baseline
turnover (gated), imaging until the separation falls inside the contrast curve's inner edge (IWA).
Network only on the optional ``--star`` resolve path.
"""

import math

import core.calculators as calculators
import core.detection_tables as dt

_ALL_METHODS = ("rv", "transit", "astrometry", "imaging")
_DEFAULT_SMA_GRID = (0.05, 0.1, 0.3, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0)


def _bin_row(by_mag, app_mag):
    """First by_mag row whose mag_max ≥ app_mag (bins are ordered brightest→faintest)."""
    for row in by_mag:
        if app_mag <= row["mag_max"]:
            return row
    return by_mag[-1]


def _resolve_star_mr(sp_type, star_mass_solar, star_radius_solar):
    """(mass, radius) in solar units from explicit values or a spectral type. → (m, r) or None."""
    m, r = star_mass_solar, star_radius_solar
    if (m is None or r is None) and sp_type:
        for ch in sp_type:
            if ch.upper() in dt._MS_MASS_RADIUS:
                dm, dr = dt._MS_MASS_RADIUS[ch.upper()]
                m = m if m is not None else dm
                r = r if r is not None else dr
                break
    if m is None or r is None:
        return None
    return m, r


def _interp_delta_mag(curve, sep_arcsec):
    """Linear-interpolate the contrast curve's Δmag at a separation; None if inside the inner edge."""
    pts = sorted(curve, key=lambda p: p["sep_arcsec"])
    if sep_arcsec < pts[0]["sep_arcsec"]:
        return None                                    # inside the inner working angle
    if sep_arcsec >= pts[-1]["sep_arcsec"]:
        return pts[-1]["delta_mag"]
    for a, b in zip(pts, pts[1:]):
        if a["sep_arcsec"] <= sep_arcsec < b["sep_arcsec"]:
            f = (sep_arcsec - a["sep_arcsec"]) / (b["sep_arcsec"] - a["sep_arcsec"])
            return a["delta_mag"] + f * (b["delta_mag"] - a["delta_mag"])
    return pts[-1]["delta_mag"]


def _rv_curve(m_star, sma_grid, precision_floor_ms, baseline_yr):
    out = []
    for a in sma_grid:
        period_yr = math.sqrt(a ** 3 / m_star)
        if period_yr > baseline_yr:                    # orbit longer than the survey baseline
            out.append({"sma_au": a, "min_mass_earth": None,
                        "note": f"P={period_yr:.1f} yr > {baseline_yr} yr baseline"})
            continue
        k_per_earth = calculators.compute_rv_semi_amplitude(1.0, m_star, sma_au=a)["k_ms"]
        out.append({"sma_au": a, "min_mass_earth": precision_floor_ms / k_per_earth})
    return out


def _transit_curve(r_star, sma_grid, phot_floor_ppm):
    floor_frac = phot_floor_ppm * 1e-6
    out = []
    for a in sma_grid:
        sig = calculators.compute_transit_signal(1.0, r_star, sma_au=a)
        depth_1re = sig["depth_frac"]
        out.append({"sma_au": a,
                    "min_radius_earth": math.sqrt(floor_frac / depth_1re),
                    "transit_prob": sig["transit_prob"]})
    return out


def _astrometry_curve(m_star, distance_pc, sma_grid, floor_uas, baseline_yr):
    floor_arcsec = floor_uas * 1e-6
    out = []
    for a in sma_grid:
        period_yr = math.sqrt(a ** 3 / m_star)
        if period_yr > baseline_yr:                    # orbit longer than the baseline → not sampled
            out.append({"sma_au": a, "min_mass_earth": None,
                        "note": f"P={period_yr:.1f} yr > {baseline_yr} yr baseline"})
            continue
        sig_per_earth = calculators.compute_astrometric_signal(1.0, m_star, a, distance_pc)["signal_arcsec"]
        out.append({"sma_au": a, "min_mass_earth": floor_arcsec / sig_per_earth})
    return out


def _imaging_curve(distance_pc, sma_grid, curve, albedo):
    out = []
    for a in sma_grid:
        sep = a / distance_pc                           # arcsec
        dmag = _interp_delta_mag(curve, sep)
        if dmag is None:
            out.append({"sma_au": a, "min_radius_earth": None,
                        "note": f"sep {sep:.3f}\" inside contrast-curve inner edge (IWA)"})
            continue
        c_floor = 10.0 ** (-0.4 * dmag)
        contrast_1re = calculators.compute_direct_imaging(a, distance_pc, 1.0, albedo)["contrast_reflected"]
        out.append({"sma_au": a, "sep_arcsec": sep,
                    "min_radius_earth": math.sqrt(c_floor / contrast_1re)})
    return out


def compute_detection_completeness(app_mag, distance_pc, sp_type=None,
                                   star_mass_solar=None, star_radius_solar=None,
                                   methods=None, sma_grid=None, albedo=0.3,
                                   rv_precision_ms=None, rv_baseline_yr=None,
                                   transit_precision_ppm=None, transit_target=False,
                                   astrom_precision_uas=None, astrom_baseline_yr=None,
                                   star=None):
    """Per-method minimum-detectable-planet vs SMA map. See module docstring.

    Returns ``{star, app_mag, distance_pc, sp_type, star_mass_solar, star_radius_solar,
    methods:[{method, applicable, detectable_vs_sma:[…], floor_source, note?}], assumptions}``
    or ``{"error": str}``.
    """
    if distance_pc is None or distance_pc <= 0:
        return {"error": "distance_pc must be positive."}
    if app_mag is None:
        return {"error": "app_mag is required."}
    if not (0 < albedo < 1):
        return {"error": "albedo must be in (0, 1)."}
    if rv_baseline_yr is not None and rv_baseline_yr <= 0:
        return {"error": "rv_baseline_yr must be positive."}
    if astrom_baseline_yr is not None and astrom_baseline_yr <= 0:
        return {"error": "astrom_baseline_yr must be positive."}
    mr = _resolve_star_mr(sp_type, star_mass_solar, star_radius_solar)
    if mr is None:
        return {"error": "Provide --sp-type, or --star-mass-solar and --star-radius-solar."}
    m_star, r_star = mr
    if m_star <= 0 or r_star <= 0:
        return {"error": "star mass and radius must be positive."}
    grid = tuple(sma_grid) if sma_grid else _DEFAULT_SMA_GRID
    if any(a <= 0 for a in grid):
        return {"error": "sma_grid values must be positive."}
    want = tuple(methods) if methods else _ALL_METHODS
    bad = [m for m in want if m not in _ALL_METHODS]
    if bad:
        return {"error": f"unknown method(s): {', '.join(bad)}"}

    defaults = dt._DETECTION_DEFAULTS
    dom = defaults["domain"]["mag_range"]
    out_of_domain = not (dom[0] <= app_mag <= dom[1])
    out_methods = []

    for method in want:
        if method == "rv":
            floor = rv_precision_ms
            base = rv_baseline_yr if rv_baseline_yr is not None else defaults["methods"]["rv"]["baseline_yr"]
            src = "per-star override" if floor is not None else None
            if floor is None:
                row = _bin_row(defaults["methods"]["rv"]["by_mag"], app_mag)
                floor = row["precision_m_s"]
                src = f"3a-default RV (mag≤{row['mag_max']}): {floor} m/s"
            out_methods.append({"method": "rv", "applicable": True,
                                "detectable_vs_sma": _rv_curve(m_star, grid, floor, base),
                                "floor_source": src, "value_kind": "min_mass_earth",
                                "baseline_yr": base})
        elif method == "transit":
            floor = transit_precision_ppm
            applicable = transit_target or (transit_precision_ppm is not None)
            src = "per-star override" if transit_precision_ppm is not None else None
            if floor is None:
                row = _bin_row(defaults["methods"]["transit"]["by_mag"], app_mag)
                floor = row["phot_precision_ppm"]
                src = f"3a-default transit (mag≤{row['mag_max']}): {floor} ppm"
            entry = {"method": "transit", "applicable": applicable,
                     "detectable_vs_sma": _transit_curve(r_star, grid, floor),
                     "floor_source": src, "value_kind": "min_radius_earth"}
            if not applicable:
                entry["note"] = ("not a known transit target / not covered — depth floor is the "
                                 "physics, but transit detection needs a covering survey "
                                 "(pass --transit-target or --transit-precision-ppm)")
            out_methods.append(entry)
        elif method == "astrometry":
            floor = astrom_precision_uas
            base = (astrom_baseline_yr if astrom_baseline_yr is not None
                    else defaults["methods"]["astrometry"]["baseline_yr"])
            src = "per-star override" if floor is not None else None
            if floor is None:
                row = _bin_row(defaults["methods"]["astrometry"]["by_mag"], app_mag)
                floor = row["astrom_precision_uas"]
                src = f"3a-default astrometry (mag≤{row['mag_max']}): {floor} µas"
            out_methods.append({"method": "astrometry", "applicable": True,
                                "detectable_vs_sma": _astrometry_curve(m_star, distance_pc, grid, floor, base),
                                "floor_source": src, "value_kind": "min_mass_earth",
                                "baseline_yr": base})
        elif method == "imaging":
            curve = defaults["methods"]["imaging"]["contrast_curve"]
            out_methods.append({"method": "imaging", "applicable": True,
                                "detectable_vs_sma": _imaging_curve(distance_pc, grid, curve, albedo),
                                "floor_source": f"3a-default imaging contrast curve "
                                                f"(anchored_to_star_mag="
                                                f"{defaults['methods']['imaging']['anchored_to_star_mag']})",
                                "value_kind": "min_radius_earth"})

    return {
        "star": star,
        "app_mag": app_mag,
        "distance_pc": distance_pc,
        "sp_type": sp_type,
        "star_mass_solar": m_star,
        "star_radius_solar": r_star,
        "methods": out_methods,
        "assumptions": {
            "reference_version": defaults["reference_version"],
            "confidence": defaults["confidence"],
            "out_of_domain": out_of_domain,
            "mag_domain": dom,
            "domain_note": (None if not out_of_domain else
                            f"app_mag {app_mag} outside the 3a reference domain {dom} — "
                            "floor is an extrapolation, flagged not clamped"),
            "sma_grid_au": list(grid),
            "albedo": albedo,
            "monotonicity": "RV/transit min-planet increases with SMA; astrometry/imaging "
                            "decreases with SMA (astrometry until P>baseline; imaging until IWA)",
        },
    }
