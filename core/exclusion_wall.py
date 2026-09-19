"""CR-22 — the two-layer exclusion-boundary WALL engine + domain/wind classifier.

The canon **STANDOFF** (``r_ex = 47.5·(M/M☉)^0.4``, ``core.exclusion_boundary``) is the outer,
regulated layer. This module adds the second, **research-grade physical WALL** — the deeper (inner,
SMALLER-radius) medium-readability surface where the FTL frame-lock cannot be held — plus the
tri-state (four-value) domain/wind classifier both ``exclusion-boundary`` and ``exclusion-system``
share. It is **pure math + classification**: no I/O, no network, no DB, no RNG, no time; it imports
only ``core.equations`` (physical constants), ``core.detection`` and ``core.shared`` (the existing
spectral-class primitives).

**Research-grade, not canon** (spec CR-22 §"Governing invariant"): every wall value is a **band with
an overridable default**, its provenance is echoed by the caller, ``verdict_marginal`` is set where a
verdict flips near a cut, and ``wall_note`` always carries "research-grade / non-canon". The standoff
arithmetic is untouched — this module never computes ``r_ex``.

Wall physics (brief §3b.8–§3b.9a, all constants pinned in the CR-22 spec):
  * **wind-term** (density family, always for a wind-driving body):
    ``r_wall,wind = √((Ẇ/Ẇ☉)·(v☉/v_wind)) × (4–8 AU)``  (Ẇ☉ = 2e-14 M☉/yr, v☉ = 400 km/s).
  * **bow-wave / bow-shock route** by the fast-magnetosonic Mach number ``M_f = V_ISM / c_ms``:
    - ``M_f < M_shock_min`` (default 1.5) → bow WAVE (C≈1, no deepening) → the wind term stands.
    - ``M_f ≥ M_shock_min`` and the apex ``r_ap`` clears the standoff → bow SHOCK binds → deepen
      ``r_wall,bow = r_wall,wind / √C``, ``C = 4·M_f²/(M_f²+3)`` (γ=5/3, C≤4).
  * **astropause** ``r_ap = 120 AU · √((Ẇ/Ẇ☉)·(v_wind/400)·(0.1/n_cloud)) · (26/V_ISM)``.
  * **giant/astropause cap** ``min(r_ap, v_wind·t_phase)`` — trims the naive multi-ly overshoot to the
    physical astropause (slow-wind M-giant/AGB/RSG stay ly-scale, K/G/F giants Oort-scale).
"""

import math

from core import equations as eq
from core import detection
from core import shared

# ── constants (all pinned in the CR-22 spec) ─────────────────────────────────────
_WDOT_SOLAR = 2e-14          # M☉/yr — the calibration anchor
_V_SUN = 400.0               # km/s
_WALL_BASE = (4.0, 8.0)      # AU — solar-wind wind-term base band
_R_AP_ANCHOR = 120.0         # AU — heliopause anchor in r_ap
_N_ANCHOR = 0.1              # cm⁻³ — LIC anchor in r_ap
_V_ISM_ANCHOR = 26.0         # km/s — the r_ap anchor value
_V_ISM_DEF = 26.0            # km/s — Sun–LISM inflow default
_C_MS_DEF = 20.0             # km/s — LIC-like default (Zank 2013 favored 2–3 μG)
_C_MS_BAND = (14.0, 22.5)    # km/s — favored B=2–3 μG band, for verdict_marginal
_N_CLOUD_DEF = 0.1           # cm⁻³
_CLOUD_T_DEF = 6300.0        # K
_F_SHOCK_DEF = 1.5           # Wilkin 1996 (research-grade, owed pin)
_M_SHOCK_MIN_DEF = 1.5       # ⇔ Rankine-Hugoniot C ≥ ~1.7
_GAMMA_AD = 5.0 / 3.0
_MU_I = 1.4                  # ion mean mass (Alfvén term)
_MU_C = 0.6                  # mean particle mass (sound term)

_WALL_NOTE = (
    "research-grade / non-canon: the physical WALL is a build-round medium-readability estimate "
    "(exclusion-boundary medium-physics brief §3b.8–§3b.9a, pending a Stage-2 audit), NOT the canon "
    "standoff. Every wall value is a band with overridable defaults; verdict_marginal flags a verdict "
    "near a cut. Real gravity runs the other way (external curvature LOWERS warp cost); this is a "
    "frame-readability phenomenon of the FTL mode only."
)

# ── domain enum (WB MSG 242: four values) ────────────────────────────────────────
MAIN_SEQUENCE = "main_sequence"
EVOLVED = "evolved"
WINDLESS = "windless_free_harbor"
UNMODELED = "unmodeled"       # a class outside the wind model (hot subdwarf sdB/sdO) → honest null

# ── per-class wind rows (spec CR-22.4 — Ẇ M☉/yr, v_wind km/s, t_phase yr, mass_loss_source) ──
# Keyed by internal row name; the two giant_overwindy rows share the EMITTED wind_class string
# "giant_overwindy" (colour selects the row via wind_row_for).
_WIND_ROWS = {
    "solar":             (2e-14, 400.0, None, "astrosphere_wood"),
    "quiet":             (1e-16, 400.0, None, "astrosphere_wood"),
    "active":            (1e-13, 400.0, None, "astrosphere_wood"),
    "a_dwarf":           (1e-14, 700.0, None, "recipe"),
    "f_dwarf":           (5e-15, 500.0, None, "recipe"),
    "b_hot":             (1e-8, 1200.0, None, "recipe"),
    "o_hot":             (5e-7, 1800.0, None, "recipe"),
    "wr_overwindy":      (3e-5, 2000.0, 1e5, "recipe"),
    "subgiant_mild":     (5e-14, 350.0, 1e9, "recipe"),
    "giant_mild":        (1e-10, 100.0, 1e8, "recipe"),
    "giant_overwindy_k": (1e-9, 30.0, 1e8, "recipe"),    # III/II, K
    "giant_overwindy_m": (1e-7, 15.0, 1e6, "recipe"),    # III/II, M / early-AGB
    "agb_overwindy":     (1e-6, 10.0, 1e5, "recipe"),
    "bsg_overwindy":     (1e-7, 300.0, 1e5, "recipe"),
    "rsg_overwindy":     (2e-6, 20.0, 1e5, "recipe"),
}

# EMITTED wind_class strings (what a JSON consumer sees; the K/M giant rows collapse to one name).
EMITTED_WIND_CLASSES = frozenset(
    {"giant_overwindy" if k.startswith("giant_overwindy") else k for k in _WIND_ROWS}
)

_EVOLVED_WIND_CLASSES = {"subgiant_mild", "giant_mild", "giant_overwindy",
                         "agb_overwindy", "bsg_overwindy", "rsg_overwindy", "wr_overwindy"}

_CLASS_NOTES = {
    WINDLESS: "windless (WD / brown dwarf / rogue) — free harbor, no boundary on either layer",
    UNMODELED: ("hot subdwarf — weak radiatively-driven wind, outside the current wind_class model; "
                "standoff/wall not computed"),
}


# ── the b-field → c_ms derivation (spec CR-22.4) ─────────────────────────────────
def c_ms_from_bfield(b_field_ug, n_cloud=_N_CLOUD_DEF, cloud_temp=_CLOUD_T_DEF):
    """Fast-magnetosonic speed c_ms (km/s) from the cloud B-field, plus a ±band.

    ``c_ms = √(v_A² + c_s²)`` with the Alfvén speed ``v_A = B/√(4π ρ)`` (CGS; ρ = μ_i·m_p·n) and the
    sound speed ``c_s = √(γ k T/(μ_c m_p))`` (SI). The two terms use different μ by construction
    (μ_i=1.4 He-inclusive ion mass; μ_c=0.6 mean particle mass), so the result carries a ~±2–3 km/s
    composition/convention band. Anchor: B=3 μG, n=0.095, T=6300 → v_A≈18, c_s≈12, c_ms≈20–22.
    """
    if b_field_ug is None or b_field_ug <= 0 or n_cloud is None or n_cloud <= 0 \
            or cloud_temp is None or cloud_temp <= 0:
        return None, None
    b_gauss = b_field_ug * 1e-6
    m_p_cgs = eq._M_PROTON * 1000.0          # kg → g
    rho_cgs = _MU_I * m_p_cgs * n_cloud      # g/cm³
    v_a_cms = b_gauss / math.sqrt(4.0 * math.pi * rho_cgs)   # cm/s
    v_a_kms = v_a_cms / 1e5
    c_s_ms = math.sqrt(_GAMMA_AD * eq._K_B * cloud_temp / (_MU_C * eq._M_PROTON))   # m/s
    c_s_kms = c_s_ms / 1000.0
    c_ms = math.sqrt(v_a_kms ** 2 + c_s_kms ** 2)
    return c_ms, [c_ms - 2.5, c_ms + 2.5]


# ── wind-class row resolution ────────────────────────────────────────────────────
def _emit_name(row_key):
    """Internal row key → the EMITTED wind_class string (K/M giant rows collapse to giant_overwindy)."""
    if row_key and row_key.startswith("giant_overwindy"):
        return "giant_overwindy"
    return row_key


def wind_row_for(wind_class, sp_type=None):
    """Resolve an EMITTED wind_class string → its ``(wdot, v_wind, t_phase, mass_loss_source)`` row.

    For ``giant_overwindy`` the colour (from ``sp_type``) selects the K vs M row; with no resolvable
    colour it defaults to the M row (more windy → larger wall → conservative, per WB Q3). Returns
    ``None`` for a windless/unmodeled/None wind_class (no wind row).
    """
    if not wind_class:
        return None
    if wind_class == "giant_overwindy":
        colour = detection._sp_letter(sp_type) if sp_type else None
        return _WIND_ROWS["giant_overwindy_k"] if colour == "K" else _WIND_ROWS["giant_overwindy_m"]
    return _WIND_ROWS.get(wind_class)


def _domain_for_wind_class(wc):
    """Domain implied by an explicit wind_class (never windless — windless carries wind_class=None)."""
    return EVOLVED if wc in _EVOLVED_WIND_CLASSES else MAIN_SEQUENCE


# bare --wind-state preset → an MS wind_class (used when no spectral colour resolves), so a
# --wind-state that drives the standoff also drives the wall consistently (CP2 finding 2).
_WIND_STATE_CLASS = {"quiet": "quiet", "solar": "solar", "active": "active", "hot": "o_hot"}


def _ms_wind_class(colour, wind_state=None, otype=None):
    """MS wind_class from the spectral colour (V rows). K/M default quiet → active on a flare/young flag.
    With no resolvable colour, fall back to an explicit --wind-state preset (else None → no wall)."""
    if colour == "O":
        return "o_hot"
    if colour == "B":
        return "b_hot"
    if colour == "A":
        return "a_dwarf"
    if colour == "F":
        return "f_dwarf"
    if colour == "G":
        return "solar"
    if colour in ("K", "M"):
        active = (wind_state or "").strip().lower() == "active" or _is_flare_otype(otype)
        return "active" if active else "quiet"
    return _WIND_STATE_CLASS.get((wind_state or "").strip().lower())   # no colour → wind_state or None


def _is_flare_otype(otype):
    ot = (otype or "").strip().lower()
    return "flare" in ot or "uv cet" in ot or ot in ("fl*", "uv*")


def _is_wr_otype(otype):
    ot = (otype or "").strip().lower()
    return "wolf" in ot or "wolf-rayet" in ot or ot in ("wr*", "wr")


def _is_agb_otype(otype):
    ot = (otype or "").strip().lower()
    return ("mira" in ot or "carbon star" in ot or "asymptotic" in ot
            or ot in ("mi*", "c*", "ab*"))


_WINDLESS_TAGS = {"wd", "white-dwarf", "white_dwarf", "brown-dwarf", "brown_dwarf", "bd",
                  "rogue", "rogue-planet", "rogue_planet"}
_MS_TAGS = {"main-sequence", "main_sequence", "ms", "dwarf"}
# coarse evolved tags → EMITTED wind_class (conservative where colour-ambiguous, WB Q3)
_EVOLVED_TAGS = {"subgiant": "subgiant_mild", "giant": "giant_overwindy",
                 "supergiant": "rsg_overwindy", "agb": "agb_overwindy",
                 "wolf-rayet": "wr_overwindy", "wolfrayet": "wr_overwindy", "wr": "wr_overwindy"}


# ── the tri/four-state domain + wind classifier ─────────────────────────────────
def classify_domain_wind(sp_type=None, otype=None, class_tag=None, wind_class=None,
                         object_name=None, wind_state=None):
    """``(domain, wind_class, class_note)`` — the four-value domain classifier + wind_class resolver.

    ``domain ∈ {main_sequence, evolved, windless_free_harbor, unmodeled}``. ``wind_class`` is the
    EMITTED string (or ``None`` for windless/unmodeled or a body with no resolvable colour).

    An explicit ``wind_class`` overrides the WIND ROW, but the **domain** is still taken from the
    identity (``sp_type``/``class_tag``/``object_name``) when one is present — so an O-subgiant whose
    emitted wind_class is ``o_hot`` re-classifies as ``evolved`` (not ``main_sequence``) as long as its
    sp_type rides along. Only a **bare** ``wind_class`` with no identity infers the domain from the
    wind_class (o_hot/b_hot → main_sequence by default). See CR-22.4.
    """
    dom, wc, note = _classify_identity(sp_type, otype, class_tag, object_name, wind_state)
    if wind_class:
        w = str(wind_class).strip().lower()
        if w in EMITTED_WIND_CLASSES:
            if dom is None or dom in (WINDLESS, UNMODELED):
                # no identity signal (or a windless/unmodeled one the user is overriding) →
                # infer the domain from the explicit wind_class
                return _domain_for_wind_class(w), w, (note if dom is None else None)
            return dom, w, note                  # identity present → keep its domain, override the row
    if dom is None:
        # a bare mass (no identity): MS, with a wall only if a --wind-state preset was given
        return MAIN_SEQUENCE, _ms_wind_class(None, wind_state, otype), None
    return dom, wc, note


def _classify_identity(sp_type, otype, class_tag, object_name, wind_state):
    """Domain + wind_class from IDENTITY only (no explicit wind_class override). Returns
    ``(None, None, None)`` when there is no identity signal at all (a bare ``--mass-msun``)."""
    # object-name presets
    obj = (object_name or "").strip().lower()
    if obj in ("brown-dwarf", "brown_dwarf", "rogue-planet", "rogue_planet", "rogue"):
        return WINDLESS, None, _CLASS_NOTES[WINDLESS]

    # explicit class_tag (from --component class=)
    if class_tag:
        t = str(class_tag).strip().lower()
        if t in _WINDLESS_TAGS:
            return WINDLESS, None, _CLASS_NOTES[WINDLESS]
        if t in _EVOLVED_TAGS:
            return EVOLVED, _EVOLVED_TAGS[t], None
        if t in _MS_TAGS:
            return MAIN_SEQUENCE, _ms_wind_class(detection._sp_letter(sp_type), wind_state, otype), None
        sp_type = sp_type or class_tag           # else treat the tag as a spectral type

    # otype-driven evolved classes (WR / AGB carry no unambiguous sp_type luminosity class)
    if _is_wr_otype(otype):
        return EVOLVED, "wr_overwindy", "Wolf-Rayet"
    if _is_agb_otype(otype):
        return EVOLVED, "agb_overwindy", "AGB / Mira / carbon star"

    sp = (sp_type or "").strip()
    if not sp:
        return None, None, None                  # no identity signal → let the caller default to MS

    # WR (WN/WC/WO) and carbon (C-*) recognized from the SPECTRAL TYPE itself (no otype needed) —
    # the leading display class covers W/C, which detection._sp_letter (OBAFGKM only) does not.
    lead = shared.spectral_leading_class(sp, letters=shared._SP_DISPLAY_LETTERS)
    if lead == "W":
        return EVOLVED, "wr_overwindy", "Wolf-Rayet"
    if lead == "C":
        return EVOLVED, "agb_overwindy", "carbon star"

    host = detection._host_class(sp)
    colour = detection._sp_letter(sp)

    if host in ("white_dwarf", "brown_dwarf"):
        return WINDLESS, None, _CLASS_NOTES[WINDLESS]

    if host == "subdwarf":
        # WB MSG 242 Item 2 — split the lump: hot sdB/sdO (colour O/B) vs cool lum-VI (colour A–M).
        if colour in ("O", "B"):
            return UNMODELED, None, _CLASS_NOTES[UNMODELED]
        # cool subdwarf (lum VI) → a metal-poor MAIN-SEQUENCE fusing star with a wind (NO standoff_note)
        return MAIN_SEQUENCE, _ms_wind_class(colour or "K", wind_state, otype), "cool subdwarf"

    if host == "subgiant":                       # lum IV
        # spec table exception: O/B at IV keep the hot line-driven wind (WB MSG 242 Item 1)
        if colour == "O":
            return EVOLVED, "o_hot", "O subgiant"
        if colour == "B":
            return EVOLVED, "b_hot", "B subgiant"
        return EVOLVED, "subgiant_mild", "subgiant"

    if host == "giant":                          # lum I/II/III (collapsed by _host_class)
        m = detection._LUM_CLASS_RE.search(sp)
        lc = m.group(1) if m else "III"
        if lc == "I":                            # supergiant
            wc = "rsg_overwindy" if colour in ("K", "M") else "bsg_overwindy"
            return EVOLVED, wc, "supergiant"
        # bright giant / giant (II/III)
        if colour == "O":
            return EVOLVED, "o_hot", "hot giant"
        if colour == "B":
            return EVOLVED, "b_hot", "hot giant"
        if colour in ("K", "M"):
            return EVOLVED, "giant_overwindy", ("M giant" if colour == "M" else "K giant")
        return EVOLVED, "giant_mild", "giant"    # A/F/G (and no-colour) → the mild row

    # main sequence (lum V or no luminosity class). A cool subdwarf carried as an sd/esd/usd PREFIX
    # (sdM1/sdK/sdG…, no roman lum class) gets the same "cool subdwarf" class_note as the lum-VI form
    # and the --star (Kapteyn's) path — the classification stays main_sequence + the colour wind_class
    # (WB MSG 244 consistency fix; hot sdB/sdO were already routed to unmodeled above).
    ms_note = "cool subdwarf" if (sp[:3] in ("esd", "usd") or sp[:2] == "sd") else None
    return MAIN_SEQUENCE, _ms_wind_class(colour, wind_state, otype), ms_note


# ── the wall (spec CR-22.3) ──────────────────────────────────────────────────────
def compute_wall(wdot, v_wind, v_ism=_V_ISM_DEF, c_ms=_C_MS_DEF, n_cloud=_N_CLOUD_DEF,
                 r_ex=None, wind_class=None, t_phase=None, f_shock=_F_SHOCK_DEF,
                 m_shock_min=_M_SHOCK_MIN_DEF, c_ms_band=_C_MS_BAND):
    """The research-grade physical WALL for a wind-driving body. See the module docstring.

    ``r_ex`` is the body's STANDOFF (for the bow-shock binding test); ``None`` when no standoff exists
    (an evolved host with no measured mass) → the shock test is "untested". Returns the wall dict
    (``wall_au`` scalar midpoint | ``None``, ``wall_band_au``, ``wall_route``, ``wall_reason``,
    ``wall_note``, ``verdict_marginal``, ``r_ap_au``).
    """
    if not wdot or wdot <= 0 or not v_wind or v_wind <= 0:
        return {"wall_au": None, "wall_band_au": None, "wall_route": "none_no_wind",
                "wall_reason": "no wind input — wall needs a wind_class or a mass-loss rate",
                "wall_note": _WALL_NOTE, "verdict_marginal": False, "r_ap_au": None}
    if not v_ism or v_ism <= 0 or not c_ms or c_ms <= 0 or not n_cloud or n_cloud <= 0:
        return {"wall_au": None, "wall_band_au": None, "wall_route": "none_no_wind",
                "wall_reason": "invalid medium inputs — v_ism / c_ms / n_cloud must be > 0",
                "wall_note": _WALL_NOTE, "verdict_marginal": False, "r_ap_au": None}

    ratio = wdot / _WDOT_SOLAR
    base = math.sqrt(ratio * (_V_SUN / v_wind))
    wt = [base * _WALL_BASE[0], base * _WALL_BASE[1]]
    r_ap = _R_AP_ANCHOR * math.sqrt(ratio * (v_wind / _V_SUN) * (_N_ANCHOR / n_cloud)) \
        * (_V_ISM_ANCHOR / v_ism)
    m_f = v_ism / c_ms
    c_compress = 4.0 * m_f ** 2 / (m_f ** 2 + 3.0)      # γ=5/3, ≤4

    verdict_marginal = False
    # honesty band: does M_f over the favored c_ms band straddle M_shock_min? Only meaningful when the
    # operating c_ms sits within that LIC band — a user-committed c_ms outside it has resolved the
    # uncertainty the band represents (finding CP1-7), so the straddle is not applied there.
    if c_ms_band and c_ms_band[0] <= c_ms <= c_ms_band[1]:
        lo, hi = c_ms_band
        if (v_ism / hi) < m_shock_min < (v_ism / lo):
            verdict_marginal = True

    # route selection
    if m_f < m_shock_min:
        route, reason, band = "wind_term", "bow wave (M_f<M_shock_min, C≈1)", list(wt)
    elif r_ex is not None and r_ap > r_ex:
        route, reason = "bow_shock", "bow shock binds (r_ap>r_ex)"
        band = [wt[0] / math.sqrt(c_compress), wt[1] / math.sqrt(c_compress)]
    elif r_ex is not None and r_ap <= r_ex < f_shock * r_ap:
        route, reason = "bow_shock_marginal", "bow shock binds marginally (r_ap≤r_ex<f·r_ap)"
        band = [wt[0] / math.sqrt(c_compress), wt[1] / math.sqrt(c_compress)]
        verdict_marginal = True
    elif r_ex is None:
        route, reason, band = "wind_term", \
            "shock exists but binding untested — no standoff (bow-shock-untested-no-standoff)", list(wt)
    else:
        route, reason, band = "wind_term", \
            "shock apex inside standoff (f·r_ap≤r_ex) — wind term stands", list(wt)

    # f·r_ap within ~10% of r_ex → marginal
    if r_ex is not None and r_ex > 0 and abs(f_shock * r_ap - r_ex) <= 0.10 * r_ex:
        verdict_marginal = True

    # giant / astropause cap (trims the naive overshoot to the physical astropause)
    cap, cap_route = r_ap, "capped_astropause"
    if t_phase is not None and t_phase > 0:
        wind_time_au = (v_wind * 1000.0 * t_phase * eq._SEC_PER_YEAR) / eq._M_PER_AU
        if wind_time_au < cap:
            cap, cap_route = wind_time_au, "capped_windtime"
    if band[1] > cap:
        band = [min(band[0], cap), cap]
        route = cap_route
        reason = ("capped at the astropause r_ap (naive multi-ly overshoot trimmed)"
                  if cap_route == "capped_astropause"
                  else "capped at the wind-time bound v_wind·t_phase (naive overshoot trimmed)")

    return {"wall_au": 0.5 * (band[0] + band[1]), "wall_band_au": [band[0], band[1]],
            "wall_route": route, "wall_reason": reason, "wall_note": _WALL_NOTE,
            "verdict_marginal": verdict_marginal, "r_ap_au": r_ap}


def resolve_wind_inputs(domain, wind_class, sp_type=None, *,
                        mass_loss_msun_yr=None, wind_speed=None, v_ism=None, c_ms=None,
                        b_field=None, n_cloud=None, cloud_temp=None, wind_phase_yr=None,
                        f_shock=None, m_shock_min=None, mass_loss_source=None):
    """Resolve the wall's wind/medium inputs to concrete values + a parallel provenance dict.

    Precedence per field: an explicit value → the wind_class row default → the module default. The
    **velocity double-handling rule** (spec CR-22.4): when the mass-loss source is ``astrosphere_wood``
    (Wood 2005's uniform-400 astrosphere calibration), v_wind is FORCED to 400 and a supplied
    ``wind_speed`` is ignored (provenance ``astrosphere_wood_forced``). Returns ``(inputs, prov)`` —
    ``inputs`` carries wdot/v_wind/t_phase/v_ism/c_ms/n_cloud/cloud_temp/f_shock/m_shock_min/
    mass_loss_source (+ ``c_ms_band`` = the FIXED favored band for verdict_marginal, and
    ``c_ms_band_derived`` when b-field-derived); each provenance ∈ {supplied, class_default,
    b_field_derived, assumed, astrosphere_wood_forced, none}.
    """
    row = wind_row_for(wind_class, sp_type)      # (wdot, v_wind, t_phase, src) or None
    prov = {}

    if mass_loss_msun_yr is not None:
        wdot, prov["mass_loss"] = mass_loss_msun_yr, "supplied"
    elif row:
        wdot, prov["mass_loss"] = row[0], "class_default"
    else:
        wdot, prov["mass_loss"] = None, "none"

    if mass_loss_source:
        src, prov["mass_loss_source"] = mass_loss_source, "supplied"
    elif row:
        src, prov["mass_loss_source"] = row[3], "class_default"
    else:
        src, prov["mass_loss_source"] = "recipe", "assumed"

    # double-handling: astrosphere_wood forces v_wind=400 — but only when the source was EXPLICITLY
    # set (spec validation #4) or no --wind-speed was given; an explicit --wind-speed over a merely
    # CLASS-DEFAULT astrosphere_wood source is honored, not silently discarded (CP4 finding 1).
    force_wood = (src == "astrosphere_wood"
                  and (prov["mass_loss_source"] == "supplied" or wind_speed is None))
    if force_wood:
        v_wind, prov["wind_speed"] = 400.0, "astrosphere_wood_forced"
    elif wind_speed is not None:
        v_wind, prov["wind_speed"] = wind_speed, "supplied"
    elif row:
        v_wind, prov["wind_speed"] = row[1], "class_default"
    else:
        v_wind, prov["wind_speed"] = None, "none"
    # CP2 finding 4: a supplied Ẇ with no resolvable wind speed still gets a wall — assume the solar
    # 400 km/s rather than silently dropping to none_no_wind.
    if v_wind is None and wdot is not None:
        v_wind, prov["wind_speed"] = _V_SUN, "assumed"

    if wind_phase_yr is not None:
        t_phase, prov["wind_phase"] = wind_phase_yr, "supplied"
    elif row:
        t_phase, prov["wind_phase"] = row[2], "class_default"
    else:
        t_phase, prov["wind_phase"] = None, "none"

    if v_ism is not None:
        vi, prov["v_ism"] = v_ism, "supplied"
    else:
        vi, prov["v_ism"] = _V_ISM_DEF, "assumed"

    nc = n_cloud if n_cloud is not None else _N_CLOUD_DEF
    prov["n_cloud"] = "supplied" if n_cloud is not None else "assumed"
    ct = cloud_temp if cloud_temp is not None else _CLOUD_T_DEF
    prov["cloud_temp"] = "supplied" if cloud_temp is not None else "assumed"

    band_derived = None
    if b_field is not None:
        cms, band_derived = c_ms_from_bfield(b_field, nc, ct)
        if cms is not None:
            prov["c_ms"] = "b_field_derived"
        elif c_ms is not None:                    # a bad --b-field falls back to an explicit --c-ms
            cms, prov["c_ms"] = c_ms, "supplied"
        else:
            cms, prov["c_ms"] = _C_MS_DEF, "assumed"
    elif c_ms is not None:
        cms, prov["c_ms"] = c_ms, "supplied"
    else:
        cms, prov["c_ms"] = _C_MS_DEF, "assumed"

    fs = f_shock if f_shock is not None else _F_SHOCK_DEF
    prov["f_shock"] = "supplied" if f_shock is not None else "assumed"
    ms = m_shock_min if m_shock_min is not None else _M_SHOCK_MIN_DEF
    prov["m_shock_min"] = "supplied" if m_shock_min is not None else "assumed"

    # verdict_marginal straddles over the DERIVED band when c_ms came from a B-field (its own ±
    # uncertainty), else the fixed favored LIC band (CP4 finding 3).
    return ({"wdot": wdot, "v_wind": v_wind, "t_phase": t_phase, "v_ism": vi, "c_ms": cms,
             "n_cloud": nc, "cloud_temp": ct, "f_shock": fs, "m_shock_min": ms,
             "mass_loss_source": src, "b_field": b_field,
             "c_ms_band": (band_derived if band_derived else _C_MS_BAND),
             "c_ms_band_derived": band_derived}, prov)


def hazard_flags(wall_band_hi, wall_au, standoff_au):
    """``(wall_exceeds_standoff, wall_to_standoff_ratio)`` — the load-bearing CR-22 hazard driver.

    ``wall_exceeds_standoff`` compares the wall's OUTER (band-hi) edge to the standoff (spec: "true at
    band-hi"); the ratio uses the wall midpoint. Both ``None`` if either layer is ``None``.
    """
    if wall_band_hi is None or standoff_au is None or standoff_au <= 0:
        return None, None
    return bool(wall_band_hi > standoff_au), (wall_au / standoff_au if wall_au is not None else None)
