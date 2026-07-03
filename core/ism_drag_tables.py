"""Phase AC — bundled ISM / fusion constants for the ISM-drag calculators (isolated static data).

For ``core.ism_drag.compute_magsail`` / ``compute_ramscoop`` (Group K of the Packet-16 STL
work). Isolated in its own module (like ``core.propulsion_tables`` / ``core.shielding_tables``)
because these numbers are **present-day / first-principles ancestors, not 2,500-yr ceilings** —
the *physics* is durable (magnetopause pressure balance ``B²/2μ₀ = kρv²``; momentum flux
``ṁ = ρvA``; the net-thrust inequality ``v_e > v``); the *parameter values* (achievable coil
performance, fusion burn efficiency, the drag/standoff coefficients) are calibrated ancestors the
setting improves upon, and every one is caller-overridable. Per the Mature-Technology Assumption,
keep the two layers separate in packet prose.

The **ISM density itself is a canon/research input** — the tools take ``n`` as a parameter (like
``bioregen-area`` takes PAR); they must not re-derive it. The defaults below are flagged to the
Local-Interstellar-Environment research packet, not embedded models.

Value provenance (web + sibling-repo research, confirmed 2026-07-02):

  * Drag coefficient C_d = 1.0 — Zubrin & Andrews' explicit convention: "a drag coefficient of
    unity for the area defined by the magsail's magnetospheric boundary" (Wikipedia *Magnetic
    sail*; Andrews & Zubrin, "Magnetic Sails and Interstellar Travel", JBIS 1990/1991).
  * Standoff coefficient k = 1.0 — the simple magnetopause pressure balance B_dipole²/2μ₀ = ρv²
    (the dipole *axial* field balancing ram pressure). The compressed-to-dipole field ratio at the
    sub-solar point is f = 2 (dipole vs an infinite conducting plane) / 2.44 (the Chapman-Ferraro
    spherical problem); a caller wanting the compressed-field convention sets --standoff-coeff
    (Samsonov 2020, GRL 47 e2019GL086474; standard magnetospheric physics). k=1 reproduces the
    request's R_mp ≈ 100 km acceptance anchor.
  * Fusion mass→energy fractions f — p-p chain 0.71% (= 26.73 MeV / 4·938.27 MeV; Atomic Rockets /
    Energy Education: "the p-p chain to ⁴He is 0.7% efficient", ~72% of the 0.97% Fe-56 ceiling);
    CNO nets the same 4H→⁴He (0.71%); D-T 0.375% (mass defect 0.018882 / 5.029053 AMU). D-D is
    bundled at 0.38% — the *catalyzed* D-D cycle (≈ D-T scale, consistent with
    core/propulsion_tables.py's fusion-dt 0.38%); a *single* D-D reaction converts only ~0.10%
    (avg 3.65 MeV / 3751 MeV). NOTE: the request spec quoted D-D ≈ 0.43%, which matches neither the
    single-reaction nor the standard catalyzed-cycle value — reconciled DOWN to 0.38% here; flag on
    shipment. The load-bearing fuel for a real ISM ramjet is p-p (the ISM is >90% protons), so the
    drive/brake verdict is unaffected by the D-D choice.
  * Directed-exhaust efficiency η default 0.1 (low) — the fraction of fusion energy delivered as
    directed exhaust KE. Ideal η=1 gives p-p v_e = √(2·0.0071)·c ≈ 0.119c (the request's "p-p ideal
    ≈ 0.12c"); Zubrin & Andrews 1985 assumed a realistic ~100 km/s exhaust vs collected solar-wind
    ions ~500 km/s, so drag > thrust — the "brake not drive" result. The low η encodes that realism.
  * Mean ISM ion mass 1.3 amu — H+He mix with He/H ≈ 0.1 by number → (1 + 0.1·4)/1.1 ≈ 1.27 amu
    (sibling Local-Interstellar-Environment packet). Default n = 0.1 cm⁻³ = the Local Interstellar
    Cloud n(H I) (0.03–0.2 directional; the medium the Sun is actually in); the Local Bubble hot
    interior is ~0.005 cm⁻³.

**Ionization caveat (baked into every output):** the real Local Interstellar Cloud is only ~22% H /
~39% He ionized (LIE packet claim-map C5, Established), and a magsail/ramscoop couples to *charged*
particles only. Assuming full ionization (boundary guard #2) therefore overestimates the
magnetically-interacting density by ~4× in the LIC — a caller who needs accuracy should pass the
*ion* number density as --ism-density-cm3 rather than the total n.
"""

from core.equations import _C_MS

_C_KMS = _C_MS / 1000.0

# ── ISM defaults (Local-Interstellar-Environment packet; overridable) ────────
_DEFAULT_N_CM3        = 0.1    # Local Interstellar Cloud n(H I); LB interior ~0.005
_MEAN_ION_MASS_AMU    = 1.3    # H+He mix, He/H ≈ 0.1 → ≈ 1.27 amu

# ── magsail / scoop coefficients (order-unity; overridable) ──────────────────
_STANDOFF_COEFF_K     = 1.0    # B_dipole²/2μ₀ = k·ρv²  (compressed factor f=2 / 2.44 — see header)
_DRAG_COEFF_CD        = 1.0    # Zubrin & Andrews: unity over the magnetospheric boundary area

# ── fusion mass→energy fractions f and default directed-exhaust efficiency ───
# fuel key -> {f (mass→energy fraction), note}. All ideal/first-principles; MTA-movable.
_FUSION = {
    "pp": {
        "f": 0.0071,
        "note": "proton-proton chain 4H→⁴He, 0.71% mass→energy (the physically load-bearing "
                "fuel — the ISM is >90% protons).",
    },
    "cno": {
        "f": 0.0071,
        "note": "CNO cycle — nets the same 4H→⁴He as the p-p chain, 0.71% mass→energy.",
    },
    "dd": {
        "f": 0.0038,
        "note": "catalyzed D-D cycle ≈ 0.38% mass→energy (≈ D-T scale; consistent with the "
                "propulsion-tables fusion-dt preset). A single D-D reaction is only ~0.10%. "
                "Reconciled down from the request's stated 0.43% (matches neither) — flag on "
                "shipment. D-D requires carried deuterium; not the native ISM-ramjet fuel.",
    },
}

_DEFAULT_FUSION_EFFICIENCY = 0.1   # directed-exhaust fraction η (low; ideal η=1 → pp v_e ≈ 0.12c)

_SOURCES = (
    "Coefficients/fractions confirmed 2026-07-02: drag C_d=1.0 (Zubrin & Andrews explicit, "
    "Wikipedia Magnetic sail); standoff k=1.0 simple pressure balance (compressed factor f=2/2.44, "
    "Samsonov 2020 GRL 47 e2019GL086474); fusion p-p/CNO 0.71%, D-T 0.375%, D-D catalyzed 0.38% "
    "(Atomic Rockets fusionfuel; Energy Education); mean ISM ion mass 1.3 amu and default n=0.1 "
    "cm⁻³ (Local Interstellar Cloud) from the sibling Local-Interstellar-Environment packet. All "
    "values are present-day / first-principles ancestors under the Mature-Technology Assumption — "
    "every one is caller-overridable. ISM density is a parameter, never re-derived."
)

_IONIZATION_NOTE = (
    "The bundled n assumes a fully-ionized medium (magsail/ramscoop couple to charged particles "
    "only). The real Local Interstellar Cloud is only ~22% H / ~39% He ionized, so full ionization "
    "overestimates the magnetically-interacting density by ~4× — pass the ion number density as "
    "--ism-density-cm3 if accuracy matters. ISM density itself is a research/canon input, not "
    "re-derived here."
)

_MODEL_NOTE_MAGSAIL = (
    "Magsail braking. The coil-pair anchor uses the EXACT on-axis current-loop field "
    "B(z) = μ₀·I·R²/(2(R²+z²)^{3/2}), inverting the pressure balance B(R_mp)²/2μ₀ = k·ρv² "
    "algebraically for R_mp; the moment-only anchor (no geometry) keeps the far-field dipole "
    "R_mp = [μ₀·m_dip²/(8π²·k·ρv²)]^(1/6). Both are echoed (magnetopause_radius_km vs "
    "magnetopause_radius_farfield_km); they converge once R_mp ≳ 3·R_coil. Drag "
    "F = C_d·½·ρv²·π·R_mp²; because R_mp ∝ v^(−1/3) in the far field, F_drag ∝ v^(4/3) (fast "
    "initial braking, long tail). For CONSTANT ISM the closed-form stopping distance/time from the "
    "single v^(4/3) drag law are EXACT (not an estimate); a real varying-ISM multi-leg trajectory "
    "optimisation is a separate consuming tool. Only ions couple — ionization_fraction scales ρ. "
    "Momentum/energy balance only — no coil mass / quench / plasma engineering (Pkt 25). " + _SOURCES
)

_MODEL_NOTE_RAMSCOOP = (
    "Bussard ramjet drag-vs-thrust: collected mass flux ṁ = ρ·v·A_mp over the magnetopause area; "
    "reaction thrust ṁ·v_e with ideal fusion exhaust v_e = √(2·η·f·c²); collecting the stream "
    "costs ṁ·v and the un-collected ISM costs magnetic drag C_d·½ρv²A_mp. Net F = ṁ(v_e − v) − "
    "F_drag, so net thrust needs at minimum v_e > v and the drag makes the real threshold stricter "
    "— above the crossover velocity the ramjet is a net BRAKE, not a drive (Zubrin & Andrews 1985). "
    "The v_e > v inequality is durable; present-day fusion η and ISM density are MTA-movable "
    "ancestors. Momentum/energy balance only — no reactor/coil/plasma engineering (Pkt 25). " + _SOURCES
)
