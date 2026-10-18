# core/regions.py — Star System Regions calculations (options 9–11, 14).
# Phase B: compute_sol_regions() (option 14).
# Phase C: spectral-class helpers + compute_star_system_regions_from_simbad() added.

import math

from core import ms_sequence, shared, twomass
from core.equations import (
    compute_solvent_zone, compute_ice_lines, _t_ref_surface, _KM_PER_AU,
)

# ── Spectral-type lookup — CR-30.2: S1 (Mamajek 2022.04.16) through the one parse ─────────────────────
# The old main-sequence CSV / ``main_sequence_stars`` ceiling lookup is retired as a runtime
# input (CR-30.1, ruling 26); every value now comes from the md5-verified S1 table (``core.ms_sequence.s1_at``).


def _lookup_s1(sp_str):
    """``(s1_read, parse)`` — CR-30.2's lookup of a spectral type on S1 (``core.ms_sequence.s1_at``)."""
    p = shared.parse_spectral_type(sp_str)
    return ms_sequence.s1_at(p), p


def _distance_values(vmag, plx):
    """(parsecs, absMagnitude, trigParallax, lightYears) from V and the parallax (mas > 0); absMagnitude None without
    a V. Shared by the region step and ``l_independent_fields``."""
    parsecs = 1000.0 / plx
    absMagnitude = (vmag + 5.0 - (5.0 * math.log10(parsecs))) if vmag is not None else None
    trigParallax = plx / 1000.0
    return parsecs, absMagnitude, trigParallax, 3.26156 / trigParallax


def _eeo_temperatures(bond_albedo, sunlight_intensity):
    """The Earth-equivalent orbit's planetary temperature (K, °C, °F) — independent of the star's luminosity."""
    t = _t_ref_surface(bond_albedo) * (sunlight_intensity ** 0.25)
    c = t - 273.15
    return t, c, (c * 9.0 / 5.0) + 32.0


def compute_star_system_regions(
    vmag: float,
    boloLum: float,
    temp: float,
    plx: float,
    sunlight_intensity: float = 1.0,
    bond_albedo: float = 0.3,
    lum_override: float = None,
    mass_override: dict = None,
) -> dict:
    """Compute all Star System Region values from the six raw input parameters.

    This is the shared core calculation used by options 9, 10, 11, and 14.
    All display formatting is left to the GUI/CLI caller.

    Args:
        vmag:              apparent magnitude (V)
        boloLum:           bolometric correction (BC)
        temp:              stellar effective temperature in K
        plx:               parallax in mas (> 0)
        sunlight_intensity: sunlight intensity relative to Terra (default 1.0)
        bond_albedo:       Bond albedo (default 0.3)

    Returns:
        A dict containing every computed value needed by the display helpers.
        Keys are the same variable names used in the CLI display functions.
    """
    parsecs, absMagnitude, trigParallax, lightYears = _distance_values(vmag, plx)
    # CR-30.3 (ruling 9): S1's own zero point and the exact magnitude step — L = 10^(−0.4 (M_bol − 4.74)), M_bol =
    # M_V + BC_V with S1's BC_V (the legacy 2.52 / 4.85 pairing is retired). The region divisors below are unchanged.
    if lum_override is not None:
        # the colour route's luminosity (CR-30.3) — M_bol and the effective BC restated on S1's zero point
        bcLuminosity = lum_override
        bcAbsMagnitude = ms_sequence.M_BOL_SUN_S1 - 2.5 * math.log10(lum_override)
        boloLum = bcAbsMagnitude - absMagnitude
    else:
        bcAbsMagnitude = absMagnitude + boloLum
        bcLuminosity = ms_sequence.luminosity_from_mbol(bcAbsMagnitude)
    # CR-30.4: the mass — the M_Ks route where the caller resolved one (``mass_override``), else the L route
    # (Eker 2018 inverted / S1's sequence; null below M9.5V — never clamped); the L-route mass reported beside it.
    lroute = ms_sequence.mass_from_luminosity(bcLuminosity)
    if mass_override and mass_override.get("mass") is not None:
        stellarMass = mass_override["mass"]
        mass_info = {"mass_route": mass_override.get("route", "mks"),
                     "mass_relation": mass_override.get("relation", "Mann2019_n5"), "mass_segment": None,
                     "mass_switch_band": None}
    else:
        stellarMass = lroute["mass"]
        mass_info = {"mass_route": "luminosity", "mass_relation": lroute["relation"],
                     "mass_segment": lroute["segment"], "mass_switch_band": lroute["switch_band"]}
    mass_info["mass_lroute_solar"] = lroute["mass"]
    mass_info["mass_lroute_null_reason"] = lroute["reason"]
    # L(M) / R(M) (CR-30.4) and the MIST v2.5 lifetime (CR-30.5); a null mass nulls every value derived from it
    lfm = ms_sequence.luminosity_from_mass(stellarMass)
    rfm = ms_sequence.radius_from_mass(stellarMass)
    life = ms_sequence.ms_lifetime(stellarMass)
    luminosityFromMass = lfm["lum"]
    stellarRadius = rfm["radius"]
    mass_info.update({"luminosity_from_mass_relation": lfm["relation"], "luminosity_from_mass_null_reason":
                      lfm["reason"], "radius_from_mass_relation": rfm["relation"], "radius_from_mass_null_reason":
                      rfm["reason"], "ms_lifetime_end_point": life["end_point"], "ms_lifetime_status": life["status"],
                      "ms_lifetime_note": life["note"]})
    if stellarMass is None:
        mass_info["mass_null_reason"] = lroute["reason"]
    stellarDiameterSol = ((5780.0 ** 2) / (temp ** 2)) * math.sqrt(bcLuminosity)
    stellarDiameterKM = stellarDiameterSol * 1391600.0
    mainSeqLifeSpan = life["yr"]

    distAU = math.sqrt(bcLuminosity / sunlight_intensity)
    # P1.4: canonical AU→km (149597870.7) — was 149000000.0 (0.4% low, the only
    # AU value in the app not sourced from equations._KM_PER_AU).
    distKM = distAU * _KM_PER_AU
    planetaryYear = math.sqrt((distAU ** 3) / stellarMass) if stellarMass else None
    # Phase P P1e: M1 surface model with the correct (1−A)^0.25 albedo exponent
    # (was the badly-wrong linear (1−A); identical at A=0.3 → 288 K, correct
    # elsewhere). _t_ref_surface(A) = 314.9 × (1−A)^0.25.
    planetaryTemperature, planetaryTemperatureC, planetaryTemperatureF = _eeo_temperatures(bond_albedo,
                                                                                         sunlight_intensity)
    # P1.1: small-angle diameter in degrees = (d/D) × 57.3 (rad→deg). Was the
    # exponentiation 57.3 ** (d/D) — a bug that rendered the Sun at ~1.04°
    # instead of ~0.53°, with non-linear error across stars.
    starAngularDiameter = 57.3 * (stellarDiameterKM / distKM)
    sizeOfSun = f"{starAngularDiameter:.2f}\N{DEGREE SIGN}"

    sysilGrav = 0.2 * stellarMass if stellarMass is not None else None
    sysilSunlight = math.sqrt(bcLuminosity / 16.0)
    hzil = math.sqrt(bcLuminosity / 1.1)
    hzol = math.sqrt(bcLuminosity / 0.53)
    # Phase P P1c: the canonical water snow line — 170 K / 2.68 AU (M2), was the
    # greenhouse-baked surface model misapplied to an ice line (0.04 → 5.0 AU).
    snowLine = math.sqrt(bcLuminosity / 0.139)
    # P1b: value unchanged — under M2 this 0.0025 divisor is the 62 K / 20 AU
    # N₂/CO 1-atm surface-frost line (relabelled in the displays, not retuned).
    lh2Line = math.sqrt(bcLuminosity / 0.0025)
    sysol = 40.0 * stellarMass if stellarMass is not None else None

    # 5778 K here is the legacy solar-Teff convention (vs IAU nominal 5772 used
    # by core/cooling.py and core/par_flux.py); kept for output stability. See
    # IMPROVEMENT_PLAN P1.5.
    calculatedLuminosity = stellarRadius ** 2 * (temp / 5778.0) ** 4 if stellarRadius is not None else None

    ffInner  = math.sqrt(bcLuminosity / 52.0)
    ffOuter  = math.sqrt(bcLuminosity / 29.9)
    fsInner  = math.sqrt(bcLuminosity / 38.7)
    fsOuter  = math.sqrt(bcLuminosity / 3.2)
    prwInner = math.sqrt(bcLuminosity / 2.8)
    prwOuter = math.sqrt(bcLuminosity / 0.8)
    praInner = math.sqrt(bcLuminosity / 0.48)
    praOuter = math.sqrt(bcLuminosity / 0.21)
    pmInner  = math.sqrt(bcLuminosity / 0.023)
    pmOuter  = math.sqrt(bcLuminosity / 0.0094)
    # Phase P P1a: hydrogen band corrected to its real 1-atm liquid range
    # (boil 20.3 K / freeze 13.8 K → ~200–440 AU). The legacy 0.0025/0.000024
    # put the inner edge supercritical (H₂ crit 33 K) and the outer at the boil.
    phInner  = math.sqrt(bcLuminosity / 0.0000247)
    phOuter  = math.sqrt(bcLuminosity / 0.0000053)

    # Phase P P2: additional alternative-solvent bands (M1 surface model, A=0.3),
    # derived from the shared _SOLVENTS liquid ranges via compute_solvent_zone so
    # they cannot drift from the Solvent Habitable Zone calculator. Additive — the
    # existing ff/fs/prw/pra/pm/ph bands are untouched.
    _co2 = compute_solvent_zone(bcLuminosity, "co2")            # pressure-conditional (≥5.2 atm)
    _sulfur = compute_solvent_zone(bcLuminosity, "sulfur")
    _wa = compute_solvent_zone(bcLuminosity, "water_ammonia")   # eutectic (approx)
    _sa = compute_solvent_zone(bcLuminosity, "sulfuric_acid")
    co2Inner, co2Outer = _co2["inner_au"], _co2["outer_au"]
    sInner,   sOuter   = _sulfur["inner_au"], _sulfur["outer_au"]
    waInner,  waOuter  = _wa["inner_au"], _wa["outer_au"]
    saInner,  saOuter  = _sa["inner_au"], _sa["outer_au"]

    # Phase P P3: volatile ice-condensation fronts (M2 equilibrium, A=0). Additive
    # keys for the CO₂/NH₃/N₂/CO fronts (the canonical water snow line stays the
    # existing snowLine key — corrected to 170 K / 2.68 AU in P1c). N₂/CO are
    # disk-midplane-set, so their irradiation placement is illustrative.
    _ice_by_t = {int(round(l["t_cond_k"])): l["au"]
                 for l in compute_ice_lines(bcLuminosity)["lines"]}
    iceLineNH3 = _ice_by_t[80]
    iceLineCO2 = _ice_by_t[70]
    iceLineN2  = _ice_by_t[22]
    iceLineCO  = _ice_by_t[20]

    return {
        # Inputs (stored for display)
        "vmag": vmag,
        "boloLum": boloLum,
        "temp": temp,
        "plx": plx,
        "sunlight_intensity": sunlight_intensity,
        "bond_albedo": bond_albedo,
        # Star System Properties
        "parsecs": parsecs,
        "absMagnitude": absMagnitude,
        "bcAbsMagnitude": bcAbsMagnitude,
        "bcLuminosity": bcLuminosity,
        "luminosityFromMass": luminosityFromMass,
        # Stellar Properties
        "stellarMass": stellarMass,
        "stellarRadius": stellarRadius,
        "stellarDiameterSol": stellarDiameterSol,
        "stellarDiameterKM": stellarDiameterKM,
        "mainSeqLifeSpan": mainSeqLifeSpan,
        # Star Distance
        "trigParallax": trigParallax,
        "lightYears": lightYears,
        # Earth Equivalent Orbit
        "distAU": distAU,
        "distKM": distKM,
        "planetaryYear": planetaryYear,
        "planetaryTemperature": planetaryTemperature,
        "planetaryTemperatureC": planetaryTemperatureC,
        "planetaryTemperatureF": planetaryTemperatureF,
        "sizeOfSun": sizeOfSun,
        # Solar System Regions
        "sysilGrav": sysilGrav,
        "sysilSunlight": sysilSunlight,
        "hzil": hzil,
        "hzol": hzol,
        "snowLine": snowLine,
        "lh2Line": lh2Line,
        "sysol": sysol,
        # Calculated Luminosity (for HZ table)
        "calculatedLuminosity": calculatedLuminosity,
        # Alternate HZ regions
        "ffInner": ffInner,   "ffOuter": ffOuter,
        "fsInner": fsInner,   "fsOuter": fsOuter,
        "prwInner": prwInner, "prwOuter": prwOuter,
        "praInner": praInner, "praOuter": praOuter,
        "pmInner": pmInner,   "pmOuter": pmOuter,
        "phInner": phInner,   "phOuter": phOuter,
        # Phase P P2 — additional alternative-solvent bands (M1)
        "co2Inner": co2Inner, "co2Outer": co2Outer,
        "sInner": sInner,     "sOuter": sOuter,
        "waInner": waInner,   "waOuter": waOuter,
        "saInner": saInner,   "saOuter": saOuter,
        # Phase P P3 — volatile ice-condensation fronts (M2)
        "iceLineNH3": iceLineNH3, "iceLineCO2": iceLineCO2,
        "iceLineN2":  iceLineN2,  "iceLineCO":  iceLineCO,
        # CR-30.4 / 30.5 — the mass route, the relations and the lifetime end point
        **mass_info,
    }


def l_independent_fields(simbad_result, sunlight_intensity=1.0, bond_albedo=0.3):
    """CR-30.3 (MSG 366 F-8, Greg's ruling): the region result's fields that do not depend on the region luminosity —
    the inputs, the distance and the Earth-equivalent planetary temperature — computed as
    ``compute_star_system_regions`` does, for a result whose region L is withheld (a 2MASS degrade). A missing input
    leaves the fields derived from it out."""
    sr = simbad_result or {}
    vmag, temp, plx = sr.get("vmag"), sr.get("teff"), sr.get("plx_value")
    out = {"vmag": vmag, "temp": temp, "plx": plx, "sunlight_intensity": sunlight_intensity,
           "bond_albedo": bond_albedo, "spectral_type": sr.get("sp_type") or ""}
    if isinstance(plx, (int, float)) and plx > 0:
        pc, absmag, trig, ly = _distance_values(vmag if isinstance(vmag, (int, float)) else None, plx)
        out.update(parsecs=pc, trigParallax=trig, lightYears=ly)
        if absmag is not None:
            out["absMagnitude"] = absmag
    t, c, f = _eeo_temperatures(bond_albedo, sunlight_intensity)
    out.update(planetaryTemperature=t, planetaryTemperatureC=c, planetaryTemperatureF=f)
    return out


ERR_NO_TEFF = "Temperature not available for this star — cannot determine star system region."
ERR_NO_VMAG = "Apparent Magnitude (V) not available for this star — cannot determine star system region."
ERR_NO_PLX = "Parallax not available for this star — cannot determine star system region."
# CR-30.4 / 30.6 F: the region step's missing-input failures — with a 2MASS degrade, the only ones on which the dossier
# still reports the resolved mass, its placement and #26 (WB MSG 366 F-5; a non-main-sequence class keeps HEAD's output)
MISSING_INPUT_ERRORS = (ERR_NO_TEFF, ERR_NO_VMAG, ERR_NO_PLX)


def is_input_failure(reg):
    """True when a region step failed on a missing Teff / V / parallax or a 2MASS degrade (only the region L withheld —
    MSG 366 F-5 / F-8) — not on a non-main-sequence class or an unreadable type."""
    return (isinstance(reg, dict) and (reg.get("error") in MISSING_INPUT_ERRORS
                                       or bool(twomass.degrade_marker(reg))))


def compute_star_system_regions_from_simbad(
    simbad_result: dict,
    sunlight_intensity: float = 1.0,
    bond_albedo: float = 0.3,
    twomass_lookup: bool = True,
) -> dict:
    """Compute Star System Regions from a simbad_result dict.

    Looks up the bolometric correction from the main-sequence CSV using the
    SIMBAD spectral type, then delegates to compute_star_system_regions().

    Args:
        simbad_result:     dict returned by core.databases.compute_simbad_lookup()
        sunlight_intensity: relative to Terra (default 1.0)
        bond_albedo:       Bond albedo (default 0.3)

    Returns the same structure as compute_star_system_regions(), extended with:
        "simbad"        — the original simbad_result dict
        "spectral_type" — str: spectral type string used
        "bc_key"        — str: CSV key that was matched (e.g. "G2")

    Returns {"error": str} on any validation failure.
    """
    if "error" in simbad_result:
        return simbad_result

    sp_type = simbad_result.get("sp_type") or ""
    s1, parse = _lookup_s1(sp_type)
    if parse.letter is None or parse.letter not in "OBAFGKM":
        sp_display = sp_type or "N/A"
        return {
            "error": (
                f"Spectral type '{sp_display}' is not a main-sequence class "
                "(O B A F G K M) — cannot determine star system region."
            )
        }
    fields = _s1_fields(s1, parse)

    # CR-30.3: the star's 2MASS resolution (K / M only) — a degrade fails loud here, never the subtype route
    # (``twomass_lookup=False`` — a caller whose request needs no luminosity, e.g. a dossier identity section —
    # makes no 2MASS call: the routes are then not taken, as for a lookup that never ran)
    # A giant / subgiant (class I–IV) takes neither 2MASS route (the colour route is a dwarf relation; Mann 2019's
    # M_Ks relation too) — no lookup, so a VizieR outage never marks it (CP2).
    # Neither route runs without a parallax (the colour route's M_bol and the M_Ks route both need it) — no lookup,
    # so a VizieR outage never masks the real "Parallax not available" error (CP6 #5)
    _plx = simbad_result.get("plx_value")
    if not (isinstance(_plx, (int, float)) and _plx > 0):
        twomass_lookup = False
    if parse.lum_class_core in ("I", "II", "III", "IV"):
        twomass_lookup = False
        if parse.letter in ("K", "M"):
            fields["lum_route_reason"] = (f"luminosity class {parse.lum_class_token} (a giant / subgiant) — S1's "
                                          "subtype route; no 2MASS lookup")
    tm = (twomass.resolve(simbad_result) if twomass_lookup
          else {"status": twomass.NOT_LOOKED_UP, "ids": [], "jks": None})
    fields.update(_twomass_disclosure(tm))
    if tm["status"] in twomass.DEGRADE_STATUSES:
        return {"error": twomass.NOTE_DEGRADE[tm["status"]], **twomass.degrade_fields(tm["status"]), **fields}
    # CR-30.4 (ruling 164; pre-fire ruling 21 D8 F1): the M_Ks route needs no V — computed BEFORE the region step's
    # Teff / V / parallax checks so a failed region step still carries it (``mks`` rides on the error too)
    mks = mks_route(simbad_result, tm=tm, parse=parse)
    fields["mks"] = mks
    fields["mass_mks_solar"] = mks["mass"]
    fields["m_ks"] = mks["m_ks"]

    temp = simbad_result.get("teff")
    if temp is None:
        return {"error": ERR_NO_TEFF, **fields}

    vmag = simbad_result.get("vmag")
    if vmag is None:
        return {"error": ERR_NO_VMAG, **fields}

    plx = simbad_result.get("plx_value")
    if plx is None or plx <= 0:
        return {"error": ERR_NO_PLX, **fields}

    # the colour route (CR-30.3; ruling 24): a K / M dwarf with one 2MASS identifier and V − J in span
    colour = None
    jks = tm.get("jks")
    if jks:
        ok, why = ms_sequence.colour_gate(parse, vmag - jks["j"])
        if ok:
            colour = ms_sequence.colour_route_luminosity(vmag, jks["j"], jks["ks"], plx)
        else:
            fields["lum_route_reason"] = why
    elif tm["status"] in ("no_id", "multiple"):
        fields["lum_route_reason"] = twomass.NOTE_NO_ID if tm["status"] == "no_id" else twomass.NOTE_MULTIPLE

    if colour is None and s1["BCv"] is None:
        # a letter-only O/B/A/M type, or a type S1 cannot read, with no colour route (Q5) — the curated reason
        return {"error": f"Could not read spectral type '{sp_type}' on S1: {s1['s1_null_reason']}.", **fields}
    boloLum = s1["BCv"]
    bc_key = s1["sp_type_read"]

    result = compute_star_system_regions(
        vmag=vmag,
        boloLum=boloLum if boloLum is not None else 0.0,
        temp=temp,
        plx=plx,
        sunlight_intensity=sunlight_intensity,
        bond_albedo=bond_albedo,
        lum_override=(colour["lum"] if colour else None),
        mass_override=(mks if mks["mass"] is not None else None),
    )
    result["simbad"] = simbad_result
    result["spectral_type"] = sp_type
    result["bc_key"] = bc_key or ""
    result.update(fields)
    sub_l = (ms_sequence.luminosity_from_mbol(result["absMagnitude"] + s1["BCv"]) if s1["BCv"] is not None
             else None)
    result["lum_subtype_lsun"] = sub_l
    if colour:
        result["lum_route"] = "colour"
        result["lum_colour_lsun"] = colour["lum"]
        result["lum_colour_paths"] = {"bc_v": colour["bc_v_path_lum"], "bc_k": colour["bc_k_path_lum"]}
        result["v_minus_j"] = colour["v_minus_j"]
        result["lum_route_disagreement"] = bool(
            sub_l and max(colour["lum"], sub_l) / min(colour["lum"], sub_l) > ms_sequence.COLOUR_DISAGREE_RATIO)
        result["lum_route_note"] = ("colour route: Mann et al. 2015 Table 3 base rows on V − J (no [Fe/H] term), the "
                                    "mean of the BC_V and BC_K paths at Mann's zero point 4.755 (×1.014 against "
                                    "S1's 4.74, disclosed)")
    else:
        result["lum_route"] = "subtype"
        result["lum_colour_lsun"] = None
        if jks:
            result["v_minus_j"] = vmag - jks["j"]
    return result


def mks_route(simbad_result, tm=None, parse=None):
    """CR-30.4's M_Ks route (ruling 52; gate 4.5–10.5 inclusive; Mann et al. 2019 n = 5) for a SIMBAD record →
    ``{status, mass, m_ks, ks, ph_qual, rd_flg, note, binary_disclosure}``.

    A K or M type letter (letter-only included) with exactly one SIMBAD ``2MASS`` identifier (``tm`` — the
    record's 2MASS resolution, resolved here when not given) and a parallax. ``status``: ``ok`` (a mass),
    ``outside_gate`` (M_Ks outside 4.5–10.5 — the L route; never clipped), ``no_parallax``, ``not_km`` /
    ``giant`` (no route), or the 2MASS status (``no_id`` / ``multiple`` / ``not_looked_up`` — the L route; a
    degrade status — fails loud upstream). Needs no V (ruling 164)."""
    from core import ms_sequence as ms
    parse = parse or shared.parse_spectral_type((simbad_result or {}).get("sp_type"))
    out = {"status": None, "mass": None, "m_ks": None, "ks": None, "ph_qual": None, "rd_flg": None, "note": None,
           "binary_disclosure": None}
    if parse.letter not in ("K", "M"):
        out["status"] = "not_km"
        return out
    if parse.lum_class_core in ("I", "II", "III", "IV"):
        out["status"] = "giant"
        return out
    if tm is None:
        tm = twomass.resolve(simbad_result)
    jks = tm.get("jks")
    if not jks:
        out["status"] = tm.get("status")
        return out
    plx = (simbad_result or {}).get("plx_value")
    out.update(ks=jks["ks"], ph_qual=jks.get("ph_qual"), rd_flg=jks.get("rd_flg"))
    if plx is None or not (plx > 0):
        out["status"] = "no_parallax"
        out["note"] = "no parallax — no M_Ks"
        return out
    m_ks = jks["ks"] + 5.0 * math.log10(plx / 1000.0) + 5.0
    out["m_ks"] = m_ks
    mass = ms.mks_mass(m_ks)
    if mass is None:
        out["status"] = "outside_gate"
        out["note"] = (f"M_Ks {m_ks:.4f} outside the M_Ks route's gate 4.5–10.5 (never clipped) — the L route")
        return out
    out.update(status="ok", mass=mass, binary_disclosure=ms.MKS_BINARY_DISCLOSURE)
    # ruling 134 W-7: an activity otype carries S13's ≈ 2 % caveat — never a placement input
    from core import exclusion_wall
    if exclusion_wall.active_otype_matches((simbad_result or {}).get("otype")):
        out["activity_caveat"] = ms.MKS_ACTIVITY_CAVEAT
    return out


def _twomass_disclosure(tm):
    """CR-30.3 / 30.4: the 2MASS fields every region output carries (``twomass`` with its quality flags;
    ``twomass_ids_multiple`` — a disclosure, never a degrade, F4)."""
    out = {}
    jks = tm.get("jks")
    if jks:
        out["twomass"] = {k: jks.get(k) for k in ("designation", "j", "e_j", "ks", "e_ks", "ph_qual", "rd_flg",
                                                   "quality_below_a")}
    if tm.get("status") == "multiple":
        out["twomass_ids_multiple"] = list(tm["ids"])
    return out


S1_FIELD_KEYS = ("sp_type_raw", "sp_type_read", "lum_class_token", "subdwarf_flag", "gravity_designation",
                 "low_gravity_class", "s1_class_v_flag", "subtype_unknown", "subtype_span_note", "s1_rows",
                 "s1_fraction")
REGION_LUM_KEYS = ("lum_route", "lum_route_reason", "lum_colour_lsun", "lum_subtype_lsun", "lum_colour_paths",
                   "v_minus_j", "twomass", "twomass_ids_multiple", "lum_route_disagreement", "lum_route_note")


def region_lum_fields(reg):
    """The type-read and luminosity-route fields of a region-step result (for a result built on it)."""
    return {k: reg[k] for k in S1_FIELD_KEYS + REGION_LUM_KEYS if k in reg}


def _s1_fields(s1, parse):
    """CR-30.2's additive output fields for an S1 read (name map ``spectral_parse``)."""
    out = parse.as_fields()
    out.update({"s1_class_v_flag": True, "subtype_unknown": bool(s1.get("subtype_unknown")),
                "subtype_span_note": s1.get("subtype_span_note"), "s1_rows": s1.get("s1_rows"),
                "s1_fraction": s1.get("s1_fraction")})
    return out


def compute_sol_regions() -> dict:
    """All Star System Region calculations for Sol (CR-30.3, ruling 22).

    Willmer 2018's V☉ −26.76 and M_V☉ 4.81 with BC −0.07 (IAU 2015 B2's M_bol,☉ 4.74 minus Willmer's M_V☉), so
    M_bol,☉ = 4.74 and Sol computes to 1.0000 L☉ on S1's zero point — every constant pinned. Sol's ``temp = 5778.0``
    (IAU 2015 nominal 5772 K) is kept and disclosed; it touches only Sol's radius.
    """
    vmag = -26.76
    boloLum = -0.07
    temp = 5778.0
    # Back-compute parallax from V☉ and M_V☉ = 4.81 (Willmer 2018)
    plx = 1000.0 / (10.0 ** ((vmag - 4.81 + 5.0) / 5.0))
    result = compute_star_system_regions(
        vmag=vmag,
        boloLum=boloLum,
        temp=temp,
        plx=plx,
        sunlight_intensity=1.0,
        bond_albedo=0.3,
        # Sol's mass is pinned at 1.000 M☉ (ruling 93 L3) — not read back through mass from L (1.0028 at log L 0)
        mass_override={"mass": 1.0, "route": "sol_pinned", "relation": "pinned_1.000"},
    )
    # The Sun is G2V — surface the spectral type so the System Regions Diagram
    # offers the Phase O O10b Honorverse hyper-limit ring (opt 13). Additive: the
    # sol-regions query.py output just gains a spectral_type field.
    result["spectral_type"] = "G2V"
    result["sol_constants_note"] = ("Willmer 2018 V☉ −26.76, M_V☉ 4.81, BC −0.07 → M_bol,☉ 4.74 (IAU 2015 B2) → "
                                    "1.0000 L☉; temp 5778 K (IAU nominal 5772 K) touches only the radius")
    return result
