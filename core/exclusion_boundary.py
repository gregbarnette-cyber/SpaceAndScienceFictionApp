"""Phase AK (Group Q) — FTL exclusion-boundary (r_ex / "Alcubierre Limit") calculator (Pkt 26.5).

One ``query.py``-only, pure-math, self-validating (Phase-H/P contract) calculator for the sibling
``scifiWorldBuilding-Claude`` repo: the FTL exclusion-boundary radius **r_ex** — the harbor mouth
inside which FTL cannot lock the local foliation — so Packet 26.5 can produce per-star-type r_ex
tables as a population pull over the census and classify the graded-forcing geography.

**In-universe (Rung-3) mechanism, NOT established science** (canon
``metric-drive-and-ftl-causality-architecture.md`` §Exclusion Boundary): the boundary is a
**readability floor**, not energy physics — FTL needs a lock on the local foliation value, and the
lock's signal-to-noise is corrupted by the body's baryonic environment (wind, plasma density,
magnetization, turbulence — the medium is the noise, the scaffolding is the signal). Boundary size
scales with the body's mass, luminosity, and wind state and is calibrated near Sol's Kuiper edge:

    r_ex = DIAL · (M/M_sun)^alpha · (L/L_sun)^beta · (Ẇ/Ẇ_sun)^gamma

  * ``alpha``  — mass exponent, canon-bounded to [1/3, 1/2]; default 1/3 (``--scan-alpha`` reports both edges).
  * ``beta``   — luminosity exponent; default 0 (off) — luminosity enters chiefly through the wind term.
  * ``gamma``  — wind exponent; default 0 (off) unless a wind input is given.
  * ``DIAL``   — the required-breakthrough calibration constant; when ``--dial`` is not given it is
    auto-set to ``--calibration-au`` (default 47.5 AU, the Kuiper-edge anchor), so the Sun row lands
    exactly on the anchor and every other body scales off it.

Every exponent/coupling is caller-overridable — this is the Rung-3 surface Pkt 26.5 calibrates.
No network, no DB, no numpy, no RNG, no time.
"""

import math

from core import exclusion_wall as ew

# ── Wind Ẇ presets (M_sun/yr — observational/first-principles ancestors, overridable) ──
_WDOT_SOLAR = 2e-14                     # Sun, calibration anchor (Wang 1998 / textbook solar-wind flux)
_WIND_PRESETS = {
    "solar":       2e-14,              # G — the calibration anchor
    "m-dwarf":     1e-13,              # active M; wind variable, astrosphere-dominant (Wood 2002/2005)
    "hot":         1e-6,               # O/B radiatively-driven winds 1e-7..1e-5 (Vink 2000/2001)
    "giant/agb":   1e-6,              # evolved; out of the settleable set, for completeness
    "brown-dwarf": 1e-16,             # ≪ solar; boundary is mass-floored
}
# --wind-state {quiet|solar|active|hot} → a Ẇ preset when the rate is unknown.
_WIND_STATE_MAP = {
    "quiet":  1e-16,
    "solar":  2e-14,
    "active": 1e-13,
    "hot":    1e-6,
}

# ── object presets: name -> (mass_msun, luminosity_lsun, mass_loss_msun_yr) ──
_OBJECT_PRESETS = {
    "sun":         (1.0,    1.0,     2e-14),
    "m-dwarf":     (0.3,    0.02,    1e-13),
    "o-star":      (20.0,   1e5,     1e-6),
    "brown-dwarf": (0.05,   1e-5,    1e-16),
    "rogue-planet": (0.001,  0.0,    0.0),
}

_KUIPER_EDGE_AU = 47.5                  # canon outer-system-boundaries 42.4–47.5 AU

# ── graded-forcing bands on the primary r_ex (provisional; Pkt-26.5-tunable) ──
_OPTIONAL_MAX_AU = 10.0                 # below ordinary safety margins → optional stop
_HARBOR_MIN_AU = 95.0                   # ≈2× Sol → destination harbor mouth

_MODEL_NOTE = (
    "IN-UNIVERSE (Rung-3) BOUNDARY MECHANISM, not established science: a medium-noise SNR floor on "
    "the drive's foliation-lock readability (canon metric-drive-and-ftl-causality-architecture.md "
    "§Exclusion Boundary). The DIAL is a required-breakthrough constant; the scaling exponents and "
    "per-star-type values are a Packet-26.5 research output, not physics. Calibrated so r_ex(Sun) = "
    "the Kuiper-edge anchor (default 47.5 AU) — a LABELED DIAL, not a measured constant (canon "
    "decisions.md 2026-07-12 ruling 4). Real gravity runs the OTHER way (external curvature LOWERS "
    "warp cost — Gomez-Zorrilla 2024); this boundary is a frame-readability phenomenon of the FTL "
    "mode ONLY — the subluminal mode is not bounded. forcing_class bands are provisional "
    "(optional < %.0f AU, harbor ≥ %.0f AU) and caller-tunable." % (_OPTIONAL_MAX_AU, _HARBOR_MIN_AU)
)


def _forcing_class(r_ex_au):
    if r_ex_au < _OPTIONAL_MAX_AU:
        return "optional"
    if r_ex_au >= _HARBOR_MIN_AU:
        return "harbor"
    return "checkpoint"


def compute_exclusion_boundary(
        mass_msun, luminosity_lsun=1.0, mass_loss_msun_yr=None, wind_state=None,
        dial=None, calibration_au=_KUIPER_EDGE_AU, alpha=1.0 / 3.0, beta=0.0, gamma=0.0,
        scan_alpha=False, object_name=None):
    """FTL exclusion-boundary radius r_ex for a body. See the module docstring.

    Returns the JSON result dict, or a curated ``{"error": str}`` on M ≤ 0, out-of-band exponents,
    or a wind exponent set without a wind input.
    """
    # ── validation ──
    if mass_msun is None or mass_msun <= 0:
        return {"error": "--mass-msun (or a resolved object mass) must be > 0."}
    if calibration_au is None or calibration_au <= 0:
        return {"error": "--calibration-au must be > 0."}
    if dial is not None and dial <= 0:
        return {"error": "--dial must be > 0."}
    if alpha < 0 or beta < 0 or gamma < 0:
        return {"error": "Scaling exponents (--alpha/--beta/--gamma) must be ≥ 0."}
    if beta != 0.0 and (luminosity_lsun is None or luminosity_lsun <= 0):
        return {"error": "--luminosity-lsun must be > 0 when --beta ≠ 0."}

    # ── wind input ──
    wdot = None
    if mass_loss_msun_yr is not None:
        if mass_loss_msun_yr <= 0:
            return {"error": "--mass-loss-msun-yr must be > 0."}
        wdot = float(mass_loss_msun_yr)
    elif wind_state is not None:
        if wind_state not in _WIND_STATE_MAP:
            return {"error": f"Unknown --wind-state '{wind_state}'. "
                             f"Choose from: {', '.join(sorted(_WIND_STATE_MAP))}."}
        wdot = _WIND_STATE_MAP[wind_state]
    if gamma != 0.0 and wdot is None:
        return {"error": "wind exponent set without --mass-loss-msun-yr/--wind-state"}

    # ── DIAL (explicit, else auto-calibrated to the Kuiper-edge anchor) ──
    DIAL = float(dial) if dial is not None else float(calibration_au)

    lum = luminosity_lsun if luminosity_lsun is not None else 1.0
    lum_term = lum ** beta if beta != 0.0 else 1.0
    wind_term = (wdot / _WDOT_SOLAR) ** gamma if gamma != 0.0 else 1.0

    def r_ex_at(a):
        return DIAL * (mass_msun ** a) * lum_term * wind_term

    r_ex_au = r_ex_at(alpha)

    result = {
        "r_ex_au": r_ex_au,
        "mass_msun": mass_msun,
        "luminosity_lsun": lum,
        "mass_loss_msun_yr": wdot,
        "dial": DIAL,
        "alpha": alpha,
        "beta": beta,
        "gamma": gamma,
        "calibration_au": calibration_au,
        "forcing_class": _forcing_class(r_ex_au),
        "object": object_name,
        "model_note": _MODEL_NOTE,
    }

    if scan_alpha:
        result["r_ex_au_alpha_third"] = r_ex_at(1.0 / 3.0)
        result["r_ex_au_alpha_half"] = r_ex_at(0.5)

    return result


# ── CR-22: the two-layer orchestrator (frozen r_ex generator above + the research-grade WALL) ──
_EVOLVED_STANDOFF_NOTE = (
    "mass-law applied outside its canon MS domain (canon: MS-only); research-grade / regulatory "
    "assumption — the standoff for an evolved host uses the measured mass, not an MS luminosity "
    "inversion")
_EVOLVED_NO_MASS_NOTE = (
    "no measured mass for an evolved host — standoff not computed; pass --star-mass-catalog or "
    "--mass-msun (the wind-term wall is still emitted)")


def _wind_echo(inputs, prov):
    """Flatten the resolved wind inputs + provenance into the additive echo fields (spec CR-22.4)."""
    echo = {
        "mass_loss_msun_yr": inputs["wdot"], "mass_loss_provenance": prov.get("mass_loss"),
        "wind_speed_kms": inputs["v_wind"], "wind_speed_provenance": prov.get("wind_speed"),
        "v_ism_kms": inputs["v_ism"], "v_ism_provenance": prov.get("v_ism"),
        "c_ms_kms": inputs["c_ms"], "c_ms_provenance": prov.get("c_ms"),
        "n_cloud_cm3": inputs["n_cloud"], "n_cloud_provenance": prov.get("n_cloud"),
        "cloud_temp_k": inputs["cloud_temp"], "cloud_temp_provenance": prov.get("cloud_temp"),
        "wind_phase_yr": inputs["t_phase"], "wind_phase_provenance": prov.get("wind_phase"),
        "f_shock": inputs["f_shock"], "f_shock_provenance": prov.get("f_shock"),
        "m_shock_min": inputs["m_shock_min"], "m_shock_min_provenance": prov.get("m_shock_min"),
        "mass_loss_source": inputs["mass_loss_source"],
        "mass_loss_source_provenance": prov.get("mass_loss_source"),
    }
    if inputs.get("b_field") is not None:
        echo["b_field_ug"] = inputs["b_field"]
        echo["c_ms_band_derived"] = inputs.get("c_ms_band_derived")
    return echo


def compute_two_layer_boundary(mass_msun=None, luminosity_lsun=None, *,
                               sp_type=None, otype=None, class_tag=None, object_name=None,
                               domain=None, wind_class=None, class_note=None, mass_provenance=None,
                               mass_note=None,
                               wind_state=None, mass_loss_msun_yr=None, wind_speed=None,
                               v_ism=None, c_ms=None, b_field=None, n_cloud=None, cloud_temp=None,
                               wind_phase_yr=None, f_shock=None, m_shock_min=None,
                               mass_loss_source=None, dial=None, calibration_au=_KUIPER_EDGE_AU,
                               alpha=1.0 / 3.0, beta=0.0, gamma=0.0, scan_alpha=False,
                               otypes=None, wind_class_provenance=None, wind_otype=None,
                               wind_class_note=None, wind_otype_source=None, wind_state_binned=None):
    """CR-22 two-layer boundary: the unchanged canon STANDOFF (the FROZEN
    ``compute_exclusion_boundary`` above) + the research-grade physical WALL
    (``exclusion_wall.compute_wall``), with the four-value domain classifier + free-harbor guard.

    Classification is done here (``exclusion_wall.classify_wind``, honoring ``wind_state`` and the
    CR-25 full otype list ``otypes``) unless ``domain`` is passed pre-classified by the caller. **A
    pre-classifying caller owns the CR-25 wind fields** — it must pass them all
    (``exclusion_wall.wind_cls_kw`` builds the set: ``wind_class_provenance`` / ``wind_otype`` /
    ``wind_class_note`` / ``wind_otype_source``) and ``otypes`` is then unused (its effect is already in
    the passed ``wind_class``). A caller-passed ``wind_class_provenance`` always wins (the ``--object``
    path's ``object_preset``). ``wind_otype_source`` (CR-25 / MSG 266) is caller-only: the main_id whose
    otype list was consulted when it is NOT the star itself. The standoff arithmetic is byte-identical to
    ``compute_exclusion_boundary`` — this function never re-derives ``r_ex``; it only wraps it and
    adds the additive wall/domain/echo fields. Returns the result dict, or — only on the main_sequence /
    evolved domains, and only for a **positive** mass — the frozen generator's curated ``{"error": …}``
    (out-of-band exponents, non-positive dial/calibration, ``β ≠ 0`` with L ≤ 0, ``mass_loss_msun_yr ≤ 0``
    or an unknown ``wind_state``); windless / unmodeled bodies return before any of that validation.

    **Mass is NOT validated here.** A ``None``, non-positive or NaN ``mass_msun`` takes the null-standoff
    branch (the honest evolved-no-mass case), and +inf reaches the frozen generator unchecked. Validating a
    user-supplied mass (finite and > 0) is the caller's job — ``query.py``'s bare ``--mass-msun`` guard
    (CR-22.6, which restored the pre-CR-22 error this wrapper had bypassed); the other entry paths pass a
    resolved finite positive mass or ``None``.
    """
    if domain is None:
        cw = ew.classify_wind(
            sp_type=sp_type, otype=otype, class_tag=class_tag, wind_class=wind_class,
            object_name=object_name, wind_state=wind_state, otypes=otypes)
        domain, wind_class, class_note = cw["domain"], cw["wind_class"], cw["class_note"]
        wind_class_provenance = wind_class_provenance or cw["wind_class_provenance"]
        wind_otype, wind_class_note = cw["wind_otype"], cw["wind_class_note"]
        wind_state_binned = cw["wind_state_binned"]

    ws = ew._norm_wind_state(wind_state)
    if wind_class_provenance == "object_preset" and ws:
        # an --object preset's bin is fixed (the user gave no wind_class — say so, not "explicit")
        wind_class_note = ew.PRESET_NOTE.format(ws=ws, wc=wind_class)

    inputs, prov = ew.resolve_wind_inputs(
        domain, wind_class, sp_type, mass_loss_msun_yr=mass_loss_msun_yr, wind_speed=wind_speed,
        v_ism=v_ism, c_ms=c_ms, b_field=b_field, n_cloud=n_cloud, cloud_temp=cloud_temp,
        wind_phase_yr=wind_phase_yr, f_shock=f_shock, m_shock_min=m_shock_min,
        mass_loss_source=mass_loss_source)

    base = {"domain": domain, "wind_class": wind_class, "class_note": class_note,
            # CR-25.3: how the wind BIN was chosen (independent of mass_loss_provenance — the Ẇ axis)
            "wind_class_provenance": wind_class_provenance, "wind_otype": wind_otype,
            "wind_otype_source": wind_otype_source, "wind_class_note": wind_class_note,
            "object": object_name, "mass_msun": mass_msun, "model_note": _MODEL_NOTE}

    # ── windless free harbor: no standoff, no wall (a WD / BD / rogue) ──
    if domain == ew.WINDLESS:
        base.update({"standoff_au": None, "r_ex_au": None, "forcing_class": "free_harbor",
                     "mass_provenance": mass_provenance,   # CR-23.2 §2a: always present (object_preset / None)
                     "wall_au": None, "wall_band_au": None, "wall_route": "none_windless",
                     "wall_reason": "windless — free harbor", "wall_note": ew._WALL_NOTE,
                     "verdict_marginal": False, "wall_exceeds_standoff": None,
                     "wall_to_standoff_ratio": None, "r_ap_au": None})
        return base

    # ── unmodeled (hot subdwarf sdB/sdO): honest null on both layers (NOT free harbor) ──
    if domain == ew.UNMODELED:
        base.update({"standoff_au": None, "r_ex_au": None, "forcing_class": None,
                     "mass_provenance": mass_provenance,   # CR-23.2 §2a: always present (None on no-mass)
                     "wall_au": None, "wall_band_au": None, "wall_route": "none_unmodeled",
                     "wall_reason": class_note or "class outside the wind model",
                     "wall_note": ew._WALL_NOTE, "verdict_marginal": False,
                     "wall_exceeds_standoff": None, "wall_to_standoff_ratio": None,
                     "r_ap_au": None})
        return base

    # ── main_sequence / evolved: the FROZEN standoff (when a mass is known) + the wall ──
    standoff = None
    result = dict(base)
    if mass_msun is not None and mass_msun > 0:
        stand = compute_exclusion_boundary(
            mass_msun=mass_msun,
            luminosity_lsun=(luminosity_lsun if luminosity_lsun is not None else 1.0),
            mass_loss_msun_yr=mass_loss_msun_yr, wind_state=wind_state, dial=dial,
            calibration_au=calibration_au, alpha=alpha, beta=beta, gamma=gamma,
            scan_alpha=scan_alpha, object_name=object_name)
        if "error" in stand:
            return stand                                   # frozen generator's curated error
        standoff = stand["r_ex_au"]
        for k in ("r_ex_au", "luminosity_lsun", "dial", "alpha", "beta", "gamma", "calibration_au",
                  "forcing_class", "r_ex_au_alpha_third", "r_ex_au_alpha_half"):
            if k in stand:
                result[k] = stand[k]
        result["standoff_au"] = standoff
        if domain == ew.EVOLVED:
            result["standoff_note"] = _EVOLVED_STANDOFF_NOTE
    else:
        result.update({"r_ex_au": None, "standoff_au": None, "forcing_class": None})
        if domain == ew.EVOLVED:
            # keep the resolver's specific hint (CP2 finding 6), not just the generic note
            result["standoff_note"] = (
                f"{_EVOLVED_NO_MASS_NOTE} ({mass_note})" if mass_note else _EVOLVED_NO_MASS_NOTE)

    # CR-25: a bin-scoped "ignored / superseded" note gains the γ>0 caveat only when the FROZEN standoff
    # above actually took the wind_state as its Ẇ (a standoff exists, no explicit rate) — shared rule.
    result["wind_class_note"] = ew.with_gamma_caveat(
        wind_class_note, wind_state=wind_state, binned=bool(wind_state_binned), gamma=gamma,
        mass_loss_msun_yr=mass_loss_msun_yr, has_standoff=standoff is not None)
    result["mass_provenance"] = mass_provenance      # CR-23.2 §2a: always present (None on no-mass)
    # CR-23.2 §2c: surface the resolver note (e.g. the L^0.2632 over-read caution) — but ONLY on the
    # with-mass path (standoff resolved). The evolved-NO-mass branch already embeds mass_note inside
    # standoff_note, so this guard avoids duplicating it across two keys (review F3); windless/unmodeled
    # return early with no mass, so they carry no mass_note either (review F5 — consistent by this rule).
    if mass_note and standoff is not None:
        result["mass_note"] = mass_note

    wall = ew.compute_wall(
        wdot=inputs["wdot"], v_wind=inputs["v_wind"], v_ism=inputs["v_ism"], c_ms=inputs["c_ms"],
        n_cloud=inputs["n_cloud"], r_ex=standoff, wind_class=wind_class, t_phase=inputs["t_phase"],
        f_shock=inputs["f_shock"], m_shock_min=inputs["m_shock_min"], c_ms_band=inputs["c_ms_band"])
    for k in ("wall_au", "wall_band_au", "wall_route", "wall_reason", "wall_note",
              "verdict_marginal", "r_ap_au"):
        result[k] = wall[k]
    band_hi = wall["wall_band_au"][1] if wall["wall_band_au"] else None
    exceeds, ratio = ew.hazard_flags(band_hi, wall["wall_au"], standoff)
    result["wall_exceeds_standoff"] = exceeds
    result["wall_to_standoff_ratio"] = ratio
    result.update(_wind_echo(inputs, prov))
    return result
