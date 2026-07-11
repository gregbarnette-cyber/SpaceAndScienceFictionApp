"""Phase AH (Group N) — Alcubierre / metric drive (Packet 22).

Two ``query.py``-only, pure-math, self-validating (Phase-H/P contract) calculators for the
warp-bubble negative-energy budget and the metric's expansion geometry. **These compute real
general relativity; whether the setting's drive USES these mechanisms is the packet's job and is
not asserted by the tool** (the physics/canon separation the request insists on).

Built in three checkpoints (see PHASE_AE_PLAN.md §7a):
  * **AH·1** — N1 ``alcubierre-energy`` ``original`` formulation: the Alcubierre-1994 T⁰⁰
    negative-energy integral, evaluated with a plain-Python Simpson rule (no numpy — keeps
    query.py's cold start ~0.1 s).
  * **AH·2** — N1 reduction-formulation ladder (Van Den Broeck / Krasnikov / White / Bobrick–Martire
    / Fuchs-2024 / Lentz) + the Santiago–Schuster–Visser NEC regime flag.
  * **AH·3 (complete)** — N2 ``warp-metric``: the tanh shape function, the expansion scalar θ, the
    wall geometry, and the Natário zero-expansion variant.

Physics (durable): the local (Eulerian) energy density of the Alcubierre metric is
``T⁰⁰ = −(c²/8πG)·v_s²(y²+z²)/(4 r_s²)·(df/dr_s)²`` (negative → exotic matter; v_s in m/s — the c's of
the textbook geometrized ``c⁴/8πG·(v_s/c)²`` form collected into a single c²); integrating over the
bubble gives ``E = −(c² v_s²/12G)·∫₀^∞ (df/dr_s)² r_s² dr_s`` **joules** (the ∫sin³θ dθ = 4/3 angular
integral fixes the 1/12). With the tanh shape function this scales as ``E ∝ −v_s²·R²/Δ`` (Δ = wall
thickness); the mass-equivalent is ``E/c²``. (A pre-2026-07-11 build used c⁴ here — off by one factor
of c², so the joule value landed in the kg-equiv field; corrected against the Pfenning–Ford ~¼ M☉
anchor at Δ=1 m.)

Constants from ``core.equations``. No network, no DB, no RNG, no time.
"""

import math

from core.equations import _G, _C_MS

# Simpson resolution: ~400 sample points across the wall width, capped so a pathologically thin
# wall can't hang the integrator (a Planck-thin wall is the Ford–Pfenning literature case, not a
# numeric target). The cap is hit only for Δ ≲ R/2500; results there carry resolution_capped=True.
_POINTS_PER_WALL = 400
_N_MAX = 1_000_000
_SECH2_CLAMP = 300.0    # |x| beyond which sech²(x) underflows to 0 (avoids cosh overflow)


def _sech2(x):
    if abs(x) > _SECH2_CLAMP:
        return 0.0
    ch = math.cosh(x)
    return 1.0 / (ch * ch)


def _shape_f(r, R, sigma):
    """Alcubierre tanh top-hat shape function f(r_s) (1 inside, 0 outside)."""
    return (math.tanh(sigma * (r + R)) - math.tanh(sigma * (r - R))) / (2.0 * math.tanh(sigma * R))


def _shape_df(r, R, sigma):
    """df/dr_s of the tanh shape function."""
    return sigma * (_sech2(sigma * (r + R)) - _sech2(sigma * (r - R))) / (2.0 * math.tanh(sigma * R))


def _alcubierre_energy_j(bubble_radius_m, v_s_ms, wall_thickness_m):
    """Numerically integrate the Alcubierre total energy (joules, signed negative).

    Returns (energy_j, integration_points, resolution_capped). Pure-Python Simpson over the
    tanh shape function's (df/dr)²·r² integrand; validated to reproduce the 3.4×10⁴⁵ J
    anchor (≈ −3.75×10²⁸ kg-equiv) at (R=100, v_s=c, Δ=10) and the ∝1/Δ scaling.
    """
    R = bubble_radius_m
    sigma = 1.0 / wall_thickness_m
    tanh_sr = math.tanh(sigma * R)
    upper = R + 40.0 * wall_thickness_m           # integrand (peaked at r=R, width ~Δ) is ~0 beyond

    raw_n = int(_POINTS_PER_WALL * upper / wall_thickness_m)
    n = max(2000, min(raw_n, _N_MAX))
    if n % 2 == 1:
        n += 1
    capped = raw_n > _N_MAX
    h = upper / n

    def integrand(r):
        df = sigma * (_sech2(sigma * (r + R)) - _sech2(sigma * (r - R))) / (2.0 * tanh_sr)
        return df * df * r * r

    total = integrand(0.0) + integrand(upper)
    for i in range(1, n):
        total += (4.0 if i % 2 else 2.0) * integrand(i * h)
    integral = total * h / 3.0
    energy = -(_C_MS ** 2 * v_s_ms ** 2 / (12.0 * _G)) * integral   # joules (E/c² → kg-equiv)
    return energy, n, capped


# The post-1994 development ladder — REPORTED published results (not first-principles
# recomputations of each modified metric). Figures/sources transcribed from the request spec's
# sourced verification pass (2026-07-05). `positive_energy_capable` is True only for the
# subluminal warp-shell frameworks (Bobrick–Martire 2021; Fuchs et al. 2024).
_REDUCTIONS = {
    "van-den-broeck": {
        "source": "Van Den Broeck 1999, arXiv:gr-qc/9905084",
        "positive_energy_capable": False,
        "contested": False,
        "published_figure": ("Total negative mass reduced to ~a few solar masses (~10³⁰ kg) plus "
                             "comparable positive energy, via a microscopic (~10⁻³² m) neck "
                             "wrapping a large interior volume. Still requires exotic matter."),
    },
    "krasnikov": {
        "source": "Krasnikov 2003 (modifying Van Den Broeck 1999)",
        "positive_energy_capable": False,
        "contested": False,
        "published_figure": ("Total negative mass reduced to ~a few milligrams by taking the "
                             "shrink-surface / expand-interior trick further. Still requires "
                             "exotic matter, but astonishingly small."),
    },
    "white": {
        "source": "White 2011, 'Warp Field Mechanics 101', NASA (JSC)",
        "positive_energy_capable": False,
        "contested": True,
        "published_figure": ("For a 10 m bubble at v_s=10c, optimizing wall thickness + oscillating "
                             "the bubble intensity (toroidal energy distribution) reduces the "
                             "requirement from ~Jupiter-mass to ~that of Voyager 1 (~700 kg) or "
                             "less. Still negative-energy; the figure is NASA-Eagleworks and "
                             "CONTESTED."),
    },
    "bobrick-martire": {
        "source": "Bobrick & Martire 2021, arXiv:2102.06824",
        "positive_energy_capable": True,
        "contested": False,
        "published_figure": ("A class of SUBLUMINAL (v_s<c) warp shells can be built from ordinary "
                             "POSITIVE energy — no exotic matter (does NOT give FTL). Also cuts the "
                             "Alcubierre negative-energy need by ~2 orders of magnitude. A warp "
                             "drive is a matter shell moving inertially → it requires propulsion, "
                             "it is not reactionless."),
    },
    "physical-2024": {
        "source": "Fuchs, Helmerich, Bobrick, Martire et al. 2024, arXiv:2405.02709 (Warp Factory; CQG 41, 095009)",
        "positive_energy_capable": True,
        "contested": False,
        "published_figure": ("The current concrete realization: a constant-velocity SUBLUMINAL "
                             "drive that satisfies ALL the energy conditions — a stable matter "
                             "shell + an Alcubierre-like shift vector (positive energy, no exotic "
                             "matter; still cannot beat light)."),
    },
    "lentz": {
        "source": "Lentz 2021, arXiv:2006.07125",
        "positive_energy_capable": False,
        "contested": True,
        "published_figure": ("Claimed SUPERLUMINAL drives from positive-energy solitons — CONTESTED "
                             "/ NOT ACCEPTED. Superluminal warp drives unavoidably violate the NEC "
                             "(Santiago–Schuster–Visser 2021, arXiv:2105.03079)."),
    },
}
FORMULATIONS = ["original"] + list(_REDUCTIONS)

# Santiago–Schuster–Visser 2021 (arXiv:2105.03079): superluminal (v_s ≥ c) warp drives unavoidably
# violate the NEC (exotic matter, in standard GR); subluminal drives can be positive-energy
# (Bobrick–Martire 2021). Load-bearing for the setting's "subluminal metric drive is physically far
# cheaper than FTL" premise.
_REGIME_NOTE = ("Energy-condition status by the Santiago–Schuster–Visser 2021 ruling (arXiv:2105.03079): "
                "any superluminal (v_s ≥ c) warp drive unavoidably violates the NEC → requires exotic "
                "matter in standard GR; a subluminal (v_s < c) drive can be positive-energy "
                "(Bobrick–Martire 2021). The tool reports the physics; canon does not assert the "
                "setting achieves any particular value.")


def compute_alcubierre_energy(bubble_radius_m=None, velocity_c=None, wall_thickness_m=None,
                              formulation="original", neck_radius_m=None):
    """Negative-energy budget of an Alcubierre warp bubble (N1).

    ``original`` (Alcubierre 1994) is COMPUTED from the T⁰⁰ integral for the given (R, v_s, Δ);
    the reduction formulations REPORT their published literature results + energy-condition status
    (not first-principles recomputations of each modified metric).
    """
    if bubble_radius_m is None or bubble_radius_m <= 0:
        return {"error": "Bubble radius must be positive (--bubble-radius-m)."}
    if velocity_c is None or velocity_c <= 0:
        return {"error": "Velocity must be positive (--velocity-c)."}
    if wall_thickness_m is None or wall_thickness_m <= 0:
        return {"error": "Wall thickness must be positive (--wall-thickness-m)."}
    if formulation not in FORMULATIONS:
        return {"error": f"Unknown formulation '{formulation}'. Choices: {', '.join(FORMULATIONS)}."}

    subluminal = velocity_c < 1.0
    common = {
        "formulation": formulation,
        "bubble_radius_m": bubble_radius_m,
        "velocity_c": velocity_c,
        "wall_thickness_m": wall_thickness_m,
        "subluminal": subluminal,
    }

    if formulation == "original":
        v_s_ms = velocity_c * _C_MS
        energy_j, points, capped = _alcubierre_energy_j(bubble_radius_m, v_s_ms, wall_thickness_m)
        note = ("Alcubierre-1994 total energy E = −(c²v_s²/12G)·∫₀^∞ (df/dr_s)² r_s² dr_s over the "
                "tanh shape function, integrated with a plain-Python Simpson rule. Always negative "
                "→ the original bubble requires exotic matter (NEC-violating) at any velocity. "
                "E ∝ −v_s²·R²/Δ (falls linearly with a thicker wall). " + _REGIME_NOTE)
        if capped:
            note += (" NOTE: the wall is thin enough that the Simpson point count was capped — the "
                     "∝1/Δ scaling still holds but this magnitude may under-resolve; the Planck-thin "
                     "limit is the Ford–Pfenning ≫-universe-mass literature case, not a numeric target.")
        return {
            **common,
            "energy_j": energy_j,
            "energy_kg_equiv": energy_j / _C_MS ** 2,
            "energy_condition_status": "NEC-violating-exotic",
            "published_figure": None,
            "positive_energy_j": None,
            "contested": False,
            "source": "Alcubierre 1994, Class. Quantum Grav. 11, L73",
            "integration_points": points,
            "resolution_capped": capped,
            "model_note": note,
        }

    f = _REDUCTIONS[formulation]
    status = "positive-energy-possible" if (subluminal and f["positive_energy_capable"]) else "NEC-violating-exotic"
    note = ("REPORTED published result for the " + formulation + " formulation — a literature value, "
            "not a first-principles recomputation of this modified metric for your inputs. " + _REGIME_NOTE)
    if f["positive_energy_capable"] and not subluminal:
        note += (" This framework is SUBLUMINAL-ONLY; at v_s ≥ c it does not apply and the "
                 "superluminal NEC-violation stands.")
    return {
        **common,
        "energy_j": None,
        "energy_kg_equiv": None,
        "energy_condition_status": status,
        "published_figure": f["published_figure"],
        "positive_energy_j": None,
        "contested": f["contested"],
        "source": f["source"],
        "integration_points": None,
        "resolution_capped": None,
        "model_note": note,
    }


# ── N2 ───────────────────────────────────────────────────────────────────────
_WALL_10_90 = math.atanh(0.8)   # σ·(r−R) at the 10%/90% f-levels → wall 10–90 half-width = this/σ


def compute_warp_metric(bubble_radius_m=None, wall_thickness_sigma=None, velocity_c=None,
                        r_eval_m=None, profile=False, variant="alcubierre"):
    """Geometry of the Alcubierre metric — shape function, expansion scalar, wall region (N2).

    f(r_s) = [tanh(σ(r_s+R)) − tanh(σ(r_s−R))]/[2 tanh(σR)] (≈1 inside, ≈0 outside); expansion
    scalar θ = v_s·(x_s/r_s)·(df/dr_s) (>0 behind = expansion, <0 ahead = contraction, on the axis
    of motion). ``variant="natario"`` (Natário 2002) is the zero-expansion metric: space slides
    around the ship (θ ≡ 0, divergence-free flow).
    """
    if bubble_radius_m is None or bubble_radius_m <= 0:
        return {"error": "Bubble radius must be positive (--bubble-radius-m)."}
    if wall_thickness_sigma is None or wall_thickness_sigma <= 0:
        return {"error": "Wall thickness σ must be positive (--wall-thickness-sigma)."}
    if velocity_c is None or velocity_c <= 0:
        return {"error": "Velocity must be positive (--velocity-c)."}
    if variant not in ("alcubierre", "natario"):
        return {"error": "Variant must be 'alcubierre' or 'natario'."}
    if r_eval_m is not None and r_eval_m < 0:
        return {"error": "Evaluation radius must be ≥ 0 (--r-eval-m)."}

    R = bubble_radius_m
    sigma = wall_thickness_sigma
    v_s_ms = velocity_c * _C_MS
    is_natario = variant == "natario"

    # peak |df/dr| (at r = R) → extremal on-axis expansion/contraction rate (s⁻¹)
    peak_df = abs(_shape_df(R, R, sigma))
    max_expansion = 0.0 if is_natario else v_s_ms * peak_df
    max_contraction = 0.0 if is_natario else -v_s_ms * peak_df

    f_at_r = df_dr_at_r = theta_at_r = None
    if r_eval_m is not None:
        f_at_r = _shape_f(r_eval_m, R, sigma)
        df_dr_at_r = _shape_df(r_eval_m, R, sigma)
        theta_at_r = 0.0 if is_natario else v_s_ms * df_dr_at_r   # forward axis (x_s=+r): contraction

    prof = None
    if profile:
        r_max = max(1.5 * R, R + 8.0 / sigma)
        n = 120
        prof = []
        for i in range(n + 1):
            r = r_max * i / n
            dfv = _shape_df(r, R, sigma)
            prof.append({
                "r_s_m": r,
                "f": _shape_f(r, R, sigma),
                "df_dr": dfv,
                "theta": 0.0 if is_natario else v_s_ms * dfv,
            })

    note = ("Alcubierre shape function f(r_s) = [tanh(σ(r_s+R)) − tanh(σ(r_s−R))]/[2 tanh(σR)] "
            "(f(0)=1 flat interior, f(≫R)=0 flat exterior). Expansion scalar θ = v_s·(x_s/r_s)·"
            "(df/dr_s) in s⁻¹, reported on the forward axis (x_s=+r_s): negative = contraction "
            "AHEAD, mirrored by equal expansion BEHIND (θ is antisymmetric front/back). The wall "
            "(where the exotic energy sits) is the 10–90% f-transition, ±artanh(0.8)/σ about R.")
    if is_natario:
        note = ("Natário 2002 (arXiv:gr-qc/0110086) zero-expansion warp metric: the flow is "
                "divergence-free, so θ ≡ 0 everywhere — space SLIDES AROUND the ship with no volume "
                "contraction/expansion (unlike the Alcubierre metric's contraction-ahead / "
                "expansion-behind). f/df_dr echo the shape function; θ and max_expansion/contraction "
                "are 0 by construction.")

    return {
        "f_at_r": f_at_r,
        "df_dr_at_r": df_dr_at_r,
        "theta_at_r": theta_at_r,
        "wall_inner_m": max(0.0, R - _WALL_10_90 / sigma),
        "wall_outer_m": R + _WALL_10_90 / sigma,
        "max_expansion": max_expansion,
        "max_contraction": max_contraction,
        "profile": prof,
        "bubble_radius_m": R,
        "wall_thickness_sigma": sigma,
        "velocity_c": velocity_c,
        "variant": variant,
        "model_note": note,
    }
