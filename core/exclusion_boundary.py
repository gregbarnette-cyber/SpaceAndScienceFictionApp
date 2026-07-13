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
