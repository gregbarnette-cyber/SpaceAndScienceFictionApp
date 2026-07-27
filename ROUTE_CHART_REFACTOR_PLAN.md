# Route-Chart Refactor Plan — converge the 7 Route Planning maps onto the shared builder

**Status: PLANNED, not started (2026-07-27).** Follow-on from
`completed_plans/SPECTRAL_CLASS_PLAN.md`, which deliberately deferred palette unification here.

## 1. The problem

The Route Planning panels render into the **same canvas** as the opt-18/19 star
charts (`make_star_chart_canvas` / `make_star_chart_3d_canvas`), but they get there
by a different path — so they silently lack half the chart's features and use a
different colour palette.

Half the convergence already happened. `gui/panels/route_planning.py` has **two**
tab builders:

| builder | used by | goes through the shared `_build_iso_chart_tab`? |
|---|---|---|
| `add_two_star_chart_tabs` (`:226`) | opts **17 / 20 / 21** (`distance_stars.py:117`, `travel_time_stars.py:146`) | **YES** — full parity |
| `_add_route_chart_tabs` (`:150`) | all **7** Route Planning panels | **NO** — calls the canvas directly |

`add_two_star_chart_tabs` was converted in the Phase O8 rebuild (2026-07-26). The
seven route planners never followed, so today they are missing:

- **O16 per-class legend filter** (`legend_filter=True`)
- **O17 travel-time isochrone control** (velocity field + Apply/Clear)
- **click-info box** (`on_star_click`)
- **O15 row↔map linking** (`_wire_row_map_linking`)
- `label_max_ly` control over the zoom-driven label threshold

They *do* have 3D viewpoint presets, via a private `_route_chart_3d_tab` (`:107`)
that duplicates what `_build_star_chart_3d_tab` (`diagram_tabs.py:309`) already does.

Affected panels (`gui/panels/route_planning.py`): `MultiStopJourneyPanel` (`:273`),
`NearestNeighborPanel` (`:349`), `TradeRoutePlannerPanel` (`:434`),
`OptimalTourPanel` (`:490`), `FarthestFirstPanel` (`:573`), `JumpRoutePanel` (`:661`),
`JumpNetworkPanel` (`:757`) — 8 call sites of `_add_route_chart_tabs`.

## 2. Why it was never converted — one missing parameter

Both canvases **already accept `routes=`** (`plot_helpers.py:1680`, `:2098`) for the
dashed leg overlay. But `_build_iso_chart_tab` (`diagram_tabs.py:439`) and
`_build_star_chart_3d_tab` (`:309`) **do not pass it through**. That is almost
certainly the whole reason route charts stayed on the direct call: the shared builder
could not carry the route overlay.

**So the core of this refactor is a `routes=None` passthrough** — the same additive-seam
pattern used to introduce `routes=` on the canvases in the first place.

## 3. The second palette

`core.calculators._star_map_color` (`:1555`) is a separate dict feeding
`_map_node` (`:1631`, used by all 7 planners) and `route_planning.py:204/216/221`
(the two-star maps for opts 17/20/21). It disagrees with `core.viz._SPECTRAL_COLORS`:

| letter | `_SPECTRAL_COLORS` | `_star_map_color` |
|---|---|---|
| G | `#FFF4EA` | `#fff4c2` |
| M | `#FF8D3F` | `#ff9d6c` |
| D | `#B0C4DE` | `#dfe6ff` |
| default | `#AAAAAA` | `#cccccc` |
| O B A F K | identical | identical |

(`L/T/W/Y/C/N` were absent until the Part 2 additive extension.) So **the same star is
a different colour depending on which panel you opened**, on the same widget.

## 4. Proposed work

**Phase 1 — the seam (no visual change).**
1. Add `routes=None` to `_build_iso_chart_tab` and `_build_star_chart_3d_tab`, passed
   straight to the canvas calls. Purely additive; existing callers unaffected.
2. Convert `_add_route_chart_tabs` to call `_build_iso_chart_tab(..., routes=edges)`
   for 2D and 3D, mirroring `add_two_star_chart_tabs`.
3. Delete `_route_chart_3d_tab` once nothing calls it.

**Phase 2 — feature parity (visible, additive).**
4. Route charts gain the legend filter, isochrone control, click-info box, and
   `label_max_ly`. Decide per-feature whether it makes sense for a route map — the
   **isochrone** control in particular overlaps conceptually with route travel times
   and may want to default off or be suppressed.
5. Wire O15 row↔map linking where the panel's result table has star names in column 0
   (Nearest-Neighbor, Farthest-First, Jump Network do; Multi-Stop / Optimal Tour /
   Jump Route are leg-shaped `From|To` tables — same situation `add_two_star_chart_tabs`
   already handles by passing `link_view=None`).

**Phase 3 — palette unification (visible, needs sign-off).**
6. Point `_map_node` and `route_planning.py:204/216/221` at `core.viz._sp_color`,
   delete `_star_map_color`.
7. **This repaints existing charts**: G, M, D and the unknown-default shift on all 7
   route panels *and* opts 17/20/21. Requires the user's explicit approval — it is a
   look change, not a bug fix.

## 5. Risks

1. **Phase 3 is a visual change to 10 panels.** Get sign-off before, not after.
2. **`tests/test_viz_phase_o.py` fixtures hard-code route-palette hexes**
   (`#dfe6ff`, `#ff9d6c` at `:490-493`, `:620`, `:723`, `:830`, `:1112`). Phase 3
   invalidates them; they must move to `_SPECTRAL_COLORS` values in the same commit.
3. **The isochrone control assumes a Sol-centred distance frame.** Route charts
   re-centre on the route origin (`_centered`), so verify the rings are meaningful
   before enabling — this is the one feature that might be wrong rather than missing.
4. **`JumpNetworkPanel` overrides dot colour with per-tier colours** (`stars[].color`
   from `compute_jump_network`). The legend filter groups by *spectral class*, so on
   that panel the legend and the dot colours would disagree. Either suppress the
   legend filter there or group by tier — decide explicitly.
5. Phase 1 is behaviour-neutral and should be verifiable by the existing suite alone;
   if it isn't, that indicates route charts have no test coverage worth the name
   (check before starting — the Part 1 review found exactly that failure mode).

## 6. Test plan

- Phase 1: existing suite must stay green with no fixture edits (that is the proof it
  is behaviour-neutral). Add a test asserting `routes=` reaches the canvas.
- Phase 2: per-feature pins — legend entries present, isochrone rebuild preserves the
  route overlay, click-info box populates.
- Phase 3: assert **one** palette — `_star_map_color` gone, every route node colour
  equals `core.viz._sp_color` for the same type. Update the hard-coded fixtures.
- Prove each phase's guard by reverting it (the `completed_plans/SPECTRAL_CLASS_PLAN.md` D1 lesson).

## 7. Open questions

1. Is the current route-map colour divergence **intentional** (a deliberate visual
   distinction) or drift? Answer decides whether Phase 3 happens at all.
2. Should the isochrone control appear on route charts, given they already show
   travel time in their tables?
3. `JumpNetworkPanel`'s tier colouring vs the spectral legend filter — suppress,
   or add a tier-mode legend?
