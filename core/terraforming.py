"""Phase AB — planetary energy balance / terraforming (Group J of the combined
settlement / propulsion / astrobiology / terraforming request; Packet 19).

Three pure-math, self-validating (Phase-H/P contract) ``query.py``-only calculators
modelling the *radiative / mass balance* of terraforming feasibility — the demand
side only (volatile *supply* is the volatile-geography canon's authority):

  * ``compute_equilibrium_temp``  (J1) — planetary equilibrium temperature + a
    greenhouse-forcing surface temperature (offset OR grey-atmosphere), with an
    inverse (target surface temp → required forcing).
  * ``compute_insolation_shift``  (J2) — orbital mirror / shade area for a
    sphere-averaged flux change.
  * ``compute_atmosphere_mass``   (J3) — hydrostatic atmosphere mass for a surface
    pressure (and the inverse).

No network, no DB, no RNG, no time. The physics is durable textbook closed form
(``T_eq=[S(1−A)/4σ]^¼``, grey-atmosphere greenhouse, hydrostatic ``m=4πR²P/g``);
present-day albedos are overridable ancestors. All constants are reused from
``core.equations`` (single source of truth); the one fixed reference below is inline.
"""

import math

from core.equations import (
    _STEFAN_BOLTZMANN,
    _M_PER_AU,
    _G,
    _EARTH_MASS_KG,
    _SOLAR_LUMINOSITY_W,
)

# Earth's total atmospheric mass, kg — the reference for the
# ``atmosphere_mass_earth_atm`` fraction only (Trenberth & Smith 2005; the widely
# quoted 5.15e18 kg). Inline (a single fixed reference, not a table).
_EARTH_ATM_MASS_KG = 5.15e18

_PA_PER_BAR = 1.0e5   # 1 bar ≡ 10⁵ Pa (exact, by definition)

_GREY_MODEL_NOTE = (
    "T_eq = [S(1−A)/(4σ)]^¼ (planetary equilibrium). Surface temperature via one "
    "greenhouse form: a simple additive offset T_s = T_eq + ΔT_greenhouse, or the "
    "grey-atmosphere form T_s = T_eq·(1 + ¾τ)^¼ (τ = IR optical depth). The two "
    "differ: for Earth (T_eq≈255 K) the +33 K offset and τ≈0.85 both reach 288 K, "
    "but they diverge away from that anchor. Present-day albedos are overridable "
    "ancestors; this is the demand-side radiative balance only."
)


def _solar_flux(insolation_wm2, luminosity_lsun, distance_au):
    """Resolve exactly one insolation/solar-flux source → {"S": float} or error.

    Direct ``insolation_wm2``, or ``luminosity_lsun`` + ``distance_au`` via
    ``S = L_sun·L / (4π(d·AU)²)`` (1 L☉ @ 1 AU ≈ 1361 W/m²; the shared Phase-AA
    expression).
    """
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
    return {"S": _SOLAR_LUMINOSITY_W * luminosity_lsun / (4.0 * math.pi * d_m * d_m)}


# ── J1 — equilibrium / greenhouse-offset temperature ─────────────────────────

def compute_equilibrium_temp(insolation_wm2=None, luminosity_lsun=None,
                             distance_au=None, albedo=0.3, greenhouse_delta_k=None,
                             optical_depth=None, target_surface_k=None):
    """Planetary equilibrium temperature + a greenhouse surface temperature.

    Insolation — exactly one source (``insolation_wm2`` OR
    ``luminosity_lsun`` + ``distance_au``). Forcing — **at most one** form:
    ``greenhouse_delta_k`` (additive offset), ``optical_depth`` (grey-atmosphere),
    or ``target_surface_k`` (inverse → the ΔT and τ required to reach it). With
    **no** forcing form the result is the bare airless equilibrium
    (``t_surface_k = t_eq_k``, ``regime = "airless"``).
    """
    if albedo is None or albedo < 0 or albedo >= 1:
        return {"error": "albedo must be in [0, 1)."}

    forcing_forms = [greenhouse_delta_k is not None, optical_depth is not None,
                     target_surface_k is not None]
    if sum(forcing_forms) > 1:
        return {"error": "Provide at most one forcing form: greenhouse_delta_k, "
                         "optical_depth, or target_surface_k."}

    sf = _solar_flux(insolation_wm2, luminosity_lsun, distance_au)
    if "error" in sf:
        return sf
    S = sf["S"]

    t_eq = (S * (1.0 - albedo) / (4.0 * _STEFAN_BOLTZMANN)) ** 0.25

    out = {
        "insolation_wm2": S,
        "albedo": float(albedo),
        "t_eq_k": t_eq,
        "greenhouse_delta_k": None,
        "optical_depth": None,
        "t_surface_k": None,
        "required_forcing": None,
        "regime": None,
        "model_note": _GREY_MODEL_NOTE,
    }

    if greenhouse_delta_k is not None:
        out["regime"] = "offset"
        out["greenhouse_delta_k"] = float(greenhouse_delta_k)
        out["t_surface_k"] = t_eq + greenhouse_delta_k
    elif optical_depth is not None:
        if optical_depth < 0:
            return {"error": "optical_depth must be >= 0."}
        out["regime"] = "grey"
        out["optical_depth"] = float(optical_depth)
        out["t_surface_k"] = t_eq * (1.0 + 0.75 * optical_depth) ** 0.25
    elif target_surface_k is not None:  # inverse
        if target_surface_k <= 0:
            return {"error": "target_surface_k must be > 0."}
        out["regime"] = "inverse"
        req_delta = target_surface_k - t_eq
        # τ from the grey form: (T_s/T_eq)^4 = 1 + ¾τ  →  τ = ((T_s/T_eq)^4 − 1)/¾
        req_tau = ((target_surface_k / t_eq) ** 4 - 1.0) / 0.75
        out["t_surface_k"] = float(target_surface_k)
        out["required_forcing"] = {
            "greenhouse_delta_k": req_delta,
            "optical_depth": req_tau,
            # A target cooler than the bare equilibrium needs cooling, not
            # greenhouse — both required values go negative to signal it.
            "cooling_required": req_delta < 0,
        }
    else:  # no forcing form → bare airless equilibrium
        out["regime"] = "airless"
        out["t_surface_k"] = t_eq

    return out


# ── J2 — orbital mirror / shade area for a flux change ───────────────────────

def compute_insolation_shift(planet_radius_km, delta_insolation_wm2,
                             solar_flux_wm2=None, luminosity_lsun=None,
                             distance_au=None):
    """Orbital mirror (warm) / shade (cool) area to change the sphere-averaged flux.

    A_m = |ΔS|·4πR_p² / solar_flux_at_planet. Signed ΔS: + = mirror, − = shade.
    """
    if planet_radius_km is None or planet_radius_km <= 0:
        return {"error": "planet_radius_km must be > 0."}
    if delta_insolation_wm2 is None or delta_insolation_wm2 == 0:
        return {"error": "delta_insolation_wm2 must be non-zero (a signed flux change)."}

    sf = _solar_flux(solar_flux_wm2, luminosity_lsun, distance_au)
    if "error" in sf:
        # Re-word the source message for this subcommand's flag name.
        if "exactly one insolation source" in sf["error"]:
            return {"error": "Provide exactly one solar-flux source: solar_flux_wm2, "
                             "or luminosity_lsun + distance_au."}
        return sf
    solar_flux = sf["S"]

    r_m = planet_radius_km * 1000.0
    sphere_area = 4.0 * math.pi * r_m * r_m
    cross_section = math.pi * r_m * r_m
    mirror_area_m2 = abs(delta_insolation_wm2) * sphere_area / solar_flux

    return {
        "planet_radius_km": float(planet_radius_km),
        "delta_insolation_wm2": float(delta_insolation_wm2),
        "solar_flux_wm2": solar_flux,
        "mode": "mirror" if delta_insolation_wm2 > 0 else "shade",
        "mirror_area_m2": mirror_area_m2,
        "mirror_area_km2": mirror_area_m2 / 1.0e6,
        "area_vs_planet_cross_section": mirror_area_m2 / cross_section,
        "model_note": (
            "Mirror/shade at the planet's orbit redirecting a sphere-averaged flux "
            "change ΔS: A_m = |ΔS|·4πR_p² / solar_flux. Positive ΔS warms (mirror), "
            "negative cools (shade/soletta). First-order area only — pointing, "
            "station-keeping, mirror efficiency and finite-figure losses are out of scope."
        ),
    }


# ── J3 — hydrostatic atmosphere mass for a surface pressure ──────────────────

_SPECIES_CHOICES = ("n2", "co2", "o2", "h2o")


def compute_atmosphere_mass(planet_radius_km, surface_gravity_ms2=None,
                            planet_mass_earth=None, pressure_bar=None,
                            volatile_mass_kg=None, species=None):
    """Hydrostatic atmosphere mass ↔ surface pressure: m = 4πR²·P / g.

    Gravity — exactly one source (``surface_gravity_ms2`` OR ``planet_mass_earth``
    → g = GM/R²). Then exactly one of ``pressure_bar`` (→ mass) or
    ``volatile_mass_kg`` (→ pressure). ``species`` is an optional echoed label.
    """
    if planet_radius_km is None or planet_radius_km <= 0:
        return {"error": "planet_radius_km must be > 0."}
    if species is not None and species not in _SPECIES_CHOICES:
        return {"error": f"species must be one of {', '.join(_SPECIES_CHOICES)}."}

    # ── gravity source ──
    if (surface_gravity_ms2 is None) == (planet_mass_earth is None):
        return {"error": "Provide exactly one gravity source: surface_gravity_ms2 "
                         "or planet_mass_earth."}
    r_m = planet_radius_km * 1000.0
    if surface_gravity_ms2 is not None:
        if surface_gravity_ms2 <= 0:
            return {"error": "surface_gravity_ms2 must be > 0."}
        g = float(surface_gravity_ms2)
    else:
        if planet_mass_earth <= 0:
            return {"error": "planet_mass_earth must be > 0."}
        g = _G * (planet_mass_earth * _EARTH_MASS_KG) / (r_m * r_m)

    # ── pressure OR mass ──
    if (pressure_bar is None) == (volatile_mass_kg is None):
        return {"error": "Provide exactly one of pressure_bar or volatile_mass_kg."}
    sphere_area = 4.0 * math.pi * r_m * r_m
    if pressure_bar is not None:
        if pressure_bar <= 0:
            return {"error": "pressure_bar must be > 0."}
        p_pa = pressure_bar * _PA_PER_BAR
        mass_kg = sphere_area * p_pa / g
        pressure_bar_out = float(pressure_bar)
    else:
        if volatile_mass_kg <= 0:
            return {"error": "volatile_mass_kg must be > 0."}
        mass_kg = float(volatile_mass_kg)
        p_pa = mass_kg * g / sphere_area
        pressure_bar_out = p_pa / _PA_PER_BAR

    return {
        "planet_radius_km": float(planet_radius_km),
        "surface_gravity_ms2": g,
        "species": species,
        "surface_pressure_bar": pressure_bar_out,
        "atmosphere_mass_kg": mass_kg,
        "atmosphere_mass_earth_atm": mass_kg / _EARTH_ATM_MASS_KG,
        "model_note": (
            "Hydrostatic column mass m = 4πR²·P/g (1 bar = 1e5 Pa); the fraction "
            "is vs Earth's 5.15e18 kg. Reports volatile demand only — whether that "
            "mass is accessibly available is the volatile-geography canon's authority. "
            "'species' is an echoed label; the total column mass is species-independent."
        ),
    }
