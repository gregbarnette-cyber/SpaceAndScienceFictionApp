"""core/kinematics.py — CR-7: heliocentric U/V/W → thin-disk / thick-disk / halo verdict.

Pure-math and **self-validating** (Phase-H/P contract: curated ``{"error"}`` → exit 1) for the
U/V/W-direct path; the ``--star`` convenience does a live SIMBAD → Hypatia lookup (the only network
path, lazily imported). Exposes ``classify_population`` behind the ``population-classify`` query.py
subcommand.

The U/V/W *data* was already CLI-exposed (``hypatia-data`` → ``u_vel``/``v_vel``/``w_vel``) and the
GUI plots a Toomre tab, but **no code anywhere returns a population verdict** — the 50/100/180 km/s
arcs are only drawn. CR-7 adds the verdict:

  membership is the Bensby et al. (2003) TD/D/H scheme — each Galactic population is a Gaussian
  velocity ellipsoid (σ_U, σ_V, σ_W) offset by its asymmetric drift ``v_asym`` and weighted by its
  local number-density fraction ``X``; the verdict is the arg-max of the X-weighted densities and
  ``membership_prob`` is the normalised winning probability.

Frame: Hypatia's U/V/W are **heliocentric** (U → Galactic centre, V → rotation, W → north Galactic
pole); they are put in the **LSR** frame by adding the Schönrich+2010 solar motion — the *same*
constant ``core.viz`` uses for the GUI Toomre tab (kept in sync; the value must not fork).
"""

import math

# Solar motion w.r.t. the Local Standard of Rest (Schönrich, Binney & Dehnen 2010), km/s, in the
# (U → Galactic centre, V → rotation, W → NGP) frame — identical to core.viz._SOLAR_MOTION_UVW
# (the GUI Toomre tab). Adding it to a heliocentric U/V/W yields the LSR-frame velocity where the
# population thresholds are defined. Do NOT fork this value; if it ever needs a single home, lift
# both to core.shared.
_SOLAR_MOTION_UVW = (11.1, 12.24, 7.25)

# Galactic-population velocity ellipsoids (LSR frame). PROVISIONAL constants block — the single
# source of truth for the classifier; a review may tune the numbers, never the structure.
#   X       = local number-density fraction (Σ over populations = 1.0015, per the source)
#   sigma_* = velocity dispersions (km/s)
#   v_asym  = asymmetric drift, subtracted from V (km/s)
# Source: Bensby, Feltzing & Lundström 2003 (A&A 410, 527), Table 1 — the widely-used empirical
# thin/thick/halo decomposition. confidence: present-datapoint (the 2014 update shifts the numbers
# modestly; swap here if a reviewer prefers it).
_POPULATION_KINEMATICS = {
    "thin":  {"X": 0.9000, "sigma_u": 35.0,  "sigma_v": 20.0, "sigma_w": 16.0, "v_asym": -15.0},
    "thick": {"X": 0.1000, "sigma_u": 67.0,  "sigma_v": 38.0, "sigma_w": 35.0, "v_asym": -46.0},
    "halo":  {"X": 0.0015, "sigma_u": 160.0, "sigma_v": 90.0, "sigma_w": 90.0, "v_asym": -220.0},
}
_KINEMATICS_CITATION = "Bensby, Feltzing & Lundström 2003 (A&A 410, 527), Table 1"
_KINEMATICS_CONFIDENCE = "present-datapoint"

# Canonical order for the verdict / probabilities dict (hottest-populated → rarest).
_POP_ORDER = ("thin", "thick", "halo")


def _gaussian_density(u_lsr, v_lsr, w_lsr, p):
    """Normalised 3D Gaussian velocity-ellipsoid density for population params ``p`` (km/s inputs)."""
    su, sv, sw = p["sigma_u"], p["sigma_v"], p["sigma_w"]
    norm = 1.0 / ((2.0 * math.pi) ** 1.5 * su * sv * sw)
    expo = (u_lsr ** 2) / (2.0 * su ** 2) \
        + ((v_lsr - p["v_asym"]) ** 2) / (2.0 * sv ** 2) \
        + (w_lsr ** 2) / (2.0 * sw ** 2)
    return norm * math.exp(-expo)


def _resolve_uvw_from_star(star):
    """Live SIMBAD → Hypatia lookup for a star identifier → (u, v, w, star_name) heliocentric km/s.

    Returns a dict ``{"error": …}`` on any failure (lookup miss / no Hypatia / no U-V-W), matching
    the self-validating contract. Lazily imports the heavy databases layer so the U/V/W-direct path
    stays pure and import-cheap.
    """
    from core import databases  # lazy — network + astroquery only on the --star path
    sl = databases.compute_simbad_lookup(star)
    if "error" in sl:
        return {"error": sl["error"]}
    hyp = databases.compute_hypatia_data(sl)
    if "error" in hyp:
        return {"error": hyp["error"]}
    props = hyp.get("properties") or {}
    u, v, w = props.get("u_vel"), props.get("v_vel"), props.get("w_vel")
    if u is None or v is None or w is None:
        return {"error": f"No U/V/W kinematics available for '{star}'"}
    return {"u": float(u), "v": float(v), "w": float(w),
            "star_name": hyp.get("star_name") or sl.get("main_id") or star}


def classify_population(u=None, v=None, w=None, star=None):
    """Thin-disk / thick-disk / halo membership from heliocentric U/V/W (km/s) or a star identifier.

    Supply the three velocities directly (``u``/``v``/``w``, heliocentric km/s) **or** a ``star``
    identifier (SIMBAD → Hypatia, live network). Explicit U/V/W win if both are given.

    Returns ``{star, u_vel_kms, v_vel_kms, w_vel_kms, toomre_velocity_kms, total_velocity_kms,
    population, membership_prob, probabilities:{thin,thick,halo}, provenance:{…}}`` or
    ``{"error": str}``.
    """
    star_name = star
    explicit = [x for x in (u, v, w) if x is not None]
    if explicit:
        # Partial U/V/W must NOT silently fall through to the --star lookup (dropping the supplied
        # values); require all three, and explicit velocities win over --star.
        if len(explicit) != 3:
            return {"error": "Provide all three of --u/--v/--w (km/s), or none and use --star."}
        try:
            u, v, w = float(u), float(v), float(w)
        except (TypeError, ValueError):
            return {"error": "U, V, W must be numeric (km/s)."}
    elif star:
        resolved = _resolve_uvw_from_star(star)
        if "error" in resolved:
            return resolved
        u, v, w = resolved["u"], resolved["v"], resolved["w"]
        star_name = resolved["star_name"]
    else:
        return {"error": "Provide --star, or all three of --u/--v/--w (km/s, heliocentric)."}

    # Heliocentric → LSR (Schönrich+2010 solar motion).
    su, sv, sw = _SOLAR_MOTION_UVW
    u_l, v_l, w_l = u + su, v + sv, w + sw
    toomre = math.hypot(u_l, w_l)                       # √(U²+W²), the Toomre y-axis
    total = math.sqrt(u_l ** 2 + v_l ** 2 + w_l ** 2)   # √(U²+V²+W²)

    # X-weighted Gaussian-ellipsoid densities → normalised membership probabilities.
    weighted = {pop: p["X"] * _gaussian_density(u_l, v_l, w_l, p)
                for pop, p in _POPULATION_KINEMATICS.items()}
    denom = sum(weighted.values())
    if denom <= 0.0:                                    # numerically underflowed (extreme velocity)
        probs = {pop: (1.0 if pop == "halo" else 0.0) for pop in _POP_ORDER}
    else:
        probs = {pop: weighted[pop] / denom for pop in _POP_ORDER}
    population = max(_POP_ORDER, key=lambda k: probs[k])

    return {
        "star": star_name,
        "u_vel_kms": u,
        "v_vel_kms": v,
        "w_vel_kms": w,
        "toomre_velocity_kms": toomre,
        "total_velocity_kms": total,
        "population": population,
        "membership_prob": probs[population],
        "probabilities": {pop: probs[pop] for pop in _POP_ORDER},
        "provenance": {
            "scheme": "Bensby TD/D/H Gaussian velocity ellipsoids",
            "citation": _KINEMATICS_CITATION,
            "confidence": _KINEMATICS_CONFIDENCE,
            "lsr_frame": "Schönrich, Binney & Dehnen 2010 solar motion",
        },
    }
