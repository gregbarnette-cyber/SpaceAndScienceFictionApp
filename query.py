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


# ── Argument parser ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Query SpaceAndScienceFictionApp core functions; outputs JSON."
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

    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as e:
        _out({"error": str(e)})


if __name__ == "__main__":
    main()
