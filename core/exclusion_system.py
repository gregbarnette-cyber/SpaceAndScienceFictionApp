"""CR-11.3 — binary / multi-star FTL exclusion-boundary composition (`exclusion-system`).

`exclusion-boundary` (``core.exclusion_boundary``) is a **strictly single-body** generator: one body
source in, one scalar ``r_ex_au`` out. Binary and multiple systems (Sirius, α Centauri) therefore had
their merged exclusion zone **hand-computed** off-tool. This module composes the **FROZEN** single-body
generator over a resolved multi-star configuration into a **set of merge-grouped, phase-varying,
asymmetric zones with per-component domain guards**, per canon
(``ftl-arrival-and-emergence-geography.md`` "composed **per-body**, not read off the primary's mass";
``metric-drive-and-ftl-causality-architecture.md`` binaries make it "larger, time-varying, asymmetric").

**The single-body ``compute_exclusion_boundary`` is FROZEN — this module edits none of it** and adds no
second calibration: every per-component ``r_ex`` is that generator on the component's mass. The default
``alpha`` here is **0.4** (mid of the canon [1/3, 1/2] band), which reproduces the hand-card anchors
exactly; a single-star input reproduces ``exclusion-boundary`` run on the same mass with the same knobs.

Pipeline (per ``--phase`` = periastron and/or apastron):
  1. **Per component** — ``r_ex`` from the frozen generator on the **CR-11.2-preferred mass**
     (``core.stellar_mass``). An **off-main-sequence** component (white dwarf / brown dwarf / rogue /
     evolved giant) is flagged out-of-domain and contributes **no sphere** (``r_ex_au = null``) — the
     canon consume-guard. The guard withholds the **sphere, not the mass**: the component's real
     (measured) mass still sets its barycentric offset (Sirius B).
  2. **Barycentric offsets** from the mass ratios (every component's real mass, WD included) and the
     instantaneous separation (periastron **and** apastron).
  3. **Merge-grouping** — union-find over the pairwise overlap test ``d < (r_ex,i + r_ex,j)`` at closest
     approach; an out-of-domain member's radius counts as 0, so the test reduces to whether it sits
     inside an in-domain member's boundary (Sirius B inside A). α Cen: {A,B} merge, {Proxima} separate.
  4. **Per merged zone** — the union of in-domain member spheres at their barycentric offsets → a
     prolate, asymmetric envelope: ``long_axis_au`` (semi-extent along the line, at peri & apo),
     ``minor_axis_au`` (perpendicular, = the largest in-domain sphere), and the ``barycenter``.
  5. **Optional corroborating ``point_mass_r_ex_au``** — M_tot of the **in-domain members only** through
     the same generator, corroboration-only (never the authoritative radius; an out-of-domain mass is
     **never** summed in — a windless WD adds no medium noise).

Pure math (no network, no DB, no RNG, no time) when handed explicit components; the ``--star`` name path
resolves the system (SIMBAD + ``binary-orbit``/SB9) then hands the components here.
"""

import math

from core import exclusion_boundary as eb
from core import stellar_mass
from core import stellar_mass_tables

_DEFAULT_ALPHA = 0.4          # mid of the canon [1/3, 1/2] band; reproduces the hand-card anchors
_OFF_MS_TAGS = {"wd", "white-dwarf", "white_dwarf", "brown-dwarf", "brown_dwarf", "bd",
                "rogue", "rogue-planet", "giant", "evolved"}
_TAG_CLASS_NOTE = {
    "wd": "white dwarf", "white-dwarf": "white dwarf", "white_dwarf": "white dwarf",
    "brown-dwarf": "brown dwarf", "brown_dwarf": "brown dwarf", "bd": "brown dwarf",
    "rogue": "rogue / sub-brown-dwarf", "rogue-planet": "rogue / sub-brown-dwarf",
    "giant": "evolved giant", "evolved": "evolved star",
}

_MODEL_NOTE_COMPOSE = (
    "CR-11.3 composition of the FROZEN single-body exclusion-boundary generator over the resolved "
    "components — no second calibration. Per-component r_ex is compute_exclusion_boundary on the "
    "CR-11.2-preferred mass; off-MS components (WD/BD/rogue/giant) are out-of-domain and contribute no "
    "sphere (their real mass still sets the barycenter). The zone envelope is the union of in-domain "
    "spheres at their barycentric offsets — larger, time-varying and asymmetric than any single "
    "component (canon). point_mass_r_ex_au is corroboration-only over in-domain members; an "
    "out-of-domain mass is never summed in."
)


# ── domain guard ──────────────────────────────────────────────────────────────
def _component_domain(sp_type=None, class_tag=None):
    """(domain, class_note) — 'main_sequence' or 'out_of_domain' for a component.

    An explicit off-MS ``class_tag`` (wd/brown-dwarf/rogue/giant) wins; else the SIMBAD ``sp_type`` is
    classified by the app's canonical ``detection._host_class`` (CR-6-AMEND) — white dwarf (``D*``),
    brown dwarf (``L``/``T``/``Y``), **hot subdwarf** (``sdB``/``sdO``), subgiant (IV), giant
    (I/II/III), luminosity VI/VII — is out-of-domain. An ordinary OBAFGKM dwarf (lum V, or cool
    subdwarfs ``sdM``/``esdM``) is main-sequence.
    """
    if class_tag:
        t = class_tag.strip().lower()
        if t in _OFF_MS_TAGS:
            return "out_of_domain", _TAG_CLASS_NOTE.get(t, t)
        if t in ("main-sequence", "main_sequence", "ms", "dwarf"):
            return "main_sequence", None
        # else fall through and treat the tag as a spectral type
        sp_type = sp_type or class_tag
    sp = (sp_type or "").strip()
    if not sp:
        return "main_sequence", None    # no info → assume MS (do not fabricate a guard)
    # Reuse the app's canonical non-MS classifier (CR-6-AMEND) so this guard agrees with the rest of
    # the tool: WD (degenerate `D*`), BD (`L`/`T`/`Y`), **hot subdwarf sdB/sdO**, subgiant (IV),
    # giant (I/II/III), luminosity VI/VII — while cool subdwarfs (sdM/esdM) and lum-V dwarfs stay MS.
    from core import detection
    host_class = detection._host_class(sp)
    if host_class is not None:
        return "out_of_domain", host_class.replace("_", " ")
    return "main_sequence", None


# ── per-component r_ex (frozen generator) ────────────────────────────────────
def _component_rex(comp, alpha, calibration_au, dial, beta, gamma):
    """r_ex_au for an in-domain component via the FROZEN generator, or None if out-of-domain / error."""
    if comp["domain"] != "main_sequence":
        return None, None
    res = eb.compute_exclusion_boundary(
        comp["mass_solar"], luminosity_lsun=comp.get("luminosity_lsun") or 1.0,
        mass_loss_msun_yr=comp.get("mass_loss_msun_yr"), wind_state=comp.get("wind_state"),
        dial=dial, calibration_au=calibration_au, alpha=alpha, beta=beta, gamma=gamma)
    if "error" in res:
        return None, res["error"]
    return res["r_ex_au"], None


# ── pairwise separation (peri / apo) from the orbital structure ──────────────
def _pair_sep(ci, cj, phase):
    """Separation (AU) between two components at ``phase`` ('peri'|'apo'), or +inf if unlinked.

    Two components sharing a ``pair`` label are the members of one close orbit (separation
    ``sma·(1∓e)``); a component whose ``orbits`` names the other's ``pair``/``id`` orbits that
    subsystem at its own ``sma``. Otherwise they are in disconnected subsystems (∞ → never merge).
    """
    def _sep(sma, ecc):
        if sma is None:
            return float("inf")
        e = ecc or 0.0
        return sma * (1.0 - e) if phase == "peri" else sma * (1.0 + e)

    if ci.get("pair") and ci.get("pair") == cj.get("pair"):
        return _sep(ci.get("sma_au"), ci.get("ecc"))
    if ci.get("orbits") and ci["orbits"] in (cj.get("pair"), cj.get("id")):
        return _sep(ci.get("sma_au"), ci.get("ecc"))
    if cj.get("orbits") and cj["orbits"] in (ci.get("pair"), ci.get("id")):
        return _sep(cj.get("sma_au"), cj.get("ecc"))
    return float("inf")


# ── zone envelope ─────────────────────────────────────────────────────────────
def _zone_envelope(members, phase):
    """Prolate envelope of a merged zone at ``phase``.

    Returns (long_axis_au, minor_axis_au, barycenter_note). ``long_axis`` is the semi-extent from the
    zone barycenter to the farthest in-domain sphere edge along the components' line =
    ``max_i(offset_i + r_i)``; ``minor_axis`` (perpendicular) = the largest in-domain sphere radius.
    The barycenter uses **every** member's real mass (out-of-domain included); an out-of-domain member
    contributes no sphere (r=0) but does shift the barycenter.
    """
    in_dom = [m for m in members if m["r_ex_au"] is not None]
    if not in_dom:
        return None, None, "no in-domain member — no sphere"
    m_tot = sum(m["mass_solar"] for m in members)

    if len(members) == 1:
        m = members[0]
        return m["r_ex_au"], m["r_ex_au"], "single component (barycenter = the star)"

    if len(members) == 2:
        a, b = members
        d = _pair_sep(a, b, phase)
        if not math.isfinite(d):
            # merged without a resolved close-pair separation — treat as concentric (offsets 0)
            long_axis = max(m["r_ex_au"] for m in in_dom)
        else:
            off_a = d * b["mass_solar"] / m_tot     # a's distance from barycenter (other mass in num.)
            off_b = d * a["mass_solar"] / m_tot
            # Only IN-DOMAIN members contribute a sphere edge to the envelope; an out-of-domain
            # member (no sphere, r=0) sets the barycenter via its real mass but its bare offset is
            # NOT an exclusion-field edge, so it must not set long_axis (matches the >2-member branch).
            reaches = [off + m["r_ex_au"]
                       for m, off in ((a, off_a), (b, off_b)) if m["r_ex_au"] is not None]
            long_axis = max(reaches)                # in_dom non-empty → reaches non-empty
        minor = max(m["r_ex_au"] for m in in_dom)
        return long_axis, minor, "mass-weighted barycenter of the two components (real masses)"

    # >2 members merged (compact multiple): best-effort — place each member at its distance from the
    # zone's mass-weighted barycenter using its closest-pair separation; the envelope is approximate
    # (members need not be collinear).
    reaches = []
    for m in in_dom:
        # distance from barycenter ≈ its separation to the nearest other member × (m_others / m_tot)
        seps = [_pair_sep(m, o, phase) for o in members if o is not m]
        d = min((s for s in seps if math.isfinite(s)), default=0.0)
        off = d * (m_tot - m["mass_solar"]) / m_tot if d else 0.0
        reaches.append(off + m["r_ex_au"])
    long_axis = max(reaches)
    minor = max(m["r_ex_au"] for m in in_dom)
    return long_axis, minor, "approximate barycenter (compact multiple, >2 members — non-collinear)"


# ── merge-grouping (union-find) ──────────────────────────────────────────────
class _UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, i):
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]
            i = self.p[i]
        return i

    def union(self, i, j):
        ri, rj = self.find(i), self.find(j)
        if ri != rj:
            self.p[ri] = rj


# ── the composition core ──────────────────────────────────────────────────────
def compose_exclusion_system(components, phase="both", alpha=_DEFAULT_ALPHA,
                             calibration_au=eb._KUIPER_EDGE_AU, dial=None,
                             beta=0.0, gamma=0.0):
    """Compose the frozen single-body generator over resolved ``components``. See the module docstring.

    ``components`` — list of dicts with (at least) ``id``, ``mass_solar`` (> 0), optional
    ``luminosity_lsun``, ``sp_type``/``class`` (drives the domain guard), and the orbital placement
    ``pair`` / ``sma_au`` / ``ecc`` / ``orbits`` / ``wind_state`` / ``mass_loss_msun_yr``. Returns the
    result dict or a curated ``{"error": str}``.
    """
    if not components:
        return {"error": "exclusion-system requires at least one --component (or a --star to resolve)."}
    if phase not in ("periastron", "apastron", "both", "peri", "apo"):
        return {"error": "--phase must be periastron, apastron, or both."}
    if alpha < 1.0 / 3.0 - 1e-9 or alpha > 0.5 + 1e-9:
        return {"error": "--alpha must be in the canon band [1/3, 1/2]."}

    comps = []
    for i, c in enumerate(components):
        cid = c.get("id") or f"component-{i + 1}"
        m = c.get("mass_solar")
        if not (isinstance(m, (int, float)) and not isinstance(m, bool) and m > 0):
            return {"error": f"component '{cid}' needs a positive mass_solar (got {m!r})."}
        domain, class_note = _component_domain(c.get("sp_type"), c.get("class"))
        comps.append({
            "id": cid, "mass_solar": float(m), "mass_provenance": c.get("mass_provenance"),
            "luminosity_lsun": c.get("luminosity_lsun"), "sp_type": c.get("sp_type"),
            "domain": domain, "class_note": class_note,
            "pair": c.get("pair"), "sma_au": c.get("sma_au"), "ecc": c.get("ecc"),
            "orbits": c.get("orbits"), "wind_state": c.get("wind_state"),
            "mass_loss_msun_yr": c.get("mass_loss_msun_yr"),
        })

    # per-component r_ex (frozen generator on the preferred mass)
    for c in comps:
        c["r_ex_au"], err = _component_rex(c, alpha, calibration_au, dial, beta, gamma)
        if err:
            return {"error": f"component '{c['id']}': {err}"}

    # merge-grouping: union over the periastron overlap test (closest approach)
    n = len(comps)
    uf = _UF(n)
    for i in range(n):
        for j in range(i + 1, n):
            d = _pair_sep(comps[i], comps[j], "peri")
            ri = comps[i]["r_ex_au"] or 0.0
            rj = comps[j]["r_ex_au"] or 0.0
            if math.isfinite(d) and d < ri + rj:
                uf.union(i, j)

    groups = {}
    for i in range(n):
        groups.setdefault(uf.find(i), []).append(comps[i])

    phases = ["periastron", "apastron"] if phase in ("both",) else \
             (["periastron"] if phase in ("periastron", "peri") else ["apastron"])
    _ph_key = {"periastron": "peri", "apastron": "apo"}

    zones = []
    for members in groups.values():
        in_dom = [m for m in members if m["r_ex_au"] is not None]
        long_axis = {}
        minor = None
        bary_note = None
        for ph in phases:
            la, mn, bn = _zone_envelope(members, _ph_key[ph])
            long_axis[ph] = la
            minor = mn if minor is None else minor
            bary_note = bn
        # point-mass corroboration: in-domain members only, never an out-of-domain mass. Pass the
        # summed in-domain luminosity + wind so a --beta run uses the real luminosities (not 1.0) and
        # a --gamma run doesn't error out → silently drop the point-mass (the per-component calls
        # already guaranteed every in-domain member carries the wind gamma needs, else compose errored).
        point_mass = None
        if in_dom:
            m_in = sum(m["mass_solar"] for m in in_dom)
            lum_in = sum((m.get("luminosity_lsun") or 0.0) for m in in_dom) or None
            wind_in = sum((m.get("mass_loss_msun_yr") or 0.0) for m in in_dom) or None
            wstate = next((m.get("wind_state") for m in in_dom if m.get("wind_state")), None)
            pm = eb.compute_exclusion_boundary(
                m_in, luminosity_lsun=(lum_in if lum_in is not None else 1.0),
                mass_loss_msun_yr=wind_in, wind_state=(wstate if wind_in is None else None),
                alpha=alpha, calibration_au=calibration_au, dial=dial, beta=beta, gamma=gamma)
            point_mass = pm.get("r_ex_au") if "error" not in pm else None
        # forcing class from the zone's representative size (the point-mass r_ex, or the single sphere)
        rep = point_mass if point_mass is not None else (in_dom[0]["r_ex_au"] if in_dom else None)
        forcing = eb._forcing_class(rep) if rep is not None else "out_of_domain"
        zones.append({
            "members": [m["id"] for m in members],
            "status": "merged" if len(members) > 1 else "separate",
            "long_axis_au": long_axis,
            "minor_axis_au": minor,
            "barycenter": bary_note,
            "components": [{
                "id": m["id"], "mass_solar": m["mass_solar"], "mass_provenance": m.get("mass_provenance"),
                "r_ex_au": m["r_ex_au"],
                "domain": "main_sequence" if m["r_ex_au"] is not None else "out_of_domain",
                "class_note": m.get("class_note"),
            } for m in members],
            "point_mass_r_ex_au": point_mass,
            "forcing_class": forcing,
        })
    # deterministic order: largest zone envelope first, then by member ids
    zones.sort(key=lambda z: (-(max((v or 0) for v in z["long_axis_au"].values()) if z["long_axis_au"] else 0),
                              z["members"]))

    # pairwise separations echo
    separations = []
    for i in range(n):
        for j in range(i + 1, n):
            dp = _pair_sep(comps[i], comps[j], "peri")
            da = _pair_sep(comps[i], comps[j], "apo")
            if math.isfinite(dp) or math.isfinite(da):
                separations.append({
                    "pair": [comps[i]["id"], comps[j]["id"]],
                    "periastron_au": dp if math.isfinite(dp) else None,
                    "apastron_au": da if math.isfinite(da) else None,
                })

    return {
        "n_components": n,
        "n_zones": len(zones),
        "phase": phase,
        "alpha": alpha,
        "dial": float(dial) if dial is not None else float(calibration_au),
        "calibration_au": calibration_au,
        "zones": zones,
        "separations_au": separations,
        "model_note": eb._MODEL_NOTE,
        "composition_note": _MODEL_NOTE_COMPOSE,
    }


# ── per-component mass resolution (CR-11.2 chain) ─────────────────────────────
def _resolve_component_mass(spec, catalog, allow_flame=True):
    """Resolve a component's preferred mass via the CR-11.2 chain. Returns
    ``(mass_solar, mass_provenance, note)`` or ``(None, None, error_str)``.

    manual ``mass`` → ``--star-mass-catalog`` (by name) → Gaia FLAME (by name, if allowed) → the
    L^0.2632 inversion from an explicit ``lum``. A pure --component with only a ``mass`` resolves as
    ``manual``; a name lets the catalog/FLAME tiers fire (so ``--star`` components carry ``catalog``).
    """
    lum = spec.get("luminosity_lsun")
    inversion = (lum ** 0.2632) if (isinstance(lum, (int, float)) and not isinstance(lum, bool)
                                    and lum > 0) else None
    name = spec.get("name") or spec.get("id")
    flame_mass = None
    manual = spec.get("mass_solar")
    manual_hit = isinstance(manual, (int, float)) and not isinstance(manual, bool) and manual > 0
    cat_hit = bool(catalog) and stellar_mass_tables.match_mass(catalog, name, spec.get("designations")) is not None
    if allow_flame and not manual_hit and not cat_hit and spec.get("designations"):
        try:
            from core import binary, catalog as catmod
            sid = binary.gaia_source_id_from_designations(spec.get("designations"))
            if sid:
                ga = catmod.gaia_astrophysical(source_id=sid)
                params = ga.get("parameters") if isinstance(ga, dict) else None
                if params:
                    mf = params.get("mass_flame")
                    if isinstance(mf, (int, float)) and not isinstance(mf, bool) and mf > 0:
                        flame_mass = mf
        except Exception:
            flame_mass = None
    block = stellar_mass.resolve_mass(
        inversion, sp_type=spec.get("sp_type") or spec.get("class"), main_id=name,
        designations=spec.get("designations"), manual_mass=manual if manual_hit else None,
        catalog=catalog, flame_mass=flame_mass)
    if block["mass_solar"] is None:
        return None, None, (f"component '{name or '?'}' has no resolvable mass "
                            "(give mass=<M☉>, a catalogued name, or lum=<L☉>)")
    return block["mass_solar"], block["mass_provenance"], block["note"]


def _parse_component_spec(s):
    """Parse a ``--component`` string 'id=A,mass=2.063,class=A0mA1Va,pair=AB,sma=19.8,ecc=0.59'
    into a spec dict. Numeric keys are coerced; unknown keys raise. Returns dict or ``{"error"}``."""
    spec = {}
    _num = {"mass", "mass_solar", "lum", "luminosity_lsun", "sma", "sma_au", "ecc",
            "mass_loss_msun_yr"}
    _alias = {"mass": "mass_solar", "lum": "luminosity_lsun", "sma": "sma_au",
              "type": "sp_type", "sptype": "sp_type"}
    _known = {"id", "name", "mass_solar", "luminosity_lsun", "sp_type", "class", "pair",
              "sma_au", "ecc", "orbits", "wind_state", "mass_loss_msun_yr"}
    for tok in str(s).split(","):
        tok = tok.strip()
        if not tok:
            continue
        if "=" not in tok:
            return {"error": f"--component token '{tok}' is not key=value."}
        k, v = tok.split("=", 1)
        k = k.strip().lower()
        key = _alias.get(k, k)
        v = v.strip()
        if k in _num or key in _num:
            try:
                v = float(v)
            except ValueError:
                return {"error": f"--component key '{k}' must be numeric (got '{v}')."}
        if key not in _known:
            return {"error": f"--component has unknown key '{k}'."}
        spec[key] = v
    return spec


def _resolve_system_from_star(star, catalog):
    """Best-effort LIVE resolution of a system name → component specs (SIMBAD + binary-orbit).

    Resolves the primary (sp_type / mass) and, from ``binary-orbit``, the orbit (sma/ecc) + companion
    mass. The companion's **domain** (WD/BD) is not carried by binary-orbit, so it is confirmed
    best-effort by a secondary ``'<name> B'`` SIMBAD lookup. Wide hierarchical companions with no
    catalogued orbit (e.g. Proxima around α Cen AB) are NOT auto-added — use ``--component`` for those.
    Returns ``(components, notes)`` or ``{"error": str}``.
    """
    from core import databases, binary
    sl = databases.compute_simbad_lookup(star)
    if isinstance(sl, dict) and "error" in sl:
        return {"error": sl["error"]}
    notes = []
    bo = binary.binary_orbit(star=star)
    solutions = bo.get("solutions", []) if isinstance(bo, dict) else []
    elements, note = binary._extract_stability_elements(solutions, {"sp_type": sl.get("sp_type")})
    prim_mass, prim_prov, _n = _resolve_component_mass(
        {"name": sl.get("main_id"), "sp_type": sl.get("sp_type"),
         "designations": sl.get("designations")}, catalog)
    if elements is None:
        # single star (no resolved orbit) — one component
        if prim_mass is None:
            return {"error": f"could not resolve a mass for '{star}': {note or 'no data'}"}
        notes.append(note or "no binary orbit resolved — treated as a single star")
        return ([{"id": sl.get("main_id") or star, "name": sl.get("main_id"),
                  "mass_solar": prim_mass, "mass_provenance": prim_prov,
                  "sp_type": sl.get("sp_type"), "designations": sl.get("designations")}], notes)
    # binary: primary A + companion B
    if prim_mass is None:
        prim_mass, prim_prov = elements["m1_solar"], "binary_orbit_m1"
    # companion domain: best-effort '<name> B' otype/sp_type lookup
    comp_sp, comp_domain_tag = None, None
    try:
        slb = databases.compute_simbad_lookup(f"{star} B")
        if isinstance(slb, dict) and "error" not in slb:
            comp_sp = slb.get("sp_type")
            otype = (slb.get("otype") or "").lower()
            if "white dwarf" in otype or (comp_sp and comp_sp.strip()[:1] == "D"):
                comp_domain_tag = "wd"
            elif "brown dwarf" in otype or (comp_sp and comp_sp.strip()[:1] in ("L", "T", "Y")):
                comp_domain_tag = "brown-dwarf"
    except Exception:
        pass
    if comp_domain_tag is None:
        notes.append(f"companion nature not confirmed (no '{star} B' WD/BD classification) — "
                     "treated as main-sequence; pass --component with class=wd/brown-dwarf to override")
    a_id = sl.get("main_id") or f"{star} A"
    comps = [
        {"id": a_id, "name": sl.get("main_id"), "mass_solar": prim_mass,
         "mass_provenance": prim_prov, "sp_type": sl.get("sp_type"),
         "designations": sl.get("designations"), "pair": "AB",
         "sma_au": elements["sma_au"], "ecc": elements["ecc"]},
        {"id": f"{star} B", "name": f"{star} B", "mass_solar": elements["m2_solar"],
         "mass_provenance": "binary_orbit_m2", "sp_type": comp_sp, "class": comp_domain_tag,
         "pair": "AB", "sma_au": elements["sma_au"], "ecc": elements["ecc"]},
    ]
    if elements.get("ecc_assumed"):
        notes.append("companion eccentricity not catalogued — assumed circular")
    return comps, notes


def compute_exclusion_system(star=None, component_specs=None, star_mass_catalog=None,
                             phase="both", alpha=_DEFAULT_ALPHA,
                             calibration_au=eb._KUIPER_EDGE_AU, dial=None, beta=0.0, gamma=0.0):
    """Entry point for ``exclusion-system``. Resolve the components (from ``--star`` live, or explicit
    ``--component`` specs) — each mass via the CR-11.2 chain — then compose. Returns the result dict
    (with a ``resolution`` note block) or a curated ``{"error": str}``.
    """
    catalog = stellar_mass_tables.load_mass_catalog(star_mass_catalog)
    if isinstance(catalog, dict) and "error" in catalog:
        return {"error": catalog["error"]}

    notes = []
    if star and component_specs:
        return {"error": "give either --star or --component blocks, not both."}
    if star:
        resolved = _resolve_system_from_star(star, catalog)
        if isinstance(resolved, dict) and "error" in resolved:
            return resolved
        components, notes = resolved
    elif component_specs:
        components = []
        for raw in component_specs:
            spec = _parse_component_spec(raw) if isinstance(raw, str) else dict(raw)
            if isinstance(spec, dict) and "error" in spec:
                return spec
            m, prov, mnote = _resolve_component_mass(spec, catalog)
            if m is None:
                return {"error": mnote}
            spec["mass_solar"] = m
            spec["mass_provenance"] = prov
            components.append(spec)
    else:
        return {"error": "exclusion-system requires --star or at least one --component."}

    result = compose_exclusion_system(components, phase=phase, alpha=alpha,
                                      calibration_au=calibration_au, dial=dial, beta=beta, gamma=gamma)
    if "error" not in result and notes:
        result["resolution_notes"] = notes
    if star and "error" not in result:
        result["star"] = star
    return result
