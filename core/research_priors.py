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
_KNOWN_SCHEMA_MAJORS = {"1"}            # schema_version "1.x" is interpretable
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

    Returns ``{loaded, dataset_version, schema_version, origin_contexts,
    stored_at}`` — ``loaded`` False (rest None) when no dataset has been ingested.
    Used by the opt-57 DbStatus surface, like ``core.dust.get_dust_map_status``.
    """
    cache = Path(cache_dir if cache_dir is not None else _DEFAULT_CACHE_DIR)
    meta_file = cache / _CACHE_META_NAME
    priors_file = cache / _CACHE_PRIORS_NAME
    if not (meta_file.is_file() and priors_file.is_file()):
        return {"loaded": False, "dataset_version": None, "schema_version": None,
                "origin_contexts": None, "stored_at": None}
    try:
        with open(meta_file, encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        return {"loaded": False, "dataset_version": None, "schema_version": None,
                "origin_contexts": None, "stored_at": None}
    return {
        "loaded": True,
        "dataset_version": meta.get("dataset_version"),
        "schema_version": meta.get("schema_version"),
        "origin_contexts": meta.get("origin_contexts"),
        "stored_at": meta.get("stored_at"),
    }
