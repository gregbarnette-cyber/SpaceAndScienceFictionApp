# PHASE R2 — Constraint / Feasibility Engine · Analysis + Mockup

> **This is the analysis + mockup gate for R2 — design only, NO code.** Companion to
> [`PHASE_R2_MOCKUP.html`](PHASE_R2_MOCKUP.html) (panel layout). The numbered, build-ready
> `PHASE_R2_PLAN.md` is the **next** gate and is written only after this mockup is signed
> off (house rule: no code until the plan is approved).
>
> **Builds on R1 (shipped 2026-06-22).** R1 delivered the deterministic generator
> (`core/generate.py` + `core/priors.py` `DefaultPriors`), both modes, `query.py
> generate-system`, and `SystemGeneratorPanel`. R2 adds the **constraint-driven
> feasibility analyzer** on top — it does **not** rework R1. See `PHASE_R_MOCKUP.md`
> (the original R analysis, §1c gap table + §2 spec + §3 four-layer sketch) and
> `PHASE_R_PLAN.md` (R1). The phasing split (R1/R2/R3) was locked in `PHASE_R_MOCKUP.md`
> §6; R3 (research-priors hook) stays deferred.

---

## 0. What R2 is (one paragraph)

R1 answers *"generate a plausible system."* **R2 answers a harder question: "is THIS system
I want actually possible — and if not, what's the nearest thing that is?"** You describe
desired features as **structured constraints** ("an Earth-mass world between the two giants",
"a habitable Trojan at the gas giant's L4", "a terraformable moon of a super-Jovian in the
HZ"), and the engine returns a **four-layer verdict per constraint** — *is it stable* (physics),
*why* (mechanism), *how it could arise* (origin, confidence-tagged), and *if infeasible, the
nearest feasible parameters* (alternatives) — plus, when feasible, a generated system that
satisfies them. Pure deterministic physics; **no LLM in the app, no research gate** (only the
origin layer leans on priors, and it degrades gracefully on `DefaultPriors`).

---

## 1. Scope — in R2 vs. deferred

| In R2 | Deferred |
|---|---|
| Constraint spec (validated JSON) — vocab **v1** (§3) | New constraint types beyond v1 (additive later; unknown → `not_evaluated`, never an error) |
| `evaluate_feasibility(spec)` — the 4-layer evaluator + rule registry (§4) | — |
| **G1** multi-body packing stability (mutual Hill / Gladman–Chambers Δ) | — |
| **G2** resonance + co-orbital/Trojan diagnostics (MMR, Gascheau, L4/L5) | — |
| **Full S/P-type** multi-star feasibility (reuse `compute_binary_orbit_stability`) | Companion-mass/separation *reader* (the app has none — supplied via spec or skipped with a note; an automated binary-orbit reader is a later data-source phase) |
| Optional **pure-numpy N-body** confirmation for marginal analytic cases (`core/nbody.py`) | scipy / REBOUND / long-term Gyr integrations; chaos indicators (MEGNO) |
| **Alternatives** engine (deterministic boundary-relaxation) | ML / optimisation search — the relaxation is a fixed ordered scan |
| **Layer-3** origin hypotheses, **confidence-tagged**, on `DefaultPriors` | Research-calibrated origin probabilities + strict policy → **R3** (the priors hook is already the seam) |
| GUI **constraint builder** + 4-layer verdict display in `SystemGeneratorPanel` | — |
| `query.py generate-system --constraint …` (repeatable) | NL→spec (stays consumer-side; the app only ever sees structured JSON) |

**Hard rule carried from R1:** determinism is the headline contract — same `seed` (+ same
`anchor_star` + same constraint spec) → byte-identical output. Every randomness source is the
single seeded `random.Random`; the N-body integrator is fixed-step with fixed ICs; the
alternatives scan is an ordered grid. No `Date.now`, no unseeded RNG, no set/dict-ordering
dependence in emitted lists.

---

## 2. Reuse / gap inventory (verified in `core/` 2026-06-22)

**Reused verbatim (no change):** `core/generate.py` `generate_system` (the base-system builder
for both modes — R2 calls it, then layers constraints on its output); `_classify_planet` /
`_equilibrium_temp` (G3/G4, shipped R1); `compute_hill_sphere` (single-planet Hill radius +
½-Hill stable-orbit limit — the moon-constraint basis); `compute_binary_orbit_stability`
(Holman & Wiegert 1999 S-type/P-type critical SMA — the multi-star basis); `compute_solvent_zone`
(alt-biochem liquid bands — the "ammonia-ocean world" constraint); `compute_habitable_zone` /
`compute_ice_lines` (HZ + snow line); the `_G / _SOLAR_MASS_KG / _EARTH_MASS_KG / _M_PER_AU /
_SEC_PER_YEAR` constants.

**Confirmed gaps (grep over `core/*.py` → zero hits for `resonance|mutual hill|gascheau|trojan|
lagrang|AMD|nbody|packing|chambers|gladman`) — all new, all Tier-A textbook physics, no research gate:**

| New | Module | Formula basis (citation) | Why existing code can't do it |
|---|---|---|---|
| **G1 · packing stability** | `core/feasibility.py` | Mutual Hill radius `R_H,m = ((m₁+m₂)/(3M★))^⅓·(a₁+a₂)/2`; separation `Δ = (a₂−a₁)/R_H,m`; **Δ_crit = 2√3 ≈ 3.46** (Gladman 1993, Hill stability of a pair) / **Δ ≳ 9–12** (Chambers 1996, long-term N-planet) | `compute_hill_sphere` is **single-planet** — can't ask "does a body fit between b and c" |
| **G2 · resonance / co-orbital** | `core/feasibility.py` | Period ratio → nearest low-order MMR (p:q, p+q ≤ ~5) with a libration-width tolerance; **Gascheau/Routh** co-orbital mass criterion `(m₁+m₂)/M★ ≲ 0.0385`; L4/L5 Trojan stability | none exist (`compute_hyper_limit…` is unrelated Honorverse) |
| **G5 · spec + registry + evaluator + alternatives** | `core/feasibility.py` | — | the whole new feature (§4) |
| **N-body confirm (optional)** | `core/nbody.py` | Fixed-step **leapfrog (kick-drift-kick)** symplectic integrator, bounded orbit count, close-encounter + SMA-drift instability flags | analytic criteria are gray near the boundary; a short deterministic integration disambiguates marginal cases |

> **Finding (unchanged from the R analysis):** the engine + the new physics depend **only**
> on textbook celestial mechanics, buildable now. **Only Layer-3 (origin narrative)** leans on
> formation priors, and it rides the R1 `DefaultPriors` seam — so R2 ships fully without the
> sister-project research; R3 later swaps in `ResearchPriors`.

---

## 3. The constraint spec (the contract both front-ends emit) — vocab v1

A structured, validated JSON object. The GUI builder and the `query.py` consumer both produce
it; `core/` only ever sees this (no NL parsing in the app).

```jsonc
{
  "mode": "synthetic" | "real_anchor",
  "seed": 4173,                          // required; deterministic
  "anchor_star": "47 Ursae Majoris",     // real_anchor only
  "spectral_class": "G1V",               // synthetic only (optional → sampled)
  "n_planets": 6,                        // optional (synthetic count / infill count)
  "require_habitable": false,
  "research_policy": "permissive",       // "permissive" (default) | "strict" (R3)
  "companion": null,                     // optional multi-star hint: {mass_solar, sma_au, ecc}
  "constraints": [
    { "id": "c1", "type": "planet_at_location",
      "planet_type": "terrestrial", "mass_earth": 1.0,
      "location": { "kind": "between", "ref_a": "b", "ref_b": "c" } },
    { "id": "c2", "type": "trojan",
      "companion_type": "terrestrial", "host": "giant_in_hz", "point": "L4" },
    { "id": "c3", "type": "moon",
      "host": "super_jovian_in_hz", "mass_earth": 1.0, "terraformable": true },
    { "id": "c4", "type": "resonance", "bodies": ["c","d"], "ratio": "2:1" }
  ]
}
```

**Constraint vocab v1** (each maps to one rule in the registry §4):

| `type` | Fields | Asks |
|---|---|---|
| `planet_at_location` | `planet_type` (terrestrial/ice/gas/super_jovian), `mass_earth`, `location` | "place a body of this mass/type here — does it survive?" |
| `trojan` | `companion_type`, `host`, `point` (L4/L5) | "a co-orbital companion at the host's L4/L5 — stable?" |
| `moon` | `host`, `mass_earth`, `terraformable?` | "a moon of this giant — does it sit between Roche and ½-Hill, and (if asked) is it temperate?" |
| `resonance` | `bodies` (two refs), `ratio` (p:q) | "are/can these two be in this MMR — and does it protect them?" |
| `habitable_world` | `min_count` (default 1), `hz` (cons/opt) | "≥ N rocky worlds in the (conservative) HZ" |
| `alt_solvent_world` | `solvent` (ammonia/methane/…), `mass_earth?` | "a world in this solvent's liquid band" (reuses `compute_solvent_zone`) |
| `architecture` | `rule` (e.g. `giant_beyond_snow_line`, `no_hot_jupiter`) | coarse system-shape constraints |

**`location.kind`:** `at` (`au`), `between` (`ref_a`,`ref_b`), `interior_to` / `exterior_to`
(`ref`), `in_hz` (`cons`/`opt`), `in_zone` (`hot`/`hz`/`cold`/`far`). Refs are planet letters
(`"b"`), observed planet names, or symbolic anchors (`giant_in_hz`, `super_jovian_in_hz`,
`outermost`). An unresolvable ref → that constraint `verdict:"not_evaluated"` + a note (never a
hard error). **Unknown `type` → `not_evaluated`** (the vocabulary is open-ended by design).

---

## 4. The engine — `core/feasibility.py`

### 4a. Architecture (rule registry + evaluator)

```
evaluate_feasibility(spec) -> dict
  1. validate_spec(spec)                      # structured; bad shape → {"error"} (self-validating)
  2. base = generate_system(seed, anchor_star, spectral_class, n_planets, …)
       → reuse R1 verbatim; observed planets are FIXED reference points
  3. for each constraint c in spec["constraints"]:
       rule = REGISTRY.get(c["type"])         # unknown → verdict "not_evaluated"
       result_c = rule.evaluate(c, base, star)  # → {verdict, layer1..4}
  4. feasible = all evaluated constraints are "feasible" (not_evaluated/marginal don't fail*)
  5. emit the satisfied system (base + placed bodies) when feasible
  → {seed, mode, anchor_star, star, planets[], constraints[<4-layer results>],
     feasible, warnings[], notes[]}
```
\* **marginal** (analytic gray-band, N-body not run or inconclusive) is surfaced distinctly so
the caller decides; it does not silently pass as feasible.

Each **rule** is a small object/callable with `validate(c)` and `evaluate(c, system, star) ->
{verdict, layer1, layer2, layer3, layer4}`. The registry is a plain dict keyed by `type` — the
seam for adding constraint types without touching the evaluator.

### 4b. Four-layer output (per constraint)

| Layer | Question | Source | Research? |
|---|---|---|---|
| 1 · **verdict** | dynamically stable / physically possible? | G1/G2 + `compute_hill_sphere`/`_binary_orbit_stability`/`_solvent_zone` | No |
| 2 · **mechanism** | *why* stable? (MMR / Trojan / Hill packing / secular / none) | G2 diagnostics | No |
| 3 · **origin** | *how* could it arise? (in-situ / migrated / scattered / captured) — ranked, **confidence-tagged** | priors hook (`DefaultPriors`) | **Yes → degrades** |
| 4 · **alternatives** | if infeasible, nearest feasible parameters | deterministic relaxation scan | No |

`verdict ∈ {feasible, marginal, infeasible, not_evaluated}`.

### 4c. Layer-1 physics, per rule

- **`planet_at_location`** → resolve the location to a target SMA; compute **G1 Δ** to each
  bracketing body (observed or generated); feasible if Δ ≥ Δ_long (~9–12), **marginal** if
  2√3 ≤ Δ < Δ_long (→ optional N-body), infeasible if Δ < 2√3 (unless a protecting resonance
  from G2 applies → mechanism in Layer 2).
- **`trojan`** → Gascheau mass criterion on (host + companion)/M★; L4/L5 linear stability;
  feasible only if both pass.
- **`moon`** → `compute_roche_limit` (inner) < requested SMA < `compute_hill_sphere`
  `stable_orbit_limit` (outer); `terraformable` adds a `_equilibrium_temp`/atmosphere check.
- **`resonance`** → period-ratio match to the requested p:q within a libration tolerance; the
  MMR is then a *protecting mechanism* the packing check (G1) may invoke.
- **`alt_solvent_world`** → `compute_solvent_zone(solvent)` band membership.
- **multi-star (`companion` set or real-anchor multiple)** → `compute_binary_orbit_stability`:
  S-type bodies must sit inside the critical SMA, P-type (circumbinary) outside it.

### 4d. Layer-4 alternatives (deterministic relaxation)

When a constraint is infeasible, scan a **fixed, ordered** set of single-parameter relaxations
and report those that flip it to feasible (first-feasible-per-axis, capped list):
- **mass** down a fixed ladder (e.g. ×0.5, ×0.1, test-particle) until Δ clears;
- **location** to the nearest feasible SMA (interior/exterior of the gap; into the HZ);
- **resonance**: snap to the nearest low-order MMR that protects the orbit.
Each alternative is `{change, result}` — deterministic, so it is unit-testable.

### 4e. Layer-3 origin (tagged; R3 upgrades)

Ranked `{pathway, plausibility (low/med/high), grounding}` hypotheses from simple
`DefaultPriors`-backed heuristics (giant beyond snow line → *in-situ* plausible; terrestrial in
a tight MMR → *migration/capture*; close-in giant → *scattered/migrated*). **Every hypothesis is
tagged `grounding="default-extrapolation"`** and a `notes[]` line says so. R3's `ResearchPriors`
swaps the heuristic for research-calibrated probabilities **without an engine change** (the hook
is already in `core/priors.py`).

---

## 5. Optional N-body confirmation — `core/nbody.py`

A **pure-numpy**, **deterministic** confirmer for **marginal analytic verdicts only** (never the
default path, never for clearly-feasible/infeasible cases — cost control + determinism):
- Fixed-step **kick-drift-kick leapfrog** (symplectic), star + planets as point masses,
  coplanar; fixed timestep = (innermost period)/N_steps; bounded total = K orbits of the
  innermost (K, N_steps fixed constants → reproducible).
- **Instability flags:** any pairwise approach within a mutual Hill radius, or any planet's SMA
  drifting beyond a fixed fractional band → `unstable`; otherwise `survived K orbits`.
- Result feeds Layer 1/2: a marginal case that survives → `feasible (N-body confirmed, K orbits)`;
  that goes unstable → `infeasible (N-body)`. The bounded horizon is stated in the note (it is a
  short-integration screen, **not** a Gyr stability proof — that honesty is in the output).
- **No scipy.** Determinism: fixed dt/steps/ICs, no RNG.

---

## 6. GUI — `SystemGeneratorPanel` gains a constraint builder

R2 **extends the R1 panel in place** (no new panel, no new nav entry). Additive:
- A **"Desired features (constraints)"** group above Generate: a list of constraint rows, each
  a `[type ▾]` dropdown + dependent fields (the structured builder — it emits the §3 spec JSON;
  no free text). `[+ Add]` / per-row `✕`.
- The button becomes **"Generate / Check Feasibility"** (constraints present → feasibility path).
  Synthetic stays synchronous; real-anchor stays `run_in_background`.
- Results: a top **feasibility banner** (green *all feasible* / amber *marginal* / red
  *infeasible*), then a **per-constraint card** showing the four layers — verdict chip, Layer-1
  reason, Layer-2 mechanism, Layer-3 hypotheses (each with a `default-extrapolation` badge),
  Layer-4 alternatives (each a clickable chip that **applies the change** and re-runs). Below
  that, the **existing** R1 Planet Table (Source-coloured) + Orbit Diagram / HZ Ring tabs render
  the satisfied system. **Copy JSON** carries the full 4-layer envelope.
- See `PHASE_R2_MOCKUP.html` for the layout.

---

## 7. `query.py` — `generate-system --constraint` (repeatable)

Extends the **existing** `generate-system` subcommand (no new subcommand): a repeatable
`--constraint` flag whose value is a compact DSL the dispatcher parses into one spec constraint
(e.g. `planet_at_location:terrestrial,1.0,between:b:c` · `trojan:terrestrial,giant_in_hz,L4` ·
`moon:super_jovian_in_hz,1.0,terraformable` · `resonance:c,d,2:1`). Zero `--constraint` flags →
the R1 generation path, byte-identical (additive). With constraints → `evaluate_feasibility`.
Self-validating (Phase H contract): a malformed constraint DSL or out-of-range value →
curated `{"error"}` exit 1; argparse exit 2 for missing/bad args. The `--nbody` flag (opt-in)
enables the marginal-case confirmer.

---

## 8. Determinism & validation contract

- **Determinism:** same `(seed, anchor_star, spec)` → byte-identical JSON, **including** the
  alternatives list and any N-body verdict (fixed dt/steps/ICs). Verified by a deep-equal test
  (the R1 headline test pattern, extended to the feasibility path).
- **Validation (self-validating — Phase H, *not* the Phase-N raw-exception path):** bad spec
  shape / out-of-range numeric / unresolvable anchor → curated `{"error"}` exit 1. An
  unresolvable *ref* or unknown constraint *type* is **not** an error — that constraint is
  `not_evaluated` with a note, and the rest still evaluate. argparse exit 2 for missing/bad CLI
  args.

---

## 9. Decisions to resolve before `PHASE_R2_PLAN.md`

| # | Question | Proposed default |
|---|---|---|
| D1 | **Constraint vocab v1 scope** — ship all 7 types in §3, or a smaller core (e.g. `planet_at_location`, `trojan`, `moon`, `resonance`) first? | **Smaller core (4)** first; `habitable_world`/`alt_solvent_world`/`architecture` are thin follow-ons within R2 if time allows. |
| D2 | **N-body in R2 or defer to R2.5?** It's the most code for the least surface. | **In R2 but opt-in** (`--nbody` / a GUI checkbox), marginal-cases-only; analytic verdicts ship regardless. |
| D3 | **Multi-star companion source** — the app has no binary-orbit reader. | Accept an **optional `companion` hint** in the spec (mass/sma/ecc); real-anchor multiples without a hint → the R1 detect+warn+safe-cap, with a note that quantitative S/P-type needs the hint. (Auto-reader = a later data phase.) |
| D4 | **Δ_long threshold** (long-term packing) — 9, 10, or 12 mutual Hill radii? | **10** (Chambers 1996 mid-range); expose the gray band [2√3, 10] as `marginal`. |
| D5 | **"Send to Dossier"** — still deferred from R1; does the 4-layer feasibility report want a Q hook now? | **Still deferred** (R1 decision stands); Copy JSON covers it. |
| D6 | **GUI alternatives "apply"** — clickable chips that mutate the spec and re-run, or display-only? | **Clickable apply** (the payoff of the feature) — but cap re-run depth and keep each re-run deterministic. |

---

## 10. Proposed checkpoint preview (the numbered plan is the next gate)

Not build-ready yet — this is the shape `PHASE_R2_PLAN.md` will formalise (one checkpoint at a
time, full suite green at each, manual GUI verify at the panel checkpoint, 3 live-net baseline):

| CP | Deliverable |
|---|---|
| R2-C1 | **G1** packing (mutual Hill / Gladman–Chambers Δ) + **G2** resonance/co-orbital/Trojan, as pure helpers + unit tests (anchored to known cases: Solar System Δ's, Jupiter Trojans, 2:1 pairs). |
| R2-C2 | Constraint **spec validator + rule registry + `evaluate_feasibility`** (Layers 1–2) for the D1 core vocab + tests. |
| R2-C3 | **Layer-4 alternatives** (deterministic relaxation) + **Layer-3** origin (tagged) + tests. |
| R2-C4 | **`core/nbody.py`** (opt-in marginal confirmer) + determinism/instability tests. |
| R2-C5 | **Multi-star** S/P-type via `compute_binary_orbit_stability` (+ `companion` hint) + tests. |
| R2-C6 | `query.py generate-system --constraint` (+ `--nbody`) DSL + subprocess contract tests. |
| R2-C7 | GUI **constraint builder + 4-layer display** in `SystemGeneratorPanel` + headless smoke; **manual GUI verify**. |
| R2-C8 | Docs (`CLAUDE.md` test inventory, `docs/integration.md` constraint surface, `docs/gui-architecture.md`, `future_phases.md` R2→done) + final full-suite green. |

---

## 11. Success criteria (R2)

A worldbuilder can state a desired system in structured constraints and get a **reasoned,
deterministic** feasibility report — stable? why? how could it arise? what's the nearest feasible
alternative? — that **agrees with the analysis side** (a system the engine calls feasible, when
re-analysed by opts 8–10 / the route/HZ tools, holds up); marginal cases are honestly flagged
(and optionally N-body-screened); multi-star anchors get quantitative S/P-type verdicts when a
companion is specified; observed vs synthetic bodies stay distinguishable; Layer-3 is always
confidence-tagged and never asserts an un-sourced fact; **no existing behaviour changes** (zero
constraints = the R1 path, byte-identical); suite green (offscreen, 3 live-net baseline). R3
(research-priors hook) then upgrades Layer-3 without reworking the engine.
