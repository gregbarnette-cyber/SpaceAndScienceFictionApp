"""Phase AL (Group R) — bundled power-storage / reactor-specific-power tables (Packet 27).

Two bundled tables surfaced as thin ``query.py`` subcommands (the ``main-sequence`` / ``substellar``
pattern — a subcommand whose job is to hand back curated rows), isolated from any calculator logic
(like ``core.propulsion_tables`` / ``core.shielding_tables``) and golden-pinned in tests:

  * ``_STORAGE`` (T1 ``energy-storage``) — battery/chemical/thermal specific energies where NO clean
    floor law exists (the two that DO — flywheel σ/ρ, SMES B²/2µ₀ — are calculators in
    ``core.energy_storage``; the nuclear/antimatter ceilings come free from ``f·c²``).
  * ``_REACTOR_SPECIFIC_POWER`` (T2 ``reactor-power``) — the engineering α = P/m [kW/kg] for
    "PW-scale field power"; NO floor-physics law, so a table + a mandatory thermal pointer.

Common contract: no ``--class`` → all rows; ``--class NAME`` → the single row; ``--override-*``
replaces a value with the caller number and echoes the substitution; every row carries a
``source_tag`` + a curated ``note``; unknown class → curated ``{"error"}`` listing valid keys (the
``_FUSION``/``_FIELD_FUEL`` error idiom). All rows are "transcribed, not fitted", MTA-movable,
caller-overridable. Load-bearing values are **[pin @ open]** illustrative anchors, flagged in
``source_tag`` — not verified promotions. No network/DB/RNG/time/numpy.
"""

# ── T1 — energy-storage specific energies (J/kg primary; [pin @ open]) ───────
_STORAGE = {
    "li-ion": {
        "specific_energy_j_kg": 1.0e6,
        "volumetric_wh_l": 700.0,
        "round_trip_efficiency": 0.90,
        "leak_note": "self-discharge ~1–5 %/month.",
        "source_tag": "[pin @ open] — ~0.25 MJ/kg current cells → ~1 MJ/kg advanced ceiling (bundled).",
        "note": "Li-ion rechargeable; bundled at the advanced ceiling. MTA-movable via --override-wh-kg.",
    },
    "supercapacitor": {
        "specific_energy_j_kg": 5.0e4,
        "volumetric_wh_l": 10.0,
        "round_trip_efficiency": 0.95,
        "leak_note": "high self-discharge (hours–days); best for high-power pulse buffering.",
        "source_tag": "[pin @ open] — ~14 Wh/kg class.",
        "note": "Electrostatic double-layer; high power density, low energy density.",
    },
    "chemical-fuel": {
        "specific_energy_j_kg": 1.3e7,
        "volumetric_wh_l": None,
        "round_trip_efficiency": None,
        "leak_note": "one-way (combustion), not rechargeable; boil-off for cryogens.",
        "source_tag": "[pin @ open] — H₂/O₂ stoichiometric ~13 MJ/kg (CH₄/O₂ similar).",
        "note": "Chemical fuel+oxidizer specific energy (one-way). Nuclear/antimatter ceilings are "
                "NOT here — they come free from f·c² (see core.ism_drag_tables _FISSION/_FUSION, "
                "core.metric_drive _FIELD_FUEL): U-235 ≈ 8.2×10¹³ J/kg, antimatter c² ≈ 9×10¹⁶ J/kg.",
    },
    "sensible-thermal": {
        "specific_energy_j_kg": 4.2e5,
        "volumetric_wh_l": None,
        "round_trip_efficiency": 0.70,
        "leak_note": "conductive/radiative loss over time; needs insulation.",
        "source_tag": "[pin @ open] — example: water c_p 4186 J/kg·K × 100 K ΔT.",
        "note": "Sensible heat E = m·c_p·ΔT — material/ΔT-dependent; use the compute branch "
                "(--mass-kg --specific-heat-jkgk --delta-t-k) for a real sizing.",
    },
    "latent-thermal": {
        "specific_energy_j_kg": 3.3e5,
        "volumetric_wh_l": None,
        "round_trip_efficiency": 0.80,
        "leak_note": "phase-change material; loss over time without insulation.",
        "source_tag": "[pin @ open] — example: water fusion latent heat 334 kJ/kg.",
        "note": "Latent heat E = m·L (phase change) — material-dependent; use the compute branch "
                "(--mass-kg --latent-heat-jkg) for a real sizing.",
    },
    "gravitational": {
        "specific_energy_j_kg": 9.81e2,
        "volumetric_wh_l": None,
        "round_trip_efficiency": 0.80,
        "leak_note": "essentially no leakage (potential energy); sited/geography-bound.",
        "source_tag": "[pin @ open] — example: 100 m head, e = g·h ≈ 981 J/kg.",
        "note": "Gravitational (pumped hydro / mass-on-height) e = g·h — very low specific energy, "
                "cheap and lossless at scale.",
    },
}

# ── T2 — reactor specific power α = P/m [kW/kg] ([pin @ open]) ────────────────
_REACTOR_SPECIFIC_POWER = {
    "fission": {
        "specific_power_kw_kg": 0.03,
        "source_tag": "[pin @ open] — SP-100 space reactor ~0.03 kW/kg; advanced concepts higher.",
        "note": "Space fission reactor. Bundled at the SP-100 ancestor; MTA-movable upward.",
    },
    "fusion": {
        "specific_power_kw_kg": 5.0,
        "source_tag": "[pin @ open] — projected mature fusion ~1–10 kW/kg.",
        "note": "Projected mature fusion power plant (mid of the ~1–10 kW/kg band).",
    },
    "antimatter": {
        "specific_power_kw_kg": 100.0,
        "source_tag": "[pin @ open] — antimatter beamed-core (Frisbee estimates); highly speculative.",
        "note": "Antimatter beamed-core reactor; the most aggressive [pin] — treat as an upper "
                "extrapolation, not a verified figure.",
    },
    "rtg": {
        "specific_power_kw_kg": 0.005,
        "source_tag": "[pin @ open] — radioisotope thermoelectric ~5 W/kg.",
        "note": "RTG (radioisotope). Low specific power, decades-long lifetime, no moving parts.",
    },
    "solar-thermal": {
        "specific_power_kw_kg": 0.1,
        "source_tag": "[pin @ open] — solar-thermal/PV at ~1 AU; falls as 1/r² outbound.",
        "note": "Solar collector at ~1 AU; distance-dependent (∝ 1/r²) — a 1-AU ancestor.",
    },
}

_THERMAL_POINTER = (
    "The real binding ceiling at high P is THERMAL, not core mass: a reactor emitting P W rejects "
    "P·(1−η) as heat and the radiator mass dominates the reactor mass. Size the plant by composing "
    "reactor-net-power / waste-heat → radiator-area — specific power (W/kg) is deliberately a table "
    "+ this pointer, not a floor-physics calculator."
)


def _valid_keys(table):
    return ", ".join(sorted(table))


def compute_energy_storage(class_name=None, override_wh_kg=None, mass_kg=None,
                           specific_heat_jkgk=None, delta_t_k=None, latent_heat_jkg=None):
    """T1 — energy-storage lookup (+ optional sensible/latent compute branch).

    No class → all rows. A class → that row (with --override-wh-kg substituted + echoed). The
    sensible/latent compute branch (``mass_kg`` + ``specific_heat_jkgk`` + ``delta_t_k`` → m·c_p·ΔT,
    or ``mass_kg`` + ``latent_heat_jkg`` → m·L) adds ``stored_energy_j``.
    """
    # ── compute branch (independent of the lookup) ──
    stored_energy_j = None
    compute_args = [mass_kg, specific_heat_jkgk, delta_t_k, latent_heat_jkg]
    if any(v is not None for v in compute_args):
        if mass_kg is None or mass_kg <= 0:
            return {"error": "the compute branch needs mass_kg > 0."}
        sensible = specific_heat_jkgk is not None or delta_t_k is not None
        latent = latent_heat_jkg is not None
        if sensible and latent:
            return {"error": "Provide either the sensible pair (specific_heat_jkgk + delta_t_k) or "
                             "latent_heat_jkg, not both."}
        if sensible:
            if specific_heat_jkgk is None or delta_t_k is None:
                return {"error": "sensible compute needs both specific_heat_jkgk and delta_t_k."}
            if specific_heat_jkgk <= 0 or delta_t_k <= 0:
                return {"error": "specific_heat_jkgk and delta_t_k must be > 0."}
            stored_energy_j = mass_kg * specific_heat_jkgk * delta_t_k
        elif latent:
            if latent_heat_jkg <= 0:
                return {"error": "latent_heat_jkg must be > 0."}
            stored_energy_j = mass_kg * latent_heat_jkg
        else:
            return {"error": "the compute branch needs specific_heat_jkgk + delta_t_k (sensible) or "
                             "latent_heat_jkg (latent)."}

    def _row(name):
        r = dict(_STORAGE[name])
        j_kg = r["specific_energy_j_kg"]
        if override_wh_kg is not None:
            if override_wh_kg <= 0:
                return {"error": "override_wh_kg must be > 0."}
            j_kg = override_wh_kg * 3600.0
            r["overridden"] = {"specific_energy_wh_kg": override_wh_kg}
        r["class"] = name
        r["specific_energy_j_kg"] = j_kg
        r["specific_energy_wh_kg"] = j_kg / 3600.0
        if stored_energy_j is not None:
            r["stored_energy_j"] = stored_energy_j
        return r

    if class_name is not None:
        if class_name not in _STORAGE:
            return {"error": f"Unknown energy-storage class '{class_name}'. "
                             f"Valid: {_valid_keys(_STORAGE)}."}
        row = _row(class_name)
        return row
    # no class → all rows
    rows = []
    for name in _STORAGE:
        r = _row(name)
        if "error" in r:
            return r
        rows.append(r)
    out = {"classes": rows}
    if stored_energy_j is not None:
        out["stored_energy_j"] = stored_energy_j
    return out


def compute_reactor_power(class_name=None, override_kw_kg=None, gross_power_w=None):
    """T2 — reactor specific-power lookup (+ optional implied core mass).

    No class → all rows. A class → that row. ``--override-kw-kg`` substitutes α (echoed).
    ``--gross-power-w`` echoes the implied core mass m = P/α — but EVERY result carries the mandatory
    thermal pointer (the real high-P ceiling is thermal, not core mass).
    """
    if gross_power_w is not None and gross_power_w <= 0:
        return {"error": "gross_power_w must be > 0."}

    def _row(name):
        r = dict(_REACTOR_SPECIFIC_POWER[name])
        alpha = r["specific_power_kw_kg"]
        if override_kw_kg is not None:
            if override_kw_kg <= 0:
                return {"error": "override_kw_kg must be > 0."}
            alpha = override_kw_kg
            r["overridden"] = {"specific_power_kw_kg": override_kw_kg}
        r["class"] = name
        r["specific_power_kw_kg"] = alpha
        r["core_mass_kg"] = (gross_power_w / (alpha * 1000.0)
                             if gross_power_w is not None else None)
        r["thermal_pointer"] = _THERMAL_POINTER
        return r

    if class_name is not None:
        if class_name not in _REACTOR_SPECIFIC_POWER:
            return {"error": f"Unknown reactor class '{class_name}'. "
                             f"Valid: {_valid_keys(_REACTOR_SPECIFIC_POWER)}."}
        return _row(class_name)
    rows = []
    for name in _REACTOR_SPECIFIC_POWER:
        r = _row(name)
        if "error" in r:
            return r
        rows.append(r)
    return {"classes": rows, "thermal_pointer": _THERMAL_POINTER}
