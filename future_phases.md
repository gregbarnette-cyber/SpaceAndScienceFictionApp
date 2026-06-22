# Context

The app is a mature Space & Science Fiction CLI/GUI tool that has completed Phases A–F plus the following post-F additions:
- **A–B**: Project skeleton + static/pure-math panels
- **C**: SIMBAD network features + QThread pattern
- **D**: Multi-source features (NASA archives, JPL Horizons, HWC, OEC, CSV utilities)
- **E**: Matplotlib visualizations embedded in panels (star maps, orbital diagrams, HZ rings, solar travel map)
- **F**: SQLite migration — all static tables auto-seeded from CSVs; star systems DB query; import/export utilities
- **Hypatia Catalog integration** (post-F): `compute_hypatia_data(simbad_result)` in `core/databases.py` fetches stellar properties, kinematics, and the full **104-species** Lodders 2009 elemental abundance set (including ionized species; defined in `core/hypatia_elements.py`) from `https://hypatiacatalog.com/hypatia/api/v2`. The 104 species are requested in chunks of 30 (the server caps the GET request line at ~4094 bytes). Integrated into opts 1, 3, 4, 5, 6, and 8 — results shown in **Hypatia** data tabs (abundances grouped by nucleosynthetic family) and **Abundance Profile** viz tabs (category-colored horizontal bar chart via `make_abundance_canvas()`). Also exposed as the `hypatia-data` subcommand in `query.py`.
- **NASA Planetary Systems Map** (post-F): `NasaPlanetarySystemsMapPanel` in `gui/panels/nasa_exoplanet.py` — GUI-only variant of opt 3 that adds a **Map Date** `QDateEdit` (defaults to today) and a **System Map** viz tab. The map is a top-down 2D ecliptic-view diagram showing the host star at the origin and each planet at its date-resolved heliocentric position, computed by solving Kepler's equation using `pl_orbtper` (JD epoch of periastron) or derived from `pl_tranmid`. Clicking a planet opens a non-modal info dialog populated from the already-fetched pscomppars row. Backed by `core.viz.prepare_exoplanet_system_diagram(planets, date_iso)` and `gui/visualizations/plot_helpers.py::make_exoplanet_system_canvas()`.

This document brainstorms future phases in order of likely value and implementation effort.


> **Status (updated 2026-06-20):** Phases **A–F** (skeleton → SQLite migration) plus **G, H, I (+ I-OPTS), K, L, M, N, O, P** are ✅ implemented; **Phase J** is ❌ declined. Their full brainstorm/spec text has been **moved to [`future_phases_archive.md`](future_phases_archive.md)** to keep this file lean — see the *Completed & Declined Phases* table below for per-phase pointers (archive section, `PHASE_*_PLAN.md`, `docs/`). This file now tracks only **forward-looking work**: the Phase **R / S** candidates (Phase **Q** — System Dossier Export — is ✅ implemented 2026-06-20; see `PHASE_Q_PLAN.md` / `PHASE_Q_MOCKUP.md` and `docs/gui-architecture.md`). **Phase R1** (Procedural System Generation — engine + panel) and **Phase R2** (Constraint / Feasibility Engine) are both ✅ implemented 2026-06-22 (R1 + R2 of R1/R2/R3 — see the Phase R section below); **R3 (research-priors hook) remains forward-looking.** `query.py` currently carries **63 subcommands** (R2 extended the existing `generate-system` subcommand rather than adding a new one).

> **Scope — GUI-only.** New feature work targets the PySide6 GUI only. The CLI (`main.py` / `MENU_OPTIONS`) is **frozen at opts 1–58** and is not extended by any phase below. Every new feature is a GUI nav entry backed by a panel class (precedent: `DbStatusPanel`, `NasaPlanetarySystemsMapPanel`, which carry no option number), so there are **no menu numbers to assign and nothing to renumber**. The shared `core/` functions each phase specifies are still built — the GUI and `query.py` consume them; only the CLI presentation layer is dropped. (The lone archive exception: Phase N was integration-surface-only — `query.py` subcommands over existing `core/` functions, no GUI/CLI change.)

---

## Completed & Declined Phases (archived)

Full brainstorm + as-built notes live in [`future_phases_archive.md`](future_phases_archive.md). Shipped behavior is documented in `docs/`; build-ready specs are the `PHASE_*_PLAN.md` files. **Phase G has no plan file — the archive is its canonical detailed record.**

| Phase | Name | Status | Detailed records |
|---|---|---|---|
| G | Interactive Data Search & Filtering | ✅ 2026-06-10 | [archive](future_phases_archive.md#phase-g--interactive-data-search--filtering--implemented-2026-06-10) · *(no plan file)* · `docs/star-databases.md` (Phase G), `docs/integration.md` |
| H | Worldbuilding Calculators | ✅ 2026-06-11 | [archive](future_phases_archive.md#phase-h--worldbuilding-calculators--implemented-2026-06-11) · [`PHASE_H_PLAN.md`](PHASE_H_PLAN.md) · `docs/equations.md`, `docs/integration.md` |
| I | Multi-System / Route Planning (+ I-OPTS) | ✅ 2026-06-12 / 06-13 | [archive](future_phases_archive.md#phase-i--multi-system--route-planning--implemented-2026-06-12) · [`PHASE_I_PLAN.md`](PHASE_I_PLAN.md), [`PHASE_I_OPTS_PLAN.md`](PHASE_I_OPTS_PLAN.md) · `docs/calculators.md`, `docs/integration.md` |
| J | User Preferences & Settings | ❌ Declined 2026-06-14 | [archive](future_phases_archive.md#phase-j--user-preferences--settings--declined-2026-06-14) · *(declined — provenance only)* |
| K | Honorverse Expansion | ✅ 2026-06-13 | [archive](future_phases_archive.md#phase-k--honorverse-expansion--implemented-2026-06-13) · [`PHASE_K_PLAN.md`](PHASE_K_PLAN.md) · `docs/science-and-scifi.md` |
| L | Exoplanet Comparison Dashboard (L1–L4) | ✅ 2026-06-13 / 06-14 | [archive](future_phases_archive.md#phase-l--exoplanet-comparison-dashboard) · [`PHASE_L_PLAN.md`](PHASE_L_PLAN.md) · `docs/equations.md`, `docs/star-databases.md`, `docs/integration.md` |
| M | GCNS Interactive Surfacing | ✅ 2026-06-11 | [archive](future_phases_archive.md#phase-m--gcns-interactive-surfacing--implemented-2026-06-11) · [`PHASE_M_PLAN.md`](PHASE_M_PLAN.md) · `docs/star-databases.md`, `docs/integration.md` |
| N | query.py Integration Expansion | ✅ 2026-06-12 | [archive](future_phases_archive.md#phase-n--querypy-integration-expansion--implemented-2026-06-12) · [`PHASE_N_PLAN.md`](PHASE_N_PLAN.md) · `docs/integration.md` |
| O | Visualization Expansion | ✅ 2026-06-18 | [archive](future_phases_archive.md#phase-o--visualization-expansion) · [`PHASE_O_PLAN.md`](PHASE_O_PLAN.md) · `docs/gui-architecture.md` |
| P | Snow Lines & Alternative-Solvent HZs | ✅ 2026-06-20 | [archive](future_phases_archive.md#phase-p--snow-lines--alternative-solvent-habitable-zones-grounded--extended) · [`PHASE_P_PLAN.md`](PHASE_P_PLAN.md) · `docs/equations.md`, `docs/star-system-regions.md`, `docs/integration.md` |
| Q | System Dossier Export & Reporting | ✅ 2026-06-20 | [archive](future_phases_archive.md#phase-q--system-dossier-export--reporting-implemented-2026-06-20) · [`PHASE_Q_PLAN.md`](PHASE_Q_PLAN.md), [`PHASE_Q_MOCKUP.md`](PHASE_Q_MOCKUP.md) · `docs/integration.md`, `docs/gui-architecture.md` |

---

# New phase candidates (beyond Q)

> Brainstormed 2026-06-13 as a coherent **worldbuilding workflow** — **export** shareable dossiers (Q, ✅ implemented 2026-06-20 — see the Completed table above + [archive](future_phases_archive.md#phase-q--system-dossier-export--reporting-implemented-2026-06-20)), **generate** plausible systems (R), **organize** them into named projects (S). The two remaining candidates (R, S) reuse existing `core/` functions, follow the GUI-only-plus-`query.py` model, and are independently valuable. Mockup-gated like every prior phase. Neither is spec'd to build-ready depth yet — these are the next brainstorm tier, at the J/K/L level of detail.

## Phase R — Procedural Star System Generation

> **Status: R1 + R2 ✅ implemented 2026-06-22** (split R1/R2/R3, locked in `PHASE_R_MOCKUP.md` §6). **R1** shipped the deterministic generator (`core/generate.py` + `core/priors.py`'s `DefaultPriors`), both modes (synthetic-from-seed + real-anchor), the `query.py generate-system` subcommand, and `SystemGeneratorPanel` (Generator nav category). **R2** added the **constraint/feasibility engine** (`core/feasibility.py` `evaluate_feasibility` — a structured constraint spec → a four-layer verdict per constraint via a rule registry; new G1 packing / G2 resonance-co-orbital physics + multi-star S/P-type via the `companion` hint), an opt-in pure-numpy N-body confirmer (`core/nbody.py`), the `generate-system --constraint/--companion/--nbody` surface (0 constraints = the R1 path), and the in-place `SystemGeneratorPanel` constraint builder + four-layer cards + clickable-apply alternatives — see [`PHASE_R_PLAN.md`](PHASE_R_PLAN.md), [`PHASE_R2_PLAN.md`](PHASE_R2_PLAN.md), `PHASE_R2_MOCKUP.md`/`.html`, `docs/integration.md` (Feasibility mode), `docs/gui-architecture.md`; tests `tests/test_generate.py` / `test_feasibility.py` / `test_nbody.py` / `test_query_generate.py` / `test_generator_panel.py`. **Deferred to R3:** the research-priors hook (`ResearchPriors` + policy switch — `DefaultPriors` is the seam; Layer-3 origin currently degrades to `default-extrapolation`). **Also deferred:** the "Send to Dossier" handoff (Copy JSON ships; the Q-ingest of a generated/feasibility system dict is a small later Q extension). The brainstorm below is the original pre-split text, retained for provenance.

**New panels (GUI-only)**: `SystemGeneratorPanel`
**Existing options touched**: none — R is a new consumer of the existing physics (`compute_main_sequence_table`, `compute_habitable_zone`, `compute_star_luminosity`, the Phase H `compute_hill_sphere` / `compute_roche_limit` / `compute_atmosphere_retention`) **and**, in real-anchor mode, the star-database readers (`compute_simbad_lookup`, `compute_star_system_regions_from_simbad`, `compute_planetary_systems_composite`, `compute_hwc`).

Generate **plausible star systems** for fiction — the inverse of the app's analysis tools. With **deterministic, reproducible output** (same inputs → same system). **Decision (2026-06-20): hybrid data model** — R works in two modes:

- **Synthetic mode** (no anchor): build the star from a seed + the main-sequence reference table, then sample planets/moons procedurally. Fully offline, no database lookups; the seed *is* the system's identity.
- **Real-anchor mode** (name a real star): **pull the star's true specs from the databases** — `compute_simbad_lookup` + `compute_star_system_regions_from_simbad` give real Teff/mass/luminosity/HZ/snow-line — and its **real known planets** from `compute_planetary_systems_composite` (NASA pscomppars) / `compute_hwc` (HWC). Then procedurally **extend** it: fill empty orbital zones with invented planets, attach moons, project unobserved bodies — all placed relative to the *real* HZ and snow line. The seed makes the *procedural additions* reproducible; the real bodies are flagged `source:"observed"` vs the generated `source:"synthetic"` so the two never blur.

**`core/generate.py`** (new module):
- `generate_system(seed: int, anchor_star: str = None, spectral_class: str = None, n_planets: int = None, require_habitable: bool = False) -> dict` — seeded `random.Random(seed)` (deterministic):
  1. **Star**: if `anchor_star` is given → resolve it via the database readers and use its real specs/HZ; else pick/accept a `spectral_class` → interpolate Teff/mass/radius/luminosity from `compute_main_sequence_table()` rows; derive the HZ via `compute_habitable_zone(teff, luminosity)`.
  2. **Planets**: in real-anchor mode, seed the planet list with the star's **observed** planets (NASA/HWC), then sample *additional* planets into the gaps; in synthetic mode, sample the whole list. Semi-major axes log-spaced (Titius–Bode-ish jitter) and de-conflicted against any observed orbits; classify each (rocky/ice/gas) by mass; compute periastron/apastron + equilibrium temperature; flag HZ membership against the star's HZ. `require_habitable=True` re-rolls until ≥ 1 rocky planet lands in the conservative HZ (bounded retries → `{"error"}` if it can't; in real-anchor mode an observed HZ planet satisfies it directly).
  3. **Moons / rings**: for giants, attach moons within `compute_hill_sphere` and outside `compute_roche_limit`; run `compute_atmosphere_retention` on rocky worlds to annotate "retains N₂/O₂/…".
- Returns `{"seed", "anchor_star", "star": {...}, "planets": [{..., "source": "observed"|"synthetic"}], "warnings": [...]}` — the **same row shapes the analysis panels already render**, so a generated system flows straight into the HZ/orbit/regions diagrams and a **Phase Q dossier** with zero new viz. (A natural pairing: anchor on a real star, extend it, then export the hybrid system as a Q dossier.)
- Self-validating: `n_planets` in a sane range, valid `spectral_class`; an unresolvable `anchor_star` → the SIMBAD error (real-anchor mode is the one networked path).

**GUI** — `SystemGeneratorPanel`: seed field (+ "Randomize" button that fills a shown, reproducible seed), an optional **"Anchor on real star"** field (blank → synthetic; filled → real-anchor, background since it hits the network), optional spectral-class chip (synthetic mode), planet-count spinner, "require habitable" checkbox → renders an orbit diagram + HZ ring (reusing `make_orbits_canvas` / `make_hz_canvas`, observed vs synthetic bodies styled distinctly) + a planet table. "Send to Dossier" hands the result to Phase Q.

**`query.py`** — `generate-system --seed N [--anchor-star "Tau Ceti"] [--spectral-class G2V] [--planets 6] [--require-habitable]`: deterministic JSON. Synthetic mode is offline; `--anchor-star` adds the SIMBAD/NASA/HWC lookups.

**Validation / tests / success**: deterministic (seed-stable) — the headline test is *same seed (+ same anchor) → identical output* (`tests/test_generate.py`, offline for synthetic mode + mocked readers for real-anchor, no `Date.now`/unseeded RNG). Also: HZ flags consistent with `compute_habitable_zone`; moons sit between Roche and Hill; synthetic planets never collide with observed orbits; `require_habitable` either delivers a HZ rocky world or errors after bounded retries; bad inputs → `{"error"}`. Success: reproducible plausible systems (synthetic or real-anchored) that render in the existing diagrams and export via Q; physics consistent with the analysis side (a generated system analyzed by opts 8–10 agrees with its generation parameters); observed and synthetic bodies always distinguishable.

## Phase S — Project Workspaces (Campaign / Novel Manager)

**New panels (GUI-only)**: `ProjectPanel`
**Existing options touched**: extends Phase J's `favorites` concept; reuses Q for export and R for "add a generated system".

Favorites (J2) is a flat global bookmark list. A worldbuilder works in **named projects** — a novel, a campaign, a setting — each a curated set of systems with freeform notes. Phase S adds a lightweight project workspace so generated (R) and looked-up systems can be **collected, annotated, and exported (Q) as a set**.

**`core/db.py`** — two additive tables (idempotent `_migrate_schema`):
```sql
CREATE TABLE IF NOT EXISTS projects (
    project_id INTEGER PRIMARY KEY, name TEXT UNIQUE, description TEXT, created_date TEXT);
CREATE TABLE IF NOT EXISTS project_members (
    project_id INTEGER, star_name TEXT, note TEXT, generated_seed INTEGER, added_date TEXT,
    PRIMARY KEY (project_id, star_name));
```
`generated_seed` is non-null for systems added from Phase R (so a procedural member is reproducible without storing its full body); looked-up real stars store `NULL`.

**`core/projects.py`** (new) — `create_project(name, description="")`, `list_projects()`, `add_member(project, star_name, note="", seed=None)`, `update_note(project, star_name, note)`, `remove_member(project, star_name)`, `delete_project(name)`, `get_project(name) -> {project, members:[...]}`. All self-validating (duplicate name → error; unknown project → error; idempotent membership via `INSERT OR REPLACE`).

**GUI** — `ProjectPanel`: a project list (create/rename/delete) + the selected project's member table (Star | Note | Source [looked-up / generated seed N] | Added) with per-row "Open" (routes to the SIMBAD/analysis panel, or re-runs `generate_system(seed)` for procedural members), inline note editing, and **"Export Project Dossier"** → Phase Q batch mode over all members. An "Add current star" button appears on the SIMBAD panel (like J2's bookmark, but targeting a chosen project).

**`query.py`** — read-only `project-list` and `project-get --name …` (so the downstream repo can drive a whole setting from query.py); mutations stay GUI-only (writes belong to the interactive workspace, consistent with the "no DB-write subcommands" principle).

**Validation / tests / success**: `tests/test_projects.py` (offline, tmp DB) — CRUD round-trips, unique-name enforcement, membership idempotency, `get_project` shape, cascade on `delete_project`, and the generated-seed round-trip (a procedural member re-generates identically via its stored seed). Success: projects persist; members carry notes + reproducible procedural seeds; a project exports as a multi-system dossier; no existing behavior changes.

---

## Remaining Work — Priority (R / S)

The full historical priority table (Phases G–P) is in [`future_phases_archive.md`](future_phases_archive.md#implementation-priority-recommendation-historical). Phase **Q** is ✅ implemented (2026-06-20). Only R/S remain:

| Phase | Effort | Value | Recommendation |
|---|---|---|---|
| R — Procedural Generation | Medium | **High** | Inverts the analysis tools into a deterministic (seed-stable) generator; reuses the Phase H + HZ + main-sequence physics. Pairs with the now-shipped Q (export systems as dossiers) and S (collect). |
| S — Project Workspaces | Medium | Medium–High | Turns the app into a worldbuilding workspace (campaign/novel manager). Builds on the J2 favorites concept; the natural home for R-generated systems and Q batch export. Best after R. |
