"""Phase Y — bundled ideal fuel exhaust-velocity presets (isolated static data).

For ``core.propulsion.compute_rocket_equation``. Isolated in its own module (like
``core.shielding_tables`` / ``core.spin_tables``) because these numbers are
**present-day / near-term ancestors, not 2,500-yr ceilings** — the rocket-equation
*physics* (Tsiolkovsky) is durable; the exhaust velocities are calibrated ancestors the
setting improves upon, and every one is caller-overridable (``--exhaust-velocity-kms`` /
``--isp-s``). Per the Mature-Technology Assumption, keep the two layers separate.

Each value is an **ideal** exhaust velocity — a real drive reaches a fraction of it
(imperfect burn fraction, non-ideal directed exhaust, nozzle/divergence losses). Marked
so in every ``note``.

**Value provenance / a documented tension to confirm at shipment (see completed_plans/PHASE_Y_PLAN.md §9):**
the combined request quotes an *ideal* D-T band of ~0.05–0.09 c (from the ~0.4 % mass→energy
of D-T fusion), but its own **acceptance anchor** pins ``fusion-dt`` at *v_e ≈ 0.03 c* → the
"marginal fusion generation ship" result (MR ≈ 28 flyby / ~800 rendezvous at β 0.1). The
testable anchor wins: ``fusion-dt`` is bundled at **0.03 c** as a conservative *effective*
exhaust velocity (below the ideal band once realistic burn/directionality losses are folded
in), reproducing the packet's scoping conclusion. Flag back to the requester on shipment.
"""

from core.equations import _C_KMS   # speed of light, km/s (≈ 299 792.458); shared (P4.5)

# fuel key -> {v_e_kms (ideal exhaust velocity), note}. All ideal; MTA-movable.
_FUELS = {
    "chemical": {
        "v_e_kms": 4.4,
        "note": "chemical (H2/O2, ideal ~4.4 km/s) — mature; the real floor.",
    },
    "fission-thermal": {
        "v_e_kms": 9.0,
        "note": "solid-core nuclear-thermal (NTR) ideal ~9 km/s; ideal fission-FRAGMENT "
                "exhaust is far higher — a separate, less-developed drive.",
    },
    "fusion-dt": {
        "v_e_kms": 0.03 * _C_KMS,          # ≈ 8 993.8 km/s (0.03 c) — see module docstring
        "note": "D-T fusion, bundled at an effective v_e ≈ 0.03 c (the request's acceptance "
                "anchor; ideal D-T is ~0.05–0.09 c but realistic burn fraction + directed-"
                "exhaust losses drop the effective value). Yields the 'marginal generation "
                "ship' result. Ideal/effective — MTA-movable.",
    },
    "fusion-catalyzed": {
        "v_e_kms": 0.10 * _C_KMS,          # ≈ 29 979 km/s (0.10 c)
        "note": "advanced / catalyzed fusion, higher effective burn fraction — extrapolated, "
                "no direct acceptance anchor. Ideal — MTA-movable.",
    },
    "antimatter": {
        "v_e_kms": 0.30 * _C_KMS,          # ≈ 89 937.7 km/s (0.30 c)
        "note": "antimatter-heated / -catalyzed exhaust, up to ~0.3 c+ ideal — extrapolated. "
                "MTA-movable.",
    },
}

# Fuel v_e figures confirmed 2026-07-02 against the references below (WebSearch, first-principles):
#   chemical        ~4.4 km/s  — H2/O2, Isp ~450 s vac × g₀; NTR is quoted as ~2× this Isp.
#   fission-thermal  ~9 km/s   — NERVA NRX Isp 825 s → 8.1 km/s; advanced NTR 850–1000 s →
#                                8.3–9.8 km/s (Wikipedia NERVA / Nuclear thermal rocket; NASA
#                                NTP overview NTRS 20190033337). Bundled 9.0 = the ideal/upper end.
#   fusion-dt        0.03c eff. — D-T releases 17.6 MeV/reaction, 0.38% (≈38/10000) of reactant
#                                mass → energy (Wikipedia D–T fusion; ITER). If ALL that energy went
#                                to directed exhaust KE the ideal ceiling is v_e = c·√(2·0.0038)
#                                ≈ 0.087c (the request's "~0.05–0.09c ideal" band); realistic burn
#                                fraction + undirected exhaust + inert propellant drop the EFFECTIVE
#                                value well below it, so 0.03c (the request's acceptance anchor) is
#                                bundled. See the module docstring for the ideal-vs-effective note.
_SOURCES = (
    "Tsiolkovsky & the relativistic rocket equation (standard astronautics; relativistic form "
    "MR = exp((c/v_e)·atanh β)). Fuel v_e: chemical H2/O2 (Isp ~450 s → 4.4 km/s); fission-thermal "
    "NERVA/NTR (Isp 825–1000 s → 8.1–9.8 km/s; Wikipedia NERVA & Nuclear thermal rocket, NASA NTP "
    "NTRS 20190033337); D-T fusion 17.6 MeV / 0.38% mass→energy → ideal v_e ≈ 0.087c ceiling "
    "(Wikipedia D–T fusion, ITER), bundled at 0.03c EFFECTIVE. Confirmed 2026-07-02. All values are "
    "IDEAL/effective exhaust velocities (real drives reach a fraction) and present-day/near-term "
    "ancestors under the Mature-Technology Assumption — every one is caller-overridable."
)

_MODEL_NOTE = (
    "Rocket-equation energetics: classical MR = exp(Δv/v_e); relativistic (β anchor) "
    "MR = exp((c/v_e)·atanh β) (photon rocket v_e=c → MR = √((1+β)/(1−β))). The input "
    "--mass-ratio (and any payload mass budget) is the SINGLE-BURN ratio; --legs raises it "
    "(flyby MR¹, rendezvous MR², round-trip MR⁴) and drives propellant_fraction = 1 − 1/MR_total. "
    "Bundled fuel exhaust velocities are IDEAL and present-day/near-term ancestors — real drives "
    "reach a fraction; every value is caller-overridable (--exhaust-velocity-kms / --isp-s). "
    "See core/propulsion_tables.py for per-fuel provenance (incl. the fusion-dt 0.03 c anchor note). "
    "Full propulsion taxonomy defers to Packet 25; this is the STL scoping envelope. " + _SOURCES
)
