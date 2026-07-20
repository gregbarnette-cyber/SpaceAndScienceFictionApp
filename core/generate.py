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
        "source": "synthetic",
        "grounding": priors.grounding,
        "multiplicity": None,
    }
    derived = {
        "teff": teff, "mass_solar": mass_solar, "luminosity": luminosity,
        "hz_cons_inner": hzmap["rg"], "hz_cons_outer": hzmap["mg"],
        "hz_opt_inner": hzmap["rv"], "hz_opt_outer": hzmap["em"],
        "snow_line": snow_line, "feh": feh,
        "disk_mass_mult": disk_mass_mult,               # L2
        "system_forms_giants": system_forms_giants,     # L2
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
                       "cold_giant_population")


def _v2_blocks_note(priors, star):
    """Provenance note naming the active v2 sampling blocks (+ host [Fe/H] when the
    metallicity path drove it), or None when no v2 block is active. Surfaces the v2
    physics in the CLI / query.py notes and the GUI."""
    active = [b for b in _V2_SAMPLING_BLOCKS if getattr(priors, b, None)]
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

    _attach_moons(rng, priors, star, synth)

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
