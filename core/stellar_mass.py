"""core/stellar_mass.py — CR-11.2 shared stellar-mass provenance resolver.

`dossier` and `compare-stars` derive stellar mass by inverting a single global mass–luminosity
power law (`regions.py`: ``stellarMass = bcLuminosity ** 0.2632``, i.e. ``L ∝ M^3.8``). That law
**over-reads on the upper main sequence** and for chemically-peculiar Am/Ap stars (Sirius A →
~2.34–2.59 vs the dynamical 2.063), and it was emitted **silently**. This module brings both to
parity with the CR-10.4/CR-10.5 provenance the tool already carries elsewhere: it resolves the mass
with an explicit **provenance** and flags the two regimes where the inversion is known unreliable.

**Precedence** (mirrors CR-10.3/CR-10.4): manual ``--mass-solar`` → ``--star-mass-catalog`` row →
Gaia DR3 **FLAME** mass → the ``L``-inversion fallback (the current number, unchanged when it is the
source). Independently, ``massL_inversion_caution`` fires when the inversion **is** the source AND
the star is in an over-read regime: **(a) hot upper-MS** — leading MK class O/B/A — or **(b)
chemically-peculiar** — an Am ``m`` / Ap ``p`` token in the SIMBAD ``sp_type``. ``peculiar_star_flag``
is set from the ``m``/``p`` tokens alone (so Vega — a λ Boo rapid rotator with no Am/Ap code — is
flagged via the hot-MS path, not the peculiar path; matches the seed catalog note).

**Pure**: no network, no DB, no RNG. The Gaia FLAME mass is *injected* by the caller (which already
fetches ``gaia-astrophysical``), keeping this resolver offline-testable and reusable verbatim by
CR-11.3 ``exclusion-system`` per component. ``mass_dependent_outputs`` returns the four mass-derived
scalars (``luminosity_from_mass`` / MS-lifespan / ``0.2·M`` / ``40·M``); the dossier's full recompute
of the mass-derived fields **including** ``stellar_radius`` / ``calculated_luminosity`` (→ the
secondary Calculated-HZ) — from the preferred mass, per WB decision B — lives in
``report._patch_regions_for_mass``. The ``bcLuminosity``-based **primary** HZ / snow line / ice lines
never use mass and are untouched.
"""

import re

from core import shared
from core import stellar_mass_tables as smt

# A lowercase Am (m) / Ap (p) peculiarity token — one that follows a subtype digit or an MK class
# letter (uppercase). The lookbehind on ``[0-9A-Z]`` keeps it from matching a lowercase letter inside
# an ordinary word (e.g. the ``m``/``p`` in a stray "comp"/"SB" annotation) — it fires on the real
# codes: A0**m**A1Va, B9**p**Si, kA5hF0**m**F2, A0**p**.
_PECULIAR_RE = re.compile(r"(?<=[0-9A-Z])[mp]")

_HOT_MS_CLASSES = {"O", "B", "A"}

# The four provenance tiers, best → worst.
MANUAL = "manual"
CATALOG = "catalog"
GAIA_FLAME = "gaia_flame"
MS_INVERSION = "ms_luminosity_inversion"

_UNSET = object()   # sentinel: caller did not pre-match the catalog row (match internally)


def peculiar_from_sp_type(sp_type):
    """True when ``sp_type`` carries an Am (``m``) / Ap (``p``) chemical-peculiarity code."""
    if not sp_type:
        return False
    return bool(_PECULIAR_RE.search(sp_type))


def hot_upper_ms_from_sp_type(sp_type):
    """True when the leading MK class is O/B/A (the mass–luminosity over-read regime).

    Teff-independent — a pure ``sp_type`` parse via the shared ``spectral_leading_class`` rule, so it
    fires for A1V and not for G2V exactly as the contract requires. A non-OBAFGKM leading class (a
    white/brown dwarf, ``sp_type`` blank) is not hot-upper-MS.
    """
    if not sp_type:
        return False
    return shared.spectral_leading_class(sp_type) in _HOT_MS_CLASSES


def resolve_mass(inversion_mass, sp_type=None, main_id=None, designations=None,
                 manual_mass=None, catalog=None, flame_mass=None, catalog_row=_UNSET):
    """Resolve the stellar mass + provenance + caution flags. Pure — see the module docstring.

    Args:
      inversion_mass : the ``L^0.2632`` mass (regions ``stellarMass``), or None if regions couldn't
                       compute one (non-MS host) — the tier-4 fallback.
      sp_type        : SIMBAD spectral type (drives the peculiar / hot-MS flags).
      main_id, designations : identity, for the catalog match.
      manual_mass    : tier-1 ``--mass-solar`` override (dossier only), or None.
      catalog        : a loaded catalog dict (``load_mass_catalog`` result); None → no catalog tier.
      flame_mass     : the Gaia DR3 FLAME mass the caller already fetched, or None.
      catalog_row    : an already-matched catalog row (or explicit ``None`` for a known miss) so a
                       caller that pre-matched to decide whether to fetch FLAME does not pay the
                       ``match_mass`` scan twice; left unset → match internally from ``catalog``.

    Returns ``{mass_solar, mass_provenance, massL_inversion_caution, peculiar_star_flag,
    inversion_mass_solar, note, catalog_citation?}``. ``mass_solar`` is never fabricated: it is None
    only when every tier is absent (a non-MS host with no measured mass). The caution is advisory —
    the inversion mass is still returned when it is the source.
    """
    peculiar = peculiar_from_sp_type(sp_type)
    hot_ms = hot_upper_ms_from_sp_type(sp_type)

    if catalog_row is _UNSET:
        catalog_row = None
        if catalog and isinstance(catalog, dict) and "error" not in catalog:
            catalog_row = smt.match_mass(catalog, main_id, designations)

    def _pos(x):
        return isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0

    if _pos(manual_mass):
        mass, prov = float(manual_mass), MANUAL
    elif catalog_row is not None:
        mass, prov = float(catalog_row["mass_solar"]), CATALOG
    elif _pos(flame_mass):
        mass, prov = float(flame_mass), GAIA_FLAME
    elif _pos(inversion_mass):
        mass, prov = float(inversion_mass), MS_INVERSION
    else:
        mass, prov = None, MS_INVERSION   # no tier available — non-MS host, no measured mass

    caution = (prov == MS_INVERSION and mass is not None and (peculiar or hot_ms))

    note = None
    cite = None
    if prov == MANUAL:
        note = "manual --mass-solar override"
    elif prov == CATALOG:
        cite = catalog_row.get("citation") or catalog_row.get("source")
        kind = catalog_row.get("mass_kind") or "measured"
        note = f"{kind} mass from catalog" + (f" [{cite}]" if cite else "")
    elif prov == GAIA_FLAME:
        note = "Gaia DR3 FLAME mass (model-dependent)"
    elif caution:
        reasons = []
        if hot_ms:
            reasons.append(f"hot upper-MS (leading class {shared.spectral_leading_class(sp_type)})")
        if peculiar:
            reasons.append("chemically-peculiar (Am/Ap)")
        note = ("L^0.2632 mass-inversion over-reads for a " + " + ".join(reasons)
                + " star; no measured mass available — treat the mass as an upper estimate")
    elif mass is None:
        note = "no main-sequence mass-inversion available (non-MS host) and no measured mass"

    out = {
        "mass_solar": mass,
        "mass_provenance": prov,
        "massL_inversion_caution": caution,
        "peculiar_star_flag": peculiar,
        "inversion_mass_solar": inversion_mass if _pos(inversion_mass) else None,
        "note": note,
    }
    if cite:
        out["catalog_citation"] = cite
    return out


def mass_dependent_outputs(mass_solar):
    """Recompute the mass-dependent dossier outputs from the **preferred** mass.

    The four scalar outputs — ``luminosity_from_mass`` (``M^3.5``), the MS-lifespan
    (``1e10·(1/M)^2.5`` yr), the gravity inner-system limit (``0.2·M`` AU) and the outer-system limit
    (``40·M`` AU) — mirroring the ``regions.py`` formulas exactly. Returns all-None when ``mass_solar``
    is None.

    Note this helper does **not** cover stellar radius / calculated luminosity. Under **WB decision B**
    (CR-11.2, MSG 006) the dossier recomputes ``stellar_radius = M^0.57`` and ``calculated_luminosity``
    (→ the secondary Calculated HZ) from the preferred mass too, so mass ↔ radius stay coherent — but
    that recompute is applied to the ``regions`` dict directly in ``report._patch_regions_for_mass``
    (so the mass-derived HZ columns recompute in step), not here. The bcLuminosity-based primary HZ /
    snow line / ice lines never use mass and are untouched.
    """
    if not (isinstance(mass_solar, (int, float)) and not isinstance(mass_solar, bool) and mass_solar > 0):
        return {"luminosity_from_mass": None, "main_seq_lifespan_yr": None,
                "inner_limit_gravity_au": None, "outer_limit_au": None}
    m = float(mass_solar)
    return {
        "luminosity_from_mass": m ** 3.5,
        "main_seq_lifespan_yr": (10.0 ** 10) * ((1.0 / m) ** 2.5),
        "inner_limit_gravity_au": 0.2 * m,
        "outer_limit_au": 40.0 * m,
    }
