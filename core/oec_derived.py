# core/oec_derived.py — the OEC System View's derived-value layer.
#
# Pure functions, no Qt, no I/O, no DB, no network (OEC_SYSTEM_VIEW_PLAN §D).
# Every entry returns a value **or None with a stated reason** — never a raise,
# never a silent zero. Nothing here invents physics: each row is arithmetic or a
# call into an existing `core/` function.
#
# Contract:
#     derive(kind, node_values, host_values=None, system_values=None)
#         -> {key: {"value": …, "unit": str, "reason": str|None, "source": str}}
#
# `node_values` is a plain dict of already-extracted numbers (the panel does the
# OEC-node → dict extraction), so this module never sees a node dict and stays
# testable headlessly and reusable from `query.py` later.
#
# Input units (OEC, verified — §D.0): planet mass/radius Jupiter · star
# mass/radius Solar · satellite mass/radius Earth · sma AU · period days ·
# distance parsecs · temperature K.
#
# Solar-Teff conventions: `compute_star_luminosity` uses 5778 K, Kopparapu uses
# 5780 K, `core/cooling.py` uses the IAU nominal 5772 K. The spread is 0.14% in L
# — harmless, and deliberately NOT reconciled here. Do not "fix" one of them.

import math

from core.equations import (
    compute_star_luminosity,
    compute_habitable_zone,
    compute_habitable_zone_sma,
    compute_circumbinary_hz,
    compute_stellar_evolution,
    compute_ice_lines,
    compute_orbit_periastron_apastron,
    compute_hill_sphere,
    compute_atmosphere_retention,
    compute_binary_orbit_stability,
    _G, _SOLAR_MASS_KG, _SUN_RADIUS_M, _M_PER_AU,
    _JUP_MASS_KG, _JUP_RADIUS_M,
)
from core.calculators import compute_rv_semi_amplitude, compute_transit_signal
from core.shared import LY_PER_PC, M_JUP_EARTH, R_JUP_EARTH, G_MS2

# Scale constants, DERIVED from the repo's existing physical constants rather
# than re-typed — the repo already carries three solar-Teff conventions (§D rule
# 8) and does not need a fourth solar-radius one.
#   log g☉ (cgs dex) = log10(G·M☉/R☉² · 100)                        → 4.4382
#   ρ☉ (g/cm³)       = M☉ / (4/3 π R☉³)                             → 1.4102
#   θ (mas)          = 2·R☉/d ; in AU-over-pc terms 2·(R☉/AU)·1000  → 9.3009
_LOG_G_SUN = math.log10(_G * _SOLAR_MASS_KG / _SUN_RADIUS_M ** 2 * 100.0)
_RHO_SUN_GCC = (_SOLAR_MASS_KG * 1000.0) / ((4.0 / 3.0) * math.pi
                                            * (_SUN_RADIUS_M * 100.0) ** 3)
_ANG_DIAM_MAS = 2000.0 * (_SUN_RADIUS_M / _M_PER_AU)

# Planet-side scale constants, likewise derived. BOTH use the **equatorial**
# Jupiter radius (`_JUP_RADIUS_M` = 7.1492e7 m), which is what OEC's 1-bar radii
# are and the convention `core.shared.R_JUP_EARTH` is measured against (§B.2).
# Against a *mean* radius the density constant would be 1.326 — a 22% error.
#   ρ♃ (g/cm³) = M♃ / (4/3 π R♃³)         → 1.240
#   g♃ (in g)  = G·M♃ / R♃² / 9.80665     → 2.527
_RHO_JUP_GCC = (_JUP_MASS_KG * 1000.0) / ((4.0 / 3.0) * math.pi
                                          * (_JUP_RADIUS_M * 100.0) ** 3)
_G_JUP_EARTH_G = _G * _JUP_MASS_KG / _JUP_RADIUS_M ** 2 / G_MS2
_DAYS_PER_JULIAN_YEAR = 365.25

# ── Domain gates (§D.2) ──────────────────────────────────────────────────────
# The Kopparapu quartic is only valid over this range. Outside it the polynomial
# misbehaves: it peaks near 7980 K, crosses zero at ~10 684–10 720 K, and above
# that `math.sqrt(L/seff)` RAISES `ValueError: math domain error`. Any A/B host —
# and any white dwarf with a catalogued temperature — would crash the call, so we
# gate here and never rely on the core function's own bounds.
KOPPARAPU_TEFF_MIN = 2600.0
KOPPARAPU_TEFF_MAX = 7200.0

# Age of the universe — the ceiling above which a main-sequence lifetime stops
# being a prediction and becomes an extrapolation (see `_derive_evolution`).
HUBBLE_GYR = 13.8

_SRC_LUM = "R²·(T/5778)⁴ — core.equations.compute_star_luminosity"
_SRC_HZ = "Kopparapu et al. 2014 — core.equations.compute_habitable_zone"


def _num(v):
    """Finite float, or None (an OEC field may be text, empty or absent)."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f or f in (float("inf"), float("-inf")) else f


def _entry(value, unit, source):
    return {"value": value, "unit": unit, "reason": None, "source": source}


def _absent(reason, unit, source):
    return {"value": None, "unit": unit, "reason": reason, "source": source}


# ── Star-side values ─────────────────────────────────────────────────────────

def _derive_luminosity(values):
    r = _num(values.get("radius"))
    t = _num(values.get("temperature"))
    if r is None or r <= 0:
        return _absent("no catalogued radius", "L☉", _SRC_LUM)
    if t is None or t <= 0:
        return _absent("no catalogued temperature", "L☉", _SRC_LUM)
    return _entry(compute_star_luminosity(r, t)["luminosity"], "L☉", _SRC_LUM)


def _derive_hz_bounds(values, luminosity):
    """Composite (§D.4 rule 6): value is a dict of the four named bounds plus the
    full six-zone list, so callers can render a range or the whole table."""
    t = _num(values.get("temperature"))
    if t is None or t <= 0:
        return _absent("no catalogued temperature", "AU", _SRC_HZ)
    lum = _num(luminosity)
    if lum is None or lum <= 0:
        return _absent("no luminosity (needs radius + temperature)", "AU", _SRC_HZ)
    if not (KOPPARAPU_TEFF_MIN <= t <= KOPPARAPU_TEFF_MAX):
        return _absent(
            f"Teff outside Kopparapu validity ({KOPPARAPU_TEFF_MIN:.0f}–"
            f"{KOPPARAPU_TEFF_MAX:.0f} K)", "AU", _SRC_HZ)
    zones = compute_habitable_zone(t, lum)
    by_key = {z["key"]: z["au"] for z in zones}
    return _entry({
        "zones": zones,
        "optimistic_inner_au": by_key.get("rv"),     # Recent Venus
        "conservative_inner_au": by_key.get("rg"),   # Runaway Greenhouse
        "conservative_outer_au": by_key.get("mg"),   # Maximum Greenhouse
        "optimistic_outer_au": by_key.get("em"),     # Early Mars
    }, "AU", _SRC_HZ)


_SRC_GEOM = "geometry — 1 pc = 3.26156 ly; ϖ = 1000/d_pc"
_SRC_ANG = "θ = 2R☉/d, small-angle (R☉ = core.equations._SUN_RADIUS_M)"
_SRC_LOGG = "log g = log g☉ + log M − 2 log R (cgs dex)"
_SRC_RHO = "ρ = ρ☉ · M/R³ (uniform-sphere mean density)"
_SRC_ABSMAG = "M_V = V + 5 − 5·log₁₀(d_pc); no extinction correction"
_SRC_COLOUR = "catalogue magnitude difference"
_SRC_EVOL = "core.equations.compute_stellar_evolution (T_ms = 10¹⁰·M^−2.5 yr)"
_SRC_ICE = "core.equations.compute_ice_lines (M2 equilibrium model, A = 0)"
_SRC_CBHZ = ("core.equations.compute_circumbinary_hz — combined light, "
             "luminosity-weighted effective Teff")


def _derive_distance_block(values, system_values):
    """Distance-derived values. The distance is catalogued on the SYSTEM node
    (95.0% coverage), not the star, so it arrives via `system_values`."""
    out = {}
    d = _num(system_values.get("distance"))
    if d is None or d <= 0:
        reason = "no catalogued distance" if d is None else "distance is zero"
        out["light_years"] = _absent(reason, "ly", _SRC_GEOM)
        out["parallax_mas"] = _absent(reason, "mas", _SRC_GEOM)
        out["angular_diameter_mas"] = _absent(reason, "mas", _SRC_ANG)
        return out, None
    out["light_years"] = _entry(d * LY_PER_PC, "ly", _SRC_GEOM)
    out["parallax_mas"] = _entry(1000.0 / d, "mas", _SRC_GEOM)
    r = _num(values.get("radius"))
    if r is None or r <= 0:
        out["angular_diameter_mas"] = _absent("no catalogued radius", "mas", _SRC_ANG)
    else:
        out["angular_diameter_mas"] = _entry(_ANG_DIAM_MAS * r / d, "mas", _SRC_ANG)
    return out, d


def _derive_log_g(values):
    m, r = _num(values.get("mass")), _num(values.get("radius"))
    if m is None or m <= 0:
        return _absent("no catalogued mass", "dex", _SRC_LOGG)
    if r is None or r <= 0:
        return _absent("no catalogued radius", "dex", _SRC_LOGG)
    return _entry(_LOG_G_SUN + math.log10(m) - 2.0 * math.log10(r), "dex", _SRC_LOGG)


def _derive_mean_density(values):
    m, r = _num(values.get("mass")), _num(values.get("radius"))
    if m is None or m <= 0:
        return _absent("no catalogued mass", "g/cm³", _SRC_RHO)
    if r is None or r <= 0:
        return _absent("no catalogued radius", "g/cm³", _SRC_RHO)
    return _entry(_RHO_SUN_GCC * m / r ** 3, "g/cm³", _SRC_RHO)


def _derive_photometry(values, distance_pc):
    """M_V plus the two colour indices.

    Two honesty notes carried in the `source`/`reason` text rather than silently
    corrected: there is **no extinction correction**, and V−K mixes Johnson V with
    2MASS Ks — a real but small systematic that this layer must not pretend away."""
    out = {}
    v = _num(values.get("magV"))
    if v is None:
        out["abs_mag_v"] = _absent("no catalogued V magnitude", "mag", _SRC_ABSMAG)
    elif distance_pc is None:
        out["abs_mag_v"] = _absent("no catalogued distance", "mag", _SRC_ABSMAG)
    else:
        out["abs_mag_v"] = _entry(v + 5.0 - 5.0 * math.log10(distance_pc),
                                  "mag", _SRC_ABSMAG)
    b, k = _num(values.get("magB")), _num(values.get("magK"))
    out["b_minus_v"] = (_entry(b - v, "mag", _SRC_COLOUR)
                        if (b is not None and v is not None)
                        else _absent("needs both B and V magnitudes", "mag", _SRC_COLOUR))
    out["v_minus_k"] = (_entry(v - k, "mag", _SRC_COLOUR + " (Johnson V − 2MASS Ks)")
                        if (v is not None and k is not None)
                        else _absent("needs both V and K magnitudes", "mag",
                                     _SRC_COLOUR))
    return out


def _derive_evolution(values):
    """MS lifetime and — only when an age is catalogued — the current stage.

    `compute_stellar_evolution` returns `{"error"}` outside 0.1–20 M☉; that is
    unwrapped to a reason and the `"error"` key never reaches the renderer."""
    out = {}
    m = _num(values.get("mass"))
    age = _num(values.get("age"))
    if m is None or m <= 0:
        out["ms_lifetime_gyr"] = _absent("no catalogued mass", "Gyr", _SRC_EVOL)
        out["stage"] = _absent("no catalogued mass", "", _SRC_EVOL)
        return out
    result = compute_stellar_evolution(m, age)
    if isinstance(result, dict) and "error" in result:
        out["ms_lifetime_gyr"] = _absent(result["error"], "Gyr", _SRC_EVOL)
        out["stage"] = _absent(result["error"], "", _SRC_EVOL)
        return out
    # `compute_stellar_evolution` extrapolates T_ms = 10¹⁰·M^−2.5 without a cap, so
    # a 0.20 M☉ star reports 564 Gyr — a number with no physical content, since no
    # such star has left the main sequence in the age of the universe. The function
    # flags this as `low_mass`; honour the flag rather than printing the figure
    # (the Stellar Evolution panel renders the same case as "> 13.8 Gyr").
    ms = result.get("ms_end_gyr")
    entry = _entry(ms, "Gyr", _SRC_EVOL)
    if ms is not None and ms > HUBBLE_GYR:
        # `reason` doubles as a QUALIFIER when a value is present: the raw figure
        # is kept for programmatic consumers, but it must not be displayed as a
        # lifetime — no star with a model lifetime past a Hubble time has yet left
        # the main sequence, so the figure is an extrapolation, not a prediction.
        #
        # The threshold is the VALUE, not `low_mass`. `T_ms = 10¹⁰·M^−2.5` crosses
        # 13.8 Gyr at ≈0.883 M☉ while `low_mass` is set only below 0.8 M☉, so
        # keying on the flag left the well-populated 0.80–0.88 M☉ band showing a
        # bare "> 13.8 Gyr" with nothing to say whether it was a real figure or a
        # caveat.
        entry["reason"] = (f"model lifetime {ms:.0f} Gyr exceeds a Hubble time — "
                           "an extrapolation, not a prediction")
        if result.get("low_mass"):
            entry["reason"] += " (M < 0.8 M☉)"
    out["ms_lifetime_gyr"] = entry
    stage = result.get("current_stage")
    out["stage"] = (_entry(stage, "", _SRC_EVOL) if stage
                    else _absent("no catalogued age", "", _SRC_EVOL))
    return out


def _derive_ice_lines(luminosity):
    """Composite (§D.4 rule 6): the value is the `lines` list itself."""
    lum = _num(luminosity)
    if lum is None or lum <= 0:
        return _absent("no luminosity (needs radius + temperature)", "AU", _SRC_ICE)
    result = compute_ice_lines(lum)
    if isinstance(result, dict) and "error" in result:
        return _absent(result["error"], "AU", _SRC_ICE)
    return _entry(result.get("lines", []), "AU", _SRC_ICE)


def _derive_star(values, host_values, system_values):
    out = {}
    out["luminosity_lsun"] = _derive_luminosity(values)
    lum = out["luminosity_lsun"]["value"]
    out["hz_bounds"] = _derive_hz_bounds(values, lum)
    dist_block, distance_pc = _derive_distance_block(values, system_values)
    out.update(dist_block)
    out["log_g"] = _derive_log_g(values)
    out["mean_density_gcc"] = _derive_mean_density(values)
    out.update(_derive_photometry(values, distance_pc))
    out.update(_derive_evolution(values))
    out["ice_lines"] = _derive_ice_lines(lum)
    return out


def _derive_circumbinary_hz(values):
    """The circumbinary (P-type) HZ from the pair's COMBINED light (D9).

    `compute_circumbinary_hz` flags an out-of-range effective Teff but still calls
    `compute_habitable_zone`, which raises above ~10 700 K — so the D.2 gate is
    applied here, before the call, exactly as for the single-star HZ."""
    comps = [c for c in (values.get("components") or []) if isinstance(c, dict)]
    usable = []
    for c in comps:
        t, r = _num(c.get("temperature")), _num(c.get("radius"))
        if t and t > 0 and r and r > 0:
            usable.append((t, compute_star_luminosity(r, t)["luminosity"]))
    if len(usable) < 2:
        return _absent("needs radius + temperature for both components",
                       "AU", _SRC_CBHZ)
    (t1, l1), (t2, l2) = usable[0], usable[1]
    eff_teff = (l1 * t1 + l2 * t2) / (l1 + l2)
    if not (KOPPARAPU_TEFF_MIN <= eff_teff <= KOPPARAPU_TEFF_MAX):
        return _absent(
            f"combined Teff {eff_teff:.0f} K outside Kopparapu validity "
            f"({KOPPARAPU_TEFF_MIN:.0f}–{KOPPARAPU_TEFF_MAX:.0f} K)", "AU", _SRC_CBHZ)
    result = compute_circumbinary_hz(t1, l1, t2, l2)
    if isinstance(result, dict) and "error" in result:
        return _absent(result["error"], "AU", _SRC_CBHZ)
    by_key = {z["key"]: z["au"] for z in result.get("zones", [])}
    return _entry({
        "zones": result.get("zones", []),
        "combined_lum": result.get("combined_lum"),
        "eff_teff": result.get("eff_teff"),
        "conservative_inner_au": by_key.get("rg"),
        "conservative_outer_au": by_key.get("mg"),
        "optimistic_inner_au": by_key.get("rv"),
        "optimistic_outer_au": by_key.get("em"),
    }, "AU", _SRC_CBHZ)


def _derive_binary(values, host_values, system_values):
    """Circumbinary HZ (D9) + the Holman & Wiegert stability radii.

    The two are independent: a pair with masses but no temperatures gets its
    critical SMAs and no HZ, so neither may short-circuit the other."""
    out = {"hz_circumbinary": _derive_circumbinary_hz(values)}
    out.update(_derive_binary_stability(values))
    return out


# ── Entry point ──────────────────────────────────────────────────────────────

# ── Planet-side values (Stage 4b) ────────────────────────────────────────────

_SRC_KEPLER = ("Kepler III — a³ = M_total·P²  (P in years, M in M☉); "
               "neglects the planet mass")
_SRC_SEFF = "core.equations.compute_habitable_zone_sma (S = L/a²) + its 5-way verdict"
_SRC_PERI = "core.equations.compute_orbit_periastron_apastron (a(1∓e))"
_SRC_DENS = "ρ = ρ♃ · M/R³ (equatorial R♃)"
_SRC_GRAV = "g = g♃ · M/R² (equatorial R♃)"
_SRC_ATMO = "core.equations.compute_atmosphere_retention (Jeans escape, λ = 6/3)"
_SRC_RV = "core.calculators.compute_rv_semi_amplitude (Lovis & Fischer 2010)"
_SRC_TRANSIT = "core.calculators.compute_transit_signal (Winn 2010)"
_SRC_HILL = "core.equations.compute_hill_sphere + Domingos 2006 moon limit"


def _host_luminosity(host_values):
    """The host's luminosity.

    An explicit `luminosity` wins: for a circumbinary planet the host is the PAIR
    and the caller supplies the combined light, which no single radius +
    temperature could reproduce."""
    lum = _num(host_values.get("luminosity"))
    if lum is not None and lum > 0:
        return lum
    r, t = _num(host_values.get("radius")), _num(host_values.get("temperature"))
    if r is None or r <= 0 or t is None or t <= 0:
        return None
    return compute_star_luminosity(r, t)["luminosity"]


def _host_note(host_values):
    """Provenance suffix when the 'host' is a binary pair rather than one star."""
    return (" — host is the BINARY PAIR (combined mass/light)"
            if host_values.get("host_kind") == "pair" else "")


def _eccentricity(values):
    """(ecc, refusal_reason, assumed_circular).

    Three distinct cases that were previously collapsed into one silent `or 0.0`:
    catalogued and bound · **not catalogued** (circular is an assumption and is
    labelled as one) · catalogued but unbound (a refusal, matching
    `_derive_peri_apo` — the same input must not be refused in one row and
    silently zeroed two rows below)."""
    raw = values.get("eccentricity")
    e = _num(raw)
    if e is None:
        return 0.0, None, True
    if e < 0 or e >= 1:
        return None, f"eccentricity {raw} is not a bound orbit (0 ≤ e < 1)", False
    return e, None, False


def _msini_note(values):
    """Qualifier for any value derived from an M·sin i mass — which is a LOWER
    bound on the true mass, so anything monotonic in mass inherits that."""
    return (" — mass is M·sin i (a lower bound), so this is a lower bound too"
            if str(values.get("mass_type") or "").lower() == "msini" else "")


def _qualify(entry, *notes):
    """Append qualifier text to an entry's `reason` (a qualifier beside a value,
    never an absence — see `_derive_evolution`)."""
    text = "; ".join(n.strip(" —") for n in notes if n)
    if not text or entry.get("value") is None:
        return entry
    entry["reason"] = f"{entry['reason']}; {text}" if entry.get("reason") else text
    return entry


def _derive_sma(values, host_values):
    """Recover a missing semi-major axis from the period (46.0% of planets have a
    period but no `semimajoraxis` — the single biggest coverage gain in §D).

    The **days → years conversion is mandatory**: Kepler III in these units is
    a³ = M·P² with P in YEARS. Feeding days straight in overstates `a` by 365.25^⅔
    ≈ 51×."""
    a = _num(values.get("semimajoraxis"))
    if a is not None and a > 0:
        return _entry(a, "AU", "catalogued")
    p_days = _num(values.get("period"))
    m = _num(host_values.get("mass"))
    if p_days is None or p_days <= 0:
        return _absent("no catalogued semi-major axis or period", "AU", _SRC_KEPLER)
    if m is None or m <= 0:
        return _absent("no catalogued host mass", "AU", _SRC_KEPLER)
    p_yr = p_days / _DAYS_PER_JULIAN_YEAR
    return _entry((m * p_yr ** 2) ** (1.0 / 3.0), "AU",
                  _SRC_KEPLER + _host_note(host_values))


def _derive_insolation(sma_au, host_values):
    """Insolation and the HZ verdict, both from `compute_habitable_zone_sma` —
    which returns `planet_seff` *and* the five-way verdict, so neither is
    reimplemented here."""
    out = {}
    lum = _host_luminosity(host_values)
    t = _num(host_values.get("temperature"))
    if sma_au is None or sma_au <= 0:
        reason = "no semi-major axis (catalogued or recovered)"
    elif lum is None:
        reason = "host luminosity unknown (needs its radius + temperature)"
    elif t is None or not (KOPPARAPU_TEFF_MIN <= t <= KOPPARAPU_TEFF_MAX):
        reason = (f"host Teff outside Kopparapu validity "
                  f"({KOPPARAPU_TEFF_MIN:.0f}–{KOPPARAPU_TEFF_MAX:.0f} K)")
    else:
        reason = None
    if reason is not None:
        # S = L/a² needs no Kopparapu polynomial, so report it even when the
        # verdict cannot be given.
        if sma_au and sma_au > 0 and lum is not None:
            out["insolation_searth"] = _entry(lum / sma_au ** 2, "S⊕", _SRC_SEFF)
        else:
            out["insolation_searth"] = _absent(reason, "S⊕", _SRC_SEFF)
        out["hz_verdict"] = _absent(reason, "", _SRC_SEFF)
        return out
    result = compute_habitable_zone_sma(t, lum, sma_au)
    if isinstance(result, dict) and "error" in result:
        out["insolation_searth"] = _absent(result["error"], "S⊕", _SRC_SEFF)
        out["hz_verdict"] = _absent(result["error"], "", _SRC_SEFF)
        return out
    note = _host_note(host_values)
    out["insolation_searth"] = _entry(result["planet_seff"], "S⊕", _SRC_SEFF + note)
    out["hz_verdict"] = _entry(result["verdict"], "", _SRC_SEFF + note)
    return out


def _derive_peri_apo(values, sma_au):
    """Periastron / apastron DISTANCES.

    Deliberately NOT keyed `periastron`: OEC's own `periastron` field is the
    argument of periastron **in degrees** (§B.6 / T17). `compute_orbit_periastron_
    apastron` does no validation of its own, so e ≥ 1 is gated here — it would
    otherwise return a negative distance."""
    out = {}
    e = _num(values.get("eccentricity"))
    if sma_au is None or sma_au <= 0:
        reason = "no semi-major axis (catalogued or recovered)"
    elif e is None:
        reason = "no catalogued eccentricity"
    elif e < 0 or e >= 1:
        reason = f"eccentricity {e} is not a bound orbit (0 ≤ e < 1)"
    else:
        reason = None
    if reason is not None:
        out["peri_distance_au"] = _absent(reason, "AU", _SRC_PERI)
        out["apo_distance_au"] = _absent(reason, "AU", _SRC_PERI)
        return out
    r = compute_orbit_periastron_apastron(sma_au, e)
    out["peri_distance_au"] = _entry(r["periastron"], "AU", _SRC_PERI)
    out["apo_distance_au"] = _entry(r["apastron"], "AU", _SRC_PERI)
    return out


def _derive_bulk(values):
    """Density and surface gravity from the Jupiter-unit mass and radius."""
    out = {}
    m, r = _num(values.get("mass")), _num(values.get("radius"))
    if m is None or m <= 0:
        reason = "no catalogued mass"
    elif r is None or r <= 0:
        reason = "no catalogued radius"
    else:
        reason = None
    if reason is not None:
        out["density_gcc"] = _absent(reason, "g/cm³", _SRC_DENS)
        out["surface_gravity_g"] = _absent(reason, "g", _SRC_GRAV)
        return out
    note = _msini_note(values)
    out["density_gcc"] = _qualify(
        _entry(_RHO_JUP_GCC * m / r ** 3, "g/cm³", _SRC_DENS), note)
    out["surface_gravity_g"] = _qualify(
        _entry(_G_JUP_EARTH_G * m / r ** 2, "g", _SRC_GRAV), note)
    return out


def _derive_atmosphere(values):
    """Escape velocity + the Jeans retention table. Needs an equilibrium
    temperature, which OEC catalogues for only 30.3% of planets."""
    out = {}
    m, r = _num(values.get("mass")), _num(values.get("radius"))
    t = _num(values.get("temperature"))
    if m is None or m <= 0 or r is None or r <= 0:
        reason = "needs both mass and radius"
    elif t is None or t <= 0:
        reason = "no catalogued equilibrium temperature"
    else:
        reason = None
    if reason is not None:
        out["escape_velocity_kms"] = _absent(reason, "km/s", _SRC_ATMO)
        out["retention"] = _absent(reason, "", _SRC_ATMO)
        return out
    result = compute_atmosphere_retention(m * M_JUP_EARTH, r * R_JUP_EARTH, t)
    if isinstance(result, dict) and "error" in result:
        out["escape_velocity_kms"] = _absent(result["error"], "km/s", _SRC_ATMO)
        out["retention"] = _absent(result["error"], "", _SRC_ATMO)
        return out
    out["escape_velocity_kms"] = _entry(result["v_escape_kms"], "km/s", _SRC_ATMO)
    out["retention"] = _entry(result["gases"], "", _SRC_ATMO)
    return out


def _derive_rv(values, host_values, sma_au):
    """The RV semi-amplitude this planet would produce.

    Two traps, both from §D.1: `compute_rv_semi_amplitude` errors unless **exactly
    one** of period/sma is given (tau Cet e has both), and an msini mass already
    carries the sin i factor — passing a catalogued inclination as well would
    **double-count it**, so i = 90° is forced whenever the mass is msini-typed."""
    m, m_star = _num(values.get("mass")), _num(host_values.get("mass"))
    if m is None or m <= 0:
        return _absent("no catalogued mass", "m/s", _SRC_RV)
    if m_star is None or m_star <= 0:
        return _absent("no catalogued host mass", "m/s", _SRC_RV)
    period = _num(values.get("period"))
    kwargs = {}
    if period is not None and period > 0:
        kwargs["period_days"] = period
    elif sma_au is not None and sma_au > 0:
        kwargs["sma_au"] = sma_au
    else:
        return _absent("no period or semi-major axis", "m/s", _SRC_RV)
    ecc, ecc_bad, ecc_assumed = _eccentricity(values)
    if ecc_bad:
        return _absent(ecc_bad, "m/s", _SRC_RV)
    msini = str(values.get("mass_type") or "").lower() == "msini"
    # `or 90.0` would treat a catalogued **0°** (face-on) as absent and report the
    # maximum K instead of ~0.
    catalogued_i = _num(values.get("inclination"))
    incl = 90.0 if (msini or catalogued_i is None) else catalogued_i
    result = compute_rv_semi_amplitude(m * M_JUP_EARTH, m_star, ecc=ecc,
                                       inclination_deg=incl, **kwargs)
    if isinstance(result, dict) and "error" in result:
        return _absent(result["error"], "m/s", _SRC_RV)
    note = _SRC_RV + (" — mass is M·sin i, so i = 90° is forced to avoid "
                      "double-counting sin i" if msini else "")
    return _qualify(_entry(result["k_ms"], "m/s", note + _host_note(host_values)),
                    "eccentricity not catalogued — assumed circular"
                    if ecc_assumed else "")


def _derive_transit(values, host_values, sma_au):
    out = {}
    r, r_star = _num(values.get("radius")), _num(host_values.get("radius"))
    if r is None or r <= 0:
        reason = "no catalogued radius"
    elif r_star is None or r_star <= 0:
        reason = "no catalogued host radius"
    elif sma_au is None or sma_au <= 0:
        reason = "no semi-major axis (catalogued or recovered)"
    else:
        reason = None
    if reason is not None:
        out["transit_depth_ppm"] = _absent(reason, "ppm", _SRC_TRANSIT)
        out["transit_prob"] = _absent(reason, "", _SRC_TRANSIT)
        return out
    result = compute_transit_signal(r * R_JUP_EARTH, r_star, sma_au=sma_au)
    if isinstance(result, dict) and "error" in result:
        out["transit_depth_ppm"] = _absent(result["error"], "ppm", _SRC_TRANSIT)
        out["transit_prob"] = _absent(result["error"], "", _SRC_TRANSIT)
        return out
    pair = (" — R★ is the PRIMARY component's radius; a transit of a pair is "
            "against one disc" if host_values.get("host_kind") == "pair" else "")
    out["transit_depth_ppm"] = _entry(result["depth_ppm"], "ppm", _SRC_TRANSIT + pair)
    # R★/a ignores eccentricity — a flagged approximation, not a silent one.
    out["transit_prob"] = _entry(result["transit_prob"], "",
                                 _SRC_TRANSIT + " — R★/a, ignores eccentricity" + pair)
    return out


def _derive_hill(values, host_values, sma_au):
    out = {}
    m, m_star = _num(values.get("mass")), _num(host_values.get("mass"))
    if m is None or m <= 0:
        reason = "no catalogued mass"
    elif m_star is None or m_star <= 0:
        reason = "no catalogued host mass"
    elif sma_au is None or sma_au <= 0:
        reason = "no semi-major axis (catalogued or recovered)"
    else:
        reason = None
    if reason is not None:
        out["hill_radius_au"] = _absent(reason, "AU", _SRC_HILL)
        out["moon_limit_au"] = _absent(reason, "AU", _SRC_HILL)
        return out
    ecc, ecc_bad, ecc_assumed = _eccentricity(values)
    if ecc_bad:
        out["hill_radius_au"] = _absent(ecc_bad, "AU", _SRC_HILL)
        out["moon_limit_au"] = _absent(ecc_bad, "AU", _SRC_HILL)
        return out
    result = compute_hill_sphere(m_star, m * M_JUP_EARTH, sma_au, eccentricity=ecc)
    if isinstance(result, dict) and "error" in result:
        out["hill_radius_au"] = _absent(result["error"], "AU", _SRC_HILL)
        out["moon_limit_au"] = _absent(result["error"], "AU", _SRC_HILL)
        return out
    src = _SRC_HILL + _host_note(host_values)
    notes = ("eccentricity not catalogued — assumed circular" if ecc_assumed else "",
             _msini_note(values))
    out["hill_radius_au"] = _qualify(
        _entry(result["hill_radius_au"], "AU", src), *notes)
    out["moon_limit_au"] = _qualify(
        _entry(result["stable_moon_limit_au"], "AU", src), *notes)
    return out


def _derive_planet(values, host_values, system_values):
    out = {}
    sma = _derive_sma(values, host_values)
    out["sma_au"] = sma
    a = sma["value"]
    out.update(_derive_insolation(a, host_values))
    out.update(_derive_peri_apo(values, a))
    out.update(_derive_bulk(values))
    out.update(_derive_atmosphere(values))
    out["rv_semi_amplitude_ms"] = _derive_rv(values, host_values, a)
    out.update(_derive_transit(values, host_values, a))
    out.update(_derive_hill(values, host_values, a))
    return out


_SRC_STABILITY = ("core.equations.compute_binary_orbit_stability "
                  "(Holman & Wiegert 1999)")


def _binary_separation_au(values):
    """The pair's semi-major axis in AU.

    Three sources in priority order, because `separation` **repeats** (AU *and*
    arcsec rows) and must be selected by its unit, never by 'the first one':
      1. a catalogued `semimajoraxis`;
      2. a `separation` row whose unit is AU;
      3. Kepler III from the period — 61 Cygni has a period but no
         `semimajoraxis`, so without this the pair has no `a` at all.
    An arcsec-only separation is NOT converted here: that needs the system
    distance and yields a *projected* separation, not `a`."""
    a = _num(values.get("semimajoraxis"))
    if a is not None and a > 0:
        return a, "the catalogued semi-major axis"
    sep_au = _num(values.get("separation_au"))
    if sep_au is not None and sep_au > 0:
        return sep_au, "the catalogued separation (AU)"
    p_days, m = _num(values.get("period")), _num(values.get("total_mass"))
    if p_days and p_days > 0 and m and m > 0:
        p_yr = p_days / _DAYS_PER_JULIAN_YEAR
        return (m * p_yr ** 2) ** (1.0 / 3.0), "the period, via Kepler III"
    return None, None


def _derive_binary_stability(values):
    """S-type and P-type critical semi-major axes for the pair."""
    out = {}
    comps = [c for c in (values.get("components") or []) if isinstance(c, dict)]
    masses = [_num(c.get("mass")) for c in comps]
    masses = [m for m in masses if m and m > 0]
    a_bin, basis = _binary_separation_au(values)
    if len(masses) < 2:
        reason = "needs a catalogued mass for both components"
    elif a_bin is None:
        reason = "no semi-major axis, AU separation or period for the pair"
    else:
        reason = None
    if reason is not None:
        for key in ("stype_critical_au", "ptype_critical_au", "mass_ratio"):
            out[key] = _absent(reason, "AU" if key.endswith("_au") else "",
                               _SRC_STABILITY)
        return out
    ecc, ecc_bad, ecc_assumed = _eccentricity(values)
    if ecc_bad:
        for key in ("stype_critical_au", "ptype_critical_au", "mass_ratio"):
            out[key] = _absent(ecc_bad, "AU" if key.endswith("_au") else "",
                               _SRC_STABILITY)
        return out
    result = compute_binary_orbit_stability(masses[0], masses[1], a_bin,
                                            a_bin, eccentricity=ecc)
    if isinstance(result, dict) and "error" in result:
        for key in ("stype_critical_au", "ptype_critical_au", "mass_ratio"):
            out[key] = _absent(result["error"], "", _SRC_STABILITY)
        return out
    src = f"{_SRC_STABILITY}; pair a from {basis}"
    note = "eccentricity not catalogued — assumed circular" if ecc_assumed else ""
    out["stype_critical_au"] = _qualify(
        _entry(result["stype_critical_sma_au"], "AU", src), note)
    out["ptype_critical_au"] = _qualify(
        _entry(result["ptype_critical_sma_au"], "AU", src), note)
    out["mass_ratio"] = _entry(result["mass_ratio"], "", src)
    return out


_DISPATCH = {
    "star": _derive_star,
    "binary": _derive_binary,
    "planet": _derive_planet,
    # NOT satellite: `_derive_planet` reads mass/radius in JUPITER units, and a
    # `<satellite>` catalogues them in EARTH units (§D.0). Reusing it would be
    # wrong by 317×/11× with no error. Satellites are display-only for now.
}


def derive(kind, node_values, host_values=None, system_values=None):
    """Derived values for one OEC node. Unknown/unimplemented kinds → `{}`."""
    fn = _DISPATCH.get(kind)
    if fn is None:
        return {}
    return fn(node_values or {}, host_values or {}, system_values or {})
