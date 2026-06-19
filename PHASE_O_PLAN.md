# PHASE O — Visualization Expansion · Implementation Plan

> # ✅ PHASE O COMPLETE & maintainer-approved (2026-06-18)
> All 18 items + the F1–F3 foundations are implemented and approved across all eight
> sub-phases (O-1…O-8). The **Master Tracking Matrix** below is the per-item source of
> truth (every row ☑). `tests/test_viz_phase_o.py` = 152 green; full offline suite 512
> passed (only the 3 flaky live-network baselines fail). The dated blocks below are the
> historical per-sub-phase build log (earliest "pending sign-off" notes are superseded by
> this banner). Working tree uncommitted (maintainer reviews/commits).

> **O-5 ✅ COMPLETE (2026-06-18, pending final maintainer sign-off):** O9
> Brachistochrone Profile Charts (`prepare_brachistochrone_profiles` +
> `make_profile_canvas`, tabs on opts 22/23/24/29/30), O5 Date Scrubber (O5a
> offline exoplanet System Map `_SystemMapScrubber`; O5b ephemeris-driven solar
> map `_SolarMapScrubber` + `compute_solar_ephemeris_track` — maintainer chose
> accurate batch ephemeris over circular propagation), O8 Two-Star Map (opts
> 17/20/21 gain "Star Chart" + "Star Chart 3D" tabs via Phase I `routes=` +
> `_two_star_route_map`/`add_two_star_chart_tabs`). Two bugs fixed under O5:
> `fetch_body_properties` urllib→requests (SSL on intercepting proxies) and the
> ERFA "dubious year" warning suppression. `tests/test_viz_phase_o.py` = 110 green.
> **O-6 ✅ COMPLETE (2026-06-18, pending final sign-off):** O6 Sol-regions ring
> parity (opt 13 via the extracted `star_regions.add_region_diagram_tabs`), O7
> Solar-system orbital diagrams (opt 11 — `prepare_solar_system_orbits` + the
> additive `make_orbits_canvas(title=, km_axis=)`), O10 Honorverse (O10a opt-14
> hyper-limit bar chart `prepare_hyper_limits`/`make_hyper_bar_canvas`; O10b opts
> 8/9 dashed-red hyper-limit ring on the System Regions Diagram via an **opt-in
> checkbox** — `science.compute_hyper_limit_for_spectral_type` ceiling lookup +
> `prepare_system_regions_diagram` `hyper_limit` key + `make_system_regions_canvas(show_hyper=)`
> + `wrap_system_regions_with_hyper_toggle`; opts 10/13 omit it). `tests/test_viz_phase_o.py`
> = 130 green.
> **O-7 ✅ COMPLETE (2026-06-18, pending final sign-off):** O11 Toomre / Galactic
> Kinematics (`core.viz.prepare_toomre` + `make_toomre_canvas` + the shared
> `make_kinematics_tab` widget) added as a **"Kinematics"** viz tab wherever the
> Hypatia Abundance Profile tab appears (opts 1, 3–6, 8), shown only when U/V/W are
> all non-null. Each tab carries the F2 **"ℹ What is this?"** Explain button
> (`TOOMRE_HELP_HTML`). **Open Decision #2 resolved:** Hypatia returns *heliocentric*
> U/V/W → LSR-corrected (Schönrich+ 2010 solar motion via `core.viz._SOLAR_MOTION_UVW`),
> arcs centred at the LSR origin so the 50/70–180/180 km/s thin/thick/halo thresholds
> read directly. `tests/test_viz_phase_o.py` = 143 green; full offline suite 503 passed.
> **O-8 ✅ COMPLETE (2026-06-18, pending final sign-off):** O12 HWC Habitability Visuals
> (opt 6) — `core.viz.prepare_hwc_temps` + `make_hwc_temp_canvas` ("Temperature Ranges":
> per-planet equilibrium/surface min→max bars + 273–373 K liquid-water band) and
> `core.viz.prepare_hwc_esi` + `make_hwc_esi_canvas` ("ESI vs Orbit": SMA-vs-ESI scatter,
> log when span >10×, optimistic/conservative HZ bands, habitable colouring, dot-anchored
> hover). Both `HwcPanel` viz tabs are additive (each shown only when ≥1 planet qualifies);
> per-system only (no overlap with L2's cross-catalog ESI ranking). `tests/test_viz_phase_o.py`
> = 152 green. **Phase O is now feature-complete (all 18 items + F1–F3 done).**
>
> **Status: O-1 ✅, O-2 ✅, O-3 ✅, O-4 ✅ COMPLETE + maintainer-approved (2026-06-17).**
> O-3 shipped all checkpoints: CP0 capability layer, CP1 O15 row↔map linking, CP2 O16 2D
> legend filtering, CP3 O16 3D legend filtering, CP4 O17 travel-time isochrone rings
> (Star Chart 2D+3D), CP5 O18 find-star box. **O-4 (Planet & System Diagrams — opts
> 3/6/Map)** shipped all four items: O3 Mass–Radius (`prepare_mass_radius` +
> `make_mass_radius_canvas`), O4 Solar-System reference overlay (additive
> `make_orbits_canvas(solar_overlay=)` + the `wrap_orbits_with_solar_toggle` checkbox),
> O13 Transit Geometry (`prepare_transit_geometry` + `make_transit_canvas`), O14 Planet
> Size-Comparison strip (`make_size_comparison_canvas`, no `prepare_*`). All four tabs are
> additive (shown only with qualifying planets); the O3/O13/O14 hover tooltips anchor to
> the dot (an early fixed-corner placement made them appear invisible). `tests/test_viz_phase_o.py`
> = 83 green; full offline suite 443 passed (the only 3 failures are flaky live-network
> tests — JPL Horizons / NASA TAP — reachable-but-throttled under the suite's back-to-back
> call pattern; the features themselves work). **Next: O-5 (Travel & Motion — opts 17, 20,
> 21, 22, 23, 24, 29, 30 + Map: O9 brachistochrone profiles, O5 date scrubber, O8 two-star
> map).** O-5…O-8 are PLAN ONLY. Build proceeds one checkpoint/item at a time; stop + wait
> for "go" at each. Working tree is uncommitted.**
> This document is the build-ready, multi-phase plan for Phase O (the 18-item
> visualization audit in `future_phases.md`). All 18 items are **maintainer-approved**
> (2026-06-14). Mockups are built and reviewed: `mockups/phase-o/o01..o18-*.html`
> (generator: `mockups/phase-o/_gen.py`).

## How to read / use this plan

- Phase O is **viz-layer only**: no new computation, no new menu numbers, no DB
  changes. Every item adds a matplotlib viz tab / canvas / interactivity to an
  **existing** panel. The one hard rule is **additivity** — an existing render must
  be byte-identical when a new feature isn't engaged, and every shared-helper change
  must keep current callers working with no signature break.
- Work is split into **one shared-foundations sub-phase (O-1)** plus **seven feature
  sub-phases (O-2 … O-8)**, grouped by host-panel family and shared canvas code.
- **Each item is independently shippable and independently removable.** The
  **Master Tracking Matrix** below is the single source of truth for status; every
  item carries an **Isolation & clean-removal** note so any one can be dropped later
  without touching the others. Update the matrix as items land.
- Per-item gate (from the spec): an item is **Done** when (1) its mockup is approved
  [already true], (2) its `prepare_*` unit test is green, (3) the viz tab appears
  only when its data qualifies, (4) the host panel's pre-existing tabs/output are
  unchanged, and (5) — for shared-helper changes — existing callers still pass.

### Star-map diagrams — model them on opts 18/19 "Star Chart" / "Star Chart 3D" (binding)

> **Maintainer preference (2026-06-14):** the opt-18/19 **"Star Chart" / "Star Chart 3D"**
> look & functionality is explicitly **preferred over** the older light-gray
> "Map X–Y / X–Z / 3D" scatter (`make_star_map_canvas`). New Phase-O map features use
> the Star Chart style; the O-3 interactivity items prioritise the Star Chart tabs.

Any Phase-O diagram that plots **stars in 3D space** must be modelled on the existing
dark-navy **"Star Chart"** + **"Star Chart 3D"** canvases that opts **18/19** already
ship (`make_star_chart_canvas` / `make_star_chart_3d_canvas` in
`gui/visualizations/plot_helpers.py`) — **reuse/extend those helpers; do not invent a
new map style.** Concretely:
- **Provide both a 2D "Star Chart" tab and a 3D "Star Chart 3D" tab** (the opt-18/19 tab
  pair + naming), not a single flat "Map".
- Dark-navy palette (fig `#070b18` / plot `#0b1020`), concentric **distance rings**
  scaled to the view, gold **★ centre** marker at the origin, spectral-class-coloured
  dots, `"Name (Z=±X.XXX)"` labels with the existing **zoom-driven label decluttering**
  (labels appear once the visible half-range drops below ~15 ly).
- The full interaction model those canvases already have: **hover tooltip**, **click
  info box**, **scroll-wheel zoom**, **Home reset**, and (3D) the **Top / Side / 3D
  Perspective** preset buttons + `azel` drag-rotate.
- This is exactly the surface Phase I's `routes=` overlay plugs into, so star-map items
  are **panel wiring over the existing canvases**, not new drawing code.

**Applies to:** O8 (new Star Chart + Star Chart 3D tabs on opts 17/20/21) and the O-3
work, which operates directly on opts 18/19's Star Chart / Star Chart 3D canvases. **O1
(night sky)** borrows the same palette + interaction model but uses a **celestial-sphere
projection** (RA/Dec, no distance rings), so it matches the *look and feel* without the
spatial layout. **Out of scope** (these keep their own purpose-built canvases): the HR
diagram, mass–radius, orbital/system diagrams, region rings, Toomre scatter,
brachistochrone profiles, HWC temp/ESI, transit geometry, and the size strip.

## Status legend

`☐ Planned` · `◐ In progress` · `☑ Done` · `✗ Dropped` (record the date + reason when set).

---

## Master Tracking Matrix

| ID | Item | Sub-phase | Host options / panels | Depends on | New `prepare_*` | New / extended canvas | Status |
|----|------|-----------|------------------------|------------|------------------|------------------------|--------|
| F1 | Opts 18/19 row extension (`app_magnitude`, `parsecs`) | O-1 | core/calculators.py | — | — | — | ☑ Done (2026-06-14) |
| F2 | Help-dialog component (info button → dialog) | O-1 | gui (shared) | — | — | — | ☑ Done (2026-06-14) |
| F3 | Test scaffold `tests/test_viz_phase_o.py` + offscreen smoke harness | O-1 | tests | — | — | — | ☑ Done (2026-06-14) |
| O1 | Night Sky From Another Star (+ from Sol) | O-2 | 18, 19 | F1 | `prepare_sky_from_star` | `make_sky_canvas` (new) | ☑ Done (2026-06-14) |
| O2 | HR / Colour–Magnitude Diagram | O-2 | 12, 18, 19 | F1 | `prepare_hr_main_sequence`, `prepare_hr_from_stars` | `make_hr_canvas` (new) | ☑ Done (2026-06-14) |
| O15 | Table-Row ↔ Map Linking | O-3 | 18, 19 | — (introduces capability layer) | — | star-map/chart: `highlight_star`, `on_star_click` | ☑ Done (CP1, 2026-06-15) |
| O16 | Clickable Legend Filtering | O-3 | 18, 19 | O-3 capability layer | — | star-map/chart: per-class collections + legend pick | ☑ Done (CP2/CP3, 2026-06-16) |
| O17 | Travel-Time Isochrone Rings | O-3 | 18, 19 | O-3 capability layer | — | star-chart: `isochrone=` param | ☑ Done (CP4, 2026-06-16) |
| O18 | Find-Star-on-Map Box | O-3 | 18, 19 | **O15** (`highlight_star`) | — | — (reuses O15) | ☑ Done (CP5, 2026-06-16) |
| O3 | Mass–Radius Diagram | O-4 | 3, 6, Map panel | — | `prepare_mass_radius` | `make_mass_radius_canvas` (new) | ☑ Done (2026-06-17) |
| O4 | Solar System Reference Overlay | O-4 | 3, 6, Map panel | — | — | `make_orbits_canvas` (extend: `solar_overlay`) | ☑ Done (2026-06-17) |
| O13 | Transit Geometry View | O-4 | 3, Map panel | — | `prepare_transit_geometry` | `make_transit_canvas` (new) | ☑ Done (2026-06-17) |
| O14 | Planet Size-Comparison Strip | O-4 | 3, 6, Map panel | — | — | `make_size_comparison_canvas` (new) | ☑ Done (2026-06-17) |
| O9 | Brachistochrone Profile Charts | O-5 | 22, 23, 24, 29, 30 | — | `prepare_brachistochrone_profiles` | `make_profile_canvas` (new) | ☑ Done (2026-06-18) |
| O5 | Date Scrubber / Orbital Animation | O-5 | Map panel, 22, 23 | — (reuses `prepare_exoplanet_system_diagram`; O5b adds `compute_solar_ephemeris_track`) | — | panel-side slider/timer + `set_offsets`; `make_exoplanet_system_canvas`/`make_solar_travel_canvas` expose additive `_scrub` handles | ☑ Done (2026-06-18) |
| O8 | Two-Star Map (Distance / Travel-Time) | O-5 | 17, 20, 21 | Phase I `routes=` (already shipped) | — | reuse `make_star_chart_canvas`/`_3d` — "Star Chart" + "Star Chart 3D" tabs (`routes=`) | ☑ Done (2026-06-18) |
| O6 | Diagram Parity for Sol Regions | O-6 | 13 | — (reuses ring prep) | — | reuse existing ring canvases | ☑ Done (2026-06-18) |
| O7 | Solar System Orbital Diagrams | O-6 | 11 | — | `prepare_solar_system_orbits` | reuse `make_orbits_canvas` (+ additive `title`/`km_axis` kwargs) | ☑ Done (2026-06-18) |
| O10 | Honorverse Visualization (bar + ring) | O-6 | 14 (bar); 8, 9, **13** (System Regions ring, opt-in checkbox); **3, 6, Map** (Orbital Diagram ring, opt-in checkbox) | — | `prepare_hyper_limits`; `prepare_system_regions_diagram` adds `hyper_limit` key; `compute_sol_regions` sets `spectral_type="G2V"`; `science.compute_hyper_limit_for_spectral_type` | `make_hyper_bar_canvas` (new); `make_system_regions_canvas(show_hyper=)` + `wrap_system_regions_with_hyper_toggle` (new); `make_orbits_canvas(hyper_au=)` + `wrap_orbits_with_solar_toggle(hyper_au=)` | ☑ Done (2026-06-18) |
| O11 | Toomre / Galactic Kinematics + Explain dialog | O-7 | 1, 3, 4, 5, 6, 8 | **F2** (help dialog) | `prepare_toomre` | `make_toomre_canvas` + `make_kinematics_tab` (new) | ☑ Done (2026-06-18) |
| O12 | HWC Habitability Visuals | O-8 | 6 | — | `prepare_hwc_temps`, `prepare_hwc_esi` | `make_hwc_temp_canvas`, `make_hwc_esi_canvas` (new) | ☑ Done (2026-06-18) |

**Note on O8 (corrected 2026-06-14):** O8 **is** a real build item. Opts 17/20/21
(`DistanceBetweenStarsPanel`, the two `TravelTimeStars*` panels) render **text-only
today** — no map tab exists. O8 needs **no new core or canvas code**, however: the
`routes=` overlay on `make_star_chart_canvas`/`_3d` already exists (built by Phase I).
O8 is therefore **panel wiring only** — add `DiagramToggleMixin` + a "Map" tab that
converts the two endpoints to nodes and passes one `routes=` edge. Placed in O-5.

### Dependency graph (the only ordering constraints)

```
F1 ──► O1, O2            (row-key extension feeds Night Sky + HR overlay)
F2 ──► O11               (help-dialog feeds the Toomre Explain button)
O-3 capability layer ──► O15, O16, O17
O15 (highlight_star) ──► O18
(everything else is independent)
```

Recommended build order: **O-1 first** (unblocks O-2 and O-7), then any feature
sub-phase. Within **O-3**, build the capability layer → O15 → O16/O17 → O18.

---

## O-1 · Shared Foundations  *(build first; small)*

Three build-once pieces consumed by later sub-phases. Each is additive and reversible.

### F1 — Opts 18/19 result-row extension  *(consumed by O1, O2b)*
- **`core/calculators.py`** — in `compute_stars_within_distance_of_sol` and
  `compute_stars_within_distance_of_star`, add two **additive** keys per result row:
  `app_magnitude` (from the `star_systems.app_magnitude` column) and `parsecs`
  (`1000/parallax`, or the stored value). Existing keys and ordering are unchanged.
- **Tests** (`tests/test_route_planning.py` already seeds a tmp `star_systems`; add a
  small case to `test_viz_phase_o.py`): assert both keys are present and numeric on a
  seeded row, and that the **rest of the row dict is unchanged** (additive only).
- **Isolation & removal:** delete the two key assignments; nothing else reads them
  unless O1/O2 shipped. If O1 & O2 are both dropped, remove F1.

### F2 — Help-dialog component  *(consumed by O11; reusable)*
- **`gui/help.py`** (new, tiny) — `show_help_dialog(parent, title: str, html: str)`
  opens a non-modal `QDialog` with a scrollable `QTextBrowser` (rich text) + Close
  button; and `info_button(title, html, parent=None) -> QPushButton` ("ℹ What is
  this?") wired to it. Pure presentation, no core/DB.
- The O11 explanation text lives as a module constant `TOOMRE_HELP_HTML` in
  `gui/help_text.py` (so text edits don't touch logic). Content = the
  `o11-toomre-kinematics.html` dialog body (what / axes / rings + population table /
  marker / heuristic caveat).
- **Tests:** offscreen (`QT_QPA_PLATFORM=offscreen`) smoke — `info_button(...)`
  builds, clicking calls `show_help_dialog` without error; no pixel test.
- **Isolation & removal:** delete `gui/help.py` + `gui/help_text.py` and the O11
  button wiring. Self-contained.

### F3 — Test scaffold + smoke harness
- **`tests/test_viz_phase_o.py`** (new) — the home for every Phase-O `prepare_*`
  unit test (offline, pure transforms, `{"error"}`/`skipped`-count paths) plus a
  shared **offscreen smoke helper** `build_canvas_ok(make_fn, data)` that asserts a
  canvas builds without raising under `QT_QPA_PLATFORM=offscreen` (guarded by
  `mpl_available()` / PySide6 import; skipped when absent — same stance as Phases E/I).
- **Additivity-regression guard:** a test that calls each **extended** shared canvas
  (`make_star_chart_canvas`, `make_star_map_canvas`, `make_orbits_canvas`, …) with
  **no** new kwargs and asserts it still builds — protects opts 18/19 / GCNS / Phase-I
  callers from signature breaks.
- **Isolation & removal:** the file is purely additive; delete cases alongside their
  items.

---

### O-1 gate — Validation · Tests · Success
- **Validation:** F1 is additive (existing opts-18/19 rows otherwise byte-identical); F2/F3 are new files touching no existing code.
- **Tests:** F1 additive-keys test; F2 offscreen button-builds-and-opens smoke; F3 ships the offscreen `build_canvas_ok` helper **and** the additivity-regression guard (calls every shared `make_star_*`/`make_orbits_canvas` with no new kwargs).
- **Done when:** F1 keys present + numeric with the rest of each row unchanged; F2 dialog opens; F3's regression guard is green for all current shared-canvas callers.

## O-2 · Star-Map Data Products  *(opts 12, 18, 19 — depends on F1)*
Mockups: `o01-night-sky.html`, `o02-hr-diagram.html`

### O1 — Night Sky From Another Star  *(opts 18 & 19 — implemented)*
> **Extended (2026-06-14):** also added to **opt 18** — the Sol-centric result has no
> `center`, so the vantage defaults to **Sol at the origin** (Sol itself is not drawn,
> since it isn't a night-sky star from Sol). Same canvas/control; one shared
> `_add_night_sky_tab` builder serves both panels.
- **`core/viz.py`** `prepare_sky_from_star(result, mag_limit=6.5) -> dict`:
  per star, vector `v=(x,y,z)` from the vantage; `ra_deg=degrees(atan2(y,x))%360`;
  `dec_deg=degrees(asin(z/|v|))`; abs mag from the Sol-centric values, then
  `m' = M − 5 + 5·log₁₀(d_ly/3.26156)`; filter `m' ≤ mag_limit`. **Sol appended**
  pointing back (`-center_xyz`, `M_V=4.83`). NULL-magnitude stars → `skipped_no_mag`
  (counted, never fabricated). Returns
  `{vantage_name, mag_limit, skipped_no_mag, stars:[{name,ra_deg,dec_deg,mag,sp_class,color}]}`
  or `{"error"}`.
- **`gui/visualizations/plot_helpers.py`** `make_sky_canvas(parent, data)` — Aitoff
  (or rectangular RA/Dec fallback — decide from the mockup), marker size by brightness,
  spectral-class colour, **the Star-Chart dark-navy palette + interaction model**
  (hover tooltip, click info; per the convention) — but a **celestial-sphere projection**
  (RA/Dec, no distance rings / gold-centre / 3D companion), so it matches the look & feel
  of the opt-18/19 charts without their spatial layout. `skipped_no_mag` footnote.
- **GUI:** opts **18 & 19** gain a **"Night Sky"** viz tab (shared `_add_night_sky_tab`)
  with a mag-limit `QLineEdit` (default 6.5) + Apply that re-runs `prepare_sky_from_star`
  on the **cached** result (no new query). Caveat: only stars within the queried distance
  limit appear — a larger limit gives a fuller sky.
- **Tests:** a star at a known offset → its `ra_deg`/`dec_deg`/`mag`; a NULL-mag star
  lands in `skipped_no_mag`; empty/`{"error"}` path. Canvas smoke.
- **Isolation & removal:** delete `prepare_sky_from_star` + `make_sky_canvas` + the
  opt-19 tab wiring + tests. (F1 only needed if O2 also dropped.)

### O2 — HR / Colour–Magnitude Diagram  *(opts 12, 18, 19)*
- **O2a** `prepare_hr_main_sequence() -> {points:[{label,teff,abs_mag,bv,lum,color}]}`
  from `main_sequence_stars`; `{"error"}` when empty.
- **O2b** `prepare_hr_from_stars(result) -> dict` — per result star
  `M_V = app_magnitude + 5 − 5·log₁₀(parsecs)` (**needs F1**) + Teff via the canonical
  `_lookup_spectral_type` ceiling rule; missing mag / non-OBAFGKM class → skipped+counted.
- **`make_hr_canvas(parent, data, overlay_points=None)`** — x = Teff (log, inverted,
  hot left), y = abs visual mag (inverted, bright top), MS line + labelled points
  (label every other), secondary top axis of spectral-class letters; result stars as
  `overlay_points` scatter.
- **GUI:** `MainSequencePanel` (12) → `DiagramToggleMixin` + **"HR Diagram"** tab;
  opts 18/19 add the same canvas with their result stars overlaid.
- **Tests:** 24-ish MS points + colour-by-class; O2b `M_V` formula at a sample, skip
  counts; canvas smoke (with & without overlay).
- **Isolation & removal:** delete both `prepare_hr_*` + `make_hr_canvas` + the three
  panels' tab wiring + tests. *(Note: GCNS BP−RP CMD is a Phase-M extension, out of scope.)*

---

### O-2 gate — Validation · Tests · Success
- **Validation:** both viz tabs are additive (appear only with qualifying data) and reuse F1's keys; no `core/` numeric output moves.
- **Tests:** `prepare_sky_from_star` (offset → ra/dec/m'; NULL-mag → `skipped_no_mag`; `{error}`); `prepare_hr_main_sequence` (24 pts, colour-by-class) + `prepare_hr_from_stars` (M_V anchor, skip counts); canvas smokes.
- **Done when:** the Night Sky tab (19) and HR tab (12/18/19) appear only when data qualifies, and host renders are byte-identical when absent.

## O-3 · Star-Chart Interactivity  *(opts 18, 19 — highest cross-cutting risk)*
Mockups: `o15-table-map-link.html`, `o16-legend-filter.html`, `o17-isochrone-rings.html`, `o18-find-star.html`

**Capability layer (build first within O-3, additive, backward-compatible).** Extend
the four shared canvases — `make_star_map_canvas`, `make_star_map_3d_canvas`,
`make_star_chart_canvas`, `make_star_chart_3d_canvas` — so existing opts-18/19 / GCNS /
Phase-I callers are unaffected (covered by F3's regression guard):
- `canvas.highlight_star(name|None)` **attribute** (no signature change) — a hollow
  gold ring at the named star, or removed for `None`; `draw_idle()`. Pure overlay —
  additive for every caller.
- optional `on_star_click(name)` kwarg (default `None` → current inline info box).
- **Opt-in per-class split (decision 2026-06-15) — the one risky edit, neutralised.**
  O16 needs per-spectral-class `PathCollection`s so a class can be hidden, but that
  rewrites the *base* dot-drawing on canvases GCNS (M1/M4c) and the seven Phase-I panels
  also call. Today `make_star_map_canvas` draws **all stars in one `ax.scatter`** (the
  single `sc` that hover/click hang off) with a proxy-`Patch` legend; splitting that into
  N per-class scatters is exactly what would silently regress a foreign panel — and the
  suite has **no pixel tests** to catch it. So gate the split behind a default-off
  `legend_filter=False` kwarg: `False` runs today's exact single-`ax.scatter` path →
  **GCNS/Phase-I are byte-identical by construction** (they never enter the new branch);
  only opts 18/19 pass `legend_filter=True` to take the per-class branch (one scatter per
  class + `legend_handle.set_picker(5)`). The hover/click/`highlight_star` logic must
  handle both "one collection" and "list of collections". Cost: a second branch in each
  helper — cleanly removable (drop O16 → delete the branch; the default path *is* the
  original).
- `isochrone={"ly_hr":float,"label_unit":str}|None` kwarg on the two chart canvases
  (O17) — pure overlay, default `None` → distance rings as today.

**Structural-regression test (improvement, 2026-06-15) — partial cover for the
no-pixel-test gap.** F3's guard proves the canvases *build*; it does **not** prove they
*render identically*. Add a structural-snapshot test to `tests/test_viz_phase_o.py`:
build each of the four shared canvases the **default way** (no O-3 kwargs,
`legend_filter=False`) and assert a set of structural invariants is unchanged — axes
count, `PathCollection`/`Line2D` counts, the scatter's face-colours, axis limits, ring
count, legend-entry count. This catches the *single-scatter-vs-split* class of bug (and
any accidental z-order / colour drift) on the **foreign-caller default path**, which F3
alone cannot. The opt-18/19 `legend_filter=True` path is allowed to differ (change is
expected there). Runs at CP0 and stays green through CP2/CP3. The fixture **must
include the edge rows** that exercise the classifier — a composite `+`-type (`G2V+K1V`),
a `dM`-prefixed dwarf (`dM6`), a null/empty `sp_type`, the white dwarf (`DA1.9`), and two
coincident-coordinate stars — or a grouping regression would slip through clean G/K/M
data.

**Scope decision (maintainer, 2026-06-14): the interactivity covers ALL opts-18/19 map
tabs** — the light-gray **Map X–Y / X–Z / 3D** (`make_star_map_canvas`/`_3d`) *and* the
dark **Star Chart / Star Chart 3D** (`make_star_chart_canvas`/`_3d`) — not just the Star
Charts. **Exception:** O17 isochrones replace *distance rings*, which only the Star Chart
canvases draw; the plain Map tabs have no ring system, so O17 stays on the Star Charts
(adding rings to the scatter Maps is out of scope). **Build order for the 3D-capable
items (O16): all 2D variants first, then the 3D variants** (3D visibility toggling is
fiddlier — best-effort).

### O-3 risk-mitigation strategy & checkpoints  *(decision 2026-06-15)*

The O-3 risk is concentrated in the **capability-layer edits to the four shared
canvases**, which three families call: opts 18/19 (being edited), **GCNS M1/M4c**, and
**all seven Phase-I route planners** (unedited — must stay identical). Mitigations:
(1) build + test the capability layer in isolation **before** any panel wiring;
(2) default-off additivity on every new kwarg/attribute; (3) the **opt-in per-class
split** above (foreign-caller regression structurally impossible); (4) **2D before 3D,
one canvas at a time**, F3 guard after each; (5) per-item clean-removal notes.

Because canvas *rendering* has no automated coverage anywhere in the suite, each step
ends at a **checkpoint**: I run the automated gate, report what landed, and give the
exact click-path + values below — then **stop until you say continue**. **CP0 and CP2
matter most** — they're where a foreign-panel regression could hide.

**Prerequisites for the manual checks:** `star_systems` populated (**option 50**) and
GCNS imported (**option 58**) so the regression-sweep panels have data. All values below
are from the **current build** (`stars-within-sol --ly 15` → **53 stars**). Useful
ground-truth rows (the table shows the SIMBAD `main_id`, *not* the common name):

| What you'll look for | Row name as stored | Class | Dist (ly) |
|---|---|---|---|
| Proxima Centauri | `NAME Proxima Centauri` | M5.5Ve → **M** | 4.2 |
| α Cen A | `* alf Cen A` | G2V → **G** | 4.4 |
| α Cen B | `* alf Cen B` | K1V → **K** | 4.4 |
| Barnard's Star | `NAME Barnard's star` | M4V → **M** | 6.0 |
| Sirius A | `* alf CMa` | A0… → **A** (the only A at 15 ly) | 8.6 |
| Sirius B | `* alf CMa B` | DA1.9 → **D** (white dwarf) | 8.6 |
| ε Eridani | `* eps Eri` | K2V → **K** | 10.5 |
| 61 Cyg A / B | `*  61 Cyg A` / `*  61 Cyg B` | K5V / K7V → **K** | 11.4 |

Class mix at 15 ly: **M dominates** (toggling M removes most dots — a very visible
legend-filter effect); **G** = α Cen A; **K** = α Cen B / ε Eri / 61 Cyg A&B; **A** =
Sirius A alone; plus exotic singletons (**L** Luhman 16, **Y** WISEA J0855, **D** Sirius B).

| CP | After | Automated gate (I run) | Manual verify — concrete inputs & expected result | Regression sweep |
|----|-------|------------------------|----------------------------------------------------|------------------|
| **CP0** | Capability layer | full suite + F3 guard + new structural-regression test green | **Opt 18, limit `15`** → open all five map tabs (Map X–Y, Map X–Z, Map 3D, Star Chart, Star Chart 3D); every dot / label / distance ring / legend looks exactly as before (nothing is wired yet) | **GCNS Census Browser `15`** (M1) **and** **Nearest-Neighbor: start `Sol`, hops `6`, max-ly `9`** (Phase-I): Star Chart dots, distance rings, and the route line all unchanged |
| **CP1** | O15 linking | capability smoke + panel-wiring smoke | **Opt 18, limit `15`** → select the **`NAME Barnard's star`** row → a gold ring appears on Barnard's on **every** map tab; click the **`NAME Proxima Centauri`** dot on any map → its row selects + scrolls into view; switch Star Chart → Map 3D → selection + ring persist. **Edge:** click an **overlapping** dot (`* alf Cen` / `A` / `B`, all ~4.4 ly) → selection is deterministic, no crash | — (no foreign-panel change since CP0) |
| **CP2** | O16 2D filter | per-class pick-toggle smoke + structural test still green | **Opt 18, limit `15`** on Star Chart + Map X–Y + Map X–Z: click the **M** legend entry → most dots vanish, "Class M" text dims to ~0.3 α; click again → they return; click **G** → only `* alf Cen A` drops; click **A** → only `* alf CMa` (Sirius A) drops. **Edge:** click **D** → Sirius B **and** Wolf 359 + Ross 128 drop together (`dM`→D bucket — expected, not a bug); hover where a hidden dot was → **no** tooltip | **Re-open GCNS Census `15` + the Nearest-Neighbor route**: both still draw **all** classes (they pass `legend_filter=False`) — no filtering, no visual change |
| **CP3** | O16 3D filter | 3D pick smoke (best-effort) | **Opt 18, limit `15`** on Map 3D + Star Chart 3D: toggling **M** hides/shows its dots (labels follow); rotate to confirm hidden dots stay hidden | same GCNS / Phase-I sweep as CP2 |
| **CP4** | O17 isochrones | `isochrone=` branch smoke | **Opt 18, limit `15`**, Star Chart: enter **`10` ×c**, Apply → distance rings replaced by time rings. **Hand anchor:** at N×c, ring radius (ly) = N × time (yr) → a **"6 months" ring sits at 5 ly** and a **"1 year" ring at 10 ly**. Then **`0.01` ly/hr** → weekly/monthly rings (**1 month ≈ 7.3 ly**, 1 week ≈ 1.68 ly). Clear the field → distance rings return. **Edge:** highlight a star first (per CP1), then Apply velocity → the gold ring **survives** the rebuild; zoom in, then clear → distance rings redraw correctly anchored | GCNS / Phase-I Star Charts still show plain **distance** rings (no isochrone control exists there) |
| **CP5** | O18 find box | panel smoke | **Opt 18, limit `15`**: type **`Barnard`** → 1 match, map centres + rings Barnard's Star, "1 of 1"; type **`61 Cyg`** → 2 matches (A & B), "1 of 2", Find-again cycles; type **`GJ`** → many matches, cycles through them; type **`zzzzz`** → no match → status-bar message | — |

> **Opt 19 variant** (network — SIMBAD-resolves the centre): same checks with e.g. centre
> **`Sirius`**, limit **`9`** (gold ★ = Sirius at origin; α CMa B + Procyon nearby). Run it
> once per CP to confirm the centre-star path behaves like the Sol-centric opt-18 path.

### O-3 edge cases, decisions & targeted unit tests  *(2026-06-15)*

Hardening list beyond the happy-path checkpoints — most fall out of the **real**
`star_systems` data (the 15-ly pull) and won't appear with clean G/K/M fixtures.

**Data-derived gotchas (all real at 15 ly):**
- **Heterogeneous "Class D".** `_star_map_color` (`core/calculators.py`) *and* the legend
  both classify on `sp_type[0].upper()`, so the old Yerkes **`dM6` (Wolf 359) / `dM4`
  (Ross 128)** are bucketed as **D** with the white-dwarf colour, alongside Sirius B
  **`DA1.9`**. O16 must **reproduce** this (group by the same key → additive); "correcting"
  it would break additivity. **Decision: reproduce, don't fix.** CP2 expects toggling **D**
  to hide Sirius B + Wolf 359 + Ross 128 together.
- **Double-space stored names** (`*  61 Cyg A`, `Wolf  359`, `HD  95735`, `Ross  248`).
  O18 find must **collapse whitespace** on both query and target, else `61 Cyg A` (single
  space) misses `*  61 Cyg A`. **Decision: normalize whitespace + case-insensitive, match
  name OR designations.**
- **Coincident points** — `* alf Cen` (composite `G2V+K1V`, empty designations) + `* alf
  Cen A` + `* alf Cen B`, plus Sirius A/B and the G 272-61 triple, share a position.
  Hit-test returns the first index **deterministically**; **find `alf Cen` → 3 matches →
  must cycle**; highlight rings the matched name only.
- **Null/empty `sp_type` → class `"?"`** has no legend entry → **unfilterable, always
  visible** (decision: by design). **Null `x/y/z`** rows have a table row but no map point
  → highlight/find/link **no-op gracefully** (same path as a clipped star).
- **Clipped-from-2D stars.** The Star Chart excludes stars whose |x| or |y| exceeds the
  limit (projection-square rule) though they exist in 3D → highlight/find **no-op on the
  tab where the star isn't drawn**, still work on the others. The **center ★** (Sol /
  queried star) is a separate artist → excluded from filtering, never selects a phantom row.

**Behavior decisions to lock (so the build isn't ambiguous):**
- Highlight **survives a canvas rebuild** (O17 velocity-Apply / O1 mag-limit-Apply re-run
  prep) — re-apply the ring after rebuild, don't drop it.
- **Filter state resets on rebuild** (simplest; document it) — re-toggling is cheap.
- **Find into a hidden class** → un-hide that class, then center + ring (never center on an
  invisible dot).
- **Multi-row drag-select** → highlight the **last** selected row only.

**Targeted offline unit tests (add to `tests/test_viz_phase_o.py`):**
- **Class-grouping key:** `dM6`/`dM4` → `"D"` (same bucket as `DA1.9`); composite `G2V+K1V`
  → `"G"`; null/empty → `"?"` (asserts O16 groups exactly as the legend/colour).
- **Whitespace-normalized find:** `61 Cyg A` matches `*  61 Cyg A`; case-insensitive;
  designation hit (`GJ 699` → Barnard's); empty query → no match; no-match → no stale
  highlight.
- **Isochrone ring math:** `10×c` and `0.0011408 ly/hr` give **identical** radii (the
  8765.8128 factor); the 1-yr ring = N ly at N×c; zero/negative/non-numeric → validation,
  no rings.
- **Hidden-collection hit-test guard:** hover/click logic skips a collection with
  `get_visible() is False` (don't pop a hidden star's tooltip).
- **Clipped / null-coord highlight no-op:** returns cleanly (no exception, no ring) on the
  tab lacking that point.
- **Large-N structural/perf smoke:** a ~2000-node canvas (Phase-I `legend_filter=False`)
  builds without error and holds the structural invariants — guards the shared-canvas
  callers at scale.

### O15 — Table-Row ↔ Map Linking  *(all 5 map tabs)*
Panels keep refs to **every** created canvas — Map X–Y, Map X–Z, Map 3D, Star Chart,
Star Chart 3D. Result `QTableView` `selectionChanged` → `highlight_star(name)` on every
canvas; clicking a star on any map (via `on_star_click`) selects + scrolls the matching
row. Selection survives switching viz tabs.
- **Tests:** capability-layer smoke (`highlight_star` callable on all four canvas types,
  `on_star_click` honored); no `prepare_*`. **Removal:** revert the canvas attribute/kwarg
  additions + panel wiring (O16/O17/O18 must be dropped first or de-coupled — they reuse
  the layer).

### O16 — Clickable Legend Filtering  *(all map tabs w/ a spectral legend; 2D then 3D)*
Per-class `PathCollection`s + `pick_event` toggles a class's visibility on **Map X–Y,
Map X–Z, Map 3D, Star Chart, Star Chart 3D**; legend text → alpha 0.3 when hidden;
per-star labels follow visibility. **Implement the 2D variants (Map X–Y/X–Z, Star Chart)
first, then the 3D variants (Map 3D, Star Chart 3D).** **Removal:** revert the per-class
drawing + pick handler.

### O17 — Travel-Time Isochrone Rings  *(Star Chart 2D + 3D only — they own the rings)*
Velocity input + unit (LY/HR | ×c) + Apply on the **Star Chart / Star Chart 3D** tabs;
rings at `d = v_lyhr × t` for nice steps (week…50 yr, 3–6 fit), labelled
`"6 months @ 0.01 ly/hr"`; clearing restores distance rings; conversion via `8765.8128`.
The plain **Map X–Y/X–Z/3D** tabs draw no distance rings, so isochrones are **N/A**
there. **Removal:** revert the `isochrone=` branch + panel control.

### O18 — Find-Star-on-Map Box  *(depends on O15; works on all map tabs)*
Substring match on name + designations; on match centre the active map at half-range
`min(current,15)` ly + `highlight_star(name)` (the shared layer rings it on every
canvas); `"1 of N matches"` with Find-again cycling; no match → status-bar message.
**Removal:** delete the find control/handler (leaves O15 intact).

---

### O-3 gate — Validation · Tests · Success
- **Validation:** the capability-layer additions are backward-compatible (F3 guard); features operate on the opt-18/19 **Star Chart / Star Chart 3D** canvases per the binding convention; selection/highlight survive viz-tab switches.
- **Tests:** capability smoke (`highlight_star` callable, `on_star_click` honoured, per-class collections, `isochrone=` branch); O18 reuses O15's `highlight_star`.
- **Done when:** row↔map linking (both ways) and legend filtering work on **all five** opts-18/19 map tabs (2D variants first, then 3D), isochrone rings work on the Star Chart 2D + 3D, find + cycle works, and opts 18/19 + GCNS + Phase-I callers still pass (F3 guard green).

## O-4 · Planet & System Diagrams  *(opts 3, 6, Map panel)*
Mockups: `o03-mass-radius.html`, `o04-solar-overlay.html`, `o13-transit-geometry.html`, `o14-size-strip.html`

### O3 — Mass–Radius Diagram
`prepare_mass_radius(planets, mass_key, radius_key, name_key) -> {planets:[{name,mass_e,radius_e}],skipped}`
(generic over NASA `pl_bmasse/pl_rade` + HWC `P_MASS/P_RADIUS`; `{"error"}` when none
qualify). `make_mass_radius_canvas` — log–log, constant-density curves
(`R=(M/(ρ/ρ⊕))^(1/3)`, ρ⊕=5.51: iron 7.9 / rock 5.51 / water 1.0 / Jupiter 1.33,
labelled "constant density"), 8 Solar-System reference points, system planets. Tab on
opts 3/6/Map when ≥1 planet qualifies. **Test:** filters null-radius + `skipped` count;
density-curve anchor (Earth M,R on the rock curve). **Removal:** delete fn+canvas+tabs.

### O4 — Solar System Reference Overlay
Extend `make_orbits_canvas(..., solar_overlay=False)` — dashed grey circles at
`_PLANET_SMAS` (`core/viz.py:354`) for planets with SMA ≤ max_au×1.1, end-of-orbit
labels. A "Show Solar System reference" `QCheckBox` rebuilds the canvas; default
unchecked → byte-identical. **Test:** additivity (default off == today); overlay adds
circles. **Removal:** drop the param + checkbox.

### O13 — Transit Geometry View
`prepare_transit_geometry(planets) -> {star_radius_au, planets:[{name,a_au,incl_deg,b}], skipped}`
— needs `st_rad` + per-planet `pl_orbsmax`/`pl_orbincl`; `b=(a/R★)·cos i`,
`R★=st_rad×0.00465 AU`; `{"error"}` when `st_rad` / all incl missing. `make_transit_canvas`
— stellar disk left, planets at `(log a, b)`, band `|b|≤1` shaded "transiting";
caveat "geometry from i only; node unknown". Tab on opt 3 + Map when ≥1 qualifies.
**Test:** `b` formula anchor; skip list. **Removal:** delete fn+canvas+tabs.

### O14 — Planet Size-Comparison Strip
`make_size_comparison_canvas(parent, planets, radius_key, name_key)` — to-scale circles,
gray Earth (1 R⊕) + Jupiter (11.21 R⊕) anchors, system planets labelled; radius-less
planets in a footnote. No `prepare_*`. Tab on opts 3/6/Map when ≥1 has a radius.
**Test:** canvas smoke + footnote for missing radius. **Removal:** delete canvas+tabs.

---

### O-4 gate — Validation · Tests · Success
- **Validation:** each tab is additive (only when ≥ 1 planet qualifies); O4 with the overlay off is byte-identical to today.
- **Tests:** `prepare_mass_radius` (null-radius filter + `skipped`, density-curve anchor); O4 additivity; `prepare_transit_geometry` (`b=(a/R★)·cos i`, skip list); size-strip missing-radius footnote; canvas smokes.
- **Done when:** the Mass–Radius / Solar-overlay / Transit / Size tabs appear on opts 3/6/Map only with qualifying planets and add nothing when absent.

## O-5 · Travel & Motion  *(opts 17, 20, 21, 22, 23, 24, 29, 30 + Map panel)*
Mockups: `o09-brachistochrone-profiles.html`, `o05-date-scrubber.html`, `o08-two-star-map.html`

### O9 — Brachistochrone Profile Charts
`prepare_brachistochrone_profiles(result) -> {profiles:[{label,color,t_hours,v_kms,d_au}],accel_g}`
— reconstruct each profile's piecewise `v(t)`/`d(t)` from `accel_g` + total time +
profile type, using the **exact** formulas in `docs/calculators.md` (incl. the opt-24
variants and opt-23 custom-thrust); ~200 samples. `make_profile_canvas` — two stacked
subplots sharing the time axis (velocity km/s + %c; cumulative AU + LM). Tab on 24/29/30,
added to existing tabs of 22/23. **Test:** segment reconstruction matches the doc formulas
at sampled t; colours fixed per index. **Removal:** delete fn+canvas+tabs.

### O5 — Date Scrubber / Orbital Animation
`NasaPlanetarySystemsMapPanel`: a `QSlider` over `[date−span, date+span]`
(span=min(2×longest period, 50 yr)) + date readout + Play/Pause; throttled 50 ms
recompute via the existing offline `prepare_exoplanet_system_diagram`, updating only
`PathCollection.set_offsets` + `draw_idle()` (orbits/star static). `epoch_known=False`
planets stay pinned at periastron (no invented motion). Opts 22/23 Solar System Map:
~~approximate **propagation** along circular reference orbits~~ **superseded
(maintainer decision 2026-06-18): use accurate batch-fetched ephemeris instead.**
Per-frame Horizons is too slow, but a single Horizons **range query per body**
(`epochs` start/stop/step) returns the whole span in one round-trip, so the new
core fn `compute_solar_ephemeris_track(body_ids, start, stop, n_steps)` pre-fetches
each animated body's real ephemeris once (background thread, "Loading ephemeris…")
and the scrubber drives `set_offsets` from the cache — **no per-frame network**.
Animated bodies = origin + destination + in-view reference planets; the dashed
departure travel-line, orbit rings, and the Sun stay static (readout labels it
"trajectory fixed at departure"). **Test:** position at day+0 == the one-shot Search;
`epoch_known=False` pinned (exoplanet map); the range fetch dedups/structures bodies
(mocked Horizons); the scrubber re-offsets markers from a cached track. **Removal:**
delete the slider/timer + `_SolarMapScrubber`/`_SystemMapScrubber` + `compute_solar_ephemeris_track`
+ the canvas `_scrub` handles (one-shot Search unchanged).

### O8 — Two-Star Map (Distance / Travel-Time)  *(opts 17, 20, 21 — reuses Phase I `routes=`)*
- **Current state:** opts 17/20/21 compute both endpoints' 3D positions but render
  **text only** — no map tab exists today (verified: `DistanceBetweenStarsPanel` is a
  plain `ResultPanel`; the `TravelTimeStars*` panels have no diagram tabs).
- **No new core or canvas code** — reuse the existing `make_star_chart_canvas` / `_3d`
  `routes=` parameter (shipped by Phase I; currently wired only to opts 18/19 + Route
  Planning).
- **GUI:** add `DiagramToggleMixin` + **"Star Chart"** and **"Star Chart 3D"** viz tabs
  to each of the three panels — the opt-18/19 tab pair, per the *Star-map diagrams*
  convention above (reuse `make_star_chart_canvas` / `make_star_chart_3d_canvas`, full
  hover/click/scroll-zoom/Home + 3D Top/Side/Perspective presets). The two endpoints
  (+ Sol as a grey reference point when neither endpoint is Sol) are connected by a
  dashed `routes=` edge labelled with the distance in ly (opts 20/21: distance + travel
  time, e.g. `11.4 ly — 4 Months @ 100×c`); centre on the origin star (gold ★). Endpoints
  already return `(name, ra, dec, ly)` from `_lookup_star_for_distance`; convert with the
  same Cartesian math opt 17 uses — no new lookups. Frame to both stars + 15% padding.
- **Tests:** a small node-conversion / edge-label helper test (offline, hand-checkable
  geometry) + canvas smoke (2D + 3D). No new `prepare_*`.
- **Isolation & removal:** drop `DiagramToggleMixin` + the two Star-Chart tabs from the
  three panels; the shared `routes=` capability stays (used elsewhere).

---

### O-5 gate — Validation · Tests · Success
- **Validation:** O9 tab additive; O5 day-0 frame == the one-shot Search, `epoch_known=False` planets stay pinned, opts 22/23 show the "approximate (propagated)" label off-date; O8 reuses Phase-I `routes=` on the Star Chart / 3D canvases (no core/canvas change).
- **Tests:** `prepare_brachistochrone_profiles` segment reconstruction vs `docs/calculators.md`; O5 position@day-0 anchor on the existing prep; O8 node-conversion/edge-label helper + 2D & 3D canvas smoke.
- **Done when:** profile charts render on opts 22–30; the scrubber animates with no new Horizons calls; opts 17/20/21 gain Star Chart + Star Chart 3D tabs.

## O-6 · Region & Reference Diagrams  *(opts 11, 13, 14, 8–10)*
Mockups: `o06-sol-regions-parity.html`, `o07-solar-orbits.html`, `o10-honorverse.html`

### O6 — Diagram Parity for Sol Regions  *(opt 13)*
`SolRegionsPanel` → `DiagramToggleMixin` + the three ring tabs opts 9/10 have, feeding
the `compute_sol_regions()` dict through the existing `prepare_hz_diagram` /
`prepare_system_regions_diagram` / `prepare_alt_hz_diagram`. **Implementation note:**
opt 13 renders at construction (no Run button) — give it a minimal Show-Diagrams flow or
refactor to the render pattern; the seven data tabs must not change. No new core code.
**Test:** the three preps already return valid shapes for the Sol dict (anchor on
`hzil`/`hzol`); canvas smoke. **Removal:** drop the mixin + viz tabs.

### O7 — Solar System Orbital Diagrams  *(opt 11)*
`prepare_solar_system_orbits(kind="planets") -> {orbits, max_au, star_name}` (kind ∈
planets / dwarfs+asteroids / `moons:<planet>`; moon SMA-km → AU via `/1.496e8`;
`hz_zones=[]`). `SolarSystemPanel` → `DiagramToggleMixin` + **"Orbital Diagram —
Planets & Dwarfs"** and **"Moon Systems"** (a `QComboBox` rebuilds per planet; axis in
AU + km). Reuses `make_orbits_canvas`. **Test:** moon-km→AU conversion anchor; orbit
shape. **Removal:** delete fn + the two tabs.

### O10 — Honorverse Visualization  *(opt 14 + opts 8–10)*
- **O10a** `prepare_hyper_limits()` over the `honorverse_hyper` table →
  `make_hyper_bar_canvas` (horizontal bars in LM, 2nd axis AU via `/8.3167`, coloured
  by leading class). `HonorverseHyperPanel` (14) → `DiagramToggleMixin` + **"Hyper
  Limits"** tab.
- **O10b** extend `prepare_system_regions_diagram(d)` — when `d` carries a
  `spectral_type` (opts 8/9; opt 10 manual → omitted), resolve the hyper limit
  (ceiling rule), LM→AU, append `{label:"Honorverse Hyper Limit", au, color:"#cc2222",
  style:"dashed"}`; `make_system_regions_canvas` draws it as a distinct dashed red ring
  (clearly fiction). No match → silently omitted.
- **Test:** O10a bar values; O10b appends the ring only when `spectral_type` present /
  resolvable, omitted otherwise (additivity for opt 10). **Docs:** `docs/science-and-scifi.md`
  + `docs/star-system-regions.md`. **Removal:** delete `prepare_hyper_limits`+canvas+tab
  (O10a) and revert the regions-prep append (O10b) — independent of each other.

---

### O-6 gate — Validation · Tests · Success
- **Validation:** O6 leaves opt-13's seven data tabs unchanged; O7 tabs additive; O10b ring appended only when `spectral_type` resolves (omitted on opt-10 manual); O10a additive.
- **Tests:** O6 — the three existing ring preps return valid shapes for the Sol dict (anchor); O7 moon-km→AU conversion + orbit shape; O10a bar values; O10b ring appended-vs-omitted; canvas smokes.
- **Done when:** opt 13 gains the 3 ring tabs (data tabs intact), opt 11 the orbital tabs, opt 14 the bar, and opts 8/9 the dashed-red hyper ring (opt 10 omitted).

## O-7 · Hypatia Kinematics  *(opts 1, 3–6, 8 — depends on F2)*
Mockup: `o11-toomre-kinematics.html` (includes the Explain dialog)

### O11 — Toomre / Galactic Kinematics Diagram + Explain dialog
- `prepare_toomre(hypatia_result) -> {v, uw:√(U²+W²), disk, star_name}` or `{"error"}`
  when any of U/V/W is null.
- `make_toomre_canvas(parent, data)` — x = V, y = √(U²+W²); dashed constant-total-velocity
  arcs at 50/100/180 km/s; heuristic region labels (thin <50 / thick ≈70–180 / halo
  >180); the star as a gold ★; subtitle = Hypatia's own `disk` class when present.
  *(Open decision: arc-centre frame — heliocentric vs LSR-corrected — settle from what
  Hypatia returns; see Open Decisions.)*
- **Explain dialog (maintainer requirement):** each host panel's **"Kinematics"** tab
  carries an **"ℹ What is this?"** button (F2's `info_button`) opening `TOOMRE_HELP_HTML`
  (the o11 mockup dialog text). Shown in **every** location O11 appears (opts 1, 3–6, 8).
- **GUI:** a **"Kinematics"** viz tab added wherever the Hypatia Abundance Profile tab
  is, shown only when U, V, W are all non-null.
- **Test:** `uw=√(U²+W²)` anchor; `{"error"}` when any null; canvas smoke; F2 button
  builds + opens (offscreen). **Removal:** delete `prepare_toomre`+`make_toomre_canvas`+
  the Kinematics tab + the Explain button; F2 stays if reused elsewhere, else drop with O11.

---

### O-7 gate — Validation · Tests · Success
- **Validation:** the Kinematics tab is additive (only when U/V/W all non-null) and reuses F2's help-dialog; no `core/` numeric change.
- **Tests:** `prepare_toomre` (`uw=√(U²+W²)` anchor; `{error}` when any of U/V/W null); `make_toomre_canvas` smoke; the Explain button builds + opens (offscreen).
- **Done when:** the Kinematics tab + "ℹ What is this?" dialog appear on opts 1/3–6/8 only when kinematics are present, and the arc-frame decision (Open Decision #2) is recorded.

## O-8 · HWC Habitability Visuals  *(opt 6)*
Mockup: `o12-hwc-habitability.html`

### O12 — Temperature Ranges + ESI-vs-Orbit
- `prepare_hwc_temps(planet_rows)` — per planet equilibrium & surface min→max bars
  (filters planets with ≥1 min/max pair); `make_hwc_temp_canvas` draws the bars with a
  marker at the central value + dashed 273 K / 373 K liquid-water band.
- `prepare_hwc_esi(star_row, planet_rows)` — SMA (log if span >10×) vs ESI; HZ shaded
  from `S_HZ_OPT_MIN/MAX` + `S_HZ_CON_MIN/MAX`; points coloured by `P_HABITABLE`;
  `make_hwc_esi_canvas`.
- **GUI:** two `HwcPanel` viz tabs. Per-system only — no overlap with L2's cross-catalog
  ESI ranking table.
- **Test:** temp-bar filter (planet with no min/max excluded); ESI HZ-band extents from
  the star row; canvas smoke. **Removal:** delete both preps + canvases + tabs.

---

### O-8 gate — Validation · Tests · Success
- **Validation:** both tabs additive (only with qualifying planets); per-system only — no overlap with L2's cross-catalog ESI table.
- **Tests:** `prepare_hwc_temps` (planet with no min/max excluded); `prepare_hwc_esi` (HZ-band extents from the star row); canvas smokes.
- **Done when:** the Temperature-Ranges and ESI-vs-Orbit tabs appear on opt 6 only with qualifying data and leave the existing HWC tabs unchanged.

## Global validation, tests & success criteria *(phase-wide rollup over the per-sub-phase gates above)*

**What is unit-tested (offline, `tests/test_viz_phase_o.py`):** every new `core/viz.py`
`prepare_*` — pure transforms with `{"error"}` contracts — asserting output **shape +
a hand-checked anchor** and the empty/missing-data `{"error"}` or `skipped`-count path
(anchors named per item above). Plus F1's additive-keys test.

**What is NOT unit-tested:** the `make_*_canvas` matplotlib rendering (no pixel tests
anywhere in the suite — same stance as Phases E/I). Verified via the **approved per-item
mockup** + an **offscreen smoke instantiation** (`QT_QPA_PLATFORM=offscreen`) that the
panel builds its viz tab without error.

**Success criteria (whole phase):**
- [ ] Every new viz tab is **additive** — appears only when its data qualifies; toggling
      it off (or a panel with no qualifying data) leaves the existing render byte-identical.
- [ ] The shared canvas additions (`highlight_star`, `on_star_click`, per-class
      collections, `isochrone=`, `solar_overlay=`) are backward-compatible — opts 18/19 +
      GCNS + Phase-I callers still pass F3's regression guard / render unchanged.
- [ ] O18 reuses (does not re-implement) O15's `highlight_star`; O1/O2b reuse F1's keys;
      O11 reuses F2's help-dialog; O8 reuses Phase I's `routes=` (no new canvas).
- [ ] No computation changes — no existing `core/` numeric output moves.
- [ ] Each shipped item has an approved mockup + a green `prepare_*` test; **dropped
      items leave no dead code** (verified by the per-item removal note).
- [ ] Whole suite green.

## Per-sub-phase doc updates (do with each sub-phase, not at the end)
- `docs/gui-architecture.md` — new helpers, per-panel viz-tab lists, the
  `highlight_star`/linking pattern, the help-dialog component.
- `docs/calculators.md` — O9 profile tab, O5 scrubber, the F1 row-key additions.
- `docs/star-system-regions.md` — O6, O10b. `docs/science-and-scifi.md` — O7, O10.
- `docs/star-databases.md` — O1/O2/O3/O11/O12/O13/O14 tabs.
- `future_phases.md` — flip Phase O's status note + the Master Matrix rows as items land.

## Open decisions (resolve at implementation, not now)
1. **O1 projection** — Aitoff vs rectangular RA/Dec (hover-math simplicity). Decide from
   the `o01` mockup.
2. *(Resolved 2026-06-18.)* **O11 arc frame** — Hypatia's U/V/W are **heliocentric**
   (Sun-relative, as stored from sources like the Geneva-Copenhagen Survey). `prepare_toomre`
   therefore **LSR-corrects** them by adding the solar motion (Schönrich, Binney & Dehnen 2010:
   `_SOLAR_MOTION_UVW = (11.1, 12.24, 7.25)`) so the constant-total-velocity arcs centre at the
   **LSR origin (0,0)** and the standard thin/thick/halo total-speed thresholds (50/70–180/180
   km/s) read directly. The correction lives in one module constant — set it to `(0,0,0)` to plot
   raw heliocentric velocities if a future Hypatia build is found to already be LSR-frame. The
   canvas footnotes the frame ("V LSR-corrected (Schönrich+ 2010); boundaries heuristic").
3. **O6 render flow** — give opt 13 a minimal Show-Diagrams flow vs. refactor to the
   standard render pattern (data tabs must not change either way).
4. *(Resolved 2026-06-14 — the two-star map for opts 17/20/21 is build item **O8** in
   O-5; those panels are text-only today and get a "Map" tab reusing Phase I's `routes=`.)*

## Deferred tweaks (post-O-3, maintainer-approved 2026-06-15)
- **3D hover tooltip should follow the cursor**, not sit in the fixed upper-right corner.
  Today the 3D canvases place the hover label as a `text2D` at `(0.98, 0.97)` in
  `make_star_map_3d_canvas` / `make_star_chart_3d_canvas` (chosen so it stays put under
  drag-rotation and clears the legend); the 2D canvases anchor it to the star. Direction:
  make the 3D label **follow the mouse pixel position**. Touches the two shared 3D canvases
  (GCNS / Phase-I also call them) → run through the structural guard + a checkpoint.
  **Deferred until after O-3.**
