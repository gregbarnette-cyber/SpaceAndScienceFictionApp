# Phase OEC — Open Exoplanet Catalogue Rebuild (menu option 7)

> **Status: Planned (2026-07-17).** Ground-up rebuild of the OEC feature removed in `7dff32a`
> ("remove old OEC functions and move to pytest"). Menu slot **7** was held free for this. The only
> retained scaffolding is `core.databases._load_oec()` + the `_OEC_DATA` cache — both rewritten here.
>
> **The lesson from last time.** The prior feature was built *without evaluating the OEC XML structure*,
> and OEC is **not** shaped like the other Star Databases options — it is a recursive
> `system → binary → star → planet` hierarchy, not a flat "star row + planet rows" table. The old
> `compute_oec` did `system_elem.iter("star")`, which flattens all multiplicity/hierarchy away and
> **silently drops the 44 planets that attach to a `<binary>` or a `<system>` rather than a `<star>`**.
> The "SIMBAD→OEC matching never worked" symptom was real but secondary; the deeper defect was a data
> model that could not represent the data. This plan is built on a full structural evaluation (below)
> **before** any code.

## Build posture

- **Surfaces: CLI + GUI + `query.py`** (all three), unlike the pure-`query.py` calculator phases.
  All three consume **one** object — the recursive node dict returned by `compute_oec` — so the model
  is built once and serialized/rendered three ways.
- **Self-validating** (Phase-H/P contract): not-found / bad input → `{"error": str}` (exit 1 in
  `query.py`); argparse → exit 2; success → exit 0. The GUI red-error label and CLI message reuse the
  same `{"error"}` returns.
- **Per-phase HTML approval gate (the workflow the requester asked for).** Before building **each** of
  the three phases, generate a self-contained HTML file (Artifact) enumerating that phase's functionality
  as an approval checklist. The user reviews/approves it; only then is the phase built. Issues surfaced
  while writing this plan (see "Open issues" §) seed the Phase-1 HTML file. This gate is what avoids
  rebuilding.

---

## §A — Structural evaluation (verified against the live catalogue 2026-07-17)

**Source:** `https://github.com/OpenExoplanetCatalogue/oec_gzip/raw/master/systems.xml.gz` — 1.05 MB
gzipped, downloads in ~2 s, parses on the py3.12 venv with stdlib `gzip` + `xml.etree.ElementTree`.
Actively maintained (site "last update" = today). Scale: **4,081 systems / 4,300 stars / 5,414 planets
/ 46,290 `<name>` alias tags.** (astroquery's `open_exoplanet_catalogue` module is *not* used — its
`xml_element_to_dict` calls the py3.9-removed `.getchildren()` and is broken; we parse directly.)

### A.1 — Where planets attach (a flat model drops 44 of them)

| Parent tag | Count | Meaning |
|---|---|---|
| `<star>` | 5,370 | normal — orbits one star |
| `<binary>` | 39 | **circumbinary (P-type)** — orbits two stars |
| `<system>` | 5 | **rogue / free-floating** — no star (WISE 0855, PSO J318.5-22, SIMP0136+0933, SDSS J1110+0116, CFBDSIR2149) |

### A.2 — Multiplicity & nesting (a flat star list loses all of this)

- Stars/system: 1×3895, 2×146, 3×29, 4×5, **6×1**. Starless: 5 (rogues).
- `<binary>` nesting depth: 0×3900, 1×146, 2×33, **3×2**.
- `<binary>` nodes carry **their own** relative-orbit elements (`separation`, `semimajoraxis`,
  `eccentricity`, `period`, `positionangle`, `periastron`, `periastrontime`, `ascendingnode`,
  `meananomaly`, `longitude`) + combined `magB/V/R/I/J/H/K`.

### A.3 — Numeric layer is attribute-rich (also skipped last time)

- `errorminus`/`errorplus` on ~45k values; `upperlimit` (233) / `lowerlimit` (120) — **values can be
  limits, not points**.
- **`unit` varies and matters**: `separation` is given in **AU *or* arcsec** (197 vs 154 occurrences,
  and *both* on the same node — 40 Eri / ε Ind / 16 Cyg); `transittime`/`periastrontime` in BJD/HJD/JD/MJD.
- `<list>` (planet status) has 10 values: Confirmed 5288, S-type 193, Controversial 100, **P-type 39**,
  open-cluster 27, Retracted 12, Solar System 9, KOI 5, **Orphan 2**, globular-cluster 1.

### A.4 — Nine reference systems (the fixture topology set)

| System | OEC topology | Proves |
|---|---|---|
| **Alpha Centauri** | `system → binary(sma 15000 AU) → [ Proxima(3 planets), binary "α Cen"(sma 23.5, e 0.52) → (A, B→2 planets) ]` | A/B **and Proxima share one `<system>`**; outer binary **unnamed**; nested grouping |
| **Tau Ceti** | `system → star → 7 planets` | trivial single-star |
| **47 UMa** | `system → star → 3 planets` | trivial single-star |
| **40 Eridani** | `system → binary(83.7″ / 417 AU) → [ HD 26965(planet b), binary "40 Eri BC"(P 84040) → (B: **DA2.9 WD**, C: M4.5V) ]` | hierarchical triple; planet on primary; white-dwarf `<star>` |
| **Epsilon Indi** | `system → binary(403″ / 1460 AU) → [ ε Ind A(planet Ab), binary "ε Ind B" → (**Ba: T1V**, **Bb: T6V**) ]` | brown dwarfs modeled as `<star>` |
| **Delta Pavonis** | **absent** | OEC is a *planet* catalogue — planetless star is not a match failure |
| **61 Cygni** | `system → binary(unnamed, P 247634 yr) → (A K5V, B K7V)` — **zero planets** | matched system can have no `<planet>` |
| **36 UMa** | **absent** | planetless → absent |
| **16 Cygni** | `system → binary(39.56″/836.5 AU) → [ binary "16 Cyg AC"(3.4″/72 AU) → (A, C), B → planet b ]` | depth-2 nesting; separation in both units |

**Expectation this sets (must be in docs + the "not found" message):** OEC holds only systems with
planets/candidates. A planetless star (Delta Pav, 36 UMa) returning "not in OEC" is **correct**, not a
lookup bug — this alone explains much of what looked like "matching never worked."

---

## §B — Core data model (the foundation for all three surfaces)

### B.1 — Recursive node model — **generic (complete) field capture**

`compute_oec(...)` returns a nested dict rooted at the **system node**; the GUI tree, CLI tree, and
`query.py` `oec-system` all consume this same object.

**Design decision (D7, 2026-07-17): capture *every* non-container child field generically — not a
curated allow-list.** A field census across the whole catalogue showed a curated subset silently drops
many real fields (esp. on planets: `description`, `lastupdate`, `periastron`, `transittime`,
`spinorbitalignment`, `impactparameter`, mags, `satellite`, …). Instead `_oec_node(elem)` walks **all**
child elements: each non-container child becomes a field via `_oec_num()`; a repeated tag collapses to a
**list** (e.g. `separation` in AU + arcsec; **and `<list>` — a planet in a binary carries "Confirmed
planets" *and* "Planets in binary systems, S-type"**); `<name>` tags collect into `names[]`; recognized
containers recurse into `children[]`. **Consumer rule (mockup lesson §F.1): any field may be a list, so
every reader must use a first-or-list accessor — never `field.value` directly** (this was a real crash).
So the **model + JSON are always complete and future-proof**; the *display*
layer (GUI/CLI) curates a **headline** set per node and puts the remainder under a "more fields" expander
— nothing is ever dropped from the data, only from the glance view.

`_oec_num(elem)` → `{value, errorminus, errorplus, upperlimit, lowerlimit, unit, type}` (only the present
attributes; `value` is the text). Notable attributes it must preserve:
- **`type` on `<mass>`** — `msini` marks an *M·sin i* minimum mass (RV), not a true mass (266 planets);
  the display labels it **"M·sin i"**. Also `type` on `<name>` (`pri` = primary) and `spinorbitalignment`.
- **`unit`** on `separation` (AU/arcsec), `transittime`/`periastrontime`/`maximumrvtime` (BJD/HJD/JD/MJD).

Missing/empty values are simply absent from a node's `fields` (no fabricated nulls). Complete inventory of
child fields seen per node (from the census — all captured generically):
- **system** — `rightascension`, `declination`, `distance`, `constellation`, `videolink`;
  rogue-only `spectraltype`, `magJ/H/K`.
- **binary** — `separation` (list), `semimajoraxis`, `eccentricity`, `period`, `positionangle`,
  `inclination`, `periastron`, `periastrontime`, `ascendingnode`, `meananomaly`, `longitude`,
  `transittime`, `magB/V/R/I/J/H/K`.
- **star** — `spectraltype`, `mass`, `radius`, `temperature`, `metallicity`, `age`,
  `magU/B/V/R/I/J/H/K`, `discoveryyear`, (rare) `asteroid`.
- **planet** — `mass` (± `type=msini`), `radius`, `period`, `semimajoraxis`, `eccentricity`,
  `inclination`, `temperature`, `periastron`, `periastrontime`, `ascendingnode`, `meananomaly`,
  `longitude`, `transittime`, `positionangle`, `impactparameter`, `spinorbitalignment`, `tilt`,
  `maximumrvtime`, `separation`, `metallicity`, `age`, `spectraltype`, `magH/J/K/I`, `discoverymethod`,
  `discoveryyear`, `lastupdate`, `istransiting`, `new`, `list` (status), `description`,
  `image`/`imagedescription`.

**`<satellite>` (moons, 18 in catalogue) are captured as nested child nodes under a planet** — a fifth
node kind (a leaf "moon"), rendered like a planet. No longer deferred; generic capture handles it.

Builder: `_oec_node(elem)` is **one** generic recursive extractor (the tag is recorded on each node) —
not four hand-written ones — so `system`/`binary`/`star`/`planet`/`satellite` all flow through the same
complete capture. `system`/`binary` are field-bearing, never pass-through containers.

### B.2 — Name matching (the visible fix)

`_norm_oec_name(s)`: lowercase → strip whitespace, `-`, `_`, `*`, leading `V*`/`* ` prefixes → drop a
trailing planet letter when indexing star/planet aliases. `_load_oec()` builds `{norm_key: system_elem}`
over **all** `<name>` tags (system + binary + star + planet), first-wins. Candidates are normalized the
same way, so `"HD 209458"` ≡ `"HD209458"`, `"K2 18"` ≡ `"K2-18"`. (Gaia release mismatch — SIMBAD emits
DR3, OEC stores DR2 — is unfixable by string match but irrelevant: HD/HIP/GJ aliases cover every host.)

### B.3 — Disk cache

Fetch `systems.xml.gz` → `data/oec/systems.xml.gz` (`data/` already gitignored). Use cache if present
and younger than a staleness window (default 7 days); else re-download, falling back to the stale cache
on network failure (classified via `_network_error_msg(…, "Open Exoplanet Catalogue")`). In-memory
`_OEC_DATA` double-checked-locking cache (P6.4 pattern). Offline after first pull.

---

## §C — Four-phase build (each gated by an HTML approval file)

> **Restructured 2026-07-17** from three phases to four: feature parity (D8) grew large enough to be its
> own phase, and the OEC-unique **System Architecture map** (novel, higher-risk) is best separated from
> the reuse-heavy parity work. Phase order de-risks — each phase is coherent and independently shippable.

### Phase 1 — Core model + text surfaces + Tier-1 query.py &nbsp;·&nbsp; **BUILT 2026-07-17** (mockup signed off; full suite 1784 passed / 1 skipped)

- `core/databases.py`: rewrite `_load_oec()` (normalized index + disk cache), `_oec_num()`, the single
  generic recursive `_oec_node()` (complete field capture — D7), `compute_oec(target)` (accepts a SIMBAD
  result **or** a raw name string) → `{simbad?, system: <node>}` or `{"error"}`.
- CLI: `query_open_exoplanet_catalogue()` — SIMBAD lookup → `compute_oec` → **indented tree render**
  (system → binary/star → planet, each node its own property line; rogue + zero-planet branches handled).
  Register `"7": ("Open Exoplanet Catalogue", query_open_exoplanet_catalogue)`.
- GUI: rebuild `OecPanel` in `gui/panels/catalogs.py` on the current `_StarSearchPanel` base +
  re-add the nav entry. **`QTreeWidget`** render mirroring the hierarchy. **Resolution is
  direct-alias-first, SIMBAD-fallback** (D1): the typed name is normalized and matched against the OEC
  alias index offline first; only on a miss is a SIMBAD lookup done to translate a common name → HD/HIP
  designations and retry. (No separate raw-name field — the single field already tries the direct match
  first.)
- `query.py` **Tier 1**: `oec-system <name>` (full tree), `oec-planet <name>` (planet node + host chain
  system→binary→star). Direct-alias resolution (offline, no SIMBAD).
- Docs: rewrite the "removed — rebuild pending" section in `docs/star-databases.md`; add the OEC section
  to `docs/integration.md` (node JSON schema, resolution posture, cache, self-validating contract).
- Tests: `tests/test_oec.py` (offline) over a **hand-built fixture XML** covering the §A.4 nine-topology
  set + an `upperlimit` value + an arcsec-only `separation`; `tests/test_oec_live.py` (network-gated via
  `tests/_netcheck.py`).

### Phase 2 — Star-Databases parity (Hypatia + per-host diagrams) &nbsp;·&nbsp; **BUILT 2026-07-17**

> **Built as `OecPanel(DiagramToggleMixin, _StarSearchPanel)` (`gui/panels/catalogs.py`).** A background
> `_oec_with_hypatia` resolves the system and pre-fetches Hypatia for every host (so the **Host** combo
> switches instantly). Reuses the NASA panel's `_make_{orbits,hz,mass_radius,transit,size}_tab` verbatim
> via an OEC-node → NASA-key adapter (`_oec_host_to_nasa`, incl. the Jupiter→Earth mass/radius
> conversion), and `build_hypatia_tab` / `prepare_abundance_profile` / `make_kinematics_tab` for the
> Hypatia tab + Abundance + Kinematics. Hosts = planet-bearing **star** (normal), **binary** (circumbinary
> pseudo-host — §F.7), or **system** (rogue → Data tab only, no diagrams). Verified: 55 Cancri (all 7 viz
> tabs), Alpha Cen (host switch Proxima↔B), Kepler-16 (circumbinary), TRAPPIST-1 (Mass–Radius/Size),
> WISE 0855 (rogue, Data only).
>
> **Known limitation (circumbinary HZ):** the reused single-star `_make_hz_tab` uses the **primary
> component's** teff+luminosity for a circumbinary (binary) host, not the **combined light** of both
> stars. §F.7/D2's `compute_circumbinary_hz` (combined-light) is the correct refinement and is left as a
> Phase-2 follow-up (a binary-host-specific HZ tab) — acceptable for wide binaries, an underestimate for
> close ones like Kepler-16.

**Design decision (D8, 2026-07-17): full feature parity with the other Star Databases panels**
(supersedes the earlier "per-host subset, skip Hypatia" call). Feasibility was proven end-to-end
(2026-07-17): OEC star names carry HD/HIP, so a `simbad_compat`-style `{designations, main_id}` dict
built from a star node feeds **the exact same** enrichment path the NASA/HWC panels use — no new core
math, only the OEC→compat wrapper (mirrors the panels' `_*_with_hypatia`). Verified pulls: Tau Ceti 44
abundances, 47 UMa 50, α Cen B 33, Proxima 0 (M-dwarf → graceful empty, same as elsewhere).

Everything below is **per selected host star** — the host is chosen via a **Host selector** in Phase 2
(a combo of the system's planet-bearing stars) and later by **click-to-recenter on the Architecture
map** in Phase 3. Single-star systems auto-select their one host.

- `OecPanel` → `DiagramToggleMixin`, matching `NasaPlanetarySystemsPanel`:
  - **Hypatia tab** — `compute_hypatia_data(compat)` → `build_hypatia_tab()` verbatim (Stellar Properties
    + Kinematics + the 104-species grouped Elemental Abundances). Empty/"no Hypatia data" for
    M/BD/WD/faint hosts — never fabricated.
  - **Diagram tabs** reusing existing `core.viz` preps: **Orbital** (`prepare_exoplanet_system_diagram`
    from the host's planet SMA/ecc, + the **O4 Solar-System overlay** and **O10b Honorverse
    hyper-limit ring** toggles via `compute_hyper_limit_for_spectral_type` on the host SpT) · **HZ**
    (`prepare_hz_diagram(teff, luminosity)`, luminosity = `R²·(T/5778)⁴` from the OEC star's teff+radius)
    · **Mass–Radius** (`prepare_mass_radius`) · **Size Comparison** · **Transit Geometry** (where
    `inclination` present) · **Abundance Profile** (`prepare_abundance_profile` → grouped [X/H] bars) ·
    **Kinematics/Toomre** (`prepare_toomre`, when U/V/W present).
  - Graceful empty-tab handling for planetless / WD / BD hosts (show what the fields support; muted
    "no planets catalogued for this component" note; spectral type shown verbatim, **not** routed through
    the OBAFGKM `_SP_PATTERN`).
- **Host selection in Phase 2 is a `QComboBox`** of the system's planet-bearing stars (single-host systems
  auto-select). Phase 3's Architecture-map click-to-recenter later becomes the selector; the combo is the
  interim mechanism so the parity tabs are usable before the map exists.
- **HZ presentation note (see §G):** the mockup's HZ tab is a *horizontal √AU strip* (bands + planet SMA
  markers, green = in-HZ) — distinct from the app's existing concentric-ring `make_hz_canvas`. For Phase 2,
  reuse the **existing** `prepare_hz_diagram`/`make_hz_canvas` for consistency with the other panels; the
  strip style is logged in §G as a separate cross-cutting enhancement to evaluate for the whole app.

### Phase 3 — System Architecture map (static → interactive)

The OEC-unique visualization; separated from Phase 2 because it is novel and higher-risk (new canvas +
barycenter math + interaction), not reuse. **Gated by an HTML approval mockup — signed off 2026-07-17**
(`mockups/oec-phase3.html`; the barycenter roll-up + log-radial layout run live in-browser on real nodes).

- **Static — BUILT 2026-07-17 (Phase 3a).** log-radial, **mass-weighted barycenter** at the origin
  (recursive Jacobi roll-up; geometric-midpoint fallback when a component mass is missing — D5). Whole
  hierarchy: each star at its reconstructed position, each planet a small ring on its host. Caveat labels:
  projected-separation (arcsec→AU via system distance) and static-placement (positionangle = on-sky
  orientation, no orbital phase) — an architecture sketch, not an ephemeris.
  - New code: `core.viz.prepare_oec_architecture(system_node, focus_node=None)` (pure layout → display-space
    dict; `focus_node` seam already in place for 3b) + `plot_helpers.make_oec_architecture_canvas(parent,
    data, on_select=None)` (dark-navy Star-Chart palette). Wired into `OecPanel._add_architecture_tab` as
    viz tab 0, shown for **every** matched system (incl. planetless 61 Cyg / rogue).
  - **Separation ladder settled (D5 extension, approved 2026-07-17):** `semimajoraxis` → `separation[AU]` →
    `separation[arcsec]×distance_pc` (projected) → **Kepler `a=∛((M₁+M₂)·P²)` from the binary period** (new
    rung — 61 Cyg has only a period; gives ~85 AU, matching the real orbit) → schematic offset when even that
    is impossible. AU-direct is preferred over arcsec-projected when both are catalogued.
  - Tests: `ArchitectureMathTests` + `ArchitectureTopologyTests` in `tests/test_oec.py`.
  - *Known limitation:* circumbinary (P-type) planets attach to the `<binary>`, not a star, so they aren't
    yet drawn as rings on the map (a Phase-3b/follow-up refinement).
- **Then interactive — Phase 3b (planned).** Three items, all landing together (they reopen the same
  `prepare_oec_architecture` / `make_oec_architecture_canvas` / `OecPanel` surface):
  1. **Click-to-recenter** — select a **star** (or a **binary** node → its subsystem barycenter) → re-anchor
     the log-radial view on it **and** repopulate the Phase-2 per-host detail tabs (the map *replaces the
     combo* as the host selector); a "⟲ Reset to barycenter" control. The `on_select` callback + `focus_node`
     param + clickable ◆ binary-barycenter handles are already built and unit-tested in 3a; this is the panel
     wiring (drive `_render_host` from the map + breadcrumb/reset UI).
  2. **Circumbinary (P-type) planet rings** *(Greg's decision, 2026-07-17 — folded in here, not left as the
     3a limitation).* The 39 planets that attach to a `<binary>` (Kepler-16 b, Kepler-47…) orbit the binary
     barycenter, not a star, so 3a doesn't draw them. Add: `prepare_oec_architecture` emits a
     `centers: [{x, y, label, planets}]` for binaries carrying child `<planet>`s (keyed to the binary
     barycenter already tracked for the ◆ handles, reusing `_oecv_planet_fracs`); the canvas draws those rings
     around the barycenter point.
  3. **Star-chart interaction parity** *(Greg's decision, 2026-07-17).* Bring the `make_star_chart_canvas`
     (opts 18/19) interactions to the Architecture map — **scroll-wheel zoom around the cursor**,
     **cursor-anchored hover tooltip** (`_anchor_hover_to_cursor`, name + key info), and a **click info box** —
     with the click semantics reconciled: **hover = show info, click = recenter/select** (recenter is the
     primary click action here, unlike the star chart where click = info). Consider the zoom-driven label
     decluttering too. (The 3D preset buttons are N/A — the Architecture map is 2-D.)

### Phase 4 — query.py Tier-2/3 (structural search + census)

Independent of the GUI work (pure data/search over the parsed catalogue); last because it serves the
sibling repo rather than the app's own UI.

- **Tier 2** `oec-search` (structural filters: `--min-stars`/`--max-stars`, `--status`, `--circumbinary`,
  `--discovery-method`, `--discovery-year-min/max`, `--mass/radius/period/sma` ranges, spectral type →
  matched systems + topology summary).
- **Tier 3** `oec-census` / `oec-status` (topology stats + catalogue snapshot/version).

---

## §D — Issues surfaced while planning (all resolved 2026-07-17)

1. **Resolution order → direct-alias-first, SIMBAD-fallback** *(reverses the earlier "SIMBAD-first"
   posture)*. Normalize the typed name → match the OEC alias index offline first (instant); on a miss,
   SIMBAD-lookup → translate to HD/HIP → retry. Avoids the old SIMBAD-format fragility. The raw-OEC-name
   field is dropped as redundant. Reflected in §C Phase 1.
2. **Circumbinary HZ → use `compute_circumbinary_hz` for the 39 P-type planets**; single-star HZ for
   normal hosts, **labelled an approximation** when the host is in a close binary. (Phase 2.)
3. **Alias collisions → accept first-wins, no logging.** Genuinely rare; not worth the noise.
4. **`oec-planet` rogue host chain → the system node only** (no star/binary); the planet is marked
   `attached_to: "system"`. (Star hosts → `"star"`; circumbinary → `"binary"`.)
5. **Barycenter → recursive Jacobi roll-up.** Bottom-up: each `<binary>` splits its two children about
   their mass-weighted barycenter (child offset = `sep × m_other/(m₁+m₂)`); subsystem mass = Σ children,
   subsystem barycenter placed by its parent. `separation` in AU directly; arcsec → AU via system
   distance. Orientation from `positionangle` when present, else a deterministic schematic angle.
   **Geometric fallback:** any missing child mass → split equally (not mass-weighted) + flag the node.
   (Phase 2.)
6. **Staleness → 7 days**, as module constant `_OEC_CACHE_MAX_AGE_DAYS = 7` (tunable); auto-refresh on
   expiry, stale-cache fallback on network failure. (Phase 1.)
7. **Generic complete field capture** (surfaced by the 2026-07-17 field census — see §B.1). The node
   model captures **every** non-container child field + its attributes (`type=msini`, `unit`, error/limit),
   not a curated subset; `<satellite>` moons become nested nodes. Display curates a headline set + a
   "more fields" expander; `query.py` JSON carries the complete node. Reflected in §B.1 and the mockup.
8. **Full Star-Databases parity** (supersedes the earlier "per-host subset, skip Hypatia" call). OEC gains
   the same **Hypatia** enrichment (Hypatia tab + Abundance Profile + Kinematics/Toomre) and the full
   **diagram** set (Orbital + Solar/Honorverse overlays, HZ, Mass–Radius, Size, Transit) as
   `NasaPlanetarySystemsPanel`, all **per selected host star** (Host selector → later the click-selected
   Architecture-map star). Proven feasible 2026-07-17 by reusing `compute_hypatia_data` + the `core.viz`
   preps verbatim; only the OEC-star→`{designations, main_id}` compat wrapper is new. GUI-only (the
   diagrams/Hypatia don't affect the CLI tree or the `query.py` node contract). Reflected in §C Phase 2/3
   and the mockup.

---

## §E — Docs to update on completion

- `docs/star-databases.md` — replace the "Open Exoplanet Catalogue Feature (removed — rebuild pending)"
  section with the rebuilt feature (tree model, normalized matching, disk cache, the planet-catalogue
  expectation, the diagrams).
- `docs/integration.md` — new "Open Exoplanet Catalogue" section: node JSON schema, `oec-system` /
  `oec-planet` / `oec-search` / `oec-census` / `oec-status` contracts, resolution posture, exit codes.
- `docs/gui-architecture.md` — `OecPanel` class → option-7 mapping, the tree + diagram tabs, the
  interactive architecture canvas.
- `docs/testing.md` — `tests/test_oec.py` / `tests/test_oec_live.py` entries.
- `CLAUDE.md` menu-options block — option 7 label (drop "reserved — OEC removed").

---

## §F — Lessons from the mockup phase (fold into the Phase-1 build)

Building the functional mockup against real data surfaced concrete build hazards — captured here so the
implementation doesn't re-learn them:

1. **Any field can repeat → treat every field as possibly a list, not just `separation`.** The load-bearing
   one: **planets in binary systems carry two or more `<list>` tags** ("Confirmed planets" *and* "Planets
   in binary systems, S-type"). Generic capture (D7) correctly stores repeated tags as an array, but *any
   consumer that reads `field.value` directly crashes* when the field is an array. The mockup crashed on
   load for exactly this (55 Cancri, a binary). **Build rule:** every reader (GUI, CLI, and any `query.py`
   consumer) must go through a first-or-list accessor (`prim()`/`tval()` in the mockup), never `field.value`
   directly. A planet may legitimately have **multiple statuses** — show them all (two status badges). Add
   `list`-repeat and `separation`-repeat assertions to `tests/test_oec.py`.
2. **Test every topology class on the default/auto path, not just the easy one.** The repeated-`<list>`
   crash was masked because the first default was a single-star system (Tau Ceti). The bug only appeared
   when the default became a binary. **Build rule:** the test matrix must exercise single / S-type binary /
   P-type circumbinary / hierarchical / rogue / zero-planet — each through the *full* render path.
3. **RV vs transiting determines which diagrams populate.** RV-discovered planets have `mass` (often
   `msini`) but **no `radius`** → Mass–Radius and Size tabs are legitimately empty. Only transiting systems
   (e.g. 55 Cancri e, TRAPPIST-1) populate them. The fixture set must include a transiting multi-planet
   system so those tabs are exercised, and empty-tab handling must be graceful (not an error).
4. **Hypatia resolution from OEC works via name-derived designations.** Regex HD/HIP/GJ/HR out of the star's
   alias list → `{designations, main_id}` → `compute_hypatia_data`. Confirmed: FGK hosts populate (Tau Ceti
   44, 47 UMa 50, 55 Cnc A 48); M/BD/WD hosts (Proxima, TRAPPIST-1, the Sun) return empty/sparse — render
   gracefully, never fabricate.
5. **`msini` must be visible.** `<mass type="msini">` is common on RV planets and materially changes meaning
   (minimum mass) — label it "M·sin i" wherever mass shows.
6. **Fixture set (finalized from the mockup):** the nine §A.4 topologies **plus** 55 Cancri (transiting +
   Hypatia) and TRAPPIST-1 (7 transiting planets) for the diagram/parity paths.
7. **Circumbinary & rogue planets have no host *star* — a Phase-2 host-model edge case (surfaced by the
   mockup).** "Host" for the per-host diagrams/Hypatia = a **planet-bearing `<star>`**. But 39 planets attach
   to a `<binary>` (P-type) and 5 to a `<system>` (rogue) — those systems have **no planet-hosting star**, so
   the host selector is empty and the mockup shows "no planet-hosting star (rogue / zero-planet system)."
   Phase 2 must **decide** how these surface: for **circumbinary**, treat the parent `<binary>` as a
   pseudo-host (Orbital diagram = planet around the binary barycenter; HZ from the combined light via
   `compute_circumbinary_hz`, which we already have — ties to D2; Hypatia keyed to a chosen component). For
   **rogue**, no orbital/HZ applies — show object properties only. *(Phase 1 is unaffected — the tree/CLI/JSON
   already render these correctly; this is a Phase-2 diagram-model decision to settle at that gate.)*
8. **OEC planet mass/radius are in Jupiter units** (`M♃`/`R♃`); satellite fields need their own unit check.
   The reused diagram preps (`prepare_mass_radius`, Size) were built for NASA **Earth-unit** data, so OEC
   values must be **converted before feeding them** (×317.8 M⊕/M♃, ×11.2 R⊕/R♃) — the mockup does this.
   Applies to Phase 2, but noted here so the reuse wiring doesn't silently plot Jupiter numbers on Earth axes.
9. **Unnamed binaries need a synthesized label.** `<binary>` `names[]` is often empty (α Cen outer, 61 Cyg);
   synthesize from child component names — the mockup's rule: "Binary (A + B)" from the last token of each
   child's primary name (recursing for nested binaries). Applies to the Phase-1 tree render (CLI + GUI).
10. **`upperlimit`/`lowerlimit` carry the numeric bound in the *attribute*, and the element text is usually
    empty** (210 of 233 in the catalogue). So a bound-only field (e.g. `<eccentricity upperlimit="0.35"/>`)
    must render as `<= 0.35`, reading the number from the attribute — not `<= ` with an empty value. Handled
    in `oec_format_field`. (Discovered during the Phase-1 CLI render.)

## §G — Cross-cutting enhancement note (not OEC-scoped — evaluate separately)

**HZ-diagram "strip" presentation → a Rings/Strip toggle, app-wide, as Phase 5 (post-OEC).** The mockup's
HZ tab renders a **horizontal √AU strip** — optimistic (light) + conservative (dark) HZ bands with planet
markers placed by semi-major axis, green when inside the optimistic HZ. This differs from the app's existing
**concentric-ring** `make_hz_canvas` (`prepare_hz_diagram` → radial circles). Greg liked the strip.

**Decision (2026-07-17):**
- **Design — a toggle, not a replacement.** Add a **Rings (default) / Strip** segmented toggle at the top of
  the HZ tab. Rings stays default so existing behavior + any golden output are unchanged; Strip is opt-in.
  One toggle design drops uniformly into **every** panel's HZ tab (OEC + NASA Planetary Systems + HWC + HWO +
  Mission Exocat) so they don't diverge.
- **Timing — Phase 5, after OEC Phase 4.** This is an **app-wide** change to shared `core.viz`/`plot_helpers`
  used by every Star Databases panel — deliberately sequenced *after* the OEC rebuild is complete and green,
  to (1) keep it out of OEC scope, (2) avoid destabilizing panels the OEC work never touches by editing the
  shared viz layer mid-build, and (3) let it be its own independently-testable unit. It gets **its own HTML
  approval mockup** (mostly toggle UX + cross-panel application; the strip render itself is already
  prototyped in `mockups/oec-phase1.html` `svgHZ`).
- **Build sketch:** new `prepare_hz_strip` / `make_hz_strip_canvas` in `core.viz` / `plot_helpers.py`; a
  small toggle control (default Rings) wired into each panel's HZ tab.

### Phase 5 — Cross-cutting HZ Rings/Strip toggle (post-OEC, app-wide)

Not OEC-scoped — retrofits the HZ tab of **all** Star Databases panels (incl. OEC's). Runs only after
Phase 4. Own approval mockup. See [[oec-hz-strip-enhancement]].
