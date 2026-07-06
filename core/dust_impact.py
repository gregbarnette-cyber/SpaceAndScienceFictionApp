"""Phase AD (C3) — hypervelocity dust / ISM-grain impact energetics.

A ``query.py``-only, pure-math, self-validating (Phase-H/P contract) calculator for what a
single interstellar dust grain does to a relativistic starship when they meet: kinetic energy,
TNT-equivalent, momentum, and — over a supplied ISM column — the cumulative impact count and
energy fluence. It is the *energetics* companion to the magnetic ``magsail``/``ramscoop``
interaction (which handle momentum exchange with the ionised ISM) and to the ``dust-*`` column
extinction subcommands (which handle photometric absorption).

Physics (durable):
  * grain mass ``m = (4/3)π r³ ρ`` (or supplied explicitly);
  * impact energy — Newtonian ``½ m v²`` at low β, switching to the relativistic
    ``(γ−1) m c²`` once ``β > 0.1`` (where the correction exceeds ~1 %);
  * momentum ``m v`` → ``γ m v`` across the same switch;
  * TNT-equivalent ``E / 4.184e6`` kg (1 kg TNT ≡ 4.184 MJ);
  * cumulative impacts ``N = n · A · L`` over a path of length L and frontal area A through
    number density n, and energy fluence ``N·E / A`` (= n·L·E).

**Penetration depth is deliberately NOT computed here** — it needs material-specific stopping
data and is handed off to the Packet-13 shielding tools (``shielding-attenuation`` for the
mass/CSDA side, ``radiator-area`` for the thermal side). See ``penetration_handoff_note``.

Reuses ``_C_MS`` / ``_SEC_PER_YEAR`` from ``core.equations``. No network, no DB, no RNG, no time.
Self-validating: bad input returns a curated ``{"error": str}``.
"""

import math

from core.equations import _C_MS, _LY_M, _TNT_J_PER_KG  # shared constants (P4.5)
from core.equations import _resolve_velocity as _resolve_velocity_shared
_REL_BETA_THRESHOLD = 0.1           # β above which the relativistic KE/momentum form is used

_PENETRATION_HANDOFF_NOTE = (
    "Penetration depth / spallation / cratering is NOT computed here — it needs "
    "material-specific stopping data. For the shielding response hand off to the Packet-13 "
    "tools: 'shielding-attenuation' (mass attenuation / CSDA range for the deposited particle "
    "cascade) and 'radiator-area' (dumping the deposited heat). This tool sizes the incident "
    "energy/momentum only."
)

_MODEL_NOTE = (
    "Grain-impact energetics: m = (4/3)π r³ ρ; kinetic energy ½ m v² (Newtonian) switching to "
    "(γ−1) m c² once β > 0.1 (the 'relativistic' flag); momentum m v → γ m v across the same "
    "switch; TNT-equivalent E / 4.184e6 kg (1 kg TNT ≡ 4.184 MJ). Cumulative impacts N = n·A·L "
    "and energy fluence N·E/A over a supplied ISM column. Point-particle deposition only — no "
    "penetration/cratering (see penetration_handoff_note), no charge/plasma coupling, no grain "
    "fragmentation. A first-cut hazard scale, not a hydrocode."
)


def _resolve_velocity(velocity_kms, beta):
    """Return (v_ms, velocity_kms, beta) or a {"error"} dict. Exactly one anchor required
    (velocity > 0). Thin wrapper over the canonical ``equations._resolve_velocity`` (P4.3)."""
    return _resolve_velocity_shared(velocity_kms, beta, allow_zero=False)


def compute_dust_impact(grain_radius_um=None, grain_density_kgm3=None, grain_mass_kg=None,
                        velocity_kms=None, beta=None, dust_density_m3=None,
                        frontal_area_m2=None, path_length_ly=None):
    """Single-grain impact energy / momentum / TNT-equivalent + optional cumulative fluence.

    Grain-mass anchor: (``grain_radius_um`` + ``grain_density_kgm3``) OR ``grain_mass_kg``.
    Velocity anchor: ``velocity_kms`` OR ``beta``. Cumulative-fluence set (all three or none):
    ``dust_density_m3`` + ``frontal_area_m2`` + ``path_length_ly``.
    """
    # ── grain-mass anchor: (radius + density) XOR explicit mass ──
    have_geom = grain_radius_um is not None or grain_density_kgm3 is not None
    have_mass = grain_mass_kg is not None
    if have_geom + have_mass != 1:
        return {"error": "Provide exactly one grain anchor: (--grain-radius-um + "
                         "--grain-density-kgm3) or --grain-mass-kg."}
    if have_mass:
        if grain_mass_kg <= 0:
            return {"error": "grain_mass_kg must be > 0."}
        m_kg = grain_mass_kg
    else:
        if grain_radius_um is None or grain_density_kgm3 is None:
            return {"error": "Provide both --grain-radius-um and --grain-density-kgm3 for the "
                             "geometry anchor."}
        if grain_radius_um <= 0:
            return {"error": "grain_radius_um must be > 0."}
        if grain_density_kgm3 <= 0:
            return {"error": "grain_density_kgm3 must be > 0."}
        radius_m = grain_radius_um * 1e-6
        m_kg = (4.0 / 3.0) * math.pi * radius_m ** 3 * grain_density_kgm3

    vel = _resolve_velocity(velocity_kms, beta)
    if isinstance(vel, dict):
        return vel
    v_ms, velocity_kms_out, beta_out = vel

    # ── cumulative-fluence set: all three or none ──
    cum_args = (dust_density_m3, frontal_area_m2, path_length_ly)
    n_cum = sum(a is not None for a in cum_args)
    if n_cum not in (0, 3):
        return {"error": "For the cumulative fluence provide all of --dust-density-m3, "
                         "--frontal-area-m2, and --path-length-ly, or none."}
    if n_cum == 3:
        if dust_density_m3 <= 0:
            return {"error": "dust_density_m3 must be > 0."}
        if frontal_area_m2 <= 0:
            return {"error": "frontal_area_m2 must be > 0."}
        if path_length_ly <= 0:
            return {"error": "path_length_ly must be > 0."}

    # ── energetics: relativistic once β > threshold ──
    relativistic = beta_out > _REL_BETA_THRESHOLD
    if relativistic:
        gamma = 1.0 / math.sqrt(1.0 - beta_out ** 2)
        energy_j = (gamma - 1.0) * m_kg * _C_MS ** 2
        momentum_kgms = gamma * m_kg * v_ms
    else:
        gamma = 1.0
        energy_j = 0.5 * m_kg * v_ms ** 2
        momentum_kgms = m_kg * v_ms

    energy_tnt_kg = energy_j / _TNT_J_PER_KG

    impacts_total = energy_fluence_j_m2 = None
    if n_cum == 3:
        path_m = path_length_ly * _LY_M
        impacts_total = dust_density_m3 * frontal_area_m2 * path_m
        energy_fluence_j_m2 = impacts_total * energy_j / frontal_area_m2

    return {
        "grain_mass_kg": m_kg,
        "grain_radius_um": grain_radius_um,
        "grain_density_kgm3": grain_density_kgm3,
        "velocity_kms": velocity_kms_out,
        "beta": beta_out,
        "relativistic": relativistic,
        "lorentz_factor": gamma,
        "impact_energy_j": energy_j,
        "impact_energy_tnt_kg": energy_tnt_kg,
        "momentum_kgms": momentum_kgms,
        "dust_density_m3": dust_density_m3,
        "frontal_area_m2": frontal_area_m2,
        "path_length_ly": path_length_ly,
        "impacts_total": impacts_total,
        "energy_fluence_j_m2": energy_fluence_j_m2,
        "penetration_handoff_note": _PENETRATION_HANDOFF_NOTE,
        "model_note": _MODEL_NOTE,
    }
