# core/nbody.py — Phase R2-C4: optional N-body confirmation of marginal verdicts.
#
# PURE + DETERMINISTIC: a fixed-step, coplanar, kick-drift-kick leapfrog (symplectic)
# integrator using ONLY numpy + math — no scipy, no RNG, no I/O. Initial conditions
# are deterministic (each planet on a circular orbit at a fixed phase), the timestep
# and orbit count are fixed module constants, and numpy float64 ops are reproducible,
# so the same inputs always give byte-identical results.
#
# This is a *short-integration screen* for marginal analytic stability verdicts (the
# Δ ∈ [2√3, 10) mutual-Hill gray band), NOT a Gyr stability proof. The feasibility
# engine calls it only when nbody=True and a packing verdict is marginal.
#
# Units: AU, years, solar masses, with G = 4π² (so a circular orbit of SMA a around
# mass M has period √(a³/M) years). Planet masses are taken in Earth masses and
# converted to solar internally.

import math

import numpy as np

from core.equations import _EARTH_MASS_KG, _SOLAR_MASS_KG

_G = 4.0 * math.pi ** 2            # AU³ yr⁻² M_sun⁻¹

# Fixed integration envelope (a screen, deliberately bounded).
_N_ORBITS = 200                    # innermost-body orbits to integrate
_STEPS_PER_ORBIT = 100             # leapfrog steps per innermost orbit
_CLOSE_FACTOR = 1.0                # close encounter = pairwise sep < this × mutual Hill
_DRIFT_BAND = 0.5                  # |Δa|/a₀ beyond this (or unbound) → unstable
_SOFTENING_AU = 1.0e-6             # gravitational softening (numerical safety)

_EARTH_PER_SOLAR = _EARTH_MASS_KG / _SOLAR_MASS_KG


def _accel(pos, gm):
    """Pairwise gravitational acceleration on every body (softened). pos:(N,2),
    gm = G·mass per body (N,) → returns (N,2)."""
    diff = pos[None, :, :] - pos[:, None, :]               # (N,N,2): j − i
    d2 = np.sum(diff * diff, axis=2) + _SOFTENING_AU ** 2   # (N,N)
    inv3 = d2 ** -1.5
    np.fill_diagonal(inv3, 0.0)
    return np.einsum("ij,ij,ijk->ik", gm[None, :].repeat(pos.shape[0], 0), inv3, diff)


def integrate_coplanar(star_mass_solar, planets, n_orbits=_N_ORBITS,
                       steps_per_orbit=_STEPS_PER_ORBIT):
    """Integrate a coplanar star + planet system; report whether it survives intact.

    Args:
        star_mass_solar: central star mass (M☉, > 0).
        planets: list of dicts with positive ``mass_earth`` and ``a_au`` (circular,
                 deterministic phases). Fewer than 2 valid planets → trivially survives.
    Returns ``{survived, orbits_run, reason, n_orbits, steps}``: ``survived`` False on
    a close encounter (< mutual Hill radius) or an SMA drift / unbinding beyond the
    fixed band; ``orbits_run`` is the innermost-orbit count reached.
    """
    valid = [p for p in (planets or [])
             if p.get("mass_earth") and p.get("a_au") and p["mass_earth"] > 0 and p["a_au"] > 0]
    n = len(valid)
    if star_mass_solar <= 0 or n < 2:
        return {"survived": True, "orbits_run": n_orbits, "reason": None,
                "n_orbits": n_orbits, "steps": 0}

    a0 = np.array([p["a_au"] for p in valid], dtype=float)
    m_planets = np.array([p["mass_earth"] * _EARTH_PER_SOLAR for p in valid], dtype=float)

    # Bodies: index 0 = star, 1..n = planets. Circular Keplerian ICs at spread phases.
    masses = np.empty(n + 1)
    masses[0] = star_mass_solar
    masses[1:] = m_planets
    pos = np.zeros((n + 1, 2))
    vel = np.zeros((n + 1, 2))
    for i in range(n):
        phase = 2.0 * math.pi * i / n
        r = a0[i]
        pos[i + 1] = (r * math.cos(phase), r * math.sin(phase))
        v = math.sqrt(_G * star_mass_solar / r)            # prograde circular speed
        vel[i + 1] = (-v * math.sin(phase), v * math.cos(phase))

    # Zero the centre of mass (position + momentum) so SMA tracking is clean.
    pos -= np.sum(masses[:, None] * pos, axis=0) / masses.sum()
    vel -= np.sum(masses[:, None] * vel, axis=0) / masses.sum()

    gm = _G * masses

    # Precompute planet-pair mutual Hill radii (close-encounter thresholds).
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            r_h = ((m_planets[i] + m_planets[j]) / (3.0 * star_mass_solar)) ** (1.0 / 3.0) \
                * (a0[i] + a0[j]) / 2.0
            pairs.append((i + 1, j + 1, _CLOSE_FACTOR * r_h))

    p_inner = math.sqrt(a0.min() ** 3 / star_mass_solar)   # years
    dt = p_inner / steps_per_orbit
    total_steps = int(n_orbits * steps_per_orbit)

    acc = _accel(pos, gm)
    for step in range(total_steps):
        # Close-encounter check (planet pairs) before advancing.
        for bi, bj, thr in pairs:
            d = math.hypot(pos[bi, 0] - pos[bj, 0], pos[bi, 1] - pos[bj, 1])
            if d < thr:
                return {"survived": False,
                        "reason": "close encounter within a mutual Hill radius",
                        "orbits_run": step // steps_per_orbit,
                        "n_orbits": n_orbits, "steps": step}

        # Kick-drift-kick leapfrog.
        vel += 0.5 * dt * acc
        pos += dt * vel
        acc = _accel(pos, gm)
        vel += 0.5 * dt * acc

        # SMA-drift / unbinding check, once per innermost orbit.
        if (step + 1) % steps_per_orbit == 0:
            rel_p = pos[1:] - pos[0]
            rel_v = vel[1:] - vel[0]
            r = np.sqrt(np.sum(rel_p * rel_p, axis=1))
            v2 = np.sum(rel_v * rel_v, axis=1)
            eps = 0.5 * v2 - _G * star_mass_solar / r       # specific orbital energy
            if np.any(eps >= 0):
                return {"survived": False, "reason": "a planet became unbound",
                        "orbits_run": (step + 1) // steps_per_orbit,
                        "n_orbits": n_orbits, "steps": step + 1}
            a_now = -_G * star_mass_solar / (2.0 * eps)
            if np.any(np.abs(a_now - a0) / a0 > _DRIFT_BAND):
                return {"survived": False,
                        "reason": f"semi-major axis drifted beyond {int(_DRIFT_BAND * 100)}%",
                        "orbits_run": (step + 1) // steps_per_orbit,
                        "n_orbits": n_orbits, "steps": step + 1}

    return {"survived": True, "orbits_run": n_orbits, "reason": None,
            "n_orbits": n_orbits, "steps": total_steps}
