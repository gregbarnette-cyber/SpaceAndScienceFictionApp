# Route-Find Plan — bring the O18 Find-Star box to the 7 Route Planning panels

**Status: COMPLETE — built 2026-07-31.** Plan written the same day and revised after
three read-only review sweeps (§5); implemented in the four parts below. Suite:
**2298 passed / 1 skipped** at baseline → **2332 passed / 1 skipped** after
(1 Part-0 pin + 33 new in `tests/test_route_find.py`). See §6 for what changed
against the plan as written.

Follow-on from `completed_plans/ROUTE_CHART_REFACTOR_PLAN.md`, which converged the
seven Route Planning charts onto the shared opt-18/19 `_build_iso_chart_tab` and so
gave them the O16 legend filter, the O17 isochrone control and the 3D presets — but
**not** the O18 Find box, which stayed behind in `gui/panels/distance_stars.py`.

Scope: **all seven panels**, sourced from the route star list (not the result
table), so the four leg-shaped panels are covered too. GUI-only — no core, no
`query.py`, no DB, no menu change.

---

## 0. What is already true (measured 2026-07-31)

Re-measure rather than trust these if the files move.

**The canvas half is already built.** `_attach_highlight_2d` / `_attach_highlight_3d`
(`plot_helpers.py:917, 990`) are called from `make_star_chart_canvas` /
`make_star_chart_3d_canvas` (`:2150, :2501`), so every route chart canvas exposes
`center_on`, `reset_view`, `highlight_star`, `highlighted_star`. **No
`plot_helpers.py` change is required by this plan** — which keeps opts 18/19, the
GCNS panels and `tests/test_sol_result_row.py:263‑318` (the six-canvas structural
pins) out of the diff. Those pins are the tripwire: if they move, D4 was violated.

- **Caveat — the empty-plot branch.** `plot_helpers.py:1857‑1860` (2D) and
  `:2259‑2264` (3D) attach an **empty** coord_map. The four methods still exist, so
  `getattr` guards never fire, but they are inert: `center_on`/`reset_view` always
  return `False`, and `highlight_star(name)` records the name while drawing **no
  ring** — so `highlighted_star()` returns a **false positive**. Any test asserting
  "highlighted after find" must also assert a ring artist or a `center_on` return,
  or it can pass against an empty chart.

**The ring is only ever produced by a table-selection side effect.** `_find_on_map`
calls `_star_click_select` (`distance_stars.py:210`) — plus `c._o16_reveal_class(...)`
(`:202‑209`) and `c.center_on(name)` (`:211‑217`), **neither of which draws a ring**,
so table selection remains the *only* ring source;
`_star_click_select` returns immediately when `model is None`
(`diagram_tabs.py:405‑433`, guard at `:415‑416`); `_on_link_selection` is the only caller of
`canvas.highlight_star` in the find flow (`diagram_tabs.py:394‑402`); and
`_wire_row_map_linking` connects `selectionChanged` only when `view is not None`
(`:444‑446`). **This is why D3a exists** — without it the four leg-shaped panels
would pan and print a readout with no ring on any canvas.

**`_link_canvases` population is conditional.** `_add_route_chart_tabs` calls
`_wire_row_map_linking` unconditionally *with respect to `link_view`*
(`route_planning.py:224`), but returns early on `not mpl_available()` or an
empty/`error` route map (`:196‑200`), and Nearest-Neighbor / Farthest-First only
call it `if chain:` (`:513, :790`). The honest statement: populated **after a
successful, non-empty render with matplotlib available**.

**Blast radius — four files, plus one shared function to leave alone.**
`_build_iso_chart_tab` / `_wire_row_map_linking` / `_star_click_select` are consumed
by `distance_stars.py` (opts 17/18/19), `route_planning.py` (the 7 planners + the
opts-17/20/21 helper), `travel_time_stars.py:10,146` (opts 20/21, which calls
`add_two_star_chart_tabs`), and `gui/panels/__init__.py`. **GCNS is mostly clear but
not entirely**: `gcns.py:126` calls `make_star_chart_canvas` directly and touches no
find code — but `gcns.py:26,133` imports and calls `_build_star_chart_3d_tab`, which
`_build_iso_chart_tab` also delegates to (`diagram_tabs.py:542`). **Rule: do not
modify `_build_star_chart_3d_tab`.**

**Table shapes (all verified).**

| Panel | call site | `link_view`? | name col | desig col |
|---|---|---|---|---|
| Nearest-Neighbor | `route_planning.py:515` | yes | 1 (`Hop #` leads) | 2 |
| Farthest-First | `:792` | yes | 1 (`Step` leads) | 2 |
| Jump Network | `:1028` (`legend_filter=False`) | yes | 1 (`Jumps` leads) | 2 |
| Multi-Stop | `:413` | **no** | n/a (`Leg #, Origin, Destination`) | n/a |
| Optimal Tour | `:686` | **no** | n/a (same) | n/a |
| Jump Route | `:886` (unreachable) and `:906` | **no** | n/a (`Jump #, From, To`) | n/a |
| Trade Route | `:587` | **no** | n/a (`From, To, Distance`) | n/a |
| opts 18/19 | `distance_stars.py:392` | yes | 0 | 1 |

`name_col=1` is `_add_route_chart_tabs`'s default (`:174`) and is never overridden,
so **the four leg-shaped panels also get `_link_name_col = 1`, pointing at
`Origin`/`From`, not an index column.** Inert today (`_link_view is None`) but a
live footgun for anyone who later re-enables table sourcing. Recorded deliberately.

**The off-chart case cannot occur — do not design for it.** The 2D cull is
`abs(x) > limit_ly or abs(y) > limit_ly` (`plot_helpers.py:1848‑1855`); 3D adds
`abs(z)` (`:2250‑2257`). For route panels `_centered` sets
`limit_ly = R × 1.1` where `R = max(√(x²+y²+z²))` (`route_planning.py:162‑164`), and
`|x| ≤ r ≤ R < 1.1R`, so neither cull ever fires. The same holds for opts 18/19
(stars carry `ly ≤ limit`). `x/y/z` are never `None` — every route star comes from
`_map_node` (`core/calculators.py:1662‑1670`), which always emits floats. An earlier
draft of this plan carried a "matched but off-chart" readout (D5); it was removed as
unreachable.

**Result-shape hazards** (`core.viz.prepare_route_map` is a pure passthrough of
`result["stars"]` — `core/viz.py:1350‑1430` — and never dedupes):

- **Duplicate names are live**, not hypothetical: Multi-Stop emits one node per
  typed stop with no dedup (`core/calculators.py:1742, 1766`) and the panel
  explicitly supports revisiting a star; Optimal Tour likewise if a star is typed
  twice. `coord_map` is name-keyed so duplicates collapse to one dot — a naive
  `_find_rows` would read "1 of 2" while centring the same point twice.
- **Jump Route `reachable=False`** renders the amber note, **builds no table at
  all**, and still calls `_add_route_chart_tabs` on a **two-node** chart
  (`route_planning.py:879‑888`, `core/calculators.py:2213‑2219`).
- **NN / FF with an empty chain** build no chart tabs at all (`if chain:`), so they
  correctly get no find box.

**The start star differs across panels.** Jump Network's tier-0 row **is** the start
(`core/calculators.py:2300‑2318`); NN/FF exclude it from `chain` (`:1795‑1802`) while
`stars[0]` keeps its `sp_type` under a gold colour override (`:1833‑1834`); the leg
panels have no per-star table. This is why D6 was reversed.

---

## 1. Decisions

- **D1 — The Find box moves to `gui/panels/diagram_tabs.py`.** It cannot stay in
  `distance_stars.py`: that module already imports `route_planning`
  (`distance_stars.py:22`), so the reverse import would be circular.
  **Re-export `_norm_find`, `_find_on_map`, `_clear_find`, `_add_find_box` from
  `distance_stars`** — three of them are imported by tests: `_norm_find`
  (`test_viz_phase_o.py:1081`), `_find_on_map` (`:1127`), `_clear_find` (`:1179`
  **and** `:1193` — two `_clear_find` sites, not `_add_find_box`, which no test
  imports). `_add_find_box`'s re-export is needed only for the internal
  `_add_map_tabs` caller at `distance_stars.py:393`.
- **D2 — The searchable set is `panel._find_rows`: a list of `(name, designations)`,
  deduped by name, first occurrence wins, order preserved.** Populated from the
  `_centered(rm)` star dicts on route panels, and from the result table on opts
  18/19 (using `_link_name_col`, which is 0 there — so their behaviour is
  unchanged). Dedupe is mandatory, not defensive: see the duplicate-name hazard in
  §0.
- **D3 — Table selection is an additive extra, not the mechanism.** When
  `panel._link_view` is set, a find still calls `_star_click_select` so the row is
  selected and scrolled to (the O15 gesture). When it is `None`, that call is
  skipped.
- **D3a — `_find_on_map` rings the canvases directly.** It calls
  `canvas.highlight_star(name)` on every entry of `_link_canvases`, and
  `_clear_find` calls `canvas.highlight_star(None)`. Without this the four
  leg-shaped panels get no ring at all (§0). This is the single most important
  correction to the original plan.
- **D4 — No `plot_helpers.py` changes.** If a part appears to need one, stop and
  re-scope. Assert on `center_on`'s return value or on ring artists — never on
  `highlighted_star()` alone, which is a false positive on the empty-plot branch.
- **D5 — (removed).** The "matched but off this chart" state is unreachable; see
  §0. The existing "No match" readout is the only negative outcome.
- **D6 — `stars[0]` (the start / gold ★) is EXCLUDED from `_find_rows` on all seven
  panels**, matching opts 18/19, where the centre star has no table row. An earlier
  draft made it findable; that was a trap for two independent reasons. (a) The ★ is
  drawn outside the O16 per-class scatter (`plot_helpers.py:1868, 1884, 2273, 2291`)
  but **is** in `name_cls` (`:2148, :2499`), and the ring's visibility rule is
  `name_cls.get(name) not in hidden` (`:928‑931`) — so filtering off the start's
  class would suppress its ring while the ★ stayed visible, and the reveal
  mitigation (`distance_stars.py:202‑209`) would un-hide a class the user
  deliberately filtered off. (b) The row behaviour is inconsistent *within* the
  route panels (§0), giving three outcomes for one gesture.
- **D7 — Opts 17/20/21 are excluded** (2–3 dots; nothing to find).
  `add_two_star_chart_tabs` is not touched. **The same reasoning applies to Jump
  Route's `reachable=False` shape** (two nodes, no table): suppress the find box
  there.
- **D8 — Jump Network gets no legend reveal, correctly.** It passes
  `legend_filter=False`, so `canvas._o16_reveal_class` does not exist — and no class
  is ever hidden there. The existing `getattr(..., None)` guard covers it.
- **D9 — An isochrone rebuild resets the find cycle.** `_build_iso_chart_tab`'s
  `_rebuild` (`diagram_tabs.py:516‑560`) swaps the canvas and gives it a fresh
  `view0`, so a stale `_find_idx` would make the next Find **advance the cycle**
  instead of re-centring, and a post-rebuild `_clear_find` would silently fail to
  restore the view (`reset_view()` returns `False`). `_rebuild` therefore clears
  `panel._find_matches` / `_find_idx`. This is a fix, not a documented quirk.

---

## 2. Parts

### Part 0 — Baseline & guard tests

No production code.

1. Run `QT_QPA_PLATFORM=offscreen venv/bin/python -m pytest` and **record the
   measured pass/skip count here** (`CLAUDE.md:67` documents 2297 passed / 1 skipped
   as of 2026-07-31 — confirm, don't assume).
2. **Add the missing pin for the `_find_widget` stale-reference guard**
   (`distance_stars.py:265‑271`): `reset()` → second `_render` → assert
   `_finish_render` was reached (Show Diagrams visible). This branch has **no test
   today** and is the highest-value untested code in the block being moved — pin it
   *before* moving it, so Part 1's neutrality claim means something.
3. Confirm the D4 canary (`test_sol_result_row.py:263‑318`) is green and note that
   it must stay untouched throughout.

**Exit:** measured baseline recorded; the new guard test passes against unmodified code.

### Part 1 — Relocation only

Move `_norm_find`, `_find_on_map`, `_clear_find`, `_add_find_box`, `_WS_RE` to
`diagram_tabs.py`; re-export from `distance_stars`. **Add `import re` to
`diagram_tabs.py`** (it imports only `math` at `:11`). No new Qt imports are needed —
`QWidget`/`QHBoxLayout`/`QLabel`/`QLineEdit`/`QPushButton` are all already imported at
`:13‑16`. Either delete the dead `existing.show()` (`distance_stars.py:273` — nothing
ever hides the find widget) or leave a note saying why it stays.

**Exit:** suite green with **zero test-file edits** (necessary, not sufficient), plus
an explicit check that all four names resolve from **both** modules. Run the
verification gate (§3) here as well as at the end.

### Part 2 — `_find_rows` + the ring path, on two panels

The behaviour change, deliberately narrow. Implement D2 (with dedupe), D3, **D3a**,
D6 (exclude `stars[0]`) and D9, and wire the find box to **exactly two panels**: one
leg-shaped (**Trade Route**) and one star-per-row (**Nearest-Neighbor**). Ship the
tests in this same part — this is where every regression will originate, so it does
not ship untested.

Also in this part: build `_find_rows` for opts 18/19 from the table via
`_link_name_col`, retiring the hardcoded `model.item(r, 0)` / `item(r, 1)`. With
`name_col=0` there, opts 18/19 must come out byte-identical. (An earlier draft made
this its own part and framed it as fixing a route-table column bug; after D2 the
find box is never wired to a route table, so there is no such bug to fix — it is
just a hardcode removal.)

**Exit:** find works on Trade Route (ring, no row selection) and Nearest-Neighbor
(ring + row selection); opts 18/19 unchanged; the §3 assertions pass for those two.

### Part 3 — The remaining five panels

Multi-Stop, Optimal Tour, Jump Route, Farthest-First, Jump Network. Per-panel
concerns: Jump Route must suppress the box on the `reachable=False` two-node shape
(D7); Jump Network is the scale case (D8, and the only panel that can return
thousands of nodes).

Lifecycle work belongs here: **clear `_find_rows` in `_prepare_render`** (not only in
`_add_route_chart_tabs`), because all seven panels render twice per Run and every
error path returns before the chart tabs are built, leaving `_find_rows` stale
otherwise. `_add_find_box` runs only inside `_add_route_chart_tabs`, after its early
returns. Record as a load-bearing invariant: `_finish_render` hides Show Diagrams
when there are zero tabs (`base.py:400‑403`), which is what keeps stale
`_link_canvases` (pointing at `deleteLater`'d canvases) unreachable between the two
renders.

### Part 4 — Docs

- `docs/gui-architecture.md` — the O-3/O18 row says the find box is opts 18/19.
- `docs/calculators.md` — the Route Planning / route-chart-refactor section.
- Move this file to `completed_plans/` + index it in `completed_plans/README.md`.

---

## 3. Verification gate

Run after **Part 1** and again after **Part 3**. The named assertions matter more
than the sweeps: three of the four defects found in review (D3a, D6, D9) are runtime
interaction outcomes that no existing test and no static reading would catch.

**Named assertions** (all new; `QT_QPA_PLATFORM=offscreen` must be set by the test
file itself — **there is no `conftest.py` in this repo**, every GUI test file sets it
via `os.environ.setdefault` before importing PySide6):

1. After a find on Multi-Stop / Trade Route / Jump Route:
   `all(c.highlighted_star() == name for c in p._link_canvases)` **and** a ring
   artist exists (guards the empty-plot false positive).
2. After Clear on the same: `highlighted_star() is None` everywhere.
3. Find → isochrone **Apply** → Find with the same query re-centres rather than
   advancing the cycle (D9).
4. Find on a `stopped_early` NN result and on an unreachable Jump Route.
5. `p.reset()` → second `_render` on a route panel (the stale-`_find_widget` guard).
6. Multi-Stop `Sol → Sirius → Sol` reads "1 of 1", not "1 of 2" (D2 dedupe).
7. A find never un-hides a legend-filtered class that the query did not match (D6).
8. Jump Network find over ≥1000 nodes, timed.

**Then:** three read-only agent sweeps (regression across the 7 panels + opts
17/18/19/20/21 + GCNS; import-graph/cycle check; coverage-gap check), `/code-review`
on the working diff, and the full suite via `venv/bin/python -m pytest`.

---

## 4. Explicitly out of scope

- Porting the opt-18/19 **HR Diagram / Night Sky / Map X–Y / X–Z / Map 3D** tabs to
  Route Planning. Separate question, separate plan.
- The Find box on opts 17/20/21 (D7).
- Any `core/` or `query.py` change — presentation layer only.
- **The pre-existing `_desc_btn` label desync**: `_enter_diagram_mode` hides
  `_tables_widget` including `_desc_box` (`base.py:405‑409`) while `_toggle_description`
  reads `isHidden()` (`route_planning.py:78‑84`), so the button label can desync after
  leaving diagram mode. Unrelated to find; named here so review sweeps stop
  re-reporting it. The find box lives in `_viz_container`, not `_tables_layout`, so
  it has no interaction with `_tables_keep` at all.

---

## 5. Review record (2026-07-31, pre-implementation)

Three read-only sweeps reviewed the first draft. Corrections folded in above:

1. **D3a added** — the original D3 asserted a ring on `link_view=None` panels that no
   code path provides. Would have shipped green: no existing test drives find on such
   a panel.
2. **D5 deleted** — the off-chart readout solved an unreachable case, and contradicted
   D2 in the same document.
3. **D6 reversed** — the start star is now excluded rather than findable (O16 ring
   suppression + inconsistent row behaviour across route panels).
4. **D2 gained dedupe** — duplicate names are reachable via Multi-Stop / Optimal Tour.
5. **D9 added** — find-after-Apply was a behaviour bug the original design introduced,
   not an inherited quirk to document.
6. **Old Part 2 dissolved** — the route-table column fix was work for a state the
   design never reaches; the hardcode removal folded into the new Part 2.
7. **Parts restructured** — the old Part 4 was one dead item, one already-shipped
   item, one doc item and one manual check. The behaviour change (old Part 3) was
   over-merged and is now split across Parts 2–3, tests shipping alongside.
8. **Gate rewritten** — from three vague agent sweeps to eight named assertions plus
   the sweeps.
9. **Blast radius corrected** — `travel_time_stars.py` added; the "GCNS is not on the
   shared-builder path" claim narrowed to "do not modify `_build_star_chart_3d_tab`".
10. **Part 0 gained the `_find_widget` guard test** — the highest-value untested
    branch in the moving code, now pinned before the move rather than after.

A fourth read-only sweep (2026-07-31, three parallel agents) re-verified every code
claim against the current tree — all decisions and the §0 panel table confirmed
line-for-line. Two factual corrections were folded in: (a) `_find_on_map` calls more
than `_star_click_select` (it also calls `_o16_reveal_class` and `center_on`, neither
of which rings) — §0 corrected; the D3a conclusion is unchanged. (b) `_add_find_box`
is imported by no test — the D1 re-export justification named it in error; corrected to
the three functions tests actually import. Neither correction changes a decision.

---

## 6. Build record (2026-07-31)

Baseline measured before any change: **2298 passed, 1 skipped, 447 subtests** — one
more than `CLAUDE.md`'s documented 2297 (corrected there). At the close of Part 4:
**2321 passed, 1 skipped**. The review sweeps (§6.1) and `/code-review` (§6.2) then
added 11 more tests → **2332 passed, 1 skipped, 484 subtests** final.

**Where the build differed from the plan.**

- **D6 is enforced by NAME, not by index.** The plan said "exclude `stars[0]`";
  implemented that way, the dedupe test caught it immediately. Multi-Stop and Optimal
  Tour emit one node per typed stop, so a route that *returns* to its start
  (`Sol → Sirius → Sol`) carries the start again at a later index — and the canvases'
  name-keyed coord maps point every copy at the same gold ★. Index-exclusion therefore
  re-admitted the exact star D6 exists to keep out. `_add_route_chart_tabs` filters on
  `s["name"] != stars[0]["name"]`.
- **D7's Jump-Route suppression needed an explicit flag**, not a row-count rule. The
  `reachable=False` shape has two nodes, so after excluding the start it still has one
  findable row — indistinguishable from a legitimate one-hop chain. Added
  `_add_route_chart_tabs(..., find_box=False)`, passed only by that branch.
- **The `_prepare_render` lifecycle work moved from Part 3 into Part 2** — it is what
  keeps the Part-2 panels correct across an error render, so shipping it later would
  have meant shipping a known-stale state.
- **Part 2's "exactly two panels" was not staged.** The find box is wired inside the
  shared `_add_route_chart_tabs`, so all seven get it in one edit; gating five of them
  behind a throwaway parameter would have been churn, not caution. The testing
  discipline the split existed to enforce was kept by other means: every decision was
  **revert-proved** (see below).
- **Part 0's guard test needed a scoped `sendPostedEvents`.** The obvious
  `QApplication.sendPostedEvents(None, DeferredDelete)` passed in isolation and
  **segfaulted the full suite** — it frees widgets other test classes hold class-level
  references to. Scoped to the panel's own old container.
- **Three import-hygiene fixes** from the review sweep: `_WS_RE` was re-exported into
  `distance_stars` with no consumer (dropped); the re-export line now carries a
  `# noqa: F401` and a comment, since an "unused import" cleanup would silently break
  four tests in `test_viz_phase_o.py`; and `route_planning`'s function-local
  `_add_find_box` import was hoisted to the existing module-level `diagram_tabs`
  import — `diagram_tabs` imports nothing from `gui.panels`, so there was never a
  cycle to defer around, and the local import implied one.

**Revert-proofs.** Each of these was removed in turn and the suite re-run; every one
failed at least one test, so none is untested scaffolding:

| Removed | Tests that failed |
|---|---|
| D3a direct `highlight_star` in `_find_on_map` | 12 |
| D9 cycle reset in `_build_iso_chart_tab._rebuild` | `test_apply_resets_the_find_cycle` |
| D6 by-name exclusion (→ by-index) | `test_multi_stop_revisit_dedupes` |
| `_prepare_render` clearing `_find_rows` | 2 |
| D7 `find_box=False` on unreachable Jump Route | `test_unreachable_jump_route_has_no_find_box` |
| the `_add_find_box` stale-`_find_widget` guard | the Part-0 pin (`RuntimeError`) |

**Not done here:** `/code-review` on the working diff is user-triggered and was left to
the repo owner.

### 6.1 Post-build review sweeps (the §3 gate)

Three read-only sweeps ran against the finished diff. They produced **one real bug**,
three code cleanups and eight test-coverage gaps, all fixed before close.

**The bug — a stale find box across renders.** `_viz_container` and `_find_widget`
both outlive a render, and `_prepare_render` only cleared `_find_rows`. So a result
that built charts but *no* box — a reachable Jump Route followed by an unreachable one
— left the previous run's box on screen, still carrying its old query, over an empty
searchable set; pressing Find hit the `if not find_rows: return` guard and did nothing
at all, with no readout and no status line (every other failure says "No match").
`_prepare_render` now **hides** the widget and `_add_find_box`'s `existing.show()`
brings it back — which incidentally makes that `show()` load-bearing rather than the
dead call Part 1 flagged. Pinned by
`test_a_result_with_no_find_box_hides_the_previous_one`.

**Cleanups.** `_WS_RE` was re-exported into `distance_stars` with no consumer
(dropped); `route_planning`'s function-local `_add_find_box` import was hoisted to the
existing module-level `diagram_tabs` import — `diagram_tabs` imports nothing from
`gui.panels`, so there was never a cycle to defer around and the local import implied
one; and D9's `except AttributeError` guard was dead (every `_build_iso_chart_tab`
call site passes a real panel).

**Test weaknesses found and fixed.** `assertRinged` checked that a ring artist existed
but not that it was **visible** — and `_attach_highlight_2d/_3d` end with
`ring.set_visible(name_cls.get(name) not in hidden)`, so the exact D6 failure mode
(ring created, then suppressed because its class is legend-filtered off) would have
passed. `test_unreachable_jump_route_has_no_find_box`'s `_find_rows == []` assertion
was a tautology (`_prepare_render` empties it on every render regardless). The scale
test's 2 s bound was ~4 orders of magnitude loose and asserted only `"of"` in the
readout. Added coverage for: the `_add_find_box` **reuse** branch (the normal path —
every Run renders twice), the full `_prepare_render` cycle clear, the empty-`_find_rows`
guard, the isochrone **Clear** button (only Apply was covered), `center_on` panning
both charts on a plain find, and the D1 re-exports (an unused-import cleanup would
silently break four tests in `test_viz_phase_o.py` with nothing else to catch it).

**One §0 claim narrowed.** "The off-chart case cannot occur" holds for the route
panels — every star comes from `_map_node` (always floats) and `limit_ly = 1.1 × R`,
so nothing is culled — but **not** for opts 18/19 as the diff now leans on it:
`prepare_star_map_from_result` drops rows with `x is None`, while `_find_rows` comes
from the table, so such a row is findable with no dot. Pre-existing (the old table scan
did the same), documented in `docs/gui-architecture.md` rather than fixed.

**Also note:** opts 18/19 are byte-identical **except** when two table rows share a
Star Name — they now collapse to one entry rather than reading "1 of 2" and cycling.
That was already a lie (the coord map is name-keyed, so both steps centred one dot).
Pinned by `test_duplicate_table_names_collapse_to_one_entry`.

**Line numbers in §0 above are pre-build and now stale** — `route_planning.py` refs
shift ~+22 and `diagram_tabs.py` refs after line 447 shift ~+223. §0 says to re-measure
rather than trust them; that still applies.

**One more behaviour change caught by the regression sweep, and fixed rather than
documented: match order after a user sorts the table.** `make_table` enables sorting
and `QStandardItemModel.sort` physically reorders rows, so the old live table scan
cycled matches in the order the user was actually looking at; a render-time snapshot
cycled in render order (sorting opts 18/19 by distance and searching `alpha` reported
the render-first star, not the nearest). Table-sourced panels now carry
`_find_rows_live` and re-derive `_find_rows` on every find; the route panels have no
per-star table to follow and keep the snapshot. Pinned by
`test_cycle_order_follows_a_user_sort`.

### 6.2 `/code-review` on the working diff

Run last, after §6.1. No crash, dropped guard or broken caller; three low-severity
findings, all real. **One was a behaviour bug and was fixed; two were cases where the
behaviour is right but the reason I wrote down for it was factually false** — the more
useful kind of finding, since a wrong rationale in a comment survives to mislead the
next change.

- **Fixed — the find readout went stale across an isochrone Apply.** D9 reset
  `_find_matches`/`_find_idx` but left the label, so after cycling to "2 of 2 matches
  — X" and pressing Apply the chart rebuilt at its default un-centred view while the
  label still claimed match 2 — and the next Find with that query re-centred match
  **1**. `_rebuild` now clears the readout too; the query text stays. Pinned by
  `test_apply_clears_the_stale_readout`.
- **Rationale corrected — `_find_rows_live` and route tables.** The comment and doc
  said route panels "have no per-star table to follow". Three of the seven do
  (Nearest-Neighbor, Farthest-First, Jump Network — all sortable). The real reason is
  D2: their searchable set is the route star list, so re-deriving from the table would
  change the *set*, not just its order — and Jump Network's table carries the start,
  which D6 excludes. The visible consequence (after a user sort, the ring cycles in
  route order while the row selection scrolls non-monotonically) is now stated rather
  than hidden behind a false premise. Route order is the more meaningful cycle on a
  route panel, so the behaviour stands.
- **Rationale corrected — D6 on `JumpNetworkPanel`.** Both of D6's premises fail for
  that one panel: its start *does* have a table row (`tiers[0]`), and it passes
  `legend_filter=False`, so no class is ever hidden and `_o16_reveal_class` does not
  exist. Typing the start's name there reports "No match" for a star visibly in the
  table and present in the canvas `coord_map`. Kept anyway — making it the single
  panel where the start is findable would give one gesture two outcomes across the
  seven, which is precisely the inconsistency D6(b) was reversed to remove — but the
  asymmetry is now recorded at the code site and in `docs/gui-architecture.md` instead
  of being implied away.
