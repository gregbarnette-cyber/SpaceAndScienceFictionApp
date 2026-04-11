# core/regions.py — Star System Regions calculations (options 9–11, 14).
# Phase B: compute_sol_regions() (option 14).
# Phase C: compute_star_system_regions() added for SIMBAD-based options 9–11.

import math


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
