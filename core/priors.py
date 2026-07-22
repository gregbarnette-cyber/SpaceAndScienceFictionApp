# core/priors.py — Phase R1: synthetic-realism priors provider (the R3 seam).
#
# A "priors provider" supplies the literature-informed sampling constants the
# procedural generator (core/generate.py) draws from: which spectral classes are
# common, how many planets to expect, how widely they are spaced, the per-zone
# mass bands, and the per-giant moon priors.
#
# Phase R1 ships ONLY `DefaultPriors` — a single concrete provider whose values
# are deliberately tagged `grounding="default-extrapolation"` so every synthetic
# field the generator emits can be flagged as "an informed default, not a
# research-derived population model."  The provider object is the seam Phase R3
# will reuse: R3 adds a `ResearchPriors` sibling (fed by the sister project's
# versioned formation-priors data contract) and a policy switch, plugging in
# WITHOUT a generator refactor because both expose the same attribute surface.
#
# Phase R3-C2 adds that sibling: `ResearchPriors` (loads the versioned formation-
# priors data contract — see core/research_priors.py + docs/research-priors-
# contract.md) and `get_priors(research_policy)` — the single selector the engine
# calls instead of instantiating a provider directly. The importer that populates
# the cache (`compute_research_priors_ingest`) lands in R3-C3; the engine wiring
# (generate.py / feasibility.py) in R3-C4/C5. Until then nothing calls get_priors.

import copy
import json
from pathlib import Path

from core.research_priors import (
    validate_priors_contract,
    _DEFAULT_CACHE_DIR,
    _CACHE_PRIORS_NAME,
)


class DefaultPriors:
    """Literature-informed default priors for synthetic system generation.

    Every value is an informed default, not a research-derived population model;
    consumers tag emitted synthetic fields with this provider's ``grounding``.

    Attribute surface (the contract R2/R3 providers must also expose):

    - ``spectral_class_weights`` — ``{letter: weight}`` host-star sampling
      weights (M ≫ K > G > F > A > B; roughly the solar-neighbourhood census,
      O excluded — too rare / short-lived for stable planetary systems).
    - ``n_planet_dist`` — ``{count: weight}`` planet-count distribution,
      peaking at 2–6.
    - ``spacing_ratio`` — ``(min, max)`` adjacent-SMA ratio band
      (Titius–Bode-ish ≈ 1.4–2.0; the generator jitters within it).
    - ``mass_by_zone`` — ``{zone: (min_earth, max_earth)}`` mass-draw bands for
      the ``hot`` / ``hz`` / ``cold`` / ``far`` orbital zones (Earth masses).
    - ``moon_count`` — ``(min, max)`` inclusive moon count drawn per giant.
    - ``moon_mass_frac`` — ``(min, max)`` moon mass as a fraction of its host
      planet's mass.
    """

    name = "DEFAULTS"
    grounding = "default-extrapolation"

    # ── Phase R3-V2 additive superset blocks ──
    # DefaultPriors never carries them (it is the v1 marginals fallback), so they
    # are None here — the engine reads them via getattr and falls back to the v1
    # field whenever they are None (mass_by_zone, flat n_planet_dist, independent
    # draws). Set on ResearchPriors only when a v2 dataset supplies them.
    mass_model = None
    occurrence_by_metallicity = None
    intra_system_correlation = None
    feh_dist = None
    cold_giant_population = None    # v2.2 — decoupled cold-giant population (B6/L2)
    inner_giant_population = None   # v2.3 — decoupled close-in giant population
    stellar_multiplicity = None     # v2.4 — stellar multiplicity / close pairs
    stellar_activity = None         # v2.4 — rotation-activity chain + circumbinary XUV

    def __init__(self):
        # Host-star spectral-class weights (M ≫ K > G > F > A > B).
        # Approximate solar-neighbourhood fractions (Kroupa-ish field census).
        self.spectral_class_weights = {
            "M": 0.74,
            "K": 0.12,
            "G": 0.076,
            "F": 0.03,
            "A": 0.006,
            "B": 0.0013,
        }

        # Planet-count distribution — weights need not sum to 1 (the generator
        # normalises). Peak at 2–6, a long thin tail, a small chance of 0.
        self.n_planet_dist = {
            0: 0.05, 1: 0.10, 2: 0.18, 3: 0.20, 4: 0.16,
            5: 0.12, 6: 0.08, 7: 0.05, 8: 0.03, 9: 0.02, 10: 0.01,
        }

        # Adjacent semi-major-axis ratio band (a_{i+1} / a_i), jittered per gap.
        self.spacing_ratio = (1.4, 2.0)

        # Mass-draw bands (Earth masses) by orbital zone relative to the HZ and
        # snow line. "cold" (just beyond the HZ, around the snow line) is where
        # giants form most readily, so its band runs widest.
        self.mass_by_zone = {
            "hot":  (0.05, 6.0),     # interior to the HZ — rocky-dominated
            "hz":   (0.10, 8.0),     # in the HZ — terrestrial / super-Earth
            "cold": (0.50, 600.0),   # HZ-outer to snow line — giants common
            "far":  (0.30, 80.0),    # outer system — ice giants and smaller
        }

        # Per-giant moon priors.
        self.moon_count = (0, 5)             # inclusive count drawn per giant
        self.moon_mass_frac = (1e-5, 5e-4)   # moon mass / host-planet mass


# ── Phase R3-C2 · research-calibrated provider + the policy selector ──────────

class PriorsUnavailable(Exception):
    """Raised when ``research_policy='strict'`` is requested but no research-priors
    dataset has been ingested. Callers (generate.py / feasibility.py, R3-C4/C5)
    convert this into the curated ``{"error": ...}`` self-validating result."""


class ResearchPriors:
    """Research-calibrated priors provider (the R3 sibling of ``DefaultPriors``).

    Exposes the **same attribute surface** as ``DefaultPriors`` (so the generator
    consumes either interchangeably), built from a validated formation-priors data
    contract (see ``core/research_priors.py`` + ``docs/research-priors-contract.md``),
    plus three additions: ``origin_priors`` (the calibrated Layer-3 narrative map),
    ``version`` (the dataset_version — folded into the determinism tuple + output
    provenance) and ``schema_version``. ``grounding`` is ``"research-calibrated"``
    so re-tagging is automatic wherever the engine reads ``priors.grounding``.

    Phase R3-V2 adds four optional superset attributes — ``mass_model``,
    ``occurrence_by_metallicity``, ``intra_system_correlation`` and ``feh_dist`` —
    each ``None`` unless a v2 dataset supplies it (``DefaultPriors`` sets them None
    too, so ``getattr`` is uniform). Stage A stores/exposes them; the sampling
    engine consumes them in Stage B (see PHASE_R3_V2_PLAN.md).

    Build via ``from_file`` / ``from_contract`` (direct, used in tests) or
    ``load(cache_dir)`` (reads the importer's cache; raises ``PriorsUnavailable``
    when no dataset has been ingested).
    """

    name = "RESEARCH"
    grounding = "research-calibrated"

    def __init__(self, contract):
        # contract is assumed validated (from_contract enforces this).
        self.schema_version = contract["schema_version"]
        self.version = contract["dataset_version"]
        self.provenance = copy.deepcopy(contract.get("provenance", {}))

        # ── the DefaultPriors attribute surface, typed to match exactly ──
        self.spectral_class_weights = dict(contract["spectral_class_weights"])
        # JSON object keys are strings → coerce to int so the generator's
        # `sorted(priors.n_planet_dist.items())` orders numerically (as it does
        # for DefaultPriors), not lexicographically ("0","1","10","2",…).
        self.n_planet_dist = {int(k): float(v)
                              for k, v in contract["n_planet_dist"].items()}
        self.spacing_ratio = tuple(contract["spacing_ratio"])
        self.mass_by_zone = {z: tuple(v) for z, v in contract["mass_by_zone"].items()}
        self.moon_count = tuple(int(x) for x in contract["moon_count"])
        self.moon_mass_frac = tuple(float(x) for x in contract["moon_mass_frac"])

        # ── the one new axis (calibrated Layer-3 origin narrative) ──
        self.origin_priors = copy.deepcopy(contract.get("origin_priors", {}))

        # ── Phase R3-V2 additive superset blocks (None when the dataset omits
        # them → the engine falls back to the v1 field, byte-identical). Stored
        # verbatim; the sampling engine interprets them in Stage B. ──
        self.mass_model = copy.deepcopy(contract.get("mass_model"))
        self.occurrence_by_metallicity = copy.deepcopy(
            contract.get("occurrence_by_metallicity"))
        self.intra_system_correlation = copy.deepcopy(
            contract.get("intra_system_correlation"))
        self.feh_dist = copy.deepcopy(contract.get("feh_dist"))
        self.cold_giant_population = copy.deepcopy(contract.get("cold_giant_population"))
        self.inner_giant_population = copy.deepcopy(
            contract.get("inner_giant_population"))
        self.stellar_multiplicity = copy.deepcopy(contract.get("stellar_multiplicity"))
        self.stellar_activity = copy.deepcopy(contract.get("stellar_activity"))

    @classmethod
    def from_contract(cls, obj):
        """Build from an in-memory contract dict (defensively re-validated)."""
        err = validate_priors_contract(obj)
        if err:
            raise ValueError(err["error"])
        return cls(obj)

    @classmethod
    def from_file(cls, path):
        """Build from a contract JSON file."""
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
        return cls.from_contract(obj)

    @classmethod
    def load(cls, cache_dir=None):
        """Load the ingested dataset from the importer's cache.

        Raises ``PriorsUnavailable`` when no dataset has been ingested (the cache's
        ``priors.json`` is absent) — that is the signal ``strict`` turns into a
        curated error.
        """
        cache = Path(cache_dir if cache_dir is not None else _DEFAULT_CACHE_DIR)
        priors_file = cache / _CACHE_PRIORS_NAME
        if not priors_file.is_file():
            raise PriorsUnavailable(
                "research_policy='strict' requires research priors — run the "
                "Import Research Priors utility (CLI/GUI) to ingest a dataset.")
        return cls.from_file(priors_file)


def get_priors(research_policy="permissive", cache_dir=None):
    """Return the priors provider for a research policy — the single swap point.

    - ``"permissive"`` (default) → ``DefaultPriors()`` (R1/R2 behaviour, unchanged).
    - ``"strict"`` → ``ResearchPriors.load(cache_dir)``; raises ``PriorsUnavailable``
      when no dataset has been ingested.
    - anything else → ``ValueError`` (an unknown policy is a programming error).

    ``cache_dir`` is an optional testability hook (default = the importer's cache);
    the engine callers pass only ``research_policy``.
    """
    if research_policy == "permissive":
        return DefaultPriors()
    if research_policy == "strict":
        return ResearchPriors.load(cache_dir)
    raise ValueError(f"unknown research_policy: {research_policy!r}")
