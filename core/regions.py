# core/regions.py — Star System Regions calculations (options 9–11, 14).
# Phase B: compute_sol_regions() (option 14).
# Phase C: spectral-class helpers + compute_star_system_regions_from_simbad() added.

import csv
import math
import os
import re

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BASE_DIR, "..")

# ── Spectral-class helpers (shared by options 9, 10, 13) ─────────────────────

_SP_PATTERN = re.compile(r"(?<![A-Z])([OBAFGKM])(\d+(?:\.\d+)?)")
_LETTER_SEQUENCE = ["O", "B", "A", "F", "G", "K", "M"]
_MAIN_SEQUENCE_DATA = None


def _load_main_sequence_data() -> dict:
    """Load propertiesOfMainSequenceStars.csv into a per-class lookup dict.

    Returns {letter: [(subtype_float, row_dict), ...]} sorted ascending by subtype.
    Cached after first load.
    """
    global _MAIN_SEQUENCE_DATA
    if _MAIN_SEQUENCE_DATA is not None:
        return _MAIN_SEQUENCE_DATA

    path = os.path.normpath(os.path.join(_DATA_DIR, "propertiesOfMainSequenceStars.csv"))
    data: dict = {}
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
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
    lightYears = 3.2616 / trigParallax

    distAU = math.sqrt(bcLuminosity / sunlight_intensity)
    distKM = distAU * 149000000.0
    planetaryYear = math.sqrt((distAU ** 3) / stellarMass)
    planetaryTemperature = 374.0 * 1.1 * (1.0 - bond_albedo) * (sunlight_intensity ** 0.25)
    planetaryTemperatureC = planetaryTemperature - 273.15
    planetaryTemperatureF = (planetaryTemperatureC * 9.0 / 5.0) + 32.0
    starAngularDiameter = 57.3 ** (stellarDiameterKM / distKM)
    sizeOfSun = f"{starAngularDiameter:.2f}\N{DEGREE SIGN}"

    sysilGrav = 0.2 * stellarMass
    sysilSunlight = math.sqrt(bcLuminosity / 16.0)
    hzil = math.sqrt(bcLuminosity / 1.1)
    hzol = math.sqrt(bcLuminosity / 0.53)
    snowLine = math.sqrt(bcLuminosity / 0.04)
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
    phInner  = math.sqrt(bcLuminosity / 0.0025)
    phOuter  = math.sqrt(bcLuminosity / 0.000024)

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
    return compute_star_system_regions(
        vmag=vmag,
        boloLum=boloLum,
        temp=temp,
        plx=plx,
        sunlight_intensity=1.0,
        bond_albedo=0.3,
    )
