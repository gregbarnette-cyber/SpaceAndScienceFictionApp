# System Dossier — Extension Investigation

**Status:** Investigation / notes only — **not** a committed plan, nothing built.
**Date:** 2026-08-11
**Scope:** What new sections could be added to the `dossier` subcommand
(`core/report.build_system_dossier`) / Phase Q, including but not limited to OEC.

This file captures the survey so a future session can pick it up without re-deriving it.
It is exploratory; the mockup-gated + `docs/integration.md`-contract conventions still apply
before any of this is built.

---

## 1. What the dossier composes today

The dossier is **pure composition over existing readers — no new astronomy**. It stitches
together the same `core/` functions that back existing `query.py` subcommands.

### Real-star path (`core/report.py::_assemble_star`)

| Core function called | query.py subcommand | Role in the dossier |
|---|---|---|
| `databases.compute_simbad_lookup(star)` | `simbad-lookup` | The gate (hard `{"error"}` if it fails) → `identity`. Also *carries* the **GCNS** (`_simbad_gcns_block`) and **Gould** (`_simbad_gould_block`) data — no separate call for those. |
| `regions.compute_star_system_regions_from_simbad(simbad)` | `star-regions` | `regions` section + feeds `habitable_zone`. |
| `databases.compute_planetary_systems_composite(simbad)` | `planetary-systems` | NASA pscomppars planets (priority 1). |
| `databases.compute_hwc(simbad)` | `hwc` | Habitable Worlds Catalog planets (priority 2). |
| `databases.compute_hypatia_data(simbad)` | `hypatia` | `hypatia` abundances section. |
| *(GCNS block)* | *(part of `simbad-lookup`)* | `gcns` section — read from `simbad.get("gcns")`, not a call. |

### Sol / Sun path (`core/report.py::_assemble_sol`, fully offline)

| Core function called | query.py subcommand | Role |
|---|---|---|
| `regions.compute_sol_regions()` | `sol-regions` | `regions` + `habitable_zone`. |
| `science.compute_solar_system_tables()` | `solar-system` | `planets` (planets/dwarf planets/asteroids) + `moons`. |
| `databases._sun_hypatia_baseline()` | *(none — internal)* | Solar [X/H]≡0 zero-point for `hypatia`. |
| *(GCNS)* | — | Not applicable → a `notes[]` entry. |

### Shared rendering helpers (both paths)

- **`equations.compute_habitable_zone(teff, L)`** → subcommand `habitable-zone` — called 3× in
  `_hz_data`, one per luminosity column (bolometric / from-mass / calculated).
- **`equations.implied_edge_temp(inner, L, "surface")`** → *no subcommand* (the P7a helper) —
  annotates the alternate-solvent band edge temps.
- **`core.viz._ss_diameter_km`** → *internal* (imported function-locally) — the "N/A"-diameter
  rule for the Sol asteroid cap.
- **`core.hypatia_elements.CATEGORIES` / `display_symbol`** → *constants* — group abundances by
  nucleosynthetic family.

### Sibling composers (same module, **not** the plain `dossier` subcommand)

- **`build_generated_dossier`** renders a `core.generate.generate_system` result (query.py
  `generate-system`) — pure composition, no SIMBAD.
- **`build_project_dossier`** calls `core.projects.get_project` (query.py `project-get`), then
  fans out to `build_system_dossier` (real) / `build_generated_dossier` + `generate_from_spec`
  (generated). **GUI-only / tested but not exposed** — there is *no* `project-dossier` subcommand
  (see `docs/integration.md` ~line 3370).

---

## 2. How the dossier is extended (framework mechanics)

Each new section is small and self-contained. Touch points in `core/report.py`:

1. Add the key to `_SECTION_ORDER` (line ~32), and to `_ALL_SECTIONS` (line ~33) **only if it
   should be in the default set** (opt-in sections stay out, like `moons`).
2. Add a title to `_SECTION_TITLES` (line ~35).
3. Write a **data builder** `_<section>_data(...)` (the JSON `data` payload).
4. Write a **block builder** `_blocks_<section>(d)` returning `(title, [blocks])`, and register
   it in `_SECTION_BLOCKS` (line ~516). Blocks use the shared model
   `("em"|"h3"|"strong"|"p", text) | ("kv", rows) | ("table", headers, rows)` so md/html/json all
   work for free.
5. Wire the source + `status[key] = ("ok"|"warn"|"note", reason)` into `_assemble_star`
   (line ~640) and/or `_assemble_sol` (line ~694).

**Key property that makes this low-risk:** the validation model already handles a missing source
gracefully. A section whose source fails/returns nothing degrades to a `warnings[]` entry and the
dossier still renders the rest (exit 0). By-design omissions (e.g. GCNS-N/A on Sol) are `notes[]`.
So adding a section can never break existing dossiers — worst case it self-omits.

Also update `docs/integration.md` (the `dossier` contract, ~lines 2411–2418) and add a subtest
mirroring `test_source_failure_isolation` (missing source → warning, rest renders).

---

## 3. Candidate sections (ranked by value ÷ cost)

All are single-system readers the app **already has** but the dossier never calls.

| Proposed section | Source (already in the app) | What it adds | Cost | Network | Sol behavior |
|---|---|---|---|---|---|
| **`kinematics`** | `compute_hypatia_data` → `properties` (U/V/W, disk) — **already fetched by the dossier** | Galactic velocity + thin/thick/halo population (stellar origin) | **~nil** (re-reads data already in hand) | none extra | note (no solar UVW) |
| **`evolution`** | `equations.compute_stellar_evolution(mass_solar, age)` — mass already computed in `regions` | Evolutionary stage, MS lifespan, current stage, "time left" | low (pure math) | none | **works** (M≈1) |
| **`oec`** | `databases.compute_oec(simbad, allow_simbad=False)` + `oec_derived.derive()` | System **topology/binarity**, **exomoons** (`<satellite>`), discovery provenance, **derived per-planet habitability** | medium | 1 cached ~1 MB download, then offline | note (Sol not in OEC) |
| **`hwo`** | `compute_hwo_exep(simbad)` | Precursor-target metrics: EEID, disk flag, Earth-twin contrast, orbital period at EEID | low | +1 TAP call | no |
| **`exocat`** | `compute_mission_exocat(simbad)` | EEID, **stellar age**, planet count | low | none (local CSV) | no |
| **`extinction`** | `dust.compute_dust_sightline(star=…)` | Line-of-sight A_V Sol→star (obscuration/visibility) | medium | reads local dust cube | A_V≈0 |
| **`companions`** | `compute_gcns_system(source_id)` (local) or Phase AM `binary-orbit` (networked) | Resolved-system members/pairs, or real companion orbital elements | low→high | none→Gaia NSS/SB9 | note |

---

## 4. Per-candidate integration notes (grounded)

### `kinematics` — nearly free
- The dossier **already** calls `compute_hypatia_data(simbad)`; `_hypatia_data` currently extracts
  only teff/logg/disk/fe_h/abundances. The `properties` dict already carries `u_vel`/`v_vel`/
  `w_vel`/`pm_ra`/`pm_dec`/`disk` (`core/databases.py` ~lines 1888–1892).
- A kinematics block is literally re-reading properties we already fetched. Population label
  (thin/thick/halo) can reuse the GUI Toomre logic (`core.viz.prepare_toomre`) or be a simple
  |V| / √(U²+W²) threshold.
- Sol: no Hypatia UVW (it's the zero-point) → `notes[]`.

### `evolution` — low, works for Sol
- `equations.compute_stellar_evolution(mass_solar, current_age_gyr=None)` (`core/equations.py`
  line 1049). Self-validating (0.1–20 M☉).
- Mass is already computed: `regions` returns `stellarMass`. Age is optional; if omitted you get
  stage durations + MS lifespan without a "current stage" marker. Age could come from `exocat`
  (`st_age`) or HWC (`S_AGE`) if either of those sections is also added.
- Sol works (M≈1 → T_ms=10 Gyr).

### `oec` — the flagship opt-in (see §5 for the full case)
- `databases.compute_oec(target, allow_simbad=True)` (`core/databases.py` line 860) **accepts a
  `compute_simbad_lookup` result dict directly** and, with `allow_simbad=False`, resolves
  direct-alias offline — the dossier already holds `simbad`, so no extra SIMBAD round-trip.
- Returns `{query, matched_name, system: <node>, [simbad]}` or `{"error"}`. The node is a recursive
  tree, **not** flat rows — needs its own block builders (the `_blocks_planets` shape won't fit).
- Derived layer: `oec_derived.derive(kind, node_values, host_values, system_values)` with
  `kind ∈ {"star","binary","planet"}` (`core/oec_derived.py` line 731, `_DISPATCH` line 721).
  Every entry is a value **or** `None`+reason — never raises, never a silent zero.

### `hwo` — low, +1 network call
- `compute_hwo_exep(simbad_result)` (`core/databases.py` line 529) takes the simbad shape already
  in hand; returns `{simbad, hwo: [rows]}` or `{"error"}`. TAP query against `di_stars_exep`.
- Relevant framing: this is a *precursor-science target list* → "is this a good observation
  target" metrics (EEID, disk, Earth-twin contrast).

### `exocat` — low, offline (local CSV)
- `compute_mission_exocat(simbad_result)` (`core/databases.py` line 595); returns `{simbad, exocat:
  row}` or `{"error"}`. Its **age** field is the most useful bit — could feed `evolution`.

### `extinction` / dust — medium, gated
- `dust.compute_dust_sightline(star=…)` (`core/dust.py` line 346). **WSL/Linux-only**, needs the
  `dustmaps` extra (`requirements-dust.txt`) — must be opt-in and gate cleanly (a Windows checkout
  or a box without the extra must degrade to a `warnings[]`/`notes[]`, never crash).
- Worldbuilding value: how obscured / visible is this star along the Sol sightline.

### `companions` — low→high depending on source
- Cheap: expand the existing GCNS block via `compute_gcns_system(source_id)` (`core/databases.py`
  line 2999) — resolved-system members + pairs (local, offline).
- Heavy: Phase AM `binary.py` `binary-orbit` — real companion orbital elements + mass classifier,
  but networked (Gaia NSS / SB9). Probably overkill for a dossier's first companion pass.

---

## 5. OEC deep-dive (the section flagged by the user)

Add OEC **not because it's a third planet catalog** — the dossier already has NASA pscomppars +
HWC. Its unique value is what those two flatten away:

- **System structure.** OEC is a recursive `system→binary→star→planet→satellite` tree, so it
  carries binarity/hierarchy that pscomppars drops. The dossier currently represents multiplicity
  only as a one-line GCNS `system_id`.
- **Exomoons.** OEC captures `<satellite>` nodes — the *only* app source of exoplanet moons, and
  exactly what a worldbuilding consumer wants.
- **Derived habitability layer.** `oec_derived.derive()` computes HZ verdict, insolation S⊕,
  density, log g, Hill radius, S/P-type stability, RV K, transit depth per node — a richer
  per-planet block than either catalog gives raw, and it never disagrees with `query.py` (uses the
  same `core/` functions).
- **Clean offline integration.** `compute_oec(simbad, allow_simbad=False)` reuses the simbad dict
  already in hand. Already a `query.py` family (`oec-system/-planet/-search/-census/-status`).

**Cost:** OEC's node model is a tree, not flat rows, so it needs bespoke block builders. This is
the "medium" in the table. Because OEC lists only systems with planets/candidates, most stars will
return "not in OEC" → a clean `warnings[]` self-omission. Given repo convention, OEC probably wants
a short **mockup of its section layout** before building.

---

## 6. Design considerations

1. **Default set vs opt-in.** Follow the `moons` precedent: keep heavy/networked sections
   (`oec`, `extinction`, `companions`) **out of the default set** and opt-in via `--sections`, so
   the default dossier stays fast and roughly one page. `kinematics` and `evolution` are cheap
   enough to default-on.
2. **Sol offline guarantee.** `evolution` is the only new section that fully works for Sol; the
   rest become by-design `notes[]` (the framework already does this). **Do not** let any new
   *default* section introduce a network call on the Sol path.
3. **Network budget.** Current real-star dossier already runs SIMBAD + regions + NASA + HWC +
   Hypatia. `kinematics`/`evolution`/`exocat` add ~nothing; `hwo` adds a TAP call; `oec` adds one
   cached ~1 MB download then offline; `extinction`/`companions` (Phase AM) are the heaviest.
4. **Age plumbing.** `evolution` currently has no age input. If `exocat` (or HWC `S_AGE`) is added,
   thread its age into `compute_stellar_evolution(current_age_gyr=…)` to get a "current stage"
   marker instead of just stage durations.
5. **Contract + tests.** Every new section needs a bullet in `docs/integration.md`'s `dossier`
   section and a `test_source_failure_isolation`-style subtest.

---

## 7. Recommendation (if/when a plan is opened)

- **Tier 1 (cheap, high value, do first):** `kinematics` + `evolution`. Both nearly free (data
  already fetched / mass already computed), both add narrative-relevant facts for the worldbuilding
  consumer, both partly/fully work offline.
- **Tier 2 (flagship opt-in):** `oec` — system structure + exomoons + derived habitability.
  Mockup-gate its layout first.
- **Tier 3 (if the consumer asks):** `hwo` / `exocat` / `extinction` / `companions`. `exocat` is
  mainly interesting because its **age** field feeds `evolution`.

## 8. Open questions

- Does the `scifiWorldBuilding-Claude` consumer actually want any of these in the `dossier`
  envelope, or would it rather call the individual subcommands (`oec-system`, etc.) itself? (Route
  cross-repo ambiguities via `/home/greg/Claude/coordination-channel.md`.)
- Should `kinematics`/`evolution` be default-on, or opt-in to keep the default envelope stable for
  existing consumers? (Adding default sections changes the default `data`/`document` output — an
  observable contract change.)
