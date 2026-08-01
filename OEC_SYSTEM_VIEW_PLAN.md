# OEC System View — Star-First Master/Detail (option 7 Data tab)

**Status:** PLANNED — not started. Design approved 2026-08-01 against
`OEC_TREE_VIEW_MOCKUP.html` (★ Recommended tab).
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

- [ ] **Stage 1** — Columnar tree + hide-empty + B.2 constant move (T1, T2, T7)
- [ ] **Stage 1b** — Star-side derived minimum: `luminosity_lsun` + `hz_bounds` (T16, T8/T9 subset)
- [ ] **Stage 2** — Detail pane + registry + selection ▲ **review R1** (T3, T6, T10, T10b, T18)
- [ ] **Stage 3** — Star dossier blocks (T4, T5, T15)
- [ ] **Stage 3b** — Binary / system / satellite sections (T20, T6 per tag)
- [ ] **Stage 4a** — Star-side derived ▲ **review R2a**
- [ ] **Stage 4b** — Planet-side derived ▲ **review R2b** (T8, T9, T17, T19)
- [ ] **Stage 5** — Pinned host band (T11)
- [ ] **Stage 6** — Toolbar (T12a, T12b, T12c)
- [ ] **Stage 7** — Validation sweeps V1–V6 + §L docs ▲ **review R3 (full diff)**

**Before writing code, read in this order:** §0 (posture) → §B (seams — §B.4 is the highest-risk
integration point) → §E (locked decisions, D1–D12) → the stage's own §C entry → its tests in §F.
For derived work also read §D.2 (domain gates) in full.

**Standing rules while building:**
- Run tests as `venv/bin/python -m pytest` — a bare `pytest` uses system Python and fails at collection.
- The approved visual target is `OEC_TREE_VIEW_MOCKUP.html`, ★ Recommended tab.
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

planet mass/radius **Jupiter** · star mass/radius **Solar** · satellite mass/radius **Earth** ·
sma **AU** · period **days** · distance **parsecs** · temperature **K**.

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
scrolling. **Baseline:** record today's tree build time here for §H.8.

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

### Stage 3 — Star dossier blocks *(~1 day)*
Identity (all aliases) · Position & distance · Photometry · Physical · Planets hosted ·
Companions (parent `<binary>`) · Cross-reference buttons.
**Tests:** T4, T5, T15.

### Stage 3b — Binary / system / satellite section sets *(~½ day)* — **new** *(r2 #1)*
The three tags §A.2 promises and §H.1 commits to but r1 never staged. Satellites carry
e / i / periastron / longitude / ascendingnode / tilt at 100% coverage.
**Tests:** T20, T6 extended per tag.

### Stage 4a — Star-side derived *(~1 day)*
`log_g`, `mean_density_gcc`, `abs_mag_v`, colours, `angular_diameter_mas`, `light_years`,
`parallax_mas`, `ms_lifetime_gyr`/`stage`, `ice_lines`, `hz_circumbinary`, panel-side
`hyper_limit_au`.
**Gate:** ▲ **code review R2a**.

### Stage 4b — Planet-side derived *(~1½ days)*
Recovered `sma_au`, `insolation_searth` + `hz_verdict` (via `compute_habitable_zone_sma`),
`peri_distance_au`/`apo_distance_au`, `density_gcc`, `surface_gravity_g`, escape/retention,
`rv_semi_amplitude_ms`, transit, Hill, `stype/ptype_critical_au`, `topology`.
**Tests:** T8, T9, T17, T19. **Gate:** ▲ **code review R2b**.

### Stage 5 — Pinned host band *(~½ day)*
Absent for non-planet selections and for rogue planets with no host star.
**Tests:** T11.

### Stage 6 — Toolbar *(~½ day)*
Tri-state units (D1), errors, derived, pin. *(No "Columns…" button — D8. No Copy/Export — §K.)*
**Tests:** T12a, T12b, T12c.

### Stage 7 — Validation sweeps + docs *(~1 day)* — **new** *(r2 #1)*
V1–V6; record actuals in §G; the five §L doc updates.
**Gate:** ▲ **code review R3** (full diff).

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
| **V1** | Build the section model headlessly for all 4,081 systems / 4,300 stars / 5,414 planets / 224 binaries / 18 satellites | 0 exceptions, 0 un-labelled keys |
| **V2** | Per-tag diff: walker keys vs. section-model keys | empty |
| **V3** | Derived coverage — **re-measured 2026-08-01, r1's figures were estimates** | star L (R+T) **80.0%** (3440/4300) · planet density (M+R) **29.8%** (1616/5414) — *r1 said 45%* · planet has `a` **52.0%** (2815) · planet `a` **and** host L **41.6%** (2253) — *r1 conflated this with the 52%* · planet P but no `a` **46.0%** (2490, the recovered-`a` gain) |
| **V4** | JSON before/after for `oec-system` / `oec-planet` / `oec-search` / `oec-census` **and `rv-semi-amplitude`** | byte-identical. The Phase-T1b calculator is included because the B.2 constant move edits `core/calculators.py:561` (`compute_rv_semi_amplitude`), which `query.py` exposes and the sibling scifiWorldBuilding repo consumes — the value is unchanged (317.828), so this gate proves it. |
| **V5** | Timing | Pane build < 50 ms. Tree build **no more than 2× the Stage-1 baseline** *(r1's absolute 250 ms was vacuous — a system is ~15 nodes)* |
| **V6** | Visual pass | α Cen (deep hierarchy) · tau Ceti (7 planets, retracted) · Kepler-16 (circumbinary) · 61 Cygni (planetless, binary with P but no a) · a rogue planet · TRAPPIST-1 · **an A-type or WD host (the D.2 raise path)** |

**Edge shapes:** planetless · rogue (no band, no insolation) · circumbinary (D9) · no spectral type ·
non-OBAFGKM host · msini mass · bound-only field (`e ≤ 0.35`) · `periastron` present as degrees.

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

*(none yet — record any display-string edit here with its review sign-off, per §0)*
