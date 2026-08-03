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
    compute_stellar_evolution,
)
from core.science import compute_main_sequence_table
from core.formation import (
    compute_disk_model,
    compute_isolation_mass,
    compute_pebble_isolation_mass,
    compute_critical_core_mass,
    compute_gap_opening_mass,
)
from core.priors import DefaultPriors, get_priors, PriorsUnavailable
from core.databases import (
    compute_simbad_lookup,
    compute_planetary_systems_composite,
    compute_hwc,
    compute_mission_exocat,
    compute_hypatia_data,
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
_GIANT_TYPES = {"gas", "super_jovian", "brown_dwarf"}   # true giants (R3-V2 F3 chain-exempt)
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

    feh = _draw_feh(rng, priors)     # R3-V2 F2: host [Fe/H] (None unless feh_dist present)
    feh_source = "feh_dist" if feh is not None else None
    disk_mass_mult = _draw_disk_mass_mult(rng, priors)          # L2: per-system disk mass
    system_forms_giants = _roll_system_forms_giants(rng, priors, feh)   # L2: growth race

    teff, radius_solar, mass_solar = _interp_star_props(_spectral_index(letter, subtype), rows)
    luminosity = compute_star_luminosity(radius_solar, teff)["luminosity"]

    hz = compute_habitable_zone(teff, luminosity)
    hzmap = {z["key"]: z["au"] for z in hz}
    ice = compute_ice_lines(luminosity)
    snow_line = next((ln["au"] for ln in ice.get("lines", []) if ln["kind"] == "snow_line"), None)

    # B2/B1/B3 draw order, and it is load-bearing:
    #   age  → needed by B3's (M_tot, age) wide-companion survival half-life, and by the
    #          activity chain's single-star branches;
    #   multiplicity → truncated by that limit, and supplies p_orb_days;
    #   activity → reads the companion (locked branch) and the age (single branches).
    # Each is None — and consumes no rng — without its block, so a v1 dataset is unchanged.
    age_gyr = _draw_age(rng, priors, mass_solar)
    multiplicity = _draw_multiplicity(rng, priors, mass_solar, age_gyr)
    activity = _draw_activity(rng, priors, mass_solar, luminosity, age_gyr,
                              (multiplicity or {}).get("companion"))

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
        "feh": _round(feh, 3),
        "feh_source": feh_source,
        "age_gyr": _round(age_gyr, 3) if age_gyr is not None else None,
        "age_source": "age_dist" if age_gyr is not None else None,
        "source": "synthetic",
        "grounding": priors.grounding,
        "multiplicity": multiplicity,
        "activity": activity,
    }
    derived = {
        "teff": teff, "mass_solar": mass_solar, "luminosity": luminosity,
        "hz_cons_inner": hzmap["rg"], "hz_cons_outer": hzmap["mg"],
        "hz_opt_inner": hzmap["rv"], "hz_opt_outer": hzmap["em"],
        "snow_line": snow_line, "feh": feh,
        "disk_mass_mult": disk_mass_mult,               # L2
        "system_forms_giants": system_forms_giants,     # L2
        # B1: the drawn companion in the `--companion` hint shape, so the feasibility
        # engine's existing binary gate can consume it (None when not multiple).
        "companion": (multiplicity or {}).get("companion"),
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


# ── Phase R3-V2 · F1 mass_model draw (isolation-mass scaling) ────────────────
#
# When a strict ResearchPriors dataset carries a `mass_model` block, planet mass
# is a *function* of the local disk surface density, orbit, and stellar mass —
# M_iso(Σ, a, M★) via the Group P calculators — with a physics-gated giant switch,
# instead of the flat log-uniform mass_by_zone band. Absent block → the v1 draw
# (the else-branch in _make_synth_planet), byte-identical.
#
# HOW the engine samples from the handed-off physics is our choice (the sister
# contract hands off the physics, not the sampling procedure). Our procedure:
#   1. Σ_solid(a) from the disk profile (F1, compute_disk_model).
#   2. M_iso from the oligarchic isolation mass with the MUTUAL-Hill full-width
#      convention (feeding_zone_b = mass_model.feeding_zone_hill — gotcha #1: the
#      contract's "10 Hill radii" is mutual full-width, NOT the single-Hill
#      half-width C=2√3 default).
#   3. Giant switch (F3+F6): a giant forms only where the pebble-isolation mass
#      reaches the critical core mass AND the orbit is beyond the snow line →
#      gas runaway. This places giants by physics (fixing the v1 flat-tail giant
#      that could land anywhere), else the body is a solid-dominated oligarch.
#   4. Solid bodies draw a merger-growth scatter about M_iso; giants draw
#      log-uniform from the critical core to the ~13 M_J planet/BD boundary.
# The scatter band + giant ceiling are engine knobs (documented, not pinned).
_MASS_MODEL_SCATTER = (2.0, 40.0)  # merger-growth spread about M_iso — B6/L2-calibrated so
                                   # solar small planets land ~1–2 M⊕ (was (0.5,8.0) → 0.10 M⊕
                                   # sub-Mars); paired with the disk_mass_dist lever (≈2.5× MMSN)

# R3-V2 B6/L1: the gas-runaway giant draw ceiling. The Type-II gap-opening mass (F4)
# at giant-forming orbits is only ~0.3–1.4 M_J — a growth-throttling *transition*, not
# the upper limit (accretion continues past a gap), so it is too low to be the ceiling.
# The physical hard limit is the planet/brown-dwarf (deuterium-burning) boundary
# ~13 M_J. Capping here (vs the old 600 M⊕ = 1.9 M_J v1-band reuse) restores the
# super-Jupiter population (2–13 M_J) mass_model was built to include (canon cold
# giants 0.3–13 M_J). A draw at the boundary classifies as super_jovian (< 13 M_J
# almost surely under the log-uniform); brown dwarfs are not a target here.
_GIANT_MASS_CEILING_EARTH = _BROWN_DWARF_MIN_EARTH   # ~13 M_J (4131.4 M⊕)

# ── Phase R3-V2 · F2 metallicity conditioning (occurrence_by_metallicity + feh_dist) ──
#
# When a strict dataset carries `occurrence_by_metallicity` and the host has a drawn
# [Fe/H] (synthetic: from `feh_dist`; real-anchor: Hypatia-preferred, SIMBAD
# mesfe_h.fe_h fallback — see _resolve_anchor_feh), three effects fire — all gated, so
# permissive/v1 stay byte-identical:
#   • giant gating — a physics-eligible giant (F1 switch) forms with probability
#     giant_fraction([Fe/H]) / giant_fraction(0) (the SHAPE relative to solar, not the
#     absolute level — gotcha #3), interpolated CLAMPED to feh_grid (gotcha #2).
#   • count shift — the planet-count draw is tilted toward higher counts with rising
#     [Fe/H] (gotcha #4 small-planet scaling; the tilt strength is an engine knob).
#   • super-Earth floor — below superearth_floor_feh, solid bodies are capped below
#     the super-Earth threshold (gotcha #4 metal-poor super-Earth cliff).
_METALLICITY_COUNT_TILT = 0.4       # exp(tilt·[Fe/H]·k) count reweight (engine knob)


def _giant_fraction_at(occ, feh):
    """Interpolate giant_fraction on feh_grid, CLAMPED to the grid domain — hold the
    endpoints outside it (gotcha #2: the FV05 fit is valid only within feh_grid)."""
    grid, frac = occ["feh_grid"], occ["giant_fraction"]
    if feh <= grid[0]:
        return frac[0]
    if feh >= grid[-1]:
        return frac[-1]
    for i in range(1, len(grid)):
        if feh <= grid[i]:
            lo, hi = grid[i - 1], grid[i]
            t = (feh - lo) / (hi - lo) if hi > lo else 0.0
            return frac[i - 1] + t * (frac[i] - frac[i - 1])
    return frac[-1]


def _resolve_anchor_feh(simbad):
    """Real-anchor host [Fe/H] → (value, source). **Hypatia-preferred, SIMBAD fallback.**

    Hypatia is the homogenized abundance catalog (all [Fe/H] on the Lodders-2009 scale),
    so its value is preferred where the star is in its domain; SIMBAD's heterogeneous
    ``mesfe_h.fe_h`` is used only as a fallback for stars Hypatia doesn't cover. Returns
    ``(None, None)`` when neither has a value. The SIMBAD lookup still runs first
    structurally (it resolves the designations Hypatia queries on) — only the *value*
    precedence prefers Hypatia. One extra network call, consistent with opt-8 / compare.
    """
    hyp = compute_hypatia_data(simbad)
    if isinstance(hyp, dict) and "error" not in hyp:
        for ab in hyp.get("abundances", []):
            # neutral Fe only ([Fe/H]); exclude ionized species like "Fe_II".
            if str(ab.get("element")).lower() == "fe" and ab.get("mean") is not None:
                val = _f(ab["mean"])
                if val is not None:
                    return val, "hypatia"
    sfeh = _f(simbad.get("fe_h"))
    if sfeh is not None:
        return sfeh, "simbad"
    return None, None


def _resolve_anchor_age(simbad):
    """Real-anchor host age (Gyr) → (value, source). **HWC S_AGE → Mission Exocat st_age.**

    The age mirror of ``_resolve_anchor_feh``: an observed star's age is *read from an
    observed catalogue*, never drawn from the synthetic ``age_dist`` SFH (an observed star
    must not inherit a modelled age). Both catalogues report stellar age in **Gyr** — HWC
    ``S_AGE`` spans 0.001–14.9 (median ≈ 4.0), Mission Exocat ``st_age`` 0.4–15.0 (median
    ≈ 6.0), both verified 2026-08-03 — and both readers are *local CSV lookups* (no network;
    ``compute_hwc`` is already read for the anchor's planet rows in ``_collect_observed``).
    HWC wins where both list an age (larger, more homogeneous catalogue); Mission Exocat is
    the fallback. A non-positive value is treated as absent. Returns ``(None, None)`` when
    neither catalogue has an age — the normal case (most stars carry no measured age).
    """
    hwc = compute_hwc(simbad)
    if isinstance(hwc, dict) and "error" not in hwc:
        age = _f((hwc.get("star_row") or {}).get("S_AGE"))
        if age is not None and age > 0:
            return age, "hwc"
    exo = compute_mission_exocat(simbad)
    if isinstance(exo, dict) and "error" not in exo:
        age = _f((exo.get("exocat") or {}).get("st_age"))
        if age is not None and age > 0:
            return age, "mission_exocat"
    return None, None


def _draw_feh(rng, priors):
    """Synthetic host [Fe/H] from the feh_dist axis (Gaussian mean/sigma + optional
    clamp), or None when the dataset omits feh_dist (→ F2 conditioning inert)."""
    fd = getattr(priors, "feh_dist", None)
    if not fd:
        return None
    val = rng.normalvariate(fd["mean"], fd["sigma"])
    lo, hi = fd.get("min"), fd.get("max")
    if lo is not None:
        val = max(val, lo)
    if hi is not None:
        val = min(val, hi)
    return val


def _metallicity_count_items(priors, derived):
    """(count, weight) items for the planet-count draw — metallicity-tilted toward
    higher counts with rising [Fe/H] when occurrence_by_metallicity + a host [Fe/H]
    are present, else the plain v1 sorted items (byte-identical)."""
    items = sorted(priors.n_planet_dist.items())
    occ = getattr(priors, "occurrence_by_metallicity", None)
    feh = derived.get("feh")
    if not occ or feh is None:
        return items
    return [(k, w * math.exp(_METALLICITY_COUNT_TILT * feh * k)) for k, w in items]


# ── Phase R3-V2 · B1 (v2.4/v2.9) · stellar multiplicity + companion sampler ─────
#
# The first STELLAR axis the generator samples — every other block is planetary (the
# `multiplicity` key inside cold_giant_population is a GIANT count, not a stellar one).
# Per system: multiplicity roll (mass-dependent) → mass ratio q → separation (the
# close-pair / wide-log-normal mixture) → eccentricity. The companion is emitted in the
# block's own `consumer_contract` shape {mass_solar, sma_au, ecc, p_orb_days, close_pair},
# which is exactly the `--companion` hint `feasibility._binary_gate` already consumes — so
# a drawn companion reaches the Holman–Wiegert S/P-type gate through the existing path,
# with NO parallel code path.
#
# Two dataset rules, both hard and both covered by tests:
#   • `ecc_dist.consumer_must_not_default_to_zero` — a silent e = 0 makes every drawn
#     binary maximally planet-friendly and inflates stable-HZ rates. Never emit e == 0.
#   • the circularization period is a STATISTICAL boundary, never a hard cut (BY Dra sits
#     at e = 0.300 with P = 5.98 d, inside it). ~6 d is the M-dwarf value (v2.9.0,
#     Packet-4 C52: Zanazzi 2022 + EBLM XVII + the local 57-system e–P transition);
#     Raghavan's 12 d is the separate SOLAR-TYPE reference and is deliberately not used.
#
# APP-SIDE MODELLING CHOICES — the block states f(e) in prose, not parametrically, so the
# following are OURS and are named as such in the emitted note (never presented as pinned):
#   • above the boundary: Rayleigh(σ = 0.21) clamped to ≤ 0.9 → median ≈ 0.25, matching the
#     block's "broad_median_~0.25_trending_thermal_tail_to_~0.9";
#   • below the fully-circular envelope: a half-normal (σ = 0.01) floored at 0.001 — near
#     zero but never zero (CM Dra is e = 0.005);
#   • between envelope and boundary: a linear ramp between those two, so the boundary is
#     soft from both sides rather than a step;
#   • higher-order systems are COUNTED in `n_components` but only the primary companion is
#     placed — stated in the note rather than silently dropped.

# ── B3 (2026-07-23) · the wide-companion survival half-life scale ───────────────
#
# There is NO fixed outer cutoff on binary separation — D&K: "there is no absolute upper
# bound on binary separation, but rather a gradual rarity beyond a certain separation."
# What erodes wide pairs is CUMULATIVE small stellar encounters, giving a survival timescale
# that shrinks with age and scales with mass (Weinberg, Shapiro & Wasserman 1987 eq. 28, via
# Dhital 2010): a_half ≃ 1.212 × (M_tot / t) pc, for M☉ and Gyr.
#
# *** WHAT THIS QUANTITY IS — AND IS NOT. *** Weinberg's t½ is a HALF-LIFE: the time by which
# HALF the binaries at a given separation have been disrupted. It is NOT "the widest binary
# still surviving at age t" — that gloss entered via the secondary source and we inherited it
# verbatim. The paper's own headline finding is the opposite of a wall:
#
#     "We find no evidence of breaks or cutoffs in most of the scenarios."  (abstract)
#
# So HARD-TRUNCATING here is a MODELLING CONVENIENCE, not a physical boundary: roughly half
# the population AT this separation actually survives. It is kept because the affected mass
# is 0.1–3% of draws and because the honest alternative — smooth attenuation — would require
# a survival law nobody has pinned, and inventing one is the same error as inventing the join
# weight below. If a decay law is ever pinned, attenuate instead of cutting.
#
# EVIDENCE GRADE — theory (a dynamics calculation) with PARTIAL, INDIRECT observational
# support. Two earlier drafts of this comment were wrong and the corrections are kept visible,
# because an overclaim that is quietly fixed is the kind that comes back: (1) it said
# "observed, not merely modelled" — WITHDRAWN, the ~0.1 pc-break leg is dead (that peak is
# contamination-dominated), the disk-vs-halo shape leg is ambiguous (Tian 2020 attribute the
# steepening to initial conditions), and only a frequency-versus-age leg survives; (2) it
# carried a ~4% prefactor slack — RETRACTED, see the coefficient note below.
#
# TWO SOURCE CAVEATS worth knowing before anyone "improves" the formula. Eq. 28 is the
# paper's NAIVE estimate ("advective diffusion alone"); its own Monte Carlo rejects the a^−1
# scaling in this range, finding t½ ∝ a₀^−1.34 for 0.1 < a₀ < 0.5 pc. But the simulation fit
# (eq. 56) has NO M_tot dependence — it is fitted at one fiducial binary mass — so eq. 28 is
# the only mass-dependent form the paper offers, and using it is deliberate. The practical
# difference is small and CHANGES SIGN with mass (removed fraction 0.09% → 0.11% at
# M_tot 0.45/5 Gyr; identical at 0.45/10 Gyr; eq. 28 is MORE aggressive at 0.25/10 Gyr,
# 0.40% vs 0.21%). Also: eq. 28 is STARS-ONLY, while the paper finds "the lifetimes cannot be
# understood by considering encounters with stars and clouds individually" — so this
# under-describes the combined stellar + GMC erosion by construction.
#
# WE DO NOT ADD AN ÖPIK / POWER-LAW TAIL. The measured index is −1.6 in dN/ds (NOT Öpik's
# −1), but a two-component mixture needs a JOIN NORMALIZATION, and the source lineage
# declares that unknown: "it remains unclear whether and how these two distributions are
# physically connected." Inventing a join weight is precisely the double-count this dataset
# has twice warned about. So: ONE log-normal, truncated here.
#
# IF THAT DECISION IS EVER REVERSED, two constraints travel with the −1.6 and neither was
# known when this was written: (a) a SINGLE power law is excluded — Tian 2020 favour TWO
# breaks (~10^3.8 AU and ~10^4.5 AU), and the single-slope result holds only for a
# disk-dominated sample over 500–50,000 AU; (b) the index is NOT mass-dependent — El-Badry
# 2019 fits M dwarfs at −1.62 ± 0.16 against solar-type −1.58 ± 0.09, indistinguishable, so
# −1.6 applies to M primaries too. The FREQUENCY mass-dependence is a different quantity and
# still stands (never apply THAT flat).
#
# THE COEFFICIENT IS CLEARED. A ~4% slack was carried here while Weinberg 1987 was known only
# through Dhital, who state the law with a (ln Λ)⁻¹ factor and then substitute Λ = 1 — making
# ln Λ = 0 and the lifetime divergent, so the stated inputs could not produce the stated
# output. The primary was opened 2026-07-23: eq. 28 reproduces the paper's own reference point
# ("t_*(a₀) ≈ 10¹⁰ yr … for a₀ ≈ 0.1 pc"), the incoherence is immaterial, and the slack is
# RETRACTED. 1.212 is primary-verified; no uncertainty band is emitted for it.
#
# ONE THING RECORDED RATHER THAN SMOOTHED OVER (from the sister's adversarial refute-pass):
#
#      A SOLAR-HOST SHAPE CAVEAT, and it errs UNSAFE. Local slope of this σ = 1.16
#      log-normal in dN/dlog s vs the measured −0.60: for M centres (5.3 AU) it is −0.64 at
#      500 AU and steepens, so the tail is UNDER-produced — safe, and 66.5% of drawn
#      companions. For solar centres (42 AU) it is −0.35 at 500 AU, shallower than measured
#      until it crosses −0.60 at ~3000 AU, so wide companions are OVER-produced there.
#      ~10.4% of companions. It is the one regime where one component is genuinely worse
#      than a power law — recorded because the alternative (a mixture) needs the join
#      weight that does not exist, not because it is acceptable.

_DISRUPTION_COEFF = 1.212        # pc per (M☉ / Gyr) — Weinberg 1987 eq. 28 (primary-verified)
_PC_AU = 206264.806              # AU per parsec
# Q3 (v2.11.0) — smooth wide-pair survival S(a) = 0.5^((a/a_half)^p): 0.5 at a_half, smooth,
# NO cutoff (Weinberg / Tian — the hard cut is confirmed wrong). p ∈ 1.2–1.5 is a TUNABLE
# modelling convenience (the true WSW curve is non-exponential, no closed form is pinnable).
_WIDE_SURVIVAL_P     = 1.35
# Q4 (v2.11.0) — the continuity splice for the two-break power-law tail. The tail's PDF is set
# EQUAL to the log-normal PDF at s_join (Tian 2020 recipe → normalization with zero free
# parameters, dissolving the old "unknown join weight" blocker). s_join is the mid of the
# sister's stated ~500–2000 AU window (below break_1, in the γ1 regime).
_WIDE_TAIL_S_JOIN_AU = 1000.0
_MULT_TRUNC_TRIES     = 64      # wide-component truncation resampling bound
_MULT_ECC_FLOOR       = 0.001   # "NEVER e == 0 identically"
_MULT_ECC_MAX         = 0.9     # the block's stated tail limit (e_max fallback)
_MULT_ECC_NEAR_SIGMA  = 0.01    # half-normal σ below the fully-circular envelope
_DAYS_PER_JULIAN_YEAR = 365.25

# Q2 (v2.11.0) — companion eccentricity f(e) ∝ e^η above the circularization boundary
# (Moe & Di Stefano 2017, ApJS 230, 15 §§8.7/9.2), replacing the fixed Rayleigh(σ=0.21)
# placeholder. η is period- AND primary-mass-dependent; drawn by inverse-CDF on [0, e_max]:
# e = e_max·u^(1/(η+1)). Coefficients are hardcoded from the dataset's `f_e_functional_form`
# formula STRINGS (like _TAU_RELATION), with a drift test asserting the strings still match so
# a sister-side change fails loudly. Late-type (0.8–3 M☉) is the workhorse (census ~90% M+K+G);
# early-type (>7 M☉) reaches thermal (η→1); 3–7 M☉ interpolates. Below the ~6 d boundary η is
# ill-defined (→−∞) and the near-circular envelope owns that zone.
_ECC_ETA_LATE    = (0.6, 0.7)   # η = 0.6 − 0.7/(logP−0.5),  M1 = 0.8–3 M☉
_ECC_ETA_EARLY   = (0.9, 0.2)   # η = 0.9 − 0.2/(logP−0.5),  M1 > 7 M☉
_ECC_ETA_M_LATE  = 3.0          # ≤ → late-type; ≥ _ECC_ETA_M_EARLY → early-type; between → interp
_ECC_ETA_M_EARLY = 7.0
_ECC_ETA_FLOOR   = -0.9         # keep e^η normalizable on [0, e_max] (η+1 ≥ 0.1)


def _interp_log10_mass(grid, values, mass_solar):
    """Linear-in-log10(mass) interpolation with endpoints held — the block's
    ``linear_in_log10_mass_hold_endpoints`` (F-4: linear in log₁₀ M, *not* in M)."""
    if not grid or not values or len(grid) != len(values):
        return None
    if mass_solar <= grid[0]:
        return values[0]
    if mass_solar >= grid[-1]:
        return values[-1]
    for i in range(len(grid) - 1):
        if grid[i] <= mass_solar <= grid[i + 1]:
            span = math.log10(grid[i + 1]) - math.log10(grid[i])
            f = 0.0 if span == 0 else (math.log10(mass_solar) - math.log10(grid[i])) / span
            return values[i] + f * (values[i + 1] - values[i])
    return values[-1]


def _kepler_sma_au(total_mass_solar, period_days):
    """Kepler III — a (AU) from orbital period and total system mass."""
    return (total_mass_solar * (period_days / _DAYS_PER_JULIAN_YEAR) ** 2) ** (1.0 / 3.0)


def _kepler_period_days(total_mass_solar, sma_au):
    """Kepler III inverted — P (days) from separation and total system mass."""
    return _DAYS_PER_JULIAN_YEAR * math.sqrt(sma_au ** 3 / total_mass_solar)


def _draw_mass_ratio(rng, mrd):
    """q from ``mass_ratio_dist`` — a q^slope power law over [q_min, q_max] with the twin
    excess applied as a density multiplier above ``twin_excess_above_q``."""
    slope = float(mrd.get("slope") or 0.0)
    q_lo = float(mrd.get("q_min") or 0.1)
    q_hi = float(mrd.get("q_max") or 1.0)
    p = slope + 1.0
    if abs(p) < 1e-9:                     # p(q) ∝ 1/q — log-uniform limit
        return q_lo * (q_hi / q_lo) ** rng.random()

    def _seg_mass(a, b):
        return (b ** p - a ** p) / p

    def _inv_cdf(a, b, u):
        return (a ** p + u * (b ** p - a ** p)) ** (1.0 / p)

    q_twin = mrd.get("twin_excess_above_q")
    factor = float(mrd.get("twin_excess_factor") or 1.0)
    if q_twin is None or not (q_lo < float(q_twin) < q_hi) or factor == 1.0:
        return _inv_cdf(q_lo, q_hi, rng.random())
    q_twin = float(q_twin)
    w_lo, w_hi = _seg_mass(q_lo, q_twin), factor * _seg_mass(q_twin, q_hi)
    if rng.random() * (w_lo + w_hi) < w_lo:
        return _inv_cdf(q_lo, q_twin, rng.random())
    return _inv_cdf(q_twin, q_hi, rng.random())


def _companion_ecc_eta(log_p, mass_solar):
    """Q2 — MDS17 η(logP, M1) for f(e) ∝ e^η: late-type (≤ 3 M☉) / early-type (≥ 7 M☉),
    linear in M1 across 3–7 M☉, floored at _ECC_ETA_FLOOR so the power law stays
    normalizable on [0, e_max]. η has a pole at logP = 0.5; the e^η branch only fires above
    the ~6 d boundary (logP ≳ 0.78) so the guard never bites there."""
    denom = log_p - 0.5
    if denom <= 0:
        return _ECC_ETA_FLOOR
    eta_late = _ECC_ETA_LATE[0] - _ECC_ETA_LATE[1] / denom
    eta_early = _ECC_ETA_EARLY[0] - _ECC_ETA_EARLY[1] / denom
    if mass_solar <= _ECC_ETA_M_LATE:
        eta = eta_late
    elif mass_solar >= _ECC_ETA_M_EARLY:
        eta = eta_early
    else:
        f = (mass_solar - _ECC_ETA_M_LATE) / (_ECC_ETA_M_EARLY - _ECC_ETA_M_LATE)
        eta = (1.0 - f) * eta_late + f * eta_early
    return max(eta, _ECC_ETA_FLOOR)


def _draw_companion_ecc(rng, ecc_dist, period_days, mass_solar):
    """Eccentricity under the ``ecc_dist`` statistical boundary (never a hard cut, never 0).

    Above the ~6 d circularization boundary the value is the Q2 (v2.11.0) f(e) ∝ e^η power
    law (MDS17, period+primary-mass-dependent); below the fully-circular envelope it stays
    near-circular-not-zero; between, a ramp. All three variates are drawn unconditionally so
    rng consumption does not depend on which branch the period lands in — the branch changes
    the value, not the stream.
    """
    u_pl, z_near, u_mix = rng.random(), rng.gauss(0.0, 1.0), rng.random()
    e_max = float(ecc_dist.get("e_max") or _MULT_ECC_MAX)
    near = abs(z_near) * _MULT_ECC_NEAR_SIGMA
    if period_days and period_days > 0:
        eta = _companion_ecc_eta(math.log10(period_days), mass_solar)
        broad = e_max * u_pl ** (1.0 / (eta + 1.0))     # inverse-CDF of f(e) ∝ e^η
    else:
        broad = near
    p_circ = float(ecc_dist.get("circularization_period_days") or 6.0)
    p_full = float(ecc_dist.get("fully_circular_envelope_days") or 0.0)
    if period_days <= p_full:
        ecc = near
    elif period_days >= p_circ or p_circ <= p_full:
        ecc = broad
    else:
        ramp = (period_days - p_full) / (p_circ - p_full)
        ecc = broad if u_mix < ramp else near
    return min(max(ecc, _MULT_ECC_FLOOR), _MULT_ECC_MAX)


def _wide_disruption_half_life_au(m_total_solar, age_gyr):
    """B3 — the (M_tot, age) wide-companion survival **half-life** scale, in AU.

    ``a_half ≃ 1.212 × (M_tot / t)`` pc (Weinberg 1987 eq. 28). This is the separation at
    which roughly **half** the population has been disrupted by age *t* — NOT the widest
    surviving pair, and the source explicitly finds "no evidence of breaks or cutoffs".
    Truncating here is a labelled modelling convenience; see the section comment.

    Returns None when there is no age to key it to (a v1 dataset with no ``age_dist``): the
    scale is a function of age, so without one there is nothing to apply — and a *constant*
    stand-in would be the fixed cutoff the sources say does not exist.
    """
    if not age_gyr or age_gyr <= 0 or not m_total_solar or m_total_solar <= 0:
        return None
    return _DISRUPTION_COEFF * (m_total_solar / age_gyr) * _PC_AU


def _wide_survival(sma, a_half):
    """Q3 — smooth wide-pair survival fraction S(a) = 0.5^((a/a_half)^p): 0.5 at the
    half-life scale, monotone, no cutoff. Returns 1.0 when there is no age scale to key it to
    (``a_half`` None), i.e. the roll-off is inert without an age axis (as the hard cut was)."""
    if not a_half or a_half <= 0 or sma <= 0:
        return 1.0
    return 0.5 ** ((sma / a_half) ** _WIDE_SURVIVAL_P)


def _lognormal_pdf_s(sma, log10_centre, sigma):
    """PDF in linear s of a variable whose log10 is N(log10_centre, σ) — the density the
    power-law tail is spliced against (both are dN/ds, so the ratio is well-defined)."""
    if sma <= 0 or sigma <= 0:
        return 0.0
    z = (math.log10(sma) - log10_centre) / sigma
    return math.exp(-0.5 * z * z) / (sma * math.log(10.0) * sigma * math.sqrt(2.0 * math.pi))


def _broken_powerlaw_factor(sma, s_join, g1, b1, gmid, b2, g2):
    """Two-break dN/ds power law relative to its value at ``s_join`` (= 1 there), continuous
    at each break: slope g1 to b1, gmid (the gradual steepening) to b2, g2 beyond."""
    factor, lo = 1.0, s_join
    for hi, g in ((b1, g1), (b2, gmid), (float("inf"), g2)):
        if sma <= hi:
            return factor * (sma / lo) ** g
        factor *= (hi / lo) ** g
        lo = hi
    return factor


def _wide_tail_thinning(sma, s_join, log10_centre, sigma, tail):
    """Q4 — beyond the splice s_join, accept a log-normal draw with probability
    min(1, PL(s)/LN(s)), thinning the LN's tail down to the continuity-spliced two-break power
    law (PL(s_join) = LN(s_join), so no invented join weight). Below s_join → 1.0. Where the LN
    already runs steeper than the tail (M-dwarf centres) the ratio is ≥ 1 → no thinning (safe);
    where it runs shallower (solar centres) it thins the over-produced wide companions."""
    if sma <= s_join or not tail:
        return 1.0
    ln_here = _lognormal_pdf_s(sma, log10_centre, sigma)
    ln_join = _lognormal_pdf_s(s_join, log10_centre, sigma)
    if ln_here <= 0 or ln_join <= 0:
        return 1.0
    g1 = float(tail.get("gamma_1") or -1.55)
    b1 = 10.0 ** float(tail.get("break_1_log10_au") or 3.8)
    b2 = 10.0 ** float(tail.get("break_2_log10_au") or 4.5)
    g2 = float(tail.get("gamma_2_disk") or -2.07)
    gmid = 0.5 * (g1 + g2)         # gradual steepening between the two breaks (not pinned)
    pl_here = ln_join * _broken_powerlaw_factor(sma, s_join, g1, b1, gmid, b2, g2)
    return min(1.0, pl_here / ln_here)


def _draw_multiplicity(rng, priors, mass_solar, age_gyr=None):
    """Stellar multiplicity + (when multiple) one companion, from the v2.4/v2.9
    ``stellar_multiplicity`` block, with B3's (M_tot, age) outer bound applied to the wide
    component.

    Returns ``None`` — consuming **no** rng — when the dataset omits the block, so a v1
    dataset / ``DefaultPriors`` run stays byte-identical.
    """
    sm = getattr(priors, "stellar_multiplicity", None)
    if not sm:
        return None
    mfd = sm.get("multiplicity_fraction") or {}
    frac = _interp_log10_mass(mfd.get("mass_msun_grid") or [], mfd.get("fraction") or [],
                              mass_solar)
    if frac is None:
        return None

    if rng.random() >= frac:
        return {"is_multiple": False, "n_components": 1, "companion": None,
                "note": (f"Single — drawn against a {frac:.3f} multiplicity fraction at "
                         f"{mass_solar:.3f} M☉ (stellar_multiplicity prior).")}

    higher = float((sm.get("higher_order_fraction") or {}).get("value") or 0.0)
    n_comp = 3 if rng.random() < higher else 2

    comps = {c.get("name"): c
             for c in ((sm.get("separation_dist") or {}).get("components") or [])}
    close, wide = comps.get("close_pair"), comps.get("wide_lognormal")
    q = _draw_mass_ratio(rng, sm.get("mass_ratio_dist") or {})
    m2 = q * mass_solar
    total = mass_solar + m2

    truncation_fallback = False
    disrupted = False
    a_max = _wide_disruption_half_life_au(total, age_gyr)     # B3; None without an age axis
    use_close = bool(close) and (not wide or rng.random() < float(close.get("weight") or 0.0))
    if use_close:
        p_lo = float(close.get("p_min_days") or 1.8)
        p_hi = float(close.get("p_max_days") or 62.6)
        period = 10.0 ** rng.uniform(math.log10(p_lo), math.log10(p_hi))
        sma = _kepler_sma_au(total, period)
    else:
        centre = _interp_log10_mass(wide.get("center_au_mass_grid") or [],
                                    wide.get("center_au") or [], mass_solar)
        sigma = float(wide.get("log10_sigma_au") or 0.0)
        log10_centre = math.log10(centre)
        p_cut = wide.get("truncate_period_days_min")
        tail = wide.get("wide_powerlaw_tail")     # Q4 spec; None on a v2.10 dataset → inert
        sma = period = None
        for _ in range(_MULT_TRUNC_TRIES):
            sma = 10.0 ** rng.normalvariate(log10_centre, sigma)
            period = _kepler_period_days(total, sma)
            below_cut = bool(p_cut) and period <= float(p_cut)
            # Q3: smooth survival S(a) = 0.5^((a/a_half)^p) REPLACES B3's hard a_half cut —
            # ~half the pairs AT the half-life scale really survive, and the sources find no
            # cutoff, so the draw is thinned smoothly by separation rather than walled off.
            # Q4: beyond the splice, thin the log-normal's shallow tail to the continuity-
            # spliced two-break power law (fixes the recorded solar-host over-production).
            accept = (1.0 if below_cut else
                      _wide_survival(sma, a_max)
                      * _wide_tail_thinning(sma, _WIDE_TAIL_S_JOIN_AU, log10_centre, sigma, tail))
            if not below_cut and rng.random() <= accept:
                break
            if a_max is not None and sma > a_max:
                disrupted = True     # a redraw driven by the survival roll-off
        else:
            # F-2 disjointness is load-bearing: the close-pair rate is 0.087 BY
            # CONSTRUCTION only while this component stays truncated above the window.
            # Place at the boundary rather than emit an overlapping draw — and say so.
            if p_cut:
                period = float(p_cut)
                sma = _kepler_sma_au(total, period)
            else:                                 # no period floor → fall back to the median
                sma = min(centre, a_max) if a_max else centre
                period = _kepler_period_days(total, sma)
            truncation_fallback = True

    ecc = _draw_companion_ecc(rng, sm.get("ecc_dist") or {}, period, mass_solar)
    note = (f"Companion drawn from the stellar_multiplicity prior "
            f"({'close-pair' if use_close else 'wide log-normal'} component; "
            f"q = {q:.3f} against a {frac:.3f} multiplicity fraction). "
            "Eccentricity uses the circularization period as a STATISTICAL boundary, not a "
            "cut, and is never identically zero; above it the f(e) ∝ e^η form is source-pinned "
            "(Moe & Di Stefano 2017, v2.11.0 Q2) with η period+primary-mass-dependent.")
    if n_comp > 2:
        note += (f" Higher-order system ({n_comp} components) — the additional component is "
                 "counted but not placed; only the primary companion is modelled.")
    if truncation_fallback:
        note += (" Wide-component truncation floor hit — companion placed at the truncation "
                 "boundary to keep the mixture components disjoint.")
    if a_max is not None and not use_close:
        note += (f" Wide separations follow the (M_tot, age) survival roll-off "
                 f"S(a) = 0.5^((a/a_half)^{_WIDE_SURVIVAL_P}) with a_half = {a_max:,.0f} AU "
                 f"(1.212 × M_tot/t pc, Weinberg 1987 eq. 28) — v2.11.0 Q3, replacing the "
                 f"hard cut: ~half the pairs AT a_half survive and the sources report no "
                 f"cutoff, so the tail is thinned smoothly rather than walled off (p is a "
                 f"tunable convenience, not a pinned exponent).")
        if wide.get("wide_powerlaw_tail"):
            note += (" Beyond a continuity splice at "
                     f"{_WIDE_TAIL_S_JOIN_AU:,.0f} AU the log-normal tail is thinned to a "
                     "two-break power law (γ₁ −1.55 → γ₂ −2.07, Tian 2020; normalization set "
                     "by continuity, no invented join weight) — v2.11.0 Q4, correcting the "
                     "solar-host over-production; M-dwarf centres (steeper log-normal) are "
                     "left unthinned and stay safe.")
        elif mass_solar >= 0.7:
            note += (" Shape caveat for a solar-type host: this single log-normal runs "
                     "SHALLOWER than the measured −0.60 tail slope out to ~3000 AU, so wide "
                     "companions are over-produced in that range.")

    return {
        "is_multiple": True,
        "n_components": n_comp,
        "mass_ratio_q": _round(q, 4),
        "wide_disruption_half_life_au": _round(a_max, 1) if a_max is not None else None,
        "wide_redrawn_for_disruption": disrupted,
        "companion": {
            "mass_solar": _round(m2, 4),
            # 6 dp, not the usual 4: a close pair sits at ~0.02 AU, where 4 dp keeps only
            # three significant figures and breaks Kepler round-tripping against p_orb_days.
            "sma_au": _round(sma, 6),
            "ecc": _round(ecc, 4),
            "p_orb_days": _round(period, 4),
            "close_pair": use_close,
        },
        "note": note,
    }


# ── Phase R3-V2 · B2 (v2.10) · stellar age + the rotation-activity chain ────────
#
# Two blocks, one chain. `age_dist` (T8) supplies the host AGE the generator never drew —
# the input `stellar_activity` names and nothing produced, which is why the activity block
# sat dormant. The chain is:
#
#     age → P_rot → Ro = P_rot/τ(M) → log(L_X/L_bol) → [X-ray→EUV] → XUV
#
# P_rot has three branches, and which one applies is a fact about the system, not a choice:
#   • a TIDALLY LOCKED close pair (B1's companion, `close_pair: true`) → P_rot = P_orb. This
#     branch needs NO age — a locked pair is saturated for life — so activity is computable
#     for a close binary even when the age draw is unavailable.
#   • an FGK single (0.6–1.36 M☉) → Skumanich t^½ spin-down anchored on the Sun.
#   • an M single (0.08–0.6 M☉) → the bimodal fast/slow population, NOT interpolated across
#     the gap (`interpolate_across_gap: false` — the gap is real, not missing data).
#
# `age_dist` is a population-weighted SFH HISTOGRAM, not a Gaussian like `feh_dist`:
#   • MS-lifetime truncation is intended (`truncate_and_renormalize`) — reject any draw with
#     age > ms_end_gyr(mass) via the Phase-L3 `compute_stellar_evolution`. It effectively
#     never bites for M dwarfs (their MS lifetime is >> a Hubble time) and bites hardest for
#     F/A, which is exactly what the block's own mass_conditional_age table shows.
#   • the histogram carries a KNOWN ARTIFACT: the BGM zeroes the 7–8 Gyr bin and piles up
#     8–9 Gyr. Sampling it literally reproduces a hole the real SFH does not have (Alzate
#     2021 has a broad minimum there), so a 3-bin kernel is applied when the dataset ships
#     an `sfh_smoothing_note` — i.e. the dataset itself declares the smoothing intended.
#
# APP-SIDE NOTE — the population split is NOT separately sampled. The block recommends
# drawing population (thin/thick/halo) then age from THAT population's distribution, but
# supplies only the blended SFH; per-population age distributions are not in the dataset.
# The block sanctions the simplification for exactly this consumer ("For the stellar_activity
# chain ALONE a single blended distribution is adequate — thick/halo are old → unsaturated
# regardless"), so the blended histogram is used and the omission is named in the note.

_AGE_TRUNC_TRIES = 64           # MS-truncation rejection bound
_SFH_KERNEL = (0.25, 0.5, 0.25)  # 3-bin smoother for the BGM discrete-age-bin artifact
_L_SUN_ERG_S = 3.828e33         # IAU nominal solar luminosity, erg/s (for L_X in erg/s)

# convective_turnover.relation, hardcoded because the dataset ships it as a FORMULA STRING.
# A test asserts the dataset's string still matches this implementation, so a sister-side
# change to the relation fails loudly instead of being silently ignored.
_TAU_RELATION = "log10_tau_days = 2.33 - 1.50*(M/Msun) + 0.31*(M/Msun)**2"
_TAU_C0, _TAU_C1, _TAU_C2 = 2.33, -1.50, 0.31


def _smoothed_sfh(age_dist):
    """SFH bins as [(lo, hi, weight)], with the 3-bin kernel applied when the dataset
    ships an ``sfh_smoothing_note`` (its own declaration that the discrete-age-bin
    artifact must not be sampled literally). Returns [] when unusable."""
    bins = [b for b in (age_dist.get("sfh_histogram") or [])
            if _is_number(b.get("lo")) and _is_number(b.get("hi"))
            and _is_number(b.get("fraction"))]
    if not bins:
        return []
    fracs = [float(b["fraction"]) for b in bins]
    if str(age_dist.get("sfh_smoothing_note") or "").strip():
        k0, k1, k2 = _SFH_KERNEL
        sm = []
        for i, f in enumerate(fracs):
            lo = fracs[i - 1] if i > 0 else f
            hi = fracs[i + 1] if i < len(fracs) - 1 else f
            sm.append(k0 * lo + k1 * f + k2 * hi)
        fracs = sm
    return [(float(b["lo"]), float(b["hi"]), w)
            for b, w in zip(bins, fracs) if w > 0]


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _ms_end_gyr(mass_solar):
    """``ms_end_gyr`` for the MS-lifetime truncation, or None when the Phase-L3
    calculator declines the mass (outside 0.1–20 M☉ — it refuses to extrapolate)."""
    ev = compute_stellar_evolution(mass_solar)
    if "error" in ev:
        return None
    return ev.get("ms_end_gyr")


# Q5 (v2.11.0) — per-population star-formation histories. Draw the Galactic population
# (thin/thick/halo) by its local mix weight, THEN the age from that population's own SFH,
# instead of one blended histogram. thin = the smoothed blended histogram restricted to
# ≤ its upper age (the blended SFH IS ~88% thin, so this reuses it); thick/halo = truncated
# Gaussians. σ is stated only in the dataset's `shape` PROSE (peak_gyr/age_range_gyr are
# numeric), so it is hardcoded here like _TAU_RELATION and drift-guarded by a test. The
# queued BGM per-population pull would replace only the thick/halo shapes. Gated on the
# `populations` sub-block, so a v2.10 dataset (no split) uses the blended path byte-identically.
_POP_ORDER = ("thin", "thick", "halo")   # deterministic population-draw order
_POP_GAUSS_SIGMA = {"thick": 1.3, "halo": 0.7}   # Gyr — from the block's `shape` strings


def _draw_truncated_gaussian(rng, peak, sigma, lo, hi):
    """A Gaussian(peak, σ) rejected to [lo, hi]; clamps to the peak (in range) after the
    resampling bound so it always returns a value in range."""
    if sigma <= 0:
        return min(max(peak, lo), hi)
    for _ in range(_AGE_TRUNC_TRIES):
        a = rng.gauss(peak, sigma)
        if lo <= a <= hi:
            return a
    return min(max(peak, lo), hi)


def _draw_thin_age(rng, age_dist, hi_cut):
    """Thin-disk age: the smoothed blended SFH restricted to bins at or below ``hi_cut`` Gyr
    (the 3-bin kernel in _smoothed_sfh already flattens the BGM thick-disk pile-up), sampled
    the same way as the blended path. None when no bin survives the cut."""
    bins = [(lo, hi, w) for lo, hi, w in _smoothed_sfh(age_dist) if hi <= hi_cut + 1e-9]
    if not bins:
        return None
    total = sum(w for _, _, w in bins)
    u = rng.random() * total
    acc = 0.0
    lo, hi = bins[-1][0], bins[-1][1]
    for b_lo, b_hi, w in bins:
        acc += w
        if u <= acc:
            lo, hi = b_lo, b_hi
            break
    return rng.uniform(lo, hi)


def _draw_age_by_population(rng, age_dist, pops, mass_solar):
    """Q5 — population (thin/thick/halo) by local mix weight, then age from that population's
    SFH, MS-lifetime-truncated exactly like the blended path. Returns None (so the caller
    falls back to the blended path) when the sub-block carries no usable population weight."""
    weights = [(p, float((pops.get(p) or {}).get("weight") or 0.0))
               for p in _POP_ORDER if isinstance(pops.get(p), dict)]
    weights = [(p, w) for p, w in weights if w > 0]
    if not weights:
        return None
    pop = _weighted_choice(rng, weights)
    spec = pops[pop]
    rng_pair = spec.get("age_range_gyr") or []
    lo, hi = ((float(rng_pair[0]), float(rng_pair[1])) if len(rng_pair) == 2
              else (0.0, 13.8))
    ms_end = _ms_end_gyr(mass_solar)
    age = None
    for _ in range(_AGE_TRUNC_TRIES):
        if pop == "thin":
            age = _draw_thin_age(rng, age_dist, hi)
            if age is None:                       # no bins → fall back to the blended path
                return None
        else:
            peak = float(spec.get("peak_gyr") or spec.get("mean_age_gyr") or (lo + hi) / 2)
            age = _draw_truncated_gaussian(rng, peak, _POP_GAUSS_SIGMA.get(pop, 1.0), lo, hi)
        if ms_end is None or age <= ms_end:
            return age
    return min(age, ms_end) if ms_end else age


def _draw_age(rng, priors, mass_solar):
    """Host age (Gyr) from the ``age_dist`` block, MS-lifetime-truncated.

    v2.11.0 (Q5): when the block carries a ``populations`` sub-block, draw population →
    age from that population's SFH; otherwise (v2.10 / no split) use the blended histogram.
    Returns ``None`` — consuming **no** rng — when the dataset omits the block.
    """
    ad = getattr(priors, "age_dist", None)
    if not ad:
        return None
    pops = ad.get("populations")
    if pops:
        age = _draw_age_by_population(rng, ad, pops, mass_solar)
        if age is not None:
            return age
        # malformed populations sub-block → fall through to the blended path below.
    bins = _smoothed_sfh(ad)
    if not bins:
        return None
    total = sum(w for _, _, w in bins)
    ms_end = _ms_end_gyr(mass_solar)
    age = None
    for _ in range(_AGE_TRUNC_TRIES):
        u = rng.random() * total
        acc = 0.0
        lo, hi = bins[-1][0], bins[-1][1]
        for b_lo, b_hi, w in bins:
            acc += w
            if u <= acc:
                lo, hi = b_lo, b_hi
                break
        age = rng.uniform(lo, hi)
        if ms_end is None or age <= ms_end:
            return age
    # Every draw exceeded the MS lifetime (a hot, short-lived star): clamp rather than
    # emit a star older than its own main sequence — the block's structural acceptance.
    return min(age, ms_end) if ms_end else age


def _tau_days(mass_solar):
    """Convective turnover time τ (days) — the Wright 2018 relation the block pins."""
    return 10.0 ** (_TAU_C0 + _TAU_C1 * mass_solar + _TAU_C2 * mass_solar ** 2)


def _in_range(value, pair):
    """True when ``value`` sits inside a [lo, hi] pair stated in EITHER direction (the
    block states log_lx_lbol_valid_range DESCENDING, and that is correct, not a typo)."""
    if not pair or len(pair) != 2 or value is None:
        return None
    lo, hi = min(pair), max(pair)
    return lo <= value <= hi


def _draw_p_rot(rng, sa, mass_solar, age_gyr, companion):
    """P_rot (days) + the branch that produced it. Returns (p_rot, branch) — p_rot is
    None when no branch applies (e.g. a single star with no age drawn)."""
    tl = sa.get("tidal_locking") or {}
    if (companion and companion.get("close_pair") and tl.get("locked_when_close_pair")
            and tl.get("p_rot_equals_p_orb") and companion.get("p_orb_days")):
        # A locked pair is saturated for life — this branch needs no age at all.
        return float(companion["p_orb_days"]), "tidally_locked"

    fgk = sa.get("rotation_age_fgk") or {}
    lo_hi = fgk.get("applicable_mass_msun") or []
    if (age_gyr is not None and len(lo_hi) == 2 and lo_hi[0] <= mass_solar <= lo_hi[1]
            and fgk.get("relation") == "skumanich"):
        p_sun = float(fgk.get("p_sun_days") or 25.4)
        age_sun = float(fgk.get("age_sun_gyr") or 4.57)
        expo = float(fgk.get("exponent") or 0.5)
        return p_sun * (age_gyr / age_sun) ** expo, "skumanich_fgk"

    singles = sa.get("rotation_age_singles") or {}
    lo_hi = singles.get("applicable_mass_msun") or []
    if age_gyr is not None and len(lo_hi) == 2 and lo_hi[0] <= mass_solar <= lo_hi[1]:
        fast, slow = singles.get("fast") or {}, singles.get("slow") or {}
        # Bimodal, and deliberately NOT interpolated across the gap: the gap between the
        # fast and slow sequences is a real feature of the M-dwarf population.
        band = fast if age_gyr <= float(fast.get("age_gyr_max") or 0.0) else slow
        rng_pair = band.get("p_rot_days") or []
        if len(rng_pair) == 2:
            return rng.uniform(float(rng_pair[0]), float(rng_pair[1])), (
                "m_dwarf_fast" if band is fast else "m_dwarf_slow")
    return None, None


def _draw_activity(rng, priors, mass_solar, luminosity, age_gyr, companion):
    """The rotation-activity chain → X-ray + XUV environment, or None when the block is
    absent / no P_rot branch applies. Consumes rng only on the M-dwarf single branch."""
    sa = getattr(priors, "stellar_activity", None)
    if not sa:
        return None
    ra = sa.get("rotation_activity") or {}
    ct = sa.get("convective_turnover") or {}
    p_rot, branch = _draw_p_rot(rng, sa, mass_solar, age_gyr, companion)
    if p_rot is None or p_rot <= 0:
        return None

    tau = _tau_days(mass_solar)
    rossby = p_rot / tau
    sat_log = float(ra.get("saturation_log_lx_lbol", -3.13))
    sat_ro = float(ra.get("saturation_rossby", 0.16))
    slope = float(ra.get("unsaturated_slope", -2.70))
    if rossby <= sat_ro:
        log_rx, regime = sat_log, "saturated"
    else:
        log_rx, regime = sat_log + slope * math.log10(rossby / sat_ro), "unsaturated"

    # Domain flags — the relation is fitted over a bounded range and this is an ANCHORED
    # RECONSTRUCTION, not Wright's own fitted line. Flag, never clamp.
    mass_ok = _in_range(mass_solar, ct.get("valid_mass_msun"))
    out_of_domain = [
        name for name, ok in (
            ("rossby", _in_range(rossby, ra.get("ro_valid_range"))),
            ("log_lx_lbol", _in_range(log_rx, ra.get("log_lx_lbol_valid_range"))),
            ("tau_mass", mass_ok),
        ) if ok is False
    ]

    out = {
        "age_gyr": _round(age_gyr, 3) if age_gyr is not None else None,
        "p_rot_days": _round(p_rot, 4),
        "p_rot_branch": branch,
        # P_rot is ALWAYS modelled — drawn or derived, never an observed period, in either
        # generation mode. This constant contract marker (1a prerequisite #2) guarantees a
        # consumer can never read a modelled p_rot_days as observed, even on a REAL anchor
        # whose age IS observed; a future observed-rotation source would set it otherwise.
        "p_rot_source": "modelled",
        "tau_days": _round(tau, 4),
        "rossby": _round(rossby, 4),
        "log_lx_lbol": _round(log_rx, 4),
        "regime": regime,
        "out_of_fitted_domain": out_of_domain,
        "band": "X-ray",
    }

    # X-ray → EUV. CONTESTED in the dataset (the spread between relations IS the
    # uncertainty and must not be averaged away), so the applied relation is named and the
    # alternative is carried alongside rather than blended.
    xuv = _xray_to_euv(sa, log_rx, luminosity)
    if xuv:
        out.update(xuv)
    cb = sa.get("circumbinary_xuv") or {}
    if companion and cb.get("component_count_scaling") is not None:
        # A ratio identity: doubled emitters cancel against a doubled HZ distance, so a
        # circumbinary XUV environment depends on L_X/L_bol ONLY — never on star count.
        out["circumbinary_component_scaling"] = float(cb["component_count_scaling"])
    return out


def _xray_to_euv(sa, log_rx, luminosity):
    """Apply the block's default X-ray→EUV relation to get an XUV environment.

    The relations are fitted on **absolute** L_X (erg/s), not the L_X/L_bol ratio, so the
    bolometric luminosity is required to enter and leave the conversion.
    """
    parent = sa.get("circumbinary_xuv") or {}
    cb = parent.get("xray_to_euv") or {}
    rels = cb.get("relations") or {}
    name = cb.get("default")
    rel = rels.get(name) or {}
    if not rel or not luminosity or luminosity <= 0:
        return None
    text = str(rel.get("relation") or "")
    m = re.search(r"\(?\s*(-?\d+(?:\.\d+)?)\s*(?:\+/-\s*[\d.]+)?\s*\)?\s*\+\s*"
                  r"\(?\s*(-?\d+(?:\.\d+)?)\s*(?:\+/-\s*[\d.]+)?\s*\)?\s*\*\s*log10 L_X", text)
    if not m:
        return None
    intercept, gradient = float(m.group(1)), float(m.group(2))
    log_lx = log_rx + math.log10(luminosity * _L_SUN_ERG_S)
    log_leuv = intercept + gradient * log_lx
    l_xuv = 10.0 ** log_lx + 10.0 ** log_leuv
    return {
        "log_l_x_erg_s": _round(log_lx, 4),
        "log_l_euv_erg_s": _round(log_leuv, 4),
        "log_l_xuv_erg_s": _round(math.log10(l_xuv), 4),
        "euv_fraction": _round(10.0 ** log_leuv / l_xuv, 4),
        "xray_to_euv_relation": name,
        "xray_to_euv_grade": parent.get("assumption_grade"),
        "xray_to_euv_alternatives": sorted(k for k in rels if k != name),
    }


# ── Phase R3-V2 · L2 (v2.1) · disk-mass lever + saturating giant occurrence ──────
#
# Three coupled refinements from the B6 channel exchange with Packet 3.5, all gated:
#   • disk-mass lever (their disk_mass_dist) — a per-SYSTEM log-normal MMSN multiplier
#     scales Σ_solid → M_iso, lifting the (previously sub-Mars) small-planet mass. Paired
#     with an upward _MASS_MODEL_SCATTER (merger growth) — the two levers together.
#   • growth-race giant occurrence — giant formation is a per-SYSTEM roll against a
#     SATURATING curve occ([Fe/H]) = C·x/(K+x), x=10^(2·[Fe/H]) (power-law below solar,
#     ceiling above — the FV05 curve, ~1.4%/10%/25% at −0.5/0/+0.5), NOT the old
#     per-orbit min(1, gf/gf₀) (which mis-saturated at solar). Eligibility stays the
#     pebble-isolation gate (now max(M_iso, M_iso,peb) ≥ M_crit so the disk lever gets
#     its second payoff), beyond the snow line and inside a ~20–30 AU outer cutoff
#     (wider giants are the disk-instability/scattered population, out of scope).
#   • peaked giant mass function — giant mass is log-normal anchored on the F4
#     gap-opening mass (modal ~Saturn, declining tail to the ~13 M_J boundary), instead
#     of log-uniform (which was top-heavy).
# Calibration order (per Packet 3.5, avoids double-tuning): mass scale first (disk +
# scatter), THEN normalize the occurrence curve. C/K/scatter/cutoff/sigma are knobs.
_OCC_C = 0.30           # saturating-occurrence ceiling (Packet 3.5 curve: occ(0/±0.5) = 10/25/1.4%)
_OCC_K = 2.0            # saturating-occurrence half-saturation. NOTE: the *realized* per-star giant
                       # occurrence is currently placement-capped (~1.6% at solar) because the
                       # generator's compact inner grid rarely populates the 1–5 AU giant zone —
                       # only ~2% of solar systems place a planet beyond the snow line. The curve
                       # is correct; lifting the realized level to 10% needs the giant-zone
                       # placement rework (channel-flagged to Packet 3.5, pending).
_GIANT_OUTER_CUTOFF_MULT = 10.0    # giant outer cutoff = mult × snow line (~27 AU for Sol)
_GIANT_MASS_LOGSIGMA = 0.85        # ln-spread of the peaked giant mass function
_GAP_ALPHA = 1e-3                  # viscosity for the F4 gap-opening-mass anchor


def _draw_disk_mass_mult(rng, priors):
    """Per-system disk-mass multiplier (MMSN units) from disk_mass_dist, or 1.0 when
    absent (→ the disk_mass_mmsn scalar fallback, unchanged). Log-normal + clamp."""
    mm = getattr(priors, "mass_model", None) or {}
    dmd = (mm.get("disk") or {}).get("disk_mass_dist")
    if not dmd:
        return 1.0
    mult = 10.0 ** rng.normalvariate(dmd["log10_mean"], dmd["log10_sigma"])
    lo, hi = dmd.get("min"), dmd.get("max")
    if lo is not None:
        mult = max(mult, lo)
    if hi is not None:
        mult = min(mult, hi)
    return mult


def _occ_eff(feh):
    """Saturating per-star giant-occurrence fraction occ([Fe/H]) = C·x/(K+x),
    x = 10^(2·[Fe/H]) — the FV05 curve (power-law below solar, ceiling above)."""
    x = 10.0 ** (2.0 * feh)
    return _OCC_C * x / (_OCC_K + x)


def _roll_system_forms_giants(rng, priors, feh):
    """Per-system growth-race roll: True if this system forms giants. When
    occurrence_by_metallicity + a host [Fe/H] are present, roll against _occ_eff;
    otherwise True (pure-physics gate — every eligible orbit is a giant, the
    mass_model-only behaviour). Consumes one rng draw only when the roll is live."""
    occ = getattr(priors, "occurrence_by_metallicity", None)
    if not occ or feh is None:
        return True
    return rng.random() < _occ_eff(feh)


def _draw_giant_mass(rng, mstar, a, temp_k, m_crit):
    """Peaked giant mass (Earth masses): log-normal anchored on the F4 gap-opening mass
    (modal ~Saturn, declining tail), clamped to [M_crit, ~13 M_J]. One rng draw. Shared
    by the grid giant switch (v2.1) and the decoupled cold-giant placement (v2.2)."""
    gap = compute_gap_opening_mass(temp_k=temp_k, mstar_msun=mstar, a_au=a, alpha=_GAP_ALPHA)
    mode = (gap.get("gap_opening_mass_mearth") if "error" not in gap else None) or 190.0
    mode = min(max(mode, m_crit * 1.5), _GIANT_MASS_CEILING_EARTH)
    mass = math.exp(rng.normalvariate(math.log(mode), _GIANT_MASS_LOGSIGMA))
    return min(max(mass, m_crit), _GIANT_MASS_CEILING_EARTH)


def _draw_cold_giant_sma(rng, sma_dist, snow):
    """Cold-giant semi-major axis (AU) from the broken-power-law sma_dist, over
    [inner, outer_au] with density in ln(a) ∝ a^slope_dn_dlna (pdf(a) ∝ a^(slope−1)).
    inner='snow_line' → the star's snow line (giants form beyond it)."""
    inner = sma_dist.get("inner")
    lo = snow if inner == "snow_line" else float(inner)
    hi = float(sma_dist["outer_au"])
    if hi <= lo:
        return lo
    s = float(sma_dist["slope_dn_dlna"])
    u = rng.random()
    if abs(s) < 1e-9:                                    # s=0 → log-uniform
        return math.exp(math.log(lo) + u * (math.log(hi) - math.log(lo)))
    return (lo ** s + u * (hi ** s - lo ** s)) ** (1.0 / s)   # inverse-CDF of a^(s−1)


def _place_cold_giants(rng, priors, star_name, derived, start_idx):
    """v2.2 (L2): the DECOUPLED cold-giant population — placed independent of the inner
    n_planet_dist grid (which is the detection-biased short-period small-planet count).
    Fires only when the per-system growth-race roll passed (derived['system_forms_giants'],
    = the saturating occurrence curve); draws the count from the conditional multiplicity,
    each giant's SMA from sma_dist (beyond the snow line, within outer_au), and mass from
    the peaked gap-anchored function. Only COLD giants (a ≥ snow_line) — hot Jupiters stay
    in the inner grid's transit-based count. Gated: returns [] without the block."""
    cgp = getattr(priors, "cold_giant_population", None)
    if not cgp or not derived.get("system_forms_giants"):
        return []
    snow = derived.get("snow_line")
    if not snow:
        return []
    mult_items = sorted((int(k), float(v)) for k, v in cgp["multiplicity"].items())
    n = _weighted_choice(rng, mult_items)              # conditional count given ≥1
    disk = (getattr(priors, "mass_model", None) or {}).get("disk", {})
    mstar = derived.get("mass_solar") or 1.0
    m_crit = compute_critical_core_mass()["critical_core_mass_mearth"]
    lum = derived["luminosity"]
    giants = []
    for j in range(n):
        a = _draw_cold_giant_sma(rng, cgp["sma_dist"], snow)
        dm = compute_disk_model(
            r_au=a, mstar_msun=mstar,
            sigma0=disk.get("sigma0_gcm2", 1700.0), sigma_slope=disk.get("sigma_slope", -1.5),
            temp0=disk.get("temp0_k", 280.0), temp_slope=disk.get("temp_slope", -0.5))
        temp_k = dm["temp_k"] if "error" not in dm else 280.0 * a ** -0.5
        mass = _draw_giant_mass(rng, mstar, a, temp_k, m_crit)
        ecc = rng.uniform(0.0, 0.1)
        ptype, radius = _classify_planet(mass, a, snow)
        t_eq = _equilibrium_temp(a, lum)
        in_hz, hz_class = _hz_membership(a, derived)
        giants.append({
            "name": f"{star_name} (cold giant {start_idx + j + 1})",
            "a_au": _round(a, 5), "mass_earth": _round(mass, 4),
            "radius_earth": _round(radius, 4), "ecc": _round(ecc, 4), "type": ptype,
            "t_eq_k": _round(t_eq, 2), "in_hz": in_hz, "hz_class": hz_class,
            "source": "synthetic", "atmosphere": None, "moons": [],
            "_a_raw": a, "_mass_raw": mass, "_ecc_raw": ecc, "_radius_raw": radius,
        })
    return giants


# v2.3 inner-giant zone split. 0.1 AU is the boundary the block's own zone keys encode
# ("hot_zone_below_0p1au" / "warm_zone_0p1au_to_snowline"); the sub-objects are selected
# by name below so a renamed zone key still resolves.
_INNER_GIANT_HOT_ZONE_AU = 0.1
# Q1 (v2.11.0) — a HOT giant's "loneliness" radius (~50 d ≈ 0.25 AU): hot Jupiters have no
# companions inside it, WASP-47 aside (Huang, Wu & Triaud 2016). WARM giants coexist with
# inner small planets at the normal peas-in-a-pod floor, so they get NO suppression.
_INNER_GIANT_HOT_LONELY_AU = 0.25
_SMALL_PLANET_TYPES = frozenset(("rocky", "super_earth", "ice"))
# Channel names implying an EXCITED (high-e) history. Only the CLASSIFICATION is fixed
# here — the mix fractions stay data (gotcha 4: they are tunable knobs, not constants).
_INNER_GIANT_EXCITED_MARKERS = ("scattering", "high_e")
_INNER_GIANT_E_SPLIT = 0.1        # e below this = circular/disk mode, above = excited


def _interp_giant_fraction(occ, feh):
    """occurrence_by_metallicity.giant_fraction at ``feh``, linearly interpolated on
    feh_grid with the ENDPOINTS HELD (no extrapolation past the fitted ±0.5 domain).

    This is the LITERAL FV05 close-in array (~3% at solar) used in its native domain.
    It is deliberately a DIFFERENT number from ``_occ_eff`` (the rescaled ~10%-solar
    saturating curve the cold block rolls against) — two disjoint SMA zones, two
    independent rolls, no double-count."""
    grid = occ.get("feh_grid") or []
    frac = occ.get("giant_fraction") or []
    if not grid or len(grid) != len(frac):
        return None
    if feh <= grid[0]:
        return float(frac[0])
    if feh >= grid[-1]:
        return float(frac[-1])
    for i in range(1, len(grid)):
        if feh <= grid[i]:
            lo_x, hi_x = float(grid[i - 1]), float(grid[i])
            lo_y, hi_y = float(frac[i - 1]), float(frac[i])
            if hi_x == lo_x:
                return lo_y
            t = (feh - lo_x) / (hi_x - lo_x)
            return lo_y + t * (hi_y - lo_y)
    return float(frac[-1])


def _draw_inner_giant_sma(rng, sma_dist, snow):
    """Inner-giant SMA (AU) from the v2.3 mixture: pick a component by weight, then draw
    (lognormal about center_au, or a power law with density in ln(a) ∝ a^slope). Clamped
    to [inner_edge_au, snow_line]. Two rng draws (component pick + value)."""
    edge = float(sma_dist["inner_edge_au"])
    comps = sma_dist["components"]
    pick = _weighted_choice(rng, [(i, float(c["weight"])) for i, c in enumerate(comps)])
    c = comps[pick]
    if c["dist"] == "lognormal_au":
        a = 10.0 ** rng.normalvariate(math.log10(float(c["center_au"])),
                                      float(c["log10_sigma"]))
    else:
        lo = float(c["inner_au"])
        outer = c.get("outer")
        hi = snow if outer == "snow_line" else float(outer)
        if hi <= lo:
            return max(min(lo, snow), edge)
        s = float(c["slope_dn_dlna"])
        u = rng.random()
        if abs(s) < 1e-9:
            a = math.exp(math.log(lo) + u * (math.log(hi) - math.log(lo)))
        else:
            a = (lo ** s + u * (hi ** s - lo ** s)) ** (1.0 / s)
    return max(min(a, snow), edge)


def _inner_giant_zone_mix(fcm, hot):
    """Select the hot/warm sub-object of formation_channel_mix by name (skipping the
    free-text note keys), returning {channel: fraction} or None."""
    want = "hot" if hot else "warm"
    for key, mix in fcm.items():
        if isinstance(mix, dict) and want in key.lower():
            return mix
    return None


def _draw_inner_giant_channel(rng, mix, ecc, hot):
    """Pick a formation_channel CONSISTENT with the drawn eccentricity (gotcha 3).

    WARM zone: eccentricity is the load-bearing observable, so it selects the group —
    channels are partitioned into excited (scattering / high-e tidal) and quiescent
    (in-situ circular / disk migration), the group is chosen by e, then one channel is
    drawn inside it by the block's own relative weights. e and the tag cannot disagree,
    and the fractions stay data-driven.

    HOT zone: no such split. Tidal circularization erases the eccentricity signature —
    *both* hot channels end up at e ≈ 0 — so e carries no channel information and the
    draw is over the full mix by weight. (Splitting here would be an artifact: the hot
    mix's 'migrated_disk_or_high_e' merely has 'high_e' in its NAME, and gating on that
    would hand every hot Jupiter to the 20% in-situ channel.)"""
    if hot:
        return _weighted_choice(rng, sorted(mix.items()))
    excited = {k: v for k, v in mix.items()
               if any(m in k.lower() for m in _INNER_GIANT_EXCITED_MARKERS)}
    quiescent = {k: v for k, v in mix.items() if k not in excited}
    group = excited if ecc >= _INNER_GIANT_E_SPLIT else quiescent
    if not group or sum(group.values()) <= 0:
        group = mix
    return _weighted_choice(rng, sorted(group.items()))


def _place_inner_giants(rng, priors, star_name, derived, start_idx):
    """v2.3: the DECOUPLED close-in giant population interior to the snow line — the
    mirror of ``_place_cold_giants``. Runs AFTER the cold block, sharing the host [Fe/H].

    Per-system occurrence is its OWN roll against the literal FV05 giant_fraction in its
    native close-in domain (NOT derived['system_forms_giants'], which is the cold block's
    rescaled curve). This deliberately BYPASSES the B1 giant_switch for a controlled,
    tagged sub-population — the gate itself is unchanged (gotcha 1). Each giant carries a
    ``formation_channel`` tag whose eccentricity agrees with it (gotcha 3). Gated: returns
    [] without the block, without occurrence_by_metallicity, or without a host [Fe/H]."""
    igp = getattr(priors, "inner_giant_population", None)
    occ = getattr(priors, "occurrence_by_metallicity", None)
    if not igp or not occ:
        return []
    feh = derived.get("feh")
    snow = derived.get("snow_line")
    if feh is None or not snow:
        return []
    p_occ = _interp_giant_fraction(occ, feh)
    if p_occ is None or rng.random() >= p_occ:
        return []

    lo_mj, hi_mj = igp["mass_range_mjup"]
    m_lo, m_hi = lo_mj * _M_JUPITER_EARTH, hi_mj * _M_JUPITER_EARTH
    ed = igp["eccentricity_dist"]
    fcm = igp["formation_channel_mix"]
    disk = (getattr(priors, "mass_model", None) or {}).get("disk", {})
    mstar = derived.get("mass_solar") or 1.0
    m_crit = compute_critical_core_mass()["critical_core_mass_mearth"]
    lum = derived["luminosity"]

    a = _draw_inner_giant_sma(rng, igp["sma_dist"], snow)
    hot = a < _INNER_GIANT_HOT_ZONE_AU

    # Eccentricity first, then a channel that agrees with it (gotcha 3).
    if hot:
        sigma = float(ed["hot"]["sigma"])
        ecc = min(sigma * math.sqrt(-2.0 * math.log(1.0 - rng.random())), 0.99)
    else:
        ecc = min(rng.betavariate(float(ed["warm"]["alpha"]),
                                  float(ed["warm"]["beta"])), 0.99)
    mix = _inner_giant_zone_mix(fcm, hot)
    channel = _draw_inner_giant_channel(rng, mix, ecc, hot) if mix else None

    # Mass: log-uniform across the block's [0.3, 13] M_J range.
    #
    # NOT the cold block's gap-anchored _draw_giant_mass — that anchors on the F4
    # gap-opening mass, which is genuinely tiny this close in (the Type-II knee scales
    # with a and disk temperature), so every draw fell below the 0.3 M_J floor and
    # clamped there, collapsing the mass function to a delta at the floor. The block
    # supplies a RANGE and no shape, so the shape is an app-side choice: log-uniform is
    # the v1 mass_by_zone convention and is deliberately flat rather than inventing a
    # centre the dataset does not pin. Flagged to WB as a candidate for a real
    # inner-giant mass function.
    mass = math.exp(rng.uniform(math.log(m_lo), math.log(m_hi)))

    ptype, radius = _classify_planet(mass, a, snow)
    t_eq = _equilibrium_temp(a, lum)
    in_hz, hz_class = _hz_membership(a, derived)
    label = "hot giant" if hot else "warm giant"
    return [{
        "name": f"{star_name} ({label} {start_idx + 1})",
        "a_au": _round(a, 5), "mass_earth": _round(mass, 4),
        "radius_earth": _round(radius, 4), "ecc": _round(ecc, 4), "type": ptype,
        "t_eq_k": _round(t_eq, 2), "in_hz": in_hz, "hz_class": hz_class,
        "source": "synthetic", "atmosphere": None, "moons": [],
        "formation_channel": channel, "giant_zone": "hot" if hot else "warm",
        "_a_raw": a, "_mass_raw": mass, "_ecc_raw": ecc, "_radius_raw": radius,
    }]


def _apply_hot_giant_loneliness(planets):
    """Q1 (v2.11.0) — enforce hot-Jupiter loneliness. When a synthetic HOT inner giant is
    present, drop the *synthetic* small planets interior to ``_INNER_GIANT_HOT_LONELY_AU``:
    hot Jupiters have no detectable companions inward of ~50 d down to ~1–2 R⊕, with WASP-47
    the single exception (Huang, Wu & Triaud 2016, ApJ 825, 98). WARM giants are untouched —
    they coexist with inner small planets at the normal peas-in-a-pod floor (the giant is a
    large pod member), which is the empirical answer to the 1b spacing-floor question.

    Never removes an OBSERVED planet (real data — this is also where a real WASP-47's
    companions correctly survive), the giant itself, or an in-HZ planet (so a synthetic
    system built under ``require_habitable`` keeps its habitable world). No rng — a pure
    filter, so the draw stream is unchanged. Returns ``(kept, n_suppressed)``."""
    if not any(p.get("giant_zone") == "hot" for p in planets):
        return planets, 0
    kept, removed = [], 0
    for p in planets:
        interior = (p.get("a_au") or 1e9) < _INNER_GIANT_HOT_LONELY_AU
        suppressible = (p.get("source") == "synthetic"
                        and p.get("giant_zone") is None
                        and p.get("type") in _SMALL_PLANET_TYPES
                        and not p.get("in_hz"))
        if interior and suppressible:
            removed += 1
            continue
        kept.append(p)
    return kept, removed


def _mass_model_draw(rng, priors, a, derived):
    """v2 F1 mass draw at SMA ``a`` (Earth masses). Consumes exactly one rng draw per
    orbit (giant or solid), so the downstream draw order is fixed for a given dataset.

    v2.1 (L2): Σ_solid is scaled by the per-system disk-mass multiplier + 10^[Fe/H];
    giant eligibility is max(M_iso, M_iso,peb) ≥ M_crit beyond the snow line within a
    ~20–30 AU cutoff; whether an eligible orbit is a giant is the per-system growth-race
    roll (derived['system_forms_giants']); giant mass is peaked on the F4 gap mass."""
    mm = priors.mass_model
    disk = mm["disk"]
    mstar = derived.get("mass_solar") or 1.0
    feh = derived.get("feh")
    disk_mult = derived.get("disk_mass_mult", 1.0)

    dm = compute_disk_model(
        r_au=a, mstar_msun=mstar,
        sigma0=disk["sigma0_gcm2"], sigma_slope=disk["sigma_slope"],
        temp0=disk["temp0_k"], temp_slope=disk["temp_slope"],
        disk_mass_mmsn=disk["disk_mass_mmsn"] * disk_mult,   # L2 disk-mass lever
        feh=feh)                                             # L2 Σ_solid ∝ 10^[Fe/H]
    iso = (compute_isolation_mass(
        sigma_p_gcm2=dm["sigma_solid_gcm2"], a_au=a, mstar_msun=mstar,
        feeding_zone_b=mm["feeding_zone_hill"]) if "error" not in dm else {"error": 1})
    if "error" in dm or "error" in iso:
        # Defensive fallback to the v1 band for this orbit (still one rng draw).
        lo, hi = priors.mass_by_zone[_zone_for(a, derived)]
        return math.exp(rng.uniform(math.log(lo), math.log(hi)))
    m_iso = iso["isolation_mass_mearth"]

    # Eligibility (WHERE a giant can form): the pebble/planetesimal core must reach the
    # critical core mass — max(M_iso, M_iso,peb) ≥ M_crit — beyond the snow line and
    # inside the ~20–30 AU core-accretion outer cutoff. max() lets the disk-mass lever
    # give its second payoff (Σ-boosted M_iso can overtake M_iso,peb at high disk×[Fe/H]).
    peb = compute_pebble_isolation_mass(temp_k=dm["temp_k"], mstar_msun=mstar, a_au=a)
    m_peb = peb.get("pebble_isolation_mass_mearth") if "error" not in peb else 0.0
    m_crit = compute_critical_core_mass()["critical_core_mass_mearth"]
    snow = derived.get("snow_line")
    outer = _GIANT_OUTER_CUTOFF_MULT * snow if snow else None
    eligible = (snow is not None and a >= snow and outer is not None and a <= outer
                and max(m_iso, m_peb) >= m_crit)

    # Formation (WHETHER, per-system growth race): an eligible orbit is a giant iff the
    # system rolled giant-forming. When a cold_giant_population block is present (v2.2),
    # cold giants are placed by the DECOUPLED population instead (from the debiased RV
    # occurrence, not grown from the detection-biased inner grid) — so the grid makes no
    # giants here, avoiding double-counting.
    is_giant = (eligible and derived.get("system_forms_giants", True)
                and not getattr(priors, "cold_giant_population", None))

    if is_giant:
        return _draw_giant_mass(rng, mstar, a, dm["temp_k"], m_crit)

    slo, shi = _MASS_MODEL_SCATTER
    mass = m_iso * math.exp(rng.uniform(math.log(slo), math.log(shi)))
    # A non-giant (no gas runaway) body can't be a gas giant by mass alone — cap it
    # just below the gas threshold so a heavy solid is an ice giant, never a gas giant
    # inside the snow line. (The higher merger-growth scatter can otherwise push a
    # solid past 50 M⊕ → _classify_planet would type it 'gas'.)
    mass = min(mass, _GAS_MIN_EARTH * 0.99)
    # Super-Earth floor: below it, metal-poor hosts sharply lose super-Earths →
    # cap solid bodies just under the super-Earth threshold (gotcha #4).
    occ = getattr(priors, "occurrence_by_metallicity", None)
    floor = (occ.get("superearth_floor_feh")
             if (occ is not None and feh is not None) else None)
    if floor is not None and feh < floor and mass >= _SUPER_EARTH_MIN_EARTH:
        mass = _SUPER_EARTH_MIN_EARTH * 0.95
    return mass


def _make_synth_planet(rng, priors, name, a, derived):
    """Build one synthetic planet at SMA ``a``: draw mass (by zone) then ecc, in
    that fixed order, then classify / T_eq / HZ / atmosphere. Carries internal
    _-prefixed working fields for downstream moon placement. Shared by the
    synthetic-mode pass and the real-anchor extension pass."""
    lum = derived["luminosity"]
    zone = _zone_for(a, derived)
    if getattr(priors, "mass_model", None):          # Phase R3-V2 F1 (gated)
        mass = _mass_model_draw(rng, priors, a, derived)
    else:
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


# ── Phase R3-V2 · F3 intra-system correlation (peas-in-a-pod) ────────────────
#
# When a strict dataset carries `intra_system_correlation`, adjacent planets are
# drawn CONDITIONAL on each other (a joint distribution), not independently — the
# fundamental v1→v2 shift. Two coupled correlations (gated → v1/permissive stay
# byte-identical): (1) SPACING — adjacent period ratios from the triangular
# period_ratio_dist {min(hard floor), mode, tail}, converted to an SMA ratio via
# Kepler III (a_ratio = P_ratio^(2/3)); this generalizes the flat spacing_ratio
# band. (2) SIZE — a peas-in-a-pod mass chain: the innermost small planet seeds
# the scale, and each subsequent SMALL body's mass follows prev × size_ratio, with
# size_ratio log-normal (median 1, sigma from size_ratio_dist) biased so ~65% of
# adjacent pairs have the outer larger (the `ordering` direction). True giants
# (physics-placed by F1) are exempt and reset the chain — peas-in-a-pod is a
# small-planet phenomenon. The chain is capped below the gas-giant threshold so it
# never fabricates a gas giant interior to the snow line (preserving the F1 gate).
# HOW the conditional draw is realised is the engine's choice; log-space sigma and
# the chain form are documented engine decisions. Applies to synthetic-mode
# architecture only (real-anchor infill keeps independent draws — correlating
# speculative infill to real observed planets is not well-defined).
_ORDERING_BIAS_Z = 0.3853     # Φ⁻¹(0.65): 65% of adjacent pairs → outer larger (Weiss 2018).
                              # B6: lands ~0.69 empirically (the ~0.04 excess is chain/reclassify,
                              # not the z-bias), which Weiss's ~60–65% spread accepts — so the
                              # principled value is kept rather than de-tuned to chase 0.65.


def _spacing_ratio_draw(rng, priors):
    """Adjacent-SMA ratio for the next planet. With intra_system_correlation, draw a
    period ratio from the triangular period_ratio_dist (min = hard mutual-Hill floor)
    and convert via Kepler III; else the flat v1 spacing_ratio band. One rng draw
    either way, so the draw order is unchanged."""
    corr = getattr(priors, "intra_system_correlation", None)
    if corr:
        prd = corr["period_ratio_dist"]
        period_ratio = rng.triangular(prd["min"], prd["tail"], prd["mode"])
        return period_ratio ** (2.0 / 3.0)
    lo, hi = priors.spacing_ratio
    return rng.uniform(lo, hi)


def _reset_planet_mass(p, mass, derived):
    """Re-derive type/radius/atmosphere (+ the working fields) after the size chain
    changes a planet's mass. T_eq / HZ membership don't depend on mass, so stay."""
    a = p["_a_raw"]
    ptype, radius = _classify_planet(mass, a, derived["snow_line"])
    atmosphere = (_atmosphere_note(mass, radius, p["t_eq_k"])
                  if ptype in ("rocky", "super_earth") else None)
    p["mass_earth"] = _round(mass, 4)
    p["radius_earth"] = _round(radius, 4)
    p["type"] = ptype
    p["atmosphere"] = atmosphere
    p["_mass_raw"] = mass
    p["_radius_raw"] = radius


def _apply_size_correlation(rng, corr, p, prev_small_mass, derived):
    """Peas-in-a-pod: pull a small planet's mass toward its inner small neighbour.
    Returns the new chain anchor (this body's small mass, or None to reset at a giant).
    Always consumes one rng draw when active, so the per-planet draw count is fixed."""
    srd = corr["size_ratio_dist"]
    # log-normal size ratio, median 1, biased so ~65% of pairs have the outer larger.
    ratio = math.exp(rng.normalvariate(_ORDERING_BIAS_Z * srd["sigma"], srd["sigma"]))
    if p["type"] in _GIANT_TYPES:
        return None                              # giant → physics mass stands, chain resets
    if prev_small_mass is None:
        return p["_mass_raw"]                     # seed small body — base mass anchors the chain
    new_mass = prev_small_mass * ratio
    if new_mass >= _GAS_MIN_EARTH:               # keep the chain sub-giant (F1 gate intact)
        new_mass = _GAS_MIN_EARTH * 0.99
    _reset_planet_mass(p, new_mass, derived)
    return new_mass


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
    corr = getattr(priors, "intra_system_correlation", None)   # R3-V2 F3 (gated)

    a = rng.uniform(0.03, 0.12) * root_l    # innermost SMA (scales with sqrt L)
    planets = []
    prev_small_mass = None
    for i in range(n):
        if i > 0:
            a *= _spacing_ratio_draw(rng, priors)
        p = _make_synth_planet(rng, priors, f"{star_name} {chr(ord('b') + i)}", a, derived)
        if corr:
            prev_small_mass = _apply_size_correlation(rng, corr, p, prev_small_mass, derived)
        planets.append(p)
    # v2.2 (L2): decoupled cold-giant population, added after the inner grid.
    planets += _place_cold_giants(rng, priors, star_name, derived, 0)
    # v2.3: decoupled inner-giant population, after the cold block (shares host [Fe/H]).
    planets += _place_inner_giants(rng, priors, star_name, derived, 0)
    # Q1 (v2.11.0): a hot giant suppresses interior synthetic small planets (a pure filter,
    # no rng); count is surfaced to the caller via `derived` for the provenance note.
    planets, derived["_hot_lonely_suppressed"] = _apply_hot_giant_loneliness(planets)
    # Emit in ORBITAL order, as the real-anchor path already does (_generate_real_anchor).
    # The two decoupled populations are appended after the grid, and an inner giant lands
    # interior to it — so without this the list is not monotonic in a_au. Sorting here does
    # NOT re-letter the grid names (they record draw order, not rank).
    planets.sort(key=lambda p: (p["a_au"] is None, p["a_au"]))
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


# R3-V2 B5: the sampling blocks whose presence changes generation (mass/count/spacing).
# feh_dist is a support axis (no standalone effect) so it isn't listed as "in effect".
_V2_SAMPLING_BLOCKS = ("mass_model", "occurrence_by_metallicity", "intra_system_correlation",
                       "cold_giant_population", "inner_giant_population")

# The STELLAR blocks (B1/B2) are drawn in synthetic mode only — a real anchor takes its
# multiplicity from GCNS and draws no age or activity.
_V2_SYNTHETIC_ONLY_BLOCKS = ("stellar_multiplicity", "age_dist", "stellar_activity")


def _v2_blocks_note(priors, star):
    """Provenance note naming the active v2 sampling blocks (+ host [Fe/H] when the
    metallicity path drove it), or None when no v2 block is active. Surfaces the v2
    physics in the CLI / query.py notes and the GUI."""
    active = [b for b in _V2_SAMPLING_BLOCKS if getattr(priors, b, None)]
    # stellar_multiplicity + age_dist are sampled in SYNTHETIC mode only — under a real
    # anchor the multiplicity is GCNS-derived and the age is OBSERVED (HWC/Exocat, not
    # age_dist), so claiming either is "in effect" there would be false.
    if star.get("source") == "synthetic":
        active += [b for b in _V2_SYNTHETIC_ONLY_BLOCKS if getattr(priors, b, None)]
    # 1a — stellar_activity is the exception: an anchor's activity IS reconstructed from its
    # observed age when the block is present and a P_rot branch applied. Claim it only when
    # it actually produced an environment (star["activity"] set), never merely present.
    elif getattr(priors, "stellar_activity", None) and star.get("activity"):
        active.append("stellar_activity")
    if not active:
        return None
    note = "v2 physics in effect: " + ", ".join(active) + "."
    if getattr(priors, "occurrence_by_metallicity", None) and star.get("feh") is not None:
        note += (f" Host [Fe/H] = {star['feh']} "
                 f"({star.get('feh_source') or 'unknown'}), metallicity-conditioned.")
    return note


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
            rng, _metallicity_count_items(priors, derived))
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
    _n_lonely = derived.get("_hot_lonely_suppressed") or 0
    if _n_lonely:
        notes.append(
            f"Hot-giant loneliness (v2.11.0 Q1, Huang+2016): {_n_lonely} synthetic small "
            "planet(s) interior to 0.25 AU were suppressed around the hot giant — hot Jupiters "
            "have no close companions (WASP-47 aside). Warm giants coexist at the normal floor.")
    _v2note = _v2_blocks_note(priors, star)
    if _v2note:
        notes.append(_v2note)
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
    # R3-V2 F2 host [Fe/H]. The Hypatia-preferred resolution (an extra network call)
    # runs ONLY when a metallicity-conditioning dataset is active; otherwise the star's
    # [Fe/H] is the cheap informational SIMBAD read (no added call for permissive/v1).
    if getattr(priors, "occurrence_by_metallicity", None):
        anchor_feh, anchor_feh_source = _resolve_anchor_feh(simbad)
    else:
        _sfeh = _f(simbad.get("fe_h"))
        anchor_feh, anchor_feh_source = (_sfeh, "simbad" if _sfeh is not None else None)

    # 1a — real-anchor host age from an observed catalogue (HWC S_AGE → Mission Exocat
    # st_age, both Gyr), which seeds the activity chain reconstructed post-infill below.
    # None when neither catalogue lists an age (the common case); no network, no rng.
    anchor_age, anchor_age_source = _resolve_anchor_age(simbad)

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
        "feh": _round(anchor_feh, 3),
        "feh_source": anchor_feh_source,
        # B2 keys are one shape across both modes. On a real anchor the AGE is *read* from
        # an observed catalogue (HWC S_AGE → Mission Exocat st_age, both Gyr — 1a), never
        # drawn from the synthetic SFH; ACTIVITY is then reconstructed from that observed age
        # AFTER planet/moon infill (see the _draw_activity call near the return, placed there
        # so the synthetic-body rng stream is byte-identical to before). P_rot stays modelled
        # and is tagged p_rot_source="modelled" so it can never be read as observed.
        "age_gyr": _round(anchor_age, 3) if anchor_age is not None else None,
        "age_source": anchor_age_source,
        "activity": None,   # reconstructed post-infill; see the _draw_activity call below
        "source": "observed",
        "grounding": "observed",
        "multiplicity": {"is_multiple": is_multiple, "n_components": n_comp, "note": mult_note},
    }
    derived = {
        "luminosity": luminosity,
        "mass_solar": mass_solar,          # for the v2 F1 mass_model draw (R3-V2)
        "hz_cons_inner": hzmap["rg"], "hz_cons_outer": hzmap["mg"],
        "hz_opt_inner": hzmap["rv"], "hz_opt_outer": hzmap["em"],
        "snow_line": snow_line,
        "feh": anchor_feh,                 # R3-V2 F2: real-anchor [Fe/H] from SIMBAD
        "disk_mass_mult": _draw_disk_mass_mult(rng, priors),          # L2
        "system_forms_giants": _roll_system_forms_giants(rng, priors, anchor_feh),  # L2
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
            rng, _metallicity_count_items(priors, derived))
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

    # v2.2 (L2): decoupled cold-giant population around the real star (synthetic).
    synth += _place_cold_giants(rng, priors, star_name, derived, len(synth))
    synth += _place_inner_giants(rng, priors, star_name, derived, len(synth))
    # Q1 (v2.11.0): a synthetic hot giant suppresses interior synthetic small planets
    # (observed planets — incl. a real WASP-47's companions — are never touched).
    synth, _n_lonely = _apply_hot_giant_loneliness(synth)
    if _n_lonely:
        notes.append(
            f"Hot-giant loneliness (v2.11.0 Q1, Huang+2016): {_n_lonely} synthetic small "
            "planet(s) interior to 0.25 AU were suppressed around the hot giant — hot Jupiters "
            "have no close companions (WASP-47 aside). Warm giants coexist at the normal floor.")

    _attach_moons(rng, priors, star, synth)

    # 1a — reconstruct the rotation-activity environment from the OBSERVED age, here at the
    # end so every synthetic draw above is untouched: without a stellar_activity block (v1 /
    # permissive) _draw_activity is None and consumes no rng, and with one it draws last, so
    # the planet/moon stream is byte-identical to before regardless of policy. The anchor
    # builds no companion dict, so only the single-star P_rot branches (Skumanich FGK /
    # bimodal M-dwarf) can apply — the tidally-locked branch needs a companion P_orb.
    star["activity"] = _draw_activity(rng, priors, mass_solar, luminosity, anchor_age, None)

    planets = observed + _strip_private(synth)
    planets.sort(key=lambda p: (p["a_au"] is None, p["a_au"]))

    notes.append("Observed bodies from NASA pscomppars / HWC; synthetic extensions use "
                 f"{_priors_note_fragment(priors)}. Observed planets carry no fabricated moons.")
    _v2note = _v2_blocks_note(priors, star)
    if _v2note:
        notes.append(_v2note)
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
