"""Phase AD (C8) — active (magnetic) radiation-shield rigidity cutoff.

A ``query.py``-only, pure-math, self-validating (Phase-H/P contract) calculator for the
*floor physics* of active magnetic shielding: a magnetic dipole deflects charged particles
whose magnetic **rigidity** (momentum per charge, R = pc/q, in volts) falls below a
geometry-set **cutoff**. It complements the *passive* ``shielding-attenuation`` (mass
stops what the field lets through) with the field side of the same problem.

Physics (durable):
  * **Störmer equatorial cutoff.** For a magnetic dipole of moment ``m`` [A·m²] the
    equatorial rigidity cutoff at radius ``r`` is ``R_c = (μ₀·c/16π)·m/r²`` [V]. The
    constant ``μ₀·c/16π ≈ 7.50`` V·m/(A·m²) reproduces Earth's geomagnetic vertical
    equatorial cutoff (m ≈ 8×10²² A·m², r = R⊕ → ≈ 14.8 GV — the measured value), so this
    is anchored, not fitted.
  * **Deflected fraction** of a supplied incident spectrum: with a caller-supplied
    characteristic rigidity ``R_s`` the integral fraction below the cutoff is modelled as
    ``1 − exp(−R_c/R_s)`` — a monotone, ∈[0,1) *order-of-magnitude* parametric estimate
    (the real GCR spectrum's low-rigidity solar-modulation turnover is not resolved).
  * **Field at the shield radius**: equatorial dipole field ``B = μ₀·m/(4π r³)`` [T].

The dipole moment comes from exactly one field source — an explicit moment, a
superconducting coil pair (``m = I·π·R_coil²``), or a field×scale (``m = 4π·r₀³·B₀/μ₀``).
``μ₀``/``c`` are reused from ``core.equations``. No network, no DB, no RNG, no time.
"""

import math

from core.equations import _MU_0, _C_MS

# Störmer equatorial-cutoff constant μ₀·c/(16π) [V·m / (A·m²)] ≈ 7.4948; R_c[V] = k·m/r².
_STORMER_K = _MU_0 * _C_MS / (16.0 * math.pi)

_MODEL_NOTE = (
    "Active magnetic shielding. Störmer equatorial rigidity cutoff R_c = (μ₀·c/16π)·m/r² "
    "(the constant ≈ 7.495 V·m/A·m² reproduces Earth's ≈14.8 GV geomagnetic equatorial "
    "cutoff — anchored). Particles with rigidity below R_c are magnetically deflected; the "
    "deflected fraction of an incident spectrum uses the ORDER-OF-MAGNITUDE parametric model "
    "1 − exp(−R_c/R_s) for a caller-supplied characteristic rigidity R_s (the GCR spectrum's "
    "low-rigidity solar-modulation turnover is not resolved). Equatorial dipole field at the "
    "shield radius B = μ₀·m/(4π r³). The dipole idealisation ignores real coil geometry, the "
    "un-shielded polar cusps, and secondary production — a first-cut feasibility screen, not a "
    "transport simulation (hand off to a Monte-Carlo code for dose). Superconducting-magnet "
    "mass/quench engineering is out of scope."
)


def _resolve_moment(coil_current_a, coil_radius_m, magnetic_moment_am2,
                    field_tesla, field_radius_m):
    """Return (m_dip, source_tag) or a {"error"} dict. Exactly one field source."""
    have_coil = coil_current_a is not None or coil_radius_m is not None
    have_moment = magnetic_moment_am2 is not None
    have_field = field_tesla is not None or field_radius_m is not None
    if have_coil + have_moment + have_field != 1:
        return {"error": "Provide exactly one field source: --magnetic-moment-am2, "
                         "(--coil-current-a + --coil-radius-m), or (--field-tesla + --field-radius-m)."}
    if have_coil:
        if coil_current_a is None or coil_radius_m is None:
            return {"error": "Provide both --coil-current-a and --coil-radius-m for the coil source."}
        if coil_current_a <= 0 or coil_radius_m <= 0:
            return {"error": "coil_current_a and coil_radius_m must be > 0."}
        return (coil_current_a * math.pi * coil_radius_m ** 2, "coil")
    if have_moment:
        if magnetic_moment_am2 <= 0:
            return {"error": "magnetic_moment_am2 must be > 0."}
        return (float(magnetic_moment_am2), "moment")
    # field × scale → m = 4π·r₀³·B₀/μ₀
    if field_tesla is None or field_radius_m is None:
        return {"error": "Provide both --field-tesla and --field-radius-m for the field source."}
    if field_tesla <= 0 or field_radius_m <= 0:
        return {"error": "field_tesla and field_radius_m must be > 0."}
    m = 4.0 * math.pi * field_radius_m ** 3 * field_tesla / _MU_0
    return (m, "field")


def compute_active_shield(shield_radius_m=None, coil_current_a=None, coil_radius_m=None,
                          magnetic_moment_am2=None, field_tesla=None, field_radius_m=None,
                          spectrum_characteristic_rigidity_gv=None):
    """Rigidity cutoff + optional deflected fraction + field for an active magnetic shield.

    ``shield_radius_m`` — the protected-region radius r at which the cutoff is evaluated.
    Field source (exactly one): explicit moment, coil pair, or field×scale. Optional
    ``spectrum_characteristic_rigidity_gv`` R_s → the deflected fraction 1 − exp(−R_c/R_s).
    """
    if shield_radius_m is None or shield_radius_m <= 0:
        return {"error": "shield_radius_m must be > 0."}

    src = _resolve_moment(coil_current_a, coil_radius_m, magnetic_moment_am2,
                          field_tesla, field_radius_m)
    if isinstance(src, dict):
        return src
    m_dip, source_tag = src

    r_c_v = _STORMER_K * m_dip / shield_radius_m ** 2         # volts
    r_c_gv = r_c_v / 1e9
    b_field_t = _MU_0 * m_dip / (4.0 * math.pi * shield_radius_m ** 3)

    deflected_fraction = None
    if spectrum_characteristic_rigidity_gv is not None:
        if spectrum_characteristic_rigidity_gv <= 0:
            return {"error": "spectrum_characteristic_rigidity_gv must be > 0."}
        deflected_fraction = 1.0 - math.exp(-r_c_gv / spectrum_characteristic_rigidity_gv)

    return {
        "shield_radius_m": float(shield_radius_m),
        "magnetic_moment_am2": m_dip,
        "field_source": source_tag,
        "coil_current_a": coil_current_a if source_tag == "coil" else None,
        "coil_radius_m": coil_radius_m if source_tag == "coil" else None,
        "rigidity_cutoff_gv": r_c_gv,
        "rigidity_cutoff_v": r_c_v,
        "magnetic_field_t": b_field_t,
        "spectrum_characteristic_rigidity_gv": spectrum_characteristic_rigidity_gv,
        "deflected_fraction": deflected_fraction,
        "is_order_of_magnitude": True,
        "model_note": _MODEL_NOTE,
    }
