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
