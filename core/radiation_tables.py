"""Phase AS (Packet 34) — bundled static data for the radiation dose → per-clade
biological-ceiling converter (``core.radiation.compute_radiation_ceiling``).

Isolated here (like ``core.shielding_tables`` / ``core.cooling_tables``) so every pinned
physics anchor, RBE/Q table, clade-modifier ladder, and policy number is auditable in one
place and ``core.radiation`` stays pure logic. All numbers are **transcribed reference
values with a stated source + confidence tag** — never fabricated. Each value's PROVENANCE
tag ∈ {``physics-limit``, ``present-datapoint``, ``policy``, ``required-breakthrough``,
``extrapolation``} travels into the response so a downstream consumer sees at a glance that
**600 mSv is policy**, **LD50 is known-science**, **Dsup ×2 is demonstrated-but-cultured**,
**~3000× (of human cells) is an existence proof not a deliverable**, and **upload is RB**.

Packet-34 source pins (verbatim quotes in the sister repo's
``research/biological-medical-and-human-condition-technologies/{claim-map.md,
source-notes/radiation-biology.md}``):

  * **S1**  Kamiya 2014 — VIC 1%-incidence tissue-reaction threshold 0.5 Gy.
  * **S3**  CDC ARS — mild symptoms ~0.3 Gy; ARS onset >0.7 Gy.
  * **S4**  GI-ARS review 2025 — LD50 3.5–4 Gy untreated, 4.5–7 Gy with intensive care.
  * **S5**  NASEM 2021 — 600 mSv career limit @ 3% REID (NASA policy; ESA/Roscosmos/CSA
    use 1000 mSv from the same dose–response science — a risk-tolerance choice, not biology).
  * **S8**  GCR quality-factor review — high-LET biological effectiveness is elevated AND
    uncertain; carry as canon-labelled uncertainty, never a precise multiplier.
  * **S10** amifostine review — pharmacological dose-modification factor 1–3× (a ceiling).
  * **S11** Deinococcus review — 5000 Gy acute with no loss of viability (~3000× human cells);
    whole-mechanism human transplant = required-breakthrough (existence proof, not a modifier).
  * **S12** Hashimoto 2016 (Dsup) — ~½ the DNA damage (comet assay) in cultured human cells;
    NOT a validated organismal survival multiplier.
  * **S14** DNA-repair-disorder clinical — fatal at doses as low as 3 Gy (the hypersensitivity
    failure mode a mis-engineered repair boost must be representable as producing).
  * **S15** Kato 2001 (p53) — apoptosis-threshold tuning trades acute vs stochastic (⚠ abstract-
    only; the acute↔cancer trade is textbook radiobiology but inferred — re-open before canon).
  * **S61** Tegmark 2000 — neural decoherence ~1e-13–1e-20 s ≪ cognition ~1e-3 s → the upload
    substrate is a required-breakthrough; no Gy/Sv number is emitted for it.

Q(LET) is the ICRP 60/103 quality-factor relation (implemented, not tabulated). The RBE(LET)
grid is an order-of-magnitude transcription of the radiobiology consensus SHAPE — the specific
numbers are this repo's implementation choice per the request (§2.1); only the sign is pinned
(high-LET HZE must yield RBE > 1). No network, no DB, no RNG, no time.
"""

import math

# ── Provenance / confidence legend (travels into every response) ──────────────
PROVENANCE_LEGEND = {
    "physics-limit": "Known-science physical/biological limit — LD50, ARS thresholds, the "
                     "ICRP quality factor.",
    "present-datapoint": "A present-day measured datapoint or prototype (electrode lifetime, "
                         "demonstrated pharmacology).",
    "policy": "A risk-tolerance POLICY choice, not a biological ceiling — the 600/1000 mSv "
              "career budget (S5).",
    "required-breakthrough": "Requires an unproven breakthrough — the Deinococcus whole-mechanism "
                             "transplant, the upload substrate (S61), whole-organ vascularization.",
    "extrapolation": "Extrapolated beyond its demonstrated regime — Dsup organismal survival "
                     "(cultured-cell → organism gap), engineered apoptosis/repair tuning.",
}

# ── Axis A — acute / deterministic anchors (photon-equivalent Gy), pinned ──────
ACUTE_MILD_GY = 0.3            # S3 — mild symptoms possible
ARS_ONSET_GY = 0.7            # S3 — acute-radiation-syndrome onset
LD50_UNTREATED_LOW_GY = 3.5   # S4
LD50_UNTREATED_HIGH_GY = 4.0  # S4
LD50_TREATED_LOW_GY = 4.5     # S4 — with intensive medical care
LD50_TREATED_HIGH_GY = 7.0    # S4
LD50_REFERENCE_GY = 3.75      # untreated midpoint — the BASELINE Axis-A ceiling
VIC_THRESHOLD_GY = 0.5        # S1 — 1%-incidence tissue-reaction sub-endpoint
REPAIR_DISORDER_FATAL_GY = 3.0    # S14 — hypersensitivity floor (below baseline LD50)
DEINOCOCCUS_CEILING_GY = 5000.0   # S11 — existence-proof sanity ceiling (not a deliverable)

ACUTE_ANCHOR_SOURCE = (
    "Acute deterministic anchors (photon-equivalent Gy): mild ~0.3 Gy, ARS onset >0.7 Gy "
    "(S3 CDC); LD50 3.5–4 Gy untreated / 4.5–7 Gy treated (S4 GI-ARS review 2025); VIC "
    "1%-incidence tissue reaction 0.5 Gy (S1 Kamiya 2014). Baseline Axis-A ceiling = the "
    "untreated LD50 midpoint 3.75 Gy."
)


def ars_band(d_a_gy):
    """ARS severity band for an RBE-weighted acute-equivalent dose (Gy)."""
    if d_a_gy < ACUTE_MILD_GY:
        return "none"
    if d_a_gy < ARS_ONSET_GY:
        return "mild"
    if d_a_gy < LD50_UNTREATED_LOW_GY:
        return "ars-onset"
    if d_a_gy <= LD50_TREATED_HIGH_GY:
        return "ld50-region"
    return "supralethal"


# ── RBE(LET) — Axis A (deterministic) ─────────────────────────────────────────
RBE_SOURCE = (
    "Deterministic (early / tissue-reaction) RBE vs unrestricted LET_inf in water — an "
    "ORDER-OF-MAGNITUDE transcription of the radiobiology consensus SHAPE: RBE rises with LET "
    "to a peak near ~100-200 keV/um, then declines past the single-hit-inactivation optimum. "
    "High-LET biological effectiveness is elevated AND uncertain (S8) — carried as canon-"
    "labelled uncertainty. DISTINCT from the stochastic quality factor Q(LET). The specific "
    "numbers are an implementation choice (request §2.1); only the sign is pinned (HZE RBE > 1)."
)

# (LET keV/um, RBE) nodes, log-LET-interpolated. Below the first / above the last node the
# value clamps and the caller is told (out_of_range_let) — never a silent extrapolation.
_RBE_LET = (
    (0.1, 1.0),
    (3.0, 1.0),
    (10.0, 1.3),
    (30.0, 2.0),
    (100.0, 3.0),
    (200.0, 3.5),   # peak
    (500.0, 2.6),
    (1000.0, 1.8),
)


def rbe_for_let(let_kev_um):
    """Return ``(rbe, out_of_range)`` for an unrestricted LET (keV/µm).

    Log-LET linear interpolation between the bundled nodes; clamps below the first / above the
    last node with ``out_of_range=True`` so the extrapolation is flagged, not silent.
    """
    nodes = _RBE_LET
    lo_let, lo_rbe = nodes[0]
    hi_let, hi_rbe = nodes[-1]
    if let_kev_um <= lo_let:
        return lo_rbe, let_kev_um < lo_let
    if let_kev_um >= hi_let:
        return hi_rbe, let_kev_um > hi_let
    for (l0, r0), (l1, r1) in zip(nodes, nodes[1:]):
        if l0 <= let_kev_um <= l1:
            t = (math.log(let_kev_um) - math.log(l0)) / (math.log(l1) - math.log(l0))
            return r0 + t * (r1 - r0), False
    return hi_rbe, True  # unreachable, defensive


# ── Q(LET) — Axis B (stochastic quality factor), ICRP 60/103 ──────────────────
Q_SOURCE = (
    "ICRP Publication 60/103 quality factor Q(L) vs unrestricted LET_inf in water: Q=1 for "
    "L<=10; Q=0.32*L-2.2 for 10<L<=100; Q=300/sqrt(L) for L>100 keV/um (peak Q~30 at L=100). "
    "The STOCHASTIC weighting used for the cumulative equivalent dose H — distinct from the "
    "deterministic RBE(LET)."
)


def q_for_let(let_kev_um):
    """ICRP 60/103 quality factor Q for an unrestricted LET (keV/µm)."""
    if let_kev_um <= 10.0:
        return 1.0
    if let_kev_um <= 100.0:
        return 0.32 * let_kev_um - 2.2
    return 300.0 / math.sqrt(let_kev_um)


# ── Fluence → absorbed dose ───────────────────────────────────────────────────
# D[Gy] = 1.602e-9 * LET[keV/um] * Phi[cm^-2]  (water, rho = 1000 kg/m^3).
FLUENCE_DOSE_K = 1.602e-9
FLUENCE_DOSE_SOURCE = (
    "Absorbed dose from fluence Phi and unrestricted LET in water: "
    "D[Gy] = 1.602e-9 * LET[keV/um] * Phi[cm^-2] (rho = 1000 kg/m^3). Standard track-structure "
    "conversion; other media scale by density (not modelled — water reference)."
)

# Representative unrestricted LET_inf in water (keV/µm) for a few particle presets — an
# order-of-magnitude convenience only; the LET-vs-energy curve is NOT modelled. Supply
# --let-kev-um directly for precision, or an --let-spectrum for a composite GCR/HZE field.
_PARTICLE_LET = {
    "photon": 0.3,
    "electron": 0.2,
    "proton": 0.5,
    "alpha": 90.0,
    "carbon": 160.0,
    "iron": 150.0,
    "hze": 100.0,
}
PARTICLE_LET_SOURCE = (
    "Representative LET presets (keV/um in water) — ORDER-OF-MAGNITUDE, energy-independent; the "
    "LET-vs-energy curve is not modelled. For GCR/HZE the physically correct input is an "
    "--let-spectrum; for precision supply --let-kev-um."
)


def particle_names():
    return sorted(_PARTICLE_LET)


def let_for_particle(particle_type, energy_mev_amu=None):
    """Preset representative LET (keV/µm) for a particle, or ``None`` if unknown.

    ``energy_mev_amu`` is accepted for provenance but does NOT move the preset (documented
    coarse convenience — see ``PARTICLE_LET_SOURCE``).
    """
    return _PARTICLE_LET.get(particle_type)


# ── Axis B — stochastic policy + REID science anchor ──────────────────────────
# REID science anchor (S5): 600 mSv effective dose -> 3% REID. ONE dose-response anchor drives
# the reported REID regardless of which career BUDGET (a policy knob) is selected.
REID_ANCHOR_MSV = 600.0
REID_ANCHOR_PCT = 3.0
REID_ANCHOR_SOURCE = (
    "NASA/NASEM 2021 (S5): career effective-dose limit 600 mSv defined at a 3% risk of "
    "exposure-induced death (REID). The reported REID scales linearly from this single "
    "science anchor; the SELECTED career budget (600 vs 1000 mSv) is a separate POLICY knob."
)

# Career BUDGETS (mSv) — a risk-tolerance POLICY, never a biological ceiling (S5).
CAREER_BUDGETS = {
    "600": {"budget_msv": 600.0, "label": "600 mSv career limit (NASA, S5)", "confidence": "policy"},
    "1000": {"budget_msv": 1000.0,
             "label": "1000 mSv career limit (ESA/Roscosmos/CSA, same science, higher risk "
                      "tolerance — S5)", "confidence": "policy"},
}
DEFAULT_CAREER_BUDGET = "600"

# Pharmacological dose-modification factor ceiling (S10) and DDREF.
DMF_MAX = 3.0
DMF_SOURCE = (
    "Pharmacological radioprotection (amifostine, S10): dose-modification factor 1-3x, oxygen-"
    "tension-dependent and tissue-selective. Applies to Axis A only; clamped at 3x (a ceiling, "
    "not clade-differentiating — genetic/engineered routes are needed beyond this)."
)
DDREF_DEFAULT = 1.0
DDREF_SOURCE = (
    "Dose-and-dose-rate effectiveness factor (DDREF) for chronic Axis-B stochastic effectiveness. "
    "Default 1.0 (inert) so the 600 mSv -> 3% REID policy anchor reproduces exactly; the disputed "
    "~2x low-dose-rate reduction is available via --ddref 2 and is flagged UNCERTAIN (the value is "
    "actively debated — NCRP/UNSCEAR). CAVEAT: the 600 mSv @ 3% REID anchor ALREADY embeds low-dose-"
    "rate effectiveness, so setting --ddref > 1 makes the reported REID DISAGREE with the NASA policy "
    "pairing (600 mSv chronic reads 1.5% at DDREF 2) — a deliberate, non-policy modeling choice the "
    "caller layers knowingly, NOT 'more correct.'"
)

# Below this order-of-magnitude chronic rate, repair keeps pace and no acute tissue reaction is
# expected (a separate check from the cumulative-dose axes; not a hard threshold).
TISSUE_REACTION_RATE_THRESHOLD_GY_PER_DAY = 0.5
TISSUE_REACTION_RATE_SOURCE = (
    "Order-of-magnitude chronic dose-rate below which repair keeps pace and the acute "
    "deterministic ceiling does not bind (a tissue-reaction-rate screen, not the cumulative axes)."
)

# ── SEU / bit-error budget (upload substrate + cyborg hardware fraction) ───────
SEU_CROSS_SECTION_DEFAULT_CM2 = 1.0e-14   # per-bit, unhardened-device order of magnitude
SEU_SOURCE = (
    "Single-event-upset / bit-error budget for the HARDWARE substrate (upload; cyborg hardware "
    "fraction). A DIFFERENT PHYSICAL QUANTITY — engineering hardening + error correction, not DNA "
    "damage. Order-of-magnitude: upsets = fluence * per-bit cross-section * bits, scored against a "
    "redundancy/ECC margin. The ECC scheme is NOT modelled — the tool emits the right axis (an "
    "error budget), never a spurious Gy/Sv. Default per-bit cross-section 1e-14 cm^2 (unhardened; "
    "override with --seu-cross-section-cm2)."
)


# ── Clade ladder (§2.4) ───────────────────────────────────────────────────────
# Each lever composes multiplicative factors onto (m_A, m_B):
#   f_a > 1 raises the acute ceiling (good); f_a < 1 LOWERS it below baseline (a mis-engineered
#           clade — "signed" m_A, per §2.3 / the S14 hypersensitivity failure mode).
#   f_b < 1 improves the stochastic axis (lower REID/Sv); f_b > 1 worsens it.
# The p53/apoptosis-suppression lever is COUPLED: raising acute tolerance (f_a>1) by culling
# fewer damaged cells MUST raise cancer risk (f_b>=1). A p53 lever configured to improve BOTH is
# forbidden by default (S15 — abstract-only, re-open before canon; overridable via a flag).
LEVER_REPAIR_FIDELITY = "repair-fidelity"
LEVER_P53 = "p53"
LEVER_TYPES = (LEVER_REPAIR_FIDELITY, LEVER_P53)

CLADES = {
    "baseline-human": {
        "base_m_a": 1.0, "base_m_b": 1.0, "levers": (),
        "biological": True, "hardware_fraction": False,
        "confidence": "physics-limit",
        "note": "Baseline anchors: LD50 ~3.75 Gy untreated (S4); 600-1000 mSv policy (S5); "
                "pharmacological DMF <=3x (S10).",
    },
    "gene-mod": {
        # Dsup-type ~2x damage reduction — a repair-fidelity lever (reduces INITIAL damage), so it
        # raises the acute ceiling AND may lower REID/Sv. Bounded + uncertain (cultured human cells,
        # comet-assay endpoint; organismal multiplier NOT shown). NOT the Deinococcus ~5000 Gy.
        "base_m_a": 1.0, "base_m_b": 1.0,
        "levers": ({"type": LEVER_REPAIR_FIDELITY, "f_a": 2.0, "f_b": 0.7,
                    "confidence": "extrapolation",
                    "note": "Dsup ~2x DNA-damage reduction in cultured human cells (S12); organismal "
                            "survival multiplier NOT shown (cultured-cell -> organism gap). NOT the "
                            "~5000 Gy / ~3000x Deinococcus existence proof (S11 — required-breakthrough, "
                            "not a deliverable modifier)."},),
        "biological": True, "hardware_fraction": False,
        "confidence": "extrapolation",
        "note": "Dsup-type engineered radiotolerance; carried as a bounded, uncertain factor.",
    },
    "cyborg": {
        # The biological neural/organ fraction still governs the Gy/Sv ceiling; the hardware
        # fraction moves to the SEU budget.
        "base_m_a": 1.0, "base_m_b": 1.0, "levers": (),
        "biological": True, "hardware_fraction": True,
        "confidence": "extrapolation",
        "note": "Biological fraction governs Axis A/B (electrode life 956-2246 d, glial scarring — "
                "present datapoint; whole-organ vascularization = required-breakthrough, S50/S52). "
                "Hardware fraction -> SEU budget.",
    },
    "upload": {
        "base_m_a": None, "base_m_b": None, "levers": (),
        "biological": False, "hardware_fraction": True,
        "confidence": "required-breakthrough",
        "note": "Whole substrate is a required-breakthrough (neural decoherence ~1e-13-1e-20 s << "
                "cognition ~1e-3 s, S61). No Gy/Sv emitted — scored on the SEU/bit-error budget.",
    },
    "custom": {
        # A user-defined clade: baseline modifiers, levers supplied entirely via --lever*.
        "base_m_a": 1.0, "base_m_b": 1.0, "levers": (),
        "biological": True, "hardware_fraction": False,
        "confidence": "extrapolation",
        "note": "Caller-defined clade — modifiers come from the supplied lever(s).",
    },
}
CLADE_NAMES = tuple(CLADES)

MODEL_NOTE = (
    "Two-axis radiation dose -> per-clade biological ceiling. Axis A (deterministic, Gy, RBE-"
    "weighted) scores acute tissue-reaction/ARS survival against a clade acute ceiling; Axis B "
    "(stochastic, Sv, ICRP Q-weighted) scores the cumulative equivalent dose against a career "
    "REID budget. The axes are INDEPENDENT and never collapse to a scalar — a clade modifier is a "
    "PAIR (m_A, m_B) and the p53/apoptosis lever forces them apart (acute up => cancer up). For "
    "the upload clade (and the cyborg hardware fraction) no Gy/Sv is emitted — a SEU/bit-error "
    "budget (a different physical quantity) is reported instead. Every number carries a PROVENANCE "
    "tag so policy (600/1000 mSv), physics-limit (LD50/ARS), extrapolation (Dsup) and required-"
    "breakthrough (Deinococcus transplant, upload substrate) are distinguishable at a glance. "
    "Order-of-magnitude: the RBE(LET) grid and clade modifiers are canon-labelled estimates, not a "
    "transport/dose-response simulation."
)
