# core/generate.py — Phase R1: deterministic procedural system generator.
#
# PURE: no Qt, no file I/O, no network of its own (the real-anchor path calls
# existing readers, which handle their own I/O). Determinism is the headline
# contract — same seed (+ same anchor_star) → byte-identical output — so all
# randomness flows through a single seeded random.Random in a fixed draw order;
# no Date.now, no module-level / unseeded RNG, no set/dict-ordering dependence.
#
# New astronomy is limited to two thin helpers (R1-C1): a planet classifier and
# an equilibrium-temperature wrapper that reuses Phase P. Everything else reuses
# verified core/ functions. R1-C2 adds synthetic-mode generate_system(); the
# real-anchor mode lands in R1-C3.

import math
import re
import random

from core.equations import (
    _rocky_radius_km,
    _EARTH_RADIUS_KM,
    implied_edge_temp,
    compute_star_luminosity,
    compute_habitable_zone,
    compute_ice_lines,
    compute_roche_limit,
    compute_hill_sphere,
    compute_atmosphere_retention,
)
from core.science import compute_main_sequence_table
from core.priors import DefaultPriors, get_priors, PriorsUnavailable
from core.databases import (
    compute_simbad_lookup,
    compute_planetary_systems_composite,
    compute_hwc,
)
from core.regions import compute_star_system_regions_from_simbad

# ── Planet-classification constants ──────────────────────────────────────────
_M_JUPITER_EARTH = 317.8        # Jupiter mass in Earth masses

# Mass class boundaries (Earth masses). The deuterium-burning limit (~13 M_J)
# separates planets from brown dwarfs; ~2 M_J separates Jovian from super-Jovian.
_BROWN_DWARF_MIN_EARTH  = 13.0 * _M_JUPITER_EARTH   # 4131.4
_SUPER_JOVIAN_MIN_EARTH = 2.0 * _M_JUPITER_EARTH    # 635.6
_GAS_MIN_EARTH          = 50.0                       # Saturn ≈ 95, Neptune ≈ 17
_ICE_MIN_EARTH          = 10.0                       # Neptune/Uranus class
_SUPER_EARTH_MIN_EARTH  = 2.0                        # > 2 M⊕ → super-Earth

# Mass–radius relations for the volatile/giant branches. Rocky / super-Earth
# reuse the Phase H _rocky_radius_km (R ∝ M^0.55). Ice giants use the Chen &
# Kipping (2017) "Forecaster" Neptunian fit (R = 0.808·M^0.589, Earth units);
# Jovian-and-up use a Jupiter-anchored near-flat relation (degeneracy support →
# radius nearly constant from Saturn through the brown-dwarf regime).
_NEPTUNIAN_COEFF = 0.808
_NEPTUNIAN_EXP   = 0.589
_JUPITER_RADIUS_EARTH = 11.2
_JOVIAN_EXP      = -0.044


def _radius_earth_for_type(ptype: str, mass_earth: float) -> float:
    """Radius (Earth radii) for a classified planet of the given mass.

    rocky / super_earth → R ∝ M^0.55 (Phase H _rocky_radius_km, reused).
    ice                 → Chen & Kipping 2017 Neptunian fit.
    gas / super_jovian / brown_dwarf → Jupiter-anchored near-flat Jovian fit.
    """
    if ptype in ("rocky", "super_earth"):
        return _rocky_radius_km(mass_earth) / _EARTH_RADIUS_KM
    if ptype == "ice":
        return _NEPTUNIAN_COEFF * mass_earth ** _NEPTUNIAN_EXP
    # gas, super_jovian, brown_dwarf
    return _JUPITER_RADIUS_EARTH * (mass_earth / _M_JUPITER_EARTH) ** _JOVIAN_EXP


def _classify_planet(mass_earth, a_au, snow_line_au=None):
    """Classify a planet by mass with a snow-line modifier; return (type, radius_earth).

    Base type by mass (Earth masses):
        < 2          → rocky
        2 – 10       → super_earth
        10 – 50      → ice
        50 – 635.6   → gas           (≈ up to 2 M_J)
        635.6 – 4131 → super_jovian  (2–13 M_J)
        ≥ 4131       → brown_dwarf   (> 13 M_J — flagged as substellar)

    Snow-line modifier: a super-Earth-mass body (2–10 M⊕) at or beyond the snow
    line accretes a volatile envelope, so it is reclassified as a (Neptune-like)
    ``ice`` world. Lower-mass bodies stay rocky (too light to hold an envelope);
    ice-and-above are volatile/gas-dominated regardless of position. When
    ``snow_line_au`` is None (or a_au is None) no modifier is applied.

    Radius follows the classified type via :func:`_radius_earth_for_type`.
    """
    m = mass_earth
    if m >= _BROWN_DWARF_MIN_EARTH:
        ptype = "brown_dwarf"
    elif m >= _SUPER_JOVIAN_MIN_EARTH:
        ptype = "super_jovian"
    elif m >= _GAS_MIN_EARTH:
        ptype = "gas"
    elif m >= _ICE_MIN_EARTH:
        ptype = "ice"
    elif m >= _SUPER_EARTH_MIN_EARTH:
        ptype = "super_earth"
    else:
        ptype = "rocky"

    # Snow-line modifier (volatile availability beyond the snow line).
    if snow_line_au is not None and a_au is not None and a_au >= snow_line_au:
        if ptype == "super_earth":
            ptype = "ice"

    return ptype, _radius_earth_for_type(ptype, m)


def _equilibrium_temp(a_au, luminosity, albedo=0.3):
    """Planet equilibrium temperature (K) at ``a_au`` for a star of ``luminosity``
    (solar = 1), reusing Phase P's M2 radiative-equilibrium model.

    Thin wrapper over :func:`core.equations.implied_edge_temp` with
    ``model="equilibrium"`` — reuse, not reinvent. ``albedo`` defaults to 0.3
    (Earth-like Bond albedo) → ≈ 255 K at 1 AU around the Sun, so an HZ planet
    lands near ~255–320 K (a generator cross-check). Returns None for
    non-positive ``a_au`` or ``luminosity`` (the implied_edge_temp guard).
    """
    return implied_edge_temp(a_au, luminosity, model="equilibrium", albedo=albedo)


# ── Synthetic-mode generation (R1-C2) ────────────────────────────────────────

_LETTER_ORDER = "OBAFGKM"                     # hot → cool; index basis for interp
_SAMPLE_LETTER_ORDER = ["M", "K", "G", "F", "A", "B"]  # fixed iteration (determinism)
_MOON_HOST_TYPES = {"ice", "gas", "super_jovian", "brown_dwarf"}
_COLD_FAR_MULT = 4.0                          # cold zone runs out to 4× snow line
_MAX_N_PLANETS = 15
_HABITABLE_TRIES = 200
_BINARY_SAFE_CAP_K = 2.0          # multiple-star synthetic cap = k × conservative HZ outer
_ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]


def _round(x, n=6):
    """Round for tidy, byte-stable JSON; pass through None."""
    return None if x is None else round(float(x), n)


def _spectral_index(letter, subtype):
    """Continuous spectral index: O0=0 … M9=69 (hotter = smaller)."""
    return _LETTER_ORDER.index(letter) * 10 + subtype


def _weighted_choice(rng, items):
    """Deterministic weighted pick from a list of (value, weight)."""
    total = sum(w for _, w in items)
    x = rng.uniform(0.0, total)
    upto = 0.0
    for val, w in items:
        upto += w
        if x <= upto:
            return val
    return items[-1][0]


def _parse_spectral_class(sc):
    """Parse 'K2V'/'K2'/'G'/'m5.5' → (letter, subtype_float), or None if invalid.

    A bare letter defaults to subtype 0.0; any trailing luminosity class is ignored.
    """
    if not sc:
        return None
    m = re.match(r"^\s*([OBAFGKMobafgkm])(\d+(?:\.\d+)?)?", sc.strip())
    if not m:
        return None
    letter = m.group(1).upper()
    subtype = float(m.group(2)) if m.group(2) else 0.0
    return letter, subtype


def _usable_ms_rows():
    """Main-sequence interpolation table: (index, teff, radius, mass), ascending.

    Rows whose Teff/R/M are missing or non-numeric are dropped — notably the
    bundled CSV's O5/B0 rows carry a corrupt radius placeholder, so the usable
    range starts at B5. Empty → caller surfaces a data-unavailable error.
    """
    rows = []
    for r in compute_main_sequence_table():
        parsed = _parse_spectral_class(str(r.get("Spectral Class", "")))
        if not parsed:
            continue
        letter, sub = parsed
        try:
            teff = float(r["Teeff(K)"])
            rad = float(r["R"])
            mass = float(r["M"])
        except (ValueError, TypeError, KeyError):
            continue
        if teff <= 0 or rad <= 0 or mass <= 0:
            continue
        rows.append((_spectral_index(letter, sub), teff, rad, mass))
    rows.sort(key=lambda t: t[0])
    return rows


def _interp_star_props(target_index, rows):
    """Linearly interpolate (teff, radius, mass) at target_index; clamp to ends."""
    if target_index <= rows[0][0]:
        return rows[0][1], rows[0][2], rows[0][3]
    if target_index >= rows[-1][0]:
        return rows[-1][1], rows[-1][2], rows[-1][3]
    for i in range(1, len(rows)):
        lo, hi = rows[i - 1], rows[i]
        if lo[0] <= target_index <= hi[0]:
            span = hi[0] - lo[0]
            f = 0.0 if span == 0 else (target_index - lo[0]) / span
            return (lo[1] + f * (hi[1] - lo[1]),
                    lo[2] + f * (hi[2] - lo[2]),
                    lo[3] + f * (hi[3] - lo[3]))
    return rows[-1][1], rows[-1][2], rows[-1][3]


def _fmt_class(letter, subtype):
    """'K', 2.0 → 'K2V'; '…', 5.5 → 'M5.5V' (drop a trailing .0)."""
    s = int(subtype) if float(subtype).is_integer() else subtype
    return f"{letter}{s}V"


def _synth_star(rng, priors, seed, spectral_class, rows):
    """Build the synthetic star dict + a derived-values bundle for planet placement."""
    if spectral_class is not None:
        parsed = _parse_spectral_class(spectral_class)
        if not parsed:
            return {"error": f"Invalid spectral class: {spectral_class!r} (expected e.g. 'K2V')."}
        letter, subtype = parsed
        if letter == "O":
            return {"error": "Spectral class O is not supported for generation "
                             "(no long-lived main-sequence data / no stable planetary systems)."}
        if not (0.0 <= subtype <= 9.9):
            return {"error": "Spectral subtype must be in the range 0–9.9."}
    else:
        letter = _weighted_choice(
            rng, [(L, priors.spectral_class_weights[L]) for L in _SAMPLE_LETTER_ORDER])
        subtype = float(rng.randint(0, 9))

    teff, radius_solar, mass_solar = _interp_star_props(_spectral_index(letter, subtype), rows)
    luminosity = compute_star_luminosity(radius_solar, teff)["luminosity"]

    hz = compute_habitable_zone(teff, luminosity)
    hzmap = {z["key"]: z["au"] for z in hz}
    ice = compute_ice_lines(luminosity)
    snow_line = next((ln["au"] for ln in ice.get("lines", []) if ln["kind"] == "snow_line"), None)

    sc_str = _fmt_class(letter, subtype)
    star = {
        "name": f"Gen-{seed}",
        "spectral_class": sc_str,
        "teff": _round(teff, 1),
        "mass_solar": _round(mass_solar, 4),
        "radius_solar": _round(radius_solar, 4),
        "luminosity": _round(luminosity, 6),
        "hz_inner_au": _round(hzmap["rg"], 5),       # conservative inner (Runaway Greenhouse)
        "hz_outer_au": _round(hzmap["mg"], 5),       # conservative outer (Maximum Greenhouse)
        "hz_opt_inner_au": _round(hzmap["rv"], 5),   # optimistic inner (Recent Venus)
        "hz_opt_outer_au": _round(hzmap["em"], 5),   # optimistic outer (Early Mars)
        "snow_line_au": _round(snow_line, 5),
        "source": "synthetic",
        "grounding": priors.grounding,
        "multiplicity": None,
    }
    derived = {
        "teff": teff, "mass_solar": mass_solar, "luminosity": luminosity,
        "hz_cons_inner": hzmap["rg"], "hz_cons_outer": hzmap["mg"],
        "hz_opt_inner": hzmap["rv"], "hz_opt_outer": hzmap["em"],
        "snow_line": snow_line,
    }
    return {"star": star, "derived": derived}


def _zone_for(a, d):
    """Orbital zone for mass-band selection."""
    if a < d["hz_opt_inner"]:
        return "hot"
    if a <= d["hz_opt_outer"]:
        return "hz"
    if d["snow_line"] and a <= _COLD_FAR_MULT * d["snow_line"]:
        return "cold"
    return "far"


def _hz_membership(a, d):
    """(in_hz, hz_class) — conservative is a subset of optimistic."""
    if d["hz_cons_inner"] <= a <= d["hz_cons_outer"]:
        return True, "conservative"
    if d["hz_opt_inner"] <= a <= d["hz_opt_outer"]:
        return True, "optimistic"
    return False, None


def _atmosphere_note(mass_earth, radius_earth, t_eq):
    """Retained-gas summary for a terrestrial world, or None if T_eq unusable."""
    if t_eq is None or t_eq <= 0:
        return None
    ret = compute_atmosphere_retention(mass_earth, radius_earth, t_eq)
    if "error" in ret:
        return None
    retained = [g["gas"] for g in ret["gases"] if g["status"] == "Retained"]
    return "Retains " + ", ".join(retained) if retained else "Negligible (gases escape)"


def _make_synth_planet(rng, priors, name, a, derived):
    """Build one synthetic planet at SMA ``a``: draw mass (by zone) then ecc, in
    that fixed order, then classify / T_eq / HZ / atmosphere. Carries internal
    _-prefixed working fields for downstream moon placement. Shared by the
    synthetic-mode pass and the real-anchor extension pass."""
    lum = derived["luminosity"]
    zone = _zone_for(a, derived)
    lo, hi = priors.mass_by_zone[zone]
    mass = math.exp(rng.uniform(math.log(lo), math.log(hi)))
    ecc = rng.uniform(0.0, 0.08)
    ptype, radius = _classify_planet(mass, a, derived["snow_line"])
    t_eq = _equilibrium_temp(a, lum)
    in_hz, hz_class = _hz_membership(a, derived)
    atmosphere = (_atmosphere_note(mass, radius, t_eq)
                  if ptype in ("rocky", "super_earth") else None)
    return {
        "name": name,
        "a_au": _round(a, 5),
        "mass_earth": _round(mass, 4),
        "radius_earth": _round(radius, 4),
        "ecc": _round(ecc, 4),
        "type": ptype,
        "t_eq_k": _round(t_eq, 2),
        "in_hz": in_hz,
        "hz_class": hz_class,
        "source": "synthetic",
        "atmosphere": atmosphere,
        "moons": [],
        "_a_raw": a, "_mass_raw": mass, "_ecc_raw": ecc, "_radius_raw": radius,
    }


def _synth_planets(rng, priors, star_name, derived):
    """One planet-architecture draw: SMAs (log-spaced, jittered) + per-planet props.

    Caller fixes the count (derived["_n"]); this consumes the RNG in a fixed
    order so re-rolls (require_habitable) stay deterministic. Returns a list of
    planet dicts (with internal _-prefixed working fields for moon placement).
    """
    n = derived["_n"]
    if n <= 0:
        return []
    root_l = math.sqrt(derived["luminosity"])
    spacing_lo, spacing_hi = priors.spacing_ratio

    a = rng.uniform(0.03, 0.12) * root_l    # innermost SMA (scales with sqrt L)
    planets = []
    for i in range(n):
        if i > 0:
            a *= rng.uniform(spacing_lo, spacing_hi)
        planets.append(_make_synth_planet(
            rng, priors, f"{star_name} {chr(ord('b') + i)}", a, derived))
    return planets


def _attach_moons(rng, priors, star, planets):
    """Add moons to giant planets: SMA strictly between the fluid Roche limit and
    the planet's stable-orbit (½ Hill) limit; mass a small fraction of the host."""
    mass_solar = star["mass_solar"]
    mlo, mhi = priors.moon_count
    fraclo, frachi = priors.moon_mass_frac
    for p in planets:
        if p["type"] not in _MOON_HOST_TYPES:
            continue
        count = rng.randint(mlo, mhi)
        if count <= 0:
            continue
        pmass = p["_mass_raw"]
        pradius_km = p["_radius_raw"] * _EARTH_RADIUS_KM
        hill = compute_hill_sphere(mass_solar, pmass, p["_a_raw"], p["_ecc_raw"])
        if "error" in hill:
            continue
        outer_au = hill["stable_orbit_limit_au"]
        moons = []
        for j in range(count):
            density = rng.uniform(1.2, 3.5)
            roche = compute_roche_limit(pmass, density, p["_radius_raw"])
            if "error" in roche:
                continue
            inner_au = roche["fluid_au"]
            if outer_au <= inner_au:
                continue                      # no stable annulus (close-in giant)
            sma_au = rng.uniform(inner_au, outer_au)
            frac = rng.uniform(fraclo, frachi)
            moons.append({
                "name": f"{p['name']} {_ROMAN[j] if j < len(_ROMAN) else j + 1}",
                "a_planet_radii": _round(sma_au * 149_597_870.7 / pradius_km, 3),
                "mass_earth": _round(frac * pmass, 6),
                "between_roche_and_hill": True,
                "source": "synthetic",
            })
        p["moons"] = moons


def _strip_private(planets):
    """Drop the internal _-prefixed working fields before emitting."""
    return [{k: v for k, v in p.items() if not k.startswith("_")} for p in planets]


def _has_conservative_hz_rocky(planets):
    return any(p["type"] in ("rocky", "super_earth") and p["hz_class"] == "conservative"
               for p in planets)


def _priors_note_fragment(priors):
    """Provenance fragment for the notes — '<Provider> (grounding=<g>[, dataset <v>])'.

    Uses the class name (DefaultPriors / ResearchPriors) so the permissive output is
    byte-identical to R1/R2; ResearchPriors appends its dataset version.
    """
    ver = getattr(priors, "version", None)
    suffix = f", dataset {ver}" if ver else ""
    return f"{type(priors).__name__} (grounding={priors.grounding}{suffix})"


def _generate_synthetic(seed, spectral_class, n_planets, require_habitable,
                        research_policy="permissive"):
    """Synthetic-from-seed system (anchor_star is None)."""
    rng = random.Random(seed)
    try:
        priors = get_priors(research_policy)
    except PriorsUnavailable as e:
        return {"error": str(e)}

    rows = _usable_ms_rows()
    if not rows:
        return {"error": "Main-sequence reference data unavailable "
                         "(run option 54 to import propertiesOfMainSequenceStars.csv)."}

    built = _synth_star(rng, priors, seed, spectral_class, rows)
    if "error" in built:
        return built
    star, derived = built["star"], built["derived"]

    if require_habitable and n_planets == 0:
        return {"error": "require_habitable needs at least one planet (n_planets is 0)."}

    planets = []
    attempts = 0
    while True:
        attempts += 1
        derived["_n"] = n_planets if n_planets is not None else _weighted_choice(
            rng, sorted(priors.n_planet_dist.items()))
        planets = _synth_planets(rng, priors, star["name"], derived)
        if not require_habitable:
            break
        if _has_conservative_hz_rocky(planets):
            break
        if attempts >= _HABITABLE_TRIES:
            return {"error": "Could not place a habitable world in the conservative "
                             f"HZ after {_HABITABLE_TRIES} attempts — try a different "
                             "seed, more planets, or a cooler spectral class."}

    _attach_moons(rng, priors, star, planets)

    notes = [f"All bodies are synthetic; realism priors = {_priors_note_fragment(priors)}."]
    return {
        "seed": seed,
        "mode": "synthetic",
        "anchor_star": None,
        "star": star,
        "planets": _strip_private(planets),
        "warnings": [],
        "notes": notes,
    }


# ── Real-anchor mode (R1-C3) ─────────────────────────────────────────────────

def _f(v):
    """Coerce an archive/CSV cell to float, or None for blank/non-numeric."""
    if v is None:
        return None
    try:
        s = str(v).strip()
        if s in ("", "nan", "None", "--", "N/A"):
            return None
        return float(v)
    except (ValueError, TypeError):
        return None


def _norm_name(s):
    """Normalise a planet name for cross-source dedup (case/space-insensitive)."""
    return "".join(str(s or "").split()).upper()


def _hz_and_snow(teff, luminosity):
    """Kopparapu HZ map (key→AU) + water snow line AU for a teff/luminosity —
    the same HZ/snow-line basis as synthetic mode, so both modes share one shape."""
    hzmap = {z["key"]: z["au"] for z in compute_habitable_zone(teff, luminosity)}
    ice = compute_ice_lines(luminosity)
    snow = next((ln["au"] for ln in ice.get("lines", []) if ln["kind"] == "snow_line"), None)
    return hzmap, snow


def _observed_planet(name, a, mass, radius, ecc, derived):
    """Build an observed planet dict (source='observed'). Reported mass/radius/ecc
    are the catalog values (None if absent); ``type`` is best-effort from mass, or
    from radius (inverse rocky relation) when mass is unmeasured."""
    eff_mass = mass
    if eff_mass is None and radius is not None and radius > 0:
        eff_mass = radius ** (1.0 / 0.55)          # inverse of _rocky_radius_km exponent
    if eff_mass is not None and eff_mass > 0:
        ptype, est_radius = _classify_planet(eff_mass, a, derived["snow_line"])
    else:
        ptype, est_radius = None, None
    out_radius = radius if (radius is not None and radius > 0) else est_radius
    t_eq = _equilibrium_temp(a, derived["luminosity"])
    in_hz, hz_class = _hz_membership(a, derived)
    return {
        "name": name,
        "a_au": _round(a, 5),
        "mass_earth": _round(mass, 4),
        "radius_earth": _round(out_radius, 4),
        "ecc": _round(ecc, 4),
        "type": ptype,
        "t_eq_k": _round(t_eq, 2),
        "in_hz": in_hz,
        "hz_class": hz_class,
        "source": "observed",
        "atmosphere": None,
        "moons": [],
    }


def _collect_observed(simbad, derived, star_name):
    """Observed planets: NASA pscomppars (priority 1) then HWC (priority 2),
    de-duplicated by name or near-identical SMA. Returns (planets, raw_smas)."""
    observed, smas = [], []
    seen = set()

    comp = compute_planetary_systems_composite(simbad)
    if "error" not in comp:
        for i, row in enumerate(comp.get("planets", [])):
            a = _f(row.get("pl_orbsmax"))
            if a is None or a <= 0:
                continue
            name = str(row.get("pl_name") or f"{star_name} (NASA {i + 1})")
            observed.append(_observed_planet(
                name, a, _f(row.get("pl_bmasse")), _f(row.get("pl_rade")),
                _f(row.get("pl_orbeccen")), derived))
            seen.add(_norm_name(name))
            smas.append(a)

    hwc = compute_hwc(simbad)
    if "error" not in hwc:
        for i, row in enumerate(hwc.get("planet_rows", [])):
            a = _f(row.get("P_SEMI_MAJOR_AXIS"))
            if a is None or a <= 0:
                continue
            name = str(row.get("P_NAME") or f"{star_name} (HWC {i + 1})")
            if _norm_name(name) in seen:
                continue
            if any(abs(a - s) / s < 0.05 for s in smas):   # same orbit, other catalog
                continue
            observed.append(_observed_planet(
                name, a, _f(row.get("P_MASS")), _f(row.get("P_RADIUS")),
                _f(row.get("P_ECCENTRICITY")), derived))
            seen.add(_norm_name(name))
            smas.append(a)

    return observed, smas


def _extension_smas(rng, priors, derived, observed_smas, safe_cap_au, n_synth):
    """SMAs for synthetic extensions: log-spaced from a √L-scaled inner edge,
    skipping any within a spacing-ratio band of an observed orbit, stopping at the
    binary safe cap (when set). Draws in a fixed order (determinism)."""
    if n_synth <= 0:
        return []
    root_l = math.sqrt(derived["luminosity"])
    lo, hi = priors.spacing_ratio
    if safe_cap_au is not None:
        outer = safe_cap_au
    else:
        base = derived["snow_line"] or root_l
        outer = _COLD_FAR_MULT * base * 2.0          # well beyond the snow line
    obs = sorted(observed_smas)

    smas = []
    a = rng.uniform(0.03, 0.12) * root_l
    steps = 0
    while len(smas) < n_synth and steps < 1000:
        steps += 1
        if a > outer:
            break
        # Too close to an observed orbit if within a factor `lo` either way.
        conflict = any(o > 0 and (1.0 / lo) < (a / o) < lo for o in obs)
        if not conflict:
            smas.append(a)
            obs.append(a)
            obs.sort()
        a *= rng.uniform(lo, hi)
    return smas


def _generate_real_anchor(seed, anchor_star, n_planets, require_habitable,
                          research_policy="permissive"):
    """Extend a real star/system: real specs + observed planets + synthetic infill."""
    rng = random.Random(seed)
    try:
        priors = get_priors(research_policy)
    except PriorsUnavailable as e:
        return {"error": str(e)}

    simbad = compute_simbad_lookup(anchor_star)
    if "error" in simbad:
        return simbad

    regions = compute_star_system_regions_from_simbad(simbad)
    if "error" in regions:
        # Non-OBAFGKM primary / missing teff·vmag·plx → can't extend without HZ.
        return regions

    teff = regions["temp"]
    mass_solar = regions["stellarMass"]
    radius_solar = regions["stellarRadius"]
    luminosity = regions["bcLuminosity"]
    hzmap, snow_line = _hz_and_snow(teff, luminosity)

    star_name = simbad.get("main_id") or anchor_star
    sp_type = simbad.get("sp_type") or regions.get("spectral_type") or regions.get("bc_key") or ""

    warnings, notes = [], []

    # Multiplicity: detect via the M5 GCNS n_components block (GCNS-only — the
    # SIMBAD lookup exposes no object-type; documented R1 limitation).
    gcns = simbad.get("gcns") or {}
    n_comp = gcns.get("n_components")
    is_multiple = bool(n_comp and n_comp > 1)
    if is_multiple:
        mult_note = (f"Known Gaia-resolved multiple ({n_comp} components); companion "
                     "dynamical truncation is not modelled in R1 — synthetic bodies are "
                     "conservatively capped (full S/P-type modelling is R2).")
        warnings.append(mult_note)
    else:
        mult_note = ("Single / not a Gaia-resolved multiple (per GCNS); no companion "
                     "truncation applied." if n_comp is not None else
                     "Multiplicity unknown (no GCNS cross-match); treated as single.")

    star = {
        "name": star_name,
        "spectral_class": sp_type,
        "teff": _round(teff, 1),
        "mass_solar": _round(mass_solar, 4),
        "radius_solar": _round(radius_solar, 4),
        "luminosity": _round(luminosity, 6),
        "hz_inner_au": _round(hzmap["rg"], 5),
        "hz_outer_au": _round(hzmap["mg"], 5),
        "hz_opt_inner_au": _round(hzmap["rv"], 5),
        "hz_opt_outer_au": _round(hzmap["em"], 5),
        "snow_line_au": _round(snow_line, 5),
        "source": "observed",
        "grounding": "observed",
        "multiplicity": {"is_multiple": is_multiple, "n_components": n_comp, "note": mult_note},
    }
    derived = {
        "luminosity": luminosity,
        "hz_cons_inner": hzmap["rg"], "hz_cons_outer": hzmap["mg"],
        "hz_opt_inner": hzmap["rv"], "hz_opt_outer": hzmap["em"],
        "snow_line": snow_line,
    }

    observed, observed_smas = _collect_observed(simbad, derived, star_name)
    if not observed:
        warnings.append("No observed planets found (NASA pscomppars / HWC) — "
                        "generating a fully synthetic system around the real star.")

    # Binary safe cap: no synthetic body beyond min(outermost observed, k × HZ outer).
    safe_cap_au = None
    if is_multiple:
        caps = [_BINARY_SAFE_CAP_K * hzmap["mg"]]
        if observed_smas:
            caps.append(max(observed_smas))
        safe_cap_au = min(caps)

    observed_ok = _has_conservative_hz_rocky(observed)
    if require_habitable and not observed_ok and (n_planets == 0):
        return {"error": "require_habitable: the real system has no conservative-HZ "
                         "rocky planet and n_planets is 0 (no synthetic infill allowed)."}

    synth = []
    attempts = 0
    while True:
        attempts += 1
        n_syn = n_planets if n_planets is not None else _weighted_choice(
            rng, sorted(priors.n_planet_dist.items()))
        ext_smas = _extension_smas(rng, priors, derived, observed_smas, safe_cap_au, n_syn)
        synth = [_make_synth_planet(rng, priors, f"{star_name} (synthetic {k + 1})", a, derived)
                 for k, a in enumerate(ext_smas)]
        if not require_habitable:
            break
        if observed_ok or _has_conservative_hz_rocky(synth):
            break
        if attempts >= _HABITABLE_TRIES:
            return {"error": "Could not place a habitable world in the conservative HZ "
                             f"after {_HABITABLE_TRIES} attempts — try a different seed, "
                             "more planets, or another anchor star."}

    _attach_moons(rng, priors, star, synth)

    planets = observed + _strip_private(synth)
    planets.sort(key=lambda p: (p["a_au"] is None, p["a_au"]))

    notes.append("Observed bodies from NASA pscomppars / HWC; synthetic extensions use "
                 f"{_priors_note_fragment(priors)}. Observed planets carry no fabricated moons.")
    return {
        "seed": seed,
        "mode": "real_anchor",
        "anchor_star": anchor_star,
        "star": star,
        "planets": planets,
        "warnings": warnings,
        "notes": notes,
    }


def generate_system(seed, anchor_star=None, spectral_class=None,
                    n_planets=None, require_habitable=False,
                    constraints=None, companion=None,
                    research_policy="permissive", nbody=False):
    """Deterministically generate a plausible planetary system.

    Two modes share one output shape:
      • synthetic-from-seed (``anchor_star`` is None) — built here (R1-C2);
      • real-anchor (``anchor_star`` given) — extends a real star/system (R1-C3).

    Determinism contract: same ``seed`` (+ same ``anchor_star`` + same constraint
    spec) → byte-identical output. Self-validating: bad input → ``{"error": str}``.

    When ``constraints`` is non-empty (Phase R2), generation is delegated to the
    constraint/feasibility engine, which builds the base system here and layers a
    four-layer feasibility verdict on top. **Zero constraints → the R1 path,
    byte-identical** (the R2 kwargs are additive).

    Args:
        seed: integer RNG seed (required).
        anchor_star: real star name to anchor on; None → synthetic mode.
        spectral_class: optional 'K2V'-style class (synthetic only); sampled if None.
        n_planets: optional planet count (0–15); sampled if None.
        require_habitable: if True, retry until a conservative-HZ rocky world lands
                           (bounded), else error.
        constraints: optional list of constraint dicts (Phase R2) → feasibility mode.
        companion: optional multi-star hint ``{mass_solar, sma_au[, ecc]}`` (Phase R2).
        research_policy: ``"permissive"`` (default) | ``"strict"`` (R3).
        nbody: opt-in N-body confirmation of marginal verdicts (Phase R2-C4).
    """
    if not isinstance(seed, int) or isinstance(seed, bool):
        return {"error": "seed must be an integer."}
    if n_planets is not None:
        if not isinstance(n_planets, int) or isinstance(n_planets, bool):
            return {"error": "n_planets must be an integer."}
        if not (0 <= n_planets <= _MAX_N_PLANETS):
            return {"error": f"n_planets must be between 0 and {_MAX_N_PLANETS}."}
    if research_policy not in ("permissive", "strict"):
        return {"error": "research_policy must be 'permissive' or 'strict' "
                         f"(got {research_policy!r})."}

    if constraints:
        # Function-local import: generate.py must stay importable without pulling
        # in core.feasibility at module load (feasibility imports back into here).
        from core.feasibility import evaluate_feasibility
        return evaluate_feasibility(seed, anchor_star, spectral_class, n_planets,
                                    require_habitable, constraints, companion,
                                    research_policy, nbody)

    if anchor_star is not None and str(anchor_star).strip():
        return _generate_real_anchor(seed, anchor_star, n_planets, require_habitable,
                                     research_policy)

    return _generate_synthetic(seed, spectral_class, n_planets, require_habitable,
                               research_policy)


def generate_from_spec(spec):
    """Re-run generate_system from a stored generation spec (Phase S).

    A "spec" is the dict a project workspace persists for a generated member
    (``generated_spec`` — the generation params, plus an ignored ``mode`` echo).
    Maps it to keyword args and returns the (deterministic) generate_system result.
    """
    spec = spec or {}
    return generate_system(
        spec.get("seed"),
        anchor_star=spec.get("anchor_star"),
        spectral_class=spec.get("spectral_class"),
        n_planets=spec.get("n_planets"),
        require_habitable=spec.get("require_habitable", False),
        constraints=spec.get("constraints"),
        companion=spec.get("companion"),
        research_policy=spec.get("research_policy", "permissive"),
        nbody=spec.get("nbody", False),
    )
