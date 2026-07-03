"""Phase Z — rotating-structure & megastructure scale (Group H of the settlement/propulsion/
astrobiology/terraforming request; Packet 17, Settlement / Megastructure).

Three pure-math, self-validating (Phase-H/P contract) calculators for the *material* size
limit — the ceiling that pairs with ``spin-comfort`` (Phase W)'s human-comfort *minimum*:

  * ``compute_spin_stress``      (H1) — hoop stress σ=ρv² → max habitat radius for a material.
  * ``compute_tether_taper``     (H2) — Pearson uniform-stress space-elevator taper ratio.
  * ``compute_dyson_collector``  (H3) — swarm/shell area & mass to intercept a luminosity fraction.

No network, no DB, no RNG, no time. ``query.py``-only (no GUI); the ``dyson-collector --star``
name→luminosity resolution happens in the ``query.py`` handler (SIMBAD stays out of the core, like
``circumbinary-hz``). Shares ``_STANDARD_GRAVITY`` / ``_M_PER_AU`` with ``core.equations``; the
material + body tables live in ``core.materials_tables`` (isolated). Self-validating: bad input
returns a curated ``{"error": str}``.
"""

import math

from core.equations import _STANDARD_GRAVITY, _M_PER_AU
from core import materials_tables

_L_SUN_W = 3.828e26   # nominal solar luminosity, W (IAU 2015 B3)
_TAPER_OVERFLOW_EXP = 700.0   # exp() overflows ~709; a material past this can't span the well.


def _resolve_material(material, density_kgm3, tensile_strength_mpa):
    """→ (rho, sigma_mpa, flag, name) or ({"error": ...}, None, None, None)."""
    explicit = density_kgm3 is not None or tensile_strength_mpa is not None
    if material is not None and explicit:
        return {"error": "Provide either --material or explicit --density-kgm3 + "
                         "--tensile-strength-mpa, not both."}, None, None, None
    if material is not None:
        if material not in materials_tables._MATERIALS:
            return ({"error": "Unknown material '%s'. Known: %s." %
                     (material, ", ".join(sorted(materials_tables._MATERIALS)))},
                    None, None, None)
        m = materials_tables._MATERIALS[material]
        return None, m["rho"], m["sigma_mpa"], m["flag"]
    # explicit path — need both
    if density_kgm3 is None or tensile_strength_mpa is None:
        return {"error": "Provide --material, or both --density-kgm3 and "
                         "--tensile-strength-mpa."}, None, None, None
    if density_kgm3 <= 0:
        return {"error": "density_kgm3 must be > 0."}, None, None, None
    if tensile_strength_mpa <= 0:
        return {"error": "tensile_strength_mpa must be > 0."}, None, None, None
    return None, density_kgm3, tensile_strength_mpa, None


# ── H1 — spin-stress → max habitat size for a material ────────────────────────

def compute_spin_stress(material=None, density_kgm3=None, tensile_strength_mpa=None,
                        safety_factor=3.0, target_gravity_g=None, radius_m=None, rpm=None):
    """Hoop stress σ=ρv² → the max spin state a material can hold.

    Material from ``material`` (bundled) or explicit ``density_kgm3`` + ``tensile_strength_mpa``.
    ``σ_allow = σ_tensile / safety_factor``; ``v_max = √(σ_allow/ρ)``. Exactly one solve form:
    ``target_gravity_g`` → r_max = v_max²/a; ``radius_m`` alone → a_max = v_max²/r; ``rpm`` +
    ``radius_m`` → the actual hoop stress + margin.
    """
    err, rho, sigma_mpa, flag = _resolve_material(material, density_kgm3, tensile_strength_mpa)
    if err:
        return err
    if safety_factor < 1:
        return {"error": "safety_factor must be ≥ 1."}

    # ── solve form: exactly one of {target}, {radius}, {rpm+radius} ──
    have_target = target_gravity_g is not None
    have_radius = radius_m is not None
    have_rpm = rpm is not None
    if have_rpm:
        if not have_radius or have_target:
            return {"error": "For the hoop-stress form provide --rpm with --radius-m "
                             "(and not --target-gravity-g)."}
        form = "rpm"
    elif have_target:
        if have_radius:
            return {"error": "Provide only one solve form: --target-gravity-g OR --radius-m "
                             "OR --rpm+--radius-m."}
        form = "target"
    elif have_radius:
        form = "radius"
    else:
        return {"error": "Provide one solve form: --target-gravity-g, --radius-m, "
                         "or --rpm with --radius-m."}
    if have_target and target_gravity_g <= 0:
        return {"error": "target_gravity_g must be > 0."}
    if have_radius and radius_m <= 0:
        return {"error": "radius_m must be > 0."}
    if have_rpm and rpm <= 0:
        return {"error": "rpm must be > 0."}

    sigma_allow_pa = sigma_mpa * 1e6 / safety_factor
    v_max = math.sqrt(sigma_allow_pa / rho)

    max_radius_m = max_radius_km = max_gravity_g = hoop_stress_mpa = margin = None
    if form == "target":
        a = target_gravity_g * _STANDARD_GRAVITY
        max_radius_m = v_max ** 2 / a
        max_radius_km = max_radius_m / 1000.0
    elif form == "radius":
        a_max = v_max ** 2 / radius_m
        max_gravity_g = a_max / _STANDARD_GRAVITY
    else:  # rpm — actual hoop stress at this spin state
        omega = rpm * 2.0 * math.pi / 60.0
        v = omega * radius_m
        sigma_actual_pa = rho * v * v
        hoop_stress_mpa = sigma_actual_pa / 1e6
        margin = sigma_allow_pa / sigma_actual_pa if sigma_actual_pa > 0 else None

    notes = []
    if flag:
        notes.append(flag)

    return {
        "material": material,
        "density_kgm3": rho,
        "tensile_strength_mpa": sigma_mpa,
        "safety_factor": safety_factor,
        "allowable_stress_mpa": sigma_allow_pa / 1e6,
        "max_tangential_velocity_ms": v_max,
        "target_gravity_g": target_gravity_g,
        "radius_m": radius_m,
        "rpm": rpm,
        "max_radius_m": max_radius_m,
        "max_radius_km": max_radius_km,
        "max_gravity_g": max_gravity_g,
        "hoop_stress_mpa": hoop_stress_mpa,
        "margin": margin,
        "specific_strength_note": (
            "specific strength σ/ρ = v_max² (%.1f (m/s)²·… ≡ J/kg) is the sole figure of merit; "
            "independent of shell thickness for a thin shell." % (v_max ** 2)),
        "notes": notes,
        "model_note": materials_tables._MODEL_NOTE,
    }


# ── H2 — tether-taper → space-elevator taper ratio ───────────────────────────

def compute_tether_taper(material=None, density_kgm3=None, tensile_strength_mpa=None,
                         body=None, surface_gravity_ms2=None, surface_radius_km=None,
                         geo_radius_km=None, safety_factor=3.0):
    """Pearson uniform-constant-stress space-elevator taper ratio.

    Taper T = exp[(ρ·g₀/σ_allow)·(R − 1.5·R²/R_s + 0.5·R⁴/R_s³)] (the synchronous-orbit ω is
    Kepler-derived from R/R_s, so it cancels the explicit rotation term). Body from a bundled
    ``body`` (earth/mars/moon/ceres) or explicit ``surface_gravity_ms2`` + ``surface_radius_km`` +
    ``geo_radius_km``. Feasibility band: taper ≲2 practical, ≫10 impractical; a material that can't
    span the well overflows → ``taper_ratio=null``, ``feasible=False``.
    """
    err, rho, sigma_mpa, flag = _resolve_material(material, density_kgm3, tensile_strength_mpa)
    if err:
        return err
    if safety_factor < 1:
        return {"error": "safety_factor must be ≥ 1."}

    # ── body params: bundled OR explicit (g0 + surface radius + geo radius) ──
    explicit = (surface_gravity_ms2 is not None or surface_radius_km is not None
                or geo_radius_km is not None)
    body_note = None
    if body is not None and explicit:
        return {"error": "Provide either --body or explicit --surface-gravity-ms2 + "
                         "--surface-radius-km + --geo-radius-km, not both."}
    if body is not None:
        if body not in materials_tables._BODIES:
            return {"error": "Unknown body '%s'. Known: %s." %
                    (body, ", ".join(sorted(materials_tables._BODIES)))}
        b = materials_tables._BODIES[body]
        g0, R_km, Rs_km, body_note = b["g0"], b["R_km"], b["Rs_km"], b["note"]
    else:
        if surface_gravity_ms2 is None or surface_radius_km is None or geo_radius_km is None:
            return {"error": "Provide --body, or all of --surface-gravity-ms2, "
                             "--surface-radius-km, --geo-radius-km."}
        g0, R_km, Rs_km = surface_gravity_ms2, surface_radius_km, geo_radius_km
    if g0 <= 0:
        return {"error": "surface_gravity_ms2 must be > 0."}
    if R_km <= 0 or Rs_km <= 0:
        return {"error": "surface_radius_km and geo_radius_km must be > 0."}
    if Rs_km <= R_km:
        return {"error": "geo_radius_km must exceed surface_radius_km."}

    R = R_km * 1000.0
    Rs = Rs_km * 1000.0
    sigma_allow_pa = sigma_mpa * 1e6 / safety_factor
    characteristic_velocity_ms = math.sqrt(sigma_allow_pa / rho)
    L_c = sigma_allow_pa / (rho * g0)                      # characteristic (breaking) length, m
    K = R - 1.5 * R ** 2 / Rs + 0.5 * R ** 4 / Rs ** 3     # Pearson well integral (g0 cancels)
    exponent = K / L_c

    notes = []
    if flag:
        notes.append(flag)
    if body_note:
        notes.append(body_note)

    if exponent > _TAPER_OVERFLOW_EXP:
        taper_ratio = None
        feasible = False
        notes.append("taper ratio overflows (→ ∞): the material cannot span the gravity well "
                     "at this stress — a space elevator is infeasible for it.")
    else:
        taper_ratio = math.exp(exponent)
        feasible = taper_ratio <= 10.0
        if not feasible:
            notes.append("taper ratio ≫ 10 — impractical (a practical elevator wants ≲2).")

    return {
        "material": material,
        "density_kgm3": rho,
        "tensile_strength_mpa": sigma_mpa,
        "safety_factor": safety_factor,
        "body": body,
        "surface_gravity_ms2": g0,
        "surface_radius_km": R_km,
        "geo_radius_km": Rs_km,
        "characteristic_velocity_ms": characteristic_velocity_ms,
        "characteristic_length_km": L_c / 1000.0,
        "taper_ratio": taper_ratio,
        "feasible": feasible,
        "notes": notes,
        "model_note": materials_tables._MODEL_NOTE,
    }


# ── H3 — dyson-collector → area & mass to intercept a luminosity fraction ─────

def compute_dyson_collector(luminosity_lsun=None, fraction=None, orbit_au=None,
                            areal_mass_kgm2=0.01):
    """Collector area/mass to intercept a fraction ``f`` of a star's luminosity at ``orbit_au``.

    ``P = f·L``; area ``A = f·4πR²`` (R = orbit radius); mass ``= A·areal_mass``; incident flux
    ``= L/(4πR²)``. ``luminosity_lsun`` is resolved from ``--star`` in the query.py handler.
    """
    if luminosity_lsun is None or luminosity_lsun <= 0:
        return {"error": "luminosity_lsun must be > 0."}
    if fraction is None or not (0.0 < fraction <= 1.0):
        return {"error": "fraction must be in (0, 1]."}
    if orbit_au is None or orbit_au <= 0:
        return {"error": "orbit_au must be > 0."}
    if areal_mass_kgm2 is None or areal_mass_kgm2 <= 0:
        return {"error": "areal_mass_kgm2 must be > 0."}

    L_w = luminosity_lsun * _L_SUN_W
    R_m = orbit_au * _M_PER_AU
    sphere_area = 4.0 * math.pi * R_m ** 2
    intercepted_power_w = fraction * L_w
    collector_area_m2 = fraction * sphere_area
    collector_mass_kg = collector_area_m2 * areal_mass_kgm2
    incident_flux_wm2 = L_w / sphere_area
    collector_area_au2 = collector_area_m2 / (_M_PER_AU ** 2)

    return {
        "intercepted_power_w": intercepted_power_w,
        "collector_area_m2": collector_area_m2,
        "collector_area_au2": collector_area_au2,
        "collector_mass_kg": collector_mass_kg,
        "incident_flux_wm2": incident_flux_wm2,
        "fraction": fraction,
        "orbit_au": orbit_au,
        "luminosity_lsun": luminosity_lsun,
        "areal_mass_kgm2": areal_mass_kgm2,
        "model_note": materials_tables._MODEL_NOTE,
    }
