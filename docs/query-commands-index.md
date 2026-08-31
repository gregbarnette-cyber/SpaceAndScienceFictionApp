# query.py — Command Index

A condensed one-line index of every `query.py` subcommand, grouped by family. **`docs/integration.md`
remains the authoritative contract** — exact arguments, JSON output keys, `sources` (network vs
offline), exit-code behaviour, and worked anchors. This file is a navigation aid, not the contract;
descriptions are condensed from integration.md's prose.

**Total: 181 subcommands** (generated from `query.py` `add_parser` names; all 181 are documented in
`docs/integration.md`).

## Star databases & catalog lookup
| Command | Description |
|---|---|
| `simbad-lookup` | SIMBAD star lookup — the identity spine; returns full star info + all designations, and carries the GCNS and Gould cross-references. |
| `exoplanets` | NASA Exoplanet Archive — queries all three tables for a star (pscomppars + HWO ExEP + Mission Exocat). |
| `planetary-systems` | NASA Exoplanet Archive — planetary-systems composite (pscomppars only). |
| `hwo-exep` | HWO ExEP precursor-science target stars (EEID, disk flag, Earth-twin metrics). |
| `mission-exocat` | NASA Mission Exocat stellar data from the local DB table. |
| `hwc` | Habitable Worlds Catalog planets from the local DB table. |
| `hypatia-data` | Hypatia Catalog stellar properties + full elemental abundances (Lodders 2009 normalisation). |
| `main-sequence` | Main-sequence star property table (spectral class → Teff / mass / radius / lum / lifetime). |
| `solar-system` | Solar-system planets / moons / dwarf planets / asteroids, read from the local SQLite tables. |

## Open Exoplanet Catalogue (OEC)
| Command | Description |
|---|---|
| `oec-system` | Full recursive `system → binary → star → planet → satellite` hierarchy tree by name. |
| `oec-planet` | A single planet node plus its host chain and what it is attached to (star / binary / system). |
| `oec-search` | Structural search across all OEC systems (star count, circumbinary, status / method / range filters). |
| `oec-census` | Catalogue-wide topology statistics (star/planet counts, attachment, circumbinary/rogue, histograms). |
| `oec-status` | OEC cache freshness + element counts. |

## GCNS & substellar census
| Command | Description |
|---|---|
| `gcns-within-sol` | All GCNS sources within N ly of Sol, with Bayesian distances (local DB). |
| `gcns-source` | A single GCNS row by Gaia EDR3/DR3 source_id. |
| `gcns-system` | The resolved multiple-star system containing a Gaia source_id. |
| `gcns-distance` | GCNS-backed 3D distance in light years between two stars (by name or Gaia id). |
| `gcns-travel-time` | GCNS-backed FTL travel time between two stars. |
| `gcns-stars-within-star` | All GCNS stars within N ly of a centre star, with Bayesian distances. |
| `substellar` | Substellar (L/T/Y) census from `gcns_stars` by spectral-type prefix, with a completeness caveat. |
| `solar-analogs` | Solar twins/analogs from the Hypatia cache via a tolerance box around the solar values (Teff/logg/[Fe/H]). |

## Star-system regions
| Command | Description |
|---|---|
| `star-regions` | Stellar properties + all HZ / region / biochemistry-zone boundaries from a SIMBAD lookup (plus Hypatia). |
| `star-regions-manual` | The manual-input variant — no SIMBAD, no Hypatia; you supply the six raw inputs. |
| `sol-regions` | Sol's full system-regions computation from hardcoded solar constants. |

## Distance & stars-within
| Command | Description |
|---|---|
| `distance` | 3D Euclidean distance in light years between two stars. |
| `stars-within-sol` | All stars in the local `star_systems` table within N ly of Sol. |
| `stars-within-star` | All stars in the local `star_systems` table within N ly of a named star. |

## Travel time, velocity converters & brachistochrone
| Command | Description |
|---|---|
| `travel-time` | FTL travel time between two stars at a given velocity. |
| `ly-hr-to-times-c` | Convert a ly/hr velocity to multiples of c. |
| `times-c-to-ly-hr` | Convert a multiple-of-c velocity to ly/hr. |
| `distance-traveled-ly-hr` | Distance covered at a ly/hr velocity over a given time. |
| `distance-traveled-times-c` | Distance covered at a multiple of c over a given time. |
| `travel-time-ly-hr` | Time to travel N light years at a ly/hr velocity. |
| `travel-time-times-c` | Time to travel N light years at a multiple of c. |
| `brachistochrone-au` | Flip-and-burn travel time for three acceleration profiles, distance in AU. |
| `brachistochrone-lm` | Same, distance in light minutes. |
| `distance-at-acceleration` | The inverse of brachistochrone — distance covered by three profiles given acceleration + travel time. |
| `travel-time-solar` | Brachistochrone travel time between two solar-system bodies at a departure epoch (live JPL Horizons). |
| `travel-time-custom-thrust` | Travel time between two solar-system bodies with a custom burn duration (accel / coast / decel; live JPL Horizons). |
| `relativistic-brachistochrone` | Flip-and-burn under constant proper acceleration (relativistically correct; lifts the 3% c cap). |

## Habitable zone & core equations
| Command | Description |
|---|---|
| `habitable-zone` | Kopparapu HZ boundaries from Teff + luminosity. |
| `habitable-zone-sma` | HZ boundaries plus an object's S_eff at its orbit and an in-HZ verdict. |
| `star-luminosity` | Stellar luminosity from radius and temperature: L = R²·(T/5778)⁴. |
| `orbit-distance` | Periastron / apastron from semi-major axis + eccentricity. |
| `moon-orbital-distance` | Orbital distance of an Earth-sized moon for a given day length. |
| `gravity-acceleration` | Centrifugal artificial gravity (m/s²) from rpm + radius. |
| `gravity-distance` | Radius from the centre of rotation from rpm + target gravity. |
| `gravity-rpm` | Rotation rate (rpm) from target gravity + radius. |
| `stellar-evolution` | Evolutionary-stage durations + timeline for a star of a given mass (0.1–20 M☉). |

## Worldbuilding physics (Phase H + T)
| Command | Description |
|---|---|
| `roche-limit` | Rigid-body and fluid Roche limits for a satellite orbiting a primary. |
| `tidal-locking` | Tidal-locking timescale of a satellite (MacDonald 1964). |
| `hill-sphere` | Hill sphere + stable-moon limit of a planet (Domingos 2006). |
| `binary-stability` | Planet-orbit stability in a binary (Holman & Wiegert 1999). |
| `atmosphere-retention` | Which atmospheric gases a planet retains against Jeans escape. |
| `trojan-stability` | L4/L5 (Trojan) co-orbital linear-stability test (Gascheau / Routh, μ < 0.0385). |
| `lorentz-factor` | Special-relativistic Lorentz / time-dilation factor for a sublight velocity. |
| `circumbinary-hz` | Circumbinary (P-type) habitable zone from the two stars' combined light. |
| `tidal-heating` | Tidal heating power + surface flux of a synchronous satellite (order-of-magnitude). |
| `kozai-lidov` | Kozai–Lidov oscillation timescale of a hierarchical triple (order-of-magnitude). |

## Detectability / survey-bias (Phase T1b)
| Command | Description |
|---|---|
| `rv-semi-amplitude` | Radial-velocity semi-amplitude a planet induces on its star (Lovis & Fischer 2010). |
| `transit-signal` | Transit depth, geometric probability, and duration (Winn 2010). |
| `astrometric-signal` | Astrometric wobble of a star induced by a planet (µas headline). |
| `direct-imaging` | Reflected-light contrast + angular separation, optionally vs a telescope inner working angle. |

## Solvent zones & ice lines (Phase P)
| Command | Description |
|---|---|
| `solvent-zone` | The AU band where a solvent is liquid on a planet surface (M1 surface model). |
| `ice-lines` | The water snow line (170 K) plus the CO₂/NH₃/N₂/CO condensation fronts (M2 equilibrium model). |

## Route planning
| Command | Description |
|---|---|
| `optimal-tour` | Shortest-total-distance visit order for a set of stars (nearest-neighbour seed + 2-opt). |
| `jump-route` | Route origin→destination over a jump-limited graph (Dijkstra for distance / BFS for fewest jumps). |
| `jump-network` | BFS reachability tiers from a start star at a given jump range. |
| `multi-stop` | Cumulative travel time along an ordered list of stops (you supply the order). |
| `nearest-neighbor` | Greedy nearest-unvisited chain from a start star over the `star_systems` pool. |
| `farthest-first` | De-clustering coverage chain — each step picks the star farthest from the visited set. |
| `trade-route` | Minimum spanning tree connecting a set of systems (Kruskal). |

## Search & compare
| Command | Description |
|---|---|
| `search-star-systems` | Filter the local `star_systems` table (all filters optional, no network). |
| `search-hwc` | Filter the local Habitable Worlds Catalog (no network). |
| `search-exoplanets` | Filter the live NASA pscomppars archive via TAP. |
| `search-hypatia` | Filter the local Hypatia abundance cache (no network). |
| `compare-stars` | Side-by-side comparison of 2–4 stars (SIMBAD + NASA supplement + HZ + Hypatia). CR-11.2: per-star mass-provenance block + `--star-mass-catalog`; measured mass preferred → `mass`/`radius` track it. |

## Cooling, thermal, shielding & compute (U / V / AD / AR)
| Command | Description |
|---|---|
| `cooling-hz` | HZ snapshot, residence time, or continuous-HZ band for a cooling white/brown-dwarf primary. WD grid 0.40–1.30 M☉, a dense Bédard-2020 re-derivation (CR-12; source-faithful cooling ages; clamp 1.30–1.38 Chandrasekhar, refuse above); high-mass WDs (M>1.05) carry an additive `one_core_uncertain` notes caveat in all modes (CR-12.4). |
| `waste-heat` | Waste heat a device must reject from a power figure + efficiency, with an optional Carnot ceiling. |
| `radiator-area` | Radiating area (and optional mass) to reject a heat load (Stefan–Boltzmann). |
| `shielding-attenuation` | Attenuation of penetrating radiation by shielding mass (photon Lambert–Beer / GCR / charged-particle). |
| `active-shield` | Active magnetic-shield rigidity cutoff (Störmer) + deflected fraction + field, from a dipole/coil/field source. |
| `equilibrium-temp` | Planetary equilibrium temperature + a greenhouse surface temperature. |
| `insolation-shift` | Orbital mirror (warm) / shade (cool) area to change a sphere-averaged absorbed flux. |
| `atmosphere-mass` | Hydrostatic atmosphere mass ↔ surface pressure (and the inverse). |
| `heat-pump` | Active-refrigeration Carnot COP — the inverse of `waste-heat`. |
| `landauer-limit` | Irreversible-compute energy floor E_bit = k_B·T·ln2. |

## Propulsion & drag (Y / AC / AD)
| Command | Description |
|---|---|
| `rocket-equation` | Tsiolkovsky (classical + relativistic) mass ratio + propellant fraction from any two of {velocity, exhaust, mass ratio}. |
| `beam-sail` | Thrust, acceleration, and optional final velocity of a laser / photon sail. |
| `magsail` | Magnetic-sail braking against the ISM (standoff, drag ∝ v^4/3, deceleration, stopping distance/time). |
| `ramscoop` | Bussard ramjet drive-vs-brake verdict + crossover velocity. |
| `pellet-stream` | Pellet-stream (momentum-beam) drive: thrust, delivered power, and drive/no-thrust verdict. |
| `dust-impact` | Hypervelocity dust-grain impact energetics: kinetic energy, TNT-equiv, momentum, optional cumulative fluence. |
| `volatile-delivery` | Volatile delivery by icy-body redirect: delivered mass, redirect mass ratio, impact energy, bodies needed. |

## Megastructures (Z / AD)
| Command | Description |
|---|---|
| `orbital-ring` | Orbital-ring rotor velocity & support balance (local gravity, orbital vs rotor velocity, rotor KE per length). |
| `spin-stress` | Hoop-stress size limit: the max habitat radius/gravity a material can spin. |
| `tether-taper` | Space-elevator / skyhook taper ratio for a material + body (Pearson uniform stress). |
| `dyson-collector` | Collector area & mass to intercept a fraction of a star's luminosity. |

## Habitats & life support (W / X / AA)
| Command | Description |
|---|---|
| `spin-comfort` | Rotating-habitat comfort: the full spin state from any two anchors + a tiered comfort verdict. |
| `life-support` | Closed-loop crew consumables/waste budget (BVAD rates) + closure-scenario makeup mass. |
| `bioregen-area` | Bioregenerative grow area + lighting power to feed a crew (PAR energy balance). |
| `population-capacity` | Sustainable population from resource budgets, reporting the binding constraint. |
| `par-flux` | PAR fraction / irradiance / PPFD and the red-star deficit vs G2 from a blackbody SED. |

## Power generation & storage (AL)
| Command | Description |
|---|---|
| `annihilation-power-train` | Antimatter annihilation power partition: total ṁ·c² split into directed / γ-heat / ν-loss. |
| `antimatter-production` | Antimatter production energy floor + Penning-trap storage-density ceiling. |
| `reactor-net-power` | Net-energy / Q-gate accounting: how much gross reactor output survives recirculation. |
| `beamed-power-delivery` | Diffraction-limited beamed-power link efficiency (the λL/D wall). |
| `fusion-lawson` | Lawson triple-product → fusion gain Q. |
| `flywheel-storage` | Flywheel specific-energy ceiling e = K·σ/ρ (material-strength wall). |
| `smes-storage` | SMES magnetic energy density u = B²/2µ₀ + structure-limited specific energy. |
| `energy-storage` | Bundled battery/chemical/thermal specific energies (+ sensible/latent compute). |
| `reactor-power` | Bundled reactor specific power α = P/m [kW/kg] + a mandatory thermal pointer. |
| `beamrider-relay-spacing` | Diffraction-limited beamrider relay-node spacing (inverts `beamed-power-delivery`). |

## Sensing & strategic geography (AP / AQ)
| Command | Description |
|---|---|
| `angular-resolution` | Diffraction-limited resolution θ = k·λ/D (Rayleigh / Dawes / Sparrow). |
| `point-source-detection` | Unresolved point-source detection SNR / max range (the "no stealth in space" core). |
| `radar-range` | Active radar range equation (the R⁻⁴ counterpart to passive R⁻²). |
| `network-centrality` | Route value / chokepoints: betweenness + articulation points + bridges + min-cut over the jump graph. |
| `arrival-corridors` | FTL-emergence / picket geometry: cluster origin bearings into corridors + size the picket sky coverage. |

## Gravitation & relativity (AE / AF)
| Command | Description |
|---|---|
| `escape-velocity` | Escape / circular speed from a body or at a distance in its field. |
| `gravitational-potential` | Gravity-well depth, binding energy, and climb-out Δv between two radii. |
| `sphere-of-influence` | Laplace sphere of influence + Hill radius for a body orbiting a primary. |
| `hyperbolic-approach` | Braking-corridor geometry for a hyperbolic arrival (v_p, C₃, capture Δv). |
| `time-dilation` | Special and/or gravitational time dilation. |
| `length-contraction` | Relativistic length contraction L = L₀/γ. |
| `velocity-addition` | Relativistic velocity addition. |
| `relativistic-doppler` | Relativistic Doppler factor + shifted λ/f (approach / recede / arbitrary angle). |
| `rapidity` | Rapidity φ = artanh(β), with linear composition via `--add`. |
| `relativistic-energy-momentum` | Relativistic energy, momentum, and kinetic energy of a particle. |
| `lorentz-transform` | Lorentz coordinate transform + simultaneity offset. |
| `causality-check` | FTL tachyonic-antitelephone causality guardrail (closed causal loop when u·v > c²). |

## Exotic physics (AG)
| Command | Description |
|---|---|
| `casimir` | Casimir pressure / negative energy density (or sphere-plate force). |
| `vacuum-energy` | Dark-energy density + the QED vacuum-catastrophe ratio. |
| `schwinger-limit` | Schwinger critical field / intensity for pair production. |
| `hubble-flow` | Cosmological recession, or a local-binding turnaround test. |

## Black holes (AI)
| Command | Description |
|---|---|
| `schwarzschild-radius` | Schwarzschild radius r_s = 2GM/c². |
| `hawking-temperature` | Hawking temperature (or the inverse T → mass). |
| `black-hole-evaporation` | Hawking power + evaporation lifetime (or the inverse). |
| `bekenstein-hawking-entropy` | Bekenstein–Hawking horizon entropy. |
| `isco` | Innermost stable circular orbit + binding efficiency. |
| `kerr-horizon` | Kerr outer/inner horizons + ergosphere. |
| `bh-tidal-force` | Tidal (spaghettification) gradient + threshold radius. |
| `eddington-luminosity` | Eddington luminosity + accretion rate. |
| `unruh-temperature` | Unruh temperature for an accelerated observer. |
| `bekenstein-bound` | Bekenstein entropy / information bound in a region. |

## Warp drive (AH)
| Command | Description |
|---|---|
| `alcubierre-energy` | Negative-energy budget of an Alcubierre warp bubble (numeric original + reported reduction ladder). |
| `warp-metric` | Alcubierre metric geometry: shape function, expansion scalar, wall region. |

## Planet formation (AJ)
| Command | Description |
|---|---|
| `disk-model` | MMSN-scalable disk Σ_gas / Σ_solid / T / (H/r) profile at a radius or over a grid. |
| `isolation-mass` | Oligarchic isolation mass M_iso (Armitage). |
| `pebble-isolation-mass` | Pebble-accretion cutoff — the super-Earth ↔ giant switch (Bitsch 2018). |
| `gap-opening-mass` | Type-II gap-opening threshold via the Crida criterion (root-find). |
| `toomre-q` | Disk gravitational-instability parameter Q (core-accretion ↔ GI boundary). |
| `critical-core-mass` | Envelope-runaway (critical core) mass for gas-giant formation. |

## Metric drive / FTL boundary (AK)
| Command | Description |
|---|---|
| `metric-drive-power` | Metric-drive field-rocket radiated power + fuel/mass bill (STL-mode law only). |
| `exclusion-boundary` | FTL exclusion-boundary radius r_ex (the "Alcubierre Limit"); a Kuiper-calibrated in-universe dial. |
| `exclusion-system` | CR-11.3: compose `exclusion-boundary` over a binary/multi-star system (`--star` or `--component`) into merge-grouped, phase-varying, asymmetric zones with per-component off-MS domain guards. |

## ISM dust / extinction (T2)
| Command | Description |
|---|---|
| `dust-sightline` | ISM dust extinction profile (A_V) along one direction (needs the optional dustmaps extra). |
| `dust-between` | ISM dust extinction (A_V) along the straight line between two stars. |

## Live catalog access (AM)
| Command | Description |
|---|---|
| `vizier-query` | Any VizieR catalog by id → JSON rows (live network). |
| `catalog-cache-clear` | Wipe the catalog caches (app `data/catalog_cache/` + any residual astroquery HTTP cache). Offline maintenance. |
| `gaia-tap` | Any Gaia DR3 table by raw ADQL or a structured filter (live network). |
| `heasarc-query` | A HEASARC X-ray catalog by cone or raw TAP/ADQL (live network). |
| `binary-orbit` | Every orbital solution for a star (Gaia NSS + SB9 + WDS/orb6) with companion-mass star/BD/planet classification (live). CR-16: a degenerate/WD-secondary query resolves the primary's sp-type for the companion masses (additive `identity.primary`/`mass_resolved_via_primary`; `binary-orbit "Sirius B"` → 2.18/0.4577 = `"Sirius"`), staying a raw reporter (no catalog). |
| `close-binary-census` | A systematic close-binary population sweep (Gaia NSS + SB9, X-Match dedup, planet filter) (live). |
| `gaia-astrophysical` | Gaia GSP-Phot + FLAME stellar parameters incl. age for one source (live). |
| `besancon-query` | Besançon Galaxy Model (m1612) synthetic field population + derived age distribution (live; needs credentials). |

## Dossier, projects & generation (Q / R / S)
| Command | Description |
|---|---|
| `dossier` | Render a complete, self-contained system dossier by composing the existing readers (markdown / html / json). CR-10.5: self-flags evolved hosts (luminosity-class region guard, `--force-ms-inversion`) + cross-checks `binary-orbit` for multiplicity (`multiplicity_basis`). CR-11.2: stellar-mass provenance block + `--star-mass-catalog`/`--mass-solar`; a preferred measured mass recomputes the mass-derived fields (radius/calc-L/limits) coherently. CR-16: a secondary-named target's `multiplicity` masses resolve via the primary (`"Sirius B"` → 2.063/0.4577, matching the system-name dossier). |
| `project-list` | List project workspaces (name, description, member count). |
| `project-get` | A project workspace + its members (with `generated_spec` echoed parsed). |
| `generate-system` | Deterministically generate a plausible planetary system (synthetic-from-seed or real-anchor). |

## Star analysis (sister `star_analysis` skill — CR-1…10)
| Command | Description |
|---|---|
| `debris-disk` | Observed IR-excess debris disk vs Chen 2014 + Cotten & Song 2016, else a per-star AllWISE-W4 warm-dust upper limit (never null). LIVE. |
| `multiplicity` | Stellar-multiplicity summary — otype hint + `binary-orbit` tool-split + GCNS component count (SB1 masses = sin i=1 lower bound). LIVE. CR-16: a degenerate/WD-secondary query's `m2_solar_lower` is now solved at the correct primary mass (`"Sirius B"` → 0.4577, not 0.283). |
| `binary-stability-auto` | Auto-pipe `binary-orbit` → Holman-Wiegert S/P-type stability with a **catalog-aware per-component mass chain** (`--star-mass-catalog`; same masses as `exclusion-system`/dossier) + real-ratio solution selection + `e_out_of_hw_range` flag. LIVE. CR-16: a degenerate/WD-secondary query resolves via the primary → `"Sirius B"` = `"Sirius"` (2.063/0.4577; 2.063/1.018 w/ catalog). |
| `population-classify` | Thin/thick/halo Galactic-population verdict from U/V/W (Bensby velocity-ellipsoid on a Schönrich LSR). |
| `nuclear-inventory` | Fusion + fissile (per-isotope GCE, WB 3c FINAL) + radiogenic-heat inventory from stellar [Fe/H]/age/[Eu/H]; CR-10.2 `[Fe/H]>+0.5` soft `feh_extrapolation` flag. |
| `detection-completeness` | Per-method min-detectable-planet-vs-SMA map (RV/transit/astrometry/imaging), WB 3a FINAL defaults; CR-10.4 archive-M★ preference + `star_mass_provenance`; CR-10.3 per-star RV tier-2 catalog (`--rv-precision-catalog`) + per-method `floor_provenance`. |
| `planetary-systems-batch` | Batch NASA `ps` pull — full per-planet + per-system fields for many hosts; CR-9 disposition/quality + CR-10.1 `survey_disposition`/`survey_siblings` (live TOI/KOI/K2 FP/candidate cross-match). LIVE. |

## Weapons & engagement physics (Phase AT)
| Command | Description |
|---|---|
| `salvo-exchange` | Hughes *Fleet Tactics* salvo-combat model over eight modes (simultaneous / first-strike / sequential-waves / break-even / solve-force / distribute / layered-defense / saturation-stream) + an opt-in `--light-lag` σ/δ one-way-lag degradation option (Packet 38.2 CR-A/CR-B). |
| `beam-weapon-engagement` | Diffraction-limited beam spot (top-hat + Gaussian), intensity, dwell-to-kill, and effective range. |
| `kinetic-kill` | Kinetic-impactor energy (classical ½mv² + relativistic (γ−1)mc²), TNT-tons, long-rod penetration + crater OOM, monolithic/Whipple verdict. |
| `warhead-effects-at-standoff` | Vacuum inverse-square warhead flux per channel → per-channel kill radius + the binding channel (yield is an input). |

## Radiation dose ceiling (Phase AS)
| Command | Description |
|---|---|
| `radiation-ceiling` | Per-clade radiation dose → two independent biological ceilings at once — acute/deterministic (Gy, RBE-weighted) + stochastic/cancer (Sv, ICRP-Q REID) — with lever-tagged clade modifiers and per-value provenance tags. |
