"""query.py — JSON dispatcher for SpaceAndScienceFictionApp core functions.

Usage:
    python query.py <subcommand> [arguments]

Prints JSON to stdout. Exits 0 on success, 1 on error.
"""

import argparse
import json
import sys

import core.active_shield as active_shield
import core.black_hole as black_hole
import core.calculators as calculators
import core.cooling as cooling
import core.databases as databases
import core.detection as detection
import core.dust_impact as dust_impact   # pure-math (no astropy/numpy) — safe at module load
# core.dust / core.dust_routing are imported lazily inside their handlers — they pull
# astropy + numpy (dust coordinate math), so keeping them out of module load makes every
# non-dust query.py invocation ~0.5 s faster (matters for the sister repo's per-call cost
# and the subprocess test suite). All dust references live inside cmd_* handlers.
import core.equations as equations
import core.exclusion_boundary as exclusion_boundary
import core.exotic_physics as exotic_physics
import core.feasibility as feasibility
import core.formation as formation
import core.metric_drive as metric_drive
import core.gravitation as gravitation
import core.generate as generate
import core.ism_drag as ism_drag
import core.kinematics as kinematics
import core.life_support as life_support
import core.megastructure as megastructure
import core.nuclear as nuclear
import core.par_flux as par_flux
import core.power as power
import core.radiation as radiation
import core.power_tables as power_tables
import core.energy_storage as energy_storage
import core.projects as projects
import core.relativity as relativity
import core.propulsion as propulsion
import core.regions as regions
import core.report as report
import core.salvo as salvo
import core.science as science
import core.sensing as sensing
import core.spin as spin
import core.strategic_geography as strategic_geography
import core.terraforming as terraforming
import core.thermal as thermal
import core.volatile_delivery as volatile_delivery
import core.warp as warp
import core.weapons as weapons


def _add_object_mass_args(p):
    """Add the shared black-hole mass flags (--mass-* + --object preset) to a parser."""
    p.add_argument("--mass-kg", type=float); p.add_argument("--mass-msun", type=float)
    p.add_argument("--mass-mearth", type=float); p.add_argument("--mass-mjup", type=float)
    p.add_argument("--object", choices=black_hole.astro_bodies.OBJECT_PRESET_KEYS,
                   help="Object preset (Sun, Sgr A*, M87*, …)")


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


def cmd_oec_system(args):
    # query.py path resolves offline against the OEC alias index (no SIMBAD).
    _out(databases.compute_oec(args.name, allow_simbad=False))


def cmd_oec_planet(args):
    _out(databases.compute_oec_planet(args.name))


def cmd_oec_search(args):
    _out(databases.compute_oec_search(
        min_stars=args.min_stars, max_stars=args.max_stars, status=args.status,
        circumbinary=args.circumbinary, discovery_method=args.discovery_method,
        discovery_year_min=args.discovery_year_min, discovery_year_max=args.discovery_year_max,
        mass_min=args.mass_min, mass_max=args.mass_max,
        radius_min=args.radius_min, radius_max=args.radius_max,
        period_min=args.period_min, period_max=args.period_max,
        sma_min=args.sma_min, sma_max=args.sma_max,
        spectral_type=args.spectral_type, limit=args.limit))


def cmd_oec_census(args):
    _out(databases.compute_oec_census())


def cmd_oec_status(args):
    _out(databases.compute_oec_status())


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


# ── Phase AE (Group K) — arrival geometry & gravitation ───────────────────────

def cmd_escape_velocity(args):
    _out(gravitation.compute_escape_velocity(
        mass_kg=args.mass_kg, mass_msun=args.mass_msun, mass_mearth=args.mass_mearth,
        mass_mjup=args.mass_mjup, radius_m=args.radius_m, radius_rsun=args.radius_rsun,
        radius_rearth=args.radius_rearth, distance_au=args.distance_au, body=args.body))


def cmd_gravitational_potential(args):
    _out(gravitation.compute_gravitational_potential(
        mass_kg=args.mass_kg, mass_msun=args.mass_msun, mass_mearth=args.mass_mearth,
        mass_mjup=args.mass_mjup, body=args.body, r_from_m=args.r_from_m, r_from_au=args.r_from_au,
        r_to_m=args.r_to_m, r_to_au=args.r_to_au, payload_kg=args.payload_kg))


def cmd_sphere_of_influence(args):
    _out(gravitation.compute_sphere_of_influence(
        body_mass_kg=args.body_mass_kg, body_mass_msun=args.body_mass_msun,
        body_mass_mearth=args.body_mass_mearth, body_mass_mjup=args.body_mass_mjup,
        primary_mass_kg=args.primary_mass_kg, primary_mass_msun=args.primary_mass_msun,
        primary_mass_mearth=args.primary_mass_mearth, primary_mass_mjup=args.primary_mass_mjup,
        primary=args.primary, semimajor_au=args.semimajor_au))


def cmd_hyperbolic_approach(args):
    _out(gravitation.compute_hyperbolic_approach(
        mass_kg=args.mass_kg, mass_msun=args.mass_msun, mass_mearth=args.mass_mearth,
        mass_mjup=args.mass_mjup, body=args.body, v_infinity_kms=args.v_infinity_kms,
        arrival_speed_kms=args.arrival_speed_kms, r_from_km=args.r_from_km, r_from_au=args.r_from_au,
        periapsis_km=args.periapsis_km, periapsis_rbody=args.periapsis_rbody,
        target=args.target, target_apoapsis_km=args.target_apoapsis_km,
        target_apoapsis_au=args.target_apoapsis_au))


# ── Phase AF (Group L) — special relativity & causality ───────────────────────

def cmd_time_dilation(args):
    _out(relativity.compute_time_dilation(
        velocity_c=args.velocity_c, velocity_kms=args.velocity_kms,
        proper_time=args.proper_time, coordinate_time=args.coordinate_time,
        mass_kg=args.mass_kg, mass_msun=args.mass_msun, mass_mearth=args.mass_mearth,
        mass_mjup=args.mass_mjup, body=args.body, radius_m=args.radius_m,
        radius_rsun=args.radius_rsun, radius_rearth=args.radius_rearth,
        distance_au=args.distance_au, combined=args.combined))


def cmd_length_contraction(args):
    _out(relativity.compute_length_contraction(
        velocity_c=args.velocity_c, velocity_kms=args.velocity_kms,
        proper_length=args.proper_length, contracted_length=args.contracted_length))


def cmd_velocity_addition(args):
    _out(relativity.compute_velocity_addition(args.u_c, args.v_c, perpendicular=args.perpendicular))


def cmd_relativistic_doppler(args):
    _out(relativity.compute_relativistic_doppler(
        velocity_c=args.velocity_c, velocity_kms=args.velocity_kms,
        approach=args.approach, recede=args.recede, angle_deg=args.angle_deg,
        rest_wavelength_nm=args.rest_wavelength_nm, rest_frequency_hz=args.rest_frequency_hz))


def cmd_rapidity(args):
    add = None
    if args.add is not None:
        try:
            add = [float(x) for x in args.add.split(",") if x.strip() != ""]
        except ValueError:
            _out({"error": "--add must be a comma-separated list of β values, e.g. '0.6,0.6,0.6'."})
            return
    _out(relativity.compute_rapidity(velocity_c=args.velocity_c, rapidity=args.rapidity, add=add))


def cmd_relativistic_energy_momentum(args):
    _out(relativity.compute_relativistic_energy_momentum(
        mass_kg=args.mass_kg, mass_mev=args.mass_mev, velocity_c=args.velocity_c,
        gamma=args.gamma, kinetic_energy_j=args.kinetic_energy_j, momentum=args.momentum))


def cmd_lorentz_transform(args):
    event2_t = event2_x = None
    if args.event2 is not None:
        parts = args.event2.split(",")
        if len(parts) != 2:
            _out({"error": "--event2 must be 't2,x2' (two comma-separated numbers)."})
            return
        try:
            event2_t, event2_x = float(parts[0]), float(parts[1])
        except ValueError:
            _out({"error": "--event2 must be 't2,x2' (two comma-separated numbers)."})
            return
    _out(relativity.compute_lorentz_transform(
        velocity_c=args.velocity_c, t=args.t, x=args.x, t_yr=args.t_yr, x_ly=args.x_ly,
        inverse=args.inverse, event2_t=event2_t, event2_x=event2_x))


def cmd_causality_check(args):
    _out(relativity.compute_causality_check(
        signal_speed_c=args.signal_speed_c, instant=args.instant,
        frame_velocity_c=args.frame_velocity_c, preferred_frame=args.preferred_frame,
        two_jump=args.two_jump))


# ── Phase AG (Group M) — exotic vacuum & cosmology ────────────────────────────

def cmd_casimir(args):
    _out(exotic_physics.compute_casimir(
        separation_m=args.separation_m, separation_nm=args.separation_nm, area_m2=args.area_m2,
        geometry=args.geometry, sphere_radius_m=args.sphere_radius_m))


def cmd_vacuum_energy(args):
    _out(exotic_physics.compute_vacuum_energy(
        omega_lambda=args.omega_lambda, hubble_kms_mpc=args.hubble_kms_mpc, cutoff=args.cutoff))


def cmd_schwinger_limit(args):
    _out(exotic_physics.compute_schwinger_limit(
        field_vm=args.field_vm, intensity_wcm2=args.intensity_wcm2))


def cmd_hubble_flow(args):
    _out(exotic_physics.compute_hubble_flow(
        distance_mpc=args.distance_mpc, distance_ly=args.distance_ly, mass_msun=args.mass_msun,
        radius_ly=args.radius_ly, radius_mpc=args.radius_mpc, hubble_kms_mpc=args.hubble_kms_mpc,
        omega_lambda=args.omega_lambda, omega_m=args.omega_m))


# ── Phase AI (Group O) — black holes & relativistic thermodynamics ────────────

def _bh_mass_kwargs(args):
    return dict(mass_kg=args.mass_kg, mass_msun=args.mass_msun, mass_mearth=args.mass_mearth,
                mass_mjup=args.mass_mjup, object=args.object)


def cmd_schwarzschild_radius(args):
    _out(black_hole.compute_schwarzschild_radius(**_bh_mass_kwargs(args)))


def cmd_hawking_temperature(args):
    _out(black_hole.compute_hawking_temperature(temperature_k=args.temperature_k, **_bh_mass_kwargs(args)))


def cmd_black_hole_evaporation(args):
    _out(black_hole.compute_black_hole_evaporation(lifetime_yr=args.lifetime_yr, **_bh_mass_kwargs(args)))


def cmd_bekenstein_hawking_entropy(args):
    _out(black_hole.compute_bekenstein_hawking_entropy(radius_m=args.radius_m, **_bh_mass_kwargs(args)))


def cmd_isco(args):
    _out(black_hole.compute_isco(spin=args.spin, prograde=not args.retrograde, **_bh_mass_kwargs(args)))


def cmd_kerr_horizon(args):
    _out(black_hole.compute_kerr_horizon(spin=args.spin, **_bh_mass_kwargs(args)))


def cmd_bh_tidal_force(args):
    _out(black_hole.compute_bh_tidal_force(
        distance_m=args.distance_m, distance_rs=args.distance_rs,
        object_length_m=args.object_length_m, threshold_g=args.threshold_g, **_bh_mass_kwargs(args)))


def cmd_eddington_luminosity(args):
    _out(black_hole.compute_eddington_luminosity(efficiency=args.efficiency, **_bh_mass_kwargs(args)))


def cmd_unruh_temperature(args):
    _out(black_hole.compute_unruh_temperature(
        acceleration_ms2=args.acceleration_ms2, acceleration_g=args.acceleration_g,
        temperature_k=args.temperature_k))


def cmd_bekenstein_bound(args):
    _out(black_hole.compute_bekenstein_bound(
        radius_m=args.radius_m, energy_j=args.energy_j, mass_kg=args.mass_kg))


# ── Phase AH (Group N) — Alcubierre / metric drive ────────────────────────────

def cmd_alcubierre_energy(args):
    _out(warp.compute_alcubierre_energy(
        bubble_radius_m=args.bubble_radius_m, velocity_c=args.velocity_c,
        wall_thickness_m=args.wall_thickness_m, formulation=args.formulation,
        neck_radius_m=args.neck_radius_m))


def cmd_warp_metric(args):
    _out(warp.compute_warp_metric(
        bubble_radius_m=args.bubble_radius_m, wall_thickness_sigma=args.wall_thickness_sigma,
        velocity_c=args.velocity_c, r_eval_m=args.r_eval_m, profile=args.profile,
        variant=args.variant))


# ── Phase AJ (Group P) — planet formation (Packet 3.5) ────────────────────────

def cmd_disk_model(args):
    _out(formation.compute_disk_model(
        r_au=args.r_au, r_grid=args.r_grid, mstar_msun=args.mstar_msun,
        disk_mass_mmsn=args.disk_mass_mmsn, disk_mass_msun=args.disk_mass_msun,
        lstar_lsun=args.lstar_lsun, ms_luminosity=args.ms_luminosity,
        feh=args.feh, z=args.z,
        snowline_au=args.snowline_au, snowline_temp_k=args.snowline_temp_k,
        ice_factor=args.ice_factor, mu=args.mu,
        sigma0=args.sigma0, sigma_slope=args.sigma_slope,
        temp0=args.temp0, temp_slope=args.temp_slope))


def cmd_isolation_mass(args):
    _out(formation.compute_isolation_mass(
        sigma_p_gcm2=args.sigma_p_gcm2, a_au=args.a_au, mstar_msun=args.mstar_msun,
        feeding_zone_c=args.feeding_zone_c, feeding_zone_b=args.feeding_zone_b))


def cmd_pebble_isolation_mass(args):
    _out(formation.compute_pebble_isolation_mass(
        hr=args.hr, temp_k=args.temp_k, mstar_msun=args.mstar_msun, a_au=args.a_au,
        alpha=args.alpha, simple=args.simple, dlnp_dlnr=args.dlnp_dlnr,
        peb_norm=args.peb_norm, mu=args.mu))


def cmd_gap_opening_mass(args):
    _out(formation.compute_gap_opening_mass(
        hr=args.hr, temp_k=args.temp_k, mstar_msun=args.mstar_msun, a_au=args.a_au,
        alpha=args.alpha, nu_code=args.nu_code, reynolds=args.reynolds,
        p_target=args.p_target, mu=args.mu))


def cmd_toomre_q(args):
    _out(formation.compute_toomre_q(
        sigma_gcm2=args.sigma_gcm2, temp_k=args.temp_k, cs_ms=args.cs_ms,
        dispersion_ms=args.dispersion_ms, mstar_msun=args.mstar_msun, a_au=args.a_au,
        mu=args.mu, q_crit=args.q_crit))


def cmd_critical_core_mass(args):
    _out(formation.compute_critical_core_mass(
        mdot_core=args.mdot_core, opacity=args.opacity, index=args.index,
        crit_norm=args.crit_norm))


# ── Phase AK (Group Q) — metric-drive power/fuel + exclusion boundary (Pkts 25 / 26.5) ──

def cmd_metric_drive_power(args):
    _out(metric_drive.compute_metric_drive_power(
        mass_kg=args.mass_kg, mass_tonnes=args.mass_tonnes,
        thrust_n=args.thrust_n, accel_g=args.accel_g, accel_ms2=args.accel_ms2,
        delta_v_kms=args.delta_v_kms, delta_v_c=args.delta_v_c, rapidity=args.rapidity,
        duration_days=args.duration_days,
        k=args.k, fuel=args.fuel, f_conv=args.f_conv, eta_dir=args.eta_dir,
        turn=args.turn, integrated_rapidity=args.integrated_rapidity,
        beam_compare=args.beam_compare,
        self_consistent=args.self_consistent, ash=args.ash))


# ── Phase AL (Group R) — power generation / storage / thermal (Pkt 27) ────────

def cmd_annihilation_power_train(args):
    _out(power.compute_annihilation_power_train(
        mass_flow_kgs=args.mass_flow_kgs, power_total_w=args.power_total_w,
        species=args.species, eta_dir=args.eta_dir))


def cmd_antimatter_production(args):
    _out(power.compute_antimatter_production(
        stored_mass_kg=args.stored_mass_kg, stored_energy_j=args.stored_energy_j,
        production_efficiency=args.production_efficiency, trap_field_t=args.trap_field_t))


def cmd_reactor_net_power(args):
    _out(power.compute_reactor_net_power(
        gross_power_w=args.gross_power_w, thermal_efficiency=args.thermal_efficiency,
        q_plasma=args.q_plasma, recirculating_fraction=args.recirculating_fraction))


def cmd_beamed_power_delivery(args):
    _out(power.compute_beamed_power_delivery(
        wavelength_m=args.wavelength_m, frequency_hz=args.frequency_hz,
        tx_aperture_m=args.tx_aperture_m, rx_aperture_m=args.rx_aperture_m,
        range_m=args.range_m, tx_power_w=args.tx_power_w,
        pointing_efficiency=args.pointing_efficiency))


def cmd_fusion_lawson(args):
    _out(power.compute_fusion_lawson(
        fuel=args.fuel, density_m3=args.density_m3, temp_kev=args.temp_kev,
        confinement_s=args.confinement_s, triple_product=args.triple_product,
        confinement_boost=args.confinement_boost))


def cmd_heat_pump(args):
    _out(thermal.compute_heat_pump(
        cold_temp_k=args.cold_temp_k, hot_temp_k=args.hot_temp_k,
        heat_lifted_w=args.heat_lifted_w, work_w=args.work_w,
        efficiency_fraction=args.efficiency_fraction))


def cmd_flywheel_storage(args):
    _out(energy_storage.compute_flywheel_storage(
        tensile_strength_pa=args.tensile_strength_pa, density_kgm3=args.density_kgm3,
        shape_factor=args.shape_factor, mass_kg=args.mass_kg))


def cmd_smes_storage(args):
    _out(energy_storage.compute_smes_storage(
        field_t=args.field_t, critical_field_t=args.critical_field_t,
        tensile_strength_pa=args.tensile_strength_pa, density_kgm3=args.density_kgm3,
        volume_m3=args.volume_m3))


def cmd_energy_storage(args):
    _out(power_tables.compute_energy_storage(
        class_name=args.storage_class, override_wh_kg=args.override_wh_kg,
        mass_kg=args.mass_kg, specific_heat_jkgk=args.specific_heat_jkgk,
        delta_t_k=args.delta_t_k, latent_heat_jkg=args.latent_heat_jkg))


def cmd_reactor_power(args):
    _out(power_tables.compute_reactor_power(
        class_name=args.reactor_class, override_kw_kg=args.override_kw_kg,
        gross_power_w=args.gross_power_w))


# ── Phase AP (Group S) — sensing / detection (Pkt 30) ─────────────────────────

def cmd_angular_resolution(args):
    _out(sensing.compute_angular_resolution(
        aperture_m=args.aperture_m, wavelength_m=args.wavelength_m, frequency_hz=args.frequency_hz,
        range_m=args.range_m, separation_m=args.separation_m, object_size_m=args.object_size_m,
        criterion=args.criterion, coefficient=args.coefficient))


def cmd_point_source_detection(args):
    _out(sensing.compute_point_source_detection(
        source_power_w=args.source_power_w, source_temp_k=args.source_temp_k,
        source_area_m2=args.source_area_m2, emissivity=args.emissivity,
        rx_aperture_m=args.rx_aperture_m, optical_efficiency=args.optical_efficiency,
        range_m=args.range_m, integration_s=args.integration_s,
        quantum_efficiency=args.quantum_efficiency,
        band=args.band, wavelength_m=args.wavelength_m,
        band_min_m=args.band_min_m, band_max_m=args.band_max_m, source_size_m=args.source_size_m,
        nep_w_rthz=args.nep_w_rthz, background=args.background,
        background_intensity_w_m2_sr_m=args.background_intensity_w_m2_sr_m,
        background_temp_k=args.background_temp_k, background_dilution=args.background_dilution,
        flux_floor_w_m2=args.flux_floor_w_m2, snr_threshold=args.snr_threshold))


def cmd_radar_range(args):
    _out(sensing.compute_radar_range(
        tx_power_w=args.tx_power_w, tx_aperture_m=args.tx_aperture_m,
        rx_aperture_m=args.rx_aperture_m, wavelength_m=args.wavelength_m,
        frequency_hz=args.frequency_hz, target_rcs_m2=args.target_rcs_m2,
        range_m=args.range_m, min_detectable_power_w=args.min_detectable_power_w,
        integration_s=args.integration_s, system_noise_temp_k=args.system_noise_temp_k,
        tx_gain=args.tx_gain, rx_gain=args.rx_gain, snr_threshold=args.snr_threshold))


# ── Phase AQ (Group T) — strategic-geography graph analytics (Pkt 32/38) ──────

def cmd_network_centrality(args):
    _out(strategic_geography.compute_network_centrality(
        stars=args.stars, within_ly=args.within_ly, of=args.of, catalog=args.catalog,
        max_jump_ly=args.max_jump, weight=args.weight,
        from_star=args.from_star, to_star=args.to_star, top=args.top,
        dust_map=args.map, dust_step_pc=args.dust_step_pc))


def cmd_arrival_corridors(args):
    _out(strategic_geography.compute_arrival_corridors(
        system=args.system, within_ly=args.within_ly, origins=args.origins,
        corridor_halfwidth_deg=args.corridor_halfwidth_deg, cluster_deg=args.cluster_deg,
        min_jump=args.min_jump, max_jump=args.max_jump))


# ── Phase AR (Group U) — compute / beamrider utilities (Pkt 29/33) ────────────

def cmd_landauer_limit(args):
    _out(thermal.compute_landauer_limit(
        temp_k=args.temp_k, bits=args.bits, power_w=args.power_w,
        bit_rate_hz=args.bit_rate_hz, reversible=args.reversible))


def cmd_beamrider_relay_spacing(args):
    _out(power.compute_beamrider_relay_spacing(
        wavelength_m=args.wavelength_m, frequency_hz=args.frequency_hz,
        tx_aperture_m=args.tx_aperture_m, rx_aperture_m=args.rx_aperture_m,
        delivered_fraction_threshold=args.delivered_fraction_threshold,
        total_range_ly=args.total_range_ly, total_range_m=args.total_range_m))


def _resolve_star_mass_lum(name):
    """Resolve a star name → {"mass": M⊙, "lum": L⊙} via SIMBAD + regions, or {"error"}.

    Reuses the Star System Regions derivation (works for any main-sequence type).
    """
    simbad = databases.compute_simbad_lookup(name)
    if "error" in simbad:
        return simbad
    reg = regions.compute_star_system_regions_from_simbad(simbad)
    if "error" in reg:
        return reg
    mass = reg.get("stellarMass")
    lum = reg.get("bcLuminosity")
    if mass is None or lum is None:
        return {"error": f"Could not derive mass/luminosity for '{name}'."}
    return {"mass": mass, "lum": lum}


def cmd_exclusion_boundary(args):
    sources = [args.mass_msun is not None, bool(args.object),
               bool(args.star), bool(args.spectral_type)]
    if sum(sources) == 0:
        _out({"error": "Provide a body: --mass-msun, --object, --star, or --spectral-type."})
        return
    if sum(sources) > 1:
        _out({"error": "Provide only one body source "
                       "(--mass-msun / --object / --star / --spectral-type)."})
        return

    obj_name = None
    mass = args.mass_msun
    lum = args.luminosity_lsun
    wdot = args.mass_loss_msun_yr

    if args.object:
        key = args.object.lower()
        if key not in exclusion_boundary._OBJECT_PRESETS:
            _out({"error": f"Unknown --object '{args.object}'. Choose from: "
                           f"{', '.join(sorted(exclusion_boundary._OBJECT_PRESETS))}."})
            return
        m_p, l_p, w_p = exclusion_boundary._OBJECT_PRESETS[key]
        mass, obj_name = m_p, key
        if lum is None:
            lum = l_p
        if wdot is None and w_p:
            wdot = w_p
    elif args.star:
        r = _resolve_star_mass_lum(args.star)
        if "error" in r:
            _out(r)
            return
        mass, obj_name = r["mass"], args.star
        if lum is None:
            lum = r["lum"]
    elif args.spectral_type:
        row, key = regions._lookup_spectral_type(args.spectral_type)
        if row is None:
            _out({"error": f"Could not resolve spectral type '{args.spectral_type}'."})
            return
        try:
            mass = float(row.get("M"))
            row_lum = float(row.get("Lum"))
        except (TypeError, ValueError):
            _out({"error": f"Main-sequence row for '{key}' lacks a numeric mass/luminosity."})
            return
        obj_name = key
        if lum is None:
            lum = row_lum

    _out(exclusion_boundary.compute_exclusion_boundary(
        mass_msun=mass,
        luminosity_lsun=(lum if lum is not None else 1.0),
        mass_loss_msun_yr=wdot, wind_state=args.wind_state,
        dial=args.dial, calibration_au=args.calibration_au,
        alpha=args.alpha, beta=args.beta, gamma=args.gamma,
        scan_alpha=args.scan_alpha, object_name=obj_name))


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
        _out({"error": "provide either --teff1/--lum1/--teff2/--lum2 OR "
                       "--star1/--star2, not both"})
        return
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
    _out({"error": "provide all of --teff1/--lum1/--teff2/--lum2, "
                   "or both --star1 and --star2"})


def cmd_cooling_hz(args):
    _out(cooling.compute_cooling_hz(
        args.track,
        mass_solar=args.mass_solar, mass_mjup=args.mass_mjup,
        cooling_age_gyr=args.cooling_age_gyr, teff=args.teff, sma_au=args.sma_au,
        chz_threshold_gyr=args.chz_threshold_gyr, hz_edge=args.hz_edge,
        age_max_gyr=args.age_max_gyr, satellite_density=args.satellite_density,
        cooling_delay_gyr=args.cooling_delay_gyr,
        distillation_teff_k=args.distillation_teff_k,
    ))


# ── Phase V — power / thermal / shielding calculators ─────────────────────────

def cmd_waste_heat(args):
    _out(thermal.compute_waste_heat(
        input_power_watts=args.input_power_watts,
        useful_power_watts=args.useful_power_watts,
        efficiency=args.efficiency,
        hot_temp_k=args.hot_temp_k, cold_temp_k=args.cold_temp_k,
        peak_w=args.peak_w, mean_w=args.mean_w, duty=args.duty,
        pulse_period_s=args.pulse_period_s, storage_mass_kg=args.storage_mass_kg,
        specific_heat_jkgk=args.specific_heat_jkgk,
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
        particle=args.particle, csda_range_gcm2=args.csda_range_gcm2, layers=args.layers,
    ))


def cmd_active_shield(args):
    _out(active_shield.compute_active_shield(
        shield_radius_m=args.shield_radius_m,
        coil_current_a=args.coil_current_a, coil_radius_m=args.coil_radius_m,
        magnetic_moment_am2=args.magnetic_moment_am2,
        field_tesla=args.field_tesla, field_radius_m=args.field_radius_m,
        spectrum_characteristic_rigidity_gv=args.spectrum_characteristic_rigidity_gv,
    ))


def cmd_radiation_ceiling(args):
    _out(radiation.compute_radiation_ceiling(
        absorbed_dose_gy=args.absorbed_dose_gy, fluence=args.fluence,
        let_kev_um=args.let_kev_um, particle_type=args.particle_type,
        energy_mev_amu=args.energy_mev_amu, let_spectrum=args.let_spectrum,
        profile=args.profile, dose_rate=args.dose_rate, dose_rate_unit=args.dose_rate_unit,
        duration=args.duration, duration_unit=args.duration_unit,
        clade=args.clade, pharmacological_dmf=args.pharmacological_dmf,
        career_budget_policy=args.career_budget_policy, ddref=args.ddref,
        lever=args.lever, lever_m_a=args.lever_m_a, lever_m_b=args.lever_m_b,
        allow_p53_double_improve=args.allow_p53_double_improve,
        allow_required_breakthrough=args.allow_required_breakthrough,
        seu_cross_section_cm2=args.seu_cross_section_cm2,
        memory_bits=args.memory_bits, ecc_margin=args.ecc_margin,
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
        ionization_fraction=args.ionization_fraction,
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
        ionization_fraction=args.ionization_fraction,
    ))


# ── Phase AD — momentum / impact tools (C2 pellet-stream, C3 dust-impact) ──────

def cmd_pellet_stream(args):
    _out(propulsion.compute_pellet_stream(
        stream_velocity_kms=args.stream_velocity_kms,
        mass_flow_rate_kgs=args.mass_flow_rate_kgs,
        pellet_mass_kg=args.pellet_mass_kg, pellet_rate_hz=args.pellet_rate_hz,
        velocity_kms=args.velocity_kms, beta=args.beta,
        coupling=args.coupling, vehicle_mass_t=args.vehicle_mass_t,
    ))


def cmd_dust_impact(args):
    _out(dust_impact.compute_dust_impact(
        grain_radius_um=args.grain_radius_um, grain_density_kgm3=args.grain_density_kgm3,
        grain_mass_kg=args.grain_mass_kg,
        velocity_kms=args.velocity_kms, beta=args.beta,
        dust_density_m3=args.dust_density_m3, frontal_area_m2=args.frontal_area_m2,
        path_length_ly=args.path_length_ly,
    ))


# ── Phase AD — megastructure / terraforming tools (C4 orbital-ring, C5 volatile-delivery) ──

def cmd_orbital_ring(args):
    _out(megastructure.compute_orbital_ring(
        body=args.body, surface_gravity_ms2=args.surface_gravity_ms2,
        body_radius_km=args.body_radius_km, altitude_km=args.altitude_km,
        ring_mass_per_length_kgm=args.ring_mass_per_length_kgm,
        rotor_mass_per_length_kgm=args.rotor_mass_per_length_kgm,
    ))


def cmd_volatile_delivery(args):
    _out(volatile_delivery.compute_volatile_delivery(
        body_mass_kg=args.body_mass_kg, volatile_fraction=args.volatile_fraction,
        delta_v_kms=args.delta_v_kms, impact_velocity_kms=args.impact_velocity_kms,
        target_atmosphere_mass_kg=args.target_atmosphere_mass_kg,
        fuel=args.fuel, exhaust_velocity_kms=args.exhaust_velocity_kms,
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
        sed=args.sed,
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


# ── Star-analysis CR-7 — kinematics / population classification ────────────────
# Network only on the --star path (SIMBAD → Hypatia); the --u/--v/--w path is pure-math.

def cmd_population_classify(args):
    _out(kinematics.classify_population(u=args.u, v=args.v, w=args.w, star=args.star))


# ── Star-analysis CR-6 — detection-completeness (pure-math; network only on --star) ──
def cmd_detection_completeness(args):
    app_mag, distance_pc, sp_type = args.app_mag, args.distance_pc, args.sp_type
    if args.star:
        sl = databases.compute_simbad_lookup(args.star)
        if "error" in sl:
            _out(sl)
            return
        if app_mag is None:
            app_mag = sl.get("vmag")
        if distance_pc is None:
            distance_pc = sl.get("parsecs")
        if sp_type is None:
            sp_type = sl.get("sp_type")
    _out(detection.compute_detection_completeness(
        app_mag=app_mag, distance_pc=distance_pc, sp_type=sp_type,
        star_mass_solar=args.star_mass_solar, star_radius_solar=args.star_radius_solar,
        methods=args.methods, sma_grid=args.sma_grid, albedo=args.albedo,
        rv_precision_ms=args.rv_precision_ms, rv_baseline_yr=args.rv_baseline_yr,
        transit_precision_ppm=args.transit_precision_ppm, transit_target=args.transit_target,
        astrom_precision_uas=args.astrom_precision_uas, astrom_baseline_yr=args.astrom_baseline_yr,
        star=args.star,
    ))


# ── Star-analysis CR-4 — nuclear-fuel & radiogenic inventory (pure-math) ───────
def cmd_nuclear_inventory(args):
    _out(nuclear.compute_nuclear_inventory(
        fe_h=args.fe_h, age_gyr=args.age_gyr, eu_h=args.eu_h, eu_fe=args.eu_fe,
        star_mass_solar=args.star_mass_solar, population=args.population,
    ))


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
    import core.dust as dust
    _out(dust.compute_dust_sightline(
        l=args.l, b=args.b, ra=args.ra, dec=args.dec, star=args.star, id=args.id,
        dist_start_pc=args.dist_start, dist_end_pc=args.dist_end,
        n_steps=args.steps, step_pc=args.step_pc, map_sel=args.map,
    ))


def cmd_dust_between(args):
    import core.dust as dust
    _out(dust.compute_dust_between(
        star1=args.star1, id1=args.id1, star2=args.star2, id2=args.id2,
        n_steps=args.steps, step_pc=args.step_pc, map_sel=args.map,
    ))


# ── Phase AM catalog-access tier (LIVE network — CDS VizieR / ESA Gaia / HEASARC) ──

def cmd_vizier_query(args):
    import core.catalog as catalog
    _out(catalog.vizier_query(
        catalog=args.catalog, columns=args.columns, filters=args.filters,
        cone=args.cone, row_limit=args.row_limit,
    ))


def cmd_gaia_tap(args):
    import core.catalog as catalog
    _out(catalog.gaia_tap(
        adql=args.adql, table=args.table, columns=args.columns, where=args.where,
        cone=args.cone, row_limit=args.row_limit, use_async=args.use_async,
    ))


def cmd_heasarc_query(args):
    import core.catalog as catalog
    _out(catalog.heasarc_query(
        catalog=args.catalog, cone=args.cone, radius=args.radius,
        adql=args.adql, row_limit=args.row_limit,
    ))


def cmd_binary_orbit(args):
    import core.binary as binary
    _out(binary.binary_orbit(
        star=args.star, ra=args.ra, dec=args.dec, source_id=args.source_id,
    ))


def cmd_binary_stability_auto(args):
    import core.binary as binary
    _out(binary.binary_stability_auto(
        star=args.star, ra=args.ra, dec=args.dec, source_id=args.source_id,
        test_sma_au=args.test_sma_au,
    ))


def cmd_multiplicity(args):
    import core.binary as binary
    _out(binary.multiplicity_summary(star=args.star, source_id=args.source_id))


def cmd_debris_disk(args):
    import core.debris_disk as debris_disk
    _out(debris_disk.debris_disk(
        star=args.star, source_id=args.source_id, ra=args.ra, dec=args.dec))


def cmd_close_binary_census(args):
    import core.binary as binary
    _out(binary.close_binary_census(
        dist_max_ly=args.dist_max_ly, period_max_d=args.period_max_d,
        sep_max_au=args.sep_max_au, include=tuple(args.include.split(",")),
        parallax_source=args.parallax_source, drop_planets=not args.keep_planets,
        separate_wide=args.separate_wide, exclude_known=args.exclude_known,
    ))


def cmd_gaia_astrophysical(args):
    import core.catalog as catalog
    _out(catalog.gaia_astrophysical(star=args.star, source_id=args.source_id))


def cmd_besancon_query(args):
    import core.besancon as besancon
    _out(besancon.besancon_query(
        glon=args.glon, glat=args.glat, local=args.local, area_deg2=args.area,
        dist_max_pc=args.dist_max_pc, mag_max=args.mag_max, sample_max=args.sample_max,
        contact_email=args.contact_email,
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
        _out({"error": "--solvent and --t-low/--t-high are mutually exclusive"})
        return
    if not args.solvent and not has_custom:
        _out({"error": "provide --solvent NAME or both --t-low and --t-high"})
        return
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
        import core.dust_routing as dust_routing
        _out(dust_routing.compute_optimal_tour_dust(
            args.stars, velocity, use_times_c, closed=args.closed,
            map_sel=args.map, dust_step_pc=args.dust_step_pc,
        ))
    else:
        _out(calculators.compute_optimal_tour(
            args.stars, velocity, use_times_c, closed=args.closed,
        ))


def cmd_jump_route(args):
    weight = getattr(args, "weight", "distance")
    alpha = getattr(args, "alpha", None)
    beta = getattr(args, "beta", None)
    if (alpha is not None or beta is not None) and weight != "blend":
        _out({"error": "--alpha/--beta apply only with --weight blend."})
        return
    via = getattr(args, "via", None)
    if weight == "dust":
        import core.dust_routing as dust_routing
        _out(dust_routing.compute_jump_route_dust(
            args.origin, args.destination, args.max_jump, optimize=args.optimize,
            map_sel=args.map, dust_step_pc=args.dust_step_pc, via=via,
        ))
    elif weight == "blend":
        import core.dust_routing as dust_routing
        _out(dust_routing.compute_jump_route_blend(
            args.origin, args.destination, args.max_jump, optimize=args.optimize,
            alpha=1.0 if alpha is None else alpha, beta=1.0 if beta is None else beta,
            map_sel=args.map, dust_step_pc=args.dust_step_pc, via=via,
        ))
    else:
        _out(calculators.compute_jump_route(
            args.origin, args.destination, args.max_jump, optimize=args.optimize,
            via=via,
        ))


def cmd_jump_network(args):
    _out(calculators.compute_jump_network(
        args.start, args.max_jump, max_jumps=args.max_jumps,
    ))


def cmd_multi_stop(args):
    use_times_c = args.times_c is not None
    velocity = args.times_c if use_times_c else args.ly_hr
    if getattr(args, "weight", "distance") == "dust":
        import core.dust_routing as dust_routing
        _out(dust_routing.compute_multi_stop_dust(
            args.stars, velocity, use_times_c,
            map_sel=args.map, dust_step_pc=args.dust_step_pc,
        ))
    else:
        _out(calculators.compute_multi_stop_journey(args.stars, velocity, use_times_c))


def cmd_nearest_neighbor(args):
    if getattr(args, "weight", "distance") == "dust":
        import core.dust_routing as dust_routing
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
        import core.dust_routing as dust_routing
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
        kcal_per_day=args.kcal_per_day, crew=args.crew, crop=args.crop, crops=args.crops,
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

# ── Phase AT (Packet 38.1) — weapons / defenses / engagement physics ──────────

def cmd_salvo_exchange(args):
    _out(salvo.compute_salvo_exchange(
        a_force=args.a_force, b_force=args.b_force,
        alpha=args.alpha, beta=args.beta, a_salvo=args.a_salvo, b_salvo=args.b_salvo,
        a_hitprob=args.a_hitprob, b_hitprob=args.b_hitprob,
        a1_staying=args.a1_staying, b1_staying=args.b1_staying,
        a3_defense=args.a3_defense, b3_defense=args.b3_defense,
        sigma_a=args.sigma_a, sigma_b=args.sigma_b, delta_a=args.delta_a, delta_b=args.delta_b,
        leak_a=args.leak_a, leak_b=args.leak_b,
        mode=args.mode, first=args.first, wave_size=args.wave_size, n_waves=args.n_waves,
        defender_magazine=args.defender_magazine, defender_preempts=args.defender_preempts,
        target_delta=args.target_delta, target_frac_loss=args.target_frac_loss,
        solve_for=args.solve_for, target_side=args.target_side, fire_fraction=args.fire_fraction,
        rings=args.rings, inbound_salvo=args.inbound_salvo, scouting=args.scouting,
        target_staying=args.target_staying,
    ))


def cmd_beam_weapon_engagement(args):
    _out(weapons.compute_beam_weapon_engagement(
        aperture_m=args.aperture_m, wavelength_m=args.wavelength_m, frequency_hz=args.frequency_hz,
        power_w=args.power_w, beam_quality_m2=args.beam_quality_m2,
        pointing_efficiency=args.pointing_efficiency, rayleigh_k=args.rayleigh_k,
        target_size_m=args.target_size_m, range_m=args.range_m,
        kill_fluence_jm2=args.kill_fluence_jm2,
        target_material_enthalpy_jkg=args.target_material_enthalpy_jkg,
        target_areal_density_kgm2=args.target_areal_density_kgm2, max_dwell_s=args.max_dwell_s,
    ))


def cmd_kinetic_kill(args):
    _out(weapons.compute_kinetic_kill(
        mass_kg=args.mass_kg, length_m=args.length_m, diameter_m=args.diameter_m,
        density_kgm3=args.density_kgm3, velocity_kms=args.velocity_kms, beta=args.beta,
        target_density_kgm3=args.target_density_kgm3, target_type=args.target_type,
        armor_thickness_m=args.armor_thickness_m,
        bumper_areal_density_kgm2=args.bumper_areal_density_kgm2, standoff_m=args.standoff_m,
        rearwall_areal_density_kgm2=args.rearwall_areal_density_kgm2,
        target_sound_speed_ms=args.target_sound_speed_ms, crater_exponent=args.crater_exponent,
        debris_cone_half_angle_deg=args.debris_cone_half_angle_deg,
    ))


def cmd_warhead_effects(args):
    _out(weapons.compute_warhead_effects(
        yield_j=args.yield_j, yield_kt=args.yield_kt, warhead_type=args.warhead_type,
        f_xray=args.f_xray, f_neutron=args.f_neutron, f_debris=args.f_debris, f_gamma=args.f_gamma,
        standoff_m=args.standoff_m,
        threshold_xray_jm2=args.threshold_xray_jm2, threshold_neutron_jm2=args.threshold_neutron_jm2,
        threshold_debris_jm2=args.threshold_debris_jm2, threshold_gamma_jm2=args.threshold_gamma_jm2,
    ))


def main(argv=None):
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

    # oec-system
    p = sub.add_parser("oec-system",
                       help="Open Exoplanet Catalogue: full system hierarchy tree by name")
    p.add_argument("--name", required=True, help="Star or planet name / designation")
    p.set_defaults(func=cmd_oec_system)

    # oec-planet
    p = sub.add_parser("oec-planet",
                       help="Open Exoplanet Catalogue: a planet node + its host chain")
    p.add_argument("--name", required=True, help="Planet name / designation")
    p.set_defaults(func=cmd_oec_planet)

    # oec-search
    p = sub.add_parser(
        "oec-search",
        help="Open Exoplanet Catalogue: structural search over all systems")
    p.add_argument("--min-stars", type=int, help="minimum number of stars in the system")
    p.add_argument("--max-stars", type=int, help="maximum number of stars in the system")
    p.add_argument("--status",
                   help="planet status substring, e.g. 'Confirmed', 'Controversial', 'P-type'")
    p.add_argument("--circumbinary", action="store_true",
                   help="only systems with a circumbinary (P-type) planet")
    p.add_argument("--discovery-method",
                   help="planet discovery-method substring, e.g. 'transit', 'RV', 'imaging'")
    p.add_argument("--discovery-year-min", type=int)
    p.add_argument("--discovery-year-max", type=int)
    p.add_argument("--mass-min", type=float, help="planet mass ≥ (Jupiter masses)")
    p.add_argument("--mass-max", type=float, help="planet mass ≤ (Jupiter masses)")
    p.add_argument("--radius-min", type=float, help="planet radius ≥ (Jupiter radii)")
    p.add_argument("--radius-max", type=float, help="planet radius ≤ (Jupiter radii)")
    p.add_argument("--period-min", type=float, help="planet orbital period ≥ (days)")
    p.add_argument("--period-max", type=float, help="planet orbital period ≤ (days)")
    p.add_argument("--sma-min", type=float, help="planet semi-major axis ≥ (AU)")
    p.add_argument("--sma-max", type=float, help="planet semi-major axis ≤ (AU)")
    p.add_argument("--spectral-type",
                   help="host star spectral-type prefix, e.g. 'G', 'M', 'DA' (white dwarf)")
    p.add_argument("--limit", type=int,
                   help="max systems to return (default 300)")
    p.set_defaults(func=cmd_oec_search)

    # oec-census
    p = sub.add_parser(
        "oec-census",
        help="Open Exoplanet Catalogue: catalogue-wide topology statistics")
    p.set_defaults(func=cmd_oec_census)

    # oec-status
    p = sub.add_parser(
        "oec-status",
        help="Open Exoplanet Catalogue: cache snapshot (freshness) + element counts")
    p.set_defaults(func=cmd_oec_status)

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
    p.add_argument("--luminosity", "--luminosity-lsun", dest="luminosity",
                   required=True, type=float, help="Stellar luminosity in solar units")
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
    p.add_argument("--cooling-delay-gyr", type=float, default=0.0,
                   help="²²Ne distillation cooling pause in Gyr (WD only; default 0 = off). Freezes "
                        "Teff/L/R at the distillation epoch for this long, lengthening HZ residence.")
    p.add_argument("--distillation-teff-k", type=float, default=5500.0,
                   help="Teff K at which the distillation pause onsets (default 5500, the 0.6 M_sun "
                        "DA onset of Vanderburg et al. 2025, arXiv:2501.06613)")
    p.set_defaults(func=cmd_cooling_hz)

    # waste-heat (Phase V — power → rejected-heat budget, with Carnot ceiling)
    p = sub.add_parser("waste-heat",
                       help="Waste heat a device must reject from a power figure + efficiency (with Carnot ceiling)")
    # Not required: transient mode (below) uses no steady power anchor. Both given → mutex exit 2;
    # neither given + not transient → the core "no power anchor" error (exit 1).
    g = p.add_mutually_exclusive_group()
    g.add_argument("--input-power-watts",  type=float, help="Gross input/thermal power, W")
    g.add_argument("--useful-power-watts", type=float, help="Net useful output power, W")
    p.add_argument("--efficiency", type=float, help="Conversion/thermal efficiency η (0 < η ≤ 1)")
    p.add_argument("--hot-temp-k",  type=float, help="Hot-reservoir temperature K (for the Carnot ceiling)")
    p.add_argument("--cold-temp-k", type=float, help="Cold-reservoir temperature K (for the Carnot ceiling)")
    # C9 — transient/pulsed thermal-buffer mode (all six together)
    p.add_argument("--peak-w", type=float, help="Peak dissipated power W (transient mode)")
    p.add_argument("--mean-w", type=float, help="Time-average power W the radiator is sized for (transient mode)")
    p.add_argument("--duty", type=float, help="On-fraction of the pulse cycle, 0 < d ≤ 1 (transient mode)")
    p.add_argument("--pulse-period-s", type=float, help="Pulse cycle period s (transient mode)")
    p.add_argument("--storage-mass-kg", type=float, help="Thermal-buffer mass kg (transient mode)")
    p.add_argument("--specific-heat-jkgk", type=float, help="Buffer specific heat J/kg·K (transient mode)")
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
    p.add_argument("--energy-mev", type=float, help="Photon/particle energy MeV for the bundled lookup")
    # C6 — charged-particle CSDA range
    p.add_argument("--particle", choices=["photon", "proton", "alpha", "ion"], default="photon",
                   help="photon (default; Lambert–Beer/GCR) or a charged particle (CSDA stopping range)")
    p.add_argument("--csda-range-gcm2", type=float,
                   help="Explicit CSDA range g/cm² for a charged particle (overrides the bundled table)")
    # C7 — multi-layer stack
    p.add_argument("--layers", help="Stacked shield 'mat:gcm2, mat:gcm2, …' → per-layer product transmitted fraction")
    p.set_defaults(func=cmd_shielding_attenuation)

    # active-shield (Phase AD C8 — magnetic rigidity cutoff / deflection)
    p = sub.add_parser("active-shield",
                       help="Active magnetic-shield rigidity cutoff (Störmer) + deflected fraction "
                            "+ field, from a dipole moment / coil / field×scale")
    p.add_argument("--shield-radius-m", type=float, required=True,
                   help="Protected-region radius r (m) at which the cutoff is evaluated")
    p.add_argument("--magnetic-moment-am2", type=float, help="Magnetic dipole moment A·m² (field source)")
    p.add_argument("--coil-current-a", type=float, help="Coil current A (with --coil-radius-m; field source)")
    p.add_argument("--coil-radius-m", type=float, help="Coil radius m (with --coil-current-a)")
    p.add_argument("--field-tesla", type=float, help="Field magnitude T at --field-radius-m (field source)")
    p.add_argument("--field-radius-m", type=float, help="Radius m at which --field-tesla is specified")
    p.add_argument("--spectrum-characteristic-rigidity-gv", type=float,
                   help="Characteristic rigidity R_s (GV) of the incident spectrum → deflected fraction")
    p.set_defaults(func=cmd_active_shield)

    # radiation-ceiling (Phase AS / Packet 34 — physical dose → per-clade two-axis biological ceiling)
    p = sub.add_parser("radiation-ceiling",
                       help="Physical radiation dose → per-clade biological ceiling: Axis A "
                            "(acute/deterministic, Gy) + Axis B (stochastic/cancer, Sv REID); "
                            "upload → SEU/bit-error budget")
    # Exposure magnitude (exactly one; or an --let-spectrum which is self-contained)
    p.add_argument("--absorbed-dose-gy", type=float, help="Absorbed dose (Gy) — needs a quality input")
    p.add_argument("--fluence", type=float, help="Particle fluence (cm⁻²) — with a quality, derives dose")
    # Radiation quality
    p.add_argument("--let-kev-um", type=float, help="Unrestricted LET (keV/µm) for the RBE/Q weighting")
    p.add_argument("--particle-type", choices=radiation.t.particle_names(),
                   help="Particle preset → representative LET (coarse; use --let-kev-um for precision)")
    p.add_argument("--energy-mev-amu", type=float, help="Particle energy (MeV/amu) — echoed for provenance")
    p.add_argument("--let-spectrum", help="Composite field 'LET:fluence, LET:fluence, …' (the GCR/HZE form)")
    # Temporal profile
    p.add_argument("--profile", choices=["acute", "chronic"], default="acute",
                   help="acute (single delivery, drives Axis A) or chronic (Axis B + rate check)")
    p.add_argument("--dose-rate", type=float, help="Chronic dose rate (with --dose-rate-unit)")
    p.add_argument("--dose-rate-unit", choices=["gy/day", "sv/yr"], default="gy/day",
                   help="Unit for --dose-rate (default gy/day)")
    p.add_argument("--duration", type=float, help="Chronic exposure duration (with --duration-unit)")
    p.add_argument("--duration-unit", choices=["days", "yr"], default="days",
                   help="Unit for --duration (default days)")
    # Clade + modifiers
    p.add_argument("--clade", choices=radiation.t.CLADE_NAMES, default="baseline-human",
                   help="Crew substrate: baseline-human / gene-mod / cyborg / upload / custom")
    p.add_argument("--pharmacological-dmf", type=float,
                   help="Pharmacological dose-modification factor (Axis A; clamped at 3× — S10)")
    p.add_argument("--career-budget-policy", choices=list(radiation.t.CAREER_BUDGETS),
                   help="Career REID budget policy in mSv (default 600; policy, not physics)")
    p.add_argument("--ddref", type=float,
                   help="Dose-and-dose-rate effectiveness factor (chronic Axis B; default 1.0 inert). "
                        "Disputed; NOTE --ddref>1 makes REID disagree with the NASA 600 mSv@3%% policy pairing")
    # Lever (custom-clade coupling; cases 5 & 7)
    p.add_argument("--lever", choices=list(radiation.t.LEVER_TYPES),
                   help="Add a lever: repair-fidelity (may improve both) or p53 (acute↑ forces cancer↑)")
    p.add_argument("--lever-m-a", type=float, help="Lever acute factor f_a (>1 raises, <1 lowers the ceiling)")
    p.add_argument("--lever-m-b", type=float, help="Lever stochastic factor f_b (<1 improves, >1 worsens REID/Sv)")
    p.add_argument("--allow-p53-double-improve", action="store_true",
                   help="Override the p53 hard block (S15 abstract-only — re-open before canon)")
    p.add_argument("--allow-required-breakthrough", action="store_true",
                   help="Permit an organism-scale ceiling beyond the Deinococcus ~5000 Gy existence proof")
    # SEU / bit-error budget (upload + cyborg hardware fraction)
    p.add_argument("--seu-cross-section-cm2", type=float, help="Per-bit upset cross-section (default 1e-14)")
    p.add_argument("--memory-bits", type=float, help="Memory size (bits) → expected upsets")
    p.add_argument("--ecc-margin", type=float, help="Redundancy/ECC upset margin → within-margin flag")
    p.set_defaults(func=cmd_radiation_ceiling)

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
    p.add_argument("--ionization-fraction", type=float,
                   help="Ionized fraction of the ISM that couples magnetically, 0<x≤1 (default 1.0)")
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
    p.add_argument("--ionization-fraction", type=float,
                   help="Ionized fraction of the ISM that couples magnetically, 0<x≤1 (default 1.0)")
    p.set_defaults(func=cmd_ramscoop)

    # pellet-stream (Phase AD C2 — momentum-beam drive: thrust/power/drive-verdict; the mass
    # analog of ramscoop)
    p = sub.add_parser("pellet-stream",
                       help="Pellet-stream (momentum-beam) drive: thrust, delivered power, and "
                            "drive/no-thrust verdict from the closing velocity")
    p.add_argument("--stream-velocity-kms", type=float, required=True,
                   help="Pellet stream velocity v_s, km/s")
    m = p.add_mutually_exclusive_group()
    m.add_argument("--mass-flow-rate-kgs", type=float, help="Stream mass-flow rate ṁ, kg/s (mass anchor)")
    m.add_argument("--pellet-mass-kg", type=float, help="Per-pellet mass, kg (with --pellet-rate-hz → ṁ)")
    p.add_argument("--pellet-rate-hz", type=float, help="Pellet arrival rate, Hz (with --pellet-mass-kg)")
    v = p.add_mutually_exclusive_group()
    v.add_argument("--velocity-kms", type=float, help="Vehicle velocity, km/s (velocity anchor; admits 0)")
    v.add_argument("--beta", type=float, help="Vehicle velocity as a fraction of c, 0<β<1 (velocity anchor)")
    p.add_argument("--coupling", choices=["reflect", "absorb"], default="reflect",
                   help="reflect (elastic, g=2) / absorb (inelastic, g=1); default reflect")
    p.add_argument("--vehicle-mass-t", type=float, help="Vehicle mass, t (→ acceleration)")
    p.set_defaults(func=cmd_pellet_stream)

    # dust-impact (Phase AD C3 — hypervelocity grain impact energetics; penetration handed off
    # to the Packet-13 shielding tools)
    p = sub.add_parser("dust-impact",
                       help="Hypervelocity dust-grain impact: kinetic energy, TNT-equivalent, "
                            "momentum, and optional cumulative impacts/fluence over an ISM column")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--grain-radius-um", type=float, help="Grain radius, µm (with --grain-density-kgm3 → mass)")
    g.add_argument("--grain-mass-kg", type=float, help="Explicit grain mass, kg (grain anchor)")
    p.add_argument("--grain-density-kgm3", type=float, help="Grain density, kg/m³ (with --grain-radius-um)")
    v = p.add_mutually_exclusive_group()
    v.add_argument("--velocity-kms", type=float, help="Impact velocity, km/s (velocity anchor)")
    v.add_argument("--beta", type=float, help="Impact velocity as a fraction of c, 0<β<1 (velocity anchor)")
    p.add_argument("--dust-density-m3", type=float,
                   help="ISM grain number density, m⁻³ (with --frontal-area-m2 + --path-length-ly)")
    p.add_argument("--frontal-area-m2", type=float, help="Vehicle frontal area, m² (cumulative set)")
    p.add_argument("--path-length-ly", type=float, help="Path length through the column, ly (cumulative set)")
    p.set_defaults(func=cmd_dust_impact)

    # orbital-ring (Phase AD C4 — stationary ring held up by a faster-than-orbital rotor)
    p = sub.add_parser("orbital-ring",
                       help="Orbital-ring rotor velocity & support balance: local gravity, "
                            "orbital vs rotor velocity, and rotor KE per unit length")
    p.add_argument("--body", choices=sorted(megastructure.materials_tables._BODIES),
                   help="Bundled body (g₀ + surface radius); mutually exclusive with the explicit pair")
    p.add_argument("--surface-gravity-ms2", type=float, help="Explicit surface gravity g₀, m/s²")
    p.add_argument("--body-radius-km", type=float, help="Explicit body surface radius, km")
    p.add_argument("--altitude-km", required=True, type=float, help="Ring altitude above the surface, km")
    p.add_argument("--ring-mass-per-length-kgm", required=True, type=float,
                   help="Ring (sheath) mass per unit length λ_ring, kg/m")
    p.add_argument("--rotor-mass-per-length-kgm", type=float,
                   help="Rotor mass per unit length λ_rotor, kg/m (default = λ_ring → v_rotor=√2·v_orb)")
    p.set_defaults(func=cmd_orbital_ring)

    # volatile-delivery (Phase AD C5 — cometary bombardment for terraforming; the supply side of
    # atmosphere-mass)
    p = sub.add_parser("volatile-delivery",
                       help="Volatile delivery by icy-body redirect: delivered mass, redirect mass "
                            "ratio, impact energy, and bodies needed for a target atmosphere")
    p.add_argument("--body-mass-kg", required=True, type=float, help="Redirected body mass M, kg")
    p.add_argument("--volatile-fraction", type=float, default=0.5,
                   help="Volatile mass fraction f of the body, (0,1] (default 0.5)")
    p.add_argument("--delta-v-kms", type=float,
                   help="Redirect Δv, km/s (with one exhaust anchor → redirect mass ratio)")
    p.add_argument("--fuel", choices=sorted(propulsion.propulsion_tables._FUELS),
                   help="Bundled ideal exhaust velocity by fuel (exhaust anchor, with --delta-v-kms)")
    p.add_argument("--exhaust-velocity-kms", type=float,
                   help="Explicit exhaust velocity v_e, km/s (exhaust anchor, with --delta-v-kms)")
    p.add_argument("--impact-velocity-kms", type=float, help="Impact velocity, km/s (→ impact energy)")
    p.add_argument("--target-atmosphere-mass-kg", type=float,
                   help="Target atmosphere mass, kg (→ bodies needed)")
    p.set_defaults(func=cmd_volatile_delivery)

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
    g.add_argument("--luminosity-lsun", "--luminosity", dest="luminosity_lsun",
                   type=float, help="Stellar luminosity in solar units")
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
    p.add_argument("--luminosity-lsun", "--luminosity", dest="luminosity_lsun",
                   type=float, help="Stellar luminosity in solar units (with --distance-au)")
    p.add_argument("--distance-au", type=float, help="Orbital distance, AU (with --luminosity-lsun)")
    p.add_argument("--par-band-nm", type=float, nargs=2, default=[400.0, 700.0],
                   metavar=("LO", "HI"), help="PAR band in nm (default 400 700)")
    p.add_argument("--sed", choices=["blackbody", "real"], default="blackbody",
                   help="SED model: blackbody (default, Planck at Teff) or real (BT-Settl "
                        "f_PAR table, band-fixed 400–700 nm, 2600–7000 K)")
    p.set_defaults(func=cmd_par_flux)

    # equilibrium-temp (Phase AB — planetary equilibrium + greenhouse surface temperature)
    p = sub.add_parser("equilibrium-temp",
                       help="Planetary equilibrium temperature + greenhouse surface temp (offset/grey/inverse)")
    p.add_argument("--insolation-wm2", type=float, help="Insolation at the planet, W/m²")
    p.add_argument("--luminosity-lsun", "--luminosity", dest="luminosity_lsun",
                   type=float, help="Stellar luminosity in solar units (with --distance-au)")
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
    p.add_argument("--luminosity-lsun", "--luminosity", dest="luminosity_lsun",
                   type=float, help="Stellar luminosity in solar units (with --distance-au)")
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
    p.add_argument("--crops",
                   help="Diet mix as \"crop:frac, crop:frac, …\" (calorie fractions summing to 1.0); "
                        "per-crop area at each crop's HI/productivity. Mutually exclusive with --crop.")
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

    # ── Star-analysis CR-7 — kinematics / population classification ───────────
    # population-classify: thin/thick/halo verdict from heliocentric U/V/W or a star id.
    p = sub.add_parser("population-classify",
                       help="Thin/thick/halo Galactic-population verdict from U/V/W or a star id")
    p.add_argument("--star", help="Star identifier (SIMBAD → Hypatia; live network)")
    p.add_argument("--u", type=float, help="Heliocentric U velocity, km/s (toward Galactic centre)")
    p.add_argument("--v", type=float, help="Heliocentric V velocity, km/s (along Galactic rotation)")
    p.add_argument("--w", type=float, help="Heliocentric W velocity, km/s (toward north Galactic pole)")
    p.set_defaults(func=cmd_population_classify)

    # ── Star-analysis CR-4 — nuclear-fuel & radiogenic inventory ──────────────
    # nuclear-inventory: fusion + fissile (per-isotope GCE) + radiogenic heat from stellar scalars.
    p = sub.add_parser("nuclear-inventory",
                       help="Fusion-fuel + fissile (U/Th) + radiogenic-heat inventory from stellar scalars")
    p.add_argument("--fe-h", required=True, type=float, help="[Fe/H] (dex)")
    p.add_argument("--age-gyr", required=True, type=float, help="Stellar age (Gyr)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--eu-h", type=float, help="r-process tracer [Eu/H] (dex)")
    g.add_argument("--eu-fe", type=float, help="r-process tracer [Eu/Fe] (dex; → [Eu/H]=[Eu/Fe]+[Fe/H])")
    p.add_argument("--star-mass-solar", type=float, help="Stellar mass (M☉, optional)")
    p.add_argument("--population", choices=["thin", "thick", "halo"],
                   help="Galactic population tag (CR-7 verdict; optional)")
    p.set_defaults(func=cmd_nuclear_inventory)

    # ── Star-analysis CR-6 — detection-completeness ───────────────────────────
    # detection-completeness: min detectable planet vs SMA per method (RV/transit/astrometry/imaging).
    p = sub.add_parser("detection-completeness",
                       help="Per-method minimum detectable planet (mass/radius) vs orbital SMA")
    p.add_argument("--star", help="Star identifier (SIMBAD → app mag / distance / sp-type; live network)")
    p.add_argument("--app-mag", type=float, help="Apparent magnitude (method working band)")
    p.add_argument("--distance-pc", type=float, help="Distance in parsecs")
    p.add_argument("--sp-type", help="Spectral type (→ star mass/radius if not given)")
    p.add_argument("--star-mass-solar", type=float)
    p.add_argument("--star-radius-solar", type=float)
    p.add_argument("--methods", nargs="+", choices=["rv", "transit", "astrometry", "imaging"],
                   help="Subset of methods (default all)")
    p.add_argument("--sma-grid", nargs="+", type=float, help="Orbital SMA grid in AU (default log grid)")
    p.add_argument("--albedo", type=float, default=0.3)
    p.add_argument("--rv-precision-ms", type=float, help="Per-star RV precision override (m/s)")
    p.add_argument("--rv-baseline-yr", type=float)
    p.add_argument("--transit-precision-ppm", type=float, help="Per-star transit photometric precision (ppm)")
    p.add_argument("--transit-target", action="store_true",
                   help="Treat the star as a covered transit target (else 'not applicable')")
    p.add_argument("--astrom-precision-uas", type=float, help="Per-star astrometric precision override (µas)")
    p.add_argument("--astrom-baseline-yr", type=float)
    p.set_defaults(func=cmd_detection_completeness)

    # ── Phase AE (Group K) — arrival geometry & gravitation (Pkt 20) ──────────

    # escape-velocity (K1)
    p = sub.add_parser("escape-velocity",
                       help="Escape / circular speed from a body or at a distance in its field")
    p.add_argument("--mass-kg", type=float); p.add_argument("--mass-msun", type=float)
    p.add_argument("--mass-mearth", type=float); p.add_argument("--mass-mjup", type=float)
    p.add_argument("--radius-m", type=float); p.add_argument("--radius-rsun", type=float)
    p.add_argument("--radius-rearth", type=float); p.add_argument("--distance-au", type=float)
    p.add_argument("--body", choices=gravitation.astro_bodies.BODY_PRESET_KEYS,
                   help="Body preset (fills mass + radius)")
    p.set_defaults(func=cmd_escape_velocity)

    # gravitational-potential (K2)
    p = sub.add_parser("gravitational-potential",
                       help="Gravity-well depth, binding energy, and climb-out Δv between two radii")
    p.add_argument("--mass-kg", type=float); p.add_argument("--mass-msun", type=float)
    p.add_argument("--mass-mearth", type=float); p.add_argument("--mass-mjup", type=float)
    p.add_argument("--body", choices=gravitation.astro_bodies.BODY_PRESET_KEYS,
                   help="Body preset (fills mass)")
    p.add_argument("--r-from-m", type=float); p.add_argument("--r-from-au", type=float)
    p.add_argument("--r-to-m", type=float); p.add_argument("--r-to-au", type=float,
                   help="Upper radius (default ∞)")
    p.add_argument("--payload-kg", type=float, help="Payload mass → binding energy (J)")
    p.set_defaults(func=cmd_gravitational_potential)

    # sphere-of-influence (K3)
    p = sub.add_parser("sphere-of-influence",
                       help="Laplace sphere of influence + Hill radius for a body orbiting a primary")
    p.add_argument("--body-mass-kg", type=float); p.add_argument("--body-mass-msun", type=float)
    p.add_argument("--body-mass-mearth", type=float); p.add_argument("--body-mass-mjup", type=float)
    p.add_argument("--primary-mass-kg", type=float); p.add_argument("--primary-mass-msun", type=float)
    p.add_argument("--primary-mass-mearth", type=float); p.add_argument("--primary-mass-mjup", type=float)
    p.add_argument("--primary", choices=gravitation.astro_bodies.BODY_PRESET_KEYS,
                   help="Primary preset (fills primary mass)")
    p.add_argument("--semimajor-au", type=float, help="Orbit semi-major axis (AU)")
    p.set_defaults(func=cmd_sphere_of_influence)

    # hyperbolic-approach (K4)
    p = sub.add_parser("hyperbolic-approach",
                       help="Braking-corridor geometry for a hyperbolic arrival (v_p, C3, capture Δv)")
    p.add_argument("--mass-kg", type=float); p.add_argument("--mass-msun", type=float)
    p.add_argument("--mass-mearth", type=float); p.add_argument("--mass-mjup", type=float)
    p.add_argument("--body", choices=gravitation.astro_bodies.BODY_PRESET_KEYS,
                   help="Body preset (fills mass + radius, enabling --periapsis-rbody)")
    p.add_argument("--v-infinity-kms", type=float, help="Hyperbolic excess speed v∞ (km/s)")
    p.add_argument("--arrival-speed-kms", type=float, help="Arrival speed at --r-from (km/s)")
    p.add_argument("--r-from-km", type=float); p.add_argument("--r-from-au", type=float)
    p.add_argument("--periapsis-km", type=float); p.add_argument("--periapsis-rbody", type=float,
                   help="Periapsis in body radii (needs --body or a known radius)")
    p.add_argument("--target", choices=["circular", "parabolic", "elliptical"], default="circular")
    p.add_argument("--target-apoapsis-km", type=float); p.add_argument("--target-apoapsis-au", type=float)
    p.set_defaults(func=cmd_hyperbolic_approach)

    # ── Phase AF (Group L) — special relativity & causality (Pkt 23) ──────────

    # time-dilation (L1)
    p = sub.add_parser("time-dilation",
                       help="Special and/or gravitational time dilation")
    p.add_argument("--velocity-c", type=float); p.add_argument("--velocity-kms", type=float)
    p.add_argument("--proper-time", type=float); p.add_argument("--coordinate-time", type=float)
    p.add_argument("--mass-kg", type=float); p.add_argument("--mass-msun", type=float)
    p.add_argument("--mass-mearth", type=float); p.add_argument("--mass-mjup", type=float)
    p.add_argument("--body", choices=relativity.astro_bodies.BODY_PRESET_KEYS,
                   help="Body preset for the gravitational source (fills mass + radius)")
    p.add_argument("--radius-m", type=float); p.add_argument("--radius-rsun", type=float)
    p.add_argument("--radius-rearth", type=float); p.add_argument("--distance-au", type=float)
    p.add_argument("--combined", action="store_true",
                   help="Multiply the special and gravitational factors")
    p.set_defaults(func=cmd_time_dilation)

    # length-contraction (L2)
    p = sub.add_parser("length-contraction", help="Relativistic length contraction L = L₀/γ")
    p.add_argument("--velocity-c", type=float); p.add_argument("--velocity-kms", type=float)
    p.add_argument("--proper-length", type=float); p.add_argument("--contracted-length", type=float)
    p.set_defaults(func=cmd_length_contraction)

    # velocity-addition (L3)
    p = sub.add_parser("velocity-addition", help="Relativistic velocity addition")
    p.add_argument("--u-c", required=True, type=float, help="First velocity (fraction of c)")
    p.add_argument("--v-c", required=True, type=float, help="Second velocity (fraction of c)")
    p.add_argument("--perpendicular", action="store_true", help="Perpendicular (transverse) case")
    p.set_defaults(func=cmd_velocity_addition)

    # relativistic-doppler (L4)
    p = sub.add_parser("relativistic-doppler", help="Relativistic Doppler factor + shifted λ/f")
    p.add_argument("--velocity-c", type=float); p.add_argument("--velocity-kms", type=float)
    p.add_argument("--approach", action="store_true"); p.add_argument("--recede", action="store_true")
    p.add_argument("--angle-deg", type=float, help="Observation angle (0=approach, 180=recede, 90=transverse)")
    p.add_argument("--rest-wavelength-nm", type=float); p.add_argument("--rest-frequency-hz", type=float)
    p.set_defaults(func=cmd_relativistic_doppler)

    # rapidity (L5)
    p = sub.add_parser("rapidity", help="Rapidity φ = artanh(β); linear composition via --add")
    p.add_argument("--velocity-c", type=float); p.add_argument("--rapidity", type=float)
    p.add_argument("--add", help="Comma-separated β list to compose, e.g. '0.6,0.6,0.6'")
    p.set_defaults(func=cmd_rapidity)

    # relativistic-energy-momentum (L6)
    p = sub.add_parser("relativistic-energy-momentum",
                       help="Relativistic energy, momentum, and kinetic energy of a particle")
    p.add_argument("--mass-kg", type=float); p.add_argument("--mass-mev", type=float)
    p.add_argument("--velocity-c", type=float); p.add_argument("--gamma", type=float)
    p.add_argument("--kinetic-energy-j", type=float); p.add_argument("--momentum", type=float)
    p.set_defaults(func=cmd_relativistic_energy_momentum)

    # lorentz-transform (L7)
    p = sub.add_parser("lorentz-transform", help="Lorentz coordinate transform + simultaneity offset")
    p.add_argument("--velocity-c", required=True, type=float, help="Boost velocity (fraction of c)")
    p.add_argument("--t", type=float, help="Event time (s)"); p.add_argument("--x", type=float, help="Event position (m)")
    p.add_argument("--t-yr", type=float, help="Event time (years)"); p.add_argument("--x-ly", type=float, help="Event position (ly)")
    p.add_argument("--inverse", action="store_true", help="Apply the inverse transform")
    p.add_argument("--event2", help="Second event 't2,x2' → relativity-of-simultaneity offset")
    p.set_defaults(func=cmd_lorentz_transform)

    # causality-check (L8)
    p = sub.add_parser("causality-check",
                       help="FTL tachyonic-antitelephone causality guardrail")
    p.add_argument("--signal-speed-c", type=float, help="FTL signal speed (units of c, >1 for FTL)")
    p.add_argument("--instant", action="store_true", help="Instantaneous signal (u → ∞)")
    p.add_argument("--frame-velocity-c", type=float, help="Relative frame velocity (fraction of c)")
    p.add_argument("--preferred-frame", action="store_true", help="Assert a universal FTL rest frame")
    p.add_argument("--two-jump", action="store_true", help="Explicit two-jump antitelephone framing")
    p.set_defaults(func=cmd_causality_check)

    # ── Phase AG (Group M) — exotic vacuum & cosmology (Pkt 21) ───────────────

    # casimir (M1)
    p = sub.add_parser("casimir", help="Casimir pressure / negative energy density (or sphere-plate force)")
    p.add_argument("--separation-m", type=float); p.add_argument("--separation-nm", type=float)
    p.add_argument("--area-m2", type=float, help="Plate area (default 1 m²)")
    p.add_argument("--geometry", choices=["parallel-plate", "sphere-plate"], default="parallel-plate")
    p.add_argument("--sphere-radius-m", type=float, help="Sphere radius (sphere-plate geometry)")
    p.set_defaults(func=cmd_casimir)

    # vacuum-energy (M2)
    p = sub.add_parser("vacuum-energy", help="Dark-energy density + the QED vacuum-catastrophe ratio")
    p.add_argument("--omega-lambda", type=float, help="Dark-energy density parameter (default 0.685)")
    p.add_argument("--hubble-kms-mpc", type=float, help="Hubble constant (default 67.4)")
    p.add_argument("--cutoff", default="planck",
                   help="QED cutoff: planck/electroweak/qcd or a number in GeV")
    p.set_defaults(func=cmd_vacuum_energy)

    # schwinger-limit (M3)
    p = sub.add_parser("schwinger-limit", help="Schwinger critical field / intensity for pair production")
    p.add_argument("--field-vm", type=float, help="Field to compare (V/m) → ratio to critical")
    p.add_argument("--intensity-wcm2", type=float, help="Intensity to compare (W/cm²) → ratio to critical")
    p.set_defaults(func=cmd_schwinger_limit)

    # hubble-flow (M4)
    p = sub.add_parser("hubble-flow", help="Cosmological recession, or local-binding turnaround test")
    p.add_argument("--distance-mpc", type=float); p.add_argument("--distance-ly", type=float)
    p.add_argument("--mass-msun", type=float); p.add_argument("--radius-ly", type=float)
    p.add_argument("--radius-mpc", type=float)
    p.add_argument("--hubble-kms-mpc", type=float, help="Hubble constant (default 67.4)")
    p.add_argument("--omega-lambda", type=float, help="Dark-energy density parameter (default 0.685)")
    p.add_argument("--omega-m", type=float, help="Matter density parameter (default 0.315)")
    p.set_defaults(func=cmd_hubble_flow)

    # ── Phase AI (Group O) — black holes & relativistic thermodynamics (Pkt 24) ─

    # schwarzschild-radius (O1)
    p = sub.add_parser("schwarzschild-radius", help="Schwarzschild radius r_s = 2GM/c²")
    _add_object_mass_args(p)
    p.set_defaults(func=cmd_schwarzschild_radius)

    # hawking-temperature (O2)
    p = sub.add_parser("hawking-temperature", help="Hawking temperature (or inverse T → mass)")
    _add_object_mass_args(p)
    p.add_argument("--temperature-k", type=float, help="Inverse: temperature → black-hole mass")
    p.set_defaults(func=cmd_hawking_temperature)

    # black-hole-evaporation (O3)
    p = sub.add_parser("black-hole-evaporation", help="Hawking power + evaporation lifetime (or inverse)")
    _add_object_mass_args(p)
    p.add_argument("--lifetime-yr", type=float, help="Inverse: lifetime → black-hole mass")
    p.set_defaults(func=cmd_black_hole_evaporation)

    # bekenstein-hawking-entropy (O4)
    p = sub.add_parser("bekenstein-hawking-entropy", help="Bekenstein-Hawking horizon entropy")
    _add_object_mass_args(p)
    p.add_argument("--radius-m", type=float, help="Horizon radius (alternative to mass)")
    p.set_defaults(func=cmd_bekenstein_hawking_entropy)

    # isco (O5)
    p = sub.add_parser("isco", help="Innermost stable circular orbit + binding efficiency")
    _add_object_mass_args(p)
    p.add_argument("--spin", type=float, default=0.0, help="Dimensionless spin a* (−1…1, default 0)")
    p.add_argument("--retrograde", action="store_true", help="Retrograde orbit (default prograde)")
    p.set_defaults(func=cmd_isco)

    # kerr-horizon (O6)
    p = sub.add_parser("kerr-horizon", help="Kerr outer/inner horizons + ergosphere")
    _add_object_mass_args(p)
    p.add_argument("--spin", type=float, default=0.0, help="Dimensionless spin a* (−1…1, default 0)")
    p.set_defaults(func=cmd_kerr_horizon)

    # bh-tidal-force (O7)
    p = sub.add_parser("bh-tidal-force", help="Tidal (spaghettification) gradient + threshold radius")
    _add_object_mass_args(p)
    p.add_argument("--distance-m", type=float); p.add_argument("--distance-rs", type=float,
                   help="Distance in Schwarzschild radii (default 1 = at the horizon)")
    p.add_argument("--object-length-m", type=float, default=1.8, help="Body length Δr (default 1.8 m)")
    p.add_argument("--threshold-g", type=float, help="Solve the spaghettification radius at this g")
    p.set_defaults(func=cmd_bh_tidal_force)

    # eddington-luminosity (O8)
    p = sub.add_parser("eddington-luminosity", help="Eddington luminosity + accretion rate")
    _add_object_mass_args(p)
    p.add_argument("--efficiency", type=float, default=0.1, help="Radiative efficiency η (default 0.1)")
    p.set_defaults(func=cmd_eddington_luminosity)

    # unruh-temperature (O9)
    p = sub.add_parser("unruh-temperature", help="Unruh temperature for an accelerated observer")
    p.add_argument("--acceleration-ms2", type=float); p.add_argument("--acceleration-g", type=float)
    p.add_argument("--temperature-k", type=float, help="Inverse: temperature → acceleration")
    p.set_defaults(func=cmd_unruh_temperature)

    # bekenstein-bound (O10)
    p = sub.add_parser("bekenstein-bound", help="Bekenstein entropy/information bound in a region")
    p.add_argument("--radius-m", required=True, type=float, help="Region radius (m)")
    p.add_argument("--energy-j", type=float); p.add_argument("--mass-kg", type=float)
    p.set_defaults(func=cmd_bekenstein_bound)

    # ── Phase AH (Group N) — Alcubierre / metric drive (Pkt 22) ───────────────

    # alcubierre-energy (N1) — AH·1: 'original' formulation only (ladder added in AH·2)
    p = sub.add_parser("alcubierre-energy",
                       help="Negative-energy budget of an Alcubierre warp bubble")
    p.add_argument("--bubble-radius-m", type=float, help="Bubble radius R (m)")
    p.add_argument("--velocity-c", type=float, help="Bubble velocity v_s (fraction of c; may be >1)")
    p.add_argument("--wall-thickness-m", type=float, help="Wall thickness Δ (m)")
    p.add_argument("--formulation", choices=warp.FORMULATIONS, default="original",
                   help="Warp-drive formulation: original (computed) or a reduction (reported)")
    p.add_argument("--neck-radius-m", type=float, help="Van Den Broeck neck radius (echoed)")
    p.set_defaults(func=cmd_alcubierre_energy)

    # warp-metric (N2)
    p = sub.add_parser("warp-metric",
                       help="Alcubierre metric geometry: shape function, expansion scalar, wall region")
    p.add_argument("--bubble-radius-m", type=float, help="Bubble radius R (m)")
    p.add_argument("--wall-thickness-sigma", type=float, help="Wall steepness σ (1/m)")
    p.add_argument("--velocity-c", type=float, help="Bubble velocity v_s (fraction of c; may be >1)")
    p.add_argument("--r-eval-m", type=float, help="Evaluate f, df/dr, θ at this radius")
    p.add_argument("--profile", action="store_true", help="Sample f/df/θ across r_s")
    p.add_argument("--variant", choices=["alcubierre", "natario"], default="alcubierre",
                   help="natario = zero-expansion metric (space slides around; θ≡0)")
    p.set_defaults(func=cmd_warp_metric)

    # ── Phase AJ (Group P) — planet formation (Packet 3.5) ────────────────────

    # disk-model (P1)
    p = sub.add_parser("disk-model",
                       help="MMSN-scalable disk Σ_gas/Σ_solid/T/(H/r) profile at a radius or grid")
    p.add_argument("--r-au", type=float, help="Single radius (AU)")
    p.add_argument("--r-grid", type=float, nargs=3, metavar=("LO", "HI", "N"),
                   help="Log-spaced radius profile: LO HI N (AU, AU, count)")
    p.add_argument("--mstar-msun", type=float, default=1.0, help="Stellar mass (M⊙, default 1)")
    p.add_argument("--disk-mass-mmsn", type=float, help="Disk mass as MMSN multiplier (default 1)")
    p.add_argument("--disk-mass-msun", type=float, help="Disk mass in M⊙ (alt to --disk-mass-mmsn)")
    p.add_argument("--lstar-lsun", type=float, help="Stellar luminosity (L⊙, default 1, for T scaling)")
    p.add_argument("--ms-luminosity", action="store_true",
                   help="Derive L★ from M★ via the main-sequence L∝M^3.5 relation")
    p.add_argument("--feh", type=float, help="Metallicity [Fe/H] dex (Z = Z_⊙·10^[Fe/H])")
    p.add_argument("--z", type=float, help="Dust-to-gas ratio Z (default Z_⊙=0.0134)")
    p.add_argument("--snowline-au", type=float, help="Override the water snow-line radius (AU)")
    p.add_argument("--snowline-temp-k", type=float, default=170.0,
                   help="Ice condensation temperature for the snow-line solve (default 170 K)")
    p.add_argument("--ice-factor", type=float, default=2.0,
                   help="Σ_solid ice enhancement exterior to the snow line (default 2)")
    p.add_argument("--mu", type=float, default=2.34, help="Mean molecular weight (default 2.34)")
    p.add_argument("--sigma0", type=float, default=1700.0, help="Σ_gas at 1 AU (g/cm², default 1700)")
    p.add_argument("--sigma-slope", type=float, default=-1.5, help="Σ_gas power-law slope (default −3/2)")
    p.add_argument("--temp0", type=float, default=280.0, help="T at 1 AU (K, default 280)")
    p.add_argument("--temp-slope", type=float, default=-0.5, help="T power-law slope (default −1/2)")
    p.set_defaults(func=cmd_disk_model)

    # isolation-mass (P2)
    p = sub.add_parser("isolation-mass",
                       help="Oligarchic isolation mass M_iso (Armitage Eq. 201)")
    p.add_argument("--sigma-p-gcm2", type=float, help="Planetesimal/solid surface density (g/cm²)")
    p.add_argument("--a-au", type=float, help="Orbital radius (AU)")
    p.add_argument("--mstar-msun", type=float, default=1.0, help="Stellar mass (M⊙, default 1)")
    p.add_argument("--feeding-zone-c", type=float,
                   help="Feeding-zone half-width in single Hill radii (default 2√3≈3.464)")
    p.add_argument("--feeding-zone-b", type=float,
                   help="Oligarchic full width in MUTUAL Hill radii (e.g. 10; Kokubo & Ida)")
    p.set_defaults(func=cmd_isolation_mass)

    # pebble-isolation-mass (P3)
    p = sub.add_parser("pebble-isolation-mass",
                       help="Pebble-accretion cutoff mass — the super-Earth ↔ giant switch (Bitsch 2018)")
    p.add_argument("--hr", type=float, help="Disk aspect ratio H/r")
    p.add_argument("--temp-k", type=float, help="Disk temperature (K, to derive H/r with --mstar/--a)")
    p.add_argument("--mstar-msun", type=float, help="Stellar mass (M⊙, for H/r derivation)")
    p.add_argument("--a-au", type=float, help="Orbital radius (AU, for H/r derivation)")
    p.add_argument("--alpha", type=float, default=1e-3, help="Turbulent viscosity α (default 1e-3)")
    p.add_argument("--simple", action="store_true",
                   help="Base Lambrechts 2014 law 20·(H/r/0.05)³ (f_fit=1)")
    p.add_argument("--dlnp-dlnr", type=float, default=-2.5,
                   help="Global pressure-gradient index (echoed; default −2.5)")
    p.add_argument("--peb-norm", type=float, help="Override the normalization (default 25; --simple→20)")
    p.add_argument("--mu", type=float, default=2.34, help="Mean molecular weight (default 2.34)")
    p.set_defaults(func=cmd_pebble_isolation_mass)

    # gap-opening-mass (P4)
    p = sub.add_parser("gap-opening-mass",
                       help="Type-II gap-opening threshold via the Crida criterion (root-find)")
    p.add_argument("--hr", type=float, help="Disk aspect ratio H/r")
    p.add_argument("--temp-k", type=float, help="Disk temperature (K, to derive H/r)")
    p.add_argument("--mstar-msun", type=float, help="Stellar mass (M⊙, required for the q→mass conversion)")
    p.add_argument("--a-au", type=float, help="Orbital radius (AU, required for the q→mass conversion)")
    p.add_argument("--alpha", type=float, help="Turbulent viscosity α (ν_code=α·(H/r)²)")
    p.add_argument("--nu-code", type=float,
                   help="Kinematic viscosity ν in a²Ω units (Crida Case 1: 3.162e-6 = 10⁻⁵·⁵)")
    p.add_argument("--reynolds", type=float, help="Reynolds number R = a²Ω/ν directly")
    p.add_argument("--p-target", type=float, default=1.0,
                   help="Crida criterion target P (default 1.0, the marginal threshold)")
    p.add_argument("--mu", type=float, default=2.34, help="Mean molecular weight (default 2.34)")
    p.set_defaults(func=cmd_gap_opening_mass)

    # toomre-q (P5)
    p = sub.add_parser("toomre-q",
                       help="Disk gravitational-instability parameter Q (core-accretion ↔ GI boundary)")
    p.add_argument("--sigma-gcm2", type=float, help="Gas surface density (g/cm²)")
    p.add_argument("--temp-k", type=float, help="Disk temperature (K, → c_s via μ)")
    p.add_argument("--cs-ms", type=float, help="Sound speed directly (m/s)")
    p.add_argument("--dispersion-ms", type=float, help="1-D velocity dispersion for a particle disk (m/s)")
    p.add_argument("--mstar-msun", type=float, help="Stellar mass (M⊙, → Ω)")
    p.add_argument("--a-au", type=float, help="Orbital radius (AU, → Ω)")
    p.add_argument("--mu", type=float, default=2.34, help="Mean molecular weight (default 2.34)")
    p.add_argument("--q-crit", type=float, default=1.0, help="Instability threshold Q_crit (default 1)")
    p.set_defaults(func=cmd_toomre_q)

    # critical-core-mass (P6)
    p = sub.add_parser("critical-core-mass",
                       help="Envelope-runaway (critical core) mass for gas-giant formation")
    p.add_argument("--mdot-core", type=float, default=1e-6, help="Core accretion rate (M⊕/yr, default 1e-6)")
    p.add_argument("--opacity", type=float, default=1.0, help="Rosseland opacity κ_R (cm²/g, default 1)")
    p.add_argument("--index", type=float, default=0.25, help="Power-law index (default 0.25, ±0.05 knob)")
    p.add_argument("--crit-norm", type=float, default=12.0, help="Normalization (default 12 M⊕)")
    p.set_defaults(func=cmd_critical_core_mass)

    # ── Phase AK (Group Q) — metric-drive power/fuel + exclusion boundary (Pkts 25 / 26.5) ──

    # metric-drive-power (Q1)
    p = sub.add_parser("metric-drive-power",
                       help="Metric-drive field-rocket radiated power + fuel/mass bill "
                            "(P_rad=k*F*c; STL-mode law only)")
    p.add_argument("--mass-kg", type=float, help="Ship mass, kg")
    p.add_argument("--mass-tonnes", type=float, help="Ship mass, tonnes (1 t = 1000 kg)")
    p.add_argument("--thrust-n", type=float, help="Thrust, N (drives radiated power k*F*c)")
    p.add_argument("--accel-g", type=float, help="Acceleration in g (with mass -> thrust; with "
                                                 "--duration-days -> a leg)")
    p.add_argument("--accel-ms2", type=float, help="Acceleration, m/s^2 (alt to --accel-g)")
    p.add_argument("--delta-v-kms", type=float, help="Net delta-v, km/s (-> rapidity via atanh)")
    p.add_argument("--delta-v-c", type=float, help="Net delta-v as a fraction of c (-> rapidity)")
    p.add_argument("--rapidity", type=float, help="Net rapidity change delta-eta directly")
    p.add_argument("--duration-days", type=float, help="Burn duration, days (leg: dv = a*t)")
    p.add_argument("--k", "--tsiolkovsky-k", dest="k", type=float, default=3.0,
                   help="Tsiolkovsky constant k (GR baseline 3; B2 discount k<3, never 0; default 3)")
    p.add_argument("--fuel", choices=sorted(metric_drive._FIELD_FUEL),
                   help="Fuel preset for the mass->energy fraction f")
    p.add_argument("--f-conv", type=float, help="Override the effective f_conv = f*eta_dir directly")
    p.add_argument("--eta-dir", type=float, help="Override just the directed/usable fraction eta_dir "
                                                 "(scales the fuel preset's f)")
    p.add_argument("--turn", action="store_true",
                   help="Use the integrated proper-acceleration arc (a turn costs >= |delta-eta|)")
    p.add_argument("--integrated-rapidity", type=float,
                   help="The integral of |a| du arc for --turn (>= |delta-eta|)")
    p.add_argument("--beam-compare", action="store_true",
                   help="Emit the beam-vs-onboard crossover block (crossover k = 0.5)")
    p.add_argument("--self-consistent", action="store_true",
                   help="R6: self-consistent fuel bill (taxes carried fuel/ash + η_dir waste); "
                        "'keep' mode reports the feasibility wall + k_wall + lifetime Δv budget")
    p.add_argument("--ash", choices=["keep", "vent"], default="keep",
                   help="Ash retention for --self-consistent: keep (default; fuel-wall) or vent "
                        "(zero-relative-velocity dump, no wall)")
    p.set_defaults(func=cmd_metric_drive_power)

    # exclusion-boundary (Q2)
    p = sub.add_parser("exclusion-boundary",
                       help="FTL exclusion-boundary radius r_ex (the 'Alcubierre Limit'); "
                            "Rung-3 in-universe dial, Kuiper-edge calibrated")
    p.add_argument("--mass-msun", type=float, help="Body mass, M_sun (primary body source)")
    p.add_argument("--object", help="Body preset (sun, m-dwarf, o-star, brown-dwarf, rogue-planet)")
    p.add_argument("--star", help="Resolve mass/luminosity from a star name (SIMBAD + regions)")
    p.add_argument("--spectral-type", help="Resolve mass/luminosity from a spectral type (main-sequence)")
    p.add_argument("--luminosity-lsun", type=float, help="Body luminosity, L_sun (default 1)")
    p.add_argument("--mass-loss-msun-yr", type=float, help="Wind mass-loss rate W-dot, M_sun/yr")
    p.add_argument("--wind-state", choices=["quiet", "solar", "active", "hot"],
                   help="Wind-state preset -> a W-dot when the rate is unknown")
    p.add_argument("--dial", type=float,
                   help="Required-breakthrough calibration constant (default: auto to --calibration-au)")
    p.add_argument("--calibration-au", type=float, default=47.5,
                   help="Kuiper-edge anchor r_ex(Sun) in AU (default 47.5)")
    p.add_argument("--alpha", type=float, default=1.0 / 3.0,
                   help="Mass exponent (canon [1/3, 1/2]; default 1/3)")
    p.add_argument("--beta", type=float, default=0.0, help="Luminosity exponent (default 0 = off)")
    p.add_argument("--gamma", type=float, default=0.0, help="Wind exponent (default 0 = off)")
    p.add_argument("--scan-alpha", action="store_true",
                   help="Also emit r_ex at both alpha edges (1/3 and 1/2)")
    p.set_defaults(func=cmd_exclusion_boundary)

    # ── Phase AL (Group R) — power generation / storage / thermal (Pkt 27) ────

    # annihilation-power-train (R1)
    p = sub.add_parser("annihilation-power-train",
                       help="Antimatter annihilation power partition: directed / γ-heat / ν-loss")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--mass-flow-kgs", type=float, help="Annihilation mass flow, kg/s (P=ṁc²)")
    g.add_argument("--power-total-w", type=float, help="Total annihilation power, W (alt to mass-flow)")
    p.add_argument("--species", choices=["pp", "ee"], default="pp",
                   help="pp (proton-antiproton, ½ν/⅓γ/⅙e±) or ee (positron-electron → 2γ); default pp")
    p.add_argument("--eta-dir", type=float,
                   help="Directed/usable fraction (default 0.5 pp / 1.0 ee)")
    p.set_defaults(func=cmd_annihilation_power_train)

    # antimatter-production (R2)
    p = sub.add_parser("antimatter-production",
                       help="Antimatter production energy floor + Penning-trap storage-density ceiling")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--stored-mass-kg", type=float, help="Stored antimatter mass, kg (E=mc²)")
    g.add_argument("--stored-energy-j", type=float, help="Stored (annihilation-usable) energy, J")
    p.add_argument("--production-efficiency", type=float,
                   help="Wall-plug → stored efficiency (REQUIRED; the H-25-1 research input, no default)")
    p.add_argument("--trap-field-t", type=float,
                   help="Penning-trap field, T → the Brillouin storage-density ceiling ε₀B²/2")
    p.set_defaults(func=cmd_antimatter_production)

    # reactor-net-power (R4)
    p = sub.add_parser("reactor-net-power",
                       help="Net-energy / Q-gate accounting: gross → electric → net (survives recirc)")
    p.add_argument("--gross-power-w", type=float, required=True, help="Gross thermal power, W")
    p.add_argument("--thermal-efficiency", type=float, required=True,
                   help="Thermal→electric efficiency η_th (0 < η ≤ 1)")
    p.add_argument("--q-plasma", type=float,
                   help="Fusion plasma gain Q (P_out/P_heat) → the Q-tax; omit for non-fusion")
    p.add_argument("--recirculating-fraction", type=float, default=0.0,
                   help="Aux + drive recirculating fraction [0, 1) (default 0)")
    p.set_defaults(func=cmd_reactor_net_power)

    # beamed-power-delivery (R7)
    p = sub.add_parser("beamed-power-delivery",
                       help="Diffraction-limited beamed-power link efficiency (the λL/D wall)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--wavelength-m", type=float, help="Beam wavelength, m")
    g.add_argument("--frequency-hz", type=float, help="Beam frequency, Hz (alt to wavelength)")
    p.add_argument("--tx-aperture-m", type=float, required=True, help="Transmit aperture D_t, m")
    p.add_argument("--rx-aperture-m", type=float, required=True, help="Receive aperture D_r, m")
    p.add_argument("--range-m", type=float, required=True, help="Link range L, m")
    p.add_argument("--tx-power-w", type=float, help="Transmit power, W (→ delivered_power_w)")
    p.add_argument("--pointing-efficiency", type=float, default=1.0,
                   help="Pointing efficiency (0 < η ≤ 1, default 1)")
    p.set_defaults(func=cmd_beamed_power_delivery)

    # fusion-lawson (R10)
    p = sub.add_parser("fusion-lawson",
                       help="Lawson triple-product → fusion gain Q (general-power / reactor side ONLY)")
    p.add_argument("--fuel", choices=sorted(power._LAWSON_IGNITION), required=True,
                   help="Fusion fuel (d-t, d-he3, d-d, p-b11)")
    p.add_argument("--density-m3", type=float, help="Plasma number density n, m⁻³")
    p.add_argument("--temp-kev", type=float, help="Ion temperature T, keV")
    p.add_argument("--confinement-s", type=float, help="Energy confinement time τ, s")
    p.add_argument("--triple-product", type=float,
                   help="n·T·τ directly, keV·s·m⁻³ (alt to the n/T/τ triple)")
    p.add_argument("--confinement-boost", type=float, default=1.0,
                   help="AG confinement multiplier on n·τ (default 1.0; feeds reactor-net-power)")
    p.set_defaults(func=cmd_fusion_lawson)

    # heat-pump (R3)
    p = sub.add_parser("heat-pump",
                       help="Active-refrigeration Carnot COP (the inverse of waste-heat)")
    p.add_argument("--cold-temp-k", type=float, required=True, help="Cold-reservoir temperature T_c, K")
    p.add_argument("--hot-temp-k", type=float, required=True, help="Hot (reject) temperature T_h, K")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--heat-lifted-w", type=float, help="Heat lifted from the cold reservoir Q_c, W")
    g.add_argument("--work-w", type=float, help="Input work W, W (alt to Q_c)")
    p.add_argument("--efficiency-fraction", type=float, default=1.0,
                   help="Fraction of the Carnot COP (0 < f ≤ 1, default 1 = ideal)")
    p.set_defaults(func=cmd_heat_pump)

    # flywheel-storage (R8)
    p = sub.add_parser("flywheel-storage",
                       help="Flywheel specific-energy ceiling e = K·σ/ρ (material-strength wall)")
    p.add_argument("--tensile-strength-pa", type=float, required=True, help="Tensile strength σ, Pa")
    p.add_argument("--density-kgm3", type=float, required=True, help="Rotor density ρ, kg/m³")
    p.add_argument("--shape-factor", type=float, default=0.5,
                   help="Shape factor K (0.3 thin rim → 1.0 constant-stress disk; default 0.5)")
    p.add_argument("--mass-kg", type=float, help="Rotor mass, kg (→ stored_energy_j)")
    p.set_defaults(func=cmd_flywheel_storage)

    # smes-storage (R9)
    p = sub.add_parser("smes-storage",
                       help="SMES magnetic energy density u = B²/2µ₀ + structure-limited specific energy")
    p.add_argument("--field-t", type=float, required=True, help="Magnetic field B, T")
    p.add_argument("--critical-field-t", type=float,
                   help="Critical field B_c, T (flags critical_field_exceeded when B > B_c)")
    p.add_argument("--tensile-strength-pa", type=float,
                   help="Structure tensile strength σ, Pa (with --density-kgm3 → specific energy σ/ρ)")
    p.add_argument("--density-kgm3", type=float, help="Structure density ρ, kg/m³ (with σ)")
    p.add_argument("--volume-m3", type=float, help="Coil volume, m³ (→ stored_energy_j)")
    p.set_defaults(func=cmd_smes_storage)

    # energy-storage (T1 table)
    p = sub.add_parser("energy-storage",
                       help="Bundled battery/chemical/thermal specific energies (+ sensible/latent compute)")
    p.add_argument("--class", dest="storage_class",
                   help="A storage class (omit → all rows); unknown → curated error listing valid keys")
    p.add_argument("--override-wh-kg", type=float, help="Override the row's specific energy, Wh/kg")
    p.add_argument("--mass-kg", type=float, help="Mass, kg (compute branch → stored_energy_j)")
    p.add_argument("--specific-heat-jkgk", type=float, help="c_p, J/kg·K (sensible: E=m·c_p·ΔT)")
    p.add_argument("--delta-t-k", type=float, help="ΔT, K (sensible compute)")
    p.add_argument("--latent-heat-jkg", type=float, help="Latent heat L, J/kg (latent: E=m·L)")
    p.set_defaults(func=cmd_energy_storage)

    # reactor-power (T2 table)
    p = sub.add_parser("reactor-power",
                       help="Bundled reactor specific power α=P/m [kW/kg] + mandatory thermal pointer")
    p.add_argument("--class", dest="reactor_class",
                   help="A reactor class (omit → all rows); unknown → curated error listing valid keys")
    p.add_argument("--override-kw-kg", type=float, help="Override the row's specific power, kW/kg")
    p.add_argument("--gross-power-w", type=float, help="Gross power, W (→ implied core_mass_kg = P/α)")
    p.set_defaults(func=cmd_reactor_power)

    # ── Phase AP (Group S) — sensing / detection (Pkt 30) ─────────────────────

    # angular-resolution (S2)
    p = sub.add_parser("angular-resolution",
                       help="Diffraction resolution θ = k·λ/D (Rayleigh/Dawes/Sparrow)")
    p.add_argument("--aperture-m", type=float, required=True, help="Aperture diameter D, m")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--wavelength-m", type=float, help="Wavelength λ, m")
    g.add_argument("--frequency-hz", type=float, help="Frequency, Hz (alt to wavelength)")
    p.add_argument("--range-m", type=float, help="Range R, m (→ linear resolution θ·R)")
    p.add_argument("--separation-m", type=float, help="Two-object separation s, m (→ resolvable)")
    p.add_argument("--object-size-m", type=float, help="Object size d, m (→ resolved-or-point)")
    p.add_argument("--criterion", choices=["rayleigh", "dawes", "sparrow"], default="rayleigh",
                   help="Resolution criterion (default rayleigh, k=1.22)")
    p.add_argument("--coefficient", type=float, help="Override the criterion coefficient k")
    p.set_defaults(func=cmd_angular_resolution)

    # point-source-detection (S1)
    p = sub.add_parser("point-source-detection",
                       help="Unresolved point-source detection: SNR / max range (no-stealth-in-space)")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--source-power-w", type=float, help="Source radiant power L, W")
    src.add_argument("--source-temp-k", type=float, help="Source temperature T, K (with --source-area-m2)")
    p.add_argument("--source-area-m2", type=float, help="Source radiating area A, m² (with --source-temp-k)")
    p.add_argument("--emissivity", type=float, default=1.0, help="Source emissivity ε (0<ε≤1, default 1)")
    p.add_argument("--rx-aperture-m", type=float, required=True, help="Receiver aperture D, m")
    p.add_argument("--optical-efficiency", type=float, default=0.8, help="Optical efficiency (default 0.8)")
    p.add_argument("--range-m", type=float, help="Range R, m (→ SNR at range; omit → solve max range)")
    p.add_argument("--integration-s", type=float, default=1.0, help="Integration time t, s (default 1)")
    p.add_argument("--quantum-efficiency", type=float, default=0.8, help="Detector QE (default 0.8)")
    p.add_argument("--band", choices=["thermal-ir", "optical", "gamma", "radio"],
                   help="Band preset (→ representative λ + Δλ)")
    p.add_argument("--wavelength-m", type=float, help="Monochromatic wavelength λ, m (no Δλ)")
    p.add_argument("--band-min-m", type=float, help="Band lower edge, m (with --band-max-m)")
    p.add_argument("--band-max-m", type=float, help="Band upper edge, m (with --band-min-m)")
    p.add_argument("--source-size-m", type=float, help="Source physical size, m (→ resolved-or-point)")
    p.add_argument("--nep-w-rthz", type=float, help="Detector noise-equivalent power, W/√Hz (detector-limited)")
    p.add_argument("--background", choices=["cmb", "zodiacal", "stellar", "none"],
                   help="Background preset (background/shot-limited; needs a band)")
    p.add_argument("--background-intensity-w-m2-sr-m", type=float,
                   help="Explicit background spectral radiance, W·m⁻²·sr⁻¹·m⁻¹ (overrides preset)")
    p.add_argument("--background-temp-k", type=float, default=5772.0,
                   help="Stellar-background temperature, K (default 5772)")
    p.add_argument("--background-dilution", type=float, default=1.0,
                   help="Stellar-background dilution factor (0<f≤1, default 1 = undiluted upper bound)")
    p.add_argument("--flux-floor-w-m2", type=float,
                   help="Irradiance sensitivity floor, W/m² (→ aperture-independent max range)")
    p.add_argument("--snr-threshold", type=float, default=5.0, help="SNR detection threshold (default 5)")
    p.set_defaults(func=cmd_point_source_detection)

    # radar-range (S3)
    p = sub.add_parser("radar-range",
                       help="Active radar range equation (R⁻⁴): received power / max range")
    p.add_argument("--tx-power-w", type=float, required=True, help="Transmit power, W")
    p.add_argument("--tx-aperture-m", type=float, required=True, help="Transmit dish diameter, m")
    p.add_argument("--rx-aperture-m", type=float, help="Receive dish diameter, m (default = tx, monostatic)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--wavelength-m", type=float, help="Wavelength λ, m")
    g.add_argument("--frequency-hz", type=float, help="Frequency, Hz (alt to wavelength)")
    p.add_argument("--target-rcs-m2", type=float, required=True, help="Target radar cross-section σ, m²")
    rg = p.add_mutually_exclusive_group(required=True)
    rg.add_argument("--range-m", type=float, help="Range R, m (→ received power / SNR)")
    rg.add_argument("--min-detectable-power-w", type=float, help="Min detectable power, W (→ max range)")
    p.add_argument("--integration-s", type=float, default=1.0, help="Integration time t, s (default 1)")
    p.add_argument("--system-noise-temp-k", type=float, help="System noise temperature T_sys, K (→ SNR)")
    p.add_argument("--tx-gain", type=float, help="Override transmit gain (else (πD/λ)²)")
    p.add_argument("--rx-gain", type=float, help="Override receive gain (else (πD/λ)²)")
    p.add_argument("--snr-threshold", type=float, default=5.0, help="SNR detection threshold (default 5)")
    p.set_defaults(func=cmd_radar_range)

    # ── Phase AQ (Group T) — strategic-geography graph analytics (Pkt 32/38) ──

    # network-centrality (T1)
    p = sub.add_parser("network-centrality",
                       help="Route value / chokepoints: betweenness + articulation points + bridges")
    ns = p.add_mutually_exclusive_group(required=True)
    ns.add_argument("--stars", nargs="+", help="Explicit node set (≥2 star names)")
    ns.add_argument("--within-ly", type=float, help="Bounding-volume radius, ly (with --of)")
    ns.add_argument("--catalog", action="store_true", help="Use the whole star_systems catalog")
    p.add_argument("--of", help="Centre star for --within-ly")
    p.add_argument("--max-jump", type=float, required=True, help="Edge threshold, ly (as jump-network)")
    p.add_argument("--weight", choices=["hops", "distance", "dust"], default="hops",
                   help="Betweenness metric: hops (default), distance (3D ly), or dust (integrated A_V)")
    p.add_argument("--map", choices=["near-field", "edenhofer", "auto"], default="auto",
                   help="Dust map when --weight dust (default auto; needs the WSL/Linux dust extra)")
    p.add_argument("--dust-step-pc", dest="dust_step_pc", type=float, default=5.0,
                   help="Dust integration step in pc when --weight dust (default 5)")
    p.add_argument("--from", dest="from_star", help="Min-cut source star (with --to)")
    p.add_argument("--to", dest="to_star", help="Min-cut sink star (with --from)")
    p.add_argument("--top", type=int, help="Report the N highest-centrality nodes (default 25)")
    p.set_defaults(func=cmd_network_centrality)

    # arrival-corridors (T2)
    p = sub.add_parser("arrival-corridors",
                       help="FTL emergence / picket geometry: origin bearings → corridors + sky coverage")
    p.add_argument("--system", required=True, help="The defended system")
    og = p.add_mutually_exclusive_group(required=True)
    og.add_argument("--within-ly", type=float, help="All systems within N ly are candidate origins")
    og.add_argument("--origins", nargs="+", help="Explicit candidate origin star names")
    p.add_argument("--corridor-halfwidth-deg", type=float, default=5.0,
                   help="Defender picket cone half-width, deg (default 5)")
    p.add_argument("--cluster-deg", type=float, default=5.0,
                   help="Merge origins whose bearings differ by less than this, deg (default 5)")
    p.add_argument("--min-jump", type=float, help="Restrict origins to distance ≥ this, ly")
    p.add_argument("--max-jump", type=float, help="Restrict origins to distance ≤ this, ly")
    p.set_defaults(func=cmd_arrival_corridors)

    # ── Phase AR (Group U) — compute / beamrider utilities (Pkt 29/33) ────────

    # landauer-limit (U1)
    p = sub.add_parser("landauer-limit",
                       help="Landauer irreversible-compute energy floor E_bit = k_B·T·ln2")
    p.add_argument("--temp-k", type=float, default=300.0, help="Temperature T, K (default 300)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--bits", type=float, help="Bit count (→ total floor energy)")
    g.add_argument("--power-w", type=float, help="Power budget, W (→ max erasure rate)")
    g.add_argument("--bit-rate-hz", type=float, help="Erasure rate, Hz (→ min dissipated power)")
    p.add_argument("--reversible", action="store_true",
                   help="Annotate that reversible/adiabatic computing can go below the floor")
    p.set_defaults(func=cmd_landauer_limit)

    # beamrider-relay-spacing (U2)
    p = sub.add_parser("beamrider-relay-spacing",
                       help="Diffraction-limited beamrider relay-node spacing (inverts beamed-power-delivery)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--wavelength-m", type=float, help="Beam wavelength λ, m")
    g.add_argument("--frequency-hz", type=float, help="Beam frequency, Hz (alt to wavelength)")
    p.add_argument("--tx-aperture-m", type=float, required=True, help="Transmit aperture D_t, m")
    p.add_argument("--rx-aperture-m", type=float, required=True, help="Receive/collector aperture D_r, m")
    p.add_argument("--delivered-fraction-threshold", type=float, default=0.5,
                   help="Delivered-fraction threshold for a relay hop (0<f≤1, default 0.5)")
    tg = p.add_mutually_exclusive_group()
    tg.add_argument("--total-range-ly", type=float, help="Total lane length, ly (→ node count)")
    tg.add_argument("--total-range-m", type=float, help="Total lane length, m (→ node count)")
    p.set_defaults(func=cmd_beamrider_relay_spacing)

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

    # ── Phase AM catalog-access tier (LIVE network: CDS VizieR / ESA Gaia / HEASARC) ──

    # vizier-query
    p = sub.add_parser("vizier-query",
                       help="Any VizieR catalog by id → JSON rows (LIVE network)")
    p.add_argument("--catalog", required=True,
                   help="VizieR catalog/table id, e.g. B/sb9/main, B/cb/cbdata, B/wds, I/311/hip2")
    p.add_argument("--columns", nargs="+", default=None,
                   help="Column names to return (default all)")
    p.add_argument("--filters", action="append", default=None,
                   help="Repeatable 'col op val' constraint, e.g. --filters 'Per < 365'")
    p.add_argument("--cone", default=None,
                   help="Cone search 'ra dec radius' in decimal degrees")
    p.add_argument("--row-limit", dest="row_limit", type=int, default=2000,
                   help="Max rows (default 2000; -1 = unlimited)")
    p.set_defaults(func=cmd_vizier_query)

    # gaia-tap
    p = sub.add_parser("gaia-tap",
                       help="Any Gaia DR3 table by ADQL or structured filter (LIVE network)")
    p.add_argument("--adql", default=None, help="Raw ADQL query (takes precedence)")
    p.add_argument("--table", default=None,
                   help="Table name for structured mode, e.g. gaiadr3.nss_two_body_orbit")
    p.add_argument("--columns", nargs="+", default=None, help="Columns (structured mode)")
    p.add_argument("--where", default=None, help="ADQL WHERE body (structured mode)")
    p.add_argument("--cone", default=None, help="Cone 'ra dec radius' (deg, structured mode)")
    p.add_argument("--row-limit", dest="row_limit", type=int, default=2000,
                   help="Max rows (sync caps at 2000; use --async for more)")
    p.add_argument("--async", dest="use_async", action="store_true",
                   help="Use async job (no 2000-row cap) for population pulls")
    p.set_defaults(func=cmd_gaia_tap)

    # heasarc-query
    p = sub.add_parser("heasarc-query",
                       help="A HEASARC X-ray catalog by cone or ADQL (LIVE network)")
    p.add_argument("--catalog", default=None,
                   help="HEASARC catalog/table, e.g. rass2rxs, chanmaster, xmmssc")
    p.add_argument("--cone", default=None, help="Cone 'ra dec radius' (deg)")
    p.add_argument("--radius", type=float, default=0.1,
                   help="Cone radius (deg) when --cone gives only 'ra dec' (default 0.1)")
    p.add_argument("--adql", default=None, help="Raw TAP ADQL (takes precedence over --cone)")
    p.add_argument("--row-limit", dest="row_limit", type=int, default=2000,
                   help="Max rows (default 2000)")
    p.set_defaults(func=cmd_heasarc_query)

    # binary-orbit (Tier 2 — the encoded tool-split + companion-mass planet filter)
    p = sub.add_parser("binary-orbit",
                       help="Every orbital solution for one star (Gaia NSS + SB9 + WDS/orb6) "
                            "with companion-mass star/BD/planet classification (LIVE network)")
    p.add_argument("--star", default=None, help="Star name (resolved via SIMBAD)")
    p.add_argument("--ra", type=float, default=None, help="ICRS RA (deg) — with --dec")
    p.add_argument("--dec", type=float, default=None, help="ICRS Dec (deg) — with --ra")
    p.add_argument("--source-id", dest="source_id", default=None,
                   help="Gaia DR3 source_id (bare integer)")
    p.set_defaults(func=cmd_binary_orbit)

    # binary-stability-auto (CR-3): auto-pipe binary-orbit elements → Holman-Wiegert stability.
    p = sub.add_parser("binary-stability-auto",
                       help="Fetch a binary's orbit and feed it into Holman-Wiegert stability in "
                            "one call — S/P-type critical SMAs + a test-orbit verdict (LIVE network)")
    p.add_argument("--star", default=None, help="Star name (resolved via SIMBAD)")
    p.add_argument("--ra", type=float, default=None, help="ICRS RA (deg) — with --dec")
    p.add_argument("--dec", type=float, default=None, help="ICRS Dec (deg) — with --ra")
    p.add_argument("--source-id", dest="source_id", default=None,
                   help="Gaia DR3 source_id (bare integer)")
    p.add_argument("--test-sma-au", dest="test_sma_au", type=float, default=None,
                   help="Test-orbit semi-major axis (AU) for the stability verdict")
    p.set_defaults(func=cmd_binary_stability_auto)

    # multiplicity (CR-2): SB flag + per-component multiplicity summary (otype + binary-orbit + GCNS).
    p = sub.add_parser("multiplicity",
                       help="Multiplicity / spectroscopic-binary summary surfaced by default "
                            "(SIMBAD otype + binary-orbit tool-split + GCNS) (LIVE network)")
    p.add_argument("--star", default=None, help="Star name (resolved via SIMBAD)")
    p.add_argument("--source-id", dest="source_id", default=None,
                   help="Gaia DR3 source_id (bare integer)")
    p.set_defaults(func=cmd_multiplicity)

    # debris-disk (CR-1): observed IR-excess / debris disk (Chen 2014 + Cotten&Song 2016 +
    # Herschel far-IR; WISE upper limit on non-detection).
    p = sub.add_parser("debris-disk",
                       help="Observed debris-disk / IR-excess: L_IR/L*, warm/cold, T_dust, R_disk; "
                            "WISE upper limit if undetected (never null) (LIVE network)")
    p.add_argument("--star", default=None, help="Star name (resolved via SIMBAD)")
    p.add_argument("--source-id", dest="source_id", default=None, help="Gaia DR3 source_id")
    p.add_argument("--ra", type=float, default=None, help="ICRS RA (deg) — with --dec")
    p.add_argument("--dec", type=float, default=None, help="ICRS Dec (deg) — with --ra")
    p.set_defaults(func=cmd_debris_disk)

    # close-binary-census (Tier 2 — the systematic population sweep)
    p = sub.add_parser("close-binary-census",
                       help="Systematic close-binary population sweep (Gaia NSS + SB9, X-Match "
                            "dedup, companion classification, planet filter) (LIVE network)")
    p.add_argument("--dist-max-ly", dest="dist_max_ly", required=True, type=float,
                   help="Distance limit from Sol (light years)")
    p.add_argument("--period-max-d", dest="period_max_d", required=True, type=float,
                   help="Maximum orbital period (days)")
    p.add_argument("--sep-max-au", dest="sep_max_au", type=float, default=None,
                   help="Wide-cut separation (AU) for --separate-wide")
    p.add_argument("--include", default="nss,sb9",
                   help="Comma list of routes: nss,sb9,wds,cv (default nss,sb9)")
    p.add_argument("--parallax-source", dest="parallax_source",
                   choices=("gaia", "hipparcos", "both"), default="both",
                   help="Parallax source for the SB9 distance cut (default both)")
    p.add_argument("--keep-planets", dest="keep_planets", action="store_true",
                   help="Do NOT drop planetary companions (default: drop them)")
    p.add_argument("--separate-wide", dest="separate_wide", action="store_true",
                   help="Move P>max ∧ a>sep-max systems to a separate wide list")
    p.add_argument("--exclude-known", dest="exclude_known", default=None,
                   help="Path to a file of names/source_ids to drop (one per line)")
    p.set_defaults(func=cmd_close_binary_census)

    # gaia-astrophysical (Tier 3 — per-source GSP-Phot + FLAME mass/radius/lum/age)
    p = sub.add_parser("gaia-astrophysical",
                       help="Gaia GSP-Phot + FLAME stellar parameters (incl. age) for one source "
                            "(LIVE network)")
    p.add_argument("--star", default=None, help="Star name (resolved via SIMBAD → source_id)")
    p.add_argument("--source-id", dest="source_id", default=None,
                   help="Gaia DR3 source_id (bare integer)")
    p.set_defaults(func=cmd_gaia_astrophysical)

    # besancon-query (Tier 3 — Besançon m1612 field population → T8 age_dist; needs a BGM account)
    p = sub.add_parser("besancon-query",
                       help="Besançon Galaxy Model (m1612) synthetic field population + derived "
                            "age distribution (LIVE; needs BESANCON_USER/BESANCON_PASS)")
    p.add_argument("--glon", type=float, default=None, help="Field-centre Galactic longitude (deg)")
    p.add_argument("--glat", type=float, default=None, help="Field-centre Galactic latitude (deg)")
    p.add_argument("--local", action="store_true",
                   help="Use a representative mid-latitude sightline (l=90, b=45) if --glon/--glat omitted")
    p.add_argument("--area", type=float, default=1.0, help="Solid angle SOLI (deg², max 10)")
    p.add_argument("--dist-max-pc", dest="dist_max_pc", type=float, default=100.0,
                   help="Distance cut isolating the local slice (pc, default 100)")
    p.add_argument("--mag-max", dest="mag_max", type=float, default=None,
                   help="Reference-band (V) faint magnitude limit (optional)")
    p.add_argument("--sample-max", dest="sample_max", type=int, default=1000,
                   help="Max raw catalogue rows echoed (age_dist is computed over ALL stars)")
    p.add_argument("--contact-email", dest="contact_email", default=None,
                   help="Contact string for the User-Agent (defaults to the BGM login)")
    p.set_defaults(func=cmd_besancon_query)

    # ── Solvent zones (Phase P) ──────────────────────────────────────────────

    # solvent-zone
    p = sub.add_parser("solvent-zone",
                       help="Solvent Habitable Zone band (M1 surface model)")
    p.add_argument("--luminosity", "--luminosity-lsun", dest="luminosity",
                   required=True, type=float, help="Stellar luminosity (L_sun)")
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
    p.add_argument("--luminosity", "--luminosity-lsun", dest="luminosity",
                   required=True, type=float, help="Stellar luminosity (L_sun)")
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
    p.add_argument("--luminosity", "--luminosity-lsun", dest="luminosity",
                   required=True, type=float, help="Stellar luminosity in solar units")
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
    p.add_argument("--via", nargs="+", default=None,
                   help="Required intermediate waypoints (max 8) — an unordered SET; "
                        "the route must pass through every one, visited in whichever "
                        "order is cheapest under --optimize. May revisit a star.")
    # jump-route gets the extra `blend` weight (C11) + α/β on top of the shared distance/dust flags.
    p.add_argument("--weight", choices=["distance", "dust", "blend"], default="distance",
                   help="Edge weight: distance (default, 3D ly), dust (integrated A_V), or "
                        "blend (α·ly + β·A_V)")
    p.add_argument("--alpha", type=float, default=None,
                   help="Distance weight for --weight blend (default 1.0; --beta 0 → distance route)")
    p.add_argument("--beta", type=float, default=None,
                   help="A_V weight for --weight blend (default 1.0; --alpha 0 → dust route)")
    p.add_argument("--map", choices=["near-field", "edenhofer", "auto"], default="auto",
                   help="Dust map when --weight dust/blend (default auto)")
    p.add_argument("--dust-step-pc", dest="dust_step_pc", type=float, default=5.0,
                   help="Dust integration step in pc when --weight dust/blend (default 5)")
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

    # ── Phase AT (Packet 38.1) — weapons / defenses / engagement physics ─────

    # salvo-exchange (W1 — Hughes salvo model)
    p = sub.add_parser("salvo-exchange",
                       help="Hughes salvo model: per-salvo losses, exchange ratio, first-strike, "
                            "sequential-waves, break-even, solve-force, distribute, layered-defense")
    p.add_argument("--a-force", type=float, help="Force size A (count; may be fractional)")
    p.add_argument("--b-force", type=float, help="Force size B (count)")
    p.add_argument("--alpha", type=float, help="A per-unit striking power α (good hits/unit/salvo)")
    p.add_argument("--beta", type=float, help="B per-unit striking power β")
    p.add_argument("--a-salvo", type=float, help="A missiles/unit (with --a-hitprob → α)")
    p.add_argument("--b-salvo", type=float, help="B missiles/unit (with --b-hitprob → β)")
    p.add_argument("--a-hitprob", type=float, help="A hit probability H (0–1)")
    p.add_argument("--b-hitprob", type=float, help="B hit probability H (0–1)")
    p.add_argument("--a1-staying", type=float, help="A staying power (hits to OOA, > 0)")
    p.add_argument("--b1-staying", type=float, help="B staying power (hits to OOA, > 0)")
    p.add_argument("--a3-defense", type=float, help="A defensive power (good shots defeated/unit)")
    p.add_argument("--b3-defense", type=float, help="B defensive power")
    p.add_argument("--sigma-a", type=float, default=1.0, help="A scouting effectiveness σ (0–1, default 1)")
    p.add_argument("--sigma-b", type=float, default=1.0, help="B scouting effectiveness σ (0–1, default 1)")
    p.add_argument("--delta-a", type=float, default=1.0, help="A defender alertness δ (0–1, default 1)")
    p.add_argument("--delta-b", type=float, default=1.0, help="B defender alertness δ (0–1, default 1)")
    p.add_argument("--leak-a", type=float, default=0.0, help="A leakage fraction L (0–1, default 0)")
    p.add_argument("--leak-b", type=float, default=0.0, help="B leakage fraction L (0–1, default 0)")
    p.add_argument("--mode", choices=list(salvo.MODES), default="simultaneous", help="engagement mode")
    p.add_argument("--first", choices=["a", "b"],
                   help="who strikes first (first-strike) / commits waves (sequential-waves) / attacks (distribute)")
    p.add_argument("--wave-size", type=float, help="ships per wave (sequential-waves)")
    p.add_argument("--n-waves", type=int, help="number of waves K (sequential-waves)")
    p.add_argument("--defender-magazine", type=int,
                   help="defender return salvos (sequential-waves; omit = unlimited/reloading)")
    p.add_argument("--defender-preempts", action="store_true",
                   help="sequential-waves out-ranging case: defender offence suppresses the wave's "
                        "salvo (only offence-survivors deliver); default off = simultaneous exchange")
    p.add_argument("--target-delta", type=float, help="target absolute Δ (solve-force)")
    p.add_argument("--target-frac-loss", type=float, help="target fractional loss Δ/force (solve-force)")
    p.add_argument("--solve-for", choices=["a", "b"], help="which force to solve for (solve-force)")
    p.add_argument("--target-side", choices=["a", "b"], help="side the target loss applies to (solve-force)")
    p.add_argument("--fire-fraction", type=float, help="fraction f of the enemy targeted (distribute)")
    p.add_argument("--rings", help="layered-defense rings 'delta:b3:leak, …' (outermost first)")
    p.add_argument("--inbound-salvo", type=float, help="inbound good-shot count (layered-defense)")
    p.add_argument("--scouting", type=float, default=1.0,
                   help="layered-defense inbound scouting σ (0–1, default 1)")
    p.add_argument("--target-staying", type=float, help="target staying power a₁ (layered → delta_target)")
    p.set_defaults(func=cmd_salvo_exchange)

    # beam-weapon-engagement (W2)
    p = sub.add_parser("beam-weapon-engagement",
                       help="Directed-energy reach & lethality: spot size, fraction on target, "
                            "intensity, dwell-to-kill, effective range (vacuum diffraction-limited)")
    p.add_argument("--aperture-m", type=float, required=True, help="Aperture diameter D, m")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--wavelength-m", type=float, help="Wavelength λ, m")
    g.add_argument("--frequency-hz", type=float, help="Frequency, Hz (alt to wavelength)")
    p.add_argument("--power-w", type=float, required=True, help="Beam power P, W")
    p.add_argument("--beam-quality-m2", type=float, default=1.0, help="Beam-quality factor M² (default 1)")
    p.add_argument("--pointing-efficiency", type=float, default=1.0,
                   help="Pointing efficiency η (0–1, default 1)")
    p.add_argument("--rayleigh-k", type=float, default=1.22, help="Diffraction coefficient k (default 1.22)")
    p.add_argument("--target-size-m", type=float, required=True, help="Target characteristic size s, m")
    p.add_argument("--range-m", type=float, required=True, help="Range R, m")
    p.add_argument("--kill-fluence-jm2", type=float, help="Areal kill fluence Φ_kill, J/m²")
    p.add_argument("--target-material-enthalpy-jkg", type=float,
                   help="Material vaporization/melt enthalpy, J/kg (→ Φ_kill with areal density)")
    p.add_argument("--target-areal-density-kgm2", type=float,
                   help="Target areal density, kg/m² (with enthalpy → Φ_kill)")
    p.add_argument("--max-dwell-s", type=float, help="Max acceptable dwell, s (→ dwell-limited range)")
    p.set_defaults(func=cmd_beam_weapon_engagement)

    # kinetic-kill (W3)
    p = sub.add_parser("kinetic-kill",
                       help="Hypervelocity impactor vs armor: KE (classical+relativistic), "
                            "TNT-equiv, penetration, monolithic/Whipple verdict")
    p.add_argument("--mass-kg", type=float, help="Impactor mass, kg (or supply rod geometry)")
    p.add_argument("--length-m", type=float, help="Rod length L, m (with --diameter-m + --density-kgm3)")
    p.add_argument("--diameter-m", type=float, help="Rod diameter, m")
    p.add_argument("--density-kgm3", type=float, help="Impactor density ρ_i, kg/m³")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--velocity-kms", type=float, help="Impact velocity, km/s")
    g.add_argument("--beta", type=float, help="Impact velocity as a fraction of c (0<β<1)")
    p.add_argument("--target-density-kgm3", type=float, required=True, help="Target density ρ_t, kg/m³")
    p.add_argument("--target-type", choices=["monolithic", "whipple"], default="monolithic",
                   help="armor type (default monolithic)")
    p.add_argument("--armor-thickness-m", type=float, help="Monolithic armor thickness, m (→ perforates)")
    p.add_argument("--bumper-areal-density-kgm2", type=float, help="Whipple bumper areal density, kg/m²")
    p.add_argument("--standoff-m", type=float, help="Whipple bumper→wall standoff, m")
    p.add_argument("--rearwall-areal-density-kgm2", type=float, help="Whipple rear-wall areal density, kg/m²")
    p.add_argument("--target-sound-speed-ms", type=float,
                   help="Target bulk sound speed, m/s (regime call + crater form)")
    p.add_argument("--crater-exponent", type=float, help="Crater velocity exponent n (default 2/3)")
    p.add_argument("--debris-cone-half-angle-deg", type=float,
                   help="Whipple debris-cloud cone half-angle, deg (default 15)")
    p.set_defaults(func=cmd_kinetic_kill)

    # warhead-effects-at-standoff (W4)
    p = sub.add_parser("warhead-effects-at-standoff",
                       help="Warhead lethality radius in vacuum: per-channel inverse-square fluence "
                            "+ kill radius (fission/fusion/antimatter/kinetic-plasma)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--yield-j", type=float, help="Total yield Y, J")
    g.add_argument("--yield-kt", type=float, help="Total yield, kt TNT (→ J)")
    p.add_argument("--warhead-type", choices=list(weapons.wt.WARHEAD_TYPES), default="fusion",
                   help="channel partition preset (illustrative defaults, overridable)")
    p.add_argument("--f-xray", type=float, help="Override soft-x-ray yield fraction")
    p.add_argument("--f-neutron", type=float, help="Override neutron yield fraction")
    p.add_argument("--f-debris", type=float, help="Override debris/plasma yield fraction")
    p.add_argument("--f-gamma", type=float, help="Override gamma yield fraction")
    p.add_argument("--standoff-m", type=float, required=True, help="Detonation standoff range R, m")
    p.add_argument("--threshold-xray-jm2", type=float, help="Target soft-x-ray kill threshold, J/m²")
    p.add_argument("--threshold-neutron-jm2", type=float, help="Target neutron kill threshold, J/m²")
    p.add_argument("--threshold-debris-jm2", type=float, help="Target debris/plasma kill threshold, J/m²")
    p.add_argument("--threshold-gamma-jm2", type=float, help="Target gamma kill threshold, J/m²")
    p.set_defaults(func=cmd_warhead_effects)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except Exception as e:
        _out({"error": str(e)})


if __name__ == "__main__":
    main()
