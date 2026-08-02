# gui/panels/oec_detail.py — the OEC System View detail pane (OEC_SYSTEM_VIEW_PLAN
# Stage 2: §B.6 field registry + per-tag section builders).
#
# Two layers:
#   * `detail_model(node, ctx)` — a pure, Qt-free description of what the pane
#     shows: title, badges, and an ordered list of {title, rows} sections. Tests
#     assert on this (T6: registry ∪ fallback covers every walker key, per tag).
#   * `build_detail_pane(node, ctx)` — renders that model into a QWidget.
#
# Two contracts this module exists to keep:
#   1. **No catalogued field can go missing.** Every tag's registry is followed by
#      an alphabetical "Other catalogued fields" fallback, so a field OEC adds
#      tomorrow shows up tomorrow rather than being silently dropped (T6 / V2).
#   2. **One node's failure must not blank the pane.** Every section is built
#      inside its own try/except that routes to `log_viz_error` (T18).
#
# It also owns the shared OEC value formatting (`oec_value_cell` and friends) —
# `gui/panels/catalogs.py` imports them from here, so the tree and the pane can
# never render the same field two different ways.

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QFrame, QPushButton,
)
from PySide6.QtCore import Qt

from core.databases import (oec_fv as _fv, oec_statuses as _statuses,
                            oec_binary_label as _binary_label)
from core.shared import M_JUP_EARTH, R_JUP_EARTH
from gui.visualizations.plot_helpers import log_viz_error

OEC_PREFIX = {"system": "◆", "binary": "⋔", "star": "★",
              "planet": "●", "satellite": "☾"}


# ── Value formatting (shared with the tree) ──────────────────────────────────

def oec_num(field):
    """Numeric value of a (possibly repeated) OEC field, or None."""
    fv = _fv(field)
    if fv is None:
        return None
    try:
        return float(fv.get("value"))
    except (TypeError, ValueError):
        return None


def _g(v):
    return f"{v:.4g}"


def oec_value_cell(field, unit="", factor=1.0, show_errors=True, repeats=False):
    """One rendered value from a (possibly repeated / bound-only / errored) field.

    With ``factor == 1.0`` the catalogue's own strings are used verbatim (no
    rounding drift, matching the historical `oec_format_field` rendering); a
    non-unity factor converts numerically (planet M♃→M⊕, R♃→R⊕ under D1).

    ``repeats=True`` renders **every** value of a repeated field, joined by ' · '
    — a binary's `separation` is catalogued twice (AU *and* arcsec), so
    first-value-only silently drops half of it. The tree stays first-only (column
    width); the pane and the tooltip pass ``repeats=True``."""
    if repeats and isinstance(field, list) and len(field) > 1:
        rendered = [oec_value_cell(one, unit, factor, show_errors) for one in field]
        return " · ".join(r for r in rendered if r)
    fv = _fv(field)
    if fv is None:
        return ""

    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    def conv(x):
        n = num(x)
        if n is None:
            return None
        return str(x) if factor == 1.0 else _g(n * factor)

    raw = fv.get("value", "")
    v = conv(raw)
    if v is None and raw:                       # non-numeric text (spectral type…)
        return f"{raw} {unit}".strip() if unit else str(raw)

    parts = [v] if v is not None else []
    if v is not None and show_errors:
        em, ep = conv(fv.get("errorminus")), conv(fv.get("errorplus"))
        if em is not None or ep is not None:
            # Symmetry is a NUMERIC question: 997 real fields carry textually
            # different but equal bounds ("0.06" vs "0.060"), which a string
            # comparison renders as the misleading "+0.060/-0.06".
            symmetric = (num(fv.get("errorminus")) is not None
                         and num(fv.get("errorminus")) == num(fv.get("errorplus")))
            parts.append(f"±{ep}" if symmetric else f"+{ep or 0}/-{em or 0}")
    ul, ll = conv(fv.get("upperlimit")), conv(fv.get("lowerlimit"))
    if v is None:                               # bound-only: value is in the attribute
        if ul is not None:
            parts.append(f"<= {ul}")
        elif ll is not None:
            parts.append(f">= {ll}")
    else:
        if ul is not None:
            parts.append(f"(<= {ul})")
        elif ll is not None:
            parts.append(f"(>= {ll})")
    if not parts:
        return ""
    s = " ".join(parts)
    u = (fv.get("unit") or unit) if factor == 1.0 else unit
    return f"{s} {u}" if u else s


def oec_planet_units(node, mode="auto"):
    """(mass_factor, mass_unit, radius_factor, radius_unit) for a planet node.

    D1: **Auto** picks M⊕/R⊕ below 0.1 M♃, else M♃/R♃ — decided **per node**, from
    the mass when catalogued and from the radius (< 0.4 R♃, the sub-Neptune
    boundary) when it is not."""
    if mode == "earth":
        earth = True
    elif mode == "jupiter":
        earth = False
    else:
        m = oec_num(node["fields"].get("mass"))
        r = oec_num(node["fields"].get("radius"))
        earth = (m < 0.1) if m is not None else (r is not None and r < 0.4)
    if earth:
        return (M_JUP_EARTH, "M⊕", R_JUP_EARTH, "R⊕")
    return (1.0, "M♃", 1.0, "R♃")


def oec_mass_label(node):
    """'M·sin i' when the catalogued planet mass is an msini value, else 'Mass'."""
    fv = _fv(node["fields"].get("mass"))
    return "M·sin i" if (fv and fv.get("type") == "msini") else "Mass"


def oec_node_title(node):
    """Display name for a node (a binary's label is synthesized when unnamed)."""
    tag = node.get("tag")
    if node.get("names"):
        return node["names"][0]
    if tag == "binary":
        return _binary_label(node)
    return {"system": "System", "star": "Star",
            "planet": "Planet", "satellite": "Moon"}.get(tag, "Node")


# ── The field registry (§B.6) ────────────────────────────────────────────────
#
# One table per tag: (section title, [(field key, label, unit)]). Keys absent from
# a node are skipped; keys absent from the registry land in the alphabetical
# "Other catalogued fields" fallback, so nothing can go missing.
#
# `@mass` / `@radius` are resolved per node against the D1 units mode.
#
# NAME COLLISION (§B.6, T17): OEC's `periastron` is the **argument of periastron
# in degrees** (tau Cet g = 395.3), NOT a distance. It is labelled as such here,
# and the derived periastron *distance* uses the non-colliding key
# `peri_distance_au`. Do not "fix" the label to AU.

_ANGLE = "°"
_ORBIT_COMMON = [
    ("period", "Period", "d"),
    ("semimajoraxis", "Semi-major axis", "AU"),
    ("eccentricity", "Eccentricity", ""),
    ("inclination", "Inclination", _ANGLE),
    ("periastron", "Argument of periastron", _ANGLE),
    ("ascendingnode", "Ascending node", _ANGLE),
    ("longitude", "Mean longitude", _ANGLE),
    ("meananomaly", "Mean anomaly", _ANGLE),
    ("periastrontime", "Periastron time", "BJD"),
    ("transittime", "Transit time", "BJD"),
    ("positionangle", "Position angle", _ANGLE),
    ("separation", "Separation", ""),
]
_PHOTOMETRY = [(f"mag{b}", f"{b} magnitude", "mag")
               for b in ("U", "B", "V", "R", "I", "J", "H", "K")]

_REGISTRY = {
    "system": [
        ("Position & distance", [
            ("rightascension", "Right ascension", ""),
            ("declination", "Declination", ""),
            ("constellation", "Constellation", ""),
            ("distance", "Distance", "pc"),
        ]),
        ("Photometry", _PHOTOMETRY),
    ],
    "binary": [
        ("Orbit", _ORBIT_COMMON),
        ("Photometry", _PHOTOMETRY),
    ],
    "star": [
        ("Physical", [
            ("spectraltype", "Spectral type", ""),
            ("mass", "Mass", "M☉"),
            ("radius", "Radius", "R☉"),
            ("temperature", "Effective temperature", "K"),
            ("metallicity", "Metallicity [Fe/H]", "dex"),
            ("age", "Age", "Gyr"),
        ]),
        ("Photometry", _PHOTOMETRY),
    ],
    "planet": [
        ("Physical", [
            ("mass", "@mass", "@mass"),
            ("radius", "Radius", "@radius"),
            ("temperature", "Equilibrium temperature", "K"),
            ("spectraltype", "Spectral type", ""),
            ("metallicity", "Metallicity [Fe/H]", "dex"),
            ("age", "Age", "Gyr"),
        ]),
        ("Orbit", _ORBIT_COMMON + [
            ("impactparameter", "Impact parameter", ""),
            ("spinorbitalignment", "Spin-orbit alignment", _ANGLE),
            ("tilt", "Axial tilt", _ANGLE),
            ("maximumrvtime", "Maximum RV time", "BJD"),
        ]),
        ("Discovery", [
            ("discoverymethod", "Discovery method", ""),
            ("discoveryyear", "Discovery year", ""),
            ("istransiting", "Transiting", ""),
            ("lastupdate", "Last update", ""),
            ("new", "New this release", ""),
        ]),
        ("Photometry", _PHOTOMETRY),
    ],
    "satellite": [
        ("Physical", [
            ("mass", "Mass", "M⊕"),
            ("radius", "Radius", "R⊕"),
        ]),
        ("Orbit", _ORBIT_COMMON + [("tilt", "Axial tilt", _ANGLE)]),
    ],
}

# Rendered elsewhere (badges / the description block), never as a plain row.
_HANDLED_ELSEWHERE = {"list", "description", "imagedescription", "image"}


def _humanise(key):
    return key[:1].upper() + key[1:] if key else key


def _row(label, value, derived=False, tip=None):
    """One pane row. `derived` drives the violet + badge treatment (D3) and the
    single Derived toggle; `tip` carries a derived value's `source` (§D.4 rule 3)."""
    return {"label": label, "value": value, "derived": derived, "tip": tip}


def _derived_rows(entries, keys, ctx):
    """Render `core.oec_derived` entries as rows. A value that could not be
    computed still shows, carrying its stated reason (§D.4 rule 2) — never a
    silent omission and never a zero."""
    if not ctx.get("derived", True):
        return []
    rows = []
    for key, label, fmt in keys:
        entry = entries.get(key)
        if entry is None:
            continue
        if entry.get("value") is None:
            rows.append(_row(label, f"— ({entry.get('reason') or 'not available'})",
                             derived=True, tip=entry.get("source")))
            continue
        text = fmt(entry["value"], entry.get("unit") or "")
        # `reason` alongside a value is a QUALIFIER, not an absence — it must be
        # shown, or a caveated number reads as an uncaveated one.
        if entry.get("reason"):
            text = f"{text} — {entry['reason']}"
        rows.append(_row(label, text, derived=True, tip=entry.get("source")))
    return rows


def _fmt_scalar(value, unit):
    return f"{value:.4g} {unit}".strip()


def _fmt_ms_lifetime(value, unit):
    """A main-sequence lifetime past a Hubble time is a bound, not a figure."""
    from core.oec_derived import HUBBLE_GYR
    if value is not None and value > HUBBLE_GYR:
        return f"> {HUBBLE_GYR:g} {unit}".strip()
    return _fmt_scalar(value, unit)


def _registry_section(node, ctx, spec):
    """Rows for one registry section — the generic builder. Raising here is what
    T18 exercises; `detail_model` catches it per section."""
    fields = node.get("fields", {}) or {}
    errs = ctx.get("errors", True)
    mf, mu, rf, ru = (1.0, "", 1.0, "")
    if node.get("tag") == "planet":
        mf, mu, rf, ru = oec_planet_units(node, ctx.get("units", "auto"))
    rows = []
    for key, label, unit in spec:
        if key not in fields:
            continue
        factor = 1.0
        if unit == "@mass":
            factor, unit = mf, mu
        elif unit == "@radius":
            factor, unit = rf, ru
        if label == "@mass":
            label = oec_mass_label(node)
        text = oec_value_cell(fields[key], unit, factor, show_errors=errs, repeats=True)
        if text:
            rows.append(_row(label, text))
    return rows


def _identity_section(node, ctx):
    """All `<name>` aliases — a star can carry 22 (T4); today's tree shows one."""
    names = node.get("names") or []
    if not names:
        return []
    rows = [_row("Name", names[0])]
    if len(names) > 1:
        rows.append(_row(f"Aliases ({len(names) - 1})", " · ".join(names[1:])))
    return rows


def _description_section(node, ctx):
    """The planet `description` free text (93.2% coverage) — visible nowhere today
    — plus the artwork URL. `image` is in `_HANDLED_ELSEWHERE`, so if it were not
    rendered here it would be dropped from the fallback too and vanish entirely
    (97 planets carry one). Fetching the artwork is a follow-up (§K); the URL is
    shown as text."""
    rows = []
    for key, label in (("description", "Description"),
                       ("imagedescription", "Image description"),
                       ("image", "Image URL")):
        txt = oec_value_cell((node.get("fields") or {}).get(key), repeats=True)
        if txt:
            rows.append(_row(label, txt))
    return rows


# ── Context: the parent chain a star dossier needs (Stage 3) ─────────────────
#
# A star's position, distance and constellation live on the SYSTEM node, and its
# companions live on the PARENT BINARY — neither is reachable from the star node
# alone, which is why the model takes a context rather than just a node.

def build_context(system, **extra):
    """Parent map + system root for one resolved OEC system."""
    parents = {}

    def walk(n):
        for c in n.get("children", []):
            parents[id(c)] = n
            walk(c)

    walk(system)
    ctx = {"system": system, "parents": parents}
    ctx.update(extra)
    return ctx


def _parent_of(node, ctx):
    return (ctx.get("parents") or {}).get(id(node))


def _ancestors(node, ctx):
    out, cur = [], _parent_of(node, ctx)
    while cur is not None:
        out.append(cur)
        cur = _parent_of(cur, ctx)
    return out


def _count_stars(node):
    return ((1 if node.get("tag") == "star" else 0)
            + sum(_count_stars(c) for c in node.get("children", [])))


def _star_label(star, ctx):
    """'Alpha Centauri A (G2 V, 1.100 M☉)' — a companion in one line."""
    name = oec_node_title(star)
    bits = []
    sp = oec_value_cell((star.get("fields") or {}).get("spectraltype"))
    if sp:
        bits.append(sp)
    m = oec_value_cell((star.get("fields") or {}).get("mass"), "M☉", show_errors=False)
    if m:
        bits.append(m)
    return f"{name} ({', '.join(bits)})" if bits else name


# ── Star dossier sections (Stage 3) ──────────────────────────────────────────

def _position_section(node, ctx):
    """RA / Dec / constellation / distance — catalogued on the system node
    (99.98% coverage; the Sun's row has neither RA nor Dec), so they are labelled
    as coming from the system record rather than silently attributed to the star."""
    system = ctx.get("system")
    if system is None:
        return []
    rows = _registry_section(system, ctx, _REGISTRY["system"][0][1])
    if rows and node.get("tag") == "star" and _count_stars(system) > 1:
        # In a multiple system these are the SYSTEM's coordinates, shared by every
        # component — say so rather than let them read as this star's own.
        rows.append(_row("Recorded on", "the system as a whole (shared by all components)"))
    rows += _derived_rows(ctx.get("derived_values", {}),
                          [("light_years", "Distance (light years)", _fmt_scalar),
                           ("parallax_mas", "Parallax", _fmt_scalar),
                           ("angular_diameter_mas", "Angular diameter", _fmt_scalar)],
                          ctx)
    return rows


def _star_physical_section(node, ctx):
    rows = _registry_section(node, ctx, _REGISTRY["star"][0][1])
    rows += _derived_rows(ctx.get("derived_values", {}),
                          [("luminosity_lsun", "Luminosity", _fmt_scalar),
                           ("log_g", "Surface gravity log g", _fmt_scalar),
                           ("mean_density_gcc", "Mean density", _fmt_scalar),
                           ("ms_lifetime_gyr", "Main-sequence lifetime",
                            _fmt_ms_lifetime),
                           ("stage", "Evolutionary stage",
                            lambda v, u: str(v))],
                          ctx)
    return rows


def _star_photometry_section(node, ctx):
    rows = _registry_section(node, ctx, _REGISTRY["star"][1][1])
    rows += _derived_rows(ctx.get("derived_values", {}),
                          [("b_minus_v", "B−V", _fmt_scalar),
                           ("v_minus_k", "V−K", _fmt_scalar),
                           ("abs_mag_v", "Absolute magnitude M_V", _fmt_scalar)],
                          ctx)
    return rows


def _hz_section(node, ctx):
    """Kopparapu bounds + (Stage 4a) the ice lines and the hyper limit. Numeric
    here for the first time — they exist today only as rings in the HZ tab."""
    entries = ctx.get("derived_values", {})
    if not ctx.get("derived", True):
        return []
    rows = []
    hz = entries.get("hz_bounds")
    if hz is not None:
        if hz.get("value") is None:
            rows.append(_row("Habitable zone",
                             f"— ({hz.get('reason') or 'not available'})",
                             derived=True, tip=hz.get("source")))
        else:
            v = hz["value"]
            rows.append(_row("Conservative HZ",
                             f"{v['conservative_inner_au']:.3g} – "
                             f"{v['conservative_outer_au']:.3g} AU",
                             derived=True, tip=hz.get("source")))
            rows.append(_row("Optimistic HZ",
                             f"{v['optimistic_inner_au']:.3g} – "
                             f"{v['optimistic_outer_au']:.3g} AU",
                             derived=True, tip=hz.get("source")))
    ice = entries.get("ice_lines")
    if ice is not None:
        if ice.get("value") is None:
            rows.append(_row("Ice lines", f"— ({ice.get('reason')})",
                             derived=True, tip=ice.get("source")))
        else:
            for line in ice["value"]:
                # `species` already reads as a label ("Water snow line",
                # "NH₃ front") — don't append a second noun to it.
                label = str(line.get("species") or "Ice line")
                note = " (disk-set)" if line.get("disk_line") else ""
                rows.append(_row(label,
                                 f"{line['au']:.3g} AU"
                                 f" ({line['t_cond_k']:.0f} K){note}",
                                 derived=True, tip=ice.get("source")))
    rows += _derived_rows(entries,
                          [("hyper_limit_au", "Honorverse hyper limit (fiction)",
                            _fmt_scalar)],
                          ctx)
    return rows


def _circumbinary_hz_section(node, ctx):
    """The P-type HZ from the pair's combined light (D9).

    D9 also requires a visible note that the panel's **HZ Diagram** tab still uses
    the primary component's light alone — a silent disagreement between two tabs
    of one panel is worse than either behaviour on its own."""
    if not ctx.get("derived", True):
        return []
    entry = (ctx.get("derived_values") or {}).get("hz_circumbinary")
    if entry is None:
        return []
    if entry.get("value") is None:
        return [_row("Circumbinary HZ", f"— ({entry.get('reason')})",
                     derived=True, tip=entry.get("source"))]
    v = entry["value"]
    rows = [
        _row("Combined luminosity", f"{v['combined_lum']:.4g} L☉",
             derived=True, tip=entry.get("source")),
        _row("Effective Teff", f"{v['eff_teff']:.0f} K",
             derived=True, tip=entry.get("source")),
        _row("Conservative HZ",
             f"{v['conservative_inner_au']:.3g} – {v['conservative_outer_au']:.3g} AU",
             derived=True, tip=entry.get("source")),
        _row("Optimistic HZ",
             f"{v['optimistic_inner_au']:.3g} – {v['optimistic_outer_au']:.3g} AU",
             derived=True, tip=entry.get("source")),
        _row("Note", "Computed from the COMBINED light of both components. The "
                     "panel's HZ Diagram tab still uses the primary component's "
                     "light alone, so the two will not agree."),
    ]
    return rows


def _planets_hosted_section(node, ctx):
    planets = [c for c in node.get("children", []) if c.get("tag") == "planet"]
    if not planets:
        return [_row("Planets", "No planets catalogued for this star.")]
    rows = []
    for p in planets:
        mf, mu, _, _ = oec_planet_units(p, ctx.get("units", "auto"))
        f = p.get("fields", {}) or {}
        bits = []
        m = oec_value_cell(f.get("mass"), mu, mf, show_errors=False)
        if m:
            bits.append(f"{oec_mass_label(p)} {m}")
        per = oec_value_cell(f.get("period"), "d", show_errors=False)
        if per:
            bits.append(f"P {per}")
        a = oec_value_cell(f.get("semimajoraxis"), "AU", show_errors=False)
        if a:
            bits.append(f"a {a}")
        statuses = _statuses(f)
        if statuses:
            bits.append(" / ".join(statuses))
        rows.append(_row(oec_node_title(p),
                         " · ".join(bits) or "no catalogued parameters"))
    return rows


def _companions_section(node, ctx):
    """The parent `<binary>`'s orbital elements, restated from this star's point of
    view — today they live only on the binary's own tree row. A single star gets
    one honest line rather than an empty section (T5)."""
    parent = _parent_of(node, ctx)
    if parent is None or parent.get("tag") != "binary":
        return [_row("Hierarchy", "No catalogued companion (single, or unresolved).")]
    rows = [_row("Parent", f"{OEC_PREFIX['binary']} {oec_node_title(parent)}")]
    for sib in parent.get("children", []):
        if sib is node:
            continue
        if sib.get("tag") == "star":
            rows.append(_row("Companion", f"{OEC_PREFIX['star']} {_star_label(sib, ctx)}"))
        elif sib.get("tag") == "binary":
            rows.append(_row("Companion", f"{OEC_PREFIX['binary']} {oec_node_title(sib)}"))
    rows += _registry_section(parent, ctx, _REGISTRY["binary"][0][1])
    # These three describe the PAIR, so they come from the parent's derived entry
    # — reading them off this star's would silently render nothing.
    rows += _derived_rows(ctx.get("parent_derived", {}),
                          [("mass_ratio", "Mass ratio μ", _fmt_scalar),
                           ("stype_critical_au", "S-type critical SMA", _fmt_scalar),
                           ("ptype_critical_au", "P-type critical SMA", _fmt_scalar)],
                          ctx)
    wider = [a for a in _ancestors(node, ctx)[1:] if a.get("tag") == "binary"]
    for w in wider:
        sep = oec_value_cell((w.get("fields") or {}).get("separation"),
                             show_errors=False, repeats=True)
        rows.append(_row("Wider hierarchy",
                         f"{OEC_PREFIX['binary']} {oec_node_title(w)}"
                         + (f" — separation {sep}" if sep else "")))
    return rows


# Catalogue designations OEC carries in its <name> tags, and what each unlocks
# elsewhere in the app.
_XREF_PATTERNS = [
    ("HD", r"^HD\s*\d"), ("HIP", r"^HIP\s*\d"), ("HR", r"^HR\s*\d"),
    ("GJ / Gliese", r"^(?:GJ|Gliese|GI)\s*[\d.]"), ("2MASS", r"^2MASS\s"),
    ("Gaia", r"^Gaia\s"), ("TYC", r"^TYC\s"), ("TIC", r"^TIC\s"),
    ("KOI", r"^KOI[-\s]"), ("Kepler", r"^Kepler[-\s]"), ("WISE", r"^WISE\s"),
]


def oec_star_xrefs(node):
    """[(catalogue, designation)] for a star, from its OEC names."""
    import re
    out = []
    for label, pat in _XREF_PATTERNS:
        hit = next((n for n in node.get("names", []) if re.match(pat, n, re.I)), None)
        if hit:
            out.append((label, hit))
    return out


def _xref_section(node, ctx):
    xrefs = oec_star_xrefs(node)
    if not xrefs:
        return [_row("Cross-references",
                     "No catalogue designation (HD / HIP / GJ / HR) — a SIMBAD, "
                     "Hypatia or GCNS lookup cannot be resolved for this star.")]
    return [_row(label, desig) for label, desig in xrefs]


# ── Binary / system / satellite section sets (Stage 3b) ──────────────────────

def _child_label(child, ctx):
    tag = child.get("tag")
    if tag == "star":
        return f"{OEC_PREFIX['star']} {_star_label(child, ctx)}"
    if tag == "binary":
        return f"{OEC_PREFIX['binary']} {oec_node_title(child)}"
    statuses = _statuses(child.get("fields", {}) or {})
    label = f"{OEC_PREFIX.get(tag, '')} {oec_node_title(child)}"
    return f"{label} — {' / '.join(statuses)}" if statuses else label


def _components_section(node, ctx):
    """The binary's own components, named — the tree shows them as child rows but
    the pane must stand alone (it is also what the map's ◆ click opens)."""
    rows = [_row("Component", _child_label(c, ctx))
            for c in node.get("children", []) if c.get("tag") in ("star", "binary")]
    planets = [c for c in node.get("children", []) if c.get("tag") == "planet"]
    for p in planets:
        # Direct planet children of a <binary> are circumbinary (P-type).
        rows.append(_row("Circumbinary planet", _child_label(p, ctx)))
    return rows or [_row("Components", "No catalogued components.")]


def _contents_section(node, ctx):
    """What the system holds — the census the tree makes you count by eye."""
    stars = _count_stars(node)
    planets, satellites, binaries = 0, 0, 0

    def walk(n):
        nonlocal planets, satellites, binaries
        for c in n.get("children", []):
            tag = c.get("tag")
            planets += tag == "planet"
            satellites += tag == "satellite"
            binaries += tag == "binary"
            walk(c)

    walk(node)
    rows = [_row("Stars", str(stars)), _row("Planets", str(planets))]
    if satellites:
        rows.append(_row("Satellites", str(satellites)))
    if binaries:
        rows.append(_row("Binary sub-systems", str(binaries)))
    if not planets:
        rows.append(_row("Note", "OEC lists only systems with planets or "
                                 "candidates; this one has none catalogued."))
    rows += _derived_rows(ctx.get("derived_values", {}),
                          [("topology", "Topology", lambda v, u: str(v))], ctx)
    rows += [_row("Top-level component", _child_label(c, ctx))
             for c in node.get("children", []) if c.get("tag") != "satellite"]
    return rows


def _satellite_parent_section(node, ctx):
    """A moon's host planet and, through it, its star — neither is on the moon."""
    parent = _parent_of(node, ctx)
    if parent is None:
        return [_row("Parent", "Host planet not resolved.")]
    rows = [_row("Host planet", _child_label(parent, ctx))]
    star = next((a for a in _ancestors(parent, ctx) if a.get("tag") == "star"), None)
    if star is not None:
        rows.append(_row("Host star", f"{OEC_PREFIX['star']} {_star_label(star, ctx)}"))
    return rows


_STAR_SECTIONS = [
    ("Identity", _identity_section),
    ("Position & distance", _position_section),
    ("Physical", _star_physical_section),
    ("Photometry", _star_photometry_section),
    ("Habitable zone & ice lines", _hz_section),
    ("Planets hosted", _planets_hosted_section),
    ("Companions & hierarchy", _companions_section),
    ("Cross-references", _xref_section),
]
# The eight blocks T15 asserts on. Named here so the test and the builder cannot
# drift apart.
STAR_DOSSIER_BLOCKS = [title for title, _ in _STAR_SECTIONS]


# Custom sections inserted after Identity, per tag (Stage 3b). The registry
# sections for that tag follow, then Description and the fallback.
def _planet_derived_section(node, ctx):
    """Everything the derived layer can say about a planet (Stage 4b), grouped
    after the catalogued blocks so the two are never interleaved."""
    entries = ctx.get("derived_values") or {}
    if not entries or not ctx.get("derived", True):
        return []
    rows = []
    sma = entries.get("sma_au")
    if sma is not None:
        if sma.get("value") is None:
            rows.append(_row("Semi-major axis", f"— ({sma['reason']})",
                             derived=True, tip=sma.get("source")))
        elif sma.get("source") != "catalogued":
            # Only worth a row when it was RECOVERED; a catalogued `a` is already
            # in the Orbit block and must not be restated as a derived value.
            rows.append(_row("Semi-major axis (recovered)",
                             f"{sma['value']:.4g} AU", derived=True,
                             tip=sma.get("source")))
    rows += _derived_rows(entries, [
        ("insolation_searth", "Insolation", _fmt_scalar),
        ("hz_verdict", "Habitable-zone verdict", lambda v, u: str(v)),
        ("peri_distance_au", "Periastron distance", _fmt_scalar),
        ("apo_distance_au", "Apastron distance", _fmt_scalar),
        ("density_gcc", "Mean density", _fmt_scalar),
        ("surface_gravity_g", "Surface gravity", _fmt_scalar),
        ("escape_velocity_kms", "Escape velocity", _fmt_scalar),
        ("rv_semi_amplitude_ms", "RV semi-amplitude K", _fmt_scalar),
        ("transit_depth_ppm", "Transit depth", _fmt_scalar),
        ("transit_prob", "Transit probability", _fmt_fraction),
        ("hill_radius_au", "Hill radius", _fmt_scalar),
        ("moon_limit_au", "Largest stable moon orbit", _fmt_scalar),
    ], ctx)
    retention = entries.get("retention")
    if retention is not None:
        if retention.get("value") is None:
            rows.append(_row("Atmospheric retention", f"— ({retention['reason']})",
                             derived=True, tip=retention.get("source")))
        else:
            kept = [g["gas"] for g in retention["value"] if g["status"] == "Retained"]
            lost = [g["gas"] for g in retention["value"]
                    if g["status"] == "Lost rapidly"]
            rows.append(_row("Gases retained", ", ".join(kept) or "none",
                             derived=True, tip=retention.get("source")))
            rows.append(_row("Gases lost rapidly", ", ".join(lost) or "none",
                             derived=True, tip=retention.get("source")))
    return rows


def _fmt_fraction(value, unit):
    return f"{value * 100:.3g}%"


def oec_hz_short(verdict):
    """`compute_habitable_zone_sma`'s verdict is a sentence; the tree column needs
    a token. Matches on the zone words, and falls back to the RAW verdict rather
    than to an empty cell, so a reworded verdict shows up as odd text instead of
    silently vanishing."""
    if not verdict:
        return ""
    v = str(verdict)
    if "NOT" in v and "Interior" in v:
        return "interior"
    if "NOT" in v and "Beyond" in v:
        return "beyond"
    if "Conservative" in v:
        return "conservative"
    if "Optimistic" in v:
        return "optimistic"
    return v


def _binary_stability_section(node, ctx):
    """Where planets can survive around this pair (Holman & Wiegert 1999) — S-type
    inside `stype_critical_au` of one component, P-type outside `ptype_critical_au`
    of the barycenter."""
    rows = _derived_rows(ctx.get("derived_values", {}),
                         [("mass_ratio", "Mass ratio μ", _fmt_scalar),
                          ("stype_critical_au", "S-type critical SMA", _fmt_scalar),
                          ("ptype_critical_au", "P-type critical SMA", _fmt_scalar)],
                         ctx)
    if rows and any(r["value"] and not r["value"].startswith("—") for r in rows):
        rows.append(_row("Reading", "S-type planets are stable INSIDE the S-type "
                                    "radius of one star; P-type (circumbinary) "
                                    "planets OUTSIDE the P-type radius."))
    return rows


_EXTRA_SECTIONS = {
    "binary": [("Components", _components_section),
               ("Habitable zone (circumbinary)", _circumbinary_hz_section),
               ("Planet stability", _binary_stability_section)],
    "system": [("Contents", _contents_section)],
    "satellite": [("Parent", _satellite_parent_section)],
}


def _section_plan(node, ctx):
    """Ordered (title, builder) list for a node's tag."""
    tag = node.get("tag")
    consumed = set(_HANDLED_ELSEWHERE)
    for _, spec in _REGISTRY.get(tag, []):
        consumed.update(k for k, _, _ in spec)

    if tag == "star":
        # Description is appended for EVERY tag, star included. `consumed` is
        # seeded from `_HANDLED_ELSEWHERE` for all tags, so a tag whose plan omits
        # this section would drop `description`/`image`/`imagedescription` from the
        # fallback *and* render them nowhere — silently, with no test failure.
        # Latent today (those keys appear only on planets) but exactly the failure
        # the module's contract #1 exists to prevent.
        return list(_STAR_SECTIONS) + [("Description", _description_section)], consumed

    plan = [("Identity", _identity_section)]
    plan += _EXTRA_SECTIONS.get(tag, [])
    for title, spec in _REGISTRY.get(tag, []):
        plan.append((title, lambda n, c, s=spec: _registry_section(n, c, s)))
    if tag == "planet":
        plan.append(("Derived", _planet_derived_section))
    plan.append(("Description", _description_section))
    return plan, consumed


def detail_model(node, ctx=None):
    """Pure description of the detail pane for one node.

    → {tag, title, subtitle, badges, sections:[{title, rows:[row dict],
       failed?}], fallback_keys}"""
    ctx = ctx or {}
    tag = node.get("tag")
    fields = node.get("fields", {}) or {}

    subtitle = ""
    if tag == "star" and fields.get("spectraltype"):
        subtitle = oec_value_cell(fields["spectraltype"])
    elif tag == "planet":
        subtitle = "planet"
    elif tag in ("system", "binary", "satellite"):
        subtitle = tag

    model = {
        "tag": tag,
        "title": f"{OEC_PREFIX.get(tag, '')} {oec_node_title(node)}".strip(),
        "subtitle": subtitle,
        "badges": _statuses(fields),
        "sections": [],
        "fallback_keys": [],
    }

    plan, consumed = _section_plan(node, ctx)

    def add(title, builder, allow_empty=False):
        try:
            rows = builder(node, ctx)
        except Exception:
            log_viz_error(f"OEC detail section: {title}")
            model["sections"].append({"title": title, "rows": [], "failed": True})
            return
        if rows or allow_empty:
            model["sections"].append({"title": title, "rows": rows})

    for title, builder in plan:
        add(title, builder)

    rest = sorted(k for k in fields if k not in consumed)
    model["fallback_keys"] = rest
    add("Other catalogued fields",
        lambda n, c: [_row(_humanise(k), oec_value_cell(fields[k], repeats=True))
                      for k in rest if oec_value_cell(fields[k], repeats=True)])
    return model


# ── Rendering ────────────────────────────────────────────────────────────────

def _section_widget(section):
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 6, 0, 0)
    lay.setSpacing(2)
    title = QLabel(f"<b>{section['title']}</b>")
    title.setTextFormat(Qt.TextFormat.RichText)
    lay.addWidget(title)

    if section.get("failed"):
        warn = QLabel("<i>This section could not be rendered (see the log).</i>")
        warn.setTextFormat(Qt.TextFormat.RichText)
        warn.setStyleSheet("color: #b06000;")
        lay.addWidget(warn)
        return box

    grid = QWidget()
    g = QGridLayout(grid)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(12)
    g.setVerticalSpacing(2)
    g.setColumnStretch(1, 1)
    for i, row in enumerate(section["rows"]):
        derived = row.get("derived")
        # D3 — derived values are violet and badged, never merged into the
        # catalogue rows, so provenance is unambiguous at a glance.
        lbl = QLabel(("◇ " if derived else "") + str(row["label"]))
        lbl.setStyleSheet("color: #6a3fa0;" if derived else "color: #666;")
        val = QLabel(str(row["value"]))
        val.setWordWrap(True)
        val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        if derived:
            val.setStyleSheet("color: #6a3fa0;")
        if row.get("tip"):
            lbl.setToolTip(row["tip"])
            val.setToolTip(row["tip"])
        g.addWidget(lbl, i, 0, Qt.AlignmentFlag.AlignTop)
        g.addWidget(val, i, 1)
    lay.addWidget(grid)
    return box


def build_detail_pane(node, ctx=None):
    """Render one node's detail model into a widget. Never raises: a failing
    section degrades to a note, and the rest of the pane still builds (T18)."""
    model = detail_model(node, ctx)
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(10, 8, 10, 10)
    lay.setSpacing(4)
    lay.setAlignment(Qt.AlignmentFlag.AlignTop)

    head = QLabel(f"<span style='font-size:15px'><b>{model['title']}</b></span>"
                  + (f" &nbsp;<span style='color:#777'>{model['subtitle']}</span>"
                     if model["subtitle"] else ""))
    head.setTextFormat(Qt.TextFormat.RichText)
    head.setWordWrap(True)
    lay.addWidget(head)

    if model["badges"]:
        badge = QLabel(" · ".join(model["badges"]))
        badge.setStyleSheet("color: #5a5aa0;")
        badge.setWordWrap(True)
        lay.addWidget(badge)

    rule = QFrame()
    rule.setFrameShape(QFrame.Shape.HLine)
    rule.setFrameShadow(QFrame.Shadow.Sunken)
    lay.addWidget(rule)

    for section in model["sections"]:
        lay.addWidget(_section_widget(section))

    # Cross-reference action: a star with a resolvable designation can be opened in
    # a SimbadPanel, which carries the Hypatia / GCNS / Gould blocks — so this one
    # button covers the mockup's "links to Hypatia / GCNS / SIMBAD". The callback
    # is supplied by the panel (this module owns no navigation).
    on_lookup = (ctx or {}).get("on_lookup")
    if on_lookup and model["tag"] == "star" and oec_star_xrefs(node):
        btn = QPushButton("Look up this star in SIMBAD →")
        btn.setToolTip("Opens the SIMBAD panel (Hypatia, GCNS and Gould included) "
                       "in a separate window. Makes a network request.")
        btn.clicked.connect(lambda _=False, n=node: on_lookup(n))
        lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignLeft)

    w._oec_model = model            # for tests + later stages
    return w
