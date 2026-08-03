# core/research_priors.py — Phase R3: the research-priors data contract.
#
# R3 fills the R1/R2 seam (core.priors.DefaultPriors + the research_policy param +
# grounding tagging) with a *second* priors provider fed by a versioned, external
# "formation-priors data contract" — a single JSON document the sister worldbuilding
# project (eventually) supplies and a GUI utility ingests, GCNS/Hypatia-style.
#
# This module owns the contract definition + its validator (R3-C1) and the importer
# + status reader (R3-C3, below). The ResearchPriors provider + get_priors selector
# live in core/priors.py (R3-C2). No engine is wired to any of this until R3-C4/C5.
#
# The contract mirrors the DefaultPriors attribute surface 1:1 (so the two providers
# are interchangeable in core/generate.py) and adds one new axis — origin_priors —
# for the calibrated Layer-3 formation narrative, plus version/provenance metadata.
# See docs/research-priors-contract.md and completed_plans/PHASE_R3_PLAN.md.

import datetime
import json
import os
from pathlib import Path

# The live cache the importer writes and ResearchPriors.load() reads (gitignored,
# like data/dust/). Committed artifacts (the sample + identity fixtures, the schema
# doc) live under tests/fixtures/ and docs/ — data/ is wholly gitignored.
_REPO_ROOT = Path(__file__).resolve().parent.parent
# Cache location: the SPACE_RESEARCH_PRIORS_DIR env var (mirroring SPACE_APP_DB)
# overrides the default, so subprocess tests / a consumer can relocate the cache.
_ENV_CACHE_DIR = os.environ.get("SPACE_RESEARCH_PRIORS_DIR")
_DEFAULT_CACHE_DIR = (Path(_ENV_CACHE_DIR) if _ENV_CACHE_DIR
                      else _REPO_ROOT / "data" / "research_priors")
_CACHE_PRIORS_NAME = "priors.json"
_CACHE_META_NAME = "meta.json"

# The committed scaffold dataset (data/ is wholly gitignored, so the canonical
# sample lives under tests/fixtures/). Used as the importer's default source so the
# hook is runnable before real sister-project priors exist; a consumer with a real
# contract passes their own path (GUI Browse / the importer's `path=` argument).
_SAMPLE_CONTRACT_PATH = _REPO_ROOT / "tests" / "fixtures" / "research_priors_sample.json"

# The sister worldbuilding repo ships the real v2 contract next door; auto-discover it so the
# GUI importer PREFILLS the live dataset instead of the committed scaffold — the cache is
# gitignored and silent about being stale, so a one-click re-ingest after a sister bump is the
# guard against running stale priors. The sibling directory name carries "Claude", whose case
# differs across checkouts (Windows vs case-sensitive Linux), so the lookup is case-tolerant.
# It is taken RELATIVE to _REPO_ROOT, so the shared parent's own case (claude/Claude) never
# enters into it. The core importer default stays the sample (test stability); only the GUI
# prefill consults this.
_SISTER_CONTRACT_REL = (Path("design-lab") / "star-system-generation-priors"
                        / "research_priors_v2.json")
_SISTER_DIR_CANONICAL = "scifiWorldBuilding-Claude"


def _discover_sister_contract():
    """Best-effort path to the sister repo's ``research_priors_v2.json`` beside this repo, or
    ``None``. Case-tolerant on the sibling directory name (some checkouts capitalise "Claude"
    differently); returns the file only when it actually exists."""
    parent = _REPO_ROOT.parent
    for name in (_SISTER_DIR_CANONICAL, _SISTER_DIR_CANONICAL.replace("Claude", "claude")):
        cand = parent / name / _SISTER_CONTRACT_REL
        if cand.is_file():
            return cand
    target = _SISTER_DIR_CANONICAL.lower()      # last resort: case-insensitive parent scan
    try:
        for child in parent.iterdir():
            if child.is_dir() and child.name.lower() == target:
                cand = child / _SISTER_CONTRACT_REL
                if cand.is_file():
                    return cand
    except OSError:
        pass
    return None


def default_priors_source():
    """The GUI importer's default source: the sister repo's live v2 contract when present
    beside this repo, else the committed scaffold sample. Always a ``Path``."""
    return _discover_sister_contract() or _SAMPLE_CONTRACT_PATH


# Contract vocabulary -------------------------------------------------------------
# "1.x" = the v1.0 marginals contract (R3). "2.x" = the additive v2 superset
# (Phase R3-V2): the same required axes plus the optional blocks in _V2_BLOCKS. A
# v2 dataset that omits every v2 block is behaviourally identical to a v1 dataset,
# so bumping the major alone never changes generation output.
_KNOWN_SCHEMA_MAJORS = {"1", "2"}
_REQUIRED_ZONES = ("hot", "hz", "cold", "far")
_PLAUSIBILITY = {"low", "medium", "high"}   # R2 Layer-3 enum (kept; D4)

# The sampling axes every provider must expose (the DefaultPriors surface). Each is
# validated by shape below; origin_priors is the one new, optional axis.
_REQUIRED_AXES = (
    "spectral_class_weights",
    "n_planet_dist",
    "spacing_ratio",
    "mass_by_zone",
    "moon_count",
    "moon_mass_frac",
)

# The Layer-3 origin context keys this contract version recognises. R3-C5 maps the
# inline core/feasibility.py heuristics onto these keys; a key a dataset omits falls
# back per-key to the DefaultPriors heuristic (never an error). Documented here as
# the single source of truth for the vocabulary.
#
# R3-V2 B4 — metallicity-qualified variants: a v2 origin_priors block may add a
# "<base_key>:metal_rich" or "<base_key>:metal_poor" entry; the feasibility engine
# prefers it over the base key when the host's [Fe/H] falls in that tail (else the
# base key). These are additive and validated like any origin_priors key; the base
# keys below remain the required vocabulary.
_ORIGIN_CONTEXT_KEYS = (
    "planet_at_location:in_situ_beyond_snow",
    "planet_at_location:in_situ_inner",
    "planet_at_location:resonant_migration",
    "planet_at_location:infeasible",
    "trojan:feasible",
    "trojan:infeasible",
    "moon:feasible",
    "moon:infeasible",
    "resonance:feasible",
    "resonance:infeasible",
)


# ── Phase R3-V2 · optional additive superset blocks ──────────────────────────
#
# v2 (schema_version "2.0") adds three optional blocks the sister project hands off
# (research-priors-v2-contract-request.md) plus one app-side axis (feh_dist). Each
# is validated *only when present*; a dataset omitting a block falls back to the v1
# field, so v1.0 datasets stay valid and permissive output stays byte-identical.
# Stage A (this checkpoint) validates + stores + exposes the blocks; NO engine reads
# them yet (Stage B — see completed_plans/PHASE_R3_V2_PLAN.md). The block names, in stored order:
_V2_BLOCK_NAMES = (
    "mass_model",                 # F1 — isolation-mass scaling (replaces mass_by_zone)
    "occurrence_by_metallicity",  # F2 — [Fe/H]-conditioned planet count / giant fraction
    "intra_system_correlation",   # F3 — peas-in-a-pod joint draws
    "feh_dist",                   # app-side: synthetic-mode host [Fe/H] source (Decision 2)
    "cold_giant_population",       # v2.2 — decoupled cold-giant SMA + multiplicity (B6/L2)
    "inner_giant_population",     # v2.3 — decoupled close-in giant population + channel tags
    "stellar_multiplicity",       # v2.4 — the first STELLAR axis: binaries + close pairs
    "stellar_activity",           # v2.4 — rotation/activity chain + circumbinary XUV geometry
    "age_dist",                   # v2.10 — app-side: synthetic-mode host AGE (T8; feh_dist's mirror)
)

_MASS_MODEL_TYPES = {"isolation-scaling"}   # recognised mass_model.type (additive)


def _err(msg):
    return {"error": f"research-priors contract: {msg}"}


def _is_num(x):
    """True for a real (non-bool) int/float."""
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _check_range_pair(value, key, *, require_positive_lo):
    """Validate a ``[lo, hi]`` pair → error string or None."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return f"{key} must be a [lo, hi] pair."
    lo, hi = value
    if not (_is_num(lo) and _is_num(hi)):
        return f"{key} bounds must be numbers."
    if require_positive_lo and lo <= 0:
        return f"{key} lower bound must be > 0."
    if lo < 0:
        return f"{key} lower bound must be >= 0."
    if lo > hi:
        return f"{key} requires lo <= hi (got {lo} > {hi})."
    return None


# ── v2 block validators (each returns an error string or None) ────────────────

def _check_mass_model(mm):
    """F1 — parametric isolation-mass model. Disk profile + feeding zone + switch."""
    if not isinstance(mm, dict):
        return "mass_model must be an object."
    t = mm.get("type")
    if not isinstance(t, str) or not t.strip():
        return "mass_model.type must be a non-empty string."
    if t not in _MASS_MODEL_TYPES:
        return (f"mass_model.type {t!r} is not recognised "
                f"(supported: {sorted(_MASS_MODEL_TYPES)}).")
    disk = mm.get("disk")
    if not isinstance(disk, dict):
        return "mass_model.disk must be an object."
    for field, positive in (("sigma0_gcm2", True), ("sigma_slope", False),
                            ("temp0_k", True), ("temp_slope", False),
                            ("disk_mass_mmsn", True)):
        v = disk.get(field)
        if not _is_num(v):
            return f"mass_model.disk.{field} must be a number."
        if positive and v <= 0:
            return f"mass_model.disk.{field} must be > 0."
    fz = mm.get("feeding_zone_hill")
    if not _is_num(fz) or fz <= 0:
        return "mass_model.feeding_zone_hill must be a positive number."
    gs = mm.get("giant_switch")
    if not isinstance(gs, str) or not gs.strip():
        return "mass_model.giant_switch must be a non-empty string."
    # R3-V2 v2.1: optional per-system disk-mass distribution (additive sibling of the
    # disk_mass_mmsn scalar, which stays the fallback). Validated only when present.
    dmd = disk.get("disk_mass_dist")
    if dmd is not None:
        return _check_disk_mass_dist(dmd)
    return None


_DISK_MASS_DISTS = {"lognormal"}   # recognised disk_mass_dist.dist (extensible enum)


def _check_disk_mass_dist(dmd):
    """v2.1 per-system disk-mass multiplier (MMSN units), log10-space — mirrors
    _check_feh_dist. mult = clamp(10^𝒩(log10_mean, log10_sigma), min, max)."""
    if not isinstance(dmd, dict):
        return "mass_model.disk.disk_mass_dist must be an object."
    dist = dmd.get("dist")
    if dist not in _DISK_MASS_DISTS:
        return (f"disk_mass_dist.dist must be one of {sorted(_DISK_MASS_DISTS)} "
                f"(got {dist!r}).")
    if not _is_num(dmd.get("log10_mean")):
        return "disk_mass_dist.log10_mean must be a number."
    if not _is_num(dmd.get("log10_sigma")) or dmd["log10_sigma"] <= 0:
        return "disk_mass_dist.log10_sigma must be a positive number."
    lo, hi = dmd.get("min"), dmd.get("max")
    if lo is not None and (not _is_num(lo) or lo <= 0):
        return "disk_mass_dist.min must be a positive number."
    if hi is not None and (not _is_num(hi) or hi <= 0):
        return "disk_mass_dist.max must be a positive number."
    if lo is not None and hi is not None and lo > hi:
        return "disk_mass_dist requires min <= max."
    return None


def _check_occurrence_by_metallicity(om):
    """F2 — giant fraction on an ascending [Fe/H] grid (+ super-Earth floor)."""
    if not isinstance(om, dict):
        return "occurrence_by_metallicity must be an object."
    grid = om.get("feh_grid")
    if not isinstance(grid, list) or len(grid) < 2:
        return "occurrence_by_metallicity.feh_grid must be a list of >= 2 numbers."
    if not all(_is_num(x) for x in grid):
        return "occurrence_by_metallicity.feh_grid entries must be numbers."
    if any(grid[i] >= grid[i + 1] for i in range(len(grid) - 1)):
        return "occurrence_by_metallicity.feh_grid must be strictly ascending."
    gf = om.get("giant_fraction")
    if not isinstance(gf, list) or len(gf) != len(grid):
        return ("occurrence_by_metallicity.giant_fraction must be a list the same "
                "length as feh_grid.")
    for x in gf:
        if not _is_num(x) or not (0.0 <= x <= 1.0):
            return "occurrence_by_metallicity.giant_fraction entries must be in [0, 1]."
    floor = om.get("superearth_floor_feh")
    if floor is not None and not _is_num(floor):
        return "occurrence_by_metallicity.superearth_floor_feh must be a number."
    shift = om.get("n_planet_dist_shift")
    if shift is not None and not isinstance(shift, str):
        return "occurrence_by_metallicity.n_planet_dist_shift must be a string."
    return None


def _check_intra_system_correlation(ic):
    """F3 — peas-in-a-pod size + period-ratio correlation kernel."""
    if not isinstance(ic, dict):
        return "intra_system_correlation must be an object."
    srd = ic.get("size_ratio_dist")
    if not isinstance(srd, dict):
        return "intra_system_correlation.size_ratio_dist must be an object."
    if not _is_num(srd.get("mean")) or srd["mean"] <= 0:
        return "intra_system_correlation.size_ratio_dist.mean must be a positive number."
    if not _is_num(srd.get("sigma")) or srd["sigma"] < 0:
        return ("intra_system_correlation.size_ratio_dist.sigma must be a "
                "non-negative number.")
    prd = ic.get("period_ratio_dist")
    if not isinstance(prd, dict):
        return "intra_system_correlation.period_ratio_dist must be an object."
    pmin, pmode, ptail = prd.get("min"), prd.get("mode"), prd.get("tail")
    if not all(_is_num(x) for x in (pmin, pmode, ptail)):
        return "intra_system_correlation.period_ratio_dist needs numeric min/mode/tail."
    if not (0 < pmin <= pmode <= ptail):
        return ("intra_system_correlation.period_ratio_dist requires "
                "0 < min <= mode <= tail.")
    for field in ("ordering", "note"):
        v = ic.get(field)
        if v is not None and not isinstance(v, str):
            return f"intra_system_correlation.{field} must be a string."
    return None


def _check_feh_dist(fd):
    """App-side axis — synthetic-mode host [Fe/H] draw (Gaussian mean/sigma, opt. clamp)."""
    if not isinstance(fd, dict):
        return "feh_dist must be an object."
    if not _is_num(fd.get("mean")):
        return "feh_dist.mean must be a number."
    if not _is_num(fd.get("sigma")) or fd["sigma"] <= 0:
        return "feh_dist.sigma must be a positive number."
    lo, hi = fd.get("min"), fd.get("max")
    if lo is not None and not _is_num(lo):
        return "feh_dist.min must be a number."
    if hi is not None and not _is_num(hi):
        return "feh_dist.max must be a number."
    if lo is not None and hi is not None and lo > hi:
        return "feh_dist requires min <= max."
    return None


def _check_cold_giant_population(cgp):
    """v2.2 — the decoupled cold-giant population (SMA power law + conditional
    multiplicity), placed independent of the inner n_planet_dist grid (B6/L2)."""
    if not isinstance(cgp, dict):
        return "cold_giant_population must be an object."
    sma = cgp.get("sma_dist")
    if not isinstance(sma, dict):
        return "cold_giant_population.sma_dist must be an object."
    if sma.get("dist") != "powerlaw":
        return "cold_giant_population.sma_dist.dist must be 'powerlaw'."
    inner = sma.get("inner")
    if inner != "snow_line" and not (_is_num(inner) and inner > 0):
        return ("cold_giant_population.sma_dist.inner must be 'snow_line' or a "
                "positive number.")
    if not _is_num(sma.get("outer_au")) or sma["outer_au"] <= 0:
        return "cold_giant_population.sma_dist.outer_au must be a positive number."
    if not _is_num(sma.get("slope_dn_dlna")):
        return "cold_giant_population.sma_dist.slope_dn_dlna must be a number."
    mult = cgp.get("multiplicity")
    if not isinstance(mult, dict) or not mult:
        return "cold_giant_population.multiplicity must be a non-empty object."
    saw_positive = False
    for k, v in mult.items():
        try:
            int(k)
        except (TypeError, ValueError):
            return f"cold_giant_population.multiplicity key {k!r} must be an integer count."
        if not _is_num(v) or v < 0:
            return f"cold_giant_population.multiplicity[{k!r}] must be a non-negative number."
        if v > 0:
            saw_positive = True
    if not saw_positive:
        return "cold_giant_population.multiplicity must have at least one positive weight."
    return None


_INNER_GIANT_OCCURRENCE_REF = "occurrence_by_metallicity.giant_fraction"
_INNER_GIANT_COMPONENT_DISTS = {"lognormal_au", "powerlaw"}


def _check_inner_giant_population(igp):
    """v2.3 — the decoupled close-in giant population (warm + hot Jupiters interior
    to the snow line), the mirror of ``cold_giant_population``.

    Shape only. The cross-block dependency (``occurrence_by_metallicity`` must be
    present, since ``occurrence_ref`` points into it) is a document-level invariant
    and is checked in ``validate_priors_contract``.
    """
    if not isinstance(igp, dict):
        return "inner_giant_population must be an object."

    # ── sma_dist: a weighted mixture over [inner_edge_au, snow_line] ──
    sma = igp.get("sma_dist")
    if not isinstance(sma, dict):
        return "inner_giant_population.sma_dist must be an object."
    if sma.get("dist") != "mixture":
        return "inner_giant_population.sma_dist.dist must be 'mixture'."
    edge = sma.get("inner_edge_au")
    if not _is_num(edge) or not (0 < edge < 1):
        return ("inner_giant_population.sma_dist.inner_edge_au must be a number "
                "in (0, 1) AU.")
    if sma.get("outer") != "snow_line":
        return "inner_giant_population.sma_dist.outer must be 'snow_line'."

    comps = sma.get("components")
    if not isinstance(comps, list) or not comps:
        return "inner_giant_population.sma_dist.components must be a non-empty list."
    weight_sum = 0.0
    for i, c in enumerate(comps):
        where = f"inner_giant_population.sma_dist.components[{i}]"
        if not isinstance(c, dict):
            return f"{where} must be an object."
        if not isinstance(c.get("name"), str) or not c["name"].strip():
            return f"{where}.name must be a non-empty string."
        cd = c.get("dist")
        if cd not in _INNER_GIANT_COMPONENT_DISTS:
            return (f"{where}.dist must be one of "
                    f"{sorted(_INNER_GIANT_COMPONENT_DISTS)} (got {cd!r}).")
        w = c.get("weight")
        if not _is_num(w) or w <= 0:
            return f"{where}.weight must be a positive number."
        weight_sum += w
        if cd == "lognormal_au":
            if not _is_num(c.get("center_au")) or c["center_au"] <= 0:
                return f"{where}.center_au must be a positive number."
            if not _is_num(c.get("log10_sigma")) or c["log10_sigma"] <= 0:
                return f"{where}.log10_sigma must be a positive number."
        else:  # powerlaw
            if not _is_num(c.get("inner_au")) or c["inner_au"] <= 0:
                return f"{where}.inner_au must be a positive number."
            outer = c.get("outer")
            if outer != "snow_line" and not (_is_num(outer) and outer > 0):
                return f"{where}.outer must be 'snow_line' or a positive number."
            if not _is_num(c.get("slope_dn_dlna")):
                return f"{where}.slope_dn_dlna must be a number."
    if abs(weight_sum - 1.0) > 1e-6:
        return ("inner_giant_population.sma_dist.components weights must sum to 1.0 "
                f"(got {weight_sum!r}).")

    # ── occurrence_ref: the hard pointer into occurrence_by_metallicity ──
    if igp.get("occurrence_ref") != _INNER_GIANT_OCCURRENCE_REF:
        return (f"inner_giant_population.occurrence_ref must be "
                f"{_INNER_GIANT_OCCURRENCE_REF!r}.")

    # ── mass_range_mjup: 0 < lo < hi <= 13 ──
    mr = igp.get("mass_range_mjup")
    if not isinstance(mr, (list, tuple)) or len(mr) != 2:
        return "inner_giant_population.mass_range_mjup must be a [lo, hi] pair."
    lo, hi = mr
    if not (_is_num(lo) and _is_num(hi)):
        return "inner_giant_population.mass_range_mjup bounds must be numbers."
    if not (0 < lo < hi <= 13):
        return ("inner_giant_population.mass_range_mjup requires "
                "0 < lo < hi <= 13 (M_Jup).")

    # ── eccentricity_dist: warm = beta, hot = rayleigh ──
    ed = igp.get("eccentricity_dist")
    if not isinstance(ed, dict):
        return "inner_giant_population.eccentricity_dist must be an object."
    warm = ed.get("warm")
    if not isinstance(warm, dict):
        return "inner_giant_population.eccentricity_dist.warm must be an object."
    if warm.get("dist") != "beta":
        return "inner_giant_population.eccentricity_dist.warm.dist must be 'beta'."
    for p in ("alpha", "beta"):
        if not _is_num(warm.get(p)) or warm[p] <= 0:
            return (f"inner_giant_population.eccentricity_dist.warm.{p} must be a "
                    "positive number.")
    hot = ed.get("hot")
    if not isinstance(hot, dict):
        return "inner_giant_population.eccentricity_dist.hot must be an object."
    if hot.get("dist") != "rayleigh":
        return "inner_giant_population.eccentricity_dist.hot.dist must be 'rayleigh'."
    sig = hot.get("sigma")
    if not _is_num(sig) or not (0 < sig < 1):
        return ("inner_giant_population.eccentricity_dist.hot.sigma must be a number "
                "in (0, 1).")

    # ── formation_channel_mix: each zone's fractions in [0,1], summing to 1 ──
    fcm = igp.get("formation_channel_mix")
    if not isinstance(fcm, dict) or not fcm:
        return "inner_giant_population.formation_channel_mix must be a non-empty object."
    saw_zone = False
    for zone, mix in fcm.items():
        # Zones are objects; any non-object sibling is metadata and is skipped —
        # the shipped dataset carries free-text note/notes here, and v2.5.0 added a
        # boolean is_prior_field flag beside them.
        if not isinstance(mix, dict):
            continue
        where = f"inner_giant_population.formation_channel_mix[{zone!r}]"
        if not mix:
            return f"{where} must be a non-empty object."
        saw_zone = True
        total = 0.0
        for channel, frac in mix.items():
            if not _is_num(frac) or not (0 <= frac <= 1):
                return f"{where}[{channel!r}] must be a number in [0, 1]."
            total += frac
        if abs(total - 1.0) > 1e-6:
            return f"{where} fractions must sum to 1.0 (got {total!r})."
    if not saw_zone:
        return ("inner_giant_population.formation_channel_mix must have at least one "
                "zone object.")
    return None


def _check_num_grid(obj, base, key_x, key_y, *, y_lo=None, y_hi=None, min_len=2):
    """Validate a pair of parallel numeric arrays (x ascending, y in range)."""
    xs, ys = obj.get(key_x), obj.get(key_y)
    for k, v in ((key_x, xs), (key_y, ys)):
        if not isinstance(v, list) or len(v) < min_len:
            return f"{base}.{k} must be a list of at least {min_len} numbers."
        if not all(_is_num(n) for n in v):
            return f"{base}.{k} entries must be numbers."
    if len(xs) != len(ys):
        return f"{base}.{key_x} and .{key_y} must be the same length."
    if any(b <= a for a, b in zip(xs, xs[1:])):
        return f"{base}.{key_x} must be strictly ascending."
    for n in ys:
        if y_lo is not None and n < y_lo:
            return f"{base}.{key_y} entries must be >= {y_lo}."
        if y_hi is not None and n > y_hi:
            return f"{base}.{key_y} entries must be <= {y_hi}."
    return None


def _check_bounds_pair(obj, base, key, *, positive=True, ordered=True):
    """Validate a [lo, hi] numeric pair. ``ordered=False`` allows either order
    (log_lx_lbol_valid_range is stated descending, -4 > log R_X > -6.3)."""
    v = obj.get(key)
    if not isinstance(v, (list, tuple)) or len(v) != 2 or not all(_is_num(n) for n in v):
        return f"{base}.{key} must be a [lo, hi] pair of numbers."
    lo, hi = v
    if positive and (lo <= 0 or hi <= 0):
        return f"{base}.{key} bounds must be positive."
    if ordered and lo >= hi:
        return f"{base}.{key} requires lo < hi (got {lo} >= {hi})."
    if not ordered and lo == hi:
        return f"{base}.{key} bounds must differ."
    return None


_SEPARATION_COMPONENT_DISTS = {"loguniform_period_days", "lognormal_au"}


def _check_stellar_multiplicity(sm):
    """v2.4+ — stellar multiplicity: the first STELLAR axis (all other blocks are
    planetary). Mass-ordered multiplicity fraction, mass ratios, and a two-component
    separation mixture whose close-pair branch sets ``p_orb_days`` for stellar_activity.
    """
    if not isinstance(sm, dict):
        return "stellar_multiplicity must be an object."

    mf = sm.get("multiplicity_fraction")
    if not isinstance(mf, dict):
        return "stellar_multiplicity.multiplicity_fraction must be an object."
    e = _check_num_grid(mf, "stellar_multiplicity.multiplicity_fraction",
                        "mass_msun_grid", "fraction", y_lo=0.0, y_hi=1.0)
    if e:
        return e
    if any(m <= 0 for m in mf["mass_msun_grid"]):
        return "stellar_multiplicity.multiplicity_fraction.mass_msun_grid entries must be > 0."
    sig = mf.get("sigma")
    if sig is not None:
        if not isinstance(sig, list) or len(sig) != len(mf["fraction"]):
            return ("stellar_multiplicity.multiplicity_fraction.sigma must be a list "
                    "the same length as fraction.")
        for s in sig:
            if s is not None and (not _is_num(s) or s < 0):
                return ("stellar_multiplicity.multiplicity_fraction.sigma entries must be "
                        "null or a non-negative number.")

    cf = sm.get("companion_frequency")
    if cf is not None:
        if not isinstance(cf, dict):
            return "stellar_multiplicity.companion_frequency must be an object."
        e = _check_num_grid(cf, "stellar_multiplicity.companion_frequency",
                            "mass_msun_grid", "frequency", y_lo=0.0)
        if e:
            return e

    hof = sm.get("higher_order_fraction")
    if hof is not None:
        if not isinstance(hof, dict):
            return "stellar_multiplicity.higher_order_fraction must be an object."
        v = hof.get("value")
        if not _is_num(v) or not (0 <= v <= 1):
            return "stellar_multiplicity.higher_order_fraction.value must be in [0, 1]."

    mr = sm.get("mass_ratio_dist")
    if not isinstance(mr, dict):
        return "stellar_multiplicity.mass_ratio_dist must be an object."
    if mr.get("dist") != "powerlaw_q":
        return "stellar_multiplicity.mass_ratio_dist.dist must be 'powerlaw_q'."
    if not _is_num(mr.get("slope")):
        return "stellar_multiplicity.mass_ratio_dist.slope must be a number."
    q_lo, q_hi = mr.get("q_min"), mr.get("q_max")
    if not (_is_num(q_lo) and _is_num(q_hi)) or not (0 < q_lo < q_hi <= 1):
        return "stellar_multiplicity.mass_ratio_dist requires 0 < q_min < q_max <= 1."
    twin_q = mr.get("twin_excess_above_q")
    if twin_q is not None and (not _is_num(twin_q) or not (0 < twin_q <= 1)):
        return "stellar_multiplicity.mass_ratio_dist.twin_excess_above_q must be in (0, 1]."
    twin_f = mr.get("twin_excess_factor")
    if twin_f is not None and (not _is_num(twin_f) or twin_f <= 0):
        return "stellar_multiplicity.mass_ratio_dist.twin_excess_factor must be > 0."

    sd = sm.get("separation_dist")
    if not isinstance(sd, dict):
        return "stellar_multiplicity.separation_dist must be an object."
    if sd.get("dist") != "mixture":
        return "stellar_multiplicity.separation_dist.dist must be 'mixture'."
    comps = sd.get("components")
    if not isinstance(comps, list) or not comps:
        return "stellar_multiplicity.separation_dist.components must be a non-empty list."
    wsum = 0.0
    for i, c in enumerate(comps):
        where = f"stellar_multiplicity.separation_dist.components[{i}]"
        if not isinstance(c, dict):
            return f"{where} must be an object."
        if not isinstance(c.get("name"), str) or not c["name"].strip():
            return f"{where}.name must be a non-empty string."
        cd = c.get("dist")
        if cd not in _SEPARATION_COMPONENT_DISTS:
            return (f"{where}.dist must be one of "
                    f"{sorted(_SEPARATION_COMPONENT_DISTS)} (got {cd!r}).")
        w = c.get("weight")
        if not _is_num(w) or w <= 0:
            return f"{where}.weight must be a positive number."
        wsum += w
        if cd == "loguniform_period_days":
            e = _check_bounds_pair({"p": [c.get("p_min_days"), c.get("p_max_days")]},
                                   where, "p")
            if e:
                return f"{where} requires 0 < p_min_days < p_max_days."
        else:
            e = _check_num_grid(c, where, "center_au_mass_grid", "center_au", y_lo=0.0)
            if e:
                return e
            if not _is_num(c.get("log10_sigma_au")) or c["log10_sigma_au"] <= 0:
                return f"{where}.log10_sigma_au must be a positive number."
            tr = c.get("truncate_period_days_min")
            if tr is not None and (not _is_num(tr) or tr <= 0):
                return f"{where}.truncate_period_days_min must be a positive number."
    if abs(wsum - 1.0) > 1e-6:
        return ("stellar_multiplicity.separation_dist.components weights must sum to 1.0 "
                f"(got {wsum!r}).")

    ecc = sm.get("ecc_dist")
    if ecc is not None:
        if not isinstance(ecc, dict):
            return "stellar_multiplicity.ecc_dist must be an object."
        # Structural guard (F-1): the whole point of this block is that a consumer
        # cannot quietly fall back to e = 0, which would make every drawn binary
        # maximally planet-friendly and inflate stable-HZ rates.
        if ecc.get("consumer_must_not_default_to_zero") is not True:
            return ("stellar_multiplicity.ecc_dist.consumer_must_not_default_to_zero "
                    "must be present and true (the F-1 guard).")
        cp = ecc.get("circularization_period_days")
        if cp is not None and (not _is_num(cp) or cp <= 0):
            return ("stellar_multiplicity.ecc_dist.circularization_period_days must be "
                    "a positive number.")
        if ecc.get("status") == "RESEARCH-GRADE" and cp is None:
            return ("stellar_multiplicity.ecc_dist: a RESEARCH-GRADE status requires "
                    "circularization_period_days.")
        pts = ecc.get("observed_points")
        if pts is not None:
            if not isinstance(pts, list):
                return "stellar_multiplicity.ecc_dist.observed_points must be a list."
            for i, pt in enumerate(pts):
                w2 = f"stellar_multiplicity.ecc_dist.observed_points[{i}]"
                if not isinstance(pt, dict):
                    return f"{w2} must be an object."
                if not _is_num(pt.get("p_orb_days")) or pt["p_orb_days"] <= 0:
                    return f"{w2}.p_orb_days must be a positive number."
                ev = pt.get("ecc")
                if not _is_num(ev) or not (0 <= ev < 1):
                    return f"{w2}.ecc must be in [0, 1)."

    cc = sm.get("consumer_contract")
    if cc is not None:
        if not isinstance(cc, dict):
            return "stellar_multiplicity.consumer_contract must be an object."
        emit = cc.get("emit")
        if not isinstance(emit, list) or not all(isinstance(x, str) for x in emit):
            return "stellar_multiplicity.consumer_contract.emit must be a list of strings."
    return None


def _check_stellar_activity(sa):
    """v2.4+ — the rotation/activity chain: P_rot → Ro = P_rot/τ → L_X/L_bol, plus the
    circumbinary XUV geometry. The three constants are a cross-fitted set (F-0) and the
    τ(mass) table was fitted assuming them, so they travel together."""
    if not isinstance(sa, dict):
        return "stellar_activity must be an object."

    ra = sa.get("rotation_activity")
    if not isinstance(ra, dict):
        return "stellar_activity.rotation_activity must be an object."
    sat = ra.get("saturation_log_lx_lbol")
    if not _is_num(sat) or sat >= 0:
        return ("stellar_activity.rotation_activity.saturation_log_lx_lbol must be a "
                "negative number (a log10 ratio).")
    ro_sat = ra.get("saturation_rossby")
    if not _is_num(ro_sat) or ro_sat <= 0:
        return ("stellar_activity.rotation_activity.saturation_rossby must be a "
                "positive number.")
    slope = ra.get("unsaturated_slope")
    if not _is_num(slope) or slope >= 0:
        return ("stellar_activity.rotation_activity.unsaturated_slope must be a "
                "negative number (activity falls with Rossby number).")
    ss = ra.get("unsaturated_slope_sigma")
    if ss is not None and (not _is_num(ss) or ss < 0):
        return ("stellar_activity.rotation_activity.unsaturated_slope_sigma must be "
                "non-negative.")
    if ra.get("ro_valid_range") is not None:
        e = _check_bounds_pair(ra, "stellar_activity.rotation_activity", "ro_valid_range")
        if e:
            return e
    if ra.get("log_lx_lbol_valid_range") is not None:
        e = _check_bounds_pair(ra, "stellar_activity.rotation_activity",
                               "log_lx_lbol_valid_range", positive=False, ordered=False)
        if e:
            return e
    rms = ra.get("relation_rms_dex")
    if rms is not None and (not _is_num(rms) or rms <= 0):
        return "stellar_activity.rotation_activity.relation_rms_dex must be > 0."

    ct = sa.get("convective_turnover")
    if not isinstance(ct, dict):
        return "stellar_activity.convective_turnover must be an object."
    if not isinstance(ct.get("relation"), str) or not ct["relation"].strip():
        return "stellar_activity.convective_turnover.relation must be a non-empty string."
    e = _check_bounds_pair(ct, "stellar_activity.convective_turnover", "valid_mass_msun")
    if e:
        return e
    if ct.get("mass_msun_grid") is not None or ct.get("tau_days") is not None:
        # The empirical grid is descending in mass, so check the τ side only.
        xs, ys = ct.get("mass_msun_grid"), ct.get("tau_days")
        for k, v in (("mass_msun_grid", xs), ("tau_days", ys)):
            if not isinstance(v, list) or len(v) < 2 or not all(_is_num(n) for n in v):
                return (f"stellar_activity.convective_turnover.{k} must be a list of "
                        "at least 2 numbers.")
            if any(n <= 0 for n in v):
                return f"stellar_activity.convective_turnover.{k} entries must be > 0."
        if len(xs) != len(ys):
            return ("stellar_activity.convective_turnover.mass_msun_grid and .tau_days "
                    "must be the same length.")
    rms = ct.get("rms_dex")
    if rms is not None and (not _is_num(rms) or rms <= 0):
        return "stellar_activity.convective_turnover.rms_dex must be > 0."

    for key in ("rotation_age_singles", "rotation_age_fgk"):
        blk = sa.get(key)
        if blk is None:
            continue
        if not isinstance(blk, dict):
            return f"stellar_activity.{key} must be an object."
        if blk.get("applicable_mass_msun") is not None:
            e = _check_bounds_pair(blk, f"stellar_activity.{key}", "applicable_mass_msun")
            if e:
                return e
    ras = sa.get("rotation_age_singles")
    if isinstance(ras, dict):
        if ras.get("dist") != "bimodal":
            return "stellar_activity.rotation_age_singles.dist must be 'bimodal'."
        for branch in ("fast", "slow"):
            b = ras.get(branch)
            if not isinstance(b, dict):
                return f"stellar_activity.rotation_age_singles.{branch} must be an object."
            e = _check_bounds_pair(b, f"stellar_activity.rotation_age_singles.{branch}",
                                   "p_rot_days")
            if e:
                return e
    rfg = sa.get("rotation_age_fgk")
    if isinstance(rfg, dict):
        for k in ("p_sun_days", "age_sun_gyr"):
            if not _is_num(rfg.get(k)) or rfg[k] <= 0:
                return f"stellar_activity.rotation_age_fgk.{k} must be a positive number."
        if not _is_num(rfg.get("exponent")):
            return "stellar_activity.rotation_age_fgk.exponent must be a number."

    cx = sa.get("circumbinary_xuv")
    if not isinstance(cx, dict):
        return "stellar_activity.circumbinary_xuv must be an object."
    # Structural guard (§9.4): the doubled emitters cancel against the doubled HZ
    # distance, so XUV at a circumbinary HZ must NOT scale with component count.
    if cx.get("component_count_scaling") != 1.0:
        return ("stellar_activity.circumbinary_xuv.component_count_scaling must be 1.0 "
                "(the §9.4 geometric result — XUV at a circumbinary HZ does not scale "
                "with the number of stars).")
    x2e = cx.get("xray_to_euv")
    if x2e is not None:
        if not isinstance(x2e, dict):
            return "stellar_activity.circumbinary_xuv.xray_to_euv must be an object."
        rels = x2e.get("relations")
        if not isinstance(rels, dict) or not rels:
            return ("stellar_activity.circumbinary_xuv.xray_to_euv.relations must be a "
                    "non-empty object.")
        default = x2e.get("default")
        if default not in rels:
            return (f"stellar_activity.circumbinary_xuv.xray_to_euv.default {default!r} "
                    f"must name one of {sorted(rels)}.")
        for name, rel in rels.items():
            if not isinstance(rel, dict):
                return (f"stellar_activity.circumbinary_xuv.xray_to_euv.relations"
                        f"[{name!r}] must be an object.")
            if not isinstance(rel.get("relation"), str) or not rel["relation"].strip():
                return (f"stellar_activity.circumbinary_xuv.xray_to_euv.relations"
                        f"[{name!r}].relation must be a non-empty string.")

    eld = sa.get("expected_locked_vs_single_delta")
    if eld is not None:
        if not isinstance(eld, dict):
            return "stellar_activity.expected_locked_vs_single_delta must be an object."
        # Structural guard (C-4): this is what the chain PRODUCES. Marking it an input
        # would double-count the delta against the Rossby computation.
        if eld.get("is_prior_field") is not False:
            return ("stellar_activity.expected_locked_vs_single_delta.is_prior_field "
                    "must be present and false (it is an acceptance target, not an input).")
        oom = eld.get("orders_of_magnitude")
        if oom is not None:
            e = _check_bounds_pair(eld, "stellar_activity.expected_locked_vs_single_delta",
                                   "orders_of_magnitude")
            if e:
                return e
    return None


def _check_age_dist(ad):
    """v2.10 (T8) — app-side axis: the synthetic-mode host stellar AGE, the mirror of
    ``feh_dist`` and the input ``stellar_activity``'s chain needs (age → P_rot → Ro →
    L_X/L_bol). Unlike ``feh_dist`` this is NOT a Gaussian: it is a population-weighted
    SFH **histogram**, mass-conditional and MS-lifetime-truncated.

    Two structural guards, each encoding something that would otherwise go silently wrong:

    * ``sfh_histogram`` bins must be contiguous, ordered and normalizable — a gap would
      silently drop probability mass rather than error.
    * a ``sfh_smoothing_note`` is REQUIRED whenever a zero-fraction bin sits between two
      non-zero ones. The BGM zeroes 7–8 Gyr and piles up 8–9 Gyr as a discrete-age-bin
      artifact; a consumer that samples the histogram literally reproduces a hole the real
      SFH does not have. Requiring the note means the artifact cannot arrive undocumented.
    """
    if not isinstance(ad, dict):
        return "age_dist must be an object."
    hist = ad.get("sfh_histogram")
    if not isinstance(hist, list) or not hist:
        return "age_dist.sfh_histogram must be a non-empty list of bins."
    prev_hi, total, interior_zero = None, 0.0, False
    for i, b in enumerate(hist):
        w = f"age_dist.sfh_histogram[{i}]"
        if not isinstance(b, dict):
            return f"{w} must be an object {{lo, hi, fraction}}."
        lo, hi, frac = b.get("lo"), b.get("hi"), b.get("fraction")
        if not _is_num(lo) or not _is_num(hi) or lo < 0 or hi <= lo:
            return f"{w} requires 0 <= lo < hi."
        if not _is_num(frac) or frac < 0:
            return f"{w}.fraction must be a non-negative number."
        if prev_hi is not None and abs(lo - prev_hi) > 1e-9:
            return (f"{w} is not contiguous with the previous bin "
                    f"(lo {lo} != previous hi {prev_hi}) — a gap silently drops mass.")
        prev_hi = hi
        total += frac
        if frac == 0 and 0 < i < len(hist) - 1:
            interior_zero = True
    if total <= 0:
        return "age_dist.sfh_histogram fractions must sum to a positive value."
    if interior_zero and not str(ad.get("sfh_smoothing_note") or "").strip():
        return ("age_dist.sfh_histogram has an interior zero-fraction bin but no "
                "sfh_smoothing_note — a discrete-age-bin artifact must not arrive "
                "undocumented (see the BGM 7-8 Gyr hole).")

    mca = ad.get("mass_conditional_age")
    if mca is not None:
        if not isinstance(mca, list) or not mca:
            return "age_dist.mass_conditional_age must be a non-empty list when present."
        for i, r in enumerate(mca):
            w = f"age_dist.mass_conditional_age[{i}]"
            if not isinstance(r, dict):
                return f"{w} must be an object."
            mlo, mhi = r.get("mass_lo"), r.get("mass_hi")
            if not _is_num(mlo) or not _is_num(mhi) or mlo < 0 or mhi <= mlo:
                return f"{w} requires 0 <= mass_lo < mass_hi."
            for k in ("mean_age_gyr", "median_age_gyr"):
                if r.get(k) is not None and (not _is_num(r[k]) or r[k] <= 0):
                    return f"{w}.{k} must be a positive number when present."

    for key in ("mean_age_gyr", "median_age_gyr"):
        if ad.get(key) is not None and (not _is_num(ad[key]) or ad[key] <= 0):
            return f"age_dist.{key} must be a positive number when present."

    for key in ("population_mix_recommended_local", "population_mix_bgm_nearplane"):
        mix = ad.get(key)
        if mix is None:
            continue
        if not isinstance(mix, dict) or not mix:
            return f"age_dist.{key} must be a non-empty object."
        for pop, frac in mix.items():
            if not _is_num(frac) or frac < 0:
                return f"age_dist.{key}.{pop} must be a non-negative number."
        if sum(mix.values()) <= 0:
            return f"age_dist.{key} weights must sum to a positive value."
    return None


# name → checker; iteration order is _V2_BLOCK_NAMES (stable).
_V2_BLOCK_CHECKERS = {
    "mass_model": _check_mass_model,
    "occurrence_by_metallicity": _check_occurrence_by_metallicity,
    "intra_system_correlation": _check_intra_system_correlation,
    "feh_dist": _check_feh_dist,
    "cold_giant_population": _check_cold_giant_population,
    "inner_giant_population": _check_inner_giant_population,
    "stellar_multiplicity": _check_stellar_multiplicity,
    "stellar_activity": _check_stellar_activity,
    "age_dist": _check_age_dist,
}


def present_v2_blocks(obj):
    """The v2 block names present (non-None) in a contract dict, in stored order."""
    return [name for name in _V2_BLOCK_NAMES if obj.get(name) is not None]


def validate_priors_contract(obj):
    """Validate a research-priors contract document (shape only, self-validating).

    Returns ``None`` when ``obj`` is a well-formed contract, else a curated
    ``{"error": str}`` dict (the repo's Phase-H idiom). Used by the importer
    (before storing — Gate 1) and defensively by ``ResearchPriors.load()``.
    """
    if not isinstance(obj, dict):
        return _err("document must be a JSON object.")

    # ── metadata ──
    sv = obj.get("schema_version")
    if not isinstance(sv, str) or not sv.strip():
        return _err("schema_version is required (a string, e.g. '1.0').")
    major = sv.split(".")[0]
    if major not in _KNOWN_SCHEMA_MAJORS:
        return _err(f"unknown schema_version major {sv!r} "
                    f"(supported: {sorted(_KNOWN_SCHEMA_MAJORS)}).")
    dv = obj.get("dataset_version")
    if not isinstance(dv, str) or not dv.strip():
        return _err("dataset_version is required (an opaque provenance string).")

    # ── required axes present ──
    for axis in _REQUIRED_AXES:
        if axis not in obj:
            return _err(f"missing required axis {axis!r}.")

    # spectral_class_weights: non-empty {str: positive number}
    scw = obj["spectral_class_weights"]
    if not isinstance(scw, dict) or not scw:
        return _err("spectral_class_weights must be a non-empty object.")
    for k, v in scw.items():
        if not isinstance(k, str):
            return _err("spectral_class_weights keys must be strings.")
        if not _is_num(v) or v <= 0:
            return _err(f"spectral_class_weights[{k!r}] must be a positive number.")

    # n_planet_dist: non-empty {int-coercible: non-negative number}, >=1 positive
    npd = obj["n_planet_dist"]
    if not isinstance(npd, dict) or not npd:
        return _err("n_planet_dist must be a non-empty object.")
    saw_positive = False
    for k, v in npd.items():
        try:
            int(k)
        except (TypeError, ValueError):
            return _err(f"n_planet_dist key {k!r} must be an integer (count).")
        if not _is_num(v) or v < 0:
            return _err(f"n_planet_dist[{k!r}] must be a non-negative number.")
        if v > 0:
            saw_positive = True
    if not saw_positive:
        return _err("n_planet_dist must have at least one positive weight.")

    # spacing_ratio: [lo, hi], 0 < lo <= hi
    e = _check_range_pair(obj["spacing_ratio"], "spacing_ratio", require_positive_lo=True)
    if e:
        return _err(e)

    # mass_by_zone: exactly the 4 zones, each [lo, hi] 0 < lo <= hi
    mbz = obj["mass_by_zone"]
    if not isinstance(mbz, dict):
        return _err("mass_by_zone must be an object.")
    if set(mbz) != set(_REQUIRED_ZONES):
        return _err(f"mass_by_zone must have exactly the zones {list(_REQUIRED_ZONES)} "
                    f"(got {sorted(mbz)}).")
    for zone in _REQUIRED_ZONES:
        e = _check_range_pair(mbz[zone], f"mass_by_zone[{zone!r}]", require_positive_lo=True)
        if e:
            return _err(e)

    # moon_count: [lo, hi] ints 0 <= lo <= hi
    mc = obj["moon_count"]
    e = _check_range_pair(mc, "moon_count", require_positive_lo=False)
    if e:
        return _err(e)
    if not all(float(x).is_integer() for x in mc):
        return _err("moon_count bounds must be whole numbers.")

    # moon_mass_frac: [lo, hi] 0 < lo <= hi
    e = _check_range_pair(obj["moon_mass_frac"], "moon_mass_frac", require_positive_lo=True)
    if e:
        return _err(e)

    # ── origin_priors (optional) ──
    op = obj.get("origin_priors")
    if op is not None:
        if not isinstance(op, dict):
            return _err("origin_priors must be an object keyed by context.")
        for ctx, hyps in op.items():
            if not isinstance(ctx, str):
                return _err("origin_priors keys must be strings.")
            if not isinstance(hyps, list) or not hyps:
                return _err(f"origin_priors[{ctx!r}] must be a non-empty list.")
            for h in hyps:
                if not isinstance(h, dict):
                    return _err(f"origin_priors[{ctx!r}] entries must be objects.")
                if not isinstance(h.get("pathway"), str) or not h["pathway"].strip():
                    return _err(f"origin_priors[{ctx!r}]: each entry needs a 'pathway' string.")
                if h.get("plausibility") not in _PLAUSIBILITY:
                    return _err(f"origin_priors[{ctx!r}]: plausibility must be one of "
                                f"{sorted(_PLAUSIBILITY)}.")

    # ── v2 optional blocks (validated only when present; additive superset) ──
    for name, checker in _V2_BLOCK_CHECKERS.items():
        block = obj.get(name)
        if block is not None:
            e = checker(block)
            if e:
                return _err(e)

    # Cross-block invariant (v2.3): inner_giant_population.occurrence_ref points into
    # occurrence_by_metallicity, so that block is a hard dependency. Checked here
    # rather than in the block checker, which only sees its own sub-document.
    if (obj.get("inner_giant_population") is not None
            and obj.get("occurrence_by_metallicity") is None):
        return _err("inner_giant_population requires occurrence_by_metallicity "
                    f"(its occurrence_ref is {_INNER_GIANT_OCCURRENCE_REF!r}).")

    return None


# ── Phase R3-C3 · importer (validate-before-store) + status reader ────────────
#
# In the GCNS/Hypatia ingest lineage: validate the source contract FIRST, then write
# the cache atomically-ish (priors.json + meta.json). A malformed source returns a
# curated {"error"} and writes NOTHING, so an existing cache survives a bad import
# (Gate-1). Storage is a cached file (D1) — the priors are one small versioned
# document read whole at generation time, not a queryable rowset. No network.

def _notify(progress_callback, msg):
    if progress_callback:
        progress_callback(msg)


def compute_research_priors_ingest(path=None, cache_dir=None, progress_callback=None):
    """Validate a formation-priors contract file and store it in the cache.

    Args:
        path: source contract JSON. Defaults to the committed sample fixture
              (scaffold mode); a consumer with real priors passes their own file.
        cache_dir: target cache dir (default ``data/research_priors/``;
                   a testability hook).
        progress_callback: optional ``fn(str)`` for GUI/CLI progress.

    Returns a summary dict on success, or ``{"error": str}`` (Gate-1 — nothing is
    written on any validation failure).
    """
    src = Path(path) if path is not None else _SAMPLE_CONTRACT_PATH
    cache = Path(cache_dir if cache_dir is not None else _DEFAULT_CACHE_DIR)

    _notify(progress_callback, f"Reading research-priors contract: {src}")
    if not src.is_file():
        return _err(f"contract file not found: {src}")
    try:
        with open(src, encoding="utf-8") as fh:
            obj = json.load(fh)
    except (OSError, ValueError) as e:
        return _err(f"could not read {src}: {e}")

    _notify(progress_callback, "Validating contract…")
    err = validate_priors_contract(obj)
    if err:
        return err   # Gate-1: nothing stored on a bad contract

    # ── store (only after validation) ──
    _notify(progress_callback, "Storing validated priors…")
    stored_at = datetime.datetime.now().isoformat(timespec="seconds")
    origin_contexts = len(obj.get("origin_priors") or {})
    meta = {
        "schema_version": obj["schema_version"],
        "dataset_version": obj["dataset_version"],
        "source": str(src),
        "axes_loaded": len(_REQUIRED_AXES),
        "origin_contexts": origin_contexts,
        "v2_blocks": present_v2_blocks(obj),   # [] for a v1 dataset (Phase R3-V2)
        "stored_at": stored_at,
    }
    try:
        cache.mkdir(parents=True, exist_ok=True)
        with open(cache / _CACHE_PRIORS_NAME, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2)
        with open(cache / _CACHE_META_NAME, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)
    except OSError as e:
        return _err(f"could not write cache at {cache}: {e}")

    _notify(progress_callback, "Done.")
    return {**meta, "cache_dir": str(cache)}


def get_research_priors_status(cache_dir=None):
    """Pure-pathlib/JSON status of the ingested priors cache (no provider build).

    Returns ``{loaded, dataset_version, schema_version, origin_contexts, v2_blocks,
    stored_at}`` — ``loaded`` False (rest None) when no dataset has been ingested.
    ``v2_blocks`` lists any Phase R3-V2 superset blocks present ([] for a v1
    dataset or a pre-V2 cache). Used by the opt-57 DbStatus surface, like
    ``core.dust.get_dust_map_status``.
    """
    cache = Path(cache_dir if cache_dir is not None else _DEFAULT_CACHE_DIR)
    meta_file = cache / _CACHE_META_NAME
    priors_file = cache / _CACHE_PRIORS_NAME
    _not_loaded = {"loaded": False, "dataset_version": None, "schema_version": None,
                   "origin_contexts": None, "v2_blocks": None, "stored_at": None}
    if not (meta_file.is_file() and priors_file.is_file()):
        return dict(_not_loaded)
    try:
        with open(meta_file, encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        return dict(_not_loaded)
    return {
        "loaded": True,
        "dataset_version": meta.get("dataset_version"),
        "schema_version": meta.get("schema_version"),
        "origin_contexts": meta.get("origin_contexts"),
        "v2_blocks": meta.get("v2_blocks") or [],   # pre-V2 caches lack the key
        "stored_at": meta.get("stored_at"),
    }
