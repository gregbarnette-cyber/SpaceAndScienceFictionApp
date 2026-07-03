"""Phase Y — STL mission energetics (Group G of the settlement/propulsion/astrobiology/
terraforming request; the pre-scope-lock prerequisite for Packet 16, STL Colonization
Propulsion).

Two pure-math, self-validating (Phase-H/P contract) calculators adding the *mass/energy*
side of sub-light travel — ``query.py`` already has the *kinematics* (brachistochrone /
distance-at-acceleration / custom-thrust). Energetics = "can you carry the fuel";
kinematics = "how long is the trip".

  * ``compute_rocket_equation`` (G1) — Tsiolkovsky (classical + relativistic), mass ratio,
    propellant fraction; flyby/rendezvous/round-trip legs; optional payload mass budget.
  * ``compute_beam_sail``       (G2) — laser / photon-sail thrust, acceleration, final velocity.
  * ``compute_pellet_stream``   (C2, Phase AD) — pellet-stream (momentum-beam) drive: thrust /
    power / drive-or-no-thrust verdict from the closing velocity. The mass analog of the
    ``ramscoop`` drag-vs-thrust balance.

No network, no DB, no RNG, no time. ``query.py``-only (no GUI). Shares ``_C_MS`` /
``_STANDARD_GRAVITY`` with ``core.equations``; the ideal fuel presets live in
``core.propulsion_tables`` (isolated, like ``core.shielding_tables``). Self-validating: bad
input returns a curated ``{"error": str}``. The bundled exhaust velocities are ideal /
present-day ancestors and caller-overridable (Mature-Technology Assumption).
"""

import math

from core.equations import _C_MS, _M_PER_AU, _STANDARD_GRAVITY
from core import propulsion_tables

_C_KMS = _C_MS / 1000.0
_LEGS = {"flyby": 1, "rendezvous": 2, "round-trip": 4}
_PELLET_COUPLING = {"reflect": 2.0, "absorb": 1.0}   # elastic 2·ṁu / inelastic 1·ṁu

_MODEL_NOTE_PELLET = (
    "Pellet-stream (momentum-beam) drive: a station-fired stream of pellets travelling at "
    "stream velocity v_s strikes a vehicle moving at v; the closing velocity is u = v_s − v. "
    "Thrust F = g·ṁ·u (g = 2 perfectly reflecting / elastic, g = 1 absorbing / inelastic); "
    "the power imparted in the vehicle frame is ½·ṁ·u². Thrust falls to zero at the crossover "
    "v = v_s and there is no push once v ≥ v_s (verdict 'no-thrust') — the mass analog of the "
    "ramscoop's drive/brake crossover. Non-relativistic momentum bookkeeping (exact for "
    "v, v_s ≪ c; an overestimate of the effective push as u → c — use the relativistic rocket "
    "equation near c). Pellet guidance, beam divergence, and interception efficiency are out of "
    "scope (they only lower the effective coupling below g)."
)


def _resolve_vehicle_velocity(velocity_kms, beta):
    """Return (v_ms, velocity_kms, beta) or a {"error"} dict. Exactly one anchor required.

    ``--velocity-kms`` admits a vehicle at rest (v = 0); ``--beta`` is strictly sublight (0<β<1).
    """
    if (velocity_kms is not None) + (beta is not None) != 1:
        return {"error": "Provide exactly one velocity anchor: --velocity-kms or --beta."}
    if beta is not None:
        if not (0.0 < beta < 1.0):
            return {"error": "beta must be in the range 0 < β < 1 (sublight)."}
        v_ms = beta * _C_MS
        return (v_ms, v_ms / 1000.0, beta)
    if velocity_kms < 0:
        return {"error": "velocity_kms must be ≥ 0."}
    v_ms = velocity_kms * 1000.0
    return (v_ms, velocity_kms, v_ms / _C_MS)


# ── G1 — Tsiolkovsky rocket equation (classical + relativistic) ──────────────

def compute_rocket_equation(delta_v_kms=None, beta=None, exhaust_velocity_kms=None,
                            isp_s=None, fuel=None, mass_ratio=None, relativistic=False,
                            legs="flyby", payload_mass_t=None, structure_fraction=None):
    """Mass ratio / propellant fraction for a rocket, from any two of {velocity, exhaust,
    mass_ratio}.

    Velocity anchor: ``delta_v_kms`` (classical) OR ``beta`` = final v/c (relativistic).
    Exhaust anchor: ``exhaust_velocity_kms`` OR ``isp_s`` (→ v_e = isp·g₀) OR ``fuel``
    (bundled ideal v_e). Or supply ``mass_ratio`` (single-burn) as one of the two anchors.
    ``legs`` raises the single-burn MR: flyby MR¹ / rendezvous MR² / round-trip MR⁴.
    """
    # ── legs ──
    if legs not in _LEGS:
        return {"error": "legs must be one of flyby, rendezvous, round-trip."}
    n_legs = _LEGS[legs]

    # ── anchor groups: exactly two of {velocity, exhaust, mass_ratio} ──
    have_v = delta_v_kms is not None or beta is not None
    have_e = exhaust_velocity_kms is not None or isp_s is not None or fuel is not None
    have_m = mass_ratio is not None
    if (have_v + have_e + have_m) != 2:
        return {"error": "Provide exactly two of {velocity (--delta-v-kms or --beta), "
                         "exhaust (--exhaust-velocity-kms/--isp-s/--fuel), --mass-ratio}."}

    # ── within-group multiplicity ──
    if delta_v_kms is not None and beta is not None:
        return {"error": "Provide only one velocity anchor: --delta-v-kms or --beta, not both."}
    if (exhaust_velocity_kms is not None) + (isp_s is not None) + (fuel is not None) > 1:
        return {"error": "Provide only one exhaust anchor: --exhaust-velocity-kms, --isp-s, or --fuel."}

    # ── per-anchor range validation ──
    if delta_v_kms is not None and delta_v_kms <= 0:
        return {"error": "delta_v_kms must be > 0."}
    if beta is not None and not (0.0 <= beta < 1.0):
        return {"error": "beta must be in the range 0 ≤ β < 1 (sublight)."}
    if exhaust_velocity_kms is not None and exhaust_velocity_kms <= 0:
        return {"error": "exhaust_velocity_kms must be > 0."}
    if isp_s is not None and isp_s <= 0:
        return {"error": "isp_s must be > 0."}
    if fuel is not None and fuel not in propulsion_tables._FUELS:
        return {"error": "Unknown fuel '%s'. Known: %s." %
                (fuel, ", ".join(sorted(propulsion_tables._FUELS)))}
    if mass_ratio is not None and mass_ratio <= 1.0:
        return {"error": "mass_ratio must be > 1 (a ratio of 1 is zero propellant)."}
    if payload_mass_t is not None and payload_mass_t <= 0:
        return {"error": "payload_mass_t must be > 0."}
    if structure_fraction is not None and not (0.0 <= structure_fraction < 1.0):
        return {"error": "structure_fraction must be in [0, 1)."}

    # ── regime: velocity form selects it (β → relativistic; Δv → classical) ──
    if beta is not None:
        rel = True
    elif delta_v_kms is not None:
        if relativistic:
            return {"error": "Relativistic mode is defined against --beta (final v/c), "
                             "not --delta-v-kms. Supply --beta for the relativistic branch."}
        rel = False
    else:  # velocity is the unknown (exhaust + mass_ratio given) — flag chooses which to emit
        rel = bool(relativistic)

    # ── resolve exhaust velocity if the exhaust group was supplied ──
    v_e_kms = None
    if have_e:
        if exhaust_velocity_kms is not None:
            v_e_kms = exhaust_velocity_kms
        elif isp_s is not None:
            v_e_kms = isp_s * _STANDARD_GRAVITY / 1000.0
        else:
            v_e_kms = propulsion_tables._FUELS[fuel]["v_e_kms"]

    # ── solve the missing anchor ──
    dv_kms = None       # proper Δv (= rapidity·c in relativistic mode)
    beta_out = None
    if have_v and have_e:                       # → mass ratio
        if rel:
            w = math.atanh(beta)                # rapidity
            dv_kms = _C_KMS * w
            beta_out = beta
        else:
            dv_kms = delta_v_kms
        mr_single = math.exp(dv_kms / v_e_kms)
    elif have_v and have_m:                     # → exhaust velocity
        mr_single = mass_ratio
        if rel:
            w = math.atanh(beta)
            dv_kms = _C_KMS * w
            beta_out = beta
        else:
            dv_kms = delta_v_kms
        v_e_kms = dv_kms / math.log(mr_single)
    else:                                       # exhaust + mass_ratio → velocity
        mr_single = mass_ratio
        dv_kms = v_e_kms * math.log(mr_single)  # proper Δv (holds classical & relativistic)
        if rel:
            beta_out = math.tanh(dv_kms * 1000.0 / _C_MS)

    mr_total = mr_single ** n_legs
    propellant_fraction = 1.0 - 1.0 / mr_total

    # ── optional payload mass budget (single-burn MR carried through legs) ──
    propellant_mass_t = wet_mass_t = None
    if payload_mass_t is not None:
        wet_mass_t = payload_mass_t * mr_total
        propellant_mass_t = wet_mass_t - payload_mass_t

    model_note = propulsion_tables._MODEL_NOTE
    if structure_fraction is not None:
        model_note += (" (structure_fraction echoed for transparency; v1 treats payload as the "
                       "dry mass — full structural staging defers to Packet 25.)")

    return {
        "mass_ratio": mr_total,
        "mass_ratio_single_burn": mr_single,
        "propellant_fraction": propellant_fraction,
        "delta_v_kms": dv_kms,
        "beta": beta_out,
        "exhaust_velocity_kms": v_e_kms,
        "isp_s": v_e_kms * 1000.0 / _STANDARD_GRAVITY,
        "fuel": fuel,
        "legs": legs,
        "relativistic": rel,
        "payload_mass_t": payload_mass_t,
        "propellant_mass_t": propellant_mass_t,
        "wet_mass_t": wet_mass_t,
        "structure_fraction": structure_fraction,
        "model_note": model_note,
    }


# ── G2 — beam / photon-sail energetics ───────────────────────────────────────

def compute_beam_sail(beam_power_w=None, sail_area_m2=None, areal_mass_gm2=None,
                      sail_mass_kg=None, payload_mass_kg=0.0, reflectivity=0.9,
                      wavelength_nm=None, transmit_aperture_m=None,
                      accel_distance_au=None, accel_time_days=None):
    """Thrust / acceleration / (optional) final velocity of a beam-driven sail.

    Thrust ``F = (1 + R)·P/c`` (R = reflectivity: R→1 reflective 2P/c, R→0 absorptive P/c).
    ``a = F/m`` with m = sail + payload. Optional final velocity from an acceleration length
    (``accel_distance_au``, v = √(2·a·d)) or time (``accel_time_days``, v = a·t) — first-order
    non-relativistic. A diffraction beam-range note when wavelength + aperture are given.
    """
    if beam_power_w is None or beam_power_w <= 0:
        return {"error": "beam_power_w must be > 0."}
    if not (0.0 <= reflectivity <= 1.0):
        return {"error": "reflectivity must be in [0, 1]."}
    if payload_mass_kg is None or payload_mass_kg < 0:
        return {"error": "payload_mass_kg must be ≥ 0."}
    if sail_area_m2 is not None and sail_area_m2 <= 0:
        return {"error": "sail_area_m2 must be > 0."}

    # ── sail mass ──
    if sail_mass_kg is not None:
        if sail_mass_kg <= 0:
            return {"error": "sail_mass_kg must be > 0."}
    else:
        if areal_mass_gm2 is None or sail_area_m2 is None:
            return {"error": "Provide sail_mass_kg, or areal_mass_gm2 + sail_area_m2."}
        if areal_mass_gm2 <= 0:
            return {"error": "areal_mass_gm2 must be > 0."}
        sail_mass_kg = areal_mass_gm2 * 1e-3 * sail_area_m2   # g/m² → kg

    total_mass_kg = sail_mass_kg + payload_mass_kg
    if total_mass_kg <= 0:
        return {"error": "total sail + payload mass must be > 0."}

    # ── acceleration length/time (optional, mutually exclusive) ──
    if accel_distance_au is not None and accel_time_days is not None:
        return {"error": "Provide only one of accel_distance_au or accel_time_days."}
    if accel_distance_au is not None and accel_distance_au <= 0:
        return {"error": "accel_distance_au must be > 0."}
    if accel_time_days is not None and accel_time_days <= 0:
        return {"error": "accel_time_days must be > 0."}

    # ── beam-range note args (both or neither) ──
    if (wavelength_nm is None) != (transmit_aperture_m is None):
        return {"error": "Provide both wavelength_nm and transmit_aperture_m for the beam-range "
                         "note, or neither."}
    if wavelength_nm is not None and wavelength_nm <= 0:
        return {"error": "wavelength_nm must be > 0."}
    if transmit_aperture_m is not None and transmit_aperture_m <= 0:
        return {"error": "transmit_aperture_m must be > 0."}

    thrust_n = (1.0 + reflectivity) * beam_power_w / _C_MS
    acceleration_ms2 = thrust_n / total_mass_kg

    final_velocity_kms = beta_out = beam_energy_j = None
    if accel_distance_au is not None:
        d_m = accel_distance_au * _M_PER_AU
        v = math.sqrt(2.0 * acceleration_ms2 * d_m)
        t = math.sqrt(2.0 * d_m / acceleration_ms2)
        beam_energy_j = beam_power_w * t
    elif accel_time_days is not None:
        t = accel_time_days * 86400.0
        v = acceleration_ms2 * t
        beam_energy_j = beam_power_w * t
    else:
        v = None
    if v is not None:
        final_velocity_kms = v / 1000.0
        beta_out = v / _C_MS

    # ── diffraction beam-range note ──
    if wavelength_nm is not None:
        lam_m = wavelength_nm * 1e-9
        # Airy spot diameter ≈ 2.44·λ·range/aperture; range where the spot equals the sail.
        if sail_area_m2 is not None:
            sail_diam_m = 2.0 * math.sqrt(sail_area_m2 / math.pi)
            range_m = sail_diam_m * transmit_aperture_m / (2.44 * lam_m)
            beam_range_note = (
                "Diffraction-limited: the beam spot (≈2.44·λ·range/aperture) grows to the sail "
                "diameter (%.1f m) at range ≈ %.3g m (%.3g AU); beyond that the sail intercepts a "
                "falling fraction of the beam (first-order Airy estimate)."
                % (sail_diam_m, range_m, range_m / _M_PER_AU))
        else:
            beam_range_note = ("Diffraction spread ≈ 2.44·λ·range/aperture; provide sail_area_m2 "
                               "for the range at which the spot exceeds the sail.")
    else:
        beam_range_note = "Beam-range note omitted (supply wavelength_nm + transmit_aperture_m)."

    model_note = (
        "Beam-sail: thrust F = (1+R)·P/c (R = reflectivity; R→1 reflective 2P/c, R→0 absorptive "
        "P/c). Final velocity is first-order non-relativistic (v = √(2·a·d) or a·t) — an "
        "overestimate as β grows; use rocket-equation/relativistic-brachistochrone near c. Beam "
        "power, reflectivity, and areal mass are present-day ancestors — MTA-movable.")

    return {
        "thrust_n": thrust_n,
        "acceleration_ms2": acceleration_ms2,
        "final_velocity_kms": final_velocity_kms,
        "beta": beta_out,
        "beam_energy_j": beam_energy_j,
        "sail_area_m2": sail_area_m2,
        "total_mass_kg": total_mass_kg,
        "sail_mass_kg": sail_mass_kg,
        "payload_mass_kg": payload_mass_kg,
        "reflectivity": reflectivity,
        "beam_range_note": beam_range_note,
        "model_note": model_note,
    }


# ── C2 (Phase AD) — pellet-stream (momentum-beam) drive ───────────────────────

def compute_pellet_stream(stream_velocity_kms=None, mass_flow_rate_kgs=None,
                          pellet_mass_kg=None, pellet_rate_hz=None,
                          velocity_kms=None, beta=None, coupling="reflect",
                          vehicle_mass_t=None):
    """Thrust / power / drive-verdict of a pellet-stream drive.

    Closing velocity ``u = v_s − v``; thrust ``F = g·ṁ·u`` (g = 2 reflect / 1 absorb); power
    ``½·ṁ·u²``. ``verdict = "drive"`` while ``v_s > v`` else ``"no-thrust"`` (crossover at
    ``v = v_s``). The mass analog of ``compute_ramscoop`` — mirror of its structure.

    Mass-flow anchor: ``mass_flow_rate_kgs`` OR (``pellet_mass_kg`` + ``pellet_rate_hz`` → ṁ).
    Velocity anchor: ``velocity_kms`` (admits v = 0) OR ``beta``. Optional ``vehicle_mass_t``
    → acceleration.
    """
    if stream_velocity_kms is None or stream_velocity_kms <= 0:
        return {"error": "stream_velocity_kms must be > 0."}
    if coupling not in _PELLET_COUPLING:
        return {"error": "coupling must be one of reflect, absorb."}

    # ── mass-flow anchor: --mass-flow-rate-kgs OR (--pellet-mass-kg + --pellet-rate-hz) ──
    have_mdot = mass_flow_rate_kgs is not None
    have_pellet = pellet_mass_kg is not None or pellet_rate_hz is not None
    if have_mdot + have_pellet != 1:
        return {"error": "Provide exactly one mass-flow anchor: --mass-flow-rate-kgs, or "
                         "(--pellet-mass-kg + --pellet-rate-hz)."}
    if have_mdot:
        if mass_flow_rate_kgs <= 0:
            return {"error": "mass_flow_rate_kgs must be > 0."}
        m_dot = mass_flow_rate_kgs
    else:
        if pellet_mass_kg is None or pellet_rate_hz is None:
            return {"error": "Provide both --pellet-mass-kg and --pellet-rate-hz for the "
                             "pellet anchor."}
        if pellet_mass_kg <= 0:
            return {"error": "pellet_mass_kg must be > 0."}
        if pellet_rate_hz <= 0:
            return {"error": "pellet_rate_hz must be > 0."}
        m_dot = pellet_mass_kg * pellet_rate_hz

    vel = _resolve_vehicle_velocity(velocity_kms, beta)
    if isinstance(vel, dict):
        return vel
    v_ms, vehicle_velocity_kms, beta_out = vel

    if vehicle_mass_t is not None and vehicle_mass_t <= 0:
        return {"error": "vehicle_mass_t must be > 0."}

    v_s_ms = stream_velocity_kms * 1000.0
    u_ms = v_s_ms - v_ms                                  # closing (relative) velocity
    g = _PELLET_COUPLING[coupling]
    if u_ms > 0.0:
        thrust_n = g * m_dot * u_ms
        delivered_power_w = 0.5 * m_dot * u_ms ** 2
        verdict = "drive"
    else:                                                 # v ≥ v_s → the stream can't catch up
        thrust_n = 0.0
        delivered_power_w = 0.0
        verdict = "no-thrust"

    acceleration_ms2 = None
    if vehicle_mass_t is not None:
        acceleration_ms2 = thrust_n / (vehicle_mass_t * 1000.0)

    return {
        "stream_velocity_kms": stream_velocity_kms,
        "vehicle_velocity_kms": vehicle_velocity_kms,
        "beta": beta_out,
        "relative_velocity_kms": u_ms / 1000.0,
        "mass_flow_rate_kgs": m_dot,
        "coupling": coupling,
        "thrust_n": thrust_n,
        "delivered_power_w": delivered_power_w,
        "verdict": verdict,
        "crossover_velocity_kms": stream_velocity_kms,
        "acceleration_ms2": acceleration_ms2,
        "model_note": _MODEL_NOTE_PELLET,
    }
