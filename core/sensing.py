"""Phase AP (Group S) — sensing / detection receiver-side calculators (Packet 30).

Three pure-math, self-validating (Phase-H/P contract) ``query.py``-only calculators for the sibling
``scifiWorldBuilding-Claude`` repo — the receiver-side "no-stealth-in-space" spine that turns a
*source* term (a drive's radiated power, a plume's γ power, a radiator's thermal luminosity) into a
**detection range / SNR**:

  * ``compute_angular_resolution``      (S2) — Rayleigh/Dawes/Sparrow diffraction limit. The shared
    resolution kernel; ``calculators.compute_direct_imaging`` calls ``_rayleigh_theta`` for its IWA.
  * ``compute_point_source_detection``  (S1) — unresolved point-source irradiance / photon-rate / SNR
    or max-detection-range. Composes S2 for the PSF solid angle.
  * ``compute_radar_range``             (S3) — active radar range equation (the R⁻⁴ counterpart to
    S1's R⁻²).

Known-science only: inverse-square radiometry, Stefan–Boltzmann, the Rayleigh criterion, the radar
range equation. No network/DB/RNG/wall-clock/numpy. This module imports ONLY ``core.equations``
constants, so ``core.calculators`` can import it (for the direct-imaging refactor) without a cycle.
All first-principles constants are caller-overridable; bundled background/band presets are
"transcribed, not fitted" with a source note and an override flag.
"""

import math

from core.equations import _C_MS, _K_B, _STEFAN_BOLTZMANN, _PLANCK_H

_ARCSEC_PER_RAD = 206_264.806          # arcsec per radian (local copy; see module docstring)
_HC = _PLANCK_H * _C_MS                 # J·m — photon energy = hc/λ

# ── S2 shared kernel — diffraction resolution ────────────────────────────────

# θ_res = k·λ/D. Rayleigh k=1.22 (first Airy null); Dawes 1.02 (empirical split of equal doubles);
# Sparrow 0.94 (peak-merge). Transcribed textbook coefficients; overridable via --coefficient.
_CRITERION_COEFF = {"rayleigh": 1.22, "dawes": 1.02, "sparrow": 0.94}


def _rayleigh_theta(wavelength_m, aperture_m, coefficient=1.22):
    """Angular resolution θ = coefficient·λ/D, radians. The one place the diffraction coefficient
    lives — shared by S1 (PSF solid angle), S2, and calculators.compute_direct_imaging (which passes
    coefficient=1.0, the 1·λ/D IWA convention)."""
    return coefficient * wavelength_m / aperture_m


def compute_angular_resolution(aperture_m=None, wavelength_m=None, frequency_hz=None,
                               range_m=None, separation_m=None, object_size_m=None,
                               criterion="rayleigh", coefficient=None):
    """Diffraction-limited angular resolution + optional linear/resolvable verdicts.

    ``θ = k·λ/D`` (k = 1.22 Rayleigh / 1.02 Dawes / 0.94 Sparrow, or --coefficient). With --range-m,
    the linear resolution ``x = θ·R``; with --separation-m, whether two objects at range R are
    resolvable (``s/R ≥ θ``); with --object-size-m, whether one object is resolved vs a point
    (``d/R ≥ θ``).
    """
    if aperture_m is None or aperture_m <= 0:
        return {"error": "aperture_m must be > 0."}
    if (wavelength_m is None) == (frequency_hz is None):
        return {"error": "Provide exactly one of wavelength_m or frequency_hz."}
    if wavelength_m is not None:
        if wavelength_m <= 0:
            return {"error": "wavelength_m must be > 0."}
        lam = float(wavelength_m)
    else:
        if frequency_hz <= 0:
            return {"error": "frequency_hz must be > 0."}
        lam = _C_MS / frequency_hz
    if coefficient is not None:
        if coefficient <= 0:
            return {"error": "coefficient must be > 0."}
        k = float(coefficient)
        crit = "custom"
    else:
        if criterion not in _CRITERION_COEFF:
            return {"error": f"Unknown criterion '{criterion}'. Choose from: "
                             f"{', '.join(sorted(_CRITERION_COEFF))} (or pass --coefficient)."}
        k = _CRITERION_COEFF[criterion]
        crit = criterion
    if range_m is not None and range_m <= 0:
        return {"error": "range_m must be > 0."}
    if separation_m is not None and separation_m <= 0:
        return {"error": "separation_m must be > 0."}
    if object_size_m is not None and object_size_m <= 0:
        return {"error": "object_size_m must be > 0."}

    theta = _rayleigh_theta(lam, aperture_m, k)
    linear = theta * range_m if range_m is not None else None
    resolvable = None
    if separation_m is not None and range_m is not None:
        resolvable = (separation_m / range_m) >= theta
    resolved_or_point = None
    if object_size_m is not None and range_m is not None:
        resolved_or_point = "resolved" if (object_size_m / range_m) >= theta else "point"

    return {
        "angular_resolution_rad": theta,
        "angular_resolution_arcsec": theta * _ARCSEC_PER_RAD,
        "linear_resolution_m": linear,
        "resolvable": resolvable,
        "resolved_or_point": resolved_or_point,
        "criterion": crit,
        "coefficient": k,
        "wavelength_m": lam,
        "aperture_m": aperture_m,
        "range_m": range_m,
        "model_note": ("θ = k·λ/D (k = 1.22 Rayleigh / 1.02 Dawes / 0.94 Sparrow). arcsec = θ·"
                       "206265; linear x_res = θ·R; resolvable = s/R ≥ θ; resolved = d/R ≥ θ. "
                       "Diffraction floor of a filled circular aperture — real optics only degrade "
                       "it. Shared kernel for point-source-detection (PSF) and direct-imaging (IWA)."),
    }


# ── S1 — point-source detection (the "no-stealth-in-space" core) ──────────────

# Band presets → (center_m, min_m, max_m). Representative, transcribed; override with --wavelength-m
# or --band-min-m/--band-max-m. gamma/radio span decades — the center is a nominal anchor. [pin @ open]
_BAND_PRESETS = {
    "thermal-ir": (10e-6, 8e-6, 14e-6),      # LWIR, the thermal-signature band
    "optical":    (0.55e-6, 0.4e-6, 0.7e-6),  # visible
    "gamma":      (1.24e-12, 1.24e-13, 1.24e-11),  # ~0.1–10 MeV (λ = hc/E); 1 MeV center
    "radio":      (0.21, 1e-3, 1.0),          # 21 cm anchor; 1 mm–1 m nominal span
}

# CMB monopole temperature, K (Fixsen 2009). stellar/zodiacal are order-of-magnitude, overridable.
_T_CMB = 2.725
# Zodiacal: representative ecliptic thermal spectral radiance ~ few×10⁻³ W·m⁻²·sr⁻¹·m⁻¹ near 25 µm
# (≈1 MJy/sr order). ORDER-OF-MAGNITUDE, ecliptic-latitude-dependent — a polar look-direction dodges
# most of it. [pin @ open] — override with --background-intensity-w-m2-sr-m. Fixed across band here.
_ZODIACAL_SPECTRAL_RADIANCE = 5e-3


def _planck_spectral_radiance(wavelength_m, temp_k):
    """Planck blackbody spectral radiance B_λ, W·m⁻²·sr⁻¹·m⁻¹."""
    x = _HC / (wavelength_m * _K_B * temp_k)
    if x > 700.0:                       # guard exp overflow deep in the Wien tail
        return 0.0
    return (2.0 * _PLANCK_H * _C_MS ** 2 / wavelength_m ** 5) / (math.expm1(x))


def _resolve_band(band, wavelength_m, band_min_m, band_max_m):
    """→ (center_lambda_m, band_width_m|None, band_label) or ('error', msg, None)."""
    have = [wavelength_m is not None, (band_min_m is not None or band_max_m is not None),
            band is not None]
    if sum(have) > 1:
        return ("error", "Provide at most one of --wavelength-m, --band-min-m/--band-max-m, or "
                         "--band.", None)
    if wavelength_m is not None:
        if wavelength_m <= 0:
            return ("error", "wavelength_m must be > 0.", None)
        return (float(wavelength_m), None, "monochromatic")
    if band_min_m is not None or band_max_m is not None:
        if band_min_m is None or band_max_m is None:
            return ("error", "Provide both --band-min-m and --band-max-m.", None)
        if not (0 < band_min_m < band_max_m):
            return ("error", "Require 0 < band_min_m < band_max_m.", None)
        return (0.5 * (band_min_m + band_max_m), band_max_m - band_min_m, "custom-band")
    if band is not None:
        if band not in _BAND_PRESETS:
            return ("error", f"Unknown band '{band}'. Choose from: "
                             f"{', '.join(sorted(_BAND_PRESETS))}.", None)
        c, lo, hi = _BAND_PRESETS[band]
        return (c, hi - lo, band)
    return (None, None, None)           # no band → photon-rate/background unavailable


def compute_point_source_detection(
        source_power_w=None, source_temp_k=None, source_area_m2=None, emissivity=1.0,
        rx_aperture_m=None, optical_efficiency=0.8, range_m=None,
        integration_s=1.0, quantum_efficiency=0.8,
        band=None, wavelength_m=None, band_min_m=None, band_max_m=None, source_size_m=None,
        nep_w_rthz=None, background=None, background_intensity_w_m2_sr_m=None,
        background_temp_k=5772.0, background_dilution=1.0,
        flux_floor_w_m2=None, snr_threshold=5.0):
    """Detect an unresolved point source of radiant power L at range R with aperture D.

    Source: --source-power-w L, OR --source-temp-k + --source-area-m2 (L = ε·σ·A·T⁴). With --range-m
    it reports irradiance E = L/(4πR²), received power P_rx = E·A_rx·η_opt, photon rate n = P_rx·λ/hc,
    and (if a floor is given) SNR. Without --range-m it solves for the max detection range.

    Detection floors (at most one): --flux-floor-w-m2 (an IRRADIANCE floor → aperture-INDEPENDENT
    range solve R_max = √(L/(4π·floor)); WB ruling MSG 016); --nep-w-rthz (detector-limited SNR); or
    --background {cmb,zodiacal,stellar,none} / --background-intensity-w-m2-sr-m (background/shot-limited
    SNR, which needs a band). --snr-threshold (default 5) sets the SNR-mode range solve.
    """
    # ── source luminosity ────────────────────────────────────────────────────
    from_temp = source_temp_k is not None or source_area_m2 is not None
    if (source_power_w is not None) == from_temp:
        return {"error": "Provide exactly one source: --source-power-w, OR "
                         "--source-temp-k with --source-area-m2."}
    if source_power_w is not None:
        if source_power_w <= 0:
            return {"error": "source_power_w must be > 0."}
        luminosity = float(source_power_w)
    else:
        if source_temp_k is None or source_area_m2 is None:
            return {"error": "Temperature source needs both --source-temp-k and --source-area-m2."}
        if source_temp_k <= 0 or source_area_m2 <= 0:
            return {"error": "source_temp_k and source_area_m2 must be > 0."}
        if not (0.0 < emissivity <= 1.0):
            return {"error": "emissivity must be in (0, 1]."}
        luminosity = emissivity * _STEFAN_BOLTZMANN * source_area_m2 * source_temp_k ** 4

    # ── receiver geometry ──────────────────────────────────────────────────────
    if rx_aperture_m is None or rx_aperture_m <= 0:
        return {"error": "rx_aperture_m must be > 0."}
    if not (0.0 < optical_efficiency <= 1.0):
        return {"error": "optical_efficiency must be in (0, 1]."}
    if not (0.0 < quantum_efficiency <= 1.0):
        return {"error": "quantum_efficiency must be in (0, 1]."}
    if integration_s <= 0:
        return {"error": "integration_s must be > 0."}
    if range_m is not None and range_m <= 0:
        return {"error": "range_m must be > 0."}
    if source_size_m is not None and source_size_m <= 0:
        return {"error": "source_size_m must be > 0."}
    if snr_threshold <= 0:
        return {"error": "snr_threshold must be > 0."}
    a_rx = math.pi * (rx_aperture_m / 2.0) ** 2

    lam, band_width, band_label = _resolve_band(band, wavelength_m, band_min_m, band_max_m)
    if lam == "error":
        return {"error": band_width}

    # ── detection floor selection (at most one) ────────────────────────────────
    use_bg = background is not None or background_intensity_w_m2_sr_m is not None
    n_floors = sum([nep_w_rthz is not None, use_bg, flux_floor_w_m2 is not None])
    if n_floors > 1:
        return {"error": "Provide at most one detection floor: --nep-w-rthz, --background/"
                         "--background-intensity-w-m2-sr-m, or --flux-floor-w-m2."}
    if nep_w_rthz is not None and nep_w_rthz <= 0:
        return {"error": "nep_w_rthz must be > 0."}
    if flux_floor_w_m2 is not None and flux_floor_w_m2 <= 0:
        return {"error": "flux_floor_w_m2 must be > 0."}
    if background_intensity_w_m2_sr_m is not None and background_intensity_w_m2_sr_m < 0:
        return {"error": "background_intensity_w_m2_sr_m must be ≥ 0."}
    if background is not None and background not in ("cmb", "zodiacal", "stellar", "none"):
        return {"error": "background must be one of: cmb, zodiacal, stellar, none."}
    if range_m is None and n_floors == 0:
        return {"error": "Solve-for-range mode needs a detection floor: --flux-floor-w-m2, "
                         "--nep-w-rthz, or --background/--background-intensity-w-m2-sr-m."}

    detection_regime = ("flux-floor" if flux_floor_w_m2 is not None
                        else "detector-limited" if nep_w_rthz is not None
                        else "background-limited" if use_bg else None)

    # Background modes need a band (Δλ) — WB MSG 016 confirmed.
    background_used = None
    i_bg = None
    if use_bg:
        if band_width is None:
            return {"error": "Background/shot-limited detection needs a band width: pass --band or "
                             "--band-min-m/--band-max-m (a bare --wavelength-m has no Δλ)."}
        if background_intensity_w_m2_sr_m is not None:
            i_bg = float(background_intensity_w_m2_sr_m)
            background_used = "caller-intensity"
        elif background == "cmb":
            i_bg = _planck_spectral_radiance(lam, _T_CMB)
            background_used = "cmb (2.725 K)"
        elif background == "stellar":
            if background_temp_k <= 0:
                return {"error": "background_temp_k must be > 0."}
            if not (0.0 < background_dilution <= 1.0):
                return {"error": "background_dilution must be in (0, 1]."}
            i_bg = background_dilution * _planck_spectral_radiance(lam, background_temp_k)
            background_used = (f"stellar ({background_temp_k:g} K × dilution {background_dilution:g}; "
                              "undiluted = star-fills-sky upper bound)")
        elif background == "zodiacal":
            i_bg = _ZODIACAL_SPECTRAL_RADIANCE
            background_used = "zodiacal (order-of-magnitude, ecliptic-latitude-dependent; [pin @ open])"
        else:  # background == "none"
            i_bg = 0.0
            background_used = "none"

    # ── point-vs-resolved + PSF solid angle (needs a wavelength) ────────────────
    theta_res = _rayleigh_theta(lam, rx_aperture_m, 1.22) if lam is not None else None
    omega_psf = math.pi * (theta_res / 2.0) ** 2 if theta_res is not None else None
    angular_size_rad = None
    resolved_or_point = "point"
    resolved_caveat = ""
    if source_size_m is not None and range_m is not None:
        angular_size_rad = source_size_m / range_m
        if theta_res is not None and angular_size_rad >= theta_res:
            resolved_or_point = "resolved"
            resolved_caveat = (
                " Source is RESOLVED (θ_s ≥ θ_res): the point-source irradiance/SNR figures are a "
                "LOWER BOUND — a resolved source's flux spreads across multiple resolution elements, "
                "so the per-PSF signal (and thus the background-limited SNR) is lower than reported.")

    # ── range-independent coefficients (P_rx = C_p/R², etc.) ───────────────────
    c_p = luminosity * a_rx * optical_efficiency / (4.0 * math.pi)
    c_n = c_p * lam / _HC if lam is not None else None          # photon-rate coeff
    # background photon count (R-independent — the sky fills the PSF regardless of source range)
    b_photons = None
    if use_bg and lam is not None:
        b_photons = (quantum_efficiency * i_bg * a_rx * omega_psf * band_width
                     * integration_s * lam / _HC)

    # ── at-range report ────────────────────────────────────────────────────────
    irradiance = received_power = photon_rate = snr = None
    if range_m is not None:
        irradiance = luminosity / (4.0 * math.pi * range_m ** 2)
        received_power = irradiance * a_rx * optical_efficiency
        if lam is not None:
            photon_rate = received_power * lam / _HC
        if detection_regime == "detector-limited":
            delta_f = 1.0 / (2.0 * integration_s)
            snr = received_power / (nep_w_rthz * math.sqrt(delta_f))
        elif detection_regime == "background-limited" and lam is not None:
            sig = quantum_efficiency * photon_rate * integration_s
            snr = sig / math.sqrt(sig + b_photons) if (sig + b_photons) > 0 else None

    # ── max-detection-range solve ──────────────────────────────────────────────
    max_range = None
    if flux_floor_w_m2 is not None:
        # WB MSG 016 ruling (A): flux floor is an IRRADIANCE → aperture-independent.
        max_range = math.sqrt(luminosity / (4.0 * math.pi * flux_floor_w_m2))
    elif range_m is None and detection_regime == "detector-limited":
        # SNR ∝ 1/R² ⇒ analytic. R_max = √(C_p/(T·NEP·√Δf)).
        delta_f = 1.0 / (2.0 * integration_s)
        max_range = math.sqrt(c_p / (snr_threshold * nep_w_rthz * math.sqrt(delta_f)))
    elif range_m is None and detection_regime == "background-limited" and lam is not None:
        # S=C_s/R², B const ⇒ s solves s²−T²s−T²B=0; R_max=√(C_s/s).
        c_s = quantum_efficiency * c_n * integration_s
        t2 = snr_threshold ** 2
        s = 0.5 * (t2 + math.sqrt(t2 ** 2 + 4.0 * t2 * b_photons))
        max_range = math.sqrt(c_s / s) if s > 0 else None

    return {
        "source_luminosity_w": luminosity,
        "irradiance_w_m2": irradiance,
        "received_power_w": received_power,
        "photon_rate_hz": photon_rate,
        "angular_size_rad": angular_size_rad,
        "resolved_or_point": resolved_or_point,
        "snr": snr,
        "max_detection_range_m": max_range,
        "detection_regime": detection_regime,
        "background_used": background_used,
        "wavelength_m": lam,
        "band": band_label,
        "rx_aperture_m": rx_aperture_m,
        "range_m": range_m,
        "model_note": (
            "Classical EM/thermal detection envelope (present-physics): E = L/(4πR²), "
            "P_rx = E·A_rx·η_opt, n = P_rx·λ/hc. Flux-floor solve (WB MSG 016 ruling A): "
            "--flux-floor-w-m2 is an IRRADIANCE floor → R_max = √(L/(4π·floor)), "
            "APERTURE-INDEPENDENT — --rx-aperture-m/--optical-efficiency/--quantum-efficiency are "
            "inert for this solve (they still drive received_power/photon_rate/snr at a given range, "
            "and the SNR-path solve); for an aperture-dependent range use the --nep or --background "
            "SNR path. Does NOT model exotic gravimetric/GW drive-wake sensing (Rung-3, "
            "packet-judgment; Pkt 25 found conventional drive γ undetectable at interstellar range "
            "and the GW wake ~30 orders below present strain floors). Background presets are "
            "order-of-magnitude and look-direction-dependent. Photon rate n is a band-centre "
            "(narrow-band) conversion of the bolometric P_rx — NOT an in-band Planck photon "
            "integral — consistent with the bolometric E/P_rx by construction; the approximation "
            "degrades as Δλ/λ grows (WB MSG 022 ruling A)." + resolved_caveat),
    }


# ── S3 — active radar range equation ─────────────────────────────────────────

def compute_radar_range(tx_power_w=None, tx_aperture_m=None, rx_aperture_m=None,
                        wavelength_m=None, frequency_hz=None, target_rcs_m2=None,
                        range_m=None, min_detectable_power_w=None,
                        integration_s=1.0, system_noise_temp_k=None,
                        tx_gain=None, rx_gain=None, snr_threshold=5.0):
    """Monostatic/bistatic radar range equation — the active, R⁻⁴ counterpart to S1.

    ``P_rx = P_tx·A_tx·A_rx·σ/(4π·λ²·R⁴)`` (equivalently via gains G = (πD/λ)²). With --range-m →
    received power (+ SNR if --system-noise-temp-k); with --min-detectable-power-w → max range
    ``R_max = [P_tx·A_tx·A_rx·σ/(4π·λ²·P_min)]^(1/4)``. The R⁻⁴ falloff is the doctrine payload:
    active sensing is inherently short-ranged, which is why passive thermal detection (S1) dominates.
    """
    if tx_power_w is None or tx_power_w <= 0:
        return {"error": "tx_power_w must be > 0."}
    if tx_aperture_m is None or tx_aperture_m <= 0:
        return {"error": "tx_aperture_m must be > 0."}
    if rx_aperture_m is None:
        rx_aperture_m = tx_aperture_m       # monostatic default
    if rx_aperture_m <= 0:
        return {"error": "rx_aperture_m must be > 0."}
    if (wavelength_m is None) == (frequency_hz is None):
        return {"error": "Provide exactly one of wavelength_m or frequency_hz."}
    if wavelength_m is not None:
        if wavelength_m <= 0:
            return {"error": "wavelength_m must be > 0."}
        lam = float(wavelength_m)
    else:
        if frequency_hz <= 0:
            return {"error": "frequency_hz must be > 0."}
        lam = _C_MS / frequency_hz
    if target_rcs_m2 is None or target_rcs_m2 <= 0:
        return {"error": "target_rcs_m2 must be > 0."}
    if (range_m is None) == (min_detectable_power_w is None):
        return {"error": "Provide exactly one of --range-m or --min-detectable-power-w."}
    if range_m is not None and range_m <= 0:
        return {"error": "range_m must be > 0."}
    if min_detectable_power_w is not None and min_detectable_power_w <= 0:
        return {"error": "min_detectable_power_w must be > 0."}
    if integration_s <= 0:
        return {"error": "integration_s must be > 0."}
    if system_noise_temp_k is not None and system_noise_temp_k <= 0:
        return {"error": "system_noise_temp_k must be > 0."}
    if tx_gain is not None and tx_gain <= 0:
        return {"error": "tx_gain must be > 0."}
    if rx_gain is not None and rx_gain <= 0:
        return {"error": "rx_gain must be > 0."}
    if snr_threshold <= 0:
        return {"error": "snr_threshold must be > 0."}

    a_tx = math.pi * (tx_aperture_m / 2.0) ** 2
    a_rx = math.pi * (rx_aperture_m / 2.0) ** 2
    g_tx = tx_gain if tx_gain is not None else (math.pi * tx_aperture_m / lam) ** 2
    g_rx = rx_gain if rx_gain is not None else (math.pi * rx_aperture_m / lam) ** 2

    # Aperture form (independent of the gain overrides, which the spec anchors use):
    # P_rx = P_tx·A_tx·A_rx·σ / (4π·λ²·R⁴).
    coeff = tx_power_w * a_tx * a_rx * target_rcs_m2 / (4.0 * math.pi * lam ** 2)

    received_power = max_range = snr = None
    if range_m is not None:
        received_power = coeff / range_m ** 4
        if system_noise_temp_k is not None:
            delta_f = 1.0 / (2.0 * integration_s)
            noise_power = _K_B * system_noise_temp_k * delta_f
            snr = received_power / noise_power if noise_power > 0 else None
    else:
        max_range = (coeff / min_detectable_power_w) ** 0.25

    return {
        "received_power_w": received_power,
        "max_range_m": max_range,
        "snr": snr,
        "tx_gain": g_tx,
        "rx_gain": g_rx,
        "wavelength_m": lam,
        "range_m": range_m,
        "model_note": ("Radar range equation P_rx = P_tx·A_tx·A_rx·σ/(4π·λ²·R⁴) (aperture form; "
                       "gains G = (πD/λ)² reported for reference, overridable). R_max = "
                       "[P_tx·A_tx·A_rx·σ/(4π·λ²·P_min)]^(1/4). SNR (if --system-noise-temp-k) vs the "
                       "thermal floor P_n = k_B·T_sys·Δf, Δf ≈ 1/(2t). The R⁻⁴ two-way falloff makes "
                       "active sensing inherently short-ranged — why passive thermal detection "
                       "(point-source-detection) dominates at range in space."),
    }
