"""core/detection_tables.py — CR-6 PROVISIONAL Interface-B (3a) survey-completeness defaults.

The WB 3a *survey-completeness reference* (Interface B, coordination MSG 035/037) is consumed
through ``_DETECTION_DEFAULTS`` — a per-(method, apparent-magnitude-bin) capability table in the
pinned shape. All values are labelled-illustrative / provisional; WB delivers the finalized table
(same shape + an instrument-era axis) → swap this constant, no code change.

`by_mag` is keyed by apparent magnitude in each method's working band (RV/transit ≈ V; astrometry =
Gaia G; imaging = host mag for the contrast anchor). Bin edges (WB-pinned): {≤6, 6–8, 8–10, 10–12,
12–15, >15}.
"""

# Bin upper edges (inclusive-below); the last bin is open (>15).
_MAG_BIN_EDGES = (6.0, 8.0, 10.0, 12.0, 15.0, float("inf"))

_DETECTION_DEFAULTS = {
    "reference_version": "provisional-0 (APP placeholder; awaiting WB 3a reference)",
    "methods": {
        "rv": {  # radial velocity — precision degrades toward fainter targets
            "baseline_yr": 10.0,
            "by_mag": [
                {"mag_max": 6.0,  "precision_m_s": 1.0},
                {"mag_max": 8.0,  "precision_m_s": 1.5},
                {"mag_max": 10.0, "precision_m_s": 3.0},
                {"mag_max": 12.0, "precision_m_s": 10.0},
                {"mag_max": 15.0, "precision_m_s": 30.0},
                {"mag_max": float("inf"), "precision_m_s": 100.0},
            ],
        },
        "transit": {  # photometric precision (ppm) over a coverage window
            "coverage_days": 365.0,
            "by_mag": [
                {"mag_max": 6.0,  "phot_precision_ppm": 50.0},
                {"mag_max": 8.0,  "phot_precision_ppm": 80.0},
                {"mag_max": 10.0, "phot_precision_ppm": 150.0},
                {"mag_max": 12.0, "phot_precision_ppm": 400.0},
                {"mag_max": 15.0, "phot_precision_ppm": 1000.0},
                {"mag_max": float("inf"), "phot_precision_ppm": 3000.0},
            ],
        },
        "astrometry": {  # Gaia-class per-source astrometric precision (µas)
            "baseline_yr": 10.0,
            "by_mag": [
                {"mag_max": 6.0,  "astrom_precision_uas": 30.0},
                {"mag_max": 8.0,  "astrom_precision_uas": 30.0},
                {"mag_max": 10.0, "astrom_precision_uas": 50.0},
                {"mag_max": 12.0, "astrom_precision_uas": 150.0},
                {"mag_max": 15.0, "astrom_precision_uas": 500.0},
                {"mag_max": float("inf"), "astrom_precision_uas": 2000.0},
            ],
        },
        "imaging": {  # reflected-light contrast curve: Δmag detectable vs separation (arcsec)
            "anchored_to_star_mag": 5.0,
            "contrast_curve": [
                {"sep_arcsec": 0.10, "delta_mag": 5.0},
                {"sep_arcsec": 0.30, "delta_mag": 10.0},
                {"sep_arcsec": 0.50, "delta_mag": 12.5},
                {"sep_arcsec": 1.00, "delta_mag": 15.0},
                {"sep_arcsec": 2.00, "delta_mag": 18.0},
            ],
        },
    },
    "domain": {"mag_range": [0.0, 20.0],
               "caveats": "provisional placeholder; achievable contrast degrades for hosts far "
                          "from anchored_to_star_mag; per-star depth for load-bearing cases from "
                          "the skill literature layer, not a rescaling law"},
    "confidence": "extrapolation",
}

# Main-sequence (mass, radius) in solar units, keyed by leading spectral class — used to derive
# star mass/radius when the caller gives only a spectral type. Illustrative anchors.
_MS_MASS_RADIUS = {
    "O": (16.0, 6.6), "B": (2.9, 1.8), "A": (1.6, 1.4), "F": (1.15, 1.15),
    "G": (0.95, 0.95), "K": (0.7, 0.72), "M": (0.3, 0.35),
}
