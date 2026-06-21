# PHASE R1 — Procedural System Generation (engine + panel) · Implementation Plan

> **Scope.** R1 is the **first of three sub-phases** (R1 engine → R2 constraint/feasibility
> engine → R3 research-priors hook; split locked in `PHASE_R_MOCKUP.md` §6). R1 delivers a
> **deterministic system generator** in two modes — **synthetic-from-seed** and **real-anchor**
> — that renders in the existing diagrams. **No constraint/feasibility layer, no N-body, no
> research hook** here (those are R2/R3). New astronomy is limited to two thin helpers (a planet
> classifier + a T_eq wrapper that reuses Phase P); everything else **reuses verified `core/`
> functions**.
>
> **Source files:** new `core/generate.py`, new `core/priors.py` (the R3 seam, R1 ships only
> `DefaultPriors`), new `gui/panels/generator.py` (one panel) + `gui/panels/__init__.py` +
> `gui/nav.py` (one new **"Generator"** nav category), `query.py` (one `generate-system`
> subcommand), `docs/` updates, new `tests/test_generate.py`.
>
> **Companion mockups (approved):** `PHASE_R_MOCKUP.md` (design + analysis) and
> `PHASE_R_MOCKUP.html` (panel layout). **No code until this plan is signed off** (house rule).

---

## 0. Decisions carried in (from mockup review 2026-06-21)

| # | Decision |
|---|---|
| Phasing | **Split R1/R2/R3.** This plan is **R1 only.** |
| Synthetic realism | **`DefaultPriors`** — literature-informed constants; every synthetic field tagged `grounding="default-extrapolation"`. |
| Stability fidelity | analytic + optional N-body — **R2** (not R1). |
| Layer-3 origin narrative | **R2** (not R1). |
| Multi-star anchors | **Detect + warn + safe-cap** — R1 stays single-star; a detected multiple gets a warning and a conservative synthetic-placement cap so R1 never emits dynamically-impossible bodies. Full S/P-type modelling → R2. |
| Q "Send to Dossier" | **Deferred** — Phase Q's `build_system_dossier` takes a *star name* and re-assembles from readers; it can't yet ingest a *generated* system dict (so a synthetic system's bodies wouldn't appear). R1 ships **"Copy JSON"**; the Q handoff is a small later Q-extension (noted, not built here). |

---

## 1. Design summary (the one rule)

`core/generate.py` stays **pure** — no Qt, no file I/O. It is a **new consumer** of existing
result dicts plus a seeded `random.Random(seed)`. **Determinism is the headline contract:**
same `seed` (+ same `anchor_star`) → byte-identical output. No `Date.now`, no module-level or
unseeded RNG, no set/dict-ordering dependence in the emitted lists.

```python
generate_system(seed: int, anchor_star: str = None, spectral_class: str = None,
                n_planets: int = None, require_habitable: bool = False) -> dict
```

Returns (synthetic *and* real-anchor share this shape):

```jsonc
{
  "seed": 88, "mode": "synthetic" | "real_anchor", "anchor_star": null | "Tau Ceti",
  "star": {
    "name", "spectral_class",            // e.g. "K2V"
    "teff", "mass_solar", "radius_solar", "luminosity",
    "hz_inner_au", "hz_outer_au",        // conservative (rg→mg); optimistic also kept
    "hz_opt_inner_au", "hz_opt_outer_au", "snow_line_au",
    "source": "synthetic" | "observed",
    "grounding": "default-extrapolation" | "observed",
    "multiplicity": { "is_multiple": bool, "n_components": int|null, "note": str }  // real-anchor
  },
  "planets": [ {
    "name", "a_au", "mass_earth", "radius_earth", "ecc",
    "type": "rocky"|"super_earth"|"ice"|"gas"|"super_jovian"|"brown_dwarf",
    "t_eq_k", "in_hz": bool, "hz_class": "conservative"|"optimistic"|null,
    "source": "synthetic"|"observed", "atmosphere": str|null,
    "moons": [ { "name","a_planet_radii","mass_earth","between_roche_and_hill":bool,"source" } ]
  } ],
  "warnings": [str], "notes": [str]
}
```
`{"error": str}` for bad input (self-validating). Shapes deliberately echo the row keys the
analysis panels already render, so the result flows into `make_orbits_canvas` / `make_hz_canvas`
with zero new viz.

---

## 2. New helpers (the only new astronomy) — `core/priors.py` + `core/generate.py` internals

### 2a. `core/priors.py` — the R3 seam, R1 ships `DefaultPriors` only

A minimal provider so R2/R3 plug in without a later refactor. R1 contents:

- `DefaultPriors` — literature-informed constants, all tagged `grounding="default-extrapolation"`:
  - `spectral_class_weights` — sampling weights (M≫K>G>F>A…; deterministic via the seed).
  - `n_planet_dist` — planet-count weights (e.g. peak 2–6).
  - `spacing_ratio` — adjacent-SMA ratio band (Titius–Bode-ish ≈ 1.4–2.0, jittered).
  - `mass_by_zone` — mass draw bands for hot / HZ / cold / far zones.
  - `moon_count` / `moon_mass_frac` — per-giant moon priors.
- No `ResearchPriors`, no policy switch, no ingest (those are **R3**). A one-line module
  docstring marks the seam.

### 2b. `_classify_planet(mass_earth, a_au, snow_line_au) -> (type, radius_earth)`  *(G3)*

Pure function in `core/generate.py`. Type by mass with a snow-line modifier
(rocky/super_earth/ice/gas/super_jovian; > 13 M_J → `brown_dwarf`, flagged). Radius from mass:
rocky/super-Earth reuse the existing `equations._rocky_radius_km(mass_earth)` (→ R⊕); volatile/
giant use a simple published mass–radius relation. **No new constants table beyond a short
piecewise.**

### 2c. `_equilibrium_temp(a_au, luminosity, albedo=0.3) -> float`  *(G4)*

Thin wrapper over Phase P's existing `equations.implied_edge_temp(au, luminosity, model="equilibrium")`
(or `_t_ref_equilibrium`) — **reuse, not reinvent**. Used for `t_eq_k` and as a cross-check that
HZ planets land near ~255–320 K.

---

## 3. Synthetic mode flow (`anchor_star is None`)

1. **Star.** If `spectral_class` given → parse + validate (OBAFGKM + subtype); else sample via
   `DefaultPriors.spectral_class_weights`. Interpolate Teff/M/R between bracketing
   `compute_main_sequence_table()` rows (keys `"Teeff(K)"`, `"M"`, `"R"`). Luminosity via
   `compute_star_luminosity(radius, teff)`. HZ via `compute_habitable_zone(teff, luminosity)`
   (conservative = `rg`→`mg`; optimistic = `rv`→`em`). Snow line via
   `compute_ice_lines(luminosity)` (water line). `source="synthetic"`.
2. **Planets.** `n_planets` (given, validated to a sane range, e.g. 0–15) or sampled. SMAs
   log-spaced from an inner edge outward using `spacing_ratio` jitter. Per planet: draw mass by
   zone → `_classify_planet` → `_equilibrium_temp` → `in_hz` against the HZ bounds → small ecc.
3. **Moons (giants only).** Attach `moon_count` moons with SMA between `compute_roche_limit`
   (inner) and `compute_hill_sphere` `stable_orbit_limit` (outer); flag `between_roche_and_hill`.
4. **Atmosphere annotation (rocky worlds).** `compute_atmosphere_retention(mass, radius, t_eq)`
   → "retains N₂, O₂, …".
5. **`require_habitable`.** Re-roll the planet pass (bounded, e.g. ≤ 200 tries) until ≥ 1 rocky
   world lands in the **conservative** HZ; exhausted → `{"error": "…could not place a habitable…"}`.

All draws come from the single seeded RNG, in a fixed order.

---

## 4. Real-anchor mode flow (`anchor_star` given) — the one networked path

1. **Resolve.** `compute_simbad_lookup(anchor_star)` → `{"error"}` (unresolvable) returns verbatim.
2. **Real star specs.** `compute_star_system_regions_from_simbad(simbad)` → real
   `temp / stellarMass / stellarRadius / bcLuminosity / hzil / hzol / snowLine`. If it errors
   (non-OBAFGKM, e.g. a white-dwarf primary, or missing teff/vmag/plx) → return that error
   (can't extend a system without HZ/snow-line). `star.source="observed"`.
3. **Multiplicity detect + warn + safe-cap.**
   - Signal: `simbad["gcns"]` M5 block `n_components > 1` (primary), SIMBAD object-type backup.
   - If multiple → set `star.multiplicity`, append a **warning** ("known multiple; companion
     dynamical truncation not modelled in R1 — see R2"), and set a **conservative synthetic
     cap**: no synthetic body beyond `min(outermost observed SMA, k·hz_outer)` (heuristic, since
     the app has no reliable binary separation reader; GCNS-separation-based capping is an R2
     refinement). Observed planets are **never** capped.
4. **Observed planets.** `compute_planetary_systems_composite(simbad)` (**priority 1**) then
   `compute_hwc(simbad)` (**priority 2**); map `pl_orbsmax/pl_bmasse/pl_rade/pl_orbeccen` (and HWC
   equivalents) → planet dicts `source="observed"`; dedupe across the two sources by name/SMA.
   Neither resolves → a **warning** (no observed planets), generation still proceeds.
5. **Extend.** Sample synthetic planets into the empty zones, **de-conflicted** against observed
   SMAs (minimum adjacent-ratio separation) and the binary safe-cap. Moons/atmosphere as in §3.
   `require_habitable` is satisfied directly if an observed HZ rocky planet already exists.

---

## 5. GUI — `SystemGeneratorPanel` (`gui/panels/generator.py`)

`(DiagramToggleMixin, ResultPanel)`, new **"Generator"** nav category (one entry). Inputs per
the approved HTML mockup: seed + **Randomize** (fills a shown reproducible seed), Synthetic /
Anchor-on-real-star radio, anchor field, spectral-class chips (disabled while anchored), planet
spinner, require-habitable, a `DEFAULTS` priors pill. **Anchor mode runs on a background thread**
(network); synthetic is synchronous/instant.

Render: a **Planet Table** (Source column, observed rows tinted) + diagram tabs **Orbit Diagram**
(`make_orbits_canvas`, observed vs synthetic styled distinctly) and **HZ Ring** (`make_hz_canvas`)
via the mixin. A **Copy JSON** button. (**Send to Dossier deferred** — §0.) Multiplicity/other
warnings surface in a status line.

---

## 6. `query.py` — `generate-system`

```bash
query.py generate-system --seed 88 --spectral-class K2V --planets 5 --require-habitable   # offline
query.py generate-system --seed 4173 --anchor-star "Tau Ceti"                              # + network
```
Thin wrapper over `generate_system`. `--seed` required (int). Synthetic offline; `--anchor-star`
adds SIMBAD/NASA/HWC. Self-validating → curated `{"error"}` exit 1 (bad spectral class, n_planets
out of range, `require_habitable` exhausted, unresolvable anchor); argparse exit 2 for
missing/non-int args. Output: the `generate_system` dict, pretty-printed.

---

## 7. Tests — `tests/test_generate.py` (offline; mocked readers for real-anchor)

- **Determinism (headline):** same seed (synthetic) → deep-equal output across two calls; same
  seed + anchor (mocked readers) → deep-equal.
- **Synthetic:** star Teff/M/R/L consistent with the main-sequence interpolation + `compute_star_luminosity`;
  HZ flags consistent with `compute_habitable_zone`; `n_planets` honoured; classifier boundaries;
  moons sit strictly between `compute_roche_limit` and `compute_hill_sphere`; `t_eq_k` decreases
  with `a_au`; `require_habitable` delivers a conservative-HZ rocky world or errors after bounded retries.
- **Real-anchor (mock `compute_simbad_lookup` / `_regions_from_simbad` / `_planetary_systems_composite` / `compute_hwc`):**
  observed planets flagged `source:"observed"`; synthetic extensions `source:"synthetic"`; synthetic
  SMAs never collide with observed; **multiplicity** (mock `gcns.n_components=2`) → warning + no
  synthetic body beyond the safe-cap; regions-error anchor (mock white dwarf) → error.
- **Bad inputs** → `{"error"}` (bad `spectral_class`, out-of-range `n_planets`).
- **query.py subprocess contract** (throwaway `SPACE_APP_DB`): synthetic happy-path exit 0,
  error exit 1, argparse exit 2 (mirrors `test_query_phase_n.py`).
- **GUI smoke** (offscreen): construct `SystemGeneratorPanel`, run a synthetic generate, assert
  the table + viz tabs build (mirrors `test_reports_panel.py`).

---

## 8. Numbered checkpoints (one at a time; full suite green at each; stop for review)

> Run headless: `QT_QPA_PLATFORM=offscreen python -m pytest -q`. **3 live-network failures are
> the expected baseline**, not regressions. Each checkpoint ends with a GUI test plan where
> relevant (nav path, tabs, exact values to check, error cases, what changed vs. didn't).

| CP | Deliverable | Gate |
|---|---|---|
| **R1-C1** | `core/priors.py` (`DefaultPriors`) + `_classify_planet` (G3) + `_equilibrium_temp` (G4), with unit tests | suite green; pure/offline |
| **R1-C2** | `core/generate.py` **synthetic mode** (star + planets + moons + `require_habitable`) + determinism/synthetic tests | suite green |
| **R1-C3** | **real-anchor mode** (readers + observed merge + extend + multiplicity detect/warn/safe-cap) + mocked-reader tests | suite green |
| **R1-C4** | `query.py generate-system` + subprocess contract tests | suite green |
| **R1-C5** | `SystemGeneratorPanel` + nav category + render (table/orbit/HZ) + Copy JSON + headless smoke | suite green; **manual GUI verify** |
| **R1-C6** | Docs (`CLAUDE.md` test inventory, `docs/integration.md` `generate-system`, `docs/gui-architecture.md` panel row, `future_phases.md` R1→done) + final full-suite green | suite green |

---

## 9. Success criteria (R1)

Reproducible (seed-stable) plausible systems in both modes that render in the existing
diagrams; observed and synthetic bodies always distinguishable; physics consistent with the
analysis side (a generated system re-analysed by opts 8–10 / `habitable-zone` agrees with its
generation parameters); multi-star anchors are detected, warned, and never produce
dynamically-impossible bodies; no existing behaviour changes; suite green (offscreen, 3 live-net
baseline). R2 (constraint/feasibility engine + stability physics + N-body + Layer-3) and R3
(research-priors hook) build on this without reworking it.
