# Route-Chart Refactor Plan — converge the 7 Route Planning maps onto the shared builder

**Status: COMPLETE — Phases 1, 2 and 3 all BUILT (2026-07-27).** Follow-on from
`completed_plans/SPECTRAL_CLASS_PLAN.md`, which deliberately deferred palette
unification here. Ready to move to `completed_plans/`.

## 0. As-built (Phases 1–2)

Suite after the change: **2114 passed, 1 skipped** (2100 + the 14 new tests),
**no fixture edits** — the Phase-1 neutrality proof.

**The seam.** `routes=None` was added to `_build_star_chart_3d_tab` and
`_build_iso_chart_tab` (`gui/panels/diagram_tabs.py`) and passed straight to the
canvases, re-passed on every isochrone rebuild. `_build_iso_chart_tab` also gained
`legend_filter=True` (it previously hard-coded `True` at both call sites) so Jump
Network can opt out. `_add_route_chart_tabs` now builds both tabs through
`_build_iso_chart_tab`; the duplicate `_route_chart_3d_tab` is deleted, and the
now-unused `make_star_chart_canvas` / `make_star_chart_3d_canvas` imports are gone
from `route_planning.py`.

**Parity.** All seven route charts gained the O16 legend filter (except Jump
Network — see below), the O17 isochrone control, and `label_max_ly`: raised to
`max(limit×10, 100)` for sparse routes (≤ `_ROUTE_SPARSE_MAX_NODES` = 25 nodes, the
O8 two-star-map treatment) and left at the shared 15 ly default above that, since
Jump Network can return thousands of nodes.

**Three plan corrections found during the build:**

1. **The click-info box was never missing.** `make_star_chart_canvas` creates it
   unconditionally (`plot_helpers.py`, the `info_box` `ax.text`); `on_star_click`
   is only the O15 row-selection callback. §1's bullet was wrong — nothing to do.
2. **No route table has star names in column 0.** All of them lead with an index
   column (`Hop #`, `Step`, `Jumps`), but `_selected_star_name` / `_star_click_select`
   hard-coded column 0, so §4 item 5's premise was wrong and linking would have
   silently matched nothing. Fixed with an additive `name_col` (default 0 → opts
   18/19 and the two-star maps unchanged; the route panels pass 1, stored as
   `panel._link_name_col`). Wired on Nearest-Neighbor, Farthest-First and Jump
   Network; the leg-shaped `From|To` panels (Multi-Stop, Optimal Tour, Jump Route,
   Trade Route) pass no `link_view`, exactly as `add_two_star_chart_tabs` does for
   opts 20/21.
3. **Risk 5 was real: route charts had zero test coverage.** Nothing touched
   `_add_route_chart_tabs` or `_route_chart_3d_tab` — only the `prepare_route_map`
   core prep was tested. `tests/test_route_chart_tabs.py` was therefore written
   *first* (8 Phase-1 pins passing against the pre-refactor code, 5 Phase-2 tests
   failing) and only then the refactor.

**Resolved risks.** Risk 3 (isochrone frame) is fine: the rings are drawn at radius
from `(0,0)` and `_centered` puts the route's start there, so they read as travel
time **from the start**. Risk 4 is decided — Jump Network passes
`legend_filter=False`; its dots carry per-tier colours while the legend groups by
spectral class and takes its swatch from that same colour, so a legend there would
show "Class M" with a tier swatch. Its own tier-swatch legend above the table stands.

## 0b. As-built (Phase 3 — palette unification)

Suite after: **2115 passed, 1 skipped** (the +1 is the new one-palette guard).

`core.calculators._star_map_color` is **deleted**. The palette moved to
**`core/shared.py`** as `_SPECTRAL_COLORS` + `sp_color()` — beside the
`spectral_leading_class` / `_SP_DISPLAY_LETTERS` rule it is keyed off, so colour and
bucketing cannot drift again. `core/viz.py` re-exports it under its historical names
(`_SPECTRAL_COLORS` / `_sp_color`), so all 17 display sites and `gui/panels/gcns.py`
are untouched. `_map_node` and the three O8 two-star map nodes call `sp_color`.

**Why `core/shared.py` and not `core/viz.py`** (a decision §4 didn't make): pointing
`_map_node` at `core.viz` would make the pure-computation layer import the viz-prep
layer — backwards, and it is on the `query.py` route path. `core/shared.py` is
already imported by both, so it is the natural home. No import cycle (`viz` and
`calculators` both import `shared`; `shared` imports neither).

**What repainted** — four values, on the 7 route panels + opts 17/20/21:
G `#fff4c2`→`#FFF4EA`, M `#ff9d6c`→`#FF8D3F`, D `#dfe6ff`→`#B0C4DE`, unknown
`#cccccc`→`#AAAAAA`. `O B A F K` and the Part-2 `L T W Y C N` were already identical.
`jump-network`'s per-tier colours are unaffected (they override the spectral colour).

**Consumer impact:** the same four hexes change in the `query.py` route subcommands'
`stars[].color`, and are now uppercase — noted in `docs/integration.md`.

**Fixture edits — §5 risk 2 was half wrong.** The `test_viz_phase_o.py` hexes it
listed are fixture *inputs* (synthetic star dicts), not assertions, so they did not
fail and were left alone. Only two real assertions broke: the `test_search.py`
palette test (which §5 missed entirely) and one `_star_map_color("")` reference at
`test_viz_phase_o.py:2063`. The former is rewritten as
`test_there_is_exactly_one_spectral_palette`, which asserts `_star_map_color` is gone,
that viz's names are the shared objects, and that every `_map_node` / two-star node
colour equals `_sp_color` for the same type. Guard-proved by reintroducing a local
G/M/D palette inside `_map_node` → it fails.

**Guard-proof (the D1 lesson).** Each guard was reverted individually and the
matching test confirmed to fail: `routes=` dropped on rebuild → the overlay test
fails; Jump Network's `legend_filter=False` removed → the suppression test fails;
`name_col` defaulted back to 0 → the linking test fails. The second and third only
bite because those two tests drive the panel's own `_render` — an earlier version
passed the kwargs from the test and **passed even with the panel's call site
reverted**.

> **Sections 1–6 below are the ORIGINAL plan, kept verbatim as the historical record —
> they describe the *pre*-refactor state in the present tense and their line numbers are
> now stale. What actually shipped (including three places the plan was wrong) is in
> §0 and §0b above; §7 records how the open questions resolved.**

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

1. **RESOLVED — drift, not design; Phase 3 built 2026-07-27.** The deciding argument
   was that Phases 1–2 put the divergence *inside a labelled key*: the route charts
   gained the O16 legend, whose swatch comes from each star's `color`, so the same
   "Class M" entry was painted two different colours on two panels. The evidence
   weighed at the time, both ways:
   - *Intentional:* `tests/test_search.py::test_colour_helpers_agree_with_the_rule`
     pins the divergent hexes with the comment "`_star_map_color` is a deliberately
     separate palette; the ADDITIVE guarantee is that no letter which already had
     an entry changes colour" — i.e. Part 2 consciously chose not to unify.
   - *Drift (this won):* that decision was about not repainting charts mid-fix, not
     about the two palettes being meaningfully different. The comment said
     "deferred", not "designed", and the code carried no reason for the divergence.
   The `tests/test_search.py:447-452` fixture site §5 risk 2 missed was updated in
   the same change.
2. **DECIDED — kept.** The isochrone control appears on all seven route charts. The
   rings are centred on the route's start (see §0), so they answer a question the
   tables don't: how far along the route you get in a given time.
3. **DECIDED — suppressed.** `JumpNetworkPanel` passes `legend_filter=False`; the
   tier-mode legend was not built. Its existing tier-swatch legend above the table
   already carries that key, and a class-grouped legend would mislabel tier colours.
