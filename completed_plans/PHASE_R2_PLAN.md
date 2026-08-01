# PHASE R2 — Constraint / Feasibility Engine · Implementation Plan

> **Scope.** R2 is the **second of three sub-phases** (R1 engine → **R2 constraint/feasibility
> engine** → R3 research-priors hook; split locked in `PHASE_R_MOCKUP.md` §6). R2 adds a
> **deterministic constraint-driven feasibility analyzer** on top of R1's generator: you describe
> a desired system as **structured constraints**, and `evaluate_feasibility` returns a **four-layer
> verdict per constraint** (stable? · why? · how could it arise? · nearest feasible alternative?)
> plus the satisfied system. New astronomy is limited to two textbook-mechanics helper groups (a
> multi-body packing-stability test + resonance/co-orbital diagnostics) and an **opt-in** pure-numpy
> N-body confirmer; everything else **reuses verified `core/` functions** (including R1's
> `generate_system`). **No research gate** — only the origin layer leans on priors, and it rides
> R1's `DefaultPriors` seam (R3 upgrades it).
>
> **Source files:** new `core/feasibility.py` (the engine + G1/G2 physics + rule registry), new
> `core/nbody.py` (opt-in marginal-case confirmer), edits to `core/generate.py` (delegate when
> constraints present — additive), `query.py` (extend the existing `generate-system` subcommand
> with a repeatable `--constraint` flag + `--nbody`), `gui/panels/generator.py` (constraint
> builder + four-layer display, in place), `docs/` updates, new `tests/test_feasibility.py` +
> `tests/test_nbody.py` (+ additions to `tests/test_query_generate.py` / `tests/test_generator_panel.py`).
>
> **Companion mockups (approved):** `PHASE_R2_MOCKUP.md` (design + analysis) and
> `mockups/PHASE_R2_MOCKUP.html` (panel layout). **No code until this plan is signed off** (house rule).

---

## 0. Decisions carried in (defaults taken 2026-06-22)

| # | Decision |
|---|---|
| D1 — vocab scope | **Core 4 constraint types** ship in R2: `planet_at_location`, `trojan`, `moon`, `resonance`. The other three (`habitable_world`, `alt_solvent_world`, `architecture`) are **stretch within R2** (built in C2/C3 only if the core 4 land with margin) — each is a thin rule over existing physics. The GUI dropdown / DSL still *list* them; an unbuilt type → `verdict:"not_evaluated"` (the same graceful path as a truly unknown type). |
| D2 — N-body | **In R2, but opt-in** (`--nbody` flag / a GUI checkbox), and **only for marginal analytic verdicts**. Analytic feasibility always ships; N-body is a confirmer, never the default path. |
| D3 — multi-star | The app has **no binary-orbit reader**. Accept an **optional `companion` hint** in the spec (`{mass_solar, sma_au, ecc}`) → quantitative S/P-type via `compute_binary_orbit_stability`. A real-anchor multiple with **no** hint → R1's detect+warn+safe-cap, plus a `notes[]` line that quantitative S/P-type needs the hint. (An auto binary reader is a later data-source phase.) |
| D4 — packing threshold | **Δ_long = 10** mutual Hill radii (Chambers 1996 mid-range) for long-term feasible; **Δ_crit = 2√3 ≈ 3.464** (Gladman 1993) is the hard Hill-stability floor; the gray band **[2√3, 10) = `marginal`** (→ optional N-body). |
| D5 — Send to Dossier | **Still deferred** (R1 decision stands). R2 ships **Copy JSON** carrying the full four-layer envelope; the Q-ingest of a generated/feasibility dict remains a later small Q extension. |
| D6 — alternatives | **Clickable-apply.** A Layer-4 alternative chip mutates the spec (the single relaxation it names) and re-runs deterministically. Re-run depth is bounded and each re-run is itself deterministic. |

Standing defaults (not contested): `research_policy="permissive"` (the only functional policy in
R2 — `"strict"` is accepted but notes that it requires R3 research priors and falls back to
permissive); constraint vocab v1 as in `PHASE_R2_MOCKUP.md` §3.

---

## 1. Design summary (the one rule)

`core/feasibility.py` stays **pure** — no Qt, no file I/O, no network of its own (the real-anchor
path calls R1's readers, which handle their own I/O). **Determinism is the headline contract:**
same `(seed, anchor_star, constraint spec)` → **byte-identical** output, *including* the
alternatives list and any N-body verdict. All randomness flows through the single seeded
`random.Random(seed)` that R1 already threads; the N-body integrator is fixed-step with fixed
initial conditions; the alternatives scan is an ordered grid. No `Date.now`, no unseeded RNG, no
set/dict-ordering dependence in emitted lists.

**Single public entry stays `generate_system`** (so the GUI and `query.py` call one function).
R1's signature gains optional kwargs; **zero constraints → the R1 path, byte-identical**:

```python
generate_system(seed, anchor_star=None, spectral_class=None, n_planets=None,
                require_habitable=False,
                constraints=None, companion=None, research_policy="permissive",
                nbody=False) -> dict
```

When `constraints` is non-empty, `generate_system` delegates (function-local import, to avoid a
module-load cycle since `feasibility` imports the R1 base-builder):

```python
if constraints:
    from core.feasibility import evaluate_feasibility
    return evaluate_feasibility(seed, anchor_star, spectral_class, n_planets,
                                require_habitable, constraints, companion,
                                research_policy, nbody)
```

Output (a superset of the R1 shape — the base/satisfied system is still rendered by the existing
diagrams with zero new viz):

```jsonc
{
  "seed": 4173, "mode": "synthetic"|"real_anchor", "anchor_star": null|"47 Ursae Majoris",
  "star": { … R1 star dict … },
  "planets": [ { … R1 planet dicts (observed + synthetic + any feasibly-placed) … } ],
  "feasible": true|false,                 // all *evaluated* constraints feasible
  "constraints": [ {
    "id": "c1", "type": "planet_at_location",
    "verdict": "feasible"|"marginal"|"infeasible"|"not_evaluated",
    "layer1": { "stable": bool|null, "reason": str, "metrics": {…} },
    "layer2": { "mechanism": str|null, "checked": [str], "note": str|null },
    "layer3": { "hypotheses": [ {"pathway": str, "plausibility": "low|medium|high",
                                 "grounding": "default-extrapolation"} ],
                "grounding": "default-extrapolation" },
    "layer4": { "alternatives": [ {"change": str, "result": str, "spec_patch": {…}} ] }
  } ],
  "warnings": [str], "notes": [str]
}
```
`{"error": str}` for a malformed spec / out-of-range numeric / unresolvable anchor
(self-validating). An unresolvable *ref* or an unbuilt/unknown constraint *type* is **not** an
error — that constraint is `not_evaluated` with a note, and the rest still evaluate.

---

## 2. New physics helpers (the only new astronomy) — `core/feasibility.py` + `core/nbody.py`

All formulas are Tier-A textbook celestial mechanics; **no research gate**. They reuse the
`_G / _SOLAR_MASS_KG / _EARTH_MASS_KG / _M_PER_AU` constants and the conversion idioms already in
`core/equations.py`.

### 2a. G1 — multi-body packing stability

```python
mutual_hill(m1_earth, m2_earth, a1_au, a2_au, star_mass_solar) -> dict
```
- Mutual Hill radius `R_H,m = ((m1+m2)/(3·M★))^(1/3) · (a1+a2)/2` (consistent units via the
  existing kg/AU constants).
- Separation `Δ = |a2 − a1| / R_H,m`.
- Returns `{r_hill_mutual_au, delta, hill_stable (Δ ≥ 2√3), long_term_stable (Δ ≥ 10)}`.
- **Anchors (tests):** every adjacent Solar-System planet pair has Δ ≫ 10; an artificially packed
  pair (Δ < 2√3) is `hill_stable=False`.

A `planet_at_location` body is checked against **both** bracketing bodies (observed or generated);
the controlling verdict is the *minimum* Δ.

### 2b. G2 — resonance / co-orbital / Trojan diagnostics

```python
period_ratio(a_inner_au, a_outer_au, star_mass_solar) -> float        # Kepler P²∝a³/M
nearest_mmr(period_ratio, max_order=5) -> dict   # {p, q, ratio_str, offset_frac}
in_mmr(a1_au, a2_au, star_mass_solar, ratio="2:1", tol=0.03) -> bool
gascheau_coorbital_stable(host_mass_earth, companion_mass_earth, star_mass_solar) -> dict
```
- `nearest_mmr` finds the nearest low-order `p:q` (`p+q ≤ 5`) and its fractional offset; `in_mmr`
  tests membership within a libration tolerance.
- **Gascheau/Routh co-orbital (Trojan) criterion:** L4/L5 linearly stable iff
  `(m_host + m_companion)/M★ ≲ 0.03812`. Returns `{mass_ratio, stable, criterion}`.
- **Anchors (tests):** Jupiter+Trojan → stable (ratio ≈ 9.5e-4 ≪ 0.03812); Neptune/Pluto detected
  as a 3:2 MMR; a fabricated 2:1 pair detected.

### 2c. N-body confirmer (opt-in) — `core/nbody.py`

```python
integrate_coplanar(bodies, n_orbits=K, steps_per_orbit=S) -> dict
```
- **Pure-numpy, deterministic**: fixed-step **kick-drift-kick leapfrog** (symplectic), star +
  planets as coplanar point masses, ICs deterministic (circular at a fixed phase from each
  body's `a_au`/`mass`), fixed timestep = (innermost period)/`S`, total = `K` innermost orbits.
  `K`, `S` are fixed module constants → reproducible. **No scipy, no RNG.**
- **Instability flags:** any pairwise separation < a mutual Hill radius, or any body's SMA drifting
  beyond a fixed fractional band → `{survived: False, reason, orbits_run}`; else
  `{survived: True, orbits_run: K}`.
- **Called only for `marginal` analytic cases when `nbody=True`.** A survivor →
  `verdict:"feasible"` with `layer1.note = "N-body confirmed, K orbits"`; an unstable run →
  `"infeasible"` with the same provenance. The note states the **bounded horizon** explicitly — a
  short-integration screen, **not** a Gyr stability proof.

### 2d. Multi-star (reuse, not new)

`compute_binary_orbit_stability(m1_solar, m2_solar, binary_sma_au, test_sma_au, ecc)` is reused
verbatim: with a spec `companion` hint, S-type bodies must sit **inside** the critical SMA and
P-type (circumbinary) **outside** it. No hint on a real-anchor multiple → R1's safe-cap + a note.

---

## 3. The constraint spec + validator (vocab v1 — core 4 committed)

`validate_constraints(constraints, companion) -> None | {"error": str}` checks shape only
(structured; **self-validating** → curated error, Phase H contract). Per `PHASE_R2_MOCKUP.md` §3:

- **`planet_at_location`** — `planet_type` (terrestrial/ice/gas/super_jovian), `mass_earth`,
  `location` (`kind ∈ {at, between, interior_to, exterior_to, in_hz, in_zone}` + refs).
- **`trojan`** — `companion_type`, `host`, `point ∈ {L4, L5}`.
- **`moon`** — `host`, `mass_earth`, `terraformable?`.
- **`resonance`** — `bodies` (two refs), `ratio` (`"p:q"`).

Refs resolve to a planet letter (`"b"`), an observed planet name, or a symbolic anchor
(`giant_in_hz`, `super_jovian_in_hz`, `outermost`). Unresolvable ref → `not_evaluated` + note.
**Stretch (D1):** `habitable_world`, `alt_solvent_world`, `architecture` validators/rules added
only after the core 4 are green.

---

## 4. The evaluator — rule registry + four-layer output

### 4a. Flow

```
evaluate_feasibility(seed, anchor_star, …, constraints, companion, research_policy, nbody):
  1. err = validate_constraints(constraints, companion); if err: return err
  2. base = _build_base_system(seed, anchor_star, spectral_class, n_planets, require_habitable)
       # reuse R1 internals (synthetic _generate_synthetic / real-anchor _generate_real_anchor);
       # observed planets are FIXED reference points. A base {"error"} returns verbatim.
  3. results = []
     for c in constraints:
       rule = _RULE_REGISTRY.get(c["type"])           # missing → not_evaluated
       results.append(rule(c, base, derived, companion, rng, nbody) if rule
                      else _not_evaluated(c, "unsupported constraint type"))
  4. feasible = all(r["verdict"] == "feasible" for r in results if r["verdict"] != "not_evaluated")
       # "marginal"/"infeasible" both make feasible=False; "not_evaluated" is neutral
  5. planets = base planets + any feasibly-placed constraint bodies (deduped, SMA-sorted)
  6. return {seed, mode, anchor_star, star, planets, feasible, constraints: results,
             warnings, notes}
```

`_RULE_REGISTRY` is a plain dict keyed by `type` — the seam for adding constraint types without
touching the evaluator.

### 4b. The four core rules (Layer 1 physics)

- **`planet_at_location`** → resolve location → target SMA; G1 Δ to each bracketing body; `feasible`
  if min Δ ≥ 10, `marginal` if 2√3 ≤ Δ < 10 (→ optional N-body), `infeasible` if Δ < 2√3 — **unless**
  a protecting MMR (G2) applies, which moves the win into Layer 2.
- **`trojan`** → Gascheau criterion on (host+companion)/M★ + L4/L5 stability; `feasible` only if it
  passes.
- **`moon`** → `compute_roche_limit` (inner) < requested SMA < `compute_hill_sphere`
  `stable_orbit_limit` (outer); `terraformable` adds a `_equilibrium_temp` + atmosphere check
  (reusing R1's `_equilibrium_temp` / `compute_atmosphere_retention`).
- **`resonance`** → `in_mmr` for the requested `p:q`; the MMR is then the protecting mechanism the
  packing check may invoke.
- **multi-star** (companion set / real-anchor multiple) → `compute_binary_orbit_stability` S/P-type.

### 4c. Layer 2 (mechanism) / Layer 3 (origin) / Layer 4 (alternatives)

- **Layer 2** — names the protecting mechanism (`mean_motion_resonance` / `trojan` / `hill_packing`
  / `secular` / `none`) + the `checked` list, from the G2 diagnostics.
- **Layer 3** — ranked `{pathway, plausibility, grounding}` hypotheses from simple
  `DefaultPriors`-backed heuristics (giant beyond snow line → *in-situ*; terrestrial in a tight MMR
  → *migration/capture*; close-in giant → *scattered/migrated*). **Every hypothesis tagged
  `grounding="default-extrapolation"`** + a `notes[]` line. R3 swaps the heuristic for
  `ResearchPriors` with **no engine change**.
- **Layer 4** — when not feasible, a **deterministic, ordered** single-parameter relaxation scan
  reports first-feasible-per-axis (capped list), each as `{change, result, spec_patch}`:
  mass down a fixed ladder (×0.5, ×0.1, test-particle) until Δ clears; location to the nearest
  feasible SMA (interior/exterior of the gap, or into the HZ); snap to the nearest protecting MMR.
  `spec_patch` is the exact spec mutation the GUI's clickable-apply (D6) re-runs.

---

## 5. GUI — `SystemGeneratorPanel` gains a constraint builder (in place)

Extends the **R1 panel** — no new panel, no new nav entry; all additive (zero constraints →
unchanged R1 behaviour).

- A **"Desired features (constraints)"** group above Generate: a list of constraint rows, each a
  `[type ▾]` dropdown + dependent fields (the **structured builder** — emits the §3 spec JSON; no
  free text), `[+ Add]` / per-row `✕`. The type and body-type dropdowns carry the full vocab
  (unbuilt types resolve to `not_evaluated`).
- The button becomes **"Generate / Check Feasibility"** — constraints present → the feasibility
  path. Synthetic stays synchronous; real-anchor stays `run_in_background`. An **N-body confirm
  (marginal)** checkbox sets `nbody=True`.
- Results: a **feasibility banner** (green all-feasible / amber any-marginal / red any-infeasible),
  then a **per-constraint card** showing the four layers — verdict chip, Layer-1 reason +
  metrics, Layer-2 mechanism, Layer-3 hypotheses (each with a `default-extrapolation` badge),
  Layer-4 alternatives as **clickable chips that apply the `spec_patch` and re-run** (D6, bounded
  depth). Below: the **existing** R1 Planet Table (Source-coloured) + Orbit Diagram / HZ Ring tabs
  render the satisfied system; the Orbit Diagram marks an infeasible requested body as a red dashed
  ghost (additive styling, no canvas change beyond an extra orbit entry). **Copy JSON** carries the
  full four-layer envelope. **Send to Dossier** stays present-but-disabled (D5).

---

## 6. `query.py` — `generate-system --constraint` (repeatable) + `--nbody`

Extends the **existing** `generate-system` subcommand (no new subcommand): a repeatable
`--constraint` flag whose value is a compact DSL the dispatcher parses into one spec constraint:

```bash
query.py generate-system --seed 4173 --anchor-star "47 Ursae Majoris" \
  --constraint 'planet_at_location:terrestrial,1.0,between:b:c' \
  --constraint 'trojan:terrestrial,giant_in_hz,L4' \
  --constraint 'moon:super_jovian_in_hz,1.0,terraformable' \
  --nbody
query.py generate-system --seed 88 --spectral-class K2V --planets 5   # 0 constraints → R1 path, byte-identical
```

DSL grammar (one per flag): `type:field,field[,…][:refA:refB]` — a small, documented parser in
`query.py` (a `_parse_constraint(s)` helper). Zero `--constraint` flags → the R1 generation path,
**byte-identical**. `--companion mass,sma,ecc` supplies the D3 hint; `--nbody` (store-true) enables
the marginal confirmer. **Self-validating** (Phase H contract): malformed DSL / out-of-range value
→ curated `{"error"}` exit 1; argparse exit 2 for missing/bad CLI args.

---

## 7. Tests (offline; mocked readers for real-anchor)

- **`tests/test_feasibility.py`**
  - **G1/G2 helpers** anchored to known cases: Solar-System adjacent Δ's ≫ 10; a packed pair < 2√3;
    Jupiter+Trojan Gascheau-stable; Neptune/Pluto 3:2 + a fabricated 2:1 detected.
  - **`evaluate_feasibility`** for the **core 4** rules — verdicts + all four layers present; the
    `planet_at_location` Δ-band boundaries (`feasible`/`marginal`/`infeasible`); `trojan` pass/fail
    across the Gascheau limit; `moon` Roche<a<½-Hill + terraformable temp check; `resonance` match.
  - **Determinism (headline):** same `(seed, anchor, constraints)` → deep-equal across two calls
    (synthetic; + mocked-reader real-anchor), including the alternatives list.
  - **Layer 4** alternatives deterministic + each `spec_patch` re-runs to the stated `result`.
  - **Graceful paths:** unknown type / unresolvable ref → `not_evaluated` (rest still evaluate);
    multi-star with a `companion` hint → S/P-type verdict; without → safe-cap + note.
  - **Validation:** malformed spec / out-of-range → `{"error"}`.
- **`tests/test_nbody.py`** — determinism (same ICs → identical summary, no RNG); a stable config
  survives `K` orbits; an overlapping/packed config flags `unstable`; bounded-horizon note present.
- **`tests/test_query_generate.py`** (additions) — `--constraint` DSL parse; the feasibility
  subprocess contract (happy-path JSON + the four-layer keys, seed determinism across processes,
  curated-error exit 1 for a malformed DSL, argparse exit 2); `--nbody` wiring; **0-constraint
  parity** (output identical to the R1 invocation).
- **`tests/test_generator_panel.py`** (additions) — a constraint row emits the right spec; the
  feasibility render builds the banner + per-constraint cards + alternative chips; a clickable
  alternative applies its `spec_patch` and re-runs; 0 constraints → the unchanged R1 render.

---

## 8. Numbered checkpoints (one at a time; full suite green at each; stop for review)

> Run headless: `QT_QPA_PLATFORM=offscreen python -m pytest -q -k "not live"`. **3 live-network
> failures are the expected baseline**, not regressions. Each checkpoint ends with a GUI test plan
> where relevant (nav path, tabs, exact values, error cases, what changed vs. didn't).

| CP | Deliverable | Gate |
|---|---|---|
| **R2-C1** | `core/feasibility.py` **G1** (mutual-Hill/Gladman–Chambers packing) + **G2** (MMR, Gascheau co-orbital/Trojan) as pure helpers + unit tests (anchored cases) | suite green; pure/offline |
| **R2-C2** | Constraint **spec validator + rule registry + `evaluate_feasibility`** (Layers 1–2) for the **core 4** vocab; `generate_system` delegation (0-constraint parity) + tests | suite green |
| **R2-C3** | **Layer-4 alternatives** (deterministic relaxation + `spec_patch`) + **Layer-3** origin (tagged); stretch vocab (`habitable_world`/`alt_solvent_world`/`architecture`) iff time + tests | suite green |
| **R2-C4** | `core/nbody.py` (opt-in marginal confirmer) + determinism/instability tests; wire into the `marginal` path under `nbody=True` | suite green |
| **R2-C5** | **Multi-star** S/P-type via `compute_binary_orbit_stability` + the spec `companion` hint (+ no-hint safe-cap note) + tests | suite green |
| **R2-C6** | `query.py generate-system --constraint` DSL (+ `--companion`, `--nbody`) + subprocess contract tests (incl. 0-constraint parity) | suite green |
| **R2-C7** | GUI **constraint builder + four-layer display + clickable-apply alternatives** in `SystemGeneratorPanel` + headless smoke | suite green; **manual GUI verify** |
| **R2-C8** | Docs (`CLAUDE.md` test inventory, `docs/integration.md` constraint surface, `docs/gui-architecture.md`, `future_phases.md` R2→done) + final full-suite green | suite green |

---

## 9. Success criteria (R2)

A worldbuilder can state a desired system in structured constraints and get a **reasoned,
deterministic** feasibility report — stable? · why? · how could it arise? · nearest feasible
alternative? — that **agrees with the analysis side** (a system the engine calls feasible holds up
when re-analysed by opts 8–10 / the HZ tools); marginal cases are honestly flagged (and optionally
N-body-screened); multi-star anchors get quantitative S/P-type verdicts when a companion is
specified; observed vs synthetic bodies stay distinguishable; Layer-3 is always confidence-tagged
and never asserts an un-sourced fact; **no existing behaviour changes** (zero constraints = the R1
path, byte-identical); suite green (offscreen, 3 live-net baseline). R3 (research-priors hook) then
upgrades Layer-3 without reworking the engine.
