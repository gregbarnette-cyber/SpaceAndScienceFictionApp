# Integration Tool Documentation — `query.py`

`query.py` is a thin JSON dispatcher at the repo root. It allows the `scifiWorldBuilding-Claude` repo (the current consumer — it sits alongside this checkout under `.../Claude/` and calls in through its `bin/sfq` wrapper; formerly the `ScienceFictionResearch-Claude` repo) and any other caller to invoke `core/` functions via a Bash command and receive structured JSON on stdout without needing a copy of the core code.

## Invocation

```bash
# Using the repo's venv directly (preferred from external repos):
# NOTE: the base folder is named "claude" on some machines and "Claude" on others.
# Linux paths are case-sensitive, so try both casings if one fails:
/home/greg/claude/SpaceAndScienceFictionApp/venv/bin/python \
  /home/greg/claude/SpaceAndScienceFictionApp/query.py \
  <subcommand> [arguments]
# or, if that path does not exist:
/home/greg/Claude/SpaceAndScienceFictionApp/venv/bin/python \
  /home/greg/Claude/SpaceAndScienceFictionApp/query.py \
  <subcommand> [arguments]

# From within this repo:
python query.py <subcommand> [arguments]
```

**Shell note (zsh on WSL2).** Callers driving `query.py` from the Bash tool are running **zsh**, which does
**not** word-split unquoted variables the way bash does. A loop like
`for pair in "10000 1.48e-3" ...; do set -- $pair` will leave `$1` = the whole string and `$2` empty
(failing *silently* — e.g. an empty `--luminosity` that breaks the output JSON parse). For multi-value
recompute loops use `read t l <<< "$pair"`, `${=pair}`, real arrays, or one invocation per case. Also: the
Bash tool's working directory resets between calls, so use the absolute venv/`query.py` paths above rather
than relying on a prior `cd`.

## Output and exit codes

- Always writes JSON to **stdout** — result dict (or list for `habitable-zone`) on success, `{"error": "..."}` on failure.
- Exits **0** on success, **1** on error.
- Output is pretty-printed: `json.dumps(result, indent=2, default=str)`. `default=str` ensures numpy/astropy masked values from archive queries are serialized as strings rather than crashing.
- astroquery warnings (e.g. `NoResultsWarning`) go to **stderr** and do not affect stdout JSON.

## Quick reference

Every success result is a JSON **dict** unless noted. Every failure is `{"error": "<message>"}` with exit code 1. Always check for an `"error"` key before reading other fields.

| Subcommand | Required args | Network | Output top-level keys (success) |
|---|---|---|---|
| `simbad-lookup` | `--star` | SIMBAD | `main_id, ra, dec, sp_type, plx_value, teff, vmag, ly, parsecs, designations, desig_str, gcns` (`gcns` optional — Phase M5, `null` when absent) |
| `star-regions` | `--star` | SIMBAD + Hypatia | region values (see below) + `simbad` + `hypatia` |
| `star-regions-manual` | `--vmag --bc --teff --parallax` [`--sunlight-intensity --bond-albedo`] | none | flat dict of region values (`hzil, hzol, snowLine, stellarMass, distAU, …`) + echoed inputs |
| `distance` | `--star1 --star2` | SIMBAD† | `star1_info, star2_info, distance_ly, distance_au` |
| `stars-within-sol` | `--ly` | none (local DB) | `limit_ly, count, stars[]` |
| `stars-within-star` | `--star --ly` | SIMBAD | `center, center_x/y/z, limit_ly, count, stars[]` |
| `travel-time` | `--star1 --star2` + (`--ly-hr` \| `--times-c`) | SIMBAD† | `origin_info, dest_info, distance_ly, ly_hr, times_c, total_hours, travel_time_str` |
| `habitable-zone` | `--teff --luminosity` | none | **list** of 6 zone dicts (not a dict) |
| `exoplanets` | `--star` | SIMBAD + archives | `simbad, planets[], hwo, exocat` |
| `planetary-systems` | `--star` | SIMBAD + archive | `simbad, planets[]` |
| `hwo-exep` | `--star` | SIMBAD + archive | `simbad, hwo[]` |
| `mission-exocat` | `--star` | SIMBAD (then local DB) | `simbad, exocat` |
| `hwc` | `--star` | SIMBAD (then local DB) | `simbad, star_row, planet_rows[]` |
| `hypatia-data` | `--star` | SIMBAD + Hypatia | `star_name, properties, abundances[]` |
| `gcns-within-sol` | `--ly` [`--wd-prob-min --wd-prob-max`] | none (local DB) | `limit_ly, count, snapshot_date, gcns_version, stars[]` |
| `gcns-source` | `--id` | none (local DB) | `snapshot_date, gcns_version, star` |
| `gcns-system` | `--id` | none (local DB) | `snapshot_date, gcns_version, query_source_id, system` |
| `gcns-distance` | (`--star1`\|`--id1`) (`--star2`\|`--id2`) | SIMBAD‡ (local DB) | `star1_info, star2_info, distance_ly, distance_au, snapshot_date, gcns_version` |
| `gcns-travel-time` | (`--star1`\|`--id1`) (`--star2`\|`--id2`) + (`--ly-hr`\|`--times-c`) | SIMBAD‡ (local DB) | `origin_info, dest_info, distance_ly, ly_hr, times_c, total_hours, travel_time_str, snapshot_date, gcns_version` |
| `gcns-stars-within-star` | (`--star`\|`--id`) `--ly` | SIMBAD‡ (local DB) | `center, center_x/y/z, limit_ly, count, snapshot_date, gcns_version, stars[]` |
| `roche-limit` | `--primary-mass-earth --satellite-density` [`--primary-radius-earth`] | none | `rigid_km, rigid_au, fluid_km, fluid_au, primary_density_gcc, …` |
| `tidal-locking` | `--primary-mass-earth --satellite-mass-earth --sma-km --rotation-hours` [`--rigidity-pa --tidal-q`] | none | `lock_time_years, lock_time_gyr, satellite_radius_km, …` |
| `hill-sphere` | `--star-mass-solar --planet-mass-earth --sma-au` [`--eccentricity --moon-inclination-deg --retrograde`] | none | `hill_radius_km, hill_radius_au, stable_orbit_limit_km/au, stable_fraction, stable_moon_limit_km/au, …` |
| `binary-stability` | `--mass1-solar --mass2-solar --binary-sma-au --test-sma-au` [`--eccentricity`] | none | `mass_ratio, stype_critical_sma_au, ptype_critical_sma_au, orbit_type, is_stable, …` |
| `atmosphere-retention` | `--planet-mass-earth --planet-radius-earth --temperature-k` | none | `v_escape_kms, gases[]` |
| `trojan-stability` | `--host-mass-earth --companion-mass-earth --star-mass-solar` | none | `mass_ratio, criterion, stable` |
| `lorentz-factor` | `--velocity-c` | none | `velocity_c, lorentz_factor, time_dilation_pct` |
| `circumbinary-hz` | (`--teff1 --lum1 --teff2 --lum2`) \| (`--star1 --star2`) | none \| SIMBAD (`--star`) | `combined_lum, eff_teff, out_of_range_teff, zones[]` |
| `cooling-hz` | `--track {wd,bd}` [`--mass-solar`\|`--mass-mjup` · one of `--teff`\|`--cooling-age-gyr`\|`--sma-au` · `--chz-threshold-gyr --hz-edge --age-max-gyr --satellite-density`] | none (bundled cooling table) | mode 1: `teff_k, lum_lsun, radius_rsun, zones[], out_of_range_teff`; mode 2: `ever_habitable, entry/exit_age_gyr, residence_gyr`; mode 3: `chz_inner/outer_au, inner_edge_roche_limited, roche_limit_au`; all: `mode, model_note, any_out_of_range, hz_model_valid_teff_k` |
| `rv-semi-amplitude` | `--planet-mass-earth --star-mass-solar` (`--period-days`\|`--sma-au`) [`--ecc --inclination-deg`] | none | `k_ms, period_days, sma_au, ecc, inclination_deg` |
| `transit-signal` | `--planet-radius-earth --star-radius-solar` (`--sma-au` \| `--period-days --star-mass-solar`) | none | `depth_ppm, depth_frac, transit_prob, duration_hours, sma_au, period_days` |
| `astrometric-signal` | `--planet-mass-earth --star-mass-solar --sma-au --distance-pc` | none | `signal_microarcsec, signal_arcsec` |
| `direct-imaging` | `--sma-au --distance-pc --planet-radius-earth` [`--albedo --telescope-diameter-m --wavelength-um`] | none | `angular_sep_arcsec, contrast_reflected, iwa_arcsec, resolvable` |
| `tidal-heating` | `--primary-mass-earth --satellite-radius-km --sma-km --ecc` [`--k2 --tidal-q`] | none | `heating_power_w, surface_flux_wm2, mean_motion_rad_s, io_flux_ratio` (order-of-mag) |
| `kozai-lidov` | `--m1-solar --m2-solar --m3-solar` (`--period-inner-yr --period-outer-yr` \| `--sma-inner-au --sma-outer-au`) [`--ecc-outer`] | none | `timescale_years` (order-of-mag) |
| `relativistic-brachistochrone` | `--accel-g --distance-ly` | none | `coord_time_yr, proper_time_yr, peak_velocity_c, peak_lorentz_factor` |
| `rocket-equation` | two of (`--delta-v-kms`\|`--beta`) · (`--exhaust-velocity-kms`\|`--isp-s`\|`--fuel`) · `--mass-ratio` [`--relativistic --legs {flyby,rendezvous,round-trip} --payload-mass-t --structure-fraction`] | none (bundled fuel presets) | `mass_ratio, mass_ratio_single_burn, propellant_fraction, delta_v_kms, beta, exhaust_velocity_kms, isp_s, fuel, legs, relativistic, payload_mass_t, propellant_mass_t, wet_mass_t, structure_fraction, model_note` |
| `beam-sail` | `--beam-power-w` (`--sail-mass-kg` \| `--areal-mass-gm2 --sail-area-m2`) [`--payload-mass-kg --reflectivity --wavelength-nm --transmit-aperture-m` · (`--accel-distance-au`\|`--accel-time-days`)] | none | `thrust_n, acceleration_ms2, final_velocity_kms, beta, beam_energy_j, sail_area_m2, total_mass_kg, sail_mass_kg, payload_mass_kg, reflectivity, beam_range_note, model_note` |
| `magsail` | (`--velocity-kms` \| `--beta`) + ((`--coil-current-a --coil-radius-m`) \| `--magnetic-moment-am2`) [`--ism-density-cm3 --ion-mass-amu --standoff-coeff --drag-coeff --vehicle-mass-t --velocity-final-kms --ionization-fraction`] | none (bundled ISM/coeffs) | `magnetopause_radius_km, magnetopause_radius_farfield_km, ram_pressure_pa, effective_area_km2, drag_force_n, drag_scaling_note, deceleration_ms2, stopping_distance_ly, stopping_time_yr, near_field_warning, magnetic_moment_am2, ionization_fraction, ism_mass_density_kgm3, ionization_note, model_note` |
| `ramscoop` | (`--velocity-kms` \| `--beta`) + ((`--coil-current-a --coil-radius-m`) \| `--scoop-area-km2` \| `--magnetic-moment-am2`) + ((`--fuel {pp,cno,dd}` [`--fusion-efficiency`]) \| `--exhaust-velocity-kms`) [`--ism-density-cm3 --ion-mass-amu --standoff-coeff --drag-coeff --ionization-fraction`] | none (bundled ISM/fusion) | `collected_mass_flux_kgs, magnetopause_radius_km, scoop_area_km2, exhaust_velocity_kms, exhaust_beta, reaction_thrust_n, collection_drag_n, magnetic_drag_n, net_force_n, verdict, crossover_velocity_kms, fusion_yield_fraction, fusion_efficiency, ionization_fraction, ionization_note, model_note` |
| `pellet-stream` (AD C2) | `--stream-velocity-kms` + (`--mass-flow-rate-kgs` \| `--pellet-mass-kg --pellet-rate-hz`) + (`--velocity-kms` \| `--beta`) [`--coupling {reflect,absorb}` (default reflect) `--vehicle-mass-t`] | none | `stream_velocity_kms, vehicle_velocity_kms, beta, relative_velocity_kms, mass_flow_rate_kgs, coupling, thrust_n, delivered_power_w, verdict, crossover_velocity_kms, acceleration_ms2, model_note` |
| `dust-impact` (AD C3) | (`--grain-radius-um --grain-density-kgm3` \| `--grain-mass-kg`) + (`--velocity-kms` \| `--beta`) [cumulative set: all of `--dust-density-m3 --frontal-area-m2 --path-length-ly`] | none | `grain_mass_kg, velocity_kms, beta, relativistic, lorentz_factor, impact_energy_j, impact_energy_tnt_kg, momentum_kgms, impacts_total, energy_fluence_j_m2, penetration_handoff_note, model_note` |
| `spin-stress` | (`--material` \| `--density-kgm3 --tensile-strength-mpa`) + one of (`--target-gravity-g` \| `--radius-m` \| `--rpm --radius-m`) [`--safety-factor`] | none (bundled materials) | `material, density_kgm3, tensile_strength_mpa, safety_factor, allowable_stress_mpa, max_tangential_velocity_ms, target_gravity_g, radius_m, rpm, max_radius_m, max_radius_km, max_gravity_g, hoop_stress_mpa, margin, specific_strength_note, notes, model_note` |
| `tether-taper` | (`--material` \| `--density-kgm3 --tensile-strength-mpa`) (`--body` \| `--surface-gravity-ms2 --surface-radius-km --geo-radius-km`) [`--safety-factor`] | none (bundled materials/bodies) | `material, density_kgm3, tensile_strength_mpa, safety_factor, body, surface_gravity_ms2, surface_radius_km, geo_radius_km, characteristic_velocity_ms, characteristic_length_km, taper_ratio, feasible, notes, model_note` |
| `dyson-collector` | (`--luminosity-lsun` \| `--star`) `--fraction --orbit-au` [`--areal-mass-kgm2`] | none \| SIMBAD (`--star`) | `intercepted_power_w, collector_area_m2, collector_area_au2, collector_mass_kg, incident_flux_wm2, fraction, orbit_au, luminosity_lsun, areal_mass_kgm2, model_note` |
| `orbital-ring` (AD C4) | (`--body` \| `--surface-gravity-ms2 --body-radius-km`) `--altitude-km --ring-mass-per-length-kgm` [`--rotor-mass-per-length-kgm`] | none (bundled `_BODIES`) | `orbital_radius_km, local_gravity_ms2, orbital_velocity_kms, rotor_velocity_kms, rotor_velocity_over_orbital, ring_mass_per_length_kgm, rotor_mass_per_length_kgm, support_ratio, rotor_ke_per_length_jm, model_note` |
| `par-flux` | one Teff (`--teff-k` \| `--spectral-type` \| `--star`) + one insolation (`--insolation-wm2` \| `--luminosity-lsun --distance-au`) [`--par-band-nm LO HI` `--sed blackbody\|real` (AD C1)] | none \| SIMBAD (`--star`) | `teff_k, par_fraction, insolation_wm2, par_irradiance_wm2, ppfd_umol_m2_s, par_deficit_vs_g2, photon_energy_mean_j, j_per_umol, band_nm, sed_model, feeds_note, model_note` |
| `equilibrium-temp` | one insolation (`--insolation-wm2` \| `--luminosity-lsun --distance-au`) + **at most one** forcing (`--greenhouse-delta-k` \| `--optical-depth` \| `--target-surface-k`) [`--albedo`] | none | `insolation_wm2, albedo, t_eq_k, greenhouse_delta_k, optical_depth, t_surface_k, required_forcing, regime, model_note` |
| `insolation-shift` | `--planet-radius-km --delta-insolation-wm2` + one flux (`--solar-flux-wm2` \| `--luminosity-lsun --distance-au`) | none | `planet_radius_km, delta_insolation_wm2, solar_flux_wm2, mode, mirror_area_m2, mirror_area_km2, area_vs_planet_cross_section, model_note` |
| `atmosphere-mass` | `--planet-radius-km` + one gravity (`--surface-gravity-ms2` \| `--planet-mass-earth`) + one of (`--pressure-bar` \| `--volatile-mass-kg`) [`--species`] | none | `planet_radius_km, surface_gravity_ms2, species, surface_pressure_bar, atmosphere_mass_kg, atmosphere_mass_earth_atm, model_note` |
| `volatile-delivery` (AD C5) | `--body-mass-kg` [`--volatile-fraction` · (`--delta-v-kms` + (`--fuel`\|`--exhaust-velocity-kms`)) · `--impact-velocity-kms` · `--target-atmosphere-mass-kg`] | none | `body_mass_kg, volatile_fraction, delivered_volatile_mass_kg, delta_v_kms, redirect_mass_ratio, impact_velocity_kms, impact_energy_j, impact_energy_tnt_kg, target_atmosphere_mass_kg, bodies_needed, model_note` |
| `waste-heat` | steady: (`--input-power-watts`\|`--useful-power-watts`) [`--efficiency` \| `--hot-temp-k --cold-temp-k`]; **transient (C9)**: all of `--peak-w --mean-w --duty --pulse-period-s --storage-mass-kg --specific-heat-jkgk` | none | steady: `waste_heat_w, useful_power_w, input_power_w, efficiency, carnot_efficiency, carnot_min_waste_heat_w, carnot_limited, notes`; transient: `mode, on_time_s, excess_power_w, heat_capacity_j_per_k, temp_swing_k, buffer_time_s, notes` |
| `radiator-area` | (`--heat-watts` \| `--input-power-watts --efficiency`) `--radiator-temp-k` [`--emissivity --sides --sink-temp-k --areal-mass-kgm2`] | none | `radiator_area_m2, radiator_area_km2, flux_wm2, blackside_flux_wm2, heat_watts, radiator_mass_kg, scaling_note` |
| `shielding-attenuation` | photon/gcr: (`--areal-density-gcm2` \| `--thickness-cm --density-gcm3`) + coeff (`--mass-atten-coeff-cm2g`\|`--attenuation-length-gcm2`\|`--material [--energy-mev]`) [`--mode {photon,gcr}`]; **charged (C6)** `--particle {proton,alpha,ion} --energy-mev` (`--material`\|`--csda-range-gcm2`); **stack (C7)** `--layers "mat:gcm2,…"` | none (bundled XCOM/PSTAR) | photon: `transmitted_fraction, half_value_layer_gcm2, tenth_value_layer_gcm2, …, is_order_of_magnitude`; csda: `mode:"csda", csda_range_gcm2, csda_range_cm, stops_primary, penetrates, residual_range_gcm2`; layers: `layers[], total_transmitted_fraction, total_attenuation` |
| `active-shield` | `--shield-radius-m` + one field source (`--magnetic-moment-am2` \| `--coil-current-a --coil-radius-m` \| `--field-tesla --field-radius-m`) [`--spectrum-characteristic-rigidity-gv`] | none | `rigidity_cutoff_gv, rigidity_cutoff_v, magnetic_field_t, magnetic_moment_am2, field_source, deflected_fraction, is_order_of_magnitude, model_note` |
| `spin-comfort` | exactly two of (`--radius-m` \| `--rpm` \| `--gravity-g`\|`--accel-ms2` \| `--tangential-velocity-ms`) [`--occupant-height-m --walk-speed-ms --criteria {conservative,moderate,relaxed,all}` + per-threshold overrides] | none (bundled comfort bands) | `radius_m, rpm, angular_velocity_rads, accel_ms2, gravity_g, tangential_velocity_ms, head_gravity_g, gravity_gradient_pct, coriolis_ratio_pct, anchors, criteria{…}, overridden_thresholds, model_note, notes` |
| `life-support` | [`--crew --days --closure-scenario {open,iss,advanced,bioregen}` + per-stream `--*-closure` + per-rate `--*-rate`/`--kcal-per-day`] | none (bundled BVAD Rev2) | `crew, days, per_person_daily{…}, totals{…}, closure{water,o2,food}, scenario, makeup_mass_kg{o2,water,food,total}, model_note` |
| `bioregen-area` | exactly one light anchor (`--ppfd-umol` \| `--dli-mol` \| `--par-wm2`) [`--kcal-per-day --crew --crop` \| **`--crops "c:f,…"` (AD C10)** ` --photoperiod-h --photo-efficiency --harvest-index --artificial --led-par-efficiency --f-edible-energy`] | none (bundled crops) | `area_m2_per_person, area_m2_total, area_m2_per_person_measured, crops, per_crop_area_m2[], dli_mol, ppfd_umol, photo_efficiency, harvest_index, lighting{…}, crop_gas_exchange{o2_kg_day,co2_kg_day}, transpiration_water_kg_day, par_is_input_note` |
| `population-capacity` | ≥1 budget of (`--crop-area-m2` \| `--power-w` \| `--water-kg-day` \| `--fixed-nitrogen-kg-yr` \| `--food-dry-kg-day`) [per-person `--per-person-*` overrides] | none (X1/X2 defaults) | `per_resource{…{budget,per_person,source,population}}, sustainable_population, binding_constraint, slack{…}` |
| `solvent-zone` | `--luminosity` + (`--solvent NAME` \| `--t-low --t-high`) [`--albedo`] | none | `solvent, name, inner_au, outer_au, inner_lm, outer_lm, s_eff_inner, s_eff_outer, t_eq_inner, t_eq_outer, pressure_conditional, assumed_pressure_atm, citation, t_ref_k` |
| `ice-lines` | `--luminosity` [`--albedo`] | none | `luminosity_solar, albedo, t_ref_k, lines[]` |
| `dossier` | `--star` [`--fmt markdown\|html\|json` `--sections …`] | SIMBAD + NASA + Hypatia (none for `Sol`/`Sun`) | `star, fmt, sections, warnings, notes` + `document` (md/html) \| `data` (json) |
| `generate-system` | `--seed` [`--anchor-star` `--spectral-class` `--planets` `--require-habitable` `--constraint…` `--companion` `--nbody` `--research-policy`] | none (synthetic) · SIMBAD + NASA + HWC (with `--anchor-star`) | `seed, mode, anchor_star, star, planets[], warnings, notes` — plus `feasible, constraints[]` with `--constraint` |
| `habitable-zone-sma` | `--teff --luminosity --sma` | none | `zones[], planet_seff, verdict` |
| `star-luminosity` | `--radius --teff` | none | `radius, temp, luminosity` |
| `stellar-evolution` | `--mass-solar` [`--current-age-gyr`] | none | `stages[], total_gyr, ms_end_gyr, current_stage, low_mass, high_mass` |
| `brachistochrone-au` | `--accel-g --au` | none | `accel_g, distance_au, distance_lm, profiles[]` |
| `brachistochrone-lm` | `--accel-g --lm` | none | `accel_g, distance_au, distance_lm, profiles[]` |
| `distance-at-acceleration` | `--accel-g --hours` | none | `accel_g, hours, travel_time_str, profiles[]` |
| `ly-hr-to-times-c` | `--ly-hr` | none | `ly_hr, times_c` |
| `times-c-to-ly-hr` | `--times-c` | none | `times_c, ly_hr` |
| `distance-traveled-ly-hr` | `--ly-hr --hours` | none | `ly_hr, hours, distance_ly` |
| `distance-traveled-times-c` | `--times-c --hours` | none | `times_c, ly_hr, hours, distance_ly` |
| `travel-time-ly-hr` | `--distance-ly --ly-hr` | none | `distance_ly, ly_hr, times_c, total_hours, travel_time_str` |
| `travel-time-times-c` | `--distance-ly --times-c` | none | `distance_ly, times_c, ly_hr, total_hours, travel_time_str` |
| `travel-time-solar` | `--origin --destination --accel-g` [`--v-cap-pct --date`] | **JPL Horizons (live)** | `origin, destination, accel_g, distance_au, distance_lm, v_cap_pct, departure_date, profiles[], …` |
| `optimal-tour` | `--stars N [N …]` (`--ly-hr` \| `--times-c`) [`--closed` `--weight dust --map --dust-step-pc`] | SIMBAD† (names) | `legs[], total_ly, total_time, naive_total_ly, optimized_total_ly, saved_ly, saved_pct, closed, stars[]` |
| `jump-route` | `--origin --destination --max-jump` [`--optimize distance\|jumps` `--weight distance\|dust\|`**`blend`**` --alpha --beta --map --dust-step-pc`] | SIMBAD† (names) | `origin_info, dest_info, reachable, jumps, total_ly, direct_ly, route[], stars[]`; blend adds `weight:"blend", alpha, beta, total_av, total_blend_cost` |
| `jump-network` | `--start --max-jump` [`--max-jumps`] | SIMBAD† (names) | `start_name, max_tier, reachable_count, total_in_pool, unreachable_count, tiers[], stars[]` |
| `multi-stop` | `--stars N [N …]` (`--ly-hr` \| `--times-c`) [`--weight dust --map --dust-step-pc`] | SIMBAD† (names) | `legs[], total_ly, total_hours, total_time, stars[]` |
| `nearest-neighbor` | `--start --hops --max-ly` [`--weight dust --map --dust-step-pc`] | SIMBAD† (names) | `chain[], stars[], total_ly, stopped_early, start_name` |
| `farthest-first` | `--start --stops` [`--max-reach`] | SIMBAD† (names) | `chain[], tree_edges[], stars[], widest_ly, stopped_early, start_name` |
| `trade-route` | `--stars N [N …]` [`--weight dust --map --dust-step-pc`] | SIMBAD† (names) | `nodes[], edges[], total_ly, stars[]` |
| `search-star-systems` | _(all optional filters)_ | none (local DB) | `count, capped, cap, stars[]` |
| `search-hwc` | _(all optional filters)_ | none (local DB) | `count, capped, cap, stars[]` |
| `search-exoplanets` | _(all optional filters)_ | **NASA TAP (live)** | `count, capped, cap, stars[]` |
| `search-hypatia` | _(all optional filters)_ | none (local DB) | `count, capped, cap, stars[]` |
| `solar-analogs` | [`--mode twin\|analog --teff-tol --logg-tol --feh-tol --ly-max --gcns-distance`] | none (local DB) | `mode, criteria, population, count, capped, cap, stars[]` |
| `substellar` | [`--ly-max --include-late-m --classes …`] | none (local DB) | `classes, ly_max, count, capped, cap, completeness_note, population, stars[]` |
| `dust-sightline` | one of (`--l --b`)\|(`--ra --dec`)\|(`--star`\|`--id`) `--dist-end` [`--dist-start --steps`\|`--step-pc` `--map`] | none (local dust cache)§ | `map, frame, l, b, dist_start_pc, dist_end_pc, n_steps, bins[], cumulative_a_v(_lo/_hi), units, rv, notes` |
| `dust-between` | (`--star1`\|`--id1`) (`--star2`\|`--id2`) [`--steps`\|`--step-pc` `--map`] | SIMBAD‡ (local dust cache)§ | `map, frame, star1_info, star2_info, separation_pc/ly, n_steps, bins[], cumulative_a_v(_lo/_hi), units, rv, notes` |
| `compare-stars` | `--stars N [N …]` (2–4) | SIMBAD + NASA + Hypatia | `stars[]` (per-star error isolation) |
| `project-list` | _(none)_ | none (local DB) | `projects[]` (name, description, member_count, created_date) |
| `project-get` | `--name` | none (local DB) | `project, members[]` (each member's `generated_spec` echoed parsed) |
| `main-sequence` | _(none)_ | none (local DB) | **list** of 24 spectral-class rows |
| `solar-system` | _(none)_ | none (local DB) | `planets[], moons[], dwarf_planets[], asteroids[]` |
| `sol-regions` | _(none)_ | none | flat dict of Sol region values (`hzil, hzol, snowLine, …`) |
| `orbit-distance` | `--sma --ecc` | none | `sma, ecc, periastron, apastron, ecc_au` |
| `moon-orbital-distance` | `--planet-mass-earth` [`--day-hours`] | none | `planet_mass_earth, day_hours, orbital_distance_km` |
| `gravity-acceleration` | `--rpm --radius-m` | none | `rpm, radius_m, accel_ms2` |
| `gravity-distance` | `--rpm --accel-ms2` | none | `rpm, accel_ms2, radius_m` |
| `gravity-rpm` | `--accel-ms2 --radius-m` | none | `accel_ms2, radius_m, rpm` |
| `travel-time-custom-thrust` | `--origin --destination --accel-g --burn-value` [`--burn-unit --v-cap-pct --date`] | **JPL Horizons (live)** | `origin, destination, distance_au, …, travel_time_str, …` |

† `distance` and `travel-time` skip the SIMBAD call for an endpoint named `"Sol"`/`"Sun"` (treated as the origin at 0,0,0). The seven Route Planning subcommands (`optimal-tour`, `jump-route`, `jump-network`, `multi-stop`, `nearest-neighbor`, `farthest-first`, `trade-route`) likewise resolve each star **DB-first** (`star_systems.star_name`, offline) then **SIMBAD** for names not in the table; `"Sol"`/`"Sun"` → the origin with no lookup. They read the local `star_systems` table for intermediate/candidate stars (run option 50 to populate it).
‡ The `gcns-*` calculators (and `dust-between`) use SIMBAD **only** for `--star`/`--star1`/`--star2` endpoints (to resolve a name to a position/Gaia id); `--id`/`--id1`/`--id2` endpoints are fully offline. For the `gcns-*` calculators there is **no** `"Sol"`/`"Sun"` special case (Sol is not a GCNS row); `dust-between` **does** treat `Sol`/`Sun` as the origin.

§ A **local read of the fetched dust map cache** (`data/dust/`, populated by CLI **option 59** / the GUI Fetch Dust Map Data panel). Needs the optional `dustmaps` extra (WSL/Linux only) — see the **Dust / ISM** section below. No network for the map query itself.

Shared shapes:
- The `simbad` sub-dict embedded in `star-regions`, `exoplanets`, `planetary-systems`, `hwo-exep`, `mission-exocat`, and `hwc` has the **same shape as `simbad-lookup`'s output** (top-level keys above).
- `planets[]`, `hwo[]`, `exocat`, `star_row`, `planet_rows[]` are dicts/lists of **raw archive or CSV column fields** — for the exact column names see `docs/star-databases.md` (NASA pscomppars, HWO ExEP `di_stars_exep`, Mission Exocat CSV, HWC CSV).

## Subcommands

### Star data

#### `simbad-lookup`
SIMBAD star lookup — returns full star info and all known designations.
```bash
query.py simbad-lookup --star "Tau Ceti"
```
Core function: `databases.compute_simbad_lookup(star)`
Output: `{main_id, ra, dec, sp_type, plx_value, teff, vmag, ly, parsecs, desig_str, designations, gcns}`. `designations` is a dict keyed by catalog (`MAIN_ID, NAME, GJ, HD, HIP, HR, Wolf, LHS, BD, K2, Kepler, KOI, TOI, CoRoT, COCONUTS, HAT_P, WASP, TIC, Gaia EDR3, 2MASS`); a catalog with no id is `null`. Numeric fields may be `null`.
- **Gaia id**: the `"Gaia EDR3"` key holds the Gaia source id as SIMBAD now formats it — `"Gaia DR3 <id>"` (SIMBAD renamed EDR3→DR3 in its id output; the source_ids are identical). To get the bare numeric id, strip the `"Gaia DR3 "` / `"Gaia EDR3 "` prefix. This is the same id used as `--id` for `gcns-source`.
- **`gcns`** (Phase M5): an **optional top-level GCNS cross-reference** — the matching `gcns_stars` row (same shape as `gcns-source`'s `star`: Bayesian `dist_pc` + `dist_lo_pc`/`dist_hi_pc`, `distance_method`, Gaia G/BP/RP, `astrom_reliable_prob`, `wd_prob`, `system_id`/`n_components`, …), giving a Bayesian distance **with 16th/84th-percentile uncertainty** beside the naive `1/ϖ` `ly`/`parsecs`. The key is **always present** but is `null` when the star has no Gaia id, is not in GCNS, or the `gcns_stars` table is empty/missing — **non-fatal and silent** (a single indexed local-DB read; no extra network). Built inside `compute_simbad_lookup`, so every `simbad`-embedding subcommand below carries it too.

#### `star-regions`
Star system regions: HZ boundaries, snow line, stellar mass/luminosity/radius, alternate biochemistry zones, plus Hypatia Catalog stellar properties and elemental abundances.
Uses hardcoded `sunlight_intensity=1.0`, `bond_albedo=0.3`.
```bash
query.py star-regions --star "61 Cygni A"
```
Core functions: `databases.compute_simbad_lookup` → `regions.compute_star_system_regions_from_simbad` + `databases.compute_hypatia_data`

Output: a flat dict of computed region values — stellar (`stellarMass, stellarRadius, bcLuminosity, luminosityFromMass, calculatedLuminosity, temp, …`), distance (`parsecs, lightYears, distAU, distKM`), Earth-equivalent orbit (`planetaryYear, planetaryTemperature{,C,F}, sizeOfSun`), and zone boundaries in AU (`hzil, hzol, snowLine, lh2Line, sysol, sysilGrav, sysilSunlight`, plus the alternate-biochemistry pairs `ffInner/ffOuter, fsInner/fsOuter, prwInner/prwOuter, praInner/praOuter, pmInner/pmOuter, phInner/phOuter`) — plus `spectral_type`, `bc_key`, and the embedded `simbad` dict.
The result dict also includes a top-level `"hypatia"` key: `{"star_name", "properties", "abundances"}` on success, or `{"error": str}` if the Hypatia API call fails. The regions result is always returned even when Hypatia fails.

#### `star-regions-manual`
The **manual-input** variant of `star-regions` (the opt-10 calculation): no SIMBAD, no Hypatia — you supply the six raw inputs directly. Returns the same flat region-values dict as `star-regions`/`sol-regions`, **without** the `spectral_type`/`bc_key`/`simbad`/`hypatia` extras (those come only from the SIMBAD path).
```bash
query.py star-regions-manual --vmag 5.5 --bc -0.1 --teff 5500 --parallax 100
query.py star-regions-manual --vmag 5.5 --bc -0.1 --teff 5500 --parallax 100 --sunlight-intensity 1.0 --bond-albedo 0.9
```
Core function: `regions.compute_star_system_regions(vmag, boloLum, temp, plx, sunlight_intensity=1.0, bond_albedo=0.3)`. `--bc` maps to the function's `boloLum` (bolometric correction); `--sunlight-intensity` / `--bond-albedo` default to `1.0` / `0.3`. **No network.** Output: the echoed inputs (`vmag, boloLum, temp, plx, sunlight_intensity, bond_albedo`) plus every computed region value — stellar (`stellarMass, stellarRadius, bcLuminosity, luminosityFromMass, calculatedLuminosity, …`), distance (`parsecs, lightYears, trigParallax`), Earth-equivalent orbit (`distAU, distKM, planetaryYear, planetaryTemperature{,C,F}, sizeOfSun`), and the zone boundaries (`sysilGrav, sysilSunlight, hzil, hzol, snowLine, lh2Line, sysol` + the alternate-biochemistry pairs `ffInner/ffOuter, …, phInner/phOuter`).
> **Validation:** this wraps a **non-self-validating** legacy function (like the Phase-N pure-compute wrappers). Out-of-range numerics surface as a **raw-exception** `{"error": str(e)}` (exit 1) — e.g. `--parallax 0` → `"division by zero"`, a negative parallax → `"math domain error"` — **not** a curated message; argparse rejects missing/non-numeric args (exit 2). Key on `"error"` + exit code, not the message text.

### Distance and proximity

#### `distance`
3D Euclidean distance in light years between two stars. Use `"Sol"` or `"Sun"` for the solar system origin.
```bash
query.py distance --star1 "Sol" --star2 "GJ 876"
```
Core function: `calculators.compute_distance_between_stars(star1, star2)`
Output: `{star1_info, star2_info, distance_ly, distance_au}`. Each `*_info` is `{name, ra_deg, dec_deg, ly, desig_str, ra_hms, dec_dms}`. `distance_au` is `null` unless the two stars are < 0.5 ly apart.

#### `stars-within-sol`
All stars in the `star_systems` DB table within N light years of Sol. No network call.
```bash
query.py stars-within-sol --ly 15
```
Core function: `calculators.compute_stars_within_distance_of_sol(ly)`
Output: `{limit_ly, count, stars[]}`. Each star: `{"Star Name", "Star Designations", "Spectral Type", "Light Years", app_magnitude, parsecs, x, y, z}` (x/y/z are heliocentric light-year coords, may be `null`; `app_magnitude` = Johnson V, `parsecs` = stored distance — both may be `null`). Sorted ascending by Light Years. *(Phase O F1 added `app_magnitude`/`parsecs` — additive.)*

#### `stars-within-star`
All stars in the `star_systems` DB table within N light years of a named star. Queries SIMBAD for the center star.
```bash
query.py stars-within-star --star "Epsilon Eridani" --ly 5
```
Core function: `calculators.compute_stars_within_distance_of_star(star, ly)`
Output: `{center, center_x, center_y, center_z, limit_ly, count, stars[]}`. Each star: `{"Star Name", "Star Designations", "Spectral Type", "Distance", app_magnitude, parsecs, x, y, z}` (`Distance` in ly from the center star; `app_magnitude` = Johnson V, `parsecs` = `1000/parallax` — both may be `null`). Sorted ascending by Distance. *(Phase O F1 added `app_magnitude`/`parsecs` — additive.)*

### Travel time

#### `travel-time`
FTL travel time between two stars. Supply exactly one of `--ly-hr` or `--times-c`.
```bash
query.py travel-time --star1 "Sol" --star2 "Epsilon Indi" --times-c 100
query.py travel-time --star1 "Sol" --star2 "Epsilon Indi" --ly-hr 0.01
```
Core function: `calculators.compute_travel_time_between_stars(star1, star2, ly_hr=..., times_c=...)`
Output: `{origin_info, dest_info, distance_ly, ly_hr, times_c, total_hours, travel_time_str}`. `*_info` shape matches `distance` above; `travel_time_str` is a human-readable breakdown (e.g. `"5 Months, 24 Days, 11 Hours"`).

### Habitable zone

#### `habitable-zone`
Kopparapu et al. HZ boundaries for all six zones from stellar parameters. Returns a **list** (not a dict) — one entry per zone.
```bash
query.py habitable-zone --teff 4900 --luminosity 0.15
```
Core function: `equations.compute_habitable_zone(teff, luminosity)`
Output: a **list** of 6 dicts, each `{zone_name, key, au, lm, seff}` (`key` ∈ `rv, rg5, rg, rg01, mg, em`; `au`/`lm` are the boundary distance). On bad input still returns `{"error": str}` (a dict, not a list) — check the type/error key.

### Worldbuilding calculators (Phase H — no network)

Five pure-math calculators (`core/equations.py`); see `docs/equations.md` for full formulas, the two formula corrections, and the model-limitation notes. Standard contract: malformed/missing args → argparse **exit 2** (stderr); out-of-range values (≤ 0 where positive required, `e ∉ [0,1)`) → `{"error": str}` on stdout, **exit 1**; success → the core function's dict, **exit 0**.

#### `roche-limit`
Rigid-body and fluid Roche limits for a satellite orbiting a primary.
```bash
query.py roche-limit --primary-mass-earth 1.0 --satellite-density 3.34
query.py roche-limit --primary-mass-earth 317.8 --satellite-density 0.5 --primary-radius-earth 11.2
```
Core function: `equations.compute_roche_limit(primary_mass_earth, satellite_density_gcc, primary_radius_earth=None)`. `--primary-radius-earth` is optional (estimated from mass via `R ∝ M^0.55` if omitted). Output: `{primary_mass_earth, primary_radius_km, primary_density_gcc, satellite_density_gcc, rigid_km, rigid_au, fluid_km, fluid_au}`.

#### `tidal-locking`
Tidal-locking timescale of a satellite (MacDonald 1964 model; order-of-magnitude).
```bash
query.py tidal-locking --primary-mass-earth 1.0 --satellite-mass-earth 0.0123 --sma-km 384400 --rotation-hours 24
```
Core function: `equations.compute_tidal_locking_time(primary_mass_earth, satellite_mass_earth, sma_km, initial_rotation_hours, rigidity_pa=3e10, tidal_q=100)`. `--rigidity-pa` / `--tidal-q` default to `3e10` / `100`. Output: `{…inputs…, satellite_radius_km, lock_time_years, lock_time_gyr}`.

#### `hill-sphere`
Hill sphere (gravitational sphere of influence) of a planet; stable satellite orbits within ~0.5 × Hill radius.
```bash
query.py hill-sphere --star-mass-solar 1.0 --planet-mass-earth 1.0 --sma-au 1.0
query.py hill-sphere --star-mass-solar 1.0 --planet-mass-earth 317.8 --sma-au 5.2 --moon-inclination-deg 30 --retrograde
```
Core function: `equations.compute_hill_sphere(star_mass_solar, planet_mass_earth, sma_au, eccentricity=0, moon_inclination_deg=0, prograde=True)`. `--eccentricity` defaults to 0. Output: `{…inputs…, moon_inclination_deg, prograde, hill_radius_km, hill_radius_au, stable_orbit_limit_km, stable_orbit_limit_au, stable_fraction, stable_moon_limit_km, stable_moon_limit_au}`.
- **Phase T1a — Domingos 2006 exomoon keys (B3, additive).** `--moon-inclination-deg` (default 0, **degrees** — radians internally; valid `0 ≤ i ≤ 180`) and `--retrograde` (store-true → the retrograde fit; default prograde) drive the largest-stable-satellite-orbit estimate of Domingos, Winter & Yokoyama (2006): `stable_moon_limit_au = stable_fraction × hill_radius_au` with `stable_fraction = f`, prograde `f = 0.4895·(1 − 1.0305·e_p − 0.2738·i)`, retrograde `f = 0.9309·(1 − 1.0764·e_p − 0.9812·i)`. **`stable_moon_limit_au` (Domingos) supersedes `stable_orbit_limit_au` (the retained crude 0.5 × r_H heuristic)** as the headline stable-moon radius. With both new args omitted, the pre-existing keys/values are **byte-identical** to before. Out-of-range inclination → `{"error"}` exit 1.

#### `binary-stability`
Planet orbit stability in a binary (Holman & Wiegert 1999). S-type = orbits one star; P-type = circumbinary.
```bash
query.py binary-stability --mass1-solar 1.0 --mass2-solar 0.5 --binary-sma-au 20 --test-sma-au 5
```
Core function: `equations.compute_binary_orbit_stability(mass1_solar, mass2_solar, binary_sma_au, test_sma_au, eccentricity=0)`. Masses are reordered internally so `M1 ≥ M2`. Output: `{mass1_solar, mass2_solar, mass_ratio, binary_sma_au, eccentricity, stype_critical_sma_au, ptype_critical_sma_au, test_sma_au, orbit_type, is_stable, stable_region_description}`.

#### `atmosphere-retention`
Which atmospheric gases a planet retains against Jeans escape (optimistic — uses equilibrium temperature).
```bash
query.py atmosphere-retention --planet-mass-earth 1.0 --planet-radius-earth 1.0 --temperature-k 255
```
Core function: `equations.compute_atmosphere_retention(planet_mass_earth, planet_radius_earth, temperature_k)`. Output: `{planet_mass_earth, planet_radius_earth, temperature_k, v_escape_kms, gases[]}` where each gas is `{gas, mol_mass_amu, lambda, v_thermal_kms, status}` (status ∈ Retained / Escaping slowly / Lost rapidly) for H₂, He, CH₄, H₂O, N₂, O₂, CO₂.

### Research-tooling extensions (Phase T1a — no network)

Three calculators added for the sibling worldbuilding repo (`scifiWorldBuilding-Claude`),
all **self-validating** (Phase-H/P contract: curated `{"error": str}` → exit 1; argparse
→ exit 2; success dict → exit 0). The B3 exomoon model rides on `hill-sphere` (above) and the
E1 white-dwarf filter rides on `gcns-within-sol` (below); both are additive — see those sections.

#### `trojan-stability`
L4/L5 (Trojan) co-orbital linear-stability test (Gascheau 1843 / Routh). Stable when the
co-orbital mass ratio `μ = (m_host + m_companion)/M★ < μ_crit = ½·(1 − √(23/27)) ≈ 0.0385`. A thin
wrapper over the **Phase R2** `core/feasibility.gascheau_coorbital_stable` (the R2 form correctly folds
the co-orbital body's own mass into the numerator; chosen over the request's generic `--mass1/--mass2`).
```bash
query.py trojan-stability --host-mass-earth 1.0 --companion-mass-earth 0 --star-mass-solar 1.0
```
Core function: `feasibility.gascheau_coorbital_stable(host_mass_earth, companion_mass_earth, star_mass_solar)`.
Output: `{mass_ratio, criterion, stable}` (`criterion` ≈ 0.03852; `stable` is `mass_ratio < criterion`).
**Validation:** `host_mass_earth > 0`, `star_mass_solar > 0`, `companion_mass_earth ≥ 0` else `{"error"}` exit 1.

#### `lorentz-factor`
Special-relativistic Lorentz / time-dilation factor for a **sublight** velocity. `γ = 1/√(1 − β²)`;
`time_dilation_pct = (γ − 1)·100`. **Deliberately distinct** from the FTL-arithmetic `ly-hr`/`times-c`
converters (which treat "× c" as a plain multiplier with no relativistic interpretation).
```bash
query.py lorentz-factor --velocity-c 0.6        # γ = 1.25
```
Core function: `calculators.compute_lorentz_factor(velocity_c)`. `--velocity-c` is β (a fraction of c).
Output: `{velocity_c, lorentz_factor, time_dilation_pct}`. **Validation:** `0 ≤ velocity_c < 1` else
`{"error": "Velocity must be in the range 0 ≤ β < 1 (sublight)."}` exit 1.

#### `circumbinary-hz`
Circumbinary (P-type) habitable zone from the two stars' **combined** light. `combined_lum = lum1 + lum2`;
the Kopparapu S_eff coefficients use a **luminosity/flux-weighted** effective temperature
`eff_teff = (lum1·teff1 + lum2·teff2)/(lum1+lum2)`; then the same 6-zone Kopparapu boundaries as
`habitable-zone`, computed from `combined_lum`.
```bash
query.py circumbinary-hz --teff1 5778 --lum1 1.0 --teff2 4000 --lum2 0.3
query.py circumbinary-hz --star1 "Alpha Centauri A" --star2 "Alpha Centauri B"   # SIMBAD-resolve (Phase T1b)
```
Core function: `equations.compute_circumbinary_hz(teff1, lum1, teff2, lum2)`. Output:
`{teff1, lum1, teff2, lum2, combined_lum, eff_teff, out_of_range_teff, zones}` — `zones` is the same
6-dict list (`zone_name, key, au, lm, seff`) as `habitable-zone`. **Out-of-range Teff is flagged, not
clamped:** when `eff_teff` falls outside the Kopparapu validity (~2600–7200 K), `out_of_range_teff` is
`true` and `eff_teff` is echoed but the zones are **still returned** (more conservative than single-star
`habitable-zone`'s silent extrapolation — a binary's combined Teff trips this far more often).
**Validation:** all four inputs `> 0` else `{"error"}` exit 1.
- **Phase T1b — `--star1`/`--star2` SIMBAD-resolve mode (additive).** Instead of the four numeric inputs,
  pass two **star names**: each is resolved via `compute_simbad_lookup` → `compute_star_system_regions_from_simbad`
  (`temp` + `bcLuminosity`, the same derivation as `star-regions`; works for any main-sequence type) and fed
  to the **unchanged** core function. The numeric and `--star` modes are mutually exclusive — supplying both,
  or only one star, or a partial numeric set, is an **argparse-style exit 2** (a stderr message, not JSON). A
  SIMBAD/regions failure on either star is returned immediately as `{"error"}` exit 1. `--star` mode adds a
  SIMBAD network call; the numeric mode stays fully offline.

### Detectability / exomoon / triple / relativistic calculators (Phase T1b — no network)

Eight new self-validating (Phase-H/P contract) pure-math calculators for the sibling worldbuilding repo's
survey-bias and dynamics research. Curated `{"error"}` → exit 1; argparse → exit 2. **B1 `tidal-heating`
and C2 `kozai-lidov` are explicitly order-of-magnitude** (fixed-Q / secular approximations) — treat their
single numbers as scale estimates, not precise predictions. The three load-bearing coefficients were
verified against the cited papers.

#### `rv-semi-amplitude` (A1)
Radial-velocity semi-amplitude a planet induces on its star (Lovis & Fischer 2010):
`K = 28.4329 m/s · (1/√(1−e²)) · (Mp·sin i / M_Jup) · ((M*+Mp)/M_sun)^(−2/3) · (P/1yr)^(−1/3)`. The input
`--planet-mass-earth` is converted to **M_Jup internally** (the constant is per-M_Jup); `k_ms` is in m/s.
```bash
query.py rv-semi-amplitude --planet-mass-earth 1 --star-mass-solar 1 --period-days 365.25
query.py rv-semi-amplitude --planet-mass-earth 317.8 --star-mass-solar 1 --sma-au 5.2 --ecc 0.05
```
Core: `calculators.compute_rv_semi_amplitude(planet_mass_earth, star_mass_solar, period_days=None, sma_au=None, ecc=0, inclination_deg=90)`. Supply exactly one of `--period-days`/`--sma-au` (a required mutually-exclusive group → argparse exit 2 if both/neither; the other is derived via Kepler III). `--ecc` default 0, `--inclination-deg` default 90. Output: `{k_ms, period_days, sma_au, ecc, inclination_deg, planet_mass_earth, star_mass_solar}`. **Validation:** masses `>0`, `0≤e<1`. **Anchor:** Earth→Sun ≈ `0.0895 m/s`.

#### `transit-signal` (A2)
Transit depth, geometric probability, and duration (Winn 2010): depth `δ=(Rp/R*)²`, prob `p≈R*/a`,
duration `T≈(P/π)·arcsin(R*/a)`.
```bash
query.py transit-signal --planet-radius-earth 1 --star-radius-solar 1 --sma-au 1 --star-mass-solar 1
```
Core: `calculators.compute_transit_signal(planet_radius_earth, star_radius_solar, sma_au=None, period_days=None, star_mass_solar=None)`. Supply `--sma-au`, **or** `--period-days` + `--star-mass-solar` (derives `a`). When only `--sma-au` is given (no mass), `period_days`/`duration_hours` are `null` (depth + probability still computed). Output: `{depth_ppm, depth_frac, transit_prob, duration_hours, sma_au, period_days, planet_radius_earth, star_radius_solar}`. **Validation:** radii `>0`; a star radius ≥ the orbital distance → `{"error"}`. **Anchor:** Earth→Sun ≈ `83.9 ppm`, `prob 0.0047`, `duration ~13 h`.

#### `astrometric-signal` (A3)
Astrometric wobble: `α = (Mp/M*)·(a_AU/d_pc)`, reported **microarcsec** headline + arcsec echo.
```bash
query.py astrometric-signal --planet-mass-earth 317.8 --star-mass-solar 1 --sma-au 5.2 --distance-pc 10
```
Core: `calculators.compute_astrometric_signal(planet_mass_earth, star_mass_solar, sma_au, distance_pc)`. Output: `{signal_microarcsec, signal_arcsec, …inputs}`. **Validation:** all four `>0`. **Anchor:** Jupiter→Sun @ 10 pc ≈ `496 µas`.

#### `direct-imaging` (A4)
Reflected-light contrast + angular separation, optionally vs a telescope inner working angle: sep
`θ=a/d`, contrast `C≈A_g·(Rp/a)²` (Rp→AU), `IWA=λ/D` (the **1·λ/D** convention — real coronagraphs use a
1–4 λ/D multiple), `resolvable = θ≥IWA`.
```bash
query.py direct-imaging --sma-au 1 --distance-pc 10 --planet-radius-earth 1
query.py direct-imaging --sma-au 1 --distance-pc 10 --planet-radius-earth 1 --telescope-diameter-m 6.5 --wavelength-um 1.0
```
Core: `calculators.compute_direct_imaging(sma_au, distance_pc, planet_radius_earth, albedo=0.3, telescope_diameter_m=None, wavelength_um=None)`. `iwa_arcsec`/`resolvable` are `null` unless **both** telescope args are given (only one → `{"error"}` exit 1). Output: `{angular_sep_arcsec, contrast_reflected, iwa_arcsec, resolvable, …inputs}`. **Validation:** sma/distance/radius `>0`, albedo `>0`. **Anchor:** Earth→Sun (A_g 0.3) ≈ contrast `5.4e-10`, sep `0.1″` @ 10 pc.

#### `tidal-heating` (B1) — order-of-magnitude
Tidal heating power + surface flux of a synchronous satellite. **`Ė = (21/2)·(G·k₂·M_p²·R_s⁵·n·e²)/(Q·a⁶)`**
(Peale & Cassen 1978; leading **21/2** pinned against Heller & Barnes 2013), `n=√(GM_p/a³)`; surface flux
`= Ė/(4πR_s²)`; `io_flux_ratio` vs Io's ≈ 2 W/m².
```bash
query.py tidal-heating --primary-mass-earth 317.8 --satellite-radius-km 1821 --sma-km 421700 --ecc 0.0041
```
Core: `equations.compute_tidal_heating(primary_mass_earth, satellite_radius_km, sma_km, ecc, k2=0.3, tidal_q=100)`. Output: `{heating_power_w, surface_flux_wm2, mean_motion_rad_s, io_flux_ratio, …inputs}`. **Validation:** mass/radius/sma `>0`, `0≤e<1`, `k2>0`, `tidal_q>0`. **Order-of-magnitude** — a fixed-Q, homogeneous, small-e estimate.

#### `kozai-lidov` (C2) — order-of-magnitude
Kozai–Lidov oscillation timescale of a hierarchical triple. **`T_KL = (8/15π)·((M₁+M₂+M₃)/M₃)·(P_out²/P_in)·(1−e_out²)^{3/2}`**
years (leading **8/15π** pinned against Antognini 2015 Eq. 42; general mass factor = Kiseleva 1998, M₃ = the
outer/tertiary perturber in the denominator).
```bash
query.py kozai-lidov --m1-solar 1 --m2-solar 1 --m3-solar 1 --period-inner-yr 1 --period-outer-yr 100
query.py kozai-lidov --m1-solar 1 --m2-solar 0.5 --m3-solar 0.3 --sma-inner-au 1 --sma-outer-au 30 --ecc-outer 0.2
```
Core: `equations.compute_kozai_lidov(m1_solar, m2_solar, m3_solar, period_inner_yr=None, period_outer_yr=None, sma_inner_au=None, sma_outer_au=None, ecc_outer=0)`. Supply **both** periods or **both** SMAs (the other set derived via Kepler III). Output: `{timescale_years, …inputs}`. **Validation:** masses `>0`, `0≤e_out<1`; partial/both input sets → `{"error"}` exit 1. **Anchor:** equal solar masses, P_in 1 yr, P_out 100 yr → `≈ 5093 yr`. **Order-of-magnitude.**

#### `relativistic-brachistochrone` (D1)
Flip-and-burn under constant **proper** acceleration, relativistically correct (MTW) — lifts the 3%c
Newtonian cap of the `brachistochrone-au`/`-lm` subcommands. `X=arccosh(1+a·(D/2)/c²)`; coordinate (observer)
time `2·(c/a)·sinh X`, proper (ship) time `2·(c/a)·X`; midpoint `peak_velocity_c=tanh X`,
`peak_lorentz_factor=cosh X`.
```bash
query.py relativistic-brachistochrone --accel-g 1 --distance-ly 4.37
```
Core: `calculators.compute_relativistic_brachistochrone(accel_g, distance_ly)`. Output: `{accel_g, distance_ly, coord_time_yr, proper_time_yr, peak_velocity_c, peak_lorentz_factor}`. **Validation:** `accel_g>0`, `distance_ly>0`. **Anchor:** 1 g over 4.37 ly → coord `≈ 6.0 yr`, proper `≈ 3.58 yr`, peak `≈ 0.95 c`; at low speed it converges to the Newtonian flip-burn `2√(D/a)` with proper ≈ coordinate time.

### Cooling-primary HZ (Phase U — bundled cooling table, no network)

A cooling primary (white or brown dwarf) has **no equilibrium luminosity**: its habitable
zone migrates inward as it cools, so a planet at a fixed orbit is habitable only for a
finite *residence time*. `cooling-hz` models this with **bundled static cooling tracks** +
the existing `habitable-zone` Kopparapu engine (reused verbatim per epoch) + the
`roche-limit` core (CHZ inner-edge cross-check). Self-validating (curated `{"error"}` →
exit 1; argparse → exit 2), pure-math, no network/DB/RNG. Out-of-Kopparapu-range Teff is
**flagged, not clamped** (the `circumbinary-hz` convention).

**Cooling tables (bundled static data, transcribed not fitted):** WD = **Bédard et al. 2020
(ApJ 901, 93) / Montreal "thick-H" (DA) cooling sequences** (`seq_0XX_thick.txt` at
`astro.umontreal.ca/~bergeron/CoolingModels/`); BD = **ATMO 2020 (Phillips et al. 2020,
A&A 637 A38)** substellar tracks. Stored in `core/cooling_tables.py` as
`(age_gyr, teff_k, log10_l_lsun, radius_rsun)` rows per mass; every row is verified against
`L/L_sun = (R/R_sun)²(Teff/Teff_sun)⁴` at transcription. **Luminosity is derived from the
interpolated (Teff, R) by that identity** (not interpolated independently), so every
interpolated epoch is physically self-consistent. *(Grid: WD 0.4–1.0 M☉ in 0.1 steps; BD
~13.6–75.4 M_Jup. A mass off the grid returns a clean error.)*

**Three modes**, selected by which of `--teff` / `--cooling-age-gyr` / `--sma-au` is given
(a single argparse mutually-exclusive group; at most one):

```bash
query.py cooling-hz --track wd --mass-solar 0.6 --teff 5000              # mode 1 snapshot
query.py cooling-hz --track wd --mass-solar 0.6 --sma-au 0.01 --hz-edge optimistic  # mode 2 residence
query.py cooling-hz --track wd --mass-solar 0.6                          # mode 3 CHZ band (default)
```
Core function: `cooling.compute_cooling_hz(track, mass_solar=None, mass_mjup=None,
cooling_age_gyr=None, teff=None, sma_au=None, chz_threshold_gyr=3.0,
hz_edge="conservative", age_max_gyr=13.8, satellite_density=5.5)`.

- **`--track {wd,bd}`** (required). **Mass** via the mutex group `--mass-solar` /
  `--mass-mjup` (WD default 0.6 M☉; BD primary unit `--mass-mjup`, default 50 M_Jup;
  conversion 1 M_Jup = 9.543×10⁻⁴ M☉, documented and applied internally).
- **`--hz-edge {conservative,optimistic}`** (default conservative = runaway-greenhouse →
  maximum-greenhouse; optimistic = recent-venus → early-mars).
- **`--chz-threshold-gyr`** (mode 3 residence threshold, default 3.0 — Agol's definition),
  **`--age-max-gyr`** (integration ceiling, default 13.8), **`--satellite-density`** (mode-3
  Roche cross-check, default 5.5 g/cc rocky).

**Mode 1 — snapshot** (`--teff` *or* `--cooling-age-gyr`): `{mode:"snapshot",
cooling_age_gyr, teff_k, lum_lsun, radius_rsun, zones[], out_of_range_teff, notes}` —
`zones[]` is the same 6-dict list as `habitable-zone`. **Anchor:** 0.6 M☉ @ 5000 K →
`lum_lsun ≈ 8.6×10⁻⁵`, conservative HZ ≈ 0.0092–0.0167 AU.

**Mode 2 — residence** (`--sma-au`): `{mode:"residence", sma_au, ever_habitable,
entry_age_gyr, exit_age_gyr, residence_gyr, entry_teff_k, exit_teff_k,
entry_out_of_range, exit_out_of_range, truncated_at_age_max}`. **The Kopparapu validity
gate is asymmetric — hot-side only.** Above ~7200 K the polynomial is unreliable (and
eventually returns a negative S_eff), so the young hot-dwarf phase is gated out — without
this a far orbit would falsely read habitable while the dwarf blazes. The cool side is a
*gentle* extrapolation (S_eff stays positive and smooth well below 2600 K) and is *needed*
for cooling-dwarf residence, so a crossing below 2600 K is **allowed and flagged**
(`entry/exit_out_of_range`), not gated — this is what lets a planet track a cooling BD's HZ
for Gyr. "Never habitable" is a normal result (`ever_habitable:false`), not an error.
**Anchors:** 0.6 M☉ WD, a=0.01 AU → `residence_gyr ≈ 7.4` (optimistic, reproducing Fossati
2012's ~8 Gyr) / ≈ 4.5 (conservative). BD peak residence rises with mass — ~0.3 Gyr at
13.6 M_Jup up to ~9 Gyr at 75 M_Jup (multi-Gyr only for the most massive BDs, ~>52 M_Jup,
matching Bolmont 2011/2017), the cold-host portion carrying `exit_out_of_range:true`.

**Mode 3 — CHZ band** (default; none of the three): `{mode:"chz", chz_threshold_gyr,
chz_inner_au, chz_outer_au, inner_edge_roche_limited, roche_limit_au, roche_rigid_au,
chz_inner_out_of_range, chz_outer_out_of_range, satellite_density}`. `roche_limit_au`
is the **fluid** (rubble-pile) tidal-disruption radius; `inner_edge_roche_limited` is true
when the CHZ inner edge falls inside it (Pkt 7 R2 — the cool-WD collision). **Anchor:**
0.6 M☉, threshold 3 Gyr → CHZ ≈ 0.0065–0.0198 AU (Agol 2011's ~0.005–0.02), reproduced
across 0.4–0.9 M☉, with the optimistic-edge inner edge Roche-limited.

**All modes** carry `track, mass_solar, mass_mjup, hz_edge, age_max_gyr, model_note`
(names the bundled table source), `any_out_of_range`, and `hz_model_valid_teff_k`
(`[2600, 7200]`).

> **Validation (self-validating — Phase-H/P):** curated `{"error"}` exit 1 for `--track`
> not in {wd,bd}, a mass off the bundled grid, or any of `--cooling-age-gyr` / `--teff` /
> `--sma-au` / `--chz-threshold-gyr` / `--age-max-gyr` / `--satellite-density` ≤ 0. Argparse
> exit 2 for a missing `--track`, a bad `--track`/`--hz-edge` choice, two mode args, two mass
> args, or a non-numeric value. **Root-find:** entry/exit crossings by bisection on age to a
> 1×10⁻⁴ Gyr tolerance over `[0, age_max]`; the CHZ band by a 600-point log-spaced orbit
> sweep. The cooling output is **order-of-magnitude where the track is sparsely sampled**;
> the snapshot luminosity is exact (closure-derived).

### Power / Thermal / Shielding (Phase V — pure math + bundled XCOM table, no network)

Three `query.py`-only **mission-engineering** calculators (Group F of
`calculator-extensions-request.md`; the pre-scope-lock prerequisite for the sibling repo's
Packet 13). They model the **floor physics** — the radiative-rejection and attenuation
limits no future engineering can repeal — and are agnostic about mature-tech
*implementation*. Self-validating (curated `{"error"}` exit 1; argparse exit 2). Pure-math;
F3 reads a **bundled NIST XCOM coefficient table** (`core/shielding_tables.py`), no live
dataset. `core/thermal.py`; the Stefan–Boltzmann constant lives in `core/equations.py`.

#### `waste-heat` (F1)
Waste heat a device must reject, with an optional Carnot ceiling. `Q = P_in·(1−η)` (gross)
or `P_useful·(1−η)/η` (net). Optional Carnot floor from reservoir temps:
`η_carnot = 1 − T_cold/T_hot`, `Q_min = P_useful·T_cold/(T_hot−T_cold)`.
```bash
query.py waste-heat --input-power-watts 3e9 --efficiency 0.4
query.py waste-heat --useful-power-watts 1e9 --efficiency 0.9 --hot-temp-k 1500 --cold-temp-k 300
```
Core: `thermal.compute_waste_heat(input_power_watts=None, useful_power_watts=None, efficiency=None, hot_temp_k=None, cold_temp_k=None, peak_w=None, mean_w=None, duty=None, pulse_period_s=None, storage_mass_kg=None, specific_heat_jkgk=None)`. Power anchor (`--input-power-watts` | `--useful-power-watts`) is an **argparse mutex group** — no longer `required` (transient mode uses no steady anchor), so both → exit 2, but **neither + not transient → the core "no power anchor" error (exit 1)**. Efficiency anchor: `--efficiency` (0<η≤1) **or** `--hot-temp-k`+`--cold-temp-k` (derives η_carnot). If both an explicit efficiency and reservoir temps are given, device waste-heat uses `--efficiency` and the Carnot floor is reported alongside; `carnot_limited:true` flags a stated η above the Carnot ceiling (physically impossible — flagged, still returned). Output: `{waste_heat_w, useful_power_w, input_power_w, efficiency, carnot_efficiency|null, carnot_min_waste_heat_w|null, carnot_limited|null, hot_temp_k, cold_temp_k, notes}` (no `mode` key — steady-state is byte-identical to Phase V). **Validation:** non-positive powers; η ∉ (0,1]; `T_hot ≤ T_cold`; incomplete reservoir pair; no efficiency anchor → curated `{"error"}` exit 1. **Anchor:** 3 GW @ η=0.4 → useful 1.2e9 / waste 1.8e9 W; T_hot=1500/T_cold=300 → η_carnot=0.8, claimed η=0.9 → `carnot_limited:true`.
- **Phase AD (C9) — transient / pulsed thermal-buffer mode.** Supplying **any** of `--peak-w --mean-w --duty --pulse-period-s --storage-mass-kg --specific-heat-jkgk` selects transient mode; **all six are required together**. The radiator is sized for the time-average `mean_w`; the excess `peak_w − mean_w` charges a thermal buffer over each on-phase `on_time_s = duty·pulse_period_s` → per-cycle `temp_swing_k = (peak_w−mean_w)·on_time_s/(m·c)` and a ride-through `buffer_time_s = m·c·temp_swing_k/mean_w`. (The plan's formula needs an absolute on-time; `--pulse-period-s` supplies it — a documented clarification of the input set.) Output: `{mode:"transient", peak_power_w, mean_power_w, duty, pulse_period_s, on_time_s, excess_power_w, storage_mass_kg, specific_heat_jkgk, heat_capacity_j_per_k, buffered_energy_j, temp_swing_k, buffer_time_s, notes}`. **Validation:** an incomplete set; `peak_w < mean_w`; `duty ∉ (0,1]`; non-positive `pulse_period_s`/`storage_mass_kg`/`specific_heat_jkgk` → curated `{"error"}` exit 1. Refrigeration/pump work stays packet prose.

#### `radiator-area` (F2)
Radiating **area** (and optional mass) to reject a heat load by Stefan–Boltzmann radiation.
`q = ε·σ·(T_rad⁴ − T_sink⁴)·n_sides` [W/m²], `A = Q/q`; σ = 5.670374419e-8.
```bash
query.py radiator-area --heat-watts 1e9 --radiator-temp-k 300 --emissivity 0.9 --sides 2
query.py radiator-area --input-power-watts 3e9 --efficiency 0.4 --radiator-temp-k 350
```
Core: `thermal.compute_radiator_area(heat_watts=None, input_power_watts=None, efficiency=None, radiator_temp_k=None, emissivity=0.9, sides=2, sink_temp_k=0.0, areal_mass_kgm2=None)`. Heat load: `--heat-watts` **or** the inline F1 chain `--input-power-watts`+`--efficiency` (computes `Q=P_in·(1−η)`). `--radiator-temp-k` required (>0); `--emissivity` default 0.9 (0<ε≤1); `--sides {1,2}` default 2 (a flat panel radiates from both faces); `--sink-temp-k` default 0 (idealized deep space); `--areal-mass-kgm2` optional → `radiator_mass_kg`. Output: `{radiator_area_m2, radiator_area_km2, flux_wm2, blackside_flux_wm2, heat_watts, radiator_temp_k, sink_temp_k, emissivity, sides, radiator_mass_kg|null, areal_mass_kgm2|null, scaling_note}`. `blackside_flux_wm2 = σ·T_rad⁴` makes the T⁴ dependence legible; `scaling_note` states the A ∝ T⁻⁴ rule, the Carnot coupling, and the `T_sink → T_rad` collapse. **Validation:** non-positive heat/temp; ε ∉ (0,1]; `sides ∉ {1,2}`; `T_sink ≥ T_rad` (a radiator can't reject below its environment — curated error); `T_sink < 0`; both/neither heat anchor → curated `{"error"}` exit 1. **Anchors (verified):** σT⁴ = 459 W/m² @300 K / 5.67e4 @1000 K (ε=1, 1 side); **1 GW @300 K, ε=0.9, double-sided → ≈1.21×10⁶ m² ≈ 1.21 km²**.

#### `shielding-attenuation` (F3)
Attenuation of penetrating radiation by shielding **mass**, two modes.
**Photon (default, exact Lambert–Beer):** `I/I₀ = exp(−(μ/ρ)·Σ)`, `HVL = ln2/(μ/ρ)`,
`TVL = ln10/(μ/ρ)` [g/cm²]. **GCR (order-of-magnitude):** `D/D₀ = exp(−Σ/Λ)` with a
mandatory secondary-buildup caveat (a thin shield can *raise* GCR dose).
```bash
query.py shielding-attenuation --material water --energy-mev 1.0 --areal-density-gcm2 20
query.py shielding-attenuation --material lead --energy-mev 1.0 --thickness-cm 1 --density-gcm3 11.35
query.py shielding-attenuation --mode gcr --material water --areal-density-gcm2 30
```
Core: `thermal.compute_shielding_attenuation(areal_density_gcm2=None, thickness_cm=None, density_gcm3=None, mass_atten_coeff_cm2g=None, attenuation_length_gcm2=None, material=None, energy_mev=None, mode="photon", particle="photon", csda_range_gcm2=None, layers=None)`. Thickness via `--areal-density-gcm2` **or** `--thickness-cm`+`--density-gcm3` (Σ = ρ·x). Coefficient (photon) via explicit `--mass-atten-coeff-cm2g`, or `--material`+`--energy-mev` **bundled NIST XCOM lookup**; (gcr) via `--attenuation-length-gcm2` or `--material` (bundled Λ).
- **Phase AD (C6) — charged-particle CSDA range.** `--particle {photon,proton,alpha,ion}` (default `photon` = the unchanged behaviour). A **charged particle** takes the CSDA-range path — a *hard stopping depth*, not exponential attenuation: `--material`+`--energy-mev` looks up the bundled **NIST PSTAR** proton/water grid, or `--csda-range-gcm2` supplies an explicit range (for alpha/ion or any un-bundled material). Output `{mode:"csda", particle, csda_range_gcm2, csda_range_cm (with density), stops_primary, penetrates, residual_range_gcm2, energy_mev, energy_exact, is_order_of_magnitude:false, model_note, buildup_caveat}`. **Data scope (surfaced):** the bundled convenience table currently covers **protons in water** (the anchor); alpha/ion beams and other materials use `--csda-range-gcm2` — a documented data-scope decision (additional PSTAR/ASTAR materials are a pure data swap). Secondary-particle production behind a partial shield is **not** modelled (hand off to a transport code). **Anchor (web-verified 2026-07-03):** 100 MeV proton in water → CSDA range **7.718 g/cm²**.
- **Phase AD (C7) — multi-layer stacks.** `--layers "mat:gcm2, mat:gcm2, …"` computes a stacked-shield transmitted fraction as the **per-layer product** (photon/GCR by `--mode`; the shared `--energy-mev` is used for photon layers). Output `{mode, layers:[{material, areal_density_gcm2, transmitted_fraction, …}], total_transmitted_fraction, total_attenuation, total_areal_density_gcm2, is_order_of_magnitude}`. A **single layer reproduces the single-material result** (parity); `total_transmitted_fraction` is order-independent. **Validation:** a malformed `--layers` token, an unknown/negative layer, or (photon) a missing `--energy-mev` → curated `{"error"}` exit 1. **Bundled photon grid** (`core/shielding_tables.py`, transcribed from NIST XCOM/XAAMDI): materials `water, polyethylene, aluminum, regolith, lead, liquid_h2` (alias `hydrogen`)`, iron` × energies `0.1, 0.5, 1, 2, 5, 10 MeV` (nearest-energy lookup; the chosen energy is echoed in `energy_mev` with an `energy_exact` flag). `regolith` is an SiO₂-dominant silicate approximation and `liquid_h2` carries a per-gram-vs-per-cm note (both surfaced in `notes`). **Bundled GCR Λ** (water/polyethylene/aluminum/regolith; NCRP 153 / NASA HRP, order-of-magnitude). Output: `{transmitted_fraction, attenuation_factor, areal_density_gcm2, half_value_layer_gcm2, tenth_value_layer_gcm2, mass_atten_coeff_cm2g|attenuation_length_gcm2, material|null, energy_mev|null, energy_exact|null, mode, model_note, buildup_caveat, is_order_of_magnitude, notes}` (+ `thickness_cm, density_gcm3, half_value_layer_cm, tenth_value_layer_cm` when thickness+density given). `is_order_of_magnitude` is `false` for photon, `true` for gcr; `model_note` names NIST XCOM (photon) / NCRP-153 (gcr). **Validation:** `--mode` ∉ {photon,gcr} → argparse exit 2; non-positive Σ/thickness/density/coeff/Λ, both Σ paths, an off-grid `--material`/`--energy-mev`, or a missing coefficient → curated `{"error"}` exit 1. **Anchors (photon, transcribed from NIST XCOM):** water @1 MeV (μ/ρ ≈ 0.0707) → HVL ≈ 9.8 cm, TVL ≈ 32.6 cm; 20 g/cm² → transmitted ≈ 0.243; lead @1 MeV → linear HVL ≈ 0.86 cm (ρ = 11.35).

> **Caveat — F3 coefficients & GCR mode.** The photon μ/ρ grid was **reconciled cell-by-cell
> against the live NIST XAAMDI tables (2026-06-30)** and is pinned by a golden test
> (`tests/test_thermal.py::test_nist_pinned_grid`): water/polyethylene from the ComTab
> compound tables; aluminum/lead/hydrogen/iron from the ElemTab element tables; `regolith` is
> an SiO₂-dominant silicate analog **computed** from the NIST elemental Si+O tables via the
> mixture rule (an approximation, flagged in `notes`). The water- and lead-@1-MeV HVL anchors
> are additionally checked. The GCR mode is **explicitly order-of-magnitude**
> (`is_order_of_magnitude:true`) and a v1 single-exponential stand-in; broad-beam photon buildup
> factors and electrostatic shielding remain out of scope (packet prose). *(Charged-particle CSDA
> range is now the Phase-AD C6 path above; active magnetic shielding is `active-shield` below.)*

#### `active-shield` (Phase AD C8 — magnetic rigidity cutoff, no network)
The **field** side of radiation shielding (complementing the mass side of `shielding-attenuation`):
a magnetic dipole deflects charged particles whose magnetic **rigidity** (R = pc/q) falls below a
geometry-set cutoff. Pure-math, self-validating, `query.py`-only. `core/active_shield.py`; reuses
`μ₀`/`c` from `core/equations.py`.
```bash
query.py active-shield --shield-radius-m 6.371e6 --magnetic-moment-am2 8e22       # Earth cross-check ≈ 14.8 GV
query.py active-shield --shield-radius-m 10 --field-tesla 5 --field-radius-m 10 --spectrum-characteristic-rigidity-gv 1.0
query.py active-shield --shield-radius-m 10 --coil-current-a 1e8 --coil-radius-m 10
```
Core: `active_shield.compute_active_shield(shield_radius_m=None, coil_current_a=None,
coil_radius_m=None, magnetic_moment_am2=None, field_tesla=None, field_radius_m=None,
spectrum_characteristic_rigidity_gv=None)`. `--shield-radius-m` (r, the protected-region radius) is
**required**. Field source — **exactly one** of `--magnetic-moment-am2`, the coil pair
(`--coil-current-a`+`--coil-radius-m`, m = I·π·R²), or field×scale (`--field-tesla`+`--field-radius-m`,
m = 4π·r₀³·B/μ₀). **Störmer equatorial cutoff** `R_c = (μ₀·c/16π)·m/r²` [V] — the constant
(≈ 7.495 V·m/A·m²) reproduces Earth's ≈ 14.8 GV geomagnetic equatorial cutoff (anchored). Optional
`--spectrum-characteristic-rigidity-gv` R_s → an **order-of-magnitude** deflected fraction
`1 − exp(−R_c/R_s)` (monotone in R_c, ∈ [0,1)). Output: `{shield_radius_m, magnetic_moment_am2,
field_source, coil_current_a|null, coil_radius_m|null, rigidity_cutoff_gv, rigidity_cutoff_v,
magnetic_field_t (= μ₀·m/4πr³), spectrum_characteristic_rigidity_gv, deflected_fraction|null,
is_order_of_magnitude:true, model_note}`. **Validation:** `shield_radius_m ≤ 0`; not exactly one
field source (partial/none/double); non-positive moment/current/radius/field; `R_s ≤ 0` → curated
`{"error"}` exit 1; a missing required `--shield-radius-m` / non-numeric → argparse exit 2. The dipole
idealisation ignores real coil geometry, un-shielded polar cusps, and secondary production — a
first-cut feasibility screen, not a transport simulation.

### Rotating-habitat comfort (Phase W — no network)

#### `spin-comfort`
The in-house analog of Theodore Hall's *SpinCalc*: given exactly **two** of the four spin-state
variables it solves the other two **plus** the three comfort-relevant derived quantities the
`gravity-*` solves don't expose — **rim tangential velocity, head-to-foot gravity gradient, and
Coriolis ratio for a walking occupant** — then classifies the design against tiered comfort
bands. Pure-math, self-validating, `query.py`-only; **extends (does not replace)**
`gravity-acceleration` / `gravity-distance` / `gravity-rpm` (those stay the terse single-scalar
solves).
```bash
query.py spin-comfort --radius-m 224 --rpm 2.0
query.py spin-comfort --radius-m 10 --gravity-g 1.0
query.py spin-comfort --gravity-g 1.0 --tangential-velocity-ms 6 --criteria moderate
```
Core function: `spin.compute_spin_comfort(radius_m=None, rpm=None, accel_ms2=None,
tangential_velocity_ms=None, occupant_height_m=1.8, walk_speed_ms=1.0, criteria="all",
max_rpm=None, min_gravity_g=None, max_gravity_g=None, min_tangential_velocity_ms=None,
max_gradient_pct=None, max_coriolis_pct=None)`.

- **State anchors — supply exactly two:** `--radius-m` (m), `--rpm`, gravity (`--gravity-g`
  **or** `--accel-ms2` m/s²; argparse-mutex), `--tangential-velocity-ms` (m/s). All six pairings
  are determinate (`ω`,`r` derived, then everything). Fewer/more than two → curated error.
- **Occupant / reference:** `--occupant-height-m` (default **1.8**; head height for the gradient;
  must be `<` the *solved* radius), `--walk-speed-ms` (default **1.0**; the Coriolis reference speed).
- **Verdict:** `--criteria {conservative,moderate,relaxed,all}` (default **all**). Optional
  per-threshold overrides `--max-rpm`, `--min-gravity-g`, `--max-gravity-g`,
  `--min-tangential-velocity-ms`, `--max-gradient-pct`, `--max-coriolis-pct` each replace that
  threshold across **all** evaluated tiers; the output lists which were overridden.

**Formulas (exact):** `ω = rpm·2π/60`; `a = ω²r` (`gravity_g = a/g₀`, g₀ = 9.80665);
`v = ωr`; gradient fraction `= h/r` (head accel `ω²(r−h)`); Coriolis ratio `= 2u/v` (u = walk speed).

**Output (units on every field):** `{radius_m (m), rpm, angular_velocity_rads (rad/s), accel_ms2,
gravity_g, tangential_velocity_ms (m/s), occupant_height_m (m), head_accel_ms2, head_gravity_g,
gravity_gradient_fraction, gravity_gradient_pct (%), walk_speed_ms (m/s), coriolis_accel_ms2,
coriolis_ratio, coriolis_ratio_pct (%), anchors [the two supplied], criteria {tier: {pass,
checks: {name: {value, threshold, pass}}}}, overridden_thresholds[], model_note, notes}`. A check
with a `null` threshold reports `pass: null` (not checked for that tier); a tier's `pass` is the
AND of its non-null checks. `--criteria <tier>` returns only that tier's block. All inputs echoed.

**Bundled comfort bands** (`core/spin_tables.py`; transcribed from Hall's SpinCalc comfort-chart
literature — Hill & Schnitzer 1962 / Gilruth 1969 / Gordon & Gervais 1969 / Stone 1973 /
Cramer 1985 / Hall 1999 Table 1). **The bands are a human-factors design *choice*, not physics** —
the kinematic outputs are exact; only the pass/fail bands are a choice, and every threshold is
overridable. Comparisons carry a **1 % relative tolerance** so a nominal-1 g design (1.0019 g from
round inputs) isn't spuriously failed by a 1.0 g ceiling.

| Threshold | Conservative | Moderate | Relaxed |
|---|--:|--:|--:|
| Max spin rate (RPM) | 2.0 | 4.0 | 6.0 |
| Min gravity (g) | 0.30 | 0.20 | 0.10 |
| Max gravity (g) | 1.0 | 1.0 | (none) |
| Min tangential velocity (m/s) | 6 | 3 | (none) |
| Max head-foot gradient (%) | 10 | 15 | 25 |
| Max Coriolis ratio @ walk (%) | 25 | 25 | (none) |

> **Provenance footnotes (echoed in `model_note`):** the RPM ladder and the min-gravity column
> are verbatim from Table 1; the conservative gradient **10 %** has no direct published basis
> (Table 1 gives 8 % and 25 %); published gradient caps are defined over a **2 m** head-to-foot
> span (default height 1.8 m); Stone's 25 % Coriolis cap is at a **1.2 m/s** carry speed (default
> walk-speed 1.0). Per the Mature-Technology Assumption these are present-day *unadapted*
> constraints — design anchors, not 2500-yr ceilings.

> **Validation (self-validating — Phase-H/P):** curated `{"error"}` exit 1 for a non-positive
> anchor / occupant-height / walk-speed, `occupant-height-m ≥` the solved radius, **not exactly
> two** state anchors, or an out-of-range override (non-positive threshold; percentage outside
> (0, 100]). Argparse exit 2 for `--gravity-g` **and** `--accel-ms2` both given (mutex), a bad
> `--criteria` choice, or a non-numeric value.

### Closed-loop life support & bioregeneration (Phase X — bundled BVAD Rev2, no network)

Three `query.py`-only mission-ecology calculators for the sibling repo's Packet 15 — crew
consumables/waste budgeting, bioregenerative grow-area + lighting-power sizing, and
resource-limited population capacity. Pure arithmetic / energy balance over one bundled static
reference table (`core/life_support_tables.py`, transcribed verbatim from **NASA BVAD Rev2**,
NASA/TP-2015-218570/REV2, Feb 2022, Tables 3-31/4-20/4-90/4-91). Self-validating (curated
`{"error"}` exit 1; argparse exit 2). No GUI, no CLI menu, no DB, no network, no RNG. Every
bundled rate/efficiency is overridable (Mature-Technology Assumption; `model_note` names the
edition and the exercising-reference-astronaut caveat). `core/life_support.py`.

> **BVAD edition note.** The bundled human loads are Rev2's exercising ~82 kg reference set —
> O₂ **0.895**, CO₂ **1.085** (RQ 0.860), food solids **0.800** kg/CM·d, food energy **3054**
> kcal, drinking water **2.0** kg/CM·d, total water incl. full hygiene **9.12** kg/CM·d (Mature
> Planetary Base). The older textbook 2500-kcal/0.816-O₂/0.617-food set is reachable through the
> `--kcal-per-day`/`--*-rate` overrides. The PAR photon energy is `0.2177 J/µmol` (~550 nm) and
> the LED wall-plug→PAR efficiency defaults to `0.4` (~1.9 µmol/J, a conservative present-day
> mid-grade fixture).

#### `life-support` (X1)
Crew consumables and metabolic-waste budget, with closure-loop makeup mass. Every rate starts
from BVAD Rev2 and is overridable; `--closure-scenario` sets water/O₂/food recycle fractions and
per-stream `--*-closure` flags override.
```bash
query.py life-support --crew 6 --days 180 --closure-scenario iss
query.py life-support --o2-rate 0.816 --food-dry-rate 0.617 --kcal-per-day 2500   # older textbook set
```
Core: `life_support.compute_life_support(crew=1, days=1, water_closure=None, o2_closure=None,
food_closure=None, closure_scenario=None, o2_rate=None, co2_rate=None, potable_water_rate=None,
total_water_rate=None, food_dry_rate=None, kcal_per_day=None, solid_waste_rate=None,
liquid_waste_rate=None)`. `--closure-scenario` ∈ `{open,iss,advanced,bioregen}` (default `open`
= no recycling). Output: `{crew, days, per_person_daily{o2_kg, co2_kg, potable_water_kg,
total_water_kg, food_dry_kg, kcal, solid_waste_kg, liquid_waste_kg}, totals{…×crew×days},
closure{water,o2,food}, scenario, makeup_mass_kg{o2, water, food, total}, model_note, notes}`.
`makeup[stream] = rate·crew·days·(1−closure)`; open-loop → makeup == total. **Validation:**
`crew>0`, `days>0`, each overridden rate `>0`, each closure ∈ [0,1], known scenario → else curated
`{"error"}` exit 1. **Anchor:** per person / open / 1 day → O₂ 0.895, CO₂ 1.085, food 0.800 kg,
3054 kcal, potable 2.0 kg; `--closure-scenario iss --days 365` water makeup = 0.10× the open total.

#### `bioregen-area` (X2)
Grow area (and optional LED electrical power) to feed a crew. **Default area path is the PAR
energy balance** `A = E_d / (PAR_energy·η_photo·HI·f_edible)`; when a **BVAD `--crop`** is named,
its measured edible productivity is reported as `area_m2_per_person_measured` (cross-check).
**Algae crops** (`chlorella`/`spirulina`) take the productivity path as the primary area (no
HI/PAR chain) and still report gas exchange. **Exactly one light anchor is required.**
```bash
query.py bioregen-area --kcal-per-day 2500 --crop wheat --dli-mol 30 --artificial
query.py bioregen-area --crop wheat --ppfd-umol 520.8 --photoperiod-h 16
query.py bioregen-area --crop chlorella --dli-mol 30
```
Core: `life_support.compute_bioregen_area(kcal_per_day=None, crew=1, crop=None, ppfd_umol=None,
photoperiod_h=16, dli_mol=None, par_wm2=None, photo_efficiency=None, harvest_index=None,
artificial=False, led_par_efficiency=None, f_edible_energy=1.0)`. Light anchor: `--ppfd-umol`
(+`--photoperiod-h`), `--dli-mol`, or `--par-wm2` (a **required argparse mutex** — 0/2 → exit 2);
all three describing the same light give the same area. `--kcal-per-day` default 2500;
`--photo-efficiency` default **0.10** (biomass-energy/incident-PAR); `--harvest-index` defaults
from `--crop` and is **required** when no BVAD crop is given; `--led-par-efficiency` default 0.4.
Output: `{kcal_per_day, crew, crop, area_m2_per_person, area_m2_total,
area_m2_per_person_measured, dli_mol, ppfd_umol, photoperiod_h, photo_efficiency, harvest_index,
f_edible_energy, lighting{artificial, par_wm2_delivered, electrical_power_w_per_person,
electrical_power_w_total, led_par_efficiency}, crop_gas_exchange{o2_kg_day, co2_kg_day},
transpiration_water_kg_day, model_note, par_is_input_note, notes}` — `electrical_power_*` are
`null` without `--artificial`; `crop_gas_exchange`/`transpiration` are `null` without `--crop`
(and `transpiration` is `null` for algae). **`--star`/`--spectral-type` are deliberately
rejected** (unknown-arg exit 2) — PAR is a caller-supplied parameter (`par_is_input_note`;
stellar-type-resolved PAR is the **Phase-AA `par-flux`** tool, whose `ppfd_umol_m2_s` output feeds
this tool's `--ppfd-umol` anchor — see "PAR / photosynthesis by stellar type"). **Validation:** exactly one light anchor;
`kcal_per_day>0`, `crew>0`, `photoperiod_h ∈ (0,24]`, `photo_efficiency`/`harvest_index`/
`led_par_efficiency`/`f_edible_energy ∈ (0,1]`, known crop → else curated `{"error"}` exit 1.
**Anchors:** 2500 kcal, DLI≈30, wheat → area ≈ 40 m²/person (measured cross-check ≈ 37 m²);
`--artificial --led-par-efficiency 0.4` → ≈ 7.6 kW/person; `--crop chlorella` gives a smaller area.

> **Phase AD (C10) — `--crops` diet mix.** Instead of a single `--crop`, pass a **calorie split**
> `--crops "wheat:0.5, white_potato:0.3, soybean:0.2"` (fractions must sum to 1.0). Each crop supplies
> its calorie share at its own harvest index / productivity; the result adds `per_crop_area_m2[]`
> (`{crop, calorie_fraction, harvest_index, area_m2_per_person, area_m2_total}` per crop) and
> `area_m2_total = Σ`. Gas exchange / transpiration sum across the mix. `--crop` and `--crops` are
> mutually exclusive (both → exit 1). A single-entry mix (`"wheat:1.0"`) reproduces the `--crop wheat`
> areas exactly. **Validation (exit 1):** malformed token, unknown crop in the list, non-positive
> fraction, or fractions **not summing to 1.0** — the tool **rejects rather than normalizes** (Locked
> C10 decision). **The protein/vitamin-target diet LP is a surfaced v2 decision** — the mix is a pure
> calorie split (noted in `model_note`).

#### `population-capacity` (X3)
Sustainable population from resource budgets; reports the binding constraint. Any omitted
per-person requirement is filled from a nominal X1 (BVAD water/food) / X2 (area/power) run + the
bundled per-person fixed-nitrogen figure (~5 kg N/person·yr); any `--per-person-*` flag overrides.
Only resources with a supplied budget are evaluated.
```bash
query.py population-capacity --power-w 1e6 --per-person-power-w 1e4
query.py population-capacity --crop-area-m2 5000 --power-w 1e6 --fixed-nitrogen-kg-yr 100
```
Core: `life_support.compute_population_capacity(crop_area_m2=None, power_w=None, water_kg_day=None,
fixed_nitrogen_kg_yr=None, food_dry_kg_day=None, per_person_area_m2=None, per_person_power_w=None,
per_person_water_kg_day=None, per_person_nitrogen_kg_yr=None, per_person_food_kg_day=None)`. Output:
`{per_resource{<resource>{budget, per_person, source ("default"|"flag"), population}},
sustainable_population, binding_constraint, slack{<non-binding resource>: population − sustainable},
model_note, notes}` — `population = budget/per_person`; `sustainable_population = min`;
`binding_constraint = argmin`. **Validation:** at least one budget, every supplied budget `>0` and
every per-person requirement `>0` → else curated `{"error"}` exit 1. **Anchor:** `--power-w 1e6
--per-person-power-w 1e4` → 100 (power-bound); a tight `--fixed-nitrogen-kg-yr` flips
`binding_constraint` to `"fixed_nitrogen"` with slack reported on the others.

### STL mission energetics (Phase Y — pure math + bundled fuel presets, no network)

Two `query.py`-only mission-propulsion calculators for the sibling repo's Packet 16 (STL
Colonization Propulsion). They add the **mass/energy** side of sub-light travel — `query.py`
already has the *kinematics* (`brachistochrone-*`, `distance-at-acceleration`,
`travel-time-custom-thrust`). Energetics = "can you carry the fuel"; kinematics = "how long is
the trip." Pure-math, self-validating (curated `{"error"}` exit 1; argparse exit 2). `core/propulsion.py`;
the bundled ideal fuel exhaust velocities live in `core/propulsion_tables.py`. The **physics is
durable** (Tsiolkovsky + the relativistic rocket equation); the fuel `v_e` values are **ideal /
present-day ancestors, overridable** (Mature-Technology Assumption). Full propulsion taxonomy
defers to Packet 25 — this is the STL scoping *envelope*.

#### `rocket-equation` (G1)
Mass ratio + propellant fraction from **any two of** {velocity, exhaust, mass_ratio}. Classical
`MR = exp(Δv/v_e)`; relativistic (β anchor) `MR = exp((c/v_e)·atanh β)`; photon rocket (`v_e=c`)
`MR = √((1+β)/(1−β))`. The input `--mass-ratio` (and payload budget) is the **single-burn** ratio;
`--legs` raises it: flyby `MR¹` / rendezvous `MR²` / round-trip `MR⁴`; `propellant_fraction =
1 − 1/MR_total`.
```bash
query.py rocket-equation --delta-v-kms 30 --exhaust-velocity-kms 30       # MR ≈ 2.718
query.py rocket-equation --beta 0.1 --fuel fusion-dt --legs rendezvous     # MR ≈ 804
query.py rocket-equation --beta 0.1 --exhaust-velocity-kms 299792.458      # photon, MR ≈ 1.105
```
Core: `propulsion.compute_rocket_equation(delta_v_kms=None, beta=None, exhaust_velocity_kms=None,
isp_s=None, fuel=None, mass_ratio=None, relativistic=False, legs="flyby", payload_mass_t=None,
structure_fraction=None)`. Velocity anchor: `--delta-v-kms` (classical) **or** `--beta` (final
v/c, relativistic). Exhaust anchor: `--exhaust-velocity-kms` **or** `--isp-s` (→ `v_e = Isp·g₀`)
**or** `--fuel` (bundled ideal `v_e`). **Regime is chosen by the velocity form** — `--beta` →
relativistic; `--delta-v-kms` → classical. `--relativistic` only affects the exhaust+mass_ratio
case (which velocity to emit); combining it with `--delta-v-kms` is a curated error (relativistic
mode is defined against β). **Bundled fuels** (`--fuel`, ideal `v_e`; all MTA-movable): `chemical`
(4.4 km/s), `fission-thermal` (9 km/s), `fusion-dt` (**0.03c** effective — see the caveat below),
`fusion-catalyzed` (0.10c, extrapolated), `antimatter` (0.30c, extrapolated). Output:
`{mass_ratio (total, incl. legs), mass_ratio_single_burn, propellant_fraction, delta_v_kms (proper
Δv in relativistic mode), beta, exhaust_velocity_kms, isp_s, fuel, legs, relativistic,
payload_mass_t|null, propellant_mass_t|null, wet_mass_t|null, structure_fraction, model_note}`.
**Validation:** not exactly two anchor groups; >1 form within the exhaust group; `β∉[0,1)`;
non-positive Δv/v_e/isp/payload; `mass_ratio≤1`; `structure_fraction∉[0,1)`; unknown `--fuel`;
`--relativistic` with `--delta-v-kms` → curated `{"error"}` exit 1. Bad `--fuel`/`--legs` choice
or a non-numeric value → argparse exit 2. **Anchors:** Δv30/v_e30 → MR≈2.718, frac≈0.632;
β0.1/v_e0.1c → MR≈2.73 flyby / 7.44 rendezvous; β0.1/`fusion-dt` → MR≈28 flyby / ~804 rendezvous
(the "marginal generation ship"); β0.1/photon → MR≈1.105.

> **Caveat — `fusion-dt` v_e.** The request quotes an ideal D-T band of
> ~0.05–0.09 c but its own **acceptance anchor** pins `fusion-dt` at *v_e ≈ 0.03 c* (0.05 c gives
> only MR≈7.4, not the anchor's ≈28). The testable anchor wins: it is bundled at **0.03 c** as a
> conservative *effective* exhaust velocity. Flagged in the per-fuel note + `model_note`; every
> value is overridable via `--exhaust-velocity-kms`/`--isp-s`.

#### `beam-sail` (G2)
Thrust, acceleration, and (optional) final velocity of a beam-driven sail. Thrust
`F = (1+R)·P/c` (R = reflectivity: R→1 reflective `2P/c`, R→0 absorptive `P/c`); `a = F/m`
(m = sail + payload). Optional final velocity over an acceleration length (`--accel-distance-au`,
`v=√(2·a·d)`) or time (`--accel-time-days`, `v=a·t`) — first-order non-relativistic.
```bash
query.py beam-sail --beam-power-w 100e9 --reflectivity 1.0 --sail-mass-kg 1000   # F ≈ 667 N
query.py beam-sail --beam-power-w 100e9 --sail-area-m2 1e6 --areal-mass-gm2 1.0 --payload-mass-kg 100 --accel-time-days 10
```
Core: `propulsion.compute_beam_sail(beam_power_w, sail_area_m2=None, areal_mass_gm2=None,
sail_mass_kg=None, payload_mass_kg=0.0, reflectivity=0.9, wavelength_nm=None,
transmit_aperture_m=None, accel_distance_au=None, accel_time_days=None)`. Sail mass from
`--sail-mass-kg` **or** `--areal-mass-gm2 + --sail-area-m2`. `--wavelength-nm + --transmit-aperture-m`
(both or neither) → a diffraction `beam_range_note`. Output: `{thrust_n, acceleration_ms2,
final_velocity_kms|null, beta|null, beam_energy_j|null, sail_area_m2, total_mass_kg, sail_mass_kg,
payload_mass_kg, reflectivity, beam_range_note, model_note}`. **Validation:** non-positive
beam_power/area/mass; `reflectivity∉[0,1]`; negative payload; no mass source; both
`--accel-distance-au` and `--accel-time-days` (argparse mutex → exit 2); only one of
wavelength/aperture → curated `{"error"}` exit 1. **Anchor:** P=100 GW reflective (R=1) → F≈667 N.

### ISM drag / magnetic sail (Phase AC — pure math + bundled ISM/fusion constants, no network)

Two `query.py`-only calculators for the sibling repo's Packet 16 (STL Colonization Propulsion),
**Group K** — the magnetic interaction of a vehicle with the interstellar medium: the one
scope-shaping STL gap Groups G–J did not enumerate. They complement Group G (`rocket-equation` =
"can you carry the fuel"; `beam-sail` = "can a photon beam push you"; **Group K = "what does the ISM
do to you — brake you, or feed a ramjet"**) and the `dust-*` subcommands (ISM *column* for
extinction, not magnetic momentum exchange). Pure-math, self-validating (curated `{"error"}` exit 1;
argparse exit 2). `core/ism_drag.py`; the bundled ISM/fusion constants live in
`core/ism_drag_tables.py` (isolated, like `core/propulsion_tables.py`). The **physics is durable**
(magnetopause pressure balance `B²/2μ₀ = kρv²`; momentum flux `ṁ = ρvA`; the net-thrust inequality
`v_e > v`); the *parameter values* (`k`, `C_d`, fusion `f`, `η`, the ISM defaults) are present-day /
first-principles ancestors, **overridable** (Mature-Technology Assumption). `_MU_0`/`_M_PROTON` were
added to `core/equations.py`.

> **The ISM density is a caller-supplied parameter, never re-derived** (like `bioregen-area`'s PAR).
> Defaults flag to the sibling **Local-Interstellar-Environment** packet: `--ism-density-cm3` default
> **0.1** (Local Interstellar Cloud n(H I); the Local Bubble hot interior is ~0.005), mean
> `--ion-mass-amu` **1.3** (H+He). **Ionization caveat (in every output as `ionization_note`):** the
> real LIC is only ~22% H / ~39% He ionized and a magsail/ramscoop couples to *charged* particles
> only, so "fully ionized" overestimates the interacting density ~4× — pass the *ion* density if
> accuracy matters. **Coefficient provenance:** drag `C_d`=1.0 (Zubrin &
> Andrews' explicit "unity over the magnetospheric boundary area"); standoff `k`=1.0 (simple pressure
> balance; the compressed-to-dipole field factor is f=2 / 2.44 Chapman-Ferraro — set `--standoff-coeff`
> for that convention); fusion `f` p-p/CNO **0.71%**, D-D **0.38%** (catalyzed cycle); default `η`=0.1
> (low directed-exhaust fraction; ideal η=1 gives p-p `v_e`≈0.12c). Echoed in each `model_note`.

#### `magsail` (K1)
Magnetic-sail braking against the ISM. `ρ = n·m̄·x_ion`; magnetopause standoff → drag
`F = C_d·½·ρv²·π·R_mp²`. Optional deceleration (`--vehicle-mass-t`) and a single-law
stopping distance/time (`--velocity-final-kms`, requires the mass) from the analytic `v^(4/3)`
integral.
> **Phase AD (A1) — the standoff now depends on the sail anchor.** The **coil-pair** anchor uses
> the **exact on-axis current-loop field** `B(z)=μ₀·I·R²/(2(R²+z²)^{3/2})`, inverting the pressure
> balance `B(R_mp)²/2μ₀ = kρv²` algebraically: `R_mp = √([μ₀·I²·R⁴/(8kρv²)]^{1/3} − R²)`. The
> **moment-only** anchor (no geometry) keeps the **far-field dipole** `R_mp =
> [μ₀·m_dip²/(8π²·k·ρv²)]^(1/6)`. Both are echoed — `magnetopause_radius_km` (the reported value)
> and `magnetopause_radius_farfield_km` (the far-field cross-check); they converge once
> `R_mp ≳ 3·R_coil`, but for a large coil the exact standoff sits **inside** the coil (deep near
> field) and is far smaller than the far-field value. `F_drag ∝ v^(4/3)` holds only in the far
> field. **(A2)** For constant ISM the closed-form stopping distance/time are **exact** (not an
> estimate); a varying-ISM multi-leg optimisation is a separate consuming tool.
```bash
query.py magsail --ism-density-cm3 0.1 --ion-mass-amu 1.0 --beta 0.1 --magnetic-moment-am2 3.14e15 --vehicle-mass-t 1000
query.py magsail --beta 0.1 --coil-radius-m 100000 --coil-current-a 100000        # exact near-field standoff
query.py magsail --beta 0.1 --magnetic-moment-am2 1e15 --ionization-fraction 0.5   # only ions couple
```
Core: `ism_drag.compute_magsail(ism_density_cm3=None, ion_mass_amu=None, velocity_kms=None,
beta=None, coil_current_a=None, coil_radius_m=None, magnetic_moment_am2=None, standoff_coeff=None,
drag_coeff=None, vehicle_mass_t=None, velocity_final_kms=None, ionization_fraction=None)`. Velocity —
exactly one of `--velocity-kms`/`--beta` (argparse mutex; `0<β<1`). Sail — exactly one of the coil
pair (`--coil-current-a`+`--coil-radius-m`) or `--magnetic-moment-am2`. **Phase AD (A3)**
`--ionization-fraction` (default 1.0, valid `(0,1]`) scales the interacting density — only charged
particles couple. Output adds `magnetopause_radius_farfield_km` and `ionization_fraction` to the
prior keys. **Validation:** the prior matrix **plus** `ionization_fraction ∉ (0,1]` → curated
`{"error"}` exit 1; the velocity mutex / non-numeric → argparse exit 2. **`near_field_warning`** is
now informational (the exact loop field is valid in the near field): set when `R_mp ≲ R_coil`, or
when the ram pressure exceeds the peak central field (no standoff — `R_mp` clamped to `R_coil`).
**Anchors:** the R_mp ≈ 101 km / drag ≈ 2.38 kN / a ≈ 2.4×10⁻³ m/s² headline is the **moment-only**
(far-field) anchor (`m_dip = I·π·R²`, I=R=1e5), byte-identical to Phase AC; the **coil-pair** anchor
with the same I/R gives the exact near-field `R_mp ≈ 13 km` (far-field cross-check ≈ 101 km);
`--ionization-fraction 1.0` is byte-identical to Phase AC.

#### `ramscoop` (K2)
Bussard ramjet drag-vs-thrust verdict. Scoop area `A_mp = π R_mp²` (magnetopause, like K1) or a
supplied `--scoop-area-km2`; collected flux `ṁ = ρ·v·A_mp`; ideal fusion exhaust
`v_e = √(2·η·f·c²)` (or explicit `--exhaust-velocity-kms`). Reaction `ṁ·v_e`, collection cost `ṁ·v`,
magnetic drag `C_d·½ρv²A_mp`, so **`F_net = ṁ(v_e − v) − F_drag`** → `verdict` "drive"/"brake". Net
thrust needs at minimum `v_e > v`, and the drag makes the real threshold stricter — the crossover
`v_crossover = v_e/(1 + C_d/2)` (the common `v^(1/3)` factor cancels, so this holds for both the
field-derived and fixed-area scoop). Above it the ramjet is a net **brake** (Zubrin & Andrews 1985).
```bash
query.py ramscoop --fuel pp --beta 0.1 --coil-radius-m 100000 --coil-current-a 100000
query.py ramscoop --fuel pp --fusion-efficiency 1.0 --beta 0.01 --scoop-area-km2 1000
query.py ramscoop --exhaust-velocity-kms 50000 --beta 0.05 --scoop-area-km2 1000
```
Core: `ism_drag.compute_ramscoop(ism_density_cm3=None, ion_mass_amu=None, velocity_kms=None,
beta=None, coil_current_a=None, coil_radius_m=None, scoop_area_km2=None, magnetic_moment_am2=None,
fuel=None, fusion_efficiency=None, exhaust_velocity_kms=None, standoff_coeff=None, drag_coeff=None,
ionization_fraction=None)`. **Phase AD (A3)** `--ionization-fraction` (default 1.0) scales the
interacting density (a fixed `--scoop-area-km2` → drag & collected mass flux both ∝ ρ, so
`--ionization-fraction 0.5` halves both; echoed as `ionization_fraction`).
Velocity — exactly one of `--velocity-kms`/`--beta`. Scoop — exactly one of the coil pair /
`--magnetic-moment-am2` / `--scoop-area-km2`. Exhaust — exactly one of `--fuel {pp,cno,dd}`
(+ optional `--fusion-efficiency`, default 0.1) or `--exhaust-velocity-kms`. Output: `{velocity_kms,
beta, ism_density_cm3, ion_mass_amu, magnetopause_radius_km, magnetic_moment_am2|null, scoop_area_km2,
collected_mass_flux_kgs, fuel, fusion_yield_fraction, fusion_efficiency, exhaust_velocity_kms,
exhaust_beta, standoff_coeff, drag_coeff, reaction_thrust_n, collection_drag_n, magnetic_drag_n,
net_force_n, verdict ("drive"|"brake"), crossover_velocity_kms, ionization_note, model_note}`.
**Validation:** non-positive density/ion-mass/area/v_e/k/C_d; `β∉(0,1)`; `η∉(0,1]`;
`ionization_fraction ∉ (0,1]`; velocity/scoop/exhaust not exactly one anchor; scoop area + field
both; `--fusion-efficiency` with `--exhaust-velocity-kms`; unknown `--fuel` → curated `{"error"}`
exit 1; the velocity mutex, a bad `--fuel` choice, or a non-numeric value → argparse exit 2. **Anchor:** `--fuel pp` at β0.1 →
`v_e`≈11,300 km/s (η=0.1) → **brake**; the *ideal* η=1 case has `v_e`≈0.12c > v (reaction > collection)
yet magnetic drag still flips it to **brake** (the Zubrin & Andrews result); low β + high η → **drive**.

### Momentum / impact tools (Phase AD — pure math, no network)

Two `query.py`-only calculators added in Phase AD Phase 2: a momentum-beam drive (`pellet-stream`,
extending `core/propulsion.py` — the mass analog of `ramscoop`) and hypervelocity grain-impact
energetics (`dust-impact`, new `core/dust_impact.py`). Both pure-math, self-validating (curated
`{"error"}` exit 1; argparse exit 2).

#### `pellet-stream` (C2)
Pellet-stream (momentum-beam) drive: a station fires pellets at stream velocity `v_s`; the closing
velocity on a vehicle at `v` is `u = v_s − v`; thrust `F = g·ṁ·u` (`g = 2` reflect / `1` absorb),
delivered power `½·ṁ·u²`. `verdict = "drive"` while `v_s > v`, else `"no-thrust"` (crossover at
`v = v_s`) — the mass analog of the `ramscoop` drive/brake crossover.
```bash
query.py pellet-stream --stream-velocity-kms 30000 --mass-flow-rate-kgs 1 --beta 0.05   # F ≈ 3.0e7 N, drive
query.py pellet-stream --stream-velocity-kms 30000 --pellet-mass-kg 0.5 --pellet-rate-hz 2 --velocity-kms 30000  # no-thrust
```
Core: `propulsion.compute_pellet_stream(stream_velocity_kms=None, mass_flow_rate_kgs=None,
pellet_mass_kg=None, pellet_rate_hz=None, velocity_kms=None, beta=None, coupling="reflect",
vehicle_mass_t=None)`. Mass-flow anchor — exactly one of `--mass-flow-rate-kgs` or
(`--pellet-mass-kg` + `--pellet-rate-hz`); the two are an argparse mutex (both → exit 2). Velocity —
exactly one of `--velocity-kms` (admits `0`) / `--beta` (`0<β<1`; argparse mutex). Output:
`{stream_velocity_kms, vehicle_velocity_kms, beta, relative_velocity_kms, mass_flow_rate_kgs,
coupling, thrust_n, delivered_power_w, verdict, crossover_velocity_kms, acceleration_ms2|null,
model_note}`. **Validation:** `stream_velocity_kms ≤ 0`; mass-flow anchor not exactly one (partial
pellet pair); velocity anchor not exactly one; `β∉(0,1)`; `vehicle_mass_t ≤ 0` → curated `{"error"}`
exit 1. The velocity mutex, mass-flow mutex, a bad `--coupling` choice, a missing required
`--stream-velocity-kms`, or a non-numeric value → argparse exit 2. `verdict:"no-thrust"` (at/above
crossover) is a **clean-negative** result (exit 0), not an error. **Anchor:** `v_s=30000, ṁ=1,
β=0.05, reflect` → `u≈15010 km/s`, `F≈3.0×10⁷ N`, drive; `absorb` = half the thrust.

#### `dust-impact` (C3)
Hypervelocity dust-grain impact energetics: mass `m = (4/3)π r³ ρ` (or explicit); kinetic energy
`½mv²` (Newtonian) → `(γ−1)mc²` once `β > 0.1` (the `relativistic` flag); momentum `mv → γmv`;
TNT-equivalent `E / 4.184e6` kg; and, over a supplied ISM column, cumulative impacts `N = n·A·L`
and energy fluence `N·E/A`.
> **Penetration depth is deliberately NOT computed** (it needs material-specific stopping data) —
> `penetration_handoff_note` directs to the Packet-13 `shielding-attenuation` (mass/CSDA) and
> `radiator-area` (thermal) tools. This sizes the incident energy/momentum only.
```bash
query.py dust-impact --grain-radius-um 1 --grain-density-kgm3 1000 --beta 0.1   # E ≈ 1.88 J, ~0.45 mg TNT
query.py dust-impact --grain-radius-um 1 --grain-density-kgm3 1000 --beta 0.2 --dust-density-m3 1e-6 --frontal-area-m2 100 --path-length-ly 4
```
Core: `dust_impact.compute_dust_impact(grain_radius_um=None, grain_density_kgm3=None,
grain_mass_kg=None, velocity_kms=None, beta=None, dust_density_m3=None, frontal_area_m2=None,
path_length_ly=None)`. Grain anchor — (`--grain-radius-um` + `--grain-density-kgm3`) or
`--grain-mass-kg` (radius/mass are an argparse mutex; radius without density → exit 1). Velocity —
exactly one of `--velocity-kms`/`--beta` (argparse mutex; `0<β<1`). Cumulative-fluence set — all
three of `--dust-density-m3` + `--frontal-area-m2` + `--path-length-ly`, or none (partial → exit 1);
both cumulative fields are `null` when omitted. Output: `{grain_mass_kg, grain_radius_um,
grain_density_kgm3, velocity_kms, beta, relativistic, lorentz_factor, impact_energy_j,
impact_energy_tnt_kg, momentum_kgms, dust_density_m3, frontal_area_m2, path_length_ly,
impacts_total|null, energy_fluence_j_m2|null, penetration_handoff_note, model_note}`.
**Validation:** grain anchor not exactly one; non-positive radius/density/mass; velocity anchor not
exactly one; `β∉(0,1)`; a partial or non-positive cumulative set → curated `{"error"}` exit 1; the
grain/velocity mutexes and non-numeric values → argparse exit 2. **Build note (verified
2026-07-03):** a 1 µm / 1000 kg·m⁻³ grain is `m ≈ 4.19×10⁻¹⁵ kg`; at β 0.1 the energy is `≈1.88 J`
(≈1.9×10⁰ J) and the TNT-equivalent `≈0.45 mg` (1 kg TNT ≡ 4.184 MJ). *This corrects two
transcription slips in `PHASE_AD_PLAN.md`:* the plan's "1.9×10² J / 40 mg" figures were computed at
`v = c`, not β 0.1; and its `E/4.184e12` divisor yields **kilotons**, not kg (the kg divisor is
`4.184×10⁶ J`). The relativistic auto-switch is `β > 0.1` (the plan prose said ~0.01, but its own
acceptance cases require `false@β0.05` / `true@β0.2`).

### Megastructure scale (Phase Z — pure math + bundled material/body tables, no network)

Three `query.py`-only calculators for the sibling repo's Packet 17 (Settlement / Megastructure).
They give the **material size limit** — the ceiling that pairs with `spin-comfort` (Phase W)'s
human-comfort *minimum*: hoop stress caps how big a spinning shell can be for a given tensile
strength (why steel O'Neills top out at a few km and ringworlds need unobtanium). Self-validating
(curated `{"error"}` exit 1; argparse exit 2). `core/megastructure.py`; the material + body tables
live in `core/materials_tables.py`. The **physics is durable** (`σ=ρv²`, the Pearson uniform-stress
taper); the material strengths are **present-day/near-term ancestors, overridable** (MTA);
nanomaterials are bundled at their theoretical/measured-intrinsic strength and **hard-flagged that
bulk material is 1–2 orders weaker**. Values researched 2026-07-02.

**Bundled materials** (`--material`; ρ kg/m³ / σ_tensile MPa): structural-steel 7850/400,
titanium-alloy 4430/950, aluminium-alloy 2700/500, carbon-fiber 1600/4000 (**raw filament**, not
a laminate), kevlar 1440/3600, uhmwpe 970/2700, basalt-fiber 2700/4100, silicon-carbide 3200/400
(brittle), cnt-theoretical 1350/100000, graphene-theoretical 2200/130000 (both extrapolated).
`σ/ρ` (specific strength) is the sole figure of merit for a thin shell. **Bundled bodies**
(`--body`): earth/mars/moon/ceres (surface radius, synchronous-orbit radius, surface gravity).

#### `spin-stress` (H1)
Max spin state a material can hold: `σ_allow = σ_tensile/SF`, `v_max = √(σ_allow/ρ)`; then one
solve form — `--target-gravity-g` → `max_radius = v_max²/a`; `--radius-m` alone → `max_gravity_g
= v_max²/(r·g₀)`; `--rpm` + `--radius-m` → the actual `hoop_stress_mpa` + `margin`.
```bash
query.py spin-stress --material structural-steel --target-gravity-g 1 --safety-factor 1   # r_max ≈ 5.2 km
query.py spin-stress --material carbon-fiber --target-gravity-g 1 --safety-factor 1        # r_max ≈ 254 km
```
Core: `megastructure.compute_spin_stress(material=None, density_kgm3=None,
tensile_strength_mpa=None, safety_factor=3.0, target_gravity_g=None, radius_m=None, rpm=None)`.
Material via `--material` **or** explicit `--density-kgm3 + --tensile-strength-mpa` (not both).
`--safety-factor` default 3 (≥1). Output includes `max_radius_m/_km` | `max_gravity_g` |
`hoop_stress_mpa`+`margin` (the non-active forms are `null`), plus `allowable_stress_mpa`,
`max_tangential_velocity_ms`, `specific_strength_note`, `notes` (material caveats). **Validation:**
unknown material; ρ or σ ≤ 0; `SF<1`; not exactly one solve form; material *and* explicit both;
`--rpm` without `--radius-m`; non-positive anchors → curated `{"error"}` exit 1; bad `--material`
choice / non-numeric → argparse exit 2. **Anchors:** steel SF1/1 g → v_max ≈ 226 m/s, r_max ≈ 5.2
km; carbon-fiber → v_max ≈ 1580 m/s, r_max ≈ 254 km (the "steel = km-scale, composite = 100-km-scale"
result). Default SF 3 shrinks these ~√3× in v_max (3× in radius).

#### `tether-taper` (H2)
Pearson uniform-constant-stress space-elevator taper ratio:
`T = exp[(ρ·g₀/σ_allow)·(R − 1.5R²/R_s + 0.5R⁴/R_s³)]` (the synchronous-orbit ω is Kepler-derived
from R/R_s). Feasibility band: ≲2 practical, ≫10 impractical; a material that can't span the well
overflows → `taper_ratio: null`, `feasible: false` (a **normal result, exit 0** — not an error).
```bash
query.py tether-taper --material cnt-theoretical --body earth --safety-factor 1   # taper ≈ 1.9 (feasible)
query.py tether-taper --material structural-steel --body earth                     # taper null, feasible false
```
Core: `megastructure.compute_tether_taper(material=None, density_kgm3=None,
tensile_strength_mpa=None, safety_factor=3.0, body=None, surface_gravity_ms2=None,
surface_radius_km=None, geo_radius_km=None)`. Body via `--body` **or** explicit
`--surface-gravity-ms2 + --surface-radius-km + --geo-radius-km` (not both). Output:
`{…material fields…, body, surface_gravity_ms2, surface_radius_km, geo_radius_km,
characteristic_velocity_ms, characteristic_length_km, taper_ratio (or null on overflow), feasible,
notes, model_note}`. **Validation:** unknown material/body; ρ/σ/g/R ≤ 0; `SF<1`; `geo_radius ≤
surface_radius`; not exactly one material source / one body source → curated `{"error"}` exit 1;
bad `--material`/`--body` choice / non-numeric → argparse exit 2. **Validated anchors:** Earth steel
→ infeasible (∞); Earth CNT@100 GPa (SF 1) → **taper ≈ 1.9** (the canonical "modest taper, excellent
material" result); graphene ≈ 2.3; kevlar → ~10⁸ (impractical). The **Moon** carries a caveat (its
naive synchronous radius lies beyond the Hill sphere — a real lunar elevator is the L1/L2 form).

#### `dyson-collector` (H3)
Swarm/shell area & mass to intercept a fraction `f` of a star's luminosity at orbit `R`:
`P = f·L`, area `A = f·4πR²`, mass `= A·areal_mass`, incident flux `= L/(4πR²)`.
```bash
query.py dyson-collector --luminosity-lsun 1 --fraction 0.01 --orbit-au 1   # P ≈ 3.8e24 W, area ≈ 2.8e21 m²
query.py dyson-collector --star "Tau Ceti" --fraction 1 --orbit-au 0.7      # --star → SIMBAD luminosity
```
Core: `megastructure.compute_dyson_collector(luminosity_lsun=None, fraction=None, orbit_au=None,
areal_mass_kgm2=0.01)`. Luminosity via `--luminosity-lsun` **or** `--star` (SIMBAD + regions
resolution in the query.py handler — the group's only networked entry; a SIMBAD failure returns
`{"error"}`). `--fraction` (0,1] and `--orbit-au` required. Output: `{intercepted_power_w,
collector_area_m2, collector_area_au2, collector_mass_kg, incident_flux_wm2, fraction, orbit_au,
luminosity_lsun, areal_mass_kgm2, model_note}`. **Validation:** `L≤0`; `fraction∉(0,1]`; `orbit_au≤0`;
`areal_mass≤0` → curated `{"error"}` exit 1; `--luminosity-lsun` **and** `--star` both, or neither,
or missing `--fraction`/`--orbit-au` → argparse exit 2. **Anchor:** Sun, f 0.01, 1 AU → P ≈ 3.828×10²⁴
W, area ≈ 2.81×10²¹ m², incident flux ≈ 1361 W/m² (the solar constant).

#### `orbital-ring` (Phase AD C4 — no network)
Orbital-ring rotor velocity & support balance: a stationary ring/sheath at altitude is held up
against gravity by a **faster-than-orbital rotor** magnetically coupled inside it. Local gravity
`g(r) = g₀·(R/r)²` (r = R + altitude); orbital velocity `v_orb = √(g·r)`; the rotor's excess
centrifugal force supports the ring — `λ_rotor·(v_rotor²/r − g) = λ_ring·g` ⟹
`v_rotor = √(r·g·(1 + λ_ring/λ_rotor))` (`support_ratio = λ_ring/λ_rotor`; equal masses →
`v_rotor = √2·v_orb`). Uses the bundled `_BODIES` `g₀`/`R_km` (no table edit — Locked decision C4-7).
```bash
query.py orbital-ring --body earth --altitude-km 300 --ring-mass-per-length-kgm 100   # v_orb≈7.7, v_rotor≈10.9 km/s
query.py orbital-ring --surface-gravity-ms2 9.81 --body-radius-km 6371 --altitude-km 300 --ring-mass-per-length-kgm 100
```
Core: `megastructure.compute_orbital_ring(body=None, surface_gravity_ms2=None, body_radius_km=None,
altitude_km=None, ring_mass_per_length_kgm=None, rotor_mass_per_length_kgm=None)`. Body — exactly one
of the bundled `--body {earth,mars,moon,ceres}` or explicit `--surface-gravity-ms2` +
`--body-radius-km`. `--rotor-mass-per-length-kgm` defaults to `--ring-mass-per-length-kgm`. Output:
`{body, surface_gravity_ms2, body_radius_km, altitude_km, orbital_radius_km, local_gravity_ms2,
orbital_velocity_kms, rotor_velocity_kms, rotor_velocity_over_orbital, ring_mass_per_length_kgm,
rotor_mass_per_length_kgm, support_ratio, rotor_ke_per_length_jm, model_note}`. **Validation:** body
+ explicit both / a partial explicit pair / no body anchor; unknown `--body`; non-positive
g/R/altitude/ring-λ/rotor-λ → curated `{"error"}` exit 1; a bad `--body` choice, missing required
`--altitude-km`/`--ring-mass-per-length-kgm`, or a non-numeric value → argparse exit 2. **Anchor:**
Earth (g₀=9.81, R=6371 km), alt 300 km → r=6671 km, g≈8.95 m/s², `v_orb≈7.73 km/s`,
`v_rotor≈10.93 km/s`, `ratio=√2≈1.414`; doubling λ_ring (rotor fixed) raises `v_rotor` by √1.5≈1.22×.

### PAR / photosynthesis by stellar type (Phase AA — pure math, network only on `--star`)

One `query.py`-only, pure-math, self-validating calculator for the sibling repo's Packet 18
(Astrobiology / Planetary Protection). It answers the *natural-light* / native-photosynthesis
question: **PAR** (photosynthetically active radiation, ~400–700 nm) is a *fraction* of a star's
output that shifts by spectral type — G ≈ 0.37 (blackbody), but K/M shift redward so far fewer
usable PAR photons reach a leaf per W/m² of insolation (the red-dwarf photosynthesis-deficit
question). Its **PPFD output feeds back into the Phase-X `bioregen-area` tool**, which takes PAR
as a caller-supplied input. `core/par_flux.py`; the two new constants (`_PLANCK_H`, `_AVOGADRO`,
plus the nominal `_SOLAR_LUMINOSITY_W`) live in `core/equations.py`. No DB, no RNG, no time.

> **SED model — blackbody, an explicit approximation.** The SED is a **Planck blackbody at Teff**
> (`sed_model: "blackbody (approx — real SED deviates)"`). The physics — the Planck function +
> PAR-band integration — is durable; the blackbody *SED* is the approximation. Real stellar SEDs
> deviate, and the deviation is one-directional for cool stars: **M-dwarf line blanketing suppresses
> the visible/blue**, so a real red dwarf's PAR fraction is **lower** than its blackbody value and the
> true photosynthesis deficit is **larger** than reported here (blackbody is *optimistic* for K/M
> stars). Concretely, a **3000 K blackbody gives f_PAR ≈ 0.081**, whereas real late-M SEDs sit nearer
> **0.04–0.07** — the blackbody reproduces that lower band only at **Teff ≈ 2700 K** (a late-M dwarf).
> Real-spectrum (PHOENIX / BT-Settl) SEDs are a v2 refinement; the gap is spelled out in `model_note`.

#### `par-flux`
PAR fraction, PAR irradiance, PPFD, and the red-star deficit vs G2 from a blackbody SED.
- **PAR fraction:** `f_PAR = ∫_{lo}^{hi} B_λ(T) dλ / (σT⁴/π)` — in-band Planck energy over the
  Stefan–Boltzmann total (which closes ∫₀^∞, avoiding an unbounded integral). Integrated by
  composite Simpson's rule.
- **PAR irradiance:** `par_irradiance_wm2 = insolation_wm2 · f_PAR`.
- **PPFD** [µmol photons·m⁻²·s⁻¹]: the in-band **photon** flux — `par_irradiance` divided by the
  **band-mean photon energy** `Ē = (∫B_λ dλ)/(∫B_λ·λ/hc dλ)`, then ÷ N_A · 1e6. Cross-checks against
  the standard PAR mean ≈ **0.219 J/µmol** (echoed as `j_per_umol`) and the ≈2000 µmol full-sun anchor.
- **Deficit vs G2:** `par_deficit_vs_g2 = f_PAR(5772 K) / f_PAR(Teff)` — how many × more insolation a
  redder star needs for the same PAR (computed at the same band, so an override is apples-to-apples).
```bash
query.py par-flux --teff-k 5772 --insolation-wm2 1361                 # Sun: f_PAR≈0.37, PPFD≈2277
query.py par-flux --spectral-type K2V --luminosity-lsun 0.29 --distance-au 0.5
query.py par-flux --teff-k 2700 --insolation-wm2 1361                 # late-M: f_PAR≈0.05, deficit≈7.3
query.py par-flux --star "Tau Ceti" --insolation-wm2 1361 --par-band-nm 400 750
```
Core: `par_flux.compute_par_flux(teff_k=None, spectral_type=None, star=None, insolation_wm2=None,
luminosity_lsun=None, distance_au=None, par_band_nm=(400.0, 700.0))`.
- **Teff — exactly one source:** `--teff-k` (offline) / `--spectral-type` (→ `main_sequence_stars`
  ceiling-rule lookup, offline local DB) / `--star` (→ SIMBAD + regions, **the only networked path**;
  resolved inside the core, lazily). **Insolation — exactly one source:** `--insolation-wm2` (direct)
  / (`--luminosity-lsun` + `--distance-au`, → `S = L_sun·L/(4π(d·AU)²)`; 1 L☉ @ 1 AU ≈ 1361 W/m²).
- **`--par-band-nm LO HI`** (nm, default `400 700`).
- **Output (units on every field):** `{teff_k (K), par_fraction, insolation_wm2 (W/m²),
  par_irradiance_wm2 (W/m²), ppfd_umol_m2_s (µmol·m⁻²·s⁻¹), par_deficit_vs_g2 (× vs 5772 K),
  photon_energy_mean_j (J/photon), j_per_umol (J/µmol), band_nm ([lo, hi] nm),
  sed_model ("blackbody (approx — real SED deviates)"), feeds_note ("PPFD → bioregen-area PAR input
  (Phase X)"), model_note}`. **The `ppfd_umol_m2_s` value is what feeds `bioregen-area`'s
  `--ppfd-umol` anchor** — that is the whole synergy (`bioregen-area` treats PAR/PPFD as an input;
  `par-flux` derives it from the star).
- **Anchors:** Sun (`--teff-k 5772`) → f_PAR ≈ 0.366 (blackbody; real solar ≈ 0.39 — see C1), and at
  `--insolation-wm2 1361` → PAR ≈ 499 W/m², PPFD ≈ 2277 µmol·m⁻²·s⁻¹, deficit 1.0; late-M
  (`--teff-k 2700`) → f_PAR ≈ 0.050, `par_deficit_vs_g2` ≈ 7.3.

> **Phase AD (C1) — `--sed {blackbody,real}` (default `blackbody`).** `--sed real` swaps the Planck
> f_PAR for a bundled **BT-Settl (CIFIST2011)** table (`core/par_flux_tables.py`; `_REAL_SED_FPAR`,
> log g 4.5, [M/H] 0, `f_PAR = ∫400–700nm F_λ / ∫F_λ` computed at build from SVO Theoretical Spectra
> — Allard+ 2012 / Baraffe+ 2015), linear-interpolated in Teff. It captures the **M-dwarf TiO/VO/H₂O
> line blanketing** a blackbody misses, so a real red dwarf's f_PAR is far **below** blackbody
> (**3000 K real ≈ 0.023 vs blackbody ≈ 0.081** — a *larger*, more realistic deficit), while a
> Sun-like star's real f_PAR (**≈ 0.389**) sits just **above** blackbody (≈ 0.366) and matches the
> measured ASTM-E490 solar ~0.39. *(This corrects the plan's Sun estimate — the true value is ~0.39,
> not 0.40–0.45.)* PPFD / band-mean photon energy still use the Planck band shape at Teff (documented
> approximation — the table carries only the energy fraction). **The table is band-fixed at 400–700 nm
> and covers 2600–7000 K:** `--sed real` with a non-default `--par-band-nm` **errors** (→ use
> `--sed blackbody`), as does a Teff off that grid. `sed_model` echoes the choice.
> **Default note (deviation from PHASE_AD_PLAN.md, user decision 2026-07-03):** the plan specified
> `--sed real` as the default, but that would change the existing `par-flux` output for the consumer,
> so the default stays **`blackbody`** (backward-compatible) and `real` is opt-in.

> **Validation (self-validating — Phase-H/P):** curated `{"error"}` exit 1 for `teff_k ≤ 0`;
> `insolation_wm2 ≤ 0`; `luminosity_lsun ≤ 0` or `distance_au ≤ 0`; **not exactly one** Teff source
> **or** insolation source; a PAR band with `lo ≥ hi` or ≤ 0; an unresolvable `--spectral-type`; a
> SIMBAD failure on `--star` (returned immediately); **(C1)** `--sed real` with a non-default
> `--par-band-nm` or a Teff off the 2600–7000 K grid. Argparse exit 2 for a non-numeric value, a
> malformed `--par-band-nm` (not two numbers), or a bad `--sed` choice. *(The "exactly one Teff / one
> insolation source" rules are **core** checks → exit 1, like `spin-comfort`'s anchors.)*

### Planetary energy balance / terraforming (Phase AB — pure math, no network)

Three `query.py`-only, pure-math, self-validating calculators for the sibling repo's Packet 19
(Planetary Transformation / Terraforming) — **Group J**, the last of the combined four-group
request. They model terraforming feasibility as a **radiative / mass balance** — can a planet be
warmed to habitable temperatures, how much greenhouse forcing or mirror area that takes, and how
much volatile mass an atmosphere/ocean needs — reporting the **demand** side only (volatile
*supply* is the volatile-geography canon's authority). `core/terraforming.py`; **no bundled table**
— reuses `_STEFAN_BOLTZMANN` / `_M_PER_AU` / `_G` / `_EARTH_MASS_KG` / `_SOLAR_LUMINOSITY_W` from
`core/equations.py`, with one inline reference `_EARTH_ATM_MASS_KG = 5.15e18`. No network, no DB,
no RNG, no time. The physics is durable textbook closed form; present-day albedos are overridable
ancestors. The `--luminosity-lsun` + `--distance-au` → S conversion is the same expression as
Phase-AA `par-flux`. Complements `atmosphere-retention` (Jeans escape) and `habitable-zone`.

#### `equilibrium-temp` (J1)
Planetary equilibrium temperature + a greenhouse surface temperature. `T_eq = [S(1−A)/(4σ)]^¼`;
surface via **at most one forcing form** — additive offset `T_s = T_eq + ΔT`, grey-atmosphere
`T_s = T_eq·(1 + ¾τ)^¼`, or the **inverse** (`--target-surface-k` → the ΔT and τ required to reach it).
**Phase AD (B) — with NO forcing form the result is the bare airless equilibrium**
(`t_surface_k = t_eq_k`, `regime = "airless"`); a `regime` field tags every result
(`airless`/`offset`/`grey`/`inverse`).
```bash
query.py equilibrium-temp --insolation-wm2 1361 --albedo 0.3                            # airless: T_s = T_eq ≈ 254.6 K
query.py equilibrium-temp --insolation-wm2 1361 --albedo 0.3 --greenhouse-delta-k 33    # Earth: 255→288 K
query.py equilibrium-temp --insolation-wm2 589 --albedo 0.25 --greenhouse-delta-k 0     # Mars: T_eq≈210 K
query.py equilibrium-temp --luminosity-lsun 1 --distance-au 1 --target-surface-k 288    # inverse → required forcing
```
Core: `terraforming.compute_equilibrium_temp(insolation_wm2=None, luminosity_lsun=None,
distance_au=None, albedo=0.3, greenhouse_delta_k=None, optical_depth=None, target_surface_k=None)`.
Insolation — exactly one source (`--insolation-wm2` **or** `--luminosity-lsun` + `--distance-au`,
→ 1 L☉ @ 1 AU ≈ 1361 W/m²). `--albedo` default 0.3, valid `[0, 1)`. Output: `{insolation_wm2 (W/m²),
albedo, t_eq_k (K), greenhouse_delta_k (K)|null, optical_depth|null, t_surface_k (K), required_forcing
|null, regime, model_note}` — the given forcing is echoed and the other is `null`; **`required_forcing`**
(only for the inverse `--target-surface-k`) is `{greenhouse_delta_k (K), optical_depth,
cooling_required (bool)}` (both values go **negative** when the target is below the bare equilibrium,
flagging that *cooling*, not greenhouse warming, is needed). **Validation:** insolation ≤ 0 (or
L/distance ≤ 0); albedo ∉ [0, 1); **more than one** forcing form (0 is now valid — the airless fix);
not exactly one insolation source; `optical_depth < 0`; `target_surface_k ≤ 0` → curated `{"error"}`
exit 1. **Anchors:** Earth (S1361, A0.3) → T_eq ≈ 255 K (airless T_s = T_eq), +ΔT 33 → 288 K (τ ≈ 0.85
reproduces the same 288 K); Mars (S589, A0.25) → T_eq ≈ 210 K.

#### `insolation-shift` (J2)
Orbital mirror (warm) / shade (cool) area to change the **sphere-averaged** absorbed flux by ΔS:
`A_m = |ΔS|·4πR_p² / solar_flux_at_planet`. Signed ΔS: **+ = mirror, − = shade** (carried in `mode`;
the area is a magnitude).
```bash
query.py insolation-shift --planet-radius-km 3390 --delta-insolation-wm2 20 --solar-flux-wm2 589
query.py insolation-shift --planet-radius-km 6371 --delta-insolation-wm2 -10 --luminosity-lsun 1 --distance-au 1
```
Core: `terraforming.compute_insolation_shift(planet_radius_km, delta_insolation_wm2,
solar_flux_wm2=None, luminosity_lsun=None, distance_au=None)`. Solar-flux — exactly one source
(`--solar-flux-wm2` **or** `--luminosity-lsun` + `--distance-au`). Output: `{planet_radius_km (km),
delta_insolation_wm2 (W/m², signed), solar_flux_wm2 (W/m²), mode ("mirror"|"shade"), mirror_area_m2
(m²), mirror_area_km2 (km²), area_vs_planet_cross_section (× πR_p²), model_note}`. **Validation:**
`planet_radius_km ≤ 0`; `delta_insolation_wm2 = 0` (no-op); not exactly one / non-positive solar-flux
source → curated `{"error"}` exit 1; missing required `--planet-radius-km`/`--delta-insolation-wm2` →
argparse exit 2. **Anchor:** a modest ΔS over Mars's `4πR² ≈ 1.44×10¹⁴ m²` → a mirror area of that
order (the cross-section ratio is exactly `4·|ΔS|/solar_flux`).

#### `atmosphere-mass` (J3)
Hydrostatic atmosphere mass ↔ surface pressure: `m = 4πR²·P / g` (and the inverse `P = m·g/(4πR²)`).
```bash
query.py atmosphere-mass --planet-radius-km 3390 --surface-gravity-ms2 3.71 --pressure-bar 1   # Mars 1 bar
query.py atmosphere-mass --planet-radius-km 6371 --planet-mass-earth 1 --volatile-mass-kg 5.15e18 --species n2
```
Core: `terraforming.compute_atmosphere_mass(planet_radius_km, surface_gravity_ms2=None,
planet_mass_earth=None, pressure_bar=None, volatile_mass_kg=None, species=None)`. Gravity — exactly
one source (`--surface-gravity-ms2` **or** `--planet-mass-earth` → `g = GM/R²`). Then exactly one of
`--pressure-bar` (→ mass) or `--volatile-mass-kg` (→ pressure). `1 bar = 10⁵ Pa`;
`atmosphere_mass_earth_atm` is the fraction of Earth's 5.15×10¹⁸ kg. `--species {n2,co2,o2,h2o}` is
an optional **echoed label** — the total column mass is species-independent. Output:
`{planet_radius_km (km), surface_gravity_ms2 (m/s²), species, surface_pressure_bar (bar),
atmosphere_mass_kg (kg), atmosphere_mass_earth_atm (× Earth), model_note}`. **Validation:**
`planet_radius_km ≤ 0`; not exactly one gravity source; not exactly one of pressure/mass;
non-positive g/pressure/mass; unknown `--species` → curated `{"error"}` exit 1; a bad `--species`
choice / non-numeric value → argparse exit 2. **Anchor:** Mars 1 bar (R 3390 km, g 3.71) →
m ≈ 3.9×10¹⁸ kg (~0.76 Earth atmospheres); the g derived from `--planet-mass-earth 0.107` matches
the explicit 3.71.

#### `volatile-delivery` (Phase AD C5 — no network)
The **supply** side of terraforming an atmosphere by redirecting icy bodies — the mass/energy
complement to `atmosphere-mass`'s demand side. Delivered volatile mass `m_vol = f·M`; optional
redirect burn mass ratio (classical Tsiolkovsky `MR = exp(Δv/v_e)` via `rocket-equation`'s bundled
fuel presets); impact energy `½·M·v_impact²` (+ TNT-equivalent `E/4.184e6` kg); and bodies needed
`N = M_atm_target / m_vol`.
```bash
query.py volatile-delivery --body-mass-kg 1e15 --volatile-fraction 0.5 --impact-velocity-kms 20 --target-atmosphere-mass-kg 5.15e18
query.py volatile-delivery --body-mass-kg 1e15 --delta-v-kms 1 --fuel fusion-dt   # redirect mass ratio
```
Core: `volatile_delivery.compute_volatile_delivery(body_mass_kg, volatile_fraction=0.5,
delta_v_kms=None, impact_velocity_kms=None, target_atmosphere_mass_kg=None, fuel=None,
exhaust_velocity_kms=None)`. Each add-on's outputs are `null` when its input is omitted:
`--delta-v-kms` (+ exactly one of `--fuel`/`--exhaust-velocity-kms`) → `redirect_mass_ratio`;
`--impact-velocity-kms` → `impact_energy_j`/`impact_energy_tnt_kg`; `--target-atmosphere-mass-kg` →
`bodies_needed`. Output: `{body_mass_kg, volatile_fraction, delivered_volatile_mass_kg, delta_v_kms,
fuel, exhaust_velocity_kms, redirect_mass_ratio, impact_velocity_kms, impact_energy_j,
impact_energy_tnt_kg, target_atmosphere_mass_kg, bodies_needed, model_note}`. **Validation:**
`body_mass_kg ≤ 0`; `volatile_fraction ∉ (0,1]`; `delta_v_kms ≤ 0`; `impact_velocity_kms ≤ 0`;
`target_atmosphere_mass_kg ≤ 0`; `--delta-v-kms` with zero or both exhaust anchors; `--fuel`/
`--exhaust-velocity-kms` **without** `--delta-v-kms`; unknown `--fuel` → curated `{"error"}` exit 1;
a bad `--fuel` choice, missing required `--body-mass-kg`, or a non-numeric value → argparse exit 2.
**Anchor:** `M=1e15 kg, f=0.5, v_impact=20 km/s` → delivered `5×10¹⁴ kg`, `E≈2×10²³ J`; target
`5.15×10¹⁸ kg` → `bodies_needed≈10 300`; `Δv=1 km/s` with `fusion-dt` → a modest `MR≈1.0001`.

> **Validation (self-validating — Phase-H/P):** all three follow the Phase-H/P contract — the §range
> and source-count checks return a curated `{"error"}` (exit 1); an unknown `--species` choice or any
> non-numeric value is argparse exit 2. *(The "exactly one insolation / gravity / pressure-or-mass"
> and the "at most one forcing form" [Phase AD B — zero forcing → airless] rules are **core**
> checks → exit 1.)*

### Solvent zones (Phase P — no network)

Two pure-math calculators backing the Worldbuilding "Solvent Habitable Zone" and
"Ice Line Calculator" panels. Both wrap **self-validating** core functions, so they
follow the **Phase H** contract (curated `{"error"}` exit 1, **not** the Phase N
raw-exception path): malformed/missing/non-numeric args → argparse **exit 2** (stderr);
out-of-range (luminosity ≤ 0, albedo ∉ [0, 1), `t_low ≥ t_high`, unknown solvent) →
`{"error": str}` **exit 1**; success → dict **exit 0**. Phase P uses **two temperature
models**: **M1 surface** `T_ref = 314.9 × (1−A)^0.25` (= 288 K at A=0.3, the alt-HZ
convention; solvent liquid bands) and **M2 equilibrium** `T_ref = 278.5 × (1−A)^0.25`
(no greenhouse; snow/ice condensation). See `docs/equations.md` / `docs/star-system-regions.md`.

#### `solvent-zone`
The AU band where a solvent is liquid on a planet surface (M1 surface model). Pick a
**named** `--solvent` from the built-in table (water, ammonia, methane, ethane,
water_ammonia, so2, co2, sulfuric_acid, sulfur, hydrogen, nitrogen, hf, formamide) **or**
supply a custom `--t-low`/`--t-high` liquid range (mutually exclusive; supplying both or
neither → exit 2). `--albedo` defaults to **0.3**.
```bash
query.py solvent-zone --luminosity 1.0 --solvent water
query.py solvent-zone --luminosity 1.0 --t-low 273.15 --t-high 373.15 --albedo 0.0
```
Core function: `equations.compute_solvent_zone(luminosity_solar, solvent=None, t_low_k=None, t_high_k=None, albedo=0.3)`. The band's inner edge = the solvent's boiling point (closer in), outer edge = its freezing point. Output: `{solvent, name, t_low_k, t_high_k, albedo, t_ref_k, luminosity_solar, inner_au, outer_au, inner_lm, outer_lm, s_eff_inner, s_eff_outer, t_eq_inner, t_eq_outer, pressure_conditional, assumed_pressure_atm, citation}` (`t_eq_*` round-trip the edge temps; `co2` is `pressure_conditional` with `assumed_pressure_atm = 5.2`).

#### `ice-lines`
The single canonical water snow line (170 K) plus the CO₂/NH₃/N₂/CO condensation fronts (M2 equilibrium model). `--albedo` defaults to **0.0** (bare ice grains).
```bash
query.py ice-lines --luminosity 1.0
query.py ice-lines --luminosity 0.5 --albedo 0.1
```
Core function: `equations.compute_ice_lines(luminosity_solar, albedo=0.0)`. Output: `{luminosity_solar, albedo, t_ref_k, lines}` where each line is `{species, t_cond_k, au, lm, kind ("snow_line"|"front"), disk_line, note}`. `AU = sqrt(L) × (T_ref / T_cond)²`; the water snow line lands at ~2.68 AU at L=1. The deep-cold N₂/CO fronts carry `disk_line=true` (disk-midplane-set; their ~160–194 AU placement is illustrative).

> **Region-output change (Phase P, consumer-facing).** The existing `star-regions` /
> `sol-regions` / `star-regions-manual` subcommands serialize the whole regions dict
> verbatim, so the Phase P **P1 value corrections** and **P2/P3 additive keys** now flow
> through their JSON automatically (no dispatcher change):
> - **Changed values:** `snowLine` (5.0 → **2.68 AU** at L=1, divisor 0.04 → 0.139),
>   `phInner`/`phOuter` (the hydrogen band → **~200–440 AU**, divisors 0.0000247 / 0.0000053),
>   and `planetaryTemperature`/`C`/`F` — the last only at **non-0.3** albedo (the
>   `(1−A)^0.25` fix; A=0.3 output is unchanged). `lh2Line` value is unchanged (relabel-only).
> - **New keys:** the P2 solvent bands `co2Inner`/`co2Outer`, `sInner`/`sOuter`,
>   `waInner`/`waOuter`, `saInner`/`saOuter` (M1) and the P3 ice fronts `iceLineNH3`,
>   `iceLineCO2`, `iceLineN2`, `iceLineCO` (M2).

### System dossier (Phase Q — no network for Sol)

#### `dossier`
Render a complete, self-contained **system dossier** by composing the existing readers
(`simbad-lookup` → regions + Kopparapu HZ + the NASA/HWC planet catalogs + Hypatia
abundances + the M5 GCNS cross-reference) into one document. This is the one call that
returns a whole system writeup instead of stitching 5+ subcommand outputs together. Pure
composition — **no new astronomy**.
```bash
query.py dossier --star "Tau Ceti"
query.py dossier --star "Tau Ceti" --fmt json
query.py dossier --star "Tau Ceti" --fmt html --sections identity regions planets
query.py dossier --star Sol                       # fully offline (Solar System)
query.py dossier --star Sol --sections planets moons
```
Core function: `report.build_system_dossier(star, sections=None, fmt="markdown")`.

- **`--fmt`** (default `markdown`): `markdown` / `html` emit a rendered **`document`** string
  (HTML is self-contained — inline `<style>`, no external assets, **text + tables only**: the
  HZ-ring / abundance figures are a GUI-only enrichment, never in the `query.py` output).
  `json` emits a structured **`data`** dict (the per-section data dicts) and **no** `document`.
- **`--sections`** (default: all available): any subset of `identity regions habitable_zone
  planets hypatia gcns moons`. `moons` is a **Sol-only opt-in** (large; never in the default
  set).
- **Sections.** `identity`, `regions` (stellar properties + system regions + the full Phase P
  alternate-solvent bands & ice/condensation lines), `habitable_zone` (Kopparapu, 3 luminosity
  columns), `planets` (**both** NASA pscomppars [priority 1] and HWC [priority 2] sub-tables
  when both resolve), `hypatia` (all measured species, grouped by nucleosynthetic family), and
  `gcns` (Bayesian distance + σ).
- **`Sol`/`Sun`** is the **offline reference-origin path**: identity from solar constants,
  regions/HZ from `compute_sol_regions`, `planets` from the real Solar System tables (Planets /
  Dwarf Planets / Major Asteroids; `moons` opt-in), Hypatia from the solar [X/H]≡0 zero-point,
  and **GCNS is not applicable** (a `notes[]` entry, not a warning). No SIMBAD/network call.
- **Output envelope:** `{star, fmt, sections, warnings, notes}` plus `document` (md/html) or
  `data` (json). `sections` lists the sections actually rendered.

> **Validation (self-validating — Phase H contract):** a **SIMBAD-lookup failure** for a real
> star, an unknown `--sections` value, or (via the core) a bad call → `{"error": str}` on
> stdout, **exit 1**. A bad `--fmt` (not markdown/html/json) is rejected by argparse → **exit
> 2** (stderr). A real star that is simply **missing a source** (no planets / no Hypatia / a
> white-dwarf regions failure) is **not** an error: that section is dropped to a **`warnings[]`**
> entry and the dossier still renders the rest (exit 0). Intentional omissions (GCNS-N/A on
> Sol) are **`notes[]`**, separate from warnings.

### Procedural system generation (Phase R1 + R2 — no network for synthetic mode)

#### `generate-system`
Deterministically generate a plausible planetary system — the inverse of the analysis
tools. Two modes: **synthetic-from-seed** (offline) and **real-anchor** (extends a real
star/system, networked). With one or more **`--constraint`** flags it becomes a
**constraint/feasibility analyzer** (Phase R2) — see "Feasibility mode" below. **Headline
contract: same `--seed` (+ same `--anchor-star` + same constraints) → byte-identical
output.** Pure composition over verified `core/` functions — the only new astronomy is a
planet classifier + a Phase-P equilibrium-temperature wrapper (R1) plus packing / resonance
/ co-orbital diagnostics + an opt-in pure-numpy N-body screen (R2).
```bash
query.py generate-system --seed 88 --spectral-class K2V --planets 5 --require-habitable   # synthetic, offline
query.py generate-system --seed 4173                                                       # synthetic, sampled class/count
query.py generate-system --seed 4173 --anchor-star "Tau Ceti"                              # real-anchor (+ network)
```
Core function: `generate.generate_system(seed, anchor_star=None, spectral_class=None, n_planets=None, require_habitable=False, constraints=None, companion=None, research_policy="permissive", nbody=False)`.

- **`--seed`** (required, int): the RNG seed — the system's identity.
- **`--anchor-star`** (optional): a real star name → **real-anchor mode** (pulls real
  specs via SIMBAD + `compute_star_system_regions_from_simbad`, the real known planets via
  NASA pscomppars / HWC flagged `source:"observed"`, then extends with synthetic infill
  flagged `source:"synthetic"`). Omit → **synthetic mode** (fully offline).
- **`--spectral-class`** (synthetic only): e.g. `K2V`; sampled from `DefaultPriors` weights
  if omitted. Ignored in real-anchor mode (the anchor's real class is used). `O`-class is
  rejected.
- **`--planets`** (optional, 0–15): the synthetic planet count (or the synthetic-infill
  count when anchored); sampled from the planet-count distribution if omitted.
- **`--require-habitable`** (store-true): retry (bounded) until a conservative-HZ rocky
  world is placed, else a curated error.
- **`--research-policy {permissive,strict}`** (Phase R3; default `permissive`): which priors
  provider the synthetic sampling **and** the Layer-3 origin narrative draw from. `permissive`
  → `DefaultPriors` (literature-informed defaults; `grounding=default-extrapolation`) — the
  default, **byte-identical** to R1/R2. `strict` → `ResearchPriors`, a versioned
  formation-priors dataset ingested via the **Import Research Priors** utility (GUI) /
  `core.research_priors.compute_research_priors_ingest`; emitted fields are re-tagged
  `grounding=research-calibrated` and the `notes` name the `dataset_version`. **`strict` with
  no dataset ingested → a curated `{"error"}` (exit 1)** — no silent fallback, no fabricated
  tag. The cache lives in the gitignored `data/research_priors/` (override with the
  `SPACE_RESEARCH_PRIORS_DIR` env var, mirroring `SPACE_APP_DB`). The data-contract schema +
  the sample/identity fixtures are documented in `docs/research-priors-contract.md`. A bad
  `--research-policy` value → argparse exit 2.
- **Output:** `{seed, mode ("synthetic"|"real_anchor"), anchor_star, star, planets[],
  warnings[], notes[]}`. `star` carries `name, spectral_class, teff, mass_solar,
  radius_solar, luminosity, hz_inner_au/hz_outer_au` (conservative) + `hz_opt_inner_au/
  hz_opt_outer_au` (optimistic) + `snow_line_au, source, grounding, multiplicity`. Each
  planet carries `name, a_au, mass_earth, radius_earth, ecc, type
  (rocky|super_earth|ice|gas|super_jovian|brown_dwarf), t_eq_k, in_hz, hz_class
  (conservative|optimistic|null), source, atmosphere, moons[]`. Every synthetic field is
  grounded `default-extrapolation` (the `DefaultPriors` provider) under the default
  `permissive` policy, or `research-calibrated` under `--research-policy strict` with an
  ingested dataset (Phase R3 — above). Multi-star anchors are **detected, warned, and safe-capped** (no
  synthetic body beyond a conservative cap; observed bodies are never capped); a quantitative
  S/P-type verdict needs a `--companion` hint (Phase R2 — below).

> **Validation (self-validating — Phase H contract, *not* the Phase-N raw-exception path):**
> bad input → a curated `{"error": str}` on stdout, **exit 1** — a bad `--spectral-class`, an
> `--planets` outside 0–15, `--require-habitable` exhausted after bounded retries, an
> unresolvable `--anchor-star`, a non-OBAFGKM (e.g. white-dwarf) anchor primary, a **malformed
> `--constraint` / `--companion` DSL**, or an out-of-range `--companion` eccentricity. Argparse
> rejects a missing or non-integer `--seed` / `--planets` → **exit 2** (stderr).

##### Feasibility mode (Phase R2 — `--constraint` / `--companion` / `--nbody`)

Describe the system you *want* as structured constraints and get a **four-layer verdict per
constraint** — stable? · why? · how could it arise? · nearest feasible alternative? — plus
the satisfied system. **Zero `--constraint` flags → the R1 generation path, byte-identical**
(all three flags are additive).
```bash
query.py generate-system --seed 4173 --anchor-star "47 Ursae Majoris" \
  --constraint 'planet_at_location:terrestrial,1.0,between:b:c' \
  --constraint 'trojan:terrestrial,giant_in_hz,L4' --nbody
query.py generate-system --seed 88 --spectral-class K2V --planets 6 \
  --constraint 'resonance:c,d,2:1' --companion '0.5,20,0.1'
```

- **`--constraint`** (repeatable) — a compact DSL `type:field,field[,…]` (comma-separated;
  location / ratio fields may themselves contain `:`). Vocabulary v1:
  - `planet_at_location:<type>,<mass_earth>,<location>` — `<location>` ∈ `in_hz` | `at:AU` |
    `between:A:B` | `interior_to:REF` | `exterior_to:REF` | `in_zone:ZONE` | `in_hz:opt`.
  - `trojan:<companion_type>,<host>,[L4|L5]` · `moon:<host>[,<mass_earth>][,terraformable]` ·
    `resonance:<bodyA>,<bodyB>,<p:q>`.
  - stretch: `habitable_world[:cons|opt[,min_count]]` · `alt_solvent_world:<solvent>[,<mass>]`
    · `architecture:<giant_beyond_snow_line|no_hot_jupiter>`.
  - Refs are a planet letter (`b` = innermost by SMA), an observed planet name, or a symbolic
    anchor (`giant_in_hz`, `super_jovian_in_hz`, `outermost`/`innermost`). An **unresolvable
    ref or an unknown constraint type is *not* an error** — that constraint is
    `verdict:"not_evaluated"` and the rest still evaluate. A **malformed** DSL → curated
    `{"error"}` exit 1.
- **`--companion 'mass_solar,sma_au[,ecc]'`** — a multi-star hint; a placed body must pass the
  Holman & Wiegert S-type (inside the critical SMA) / P-type (circumbinary, outside it) test.
  Binary instability is decisive (overrides a stable packing verdict → infeasible).
- **`--nbody`** (store-true) — run a **bounded, deterministic, pure-numpy** N-body screen on a
  **marginal** packing verdict (the Δ ∈ [2√3, 10) gray band) to resolve it to feasible /
  infeasible. Opt-in; a short-integration screen, **not** a Gyr stability proof.

- **Feasibility output** (only with `--constraint`): the R1 envelope **plus** `feasible`
  (bool — all *evaluated* constraints feasible; marginal/infeasible make it false;
  `not_evaluated` is neutral) and `constraints[]`, one entry per constraint:
  `{id, type, verdict ("feasible"|"marginal"|"infeasible"|"not_evaluated"),
  layer1 {stable, reason, metrics}, layer2 {mechanism, checked, note},
  layer3 {hypotheses:[{pathway, plausibility, grounding}], grounding}, layer4
  {alternatives:[{change, result, spec_patch}]}}`. Layer-3 hypotheses are **always tagged
  `grounding="default-extrapolation"`** (R3 swaps in research-calibrated priors with no engine
  change); each Layer-4 `spec_patch` is the exact spec mutation that flips the constraint.

### Integration expansion (Phase N)

Five subcommands that each wrap an **existing `core/` function verbatim** — no new output shapes; each returns
exactly what its core function returns today, pretty-printed. Four are pure-compute (no network); `travel-time-solar`
is the **only network-bound** entry (live JPL Horizons).

> **⚠️ Validation contract — read this before relying on exit codes.** Unlike the Phase-H worldbuilding calculators
> (which **self-validate** and return a curated `{"error": str}` for out-of-range input), the four pure-compute Phase-N
> subcommands wrap the project's **older, non-self-validating** equation/calculator functions, and Phase N adds **no
> validation** (it is a thin verbatim wrapper). The exit-code behavior is therefore:
>
> - **Malformed / missing / non-numeric arg** → argparse rejection, **exit 2**, message on **stderr** (not JSON) — all five.
> - **Out-of-range numeric** for `habitable-zone-sma`, `brachistochrone-au`, `brachistochrone-lm` → the wrapped function
>   **raises**, and `query.py`'s top-level handler turns it into `{"error": str(e)}` on stdout, **exit 1** — but the
>   message is a **raw Python exception string** (e.g. `"math domain error"` for a negative luminosity/distance,
>   `"float division by zero"` for `--sma 0` or `--accel-g 0`), **not** a curated sentence. Do not pattern-match on the
>   exact text; key on the presence of `"error"` + exit 1.
> - **`star-luminosity` has no out-of-range error path at all**: `L = R²·(T/5778)⁴` returns a finite number for any
>   float (a negative radius yields a positive luminosity because it is squared), so the only non-zero exit it produces
>   is argparse's **exit 2**.
> - **`travel-time-solar`** is the exception: it **does** return curated `{"error": str}` dicts (ambiguous Horizons
>   name — with a disambiguation hint — same-object, and network failures), **exit 1**.
>
> This is intentional (the raw-exception path is the pre-existing behavior of these legacy functions); key on
> `"error"` + exit code, never on the message text.

#### `habitable-zone-sma`
Kopparapu HZ boundaries **plus** the object's S_eff at its orbit and a plain-language HZ-membership verdict (the opt-40 calculation). Complements `habitable-zone`, which lacks the per-object Seff/verdict.
```bash
query.py habitable-zone-sma --teff 4900 --luminosity 0.15 --sma 0.45
```
Core function: `equations.compute_habitable_zone_sma(teff, luminosity, sma)`. No network. Output: `{zones, planet_seff, verdict}` — `zones` is the same 6-element list as `habitable-zone` (each `{zone_name, key, au, lm, seff}`); `planet_seff = (1/sma)² · luminosity`; `verdict` is a human-readable HZ-membership string.

#### `star-luminosity`
Stellar luminosity from radius and temperature: `L = R² × (T/5778)⁴` (the opt-41 calculation).
```bash
query.py star-luminosity --radius 0.82 --teff 5344
```
Core function: `equations.compute_star_luminosity(radius, temp)`. No network. Arg is `--teff` (consistency with `habitable-zone` / `habitable-zone-sma`), mapped to the function's `temp` parameter. Output: `{radius, temp, luminosity}`.

#### `stellar-evolution`
Evolutionary-stage durations and timeline for a star of a given mass (Phase L3). **Self-validating** (unlike the Phase-N legacy wrappers): a mass outside `0.1–20 M☉` returns a curated `{"error": str}` (exit 1); argparse rejects missing/non-numeric args (exit 2).
```bash
query.py stellar-evolution --mass-solar 1.0
query.py stellar-evolution --mass-solar 1.0 --current-age-gyr 4.6
```
Core function: `equations.compute_stellar_evolution(mass_solar, current_age_gyr=None)`. No network. `--current-age-gyr` is optional (marks the stage containing that age, or `"Beyond AGB"` past all stages). Output: `{mass_solar, stages:[{name, start_gyr, end_gyr, duration_gyr, color}], total_gyr, ms_end_gyr, current_age_gyr, current_stage, low_mass, high_mass}`. `T_ms = 10¹⁰ × (1/M)^2.5 yr`; stage fractions Pre-MS 0.01 · MS 1.0 · Subgiant 0.15 · RGB 0.10 · HB 0.10 · AGB 0.02. Special cases are **values, not errors**: `mass < 0.8` → `low_mass=true`, only Pre-MS + MS stages emitted (post-MS not reachable in a Hubble time); `mass > 8` → `high_mass=true`, the AGB stage becomes `"Supergiant → Supernova"`.

#### `brachistochrone-au` and `brachistochrone-lm`
All three brachistochrone acceleration profiles for a given distance (the opt-29 / opt-30 calculations).
```bash
query.py brachistochrone-au --accel-g 1.0 --au 5.2
query.py brachistochrone-lm --accel-g 0.5 --lm 43.2
```
Core functions: `calculators.compute_travel_time_system_au(accel_g, distance_au)` / `compute_travel_time_system_lm(accel_g, distance_lm)`. No network. Output: `{accel_g, distance_au, distance_lm, profiles}` (`distance_lm` ↔ `distance_au` are inter-derived). `profiles` is a list of 3 dicts, each `{label, hours, travel_time_str, max_vel}` (`max_vel` ∈ `"N/A"`/`"Y"`/`"N"`): ① continuous-to-halfway, ② accel¼/coast½/decel¼, ③ accel-to-3%c/coast/decel.

#### `distance-at-acceleration`
*(Added later to close an exposure gap — not one of the original Phase-N five above, but it shares their non-self-validating contract and sits with its brachistochrone siblings.)* The **inverse** of the brachistochrone subcommands — given an acceleration **and a travel time**, the distance covered by three profiles (the opt-24 calculation).
```bash
query.py distance-at-acceleration --accel-g 1.0 --hours 24
```
Core function: `calculators.compute_distance_at_acceleration(accel_g, hours)`. No network. Output: `{accel_g, hours, travel_time_str, profiles}` — `profiles` is a list of 3 dicts, each `{label, distance_au, distance_lm, max_vel}` (`max_vel` is `"N/A"` for profiles ① continuous-accel-for-the-whole-time and ② accel¼/coast½/decel¼; `"Y"`/`"N"` for profile ③ accel-to-3%c/coast, indicating whether the 3% c cap was reached in the window).
> **Validation:** non-self-validating (like the Phase-N pure-compute wrappers). An out-of-range numeric surfaces as a **raw-exception** `{"error": str(e)}` (exit 1) — e.g. `--accel-g 0` → `"division by zero"`; argparse rejects missing/non-numeric args (exit 2).

#### Velocity & constant-speed travel converters (opts 25–28, 31, 32)
Six thin wrappers over the simple constant-velocity calculators (the CLI menu opts 25–28 / 31 / 32), added to close an exposure gap. No network. **Non-self-validating** (Phase-N contract): the conversion / distance wrappers have **no error path** (any float is finite); the two travel-time wrappers raise `{"error": "float division by zero"}` (exit 1) on a zero velocity. Argparse rejects missing/non-numeric args (exit 2). Velocity ↔ c uses the Julian-year constant `8765.8128` (hours/yr).
```bash
query.py ly-hr-to-times-c --ly-hr 0.01                       # opt 31
query.py times-c-to-ly-hr --times-c 100                      # opt 32
query.py distance-traveled-ly-hr --ly-hr 0.01 --hours 100    # opt 25
query.py distance-traveled-times-c --times-c 100 --hours 50  # opt 26
query.py travel-time-ly-hr --distance-ly 4.37 --ly-hr 0.01   # opt 27
query.py travel-time-times-c --distance-ly 4.37 --times-c 100 # opt 28
```
Core functions: `calculators.compute_ly_hr_to_times_c(ly_hr)` → `{ly_hr, times_c}`; `compute_speed_of_light_to_ly_hr(times_c)` → `{times_c, ly_hr}`; `compute_distance_traveled_ly_hr(ly_hr, hours)` → `{ly_hr, hours, distance_ly}`; `compute_distance_traveled_times_c(times_c, hours)` → `{times_c, ly_hr, hours, distance_ly}`; `compute_travel_time_ly_hr(distance_ly, ly_hr)` → `{distance_ly, ly_hr, times_c, total_hours, travel_time_str}`; `compute_travel_time_times_c(distance_ly, times_c)` → `{distance_ly, times_c, ly_hr, total_hours, travel_time_str}` (`travel_time_str` is a human-readable breakdown, e.g. `"18 Days, 5 Hours"`).

#### `travel-time-solar`
Brachistochrone travel time between two solar-system bodies at a departure epoch (the opt-22 calculation). **Live JPL Horizons network call** — the only network-bound entry in this phase.
```bash
query.py travel-time-solar --origin Earth --destination Mars --accel-g 1.0
query.py travel-time-solar --origin Earth --destination "Jupiter" --accel-g 0.3 --v-cap-pct 5 --date 2027-03-15
```
Core function: `calculators.compute_travel_time_solar_objects(origin, destination, accel_g, v_cap_pct=3.0, departure_date=None)`. `--v-cap-pct` defaults to `3.0`; `--date` is ISO `YYYY-MM-DD`, defaulting to today (mapped to `departure_date`). The GUI-only `progress_callback` is never passed. Output: `{origin, destination, accel_g, distance_au, distance_lm, v_cap_pct, departure_date, profiles, origin_xyz, dest_xyz, planet_positions, origin_id, dest_id}` — `profiles` carries the same `{label, hours, travel_time_str, max_vel}` shape as the brachistochrone subcommands; JSON consumers may ignore `origin_xyz`/`dest_xyz`/`planet_positions`/`origin_id`/`dest_id`. Ambiguous Horizons names return the disambiguation error already produced by the core function.

### Route Planning additions (Phase I-OPTS)

The three Phase I-OPTS subcommands below (`optimal-tour`, `jump-route`, `jump-network`) wrap the **self-validating**
Route Planning functions (so out-of-range numerics return a curated `{"error": str}`, exit 1, unlike the Phase-N legacy
wrappers; argparse rejects missing/malformed args with exit 2 and a stderr message). Each resolves every star
**DB-first** (`star_systems.star_name`) then **SIMBAD** for names not in the table; `"Sol"`/`"Sun"` → the origin with no
lookup. Candidate/intermediate stars come from the local `star_systems` table (run **option 50** to populate it). The
fourth I-OPTS planner, Farthest-First Coverage (`farthest-first`), is documented with the original I1/I2/I3 planners in
the next section.

#### `optimal-tour`
Shortest-total-distance visit order for a set of stars (NN seed + 2-opt; the first star is the fixed start). Supply
exactly one of `--ly-hr` / `--times-c`; `--closed` adds a return-to-start leg.
```bash
query.py optimal-tour --stars Sol "Alpha Centauri" Sirius Procyon --ly-hr 0.01
query.py optimal-tour --stars Sol Sirius Procyon --times-c 100 --closed
```
Core function: `calculators.compute_optimal_tour(star_names, velocity_input, use_times_c, closed=False)`. Output:
`{legs[], total_ly, total_hours, total_time, naive_total_ly, optimized_total_ly, saved_ly, saved_pct, closed, stars[]}` —
each leg is `{leg, origin, dest, distance_ly, ly_hr, times_c, hours, cumulative_hours, travel_time, cumulative_time}`
(includes the wrap leg when `--closed`). `< 2` distinct stars or a non-positive velocity → `{"error"}` exit 1.

#### `jump-route`
Route origin→destination through intermediate stars, each jump ≤ `--max-jump` ly. `--optimize distance` (default,
Dijkstra) or `jumps` (BFS).
```bash
query.py jump-route --origin Sol --destination Procyon --max-jump 9
query.py jump-route --origin Sol --destination "Epsilon Indi" --max-jump 7 --optimize jumps
```
Core function: `calculators.compute_jump_route(origin, destination, max_jump_ly, optimize="distance")`. Output:
`{origin_info, dest_info, reachable, optimize, jumps, total_ly, direct_ly, route:[{jump, from, to, jump_ly,
cumulative_ly}], max_jump_ly, stars[]}`. **An unreachable destination is a normal result** (`reachable=false`, empty
`route`, **exit 0**) — not an error. Same origin/destination, `max_jump ≤ 0`, or an unresolvable endpoint → `{"error"}`
exit 1; `--optimize` other than `distance`/`jumps` is an argparse exit 2.

#### `jump-network`
BFS reachability tiers from a start star at jump range `--max-jump`; optional `--max-jumps` cap.
```bash
query.py jump-network --start Sol --max-jump 6
query.py jump-network --start "Alpha Centauri" --max-jump 5 --max-jumps 3
```
Core function: `calculators.compute_jump_network(start, max_jump_ly, max_jumps=None)`. Output: `{start_name,
max_jump_ly, max_jumps, max_tier, reachable_count, total_in_pool, unreachable_count, tiers:[{jumps, stars:[{star_name,
desig, sp_type, dist_from_start_ly, ly_from_sol}]}], stars[]}`. `reachable_count` includes the start; `unreachable_count`
is over the original `star_systems` rows. Each star in `stars[]` carries a per-tier `color` and `tier`. `max_jump ≤ 0`
or `max_jumps < 1` → `{"error"}` exit 1; empty `star_systems` → the opt-50 message, exit 1.

### Route Planning — original four (Phase I planners, now also via `query.py`)

The original Phase I planners (`compute_multi_stop_journey`, `compute_nearest_neighbor_chain`,
`compute_trade_route_mst`) plus the Phase I-OPTS Farthest-First Coverage (`compute_farthest_first_chain`, previously
GUI-only) are exposed here as subcommands — the same self-validating contract (curated `{"error"}` exit 1; argparse
exit 2 for missing/malformed args). Name resolution is DB-first → SIMBAD, as above.

#### `multi-stop`
Cumulative travel time along an **ordered** list of stops (you supply the order). One of `--ly-hr` / `--times-c`.
```bash
query.py multi-stop --stars Sol "Alpha Centauri" Sirius Procyon --times-c 100
```
Core function: `calculators.compute_multi_stop_journey(star_names, velocity_input, use_times_c)`. Output:
`{legs:[{leg, origin, dest, distance_ly, ly_hr, times_c, hours, cumulative_hours, travel_time, cumulative_time}],
total_ly, total_hours, total_time, stars[]}`. `< 2` stops or non-positive velocity → `{"error"}` exit 1; the first
unresolvable stop → `{"error": "Stop N ('name'): …"}`.

#### `nearest-neighbor`
Greedy nearest-unvisited chain from a start star over the `star_systems` pool.
```bash
query.py nearest-neighbor --start Sol --hops 6 --max-ly 6
```
Core function: `calculators.compute_nearest_neighbor_chain(start_star, num_hops, max_ly)`. Output:
`{chain:[{hop, star_name, desig, sp_type, dist_from_prev_ly, cumulative_ly, ly_from_sol}], stars[], total_ly,
stopped_early, start_name}`. No unvisited star within `--max-ly` → `stopped_early=true` (a normal result, **exit 0**).
`hops < 1` or `max_ly ≤ 0` → `{"error"}` exit 1; non-integer `--hops` → argparse exit 2; empty `star_systems` → the
opt-50 message, exit 1.

#### `farthest-first`
De-clustering coverage chain — each step picks the star **farthest** from the visited set (optional `--max-reach`).
```bash
query.py farthest-first --start Sol --stops 5
query.py farthest-first --start Sol --stops 8 --max-reach 13
```
Core function: `calculators.compute_farthest_first_chain(start, num_stops, max_reach_ly=None)`. Output:
`{chain:[{step, star_name, desig, sp_type, sep_to_visited_ly, dist_from_start_ly, ly_from_sol}], tree_edges[], stars[],
widest_ly, stopped_early, start_name}`. Nothing within reach → `stopped_early=true` (exit 0). `stops < 1` or
`max_reach ≤ 0` → `{"error"}` exit 1; empty `star_systems` → the opt-50 message, exit 1.

#### `trade-route`
Minimum spanning tree connecting a set of systems (Kruskal).
```bash
query.py trade-route --stars Sol Sirius Procyon "61 Cygni" "Epsilon Eridani"
```
Core function: `calculators.compute_trade_route_mst(star_names)`. Output: `{nodes:[{name,x,y,z,sp_type,desig}],
edges:[{from,to,distance_ly}] (N−1, ascending), total_ly, stars[]}`. After case-insensitive dedup, `< 2` systems →
`{"error"}` exit 1; the first unresolvable system → `{"error": "'name': …"}`.

### Exoplanet archives (network)

#### `exoplanets`
NASA Exoplanet Archive — all tables (pscomppars + HWO ExEP + Mission Exocat). Live network call.
```bash
query.py exoplanets --star "Epsilon Eridani"
```
Core functions: `databases.compute_simbad_lookup` → `databases.compute_exoplanet_archive`
Output: `{simbad, planets[], hwo, exocat}`. `planets[]` are pscomppars rows (sorted by `pl_orbsmax`); `hwo` is a list of `di_stars_exep` rows or `null` if no match; `exocat` is a single Mission Exocat row dict or `null`. Field names = raw archive/CSV columns (see `docs/star-databases.md`).

#### `planetary-systems`
NASA Exoplanet Archive — planetary systems composite (pscomppars only). Live network call.
```bash
query.py planetary-systems --star "Epsilon Eridani"
```
Core functions: `databases.compute_simbad_lookup` → `databases.compute_planetary_systems_composite`
Output: `{simbad, planets[]}` — `planets[]` are pscomppars rows (raw archive columns), sorted by `pl_orbsmax`.

#### `hwo-exep`
HWO ExEP precursor science star list. Live network call.
```bash
query.py hwo-exep --star "Tau Ceti"
```
Core functions: `databases.compute_simbad_lookup` → `databases.compute_hwo_exep`
Output: `{simbad, hwo[]}` — `hwo[]` are `di_stars_exep` rows (raw archive columns), sorted by `sy_dist`.

### Local DB archives (no network after first import)

#### `mission-exocat`
NASA Mission Exocat — queries the local `mission_exocat` DB table (2,396 rows). No network call after data is imported.
```bash
query.py mission-exocat --star "Epsilon Indi"
```
Core functions: `databases.compute_simbad_lookup` → `databases.compute_mission_exocat`
Output: `{simbad, exocat}` — `exocat` is a single Mission Exocat CSV row dict (raw columns).

#### `hwc`
Habitable Worlds Catalog — queries the local `hwc` DB table (5,599 rows). No network call after data is imported.
```bash
query.py hwc --star "Tau Ceti"
```
Core functions: `databases.compute_simbad_lookup` → `databases.compute_hwc`
Output: `{simbad, star_row, planet_rows[]}` — `star_row` holds star-level HWC fields; `planet_rows[]` are per-planet rows (raw HWC CSV columns), sorted by `P_SEMI_MAJOR_AXIS`.

### Hypatia Catalog (live network)

#### `hypatia-data`
Hypatia Catalog stellar properties and elemental abundances (Lodders 2009 normalisation). Live network call.
```bash
query.py hypatia-data --star "Tau Ceti"
```
Core functions: `databases.compute_simbad_lookup` → `databases.compute_hypatia_data`

Returns `{"star_name", "properties", "abundances"}` on success.
- `properties`: `{teff, logg, spectral_type, vmag, bmag, bv, distance_pc, disk, u_vel, v_vel, w_vel, pm_ra, pm_dec}` (any field may be `null`).
- `abundances`: list of `{element, name, z, category, mean, std, min, max, n}` for the full **104-species** Hypatia set (all elements the API exposes via `GET /element`, including singly-ionized species such as `Ba_II`); only species with a non-null mean are included. `element` preserves the API casing (`Fe`, `Ba_II`); `name` is the full element name (ionized → e.g. `Barium II`); `z` is the atomic number; `category` is the nucleosynthetic-family key (`light`, `cno`, `alpha`, `oddz`, `iron`, `s_light`, `s_heavy`, `ree`, `heavy`). `n` (# catalogs) is derived from the response's `catalogs_linear` length. The species set, names, atomic numbers, and categories are defined in `core/hypatia_elements.py`. Results are ordered by that table's display order (category light→heavy, then atomic number). The 104 species can't be requested in one call (the server caps the GET request line at ~4094 bytes), so `compute_hypatia_data` fetches them in chunks of 30 and concatenates the responses.

### GCNS — Gaia Catalogue of Nearby Stars (local DB, no network)

Reads the `gcns_stars` / `gcns_systems` / `gcns_system_members` / `gcns_system_pairs` DB tables, populated by CLI **option 58** (Import GCNS Data) — the GCNS backbone (331,312 sources to 100 pc) with **Bayesian distances + uncertainties**, plus a SIMBAD identity layer (spectral type / common name / Johnson V) attached by cross-match, plus the **resolved multiple-star systems** derived from `gcns.resolvedss`. No network call after the import. If the relevant table is empty, the `gcns_stars`-backed subcommands return `{"error": "gcns_stars table is empty — run option 58 (Import GCNS Data) first."}` and `gcns-system` returns the analogous `gcns_systems table is empty …`, both with exit 1. See `docs/star-databases.md` for the ingest/build, the cross-match, the resolved-system derivation, and the documented completeness limits.

**Per-star fields** (snake_case; any numeric field may be `null`):

| Field | Type | Meaning |
|---|---|---|
| `gaia_source_id` | int \| null | Gaia EDR3/DR3 source id. `null` for `missing_10mas` rows. |
| `ra`, `dec` | float | ICRS position, degrees (J2016.0). |
| `parallax`, `parallax_error` | float | mas. |
| `dist_pc` | float | **Bayesian** median distance (pc). For `missing_10mas` rows this is `1000/parallax` (1/ϖ inversion). |
| `dist_lo_pc`, `dist_hi_pc` | float \| null | 16th / 84th percentile distance (pc). `null` for `missing_10mas` (no Bayesian PDF). |
| `light_years` | float | `dist_pc × 3.26156`. |
| `phot_g_mean_mag`, `phot_bp_mean_mag`, `phot_rp_mean_mag` | float \| null | **Gaia bands — NOT Johnson V.** `null` for `missing_10mas`. |
| `rv_kms` | float \| null | Adopted radial velocity (km/s). |
| `wd_prob` | float \| null | Probability the source is a white dwarf. |
| `astrom_reliable_prob` | float \| null | GCNS probability the astrometry is reliable. |
| `spectral_type` | str \| null | SIMBAD spectral type (cross-match). `null` when unmatched — never fabricated. |
| `star_name` | str \| null | SIMBAD common name (cross-match); for `missing_10mas` defaults to the GCNS `main_id`. |
| `app_magnitude` | float \| null | SIMBAD **Johnson V** (cross-match). Distinct from the Gaia bands. |
| `in_gcns` | bool | Always `true` (row is GCNS-sourced). |
| `in_simbad` | bool | `true` if cross-matched to a `star_systems` row. |
| `distance_method` | str | `"gcns_bayesian"` (main) \| `"gcns_missing_plx_inversion"` (missing_10mas). |
| `gcns_table` | str | `"main"` \| `"missing_10mas"`. |
| `system_id` | int \| null | `gcns_systems.system_id` if this source is a member of a Gaia-resolved system; `null` otherwise (single/unresolved, or a `missing_10mas` row with no source_id). Join key for `gcns-system`. |
| `n_components` | int \| null | Component count of that resolved system; `null` if not a member. |

**Populating it:** the table is built by CLI **option 58** (Import GCNS Data) — a one-time ~331k-row pull from GAVO. GCNS is Gaia EDR3-based and static, so the data only changes when re-imported; `snapshot_date`/`gcns_version` record which build a result came from. `in_simbad` coverage depends on the `star_systems` build carrying Gaia/2MASS keys (currently ~70%). See `docs/star-databases.md`.

#### `gcns-within-sol`
All GCNS sources within N light years of Sol, sorted ascending by `light_years`.
```bash
query.py gcns-within-sol --ly 15
query.py gcns-within-sol --ly 50 --wd-prob-min 0.5      # white-dwarf census (Phase T1a)
```
Core function: `databases.compute_gcns_within_sol(ly, wd_prob_min=None, wd_prob_max=None)`
Output: `{limit_ly, count, snapshot_date, gcns_version, stars[]}`. Each star carries the fields above plus heliocentric `x`/`y`/`z` (ly) for map parity with `stars-within-sol`.
- **Phase T1a — white-dwarf census filter (E1, additive).** Optional `--wd-prob-min` / `--wd-prob-max` restrict the census to sources whose GCNS white-dwarf probability (`wd_prob`) falls in the given range; rows with a NULL `wd_prob` are excluded once either bound is set. Both omitted → byte-identical to the unfiltered census. A `min > max` simply matches nothing (count 0), not an error — consistent with the other range filters. This is the closest census primitive to attach to (there is **no** GCNS `search-*` function). Empty `gcns_stars` → `{"error"}` exit 1; non-numeric `--ly`/`--wd-prob-*` → argparse exit 2.
Example (abridged):
```json
{
  "limit_ly": 6.0,
  "count": 4,
  "snapshot_date": "2026-06-05",
  "gcns_version": "GCNS / Smart et al. 2021 A&A 649 A6 (VizieR J/A+A/649/A6) via GAVO gcns.main + gcns.missing_10mas + gcns.resolvedss",
  "stars": [
    {
      "gaia_source_id": 5853498713190525696,
      "ra": 217.3923, "dec": -62.6761,
      "parallax": 768.0665, "parallax_error": 0.0499,
      "dist_pc": 1.3019, "dist_lo_pc": 1.2771, "dist_hi_pc": 1.3020,
      "light_years": 4.2464,
      "phot_g_mean_mag": 8.9847, "phot_bp_mean_mag": 11.3731, "phot_rp_mean_mag": 7.5685,
      "rv_kms": -22.4, "wd_prob": 0.2144, "astrom_reliable_prob": 1.0,
      "spectral_type": "M5.5Ve", "star_name": "NAME Proxima Centauri", "app_magnitude": 11.13,
      "in_gcns": true, "in_simbad": true,
      "distance_method": "gcns_bayesian", "gcns_table": "main",
      "system_id": null, "n_components": null,
      "x": -1.55, "y": -1.18, "z": -3.77
    }
    // … α Cen A/B appear here as gcns_table "missing_10mas" with
    //   distance_method "gcns_missing_plx_inversion" and dist_lo_pc/dist_hi_pc = null
  ]
}
```

#### `gcns-source`
Single GCNS row by Gaia EDR3/DR3 `source_id` (the cross-match join key). EDR3 and DR3 source_ids are identical. The id can be taken from `simbad-lookup`'s `designations["Gaia EDR3"]` (strip the `"Gaia DR3 "` prefix).
```bash
query.py gcns-source --id 5853498713190525696
```
Core function: `databases.compute_gcns_by_source_id(id)`
Output: `{snapshot_date, gcns_version, star}` — `star` is a single dict with the fields above (no `x`/`y`/`z`) — or `{"error": ...}` if the id is not present (exit 1).

#### `gcns-system`
The resolved multiple-star system containing a Gaia EDR3/DR3 `source_id`. Derived from `gcns.resolvedss` (pair-keyed; systems are connected components — see `docs/star-databases.md`). Pass the `source_id` of **any** component; the whole system is returned.
```bash
query.py gcns-system --id 1872046609345556480   # 61 Cygni A → the 61 Cyg system
```
Core function: `databases.compute_gcns_system(id)`
Output: `{snapshot_date, gcns_version, query_source_id, system}`, or `{"error": ...}` (exit 1) when the id is in **no** resolved system (single/unresolved object) or the `gcns_systems` table is empty.

`system` is a dict:
- `system_id` (int, synthetic & stable per build), `n_components` (int), `n_pairs` (int).
- `any_bin`, `any_bound`, `all_bound` — bool|null, aggregated over the system's pairs (`bin` = pair probably part of a >2-star system; `bound` = probably gravitationally bound).
- `max_proj_sep_au`, `min_proj_sep_au` — float|null, projected separation extremes (AU).
- `n_in_gcns_stars` (int) — members that link to a `gcns_stars` row.
- `members` — list, one per component, sorted by `gaia_source_id`: `{gaia_source_id, in_gcns_stars (bool), is_query (bool — true for the queried id), star_name, spectral_type, dist_pc, light_years}`. The last four are joined from `gcns_stars` and are `null` for a member not present there (retained, not dropped).
- `pairs` — list of the raw `gcns.resolvedss` edges in this system, sorted by `proj_sep_au`: `{source_id1, source_id2, separation_arcsec, mag_diff, proj_sep_au, bin (bool|null), bound (bool|null)}`.

Example (61 Cygni, abridged):
```json
{
  "snapshot_date": "2026-06-05",
  "query_source_id": 1872046609345556480,
  "system": {
    "system_id": 1234, "n_components": 2, "n_pairs": 1,
    "any_bin": true, "any_bound": true, "all_bound": true,
    "max_proj_sep_au": 110.47, "min_proj_sep_au": 110.47, "n_in_gcns_stars": 2,
    "members": [
      {"gaia_source_id": 1872046574983497216, "in_gcns_stars": true, "is_query": false,
       "star_name": null, "spectral_type": null, "dist_pc": 3.4966, "light_years": 11.4042},
      {"gaia_source_id": 1872046609345556480, "in_gcns_stars": true, "is_query": true,
       "star_name": null, "spectral_type": null, "dist_pc": 3.4966, "light_years": 11.4042}
    ],
    "pairs": [
      {"source_id1": 1872046609345556480, "source_id2": 1872046574983497216,
       "separation_arcsec": 31.59, "mag_diff": 0.68, "proj_sep_au": 110.47,
       "bin": true, "bound": true}
    ]
  }
}
```

### GCNS-backed calculators (distance / travel-time / within-star)

GCNS-sourced versions of `distance`, `travel-time`, and `stars-within-star`, using the GCNS census (Bayesian distances + uncertainties) from the `gcns_stars` table instead of the SIMBAD-derived `star_systems` table. The existing SIMBAD-based subcommands are unchanged. Each endpoint accepts a **name** (`--star…`, resolved through SIMBAD) or a **Gaia EDR3/DR3 source_id** (`--id…`, fully offline). Populated by CLI **option 58** (Import GCNS Data); see `docs/star-databases.md`.

**Endpoint resolution** (`_resolve_gcns_row` in `core/databases.py`):
- `--id…`: direct `gcns_stars` fetch by `gaia_source_id` (offline). `missing_10mas` rows have a NULL `gaia_source_id` and are **not** id-addressable.
- `--star…`: SIMBAD lookup → extract the Gaia id from its designations → fetch by id. If SIMBAD itself errors (network/no-match), that error is returned (no fallback). If the resolved id is absent from `gcns_stars`, it falls through to an exact `star_name` match (case-insensitive) — this is how `missing_10mas` rows (e.g. Alpha Cen A/B) resolve.
- A star **truly absent** from GCNS returns `{"error": "… is not in the GCNS catalog …"}` — it is **never** silently substituted with a SIMBAD distance. An **ambiguous** name (matching >1 `gcns_stars` row) returns an error naming the candidate source_ids.

**Uncertainty:** every endpoint info block carries `distance_method` (`gcns_bayesian` vs `gcns_missing_plx_inversion`) plus `dist_pc` and `dist_lo_pc`/`dist_hi_pc` (the latter two are `null` for `missing_10mas` endpoints — point value only, no error bar). **No** combined/propagated separation or travel-time interval is computed — that is left to the consumer.

#### `gcns-distance`
3D Euclidean distance in light years between two GCNS stars.
```bash
query.py gcns-distance --id1 5853498713190525696 --id2 5853498618164729728
query.py gcns-distance --star1 "Proxima Centauri" --id2 5853498618164729728
```
Core function: `databases.compute_gcns_distance(star1=, id1=, star2=, id2=)`
Output: `{star1_info, star2_info, distance_ly, distance_au, snapshot_date, gcns_version}`. Each `*_info` block is the full GCNS per-star dict (the same fields as `gcns-source`'s `star`: `gaia_source_id, ra, dec, parallax, dist_pc, dist_lo_pc, dist_hi_pc, light_years, distance_method, spectral_type, star_name, …`) **plus** `ra_hms`/`dec_dms`. `distance_au` is `null` unless the two stars are `< 0.5` ly apart. A self-distance (same endpoint twice) returns `distance_ly ≈ 0` (not an error).

#### `gcns-travel-time`
GCNS-backed FTL travel time between two stars. Supply exactly one of `--ly-hr` or `--times-c`.
```bash
query.py gcns-travel-time --id1 5853498713190525696 --id2 5853498618164729728 --times-c 100
```
Core function: `databases.compute_gcns_travel_time(star1=, id1=, star2=, id2=, ly_hr=, times_c=)`
Output: `{origin_info, dest_info, distance_ly, ly_hr, times_c, total_hours, travel_time_str, snapshot_date, gcns_version}`. `origin_info` = endpoint 1 (`--star1`/`--id1`), `dest_info` = endpoint 2; both are the same info-block shape as `gcns-distance`. A zero (or negative) velocity returns an error.

#### `gcns-stars-within-star`
All GCNS stars within N light years of a center star, sorted ascending by 3D `Distance`.
```bash
query.py gcns-stars-within-star --star "Alpha Centauri A" --ly 1
query.py gcns-stars-within-star --id 5853498713190525696 --ly 5
```
Core function: `databases.compute_gcns_stars_within_star(star=, source_id=, limit_ly=)`
Output: `{center, center_x, center_y, center_z, limit_ly, count, snapshot_date, gcns_version, stars[]}`. `center` is the resolved center row (with its own `x`/`y`/`z` added). Each star in `stars[]` mirrors `gcns-within-sol`'s row shape (the full GCNS fields + `system_id`/`n_components` + heliocentric `x`/`y`/`z`) **plus** a per-row `Distance` (ly from the center). The center itself is excluded **precisely** by `gaia_source_id` (with a `Distance < 1e-9` exact-self skip for a `missing_10mas` center that has no id), so Gaia-resolved **close companions remain** in the results — unlike the SIMBAD `stars-within-star`, which drops everything within `0.001` ly (~63 AU) of the center.

### Search & Filter (Phase G — local DB, except `search-exoplanets`)

The three interactive-search functions, exposed with **all filters optional** (omitting every filter returns the
first page up to the cap). Each returns `{count, capped, cap, stars[]}` (`capped=true` means the result hit the cap) or
`{"error": str}`. Spectral-class filtering uses the friendly **chips + refine** model: `--spectral-classes` takes one
or more of `O B A F G K M Other` (OR-ed leading-letter matches), and `--spectral-refine` is a case-insensitive
contains-match on the rest of the type (e.g. `V` for the luminosity class). See `docs/star-databases.md` (Phase G).

#### `search-star-systems`
Filter the local `star_systems` table (no network). Cap 500; sorted by light years.
```bash
query.py search-star-systems --spectral-classes M K --ly-max 20 --mag-max 10
```
Core function: `databases.search_star_systems(filters)`. Flags → filter keys: `--spectral-classes`/`--spectral-refine`,
`--ly-min`/`--ly-max`, `--mag-min`/`--mag-max`, `--designation-prefix`, and (Phase L4) `--fe-h-min`/`--fe-h-max` (an
inner JOIN onto `hypatia_cache` — matches nothing when that cache is empty; run **Import Hypatia Cache** first). Each
star: `{star_name, designations, spectral_type, parallax, parsecs, light_years, app_magnitude, ra, dec}`. Empty
`star_systems` → the opt-50 error.

#### `search-hwc`
Filter the local Habitable Worlds Catalog (no network). Cap 500; sorted by ESI descending.
```bash
query.py search-hwc --esi-min 0.8 --habitable --spectral-classes K G
```
Core function: `databases.search_hwc(filters)`. Flags: `--esi-min`; `--habitable` / `--habzone-con` / `--habzone-opt`
(store-true booleans); `--mass-min`/`--mass-max` (`P_MASS`), `--radius-min`/`--max` (`P_RADIUS`),
`--temp-min`/`--max` (`P_TEMP_EQUIL`); `--spectral-classes`/`--spectral-refine` (`S_TYPE`); `--ly-max`. Empty `hwc` →
the opt-52 error.

#### `search-exoplanets`
Filter the **live** NASA `pscomppars` archive via TAP. Cap 200; sorted by `pl_orbsmax`.
```bash
query.py search-exoplanets --radius-min 0.5 --radius-max 1.6 --dist-max-pc 15 --method "Transit"
```
Core function: `databases.search_exoplanets(filters)`. Flags → ADQL columns: `--mass-min`/`--max` (`pl_bmasse`),
`--radius-min`/`--max` (`pl_rade`), `--period-min`/`--max` (`pl_orbper`), `--teff-min`/`--max` (`st_teff`),
`--dist-max-pc` (`sy_dist`, **parsecs**), `--method` (`discoverymethod`, exact), `--spectral-classes`/`--spectral-refine`
(`st_spectype`). Network failures are classified to `{"error": str}`.

#### `search-hypatia`
Filter the **local Hypatia abundance cache** (Phase L4 — no network; populated by the GUI **Import Hypatia Cache**
utility / `databases.import_hypatia_cache`). Cap 500; sorted by Fe/H descending (NULL fe_h last).
```bash
query.py search-hypatia --fe-h-min 0.3 --ly-max 60 --element Mg --element-min 0.2
```
Core function: `databases.search_hypatia_cache(filters)`. Flags → filter keys: `--fe-h-min`/`--fe-h-max` (`[Fe/H]`),
`--teff-min`/`--teff-max`, `--ly-max` (`light_years`), `--disk` (exact Hypatia disk code, e.g. `0`=thin / `1`=thick),
`--element` (species symbol in API casing, e.g. `Mg`, `Ba_II`) + `--element-min`/`--element-max` (that species' [X/H],
via an `EXISTS` subquery). Each star: `{star_name, hip, hd, teff, logg, vmag, bv, distance_pc, disk, fe_h, light_years,
mg_h, si_h, o_h}` (`mg_h`/`si_h`/`o_h` are pivoted convenience [X/H] values; any may be `null`). Empty cache →
`{"error": "hypatia_cache table is empty — run the Import Hypatia Cache utility first."}`, exit 1.

> **Bulk-path caveat:** the cache carries the catalog-averaged **[X/H] mean** per element (the filter key) but not the
> spread (`std`/`min`/`max`/`n`) or UVW kinematics — those come from the live per-star `hypatia-data` subcommand. The
> Star Systems search also gained `--fe-h-min`/`--fe-h-max` (an inner JOIN onto this cache; matches nothing when the
> cache is empty).

### Census-filter presets (Phase T1c — local DB, no network)

Two convenience census presets for the sibling worldbuilding repo. Self-validating (curated `{"error"}` →
exit 1; argparse → exit 2). **The defining feature: each result carries its population/completeness caveat as a
JSON field** (`population` / `completeness_note`) — the external consumer reads JSON, not docs, at query time —
so a short list is never mistaken for a complete census.

#### `solar-analogs`
Solar twins/analogs from the **Hypatia cache** by a tolerance box around the solar values (Teff 5772 K, log g
4.44, [Fe/H] 0.0). Backed by `hypatia_cache` — the only table carrying teff/logg/[Fe/H] — so the population is
necessarily the ~14k abundance-measured stars (stated in the output).
```bash
query.py solar-analogs                                   # twin box (default)
query.py solar-analogs --mode analog --ly-max 50
query.py solar-analogs --teff-tol 30 --feh-tol 0.05 --gcns-distance
```
Core: `databases.compute_solar_analogs(mode="twin", teff_tol=None, logg_tol=None, feh_tol=None, ly_max=None, gcns_distance=False)`. `--mode twin` → tolerance `±100 K / ±0.1 / ±0.1`; `--mode analog` → `±500 K / ±0.4 / ±0.3`; any `--*-tol` overrides that axis; `--ly-max` filters `light_years`. Output: `{mode, criteria{teff_center, teff_tol, logg_center, logg_tol, feh_center, feh_tol, ly_max}, population{source:"hypatia_cache", total_in_cache, returned, gcns_distance_matched, note}, count, capped, cap, stars[]}` — `stars` carry the `hypatia_cache` columns + `mg_h/si_h/o_h` pivots. **`population.note`** states the Hypatia-cache limit (the locked caveat).
- **`--gcns-distance` (opt-in, best-effort):** attaches a GCNS Bayesian distance `dist_pc_gcns` per star via the cross-match `star_name → star_systems.designations → Gaia id → gcns_stars.dist_pc` (`null` where the chain breaks); `population.gcns_distance_matched` reports the hit count. Default off → no `dist_pc_gcns` key, `gcns_distance_matched: null`.
- **Validation:** empty `hypatia_cache` → `{"error"}` exit 1; any explicit `--*-tol ≤ 0` or `--ly-max ≤ 0` → curated `{"error"}` exit 1; bad `--mode` / non-numeric tol → argparse exit 2.

#### `substellar`
Substellar (**L/T/Y**) census from `gcns_stars` by SIMBAD-cross-matched **spectral-type prefix** — the census the
completeness caveat is about. `--teff-max` is **not** offered (`gcns_stars` has no teff).
```bash
query.py substellar
query.py substellar --ly-max 20 --include-late-m
query.py substellar --classes L T            # override the prefix set
```
Core: `databases.compute_substellar_census(ly_max=None, include_late_m=False, classes=None)`. Selects rows whose `spectral_type` begins with one of `classes` (default `L T Y`; `--include-late-m` adds `M7/M8/M9`); `spectral_type IS NOT NULL` (only cross-matched rows carry a type); `--ly-max` filters `light_years`; sorted by distance, capped at 500. Output: `{classes, ly_max, count, capped, cap, completeness_note, population{total_in_gcns, with_spectral_type, returned}, snapshot_date, gcns_version, stars[]}` — `stars` are the standard GCNS row shape. **`completeness_note`** is the mandatory lower-bound disclosure (GCNS substellar completeness falls off beyond ~10–25 pc; only cross-matched rows carry types).
- **Validation:** empty `gcns_stars` → `{"error"}` exit 1; `--ly-max ≤ 0` → curated `{"error"}` exit 1; non-numeric `--ly-max` → argparse exit 2.

### Dust / ISM (Phase T2 Part A — optional `dustmaps` extra; WSL/Linux venv)

Read-only 3D interstellar-**dust extinction** queries over the `dustmaps` package — the
**optional `dust` extra** (`pip install -r requirements-dust.txt`, on top of base
`requirements.txt`). `core/dust.py` is the only module that imports `dustmaps`/`healpy`, and it
does so lazily, so the stellar layer stays importable on a checkout **without** the extra. The
extra is **WSL/Linux-venv-only**: `dustmaps` hard-requires `healpy`, which has no native-Windows
pip wheel — a Windows pip checkout keeps the stellar layer and the dust subcommands return a
curated *"install the optional 'dust' extra"* error. § = a local read **of the fetched dust map
cache** (`data/dust/`, gitignored); see **CLI option 59 `dust-fetch`** below to populate it.

**Maps (`--map`, default `auto`):** `near-field` = **Leike, Glatzle & Enßlin 2020** (Cartesian box
±370/±370/±270 pc, 1-pc voxels; `dustmaps.leike2020`); `edenhofer` = **Edenhofer et al. 2024**
(HEALPix sphere ~69 pc–1.25 kpc; `dustmaps.edenhofer2023` — the dustmaps key/module is **2023**,
the A&A paper is 2024); `auto` = Leike ≤ ~69 pc, Edenhofer beyond. To avoid the inner-<69 pc
double-count, the engine queries each map's **differential density** (`integrated=False`) and
integrates per-segment itself — Edenhofer differential is NaN inside ~69 pc, so the two maps own
disjoint distance ranges (the seam ≈ 69 pc; bins within 5 pc of it carry `seam:true`).

**Units (declared):** output is **`A_V` in magnitudes at `R_V=3.1`** (`units:"A_V_mag_RV3.1"`, `rv:3.1`),
standardized from each map's native quantity by a pinned per-map scalar — **Edenhofer:** `A_V =
2.8·E` (ZGR23 unit `E`; Edenhofer et al. 2024 / the Zhang, Green & Rix 2023 extinction curve,
zenodo 6674521); **Leike:** density (e-foldings/kpc, Gaia-G optical depth) integrated → `τ_G`, then
`A_G = 1.0857·τ_G` and `A_V = 1.202·A_G` (the Gaia-G→V ratio at R_V=3.1; O'Neill et al. 2024 Local
Bubble). Each bin echoes its raw `native_value` + `native_quantity`
(`"leike2020_density_efoldings_per_kpc_gaiaG"` / `"edenhofer2023_ZGR23_E_per_pc"`) so the conversion
is auditable. Distances are **parsecs** (map-native) with a light-year echo (`dist_ly`).

**Uncertainty:** per-bin `a_v_lo`/`a_v_hi` from the map's `std`; cumulative `*_lo`/`*_hi` from a
**quadrature sum** of the per-bin σ (an independent-bin approximation — it understates correlated
uncertainty; the exact per-sample integration, Edenhofer's 19 GB samples, is a deferred enhancement).

**Coverage:** geometry leaving a map box is **not** an error — that bin gets `a_v:null` + an
`out_of_coverage` note (never clamped to an edge value). A covered-but-near-zero deep-cavity bin
returns its small `a_v` with a wide σ + a `low_dust_high_uncertainty` note. Top-level `notes` flags
`seam_crossed` / `out_of_coverage` / `all_out_of_coverage` / `low_dust_high_uncertainty`.

#### `dust-sightline`
Extinction profile along one direction — Galactic (`--l --b`), equatorial (`--ra --dec`), or the
direction of a star (`--star`/`--id`, which sets only the direction; the distance range still comes
from `--dist-*`) — from `--dist-start` (pc, default 0) to `--dist-end` (pc, required), in `--steps`
bins (default 50) or `--step-pc` spacing.
```bash
query.py dust-sightline --l 120 --b 5 --dist-end 200
query.py dust-sightline --ra 101.3 --dec -16.7 --dist-start 0 --dist-end 150 --steps 75 --map auto
query.py dust-sightline --star "Epsilon Eridani" --dist-end 60 --map near-field
```
Core: `dust.compute_dust_sightline(l, b, ra, dec, star, id, dist_start_pc=0.0, dist_end_pc, n_steps=50, step_pc=None, map_sel="auto")`. Output: `{map, frame, l, b, dist_start_pc, dist_end_pc, n_steps, bins:[{dist_pc, dist_ly, map, a_v, a_v_lo, a_v_hi, cumulative_a_v, cumulative_a_v_lo, cumulative_a_v_hi, native_value, native_quantity, seam, notes}], cumulative_a_v, cumulative_a_v_lo, cumulative_a_v_hi, units, rv, notes}`.

#### `dust-between`
Extinction along the straight line between two stars (reuses the route/GCNS resolvers; `Sol`/`Sun` →
origin). Per-bin `dist_pc` is the path distance from `star1`; map ownership uses each bin's
heliocentric distance.
```bash
query.py dust-between --star1 Sol --star2 "Epsilon Eridani"
query.py dust-between --id1 5853498713190525696 --id2 4472832130942575872 --step-pc 2 --map auto
```
Core: `dust.compute_dust_between(star1, id1, star2, id2, n_steps=50, step_pc=None, map_sel="auto")`. Output: the `dust-sightline` block **plus** `{star1_info, star2_info, separation_pc, separation_ly}` and `frame:"star-to-star"`.

#### CLI option 59 `dust-fetch` (NOT a `query.py` subcommand)
A one-time map download / cache-status utility — CLI **menu option 59** (`main.py::dust_fetch_data`),
in the opt-58 (GCNS) import-utility lineage. It also has a **GUI panel** —
**`FetchDustMapPanel`** (Utilities nav, mirroring `ImportGcnsPanel`: map selector + Check-Status/Fetch
buttons + a background `QThread` + progress bar), gated so a checkout without the `dustmaps` extra shows an
install hint instead of a broken entry. The dust **query** subcommands (`dust-sightline` / `dust-between` /
the routing `--weight dust`) remain `query.py`-only (no GUI) by design. The **Database Table Status** panel
(GUI **option 57**, `DbStatusPanel`) also lists the two cached map **files** (presence + size in MB) under the
DB tables — via the pure-pathlib `core.dust.get_dust_map_status()`, which needs no `dustmaps` import, so it
reports file presence even on a checkout without the extra. (The maps are **files**, not a SQLite table — this
is file-presence status, not a row count.)

**Zenodo throttle & manual download (read before fetching).** Both maps are hosted on **Zenodo** (CERN's
open-data repository), which **bandwidth-throttles** large anonymous file downloads — observed at ~0.5 MB/s,
so the in-app `compute_dust_fetch` of the 2.4 GB Leike + 3.2 GB Edenhofer files can take well over an hour.
This is download *bandwidth shaping* (and/or transient server load), distinct from Zenodo's separate API
request-rate limits; it is not an error, just slow. The dustmaps fetcher **cannot resume** a broken transfer
(it verifies an md5 and restarts from zero), so a faster, **resumable** path is to download the files
manually into the cache, then run `dust-fetch --check` (or the GUI panel's **Check Status**) — dustmaps
verifies the md5 and uses the cached file. The fetch is one-time; the cache is offline thereafter. The GUI
`FetchDustMapPanel` shows these commands (aimed at the real cache dir) in a **copyable "Manual download"
box** with a Copy button:

```bash
# Leike 2020 → data/dust/leike_2020/mean_std.h5   (md5 1ea998fdaef58f53da639356362223ba)
aria2c -c -x4 -d data/dust/leike_2020 \
  'https://zenodo.org/record/3993082/files/mean_std.h5'
# Edenhofer 2024 → data/dust/edenhofer_2023/mean_and_std_healpix.fits  (md5 10c823a5fcf81b47b6e15530bcdf54dc)
aria2c -c -x4 -d data/dust/edenhofer_2023 \
  'https://zenodo.org/record/8187943/files/mean_and_std_healpix.fits'
# No aria2c? Resumable wget:  wget -c -P <dir> '<url>'
```

`aria2c -c` / `wget -c` resume on interruption (the dustmaps fetcher can't), and aria2c's multiple
connections (`-x4`) often beat the per-connection throttle. The cache dir is `data/dust/` under the repo
root by default (`core.dust._DUST_CACHE_DIR`, on the native WSL filesystem), gitignored.
It prompts for the map (`auto`/`near-field`/`edenhofer`) and Fetch-vs-Check, then calls
`dust.compute_dust_fetch(map_sel, check_only, progress_callback)`. The cache lands in `data/dust/`
(gitignored, on the native WSL filesystem), fetch-once/offline-after. **Sizes are large:** Leike
`mean_std.h5` ≈ **2.4 GB**, Edenhofer `mean_and_std_healpix.fits` ≈ **3.2 GB** (`auto` ≈ 5.6 GB);
download from Zenodo can be slow. Returns `{map, cache_dir, fetched:[{map, status, path, size_mb}]}`
or `{"error"}`.

> **Validation (self-validating — Phase-H/P).** Curated `{"error"}` exit 1: the `dust` extra not
> installed; the requested map not fetched (`run CLI option 59`); not exactly one direction mode;
> `dist_end ≤ dist_start` / `< 0`; `step_pc ≤ 0` / `n_steps < 1`; an endpoint resolver error. Argparse
> exit 2: a bad `--map` (not near-field/edenhofer/auto); a non-numeric `--l`/`--b`/`--ra`/`--dec`/
> `--dist-*`/`--step-pc`; `dust-between` without exactly one endpoint per side
> (`--star1`/`--id1`, `--star2`/`--id2` are required mutually-exclusive groups). **Geometry leaving a
> map box is never an error** (null bin + note). ‡ `dust-between` resolves `--star…` endpoints through
> SIMBAD (a name → position); `--id…` endpoints and the direction maths are offline against the local
> caches.

#### Dust-weighted routing — `--weight dust` (Phase T2 Part B)

The five Core route planners (`jump-route`, `optimal-tour`, `multi-stop`, `nearest-neighbor`,
`trade-route`) gain three flags: **`--weight {distance,dust}`** (default `distance` — the unchanged
`core/calculators.py` path; existing callers are byte-identical), **`--map {near-field,edenhofer,auto}`**
(default `auto`), and **`--dust-step-pc`** (the per-leg integration step, default 5 pc — coarser than a
reported corridor). With `--weight dust`, the edge weight becomes the **integrated A_V (mag, R_V=3.1)**
along each leg (from `core/dust.py`), so the route minimizes *extinction* instead of distance. The dust
path lives in the forked `core/dust_routing.py` (the optional `dustmaps` extra is never imported by the
stellar layer). **Reachability stays geometric:** `--max-jump` / `--max-ly` still govern which edges exist
— dust only weights edges that already exist; an unreachable destination is still a clean
`reachable:false`, not an error.
```bash
query.py jump-route --origin Sol --destination Procyon --max-jump 9 --weight dust
query.py jump-route --origin Sol --destination Procyon --max-jump 9 --weight dust --map near-field --dust-step-pc 2
query.py trade-route --stars Sol Sirius Procyon "61 Cygni" --weight dust
```
Core: `dust_routing.compute_jump_route_dust` / `compute_optimal_tour_dust` / `compute_multi_stop_dust` /
`compute_nearest_neighbor_dust` / `compute_trade_route_dust`. **A_V is a non-negative additive edge weight**,
so Dijkstra (`jump-route --optimize distance`) and Kruskal (`trade-route`) stay correct; `jump-route
--optimize jumps` is still BFS (fewest jumps, dust reported). Each result extends its distance sibling's
shape with **per-leg/edge** `a_v`, `a_v_lo`, `a_v_hi`, `weight_value`, `fully_covered`, `cumulative_av`, and
**top-level** `weight:"dust"`, `total_av` (+`_lo`/`_hi`), `all_legs_covered`, plus the **distance-optimal
comparison** `distance_optimal_ly`, `distance_optimal_av`, `extra_ly`, `saved_av` (the dust column of the
min-ly route over the same graph — "the least-dust route is `extra_ly` longer but saves `saved_av` mag of
extinction"; for `multi-stop` the order is fixed so the comparison is degenerate, `extra_ly`/`saved_av` = 0).
An out-of-coverage leg integrates only its covered portion and is flagged `fully_covered:false`.

> **Validation:** `--weight dust` requires the dust extra + a fetched map (else the same curated `{"error"}`
> exit 1 as `dust-sightline`); a bad `--weight`/`--map` is argparse exit 2; the underlying planner's own
> validation (positive `--max-jump`, ≥2 stars, resolvable names) is unchanged.

##### `jump-route --weight blend` (Phase AD C11)

**`jump-route` only** (the `_grid_search` planner) gains a third weight, **`--weight blend`**, with
**`--alpha`** (distance weight) and **`--beta`** (A_V weight): each edge costs `α·distance_ly + β·A_V`,
fed to the same Dijkstra. `--beta 0` reproduces the `--weight distance` route; `--alpha 0` reproduces the
`--weight dust` route; an intermediate blend is a compromise (raising `--beta` flips the route from the
distance corridor toward the least-dust detour). Both default to 1.0 when omitted under `--weight blend`.
```bash
query.py jump-route --origin Sol --destination Procyon --max-jump 9 --weight blend --alpha 1 --beta 50
```
Core: `dust_routing.compute_jump_route_blend(origin, destination, max_jump_ly, optimize="distance",
alpha=1.0, beta=1.0, map_sel="auto", dust_step_pc=5.0)`. Output mirrors the dust route's shape plus
`weight:"blend"`, echoed `alpha`/`beta`, and `total_blend_cost` (= `α·total_ly + β·total_av`).
**Validation:** negative `--alpha`/`--beta`, or both 0, → curated `{"error"}` exit 1; `--alpha`/`--beta`
supplied **without** `--weight blend` → exit 1 (handler guard); the dust preflight (missing extra /
unfetched map) applies as for `--weight dust`; a bad `--weight` choice is argparse exit 2. **Reachability
stays geometric.** The other four planners keep `--weight {distance,dust}`. **Still deferred:**
`--max-leg-av` pruning, the `jump-network` cost-budget, and `farthest-first` dust-weighting.

#### `compare-stars`
Side-by-side comparison of **2–4 stars** in one structured result (Phase L1). Live network (SIMBAD + an optional NASA
pscomppars supplement + Hypatia). This is the one call that bundles work an external caller would otherwise have to
reassemble from `simbad-lookup` + `planetary-systems` + `hypatia-data` per star **and** re-derive itself: the NASA
radius/mass/(teff/lum) supplement, the photometric mass/radius/luminosity fallback, and the conservative HZ inner/outer
bounds.
```bash
query.py compare-stars --stars "Tau Ceti" Sol "18 Sco" "Delta Pavonis"
```
Core function: `databases.compare_stars(names)`. Output: `{stars: [{name, sp_type, teff, luminosity, mass, radius,
hz_inner_au, hz_outer_au, ly, app_magnitude, hypatia, error}, …]}` — `hypatia` is the raw `hypatia-data` result dict
(or `null`). **Per-star failures are isolated**: each star carries its own `error` (`null` on success) with missing
numerics `null`; the **only top-level `{"error"}` (exit 1)** is the arg-count check (< 2 non-blank names, or > 4).
`"Sol"`/`"Sun"` are injected from reference constants (G2V, 5778 K, 1 M/R/L☉, [X/H]≡0 baseline) with no SIMBAD call, so
`--stars Sol Sun` resolves fully offline. Missing/non-numeric `--stars` (or fewer than one value) is an argparse
**exit 2**.

### Project workspaces (Phase S — local DB, read-only)

Read-only views of the **project workspaces** (named sets of real + procedurally-generated
systems with notes), created/edited in the GUI **Projects** panel. **Mutations are GUI-only** —
`query.py` exposes only these two readers (the "no DB-write subcommands" principle), so the sibling
repo can enumerate a setting and pull each member, then call `dossier` / `generate-system` /
`simbad-lookup` per member. Local-DB reads (no network); the DB path is overridable via
`SPACE_APP_DB`. Both backed by `core/projects.py` (the additive `projects` / `project_members`
tables; see `docs/gui-architecture.md` Phase S).

#### `project-list`
All project workspaces with member counts.
```bash
query.py project-list
```
Core function: `projects.list_projects()`. Output: `{"projects": [{project_id, name, description,
created_date, member_count}]}` (sorted by name, case-insensitive). Empty store → `{"projects": []}`.

#### `project-get`
A project + its members.
```bash
query.py project-get --name "The Frontier Campaign"
```
Core function: `projects.get_project(name)`. Output: `{project: {project_id, name, description,
created_date}, members: [{star_name, note, source ("looked_up"|"generated"), generated_seed,
generated_spec, added_date}]}`. A **generated** member's `generated_spec` is echoed as a **parsed
JSON object** (the `generate_system` params that re-create it byte-identically — seed, mode,
spectral_class, n_planets, anchor_star, constraints, companion, research_policy); `null` for
looked-up members. Unknown project name → `{"error": str}` exit 1; missing `--name` → argparse
exit 2.

> **Export note:** the GUI's *Export Project Dossier* (real members via Q's `build_system_dossier`,
> generated members via the R→Q `build_generated_dossier`, combined or per-file) is **GUI-only** in
> Phase S — it spans network + offline members. The composing core functions
> (`report.build_generated_dossier`, `report.build_project_dossier`) exist and are tested, but no
> `project-dossier` subcommand is exposed (additive later if the consumer asks).

### Reference data (Phase B — local DB / hardcoded, no arguments)

#### `main-sequence`
Main-sequence star properties table. Returns a **list** of 24 rows, one per spectral class, with the raw CSV columns
(`Spectral Class, B-V, Teeff(K), AbsMag Vis., AbsMag Bol., Bolo. Corr. (BC), Lum, R, M, p (g/cm3), Lifetime (years)`).
```bash
query.py main-sequence
```
Core function: `science.compute_main_sequence_table()`.

#### `solar-system`
Solar-system reference data. Output `{planets[], moons[], dwarf_planets[], asteroids[]}` (raw CSV columns per body).
```bash
query.py solar-system
```
Core function: `science.compute_solar_system_tables()`.

#### `sol-regions`
Sol's full system-regions computation from hardcoded solar constants (the opt-13 calculation). Output is the same flat
region dict as `star-regions` (`hzil, hzol, snowLine, lh2Line, bcLuminosity, stellarMass, distAU, the alternate-
biochemistry pairs, …`) but for the Sun, with no SIMBAD/Hypatia step.
```bash
query.py sol-regions
```
Core function: `regions.compute_sol_regions()`.

### Planetary / rotating-habitat equations (Phase B — pure math, no network)

> **Validation:** like the Phase-N pure-compute subcommands, these wrap the project's **older, non-self-validating**
> equation functions. Argparse rejects missing/non-numeric args (**exit 2**). Out-of-range values do **not** yield a
> curated error: where the math raises (e.g. `--rpm 0` → division by zero in `gravity-distance`), the top-level handler
> returns `{"error": str(e)}` (raw message, **exit 1**); where it doesn't (e.g. `orbit-distance --ecc 1.5` just yields a
> negative periastron), the result is returned as-is with **exit 0**. Validate ranges on the caller side.

#### `orbit-distance`
Periastron / apastron from semi-major axis + eccentricity (opt 33).
```bash
query.py orbit-distance --sma 1.0 --ecc 0.0167
```
Core function: `equations.compute_orbit_periastron_apastron(sma, ecc)`. Output: `{sma, ecc, periastron, apastron, ecc_au}`.

#### `moon-orbital-distance`
Orbital distance of an Earth-sized moon for a given day length (opts 34/35). `--day-hours` defaults to 24.
```bash
query.py moon-orbital-distance --planet-mass-earth 1.0 --day-hours 24
```
Core function: `equations.compute_moon_orbital_distance(planet_mass_earth, day_hours)`. Output:
`{planet_mass_earth, day_hours, orbital_distance_km}`.

#### `gravity-acceleration` / `gravity-distance` / `gravity-rpm`
The three rotating-habitat solves (opts 36/37/38) — each solves for the missing one of {rpm, radius, gravity}.
```bash
query.py gravity-acceleration --rpm 2 --radius-m 224     # → accel_ms2
query.py gravity-distance --rpm 2 --accel-ms2 9.81       # → radius_m
query.py gravity-rpm --accel-ms2 9.81 --radius-m 224     # → rpm
```
Core functions: `equations.compute_centrifugal_gravity_acceleration(rpm, radius_m)` /
`_distance(rpm, accel_ms2)` / `_rpm(accel_ms2, radius_m)`. Each output echoes all three values
(`{rpm, radius_m, accel_ms2}`) with the computed one filled in.

#### `travel-time-custom-thrust`
Travel time between two solar-system bodies with a **custom burn duration** (accelerate for the burn, coast, decelerate
for the same burn — the opt-23 calculation). **Live JPL Horizons** (the only network entry in this group).
```bash
query.py travel-time-custom-thrust --origin Earth --destination Mars --accel-g 1.0 --burn-value 2 --burn-unit D
```
Core function: `calculators.compute_travel_time_custom_thrust(origin, destination, accel_g, burn_duration_s,
v_cap_pct=3.0, burn_value=…, burn_unit_label=…, departure_date=None)`. `--burn-unit` is `H`/`D`/`W` (Hours/Days/Weeks,
default `D`); the CLI converts `--burn-value` + `--burn-unit` to `burn_duration_s` and passes the value/label through for
display. `--v-cap-pct` defaults to `3.0`; `--date` is ISO `YYYY-MM-DD` (default today). The GUI-only `progress_callback`
is never passed. Output: the full phase/burn-profile dict (`travel_time_str, t_total_hours, distance_au, distance_lm,
eff_burn_s, v_coast_ms, fallback, iterations_done, …`). Ambiguous Horizons names return the disambiguation error from
the core function.

## Two-step subcommands

For subcommands that run SIMBAD first (`star-regions`, `exoplanets`, `planetary-systems`, `hwo-exep`, `mission-exocat`, `hwc`, `hypatia-data`): if the SIMBAD lookup returns `{"error": ...}`, that error is returned immediately and the second core function is never called.

`dossier` (Phase Q) runs SIMBAD first for a real star and aborts with that error if it fails; per-section sources that fail *after* SIMBAD resolves become warnings, not errors. `dossier --star Sol`/`Sun` runs no SIMBAD/network step at all (the offline reference-origin path; it reads the local Solar System tables, overridable via `SPACE_APP_DB`).

`generate-system` (Phase R1) runs **no network in synthetic mode** (no `--anchor-star`). With `--anchor-star` it runs SIMBAD first (then `compute_star_system_regions_from_simbad` + NASA pscomppars / HWC); an unresolvable anchor or a non-OBAFGKM (e.g. white-dwarf) regions failure is returned immediately as `{"error": ...}`, while missing observed planets is a `warnings[]` entry, not an error.

The `gcns-within-sol`, `gcns-source`, and `gcns-system` subcommands are **local DB reads** (no SIMBAD step). The `gcns-distance` / `gcns-travel-time` / `gcns-stars-within-star` calculators are local DB reads **except** for `--star…` endpoints, which add a SIMBAD name-resolution step (a SIMBAD error on any `--star…` endpoint is returned immediately). The DB path can be overridden with the `SPACE_APP_DB` environment variable (used by tests).

`circumbinary-hz` (Phase T1a/T1b) is **offline in its numeric mode** (`--teff1/--lum1/--teff2/--lum2`); its `--star1/--star2` mode adds a SIMBAD lookup per star (→ `compute_star_system_regions_from_simbad` for teff/luminosity), returning a SIMBAD/regions error immediately. The two modes are mutually exclusive (both, or one star only, or a partial numeric set → argparse-style exit 2). All other Phase T1b calculators (`rv-semi-amplitude`, `transit-signal`, `astrometric-signal`, `direct-imaging`, `tidal-heating`, `kozai-lidov`, `relativistic-brachistochrone`) are pure-compute, no network.

## Implementation notes

- No `sys.path` manipulation — Python prepends the script's own directory automatically when run directly, so `import core.X` works without changes.
- Unexpected exceptions from core functions are caught by a top-level handler in `main()` and returned as `{"error": str(e)}` with exit code 1.
- `--ly-hr` and `--times-c` are a mutually exclusive required group for `travel-time`, `optimal-tour`, and `multi-stop`; supplying both or neither is rejected by `argparse` with exit code 2.
- The `gcns-*` calculators use one required mutually-exclusive group **per endpoint** (`--star1`/`--id1`, `--star2`/`--id2`, or `--star`/`--id`), plus the `--ly-hr`/`--times-c` group for `gcns-travel-time`. Supplying both or neither within any group is rejected by `argparse` with **exit code 2** and a message on **stderr** — this is the argparse path, **not** the JSON-`{"error"}`/exit-1 path, so do not parse stdout as JSON for those invocations. A resolvable-but-invalid request (e.g. a name not in GCNS, an ambiguous name, or an empty `gcns_stars` table) instead returns `{"error": ...}` on stdout with exit 1.
- **Phase T mode-selection groups:** `rv-semi-amplitude` uses a real **argparse** required mutually-exclusive group `--period-days`/`--sma-au` (both/neither → exit 2). `circumbinary-hz` (numeric `--teff1/--lum1/--teff2/--lum2` vs `--star1/--star2`) enforces its mode exclusivity **in the handler** — both modes, one star only, or a partial numeric set → a stderr message + **exit 2**. `kozai-lidov` requires exactly one complete pair (both periods **or** both SMAs); a partial/both-pair input is a **core** check → curated `{"error"}` **exit 1**. `solar-analogs --mode` is an argparse `choices` (bad value → exit 2). `substellar --classes` is `nargs="+"`.
- **Phase W `spin-comfort` anchors:** the two gravity forms `--gravity-g` / `--accel-ms2` are an **optional** argparse mutually-exclusive group (both → exit 2), but the "**exactly two** state anchors" rule is a **core** check → curated `{"error"}` **exit 1** (so 0 / 1 / 3 / 4 anchors is exit 1, not the argparse exit 2). `--criteria` is an argparse `choices` (bad value → exit 2); the per-threshold overrides and `occupant-height-m ≥` the *solved* radius are core checks (exit 1).
- **Phase N validation asymmetry** (see "Integration expansion (Phase N)" above): the pure-compute Phase-N subcommands (`habitable-zone-sma`, `star-luminosity`, `brachistochrone-au`, `brachistochrone-lm`) wrap **non-self-validating** legacy core functions, so out-of-range numerics surface via the generic top-level handler as `{"error": str(e)}` with a **raw exception message** (not a curated sentence), exit 1 — except `star-luminosity`, which has no out-of-range error path (only argparse exit 2). Only `travel-time-solar` returns curated `{"error": ...}` dicts. This is intentional (Phase N adds no `core/` validation); key on `"error"` + exit code, never on the message text.
