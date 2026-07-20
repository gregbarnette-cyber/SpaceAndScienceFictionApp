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
# See docs/research-priors-contract.md and PHASE_R3_PLAN.md.

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
# them yet (Stage B — see PHASE_R3_V2_PLAN.md). The block names, in stored order:
_V2_BLOCK_NAMES = (
    "mass_model",                 # F1 — isolation-mass scaling (replaces mass_by_zone)
    "occurrence_by_metallicity",  # F2 — [Fe/H]-conditioned planet count / giant fraction
    "intra_system_correlation",   # F3 — peas-in-a-pod joint draws
    "feh_dist",                   # app-side: synthetic-mode host [Fe/H] source (Decision 2)
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


# name → checker; iteration order is _V2_BLOCK_NAMES (stable).
_V2_BLOCK_CHECKERS = {
    "mass_model": _check_mass_model,
    "occurrence_by_metallicity": _check_occurrence_by_metallicity,
    "intra_system_correlation": _check_intra_system_correlation,
    "feh_dist": _check_feh_dist,
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
