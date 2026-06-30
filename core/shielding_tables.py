"""Bundled static shielding-coefficient tables for the Phase V `shielding-attenuation`
calculator (`core.thermal.compute_shielding_attenuation`).

Two bundled datasets, isolated here (like ``core.cooling_tables``) so the numbers are
auditable in one place and ``core.thermal`` stays pure logic:

  * ``_XCOM_MU_RHO`` — photon **mass-attenuation coefficients** μ/ρ [cm²/g], transcribed
    from **NIST XCOM / XAAMDI** on a material × reference-energy grid. The photon mode is
    *exact* Lambert–Beer once μ/ρ is correct, so these are the load-bearing numbers; the
    water- and lead-@-1-MeV values are anchor-checked in ``tests/test_thermal.py``.
  * ``_GCR_LAMBDA`` — galactic-cosmic-ray dose-equivalent **attenuation lengths** Λ
    [g/cm²], **order-of-magnitude** literature values (NCRP 153 / NASA HRP). The GCR mode
    is explicitly approximate and carries a secondary-particle-buildup caveat.

These are **transcribed reference data, not analytic fits** — the same "bundled static
data, sourced not fabricated" pattern as ``core.cooling_tables`` and the Kopparapu S_eff
coefficients. Provenance is declared in ``_XCOM_SOURCE`` / ``_GCR_SOURCE`` and surfaced in
every ``shielding-attenuation`` response's ``model_note`` and in ``docs/integration.md``.
"""

# ── Photon mass-attenuation coefficients μ/ρ [cm²/g] (NIST XCOM / XAAMDI) ─────
_XCOM_SOURCE = (
    "NIST XCOM (Berger et al., NIST Standard Reference Database 8) / NIST XAAMDI "
    "(Hubbell & Seltzer 2004); total mass-attenuation coefficient mu/rho [cm^2/g], "
    "with coherent scattering, at the listed photon energies. All cells reconciled "
    "against the live NIST XAAMDI tables on 2026-06-30 (regolith computed from the "
    "elemental Si+O tables via the SiO2 mixture rule)."
)

# Reference photon energies, MeV (nearest-energy lookup; the chosen energy is echoed
# and an exact/nearest flag is returned).
_XCOM_ENERGIES_MEV = (0.1, 0.5, 1.0, 2.0, 5.0, 10.0)

# _XCOM_MU_RHO[material] = {energy_mev: mu_over_rho_cm2_g}.
# All values reconciled against live NIST XAAMDI (2026-06-30):
#   water, polyethylene -> ComTab/{water,polyethylene}.html (compound tables);
#   aluminum/lead/hydrogen/iron -> ElemTab/z{13,82,01,26}.html (element tables).
# `regolith` is an SiO2-dominant silicate analog (a lunar-mare regolith stand-in), pinned
# by COMPUTING the compound coefficient from the NIST elemental Si (z14) + O (z08) tables
# via the additive mixture rule mu/rho = sum_i w_i (mu/rho)_i, with SiO2 mass fractions
# w_Si=28.0855/60.0843=0.46744, w_O=31.9988/60.0843=0.53256; flagged as an approximation.
# `liquid_h2` is elemental hydrogen (Z=1): mu/rho is per-gram and identical to gaseous H,
# so liquefaction changes the per-*cm* shielding (via density) but not these per-gram
# coefficients — see the `_PER_GRAM_NOTE`.
_XCOM_MU_RHO = {
    "water":        {0.1: 0.1707,  0.5: 0.09687, 1.0: 0.07072, 2.0: 0.04942, 5.0: 0.03031, 10.0: 0.02219},
    "polyethylene": {0.1: 0.1719,  0.5: 0.09947, 1.0: 0.07262, 2.0: 0.05064, 5.0: 0.03045, 10.0: 0.02145},
    "aluminum":     {0.1: 0.1704,  0.5: 0.08445, 1.0: 0.06146, 2.0: 0.04324, 5.0: 0.02836, 10.0: 0.02318},
    "regolith":     {0.1: 0.16838, 0.5: 0.08738, 1.0: 0.06367, 2.0: 0.04469, 5.0: 0.02866, 10.0: 0.02263},
    "lead":         {0.1: 5.549,   0.5: 0.1614,  1.0: 0.07102, 2.0: 0.04606, 5.0: 0.04272, 10.0: 0.04972},
    "liquid_h2":    {0.1: 0.2944,  0.5: 0.1729,  1.0: 0.1263,  2.0: 0.08769, 5.0: 0.05049, 10.0: 0.03254},
    "iron":         {0.1: 0.3717,  0.5: 0.08414, 1.0: 0.05995, 2.0: 0.04265, 5.0: 0.03146, 10.0: 0.02994},
}

# `hydrogen` is an accepted alias for `liquid_h2` (same per-gram coefficients).
_MATERIAL_ALIASES = {"hydrogen": "liquid_h2"}

_PER_GRAM_NOTE = (
    "liquid_h2/hydrogen: mu/rho is per-gram (Z=1 has the highest mass-attenuation of any "
    "element) — the best shield by MASS but the worst by VOLUME; the per-cm layer depends "
    "on the (low) density."
)

_REGOLITH_NOTE = (
    "regolith mu/rho is an SiO2-dominant silicate approximation (lunar-mare analog) computed "
    "from the NIST elemental Si+O coefficients via the mixture rule, not a measured regolith "
    "sample; treat as indicative."
)


def lookup_mu_rho(material: str, energy_mev: float):
    """Nearest-energy μ/ρ [cm²/g] for a bundled material.

    Returns ``(mu_rho, chosen_energy_mev, exact)`` or ``None`` if the material is not in
    the bundled grid. ``exact`` is True iff ``energy_mev`` matches a grid energy exactly.
    """
    mat = _MATERIAL_ALIASES.get(material, material)
    grid = _XCOM_MU_RHO.get(mat)
    if grid is None:
        return None
    chosen = min(grid, key=lambda e: abs(e - energy_mev))
    exact = abs(chosen - energy_mev) < 1e-9
    return grid[chosen], chosen, exact


def material_names():
    """The user-facing material choices (bundled materials + aliases), sorted."""
    return sorted(set(_XCOM_MU_RHO) | set(_MATERIAL_ALIASES))


# ── GCR dose-equivalent attenuation lengths Λ [g/cm²] (order-of-magnitude) ────
_GCR_SOURCE = (
    "NCRP Report 153 / NASA Human Research Program space-radiation references; "
    "order-of-magnitude GCR dose-equivalent attenuation length Lambda [g/cm^2]."
)

# Order-of-magnitude only. Hydrogen-rich materials attenuate GCR dose better per g/cm².
_GCR_LAMBDA = {
    "polyethylene": 25.0,
    "water":        28.0,
    "aluminum":     30.0,
    "regolith":     32.0,
}

_GCR_BUILDUP_CAVEAT = (
    "GCR dose behind THIN shielding can RISE before it falls (spallation/secondary "
    "production — a thin shield can be worse than none). This single-exponential is a "
    "high-depth approximation only; order-of-magnitude."
)


def lookup_gcr_lambda(material: str):
    """Bundled GCR attenuation length Λ [g/cm²] for a material, or ``None``."""
    mat = _MATERIAL_ALIASES.get(material, material)
    return _GCR_LAMBDA.get(mat)


def gcr_material_names():
    return sorted(_GCR_LAMBDA)
