# Integration Tool Documentation — `query.py`

`query.py` is a thin JSON dispatcher at the repo root. It allows the `scifiWorldBuilding-Claude` repo (the current consumer — it sits alongside this checkout under `.../Claude/` and calls in through its `bin/sfq` wrapper; formerly the `ScienceFictionResearch-Claude` repo) and any other caller to invoke `core/` functions via a Bash command and receive structured JSON on stdout without needing a copy of the core code.

> **Cross-repo coordination channel.** Spec/contract questions between this app repo and `scifiWorldBuilding-Claude` are handled asynchronously via the shared, append-only file **`/home/greg/claude/coordination-channel.md`** (parent dir of both repos; note the lowercase `claude`). It carries a protocol preamble at the top — newest entry on top, per-entry `STATUS`, and the file-ownership rule (**this repo owns code/tests/`docs/integration.md`; the research repo owns request/spec/canon files — each side edits only its own repo's files and requests changes to the other's in-channel**). Read it before acting on a cross-repo request; post a reply entry when you action one.

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

### Luminosity-flag aliases (P4.2)

`--luminosity` and `--luminosity-lsun` are **interchangeable aliases** on every subcommand
that takes a stellar luminosity: `habitable-zone`, `habitable-zone-sma`, `solvent-zone`,
`ice-lines` (documented as `--luminosity`) and `par-flux`, `equilibrium-temp`,
`insolation-shift`, `dyson-collector` (documented as `--luminosity-lsun`) all accept either
spelling. The documented spelling per command stays primary in `--help`; the other is an
accepted synonym.

### `jump-route` gains four always-present waypoint keys (2026-07-31)

**Additive; no existing key changed value or type.** `jump-route` now returns three new top-level keys —
**`via`** (list, `[]`), **`via_legs`** (list, `[]`) and **`unreachable_leg`** (`null`, or `{from, to}` naming the
hop that failed when `reachable: false`) — plus an always-present boolean **`waypoint`** on every `route[]` row.
They are present on **every `--weight` value** (`distance`, `dust`, `blend`), so no `KeyError` branch is needed.

They back **`--via N [N …]`** (see the `jump-route` section below): required intermediate waypoints, a *set* of
stars the route must pass through, visited in whichever order is cheapest under `--optimize`. Without `--via`
every response has `via: []` / `via_legs: []` / `waypoint: false`, exactly as before. Two things to code for:

- **A waypointed route may revisit a star.** `route[]`/`stars[]` can repeat a name — `jump-route`'s first-ever
  repeated star (`multi-stop`/`optimal-tour` already do it). So `len({s["name"] for s in stars}) != len(stars)`
  becomes possible, and any `{s["name"]: s for s in stars}` index **silently loses route position**. Index by
  position, not by name.
- **`reachable: false` no longer implies two stars.** `stars[]` returns *every* terminal (origin + waypoints +
  destination), and `unreachable_leg` — not the origin/destination pair — names what actually failed.

`route[]` stays flat and continuously numbered (`jump: 1..n`) across the whole trip; `route[i]["from"] ==
route[i-1]["to"]` and `len(stars) == jumps + 1` still hold. Full semantics: `docs/calculators.md` §B
("Required waypoints").

### Route-map dot colours unified (2026-07-27)

The `stars[]` map dicts returned by the seven route planners (`multi-stop`, `nearest-neighbor`,
`trade-route`, `optimal-tour`, `jump-route`, `jump-network`, `farthest-first`, plus their
`--weight dust`/`blend` variants) carry a **`color`** hex per star. Those hexes came from a
route-only palette that disagreed with the app's star-chart palette; it was deleted
(`completed_plans/ROUTE_CHART_REFACTOR_PLAN.md` Phase 3) and `color` now comes from the single
`core.shared.sp_color`. **Four values changed** — G `#fff4c2` → `#FFF4EA`, M `#ff9d6c` →
`#FF8D3F`, D `#dfe6ff` → `#B0C4DE`, unknown/unparseable `#cccccc` → `#AAAAAA`; `O B A F K` and
`L T W Y C N` are unchanged. Hexes are now also **uppercase**, so a consumer comparing them
literally should casefold. Structure, keys and every other field are untouched. `jump-network`'s
per-tier `color` (from `TIER_COLORS`) is unaffected — it overrides the spectral colour by design.

### Star designation strings (2026-07-26)

Several subcommands return a **comma-separated designation string** — `"Star Designations"`
(`stars-within-sol`, `stars-within-star`), `designations` (`search-star-systems`), `desig`
(`nearest-neighbor`, `jump-network`, `farthest-first`, `trade-route`, and the `stars[]` map dicts of
the other route planners), and `desig_str` (`distance`, `travel-time`). **All of them now lead with
SIMBAD's common name when the star has one**, then the catalog IDs:

```
NAME Chara, GJ 475, HD 109358, HIP 61317, HR  4785, Gaia DR3 1534011998572555776, 2MASS J12334454+4121270
```

Previously the `star_systems`-backed fields dropped the `NAME` token entirely (the SIMBAD-backed
`desig_str` of `distance`/`travel-time` always included it, so the two families now agree). Notes for
consumers:

- **Parse with a real CSV/split-on-`", "` reader, not by position** — index 0 is no longer reliably a
  catalog ID. A star with no common name is unchanged (no leading token is added).
- The `star_systems`-backed fields only carry NAME **after an option-50 rebuild**; rows written before
  2026-07-26 have none.
- `simbad-lookup`'s `designations` **dict** is unaffected — it always had a `NAME` key (`null` when
  absent), and dict access is order-independent.

### Bayer & Flamsteed designations (Phase AN2, 2026-07-29)

The designation set gained **two new keys, `Bayer` and `Flamsteed`** — the α/β/γ and numbered forms
SIMBAD returns under an asterisk-space prefix (`* alf CMi`, `*  10 CMi`), which the app parsed and
then silently discarded until now. **23 of 43 sampled stars had at least one such id being dropped**
(18 of them an id that was not already visible as `main_id`).

```
"designations": { "MAIN_ID": "* alf CMi", "NAME": "NAME Procyon",
                  "Bayer": "* alf CMi", "Flamsteed": "*  10 CMi", "GJ": "GJ 280 A", … }
```

- **Values are the verbatim SIMBAD string**, prefix intact and internal spacing untouched — note
  Flamsteed's **double space** (`"*  10 CMi"`). The raw string is the identifier and is
  round-trippable; pretty-rendering (`10 Canis Minoris`) is a display concern, never stored.
- **Additive, but key ORDER moved.** The two keys are inserted directly after `NAME`, so a consumer
  that reads the JSON object positionally sees a reordering. Read by key.
- **`Bayer` is frequently equal to `MAIN_ID`** — for a bright star SIMBAD's main id usually *is* the
  Bayer form (16 of 43 sampled). The dict carries both; the rendered **`desig_str` emits a repeated
  value only once**, keeping the first (`MAIN_ID`). So `desig_str` gains the Flamsteed id on such a
  star and not the Bayer one, while the dict has both.

#### `desig_str` now suppresses **any** repeated value — including on stars with no Bayer id

The dedupe above is not specific to `Bayer`, and it changes `desig_str` for stars this section
otherwise says nothing about. `main_id` frequently duplicates an ordinary catalogue slot — a planet
host whose main id is its HD number used to render the token twice:

```
before   "HD 209458, HD 209458, HIP 108859, TIC 420779000, …"
after    "HD 209458, HIP 108859, TIC 420779000, …"
```

**13 of 43 sampled stars (30%) are affected this way with no `* ` id involved** — HD 209458, HR 8799,
Kepler-186, TOI-700, WASP-12, CoRoT-7, HAT-P-11, Wolf 359, Barnard's star, GJ 35, Kapteyn's star,
Luyten's star, HD 102365. The duplicate was a pre-existing wart; removing it is an improvement, but
**a consumer that splits `desig_str` on `", "` and counts or indexes tokens will see one fewer**. The
`designations` **dict is unchanged** by this — both keys still hold the value. Only the rendered
string dedupes.
- **`V*` variable-star ids and `**` double-*system* ids are deliberately not captured.** `**` is an
  id for a pair, not a name for the queried star; `V*` is redundant with the Bayer form on
  essentially every star carrying both.
- **The narrow designation strings are unchanged** — `desig` / `desig_str` on `distance`,
  `travel-time` and all seven route planners still carry `NAME/HD/HR/GJ/Wolf` only. Those results
  already name the star separately, which for a bright star is the Bayer string.
- **`search-star-systems` and the other `star_systems`-backed fields DO carry these** as of the
  **2026-07-29 option-50 rebuild** (this note previously said they did not — the column is written
  only by a rebuild, and one had not happened when the keys shipped). **2135 rows** carry a `* `
  token; `--designation-prefix "*  10"` returns 29 rows, `"* alf"` returns 86. Mind the **double
  space** in a Flamsteed prefix. The rebuild changed **no row count** (256,003 before and after,
  0 discarded).

#### Which id you get when a star offers several (Phase AN, settled 2026-07-29)

A star can carry more than one competing Bayer or Flamsteed id. The pick is **rule-based and
deterministic** — it does *not* follow SIMBAD's id order, which is not a stable contract:

- **Bayer** — the component-less form wins (`* alf CMi` over `* alf CMi A`), then the **superscript**
  one (**`* ksi02 Cap` over `* ksi Cap`**; in 47 of the 49 affected stars a numbered *sibling* star
  exists, so the bare form does not say which is meant).
- **Flamsteed** — the component-less form wins (`*   4 Cen` over `*   4 Cen A`), then the one whose
  constellation matches the chosen Bayer (which rejects Fomalhaut's cross-boundary `*  79 Aqr` in
  favour of `*  24 PsA`).
- Where no rule can prefer — **α And *is* δ Peg** — the tie breaks on the raw string, so the value is
  arbitrary but **cannot drift** when CDS reorders its ids.

**No pick can be wrong:** SIMBAD attaches no `* ` id to more than one object (0 of 6293 measured), so
every candidate is an unambiguous designation of that star. Consumers wanting the readable form can
call `core.shared.format_star_designation("*  10 CMi")` → `"10 Canis Minoris"`; it is **never stored
or serialized**, so this contract always carries the raw string.
- `SAO` remains **uncaptured** (considered and declined alongside these two), so `gould.matched_on`
  is still always `"hd"`.
- **`simbad-lookup`'s `desig_str` empty case is now `""`, not the string `"N/A"`** (Phase AN2e). A
  star with no capturable designation at all previously returned the literal two-character-plus-slash
  token as *data*; it is an empty string now, matching every other designation-string field in this
  contract. **Effectively unreachable** — the string leads with `main_id`, which falls back to the
  queried name — so no real star's output changes; it is listed because a consumer testing
  `desig_str == "N/A"` would now never match.

## Quick reference

Every success result is a JSON **dict** unless noted. Every failure is `{"error": "<message>"}` with exit code 1. Always check for an `"error"` key before reading other fields.

| Subcommand | Required args | Network | Output top-level keys (success) |
|---|---|---|---|
| `simbad-lookup` | `--star` | SIMBAD | `main_id, ra, dec, sp_type, plx_value, teff, vmag, fe_h, ly, parsecs, designations, desig_str, gcns, gould` (`fe_h` = [Fe/H] from `mesfe_h`, `null` when absent; `gcns` optional — Phase M5, `null` when absent; `gould` optional — Phase AO, `null` when absent) |
| `oec-system` | `--name` | none (local cache)‡ | `query, matched_name, system` (recursive node tree) |
| `oec-planet` | `--name` | none (local cache)‡ | `query, planet, attached_to, host_chain, system_name` |
| `oec-search` | all optional (`--min-stars/--max-stars`, `--status`, `--circumbinary`, `--discovery-method`, `--discovery-year-min/max`, `--mass-min/max`, `--radius-min/max`, `--period-min/max`, `--sma-min/max`, `--spectral-type`, `--limit`) | none (local cache)‡ | `count, capped, cap, filters, systems[]` |
| `oec-census` | none | none (local cache)‡ | topology stats (`n_systems/stars/planets/binaries/satellites`, distributions, `planet_attachment`, `circumbinary/rogue/planetless`, histograms) |
| `oec-status` | none | none (local cache)‡ | cache snapshot (`cached, cache_size_bytes, cache_mtime_utc, cache_age_days, stale`) + element counts |
| `star-regions` | `--star` | SIMBAD + Hypatia | region values (see below) + `simbad` + `hypatia` |
| `star-regions-manual` | `--vmag --bc --teff --parallax` [`--sunlight-intensity --bond-albedo`] | none | flat dict of region values (`hzil, hzol, snowLine, stellarMass, distAU, …`) + echoed inputs |
| `distance` | `--star1 --star2` | SIMBAD† | `star1_info, star2_info, distance_ly, distance_au` (each `*_info` carries `sp_type`) |
| `stars-within-sol` | `--ly` | none (local DB) | `limit_ly, count, stars[]` |
| `stars-within-star` | `--star --ly` | SIMBAD | `center, center_x/y/z, limit_ly, count, stars[]` |
| `travel-time` | `--star1 --star2` + (`--ly-hr` \| `--times-c`) | SIMBAD† | `origin_info, dest_info, distance_ly, ly_hr, times_c, total_hours, travel_time_str` |
| `habitable-zone` | `--teff --luminosity` | none | **list** of 6 zone dicts (not a dict) |
| `exoplanets` | `--star` | SIMBAD + archives | `simbad, planets[], hwo, exocat` |
| `planetary-systems` | `--star` | SIMBAD + archive | `simbad, planets[]` |
| `planetary-systems-batch` | Mode A: `--hosts N […]` \| `--host-file P`; Mode B: property filters (`--mass-min/max --radius-min/max --period-min/max --teff-min/max --dist-max-pc --method --spectral-classes/-refine`) \| `--archive-query "ADQL"`; both: `--solution-scope {default,all}` `--fields {core,full}` | **NASA TAP `ps` (live)** + SIMBAD (Mode A) + pscomppars/OEC (full) | `mode, solution_scope, field_scope, coverage{}, hosts[]` (+ CR-9 disposition/quality + CR-10.1 `survey_disposition`/`survey_siblings` fields) — see CR-8 + CR-9 + CR-10 blocks below |
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
| `cooling-hz` | `--track {wd,bd}` [`--mass-solar`\|`--mass-mjup` · one of `--teff`\|`--cooling-age-gyr`\|`--sma-au` · `--chz-threshold-gyr --hz-edge --age-max-gyr --satellite-density` · `--cooling-delay-gyr --distillation-teff-k` (AD A0, WD-only ²²Ne pause)] | none (bundled cooling table) | mode 1: `teff_k, lum_lsun, radius_rsun, zones[], out_of_range_teff`; mode 2: `ever_habitable, entry/exit_age_gyr, residence_gyr`; mode 3: `chz_inner/outer_au, inner_edge_roche_limited, roche_limit_au`; all: `mode, model_note, any_out_of_range, hz_model_valid_teff_k`; +pause: `pause_teff_k, pause_hz_inner/outer_au, effective_age_max_gyr`. **CR-11.1:** WD `--mass-solar` accepts 0.40–1.30 M☉ (clamp 1.30–1.38 Chandrasekhar; refuse >1.38); ≤1.0 byte-identical |
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
| `waste-heat` | steady: (`--input-power-watts`\|`--useful-power-watts`) [`--efficiency` \| `--hot-temp-k --cold-temp-k`]; **transient (C9)**: all of `--peak-w --mean-w --duty --pulse-period-s --storage-mass-kg --specific-heat-jkgk` | none | steady: `waste_heat_w, useful_power_w, input_power_w, efficiency, carnot_efficiency, carnot_min_waste_heat_w, carnot_limited, notes, model_note`; transient: `mode, on_time_s, excess_power_w, heat_capacity_j_per_k, temp_swing_k, buffer_time_s, notes` |
| `radiator-area` | (`--heat-watts` \| `--input-power-watts --efficiency`) `--radiator-temp-k` [`--emissivity --sides --sink-temp-k --areal-mass-kgm2`] | none | `radiator_area_m2, radiator_area_km2, flux_wm2, blackside_flux_wm2, heat_watts, radiator_mass_kg, scaling_note, model_note` |
| `shielding-attenuation` | photon/gcr: (`--areal-density-gcm2` \| `--thickness-cm --density-gcm3`) + coeff (`--mass-atten-coeff-cm2g`\|`--attenuation-length-gcm2`\|`--material [--energy-mev]`) [`--mode {photon,gcr}`]; **charged (C6)** `--particle {proton,alpha,ion} --energy-mev` (`--material`\|`--csda-range-gcm2`); **stack (C7)** `--layers "mat:gcm2,…"` | none (bundled XCOM/PSTAR) | photon: `transmitted_fraction, half_value_layer_gcm2, tenth_value_layer_gcm2, …, is_order_of_magnitude`; csda: `mode:"csda", csda_range_gcm2, csda_range_cm, stops_primary, penetrates, residual_range_gcm2`; layers: `layers[], total_transmitted_fraction, total_attenuation` |
| `active-shield` | `--shield-radius-m` + one field source (`--magnetic-moment-am2` \| `--coil-current-a --coil-radius-m` \| `--field-tesla --field-radius-m`) [`--spectrum-characteristic-rigidity-gv`] | none | `rigidity_cutoff_gv, rigidity_cutoff_v, magnetic_field_t, magnetic_moment_am2, field_source, deflected_fraction, is_order_of_magnitude, model_note` |
| `radiation-ceiling` | exposure (`--absorbed-dose-gy`\|`--fluence`) + quality (`--let-kev-um`\|`--particle-type`) **or** self-contained `--let-spectrum "LET:flu,…"`; [`--profile {acute,chronic}` `--dose-rate --dose-rate-unit --duration`]; [`--clade {baseline-human,gene-mod,cyborg,upload,custom}` `--pharmacological-dmf --career-budget-policy {600,1000} --ddref`]; [`--lever {repair-fidelity,p53} --lever-m-a --lever-m-b --allow-p53-double-improve --allow-required-breakthrough`]; [SEU `--seu-cross-section-cm2 --memory-bits --ecc-margin`] | none | `clade, clade_note, clade_confidence, profile, exposure{}, axis_a_deterministic{}, axis_b_stochastic{}, clade_modifiers{}, seu_budget, flags{}, provenance_legend{}, is_order_of_magnitude, model_note` |
| `annihilation-power-train` (AL R1) | (`--mass-flow-kgs`\|`--power-total-w`) [`--species {pp,ee}` · `--eta-dir`] | none | `power_total_w, power_directed_w, power_gamma_w, power_neutrino_w, eta_dir, species, model_note` |
| `antimatter-production` (AL R2) | (`--stored-mass-kg`\|`--stored-energy-j`) `--production-efficiency` [`--trap-field-t`] | none | `energy_in_j, energy_stored_j, production_efficiency, threshold_floor_efficiency, energy_ratio_in_per_stored, storage_density_kg_m3, notes, model_note` |
| `reactor-net-power` (AL R4) | `--gross-power-w --thermal-efficiency` [`--q-plasma --recirculating-fraction`] | none | `gross_power_w, electric_power_w, net_power_w, engineering_breakeven_q, thermal_efficiency, q_plasma, recirculating_fraction, model_note` |
| `beamed-power-delivery` (AL R7) | (`--wavelength-m`\|`--frequency-hz`) `--tx-aperture-m --rx-aperture-m --range-m` [`--tx-power-w --pointing-efficiency`] | none | `spot_diameter_m, capture_fraction, delivered_power_w, aperture_product_m2, full_coupling_product_m2, coupling_margin, wavelength_m, model_note` |
| `fusion-lawson` (AL R10) | `--fuel {d-t,d-he3,d-d,p-b11}` (`--density-m3 --temp-kev --confinement-s` \| `--triple-product`) [`--confinement-boost`] | none | `triple_product_kev_s_m3, ignition_threshold, q_fusion, ignited, confinement_boost, fuel, model_note` |
| `heat-pump` (AL R3) | `--cold-temp-k --hot-temp-k` (`--heat-lifted-w`\|`--work-w`) [`--efficiency-fraction`] | none | `cop_cool_carnot, cop_heat_carnot, cop_cool_actual, work_w, heat_lifted_w, heat_rejected_w, model_note` |
| `flywheel-storage` (AL R8) | `--tensile-strength-pa --density-kgm3` [`--shape-factor --mass-kg`] | none | `specific_energy_j_kg, specific_energy_wh_kg, stored_energy_j, shape_factor, model_note` |
| `smes-storage` (AL R9) | `--field-t` [`--critical-field-t` · (`--tensile-strength-pa --density-kgm3`) · `--volume-m3`] | none | `energy_density_j_m3, stored_energy_j, specific_energy_j_kg, field_t, critical_field_exceeded, model_note` |
| `energy-storage` (AL T1) | [`--class` · `--override-wh-kg` · (`--mass-kg --specific-heat-jkgk --delta-t-k` \| `--mass-kg --latent-heat-jkg`)] | bundled `_STORAGE` | lookup: `class, specific_energy_j_kg, specific_energy_wh_kg, volumetric_wh_l, round_trip_efficiency, leak_note, source_tag, note`; no class → `classes[]`; compute → `+stored_energy_j` |
| `reactor-power` (AL T2) | [`--class` · `--override-kw-kg` · `--gross-power-w`] | bundled `_REACTOR_SPECIFIC_POWER` | `class, specific_power_kw_kg, core_mass_kg, source_tag, note, thermal_pointer`; no class → `classes[], thermal_pointer` |
| `spin-comfort` | exactly two of (`--radius-m` \| `--rpm` \| `--gravity-g`\|`--accel-ms2` \| `--tangential-velocity-ms`) [`--occupant-height-m --walk-speed-ms --criteria {conservative,moderate,relaxed,all}` + per-threshold overrides] | none (bundled comfort bands) | `radius_m, rpm, angular_velocity_rads, accel_ms2, gravity_g, tangential_velocity_ms, head_gravity_g, gravity_gradient_pct, coriolis_ratio_pct, anchors, criteria{…}, overridden_thresholds, model_note, notes` |
| `life-support` | [`--crew --days --closure-scenario {open,iss,advanced,bioregen}` + per-stream `--*-closure` + per-rate `--*-rate`/`--kcal-per-day`] | none (bundled BVAD Rev2) | `crew, days, per_person_daily{…}, totals{…}, closure{water,o2,food}, scenario, makeup_mass_kg{o2,water,food,total}, model_note` |
| `bioregen-area` | exactly one light anchor (`--ppfd-umol` \| `--dli-mol` \| `--par-wm2`) [`--kcal-per-day --crew --crop` \| **`--crops "c:f,…"` (AD C10)** ` --photoperiod-h --photo-efficiency --harvest-index --artificial --led-par-efficiency --f-edible-energy`] | none (bundled crops) | `area_m2_per_person, area_m2_total, area_m2_per_person_measured, crops, per_crop_area_m2[], dli_mol, ppfd_umol, photo_efficiency, harvest_index, lighting{…}, crop_gas_exchange{o2_kg_day,co2_kg_day}, transpiration_water_kg_day, par_is_input_note` |
| `population-capacity` | ≥1 budget of (`--crop-area-m2` \| `--power-w` \| `--water-kg-day` \| `--fixed-nitrogen-kg-yr` \| `--food-dry-kg-day`) [per-person `--per-person-*` overrides] | none (X1/X2 defaults) | `per_resource{…{budget,per_person,source,population}}, sustainable_population, binding_constraint, slack{…}` |
| `solvent-zone` | `--luminosity` + (`--solvent NAME` \| `--t-low --t-high`) [`--albedo`] | none | `solvent, name, inner_au, outer_au, inner_lm, outer_lm, s_eff_inner, s_eff_outer, t_eq_inner, t_eq_outer, pressure_conditional, assumed_pressure_atm, citation, t_ref_k` |
| `ice-lines` | `--luminosity` [`--albedo`] | none | `luminosity_solar, albedo, t_ref_k, lines[]` |
| `dossier` | `--star` [`--fmt markdown\|html\|json` `--sections …` `--force-ms-inversion` `--star-mass-catalog <path>` `--mass-solar <M☉>`] | SIMBAD + NASA + Hypatia + Gaia FLAME + binary-orbit (none for `Sol`/`Sun`) | `star, fmt, sections, warnings, notes` + `document` (md/html) \| `data` (json); CR-10.5 adds `regions.{luminosity_class,evolved_star_flag,region_basis,luminosity_consistency}` + `multiplicity.multiplicity_basis`; **CR-11.2** adds `regions.mass{mass_solar,mass_provenance,massL_inversion_caution,peculiar_star_flag,inversion_mass_solar,note}` (a preferred measured mass recomputes radius/calc-L/limits — decision B) |
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
| `jump-route` | `--origin --destination --max-jump` [**`--via N [N …]`** `--optimize distance\|jumps` `--weight distance\|dust\|`**`blend`**` --alpha --beta --map --dust-step-pc`] | SIMBAD† (names) | `origin_info, dest_info, reachable, jumps, total_ly, direct_ly, route[], stars[]`, **`via, via_legs, unreachable_leg`**; blend adds `weight:"blend", alpha, beta, total_av, total_blend_cost` |
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
| `compare-stars` | `--stars N [N …]` (2–4) [`--star-mass-catalog <path>`] | SIMBAD + NASA + Hypatia + Gaia FLAME | `stars[]` (per-star error isolation) + **CR-11.2** per-star `mass_solar,mass_provenance,massL_inversion_caution,peculiar_star_flag,mass_note` (measured mass preferred → `mass`/`radius` track it, decision B) |
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
| `vizier-query` | `--catalog` [`--columns --filters --cone --row-limit`] | **CDS VizieR (live)**¶ | `service, catalog, count, row_limit, truncated, column_units, rows[]` |
| `catalog-cache-clear` | (none) | local FS (offline) | `app_cache_files_removed, astroquery_cache_dir, astroquery_cache_removed` — wipes `data/catalog_cache/` + any residual astroquery HTTP cache |
| `gaia-tap` | (`--adql` \| `--table`) [`--columns --where --cone --row-limit --async`] | **ESA Gaia TAP (live)**¶ | `service, query, count, async, truncated, column_units, rows[]` |
| `heasarc-query` | (`--catalog --cone` \| `--adql`) [`--radius --row-limit`] | **HEASARC (live)**¶ | `service, catalog, count, column_units, rows[]` |
| `binary-orbit` | (`--star` \| `--source-id` \| `--ra --dec`) | **CDS + ESA Gaia (live)**¶ | `query, identity, solutions[], route_tried[], units` (`note`/`route_errors` when relevant) |
| `close-binary-census` | `--dist-max-ly --period-max-d` [`--sep-max-au --include --parallax-source --keep-planets --separate-wide --exclude-known`] | **ESA Gaia + CDS (live)**¶ | `query, count, counts_by_class, dedup, census[], excluded_planets[], wide[], coverage, units` |
| `gaia-astrophysical` | (`--star` \| `--source-id`) | **ESA Gaia (live)**¶ | `query, source_id, identity, parameters, caveats, units` |
| `besancon-query` | (`--glon --glat` \| `--local`) [`--area --dist-max-pc --mag-max --sample-max --contact-email`] | **Besançon BGM (live; needs account)**¶ | `query, model_version, n_stars, columns, catalogue_sample[], catalogue_truncated, age_dist, coverage, units` |
| `salvo-exchange` | (`--alpha --beta` \| `--a-salvo/--a-hitprob` + `--b-salvo/--b-hitprob`) `--a1-staying --b1-staying` [`--a-force --b-force --a3-defense --b3-defense --sigma-a/-b --delta-a/-b --leak-a/-b`]; `--mode {simultaneous,first-strike,sequential-waves,break-even,solve-force,distribute,layered-defense}` + mode args | none | `mode, resolved_inputs, model_note` (always); the force-on-force modes (`simultaneous`/`first-strike`/`sequential-waves`) add `delta_a/_b, frac_loss_a/_b, overkill_a/_b, exchange_ratio` (or `final_survivors_a/_b`), `survivors_a/_b`, while `break-even`/`solve-force`/`distribute`/`layered-defense` return **only** their own per-mode keys (`break_even_force_ratio` · `required_force_exact`+`integer_wave` · `delta_targeted`+`targeted_count` · `survivors_to_target`+ring table) — see the W1 detail below |
| `beam-weapon-engagement` | `--aperture-m` (`--wavelength-m`\|`--frequency-hz`) `--power-w --target-size-m --range-m` (`--kill-fluence-jm2` \| `--target-material-enthalpy-jkg` + `--target-areal-density-kgm2`) [`--beam-quality-m2 --pointing-efficiency --rayleigh-k --max-dwell-s`] | none | `spot_diameter_m, frac_power_on_target_tophat/encircled, intensity_on_target_wm2, peak_spot_intensity_wm2, spot_smaller_than_target, dwell_to_kill_s, effective_range_spot_m, effective_range_dwell_m, light_travel_time_s, kill_fluence_jm2, model_note` |
| `kinetic-kill` | (`--mass-kg` \| `--length-m --diameter-m --density-kgm3`) (`--velocity-kms`\|`--beta`) `--target-density-kgm3` [`--target-type {monolithic,whipple}` (`--armor-thickness-m` \| `--bumper-areal-density-kgm2 --standoff-m --rearwall-areal-density-kgm2`) `--target-sound-speed-ms --crater-exponent --debris-cone-half-angle-deg`] | none | `ke_classical_j, ke_relativistic_j, ke_j, regime, tnt_equiv_t, specific_energy_jkg, momentum_kgms, penetration_depth_m, crater_penetration_m, perforates, whipple{}, model_note` |
| `warhead-effects-at-standoff` | (`--yield-j`\|`--yield-kt`) `--standoff-m` [`--warhead-type {fission,fusion,antimatter,kinetic-plasma}` `--f-xray/--f-neutron/--f-debris/--f-gamma`; `--threshold-{xray,neutron,debris,gamma}-jm2`] | none | `yield_j, warhead_type, channels{<ch>{fraction,fluence_jm2,kill_radius_m,killed_at_range,note}}, partition_fractions, escaping_fraction, killed_at_range, binding_channel, model_note` |

† `distance` and `travel-time` skip the SIMBAD call for an endpoint named `"Sol"`/`"Sun"` (treated as the origin at 0,0,0). The seven Route Planning subcommands (`optimal-tour`, `jump-route`, `jump-network`, `multi-stop`, `nearest-neighbor`, `farthest-first`, `trade-route`) likewise resolve each star **DB-first** (`star_systems.star_name`, offline) then **SIMBAD** for names not in the table; `"Sol"`/`"Sun"` → the origin with no lookup. They read the local `star_systems` table for intermediate/candidate stars (run option 50 to populate it).
‡ The `gcns-*` calculators (and `dust-between`) use SIMBAD **only** for `--star`/`--star1`/`--star2` endpoints (to resolve a name to a position/Gaia id); `--id`/`--id1`/`--id2` endpoints are fully offline. For the `gcns-*` calculators there is **no** `"Sol"`/`"Sun"` special case (Sol is not a GCNS row); `dust-between` **does** treat `Sol`/`Sun` as the origin.

§ A **local read of the fetched dust map cache** (`data/dust/`, populated by CLI **option 59** / the GUI Fetch Dust Map Data panel). Needs the optional `dustmaps` extra (WSL/Linux only) — see the **Dust / ISM** section below. No network for the map query itself.

¶ The **Phase AM catalog-access tier** (`vizier-query`, `gaia-tap`, `heasarc-query`, `binary-orbit`, `close-binary-census`, `gaia-astrophysical`, `besancon-query`) makes live queries to CDS / ESA Gaia / HEASARC / Besançon. Failures return `{"error": …}` (often with `route_tried[]`); an **empty but valid** result is `count: 0` / an empty list, **not** an error. Successful non-empty results are **cached** (`data/catalog_cache/`, gitignored; `SPACE_APP_CATALOG_CACHE=0` disables); **errors/empties are never cached**, and **astroquery's own HTTP cache is disabled** (`cache=False` on the Vizier/Heasarc/XMatch calls) so a throttle-induced empty can't be served stale for ~7 days — `catalog_cache` is the single cache authority. **`catalog-cache-clear`** wipes both layers (the app cache + any residual astroquery cache dir). `besancon-query` additionally requires a BGM account via `BESANCON_USER`/`BESANCON_PASS`. See the **Catalog-access tier (Phase AM)** section below for the full per-subcommand contract.

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
Output: `{main_id, ra, dec, sp_type, plx_value, teff, vmag, fe_h, ly, parsecs, desig_str, designations, gcns, gould}`. `fe_h` is the host `[Fe/H]` from SIMBAD's `mesfe_h` table (`null` when SIMBAD has no value); it is the real-anchor metallicity source for the `generate-system` v2 path. `designations` is a dict keyed by catalog (`MAIN_ID, NAME, Bayer, Flamsteed, GJ, HD, HIP, HR, Wolf, LHS, BD, K2, Kepler, KOI, TOI, CoRoT, COCONUTS, HAT_P, WASP, TIC, Gaia EDR3, 2MASS`); a catalog with no id is `null`. `Bayer`/`Flamsteed` are Phase AN2 (2026-07-29) — see **Bayer & Flamsteed designations** above for the verbatim-string, key-order and `desig_str`-dedupe notes. Numeric fields may be `null`.
- **Gaia id**: the `"Gaia EDR3"` key holds the Gaia source id as SIMBAD now formats it — `"Gaia DR3 <id>"` (SIMBAD renamed EDR3→DR3 in its id output; the source_ids are identical). To get the bare numeric id, strip the `"Gaia DR3 "` / `"Gaia EDR3 "` prefix. This is the same id used as `--id` for `gcns-source`.
- **`gcns`** (Phase M5): an **optional top-level GCNS cross-reference** — the matching `gcns_stars` row (same shape as `gcns-source`'s `star`: Bayesian `dist_pc` + `dist_lo_pc`/`dist_hi_pc`, `distance_method`, Gaia G/BP/RP, `astrom_reliable_prob`, `wd_prob`, `system_id`/`n_components`, …), giving a Bayesian distance **with 16th/84th-percentile uncertainty** beside the naive `1/ϖ` `ly`/`parsecs`. The key is **always present** but is `null` when the star has no Gaia id, is not in GCNS, or the `gcns_stars` table is empty/missing — **non-fatal and silent** (a single indexed local-DB read; no extra network). Built inside `compute_simbad_lookup`, so every `simbad`-embedding subcommand below carries it too.
- **`gould`** (Phase AO): an **optional top-level Gould designation** — the star's *Uranometria Argentina* (Gould 1879) number, e.g. HD 102365 → **66 G. Centauri**. Shape: `{g_number, cst, constellation, designation, display, hd, sao, matched_on, source}`, where `designation` is the abbreviated form (`"66 G. Cen"`), `display` the genitive form (`"66 G. Centauri"`), `cst` the IAU 3-letter code, and `matched_on` is always `"hd"` (see the join note below). `constellation`/`display` fall back to the raw abbreviation for an unrecognised code — a name is never invented. The key is **always present** but is `null` when the star has no HD number, is absent from the catalogue, or the `gould_designations` table is empty/missing — **non-fatal and silent**, like `gcns`. **Joins on HD only:** an SAO fallback was built and then removed (code review, 2026-07-29) because `designations` never carries an `"SAO"` key, making the branch unreachable — so `matched_on` is a constant and **a consumer branching on `"sao"` would be writing dead code**. `sao` is still echoed from the matched row. Only 26 catalogue rows have an SAO number but no HD, and just 3 of those carry a Gould number. **Sourced from bundled VizieR `V/135A`, not SIMBAD** (SIMBAD's `ident` table contains zero Gould ids), so no extra network call. **`null` is the normal answer for most stars:** Gould listed only bright *southern* stars — 8471 rows, 7756 with a Gould number — so an absent designation is correct coverage, not a lookup failure. **Constellations use Gould's 1875 boundaries and may disagree with the modern IAU one for the same star** — HD 100623 is `Hya` here while SIMBAD's own Flamsteed id is `*  20 Crt` (Crater). Both are right; do not reconcile them.

#### `oec-system` / `oec-planet` (Open Exoplanet Catalogue)
The Open Exoplanet Catalogue exposed as a recursive **`system → binary → star → planet → satellite`
hierarchy** (NOT a flat table). ‡ **Network:** the first call downloads `systems.xml.gz` (~1 MB) from the
`oec_gzip` GitHub repo to `data/oec/systems.xml.gz`; subsequent calls are **offline** (7-day staleness,
stale-cache fallback). Resolution is **offline direct-alias** against the OEC name index — the `query.py`
path does **not** call SIMBAD (`allow_simbad=False`). Self-validating: not-found / no name → `{"error"}`
exit 1; argparse exit 2. **Expectation:** OEC lists only systems with planets/candidates, so a planetless
star (Delta Pav, 36 UMa) returns `"'…' is not in the Open Exoplanet Catalogue (which lists only systems
with planets or planet candidates)."` — a correct result, not a bug.
```bash
query.py oec-system --name "Alpha Centauri"     # A, B and Proxima in one tree
query.py oec-system --name "HD 186408"          # alias → 16 Cygni (depth-2 nesting)
query.py oec-planet --name "Kepler-16 b"        # circumbinary → attached_to: "binary"
```
Core: `databases.compute_oec(name, allow_simbad=False)` / `databases.compute_oec_planet(name)`.

**Node shape (every node):** `{"tag": "system|binary|star|planet|satellite", "names": [str, …],
"fields": {…}, "children": [node, …]}` (`children` absent on leaves). **`fields`** is generic complete
capture: each key maps to a **value dict** `{"value": str, ["errorminus","errorplus","upperlimit",
"lowerlimit","unit","type"]}` — only present attributes appear. **A field may be a *list* of value dicts**
when the source tag repeats (e.g. `separation` in AU + arcsec; `list` — a planet in a binary carries
"Confirmed planets" *and* "Planets in binary systems, S-type"), so a consumer must treat every field as
possibly a list. `mass` may carry `"type": "msini"` (minimum mass). `upperlimit`/`lowerlimit` carry the
bound in the attribute (the `value` is then usually `""`).

- **`oec-system`** → `{query, matched_name, system: <node>}`. `system` is the full tree; a rogue planet is
  a `planet` child of the `system`; a zero-planet system still returns its stellar tree.
- **`oec-planet`** → `{query, planet: <node>, attached_to: "star"|"binary"|"system", host_chain: [<node
  shallow>, …], system_name}`. `attached_to` distinguishes normal (star), circumbinary/P-type (binary),
  and rogue (system); `host_chain` is the ancestor nodes (system → … → immediate parent), each **without**
  `children` (so siblings aren't dumped).

Field units are **not** encoded in the JSON where OEC leaves them implicit: planet `mass`/`radius` are in
**Jupiter** units, star mass/radius in **Solar** units, and a **`satellite`'s `mass`/`radius` are in
Jupiter units too** — exactly like a planet's (a consumer feeding Earth-unit tools must convert; multiply
by 317.828 / 11.209).

> **Correction, 2026-08-02.** This line previously said satellite mass/radius were in **Earth** units.
> They are not, and the JSON never changed — only this description was wrong. Verified against the
> catalogue: the Moon is `mass 0.000039` (= 7.35×10²² kg / 1.898×10²⁷ = 3.87×10⁻⁵ M♃, i.e. **0.0124 M⊕**)
> and `radius 0.024847` (= 1737 km / 71 492 km). **A consumer that trusted the old wording has been
> reading every moon 318× / 11× too small.** Affects the 18 satellites the catalogue carries (the Galilean
> moons, Titan, Triton, Charon, the major Uranian and Saturnian moons and Luna) — `oec-system` and
> `oec-planet` are the only subcommands that emit them.

#### `oec-search` / `oec-census` / `oec-status` (structural search + census — Phase 4)
Catalogue-wide readers over the **whole** parsed catalogue (same offline local cache ‡; no SIMBAD). All
three walk the ElementTree directly — cheap over ~4k systems. Self-validating (bad input → `{"error"}`
exit 1; argparse exit 2).
```bash
query.py oec-search --circumbinary                       # the 33 circumbinary (P-type) systems
query.py oec-search --min-stars 3 --spectral-type M      # ≥3-star systems with an M-dwarf host
query.py oec-search --status Confirmed --sma-max 0.1 --discovery-method transit
query.py oec-census                                      # topology statistics (the §A evaluation, live)
query.py oec-status                                      # cache freshness + element counts
```
Core: `databases.compute_oec_search(**filters)` / `databases.compute_oec_census()` /
`databases.compute_oec_status()`.

- **`oec-search`** → `{count, capped, cap, filters, systems: [row, …]}`. `count` is the **total** matches;
  `systems` is truncated to `cap` (`--limit`, default 300; `capped=true` when `count > cap`). `filters`
  echoes the set filters. A system matches when it passes the **system-level** filters (`--min-stars` ≤
  `n_stars` ≤ `--max-stars`; `--circumbinary` requires a P-type planet; `--spectral-type` is a
  case-insensitive **prefix** on a host star's spectral type — `G`→G0V…G9V, `DA`→white dwarfs) **and**,
  when any **planet-level** filter is set (`--status` substring on a planet's `<list>` status;
  `--discovery-method` substring; `--discovery-year-min/max`; `--mass/radius/period/sma-min/max`), carries
  ≥1 planet passing **all** of them (conjunction). Each **row**: `{name, n_stars, n_planets, n_binaries,
  n_satellites, max_binary_depth, circumbinary, rogue, spectral_types[], distance_pc, planets: [planet, …]}`
  — `planets` is the matching planets when a planet filter is set, else all of the system's planets. Each
  **planet**: `{name, mass, mass_type, radius, period, sma, eccentricity, discovery_method, discovery_year,
  status[]}` (mass/radius **Jupiter** units, period days, sma AU — OEC-native; `mass_type="msini"` marks a
  minimum mass). Validation: an inverted min/max range or `--limit < 1` → `{"error"}` exit 1.
- **`oec-census`** → catalogue topology statistics: `{n_systems, n_stars, n_planets, n_binaries,
  n_satellites, n_name_tags, n_alias_keys, stars_per_system{}, planets_per_system{}, binary_depth{},
  planet_attachment: {star, binary, system}, circumbinary_systems, rogue_systems, planetless_systems,
  discovery_methods{}, status_counts{}}`. The distributions are `{count_as_str: n_systems}`; the histograms
  are count-descending. (Live catalogue reproduces the plan's §A: attachment star 5370 / binary 39 /
  system 5; stars-per-system 1×3895/2×146/3×29/4×5/6×1.)
- **`oec-status`** → cache snapshot without the census walk: `{source, cache_path, cached,
  cache_size_bytes, cache_mtime_utc, cache_age_days, staleness_window_days, stale, n_systems, n_stars,
  n_planets, n_binaries, n_name_tags, n_alias_keys}` — `cache_mtime_utc` is the local `systems.xml.gz`
  download time (the catalogue snapshot proxy; OEC embeds no version), `stale` flags an age past the 7-day
  window.

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
Output: `{star1_info, star2_info, distance_ly, distance_au}`. Each `*_info` is `{name, ra_deg, dec_deg, ly, sp_type, desig_str, ra_hms, dec_dms}`. `distance_au` is `null` unless the two stars are < 0.5 ly apart. *(`sp_type` is the SIMBAD spectral type — additive, added for the O8 Sol-centered star charts; `""` when SIMBAD has no type, `"G2V"` for the `Sol`/`Sun` special case. Read it defensively — `.get("sp_type", "")`.)*

#### `stars-within-sol`
All stars in the `star_systems` DB table within N light years of Sol. No network call.
```bash
query.py stars-within-sol --ly 15
```
Core function: `calculators.compute_stars_within_distance_of_sol(ly)`
Output: `{limit_ly, count, stars[]}`. Each star: `{"Star Name", "Star Designations", "Spectral Type", "Light Years", app_magnitude, parsecs, x, y, z}` (x/y/z are heliocentric light-year coords, may be `null`; `app_magnitude` = Johnson V, `parsecs` = stored distance — both may be `null`). Sorted ascending by Light Years. *(Phase O F1 added `app_magnitude`/`parsecs` — additive.)* `"Star Designations"` leads with the SIMBAD common name — see **Star designation strings** above.

#### `stars-within-star`
All stars in the `star_systems` DB table within N light years of a named star. Queries SIMBAD for the center star.
```bash
query.py stars-within-star --star "Epsilon Eridani" --ly 5
```
Core function: `calculators.compute_stars_within_distance_of_star(star, ly)`
Output: `{center, center_x, center_y, center_z, limit_ly, count, stars[]}`. Each star: `{"Star Name", "Star Designations", "Spectral Type", "Distance", app_magnitude, parsecs, x, y, z}` (`Distance` in ly from the center star; `app_magnitude` = Johnson V, `parsecs` = `1000/parallax` — both may be `null`). Sorted ascending by Distance. *(Phase O F1 added `app_magnitude`/`parsecs` — additive.)* `"Star Designations"` leads with the SIMBAD common name — see **Star designation strings** above. Rows whose stored `ra`/`dec` cannot be parsed are **skipped** (a blank/short sexagesimal string raises `IndexError`, now caught) rather than aborting the query; `stars-within-sol` instead returns them with `x/y/z = null`.

**A synthetic `Sol` row is included** when the center star lies within `limit_ly` of the origin, so `count` and `stars[]` carry one entry that has no `star_systems` backing. The Sun is not a SIMBAD catalog object, so no catalogue build can ever supply it — yet from any other star Sol is an ordinary neighbour (11.91 ly from τ Ceti). The row is `{"Star Name": "Sol", "Star Designations": "Sun", "Spectral Type": "G2V", app_magnitude: -26.74, parsecs: 4.84813681e-06, x/y/z: 0}` with `Distance` = the center's heliocentric radius. `parsecs` is **1 AU expressed in parsecs**, not a measured distance — it is the value that makes the standard `M = V + 5 − 5·log₁₀(pc)` recovery yield Sol's true M_V of 4.83, so a consumer computing absolute magnitudes needs no special case. A consumer that wants catalogue rows only can filter on `"Star Name" == "Sol"`. Centering *on* Sol excludes it (distance 0 fails the existing `0.001` self-exclusion floor).

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
  or only one star, or a partial numeric set, is a curated `{"error"}` on **stdout, exit 1** (P4.1 — these
  handler-validation cases were previously a stderr/exit-2 message; only argparse's own missing/non-numeric
  errors remain exit 2). A SIMBAD/regions failure on either star is likewise returned as `{"error"}` exit 1.
  `--star` mode adds a SIMBAD network call; the numeric mode stays fully offline.

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
hz_edge="conservative", age_max_gyr=13.8, satellite_density=5.5,
cooling_delay_gyr=0.0, distillation_teff_k=5500.0)`.

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

**Phase AD A0 — ²²Ne distillation cooling pause (WD only).** A neon-rich WD core undergoes
²²Ne distillation that *pauses* cooling for several Gyr, greatly lengthening HZ residence.
`--cooling-delay-gyr Δ` (default **0 = off**, so the whole path is **byte-identical** to the
pre-AD result) freezes the track's (Teff, L, R) at the `--distillation-teff-k` epoch
(default **5500 K** — the 0.6 M☉ DA onset of **Vanderburg, Bédard, Becker & Blouin 2025**,
arXiv:2501.06613 §2, which pins 0.6/0.8/1.0 M☉ onsets at ≈5500/8100/12000 K with ~10/9/6 Gyr
delays) for Δ Gyr, then resumes (later epochs shift +Δ; the integration ceiling extends by Δ).
When Δ>0 every mode's result additionally carries `cooling_delay_gyr`, `distillation_teff_k`,
`pause_teff_k`, `pause_duration_gyr`, `pause_hz_inner_au`, `pause_hz_outer_au`,
`effective_age_max_gyr`, and a pause note appended to `model_note`. **Order-of-magnitude**: the
pause is modelled as a (Teff, L, R) freeze (not a re-solved track), and the realized ~10 Gyr
delay depends strongly on the assumed ²²Ne fraction (~3%), applying only to the ~0.6–2.5%
high-neon WD subset. **Anchors:** 0.6 M☉ peak residence **6.3 Gyr → 16.3 Gyr at Δ=10**
(Vanderburg Table 1: 6.67 → 15.56); a planet inside the frozen pause-HZ band gains ~Δ Gyr of
residence; the long-residence CHZ outer edge moves **outward** (threshold 6 Gyr: 0.0147 →
0.0193 AU; at threshold 8 Gyr standard cooling yields *no* CHZ while the pause creates one).
**Finding (documented):** for a 0.6 M☉ WD standard cooling already yields a ≥3 Gyr CHZ out to
~0.02 AU, so the outward extension appears at *long*-residence thresholds (≥5 Gyr), not at the
plan's "≥3 Gyr" — which is truer to Vanderburg's max-duration framing. **Validation (exit 1):**
`cooling_delay_gyr < 0`; `distillation_teff_k ≤ 0`; a `distillation_teff_k` outside the track's
Teff range for the mass; **`--cooling-delay-gyr > 0` on `--track bd`** (distillation is a WD
mechanism). **Exit 2:** non-numeric `--cooling-delay-gyr`/`--distillation-teff-k`.

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
Core: `thermal.compute_waste_heat(input_power_watts=None, useful_power_watts=None, efficiency=None, hot_temp_k=None, cold_temp_k=None, peak_w=None, mean_w=None, duty=None, pulse_period_s=None, storage_mass_kg=None, specific_heat_jkgk=None)`. Power anchor (`--input-power-watts` | `--useful-power-watts`) is an **argparse mutex group** — no longer `required` (transient mode uses no steady anchor), so both → exit 2, but **neither + not transient → the core "no power anchor" error (exit 1)**. Efficiency anchor: `--efficiency` (0<η≤1) **or** `--hot-temp-k`+`--cold-temp-k` (derives η_carnot). If both an explicit efficiency and reservoir temps are given, device waste-heat uses `--efficiency` and the Carnot floor is reported alongside; `carnot_limited:true` flags a stated η above the Carnot ceiling (physically impossible — flagged, still returned). Output: `{waste_heat_w, useful_power_w, input_power_w, efficiency, carnot_efficiency|null, carnot_min_waste_heat_w|null, carnot_limited|null, hot_temp_k, cold_temp_k, notes, model_note}` (P4.4 adds the `model_note` string summarizing the efficiency-split/Carnot-cap model; no `mode` key — steady-state is otherwise byte-identical to Phase V). **Validation:** non-positive powers; η ∉ (0,1]; `T_hot ≤ T_cold`; incomplete reservoir pair; no efficiency anchor → curated `{"error"}` exit 1. **Anchor:** 3 GW @ η=0.4 → useful 1.2e9 / waste 1.8e9 W; T_hot=1500/T_cold=300 → η_carnot=0.8, claimed η=0.9 → `carnot_limited:true`.
- **Phase AD (C9) — transient / pulsed thermal-buffer mode.** Supplying **any** of `--peak-w --mean-w --duty --pulse-period-s --storage-mass-kg --specific-heat-jkgk` selects transient mode; **all six are required together**. The radiator is sized for the time-average `mean_w`; the excess `peak_w − mean_w` charges a thermal buffer over each on-phase `on_time_s = duty·pulse_period_s` → per-cycle `temp_swing_k = (peak_w−mean_w)·on_time_s/(m·c)` and a ride-through `buffer_time_s = m·c·temp_swing_k/mean_w`. (The plan's formula needs an absolute on-time; `--pulse-period-s` supplies it — a documented clarification of the input set.) Output: `{mode:"transient", peak_power_w, mean_power_w, duty, pulse_period_s, on_time_s, excess_power_w, storage_mass_kg, specific_heat_jkgk, heat_capacity_j_per_k, buffered_energy_j, temp_swing_k, buffer_time_s, notes}`. **Validation:** an incomplete set; `peak_w < mean_w`; `duty ∉ (0,1]`; non-positive `pulse_period_s`/`storage_mass_kg`/`specific_heat_jkgk` → curated `{"error"}` exit 1. Refrigeration/pump work stays packet prose.

#### `radiator-area` (F2)
Radiating **area** (and optional mass) to reject a heat load by Stefan–Boltzmann radiation.
`q = ε·σ·(T_rad⁴ − T_sink⁴)·n_sides` [W/m²], `A = Q/q`; σ = 5.670374419e-8.
```bash
query.py radiator-area --heat-watts 1e9 --radiator-temp-k 300 --emissivity 0.9 --sides 2
query.py radiator-area --input-power-watts 3e9 --efficiency 0.4 --radiator-temp-k 350
```
Core: `thermal.compute_radiator_area(heat_watts=None, input_power_watts=None, efficiency=None, radiator_temp_k=None, emissivity=0.9, sides=2, sink_temp_k=0.0, areal_mass_kgm2=None)`. Heat load: `--heat-watts` **or** the inline F1 chain `--input-power-watts`+`--efficiency` (computes `Q=P_in·(1−η)`). `--radiator-temp-k` required (>0); `--emissivity` default 0.9 (0<ε≤1); `--sides {1,2}` default 2 (a flat panel radiates from both faces); `--sink-temp-k` default 0 (idealized deep space); `--areal-mass-kgm2` optional → `radiator_mass_kg`. Output: `{radiator_area_m2, radiator_area_km2, flux_wm2, blackside_flux_wm2, heat_watts, radiator_temp_k, sink_temp_k, emissivity, sides, radiator_mass_kg|null, areal_mass_kgm2|null, scaling_note, model_note}`. `blackside_flux_wm2 = σ·T_rad⁴` makes the T⁴ dependence legible; `scaling_note` states the A ∝ T⁻⁴ rule, the Carnot coupling, and the `T_sink → T_rad` collapse; P4.4 adds `model_note` (the gray-body σ(T⁴−T_sink⁴) formula + its uniform-temperature/diffuse-gray assumptions). **Validation:** non-positive heat/temp; ε ∉ (0,1]; `sides ∉ {1,2}`; `T_sink ≥ T_rad` (a radiator can't reject below its environment — curated error); `T_sink < 0`; both/neither heat anchor → curated `{"error"}` exit 1. **Anchors (verified):** σT⁴ = 459 W/m² @300 K / 5.67e4 @1000 K (ε=1, 1 side); **1 GW @300 K, ε=0.9, double-sided → ≈1.21×10⁶ m² ≈ 1.21 km²**.

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

### Radiation dose → per-clade biological ceiling (Phase AS / Packet 34 — no network)

#### `radiation-ceiling`
Converts a **physical radiation exposure** to a crew substrate's ("clade") standing on **two
independent biological ceilings at once** — the number the sister repo computes per route × velocity
× clade for its drive-canon dose policy and STL substrate ladder. Pure-math, self-validating,
`query.py`-only; `core/radiation.py` + bundled `core/radiation_tables.py`. **The two axes never
collapse to a scalar** and a clade carries a modifier **pair** `(m_A, m_B)`.
- **Axis A — acute / deterministic (Gy, RBE-weighted):** `D_A = D_absorbed × RBE(LET)` vs a clade
  acute ceiling (`LD50_ref 3.75 Gy × m_A × DMF`). Reports margin, fraction-of-ceiling, and an ARS
  severity band (`none/mild/ars-onset/ld50-region/supralethal`). A **chronic** exposure does **not**
  bind the acute ceiling (§2.1) — Axis A returns `applicable:false` + an optional tissue-reaction-rate
  check.
- **Axis B — stochastic / cancer (Sv, ICRP-Q-weighted):** `H = D_absorbed × Q(LET)` scored against a
  career **REID budget**. REID% scales from the **600 mSv → 3% REID** science anchor (S5); the selected
  budget (`600` default / `1000` mSv) is a **policy** knob, labelled as such. `--ddref` (default 1.0,
  inert; the disputed ~2× is opt-in) reduces chronic stochastic effectiveness.
- **RBE(LET) and Q(LET) are kept distinct** (§1.2): RBE is a bundled order-of-magnitude grid (peak
  ~100–200 keV/µm, high-LET **uncertain** — S8); Q is the ICRP 60/103 relation (`Q=1 L≤10`;
  `0.32L−2.2` 10–100; `300/√L` >100). Equal absorbed Gy of GCR/HZE exhausts the budget faster than
  photons (Q≫1).
- **Clade coupling (§2.3) is lever-tagged.** `--lever repair-fidelity` may improve **both** axes;
  `--lever p53` forces the trade (acute↑ ⇒ cancer↑) and a p53 lever improving both is a **hard block**
  unless `--allow-p53-double-improve` (S15 is abstract-only). `m_A` is **signed** — a lever factor < 1
  lowers the ceiling below baseline (the S14 repair-disorder hypersensitivity, fatal ~3 Gy).
- **`upload` (and the cyborg hardware fraction)** emit **no Gy/Sv** — both biological axes return
  `applicable:false` and a **SEU / bit-error budget** (`upsets = fluence × cross-section × bits` vs an
  ECC margin) is reported, explicitly labelled *a different physical quantity*.
- **Provenance:** every number carries a tag ∈ `{physics-limit, present-datapoint, policy,
  required-breakthrough, extrapolation}` (full `provenance_legend` in the response) — so a consumer sees
  at a glance that **600 mSv is policy**, **LD50 is physics-limit**, **Dsup ×2 is extrapolation**, and
  **upload is required-breakthrough**. A **policy/extrapolation number is never tagged `physics-limit`**
  (MTA discipline): `reid_percent` is `extrapolation` (a linear LNT projection off the policy anchor,
  sharpest at high acute dose where LNT is out of regime), `clade_adjusted_budget_sv` is `policy`
  (= 600 mSv / m_b), and only `q_used` (the ICRP Q factor) among Axis-B numbers is `physics-limit`.
  `--allow-required-breakthrough` is required to emit any Axis-A ceiling beyond the Deinococcus ~5000 Gy
  existence proof; `--pharmacological-dmf` is clamped at 3× (S10).
- **Two clarity notes ride the output** (additive): `axis_a_deterministic.ars_band_note` — the ARS band
  is scored against **absolute baseline photon-equivalent** thresholds, so it can diverge from the
  clade-relative `fraction_of_ceiling` (a radiosensitive clade at 100% of its own lowered ceiling may
  still read a mild band — read the two together); `axis_b_stochastic.ddref_note` (present only when
  `--ddref ≠ 1`) — because the 600 mSv @ 3% REID anchor already embeds low-dose-rate effectiveness,
  `--ddref > 1` makes the reported REID **disagree with the NASA policy pairing** (a deliberate,
  non-policy modeling choice, not "more correct").
```bash
query.py radiation-ceiling --clade baseline-human --profile acute --absorbed-dose-gy 4 --let-kev-um 0.3   # frac ≈ 1.067, ld50-region
query.py radiation-ceiling --clade baseline-human --profile chronic --absorbed-dose-gy 0.6 --let-kev-um 0.3 # REID = 3.0% exactly
query.py radiation-ceiling --absorbed-dose-gy 0.1 --let-kev-um 100    # HZE: Q ≈ 29.8 → REID ≈ 14.9% vs 0.5% for photons
query.py radiation-ceiling --clade gene-mod --absorbed-dose-gy 4 --let-kev-um 0.3   # Dsup: ceiling 7.5 Gy (~2×), tag extrapolation
query.py radiation-ceiling --clade upload --fluence 1e10 --memory-bits 1e12 --ecc-margin 1e6   # SEU path, no Gy/Sv
query.py radiation-ceiling --let-spectrum "0.3:1e9, 100:1e7"   # composite GCR/HZE field (dose-weighted RBE & Q)
```
Core: `radiation.compute_radiation_ceiling(absorbed_dose_gy=None, fluence=None, let_kev_um=None,
particle_type=None, energy_mev_amu=None, let_spectrum=None, profile="acute", dose_rate=None,
dose_rate_unit="gy/day", duration=None, duration_unit="days", clade="baseline-human",
pharmacological_dmf=None, career_budget_policy=None, ddref=None, lever=None, lever_m_a=None,
lever_m_b=None, allow_p53_double_improve=False, allow_required_breakthrough=False,
seu_cross_section_cm2=None, memory_bits=None, ecc_margin=None)`.
- **Output shape.** Top level: `{clade, clade_note, clade_confidence, profile, is_order_of_magnitude,
  model_note, provenance_legend, exposure, axis_a_deterministic, axis_b_stochastic, clade_modifiers,
  seu_budget, flags}`. `axis_a_deterministic{applicable, clade_acute_ceiling_gy, acute_equivalent_dose_gy,
  rbe_used, margin_gy, fraction_of_ceiling, ars_severity_band, ars_band_note, dmf_applied, provenance}`
  (chronic: `{applicable:false, reason, clade_acute_ceiling_gy, tissue_reaction_rate_check, provenance}`);
  `axis_b_stochastic{applicable, career_budget_sv, career_budget_policy, clade_adjusted_budget_sv,
  cumulative_equivalent_dose_sv, q_used, w_r_note, reid_percent, fraction_of_budget, remaining_budget_sv,
  ddref_used, ddref_note, provenance}` (`ddref_note` is `null` at the default DDREF 1.0, the source string
  otherwise); `clade_modifiers{m_a, m_b, levers[], coupling_enforced}`; `seu_budget` (null for
  pure-biological clades; `{applicable, different_physical_quantity:true, fluence_cm2, cross_section_cm2,
  cross_section_is_default, seu_rate_per_bit, memory_bits, expected_upsets, ecc_margin, within_ecc_margin,
  note, confidence, provenance}` for upload/cyborg); `flags{out_of_range_let, required_breakthrough,
  dmf_capped, p53_double_improve_overridden}`; `exposure{absorbed_dose_gy, quality, rbe_effective,
  q_effective, source_form}`. **Provenance tags** (`axis_b.provenance`): `career_budget_policy` +
  `clade_adjusted_budget_sv` = `policy`, `reid_percent` + `ddref_used` = `extrapolation`, `q_used` =
  `physics-limit` (a policy/projection number is never tagged `physics-limit`).
- **Validation:** unknown clade/profile/lever/policy, a fluence with **no** quality (cannot weight),
  both magnitude forms, non-positive dose/LET/DMF/DDREF/dose-rate, a malformed/non-exclusive
  `--let-spectrum`, a blocked p53 double-improve, or an over-5000-Gy ceiling without the RB flag →
  curated `{"error"}` exit 1; a bad `--clade`/`--profile` choice or non-numeric value → argparse exit 2.
- **Order-of-magnitude & scope.** `is_order_of_magnitude:true`. The RBE grid and clade modifiers are
  canon-labelled estimates, not a transport/dose-response simulation. Per §5 the tool does **not** compute
  shielding (→ `shielding-attenuation`), trajectory dose accumulation (→ relativistic `travel-time`/flux +
  `time-dilation`/`lorentz-factor`), a flight Sv/yr magnitude, or a dose→cruise-velocity mapping — it
  converts a *given* exposure. Anchors, the RBE/Q sources, and the clade ladder are pinned in
  `core/radiation_tables.py` (Packet-34 S-citations).

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
transcription slips in `completed_plans/PHASE_AD_PLAN.md`:* the plan's "1.9×10² J / 40 mg" figures were computed at
`v = c`, not β 0.1; and its `E/4.184e12` divisor yields **kilotons**, not kg (the kg divisor is
`4.184×10⁶ J`). The relativistic auto-switch is `β > 0.1` (the plan prose said ~0.01, but its own
acceptance cases require `false@β0.05` / `true@β0.2`).

### Arrival geometry & gravitation (Phase AE — Group K, no network)

Four `query.py`-only, pure-math, self-validating (Phase-H/P contract) gravitational-geometry calculators
(`core/gravitation.py`) for Packet 20's arrival/departure energetics — closing the escape-velocity /
well-depth / Laplace-SOI / hyperbolic-capture gap over the existing `gravity-*`/`hill-sphere`/`roche-limit`
set. Closed-form on fundamental constants; curated `{"error"}` exit 1, argparse exit 2, `model_note` on
every object. Masses/radii resolve through the shared **`core/astro_bodies.py`** multi-unit gate + presets
(`--body`/`--primary`/`--object` share one body table across Groups K–O; every constant is flag-overridable
in `core/equations.py`). All four functions accept mass in **exactly one** of `--mass-kg`/`--mass-msun`/
`--mass-mearth`/`--mass-mjup` (or a `--body` preset that fills mass — and, for K1/K4, radius).

#### `escape-velocity` (K1)
`v_esc = √(2GM/r)`, `v_circ = v_esc/√2`, specific escape energy `½v_esc²`.
```bash
query.py escape-velocity --body earth                       # 11.19 km/s
query.py escape-velocity --mass-msun 1 --radius-rsun 1      # 617.7 km/s
```
Core: `gravitation.compute_escape_velocity(mass_*, radius_m|radius_rsun|radius_rearth|distance_au, body)`.
Radius via exactly one of `--radius-m`/`--radius-rsun`/`--radius-rearth`/`--distance-au`, or a `--body`
preset. Output: `{escape_velocity_kms, escape_velocity_c, circular_velocity_kms, specific_energy_j_per_kg,
mass_kg, radius_m, body|null, model_note}`. **Validation:** not exactly one mass/radius unit, `--body` +
explicit flags together, or non-positive → curated exit 1; bad `--body` choice / non-numeric → exit 2.
**Anchors:** Earth → **11.19 km/s**; Sun → **617.7 km/s**; Jupiter (1-bar equatorial R) → **59.5 km/s**;
Earth specific energy ≈ **6.26×10⁷ J/kg**.

#### `gravitational-potential` (K2)
`Φ = −GM/r`; well-depth `r_from→r_to` = `GM(1/r_from − 1/r_to)` (default `r_to = ∞`); binding energy =
`payload · well_depth`; Δv-equivalent = `√(2·|well_depth|)`.
```bash
query.py gravitational-potential --body earth --r-from-m 6.371e6                # well 6.26e7 J/kg, Δv 11.19
query.py gravitational-potential --body sun --r-from-m 6.957e8 --payload-kg 1000
```
Core: `gravitation.compute_gravitational_potential(mass_*, body, r_from_m|r_from_au, r_to_m|r_to_au,
payload_kg)`. `--r-from-*` required (exactly one unit); `--r-to-*` optional (default ∞). Output:
`{potential_j_per_kg, well_depth_j_per_kg, binding_energy_j|null, delta_v_kms, r_from_m, r_to_m|null,
mass_kg, body|null, model_note}`. **Validation:** missing/duplicate r-from unit, non-positive payload, mass
gate → exit 1. **Anchors:** Earth surface→∞ = **6.26×10⁷ J/kg** (= K1 ½v_esc²); Sun surface→∞ =
**1.91×10¹¹ J/kg**.

#### `sphere-of-influence` (K3)
Laplace `r_SOI = a·(m/M)^(2/5)`, reported beside Hill `r_Hill = a·(m/3M)^(1/3)`.
```bash
query.py sphere-of-influence --body-mass-mearth 1 --primary sun --semimajor-au 1     # SOI 0.00618 AU
query.py sphere-of-influence --body-mass-mjup 1 --primary-mass-msun 1 --semimajor-au 5.2
```
Core: `gravitation.compute_sphere_of_influence(body_mass_*, primary_mass_*, primary, semimajor_au)`. Body
mass via `--body-mass-*` (no preset); primary mass via `--primary-mass-*` or a `--primary` body preset.
Output: `{soi_laplace_au, soi_laplace_km, hill_radius_au, hill_radius_km, ratio_soi_hill, body_mass_kg,
primary_mass_kg, primary|null, semimajor_au, model_note}`. **Validation:** either mass gate, non-positive
`--semimajor-au` → exit 1. **Anchors:** Earth about Sun → SOI ≈ **0.924×10⁶ km (0.00618 AU)**, Hill ≈
1.50×10⁶ km; Jupiter → SOI ≈ **4.82×10⁷ km**.

#### `hyperbolic-approach` (K4)
At periapsis `r_p`: `v_p = √(v∞² + 2GM/r_p)`, `C₃ = v∞²`, capture Δv = `v_p − v_capture` (circular
`√(GM/r_p)` | parabolic `√(2GM/r_p)` | elliptical vis-viva with `--target-apoapsis-*`).
```bash
query.py hyperbolic-approach --body earth --v-infinity-kms 3 --periapsis-km 6771   # v_p 11.26, capture Δv 3.59
query.py hyperbolic-approach --body earth --arrival-speed-kms 11.2 --r-from-km 1e6 --periapsis-rbody 1.06 --target elliptical --target-apoapsis-km 100000
```
Core: `gravitation.compute_hyperbolic_approach(mass_*, body, v_infinity_kms|arrival_speed_kms(+r_from_km|
r_from_au), periapsis_km|periapsis_rbody, target, target_apoapsis_km|target_apoapsis_au)`. Provide **exactly
one** v-mode (direct `--v-infinity-kms`, or `--arrival-speed-kms` + `--r-from-*`) and **exactly one**
periapsis (`--periapsis-km`, or `--periapsis-rbody` which needs a known body radius via `--body`). `--target`
∈ `{circular(default),parabolic,elliptical}`; elliptical requires `--target-apoapsis-*`. Output:
`{v_periapsis_kms, capture_delta_v_kms, c3_km2s2, v_infinity_kms, periapsis_km, target, mass_kg, body|null,
model_note}`. **Validation:** v-mode/periapsis not exactly one, `--periapsis-rbody` without a radius, an
arrival speed at/below escape at `--r-from` (bound, not hyperbolic), missing/too-small elliptical apoapsis →
exit 1; bad `--target` choice / non-numeric → exit 2. **Anchor:** v∞ = 3 km/s at Earth, periapsis = 6771 km
→ v_p ≈ **11.26 km/s**, capture-to-circular Δv ≈ **3.59 km/s**.

### Special relativity & causality (Phase AF — Group L, no network)

Eight `query.py`-only, pure-math, self-validating (Phase-H/P contract) calculators (`core/relativity.py`)
for Packet 23 — the full special-relativity toolkit plus the load-bearing `causality-check` FTL guardrail.
Extends the `lorentz-factor` (γ) seed. Curated `{"error"}` exit 1, argparse exit 2, `model_note` on every
object; constants from `core/equations.py`; L1's gravitational source resolves through `core/astro_bodies.py`.
Velocity inputs take **exactly one** of `--velocity-c` / `--velocity-kms` (0 ≤ β < 1) throughout.

#### `time-dilation` (L1)
Special `Δt = γΔτ`; gravitational `Δτ/Δt = √(1 − r_s/r)` (`r_s = 2GM/c²`); optional `--combined` product
`γ/√(1 − r_s/r)`. `--proper-time` **or** `--coordinate-time` solves the other; gravitational source via
`--body` or `--mass-* + --radius-*`/`--distance-au`.
```bash
query.py time-dilation --velocity-c 0.866 --proper-time 1     # γ 2.0, coordinate_time 2.0
query.py time-dilation --body earth                           # gravitational_factor ≈ 1 − 6.95e-10
```
Core: `relativity.compute_time_dilation(velocity_c|velocity_kms, proper_time, coordinate_time, mass_*|body,
radius_*|distance_au, combined)`. Output: `{gamma, dilation_factor, proper_time, coordinate_time,
gravitational_factor|null, combined_factor|null, model_note}`. **Validation:** neither velocity nor gravity,
β≥1, `--combined` without both, both times, radius ≤ r_s → exit 1. **Anchors:** β=0.866 → γ=**2.000**;
β=0.99 → γ≈**7.089**; Earth surface gravitational factor ≈ **1 − 6.95×10⁻¹⁰**.

#### `length-contraction` (L2)
`L = L₀/γ`; `--proper-length` or `--contracted-length` solves the other. Output: `{gamma, proper_length,
contracted_length, contraction_factor, model_note}`. **Anchor:** β=0.866 → L = **0.5 L₀**.

#### `velocity-addition` (L3)
Collinear `w = (u+v)/(1+uv/c²)`; `--perpendicular` → `w = √(v² + u²(1−v²))`. Required `--u-c`, `--v-c`
(−1 ≤ β ≤ 1). Output: `{combined_velocity_c, combined_velocity_kms, gamma_combined|null, model_note}`
(`gamma_combined` null at exactly c). **Anchors:** 0.75c ⊕ 0.75c = **0.96c**; c ⊕ anything = **c**.

#### `relativistic-doppler` (L4)
`f_obs/f_src = 1/(γ(1 − β cosθ))` via exactly one of `--approach` (θ=0) / `--recede` (180°) / `--angle-deg`;
optional `--rest-wavelength-nm` or `--rest-frequency-hz`. Output: `{doppler_factor, angle_deg,
observed_wavelength_nm|null, observed_frequency_hz|null, redshift_z, model_note}`. **Anchors:** β=0.6 approach
→ factor **2.0** (z=**−0.5**); transverse (90°) → **0.8**.

#### `rapidity` (L5)
`φ = artanh(β)`, `β = tanh(φ)`, `γ = cosh(φ)`; exactly one of `--velocity-c` / `--rapidity` / `--add`
(comma-separated β list → `tanh(Σ artanh(βᵢ))`). Output: `{rapidity, velocity_c, gamma,
composed_velocity_c|null, model_note}`. **Anchors:** β=0.6 → φ≈**0.6931**; `--add "0.6,0.6,0.6"` → φ=**2.079**,
composed ≈ **0.9695c**.

#### `relativistic-energy-momentum` (L6)
`E = γmc²`, `p = γmv`, `KE = (γ−1)mc²`, `E² = (pc)² + (mc²)²`. Mass via exactly one of `--mass-kg` /
`--mass-mev`; state via exactly one of `--velocity-c` / `--gamma` / `--kinetic-energy-j` / `--momentum`.
Output: `{gamma, total_energy_j, rest_energy_j, kinetic_energy_j, momentum_kgms, velocity_c, mass_kg,
model_note}`. **Anchor:** proton (938.272 MeV) at β=0.99 → γ≈**7.089**, KE ≈ **5.72 GeV**.

#### `lorentz-transform` (L7)
`t' = γ(t − vx/c²)`, `x' = γ(x − vt)`; `--inverse`; `--event2 "t2,x2"` → simultaneity offset. Event in SI
(`--t` s, `--x` m) **or** astro (`--t-yr`, `--x-ly`, c = 1 ly/yr); required `--velocity-c`. Output:
`{t_prime, x_prime, gamma, simultaneity_offset|null, model_note}`. **Validation:** β≥1, incomplete/mixed-unit
event, partial `--event2` → exit 1. **Anchor:** β=0.6, event (t=0, x=1 ly) → t' = **−0.75 yr**, x' = **1.25 ly**.

#### `causality-check` (L8) ⭐
FTL tachyonic-antitelephone guardrail: a closed causal loop is possible when `u·v > c²`; `v_crit = c²/u`;
a universal `--preferred-frame` removes it. Signal speed via exactly one of `--signal-speed-c` / `--instant`
(u → ∞); required `--frame-velocity-c` (0 ≤ β < 1); optional `--two-jump` framing.
```bash
query.py causality-check --signal-speed-c 2 --frame-velocity-c 0.6   # loop_possible true, v_crit 0.5
query.py causality-check --instant --frame-velocity-c 0.01           # loop_possible true (any v>0)
```
Core: `relativity.compute_causality_check(signal_speed_c|instant, frame_velocity_c, preferred_frame,
two_jump)`. Output: `{loop_possible, condition_value|null, critical_frame_velocity_c, margin|null,
preferred_frame_safe, signal_speed_c|null, frame_velocity_c, instant, explanation, model_note}` (`--instant`
→ `condition_value`/`margin` null, `v_crit` 0). **Anchors:** u=2c, v=0.6c → `u·v/c²`=**1.2** → loop **true**,
v_crit **0.5c**; u=2c, v=0.4c → **0.8** → false; `--preferred-frame` → `preferred_frame_safe` **true**
regardless. A `loop_possible=false` verdict is a clean result (exit 0), not an error.

### Exotic vacuum & cosmology (Phase AG — Group M, no network)

Four `query.py`-only, pure-math, self-validating (Phase-H/P contract) calculators (`core/exotic_physics.py`)
for Packet 21 — vacuum/negative energy, the vacuum catastrophe, the pair-production threshold, and the
expansion-vs-binding accounting. Closed-form on fundamental constants; curated `{"error"}` exit 1, argparse
exit 2, `model_note` on every object; cosmology constants (H₀, Ω_Λ, Ω_m) flag-overridable from
`core/equations.py`.

#### `casimir` (M1)
Parallel-plate `P = π²ℏc/(240 d⁴)`, energy density `u = −π²ℏc/(720 d³)` (the negative, NEC-relevant quantity
feeding Group N); `--geometry sphere-plate` gives the proximity-force `F = −π³ℏcR/(360 d³)`.
```bash
query.py casimir --separation-nm 1000                                      # P 1.30e-3 Pa, u −4.33e-10 J/m³
query.py casimir --separation-nm 100 --geometry sphere-plate --sphere-radius-m 1e-4
```
Core: `exotic_physics.compute_casimir(separation_m|separation_nm, area_m2, geometry, sphere_radius_m)`.
Separation via exactly one unit; `--area-m2` default 1. Output: `{pressure_pa, force_n, energy_density_j_m3,
total_energy_j, separation_m, area_m2, geometry, sphere_radius_m, model_note}` (sphere-plate → pressure /
energy-density `null`, force only). **Validation:** no/duplicate separation, non-positive, `--sphere-radius-m`
with parallel-plate, sphere-plate without radius → exit 1. **Anchors:** d=1 µm → P ≈ **1.30×10⁻³ Pa**, u ≈
**−4.33×10⁻¹⁰ J/m³**; d=10 nm → P ≈ **1.30×10⁵ Pa** (∝ 1/d⁴).

#### `vacuum-energy` (M2)
`ρ_Λ = Ω_Λ·ρ_crit` (`ρ_crit = 3H₀²c²/8πG`), `Λ = 3Ω_ΛH₀²/c²`, `w = −1`; the QED cutoff estimate
`ρ_vac ~ E_cutoff⁴/(ℏc)³` and the catastrophe ratio.
```bash
query.py vacuum-energy                              # ρ_Λ 5.3e-10, ρ_crit 7.7e-10 J/m³, ratio ~1e122
query.py vacuum-energy --cutoff electroweak
```
Core: `exotic_physics.compute_vacuum_energy(omega_lambda, hubble_kms_mpc, cutoff)`. `--cutoff` ∈
`{planck(default), electroweak, qcd}` or a number in GeV. Output: `{rho_lambda_j_m3, rho_crit_j_m3,
lambda_m2, equation_of_state_w, cutoff, qed_estimate_j_m3, catastrophe_ratio, omega_lambda, hubble_kms_mpc,
model_note}`. **Validation:** `Ω_Λ ∉ (0,1]`, `H₀ ≤ 0`, unparseable cutoff → exit 1. **Anchors:** default →
ρ_Λ ≈ **5.3×10⁻¹⁰**, ρ_crit ≈ **7.7×10⁻¹⁰ J/m³**, Λ ≈ 1.09×10⁻⁵² m⁻², Planck-cutoff ratio ~**10¹²²**.

#### `schwinger-limit` (M3)
`E_c = m_e²c³/(eℏ)`, `B_c = E_c/c`, `I_c = ½ε₀cE_c²`; optional `--field-vm` or `--intensity-wcm2` → ratio to
critical. Output: `{critical_field_vm, critical_magnetic_field_t, critical_intensity_wcm2, ratio_to_critical
|null, model_note}`. **Validation:** both compare-flags together, non-positive → exit 1. **Anchors:** E_c ≈
**1.32×10¹⁸ V/m**, B_c ≈ **4.41×10⁹ T**, I_c ≈ **2.3×10²⁹ W/cm²** (½ε₀cE² convention; `model_note` flags the
~4.6×10²⁹ no-½ convention).

#### `hubble-flow` (M4)
Recession `v = H₀·d`, or the local-binding turnaround test `r_ta = (GM/(Ω_ΛH₀²))^(1/3)`, `binding_ratio =
(r_ta/r)³`.
```bash
query.py hubble-flow --distance-mpc 100                          # v ≈ 6740 km/s
query.py hubble-flow --mass-msun 3e12 --radius-mpc 1            # Local Group → bound, r_ta ≈ 1.6 Mpc
```
Core: `exotic_physics.compute_hubble_flow(distance_mpc|distance_ly, mass_msun + radius_ly|radius_mpc,
hubble_kms_mpc, omega_lambda, omega_m)`. Provide **either** a recession distance **or** a binding test (mass +
radius), not both. Output: `{recession_velocity_kms|null, recession_fraction_c|null, binding_ratio|null,
turnaround_radius_mpc|null, bound|null, hubble_kms_mpc, omega_lambda, omega_m, model_note}` (+ the echoed
distance/mass/radius). **Validation:** both/neither mode, missing radius in binding mode, duplicate distance/
radius unit, non-positive → exit 1. **Anchors:** d=100 Mpc → v ≈ **6740 km/s**; Local Group (3×10¹² M☉, 1 Mpc)
→ **bound**, r_ta ≈ **1.6 Mpc**; a 10¹¹ M☉ galaxy at 10 kpc → binding_ratio ≫ 1 (bound). A `bound=false`
verdict is a clean result, not an error.

### Black holes & relativistic thermodynamics (Phase AI — Group O, no network)

Ten `query.py`-only, pure-math, self-validating (Phase-H/P contract) calculators (`core/black_hole.py`) for
Packet 24 — the horizon / Hawking-thermodynamics / accretion toolkit. Closed-form on fundamental constants;
curated `{"error"}` exit 1, argparse exit 2, `model_note` on every object. Mass resolves through
`core/astro_bodies.py` (multi-unit `--mass-kg`/`--mass-msun`/`--mass-mearth`/`--mass-mjup` or an `--object`
preset: `sun`, `earth`, `cygnus-x1`, `sgr-a-star`, `m87-star`, `ton-618`).

#### `schwarzschild-radius` (O1)
`r_s = 2GM/c²`. Output: `{schwarzschild_radius_m, schwarzschild_radius_km, schwarzschild_radius_au, mass_kg,
object|null, model_note}`. **Anchors:** Sun → **2.953 km**; Earth → 8.87 mm; Sgr A* → **0.082 AU**.

#### `hawking-temperature` (O2)
`T_H = ℏc³/(8πGMk_B)`, or the inverse `--temperature-k` → mass. Output: `{hawking_temperature_k, mass_kg,
mass_msun, object|null, model_note}`. **Anchors:** 1 M☉ → **6.17×10⁻⁸ K**; T=2.725 K → M ≈ **4.5×10²² kg**.

#### `black-hole-evaporation` (O3)
`P = ℏc⁶/(15360πG²M²)`, `τ = 5120πG²M³/(ℏc⁴)`, or the inverse `--lifetime-yr` → mass. Output: `{power_w,
lifetime_s, lifetime_yr, mass_kg, object|null, model_note}`. **Anchors:** 1 M☉ → τ ≈ **2.1×10⁶⁷ yr**, P ≈
9.0×10⁻²⁹ W; M ≈ **1.7×10¹¹ kg** → τ ≈ age of universe (photon-only 5120π coefficient — stated in
`model_note`).

#### `bekenstein-hawking-entropy` (O4)
`S = k_B·A/(4l_p²)`, `A = 4πr_s²`; mass **or** `--radius-m`. Output: `{entropy_j_per_k, entropy_over_kb,
horizon_area_m2, schwarzschild_radius_m, mass_kg|null, model_note}`. **Anchor:** 1 M☉ → S/k_B ≈ **1.05×10⁷⁷**.

#### `isco` (O5)
Schwarzschild `r_ISCO = 6GM/c² = 3r_s`; Kerr via Bardeen-Press-Teukolsky. `--spin` (a*, −1…1, default 0),
`--retrograde` (default prograde). Output: `{isco_radius_m, isco_radius_rs, orbital_velocity_c|null,
binding_efficiency, spin, prograde, mass_kg, object|null, model_note}` (`orbital_velocity_c` = 0.5c for a*=0,
null for spin≠0). **Anchors:** Schwarzschild → r_ISCO ≈ **8.86 km**, efficiency **5.72%**; extremal Kerr
prograde → efficiency **42.3%** (retrograde 3.8%).

#### `kerr-horizon` (O6)
`r± = (GM/c²)(1 ± √(1−a*²))`, equatorial ergosphere `r_E = 2GM/c²`. `--spin`. Output: `{outer_horizon_m,
inner_horizon_m, ergosphere_equatorial_m, extremal, spin, mass_kg, object|null, frame_dragging_note,
model_note}`. **Anchors:** a*=0 → r₊ = r_s; a*=1 → r₊ = GM/c² (half r_s), ergosphere = 2GM/c².

#### `bh-tidal-force` (O7)
`Δa = 2GM·Δr/r³` (at the horizon `Δr·c⁶/(4G²M²)`); `--distance-m`/`--distance-rs` (default = horizon),
`--object-length-m` (Δr, default 1.8), `--threshold-g` → spaghettification radius. Output:
`{tidal_acceleration_ms2, tidal_gees, distance_m, schwarzschild_radius_m, object_length_m,
spaghettification_radius_m|null, inside_horizon|null, mass_kg, object|null, model_note}`. **Anchors:** 10 M☉
horizon, 1.8 m body → ≈ **2×10⁷ g**; 10⁸ M☉ SMBH horizon → ≈ **2×10⁻⁷ g** (spaghettification radius inside
the horizon → `inside_horizon=true`).

#### `eddington-luminosity` (O8)
`L_Edd = 4πGM m_p c/σ_T`, `Ṁ_Edd = L_Edd/(ηc²)`; `--efficiency` (η, default 0.1). Output:
`{eddington_luminosity_w, eddington_luminosity_lsun, eddington_accretion_rate_kg_s,
eddington_accretion_msun_yr, efficiency, mass_kg, object|null, model_note}`. **Anchor:** 1 M☉ → L_Edd ≈
**1.26×10³¹ W** (≈3.3×10⁴ L☉), Ṁ ≈ **1.4×10¹⁵ kg/s** at η=0.1.

#### `unruh-temperature` (O9)
`T_U = ℏa/(2πck_B)`; exactly one of `--acceleration-ms2` / `--acceleration-g` / `--temperature-k` (inverse).
Output: `{unruh_temperature_k, acceleration_ms2, acceleration_g, model_note}`. **Anchors:** a=2.47×10²⁰ m/s²
→ ≈ **1 K**; 1 g → ≈ **4.0×10⁻²⁰ K**.

#### `bekenstein-bound` (O10)
`S ≤ 2πk_B RE/(ℏc)`, `I ≤ 2πRE/(ℏc·ln2)` bits; required `--radius-m` + exactly one of `--energy-j` /
`--mass-kg`. Output: `{max_entropy_j_per_k, max_entropy_over_kb, max_information_bits, radius_m, energy_j,
model_note}`. **Anchors:** 1 kg, 0.1 m → I ≈ **2.58×10⁴² bits**; human (70 kg, 1 m) → ≈ **1.80×10⁴⁵ bits**.

### Alcubierre / metric drive (Phase AH — Group N, no network)

`query.py`-only, pure-math, self-validating (Phase-H/P contract) calculators (`core/warp.py`) for Packet 22 —
the warp-bubble negative-energy budget. **These compute real general relativity; whether the setting's drive
uses these mechanisms is the packet's job and is not asserted by the tool** (the physics/canon separation).
Curated `{"error"}` exit 1, argparse exit 2, `model_note` on every object. No numpy (the N1 integral is
plain-Python Simpson — keeps query.py's cold start ~0.1 s).

#### `alcubierre-energy` (N1)
The `original` (Alcubierre 1994) formulation is **computed** from the T⁰⁰ integral `E = −(c²v_s²/12G)·∫₀^∞
(df/dr_s)² r_s² dr_s` **joules** over the tanh shape function (always negative → exotic matter; `E ∝ −v_s²·R²/Δ`;
`energy_kg_equiv = energy_j / c²`). The six
**reduction formulations report** their published literature results + energy-condition status (not
first-principles recomputations of each modified metric).
```bash
query.py alcubierre-energy --bubble-radius-m 100 --velocity-c 1 --wall-thickness-m 10          # energy_j −3.37e45 J (−3.75e28 kg-equiv)
query.py alcubierre-energy --bubble-radius-m 10 --velocity-c 10 --wall-thickness-m 1 --formulation white
query.py alcubierre-energy --bubble-radius-m 100 --velocity-c 0.5 --wall-thickness-m 10 --formulation bobrick-martire
```
Core: `warp.compute_alcubierre_energy(bubble_radius_m, velocity_c, wall_thickness_m, formulation, neck_radius_m)`.
`--formulation` ∈ `{original(default), van-den-broeck, krasnikov, white, bobrick-martire, physical-2024,
lentz}`. Output: `{energy_j, energy_kg_equiv, formulation, bubble_radius_m, velocity_c, wall_thickness_m,
subluminal, energy_condition_status, published_figure|null, positive_energy_j|null, contested, source,
integration_points|null, resolution_capped|null, model_note}`. For `original`, `energy_j`/`energy_kg_equiv`
are the numeric integral (+ `integration_points`, `resolution_capped`) and `published_figure` is null; for the
reductions, `energy_j`/`energy_kg_equiv` are null and `published_figure` carries the literature string.
**Energy-condition regime flag (Santiago–Schuster–Visser 2021):** any superluminal (v_s ≥ c) →
`energy_condition_status="NEC-violating-exotic"` regardless of formulation; subluminal (v_s < c) with a
positive-energy framework (`bobrick-martire`/`physical-2024`) → `"positive-energy-possible"`. **Validation:**
non-positive radius/velocity/wall, unknown formulation → exit 1; bad `--formulation` choice / non-numeric →
exit 2. **Anchors:** R=100 m, v_s=c, Δ=10 m → |E| ≈ **3.37×10⁴⁵ J** (≈ 3.75×10²⁸ kg-equiv; ∝1/Δ: Δ=1 m →
3.36×10⁴⁶ J ≈ 3.74×10²⁹ kg ≈ **0.19 M☉**, matching Pfenning–Ford ~¼ M☉);
`van-den-broeck` → ~a few M☉; `krasnikov` → ~a few mg; `white` → ~700 kg (Voyager, contested);
`bobrick-martire`/`physical-2024` subluminal → positive-energy; `lentz` → contested.

#### `warp-metric` (N2)
The geometry of the Alcubierre metric: shape function `f(r_s) = [tanh(σ(r_s+R)) − tanh(σ(r_s−R))]/[2 tanh(σR)]`
(≈1 inside, ≈0 outside), expansion scalar `θ = v_s·(x_s/r_s)·(df/dr_s)` (on the forward axis: <0 = contraction
ahead, mirrored by expansion behind), and the wall region (the 10–90% f-transition, ±artanh(0.8)/σ about R).
`--variant natario` (Natário 2002) is the zero-expansion metric — space slides around the ship, θ ≡ 0.
```bash
query.py warp-metric --bubble-radius-m 100 --wall-thickness-sigma 0.1 --velocity-c 1 --r-eval-m 100
query.py warp-metric --bubble-radius-m 100 --wall-thickness-sigma 0.1 --velocity-c 1 --profile
query.py warp-metric --bubble-radius-m 100 --wall-thickness-sigma 0.1 --velocity-c 1 --r-eval-m 100 --variant natario
```
Core: `warp.compute_warp_metric(bubble_radius_m, wall_thickness_sigma, velocity_c, r_eval_m, profile,
variant)`. Optional `--r-eval-m` (evaluate f/df/θ at a radius) and `--profile` (sample across r_s). Output:
`{f_at_r|null, df_dr_at_r|null, theta_at_r|null, wall_inner_m, wall_outer_m, max_expansion, max_contraction,
profile[]|null, bubble_radius_m, wall_thickness_sigma, velocity_c, variant, model_note}` (θ in s⁻¹; natário →
θ / max_expansion / max_contraction all 0). **Validation:** non-positive radius/σ/velocity, negative
`--r-eval-m`, bad `--variant` → exit 1/2. **Anchors:** f(0) ≈ 1 (flat interior), f(≫R) ≈ 0 (flat exterior);
θ antisymmetric front/back (contraction ahead, equal expansion behind); `natario` → θ = 0.

### Planet formation (Phase AJ — Group P, no network)

Six `query.py`-only, pure-math, self-validating (Phase-H/P contract) planet-formation calculators
(`core/formation.py`) for Packet 3.5 — the disk-model + isolation / pebble-isolation / gap-opening /
Toomre-Q / critical-core-mass spine the generator's `mass_by_zone` / `spacing_ratio` / `origin_priors` are
derived from (nothing computed formation surface densities, masses, or instability thresholds before this
group). Closed-form on the F1–F6 claim-map pins; curated `{"error"}` exit 1, argparse exit 2, `model_note`
on every object; every bundled coefficient flag-overridable (constants in `core/equations.py`; new
`_MU_GAS_DEFAULT = 2.34`, `_Z_SUN = 0.0134`). Numpy-free — P4's root find is a pure-Python bisection.

**The calculators chain.** `disk-model` emits `sigma_solid_gcm2`, `temp_k`, and `aspect_ratio_hr` at a
radius; those feed `isolation-mass` (Σ_p), `pebble-isolation-mass`/`gap-opening-mass` (H/r), and `toomre-q`
(Σ, T). Each linking quantity is also a **direct flag**, so every tool stands alone.

#### `disk-model` (P1) ⭐
MMSN-scalable `Σ_gas(r) = Σ₀·(M_disk/M_MMSN)·(r/AU)^p`, `T(r) = T₀·(L★/L⊙)^¼·(r/AU)^q`,
`Σ_solid = Z·f_ice·Σ_gas`, `H/r = c_s/v_K`. **Defaults reproduce the Approved-Canon MMSN exactly**
(Σ₀=1700 g/cm², p=−3/2; T₀=280 K, q=−1/2). Snow line solved from **this** T-law at `--snowline-temp-k`
(default 170 K → 2.71 AU at L=1, ∝ L^½) — **no `ice-lines` import** (followup-1 Ruling 2 / Option A).
```bash
query.py disk-model --r-au 1.0                       # Σ_gas 1700, T 280, H/r 0.0334, Σ_solid 22.78
query.py disk-model --r-grid 1 30 40 --feh 0.2 --ms-luminosity --mstar-msun 1.2
```
Core: `formation.compute_disk_model(r_au|r_grid, mstar_msun, disk_mass_mmsn|disk_mass_msun,
lstar_lsun|ms_luminosity, feh|z, snowline_au, snowline_temp_k, ice_factor, mu, sigma0, sigma_slope, temp0,
temp_slope)`. Provide **exactly one** of `--r-au` / `--r-grid LO HI N` (log-spaced); at most one of each
either/or pair. Output (per radius): `{r_au, sigma_gas_gcm2, sigma_solid_gcm2, temp_k, sound_speed_ms,
aspect_ratio_hr, scale_height_au, omega_per_s, kepler_velocity_kms, interior_to_snowline, disk_mass_mmsn,
metallicity_z, snowline_au, model_note}`; `--r-grid` → `{radii:[…], disk_mass_mmsn, metallicity_z,
snowline_au, mstar_msun, lstar_lsun, model_note}` — each `radii[]` element carries the per-radius keys
through `interior_to_snowline` only (the disk-wide `disk_mass_mmsn`/`metallicity_z`/`snowline_au`/`model_note`
are hoisted to the top level, not repeated per row). **Σ_solid convention:** the default emits the Z_⊙-scaled
**22.8 g/cm²** at 1 AU; the **10 g/cm²** planetesimal convention the isolation anchors use is a lower MMSN
variant recovered via `--z`/`--ice-factor`. **Validation:** neither/both radius mode, non-positive
radius/M★/μ/ice-factor/snow-temp, both metallicity/disk-mass/luminosity modes, bad grid (HI≤LO, N<2) → exit
1; non-numeric → exit 2. **Anchors:** 1 AU → Σ_gas **1700**, T **280**, H/r **0.0334**, Σ_solid **22.78**;
5.2 AU → **143.4 g/cm²**, **122.8 K**; snow line **2.71 AU** (L=4 → 5.43, L=0.1 → 0.858).

#### `isolation-mass` (P2) ⭐
Oligarchic `M_iso = (8/√3)·π^{3/2}·C^{3/2}·M★^{−1/2}·Σ_p^{3/2}·a³` (Armitage Eq. 201).
```bash
query.py isolation-mass --sigma-p-gcm2 10 --a-au 1     # 0.066 M⊕ (terrestrial)
query.py isolation-mass --sigma-p-gcm2 10 --a-au 5.2   # 9.27 M⊕ (Jupiter-core)
```
Core: `formation.compute_isolation_mass(sigma_p_gcm2, a_au, mstar_msun, feeding_zone_c|feeding_zone_b)`.
`--feeding-zone-c` = Armitage single-Hill half-width (default 2√3≈3.464); `--feeding-zone-b` = Kokubo & Ida
oligarchic full width in **mutual** Hill radii (C = b/(2·2^{1/3})). Output: `{isolation_mass_mearth,
isolation_mass_mjup, feeding_zone_width_hill, convention ("half-width-C"|"full-width-b"), sigma_p_gcm2, a_au,
mstar_msun, model_note}`. **Validation:** non-positive Σ_p/a/M★, both conventions → exit 1. **Anchors:**
0.066 M⊕ (a=1, Σ_p=10) / 9.27 M⊕ (a=5.2); scaling ∝ Σ_p^{3/2}·a³·M★^{−1/2}.

#### `pebble-isolation-mass` (P3)
`M_iso,peb = 25·f_fit·(H/r/0.05)³ M⊕`, `f_fit = 0.34·(log(0.001)/log(α))⁴ + 0.66` (Bitsch 2018); `--simple`
→ Lambrechts `20·(H/r/0.05)³` (f_fit=1). The super-Earth ↔ giant switch.
```bash
query.py pebble-isolation-mass --hr 0.05               # 25 M⊕ (α=1e-3 → f_fit 1)
query.py pebble-isolation-mass --temp-k 150 --mstar-msun 1 --a-au 5 --alpha 5e-3
```
Core: `formation.compute_pebble_isolation_mass(hr | (temp_k,mstar_msun,a_au), alpha, simple, dlnp_dlnr,
peb_norm, mu)`. H/r via `--hr` **or** derived from `--temp-k --mstar-msun --a-au` (exactly one mode). Output:
`{pebble_isolation_mass_mearth, hr, alpha, f_fit, dlnp_dlnr, mode ("bitsch2018"|"lambrechts2014"),
model_note}`. **Validation:** no/both H/r mode, incomplete derive, non-positive hr/α → exit 1. **Anchors:**
H/r=0.05 → **25** (bitsch) / **20** (`--simple`); H/r=0.03 → **5.4**. Higher α → higher mass (f_fit↑).

#### `gap-opening-mass` (P4)
Root-finds the **marginal-threshold** q where Crida (2006) Eq. 15 `P(q) = 3H/(4R_H) + 50/(qR) = --p-target`
(default 1.0); `M_gap = q·M★`. Headline = the solved threshold (followup-1 Ruling 1a).
```bash
query.py gap-opening-mass --hr 0.05 --nu-code 3.162e-6 --mstar-msun 1 --a-au 5.2   # q 4.98e-4, 0.52 M_Jup
```
Core: `formation.compute_gap_opening_mass(hr | temp_k, mstar_msun, a_au, alpha|nu_code|reynolds, p_target,
mu)`. `--mstar-msun`+`--a-au` **always required** (the q→mass conversion); H/r via `--hr` **or** `--temp-k`;
viscosity via **exactly one** of `--alpha` (ν_code=α·(H/r)²), `--nu-code` (ν in a²Ω units), `--reynolds`
(R=a²Ω/ν). Output: `{gap_opening_mass_mearth, gap_opening_mass_mjup, threshold_q, hr, alpha_or_reynolds,
p_value_at_threshold, p_target, mstar_msun, a_au, model_note}`. **⚠ Reproduce Crida Case 1 with
`--nu-code 3.162e-6` (=10⁻⁵·⁵), NOT `--alpha`** — α=1e-3 gives a different ν (10⁻⁵·⁶⁰²) and threshold.
**Validation:** no/both H/r mode, missing M★/a, not exactly one viscosity, non-positive p-target, no
threshold in (1e-9,1) → exit 1. **Anchors:** threshold_q **4.978e-4** → **0.52 M_Jup** at M⊙,
p_at_threshold **1.000**; criterion cross-check P(q=1e-3)=**0.699** (a clear, super-marginal gap).
`model_note` carries the Malik et al. 2015 necessary-but-not-sufficient-for-migrating caveat.

#### `toomre-q` (P5)
`Q = c_s·Ω/(πGΣ)`; `unstable` when `Q < --q-crit` (default 1). Reports `λ_crit = 2c_s²/(GΣ)` and an
order-of-magnitude `M_frag ≈ πΣ(λ_crit/2)²`.
```bash
query.py toomre-q --sigma-gcm2 10.35 --temp-k 51.1 --mstar-msun 1 --a-au 30   # Q 23.7, stable
```
Core: `formation.compute_toomre_q(sigma_gcm2, temp_k|cs_ms|dispersion_ms, mstar_msun, a_au, mu, q_crit)`.
Sound speed via **exactly one** of `--temp-k` (→ c_s via μ), `--cs-ms`, `--dispersion-ms` (particle disk).
Output: `{toomre_q, unstable, q_crit, lambda_crit_au, fragment_mass_mjup, sound_speed_ms, omega_per_s,
sigma_gcm2, a_au, model_note}`. **Validation:** non-positive Σ/M★/a/q-crit, not exactly one c_s mode → exit
1. **Anchor:** MMSN at 30 AU → **Q ≈ 23.7** (stable, Q≫1); GI needs a disk ~1–2 orders more massive.

#### `critical-core-mass` (P6)
`M_crit = 12·(Ṁ/1e-6)^{1/4}·(κ/1)^{1/4} M⊕` (Armitage Eq. 236 / Ikoma+2000) — the envelope-runaway trigger.
```bash
query.py critical-core-mass                            # 12 M⊕ (fiducial)
query.py critical-core-mass --mdot-core 1e-7           # 6.75 M⊕
```
Core: `formation.compute_critical_core_mass(mdot_core, opacity, index, crit_norm)`. `--index` (default 0.25)
is the ±0.05 sensitivity knob. Output: `{critical_core_mass_mearth, mdot_core, opacity, index, model_note}`.
**Validation:** non-positive mdot/opacity/crit-norm → exit 1. **Anchors:** fiducial **12 M⊕**; Ṁ=1e-7 or
κ=0.1 → **6.75 M⊕** (weak ¼-power dependence, ~10 M⊕ scale).

### Metric-drive power & exclusion boundary (Phase AK — Group Q, network only on `exclusion-boundary --star`)

Two `query.py`-only, pure-math, self-validating (Phase-H/P contract) calculators for the FTL-arc packets:
`metric-drive-power` (`core/metric_drive.py`, Packet 25) and `exclusion-boundary`
(`core/exclusion_boundary.py`, Packet 26.5). Curated `{"error"}` exit 1, argparse exit 2, `model_note` on
every object. No numpy/RNG/time. **Two load-bearing caveats surfaced in `model_note`:** (1) the metric-drive
power/fuel law is the **subluminal (STL) mode ONLY** — Le 2026's theorem hypotheses exclude the exotic-matter
FTL mode, so it must NOT be inherited for FTL legs; (2) `exclusion-boundary` is a **required-breakthrough
(Rung-3) in-universe mechanism**, not established science — the `DIAL` and scaling exponents are a Packet-26.5
research output, calibrated (not measured) to Sol at the Kuiper edge.

#### `metric-drive-power` (Q1)
Field-rocket (photon-rocket) power + fuel/mass bill for the metric drive. `P_rad = k·F·c` (k = 3 the GR
geometric baseline ⟨cos²θ⟩=1/3 → c/3 → ≈0.9 GW/N; k < 3 is the setting's Rung-3 **B2** exotic discount, never
0). Fuel bill: `f_rad = 1 − e^(−k·Δη)`, `fuel_mass_fraction = f_rad / f_conv` with
`f_conv = f(mass→energy) × η_dir(directed/usable)`. Constant velocity (F = 0) ⇒ zero propulsive power.
```bash
query.py metric-drive-power --thrust-n 1 --k 3                                    # power_gw_per_n 0.9
query.py metric-drive-power --mass-tonnes 1000 --accel-g 1 --k 3                  # ≈8.83e15 W (9 PW)
query.py metric-drive-power --mass-tonnes 1000 --accel-g 1 --duration-days 1 --k 3 --fuel d-t          # f_rad 0.84%, fuel 2.25× ship
query.py metric-drive-power --mass-tonnes 1000 --accel-g 1 --duration-days 1 --k 3 --fuel antimatter-pp --eta-dir 1.0   # 0.84%
query.py metric-drive-power --thrust-n 1 --k 3 --beam-compare                     # beam 0.15 vs onboard 0.9 GW/N, crossover k 0.5
```
Core: `metric_drive.compute_metric_drive_power(mass_kg, mass_tonnes, thrust_n, accel_g, accel_ms2,
delta_v_kms, delta_v_c, rapidity, duration_days, k, fuel, f_conv, eta_dir, turn, integrated_rapidity,
beam_compare)`. **Mass:** `--mass-kg` | `--mass-tonnes`. **Thrust source:** `--thrust-n` OR `--accel-g`/
`--accel-ms2` (× mass). **Rapidity source:** `--rapidity` (Δη direct) OR `--delta-v-c`/`--delta-v-kms`
(exact-relativistic atanh) OR a leg `--accel-* + --duration-days`. `--k` (alias `--tsiolkovsky-k`, default 3);
`--fuel {d-t, d-he3, pp, dd, antimatter-pp, antimatter-ee}` (pp/dd f-values reused from
`core.ism_drag_tables._FUSION`); `--f-conv`/`--eta-dir` overrides; `--turn` + `--integrated-rapidity` (a turn
costs ≥ |Δη|); `--beam-compare`. Output: `{propulsion_power_w, power_gw_per_n, thrust_n, rapidity_delta,
radiated_mass_fraction, leg_energy_j, fuel_mass_fraction, fuel_mass_kg, fuel_key, f_conv, eta_dir, k,
ship_mass_kg, turn, beam_vs_onboard{beam_power_gw_per_n, onboard_power_gw_per_n, crossover_k, winner},
model_note}` (`beam_vs_onboard` only with `--beam-compare`; power/fuel fields null when the relevant input is
absent). **Validation:** k ≤ 0 (reactionless forbidden), f_conv ≤ 0, contradictory maneuver inputs, `--turn`
without `--integrated-rapidity` (or arc < |Δη|), |β| ≥ 1 → exit 1. **Anchors:** 0.9 GW/N @k3; 9 PW @1g/1000t;
4.4×10¹⁷ W @50g; 0.84% radiated @1 g-day; d-t → 2.25× ship mass; antimatter-pp η_dir 1.0 → 0.84%, default
η_dir 0.5 → 1.69%; F=0 → power 0.

**`--self-consistent` (R6 / Phase AL — self-consistent fuel-bill mode).** The first-order bill above treats
ship mass as fixed; `--self-consistent` taxes the carried fuel + retained ash + η_dir waste that are part of
the Bondi mass the law taxes (effective exponent k/η_dir). Requires a `--fuel` preset (to separate the
mass→energy fraction `f` from `η_dir`) and a maneuver (Δη > 0). `--ash {keep,vent}` (default `keep`):
**keep** yields the Packet-25 feasibility wall `X = (1−e^(−k·Δη/η_dir))/f < 1` and adds
`fuel_mass_fraction_sc` (when feasible), `feasible`, `wall_ratio_x`, `k_wall = −η_dir·ln(1−f)/Δη`, and
`lifetime_delta_v_budget_kms = c·tanh(−η_dir·ln(1−f)/k)`; **vent** (zero-relative-velocity dump) has no wall,
`fuel_mass_fraction_sc = e^(k·Δη/f_conv) − 1`. The first-order fields are unchanged (sc → first-order as
Δη → 0). Full-annihilation fuels (f = 1) have no finite `k_wall` (null) and a lightspeed Δv budget.
```bash
query.py metric-drive-power --mass-tonnes 1000 --accel-g 1 --duration-days 1 --fuel d-t --self-consistent          # infeasible, k_wall 1.329, budget 375.4 km/s
query.py metric-drive-power --mass-tonnes 1000 --accel-g 1 --duration-days 1 --fuel d-t --k 1 --self-consistent     # feasible, fuel_mass_fraction_sc 3.04
query.py metric-drive-power --mass-tonnes 1000 --accel-g 1 --duration-days 1 --fuel d-t --self-consistent --ash vent  # 8.59 (no wall)
```
Added output keys (only with `--self-consistent`): `{self_consistent, ash, feasible, fuel_mass_fraction_sc,
wall_ratio_x, k_wall|null, lifetime_delta_v_budget_kms|null}`. **Validation:** `--ash vent` without
`--self-consistent`, `keep` mode with only `--f-conv` (can't split f/η_dir), or no maneuver (Δη = 0) → exit 1.
**Anchors:** D-T 1 g-day k=3 → infeasible / k_wall 1.329 / budget 375.4; k=1 → sc 3.04; antimatter-pp 25 g-day
k=3 → sc 0.529; vent D-T k=3 → sc 8.59.

#### `exclusion-boundary` (Q2)
FTL exclusion-boundary radius **r_ex** (the "Alcubierre Limit") for a body:
`r_ex = DIAL · (M/M☉)^α · (L/L☉)^β · (Ẇ/Ẇ_☉)^γ`, auto-calibrated so r_ex(Sun) = the Kuiper-edge anchor
(47.5 AU) unless `--dial` is given. `α` (mass exponent, canon [1/3, 1/2], default 1/3), `β`/`γ` (luminosity /
wind exponents, default 0 = off). Classifies the **graded forcing** geography (`forcing_class` ∈ `harbor` /
`checkpoint` / `optional`, provisional bands: optional < 10 AU, harbor ≥ 95 AU).
```bash
query.py exclusion-boundary --object sun                          # r_ex 47.5 AU
query.py exclusion-boundary --mass-msun 0.1 --scan-alpha          # third 22.05 / half 15.02 AU, checkpoint
query.py exclusion-boundary --mass-msun 10 --scan-alpha           # third 102.3 / half 150.2 AU, harbor
query.py exclusion-boundary --object sun --dial 100 --alpha 0.5   # explicit dial overrides auto-cal → 100
query.py exclusion-boundary --mass-msun 1 --gamma 0.5 --mass-loss-msun-yr 1e-6   # hot-star wind pushes r_ex out
```
Core: `exclusion_boundary.compute_exclusion_boundary(mass_msun, luminosity_lsun, mass_loss_msun_yr, wind_state,
dial, calibration_au, alpha, beta, gamma, scan_alpha, object_name)`. **Body source (exactly one):** `--mass-msun`
| `--object {sun, m-dwarf, o-star, brown-dwarf, rogue-planet}` | `--star <name>` (SIMBAD + regions mass/lum,
**network**) | `--spectral-type <type>` (main-sequence table, local DB). Optional environment: `--luminosity-lsun`,
`--mass-loss-msun-yr` (Ẇ), `--wind-state {quiet, solar, active, hot}` (→ a Ẇ preset). Calibration/scaling:
`--dial`, `--calibration-au` (default 47.5), `--alpha` (default 1/3), `--beta`/`--gamma` (default 0),
`--scan-alpha` (emit both α edges). Output: `{r_ex_au, r_ex_au_alpha_third, r_ex_au_alpha_half, mass_msun,
luminosity_lsun, mass_loss_msun_yr, dial, alpha, beta, gamma, calibration_au, forcing_class, object,
model_note}` (`r_ex_au_alpha_*` only with `--scan-alpha`). **Validation:** M ≤ 0, negative exponents,
non-positive dial/calibration, `β ≠ 0` with L ≤ 0, or a wind exponent (`γ ≠ 0`) with no wind input → exit 1.
**Anchors:** Sun 47.5 AU; 0.1 M☉ → 22.05/15.02 AU (α 1/3, 1/2); 10 M☉ → 102.3/150.2 AU (harbor); explicit
`--dial` overrides auto-cal; solar-wind term = 1 at the Ẇ=2×10⁻¹⁴ preset.

### Power generation / storage / thermal (Phase AL — Group R, no network)

Ten `query.py`-only, pure-math, self-validating calculators + two bundled-table subcommands for the
sibling repo's **Packet 27** (Power Generation, Storage, Distribution, Thermal Management). Modules:
`core/power.py` (R1/R2/R4/R7/R10), `core/energy_storage.py` (R8/R9), `core/thermal.py` (R3, beside the
Phase V calcs), `core/power_tables.py` (T1/T2). Fission `f` rows added to `core/ism_drag_tables.py`
(`_FISSION`). Every calc self-validates (curated `{"error"}` exit 1 / argparse exit 2) and carries a
`model_note`; every bundled row carries a `source_tag` + `note` and is caller-overridable; load-bearing
`[pin @ open]` values are flagged un-promoted. Composes with the existing `waste-heat` / `radiator-area` /
`dyson-collector` / black-hole family for the full power→heat→rejection chain.

#### `annihilation-power-train` (R1)
Antimatter annihilation power partition: `P_total = ṁ·c²` split into directed / γ-heat / ν-loss.
```bash
query.py annihilation-power-train --mass-flow-kgs 1e-9                 # pp: total 8.99e7, directed 4.49e7, γ 3.0e7, ν 4.49e7
query.py annihilation-power-train --power-total-w 1 --species ee       # ee → 2γ, no ν
```
Core: `power.compute_annihilation_power_train(mass_flow_kgs, power_total_w, species, eta_dir)`. Anchor
(exactly one): `--mass-flow-kgs` (P=ṁc²) | `--power-total-w`. `--species {pp,ee}` (default pp); `--eta-dir`
override (default 0.5 pp / 1.0 ee). Output: `{power_total_w, power_directed_w, power_gamma_w,
power_neutrino_w, eta_dir, species, model_note}`. For `pp` the branching is fixed ≈½ν/⅓γ/⅙e± (γ = P/3, ν = P/2)
and `power_directed_w = η_dir·P_total` is the design-capturable fraction (overlaps the channels, not a strict
partition). **Validation:** both/neither anchor, non-positive value, bad species, η_dir ∉ (0,1] → exit 1.
**Anchor:** pp, 1 µg/s → total 8.988e7 W; η_dir 0.5 → directed 4.494e7, γ 2.996e7, ν 4.494e7.

#### `antimatter-production` (R2)
Antimatter production energy floor + Penning-trap storage-density ceiling.
```bash
query.py antimatter-production --stored-mass-kg 1e-9 --production-efficiency 1e-4   # energy_in 8.99e11 J, floor 0.333
query.py antimatter-production --stored-energy-j 8.99e7 --production-efficiency 1e-4 --trap-field-t 20
```
Core: `power.compute_antimatter_production(stored_mass_kg, stored_energy_j, production_efficiency,
trap_field_t)`. Anchor (exactly one): `--stored-mass-kg` (E=mc²) | `--stored-energy-j`.
**`--production-efficiency` is REQUIRED and un-defaulted** — the H-25-1 research input (Frisbee 2008;
Schmidt/Gerrish/Martin NASA), never a shipped number. Optional `--trap-field-t` → the Brillouin
space-charge mass-density ceiling ε₀·B²/2. Output: `{energy_in_j, energy_stored_j, production_efficiency,
threshold_floor_efficiency, energy_ratio_in_per_stored, storage_density_kg_m3|null, trap_field_t, notes,
model_note}`. `threshold_floor_efficiency = 2 m_p/6 m_p = 0.3333` (exact, baryon-conserving threshold).
**Validation:** both/neither anchor, non-positive, missing efficiency, η ∉ (0,1], trap field ≤ 0 → exit 1.
**Anchor:** stored 1 ng, η 1e-4 → stored 8.988e7 J, in 8.988e11 J, floor 0.3333, ratio 1e4.

#### `reactor-net-power` (R4)
Net-energy / Q-gate accounting: how much gross reactor output survives recirculation.
```bash
query.py reactor-net-power --gross-power-w 1e9 --thermal-efficiency 0.4 --q-plasma 10   # elec 4e8, net 3.6e8, breakeven 2.5
```
Core: `power.compute_reactor_net_power(gross_power_w, thermal_efficiency, q_plasma, recirculating_fraction)`.
`--gross-power-w` + `--thermal-efficiency` required; `--q-plasma` (fusion Q-tax P_elec/Q → 0 at ignition);
`--recirculating-fraction` [0,1) default 0. Output: `{gross_power_w, electric_power_w, net_power_w,
engineering_breakeven_q, thermal_efficiency, q_plasma|null, recirculating_fraction, model_note}`. Net-energy
only — specific power (W/kg) is `reactor-power` + the thermal pointer. `--q-plasma` can be fed from
`fusion-lawson`. **Validation:** non-positive gross, η_th ∉ (0,1], q_plasma ≤ 0, recirc ∉ [0,1) → exit 1.
**Anchor:** 1 GW / η 0.4 / Q 10 → electric 4.0e8, breakeven 2.5, net 3.6e8 W.

#### `beamed-power-delivery` (R7)
Diffraction-limited beamed-power link efficiency — the λL/D wall behind "beamed power".
```bash
query.py beamed-power-delivery --wavelength-m 1e-6 --tx-aperture-m 10 --rx-aperture-m 100 --range-m 1.496e11   # spot 36.5 km, capture 7.5e-6
```
Core: `power.compute_beamed_power_delivery(wavelength_m, frequency_hz, tx_aperture_m, rx_aperture_m, range_m,
tx_power_w, pointing_efficiency)`. Wavelength anchor (exactly one): `--wavelength-m` | `--frequency-hz`;
`--tx-aperture-m` / `--rx-aperture-m` / `--range-m` required; `--tx-power-w` (→ delivered), `--pointing-efficiency`
default 1. `D_spot = 2.44·λ·L/D_t`, `capture = min(1, (D_r/D_spot)²)`, full coupling needs D_t·D_r ≳ 2.44·λ·L.
Output: `{spot_diameter_m, capture_fraction, delivered_power_w|null, aperture_product_m2,
full_coupling_product_m2, coupling_margin, wavelength_m, range_m, pointing_efficiency, model_note}`.
**Validation:** both/neither wavelength anchor, any non-positive aperture/range, pointing ∉ (0,1] → exit 1.
**Anchor:** λ 1 µm, D_t 10 m, L 1 AU → D_spot 3.65e4 m; D_r 100 m → capture 7.5e-6.

#### `fusion-lawson` (R10)
Lawson triple-product → fusion gain Q (grounds `reactor-net-power`'s `--q-plasma`). **General-power /
civilian-reactor side ONLY** — does not reopen the metric-drive task-(d) f-wall.
```bash
query.py fusion-lawson --fuel d-t --triple-product 3e21                       # q 1, ignited (boundary)
query.py fusion-lawson --fuel d-t --density-m3 1e21 --temp-kev 3 --confinement-s 1 --confinement-boost 3   # q 3
```
Core: `power.compute_fusion_lawson(fuel, density_m3, temp_kev, confinement_s, triple_product,
confinement_boost)`. `--fuel {d-t,d-he3,d-d,p-b11}` required; supply the `(n,T,τ)` triple OR
`--triple-product` directly; `--confinement-boost` (AG multiplier on n·τ, default 1). Output:
`{triple_product_kev_s_m3, ignition_threshold, q_fusion, ignited, confinement_boost, fuel, model_note}`.
Per-fuel ignition thresholds are **[pin @ open]** illustrative anchors (p-B11 ~10³× harder). **Validation:**
bad fuel, no/partial triple + no `--triple-product`, both supplied, non-positive, boost ≤ 0 → exit 1.
**Anchor:** D-T n·T·τ = 3e21 → q 1 (ignited boundary); boost 3 → q 3.

#### `heat-pump` (R3)
Active-refrigeration Carnot COP — the inverse of `waste-heat` (radiating from a cold reservoir).
```bash
query.py heat-pump --cold-temp-k 300 --hot-temp-k 320 --heat-lifted-w 1   # COP 15, work 0.0667 W, rejected 1.0667 W
```
Core: `thermal.compute_heat_pump(cold_temp_k, hot_temp_k, heat_lifted_w, work_w, efficiency_fraction)`.
`--cold-temp-k` / `--hot-temp-k` required (T_h > T_c); load anchor (exactly one): `--heat-lifted-w` (Q_c) |
`--work-w`; `--efficiency-fraction` (0,1] default 1 (fraction of Carnot COP). `COP_cool = T_c/(T_h−T_c)`;
`W = Q_c/COP`; `heat_rejected = Q_c + W` (feeds `radiator-area` at T_h). Output: `{cop_cool_carnot,
cop_heat_carnot, cop_cool_actual, work_w, heat_lifted_w, heat_rejected_w, cold_temp_k, hot_temp_k,
efficiency_fraction, model_note}`. **Validation:** T ≤ 0, T_h ≤ T_c, both/neither load anchor, frac ∉ (0,1] →
exit 1. **Anchor:** lift 1 W 300→320 K → COP 15, W 0.0667, rejected 1.0667 W.

#### `flywheel-storage` (R8)
Flywheel specific-energy ceiling `e = K·σ/ρ` (the material-strength wall, same σ as a rotating-habitat rim).
```bash
query.py flywheel-storage --tensile-strength-pa 5e9 --density-kgm3 1800 --shape-factor 0.5   # 1.39e6 J/kg (386 Wh/kg)
```
Core: `energy_storage.compute_flywheel_storage(tensile_strength_pa, density_kgm3, shape_factor, mass_kg)`.
`--tensile-strength-pa` / `--density-kgm3` required; `--shape-factor` (0,1] default 0.5 (0.3 thin rim → 1.0
constant-stress disk); `--mass-kg` → stored energy. Output: `{specific_energy_j_kg, specific_energy_wh_kg,
stored_energy_j|null, shape_factor, tensile_strength_pa, density_kgm3, mass_kg, model_note}`. **Validation:**
non-positive σ/ρ, K ∉ (0,1], mass ≤ 0 → exit 1. **Anchor:** σ 5e9 / ρ 1800 / K 0.5 → 1.389e6 J/kg; K 0.3 → 8.33e5.

#### `smes-storage` (R9)
SMES magnetic energy density `u = B²/2µ₀` + the structure-limited specific energy (same σ/ρ family as R8 — the
magnetic pressure must be held by structure).
```bash
query.py smes-storage --field-t 20                                            # u 1.59e8 J/m³ (159 MJ/m³)
query.py smes-storage --field-t 25 --critical-field-t 20 --tensile-strength-pa 5e9 --density-kgm3 1800
```
Core: `energy_storage.compute_smes_storage(field_t, critical_field_t, tensile_strength_pa, density_kgm3,
volume_m3)`. `--field-t` required; `--critical-field-t` (flags `critical_field_exceeded` when B > B_c);
`--tensile-strength-pa` + `--density-kgm3` **as a pair** → specific energy σ/ρ; `--volume-m3` → stored energy.
Output: `{energy_density_j_m3, stored_energy_j|null, specific_energy_j_kg|null, field_t, critical_field_t,
critical_field_exceeded|null, volume_m3, model_note}`. **Validation:** B ≤ 0, B_c ≤ 0, volume ≤ 0, only one of
σ/ρ → exit 1. **Anchor:** B 20 T → u 1.592e8 J/m³.

#### `energy-storage` (T1 — bundled table)
Battery/chemical/thermal specific energies (where no clean floor law exists). No `--class` → all rows.
```bash
query.py energy-storage                                                       # all rows
query.py energy-storage --class li-ion --override-wh-kg 500                    # single row, overridden
query.py energy-storage --mass-kg 1000 --specific-heat-jkgk 4186 --delta-t-k 100   # sensible compute → 4.186e8 J
query.py energy-storage --class latent-thermal --mass-kg 1000 --latent-heat-jkg 334000   # latent compute
```
Core: `power_tables.compute_energy_storage(class_name, override_wh_kg, mass_kg, specific_heat_jkgk, delta_t_k,
latent_heat_jkg)`. Classes: `li-ion, supercapacitor, chemical-fuel, sensible-thermal, latent-thermal,
gravitational` (all rows **[pin @ open]**). Compute branch: `--mass-kg` + `--specific-heat-jkgk` + `--delta-t-k`
→ sensible `E=m·c_p·ΔT`; `--mass-kg` + `--latent-heat-jkg` → latent `E=m·L`. Output: lookup `{class,
specific_energy_j_kg, specific_energy_wh_kg, volumetric_wh_l|null, round_trip_efficiency|null, leak_note,
source_tag, note}` (+ `overridden` when `--override-wh-kg`, + `stored_energy_j` when computed); no-class → `{classes:[…]}`.
Nuclear/antimatter ceilings come free from `f·c²` (not rows). **Validation:** unknown class → curated error
listing valid keys; both compute branches, mass ≤ 0, non-positive override → exit 1.

#### `reactor-power` (T2 — bundled table)
Reactor specific power `α = P/m` [kW/kg] — no floor-physics law, so a table + a **mandatory thermal pointer**.
```bash
query.py reactor-power                                                         # all rows
query.py reactor-power --class fusion --gross-power-w 1e9                       # implied core_mass_kg 2e5
```
Core: `power_tables.compute_reactor_power(class_name, override_kw_kg, gross_power_w)`. Classes: `fission,
fusion, antimatter, rtg, solar-thermal` (all α **[pin @ open]**). `--override-kw-kg` substitutes α (echoed);
`--gross-power-w` → implied `core_mass_kg = P/(α·1000)`. Output: `{class, specific_power_kw_kg, core_mass_kg|null,
source_tag, note, thermal_pointer}` (+ `overridden`); no-class → `{classes:[…], thermal_pointer}`. **Every result
carries `thermal_pointer`** — the real high-P ceiling is thermal (compose `reactor-net-power`/`waste-heat` →
`radiator-area`), not core mass. **Validation:** unknown class → curated error listing valid keys; gross ≤ 0,
override ≤ 0 → exit 1.

### Sensing & detection (Phase AP — Group S, no network)

Three `query.py`-only, pure-math, self-validating calculators for the sibling repo's **Packet 30**
(Sensing, Navigation, Mapping, Surveillance) — the **receiver side** query.py lacked: turning a
*source* term (a drive/plume/radiator power) into a **detection range / SNR**. Module: `core/sensing.py`
(imports only `core.equations` constants, so `core.calculators` can call its Rayleigh kernel without a
cycle). Every calc self-validates (curated `{"error"}` exit 1 / argparse exit 2) and carries a
`model_note`; bundled background/band presets are transcribed + overridable. Composes with `waste-heat`
/ `radiator-area` / `metric-drive-power` / `annihilation-power-train` (source terms) and `distance` /
`gcns-distance` (range = light-lag).

#### `angular-resolution` (S2)
Diffraction-limited resolution `θ = k·λ/D` (the shared kernel; `direct-imaging` calls it for its IWA).
```bash
query.py angular-resolution --aperture-m 1 --wavelength-m 10e-6 --range-m 1.496e11   # θ=1.22e-5 rad=2.516″; x_res≈1825 km
query.py angular-resolution --aperture-m 6.5 --wavelength-m 2e-6                      # JWST-class: 0.0774″
```
Core: `sensing.compute_angular_resolution(aperture_m, wavelength_m|frequency_hz, range_m, separation_m,
object_size_m, criterion, coefficient)`. `--criterion {rayleigh,dawes,sparrow}` (k = 1.22/1.02/0.94) or
`--coefficient` override; `--range-m` → `linear_resolution_m`; `--separation-m` → `resolvable`;
`--object-size-m` → `resolved_or_point`. Output: `{angular_resolution_rad, angular_resolution_arcsec,
linear_resolution_m|null, resolvable|null, resolved_or_point|null, criterion, coefficient, …}`.
**Validation:** aperture ≤ 0, both/neither λ/f, bad criterion, coefficient ≤ 0, non-positive range/sep/size → exit 1.

#### `point-source-detection` (S1)
The "no-stealth-in-space" core: an unresolved source of power `L` at range `R`, aperture `D`.
```bash
query.py point-source-detection --source-temp-k 300 --source-area-m2 1000 --rx-aperture-m 1 --flux-floor-w-m2 1e-19
      # L=4.593e5 W; max_detection_range 6.05e11 m ≈ 4.04 AU (aperture-INDEPENDENT flux-floor solve)
query.py point-source-detection --source-power-w 4.593e5 --rx-aperture-m 1 --range-m 1.496e11 --wavelength-m 10e-6 --nep-w-rthz 1e-19
      # E=1.633e-18 W/m², P_rx=1.026e-18 W, n=51.7 photon/s, detector-limited SNR
query.py point-source-detection --source-power-w 4.593e5 --rx-aperture-m 1 --range-m 1.496e11 --band thermal-ir --background cmb
```
Core: `sensing.compute_point_source_detection(source_power_w | source_temp_k+source_area_m2, emissivity,
rx_aperture_m, optical_efficiency, range_m, integration_s, quantum_efficiency, band | wavelength_m |
band_min_m+band_max_m, source_size_m, nep_w_rthz | background(+background_intensity_w_m2_sr_m,
background_temp_k, background_dilution) | flux_floor_w_m2, snr_threshold)`. Laws: `E = L/(4πR²)`,
`P_rx = E·A_rx·η_opt`, `n = P_rx·λ/hc`; detector-limited `SNR = P_rx/(NEP·√(1/2t))`; background/shot-limited
`SNR = S/√(S+B)` over the PSF solid angle (the S2 kernel at 1.22). Output: `{source_luminosity_w,
irradiance_w_m2, received_power_w, photon_rate_hz, angular_size_rad|null, resolved_or_point, snr|null,
max_detection_range_m|null, detection_regime, background_used, …}`.
**`--flux-floor-w-m2` is an IRRADIANCE floor** → `max_detection_range_m = √(L/(4π·floor))`,
**aperture-independent** (`--rx-aperture-m`/`--optical-efficiency`/`--quantum-efficiency` are inert for
*that* solve; they still drive `received_power_w`/`photon_rate_hz`/`snr` and the SNR-path solve — for an
aperture-dependent range use the `--nep`/`--background` SNR path). **`--background` modes need a band**
(`--band` or `--band-min-m`/`--band-max-m`) — a bare `--wavelength-m` has no Δλ. The `model_note` states
this is the classical EM/thermal envelope (no exotic gravimetric/GW drive-wake sensing). Background presets
(`cmb`/`stellar`/`zodiacal`/`none`) are order-of-magnitude + look-direction-dependent; override with
`--background-intensity-w-m2-sr-m`. With `--source-size-m`, `resolved_or_point` is `resolved` when
`θ_s = size/R ≥ θ_res`, and the `model_note` then flags the point-source irradiance/SNR figures as a
**lower bound** (a resolved source spreads flux over multiple resolution elements). The `photon_rate_hz`
is a **band-centre (narrow-band) conversion of the bolometric `P_rx`** — not an in-band Planck integral —
consistent with the bolometric `E`/`P_rx` by construction (degrades as Δλ/λ grows). **Validation:**
both/neither source, rx ≤ 0, ε/η ∉ (0,1], >1 floor, solve-mode with no floor, background with no band → exit 1.

#### `radar-range` (S3)
Active radar range equation (the `R⁻⁴` counterpart to S1's passive `R⁻²`).
```bash
query.py radar-range --tx-power-w 1e9 --tx-aperture-m 10 --wavelength-m 0.03 --target-rcs-m2 100 --range-m 1e9          # P_rx=5.45e-20 W
query.py radar-range --tx-power-w 1e9 --tx-aperture-m 10 --wavelength-m 0.03 --target-rcs-m2 100 --min-detectable-power-w 1e-18  # R_max≈4.83e8 m
```
Core: `sensing.compute_radar_range(tx_power_w, tx_aperture_m, rx_aperture_m, wavelength_m|frequency_hz,
target_rcs_m2, range_m | min_detectable_power_w, integration_s, system_noise_temp_k, tx_gain, rx_gain,
snr_threshold)`. `P_rx = P_tx·A_tx·A_rx·σ/(4π·λ²·R⁴)`; `--rx-aperture-m` defaults to tx (monostatic);
gains default `(πD/λ)²`, overridable; `--system-noise-temp-k` → SNR vs `P_n = k_B·T_sys·Δf`. Output:
`{received_power_w|null, max_range_m|null, snr|null, tx_gain, rx_gain, …}`. **Validation:** non-positive
tx-power/aperture/rcs, both/neither λ/f, both/neither range/P_min → exit 1.

### Strategic-geography graph analytics (Phase AQ — Group T, local DB, no network unless a name needs SIMBAD)

Two `query.py`-only calculators adding an **analytic layer** over the same jump graph the routing group
builds (`core/strategic_geography.py`), for the sibling repo's **Packets 32 / 38**. Reads the
`star_systems` catalog through the routing helpers (`_resolve_star_position` / `_load_star_systems_positions`
/ `_SpatialGrid`) — same read path as `jump-network`, **no new dataset**. A star given by name resolves
DB-first then SIMBAD (network only on a DB miss); `"Sol"`/`"Sun"` and Gaia/DB names stay offline. Graph
algorithms are iterative (survive the ~256k-row catalog). Self-validating; each result carries a `model_note`.

#### `network-centrality` (T1)
Route value / chokepoints: degree + Freeman betweenness, Hopcroft–Tarjan articulation points + bridges,
optional Menger min-cut.
```bash
query.py network-centrality --within-ly 15 --of Sol --max-jump 6            # neighbourhood chokepoints
query.py network-centrality --stars Sol "Alpha Cen" "Barnard's star" --max-jump 6 --from Sol --to "Alpha Cen"
query.py network-centrality --within-ly 15 --of Sol --max-jump 6 --weight dust   # least-extinction chokepoints (WSL/Linux dust extra)
```
Core: `strategic_geography.compute_network_centrality(stars | within_ly+of | catalog, max_jump_ly, weight,
from_star, to_star, top, dust_map, dust_step_pc)`. Node set: `--stars <list>` | `--within-ly N --of <star>` |
`--catalog`. Edges = pairs within `--max-jump` ly. **`--weight {hops,distance,dust}`** selects the
**betweenness** shortest-path metric — `dust` minimises the integrated extinction **A_V** per edge (composes
the dust-routing edge cost; `--map {near-field,edenhofer,auto}` + `--dust-step-pc`, default 5; **needs the
WSL/Linux `dustmaps` extra** — a curated `{"error"}` otherwise; a sightline the map can't integrate is routed
around and listed in `dust_errors`, still counted for the topological metrics). `--from`/`--to` → a pairwise
edge **min-cut** (topological — fewest edges, weight-independent; endpoints resolve **local-first** against the
node set before any SIMBAD call); `--top N` caps the reported highest-centrality nodes (default 25). Output:
`{nodes[]{name,degree,betweenness}, articulation_points[], bridges[], min_cut{value,cut_set}|null,
graph{n_nodes,n_edges,connected,components}, node_set, weight, betweenness_capped, [dust_map, dust_step_pc,
dust_errors], …}`. **Scale guard:**
degree/articulation/bridges/components run on any size; **betweenness + min-cut are capped at 2000 nodes**
— above it they return `null` with a note (narrow `--within-ly` or use `--stars`). Models the STL/lane era;
for FTL free-emergence picketing use `arrival-corridors`. **Validation:** no/two selectors, max-jump ≤ 0,
bad weight, `--from` without `--to`, `--within-ly` without `--of`, < 2 nodes → exit 1.

#### `arrival-corridors` (T2)
FTL-emergence / picket geometry: cluster the origin bearings into corridors and size the picket solid angle.
```bash
query.py arrival-corridors --system Sol --within-ly 12 --corridor-halfwidth-deg 5 --cluster-deg 5
query.py arrival-corridors --system Sol --origins "Alpha Cen" "Barnard's star" Sirius
```
Core: `strategic_geography.compute_arrival_corridors(system, within_ly | origins, corridor_halfwidth_deg,
cluster_deg, min_jump, max_jump)`. Bearings = unit vectors system→origin as galactic `(l,b)` (J2000
equatorial→galactic rotation); `light_lag_yr = distance_ly`; cluster by angular separation `< --cluster-deg`;
`angular_coverage_fraction = Σ Ω_cone/4π`, `Ω_cone = 2π(1−cos halfwidth)`. Output: `{system, corridors[]
{origin, distance_ly, bearing_lb{l,b}, light_lag_yr, cluster_id}, n_origins, n_distinct_corridors,
corridor_halfwidth_deg, cluster_deg, angular_coverage_fraction, …}`. Geometry only — interdiction *doctrine*
is Pkt 38. **Validation:** no system, no/both origin selectors, halfwidth/cluster ∉ (0,180], min ≥ max,
no candidates after filters → exit 1.

### Compute & beamrider utilities (Phase AR — Group U, no network)

Two thin `query.py`-only derivations for the sibling repo's **Packets 29 / 33** — a clean CLI for two
recurring worldbuilding numbers. `landauer-limit` lives in `core/thermal.py` (a thermodynamic floor beside
`heat-pump`); `beamrider-relay-spacing` in `core/power.py` (it inverts `beamed-power-delivery`). Self-validating.

#### `landauer-limit` (U1)
Irreversible-compute energy floor `E_bit = k_B·T·ln2` — the compute-energy companion to `bekenstein-bound`.
```bash
query.py landauer-limit --temp-k 300 --power-w 1        # E_bit=2.871e-21 J; max erasure rate 3.483e20 bit/s
query.py landauer-limit --temp-k 2.725                  # CMB-cold: E_bit=2.608e-23 J
```
Core: `thermal.compute_landauer_limit(temp_k, bits | power_w | bit_rate_hz, reversible)`. Output:
`{energy_per_bit_j, temp_k, total_energy_j|null, max_erasure_rate_hz|null, min_power_w|null, reversible,
model_note}`. `--reversible` only annotates that reversible/adiabatic computing can go below the floor.
**Validation:** temp ≤ 0, >1 of bits/power/bit-rate, non-positive value → exit 1.

#### `beamrider-relay-spacing` (U2)
Diffraction-limited relay-node spacing — inverts `beamed-power-delivery` for the STL-waystation skeleton.
```bash
query.py beamrider-relay-spacing --wavelength-m 1e-6 --tx-aperture-m 1000 --rx-aperture-m 1000 --total-range-ly 4
      # L_t=4.10e11 m; relay spacing 5.80e11 m ≈ 3.87 AU; 4 ly lane → 65,292 relays
```
Core: `power.compute_beamrider_relay_spacing(wavelength_m|frequency_hz, tx_aperture_m, rx_aperture_m,
delivered_fraction_threshold, total_range_ly | total_range_m)`. `L_t = D_t·D_r/(2.44·λ)` (full-capture
range); `L_relay = L_t/√threshold`. Output: `{transition_range_m, relay_spacing_m, relay_spacing_ly,
delivered_fraction_threshold, n_relays|null, …}`. **Validation:** both/neither λ/f, non-positive aperture,
threshold ∉ (0,1], both total-range units → exit 1.

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
> **Default note (deviation from completed_plans/PHASE_AD_PLAN.md, user decision 2026-07-03):** the plan specified
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
neither is a curated `{"error"}` on **stdout, exit 1** — P4.1, previously a stderr/exit-2
message). A missing required `--luminosity` remains an argparse **exit 2**. `--albedo`
defaults to **0.3**.
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
Core function: `report.build_system_dossier(star, sections=None, fmt="markdown", force_ms_inversion=False)`
(CR-10.5: `--force-ms-inversion` overrides the evolved-star region guard — see the CR-10 second-fire block below.
CR-11.2: `--star-mass-catalog`/`--mass-solar` add stellar-mass provenance + measured-mass preference — see the CR-11 block below.)

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
- **`identity.gould`** (Phase AO, additive): the star's Gould designation in genitive display
  form (`"66 G. Centauri"`), or `null`. The key is **always present** in the `json` `data`
  payload; the rendered md/html adds a **"Gould designation"** row directly after
  "Designations" **only when non-null**, so the ~99% of dossiers with no Gould designation are
  byte-identical to before. It is **not** appended to the `designations` list — that list is
  SIMBAD-sourced and Gould comes from VizieR. `null` for Sol (Gould catalogued southern stars).
- **`Sol`/`Sun`** is the **offline reference-origin path**: identity from solar constants,
  regions/HZ from `compute_sol_regions`, `planets` from the real Solar System tables (Planets /
  Dwarf Planets / Major Asteroids; `moons` opt-in), Hypatia from the solar [X/H]≡0 zero-point,
  and **GCNS is not applicable** (a `notes[]` entry, not a warning). No SIMBAD/network call.
- **Output envelope:** `{star, fmt, sections, warnings, notes}` plus `document` (md/html) or
  `data` (json). `sections` lists the sections actually rendered.
- **`document` luminosity formatting (md/html only — consumer-parser note):** the rendered
  `document`'s three `regions` luminosity rows — `Bolometric luminosity`, `Luminosity from mass`,
  `Calculated luminosity` — are formatted to **3 significant figures** (`%.3g`), **not** fixed
  decimals. Fixed 3-decimal rounding flattened every M/L dwarf to `0.001 L☉` (and ultracool
  dwarfs to `0.000`), unusable for a downstream snow-line/HZ calc; `%.3g` keeps both ends usable
  (`0.00141`, `0.000552`, `0.555`, `50`). **Values below ~1e-4 L☉ render in scientific notation**
  (e.g. `6e-05 L☉`), so a parser extracting the numeric token from a `| <label> | <value> L☉ |`
  row **must accept an `e±NN` exponent**. The row shape is unchanged. The **`json` `data`** payload
  is unaffected — it carries full float precision (e.g. `bc_luminosity = 1.0867409911518908`), so
  prefer `--fmt json` for numeric consumption.

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
  hz_opt_outer_au` (optimistic) + `snow_line_au, feh, feh_source, source, grounding,
  multiplicity`. `feh` is the host `[Fe/H]` (nullable) and `feh_source` its provenance
  (`"feh_dist"` synthetic-draw · `"hypatia"`/`"simbad"` real-anchor · `null`) — populated
  only under the `strict` v2 metallicity path (below), else both `null`. Each planet carries
  `name, a_au, mass_earth, radius_earth, ecc, type
  (rocky|super_earth|ice|gas|super_jovian|brown_dwarf), t_eq_k, in_hz, hz_class
  (conservative|optimistic|null), source, atmosphere, moons[]`. Every synthetic field is
  grounded `default-extrapolation` (the `DefaultPriors` provider) under the default
  `permissive` policy, or `research-calibrated` under `--research-policy strict` with an
  ingested dataset (Phase R3 — above). Multi-star anchors are **detected, warned, and safe-capped** (no
  synthetic body beyond a conservative cap; observed bodies are never capped); a quantitative
  S/P-type verdict needs a `--companion` hint (Phase R2 — below).
  Planets are emitted in **orbital order** (ascending `a_au`) in both modes — the v2.2/v2.3
  decoupled giant populations are placed after the grid, so the list is sorted before it is
  returned.
- **`star.age_gyr` / `star.age_source` / `star.activity`** — all `null` under `permissive` / a v1
  dataset. Under `strict` with a v2.10+ dataset, **synthetic** mode draws the host age from the
  `age_dist` block (Phase R3-V2 B2) — a population-weighted **SFH histogram**, not a Gaussian —
  and **MS-lifetime-truncated**: no star is ever older than its own main sequence (rejection
  against the Phase-L3 `compute_stellar_evolution`). `age_source` is `"age_dist"` or `null`.
  **v2.11.0 Q5:** when the block carries a `populations` sub-block, age is drawn **per Galactic
  population** — draw thin/thick/halo by its local mix weight (≈ 0.88/0.10/0.01), then the age
  from that population's own SFH (thin = the smoothed blended histogram restricted to ≤ 11 Gyr;
  thick/halo = truncated Gaussians peaked ~10.5/~12.5 Gyr); without the sub-block the blended
  histogram is used, unchanged.
  The histogram's known BGM discrete-age-bin artifact (a zeroed 7–8 Gyr bin) is **smoothed**,
  because the dataset ships an `sfh_smoothing_note` declaring that intended.
  `activity` is the `stellar_activity` chain it unblocks: `{age_gyr, p_rot_days, p_rot_branch,
  p_rot_source, tau_days, rossby, log_lx_lbol, regime, out_of_fitted_domain[], band, log_l_x_erg_s,
  log_l_euv_erg_s, log_l_xuv_erg_s, euv_fraction, xray_to_euv_relation, xray_to_euv_grade,
  xray_to_euv_alternatives[], circumbinary_component_scaling?}`. `p_rot_branch` is one of
  `tidally_locked` (a B1 close pair — `P_rot = P_orb`, saturated for life, and the **only branch
  that needs no age**), `skumanich_fgk` (0.6–1.36 M☉), `m_dwarf_fast` / `m_dwarf_slow` (0.08–0.6 M☉,
  bimodal and deliberately **not** interpolated across the gap). Out-of-domain values are
  **flagged, never clamped**. The X-ray→EUV conversion is **contested in the dataset** — the applied
  relation is named and its alternative listed rather than averaged. `p_rot_source` is the constant
  `"modelled"` — a contract marker so a modelled `p_rot_days` can never be read as an observed
  rotation period, even on a real anchor whose age *is* observed; it is `"modelled"` in both modes.
  **Real-anchor mode (1a, 2026-08-03) now reads the host age from an observed catalogue** — HWC
  `S_AGE` → Mission Exocat `st_age`, both **Gyr** — and reconstructs `activity` from it, so under
  `strict` `age_source` there is `"hwc"` or `"mission_exocat"` (never `"age_dist"`) and `activity`
  is a full chain (single-star P_rot branches only — the anchor builds no companion, so
  `tidally_locked` cannot apply). When neither catalogue lists an age (the common case) all three
  keys stay `null`; under `permissive` / a v1 dataset the activity chain is inert regardless, so
  only `age_gyr` / `age_source` can be populated.
- **`star.multiplicity`** — `null` under `permissive` / a v1 dataset (unchanged). Under
  `strict` with a v2.4+ dataset, **synthetic** mode now draws it from the
  `stellar_multiplicity` block (Phase R3-V2 B1): `{is_multiple, n_components, mass_ratio_q,
  companion, note}`, where `companion` is `null` for a single star and otherwise
  `{mass_solar, sma_au, ecc, p_orb_days, close_pair}` — the block's own `consumer_contract`
  shape, which is **exactly the `--companion` hint shape**, so a drawn companion feeds the
  same Holman–Wiegert S/P-type gate. An explicit `--companion` always overrides the drawn
  one. **Real-anchor** mode is unchanged: its `multiplicity` stays GCNS-derived
  (`{is_multiple, n_components, note}`, no `companion`) and is never overwritten by a draw.
  The companion block also carries **`wide_disruption_half_life_au`** and
  **`wide_redrawn_for_disruption`** (Phase R3-V2 B3 + v2.11.0 Q3): the wide separation follows
  a **smooth survival roll-off** `S(a) = 0.5^((a/a_half)^p)` (p ≈ 1.35, a tunable convenience)
  around the moving half-life scale `a_half ≈ 1.212 × (M_tot / t)` pc (Weinberg 1987 eq. 28) —
  **replacing the old hard truncation**: ~half the pairs at `a_half` survive and the source
  finds "no evidence of breaks or cutoffs", so the tail is thinned by separation, not walled
  off. `a_half`/the roll-off are `null`/inert without an age axis (the scale moves with mass
  and age). The `a_half` coefficient is **stars-only, solar-neighbourhood-normalized and
  orientation-blind** (WB canon `multiple-star-systems.md` §13, the X9 amendment — a scope
  disclosure, the value is unchanged); the generator applies it inside its own
  solar-neighbourhood census domain, so read `a_half` as a decay *scale* typed to that domain,
  never a hard outer cutoff.
  **A two-break power-law tail IS now added** (v2.11.0 Q4), beyond a **continuity splice** at
  ~1000 AU: the tail's PDF is set equal to the log-normal at the splice (Tian 2020 recipe →
  normalization with zero free parameters, no invented join weight), slope γ₁ −1.55 → γ₂ −2.07
  (disk). This thins the previously over-produced solar-host wide companions (the log-normal
  ran shallower than the −0.60 tail slope); M-dwarf centres (steeper log-normal) stay unthinned
  and safe.
  Two guarantees worth relying on: `ecc` is **never identically zero** (a silent `e = 0`
  makes every drawn binary maximally planet-friendly), and the circularization period is a
  **statistical boundary, not a cut** — eccentric short-period pairs are drawable (BY Dra is
  `e = 0.300` at `P = 5.98 d`). Above the boundary `ecc` is drawn from the **`f(e) ∝ e^η`**
  power law (Moe & Di Stefano 2017, period + primary-mass-dependent — v2.11.0 Q2, replacing the
  Rayleigh(0.21) placeholder; η rises with `logP` toward sub-thermal for solar-type, thermal
  for early-type), and `note` names the source.

> **v2 research-priors sampling (Phase R3-V2, under `--research-policy strict` with a v2
> dataset).** When the ingested dataset is a `schema_version` "2.0"+ contract carrying the
> optional v2 blocks, `strict` sampling changes physically (all block-gated — a v1.0 dataset
> or `permissive` is byte-identical): planet **mass** is drawn from oligarchic isolation-mass
> physics (`mass_model`); **giant occurrence / planet count / a super-Earth floor** are
> conditioned on the host `[Fe/H]` (`occurrence_by_metallicity` + the `feh_dist`/Hypatia/SIMBAD
> [Fe/H] source); neighbours are drawn **peas-in-a-pod correlated** (`intra_system_correlation`);
> and — v2.2 — a **decoupled cold-giant population** (`cold_giant_population`) places cold giants
> (planets named `"… (cold giant N)"`, `a ≥ snow_line`) from the debiased RV occurrence curve
> independent of the inner grid. The `notes` gain a `"v2 physics in effect: …"` line naming the
> active blocks + the host `[Fe/H]`. The full block schema is in `docs/research-priors-contract.md`.

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
Core function: `calculators.compute_jump_route(origin, destination, max_jump_ly, optimize="distance", via=None)`.
Output: `{origin_info, dest_info, reachable, optimize, jumps, total_ly, direct_ly, route:[{jump, from, to, jump_ly,
cumulative_ly, waypoint}], max_jump_ly, stars[], via, via_legs, unreachable_leg}`. **An unreachable destination is a
normal result** (`reachable=false`, empty `route`, **exit 0**) — not an error; it now also carries
`unreachable_leg:{from,to}` naming the hop that failed. Same origin/destination, `max_jump ≤ 0`, or an unresolvable
endpoint → `{"error"}` exit 1; `--optimize` other than `distance`/`jumps` is an argparse exit 2.

**`--via N [N …]` — required intermediate waypoints.** Stars the route must pass through, on **every `--weight`
value** (`distance`, `dust`, `blend`). They are an **unordered set**: type them in any order and the planner
visits them in whichever order is cheapest under `--optimize`, so `via` echoes back the *chosen* order, which
may differ from the typed one. Every single jump still obeys `--max-jump`; reachability is unchanged.
```bash
query.py jump-route --origin Sol --destination "38 Vir" --max-jump 15 --via "70 Vir"
query.py jump-route --origin Sol --destination "36 Oph" --max-jump 8 --via "70 Oph" --weight dust
```
Output: `via` (the **chosen** visit order when `reachable: true`; the **requested** order when `false`, since
no order was chosen — `via_legs` is `[]` there too), `via_legs` (`[{from, to, jumps, ly}]` per waypoint-to-waypoint leg; the
dust/blend forks add `a_v`), `unreachable_leg`, and a **`waypoint`** boolean on every `route[]` row — `true`
on the row that *arrives* at a waypoint at a leg boundary, flagged by route index rather than name match, so
`count(waypoint) == len(via)`. All four are **always present** (`[]`/`[]`/`null`/`false` without `--via`).

**Two consumer-visible consequences.** (1) **A waypointed route may revisit a star** — `route[]`/`stars[]` can
repeat a name, so index by position, never by name (see the 2026-07-31 change note above). (2) **`reachable:
false` no longer implies two stars**: `stars[]` carries every terminal and `unreachable_leg` names the hop that
actually failed, which with waypoints is often `origin → waypoint` rather than `origin → destination`. Adding a
far-flung waypoint can strand a route that worked without it — that is a correct result, still **exit 0**.

Errors (all curated, **exit 1**): more than **8** waypoints (`"At most 8 waypoints."`, checked before any name
resolution); an unresolvable waypoint (`"Waypoint N ('…'): <reason>"`, 1-based); and any two terminals that
resolve to the same star — including the `Sol`/`Sun` alias pair. `--via` with no value is argparse **exit 2**.
Full semantics: `docs/calculators.md` §B ("Required waypoints").

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

**A synthetic `Sol` row is included** when the center lies within `limit_ly` of the origin (same reasoning as `stars-within-star` above — Gaia does not observe the Sun, so `gcns_stars` can never hold a row for it). It fills the standard row shape with `star_name: "Sol"`, `spectral_type: "G2V"`, `app_magnitude: -26.74`, `dist_pc`/`light_years` `0.0`, `x/y/z` `0.0`, and **every other GCNS field `null`** — no `gaia_source_id`, no Bayesian distance, no Gaia photometry, since none exists. It is flagged `in_gcns: false` with `distance_method: "synthetic_sol_origin"`, so it can never be mistaken for catalogue astrometry; filter on either field to get catalogue rows only.

### Search & Filter (Phase G — local DB, except `search-exoplanets`)

The three interactive-search functions, exposed with **all filters optional** (omitting every filter returns the
first page up to the cap). Each returns `{count, capped, cap, stars[]}` (`capped=true` means the result hit the cap) or
`{"error": str}`. Spectral-class filtering uses the friendly **chips + refine** model: `--spectral-classes` takes one
or more of `O B A F G K M Other`, and `--spectral-refine` is a case-insensitive
contains-match on the rest of the type (e.g. `V` for the luminosity class). See `docs/star-databases.md` (Phase G).

> **Chip matching skips luminosity prefixes (changed 2026-07-27).** A letter chip matches the leading class letter
> after stripping a known prefix — `d` (dwarf), `sd`/`esd`/`usd` (subdwarf), the Am/Ap line-type forms `k`/`h`/`kn`,
> and the uncertain-classification forms `d/sd`/`sd:`/`s/sd`/`(sd)`. So `dM6` (Wolf 359) and `sdM3.0` now return
> under `M`, where they previously fell into `Other`. Matching is **case-sensitive**: the uppercase degenerate
> prefix `D…` (`DA`, `DZ7.5`, `DQ`, `DA+dM`) is *not* a luminosity prefix and stays in `Other`. `Other` is the
> exact complement, so no star is ever returned under both a letter chip and `Other`.
>
> Two consequences worth noting for consumers: **chip `K` returns fewer rows** than before (the ~107 lowercase
> `kA…` Am/Ap stars were previously matched by a case-insensitive `LIKE 'K%'` and are now correctly filed under
> `A`/`F`), and an Am star is bucketed by its **first** class letter, so `kA5hF0mF2` → `A` (not its hydrogen-line
> type `F`). Brown dwarfs (`L`/`T`/`Y`) and blank/NULL types are unaffected and remain in `Other`.

#### `search-star-systems`
Filter the local `star_systems` table (no network). Cap 500; sorted by light years.
```bash
query.py search-star-systems --spectral-classes M K --ly-max 20 --mag-max 10
```
Core function: `databases.search_star_systems(filters)`. Flags → filter keys: `--spectral-classes`/`--spectral-refine`,
`--ly-min`/`--ly-max`, `--mag-min`/`--mag-max`, `--designation-prefix`, and (Phase L4) `--fe-h-min`/`--fe-h-max` (an
inner JOIN onto `hypatia_cache` — matches nothing when that cache is empty; run **Import Hypatia Cache** first). Each
star: `{star_name, designations, spectral_type, parallax, parsecs, light_years, app_magnitude, ra, dec}` —
`designations` leads with the SIMBAD common name (see **Star designation strings** above), so
`--designation-prefix` now also matches a common name — but only as the **whole token including the
`NAME ` prefix**: `--designation-prefix "NAME Chara"` matches, `"Chara"` does **not** (the clause
anchors at the string start or immediately after `", "`). Catalog prefixes are unaffected. Empty
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
Core: `databases.compute_substellar_census(ly_max=None, include_late_m=False, classes=None)`. Selects rows whose `spectral_type` begins with one of `classes` **or with one of those classes behind a luminosity prefix** (`d`/`sd`/`esd`/`usd`/`k`/`h`/…), so `--classes L` also returns `sdL0`/`esdL7` (changed 2026-07-27; default `L T Y`; `--include-late-m` adds `M7/M8/M9` and now also finds `dM7`/`sdM7.0` — 73 rows the previous prefix-blind form missed); `spectral_type IS NOT NULL` (only cross-matched rows carry a type); `--ly-max` filters `light_years`; sorted by distance, capped at 500. Output: `{classes, ly_max, count, capped, cap, completeness_note, population{total_in_gcns, with_spectral_type, returned}, snapshot_date, gcns_version, stars[]}` — `stars` are the standard GCNS row shape. **`completeness_note`** is the mandatory lower-bound disclosure (GCNS substellar completeness falls off beyond ~10–25 pc; only cross-matched rows carry types).
- **Validation:** empty `gcns_stars` → `{"error"}` exit 1; `--ly-max ≤ 0` → curated `{"error"}` exit 1; non-numeric `--ly-max` → argparse exit 2; a `--classes` token that is not a class letter with an optional subtype (`L`, `T`, `Y`, `M7`, `M7.5`) → curated `{"error"}` exit 1 — the token is concatenated into a GLOB pattern and SQLite's GLOB has **no ESCAPE clause**, so `--classes '*'` would otherwise match every typed row and present arbitrary G/K/M stars as a substellar census.
- **Matching is case-sensitive (GLOB, changed 2026-07-27).** Previously `LIKE` fused the uppercase *degenerate* prefix with the lowercase *dwarf* one: `--classes D` returned 4,918 rows = 2,561 real white dwarfs **plus 2,357 lowercase-`d` M dwarfs** (`dM6`, `dM4.0`, …). `--classes D` now returns white dwarfs only.

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
Core: `dust_routing.compute_jump_route_dust(origin, destination, max_jump_ly, optimize="distance",
map_sel="auto", dust_step_pc=5.0, via=None)` / `compute_optimal_tour_dust` / `compute_multi_stop_dust` /
`compute_nearest_neighbor_dust` / `compute_trade_route_dust` (only the two `jump-route` forks take `via`). **A_V is a non-negative additive edge weight**,
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

> **Waypoints compose with the weight (2026-07-31).** `jump-route --via` works under **every** `--weight`
> value. The forks share the plain planner's `_route_through` helper and their own `edge_cost`, so the
> waypoint *visit order* is chosen under the same metric the weight selects — least-A_V ordering for
> `--weight dust`, blended for `blend`. Their `via_legs` rows carry `a_v` alongside `ly`. The
> distance-optimal comparison (`extra_ly` / `saved_av`) is computed against the **via-constrained**
> distance route, so the two sides stay like-for-like; without that threading the numbers would compare a
> constrained route against an unconstrained one and be meaningless. Note that `--optimize jumps` ignores
> `edge_cost` entirely (its BFS never calls it) — pre-existing, but waypoints make it more visible.

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
alpha=1.0, beta=1.0, map_sel="auto", dust_step_pc=5.0, via=None)`. Output mirrors the dust route's shape plus
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
Solar-system reference data, read from the local SQLite tables (`planets`/`moons`/`dwarf_planets`/`asteroids`) — **not**
from the CSVs, which are only the seed/import source. Output `{planets[], moons[], dwarf_planets[], asteroids[]}`; keys
within each body dict are the original CSV header strings (`"Semimajor Axis"`, `"Mean Radius (km)"`, …), which the SQL
aliases back, so the shape is unchanged. All values are **strings** (every column is TEXT), including numerics.
`moons` is a **dict keyed by parent planet** (`Earth, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto`), not a flat list;
the other three are lists sorted ascending by semi-major axis.
```bash
query.py solar-system
```
Core function: `science.compute_solar_system_tables()`.

**Row counts grew on 2026-08-02** (JPL expansion — see `docs/science-and-scifi.md` option 11): `moons` **21 → 43**,
`asteroids` **22 → 259**; `planets` (8) and `dwarf_planets` (5) unchanged. Purely additive — every pre-existing row is
byte-identical apart from two corrected transcription errors (the Moon's period `37.322 → 27.322` d, Ariel's
diameter/radius `2324`/`1162.2 → 1157.8`/`578.9` km). Every row is complete: there are **no empty-string cells** in
`moons` or `asteroids`, so a consumer need not guard for blanks. **But "complete" is not "numeric":** nine `asteroids`
rows (Sedna, Quaoar, Orcus, Gonggong, Ixion, Chaos, 2012 VP113, 2018 VG18, 2018 AG37) carry the literal string
`"N/A"` in `Diameter` — no diameter has ever been published for them — so `float(row["Diameter"].replace(" km",""))`
raises on those. Guard the cast. The same rows are why nothing in this table may be sorted or filtered by diameter:
a size ranking silently drops every one of them. Note `asteroids` includes TNOs/centaurs despite the table name.

> A consumer reads whatever the **local DB** holds. Counts differ between machines until each one runs option 55
> (`data/space_app.db` is gitignored and `_auto_seed` only fires on an empty table).

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

## Catalog-access tier (Phase AM — LIVE VizieR / Gaia TAP / HEASARC)

Seven subcommands that make **live network** queries to CDS VizieR, the ESA Gaia TAP archive, HEASARC,
and the Besançon Galaxy Model (via `astroquery` / direct REST, already in the venv). They are in the
same class as the `dust-*` / GCNS network paths, **not** the pure-math calculators. Cross-cutting behavior:

- **Error shape:** any failure (network, HTTP 4xx/5xx, bad id) returns `{"error": "…"}` — often with
  an additive `"route_tried": [...]` list — and exit 1. An **empty but valid** result is **not** an
  error: it returns the normal shape with `count: 0` / an empty list (a blocked route enumerates the
  alternatives instead of implying "no such object"). Always check `"error"` first.
- **Caching:** successful, non-empty results are cached by (service + query-hash) under the gitignored
  `data/catalog_cache/` with a 7-day TTL (`core/catalog_cache.py`); errors/empties are never cached.
  Set `SPACE_APP_CATALOG_CACHE=0` to disable (used to force live paths in tests).
- **Row limits / async:** VizieR/Gaia default to a finite row limit (`--row-limit -1` lifts VizieR's);
  Gaia's **sync** endpoint caps at 2000 rows, so `close-binary-census` and any population pull use an
  **async** job (no cap) internally. A sync Gaia result at exactly 2000 rows is flagged `truncated`.
- **Units + provenance:** period (days), separation (arcsec / AU), mass (M☉ + M_Jup), parallax (mas),
  distance (ly + pc). Generic gateway results carry a `column_units` map; orbit rows carry a
  paste-ready `verification` tag (`[V-PRIMARY-Gaia-DR3-NSS source_id=…]` / `[V-SECONDARY SB9 gr<N>
  <bibcode>]` / `[V-SECONDARY WDS/orb6 <ref>]`).
- **Companion masses are estimates, always labelled** with their `method` (`astrom` Thiele-Innes /
  `spec-min` SB1 sin i=1 lower bound / `SB2` double-lined) and a `caveat`. Class thresholds:
  M₂ > 0.075 M☉ → `stellar`; 0.013–0.075 → `brown-dwarf`; < 0.013 → `planet`; astrometric a₀ ≲ 1 mas →
  `low_significance: true`.

#### `vizier-query`
Any VizieR catalog by id → JSON rows. `--filters` is repeatable (`'col op val'`, e.g. `'Per < 365'`);
`--cone` is `'ra dec radius'` (deg); `--columns` trims the (often wide) column set; `--row-limit -1`
is unlimited.
```bash
query.py vizier-query --catalog B/cb/cbdata --filters "Name = GK Per"
query.py vizier-query --catalog B/sb9/orbits --filters "Per < 365" --row-limit 500
```
Core: `catalog.vizier_query(catalog, columns=None, filters=None, cone=None, row_limit=2000)`. Output:
`{service:"vizier", catalog, count, row_limit, truncated, column_units:{…}, rows:[{col: val, …}]}`.
Reuse targets: `B/sb9/*` (SB9), `B/wds/wds`, `B/orb6/orbits`, `B/cb/cbdata` (Ritter & Kolb CVs),
`B/gcvs`, `I/311/hip2` (Hipparcos).

#### `gaia-tap`
Any Gaia DR3 table by raw ADQL (`--adql`, takes precedence) or structured
(`--table`/`--columns`/`--where`/`--cone`). `--async` uses an async job (no 2000-row cap) for
population pulls.
```bash
query.py gaia-tap --adql "SELECT source_id, parallax FROM gaiadr3.gaia_source WHERE source_id=425040000962559616"
query.py gaia-tap --table gaiadr3.nss_two_body_orbit --where "parallax > 50 AND period < 365" --async
```
Core: `catalog.gaia_tap(adql=None, table=None, columns=None, where=None, cone=None, row_limit=2000,
use_async=False)`. Output: `{service:"gaia", query, count, async, truncated, column_units, rows:[…]}`.

#### `heasarc-query`
A HEASARC X-ray catalog by cone (`--catalog` + `--cone 'ra dec radius'`) or raw TAP (`--adql`).
```bash
query.py heasarc-query --catalog rassbsc --cone "79.1723 45.998 0.5"
```
Core: `catalog.heasarc_query(catalog, cone=None, radius=0.1, adql=None, row_limit=2000)`. Output:
`{service:"heasarc", catalog, count, column_units, rows:[…]}`. Serves the binary activity/flare +
CV/compact-object identification story.

#### `binary-orbit`
Every orbital solution for one star across the tool-split (Gaia NSS → SB9 → WDS/orb6), each with a
companion-mass estimate + `class` + a `verification` tag. Resolve by `--star` (SIMBAD), `--source-id`
(Gaia), or `--ra`/`--dec`. **The planet filter is baked in** (GJ 876's 61 d NSS "orbit" classifies as
`planet`, not a stellar binary). **No solution → an explicit empty `solutions` list + `route_tried` +
a `note`**, never a silent empty (failed-tool ≠ absent-capability).
```bash
query.py binary-orbit --star "delta Trianguli"
query.py binary-orbit --star "GJ 876"          # 61.36 d solution → class "planet"
```
Core: `binary.binary_orbit(star=None, ra=None, dec=None, source_id=None)`. Output:
`{query, identity:{main_id, ra, dec, sp_type, parallax_mas, distance_ly, gaia_source_id, hip},
solutions:[{source, solution_type|seq, period_d, eccentricity, grade, primary_ref,
separation_arcsec, separation_au, component, companion:{method, m1_solar, m2_solar, m2_mjup, a0_mas,
a1_au, mass_function, class, low_significance, caveat, mass_ratio_q?, binary_masses?}, verification}],
route_tried:[…], route_errors?, note?, units:{…}}`. The **`companion.binary_masses`** sub-block (§3.3)
is the **independent Gaia `gaiadr3.binary_masses` cross-check**, present only when Gaia derived a mass
for that source: `{m1_solar, m2_solar(+m2_lower/upper), fluxratio, combination_method, m1_ref,
agreement_pct?}` (`agreement_pct` = |our m2 − Gaia m2| / Gaia m2 × 100, when both are numeric). Our
Thiele-Innes/SB1 estimate stays the **primary** `m2_solar`; `binary_masses` cross-checks it, or — when
our tool-split produced no mass but Gaia's `m2` is non-null — **fills** it (`method:"gaia-binary-masses"`).

#### `close-binary-census`
The systematic population sweep (Gaia NSS faint + SB9 bright with Hipparcos/Gaia parallax → X-Match
dedup → companion classification → planet filter). `--drop-planets` is **on by default** (opt out with
`--keep-planets`).
```bash
query.py close-binary-census --dist-max-ly 65 --period-max-d 365
query.py close-binary-census --dist-max-ly 100 --period-max-d 365 --include nss,sb9 --exclude-known census.txt
```
Core: `binary.close_binary_census(dist_max_ly, period_max_d, sep_max_au=None, include=("nss","sb9"),
parallax_source="both", drop_planets=True, separate_wide=False, exclude_known=None)`. Output:
`{query:{…}, count, counts_by_class:{stellar, brown-dwarf, …}, census:[<per-system rows, same shape as
binary-orbit solutions + ra/dec/distance_ly/also_in>], excluded_planets:[…], wide:[…],
coverage:{catalogs_swept, catalogs_not_swept, requested_not_implemented, dist_max_ly, period_max_d,
parallax_min_mas, parallax_source, notes:[…]}, route_errors?, units:{…}}`. `--include` accepts
`nss,sb9,wds,cv` (default `nss,sb9`); **only `nss`/`sb9` are wired as
sweep sources** — a requested but unimplemented `wds`/`cv` is reported honestly under
`coverage.requested_not_implemented` (never silently dropped; both are reachable directly via
`vizier-query --catalog B/wds/wds` / `B/cb/cbdata`), and an **unknown** `--include` token → a curated
`{"error"}`. The `coverage` block is **never** empty and never implies exhaustive. Bulk NSS companion
masses assume a solar-mass primary (per-system `binary-orbit` gives the spectral-typed refinement + the
`binary_masses` cross-check).

**Dedup — a census row is one SYSTEM, not one catalogue row.** Two mechanisms, plus an accounting block:

- **Intra-source.** One Gaia `source_id` can carry several NSS orbit solutions of very different quality.
  They collapse to the **highest-graded** one; the rest are surfaced, not dropped, via
  `n_orbit_solutions`, `sole_solution` and `other_solutions[{period_d, eccentricity, grade,
  solution_type}]`. Each row now also carries its Gaia **`solution_type`**.
- **Cross-route, identity-first.** An SB9 row is matched to an NSS row by **Gaia `source_id`** (resolved
  from a dedicated wide X-Match — SB9's coordinates are coarse enough that the 5″ parallax X-Match
  resolves almost none of them). A match single-counts and sets `also_in:["sb9"]`, `sb9_period_d`,
  `sb9_ref`. Where identity cannot be resolved, positional proximity **flags** (`possible_duplicate_of`)
  and **never merges** — two real close pairs can share one position (Castor carries two), so merging on
  proximity alone would *under*-count. A second SB9 orbit resolving to an already-merged Gaia source is
  likewise kept and flagged rather than absorbed.
- **Disagreement is surfaced, never silently resolved.** When both routes describe the same star but the
  periods differ by >5%, the row carries `period_disagreement:{nss_period_d, sb9_period_d,
  nss_solution_type, nss_grade, sb9_ref}`. This is load-bearing: that disagreement is what identified two
  spurious Gaia solutions (FK Aqr, BY Dra — in both, a low-grade `OrbitalTargetedSearch` against an SB9/SB2
  value matching the primary paper). The census does **not** pick a winner.
- **`dedup:{possible_duplicates, period_disagreements, multi_solution_sources,
  cross_route_single_counted}`** — the honest caveats on the "one row = one system" claim.

**No quality verdict is manufactured.** There is deliberately no "distrust low-grade rows" or "distrust
short-period rows" rule: a *sole* solution is flagged with its `solution_type` and `grade` and left to the
caller, because G 184-19 (sole `SB2`, grade 126, e = 0.685 at 2.535 d) and Wolf 227 (sole
`OrbitalTargetedSearch`, grade 38) are told apart by **type plus whether a rival row exists**, not by grade
alone — and the NSS grades run 2.9–270.7 with a median of 44.4, so any cutoff would flag much of the census.

#### `gaia-astrophysical`
Gaia GSP-Phot + FLAME stellar parameters (incl. **age**) for one source, by `--star` (SIMBAD →
source_id) or `--source-id`. Every FLAME age carries a model-dependence caveat.
```bash
query.py gaia-astrophysical --star "eta Cas A"
```
Core: `catalog.gaia_astrophysical(star=None, source_id=None)`. Output: `{query, source_id, identity,
parameters:{teff_gspphot, logg_gspphot, mh_gspphot, radius_gspphot, mass_flame, radius_flame,
lum_flame, age_flame, age_flame_lower, age_flame_upper, evolstage_flame}, caveats:{age_flame:"…"},
units:{…}}` (`parameters: null` + a `note` when the source has no astrophysical_parameters row).

#### `besancon-query`  (needs a BGM account)
Queries the **Besançon Galaxy Model (`m1612`)** for a synthetic field population and derives the T8
`age_dist` summary. **Not `astroquery.besancon`** (which targets the dead 2003 email/FTP path) — this
drives the modern **UWS 1.0 REST web service** at `model.obs-besancon.fr/ws/` directly. Credentials come
from `BESANCON_USER` / `BESANCON_PASS` (register at `https://model.obs-besancon.fr/ws/subscribe.php`; put
them in `~/.zshenv` so subprocesses inherit them). Missing creds → a curated `{"error"}`, not a crash.
`--local` uses a representative mid-latitude sightline (l=90, b=45); the `--dist-max-pc` cut isolates the
solar-neighbourhood slice.
```bash
query.py besancon-query --local --dist-max-pc 150 --area 1.0
query.py besancon-query --glon 120 --glat 30 --dist-max-pc 200 --mag-max 18
```
Core: `besancon.besancon_query(glon=None, glat=None, local=False, area_deg2=1.0, dist_max_pc=100.0,
mag_max=None, sample_max=1000, contact_email=None)`. Output: `{query, model_version:"m1612", n_stars,
columns:[…], catalogue_sample:[<per-star: Age, Mass, [M/H], [a/Fe], Pop, Teff, logg, Dist, UU/VV/WW, …>],
catalogue_truncated, age_dist:{histogram, mean_age_gyr, median_age_gyr, mass_conditional_age,
population_mix:{thin,thick,halo,bulge}, population_by_pop_code, age_metallicity_relation, feh_mean,
feh_std}, coverage:{model, sightline_lb, dist_max_pc, verify_against_observation:true, notes:[…]},
units:{…}}`.

**Safeguards (this is a small, individually-hosted academic server — treat it gently):** results are
**cached 30 days** (an identical query never re-runs the model — the main protection against repeated
requests); polling uses the reference client's **30 s cadence**, **one job at a time**; every job is
**deleted after retrieval** (no accumulation); `sendmail=0`; `--area` (solid angle, deg²) is **capped at
10** (smallfield-only model — tile for wider surveys); jobs carry a server-side `EXECUTIONDURATION`; and
the `User-Agent` identifies the BGM login. **The output is a synthetic model, not observation** — every
result carries `verify_against_observation: true`; the consumer must cross-check the age distribution
against observational field ages before pinning the `age_dist` prior.

## Two-step subcommands

For subcommands that run SIMBAD first (`star-regions`, `exoplanets`, `planetary-systems`, `hwo-exep`, `mission-exocat`, `hwc`, `hypatia-data`): if the SIMBAD lookup returns `{"error": ...}`, that error is returned immediately and the second core function is never called.

`dossier` (Phase Q) runs SIMBAD first for a real star and aborts with that error if it fails; per-section sources that fail *after* SIMBAD resolves become warnings, not errors. `dossier --star Sol`/`Sun` runs no SIMBAD/network step at all (the offline reference-origin path; it reads the local Solar System tables, overridable via `SPACE_APP_DB`).

`generate-system` (Phase R1) runs **no network in synthetic mode** (no `--anchor-star`). With `--anchor-star` it runs SIMBAD first (then `compute_star_system_regions_from_simbad` + NASA pscomppars / HWC); an unresolvable anchor or a non-OBAFGKM (e.g. white-dwarf) regions failure is returned immediately as `{"error": ...}`, while missing observed planets is a `warnings[]` entry, not an error.

The `gcns-within-sol`, `gcns-source`, and `gcns-system` subcommands are **local DB reads** (no SIMBAD step). The `gcns-distance` / `gcns-travel-time` / `gcns-stars-within-star` calculators are local DB reads **except** for `--star…` endpoints, which add a SIMBAD name-resolution step (a SIMBAD error on any `--star…` endpoint is returned immediately). The DB path can be overridden with the `SPACE_APP_DB` environment variable (used by tests).

`circumbinary-hz` (Phase T1a/T1b) is **offline in its numeric mode** (`--teff1/--lum1/--teff2/--lum2`); its `--star1/--star2` mode adds a SIMBAD lookup per star (→ `compute_star_system_regions_from_simbad` for teff/luminosity), returning a SIMBAD/regions error immediately. The two modes are mutually exclusive (both, or one star only, or a partial numeric set → argparse-style exit 2). All other Phase T1b calculators (`rv-semi-amplitude`, `transit-signal`, `astrometric-signal`, `direct-imaging`, `tidal-heating`, `kozai-lidov`, `relativistic-brachistochrone`) are pure-compute, no network.

### Phase AT (Packet 38.1) — weapons / defenses / engagement physics

Four `query.py`-only, pure-math, self-validating calculators (`core/salvo.py` W1 + `core/weapons.py`
W2/W3/W4 + bundled `core/weapons_tables.py`). No network, DB, RNG, time, or numpy. Every mode/channel
echoes its complete resolved input set including defaults (R3). Bundled defaults (W4 partition
fractions, W3 Whipple Al thresholds + crater exponent) are **labelled-illustrative and overridable**
(the `*-theoretical` convention). See `completed_plans/PHASE_AT_PLAN.md`.

#### `salvo-exchange`  (W1)
The Hughes Ch. 13 salvo model of missile combat: a discrete-pulse force-on-force exchange between
forces A and B. Base engine (per-unit striking α/β, defence a₃/b₃, staying a₁/b₁; scouting σ,
alertness δ, leaker floor L):
`ΔB = clamp(max(σ_A·α·A − δ_B·b₃·B, L_A·σ_A·α·A)/b₁, 0, B)` and the mirror for ΔA. **α/β and a₃/b₃ are
PER UNIT** (aggregate = ×force); losses may be fractional (aggregated task elements). Provide striking
directly (`--alpha/--beta`) or as `--a-salvo × --a-hitprob` (`α = a₂·H`). The un-clamped surplus beyond
annihilation is `overkill_*`; `exchange_ratio = ΔB/ΔA` (null when ΔA = 0).
- `--mode simultaneous` (default) — both salvos vs pre-salvo forces.
- `--mode first-strike --first {a,b}` — one side strikes; the loser's survivors return fire (two pulses
  + `final_survivors_a/b`).
- `--mode sequential-waves --first {a,b} --wave-size N --n-waves K [--defender-magazine M --defender-preempts]`
  — **two-sided** wave attack (WB MSG 025 + 029): each wave is a **simultaneous** base-engine exchange between
  the wave and the current defender — the wave's **full already-launched salvo** hits the defender, reduced only
  by the defender's **defence a₃** (the defender's *offence* kills wave ships but does **not** suppress the salvo),
  while defence **reloads every wave** and defender staying-power hits **accumulate**. `--defender-magazine` caps
  the defender's *offensive* return salvos (a dry magazine still defends via a₃ and still takes wave damage — the
  shot-your-bolt dynamic); omit for unlimited. `--defender-preempts` is the out-ranging case (defender offence
  suppresses the salvo → only offence-survivors deliver; default off = simultaneous). Per-wave + cumulative output.
- `--mode break-even` — the B:A count ratio for parity in fractional losses (Hughes' numerical-superiority
  theorem: n× the numbers ⇒ each unit needs n× α, a₃, a₁).
- `--mode solve-force --solve-for {a,b}` (`--target-delta X` \| `--target-frac-loss f`) `[--target-side {a,b}]`
  — invert for the force achieving a target loss (absolute Δ or fractional Δ/force) on a side. Returns
  `required_force_exact` + `integer_wave` (ceil). Default `--target-side` = the opposite side for an
  absolute Δ, the solved side for a fractional loss.
- `--mode distribute --fire-fraction f [--first {a,b}]` — concentration of fire: the attacker's whole
  salvo onto a fraction f of the enemy; **only the targeted subset defends** (no mutual support — WB MSG
  025 ruling A). Returns `delta_targeted`, `targeted_count`.
- `--mode layered-defense --rings "δ:b₃:leak, …" (--inbound-salvo N | --alpha + --a-force) [--scouting σ --target-staying a₁]`
  — one inbound salvo cascaded through K defensive rings (WB MSG 027, disjoint from sequential-waves):
  `survivors_j = max(incoming_j − δ_j·b₃_j, L_j·incoming_j)`, outermost→inner. Returns a per-ring table,
  `survivors_to_target`, and `delta_target` (leakers/a₁) when `--target-staying` is given.
- `--leak-a/--leak-b > 0` applies the saturation floor to any mode. Validation is a **core** check →
  curated `{"error"}` **exit 1** (bad `--mode` / choices → argparse **exit 2**).
```bash
query.py salvo-exchange --a-force 10 --b-force 10 --alpha 3 --beta 3 --a1-staying 2 --b1-staying 2 --a3-defense 2 --b3-defense 2   # ΔA=ΔB=5
query.py salvo-exchange --mode solve-force --a-force 7 --a1-staying 1 --b1-staying 1 --a3-defense 1 --beta 3.88 --alpha 1 --solve-for b --target-delta 7 --target-side a   # 3.61 → 4
query.py salvo-exchange --mode layered-defense --inbound-salvo 100 --rings "1:30:0.1, 1:30:0.1, 1:30:0.1"   # survivors_to_target=10
```

#### `beam-weapon-engagement`  (W2)
Directed-energy reach & lethality in the vacuum diffraction-limited regime. `θ = k·M²·λ/D` (shared
`angular-resolution` kernel; k=1.22 Rayleigh default), far-field spot **diameter** `d = 2θR`. Fraction on
a target of size s: **top-hat** `η·min(1,(s/d)²)` (the headline for intensity/dwell) and a **Gaussian
encircled-energy** `η·(1−exp(−2(s/d)²))` (the Airy figure would need Bessel; the Gaussian is the standard
closed-form beam-weapon model, noted in `model_note`). `I = f_on·P/A_target`, `A_target = π(s/2)²`;
`t_kill = Φ_kill/I`. `Φ_kill` supplied directly, or `--target-material-enthalpy-jkg × --target-areal-density-kgm2`.
`effective_range_spot_m` (d = s) and, with `--max-dwell-s`, `effective_range_dwell_m` (t_kill scales ∝ R²
beyond R_spot). Echoes `light_travel_time_s = R/c`. `intensity_on_target_wm2`/`dwell_to_kill_s` use the
spec's **target-averaged** convention, so dwell is conservative when `spot_smaller_than_target` — the
actual on-spot peak is `peak_spot_intensity_wm2` (= η·P/A_spot; equal to the target-averaged value in the
spill regime). Vacuum only (no atmospheric blooming).

#### `kinetic-kill`  (W3)
Hypervelocity impactor vs armor. KE both **classical** ½mv² and **relativistic** (γ−1)mc² (composes
`relativistic-energy-momentum`), regime flag at β>0.1 (`ke_j` = the regime pick). `tnt_equiv_t = KE/4.184e9`
(tons); `specific_energy_jkg`; `momentum_kgms`. Penetration **headline** = hydrodynamic long-rod
`P ≈ L·√(ρ_i/ρ_t)` (needs rod geometry — mass-only → `penetration_depth_m: null` + reason); the crater form
`P/d ∝ (ρ_i/ρ_t)^0.5·(v/c_t)^n` is a **labelled order-of-magnitude** alternative (n = 2/3 default,
spacecraft-shielding regime — Cour-Palais/MMOD; overridable, CP2 pins it). Strength-vs-hydrodynamic regime
from v vs `--target-sound-speed-ms`. `--target-type monolithic` → `perforates` vs `--armor-thickness-m`;
`--target-type whipple` → `impactor_shattered` (v vs the **present-day-Al reference** thresholds, override
for advanced armor) + a crude areal-overmatch `rearwall_defeated` (compose `shielding-attenuation` for a
real wall calc). At β>0.1 the penetration models are flagged non-relativistic / reference-only.

#### `warhead-effects-at-standoff`  (W4)
Warhead lethality radius in vacuum — **no blast wave**, kill is by radiated/particulate fluence.
`Φ_i = f_i·Y/(4πR²)` per channel; `R_kill,i = √(f_i·Y/(4π·Φ_th,i))`; overall `killed_at_range` (any
channel with `Φ_i ≥ Φ_th,i`); `binding_channel` (largest kill radius). Yield is an **input**
(`metric-drive-power` / `annihilation-power-train` are the yield source). Partition fractions default by
`--warhead-type` (**labelled-illustrative**, per-channel overridable via `--f-*`); they may sum to < 1
(`escaping_fraction` leaves as non-lethal / neutrino radiation — notably antimatter). Kill thresholds are
the target's per-channel hardness (`--threshold-*-jm2`). A channel with fraction 0 is omitted from
`channels` — **unless** a kill threshold was supplied for it, in which case it is emitted **inactive**
(fluence 0, `killed_at_range` false, a `note`) so a supplied input is never silently dropped.
```bash
query.py warhead-effects-at-standoff --yield-kt 1 --warhead-type fission --standoff-m 1000 --threshold-xray-jm2 1e6   # R_kill ≈ 500 m
```

All four Phase AT calculators are **pure-compute, no network**; core validation is a curated `{"error"}`
(exit 1), argparse errors (bad choices, non-numeric, required mutually-exclusive groups) are exit 2.

## Star-analysis change requests (CR-1 … CR-7 — for the star_analysis skill)

Seven subcommands built from the `spaceapp-change-request-spec.md` contract. **CR-1/2/3** make **LIVE**
VizieR/SIMBAD/Gaia queries (same network class as the Phase AM catalog tier — `{"error", route_tried}` on
failure, an empty-but-valid result is not an error); **CR-4/6/7** are pure-math self-validating (curated
`{"error"}` exit 1, argparse exit 2) with `network only on the optional --star path`. Every non-detection
returns an **upper limit / explicit empty, never a null**.

**CR-4/CR-6 WB bundles.** `nuclear-inventory`'s fissile output consumes the WB **3c FINAL** fissile-GCE model —
**integrated 2026-08-15** (`provenance.gce_model_version = "3c-v1.0.0-2026-08-15"`, `confidence:"extrapolation"`).
It is the **age-dependent** uniform-production survival integral (`g_i = (1−e^(−λ_i·D))/(λ_i·D)`,
`D = max(0, D_eff−age)`, `D_eff=11.55`) — not the earlier constant-g provisional (they agree only at the solar
anchor). `detection-completeness`'s fallback defaults consume the WB **3a FINAL** survey-completeness reference —
**integrated 2026-08-15** (`assumptions.reference_version = "3a-v1.1.0-2026-08-15"`, `confidence:"extrapolation"`).
Four WB consumption rulings (channel MSG 048/050) are wired: **RV effective floor = max(precision, sp_type-keyed
jitter)** (O/B/A=5, F=3, G/K/M=1.5 m/s — the Kraft-break bump keeps a Neptune from reading detectable around an
RV-hostile A star); **transit default = TESS-only** all-sky (Kepler's deeper fixed-field floor is a
`--transit-precision-ppm` override, not an off-field default); the **transit >12-mag and astrometry >15-mag faint
tails prefer the analytic noise model** (TESS Kunimoto 2022 σ₁ₕᵣ(Tmag) / ESA Gaia σϖ(G)) over the binned scalar,
which was knowingly optimistic there (~4× near G20); and **imaging carries an H-band self-luminous
`mechanism_caveat`** — its `min_radius_earth` inverts *reflected* contrast against a *thermal self-luminous* floor,
flagged (not reconciled) so a consumer never reads it as a literal reflected-light limit (WB DV-7).

#### `debris-disk` (CR-1 — LIVE)
Observed IR-excess / debris disk for one star. Cross-matches **Chen et al. 2014** (`J/ApJS/211/25`, Spitzer,
per-component L_IR/L*) + **Cotten & Song 2016** (`J/ApJS/225/15`, WISE + IRAS/MIPS + **Herschel** PACS/SPIRE
far-IR; `Tau` is L_IR/L* in units of 1e-4). Both catalogues' components are reported, ref-tagged. Undetected
→ a per-star **AllWISE W4** warm-dust upper limit (documented survey floor when W4 is absent).
```bash
query.py debris-disk --star Vega           # detected → components
query.py debris-disk --star "18 Scorpii"   # non-detection → upper_limit (never null)
```
Core: `debris_disk.debris_disk(star=None, source_id=None, ra=None, dec=None)`. Output: `{star, components:
[{type:warm|cold, L_IR_over_Lstar, T_dust_K, R_disk_au, band, ref}], detection: detected|upper_limit,
upper_limit_L_IR_over_Lstar, system_L_IR_over_Lstar?, catalogs_matched?, upper_limit_basis?,
upper_limit_regime?, route_tried}`. **Upper limits are warm-regime (WISE W4); cold Kuiper-analog dust needs
the far-IR path** (carried by the Cotten cold components on a detection).

#### `multiplicity` (CR-2 — LIVE)
Multiplicity / spectroscopic-binary summary surfaced by default. Composes the cheap SIMBAD **otype** hint
(also now on `simbad-lookup`'s new `otype`/`multiplicity` keys), the `binary-orbit` tool-split (per-component
basis + SB1 lower-bound masses), and the offline GCNS resolved-system count.
```bash
query.py multiplicity --star "alpha Centauri"
```
Core: `binary.multiplicity_summary(star=None, source_id=None)`. Output: `{star, is_multiple, n_components,
components:[{basis, sb_flag, sep_au?, m2_solar_lower?}], sb_flag, sources, note?}`. `basis` ∈ visual /
astrometric / SB1 / SB2 / eclipsing / spectroscopic; **SB1 masses are always the sin i=1 lower bound**.

#### `binary-stability-auto` (CR-3 — LIVE)
Auto-pipes `binary-orbit` → Holman-Wiegert stability in one call (no manual re-entry). Picks the best
solution, derives the binary relative semi-major axis via Kepler III (period + masses), and runs the S/P-type
critical-SMA calc. A visual pair without a companion classifier falls to a primary-spectral-type equal-mass
estimate. **`elements: null` + a `note` is a correct find≠fabricate result**, not a failure: a solution with no
absolute masses AND no period (SB2-only / WDS-projected-separation / no period-bearing orbit in any route) can't
yield a relative `a`. It resolves wherever the catalog carries masses+period (e.g. α Cen: SB9 masses → S-crit
2.6 AU). **Note on 36 Oph:** the canonical anchor (M1=M2=0.85, e=0.92 → S-crit 0.30–0.47 AU, test 1 AU unstable)
is only reproduced when a **period-bearing** orbit is supplied — 36 Oph itself is absent from orb6 (WDS-only, no
period) so the *live* `--star "36 Ophiuchi"` returns the honest null; supply the elements to `binary-stability`
to see the 0.30–0.47 AU numbers.
```bash
query.py binary-stability-auto --star "alpha Centauri" --test-sma-au 1.0   # SB9 masses → stability verdict
query.py binary-stability-auto --star "36 Ophiuchi"    --test-sma-au 1.0   # honest null (36 Oph not in orb6)
```
Core: `binary.binary_stability_auto(star=None, ra=None, dec=None, source_id=None, test_sma_au=None)`. Output:
`{star, elements:{m1_solar, m2_solar, sma_au, ecc, source, grade, mass_basis, a_basis}|null,
stype_critical_au, ptype_critical_au, mass_ratio, test_sma_au, test_verdict: stable|unstable|null,
orbit_type, e_out_of_hw_range, route_tried, note?}`. **`e_out_of_hw_range`** flags an eccentricity past the
Holman-Wiegert 1999 fit domain (e≤0.8) — the verdict stays robust, the exact critical SMA is an extrapolation.
`--test-sma-au 0` (or negative) is a curated `{"error"}` before the network call.

#### `nuclear-inventory` (CR-4 — pure-math; fissile consumes the WB 3c bundle)
Fusion-fuel + fissile (U/Th) + radiogenic-heat inventory from stellar scalars.
```bash
query.py nuclear-inventory --fe-h 0 --age-gyr 4.567 --eu-h 0    # solar → U235/U238 ≈ 0.00726
```
Core: `nuclear.compute_nuclear_inventory(fe_h, age_gyr, eu_h=None, eu_fe=None, star_mass_solar=None,
population=None, ba_eu=None, age_soft=False)`. Output: `{fusion:{D_over_H, He3_est, Li6, Li7, B11},
fissile:{U235_frac, U238_frac, Th232_frac, U235_U238_ratio, u_over_h, th_over_h, a_u, a_th}|{note},
radiogenic_heat_W_per_kg, radiogenic_heat:{value_W_per_kg, computable, components_W_per_kg:{U235,U238,Th232,K40},
actinide_scaling, note, provenance}, provenance:{gce_model_version, confidence, domain_ok, domain_note,
domain_reasons, per_output, flags, bands, …}, inputs}`. **`fissile` needs a tracer** (`--eu-h`
xor `--eu-fe`); absent → `fissile.note` (not null). `fissile.{u_over_h,th_over_h,a_u,a_th}` are the absolute
**tonnage** (Eu-scaled), beyond the Eu-independent fraction keys. `--eu-h`/`--eu-fe` are an argparse
mutually-exclusive group.

**CR-10.2 rider — [Fe/H]-upper soft-flag (CQ-7-3c-6):** `[Fe/H] > +0.5` is now a soft `feh_extrapolation` flag on the
K-40 `radiogenic_heat` channel (+ `provenance.per_output`), NOT a global void — the fissile fraction stays valid. See
the CR-10 block below.

**CR-9 riders — 3c defect fixes CQ-7-3c-1…4 (post-fulfilment CR-4 corrections; WB MSG 079 pin):**
- **CQ-7-3c-1 (radiogenic-heat Eu-wiring).** The U/Th (r-process) heat channels now scale with the star's
  **[Eu/H]-driven GCE actinide inventory** relative to the solar anchor (`g_i(A)/g_i(solar)·exp(λ_i(solar−A))·
  10^[Eu/H]`), K-40 by a `10^[Fe/H]` proxy — no longer the Eu-blind co-formation form (which inverted DV-6).
  With **no r-process tracer the heat is WITHHELD** (`radiogenic_heat_W_per_kg = null`,
  `radiogenic_heat.computable = false`) — never back-filled with `10^[Fe/H]`; the K-40 partial is shown for
  reference. `radiogenic_heat.provenance` inherits the domain flags (DV-2/DV-3/DV-4/DV-6). Solar anchor
  (~5.0e-12 W/kg) is byte-stable.
- **CQ-7-3c-2 (DV-1 + DV-3).** `--age-soft` sets the DV-1 *advisory* order-of-magnitude flag (`flags.age_soft`;
  a band, **not** a veto). DV-3 s-process: `--ba-eu` ([Ba/Eu], preferred discriminant — ≥ +0.5, the CEMP-s cut, ⇒ s-dominance;
  solar 0 / pure-r ≈ −0.7 stay clean) else the runbook proxy (a high [Eu/Fe] on a thin-disk, non-metal-poor
  star ⇒ likely AGB/Ba pollution) → `flags.s_process`,
  which voids the **tonnage/heat** but **not** the Eu-independent isotope ratio.
- **CQ-7-3c-3 (band boundaries).** DV-4/DV-7 band edges are `>=`/`<=` (age exactly 4.0/8.0 and the 11.5–11.55
  sliver now land in a band).
- **CQ-7-3c-4 (tri-state + per-output + multi-reason).** `provenance.domain_ok` is **tri-state**:
  `true` / `false` (a veto fired) / **`null`** (Eu-dependent guards unevaluable — no tracer). `provenance.per_output`
  gives the severity per output (`isotope_ratio` / `tonnage` / `radiogenic_heat` ∈ ok/extrapolated/unreliable/
  void/unevaluable). `provenance.domain_reasons` lists **all** fired vetoes (no `elif` shadowing);
  `provenance.domain_note` joins them.

#### `detection-completeness` (CR-6 — pure-math; defaults consume the WB 3a FINAL v1.1.0 bundle)
Per-method minimum detectable planet (mass M⊕ or radius R⊕) vs orbital SMA — a completeness map inverting the
four detection-limit calculators. Survey capability from a per-star override or the 3a defaults keyed by
apparent magnitude. Defaults: RV floor = max(precision, sp_type-keyed jitter); transit = TESS all-sky; the
transit >12-mag / astrometry >15-mag faint tails use the analytic noise model (TESS Kunimoto / Gaia σϖ(G))
instead of the bin scalar; imaging is an H-band self-luminous floor carrying a `mechanism_caveat` (see the
CR-4/CR-6 WB-bundles note above).
```bash
query.py detection-completeness --app-mag 4.83 --distance-pc 10 --sp-type G2V   # Earth@1AU below the floor
query.py detection-completeness --star "Tau Ceti"                               # --star resolves mag/dist/sptype (live)
query.py detection-completeness --star "HD 69830"                               # CR-10.3: tier-2 RV catalog hit (seed) → floor_provenance="catalog"
query.py detection-completeness --star "HD 69830" --rv-precision-catalog PATH   # WB-owned catalog file (replaces the internal seed)
```
Core: `detection.compute_detection_completeness(app_mag, distance_pc, sp_type=None, star_mass_solar=None,
star_radius_solar=None, methods=None, sma_grid=None, albedo=0.3, rv_precision_ms=None, rv_baseline_yr=None,
transit_precision_ppm=None, transit_target=False, astrom_precision_uas=None, astrom_baseline_yr=None,
star=None, activity=None, star_mass_provenance=None, rv_precision_provenance=None, rv_precision_meta=None)`.
Output: `{star, app_mag, distance_pc, sp_type, host_class, star_mass_solar, star_mass_provenance,
star_radius_solar, methods:[{method, applicable, detectable_vs_sma:[{sma_au, min_mass_earth?|min_radius_earth?,
…}], floor_source, floor_provenance, value_kind, baseline_yr?, contrast_band?, mechanism_caveat?, jitter_advisory?,
jitter_note?, note?}], assumptions:{reference_version, confidence, out_of_domain, host_class, host_class_note, …}}`.
`floor_source` names the basis per method (manual `per-star override` / **CR-10.3** per-star catalog string /
binned 3a scalar / analytic noise-model σ at the actual mag); **`floor_provenance`** (CR-10.3) is the machine-readable
tier per method (`manual`/`catalog`/`generic-3a`, or `null` on a non-applicable entry; `catalog` only ever on `rv`).
The imaging method dict carries `contrast_band:"H"` + `mechanism_caveat`. **Non-MS host guard (CR-6-AMEND):** when `sp_type` resolves to a **white dwarf / hot
subdwarf / giant / subgiant / brown dwarf**, `host_class` is set, `out_of_domain:true`, and the MS mass/radius +
sp_type→jitter defaults are **not faked** (`DA2` no longer → a 1.6 M☉ A star); it still computes on explicit
`--star-mass-solar`/`--star-radius-solar` (flagged, flat RV jitter), else the methods are flagged/skipped with a
`note`. A normal dwarf (`…V`) is unchanged (`host_class:null`, `out_of_domain:false`).
**Monotonicity is per-method** (RV min-mass hardens with SMA; transit min-radius is SMA-independent;
astrometry/imaging ease, gated at P>baseline / inside the IWA). **Transit is `applicable:false` unless
`--transit-target` / `--transit-precision-ppm`** is given (honest "not covered").
**CR-10.4 rider — archive-M★ preference.** On the `--star` path M★ prefers the archive `ps` value batch reports
(precedence manual > archive > sp_type_estimate); a new `star_mass_provenance` field names the tier. See the CR-10
block below.

**CR-10.3 rider (second fire) — per-star RV-precision tier-2 catalog.** RV-floor precedence **manual
`--rv-precision-ms` → per-star catalog → generic 3a**; `--rv-precision-catalog <path>` reads a WB-owned JSON that
**replaces** the internal HD 69830 seed wholesale (bad path → curated `{"error"}`, loud even with a manual override).
Per-method `floor_provenance` names the tier. Fires only on the `--star` path (SIMBAD supplies the match key). See
the CR-10 second-fire block below.

**CR-9 rider — Companion CR#1 (RV jitter bumps, advisory placeholder).** Two symmetric jitter floors beyond
the MS Kraft-break map: an **evolved-star** bump (subgiant/giant p-mode+granulation — fires for `host_class`
subgiant/giant with explicit M/R) and an **active/young cool-dwarf** bump (fires when `--activity {active,young}`
is given on a G/K/M host). When either applies, the RV method dict carries `jitter_advisory:true` + a
`jitter_note`. **The bump magnitudes are an un-cleared LEAD — advisory PLACEHOLDER only** (WB pins the jitter–L/M
scaling in Phase 5); the consumer treats an un-pinned bump as advisory (flag, not a hard `likely-absent`), and a
`--rv-precision-ms` override supersedes. A normal MS star with no `--activity` is byte-identical to pre-CR#1.

#### `population-classify` (CR-7 — pure-math; network only on --star)
Thin-disk / thick-disk / halo verdict + membership probability from heliocentric U/V/W (Bensby TD/D/H velocity
ellipsoids on a Schönrich LSR). Feeds CR-4's population tag.
```bash
query.py population-classify --u 0 --v 0 --w 0            # Sun → thin
query.py population-classify --star "HD 122563"          # SIMBAD → Hypatia U/V/W (live)
```
Core: `kinematics.classify_population(u=None, v=None, w=None, star=None)`. Output: `{star, u_vel_kms,
v_vel_kms, w_vel_kms, toomre_velocity_kms, total_velocity_kms, population: thin|thick|halo, membership_prob,
probabilities:{thin, thick, halo}, provenance}`. Supply all three of `--u/--v/--w` **or** `--star` (partial
U/V/W → curated error; explicit velocities win over `--star`).

#### `dossier` gains three sections (CR-5)
`dossier` (Phase Q, above) now composes **`multiplicity`** (CR-2 flag + CR-3 stability), **`age_population`**
(Gaia FLAME age + CR-7 population from the Hypatia U/V/W it already fetched) and **`disk`** (CR-1) into the
default section set. These three **always render as explicit empties / upper limits, never omitted** (unlike
the six original sections, which drop to a `warnings[]` entry when absent) — a bare single star still shows a
`disk` upper-limit and an `age_population` "not determined". Sol carries offline reference values (single
star, ~4.567 Gyr thin-disk, zodiacal + Kuiper dust). `--sections multiplicity age_population disk` selects
them; the section keys are additive to the envelope. **CR-10.5 (second fire) enriches two of these:** the
`regions` section now self-flags an **evolved** host (luminosity-class guard — refuse the MS mass-inversion,
`evolved_star_flag`/`luminosity_class`/`luminosity_consistency`, Teff-independent) and the `multiplicity`
section now **cross-checks `binary-orbit` regardless of otype** (catches a variability-primary SB) with a
`multiplicity_basis` — see the CR-10 second-fire block below.

## CR-8 — batch exoplanet-archive pull (`planetary-systems-batch`, LIVE)

A separate, follow-up CR (CR-1…7 stay FULFILLED). One invocation returns the **full per-planet +
per-system field set for many hosts at once** — the deep orbital architecture (per-planet inclination
+ eccentricity, with meaningful nulls + per-value provenance) that `planetary-systems --star` gives
one host at a time. Core: `exoplanet_batch.compute_exoplanet_batch(hosts, filters, archive_query,
solution_scope, field_scope)`. **Built on the NASA `ps` (Planetary Systems) table, NOT `pscomppars`** —
`ps` has `default_flag` (solution scope), per-solution `pl_refname`/`st_refname` (provenance), and
preserves the genuine null/0 per solution (un-fabricated null inclination; reported-0-vs-null
eccentricity). The single-host `planetary-systems` (`pscomppars`) path is unchanged.

**Two selection modes** (exactly one per invocation):
- **Mode A — host list:** `--hosts N […]` or `--host-file P` (one host per line; `#`-comments/blanks
  skipped). Each host is resolved through SIMBAD first (identity authority → canonical id + cross-IDs +
  stellar fallbacks), then the archive round-trips are batched by name-column `IN(...)` lists.
- **Mode B — filter:** the `search-exoplanets` property flags (`--mass-min/max` = `pl_bmasse`,
  `--radius-min/max` = `pl_rade`, `--period-min/max` = `pl_orbper`, `--teff-min/max` = `st_teff`,
  `--dist-max-pc` = `sy_dist`, `--method` = `discoverymethod`, `--spectral-classes/-refine` =
  `st_spectype`) built into an ADQL WHERE over `ps`, **or** `--archive-query "ADQL"` (raw WHERE body).

**Both modes:** `--solution-scope {default,all}` (default = `default_flag=1` only; all = every published
solution, each carrying `default_solution`), `--fields {core,full}` (full = plus every raw `ps` column
under a `raw` key on each host/planet).

**Output:** `{mode ("hosts"|"filter"), solution_scope, field_scope, coverage{}, hosts[]}`, or the
`{error, route_tried:["nasa-tap:ps"]}` shape on failure.
- `coverage` (Mode A): `requested[], resolved_count, returned_host_count, unresolved[{input,reason}],
  zero_planet[{input,resolved_host}], total_hosts, total_planets` — **an unresolvable designation or a
  resolvable planet-less star is reported explicitly, never silently dropped.** (Mode B: `selection_echo,
  total_hosts, total_planets`.)
- each `hosts[]`: `resolved_host` (SIMBAD main_id, or hostname in Mode B), `hostname`, `cross_ids{}`,
  `spectral_type, teff_k, mass_solar, radius_solar, fe_h_dex, distance_pc`, `magnitudes{}` (band-labelled
  V/K/Gaia_G), `num_planets` (distinct planet names), `sy_pnum`, `provenance{}` (from `st_refname`),
  `stellar_param_sources{}` (per-field `archive`|`simbad` — SIMBAD fills a null archive value and is
  tagged), and `input` (Mode A), plus `planets[]`.
- each `planets[]`: `name, discovery_method, period_days, sma_au, inclination_deg` (**null when
  unmeasured — never defaulted to 90**), `eccentricity` (present `0` = reported fixed-circular,
  distinguishable from `null`), `arg_periastron_deg, mass_earth, mass_jupiter`, **`mass_kind`** ∈
  `{true_mass, msini, mass_radius_relation, unknown}` **+ `mass_prov_raw`** (the raw `pl_bmassprov`; the
  `M-R relationship` third category is kept, not laundered as `true_mass`), `radius_earth` (null when
  non-transiting), `transiting`, `default_solution`, `provenance{citation, refstr, href, raw}`.

**Validation gate (WB re-gates, CR-8 §5):** batch≡single on `HD 136352` — b/c/d at inclination
88.49/88.571/89.73 citing Delrez et al. 2021, identical to `planetary-systems --star "HD 136352"`;
RV-only host (e.g. HD 10700) → inclination `null`; coverage manifest with no silent drops; units per
CR §4. Live anchor: `tests/test_query_exoplanet_batch_live.py` (`SPACE_APP_RUN_LIVE=1`); offline logic:
`tests/test_exoplanet_batch.py`. Gate-adjudication (WB MSG 060): a non-anchor host may diverge from
`pscomppars` on a back-filled field → the `ps` default-flag value is authoritative (pass-with-note, not
a fail).

## CR-9 — disposition & quality fields (additive to `planetary-systems-batch`)

A **new, additive** CR extending CR-8 (CR-8 stays fulfilled/unchanged). Same tool, same inputs, same two
modes — CR-9 only **adds output fields + two pull-behaviors**. Built on the same `ps` table (composite-only
fields come from a second `pscomppars` query, always tagged). `core/exoplanet_batch.py`; contract
`scifiWorldBuilding-Claude/.../spaceapp-change-request-CR9-disposition-quality-fields.md`; plan
`PHASE_CR9_PLAN.md`.

**Field tiering (`--fields`):** `core` = the CR-8 fields **+ CR-9 Tier-1 disposition/quality**; `full` = that
**+ Tier-2 enrichment + the composite block + the OEC block + the raw `ps` row**. All built in one delivery —
`full` is a verbosity superset, not a phase.

**Load-bearing null rules (inherit CR-8):** never fabricate — a null stays null; a `*lim` flag is the **raw
tri-state int** `+1 upper / 0 measurement / −1 lower / null` (NEVER collapsed to a bool — a consumer coding
`if lim==1` must still see the `−1`); composite-only values are tagged `source:composite`; OEC values are
`authority:"SECONDARY"` (verify-at-primary).

**Per-planet — Tier-1 (core), archive-named keys:**
- `disposition{}`: `soltype` (str), `pl_controv_flag` `ttv_flag` `cb_flag` (raw int 0/1/null),
  `detection{}` (all 10 method flags `tran_flag`/`rv_flag`/`ima_flag`/`ast_flag`/`micro_flag`/`obm_flag`/
  `etv_flag`/`ptv_flag`/`pul_flag`/`dkin_flag` as raw ints), and `detection_methods[]` (convenience: the
  archive-stem of every flag set to 1, e.g. `["tran","rv"]`).
- `limits{}`: the 11 tri-state limit flags `pl_bmasselim` `pl_masselim` `pl_msinielim` `pl_radelim`
  `pl_orbeccenlim` `pl_orbincllim` `pl_orbsmaxlim` `pl_orbperlim` `pl_orblperlim` `pl_denslim` `pl_impparlim`.
- `pl_dens` (g/cm³), `pl_imppar`, `pl_orbinclerr1` `pl_orbinclerr2` (deg; the W3 assumed-edge-on discriminator
  — a genuinely-fitted `i` carries error bars, blank on an `inclination_deg==90.0`/`transiting:false` row ⇒
  assumed default).

**Per-planet — Tier-2 + composite + OEC (`--fields full` only):** `transit_geometry{}` (ratdor/ratror/
trandep/trandur/tranmid + `*lim`), `environment{}` (insol/eqt), `obliquity{}` (proj/true), `ephemeris{}`
(orbtper), `discovery{}` (year/facility/telescope/instrument/pubdate/refname), `record{}` (pubdate/rowupdate/
releasedate + spectra/note counts); `composite{source:"composite", pl_angsep(+lim)/pl_tsm/pl_esm/
pl_nobs_jwst_*}` (from pscomppars — `null` when no pscomppars row); `oec{source:"oec", authority:"SECONDARY",
lists[], discoveryyear, lastupdate, description}` (`null` when no OEC match — the `lists` carry OEC's
S-type/P-type/Controversial catalog tags).

**Per-host — Tier-2 (`--fields full` only):** `stellar_extra{}` (st_rotp/vsin/age/dens + `*lim`),
`coverage_counts{}` (st_nrvc/nphot/nspec), `system{}` (sy_snum/sy_mnum), `kinematics{}` (sy_pmra/pmdec/pm/plx
+ err + st_radv + err — Gaia-sourced; `st_radv` coverage patchy), `oec_structure{}` (the OEC binary-nesting
tree, SECONDARY).

**Behavior #2 — host name-resolution (always; a hard anchor).** Mode A now resolves each host through **all**
archive-match arms — catalog ids (HD/HIP/TIC/Gaia) **then a `hostname` fallback** (bare input + main_id +
common designations) for a host whose ps rows carry null catalog ids (the GJ 667 C false-drop). Two-phase:
catalog arms first (byte-identical to CR-8 for a normally-catalogued host), hostname fallback only for a host
phase 1 left empty. `coverage.resolution[]` records `{input, resolved_host, matched_on}` per returned host.

**Behavior #3 — component enumeration (best-effort; WB MSG 073 = option A).** For every resolved Mode-A host,
if OEC groups it with **planet-bearing non-primary components** (α Cen A → Proxima Cen b, even though α Cen A
is planetless in ps), those planets are surfaced under **`coverage.component_planets[]`**
(`{primary, component, source:"oec-tree", authority:"SECONDARY", note, planets:[records]}`), never merged into
the primary's `planets`. **A wide *un-catalogued* companion (26 Dra → GJ 685) correctly yields nothing** — no
offline catalog links them; the Gaia co-motion binding is the **consumer's** job (§7#3), not the pull's. No-op
when OEC is unavailable.

**Coverage manifest additions (Mode A):** `resolution[]` (behavior #2), `component_planets[]` (behavior #3),
`archive_absence` (candidate-grade rows are carried — a `soltype='Candidate'` planet still has a
`default_flag=1` row; FP/removed-targets triage is out of bulk-TAP reach), and best-effort error flags
`composite_error` / `oec_error_hosts` when the full-scope enrichment can't complete.

**Not carried (decisions, not gaps):** the archive **overview** disposition (`Confirmed:Controversial`) is
**not a TAP column** and — verified live — **equals `pl_controv_flag`** (already delivered) for both cited
cases; it is not fetched (WB MSG 074/075). Its genuinely-independent surface is **literature** (47 UMa d), the
skill's LEAD, unreachable by any pull.

**Validation gate — 16 anchors, all live-verified (WB re-gates independently).** The 12 §5 criteria (with two
carrying a second pinned sub-case) + the two pull-behavior anchors:
`GJ 667 C e/f/g→pl_controv_flag=1, b/c→0` · `LP 890-9 b/c→pl_bmasselim=1` · `TRAPPIST-1 b–h→ttv_flag=1` ·
`LTT 1445 A c→pl_orbeccenlim=1` · `Kepler-16 b→cb_flag=1` · `GJ 367 b pl_dens≈6.9` **and** `GJ 1214 b≈2.26` ·
`GJ 436 b→tran_flag=1 AND rv_flag=1` · `GJ 1214 b composite present + source:composite` (full) ·
`GJ 667 C c OEC list ⊇ "Planets in binary systems, S-type"` (full) · `HD 136352 b/c/d` batch≡single
inclinations 88.49/88.571/89.73 · `HD 219134 d & f→pl_bmasselim=−1` **and** `HD 128311 b→pl_orbincllim=−1`
(the −1 sign) · `HD 192310 b/c→inclination_deg=90.0 + mass_prov_raw="Msin(i)/sin(i)"` · **behavior #2**
`GJ 667 C→b/c/e/f/g present` · **behavior #3** `α Cen A→Proxima Cen b under component_planets` (26 Dra→nothing,
a documented limitation). Offline logic: `tests/test_exoplanet_batch.py` (+8 CR-9 classes); live anchors reuse
`tests/test_query_exoplanet_batch_live.py`.

## CR-10 — detection-floor & survey-disposition bundle (three items; additive, no fulfilled behavior moved)

First fire = **CR-10.1 + CR-10.2 + CR-10.4** (CR-10.3 HELD, not built). All additive; each item is an enrichment.
Coordination MSG 087–091; `PHASE_CR10_PLAN.md`; WB re-gates each independently on the sister venv.

**CR-10.1 — native transit-survey FP/candidate disposition (`planetary-systems-batch`, LIVE, core-tier).**
A **new per-planet `survey_disposition` block** (present-but-`null`, **never omitted** — CR-9 tri-state discipline):
`{source_catalog: "toi"|"koi"|"k2pandc"|null, disposition_code, disposition_text, catalog_id, match_status:
"matched"|"ambiguous"|null, match_note}`. Cross-match is schema-forced: **TESS** via the host `tic_id` +
orbital-**period** bind (`toi.tfopwg_disp`, tolerance ≈1.5%); **Kepler** (`cumulative.koi_disposition`) and **K2**
(`k2pandc.disposition`, incl. the `k2_name` alias) via an **exact planet-name join** (`ps` carries no KIC/EPIC).
Precedence koi > k2pandc > toi. RV-only planets → `null` (expected, not an error) — the audit's RV FPs (GJ 832 c,
HD 102365 b) stay `null`, so the Q9 absence-triage stays primary. **Faithful surfacing (WB MSG 091):** a survey `FP`
is emitted verbatim **even when the planet is archive-confirmed** (TOI-1836 c is TFOPWG-`FP` yet confirmed → the tool
reports `FP`, never suppresses); the FP-vs-confirmation reconciliation is the **consumer's** §6.7 job. Also adds a
per-host **`survey_siblings`** list (present-but-empty) — unbound TESS TOIs + Kepler/K2 FP siblings found via a
`kepid`/`epic_hostname` pivot (WB Q1a sweep) — and a `coverage.survey_disposition` summary
(`{matched, ambiguous, hosts_with_siblings[, errors]}`). **Best-effort:** a survey-table failure degrades that arm to
`null` + a `coverage.survey_disposition.errors` note; the primary `ps` pull is never broken. Scoped to
`planetary-systems-batch` only (single-host `planetary-systems`/`pscomppars` has no disposition layer). Anchors:
`HD 148193` → TOI-1836 c `disposition_code="FP"` `match_status="matched"` (validation #1, clean bind); `Kepler-10`
b/c → `CONFIRMED`; `HD 69830` b/c/d → `null`. Offline `tests/test_exoplanet_batch.py::Cr10SurveyDispositionTest`;
live `tests/test_query_exoplanet_batch_live.py::Cr10SurveyDispositionLiveTest`.

**CR-10.2 — `nuclear-inventory` [Fe/H]-upper soft-flag (CQ-7-3c-6).** `[Fe/H] > +0.5` no longer **globally voids** the
output. It becomes a **soft per-output `feh_extrapolation: true|false`** flag carried on the **`radiogenic_heat.provenance`**
(the [Fe/H]-dependent K-40 channel) **and** mirrored in **`provenance.per_output`** (an additive key beside the severity
strings; also in `provenance.flags`). The `[Fe/H]`-independent **fissile fraction stays computed and valid**
(`--fe-h 0.55` ≡ `0.45`, byte-identical), and `domain_ok` is **no longer `false` from `[Fe/H] > +0.5` alone** (still
`false`/`None` for a real out-of-domain per CQ-7-3c-4). **Age-out and the lower `[Fe/H] < −2.5` edge stay HARD.** The
threshold is a named constant `_DV5_FEH_SOFT_UPPER = 0.5` (strict `>`). Tests: `tests/test_nuclear.py::Cr102FehSoftFlagTest`,
`tests/test_query_nuclear.py`.

**CR-10.4 — `detection-completeness` archive-M★ preference.** On the `--star` path the tool now prefers the
**archive M★** (the *same* NASA `ps` + `default_flag=1` `st_mass` `planetary-systems-batch` reports — read through
`exoplanet_batch.fetch_archive_stellar_mass`, so the two can never disagree; never hard-coded) over the sp-type→mass
estimate for the RV/astrometry √M★ floors. Precedence **manual `--star-mass-solar` > archive > sp_type_estimate**. New
output field **`star_mass_provenance ∈ {"manual","archive","sp_type_estimate", null}`** beside `star_mass_solar`.
A **non-MS** host receives an archive mass **only if the archive radius is also present** (a mass-only injection would
turn the CR-6-AMEND graceful-skip into an error). Anchor: `detection-completeness --star "HD 69830"` →
`star_mass_solar ≈ 0.86`, `star_mass_provenance="archive"`, equal to batch's `mass_solar`. Tests:
`tests/test_detection.py::Cr104MassProvenanceTest`, `tests/test_query_detection.py::Cr104WrapperTest` (the wrapper
precedence + non-MS guard, mocked), `tests/test_query_detection_live.py` (live archive anchor).

### CR-10 SECOND FIRE — CR-10.3 + CR-10.5 (additive; no fulfilled behavior moved)

**CR-10.3 — `detection-completeness` per-star RV-precision auto-lookup.** A new **tier-2 catalog** in the RV-floor
selection: precedence **manual `--rv-precision-ms` → per-star catalog → generic 3a default**. Every method entry now
carries a **`floor_provenance ∈ {"manual","catalog","generic-3a", null}`** field — the *true tier per method* (`manual`
when *that method's own* override is supplied; `catalog` only ever on `rv`; else `generic-3a`; `null` on a
non-applicable entry). The catalog is a WB-owned JSON read via **`--rv-precision-catalog <path>`**, which **replaces**
the internal seed wholesale (the APP ships a minimal seed = HD 69830 `0.81 m/s` [Lovis 2006] as the flag-less default);
a bad/unreadable/invalid path → curated `{"error"}` (never a silent seed fallback); a malformed single row is skipped
best-effort. Match key = the SIMBAD-resolved `main_id` + every `designations` value vs a row's `main_id` + `aliases`
(whitespace-collapsed, case-insensitive); the catalog tier fires only on the `--star` path (like CR-10.4). `floor_source`
for a catalog hit reads `"per-star catalog: HD 69830 residual RMS 0.81 m/s [Lovis 2006]"`. RV-only (transit/astrometry/
imaging floors stay generic-3a; only `rv` can be `catalog`).
```
query.py detection-completeness --star "HD 69830"                                  # → rv floor_provenance="catalog", ~0.81 m/s
query.py detection-completeness --star "HD 69830" --rv-precision-catalog PATH.json  # WB-owned file replaces the seed
query.py detection-completeness --star "18 Sco"                                     # not in catalog → floor_provenance="generic-3a"
```
Tests: `tests/test_rv_precision.py` (loader/matcher/replace/malformed), `tests/test_detection.py::Cr103FloorProvenanceTest`,
`tests/test_query_detection.py` (catalog wrapper + curated bad-path), `tests/test_query_detection_live.py::Cr103RvCatalogLiveTest`.

**CR-10.5 — `dossier` robustness bundle** (edits the one `dossier` command; `regions.py`/`binary.py` core math unchanged).
- **Part 1 — luminosity-class region guard.** The `regions` section parses the SIMBAD sp_type **luminosity-class token**
  (token-boundary-aware: `K0IIIb`→`III`, never `Ib`; compound `M1-M2Ia-Iab`→`Ia-Iab`) and, for a giant/bright-giant/
  supergiant/subgiant, **refuses the MS mass-inversion** (the bogus MS mass/radius/regions are **withheld**; the
  `habitable_zone` section becomes a `note`), unless **`--force-ms-inversion`**. New `regions` keys (json):
  `luminosity_class`, `evolved_star_flag`, `region_basis`, and `luminosity_consistency{calc_L, L_bol, ratio, flagged}`
  where `L_bol` is Gaia FLAME `lum_flame` — **graceful-null** (`L_bol/ratio/flagged = null`) when FLAME does not cover the
  star (e.g. saturated supergiants Polaris/Betelgeuse), never a fabricated ratio. `flagged=true` when `calc_L` vs `L_bol`
  disagree by >2×. A clean MS dwarf keeps **byte-identical region values** plus these additive keys. **The evolved
  self-flag is Teff-independent:** when SIMBAD has no Teff (so the region computation errors — e.g. Pollux `K0IIIb`), the
  `regions` section still emits `luminosity_class`/`evolved_star_flag`/`ms_inversion_withheld` structurally (a pure
  sp_type parse), with `luminosity_consistency` all-null (calc_L needs Teff); a non-evolved star that errors keeps the
  plain `warnings[]` path.
- **Part 2 — multiplicity-flag cross-check.** The `multiplicity` section now calls **`binary-orbit` once regardless of
  otype**, so a spectroscopic binary whose primary otype is a *variability* class (Spica `bC*`) is still flagged.
  `is_multiple`/`sb_flag` reflect the SB9/WDS-ORB6/Gaia-NSS cross-check; a new **`multiplicity_basis`** names the catalog
  source, e.g. `"SB9 seq 766 (P=4.01 d, SB2)"`. Stability reuses the same fetched result (one network call, via the new
  pure `binary.stability_from_solutions`).
```
query.py dossier --star Polaris --sections regions --fmt json      # evolved_star_flag=true, luminosity_class="Ib", MS-inversion withheld, L_bol null
query.py dossier --star Pollux --sections regions --fmt json       # luminosity_class="III" (token boundary), evolved
query.py dossier --star "HD 116658" --sections multiplicity --fmt json  # Spica: multiple/sb via SB9, multiplicity_basis names the orbit
query.py dossier --star Polaris --sections regions --force-ms-inversion  # override the guard (values unreliable)
```
Tests: `tests/test_shared_luminosity_class.py`, `tests/test_report.py::Cr105Part1RegionGuard`/`Cr105Part2Multiplicity`,
`tests/test_binary_stability_auto.py` (the refactor is byte-identical), `tests/test_query_dossier_live.py` (live anchors).

## CR-11 — WD cooling-grid extension, stellar-mass provenance & binary/multi-star exclusion composition (three items; additive, no fulfilled behavior moved)

Built 2026-08-26. Additive to CR-8/9/10; edits no fulfilled spec. `completed_plans/PHASE_CR11_PLAN.md`.

**CR-11.1 — `cooling-hz --track wd` high-mass extension.** *(⚠ **SUPERSEDED BY CR-12** — the ≤1.0 "byte-identical"
guarantee, the `young_teff_cooling_age_inflation` note, and the `cooling_age_gyr ≈ 0.146` Sirius-B anchor described
below are all replaced. The whole 0.40–1.30 grid is now a dense Bedard 2020 re-derivation; Sirius B ≈ 0.118. See the
CR-12 block.)* The bundled WD cooling grid was extended **0.40 → 1.30 M☉**
(the same Bedard 2020 / Montreal DA thick-H sequences `seq_105…130_thick.txt`, transcribed + closure-validated). A WD mass
**`1.30 < M ≤ ~1.38`** (Chandrasekhar) now **clamps** to the 1.30 sequence (no grid-range error); **`M > ~1.38` refuses**
(`{"error": "…exceeds the Chandrasekhar limit…"}`). **Unchanged JSON shape.** **≤ 1.0 M☉ is byte-identical** (no regression;
the 0.151 Gyr M=1.0/25970 K reference stands). Snapshot mode gains one **advisory `notes` entry**
`"young_teff_cooling_age_inflation…"` **only for M > 1.0 at young/hot epochs** (Teff > 12000 K) — the massive-WD young cooling
age is a mild upper estimate (Sirius B ≈ 0.146 vs literature ~0.126 Gyr; Bond 2017), an interpolation artifact of the frozen
≤1.0 anchor (WB decision A, MSG 004; the ≤1.0 re-sampling is a separate WB follow-up OQ-SA-WDAGE1). Anchors: `--mass-solar 1.018
--teff 25970` → no error, `radius_rsun ≈ 0.008`, `cooling_age_gyr ≈ 0.146` (< 0.151); 1.20/1.30 no error, `radius_rsun`
monotone-decreasing in mass.
```
query.py cooling-hz --track wd --mass-solar 1.018 --teff 25970    # Sirius B: was an error; now age ~0.146 Gyr, R ~0.008 R☉
query.py cooling-hz --track wd --mass-solar 1.30 --teff 20000     # extended grid point
query.py cooling-hz --track wd --mass-solar 1.45                  # error: exceeds Chandrasekhar
```
Tests: `tests/test_cooling_hz.py::Cr111HighMassWDTest`.

**CR-11.2 — stellar-mass provenance on `dossier` + `compare-stars`.** Both now resolve stellar mass with an explicit
**provenance** and two caution flags, mirroring CR-10.4/CR-10.5. **Precedence: manual `--mass-solar` (dossier only) → catalog
row (`--star-mass-catalog <path>`) → Gaia DR3 FLAME → the `L^0.2632` inversion.** New fields — on `dossier` in the `regions`
section as **`mass{mass_solar, mass_provenance ∈ {manual|catalog|gaia_flame|ms_luminosity_inversion}, massL_inversion_caution,
peculiar_star_flag, inversion_mass_solar, note, catalog_citation?}`**; on `compare-stars` as flat per-star keys **`mass_solar,
mass_provenance, massL_inversion_caution, peculiar_star_flag, mass_note`**. Under **decision B** (WB MSG 008) the
headline `mass` and `radius` (= `M^0.57`) also track the preferred mass when a measured one is preferred — so mass ↔
radius are coherent and `dossier ≡ compare-stars` on `mass`/`radius`, not just `mass_solar`; an inversion-sourced star is
byte-unchanged, and `luminosity` (bolometric/archive) + the L-based `hz_inner/outer_au` are unaffected. `massL_inversion_caution=true` **iff** the provenance is `ms_luminosity_inversion`
**AND** the star is in an over-read regime = **hot upper-MS** (leading MK class O/B/A) **or chemically-peculiar** (an Am `m` /
Ap `p` token in `sp_type`); `peculiar_star_flag` is set from the `m`/`p` tokens **only**. The caution is **advisory — the mass is
still returned, never null**. When a **measured** mass (manual/catalog/FLAME) is preferred over the inversion, the
**mass-derived** dossier fields all recompute from it (WB decision B, MSG 006) so mass ↔ radius stay coherent:
`stellar_radius` (`M^0.57`), `luminosity_from_mass` (`M^3.5`), `calculated_luminosity` (→ the **secondary Calculated-HZ**
column), `main_seq_lifespan_yr`, and the `0.2·M` inner / `40·M` outer system limits. The **primary** HZ
(`hz_inner/outer_au`), snow line and ice lines are `bcLuminosity`-based (never use mass) and are **unchanged**; the CR-10.5
`luminosity_consistency` diagnostic stays pinned to the inversion radius (it is a check *of* the inversion). A star still
on the inversion mass is **byte-unchanged**. **`--star-mass-catalog`** is a WB-owned JSON that **REPLACES** the internal seed wholesale (the seed = the four
verified anchors: Sirius A 2.063 / Vega 2.135 / α Cen A 1.079 / α Cen B 0.909); a bad/unreadable/no-`stars`-array path →
curated `{"error"}` (loud, never a silent fallback); a malformed row skipped best-effort (mirrors CR-10.3). Anchors: Sirius A
(`A0mA1Va`) → default seed `catalog` 2.063 + `peculiar_star_flag=true`; with an empty/replacing catalog →
`ms_luminosity_inversion` ≈ 2.59 + `massL_inversion_caution=true` (**the silent 2.59-with-no-flag must not persist**); Vega
(`A0Va`) → caution via the hot-MS path, `peculiar_star_flag=false`; α Cen A `G2V` / B `K1V` → both flags false.
```
query.py dossier --star "Sirius A" --sections regions --fmt json                       # catalog 2.063, peculiar=true
query.py dossier --star "Sirius A" --sections regions --fmt json --star-mass-catalog EMPTY.json  # inversion ~2.59, caution=true
query.py dossier --star "Vega" --mass-solar 2.135 --sections regions --fmt json        # manual override
query.py compare-stars --stars "Sirius A" "alf Cen A" Sol --star-mass-catalog WB.json   # per-star mass_provenance
```
Tests: `tests/test_stellar_mass.py` (resolver/catalog/flags/precedence/downstream + offline Sol dossier & bad-path),
`tests/test_query_stellar_mass_live.py` (live SIMBAD anchors + dossier≡compare-stars parity). Reusable resolver:
`core/stellar_mass.py` (+ `core/stellar_mass_tables.py`).

**CR-11.3 — `exclusion-system` (new subcommand): binary / multi-star exclusion-boundary composition.** Composes the **FROZEN**
single-body `exclusion-boundary` generator (no second calibration) over a resolved multi-star configuration into a set of
**merge-grouped, phase-varying, asymmetric zones with per-component domain guards**. **Default `--alpha 0.4`** (mid of the canon
[1/3,1/2] band — reproduces the hand-card anchors). Two input modes: **`--star "<name>"`** (best-effort live SIMBAD +
`binary-orbit`/SB9 resolution of the primary orbit; a companion's WD/BD nature is confirmed by a `"<name> B"` otype lookup —
**wide hierarchical companions with no catalogued orbit, e.g. Proxima, need `--component`**) and the deterministic
**`--component "id=A,mass=2.063,lum=25,class=A0mA1Va,pair=AB,sma=19.8,ecc=0.59"`** (repeatable; keys id/name, mass, lum, class
[sp_type or `wd`/`brown-dwarf`/`rogue`/`giant`], pair, sma, ecc, orbits, wind_state, mass_loss_msun_yr). Per-component mass = the
**CR-11.2 chain** (manual `mass=` → `--star-mass-catalog` → FLAME → `L`-inversion from `lum`), which drives **both** the r_ex
sphere **and** the barycentric offset. An **off-MS component** (WD/BD/rogue/giant) is `domain: out_of_domain`, `r_ex_au: null`
(**no sphere**) — but its **real mass still sets the barycenter** (Sirius B). Merge-grouping = union-find over the periastron
overlap test `d < r_ex,i + r_ex,j` (out-of-domain radius = 0). Output: `zones[]` (per zone `members`, `status ∈ {merged,
separate}`, `long_axis_au{periastron,apastron}`, `minor_axis_au`, `barycenter`, `components[]{id, mass_solar, mass_provenance,
r_ex_au|null, domain, class_note}`, `point_mass_r_ex_au` [**in-domain members only** — an out-of-domain mass is **never** summed
in], `forcing_class`), plus `separations_au`, `n_components`, `n_zones`, `phase`, `alpha`/`dial`/`calibration_au`, `model_note`,
`composition_note`. A **single-star** input reproduces `exclusion-boundary` on the same mass + `alpha`. Self-validating (curated
`{"error"}` exit 1; argparse exit 2). Anchors (via `--component`): **Sirius** — one `merged` zone, A `r_ex ≈ 63.5` (measured
2.063), B `out_of_domain`/`null` (WD guard), `long_axis ≈ {peri: 66, apo: 74}`, `point_mass ≈ 63.5` (A alone); **α Cen** — two
zones, AB `merged` (A 49.0 / B 45.7, `long_axis ≈ {54, 65}`, `minor ≈ 49`, `point_mass ≈ 62.5`) + Proxima `separate` (≈ 20.5).
```
query.py exclusion-system --star "Sirius"                                              # live: merged, B WD-guarded
query.py exclusion-system --component "id=A,mass=2.063,class=A0mA1Va,pair=AB,sma=19.8,ecc=0.59" \
                          --component "id=B,mass=1.018,class=wd,pair=AB,sma=19.8,ecc=0.59"   # deterministic Sirius anchor
```
Tests: `tests/test_exclusion_system.py` (anchors/domain-guard/merge/envelope/point-mass/degenerate/validation),
`tests/test_query_exclusion_system.py` (query contract), `tests/test_query_exclusion_system_live.py` (live `--star Sirius`).
Core: `core/exclusion_system.py` (composes the frozen `core/exclusion_boundary.py`).

## CR-12 — WD cooling-grid ≤1.00 M☉ cooling-age re-derivation (Bedard 2020 unification) + criterion-1 correction

Built 2026-08-26. A **correction** CR (not additive): it deliberately **supersedes** CR-11.1's "byte-identical ≤1.0"
guarantee and **amends** CR-11.1's criterion 1. `completed_plans/PHASE_CR12_PLAN.md`; evidence
`scifiWorldBuilding-Claude/design-lab/star-system-analysis/wd-cooling-grid-verification.md`.

**The fix.** `cooling-hz --track wd`'s ≤1.00 M☉ **cooling-age** was erratically wrong (+2..+86%) vs the Bedard 2020
Montreal `seq_XXX_thick.txt` sequences the `model_note` cites, while `radius_rsun`/`teff_k`/`lum_lsun` were
source-exact — an **age-only** defect. Root cause: the ≤1.00 rows were **sparsely sampled** (~10 nodes/sequence,
skipping the ~18k–30k K mid-track), so linear-in-Teff interpolation over-read the convex age(Teff) curve. CR-12
re-derives the **whole 0.40–1.30 M☉ grid** as one dense adaptive resample of the source `Age` column (uniform
0.05 M☉ spacing; ~77 nodes/mass; reproduced by `CR12_montreal_files/transcribe.py` + the archived seq files), so the
cooling-age matches source to **~2%** (build target <0.5%) across all four §3.1 anchor Teff.

**Contract impact (JSON shape unchanged).**
- **Existing ≤1.00 cooling ages CHANGE** (up to ~86% — a correction). E.g. `1.00/25970` **0.1514 → 0.1096**;
  `0.6/25970` **0.0213 → 0.0154**.
- **Sirius B `1.018/25970` → `cooling_age_gyr ≈ 0.118`** (was 0.146), **≥ the clean M=1.00 (~0.110)** — monotonic
  older-with-mass (criterion 1 corrected: at fixed Teff a more massive WD is *older*; the 0.151 reference is retired).
- The **`young_teff_cooling_age_inflation` note is REMOVED** (D-B) — the ages are source-faithful, so it would be false.
- **Age-axis re-parameterization:** any age-dependent output also shifts — snapshot state at `--cooling-age-gyr`,
  residence time, the CHZ band, and the ²²Ne distillation-pause epochs — a correct consequence of the more accurate
  age axis (WB re-checked: no production card blast beyond `cards/sirius.md`). **Teff-only outputs
  (`radius_rsun`/`teff_k`/`lum_lsun` at a given Teff) are unchanged/source-faithful.**
- `> 1.38` still refuses; the 1.30–1.38 Chandrasekhar clamp is intact. `_BD_COOLING` (BD track) untouched.

```
query.py cooling-hz --track wd --mass-solar 1.018 --teff 25970    # Sirius B: age ~0.118 Gyr (was 0.146), R ~0.008 R☉
query.py cooling-hz --track wd --mass-solar 1.00  --teff 25970    # age ~0.110 Gyr (was 0.151)
```
Tests: `tests/test_cooling_hz.py::Cr12AgeRederivationTest` (age-vs-source anchors + turnover monotonicity),
`::Cr111HighMassWDTest` (re-pinned: source-faithful ≤1.0, Sirius B older-with-mass, note removed). Source archive +
regenerator: `CR12_montreal_files/` (19 seq files + md5 MANIFEST + `transcribe.py`).

**CR-12.4 — `one_core_uncertain` runtime caveat for high-mass WDs (additive, 2026-08-26).** `cooling-hz --track wd`
now carries an additive **`one_core_uncertain`** entry in the `notes` array — in **all three modes (snapshot /
residence / CHZ)**, Part 2 having extended it beyond snapshot — when `--mass-solar` **> 1.05 M☉** (`_T_ONE_MSUN`): the
bundled grid is CO-core (Bédard 2020), and WDs above ~1.05 M☉ may host **O-Ne cores** the
CO grid does not resolve (ONe cores are more compact / cool faster; the literature pairs CO-Bédard ≤1.05 with
**ONe-Camisassa et al. 2019, A&A 625, A87** >1.05). **No numeric output changes** —
`cooling_age_gyr`/`radius_rsun`/`teff_k`/`lum_lsun`/zones and every residence/CHZ-band value are untouched; the caveat
coexists with any existing note (e.g. `hz_undefined_extrapolation` in snapshot). The note **text is byte-identical
across all three modes** (one source of truth, `core.cooling._one_core_notes`). **Sirius B (1.018 M☉) is below the
threshold → caveat absent** in every mode; the BD track never carries it. No new flags; residence/CHZ gain an
always-present `notes` array (empty `[]` ≤1.05). Tests: `tests/test_cooling_hz.py::Cr124OneCoreCaveatTest`.
```
query.py cooling-hz --track wd --mass-solar 1.10  --teff 25970    # snapshot: notes has one_core_uncertain; age 0.161
query.py cooling-hz --track wd --mass-solar 1.10  --sma-au 0.01   # residence: same caveat; residence_gyr unchanged
query.py cooling-hz --track wd --mass-solar 1.018 --teff 25970    # Sirius B: caveat absent; age 0.1178 unchanged
```

## CR-13 — `exclusion-system --star` live-resolution robustness (additive to CR-11.3; new `mass_provenance` enum values)

Built 2026-08-29. Hardens **only** the `--star` auto-resolve convenience layer of `exclusion-system` (CR-11.3). The
`--component` deterministic core, the frozen single-body generator, the union/merge composition and the barycenter model
are **unchanged** (their anchors are byte-identical). `completed_plans/PHASE_CR13_PLAN.md`.

**What changed in the `--star` path.**
- **Component / wide-member / secondary resolution (CR-13.1).** A directly-named **secondary** (`--star "Sirius B"` →
  SIMBAD `* alf CMa B`) or any **off-MS** body (WD/BD/sdB/sdO/giant/subgiant) resolves to a **single component**, never
  the old mangled `"Sirius B B"` / placeholder-1.0 / mislabeled-WD output. A **single star** or a **wide-hierarchical
  member** whose only catalogued "orbit" is a wide bond with no usable component mass (`--star "Proxima Centauri"`, the
  ~13 000 AU tie to α Cen AB) computes as a **single body** (no crash). A **primary**-named input (`--star "alpha Cen A"`)
  is **not** caught by the secondary detector — it composes the system. A genuinely unresolvable target returns an error
  **naming the resolved SIMBAD id + the remedy** (`--star-mass-catalog`, or `--component`).
- **Per-component mass provenance (CR-13.2).** **Both** the primary and the companion now run the full CR-11.2 chain
  (`manual → --star-mass-catalog → FLAME → inversion/orbit`); the catalog is matched on the resolved id **and** a
  **per-component designation** (system id `* alf Cen` also tries `* alf Cen A`/`B`), so a measured catalog mass wins over
  a binary-orbit split. For a single MS body with no manual/catalog/FLAME mass, the chain's `L`-inversion is fed the
  bolometric luminosity (same value the dossier inverts), so a no-catalog Proxima resolves to the tool's `0.139` instead
  of crashing.
- **Binary-orbit mass quality (CR-13.3).** When the fallback is a `binary-orbit` mass, a **degenerate placeholder** orbit
  solution (`mass_ratio_q` exactly 1.0) is filtered out in favour of a real-ratio solution; a mass that is only a
  degenerate equal-split or an SB1 minimum-mass lower bound is **flagged**, never presented as a clean measured mass.

**New additive `mass_provenance` values** (a consumer switching on `mass_provenance` should tolerate them; no existing
value changes meaning): **`unresolved_out_of_domain`** (a lone out-of-domain body whose mass could not be resolved — the
sphere is `null` and the mass is numerically inert, so it is emitted with `r_ex_au: null` rather than an error; the C1→A
tolerance, which the `--component` path shares for a lone out-of-domain component with no `mass=`),
**`binary_orbit_equal_split_unresolved`** (a placeholder `q=1.0` orbit **or** the no-secondary equal-mass fallback), and
**`binary_orbit_sb1_min`** (an SB1 sin i=1 lower bound). Each carries a `resolution_notes` caution. Output JSON shape is
otherwise unchanged.

**Anchors** (WB re-gates live, both `--star` and `--component`; α=0.4, calibration 47.5): `--star "alpha Centauri"
--star-mass-catalog <cat>` → A `1.079`/`catalog`/`49.0`, B `0.909`/`catalog`/`45.7`, merged `{54, 65}`, minor `≈49`,
point-mass `62.5` (= the `--component` reference); `--star "Sirius" --star-mass-catalog <cat>` → A `2.063`/`catalog`/`63.5`,
Sirius B `1.018`/`catalog` (WD guard, `r_ex null`), merged `{66, 74}`; `--star "Sirius B"` → a single WD component,
`r_ex_au: null`, `class_note "white dwarf"`, **bare** `mass_provenance "unresolved_out_of_domain"` / **with catalog**
`1.018`/`catalog`; `--star "Proxima Centauri" --alpha 0.4` → single body, **with catalog** `0.1221`/`catalog`/`20.48`,
**bare** `0.139`/`ms_luminosity_inversion`/`21.57`; `--star "alpha Centauri"` (no catalog) → not a silent `1.02/1.02`
(real-ratio or a flagged equal-split); `--star "Sirius"` (no B row) → B's `0.458` flagged `binary_orbit_sb1_min`.
Regression anchors unchanged: `--star "Sol"`/`"epsilon Eridani"`, `--component` α Cen/Sirius/Proxima, `>1.38 M☉` WD
refuse + out-of-domain guards. Tests: `tests/test_exclusion_system.py` (offline decision helpers + mocked resolver +
C1→A), live `--star` anchors gated in `tests/test_query_exclusion_system_live.py`. Core: `core/exclusion_system.py` (the
only file changed).

## CR-14 — shared `_extract_stability_elements` correctness (solution selection + catalog-aware mass + degenerate flagging)

Built 2026-08-29. The general parallel to CR-13 for the OTHER consumers of the shared stability-element extraction —
**`binary-stability-auto`** (CR-3), the dossier **`multiplicity`** section (CR-10.5), and **`binary-orbit`**. The CR-13.3
degenerate-`q` solution selection + the CR-11.2/CR-13.2 mass chain now live at the shared root, so all these paths — and
`exclusion-system` — report the **same** per-component masses for a given star. `completed_plans/PHASE_CR14_PLAN.md`.
The standalone **`multiplicity`** subcommand exposes no per-component masses and is **unchanged** (not in scope).

**Four parts.**
- **CR-14.1 — solution selection.** A shared selector (`core.binary.select_stability_elements`) filters degenerate
  placeholder solutions **before** the frozen `_extract_stability_elements`, so a real-ratio solution wins over a
  degenerate `mass_ratio_q ≈ 1.0` equal-split (α Cen's `1.02/1.02` → the real `~0.84` ratio; sma/period from the
  real-ratio solution, so the Holman-Wiegert `stype/ptype_critical_au` recompute from the true μ, not 0.5).
- **CR-14.2 — degenerate/SB1 flagging.** `binary-stability-auto` / dossier-`multiplicity` `elements` blocks gain
  **`mass_provenance_a`** / **`mass_provenance_b`** (per component) + a **`resolution_notes`** list. The CR-13.3 enum
  values are reused verbatim — `binary_orbit_equal_split_unresolved` (placeholder `q≈1.0` or a no-secondary equal-mass
  fallback) and `binary_orbit_sb1_min` (SB1 sin i=1 lower bound) — a flag appears only when a degenerate/lower-bound
  value is genuinely the best available. Additive; a consumer switching on `mass_provenance` must tolerate the values.
- **CR-14.3 — catalog-aware mass sourcing (general, all stars).** Per-component masses route through the shared CR-11.2
  chain (`manual > --star-mass-catalog / internal seed > Gaia FLAME > orbit-ratio / MS L-inversion`), matched on the
  resolved `main_id` + aliases + a per-component designation (the `* alf Cen` → `* alf Cen A`/`B` derivation). When a
  measured mass is preferred, the binary sma is recomputed at the observed period from it (`a ∝ M_tot^⅓`), so mass + sma
  + barycenter share one mass set. **`binary-stability-auto` gains `--star-mass-catalog <path>`** (REPLACE semantics,
  loud error on a bad path; the dossier already had it). Cross-path: `binary-stability-auto` / dossier-`multiplicity` /
  `exclusion-system` report the same masses for a star.
- **CR-14.4 — abs-mass-drop filter narrowed.** The shared selector keeps a **clean astrometric** absolute-mass row
  rather than discarding it for an SB2-ratio estimate; it still drops a degenerate `q≈1.0` placeholder always, and an
  **SB1 minimum** (an abs-mass row whose classifier `method == "spec-min"`) when a real SB2 exists (a real ratio beats a
  lower bound). The only behavior change vs CR-13.3 is the real-SB2 + clean-astrometric-abs corner. **This makes the
  exclusion path no longer strictly byte-identical** (it adopts the same filter); the exclusion anchors are nonetheless
  unchanged (none carries that co-occurrence).

**`binary-orbit`** stays a raw-orbit reporter: it gains only an additive **`degenerate: true`** marker on a placeholder
`q≈1.0` solution (never reordered, never dropped, no chain, no `--star-mass-catalog`).

**New/changed output keys** (all additive): `elements.mass_provenance_a` / `elements.mass_provenance_b`, top-level
`selected_solution` (the solution the selector picked — the dossier names it in `multiplicity_basis`), and
`resolution_notes` on `binary-stability-auto` / the dossier `multiplicity` section; `degenerate` on a `binary-orbit`
solution. Existing keys/shapes are unchanged.

**Anchors** (WB re-gated live 2026-08-29, both with and without the catalog): `binary-stability-auto --star "alpha
Centauri" [--star-mass-catalog <cat>]` → A `1.079`/`catalog`, B `0.909`/`catalog`, **sma `23.326`, stype_critical
`2.749`, ptype_critical `86.652`** (μ=0.457; was the degenerate `2.596`/`87.005`), the real-ratio period `P≈29183`
(not the degenerate `29650`); **equal to** `dossier --sections multiplicity --star "alpha Centauri"` (identical
1.079/0.909, `multiplicity_basis` now the real-ratio P=29183) and to `exclusion-system`'s per-component masses.
`binary-stability-auto --star "Sirius"` (no seeded B) → Sirius B `0.458`/`binary_orbit_sb1_min`, matching
`exclusion-system`. `binary-orbit --star "alpha Centauri"` → the degenerate `q=1.0` solution carries
`degenerate: true`, the real-ratio solutions after it. Regression: standalone `multiplicity --star "alpha Centauri"`
byte-identical (classification only, sep 10.788); Sol / ε Eri unaffected. **CR-11/CR-13 exclusion anchors UNCHANGED
under the CR-14.4 (b) filter (re-verified live, not asserted):** α Cen A `48.97` / B `45.72` / env `{54.10, 65.17}` /
point-mass `62.53`; Sirius A `63.46` / B null-WD / env `{66.14, 73.84}`; Proxima `20.48`; Sirius B bare
`unresolved_out_of_domain`; `--component` `48.967`; ε Eri `0.811`/`gaia_flame`/`43.69`. Cores:
`core/binary.py` (the shared selector + `_extract_stability_elements_full` + `_mass_flags` hoist + the chain wiring +
the `binary-orbit` marker), `core/stellar_mass.py` (the hoisted `resolve_component_mass` / `augment_designations` /
`component_candidate_ids` + the `resolve_binary_components` orchestrator), `core/exclusion_system.py` (now delegates the
hoisted helpers), `core/report.py` (the dossier `multiplicity` chain + H1 guard + M3 basis), `query.py`
(`--star-mass-catalog` on `binary-stability-auto`). Tests: `tests/test_binary_stability_auto.py` (CR-14 classes),
`tests/test_exclusion_system.py` (byte-identical delegation guard).

## Implementation notes

- No `sys.path` manipulation — Python prepends the script's own directory automatically when run directly, so `import core.X` works without changes.
- Unexpected exceptions from core functions are caught by a top-level handler in `main()` and returned as `{"error": str(e)}` with exit code 1.
- `--ly-hr` and `--times-c` are a mutually exclusive required group for `travel-time`, `optimal-tour`, and `multi-stop`; supplying both or neither is rejected by `argparse` with exit code 2.
- The `gcns-*` calculators use one required mutually-exclusive group **per endpoint** (`--star1`/`--id1`, `--star2`/`--id2`, or `--star`/`--id`), plus the `--ly-hr`/`--times-c` group for `gcns-travel-time`. Supplying both or neither within any group is rejected by `argparse` with **exit code 2** and a message on **stderr** — this is the argparse path, **not** the JSON-`{"error"}`/exit-1 path, so do not parse stdout as JSON for those invocations. A resolvable-but-invalid request (e.g. a name not in GCNS, an ambiguous name, or an empty `gcns_stars` table) instead returns `{"error": ...}` on stdout with exit 1.
- **Phase T mode-selection groups:** `rv-semi-amplitude` uses a real **argparse** required mutually-exclusive group `--period-days`/`--sma-au` (both/neither → exit 2). `circumbinary-hz` (numeric `--teff1/--lum1/--teff2/--lum2` vs `--star1/--star2`) enforces its mode exclusivity **in the handler** — both modes, one star only, or a partial numeric set → a stderr message + **exit 2**. `kozai-lidov` requires exactly one complete pair (both periods **or** both SMAs); a partial/both-pair input is a **core** check → curated `{"error"}` **exit 1**. `solar-analogs --mode` is an argparse `choices` (bad value → exit 2). `substellar --classes` is `nargs="+"`.
- **Phase W `spin-comfort` anchors:** the two gravity forms `--gravity-g` / `--accel-ms2` are an **optional** argparse mutually-exclusive group (both → exit 2), but the "**exactly two** state anchors" rule is a **core** check → curated `{"error"}` **exit 1** (so 0 / 1 / 3 / 4 anchors is exit 1, not the argparse exit 2). `--criteria` is an argparse `choices` (bad value → exit 2); the per-threshold overrides and `occupant-height-m ≥` the *solved* radius are core checks (exit 1).
- **Phase N validation asymmetry** (see "Integration expansion (Phase N)" above): the pure-compute Phase-N subcommands (`habitable-zone-sma`, `star-luminosity`, `brachistochrone-au`, `brachistochrone-lm`) wrap **non-self-validating** legacy core functions, so out-of-range numerics surface via the generic top-level handler as `{"error": str(e)}` with a **raw exception message** (not a curated sentence), exit 1 — except `star-luminosity`, which has no out-of-range error path (only argparse exit 2). Only `travel-time-solar` returns curated `{"error": ...}` dicts. This is intentional (Phase N adds no `core/` validation); key on `"error"` + exit code, never on the message text.
