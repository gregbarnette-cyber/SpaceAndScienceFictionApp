"""Phase AJ (Group P) — planet-formation calculators (Packet 3.5).

Six ``query.py``-only, pure-math, self-validating (Phase-H/P contract) formation-physics
calculators for the sibling ``scifiWorldBuilding-Claude`` repo — the disk-model + isolation /
pebble-isolation / gap-opening / Toomre-Q / critical-core-mass spine the generator's
``mass_by_zone`` / ``spacing_ratio`` / ``origin_priors`` are derived from. Nothing here computes
surface densities, formation masses, or instability thresholds before this module; the existing
zone calcs (``ice-lines`` / ``habitable-zone`` / ``roche-limit`` / ``hill-sphere``) do not.

Physics pins F1–F6 (claim-map, sibling repo):
  * **P1 disk-model** (F1, Hartmann 2017 / canon MMSN) — Σ_gas(r) = Σ₀·(M_disk/M_MMSN)·r^p,
    T(r) = T₀·(L★/L⊙)^¼·r^q, Σ_solid = Z·f_ice·Σ_gas, H/r = c_s/v_K. Defaults reproduce the
    Approved-Canon MMSN exactly (Σ₀=1700 g/cm², p=−3/2; T₀=280 K, q=−1/2). Snow line solved from
    this module's OWN T-law (no ice-lines import; followup-1 Ruling 2 / Option A).
  * **P2 isolation-mass** (F2, Armitage Eq. 201 after Lissauer 1993) —
    M_iso = (8/√3)·π^{3/2}·C^{3/2}·M★^{−1/2}·Σ_p^{3/2}·a³.
  * **P3 pebble-isolation-mass** (F3, Bitsch 2018) — 25·f_fit·(H/r/0.05)³ M⊕.
  * **P4 gap-opening-mass** (F4, Crida 2006 Eq. 15) — root-find the marginal-threshold q where
    P(q)=3H/(4R_H)+50/(qR)=p_target (followup-1 Ruling 1a: headline = solved threshold).
  * **P5 toomre-q** (F5, Armitage Eq. 164) — Q = c_s·Ω/(πGΣ).
  * **P6 critical-core-mass** (F6, Armitage Eq. 236 / Ikoma+2000) — 12·(Ṁ/1e-6)^¼·(κ/1)^¼ M⊕.

Constants come from ``core.equations``; every bundled coefficient is flag-overridable in
``query.py``. No network, no DB, no numpy/scipy (P4's root find is a pure-Python bisection),
no RNG, no time.
"""

import math

from core.equations import (
    _G, _K_B, _M_PROTON, _SOLAR_MASS_KG, _EARTH_MASS_KG, _JUP_MASS_KG,
    _M_PER_AU, _KM_PER_AU, _MU_GAS_DEFAULT, _Z_SUN,
)

# MMSN reference (F1): total disk mass out to 100 AU ≈ 0.01 M⊙.
_M_MMSN_MSUN = 0.01
_M_H = _M_PROTON  # hydrogen atom mass ≈ proton mass (reproduces H/r ≈ 0.033 anchor)


# ── Shared helpers ────────────────────────────────────────────────────────────
def _sound_speed(temp_k, mu):
    """Isothermal sound speed c_s = √(k_B·T/(μ·m_H)), m/s."""
    return math.sqrt(_K_B * temp_k / (mu * _M_H))


def _omega(mstar_kg, a_m):
    """Keplerian angular frequency Ω = √(GM★/a³), rad/s."""
    return math.sqrt(_G * mstar_kg / a_m ** 3)


def _kepler_velocity(mstar_kg, a_m):
    """Keplerian orbital speed v_K = √(GM★/a), m/s."""
    return math.sqrt(_G * mstar_kg / a_m)


def _aspect_ratio(temp_k, mstar_kg, a_m, mu):
    """Disk aspect ratio H/r = c_s/v_K."""
    return _sound_speed(temp_k, mu) / _kepler_velocity(mstar_kg, a_m)


def _resolve_hr(hr, temp_k, mstar_msun, a_au, mu):
    """H/r from a direct --hr, OR derived from (--temp-k, --mstar-msun, --a-au).

    Returns a float, or an {"error"} dict. Exactly one mode must be supplied so each
    tool stands alone yet chains from disk-model.
    """
    direct = hr is not None
    derived = any(v is not None for v in (temp_k, mstar_msun, a_au))
    if direct and derived:
        return {"error": "Provide either --hr OR (--temp-k --mstar-msun --a-au), not both."}
    if direct:
        if hr <= 0:
            return {"error": "Aspect ratio --hr must be positive."}
        return hr
    if not derived:
        return {"error": "Provide --hr, or all of --temp-k --mstar-msun --a-au to derive it."}
    if temp_k is None or mstar_msun is None or a_au is None:
        return {"error": "Deriving H/r needs all of --temp-k, --mstar-msun, and --a-au."}
    if temp_k <= 0 or mstar_msun <= 0 or a_au <= 0:
        return {"error": "--temp-k, --mstar-msun, and --a-au must all be positive."}
    return _aspect_ratio(temp_k, mstar_msun * _SOLAR_MASS_KG, a_au * _M_PER_AU, mu)


_NOTE_DISK = (
    "MMSN disk model (Hartmann 2017 / canon, pin F1): Σ_gas=Σ₀·(M_disk/M_MMSN)·(r/AU)^p "
    "[default Σ₀=1700 g/cm², p=−3/2]; T=T₀·(L★/L⊙)^¼·(r/AU)^q [default T₀=280 K, q=−1/2, Hayashi "
    "irradiation]; Σ_solid=Z·f_ice·Σ_gas [default Z=Z_⊙=0.0134 → 22.8 g/cm² at 1 AU; the 10 g/cm² "
    "planetesimal convention the isolation-mass anchors use is a lower MMSN variant, recover via "
    "--z/--ice-factor]. Snow line solved from THIS T-law at T_snow (default 170 K → 2.71 AU at "
    "L=1, ∝L^½); f_ice steps ×ice_factor exterior. H/r=c_s/v_K, c_s=√(k_B T/(μ m_H)). Defaults "
    "reproduce the Approved-Canon MMSN exactly; overrides are for scaling/experiments."
)
_NOTE_ISO = (
    "Oligarchic isolation mass (Armitage Eq. 201 after Lissauer 1993, pin F2): "
    "M_iso=(8/√3)·π^{3/2}·C^{3/2}·M★^{−1/2}·Σ_p^{3/2}·a³, C=feeding-zone half-width in Hill radii "
    "(default 2√3≈3.464). --feeding-zone-b gives the Kokubo&Ida oligarchic full width in MUTUAL "
    "Hill radii (C=b/(2·2^{1/3}), since r_H,mutual≈2^{1/3}·r_H,single). Scaling M_iso∝Σ_p^{3/2}·a³·M★^{−1/2}."
)


# ── P1 — disk-model ───────────────────────────────────────────────────────────
def _disk_point(r_au, mstar_kg, lstar_lsun, disk_mass_mmsn, z, snowline_au, ice_factor, mu,
                sigma0, sigma_slope, temp0, temp_slope):
    """One radius of the disk profile → the per-radius output dict (no validation)."""
    sigma_gas = sigma0 * disk_mass_mmsn * r_au ** sigma_slope          # g/cm²
    temp_k = temp0 * (lstar_lsun ** 0.25) * r_au ** temp_slope         # K
    interior = r_au < snowline_au
    f_ice = 1.0 if interior else ice_factor
    sigma_solid = z * f_ice * sigma_gas                                # g/cm²

    a_m = r_au * _M_PER_AU
    c_s = _sound_speed(temp_k, mu)                                     # m/s
    v_k = _kepler_velocity(mstar_kg, a_m)                              # m/s
    omega = _omega(mstar_kg, a_m)                                      # rad/s
    hr = c_s / v_k
    scale_height_au = (c_s / omega) / _M_PER_AU
    return {
        "r_au": r_au,
        "sigma_gas_gcm2": sigma_gas,
        "sigma_solid_gcm2": sigma_solid,
        "temp_k": temp_k,
        "sound_speed_ms": c_s,
        "aspect_ratio_hr": hr,
        "scale_height_au": scale_height_au,
        "omega_per_s": omega,
        "kepler_velocity_kms": v_k / 1000.0,
        "interior_to_snowline": interior,
    }


def compute_disk_model(r_au=None, r_grid=None, mstar_msun=1.0,
                       disk_mass_mmsn=None, disk_mass_msun=None,
                       lstar_lsun=None, ms_luminosity=False,
                       feh=None, z=None,
                       snowline_au=None, snowline_temp_k=170.0, ice_factor=2.0,
                       mu=_MU_GAS_DEFAULT,
                       sigma0=1700.0, sigma_slope=-1.5, temp0=280.0, temp_slope=-0.5):
    """Protoplanetary-disk Σ_gas / Σ_solid / T / H-r profile (P1). Single radius or a grid."""
    # radius mode — exactly one of --r-au / --r-grid
    if (r_au is None) == (r_grid is None):
        return {"error": "Provide exactly one of --r-au or --r-grid LO HI N."}
    if mstar_msun <= 0:
        return {"error": "--mstar-msun must be positive."}
    if mu <= 0:
        return {"error": "--mu must be positive."}
    if ice_factor <= 0:
        return {"error": "--ice-factor must be positive."}
    if snowline_temp_k <= 0:
        return {"error": "--snowline-temp-k must be positive."}

    # disk mass — at most one of --disk-mass-mmsn / --disk-mass-msun (default 1 MMSN)
    if disk_mass_mmsn is not None and disk_mass_msun is not None:
        return {"error": "Provide only one of --disk-mass-mmsn or --disk-mass-msun."}
    if disk_mass_msun is not None:
        if disk_mass_msun <= 0:
            return {"error": "--disk-mass-msun must be positive."}
        disk_mmsn = disk_mass_msun / _M_MMSN_MSUN
    else:
        disk_mmsn = 1.0 if disk_mass_mmsn is None else disk_mass_mmsn
        if disk_mmsn <= 0:
            return {"error": "--disk-mass-mmsn must be positive."}

    # luminosity — at most one of --lstar-lsun / --ms-luminosity (default 1)
    if lstar_lsun is not None and ms_luminosity:
        return {"error": "Provide only one of --lstar-lsun or --ms-luminosity."}
    if ms_luminosity:
        lstar = mstar_msun ** 3.5
    else:
        lstar = 1.0 if lstar_lsun is None else lstar_lsun
        if lstar <= 0:
            return {"error": "--lstar-lsun must be positive."}

    # metallicity — at most one of --feh / --z (default Z_⊙)
    if feh is not None and z is not None:
        return {"error": "Provide only one of --feh or --z."}
    if feh is not None:
        z_val = _Z_SUN * 10.0 ** feh
    else:
        z_val = _Z_SUN if z is None else z
        if z_val <= 0:
            return {"error": "--z must be positive."}

    # snow line — explicit --snowline-au, else solved from THIS T-law at snowline_temp_k
    # (Ruling 2 / Option A): T(r)=snowline_temp_k → r = √L·(T₀/T_snow)^(−1/temp_slope)... general:
    # temp0·L^¼·r^temp_slope = T_snow → r = (T_snow/(temp0·L^¼))^(1/temp_slope).
    if snowline_au is not None:
        if snowline_au <= 0:
            return {"error": "--snowline-au must be positive."}
        snow_au = snowline_au
    else:
        snow_au = (snowline_temp_k / (temp0 * lstar ** 0.25)) ** (1.0 / temp_slope)

    mstar_kg = mstar_msun * _SOLAR_MASS_KG
    kwargs = dict(mstar_kg=mstar_kg, lstar_lsun=lstar, disk_mass_mmsn=disk_mmsn, z=z_val,
                  snowline_au=snow_au, ice_factor=ice_factor, mu=mu,
                  sigma0=sigma0, sigma_slope=sigma_slope, temp0=temp0, temp_slope=temp_slope)

    if r_au is not None:
        if r_au <= 0:
            return {"error": "--r-au must be positive."}
        out = _disk_point(r_au, **kwargs)
        out.update(disk_mass_mmsn=disk_mmsn, metallicity_z=z_val, snowline_au=snow_au,
                   model_note=_NOTE_DISK)
        return out

    # grid mode
    lo, hi, n = r_grid
    if lo <= 0 or hi <= 0:
        return {"error": "--r-grid LO and HI must be positive."}
    if hi <= lo:
        return {"error": "--r-grid HI must exceed LO."}
    n = int(n)
    if n < 2:
        return {"error": "--r-grid N must be ≥ 2."}
    log_lo, log_hi = math.log10(lo), math.log10(hi)
    radii = [_disk_point(10.0 ** (log_lo + (log_hi - log_lo) * i / (n - 1)), **kwargs)
             for i in range(n)]
    return {
        "radii": radii,
        "disk_mass_mmsn": disk_mmsn,
        "metallicity_z": z_val,
        "snowline_au": snow_au,
        "mstar_msun": mstar_msun,
        "lstar_lsun": lstar,
        "model_note": _NOTE_DISK,
    }


# ── P2 — isolation-mass ───────────────────────────────────────────────────────
_C_LISSAUER = 2.0 * math.sqrt(3.0)  # feeding-zone half-width in Hill radii (Lissauer 1993)


def compute_isolation_mass(sigma_p_gcm2=None, a_au=None, mstar_msun=1.0,
                           feeding_zone_c=None, feeding_zone_b=None):
    """Oligarchic isolation mass M_iso (P2). Sets mass_by_zone + oligarch spacing."""
    if sigma_p_gcm2 is None or sigma_p_gcm2 <= 0:
        return {"error": "--sigma-p-gcm2 (planetesimal surface density) must be positive."}
    if a_au is None or a_au <= 0:
        return {"error": "--a-au (orbital radius) must be positive."}
    if mstar_msun <= 0:
        return {"error": "--mstar-msun must be positive."}

    # feeding zone — at most one convention; default Armitage half-width C = 2√3
    if feeding_zone_c is not None and feeding_zone_b is not None:
        return {"error": "Provide only one of --feeding-zone-c or --feeding-zone-b."}
    if feeding_zone_b is not None:
        if feeding_zone_b <= 0:
            return {"error": "--feeding-zone-b must be positive."}
        # b = full width in MUTUAL Hill radii; C = single-Hill half-width = b/(2·2^{1/3}).
        c = feeding_zone_b / (2.0 * 2.0 ** (1.0 / 3.0))
        convention = "full-width-b"
        width_hill = feeding_zone_b
    else:
        c = _C_LISSAUER if feeding_zone_c is None else feeding_zone_c
        if c <= 0:
            return {"error": "--feeding-zone-c must be positive."}
        convention = "half-width-C"
        width_hill = c

    sigma_si = sigma_p_gcm2 * 10.0        # g/cm² → kg/m²
    a_m = a_au * _M_PER_AU
    mstar_kg = mstar_msun * _SOLAR_MASS_KG
    m_iso_kg = ((8.0 / math.sqrt(3.0)) * math.pi ** 1.5 * c ** 1.5
                * mstar_kg ** -0.5 * sigma_si ** 1.5 * a_m ** 3)
    return {
        "isolation_mass_mearth": m_iso_kg / _EARTH_MASS_KG,
        "isolation_mass_mjup": m_iso_kg / _JUP_MASS_KG,
        "feeding_zone_width_hill": width_hill,
        "convention": convention,
        "sigma_p_gcm2": sigma_p_gcm2,
        "a_au": a_au,
        "mstar_msun": mstar_msun,
        "model_note": _NOTE_ISO,
    }


# ── P3 — pebble-isolation-mass ────────────────────────────────────────────────
_NOTE_PEB = (
    "Pebble-isolation mass (Bitsch 2018 Eq. 5, refining Lambrechts 2014, pin F3): "
    "M_iso,peb = 25·f_fit·(H/r/0.05)³ M⊕, f_fit = 0.34·(log(0.001)/log(α))⁴ + 0.66 (α₃=0.001). "
    "--simple → the base Lambrechts law 20·(H/r/0.05)³ (f_fit=1). The pebble-accretion cutoff — the "
    "core's pressure bump traps drifting pebbles: below it a solid-dominated super-Earth, above it a "
    "core that can reach gas runaway. Cube-in-(H/r) → steep inner-vs-outer mass gradient."
)


def compute_pebble_isolation_mass(hr=None, temp_k=None, mstar_msun=None, a_au=None,
                                  alpha=1e-3, simple=False, dlnp_dlnr=-2.5,
                                  peb_norm=None, mu=_MU_GAS_DEFAULT):
    """Pebble-isolation mass — the super-Earth ↔ giant switch (P3)."""
    resolved = _resolve_hr(hr, temp_k, mstar_msun, a_au, mu)
    if isinstance(resolved, dict):
        return resolved
    hr_val = resolved
    if alpha <= 0:
        return {"error": "--alpha must be positive."}

    if simple:
        norm = 20.0 if peb_norm is None else peb_norm
        f_fit = 1.0
        mode = "lambrechts2014"
    else:
        norm = 25.0 if peb_norm is None else peb_norm
        f_fit = 0.34 * (math.log(0.001) / math.log(alpha)) ** 4 + 0.66
        mode = "bitsch2018"
    m_peb = norm * f_fit * (hr_val / 0.05) ** 3
    return {
        "pebble_isolation_mass_mearth": m_peb,
        "hr": hr_val,
        "alpha": alpha,
        "f_fit": f_fit,
        "dlnp_dlnr": dlnp_dlnr,
        "mode": mode,
        "model_note": _NOTE_PEB,
    }


# ── P4 — gap-opening-mass ─────────────────────────────────────────────────────
_NOTE_GAP = (
    "Marginal gap-opening threshold: mass where Crida (2006) Eq. 15 P(q)=3H/(4R_H)+50/(qR)=p_target "
    "(pin F4). At H/r=0.05, ν=10⁻⁵·⁵ → q≈4.98e-4 (≈0.52 M_Jup at M⊙). Crida's Case-1 example q=10⁻³ "
    "(≈1.05 M_Jup) gives P=0.699 — a clear, super-marginal gap, NOT the threshold. Viscosity via "
    "--alpha (ν_code=α·(H/r)²), --nu-code (ν in a²Ω units), or --reynolds (R=a²Ω/ν). Criterion is "
    "necessary but, for a migrating planet, not always sufficient (Malik et al. 2015)."
)


def _crida_p(q, hr, reynolds):
    """Crida Eq. 15 gap function P(q) = 3H/(4R_H) + 50/(qR); H and R_H in units of a."""
    r_hill = (q / 3.0) ** (1.0 / 3.0)
    return 3.0 * hr / (4.0 * r_hill) + 50.0 / (q * reynolds)


def compute_gap_opening_mass(hr=None, temp_k=None, mstar_msun=None, a_au=None,
                             alpha=None, nu_code=None, reynolds=None,
                             p_target=1.0, mu=_MU_GAS_DEFAULT):
    """Type-II gap-opening mass via the Crida criterion — root-find the marginal q (P4)."""
    # M★ and a are ALWAYS required (the q→mass conversion), so P4 can't use the shared
    # _resolve_hr (which reads their presence as "derive H/r" mode). H/r comes from --hr
    # directly, or is derived from --temp-k with the (already-required) M★ and a.
    if mstar_msun is None or a_au is None:
        return {"error": "Gap mass needs --mstar-msun and --a-au (for the q→mass conversion)."}
    if mstar_msun <= 0 or a_au <= 0:
        return {"error": "--mstar-msun and --a-au must be positive."}
    if p_target <= 0:
        return {"error": "--p-target must be positive."}

    if hr is not None and temp_k is not None:
        return {"error": "Provide either --hr OR --temp-k, not both."}
    if hr is not None:
        if hr <= 0:
            return {"error": "Aspect ratio --hr must be positive."}
        hr_val = hr
    elif temp_k is not None:
        if temp_k <= 0:
            return {"error": "--temp-k must be positive."}
        hr_val = _aspect_ratio(temp_k, mstar_msun * _SOLAR_MASS_KG, a_au * _M_PER_AU, mu)
    else:
        return {"error": "Provide --hr, or --temp-k (with --mstar-msun --a-au) to derive it."}

    # viscosity → Reynolds number R = a²Ω/ν; exactly one of --alpha / --nu-code / --reynolds
    given = [x for x in (alpha, nu_code, reynolds) if x is not None]
    if len(given) != 1:
        return {"error": "Provide exactly one of --alpha, --nu-code, or --reynolds."}
    if alpha is not None:
        if alpha <= 0:
            return {"error": "--alpha must be positive."}
        nu = alpha * hr_val ** 2          # ν in a²Ω units
        R = 1.0 / nu
        alpha_or_reynolds = alpha
    elif nu_code is not None:
        if nu_code <= 0:
            return {"error": "--nu-code must be positive."}
        R = 1.0 / nu_code
        alpha_or_reynolds = R
    else:
        if reynolds <= 0:
            return {"error": "--reynolds must be positive."}
        R = reynolds
        alpha_or_reynolds = R

    # P(q) is monotone-decreasing in q; bisect for P(q) = p_target.
    lo, hi = 1e-9, 1.0
    p_lo, p_hi = _crida_p(lo, hr_val, R), _crida_p(hi, hr_val, R)
    if p_lo < p_target:
        return {"error": "No gap-opening threshold below q=1e-9 for these parameters "
                         "(disk too thick/viscous — a gap never opens up to q→0)."}
    if p_hi > p_target:
        return {"error": "No gap-opening threshold below q=1 for these parameters."}
    for _ in range(200):
        mid = math.sqrt(lo * hi)          # geometric bisection (q spans orders of magnitude)
        if _crida_p(mid, hr_val, R) > p_target:
            lo = mid
        else:
            hi = mid
    q = math.sqrt(lo * hi)
    mstar_kg = mstar_msun * _SOLAR_MASS_KG
    m_gap_kg = q * mstar_kg
    return {
        "gap_opening_mass_mearth": m_gap_kg / _EARTH_MASS_KG,
        "gap_opening_mass_mjup": m_gap_kg / _JUP_MASS_KG,
        "threshold_q": q,
        "hr": hr_val,
        "alpha_or_reynolds": alpha_or_reynolds,
        "p_value_at_threshold": _crida_p(q, hr_val, R),
        "p_target": p_target,
        "mstar_msun": mstar_msun,
        "a_au": a_au,
        "model_note": _NOTE_GAP,
    }


# ── P5 — toomre-q ─────────────────────────────────────────────────────────────
_NOTE_TOOMRE = (
    "Toomre gravitational-instability parameter (Armitage Eq. 164 after Toomre 1964, pin F5): "
    "Q=c_s·Ω/(πGΣ), unstable for Q<Q_crit (default 1), stable above (Keplerian κ=Ω). "
    "Collisionless/particle disk: replace c_s with the 1-D velocity dispersion (--dispersion-ms). "
    "Most-unstable wavelength λ_crit=2c_s²/(GΣ); order-of-magnitude fragment mass M_frag≈πΣ(λ_crit/2)². "
    "The MMSN disk is stable everywhere (Q≫1); GI needs a disk ~1–2 orders more massive."
)


def compute_toomre_q(sigma_gcm2=None, temp_k=None, cs_ms=None, dispersion_ms=None,
                     mstar_msun=None, a_au=None, mu=_MU_GAS_DEFAULT, q_crit=1.0):
    """Toomre Q disk-instability parameter + λ_crit and fragment mass (P5)."""
    if sigma_gcm2 is None or sigma_gcm2 <= 0:
        return {"error": "--sigma-gcm2 (gas surface density) must be positive."}
    if mstar_msun is None or mstar_msun <= 0:
        return {"error": "--mstar-msun must be positive."}
    if a_au is None or a_au <= 0:
        return {"error": "--a-au must be positive."}
    if q_crit <= 0:
        return {"error": "--q-crit must be positive."}

    # sound speed — exactly one of --temp-k / --cs-ms / --dispersion-ms
    given = [x for x in (temp_k, cs_ms, dispersion_ms) if x is not None]
    if len(given) != 1:
        return {"error": "Provide exactly one of --temp-k, --cs-ms, or --dispersion-ms."}
    if temp_k is not None:
        if temp_k <= 0:
            return {"error": "--temp-k must be positive."}
        c_s = _sound_speed(temp_k, mu)
    elif cs_ms is not None:
        if cs_ms <= 0:
            return {"error": "--cs-ms must be positive."}
        c_s = cs_ms
    else:
        if dispersion_ms <= 0:
            return {"error": "--dispersion-ms must be positive."}
        c_s = dispersion_ms

    sigma_si = sigma_gcm2 * 10.0          # g/cm² → kg/m²
    a_m = a_au * _M_PER_AU
    mstar_kg = mstar_msun * _SOLAR_MASS_KG
    omega = _omega(mstar_kg, a_m)
    q = c_s * omega / (math.pi * _G * sigma_si)
    lambda_crit_m = 2.0 * c_s ** 2 / (_G * sigma_si)
    m_frag_kg = math.pi * sigma_si * (lambda_crit_m / 2.0) ** 2
    return {
        "toomre_q": q,
        "unstable": q < q_crit,
        "q_crit": q_crit,
        "lambda_crit_au": lambda_crit_m / _M_PER_AU,
        "fragment_mass_mjup": m_frag_kg / _JUP_MASS_KG,
        "sound_speed_ms": c_s,
        "omega_per_s": omega,
        "sigma_gcm2": sigma_gcm2,
        "a_au": a_au,
        "model_note": _NOTE_TOOMRE,
    }


# ── P6 — critical-core-mass ───────────────────────────────────────────────────
_NOTE_CRIT = (
    "Critical core mass (Armitage Eq. 236, fit of Ikoma, Nakazawa & Emori 2000; concept Mizuno 1980 / "
    "Pollack 1996, pin F6): M_crit ≈ 12·(Ṁ_core/1e-6 M⊕ yr⁻¹)^{1/4}·(κ_R/1 cm² g⁻¹)^{1/4} M⊕. Above this "
    "the gaseous envelope can no longer stay in hydrostatic equilibrium → runaway gas accretion. Power-law "
    "indices uncertain ±0.05 (weak dependence, ~10 M⊕ scale). Pairs with the pebble-isolation mass (P3): "
    "a core must reach ~pebble-isolation AND the critical core mass to run away."
)


def compute_critical_core_mass(mdot_core=1e-6, opacity=1.0, index=0.25, crit_norm=12.0):
    """Critical (envelope-runaway) core mass for gas-giant formation (P6)."""
    if mdot_core <= 0:
        return {"error": "--mdot-core must be positive."}
    if opacity <= 0:
        return {"error": "--opacity must be positive."}
    if crit_norm <= 0:
        return {"error": "--crit-norm must be positive."}
    m_crit = crit_norm * (mdot_core / 1e-6) ** index * (opacity / 1.0) ** index
    return {
        "critical_core_mass_mearth": m_crit,
        "mdot_core": mdot_core,
        "opacity": opacity,
        "index": index,
        "model_note": _NOTE_CRIT,
    }
