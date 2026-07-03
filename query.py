"""query.py — JSON dispatcher for SpaceAndScienceFictionApp core functions.

Usage:
    python query.py <subcommand> [arguments]

Prints JSON to stdout. Exits 0 on success, 1 on error.
"""

import argparse
import json
import sys

import core.calculators as calculators
import core.cooling as cooling
import core.databases as databases
import core.dust as dust
import core.dust_routing as dust_routing
import core.equations as equations
import core.feasibility as feasibility
import core.generate as generate
import core.ism_drag as ism_drag
import core.life_support as life_support
import core.megastructure as megastructure
import core.par_flux as par_flux
import core.projects as projects
import core.propulsion as propulsion
import core.regions as regions
import core.report as report
import core.science as science
import core.spin as spin
import core.terraforming as terraforming
import core.thermal as thermal


def _out(result):
    """Serialize result to stdout and exit with the appropriate code."""
    print(json.dumps(result, indent=2, default=str))
    if isinstance(result, dict) and "error" in result:
        sys.exit(1)
    sys.exit(0)


def _simbad_then(star, fn, **kwargs):
    """Run SIMBAD lookup and pass the result to fn; return early on error."""
    simbad_result = databases.compute_simbad_lookup(star)
    if "error" in simbad_result:
        return simbad_result
    return fn(simbad_result, **kwargs)


# ── Subcommand handlers ───────────────────────────────────────────────────────

def cmd_simbad_lookup(args):
    _out(databases.compute_simbad_lookup(args.star))


def cmd_star_regions(args):
    simbad = databases.compute_simbad_lookup(args.star)
    if "error" in simbad:
        _out(simbad)
        return
    result = regions.compute_star_system_regions_from_simbad(simbad)
    if "error" not in result:
        result["hypatia"] = databases.compute_hypatia_data(simbad)
    _out(result)


def cmd_star_regions_manual(args):
    _out(regions.compute_star_system_regions(
        args.vmag, args.bc, args.teff, args.parallax,
        sunlight_intensity=args.sunlight_intensity, bond_albedo=args.bond_albedo,
    ))


def cmd_distance(args):
    _out(calculators.compute_distance_between_stars(args.star1, args.star2))


def cmd_stars_within_sol(args):
    _out(calculators.compute_stars_within_distance_of_sol(args.ly))


def cmd_stars_within_star(args):
    _out(calculators.compute_stars_within_distance_of_star(args.star, args.ly))


def cmd_travel_time(args):
    ly_hr   = args.ly_hr   if hasattr(args, "ly_hr")   else None
    times_c = args.times_c if hasattr(args, "times_c") else None
    _out(calculators.compute_travel_time_between_stars(
        args.star1, args.star2, ly_hr=ly_hr, times_c=times_c
    ))


def cmd_habitable_zone(args):
    _out(equations.compute_habitable_zone(args.teff, args.luminosity))


def cmd_exoplanets(args):
    _out(_simbad_then(args.star, databases.compute_exoplanet_archive))


def cmd_planetary_systems(args):
    _out(_simbad_then(args.star, databases.compute_planetary_systems_composite))


def cmd_hwo_exep(args):
    _out(_simbad_then(args.star, databases.compute_hwo_exep))


def cmd_mission_exocat(args):
    _out(_simbad_then(args.star, databases.compute_mission_exocat))


def cmd_hwc(args):
    _out(_simbad_then(args.star, databases.compute_hwc))


def cmd_hypatia_data(args):
    _out(_simbad_then(args.star, databases.compute_hypatia_data))


def cmd_gcns_within_sol(args):
    _out(databases.compute_gcns_within_sol(
        args.ly, wd_prob_min=args.wd_prob_min, wd_prob_max=args.wd_prob_max,
    ))


def cmd_gcns_source(args):
    _out(databases.compute_gcns_by_source_id(args.id))


def cmd_gcns_system(args):
    _out(databases.compute_gcns_system(args.id))


def cmd_gcns_distance(args):
    _out(databases.compute_gcns_distance(
        star1=args.star1, id1=args.id1, star2=args.star2, id2=args.id2
    ))


def cmd_gcns_travel_time(args):
    _out(databases.compute_gcns_travel_time(
        star1=args.star1, id1=args.id1, star2=args.star2, id2=args.id2,
        ly_hr=args.ly_hr, times_c=args.times_c,
    ))


def cmd_gcns_stars_within_star(args):
    _out(databases.compute_gcns_stars_within_star(
        star=args.star, source_id=args.id, limit_ly=args.ly
    ))


# ── Worldbuilding calculators (Phase H) ───────────────────────────────────────

def cmd_roche_limit(args):
    _out(equations.compute_roche_limit(
        args.primary_mass_earth, args.satellite_density,
        primary_radius_earth=args.primary_radius_earth,
    ))


def cmd_tidal_locking(args):
    _out(equations.compute_tidal_locking_time(
        args.primary_mass_earth, args.satellite_mass_earth,
        args.sma_km, args.rotation_hours,
        rigidity_pa=args.rigidity_pa, tidal_q=args.tidal_q,
    ))


def cmd_hill_sphere(args):
    _out(equations.compute_hill_sphere(
        args.star_mass_solar, args.planet_mass_earth, args.sma_au,
        eccentricity=args.eccentricity,
        moon_inclination_deg=args.moon_inclination_deg, prograde=not args.retrograde,
    ))


def cmd_binary_stability(args):
    _out(equations.compute_binary_orbit_stability(
        args.mass1_solar, args.mass2_solar, args.binary_sma_au, args.test_sma_au,
        eccentricity=args.eccentricity,
    ))


def cmd_atmosphere_retention(args):
    _out(equations.compute_atmosphere_retention(
        args.planet_mass_earth, args.planet_radius_earth, args.temperature_k,
    ))


# ── Phase T1a — research-tooling extensions (self-validating, Phase-H/P) ───────

def cmd_trojan_stability(args):
    _out(feasibility.gascheau_coorbital_stable(
        args.host_mass_earth, args.companion_mass_earth, args.star_mass_solar,
    ))


def cmd_lorentz_factor(args):
    _out(calculators.compute_lorentz_factor(args.velocity_c))


def _resolve_star_teff_lum(name):
    """Resolve a star name → (teff, bolometric luminosity) via SIMBAD + regions.

    Returns {"teff": float, "lum": float} or {"error": str}. Reuses the same
    derivation as the Star System Regions feature (works for any main-sequence type).
    """
    simbad = databases.compute_simbad_lookup(name)
    if "error" in simbad:
        return simbad
    reg = regions.compute_star_system_regions_from_simbad(simbad)
    if "error" in reg:
        return reg
    teff = reg.get("temp")
    lum = reg.get("bcLuminosity")
    if teff is None or lum is None:
        return {"error": f"Could not derive temperature/luminosity for '{name}'."}
    return {"teff": teff, "lum": lum}


def cmd_circumbinary_hz(args):
    numeric = [args.teff1, args.lum1, args.teff2, args.lum2]
    any_numeric = any(v is not None for v in numeric)
    all_numeric = all(v is not None for v in numeric)
    any_star = bool(args.star1) or bool(args.star2)
    both_star = bool(args.star1) and bool(args.star2)

    if any_star and any_numeric:
        sys.stderr.write("error: provide either --teff1/--lum1/--teff2/--lum2 OR "
                         "--star1/--star2, not both\n")
        sys.exit(2)
    if both_star:
        r1 = _resolve_star_teff_lum(args.star1)
        if "error" in r1:
            _out(r1)
            return
        r2 = _resolve_star_teff_lum(args.star2)
        if "error" in r2:
            _out(r2)
            return
        _out(equations.compute_circumbinary_hz(r1["teff"], r1["lum"], r2["teff"], r2["lum"]))
        return
    if all_numeric:
        _out(equations.compute_circumbinary_hz(args.teff1, args.lum1, args.teff2, args.lum2))
        return
    sys.stderr.write("error: provide all of --teff1/--lum1/--teff2/--lum2, "
                     "or both --star1 and --star2\n")
    sys.exit(2)


def cmd_cooling_hz(args):
    _out(cooling.compute_cooling_hz(
        args.track,
        mass_solar=args.mass_solar, mass_mjup=args.mass_mjup,
        cooling_age_gyr=args.cooling_age_gyr, teff=args.teff, sma_au=args.sma_au,
        chz_threshold_gyr=args.chz_threshold_gyr, hz_edge=args.hz_edge,
        age_max_gyr=args.age_max_gyr, satellite_density=args.satellite_density,
    ))


# ── Phase V — power / thermal / shielding calculators ─────────────────────────

def cmd_waste_heat(args):
    _out(thermal.compute_waste_heat(
        input_power_watts=args.input_power_watts,
        useful_power_watts=args.useful_power_watts,
        efficiency=args.efficiency,
        hot_temp_k=args.hot_temp_k, cold_temp_k=args.cold_temp_k,
    ))


def cmd_radiator_area(args):
    _out(thermal.compute_radiator_area(
        heat_watts=args.heat_watts,
        input_power_watts=args.input_power_watts, efficiency=args.efficiency,
        radiator_temp_k=args.radiator_temp_k, emissivity=args.emissivity,
        sides=args.sides, sink_temp_k=args.sink_temp_k,
        areal_mass_kgm2=args.areal_mass_kgm2,
    ))


def cmd_shielding_attenuation(args):
    _out(thermal.compute_shielding_attenuation(
        areal_density_gcm2=args.areal_density_gcm2,
        thickness_cm=args.thickness_cm, density_gcm3=args.density_gcm3,
        mass_atten_coeff_cm2g=args.mass_atten_coeff_cm2g,
        attenuation_length_gcm2=args.attenuation_length_gcm2,
        material=args.material, energy_mev=args.energy_mev, mode=args.mode,
    ))


# ── Phase Y — STL mission energetics (Group G) ────────────────────────────────

def cmd_rocket_equation(args):
    _out(propulsion.compute_rocket_equation(
        delta_v_kms=args.delta_v_kms, beta=args.beta,
        exhaust_velocity_kms=args.exhaust_velocity_kms, isp_s=args.isp_s, fuel=args.fuel,
        mass_ratio=args.mass_ratio, relativistic=args.relativistic, legs=args.legs,
        payload_mass_t=args.payload_mass_t, structure_fraction=args.structure_fraction,
    ))


def cmd_beam_sail(args):
    _out(propulsion.compute_beam_sail(
        beam_power_w=args.beam_power_w, sail_area_m2=args.sail_area_m2,
        areal_mass_gm2=args.areal_mass_gm2, sail_mass_kg=args.sail_mass_kg,
        payload_mass_kg=args.payload_mass_kg, reflectivity=args.reflectivity,
        wavelength_nm=args.wavelength_nm, transmit_aperture_m=args.transmit_aperture_m,
        accel_distance_au=args.accel_distance_au, accel_time_days=args.accel_time_days,
    ))


# ── Phase AC — ISM-drag / magnetic-sail calculators (Group K) ─────────────────

def cmd_magsail(args):
    _out(ism_drag.compute_magsail(
        ism_density_cm3=args.ism_density_cm3, ion_mass_amu=args.ion_mass_amu,
        velocity_kms=args.velocity_kms, beta=args.beta,
        coil_current_a=args.coil_current_a, coil_radius_m=args.coil_radius_m,
        magnetic_moment_am2=args.magnetic_moment_am2,
        standoff_coeff=args.standoff_coeff, drag_coeff=args.drag_coeff,
        vehicle_mass_t=args.vehicle_mass_t, velocity_final_kms=args.velocity_final_kms,
    ))


def cmd_ramscoop(args):
    _out(ism_drag.compute_ramscoop(
        ism_density_cm3=args.ism_density_cm3, ion_mass_amu=args.ion_mass_amu,
        velocity_kms=args.velocity_kms, beta=args.beta,
        coil_current_a=args.coil_current_a, coil_radius_m=args.coil_radius_m,
        scoop_area_km2=args.scoop_area_km2, magnetic_moment_am2=args.magnetic_moment_am2,
        fuel=args.fuel, fusion_efficiency=args.fusion_efficiency,
        exhaust_velocity_kms=args.exhaust_velocity_kms,
        standoff_coeff=args.standoff_coeff, drag_coeff=args.drag_coeff,
    ))


# ── Phase Z — rotating-structure & megastructure scale (Group H) ──────────────

def cmd_spin_stress(args):
    _out(megastructure.compute_spin_stress(
        material=args.material, density_kgm3=args.density_kgm3,
        tensile_strength_mpa=args.tensile_strength_mpa, safety_factor=args.safety_factor,
        target_gravity_g=args.target_gravity_g, radius_m=args.radius_m, rpm=args.rpm,
    ))


def cmd_tether_taper(args):
    _out(megastructure.compute_tether_taper(
        material=args.material, density_kgm3=args.density_kgm3,
        tensile_strength_mpa=args.tensile_strength_mpa, safety_factor=args.safety_factor,
        body=args.body, surface_gravity_ms2=args.surface_gravity_ms2,
        surface_radius_km=args.surface_radius_km, geo_radius_km=args.geo_radius_km,
    ))


def cmd_dyson_collector(args):
    lum = args.luminosity_lsun
    if args.star:
        resolved = _resolve_star_teff_lum(args.star)   # SIMBAD + regions (like circumbinary-hz)
        if "error" in resolved:
            _out(resolved)
        lum = resolved["lum"]
    _out(megastructure.compute_dyson_collector(
        luminosity_lsun=lum, fraction=args.fraction, orbit_au=args.orbit_au,
        areal_mass_kgm2=args.areal_mass_kgm2,
    ))


# ── Phase AA — PAR / photosynthesis by stellar type ───────────────────────────

def cmd_par_flux(args):
    # Teff (teff_k/spectral_type/star) and insolation source resolution both
    # happen inside the core (curated exit-1 on 0/2+ sources); --star is the
    # only networked path (SIMBAD, resolved lazily in core.par_flux).
    _out(par_flux.compute_par_flux(
        teff_k=args.teff_k, spectral_type=args.spectral_type, star=args.star,
        insolation_wm2=args.insolation_wm2, luminosity_lsun=args.luminosity_lsun,
        distance_au=args.distance_au, par_band_nm=tuple(args.par_band_nm),
    ))


# ── Phase AB — planetary energy balance / terraforming ────────────────────────

def cmd_equilibrium_temp(args):
    _out(terraforming.compute_equilibrium_temp(
        insolation_wm2=args.insolation_wm2, luminosity_lsun=args.luminosity_lsun,
        distance_au=args.distance_au, albedo=args.albedo,
        greenhouse_delta_k=args.greenhouse_delta_k, optical_depth=args.optical_depth,
        target_surface_k=args.target_surface_k,
    ))


def cmd_insolation_shift(args):
    _out(terraforming.compute_insolation_shift(
        planet_radius_km=args.planet_radius_km,
        delta_insolation_wm2=args.delta_insolation_wm2,
        solar_flux_wm2=args.solar_flux_wm2, luminosity_lsun=args.luminosity_lsun,
        distance_au=args.distance_au,
    ))


def cmd_atmosphere_mass(args):
    _out(terraforming.compute_atmosphere_mass(
        planet_radius_km=args.planet_radius_km,
        surface_gravity_ms2=args.surface_gravity_ms2,
        planet_mass_earth=args.planet_mass_earth, pressure_bar=args.pressure_bar,
        volatile_mass_kg=args.volatile_mass_kg, species=args.species,
    ))


# ── Phase T1b — detectability / exomoon / triple / relativistic calculators ───

def cmd_rv_semi_amplitude(args):
    _out(calculators.compute_rv_semi_amplitude(
        args.planet_mass_earth, args.star_mass_solar,
        period_days=args.period_days, sma_au=args.sma_au,
        ecc=args.ecc, inclination_deg=args.inclination_deg,
    ))


def cmd_transit_signal(args):
    _out(calculators.compute_transit_signal(
        args.planet_radius_earth, args.star_radius_solar,
        sma_au=args.sma_au, period_days=args.period_days,
        star_mass_solar=args.star_mass_solar,
    ))


def cmd_astrometric_signal(args):
    _out(calculators.compute_astrometric_signal(
        args.planet_mass_earth, args.star_mass_solar, args.sma_au, args.distance_pc,
    ))


def cmd_direct_imaging(args):
    _out(calculators.compute_direct_imaging(
        args.sma_au, args.distance_pc, args.planet_radius_earth, albedo=args.albedo,
        telescope_diameter_m=args.telescope_diameter_m, wavelength_um=args.wavelength_um,
    ))


def cmd_tidal_heating(args):
    _out(equations.compute_tidal_heating(
        args.primary_mass_earth, args.satellite_radius_km, args.sma_km, args.ecc,
        k2=args.k2, tidal_q=args.tidal_q,
    ))


def cmd_kozai_lidov(args):
    _out(equations.compute_kozai_lidov(
        args.m1_solar, args.m2_solar, args.m3_solar,
        period_inner_yr=args.period_inner_yr, period_outer_yr=args.period_outer_yr,
        sma_inner_au=args.sma_inner_au, sma_outer_au=args.sma_outer_au,
        ecc_outer=args.ecc_outer,
    ))


def cmd_relativistic_brachistochrone(args):
    _out(calculators.compute_relativistic_brachistochrone(args.accel_g, args.distance_ly))


# ── Phase T1c — census-filter presets ─────────────────────────────────────────

def cmd_solar_analogs(args):
    _out(databases.compute_solar_analogs(
        mode=args.mode, teff_tol=args.teff_tol, logg_tol=args.logg_tol,
        feh_tol=args.feh_tol, ly_max=args.ly_max, gcns_distance=args.gcns_distance,
    ))


def cmd_substellar(args):
    _out(databases.compute_substellar_census(
        ly_max=args.ly_max, include_late_m=args.include_late_m, classes=args.classes,
    ))


# ── Dust / ISM (Phase T2 Part A — optional dustmaps extra) ────────────────────
# Self-validating: a missing extra / unfetched map / bad direction → curated
# {"error"} (exit 1); a bad --map / non-numeric arg → argparse exit 2. Geometry
# leaving a map box is NOT an error (per-bin null + note).

def cmd_dust_sightline(args):
    _out(dust.compute_dust_sightline(
        l=args.l, b=args.b, ra=args.ra, dec=args.dec, star=args.star, id=args.id,
        dist_start_pc=args.dist_start, dist_end_pc=args.dist_end,
        n_steps=args.steps, step_pc=args.step_pc, map_sel=args.map,
    ))


def cmd_dust_between(args):
    _out(dust.compute_dust_between(
        star1=args.star1, id1=args.id1, star2=args.star2, id2=args.id2,
        n_steps=args.steps, step_pc=args.step_pc, map_sel=args.map,
    ))


def _add_dust_weight_flags(p):
    """Phase T2 Part B: dust-weighted routing flags on a Core route planner.
    --weight distance (default) → the unchanged core.calculators path; --weight
    dust → core.dust_routing (integrated A_V edge cost)."""
    p.add_argument("--weight", choices=["distance", "dust"], default="distance",
                   help="Edge weight: distance (default, 3D ly) or dust (integrated A_V)")
    p.add_argument("--map", choices=["near-field", "edenhofer", "auto"], default="auto",
                   help="Dust map when --weight dust (default auto)")
    p.add_argument("--dust-step-pc", dest="dust_step_pc", type=float, default=5.0,
                   help="Dust integration step in pc when --weight dust (default 5)")


# ── Solvent zones (Phase P) ───────────────────────────────────────────────────
# Wrap the self-validating compute_solvent_zone / compute_ice_lines (Phase H
# contract: curated {"error"} → exit 1, unlike the Phase N raw-exception path).

def cmd_solvent_zone(args):
    has_custom = args.t_low is not None or args.t_high is not None
    if args.solvent and has_custom:
        sys.stderr.write("error: --solvent and --t-low/--t-high are mutually exclusive\n")
        sys.exit(2)
    if not args.solvent and not has_custom:
        sys.stderr.write("error: provide --solvent NAME or both --t-low and --t-high\n")
        sys.exit(2)
    _out(equations.compute_solvent_zone(
        args.luminosity, solvent=args.solvent,
        t_low_k=args.t_low, t_high_k=args.t_high, albedo=args.albedo,
    ))


def cmd_ice_lines(args):
    _out(equations.compute_ice_lines(args.luminosity, albedo=args.albedo))


# Phase Q — system dossier (pure composition over existing readers; self-validating).
# Markdown/HTML emit a `document`; JSON emits structured `data`. `--star Sol`/`Sun` is the
# offline reference-origin path. Bad fmt/section or a SIMBAD-lookup failure → {"error"} exit 1.
def cmd_dossier(args):
    _out(report.build_system_dossier(args.star, sections=args.sections, fmt=args.fmt))


# Phase S — project workspaces (read-only; mutations are GUI-only). Local-DB reads,
# no network. project-get on an unknown name → {"error"} exit 1.
def cmd_project_list(args):
    _out({"projects": projects.list_projects()})


def cmd_project_get(args):
    _out(projects.get_project(args.name))


# ── Velocity & constant-speed travel converters (opts 25–28, 31, 32) ──────────
# Thin wrappers over non-self-validating pure-math core functions, so they share
# the Phase-N contract: out-of-range → raw-exception {"error"} (exit 1) where the
# math raises (e.g. zero velocity in the travel-time pair → division by zero);
# argparse rejects missing/non-numeric args (exit 2). The conversion / distance
# wrappers have no error path (any float is finite).

def cmd_ly_hr_to_times_c(args):
    _out(calculators.compute_ly_hr_to_times_c(args.ly_hr))


def cmd_times_c_to_ly_hr(args):
    _out(calculators.compute_speed_of_light_to_ly_hr(args.times_c))


def cmd_distance_traveled_ly_hr(args):
    _out(calculators.compute_distance_traveled_ly_hr(args.ly_hr, args.hours))


def cmd_distance_traveled_times_c(args):
    _out(calculators.compute_distance_traveled_times_c(args.times_c, args.hours))


def cmd_travel_time_ly_hr(args):
    _out(calculators.compute_travel_time_ly_hr(args.distance_ly, args.ly_hr))


def cmd_travel_time_times_c(args):
    _out(calculators.compute_travel_time_times_c(args.distance_ly, args.times_c))


# ── Integration expansion (Phase N) ───────────────────────────────────────────
# Each handler is a thin verbatim wrapper over an existing core function. N1–N4
# wrap the older, non-self-validating equation/calculator functions, so
# out-of-range numerics surface as {"error": str(e)} (a raw exception message)
# via main()'s top-level handler with exit 1 — see docs/integration.md. Only N5
# (travel-time-solar) emits curated {"error": ...} dicts.

def cmd_habitable_zone_sma(args):
    _out(equations.compute_habitable_zone_sma(args.teff, args.luminosity, args.sma))


def cmd_star_luminosity(args):
    # --teff is mapped to the function's `temp` parameter (naming parity with
    # habitable-zone / habitable-zone-sma).
    _out(equations.compute_star_luminosity(args.radius, args.teff))


def cmd_stellar_evolution(args):
    _out(equations.compute_stellar_evolution(args.mass_solar, args.current_age_gyr))


def cmd_brachistochrone_au(args):
    _out(calculators.compute_travel_time_system_au(args.accel_g, args.au))


def cmd_brachistochrone_lm(args):
    _out(calculators.compute_travel_time_system_lm(args.accel_g, args.lm))


def cmd_distance_at_acceleration(args):
    _out(calculators.compute_distance_at_acceleration(args.accel_g, args.hours))


def cmd_travel_time_solar(args):
    # progress_callback is GUI-only and is deliberately NOT passed (defaults to None).
    _out(calculators.compute_travel_time_solar_objects(
        args.origin, args.destination, args.accel_g,
        v_cap_pct=args.v_cap_pct, departure_date=args.date,
    ))


def cmd_optimal_tour(args):
    use_times_c = args.times_c is not None
    velocity = args.times_c if use_times_c else args.ly_hr
    if getattr(args, "weight", "distance") == "dust":
        _out(dust_routing.compute_optimal_tour_dust(
            args.stars, velocity, use_times_c, closed=args.closed,
            map_sel=args.map, dust_step_pc=args.dust_step_pc,
        ))
    else:
        _out(calculators.compute_optimal_tour(
            args.stars, velocity, use_times_c, closed=args.closed,
        ))


def cmd_jump_route(args):
    if getattr(args, "weight", "distance") == "dust":
        _out(dust_routing.compute_jump_route_dust(
            args.origin, args.destination, args.max_jump, optimize=args.optimize,
            map_sel=args.map, dust_step_pc=args.dust_step_pc,
        ))
    else:
        _out(calculators.compute_jump_route(
            args.origin, args.destination, args.max_jump, optimize=args.optimize,
        ))


def cmd_jump_network(args):
    _out(calculators.compute_jump_network(
        args.start, args.max_jump, max_jumps=args.max_jumps,
    ))


def cmd_multi_stop(args):
    use_times_c = args.times_c is not None
    velocity = args.times_c if use_times_c else args.ly_hr
    if getattr(args, "weight", "distance") == "dust":
        _out(dust_routing.compute_multi_stop_dust(
            args.stars, velocity, use_times_c,
            map_sel=args.map, dust_step_pc=args.dust_step_pc,
        ))
    else:
        _out(calculators.compute_multi_stop_journey(args.stars, velocity, use_times_c))


def cmd_nearest_neighbor(args):
    if getattr(args, "weight", "distance") == "dust":
        _out(dust_routing.compute_nearest_neighbor_dust(
            args.start, args.hops, args.max_ly,
            map_sel=args.map, dust_step_pc=args.dust_step_pc,
        ))
    else:
        _out(calculators.compute_nearest_neighbor_chain(
            args.start, args.hops, args.max_ly,
        ))


def cmd_farthest_first(args):
    _out(calculators.compute_farthest_first_chain(
        args.start, args.stops, max_reach_ly=args.max_reach,
    ))


def cmd_trade_route(args):
    if getattr(args, "weight", "distance") == "dust":
        _out(dust_routing.compute_trade_route_dust(
            args.stars, map_sel=args.map, dust_step_pc=args.dust_step_pc,
        ))
    else:
        _out(calculators.compute_trade_route_mst(args.stars))


# ── Search & Filter (Phase G) ─────────────────────────────────────────────────

def _build_filters(args, simple_keys, bool_keys=(), list_keys=()):
    """Assemble a filters dict from argparse attrs, omitting unset values."""
    f = {}
    for attr, key in simple_keys:
        v = getattr(args, attr)
        if v is not None:
            f[key] = v
    for attr, key in list_keys:
        v = getattr(args, attr)
        if v:
            f[key] = v
    for attr, key in bool_keys:
        if getattr(args, attr):
            f[key] = True
    return f


def cmd_search_star_systems(args):
    f = _build_filters(
        args,
        simple_keys=[("ly_min", "ly_min"), ("ly_max", "ly_max"),
                     ("mag_min", "mag_min"), ("mag_max", "mag_max"),
                     ("spectral_refine", "spectral_refine"),
                     ("designation_prefix", "designation_prefix"),
                     ("fe_h_min", "fe_h_min"), ("fe_h_max", "fe_h_max")],
        list_keys=[("spectral_classes", "spectral_classes")],
    )
    _out(databases.search_star_systems(f))


def cmd_search_hwc(args):
    f = _build_filters(
        args,
        simple_keys=[("esi_min", "esi_min"), ("mass_min", "mass_min"),
                     ("mass_max", "mass_max"), ("radius_min", "radius_min"),
                     ("radius_max", "radius_max"), ("temp_min", "temp_min"),
                     ("temp_max", "temp_max"), ("ly_max", "ly_max"),
                     ("spectral_refine", "spectral_refine")],
        bool_keys=[("habitable", "habitable"), ("habzone_con", "habzone_con"),
                   ("habzone_opt", "habzone_opt")],
        list_keys=[("spectral_classes", "spectral_classes")],
    )
    _out(databases.search_hwc(f))


def cmd_search_exoplanets(args):
    f = _build_filters(
        args,
        simple_keys=[("mass_min", "pl_bmasse_min"), ("mass_max", "pl_bmasse_max"),
                     ("radius_min", "pl_rade_min"), ("radius_max", "pl_rade_max"),
                     ("period_min", "pl_orbper_min"), ("period_max", "pl_orbper_max"),
                     ("teff_min", "st_teff_min"), ("teff_max", "st_teff_max"),
                     ("dist_max_pc", "sy_dist_max"), ("method", "discoverymethod"),
                     ("spectral_refine", "spectral_refine")],
        list_keys=[("spectral_classes", "spectral_classes")],
    )
    _out(databases.search_exoplanets(f))


def cmd_search_hypatia(args):
    f = _build_filters(
        args,
        simple_keys=[("fe_h_min", "fe_h_min"), ("fe_h_max", "fe_h_max"),
                     ("teff_min", "teff_min"), ("teff_max", "teff_max"),
                     ("ly_max", "ly_max"), ("disk", "disk"),
                     ("element", "element"), ("element_min", "element_min"),
                     ("element_max", "element_max")],
    )
    _out(databases.search_hypatia_cache(f))


def cmd_compare_stars(args):
    _out(databases.compare_stars(args.stars))


# ── Reference data ────────────────────────────────────────────────────────────

def cmd_main_sequence(args):
    _out(science.compute_main_sequence_table())


def cmd_solar_system(args):
    _out(science.compute_solar_system_tables())


def cmd_sol_regions(args):
    _out(regions.compute_sol_regions())


# ── Planetary / rotating-habitat equations ────────────────────────────────────

def cmd_orbit_distance(args):
    _out(equations.compute_orbit_periastron_apastron(args.sma, args.ecc))


def cmd_moon_orbital_distance(args):
    _out(equations.compute_moon_orbital_distance(args.planet_mass_earth, args.day_hours))


def cmd_gravity_acceleration(args):
    _out(equations.compute_centrifugal_gravity_acceleration(args.rpm, args.radius_m))


def cmd_gravity_distance(args):
    _out(equations.compute_centrifugal_gravity_distance(args.rpm, args.accel_ms2))


def cmd_gravity_rpm(args):
    _out(equations.compute_centrifugal_gravity_rpm(args.accel_ms2, args.radius_m))


def cmd_spin_comfort(args):
    accel = args.accel_ms2
    if args.gravity_g is not None:
        accel = args.gravity_g * equations._STANDARD_GRAVITY
    _out(spin.compute_spin_comfort(
        radius_m=args.radius_m, rpm=args.rpm, accel_ms2=accel,
        tangential_velocity_ms=args.tangential_velocity_ms,
        occupant_height_m=args.occupant_height_m, walk_speed_ms=args.walk_speed_ms,
        criteria=args.criteria,
        max_rpm=args.max_rpm, min_gravity_g=args.min_gravity_g, max_gravity_g=args.max_gravity_g,
        min_tangential_velocity_ms=args.min_tangential_velocity_ms,
        max_gradient_pct=args.max_gradient_pct, max_coriolis_pct=args.max_coriolis_pct,
    ))


# ── Phase X — closed-loop life-support & bioregenerative calculators ──────────

def cmd_life_support(args):
    _out(life_support.compute_life_support(
        crew=args.crew, days=args.days,
        water_closure=args.water_closure, o2_closure=args.o2_closure,
        food_closure=args.food_closure, closure_scenario=args.closure_scenario,
        o2_rate=args.o2_rate, co2_rate=args.co2_rate,
        potable_water_rate=args.potable_water_rate, total_water_rate=args.total_water_rate,
        food_dry_rate=args.food_dry_rate, kcal_per_day=args.kcal_per_day,
        solid_waste_rate=args.solid_waste_rate, liquid_waste_rate=args.liquid_waste_rate,
    ))


def cmd_bioregen_area(args):
    _out(life_support.compute_bioregen_area(
        kcal_per_day=args.kcal_per_day, crew=args.crew, crop=args.crop,
        ppfd_umol=args.ppfd_umol, photoperiod_h=args.photoperiod_h,
        dli_mol=args.dli_mol, par_wm2=args.par_wm2,
        photo_efficiency=args.photo_efficiency, harvest_index=args.harvest_index,
        artificial=args.artificial, led_par_efficiency=args.led_par_efficiency,
        f_edible_energy=args.f_edible_energy,
    ))


def cmd_population_capacity(args):
    _out(life_support.compute_population_capacity(
        crop_area_m2=args.crop_area_m2, power_w=args.power_w,
        water_kg_day=args.water_kg_day, fixed_nitrogen_kg_yr=args.fixed_nitrogen_kg_yr,
        food_dry_kg_day=args.food_dry_kg_day,
        per_person_area_m2=args.per_person_area_m2, per_person_power_w=args.per_person_power_w,
        per_person_water_kg_day=args.per_person_water_kg_day,
        per_person_nitrogen_kg_yr=args.per_person_nitrogen_kg_yr,
        per_person_food_kg_day=args.per_person_food_kg_day,
    ))


_BURN_UNITS = {"H": ("Hours", 3600.0), "D": ("Days", 86400.0), "W": ("Weeks", 604800.0)}


def cmd_travel_time_custom_thrust(args):
    label, secs_per = _BURN_UNITS[args.burn_unit]
    burn_duration_s = args.burn_value * secs_per
    # progress_callback is GUI-only and is deliberately NOT passed.
    _out(calculators.compute_travel_time_custom_thrust(
        args.origin, args.destination, args.accel_g, burn_duration_s,
        v_cap_pct=args.v_cap_pct, burn_value=args.burn_value,
        burn_unit_label=label, departure_date=args.date,
    ))


# ── Phase R2 · constraint / companion DSL parsing for generate-system ────────

def _parse_location(token):
    """Parse a planet_at_location location token: in_hz | at:AU | between:A:B |
    interior_to:REF | exterior_to:REF | in_zone:ZONE | in_hz:opt."""
    kind, _, larg = token.partition(":")
    kind = kind.strip()
    if kind == "at":
        return {"kind": "at", "au": float(larg)}
    if kind == "between":
        a, _, b = larg.partition(":")
        if not a or not b:
            raise ValueError("location 'between' needs two refs, e.g. between:b:c")
        return {"kind": "between", "ref_a": a, "ref_b": b}
    if kind in ("interior_to", "exterior_to"):
        if not larg:
            raise ValueError(f"location '{kind}' needs a ref, e.g. {kind}:b")
        return {"kind": kind, "ref": larg}
    if kind == "in_hz":
        return {"kind": "in_hz", "hz": larg} if larg else {"kind": "in_hz"}
    if kind == "in_zone":
        return {"kind": "in_zone", "zone": larg or "hz"}
    raise ValueError(f"unknown location kind: {kind!r}")


def _parse_constraint(spec):
    """Parse one --constraint DSL string into a spec constraint dict.

    Grammar: ``type:field,field[,…]`` — comma-separated fields after the type;
    location / ratio fields may themselves contain ':'. An unknown type passes
    through verbatim (the engine reports it as not_evaluated)."""
    ctype, _, rest = spec.partition(":")
    ctype = ctype.strip()
    if not ctype:
        raise ValueError(f"Malformed --constraint {spec!r}: missing type.")
    fields = [f.strip() for f in rest.split(",")] if rest else []
    try:
        if ctype == "planet_at_location":
            if len(fields) < 3:
                raise ValueError("expected type,mass,location "
                                 "(e.g. planet_at_location:terrestrial,1.0,between:b:c)")
            return {"type": ctype, "planet_type": fields[0],
                    "mass_earth": float(fields[1]), "location": _parse_location(fields[2])}
        if ctype == "trojan":
            if len(fields) < 2:
                raise ValueError("expected companion_type,host[,point] "
                                 "(e.g. trojan:terrestrial,giant_in_hz,L4)")
            out = {"type": ctype, "companion_type": fields[0], "host": fields[1]}
            if len(fields) >= 3 and fields[2]:
                out["point"] = fields[2].upper()
            return out
        if ctype == "moon":
            if not fields or not fields[0]:
                raise ValueError("expected host[,mass][,terraformable] "
                                 "(e.g. moon:super_jovian_in_hz,1.0,terraformable)")
            out = {"type": ctype, "host": fields[0]}
            if len(fields) >= 2 and fields[1] and fields[1] != "terraformable":
                out["mass_earth"] = float(fields[1])
            if "terraformable" in fields[1:]:
                out["terraformable"] = True
            return out
        if ctype == "resonance":
            if len(fields) < 3:
                raise ValueError("expected bodyA,bodyB,ratio (e.g. resonance:c,d,2:1)")
            return {"type": ctype, "bodies": [fields[0], fields[1]], "ratio": fields[2]}
        if ctype == "habitable_world":
            out = {"type": ctype}
            if fields and fields[0]:
                out["hz"] = fields[0]
            if len(fields) >= 2 and fields[1]:
                out["min_count"] = int(fields[1])
            return out
        if ctype == "alt_solvent_world":
            if not fields or not fields[0]:
                raise ValueError("expected solvent[,mass] (e.g. alt_solvent_world:ammonia)")
            out = {"type": ctype, "solvent": fields[0]}
            if len(fields) >= 2 and fields[1]:
                out["mass_earth"] = float(fields[1])
            return out
        if ctype == "architecture":
            if not fields or not fields[0]:
                raise ValueError("expected rule (e.g. architecture:giant_beyond_snow_line)")
            return {"type": ctype, "rule": fields[0]}
        return {"type": ctype}      # unknown type → engine emits not_evaluated
    except ValueError as e:
        raise ValueError(f"Malformed --constraint {spec!r}: {e}")


def _parse_companion(spec):
    """Parse --companion 'mass_solar,sma_au[,ecc]' into a hint dict."""
    parts = [p.strip() for p in spec.split(",")]
    if len(parts) < 2:
        raise ValueError(f"Malformed --companion {spec!r}: expected 'mass_solar,sma_au[,ecc]'.")
    try:
        out = {"mass_solar": float(parts[0]), "sma_au": float(parts[1])}
        if len(parts) >= 3 and parts[2]:
            out["ecc"] = float(parts[2])
    except ValueError:
        raise ValueError(f"Malformed --companion {spec!r}: values must be numbers.")
    return out


def cmd_generate_system(args):
    # Synthetic offline; --anchor-star adds SIMBAD/NASA/HWC network. With one or more
    # --constraint flags, generation delegates to the R2 feasibility engine (a malformed
    # DSL raises → curated {"error"} exit 1 via main()). Zero constraints → the R1 path.
    constraints = [_parse_constraint(s) for s in (args.constraint or [])]
    companion = _parse_companion(args.companion) if args.companion else None
    _out(generate.generate_system(
        args.seed,
        anchor_star=args.anchor_star,
        spectral_class=args.spectral_class,
        n_planets=args.planets,
        require_habitable=args.require_habitable,
        constraints=constraints or None,
        companion=companion,
        nbody=args.nbody,
        research_policy=args.research_policy,
    ))


# ── Argument parser ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Query SpaceAndScienceFictionApp core functions; outputs JSON to stdout.",
        epilog=(
            "Every result is JSON: a dict on success (a list for 'habitable-zone'), "
            "or {\"error\": \"...\"} with exit code 1 on failure — always check for an "
            "'error' key first. For each subcommand's required arguments and the exact "
            "output keys it returns, see docs/integration.md in this repo."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # simbad-lookup
    p = sub.add_parser("simbad-lookup", help="SIMBAD star lookup")
    p.add_argument("--star", required=True)
    p.set_defaults(func=cmd_simbad_lookup)

    # star-regions
    p = sub.add_parser("star-regions", help="Star system regions + HZ boundaries")
    p.add_argument("--star", required=True)
    p.set_defaults(func=cmd_star_regions)

    # star-regions-manual
    p = sub.add_parser("star-regions-manual",
                       help="Star system regions from manual inputs (no SIMBAD)")
    p.add_argument("--vmag",     required=True, type=float, help="Apparent magnitude (V)")
    p.add_argument("--bc",       required=True, type=float, help="Bolometric correction (BC)")
    p.add_argument("--teff",     required=True, type=float, help="Effective temperature (K)")
    p.add_argument("--parallax", required=True, type=float, help="Parallax (mas, > 0)")
    p.add_argument("--sunlight-intensity", dest="sunlight_intensity", type=float, default=1.0,
                   help="Sunlight intensity (Terra = 1.0; default 1.0)")
    p.add_argument("--bond-albedo", dest="bond_albedo", type=float, default=0.3,
                   help="Bond albedo (Terra = 0.3, Venus = 0.9; default 0.3)")
    p.set_defaults(func=cmd_star_regions_manual)

    # distance
    p = sub.add_parser("distance", help="3D distance between two stars")
    p.add_argument("--star1", required=True)
    p.add_argument("--star2", required=True)
    p.set_defaults(func=cmd_distance)

    # stars-within-sol
    p = sub.add_parser("stars-within-sol", help="Stars within N light years of Sol")
    p.add_argument("--ly", required=True, type=float)
    p.set_defaults(func=cmd_stars_within_sol)

    # stars-within-star
    p = sub.add_parser("stars-within-star", help="Stars within N light years of a star")
    p.add_argument("--star", required=True)
    p.add_argument("--ly", required=True, type=float)
    p.set_defaults(func=cmd_stars_within_star)

    # travel-time
    p = sub.add_parser("travel-time", help="FTL travel time between two stars")
    p.add_argument("--star1", required=True)
    p.add_argument("--star2", required=True)
    vel = p.add_mutually_exclusive_group(required=True)
    vel.add_argument("--ly-hr",   dest="ly_hr",   type=float, help="Velocity in light years per hour")
    vel.add_argument("--times-c", dest="times_c", type=float, help="Velocity as a multiple of c")
    p.set_defaults(func=cmd_travel_time)

    # habitable-zone
    p = sub.add_parser("habitable-zone", help="Kopparapu HZ boundaries from stellar parameters")
    p.add_argument("--teff",       required=True, type=float, help="Stellar temperature in K")
    p.add_argument("--luminosity", required=True, type=float, help="Stellar luminosity in solar units")
    p.set_defaults(func=cmd_habitable_zone)

    # exoplanets
    p = sub.add_parser("exoplanets", help="NASA Exoplanet Archive — all tables")
    p.add_argument("--star", required=True)
    p.set_defaults(func=cmd_exoplanets)

    # planetary-systems
    p = sub.add_parser("planetary-systems", help="NASA Exoplanet Archive — planetary systems composite")
    p.add_argument("--star", required=True)
    p.set_defaults(func=cmd_planetary_systems)

    # hwo-exep
    p = sub.add_parser("hwo-exep", help="HWO ExEP precursor science stars")
    p.add_argument("--star", required=True)
    p.set_defaults(func=cmd_hwo_exep)

    # mission-exocat
    p = sub.add_parser("mission-exocat", help="NASA Mission Exocat (local DB)")
    p.add_argument("--star", required=True)
    p.set_defaults(func=cmd_mission_exocat)

    # hwc
    p = sub.add_parser("hwc", help="Habitable Worlds Catalog (local DB)")
    p.add_argument("--star", required=True)
    p.set_defaults(func=cmd_hwc)

    # hypatia-data
    p = sub.add_parser("hypatia-data",
                       help="Hypatia Catalog stellar properties and elemental abundances")
    p.add_argument("--star", required=True)
    p.set_defaults(func=cmd_hypatia_data)

    # gcns-within-sol
    p = sub.add_parser("gcns-within-sol",
                       help="GCNS stars within N light years of Sol (Bayesian distances, local DB)")
    p.add_argument("--ly", required=True, type=float)
    p.add_argument("--wd-prob-min", dest="wd_prob_min", type=float, default=None,
                   help="Minimum GCNS white-dwarf probability (white-dwarf census filter)")
    p.add_argument("--wd-prob-max", dest="wd_prob_max", type=float, default=None,
                   help="Maximum GCNS white-dwarf probability")
    p.set_defaults(func=cmd_gcns_within_sol)

    # gcns-source
    p = sub.add_parser("gcns-source",
                       help="Single GCNS row by Gaia EDR3/DR3 source_id (local DB)")
    p.add_argument("--id", required=True, type=int, help="Gaia EDR3/DR3 source_id")
    p.set_defaults(func=cmd_gcns_source)

    # gcns-system
    p = sub.add_parser("gcns-system",
                       help="Resolved multiple-star system containing a Gaia source_id (local DB)")
    p.add_argument("--id", required=True, type=int,
                   help="Gaia EDR3/DR3 source_id of any component")
    p.set_defaults(func=cmd_gcns_system)

    # gcns-distance
    p = sub.add_parser("gcns-distance",
                       help="GCNS-backed 3D distance between two stars (by name or Gaia id)")
    g1 = p.add_mutually_exclusive_group(required=True)
    g1.add_argument("--star1", help="Endpoint 1 by name (SIMBAD network lookup)")
    g1.add_argument("--id1", type=int, help="Endpoint 1 by Gaia EDR3/DR3 source_id")
    g2 = p.add_mutually_exclusive_group(required=True)
    g2.add_argument("--star2", help="Endpoint 2 by name (SIMBAD network lookup)")
    g2.add_argument("--id2", type=int, help="Endpoint 2 by Gaia EDR3/DR3 source_id")
    p.set_defaults(func=cmd_gcns_distance)

    # gcns-travel-time
    p = sub.add_parser("gcns-travel-time",
                       help="GCNS-backed FTL travel time between two stars (by name or Gaia id)")
    g1 = p.add_mutually_exclusive_group(required=True)
    g1.add_argument("--star1", help="Origin by name (SIMBAD network lookup)")
    g1.add_argument("--id1", type=int, help="Origin by Gaia EDR3/DR3 source_id")
    g2 = p.add_mutually_exclusive_group(required=True)
    g2.add_argument("--star2", help="Destination by name (SIMBAD network lookup)")
    g2.add_argument("--id2", type=int, help="Destination by Gaia EDR3/DR3 source_id")
    vel = p.add_mutually_exclusive_group(required=True)
    vel.add_argument("--ly-hr",   dest="ly_hr",   type=float, help="Velocity in light years per hour")
    vel.add_argument("--times-c", dest="times_c", type=float, help="Velocity as a multiple of c")
    p.set_defaults(func=cmd_gcns_travel_time)

    # gcns-stars-within-star
    p = sub.add_parser("gcns-stars-within-star",
                       help="GCNS stars within N light years of a star (Bayesian distances)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--star", help="Center by name (SIMBAD network lookup)")
    g.add_argument("--id", type=int, help="Center by Gaia EDR3/DR3 source_id")
    p.add_argument("--ly", required=True, type=float, help="Light-year radius")
    p.set_defaults(func=cmd_gcns_stars_within_star)

    # roche-limit
    p = sub.add_parser("roche-limit", help="Rigid + fluid Roche limits for a satellite")
    p.add_argument("--primary-mass-earth", required=True, type=float,
                   help="Primary mass in Earth masses")
    p.add_argument("--satellite-density", required=True, type=float,
                   help="Satellite bulk density in g/cm³")
    p.add_argument("--primary-radius-earth", type=float, default=None,
                   help="Primary radius in Earth radii (optional; estimated from mass if omitted)")
    p.set_defaults(func=cmd_roche_limit)

    # tidal-locking
    p = sub.add_parser("tidal-locking", help="Tidal-locking timescale of a satellite")
    p.add_argument("--primary-mass-earth",   required=True, type=float)
    p.add_argument("--satellite-mass-earth", required=True, type=float)
    p.add_argument("--sma-km",               required=True, type=float)
    p.add_argument("--rotation-hours",       required=True, type=float,
                   help="Initial rotation period in hours")
    p.add_argument("--rigidity-pa", type=float, default=3e10)
    p.add_argument("--tidal-q",     type=float, default=100)
    p.set_defaults(func=cmd_tidal_locking)

    # hill-sphere
    p = sub.add_parser("hill-sphere", help="Hill sphere of a planet in a star system")
    p.add_argument("--star-mass-solar",   required=True, type=float)
    p.add_argument("--planet-mass-earth", required=True, type=float)
    p.add_argument("--sma-au",            required=True, type=float)
    p.add_argument("--eccentricity",      type=float, default=0)
    p.add_argument("--moon-inclination-deg", dest="moon_inclination_deg",
                   type=float, default=0,
                   help="Satellite orbital inclination in degrees (Domingos 2006 stable-moon limit)")
    p.add_argument("--retrograde", action="store_true",
                   help="Use the retrograde Domingos factor (default: prograde)")
    p.set_defaults(func=cmd_hill_sphere)

    # binary-stability
    p = sub.add_parser("binary-stability",
                       help="Planet orbit stability in a binary (Holman & Wiegert 1999)")
    p.add_argument("--mass1-solar",  required=True, type=float)
    p.add_argument("--mass2-solar",  required=True, type=float)
    p.add_argument("--binary-sma-au", required=True, type=float)
    p.add_argument("--test-sma-au",   required=True, type=float)
    p.add_argument("--eccentricity",  type=float, default=0)
    p.set_defaults(func=cmd_binary_stability)

    # atmosphere-retention
    p = sub.add_parser("atmosphere-retention",
                       help="Atmospheric gases a planet retains against Jeans escape")
    p.add_argument("--planet-mass-earth",   required=True, type=float)
    p.add_argument("--planet-radius-earth", required=True, type=float)
    p.add_argument("--temperature-k",       required=True, type=float)
    p.set_defaults(func=cmd_atmosphere_retention)

    # ── Phase T1a — research-tooling extensions ──────────────────────────────

    # trojan-stability (wraps R2 gascheau_coorbital_stable)
    p = sub.add_parser("trojan-stability",
                       help="L4/L5 Trojan co-orbital stability (Gascheau/Routh μ < 0.0385)")
    p.add_argument("--host-mass-earth",      required=True, type=float,
                   help="Co-orbital host body mass in Earth masses")
    p.add_argument("--companion-mass-earth", required=True, type=float,
                   help="Trojan companion mass in Earth masses (may be 0)")
    p.add_argument("--star-mass-solar",      required=True, type=float,
                   help="Central star mass in solar masses")
    p.set_defaults(func=cmd_trojan_stability)

    # lorentz-factor (relativistic time dilation; distinct from the FTL converters)
    p = sub.add_parser("lorentz-factor",
                       help="Relativistic Lorentz / time-dilation factor for a sublight velocity")
    p.add_argument("--velocity-c", required=True, type=float,
                   help="Velocity as a fraction of c (0 ≤ β < 1)")
    p.set_defaults(func=cmd_lorentz_factor)

    # circumbinary-hz (reuses compute_habitable_zone from combined light)
    p = sub.add_parser("circumbinary-hz",
                       help="Circumbinary (P-type) habitable zone from two stars' combined light")
    p.add_argument("--teff1", type=float, help="Star 1 effective temperature (K)")
    p.add_argument("--lum1",  type=float, help="Star 1 luminosity (L_sun)")
    p.add_argument("--teff2", type=float, help="Star 2 effective temperature (K)")
    p.add_argument("--lum2",  type=float, help="Star 2 luminosity (L_sun)")
    p.add_argument("--star1", help="Star 1 by name (SIMBAD; alt to --teff1/--lum1)")
    p.add_argument("--star2", help="Star 2 by name (SIMBAD; alt to --teff2/--lum2)")
    p.set_defaults(func=cmd_circumbinary_hz)

    # cooling-hz (Phase U — cooling-primary WD/BD HZ residence & CHZ)
    p = sub.add_parser("cooling-hz",
                       help="Cooling-primary (white/brown dwarf) HZ snapshot / residence / CHZ band")
    p.add_argument("--track", required=True, choices=["wd", "bd"],
                   help="Cooling track: wd (white dwarf) or bd (brown dwarf)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--mass-solar", type=float, help="Primary mass in solar masses (WD default 0.6)")
    g.add_argument("--mass-mjup",  type=float, help="Primary mass in Jupiter masses (BD primary unit, default 50)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--cooling-age-gyr", type=float, help="Snapshot epoch by cooling age (mode 1)")
    mode.add_argument("--teff",            type=float, help="Snapshot epoch by effective temperature K (mode 1)")
    mode.add_argument("--sma-au",          type=float, help="Residence at this orbit AU (mode 2); omit all three for the CHZ band (mode 3)")
    p.add_argument("--chz-threshold-gyr", type=float, default=3.0,
                   help="CHZ residence threshold in Gyr (mode 3, default 3.0)")
    p.add_argument("--hz-edge", choices=["conservative", "optimistic"], default="conservative",
                   help="HZ edge set (default conservative: runaway->maximum greenhouse)")
    p.add_argument("--age-max-gyr", type=float, default=13.8,
                   help="Integration ceiling in Gyr (default 13.8)")
    p.add_argument("--satellite-density", type=float, default=5.5,
                   help="Satellite bulk density g/cc for the CHZ Roche cross-check (default 5.5 rocky)")
    p.set_defaults(func=cmd_cooling_hz)

    # waste-heat (Phase V — power → rejected-heat budget, with Carnot ceiling)
    p = sub.add_parser("waste-heat",
                       help="Waste heat a device must reject from a power figure + efficiency (with Carnot ceiling)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--input-power-watts",  type=float, help="Gross input/thermal power, W")
    g.add_argument("--useful-power-watts", type=float, help="Net useful output power, W")
    p.add_argument("--efficiency", type=float, help="Conversion/thermal efficiency η (0 < η ≤ 1)")
    p.add_argument("--hot-temp-k",  type=float, help="Hot-reservoir temperature K (for the Carnot ceiling)")
    p.add_argument("--cold-temp-k", type=float, help="Cold-reservoir temperature K (for the Carnot ceiling)")
    p.set_defaults(func=cmd_waste_heat)

    # radiator-area (Phase V — Stefan–Boltzmann thermal-rejection wall)
    p = sub.add_parser("radiator-area",
                       help="Radiating area (and optional mass) to reject a heat load (Stefan–Boltzmann)")
    p.add_argument("--heat-watts", type=float, help="Heat load to reject, W")
    p.add_argument("--input-power-watts", type=float, help="Gross input power W (chain with --efficiency → Q=P_in·(1−η))")
    p.add_argument("--efficiency", type=float, help="Efficiency η for the input-power chain (0 < η ≤ 1)")
    p.add_argument("--radiator-temp-k", type=float, required=True, help="Radiator surface temperature K (> 0)")
    p.add_argument("--emissivity", type=float, default=0.9, help="Surface emissivity ε (0 < ε ≤ 1, default 0.9)")
    p.add_argument("--sides", type=int, choices=[1, 2], default=2,
                   help="Radiating faces: 1 (one hemisphere) or 2 (flat panel, default)")
    p.add_argument("--sink-temp-k", type=float, default=0.0,
                   help="Effective sink temperature K (default 0 = idealized deep space)")
    p.add_argument("--areal-mass-kgm2", type=float, default=None,
                   help="Radiator areal mass kg/m² (optional → radiator_mass_kg)")
    p.set_defaults(func=cmd_radiator_area)

    # shielding-attenuation (Phase V — Lambert–Beer photon / GCR order-of-magnitude)
    p = sub.add_parser("shielding-attenuation",
                       help="Radiation attenuation by shielding mass (photon Lambert–Beer / GCR order-of-mag)")
    p.add_argument("--mode", choices=["photon", "gcr"], default="photon",
                   help="photon (exact Lambert–Beer, default) or gcr (order-of-magnitude)")
    p.add_argument("--areal-density-gcm2", type=float, help="Shield areal density Σ, g/cm²")
    p.add_argument("--thickness-cm", type=float, help="Shield thickness cm (with --density-gcm3 → Σ=ρ·x)")
    p.add_argument("--density-gcm3", type=float, help="Shield density g/cm³ (with --thickness-cm)")
    p.add_argument("--mass-atten-coeff-cm2g", type=float, help="Photon μ/ρ, cm²/g (explicit; photon mode)")
    p.add_argument("--attenuation-length-gcm2", type=float, help="GCR attenuation length Λ, g/cm² (explicit; gcr mode)")
    p.add_argument("--material", help="Bundled material for the coefficient lookup "
                                      "(water/polyethylene/aluminum/regolith/lead/liquid_h2/hydrogen/iron)")
    p.add_argument("--energy-mev", type=float, help="Photon energy MeV for the bundled μ/ρ lookup")
    p.set_defaults(func=cmd_shielding_attenuation)

    # rocket-equation (Phase Y — Tsiolkovsky classical + relativistic; complements the
    # brachistochrone-* kinematics with the mass/energy side of STL travel)
    p = sub.add_parser("rocket-equation",
                       help="Tsiolkovsky (classical + relativistic) mass ratio & propellant "
                            "fraction from any two of {velocity, exhaust, mass_ratio}")
    p.add_argument("--delta-v-kms", type=float, help="Mission Δv, km/s (classical velocity anchor)")
    p.add_argument("--beta", type=float, help="Final velocity as a fraction of c (relativistic anchor, 0≤β<1)")
    p.add_argument("--exhaust-velocity-kms", type=float, help="Exhaust velocity v_e, km/s (exhaust anchor)")
    p.add_argument("--isp-s", type=float, help="Specific impulse, s (→ v_e = Isp·g₀; exhaust anchor)")
    p.add_argument("--fuel", choices=sorted(propulsion.propulsion_tables._FUELS),
                   help="Bundled ideal exhaust velocity by fuel (exhaust anchor)")
    p.add_argument("--mass-ratio", type=float, help="Single-burn wet/dry mass ratio (anchor)")
    p.add_argument("--relativistic", action="store_true",
                   help="Emit the relativistic velocity when solving from exhaust+mass-ratio")
    p.add_argument("--legs", choices=["flyby", "rendezvous", "round-trip"], default="flyby",
                   help="flyby MR¹ / rendezvous MR² / round-trip MR⁴ (default flyby)")
    p.add_argument("--payload-mass-t", type=float, help="Payload/dry mass, t (→ propellant & wet mass)")
    p.add_argument("--structure-fraction", type=float, help="Structure mass fraction [0,1) (echoed; v1 note)")
    p.set_defaults(func=cmd_rocket_equation)

    # beam-sail (Phase Y — laser / photon-sail thrust & energetics)
    p = sub.add_parser("beam-sail",
                       help="Laser / photon-sail thrust, acceleration, and (optional) final velocity")
    p.add_argument("--beam-power-w", required=True, type=float, help="Intercepted beam power, W")
    p.add_argument("--sail-area-m2", type=float, help="Sail area, m² (for areal-mass + beam-range note)")
    p.add_argument("--areal-mass-gm2", type=float, help="Sail areal mass, g/m² (with --sail-area-m2 → sail mass)")
    p.add_argument("--sail-mass-kg", type=float, help="Sail mass, kg (explicit; overrides areal-mass path)")
    p.add_argument("--payload-mass-kg", type=float, default=0.0, help="Payload mass, kg (default 0)")
    p.add_argument("--reflectivity", type=float, default=0.9, help="Sail reflectivity R, 0≤R≤1 (default 0.9)")
    p.add_argument("--wavelength-nm", type=float, help="Beam wavelength, nm (with --transmit-aperture-m → range note)")
    p.add_argument("--transmit-aperture-m", type=float, help="Transmitter aperture, m (with --wavelength-nm)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--accel-distance-au", type=float, help="Acceleration length, AU (→ final velocity)")
    g.add_argument("--accel-time-days", type=float, help="Acceleration time, days (→ final velocity)")
    p.set_defaults(func=cmd_beam_sail)

    # magsail (Phase AC — magnetic-sail braking against the ISM: standoff → drag ∝ v^4/3 →
    # deceleration → optional stopping distance/time)
    p = sub.add_parser("magsail",
                       help="Magnetic-sail braking against the ISM: magnetopause standoff, drag "
                            "force (∝ v^4/3), deceleration, and optional stopping distance/time")
    p.add_argument("--ism-density-cm3", type=float,
                   help="ISM number density, cm⁻³ (default 0.1 = Local Interstellar Cloud)")
    p.add_argument("--ion-mass-amu", type=float, help="Mean ISM ion mass, amu (default 1.3 = H+He)")
    v = p.add_mutually_exclusive_group()
    v.add_argument("--velocity-kms", type=float, help="Flight velocity, km/s (velocity anchor)")
    v.add_argument("--beta", type=float, help="Flight velocity as a fraction of c, 0<β<1 (velocity anchor)")
    p.add_argument("--coil-current-a", type=float, help="Superconducting-loop current, A (with --coil-radius-m)")
    p.add_argument("--coil-radius-m", type=float, help="Coil radius, m (with --coil-current-a)")
    p.add_argument("--magnetic-moment-am2", type=float, help="Magnetic dipole moment, A·m² (sail anchor)")
    p.add_argument("--standoff-coeff", type=float, help="Standoff coefficient k (default 1.0; see docs)")
    p.add_argument("--drag-coeff", type=float, help="Drag coefficient C_d (default 1.0; Zubrin & Andrews)")
    p.add_argument("--vehicle-mass-t", type=float, help="Vehicle mass, t (→ deceleration; needed for stopping)")
    p.add_argument("--velocity-final-kms", type=float,
                   help="Target final velocity, km/s (→ stopping distance/time; requires --vehicle-mass-t)")
    p.set_defaults(func=cmd_magsail)

    # ramscoop (Phase AC — Bussard ramjet drag-vs-thrust verdict: drive or brake?)
    p = sub.add_parser("ramscoop",
                       help="Bussard ramjet drag-vs-thrust verdict (drive or brake?) + crossover "
                            "velocity, from the ISM/scoop/fusion balance")
    p.add_argument("--ism-density-cm3", type=float,
                   help="ISM number density, cm⁻³ (default 0.1 = Local Interstellar Cloud)")
    p.add_argument("--ion-mass-amu", type=float, help="Mean ISM ion mass, amu (default 1.3 = H+He)")
    v = p.add_mutually_exclusive_group()
    v.add_argument("--velocity-kms", type=float, help="Flight velocity, km/s (velocity anchor)")
    v.add_argument("--beta", type=float, help="Flight velocity as a fraction of c, 0<β<1 (velocity anchor)")
    p.add_argument("--coil-current-a", type=float, help="Loop current, A (with --coil-radius-m; scoop anchor)")
    p.add_argument("--coil-radius-m", type=float, help="Coil radius, m (with --coil-current-a)")
    p.add_argument("--magnetic-moment-am2", type=float, help="Magnetic dipole moment, A·m² (scoop anchor)")
    p.add_argument("--scoop-area-km2", type=float, help="Physical scoop area, km² (scoop anchor)")
    p.add_argument("--fuel", choices=sorted(ism_drag._t._FUSION),
                   help="Bundled fusion mass→energy fraction (pp/cno/dd; exhaust anchor, with --fusion-efficiency)")
    p.add_argument("--fusion-efficiency", type=float,
                   help="Directed-exhaust efficiency η, 0<η≤1 (default 0.1, low; with --fuel)")
    p.add_argument("--exhaust-velocity-kms", type=float, help="Explicit exhaust velocity v_e, km/s (exhaust anchor)")
    p.add_argument("--standoff-coeff", type=float, help="Standoff coefficient k (default 1.0)")
    p.add_argument("--drag-coeff", type=float, help="Drag coefficient C_d (default 1.0)")
    p.set_defaults(func=cmd_ramscoop)

    # spin-stress (Phase Z — hoop stress σ=ρv² → max habitat size for a material)
    p = sub.add_parser("spin-stress",
                       help="Hoop-stress size limit: max habitat radius/gravity a material can spin "
                            "(complements spin-comfort's human-comfort minimum)")
    p.add_argument("--material", choices=sorted(megastructure.materials_tables._MATERIALS),
                   help="Bundled material (ρ + σ_tensile)")
    p.add_argument("--density-kgm3", type=float, help="Explicit density, kg/m³ (with --tensile-strength-mpa)")
    p.add_argument("--tensile-strength-mpa", type=float, help="Explicit tensile strength, MPa (with --density-kgm3)")
    p.add_argument("--safety-factor", type=float, default=3.0, help="Safety factor SF ≥ 1 (default 3)")
    p.add_argument("--target-gravity-g", type=float, help="Target gravity in g (→ max radius)")
    p.add_argument("--radius-m", type=float, help="Radius, m (alone → max gravity; with --rpm → hoop stress)")
    p.add_argument("--rpm", type=float, help="Spin rate, RPM (with --radius-m → actual hoop stress + margin)")
    p.set_defaults(func=cmd_spin_stress)

    # tether-taper (Phase Z — Pearson uniform-stress space-elevator taper ratio)
    p = sub.add_parser("tether-taper",
                       help="Space-elevator / skyhook taper ratio for a material + body (Pearson uniform stress)")
    p.add_argument("--material", choices=sorted(megastructure.materials_tables._MATERIALS),
                   help="Bundled material (ρ + σ_tensile)")
    p.add_argument("--density-kgm3", type=float, help="Explicit density, kg/m³ (with --tensile-strength-mpa)")
    p.add_argument("--tensile-strength-mpa", type=float, help="Explicit tensile strength, MPa (with --density-kgm3)")
    p.add_argument("--safety-factor", type=float, default=3.0, help="Safety factor SF ≥ 1 (default 3)")
    p.add_argument("--body", choices=sorted(megastructure.materials_tables._BODIES),
                   help="Bundled body (earth/mars/moon/ceres): surface radius, synchronous radius, g")
    p.add_argument("--surface-gravity-ms2", type=float, help="Explicit surface gravity, m/s²")
    p.add_argument("--surface-radius-km", type=float, help="Explicit surface radius, km")
    p.add_argument("--geo-radius-km", type=float, help="Explicit synchronous-orbit radius from centre, km")
    p.set_defaults(func=cmd_tether_taper)

    # dyson-collector (Phase Z — swarm/shell area & mass to intercept a luminosity fraction)
    p = sub.add_parser("dyson-collector",
                       help="Collector area & mass to intercept a fraction of a star's luminosity")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--luminosity-lsun", type=float, help="Stellar luminosity in solar units")
    g.add_argument("--star", help="Star name → SIMBAD-resolved luminosity (network)")
    p.add_argument("--fraction", required=True, type=float, help="Fraction of the full sphere to intercept (0–1]")
    p.add_argument("--orbit-au", required=True, type=float, help="Collector orbital radius, AU")
    p.add_argument("--areal-mass-kgm2", type=float, default=0.01, help="Collector areal mass, kg/m² (default 0.01)")
    p.set_defaults(func=cmd_dyson_collector)

    # par-flux (Phase AA — PAR fraction / PPFD / red-dwarf photosynthesis deficit by stellar type)
    p = sub.add_parser("par-flux",
                       help="PAR fraction, PAR irradiance, PPFD & red-dwarf deficit from a blackbody SED")
    # Teff source — exactly one (the count check is a core exit-1, like spin-comfort's anchors).
    p.add_argument("--teff-k", type=float, help="Effective temperature K (offline)")
    p.add_argument("--spectral-type", help="Spectral type, e.g. G2V → main-sequence Teff (offline)")
    p.add_argument("--star", help="Star name → SIMBAD-resolved Teff (network)")
    # Insolation source — exactly one (core exit-1).
    p.add_argument("--insolation-wm2", type=float, help="Total insolation at the surface, W/m²")
    p.add_argument("--luminosity-lsun", type=float, help="Stellar luminosity in solar units (with --distance-au)")
    p.add_argument("--distance-au", type=float, help="Orbital distance, AU (with --luminosity-lsun)")
    p.add_argument("--par-band-nm", type=float, nargs=2, default=[400.0, 700.0],
                   metavar=("LO", "HI"), help="PAR band in nm (default 400 700)")
    p.set_defaults(func=cmd_par_flux)

    # equilibrium-temp (Phase AB — planetary equilibrium + greenhouse surface temperature)
    p = sub.add_parser("equilibrium-temp",
                       help="Planetary equilibrium temperature + greenhouse surface temp (offset/grey/inverse)")
    p.add_argument("--insolation-wm2", type=float, help="Insolation at the planet, W/m²")
    p.add_argument("--luminosity-lsun", type=float, help="Stellar luminosity in solar units (with --distance-au)")
    p.add_argument("--distance-au", type=float, help="Orbital distance, AU (with --luminosity-lsun)")
    p.add_argument("--albedo", type=float, default=0.3, help="Bond albedo, [0,1) (default 0.3)")
    # Forcing form — exactly one (a core exit-1 check, like par-flux's anchors).
    p.add_argument("--greenhouse-delta-k", type=float, help="Additive greenhouse offset ΔT, K")
    p.add_argument("--optical-depth", type=float, help="Grey-atmosphere IR optical depth τ (≥0)")
    p.add_argument("--target-surface-k", type=float, help="Target surface temp K → required forcing (inverse)")
    p.set_defaults(func=cmd_equilibrium_temp)

    # insolation-shift (Phase AB — orbital mirror/shade area for a flux change)
    p = sub.add_parser("insolation-shift",
                       help="Orbital mirror (warm) / shade (cool) area for a sphere-averaged flux change")
    p.add_argument("--planet-radius-km", required=True, type=float, help="Planet radius, km")
    p.add_argument("--delta-insolation-wm2", required=True, type=float,
                   help="Signed flux change ΔS, W/m² (+ mirror / − shade)")
    p.add_argument("--solar-flux-wm2", type=float, help="Solar flux at the planet's orbit, W/m²")
    p.add_argument("--luminosity-lsun", type=float, help="Stellar luminosity in solar units (with --distance-au)")
    p.add_argument("--distance-au", type=float, help="Orbital distance, AU (with --luminosity-lsun)")
    p.set_defaults(func=cmd_insolation_shift)

    # atmosphere-mass (Phase AB — hydrostatic atmosphere mass ↔ surface pressure)
    p = sub.add_parser("atmosphere-mass",
                       help="Hydrostatic atmosphere mass for a surface pressure (and the inverse)")
    p.add_argument("--planet-radius-km", required=True, type=float, help="Planet radius, km")
    p.add_argument("--surface-gravity-ms2", type=float, help="Surface gravity, m/s²")
    p.add_argument("--planet-mass-earth", type=float, help="Planet mass in Earth masses (→ g = GM/R²)")
    p.add_argument("--pressure-bar", type=float, help="Surface pressure, bar (→ mass)")
    p.add_argument("--volatile-mass-kg", type=float, help="Atmosphere mass, kg (→ pressure)")
    p.add_argument("--species", choices=["n2", "co2", "o2", "h2o"], help="Optional volatile species label")
    p.set_defaults(func=cmd_atmosphere_mass)

    # spin-comfort (Phase W — rotating-habitat comfort readout + criteria verdict)
    p = sub.add_parser("spin-comfort",
                       help="Rotating-habitat comfort: solve spin state from any two anchors + "
                            "rim velocity / gravity gradient / Coriolis ratio + tiered comfort verdict "
                            "(complements the terse gravity-acceleration/-distance/-rpm solves)")
    p.add_argument("--radius-m", type=float, help="Radius to the occupant's feet, m (state anchor)")
    p.add_argument("--rpm", type=float, help="Spin rate, revolutions per minute (state anchor)")
    grav = p.add_mutually_exclusive_group()
    grav.add_argument("--gravity-g", type=float, help="Centrifugal gravity in g (state anchor)")
    grav.add_argument("--accel-ms2", type=float, help="Centrifugal gravity in m/s² (state anchor)")
    p.add_argument("--tangential-velocity-ms", type=float, help="Rim tangential velocity, m/s (state anchor)")
    p.add_argument("--occupant-height-m", type=float, default=1.8,
                   help="Head height for the gravity gradient, m (default 1.8; must be < radius)")
    p.add_argument("--walk-speed-ms", type=float, default=1.0,
                   help="Reference occupant walking speed for the Coriolis ratio, m/s (default 1.0)")
    p.add_argument("--criteria", choices=["conservative", "moderate", "relaxed", "all"], default="all",
                   help="Comfort tier(s) to report (default all)")
    p.add_argument("--max-rpm", type=float, help="Override the max spin rate threshold (RPM)")
    p.add_argument("--min-gravity-g", type=float, help="Override the min gravity threshold (g)")
    p.add_argument("--max-gravity-g", type=float, help="Override the max gravity threshold (g)")
    p.add_argument("--min-tangential-velocity-ms", type=float, help="Override the min rim-velocity threshold (m/s)")
    p.add_argument("--max-gradient-pct", type=float, help="Override the max head-foot gradient threshold (%%)")
    p.add_argument("--max-coriolis-pct", type=float, help="Override the max Coriolis-ratio threshold (%%)")
    p.set_defaults(func=cmd_spin_comfort)

    # life-support (Phase X1 — crew consumables/waste budget + closure-loop makeup mass)
    p = sub.add_parser("life-support",
                       help="Closed-loop crew consumables/waste budget (BVAD Rev2 rates) + "
                            "closure-scenario makeup mass")
    p.add_argument("--crew", type=int, default=1, help="Crew size (default 1)")
    p.add_argument("--days", type=int, default=1, help="Mission duration in days (default 1)")
    p.add_argument("--closure-scenario", choices=sorted(life_support._t.get_closure_scenarios()),
                   help="Recycle scenario: open (default) | iss | advanced | bioregen")
    p.add_argument("--water-closure", type=float, help="Override water recycle fraction [0,1]")
    p.add_argument("--o2-closure", type=float, help="Override O2 recycle fraction [0,1]")
    p.add_argument("--food-closure", type=float, help="Override food recycle fraction [0,1]")
    p.add_argument("--o2-rate", type=float, help="Override O2 consumed, kg/CM·d")
    p.add_argument("--co2-rate", type=float, help="Override CO2 produced, kg/CM·d")
    p.add_argument("--potable-water-rate", type=float, help="Override drinking water, kg/CM·d")
    p.add_argument("--total-water-rate", type=float, help="Override total (incl. hygiene) water, kg/CM·d")
    p.add_argument("--food-dry-rate", type=float, help="Override food solids (dry), kg/CM·d")
    p.add_argument("--kcal-per-day", type=float, help="Override food energy, kcal/CM·d")
    p.add_argument("--solid-waste-rate", type=float, help="Override dry metabolic solids, kg/CM·d")
    p.add_argument("--liquid-waste-rate", type=float, help="Override liquid (water) waste, kg/CM·d")
    p.set_defaults(func=cmd_life_support)

    # bioregen-area (Phase X2 — grow area + lighting power to feed a crew)
    p = sub.add_parser("bioregen-area",
                       help="Bioregenerative grow area + lighting power (PAR energy balance; "
                            "BVAD-crop measured cross-check; algae productivity path)")
    p.add_argument("--kcal-per-day", type=float, help="Dietary energy per person, kcal/day (default 2500)")
    p.add_argument("--crew", type=int, default=1, help="Crew size (default 1)")
    p.add_argument("--crop", choices=sorted(life_support._t.get_crops()),
                   help="Bundled crop (wheat/…/lettuce = BVAD; chlorella/spirulina = algae)")
    light = p.add_mutually_exclusive_group(required=True)
    light.add_argument("--ppfd-umol", type=float, help="Photosynthetic photon flux density, µmol/m²·s")
    light.add_argument("--dli-mol", type=float, help="Daily light integral, mol/m²·d")
    light.add_argument("--par-wm2", type=float, help="PAR irradiance over the photoperiod, W/m²")
    p.add_argument("--photoperiod-h", type=float, default=16.0, help="Photoperiod, hours (default 16)")
    p.add_argument("--photo-efficiency", type=float,
                   help="Biomass-energy/incident-PAR efficiency (default 0.10)")
    p.add_argument("--harvest-index", type=float,
                   help="Edible/total biomass fraction (default from --crop; required otherwise)")
    p.add_argument("--artificial", action="store_true",
                   help="Compute LED electrical power (omit for natural/concentrated light)")
    p.add_argument("--led-par-efficiency", type=float,
                   help="Wall-plug→PAR LED efficiency (default 0.4)")
    p.add_argument("--f-edible-energy", type=float, default=1.0,
                   help="Fraction of edible dry mass that is metabolizable energy (default 1.0)")
    p.set_defaults(func=cmd_bioregen_area)

    # population-capacity (Phase X3 — sustainable population from resource budgets)
    p = sub.add_parser("population-capacity",
                       help="Sustainable population from resource budgets; reports the binding "
                            "constraint (per-person defaults from X1/X2)")
    p.add_argument("--crop-area-m2", type=float, help="Total available crop area budget, m²")
    p.add_argument("--power-w", type=float, help="Total available electrical power budget, W")
    p.add_argument("--water-kg-day", type=float, help="Total available water budget, kg/day")
    p.add_argument("--fixed-nitrogen-kg-yr", type=float, help="Total available fixed nitrogen budget, kg/yr")
    p.add_argument("--food-dry-kg-day", type=float, help="Total available food (dry) budget, kg/day")
    p.add_argument("--per-person-area-m2", type=float, help="Override per-person crop area, m²")
    p.add_argument("--per-person-power-w", type=float, help="Override per-person power, W")
    p.add_argument("--per-person-water-kg-day", type=float, help="Override per-person water, kg/day")
    p.add_argument("--per-person-nitrogen-kg-yr", type=float, help="Override per-person fixed nitrogen, kg/yr")
    p.add_argument("--per-person-food-kg-day", type=float, help="Override per-person food (dry), kg/day")
    p.set_defaults(func=cmd_population_capacity)

    # rv-semi-amplitude (A1)
    p = sub.add_parser("rv-semi-amplitude",
                       help="Radial-velocity semi-amplitude a planet induces on its star")
    p.add_argument("--planet-mass-earth", required=True, type=float)
    p.add_argument("--star-mass-solar",   required=True, type=float)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--period-days", type=float, help="Orbital period in days")
    g.add_argument("--sma-au",      type=float, help="Semi-major axis in AU (derive P via Kepler III)")
    p.add_argument("--ecc",             type=float, default=0)
    p.add_argument("--inclination-deg", type=float, default=90)
    p.set_defaults(func=cmd_rv_semi_amplitude)

    # transit-signal (A2)
    p = sub.add_parser("transit-signal",
                       help="Transit depth, geometric probability, and duration")
    p.add_argument("--planet-radius-earth", required=True, type=float)
    p.add_argument("--star-radius-solar",   required=True, type=float)
    p.add_argument("--sma-au",          type=float, help="Semi-major axis in AU")
    p.add_argument("--period-days",     type=float, help="Orbital period in days (with --star-mass-solar)")
    p.add_argument("--star-mass-solar", type=float, help="Star mass (M_sun); derives a from --period-days")
    p.set_defaults(func=cmd_transit_signal)

    # astrometric-signal (A3)
    p = sub.add_parser("astrometric-signal",
                       help="Astrometric wobble of a star induced by a planet")
    p.add_argument("--planet-mass-earth", required=True, type=float)
    p.add_argument("--star-mass-solar",   required=True, type=float)
    p.add_argument("--sma-au",            required=True, type=float)
    p.add_argument("--distance-pc",       required=True, type=float)
    p.set_defaults(func=cmd_astrometric_signal)

    # direct-imaging (A4)
    p = sub.add_parser("direct-imaging",
                       help="Reflected-light contrast and angular separation, optional vs telescope IWA")
    p.add_argument("--sma-au",              required=True, type=float)
    p.add_argument("--distance-pc",         required=True, type=float)
    p.add_argument("--planet-radius-earth", required=True, type=float)
    p.add_argument("--albedo",              type=float, default=0.3)
    p.add_argument("--telescope-diameter-m", type=float, default=None,
                   help="Telescope aperture (m); with --wavelength-um computes the IWA")
    p.add_argument("--wavelength-um",        type=float, default=None,
                   help="Observing wavelength (µm); with --telescope-diameter-m computes the IWA")
    p.set_defaults(func=cmd_direct_imaging)

    # tidal-heating (B1)
    p = sub.add_parser("tidal-heating",
                       help="Tidal heating power + surface flux of a satellite (order-of-magnitude)")
    p.add_argument("--primary-mass-earth",  required=True, type=float)
    p.add_argument("--satellite-radius-km", required=True, type=float)
    p.add_argument("--sma-km",              required=True, type=float)
    p.add_argument("--ecc",                 required=True, type=float)
    p.add_argument("--k2",      type=float, default=0.3, help="Satellite Love number (default 0.3)")
    p.add_argument("--tidal-q", type=float, default=100, help="Satellite tidal quality factor (default 100)")
    p.set_defaults(func=cmd_tidal_heating)

    # kozai-lidov (C2)
    p = sub.add_parser("kozai-lidov",
                       help="Kozai–Lidov oscillation timescale for a hierarchical triple (order-of-magnitude)")
    p.add_argument("--m1-solar", required=True, type=float)
    p.add_argument("--m2-solar", required=True, type=float)
    p.add_argument("--m3-solar", required=True, type=float, help="Outer/tertiary perturber mass (M_sun)")
    p.add_argument("--period-inner-yr", type=float, help="Inner orbital period (yr) — with --period-outer-yr")
    p.add_argument("--period-outer-yr", type=float, help="Outer orbital period (yr)")
    p.add_argument("--sma-inner-au",    type=float, help="Inner SMA (AU) — alt to periods, with --sma-outer-au")
    p.add_argument("--sma-outer-au",    type=float, help="Outer SMA (AU)")
    p.add_argument("--ecc-outer",       type=float, default=0)
    p.set_defaults(func=cmd_kozai_lidov)

    # relativistic-brachistochrone (D1)
    p = sub.add_parser("relativistic-brachistochrone",
                       help="Flip-and-burn under constant proper acceleration (relativistic; lifts the 3%% c cap)")
    p.add_argument("--accel-g",     required=True, type=float)
    p.add_argument("--distance-ly", required=True, type=float)
    p.set_defaults(func=cmd_relativistic_brachistochrone)

    # ── Phase T1c — census-filter presets ────────────────────────────────────

    # solar-analogs (E2)
    p = sub.add_parser("solar-analogs",
                       help="Solar twins/analogs from the Hypatia cache (teff/logg/[Fe/H] box)")
    p.add_argument("--mode", choices=["twin", "analog"], default="twin",
                   help="twin = tight box (±100/±0.1/±0.1); analog = looser (±500/±0.4/±0.3)")
    p.add_argument("--teff-tol", type=float, default=None, help="Override Teff tolerance (K)")
    p.add_argument("--logg-tol", type=float, default=None, help="Override log g tolerance (dex)")
    p.add_argument("--feh-tol",  type=float, default=None, help="Override [Fe/H] tolerance (dex)")
    p.add_argument("--ly-max",   type=float, default=None, help="Max distance (light years)")
    p.add_argument("--gcns-distance", action="store_true",
                   help="Best-effort attach the GCNS Bayesian distance (dist_pc_gcns) per star")
    p.set_defaults(func=cmd_solar_analogs)

    # substellar (E3)
    p = sub.add_parser("substellar",
                       help="Substellar (L/T/Y) census from gcns_stars by spectral-type prefix")
    p.add_argument("--ly-max", type=float, default=None, help="Max distance (light years)")
    p.add_argument("--include-late-m", action="store_true",
                   help="Also include late-M dwarfs (M7/M8/M9, the M/L boundary)")
    p.add_argument("--classes", nargs="+", default=None,
                   help="Override the spectral-class prefixes (default: L T Y)")
    p.set_defaults(func=cmd_substellar)

    # ── Dust / ISM (Phase T2 Part A — optional dustmaps extra) ───────────────

    # dust-sightline
    p = sub.add_parser("dust-sightline",
                       help="ISM dust extinction profile along one direction (A_V, optional dustmaps extra)")
    p.add_argument("--l", type=float, help="Galactic longitude (deg)")
    p.add_argument("--b", type=float, help="Galactic latitude (deg)")
    p.add_argument("--ra", type=float, help="ICRS right ascension (deg)")
    p.add_argument("--dec", type=float, help="ICRS declination (deg)")
    p.add_argument("--star", help="Star name whose resolved direction sets the sightline")
    p.add_argument("--id", type=int, help="Gaia EDR3/DR3 source_id whose direction sets the sightline")
    p.add_argument("--dist-start", dest="dist_start", type=float, default=0.0,
                   help="Sightline start distance (pc, default 0)")
    p.add_argument("--dist-end", dest="dist_end", type=float, default=None,
                   help="Sightline end distance (pc)")
    p.add_argument("--steps", type=int, default=50, help="Number of bins (default 50)")
    p.add_argument("--step-pc", dest="step_pc", type=float, default=None,
                   help="Bin spacing (pc); overrides --steps")
    p.add_argument("--map", choices=["near-field", "edenhofer", "auto"], default="auto",
                   help="Dust map (default auto: Leike ≤69 pc, Edenhofer beyond)")
    p.set_defaults(func=cmd_dust_sightline)

    # dust-between
    p = sub.add_parser("dust-between",
                       help="ISM dust extinction along a star-to-star line (A_V, optional dustmaps extra)")
    g1 = p.add_mutually_exclusive_group(required=True)
    g1.add_argument("--star1", help="Endpoint 1 by name (Sol/Sun → origin)")
    g1.add_argument("--id1", type=int, help="Endpoint 1 by Gaia EDR3/DR3 source_id")
    g2 = p.add_mutually_exclusive_group(required=True)
    g2.add_argument("--star2", help="Endpoint 2 by name (Sol/Sun → origin)")
    g2.add_argument("--id2", type=int, help="Endpoint 2 by Gaia EDR3/DR3 source_id")
    p.add_argument("--steps", type=int, default=50, help="Number of bins (default 50)")
    p.add_argument("--step-pc", dest="step_pc", type=float, default=None,
                   help="Bin spacing (pc); overrides --steps")
    p.add_argument("--map", choices=["near-field", "edenhofer", "auto"], default="auto",
                   help="Dust map (default auto)")
    p.set_defaults(func=cmd_dust_between)

    # ── Solvent zones (Phase P) ──────────────────────────────────────────────

    # solvent-zone
    p = sub.add_parser("solvent-zone",
                       help="Solvent Habitable Zone band (M1 surface model)")
    p.add_argument("--luminosity", required=True, type=float,
                   help="Stellar luminosity (L_sun)")
    p.add_argument("--solvent",
                   help="Named solvent key (water, ammonia, methane, co2, ...)")
    p.add_argument("--t-low", dest="t_low", type=float,
                   help="Custom freezing/lower edge (K) — use with --t-high")
    p.add_argument("--t-high", dest="t_high", type=float,
                   help="Custom boiling/upper edge (K) — use with --t-low")
    p.add_argument("--albedo", type=float, default=0.3,
                   help="Bond albedo (default 0.3)")
    p.set_defaults(func=cmd_solvent_zone)

    # ice-lines
    p = sub.add_parser("ice-lines",
                       help="Volatile condensation / ice lines (M2 equilibrium model)")
    p.add_argument("--luminosity", required=True, type=float,
                   help="Stellar luminosity (L_sun)")
    p.add_argument("--albedo", type=float, default=0.0,
                   help="Bond albedo (default 0.0, bare ice grains)")
    p.set_defaults(func=cmd_ice_lines)

    # ── Velocity & constant-speed travel converters (opts 25–28, 31, 32) ──────

    # ly-hr-to-times-c (opt 31)
    p = sub.add_parser("ly-hr-to-times-c",
                       help="Convert a ly/hr velocity to multiples of c")
    p.add_argument("--ly-hr", dest="ly_hr", required=True, type=float,
                   help="Velocity in light years per hour")
    p.set_defaults(func=cmd_ly_hr_to_times_c)

    # times-c-to-ly-hr (opt 32)
    p = sub.add_parser("times-c-to-ly-hr",
                       help="Convert a multiple-of-c velocity to ly/hr")
    p.add_argument("--times-c", dest="times_c", required=True, type=float,
                   help="Velocity as a multiple of the speed of light")
    p.set_defaults(func=cmd_times_c_to_ly_hr)

    # distance-traveled-ly-hr (opt 25)
    p = sub.add_parser("distance-traveled-ly-hr",
                       help="Distance covered at a ly/hr velocity over a time")
    p.add_argument("--ly-hr", dest="ly_hr", required=True, type=float,
                   help="Velocity in light years per hour")
    p.add_argument("--hours", required=True, type=float, help="Travel time in hours")
    p.set_defaults(func=cmd_distance_traveled_ly_hr)

    # distance-traveled-times-c (opt 26)
    p = sub.add_parser("distance-traveled-times-c",
                       help="Distance covered at a multiple of c over a time")
    p.add_argument("--times-c", dest="times_c", required=True, type=float,
                   help="Velocity as a multiple of the speed of light")
    p.add_argument("--hours", required=True, type=float, help="Travel time in hours")
    p.set_defaults(func=cmd_distance_traveled_times_c)

    # travel-time-ly-hr (opt 27)
    p = sub.add_parser("travel-time-ly-hr",
                       help="Time to travel N light years at a ly/hr velocity")
    p.add_argument("--distance-ly", dest="distance_ly", required=True, type=float,
                   help="Distance in light years")
    p.add_argument("--ly-hr", dest="ly_hr", required=True, type=float,
                   help="Velocity in light years per hour (> 0)")
    p.set_defaults(func=cmd_travel_time_ly_hr)

    # travel-time-times-c (opt 28)
    p = sub.add_parser("travel-time-times-c",
                       help="Time to travel N light years at a multiple of c")
    p.add_argument("--distance-ly", dest="distance_ly", required=True, type=float,
                   help="Distance in light years")
    p.add_argument("--times-c", dest="times_c", required=True, type=float,
                   help="Velocity as a multiple of the speed of light (> 0)")
    p.set_defaults(func=cmd_travel_time_times_c)

    # ── Integration expansion (Phase N) ──────────────────────────────────────

    # habitable-zone-sma
    p = sub.add_parser("habitable-zone-sma",
                       help="HZ boundaries + object's Seff and HZ-membership verdict")
    p.add_argument("--teff",       required=True, type=float, help="Stellar temperature in K")
    p.add_argument("--luminosity", required=True, type=float, help="Stellar luminosity in solar units")
    p.add_argument("--sma",        required=True, type=float, help="Object's semi-major axis in AU")
    p.set_defaults(func=cmd_habitable_zone_sma)

    # star-luminosity
    p = sub.add_parser("star-luminosity",
                       help="Stellar luminosity from radius and temperature: L = R^2 * (T/5778)^4")
    p.add_argument("--radius", required=True, type=float, help="Stellar radius in solar radii (R_sun)")
    p.add_argument("--teff",   required=True, type=float, help="Effective temperature in K")
    p.set_defaults(func=cmd_star_luminosity)

    # stellar-evolution
    p = sub.add_parser("stellar-evolution",
                       help="Evolutionary-stage timeline from stellar mass (0.1-20 M_sun)")
    p.add_argument("--mass-solar",      required=True, type=float,
                   help="Stellar mass in solar masses (0.1-20)")
    p.add_argument("--current-age-gyr", type=float, default=None,
                   help="Optional current age in Gyr (marks the current stage)")
    p.set_defaults(func=cmd_stellar_evolution)

    # brachistochrone-au
    p = sub.add_parser("brachistochrone-au",
                       help="Brachistochrone travel time for three profiles, distance in AU")
    p.add_argument("--accel-g", dest="accel_g", required=True, type=float, help="Acceleration in g")
    p.add_argument("--au",      required=True, type=float, help="Distance in AU")
    p.set_defaults(func=cmd_brachistochrone_au)

    # brachistochrone-lm
    p = sub.add_parser("brachistochrone-lm",
                       help="Brachistochrone travel time for three profiles, distance in light minutes")
    p.add_argument("--accel-g", dest="accel_g", required=True, type=float, help="Acceleration in g")
    p.add_argument("--lm",      required=True, type=float, help="Distance in light minutes")
    p.set_defaults(func=cmd_brachistochrone_lm)

    # distance-at-acceleration
    p = sub.add_parser("distance-at-acceleration",
                       help="Distance traveled for three profiles given acceleration + travel time")
    p.add_argument("--accel-g", dest="accel_g", required=True, type=float, help="Acceleration in g")
    p.add_argument("--hours",   required=True, type=float, help="Travel time in hours")
    p.set_defaults(func=cmd_distance_at_acceleration)

    # travel-time-solar
    p = sub.add_parser("travel-time-solar",
                       help="Brachistochrone travel time between two solar-system bodies (live JPL Horizons)")
    p.add_argument("--origin",      required=True, help="Origin body name or Horizons ID")
    p.add_argument("--destination", required=True, help="Destination body name or Horizons ID")
    p.add_argument("--accel-g", dest="accel_g", required=True, type=float, help="Acceleration in g")
    p.add_argument("--v-cap-pct", dest="v_cap_pct", type=float, default=3.0,
                   help="Coast-phase velocity cap as %% of c (default 3.0)")
    p.add_argument("--date", default=None, help="Departure date ISO YYYY-MM-DD (default: today)")
    p.set_defaults(func=cmd_travel_time_solar)

    # ── Route Planning additions (Phase I-OPTS) ──────────────────────────────

    # optimal-tour
    p = sub.add_parser("optimal-tour",
                       help="Shortest-total-distance visit order for a set of stars (NN + 2-opt)")
    p.add_argument("--stars", required=True, nargs="+",
                   help="Star names to visit (first = fixed start)")
    p.add_argument("--closed", action="store_true",
                   help="Closed loop (return to start)")
    vel = p.add_mutually_exclusive_group(required=True)
    vel.add_argument("--ly-hr",   dest="ly_hr",   type=float, help="Velocity in light years per hour")
    vel.add_argument("--times-c", dest="times_c", type=float, help="Velocity as a multiple of c")
    _add_dust_weight_flags(p)
    p.set_defaults(func=cmd_optimal_tour)

    # jump-route
    p = sub.add_parser("jump-route",
                       help="Route origin→destination over a jump-limited graph (Dijkstra/BFS)")
    p.add_argument("--origin",      required=True, help="Origin star name")
    p.add_argument("--destination", required=True, help="Destination star name")
    p.add_argument("--max-jump", dest="max_jump", required=True, type=float,
                   help="Maximum single-jump distance in light years")
    p.add_argument("--optimize", choices=["distance", "jumps"], default="distance",
                   help="Minimize total distance (default) or number of jumps")
    _add_dust_weight_flags(p)
    p.set_defaults(func=cmd_jump_route)

    # jump-network
    p = sub.add_parser("jump-network",
                       help="BFS reachability tiers from a start star at a jump range")
    p.add_argument("--start",    required=True, help="Start star name")
    p.add_argument("--max-jump", dest="max_jump", required=True, type=float,
                   help="Maximum single-jump distance in light years")
    p.add_argument("--max-jumps", dest="max_jumps", type=int, default=None,
                   help="Cap on the number of jumps (optional)")
    p.set_defaults(func=cmd_jump_network)

    # multi-stop
    p = sub.add_parser("multi-stop",
                       help="Cumulative travel time along an ordered list of stops")
    p.add_argument("--stars", required=True, nargs="+", help="Ordered stop star names")
    vel = p.add_mutually_exclusive_group(required=True)
    vel.add_argument("--ly-hr",   dest="ly_hr",   type=float, help="Velocity in light years per hour")
    vel.add_argument("--times-c", dest="times_c", type=float, help="Velocity as a multiple of c")
    _add_dust_weight_flags(p)
    p.set_defaults(func=cmd_multi_stop)

    # nearest-neighbor
    p = sub.add_parser("nearest-neighbor",
                       help="Greedy nearest-unvisited chain from a start star")
    p.add_argument("--start",  required=True, help="Start star name")
    p.add_argument("--hops",   required=True, type=int, help="Number of hops")
    p.add_argument("--max-ly", dest="max_ly", required=True, type=float,
                   help="Maximum single-hop distance in light years")
    _add_dust_weight_flags(p)
    p.set_defaults(func=cmd_nearest_neighbor)

    # farthest-first
    p = sub.add_parser("farthest-first",
                       help="De-clustering coverage chain (farthest-from-visited)")
    p.add_argument("--start", required=True, help="Start star name")
    p.add_argument("--stops", required=True, type=int, help="Number of stops")
    p.add_argument("--max-reach", dest="max_reach", type=float, default=None,
                   help="Maximum reach from the visited set in light years (optional)")
    p.set_defaults(func=cmd_farthest_first)

    # trade-route
    p = sub.add_parser("trade-route",
                       help="Minimum spanning tree connecting a set of systems")
    p.add_argument("--stars", required=True, nargs="+", help="System names (≥ 2)")
    _add_dust_weight_flags(p)
    p.set_defaults(func=cmd_trade_route)

    # ── Search & Filter (Phase G) ────────────────────────────────────────────

    # search-star-systems
    p = sub.add_parser("search-star-systems",
                       help="Filter the local star_systems table (all filters optional)")
    p.add_argument("--spectral-classes", dest="spectral_classes", nargs="+",
                   help="Spectral class chips: O B A F G K M Other")
    p.add_argument("--spectral-refine", dest="spectral_refine",
                   help="Case-insensitive contains-match on the rest of the type (e.g. V)")
    p.add_argument("--ly-min",  dest="ly_min",  type=float)
    p.add_argument("--ly-max",  dest="ly_max",  type=float)
    p.add_argument("--mag-min", dest="mag_min", type=float)
    p.add_argument("--mag-max", dest="mag_max", type=float)
    p.add_argument("--designation-prefix", dest="designation_prefix")
    p.add_argument("--fe-h-min", dest="fe_h_min", type=float,
                   help="[Fe/H] minimum (JOINs the Hypatia cache; needs Import Hypatia Cache)")
    p.add_argument("--fe-h-max", dest="fe_h_max", type=float, help="[Fe/H] maximum")
    p.set_defaults(func=cmd_search_star_systems)

    # search-hwc
    p = sub.add_parser("search-hwc",
                       help="Filter the local Habitable Worlds Catalog (all filters optional)")
    p.add_argument("--esi-min",   dest="esi_min",   type=float)
    p.add_argument("--mass-min",  dest="mass_min",  type=float, help="P_MASS (Earth masses)")
    p.add_argument("--mass-max",  dest="mass_max",  type=float)
    p.add_argument("--radius-min", dest="radius_min", type=float, help="P_RADIUS (Earth radii)")
    p.add_argument("--radius-max", dest="radius_max", type=float)
    p.add_argument("--temp-min",  dest="temp_min",  type=float, help="P_TEMP_EQUIL (K)")
    p.add_argument("--temp-max",  dest="temp_max",  type=float)
    p.add_argument("--ly-max",    dest="ly_max",    type=float)
    p.add_argument("--spectral-classes", dest="spectral_classes", nargs="+")
    p.add_argument("--spectral-refine",  dest="spectral_refine")
    p.add_argument("--habitable",   action="store_true", help="P_HABITABLE = 1")
    p.add_argument("--habzone-con", dest="habzone_con", action="store_true", help="In conservative HZ")
    p.add_argument("--habzone-opt", dest="habzone_opt", action="store_true", help="In optimistic HZ")
    p.set_defaults(func=cmd_search_hwc)

    # search-exoplanets
    p = sub.add_parser("search-exoplanets",
                       help="Filter live NASA pscomppars (all filters optional)")
    p.add_argument("--mass-min",   dest="mass_min",   type=float, help="pl_bmasse (Earth masses)")
    p.add_argument("--mass-max",   dest="mass_max",   type=float)
    p.add_argument("--radius-min", dest="radius_min", type=float, help="pl_rade (Earth radii)")
    p.add_argument("--radius-max", dest="radius_max", type=float)
    p.add_argument("--period-min", dest="period_min", type=float, help="pl_orbper (days)")
    p.add_argument("--period-max", dest="period_max", type=float)
    p.add_argument("--teff-min",   dest="teff_min",   type=float, help="st_teff (K)")
    p.add_argument("--teff-max",   dest="teff_max",   type=float)
    p.add_argument("--dist-max-pc", dest="dist_max_pc", type=float, help="sy_dist (parsecs)")
    p.add_argument("--method", dest="method", help="discoverymethod (exact)")
    p.add_argument("--spectral-classes", dest="spectral_classes", nargs="+")
    p.add_argument("--spectral-refine",  dest="spectral_refine")
    p.set_defaults(func=cmd_search_exoplanets)

    # search-hypatia
    p = sub.add_parser("search-hypatia",
                       help="Filter the local Hypatia abundance cache (all filters optional)")
    p.add_argument("--fe-h-min", dest="fe_h_min", type=float, help="[Fe/H] minimum")
    p.add_argument("--fe-h-max", dest="fe_h_max", type=float, help="[Fe/H] maximum")
    p.add_argument("--teff-min", dest="teff_min", type=float)
    p.add_argument("--teff-max", dest="teff_max", type=float)
    p.add_argument("--ly-max",   dest="ly_max",   type=float)
    p.add_argument("--disk",     dest="disk",     help="Hypatia disk code (exact, e.g. 0=thin 1=thick)")
    p.add_argument("--element",  dest="element",  help="Species symbol (API casing, e.g. Mg, Ba_II)")
    p.add_argument("--element-min", dest="element_min", type=float, help="[X/H] minimum for --element")
    p.add_argument("--element-max", dest="element_max", type=float, help="[X/H] maximum for --element")
    p.set_defaults(func=cmd_search_hypatia)

    # compare-stars
    p = sub.add_parser("compare-stars",
                       help="Side-by-side comparison of 2–4 stars (SIMBAD + NASA supplement + HZ + Hypatia)")
    p.add_argument("--stars", required=True, nargs="+",
                   help='2–4 star names (e.g. "Tau Ceti" Sol "18 Sco"); Sol/Sun use reference constants')
    p.set_defaults(func=cmd_compare_stars)

    # ── Reference data ───────────────────────────────────────────────────────

    # main-sequence
    p = sub.add_parser("main-sequence",
                       help="Main-sequence star properties table (spectral class → Teff/mass/radius/lum/…)")
    p.set_defaults(func=cmd_main_sequence)

    # solar-system
    p = sub.add_parser("solar-system",
                       help="Solar system planets / moons / dwarf planets / asteroids data")
    p.set_defaults(func=cmd_solar_system)

    # sol-regions
    p = sub.add_parser("sol-regions",
                       help="Sol's system regions (HZ, snow line, etc.) from hardcoded solar constants")
    p.set_defaults(func=cmd_sol_regions)

    # ── Planetary / rotating-habitat equations ───────────────────────────────

    # orbit-distance
    p = sub.add_parser("orbit-distance",
                       help="Periastron / apastron from semi-major axis and eccentricity")
    p.add_argument("--sma", required=True, type=float, help="Semi-major axis (AU)")
    p.add_argument("--ecc", required=True, type=float, help="Eccentricity (0 ≤ e < 1)")
    p.set_defaults(func=cmd_orbit_distance)

    # moon-orbital-distance
    p = sub.add_parser("moon-orbital-distance",
                       help="Orbital distance of an Earth-sized moon for a given day length")
    p.add_argument("--planet-mass-earth", dest="planet_mass_earth", required=True, type=float)
    p.add_argument("--day-hours", dest="day_hours", type=float, default=24.0,
                   help="Day length in hours (default 24)")
    p.set_defaults(func=cmd_moon_orbital_distance)

    # gravity-acceleration
    p = sub.add_parser("gravity-acceleration",
                       help="Centrifugal artificial gravity at a point (m/s^2) from rpm + radius")
    p.add_argument("--rpm",      required=True, type=float)
    p.add_argument("--radius-m", dest="radius_m", required=True, type=float)
    p.set_defaults(func=cmd_gravity_acceleration)

    # gravity-distance
    p = sub.add_parser("gravity-distance",
                       help="Radius from the centre of rotation (m) from rpm + target gravity")
    p.add_argument("--rpm",       required=True, type=float)
    p.add_argument("--accel-ms2", dest="accel_ms2", required=True, type=float,
                   help="Target centrifugal gravity (m/s^2)")
    p.set_defaults(func=cmd_gravity_distance)

    # gravity-rpm
    p = sub.add_parser("gravity-rpm",
                       help="Rotation rate (rpm) from target gravity + radius")
    p.add_argument("--accel-ms2", dest="accel_ms2", required=True, type=float,
                   help="Target centrifugal gravity (m/s^2)")
    p.add_argument("--radius-m",  dest="radius_m", required=True, type=float)
    p.set_defaults(func=cmd_gravity_rpm)

    # travel-time-custom-thrust
    p = sub.add_parser("travel-time-custom-thrust",
                       help="Travel time between two solar-system bodies with a custom burn duration (live JPL Horizons)")
    p.add_argument("--origin",      required=True, help="Origin body name or Horizons ID")
    p.add_argument("--destination", required=True, help="Destination body name or Horizons ID")
    p.add_argument("--accel-g", dest="accel_g", required=True, type=float, help="Acceleration in g")
    p.add_argument("--burn-value", dest="burn_value", required=True, type=float,
                   help="Accel/decel burn duration value")
    p.add_argument("--burn-unit", dest="burn_unit", choices=["H", "D", "W"], default="D",
                   help="Burn duration unit: H=Hours, D=Days (default), W=Weeks")
    p.add_argument("--v-cap-pct", dest="v_cap_pct", type=float, default=3.0,
                   help="Coast-phase velocity cap as %% of c (default 3.0)")
    p.add_argument("--date", default=None, help="Departure date ISO YYYY-MM-DD (default: today)")
    p.set_defaults(func=cmd_travel_time_custom_thrust)

    # dossier
    p = sub.add_parser("dossier",
                       help="Render a full system dossier (markdown/html/json)")
    p.add_argument("--star", required=True,
                   help="Star name, or 'Sol'/'Sun' for the Solar System (offline)")
    p.add_argument("--fmt", choices=["markdown", "html", "json"], default="markdown",
                   help="Output format (default markdown)")
    p.add_argument("--sections", nargs="+",
                   help="Subset of: identity regions habitable_zone planets hypatia gcns moons "
                        "(default: all available; 'moons' is Sol-only opt-in)")
    p.set_defaults(func=cmd_dossier)

    # project-list (Phase S — read-only)
    p = sub.add_parser("project-list",
                       help="List project workspaces (name, description, member count)")
    p.set_defaults(func=cmd_project_list)

    # project-get (Phase S — read-only)
    p = sub.add_parser("project-get",
                       help="A project workspace + its members (generated_spec echoed parsed)")
    p.add_argument("--name", required=True, help="Project name")
    p.set_defaults(func=cmd_project_get)

    # generate-system
    p = sub.add_parser("generate-system",
                       help="Procedurally generate a planetary system (synthetic or real-anchor)")
    p.add_argument("--seed", required=True, type=int,
                   help="Integer RNG seed (same seed → identical output)")
    p.add_argument("--anchor-star", dest="anchor_star", default=None,
                   help="Real star to anchor on (adds SIMBAD/NASA/HWC network); omit for synthetic")
    p.add_argument("--spectral-class", dest="spectral_class", default=None,
                   help="Synthetic-only host class, e.g. K2V (sampled if omitted)")
    p.add_argument("--planets", dest="planets", type=int, default=None,
                   help="Planet count 0-15 (synthetic count, or synthetic-infill count when anchored; sampled if omitted)")
    p.add_argument("--require-habitable", dest="require_habitable", action="store_true",
                   help="Require a conservative-HZ rocky world (bounded retry, else error)")
    p.add_argument("--constraint", dest="constraint", action="append", default=None,
                   help="A desired feature (repeatable) → feasibility mode. DSL 'type:fields', "
                        "e.g. 'planet_at_location:terrestrial,1.0,between:b:c', "
                        "'trojan:terrestrial,giant_in_hz,L4', "
                        "'moon:super_jovian_in_hz,1.0,terraformable', 'resonance:c,d,2:1'")
    p.add_argument("--companion", dest="companion", default=None,
                   help="Multi-star companion hint 'mass_solar,sma_au[,ecc]' for S/P-type checks")
    p.add_argument("--nbody", dest="nbody", action="store_true",
                   help="N-body confirmation of marginal packing verdicts (opt-in)")
    p.add_argument("--research-policy", dest="research_policy",
                   choices=("permissive", "strict"), default="permissive",
                   help="permissive (default; DefaultPriors) | strict (research-calibrated "
                        "priors — requires an ingested dataset, else a curated error)")
    p.set_defaults(func=cmd_generate_system)

    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as e:
        _out({"error": str(e)})


if __name__ == "__main__":
    main()
