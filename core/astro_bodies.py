"""Shared mass / radius / body-preset resolution for the Pkt 20–24 physics groups.

Phases AE–AI (gravitation / relativity / warp / black_hole) all take a mass — and
often a radius — via the same multi-unit flag pattern (``--mass-kg`` | ``--mass-msun``
| ``--mass-mearth`` | ``--mass-mjup``), and several offer a ``--body`` / ``--object``
preset that fills those fields from a bundled table. This module is the single source
of that logic so the five packs cannot drift and the presets stay mutually consistent.

Convention (matching ``core.active_shield._resolve_moment`` / ``equations._resolve_velocity``):
each resolver returns a **tuple on success** or a ``{"error": str}`` dict on failure — the
caller checks ``isinstance(result, dict)`` and propagates the error (curated exit 1). The
argparse ``type=float`` / ``choices=`` layer still catches non-numeric values and bad preset
names at exit 2 before these run.

Pure math — imports only the CODATA constants from ``core.equations``. No network, no DB,
no RNG, no time.
"""

from core.equations import (
    _SOLAR_MASS_KG,
    _EARTH_MASS_KG,
    _JUP_MASS_KG,
    _SUN_RADIUS_M,
    _EARTH_RADIUS_M,
    _JUP_RADIUS_M,
    _M_PER_AU,
)


def resolve_mass(kg=None, msun=None, mearth=None, mjup=None, name="mass"):
    """Resolve a mass given in exactly one unit → ``(mass_kg, source_label)``.

    Exactly one of ``kg``/``msun``/``mearth``/``mjup`` must be supplied and positive,
    else a ``{"error"}`` dict. ``name`` customises the message ("mass", "body mass", …).
    """
    candidates = [
        (kg, "kg", 1.0),
        (msun, "msun", _SOLAR_MASS_KG),
        (mearth, "mearth", _EARTH_MASS_KG),
        (mjup, "mjup", _JUP_MASS_KG),
    ]
    given = [(v, label, factor) for (v, label, factor) in candidates if v is not None]
    if len(given) != 1:
        return {"error": f"Provide exactly one {name} unit (kg / msun / mearth / mjup)."}
    value, label, factor = given[0]
    if value <= 0:
        return {"error": f"{name.capitalize()} must be positive."}
    return (value * factor, label)


def resolve_radius(m=None, rsun=None, rearth=None, au=None, name="radius"):
    """Resolve a radius/distance given in exactly one unit → ``(radius_m, source_label)``.

    Exactly one of ``m``/``rsun``/``rearth``/``au`` must be supplied and positive, else a
    ``{"error"}`` dict.
    """
    candidates = [
        (m, "m", 1.0),
        (rsun, "rsun", _SUN_RADIUS_M),
        (rearth, "rearth", _EARTH_RADIUS_M),
        (au, "au", _M_PER_AU),
    ]
    given = [(v, label, factor) for (v, label, factor) in candidates if v is not None]
    if len(given) != 1:
        return {"error": f"Provide exactly one {name} unit (m / rsun / rearth / au)."}
    value, label, factor = given[0]
    if value <= 0:
        return {"error": f"{name.capitalize()} must be positive."}
    return (value * factor, label)


# ── Presets ──────────────────────────────────────────────────────────────────
# Body presets carry mass + radius (for escape-velocity / potential geometry).
# Giant-planet radii are 1-bar EQUATORIAL radii (callers state this in model_note).
_BODY_PRESETS = {
    "sun":     {"display": "Sun",     "mass_kg": 1.989e30, "radius_m": _SUN_RADIUS_M},
    "mercury": {"display": "Mercury", "mass_kg": 3.301e23, "radius_m": 2.4397e6},
    "venus":   {"display": "Venus",   "mass_kg": 4.867e24, "radius_m": 6.0518e6},
    "earth":   {"display": "Earth",   "mass_kg": _EARTH_MASS_KG, "radius_m": _EARTH_RADIUS_M},
    "moon":    {"display": "Moon",    "mass_kg": 7.342e22, "radius_m": 1.7374e6},
    "mars":    {"display": "Mars",    "mass_kg": 6.417e23, "radius_m": 3.3895e6},
    "ceres":   {"display": "Ceres",   "mass_kg": 9.39e20,  "radius_m": 4.73e5},
    "jupiter": {"display": "Jupiter", "mass_kg": _JUP_MASS_KG, "radius_m": _JUP_RADIUS_M},
    "saturn":  {"display": "Saturn",  "mass_kg": 5.683e26, "radius_m": 6.0268e7},
    "uranus":  {"display": "Uranus",  "mass_kg": 8.681e25, "radius_m": 2.5559e7},
    "neptune": {"display": "Neptune", "mass_kg": 1.024e26, "radius_m": 2.4764e7},
    "pluto":   {"display": "Pluto",   "mass_kg": 1.303e22, "radius_m": 1.188e6},
}

# Object presets carry mass only (compact objects / black holes for Group O). Masses in
# solar masses, converted to kg on load.
_OBJECT_PRESETS = {
    "sun":       {"display": "Sun",        "mass_kg": _SOLAR_MASS_KG},
    "earth":     {"display": "Earth",      "mass_kg": _EARTH_MASS_KG},
    "cygnus-x1": {"display": "Cygnus X-1", "mass_kg": 21.2 * _SOLAR_MASS_KG},
    "sgr-a-star":{"display": "Sgr A*",     "mass_kg": 4.15e6 * _SOLAR_MASS_KG},
    "m87-star":  {"display": "M87*",       "mass_kg": 6.5e9 * _SOLAR_MASS_KG},
    "ton-618":   {"display": "TON 618",    "mass_kg": 6.6e10 * _SOLAR_MASS_KG},
}

BODY_PRESET_KEYS = sorted(_BODY_PRESETS)
OBJECT_PRESET_KEYS = sorted(_OBJECT_PRESETS)


def body_preset(key):
    """Return a copy of the ``_BODY_PRESETS`` entry for ``key`` (mass_kg + radius_m +
    display), or a ``{"error"}`` dict. (argparse ``choices=`` normally guards this.)"""
    entry = _BODY_PRESETS.get(key)
    if entry is None:
        return {"error": f"Unknown body preset '{key}'. Choices: {', '.join(BODY_PRESET_KEYS)}."}
    return dict(entry)


def object_preset(key):
    """Return a copy of the ``_OBJECT_PRESETS`` entry for ``key`` (mass_kg + display),
    or a ``{"error"}`` dict."""
    entry = _OBJECT_PRESETS.get(key)
    if entry is None:
        return {"error": f"Unknown object preset '{key}'. Choices: {', '.join(OBJECT_PRESET_KEYS)}."}
    return dict(entry)
