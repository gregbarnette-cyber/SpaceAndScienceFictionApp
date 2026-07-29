# core/shared.py — Shared constants and helper functions used across core modules.

import csv
import math
import os
import random
import re
import socket
import time
from contextlib import contextmanager

from core.equations import _kopparapu_seff  # single Kopparapu Seff source (P4.6)

# ─── Physical Constants ───────────────────────────────────────────────────────

G_MS2        = 9.80665                # 1 g in m/s²
C_MS         = 299_792_458.0          # speed of light in m/s
V_CAP_MS     = 0.03 * C_MS           # 3% of c in m/s
M_PER_AU     = 149_597_870_700.0      # metres per AU
M_PER_LM     = C_MS * 60.0           # metres per light-minute
HOURS_PER_YEAR  = 365.25 * 24        # 8765.82  (Julian year)
HOURS_PER_MONTH = HOURS_PER_YEAR / 12
LY_PER_PC       = 3.26156            # light years per parsec

# ─── Spectral Class Helpers ───────────────────────────────────────────────────

# Negative lookbehind prevents matching the OBAFGKM letter when preceded by
# another uppercase letter (e.g. the 'A' in 'DA1.9' white-dwarf types).
_SP_PATTERN = re.compile(r"(?<![A-Z])([OBAFGKM])(\d+(?:\.\d+)?)")

_LETTER_SEQUENCE = ["O", "B", "A", "F", "G", "K", "M"]

# ─── CSV Designation Helpers ──────────────────────────────────────────────────

_CSV_PREFIX_MAP = [
    ("NAME ",       "NAME"),
    ("GJ ",         "GJ"),
    ("HD ",         "HD"),
    ("HIP ",        "HIP"),
    ("HR ",         "HR"),
    ("Wolf ",       "Wolf"),
    ("LHS ",        "LHS"),
    ("BD+",         "BD"),
    ("BD-",         "BD"),
    ("BD ",         "BD"),
    ("K2 ",         "K2"),
    ("Kepler-",     "Kepler"),
    ("Kepler ",     "Kepler"),
    ("KOI-",        "KOI"),
    ("KOI ",        "KOI"),
    ("TOI-",        "TOI"),
    ("TOI ",        "TOI"),
    ("CoRoT-",      "CoRoT"),
    ("CoRoT ",      "CoRoT"),
    ("COCONUTS-",   "COCONUTS"),
    ("HAT-P-",      "HAT_P"),
    ("WASP-",       "WASP"),
    ("TIC ",        "TIC"),
    # SIMBAD now emits "Gaia DR3 <id>" (not "Gaia EDR3"); DR3 ≡ EDR3 source_ids.
    # DR1/DR2 differ and are intentionally not captured.
    ("Gaia EDR3 ",  "Gaia EDR3"),
    ("Gaia DR3 ",   "Gaia EDR3"),
    ("2MASS J",     "2MASS"),
    ("2MASS ",      "2MASS"),
]

# Phase AN2: "Bayer" and "Flamsteed" are the only two keys here NOT produced by
# _CSV_PREFIX_MAP — they come from _classify_star_id's `* ` pre-pass (AN1). They sit
# directly after NAME because that is the human-name end of the list; MAIN_ID is not
# in this list at all, and the rendered desig_str leads with it separately (AN0c).
#
# Insertion POSITION is wire-visible: query.py serialises this dict verbatim, so the
# sibling repo sees the JSON object re-ordered, not merely extended (AN2b). Documented
# in docs/integration.md.
#
# "Variable" (V*) is classified but deliberately NOT a key — D2. Adding it here is the
# whole change required; see _classify_star_id.
_CSV_DESIG_KEYS = [
    "NAME", "Bayer", "Flamsteed", "GJ", "HD", "HIP", "HR", "Wolf", "LHS", "BD",
    "K2", "Kepler", "KOI", "TOI", "CoRoT", "COCONUTS", "HAT_P", "WASP",
    "TIC", "Gaia EDR3", "2MASS",
]

# The narrow key set used by the cheap SIMBAD lookup behind opts 17/19/20/21 and
# the seven route planners (core.calculators.compute_lookup_star_for_distance).
#
# Phase AN0b [R4]: this order is LOAD-BEARING and is NOT a filtered view of
# _CSV_PREFIX_MAP. That map runs NAME, GJ, HD, … — filtering it to build this list
# would move GJ from 4th to 2nd and silently reorder desig_str on ten surfaces.
# Always pass an explicit ordered key list to the narrow call sites; never derive
# the order from the prefix map. Pinned by
# tests/test_designation_harness.py::NarrowCopyOrderTest.
_NARROW_DESIG_KEYS = ("NAME", "HD", "HR", "GJ", "Wolf")


def _designation_ids_from_rows(ids_result):
    """Pull the raw id strings out of a SIMBAD ``query_objectids()`` result.

    Accepts ``None`` (SIMBAD returned nothing) and yields an empty sequence, which
    is what every call site wants — an id-less star still gets a full key dict.
    """
    if ids_result is None:
        return []
    return [row["id"] for row in ids_result]


# ─── Bayer / Flamsteed classification (Phase AN1) ─────────────────────────────
#
# SIMBAD returns Bayer and Flamsteed designations under an asterisk-space prefix,
# which _CSV_PREFIX_MAP cannot express: `* ` carries TWO designation systems, told
# apart by the shape of the first token rather than by the prefix. Hence a
# classifier rather than more map rows.
#
#   *  20 Crt        Flamsteed   (note the DOUBLE space before the number)
#   * alf CMi        Bayer
#   * alf CMi A      Bayer + component letter
#   * alf01 Cen      Bayer + superscript numeral (α¹)
#   V* eps Eri       variable-star designation  — classified, but not a key (D2)
#   ** LDS 6248A     DOUBLE-star system id      — NOT a name for this star (D2)

# A trailing single capital letter is a component marker ("* alf CMi A"). Anchored
# to the end and requiring the preceding space, so it cannot fire on a
# constellation abbreviation ("* alf01 Cen" ends in "Cen", not a component).
_COMPONENT_SUFFIX_RE = re.compile(r"\s[A-Z]$")


def _classify_star_id(id_str):
    """Classify a SIMBAD `* `-family id → "Bayer" | "Flamsteed" | "Variable" | None.

    The `** ` branch is a real guard, but NOT for the reason PHASE_AN_PLAN.md §4
    step 1 gives. The plan says "** LDS 6248A" also satisfies ``startswith("* ")``
    and calls the ordering load-bearing; it does not and it is not — two asterisks
    then a space never matches asterisk-then-space, so the `* ` branch could not
    claim a `**` id even if it ran first (see plan [A4]). What the branch actually
    guards is the two other obvious ways to write this: ``startswith("*")``, or
    stripping asterisks first, either of which reads "** SHB    1A" as a Bayer id.
    Pinned by tests/test_designation_ids.py::ClassifierTest.

    "Variable" is returned but is deliberately NOT a designation key (D2) — `V*` is
    redundant with the Bayer form on essentially every star that has both. It is
    classified anyway so that promoting it to a key later is genuinely a one-line
    change: `_match_designations` **collects** `V* ` ids into the same candidate
    bucket as Bayer/Flamsteed and offers them to the same guard, so adding
    "Variable" to a key list is sufficient on its own.

    That last property was NOT true when AN1 first landed — the bucket held only
    Bayer and Flamsteed, so a `V* ` id fell through to the prefix loop, matched
    nothing, and was stored nowhere; adding "Variable" to a key set would have
    produced a key that was silently always None, with no error and no failing test.
    Caught by `/code-review` (2026-07-29) reading this docstring against the code.
    Pinned by test_promoting_variable_to_a_key_needs_no_other_change.
    """
    s = str(id_str).strip()
    if s.startswith("** "):          # must precede the `* ` test
        return None
    if s.startswith("V* "):
        return "Variable"
    if s.startswith("* "):
        tokens = s[2:].split()
        if not tokens:
            return None
        # Flamsteed numbers are bare integers; Bayer letters never are.
        return "Flamsteed" if tokens[0].isdigit() else "Bayer"
    return None


def _star_id_constellation(id_str):
    """The constellation abbreviation from a `* ` id ("*  24 PsA" → "PsA"), or None."""
    tokens = str(id_str).strip()[2:].split()
    return tokens[1] if len(tokens) >= 2 else None


def _preferred_star_id(candidates, kind, bayer_choice=None):
    """Apply the D8 precedence rule to same-kind `* ` candidates for one star.

    ``candidates`` is in SIMBAD's own id order, which is NOT a stable contract
    across releases — the whole point of D8 is to stop depending on it. Ties fall
    back to the first candidate.

    **That fallback is order-dependent for one shape, which is unmeasured — say so
    rather than invent a rule** (raised by `/code-review`, 2026-07-29). A tie means two
    candidates the clause cannot separate, and bare-vs-superscript Bayer forms
    (``* alf Cen`` alongside ``* alf01 Cen``, neither carrying a component letter) are
    exactly that: the choice would come from SIMBAD's ordering, the dependency D8 was
    written to remove. **No corpus star has this shape** — α Cen A lists
    ``* alf Cen A`` + ``* alf01 Cen``, so the component test does separate them, which
    is why the deliberate α¹ Cen decision (§4b) works. A secondary tie-break was
    considered and declined: the only obvious candidate, "prefer the non-superscript",
    would flip α Cen A's chosen designation the moment SIMBAD dropped the ``A`` form,
    and there is no evidence for which form should win. If a real example appears, that
    is the evidence to settle it with — and `test_ties_are_stable_on_the_first_candidate`
    is where the current behaviour is pinned.

    D8(i) Bayer — prefer the candidate with **no trailing component letter**. One
        clause covers all three measured cases: Procyon ("* alf CMi" over
        "* alf CMi A"), Sirius (same, though SIMBAD lists it in the OPPOSITE order —
        this is the case first-match-wins got wrong), and α Cen A, where the
        component-less candidate is the superscript form "* alf01 Cen". That last
        one was a deliberate maintainer decision, not a fallout: α Cen A's MAIN_ID is
        "* alf Cen A", so choosing that form would make D3 suppress it as a duplicate
        and the star would gain nothing from the phase. See PHASE_AN_PLAN.md §4b.

    D8(ii) Flamsteed — prefer the candidate whose constellation matches the chosen
        Bayer's. Fomalhaut carries "*  24 PsA" AND "*  79 Aqr"; its Bayer is
        "* alf PsA", so this selects 24 PsA and rejects 79 Aqr, Flamsteed's
        historical cross-boundary duplicate. With no Bayer to key off, first wins.
    """
    if not candidates:
        return None
    if kind == "Bayer":
        return min(candidates, key=lambda s: bool(_COMPONENT_SUFFIX_RE.search(s)))
    if kind == "Flamsteed" and bayer_choice:
        want = _star_id_constellation(bayer_choice)
        if want:
            return min(candidates, key=lambda s: _star_id_constellation(s) != want)
    return candidates[0]


def _match_designations(id_strings, keys):
    """Map SIMBAD id strings onto designation keys via ``_CSV_PREFIX_MAP``.

    Returns ``{key: first matching id string or None}`` in ``keys`` order — first
    match wins per key, and the id is stored with its prefix intact ("HD 102365",
    not 102365; ``databases._simbad_gould_block`` parses the integer back out of
    that string form, so the shape is a contract — see PHASE_AN_PLAN.md [A2]).

    Phase AN0: the single canonical matcher. Every in-scope copy of the loop
    (core.shared, databases.compute_simbad_lookup, calculators, main.py's opt-50
    builder) delegates here, so a new prefix entry lands everywhere at once.

    The ``key in desig`` guard is AN0a and is load-bearing: it lets one prefix map
    serve any key set, so a caller passing a narrow ``keys`` list simply skips the
    prefixes it doesn't want instead of raising ``KeyError``. Three of the copies
    this replaces had no such guard, which is why AN0 had to land completely before
    Phase AN1 adds a ``* `` entry.
    """
    desig = {k: None for k in keys}
    # "Variable" is collected but is not a shipped key (D2) — see _classify_star_id.
    star_ids = {"Bayer": [], "Flamsteed": [], "Variable": []}

    for raw in id_strings:
        id_str = str(raw).strip()
        # AN1: the `* ` family is owned by the classifier, not the prefix map —
        # collected here and resolved below, because D8's precedence needs to see
        # every candidate before choosing. No _CSV_PREFIX_MAP entry begins with `*`
        # or `V`, so this claims nothing the loop below would have matched; that
        # invariant is pinned by test_no_prefix_map_entry_shadows_the_star_family.
        kind = _classify_star_id(id_str)
        if kind in star_ids:
            star_ids[kind].append(id_str)
            continue
        for prefix, key in _CSV_PREFIX_MAP:
            if id_str.startswith(prefix) and key in desig and desig[key] is None:
                desig[key] = id_str
                break

    # AN1 second pass — D8 precedence. Bayer is resolved first because the
    # Flamsteed clause keys off the chosen Bayer's constellation.
    #
    # The `kind in desig` guard is re-spelled here ON PURPOSE. AN0a's protection is
    # one conjunct of the prefix loop's `if`, NOT a property of this function, so a
    # pre-pass that assigned blindly would raise KeyError: 'Bayer' on the narrow
    # key set (_NARROW_DESIG_KEYS, opts 17/19/20/21 + the seven route planners),
    # which per D7 deliberately does not carry these keys. Found by the AN0→AN1
    # sweep; see PHASE_AN_PLAN.md §4a.
    bayer = _preferred_star_id(star_ids["Bayer"], "Bayer")
    flamsteed = _preferred_star_id(star_ids["Flamsteed"], "Flamsteed", bayer)
    variable = _preferred_star_id(star_ids["Variable"], "Variable")
    for key, chosen in (("Bayer", bayer), ("Flamsteed", flamsteed), ("Variable", variable)):
        if chosen is not None and key in desig and desig[key] is None:
            desig[key] = chosen

    return desig


def _join_designations(designations, keys):
    """Render a designation dict as the comma-separated ``desig_str`` display form.

    Order comes from ``keys``, never from the dict or the prefix map (AN0b). Callers
    that want MAIN_ID to lead must say so by passing it first in ``keys`` — AN0c:
    ``compute_simbad_lookup`` does, and dropping it would strip the main id from all
    four GUI designation banners.

    AN2d / D3 — **a repeated VALUE is emitted once, first key wins.** For 16 of the 43
    corpus stars SIMBAD's ``main_id`` *is* the Bayer string, so once AN2 gives that
    string a key of its own the naive join renders
    ``* alf CMi, NAME Procyon, * alf CMi, …`` on all four GUI banners. Deduping here
    rather than in the dict is deliberate: the ``Bayer`` key still holds the value and
    still reaches ``query.py``'s consumers — it is only the rendered banner that is
    unchanged (PHASE_AN_PLAN.md §4b).

    Because MAIN_ID leads the only key list that contains it, "first wins" *is* "keep
    MAIN_ID, drop the keyed copy" — the D3 wording — without this function needing to
    know which key is special.

    **It is NOT limited to Bayer, and that is worth stating because the plan's D3
    framing implies it is.** The rule is "any repeated value", and MAIN_ID duplicates a
    keyed slot for plenty of stars with no `* ` id at all — a planet host whose main_id
    is its HD number previously rendered ``HD 209458, HD 209458, HIP 108859, …``. **13
    of the 43 corpus stars (30%) are deduped on this path alone**, none of them
    Bayer/Flamsteed cases: HD 209458, HR 8799, Kepler-186, TOI-700, WASP-12, CoRoT-7,
    HAT-P-11, Wolf 359, Barnard's star, GJ 35, Kapteyn's star, Luyten's star, HD 102365.
    That duplicate was a pre-existing display wart AN2 happens to fix; it is called out
    in docs/integration.md because a consumer splitting ``desig_str`` on ``", "`` sees a
    token disappear on stars the Bayer/Flamsteed notes say nothing about.

    Found by `/code-review` (2026-07-29), which measured the 30% and caught that both
    this docstring and the contract doc described the dedupe as a Bayer consequence.

    Pinned by tests/test_designation_an2.py::MainIdDedupeTest — on a ``* `` star, on a
    non-``* `` star (so the suppression cannot be implemented as "always drop Bayer"),
    and on a star with no ``* `` id whatsoever.
    """
    out, seen = [], set()
    for k in keys:
        val = designations.get(k)
        if not val:
            continue
        val = str(val)
        if val in seen:
            continue
        seen.add(val)
        out.append(val)
    return ", ".join(out)

# ─── Constellation Genitives (Phase AO §2) ────────────────────────────────────
#
# IAU 3-letter abbreviation → Latin genitive, all 88 modern constellations.
# The genitive is the form used in star designations: "66 G. Centauri",
# "18 Eridani", "alpha Canis Majoris" — never the nominative ("Centaurus").
#
# Owned by Phase AO (Gould designations), which needs it for the `display`
# field of its `gould` block. Phase AN3 CONSUMES it for Bayer/Flamsteed
# rendering and must not rebuild it — see PHASE_AO_PLAN.md §2 [R1].

_CONSTELLATION_GENITIVES = {
    "And": "Andromedae",        "Ant": "Antliae",           "Aps": "Apodis",
    "Aqr": "Aquarii",           "Aql": "Aquilae",           "Ara": "Arae",
    "Ari": "Arietis",           "Aur": "Aurigae",           "Boo": "Boötis",
    "Cae": "Caeli",             "Cam": "Camelopardalis",    "Cnc": "Cancri",
    "CVn": "Canum Venaticorum", "CMa": "Canis Majoris",     "CMi": "Canis Minoris",
    "Cap": "Capricorni",        "Car": "Carinae",           "Cas": "Cassiopeiae",
    "Cen": "Centauri",          "Cep": "Cephei",            "Cet": "Ceti",
    "Cha": "Chamaeleontis",     "Cir": "Circini",           "Col": "Columbae",
    "Com": "Comae Berenices",   "CrA": "Coronae Australis", "CrB": "Coronae Borealis",
    "Crv": "Corvi",             "Crt": "Crateris",          "Cru": "Crucis",
    "Cyg": "Cygni",             "Del": "Delphini",          "Dor": "Doradus",
    "Dra": "Draconis",          "Equ": "Equulei",           "Eri": "Eridani",
    "For": "Fornacis",          "Gem": "Geminorum",         "Gru": "Gruis",
    "Her": "Herculis",          "Hor": "Horologii",         "Hya": "Hydrae",
    "Hyi": "Hydri",             "Ind": "Indi",              "Lac": "Lacertae",
    "Leo": "Leonis",            "LMi": "Leonis Minoris",    "Lep": "Leporis",
    "Lib": "Librae",            "Lup": "Lupi",              "Lyn": "Lyncis",
    "Lyr": "Lyrae",             "Men": "Mensae",            "Mic": "Microscopii",
    "Mon": "Monocerotis",       "Mus": "Muscae",            "Nor": "Normae",
    "Oct": "Octantis",          "Oph": "Ophiuchi",          "Ori": "Orionis",
    "Pav": "Pavonis",           "Peg": "Pegasi",            "Per": "Persei",
    "Phe": "Phoenicis",         "Pic": "Pictoris",          "Psc": "Piscium",
    "PsA": "Piscis Austrini",   "Pup": "Puppis",            "Pyx": "Pyxidis",
    "Ret": "Reticuli",          "Sge": "Sagittae",          "Sgr": "Sagittarii",
    "Sco": "Scorpii",           "Scl": "Sculptoris",        "Sct": "Scuti",
    "Ser": "Serpentis",         "Sex": "Sextantis",         "Tau": "Tauri",
    "Tel": "Telescopii",        "Tri": "Trianguli",         "TrA": "Trianguli Australis",
    "Tuc": "Tucanae",           "UMa": "Ursae Majoris",     "UMi": "Ursae Minoris",
    "Vel": "Velorum",           "Vir": "Virginis",          "Vol": "Volantis",
    "Vul": "Vulpeculae",
}

# Case-insensitive index, built once. SIMBAD, VizieR and hand-typed input all
# vary the casing of the 3-letter code ("CMa" / "cma" / "CMA"), but the
# abbreviations are only unique case-insensitively, so a folded key is safe.
_CONSTELLATION_GENITIVES_CI = {
    k.lower(): v for k, v in _CONSTELLATION_GENITIVES.items()
}


def constellation_genitive(abbr):
    """IAU 3-letter constellation abbreviation → Latin genitive, or None.

    Case- and whitespace-insensitive. Returns None for a blank, unknown or
    non-string input — callers fall back to the raw abbreviation rather than
    inventing a name (Phase AO's `display` degrades to "66 G. Cen").
    """
    if not abbr:
        return None
    return _CONSTELLATION_GENITIVES_CI.get(str(abbr).strip().lower())

# ─── Module-level cache for main sequence data ────────────────────────────────

_MAIN_SEQUENCE_DATA = None


# ─── Helper Functions ─────────────────────────────────────────────────────────

def _format_travel_time(total_hours):
    """Break total_hours into years, months, days, hours, minutes, seconds.
    Only includes units that are >= 1 (or seconds if < 1 minute)."""
    HOURS_PER_DAY = 24.0
    HOURS_PER_MIN = 1 / 60.0

    remaining = total_hours

    years = int(remaining / HOURS_PER_YEAR)
    remaining -= years * HOURS_PER_YEAR

    months = int(remaining / HOURS_PER_MONTH)
    remaining -= months * HOURS_PER_MONTH

    days = int(remaining / HOURS_PER_DAY)
    remaining -= days * HOURS_PER_DAY

    hours = int(remaining)
    remaining -= hours

    minutes = int(remaining * 60)
    remaining -= minutes / 60

    seconds = remaining * 3600

    parts = []
    if years:
        parts.append(f"{years} Year{'s' if years != 1 else ''}")
    if months:
        parts.append(f"{months} Month{'s' if months != 1 else ''}")
    if days:
        parts.append(f"{days} Day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} Hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} Minute{'s' if minutes != 1 else ''}")
    if seconds >= 0.005 and (not parts or total_hours < HOURS_PER_MIN):
        parts.append(f"{seconds:.2f} Second{'s' if seconds != 1.0 else ''}")

    return ", ".join(parts) if parts else "0 Seconds"


def _to_cartesian(ra_deg: float, dec_deg: float, ly: float):
    """Convert spherical (RA/DEC + distance) to Cartesian light-year coordinates.
    One canonical copy (P4.6) shared by core.calculators and core.viz."""
    ra_r = math.radians(ra_deg)
    dec_r = math.radians(dec_deg)
    return (
        ly * math.cos(dec_r) * math.cos(ra_r),
        ly * math.cos(dec_r) * math.sin(ra_r),
        ly * math.sin(dec_r),
    )


def _fval(v):
    """Convert to float; return None if missing or NaN."""
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def _fmt(v, decimals=3, default="N/A"):
    """Format value to fixed-decimal string, or return default."""
    f = _fval(v)
    return f"{f:.{decimals}f}" if f is not None else default


def _safe_get(row, col_names, col):
    """Return a column value, or None if missing/masked/blank."""
    if col not in col_names:
        return None
    val = row[col]
    try:
        if hasattr(val, "mask") and val.mask:
            return None
    except Exception:
        pass
    s = str(val).strip()
    if s in ("", "--", "N/A", "nan", "None"):
        return None
    return val


def _parse_designations(result, ids_result):
    """Extract and organise star designations from SIMBAD results."""
    # AN2 (plan §4a "copy 8"): this was a hardcoded literal duplicating
    # ["MAIN_ID"] + _CSV_DESIG_KEYS. Adding a key to the shared list but not here left
    # the new keys at the END of insertion order (they arrived via the .update() below)
    # instead of at the literal's position — a silent ordering split between this
    # function and compute_simbad_lookup, which builds the same list from the shared
    # constant. Derived now, so the two cannot drift.
    keys_order = ["MAIN_ID"] + list(_CSV_DESIG_KEYS)
    designations = {k: None for k in keys_order}

    # MAIN_ID is set only when SIMBAD actually returned the column. AN0d: this is a
    # DELIBERATE divergence from compute_simbad_lookup, which falls back to the
    # user's query string — that difference is wire-visible through query.py and is
    # pinned by tests/test_designation_harness.py::MainIdDivergenceTest, not
    # inherited by accident.
    if result is not None and "main_id" in result.colnames:
        designations["MAIN_ID"] = str(result["main_id"][0])

    # AN0: the match loop lives in _match_designations now (one copy, guarded).
    designations.update(_match_designations(_designation_ids_from_rows(ids_result),
                                            _CSV_DESIG_KEYS))
    return designations


def _parse_designations_from_ids(ids_string, keys=None):
    """Parse a pipe-separated SIMBAD ids string into a comma-separated designation string.

    Returns a string of found designations (excluding MAIN_ID), or an empty string.

    P4.6: this is the single canonical parser. ``keys`` selects the caller's key set and
    defaults to ``_CSV_DESIG_KEYS`` — which leads with ``NAME`` (SIMBAD's common name,
    e.g. "NAME Chara"), so a named star reads as "NAME Chara, GJ 475, HD 109358, …".
    ``core.databases`` (the opt-50 builder) used to override this with a NAME-less key
    set; that drift is retired and it now uses the default. The ``key in desig`` guard
    means a custom ``keys`` list may omit keys the prefix map names (they're simply
    skipped), so one prefix map still serves any key set.
    """
    keys = _CSV_DESIG_KEYS if keys is None else keys
    if not ids_string:
        return ""
    # AN0: shares _match_designations/_join_designations with every other copy.
    return _join_designations(_match_designations(ids_string.split("|"), keys), keys)


def _parse_spectral_class(sp_str):
    """Extract primary class letter and numeric subtype from a SIMBAD spectral string.

    Returns (letter, subtype_float) or (None, None) if no OBAFGKM class found.
    Uses search so prefixes like 'sd' in 'sdG5' are skipped transparently.
    """
    if not sp_str or sp_str in ("N/A", "None", ""):
        return None, None
    m = _SP_PATTERN.search(sp_str)
    if not m:
        return None, None
    return m.group(1), float(m.group(2))


def _lookup_spectral_type(sp_str):
    """Return (row_dict, key_used_str) for the nearest ceiling entry in the CSV.

    Ceiling rule: smallest available subtype number >= requested subtype.
    Within-class fallthrough: if all entries are cooler than requested (e.g. F9
    with entries only up to F7), advance to the next cooler letter class and
    return its hottest (lowest subtype) entry (e.g. G0).
    Falls back to the last entry in the final available class if no next class exists.
    Returns (None, None) if class letter not found in data.
    """
    letter, subtype = _parse_spectral_class(sp_str)
    if letter is None:
        return None, None

    data = _load_main_sequence_data()

    try:
        start_idx = _LETTER_SEQUENCE.index(letter)
    except ValueError:
        return None, None

    for idx in range(start_idx, len(_LETTER_SEQUENCE)):
        current_letter = _LETTER_SEQUENCE[idx]
        entries = data.get(current_letter)
        if not entries:
            continue

        if idx == start_idx:
            for entry_subtype, row in entries:
                if entry_subtype >= subtype:
                    return row, row.get("Spectral Class", "").strip()
        else:
            row = entries[0][1]
            return row, row.get("Spectral Class", "").strip()

    entries = data.get(letter)
    if entries:
        row = entries[-1][1]
        return row, row.get("Spectral Class", "").strip()
    return None, None


def _load_main_sequence_data():
    """Load propertiesOfMainSequenceStars.csv into a per-class lookup structure."""
    global _MAIN_SEQUENCE_DATA
    if _MAIN_SEQUENCE_DATA is not None:
        return _MAIN_SEQUENCE_DATA

    filepath = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "propertiesOfMainSequenceStars.csv",
    )
    data = {}

    try:
        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sc = row.get("Spectral Class", "").strip()
                m = _SP_PATTERN.match(sc)
                if not m:
                    continue
                letter  = m.group(1)
                subtype = float(m.group(2))
                data.setdefault(letter, []).append((subtype, row))
        for letter in data:
            data[letter].sort(key=lambda t: t[0])
    except Exception as e:
        print(f"Warning: Could not load propertiesOfMainSequenceStars.csv: {e}")
        data = {}

    _MAIN_SEQUENCE_DATA = data
    return _MAIN_SEQUENCE_DATA


# _kopparapu_seff is imported from core.equations (P4.6 — one canonical copy).


# ─── Search Filter Helpers (Phase G) ─────────────────────────────────────────

# Spectral-class chips used by the search panels. "Other" matches anything whose
# leading type is not OBAFGKM (white dwarfs / degenerate D... types) plus NULLs.
_SPECTRAL_CHIP_LETTERS = ["O", "B", "A", "F", "G", "K", "M"]

# Prefixes that may sit in front of the real class letter, stripped when bucketing a
# type into a chip. Derived from a census of every distinct string preceding the first
# uppercase OBAFGKM letter in `star_systems` + `gcns_stars` (2026-07-27):
#   ''        plain type                              d      dwarf / lum. class V (4737)
#   sd (429)  subdwarf VI      esd (161) / usd (68)   extreme / ultra subdwarf
#   k (204) / h (8) / kn (1)   Am-Ap line-type notation: k = Ca II K-line type,
#                              h = hydrogen-line type, m = metallic-line type. NOT a
#                              luminosity prefix and NOT a binarity marker (SIMBAD
#                              otypes show these on singles and binaries alike; the
#                              binarity marker on such records is '+').
#   d/sd (22) / sd: (16) / s/sd (2) / (sd) (2)        uncertain-classification forms
# Uppercase 'D...' (DA/DC/DQ/DZ, ~13.4k rows) is the DEGENERATE white-dwarf prefix and
# is deliberately absent — those must stay in "Other".
#
# CRITICAL: this is why the SQL below uses GLOB, not LIKE. SQLite's LIKE is
# case-INSENSITIVE for ASCII, so `LIKE 'dM%'` cannot distinguish the dwarf prefix 'd'
# from the degenerate prefix 'D' and would drag white dwarfs into the letter chips.
# GLOB is case-SENSITIVE. Verified on this connection: core/db.py sets no
# `PRAGMA case_sensitive_like`, no custom collation, and no like()/glob() UDF.
# None of these strings contain a GLOB metacharacter (* ? [ ]), so they are safe to
# bind as parameters.
_SP_CLASS_PREFIXES = ("", "d", "sd", "esd", "usd", "k", "h", "kn",
                      "d/sd", "sd:", "s/sd", "(sd)")

# The wider letter set used for DISPLAY (dot colour + legend bucketing), as opposed to
# the search chips above. Adds the classes that are not main-sequence OBAFGKM but are
# still real, colourable classes: degenerate D (white dwarfs), brown dwarfs L/T/Y,
# Wolf-Rayet W, and the carbon/S-type sequence C/N/R/S.
#
# Why two sets rather than one: a search chip must send `DA` to "Other" (a white dwarf
# is not an O-B-A-F-G-K-M star), but a star chart must still PAINT it — using the chip
# set for colour would turn every white dwarf, brown dwarf and Wolf-Rayet grey.
#
# Widening is provably safe: it can only let an EARLIER prefix qualify, and in every
# containment pair the shorter member is the earlier one ('' < d < d/sd, sd < sd:,
# k < kn) while the joining characters are 'd s e u k h ( / : n' — never uppercase.
# So the display set can never override an answer the chip set already gave.
# Verified: 0 disagreements over all 3,827 distinct catalogue values.
# NOTE 'R' and 'S' are deliberately EXCLUDED. They are real historical classes (R and
# N are the older subdivisions of carbon class C; S is the ZrO class), but they have
# ZERO rows in star_systems / gcns_stars / hwc, and including them makes any
# non-spectral label that happens to start with those letters resolve to a class —
# "Red Giant" (a row label in the Honorverse hyper-limit table, which is fed through
# the same colour helper) became carbon class R. Zero benefit, real false positives.
# Add them back only alongside data that needs them.
_SP_DISPLAY_LETTERS = ("O", "B", "A", "F", "G", "K", "M",
                       "L", "T", "Y", "W", "D", "C", "N")


def spectral_leading_class(sp_str, letters=_SPECTRAL_CHIP_LETTERS):
    """Leading class letter of a spectral type, skipping a known luminosity prefix.

    `letters` selects the alphabet: the default `_SPECTRAL_CHIP_LETTERS` (OBAFGKM) is
    the search-chip rule; pass `_SP_DISPLAY_LETTERS` for colour/legend bucketing,
    which must also resolve D/L/T/Y/W and the carbon classes. The default is
    unchanged, so Part 1's search behaviour is byte-identical.

        spectral_leading_class("dM6")                          -> 'M'
        spectral_leading_class("DA")                           -> None   (chips)
        spectral_leading_class("DA", _SP_DISPLAY_LETTERS)      -> 'D'    (display)
        spectral_leading_class("dC:", _SP_DISPLAY_LETTERS)     -> 'C'    (carbon dwarf)


    The Python counterpart of the GLOB rule in `spectral_where` — one definition of
    "which chip does this type belong to". Note nothing enforces the equivalence at
    runtime — the two implementations are kept in step by
    `tests/test_search.py::test_sql_and_python_rules_agree`, which cross-checks them
    over a sample covering every prefix. Change one, run that test.

    Whitespace caveat: this strips the input, the GLOB fragment does not — so a type
    with a leading space resolves here but not in SQL. Latent only (0 of 3,827
    distinct real catalogue values have surrounding whitespace).

    'dM6' -> 'M'   'sdM3.0' -> 'M'   'kA5hF0mF2' -> 'A'   'M5.5Ve' -> 'M'
    'DA'  -> None  'DZ7.5'  -> None  'L0' -> None         '' / None -> None

    Note this deliberately takes the FIRST class letter, so an Am star's Ca-K type
    wins over its hydrogen-line type (`kA5hF0mF2` -> 'A', not 'F'). That matches
    `_SP_PATTERN`, which already drives BC/Teff/HZ/HR everywhere else in the app.
    Astronomically the h-type is the better temperature proxy for an Am star (Ca K
    reads too early, metals too late) and would move ~37 rows A->F; that was
    considered and declined, because adopting it here alone would make search
    disagree with the region/HR calculators. Changing it would mean changing
    `_SP_PATTERN` app-wide. See docs/star-databases.md (Phase G).

    Also slightly more permissive than `_SP_PATTERN`, which requires a digit after
    the letter: 'dMe' and 'sdK' resolve here but are (None, None) there.
    """
    s = (sp_str or "").strip()
    if not s:
        return None
    for prefix in _SP_CLASS_PREFIXES:
        if prefix and not s.startswith(prefix):
            continue
        rest = s[len(prefix):]
        if rest and rest[0] in letters:
            return rest[0]
    return None


# ── The one spectral-class colour palette (completed_plans/ROUTE_CHART_REFACTOR_PLAN.md Phase 3) ──
# Lives here, beside the `spectral_leading_class` rule it is keyed off, so the
# colour and the bucketing can never drift. `core.viz` re-exports it as
# `_SPECTRAL_COLORS`/`_sp_color` (its historical names, which the GUI imports) and
# `core.calculators._map_node` calls `sp_color` directly.
#
# Until 2026-07-27 the route maps had a SECOND palette
# (`core.calculators._star_map_color`) that disagreed on G/M/D and the unknown
# grey, so the same star was a different colour depending on which panel you
# opened — and, once the route charts gained the O16 per-class legend, the same
# "Class M" legend entry was painted two different colours. That palette is gone;
# these values (the physically-motivated set) won.
_SPECTRAL_COLORS = {
    "O": "#9BB0FF",
    "B": "#AABFFF",
    "A": "#CAD7FF",
    "F": "#F8F7FF",
    "G": "#FFF4EA",
    "K": "#FFD2A1",
    "M": "#FF8D3F",
    "L": "#FF4500",
    "T": "#CD853F",
    "W": "#E040FB",
    "D": "#B0C4DE",
    # Part 2 additions. Chosen for LEGIBILITY on the dark chart surface, not physical
    # realism: the physically-accurate deep reds fail 3:1 contrast against #0b1020.
    # C/N/R share one hue deliberately — R and N are the older subdivisions of the
    # same modern carbon class, and the validator shows four distinguishable warm
    # hues do not exist beside M/L/T. Identity comes from the legend label, not the
    # hue (see the palette note on sp_color).
    "Y": "#A9746E",
    "C": "#D94F2B",
    "N": "#D94F2B",
}

_SP_UNKNOWN_COLOR = "#AAAAAA"


def sp_color(sp_type: str) -> str:
    """Spectral type -> dot colour, skipping any luminosity prefix.

    Uses the DISPLAY letter set, so `dM6` (Wolf 359) paints as an M dwarf rather
    than — as the old `[:1].upper()` did — a white dwarf, while `DA`/`DZ7.5` still
    correctly resolve to D. Unknown/unparseable -> the neutral grey.

    PALETTE NOTE: `_SPECTRAL_COLORS` is *physically motivated* (it approximates true
    stellar colour), so it deliberately fails the generic categorical-palette checks
    — F `#F8F7FF` and G `#FFF4EA` sit at OKLab ΔE 2.7, because F and G stars really
    are both near-white. Identity is therefore carried by SECONDARY ENCODING — the
    per-class legend labels, the hover tooltip, and the click info box — never by
    hue alone. Do not "fix" this by re-stepping the hues onto passing values; that
    would make the colours lie about the physics."""
    return _SPECTRAL_COLORS.get(
        spectral_leading_class(sp_type, _SP_DISPLAY_LETTERS), _SP_UNKNOWN_COLOR)


def _escape_like(s: str) -> str:
    """Escape LIKE wildcards so user text matches literally (use with ESCAPE '\\')."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _adql_sanitize(s: str) -> str:
    """Keep only characters safe inside an ADQL string literal for a spectral refine."""
    return re.sub(r"[^A-Za-z0-9 .+\-/]", "", s or "").strip()


def spectral_where(column: str, classes, refine: str):
    """Build a parameterized SQL fragment for the spectral chips + refine control.

    classes: list of selected chip letters from {O,B,A,F,G,K,M,Other} (or empty/None).
    refine:  case-insensitive substring matched against the rest of the type.

    Returns (fragment, params). The fragment is '' when both inputs are empty; the
    caller ANDs it into its WHERE clause. Refine adds LIKE '%refine%' (ESCAPEd).

    A letter chip matches the leading class letter after skipping any prefix in
    `_SP_CLASS_PREFIXES`, using case-sensitive GLOB — so `dM6` (Wolf 359) and
    `sdM3.0` bucket under M, while the degenerate `DA`/`DZ7.5` white dwarfs do not.
    See the `_SP_CLASS_PREFIXES` comment for why LIKE cannot be used here.

    "Other" is the EXACT COMPLEMENT of the same expression (plus NULLs), so a star
    can never appear under both a letter chip and Other.
    """
    classes = classes or []
    letters = [c for c in classes if c in _SPECTRAL_CHIP_LETTERS]
    want_other = "Other" in classes

    clauses, params = [], []

    def _letter_terms(letter):
        """(sql, params) matching `letter` under every allowed prefix."""
        sql = " OR ".join(f"{column} GLOB ?" for _ in _SP_CLASS_PREFIXES)
        return f"({sql})", [f"{p}{letter}*" for p in _SP_CLASS_PREFIXES]

    sub = []
    for letter in letters:
        sql, ps = _letter_terms(letter)
        sub.append(sql)
        params.extend(ps)
    if want_other:
        # Complement over ALL chip letters, not just the selected ones.
        all_sql, all_params = [], []
        for letter in _SPECTRAL_CHIP_LETTERS:
            sql, ps = _letter_terms(letter)
            all_sql.append(sql)
            all_params.extend(ps)
        sub.append(f"({column} IS NULL OR NOT ({' OR '.join(all_sql)}))")
        params.extend(all_params)
    if sub:
        clauses.append("(" + " OR ".join(sub) + ")")

    refine = (refine or "").strip()
    if refine:
        clauses.append(f"{column} LIKE ? ESCAPE '\\'")
        params.append(f"%{_escape_like(refine)}%")

    if not clauses:
        return "", []
    return " AND ".join(clauses), params


def spectral_adql(column: str, classes, refine: str) -> str:
    """ADQL counterpart of spectral_where (inline literals; no parameters).

    Letter chips come from a fixed whitelist; the refine text is sanitized to a
    safe character set. Returns '' when empty; the caller ANDs the result.
    """
    classes = classes or []
    letters = [c for c in classes if c in _SPECTRAL_CHIP_LETTERS]
    want_other = "Other" in classes

    clauses = []
    sub = [f"{column} LIKE '{letter}%'" for letter in letters]
    if want_other:
        not_obafgkm = " OR ".join(f"{column} LIKE '{l}%'" for l in _SPECTRAL_CHIP_LETTERS)
        sub.append(f"({column} IS NULL OR NOT ({not_obafgkm}))")
    if sub:
        clauses.append("(" + " OR ".join(sub) + ")")

    refine = _adql_sanitize(refine)
    if refine:
        clauses.append(f"{column} LIKE '%{refine}%'")

    return " AND ".join(clauses)


# ─── Network Reliability Helpers ─────────────────────────────────────────────

def _retry_after_seconds(exc):
    """If *exc* is an HTTP error whose response carries a ``Retry-After`` header in the
    integer-seconds form, return ``min(seconds, 60.0)``; otherwise None (P6.1).

    Duck-typed on ``exc.response.headers`` so it works for ``requests.HTTPError`` without
    importing requests here. The HTTP-date form of Retry-After is not honored (falls back
    to exponential backoff)."""
    resp = getattr(exc, "response", None)
    if resp is None:
        return None
    try:
        header = resp.headers.get("Retry-After")
    except Exception:
        return None
    if not header:
        return None
    try:
        return min(float(header), 60.0)
    except (ValueError, TypeError):
        return None


def _with_retries(fn, *args, retries=3, base_delay=2.0, **kwargs):
    """Call fn(*args, **kwargs) up to `retries` times with exponential backoff.

    P6.1: when the failure is an HTTP error whose response carries a ``Retry-After``
    header (integer seconds), honor it (capped at 60 s) for that attempt instead of the
    exponential backoff — so any NASA-TAP / SIMBAD-over-requests caller gets 429/503
    throttling respect for free (previously only ``_hypatia_data_fetch`` did)."""
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if attempt == retries - 1:
                raise
            delay = _retry_after_seconds(e)
            if delay is None:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(delay)


@contextmanager
def _timeout_ctx(seconds):
    """Temporarily set the default socket timeout (applies to all blocking socket ops)."""
    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(seconds)
    try:
        yield
    finally:
        socket.setdefaulttimeout(old)


def _make_simbad(*fields, timeout=30):
    """Return a Simbad instance with a short timeout and the requested votable fields."""
    from astroquery.simbad import Simbad
    s = Simbad()
    s.TIMEOUT = timeout
    for f in fields:
        s.add_votable_fields(f)
    return s


def _network_error_msg(e, service: str) -> str:
    """Return a user-friendly string for a network exception."""
    try:
        import requests
        if isinstance(e, requests.exceptions.Timeout):
            return f"{service} request timed out. Try again."
        if isinstance(e, requests.exceptions.ConnectionError):
            return f"Could not connect to {service}. Check your network connection."
    except ImportError:
        pass
    try:
        import urllib.error
        if isinstance(e, urllib.error.URLError):
            reason = str(getattr(e, "reason", e)).lower()
            if "timed out" in reason or "timeout" in reason:
                return f"{service} request timed out. Try again."
            return f"Could not connect to {service}. Check your network connection."
    except ImportError:
        pass
    msg = str(e).lower()
    if "timed out" in msg or "timeout" in msg:
        return f"{service} request timed out. Try again."
    if "connection" in msg or "unreachable" in msg or "network" in msg:
        return f"Could not connect to {service}. Check your network connection."
    return str(e)


def _route_error(message: str, route_tried=None) -> dict:
    """Standard error dict for the Phase AM catalog-access tier (spec §5).

    Extends the app-wide ``{"error": str}`` contract with an optional ``route_tried``
    list so a blocked lookup is reported *with the alternatives enumerated*
    (failed-tool ≠ absent-capability). ``route_tried`` is omitted when empty, so callers
    that don't track routes stay byte-identical to the plain ``{"error": …}`` shape."""
    err = {"error": message}
    if route_tried:
        err["route_tried"] = list(route_tried)
    return err
