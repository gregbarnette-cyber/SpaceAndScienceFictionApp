"""CR-30 — the main-sequence relations module: S1's lookup by spectral type (CR-30.2), and (Stage 3) the
mass / luminosity / radius relations and the MIST v2.5 lifetime (CR-30.4–30.5).

Pure: reads only the md5-verified tables of ``core.ms_reference_tables``; no network, no Qt, no DB.
"""

import math

from core import ms_reference_tables as mrt
from core import shared

_LETTERS = "OBAFGKM"
_COLS = ("Teff", "B-V", "Mv", "BCv", "logL", "R_Rsun", "Msun")
# Letter-only F / G / K read the class's middle row (ruling 21); the note states the class's span in L.
_LETTER_ONLY_MIDDLE = {"F": "F5V", "G": "G5V", "K": "K5V"}


def _ordinal(letter, subtype):
    return _LETTERS.index(letter) * 10.0 + float(subtype)


_INDEX = {}


def _s1_index():
    """``[(ordinal, row)]`` in S1 order (strictly increasing ordinal — S1 is one ordered sequence); memoised per
    loaded S1 table (CP1)."""
    rows = mrt.s1_rows()
    hit = _INDEX.get(id(rows))
    if hit is not None and hit[0] is rows:
        return hit[1]
    out = []
    for r in rows:
        p = shared.parse_spectral_type(r["SpT"])
        out.append((_ordinal(p.letter, p.subtype), r))
    _INDEX.clear()
    _INDEX[id(rows)] = (rows, out)
    return out


def letter_span_ratio(letter):
    """S1's span in L across a class's rows (max L / min L) — the letter-only note (F 4.8×, G 2.5×, K 5.8×)."""
    ls = [r["logL"] for r in mrt.s1_rows() if r["SpT"][0] == letter and r["logL"] is not None]
    return 10 ** (max(ls) - min(ls)) if ls else None


def _empty(parse, reason, **kw):
    out = {c: None for c in _COLS}
    out.update({"L_lsun": None, "sp_type_read": parse.read if parse else None, "s1_rows": None, "s1_fraction": None,
                "subtype_unknown": False, "subtype_span_note": None, "s1_null_reason": reason})
    out.update(kw)
    return out


def s1_at(sp):
    """CR-30.2's lookup — S1's values at a spectral type (a string or a ``shared.SpParse``).

    An exact S1 row is used as published; otherwise linear interpolation in subtype along S1's ordered rows,
    across a class edge (G9.5 between G9V and K0V) — ``logL`` interpolated in log (it is already log₁₀ L),
    every other column linearly; never into a placeholder cell (that column is ``None``). Letter-only F / G / K
    read F5V / G5V / K5V with ``subtype_unknown``; letter-only M / O / B / A read ``None`` with
    ``subtype_unknown``; a type outside O3V–M9.5V (incl. any L / T / Y / D) reads ``None`` with its reason.

    → ``{Teff, B-V, Mv, BCv, logL, L_lsun (10^logL), R_Rsun, Msun, sp_type_read, s1_rows, s1_fraction, subtype_unknown,
    subtype_span_note, s1_null_reason}``.
    """
    p = sp if isinstance(sp, shared.SpParse) else shared.parse_spectral_type(sp)
    if p.letter is None:
        return _empty(p, "no spectral class could be read from the type")
    if p.letter not in _LETTERS:
        return _empty(p, f"type {p.read} is outside S1's O3V–M9.5V span (S1 is a main-sequence table)")
    if p.subtype is None:
        mid = _LETTER_ONLY_MIDDLE.get(p.letter)
        if mid is None:
            return _empty(p, f"letter-only type '{p.letter}' — S1 needs a subtype (e.g. {p.letter}4V)",
                          subtype_unknown=True)
        row = next(r for r in mrt.s1_rows() if r["SpT"] == mid)
        out = {c: row[c] for c in _COLS}
        out.update({"sp_type_read": p.read, "s1_rows": [mid], "s1_fraction": None, "subtype_unknown": True,
                    "subtype_span_note": (f"letter-only '{p.letter}' read at {mid}; S1's {p.letter} class spans "
                                          f"{letter_span_ratio(p.letter):.1f}x in L"),
                    "s1_null_reason": None})
        return _with_l(out)
    x = _ordinal(p.letter, p.subtype)
    idx = _s1_index()
    if x < idx[0][0] or x > idx[-1][0]:
        return _empty(p, f"type {p.read} is outside S1's O3V–M9.5V span")
    for ox, row in idx:
        if ox == x:
            out = {c: row[c] for c in _COLS}
            out.update({"sp_type_read": p.read, "s1_rows": [row["SpT"]], "s1_fraction": None,
                        "subtype_unknown": False, "subtype_span_note": None, "s1_null_reason": None})
            return _with_l(out)
    for (oa, ra), (ob, rb) in zip(idx, idx[1:]):
        if oa < x < ob:
            f = (x - oa) / (ob - oa)
            out = {}
            for c in _COLS:
                va, vb = ra[c], rb[c]
                out[c] = None if (va is None or vb is None) else va + f * (vb - va)
            out.update({"sp_type_read": p.read, "s1_rows": [ra["SpT"], rb["SpT"]], "s1_fraction": f,
                        "subtype_unknown": False, "subtype_span_note": None, "s1_null_reason": None})
            return _with_l(out)
    return _empty(p, f"type {p.read} could not be placed on S1's sequence")  # unreachable (span checked)


def _with_l(out):
    out["L_lsun"] = None if out.get("logL") is None else 10 ** out["logL"]
    return out


def s1_luminosity(read):
    """10^logL of an ``s1_at`` result, or ``None``."""
    return None if read.get("logL") is None else 10 ** read["logL"]


def s1_display_rows():
    """``main-sequence``'s rows — S1's 87 rows with the computed columns labelled (CR-30.1 display):
    S1's columns as published (the file's strings converted to numbers, an empty cell ``None``), plus
    ``Mbol_computed`` (M_V + BC_V), ``density_computed_gcc`` / ``density_computed_rho_sun`` (from M and R) and
    ``ms_lifetime_gyr_computed`` (MIST v2.5 at S1's mass — CR-30.5) with its end point."""
    rho_sun_gcc = 1.98847e33 / (4.0 / 3.0 * math.pi * (6.957e10 ** 3))
    out = []
    for r in mrt.s1_rows():
        m, rad = r["Msun"], r["R_Rsun"]
        rho = (m / rad ** 3) if (m is not None and rad) else None
        life = ms_lifetime(m) if m is not None else None
        out.append({"SpT": r["SpT"], "Teff": r["Teff"], "B-V": r["B-V"], "Mv": r["Mv"], "BCv": r["BCv"],
                    "logL": r["logL"], "R_Rsun": rad, "Msun": m, "s1_line": r["s1_line"],
                    "Mbol_computed": (r["Mv"] + r["BCv"]) if (r["Mv"] is not None and r["BCv"] is not None)
                    else None,
                    "density_computed_rho_sun": rho,
                    "density_computed_gcc": rho * rho_sun_gcc if rho is not None else None,
                    "ms_lifetime_gyr_computed": (life["yr"] / 1e9) if life and life["yr"] is not None else None,
                    "ms_lifetime_end_point": life["end_point"] if life else None})
    return out


# ── CR-30.5 — the MIST v2.5 main-sequence lifetime ────────────────────────────────────────────────────
MIST_MIN_MSUN, MIST_MAX_MSUN = 0.10, 300.0


def ms_lifetime(mass):
    """MIST v2.5 (non-rotating, [Fe/H] 0) main-sequence duration from ZAMS at ``mass`` (M☉):
    ``{yr, end_point, interpolated, status, note}``.

    log t linear in log M between adjacent tracks (ruling 60; the 1.15 → 1.16 M☉ reversal kept as published);
    an exact track mass reads its row. The end point is each track's (``first_Xc_lt_1e-4`` from 0.65 M☉ up,
    ``first_Xc_lt_1e-2`` below); a value between a 10⁻² and a 10⁻⁴ track (0.60–0.65 M☉) is
    ``interpolated_1e-2_to_1e-4``. Outside 0.10–300 M☉ the value is ``None`` with a status (``below_0.10`` /
    ``above_300``) — the caller applies CR-30.5's per-placement treatment."""
    if mass is None or not (mass > 0) or math.isinf(mass):
        return {"yr": None, "end_point": None, "interpolated": False, "status": "mass_null",
                "note": "no mass — no main-sequence lifetime"}
    tr = mrt.mist_tracks()
    if mass < MIST_MIN_MSUN:
        return {"yr": None, "end_point": None, "interpolated": False, "status": "below_0.10",
                "note": "below MIST v2.5's lowest track (0.10 Msun)"}
    if mass > MIST_MAX_MSUN:
        return {"yr": None, "end_point": None, "interpolated": False, "status": "above_300",
                "note": "above MIST v2.5's highest track (300 Msun) — no lifetime"}
    for t in tr:
        if t["initial_mass"] == mass:
            return {"yr": t["ms_duration_yr"], "end_point": t["end_point"], "interpolated": False,
                    "status": "value", "note": None}
    for a, b in zip(tr, tr[1:]):
        if a["initial_mass"] < mass < b["initial_mass"]:
            f = (math.log10(mass) - math.log10(a["initial_mass"])) / (
                math.log10(b["initial_mass"]) - math.log10(a["initial_mass"]))
            lt = math.log10(a["ms_duration_yr"]) + f * (math.log10(b["ms_duration_yr"])
                                                          - math.log10(a["ms_duration_yr"]))
            ep = a["end_point"] if a["end_point"] == b["end_point"] else "interpolated_1e-2_to_1e-4"
            note = ("interpolated from a 10^-2 track to a 10^-4 track" if ep == "interpolated_1e-2_to_1e-4"
                    else None)
            return {"yr": 10 ** lt, "end_point": ep, "interpolated": True, "status": "value", "note": note}
    return {"yr": None, "end_point": None, "interpolated": False, "status": "mass_null", "note": None}


# ── CR-30.3 — the region luminosity's zero point and the M-dwarf colour route ──────────────────────────────────────
# S1's own M_bol,☉ (IAU 2015 B2 — the scale S1's BCv and logL are computed on): a property of the vendored table.
M_BOL_SUN_S1 = 4.74
# Mann et al. 2015 (arXiv:1501.01635) Table 3 base rows on X = V − J, and their zero point (m☉ = −26.8167).
MANN15_ZP = 4.755
_MANN15_BCV = (0.5817, -0.4168, -0.08165, 4.084e-3)
_MANN15_BCK = (1.421, 0.6084, -0.09655, 6.263e-3)
COLOUR_VJ_LO, COLOUR_VJ_HI = 2.53, 6.98
COLOUR_DISAGREE_RATIO = 1.40


def luminosity_from_mbol(mbol, zp=M_BOL_SUN_S1):
    """L / L☉ = 10^(−0.4 (M_bol − zp)) — the exact step 10^0.4 (CR-30.3; ruling 9)."""
    return 10 ** (-0.4 * (mbol - zp))


def _poly(c, x):
    return c[0] + c[1] * x + c[2] * x * x + c[3] * x ** 3


def colour_gate(parse, v_minus_j):
    """``(applies, reason)`` — the colour route's gate: a K or M type (letter-only included) with no luminosity-class
    token I–IV (a giant / subgiant takes the subtype route with the class flag — pre-fire ruling 19 R-7; a flagged
    late-M / L III–IV is low gravity, so already no class token) and V − J inside 2.53–6.98 inclusive."""
    if parse.letter not in ("K", "M"):
        return False, "not a K / M type"
    if parse.lum_class_core in ("I", "II", "III", "IV"):
        return False, f"luminosity class {parse.lum_class_token} (a giant / subgiant) — S1's subtype route"
    if v_minus_j is None:
        return False, "no V − J"
    if not (COLOUR_VJ_LO <= v_minus_j <= COLOUR_VJ_HI):
        return False, f"V − J {v_minus_j:.3f} outside the colour route's span 2.53–6.98"
    return True, None


def colour_route_luminosity(vmag, j, ks, plx_mas):
    """Mann et al. 2015's two paths on X = V − J → ``{lum, bc_v_path_lum, bc_k_path_lum, bc_v, bc_k, m_v, m_ks,
    v_minus_j}`` (L = their mean; M_bol at Mann's zero point 4.755 — the ×1.014 against 4.74 disclosed)."""
    x = vmag - j
    dm = 5.0 * math.log10(1000.0 / plx_mas) - 5.0
    m_v, m_ks = vmag - dm, ks - dm
    bc_v, bc_k = _poly(_MANN15_BCV, x), _poly(_MANN15_BCK, x)
    lv = luminosity_from_mbol(m_v + bc_v, MANN15_ZP)
    lk = luminosity_from_mbol(m_ks + bc_k, MANN15_ZP)
    return {"lum": 0.5 * (lv + lk), "bc_v_path_lum": lv, "bc_k_path_lum": lk, "bc_v": bc_v, "bc_k": bc_k,
            "m_v": m_v, "m_ks": m_ks, "v_minus_j": x}


# ── CR-30.4 — the mass, luminosity and radius relations (F9) ──────────────────────────────────────────────────────
# S12: Eker et al. 2018 (MNRAS 479, 5491) Table 4 — log L = a log M + b, central coefficients; (M_lo, M_hi] ranges.
_S12 = (
    ("0.179-0.45", 0.179, 0.45, 2.028, -0.976),     # below the switch — never read (ruling 51)
    ("0.45-0.72", 0.45, 0.72, 4.572, -0.102),
    ("0.72-1.05", 0.72, 1.05, 5.743, -0.007),
    ("1.05-2.40", 1.05, 2.40, 4.329, 0.010),
    ("2.4-7", 2.40, 7.0, 3.967, 0.093),
    ("7-31", 7.0, 31.0, 2.865, 1.105),
)
LOGL_SWITCH = -1.066          # S12 inverted meets S1's sequence (0.615 M☉; WB's bisection, ruling 55)
LOGL_S12_TOP = 5.37775        # S12's top (31 M☉; pre-fire record §19, B-A18)
S1_MASS_SPAN = (0.078, 59.0)  # S1's mass span — L(M) / R(M) null outside it (ruling 144; pre-fire ruling 14)


def _seg(name):
    return next(s for s in _S12 if s[0] == name)


def _s12_logl(seg, m):
    return seg[3] * math.log10(m) + seg[4]


def _s12_inv(seg, logl):
    return 10 ** ((logl - seg[4]) / seg[3])


# the midpoint switches at the three down-step breaks (the mean of the two segments' log L at the break mass)
SWITCH_072 = 0.5 * (_s12_logl(_seg("0.45-0.72"), 0.72) + _s12_logl(_seg("0.72-1.05"), 0.72))   # −0.790308
SWITCH_105 = 0.5 * (_s12_logl(_seg("0.72-1.05"), 1.05) + _s12_logl(_seg("1.05-2.40"), 1.05))   # 0.108209
SWITCH_240 = 0.5 * (_s12_logl(_seg("1.05-2.40"), 2.40) + _s12_logl(_seg("2.4-7"), 2.40))       # 1.628616
GAP7_LO = _s12_logl(_seg("2.4-7"), 7.0)        # 3.4455 — the 7 M☉ up-step: no mass gives log L in (GAP7_LO, GAP7_HI)
GAP7_HI = _s12_logl(_seg("7-31"), 7.0)         # 3.5262
M_SWITCH = _s12_inv(_seg("0.45-0.72"), LOGL_SWITCH)   # 0.615391 M☉ — the L(M) mirror's switch mass


_PAIRS = {}


def _s1_pairs(xkey, ykey):
    """S1's (log x, log y) pairs sorted by x (``Msun`` sorted for R / L of M; ``logL`` for M of L) — memoised per
    loaded S1 table (CP6 #9)."""
    rows = mrt.s1_rows()
    hit = _PAIRS.get((xkey, ykey))
    if hit is not None and hit[0] is rows:
        return hit[1]
    pts = []
    for r in rows:
        x, y = r[xkey], r[ykey]
        if x is None or y is None:
            continue
        lx = x if xkey == "logL" else math.log10(x)
        ly = y if ykey == "logL" else math.log10(y)
        pts.append((lx, ly))
    pts.sort()
    pts = tuple(pts)                                       # shared by every caller — immutable
    _PAIRS[(xkey, ykey)] = (rows, pts)
    return pts


def _interp(pts, x):
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        if xa <= x <= xb:
            if xb == xa:
                return ya
            return ya + (x - xa) / (xb - xa) * (yb - ya)
    return None


_DOWN_BREAKS = (("0.72", "0.45-0.72", "0.72-1.05", 0.72), ("1.05", "0.72-1.05", "1.05-2.40", 1.05),
                ("2.40", "1.05-2.40", "2.4-7", 2.40))


def _switch_band(logl):
    """The down-step break whose dual-valued band holds ``logl`` (both segments give a mass there — the midpoint
    switch decides which is read), else None (CP3: the band spans both segments' log L at the break mass)."""
    for name, a, b, m in _DOWN_BREAKS:
        la, lb = _s12_logl(_seg(a), m), _s12_logl(_seg(b), m)
        if min(la, lb) <= logl <= max(la, lb):
            return name
    return None


def mass_from_luminosity(lum):
    """CR-30.4's mass from L (rulings 41, 51, 55, 78 (v), 144) → ``{mass, relation, segment, switch_band, reason}``.

    S12 inverted from log L −1.066 to 5.37775 on the segment whose L range holds the star's L, with the midpoint
    switches at 0.72 / 1.05 / 2.40 M☉ (the lower-mass segment below the mean log L, the higher-mass segment at or
    above it) and an L inside the 7 M☉ up-step gap → 7.0 M☉; S1's sequence (log M linear in log L) below the switch
    and above 31 M☉; **no clamp** — log L below M9.5V's −3.57 (or above O3V's) → ``mass`` None with the reason."""
    out = {"mass": None, "relation": None, "segment": None, "switch_band": None, "reason": None}
    if lum is None or not (lum > 0) or math.isinf(lum):
        out["reason"] = "no luminosity"
        return out
    logl = math.log10(lum)
    s1 = _s1_pairs("logL", "Msun")
    lo, hi = s1[0][0], s1[-1][0]
    if logl < lo:
        out["reason"] = (f"log L {logl:.4f} below S1's last row (M9.5V, log L {lo:.2f}) — no mass "
                         "(never clamped to S1's last mass)")
        return out
    if logl < LOGL_SWITCH or logl > LOGL_S12_TOP:
        if logl > hi:
            out["reason"] = f"log L {logl:.4f} above S1's first row (O3V, log L {hi:.2f})"
            return out
        out.update(mass=10 ** _interp(s1, logl), relation="S1_sequence",
                   segment="below the switch" if logl < LOGL_SWITCH else "above S12's 31 M☉ top")
        return out
    out["relation"] = "Eker2018_inverted"
    if logl < SWITCH_072:
        seg = "0.45-0.72"
    elif logl < SWITCH_105:
        seg = "0.72-1.05"
    elif logl < SWITCH_240:
        seg = "1.05-2.40"
    elif logl < GAP7_LO:
        seg = "2.4-7"
    elif logl <= GAP7_HI:
        out.update(mass=7.0, segment="7 M☉ up-step gap", switch_band="7.0_gap")
        return out
    else:
        seg = "7-31"
    band = _switch_band(logl)
    out.update(mass=_s12_inv(_seg(seg), logl), segment=seg, switch_band=band)
    return out


def luminosity_from_mass(mass):
    """CR-30.4's L from M — the mirror (ruling 53): S12 forward from the switch mass (0.615 M☉) to 31 M☉ by S12's
    own mass ranges and their inclusive upper edges; S1's sequence (log L linear in log M) below 0.615 and above 31;
    **null outside S1's mass span 0.078–59 M☉** with its reason → ``{lum, relation, reason}``."""
    if mass is None or not (mass > 0) or math.isinf(mass):
        return {"lum": None, "relation": None, "reason": "no mass"}
    if mass < S1_MASS_SPAN[0] or mass > S1_MASS_SPAN[1]:
        return {"lum": None, "relation": None,
                "reason": f"mass {mass:g} Msun outside S1's mass span 0.078-59 Msun — no L(M)"}
    if mass < M_SWITCH or mass > 31.0:
        return {"lum": 10 ** _interp(_s1_pairs("Msun", "logL"), math.log10(mass)), "relation": "S1_sequence",
                "reason": None}
    for seg in _S12[1:]:
        if seg[1] < mass <= seg[2] or (seg[0] == "0.45-0.72" and mass <= seg[2]):
            return {"lum": 10 ** _s12_logl(seg, mass), "relation": "Eker2018_forward", "segment": seg[0],
                    "reason": None}
    return {"lum": None, "relation": None, "reason": "no S12 segment"}         # unreachable


def radius_from_mass(mass):
    """CR-30.4's R from M (rulings 54, 94): S1's (mass, radius) pairs **sorted by mass**, log R linear in log M;
    null outside S1's mass span 0.078–59 M☉ with its reason → ``{radius, relation, reason}``."""
    if mass is None or not (mass > 0) or math.isinf(mass):
        return {"radius": None, "relation": None, "reason": "no mass"}
    if mass < S1_MASS_SPAN[0] or mass > S1_MASS_SPAN[1]:
        return {"radius": None, "relation": None,
                "reason": f"mass {mass:g} Msun outside S1's mass span 0.078-59 Msun — no R(M)"}
    return {"radius": 10 ** _interp(_s1_pairs("Msun", "R_Rsun"), math.log10(mass)),
            "relation": "S1_sorted_by_mass", "reason": None}


# S13: Mann et al. 2019 (ApJ 871, 63) Table 6, n = 5, zero point 7.5, no [Fe/H] term (ruling 52).
_MANN19 = (-0.642, -0.208, -8.43e-4, 7.87e-3, 1.42e-4, -2.13e-4)
MKS_GATE = (4.5, 10.5)        # inclusive (ruling 93 L1) — never clipped to it
MKS_BINARY_DISCLOSURE = ("M_Ks route (Mann et al. 2019): an unresolved binary's combined Ks over-reads the mass — "
                         "no catalog signal separates a single star from an unresolved pair (S13)")
MKS_ACTIVITY_CAVEAT = "Mann et al. 2019: an active star's M_Ks mass carries an ≈ 2 % activity caveat (S13 L1222)"


def mks_mass(m_ks):
    """Mann et al. 2019's n = 5 mass at M_Ks inside the 4.5–10.5 gate (inclusive), else None (never clipped)."""
    if m_ks is None or not (MKS_GATE[0] <= m_ks <= MKS_GATE[1]):
        return None
    x = m_ks - 7.5
    return 10 ** sum(a * x ** i for i, a in enumerate(_MANN19))


# ── CR-30 §7 / §13.6 C5: the every-run disclosures (a static ``cr30_disclosures`` key on each output that reads S1,
# MIST or the over-read factor; per-run disclosures stay in each output's own notes beside the value they qualify) ──
CR30_DISCLOSURES = {
    "s1": ("S1 (Mamajek, 2022.04.16) is a class-V, solar-composition table: an evolved or subdwarf type is read at "
           "its class-V row and flagged; metal-poor (globular-cluster / bulge) stars score 1.05–1.50 on every "
           "relation; a letter-only F / G / K reads at F5V / G5V / K5V, a letter-only O / B / A / M gives no row"),
    "luminosity": ("region luminosity on IAU 2015's M_bol,☉ 4.74 with S1's BC (the BC path cannot tell interpolation "
                   "from nearest-row on the measured stars); a K / M dwarf with one 2MASS J / Ks takes the Mann 2015 "
                   "colour route (×1.014 zero-point offset; ±2 % against measured M-dwarf luminosities, mostly "
                   "in-sample); a 2MASS degrade is marked not_authoritative, never a substituted route"),
    "relations": ("masses: Eker et al. 2018 (S12, inverted; disc stars 0.008 ≤ Z ≤ 0.040, steps at 0.72 / 1.05 / 2.4 "
                  "/ 7 M☉), S1 outside it, Mann et al. 2019 M_Ks (S13, n = 5, no [Fe/H]) for K / M dwarfs — the "
                  "L route runs 6–12 % above S13 for the same M dwarf; an unresolved binary over-reads; R(M) is S1's "
                  "mean-sequence radius (out-of-sample 16th–84th 0.748–1.084), null outside 0.078–59 M☉; "
                  "--spectral-type reads S1's mass directly"),
    "lifetime": ("main-sequence lifetime: MIST v2.5 (non-rotating, [Fe/H] 0 = Z 0.016358; [Fe/H] and [α/Fe] not "
                 "modelled), end point by mass with the 10⁻² shortfall below 0.65 M☉ (≈ 5 % seam at 0.60–0.65), "
                 "each 0.10–0.60 M☉ track's last EEP, the 0.30–0.40 transition band and the 1.15 → 1.16 M☉ reversal; "
                 "no low-mass validation in MIST II (brighter than eclipsing M dwarfs); null outside 0.10–300 M☉"),
    "hbl": ("hydrogen-burning limit 0.075 M☉ inclusive (Chabrier et al. 2023 — below it nuclear equilibrium is never "
            "reached); band 0.067 (substellar iff hi < 0.067), margin X > 0.080 for an inference / relation / model / "
            "FLAME / archive mass; T, Y, an L later than L5 or log L < −4.3 (S23 empirical; S22's model −4.19) are "
            "substellar whatever the mass; the limit rises at low metallicity (S24: 0.083 M☉ at [M/H] −2.0)"),
    "youth": ("the youth cut and over-read factor are model-based (BHAC15; the ×1.05 margin from one dynamical pair, "
              "LP 349-25); the 0.309062 no-age cut is model output at an untested age; activity and rotation are not "
              "youth; Gaia FLAME's age is not a signal; SIMBAD's pre-MS codes are read from the primary type only; "
              "\"≤ X\" (0.01 deadband) bounds the field relation's old-star read, not BHAC15's true mass, and is exact "
              "for true masses ≲ 0.6 M☉ (≲ 0.5 on the type route)"),
}


def cr30_disclosures(*topics):
    """The static ``cr30_disclosures`` block — ``{topic: text}`` for the named topics (CR-30 §7)."""
    return {t: CR30_DISCLOSURES[t] for t in topics}
