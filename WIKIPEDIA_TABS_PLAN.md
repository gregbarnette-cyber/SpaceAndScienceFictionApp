# WIKIPEDIA_TABS_PLAN.md — In-App Wikipedia Article Tabs

**Status:** **BUILT** 2026-08-23 on branch `feature/wikipedia-tabs` (uncommitted — awaiting user
commit). All 6 phases done; both `/code-review high` checkpoints run and their findings applied
(CP1: 5 findings; CP2: 6 findings — see the CP notes at the end of §14). Full offline suite
**3095 passed, 76 skipped, 0 failures** (incl. two post-review user-feedback fixes — full article
body via the Action API, and WSL-aware external links; see §9). Mockup approved 2026-08-23; independent plan review
2026-08-23 — findings incorporated (see §6, §7, §8, §10, §15).
**Scope:** GUI-only feature. A button that opens the star's Wikipedia article as a tab, fetched
on demand and rendered as formatted text in a `QTextBrowser`. Six surfaces = **11 distinct panel
classes** (SimbadPanel · 5 NASA classes incl. Map · HwcPanel · OecPanel · StarSystemsSearchPanel ·
opts 18 & 19).

---

## 1. Goal

Add a Wikipedia article view to the star-facing panels so a user can read the star's Wikipedia
lead section (with thumbnail + link to the full page) without leaving the app. One shared
mechanism, wired into six surfaces:

| # | Surface | Panels | Trigger |
|---|---------|--------|---------|
| §1 | SIMBAD Lookup | `SimbadPanel` (opt 1) | button → tab in the panel's tab widget |
| §2 | NASA Exoplanet Archive | opts 2/3/4/5 + Map | button → tab beside Data/Hypatia |
| §3 | Habitable Worlds Catalog | `HwcPanel` (opt 6) | button → tab beside Data/Hypatia |
| §4 | Open Exoplanet Catalogue | `OecPanel` (opt 7) | button → tab; host resolved via OEC→SIMBAD |
| §5 | Star Systems Search | `StarSystemsSearchPanel` (G1) | selection button → detail tab |
| §6 | Stars within a Distance | opts 18 & 19 | **row-click → selection button → detail tab** |

---

## 2. Approved decisions (locked)

- **Rendering:** fetched text via the Wikipedia REST **summary** endpoint → rendered in a
  `QTextBrowser` (the widget already used by `gui/help.py` and `gui/panels/reports.py`).
  **No QtWebEngine.** No new pip dependency (`requests` is already present).
- **Lazy fetch:** nothing is fetched until the user presses the button / opens the tab.
- **Where it opens:** as a **tab in the panel's results/table area** (not the chart/diagram tabs).
- **Opts 18/19 behave like Star Systems Search:** click a table row, then open it in a new tab.
- **Thumbnail included** (best-effort; text always renders even if the image fails).
- **Resolver with a star-check guard** so a bad candidate can never show a wrong article.

## 3. Non-goals

- No `query.py` subcommand (this is presentation, not a calculator). Core logic still lives in
  `core/` so it is unit-testable.
- No full-article rendering (all sections/infobox/tables). The REST summary lead + link is the
  approved scope; a full-text variant is a possible later extension, noted in §9.
- No CLI (`main.py`) surface — the CLI menu is deprecated.

---

## 4. Architecture — one mechanism

Two new modules plus thin per-panel wiring:

1. **`core/wikipedia.py`** (pure + network, **no Qt**) — resolve a star to a Wikipedia article
   and fetch its summary. Reuses `core.shared._with_retries` / `_timeout_ctx` /
   `_network_error_msg`, and `core.databases.compute_simbad_lookup` (lazy import) for the
   name-only path. Offline-testable resolution logic; live fetch behind a network gate.
2. **`gui/panels/wikipedia_tab.py`** (Qt) — `WikipediaView` (the tab body), a
   `WikipediaButtonMixin` (button + open/focus logic), and `open_or_focus_wiki_tab(...)`.

Star-title source per surface:
- §1/§2/§3 already carry the SIMBAD result (`result` / `result["simbad"]` → `main_id` +
  `designations`) — pass it straight to the resolver, **no extra network**.
- §4 (OEC) has no SIMBAD dict → resolve by the **selected host** name (the resolver does its
  own `compute_simbad_lookup`), reusing OEC's existing `_oec_star_xrefs` / host name.
- §5/§6 have the **star name** from the selected table row → resolver does its own
  `compute_simbad_lookup` (exactly what "Open star in new tab" already does).

---

## 5. New module — `core/wikipedia.py`

### Constants
```python
_WIKI_REST = "https://en.wikipedia.org/api/rest_v1/page/summary/"
_WIKI_UA   = "SpaceAndScienceFictionApp/1.0 (astronomy worldbuilding desktop tool)"
_WIKI_TIMEOUT = 15
# Guard keywords — a candidate article's description+extract must mention one of these:
_STAR_WORDS = frozenset({
    "star", "stellar", "dwarf", "subdwarf", "subgiant", "giant", "supergiant",
    "binary", "multiple star", "planetary system", "brown dwarf",
    "main sequence", "sun-like", "solar analog",
})
# NOTE: "constellation" deliberately EXCLUDED — a mis-split Bayer candidate can resolve to a
# constellation article (e.g. "Cetus"), whose lead contains "constellation"; including it would
# pass the guard on the wrong page. Accepted trade-off: a star whose lead lacks every keyword
# yields a (rare) false not-found rather than a wrong article.
```
> **User-Agent:** descriptive per Wikipedia's API etiquette, **no personal email** (per the
> "userEmail" memory rule — Wikipedia is the integrated service, but a contact URL, not the
> user's address, is the safe form; add a repo URL if one is wanted).

### Public API
```python
def build_candidates(designations: dict | None,
                     main_id: str | None = None,
                     name: str | None = None) -> list[tuple[str, str]]:
    """Ordered (query_title, matched_on_label) candidates. Pure, offline."""

def resolve_and_fetch(designations: dict | None = None,
                      main_id: str | None = None,
                      name: str | None = None) -> dict:
    """Resolve the best star article and fetch its summary. Network."""

def fetch_thumbnail(url: str) -> bytes | None:
    """Best-effort image fetch; None on any failure. Network."""
```

### `build_candidates` order (highest → lowest)
1. `NAME` proper name (strip the `NAME ` prefix) — strongest.
2. **Bayer, spelled for Wikipedia** — `* tau Cet` → `"Tau Ceti"` (see §9).
3. `Flamsteed` — `*  10 CMi` → `"10 Canis Minoris"` (reuse `core.shared.format_star_designation`).
4. `HR`.
5. `HD`.
6. `GJ` — emit **both** `"GJ 71"` and `"Gliese 71"` (Wikipedia titles use "Gliese").
7. `HIP`.
8. `MAIN_ID` (last resort).
9. If `designations` is empty but `name` is given, `name` itself is the sole candidate.

Deduplicate case-insensitively, preserving order. `matched_on_label` is the raw designation
string that produced the query (surfaced in the tab as "matched on …").

### `resolve_and_fetch` behavior
- If `designations is None` and `name` given → `compute_simbad_lookup(name)` (lazy import);
  on success use its `designations`/`main_id`; on error, fall back to `name` as a candidate.
- For each candidate, `_fetch_summary(query)`:
  - `GET _WIKI_REST + urllib.parse.quote(title) + "?redirect=true"`, UA header, wrapped in
    `_with_retries` inside `_timeout_ctx(_WIKI_TIMEOUT)`.
  - **404 → return `None`** (skip candidate, **no retry** — return None cleanly rather than
    raising, so `_with_retries` does not spin on a legitimate miss).
  - other non-200 → `raise_for_status()` (retried by `_with_retries`).
  - 200 → parsed JSON.
- Skip a summary if `_is_star_article(summ)` is False (disambiguation, or no star keyword).
- First accepted → return the **found** dict. Exhausted → **not-found** dict.
- Any network exception from `_fetch_summary` → `{"error": _network_error_msg(e, "Wikipedia")}`.

### `_is_star_article(summ)` (pure)
- `summ.get("type") == "disambiguation"` → False.
- `text = (description + " " + extract).lower()`; True iff any `_STAR_WORDS` token in `text`.
- (Future refinement, noted not built: check the Wikidata `wikibase_item` "instance of" —
  strictly correct but costs an extra call.)

### Return contracts
```python
# found
{"found": True, "title": "Tau Ceti",
 "url": "https://en.wikipedia.org/wiki/Tau_Ceti",
 "extract_html": "<p>…</p>", "summary_text": "…",
 "thumbnail_url": "https://…/…jpg" | None,
 "description": "star in the constellation Cetus",
 "matched_on": "HD 10700", "query": "Tau Ceti"}
# not found
{"found": False, "tried": ["Tau Ceti", "HD 10700", "Gliese 71", …]}
# network error
{"error": "Wikipedia request timed out. Try again."}
```

---

## 6. New module — `gui/panels/wikipedia_tab.py`

### `class WikipediaView(QWidget)`
- Layout: a single `QTextBrowser` (`setOpenExternalLinks(True)`, `setOpenLinks(True)`) so the
  "Read the full article ↗" link opens the system browser.
- `load_for(*, name=None, designations=None, main_id=None, star_label=None)`:
  - render the **loading** HTML, then start a background fetch of `core.wikipedia.resolve_and_fetch`.
  - `_on_article(res)`: `error` → error HTML; `found is False` → not-found HTML; else **found**
    HTML (title, "matched on …", `extract_html`, link, "Text: Wikipedia, CC BY-SA"), then if
    `thumbnail_url`, start a second background fetch of `fetch_thumbnail` → `_on_thumb`, which
    adds the image via `document().addResource(QTextDocument.ImageResource, QUrl(url), QImage)`
    and re-renders with an `<img src="url">` at the top. Text shows immediately; the thumbnail
    fills in when it arrives (best-effort — failure leaves the text intact).
- Four HTML render helpers (loading / found / not-found / error) matching the approved mockup
  states. All strings are `QTextBrowser`-safe HTML (headings, `<p>`, `<b>`, `<a>`, `<img>`).

### Threading
Reuse **one** shared background helper so the QThread-lifetime GC guard is not duplicated:
- **Extract** `run_in_thread(owner, fn, args=(), kwargs=None, on_result=None, on_progress=None)`
  as a module-level function in `gui/panels/base.py`, using the existing `_live_threads`
  registry (see §7). `WikipediaView` calls `run_in_thread(self, …)`; the registry keeps the
  thread alive even if the tab is closed mid-fetch (the current fix for "QThread destroyed
  while running").

### Button + open helpers
```python
class WikipediaButtonMixin:
    def _make_wiki_button(self, label="📖 Wikipedia") -> QPushButton: ...   # disabled until context set
    def _set_wiki_context(self, tabs, *, designations=None, main_id=None,
                          name=None, star_label=None): ...                 # enables the button
    def _open_wikipedia(self): ...                                          # open/focus into ctx tabs

def open_or_focus_wiki_tab(tabs: QTabWidget, star_label, *,
                           designations=None, main_id=None, name=None,
                           closable=False) -> None:
    """If a '📖 … — Wikipedia' tab for this star exists, focus it; else create a
    WikipediaView, addTab titled '📖 {star_label} — Wikipedia', select it."""
```

---

## 7. `gui/panels/base.py` — thread-helper extraction (the highest-risk piece)

Extract the QThread/`Worker`/`_live_threads` plumbing out of `ResultPanel.run_in_background`
into a module-level `run_in_thread(...)`. `run_in_background` becomes a thin wrapper that keeps
the **ResultPanel-only** behavior; `WikipediaView` (a plain `QWidget`) uses `run_in_thread`
directly. **No behavior change** for existing panels — guarded by the entire GUI test suite.

**Main-thread delivery affinity is load-bearing (do not get this wrong).** Today
`run_in_background` connects `worker.finished` → **`self._deliver_bg_result`**, a *bound method
of a main-thread `QObject`*, so Qt's queued connection runs the callback on the **main thread**
— see the explicit warning at `base.py:210–217`: a context-less free function / lambda has no
`QObject` affinity, so Qt would run it on the **worker** thread, and `WikipediaView` would then
build its `QTextBrowser`/`QTextDocument`/`QImage` off the main thread (a crash-class bug). The
extraction MUST preserve this:
- `run_in_thread(owner, fn, args=(), kwargs=None, on_result=None, on_progress=None)` connects
  **only**: `thread.started`→`worker.run`; `worker.finished`→a **main-thread deliverer bound
  method**; `worker.finished`→`thread.quit`; and the `_live_threads` grace-period cleanup on
  `thread.finished`. The deliverer must be a bound method of a `QObject` living on the main
  thread — either a tiny shared `_BgDelivery` mixin that both `ResultPanel` and `WikipediaView`
  inherit (giving each a `_deliver_bg_result`), or a dedicated deliverer `QObject` that
  `run_in_thread` creates and stores in `_live_threads` alongside `(thread, worker)`.
- The wrapper `ResultPanel.run_in_background` keeps everything that touches ResultPanel members:
  `set_status("Working…")`, the `run_btn` disable/re-enable, and the `worker.error` /
  `worker.progress` connections (`base.py:220–221`). Note the stock `Worker.run` (`base.py:34–42`)
  routes **all** exceptions through `finished` as `{"error": …}` and never emits `error`/`progress`,
  so `run_in_thread` must NOT hard-wire `worker.error.connect(owner._on_error)` — a non-ResultPanel
  owner has no `_on_error`. Keep those connections in the wrapper (or guard with `hasattr`).

This is the enabling change that lets `WikipediaView` share the exact same GC-safe, main-thread
threading. It is the first thing `/code-review` Checkpoint 1 must scrutinize.

---

## 8. Per-surface wiring

### §1 — SimbadPanel (`gui/panels/simbad.py`)
- Mix in `WikipediaButtonMixin`.
- `build_inputs`: add `self._make_wiki_button()` to the form (beside "Add to project"); disabled.
- `render()` (`simbad.py:142`): after building `tabs` (line 200) and before/at `add_result_widget`
  (line 233), keep `self._wiki_tabs = tabs` and call
  `self._set_wiki_context(tabs, designations=result["designations"], main_id=result.get("main_id"),
  star_label=result.get("main_id"))`. On the **error path** (`simbad.py:145–148`) actively `self._wiki_btn.setEnabled(False)` (mirroring `_add_proj_btn`) — `clear_results()` at `:143` deletes the prior `tabs`, so an enabled button still pointing at the freed `self._wiki_tabs` would `RuntimeError` on click.
- `_open_wikipedia` (from mixin) opens/focuses the tab in `self._wiki_tabs`.

### §2 — NASA panels (`gui/panels/nasa_exoplanet.py`)
Applies to opts 2/3/4/5 + Map. Each `_render` already computes `simbad = result["simbad"]` and
builds a `data_tabs` (opt 2 uses a single `tabs`). For each:
- Mix in `WikipediaButtonMixin`; add the button to the search/action row in `build_inputs`.
- In `_render`, after building the data tab widget, call
  `self._set_wiki_context(<that tab widget>, designations=simbad["designations"],
  main_id=simbad.get("main_id"), star_label=simbad.get("main_id"))`.
- Insertion points — the data-tab-widget **attach** lines (reviewer-corrected): opt 2 `:402`
  (single `tabs`), opt 3 `:571`, opt 4 `:694`, opt 5 `:798`, Map `:1188`. Call `_set_wiki_context`
  after that attach.

### §3 — HwcPanel (`gui/panels/catalogs.py`)
Same as NASA. `_render` has `simbad = result["simbad"]` (`catalogs.py:198`) and a `data_tabs`
(`:210`, attached `:348`). Add button + `_set_wiki_context(data_tabs, …)` after the Hypatia tab.

### §4 — OecPanel (`gui/panels/catalogs.py`)
- Mix in `WikipediaButtonMixin`; add the button to the OEC action row.
- OEC has **no** `simbad` dict. On host render/switch (`_render_host`, `catalogs.py:1733`) or
  `_on_oec_result`, set the context by **name**:
  `self._set_wiki_context(self._data_tabs, name=<resolvable host id>, star_label=host["name"])`,
  where the resolvable id is `host["name"]` or, if available, an id from `_oec_star_xrefs(node)`
  (the same source `_open_oec_star_lookup` uses at `catalogs.py:1302`).
- The `WikipediaView`'s name-path calls `compute_simbad_lookup` itself; a rogue/unresolvable host
  yields the not-found state (never a wrong page).
- **Host-switch teardown (expected):** `_render_host`/`_rebuild_after_focus` prune `_data_tabs`
  down to index 0 on every host switch and Architecture-map recenter
  (`while self._data_tabs.count() > 1: removeTab(1); …deleteLater()`, `catalogs.py:1718–1722`), so
  an open Wikipedia tab is removed when the user changes host or clicks a star on the map. This is
  correct — the article should follow the focused host — and `open_or_focus_wiki_tab` re-adds a
  fresh one; verify no dangling reference to the deleted view survives (re-resolve on each open).

### §5 — Star Systems Search (`gui/panels/search_common.py` + `gui/panels/search.py`)
- `search_common.py`: in `_build_results_scaffold` initialize `self._on_wiki = None` (beside
  `self._on_open = None`, `:140`) and add a second selection button
  `self._wiki_btn = QPushButton("📖 Open in Wikipedia →")` in `sel_row` beside `_open_btn`,
  hidden initially; wired to `_wiki_clicked → self._on_wiki(self._sel_record)`.
- `_render_table(...)` gains an optional `on_wiki=None` param; store `self._on_wiki`; in
  `_on_sel` show `_wiki_btn` **only when `on_wiki` is set** (so G2/G3/L4 don't show a dead
  button unless they opt in). **Also hide `_wiki_btn` in the two places `_open_btn` is hidden** —
  the start of `_render_table` (`:165`) and `_show_search_error` (`:200`) — so a stale wiki button
  can't linger across a re-render or a failed search.
- `search.py` G1 `StarSystemsSearchPanel._render` (`:176`): pass `on_wiki=self._open_wiki_star`.
  New `_open_wiki_star(rec)`: `name = rec.get("star_name")`; `self.open_detail_tab(("wiki",
  name), f"📖 {name} — Wikipedia", lambda: _wiki_view_for_name(name))` — reuses the existing
  `open_detail_tab` machinery (`search_common.py:207`).
- The base change makes the button available to G2/G3/L4 with a one-line `on_wiki=` opt-in
  each — **out of scope now** (only G1 requested), but free to add later.

### §6 — Opts 18/19 (`gui/panels/distance_stars.py`) — the one structural change
Today `_build_results_area_distance` (`:128`) puts a flat `_tables_layout` (count label + a
single `QTableView`) inside `_tables_widget`, and each `_render` rebuilds it via
`_clear_tables_layout`. Restructure so the table area is a small tab widget:

- **`_build_results_area_distance`**: create `panel._results_tabs = QTabWidget()` inside
  `_tables_widget`; add a permanent, non-closable **"Results"** tab (index 0) whose inner
  `QVBoxLayout` is **still named `panel._tables_layout`** (relocate the existing layout into the
  Results tab rather than renaming it). Keep `panel._setup_diagram_view()` unchanged. Closable
  Wikipedia tabs are added beside "Results" (mirror `SearchPanelBase._on_tab_close`, index 0
  protected; dedupe by `("wiki", name)`).
  > **Why reuse the `_tables_layout` name (reviewer finding #3, a simplification):** both
  > `_render` methods call `self._tables_layout.addWidget(...)` in ~6 places each (count label,
  > table, and every error block — `:353/370/375/390` opt 18; `:456/473/479/494` opt 19). Keeping
  > the name means **only `_build_results_area_distance` changes** and every existing
  > `addWidget` keeps working — a far smaller, lower-risk diff than a `_results_inner` rename.
- **`_clear_tables_layout` (`:138`) is NOT deleted** — opt 17 (`DistanceBetweenStarsPanel`) calls
  it at `:80` and `:89` and keeps a plain `_tables_layout`. Add a **new** helper
  `_clear_results_tabs(panel)` that opts 18/19 call: it clears `_tables_layout` (now inside the
  Results tab) **and** closes any open Wikipedia tabs. Swap the `_clear_tables_layout(self)` calls
  in the opt-18/19 `_render`/error paths (`:349/363/452/466`) for `_clear_results_tabs(self)`.
- **`_render` (both)**: unchanged `self._tables_layout.addWidget(...)` for the count label +
  `view = make_table(...)`; keep `self._link_view = view` for O15 linking (unchanged — O15 keys off
  the QTableView object, not the container). Below the table, add a selection button **"📖 Open in
  Wikipedia →"**, disabled; enable it on table row selection
  (`view.selectionModel().selectionChanged`), and on click read the selected row's Star Name
  (column 0) and `open_or_focus_wiki_tab(panel._results_tabs, name, name=name, closable=True)`.
- **DiagramToggleMixin untouched**: `_tables_widget` is still hidden/shown as a whole; the chart
  tabs (`_viz_tabs_widget`), the Find-star box, and O15 row↔map linking all keep working — the
  new tabbing lives entirely inside the table view.
- Opt 17 (`DistanceBetweenStarsPanel`) is **not** in scope (two fixed stars, not a row list),
  but note the shared helpers must not break it — it uses `_tables_layout` directly and is
  left as-is (it does not call `_build_results_area_distance`; it builds its own — verify no
  shared-helper collision).

---

## 9. Title resolution detail (§5 of the mockup)

**Greek spelling for Bayer titles** — Wikipedia spells the Greek letter and uses the
constellation genitive: `τ Ceti → "Tau Ceti"`, `ε Eri → "Epsilon Eridani"`,
`α Cen → "Alpha Centauri"`. Implement `_bayer_wikipedia_title(raw)` in `core/wikipedia.py`:
- strip the `* ` prefix (`core.shared.strip_star_prefix`);
- split into the Greek token + constellation abbrev; strip trailing digits/superscripts from
  the Greek token (`alf01 → alf`) and drop the component letter (Wikipedia's primary article is
  the system, e.g. "Alpha Centauri");
- map the abbrev via a new `_GREEK_ENGLISH` table (`alf→Alpha … ome→Omega`, mirroring the
  existing `core.shared._GREEK_ABBREVIATIONS` symbol map);
- genitive via `core.shared.constellation_genitive`;
- unknown token → skip this candidate (don't invent).

Because every candidate is validated against the live API **and** the star guard, imperfect
candidate generation degrades gracefully to the next candidate or the not-found state.

**Full-article body (BUILT — post-review user feedback 2026-08-23):** the REST summary was
lead-only (one sentence), so after it resolves the article, `_fetch_extract` pulls the whole
article via the MediaWiki `action=query&prop=extracts` endpoint and it becomes `extract_html`
(best-effort — falls back to the summary lead). **External links (BUILT — same feedback):** WSL's
`xdg-open` has no browser, so `WikipediaView` handles clicks itself and `_open_url_external` routes
to the Windows browser on WSL (wslview → PowerShell → cmd), Qt's opener elsewhere.

---

## 10. Tests

> Read `docs/testing.md` before writing tests (per CLAUDE.md). All new tests are
> `unittest.TestCase` classes collected by pytest, run via `venv/bin/python -m pytest`.

### `tests/test_wikipedia.py` (offline, no network)
- `build_candidates`: order + spelled Bayer + `GJ`/`Gliese` doubling + dedupe; `name`-only path.
- `_bayer_wikipedia_title`: `* tau Cet→Tau Ceti`, `* eps Eri→Epsilon Eridani`,
  `* alf01 Cen→Alpha Centauri`, unknown constellation → skipped.
- `_is_star_article`: star description → True; disambiguation type → False; "genus of moth" → False.
- `resolve_and_fetch` with **monkeypatched `_fetch_summary`** (and `compute_simbad_lookup`):
  first candidate is a star → found + `matched_on`; first is non-star, second is star → found on
  second; all None → `{"found": False, tried:[…]}`; `_fetch_summary` raises → `{"error": …}`;
  name-path calls `compute_simbad_lookup` and uses its designations.

### `tests/test_wikipedia_live.py` (gated: `SPACE_APP_RUN_LIVE=1` + `_netcheck` reachability)
- `resolve_and_fetch(name="Tau Ceti")` → found; title "Tau Ceti"; url contains `/Tau_Ceti`;
  extract mentions a star word.
- `resolve_and_fetch(designations={"HD":"HD 10700"})` → resolves (redirect) to Tau Ceti.
- A deliberately unresolvable designation → `{"found": False}` (not `error`).
- `fetch_thumbnail(<known star thumб url>)` → non-empty `bytes`.

### `tests/test_wikipedia_panels.py` (offscreen Qt, offline — monkeypatch `resolve_and_fetch`/`fetch_thumbnail`)
- `WikipediaView`: the four states render the expected text into the `QTextBrowser`
  (found title; "No Wikipedia article"; error message; loading).
- `SimbadPanel`: render a canned SIMBAD result → `_wiki_btn` enabled → click adds a
  "📖 … — Wikipedia" tab to the tab widget.
- Opts 18/19: render a canned result → Results tab present → selecting a row enables the wiki
  button → click opens a closable Wikipedia tab; **Show Diagrams still builds the chart tabs**
  (regression guard for the restructure).
- G1 Search: a selected row shows the second button; clicking opens a `("wiki", name)` detail tab.
- **Main-thread delivery guard (reviewer finding #9):** a monkeypatched `resolve_and_fetch` can
  return synchronously and mask a wrong-thread delivery bug. Add an explicit test that captures
  `QThread.currentThread()` inside `WikipediaView._on_article` (via a real cross-thread worker, or
  by asserting it equals the app's main thread) — the standard GUI suite only exercises the
  `ResultPanel` delivery path, not `run_in_thread` on a non-`ResultPanel` owner.

### Regression
Full offline suite stays green with no new failures. Baseline: **3040 passed, 70 skipped, 494
subtests** (per CLAUDE.md, 2026-08-22). New offline tests add to `passed`; new live tests add to
`skipped` by default.

---

## 11. Validation

- **Automated:** `venv/bin/python -m pytest` green (offline). `SPACE_APP_RUN_LIVE=1
  venv/bin/python -m pytest tests/test_wikipedia_live.py` green with network up.
- **Manual (via the `run` skill / launching the GUI)** — confirm on real stars:
  - §1 SIMBAD "Tau Ceti" → Wikipedia tab shows the Tau Ceti article + thumbnail + working link.
  - §2 NASA opt 3 "HD 209458" → article. §3 HWC "TRAPPIST-1" → article. §4 OEC "55 Cancri" →
    article follows the selected host.
  - §5 Search: select a row → "Open in Wikipedia →" opens a detail tab. §6 opt 19 "Sol"/15 ly →
    select "Tau Ceti" row → opens a Wikipedia tab; **Show Diagrams / Find box still work**.
  - **States:** a gibberish name → not-found tab; disconnect network → error tab (no crash, no
    hang — background thread returns the classified error).
- **Resource safety (8 GB WSL box):** lightweight (text + one thumbnail); no QtWebEngine/Chromium;
  respects "one heavy job at a time".

---

## 12. Success criteria

1. All six surfaces show the button and open a Wikipedia tab lazily, per the approved mockup.
2. A correct star resolves to its article; a wrong candidate is **never** shown (guard + order).
3. Not-found and network-error states render calmly in the tab; no crash, no UI hang.
4. Opts 18/19 gain the row-click→tab flow **without** breaking Show Diagrams, the chart tabs,
   the Find-star box, or O15 row↔map linking.
5. No new pip dependency; no QtWebEngine; no `query.py`/CLI change.
6. Offline test suite green with new coverage; live tests skip cleanly by default.
7. Docs updated (§13).

## 13. Docs to update

- `CLAUDE.md` — one architecture line for `core/wikipedia.py` + the GUI Wikipedia tab.
- `docs/gui-architecture.md` — the button/tab per panel; the opts 18/19 table-view tabbing.
- `docs/star-databases.md` — a short "Wikipedia" note under the SIMBAD-fed panels (sibling to
  the M5 GCNS / Gould blocks).
- `docs/testing.md` — the three new test files.

---

## 14. Review strategy

### 14a. Plan review — **1 independent agent (DONE 2026-08-23)**
One general-purpose review agent verified the plan against the real code: (a) insertion
points/line numbers; (b) the `base.py` extraction; (c) the opts 18/19 restructure vs. opt 17 and
the diagram toggle; (d) the resolver contract/guard. **Outcome:** insertion points and reused-symbol
claims held up (§3/§4/§5 exact, §2 off by 1–2 lines — corrected in §8); the opts-18/19 restructure
confirmed safe for O15 linking, the Find box, the diagram toggle, and opt 17. **Nine findings folded
in** — the load-bearing one being §7 main-thread delivery affinity for a non-`ResultPanel` owner
(now specified), plus the §6 `_tables_layout`-reuse simplification, the §1 error-path button
disable, the §5 button-hide/reset points, the §4 OEC host-switch teardown note, and the dropped
"constellation" guard keyword. No second plan-review pass needed.

### 14b. `/code-review` during the build — **2 required + 1 optional final**
`/code-review` is run at effort **high**, scoped to the diff at each checkpoint:

1. **Checkpoint 1 — core + shared layer.** After `core/wikipedia.py`, the `base.py`
   `run_in_thread` extraction, and `gui/panels/wikipedia_tab.py` (`WikipediaView` + mixin) are
   built and unit-tested. This is the highest-logic, highest-risk code: network/resolver
   correctness, the star guard, 404-vs-error handling, and thread lifetime. **Run `/code-review
   high` here.**
2. **Checkpoint 2 — opts 18/19 restructure.** After the table-view→tabbed-container change and
   its regression tests. This is the most invasive UI change (tab management, diagram-toggle
   interaction, clearing logic, O15 linking). **Run `/code-review high` here, on the
   distance_stars diff.**
3. **Optional final — whole-diff pass** before commit, once all panels are wired. The catalog
   panels (§1–§4) and Search (§5) are repetitive/low-risk, so they don't each need their own
   review; a single final `/code-review` over the complete diff catches cross-panel
   inconsistencies. Recommended but skippable if checkpoints 1–2 are clean.

> `/code-review ultra` (the cloud multi-agent review) is **not** required here — the change is
> moderate and well-scoped; the two `high` checkpoints cover the risk. Escalate to `ultra` only
> if checkpoint 1 or 2 surfaces something structural.

---

## 15. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| **False article match** (bad candidate → wrong page) | Ordered candidates (proper name first) + `_is_star_article` guard + disambiguation reject. Never shows a page that fails the guard. |
| **404 spins `_with_retries`** | `_fetch_summary` returns `None` on 404 without raising, so no retry loop. |
| **Thread destroyed while tab closed mid-fetch** | Reuse the `_live_threads` registry via the shared `run_in_thread` (the existing GC guard). |
| **`base.py` refactor regresses every panel** | Behavior-preserving extraction; guarded by the full GUI suite; Checkpoint-1 `/code-review`. |
| **Wrong-thread delivery for `WikipediaView`** (builds `QTextBrowser`/`QImage` off the main thread) | `run_in_thread` delivers `finished` only via a bound method of a main-thread `QObject` (§7); explicit main-thread-affinity test (§10 finding #9); Checkpoint-1 `/code-review`. |
| **Opts 18/19 restructure breaks charts/Find/linking** | Tabbing lives inside `_tables_widget` only; explicit regression test that Show Diagrams still builds; Checkpoint-2 `/code-review`. |
| **Wikipedia UA blocked / rate-limited** | Descriptive UA; `_with_retries` honors `Retry-After`; lazy fetch (one request per user click, not per lookup). |
| **Thumbnail path is a brand-new pattern** | Strictly best-effort and secondary — text renders first; thumbnail failure is silent. |
| **Personal email leakage in UA** | UA carries app name only, no email (userEmail memory rule). |

---

## 16. Build order

1. `core/wikipedia.py` + `tests/test_wikipedia.py` (+ `tests/test_wikipedia_live.py`). Green offline.
2. `gui/panels/base.py` `run_in_thread` extraction (suite stays green).
3. `gui/panels/wikipedia_tab.py` (`WikipediaView` + mixin + open helper) + `test_wikipedia_panels.py` (view states).
4. **→ `/code-review high` (Checkpoint 1).**
5. §1 SIMBAD, then §2 NASA, §3 HWC, §4 OEC, §5 Search wiring (+ panel tests).
6. §6 opts 18/19 restructure (+ regression tests).
7. **→ `/code-review high` (Checkpoint 2, distance_stars diff).**
8. Docs (§13). Full suite green.
9. **→ optional final `/code-review` (whole diff).**
10. Commit (branch off `master`; the repo default-branch note in CLAUDE.md). Do **not** commit
    until the user asks.

---

## 17. Open questions for the user (none blocking)

- Wikipedia language: **English only** assumed (`en.wikipedia.org`). Multi-language is out of scope.
- Should the button also go on the G2/G3/L4 search panels? Base change makes it a one-liner each;
  only G1 ("Star Systems Search") was requested — left off the others.
