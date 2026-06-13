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

    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as e:
        _out({"error": str(e)})


if __name__ == "__main__":
    main()
