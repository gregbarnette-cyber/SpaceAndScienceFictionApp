"""CR-26 — the per-star wind model: supplied → measured → X-ray → non-detection → class-default tier ladder.

WB contract: ``design-lab/star-system-analysis/spaceapp-change-request-CR26-xray-tier-wind-model.md``
(cited ``§26.N``), plus the channel rulings MSG 287–302 (Q/R/G/H/J/K). This module is the **pure**
model: it maps a ``StarWindInputs`` (identity, supplied inputs, and the already-fetched lookup results)
to a ``WindModel`` dict. **No network, no I/O beyond the md5-checked tables, no Qt**, and it imports
only ``core.stellar_wind_tables`` and ``core.shared`` — the caller fills the non-coronal / legacy rates
and the CR-25 colour letter (``exclusion_wall`` / ``exclusion_boundary`` / ``xray_catalog``), so no
import cycle can form.

The relation (§26.3.6, the censored Wood 2021 fit): ``log(Ṁ/A) = 0.245 + 0.592 (log F_X − 5)`` in Ṁ⊙
per A⊙, ``Ṁ[Ṁ⊙] = 10^(log Ṁ/A) × (R★/R⊙)²``, Ṁ⊙ = 2×10⁻¹⁴ M☉/yr. Every CR-26 value is research-grade:
**a long-term, population-typical Ṁ for a star at that X-ray flux, not the star's current wind.**
"""

import math
import re
from dataclasses import dataclass, field

from core import shared
from core import stellar_wind_tables as swt

MDOT_SUN = 2e-14                     # M☉/yr — Wood 2021's unit Ṁ⊙
PC_CM = 3.0856775814913673e18        # cm
RSUN_CM = 6.957e10                   # cm (IAU nominal)

_INTERCEPT, _SLOPE = 0.245, 0.592
_QUIET_EDGE, _ACTIVE_EDGE = 4.85, 6.0
_FIT_LO, _FIT_HI = 4.03, 7.2         # the fit's lowest / highest astrospheric detection
_XMM_FLOOR = 3.5
_REGIME_EDGE_WINDOW = 0.15
_FAST_ROTATOR_DAYS = 0.5
_F_DWARF_LO_SHIFT = 0.63
_LATE_M_TERM = 0.2
_LATE_M_FROM = 4.5
_BIMODAL_LIMIT = 6.2633              # the saturated mode's log F_X (§26.4 M4+ gate)
_RADIUS_CHECK_DEX = 0.3

# ── enums (§26.7) ────────────────────────────────────────────────────────────────
TIERS = ("supplied", "measured", "xray", "xray_nondetection", "class_default")
LADDER_TIERS = ("measured", "xray", "xray_nondetection", "class_default")   # tiers 2–5
MASS_LOSS_TIERS = TIERS + ("noncoronal_row", "object_preset", "legacy_row", "none")
FLAGS = ("active_bimodal", "bimodal_class", "extrapolated", "fast_rotator", "above_fit_range",
         "below_fit_range", "xray_upper_limit", "blended_source", "blend_mixed_class",
         "blend_partner_radius_missing", "blend_partner_by_designation", "blend_partner_radius_unchecked",
         "field_star_in_beam", "wd_partner_in_beam", "xmm_rung", "xmm_guard_demoted", "xmm_floor_demoted",
         "method_conflict", "method_mixed", "measured_upper_limit", "measured_combined_split",
         "marginal_state", "subtype_unknown", "radius_unchecked", "radius_pair_ambiguous",
         "not_authoritative")
RUNGS = ("2RXS", "eRASS1", "XMM")
FAIL_CODES = ("timeout", "unreachable", "error")
STATE_LABEL = {"quiet": "quiet", "typical": "solar", "active": "active"}
_WIND_STATE_TO_STATE = {"quiet": "quiet", "solar": "typical", "active": "active"}

# ── notes (fixed strings, each pinned by a test) ─────────────────────────────────
NOTE_UNUSED_WIND_STATE = ("--wind-state '{ws}' did not set the wind rate — the {tier} tier set it "
                          "(--wind-state selects the class-default state only; supply --mass-loss-msun-yr to "
                          "override a data tier); the wind_class label still carries the selected state")
NOTE_UNUSED_WIND_CLASS = ("wind_class '{wc}' did not set the wind rate — the {tier} tier set it (a "
                          "quiet/solar/active wind_class selects the class-default state only)")
NOTE_G10_BYPASS = ("the caller's wind_class '{wc}' bypassed the CR-26 ladder — the '{wc}' row is used as "
                   "given (noncoronal_row)")
NOTE_IGNORED_SOURCE = ("--mass-loss-source '{src}' ignored: a tool-chosen CR-26 rate is always a "
                       "Wood-convention rate (astrosphere_wood); it counts only together with a supplied rate")
NOTE_IGNORED_SPEED = ("--wind-speed {v:g} ignored: a CR-26 tier rate is a Wood-convention rate, which forces "
                      "v_wind = 400 km/s — to use another speed, supply the rate (--mass-loss-msun-yr) with it")
NOTE_IGNORED_INPUT = ("{name} ignored: no CR-26 tier can use it on this path or star")
NOTE_T12 = ("the X-ray tier's point ({xp:.3g} Ṁ⊙) lies {dir} the Wood upper limit ({lim:g} Ṁ⊙) — a "
            "comparison, not a correction; the X-ray tier never replaces or caps the limit")
NOTE_SYSTEM_EDGE = ("61 Cyg system upper edge: Kislyakova 2024's A+B rate {edge:g} Ṁ⊙ (the published mean of "
                    "per-observation rates) — reported at system level, never a band edge on A")
NOTE_H3 = ("`--wind-state` did not set the wind rate (the wall is null); it still feeds the γ > 0 standoff "
           "through the legacy map, as before.")
NOTE_H4 = ("the caller's class '{cc}' disagrees with the measured row's SIMBAD type '{rc}' — the caller's "
           "class is used")
NOTE_H7 = "the lower-case Am/peculiarity prefix was skipped; read as {letter}"
NOTE_SUBDWARF = ("a subdwarf takes the dwarf subtype median radius, which is likely too large for it — "
                 "supply --radius-rsun where no catalog radius exists")
NOTE_RADIUS_OFF = ("the supplied radius {r:g} R☉ sits {dex:.2f} dex from the {ref} median {m:g} R☉ — used as "
                   "given (never replaced)")
NOTE_Q1_UPPER = ("at γ > 0 the standoff's wind term takes this upper-bound rate, so the standoff is an upper "
                 "bound too")
NOTE_NETWORK_OFF = ("no catalog lookup on this path (deterministic) — the X-ray and non-detection tiers were "
                    "not evaluated from catalogs")
NOTE_NO_DISTANCE = "no usable distance — the X-ray and non-detection tiers were not evaluated"
NOTE_REGIME_EDGE = ("log F_X {x:.3f} is within 0.15 dex of the {edge} regime edge (log F_X {e:g}); the "
                    "neighbouring {nb} regime's band would be {lo:+.3f} / {hi:+.3f} dex")
NOTE_SUBTYPE_UNKNOWN = ("an M star typed without a subtype digit has no class bin — the class default and "
                        "the non-detection tables are not reachable")

# ── §26.8 disclosures (verbatim; only spec cross-references and ruling tags dropped — R8) ────────────
DISCLOSURE_WHAT = {
    "xray": ("What it is (X-ray tier): a long-term, population-typical Ṁ for a star at that X-ray flux. "
             "Never the star's current wind; single-epoch catalog fluxes, with the cycle/flare spread inside "
             "the band."),
    "xray_nondetection": ("What it is (non-detection tier): a long-term, population-typical Ṁ for a star of "
                          "its class below its survey limit. Never the star's current wind; single-epoch "
                          "catalog fluxes, with the cycle/flare spread inside the band."),
    "class_default": ("What it is (class default): a long-term, population-typical Ṁ for a typical star of its "
                      "class and radius (no X-ray measurement of the star). Never the star's current wind; "
                      "single-epoch catalog fluxes, with the cycle/flare spread inside the band."),
}
DISCLOSURES = {
    2: ("The band is ≈ 68 %: on the 22 astrospheric detections' leave-one-out residuals the regime bands cover "
        "15 — about 1 star in 3 falls outside, with residuals up to 1.5 dex from the line (≤ 0.3 dex beyond a "
        "band edge); the widths were set with those residuals in view (a calibration, not an independent "
        "test); the widened, class-default and non-detection bands are model constructions with no separate "
        "coverage test."),
    3: ("How much the X-ray tier knows: it beats a class default by ≈ 9 % in dex overall (leave-one-out rms "
        "0.855 vs 0.944). By regime (line vs class default): log F_X < 4.7 — 0.20 vs 0.45 dex (n = 5); "
        "4.7–6.0 — 0.88 vs 1.02 (n = 13); above 6.0 — 1.21 vs 1.12 (n = 4: no gain — there a single F_X "
        "carries no more information than \"active star\")."),
    4: ("The quiet band is GK-calibrated: the six detections below log F_X 4.7 are G/K stars and the Sun; the "
        "4.85 quiet edge takes in one M dwarf, GJ 173 (log F_X 4.81), which sits +0.50 above the line, "
        "outside +0.30."),
    5: ("K and M stars split in the mid regime: K dwarfs sit ≈ +0.8 dex above the line, M dwarfs ≈ 0 — "
        "equally consistent with one line (LRT p = 0.72), so one line is used."),
    6: ("The intercept is a method choice: using the upper limits (censoring) lowers it 0.18 dex vs a plain "
        "fit (×1.5 in Ṁ, ×1.23 in a wall); it is WB-derived (Wood publishes a slope only; Wood's 0.77 lies "
        "inside this fit's slope 68 % CI)."),
    7: ("eRASS1 fluxes of soft, quiet stars may read low: a one-sided term ≲ 0.3 dex in F_X, so the point Ṁ "
        "may read up to 0.18 dex low (0.3 × the slope 0.592; the central wall up to ≈ 19 % low — the true "
        "wall up to ≈ 23 % larger) — inside the band's upper half in every regime; it is not added to the "
        "band (were it added in quadrature to the quiet band's +0.30, that wall edge would move ≈ 6 %); the "
        "conversion is untested below log F_X 5.5."),
    8: "G's quiet state is marginal (when used): it sits on the class's lowest detection.",
    9: "The typical point sits above the class's predicted-rate median by 0.08–0.27 dex.",
    10: ("Radius limits: M7–M9 have fewer than 3 catalog radii within 10 pc and take the M6 median (0.1275 "
         "R⊙), likely too large for M8–M9 (by roughly 10–25 % — an unpinned estimate) — ≲ 0.08 dex in an "
         "X-ray-tier Ṁ (the radius enters F_X too: Ṁ ∝ R^(2 × (1 − 0.592)) = R^0.82) but up to ≈ 0.19 dex in "
         "a class-default Ṁ (Ṁ ∝ R²); in a close pair a catalog cross-match can give a star its companion's "
         "radius, which the 0.3-dex check does not catch when the two are similar (α Cen B carries α Cen A's "
         "1.225 R⊙ in the W4 pull; flagged radius_pair_ambiguous) — supply --radius-rsun where it matters."),
    12: ("XMM-rung fluxes: the conversion was calibrated on RASS-detected sources (sum_flag ≤ 1), whose "
         "p16/p84 −0.41/+0.04 tail comes from bright-star pile-up failures the guard excludes; the scatter for "
         "the faint, clean sources the guard keeps is untested, and no band term is applied."),
    13: ("Below the fit: the point sits below the fit's lowest astrospheric detection (log F_X 4.03); the "
         "relation is extrapolated there, without a widening."),
    14: ("An otype-selected active state: it assumes the star sits at its class's p84 X-ray flux; of the "
         "flare-labelled local stars checked at W6 about 1 in 3 reach it (e.g. AD Leo, EV Lac, Ross 154 and "
         "YZ CMi above; 61 Cyg A, Barnard's star and most other M4+ flare stars 0.3 dex or more below) — "
         "supply the star's X-ray flux (--log-fx / log_fx=) where it is known."),
    15: ("A combined-wind band: the band sums the members' band-edge rates — the merged system's own band "
         "when they share one blended F_X; with separate F_X it assumes their residuals move together, and for "
         "independent residuals the pair's upper edge could lie up to ≈ ×1.3 further out in the wall (mid, "
         "active and class-default bands; in the quiet band the summed edge is conservative)."),
}
DISCLOSURE_MEASURED = {
    "wood_x2": "Measured tier: Wood's astrospheric rates carry Wood's own ≈ ×2 systematic.",
    # CR-24 ⚑4: a placeholder, replaced once V_ISM is known (exclusion_boundary._cr26_fields) by "A measured Ṁ was
    # inferred at the V_ISM Wood 2021 Table 3 lists for this star (<n> km/s); this run uses <V> km/s (<prov>)."
    "ism": "[[CR-24 ISM note — filled once V_ISM is known]]",
    "combined": ("Binary rates are combined astrospheres: Wood's one combined rate is area-shared per component "
                 "(measured_combined_split — equal mass loss per unit area, Wood's Table 3 radii)."),
    "method_conflict": ("method_conflict: Wood's split value is used; Kislyakova 2024's upper limit (< 0.75 "
                        "Ṁ⊙, A+B) is shown but never sets a value or a band edge."),
    "method_mixed": ("method_mixed: Wood's value for A is used; Kislyakova 2024's A+B rate is reported only as the "
                     "system upper edge."),
    "kislyakova": ("Kislyakova-set values (the band edges, the system edges) are charge-exchange rates, not "
                   "V_w-conditioned, run at v_wind 400 by convention, with systematics \"a factor of a few\" and "
                   "model inputs shared with the hydrogen-wall method."),
    "evolved_v400": ("On an evolved host, v_wind 400 km/s is Wood's lower-main-sequence assumption (\"the surface "
                     "escape speed is relatively constant\"); it does not cover evolved hosts — each measured "
                     "rate stays at Wood's published convention."),
}
# Item 11 — each flag's one-line meaning (active_bimodal / bimodal_class verbatim from §26.3.7 / §26.5).
FLAG_TEXT = {
    "active_bimodal": ("this star's F_X is in the active regime (≥ 6.0), where the four astrospheric detections "
                       "split into a weak mode (3 of the 4) 0.7–1.4 dex below the line and a strong mode (1 of "
                       "the 4) ≈ 1.4 dex above it — what Wood 2021 calls \"a hint of possible bimodality\". The "
                       "point is the line, which neither mode sits on; the ±1.2-dex band spans both."),
    "bimodal_class": ("the class's F_X distribution is two-peaked; the two reported values are conditional "
                      "medians — of the class below log F_X 5.25 (inactive) and above 5.75 (saturated). The cut "
                      "points are a convention, not derived, and the weights and both conditional medians depend "
                      "on them. The typical point lies between the two. This is a statement about the class, not "
                      "about the star's wind (compare active_bimodal)."),
    "extrapolated:f_dwarf": ("class F lies outside the fit's calibration: the band's lower edge moves 0.63 dex "
                             "further down, added linearly (Procyon's limit sits 0.63 below the line; the true "
                             "offset may be larger or smaller)."),
    "extrapolated:late_m": ("an M4.5 or later star lies outside the fit's calibration: 0.2 dex is added in "
                            "quadrature to both band edges — a nominal term (no M4.5+ astrospheric detection "
                            "exists, so the extrapolation is unsized)."),
    "fast_rotator": ("a supplied rotation period ≤ 0.5 d: the upper band edge becomes max(hi, √(2.0² + hw²)) — the "
                     "envelope of three of Wood's slingshot stars, not a ≈ 68 % edge."),
    "above_fit_range": ("the X-ray-tier log F_X lies above the fit's top (7.20): the upper band edge becomes "
                        "max(hi, √(2.0² + hw²))."),
    "below_fit_range": ("the point is evaluated below the fit's lowest astrospheric detection (log F_X 4.03): "
                        "disclosure only, no widening."),
    "xray_upper_limit": "no X-ray detection: the star is taken as a non-detection below its survey limit.",
    "blended_source": ("the matched X-ray source contains physical companions: equal surface flux — the system "
                       "F_X over every matched star, each star's Ṁ at its own R²."),
    "blend_mixed_class": "the blended partners' class bins differ (the same equal-surface-flux rule is used).",
    "blend_partner_radius_missing": ("a blend partner has no radius — the star keeps its own-area F_X."),
    "blend_partner_by_designation": ("a partner qualified only because the catalogs name the two one system "
                                     "(GCNS system_id, a SIMBAD parent, or a component letter)."),
    "blend_partner_radius_unchecked": ("a partner with no spectral class took a catalog radius without the "
                                       "subtype check."),
    "field_star_in_beam": ("a GCNS star inside the matched source's radius failed all three partner tests — it is "
                           "named and takes no area share."),
    "wd_partner_in_beam": ("a white-dwarf partner is in the beam — a hot white dwarf can itself be the X-ray "
                           "source, so the target's F_X may be overstated (its area share is kept)."),
    "xmm_rung": "the flux came from the guarded XMM rung (conversion ×10^0.087, no band term).",
    "xmm_guard_demoted": ("the XMM match failed the guard (G > 7, sum_flag ≤ 1, det_ML ≥ 15) — demoted to the "
                          "non-detection path."),
    "xmm_floor_demoted": "the XMM match fell below the log F_X 3.5 floor — demoted to the non-detection path.",
    "method_conflict": DISCLOSURE_MEASURED["method_conflict"],
    "method_mixed": DISCLOSURE_MEASURED["method_mixed"],
    "measured_upper_limit": "the measured value is Wood's upper limit — the rate and the wall are upper bounds (≲).",
    "measured_combined_split": DISCLOSURE_MEASURED["combined"],
    "marginal_state": ("G's quiet state is marginal: it sits on the class's lowest detection, with 14 % of the KM "
                       "mass unresolved below it."),
    "subtype_unknown": NOTE_SUBTYPE_UNKNOWN,
    "radius_unchecked": ("an M star with no subtype digit took a catalog radius without the subtype check."),
    "radius_pair_ambiguous": ("the accepted catalog radius may be a close companion's (another star in the 5″ "
                              "cone, or a lettered component) — supply --radius-rsun where it matters."),
    "not_authoritative": ("a catalog lookup failed that changed, or could have changed, the value that set the "
                          "rate."),
}


# ── parsing / scope / bins (§26.1, §26.3.5) ──────────────────────────────────────
_SUBTYPE_RE = re.compile(r"([OBAFGKM])(\d+(?:\.\d+)?)?")


def parse_sp(sp):
    """``(letter, subtype|None, is_subdwarf)`` — the ONLY letter source for CR-26 scope.

    Strips one leading sd-family / dwarf prefix (``core.shared._SP_DWARF_SUBDWARF_PREFIXES``, longest
    first), then takes the first **upper-case** O/B/A/F/G/K/M and the number directly after it (decimals
    allowed); anything after is ignored and a range takes its first type (``K7-M0`` → K7). ``kA5hF0mF2`` → A
    (the lower-case Am prefixes are not dwarf markers — H7)."""
    s = (sp or "").strip()
    if not s:
        return None, None, False
    sub = False
    for p in shared._SP_DWARF_SUBDWARF_PREFIXES:
        if s.startswith(p):
            sub = p != "d"
            s = s[len(p):]
            break
    m = _SUBTYPE_RE.search(s)
    if not m:
        return None, None, sub
    return m.group(1), (float(m.group(2)) if m.group(2) else None), sub


def class_bin(letter, subtype):
    """F / G / K / M0–M3.5 (M < 4.0) / M4+ (M ≥ 4.0); an M star with no subtype → ``None``."""
    if letter in ("F", "G", "K"):
        return letter
    if letter == "M":
        if subtype is None:
            return None
        return swt.BIN_M_LATE if subtype >= 4.0 else swt.BIN_M_EARLY
    return None


def in_scope(domain, letter):
    return domain == "main_sequence" and letter in ("F", "G", "K", "M")


# ── the relation, hw, regimes, bands (§26.3.6–.8) ────────────────────────────────
def _pow10(x):
    if x > 300 or x < -300:
        raise OverflowError(f"10^{x:g} is out of range")
    return 10.0 ** x


def per_area_log(x):
    return _INTERCEPT + _SLOPE * (x - 5.0)


def hw(x):
    """The line's bootstrap 68 % half-width at log F_X x (0.01 grid, clamped to 2.00–8.00)."""
    t = swt.load_cr26_tables()["HW"]
    i = int(math.floor(min(max(x, 2.0), 8.0) * 100 + 0.5 + 1e-9))      # x rounded (half up) to 0.01
    return t[i]


def regime_of(x):
    if x is None:
        return None
    if x < _QUIET_EDGE:
        return "quiet"
    return "active" if x >= _ACTIVE_EDGE else "mid"


def regime_band(x, regime=None):
    regime = regime or regime_of(x)
    h = hw(x)
    if regime == "quiet":
        return -0.50, 0.30
    if regime == "mid":
        return -math.sqrt(0.85 ** 2 + h ** 2), math.sqrt(1.20 ** 2 + h ** 2)
    a = math.sqrt(1.20 ** 2 + h ** 2)
    return -a, a


def widen(lo, hi, x, letter, subtype, *, fast_rotator=False, above_fit=False):
    """§26.3.8 widening, in table order. Returns ``(lo, hi, extrapolation_class)``."""
    if fast_rotator or above_fit:
        hi = max(hi, math.sqrt(2.0 ** 2 + hw(x) ** 2))
    ext = None
    if letter == "F":
        lo -= _F_DWARF_LO_SHIFT
        ext = "f_dwarf"
    elif letter == "M" and subtype is not None and subtype >= _LATE_M_FROM:
        lo = -math.sqrt(lo ** 2 + _LATE_M_TERM ** 2)
        hi = math.sqrt(hi ** 2 + _LATE_M_TERM ** 2)
        ext = "late_m"
    return lo, hi, ext


def log_fx_from_flux(f_x, d_pc, r_rsun_sq_sum):
    """``log(f_x × d² / ΣR²)`` — the surface flux on the fit scale (erg cm⁻² s⁻¹)."""
    if not f_x or f_x <= 0 or not d_pc or d_pc <= 0 or not r_rsun_sq_sum or r_rsun_sq_sum <= 0:
        return None
    d = d_pc * PC_CM
    return math.log10(f_x) + 2 * math.log10(d) - math.log10(r_rsun_sq_sum * RSUN_CM ** 2)


def xmm_guard(g, sum_flag, det_ml, logfx_eval):
    """§26.3.3: the guard (G, sum_flag, det_ML) first, then the floor on the F_X the relation would use."""
    if g is None or g <= 7 or sum_flag is None or sum_flag > 1 or det_ml is None or det_ml < 15:
        return "xmm_guard_demoted"
    if logfx_eval is None or logfx_eval < _XMM_FLOOR:
        return "xmm_floor_demoted"
    return "kept"


def ladder_outcome(rungs, astrom_status=None, limit_status=None, xmm_result=None):
    """The §26.1 partial-failure rule, pure and table-tested.

    ``rungs`` — ``[(rung, status)]`` in ladder order, status ∈ {detection, no_detection, out_of_footprint,
    timeout, unreachable, error}; ``xmm_result`` — for an XMM detection with no earlier detection: ``kept`` /
    a demotion name / a failure code (the H6 failed SIMBAD-G fetch). Returns
    ``{path: detection|nondetection|failed, used: rung|None, status, not_authoritative, rungs}``."""
    if astrom_status:
        return {"path": "failed", "used": None, "status": astrom_status, "not_authoritative": True,
                "rungs": [{"rung": r, "status": "not_queried"} for r, _ in rungs]}
    out, used, first_fail, fail_above = [], None, None, False
    for r, st in rungs:
        eff = st
        if used is None and r == "XMM" and st == "detection" and xmm_result in FAIL_CODES:
            eff = xmm_result                                  # H6: a failed G fetch fails the rung
        out.append({"rung": r, "status": eff})
        if used is not None:
            continue
        if eff in FAIL_CODES:
            first_fail = first_fail or eff
            fail_above = True
            continue
        if eff == "detection" and (r != "XMM" or xmm_result == "kept"):
            used = r
    if used is not None:
        return {"path": "detection", "used": used, "status": first_fail or "ok",
                "not_authoritative": fail_above, "rungs": out}
    if first_fail:
        return {"path": "failed", "used": None, "status": first_fail, "not_authoritative": True, "rungs": out}
    if limit_status:
        return {"path": "failed", "used": None, "status": limit_status, "not_authoritative": True,
                "rungs": out}
    return {"path": "nondetection", "used": None, "status": "ok", "not_authoritative": False, "rungs": out}


# ── radius (§26.3.5) ─────────────────────────────────────────────────────────────
_LETTERED_RE = re.compile(r"(\s[A-D]|\d[A-D])$")


def lettered_main_id(main_id):
    return bool(_LETTERED_RE.search(swt.collapse_ws(main_id)))


def subtype_median(letter, subtype):
    if letter not in ("F", "G", "K", "M") or subtype is None:
        return None
    return swt.load_cr26_tables()["SUBTYPE_R"].get((letter, min(int(math.floor(subtype)), 9)))


def class_median(letter, subtype):
    b = class_bin(letter, subtype)
    if b is None:
        return None
    return swt.load_cr26_tables()["CLASS_STATES"][(b, "typical")]["class_median_r"]


def select_radius(letter, subtype, is_subdwarf=False, supplied=None, candidates=(), statuses=None, *,
                  main_id=None, cone_other=None, gcns_neighbour=None, partner=False):
    """The radius chain: supplied → TIC → FLAME → GSP-Phot (each within 0.3 dex of the reference) →
    subtype median (or ``subtype_median_replaced_outlier``) → class median. Returns the §26.3.5 dict +
    ``flags`` / ``notes`` lists (not output keys). ``radius_rsun`` is ``None`` only when no rung applies
    (an M star with no digit / a class-less partner, and no catalog value)."""
    sub_m = subtype_median(letter, subtype)
    cls_m = class_median(letter, subtype) if letter in ("F", "G", "K") else None
    ref, ref_name = (sub_m, "subtype") if sub_m is not None else (cls_m, "class")     # K2: F/G/K no digit
    out = {"radius_rsun": None, "radius_source": None, "subtype_median_rsun": sub_m, "rejected": [],
           "status": dict(statuses or {}), "flags": [], "notes": []}
    if supplied is not None:
        out.update(radius_rsun=supplied, radius_source="supplied")
        if ref is not None:
            dex = abs(math.log10(supplied / ref))
            if dex > _RADIUS_CHECK_DEX:
                out["notes"].append(NOTE_RADIUS_OFF.format(r=supplied, dex=dex, ref=ref_name, m=ref))
        return out
    had_catalog = False
    for c in candidates:
        v = c.get("value")
        if v is None or not (v > 0) or not math.isfinite(v):
            continue
        had_catalog = True
        if ref is None:
            out.update(radius_rsun=v, radius_source=c["source"])
            out["flags"].append("blend_partner_radius_unchecked" if partner else "radius_unchecked")
            break
        if abs(math.log10(v / ref)) <= _RADIUS_CHECK_DEX:
            out.update(radius_rsun=v, radius_source=c["source"])
            break
        out["rejected"].append({"source": c["source"], "value": v})
    if out["radius_rsun"] is not None:
        if not partner and (cone_other or gcns_neighbour or lettered_main_id(main_id)):
            out["flags"].append("radius_pair_ambiguous")
        return out
    if sub_m is not None:
        out.update(radius_rsun=sub_m, radius_source=("subtype_median_replaced_outlier" if had_catalog
                                                      else "subtype_median"))
    elif cls_m is not None:
        out.update(radius_rsun=cls_m, radius_source="class_median")
    if is_subdwarf and out["radius_rsun"] is not None:
        out["notes"].append(NOTE_SUBDWARF)
    return out


def radius_public(r):
    return {k: r[k] for k in ("radius_rsun", "radius_source", "subtype_median_rsun", "rejected", "status")}


# ── inputs ───────────────────────────────────────────────────────────────────────
@dataclass
class StarWindInputs:
    """Everything the pure model needs. Lookup results are already fetched (``core.xray_catalog``)."""
    sp_type: str = None
    main_id: str = None
    domain: str = "main_sequence"
    cr25_letter: str = None                 # detection._sp_letter(sp_type), for H7 (caller-computed)
    # supplied inputs
    supplied_rate: float = None             # M☉/yr (tier 1)
    log_fx: float = None
    log_fx_limit: float = None
    radius_rsun: float = None
    prot_days: float = None
    wind_state: str = None                  # effective (own, else the system flag), normalized
    wind_class: str = None                  # an explicit caller wind_class (G10)
    active_otype: bool = False              # the CR-25 active-otype match (MS K/M)
    mass_loss_source: str = None            # a caller --mass-loss-source (ignored on tiers 2–5)
    wind_speed: float = None                # a caller --wind-speed (ignored on tiers 2–5 — R10)
    # identity → measured table
    measured_ids: list = field(default_factory=list)    # strings tried in order (main_id; H1/G12/K3 forms)
    measured_miss_not_authoritative: bool = False       # H1: identity failed AND no string hit
    a_record: tuple = None          # CR-24: the (record, status) of the A-candidate identity lookup, for reuse
    identity_failed: bool = False           # RG5: the star's own SIMBAD identity lookup failed (H1)
    # lookup results (None = not run)
    network: bool = False                   # a catalog ladder was attempted
    not_run_reason: str = None              # why xray.status is not_run
    d_pc: float = None
    astrom_status: str = None               # a failure code when every astrometry step failed
    rungs: list = None                      # [{rung, status, cand:{…}}]
    g_mag: float = None
    g_status: str = None                    # None = answered (g_mag may be None) / a failure code
    limit: dict = None                      # {status, f_limit, survey}
    radius_candidates: list = field(default_factory=list)
    radius_status: dict = field(default_factory=dict)
    cone_other: bool = None
    gcns_neighbour: bool = None
    blend: dict = None                      # {status, partners:[…], field_stars:[…], notes:[…], partial}
    noncoronal_rate: float = None           # the CR-25 identity row's rate (caller-filled, M-5)
    notes: list = field(default_factory=list)            # orchestrator notes (Q2, Q3, R3, R6, G12, H1, …)


def _mdot(per_area, r):
    return _pow10(per_area) * r * r * MDOT_SUN


def _band_msun(rate, lo, hi):
    if rate is None or lo is None:
        return None
    return [rate * _pow10(lo), rate * _pow10(hi)]


def _select_state(inp, letter):
    """§26.5 state precedence → ``(state, source)``; ``hot`` → ``(None, 'hot')``."""
    wc = (inp.wind_class or "").strip().lower()
    if wc in ("quiet", "solar", "active"):
        return _WIND_STATE_TO_STATE[wc], "manual"
    ws = (inp.wind_state or "").strip().lower()
    if ws == "hot":
        # J2: hot maps to no state; the label falls through to the next selector
        st, src = ("active", "otype_auto") if (inp.active_otype and letter in ("K", "M")) else ("typical",
                                                                                               "class_default")
        return st, "hot:" + src
    if ws in _WIND_STATE_TO_STATE:
        return _WIND_STATE_TO_STATE[ws], "manual"
    if inp.active_otype and letter in ("K", "M"):
        return "active", "otype_auto"
    return "typical", "class_default"


def _entry(rate=None, band=None, status="ok", log_fx=None, flags=None, upper=False):
    return {"mass_loss_msun_yr": rate, "mass_loss_band_msun_yr": band, "used": False,
            "status": ("upper_limit_only" if (upper and status == "ok") else status),
            "log_fx": log_fx, "flags": list(flags or [])}


def _add(flags, *names):
    for n in names:
        if n and n not in flags:
            flags.append(n)


# ── the tier computations ────────────────────────────────────────────────────────
def measured_result(inp):
    """§26.2 — the measured tier from the first ``measured_ids`` hit, or ``None``."""
    t = swt.load_cr26_tables()["MEASURED"]
    row = None
    for mid in inp.measured_ids or []:
        row = t.get(swt.collapse_ws(mid))
        if row:
            break
    if row is None:
        return None
    rule, w = row["measured_rule"], row["wood_mdot_sun"]
    flags, notes = [], []
    point, band_dex, bc, upper, edge = w, None, None, False, None
    system_rows = [r for r in t.values() if r["system"] == row["system"]]
    if rule == "point_combined":
        rsq = sum((r["wood_radius_rsun"] or 0.0) ** 2 for r in system_rows)
        point = w * row["wood_radius_rsun"] ** 2 / rsq
        _add(flags, "measured_combined_split")
    elif rule == "upper_limit":
        upper = True
        _add(flags, "measured_upper_limit")
    elif rule == "point_span_both":
        k = row["kislyakova_mdot_sun"]
        if row["kislyakova_scope"] == "combined_system":
            k = k * w / sum(r["wood_mdot_sun"] for r in system_rows)
        lo, hi = min(w, k), max(w, k)
        band_dex = [math.log10(lo / w), math.log10(hi / w)]
        bc = "measured_span"
    elif rule == "point_method_conflict":
        _add(flags, "method_conflict")
    elif rule == "point_method_mixed_system_edge":
        _add(flags, "method_mixed")
        edge = row["kislyakova_mdot_sun"]
        notes.append(NOTE_SYSTEM_EDGE.format(edge=edge))
    measured = {k: row[k] for k in ("row_key", "wood_mdot_sun", "wood_limit", "wood_scope",
                                    "kislyakova_mdot_sun", "kislyakova_limit", "kislyakova_scope",
                                    "measured_rule")}
    measured["system_upper_edge_mdot_sun"] = edge
    rate = point * MDOT_SUN
    return {"tier": "measured", "rate": rate, "band_dex": band_dex, "band": _band_msun(
                rate, *(band_dex or (None, None))),
            "upper": upper, "flags": flags, "notes": notes, "band_construction": bc, "measured": measured,
            "row": row, "log_fx": None, "per_area_log": None, "regime": None}


def _relation_result(tier, x, r, letter, subtype, inp, *, kind, bc, band=None, above_fit=False):
    """A relation-tier value at log F_X ``x`` and radius ``r`` (band from the regime unless given)."""
    flags = []
    pal = per_area_log(x)
    reg = regime_of(x)
    lo, hi = regime_band(x, reg) if band is None else band
    if x >= _ACTIVE_EDGE:
        _add(flags, "active_bimodal")                         # any tier evaluated at log F_X ≥ 6.0
    fast = inp.prot_days is not None and inp.prot_days <= _FAST_ROTATOR_DAYS
    lo, hi, ext = widen(lo, hi, x, letter, subtype, fast_rotator=fast, above_fit=above_fit)
    if fast:
        _add(flags, "fast_rotator")
    if above_fit:
        _add(flags, "above_fit_range")
    if ext:
        _add(flags, "extrapolated")
    if x < _FIT_LO:
        _add(flags, "below_fit_range")
    rate = _mdot(pal, r)
    return {"tier": tier, "rate": rate, "band_dex": [lo, hi], "band": _band_msun(rate, lo, hi),
            "upper": False, "flags": flags, "notes": [], "band_construction": bc, "extrapolation_class": ext,
            "log_fx": x, "log_fx_kind": kind, "per_area_log": pal, "regime": reg}


def class_default_result(inp, letter, subtype, r, state):
    b = class_bin(letter, subtype)
    t = swt.load_cr26_tables()
    st = t["CLASS_STATES"][(b, state)]
    x = st["log_fx"]
    if state == "typical":
        f8 = t["FORK8"][b]
        band, bc = (f8["band_lo"], f8["band_hi"]), "class_mixture"
    else:
        band, bc = (st["band_lo"], st["band_hi"]), "regime"
    res = _relation_result("class_default", x, r, letter, subtype, inp, kind="class_state", bc=bc, band=band)
    # the stored 4-dp state level, not the relation recomputed (§26.5)
    res["per_area_log"] = st["point_log"]
    res["rate"] = _mdot(st["point_log"], r)
    res["band"] = _band_msun(res["rate"], *res["band_dex"])
    if st["marginal"]:
        _add(res["flags"], "marginal_state")
    if b == swt.BIN_M_LATE:
        _add(res["flags"], "bimodal_class")
        res["modes"] = _modes(r)
    res["state"] = state
    return res


def _modes(r):
    t = swt.load_cr26_tables()["CLASS_STATES"]
    out = []
    for name, key in (("inactive", "mode_inactive"), ("saturated", "mode_saturated")):
        m = t[(swt.BIN_M_LATE, key)]
        out.append({"name": name, "weight": m["weight"], "log_fx": m["log_fx"],
                    "mass_loss_msun_yr": _mdot(m["point_log"], r)})
    return out


def nondetection_result(inp, letter, subtype, r, limit, survey):
    """§26.4 — the fork-9 row at the largest grid limit ≤ the star's limit."""
    b = class_bin(letter, subtype)
    rows = swt.load_cr26_tables()["FORK9"][b]
    idx = int(math.floor(limit * 20 + 1e-9))
    row = None if idx < 70 else rows[min(idx, 160)]
    if row is None or row["status"] == "upper_limit_only":
        pal = per_area_log(limit)
        rate = _mdot(pal, r)
        flags = ["xray_upper_limit"]
        if limit < _FIT_LO:
            _add(flags, "below_fit_range")                    # H5
        return {"tier": "xray_nondetection", "rate": rate, "band_dex": None, "band": None, "upper": True,
                "flags": flags, "notes": [], "band_construction": None, "extrapolation_class": None,
                "log_fx": limit, "log_fx_kind": "survey_limit", "per_area_log": pal,
                "regime": regime_of(limit), "limit_log_fx": limit, "limit_survey": survey}
    x = row["conditional_log_fx"]
    res = _relation_result("xray_nondetection", x, r, letter, subtype, inp, kind="conditional_below_limit",
                           bc="truncated_mixture", band=(row["band_lo"], row["band_hi"]))
    res["per_area_log"] = row["point_log"]
    res["rate"] = _mdot(row["point_log"], r)
    res["band"] = _band_msun(res["rate"], *res["band_dex"])
    res["flags"] = ["xray_upper_limit"] + res["flags"]
    if b == swt.BIN_M_LATE and limit >= _BIMODAL_LIMIT:
        _add(res["flags"], "bimodal_class")
        res["modes"] = _modes(r)
    res["limit_log_fx"], res["limit_survey"] = limit, survey
    return res


# ── the X-ray ladder evaluation (pure, over already-fetched rungs) ──────────────
def _eval_blend(inp, blend, own_r, target_bin):
    """System ΣR² + blend flags/notes for the matched source's partners (§26.3.4, J1, H2)."""
    flags, notes, names = [], [], []
    rsq, missing = own_r ** 2, False
    if blend is None:
        return rsq, flags, notes, names
    notes.extend(blend.get("notes") or [])
    if blend.get("status") == "failed":
        _add(flags, "not_authoritative")
        return rsq, flags, notes, names
    if blend.get("partial"):
        _add(flags, "not_authoritative")
    for fs in blend.get("field_stars") or []:
        _add(flags, "field_star_in_beam")
        notes.append(f"field star in the beam (not a partner, no area share): {fs}")
    partner_rsq = 0.0
    for p in blend.get("partners") or []:
        names.append(p["name"])
        pl, psub, psd = parse_sp(p.get("sp_type"))
        pr = select_radius(pl, psub, psd, None, p.get("radius_candidates") or (), partner=True)
        for f in pr["flags"]:
            _add(flags, f)
        if pr["radius_rsun"] is None:
            missing = True
        else:
            partner_rsq += pr["radius_rsun"] ** 2
        pb = class_bin(pl, psub)
        if pb is not None and target_bin is not None and pb != target_bin:
            _add(flags, "blend_mixed_class")
        if p.get("by_designation"):
            _add(flags, "blend_partner_by_designation")
        if p.get("wd"):
            _add(flags, "wd_partner_in_beam")
    if names:
        _add(flags, "blended_source")
        if missing:
            _add(flags, "blend_partner_radius_missing")
        else:
            rsq += partner_rsq
    return rsq, flags, notes, names


def xray_evaluation(inp, letter, subtype, r):
    """Run the §26.1/§26.3 ladder logic over the fetched rungs. Returns
    ``(xray_block, xray_result|None, nondet_result|None, outcome)``."""
    target_bin = class_bin(letter, subtype)
    xb = {"status": "ok", "rung": None, "detection": False, "source_id": None, "epoch": None,
          "separation_arcsec": None, "flux_fit_scale": None, "log_fx": None, "system_log_fx": None,
          "limit_log_fx": None, "limit_survey": None, "erass1_footprint": None, "blended_source": [],
          "rungs": []}
    rungs = inp.rungs or []
    by = {rr["rung"]: rr for rr in rungs}
    e1 = by.get("eRASS1", {}).get("status")
    xb["erass1_footprint"] = (None if e1 in (None, "not_queried") else e1 != "out_of_footprint")
    # XMM guard: evaluated only when no earlier rung detected (G6)
    early = next((rr for rr in rungs if rr["rung"] != "XMM" and rr["status"] == "detection"), None)
    xmm_result, xmm_block, blend_cache = None, None, {}
    x_rr = by.get("XMM")
    if early is None and x_rr and x_rr["status"] == "detection" and not inp.astrom_status:
        cand = x_rr.get("cand") or {}
        if inp.g_status in FAIL_CODES:
            xmm_result = inp.g_status                 # H6: the rung fails; the guard is not evaluated
        else:
            blend_cache["XMM"] = _eval_blend(inp, cand.get("blend"), r, target_bin)
            rsq = blend_cache["XMM"][0]
            logfx_eval = log_fx_from_flux(cand.get("f_x"), inp.d_pc, rsq)
            xmm_result = xmm_guard(inp.g_mag, cand.get("sum_flag"), cand.get("det_ml"), logfx_eval)
            xmm_block = {"g_mag": inp.g_mag, "sum_flag": cand.get("sum_flag"), "det_ml": cand.get("det_ml"),
                         "log_fx": logfx_eval, "result": xmm_result}
    lim = inp.limit or {}
    oc = ladder_outcome([(rr["rung"], rr["status"]) for rr in rungs], inp.astrom_status,
                        lim.get("status") if inp.limit is not None else None, xmm_result)
    xb["rungs"] = oc["rungs"]
    xb["status"] = oc["status"]
    if xmm_result in ("xmm_guard_demoted", "xmm_floor_demoted") and "XMM" in blend_cache:
        oc["guard_notes"] = list(blend_cache["XMM"][2])   # RG8: the blend that set the guard's ΣR² is disclosed
    if xmm_block is not None:
        xb["xmm_guard"] = xmm_block
    xray_res = nondet = None
    if oc["path"] == "detection":
        rr = by[oc["used"]]
        cand = rr.get("cand") or {}
        rsq, bflags, bnotes, names = blend_cache.get(oc["used"]) or _eval_blend(inp, cand.get("blend"), r,
                                                                                 target_bin)
        own = log_fx_from_flux(cand.get("f_x"), inp.d_pc, r * r)
        x = log_fx_from_flux(cand.get("f_x"), inp.d_pc, rsq)
        xb.update(rung=cand.get("rung_label", oc["used"]), detection=True, source_id=cand.get("source_id"),
                  epoch=cand.get("epoch"), separation_arcsec=cand.get("separation_arcsec"),
                  flux_fit_scale=cand.get("f_x"), log_fx=own, blended_source=names,
                  system_log_fx=(x if names else None))
        xray_res = _relation_result("xray", x, r, letter, subtype, inp, kind="detection", bc="regime",
                                    above_fit=x > _FIT_HI)
        for f in bflags:
            _add(xray_res["flags"], f)
        xray_res["notes"].extend(bnotes)
        if oc["used"] == "XMM":
            _add(xray_res["flags"], "xmm_rung")
        if oc["not_authoritative"]:
            _add(xray_res["flags"], "not_authoritative")
    elif oc["path"] == "nondetection" and target_bin is not None:
        f_lim = lim.get("f_limit")
        limit = log_fx_from_flux(f_lim, inp.d_pc, r * r)
        if limit is not None:
            nondet = nondetection_result(inp, letter, subtype, r, limit, lim.get("survey"))
            if xmm_result in ("xmm_guard_demoted", "xmm_floor_demoted"):
                _add(nondet["flags"], xmm_result)
            xb.update(limit_log_fx=limit, limit_survey=lim.get("survey"))
    return xb, xray_res, nondet, oc


# ── assembly ─────────────────────────────────────────────────────────────────────
def _skeleton_xray(status="not_run"):
    return {"status": status, "rung": None, "detection": False, "source_id": None, "epoch": None,
            "separation_arcsec": None, "flux_fit_scale": None, "log_fx": None, "system_log_fx": None,
            "limit_log_fx": None, "limit_survey": None, "erass1_footprint": None, "blended_source": [],
            "rungs": []}


def skeleton(notes=()):
    """R7 — the ``wind_model`` skeleton on a non-ladder result (no disclosures, empty tiers)."""
    return {"model": "cr26", "per_area_log": None, "log_fx": None, "log_fx_kind": None, "regime": None,
            "band_construction": None, "class_bin": None, "state": None, "flags": [],
            "extrapolation_class": None, "modes": None, "xray": _skeleton_xray(), "radius": None,
            "measured": None, "tiers": {}, "notes": list(notes)}


def _disclosures(tier, res, state_source):
    out = [DISCLOSURE_WHAT[tier]]
    for i in (2, 3, 4, 5, 6, 7):
        out.append(DISCLOSURES[i])
    if tier == "class_default" and res.get("state") == "quiet" and "marginal_state" in res["flags"]:
        out.append(DISCLOSURES[8])
    out.extend([DISCLOSURES[9], DISCLOSURES[10]])
    for f in res["flags"]:
        if f == "subtype_unknown":
            continue                                   # its note is already carried verbatim
        key = f"extrapolated:{res.get('extrapolation_class')}" if f == "extrapolated" else f
        if key in FLAG_TEXT:
            out.append(f"flag {f}: {FLAG_TEXT[key]}")
    if "xmm_rung" in res["flags"]:
        out.append(DISCLOSURES[12])
    if "below_fit_range" in res["flags"]:
        out.append(DISCLOSURES[13])
    if tier == "class_default" and state_source == "otype_auto":
        out.append(DISCLOSURES[14])
    return out


def _measured_disclosures(res, evolved):
    out = [DISCLOSURE_MEASURED["wood_x2"], DISCLOSURE_MEASURED["ism"]]
    rule = res["measured"]["measured_rule"]
    if rule == "point_combined":
        out.append(DISCLOSURE_MEASURED["combined"])
    if "method_conflict" in res["flags"]:
        out.append(DISCLOSURE_MEASURED["method_conflict"])
    if "method_mixed" in res["flags"]:
        out.append(DISCLOSURE_MEASURED["method_mixed"])
    if rule in ("point_span_both", "point_method_mixed_system_edge"):
        out.append(DISCLOSURE_MEASURED["kislyakova"])
    if "measured_upper_limit" in res["flags"]:
        out.append(f"flag measured_upper_limit: {FLAG_TEXT['measured_upper_limit']}")
    if evolved:
        out.append(DISCLOSURE_MEASURED["evolved_v400"])
    return out


def _entry_from(res, status_override=None, extra_flags=()):
    if res is None:
        return None
    flags = list(res["flags"]) + [f for f in extra_flags if f not in res["flags"]]
    return _entry(res["rate"], res["band"], status_override or "ok", res.get("log_fx"), flags, res["upper"])


def resolve_wind_model(inp):
    """The public entry: :func:`_resolve_wind_model` + the ``h1_miss`` marker (RG9 — H1's string match found no
    row after a failed identity lookup; a caller that discards the model keeps its note + flag via
    :func:`h1_carry`)."""
    res = _resolve_wind_model(inp)
    res["h1_miss"] = bool(inp.measured_miss_not_authoritative)
    return res


def h1_carry(model):
    """RG9 — ``(notes, flags)`` a caller keeps when it discards a non-ladder ``model`` (the evolved non-measured
    route): on an H1 miss, the model's notes (H1's among them) and ``not_authoritative``; else nothing."""
    if not (model and model.get("h1_miss")):
        return [], []
    return list((model.get("wind_model") or {}).get("notes") or []), ["not_authoritative"]


def _resolve_wind_model(inp):
    """The §26.1 ladder for an in-scope (or evolved-measured) star → the model result dict:

    ``{mass_loss_tier, rate, upper, band, band_dex, label, provenance, standoff_rate, wind_model,
    unused_wind_state, state_source}``. ``rate`` is M☉/yr (``None`` for ``none``). The caller routes the
    ``noncoronal_row`` / ``none`` tiers through today's code path (``tier=None``)."""
    letter, subtype, is_sd = parse_sp(inp.sp_type)
    b = class_bin(letter, subtype)
    notes = list(inp.notes)
    evolved = inp.domain == "evolved"
    scope = in_scope(inp.domain, letter)
    wm = skeleton()
    wm["class_bin"] = b if scope else None

    meas = measured_result(inp) if (scope or evolved) else None

    if not scope and meas is None:
        # H7: an Am-type string (parse letter outside FGKM, CR-25 colour inside) → noncoronal on the parse row
        h7 = (letter if (inp.domain == "main_sequence" and letter and letter not in ("F", "G", "K", "M")
                         and inp.cr25_letter in ("F", "G", "K", "M")) else None)
        if h7:
            notes.append(NOTE_H7.format(letter=h7))
        wm["notes"] = notes
        if inp.supplied_rate is not None:
            # a supplied rate is tier 1 on every path; an out-of-scope star reaches only its CR-22 row
            wm["tiers"] = {"noncoronal_row": _entry(inp.noncoronal_rate, None, "ok")}
            return {"mass_loss_tier": "supplied", "rate": inp.supplied_rate, "wind_model": wm, "label": None,
                    "h7_letter": h7, "upper": False, "band": None, "band_dex": None, "standoff_rate": None}
        if inp.domain == "main_sequence" and letter is None:
            # no spectral type at all: no CR-26 tier — the caller keeps today's path (legacy_row / none)
            if inp.measured_miss_not_authoritative:
                _add(wm["flags"], "not_authoritative")          # RG5: H1 miss — a measured row could have set it
            return {"mass_loss_tier": "none", "rate": None, "wind_model": wm, "label": None, "h7_letter": None,
                    "typeless": True}
        if inp.measured_miss_not_authoritative:
            _add(wm["flags"], "not_authoritative")              # RG9: H1's miss, whatever tier then sets the rate
        return {"mass_loss_tier": "noncoronal_row", "rate": None, "wind_model": wm, "label": None, "h7_letter": h7}

    # G10: a non-state explicit wind_class → noncoronal_row on that row
    wc = (inp.wind_class or "").strip().lower()
    if wc and wc not in ("quiet", "solar", "active") and meas is None and inp.supplied_rate is None:
        notes.append(NOTE_G10_BYPASS.format(wc=wc))
        wm["notes"] = notes
        if inp.measured_miss_not_authoritative:
            _add(wm["flags"], "not_authoritative")              # RG9: H1's miss, whatever tier then sets the rate
        return {"mass_loss_tier": "noncoronal_row", "rate": None, "wind_model": wm, "label": None}

    state, state_src = _select_state(inp, letter)
    hot = state_src.startswith("hot:")
    base_src = state_src.split(":", 1)[1] if hot else state_src
    label = STATE_LABEL[state] if scope else None

    # ── radius (the target) ──
    rad = select_radius(letter, subtype, is_sd, inp.radius_rsun, inp.radius_candidates, inp.radius_status,
                        main_id=inp.main_id, cone_other=inp.cone_other, gcns_neighbour=inp.gcns_neighbour)
    r = rad["radius_rsun"]
    notes.extend(rad["notes"])

    # ── X-ray / non-detection (catalog ladder, or supplied) ──
    xray_res = nondet = None
    xb = _skeleton_xray("not_run")
    oc = None
    if scope:
        if inp.log_fx is not None:                     # a supplied flux replaces the ladder (§26.3.6)
            xb.update(rung="supplied", log_fx=inp.log_fx)
            if r is not None:
                xray_res = _relation_result("xray", inp.log_fx, r, letter, subtype, inp, kind="supplied",
                                            bc="regime", above_fit=inp.log_fx > _FIT_HI)
        elif inp.log_fx_limit is not None:             # a supplied limit replaces the ladder AND the limit
            xb.update(limit_survey="supplied", limit_log_fx=inp.log_fx_limit)
            if r is not None and b is not None:
                nondet = nondetection_result(inp, letter, subtype, r, inp.log_fx_limit, "supplied")
        elif inp.network and r is not None:
            xb, xray_res, nondet, oc = xray_evaluation(inp, letter, subtype, r)
        elif inp.network and r is None:
            # subtype_unknown with no catalog radius: the lookups ran but no radius → no usable value
            xb, _x, _n, oc = xray_evaluation(inp, letter, subtype, 1.0)
            xb.update(log_fx=None, system_log_fx=None, limit_log_fx=None)
        if not inp.network and inp.log_fx is None and inp.log_fx_limit is None:
            if inp.not_run_reason == "no_distance":
                notes.append(NOTE_NO_DISTANCE)
            elif inp.not_run_reason == "network_disabled":
                notes.append(NOTE_NETWORK_OFF)
    lookup_failed = bool(oc and oc["path"] == "failed")
    if oc:
        notes.extend(n for n in oc.get("guard_notes") or [] if n not in notes)
    # RG5 (MSG 311): a failed identity lookup that kept the ladder from running blocked the catalog tiers
    ident_blocked = inp.identity_failed and inp.not_run_reason == "no_identity"
    for _r in (xray_res, nondet):
        if _r is not None:
            for f in rad["flags"]:
                _add(_r["flags"], f)

    # ── class default at the selected state ──
    cls = class_default_result(inp, letter, subtype, r, state) if (scope and b is not None and r is not None) \
        else None
    if cls is not None:
        for f in rad["flags"]:
            _add(cls["flags"], f)

    # ── precedence ──
    if inp.supplied_rate is not None:
        used = "supplied"
    elif meas is not None:
        used = "measured"
    elif xray_res is not None:
        used = "xray"
    elif nondet is not None:
        used = "xray_nondetection"
    elif cls is not None and hot:
        used = "noncoronal_hot"
    elif cls is not None:
        used = "class_default"
    else:
        used = "none"

    # ── tiers below the used one (Q4 + G2 + K1) ──
    tiers = {}
    order = ["supplied", "measured", "xray", "xray_nondetection", "class_default"]
    if evolved and not scope:
        if used in ("supplied", "measured"):
            tiers["noncoronal_row"] = _entry(inp.noncoronal_rate, None, "ok")
    else:
        start = order.index(used) + 1 if used in order else len(order)
        for t in order[start:] if used in order else []:
            if t == "measured":
                tiers[t] = _entry_from(meas) if meas else _entry(status="not_reachable")
            elif t == "xray":
                if xray_res is not None:
                    tiers[t] = _entry_from(xray_res)
                elif lookup_failed or ident_blocked:
                    tiers[t] = _entry(status="failed")
                else:
                    tiers[t] = _entry(status="not_reachable")
            elif t == "xray_nondetection":
                if nondet is not None:
                    tiers[t] = _entry_from(nondet)
                elif lookup_failed or ident_blocked:
                    tiers[t] = _entry(status="failed")
                else:
                    tiers[t] = _entry(status="not_reachable")
            elif t == "class_default":
                tiers[t] = _entry_from(cls) if cls is not None else _entry(status="not_reachable")
        if used == "measured" and meas["upper"] and xray_res is not None:
            xp = xray_res["rate"] / MDOT_SUN
            lim = meas["measured"]["wood_mdot_sun"]
            notes.append(NOTE_T12.format(xp=xp, dir=("below" if xp < lim else "above"), lim=lim))

    # ── the used result ──
    res = {"measured": meas, "xray": xray_res, "xray_nondetection": nondet, "class_default": cls}.get(used)
    flags = []
    if used == "none" and scope and b is None and lookup_failed:
        _add(flags, "not_authoritative")
    if b is None and scope:
        _add(flags, "subtype_unknown")
        notes.append(NOTE_SUBTYPE_UNKNOWN)
    if res is not None:
        for f in res["flags"]:
            _add(flags, f)
        notes.extend(res.get("notes") or [])
    if used in ("class_default", "noncoronal_hot") and lookup_failed:
        _add(flags, "not_authoritative")
    if used not in ("supplied", "measured") and inp.measured_miss_not_authoritative:
        _add(flags, "not_authoritative")    # H1: a measured row could have been missed — any lower tier (RG5 / RG9)

    # unused inputs (§26.1 / G10 / R10 / §26.6)
    unused_ws = None
    if used in ("measured", "xray", "xray_nondetection") and scope:
        if wc in ("quiet", "solar", "active"):
            notes.append(NOTE_UNUSED_WIND_CLASS.format(wc=wc, tier=used))
        elif inp.wind_state:
            unused_ws = inp.wind_state
            notes.append(NOTE_UNUSED_WIND_STATE.format(ws=inp.wind_state, tier=used))
    if used in LADDER_TIERS:
        if inp.mass_loss_source:
            notes.append(NOTE_IGNORED_SOURCE.format(src=inp.mass_loss_source))
        if inp.wind_speed is not None:
            notes.append(NOTE_IGNORED_SPEED.format(v=inp.wind_speed))
    if used == "none" and inp.wind_state:
        notes.append(NOTE_H3)

    # ── wind_model ──
    wm["xray"] = xb
    wm["radius"] = radius_public(rad) if scope else None
    wm["flags"] = flags
    wm["tiers"] = tiers
    wm["measured"] = meas["measured"] if meas else None
    if res is not None and used != "measured":
        wm.update(per_area_log=res["per_area_log"], log_fx=res["log_fx"], log_fx_kind=res.get("log_fx_kind"),
                  regime=res["regime"], band_construction=res["band_construction"],
                  extrapolation_class=res.get("extrapolation_class"), modes=res.get("modes"),
                  state=(res.get("state") if used == "class_default" else None))
        if res.get("band_construction") == "regime" and res["log_fx"] is not None:
            _regime_edge_note(res["log_fx"], notes)
    elif used == "measured":
        wm["band_construction"] = meas["band_construction"]
    if used in ("xray", "xray_nondetection", "class_default"):
        notes.extend(_disclosures(used, dict(res, flags=flags), base_src))
    elif used == "measured":
        notes.extend(_measured_disclosures(meas, evolved))
    wm["notes"] = notes

    if used == "noncoronal_hot":
        return {"mass_loss_tier": "noncoronal_row", "rate": None, "wind_model": wm, "label": None,
                "hot": True, "state_source": base_src}
    out = {"mass_loss_tier": used, "wind_model": wm, "label": label, "state_source": base_src,
           "unused_wind_state": unused_ws, "rate": None, "upper": False, "band": None, "band_dex": None,
           "standoff_rate": None}
    if used == "supplied":
        out.update(rate=inp.supplied_rate)
    elif res is not None:
        out.update(rate=res["rate"], upper=res["upper"], band=res["band"], band_dex=res["band_dex"],
                   standoff_rate=res["rate"])
    return out


def _regime_edge_note(x, notes):
    for edge, e, lo_reg, hi_reg in (("quiet/mid", _QUIET_EDGE, "quiet", "mid"),
                                    ("mid/active", _ACTIVE_EDGE, "mid", "active")):
        if abs(x - e) < _REGIME_EDGE_WINDOW:
            nb = hi_reg if x < e else lo_reg
            lo, hi = regime_band(x, nb)
            notes.append(NOTE_REGIME_EDGE.format(x=x, edge=edge, e=e, nb=nb, lo=lo, hi=hi))
