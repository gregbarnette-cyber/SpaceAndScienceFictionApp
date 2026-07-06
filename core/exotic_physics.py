"""Phase AG (Group M) — exotic vacuum & cosmology (Packet 21).

Four ``query.py``-only, pure-math, self-validating (Phase-H/P contract) calculators for
vacuum/negative energy, the vacuum catastrophe, the pair-production threshold, and the
cosmological-expansion-vs-local-binding accounting.

Physics (durable, closed-form on fundamental constants):
  * **M1 casimir** — parallel-plate pressure P = π²ℏc/(240 d⁴) (attractive), energy density
    u = −π²ℏc/(720 d³) (the NEC-relevant NEGATIVE energy feeding Group N); sphere-plate force
    (proximity-force approximation) F = −π³ℏcR/(360 d³).
  * **M2 vacuum-energy** — observed ρ_Λ = Ω_Λ·ρ_crit (ρ_crit = 3H₀²/8πG·c²), Λ = 3Ω_ΛH₀²/c²;
    the QED cutoff estimate ρ_vac ~ E_cutoff⁴/(ℏc)³ (Planck → ~10¹¹³ J/m³) and the ~10¹²² ratio.
  * **M3 schwinger-limit** — critical field E_c = m_e²c³/(eℏ), critical intensity I_c = ½ε₀cE_c².
  * **M4 hubble-flow** — recession v = H₀·d; the local-binding turnaround radius
    r_ta = (GM/(Ω_Λ H₀²))^(1/3) (where the Λ acceleration Ω_ΛH₀²r balances gravity GM/r²).

Constants from ``core.equations``; every bundled cosmology constant is flag-overridable. No
network, no DB, no RNG, no time.
"""

import math

from core.equations import (
    _HBAR, _C_MS, _C_KMS, _G, _EPSILON_0, _ELEMENTARY_CHARGE, _M_ELECTRON,
    _MPC_M, _HUBBLE_DEFAULT_KMS_MPC, _OMEGA_LAMBDA_DEFAULT, _OMEGA_M_DEFAULT, _SOLAR_MASS_KG, _LY_M,
)

_PI = math.pi
_PI2_HBAR_C = _PI ** 2 * _HBAR * _C_MS          # π²ℏc (casimir)
_E_PLANCK_J = math.sqrt(_HBAR * _C_MS ** 5 / _G)  # Planck energy √(ℏc⁵/G), J
_GEV_J = 1e9 * _ELEMENTARY_CHARGE                 # 1 GeV in joules

# QED-cutoff energy-scale presets (GeV) for the vacuum catastrophe.
_CUTOFF_PRESETS_GEV = {"planck": _E_PLANCK_J / _GEV_J, "electroweak": 246.0, "qcd": 0.2}


# ── M1 ───────────────────────────────────────────────────────────────────────
def compute_casimir(separation_m=None, separation_nm=None, area_m2=None,
                    geometry="parallel-plate", sphere_radius_m=None):
    """Casimir pressure / negative energy density (parallel-plate) or force (sphere-plate) (M1)."""
    given = [(v, f) for (v, f) in ((separation_m, 1.0), (separation_nm, 1e-9)) if v is not None]
    if len(given) != 1:
        return {"error": "Provide exactly one of --separation-m / --separation-nm."}
    d = given[0][0] * given[0][1]
    if d <= 0:
        return {"error": "Separation must be positive."}
    if geometry not in ("parallel-plate", "sphere-plate"):
        return {"error": "Geometry must be parallel-plate or sphere-plate."}

    if geometry == "parallel-plate":
        if sphere_radius_m is not None:
            return {"error": "--sphere-radius-m applies only to --geometry sphere-plate."}
        A = 1.0 if area_m2 is None else area_m2
        if A <= 0:
            return {"error": "Area must be positive."}
        pressure = _PI2_HBAR_C / (240.0 * d ** 4)
        energy_density = -_PI2_HBAR_C / (720.0 * d ** 3)
        return {
            "pressure_pa": pressure,
            "force_n": pressure * A,
            "energy_density_j_m3": energy_density,
            "total_energy_j": energy_density * A * d,
            "separation_m": d,
            "area_m2": A,
            "geometry": geometry,
            "sphere_radius_m": None,
            "model_note": ("Parallel-plate Casimir: P = π²ℏc/(240 d⁴) (attractive), energy density "
                           "u = −π²ℏc/(720 d³) (negative → the NEC-relevant quantity for Group N). "
                           "Idealised perfect conductors at T=0; real plates (finite conductivity, "
                           "roughness, temperature) deviate."),
        }

    # sphere-plate — proximity-force approximation
    if sphere_radius_m is None:
        return {"error": "--geometry sphere-plate needs --sphere-radius-m."}
    if sphere_radius_m <= 0:
        return {"error": "Sphere radius must be positive."}
    force = -_PI ** 3 * _HBAR * _C_MS * sphere_radius_m / (360.0 * d ** 3)
    return {
        "pressure_pa": None,
        "force_n": force,
        "energy_density_j_m3": None,
        "total_energy_j": None,
        "separation_m": d,
        "area_m2": None,
        "geometry": geometry,
        "sphere_radius_m": sphere_radius_m,
        "model_note": ("Sphere-plate Casimir force F = −π³ℏcR/(360 d³) via the proximity-force "
                       "approximation (valid for R ≫ d) — the configuration most Casimir "
                       "experiments use. Pressure/energy-density are not reported for the curved "
                       "geometry (see --geometry parallel-plate for the negative energy density)."),
    }


# ── M2 ───────────────────────────────────────────────────────────────────────
def compute_vacuum_energy(omega_lambda=None, hubble_kms_mpc=None, cutoff="planck"):
    """Vacuum / dark-energy density and the QED vacuum-catastrophe ratio (M2)."""
    omega_lambda = _OMEGA_LAMBDA_DEFAULT if omega_lambda is None else omega_lambda
    hubble = _HUBBLE_DEFAULT_KMS_MPC if hubble_kms_mpc is None else hubble_kms_mpc
    if omega_lambda <= 0 or omega_lambda > 1:
        return {"error": "Omega_lambda must be in (0, 1]."}
    if hubble <= 0:
        return {"error": "Hubble constant must be positive."}

    # cutoff → energy scale in joules
    if isinstance(cutoff, str) and cutoff.lower() in _CUTOFF_PRESETS_GEV:
        cutoff_gev = _CUTOFF_PRESETS_GEV[cutoff.lower()]
        cutoff_label = cutoff.lower()
    else:
        try:
            cutoff_gev = float(cutoff)
        except (TypeError, ValueError):
            return {"error": "Cutoff must be planck/electroweak/qcd or a number in GeV."}
        if cutoff_gev <= 0:
            return {"error": "Cutoff energy must be positive (GeV)."}
        cutoff_label = f"{cutoff_gev:g} GeV"
    cutoff_j = cutoff_gev * _GEV_J

    h0_si = hubble * 1000.0 / _MPC_M
    rho_crit = 3.0 * h0_si ** 2 / (8.0 * _PI * _G) * _C_MS ** 2   # energy density, J/m³
    rho_lambda = omega_lambda * rho_crit
    lam = 3.0 * omega_lambda * h0_si ** 2 / _C_MS ** 2            # cosmological constant, m⁻²
    qed_estimate = cutoff_j ** 4 / (_HBAR * _C_MS) ** 3          # J/m³
    return {
        "rho_lambda_j_m3": rho_lambda,
        "rho_crit_j_m3": rho_crit,
        "lambda_m2": lam,
        "equation_of_state_w": -1.0,
        "cutoff": cutoff_label,
        "qed_estimate_j_m3": qed_estimate,
        "catastrophe_ratio": qed_estimate / rho_lambda,
        "omega_lambda": omega_lambda,
        "hubble_kms_mpc": hubble,
        "model_note": ("Observed ρ_Λ = Ω_Λ·ρ_crit, ρ_crit = 3H₀²c²/(8πG); Λ = 3Ω_ΛH₀²/c²; "
                       "w = −1 (cosmological constant). QED zero-point estimate ρ_vac ~ "
                       "E_cutoff⁴/(ℏc)³ (Planck cutoff → ~10¹¹³ J/m³) gives the ~10¹²² "
                       "'vacuum catastrophe' ratio — an order-of-magnitude dimensional estimate, "
                       "not a renormalised QFT prediction."),
    }


# ── M3 ───────────────────────────────────────────────────────────────────────
def compute_schwinger_limit(field_vm=None, intensity_wcm2=None):
    """Schwinger critical field / intensity for vacuum pair production (M3)."""
    if field_vm is not None and intensity_wcm2 is not None:
        return {"error": "Provide only one of --field-vm / --intensity-wcm2."}
    e_c = _M_ELECTRON ** 2 * _C_MS ** 3 / (_ELEMENTARY_CHARGE * _HBAR)   # V/m
    b_c = e_c / _C_MS                                                    # T
    i_c_wm2 = 0.5 * _EPSILON_0 * _C_MS * e_c ** 2
    i_c_wcm2 = i_c_wm2 / 1e4

    ratio = None
    if field_vm is not None:
        if field_vm <= 0:
            return {"error": "Field must be positive (V/m)."}
        ratio = field_vm / e_c
    elif intensity_wcm2 is not None:
        if intensity_wcm2 <= 0:
            return {"error": "Intensity must be positive (W/cm²)."}
        ratio = intensity_wcm2 / i_c_wcm2

    return {
        "critical_field_vm": e_c,
        "critical_magnetic_field_t": b_c,
        "critical_intensity_wcm2": i_c_wcm2,
        "ratio_to_critical": ratio,
        "model_note": ("Schwinger critical field E_c = m_e²c³/(eℏ) ≈ 1.32×10¹⁸ V/m (B_c = E_c/c ≈ "
                       "4.41×10⁹ T); below it, spontaneous e⁺e⁻ pair production is exponentially "
                       "suppressed. Critical intensity uses I_c = ½ε₀cE_c² ≈ 2.3×10²⁹ W/cm² — some "
                       "references quote ~4.6×10²⁹ W/cm² under a peak-field/no-½ convention."),
    }


# ── M4 ───────────────────────────────────────────────────────────────────────
def compute_hubble_flow(distance_mpc=None, distance_ly=None, mass_msun=None,
                        radius_ly=None, radius_mpc=None, hubble_kms_mpc=None,
                        omega_lambda=None, omega_m=None):
    """Cosmological recession, or the local-binding turnaround test (M4)."""
    hubble = _HUBBLE_DEFAULT_KMS_MPC if hubble_kms_mpc is None else hubble_kms_mpc
    omega_lambda = _OMEGA_LAMBDA_DEFAULT if omega_lambda is None else omega_lambda
    omega_m = _OMEGA_M_DEFAULT if omega_m is None else omega_m
    if hubble <= 0:
        return {"error": "Hubble constant must be positive."}
    if omega_lambda <= 0:
        return {"error": "Omega_lambda must be positive."}

    have_dist = distance_mpc is not None or distance_ly is not None
    have_bind = mass_msun is not None or radius_ly is not None or radius_mpc is not None
    if have_dist == have_bind:
        return {"error": "Provide either a recession distance (--distance-mpc/--distance-ly) OR a "
                         "binding test (--mass-msun + --radius-ly/--radius-mpc), not both."}

    out = {
        "recession_velocity_kms": None, "recession_fraction_c": None,
        "binding_ratio": None, "turnaround_radius_mpc": None, "bound": None,
        "hubble_kms_mpc": hubble, "omega_lambda": omega_lambda, "omega_m": omega_m,
        "model_note": ("Recession v = H₀·d. Binding test: the Λ acceleration Ω_ΛH₀²·r balances "
                       "gravity GM/r² at the turnaround radius r_ta = (GM/(Ω_ΛH₀²))^(1/3); "
                       "binding_ratio = (r_ta/r)³ (> 1 → bound). Λc²/3 = Ω_ΛH₀². Local M is the "
                       "supplied bound mass; Ω_m is echoed for the deceleration-parameter context."),
    }

    if have_dist:
        dm = [(v, f) for (v, f) in ((distance_mpc, 1.0), (distance_ly, 1.0 / (_MPC_M / _LY_M)))
              if v is not None]
        if len(dm) != 1:
            return {"error": "Provide exactly one of --distance-mpc / --distance-ly."}
        d_mpc = dm[0][0] * dm[0][1]
        if d_mpc <= 0:
            return {"error": "Distance must be positive."}
        v_kms = hubble * d_mpc
        out["recession_velocity_kms"] = v_kms
        out["recession_fraction_c"] = v_kms / _C_KMS
        out["distance_mpc"] = d_mpc
        return out

    # binding mode
    if mass_msun is None:
        return {"error": "Binding test needs --mass-msun."}
    if mass_msun <= 0:
        return {"error": "Mass must be positive."}
    rm = [(v, f) for (v, f) in ((radius_mpc, _MPC_M), (radius_ly, _LY_M)) if v is not None]
    if len(rm) != 1:
        return {"error": "Provide exactly one of --radius-ly / --radius-mpc."}
    r_m = rm[0][0] * rm[0][1]
    if r_m <= 0:
        return {"error": "Radius must be positive."}

    M = mass_msun * _SOLAR_MASS_KG
    h0_si = hubble * 1000.0 / _MPC_M
    r_ta_m = (_G * M / (omega_lambda * h0_si ** 2)) ** (1.0 / 3.0)
    out["turnaround_radius_mpc"] = r_ta_m / _MPC_M
    out["binding_ratio"] = (r_ta_m / r_m) ** 3
    out["bound"] = out["binding_ratio"] > 1.0
    out["mass_msun"] = mass_msun
    out["radius_mpc"] = r_m / _MPC_M
    return out
