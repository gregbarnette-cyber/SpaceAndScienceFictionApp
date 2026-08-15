"""Phase AT (Packet 38.1) — bundled static data for the weapons / engagement calculators.

Isolated like ``shielding_tables.py`` / ``radiation_tables.py``: every number carries a source +
a confidence note, and every default here is **LABELLED-ILLUSTRATIVE and overridable** at the CLI
(the ``*-theoretical`` honesty convention). None of these are setting/canon values — they are
present-physics reference defaults the sibling repo overrides per load-bearing cell.

Consumers: ``core.weapons`` (W3 ``kinetic-kill``, W4 ``warhead-effects-at-standoff``). W1
``salvo-exchange`` has no bundled data (pure combat arithmetic). See ``PHASE_AT_PLAN.md``.
"""

# ── W4 — warhead yield partition fractions (vacuum) ────────────────────────────
# Fraction of total yield Y radiated into each lethal channel IN VACUUM (no blast wave — kill is
# by radiated/particulate fluence). ILLUSTRATIVE DEFAULTS from the vacuum nuclear-effects /
# annihilation literature, to be pinned at Packet 38.1 CP2; override any channel per load-bearing
# cell. Fractions may sum to < 1: the remainder leaves as non-lethal / escaping radiation
# (notably antimatter neutrinos), which is physically correct — not all yield is lethal fluence.
PARTITION_SOURCE = ("illustrative vacuum-effects defaults (fission/fusion soft-x-ray-dominated; "
                    "antimatter p̄p → γ + charged pions, ~0.2 escapes as neutrinos; kinetic-plasma "
                    "debris) — labelled-theoretical, overridable per channel; pinned at Pkt 38.1 CP2")

WARHEAD_PARTITIONS = {
    # channel keys: xray (soft x-ray), neutron, debris (debris/plasma), gamma
    "fission":        {"xray": 0.75, "neutron": 0.03, "debris": 0.22, "gamma": 0.0},
    "fusion":         {"xray": 0.70, "neutron": 0.05, "debris": 0.25, "gamma": 0.0},
    "antimatter":     {"xray": 0.0,  "neutron": 0.0,  "debris": 0.50, "gamma": 0.30},
    "kinetic-plasma": {"xray": 0.15, "neutron": 0.0,  "debris": 0.85, "gamma": 0.0},
}
WARHEAD_TYPES = tuple(WARHEAD_PARTITIONS)
CHANNELS = ("xray", "neutron", "debris", "gamma")

_TNT_J_PER_KT = 4.184e12    # 1 kt TNT ≡ 4.184e12 J  (W4 yield-kt → J)
_TNT_J_PER_TON = 4.184e9    # 1 ton TNT ≡ 4.184e9 J  (W3 KE → tons TNT)

# ── W3 — Whipple / hypervelocity armor thresholds (present-day aluminium) ───────
# PRESENT-DAY-ALUMINIUM REFERENCE — NOT setting armor (canon is advanced CNT/materials); override
# for the setting's hulls. An Al impactor shatters into a debris cloud above ~3 km/s and largely
# vaporizes above ~7 km/s (Al-on-Al, order-of-magnitude; Cour-Palais / MMOD regime).
WHIPPLE_AL_SHATTER_KMS = 3.0
WHIPPLE_AL_VAPORIZE_KMS = 7.0
WHIPPLE_SOURCE = ("present-day-aluminium reference (~3 km/s shatter, ~7 km/s vaporize; "
                  "Cour-Palais / MMOD, order-of-magnitude) — override for advanced armor")

# Default debris-cone half-angle for the shattered-cloud rear-wall estimate (illustrative).
DEBRIS_CONE_HALF_ANGLE_DEG = 15.0

# Crater-scaling velocity exponent (W3 alternative penetration form). LABELLED order-of-magnitude:
# P/d ∝ (ρ_i/ρ_t)^0.5 · (v/c_t)^n, n ≈ 2/3 in the spacecraft-shielding regime (Cour-Palais / MMOD
# penetration correlations). NOT a pinned number — Pkt 38.1 CP2 pins the exact form/exponent
# against the impact literature; the hydrodynamic long-rod P = L·√(ρ_i/ρ_t) stays the headline.
CRATER_VELOCITY_EXPONENT = 2.0 / 3.0
CRATER_SOURCE = ("hypervelocity penetration correlation ~v^(2/3), spacecraft-shielding regime "
                 "(Cour-Palais / MMOD) — labelled order-of-magnitude, overridable; pinned Pkt 38.1 CP2")
