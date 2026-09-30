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
