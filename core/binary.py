"""core/binary.py — binary-star catalog orchestration + the companion-mass classifier.

Phase AM (catalog-access tier). Two responsibilities:

  1. **The companion-mass classifier (§3.3)** — the load-bearing, reusable piece the spec's §8
     warns must be codified so the v0.1.52 "a raw NSS pull silently ingests planets" lesson can't
     decay into a per-run footgun. Pure math, no network, offline-testable: Thiele-Innes elements
     (or an SB1 semi-amplitude) → companion mass → star / brown-dwarf / planet classification.

  2. **The Tier-2 orchestrators** `binary_orbit()` and `close_binary_census()` — the encoded
     tool-split (Gaia NSS ↔ SB9 ↔ WDS/orb6) + the population sweep. *(Added in phases AM-2/AM-3;
     they reuse the classifier below plus the `core.catalog` gateways and `compute_simbad_lookup`.)*

Mass thresholds (spec §3.3): M₂ > 0.075 M☉ → ``stellar``; 0.013–0.075 → ``brown-dwarf``;
< 0.013 M☉ (~13 M_Jup) → ``planet``. An astrometric solution with a₀ ≲ 1 mas (near the Gaia floor)
is flagged ``low-significance`` regardless of class — that is where the estimate is least reliable.
"""

import math
import re

from core.shared import _parse_spectral_class, _route_error

# ── constants ────────────────────────────────────────────────────────────────
_MJUP_PER_MSUN = 1047.5673          # M☉ / M_Jup (IAU) — M_Jup echo per spec §5 (mass in M☉ + M_Jup)
_STELLAR_MIN_MSUN = 0.075           # hydrogen-burning limit
_BD_MIN_MSUN = 0.013                # ~13 M_Jup deuterium-burning limit
_LOW_SIGNIF_A0_MAS = 1.0            # a₀ at/under this (mas) → low-significance flag (Gaia floor)

# SB1 mass-function constant: f(m) = 1.0361e-7 · K1³ · P_d · (1−e²)^1.5  (M☉; K1 km/s, P days).
_SB1_MASS_FUNC_CONST = 1.0361e-7

# Coarse main-sequence mass ladder (M☉) for M₁ from spectral type — Pecaut & Mamajek (2013)
# anchor points, linearly interpolated within a letter by subtype. Used only to seed the cubic
# (M₂ is the classified quantity); a missing/undecodable type falls back to solar.
_MS_MASS_ANCHORS = {
    "O": [(3, 60.0), (5, 32.0), (9, 16.0)],
    "B": [(0, 17.5), (1, 11.0), (3, 7.6), (5, 5.4), (8, 3.4), (9, 2.9)],
    "A": [(0, 2.18), (2, 1.98), (5, 1.86), (7, 1.74), (9, 1.66)],
    "F": [(0, 1.61), (2, 1.48), (5, 1.33), (8, 1.13), (9, 1.08)],
    "G": [(0, 1.06), (2, 1.02), (5, 0.93), (8, 0.87)],
    "K": [(0, 0.88), (2, 0.79), (5, 0.70), (7, 0.62), (9, 0.59)],
    "M": [(0, 0.57), (1, 0.50), (2, 0.44), (3, 0.36), (4, 0.23),
          (5, 0.16), (6, 0.10), (8, 0.08), (9, 0.075)],
}
_DEFAULT_M1_MSUN = 1.0


def m1_from_spectral_type(sp_type, default: float = _DEFAULT_M1_MSUN) -> float:
    """Approximate main-sequence primary mass (M☉) from a spectral type string.

    Linear interpolation within the letter's anchor list by subtype; clamps to the endpoints;
    returns `default` when the type carries no decodable OBAFGKM class (white dwarfs, unknowns)."""
    letter, subtype = _parse_spectral_class(sp_type or "")
    if letter is None or letter not in _MS_MASS_ANCHORS:
        return default
    anchors = _MS_MASS_ANCHORS[letter]
    if subtype <= anchors[0][0]:
        return anchors[0][1]
    if subtype >= anchors[-1][0]:
        return anchors[-1][1]
    for (s0, m0), (s1, m1) in zip(anchors, anchors[1:]):
        if s0 <= subtype <= s1:
            frac = (subtype - s0) / (s1 - s0) if s1 != s0 else 0.0
            return m0 + frac * (m1 - m0)
    return default


def _solve_mass_function(mass_function: float, m1_solar: float) -> float:
    """Solve M₂³ = f · (M₁ + M₂)²  for the positive companion mass M₂ (M☉).

    f = M₂³/(M₁+M₂)² is the mass function; g(M₂)=M₂³−f(M₁+M₂)² is negative at 0 and →+∞, so a
    bracket-and-bisect converges to the single physical root. Returns 0.0 for f ≤ 0."""
    f = mass_function
    if f <= 0 or m1_solar <= 0:
        return 0.0

    def g(m2):
        return m2 ** 3 - f * (m1_solar + m2) ** 2

    lo, hi = 0.0, 1.0
    it = 0
    while g(hi) < 0 and it < 200:
        hi *= 2.0
        it += 1
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if g(mid) < 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def companion_mass_from_thiele_innes(a_ti, b_ti, f_ti, g_ti, parallax_mas,
                                     period_yr, m1_solar) -> dict:
    """Companion mass from the Gaia ``nss_two_body_orbit`` Thiele-Innes elements (astrometric).

    a₀ = √(u + √(u²−v²)) mas, where u = ½(A²+B²+F²+G²), v = A·G − B·F; a₁[AU] = a₀/ϖ[mas];
    mass function f = a₁³/P_yr² = M₂³/(M₁+M₂)². Solve the cubic for M₂ with M₁ from spectral type.

    **Caveat (emitted):** this *under*-estimates M₂ when the secondary is itself luminous (the
    photocenter orbit is smaller than the primary's true orbit). Validated 2026-07-23 vs Gaia
    `binary_masses` on HD 110833 (→ 0.16 M☉ vs Gaia m2 = 0.171, ~7 %)."""
    for name, val in (("parallax_mas", parallax_mas), ("period_yr", period_yr),
                      ("m1_solar", m1_solar)):
        if val is None or val <= 0:
            raise ValueError(f"{name} must be > 0 for the astrometric mass estimate")
    A, B, F, G = float(a_ti), float(b_ti), float(f_ti), float(g_ti)
    u = 0.5 * (A * A + B * B + F * F + G * G)
    v = A * G - B * F
    disc = u * u - v * v
    if disc < 0:
        disc = 0.0                          # tiny negative from rounding → clamp
    a0_mas = math.sqrt(u + math.sqrt(disc))
    a1_au = a0_mas / parallax_mas
    mass_function = a1_au ** 3 / period_yr ** 2
    m2 = _solve_mass_function(mass_function, m1_solar)
    return {
        "method": "astrom",
        "a0_mas": a0_mas,
        "a1_au": a1_au,
        "mass_function": mass_function,
        "m2_solar": m2,
        "m2_mjup": m2 * _MJUP_PER_MSUN,
        "m1_solar": m1_solar,
        "caveat": ("astrometric mass function estimate; under-estimates M₂ when the "
                   "secondary is luminous (photocenter < primary orbit)"),
    }


def companion_mass_from_sb1(k1_kms, period_d, ecc, m1_solar) -> dict:
    """Companion **minimum** mass from a single-lined spectroscopic (SB1) semi-amplitude.

    f(m) = 1.0361e-7 · K1³ · P_d · (1−e²)^1.5  (M☉) → cubic for M₂,min (sin i = 1 **lower bound**)."""
    if k1_kms is None or k1_kms <= 0:
        raise ValueError("k1_kms must be > 0")
    if period_d is None or period_d <= 0:
        raise ValueError("period_d must be > 0")
    if ecc is None or not (0.0 <= ecc < 1.0):
        raise ValueError("ecc must be in [0, 1)")
    if m1_solar is None or m1_solar <= 0:
        raise ValueError("m1_solar must be > 0")
    mass_function = _SB1_MASS_FUNC_CONST * k1_kms ** 3 * period_d * (1.0 - ecc * ecc) ** 1.5
    m2 = _solve_mass_function(mass_function, m1_solar)
    return {
        "method": "spec-min",
        "mass_function": mass_function,
        "m2_solar": m2,
        "m2_mjup": m2 * _MJUP_PER_MSUN,
        "m1_solar": m1_solar,
        "caveat": "SB1 minimum mass (sin i = 1 lower bound); true M₂ ≥ this",
    }


def classify_companion(m2_solar, a0_mas=None) -> dict:
    """Star / brown-dwarf / planet class from companion mass, with the low-significance flag.

    Thresholds (§3.3): >0.075 → ``stellar``; 0.013–0.075 → ``brown-dwarf``; <0.013 → ``planet``.
    ``low_significance`` is set when an astrometric a₀ ≲ 1 mas (near the Gaia floor), where the
    mass estimate is least reliable — regardless of the class it lands in."""
    if m2_solar is None:
        cls = "unknown"
    elif m2_solar > _STELLAR_MIN_MSUN:
        cls = "stellar"
    elif m2_solar >= _BD_MIN_MSUN:
        cls = "brown-dwarf"
    else:
        cls = "planet"
    low = a0_mas is not None and a0_mas <= _LOW_SIGNIF_A0_MAS
    return {"class": cls, "low_significance": low}


def verification_tag(source: str, source_id=None, grade=None, bibcode=None, ref=None) -> str:
    """Paste-ready ledger verification tag for one orbit solution (spec §3.1).

    gaia-nss → ``[V-PRIMARY-Gaia-DR3-NSS source_id=…]`` · sb9 → ``[V-SECONDARY SB9 gr<N> <bib>]`` ·
    wds/orb6 → ``[V-SECONDARY WDS/orb6 <ref>]``."""
    s = (source or "").lower()
    if s.startswith("gaia"):
        return f"[V-PRIMARY-Gaia-DR3-NSS source_id={source_id}]"
    if s == "sb9":
        gr = f"gr{grade}" if grade is not None else "gr?"
        return f"[V-SECONDARY SB9 {gr} {bibcode or ''}]".rstrip()
    if s in ("wds", "orb6", "wds/orb6"):
        return f"[V-SECONDARY WDS/orb6 {ref or bibcode or ''}]".rstrip()
    return f"[V-SECONDARY {source} {ref or bibcode or ''}]".rstrip()


# ── Tier-2 orchestrator: binary-orbit (the encoded tool-split, spec §3.1) ─────

_GAIA_ID_RE = re.compile(r"(\d{5,})")
_LY_PER_PC = 3.26156
_SB9_CONE_DEG = 0.006          # ~22" — SB9/WDS are bright-star catalogs, tight cone is fine

# close-binary-census --include: known sources vs the two implemented sweep routes. wds/cv are known
# but not yet wired as census sources (they ARE reachable via the vizier-query gateway) — they are
# accounted for honestly in the coverage block rather than silently dropped.
_KNOWN_INCLUDE = ("nss", "sb9", "wds", "cv")
_EXTRA_INCLUDE = {"wds": "B/wds visual pairs", "cv": "B/cb Ritter & Kolb CVs"}


def gaia_source_id_from_designations(designations):
    """Extract the bare Gaia source_id integer (string) from the SIMBAD designations dict —
    the value is 'Gaia DR3 <id>', so strip the prefix. None when absent."""
    v = (designations or {}).get("Gaia EDR3")
    if not v:
        return None
    m = _GAIA_ID_RE.search(str(v))
    return m.group(1) if m else None


def gcns_bound_companions(gaia_id):
    """CR-18: the GCNS bound-companion signal for a Gaia source_id — a single offline read via
    ``compute_gcns_system``. Returns ``(gcns_n_components, companions)`` where each companion is
    ``{source_id, star_name, bound, proj_sep_au, separation_arcsec, basis:"gcns_cpm"}``, and
    ``(None, [])`` when there is no Gaia id / the star is not in a GCNS resolved system.

    Only pairs **incident on** ``gaia_id`` are emitted — ``compute_gcns_system`` returns every pair in
    the connected component, so a ≥3-star chain carries non-incident B–C edges that must NOT be keyed
    onto this star. Shared by the ``multiplicity`` subcommand and the dossier multiplicity section so
    the two agree by construction."""
    if not gaia_id:
        return None, []
    from core import databases
    try:
        gsys = databases.compute_gcns_system(int(gaia_id))
    except (TypeError, ValueError):
        return None, []
    if "error" in gsys or not gsys.get("system"):
        return None, []
    system = gsys["system"]
    gid = int(gaia_id)
    members = {m.get("gaia_source_id"): m.get("star_name") for m in (system.get("members") or [])}
    comps = []
    for p in system.get("pairs") or []:
        s1, s2 = p.get("source_id1"), p.get("source_id2")
        if gid == s1:
            other = s2
        elif gid == s2:
            other = s1
        else:
            continue                                   # non-incident (B–C) edge in a chain
        comps.append({
            "source_id":        other,
            "star_name":        members.get(other) or str(other),   # uncross-matched member → id string
            "bound":            p.get("bound"),   # already tri-state (compute_gcns_system applies _gcns_bool)
            "proj_sep_au":      p.get("proj_sep_au"),
            "separation_arcsec": p.get("separation_arcsec"),
            "basis":            "gcns_cpm",
        })
    comps.sort(key=lambda c: (c["proj_sep_au"] if c["proj_sep_au"] is not None else float("inf"),
                              c["source_id"]))
    return system.get("n_components"), comps


def _resolve_binary_identity(star, ra, dec, source_id):
    """Return an identity dict (main_id/ra/dec/sp_type/parallax_mas/gaia_source_id/hip/…) from a
    star name (SIMBAD), a Gaia source_id (gaia_source), or raw ra/dec. Returns (identity, error)."""
    from core import databases, catalog
    ident = {"main_id": None, "ra": ra, "dec": dec, "sp_type": None,
             "parallax_mas": None, "gaia_source_id": (str(source_id) if source_id else None),
             "hip": None}
    if star:
        sl = databases.compute_simbad_lookup(star)
        if "error" in sl:
            if ra is None or dec is None:
                return None, sl["error"]
        else:
            desig = sl.get("designations") or {}
            ident.update({
                "main_id": sl.get("main_id"), "ra": sl.get("ra"), "dec": sl.get("dec"),
                "sp_type": sl.get("sp_type"), "parallax_mas": sl.get("plx_value"),
                "gaia_source_id": gaia_source_id_from_designations(desig),
                "hip": desig.get("HIP"),
                "designations": desig,   # CR-15.4: additive — lets consumers reuse the primary lookup
            })
    if ident["gaia_source_id"] is None and source_id:
        ident["gaia_source_id"] = str(source_id)
    # Fill coords/parallax from Gaia if we have an id but no coords yet.
    if (ident["ra"] is None or ident["dec"] is None or ident["parallax_mas"] is None) \
            and ident["gaia_source_id"]:
        g = catalog.gaia_tap(adql=(
            "SELECT source_id, ra, dec, parallax FROM gaiadr3.gaia_source "
            f"WHERE source_id={ident['gaia_source_id']}"))
        if "error" not in g and g.get("rows"):
            row = g["rows"][0]
            ident["ra"] = ident["ra"] if ident["ra"] is not None else row.get("ra")
            ident["dec"] = ident["dec"] if ident["dec"] is not None else row.get("dec")
            if ident["parallax_mas"] is None:
                ident["parallax_mas"] = row.get("parallax")
    if ident["ra"] is None or ident["dec"] is None:
        return None, "Could not resolve coordinates for the target"
    plx = ident["parallax_mas"]
    ident["distance_ly"] = (1000.0 / plx * _LY_PER_PC) if (plx and plx > 0) else None
    return ident, None


def _apply_binary_masses(comp, bmass):
    """Attach Gaia `binary_masses` as the §3.3 independent cross-check, or **fill** when our tool-split
    produced no companion mass. Gaia's `m2` stays a *cross-check* (not the primary path) when we already
    have a Thiele-Innes / SB1 estimate — it only becomes the companion when ours is absent (and only if
    Gaia's `m2` is non-null; Gaia often derives just the primary mass)."""
    if not bmass:
        return comp
    gm1, gm2 = bmass.get("m1"), bmass.get("m2")
    block = {
        "m1_solar": gm1, "m2_solar": gm2,
        "m2_lower": bmass.get("m2_lower"), "m2_upper": bmass.get("m2_upper"),
        "fluxratio": bmass.get("fluxratio"),
        "combination_method": bmass.get("combination_method"),
        "m1_ref": bmass.get("m1_ref"),
    }
    if comp is None:                                    # FILL only where Gaia's m2 is non-null
        if gm2 is None:
            return None
        return {"method": "gaia-binary-masses",
                "m2_solar": gm2, "m2_mjup": gm2 * _MJUP_PER_MSUN,
                **classify_companion(gm2),
                "caveat": "from Gaia binary_masses (the tool-split produced no companion mass)",
                "binary_masses": block}
    if comp.get("m2_solar") is not None and gm2 is not None and gm2 > 0:
        block["agreement_pct"] = round(abs(comp["m2_solar"] - gm2) / gm2 * 100.0, 1)
    comp = dict(comp)
    comp["binary_masses"] = block                       # cross-check alongside our primary estimate
    return comp


def _nss_two_body_solutions(source_id, sp_type, plx_fallback):
    """Gaia NSS two_body_orbit solutions for one source_id, each with a companion-mass estimate
    plus the independent Gaia binary_masses cross-check (§3.3) where Gaia derived it."""
    from core import catalog
    res = catalog.gaia_tap(adql=("SELECT * FROM gaiadr3.nss_two_body_orbit "
                                 f"WHERE source_id={source_id}"))
    if "error" in res:
        return [], res["error"]
    m1 = m1_from_spectral_type(sp_type)
    bmass = catalog.gaia_binary_masses(source_id)      # §3.3 independent cross-check (once per source)
    out = []
    for row in res.get("rows", []):
        period = row.get("period")
        ecc = row.get("eccentricity")
        plx = row.get("parallax") or plx_fallback
        comp = None
        A, B, F, G = (row.get("a_thiele_innes"), row.get("b_thiele_innes"),
                      row.get("f_thiele_innes"), row.get("g_thiele_innes"))
        k1 = row.get("semi_amplitude_primary")
        k2 = row.get("semi_amplitude_secondary")
        try:
            if k1 and k2:                                  # double-lined → stellar, q = K1/K2
                comp = {"method": "SB2", "class": "stellar", "low_significance": False,
                        "mass_ratio_q": (k1 / k2 if k2 else None),
                        "caveat": "double-lined (SB2): both components luminous → stellar; q = K1/K2"}
            elif all(v is not None for v in (A, B, F, G)) and period and plx:
                cm = companion_mass_from_thiele_innes(A, B, F, G, plx, period / 365.25, m1)
                comp = {**cm, **classify_companion(cm["m2_solar"], cm["a0_mas"])}
            elif k1 and period:                            # single-lined spectroscopic
                cm = companion_mass_from_sb1(k1, period, ecc or 0.0, m1)
                comp = {**cm, **classify_companion(cm["m2_solar"])}
        except ValueError:
            comp = None
        comp = _apply_binary_masses(comp, bmass)
        out.append({
            "source": "gaia-nss:two_body_orbit",
            "solution_type": row.get("nss_solution_type"),
            "period_d": period, "eccentricity": ecc,
            "grade": row.get("significance"), "primary_ref": None,
            "parallax_mas": plx, "companion": comp,
            "verification": verification_tag("gaia-nss", source_id=source_id),
        })
    return out, None


def multiplicity_summary(star=None, source_id=None):
    """CR-2: a multiplicity / spectroscopic-binary summary, composing the cheap SIMBAD otype hint,
    the binary-orbit tool-split (per-component basis + SB1 lower-bound masses), and the offline
    GCNS resolved-system count. Surfaces ``sb_flag`` (an unseen-RV / spectroscopic companion) so an
    aggregator read can't miss a known binary.

    Output: ``{star, is_multiple, n_components, components:[{basis, sb_flag, sep_au?,
    m2_solar_lower?}], sb_flag, sources, note?, multiplicity_basis?}`` or ``{"error"}``. ``basis`` ∈
    visual / astrometric / SB1 / SB2 / eclipsing / spectroscopic / **gcns_cpm** (CR-18: a GCNS
    common-proper-motion companion, carrying ``bound`` + ``proj_sep_au`` + ``separation_arcsec`` +
    ``star_name``/``source_id`` — the same fields the dossier's ``gcns_companions`` expose — added even
    with no orbit); SB1 masses are always the sin i=1 **lower bound**. ``multiplicity_basis`` is set to
    ``"gcns_cpm"`` only for a pure-GCNS detection with an actually **bound** companion (no orbit
    component). ``bound`` is tri-state: True=GCNS-bound, False=GCNS-optical, absent=outside the GCNS
    layer (unknown, NOT unbound). **De-dup (WB MSG 197):** a companion confirmed by BOTH an orbit route
    AND the GCNS layer is ONE entry — the GCNS signal (``bound``/``proj_sep_au``/``separation_arcsec`` +
    ``gcns_confirmed:true`` + the resolved ``star_name``/``source_id``) is merged onto the resolved-pair
    (visual/astrometric) orbit component, so ``len(components)`` = distinct physical companions."""
    from core import databases
    if not star and not source_id:
        return _route_error("multiplicity requires --star or --source-id", ["multiplicity"])

    otype_block, designations, star_label = None, None, star
    if star:
        sl = databases.compute_simbad_lookup(star)
        if "error" in sl:
            return {"error": sl["error"]}
        otype_block = sl.get("multiplicity")
        designations = sl.get("designations")
        star_label = sl.get("main_id") or star
    gaia_id = source_id or (gaia_source_id_from_designations(designations) if designations else None)
    if star_label is None:
        star_label = str(source_id) if source_id else None

    # GCNS resolved-system multiplicity (offline, by Gaia source_id) — CR-18: one shared read via the
    # bound-companion helper (incident pairs only; exposes bound + projected separation).
    gcns_n, gcns_comps = gcns_bound_companions(gaia_id)

    # binary-orbit tool-split → per-component basis.
    bo = binary_orbit(star=star, source_id=source_id)
    by_basis = {}                                          # dedupe: one component per detection basis

    def _add(basis, sb, sep_au=None, m2_lower=None):
        cur = by_basis.get(basis)
        entry = cur or {"basis": basis, "sb_flag": sb}
        if sep_au is not None and "sep_au" not in entry:
            entry["sep_au"] = sep_au
        if m2_lower is not None and "m2_solar_lower" not in entry:
            entry["m2_solar_lower"] = m2_lower
        by_basis[basis] = entry

    for sol in bo.get("solutions", []) if isinstance(bo, dict) else []:
        comp = sol.get("companion") or {}
        method, src = comp.get("method"), sol.get("source") or ""
        if method == "SB2":
            basis = "SB2"
        elif method == "spec-min":
            basis = "SB1"
        elif method == "astrom":
            basis = "astrometric"
        elif src in ("wds", "orb6"):
            basis = "visual"
        elif src.startswith("gaia-nss"):
            basis = "astrometric"
        else:
            basis = "spectroscopic"
        _add(basis, basis in ("SB1", "SB2"),
             sep_au=sol.get("separation_au"),
             m2_lower=(comp.get("m2_solar") if basis == "SB1" else None))

    # Fold in the otype hint (eclipsing has no orbit route; spectroscopic when the split missed it).
    if otype_block and otype_block.get("basis") == "eclipsing":
        _add("eclipsing", False)
    if otype_block and otype_block.get("sb_flag") and not any(
            b in ("SB1", "SB2", "spectroscopic") for b in by_basis):
        _add("spectroscopic", True)
    components = list(by_basis.values())
    sb_flag = any(c["sb_flag"] for c in components) or bool(otype_block and otype_block.get("sb_flag"))
    is_multiple = (bool(components)
                   or bool(otype_block and otype_block.get("is_multiple"))
                   or bool(gcns_n and gcns_n > 1)
                   or any(c.get("bound") for c in gcns_comps))   # a bound GCNS companion ⇒ multiple
    if gcns_n and gcns_n > 1:
        n_components = gcns_n
    else:
        n_components = 2 if is_multiple else 1

    # CR-18: fold each GCNS bound companion into components AFTER is_multiple/sb_flag/n_components are
    # computed (so they can't perturb the verdict). DE-DUP (WB MSG 197): a companion confirmed by BOTH
    # an orbit route AND the GCNS layer is ONE physical companion — merge the GCNS bound signal onto the
    # matching **resolved-pair** orbit component (basis visual/astrometric = the same spatially-resolved
    # companion; an SB/spectroscopic component is an UNRESOLVED close pair, a DIFFERENT companion, never
    # merged) instead of listing it twice, so len(components) = distinct physical companions. The orbit
    # components carry no companion source_id/name to match on, so the match is basis-kind + nearest
    # sep_au↔proj_sep_au; a merged entry keeps its orbit basis and additively gains `bound`/`proj_sep_au`/
    # `separation_arcsec`/`gcns_confirmed:true` + the GCNS-resolved `star_name`/`source_id`. No match
    # (an orbit-less wide pair like ζ Ret, or a distinct wide companion) → a new gcns_cpm entry.
    def _sep_consistent(sep_au, proj_sep_au):
        # A projected separation vs an orbit separation for the SAME companion agree within a factor
        # (projection + eccentricity); a factor >4 apart is a different (wide-vs-close) companion.
        if not sep_au or not proj_sep_au or sep_au <= 0 or proj_sep_au <= 0:
            return False
        return 0.25 <= (proj_sep_au / sep_au) <= 4.0

    for comp in gcns_comps:
        psep = comp.get("proj_sep_au")
        cands = [c for c in components
                 if c.get("basis") in ("visual", "astrometric") and not c.get("gcns_confirmed")]
        target = None
        consistent = [c for c in cands if _sep_consistent(c.get("sep_au"), psep)]
        if consistent:
            target = min(consistent, key=lambda c: abs(c["sep_au"] - psep))
        elif len(gcns_comps) == 1 and len(cands) == 1:
            # simple-binary fallback: one resolved-pair candidate + one GCNS companion → the same star,
            # UNLESS a present-on-both separation actively contradicts it (that is the DR-1 wide-vs-close
            # case, handled above by _sep_consistent). A separation absent on either side can't contradict.
            c0 = cands[0]
            if not (c0.get("sep_au") and psep and not _sep_consistent(c0.get("sep_au"), psep)):
                target = c0
        if target is not None:
            target["bound"] = comp.get("bound")
            target["proj_sep_au"] = comp.get("proj_sep_au")
            target["separation_arcsec"] = comp.get("separation_arcsec")
            target["gcns_confirmed"] = True
            target["star_name"] = comp.get("star_name")
            target["source_id"] = comp.get("source_id")
        else:
            components.append({
                "basis": "gcns_cpm", "sb_flag": False,
                "sep_au": comp.get("proj_sep_au"), "proj_sep_au": comp.get("proj_sep_au"),
                "separation_arcsec": comp.get("separation_arcsec"),
                "bound": comp.get("bound"),
                "star_name": comp.get("star_name"), "source_id": comp.get("source_id"),
            })

    out = {
        "star": star_label, "is_multiple": is_multiple, "n_components": n_components,
        "components": components, "sb_flag": sb_flag,
        "sources": {"simbad_otype": otype_block.get("otype") if otype_block else None,
                    "gcns_n_components": gcns_n,
                    "binary_orbit_routes": bo.get("route_tried") if isinstance(bo, dict) else None},
    }
    # CR-18: name the GCNS/CPM route as the top-level basis ONLY when a companion is actually BOUND and
    # detection is pure-GCNS (no orbit component). gcns_cpm means a bound CPM pair, so a purely optical
    # co-membership (all bound=0) does NOT claim it, and an orbit-detected system keeps its own basis.
    if any(c.get("bound") for c in gcns_comps) and not by_basis:
        out["multiplicity_basis"] = "gcns_cpm"
    if isinstance(bo, dict) and bo.get("note"):
        out["note"] = bo["note"]
    return out


def _sb9_solutions(ra, dec, sp_type):
    """SB9 orbits for the system at (ra, dec): cone B/sb9/main → Seq → B/sb9/orbits."""
    from core import catalog
    main = catalog.vizier_query(catalog="B/sb9/main", cone=f"{ra} {dec} {_SB9_CONE_DEG}")
    if "error" in main:
        return [], main["error"]
    if not main.get("rows"):
        return [], None
    m0 = main["rows"][0]
    seq = m0.get("Seq")
    m1 = m1_from_spectral_type(sp_type or m0.get("Sp1"))
    # VizieR needs the leading "=" for an exact NUMERIC match ("=766"); a bare "766" matches nothing
    # (verified 2026-08-22: `Seq = 766` → 0 rows, `Seq:=766` → Spica's orbit Per=4.0145). The `Seq:=…`
    # passthrough form emits {"Seq": "=766"}. (`_parse_vizier_filters` drops the "=" for a plain `=`
    # operator — fine for a text column like Name, latent-wrong for a numeric one; scoped-fixed here.)
    orbits = catalog.vizier_query(catalog="B/sb9/orbits", filters=[f"Seq:={seq}"])
    if "error" in orbits:
        return [], orbits["error"]
    out = []
    for row in orbits.get("rows", []):
        per, e = row.get("Per"), row.get("e")
        grade, ref = row.get("Grade"), row.get("Ref")
        k1, k2 = row.get("K1"), row.get("K2")
        comp = None
        try:
            if k1 and k2:
                comp = {"method": "SB2", "class": "stellar", "low_significance": False,
                        "mass_ratio_q": (k1 / k2 if k2 else None),
                        "caveat": "double-lined (SB2): both components luminous → stellar; q = K1/K2"}
            elif k1 and per:
                cm = companion_mass_from_sb1(k1, per, e or 0.0, m1)
                comp = {**cm, **classify_companion(cm["m2_solar"])}
        except ValueError:
            comp = None
        out.append({
            "source": "sb9", "seq": seq, "period_d": per, "eccentricity": e,
            "grade": (int(grade) if grade is not None else None), "primary_ref": ref,
            "companion": comp,
            "verification": verification_tag(
                "sb9", grade=(int(grade) if grade is not None else None), bibcode=ref),
        })
    return out, None


def _wds_orb6_solutions(ra, dec, distance_pc):
    """Visual-pair solutions: WDS separations/PA + orb6 visual orbits (best-effort cone)."""
    from core import catalog
    out = []
    wds = catalog.vizier_query(catalog="B/wds/wds", cone=f"{ra} {dec} {_SB9_CONE_DEG}")
    if "error" not in wds:
        # WDS carries one row per observation epoch — collapse to one entry per (WDS id, Comp),
        # preferring a row that actually reports a separation.
        seen = {}
        for row in wds.get("rows", []):
            key = (row.get("WDS"), row.get("Comp"))
            sep = row.get("sep2") if row.get("sep2") is not None else row.get("sep1")
            if key in seen and sep is None:
                continue
            seen[key] = {
                "source": "wds", "component": row.get("Comp"),
                "period_d": None, "eccentricity": None, "grade": None,
                "separation_arcsec": sep,
                "separation_au": (sep * distance_pc) if (sep is not None and distance_pc) else None,
                "pa_deg": row.get("pa2") if row.get("pa2") is not None else row.get("pa1"),
                "primary_ref": row.get("WDS"), "companion": None,
                "verification": verification_tag("wds", ref=row.get("WDS")),
            }
        out.extend(seen.values())
    orb6 = catalog.vizier_query(catalog="B/orb6/orbits", cone=f"{ra} {dec} {_SB9_CONE_DEG}")
    if "error" not in orb6:
        for row in orb6.get("rows", []):
            out.append({
                "source": "orb6", "period_d": None, "eccentricity": row.get("e"),
                "grade": row.get("Grade"), "visual_period": row.get("P"),
                "visual_period_unit": row.get("U"), "separation_arcsec": row.get("a"),
                "primary_ref": row.get("WDS") or row.get("Name"), "companion": None,
                "verification": verification_tag("orb6", ref=row.get("WDS") or row.get("Name")),
            })
    return out


# ── CR-16: degenerate-secondary → primary-identity redirect (letterless-primary gap) ──
_SECONDARY_RE = re.compile(r"\s+[B-Z]$")   # a trailing component letter B–Z; 'A' excluded (a primary)


def _is_secondary_component(main_id):
    """True when a resolved ``main_id`` ends in a trailing component letter B–Z (a named secondary,
    e.g. ``* alf CMa B``). 'A' is excluded so a primary-named input (``* alf Cen A``) is not treated as a
    secondary. Mirrors the trailing-letter idiom of ``exclusion_system._is_secondary_component`` (which
    additionally classifies off-MS otypes — the two are NOT identical). ``_SECONDARY_RE`` single-sources
    the ``\\s+[B-Z]$`` pattern within this module (this detector + the primary-id strip in ``binary_orbit``)."""
    return bool(_SECONDARY_RE.search((main_id or "").strip()))


def redirected_primary(ident):
    """CR-16: the ``(sp_type, primary_sl, system_name)`` a mass consumer should use when ``binary_orbit``
    redirected a degenerate secondary to its primary (it attached ``ident["primary"]``), else
    ``(None, None, None)`` → the caller keeps its own fallback. Single-sources the ``ident["primary"]``
    shape so ``binary_stability_auto`` and the dossier ``_multiplicity_data_star`` consume it identically
    (avoids a three-site special case). ``primary_sl`` is the ``{main_id, sp_type, designations}`` dict
    ``resolve_binary_components`` reads."""
    prim = (ident or {}).get("primary")
    if not prim:
        return None, None, None
    return prim.get("sp_type"), prim, prim.get("main_id")


def _secondary_needs_primary_sp(ident):
    """CR-16 trigger: the query resolved to a **secondary** whose spectral type carries **no OBAFGKM
    class** (a white dwarf / degenerate / blank type — ``DA1.9``, ``DQZ``). Such a secondary cannot seed
    the orbit's primary mass (``m1_from_spectral_type`` returns the default), so the mass/orbit derivation
    must borrow the **primary's** spectral type + identity. Gated on the SECONDARY's degeneracy (NOT a
    "letterless primary" check) so an MS secondary (α Cen B ``K1V``) never trips it → the letter-symmetric
    CR-13/CR-14 battery runs unchanged code and stays byte-identical **by construction**. ``⚠``
    ``_parse_spectral_class`` returns a 2-tuple ``(letter, subtype)`` that is ALWAYS truthy (``(None,
    None)`` included) — test element ``[0]``, never the tuple itself."""
    if not _is_secondary_component(ident.get("main_id")):
        return False
    return _parse_spectral_class(ident.get("sp_type") or "")[0] is None


def binary_orbit(star=None, ra=None, dec=None, source_id=None):
    """Every orbital solution for one star across the tool-split (Gaia NSS → SB9 → WDS/orb6),
    each grade-tagged with a companion-mass estimate + star/BD/planet class + a paste-ready
    verification tag. **No solution → an explicit empty list + the routes tried**, never a silent
    empty (failed-tool ≠ absent-capability). See spec §3.1."""
    if not star and not source_id and (ra is None or dec is None):
        return _route_error("binary-orbit requires --star, --source-id, or --ra/--dec")

    ident, err = _resolve_binary_identity(star, ra, dec, source_id)
    if err and ident is None:
        return _route_error(err, ["simbad", "gaia_source"])

    # CR-16: a degenerate/non-MS secondary (WD sp-type, no OBAFGKM class) of a letterless-primary pair
    # cannot seed the orbit's primary mass. Resolve the PRIMARY's sp-type + identity and use them for the
    # companion-mass derivation (`mass_sp`), keeping the queried star's identity echo (additive `primary`
    # + `mass_resolved_via_primary` markers). Coordinates stay the queried secondary's, so the SAME orbit
    # solutions are found — only the companion m1/m2 change. Stays a RAW reporter: no catalog, sp-type only.
    mass_sp = ident.get("sp_type")
    if _secondary_needs_primary_sp(ident):
        from core import databases
        bare = _SECONDARY_RE.sub("", ident["main_id"].strip())   # strip FIRST (trailing ws defeats $)
        psl = databases.compute_simbad_lookup(bare)
        if (isinstance(psl, dict) and "error" not in psl
                and _parse_spectral_class(psl.get("sp_type") or "")[0] is not None):
            ident["primary"] = {"main_id": psl.get("main_id"), "sp_type": psl.get("sp_type"),
                                "designations": psl.get("designations") or {}}
            ident["mass_resolved_via_primary"] = psl.get("main_id")
            mass_sp = psl.get("sp_type")

    route_tried, solutions, route_errors = [], [], []

    if ident.get("gaia_source_id"):
        route_tried.append("gaia-nss:two_body_orbit")
        nss, nss_err = _nss_two_body_solutions(
            ident["gaia_source_id"], mass_sp, ident.get("parallax_mas"))
        solutions.extend(nss)
        if nss_err:
            route_errors.append(f"gaia-nss: {nss_err}")

    route_tried.append("sb9")
    sb9, sb9_err = _sb9_solutions(ident["ra"], ident["dec"], mass_sp)
    solutions.extend(sb9)
    if sb9_err:
        route_errors.append(f"sb9: {sb9_err}")

    route_tried.extend(["wds", "orb6"])
    dist_pc = (1000.0 / ident["parallax_mas"]
               if ident.get("parallax_mas") and ident["parallax_mas"] > 0 else None)
    solutions.extend(_wds_orb6_solutions(ident["ra"], ident["dec"], dist_pc))

    # CR-14.1 (Q3=(a)): mark — never reorder or drop — a degenerate placeholder `mass_ratio_q ≈ 1.0`
    # solution, so a consumer taking solutions[0] can see it is not a real ratio. binary-orbit stays a
    # raw-orbit reporter (no chain, no preferred mass); the real-ratio *selection* is done downstream in
    # `select_stability_elements` (binary-stability-auto / dossier), not here.
    for _sol in solutions:
        if _degenerate_sb2(_sol):
            _sol["degenerate"] = True

    result = {
        "query": star or (str(source_id) if source_id else f"{ra},{dec}"),
        "identity": ident,
        "solutions": solutions,
        "route_tried": route_tried,
        "units": {"period_d": "days", "separation_arcsec": "arcsec", "separation_au": "AU",
                  "parallax_mas": "mas", "distance_ly": "ly", "m2_solar": "M_sun",
                  "m2_mjup": "M_Jupiter"},
    }
    if route_errors:
        result["route_errors"] = route_errors
    if not solutions:
        result["note"] = ("no orbital solution found across the routes tried "
                          f"({', '.join(route_tried)}) — not-Gaia-resolved / not-in-SB9 does not "
                          "imply the star is single")
    return result


# ── CR-3: auto-pipe binary-orbit → Holman-Wiegert stability ───────────────────

_HW_ECC_MAX = 0.8               # Holman & Wiegert 1999 fit domain upper bound (e ≤ ~0.7–0.8)
# WDS orb6 period-unit ('U') codes → years. NOTE 'm' is MINUTES, not months (orb6 convention);
# 'c' centuries, 'd' days, 'h' hours, 'y' years.
_ORB6_PERIOD_UNIT_YR = {"y": 1.0, "d": 1.0 / 365.25, "c": 100.0,
                        "h": 1.0 / (365.25 * 24.0), "m": 1.0 / (365.25 * 24.0 * 60.0)}


def _solution_period_yr(sol):
    """Orbital period of a solution in years (period_d, or an orb6 visual_period × its unit)."""
    if sol.get("period_d"):
        return sol["period_d"] / 365.25
    vp = sol.get("visual_period")
    if vp:
        unit = (sol.get("visual_period_unit") or "y").strip().lower()[:1]
        return vp * _ORB6_PERIOD_UNIT_YR.get(unit, 1.0)
    return None


_Q_DEGEN_EPS = 1e-6          # a mass_ratio_q within this of exactly 1.0 = a placeholder equal-split


def _degenerate_sb2(sol):
    """True when a solution carries a degenerate/placeholder ``mass_ratio_q`` — exactly 1.0 with no
    spectroscopic support (an equal-split placeholder a real measured ratio never lands on)."""
    q = (sol.get("companion") or {}).get("mass_ratio_q")
    return q is not None and abs(q - 1.0) < _Q_DEGEN_EPS


def _real_sb2(sol):
    """True when a solution carries a **real** (non-placeholder) SB2 mass ratio (|q−1| ≥ eps)."""
    q = (sol.get("companion") or {}).get("mass_ratio_q")
    return q is not None and abs(q - 1.0) >= _Q_DEGEN_EPS


def _sb1_minimum(sol):
    """True when a solution's companion masses are an **SB1 minimum** (sin i = 1 lower bound) — a
    tier-1 abs-mass row whose classifier method is ``spec-min``. This is a lower bound, not a clean
    measurement, so a real SB2 ratio legitimately preempts it (CR-13). A clean astrometric abs-mass
    row (any other method) is NOT this and is never dropped (the CR-14.4 (b) improvement)."""
    c = sol.get("companion") or {}
    return (c.get("m1_solar") is not None and c.get("m2_solar") is not None
            and c.get("method") == "spec-min")


def _extract_stability_elements_full(solutions, ident):
    """Implementation of the tiered element extraction that ALSO returns the selected ``sol`` object.

    Tiered so a visual pair without a companion classifier (the 36 Oph case) still resolves:
      1. absolute companion masses + a period → a_bin via Kepler III (the clean NSS/SB9 path);
      2. an SB2 mass ratio q=K1/K2 + a period + a primary spectral type → M₂ = M₁·q;
      3. a period + a primary spectral type → equal-mass fallback (secondary mass unknown);
      4. nothing usable → (None, honest note, None).
    Returns ``(elements_dict | None, note | None, selected_sol | None)``. CR-14 (M3) exposes the picked
    solution so a consumer can name it in ``multiplicity_basis``; the byte-identical 2-tuple
    ``_extract_stability_elements`` below (its public contract) wraps this."""
    sp_type = ident.get("sp_type")
    m1_sp = m1_from_spectral_type(sp_type) if sp_type else None

    def _elem(m1, m2, sol, mass_basis):
        p_yr = _solution_period_yr(sol)
        a_bin = ((m1 + m2) * p_yr ** 2) ** (1.0 / 3.0)
        return {"m1_solar": m1, "m2_solar": m2, "sma_au": a_bin,
                "ecc": sol.get("eccentricity") or 0.0,
                "ecc_assumed": sol.get("eccentricity") is None,
                "source": sol.get("source"), "grade": sol.get("grade"),
                "mass_basis": mass_basis, "a_basis": "Kepler III (period + masses)"}

    for sol in solutions:                                   # tier 1
        comp = sol.get("companion") or {}
        if comp.get("m1_solar") and comp.get("m2_solar") and _solution_period_yr(sol):
            return (_elem(comp["m1_solar"], comp["m2_solar"], sol,
                          f"companion classifier ({comp.get('method')})"), None, sol)
    if m1_sp:
        for sol in solutions:                               # tier 2
            comp = sol.get("companion") or {}
            q = comp.get("mass_ratio_q")
            if q and _solution_period_yr(sol):
                return (_elem(m1_sp, m1_sp * q, sol,
                              "primary spectral type + SB2 mass ratio q=K1/K2"), None, sol)
        for sol in solutions:                               # tier 3
            if _solution_period_yr(sol):
                return (_elem(m1_sp, m1_sp, sol,
                              "primary spectral type; equal-mass assumption "
                              "(secondary mass unknown)"), None, sol)
    if not solutions:
        return None, ("no orbital solution found — stability not computable "
                      "(not-Gaia-resolved / not-in-SB9 does not imply single)"), None
    return None, ("orbital solution(s) found but none carries the masses + period needed for "
                  "stability — an SB2/visual pair without a primary spectral type, or a "
                  "projected-separation-only WDS row; re-run with a spectral type or masses"), None


def _extract_stability_elements(solutions, ident):
    """Pick the best solution + return (m1, m2, a_bin AU, ecc, source, grade, mass_basis, …).

    FROZEN public 2-tuple contract (unchanged output). CR-14 keeps the body in
    ``_extract_stability_elements_full`` (which also returns the selected solution) and wraps it here so
    every existing caller/test stays byte-identical. Returns (elements_dict | None, note | None)."""
    elements, note, _sol = _extract_stability_elements_full(solutions, ident)
    return elements, note


def _mass_flags(elements):
    """(mass_prov_a, mass_prov_b, notes) for a binary-orbit-derived mass pair (CR-14.2 transparency),
    read entirely from what ``_extract_stability_elements`` already returns — no solution match-back.
    Flags a degenerate equal-split (a placeholder q≈1.0 orbit OR the no-secondary ``m2=m1`` tier-3
    fallback) and an SB1 minimum-mass lower bound; never a silent mass. CR-14 hoist from
    ``exclusion_system._mass_flags`` (verbatim strings), now the single copy both paths use."""
    basis = elements.get("mass_basis") or ""
    m1, m2 = elements.get("m1_solar"), elements.get("m2_solar")
    if "equal-mass assumption" in basis:
        return ("binary_orbit_m1", "binary_orbit_equal_split_unresolved",
                ["companion mass unresolved — equal-mass assumption (no secondary mass in the orbit "
                 "solution); a placeholder, not a measured mass"])
    if "spec-min" in basis:                        # tier-1 "companion classifier (spec-min)" = SB1
        return ("binary_orbit_m1", "binary_orbit_sb1_min",
                ["companion mass is an SB1 minimum (sin i = 1 lower bound); true M₂ ≥ this — a lower "
                 "bound, not a measured mass"])
    if ("SB2 mass ratio" in basis and m1 and m2 and abs(m2 / m1 - 1.0) < _Q_DEGEN_EPS):
        return ("binary_orbit_m1", "binary_orbit_equal_split_unresolved",
                ["orbit solution reports q exactly 1.0 (a placeholder equal split — a real measured "
                 "ratio is never exactly unity); treated as unresolved, not a measured mass ratio"])
    return ("binary_orbit_m1", "binary_orbit_m2", [])


def select_stability_elements(solutions, sp_type):
    """CR-14.1/.4 shared solution selection over a ``binary-orbit`` result's ``solutions``: FILTER the
    degenerate ``q≈1.0`` placeholders BEFORE the frozen ``_extract_stability_elements``, so a real-ratio
    solution wins over an equal-split placeholder. **CR-14.4 (the (b) narrowing):** the filter drops
    ONLY degenerate rows — a clean absolute-mass row is never discarded, so ``_extract`` tier-1 (abs
    masses) still wins over tier-2 (SB2 ratio × spectral type) when both are present.

    Returns ``(sel_dict, None)`` — carrying the winning ``m1/m2/sma/ecc/mass_basis`` + per-side
    provenance flags + ``source/grade/a_basis`` + the selected ``sol`` (``selected_solution``, for M3
    ``multiplicity_basis``) — or ``(None, note)`` when no orbit is usable. Shared by
    ``exclusion_system._select_orbit_masses`` (delegate) and ``stability_from_solutions``."""
    sols = solutions or []
    # CR-14.4 (the (b) narrowing): always drop the degenerate q≈1.0 placeholders; when a REAL SB2 ratio
    # exists, also drop SB1-**minimum** rows (a real ratio beats a sin i=1 lower bound — CR-13), but keep
    # a clean astrometric absolute-mass row so _extract tier-1 (a real measurement) wins over the SB2
    # ratio × spectral-type estimate. (The old CR-13.3 filter dropped ALL abs-mass rows here, discarding
    # clean astrometric masses too — the M4 corner this narrows.)
    if any(_real_sb2(s) for s in sols):
        pool = [s for s in sols if not (_degenerate_sb2(s) or _sb1_minimum(s))]
    else:
        pool = [s for s in sols if not _degenerate_sb2(s)]
    if not pool:
        pool = sols
    elements, note, sel_sol = _extract_stability_elements_full(pool, {"sp_type": sp_type})
    if elements is None and pool is not sols:
        elements, note, sel_sol = _extract_stability_elements_full(sols, {"sp_type": sp_type})
    if elements is None:
        return None, note
    prov_a, prov_b, notes = _mass_flags(elements)
    return {
        "m1_solar": elements["m1_solar"], "m2_solar": elements["m2_solar"],
        "sma_au": elements["sma_au"], "ecc": elements["ecc"],
        "ecc_assumed": elements.get("ecc_assumed"), "mass_basis": elements.get("mass_basis"),
        "source": elements.get("source"), "grade": elements.get("grade"),
        "a_basis": elements.get("a_basis"),
        "mass_prov_a": prov_a, "mass_prov_b": prov_b, "notes": notes,
        "selected_solution": sel_sol,
    }, None


def stability_from_solutions(star_label, ident, solutions, route_tried, test_sma_au=None,
                             preferred_masses=None, selection=None):
    """Pure (no network): turn a ``binary_orbit`` result's ``solutions`` into the Holman-Wiegert
    stability block. Extracted from ``binary_stability_auto`` (CR-10.5 Part 2) so the ``dossier``
    multiplicity cross-check can reuse it on an already-fetched ``binary_orbit`` result — one network
    call, not two.

    CR-14: selects a real-ratio solution over a degenerate ``q≈1.0`` placeholder (via
    ``select_stability_elements``), surfaces per-component ``mass_provenance_a``/``_b`` +
    ``resolution_notes`` (CR-14.2), returns the ``selected_solution`` (M3, for ``multiplicity_basis``),
    and — when the network-bearing caller passes ``preferred_masses=(m1, prov_a, m2, prov_b, notes)`` (the
    CR-14.3 catalog/FLAME chain) — uses those **measured** masses, recomputing the binary sma at the same
    period via ``a ∝ M_tot^(1/3)`` (L3) so stype/ptype come off the preferred masses. **Stays PURE**: the
    chain lives in the caller; ``preferred_masses=None`` is today's orbit-derived behavior (plus the
    CR-14.1 selection + additive keys).

    ``selection=(sel, note)`` lets a caller that ALREADY ran ``select_stability_elements`` (to build
    ``preferred_masses``) thread its **single** selection through — so the preferred masses and the
    sma/element recompute come from one selection, not two independent re-selections off possibly-different
    ``sp_type`` sources (code-review CR-14 findings 1/2). Omit it → selects internally from
    ``ident.sp_type`` (the test/legacy path)."""
    from core import equations, stellar_mass
    if selection is not None:
        sel, note = selection
    else:
        sp_type = ident.get("sp_type") if isinstance(ident, dict) else None
        sel, note = select_stability_elements(solutions, sp_type)
    if sel is None:
        return {"star": star_label, "elements": None,
                "stype_critical_au": None, "ptype_critical_au": None, "mass_ratio": None,
                "test_sma_au": test_sma_au, "test_verdict": None, "orbit_type": None,
                "e_out_of_hw_range": None, "route_tried": route_tried, "note": note,
                "selected_solution": None}

    m1, m2 = sel["m1_solar"], sel["m2_solar"]
    a_bin, ecc = sel["sma_au"], sel["ecc"]
    prov_a, prov_b = sel["mass_prov_a"], sel["mass_prov_b"]
    res_notes = list(sel.get("notes") or [])
    # CR-14.3: a measured (catalog/FLAME/manual) mass from the caller's chain supersedes the orbit split;
    # recompute the binary sma at the observed period from the preferred masses (a ∝ M_tot^(1/3)).
    if preferred_masses is not None:
        pm1, pprov_a, pm2, pprov_b, pnotes = preferred_masses
        sel_mtot = (m1 or 0.0) + (m2 or 0.0)
        m1 = pm1 if pm1 is not None else m1
        m2 = pm2 if pm2 is not None else m2
        pref_mtot = (m1 or 0.0) + (m2 or 0.0)
        a_bin = stellar_mass.recompute_sma_kepler3(a_bin, sel_mtot, pref_mtot)   # CR-15.3 shared helper
        prov_a = pprov_a if pprov_a is not None else prov_a
        prov_b = pprov_b if pprov_b is not None else prov_b
        res_notes = list(pnotes or [])

    hw = equations.compute_binary_orbit_stability(
        m1, m2, a_bin, test_sma_au if test_sma_au is not None else a_bin, eccentricity=ecc)
    if "error" in hw:
        return {"star": star_label,
                "elements": {"m1_solar": m1, "m2_solar": m2, "sma_au": a_bin, "ecc": ecc,
                             "source": sel["source"], "grade": sel["grade"],
                             "mass_basis": sel["mass_basis"], "a_basis": sel["a_basis"],
                             "mass_provenance_a": prov_a, "mass_provenance_b": prov_b},
                "stype_critical_au": None, "ptype_critical_au": None, "mass_ratio": None,
                "test_sma_au": test_sma_au, "test_verdict": None, "orbit_type": None,
                "e_out_of_hw_range": ecc > _HW_ECC_MAX,
                "route_tried": route_tried, "selected_solution": sel.get("selected_solution"),
                "note": f"Holman-Wiegert rejected the elements: {hw['error']}"}

    notes = []
    if sel["ecc_assumed"]:
        notes.append("eccentricity not catalogued — assumed circular")
    if ecc > _HW_ECC_MAX:
        notes.append(f"e={ecc:.2f} is outside the Holman-Wiegert 1999 fit domain (e≤{_HW_ECC_MAX}) — "
                     "the verdict is robust but the exact critical SMA is an extrapolation")
    out = {
        "star": star_label,
        "elements": {"m1_solar": m1, "m2_solar": m2, "sma_au": a_bin, "ecc": ecc,
                     "source": sel["source"], "grade": sel["grade"],
                     "mass_basis": sel["mass_basis"], "a_basis": sel["a_basis"],
                     "mass_provenance_a": prov_a, "mass_provenance_b": prov_b},
        "stype_critical_au": hw["stype_critical_sma_au"],
        "ptype_critical_au": hw["ptype_critical_sma_au"],
        "mass_ratio": hw["mass_ratio"],
        "test_sma_au": test_sma_au,
        "test_verdict": (("stable" if hw["is_stable"] else "unstable")
                         if test_sma_au is not None else None),
        "orbit_type": hw["orbit_type"] if test_sma_au is not None else None,
        "e_out_of_hw_range": ecc > _HW_ECC_MAX,
        "route_tried": route_tried,
        "selected_solution": sel.get("selected_solution"),
    }
    if notes:
        out["note"] = "; ".join(notes)
    if res_notes:
        out["resolution_notes"] = res_notes
    return out


def binary_stability_auto(star=None, ra=None, dec=None, source_id=None, test_sma_au=None,
                          star_mass_catalog=None):
    """CR-3 + CR-14.3: fetch a binary's orbital elements (``binary_orbit``) and feed them into the
    Holman-Wiegert stability calculator — now routing the per-component **masses** through the shared
    CR-11.2/CR-13.2 chain (manual > ``--star-mass-catalog`` / internal seed > Gaia FLAME > orbit-ratio /
    inversion), so ``binary-stability-auto`` reports the **same** per-component masses as
    ``exclusion-system`` / the dossier for a given star. Real-ratio solution selection (CR-14.1) +
    degenerate/SB1 flags (CR-14.2) apply when a mass is orbit-derived.

    Output: ``{star, elements:{m1_solar, m2_solar, sma_au, ecc, source, grade, mass_basis, a_basis,
    mass_provenance_a, mass_provenance_b}, stype_critical_au, ptype_critical_au, mass_ratio, test_sma_au,
    test_verdict, orbit_type, e_out_of_hw_range, route_tried, selected_solution, note?, resolution_notes?}``
    — or ``{"error"}`` on an unresolvable identity / bad catalog, or an ``elements: None`` honest-empty
    when no usable orbit exists (never fabricated elements)."""
    if test_sma_au is not None and test_sma_au <= 0:
        return {"error": "test_sma_au must be positive."}
    from core import stellar_mass, stellar_mass_tables, databases
    catalog = stellar_mass_tables.load_mass_catalog(star_mass_catalog)
    if isinstance(catalog, dict) and "error" in catalog:
        return {"error": catalog["error"]}
    result = binary_orbit(star=star, ra=ra, dec=dec, source_id=source_id)
    if "error" in result:
        return result
    ident = result.get("identity", {})
    solutions = result.get("solutions", [])
    # CR-14.3: per-component preferred masses via the shared chain. Needs a resolved main_id (the primary
    # SIMBAD identity carries the designations the catalog/FLAME tiers match on); coordinate-only input
    # (--ra/--dec/--source-id with no name) leaves main_id None → no catalog designations → the orbit
    # masses stand (L3 graceful fallback).
    preferred = None
    # CR-16: when binary_orbit redirected a degenerate secondary, resolve masses via the PRIMARY it
    # attached (`redirected_primary` → sp_type + primary_sl + system_name); else keep the CR-15.4 fallback.
    prim_sp, prim_sl, prim_name = redirected_primary(ident)
    sel, sel_note = select_stability_elements(
        solutions, prim_sp if prim_sp is not None else ident.get("sp_type"))
    if sel is not None and (star or ident.get("main_id")):
        # A redirected primary makes slot A hit the primary catalog row and slot B the secondary
        # (cross-path-equal to the system-name query; the queried secondary main_id is never in slot A's id
        # set). CR-15.4 fallback: reuse the primary identity binary_orbit already resolved (its identity
        # carries `designations` for name-based input) instead of a redundant SIMBAD re-lookup;
        # coordinate-/source_id-only input has no designations → fall back to the lookup.
        if prim_sl is not None:
            primary_sl = prim_sl
        elif ident.get("designations") is not None:
            primary_sl = {"main_id": ident.get("main_id"), "sp_type": ident.get("sp_type"),
                          "designations": ident.get("designations")}
        else:
            primary_sl = databases.compute_simbad_lookup(star or ident.get("main_id"))
        if isinstance(primary_sl, dict) and "error" not in primary_sl:
            preferred = stellar_mass.resolve_binary_components(
                primary_sl, sel, catalog,
                system_name=(prim_name if prim_name is not None else (star or ident.get("main_id"))))
    # Thread the SAME selection through (code-review findings 1/2) — one select, not two.
    out = stability_from_solutions(result.get("query"), ident, solutions,
                                   result.get("route_tried"), test_sma_au=test_sma_au,
                                   preferred_masses=preferred, selection=(sel, sel_note))
    # CR-16 transparency: when the masses resolved via a redirected primary, flag it additively so a
    # consumer seeing the PRIMARY's m1 for a secondary-named query (`star` still echoes "Sirius B") knows
    # why. Only present on the redirect path — absent (byte-identical) for every letter-symmetric/primary query.
    if isinstance(out, dict) and ident.get("primary"):
        out["mass_resolved_via_primary"] = ident["primary"].get("main_id")
    return out


# ── Tier-2 orchestrator: close-binary-census (the population sweep, spec §3.2) ─

def _companion_from_row(period_d, ecc, ti, k1, k2, plx, m1):
    """Companion-mass block for one census row (Thiele-Innes → SB1 → SB2), or None."""
    A, B, F, G = ti
    try:
        if k1 and k2:
            return {"method": "SB2", "class": "stellar", "low_significance": False,
                    "mass_ratio_q": (k1 / k2 if k2 else None),
                    "caveat": "double-lined → stellar; q = K1/K2"}
        if all(v is not None for v in (A, B, F, G)) and period_d and plx:
            cm = companion_mass_from_thiele_innes(A, B, F, G, plx, period_d / 365.25, m1)
            return {**cm, **classify_companion(cm["m2_solar"], cm["a0_mas"])}
        if k1 and period_d:
            cm = companion_mass_from_sb1(k1, period_d, ecc or 0.0, m1)
            return {**cm, **classify_companion(cm["m2_solar"])}
    except ValueError:
        return None
    return None


def _census_nss(plx_min, period_max_d):
    """Gaia NSS faint-pair census: nss_two_body_orbit with parallax > plx_min and period < max.
    Uses the table's own ra/dec/parallax (no gaia_source JOIN — the JOIN times out server-side,
    spec §4.2) via an async job (no 2000-row cap)."""
    from core import catalog
    adql = ("SELECT source_id, nss_solution_type, period, eccentricity, "
            "a_thiele_innes, b_thiele_innes, f_thiele_innes, g_thiele_innes, "
            "semi_amplitude_primary, semi_amplitude_secondary, parallax, significance, ra, dec "
            "FROM gaiadr3.nss_two_body_orbit "
            f"WHERE parallax > {plx_min} AND period > 0 AND period < {period_max_d}")
    res = catalog.gaia_tap(adql=adql, use_async=True, row_limit=-1)
    if "error" in res:
        return [], res["error"]
    out = []
    for row in res.get("rows", []):
        plx = row.get("parallax")
        dist_ly = (1000.0 / plx * _LY_PER_PC) if (plx and plx > 0) else None
        comp = _companion_from_row(
            row.get("period"), row.get("eccentricity"),
            (row.get("a_thiele_innes"), row.get("b_thiele_innes"),
             row.get("f_thiele_innes"), row.get("g_thiele_innes")),
            row.get("semi_amplitude_primary"), row.get("semi_amplitude_secondary"),
            plx, _DEFAULT_M1_MSUN)                       # bulk: solar-mass primary assumption
        out.append({
            "source": "gaia-nss:two_body_orbit", "source_id": str(row.get("source_id")),
            "solution_type": row.get("nss_solution_type"),
            "name": None, "ra": row.get("ra"), "dec": row.get("dec"),
            "parallax_mas": plx, "distance_ly": dist_ly,
            "period_d": row.get("period"), "eccentricity": row.get("eccentricity"),
            "grade": row.get("significance"), "companion": comp,
            "verification": verification_tag("gaia-nss", source_id=row.get("source_id")),
        })
    return _collapse_nss_solutions(out), None


def _collapse_nss_solutions(rows):
    """One row per Gaia `source_id`, keeping the highest-graded orbit solution.

    A single source can carry SEVERAL NSS solutions of very different quality, and emitting
    them all counts one system many times. The SB9 route has always collapsed this way (best
    row per `Seq`); this is the same rule for NSS. The discarded solutions are **surfaced,
    not dropped** — `n_orbit_solutions` + `other_solutions[]` — because the disagreement is
    often the interesting part:

      • FK Aqr / GJ 867 A (source 2400808142038361088) — a grade-43 `OrbitalTargetedSearch`
        at 7.98 d against a grade-205 `SB2C` at 4.083196151 d, the latter reproducing the
        primary paper to 10 significant figures.
      • BY Dra (source 2145277550935525760) — a grade-17 `OrbitalTargetedSearch` at 32.27 d
        against a grade-141 `SB2` at 5.977 d, which matches the primary paper.

    Grade preference resolves both **mechanically**, with no per-system special-casing.

    NOTE what is deliberately NOT done: no rule of the form "distrust low-grade rows" or
    "distrust short-period rows". A **sole** solution is flagged (`sole_solution`) and its
    `solution_type` + `grade` are emitted, but no verdict is manufactured — G 184-19 is a
    sole `SB2` at grade 126 (trustworthy) while Wolf 227 is a sole `OrbitalTargetedSearch` at
    grade 38 (weak), and the two are told apart by *type plus whether a rival row exists*,
    not by grade alone. There is also no natural grade cliff to cut on: across a 65 ly sweep
    the NSS grades run 2.9–270.7 with a median of 44.4, so any threshold would flag much of
    the census. The consumer gets the signals and applies its own policy.
    """
    best, extras = {}, {}
    for r in rows:
        sid = r.get("source_id")
        if not sid:
            continue
        prev = best.get(sid)
        if prev is None or (r.get("grade") or 0) > (prev.get("grade") or 0):
            if prev is not None:
                extras.setdefault(sid, []).append(prev)
            best[sid] = r
        else:
            extras.setdefault(sid, []).append(r)
    out = []
    for sid, r in best.items():
        others = extras.get(sid, [])
        r["n_orbit_solutions"] = 1 + len(others)
        r["sole_solution"] = not others
        r["other_solutions"] = [
            {"period_d": o.get("period_d"), "eccentricity": o.get("eccentricity"),
             "grade": o.get("grade"), "solution_type": o.get("solution_type")}
            for o in sorted(others, key=lambda o: -(o.get("grade") or 0))
        ]
        out.append(r)
    return out


def _sb9_coords_by_seq(seqs):
    """{Seq: (ra_deg, dec_deg, name, sp1)} for the given Seqs, from B/sb9/main (sexagesimal→deg)."""
    from core import catalog
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    main = catalog.vizier_query(catalog="B/sb9/main", row_limit=-1)
    if "error" in main:
        return {}, main["error"]
    want = set(seqs)
    coords = {}
    for row in main.get("rows", []):
        seq = row.get("Seq")
        if seq not in want:
            continue
        try:
            c = SkyCoord(str(row.get("RAJ2000")), str(row.get("DEJ2000")),
                         unit=(u.hourangle, u.deg))
            coords[seq] = (float(c.ra.deg), float(c.dec.deg), row.get("Name"), row.get("Sp1"))
        except Exception:
            continue
    return coords, None


def _census_sb9(period_max_d, dist_max_ly, parallax_source):
    """SB9 bright-classical census: orbits with Per < max → one best-graded orbit per system →
    B/sb9/main coords → X-Match to Hipparcos (+optionally Gaia) parallax → distance cut."""
    from core import catalog
    orbits = catalog.vizier_query(catalog="B/sb9/orbits",
                                  filters=[f"Per < {period_max_d}"], row_limit=-1)
    if "error" in orbits:
        return [], orbits["error"]
    best = {}                                            # Seq → best-graded orbit row
    for row in orbits.get("rows", []):
        seq, per = row.get("Seq"), row.get("Per")
        if seq is None or not per or per <= 0:
            continue
        g = row.get("Grade") or 0
        if seq not in best or (g or 0) > (best[seq].get("Grade") or 0):
            best[seq] = row
    if not best:
        return [], None
    coords, err = _sb9_coords_by_seq(best.keys())
    if err:
        return [], err
    # X-Match the system coords to Hipparcos (and optionally Gaia) for parallax.
    coord_rows = [{"_seq": seq, "ra": coords[seq][0], "dec": coords[seq][1]}
                  for seq in best if seq in coords]
    plx_by_seq = {}
    gaia_id_by_seq = {}
    cats = []
    if parallax_source in ("hipparcos", "both"):
        cats.append(("vizier:I/311/hip2", "Plx"))
    if parallax_source in ("gaia", "both"):
        cats.append(("vizier:I/355/gaiadr3", "Plx"))
    for cat2, plx_col in cats:
        xm = catalog.xmatch_query(coord_rows, cat2=cat2, max_arcsec=5.0)
        if "error" in xm:
            continue
        for mrow in xm.get("rows", []):
            seq = coord_rows[int(mrow["_idx"])]["_seq"]
            plx = mrow.get(plx_col)
            if plx and plx > 0 and seq not in plx_by_seq:   # first source wins (Hipparcos, then Gaia)
                plx_by_seq[seq] = plx
            # Capture the Gaia source_id from the SAME X-Match — it is already fetched and
            # was being discarded. This is what makes cross-route dedup IDENTITY-based
            # instead of positional, at zero extra network cost. (Only available when the
            # Gaia leg runs, i.e. --parallax-source gaia|both; with hipparcos-only the
            # dedup falls back to flagging by position.)
            if seq not in gaia_id_by_seq:
                gid = mrow.get("Source") or mrow.get("DR3Name")
                if gid:
                    gid = str(gid).replace("Gaia DR3 ", "").strip()
                    if gid.isdigit():
                        gaia_id_by_seq[seq] = gid
    out = []
    # Identity pass. The parallax X-Match above runs at 5″ — deliberately tight, because a
    # mis-matched parallax would corrupt the distance cut and therefore census membership.
    # But SB9's coordinates are coarse enough that genuine twins sit 6–9″ away, so that
    # radius resolves a Gaia id for almost none of the rows that need one. A SECOND, wider
    # X-Match is run for identity only (one extra call, not per-row): a wrong id here can
    # only cause a merge decision, which is audited by the recorded separation + the period
    # comparison, whereas a wrong parallax would silently move a star in or out of the cut.
    if parallax_source in ("gaia", "both"):
        missing = [r for r in coord_rows if r["_seq"] not in gaia_id_by_seq]
        if missing:
            xm = catalog.xmatch_query(missing, cat2="vizier:I/355/gaiadr3",
                                      max_arcsec=_IDENTITY_XMATCH_ARCSEC)
            if "error" not in xm:
                for mrow in xm.get("rows", []):
                    seq = missing[int(mrow["_idx"])]["_seq"]
                    if seq in gaia_id_by_seq:
                        continue
                    gid = mrow.get("Source") or mrow.get("DR3Name")
                    if gid:
                        gid = str(gid).replace("Gaia DR3 ", "").strip()
                        if gid.isdigit():
                            gaia_id_by_seq[seq] = gid

    for seq, row in best.items():
        if seq not in coords or seq not in plx_by_seq:
            continue
        plx = plx_by_seq[seq]
        dist_ly = 1000.0 / plx * _LY_PER_PC
        if dist_ly > dist_max_ly:
            continue
        ra, dec, name, sp1 = coords[seq]
        m1 = m1_from_spectral_type(sp1)
        comp = _companion_from_row(row.get("Per"), row.get("e"), (None, None, None, None),
                                   row.get("K1"), row.get("K2"), plx, m1)
        grade = row.get("Grade")
        out.append({
            "source": "sb9", "source_id": None, "seq": seq, "name": name,
            "gaia_source_id": gaia_id_by_seq.get(seq),   # identity key for cross-route dedup
            "ra": ra, "dec": dec, "parallax_mas": plx, "distance_ly": dist_ly,
            "period_d": row.get("Per"), "eccentricity": row.get("e"),
            "grade": (int(grade) if grade is not None else None),
            "primary_ref": row.get("Ref"), "companion": comp,
            "verification": verification_tag(
                "sb9", grade=(int(grade) if grade is not None else None), bibcode=row.get("Ref")),
        })
    return out, None


_IDENTITY_XMATCH_ARCSEC = 15.0   # identity-only X-Match radius (SB9 coords are coarse)
_PERIOD_AGREE_FRAC = 0.05    # >5% apart → the two routes disagree on the period, and say so


def _sky_sep_arcsec(a, b):
    """Small-angle separation between two rows carrying ra/dec in degrees, or None."""
    if a.get("ra") is None or a.get("dec") is None or b.get("ra") is None or b.get("dec") is None:
        return None
    cosd = max(0.05, math.cos(math.radians(a["dec"])))
    return 3600.0 * math.hypot((a["ra"] - b["ra"]) * cosd, a["dec"] - b["dec"])


def _dedup_census(nss_rows, sb9_rows, tol_arcsec=15.0):
    """Single-count Gaia↔SB9 twins, **identity first**.

    Three rules, in order, and the third is the one that matters:

    1. **Identity** — an SB9 row whose Gaia `source_id` (captured from the parallax X-Match)
       equals an NSS row's is the SAME star: single-counted, `also_in:['sb9']`.
    2. **Position, only as a fallback** for SB9 rows with no resolved Gaia id, and widened to
       ~15″ because SB9's coordinates are coarse (the old 3″ box let genuine twins through
       6–9″ apart — FK Aqr's two rows sit 7.2″ apart).
    3. **A positional match is FLAGGED, never merged.** Proximity alone does not prove
       identity: Castor (HIP 36850) genuinely carries two real close pairs at one position,
       and merging them would *under*-count. Such rows stay in the census carrying
       `possible_duplicate_of` for the caller to adjudicate.

    And when two routes *are* the same star but disagree on the period, the disagreement is
    surfaced (`period_disagreement`) rather than silently resolved — that disagreement is
    exactly what identified two spurious Gaia solutions (FK Aqr, BY Dra), so hiding it would
    have hidden the finding.
    """
    by_gaia = {n["source_id"]: n for n in nss_rows if n.get("source_id")}
    merged_into = set()          # NSS source_ids that have already absorbed an SB9 row
    kept_sb9 = []
    for s in sb9_rows:
        twin = by_gaia.get(s.get("gaia_source_id")) if s.get("gaia_source_id") else None
        if twin is not None and s.get("gaia_source_id") in merged_into:
            # A SECOND SB9 orbit resolving to the same Gaia source is not a duplicate — it is
            # very likely a second real close pair in a multiple system (Castor carries two).
            # Merging it would UNDER-count, so keep it and flag instead.
            s["possible_duplicate_of"] = {
                "source_id": s.get("gaia_source_id"), "separation_arcsec": None,
                "note": ("second SB9 orbit on the same Gaia source — kept, not merged: this "
                         "is usually a second real close pair in a multiple (e.g. Castor), "
                         "and merging would under-count"),
            }
            kept_sb9.append(s)
            continue
        if twin is not None:
            merged_into.add(s.get("gaia_source_id"))
            twin.setdefault("also_in", []).append("sb9")
            twin["sb9_period_d"] = s.get("period_d")
            twin["sb9_ref"] = s.get("primary_ref")
            n_p, s_p = twin.get("period_d"), s.get("period_d")
            if n_p and s_p and abs(n_p - s_p) / max(n_p, s_p) > _PERIOD_AGREE_FRAC:
                # Same star, different periods. Do NOT pick a winner here: the caller has
                # the grades, the solution types and the SB9 reference, and both FK Aqr and
                # BY Dra turned out to be the Gaia row being wrong.
                twin["period_disagreement"] = {
                    "nss_period_d": n_p, "sb9_period_d": s_p,
                    "nss_solution_type": twin.get("solution_type"),
                    "nss_grade": twin.get("grade"), "sb9_ref": s.get("primary_ref"),
                }
            continue
        # No identity → positional FLAG only.
        for n in nss_rows:
            sep = _sky_sep_arcsec(n, s)
            if sep is not None and sep <= tol_arcsec:
                s["possible_duplicate_of"] = {
                    "source_id": n.get("source_id"), "separation_arcsec": round(sep, 2),
                    "note": ("positional match only — identity not resolved, so this is "
                             "flagged rather than merged (two real close pairs can share "
                             "one position, e.g. Castor)"),
                }
                break
        kept_sb9.append(s)
    return nss_rows + kept_sb9


def _load_exclude(exclude_known):
    """Load a set of lowercased names / Gaia source_ids to drop (one token per line)."""
    if not exclude_known:
        return set()
    import os
    out = set()
    try:
        if os.path.isfile(exclude_known):
            with open(exclude_known, encoding="utf-8") as fh:
                for line in fh:
                    tok = line.strip()
                    if tok and not tok.startswith("#"):
                        out.add(tok.lower())
    except Exception:
        pass
    return out


def _is_excluded(entry, excl):
    if not excl:
        return False
    for k in (entry.get("source_id"), entry.get("name")):
        if k and str(k).lower() in excl:
            return True
    return False


def close_binary_census(dist_max_ly, period_max_d, sep_max_au=None,
                        include=("nss", "sb9"), parallax_source="both",
                        classify=True, drop_planets=True, separate_wide=False,
                        exclude_known=None):
    """The systematic close-binary population sweep as one reproducible call (spec §3.2): Gaia NSS
    (faint) + SB9 (bright, Hipparcos/Gaia parallax) → X-Match dedup → companion classification →
    planet filter → honest coverage block. Companion masses are estimates (bulk NSS uses a
    solar-mass primary assumption — per-system `binary-orbit` gives the spectral-typed refinement)."""
    if dist_max_ly is None or dist_max_ly <= 0:
        return _route_error("--dist-max-ly must be > 0")
    if period_max_d is None or period_max_d <= 0:
        return _route_error("--period-max-d must be > 0")
    include = tuple(include or ())
    unknown = [t for t in include if t not in _KNOWN_INCLUDE]
    if unknown:
        return _route_error(f"unknown --include source(s): {', '.join(unknown)} "
                            f"(known: {', '.join(_KNOWN_INCLUDE)})")
    dist_max_pc = dist_max_ly / _LY_PER_PC
    plx_min = 1000.0 / dist_max_pc
    excl = _load_exclude(exclude_known)

    swept, not_swept, route_errors, requested_not_implemented = [], [], [], []
    nss_rows, sb9_rows = [], []

    if "nss" in include:
        nss_rows, err = _census_nss(plx_min, period_max_d)
        swept.append("gaiadr3.nss_two_body_orbit (faint pairs)")
        if err:
            route_errors.append(f"nss: {err}")
    else:
        not_swept.append("gaiadr3.nss_two_body_orbit")

    if "sb9" in include:
        sb9_rows, err = _census_sb9(period_max_d, dist_max_ly, parallax_source)
        swept.append(f"SB9 (B/sb9) + {parallax_source} parallax (bright classical SBs)")
        if err:
            route_errors.append(f"sb9: {err}")
    else:
        not_swept.append("SB9 (B/sb9)")

    # wds/cv are not yet wired as census sweep sources — account for them HONESTLY (never silently
    # drop a requested source): requested → requested_not_implemented; not requested → not_swept.
    for tag, label in _EXTRA_INCLUDE.items():
        (requested_not_implemented if tag in include else not_swept).append(label)

    combined = _dedup_census(nss_rows, sb9_rows)

    census, excluded_planets, wide = [], [], []
    for e in combined:
        if _is_excluded(e, excl):
            continue
        cls = (e.get("companion") or {}).get("class", "unknown")
        if drop_planets and cls == "planet":
            excluded_planets.append(e)
            continue
        if separate_wide and sep_max_au and e.get("separation_au") \
                and e["separation_au"] > sep_max_au:
            wide.append(e)
            continue
        census.append(e)

    counts = {}
    for e in census:
        cls = (e.get("companion") or {}).get("class", "unknown")
        counts[cls] = counts.get(cls, 0) + 1

    coverage = {
        "catalogs_swept": swept,
        "catalogs_not_swept": not_swept,
        "requested_not_implemented": requested_not_implemented,
        "dist_max_ly": dist_max_ly, "period_max_d": period_max_d,
        "parallax_min_mas": plx_min, "parallax_source": parallax_source,
        "notes": [
            "NOT exhaustive — only the Gaia NSS + SB9 orbit routes are implemented census sources; "
            "unresolved/spectroscopic pairs outside SB9 and wide literature-only companions are not "
            "covered.",
            "Bulk NSS companion masses assume a solar-mass primary; run `binary-orbit --star` per "
            "system for the spectral-typed refinement + the Gaia binary_masses cross-check.",
            "Gaia NSS saturates on bright stars (G ≲ 5) — those are covered by the SB9 route.",
        ],
    }
    if requested_not_implemented:
        coverage["notes"].append(
            "Requested --include source(s) not yet wired into the census sweep: "
            + ", ".join(requested_not_implemented)
            + " (reachable directly via `vizier-query --catalog B/wds/wds` / `B/cb/cbdata`).")
    result = {
        "query": {"dist_max_ly": dist_max_ly, "period_max_d": period_max_d,
                  "sep_max_au": sep_max_au, "include": list(include),
                  "drop_planets": drop_planets, "separate_wide": separate_wide},
        "count": len(census), "counts_by_class": counts,
        # Dedup accounting — a census row is one SYSTEM, but two of these numbers are the
        # honest caveats on that claim: rows that carry an unresolved positional twin, and
        # rows where the two routes disagree about the period of the same star.
        "dedup": {
            "possible_duplicates": sum(1 for e in census if e.get("possible_duplicate_of")),
            "period_disagreements": sum(1 for e in census if e.get("period_disagreement")),
            "multi_solution_sources": sum(1 for e in census
                                          if (e.get("n_orbit_solutions") or 1) > 1),
            "cross_route_single_counted": sum(1 for e in census if e.get("also_in")),
        },
        "census": census, "excluded_planets": excluded_planets, "wide": wide,
        "coverage": coverage,
        "units": {"period_d": "days", "distance_ly": "ly", "parallax_mas": "mas",
                  "separation_au": "AU", "m2_solar": "M_sun", "m2_mjup": "M_Jupiter"},
    }
    if route_errors:
        result["route_errors"] = route_errors
    return result

