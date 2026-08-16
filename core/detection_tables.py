"""core/detection_tables.py — CR-6 Interface-B (3a) survey-completeness defaults.

Integrated from the WB **3a FINAL** survey-completeness reference (`3a-v1.1.0-2026-08-15`,
coordination-channel MSG 048/050), delivered as the authoritative Interface B JSON
(`scifiWorldBuilding-Claude/design-lab/star-system-analysis/deliverables/survey-completeness-reference.json`).
Consumed by ``core.detection.compute_detection_completeness`` as the fallback survey capability
when a per-star override is not supplied. Confidence ceiling **``extrapolation``** — a *typical*
floor by magnitude/era, NOT a per-star truth; a per-star override always supersedes.

``by_mag`` is keyed **internally** by ``mag_max`` (inclusive-below numeric edge; last bin open) in
each method's working band — this mirrors the WB JSON's ``mag_bin`` strings {≤6, 6–8, 8–10, 10–12,
12–15, >15} exactly (``"<=6"``→6.0 … ``">15"``→inf), so ``core.detection._bin_row`` reproduces the
pinned bins. Bands per method: RV ≈ V, transit = TESS **Tmag**, astrometry = Gaia **G**, imaging =
host **H** mag.

WB rulings folded in (MSG 050):
  * **RV effective floor = max(precision_m_s, jitter)**, where ``jitter`` is
    ``jitter_floor_by_sptype_m_s[letter]`` when the host spectral letter is known (Kraft-break bump:
    O/B/A=5, F=3, G/K/M=1.5), else the flat per-bin ``jitter_floor_m_s`` (1.5). Prevents a
    bright-bin *photon* 0.3 m/s reading 3–6× too optimistic, and stops CR-6 declaring a Neptune
    detectable around an RV-hostile A star in the fallback.
  * **Transit default = TESS-only** (all-sky ongoing survey a generic star actually has; Kepler's
    deeper fixed-field floor is a per-star ``--transit-precision-ppm`` override, not an off-field
    default — domain-of-validity call).
  * **Noise-model formulas preferred at the faint tail** — TESS Kunimoto 2022 σ₁ₕᵣ(Tmag) for the
    transit >12-mag bins and the ESA Gaia analytic σϖ(G) for the astrometry >15-mag bin, instead of
    the binned scalar (the scalars are knowingly optimistic there: astrometry ~4× near G20, TESS
    steeply convex). ``noise_model.prefer_above_mag`` is the switchover.
  * **Imaging is an H-band SELF-LUMINOUS floor** (young hot giants by own emission) — NOT
    reflected-optical. ``mechanism_caveat`` is surfaced on the imaging output; the mismatch with
    CR-6's reflected-contrast inversion is *flagged, not reconciled* (WB DV-7).
"""

# Bin edges are the per-row ``mag_max`` (inclusive-below; the last bin is open, >15) — the single
# source of truth ``core.detection._bin_row`` reads. They mirror the WB JSON ``mag_bin`` strings
# {≤6, 6–8, 8–10, 10–12, 12–15, >15}.
_DETECTION_DEFAULTS = {
    "reference_version": "3a-v1.1.0-2026-08-15",
    "methods": {
        "rv": {  # radial velocity — band ≈ V. Effective floor = max(precision, jitter).
            # jitter superseded by jitter_floor_by_sptype_m_s[letter] when the host letter is known.
            "jitter_floor_by_sptype_m_s": {"O": 5.0, "B": 5.0, "A": 5.0, "F": 3.0,
                                           "G": 1.5, "K": 1.5, "M": 1.5},
            "by_mag": [
                {"mag_max": 6.0,  "precision_m_s": 0.3,  "jitter_floor_m_s": 1.5, "baseline_yr": 15.0},
                {"mag_max": 8.0,  "precision_m_s": 0.5,  "jitter_floor_m_s": 1.5, "baseline_yr": 15.0},
                {"mag_max": 10.0, "precision_m_s": 1.0,  "jitter_floor_m_s": 1.5, "baseline_yr": 12.0},
                {"mag_max": 12.0, "precision_m_s": 2.0,  "jitter_floor_m_s": 1.5, "baseline_yr": 8.0},
                {"mag_max": 15.0, "precision_m_s": 6.0,  "jitter_floor_m_s": 1.5, "baseline_yr": 4.0},
                {"mag_max": float("inf"), "precision_m_s": 20.0, "jitter_floor_m_s": 1.5, "baseline_yr": 2.0},
            ],
        },
        "transit": {  # photometric floor (ppm). Default = TESS σ₁ₕᵣ (50th-pct CDPP), all-sky.
            "coverage_days": 27.0,   # TESS single-sector (CVZ up to 351 d; per-star override territory)
            "by_mag": [
                {"mag_max": 6.0,  "phot_precision_ppm": 68.0},
                {"mag_max": 8.0,  "phot_precision_ppm": 81.0},
                {"mag_max": 10.0, "phot_precision_ppm": 149.0},
                {"mag_max": 12.0, "phot_precision_ppm": 440.0},
                {"mag_max": 15.0, "phot_precision_ppm": 2900.0},
                {"mag_max": float("inf"), "phot_precision_ppm": 10300.0},
            ],
            # WB-preferred at the faint tail (app_mag > prefer_above_mag): σ₁ₕᵣ(Tmag) refines the
            # steeply-convex scalar. Kunimoto 2022 (arXiv:2202.03656), 50th-pct; reproduces T=10→240.5 ppm.
            "noise_model": {"kind": "tess_kunimoto_2022_50pct",
                            "a": 50.2, "b": 97.4, "c": 92.9, "prefer_above_mag": 12.0,
                            "formula": "sigma_1hr_ppm = a + b*10^(0.2*(T-10)) + c*10^(0.4*(T-10))",
                            "source": "Kunimoto 2022 (arXiv:2202.03656)"},
        },
        "astrometry": {  # Gaia-class per-source astrometric precision (µas), band = Gaia G.
            "baseline_yr": 10.0,  # representative decade window (per-star --astrom-baseline-yr overrides)
            "by_mag": [
                {"mag_max": 6.0,  "astrom_precision_uas": 10.0},
                {"mag_max": 8.0,  "astrom_precision_uas": 10.0},
                {"mag_max": 10.0, "astrom_precision_uas": 10.0},
                {"mag_max": 12.0, "astrom_precision_uas": 10.0},
                {"mag_max": 15.0, "astrom_precision_uas": 20.0},
                {"mag_max": float("inf"), "astrom_precision_uas": 200.0},
            ],
            # WB-preferred for G>15 (the 200 µas scalar over-states detection ~4× near G20): the ESA
            # analytic σϖ(G), valid 3 ≤ G < 20.7. DR4 Tfactor 0.749; g_floor is the bright z-plateau.
            "noise_model": {"kind": "gaia_dr4_analytic", "tfactor": 0.749, "g_floor": 13.0,
                            "prefer_above_mag": 15.0,
                            "formula": "sigma_pi_uas = tfactor*sqrt(40 + 800*z + 30*z^2), "
                                       "z = max(10^(0.4*(g_floor-15)), 10^(0.4*(G-15)))",
                            "source": "ESA Gaia Science-Performance (DR4, re-verified 2026-08-15)"},
        },
        "imaging": {  # H-band (~1.6 µm) SELF-LUMINOUS ground extreme-AO contrast curve (SPHERE/GPI-class).
            "anchored_to_star_mag": 6.0,
            "anchored_to_star_mag_band": "H",
            "contrast_band": "H",
            "mechanism_caveat": (
                "H-band near-IR SELF-LUMINOUS floor (detects young, hot, self-luminous giants by their "
                "own emission) — NOT reflected-optical. CR-6's imaging min_radius_earth inverts a "
                "REFLECTED-light contrast against this thermal floor: flag, do not read it as a literal "
                "reflected-light limit and do not compare cell-for-cell against direct-imaging's reflected "
                "contrast. Mature, cool, reflected-light planets (~1e-9…1e-12) are below all present "
                "floors — an HWO-class future target (WB DV-7)."),
            "contrast_curve": [
                {"sep_arcsec": 0.2, "delta_mag": 11.8},
                {"sep_arcsec": 0.4, "delta_mag": 12.8},
                {"sep_arcsec": 0.5, "delta_mag": 13.5},
                {"sep_arcsec": 0.8, "delta_mag": 13.8},
                {"sep_arcsec": 1.0, "delta_mag": 14.0},
                {"sep_arcsec": 3.0, "delta_mag": 15.8},
            ],
        },
    },
    "domain": {"mag_range": [3.0, 20.7],   # astrometry (Gaia G) validity window; other methods extend brighter
               "caveats": "Typical detection floor by magnitude/era, not per-star truth. RV effective floor = "
                          "max(precision, sp_type-keyed jitter); transit default = TESS all-sky (+ a geometric "
                          "R*/a ceiling and window function not modelled here); astrometry/TESS faint tails use "
                          "the analytic noise model, not the binned scalar; imaging is an H-band self-luminous "
                          "floor (see methods.imaging.mechanism_caveat). Per-star overrides supersede."},
    "confidence": "extrapolation",
}

# Main-sequence (mass, radius) in solar units, keyed by leading spectral class — used to derive
# star mass/radius when the caller gives only a spectral type. Illustrative anchors.
_MS_MASS_RADIUS = {
    "O": (16.0, 6.6), "B": (2.9, 1.8), "A": (1.6, 1.4), "F": (1.15, 1.15),
    "G": (0.95, 0.95), "K": (0.7, 0.72), "M": (0.3, 0.35),
}
