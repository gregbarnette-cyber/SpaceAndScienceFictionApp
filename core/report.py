# core/report.py — System Dossier composition (Phase Q).
#
# Pure formatting/composition over the existing readers — NO Qt, NO file I/O, NO new
# astronomy. Reads the result dicts compute_simbad_lookup / compute_star_system_regions_*
# / compute_planetary_systems_composite / compute_hwc / compute_hypatia_data already
# produce, merges them, and renders one document (markdown / html) or a structured data
# dict (json).
#
# Rendering uses a small block model (em/h3/strong/p/kv/table) so markdown and HTML share
# one section structure; the json `data` payload is the per-section data dicts.
#
# Validation tiers (Phase H contract — curated {"error"}):
#   - hard error  → {"error": str} : bad fmt/section, or SIMBAD lookup fails for a real star.
#   - soft warn   → warnings[]      : a requested section's source failed/returned nothing.
#   - by-design   → notes[]         : an intentional omission (e.g. GCNS-N/A on Sol).
#
# Build status: Q-core-2 — normal-star path (identity/regions/habitable_zone/planets/
# hypatia/gcns) + markdown/html/json renderers + the full Phase P regions surface. The
# Sol path lands in Q-core-3; the query.py surface in Q-core-4; the GUI panel in Q-core-5.

import core.databases as databases
import core.regions as regions
import core.science as science
from core.equations import compute_habitable_zone, implied_edge_temp
from core.hypatia_elements import CATEGORIES, display_symbol

_AU_TO_LM = 8.3167
_FORMATS = {"markdown", "html", "json"}

# Section vocabulary. "moons" is a Sol-only opt-in section: valid to request, but never in
# the default set (decision #13) — large, and meaningless for a single star.
_SECTION_ORDER = ["identity", "regions", "habitable_zone", "planets", "hypatia", "gcns", "moons"]
_ALL_SECTIONS = ["identity", "regions", "habitable_zone", "planets", "hypatia", "gcns"]

_SECTION_TITLES = {
    "identity":       "Identity",
    "regions":        "Stellar Properties & System Regions",
    "habitable_zone": "Calculated Habitable Zone (Kopparapu et al. 2014)",
    "planets":        "Planets",
    "hypatia":        "Elemental Abundances (Hypatia Catalog · Lodders 2009)",
    "gcns":           "GCNS Cross-Reference (Gaia Catalogue of Nearby Stars)",
    "moons":          "Moon Systems",
}

# Curated identity designation subset (decision: common name + HD/HIP/GJ/HR/Gaia).
_IDENTITY_DESIG_KEYS = ["HD", "HIP", "GJ", "HR", "Gaia EDR3"]

# The full Phase P alternate-solvent surface (M1) — (display name, inner key, outer key,
# pressure_conditional). Implied edge temps come from implied_edge_temp (L cancels, so the
# liquid range is the solvent's intrinsic boil/freeze pair, the same for every star).
_ALT_SOLVENT_BANDS = [
    ("Fluorosilicone–Fluorosilicone", "ffInner",  "ffOuter",  False),
    ("Fluorocarbon–Sulfur",           "fsInner",  "fsOuter",  False),
    ("Protein–Water",                 "prwInner", "prwOuter", False),
    ("Protein–Ammonia",               "praInner", "praOuter", False),
    ("Polylipid–Methane",             "pmInner",  "pmOuter",  False),
    ("Polylipid–Hydrogen",            "phInner",  "phOuter",  False),
    ("Carbon Dioxide",                "co2Inner", "co2Outer", True),
    ("Liquid Sulfur",                 "sInner",   "sOuter",   False),
    ("Water–Ammonia Eutectic",        "waInner",  "waOuter",  False),
    ("Sulfuric Acid",                 "saInner",  "saOuter",  False),
]

# The Phase P ice/condensation surface (M2) — (species, regions key, condensation T (K),
# kind, disk_line). The cond temps are the fixed model values regions.py keys on.
_ICE_LINES = [
    ("Water (snow line)",    "snowLine",   170, "snow_line", False),
    ("Ammonia (NH₃)",        "iceLineNH3",  80, "front",     False),
    ("Carbon dioxide (CO₂)", "iceLineCO2",  70, "front",     False),
    ("Nitrogen (N₂)",        "iceLineN2",   22, "front",     True),
    ("Carbon monoxide (CO)", "iceLineCO",   20, "front",     True),
]


# ── number/formatting helpers ─────────────────────────────────────────────────

def _fnum(v):
    """Coerce to float, or None (HWC cells are TEXT; archive cells may be masked)."""
    try:
        f = float(v)
        return f
    except (TypeError, ValueError):
        return None


def _n(v, dp=3):
    """Format a float to dp decimals, or '—' for None/non-numeric."""
    f = _fnum(v)
    return f"{f:.{dp}f}" if f is not None else "—"


def _g(v, sig=3):
    """General format (significant figures) for large/small magnitudes, or '—'."""
    f = _fnum(v)
    return f"{f:.{sig}g}" if f is not None else "—"


def _au(v, dp=3, lm=False):
    """'X.XXX AU' (optionally with the light-minute equivalent), or '—'."""
    f = _fnum(v)
    if f is None:
        return "—"
    return f"{f:.{dp}f} AU ({f * _AU_TO_LM:.{dp}f} LM)" if lm else f"{f:.{dp}f} AU"


def _hwc_bool(v):
    """HWC flag cell ('1'/'0') → Yes/No/—."""
    s = str(v).strip() if v is not None else ""
    return {"1": "Yes", "0": "No"}.get(s, "—")


# ── section data builders (the json `data` payload) ───────────────────────────

def _identity_data_star(simbad):
    desig = simbad.get("designations", {}) or {}
    name_raw = desig.get("NAME")
    common = name_raw.replace("NAME ", "", 1).strip() if name_raw else None
    subset = [str(desig[k]) for k in _IDENTITY_DESIG_KEYS if desig.get(k)]
    return {
        "primary_name": simbad.get("main_id"),
        "common_name": common,
        "spectral_type": simbad.get("sp_type"),
        "designations": subset,
        "ra": simbad.get("ra"),
        "dec": simbad.get("dec"),
        "app_magnitude": simbad.get("vmag"),
        "parallax_mas": simbad.get("plx_value"),
        "parsecs": simbad.get("parsecs"),
        "light_years": simbad.get("ly"),
    }


def _identity_data_sol():
    """Hardcoded solar-constant identity (Sol doesn't resolve in SIMBAD)."""
    return {
        "primary_name": "Sol (the Sun)",
        "common_name": "Sun",
        "spectral_type": "G2V",
        "designations": [],
        "ra": None, "dec": None,
        "app_magnitude": -26.74,
        "parallax_mas": None,
        "parsecs": 0.0, "light_years": 0.0,
    }


def _planets_data_sol(ss):
    """Real Solar System bodies (compute_solar_system_tables) under a 'sol' discriminator
    so _blocks_planets can tell them from the NASA/HWC exoplanet shape."""
    return {"sol": {
        "planets": ss.get("planets", []),
        "dwarf_planets": ss.get("dwarf_planets", []),
        "asteroids": ss.get("asteroids", []),
    }}


def _regions_data(reg):
    L = reg.get("bcLuminosity")
    bands = []
    for name, ik, ok, pc in _ALT_SOLVENT_BANDS:
        inner, outer = reg.get(ik), reg.get(ok)
        bands.append({
            "name": name, "inner_au": inner, "outer_au": outer,
            "t_boil_k": implied_edge_temp(inner, L, "surface"),
            "t_freeze_k": implied_edge_temp(outer, L, "surface"),
            "pressure_conditional": pc,
        })
    bands.sort(key=lambda b: b["inner_au"] if b["inner_au"] is not None else float("inf"))
    ice = [{"species": nm, "t_cond_k": t, "au": reg.get(k), "kind": kind, "disk_line": disk}
           for nm, k, t, kind, disk in _ICE_LINES]
    return {
        "sunlight_intensity": reg.get("sunlight_intensity"),
        "bond_albedo": reg.get("bond_albedo"),
        "stellar": {
            "teff": reg.get("temp"),
            "stellar_mass": reg.get("stellarMass"),
            "stellar_radius": reg.get("stellarRadius"),
            "bc_luminosity": reg.get("bcLuminosity"),
            "luminosity_from_mass": reg.get("luminosityFromMass"),
            "calculated_luminosity": reg.get("calculatedLuminosity"),
            "main_seq_lifespan_yr": reg.get("mainSeqLifeSpan"),
        },
        "system_regions": {
            "inner_limit_gravity_au": reg.get("sysilGrav"),
            "inner_limit_sunlight_au": reg.get("sysilSunlight"),
            "hz_inner_au": reg.get("hzil"),
            "eeid_au": reg.get("distAU"),
            "hz_outer_au": reg.get("hzol"),
            "water_snow_line_au": reg.get("snowLine"),
            "n2_co_condensation_au": reg.get("lh2Line"),
            "outer_limit_au": reg.get("sysol"),
        },
        "alt_solvent": bands,
        "ice_lines": ice,
    }


def _hz_data(reg):
    teff = reg.get("temp")
    cols = [("Bolometric L", reg.get("bcLuminosity")),
            ("Luminosity from mass", reg.get("luminosityFromMass")),
            ("Calculated L", reg.get("calculatedLuminosity"))]
    per_col = [compute_habitable_zone(teff, L) for _, L in cols]
    base = per_col[0]
    zones = [{"zone": z["zone_name"], "au": [pc[i]["au"] for pc in per_col]}
             for i, z in enumerate(base)]
    return {"columns": [c[0] for c in cols], "zones": zones}


def _planets_data(nasa_planets, hwc_planets):
    data = {}
    if nasa_planets:
        rows = [{
            "name": p.get("pl_name"),
            "mass_earth": _fnum(p.get("pl_bmasse")),
            "radius_earth": _fnum(p.get("pl_rade")),
            "sma_au": _fnum(p.get("pl_orbsmax")),
            "period_days": _fnum(p.get("pl_orbper")),
            "eccentricity": _fnum(p.get("pl_orbeccen")),
            "inclination_deg": _fnum(p.get("pl_orbincl")),
            "method": p.get("discoverymethod"),
        } for p in nasa_planets]
        rows.sort(key=lambda r: r["sma_au"] if r["sma_au"] is not None else float("inf"))
        data["nasa"] = rows
    if hwc_planets:
        rows = [{
            "name": p.get("P_NAME"),
            "mass_earth": _fnum(p.get("P_MASS")),
            "sma_au": _fnum(p.get("P_SEMI_MAJOR_AXIS")),
            "type": p.get("P_TYPE"),
            "in_hz_con": _hwc_bool(p.get("P_HABZONE_CON")),
            "esi": _fnum(p.get("P_ESI")),
            "habitable": _hwc_bool(p.get("P_HABITABLE")),
        } for p in hwc_planets]
        rows.sort(key=lambda r: r["sma_au"] if r["sma_au"] is not None else float("inf"))
        data["hwc"] = rows
    return data


def _hypatia_data(hyp):
    props = hyp.get("properties", {}) or {}
    abundances = hyp.get("abundances", []) or []
    fe = next((a for a in abundances if a.get("element") == "Fe"), None)
    return {
        "star_name": hyp.get("star_name"),
        "teff": props.get("teff"),
        "logg": props.get("logg"),
        "disk": props.get("disk"),
        "fe_h": fe.get("mean") if fe else None,
        "species_count": len(abundances),
        "abundances": abundances,
    }


def _gcns_data(gcns):
    return {
        "gaia_source_id": gcns.get("gaia_source_id"),
        "distance_method": gcns.get("distance_method"),
        "dist_pc": gcns.get("dist_pc"),
        "dist_lo_pc": gcns.get("dist_lo_pc"),
        "dist_hi_pc": gcns.get("dist_hi_pc"),
        "light_years": gcns.get("light_years"),
        "phot_g_mean_mag": gcns.get("phot_g_mean_mag"),
        "phot_bp_mean_mag": gcns.get("phot_bp_mean_mag"),
        "phot_rp_mean_mag": gcns.get("phot_rp_mean_mag"),
        "astrom_reliable_prob": gcns.get("astrom_reliable_prob"),
        "wd_prob": gcns.get("wd_prob"),
        "system_id": gcns.get("system_id"),
        "n_components": gcns.get("n_components"),
    }


# ── section block builders (presentation; consumed by both md and html) ───────
# A block is a tuple: ("em"|"h3"|"strong"|"p", text) | ("kv", rows) | ("table", headers, rows).

def _blocks_identity(d):
    rows = [
        ("Primary name", d.get("primary_name") or "—"),
        ("Common name", d.get("common_name") or "—"),
        ("Spectral type", d.get("spectral_type") or "—"),
        ("Designations", ", ".join(d.get("designations") or []) or "—"),
        ("RA / Dec (deg)", f"{_n(d.get('ra'), 4)} / {_n(d.get('dec'), 4)}"),
        ("Apparent magnitude (V)", _n(d.get("app_magnitude"), 2)),
        ("Parallax (mas)", _n(d.get("parallax_mas"), 4)),
        ("Distance", f"{_n(d.get('parsecs'), 4)} pc ({_n(d.get('light_years'), 3)} ly)"),
    ]
    return _SECTION_TITLES["identity"], [("kv", rows)]


def _blocks_regions(d):
    s = d["stellar"]
    sr = d["system_regions"]
    blocks = [
        ("em", f"Computed with sunlight intensity = {_n(d.get('sunlight_intensity'), 1)}, "
               f"bond albedo = {_n(d.get('bond_albedo'), 1)}."),
        ("kv", [
            ("Effective temperature", f"{_n(s.get('teff'), 0)} K"),
            ("Stellar mass", f"{_n(s.get('stellar_mass'))} M☉"),
            ("Stellar radius", f"{_n(s.get('stellar_radius'))} R☉"),
            ("Bolometric luminosity", f"{_n(s.get('bc_luminosity'))} L☉"),
            ("Luminosity from mass", f"{_n(s.get('luminosity_from_mass'))} L☉"),
            ("Calculated luminosity", f"{_n(s.get('calculated_luminosity'))} L☉"),
            ("Main-sequence lifespan", f"{_g(s.get('main_seq_lifespan_yr'))} yr"),
        ]),
        ("table", ["System region", "Distance"], [
            ("Inner system limit (gravity)", _au(sr.get("inner_limit_gravity_au"))),
            ("Inner system limit (sunlight)", _au(sr.get("inner_limit_sunlight_au"))),
            ("Habitable zone — inner", _au(sr.get("hz_inner_au"), lm=True)),
            ("Earth-equivalent orbit (EEID)", _au(sr.get("eeid_au"), lm=True)),
            ("Habitable zone — outer", _au(sr.get("hz_outer_au"), lm=True)),
            ("Water snow line", _au(sr.get("water_snow_line_au"), lm=True)),
            ("N₂/CO (1-atm) condensation", _au(sr.get("n2_co_condensation_au"), lm=True)),
            ("Outer system limit", _au(sr.get("outer_limit_au"))),
        ]),
    ]
    # Alternate Solvent Habitable Zones (Phase P · M1)
    blocks.append(("h3", "Alternate Solvent Habitable Zones (Phase P · M1 surface model)"))
    has_pc = False
    arows = []
    for b in d["alt_solvent"]:
        name = b["name"] + (" †" if b["pressure_conditional"] else "")
        has_pc = has_pc or b["pressure_conditional"]
        if b["t_freeze_k"] is not None and b["t_boil_k"] is not None:
            lr = f"{b['t_freeze_k']:.0f}–{b['t_boil_k']:.0f}"
        else:
            lr = "—"
        arows.append([name, _n(b["inner_au"]), _n(b["outer_au"]), lr])
    blocks.append(("table", ["Solvent zone", "Inner (AU)", "Outer (AU)", "Liquid range (K)"], arows))
    if has_pc:
        blocks.append(("em", "† Carbon Dioxide is pressure-conditional — requires ≥ 5.2 atm "
                             "to sustain liquid CO₂."))
    # Condensation / Ice Lines (Phase P · M2)
    blocks.append(("h3", "Condensation / Ice Lines (Phase P · M2 equilibrium model)"))
    irows = []
    for il in d["ice_lines"]:
        kind = il["kind"] + (" · disk-set" if il["disk_line"] else "")
        irows.append([il["species"], _n(il["t_cond_k"], 0), _n(il["au"]), kind])
    blocks.append(("table", ["Species", "Condensation T (K)", "Distance (AU)", "Kind"], irows))
    return _SECTION_TITLES["regions"], blocks


def _blocks_hz(d):
    headers = ["Zone"] + d["columns"]
    rows = [[z["zone"]] + [_au(au) for au in z["au"]] for z in d["zones"]]
    return _SECTION_TITLES["habitable_zone"], [("table", headers, rows)]


def _blocks_planets_sol(ss):
    blocks = []
    pl = ss.get("planets", [])
    if pl:
        blocks.append(("h3", f"Planets · {len(pl)}"))
        rows = [[p.get("Planet") or "—", _n(p.get("Mass"), 6), _n(p.get("Diameter"), 4),
                 _n(p.get("Period"), 3), _n(p.get("Periastron"), 4),
                 _n(p.get("Semimajor Axis"), 4), _n(p.get("Apastron"), 4),
                 _n(p.get("Eccentricity"), 4), p.get("Moons") if p.get("Moons") is not None else "—"]
                for p in pl]
        blocks.append(("table", ["Planet", "Mass (M♃)", "Diameter (D♃)", "Period (yr)",
                                 "Periastron (AU)", "Semi-major axis (AU)", "Apastron (AU)",
                                 "Eccentricity", "Moons"], rows))
    dw = ss.get("dwarf_planets", [])
    if dw:
        blocks.append(("h3", f"Dwarf Planets · {len(dw)}"))
        rows = [[p.get("Name") or "—", _n(p.get("Mass"), 6), _n(p.get("Periastron"), 4),
                 _n(p.get("Semimajor Axis"), 4), _n(p.get("Apastron"), 4),
                 _n(p.get("Eccentricity"), 4), _n(p.get("Period"), 3)] for p in dw]
        blocks.append(("table", ["Name", "Mass (M⊕)", "Periastron (AU)", "Semi-major axis (AU)",
                                 "Apastron (AU)", "Eccentricity", "Period (yr)"], rows))
    ast = ss.get("asteroids", [])
    if ast:
        blocks.append(("h3", f"Major Asteroids · {len(ast)}"))
        rows = [[p.get("Name") or "—", _n(p.get("Diameter"), 1), _n(p.get("Periastron"), 4),
                 _n(p.get("Semimajor Axis"), 4), _n(p.get("Apastron"), 4),
                 _n(p.get("Eccentricity"), 4), _n(p.get("Period"), 3)] for p in ast]
        blocks.append(("table", ["Asteroid", "Diameter (km)", "Periastron (AU)",
                                 "Semi-major axis (AU)", "Apastron (AU)", "Eccentricity",
                                 "Period (yr)"], rows))
    return _SECTION_TITLES["planets"], blocks


def _blocks_moons(moons):
    blocks = []
    for planet, sats in moons.items():
        blocks.append(("h3", f"{planet} · {len(sats)} moon(s)"))
        rows = [[m.get("Satellite Name") or "—", _n(m.get("Diameter (km)"), 1),
                 _n(m.get("SemiMajor Axis (km)"), 0), _n(m.get("Eccentricity"), 4),
                 _n(m.get("Period (days)"), 3), _n(m.get("Gravity (m/s^2)"), 4),
                 _n(m.get("Escape Velocity (km/s)"), 4)] for m in sats]
        blocks.append(("table", ["Satellite", "Diameter (km)", "SemiMajor Axis (km)",
                                 "Eccentricity", "Period (days)", "Gravity (m/s²)",
                                 "Escape (km/s)"], rows))
    return _SECTION_TITLES["moons"], blocks


def _blocks_planets(d):
    if "sol" in d:
        return _blocks_planets_sol(d["sol"])
    blocks = []
    nasa = d.get("nasa")
    hwc = d.get("hwc")
    if nasa:
        blocks.append(("h3", f"NASA Exoplanet Archive — pscomppars (priority 1) · "
                             f"{len(nasa)} planet(s)"))
        rows = [[p["name"] or "—", _n(p["mass_earth"]), _n(p["radius_earth"]),
                 _n(p["sma_au"]), _n(p["period_days"]), _n(p["eccentricity"]),
                 _n(p["inclination_deg"], 1), p["method"] or "—"] for p in nasa]
        blocks.append(("table", ["Planet", "Mass (M⊕)", "Radius (R⊕)", "SMA (AU)",
                                 "Period (d)", "Eccentricity", "Incl. (°)", "Disc. method"], rows))
    if hwc:
        blocks.append(("h3", f"Habitable Worlds Catalog (priority 2) · {len(hwc)} planet(s)"))
        rows = [[p["name"] or "—", _n(p["mass_earth"]), _n(p["sma_au"]), p["type"] or "—",
                 p["in_hz_con"], _n(p["esi"]), p["habitable"]] for p in hwc]
        blocks.append(("table", ["Planet", "Mass (M⊕)", "SMA (AU)", "Type",
                                 "In HZ (cons.)", "ESI", "Habitable?"], rows))
    return _SECTION_TITLES["planets"], blocks


def _blocks_hypatia(d):
    head = (f"T_eff {_n(d.get('teff'), 0)} K · log g {_n(d.get('logg'), 2)} · "
            f"[Fe/H] {_n(d.get('fe_h'), 2)} · Disk: {d.get('disk') or '—'} · "
            f"{d.get('species_count', 0)} species on record.")
    blocks = [("p", head)]
    by_cat = {}
    for a in d.get("abundances", []):
        by_cat.setdefault(a.get("category"), []).append(a)
    for key, label, _color in CATEGORIES:
        items = by_cat.get(key)
        if not items:
            continue
        blocks.append(("strong", label))
        rows = [[display_symbol(a.get("element", "")), _n(a.get("mean"), 2),
                 _n(a.get("std"), 2), a.get("n") if a.get("n") is not None else "—"]
                for a in items]
        blocks.append(("table", ["Element", "[X/H]", "±Std", "# Catalogs"], rows))
    return _SECTION_TITLES["hypatia"], blocks


def _blocks_gcns(d):
    lo, hi, c = d.get("dist_lo_pc"), d.get("dist_hi_pc"), d.get("dist_pc")
    if lo is not None and hi is not None and c is not None:
        sigma = f"{_n(c, 4)} pc (−{_n(float(c) - float(lo), 4)} / +{_n(float(hi) - float(c), 4)} pc)"
    else:
        sigma = f"{_n(c, 4)} pc (— no Bayesian σ)"
    sys_ptr = ("part of a Gaia-resolved system (system_id "
               f"{d.get('system_id')}, {d.get('n_components')} components)"
               if d.get("system_id") else
               "not part of a Gaia-resolved multiple system (single or unresolved)")
    rows = [
        ("Gaia source id", d.get("gaia_source_id") or "—"),
        ("Distance basis", d.get("distance_method") or "—"),
        ("Bayesian distance", sigma),
        ("Light years", _n(d.get("light_years"), 3)),
        ("Gaia G / BP / RP", f"{_n(d.get('phot_g_mean_mag'), 2)} / "
                             f"{_n(d.get('phot_bp_mean_mag'), 2)} / "
                             f"{_n(d.get('phot_rp_mean_mag'), 2)}"),
        ("Astrometry reliable prob.", _n(d.get("astrom_reliable_prob"), 2)),
        ("White-dwarf prob.", _n(d.get("wd_prob"), 2)),
        ("Resolved system", sys_ptr),
    ]
    return _SECTION_TITLES["gcns"], [("kv", rows)]


_SECTION_BLOCKS = {
    "identity": _blocks_identity,
    "regions": _blocks_regions,
    "habitable_zone": _blocks_hz,
    "planets": _blocks_planets,
    "hypatia": _blocks_hypatia,
    "gcns": _blocks_gcns,
    "moons": _blocks_moons,
}


# ── markdown rendering ────────────────────────────────────────────────────────

def _md_table(headers, rows):
    out = ["| " + " | ".join(str(h) for h in headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def _md_block(b):
    t = b[0]
    if t == "h3":
        return f"### {b[1]}"
    if t == "strong":
        return f"**{b[1]}**"
    if t == "em":
        return f"*{b[1]}*"
    if t == "p":
        return b[1]
    if t == "kv":
        return _md_table(["Field", "Value"], b[1])
    if t == "table":
        return _md_table(b[1], b[2])
    return ""


def _md_section(title, blocks):
    return "\n\n".join([f"## {title}"] + [_md_block(b) for b in blocks])


def _render_markdown(star, rendered, data, warnings, notes):
    parts = [f"# {star} — System Dossier",
             "*Generated by Space & Science Fiction App · sections: "
             + ", ".join(rendered) + "*"]
    for key in rendered:
        parts.append(_md_section(*_SECTION_BLOCKS[key](data[key])))
    footer = f"*End of dossier · {len(warnings)} warning(s) · {len(notes)} note(s).*"
    if warnings:
        footer += "\n\n" + "\n".join(f"> ⚠ {w}" for w in warnings)
    if notes:
        footer += "\n\n" + "\n".join(f"> ℹ {n}" for n in notes)
    parts.append(footer)
    return "\n\n".join(parts)


# ── HTML rendering (self-contained; text + tables only — images are GUI-only) ─

_HTML_STYLE = (
    "<style>"
    "body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"
    "max-width:54rem;margin:2rem auto;padding:0 1rem;color:#222;line-height:1.5}"
    "h1{border-bottom:2px solid #334455;padding-bottom:.3rem}"
    "h2{margin-top:2rem;color:#223344;border-bottom:1px solid #ccd;padding-bottom:.2rem}"
    "h3{margin-top:1.2rem;color:#445566}"
    "table{border-collapse:collapse;margin:.6rem 0;font-size:.92rem}"
    "th,td{border:1px solid #ccd;padding:.3rem .6rem;text-align:left}"
    "th{background:#eef}"
    ".warn{color:#aa4400}.note{color:#226688}"
    "footer{margin-top:2rem;color:#666;font-size:.9rem;border-top:1px solid #ccd;"
    "padding-top:.6rem}"
    "</style>"
)


def _esc(x):
    return (str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _html_table(headers, rows):
    head = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{_esc(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _html_block(b):
    t = b[0]
    if t == "h3":
        return f"<h3>{_esc(b[1])}</h3>"
    if t == "strong":
        return f"<p><strong>{_esc(b[1])}</strong></p>"
    if t == "em":
        return f"<p><em>{_esc(b[1])}</em></p>"
    if t == "p":
        return f"<p>{_esc(b[1])}</p>"
    if t == "kv":
        return _html_table(["Field", "Value"], b[1])
    if t == "table":
        return _html_table(b[1], b[2])
    return ""


def _html_section(title, blocks):
    return "\n".join([f"<h2>{_esc(title)}</h2>"] + [_html_block(b) for b in blocks])


def _render_html(star, rendered, data, warnings, notes):
    body = [f"<h1>{_esc(star)} — System Dossier</h1>",
            f"<p><em>Generated by Space &amp; Science Fiction App · sections: "
            f"{_esc(', '.join(rendered))}</em></p>"]
    for key in rendered:
        body.append(_html_section(*_SECTION_BLOCKS[key](data[key])))
    foot = [f"<p>End of dossier · {len(warnings)} warning(s) · {len(notes)} note(s).</p>"]
    foot += [f'<p class="warn">⚠ {_esc(w)}</p>' for w in warnings]
    foot += [f'<p class="note">ℹ {_esc(n)}</p>' for n in notes]
    body.append("<footer>" + "\n".join(foot) + "</footer>")
    return (f"<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
            f"<title>{_esc(star)} — System Dossier</title>{_HTML_STYLE}</head><body>\n"
            + "\n".join(body) + "\n</body></html>")


# ── assembly ──────────────────────────────────────────────────────────────────

def _assemble_star(star):
    """Run the readers for a real star. Returns {"error"} (hard) or {data, status}.

    `status` maps each section key → (state, reason) where state is "ok" (in data),
    "warn" (source failed/empty), or "note" (by-design). The caller decides which to
    surface based on the requested section set.
    """
    simbad = databases.compute_simbad_lookup(star)
    if "error" in simbad:
        return {"error": simbad["error"]}

    data, status = {}, {}
    data["identity"] = _identity_data_star(simbad)
    status["identity"] = ("ok", None)

    reg = regions.compute_star_system_regions_from_simbad(simbad)
    if "error" in reg:
        status["regions"] = ("warn", reg["error"])
        status["habitable_zone"] = ("warn", "depends on the regions computation (unavailable)")
    else:
        data["regions"] = _regions_data(reg)
        status["regions"] = ("ok", None)
        data["habitable_zone"] = _hz_data(reg)
        status["habitable_zone"] = ("ok", None)

    nasa = databases.compute_planetary_systems_composite(simbad)
    hwc = databases.compute_hwc(simbad)
    nasa_planets = nasa.get("planets") if "error" not in nasa else None
    hwc_planets = hwc.get("planet_rows") if "error" not in hwc else None
    if not nasa_planets and not hwc_planets:
        status["planets"] = ("warn", "no NASA Exoplanet Archive or Habitable Worlds Catalog "
                                     "entry for this star")
    else:
        data["planets"] = _planets_data(nasa_planets, hwc_planets)
        status["planets"] = ("ok", None)

    hyp = databases.compute_hypatia_data(simbad)
    if "error" in hyp or not hyp.get("abundances"):
        reason = hyp.get("error") or "Hypatia Catalog returned no abundances for this star"
        status["hypatia"] = ("warn", reason)
    else:
        data["hypatia"] = _hypatia_data(hyp)
        status["hypatia"] = ("ok", None)

    gcns = simbad.get("gcns")
    if not gcns:
        status["gcns"] = ("warn", "no Gaia id, source not in GCNS, or GCNS table empty")
    else:
        data["gcns"] = _gcns_data(gcns)
        status["gcns"] = ("ok", None)

    return {"data": data, "status": status}


def _assemble_sol():
    """The Sol / Solar System reference-origin path — fully offline (local DB + constants).

    Maps each section to its Sol-special-case source: identity = solar constants, regions/HZ
    = compute_sol_regions, planets = the real Solar System tables, hypatia = the solar
    zero-point baseline. GCNS is N/A for the frame origin → a by-design `note`. The opt-in
    `moons` section is built but only rendered when explicitly requested.
    """
    data, status = {}, {}
    data["identity"] = _identity_data_sol()
    status["identity"] = ("ok", None)

    reg = regions.compute_sol_regions()
    data["regions"] = _regions_data(reg)
    status["regions"] = ("ok", None)
    data["habitable_zone"] = _hz_data(reg)
    status["habitable_zone"] = ("ok", None)

    ss = science.compute_solar_system_tables()
    if ss.get("planets") or ss.get("dwarf_planets") or ss.get("asteroids"):
        data["planets"] = _planets_data_sol(ss)
        status["planets"] = ("ok", None)
    else:
        status["planets"] = ("warn", "Solar System tables are empty — run the Solar System "
                                     "import utility")
    moons = ss.get("moons") or {}
    if moons:
        data["moons"] = moons
        status["moons"] = ("ok", None)
    else:
        status["moons"] = ("warn", "no Solar System moon data")

    # Solar zero-point Hypatia baseline ([X/H] ≡ 0, n=0). Add teff for the properties line.
    hyp = databases._sun_hypatia_baseline()
    hyp = {**hyp, "properties": {**hyp["properties"], "teff": 5778.0}}
    data["hypatia"] = _hypatia_data(hyp)
    status["hypatia"] = ("ok", None)

    status["gcns"] = ("note", "Sol is the reference-frame origin, not a GCNS catalog source "
                              "— section not applicable.")
    return {"data": data, "status": status}


# ── public API ────────────────────────────────────────────────────────────────

def render_document(envelope, fmt):
    """Render a json-format dossier envelope (from build_system_dossier(fmt="json")) to a
    markdown/html `document` string. Lets a caller (the GUI) fetch the structured data once
    and both render the document and build figures from the same envelope. Returns None for
    fmt="json" or an error envelope.
    """
    if fmt == "json" or "error" in envelope:
        return None
    render = _render_html if fmt == "html" else _render_markdown
    return render(envelope["star"], envelope["sections"], envelope["data"],
                  envelope["warnings"], envelope["notes"])


def build_system_dossier(star, sections=None, fmt="markdown"):
    """Compose a full system dossier from the existing readers.

    Pure (no Qt / file I/O / new astronomy). Returns one of:
      - {"star", "fmt", "sections", "warnings", "notes", "document"}  (markdown/html)
      - {"star", "fmt": "json", "sections", "warnings", "notes", "data"}  (json)
      - {"error": str}  (bad fmt/section, or a SIMBAD-lookup failure for a real star)

    `sections` is an optional subset of the section vocabulary (default: all available).
    """
    if fmt not in _FORMATS:
        return {"error": f"unknown format '{fmt}' (valid: {', '.join(sorted(_FORMATS))})"}
    if sections is not None:
        bad = [s for s in sections if s not in _SECTION_ORDER]
        if bad:
            return {"error": f"unknown section '{bad[0]}' "
                             f"(valid: {', '.join(_SECTION_ORDER)})"}
    if not (star or "").strip():
        return {"error": "a star name is required"}

    # Sol / Sun is the reference-frame origin — it doesn't resolve in SIMBAD and its planets
    # are the real Solar System, so route to the offline reference-origin path.
    if (star or "").strip().lower() in {"sol", "sun"}:
        assembled = _assemble_sol()
    else:
        assembled = _assemble_star(star)
        if "error" in assembled:
            return {"error": assembled["error"]}
    data, status = assembled["data"], assembled["status"]
    default_sections = list(_ALL_SECTIONS)

    requested = list(sections) if sections else default_sections
    warnings, notes = [], []
    rendered = []
    for key in _SECTION_ORDER:
        if key not in requested:
            continue
        state, reason = status.get(key, ("warn", "section not applicable to this star"))
        if state == "ok" and key in data:
            rendered.append(key)
        elif state == "note":
            notes.append(f"{key}: {reason}")
        else:
            warnings.append(f"{key}: {reason}")

    if fmt == "json":
        return {"star": star, "fmt": "json", "sections": rendered,
                "warnings": warnings, "notes": notes,
                "data": {k: data[k] for k in rendered}}

    render = _render_html if fmt == "html" else _render_markdown
    document = render(star, rendered, data, warnings, notes)
    return {"star": star, "fmt": fmt, "sections": rendered,
            "warnings": warnings, "notes": notes, "document": document}


# ── Generated-system dossier (Phase S-C2 — the R→Q "Send to Dossier" link) ────
#
# Renders a core.generate.generate_system result dict as a dossier document. Pure
# composition — NO re-analysis, no SIMBAD (a generated/synthetic name like "Gen-88"
# would not resolve, which is exactly why build_system_dossier can't serve these).
# Its own small section vocabulary + a self-contained renderer (it deliberately
# does NOT touch _SECTION_BLOCKS / _render_markdown / _render_html, which are
# guarded byte-identical for build_system_dossier).

_GEN_SECTION_ORDER = ["identity", "star", "planets", "feasibility"]


def _gen_identity_data(result):
    star = result.get("star") or {}
    return {
        "name": star.get("name"),
        "mode": result.get("mode"),
        "seed": result.get("seed"),
        "anchor_star": result.get("anchor_star"),
        "spectral_class": star.get("spectral_class"),
        "source": star.get("source"),
        "grounding": star.get("grounding"),
        "multiplicity": (star.get("multiplicity") or {}).get("note")
        if isinstance(star.get("multiplicity"), dict) else None,
    }


def _gen_star_data(result):
    s = result.get("star") or {}
    return {
        "teff": s.get("teff"), "mass_solar": s.get("mass_solar"),
        "radius_solar": s.get("radius_solar"), "luminosity": s.get("luminosity"),
        "hz_inner_au": s.get("hz_inner_au"), "hz_outer_au": s.get("hz_outer_au"),
        "hz_opt_inner_au": s.get("hz_opt_inner_au"), "hz_opt_outer_au": s.get("hz_opt_outer_au"),
        "snow_line_au": s.get("snow_line_au"),
    }


def _gen_planets_data(result):
    return {"planets": list(result.get("planets") or [])}


def _gen_feasibility_data(result):
    return {"feasible": result.get("feasible"),
            "constraints": list(result.get("constraints") or [])}


def _gen_blocks_identity(d):
    rows = [
        ["Name", d.get("name")],
        ["Mode", d.get("mode")],
        ["Seed", d.get("seed")],
        ["Spectral class", d.get("spectral_class")],
        ["Source", d.get("source")],
        ["Grounding", d.get("grounding")],
    ]
    if d.get("anchor_star"):
        rows.insert(2, ["Anchor star", d["anchor_star"]])
    if d.get("multiplicity"):
        rows.append(["Multiplicity", d["multiplicity"]])
    return "Identity", [("kv", rows)]


def _gen_blocks_star(d):
    rows = [
        ["Effective temperature (K)", _n(d.get("teff"), 1)],
        ["Mass (M☉)", _n(d.get("mass_solar"), 4)],
        ["Radius (R☉)", _n(d.get("radius_solar"), 4)],
        ["Luminosity (L☉)", _n(d.get("luminosity"), 6)],
        ["Conservative HZ (AU)", f"{_n(d.get('hz_inner_au'))} – {_n(d.get('hz_outer_au'))}"],
        ["Optimistic HZ (AU)", f"{_n(d.get('hz_opt_inner_au'))} – {_n(d.get('hz_opt_outer_au'))}"],
        ["Snow line (AU)", _n(d.get("snow_line_au"))],
    ]
    return "Star", [("kv", rows)]


def _gen_blocks_planets(d):
    planets = d.get("planets") or []
    if not planets:
        return "Planets", [("em", "No planets.")]
    headers = ["#", "Name", "a (AU)", "Mass (M⊕)", "Radius (R⊕)", "Type",
               "T_eq (K)", "In HZ", "Source", "Moons"]
    rows = []
    for i, p in enumerate(planets, 1):
        rows.append([
            i, p.get("name"), _n(p.get("a_au")), _n(p.get("mass_earth"), 2),
            _n(p.get("radius_earth"), 2), p.get("type"), _n(p.get("t_eq_k"), 1),
            "Yes" if p.get("in_hz") else "No", p.get("source"),
            len(p.get("moons") or []),
        ])
    return "Planets", [("table", headers, rows)]


def _gen_blocks_feasibility(d):
    blocks = [("strong", "Overall: " + ("feasible" if d.get("feasible") else "not feasible"))]
    cons = d.get("constraints") or []
    if cons:
        headers = ["Constraint", "Type", "Verdict", "Why", "Mechanism"]
        rows = []
        for c in cons:
            l1 = c.get("layer1") or {}
            l2 = c.get("layer2") or {}
            rows.append([c.get("id"), c.get("type"), c.get("verdict"),
                         l1.get("reason"), l2.get("mechanism")])
        blocks.append(("table", headers, rows))
    return "Feasibility", blocks


_GEN_SECTION_BLOCKS = {
    "identity": _gen_blocks_identity,
    "star": _gen_blocks_star,
    "planets": _gen_blocks_planets,
    "feasibility": _gen_blocks_feasibility,
}
_GEN_SECTION_DATA = {
    "identity": _gen_identity_data,
    "star": _gen_star_data,
    "planets": _gen_planets_data,
    "feasibility": _gen_feasibility_data,
}


def _render_generated(star, rendered, data, warnings, notes, fmt):
    if fmt == "html":
        body = [f"<h1>{_esc(star)} — Generated System Dossier</h1>",
                f"<p><em>Generated by Space &amp; Science Fiction App (procedural) · "
                f"sections: {_esc(', '.join(rendered))}</em></p>"]
        for key in rendered:
            body.append(_html_section(*_GEN_SECTION_BLOCKS[key](data[key])))
        foot = [f"<p>End of dossier · {len(warnings)} warning(s) · {len(notes)} note(s).</p>"]
        foot += [f'<p class="warn">⚠ {_esc(w)}</p>' for w in warnings]
        foot += [f'<p class="note">ℹ {_esc(n)}</p>' for n in notes]
        body.append("<footer>" + "\n".join(foot) + "</footer>")
        return (f"<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
                f"<title>{_esc(star)} — Generated System Dossier</title>{_HTML_STYLE}"
                f"</head><body>\n" + "\n".join(body) + "\n</body></html>")
    parts = [f"# {star} — Generated System Dossier",
             "*Generated by Space & Science Fiction App (procedural) · sections: "
             + ", ".join(rendered) + "*"]
    for key in rendered:
        parts.append(_md_section(*_GEN_SECTION_BLOCKS[key](data[key])))
    footer = f"*End of dossier · {len(warnings)} warning(s) · {len(notes)} note(s).*"
    if warnings:
        footer += "\n\n" + "\n".join(f"> ⚠ {w}" for w in warnings)
    if notes:
        footer += "\n\n" + "\n".join(f"> ℹ {n}" for n in notes)
    parts.append(footer)
    return "\n\n".join(parts)


def build_generated_dossier(result, sections=None, fmt="markdown"):
    """Render a ``generate_system`` result dict as a dossier (the R→Q link, S-C2).

    Pure composition over the already-generated dict — no SIMBAD, no re-analysis.
    Returns one of:
      - {"star", "fmt", "mode", "seed", "sections", "warnings", "notes", "document"}  (md/html)
      - {"star", "fmt": "json", "mode", "seed", "sections", "warnings", "notes", "data"}  (json)
      - {"error": str}  (bad fmt/section, or a result that isn't a generated system)

    The ``feasibility`` section is available only when the result carries
    ``constraints`` (Phase R2 feasibility mode); requesting it otherwise drops it
    with a note (never an error). ``sections`` defaults to all available.
    """
    if fmt not in _FORMATS:
        return {"error": f"unknown format '{fmt}' (valid: {', '.join(sorted(_FORMATS))})"}
    if not isinstance(result, dict) or "error" in result:
        return {"error": "not a valid generated-system result"}
    if "star" not in result or "planets" not in result:
        return {"error": "result is not a generate_system output (missing star/planets)"}
    if sections is not None:
        bad = [s for s in sections if s not in _GEN_SECTION_ORDER]
        if bad:
            return {"error": f"unknown section '{bad[0]}' "
                             f"(valid: {', '.join(_GEN_SECTION_ORDER)})"}

    has_feasibility = "constraints" in result
    requested = list(sections) if sections else list(_GEN_SECTION_ORDER)
    warnings = list(result.get("warnings") or [])
    notes = list(result.get("notes") or [])

    rendered = []
    for key in _GEN_SECTION_ORDER:
        if key not in requested:
            continue
        if key == "feasibility" and not has_feasibility:
            notes.append("feasibility: no constraints in this result (nothing to evaluate)")
            continue
        rendered.append(key)

    data = {k: _GEN_SECTION_DATA[k](result) for k in rendered}
    star_name = (result.get("star") or {}).get("name") or "Generated system"

    if fmt == "json":
        return {"star": star_name, "fmt": "json", "mode": result.get("mode"),
                "seed": result.get("seed"), "sections": rendered,
                "warnings": warnings, "notes": notes,
                "data": {k: data[k] for k in rendered}}

    document = _render_generated(star_name, rendered, data, warnings, notes, fmt)
    return {"star": star_name, "fmt": fmt, "mode": result.get("mode"),
            "seed": result.get("seed"), "sections": rendered,
            "warnings": warnings, "notes": notes, "document": document}


# ── Project dossier (Phase S-C5 — fan Q/the generated composer over a project) ─

def _html_inner(doc):
    """Return the <body> contents of a self-contained dossier HTML doc (for merging)."""
    lo = doc.find("<body>")
    hi = doc.rfind("</body>")
    if lo != -1 and hi != -1:
        return doc[lo + len("<body>"):hi].strip()
    return doc


def _member_dossier(member, sections, fmt):
    """Render one project member: real → build_system_dossier; generated →
    re-run generate_system(spec) → build_generated_dossier. (`sections` is the Q
    vocabulary, applied to real members only; generated members render in full.)"""
    if member.get("source") == "generated":
        from core.generate import generate_from_spec   # function-local (one-way dep)
        spec = member.get("generated_spec") or {"seed": member.get("generated_seed")}
        res = generate_from_spec(spec)
        if isinstance(res, dict) and "error" in res:
            return {"error": res["error"]}
        return build_generated_dossier(res, fmt=fmt)
    return build_system_dossier(member["star_name"], sections=sections, fmt=fmt)


def build_project_dossier(project_name, sections=None, fmt="markdown", combined=True):
    """Compose a whole project workspace as a dossier (the Phase S export fan-out).

    Real members → Q's ``build_system_dossier``; generated members → the R→Q
    ``build_generated_dossier`` (re-created from the stored spec). Returns:
      - combined md/html: {project, fmt, combined:True, members:[{star_name, source,
        ok}], document, warnings}
      - combined json:    {project, fmt:"json", combined:True, members:[...], data}
      - per-file (any fmt): {project, fmt, combined:False, members:[{star_name,
        source, ok, document|data|error}], warnings}
      - {"error": str} for an unknown project / bad fmt.
    A per-member failure is isolated (that member ``ok=False`` + its error + a
    top-level warning); it never aborts the export. ``sections`` is the Q vocabulary
    (real members); generated members always render in full.
    """
    if fmt not in _FORMATS:
        return {"error": f"unknown format '{fmt}' (valid: {', '.join(sorted(_FORMATS))})"}
    from core.projects import get_project            # function-local (one-way dep)
    proj = get_project(project_name)
    if "error" in proj:
        return proj
    name = proj["project"]["name"]
    desc = proj["project"].get("description") or ""

    rendered, warnings = [], []
    for m in proj["members"]:
        r = _member_dossier(m, sections, fmt)
        entry = {"star_name": m["star_name"], "source": m.get("source")}
        if isinstance(r, dict) and "error" in r:
            entry["ok"] = False
            entry["error"] = r["error"]
            warnings.append(f"{m['star_name']}: {r['error']}")
        else:
            entry["ok"] = True
            entry["result"] = r
        rendered.append(entry)

    ok = [e for e in rendered if e["ok"]]

    if not combined:
        members = []
        for e in rendered:
            row = {"star_name": e["star_name"], "source": e["source"], "ok": e["ok"]}
            if not e["ok"]:
                row["error"] = e["error"]
            elif fmt == "json":
                row["data"] = e["result"].get("data")
            else:
                row["document"] = e["result"].get("document")
            members.append(row)
        return {"project": name, "fmt": fmt, "combined": False,
                "members": members, "warnings": warnings}

    # combined
    member_summ = [{"star_name": e["star_name"], "source": e["source"], "ok": e["ok"]}
                   for e in rendered]
    if fmt == "json":
        data = {"project": proj["project"],
                "members": [{"star_name": e["star_name"], "source": e["source"],
                             "data": e["result"].get("data")} for e in ok]}
        return {"project": name, "fmt": "json", "combined": True,
                "members": member_summ, "warnings": warnings, "data": data}

    if fmt == "html":
        parts = [f"<h1>{_esc(name)} — Project Dossier</h1>"]
        if desc:
            parts.append(f"<p><em>{_esc(desc)}</em></p>")
        parts.append(f"<p>{len(ok)} of {len(rendered)} system(s).</p>")
        for e in ok:
            parts.append("<hr>")
            parts.append(_html_inner(e["result"]["document"]))
        if warnings:
            parts.append("<hr>")
            parts += [f'<p class="warn">⚠ {_esc(w)}</p>' for w in warnings]
        document = (f"<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
                    f"<title>{_esc(name)} — Project Dossier</title>{_HTML_STYLE}"
                    f"</head><body>\n" + "\n".join(parts) + "\n</body></html>")
    else:  # markdown
        parts = [f"# {name} — Project Dossier"]
        if desc:
            parts.append(f"*{desc}*")
        parts.append(f"*{len(ok)} of {len(rendered)} system(s).*")
        for e in ok:
            parts.append("---")
            parts.append(e["result"]["document"])
        if warnings:
            parts.append("---")
            parts += [f"> ⚠ {w}" for w in warnings]
        document = "\n\n".join(parts)

    return {"project": name, "fmt": fmt, "combined": True,
            "members": member_summ, "warnings": warnings, "document": document}
