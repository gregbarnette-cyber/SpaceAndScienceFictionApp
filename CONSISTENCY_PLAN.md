# Consistency Fix Plan

**Audience:** A Claude Opus (high effort) instance implementing this plan in a single focused session.
**Origin:** Full doc-vs-code consistency audit performed 2026-06-10, reviewed by the maintainer. All file:line references were verified against the working tree at commit `9f04915`.
**Scope:** Consistency and maintenance only. New or substantial functionality enhancements are out of scope for this plan — they belong in `future_phases.md` (see "Out of scope" at the bottom).

## Ground rules

1. **Verify before editing.** Line numbers below were correct at audit time; re-grep each anchor before changing it.
2. **The CLI is frozen at opts 1–58** (per `future_phases.md`). No new `MENU_OPTIONS` entries.
3. **Docs are the contract.** Whenever code changes, update the matching `docs/*.md` section in the same commit.
4. **Maintainer decisions already made** (do not revisit): opts 2 and 7 were deliberately removed from the GUI — the "not exported / not in nav" state is intentional and the docs describing it are correct. No OEC `query.py` subcommand is wanted. `generate_star_map_html.py` was a one-off testing script — leave it alone.
5. **Run verification (§3) after each part.** Parts are independent; commit each part separately.

---

## Part 1 — Documentation consistency fixes (doc-only except 1.4)

### 1.1 Fix stale `_ELEMENT_NAMES` reference
- `docs/gui-architecture.md:57` claims `gui/panels/hypatia_tab.py` provides `build_hypatia_tab(), fit_table_height(), _ELEMENT_NAMES`.
- Reality: `_ELEMENT_NAMES` does not exist. The module exports `build_hypatia_tab()` and `fit_table_height()`; element metadata comes from `core.hypatia_elements` (`CATEGORIES`, `category_label`, `display_symbol` — see `gui/panels/hypatia_tab.py:11`).
- **Change:** update the repo-structure comment to `# Shared: build_hypatia_tab(), fit_table_height(); element metadata from core.hypatia_elements`.

### 1.2 Fix SETUP.md database location
- `SETUP.md:80` says the SQLite DB is "created automatically in the project directory".
- Reality: `core/db.py:11` resolves it to `data/space_app.db` under the repo root (and `data/` is gitignored).
- **Change:** correct the path in SETUP.md; mention the `SPACE_APP_DB` env override (already documented in `docs/integration.md`).

### 1.3 Reconcile CLAUDE.md option-4 menu label
- `CLAUDE.md:65` says "NASA Exoplanet Archive: HWO ExEP Stars"; `main.py:5631` registers "NASA Exoplanet Archive: HWO ExEP Precursor Science Stars".
- **Change:** update CLAUDE.md to the full label. If it breaks the two-column ASCII layout, keep the short form but add a footnote noting the full in-app label. Do **not** change the code label.

### 1.4 Standardize the ly-per-parsec constant *(small code change — the only behavioral edit in Part 1)*
- The Star System Regions paths use `3.2616` (`main.py:1136`, `main.py:1656`, `main.py:1734`, `main.py:5392`, `core/regions.py:145`); everything else in the app uses `3.26156`.
- `docs/star-system-regions.md:64` documents the `3.2616` value, so doc and code currently agree with each other but not with the rest of the app.
- **Change:** change all five code sites to `3.26156` and update `docs/star-system-regions.md:64` to match. Numeric impact is ~1 part in 10⁵ (4th decimal of displayed light-years may shift).
- **Acceptance:** `grep -rn "3\.2616[^0-9]" main.py core/ docs/` returns nothing.

### 1.5 Link the orphaned Hypatia API doc
- `docs/hypatia_catalog_api.md` is the only `docs/` file not `@`-referenced from CLAUDE.md (CLAUDE.md `@docs/...` block) and is linked from no other doc. Its content is accurate.
- **Change:** add `@docs/hypatia_catalog_api.md` to CLAUDE.md's reference block (or, if it's meant as reference-only, add a pointer line in `docs/star-system-regions.md`'s Hypatia section saying so).

### 1.6 Document the test suite
- `tests/` has 8 files (`test_gcns.py`, `test_gcns_live.py`, `test_gui_hypatia.py`, `test_hypatia_elements.py`, `test_hypatia_live.py`, `test_parse_composition.py`, `test_prepare_abundance_profile.py`, `_netcheck.py`) but no doc mentions them.
- **Change:** add a "Run tests" entry to CLAUDE.md's Commands section (`pytest` invocation), noting: which tests hit the live network (`*_live.py`, gated via `tests/_netcheck.py`), and that tests use the `SPACE_APP_DB` env override for fixture DBs. One short paragraph, not a new doc. Write it to also cover the new tests added in Part 2.2.

### 1.7 Declare numpy in requirements.txt
- `gui/visualizations/plot_helpers.py:1161` and `:1962` import numpy directly; `requirements.txt` only provides it transitively (matplotlib/astropy).
- **Change:** add `numpy` to `requirements.txt`. Update SETUP.md's library table if it lists packages individually.

### 1.8 Disposition the three unreferenced root CSVs
- `templateStarSystems.csv`, `starSystems_327ly.csv`, `starSystemsBackup-20260416.csv` have zero references in any `.py` or `.md` file.
- **Change (default):** move them to a new `backups/` directory and add one line to SETUP.md saying `backups/` holds manual snapshots not used by the app. Do **not** delete without explicit maintainer approval.

### 1.9 Banner the stale planning docs
- `hypatia_implementation.md` already carries a "Historical planning doc" banner; `INTEGRATION_PLAN.md` and `GCNS_EXTENSION_REQUEST.md` describe fully completed work but lack it.
- **Change:** add the same one-line historical banner to the top of both files. Content otherwise untouched.

---

## Part 2 — Maintainer-approved maintenance items

### 2.1 Prune opt-50 backup tables — keep the last 3
- Opt 50 creates `star_systems_backup_YYYYMMDD` tables (`core/databases.py:840`) and nothing ever deletes them — they accumulate forever.
- **Maintainer decision: keep the last 3 backups.**
- **Change:** in `core/db.py`, add `prune_star_systems_backups(keep_n=3)` returning `{dropped: [...], kept: [...]}`; call it at the end of the opt-50 build (after the new backup is created). Only tables matching `^star_systems_backup_\d{8}$` may ever be dropped; keep the 3 newest by date stamp. Surface the dropped/kept lists in opt 50's completion output (CLI print + GUI status). Document in `docs/star-databases.md` Backup section.
- **Acceptance:** running opt 50 repeatedly leaves at most 3 backup tables; non-backup tables are never touched; behavior is a no-op when ≤ 3 backups exist.

### 2.2 Test coverage for the pure-math core
- Current tests cover only GCNS + Hypatia paths. Zero coverage for `core/calculators.py`, `core/equations.py`, `core/regions.py`, `core/science.py`, `core/viz.py` — the physics/math heart of the app.
- **Change:** add offline-only tests (no network, no Qt) for at minimum:
  - `equations.compute_habitable_zone` — known-good Kopparapu values for Sol-like input (teff 5778, L 1.0) and a cool dwarf; error dict on bad input.
  - `shared._kopparapu_seff` — all six zone keys.
  - `shared._format_travel_time` — boundary cases (sub-minute, exactly 1 year, mixed units).
  - `regions._lookup_spectral_type` ceiling rule — G1→G2, F9→G0 cross-letter fallthrough, white-dwarf rejection (`DA1.9` must not match an OBAFGKM class).
  - Brachistochrone profiles (`compute_distance_at_acceleration`, `compute_travel_time_system_au/lm` at `core/calculators.py:837/900/918`) — closed-form checks (e.g. Profile 1: `t = 2·√(d/a)`), cap-not-reached branch, Profile 2 `d = 3·a·t²/16`.
  - Velocity conversions — `8765.8128` round-trips (ly/hr ↔ ×c).
  - Equations opts 33–38 math (`compute_orbit_periastron_apastron`, moon orbital distance via Kepler's third law against a hand-computed value, the three centrifugal-gravity functions — including the rpm↔radius↔accel mutual-inverse property).
  - Coordinate math used by opts 17/19 — RA/DEC sexagesimal↔degrees round-trip, 3D Cartesian distance for two synthetic stars, the Sol/Sun special case at origin.
  - Use `SPACE_APP_DB` pointing at a tmp fixture DB for anything touching `star_systems` (pattern already established in `tests/test_gcns.py`).
- **Acceptance:** `pytest` green offline; new tests live in `tests/test_calculators.py`, `tests/test_equations.py`, `tests/test_regions.py` (and `tests/test_science.py` if science-table functions are covered). Update the CLAUDE.md test paragraph from 1.6 accordingly.

---

## §3 Verification checklist (run per part)

1. `pytest` (offline subset must pass; live tests only if network available).
2. `python main.py` — menu renders; smoke-test one option per touched group (at minimum opts 8 and 17 after the 1.4 constant change, opt 50 path review for 2.1 — don't actually run the 17 SIMBAD queries unless the maintainer wants a rebuild; testing `prune_star_systems_backups` directly against a fixture DB is sufficient).
3. `python query.py simbad-lookup --star "Tau Ceti"` — integration surface unaffected.
4. Doc cross-check: every code change has a matching `docs/*.md` update; `grep -rn "3\.2616[^0-9]" main.py core/ docs/` is clean; CLAUDE.md menu table still matches `MENU_OPTIONS`.

## Suggested commit sequence

1. Part 1 (doc fixes + constant + requirements + CSV moves) — one commit: "docs: consistency fixes from 2026-06-10 audit".
2. 2.1 (backup pruning, keep 3) — one commit.
3. 2.2 (math-core tests + CLAUDE.md test docs) — one commit.

## Out of scope — enhancement candidates for `future_phases.md`

The audit surfaced these; the maintainer has directed that new/substantial enhancements live in `future_phases.md`, not this plan. Listed here only so they aren't lost:

- **Curated `query.py` subcommand expansion** — now formalized as **Phase N** in `future_phases.md` (`habitable-zone-sma`, `star-luminosity`, `brachistochrone-au`, `brachistochrone-lm`, `travel-time-solar`).
- **Surface `_planet_fetch_errors`** (`core/calculators.py:478`) in the System Travel panels so silently-missing planets are explained.
- **Index `star_systems(light_years)`** for opts 18/19 scans.
- Items already rejected by the maintainer (do not re-propose): GUI surfacing of opts 2/7, OEC `query.py` subcommand, `generate_star_map_html.py` integration.
- Items requiring a design decision before any work: standalone viz panels in nav, `query_criteria()` migration spike, 3D solar travel canvas, GCNS CSV export/restore, GCNS uncertainty propagation.
