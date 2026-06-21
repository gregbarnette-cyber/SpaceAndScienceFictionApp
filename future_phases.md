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


> **Status (updated 2026-06-20):** Phases **A–F** (skeleton → SQLite migration) plus **G, H, I (+ I-OPTS), K, L, M, N, O, P** are ✅ implemented; **Phase J** is ❌ declined. Their full brainstorm/spec text has been **moved to [`future_phases_archive.md`](future_phases_archive.md)** to keep this file lean — see the *Completed & Declined Phases* table below for per-phase pointers (archive section, `PHASE_*_PLAN.md`, `docs/`). This file now tracks only **forward-looking work**: the Phase **Q / R / S** candidates. `query.py` currently carries **61 subcommands**.

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

---

# New phase candidates (beyond P)

> Brainstormed 2026-06-13. Three new phases that build a coherent **worldbuilding workflow** on top of the existing engine — **generate** plausible systems (R), **organize** them into named projects (S), and **export** them as shareable dossiers (Q). Each reuses existing `core/` functions, follows the GUI-only-plus-`query.py` model, and is independently valuable. Mockup-gated like every prior phase. None is spec'd to build-ready depth yet — these are the next brainstorm tier, at the J/K/L level of detail.

## Phase Q — System Dossier Export & Reporting

**New panels (GUI-only)**: `DossierExportPanel`
**Existing options touched**: none — Q *reads* the result dicts that opts 1/3/6/8 and the GCNS/Hypatia paths already produce; no computation changes.

The app computes rich per-star analyses but can only **display** them, one tab at a time. A worldbuilder (and the downstream `scifiWorldBuilding` repo) wants a single **shareable document** bundling everything known about a system. Q renders the existing result dicts into a self-contained **HTML or Markdown dossier** — no new astronomy, just composition + templating.

**`core/report.py`** (new module) — pure formatting, no I/O beyond returning a string:
- `build_system_dossier(star: str, sections: list[str] = None, fmt: str = "markdown") -> dict` — orchestrates the existing readers (`compute_simbad_lookup` → `compute_star_system_regions_from_simbad` + `compute_hypatia_data`; optional `compute_hwc`, `compute_planetary_systems_composite`, the GCNS cross-ref) and renders the merged data to one document. `sections` selects among `{"identity", "regions", "habitable_zone", "planets", "hypatia", "gcns"}` (default all available). `fmt ∈ {"markdown", "html", "json"}`.
- Returns `{"star": str, "fmt": str, "sections": [...], "document": str, "warnings": [str]}` or `{"error": str}`. Per-source failures (e.g. no Hypatia data) become `warnings`, not errors — the dossier still renders with what resolved.
- HTML output is **self-contained** (inline `<style>`, no external assets); tables mirror the GUI table columns; embeds the existing matplotlib diagrams as inline base64 `<img>` **only when matplotlib is available** (HZ ring, abundance bar chart), otherwise text-only.

**GUI** — `DossierExportPanel`: star name field + section checkboxes + format radio (Markdown / HTML) + "Generate" (background, since it runs the network readers) → preview pane + "Save to file…" (`QFileDialog`). A "Batch" mode takes a newline list of stars and writes one file each (ties into Phase S projects — export a whole project at once).

**`query.py`** — `dossier --star … [--fmt markdown|html|json] [--sections …]`: emits the document on stdout. This is **high value for the downstream repo** — one Bash call returns a complete, citeable system writeup instead of stitching 5+ subcommand outputs together.

**Validation / tests / success**: self-validating (bad star → the SIMBAD error; unknown `fmt`/`section` → `{"error"}`). Tests (`tests/test_report.py`, offline, mocked readers): section selection, the markdown/html/json shapes, per-source-failure-becomes-warning isolation, deterministic output for a fixed fixture. Success: a single call produces a complete, self-contained dossier; missing data degrades to warnings; existing panels/outputs untouched.

## Phase R — Procedural Star System Generation

**New panels (GUI-only)**: `SystemGeneratorPanel`
**Existing options touched**: none — R is a new consumer of the existing physics (`compute_main_sequence_table`, `compute_habitable_zone`, `compute_star_luminosity`, and the Phase H `compute_hill_sphere` / `compute_roche_limit` / `compute_atmosphere_retention`).

Generate **plausible synthetic star systems** for fiction — the inverse of the app's analysis tools. Given a seed (and optional constraints), build a star, place planets, and attach moons, all grounded in the equations already implemented, with **deterministic, reproducible output** (same seed → same system).

**`core/generate.py`** (new module):
- `generate_system(seed: int, spectral_class: str = None, n_planets: int = None, require_habitable: bool = False) -> dict` — uses a seeded `random.Random(seed)` (deterministic):
  1. **Star**: pick/accept a spectral class → interpolate Teff/mass/radius/luminosity from `compute_main_sequence_table()` rows; derive the HZ via `compute_habitable_zone(teff, luminosity)`.
  2. **Planets**: sample count + semi-major axes (log-spaced with a Titius–Bode-ish jitter), masses, and eccentricities; classify each (rocky/ice/gas) by mass; compute periastron/apastron and equilibrium temperature; flag HZ membership against the star's HZ. `require_habitable=True` re-rolls until ≥ 1 rocky planet lands in the conservative HZ (bounded retries → `{"error"}` if it can't).
  3. **Moons / rings**: for giants, attach moons within `compute_hill_sphere` and outside `compute_roche_limit`; run `compute_atmosphere_retention` on rocky worlds to annotate "retains N₂/O₂/…".
- Returns a structured `{"seed", "star": {...}, "planets": [{...}], "warnings": [...]}` — the **same row shapes the analysis panels already render**, so the generated system can flow straight into the HZ/orbit/regions diagrams and a Phase Q dossier with zero new viz.
- Self-validating: `n_planets` in a sane range, valid `spectral_class`, etc.

**GUI** — `SystemGeneratorPanel`: seed field (+ "Randomize" button that fills a seed — the value is shown so it's reproducible), optional spectral-class chip, planet-count spinner, "require habitable" checkbox → generates and renders an orbit diagram + HZ ring (reusing `make_orbits_canvas` / `make_hz_canvas`) + a planet table. "Send to Dossier" hands the result to Phase Q.

**`query.py`** — `generate-system --seed N [--spectral-class G2V] [--planets 6] [--require-habitable]`: deterministic JSON, so the downstream repo can generate a stable named system from a seed and re-fetch it identically.

**Validation / tests / success**: deterministic (seed-stable) — the headline test is *same seed → identical output* (`tests/test_generate.py`, offline, no `Date.now`/unseeded RNG). Also: HZ flags consistent with `compute_habitable_zone`; moons sit between Roche and Hill; `require_habitable` either delivers a HZ rocky world or errors after bounded retries; bad inputs → `{"error"}`. Success: reproducible plausible systems that render in the existing diagrams and export via Q; physics consistent with the analysis side (a generated system analyzed by opts 8–10 agrees with its generation parameters).

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

## Remaining Work — Priority (Q / R / S)

The full historical priority table (Phases G–P) is in [`future_phases_archive.md`](future_phases_archive.md#implementation-priority-recommendation-historical). Only Q/R/S remain:

| Phase | Effort | Value | Recommendation |
|---|---|---|---|
| Q — Dossier Export | Low–Medium | **High** | Pure composition over existing readers — no new astronomy. One `query.py dossier` call returns a complete system writeup; the biggest single win for the downstream repo. |
| R — Procedural Generation | Medium | **High** | Inverts the analysis tools into a deterministic (seed-stable) generator; reuses the Phase H + HZ + main-sequence physics. Pairs with Q (export) and S (collect). |
| S — Project Workspaces | Medium | Medium–High | Turns the app into a worldbuilding workspace (campaign/novel manager). Builds on the J2 favorites concept; the natural home for R-generated systems and Q batch export. Best after Q, R. |
