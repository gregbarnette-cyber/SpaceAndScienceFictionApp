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


def component_candidate_ids(system_main_id, suffix):
    """Per-component catalog-match candidate ids from a system/primary ``main_id`` + a component
    ``suffix`` (``A``/``B``). Strips any existing trailing `` [A-Z]`` first, so ``* alf Cen A`` + ``B``
    → ``* alf Cen B`` (NOT ``* alf Cen A B``) and ``* alf Cen`` + ``A`` → ``* alf Cen A``.

    CR-14.3 (M1): hoisted here from ``exclusion_system`` so the exclusion path, ``binary-stability-auto``
    and the dossier ``multiplicity`` section derive the **same** per-component designations → the same
    catalog hits → the same masses (cross-path consistency). ``exclusion_system._component_candidate_ids``
    delegates to this.
    """
    base = (system_main_id or "").strip()
    if not base:
        return set()
    base = re.sub(r"\s+[A-Z]$", "", base)
    return {f"{base} {suffix}"}


def augment_designations(designations, extra_ids):
    """A copy of the SIMBAD ``designations`` dict with ``extra_ids`` injected as synthetic values, so
    ``stellar_mass_tables.match_mass`` (which scans every ``designations`` value against a catalog
    row's main_id + aliases) hits a per-component catalog row keyed on a designation the base dict
    lacks (e.g. ``* alf Cen`` resolves the ``* alf Cen A`` row). CR-14.3 (M1) hoist —
    ``exclusion_system._augment_designations`` delegates to this."""
    d = dict(designations) if isinstance(designations, dict) else {}
    for i, x in enumerate(sorted(v for v in extra_ids if v)):
        d[f"_component_id_{i}"] = x
    return d


def resolve_component_mass(spec, catalog, allow_flame=True, status_out=None):
    """Resolve one component's preferred mass via the CR-11.2 chain. Returns
    ``(mass_solar, mass_provenance, note)`` or ``(None, None, error_str)``.

    manual ``mass_solar`` → ``--star-mass-catalog`` / internal seed (by name+designations) → Gaia FLAME
    (by designations, if allowed) → the ``L^0.2632`` inversion from an explicit ``luminosity_lsun``. A
    pure ``--component`` with only a ``mass_solar`` resolves as ``manual``; a name lets the catalog/FLAME
    tiers fire (so ``--star`` components carry ``catalog``).

    CR-14.3 (L7/M1): hoisted here from ``exclusion_system`` so ``binary-stability-auto`` / the dossier
    ``multiplicity`` section / ``exclusion-system`` all route per-component mass through **one** chain.
    ``exclusion_system._resolve_component_mass`` delegates to this (behavior byte-identical). The FLAME
    imports stay **function-local** so ``stellar_mass`` keeps its clean module-top imports (no cycle).
    """
    lum = spec.get("luminosity_lsun")
    inversion = (lum ** 0.2632) if (isinstance(lum, (int, float)) and not isinstance(lum, bool)
                                    and lum > 0) else None
    name = spec.get("name") or spec.get("id")
    flame_mass = None
    manual = spec.get("mass_solar")
    manual_hit = isinstance(manual, (int, float)) and not isinstance(manual, bool) and manual > 0
    cat_hit = bool(catalog) and smt.match_mass(catalog, name, spec.get("designations")) is not None
    if allow_flame and not manual_hit and not cat_hit and spec.get("designations"):
        try:
            from core import binary, catalog as catmod
            sid = binary.gaia_source_id_from_designations(spec.get("designations"))
            if sid:
                ga = catmod.gaia_astrophysical(source_id=sid)
                params = ga.get("parameters") if isinstance(ga, dict) else None
                if params:
                    mf = params.get("mass_flame")
                    if isinstance(mf, (int, float)) and not isinstance(mf, bool) and mf > 0:
                        flame_mass = mf
                # CR-19: a bounded per-component FLAME call (timeout/unreachable) with no mass →
                # record it so the caller can flag the mass-path degrade (else None → byte-identical).
                if flame_mass is None and status_out is not None and isinstance(ga, dict) \
                        and ga.get("gaia_bound_reason"):
                    status_out["flame_status"] = ga["gaia_bound_reason"]
        except Exception:
            flame_mass = None
    block = resolve_mass(
        inversion, sp_type=spec.get("sp_type") or spec.get("class"), main_id=name,
        designations=spec.get("designations"), manual_mass=manual if manual_hit else None,
        catalog=catalog, flame_mass=flame_mass)
    if block["mass_solar"] is None:
        return None, None, (f"component '{name or '?'}' has no resolvable mass "
                            "(give mass=<M☉>, a catalogued name, or lum=<L☉>)")
    return block["mass_solar"], block["mass_provenance"], block["note"]


def recompute_sma_kepler3(sma, sel_mtot, pref_mtot):
    """CR-15.3 (shared): recompute a binary sma at the SAME observed period from the PREFERRED masses
    (``a ∝ M_tot^(1/3)``). Returns ``sma`` unchanged when any operand is falsy / non-positive — a no-op
    when the preferred masses equal the orbit-selected masses, or when ``sma`` is None/0. The single copy
    shared by ``binary.stability_from_solutions`` and ``exclusion_system._resolve_system_from_star``;
    **byte-identical** to the two former inline copies (the truthiness guard on ``sma`` is preserved, so a
    None/0 sma passes through rather than crashing)."""
    if sma and sel_mtot > 0 and pref_mtot > 0:
        return sma * (pref_mtot / sel_mtot) ** (1.0 / 3.0)
    return sma


def resolve_binary_components(primary_sl, sel, catalog, allow_flame=True, system_name=None,
                              status_out=None):
    """CR-14.3 orchestrator: resolve the **preferred** masses of a binary's two components (A + B)
    through the shared chain, matching ``exclusion_system._resolve_system_from_star``'s per-component
    derivation so ``binary-stability-auto`` / the dossier ``multiplicity`` section / ``exclusion-system``
    all report the **same** masses for a given star (cross-path consistency #3).

    Args:
      primary_sl : the primary's SIMBAD result dict. **Only ``main_id`` / ``sp_type`` / ``designations``
                   are read**, so a reduced ``{main_id, sp_type, designations}`` dict is a valid input —
                   ``binary_stability_auto`` passes exactly that, built from the orbit identity (CR-15.4).
                   A future tier that reads another key (e.g. ``luminosity_lsun``) MUST widen every caller.
      sel        : the selected-orbit dict from ``binary.select_stability_elements`` — supplies the
                   orbit-mass fallback (``m1_solar``/``m2_solar``/``mass_prov_a``/``mass_prov_b``/``notes``)
                   used when a component has no measured (manual/catalog/FLAME) mass.
      catalog    : a loaded mass catalog (``load_mass_catalog`` result).
      allow_flame: gate the network FLAME tier (kept True on both consumers per WB Q1).
      system_name: the raw star/system name for the empty-``main_id`` component-B fallback
                   (``"{system_name} B"``), matching ``exclusion_system._resolve_system_from_star``'s
                   fallback so both paths derive the identical component-B id (CR-15.2 cross-path consistency).

    Returns ``(m1, prov_a, m2, prov_b, notes)`` — the FINAL per-component masses (measured tier, else the
    orbit fallback) + provenance + any orbit-flag notes. The secondary designation is derived with the
    shared ``component_candidate_ids`` (the same "star B" derivation exclusion uses); one SIMBAD lookup
    for the secondary. Class/sp_type never change the resolved mass *value* — only the caution flag — so
    the values match exclusion's even though this orchestrator omits the WD/BD class tag.
    """
    main_id = primary_sl.get("main_id") if isinstance(primary_sl, dict) else None

    prim_spec = {"name": main_id, "sp_type": primary_sl.get("sp_type"),
                 "designations": augment_designations(primary_sl.get("designations"),
                                                      component_candidate_ids(main_id, "A"))}
    _sa = {}
    m1, prov_a, _n = resolve_component_mass(prim_spec, catalog, allow_flame=allow_flame, status_out=_sa)
    if m1 is None:
        m1, prov_a = sel.get("m1_solar"), sel.get("mass_prov_a")

    # CR-15.2: on an empty/None main_id, fall back to "{system_name} B" (matching exclusion_system) so
    # both paths derive the identical component-B id — not None (which skipped the B lookup → orbit split).
    comp_id = next(iter(component_candidate_ids(main_id, "B")),
                   (f"{system_name} B" if system_name else None))
    comp_sp = comp_desig = None
    if comp_id:
        from core import databases
        comp_sl = databases.compute_simbad_lookup(comp_id)
        if isinstance(comp_sl, dict) and "error" not in comp_sl:
            comp_sp = comp_sl.get("sp_type")
            comp_desig = comp_sl.get("designations")
    comp_spec = {"name": comp_id, "sp_type": comp_sp,
                 "designations": augment_designations(comp_desig, {comp_id} if comp_id else set())}
    b_orbit = False
    _sb = {}
    m2, prov_b, _n = resolve_component_mass(comp_spec, catalog, allow_flame=allow_flame, status_out=_sb)
    if m2 is None:
        m2, prov_b, b_orbit = sel.get("m2_solar"), sel.get("mass_prov_b"), True

    # The orbit-flag notes (from _mass_flags) describe the SECONDARY / the pair (they key off prov_b —
    # equal-split / SB1-min), so attach them only when B itself is orbit-derived. When only A falls back
    # (prov_a is the clean "binary_orbit_m1", which carries no caution) they would mislabel a measured B
    # (code-review finding 3).
    notes = list(sel.get("notes") or []) if b_orbit else []
    # CR-19: surface a bounded per-component FLAME degrade via the side channel (return arity unchanged →
    # a caller that passes no status_out is byte-identical). Degrade-branch only.
    if status_out is not None:
        if _sa.get("flame_status"):
            status_out["flame_status_a"] = _sa["flame_status"]
        if _sb.get("flame_status"):
            status_out["flame_status_b"] = _sb["flame_status"]
    return m1, prov_a, m2, prov_b, notes


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
