"""core/detection.py — CR-6: per-target detection-completeness map (pure-math composition).

Self-validating (Phase-H/P contract). Composes the four existing forward detection calculators
(``calculators.compute_rv_semi_amplitude`` / ``compute_transit_signal`` /
``compute_astrometric_signal`` / ``compute_direct_imaging``), **inverted**, into the minimum
detectable planet (mass M⊕ or radius R⊕) vs orbital SMA per method — a completeness map.

Survey capability comes from a per-star override or, absent that, the WB **3a FINAL** survey-
completeness reference (``detection_tables._DETECTION_DEFAULTS``, ``3a-v1.1.0-2026-08-15``). The RV
floor is ``max(precision, sp_type-keyed jitter)``; the transit default is TESS all-sky; the transit
>12-mag and astrometry >15-mag faint tails prefer the analytic noise model over the binned scalar;
imaging carries the H-band self-luminous ``mechanism_caveat`` (WB MSG 048/050).

**Non-main-sequence host guard (CR-6-AMEND, WB MSG 053):** the MS mass/radius relation and the
sp_type→jitter map are MS-only. When ``sp_type`` resolves to a **white dwarf / hot subdwarf / giant /
subgiant / brown dwarf** (``_host_class``), the result sets ``out_of_domain=True`` + a ``host_class``
field and **refuses to fake MS params** by scanning to the first OBAFGKM letter (which had turned
``DA2`` → a 1.6 M☉ A star). It still computes on **explicit** ``--star-mass-solar``/``--star-radius-solar``
(the four calculators are valid for any real M/R) — flagged, with the RV jitter falling back to the
flat floor — else the methods are flagged/skipped with a note, never fabricated.

Monotonicity is **per-method** (domain review 2026-08-15): RV min-mass gets harder (larger) at
wider SMA; transit min-radius is **SMA-independent** (transit depth carries no SMA — the falling
``transit_prob`` is what makes wide orbits rarely transit, not a rising min-radius); astrometry &
direct imaging get *easier* at wider SMA — astrometry until a period > baseline turnover (gated),
imaging until the separation falls inside the contrast curve's inner edge (IWA).
Network only on the optional ``--star`` resolve path.
"""

import math
import re

import core.calculators as calculators
import core.detection_tables as dt
import core.rv_precision_tables as rvt
import core.shared as shared

_ALL_METHODS = ("rv", "transit", "astrometry", "imaging")
_DEFAULT_SMA_GRID = (0.05, 0.1, 0.3, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0)

# Luminosity class (Roman numeral) after the temperature subtype: III/II/I → giant, IV → subgiant,
# V → dwarf (MS), VI → subdwarf, VII → white dwarf. Longest Roman alternatives first.
_LUM_CLASS_RE = re.compile(r"[^A-Za-z](VII|VI|IV|V|III|II|I)(?:ab|a|b|0)?")


def _bin_row(by_mag, app_mag):
    """First by_mag row whose mag_max ≥ app_mag (bins are ordered brightest→faintest)."""
    for row in by_mag:
        if app_mag <= row["mag_max"]:
            return row
    return by_mag[-1]


def _sp_letter(sp_type):
    """Leading OBAFGKM class letter of a spectral type (same scan as _resolve_star_mr), else None."""
    if not sp_type:
        return None
    for ch in sp_type:
        if ch.upper() in "OBAFGKM":
            return ch.upper()
    return None


def _host_class(sp_type):
    """Non-main-sequence host class of a spectral type, else None (MS dwarf, or not classifiable as
    non-MS). CR-6-AMEND (WB MSG 053): the MS mass/radius relation and the sp_type→jitter map are
    MS-only and must not transfer to a WD / subdwarf / giant / subgiant / brown dwarf. Uses the
    app-wide, case-sensitive ``spectral_leading_class`` so the *degenerate* prefix ``D`` (DA2 → white
    dwarf) is never confused with the *dwarf* luminosity prefix ``d`` (dM6 → an M dwarf)."""
    if not sp_type:
        return None
    s = sp_type.strip()
    lead = shared.spectral_leading_class(s, letters=shared._SP_DISPLAY_LETTERS)
    if lead in ("L", "T", "Y"):
        return "brown_dwarf"
    if lead == "D":
        return "white_dwarf"                        # DA/DB/DO/DQ/DZ/DC… (uppercase D = degenerate)
    if s[:2] == "sd" and s[2:3] in ("B", "O"):      # hot subdwarf (sdB/sdO); cool sdM/esdM stay ~MS
        return "subdwarf"
    m = _LUM_CLASS_RE.search(s)                      # giants/subgiants via the luminosity class
    if m:
        lc = m.group(1)
        if lc == "IV":
            return "subgiant"
        if lc == "VI":
            return "subdwarf"
        if lc == "VII":
            return "white_dwarf"
        if lc == "V":
            return None                             # main-sequence dwarf
        return "giant"                              # I/Ia/Iab/Ib/II/III
    return None                                     # no luminosity class → treat as MS


def _domain_note(mag_out, app_mag, dom, host_class):
    """Human note for the out-of-domain flag — magnitude and/or non-MS-host reason(s), or None."""
    parts = []
    if mag_out:
        parts.append(f"app_mag {app_mag} outside the 3a reference domain {dom} — "
                     "floor is an extrapolation, flagged not clamped")
    if host_class is not None:
        parts.append(f"host is {host_class} (non-main-sequence) — the survey-floor defaults "
                     "(sp_type→jitter map, MS mass/radius relation) are MS-calibrated and may not transfer")
    return "; ".join(parts) if parts else None


def _rv_jitter_floor(rv_defaults, row, sp_type, host_class=None, activity=None):
    """``(floor_m_s, advisory)`` — the astrophysical RV jitter floor. Base = the sp_type-keyed
    Kraft-break bump when the host letter is known, else the flat per-bin value (WB 3a MSG 050;
    effective floor upstream = max(precision, this)).

    **Companion CR #1 (advisory PLACEHOLDER, WB Phase 5):** a larger floor for an **evolved** host
    (subgiant/giant p-mode + granulation) or an **active/young cool dwarf**. Whenever such a placeholder
    bump is applied, ``advisory=True`` — the *magnitude* is an un-cleared LEAD, so the caller flags the
    result advisory rather than treating it as a hard floor. Default (no evolved host, no activity
    signal) is byte-identical to the pre-CR#1 MS behaviour."""
    by_sp = rv_defaults.get("jitter_floor_by_sptype_m_s")
    letter = _sp_letter(sp_type)
    base = by_sp[letter] if (by_sp and letter in by_sp) else row.get("jitter_floor_m_s", 0.0)
    bumps = rv_defaults.get("jitter_bumps")
    advisory = False
    if bumps:
        ev = bumps.get("evolved", {})
        cand = ev.get("subgiant_m_s") if host_class == "subgiant" else (
            ev.get("giant_m_s") if host_class == "giant" else None)
        # active/young bump is a cool-dwarf effect → gate on a G/K/M host letter (never an evolved host,
        # whose letter is nulled upstream), and only when the caller supplies an activity signal.
        if cand is None and activity in ("active", "young") and letter in ("G", "K", "M"):
            cand = bumps.get("active_young_cool_dwarf_m_s")
        # Flag advisory ONLY when the placeholder actually raises the floor (a bump that doesn't move
        # the number is not a bump — don't claim one in the note).
        if cand is not None and cand > base:
            base, advisory = cand, True
    return base, advisory


def _tess_sigma_1hr_ppm(tmag, nm):
    """TESS 1-hr CDPP σ (ppm) at a Tmag — Kunimoto 2022 convex model (reproduces T=10 → 240.5 ppm)."""
    return (nm["a"] + nm["b"] * 10.0 ** (0.2 * (tmag - 10.0))
            + nm["c"] * 10.0 ** (0.4 * (tmag - 10.0)))


def _gaia_sigma_pi_uas(g, nm):
    """Gaia end-of-mission parallax σ (µas) at a G mag — ESA analytic model (valid 3 ≤ G < 20.7)."""
    z = max(10.0 ** (0.4 * (nm.get("g_floor", 13.0) - 15.0)), 10.0 ** (0.4 * (g - 15.0)))
    return nm["tfactor"] * math.sqrt(40.0 + 800.0 * z + 30.0 * z * z)


def _transit_floor(transit_defaults, app_mag):
    """(ppm, source) — TESS Kunimoto σ(Tmag) for the faint tail (app_mag > prefer_above_mag), else
    the binned TESS scalar."""
    nm = transit_defaults.get("noise_model")
    if nm and app_mag > nm["prefer_above_mag"]:
        floor = _tess_sigma_1hr_ppm(app_mag, nm)
        return floor, f"3a noise-model TESS σ₁ₕᵣ(Tmag={app_mag}) = {floor:.0f} ppm"
    row = _bin_row(transit_defaults["by_mag"], app_mag)
    return row["phot_precision_ppm"], f"3a-default transit TESS (mag≤{row['mag_max']}): {row['phot_precision_ppm']} ppm"


def _astrom_floor(astro_defaults, app_mag):
    """(µas, source) — Gaia analytic σϖ(G) for G>prefer_above_mag, else the binned scalar."""
    nm = astro_defaults.get("noise_model")
    if nm and app_mag > nm["prefer_above_mag"]:
        floor = _gaia_sigma_pi_uas(app_mag, nm)
        return floor, f"3a noise-model Gaia σϖ(G={app_mag}) = {floor:.0f} µas"
    row = _bin_row(astro_defaults["by_mag"], app_mag)
    return row["astrom_precision_uas"], f"3a-default astrometry (mag≤{row['mag_max']}): {row['astrom_precision_uas']} µas"


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
                                   star=None, activity=None, star_mass_provenance=None,
                                   rv_precision_provenance=None, rv_precision_meta=None):
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
    if activity is not None and activity not in ("active", "young", "quiet"):
        return {"error": "activity must be one of active / young / quiet."}
    host_class = _host_class(sp_type)
    if host_class is not None:
        # Non-MS host (CR-6-AMEND, WB MSG 053): the MS mass/radius relation + the sp_type→jitter map
        # do NOT transfer, so never fake MS params by scanning to the first OBAFGKM letter. Compute
        # only on explicit real M/R; without it, the methods are flagged/skipped, not fabricated.
        if star_mass_solar is not None and star_radius_solar is not None:
            if star_mass_solar <= 0 or star_radius_solar <= 0:
                return {"error": "star mass and radius must be positive."}
            m_star, r_star = star_mass_solar, star_radius_solar
        elif star_mass_solar is not None or star_radius_solar is not None:
            return {"error": "Provide BOTH --star-mass-solar and --star-radius-solar for a "
                             "non-main-sequence host."}
        else:
            m_star = r_star = None
    else:
        mr = _resolve_star_mr(sp_type, star_mass_solar, star_radius_solar)
        if mr is None:
            return {"error": "Provide --sp-type, or --star-mass-solar and --star-radius-solar."}
        m_star, r_star = mr
        if m_star <= 0 or r_star <= 0:
            return {"error": "star mass and radius must be positive."}
    # CR-10.4: which tier supplied M★ — an explicit value (manual or archive) vs the sp_type→mass
    # estimate. The query.py --star wrapper passes "manual"/"archive"; a direct explicit mass with no
    # provenance defaults to "manual"; a mass filled from the MS table is "sp_type_estimate".
    if m_star is None:
        mass_provenance = None
    elif star_mass_solar is not None:
        mass_provenance = star_mass_provenance or "manual"
    else:
        mass_provenance = "sp_type_estimate"
    grid = tuple(sma_grid) if sma_grid else _DEFAULT_SMA_GRID
    if any(a <= 0 for a in grid):
        return {"error": "sma_grid values must be positive."}
    want = tuple(methods) if methods else _ALL_METHODS
    bad = [m for m in want if m not in _ALL_METHODS]
    if bad:
        return {"error": f"unknown method(s): {', '.join(bad)}"}

    defaults = dt._DETECTION_DEFAULTS
    dom = defaults["domain"]["mag_range"]
    mag_out = not (dom[0] <= app_mag <= dom[1])
    out_of_domain = mag_out or (host_class is not None)
    # sp_type feeds the MS-only jitter map only for a main-sequence host; a non-MS host with explicit
    # M/R falls back to the flat per-bin jitter (the sp_type map does not transfer — WB MSG 053).
    jitter_sp = sp_type if host_class is None else None
    non_ms_no_mr = host_class is not None and m_star is None
    out_methods = []

    for method in want:
        if non_ms_no_mr:
            out_methods.append({
                "method": method, "applicable": False, "detectable_vs_sma": [], "floor_source": None,
                "floor_provenance": None,
                "value_kind": "min_radius_earth" if method in ("transit", "imaging") else "min_mass_earth",
                "note": (f"host is {host_class} (non-main-sequence) — not computed: the MS "
                         "mass/radius/jitter defaults do not transfer. Supply --star-mass-solar and "
                         "--star-radius-solar to run the four detection calculators on the real host M/R.")})
            continue
        if method == "rv":
            rv_def = defaults["methods"]["rv"]
            row = _bin_row(rv_def["by_mag"], app_mag)
            base = rv_baseline_yr if rv_baseline_yr is not None else row["baseline_yr"]
            jitter_advisory = False
            if rv_precision_ms is not None:
                # CR-10.3: tier-1 manual (--rv-precision-ms) or tier-2 catalog (query.py resolved a
                # per-star row and passed provenance="catalog" + the row as rv_precision_meta).
                floor = rv_precision_ms
                floor_prov = rv_precision_provenance or "manual"
                if floor_prov == "catalog" and rv_precision_meta:
                    src = rvt.catalog_floor_source(rv_precision_meta)
                else:
                    src = "per-star override"   # same string as transit/astrometry manual overrides
            else:
                jitter, jitter_advisory = _rv_jitter_floor(
                    rv_def, row, jitter_sp, host_class=host_class, activity=activity)
                floor = max(row["precision_m_s"], jitter)
                src = (f"3a-default RV (mag≤{row['mag_max']}): "
                       f"max(precision {row['precision_m_s']}, jitter {jitter}) = {floor} m/s")
                floor_prov = "generic-3a"
            rv_entry = {"method": "rv", "applicable": True,
                        "detectable_vs_sma": _rv_curve(m_star, grid, floor, base),
                        "floor_source": src, "floor_provenance": floor_prov,
                        "value_kind": "min_mass_earth",
                        "baseline_yr": base}
            if jitter_advisory:
                # Companion CR #1: an evolved / active-young jitter bump was applied from an ADVISORY
                # PLACEHOLDER (magnitude un-cleared — WB Phase 5 pins the jitter–L/M scaling). Flag it
                # so the consumer treats it as advisory (not a hard 'likely-absent'), overridable via
                # --rv-precision-ms.
                rv_entry["jitter_advisory"] = True
                rv_entry["jitter_note"] = (
                    "an evolved-star / active-young-dwarf jitter bump was applied from an ADVISORY "
                    "PLACEHOLDER magnitude (un-cleared LEAD — WB Phase 5 pins the jitter–L/M scaling); "
                    "treat as advisory, not a hard floor. Override with --rv-precision-ms.")
            out_methods.append(rv_entry)
        elif method == "transit":
            applicable = transit_target or (transit_precision_ppm is not None)
            if transit_precision_ppm is not None:
                floor, src = transit_precision_ppm, "per-star override"
            else:
                floor, src = _transit_floor(defaults["methods"]["transit"], app_mag)
            entry = {"method": "transit", "applicable": applicable,
                     "detectable_vs_sma": _transit_curve(r_star, grid, floor),
                     "floor_source": src, "value_kind": "min_radius_earth",
                     "floor_provenance": "manual" if transit_precision_ppm is not None else "generic-3a"}
            if not applicable:
                entry["note"] = ("not a known transit target / not covered — depth floor is the "
                                 "physics, but transit detection needs a covering survey "
                                 "(pass --transit-target or --transit-precision-ppm)")
            out_methods.append(entry)
        elif method == "astrometry":
            astro_def = defaults["methods"]["astrometry"]
            base = astrom_baseline_yr if astrom_baseline_yr is not None else astro_def["baseline_yr"]
            if astrom_precision_uas is not None:
                floor, src = astrom_precision_uas, "per-star override"
            else:
                floor, src = _astrom_floor(astro_def, app_mag)
            out_methods.append({"method": "astrometry", "applicable": True,
                                "detectable_vs_sma": _astrometry_curve(m_star, distance_pc, grid, floor, base),
                                "floor_source": src, "value_kind": "min_mass_earth",
                                "floor_provenance": "manual" if astrom_precision_uas is not None else "generic-3a",
                                "baseline_yr": base})
        elif method == "imaging":
            im = defaults["methods"]["imaging"]
            band = im.get("contrast_band")
            out_methods.append({"method": "imaging", "applicable": True,
                                "detectable_vs_sma": _imaging_curve(distance_pc, grid, im["contrast_curve"], albedo),
                                "floor_source": f"3a-default imaging contrast curve "
                                                f"({band}-band self-luminous; anchored_to_star_mag="
                                                f"{im['anchored_to_star_mag']})",
                                "floor_provenance": "generic-3a",  # imaging has no per-star override arg
                                "value_kind": "min_radius_earth",
                                "contrast_band": band,
                                "mechanism_caveat": im.get("mechanism_caveat")})

    return {
        "star": star,
        "app_mag": app_mag,
        "distance_pc": distance_pc,
        "sp_type": sp_type,
        "host_class": host_class,
        "star_mass_solar": m_star,
        "star_mass_provenance": mass_provenance,
        "star_radius_solar": r_star,
        "methods": out_methods,
        "assumptions": {
            "reference_version": defaults["reference_version"],
            "confidence": defaults["confidence"],
            "out_of_domain": out_of_domain,
            "mag_domain": dom,
            "host_class": host_class,
            "host_class_note": (None if host_class is None else
                                f"host is {host_class} (non-main-sequence) — MS mass/radius and the "
                                "sp_type→jitter map were NOT applied; the survey-floor defaults are "
                                "MS-calibrated and may not transfer. Pass explicit --star-mass-solar / "
                                "--star-radius-solar to compute on the real host."),
            "domain_note": _domain_note(mag_out, app_mag, dom, host_class),
            "sma_grid_au": list(grid),
            "albedo": albedo,
            "monotonicity": "RV min-mass increases with SMA; transit min-radius is SMA-independent "
                            "(depth-driven — transit_prob falls with SMA instead); astrometry/imaging "
                            "min-planet decreases with SMA (astrometry until P>baseline; imaging until IWA)",
        },
    }
