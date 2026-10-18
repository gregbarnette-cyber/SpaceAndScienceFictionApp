"""CR-24's additive output keys, stripped by name for the byte-identity (A0) comparisons — shared by the CR-24 A0
test and the CR-31 snapshot test (stage 3 on; plan §5, CP0 F-B6b)."""

CR24_KEYS = frozenset({
    # V_ISM + range fields (§CR-24.5)
    "v_cloud_used", "v_cloud_chi2", "v_ism_derived_kms", "v_ism_range_kms", "clic_domain", "m_f",
    "wall_range_vism_au", "wall_route_provisional", "verdict_marginal_reasons",
    # velocity fields
    "velocity_provenance", "velocity_status", "space_velocity",
    # the D6 medium echo on exclusion-system components (exclusion-boundary already carries it — compared as-is there)
    # — stripped only inside zones[].components[] (see strip())
    # zone fields (§CR-24.4)
    "combined_wind_wall_route", "combined_wind_wall_band_wind_routes", "combined_wind_route_comparator_au",
    "combined_wind_route_geometry_marginal", "combined_wind_medium_member", "combined_wind_route_provisional",
    "combined_wind_wall_range_vism_au",
})
D6_ECHO_KEYS = frozenset({
    "wind_speed_kms", "wind_speed_provenance", "v_ism_kms", "v_ism_provenance", "c_ms_kms", "c_ms_provenance",
    "n_cloud_cm3", "n_cloud_provenance", "cloud_temp_k", "cloud_temp_provenance", "wind_phase_yr",
    "wind_phase_provenance", "f_shock", "f_shock_provenance", "m_shock_min", "m_shock_min_provenance",
    "mass_loss_source", "mass_loss_source_provenance", "b_field_ug", "c_ms_band_derived",
})


def strip(obj, _in_component=False):
    """A deep copy of a query.py payload without CR-24's additive keys (and, inside exclusion-system components,
    without the D6 echo keys — ``mass_loss_msun_yr`` / ``mass_loss_provenance`` were already there and are kept)."""
    if isinstance(obj, dict):
        drop = CR24_KEYS | (D6_ECHO_KEYS if _in_component else frozenset())
        out = {}
        for k, v in obj.items():
            if k in drop:
                continue
            out[k] = strip(v, _in_component=(k == "components")) if k == "components" else strip(v)
        return out
    if isinstance(obj, list):
        return [strip(x, _in_component) for x in obj]
    return obj


# ── CR-27 (plan §4.8, CP0 F-C H1): the pre-CR-27 baselines are kept, not re-recorded ──────────────────────────────
CR27_KEYS = frozenset({"system_entry", "luminosity_provenance", "luminosity_status"})
_LUM_PROVS = {None, "manual", "regions_bc", "gaia_flame", "spectral_type_table", "object_preset"}


def cr27_normalise(test, args, payload, baseline):
    """Assert CR-27's invariants on a no-lookup payload, then return ``(payload, baseline)`` with CR-27's additive keys
    dropped: ``system_entry`` is null on every such result; ``luminosity_provenance`` is a known value; and a bare
    ``--mass-msun`` run with no ``--luminosity-lsun`` reports ``luminosity_lsun: null`` where the pre-CR-27 baseline
    carried the fabricated 1.0 (the one deliberate value change — the key is then dropped from both sides)."""
    payload, baseline = dict(payload), dict(baseline)
    if "error" not in payload:
        test.assertIn("system_entry", payload)
        test.assertIsNone(payload["system_entry"])
        test.assertNotIn("luminosity_status", payload)              # no fetch on a no-lookup path
        if "luminosity_lsun" in payload:                             # the provenance rides exactly beside it (Q4)
            test.assertIn("luminosity_provenance", payload)
            test.assertIn(payload["luminosity_provenance"], _LUM_PROVS)
            test.assertEqual(payload["luminosity_provenance"] is None, payload["luminosity_lsun"] is None)
            supplied = any(a == "--luminosity-lsun" or a.startswith("--luminosity-lsun=") for a in args)
            if supplied:
                test.assertEqual(payload["luminosity_provenance"], "manual")
        else:
            test.assertNotIn("luminosity_provenance", payload)
    for k in CR27_KEYS:
        payload.pop(k, None)
    bare = (bool(args) and args[0] == "exclusion-boundary"
            and any(a == "--mass-msun" or a.startswith("--mass-msun=") for a in args)
            and not any(a == "--luminosity-lsun" or a.startswith("--luminosity-lsun=") for a in args))
    if bare and "luminosity_lsun" in baseline:
        test.assertEqual(baseline["luminosity_lsun"], 1.0)
        test.assertIsNone(payload.get("luminosity_lsun"))
        payload.pop("luminosity_lsun", None)
        baseline.pop("luminosity_lsun", None)
    return payload, baseline


# ── CR-30 (plan §13.6 T6): the pre-CR-30 baselines are kept, not re-recorded ──────────────────────────────────────
# CR-30's additive keys are stripped by name; a ``--spectral-type`` case (``mass_provenance: spectral_type_table``)
# moves by design (CR-30.2: S1's mass and luminosity at the type) — ``cr30_run`` REPLAYS it with the S1 lookup
# returning the baseline's own (pre-CR-30 table) mass and luminosity, so every other key must still equal the
# baseline byte-for-byte, and separately asserts the real run reads S1.
CR30_KEYS = frozenset({
    "sp_type_raw", "sp_type_read", "lum_class_token", "subdwarf_flag", "gravity_designation", "low_gravity_class",
    "s1_class_v_flag", "subtype_unknown", "subtype_span_note", "s1_rows", "s1_fraction",
    # CR-30.6: the placement object (top level and per component) and the age echo — asserted in test_cr30_*
    "placement", "age_input", "cr30_disclosures",
})


def cr30_strip(obj):
    if isinstance(obj, dict):
        return {k: cr30_strip(v) for k, v in obj.items() if k not in CR30_KEYS}
    if isinstance(obj, list):
        return [cr30_strip(x) for x in obj]
    return obj


def cr30_run(test, case, run):
    """``run(*args) -> (code, payload, err)``. Returns the payload to compare with ``case["payload"]`` (CR-30 keys
    stripped). For a ``spectral_type_table`` baseline: the replay under the baseline's own mass / L (and its
    ``object`` key), plus the S1 assertion on the real run."""
    import math
    from unittest import mock
    from core import ms_sequence, regions
    base = case["payload"]
    code, payload, err = run(*case["args"])
    if not (isinstance(base, dict) and base.get("mass_provenance") == "spectral_type_table"):
        return code, cr30_strip(payload), err
    sp = case["args"][case["args"].index("--spectral-type") + 1]
    s1 = ms_sequence.s1_at(sp)
    test.assertAlmostEqual(payload["mass_msun"], s1["Msun"], places=12)          # the real run reads S1
    real_lookup = regions._lookup_s1

    def _old_table(sp_str):
        r, p = real_lookup(sp_str)
        r = dict(r, Msun=base["mass_msun"], sp_type_read=base["object"])
        if base.get("luminosity_lsun") is not None:
            r["L_lsun"] = base["luminosity_lsun"]
            r["logL"] = math.log10(base["luminosity_lsun"])
        return r, p
    with mock.patch.object(regions, "_lookup_s1", _old_table):
        code2, payload2, err2 = run(*case["args"])
    return code2, cr30_strip(payload2), err2
