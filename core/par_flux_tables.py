"""Phase AD (C1) — bundled real-SED PAR-fraction table for ``core.par_flux``.

Isolated static data (like ``core.shielding_tables`` / ``core.propulsion_tables``): the
fraction of a star's **bolometric** flux that falls in the photosynthetically active band
(400–700 nm), computed from **real model-atmosphere spectra** rather than a blackbody. It is
the ``--sed real`` path's lookup table; the blackbody path needs no table.

**Provenance (computed at build, 2026-07-03).** ``f_PAR = ∫_{400}^{700 nm} F_λ dλ /
∫_0^∞ F_λ dλ``, trapezoidal integration over the full model wavelength range, from the
**BT-Settl (CIFIST2011)** synthetic-spectrum grid (Allard, Homeier & Freytag 2012, RSPTA 370,
2765; Baraffe et al. 2015, A&A 577, A42) at **log g = 4.5, [M/H] = 0**, retrieved as ASCII
spectra from the **SVO Theoretical Spectra** service (``svo2.cab.inta-csic.es``; Bayo et al.
2008). The real grid captures the M-dwarf **TiO / VO / H₂O line blanketing** that suppresses
the visible band — an effect a blackbody misses — so a real red dwarf's f_PAR is far **below**
its blackbody value (e.g. 3000 K real ≈ 0.023 vs blackbody ≈ 0.081), while a Sun-like star's
real f_PAR (≈ 0.39 at 5800 K) sits slightly **above** blackbody (≈ 0.37) and matches the
measured ASTM-E490 solar ~0.39 in-band fraction.

The table is **band-fixed at 400–700 nm** (that is the band it was integrated over); a
``par-flux --sed real`` request with a non-default ``--par-band-nm`` is rejected (use
``--sed blackbody`` for a custom band). Grid coverage 2600–7000 K; outside that, ``--sed real``
errors (use blackbody). Interpolation is linear in Teff.
"""

# Teff (K) -> f_PAR (400–700 nm energy / bolometric), BT-Settl CIFIST2011, log g 4.5, [M/H] 0.
_REAL_SED_FPAR = {
    2600: 0.0044,
    2800: 0.0113,
    3000: 0.0228,
    3300: 0.0541,
    3600: 0.0940,
    4000: 0.1585,
    4400: 0.2287,
    4800: 0.2930,
    5200: 0.3415,
    5800: 0.3910,
    6200: 0.4132,
    6800: 0.4371,
    7000: 0.4436,
}

_REAL_TEFF_MIN = min(_REAL_SED_FPAR)
_REAL_TEFF_MAX = max(_REAL_SED_FPAR)
_REAL_BAND_NM = (400.0, 700.0)   # the fixed band the table was integrated over

_SOURCE = (
    "Real-SED f_PAR from the BT-Settl (CIFIST2011) grid (Allard+ 2012; Baraffe+ 2015) at "
    "log g 4.5, [M/H] 0, via the SVO Theoretical Spectra service; f_PAR = ∫400–700nm F_λ / "
    "∫F_λ (trapezoidal, full range), computed at build 2026-07-03. Captures M-dwarf TiO/VO/H₂O "
    "line blanketing (real red-dwarf f_PAR ≪ blackbody); band-fixed at 400–700 nm, grid "
    "2600–7000 K, linear-in-Teff interpolation."
)


def real_f_par(teff_k):
    """Linear-interpolated real-SED f_PAR at ``teff_k``, or ``None`` if outside the grid."""
    if teff_k < _REAL_TEFF_MIN or teff_k > _REAL_TEFF_MAX:
        return None
    if teff_k in _REAL_SED_FPAR:
        return _REAL_SED_FPAR[teff_k]
    teffs = sorted(_REAL_SED_FPAR)
    for i in range(len(teffs) - 1):
        t0, t1 = teffs[i], teffs[i + 1]
        if t0 <= teff_k <= t1:
            f0, f1 = _REAL_SED_FPAR[t0], _REAL_SED_FPAR[t1]
            return f0 + (f1 - f0) * (teff_k - t0) / (t1 - t0)
    return None   # unreachable (bounds checked above)
