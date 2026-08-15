"""Phase AT (Packet 38.1) — weapon reach & lethality physics (W2 / W3 / W4).

Three ``query.py``-only, pure-math, self-validating (Phase-H/P contract: curated ``{"error"}`` →
exit 1, argparse → exit 2) calculators for the sibling ``scifiWorldBuilding-Claude`` repo:

  * ``compute_beam_weapon_engagement`` (W2) — directed-energy reach & lethality: diffraction spot,
    fraction on target, intensity, dwell-to-kill, effective range. Composes ``sensing._rayleigh_theta``.
  * ``compute_kinetic_kill``           (W3) — hypervelocity impactor vs armor: KE (classical +
    relativistic), TNT-equiv, penetration, monolithic/Whipple verdict. Composes
    ``relativity.compute_relativistic_energy_momentum``; references ``shielding-attenuation``.
  * ``compute_warhead_effects``        (W4) — warhead lethality radius in vacuum: per-channel
    inverse-square fluence + kill radius. Yield is an INPUT (the ``metric-drive-power`` /
    ``annihilation-power-train`` calculators are the yield source).

Known-science only; no network/DB/RNG/wall-clock/numpy. Bundled illustrative defaults live in
``core.weapons_tables`` (all labelled-theoretical + overridable). The companion salvo model (W1)
is ``core.salvo``. See ``docs/integration.md`` and ``PHASE_AT_PLAN.md``.
"""

import math

import core.weapons_tables as wt
from core.equations import _C_MS
from core.relativity import compute_relativistic_energy_momentum
from core.sensing import _rayleigh_theta

_REL_BETA_THRESHOLD = 0.1     # β above which the relativistic KE/momentum form is used (W3)


# ── W2 — beam-weapon engagement ───────────────────────────────────────────────

def compute_beam_weapon_engagement(
        aperture_m=None, wavelength_m=None, frequency_hz=None, power_w=None,
        beam_quality_m2=1.0, pointing_efficiency=1.0, rayleigh_k=1.22,
        target_size_m=None, range_m=None,
        kill_fluence_jm2=None, target_material_enthalpy_jkg=None, target_areal_density_kgm2=None,
        max_dwell_s=None):
    """Directed-energy reach & lethality in the vacuum diffraction-limited regime.

    ``θ = k·M²·λ/D`` (shared ``_rayleigh_theta`` kernel); far-field spot **diameter**
    ``d_spot = 2·θ·R``. Fraction on a target of size ``s``: top-hat ``η·min(1,(s/d_spot)²)`` and a
    Gaussian encircled-energy ``η·(1−exp(−2(s/d_spot)²))``. Intensity ``I = f_on·P/A_target``
    (top-hat headline), dwell-to-kill ``t = Φ_kill/I``. Effective ranges: spot=target and (if
    ``--max-dwell-s``) the dwell limit. Echoes light-travel time R/c.
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
    if power_w is None or power_w <= 0:
        return {"error": "power_w must be > 0."}
    if beam_quality_m2 <= 0:
        return {"error": "beam_quality_m2 must be > 0."}
    if not (0.0 < pointing_efficiency <= 1.0):
        return {"error": "pointing_efficiency must be in (0, 1]."}
    if rayleigh_k <= 0:
        return {"error": "rayleigh_k must be > 0."}
    if target_size_m is None or target_size_m <= 0:
        return {"error": "target_size_m must be > 0."}
    if range_m is None or range_m <= 0:
        return {"error": "range_m must be > 0."}
    if max_dwell_s is not None and max_dwell_s <= 0:
        return {"error": "max_dwell_s must be > 0."}

    # Kill fluence: supplied directly, OR enthalpy × areal density.
    have_direct = kill_fluence_jm2 is not None
    have_material = target_material_enthalpy_jkg is not None or target_areal_density_kgm2 is not None
    if have_direct and have_material:
        return {"error": "Provide EITHER --kill-fluence-jm2 OR "
                         "--target-material-enthalpy-jkg + --target-areal-density-kgm2, not both."}
    if have_direct:
        if kill_fluence_jm2 <= 0:
            return {"error": "kill_fluence_jm2 must be > 0."}
        phi_kill = float(kill_fluence_jm2)
        phi_source = "supplied"
    elif have_material:
        if target_material_enthalpy_jkg is None or target_areal_density_kgm2 is None:
            return {"error": "Material Φ_kill needs BOTH --target-material-enthalpy-jkg and "
                             "--target-areal-density-kgm2."}
        if target_material_enthalpy_jkg <= 0 or target_areal_density_kgm2 <= 0:
            return {"error": "target_material_enthalpy_jkg and target_areal_density_kgm2 must be > 0."}
        phi_kill = target_material_enthalpy_jkg * target_areal_density_kgm2
        phi_source = "enthalpy × areal_density"
    else:
        return {"error": "Provide a kill fluence: --kill-fluence-jm2, or "
                         "--target-material-enthalpy-jkg + --target-areal-density-kgm2."}

    s = float(target_size_m)
    k_eff = rayleigh_k * beam_quality_m2
    theta = _rayleigh_theta(lam, aperture_m, k_eff)          # diffraction half-angle
    d_spot = 2.0 * theta * range_m                           # far-field spot diameter
    a_target = math.pi * (s / 2.0) ** 2

    ratio2 = (s / d_spot) ** 2
    f_tophat = pointing_efficiency * min(1.0, ratio2)
    f_encircled = pointing_efficiency * (1.0 - math.exp(-2.0 * ratio2))

    intensity = f_tophat * power_w / a_target                # W/m² (target-averaged, spec convention)
    dwell_to_kill = phi_kill / intensity if intensity > 0 else None
    a_spot = math.pi * (d_spot / 2.0) ** 2
    peak_spot_intensity = pointing_efficiency * power_w / a_spot   # η·P/A_spot (on-spot peak)

    r_spot = s / (2.0 * theta)                               # range where d_spot = s
    # t_kill floor (fully-on-target, R ≤ r_spot): I = η·P/A_target constant.
    t_kill_spot = phi_kill * a_target / (pointing_efficiency * power_w)
    r_dwell = None
    r_dwell_note = None
    if max_dwell_s is not None:
        if max_dwell_s < t_kill_spot:
            r_dwell_note = ("target un-killable within max_dwell at any range: the on-target dwell "
                            "floor t_kill_spot = %.6g s already exceeds --max-dwell-s." % t_kill_spot)
        else:
            r_dwell = r_spot * math.sqrt(max_dwell_s / t_kill_spot)

    return {
        "spot_diameter_m": d_spot,
        "frac_power_on_target_tophat": f_tophat,
        "frac_power_on_target_encircled": f_encircled,
        "intensity_on_target_wm2": intensity,
        "peak_spot_intensity_wm2": peak_spot_intensity,
        "spot_smaller_than_target": d_spot < s,
        "dwell_to_kill_s": dwell_to_kill,
        "effective_range_spot_m": r_spot,
        "effective_range_dwell_m": r_dwell,
        "effective_range_dwell_note": r_dwell_note,
        "light_travel_time_s": range_m / _C_MS,
        "kill_fluence_jm2": phi_kill,
        "kill_fluence_source": phi_source,
        "diffraction_half_angle_rad": theta,
        # resolved input echo (R3)
        "aperture_m": aperture_m, "wavelength_m": lam, "power_w": power_w,
        "beam_quality_m2": beam_quality_m2, "pointing_efficiency": pointing_efficiency,
        "rayleigh_k": rayleigh_k, "target_size_m": s, "range_m": range_m, "max_dwell_s": max_dwell_s,
        "model_note": (
            "Vacuum diffraction-limited DE weapon. θ = k·M²·λ/D (k=1.22 Rayleigh default; shared "
            "angular-resolution kernel), spot diameter d = 2θR. f_on: top-hat (geometric "
            "η·min(1,(s/d)²), the headline for I and dwell) and Gaussian encircled-energy "
            "η·(1−exp(−2(s/d)²)) with the 1/e² radius set to the spot radius (an Airy encircled figure "
            "would need Bessel J₀/J₁; the Gaussian is the standard closed-form beam-weapon model). "
            "I = f_on·P/A_target, A_target = π(s/2)²; t_kill = Φ_kill/I. R_spot = s/(2θ); the "
            "dwell-limited range scales as t_kill ∝ R² beyond R_spot. intensity_on_target_wm2 is the "
            "TARGET-AVERAGED intensity (the spec's f_on·P/A_target convention), so dwell_to_kill_s is "
            "CONSERVATIVE when the spot is smaller than the target (spot_smaller_than_target=true): the "
            "beam is actually concentrated in the spot, peak_spot_intensity_wm2 = η·P/A_spot is the real "
            "on-spot intensity (higher there, equal to the target-averaged value in the spill regime). "
            "No atmospheric blooming/turbulence (vacuum-only, per spec exclusions)."),
    }


# ── W3 — kinetic-kill ─────────────────────────────────────────────────────────

def _resolve_impactor(mass_kg, length_m, diameter_m, density_kgm3):
    """→ (mass_kg, length_m|None, diameter_m|None, density_kgm3|None, form) or {"error"}."""
    have_mass = mass_kg is not None
    have_geom = length_m is not None or diameter_m is not None or density_kgm3 is not None
    if have_mass == have_geom:
        return {"error": "Provide exactly one impactor anchor: --mass-kg, OR "
                         "--length-m + --diameter-m + --density-kgm3."}
    if have_mass:
        if mass_kg <= 0:
            return {"error": "mass_kg must be > 0."}
        return (float(mass_kg), None, None, None, "mass")
    if length_m is None or diameter_m is None or density_kgm3 is None:
        return {"error": "Rod geometry needs all of --length-m, --diameter-m, --density-kgm3."}
    if length_m <= 0 or diameter_m <= 0 or density_kgm3 <= 0:
        return {"error": "length_m, diameter_m, density_kgm3 must be > 0."}
    vol = math.pi * (diameter_m / 2.0) ** 2 * length_m
    return (density_kgm3 * vol, float(length_m), float(diameter_m), float(density_kgm3), "geometry")


def compute_kinetic_kill(
        mass_kg=None, length_m=None, diameter_m=None, density_kgm3=None,
        velocity_kms=None, beta=None,
        target_density_kgm3=None, target_type="monolithic", armor_thickness_m=None,
        bumper_areal_density_kgm2=None, standoff_m=None, rearwall_areal_density_kgm2=None,
        target_sound_speed_ms=None, crater_exponent=None, debris_cone_half_angle_deg=None):
    """Hypervelocity impactor vs armor: KE, TNT-equiv, penetration, monolithic/Whipple verdict.

    KE both classical ½mv² and relativistic (γ−1)mc² (composes relativistic-energy-momentum) with a
    regime flag at β>0.1. Penetration headline = hydrodynamic long-rod P ≈ L·√(ρ_i/ρ_t); crater form
    (labelled OOM, n≈2/3) as an alternative. Whipple shatter + rear-wall verdict (composes
    shielding-attenuation conceptually for the wall).
    """
    imp = _resolve_impactor(mass_kg, length_m, diameter_m, density_kgm3)
    if isinstance(imp, dict):
        return imp
    m, L, dia, rho_i, imp_form = imp

    if (velocity_kms is None) == (beta is None):
        return {"error": "Provide exactly one of --velocity-kms or --beta."}
    if velocity_kms is not None:
        if velocity_kms <= 0:
            return {"error": "velocity_kms must be > 0."}
        v_ms = velocity_kms * 1000.0
        b = v_ms / _C_MS
        if b >= 1.0:
            return {"error": "velocity_kms is ≥ c — supply a sublight velocity (or use --beta < 1)."}
    else:
        if not (0.0 < beta < 1.0):
            return {"error": "beta must be in (0, 1)."}
        b = float(beta)
        v_ms = b * _C_MS

    if target_density_kgm3 is None or target_density_kgm3 <= 0:
        return {"error": "target_density_kgm3 must be > 0."}
    if target_type not in ("monolithic", "whipple"):
        return {"error": "target_type must be 'monolithic' or 'whipple'."}
    if armor_thickness_m is not None and armor_thickness_m <= 0:
        return {"error": "armor_thickness_m must be > 0."}
    if target_sound_speed_ms is not None and target_sound_speed_ms <= 0:
        return {"error": "target_sound_speed_ms must be > 0."}
    n_crater = wt.CRATER_VELOCITY_EXPONENT if crater_exponent is None else float(crater_exponent)
    if n_crater <= 0:
        return {"error": "crater_exponent must be > 0."}
    cone_deg = (wt.DEBRIS_CONE_HALF_ANGLE_DEG if debris_cone_half_angle_deg is None
                else float(debris_cone_half_angle_deg))
    if not (0.0 < cone_deg < 90.0):
        return {"error": "debris_cone_half_angle_deg must be in (0, 90)."}

    # ── energy / momentum ────────────────────────────────────────────────────
    ke_classical = 0.5 * m * v_ms ** 2
    rel = compute_relativistic_energy_momentum(mass_kg=m, velocity_c=b)
    ke_relativistic = rel["kinetic_energy_j"]
    is_relativistic = b > _REL_BETA_THRESHOLD
    ke = ke_relativistic if is_relativistic else ke_classical
    momentum = rel["momentum_kgms"] if is_relativistic else m * v_ms

    # ── penetration ──────────────────────────────────────────────────────────
    regime = None
    if target_sound_speed_ms is not None:
        regime = "hydrodynamic" if v_ms > target_sound_speed_ms else "strength-dominated"
    else:
        regime = "hydrodynamic (assumed — no --target-sound-speed-ms)"
    rho_ratio = rho_i / target_density_kgm3 if rho_i is not None else None

    penetration = None
    penetration_reason = None
    if L is not None and rho_i is not None:
        penetration = L * math.sqrt(rho_ratio)              # hydrodynamic long-rod
    else:
        penetration_reason = ("hydrodynamic long-rod P = L·√(ρ_i/ρ_t) needs rod length + impactor "
                              "density — supply --length-m + --diameter-m + --density-kgm3.")
    crater_penetration = None
    crater_reason = None
    if dia is not None and rho_i is not None and target_sound_speed_ms is not None:
        if v_ms > target_sound_speed_ms:            # hypervelocity correlation domain only
            crater_penetration = dia * math.sqrt(rho_ratio) * (v_ms / target_sound_speed_ms) ** n_crater
        else:
            crater_reason = ("crater form is out of domain in the strength-dominated regime "
                             "(v ≤ target sound speed): the (v/c_t)^n hypervelocity penetration "
                             "correlation applies only above the target's bulk sound speed.")
    else:
        crater_reason = ("crater form P/d ∝ (ρ_i/ρ_t)^0.5·(v/c_t)^n needs --diameter-m, impactor "
                         "density, and --target-sound-speed-ms.")
    rel_pen_caveat = (" Penetration models are non-relativistic (hydrodynamic long-rod); at β>0.1 "
                      "they are reported for reference only." if is_relativistic else "")

    perforates = None
    if target_type == "monolithic" and armor_thickness_m is not None and penetration is not None:
        perforates = penetration > armor_thickness_m

    # ── Whipple verdict ──────────────────────────────────────────────────────
    whipple = None
    if target_type == "whipple":
        missing = [n for n, v in (("--bumper-areal-density-kgm2", bumper_areal_density_kgm2),
                                   ("--standoff-m", standoff_m),
                                   ("--rearwall-areal-density-kgm2", rearwall_areal_density_kgm2))
                   if v is None]
        if missing:
            return {"error": "Whipple target needs " + ", ".join(missing) + "."}
        if bumper_areal_density_kgm2 <= 0 or standoff_m <= 0 or rearwall_areal_density_kgm2 <= 0:
            return {"error": "bumper/standoff/rearwall values must be > 0."}
        v_kms = v_ms / 1000.0
        shattered = v_kms > wt.WHIPPLE_AL_SHATTER_KMS
        vaporized = v_kms > wt.WHIPPLE_AL_VAPORIZE_KMS
        cone = math.radians(cone_deg)
        cloud_radius = standoff_m * math.tan(cone)
        cloud_area = math.pi * cloud_radius ** 2
        cloud_areal_density = m / cloud_area if cloud_area > 0 else None
        if not shattered:
            rearwall_defeated = True     # intact hypervelocity impactor — Whipple failed to break it up
            whipple_note = ("impactor below the shatter threshold — passes the bumper intact and "
                            "defeats the rear wall (Whipple relies on fragmentation).")
        else:
            rearwall_defeated = (cloud_areal_density is not None
                                 and cloud_areal_density > rearwall_areal_density_kgm2)
            whipple_note = ("crude areal-overmatch heuristic: the fragmented debris cloud spreads to "
                            "radius standoff·tan(cone) and defeats the wall when its smeared areal "
                            "density exceeds the rear-wall areal density. A real assessment composes "
                            "shielding-attenuation (or a hydrocode) for the wall.")
        whipple = {
            "impactor_shattered": shattered,
            "impactor_vaporized": vaporized,
            "shatter_threshold_kms": wt.WHIPPLE_AL_SHATTER_KMS,
            "vaporize_threshold_kms": wt.WHIPPLE_AL_VAPORIZE_KMS,
            "threshold_source": wt.WHIPPLE_SOURCE,
            "debris_cloud_radius_m": cloud_radius,
            "debris_cloud_areal_density_kgm2": cloud_areal_density,
            "rearwall_defeated": rearwall_defeated,
            "debris_cone_half_angle_deg": cone_deg,
            "note": whipple_note,
        }

    return {
        "impactor_mass_kg": m,
        "impactor_form": imp_form,
        "velocity_kms": v_ms / 1000.0,
        "beta": b,
        "ke_classical_j": ke_classical,
        "ke_relativistic_j": ke_relativistic,
        "ke_j": ke,
        "regime": "relativistic" if is_relativistic else "classical",
        "tnt_equiv_t": ke / wt._TNT_J_PER_TON,
        "specific_energy_jkg": ke / m,
        "momentum_kgms": momentum,
        "penetration_depth_m": penetration,
        "penetration_reason": penetration_reason,
        "penetration_regime": regime,
        "crater_penetration_m": crater_penetration,
        "crater_reason": crater_reason,
        "crater_exponent": n_crater,
        "crater_source": wt.CRATER_SOURCE,
        "density_ratio": rho_ratio,
        "perforates": perforates,
        "target_type": target_type,
        "whipple": whipple,
        # resolved input echo (R3)
        "target_density_kgm3": target_density_kgm3,
        "armor_thickness_m": armor_thickness_m,
        "target_sound_speed_ms": target_sound_speed_ms,
        "model_note": (
            "KE ½mv² (classical) and (γ−1)mc² (relativistic; composes relativistic-energy-momentum), "
            "regime flag at β>0.1. TNT-equiv = KE/4.184e9 (tons). Penetration headline = hydrodynamic "
            "long-rod P = L·√(ρ_i/ρ_t); crater form P/d ∝ (ρ_i/ρ_t)^0.5·(v/c_t)^n is a labelled "
            "order-of-magnitude alternative (n≈2/3, spacecraft-shielding regime — CP2 pins it). "
            "Whipple thresholds are present-day-Al reference (override for advanced armor); the "
            "rear-wall verdict is a crude areal-overmatch heuristic (compose shielding-attenuation "
            "for a real wall calc)." + rel_pen_caveat),
    }


# ── W4 — warhead effects at standoff ──────────────────────────────────────────

def compute_warhead_effects(
        yield_j=None, yield_kt=None, warhead_type="fusion",
        f_xray=None, f_neutron=None, f_debris=None, f_gamma=None,
        standoff_m=None,
        threshold_xray_jm2=None, threshold_neutron_jm2=None,
        threshold_debris_jm2=None, threshold_gamma_jm2=None):
    """Warhead lethality radius in vacuum: per-channel inverse-square fluence + kill radius.

    Φ_i = f_i·Y/(4πR²); R_kill,i = √(f_i·Y/(4π·Φ_th,i)). No blast wave in vacuum — kill is by
    radiated/particulate fluence. Partition fractions default by --warhead-type (labelled
    illustrative, overridable per channel).
    """
    if (yield_j is None) == (yield_kt is None):
        return {"error": "Provide exactly one of --yield-j or --yield-kt."}
    if yield_j is not None:
        if yield_j <= 0:
            return {"error": "yield_j must be > 0."}
        y = float(yield_j)
    else:
        if yield_kt <= 0:
            return {"error": "yield_kt must be > 0."}
        y = yield_kt * wt._TNT_J_PER_KT
    if warhead_type not in wt.WARHEAD_PARTITIONS:
        return {"error": f"warhead_type must be one of {', '.join(wt.WARHEAD_TYPES)}."}
    if standoff_m is None or standoff_m <= 0:
        return {"error": "standoff_m must be > 0."}

    overrides = {"xray": f_xray, "neutron": f_neutron, "debris": f_debris, "gamma": f_gamma}
    defaults = wt.WARHEAD_PARTITIONS[warhead_type]
    fractions = {}
    frac_source = {}
    for ch in wt.CHANNELS:
        ov = overrides[ch]
        if ov is not None:
            if ov < 0 or ov > 1:
                return {"error": f"--f-{ch} must be in [0, 1]."}
            fractions[ch] = float(ov)
            frac_source[ch] = "override"
        else:
            fractions[ch] = defaults[ch]
            frac_source[ch] = "default"
    frac_sum = sum(fractions.values())
    if frac_sum > 1.0 + 1e-9:
        return {"error": f"partition fractions sum to {frac_sum:.4g} > 1 — reduce the overrides."}

    thresholds = {"xray": threshold_xray_jm2, "neutron": threshold_neutron_jm2,
                  "debris": threshold_debris_jm2, "gamma": threshold_gamma_jm2}
    for ch, th in thresholds.items():
        if th is not None and th <= 0:
            return {"error": f"--threshold-{ch}-jm2 must be > 0."}

    four_pi_r2 = 4.0 * math.pi * standoff_m ** 2
    channels = {}
    killed_overall = False
    binding_channel = None
    binding_radius = -1.0
    for ch in wt.CHANNELS:
        f = fractions[ch]
        th = thresholds[ch]
        if f <= 0 and th is None:
            continue                                # inactive channel, nothing to report
        fluence = f * y / four_pi_r2
        kill_radius = killed = None
        note = None
        if f <= 0:
            # a threshold was supplied for a channel this warhead type puts no energy into —
            # emit it (never silently drop the input), flagged inactive.
            note = ("yield fraction 0 for this warhead type — channel inactive; the supplied kill "
                    "threshold has no effect.")
            kill_radius = 0.0
            killed = False
        elif th is not None:
            kill_radius = math.sqrt(f * y / (4.0 * math.pi * th))
            killed = fluence >= th
            if killed:
                killed_overall = True
            if kill_radius > binding_radius:
                binding_radius = kill_radius
                binding_channel = ch
        channels[ch] = {
            "fraction": f,
            "fraction_source": frac_source[ch],
            "fluence_jm2": fluence,
            "threshold_jm2": th,
            "kill_radius_m": kill_radius,
            "killed_at_range": killed,
            "note": note,
        }

    return {
        "yield_j": y,
        "yield_kt": y / wt._TNT_J_PER_KT,
        "warhead_type": warhead_type,
        "standoff_m": standoff_m,
        "channels": channels,
        "partition_fractions": fractions,
        "partition_fraction_sum": frac_sum,
        "partition_source": wt.PARTITION_SOURCE,
        "escaping_fraction": max(0.0, 1.0 - frac_sum),
        "killed_at_range": killed_overall,
        "binding_channel": binding_channel,
        "model_note": (
            "Vacuum warhead — no blast wave; kill is by radiated/particulate fluence. "
            "Φ_i = f_i·Y/(4πR²) (inverse-square identity), R_kill,i = √(f_i·Y/(4π·Φ_th,i)). "
            "Yield Y is an INPUT (metric-drive-power / annihilation-power-train are the yield source). "
            "Partition fractions are LABELLED-ILLUSTRATIVE defaults by warhead type (see "
            "partition_source), overridable per channel; they may sum to < 1 (escaping_fraction "
            "leaves as non-lethal / neutrino radiation). Kill thresholds are the target's per-channel "
            "hardness (supplied)."),
    }
