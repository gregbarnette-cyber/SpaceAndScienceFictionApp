import csv
import os

from core.db import get_conn
from core.shared import _format_travel_time
from core.equations import _C_MS, _STANDARD_GRAVITY as _G_MS2  # shared constants (P4.5)
_HOURS_PER_JULIAN_YEAR = 8765.8128   # 365.2422 × 24 (tropical year) — legacy ly/hr↔×c anchor; NOT 365.25×24 (=8766.0).
                                     # Golden pins and the downstream consumer depend on this exact value; see IMPROVEMENT_PLAN D1.


def compute_main_sequence_table() -> list:
    """Return all rows from main_sequence_stars as a list of dicts.

    Dict keys match the original CSV column names so all callers work unchanged.
    """
    conn = get_conn()
    rows = conn.execute("""
        SELECT
            spectral_class  AS "Spectral Class",
            b_v             AS "B-V",
            teff_k          AS "Teeff(K)",
            abs_mag_vis     AS "AbsMag Vis.",
            abs_mag_bol     AS "AbsMag Bol.",
            bc              AS "Bolo. Corr. (BC)",
            lum             AS "Lum",
            radius          AS "R",
            mass            AS "M",
            density         AS "p (g/cm3)",
            lifetime        AS "Lifetime (years)"
        FROM main_sequence_stars
    """).fetchall()
    return [dict(r) for r in rows]


def compute_solar_system_tables() -> dict:
    """Return solar system body data from the DB.

    Returns a dict with keys:
        planets       — list of dicts sorted ascending by Semimajor Axis
        moons         — dict mapping planet name → list of moon dicts sorted by SemiMajor Axis
        dwarf_planets — list of dicts sorted ascending by Semimajor Axis
        asteroids     — list of dicts sorted ascending by Semimajor Axis
    """
    conn = get_conn()

    planets = [dict(r) for r in conn.execute("""
        SELECT
            planet_name    AS "Planet",
            mass           AS "Mass",
            diameter       AS "Diameter",
            period         AS "Period",
            periastron     AS "Periastron",
            semimajor_axis AS "Semimajor Axis",
            apastron       AS "Apastron",
            eccentricity   AS "Eccentricity",
            moons          AS "Moons"
        FROM planets
        ORDER BY CAST(semimajor_axis AS REAL)
    """).fetchall()]

    moons_raw = [dict(r) for r in conn.execute("""
        SELECT
            satellite_name    AS "Satellite Name",
            planet_name       AS "Planet Name",
            diameter_km       AS "Diameter (km)",
            mean_radius_km    AS "Mean Radius (km)",
            mass_kg           AS "Mass (kg)",
            perigee_km        AS "Perigee (km)",
            apogee_km         AS "Apogee (km)",
            semimajor_axis_km AS "SemiMajor Axis (km)",
            eccentricity      AS "Eccentricity",
            period_days       AS "Period (days)",
            gravity           AS "Gravity (m/s^2)",
            escape_velocity   AS "Escape Velocity (km/s)"
        FROM moons
        ORDER BY CAST(semimajor_axis_km AS REAL)
    """).fetchall()]

    planet_order = ["Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
    moons = {}
    for planet in planet_order:
        planet_moons = [m for m in moons_raw if m.get("Planet Name", "").strip() == planet]
        if planet_moons:
            moons[planet] = planet_moons

    dwarf_planets = [dict(r) for r in conn.execute("""
        SELECT
            name           AS "Name",
            periastron     AS "Periastron",
            semimajor_axis AS "Semimajor Axis",
            apastron       AS "Apastron",
            eccentricity   AS "Eccentricity",
            period         AS "Period",
            mass           AS "Mass",
            diameter       AS "Diameter",
            moons          AS "Moons"
        FROM dwarf_planets
        ORDER BY CAST(semimajor_axis AS REAL)
    """).fetchall()]

    asteroids = [dict(r) for r in conn.execute("""
        SELECT
            name           AS "Name",
            periastron     AS "Periastron",
            semimajor_axis AS "Semimajor Axis",
            apastron       AS "Apastron",
            eccentricity   AS "Eccentricity",
            period         AS "Period",
            diameter       AS "Diameter"
        FROM asteroids
        ORDER BY CAST(semimajor_axis AS REAL)
    """).fetchall()]

    return {
        "planets": planets,
        "moons": moons,
        "dwarf_planets": dwarf_planets,
        "asteroids": asteroids,
    }


def compute_honorverse_hyper_limits() -> list:
    """Return Honorverse hyper limit data from the DB.

    Returns a list of dicts with keys: spectral_class (str), lm (float), au (float).
    """
    LM_PER_AU = 8.3167
    conn = get_conn()
    rows = conn.execute(
        "SELECT spectral_class, lm FROM honorverse_hyper"
    ).fetchall()
    return [
        {"spectral_class": r["spectral_class"], "lm": r["lm"], "au": r["lm"] / LM_PER_AU}
        for r in rows
    ]


_HYPER_LETTER_SEQUENCE = ["O", "B", "A", "F", "G", "K", "M"]


def compute_hyper_limit_for_spectral_type(sp_type: str):
    """Resolve a star's Honorverse hyper limit from its spectral type (Phase O · O10b).

    Ceiling-rule lookup over the honorverse_hyper table (mirrors
    regions._lookup_spectral_type): O/B/A are single-entry letters (any subtype →
    that row); F/G/K/M are subtyped F0–M9 (smallest subtype ≥ the requested one,
    falling through to the next cooler letter's hottest entry if it exceeds the
    class; clamped to M9 past the coolest). Returns {lm, au, matched_class} or
    None (no OBAFGKM class — e.g. a white dwarf `DA…` or an unparseable/empty
    type — or an empty table). Used by core.viz.prepare_system_regions_diagram.
    """
    import re
    if not sp_type:
        return None
    m = re.search(r"(?<![A-Z])([OBAFGKM])(\d+(?:\.\d+)?)?", sp_type)
    if not m:
        return None
    letter = m.group(1)
    sub = float(m.group(2)) if m.group(2) else 0.0

    rows = compute_honorverse_hyper_limits()
    singles, subtyped = {}, {}
    for r in rows:
        rm = re.match(r"^([OBAFGKM])(\d+(?:\.\d+)?)?$", r["spectral_class"])
        if not rm:
            continue  # "Red Giant" etc. — not main-sequence-addressable
        rl, rs = rm.group(1), rm.group(2)
        if rs is None:
            singles[rl] = r
        else:
            subtyped.setdefault(rl, []).append((float(rs), r))
    for lst in subtyped.values():
        lst.sort(key=lambda t: t[0])

    start = _HYPER_LETTER_SEQUENCE.index(letter)
    for li in range(start, len(_HYPER_LETTER_SEQUENCE)):
        L = _HYPER_LETTER_SEQUENCE[li]
        want = sub if li == start else 0.0   # ceiling only within the requested letter
        if L in singles:                     # O/B/A → any subtype matches
            r = singles[L]
            return {"lm": r["lm"], "au": r["lm"] / 8.3167,
                    "matched_class": r["spectral_class"]}
        for st, r in subtyped.get(L, []):
            if st >= want:
                return {"lm": r["lm"], "au": r["lm"] / 8.3167,
                        "matched_class": r["spectral_class"]}
        # none ≥ want in this letter → fall through to the next cooler letter
    # Past the coolest available subtype → clamp to the coolest M entry.
    m_entries = subtyped.get("M", [])
    if m_entries:
        r = m_entries[-1][1]
        return {"lm": r["lm"], "au": r["lm"] / 8.3167,
                "matched_class": r["spectral_class"]}
    return None


# ── Honorverse data tables (single source of truth) ─────────────────────────
# Shared by the opt 15/16 display functions AND the Phase K calculators. Lifting
# these to module scope removes the previous duplication between the display
# functions and (formerly) the CLI.

# Mass-acceleration bands (opt 15). Numeric so K2 can select a band and scale;
# the display function formats the g-values back to "550 g" strings.
# Tuple: (mass_min, mass_max, label, warship_normal_g, merchant_normal_g,
#         warship_hyper_g, merchant_hyper_g). Labels kept verbatim (incl. the
#         historical "80-499,999" abbreviation) for byte-identical opt-15 output.
_HONORVERSE_ACCEL_BANDS = [
    (0,        79999,   "0-79,999 (FG/DD)",         550, 253, 5280, 2429),
    (80000,    499999,  "80-499,999 (CL/CA)",       520, 240, 5018, 2308),
    (500000,   1499999, "500,000-1,499,999 (BC)",   500, 230, 4825, 2215),
    (1500000,  4999999, "1,500,000-4,999,999 (BB)", 470, 215, 4536, 2085),
    (5000000,  6999999, "5,000,000-6,999,999 (DN)", 450, 207, 4345, 1990),
    (7000000,  8499999, "7,000,000-8,499,999 (SD)", 420, 190, 4053, 1860),
]

# Effective speed — Table 1 (Alpha–Iota): band, bleed_off, multiplier,
# warship_xc, merchant_xc, note. Iota is canon "unattainable" (0).
_HONORVERSE_BANDS = [
    ("Alpha",   "92%", 62,   37.2,  31.0,  ""),
    ("Beta",    "85%", 767,  460.2, 383.5, ""),
    ("Gamma",   "78%", 1473, 883.8, 736.5, ""),
    ("Delta",   "72%", 2178, 1306.8, 1089.0, ""),
    ("Epsilon", "66%", 2884, 1730.4, 1442.0, " *"),
    ("Zeta",    "61%", 3589, 2153.4, 1794.5, " *"),
    ("Eta",     "56%", 4294, 2576.4, 2147.0, " *"),
    ("Theta",   "52%", 5000, 3000.0, 2500.0, " *"),
    ("Iota",    "48%", 6000, 0,     0,      "*"),
]

# Effective speed — Table 2 (Alpha–Omega, 24 bands): band, warship_xc,
# merchant_xc, note. warship = 0.6×multiplier, merchant = 0.5×multiplier.
# Iota–Omega re-anchored so Iota = 6000× canon (Pearls of Weber); each
# multiplier above Theta is +295 vs the original smoothed sequence (which also
# cleared a −0.3 merchant transcription drift that ran from Pi onward). Bands
# above Iota are an extrapolation — the Iota band is unreachable in canon.
_HONORVERSE_EXPANDED_BANDS = [
    ("Alpha",   37.2,   31.0,   ""),
    ("Beta",    460.2,  383.5,  ""),
    ("Gamma",   883.8,  736.5,  ""),
    ("Delta",   1306.8, 1089.0, ""),
    ("Epsilon", 1730.4, 1442.0, " *"),
    ("Zeta",    2153.4, 1794.5, " *"),
    ("Eta",     2576.4, 2147.0, " *"),
    ("Theta",   3000.0, 2500.0, " *"),
    ("Iota",    3600.0, 3000.0, " *"),
    ("Kappa",   4023.6, 3353.0, " *"),
    ("Lambda",  4446.6, 3705.5, " *"),
    ("Mu",      4870.2, 4058.5, " *"),
    ("Nu",      5293.2, 4411.0, " *"),
    ("Xi",      5716.2, 4763.5, " *"),
    ("Omicron", 6139.8, 5116.5, " *"),
    ("Pi",      6562.8, 5469.0, " *"),
    ("Rho",     6986.4, 5822.0, " *"),
    ("Sigma",   7409.4, 6174.5, " *"),
    ("Tau",     7833.0, 6527.5, " *"),
    ("Upsilon", 8256.0, 6880.0, " *"),
    ("Phi",     8679.0, 7232.5, " *"),
    ("Chi",     9102.6, 7585.5, " *"),
    ("Psi",     9525.6, 7938.0, " *"),
    ("Omega",   9949.2, 8291.0, " *"),
]

# Velocity multiplier per expanded band (= warship_xc / 0.6 = merchant_xc / 0.5).
#
# The multiplier ramp is ARITHMETIC with a 7-band period. The nine canon
# (Alpha–Iota) multipliers rise 62 → 5000 over the seven Alpha→Theta steps —
# an exact +4938 per seven bands (avg step 705.43), distributed as the
# published 705/706 pattern below — then Iota breaks the ramp with a canon
# +1000 to 6000, i.e. a ONE-TIME +295 offset carried by every band from Iota on.
# So, with k = band_index - 1 (Alpha = 0):
#
#     multiplier(n) = 62 + 4938·⌊k/7⌋ + _MULT_CYCLE[k mod 7] + (295 if n ≥ 9)
#
# This reproduces all nine canon values exactly and generates Kappa–Omega, which
# is precisely how the extrapolated bands in _HONORVERSE_EXPANDED_BANDS were
# built (verified: it regenerates all 24 stored warship/merchant xC values).
_MULT_CYCLE = (0, 705, 1411, 2116, 2822, 3527, 4232)  # canon offsets within a cycle
_MULT_PERIOD = 4938        # multiplier gained per 7 bands (Alpha → Theta)
_IOTA_OFFSET = 295         # one-time canon break at Iota (5705 → 6000)


def honorverse_band_multiplier(band_index: int) -> int:
    """Velocity multiplier for the 1-based hyper-band index (Alpha = 1 … Omega = 24)."""
    k = band_index - 1
    base = 62 + _MULT_PERIOD * (k // 7) + _MULT_CYCLE[k % 7]
    return base + (_IOTA_OFFSET if band_index >= 9 else 0)


_HONORVERSE_EXPANDED_MULTIPLIERS = {
    band: honorverse_band_multiplier(i)
    for i, (band, *_rest) in enumerate(_HONORVERSE_EXPANDED_BANDS, start=1)
}

# Translation bleed-off. Unlike the multiplier's arithmetic ramp, the canon
# bleed-off decays GEOMETRICALLY: 92·0.9215^(n−1), rounded to the nearest whole
# percent, reproduces all nine published Alpha–Iota values exactly —
#   92 85 78 72 66 61 56 52 48  — a ~7.85%-per-band decay
# (log-linear least-squares fit over the nine canon points: 91.93·0.92150^(n−1),
# max residual 0.33 pp, every value rounding to its published integer).
# Kappa–Omega continue that decay: 44% … 14%. Canon publishes no bleed-off above
# Iota, so those fifteen are derived, flagged per band by `bleed_off_canon`.
_HONORVERSE_BLEED_BASE  = 92.0
_HONORVERSE_BLEED_DECAY = 0.9215
_HONORVERSE_CANON_BLEED = {band: bleed for band, bleed, *_ in _HONORVERSE_BANDS}


def honorverse_band_bleed_off(band_index: int) -> int:
    """Translation bleed-off (whole percent) for the 1-based hyper-band index."""
    return round(_HONORVERSE_BLEED_BASE * _HONORVERSE_BLEED_DECAY ** (band_index - 1))


_HONORVERSE_EXPANDED_BLEED_OFF = {
    band: (_HONORVERSE_CANON_BLEED.get(band) or f"{honorverse_band_bleed_off(i)}%")
    for i, (band, *_rest) in enumerate(_HONORVERSE_EXPANDED_BANDS, start=1)
}


def get_honorverse_accel_bands() -> list:
    """The mass-acceleration bands as numeric dicts (for the Phase K K2 calculator)."""
    return [
        {"mass_min": lo, "mass_max": hi, "label": lbl,
         "warship_normal_g": wn, "merchant_normal_g": mn,
         "warship_hyper_g": wh, "merchant_hyper_g": mh}
        for lo, hi, lbl, wn, mn, wh, mh in _HONORVERSE_ACCEL_BANDS
    ]


def get_honorverse_expanded_bands() -> list:
    """The 24 expanded speed bands as dicts (for the Phase K K1 calculator)."""
    return [
        {"band": b, "warship_xc": w, "merchant_xc": m, "note": n}
        for b, w, m, n in _HONORVERSE_EXPANDED_BANDS
    ]


def compute_honorverse_acceleration_table() -> list:
    """Return the Honorverse acceleration-by-mass table as a list of dicts.

    Each dict has keys: mass_range, warship_normal, merchant_normal,
                        warship_hyper, merchant_hyper.
    """
    return [
        {
            "mass_range": lbl,
            "warship_normal": f"{wn} g",
            "merchant_normal": f"{mn} g",
            "warship_hyper": f"{wh} g",
            "merchant_hyper": f"{mh} g",
        }
        for lo, hi, lbl, wn, mn, wh, mh in _HONORVERSE_ACCEL_BANDS
    ]


def compute_honorverse_effective_speed() -> dict:
    """Return Honorverse effective speed data for both band tables.

    Returns a dict with keys:
        bands          — list of dicts for Alpha–Iota (Table 1)
        expanded_bands — list of dicts for Alpha–Omega (Table 2)

    Each band dict has keys: band, bleed_off, multiplier, warship_xc,
    merchant_xc, merchant_note. expanded_bands additionally carries
    bleed_off_canon — False for the bands above Iota, whose bleed-off is
    extrapolated from the canon 92·0.9215^(n−1) decay rather than published.
    """
    def _ly_hr(xc):
        return xc / _HOURS_PER_JULIAN_YEAR if xc else 0.0

    bands = [
        {
            "band": band, "bleed_off": bleed, "multiplier": mult,
            "warship_xc": war_xc, "warship_ly_hr": _ly_hr(war_xc),
            "merchant_xc": mer_xc, "merchant_ly_hr": _ly_hr(mer_xc),
            "merchant_note": note,
        }
        for band, bleed, mult, war_xc, mer_xc, note in _HONORVERSE_BANDS
    ]

    expanded_bands = [
        {
            "band": band,
            "bleed_off": _HONORVERSE_EXPANDED_BLEED_OFF.get(band),
            "bleed_off_canon": band in _HONORVERSE_CANON_BLEED,
            "multiplier": _HONORVERSE_EXPANDED_MULTIPLIERS.get(band),
            "warship_xc": war_xc, "warship_ly_hr": _ly_hr(war_xc),
            "merchant_xc": mer_xc, "merchant_ly_hr": _ly_hr(mer_xc),
            "merchant_note": note,
        }
        for band, war_xc, mer_xc, note in _HONORVERSE_EXPANDED_BANDS
    ]

    return {"bands": bands, "expanded_bands": expanded_bands}


# ── Phase K calculators ──────────────────────────────────────────────────────

def compute_hyper_translation_time(distance_ly, ship_type) -> dict:
    """Travel time for a distance across all 24 hyper bands, per ship type (K1).

    Self-validating. Returns:
        {distance_ly, ship_type,
         bands: [{band, speed_xc, speed_ly_hr, travel_hours, travel_time, note}],
         footnote: str | None}
        or {"error": str}
    """
    if distance_ly is None or distance_ly <= 0:
        return {"error": "Distance must be positive."}
    st = (ship_type or "").strip().lower()
    if st not in ("warship", "merchantship"):
        return {"error": "Ship type must be 'warship' or 'merchantship'."}

    out, any_star = [], False
    for band, war_xc, mer_xc, note in _HONORVERSE_EXPANDED_BANDS:
        xc = war_xc if st == "warship" else mer_xc
        starred = bool(note.strip()) and st == "merchantship"
        any_star = any_star or starred
        if xc:
            ly_hr = xc / _HOURS_PER_JULIAN_YEAR
            hours = distance_ly / ly_hr
            travel = _format_travel_time(hours)
        else:
            ly_hr, hours, travel = 0.0, None, "N/A"
        out.append({
            "band": band, "speed_xc": xc, "speed_ly_hr": ly_hr,
            "travel_hours": hours, "travel_time": travel, "note": note.strip(),
        })
    footnote = ("* Bands merchantmen do not normally operate in (Epsilon onward); "
                "the speeds shown are their maximum theoretical values."
                if any_star else None)
    return {"distance_ly": distance_ly, "ship_type": st, "bands": out, "footnote": footnote}


def compute_impeller_wedge(ship_mass_tons, ship_type, wedge_power_pct) -> dict:
    """Effective acceleration and max velocities for a ship at a wedge power (K2).

    Self-validating; a mass above the heaviest band clamps to it (clamped=True).
    Returns:
        {ship_mass_tons, mass_band, clamped, ship_type, wedge_power_pct,
         base_accel_g, effective_accel_g, max_vel_normal_xc, max_vel_hyper_xc,
         time_to_max_vel}
        or {"error": str}
    """
    if ship_mass_tons is None or ship_mass_tons <= 0:
        return {"error": "Ship mass must be positive."}
    if wedge_power_pct is None or not (0 < wedge_power_pct <= 100):
        return {"error": "Wedge power must be between 0 and 100 percent."}
    st = (ship_type or "").strip().lower()
    if st not in ("warship", "merchantship"):
        return {"error": "Ship type must be 'warship' or 'merchantship'."}

    bands = get_honorverse_accel_bands()
    band, clamped = None, False
    for b in bands:
        if b["mass_min"] <= ship_mass_tons <= b["mass_max"]:
            band = b
            break
    if band is None:                      # above the heaviest band → clamp
        band = bands[-1]
        clamped = True

    base = band["warship_normal_g"] if st == "warship" else band["merchant_normal_g"]
    eff = base * wedge_power_pct / 100.0
    cap = 0.8 if st == "warship" else 0.6          # canon full-power velocity cap
    max_norm = cap * wedge_power_pct / 100.0
    t_s = (max_norm * _C_MS) / (eff * _G_MS2)      # time from rest to max velocity

    return {
        "ship_mass_tons": ship_mass_tons, "mass_band": band["label"],
        "clamped": clamped, "ship_type": st, "wedge_power_pct": wedge_power_pct,
        "base_accel_g": base, "effective_accel_g": eff,
        "max_vel_normal_xc": max_norm, "max_vel_hyper_xc": max_norm,
        "time_to_max_vel": _format_travel_time(t_s / 3600.0),
    }
