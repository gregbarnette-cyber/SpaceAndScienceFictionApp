"""query.py — JSON dispatcher for SpaceAndScienceFictionApp core functions.

Usage:
    python query.py <subcommand> [arguments]

Prints JSON to stdout. Exits 0 on success, 1 on error.
"""

import argparse
import json
import sys

import core.calculators as calculators
import core.databases as databases
import core.equations as equations
import core.regions as regions
import core.science as science


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
    _out(databases.compute_gcns_within_sol(args.ly))


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


def cmd_travel_time_solar(args):
    # progress_callback is GUI-only and is deliberately NOT passed (defaults to None).
    _out(calculators.compute_travel_time_solar_objects(
        args.origin, args.destination, args.accel_g,
        v_cap_pct=args.v_cap_pct, departure_date=args.date,
    ))


def cmd_optimal_tour(args):
    use_times_c = args.times_c is not None
    velocity = args.times_c if use_times_c else args.ly_hr
    _out(calculators.compute_optimal_tour(
        args.stars, velocity, use_times_c, closed=args.closed,
    ))


def cmd_jump_route(args):
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
    _out(calculators.compute_multi_stop_journey(args.stars, velocity, use_times_c))


def cmd_nearest_neighbor(args):
    _out(calculators.compute_nearest_neighbor_chain(
        args.start, args.hops, args.max_ly,
    ))


def cmd_farthest_first(args):
    _out(calculators.compute_farthest_first_chain(
        args.start, args.stops, max_reach_ly=args.max_reach,
    ))


def cmd_trade_route(args):
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
    p.set_defaults(func=cmd_multi_stop)

    # nearest-neighbor
    p = sub.add_parser("nearest-neighbor",
                       help="Greedy nearest-unvisited chain from a start star")
    p.add_argument("--start",  required=True, help="Start star name")
    p.add_argument("--hops",   required=True, type=int, help="Number of hops")
    p.add_argument("--max-ly", dest="max_ly", required=True, type=float,
                   help="Maximum single-hop distance in light years")
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

    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as e:
        _out({"error": str(e)})


if __name__ == "__main__":
    main()
