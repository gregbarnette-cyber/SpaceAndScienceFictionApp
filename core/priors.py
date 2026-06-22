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
# There is no policy switch, no ingest, and no `ResearchPriors` here — that is R3.


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
