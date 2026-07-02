"""Phase W — bundled artificial-gravity comfort-criteria bands (isolated static data).

Transcribed from the comfort-chart literature synthesized in Theodore Hall's
*The Architecture of Artificial Gravity* / "Artificial Gravity and the Architecture of
Orbital Habitats" (JBIS 52, 1999, Table 1) and his *SpinCalc* tool. Isolated in its own
module (like ``core.cooling_tables`` / ``core.shielding_tables``) because these numbers are
a **human-factors design choice, not physics** — the kinematic outputs of ``core.spin`` are
exact; only the pass/fail bands here are a choice, and every threshold is caller-overridable.

Studies behind Table 1: Hill & Schnitzer 1962; Gilruth 1969; Gordon & Gervais 1969;
Stone 1973; Cramer 1985. The RPM ladder (2/4/6) and the min-gravity column (0.30/0.20/0.10 g)
are verbatim-published; see ``_MODEL_NOTE`` for the three provenance footnotes on the softer
caps (gradient, Coriolis). Values are the request's proposed bands, unadjusted.
"""

# Relative tolerance on band comparisons. A nominal-1 g design computed from round inputs
# (e.g. r=224 m, 2 rpm → 1.0019 g) must not be spuriously failed by a 1.0 g ceiling; the real
# failures in the comfort literature are 10s–100s of % over threshold, so a 1% tolerance
# reconciles boundary designs without masking meaningful failures.
_BAND_TOL = 0.01

# _COMFORT_BANDS[tier][threshold] — None means "not checked for this tier".
_COMFORT_BANDS = {
    "conservative": {  # 1960s unadapted test subjects
        "max_rpm": 2.0,
        "min_gravity_g": 0.30,
        "max_gravity_g": 1.0,
        "min_tangential_velocity_ms": 6.0,
        "max_gradient_pct": 10.0,
        "max_coriolis_pct": 25.0,
    },
    "moderate": {      # adapted occupants
        "max_rpm": 4.0,
        "min_gravity_g": 0.20,
        "max_gravity_g": 1.0,
        "min_tangential_velocity_ms": 3.0,
        "max_gradient_pct": 15.0,
        "max_coriolis_pct": 25.0,
    },
    "relaxed": {       # modern / Hall–Globus, selected or habituated populations
        "max_rpm": 6.0,
        "min_gravity_g": 0.10,
        "max_gravity_g": None,
        "min_tangential_velocity_ms": None,
        "max_gradient_pct": 25.0,
        "max_coriolis_pct": None,
    },
}

_TIERS = ("conservative", "moderate", "relaxed")

# Each check's direction and which computed quantity it reads. "max" → value must be ≤
# threshold (within _BAND_TOL); "min" → value ≥ threshold. Ordered as emitted in the output.
_CHECKS = (
    ("max_rpm",                    "max", "rpm"),
    ("min_gravity_g",              "min", "gravity_g"),
    ("max_gravity_g",              "max", "gravity_g"),
    ("min_tangential_velocity_ms", "min", "tangential_velocity_ms"),
    ("max_gradient_pct",           "max", "gravity_gradient_pct"),
    ("max_coriolis_pct",           "max", "coriolis_ratio_pct"),
)

_SOURCES = (
    "Hill & Schnitzer 1962; Gilruth 1969; Gordon & Gervais 1969; Stone 1973; Cramer 1985; "
    "synthesized in Hall, T. W. (1999), 'Artificial Gravity and the Architecture of Orbital "
    "Habitats', JBIS 52, Table 1, and Hall's SpinCalc."
)

_MODEL_NOTE = (
    "Comfort bands synthesized from the artificial-gravity comfort-chart literature "
    "(" + _SOURCES + "). The bands are a human-factors DESIGN CHOICE, not physics: the "
    "kinematic outputs (v, gradient, Coriolis ratio) are exact; only the pass/fail bands are "
    "a choice, and every threshold is overridable. Conservative/moderate/relaxed are a tiered "
    "synthesis, not published tiers. Confirmed values: the RPM ladder (2/4/6) and the "
    "min-gravity column (0.30/0.20/0.10 g) are verbatim from Table 1. Provenance footnotes: "
    "(1) the conservative gradient 10% has no direct published basis — Table 1 gives 8% "
    "(Gilruth, Gordon & Gervais) and 25% (Stone); (2) published gradient caps are defined over "
    "a 2 m head-to-foot span while occupant_height_m defaults to 1.8 m (gradient scales as "
    "h/r); (3) Stone's 25% Coriolis/apparent-weight cap is defined at a 1.2 m/s carry speed "
    "while walk_speed_ms defaults to 1.0 m/s. Per the Mature-Technology Assumption these are "
    "present-day unadapted constraints — design anchors, not 2500-yr ceilings."
)

_NOTES = (
    "Ballistic/throw deflection (a dropped or thrown object's Coriolis deflection over its "
    "trajectory) scales with the same 2ωu term as the walking Coriolis ratio; it is not a "
    "separate output axis. The RPM ceiling encodes cross-coupled head-turn (canal) sickness, "
    "which scales with ω; an explicit illusory-tumbling magnitude is out of scope."
)
