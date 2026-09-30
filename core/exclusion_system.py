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
import re

from core import detection
from core import exclusion_boundary as eb
from core import exclusion_wall as ew           # CR-22 wall engine + four-value classifier
from core import stellar_mass
from core import stellar_mass_tables
from core import stellar_wind                   # CR-26 per-star wind model (pure)
from core import xray_catalog                   # CR-26 orchestrator (the deterministic path never networks)

_WIDE_SMA_AU = 1000.0        # a resolved "orbit" wider than this + an invented equal-mass = a wide member

_DEFAULT_ALPHA = 0.4          # mid of the canon [1/3, 1/2] band; reproduces the hand-card anchors
# (CR-22: the off-MS tag/class-note tables moved into core.exclusion_wall — _WINDLESS_TAGS /
# _EVOLVED_TAGS / _CLASS_NOTES — the single source of truth for the four-value classifier.)

_NOTE_R11 = ("at γ > 0 the zone's point_mass_r_ex_au sums an upper-bound member rate, so it is an upper bound "
             "too")

_MODEL_NOTE_COMPOSE = (
    "CR-11.3 composition of the FROZEN single-body exclusion-boundary generator over the resolved "
    "components — no second calibration. Per-component STANDOFF r_ex is compute_exclusion_boundary on "
    "the CR-11.2-preferred mass; CR-22 gives an EVOLVED host (subgiant/giant/supergiant/AGB/WR) a "
    "standoff too, from its measured mass (standoff_note flags the out-of-canon-MS-domain use). Only "
    "windless_free_harbor (WD/BD/rogue) and unmodeled (hot subdwarf) components contribute NO sphere "
    "(r_ex_au=null; their real mass still sets the barycenter). The standoff-zone envelope is the union "
    "of standoff-bearing spheres at their barycentric offsets. CR-22 also emits a second, "
    "research-grade physical WALL per component + a parallel wall_zones merge (envelope + combined-wind "
    "on summed mass-loss). point_mass_r_ex_au corroborates over standoff-bearing members (main-sequence "
    "+ evolved); a windless/unmodeled mass is never summed in."
)


# ── domain guard (CR-22: four-value, via the shared classifier) ─────────────────
def _component_domain(sp_type=None, class_tag=None, otype=None):
    """(domain, class_note) — the CR-22 four-value domain for a component.

    Thin 2-tuple wrapper over ``exclusion_wall.classify_domain_wind`` (dropping wind_class), so every
    existing caller/unpack site is unchanged while the VALUES become the four-state enum
    ``{main_sequence, evolved, windless_free_harbor, unmodeled}`` (WB CR-22 MSG 240/242): WD/BD/rogue →
    windless_free_harbor; hot subdwarf sdB/sdO → unmodeled (honest null); cool subdwarf (lum VI),
    lum-V dwarf, Am/Ap → main_sequence; subgiant/giant/supergiant/AGB/WR → evolved. ``otype`` is
    forwarded so an AGB/Mira/WR/carbon star with a bare (lum-class-less) spectral type is classified
    evolved — never fabricated as MS (the CR-6-AMEND / CR-13-F1 off-MS-fabrication guard)."""
    dom, _wc, note = ew.classify_domain_wind(sp_type=sp_type, class_tag=class_tag, otype=otype)
    return dom, note


# ── per-component r_ex (frozen generator) ────────────────────────────────────
def _component_rex(comp, alpha, calibration_au, dial, beta, gamma, standoff_rate=None):
    """r_ex_au for a component that HAS a standoff (main_sequence OR evolved-with-a-mass) via the
    FROZEN generator, or ``None`` for windless_free_harbor / unmodeled / an evolved host with no mass.
    CR-22: an evolved host earns a standoff from its measured mass (spec CR-22.2), so only the genuinely
    boundary-less domains return ``None`` here — Sirius B (windless) stays null; a giant now gets r_ex."""
    if comp["domain"] not in (ew.MAIN_SEQUENCE, ew.EVOLVED):
        return None, None
    if comp.get("mass_solar") is None:
        return None, None                         # evolved host with no measured mass → no standoff
    # CR-26 (WB Q1): at γ > 0 a ladder tier's rate feeds the standoff (the caller passes it only then)
    ml, ws = ((standoff_rate, None) if standoff_rate is not None
              else (comp.get("mass_loss_msun_yr"), comp.get("wind_state")))
    res = eb.compute_exclusion_boundary(
        comp["mass_solar"], luminosity_lsun=comp.get("luminosity_lsun") or 1.0,
        mass_loss_msun_yr=ml, wind_state=ws,
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
# ── CR-22.5 wall geometry: a PARALLEL merge on wall overlap, distinct from the standoff merge ─────
def _comp_wind_params(comp, system_wind):
    """Per-component wall inputs (the component overrides the system-level default) for
    ``exclusion_wall.resolve_wind_inputs``."""
    sw = system_wind or {}

    def pick(key):
        v = comp.get(key)
        return v if v is not None else sw.get(key)
    return dict(mass_loss_msun_yr=comp.get("mass_loss_msun_yr"),
                wind_speed=pick("wind_speed"), v_ism=pick("v_ism"), c_ms=pick("c_ms"),
                b_field=pick("b_field"), n_cloud=pick("n_cloud"), cloud_temp=pick("cloud_temp"),
                wind_phase_yr=pick("wind_phase_yr"), f_shock=pick("f_shock"),
                m_shock_min=pick("m_shock_min"), mass_loss_source=pick("mass_loss_source"))


def _wall_envelope(members, phase):
    """Semi-extent of a group's merged WALL at ``phase`` (union of walls + orbital offsets), or
    ``None`` when the walls do NOT overlap at this phase (absence is reported, not asserted — CR-22.5)."""
    contrib = [m for m in members if m.get("wall_band_hi") is not None]
    if not contrib:
        return None
    if len(members) == 1:
        return contrib[0]["wall_band_hi"]
    m_tot = sum((m.get("mass_solar") or 0.0) for m in members) or None
    if len(members) == 2 and m_tot:
        a, b = members
        d = _pair_sep(a, b, phase)
        wa = a.get("wall_band_hi") or 0.0
        wb = b.get("wall_band_hi") or 0.0
        if math.isfinite(d):
            if d >= wa + wb:                       # walls do not overlap at this phase
                return None
            off_a = d * (b.get("mass_solar") or 0.0) / m_tot
            off_b = d * (a.get("mass_solar") or 0.0) / m_tot
            reaches = [off + m["wall_band_hi"] for m, off in ((a, off_a), (b, off_b))
                       if m.get("wall_band_hi") is not None]
            return max(reaches)
        return max(m["wall_band_hi"] for m in contrib)     # concentric (no finite separation)
    return max(m["wall_band_hi"] for m in contrib)          # >2 members: approximate union reach


def _combined_wind_wall(contrib):
    """Combined-wind wall band for a tight group: the wind-term on the SUMMED mass-loss (spec CR-22.5),
    a single value with no phase dependence; v_wind = the dominant (max-Ẇ) member's speed, and the
    medium (v_ism/c_ms/n_cloud) from that member's resolved inputs. ``None`` for a single wind source."""
    winds = [m for m in contrib if (m.get("wall_inputs") or {}).get("wdot")]
    if len(winds) < 2:
        return None, None
    dom = max(winds, key=lambda m: m["wall_inputs"]["wdot"])
    di = dom["wall_inputs"]
    sum_wdot = sum(m["wall_inputs"]["wdot"] for m in winds)
    # carry the dominant member's t_phase so the giant/astropause cap still trims an evolved combined
    # wall to ly-scale (CP3 finding 2) — a solar-class pair has t_phase=None → no cap, as before.
    w = ew.compute_wall(wdot=sum_wdot, v_wind=di["v_wind"], v_ism=di["v_ism"], c_ms=di["c_ms"],
                        n_cloud=di["n_cloud"], r_ex=None, wind_class=None, t_phase=di.get("t_phase"))
    return w.get("wall_au"), w.get("wall_band_au")


def _classify_component(c, system_wind_state=None):
    """CR-25: one component's wind classification →
    ``(classify_wind result, effective wind_state, system_flag_withheld)``.

    A component's OWN ``wind_state`` always wins. The system ``--wind-state`` (Q3b) reaches every
    MAIN-SEQUENCE component with no own ``wind_state``: it sets the bin (unless an explicit
    ``wind_class`` supersedes it — noted) and, like ``exclusion-boundary --wind-state``, the γ>0 standoff
    Ẇ. A non-MS component is not given it at all (neither the bin nor the γ>0 standoff) — noted, and
    ``system_flag_withheld`` lets the caller explain a resulting γ>0 "no wind input" error."""
    kw = dict(sp_type=c.get("sp_type"), otype=c.get("otype"), class_tag=c.get("class"),
              wind_class=c.get("wind_class"), otypes=c.get("otypes"))
    own = c.get("wind_state")
    # a recognized own wind_state is normalized ('Active' → 'active') so the FROZEN standoff accepts what
    # the classifier binned; an unrecognized one stays raw → the frozen generator's curated error, as before
    own = ew._norm_wind_state(own) or own
    sys_ws = ew._norm_wind_state(system_wind_state)
    if own or not sys_ws:
        return ew.classify_wind(wind_state=own, **kw), own, False
    cw0 = ew.classify_wind(wind_state=None, **kw)
    if cw0["domain"] != ew.MAIN_SEQUENCE:
        return dict(cw0, wind_class_note=ew.SYSTEM_NOT_APPLIED_NOTE.format(
            ws=sys_ws, host=ew._Q3A_HOST[cw0["domain"]])), None, True
    cw = ew.classify_wind(wind_state=sys_ws, **kw)
    wc = c.get("wind_class")
    if wc and str(wc).strip().lower() in ew.EMITTED_WIND_CLASSES:
        cw = dict(cw, wind_class_note=ew.SYSTEM_SUPERSEDED_NOTE.format(ws=sys_ws, wc=cw["wind_class"]))
    return cw, sys_ws, False


# ── CR-26: the per-component wind model ──────────────────────────────────────────
_TAG_WORDS = ew._WINDLESS_TAGS | ew._MS_TAGS | set(ew._EVOLVED_TAGS)


def _model_sp(c):
    """The spectral string the CR-26 model parses: ``sp_type``, else a ``class=`` that is a type (not a tag)."""
    sp = c.get("sp_type")
    if sp:
        return sp
    cl = c.get("class")
    return cl if cl and str(cl).strip().lower() not in _TAG_WORDS else None


def _component_model(c, system_wind, system_prot_days):
    """Run the CR-26 model for one classified component (``None`` for a windless / unmodeled one, or an evolved
    one without a measured row — those keep today's path). A ``--star`` component carries ``wind_inputs`` (the
    network lookups, resolved at the entry point); a plain dict takes the deterministic inputs (no network)."""
    if c["domain"] not in (ew.MAIN_SEQUENCE, ew.EVOLVED):
        return None
    sw_ = system_wind or {}
    sp = _model_sp(c)
    row = ew.wind_row_for(c.get("wind_class"), sp)
    sup = {"supplied_rate": c.get("mass_loss_msun_yr"), "log_fx": c.get("log_fx"),
           "log_fx_limit": c.get("log_fx_limit"), "radius_rsun": c.get("radius_rsun"),
           "prot_days": c.get("prot_days") if c.get("prot_days") is not None else system_prot_days,
           "wind_state": c.get("wind_state"),
           "wind_class": c.get("wind_class_explicit"), "active_otype": bool(c.get("wind_otype")),
           "mass_loss_source": c.get("mass_loss_source") or sw_.get("mass_loss_source"),
           "wind_speed": c.get("wind_speed") if c.get("wind_speed") is not None else sw_.get("wind_speed")}
    inp = c.get("wind_inputs")
    if inp is None:
        inp = xray_catalog.resolve_star_wind_inputs(
            {"sp_type": sp, "main_id": c.get("main_id"), "domain": c["domain"],
             "cr25_letter": detection._sp_letter(sp), "noncoronal_rate": row[0] if row else None,
             "notes": c.get("cr26_notes")}, sup, allow_network=False)
    else:
        for k, v in sup.items():
            if k in ("log_fx", "log_fx_limit", "radius_rsun") and v is None:
                continue
            setattr(inp, k, v)
        inp.domain, inp.cr25_letter = c["domain"], detection._sp_letter(sp)
        inp.noncoronal_rate = row[0] if row else None
        inp.notes = list(c.get("cr26_notes") or []) + list(inp.notes or [])
    m = stellar_wind.resolve_wind_model(inp)
    if c["domain"] == ew.EVOLVED and m["mass_loss_tier"] != "measured":
        h1_notes, h1_flags = stellar_wind.h1_carry(m)            # RG9: an H1 miss keeps its note + flag
        c["cr26_notes"] += [n for n in h1_notes if n not in c["cr26_notes"]]
        if h1_flags:
            c["cr26_carry_flags"] = h1_flags
        return None
    return m


def _combined_wind_band(contrib, max_standoff):
    """CR-26 §26.6 / T11 — the combined-wind wall at the summed band-edge rates (a member with no band adds its
    point to both sums; v / medium / t_phase of the largest-rate member held fixed). Returns the three zone
    fields ``{combined_wind_wall_band_wind_au, combined_wind_band_exceeds_standoff,
    combined_wind_wall_is_upper_bound}``."""
    winds = [m for m in contrib if (m.get("wall_inputs") or {}).get("wdot")]
    if len(winds) < 2:
        return {"combined_wind_wall_band_wind_au": None, "combined_wind_band_exceeds_standoff": None,
                "combined_wind_wall_is_upper_bound": None}
    if any(m.get("cr26_upper") for m in winds):
        return {"combined_wind_wall_band_wind_au": None, "combined_wind_band_exceeds_standoff": None,
                "combined_wind_wall_is_upper_bound": True}
    dom = max(winds, key=lambda m: m["wall_inputs"]["wdot"])
    di = dom["wall_inputs"]
    lo_sum = hi_sum = 0.0
    for m in winds:
        w, bd = m["wall_inputs"]["wdot"], m.get("cr26_band_dex")
        lo_sum += w * (10.0 ** bd[0] if bd else 1.0)
        hi_sum += w * (10.0 ** bd[1] if bd else 1.0)
    kw = dict(v_wind=di["v_wind"], v_ism=di["v_ism"], c_ms=di["c_ms"], n_cloud=di["n_cloud"], r_ex=None,
              wind_class=None, t_phase=di.get("t_phase"))
    lo, hi = ew.compute_wall(wdot=lo_sum, **kw), ew.compute_wall(wdot=hi_sum, **kw)
    band = [lo["wall_band_au"][0], hi["wall_band_au"][1]]
    return {"combined_wind_wall_band_wind_au": band,
            "combined_wind_band_exceeds_standoff": (bool(band[1] > max_standoff) if max_standoff is not None
                                                    else None),
            "combined_wind_wall_is_upper_bound": False}


def _measured_system_edges(comps):
    """G4 — Kislyakova's system upper edge, reported at system level when the system's components resolve."""
    out = []
    for c in comps:
        meas = ((c.get("cr26") or {}).get("wind_model") or {}).get("measured") or {}
        edge = meas.get("system_upper_edge_mdot_sun")
        if edge is None:
            continue
        head = re.sub(r"\s?[A-D]$", "", stellar_wind.swt.collapse_ws(c.get("main_id")))
        members = [o["id"] for o in comps
                   if re.sub(r"\s?[A-D]$", "", stellar_wind.swt.collapse_ws(o.get("main_id"))) == head]
        if len(members) >= 2:
            out.append({"members": members, "system_upper_edge_mdot_sun": edge, "source": "kislyakova2024"})
    return out


def _compose_arg_error(phase, alpha):
    """The compose argument checks (also run by ``compute_exclusion_system`` BEFORE any --star network
    resolution, so a bad --phase/--alpha costs no SIMBAD / Gaia call)."""
    if phase not in ("periastron", "apastron", "both", "peri", "apo"):
        return {"error": "--phase must be periastron, apastron, or both."}
    if alpha < 1.0 / 3.0 - 1e-9 or alpha > 0.5 + 1e-9:
        return {"error": "--alpha must be in the canon band [1/3, 1/2]."}
    return None


def compose_exclusion_system(components, phase="both", alpha=_DEFAULT_ALPHA,
                             calibration_au=eb._KUIPER_EDGE_AU, dial=None,
                             beta=0.0, gamma=0.0, system_wind=None, system_wind_state=None, prot_days=None):
    """Compose the frozen single-body generator over resolved ``components``. See the module docstring.

    ``components`` — list of dicts with (at least) ``id``, ``mass_solar`` (> 0), optional
    ``luminosity_lsun``, ``sp_type``/``class``/``wind_class`` (drive the domain + wind classifier), and
    the orbital placement ``pair`` / ``sma_au`` / ``ecc`` / ``orbits`` plus per-component wind inputs
    (CR-25: ``otype`` — the primary SIMBAD otype, or a ``|`` code list — and ``otypes``, the fetched full
    list). ``system_wind`` supplies system-level wall inputs (a component's own value wins);
    ``system_wind_state`` is the CR-25 system ``--wind-state`` (MS components only — see
    ``_classify_component``). Returns the result dict (standoff ``zones`` + CR-22.5 ``wall_zones``) or a
    curated ``{"error": str}``.
    """
    if not components:
        return {"error": "exclusion-system requires at least one --component (or a --star to resolve)."}
    arg_err = _compose_arg_error(phase, alpha)
    if arg_err:
        return arg_err

    comps = []
    n_comp = len(components)
    for i, c in enumerate(components):
        cid = c.get("id") or f"component-{i + 1}"
        m = c.get("mass_solar")
        # CR-22.6: finite too — the resolver already turns a non-finite `--component mass=` into the "no resolvable
        # mass" error; this backstops a directly-built component dict (inf would otherwise reach r_ex as Infinity).
        m_ok = stellar_mass_tables.is_positive_finite(m)
        cw, eff_ws, sys_withheld = _classify_component(c, system_wind_state)
        domain, wind_class, class_note = cw["domain"], cw["wind_class"], cw["class_note"]
        # CR-13 C1 → Option (A), CR-22-widened: a LONE non-main-sequence component with an unresolved
        # mass is numerically inert (windless/unmodeled carry no standoff; an evolved host with no
        # measured mass emits only the mass-free wall) — needs no mass, so flag it rather than erroring.
        lone_ood_unresolved = (n_comp == 1 and domain != ew.MAIN_SEQUENCE and not m_ok)
        m_given = isinstance(m, (int, float)) and not isinstance(m, bool)
        if not m_ok and not lone_ood_unresolved:
            if m_given and m > 0:    # CR-22.6: +inf is positive, so say what is actually wrong with it
                return {"error": f"component '{cid}' needs a finite mass_solar (got {m!r})."}
            return {"error": f"component '{cid}' needs a positive mass_solar (got {m!r})."}
        prov = c.get("mass_provenance")
        if lone_ood_unresolved and (not prov or m_given):
            # CR-22.6: a rejected numeric mass (non-finite / ≤ 0) must not keep the tier provenance it arrived with
            prov = "unresolved_out_of_domain"
        comps.append({
            "id": cid, "mass_solar": float(m) if m_ok else None,
            "mass_provenance": prov,
            "mass_note": c.get("mass_note"),   # CR-23.2 §2c (review F4): parity with exclusion-boundary
            "luminosity_lsun": c.get("luminosity_lsun"), "sp_type": c.get("sp_type"),
            "domain": domain, "wind_class": wind_class, "class_note": class_note,
            # CR-25.3 (+ MSG 266 wind_otype_source — set by the --star resolve, else null)
            "wind_class_provenance": cw["wind_class_provenance"], "wind_otype": cw["wind_otype"],
            "wind_otype_source": c.get("wind_otype_source"), "wind_class_note": cw["wind_class_note"],
            "wind_state_binned": cw["wind_state_binned"], "sys_wind_state_withheld": sys_withheld,
            "pair": c.get("pair"), "sma_au": c.get("sma_au"), "ecc": c.get("ecc"),
            "orbits": c.get("orbits"), "wind_state": eff_ws,
            "mass_loss_msun_yr": c.get("mass_loss_msun_yr"),
            # per-component wall inputs (fall back to system-level in _comp_wind_params)
            "wind_speed": c.get("wind_speed"), "v_ism": c.get("v_ism"), "c_ms": c.get("c_ms"),
            "b_field": c.get("b_field"), "n_cloud": c.get("n_cloud"),
            "cloud_temp": c.get("cloud_temp"), "wind_phase_yr": c.get("wind_phase_yr"),
            "f_shock": c.get("f_shock"), "m_shock_min": c.get("m_shock_min"),
            "mass_loss_source": c.get("mass_loss_source"),
            # CR-26 inputs (the model runs below, before the standoff — plan §5d)
            "class": c.get("class"), "main_id": c.get("main_id"), "wind_inputs": c.get("wind_inputs"),
            "log_fx": c.get("log_fx"), "log_fx_limit": c.get("log_fx_limit"),
            "radius_rsun": c.get("radius_rsun"), "prot_days": c.get("prot_days"),
            "wind_class_explicit": c.get("wind_class"), "cr26_notes": list(c.get("cr26_notes") or []),
            "sys_ws_reached": bool(eff_ws and not c.get("wind_state")),
        })

    # CR-26 — the per-component wind model (plan §5d step 2), before the standoff
    for c in comps:
        own = c.get("wind_state") if not c["sys_ws_reached"] else None
        if (own and c["domain"] in (ew.MAIN_SEQUENCE, ew.EVOLVED) and c.get("mass_solar") is not None
                and c.get("mass_loss_msun_yr") is None and own not in eb._WIND_STATE_MAP):
            # M-6 (MED-2c): a bad own wind_state is rejected at any γ (a ladder tier would otherwise hide it)
            return {"error": f"component '{c['id']}': Unknown --wind-state '{own}'. "
                             f"Choose from: {', '.join(sorted(eb._WIND_STATE_MAP))}."}
        m = _component_model(c, system_wind, prot_days)
        if m is not None and m.get("typeless"):
            c["cr26_notes"] += [n for n in m["wind_model"]["notes"] if n not in c["cr26_notes"]]
            c["cr26_carry_flags"] = list(m["wind_model"]["flags"])      # RG5: e.g. an H1 miss's not_authoritative
            m = None                                          # no spectral type at all → today's path (§26.5)
        if not stellar_wind.in_scope(c["domain"], stellar_wind.parse_sp(_model_sp(c))[0]):
            sup26 = xray_catalog.cr26_supplied(None, getter=c.get)
            if sup26["prot_days"] is None and prot_days is not None:
                sup26["prot_days"] = prot_days                # the system --prot-days reached it too
            c["cr26_notes"] += xray_catalog.ignored_input_notes(sup26)
        c["cr26"] = m
        if m and m.get("h7_letter") and c.get("wind_class_provenance") in ("class_default", "otype_auto"):
            wc = ew._COLOUR_DEFAULT_WIND.get(m["h7_letter"])      # H7 (as exclusion-boundary's _h7_cls_kw)
            if wc:
                c["wind_class"], c["wind_class_provenance"], c["wind_otype"] = wc, "class_default", None
                row = ew.wind_row_for(wc)
                ent = m["wind_model"]["tiers"].get("noncoronal_row")
                if ent is not None and row:
                    ent["mass_loss_msun_yr"] = row[0]
        c["cr26_ladder"] = bool(m and m["mass_loss_tier"] in ew.CR26_LADDER_TIERS)

    # per-component r_ex (frozen generator on the preferred mass)
    for c in comps:
        st_rate = c["cr26"]["standoff_rate"] if (c["cr26_ladder"] and gamma) else None
        if st_rate is not None and c["cr26"]["upper"]:
            c["cr26"]["wind_model"]["notes"].append(stellar_wind.NOTE_Q1_UPPER)
        c["r_ex_au"], err = _component_rex(c, alpha, calibration_au, dial, beta, gamma, standoff_rate=st_rate)
        if err:
            if c["sys_wind_state_withheld"]:
                # CR-25 Q3b: the system --wind-state was given but (by design) not fed to this non-MS
                # component — say so instead of implying the flag was missing
                err += (" — the system --wind-state reaches main-sequence components only; give this "
                        "component its own wind_state= or mass_loss_msun_yr=")
            return {"error": f"component '{c['id']}': {err}"}
        # a bin-scoped "ignored / superseded" note gains the γ>0 caveat only when the FROZEN standoff
        # actually took the wind_state (the same shared rule as exclusion-boundary)
        c["wind_class_note"] = ew.with_gamma_caveat(
            c.get("wind_class_note"), wind_state=c.get("wind_state"), binned=c["wind_state_binned"],
            gamma=gamma, mass_loss_msun_yr=(st_rate if st_rate is not None else c.get("mass_loss_msun_yr")),
            has_standoff=c["r_ex_au"] is not None)

    # per-component WALL (research-grade; composed here, the frozen generator stays pure — CR-22.5)
    for c in comps:
        wp = _comp_wind_params(c, system_wind)
        m = c["cr26"]
        tier = m["mass_loss_tier"] if m else None
        label = m.get("label") if m else None
        rw_args = (c["domain"], c["wind_class"], c.get("sp_type"))
        rw_kw = dict(tier=(tier if (c["cr26_ladder"] or tier == "none") else None),
                     tier_rate=(m["rate"] if c["cr26_ladder"] else None),
                     tier_row=((label or c["wind_class"]) if c["cr26_ladder"] else None))
        inputs, prov = ew.resolve_wind_inputs(*rw_args, **wp, **rw_kw)
        if tier is None:                                      # derived here (before the wall) for CR-31
            tier = eb.derive_mass_loss_tier(
                c["domain"], c.get("wind_class_provenance"), c.get("mass_loss_msun_yr"), c.get("wind_state"),
                inputs["wdot"], sp_type=c.get("sp_type"), class_tag=c.get("class"))
        inputs, prov, n31 = ew.cr31_wind_speed(
            tier, inputs, prov, lambda: ew.resolve_wind_inputs(*rw_args, **dict(wp, wind_speed=None), **rw_kw))
        if n31:
            c["cr26_notes"].append(n31)
        if label:
            c["wind_class"] = label                           # CR-26 §26.5: the state label
        wall = ew.compute_wall(
            wdot=inputs["wdot"], v_wind=inputs["v_wind"], v_ism=inputs["v_ism"], c_ms=inputs["c_ms"],
            n_cloud=inputs["n_cloud"], r_ex=c["r_ex_au"], wind_class=c["wind_class"],
            t_phase=inputs["t_phase"], f_shock=inputs["f_shock"], m_shock_min=inputs["m_shock_min"],
            c_ms_band=inputs["c_ms_band"]) if c["domain"] in (ew.MAIN_SEQUENCE, ew.EVOLVED) else {
                "wall_au": None, "wall_band_au": None,
                "wall_route": "none_windless" if c["domain"] == ew.WINDLESS else "none_unmodeled",
                "wall_reason": (c.get("class_note") or ("windless — free harbor"
                                if c["domain"] == ew.WINDLESS else "class outside the wind model")),
                "wall_note": ew._WALL_NOTE, "verdict_marginal": False, "r_ap_au": None}
        c["wall"] = wall
        c["wall_inputs"] = inputs if c["domain"] in (ew.MAIN_SEQUENCE, ew.EVOLVED) else None
        c["wall_prov"] = prov if c["domain"] in (ew.MAIN_SEQUENCE, ew.EVOLVED) else None
        c["wall_band_hi"] = wall["wall_band_au"][1] if wall.get("wall_band_au") else None
        exceeds, ratio = ew.hazard_flags(c["wall_band_hi"], wall.get("wall_au"), c["r_ex_au"])
        c["wall_exceeds_standoff"] = exceeds
        c["wall_to_standoff_ratio"] = ratio
        # CR-26 additive fields (§26.7) — the tier was derived above (CR-31)
        if c["domain"] in (ew.WINDLESS, ew.UNMODELED) and c.get("mass_loss_msun_yr") is not None:
            c["cr26_notes"].append(eb.NOTE_RATE_UNUSED)
        c["cr26_fields"] = eb._cr26_fields(tier, m, c["wall_inputs"], c["r_ex_au"], c["wind_class"],
                                           c["cr26_notes"], c.get("cr26_carry_flags", ()))
        c["cr26_upper"] = bool(c["cr26_fields"]["mass_loss_upper_limit"])
        c["cr26_band_dex"] = c["cr26_fields"]["mass_loss_band_dex"]

    # standoff merge-grouping: union over the periastron overlap test (closest approach)
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
        # point-mass corroboration: standoff-bearing members only (main_sequence + evolved-with-mass;
        # CR-22 MINOR-10 — evolved masses now corroborate, windless/unmodeled masses are never summed).
        point_mass = None
        if in_dom:
            m_in = sum(m["mass_solar"] for m in in_dom)
            lum_in = sum((m.get("luminosity_lsun") or 0.0) for m in in_dom) or None
            if gamma:
                # CR-26 R11 / H8: each member's standoff-input rate (a ladder tier's rate, a supplied rate, or a
                # wind_state member's legacy-map rate); an upper-bound member makes the point mass an upper bound
                def _st_in(m):
                    if m.get("cr26_ladder"):
                        return m["cr26"]["standoff_rate"] or 0.0
                    if m.get("mass_loss_msun_yr") is not None:
                        return m["mass_loss_msun_yr"]
                    return eb._WIND_STATE_MAP.get(m.get("wind_state") or "", 0.0)
                wind_in = sum(_st_in(m) for m in in_dom) or None
                wstate = None
                if len(in_dom) > 1 and any(m.get("cr26_upper") for m in in_dom):
                    for m in in_dom:                          # (a lone member's own Q1 note already says it)
                        if m.get("cr26"):
                            m["cr26"]["wind_model"]["notes"].append(_NOTE_R11)
            else:
                wind_in = sum((m.get("mass_loss_msun_yr") or 0.0) for m in in_dom) or None
                wstate = next((m.get("wind_state") for m in in_dom if m.get("wind_state")), None)
            pm = eb.compute_exclusion_boundary(
                m_in, luminosity_lsun=(lum_in if lum_in is not None else 1.0),
                mass_loss_msun_yr=wind_in, wind_state=(wstate if wind_in is None else None),
                alpha=alpha, calibration_au=calibration_au, dial=dial, beta=beta, gamma=gamma)
            point_mass = pm.get("r_ex_au") if "error" not in pm else None
        rep = point_mass if point_mass is not None else (in_dom[0]["r_ex_au"] if in_dom else None)
        if rep is not None:
            forcing = eb._forcing_class(rep)
        elif all(m["domain"] == ew.WINDLESS for m in members):
            forcing = "free_harbor"
        else:
            forcing = "out_of_domain"
        zones.append({
            "members": [m["id"] for m in members],
            "status": "merged" if len(members) > 1 else "separate",
            "long_axis_au": long_axis,
            "minor_axis_au": minor,
            "barycenter": bary_note,
            "components": [{
                "id": m["id"], "mass_solar": m["mass_solar"], "mass_provenance": m.get("mass_provenance"),
                "r_ex_au": m["r_ex_au"], "standoff_au": m["r_ex_au"],
                # CR-23.3: an EVOLVED host's standoff uses the mass-law outside its canon MS domain →
                # flag it research-grade (shared wording with exclusion-boundary two_layer); null for
                # main_sequence (the standoff IS canon) and windless/unmodeled (no standoff).
                "standoff_note": (
                    eb._EVOLVED_STANDOFF_NOTE if m["domain"] == ew.EVOLVED and m["r_ex_au"] is not None
                    else eb._EVOLVED_NO_MASS_NOTE if m["domain"] == ew.EVOLVED else None),
                "mass_note": m.get("mass_note"),   # CR-23.2 §2c (review F4): == exclusion-boundary shape
                "domain": m["domain"], "wind_class": m.get("wind_class"),
                "class_note": m.get("class_note"),
                # CR-25.3: how the wind BIN was chosen + the matched active otype codes (+ source)
                "wind_class_provenance": m.get("wind_class_provenance"), "wind_otype": m.get("wind_otype"),
                "wind_otype_source": m.get("wind_otype_source"),
                "wind_class_note": m.get("wind_class_note"),
                # CR-25.4 (WB E2): the resolved per-component Ẇ (M☉/yr) the wall used + its CR-22
                # provenance (supplied / class_default / none — as exclusion-boundary); null windless/unmodeled
                "mass_loss_msun_yr": (m["wall_inputs"]["wdot"] if m.get("wall_inputs") else None),
                "mass_loss_provenance": (m["wall_prov"].get("mass_loss") if m.get("wall_prov") else None),
                "wall_au": m["wall"].get("wall_au"), "wall_band_au": m["wall"].get("wall_band_au"),
                "wall_route": m["wall"].get("wall_route"), "wall_reason": m["wall"].get("wall_reason"),
                "wall_note": m["wall"].get("wall_note"),
                "verdict_marginal": m["wall"].get("verdict_marginal"),
                "r_ap_au": m["wall"].get("r_ap_au"),
                "wall_exceeds_standoff": m["wall_exceeds_standoff"],
                "wall_to_standoff_ratio": m["wall_to_standoff_ratio"],
                **m["cr26_fields"],                                  # CR-26 §26.7 (additive)
            } for m in members],
            "point_mass_r_ex_au": point_mass,
            "forcing_class": forcing,
        })
    # deterministic order: largest zone envelope first, then by member ids
    zones.sort(key=lambda z: (-(max((v or 0) for v in z["long_axis_au"].values()) if z["long_axis_au"] else 0),
                              z["members"]))

    # ── CR-22.5 WALL ZONES (parallel to the standoff zones): a separate union-find on wall overlap ──
    wuf = _UF(n)
    for i in range(n):
        for j in range(i + 1, n):
            d = _pair_sep(comps[i], comps[j], "peri")
            wi = comps[i]["wall_band_hi"] or 0.0
            wj = comps[j]["wall_band_hi"] or 0.0
            if math.isfinite(d) and wi and wj and d < wi + wj:
                wuf.union(i, j)
    wgroups = {}
    for i in range(n):
        wgroups.setdefault(wuf.find(i), []).append(comps[i])

    wall_zones = []
    for members in wgroups.values():
        contrib = [m for m in members if m.get("wall_band_hi") is not None]
        if not contrib:
            continue
        env = {}
        overlap_phases = []
        for ph in phases:
            la = _wall_envelope(members, _ph_key[ph]) if len(members) > 1 else None
            env[ph] = la
            if la is not None:
                overlap_phases.append(ph)
        combined_au, combined_band = _combined_wind_wall(contrib)
        # only report a wall zone where walls actually OVERLAP at a requested phase (F11 eligibility) —
        # a lone / non-overlapping wall stays on its standoff-zone component (CR-22.5). The union-find
        # groups on peri (closest approach), so in an apastron-only run a peri-only-overlap pair yields
        # no apo envelope → no wall_zone (CP4 finding 2 — no spurious phase-None combined-wind zone).
        if not overlap_phases:
            continue
        # combined_wind_phase names WHERE the combined wind is eligible (walls overlap) — F11
        # phase-eligibility; the value itself is phase-independent. overlap_phases is non-empty here
        # (a 2+-member wall group is unioned at peri → peri always overlaps).
        combined_phase = None
        if combined_au is not None and overlap_phases:
            combined_phase = "both" if len(overlap_phases) == 2 else overlap_phases[0]
        max_standoff = max((m["r_ex_au"] for m in members if m["r_ex_au"] is not None), default=None)
        env_hi = max([v for v in env.values() if v is not None] + ([combined_band[1]] if combined_band else []),
                     default=None)
        zone = {
            "members": [m["id"] for m in members],
            "wall_envelope_au": env,
            "combined_wind_wall_au": combined_au,
            "combined_wind_band_au": combined_band,
            "combined_wind_phase": combined_phase,
            "wall_exceeds_standoff": (bool(env_hi > max_standoff)
                                      if env_hi is not None and max_standoff is not None else None),
        }
        # CR-26 §26.6 / T11 — the combined-wind band fields ride wherever combined_wind_wall_au does (null with it)
        zone.update(_combined_wind_band(contrib, max_standoff) if combined_au is not None else
                    {"combined_wind_wall_band_wind_au": None, "combined_wind_band_exceeds_standoff": None,
                     "combined_wind_wall_is_upper_bound": None})
        if combined_au is not None:
            if zone["combined_wind_wall_band_wind_au"] is not None:
                for m in members:                             # disclosure item 15, on every member
                    wm = m["cr26_fields"]["wind_model"]
                    if stellar_wind.DISCLOSURES[15] not in wm["notes"]:
                        wm["notes"].append(stellar_wind.DISCLOSURES[15])
        wall_zones.append(zone)
    wall_zones.sort(key=lambda z: z["members"])

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
        "wall_zones": wall_zones,
        "measured_system_edges": _measured_system_edges(comps),     # CR-26 G4
        "separations_au": separations,
        "model_note": eb._MODEL_NOTE,
        "composition_note": _MODEL_NOTE_COMPOSE,
        # internal (popped by query.py): the components the system --wind-state reached whose rate a data tier set
        "_cr26_system_ws_unused": [c["id"] for c in comps if c.get("sys_ws_reached") and c.get("cr26")
                                   and c["cr26"].get("unused_wind_state")],
    }


# ── per-component mass resolution (CR-11.2 chain) ─────────────────────────────
def _resolve_component_mass(spec, catalog, allow_flame=True, status_out=None):
    """CR-14.3 (L7): thin delegate to the shared ``stellar_mass.resolve_component_mass`` — the single
    per-component mass chain now used by ``exclusion-system``, ``binary-stability-auto`` and the dossier
    ``multiplicity`` section (so they report the same masses for a given star). Behavior byte-identical
    to the CR-11.2/CR-13.2 body it replaced."""
    return stellar_mass.resolve_component_mass(spec, catalog, allow_flame, status_out=status_out)


def _parse_component_spec(s):
    """Parse a ``--component`` string 'id=A,mass=2.063,class=A0mA1Va,pair=AB,sma=19.8,ecc=0.59'
    into a spec dict. Numeric keys are coerced; unknown keys raise. Returns dict or ``{"error"}``."""
    spec = {}
    _num = {"mass", "mass_solar", "lum", "luminosity_lsun", "sma", "sma_au", "ecc",
            "mass_loss_msun_yr",
            # CR-22 per-component wall inputs
            "wind_speed", "v_ism", "c_ms", "b_field", "n_cloud", "cloud_temp",
            "wind_phase_yr", "f_shock", "m_shock_min",
            # CR-26 per-star wind-model inputs (their G14 ranges are exit-2-validated by query.py)
            "radius_rsun", "log_fx", "log_fx_limit", "prot_days"}
    _alias = {"mass": "mass_solar", "lum": "luminosity_lsun", "sma": "sma_au",
              "type": "sp_type", "sptype": "sp_type", "sp": "sp_type", "otype": "otype"}
    _known = {"id", "name", "mass_solar", "luminosity_lsun", "sp_type", "otype", "class", "pair",
              "sma_au", "ecc", "orbits", "wind_state", "mass_loss_msun_yr",
              # CR-22 per-component wall inputs
              "wind_class", "wind_speed", "v_ism", "c_ms", "b_field", "n_cloud", "cloud_temp",
              "wind_phase_yr", "f_shock", "m_shock_min", "mass_loss_source",
              # CR-26 (main_id= is the measured-table identity key — distinct from the free-text id / name)
              "radius_rsun", "log_fx", "log_fx_limit", "prot_days", "main_id"}
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


# ── CR-25: the ONE fetch → classify sequence for a SIMBAD-resolved star (both subcommands) ─────────
def resolve_star_wind(sp_type, otype, main_id, wind_state=None, class_tag=None, component_rule=True,
                      cw=None):
    """CR-25.2/.3 — classify a SIMBAD-resolved star's wind with its FULL otype list, fetched only where
    it can matter (MS K/M — Q1/Q6) via ``databases.fetch_star_otypes`` (bounded; degrades to the primary
    ``otype``). Shared by ``exclusion-boundary --star`` and every ``exclusion-system --star`` component
    so the two subcommands cannot drift. Returns a dict:

    * ``cls_kw`` — the pre-classified ``compute_two_layer_boundary`` kwargs (``ew.wind_cls_kw``: domain,
      wind_class, class_note, wind_class_provenance, wind_otype, wind_class_note, wind_otype_source);
    * ``otypes`` — the fetched codes (or ``None``: no fetch) for a compose component spec;
    * ``status`` — the degrade flag (``timeout``/``unreachable``/``error``) or ``None``;
    * ``fallback_to_head`` — the Q2 A-candidate did not resolve (binary component A's note);
    * ``candidate`` — the A-candidate id actually queried (or ``None``).

    ``component_rule=False`` for an already-resolved component (binary B). ``cw`` — the caller's own
    no-list ``classify_wind`` result for the SAME inputs (skips the first identity pass)."""
    from core import databases
    if cw is None:
        cw = ew.classify_wind(sp_type=sp_type, otype=otype, class_tag=class_tag, wind_state=wind_state)
    fx = None
    if cw["otype_list_relevant"] and main_id:
        fx = databases.fetch_star_otypes(main_id, primary_otype=otype, component_rule=component_rule)
        if fx is not None:
            cw = ew.classify_wind(sp_type=sp_type, otype=otype, class_tag=class_tag,
                                  wind_state=wind_state, otypes=fx["codes"])
    return {"cls_kw": ew.wind_cls_kw(cw, fx), "otypes": (fx["codes"] if fx else None),
            "status": (fx.get("status") if fx else None),
            "fallback_to_head": bool(fx and fx.get("fallback_to_head")),
            "candidate": (fx.get("candidate") if fx else None)}


# ── CR-13 --star resolution helpers (component / wide-member identity + mass quality) ────────────
def _is_secondary_component(main_id, otype=None, sp_type=None):
    """True if a resolved target names a SECONDARY component (must NOT be composed as a primary): a
    ``main_id`` ending in a space + a non-``A`` component letter (``* alf CMa B``), OR an off-MS
    otype/sp_type (a WD/BD, which resolves as its own single out-of-domain body). A primary/system head
    (``* alf Cen A`` / ``* alf Cen``) → False, so a primary-named input is not caught (WB MSG 126)."""
    if re.search(r"\s[B-Z]$", (main_id or "").strip()):
        return True
    return _classify_off_ms(otype, sp_type) is not None


def _classify_off_ms(otype=None, sp_type=None):
    """The explicit off-MS class tag (``wd`` / ``brown-dwarf``) from a SIMBAD otype or spectral type,
    else None. otype ("white dwarf"/"brown dwarf") is preferred; the degenerate ``D*`` / substellar
    ``L``/``T``/``Y`` leading letter is the fallback."""
    ot = (otype or "").lower()
    sp = (sp_type or "").strip()
    if "white dwarf" in ot or sp[:1] == "D":
        return "wd"
    if "brown dwarf" in ot or sp[:1] in ("L", "T", "Y"):
        return "brown-dwarf"
    return None


def _component_candidate_ids(system_main_id, suffix):
    """CR-14.3 (L7/M1): delegate to the shared ``stellar_mass.component_candidate_ids`` (kept under this
    name — ``test_exclusion_system.py`` calls it directly)."""
    return stellar_mass.component_candidate_ids(system_main_id, suffix)


def _augment_designations(designations, extra_ids):
    """CR-14.3 (L7/M1): delegate to the shared ``stellar_mass.augment_designations``."""
    return stellar_mass.augment_designations(designations, extra_ids)


def _select_orbit_masses(solutions, sp_type):
    """CR-14 (L1/CR-14.4): delegate to the shared ``binary.select_stability_elements`` — the single
    degenerate-q solution selector now used by the exclusion path AND ``stability_from_solutions``.
    Under CR-14.4 the pool filter narrows to **degenerate-q-only** (a clean abs-mass row is never
    dropped); the exclusion anchors are unchanged (none carries a real-SB2 + clean-abs co-occurrence).
    Returns the same ``(sel_dict | None, note)`` shape the CR-13.3 body returned — a superset dict whose
    extra ``source``/``grade``/``a_basis``/``selected_solution`` keys are additive and ignored here."""
    from core import binary
    return binary.select_stability_elements(solutions, sp_type)


def _cr26_identity(sl, *, candidate=None, sl_failed=False, component_a=False, borrow_plx=None):
    """The identity a ``--star`` component hands the CR-26 orchestrator (all SIMBAD resolution for CR-26
    happens there, behind ``allow_network``)."""
    sl = sl or {}
    own = sl.get("plx_value") if (sl.get("plx_value") or 0) > 0 else None
    plx = own or (borrow_plx if (borrow_plx or 0) > 0 else None)
    notes = []
    if own is None and plx:
        notes.append("this component has no parallax of its own — the system primary's parallax is used (a "
                      "physical companion's distance matches the primary's to far better than 1 %)")
    main_id = sl.get("main_id")
    return {"sp_type": sl.get("sp_type"), "main_id": main_id, "designations": sl.get("designations"),
            "ra": sl.get("ra"), "dec": sl.get("dec"), "d_pc": (1000.0 / plx if plx else None),
            "candidate": candidate if candidate is not None else (None if component_a else
                                                                  xray_catalog.a_candidate(main_id)),
            "sl_failed": sl_failed, "component_a": component_a, "notes": notes}


def _single_body_component(sl, catalog, star, status_out=None):
    """Resolve a single / secondary / wide-member star to ONE component via the CR-11.2 mass chain,
    wiring the bolometric-L inversion (CR-13.2 / Q2) when a **main-sequence** star has no
    manual/catalog/FLAME mass, and leaving a lone **out-of-domain** body's mass unresolved for
    compose's C1→(A) tolerance. The MS-vs-out-of-domain decision uses the SAME broad guard compose
    applies (``_component_domain`` → ``detection._host_class``: WD/BD/sdB/sdO/giant/subgiant), so an
    out-of-domain star is never given a fabricated inversion mass (plan-review F1). Returns
    ``(component_dict, mass_or_None, domain, class_note)`` or ``{"error": str}``."""
    name = sl.get("main_id") or star
    sp = sl.get("sp_type")
    class_tag = _classify_off_ms(sl.get("otype"), sp)
    spec = {"name": sl.get("main_id"), "sp_type": sp, "class": class_tag,
            "designations": _augment_designations(sl.get("designations"), {sl.get("main_id")})}
    # CR-23.2: pass status_out on the FLAME-eligible first call so a bounded single-body FLAME degrade is
    # surfaced (previously dropped). The L-inversion retry below uses allow_flame=False → never resets it.
    mass, prov, note = _resolve_component_mass(spec, catalog, status_out=status_out)
    domain, class_note = _component_domain(sp, class_tag, otype=sl.get("otype"))   # broad guard, matches compose
    if mass is None and domain == "main_sequence":
        # MS single body with no measured mass — reuse the dossier's bolometric-L inversion (Q2).
        from core import regions
        reg = regions.compute_star_system_regions_from_simbad(sl)
        if isinstance(reg, dict) and "error" not in reg and reg.get("bcLuminosity"):
            spec["luminosity_lsun"] = reg["bcLuminosity"]
            # allow_flame=False (plan-review F4): FLAME already missed above; the retry only adds the
            # L-inversion, so re-issuing the Gaia TAP call would be redundant network I/O.
            mass, prov, note = _resolve_component_mass(spec, catalog, allow_flame=False)
        if mass is None:
            return {"error": (f"could not resolve a mass for '{star}' (SIMBAD: {name}) — no catalogued "
                              "mass, no Gaia FLAME, and no usable luminosity for the MS inversion; pass "
                              "--star-mass-catalog or use --component with mass=<M☉>")}
    comp = {"id": name, "name": sl.get("main_id"), "sp_type": sp, "class": class_tag,
            # CR-25 (contract 3(b)): the primary otype rides on the component (compose's classify
            # previously saw otype=None — its WR/AGB-by-otype now agrees with the domain above)
            "otype": sl.get("otype"),
            "designations": sl.get("designations"),
            # CR-26: the resolved SIMBAD record the orchestrator needs (resolved at the entry point)
            "_cr26_identity": _cr26_identity(sl)}
    # CR-25.2: the FULL otype list — fetched only for an MS K/M body, and only now the mass resolved
    sw = resolve_star_wind(sp, sl.get("otype"), sl.get("main_id"), class_tag=class_tag)
    if sw["otypes"] is not None:
        comp["otypes"] = sw["otypes"]
    comp["wind_otype_source"] = sw["cls_kw"]["wind_otype_source"]
    if sw["status"] and status_out is not None:
        status_out["otype_status"] = sw["status"]
    if spec.get("luminosity_lsun") is not None:
        comp["luminosity_lsun"] = spec["luminosity_lsun"]
    if mass is not None:
        comp["mass_solar"] = mass
        comp["mass_provenance"] = prov
        if note:
            comp["mass_note"] = note    # CR-23.2 §2c (review F4): carry the resolver caution
    return comp, mass, domain, class_note


def _resolve_system_from_star(star, catalog):
    """CR-13 LIVE resolution of a ``--star`` name → component specs (SIMBAD + binary-orbit).

    Routes a resolved target to the right shape: a directly-named SECONDARY (``Sirius B``) or an
    off-MS body → a single out-of-domain component (CR-13.1); a single star or a wide-hierarchical
    member whose only "orbit" is a wide bond → a single body via the mass chain incl. the bolometric-L
    inversion (CR-13.1 / Q2); a close binary → primary + companion, BOTH through the per-component mass
    chain (CR-13.2, catalog matched on the per-component designation), any binary-orbit fallback mass
    flagged (CR-13.3). Never a doubled designation or a placeholder mass presented as real. Returns
    ``(components, notes)`` or ``{"error": str}``."""
    from core import databases
    sl = databases.compute_simbad_lookup(star)
    if isinstance(sl, dict) and "error" in sl:
        return {"error": sl["error"]}
    main_id = sl.get("main_id")
    notes = []

    # CR-13.1: a directly-named secondary (Sirius B → * alf CMa B) or an off-MS body → single body.
    if _is_secondary_component(main_id, sl.get("otype"), sl.get("sp_type")):
        _sf = {}                                          # CR-23.2: capture a bounded single-body FLAME degrade
        built = _single_body_component(sl, catalog, star, status_out=_sf)
        if isinstance(built, dict) and "error" in built:
            return built
        comp, mass, domain, class_note = built
        if mass is None and domain != ew.MAIN_SEQUENCE:
            notes.append(f"'{star}' is a lone {class_note or domain} component with no resolvable mass "
                         "(no catalog row, no Gaia FLAME) — the off-MS guard gives r_ex=null; pass "
                         "--star-mass-catalog for its mass")
        else:
            notes.append(f"'{star}' resolved to the single component {main_id}")
        # CR-23.2 3-tuple: surface flame_status (else {} → byte-identical to the pre-CR-23 meta);
        # CR-25: + a bounded otype-list degrade
        return [comp], notes, {k: _sf[k] for k in ("flame_status", "otype_status") if _sf.get(k)}

    # binary-orbit → real-ratio-preferring stability elements (CR-13.3)
    from core import binary
    bo = binary.binary_orbit(star=star)
    bo_status = bo.get("gaia_status") if isinstance(bo, dict) else None   # CR-19: binary-path degrade
    solutions = bo.get("solutions", []) if isinstance(bo, dict) else []
    sel, sel_note = _select_orbit_masses(solutions, sl.get("sp_type"))

    # CR-13.1 (+ defensive wide-member guard): no usable orbit, OR a very-wide invented equal-mass
    # "orbit" (a wide bond that gained a period) → single body.
    wide_member = bool(sel and sel.get("sma_au") and sel["sma_au"] > _WIDE_SMA_AU
                       and "equal-mass assumption" in (sel.get("mass_basis") or ""))
    if sel is None or wide_member:
        _sf = {}                                          # CR-23.2: capture a bounded single-body FLAME degrade
        built = _single_body_component(sl, catalog, star, status_out=_sf)
        if isinstance(built, dict) and "error" in built:
            if sel is None and sel_note:
                built = {"error": f"{built['error']} (no usable close-companion orbit: {sel_note})"}
            return built
        comp, _mass, _domain, _cn = built
        notes.append(sel_note if sel is None else
                     "only a wide hierarchical bond resolved (no close companion) — single body")
        _meta = {"gaia_status": bo_status}                 # CR-19: flag a bounded coords/NSS degrade
        if _sf.get("flame_status"):                        # CR-23.2: + a bounded single-body FLAME degrade
            _meta["flame_status"] = _sf["flame_status"]
        if _sf.get("otype_status"):                        # CR-25: + a bounded otype-list degrade
            _meta["otype_status"] = _sf["otype_status"]
        return [comp], notes, _meta

    # binary: primary A + companion B, BOTH routed through the per-component mass chain (CR-13.2).
    used_orbit = False

    prim_spec = {"name": main_id, "sp_type": sl.get("sp_type"),
                 "designations": _augment_designations(sl.get("designations"),
                                                       _component_candidate_ids(main_id, "A"))}
    _sa = {}
    prim_mass, prim_prov, prim_note = _resolve_component_mass(prim_spec, catalog, status_out=_sa)
    if prim_mass is None:
        prim_mass, prim_prov, used_orbit = sel["m1_solar"], sel["mass_prov_a"], True
        prim_note = None    # CR-23.2 §2c (review F4): orbit fallback → no resolver caution

    comp_id = next(iter(_component_candidate_ids(main_id, "B")), f"{star} B")
    comp_sl = databases.compute_simbad_lookup(comp_id)
    comp_ok = isinstance(comp_sl, dict) and "error" not in comp_sl
    comp_sp = comp_sl.get("sp_type") if comp_ok else None
    comp_otype = comp_sl.get("otype") if comp_ok else None
    comp_desig = comp_sl.get("designations") if comp_ok else None
    comp_class = _classify_off_ms(comp_otype, comp_sp)
    if comp_class is None:
        notes.append(f"companion nature not confirmed (no '{comp_id}' WD/BD classification) — treated "
                     "as main-sequence; pass --component with class=wd/brown-dwarf to override")
    comp_spec = {"name": comp_id, "sp_type": comp_sp, "class": comp_class,
                 "designations": _augment_designations(comp_desig, {comp_id})}
    _sb = {}
    comp_mass, comp_prov, comp_note = _resolve_component_mass(comp_spec, catalog, status_out=_sb)
    if comp_mass is None:
        comp_mass, comp_prov, used_orbit = sel["m2_solar"], sel["mass_prov_b"], True
        comp_note = None    # CR-23.2 §2c (review F4): orbit fallback → no resolver caution

    if used_orbit and sel.get("notes"):
        notes.extend(sel["notes"])
    if sel.get("ecc_assumed"):
        notes.append("companion eccentricity not catalogued — assumed circular")

    # Kepler-III consistency: ``_extract`` derived the binary sma from the orbit's *spectral-type-
    # estimated* masses; recompute it at the observed period from the PREFERRED (catalog/FLAME) masses
    # so the separation, barycenter and offsets all use one mass set (a ∝ M_tot^(1/3) at fixed period).
    # A no-op when both masses fell back to the orbit (pref_mtot == sel_mtot).
    sma = sel["sma_au"]
    sel_mtot = (sel.get("m1_solar") or 0.0) + (sel.get("m2_solar") or 0.0)
    pref_mtot = (prim_mass or 0.0) + (comp_mass or 0.0)
    sma = stellar_mass.recompute_sma_kepler3(sma, sel_mtot, pref_mtot)   # CR-15.3 shared helper

    # CR-25.2 (Q2): each component's OWN otype list — A via the A-candidate object of the head
    # (never a union), B its own resolved object — fetched only for an MS K/M component.
    # Component A carries NO primary otype: the head's primary is a SYSTEM-level code (it can be the
    # companion's flare code) — so a degraded A fetch falls back to nothing (the pre-CR-25 A), not to it.
    sw_a = resolve_star_wind(sl.get("sp_type"), None, main_id)
    if sw_a["fallback_to_head"]:
        notes.append(f"component A otype list taken from the system head '{main_id}' (no distinct "
                     f"'{sw_a['candidate']}' SIMBAD object)")
    sw_b = (resolve_star_wind(comp_sp, comp_otype, comp_sl.get("main_id"), class_tag=comp_class,
                              component_rule=False)
            if comp_ok else {"cls_kw": {"wind_otype_source": None}, "otypes": None, "status": None,
                             "fallback_to_head": False, "candidate": None})
    # CR-26: A is identified through its A candidate (independent of the CR-25 K/M gate; G12 falls back to the
    # head); B through the comp_sl already fetched above (a network failure → the H1 string fallback).
    comp_failed = (not comp_ok and isinstance(comp_sl, dict) and not str(comp_sl.get("error", "")).startswith(
        databases.SIMBAD_NO_RESULTS_PREFIX))
    ident_a = _cr26_identity(sl, candidate=xray_catalog.a_candidate(main_id), component_a=True)
    ident_b = _cr26_identity(comp_sl if comp_ok else {"sp_type": comp_sp},
                             candidate=(comp_id if comp_failed else ""), sl_failed=comp_failed,
                             borrow_plx=sl.get("plx_value"))
    comps = [
        {"id": main_id or f"{star} A", "name": main_id, "mass_solar": prim_mass,
         "mass_provenance": prim_prov, "mass_note": prim_note, "sp_type": sl.get("sp_type"),
         "wind_otype_source": sw_a["cls_kw"]["wind_otype_source"],
         "designations": sl.get("designations"), "pair": "AB",
         "sma_au": sma, "ecc": sel["ecc"], "_cr26_identity": ident_a},
        {"id": comp_id, "name": comp_id, "mass_solar": comp_mass, "mass_provenance": comp_prov,
         "mass_note": comp_note, "sp_type": comp_sp, "class": comp_class,
         "otype": comp_otype, "wind_otype_source": sw_b["cls_kw"]["wind_otype_source"],
         "designations": comp_desig, "pair": "AB", "sma_au": sma, "ecc": sel["ecc"], "_cr26_identity": ident_b},
    ]
    for c, sw in zip(comps, (sw_a, sw_b)):
        if sw["otypes"] is not None:
            c["otypes"] = sw["otypes"]
    # CR-19: system-level degrade meta — gaia_status (binary path) + per-component flame_status_a/_b (a
    # bounded per-component FLAME call). Surfaced on the result by compute_exclusion_system; compose
    # builds fixed per-component dicts, so these ride at the system level (matching binary-stability-auto).
    meta = {"gaia_status": bo_status}
    if _sa.get("flame_status"):
        meta["flame_status_a"] = _sa["flame_status"]
    if _sb.get("flame_status"):
        meta["flame_status_b"] = _sb["flame_status"]
    if sw_a["status"]:                                    # CR-25: per-component otype-list degrade
        meta["otype_status_a"] = sw_a["status"]
    if sw_b["status"]:
        meta["otype_status_b"] = sw_b["status"]
    return comps, notes, meta


def compute_exclusion_system(star=None, component_specs=None, star_mass_catalog=None,
                             phase="both", alpha=_DEFAULT_ALPHA,
                             calibration_au=eb._KUIPER_EDGE_AU, dial=None, beta=0.0, gamma=0.0,
                             system_wind=None, wind_state=None, prot_days=None):
    """Entry point for ``exclusion-system``. Resolve the components (from ``--star`` live, or explicit
    ``--component`` specs) — each mass via the CR-11.2 chain — then compose. Returns the result dict
    (with a ``resolution`` note block) or a curated ``{"error": str}``.
    """
    from core import stellar_wind_tables
    try:
        return _compute_exclusion_system(star, component_specs, star_mass_catalog, phase, alpha, calibration_au,
                                         dial, beta, gamma, system_wind, wind_state, prot_days)
    except stellar_wind_tables.Cr26DataError as e:       # a corrupt / missing WB data file (CR-26 §1)
        return {"error": str(e)}


def _h4_inject(spec):
    """H4 (M-8) — a ``main_id=`` measured-row hit supplies the class (``sp_type_simbad``) when the caller gave
    none; a caller's class wins, with a note if it disagrees — its ``parse_sp`` letter or its domain differs (RG2).
    Runs in the ``--component`` loop BEFORE the mass chain / domain, so an evolved row classifies as evolved."""
    mid = spec.get("main_id")
    if not mid:
        return spec
    row = stellar_wind.swt.load_cr26_tables()["MEASURED"].get(stellar_wind.swt.collapse_ws(mid))
    if row is None:
        return spec
    caller = spec.get("sp_type") or spec.get("class")
    if not caller:
        spec["sp_type"] = row["sp_type_simbad"]
        return spec
    rl = stellar_wind.parse_sp(row["sp_type_simbad"])[0]
    cl = stellar_wind.parse_sp(caller)[0] if str(caller).strip().lower() not in _TAG_WORDS else None
    rd = _component_domain(row["sp_type_simbad"], None)[0]
    cd = _component_domain(spec.get("sp_type"), spec.get("class"), spec.get("otype"))[0]   # as the component is classed
    if (cl and cl != rl) or cd != rd:                # RG2 (MSG 311): the class letter OR the domain it resolves to
        spec.setdefault("cr26_notes", []).append(
            stellar_wind.NOTE_H4.format(cc=caller, rc=row["sp_type_simbad"]))
    return spec


def _compute_exclusion_system(star, component_specs, star_mass_catalog, phase, alpha, calibration_au, dial, beta,
                              gamma, system_wind, wind_state, prot_days):
    catalog = stellar_mass_tables.load_mass_catalog(star_mass_catalog)
    if isinstance(catalog, dict) and "error" in catalog:
        return {"error": catalog["error"]}
    arg_err = _compose_arg_error(phase, alpha)          # CR-25: before any --star network resolution
    if arg_err:
        return arg_err

    notes = []
    star_meta = {}                                       # CR-19: exclusion --star degrade markers
    comp_flame = {}                                      # CR-19 (MSG 209): --component per-component FLAME degrade
    if star and component_specs:
        return {"error": "give either --star or --component blocks, not both."}
    if star:
        resolved = _resolve_system_from_star(star, catalog)
        if isinstance(resolved, dict) and "error" in resolved:
            return resolved
        components, notes, star_meta = resolved
    elif component_specs:
        components = []
        for i, raw in enumerate(component_specs):
            spec = _parse_component_spec(raw) if isinstance(raw, str) else dict(raw)
            if isinstance(spec, dict) and "error" in spec:
                return spec
            spec = _h4_inject(spec)                          # CR-26 H4 — before the mass chain / domain
            # CR-19 (WB MSG 209): uniform-surface addendum — a bounded FLAME on a mass-resolving
            # --component (a dict spec carrying `designations`; a CLI string spec carries none, so it
            # stays FLAME-free / deterministic) flags a per-component `flame_status_<a+i>` ∈
            # {timeout|unreachable}, degrade-branch-only, matching the --star C3 convention. The
            # `mass_provenance` stays the actual tier used; the universal gaia_tap `_warn` stderr fires.
            _st = {}
            m, prov, mnote = _resolve_component_mass(spec, catalog, status_out=_st)
            if _st.get("flame_status"):
                comp_flame[f"flame_status_{chr(ord('a') + i)}"] = _st["flame_status"]
            if m is None:
                # C1 → (A) parity (plan-review F2): a LONE out-of-domain component is numerically inert
                # and needs no mass — let compose's tolerance emit r_ex=null + unresolved_out_of_domain.
                # Any mass-requiring component (MS, or one of several) still errors here.
                domain, _cn = _component_domain(spec.get("sp_type"), spec.get("class"),
                                                otype=spec.get("otype"))
                if not (len(component_specs) == 1 and domain != ew.MAIN_SEQUENCE):
                    return {"error": mnote, **comp_flame}   # CR-19: a bounded FLAME → flag it on the error too
            else:
                spec["mass_solar"] = m
                spec["mass_provenance"] = prov
                if mnote:
                    spec["mass_note"] = mnote    # CR-23.2 §2c (review F4): carry the resolver caution
            components.append(spec)
    else:
        return {"error": "exclusion-system requires --star or at least one --component."}

    if star:
        # CR-26: the per-star network inputs, after the CR-23 mass + CR-25 otype resolution. The frozen
        # generator's checks run first on the standoff-bearing components (M-6: no CR-26 lookup is spent on a
        # bad --dial/--beta/…; an all-windless system keeps today's exit 0).
        for c in components:
            dom, _ = _component_domain(c.get("sp_type"), c.get("class"), otype=c.get("otype"))
            if dom in (ew.MAIN_SEQUENCE, ew.EVOLVED) and c.get("mass_solar") is not None:
                ws_c = (ew._norm_wind_state(wind_state) or wind_state) if dom == ew.MAIN_SEQUENCE else None
                err = eb.standoff_arg_error(c.get("luminosity_lsun") or 1.0, c.get("mass_loss_msun_yr"),
                                            ws_c, dial, calibration_au, alpha, beta, gamma)
                if err:
                    return {"error": f"component '{c.get('id')}': {err['error']}"}
        for c in components:
            ident = c.pop("_cr26_identity", None)
            if ident is None:
                continue
            dom, _ = _component_domain(c.get("sp_type"), c.get("class"), otype=c.get("otype"))
            if dom not in (ew.MAIN_SEQUENCE, ew.EVOLVED):
                continue
            ident = dict(ident, domain=dom, mass=c.get("mass_solar"), catalog=catalog)
            c["wind_inputs"] = xray_catalog.resolve_star_wind_inputs(
                ident, {"prot_days": prot_days}, catalog=catalog)
            c["main_id"] = c["wind_inputs"].main_id
    result = compose_exclusion_system(components, phase=phase, alpha=alpha,
                                      calibration_au=calibration_au, dial=dial, beta=beta, gamma=gamma,
                                      system_wind=system_wind, system_wind_state=wind_state, prot_days=prot_days)
    if "error" not in result and notes:
        result["resolution_notes"] = notes
    if star and "error" not in result:
        result["star"] = star
        # CR-19: degrade markers — gaia_status (binary path; a bounded coords/NSS call → the
        # single-body/no-companion verdict is degraded) + per-component flame_status_a/_b (binary mass
        # path). CR-23.2: + flame_status (a bounded FLAME on the SINGLE-body --star mass path).
        # CR-25: + otype_status (single body) / otype_status_a/_b (binary) — a bounded otype-list fetch.
        for _k in ("gaia_status", "flame_status", "flame_status_a", "flame_status_b",
                   "otype_status", "otype_status_a", "otype_status_b"):
            if star_meta.get(_k):
                result[_k] = star_meta[_k]
    if component_specs and comp_flame and "error" not in result:
        result.update(comp_flame)                        # CR-19 (MSG 209): --component FLAME degrade
    return result
