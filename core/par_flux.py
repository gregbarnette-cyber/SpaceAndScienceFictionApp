"""Phase AA — PAR / photosynthesis by stellar type (Group I of the combined
settlement / propulsion / astrobiology / terraforming request; Packet 18).

One pure-math, self-validating (Phase-H/P contract) ``query.py``-only calculator,
``compute_par_flux``. It answers the *natural-light* / native-photosynthesis
question: PAR (photosynthetically active radiation, ~400–700 nm) is a *fraction*
of a star's output that shifts by spectral type — G ≈ 0.37 (blackbody), but K/M
shift redward so far fewer usable PAR photons reach a leaf per W/m² of insolation
(the red-dwarf photosynthesis-deficit question). Its PPFD output **feeds back**
into the Phase-X ``bioregen-area`` tool, which takes PAR as a caller-supplied input.

**SED model — blackbody at Teff, flagged as an approximation.** Real stellar SEDs
(esp. M-dwarf line blanketing) deviate: a real M-dwarf's PAR fraction is *lower*
than its blackbody, so blackbody is *optimistic* about red-dwarf PAR (the true
deficit is larger). Real-spectrum (PHOENIX / BT-Settl) SEDs are a v2 refinement.

No DB write, no RNG, no time; **network only** on the ``--star`` Teff-resolution
path (SIMBAD, lazily imported so the module stays lightweight offline). The
physical constants live in ``core.equations`` (single source of truth); the
main-sequence Teff table is read through ``core.regions``.
"""

import math

from core.equations import (
    _PLANCK_H,
    _C_MS,
    _K_B,
    _AVOGADRO,
    _STEFAN_BOLTZMANN,
    _M_PER_AU,
    _SOLAR_LUMINOSITY_W,
)

# G2V (nominal solar) reference temperature for the PAR-deficit ratio (IAU 2015).
_T_SUN_PAR_REF = 5772.0

# Simpson-rule intervals for the in-band Planck integrations. The band integrand
# is smooth, so the fraction converges to <1e-6 by n≈100 (verified at build);
# 1000 leaves a wide margin and is still instant.
_N_SIMPSON = 1000

_SED_MODEL = "blackbody (approx — real SED deviates)"
_FEEDS_NOTE = "PPFD → bioregen-area PAR input (Phase X)"
_MODEL_NOTE = (
    "PAR fraction from a blackbody (Planck) SED at Teff, integrated 400–700 nm "
    "(default) over the Stefan–Boltzmann total. Blackbody is an approximation: "
    "real stellar SEDs deviate — M-dwarf line blanketing suppresses the "
    "visible/blue, so a real red dwarf's PAR fraction is LOWER than its "
    "blackbody value and the true photosynthesis deficit is LARGER than reported "
    "here (blackbody is optimistic for K/M stars). Blackbody f_PAR: Sun ~0.37, "
    "real solar ~0.40–0.45; a 3000 K blackbody gives ~0.08 where real late-M SEDs "
    "sit nearer 0.04–0.07. PPFD uses the band-mean photon energy "
    "(~0.219 J/µmol at ~550 nm). Real-spectrum (PHOENIX/BT-Settl) SEDs are a v2 "
    "refinement."
)


def _planck_lambda(lam_m: float, teff_k: float) -> float:
    """Spectral radiance B_λ(T) [W·m⁻³·sr⁻¹] at wavelength ``lam_m`` (metres)."""
    return (2.0 * _PLANCK_H * _C_MS * _C_MS / lam_m ** 5) / math.expm1(
        _PLANCK_H * _C_MS / (lam_m * _K_B * teff_k)
    )


def _simpson(f, a: float, b: float, n: int = _N_SIMPSON) -> float:
    """Composite Simpson's rule for ∫_a^b f (n forced even)."""
    if n % 2:
        n += 1
    h = (b - a) / n
    total = f(a) + f(b)
    for i in range(1, n):
        total += (4.0 if i % 2 else 2.0) * f(a + i * h)
    return total * h / 3.0


def _band_energy_and_photons(teff_k: float, lo_m: float, hi_m: float):
    """Return (band energy [W·m⁻²·sr⁻¹], band photon rate [s⁻¹·m⁻²·sr⁻¹]).

    Photon integrand = B_λ · λ/(hc): each photon carries hc/λ, so dividing the
    spectral energy by that gives the spectral photon rate.
    """
    band_energy = _simpson(lambda l: _planck_lambda(l, teff_k), lo_m, hi_m)
    band_photons = _simpson(
        lambda l: _planck_lambda(l, teff_k) * l / (_PLANCK_H * _C_MS), lo_m, hi_m
    )
    return band_energy, band_photons


def _f_par(teff_k: float, lo_m: float, hi_m: float) -> float:
    """PAR fraction = in-band energy / total (σT⁴/π closes the total)."""
    band_energy, _ = _band_energy_and_photons(teff_k, lo_m, hi_m)
    total = _STEFAN_BOLTZMANN * teff_k ** 4 / math.pi
    return band_energy / total


def _resolve_teff(teff_k, spectral_type, star):
    """Resolve exactly one Teff source → {"teff": float} or {"error": str}."""
    sources = [teff_k is not None, bool(spectral_type), bool(star)]
    if sum(sources) != 1:
        return {"error": "Provide exactly one Teff source: teff_k, spectral_type, or star."}

    if teff_k is not None:
        if teff_k <= 0:
            return {"error": "teff_k must be > 0."}
        return {"teff": float(teff_k)}

    if spectral_type:
        # Offline main-sequence table lookup via the shared ceiling rule.
        from core import regions
        row, _key = regions._lookup_spectral_type(spectral_type)
        if not row:
            return {"error": f"Could not resolve spectral type '{spectral_type}' "
                             f"to a main-sequence Teff."}
        try:
            teff = float(row["Teeff(K)"])
        except (KeyError, TypeError, ValueError):
            return {"error": f"Main-sequence row for '{spectral_type}' has no usable Teff."}
        if teff <= 0:
            return {"error": f"Main-sequence Teff for '{spectral_type}' is non-positive."}
        return {"teff": teff}

    # star → SIMBAD (the only networked path); lazy import keeps astroquery out
    # of the offline import graph.
    from core import databases, regions
    simbad = databases.compute_simbad_lookup(star)
    if "error" in simbad:
        return simbad
    reg = regions.compute_star_system_regions_from_simbad(simbad)
    if "error" in reg:
        return reg
    teff = reg.get("temp")
    if teff is None or teff <= 0:
        return {"error": f"Could not derive a temperature for '{star}'."}
    return {"teff": float(teff)}


def _resolve_insolation(insolation_wm2, luminosity_lsun, distance_au):
    """Resolve exactly one insolation source → {"S": float} or {"error": str}."""
    has_direct = insolation_wm2 is not None
    has_lumdist = luminosity_lsun is not None or distance_au is not None
    if has_direct == has_lumdist:
        return {"error": "Provide exactly one insolation source: insolation_wm2, "
                         "or luminosity_lsun + distance_au."}

    if has_direct:
        if insolation_wm2 <= 0:
            return {"error": "insolation_wm2 must be > 0."}
        return {"S": float(insolation_wm2)}

    if luminosity_lsun is None or distance_au is None:
        return {"error": "Provide both luminosity_lsun and distance_au."}
    if luminosity_lsun <= 0:
        return {"error": "luminosity_lsun must be > 0."}
    if distance_au <= 0:
        return {"error": "distance_au must be > 0."}
    d_m = distance_au * _M_PER_AU
    S = _SOLAR_LUMINOSITY_W * luminosity_lsun / (4.0 * math.pi * d_m * d_m)
    return {"S": S}


def compute_par_flux(teff_k=None, spectral_type=None, star=None,
                     insolation_wm2=None, luminosity_lsun=None, distance_au=None,
                     par_band_nm=(400.0, 700.0)):
    """PAR fraction, PAR irradiance, PPFD, and the red-star deficit vs G2.

    Teff — exactly one source: ``teff_k`` (offline) / ``spectral_type``
    (→ main-sequence table, offline) / ``star`` (→ SIMBAD, networked).
    Insolation — exactly one source: ``insolation_wm2`` / (``luminosity_lsun``
    + ``distance_au``). ``par_band_nm`` is the (lo, hi) PAR band in nm.

    Returns a dict (see docs/integration.md) or a curated ``{"error": str}``.
    """
    # ── band validation ──
    try:
        lo_nm, hi_nm = float(par_band_nm[0]), float(par_band_nm[1])
    except (TypeError, ValueError, IndexError):
        return {"error": "par_band_nm must be two numbers (lo_nm, hi_nm)."}
    if lo_nm <= 0 or hi_nm <= 0:
        return {"error": "PAR band wavelengths must be > 0 nm."}
    if lo_nm >= hi_nm:
        return {"error": "PAR band lower bound must be < upper bound."}

    # ── Teff ──
    tr = _resolve_teff(teff_k, spectral_type, star)
    if "error" in tr:
        return tr
    teff = tr["teff"]

    # ── insolation ──
    ir = _resolve_insolation(insolation_wm2, luminosity_lsun, distance_au)
    if "error" in ir:
        return ir
    S = ir["S"]

    lo_m, hi_m = lo_nm * 1e-9, hi_nm * 1e-9

    # ── PAR fraction + band-mean photon energy ──
    band_energy, band_photons = _band_energy_and_photons(teff, lo_m, hi_m)
    total = _STEFAN_BOLTZMANN * teff ** 4 / math.pi
    f_par = band_energy / total
    e_photon_mean = band_energy / band_photons          # J per photon (band mean)

    par_irradiance = S * f_par                           # W/m²
    # W/m² ÷ (J/photon) → photons/s/m² ÷ N_A → mol/s/m² ×1e6 → µmol/s/m²
    ppfd = par_irradiance / e_photon_mean / _AVOGADRO * 1e6

    # ── deficit vs G2 (same band, so an override is apples-to-apples) ──
    f_par_g2 = _f_par(_T_SUN_PAR_REF, lo_m, hi_m)
    par_deficit = f_par_g2 / f_par

    return {
        "teff_k": teff,
        "par_fraction": f_par,
        "insolation_wm2": S,
        "par_irradiance_wm2": par_irradiance,
        "ppfd_umol_m2_s": ppfd,
        "par_deficit_vs_g2": par_deficit,
        "photon_energy_mean_j": e_photon_mean,
        "j_per_umol": e_photon_mean * _AVOGADRO * 1e-6,
        "band_nm": [lo_nm, hi_nm],
        "sed_model": _SED_MODEL,
        "feeds_note": _FEEDS_NOTE,
        "model_note": _MODEL_NOTE,
    }
