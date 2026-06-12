# Phase M — GCNS Interactive Surfacing · Implementation Plan

Detailed, build-ready plan for Phase M of `future_phases.md`. GCNS (opt 58) is
fully ingested — the **331,312-source** Bayesian-distance census plus the
**~17,103 Gaia-resolved multiple-star systems** — but is reachable **only**
through `query.py`'s `gcns-*` subcommands (built for the external
scifiWorldBuilding repo). Interactive GUI users currently see only the import
panel. Phase M gives the data **display surfaces**, reusing the existing
`compute_gcns_*` core functions **without modification**.

> Status: **implemented (2026-06-11).** Six panels in `gui/panels/gcns.py`, the M5
> enrichment in `core/databases.py`, the `SimbadPanel` GCNS tab, nav + exports, docs,
> and `tests/test_simbad_gcns_enrichment.py` are all in place; the full suite is green.
> Companion mockup: `mockups/phase-m.html` (representative sample data — the real
> panels read the local `gcns_stars` / `gcns_systems` / … tables). Pointer lives in
> the Phase M section of `future_phases.md`.

> **GUI-only — no menu numbers, no renumber.** Built entirely as GUI nav entries
> (precedent: `DbStatusPanel`, `NasaPlanetarySystemsMapPanel`), so it touches
> neither `main.py`'s `MENU_OPTIONS` nor the CLI menu. Six panels grouped under a
> new **"GCNS"** nav category.

---

## ⚠️ The single piece of new core code: M5

**M1–M4 add no `core/` functions.** All six display panels call the **already
built and tested** `compute_gcns_*` functions verbatim — Phase M is almost
entirely UI wiring. The *only* new computation is **M5**: an optional `"gcns"`
enrichment block attached to `compute_simbad_lookup`'s return.

**Design decision — M5 is a top-level `"gcns"` key, set inside the core
function.** `future_phases.md` and `docs/integration.md` both specify the
enrichment "lives in the shared core function" so that `query.py`'s
`simbad-lookup` gets it for free. Therefore:

- The `"gcns"` key is added **inside `core/databases.compute_simbad_lookup`**
  (not in the GUI `_simbad_with_hypatia` worker, and **not** inside the
  `designations` sub-dict — it is a **sibling** of `designations`/`hypatia`,
  exactly parallel to how the GUI attaches a top-level `"hypatia"` key).
- It is **non-fatal and silent**: wrapped so any failure (no Gaia id, GCNS not
  imported, empty/missing table, DB error) yields `result["gcns"] = None`. The
  SIMBAD result is always returned unchanged otherwise — mirroring opt 1's
  optional HWO/Hypatia sub-sections.
- **Blast radius (intended):** every `compute_simbad_lookup` consumer (all the
  two-step `query.py` subcommands and every GUI SIMBAD panel) gains the optional
  `"gcns"` key. This is the desired "parity for free" and is harmless when the
  key is `None`.

---

## Grounding facts (verified in code)

| Area | Reality (file:line) |
|---|---|
| GCNS readers | `core/databases.py`: `compute_gcns_within_sol(limit_ly)` (2011), `compute_gcns_by_source_id(source_id)` (2062), `compute_gcns_system(source_id)` (2101), `compute_gcns_distance(star1,id1,star2,id2)` (2304), `compute_gcns_travel_time(star1,id1,star2,id2,ly_hr,times_c)` (2343), `compute_gcns_stars_within_star(star,source_id,limit_ly)` (2403). **All exist, all tested, none modified by Phase M.** |
| Resolution helper | `_resolve_gcns_row(*, star=None, source_id=None)` (2210): `source_id` → offline `compute_gcns_by_source_id` (no fallback); `star` → SIMBAD → extract Gaia id via `r"Gaia\s+E?DR3\s+(\d+)"` → fetch by id → fallback to case-insensitive `star_name` match. Errors: not-in-GCNS, ambiguous-name (lists candidate ids), empty-table. |
| GCNS row shape | `_GCNS_ROW_COLS` (1992) / `_gcns_row_to_dict` (2003): `gaia_source_id, ra, dec, parallax, parallax_error, dist_pc, dist_lo_pc, dist_hi_pc, light_years, phot_g_mean_mag, phot_bp_mean_mag, phot_rp_mean_mag, rv_kms, wd_prob, astrom_reliable_prob, spectral_type, star_name, app_magnitude, in_gcns, in_simbad, distance_method, gcns_table, system_id, n_components`. |
| SIMBAD lookup | `compute_simbad_lookup(star_name)` (90); returns `{main_id, ra, dec, sp_type, plx_value, teff, vmag, ly, parsecs, designations, desig_str}`. `designations["Gaia EDR3"]` set at ~218 from `"Gaia EDR3 "`/`"Gaia DR3 "` prefixes. **M5 inserts a top-level `"gcns"` key here.** |
| Empty-table errors | `"gcns_stars table is empty — run option 58 (Import GCNS Data) first."` and the analogous `gcns_systems` message. Panels surface these in the red `_err` label. |
| DB path | `core/db.py` `_DB_PATH` (8): `SPACE_APP_DB` env override else `data/space_app.db`. Tests monkeypatch this. |
| Pure-form panel pattern | `LuminosityPanel`/`HabZone*Panel`: `build_inputs()` sets `_input_count`, `QFormLayout` + Calculate `QPushButton`, hidden red `_err` `QLabel`, result container rebuilt per calc. |
| Network panel pattern | `SimbadPanel` (`gui/panels/simbad.py:23`): `build_inputs()` → `_name_input` + `run_btn` → `_search()` (47) → `self.run_in_background(_simbad_with_hypatia, name)` (52) → `render(result)` (54). Background `Worker`/`run_in_background` from `base.py`. |
| Map-tab panel pattern | `StarsWithinDistanceSolPanel`/`StarsWithinDistanceStarPanel` (`gui/panels/distance_stars.py`) inherit `(DiagramToggleMixin, ResultPanel)`; `_build_results_area_distance(self)` (93) builds `_tables_widget` + `_setup_diagram_view()` (`_viz_container`/`_viz_tabs_widget`); `_render` calls `_prepare_render()` → add tables → add canvases to `_viz_tabs_widget` → `_finish_render()`. |
| Canvas helpers | `gui/visualizations/plot_helpers.py`: `make_star_map_canvas(parent, stars, title="", xk="x", yk="y", xlabel="X (ly)", ylabel="Y (ly)", bg=_SPACE_BG)` (536) → `(canvas, toolbar)`; `make_star_map_3d_canvas(parent, stars, title="", bg=_SPACE_BG)` (650) → `(canvas, toolbar, ax)`; `make_star_chart_canvas`/`make_star_chart_3d_canvas`. `mpl_available()` guards all. Star dicts need `{name, color, ly, x, y, z}`. |
| nav | `gui/nav.py` `NAVIGATION = [(category, [(label, "PanelClassName"), …])]`; resolved via `getattr(gui.panels, name)`. |
| exports | `gui/panels/__init__.py` explicit `from gui.panels.x import Y`. |
| query.py | `cmd_simbad_lookup(args)` (37) = `_out(databases.compute_simbad_lookup(args.star))` — **serializes the core return verbatim**, so the M5 `"gcns"` key flows out with **no query.py code change**. The six `gcns-*` subcommands already exist (100–128). |

---

## Resolution model — name vs. Gaia source_id (shared by M2/M3/M4)

The GCNS core is keyed on **Gaia source_id**; every reader runs **offline**
against the local tables. SIMBAD is **never required** — only an optional
front-end translating a typed *name* → Gaia id. This dual path is already proven
in the `query.py` GCNS calculators (`--star` vs `--id`); the panels mirror it
**without adding resolution code** — the `compute_gcns_*` functions already take
`star=`/`id=`/`source_id=` params and call `_resolve_gcns_row` internally.

GUI branch rule (the one new bit of panel logic):

- **Both a name field and a Gaia source_id field** on M2/M3 and the M4
  calculators. **id wins if both are filled.**
- **Any endpoint resolved by name** → the panel runs the compute call in a
  **background `Worker`** (network SIMBAD step), exactly like `SimbadPanel`.
- **All endpoints are raw source_ids** → **synchronous instant** call (pure
  local DB), no thread.
- A star genuinely absent from GCNS surfaces the core's clean
  `"… is not in the GCNS catalog …"` in the red `_err` label — **never** a
  silent SIMBAD-distance substitution. Ambiguous names show the candidate ids.

---

## Work Package 0 — Shared GCNS panel scaffolding (`gui/panels/gcns.py`)

New file holding all six panels + shared helpers. Factor these so the panels stay
thin:

1. **`_GCNS_FIELDS`** — ordered `(key, label, fmt)` list for rendering a single
   GCNS row as a label/value detail table (used by M2 and the M5 block). Formats:
   distances 4dp, probabilities 4dp, photometry 4dp, ids/strings verbatim, `None`
   → `"N/A"`.
2. **`_fmt_sigma(row)`** — renders the headline uncertainty as
   `"{dist_lo_pc:.4f} / {dist_hi_pc:.4f}"` (the −σ/+σ pair), or `"—"` when
   `dist_lo_pc`/`dist_hi_pc` are `None` (the `missing_10mas` 1/ϖ rows). **This is
   the app's only distance error bar.**
3. **`_dual_input(form, name_label, id_label)`** — builds and returns the
   `(name_edit, id_edit)` `QLineEdit` pair used by M2/M3/M4; wires
   `returnPressed → run_btn.click`.
4. **`_needs_network(*name_id_pairs)`** — returns `True` if any endpoint is given
   by name (→ background) else `False` (→ instant). Drives the branch above.
5. **`_run(self, fn, **kwargs)`** — helper: if `_needs_network`, call
   `self.run_in_background(fn, **kwargs)`; else call `fn(**kwargs)` synchronously
   and hand the result straight to `_render`. Centralizes the branch so each
   panel's button handler is one line.
6. **`_gcns_star_map(stars, center=None)`** — adapts GCNS `stars[]` (which already
   carry `x`/`y`/`z`) into the `{name, color, ly, x, y, z}` dicts the canvas
   helpers want; spectral color via the existing spectral→color map used by the
   opt 18/19 maps; center star (M4 within-star) gold-highlighted.

All six panels also share the **empty-table guard**: check `result.get("error")`
first and show it in `_err` (covers the "run option 58 first" message).

---

## WP1 — M1 GCNS Census Browser (`GcnsCensusBrowserPanel`)

**All GCNS sources within N ly of Sol.** Backed by
`compute_gcns_within_sol(limit_ly)`. **No SIMBAD, no network, no thread** — an
instant local-DB read (like opt 18, not opt 1).

### Class: `GcnsCensusBrowserPanel(DiagramToggleMixin, ResultPanel)`
- MRO **must** be `(DiagramToggleMixin, ResultPanel)` (mixin `reset()` runs first).
- `build_inputs()`: single distance `QLineEdit` ("Distance from Sol (ly)") +
  Calculate button; `_show_diagrams_btn` created here, hidden.
- `build_results_area()`: build `_tables_widget` (count label + the table) and
  call `self._setup_diagram_view()`; reset `_input_count` at the end (the
  opt 18/19 `_build_results_area_distance` pattern).
- `_render(result)`: `_prepare_render()` → if `result.get("error")` show it and
  return → count label `"N GCNS sources found."` → table → add map tabs to
  `_viz_tabs_widget` (`mpl_available()` guard) → `_finish_render()`.

### Output table columns
Star Name | Gaia source_id | Spectral Type | Dist (pc, 4dp) | **−σ / +σ (pc)** |
Light Years (4dp) | Distance Method | In SIMBAD.
- The **−σ/+σ columns are the headline differentiator** (`_fmt_sigma`);
  `missing_10mas` rows show `—`.
- `In SIMBAD` → `Yes`/`No` from `in_simbad`.

### Viz tabs (reuse opt 18/19 infra)
**"Star Chart" + "Star Chart 3D"** — the labeled dark-navy diagrams from opts 18/19
(`make_star_chart_canvas` + `_build_star_chart_3d_tab`), over the heliocentric
`x`/`y`/`z` already in the result, with Sol as the gold ★ at the origin.
*(Maintainer preference: the GUI uses the labeled Star Chart / Star Chart 3D format,
not the plain Map X–Y/X–Z/3D set.)*
- **Viz enhancement (M1-specific, optional, NOT built):** a radial distance-
  uncertainty indicator from `dist_lo_pc`/`dist_hi_pc` was deliberately skipped to
  avoid modifying the shared canvas helpers (which opts 18/19 also use). The −σ/+σ
  table columns deliver the uncertainty headline instead.

---

## WP2 — M2 GCNS Source Lookup (`GcnsSourceLookupPanel`)

**Full detail for one GCNS source.** Dual input. Backed by
`compute_gcns_by_source_id(source_id)` (id path) and `_resolve_gcns_row(star=…)`
(name path). **Use `_resolve_gcns_row` for the name path** so the
SIMBAD→id→name-fallback chain (and `missing_10mas` name resolution) comes for
free; for a raw id, call `compute_gcns_by_source_id` directly.

### Class: `GcnsSourceLookupPanel(ResultPanel)` (no mixin — no map)
- `build_inputs()`: `_dual_input` (name + Gaia source_id) + Lookup button.
- Button handler: `_run` → instant for id, background for name.
- `_render(result)`: error → `_err`; else render via `_GCNS_FIELDS` as a
  two-column (Field | Value) `QTableView`.

### Output (single-source detail)
Bayesian `dist_pc` **+ −σ/+σ**, `light_years`, `distance_method`, Gaia
**G/BP/RP** photometry (labeled explicitly *Gaia bands — not Johnson V*),
`wd_prob`, `astrom_reliable_prob`, `rv_kms`, SIMBAD cross-match
(`spectral_type`, `star_name`, Johnson `app_magnitude`), and
`system_id`/`n_components`.
- When `system_id` is set: an info line
  `"Part of a resolved {n_components}-component system — open the System Viewer."`
  Otherwise (single/unresolved): a muted note
  `"Not part of a Gaia-resolved multiple system (single or unresolved)."` — so the
  multiplicity status is explicit either way and Source Lookup agrees with the
  System Viewer.

---

## WP3 — M3 Resolved System Viewer (`GcnsSystemViewerPanel`)

**The Gaia-resolved system containing a source.** Dual input. Backed by
`compute_gcns_system(source_id)` (id path) / `_resolve_gcns_row(star=…)` → take
its `gaia_source_id` → `compute_gcns_system` (name path).

### Class: `GcnsSystemViewerPanel(ResultPanel)`
- `build_inputs()`: `_dual_input` + View button.
- `_render(result)`: error → `_err` (covers *"not part of any GCNS resolved
  system (single or unresolved object)"* and the empty-`gcns_systems` message);
  else three sections:
  1. **System summary** (label/value table): `system_id`, `n_components`,
     `n_pairs`, `any_bin`, `any_bound`, `all_bound`, `min/max_proj_sep_au`,
     `n_in_gcns_stars`.
  2. **Members table**: `gaia_source_id`, `in_gcns_stars` (Yes/No), `is_query`
     (▶ marker on the queried component), `star_name`, `spectral_type`,
     `dist_pc`, `light_years` — last four `N/A` when a member isn't in
     `gcns_stars` (retained, not dropped).
  3. **Pairs table**: `source_id1`, `source_id2`, `separation_arcsec`,
     `mag_diff`, `proj_sep_au`, `bin` (Yes/No), `bound` (Yes/No).
- **Stretch viz (skippable):** a component-geometry scatter positioned from
  `proj_sep_au`, with a footnote on the friends-of-friends chaining caveat
  (`n_components` from chained pairs is an upper bound in crowded fields). Not
  required for first ship.

---

## WP4 — M4 GCNS-backed calculators (3 panels)

Mirror opts 17 / 20–21 / 19 but compute over the GCNS census (Bayesian distances
+ uncertainties), **keeping Gaia-resolved close companions** the SIMBAD
`stars-within-star` drops within 0.001 ly. Each carries `distance_method` +
`dist_lo_pc`/`dist_hi_pc` in its info blocks. **No new core code** — pass through.

### M4a `GcnsDistancePanel(ResultPanel)` — `compute_gcns_distance(star1,id1,star2,id2)`
- Inputs: two `_dual_input` endpoint blocks (Star 1: name|id, Star 2: name|id).
- Output: a `distance_ly` headline line (+ `distance_au` when < 0.5 ly), then a
  two-column comparison of `star1_info` / `star2_info`
  (`gaia_source_id, star_name, spectral_type, dist_pc, −σ/+σ, light_years,
  distance_method, ra_hms, dec_dms`).

### M4b `GcnsTravelTimePanel(ResultPanel)` — `compute_gcns_travel_time(…, ly_hr, times_c)`
- Inputs: two endpoint blocks + a velocity unit `QComboBox` (LY/HR | ×c) +
  value `QLineEdit` (derive `ly_hr`/`times_c`; pass exactly one).
- Output: a results table — Origin | Destination | Distance (LY) | LY/HR | ×c |
  Travel Time (Hours) | Travel Time (`travel_time_str`) — plus the two endpoint
  info blocks. Zero/negative velocity → core `{"error"}` → `_err`.

### M4c `GcnsStarsWithinStarPanel(DiagramToggleMixin, ResultPanel)` — `compute_gcns_stars_within_star(star,source_id,limit_ly)`
- Inputs: one `_dual_input` (center: name|id) + distance `QLineEdit` (ly).
- Output: count `"N GCNS stars within {ly} ly of {center}."` + table — Star Name |
  Gaia source_id | Spectral Type | Dist (pc) | −σ/+σ | **Distance from center
  (ly, 4dp)** | Distance Method.
- Viz tabs: same **"Star Chart" + "Star Chart 3D"** (labeled dark-navy, opts-18/19
  style) as M1, with the **center star gold-highlighted** at the origin
  (`_gcns_map_stars(result, center=True)`); uses the `center_x/y/z` + per-row
  `x/y/z` from the result. *(Implementation note: the GUI uses the labeled Star
  Chart / Star Chart 3D diagrams per the maintainer's preference, not the plain
  Map X–Y/X–Z/3D set.)*

**Branch:** M4a/M4b render synchronously when both endpoints are ids; M4c is
instant when the center is an id; otherwise background (`_needs_network`).

---

## WP5 — M5 opt-1 SIMBAD GCNS cross-reference (the only core change)

### Core: enrich `compute_simbad_lookup` (`core/databases.py`)
After `designations` is built and the Gaia id is known, attach a **top-level**
`"gcns"` key:

```python
# after designations / desig_str are assembled, before `return result`
result["gcns"] = _simbad_gcns_block(result["designations"])
```

`_simbad_gcns_block(designations) -> dict | None` (new private helper):
- Parse the bare id from `designations["Gaia EDR3"]` (strip `"Gaia DR3 "` /
  `"Gaia EDR3 "`); if absent → return `None`.
- `r = compute_gcns_by_source_id(int(id))`; if `r` has `"error"` (not found /
  empty table) → return `None`.
- Return `r["star"]` (the full GCNS row dict — Bayesian `dist_pc` + `dist_lo_pc`/
  `dist_hi_pc`, `distance_method`, `astrom_reliable_prob`, `wd_prob`, Gaia
  G/BP/RP, `system_id`/`n_components`).
- **Wrap the whole thing in `try/except` returning `None`** — non-fatal, silent.

> Single indexed local-DB read; no extra network (reuses the id opt 1 already
> resolved). Resilient to empty/missing `gcns_stars` (tests that monkeypatch
> `_DB_PATH` to a seed-less DB still pass — the block is just `None`).

### GUI: render the block in `SimbadPanel` (`gui/panels/simbad.py`)
In `render(result)`, when `result.get("gcns")` is non-`None`, add a **"GCNS"
tab** to the existing `QTabWidget` (between Hypatia and Abundance Profile), or a
small table at the bottom of the **Star Properties** tab. **Headline:** show the
GCNS **Bayesian distance with its 16th/84th uncertainty** next to opt 1's
existing naive **1/ϖ parallax distance** (`result["ly"]`/`result["parsecs"]`) — a
probabilistic distance *with error bars* beside the point estimate — plus
`distance_method`, `astrom_reliable_prob`, `wd_prob`, the Gaia G/BP/RP photometry
(separate from Johnson V), and the `"part of a resolved N-component system"`
pointer when `system_id` is set. **Silent when `result["gcns"]` is `None`.**

### query.py parity — no code change
`cmd_simbad_lookup` serializes the core dict verbatim, so `simbad-lookup` output
**automatically** gains the optional `"gcns"` key. **Only deliverable here is the
doc note** (WP7).

---

## WP6 — Wiring (exports + nav)

- **`gui/panels/__init__.py`** — explicit import:
  ```python
  from gui.panels.gcns import (
      GcnsCensusBrowserPanel, GcnsSourceLookupPanel, GcnsSystemViewerPanel,
      GcnsDistancePanel, GcnsTravelTimePanel, GcnsStarsWithinStarPanel,
  )
  ```
- **`gui/nav.py`** — new **"GCNS"** category (place after "Star Databases"),
  entries in this order:
  | Label | Panel |
  |---|---|
  | GCNS Census Browser | `GcnsCensusBrowserPanel` |
  | GCNS Source Lookup | `GcnsSourceLookupPanel` |
  | Resolved System Viewer | `GcnsSystemViewerPanel` |
  | GCNS Distance Between 2 Stars | `GcnsDistancePanel` |
  | GCNS Travel Time | `GcnsTravelTimePanel` |
  | GCNS Stars Within a Star | `GcnsStarsWithinStarPanel` |
- No `main.py` / `MENU_OPTIONS` change.

---

## WP7 — Docs

- **`docs/gui-architecture.md`** — add the six panels to the panel→option mapping
  (option column "— (GUI-only, Phase M)"); add `gcns.py` to the repo-structure
  block; document the dual name/id input + instant-vs-background branch; note the
  M5 GCNS tab in `SimbadPanel`'s viz-tab table; the M1/M4c **Star Chart / Star
  Chart 3D** tabs (`_add_chart_tabs` → `make_star_chart_canvas` /
  `_build_star_chart_3d_tab`).
- **`docs/star-databases.md`** — new "GCNS Display Surfaces (Phase M)" subsection
  describing M1–M4 (each maps to its existing `compute_gcns_*` reader) and the M5
  cross-reference enrichment.
- **`docs/integration.md`** — under `simbad-lookup`, note the new **optional
  top-level `"gcns"` key** (full GCNS row dict, or `null` when no Gaia id / not in
  GCNS / table empty); same shape as `gcns-source`'s `star`. Flag that it is
  silent/non-fatal.
- **`future_phases.md`** — mark the Phase M section "✅ IMPLEMENTED" with a pointer
  to this plan (mirror the Phase H pointer block).

---

## Tests & Validation

### `tests/test_simbad_gcns_enrichment.py` (new, offline — monkeypatch `_DB_PATH`)
Pattern from `tests/test_gcns.py` (SIMBAD mocked, tmp DB, seeding disabled):
- Seed a tiny `gcns_stars` row with a known `gaia_source_id`; mock
  `compute_simbad_lookup`'s SIMBAD call to return designations carrying that id
  → assert `result["gcns"]` is the row dict (Bayesian dist + σ present).
- Designations with **no** Gaia id → `result["gcns"] is None`.
- Id present but **absent** from `gcns_stars` → `result["gcns"] is None`.
- **Empty/missing `gcns_stars`** → `result["gcns"] is None` **and the rest of the
  SIMBAD result is unchanged** (non-fatal guard).
- `_simbad_gcns_block` strips both `"Gaia DR3 "` and `"Gaia EDR3 "` prefixes.

### `tests/test_query_simbad_gcns.py` (optional, subprocess like `test_gcns`)
- `query.py simbad-lookup --star …` against a seeded tmp DB (`SPACE_APP_DB`) →
  JSON has top-level `"gcns"`; against an empty DB → `"gcns"` is `null`, exit 0.

### Regression
- The existing `test_gcns.py` GCNS-reader tests are **untouched** (M1–M4 add no
  core code). Full `pytest` suite stays green; the M5 guard must not perturb
  existing `compute_simbad_lookup` tests (they should now also carry a `"gcns"`
  key — update any exact-dict-equality assertion to tolerate it, or assert
  subset).

### Manual / GUI
- `python gui_main.py` → **GCNS** category:
  - **Census**: distance N → table with populated −σ/+σ columns; `missing_10mas`
    rows show `—`; Show Diagrams → maps render; empty table → red "run opt 58".
  - **Source Lookup**: by Gaia id (instant) and by name (background SIMBAD);
    absent star → clean "not in GCNS"; ambiguous name → candidate-id message.
  - **System Viewer**: a known 2-component id (e.g. 61 Cygni) → summary + members
    (▶ on the queried row) + pairs; a single star → "not part of any resolved
    system".
  - **Distance / Travel Time / Within-Star**: id↔id instant, name endpoints
    background; within-star keeps close companions.
- **opt 1 SIMBAD** on a GCNS-present star → GCNS block shows Bayesian dist + σ
  beside the 1/ϖ distance; on a star with no Gaia id / outside GCNS → block
  absent (silent).

---

## Success Criteria
- Six GCNS panels under a new "GCNS" nav category, each calling the **existing**
  `compute_gcns_*` readers verbatim (no `core/` changes for M1–M4).
- Dual name/id input on M2/M3/M4 with the instant-vs-background branch; clean
  pass-through of the core's not-in-GCNS / ambiguous / empty-table errors.
- M1/M4c reuse the opt 18/19 map tabs; the **−σ/+σ distance-uncertainty columns**
  (the app's only distance error bar) render, blank for `missing_10mas`.
- **M5**: `compute_simbad_lookup` gains a non-fatal top-level `"gcns"` key;
  `SimbadPanel` shows the Bayesian-distance-with-uncertainty block beside the 1/ϖ
  estimate; `query.py simbad-lookup` emits the key with **no dispatcher change**.
- New offline tests pass; existing GCNS + SIMBAD suites stay green; docs updated.

**Suggested build order:** WP0 (scaffolding) → WP1 (Census — proves the map-tab
panel + GCNS row rendering with no network) → WP2 (Source Lookup — proves the
dual input + branch) → WP3 (System Viewer) → WP4 (the three calculators) → WP5
(M5 core enrichment + SimbadPanel block — the only core change) → WP6 wiring →
WP7 docs → tests throughout.
