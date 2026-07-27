# Phase R — Procedural System Generation & Feasibility Mockup

> **Status:** mockup + analysis only — no `core/generate.py` exists yet. This file
> folds the **analysis pass** (verified function reuse + gaps) into the **design**
> agreed in discussion (2026-06-21), then surfaces the open decisions to react to
> before `PHASE_R_PLAN.md` is written. Values below are illustrative, hand-authored
> to anchor the shapes.

---

## 0. Scope evolution (read first)

The `future_phases.md` brainstorm scoped Phase R as a **generator only** ("produce
plausible star systems, the inverse of the analysis tools"). The 2026-06-21 design
discussion **expanded** it into a generator **plus a constraint-driven feasibility
analyzer**:

> Pass in desired features for a system; the tool decides whether they're physically
> possible, reports the verdict with reasoning, proposes alternatives when they fail,
> and (when feasible) generates a system satisfying them. Both **synthetic-from-seed**
> and **real-anchor** modes accept the constraints. Exposed via **`query.py` and the
> GUI**.

That is a materially larger phase than the brainstorm. Decisions in §6 include whether
to split it into sub-phases (recommended).

### Locked decisions (from discussion)

1. **Hybrid data model** — synthetic-from-seed mode *and* real-anchor mode (pull a
   real star's specs + observed planets, procedurally extend). Every body flagged
   `source: "observed" | "synthetic"`.
2. **NL boundary** — `core/` is deterministic and takes a **structured constraint
   spec** (JSON). The natural-language→spec translation happens **only** on the
   `query.py` consumer side (the `scifiWorldBuilding-Claude` agent, on the user's
   subscription, for free). **No LLM in the app**, no API key, no CLI-token hack.
3. **GUI = structured constraint builder** — form widgets emit the *same* spec JSON
   the agent produces. The GUI never parses prose.
4. **Research-priors hook** — the sister project's stellar/system/planet-formation
   research (roadmap packets #2/#3/#4/#8/#12, currently all *Not Started*) is **not a
   blocker**. A swappable priors-provider (`DefaultPriors` / `ResearchPriors` /
   absent) carries all research sensitivity behind one seam; outputs are
   confidence-tagged.
5. **Four-layer output** — verdict / mechanism / origin-narrative / alternatives
   (§3). Only the origin-narrative layer + synthetic *population realism* are
   research-sensitive.

### Resolved at mockup review (2026-06-21)

6. **Phasing → split R1 / R2 / R3.** R1 = generation engine (synthetic +
   real-anchor) on `DefaultPriors`. R2 = constraint/feasibility engine (4-layer
   output + the G1–G4 stability/resonance physics). R3 = research-priors hook +
   synthetic population realism. Each ships green at its own checkpoint.
7. **Synthetic realism bar (v1) → DefaultPriors.** Conservative, literature-informed
   occurrence/mass/architecture values; every synthetic field tagged
   `grounding="default-extrapolation"`; upgrades via the R3 hook when research lands.
8. **Stability fidelity → analytic criteria + optional N-body confirmation.** The
   verdict uses the closed-form criteria (mutual-Hill / Gladman–Chambers / AMD /
   resonance) by default; **marginal cases get an optional short N-body check.**
   Implemented as a self-contained **pure-numpy fixed-timestep symplectic integrator**
   (`core/nbody.py`) — numpy is already a dependency; **no scipy**. Fixed timestep +
   fixed initial conditions ⇒ deterministic and unit-testable. N-body is opt-in
   (a flag / "confirm marginal" action), not on every call.
9. **Layer 3 (origin narrative) → in the first feasibility build (R2), confidence-
   tagged.** Ranked formation hypotheses, each `grounding`-tagged; degrades through
   the R3 hook; never asserts an un-sourced fact.

---

## 1. Analysis pass — verified reuse vs. new code

Every existing function below was read in `core/` and its signature + return shape
confirmed (2026-06-21).

### 1a. Reusable as-is (no research dependency)

| Function | Module | Signature (verified) | R uses it for |
|---|---|---|---|
| `compute_main_sequence_table()` | science.py | → list[24 dicts]; keys incl. `"Spectral Class"`, **`"Teeff(K)"`**, `"M"`, `"R"`, `"Lum"`, `"Bolo. Corr. (BC)"` | Synthetic star: interpolate Teff/M/R/L from spectral class |
| `compute_star_luminosity(radius, temp)` | equations.py | → `{radius, temp, luminosity}` | Synthetic star luminosity (R²·(T/5778)⁴) |
| `compute_habitable_zone(teff, luminosity)` | equations.py | → list[6 zone dicts] `{zone_name, key, au, lm, seff}` (`rv,rg5,rg,rg01,mg,em`) | HZ ring; "in HZ" flag; `--require-habitable` |
| `compute_habitable_zone_sma(teff, lum, sma)` | equations.py | → `{zones, planet_seff, verdict}` | Per-planet HZ membership verdict |
| `compute_hill_sphere(star_mass_solar, planet_mass_earth, sma_au, ecc=0)` | equations.py | → `{hill_radius_au, stable_orbit_limit_au, …}` | Moon-orbit outer bound; single-body SOI |
| `compute_roche_limit(primary_mass_earth, satellite_density_gcc, primary_radius_earth=None)` | equations.py | → `{rigid_km, fluid_km, rigid_au, fluid_au, …}` | Moon-orbit inner bound (primary mass in **Earth** masses) |
| `compute_atmosphere_retention(planet_mass_earth, planet_radius_earth, temperature_k)` | equations.py | → `{v_escape_kms, gases[…status]}` | "retains N₂/O₂/…"; terraformability gate |
| `compute_tidal_locking_time(…)` | equations.py | → `{lock_time_years, lock_time_gyr, …}` | Moon/terraformability annotation |
| `compute_binary_orbit_stability(m1_solar, m2_solar, binary_sma_au, test_sma_au, ecc=0)` | equations.py | → `{stype_critical_sma_au, ptype_critical_sma_au, orbit_type, is_stable, …}` | Binary-anchored / circumbinary feasibility |
| `compute_ice_lines(luminosity_solar, albedo=0)` | equations.py | → `{t_ref_k, lines[{species, au, kind, disk_line}]}` | Snow-line placement; ice/gas classification |
| `compute_solvent_zone(luminosity_solar, solvent=…, …)` | equations.py | → solvent liquid band | Alt-biochem ("ammonia ocean") feasibility |

### 1b. Real-anchor readers (networked; verified)

| Function | Returns | Note |
|---|---|---|
| `compute_simbad_lookup(star)` | `{main_id, sp_type, teff, vmag, plx_value, ly, parsecs, designations, …}` | Entry point for real-anchor |
| `compute_star_system_regions_from_simbad(simbad_result, sunlight=1.0, albedo=0.3)` | flat regions dict + `spectral_type` (incl. `stellarMass, stellarRadius, bcLuminosity, temp, hzil, hzol, snowLine`) | **Errors cleanly** on non-OBAFGKM stars and when teff/vmag/plx missing → real-anchor degrades to a warning |
| `compute_planetary_systems_composite(simbad_result)` | `{simbad, planets[]}` raw pscomppars rows (`pl_name, pl_bmasse, pl_rade, pl_orbsmax, pl_orbeccen, …`) | Observed planets (priority 1) |
| `compute_hwc(simbad_result)` | `{simbad, star_row, planet_rows[]}` | Observed planets (priority 2) |

### 1c. Gaps — NEW code Phase R must add (all Tier-A textbook physics, **no research gate**)

| New | What | Why existing code can't do it |
|---|---|---|
| **G1 · multi-body packing stability** | mutual Hill radius + Gladman/Chambers separation (Δ ≥ ~2√3 critical; ~10 long-term) + optional AMD stability | `compute_hill_sphere` is **single-planet** only — can't answer "does an Earth fit between b and c" |
| **G2 · resonance / co-orbital diagnostics** | period-ratio→MMR detection; Gascheau co-orbital criterion (m₁+m₂ ≲ 0.0385 M★); L4/L5 Trojan stability | none exist (`compute_hyper_limit…` is unrelated Honorverse) — needed for the Trojan example + Layer-2 "why is it stable" |
| **G3 · planet-type classifier** | rocky / ice / gas / super-Jovian by mass + insolation vs frost line | trivial, but nothing classifies today |
| **G4 · equilibrium-temp helper** | T_eq(L, a, albedo) for an arbitrary orbit | Phase P has `_t_ref`/`implied_edge_temp` to reuse; thin wrapper |
| **G5 · constraint spec + rule registry + evaluator + alternatives** | the feasibility engine (§2–§3) | the whole new feature |
| **G6 · generation engine** | seeded placement (Titius–Bode-ish jitter), de-conflict vs observed orbits, moons/rings | new |
| **G7 · priors-provider hook** | `DefaultPriors` / `ResearchPriors` / absent + policy switch | new (§4) |

**Finding:** the feasibility *engine* and the *generator* depend only on physics
already present + the G1–G4 textbook additions. **Nothing in the engine waits on the
sister-project research.** Only Layer 3 (origin narrative) and synthetic *population
realism* are research-sensitive, and both sit behind the G7 hook (§4).

---

## 2. The constraint spec (the contract both front-ends emit)

A structured, validated JSON object. The GUI builder and the `query.py` agent both
produce this; `core/` only ever sees this.

```jsonc
{
  "mode": "synthetic" | "real_anchor",
  "seed": 4173,                          // deterministic; required
  "anchor_star": "47 Ursae Majoris",     // real_anchor only
  "spectral_class": "G1V",               // synthetic only (optional → sampled)
  "n_planets": 6,                        // optional
  "constraints": [
    { "id": "c1", "type": "planet_at_location",
      "planet_type": "terrestrial", "mass_earth": 1.0,
      "location": { "kind": "between", "ref_a": "b", "ref_b": "c" } },
    { "id": "c2", "type": "trojan",
      "companion_type": "terrestrial", "host": "giant_in_hz", "point": "L4" },
    { "id": "c3", "type": "moon",
      "host": "super_jovian_in_hz", "mass_earth": 1.0, "terraformable": true }
  ],
  "research_policy": "permissive" | "strict",   // default permissive
  "require_habitable": false
}
```

Unsupported `type` values → `verdict: "not_evaluated"` (never a hard error), since the
input set is open-ended.

---

## 3. Four-layer output

`evaluate_feasibility(spec)` returns per-constraint verdicts + an optional generated
system. Each layer's research dependency is marked.

| Layer | Question | Source | Research? |
|---|---|---|---|
| 1 · **verdict** | Is it dynamically stable / physically possible? | physics (G1–G4 + existing) | No |
| 2 · **mechanism** | *Why* is it stable? (resonance / Trojan / packing / secular) | physics diagnostics (G2) | No |
| 3 · **origin** | *How* did it get there? (in-situ / scattered / captured) — ranked hypotheses | priors hook | **Yes** → degrades |
| 4 · **alternatives** | If infeasible, nearest feasible parameters | boundary relaxation | No |

### Example A — feasibility query (real-anchor 47 UMa, "Earth between the giants")

```bash
query.py generate-system --seed 4173 --anchor-star "47 Ursae Majoris" \
  --constraint 'planet_at_location:terrestrial,1.0,between:b:c'
```
```jsonc
{
  "seed": 4173, "mode": "real_anchor", "anchor_star": "47 Ursae Majoris",
  "feasible": false,
  "constraints": [
    {
      "id": "c1", "type": "planet_at_location",
      "verdict": "infeasible",
      "layer1": { "stable": false,
                  "reason": "1.0 M⊕ at 2.85 AU sits 3.1 mutual Hill radii from b and 2.4 from c; long-term stability needs ≳ 8–10. Feeding zones of b and c overlap the gap." },
      "layer2": { "mechanism": null,
                  "checked": ["mean_motion_resonance","trojan","amd_packing"],
                  "note": "no protecting resonance found near the gap" },
      "layer3": { "hypotheses": [
                    { "pathway": "captured/scattered survivor", "plausibility": "low",
                      "grounding": "default-extrapolation" } ],
                  "grounding": "default-extrapolation" },
      "layer4": { "alternatives": [
                    { "change": "mass_earth → 0.05", "result": "marginally stable (Mars-class test particle)" },
                    { "change": "location → interior to b (1.3 AU, in HZ)", "result": "feasible, stable, in conservative HZ" },
                    { "change": "lock into 2:1 MMR with c (2.27 AU)", "result": "feasible via resonant protection" } ] }
    }
  ],
  "warnings": [], "notes": ["Layer-3 grounding is default-extrapolation; refines when research packets #3/#4 land."]
}
```

### Example B — generation (synthetic, habitable required)

```bash
query.py generate-system --seed 88 --spectral-class K2V --planets 5 --require-habitable
```
```jsonc
{
  "seed": 88, "mode": "synthetic",
  "star": { "name": "Seed-88 (K2V)", "spectral_class": "K2V", "teff": 4960,
            "mass_solar": 0.78, "radius_solar": 0.74, "luminosity": 0.29,
            "hz_inner_au": 0.49, "hz_outer_au": 0.86, "snow_line_au": 1.44,
            "source": "synthetic", "grounding": "default-extrapolation" },
  "planets": [
    { "name": "Seed-88 b", "a_au": 0.21, "mass_earth": 0.6, "radius_earth": 0.85,
      "type": "rocky", "t_eq_k": 470, "in_hz": false, "source": "synthetic" },
    { "name": "Seed-88 c", "a_au": 0.63, "mass_earth": 1.1, "radius_earth": 1.03,
      "type": "rocky", "t_eq_k": 268, "in_hz": true, "source": "synthetic",
      "atmosphere": "retains N₂, O₂, H₂O, CO₂" },
    { "name": "Seed-88 d", "a_au": 2.9, "mass_earth": 190, "radius_earth": 9.1,
      "type": "gas", "source": "synthetic",
      "moons": [ { "name": "d I", "a_planet_radii": 12, "mass_earth": 0.02,
                   "between_roche_and_hill": true, "source": "synthetic" } ] }
  ],
  "warnings": [], "notes": ["Population statistics are default-extrapolation, not research-calibrated."]
}
```

Both shapes reuse the planet/star row keys the analysis panels already render, so a
generated system flows into the existing HZ/orbit diagrams and a **Phase Q dossier**
with zero new viz.

---

## 4. The research-priors hook (the one research seam)

```
core/priors.py
  PriorsProvider (interface)
    DefaultPriors    → literature/textbook values; outputs grounding="default-extrapolation"
    ResearchPriors   → reads an ingested "formation-priors" data product (when present);
                       grounding="research-sourced" + source tier
    (absent)         → research-only judgements return {"status":"not_evaluated"}
```

- **Ingestion mirrors CSV/GCNS/Hypatia imports** — research priors arrive as a
  versioned data file the app imports, not hardcoded constants.
- **Policy switch** (`research_policy`): `permissive` (run on defaults, every
  research-sensitive field tagged) | `strict` (research-dependent fields →
  `not_evaluated`; verdict + mechanism still answer).
- **Contract to lock early:** a small versioned *formation-priors schema* (occurrence
  table, architecture templates, pathway-plausibility table) — defined contract-by-
  reference, so the sister project knows the delivery target and R builds against a
  stable interface with `DefaultPriors` standing in.

What the hook gates: Layer-3 origin-narrative *quality/thresholds*, synthetic
*population realism* (occurrence rates, mass distributions, architecture templates,
multiplicity, moon priors, metallicity), and real-anchor *formation annotations*.
Everything else ignores it.

---

## 5. GUI mockup — `SystemGeneratorPanel`

```
┌─ System Generator ───────────────────────────────────────────────┐
│ Seed:  [ 4173        ] [🎲 Randomize]   (deterministic)            │
│ Mode:  ( ) Synthetic   (•) Anchor on real star                    │
│ Anchor star: [ 47 Ursae Majoris            ]   (blank → synthetic)│
│ Spectral class (synthetic): [O][B][A][F][G•][K][M]  subtype [1V ] │
│ Planets: [ 6 ]   [✓] require habitable                            │
│ Research priors: (•) permissive  ( ) strict     status: DEFAULTS  │
│                                                                    │
│ ── Desired features (constraints) ──────────────  [+ Add]         │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ ① Planet at location  type[terrestrial▾] mass[1.0]M⊕      │    │
│  │    location [between▾] ref-a[b ▾] ref-b[c ▾]        [✕]   │    │
│  │ ② Trojan  companion[terrestrial▾] host[giant in HZ▾]      │    │
│  │    point [L4▾]                                       [✕]   │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                          [ Generate / Evaluate ]   │
├────────────────────────────────────────────────────────────────── │
│  Verdict: ✗ NOT FEASIBLE as specified                             │
│  ① between b,c: unstable (3.1 mutual Hill radii; need ≳8). →       │
│     Try: interior to b (1.3 AU, in HZ) ✓ | 0.05 M⊕ ✓ | 2:1 MMR ✓  │
│  ── tabs: [Planet Table] [Orbit Diagram] [HZ Ring] [Send to Dossier]
└────────────────────────────────────────────────────────────────── ┘
```

- Constraints are added via the structured builder (dropdowns/fields → spec JSON).
  No free-text box.
- Observed vs synthetic bodies styled distinctly in the diagrams (reuse
  `make_orbits_canvas` / `make_hz_canvas`).
- "Send to Dossier" hands the result to Phase Q.

---

## 6. Decisions (resolved 2026-06-21) → drives `PHASE_R_PLAN.md`

All four open choices were answered at mockup review (see §0 items 6–9):

1. **Phasing** → **split R1 / R2 / R3.**
2. **Synthetic realism bar (v1)** → **DefaultPriors** (literature-informed, tagged).
3. **Stability fidelity** → **analytic criteria + optional pure-numpy N-body** for
   marginal cases (`core/nbody.py`, deterministic, no scipy).
4. **Layer 3 origin narrative** → **in R2, confidence-tagged** (degrades via R3 hook).

Standing defaults (not contested): `research_policy=permissive`; constraint vocab v1 =
{planet_at_location, planet_mass, moon, trojan/co-orbital, terraformable, multiplicity,
hz_membership}; alternatives = deterministic boundary-relaxation.

### Sub-phase split for the plan

| Sub-phase | Delivers | New code | Research dep |
|---|---|---|---|
| **R1** | `generate_system()` synthetic + real-anchor; GUI panel (no constraints yet); `generate-system` query.py; render in existing diagrams; Q-dossier handoff | `core/generate.py`, G3/G4 classifier+T_eq, `DefaultPriors` (R3 stub) | none |
| **R2** | constraint spec + rule registry + 4-layer `evaluate_feasibility()`; G1/G2 stability+resonance physics + optional `core/nbody.py`; GUI constraint builder; alternatives engine; Layer-3 (tagged) | `core/feasibility.py`, `core/nbody.py`, G1/G2 | Layer-3 only, via stub |
| **R3** | full `core/priors.py` hook (`ResearchPriors` + ingest), formation-priors data contract, synthetic population realism, strict-policy path | `core/priors.py` + importer | activates the seam |

Each sub-phase: built in numbered checkpoints, full suite green
(`QT_QPA_PLATFORM=offscreen`; 3 live-network failures = baseline) at each, stop for
manual GUI verification.
