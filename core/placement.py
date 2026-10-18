"""CR-30.6 — the hydrogen-burning limit and object placement (pure; no network, no Qt, no DB).

**The limit** (A, ruling 77): 0.075 M☉ **inclusive** — Chabrier et al. 2023's model minimum mass to sustain hydrogen
fusion at solar composition; one constant for every site (``HBL_MSUN``; ``binary`` reads it).

**One placement rule** (B, rulings 78, 128, 144): a mass reading is an interval ``[lo, hi]``, a point X and a basis.
The tool's own inference (the M_Ks, luminosity or type route) is the zero-width row; a supplied mass is a zero-width
row placed by the band alone; a Gaia FLAME / archive mass is a zero-width row with the margin. Every row is placed by
its interval against the band — **stellar needs lo ≥ 0.075; substellar iff hi < 0.067** — and, for a margin-taking
row, by its point against the margin, **X > 0.080**. Under the youth rule (D) the cut replaces the margin and is
tested on lo (stellar iff lo > cut). Boundary otherwise. A flag never moves a row toward stellar (the cut ≥ 0.080).
**The override** (ruling 78 (iii)): a leading T / Y, an L later than L5, or log L < −4.3 → substellar whatever the
mass; a stellar mass carried with any of the three raises a conflict flag (pre-fire ruling 19 R-11).

**The youth rule** (D) and **pre-main-sequence** (E — E governs D wherever a pre-MS signal is present) — see
``place``. The over-read factor is read from the vendored BHAC15 table (``core.ms_reference_tables.factor_rows``)
by the contract's node rules and Greg's Q18 ruling (MSG 361).
"""

import math

from core import ms_reference_tables as mrt

HBL_MSUN = 0.075                 # inclusive — 0.075 itself is stellar (S22 L191–192)
BAND_LO_MSUN = 0.067             # substellar iff hi < 0.067 (S23's own M☉ figure)
MARGIN_MSUN = 0.080              # an inferred / relation / model / FLAME / archive point must exceed it
PRE_MS_SPLIT_MSUN = 0.625504     # 1.05 × 0.595718 (the band top's 0.5 Myr read; pre-fire ruling 19 R-9)
OVERRIDE_LOG_L = -4.3            # S23's empirical; S22's model −4.19 disclosed
OVER_READ_HI, OVER_READ_LO = 1.01, 0.99   # the deadband (δ = 0.01, BHAC15's print step; ruling 159)
NO_AGE_T_LO = 0.01               # a flag with no sizing age is read at the 0.01 Gyr node (ruling 134 M10)
FACTOR_STOP_GYR = 0.8            # from t_lo 0.8 Gyr: no factor, cut 0.080 (rulings 109, 135 L7)

# The cut: 1.05 × B(t_lo), the six-decimal nodes (pre-fire ruling 9 (2)); held 0.625–0.8; 0.080 from 0.8.
CUT_NODES = ((0.01, 0.309062), (0.025, 0.211442), (0.05, 0.163074), (0.08, 0.138593), (0.1, 0.129025),
             (0.12, 0.122391), (0.2, 0.104600), (0.3, 0.095062), (0.4, 0.089767), (0.5, 0.086102),
             (0.625, 0.083420))
NO_AGE_CUT = CUT_NODES[0][1]     # 0.309062

# SIMBAD's pre-main-sequence object types (the live otypedef; there is no pMS* code — ruling 135 L2)
PRE_MS_OTYPES = frozenset({"Y*O", "Y*?", "TT*", "TT?", "Or*", "Ae*", "Ae?"})

MEASURED_BASES = frozenset({"dynamical", "interferometric", "asteroseismic"})
MARGIN_BASES = frozenset({"inference", "relation", "model", "model_age_inconsistent", "gaia_flame", "archive"})
YOUTH_RULE_BASES = frozenset({"inference", "relation", "archive"})   # a model-basis row never (ruling 114)
CATALOG_BASES = frozenset({"dynamical", "interferometric", "asteroseismic", "relation", "model",
                           "model_age_inconsistent"})
AGE_BASES = frozenset({"membership", "lithium", "gravity_class", "model_fit"})
AGE_GRADES = frozenset({"member", "candidate"})
INTERVAL_KINDS = frozenset({"source_range", "sigma_1", "wb_derivation"})

STATUS_TEXT = {"stellar": "stellar", "boundary": "boundary — star or brown dwarf uncertain",
               "substellar": "substellar", "undetermined_no_mass": "undetermined — no mass"}
TEXT_LE = "young — the field relation over-reads"
TEXT_FLAT = "young — no measurable over-read here (BHAC15)"
TEXT_UNDER = "young — the field relation under-reads here; no bound from the main-sequence relations"
TEXT_OLD = "young — the relation does not over-read from 0.8 Gyr (BHAC15); no bound"
TEXT_ABOVE = "young — above the over-read table's domain on this route; no bound"
TEXT_PRE_MS = "pre-MS — no bound from the main-sequence relations"


# ── the cut ───────────────────────────────────────────────────────────────────────────────────────────────────
def cut_at(t_lo):
    """The youth cut at a sizing age (Gyr): linear in age between the nodes, held 0.625–0.8, 0.080 from 0.8."""
    if t_lo is None:
        return NO_AGE_CUT
    if t_lo >= FACTOR_STOP_GYR:
        return MARGIN_MSUN
    if t_lo >= CUT_NODES[-1][0]:
        return CUT_NODES[-1][1]
    if t_lo <= CUT_NODES[0][0]:
        return CUT_NODES[0][1]
    for (a, ca), (b, cb) in zip(CUT_NODES, CUT_NODES[1:]):
        if a <= t_lo <= b:
            return ca + (t_lo - a) / (b - a) * (cb - ca)
    return MARGIN_MSUN                                       # unreachable


# ── the over-read factor (D; rulings 138, 145, 156–158; Greg's Q18) ─────────────────────────────────────────────
_NODE_ROWS = {}


def _node_rows(route, node):
    """The factor table's rows at one (route, age node), sorted by inferred read — grouped once per loaded table
    (CP6 #9: no 888-row scan per node read)."""
    table = mrt.factor_rows()
    hit = _NODE_ROWS.get("_table")
    if hit is not table:
        _NODE_ROWS.clear()
        _NODE_ROWS["_table"] = table
        for r in table:
            if r["inferred_read"] is not None:
                _NODE_ROWS.setdefault((r["route"], round(r["age_gyr"], 9)), []).append(r)
        for k, v in _NODE_ROWS.items():
            if k != "_table":
                v.sort(key=lambda r: r["inferred_read"])
    return list(_NODE_ROWS.get((route, round(node, 9)), []))


def _at_node(route, x, node):
    """One age node → ``{"state": "below" | "above" | "in", "factor", "reasons": [...]}``.

    The route's factor domain at a node is the span of the reads that carry a factor; X below its lowest →
    ``below``, above its highest → ``above``. The factor itself: linear in log X between the two rows bracketing X
    (by their inferred read); a bracketing row with no factor → null with that row's ``null_reason`` (ruling 157);
    X outside every read at the node → null, "outside the table at the <t> Gyr node"."""
    rows = _node_rows(route, node)
    with_f = [r for r in rows if r["factor"] is not None]
    out = {"node": node, "factor": None, "reasons": []}
    if not with_f:
        out["state"] = "below"
        out["reasons"] = sorted({r["null_reason"] for r in rows if r["null_reason"]}) or [
            f"outside the table at the {node:g} Gyr node"]
        return out
    lo_f, hi_f = with_f[0]["inferred_read"], with_f[-1]["inferred_read"]
    out["state"] = "below" if x < lo_f else ("above" if x > hi_f else "in")
    if not rows or x < rows[0]["inferred_read"] or x > rows[-1]["inferred_read"]:
        out["reasons"] = [f"outside the table at the {node:g} Gyr node"]
        return out
    for r in rows:
        if r["inferred_read"] == x:
            if r["factor"] is not None:
                out["factor"] = r["factor"]
            else:
                out["reasons"] = [r["null_reason"]]
            return out
    for a, b in zip(rows, rows[1:]):
        if a["inferred_read"] < x < b["inferred_read"]:
            if a["factor"] is None or b["factor"] is None:
                out["reasons"] = sorted({r["null_reason"] for r in (a, b) if r["factor"] is None})
                return out
            f = (math.log10(x) - math.log10(a["inferred_read"])) / (
                math.log10(b["inferred_read"]) - math.log10(a["inferred_read"]))
            out["factor"] = a["factor"] + f * (b["factor"] - a["factor"])
            return out
    out["reasons"] = [f"outside the table at the {node:g} Gyr node"]
    return out


def overread_factor(route, x, t_lo):
    """The over-read factor on a route at (X, t_lo) →
    ``{"factor", "null_reasons", "domain": "below" | "above" | "in" | "none", "reading_factor", "reading_node_gyr"}``.

    Linear in t_lo between the two bracketing age nodes (held at 0.625 to 0.8; none from 0.8). Greg's Q18 ruling:
    X is **below** the route's domain if below at either node read; **above** only if above at both; inside at one
    and above at the other → the in-domain node's factor sets the reading (``reading_factor``), the factor itself
    stays null with "outside the table at the <t> Gyr node", and the output names the node."""
    res = {"factor": None, "null_reasons": [], "domain": "none", "reading_factor": None, "reading_node_gyr": None}
    if t_lo is None or t_lo >= FACTOR_STOP_GYR:
        res["null_reasons"] = ["no factor from t_lo 0.8 Gyr (the relation does not over-read there)"]
        return res
    nodes = mrt.FACTOR_AGE_NODES
    t = min(max(t_lo, nodes[0]), nodes[-1])
    if t in nodes:
        pair = [t]
    else:
        a = max(n for n in nodes if n < t)
        b = min(n for n in nodes if n > t)
        pair = [a, b]
    reads = [_at_node(route, x, n) for n in pair]
    states = [r["state"] for r in reads]
    reasons = []
    for r in reads:
        for why in r["reasons"]:
            if why not in reasons:
                reasons.append(why)
    if "below" in states:
        res["domain"] = "below"
    elif all(s == "above" for s in states):
        res["domain"] = "above"
    else:
        res["domain"] = "in"
    if len(reads) == 1:
        res["factor"] = reads[0]["factor"]
        res["reading_factor"] = reads[0]["factor"]
        res["reading_node_gyr"] = pair[0]
    elif all(r["factor"] is not None for r in reads):
        f = (t - pair[0]) / (pair[1] - pair[0])
        res["factor"] = reads[0]["factor"] + f * (reads[1]["factor"] - reads[0]["factor"])
        res["reading_factor"] = res["factor"]
    elif res["domain"] == "in":
        ins = [(n, r) for n, r in zip(pair, reads) if r["state"] == "in" and r["factor"] is not None]
        others = [r for r in reads if r["state"] == "above"]
        if ins and others:                                # Q18: inside at one node, above at the other
            res["reading_factor"] = ins[0][1]["factor"]
            res["reading_node_gyr"] = ins[0][0]
    if res["factor"] is None:
        res["null_reasons"] = reasons
    return res


# ── the reading ───────────────────────────────────────────────────────────────────────────────────────────────
def _classify_factor(f):
    if f is None:
        return None
    if f >= OVER_READ_HI:
        return "le"
    if f > OVER_READ_LO:
        return "flat"
    return "under"


def reading_for(route, x, t_lo, placed_boundary):
    """The flagged reading of an inferred / relation / archive mass (D; rulings 106, 108, 159; pre-fire ruling 2
    (a1)–(a2)) → ``{"reading", "reading_text", "overread_route", "overread_factor", "overread_factor_null_reasons",
    "x_over_factor", "reading_node_gyr", "overread_factor_by_route"?}``."""
    out = {"reading": "x", "reading_text": None, "overread_route": route or "unknown", "overread_factor": None,
           "overread_factor_null_reasons": [], "x_over_factor": None, "reading_node_gyr": None}
    if t_lo is not None and t_lo >= FACTOR_STOP_GYR:
        out["reading_text"] = TEXT_OLD
        out["overread_factor_null_reasons"] = ["no factor from t_lo 0.8 Gyr"]
        return out
    if route in ("mks", "luminosity", "type"):
        fr = overread_factor(route, x, t_lo)
        out["overread_factor"] = fr["factor"]
        out["overread_factor_null_reasons"] = fr["null_reasons"]
        out["reading_node_gyr"] = fr["reading_node_gyr"]
        if fr["factor"]:
            out["x_over_factor"] = x / fr["factor"]
        cls = _classify_factor(fr["reading_factor"])
        if placed_boundary:
            out.update(reading="le_x", reading_text=f"≤ {x:.4g} ({TEXT_LE})")
        elif fr["domain"] == "below":
            out.update(reading="le_x", reading_text=f"≤ {x:.4g} ({TEXT_LE}; below the route's factor domain)")
        elif fr["domain"] == "above":
            out["reading_text"] = TEXT_ABOVE
        elif cls == "le":
            out.update(reading="le_x", reading_text=f"≤ {x:.4g} ({TEXT_LE})")
        elif cls == "flat":
            out["reading_text"] = TEXT_FLAT
        elif cls == "under":
            out["reading_text"] = TEXT_UNDER
        else:
            out["reading_text"] = "young — no over-read factor here (" + "; ".join(fr["null_reasons"]) + ")"
        return out
    # route unknown (a relation-basis catalog row, an archive mass) — every route at (X, t_lo)
    by = {r: overread_factor(r, x, t_lo) for r in ("mks", "luminosity", "type")}
    out["overread_factor_by_route"] = {r: v["factor"] for r, v in by.items()}
    have = [v["reading_factor"] for v in by.values() if v["reading_factor"] is not None]
    below_all = all(v["domain"] == "below" for v in by.values())
    above_all = all(v["domain"] == "above" for v in by.values())
    out["overread_factor_null_reasons"] = ["route unknown (a relation-basis catalog row / an archive mass) — no "
                                           "single-route factor"]
    if placed_boundary:
        out.update(reading="le_x", reading_text=f"≤ {x:.4g} ({TEXT_LE})")
    elif below_all:
        out.update(reading="le_x", reading_text=f"≤ {x:.4g} ({TEXT_LE}; below every route's factor domain)")
    elif above_all:
        out["reading_text"] = TEXT_ABOVE
    elif have and all(f >= OVER_READ_HI for f in have):
        out.update(reading="le_x", reading_text=f"≤ {x:.4g} ({TEXT_LE} on every route)")
    else:
        out["reading_text"] = "young — not every route over-reads here; no bound"
    return out


# ── placement ─────────────────────────────────────────────────────────────────────────────────────────────────
def mass_reading(x, basis, lo=None, hi=None, kind=None, route=None, basis_unknown=False):
    """A mass reading → the dict ``place`` takes (an inference / supplied / FLAME / archive mass is zero-width)."""
    lo = x if lo is None else lo
    hi = x if hi is None else hi
    return {"x": x, "lo": lo, "hi": hi, "basis": basis, "kind": kind, "route": route, "basis_unknown": basis_unknown}


def reading_from_catalog_row(row, x=None):
    """CR-30.6 C: a catalog row → its mass reading (a row without the new fields: relation, "basis unknown",
    ± σ, no age — ruling 144)."""
    x = row.get("mass_solar") if x is None else x
    basis = row.get("mass_basis")
    unknown = basis is None
    basis = basis or "relation"
    iv = row.get("mass_interval")
    if isinstance(iv, dict):
        lo, hi, kind = iv.get("lo"), iv.get("hi"), iv.get("kind")
    elif row.get("mass_uncertainty_solar") is not None:
        s = float(row["mass_uncertainty_solar"])          # finite ≥ 0 — checked at load (validate_cr30_fields)
        # a σ ≥ X would put lo at or below 0: a mass is positive, so the derived interval's lo floors at 0 (CP4 #1)
        lo, hi, kind = max(0.0, x - s), x + s, "sigma_1"
    else:
        lo = hi = x
        kind = None
    return mass_reading(x, basis, lo=lo, hi=hi, kind=kind, route=None, basis_unknown=unknown)


def is_l0_l5(parse):
    """CR-30.7 A (Q28): a leading L0–L5 (or a letter-only L) — placed by its mass; no inference route."""
    return parse is not None and parse.letter == "L" and (parse.subtype is None or parse.subtype <= 5)


def is_substellar_type(parse):
    """CR-30.6 (ruling 78 (iii)): a leading T / Y, or an L later than L5 — substellar by type."""
    return parse is not None and (parse.letter in ("T", "Y") or (parse.letter == "L" and parse.subtype is not None
                                                                 and parse.subtype > 5))


def _first_otype(otype):
    if not otype:
        return None
    return str(otype).split("|")[0].strip() or None


def place(reading, parse=None, log_l=None, call_age=None, catalog_age=None, otype=None, otype_source="simbad"):
    """CR-30.6 — place one mass reading. ``reading``: a ``mass_reading`` (or None — no mass). ``parse``: the
    star's ``shared.SpParse`` (the override and the gravity designation). ``log_l``: log₁₀ L (the override).
    ``call_age`` = ``{lo_gyr, hi_gyr, basis}`` (the new input); ``catalog_age`` = the row's ``age_interval``.
    ``otype``: SIMBAD's primary type, or a ``--component otype=`` list (its first code — Q21).

    → the name map's ``placement`` object (``status``, ``status_text``, ``reading``, ``reading_text``, ``x_msun``,
    ``basis``, ``interval``, the youth / pre-MS fields, the cut, the factor, the conflict flag, ``lifetime``)."""
    from core import ms_sequence
    p = parse
    out = {"status": None, "status_text": None, "reading": None, "reading_text": None, "x_msun": None,
           "basis": None, "basis_unknown": False, "interval": None, "x_equals_hi": False, "takes_margin": False,
           "youth_rule_applies": False, "youth_flag": False, "youth_trigger": [], "youth_caveat": None,
           "pre_ms": False, "pre_ms_signal": None, "cut_msun": MARGIN_MSUN, "cut_t_lo_gyr": None,
           "cut_age_source": "none", "no_sizing_age_reason": None, "overread_route": None, "overread_factor": None,
           "overread_factor_null_reasons": [], "x_over_factor": None, "reading_node_gyr": None,
           "conflict_flag": False, "conflict_trigger": None, "r_ex_direction": None, "derived_direction": None}

    # the override triggers (type / luminosity)
    trig = None
    if p is not None and p.letter in ("T", "Y"):
        trig = f"type:{p.read}"
    elif p is not None and p.letter == "L" and p.subtype is not None and p.subtype > 5:
        trig = f"type:{p.read}"
    elif log_l is not None and log_l < OVERRIDE_LOG_L:
        trig = f"logL<{OVERRIDE_LOG_L}"

    # youth signals (D)
    ages = []
    for src, a in (("call", call_age), ("catalog", catalog_age)):
        if not a:
            continue
        hi_g = a.get("hi_gyr")
        if hi_g is None or hi_g > 1.0:
            continue                                   # no upper bound, or above 1 Gyr: no youth signal (D3, 26)
        if src == "catalog" and a.get("grade") not in AGE_GRADES:
            continue
        ages.append((src, a))
    triggers = [f"{src}_age" for src, _ in ages]
    if p is not None and p.youth_from_gravity:
        triggers.append(f"gravity:{p.gravity}")
    out["youth_flag"] = bool(triggers)
    out["youth_trigger"] = triggers
    sizing = [(a["lo_gyr"], src) for src, a in ages if a.get("lo_gyr") is not None and a.get("basis") != "model_fit"]

    # pre-MS signals (E)
    ot1 = _first_otype(otype)
    if ot1 in PRE_MS_OTYPES:
        out["pre_ms"], out["pre_ms_signal"] = True, f"{otype_source}_otype:{ot1}"
    elif p is not None and p.pre_ms_from_gravity:
        out["pre_ms"], out["pre_ms_signal"] = True, "gravity:delta"
    else:
        for src, a in ages:
            if a.get("lo_gyr") is not None and a["lo_gyr"] < NO_AGE_T_LO and a.get("basis") != "model_fit":
                out["pre_ms"], out["pre_ms_signal"] = True, f"{src}_age"
                break

    if reading is None or reading.get("x") is None:
        if trig:
            out.update(status="substellar", status_text=STATUS_TEXT["substellar"], conflict_trigger=trig)
        else:
            out.update(status="undetermined_no_mass", status_text=STATUS_TEXT["undetermined_no_mass"])
        out["lifetime"] = lifetime_for_placement(out)
        return out

    x, lo, hi, basis = reading["x"], reading["lo"], reading["hi"], reading["basis"]
    out.update(x_msun=x, basis=basis, basis_unknown=bool(reading.get("basis_unknown")),
               interval=({"lo": lo, "hi": hi, "kind": reading.get("kind")} if (lo != hi or reading.get("kind"))
                         else None),
               x_equals_hi=(lo != hi and x == hi), takes_margin=basis in MARGIN_BASES,
               youth_rule_applies=basis in YOUTH_RULE_BASES)

    if sizing:
        t_lo, src = min(sizing)
        out.update(cut_t_lo_gyr=t_lo, cut_age_source=src)
    elif out["youth_flag"]:
        t_lo = None
        out["no_sizing_age_reason"] = ("no lower age bound — boundary assumes the youngest ages are possible"
                                       if any(a.get("lo_gyr") is None for _s, a in ages)
                                       else ("a model-fit-only age never sizes the cut" if ages
                                             else "a gravity designation sizes nothing"))
    else:
        t_lo = None

    youth_rule = out["youth_flag"] and out["youth_rule_applies"]
    pre_ms_rule = out["pre_ms"] and out["youth_rule_applies"]
    if youth_rule:                     # the cut is reported wherever the youth rule applies, even where E governs
        out["cut_msun"] = cut_at(t_lo) if t_lo is not None else NO_AGE_CUT

    # placement by the band + margin / cut
    if hi < BAND_LO_MSUN:
        status = "substellar"
    elif pre_ms_rule:
        status = "boundary" if x <= PRE_MS_SPLIT_MSUN else "stellar"
    elif youth_rule:
        cut = out["cut_msun"]
        status = "stellar" if (lo >= HBL_MSUN and lo > cut) else "boundary"
    else:
        margin_ok = (not out["takes_margin"]) or x > MARGIN_MSUN
        status = "stellar" if (lo >= HBL_MSUN and margin_ok) else "boundary"
    if trig:
        out["conflict_flag"] = status == "stellar"
        out["conflict_trigger"] = trig
        status = "substellar"
    out["status"] = status
    out["status_text"] = STATUS_TEXT[status]

    # the reading (E governs D)
    if pre_ms_rule and status != "substellar":
        if x <= PRE_MS_SPLIT_MSUN:
            out.update(reading="le_x", reading_text=f"≤ {x:.4g} (pre-MS — the field relation over-reads)")
        else:
            out.update(reading="x", reading_text=TEXT_PRE_MS, status_text="stellar, pre-main-sequence")
    elif youth_rule and status != "substellar":
        t_read = t_lo if t_lo is not None else NO_AGE_T_LO
        rd = reading_for(reading.get("route") if basis == "inference" else None, x, t_read,
                         placed_boundary=(status == "boundary" and t_read < FACTOR_STOP_GYR))
        out.update({k: v for k, v in rd.items()})
    elif lo != hi:
        out["reading"] = "interval"
    else:
        out["reading"] = "x"
    if out["youth_flag"] and out["youth_rule_applies"]:     # the caveat qualifies an inferred / relation mass only
        age_txt = (f"t_lo {t_lo:g} Gyr ({out['cut_age_source']})" if t_lo is not None
                   else (out["no_sizing_age_reason"] or "no sizing age"))
        out["youth_caveat"] = f"youth-flagged ({', '.join(triggers)}; {age_txt}) — a young object's inferred " \
                              "mass over-reads near the limit (BHAC15)"
    if out["reading"] == "le_x":
        out["r_ex_direction"] = "upper_bound"
        out["derived_direction"] = "upper_bound"
    out["lifetime"] = lifetime_for_placement(out, ms_sequence)
    return out


# ── the lifetime by status (CR-30.5 range rules) ────────────────────────────────────────────────────────────────
def lifetime_for_placement(pl, ms_sequence=None):
    """CR-30.5's per-placement lifetime → ``{ms_lifetime_yr, ms_lifetime_direction, ms_lifetime_status,
    ms_lifetime_note, ms_lifetime_end_point, ms_lifetime_if_stellar_ge_yr}``."""
    if ms_sequence is None:
        from core import ms_sequence
    out = {"ms_lifetime_yr": None, "ms_lifetime_direction": None, "ms_lifetime_status": None,
           "ms_lifetime_note": None, "ms_lifetime_end_point": None, "ms_lifetime_if_stellar_ge_yr": None}
    st, x = pl.get("status"), pl.get("x_msun")
    lo_track = ms_sequence.MIST_MIN_MSUN
    if st == "undetermined_no_mass" or x is None:
        out.update(ms_lifetime_status="mass_null", ms_lifetime_note="no mass — no main-sequence lifetime")
        return out
    if st == "substellar":
        out.update(ms_lifetime_status="substellar_null", ms_lifetime_note="substellar — no main-sequence lifetime")
        return out
    pre_ms_unbounded = pl.get("pre_ms") and pl.get("reading") != "le_x"
    if pre_ms_unbounded:
        out.update(ms_lifetime_status="pre_ms", ms_lifetime_note="pre-MS — not on the main sequence")
        return out
    if st == "boundary":
        iv = pl.get("interval") or {}
        m_hi = x if (pl.get("reading") == "le_x" or not iv) else iv.get("hi", x)
        m_hi = max(lo_track, m_hi)
        life = ms_sequence.ms_lifetime(m_hi)
        out.update(ms_lifetime_status="boundary_null", ms_lifetime_if_stellar_ge_yr=life["yr"],
                   ms_lifetime_end_point=life["end_point"],
                   ms_lifetime_note=(f"if stellar, ≥ t({m_hi:.4g} Msun) = {life['yr'] / 1e9:.1f} Gyr"
                                     if life["yr"] else "if stellar — no MIST lifetime at the upper mass")
                   + ("; MIST's 0.10 → 0.15 Msun step disclosed" if m_hi < 0.15 else ""))
        return out
    # stellar
    m = max(lo_track, x)
    life = ms_sequence.ms_lifetime(m)
    out.update(ms_lifetime_yr=life["yr"], ms_lifetime_end_point=life["end_point"])
    if pl.get("reading") == "le_x" or x < lo_track:
        out.update(ms_lifetime_direction="ge", ms_lifetime_status="lower_bound",
                   ms_lifetime_note=f"≥ t({m:.4g} Msun)" + (" — below MIST's lowest track (0.10 Msun)"
                                                              if x < lo_track else ""))
    else:
        out.update(ms_lifetime_status=("value" if life["yr"] is not None else life["status"]),
                   ms_lifetime_note=life["note"])
    return out


# ── the age input (ruling 141; F2; Q23) and the bridge from a resolved mass ───────────────────────────────────────
AGE_INPUT_ERROR_PREFIX = "age input: "


def age_input(lo_gyr, hi_gyr, basis):
    """CR-30.6 — the call's age (``--age-lo-gyr`` / ``--age-hi-gyr`` / ``--age-basis``, or a component's
    ``age_lo=`` / ``age_hi=`` / ``age_basis=``) → ``(age_or_None, error_or_None)``.

    Nothing given → ``(None, None)``. Giving an age requires ``hi`` and a basis; ``lo`` omitted = no lower bound.
    Each bound finite and ≥ 0; ``lo ≤ hi``. ``age`` = ``{"lo_gyr", "hi_gyr", "basis"}`` (echoed as ``age_input``)."""
    if lo_gyr is None and hi_gyr is None and basis is None:
        return None, None
    if hi_gyr is None:
        return None, AGE_INPUT_ERROR_PREFIX + "giving an age requires an upper bound (--age-hi-gyr / age_hi=)"
    if basis is None:
        return None, AGE_INPUT_ERROR_PREFIX + ("an age needs its basis (--age-basis / age_basis=): one of "
                                               + ", ".join(sorted(AGE_BASES)))
    if basis not in AGE_BASES:
        return None, AGE_INPUT_ERROR_PREFIX + f"basis {basis!r} is not one of " + ", ".join(sorted(AGE_BASES))
    vals = {}
    for nm, v in (("lo", lo_gyr), ("hi", hi_gyr)):
        if v is None:
            vals[nm] = None
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None, AGE_INPUT_ERROR_PREFIX + f"the {nm} bound {v!r} is not a number"
        if isinstance(v, bool) or not math.isfinite(f) or f < 0:
            return None, AGE_INPUT_ERROR_PREFIX + f"the {nm} bound must be a finite number >= 0 Gyr (got {v!r})"
        vals[nm] = f
    if vals["lo"] is not None and vals["lo"] > vals["hi"]:
        return None, AGE_INPUT_ERROR_PREFIX + f"lo {vals['lo']:g} Gyr > hi {vals['hi']:g} Gyr"
    return {"lo_gyr": vals["lo"], "hi_gyr": vals["hi"], "basis": basis}, None


# a resolved mass's provenance → the placement basis (C10: which rows take the margin / the youth rule)
_PROV_BASIS = {"manual": "supplied", "gaia_flame": "gaia_flame", "ms_mks_relation": "inference",
               "ms_luminosity_inversion": "inference", "spectral_type_table": "inference", "archive": "archive",
               # CR-14.2's orbit fallbacks (CP4 #2): M₁ is seeded from the type (the type route); an orbit M₂ / an
               # equal split rests on that M₁ — relation-like, basis unknown; an SB1 minimum is a lower bound
               "binary_orbit_m1": "inference", "binary_orbit_m2": "relation",
               "binary_orbit_equal_split_unresolved": "relation", "binary_orbit_sb1_min": "orbit_minimum"}
_PROV_ROUTE = {"ms_mks_relation": "mks", "ms_luminosity_inversion": "luminosity", "spectral_type_table": "type",
               "binary_orbit_m1": "type"}
TEXT_SB1_MIN = "an SB1 minimum mass (M₂ sin i) — the true mass is at least this"


def _place_minimum(out, x):
    """An SB1 minimum mass (CR-30.7 B, ruling 142): ≥ 0.075 proves stellar; below it the true mass is undetermined.
    The reading is ``ge_x``; the lifetime an upper bound ``≤ t(X)`` (a larger true mass lives shorter)."""
    from core import ms_sequence
    if x >= HBL_MSUN:
        out.update(status="stellar", status_text=STATUS_TEXT["stellar"])
    else:
        out.update(status="boundary", status_text="undetermined (minimum mass)")
    out.update(reading="ge_x", reading_text=f"≥ {x:.4g} ({TEXT_SB1_MIN})", r_ex_direction="lower_bound",
               derived_direction="lower_bound")
    life = ms_sequence.ms_lifetime(max(ms_sequence.MIST_MIN_MSUN, x))
    out["lifetime"] = {"ms_lifetime_yr": life["yr"], "ms_lifetime_direction": "le",
                       "ms_lifetime_status": "upper_bound", "ms_lifetime_note": f"≤ t({x:.4g} Msun) — a minimum mass",
                       "ms_lifetime_end_point": life["end_point"], "ms_lifetime_if_stellar_ge_yr": None}


LIFETIME_KEYS = ("ms_lifetime_end_point", "ms_lifetime_direction", "ms_lifetime_status", "ms_lifetime_note",
                 "ms_lifetime_if_stellar_ge_yr")
NOTE_WINDLESS_ALTERNATIVE = ("boundary — if the object is substellar it is a windless free harbor (no standoff, no "
                             "wall); the standoff shown is the stellar reading at X")


def apply_lifetime(target, pl, yr_key):
    """CR-30.5 / 30.6 (#26): write a placement's lifetime onto an output's lifetime site — ``yr_key`` (the site's
    own lifespan key) and the ``ms_lifetime_*`` keys. The one copy every carrier uses."""
    if not isinstance(target, dict) or not pl:
        return
    life = pl.get("lifetime") or {}
    target[yr_key] = life.get("ms_lifetime_yr")
    for k in LIFETIME_KEYS:
        target[k] = life.get(k)


def boundary_extras(pl, r_ex_au, alpha, windless_domain="windless_free_harbor"):
    """CR-30.6 / 30.7 A: a boundary placement's ``windless_alternative``; a boundary **catalog** row's
    ``r_ex_interval_au`` — the FROZEN standoff at the row's lo / hi (r_ex ∝ M^α, every other term held; a lo of 0
    gives 0). The one copy both exclusion subcommands use. Returns ``pl``."""
    if pl.get("status") != "boundary" or pl.get("basis") == "orbit_minimum":
        return pl
    pl["windless_alternative"] = {"domain": windless_domain, "note": NOTE_WINDLESS_ALTERNATIVE}
    iv, x = pl.get("interval"), pl.get("x_msun")
    if iv and pl.get("basis") in CATALOG_BASES and r_ex_au and x and alpha is not None:
        pl["r_ex_interval_au"] = [r_ex_au * (max(iv["lo"], 0.0) / x) ** alpha, r_ex_au * (iv["hi"] / x) ** alpha]
    return pl


def place_resolved(mass, provenance, catalog_row=None, sp_type=None, parse=None, lum_lsun=None, call_age=None,
                   otype=None, otype_source="simbad"):
    """CR-30.6 — place a mass the tier ladder resolved (``stellar_mass`` provenance) → the ``placement`` object.

    ``catalog`` → the matched row (its basis / interval / age — ruling 144); ``gaia_flame`` → zero-width with the
    margin; the M_Ks / luminosity / type routes → the tool's inference (zero-width, route named); ``manual`` →
    supplied (the band alone); ``archive`` → an archive mass (relation-like: basis unknown, margin + youth rule).
    ``lum_lsun`` feeds the log L < −4.3 override; ``parse`` (else ``sp_type`` parsed here) the type override and the
    gravity designation. A null mass → ``undetermined_no_mass`` (or substellar by the override)."""
    if parse is None and sp_type:
        from core import shared
        parse = shared.parse_spectral_type(sp_type)
    log_l = math.log10(lum_lsun) if (isinstance(lum_lsun, (int, float)) and not isinstance(lum_lsun, bool)
                                     and lum_lsun > 0 and math.isfinite(lum_lsun)) else None
    catalog_age = None
    if mass is None:
        reading = None
    elif provenance == "catalog" and isinstance(catalog_row, dict):
        reading = reading_from_catalog_row(catalog_row, x=mass)
        catalog_age = catalog_row.get("age_interval")
    else:
        # an unrecognised provenance is read as relation-basis, basis unknown — never as the tool's own inference
        basis = _PROV_BASIS.get(provenance, "relation")
        reading = mass_reading(mass, basis, route=_PROV_ROUTE.get(provenance),
                               basis_unknown=(basis in ("archive", "relation")))
    out = place(reading, parse=parse, log_l=log_l, call_age=call_age, catalog_age=catalog_age, otype=otype,
                otype_source=otype_source)
    if reading is not None and reading["basis"] == "orbit_minimum" and not out["conflict_trigger"]:
        # a minimum never places by the band's upper edge (hi is unbounded); only the override makes it substellar
        _place_minimum(out, mass)
    out["windless_alternative"] = None
    out["r_ex_interval_au"] = None
    if catalog_age:
        out["catalog_age"] = catalog_age
    return out
