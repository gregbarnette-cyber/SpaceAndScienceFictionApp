# OEC System View — Star-First Master/Detail (option 7 Data tab)

**Status:** PLANNED — not started. Design approved 2026-08-01 against
`mockups/OEC_TREE_VIEW_MOCKUP.html` (★ Recommended tab).
**Revision 2 (2026-08-01)** — folds in three plan reviews (codebase fact-check, plan/risk,
derived-layer physics). Changes from r1: coverage figures re-measured; the derived layer's
raise-paths and unit traps made explicit; Stage 4 split; three stages added; Copy/Export deferred;
estimate 5 → **7–9 days**.
**Scope:** `gui/panels/catalogs.py` (`OecPanel`) display layer + one new pure-math core module.
**Not in scope:** the OEC parser, the cache, `query.py`, the Architecture map's geometry,
every other panel.

---

## ▶ START HERE — resuming implementation

**This plan is approved and ready to build. When it is loaded, begin at the first stage whose
checkbox below is unticked — do not re-plan, re-review, or re-litigate settled decisions.**

Progress ledger — tick a box only when that stage is complete *and* the full suite is green:

- [x] **Stage 1** — Columnar tree + hide-empty + B.2 constant move (T1, T2, T7) — done
      2026-08-01; suite **2402 passed, 1 skipped** (17 new in `tests/test_oec_view.py`).
- [x] **Stage 1b** — Star-side derived minimum: `luminosity_lsun` + `hz_bounds` (T16, T8/T9 subset)
      — done 2026-08-01; suite **2421 passed, 1 skipped** (`core/oec_derived.py`,
      `tests/test_oec_derived.py`, T16 in `tests/test_oec_view.py`).
- [x] **Stage 2** — Detail pane + registry + selection ▲ **review R1** (T3, T6, T10, T10b, T18)
      — built 2026-08-01; **R1 run and all six findings fixed**; suite **2448 passed, 1 skipped**.
- [x] **Stage 3** — Star dossier blocks (T4, T5, T15) — done 2026-08-01
- [x] **Stage 3b** — Binary / system / satellite sections (T20, T6 per tag) — done
      2026-08-01; suite **2478 passed, 1 skipped**. **V1/V2 run early and clean** (below).
- [x] **Stage 4a** — Star-side derived ▲ **review R2a** — built 2026-08-01; **R2a run, all
      four findings fixed**; suite **2510 passed, 1 skipped**.
- [x] **Stage 4b** — Planet-side derived ▲ **review R2b** (T8, T9, T17, T19) — built
      2026-08-01; **R2b run, all eight findings fixed**; suite **2555 passed, 1 skipped**
      (2026-08-02).
- [x] **Stage 5** — Pinned host band (T11) — done 2026-08-02; suite **2564 passed,
      1 skipped** (9 new in `HostBandTests`).
- [x] **Stage 6** — Toolbar (T12a, T12b, T12c) — done 2026-08-02 (12 new in `ToolbarTests`).
- [x] **Stage 7** — Validation sweeps V1–V6 + §L docs — done 2026-08-02; actuals in §G;
      suite **2571 passed, 7 skipped, 484 subtests** (the 6 extra skips vs Stage 4b are the
      `_netcheck`-gated `*_live.py` tests, which pass 24/24 when run on their own —
      the gate tripping under a 9-minute run, not a regression).
      ▲ **R3 run 2026-08-02 — seven findings, all fixed** (see the Stage-7 entry);
      suite after the fixes **2583 passed, 1 skipped, 484 subtests**, and V1 re-run
      clean (14,037 nodes, 0 exceptions, 0 failed sections).

**All stages complete.** Nothing is committed — the user commits.

**Before writing code, read in this order:** §0 (posture) → §B (seams — §B.4 is the highest-risk
integration point) → §E (locked decisions, D1–D12) → the stage's own §C entry → its tests in §F.
For derived work also read §D.2 (domain gates) in full.

**Standing rules while building:**
- Run tests as `venv/bin/python -m pytest` — a bare `pytest` uses system Python and fails at collection.
- The approved visual target is `mockups/OEC_TREE_VIEW_MOCKUP.html`, ★ Recommended tab.
- Decisions D1–D12 are **locked** (§E). If one turns out to be wrong, stop and raise it — do not
  silently re-decide.
- `tests/test_oec.py` edits are a tripwire (§0); any permitted edit is recorded in §M.
- Each stage ends green and shippable, not merely green — see its acceptance line.
- Do not commit unless asked.

---

## §0 — Build posture

- **Display-layer change.** `core.databases._oec_node` already captures every field in the XML
  (D7 generic capture). Nothing about parsing, caching or resolution changes. The one new *core*
  file is a pure-math derived-values module (§D) — in `core/` rather than the panel so it is
  testable headlessly and reusable by `query.py` later.
- **Additive to the panel.** The Data tree tab stays tab 0 of `_data_tabs`; the Hypatia tab and all
  viz tabs keep their indices and build order.
- **`tests/test_oec.py` edits are a tripwire, not a prohibition** *(r2 finding 6)*. An existing test
  may be edited **only** if the change is to a display-string assertion; it must be called out in
  the Stage-2 or Stage-4 review and recorded in §M below. Any edit to a behavioural assertion means
  the change went wider than intended — stop and re-scope.
- **No new dependencies.** No network, no DB write from the new core module (§D rule 6), no
  `QSettings` (D6).
- **`query.py` output must not move** — byte-identical (§G V4).

---

## §A — What ships

1. **Columnar tree** replacing the crammed properties string — 10 columns, **star rows populated in
   the same columns as planets** (M☉, R☉, T_eff, derived L, HZ bounds).
2. **Detail pane** (right / below / hidden) driven by tree selection, for **all five** node types:
   star (8-block dossier), planet, binary, system, satellite.
3. **Pinned host-star band** on the planet pane (L, HZ bounds, snow line, distance); click to
   return to the star dossier.
4. **Derived layer** — violet, badged, one toggle, never merged into the catalogue block.
5. **Toolbar** — tri-state units, errors, derived, hide-empty, pin-host, pane position.
   *(Copy TSV / Export CSV deferred — §K.)*

---

## §B — Architecture & seams

### B.1 New files

| File | Purpose | Qt? |
|---|---|---|
| `core/oec_derived.py` | Pure derived-value functions (§D) | no |
| `gui/panels/oec_detail.py` | Field registry + per-tag section builders | yes |
| `tests/test_oec_derived.py` | Pure math + contract tests | no |
| `tests/test_oec_view.py` | Tree columns, selection, toolbar | Qt-gated |
| `tests/_oeccheck.py` | Cache-presence gate (§F) | no |

`_oec_tree_item` / `_oec_tree_bits` / `_OEC_TREE_KEYS` are **replaced**, not extended.

### B.2 Constants that must not fork *(revised — r3 finding 6)*

Three Jupiter→Earth constants already exist under **two different names**:

| Constant | Location | Value |
|---|---|---|
| `_M_JUP_EARTH` | `core/calculators.py:516` | 317.828 |
| `_MJUP_MEARTH` | `gui/panels/catalogs.py:609` | 317.828 |
| `_RJUP_REARTH` | `gui/panels/catalogs.py:610` | 11.209 |

**A name-based guard test would pass against this duplicate.** T7 must assert on the **value**:
no float literal `317.828` / `11.209` may appear outside the single canonical definition.

**Decision:** canonical pair lives in `core/shared.py`; `core/calculators.py` and
`gui/panels/catalogs.py` import it under their existing names. Mirrors the `_SPECTRAL_COLORS` move.

**This is the only code edit outside OEC in the whole change.** `_M_JUP_EARTH` is consumed at
`core/calculators.py:561` by `compute_rv_semi_amplitude` — exposed as `query.py rv-semi-amplitude`
(Phase T1b A1) and consumed by the sibling scifiWorldBuilding repo. The value does not change, so
output stays byte-identical; V4 proves it. `core/shared.py` is the widest-reach file touched, but
the edit is purely additive (two module-level floats, no existing name altered).

**Radius convention must be stated, not assumed.** `11.209` = R♃(equatorial)/R⊕(equatorial);
against `_EARTH_RADIUS_KM = 6371` (mean) it is 11.221. **Lock: equatorial for both**, matching
`core/equations.py:49` `_JUP_RADIUS_M = 7.1492e7` — which is what OEC's 1-bar radii are. The
consequence propagates to §D (density and gravity constants).

### B.3 Selection is one source of truth

Three selectors must converge on one panel attribute:

```
selection = (node, kind)          # self._oec_sel
    ├── tree currentChanged   → set selection → render pane        (NOT itemClicked — r2 #3)
    ├── map star / ◆ click    → set selection → render pane + recenter (existing)
    ├── host combo change     → set selection → render pane + recenter (existing)
    └── pinned band click     → set selection to the host star → render pane
```

Wiring to `selectionModel().currentChanged` rather than `itemClicked` is load-bearing: with
`itemClicked`, arrow-key navigation silently stops updating the pane and no test would catch it
(T3 now asserts keyboard).

**A selection change must not rebuild the viz tabs** — only `_on_arch_select` / `_on_host_changed`
do that today and that stays true, else clicking a planet tears down the diagram in view.

**Cold state (D10):** on build, auto-select the primary host star. Gives criterion 3 a first paint
and T3 a deterministic start.

### B.4 The trap in `_rebuild_after_focus`

```python
while self._data_tabs.count() > 1:      # keeps index 0 (the tree), deletes the rest
```

Verified at `gui/panels/catalogs.py:1006-1010`; the Hypatia tab is added at index 1. The pane must
live **inside** the Data tab (a `QSplitter` of tree + pane), never as a sibling tab — as a tab it
would be silently destroyed on every recenter and host switch. Pinned by T10.

**A second, distinct layout risk** *(r2 #6)*: that splitter sits inside a `QScrollArea` whose
layout is `AlignTop`, above which the "Matched on:" header and the Host combo consume vertical
budget. T10b covers the layout interaction separately from the teardown.

### B.5 Preserved tree properties *(new — r2 #3)*

The rewrite must consciously re-decide, not silently drop:
`setAlternatingRowColors(True)` — keep · `setColumnWidth(0, 340)` — **drop**, replaced by
`ResizeToContents` on numeric columns + `Stretch` on the name column · `setMinimumHeight(360)` —
re-tune for the splitter · the "Matched on:" header and Host combo — unchanged.

### B.6 Field registry, not scattered conditionals

One table per tag in `gui/panels/oec_detail.py`, with a trailing **"Other catalogued fields"**
fallback (alphabetical, humanised label) that guarantees a future OEC field cannot go missing.

**Name-collision guard** *(r3 finding 3)*: OEC's planet `periastron` is the **argument of
periastron in degrees** (τ Cet g = 395.3), *not* a distance. It must be labelled
"Argument of periastron (°)" and the derived distance must use a **non-colliding key**
(`peri_distance_au` / `apo_distance_au`). T17 pins it.

**Every section builder is wrapped in the panel's existing `log_viz_error` idiom** — one node's
failure must not blank the pane (T18).

---

## §D — The derived layer (`core/oec_derived.py`)

Pure functions, no Qt, **no I/O**. Every entry returns a value **or `None` with a reason** — never
a raise, never a silent zero.

```python
def derive(kind, node_values, host_values=None, system_values=None) -> dict
# → {key: {"value": …, "unit": str, "reason": str|None, "source": str}}
```

### D.0 Input units (OEC, verified)

planet mass/radius **Jupiter** · star mass/radius **Solar** · satellite mass/radius **Jupiter**
*(corrected at R3 — see below)* · sma **AU** · period **days** · distance **parsecs** ·
temperature **K**.

> **§D.0 was wrong about satellites, and it propagated (R3, 2026-08-02).** This line read
> "satellite mass/radius **Earth**". It is not: OEC catalogues a `<satellite>` exactly like a
> planet, in **Jupiter** units — the Moon is `mass 0.000039` (= 7.35e22 kg / 1.898e27 = 3.87e-5 M♃)
> and `radius 0.024847` (= 1737 km / 71 492 km). Because the plan asserted otherwise, **both**
> render sites labelled the raw number `M⊕`/`R⊕` with no conversion, so every one of the 18
> catalogued moons was shown **318× / 11× too small** from Stage 1 through Stage 7 — and no test
> caught it, because the tests asserted the *unit string* the plan specified. Both sites now
> convert (`@sat_mass`/`@sat_radius` in the registry, `_MJUP_MEARTH`/`_RJUP_REARTH` in the tree),
> always to Earth units — a moon is unreadable in Jupiter units and D1's toolbar scope stays
> planets-only. Anchored by a hand-checkable Moon test (0.0124 M⊕ / 0.2785 R⊕).
> **The lesson:** T8-style anchors were required of the *derived* layer but not of *catalogued*
> rendering, so a wrong premise in the plan passed straight through to the screen.

### D.1 The value table

| Key | Formula / source | Notes from review |
|---|---|---|
| `light_years` | `pc × 3.26156` | |
| `parallax_mas` | `1000 / pc` | guard pc = 0 |
| `angular_diameter_mas` | **`9.305 × R☉/d_pc`** | r3 #8 — "2R/d" is dimensionless; write the constant |
| `luminosity_lsun` | **call `compute_star_luminosity`** (opt 41) | r3 #7 — don't reimplement |
| `log_g` | `4.438 + log₁₀M − 2log₁₀R` (cgs dex) | zero point verified exact (4.4380) |
| `mean_density_gcc` | `1.41 × M/R³` | verified 1.4101; **stars only** |
| `abs_mag_v` | `V + 5 − 5log₁₀(pc)` | no extinction; combined-mag caveat for unresolved binaries |
| `b_minus_v`, `v_minus_k` | subtraction | V−K mixes Johnson V with 2MASS Ks — **label, don't correct** |
| `ms_lifetime_gyr`, `stage` | `compute_stellar_evolution` | returns `{"error"}` outside 0.1–20 M☉ → unwrap to `reason` |
| `hz_bounds` | `compute_habitable_zone` | **gate 2600 ≤ T ≤ 7200 first** — see D.2 |
| `hz_circumbinary` | `compute_circumbinary_hz` (D9) | flags out-of-range but **still calls** HZ → same gate needed |
| `ice_lines` | `compute_ice_lines` | returns a list |
| `hyper_limit_au` | `compute_hyper_limit_for_spectral_type` | **does a SQLite read** → computed by the **panel**, passed in; not in this module (r3 #7) |
| `sma_au` (recovered) | Kepler III, **P in years, M☉** | days→years conversion mandatory; neglects Mp (state it) |
| `insolation_searth` + `hz_verdict` | **call `compute_habitable_zone_sma`** | r3 #7 — returns `planet_seff` *and* the 5-way verdict; do not reimplement either |
| `peri_distance_au`, `apo_distance_au` | `compute_orbit_periastron_apastron` | **no validation inside** — guard e ≥ 1 (τ Cet b: e = 0.16 **+0.22**) |
| `density_gcc` | **`1.240 × M♃/R♃³`** | r3 #6 — 1.326 is the *mean*-radius constant; OEC radii are equatorial → 22% error |
| `surface_gravity_g` | **`2.527 × M♃/R♃²`** | equatorial, not 2.643 |
| `escape_velocity_kms`, `retention` | `compute_atmosphere_retention` | returns `{"error"}` dict |
| `rv_semi_amplitude_ms` | `compute_rv_semi_amplitude` | errors unless **exactly one** of period/sma; τ Cet e has both. **msini + catalogued inclination double-counts sin i → pass `inclination_deg=90` whenever mass is msini-typed** |
| `transit_prob`, `transit_depth_ppm` | `compute_transit_signal` | `R★/a` ignores e — flagged approximation |
| `hill_radius_au`, `moon_limit_au` | `compute_hill_sphere` | |
| `tidal_lock_gyr` | `compute_tidal_locking_time` | **DEFERRED — see D.3** |
| `stype_critical_au` / `ptype_critical_au` | `compute_binary_orbit_stability` | binary `separation` **repeats (AU + arcsec)** — select by `unit` attr, not `oec_fv`'s first. 61 Cyg has P but no `semimajoraxis` → binary-a needs its own Kepler recovery |
| `topology` | tree walk (mirrors `oec-census`) | string/dict composite |

### D.2 Domain gates — the contract's real test *(r3 finding 1)*

**`compute_habitable_zone` raises.** Measured: the Kopparapu quartic peaks near 7980 K, crosses
zero at ~10 684–10 720 K, and above that `math.sqrt(L/seff)` throws `ValueError: math domain
error` (verified: 10 000 K → 0.9344 AU silently wrong; 10 700 K → raises). Any A/B host — and any
white dwarf with a catalogued `temperature` — crashes the call.

**Rule: gate in the derived layer; never rely on the core function's own bounds.**

| Input condition | Result |
|---|---|
| T_eff outside 2600–7200 K | `None`, `reason="Teff outside Kopparapu validity (2600–7200 K)"` |
| mass outside 0.1–20 M☉ | `None`, unwrapped from `compute_stellar_evolution`'s `{"error"}` |
| distance / mass / radius / sma = 0 or absent | `None` + reason (guards `1000/pc`, `log₁₀`, `L/a²`) |
| e ≥ 1 | `None` — `compute_orbit_periastron_apastron` silently returns negative |
| any core call returning `{"error": …}` | unwrapped to `reason`; the `"error"` key must never reach the renderer |

T9 enumerates every row of this table as a case.

### D.3 `tidal_lock_gyr` is dropped from v1 *(r3 finding 5)*

`compute_tidal_locking_time` takes the satellite **mass**, not radius, and derives its radius from
mass via `_rocky_radius_km` (R ∝ M^0.55) — meaningless for a gas giant. It also needs
`initial_rotation_hours`, which **OEC never catalogues**, so any value is invented. Reporting a
lock time built on an invented rotation period and a fictitious radius fails the plan's own
provenance standard. Moved to §K.

### D.4 Rules

1. A catalogued value always wins the display slot; the derived one appears beside it as a
   cross-check, never overwriting.
2. Missing input → `{"value": None, "reason": "no radius"}`; the pane renders the reason.
3. Every entry carries `source`.
4. **Cache keyed on the panel's current result, cleared in `_on_oec_result`** — *not* `id(node)`
   *(r2 #5: `id()` is reused after GC and node dicts are rebuilt per search — a stale key is a
   wrong-numbers bug)*. T19 runs two searches back-to-back and checks the second's values.
5. Derived keys carry **fixed, name-encoded units** (`_au`, `_gcc`, `_gyr`, `_mas`, `_kms`, `_ms`,
   `_ppm`) — not SI *(r3 #8 corrects r1's wording)*. **The D1 units toggle touches only catalogued
   planet mass/radius rendering; no derived key is affected by it.**
6. Composite returns (`hz_bounds`, `ice_lines`, `retention`, `stype/ptype_critical_au` → lists;
   `stage`, `hz_verdict`, `topology` → strings) carry `"value"` as that object and document the
   shape; the scalar contract is not forced onto them.
7. No new physics. Every row is arithmetic or an existing `core/` call.
8. Three solar-T conventions coexist in the repo (L uses 5778, Kopparapu 5780, `core/cooling.py`
   IAU 5772). Harmless (0.14% in L) — add a comment so nobody "fixes" one.

---

## §C — Phased build

### Stage 1 — Columnar tree + hide-empty + constants *(~1 day)*
Column model replacing `_oec_tree_item`/`_oec_tree_bits`/`_OEC_TREE_KEYS`; star rows populate
M/R/T; status badges; dimmed errors; §B.5 sizing; D5 expand rule. **Includes hide-empty-columns**
*(r2 #2 — a column-model concern, and without it Stage 1 ships an unreadable sliver)* and the
**B.2 constant move** *(prerequisite for D1 auto-units)*.
**Tests:** T1, T2, T7. **Acceptance:** tau Ceti readable at the default panel width, no horizontal
scrolling. **Baseline (measured 2026-08-01, real cache, `_oec_tree_item` × 20, warm):** tau Ceti 9 nodes
**0.80 ms** · α Cen 11 nodes **0.93 ms** · TRAPPIST-1 9 nodes **0.90 ms** (a cold first call in a
fresh process is ~4–6 ms — Qt/font warm-up, not tree work; measure warm). V5's ceiling is 2× these.
Stage 1b's per-star derived call is inside these figures.

**Two implementation notes worth keeping:**
- The node dict is attached to each item as a **Python attribute** (`item._oec_node`, read via
  `_oec_item_node`), *not* `setData(…, UserRole, node)` — PySide6 marshals a dict through
  `QVariantMap` and hands back a **copy**, so the identity every selection path keys on (§B.3, T3)
  would be silently lost. Verified.
- Every node also carries a **tooltip of all its catalogued fields**, so no value is unreachable in
  the stages before the detail pane exists (`[Fe/H]`, `age`, `inclination` have no column).

### Stage 1b — Star-side derived minimum *(~½ day)* — **new** *(r2 #1)*
`core/oec_derived.py` with `luminosity_lsun` + `hz_bounds` only (both existing `core/` calls, both
gated per D.2), so the tree's L and HZ columns are real at Stage 1 rather than depending on
Stage 4.
**Tests:** T16, plus T8/T9 for those two keys.

### Stage 2 — Detail pane skeleton + registry + selection *(~1½ days)*
`gui/panels/oec_detail.py`; `QSplitter` inside the Data tab (§B.4); `currentChanged` wiring
(§B.3); cold state (D10); planet mode reusing the click-dialog content; the fallback section;
`log_viz_error` wrapping; **pane-position toggle** *(moved here from Stage 6 — r2 #2)*.
**Tests:** T3, T6, T10, T10b, T18. **Gate:** ▲ **code review R1**.

**Built 2026-08-01.** Three things the plan did not anticipate, all now pinned by tests:
- **`tree.blockSignals()` does not block `currentChanged`** — that signal belongs to the
  *selection model*, a separate QObject. The programmatic tree sync must block
  `tree.selectionModel()`, or `_set_oec_selection` re-enters through
  `_on_oec_tree_current` and builds the pane twice. Pinned by
  `test_programmatic_selection_builds_the_pane_exactly_once` (verified to fail against the
  naive version).
- **The value formatters moved into `gui/panels/oec_detail.py`**, and `catalogs.py` imports
  them — the tree and the pane must not be able to render one field two ways. (The reverse
  import direction would be circular.)
- **D7 discharged by deletion:** `_show_oec_planet_dialog` now renders `build_detail_pane`,
  and its hand-written `_OEC_PLANET_DIALOG_LABELS` / `_EXTRA` tables are gone. That is where
  the T17 `periastron` collision actually lived — the dialog labelled the argument of
  periastron (degrees) as "Periastron … AU". The registry labels it
  "Argument of periastron (°)".

**R1 (2026-08-01) — six findings, all fixed, each pinned by a test that fails against the
reviewed code.** The two worth remembering:
- **Every planet mass was labelled `M·sin i`.** The tree guarded on
  `oec_mass_label(node) != "M"`, but that function returns `"M·sin i"` or `"Mass"` — never
  `"M"` — so the branch always fired: **2,581 of 2,844** real masses mislabelled as RV minimum
  masses. The existing T2 covered only the positive case. *Lesson for the remaining stages: test
  the negative case of any label/flag branch.*
- **Neither obvious way to sync the tree cursor is correct.** `tree.blockSignals()` does not
  block `currentChanged` (it belongs to the selection model) → the pane builds twice;
  `selectionModel().blockSignals()` does block it but also suppresses the **view's own** slots,
  so the row moves without being painted as selected or scrolled into view. The answer is a
  re-entrancy flag (`_oec_syncing`) checked in `_on_oec_tree_current`.

The other four: `image` sat in `_HANDLED_ELSEWHERE` but was rendered nowhere (97 planets, and the
fallback could not catch it — the exclusion list must be *proved* rendered, which
`test_every_handled_elsewhere_key_is_actually_rendered` now does); error-bar symmetry was compared
on **strings**, so 997 fields with `"0.06"`/`"0.060"` rendered `+0.060/-0.06`; `hide_empty` had no
control, making a hidden column unrecoverable (a checkbox now ships in Stage 2, ahead of the Stage-6
toolbar); and repeated fields rendered first-value-only, so a binary's `separation` lost its second
unit — `oec_value_cell(..., repeats=True)` is now used by the pane and the tooltip, while the tree
stays first-only for column width.

**V4 spot-checked early** (not deferred to Stage 7) because the B.2 constant move touches
`compute_rv_semi_amplitude`: `rv-semi-amplitude`, `oec-system`, `oec-census` and `oec-status`
are md5-identical against `git stash`.

### Stage 3 — Star dossier blocks *(~1 day)*
Identity (all aliases) · Position & distance · Photometry · Physical · Planets hosted ·
Companions (parent `<binary>`) · Cross-reference buttons.
**Tests:** T4, T5, T15.

### Stage 3b — Binary / system / satellite section sets *(~½ day)* — **new** *(r2 #1)*
The three tags §A.2 promises and §H.1 commits to but r1 never staged. Satellites carry
e / i / periastron / longitude / ascendingnode / tilt at 100% coverage.
**Tests:** T20, T6 extended per tag.

**Stages 3 + 3b built 2026-08-01.** Notes:
- **Rows are dicts, not `(label, value)` tuples** — `{label, value, derived, tip}`. Derived rows
  had to be distinguishable *inside* a shared section (Luminosity sits in Physical, HZ bounds in
  their own block), which a tuple cannot express. `tip` carries the `source` (§D.4 rule 3).
- **The pane needs a context, not just a node.** A star's RA/Dec/distance live on the **system**
  node and its companions on the **parent binary** — neither is reachable from the star.
  `oec_detail.build_context(system)` supplies the parent map; the panel builds it once per result.
- **In a multiple system the position block says so** ("Recorded on: the system as a whole") —
  otherwise the system's shared coordinates read as this component's own.
- **§F's fixture extension lives in `tests/test_oec_view.py`, not `test_oec.py`** (`_VIEW_FIXTURE`
  + `OecViewFixtureBase`): growing the tripwire file's shared fixture changes what every test in
  it sees. It carries the photometry-rich star, the no-`semimajoraxis` planet, the A-type
  (9000 K) host that exercises the D.2 raise path end-to-end, and the full-element satellite.
- **Cross-references ship as one button, not four.** "Look up this star in SIMBAD →" opens a
  `SimbadPanel` in a non-modal window (the `ProjectsPanel._open_real` idiom) — that panel already
  carries Hypatia, GCNS and Gould, so it covers the mockup's four links. It appears only when the
  star has a resolvable designation *and* the panel supplied the callback; `oec_detail` owns no
  navigation.

**V1 / V2 run early (2026-08-01), on the real cache — clean:** the section model built for all
**14,037 nodes** (4,081 systems · 4,300 stars · 5,414 planets · 224 binaries · 18 satellites) with
**0 exceptions, 0 failed sections, 0 un-labelled keys**. Exactly three keys reach the
"Other catalogued fields" fallback — `star.discoveryyear` (45), `system.videolink` (30),
`system.spectraltype` (1) — which is the fallback doing its job, not a gap. Re-run at Stage 7.

### Stage 4a — Star-side derived *(~1 day)*
`log_g`, `mean_density_gcc`, `abs_mag_v`, colours, `angular_diameter_mas`, `light_years`,
`parallax_mas`, `ms_lifetime_gyr`/`stage`, `ice_lines`, `hz_circumbinary`, panel-side
`hyper_limit_au`.
**Gate:** ▲ **code review R2a**.

**Built 2026-08-01.** Deviations and findings, all deliberate:
- **The three scale constants are DERIVED from `core.equations`, not typed.** `_LOG_G_SUN`
  (4.4382), `_RHO_SUN_GCC` (1.4102) and `_ANG_DIAM_MAS` (**9.3009**) come from `_G`,
  `_SOLAR_MASS_KG`, `_SUN_RADIUS_M` and `_M_PER_AU`. **§D.1 pinned the angular-diameter
  coefficient at 9.305**, which implies R☉ = 6.96e8 m; the repo's own `_SUN_RADIUS_M` is the
  IAU-2015 6.957e8, giving 9.3009 — a **0.04%** difference that leaves T8's 2.021 mas anchor
  intact. Typing 9.305 would have introduced a fourth solar-constant convention into a repo that
  already documents three (§D rule 8). Raised here rather than silently re-decided.
- **`compute_hyper_limit_for_spectral_type` returns `{lm, au, matched_class}`, not a float.**
  §D.1 reads as though it returns AU. Formatting the dict raised inside `_fmt_scalar` and — via
  the T18 isolation — took the *entire* HZ block down with it, silently. Found by running the
  real cache, not by a test. Pinned by
  `test_hyper_limit_is_an_au_value_not_the_returned_dict`.
- **A < 0.8 M☉ main-sequence lifetime is a bound, not a figure.** `compute_stellar_evolution`
  extrapolates `T_ms = 10¹⁰·M^−2.5` uncapped, so Kepler-16 B (0.20 M☉) reports **564 Gyr**. The
  pane now renders `> 13.8 Gyr` plus the reason; the raw figure is kept in `value` for
  programmatic consumers. This established a contract refinement worth knowing: **`reason`
  beside a non-None `value` is a QUALIFIER, not an absence**, and the renderer must show it or a
  caveated number reads as an uncaveated one.
- **`compute_ice_lines`' `species` is already a label** ("Water snow line", "NH₃ front") — do not
  append a second noun.
- **D9's note ships.** The binary pane's "Habitable zone (circumbinary)" block states in the pane
  that the HZ *Diagram* tab still uses primary-component light alone, so the two tabs' visible
  disagreement is explained rather than silent.

**R2a (2026-08-01) — four findings, no crash-class bugs, all fixed.** The two structural ones:
- **The star plan had no Description section**, yet `consumed` is seeded from
  `_HANDLED_ELSEWHERE` for *every* tag — so a `<description>`/`<image>` on a star would have been
  removed from the fallback *and* rendered nowhere. Latent only because those keys currently
  appear on planets alone, and invisible to the guard test because it hard-coded
  `"tag": "planet"`. **The guard test is now parameterised over all five tags** — that
  generalisation is the durable fix; the missing section was just its first catch.
- **The Hubble-time qualifier keyed on `low_mass` (M < 0.8) while the display bound keys on the
  value**, and `T_ms` crosses 13.8 Gyr at **≈0.883 M☉** — so the well-populated 0.80–0.88 M☉ band
  showed a bare "> 13.8 Gyr" with nothing to say whether it was a real figure or a caveat. Now
  keyed on the value throughout, with the low-mass range named only when it applies.

The other two: `_oec_view` was rebuilt inside `_on_oec_result`, silently reverting the user's pane
position and toggles on every new search (and Stage 6 adds three more controls to that dict); and
`_oec_derived_for`'s docstring asserted the opposite of its code — it says "never on `id(node)`"
above a literal `key = id(node)`. The behaviour was correct; the docstring now names the three
mechanisms that make it correct (per-result clear + stored strong reference + `hit[0] is node`
re-check) and says that all three are load-bearing.

**V1 re-run after 4a — clean.** All 4,081 systems: **0 exceptions, 0 failed sections**. Derived
coverage measured on the real cache: `light_years`/`parallax_mas` 4,089 · `ms_lifetime_gyr` 4,052 ·
`log_g`/`mean_density_gcc` 3,513 · `luminosity_lsun`/`ice_lines` 3,437 · `angular_diameter_mas`
3,422 · `hz_bounds` 3,390 · `abs_mag_v` 2,134 · `v_minus_k` 1,844 · `b_minus_v` 1,104 · `stage` 444
(only 444 stars carry an age) · `hz_circumbinary` 27 binaries. Every absence carries a stated
reason; the four commonest are "no catalogued age" (3,608), "needs both B and V magnitudes"
(3,196), "needs both V and K" (2,456) and "no catalogued V magnitude" (2,140).

### Stage 4b — Planet-side derived *(~1½ days)*
Recovered `sma_au`, `insolation_searth` + `hz_verdict` (via `compute_habitable_zone_sma`),
`peri_distance_au`/`apo_distance_au`, `density_gcc`, `surface_gravity_g`, escape/retention,
`rv_semi_amplitude_ms`, transit, Hill, `stype/ptype_critical_au`, `topology`.
**Tests:** T8, T9, T17, T19. **Gate:** ▲ **code review R2b**.

**Built 2026-08-01. Every T8 planet anchor reproduces exactly** against the real cache — tau Cet e
S = 1.5898, peri/apo 0.4412 / 0.6348, **K = 0.5522** (the e = 0.18 value; a test that also passes
at 0.5432 is not testing the eccentricity path), tau Cet g recovered a = **0.1329 AU**. α Cen AB
gives μ = 0.4519 and S-type critical 2.795 AU, matching the mockup's 0.452 / 2.78.

Five things found by running real data, not by tests:
- **A `<satellite>` must NOT be routed through `_derive_planet`.** *(Rationale corrected at R3:
  this said the two use different mass units — they do not, both are Jupiter, see §D.0. The
  conclusion stands for a better reason: a moon's `semimajoraxis` is **planet-centric**, so Kepler
  recovery against a stellar mass, the insolation, the Hill radius and the RV amplitude would all
  be answering a question nobody asked.)* `satellite` is deliberately absent from `_DISPATCH`.
- **A binary's `separation` must be selected by its `unit` attribute** (`_oec_field_by_unit`), not
  by `oec_fv`'s first value: the same pair is catalogued in AU *and* arcsec, and Binary S would
  have taken "80" (arcsec) as 80 AU. An arcsec-only separation is **not** converted — that needs
  the distance and yields a *projected* separation, not `a`.
- **A nested binary disqualifies the Kepler-recovery total mass.** α Cen's outer pair is Proxima +
  the AB *binary*, and a `<binary>` carries no mass of its own, so summing the star children gave
  **0.12 M☉ for a ~2.1 M☉ pair** — a recovered `a` wrong by ~2.4×. Now suppressed when any
  component is itself a binary. 61 Cygni (period, no `semimajoraxis`, no nesting) recovers
  correctly: a ≈ 85 AU → S-type critical 10.55 AU.
- **HZ and stability must not short-circuit each other.** A pair with masses but no temperatures
  gets its critical SMAs and no HZ, and vice versa — the original single-`out` early-returns lost
  one whenever the other was ungated.
- **T7's own guard caught a literal in a comment I wrote** (`R_JUP_EARTH = 11.209`). Working as
  designed; the comment now names the constant instead of its value.

**R2b (2026-08-01) — eight findings, all fixed, each pinned by a test verified to fail against
the reviewed code.** The two that mattered:
- **A circumbinary planet was derived from its primary component, not the pair.** `_oec_host_of`
  returned the binary's *first* star, so Kepler III, insolation, RV K and the Hill radius all used
  one star's mass and light. Measured: TIC 172900988 b's recovered a came out **0.7115 AU instead
  of 0.8921 (−20%)**, Kepler-413 b 0.300 vs 0.355, and KIC 7177553 b's insolation read 0.361 S⊕
  where the *same panel's* binary HZ row implied 0.708 — a ~2× self-contradiction one click apart.
  Fixed by `_oec_pair_host_values`: M₁+M₂, L₁+L₂, and the same luminosity-weighted effective Teff
  `compute_circumbinary_hz` uses, so the two rows now agree by construction. It reuses the
  nested-binary guard (a `<binary>` component carries no mass, so the sum must be suppressed) and
  keeps the primary's radius for transit geometry, saying so in `source`.
- **The whole S/P-type stability derivation was invisible.** `_companions_section` read
  `mass_ratio` / `stype_critical_au` / `ptype_critical_au` from the **star's** derived entry, but
  those keys only exist on the **binary's** — and `_derived_rows` skips missing keys silently, so
  a fully unit-tested Stage-4b deliverable rendered nothing anywhere. Now the star's ctx carries
  `parent_derived` (which is what the mockup's "S-type critical SMA 2.78 AU" row wants), and the
  binary tag gained its own **Planet stability** section.

The other six: the map's planet dialog passed a hard-coded ctx, so clicking a planet on the
Architecture map showed catalogue fields only while the tree pane showed the derived block — the
exact divergence the shared builder exists to prevent; an out-of-range eccentricity was **refused**
in `_derive_peri_apo` but silently **zeroed** in `_derive_hill`/`_derive_rv`/`_derive_binary_stability`
(now one `_eccentricity` helper distinguishes catalogued-and-bound · not-catalogued, which is an
assumption and is labelled one · unbound, which is a refusal); msini masses fed density, gravity and
Hill with no qualifier though all are monotonic in mass (261 of 263 affected); **`topology` was
listed in Stage 4b and never implemented** — now a panel-side tree walk in the census vocabulary;
`_oec_field_by_unit` `return`ed instead of `continue`d on an unparseable repeat, so a blank AU row
masked a usable one behind it; and `or 90.0` treated a catalogued **0°** inclination as absent,
reporting maximum K for a face-on orbit.

**Coverage after 4b, measured on the real cache (V3 update):** the recovered `sma_au` reaches
**5,151 of 5,414 planets (95.1%)** against 2,815 catalogued (52.0%) — **+2,336**, close to r2's
predicted 2,490 (the shortfall is planets whose host has no catalogued mass). `insolation_searth`
reaches **4,451 (82.2%)**, far above r2's V3 estimate of 41.6%, precisely because the recovered `a`
feeds it. Then `hz_verdict` 4,400 · transit depth/probability 3,923 · RV K / Hill / moon limit
2,586 · peri/apo 2,165 · density + surface gravity 1,554 · escape velocity + retention 1,042.
**0 exceptions, 0 failed sections** across all 14,037 nodes.

### Stage 5 — Pinned host band *(~½ day)*
Absent for non-planet selections and for rogue planets with no host star.
**Tests:** T11.

**Built 2026-08-02.** `oec_detail.host_band_model(node, ctx)` → the model's new
`host_band` key; `_HostBandWidget` renders it **above** the planet's own title, and the
panel supplies `host_node` / `host_derived` / `on_select_host` through `_oec_detail_ctx`.
tau-Ceti-shaped fixture reproduces the mockup band exactly: `L 0.4602 L☉ · HZ
0.661–1.18 AU · snow line 1.82 AU · 11.91 ly`. Four things worth keeping:
- **The band resolves its host with `_oec_host_of`** — the same resolver the planet's own
  derived layer uses — so a circumbinary planet pins the **pair** and the band's combined
  L is by construction the value its insolation was computed from. Naming the host twice
  through two code paths is exactly how R2b's −20% bug happened; a test asserts the band's
  L equals `_oec_host_values(planet, ctx)["luminosity"]`.
- **A `<binary>` host has no `light_years`** (the distance block is built in `_derive_star`
  from the system node), so a circumbinary band shows L + HZ and no distance. Absence with
  no wrong number — extending `_derive_binary` with a distance block would be a change to a
  reviewed pure module for one display line, so it is deliberately not done here.
- The band honours **`derived`** (bits drop, band stays — it still carries the catalogued
  M/R/T line) and a new **`pin_host`** view key, default True; Stage 6 gives it a checkbox.
- Built inside its own `try/except` in `detail_model`: a band that cannot be assembled
  costs the planet its context line, never its record.

### Stage 6 — Toolbar *(~½ day)*
Tri-state units (D1), errors, derived, pin. *(No "Columns…" button — D8. No Copy/Export — §K.)*
**Tests:** T12a, T12b, T12c.

**Built 2026-08-02.** Units combo (`Auto / M⊕ R⊕ / M♃ R♃`) + Errors · Derived · Hide empty
columns · Pin host star, beside the Stage-2 pane-position combo. Three notes:
- **`_oec_tree_cells` was split out of `_oec_tree_item`** so a toggle re-*texts* the existing
  items (`_oec_refresh_tree_cells`) instead of rebuilding the tree. A rebuild would silently
  drop expansion state, scroll position and the selection — and the pane keys on node
  **identity** (§B.3), so it would also detach. T12a pins `topLevelItem(0)` identity, the
  selection and the expansion across a units change.
- **Column visibility is re-applied after every refresh**, not just on the hide-empty toggle:
  turning Derived off empties L and HZ, and with hide-empty on those columns should then go
  (and come back). Own test.
- Toolbar state is read back out of `_oec_view` when a new result rebuilds the bar, so a
  search does not silently reset the user's choices (the R2a finding, now pinned by
  `test_toolbar_state_survives_a_new_search`).

### Stage 7 — Validation sweeps + docs *(~1 day)* — **new** *(r2 #1)*
V1–V6; record actuals in §G; the five §L doc updates.
**Gate:** ▲ **code review R3** (full diff).

**Run 2026-08-02.** All six sweeps recorded in §G — V1/V2/V4 clean, V3 re-measured, V5 inside
budget, **V6 found and fixed the starved Node column**. Docs updated: `docs/gui-architecture.md`
(an OEC System View note beside the Architecture-map note, the `OecPanel` viz-tab row, and a phase
row), `docs/testing.md` (`test_oec_derived.py`, `test_oec_view.py`, `_oeccheck.py`),
`docs/star-databases.md` (a System View bullet under opt 7), `completed_plans/PHASE_OEC_PLAN.md`
(a follow-up pointer). **`tests/test_oec.py` was never edited — §M stays empty**, so the §0
tripwire never fired in seven stages.
**R3 (2026-08-02) — seven findings, all fixed, the five code ones each pinned by a test verified
to fail against the reviewed code (`R3RegressionTests`).** The two that mattered:
- **Clicking the pinned band destroyed the band inside its own event handler.** `_oec_click` →
  `_set_oec_selection` → `_render_oec_detail` → `QScrollArea.setWidget()`, which deletes the
  previous pane **synchronously** — including the widget being clicked; the following
  `super().mouseReleaseEvent(event)` then ran on a freed C++ object
  (`RuntimeError: Internal C++ object (_HostBandWidget) already deleted`, reproduced). **Every
  real click on Stage 5's headline interaction hit this**, and the test did not: it called
  `band._oec_click()` directly, skipping the event path entirely. Fixed with
  `QTimer.singleShot(0, …)` — the idiom the Architecture map already uses for exactly this reason,
  which the plan quotes in §C Phase 3b and I did not apply. *Lesson: when a handler's callback can
  rebuild the widget tree, test the **event**, not the callback.*
- **Satellite mass/radius were wrong by 318×/11×** — the §D.0 error, written up above.

The other five: the release handler fired on any mouse button and on a press-drag-off-and-release
(Qt delivers a release to whichever widget took the press); the band's `QFrame {…}` stylesheet also
matched its child labels (**QLabel subclasses QFrame**), drawing a second rounded box round the
title — now an `#oecHostBand` object-name selector; the band's HZ bit checked only the *inner*
bound then formatted the outer, so an absent outer would have cost the planet its whole context
line via `detail_model`'s blanket guard; three docs linked to `completed_plans/OEC_SYSTEM_VIEW_PLAN.md`
while the file was still at the repo root (fixed by this move); and `_build_oec_tree`'s docstring
still described the Stretch sizing the V6 fix had replaced.

**Remaining:** nothing — R3 is run and this file has moved to `completed_plans/`. **Not committed**
(the user commits).

**Total: 7–9 days** *(r1's 5 was not credible — r2 #9)*.

---

## §E — Decisions — locked 2026-08-01

| # | Decision | Locked as |
|---|---|---|
| **D1** | Default units | **Auto** — M⊕ below 0.1 M♃, else M♃, applied **per node**; toolbar is tri-state `Auto / M⊕ / M♃`. Applies to catalogued planet mass/radius only. |
| **D2** | Default pane position | **Right**, session-only. |
| **D3** | Derived on by default | **Yes** — violet + badge makes provenance unambiguous. |
| **D4** | Errors on by default | **Yes, inline dimmed.** |
| **D5** | Expand rule | `expandAll()` ≤ 25 nodes, else expand to star level. |
| **D6** | Persist toolbar choices | **No** — no `QSettings` exists in `gui/` today. Session-only panel state. |
| **D7** | Keep the planet click-dialog | **Yes** — the map has no pane; both render from one shared section builder. |
| **D8** | Column chooser | **Deferred** — only worth having with D6's persistence. Ship no dead button. |
| **D9** | Circumbinary HZ | Use `compute_circumbinary_hz` (behind the D.2 gate). **Plus:** the HZ *diagram* tab keeps its primary-component-light limitation, so the pane must carry a visible note that the two differ — *(r2 #8: a silent disagreement between two tabs of one panel is worse than either behaviour)*. |
| **D10** | Cold state | **Auto-select the primary host star** on build. *(new — r2 #3)* |
| **D11** | `tidal_lock_gyr` | **Dropped from v1** — invented rotation period + fictitious radius (D.3). *(new — r3 #5)* |
| **D12** | Copy TSV / Export CSV | **Deferred to §K** — the only file-write path in the change, and the least valuable item in §A. *(new — r2 #8)* |

---

## §F — Tests

`tests/test_oec_derived.py` (pure, always runs) and `tests/test_oec_view.py` (Qt-gated,
`_oec_mpl_ok()` pattern at `tests/test_oec.py:597`). Fixture: `OecTestBase` extended with a
photometry-rich single star, a no-`semimajoraxis` planet, a hot (A-type) host, and a satellite.

**Cache gate** *(r2 #4)*: real-cache assertions live behind `tests/_oeccheck.py`, mirroring
`_dustcheck.py` / `_netcheck.py`. The fixture half of every test always runs; a fresh checkout with
no `data/oec/systems.xml.gz` skips cleanly rather than failing.

| # | Test | Asserts |
|---|---|---|
| **T1** | Tree columns per tag | Star row populates M/R/T; planet row P/a/e; no bleed. |
| **T2** | Badges + M·sin i | Multi-status renders both; msini mass keeps the `M·sin i` label. |
| **T3** | **Selection maps to its own node** | Every fixture node, clicked, renders *that* node's record — asserted on content identity, not index arithmetic. **Plus keyboard**: arrow-key `currentChanged` updates the pane. |
| **T4** | All aliases | A 22-name star renders 22. |
| **T5** | Companions | Binary component shows parent a/e/P/i/PA/node; single star shows the "no companion" line and no empty section. |
| **T6** | **No field is droppable** | Registry ∪ fallback covers every walker key, per tag — fixture always, real cache behind the gate. |
| **T7** | **One conversion constant, by value** | No `317.828` / `11.209` literal outside the canonical definition in `core/shared.py`. **Scoped to non-test source under `core/` and `gui/`** — `tests/test_query_phase_t.py` lines 388/445/456 pass `317.828` as an *argument* value (1 M♃ expressed in M⊕), not as a copy of the constant, and must not trip the guard. Asserted on the value, not the name *(r3 #6 — a name-based test passes against `_M_JUP_EARTH`)*. |
| **T8** | Derived anchors | Sol-like R=1,T=5778 → L=1.000. tau Ceti: L=0.4602 ✓, log g=4.533 ✓, ρ=2.214 ✓, M_V=5.688 ✓, HZ 0.661–1.182 ✓, snow line 1.82 ✓, θ=2.021 mas. Planet e: S=1.590 ✓, peri/apo 0.441/0.635 ✓, **K = 0.552 with e=0.18** *(r1's 0.54 was the e=0 value — verified 0.5522 vs 0.5432)*. Planet g: recovered a = 0.1329 ✓. |
| **T9** | Derived contract | Every D.2 row: `None` + non-empty `reason`, no raise, no 0. Includes **T=10 700 K does not raise**, mass 0.05 M☉, e=1.2, distance 0, and an `{"error"}` dict never reaching the renderer. Every entry carries `source`. Catalogued never overwritten. |
| **T10** | **Pane survives a recenter** | After `_rebuild_after_focus`, pane exists, tree still `_data_tabs` index 0. |
| **T10b** | Layout interaction | Splitter inside the `AlignTop` `QScrollArea` with the Matched-on header + Host combo present gives the tree a non-zero height. *(r2 #6)* |
| **T11** | Pinned band | Present for a star-hosted planet; absent for rogue planets and star/system/binary; click selects the host. |
| **T12a** | Units | Tri-state; Auto picks M⊕ below 0.1 M♃ **per node**; changes value + per-row header unit; **does not rebuild the tree** — asserted concretely via an unchanged `topLevelItem(0)` identity *(r2 #4)*. |
| **T12b** | Toggles | Derived-off removes every derived row; errors-off; hide-empty removes an unpopulated column. |
| **T12c** | Repo shape | No `QSettings` import anywhere in the change (D6). |
| **T15** | **Star dossier completeness** | Selecting a star renders all eight named blocks (assert on section titles). *(covers criterion 3 — r2 #4)* |
| **T16** | **Star row derived cells** | Tree star row exposes non-empty L and HZ cells. *(covers criterion 3)* |
| **T17** | `periastron` collision | Catalogued `periastron` renders as "Argument of periastron (°)" with the catalogued degrees; the derived distance uses `peri_distance_au` and is not confused with it. *(r3 #3)* |
| **T18** | Pane fault isolation | A section builder raising on one node logs via `log_viz_error` and does not blank the pane. |
| **T19** | Derived cache correctness | Two searches back-to-back; the second system's derived values are its own. *(r2 #5)* |
| **T20** | Binary / system / satellite sections | A satellite renders all six of its 100%-coverage orbital elements. *(r2 #1)* |
| **T14** | Regression | `tests/test_oec.py` passes unmodified (§0 tripwire; any permitted edit recorded in §M). |

---

## §G — Validation

| # | Sweep | Expected |
|---|---|---|
| **V1** | Build the section model headlessly for all 4,081 systems / 4,300 stars / 5,414 planets / 224 binaries / 18 satellites — **via the pure path, see below** | 0 exceptions, 0 un-labelled keys |
| **V2** | Per-tag diff: walker keys vs. section-model keys | empty |
| **V3** | Derived coverage — **re-measured 2026-08-01, r1's figures were estimates** | star L (R+T) **80.0%** (3440/4300) · planet density (M+R) **29.8%** (1616/5414) — *r1 said 45%* · planet has `a` **52.0%** (2815) · planet `a` **and** host L **41.6%** (2253) — *r1 conflated this with the 52%* · planet P but no `a` **46.0%** (2490, the recovered-`a` gain) |
| **V4** | JSON before/after for `oec-system` / `oec-planet` / `oec-search` / `oec-census` **and `rv-semi-amplitude`** | byte-identical. The Phase-T1b calculator is included because the B.2 constant move edits `core/calculators.py:561` (`compute_rv_semi_amplitude`), which `query.py` exposes and the sibling scifiWorldBuilding repo consumes — the value is unchanged (317.828), so this gate proves it. |
| **V5** | Timing | Pane build < 50 ms. Tree build **no more than 2× the Stage-1 baseline** *(r1's absolute 250 ms was vacuous — a system is ~15 nodes)* |
| **V6** | Visual pass | α Cen (deep hierarchy) · tau Ceti (7 planets, retracted) · Kepler-16 (circumbinary) · 61 Cygni (planetless, binary with P but no a) · a rogue planet · TRAPPIST-1 · **an A-type or WD host (the D.2 raise path)** |

**Edge shapes:** planetless · rogue (no band, no insolation) · circumbinary (D9) · no spectral type ·
non-OBAFGKM host · msini mass · bound-only field (`e ≤ 0.35`) · `periastron` present as degrees.

### Measured actuals — Stage 7, 2026-08-02 (real cache, pure path)

| # | Result |
|---|---|
| **V1** | **PASS.** 14,037 nodes (4,081 system · 4,300 star · 5,414 planet · 224 binary · 18 satellite): **0 exceptions, 0 failed sections, 0 nodes with no rendered row.** |
| **V2** | **PASS.** Exactly three keys reach the fallback — `star.discoveryyear` (45), `system.videolink` (30), `system.spectraltype` (1) — unchanged since Stage 3b; the fallback doing its job, not a gap. |
| **V3** | Recovered `sma_au` **5151** · `insolation_searth` 4447 · `hz_verdict` 4399 · `light_years`/`parallax_mas` 4089 · `ms_lifetime_gyr` 4052 · transit depth/prob 3923 · `log_g`/`mean_density_gcc` 3513 · `luminosity_lsun`/`ice_lines` 3437 · `angular_diameter_mas` 3422 · `hz_bounds` 3390 · RV K / Hill / moon limit 2584 · peri/apo 2165 · `abs_mag_v` 2134 · `v_minus_k` 1844 · density + gravity 1554 · `b_minus_v` 1104 · escape + retention 1042 · `stage` 444 · S/P-type + μ 156 · `hz_circumbinary` 27. **Stage 5 band:** 5,370 planets pin a star · 39 pin a pair · **5 rogue planets correctly get none**; 5,343 bands carry derived bits. |
| **V4** | **PASS — byte-identical** against `f2b91e4` (the pre-Stage-1 commit) in a worktree sharing `data/`: `oec-system` (α Cen, tau Ceti), `oec-planet` (tau Cet e, Kepler-16 b), `oec-search`, `oec-census`, and **`rv-semi-amplitude`** (two forms, exercising the B.2 constant move). `oec-status` differs in one field only — `cache_path`, which echoes the worktree's own path; an artifact of how the comparison was run, not of the change. |
| **V5** | **PASS.** Tree build, warm: tau Ceti **0.77 ms** · α Cen **1.34 ms** · TRAPPIST-1 **0.97 ms** (Stage-1 baseline 0.80 / 0.93 / 0.90; ceiling 2×). Detail pane: model 0.38 ms, full widget **13.7 ms** for the 53-row tau Ceti dossier — well inside the 50 ms budget. Toolbar refresh (re-text, no rebuild) 0.5–1.4 ms. **Measure warm:** the first figures taken in a cold process read 4–5× high (Qt/font/import warm-up), the same caveat the Stage-1 baseline records. |
| **V6** | **PASS with one defect found and fixed.** All seven shapes build with 0 failed sections: α Cen (depth-2, 3 stars/5 planets) · tau Ceti (7 planets incl. retracted) · Kepler-16 (band on the **pair**) · 61 Cygni (planetless binary, no band) · PSO J318.5-22 (rogue → no band) · TRAPPIST-1 (2559 K → snow line but **no HZ**, the D.2 gate visible in the band) · Fomalhaut (A-type 8590 K → same). **The defect:** with the Stage-2 detail pane taking its share of the width, the Node column's `Stretch` mode received only ~95 px and every tau Ceti planet rendered as `t…` — Stage 1's own acceptance line, broken by a later stage. Fixed by making the Node column **Interactive at 300 px** (§B.5's "drop the fixed width" was right about the *numeric* columns, wrong about column 0); pinned by two tests. |

### How to run V1 — the PURE path, never a panel per system

**Build the sweep out of `core.databases._oec_node` + `oec_detail.build_context` +
`detail_model`, with `core.oec_derived.derive` called directly.** Do **not** construct an
`OecPanel` per system: each one creates a `QTreeWidget`, a splitter, a detail pane and a
matplotlib Architecture canvas, and Qt reclaims those through `deleteLater()` — which needs
an event loop a plain script never runs. Doing it over 4,081 systems exhausted an 8 GB WSL box
on 2026-08-01 and the machine had to be killed. The pure path walked all **14,037 nodes**
comfortably and is what produced every coverage figure in this plan.

The three panel-only values (`hyper_limit_au`, `topology`, and the pair-host values for a
circumbinary planet) need a panel — **sample a handful of systems** for those, don't sweep them.
And **run V1 alone**: the full suite by itself is ~2.5 GB on this machine.

---

## §H — Success criteria

0. **Decisions honoured.** D1 auto-units per-node and panel-side; D6 no `QSettings`, no
   "Columns…" button; D11 no tidal-lock row; D12 no export path.
1. **Coverage.** V2 diff empty. The six fields the mockup called out as hidden are all reachable:
   planet `description` (93.2%), `lastupdate` (99.9%), `discoverymethod`/`discoveryyear` (99.8%),
   system RA/Dec (99.98% — the Sun row has neither), star `magV`/`magK` (50.3/65.1%), all six
   satellite orbital elements (100%).
2. **Selection correctness.** T3 passes for every fixture node, mouse **and keyboard**.
3. **Star-first.** T16 (tree row L + HZ) **and** T15 (all eight dossier blocks).
4. **Context retention.** T11.
5. **Provenance.** T9 — no derived value without violet + `source`; missing input yields a stated
   reason; one toggle removes the class.
6. **No collateral change.** T14; V4 byte-identical; T10/T10b.
7. **Suite green.** No new failures; ~48 new tests added. *(r1 hardcoded "2385 existing" — a
   moving target that would fail for unrelated reasons.)*
8. **Performance.** V5, relative to the Stage-1 baseline.
9. **Contract holds at the edges.** T9's full D.2 table passes — in particular a 10 700 K host
   returns a reason instead of raising.

---

## §I — Code review placement

| Point | Review? | Why |
|---|---|---|
| Stage 1 / 1b | **No** | Mechanical; covered by T1/T2/T7/T16. R1 reviews the working diff, so Stage 1's code is covered there anyway. |
| **Stage 2** | ▲ **R1 — `/code-review`** | Every structural decision lands here: splitter-vs-tab (§B.4), the `currentChanged` selection convergence (§B.3), the registry fallback contract. Cheapest moment to catch a bad seam. |
| Stage 3 / 3b | **No** | Additive builders over a reviewed registry. |
| **Stage 4a** | ▲ **R2a — `/code-review`** | Star-side formulas + the D.2 gates. |
| **Stage 4b** | ▲ **R2b — `/code-review` + numeric spot-checks** | Planet-side: unit conversions in both directions, the msini/inclination interaction, the `periastron` collision. |
| Stage 5 / 6 | **No** | Low-risk UI state; T11–T12c. |
| **Stage 7** | ▲ **R3 — full-diff review** | Final pass. |

**Why 4a/4b split** *(r2 #7)*: r1 reviewed ~25 formulas once, at the end, while itself arguing the
bug class here is "plausible wrong numbers… the class tests catch least well". Two reviews at half
the surface each. **Review checklist for R2a/R2b:** every §D row cites either an existing `core/`
function or a numeric anchor; no formula reimplements an existing one; every D.2 gate present.

**Not applicable:** `/security-review` — no network, no new input parsing, no credentials, and
with D12 no file-write path at all.

---

## §J — Risks

| Risk | Mitigation |
|---|---|
| Pane destroyed by `_rebuild_after_focus` | Splitter-inside-tab (§B.4); T10 |
| Splitter × `QScrollArea`/`AlignTop` layout | §B.5 sizing decisions; T10b |
| Selection desync across three selectors | §B.3 single attribute + `currentChanged`; T3 |
| Derived mistaken for catalogued | Violet + badge + `source` + toggle; T9 |
| Wrong physics / units | Reuse `core/` fns; D.2 gates; T8 anchors; R2a+R2b |
| Stale derived cache → wrong numbers | Cache cleared in `_on_oec_result` (D.4 r4); T19 |
| Unreadable panel mid-build | hide-empty in Stage 1, pane-position in Stage 2; per-stage acceptance line |
| A future OEC field goes missing | Registry fallback; T6 + V2 |
| **T14 tripwire blocks legitimate work** | §0 escape clause: display-string edits allowed, called out in review, recorded in §M |
| **OEC cache absent / stale** | `tests/_oeccheck.py` gate; fixture half always runs |
| **§D volume (24 keys) underestimated** | Split 4a/4b; D11 drops one; two rows collapse into existing `core/` calls |
| Scope creep into `query.py` | V4 byte-identical gate |

---

## §K — Non-goals / follow-ups

- **Copy TSV / Export CSV** (D12) — the only write path; easiest to add later.
- **`tidal_lock_gyr`** (D11) — needs a Love-number refinement and a defensible rotation-period
  assumption.
- **Column chooser + persisted preferences** — blocked on D6.
- Mockup options **C / D / E** (tier tables, dossier cards, planet matrix) — additive tabs, decide
  after this ships.
- **Exposing the derived layer via `query.py`** — `core/oec_derived.py` is written to allow it.
- **Planet artwork thumbnails** (`image`, 97 planets) — needs a network-fetch policy.
- **Circumbinary HZ in the HZ *diagram* tab** — D9 fixes the pane and notes the difference; fixing
  the diagram is its own change.

## §L — Docs to update (Stage 7)

`docs/star-databases.md` (OEC Display bullet) · `docs/gui-architecture.md` (`OecPanel` + phase
table) · `docs/testing.md` (two new test files + `_oeccheck.py`) ·
`completed_plans/PHASE_OEC_PLAN.md` (cross-reference) · move this file to `completed_plans/`.

## §M — Permitted `tests/test_oec.py` edits

**None, across all seven stages.** The §0 tripwire never fired: `tests/test_oec.py` is
byte-unchanged, and every new assertion went into `tests/test_oec_view.py` /
`tests/test_oec_derived.py`.
