"""Phase AL (Group R) — energy-storage floor-physics calculators (Packet 27).

Two pure-math, self-validating (Phase-H/P contract) ``query.py``-only calculators for the sibling
``scifiWorldBuilding-Claude`` repo — the two energy-storage ceilings that ARE repeal-proof floor
laws (battery/chemical/thermal specific energies, where no clean floor exists, live in the bundled
``core.power_tables._STORAGE`` table instead):

  * ``compute_flywheel_storage`` (R8) — material-strength specific-energy ceiling e = K·σ/ρ.
  * ``compute_smes_storage``     (R9) — magnetic-field energy density u = B²/2µ₀, plus the
    structure-limited specific energy (same σ/ρ family as R8 — the magnetic pressure must be held).

Both are strength-limited at the per-kg level by the SAME σ/ρ ceiling — the flywheel rim and the
SMES coil structure obey the same materials wall (ties to the materials packet and the ``spin-stress``
σ values). No network, no DB, no RNG, no time, no numpy. σ/ρ are MTA-movable, caller-supplied.
"""

from core.equations import _MU_0


# ── R8 — flywheel specific-energy ceiling ────────────────────────────────────

def compute_flywheel_storage(tensile_strength_pa=None, density_kgm3=None,
                             shape_factor=0.5, mass_kg=None):
    """Flywheel specific-energy ceiling from material strength.

    ``e_specific = K·σ/ρ`` [J/kg], the material-strength wall a rotating mass storage cannot beat
    (the same σ ceiling as a rotating-habitat rim — MTA-movable, ties to the materials packet). K is
    the shape factor: 0.3 (thin rim) → 1.0 (constant-stress disk); default 0.5.
    """
    if tensile_strength_pa is None or tensile_strength_pa <= 0:
        return {"error": "tensile_strength_pa must be > 0."}
    if density_kgm3 is None or density_kgm3 <= 0:
        return {"error": "density_kgm3 must be > 0."}
    if not (0.0 < shape_factor <= 1.0):
        return {"error": "shape_factor must be in (0, 1] (0.3 thin rim → 1.0 constant-stress disk)."}
    if mass_kg is not None and mass_kg <= 0:
        return {"error": "mass_kg must be > 0."}

    e_specific = shape_factor * tensile_strength_pa / density_kgm3
    stored_energy_j = e_specific * mass_kg if mass_kg is not None else None

    return {
        "specific_energy_j_kg": e_specific,
        "specific_energy_wh_kg": e_specific / 3600.0,
        "stored_energy_j": stored_energy_j,
        "shape_factor": shape_factor,
        "tensile_strength_pa": tensile_strength_pa,
        "density_kgm3": density_kgm3,
        "mass_kg": mass_kg,
        "model_note": ("Flywheel specific-energy ceiling e = K·σ/ρ [J/kg]: the material-strength "
                       "wall (identical to a rotating-habitat rim's σ ceiling — MTA-movable, "
                       "materials-packet-linked). K = 0.3 (thin rim) → 1.0 (constant-stress disk). "
                       "Ideal ancestor; a real rotor reaches a fraction (safety margin, hub mass, "
                       "fatigue). σ and ρ are caller-supplied."),
    }


# ── R9 — SMES magnetic energy density + structure-limited specific energy ────

def compute_smes_storage(field_t=None, critical_field_t=None, tensile_strength_pa=None,
                         density_kgm3=None, volume_m3=None):
    """Superconducting magnetic energy storage — volumetric + structure-limited specific energy.

    Volumetric ``u = B²/(2µ₀)`` [J/m³]. **Physics catch:** the magnetic pressure B²/2µ₀ must be
    held by structure, so the *specific* (per-kg) energy is *again* strength-limited ``≈ σ/ρ`` —
    the same family as the flywheel, NOT the volumetric figure. Both are reported; ``B > B_c`` is
    flagged (a superconductor quenches above its critical field).
    """
    if field_t is None or field_t <= 0:
        return {"error": "field_t must be > 0."}
    if critical_field_t is not None and critical_field_t <= 0:
        return {"error": "critical_field_t must be > 0."}
    if volume_m3 is not None and volume_m3 <= 0:
        return {"error": "volume_m3 must be > 0."}
    # σ and ρ come as a pair for the specific-energy branch.
    if (tensile_strength_pa is None) != (density_kgm3 is None):
        return {"error": "Provide both tensile_strength_pa and density_kgm3 for the specific-energy "
                         "branch, or neither."}
    if tensile_strength_pa is not None and tensile_strength_pa <= 0:
        return {"error": "tensile_strength_pa must be > 0."}
    if density_kgm3 is not None and density_kgm3 <= 0:
        return {"error": "density_kgm3 must be > 0."}

    energy_density = field_t ** 2 / (2.0 * _MU_0)
    stored_energy_j = energy_density * volume_m3 if volume_m3 is not None else None
    specific_energy = (tensile_strength_pa / density_kgm3
                       if tensile_strength_pa is not None else None)
    critical_field_exceeded = (field_t > critical_field_t
                               if critical_field_t is not None else None)

    return {
        "energy_density_j_m3": energy_density,
        "stored_energy_j": stored_energy_j,
        "specific_energy_j_kg": specific_energy,
        "field_t": field_t,
        "critical_field_t": critical_field_t,
        "critical_field_exceeded": critical_field_exceeded,
        "volume_m3": volume_m3,
        "model_note": ("SMES volumetric energy density u = B²/2µ₀ [J/m³]. Physics catch: the "
                       "magnetic pressure B²/2µ₀ must be reacted by structure, so the per-kg "
                       "(specific) energy is strength-limited ≈ σ/ρ — the SAME materials wall as a "
                       "flywheel, not the volumetric figure. critical_field_exceeded flags B > B_c "
                       "(a superconductor quenches above its critical field). Ideal; σ/ρ and B_c "
                       "are caller-supplied / MTA-movable."),
    }
