# core/regions.py — Star System Regions calculations (options 9–11, 14).
# Phase B: compute_sol_regions() (option 14).
# Phase C: spectral-class helpers + compute_star_system_regions_from_simbad() added.

import math
import re

from core.db import get_conn
from core.equations import compute_solvent_zone, compute_ice_lines, _t_ref_surface

# ── Spectral-class helpers (shared by options 9, 10, 13) ─────────────────────

_SP_PATTERN = re.compile(r"(?<![A-Z])([OBAFGKM])(\d+(?:\.\d+)?)")
_LETTER_SEQUENCE = ["O", "B", "A", "F", "G", "K", "M"]
_MAIN_SEQUENCE_DATA = None


def _load_main_sequence_data() -> dict:
    """Load main_sequence_stars DB table into a per-class lookup dict.

    Returns {letter: [(subtype_float, row_dict), ...]} sorted ascending by subtype.
    Row dicts use the original CSV column names so all callers work unchanged.
    Cached after first load.
    """
    global _MAIN_SEQUENCE_DATA
    if _MAIN_SEQUENCE_DATA is not None:
        return _MAIN_SEQUENCE_DATA

    data: dict = {}
    try:
        conn = get_conn()
        rows = conn.execute("""
            SELECT
                spectral_class  AS "Spectral Class",
                b_v             AS "B-V",
                teff_k          AS "Teeff(K)",
                abs_mag_vis     AS "AbsMag Vis.",
                abs_mag_bol     AS "AbsMag Bol.",
                bc              AS "Bolo. Corr. (BC)",
                lum             AS "Lum",
                radius          AS "R",
                mass            AS "M",
                density         AS "p (g/cm3)",
                lifetime        AS "Lifetime (years)"
            FROM main_sequence_stars
        """).fetchall()
        for row in rows:
            row = dict(row)
            sc = row.get("Spectral Class", "").strip()
            m = _SP_PATTERN.match(sc)
            if not m:
                continue
            letter = m.group(1)
            subtype = float(m.group(2))
            data.setdefault(letter, []).append((subtype, row))
        for letter in data:
            data[letter].sort(key=lambda t: t[0])
    except Exception:
        data = {}

    _MAIN_SEQUENCE_DATA = data
    return _MAIN_SEQUENCE_DATA


def _parse_spectral_class(sp_str: str):
    """Extract (letter, subtype_float) from a spectral type string.

    Returns (None, None) if no OBAFGKM class is found.
    Uses _SP_PATTERN.search so prefixes like 'sd' in 'sdG5' are skipped.
    """
    if not sp_str or sp_str in ("N/A", "None", ""):
        return None, None
    m = _SP_PATTERN.search(sp_str)
    if not m:
        return None, None
    return m.group(1), float(m.group(2))


def _lookup_spectral_type(sp_str: str):
    """Return (row_dict, key_str) for the nearest ceiling entry in the CSV.

    Ceiling rule: smallest available subtype >= requested subtype.
    If all entries in the class are cooler than requested, advances to the
    next cooler letter class's hottest entry (e.g. F9 → G0).
    Returns (None, None) on failure.
    """
    data = _load_main_sequence_data()
    letter, subtype = _parse_spectral_class(sp_str)
    if not letter or letter not in data:
        return None, None

    entries = data[letter]
    for st, row in entries:
        if st >= subtype:
            return row, f"{letter}{st}"

    # All entries are cooler — fall through to next letter class
    idx = _LETTER_SEQUENCE.index(letter)
    if idx + 1 < len(_LETTER_SEQUENCE):
        next_letter = _LETTER_SEQUENCE[idx + 1]
        if next_letter in data:
            st, row = data[next_letter][0]
            return row, f"{next_letter}{st}"

    return None, None


def compute_star_system_regions(
    vmag: float,
    boloLum: float,
    temp: float,
    plx: float,
    sunlight_intensity: float = 1.0,
    bond_albedo: float = 0.3,
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
    parsecs = 1000.0 / plx
    absMagnitude = vmag + 5.0 - (5.0 * math.log10(parsecs))
    bcAbsMagnitude = absMagnitude + boloLum
    bcLuminosity = 2.52 ** (4.85 - bcAbsMagnitude)
    stellarMass = bcLuminosity ** 0.2632
    luminosityFromMass = stellarMass ** 3.5

    stellarRadius = stellarMass ** 0.57 if stellarMass >= 1.0 else stellarMass ** 0.8
    stellarDiameterSol = ((5780.0 ** 2) / (temp ** 2)) * math.sqrt(bcLuminosity)
    stellarDiameterKM = stellarDiameterSol * 1391600.0
    mainSeqLifeSpan = (10.0 ** 10) * ((1.0 / stellarMass) ** 2.5)

    trigParallax = plx / 1000.0
    lightYears = 3.26156 / trigParallax

    distAU = math.sqrt(bcLuminosity / sunlight_intensity)
    distKM = distAU * 149000000.0
    planetaryYear = math.sqrt((distAU ** 3) / stellarMass)
    # Phase P P1e: M1 surface model with the correct (1−A)^0.25 albedo exponent
    # (was the badly-wrong linear (1−A); identical at A=0.3 → 288 K, correct
    # elsewhere). _t_ref_surface(A) = 314.9 × (1−A)^0.25.
    planetaryTemperature = _t_ref_surface(bond_albedo) * (sunlight_intensity ** 0.25)
    planetaryTemperatureC = planetaryTemperature - 273.15
    planetaryTemperatureF = (planetaryTemperatureC * 9.0 / 5.0) + 32.0
    starAngularDiameter = 57.3 ** (stellarDiameterKM / distKM)
    sizeOfSun = f"{starAngularDiameter:.2f}\N{DEGREE SIGN}"

    sysilGrav = 0.2 * stellarMass
    sysilSunlight = math.sqrt(bcLuminosity / 16.0)
    hzil = math.sqrt(bcLuminosity / 1.1)
    hzol = math.sqrt(bcLuminosity / 0.53)
    # Phase P P1c: the canonical water snow line — 170 K / 2.68 AU (M2), was the
    # greenhouse-baked surface model misapplied to an ice line (0.04 → 5.0 AU).
    snowLine = math.sqrt(bcLuminosity / 0.139)
    # P1b: value unchanged — under M2 this 0.0025 divisor is the 62 K / 20 AU
    # N₂/CO 1-atm surface-frost line (relabelled in the displays, not retuned).
    lh2Line = math.sqrt(bcLuminosity / 0.0025)
    sysol = 40.0 * stellarMass

    calculatedLuminosity = stellarRadius ** 2 * (temp / 5778.0) ** 4

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
    }


def compute_star_system_regions_from_simbad(
    simbad_result: dict,
    sunlight_intensity: float = 1.0,
    bond_albedo: float = 0.3,
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
    letter, _ = _parse_spectral_class(sp_type)
    if not letter:
        sp_display = sp_type or "N/A"
        return {
            "error": (
                f"Spectral type '{sp_display}' is not a main-sequence class "
                "(O B A F G K M) — cannot determine star system region."
            )
        }

    ms_row, bc_key = _lookup_spectral_type(sp_type)
    if ms_row is None:
        return {"error": f"Could not find spectral type '{sp_type}' in main sequence data."}

    try:
        boloLum = float(ms_row["Bolo. Corr. (BC)"])
    except (KeyError, ValueError, TypeError):
        return {"error": "Bolometric correction not available for this spectral type."}

    temp = simbad_result.get("teff")
    if temp is None:
        return {"error": "Temperature not available for this star — cannot determine star system region."}

    vmag = simbad_result.get("vmag")
    if vmag is None:
        return {"error": "Apparent Magnitude (V) not available for this star — cannot determine star system region."}

    plx = simbad_result.get("plx_value")
    if plx is None or plx <= 0:
        return {"error": "Parallax not available for this star — cannot determine star system region."}

    result = compute_star_system_regions(
        vmag=vmag,
        boloLum=boloLum,
        temp=temp,
        plx=plx,
        sunlight_intensity=sunlight_intensity,
        bond_albedo=bond_albedo,
    )
    result["simbad"] = simbad_result
    result["spectral_type"] = sp_type
    result["bc_key"] = bc_key or ""
    return result


def compute_sol_regions() -> dict:
    """All Star System Region calculations for Sol using hardcoded solar constants.

    Returns the same structure as compute_star_system_regions() so the GUI
    panel is reusable for both Sol and user-queried stars.
    """
    vmag = -26.74
    boloLum = -0.07   # Bolometric correction for G2V Sun
    temp = 5778.0
    # Back-compute parallax from vmag and absMag_sun = 4.83
    plx = 1000.0 / (10.0 ** ((-26.74 - 4.83 + 5.0) / 5.0))
    result = compute_star_system_regions(
        vmag=vmag,
        boloLum=boloLum,
        temp=temp,
        plx=plx,
        sunlight_intensity=1.0,
        bond_albedo=0.3,
    )
    # The Sun is G2V — surface the spectral type so the System Regions Diagram
    # offers the Phase O O10b Honorverse hyper-limit ring (opt 13). Additive: the
    # sol-regions query.py output just gains a spectral_type field.
    result["spectral_type"] = "G2V"
    return result
