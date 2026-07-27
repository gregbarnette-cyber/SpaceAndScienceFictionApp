# PHASE Q — System Dossier Export & Reporting · Implementation Plan

> **Scope.** Render the rich per-system data the app already computes into one shareable
> **Markdown / HTML / JSON dossier**. **No new astronomy** — pure composition + templating
> over existing readers. **GUI-only feature work + `query.py` parity** (the CLI menu is frozen
> at opts 1–58; the new panel carries no option number, like `DbStatusPanel`). Source files:
> new `core/report.py`, new `gui/panels/reports.py` (one panel) + `gui/panels/__init__.py` +
> `gui/nav.py` (one new **"Reports"** nav category), `query.py` (one `dossier` subcommand),
> `docs/` updates, new `tests/test_report.py`.
>
> **Companion mockup (approved):** `PHASE_Q_MOCKUP.md` — anchors both a normal star (Tau Ceti,
> all six sections + full Phase P surface) and the Solar System (Sol, the reference-origin path).
> All 13 layout decisions are locked there; this plan implements them. **No code until this plan
> is signed off** (house rule).

---

## 0. Design summary (the one rule)

`core/report.py` stays **pure** — no Qt, no file I/O, no new computation. It *reads* the
existing `core/` result dicts, merges them, and returns a **string** (md/html) or a
**structured data dict** (json). Two consequences locked in the mockup:

- **Diagrams are GUI-only (decision #5, option A).** The drawing helpers live in `gui/` and
  return Qt widgets; `core/report.py` can't touch them. So `query.py dossier --fmt html` is
  **text + tables only**; only `DossierExportPanel` splices base64 figures into *its own*
  preview/save (§7). This keeps the `core↔Qt` boundary clean.
- **Warnings ≠ notes (decisions #7, #11).** A source that *fails / returns nothing for a real
  star* → a `warnings[]` entry (section omitted, dossier still renders). A *by-design* omission
  (GCNS-N/A on Sol) → a `notes[]` entry. The **only** hard `{"error"}` is a SIMBAD-lookup
  failure (no such star) or a bad `fmt`/`section` argument.

---

## 1. Reader orchestration — the data assembly

`build_system_dossier` first branches on whether the target is Sol, then assembles a
per-section **data dict** from the existing readers. Every reader is called **verbatim**.

### 1a. Normal-star path — `_assemble_star(star) -> (data, warnings, notes)`

| Section key | Reader (verified) | Notes |
|---|---|---|
| `identity` | `databases.compute_simbad_lookup(star)` (`databases.py:115`) | The spine — runs first; its `{"error"}` aborts the whole dossier. Carries the M5 `gcns` block for free. |
| `regions` | `regions.compute_star_system_regions_from_simbad(simbad)` (`regions.py:273`) | Returns `{"error"}` for a non-OBAFGKM type (white dwarf) → **warning**, regions+HZ omitted. |
| `habitable_zone` | `equations.compute_habitable_zone(temp, L)` ×3 | Called with `bcLuminosity`, `luminosityFromMass`, `calculatedLuminosity` from the regions dict → the 3-column Kopparapu table (mirrors `_display_calculated_hz`). Skipped if `regions` failed. |
| `planets` | `databases.compute_planetary_systems_composite(simbad)` **(priority 1)** + `databases.compute_hwc(simbad)` **(priority 2)** | **Both shown when both resolve** (decision #3). Each → its own sub-table. Neither resolves → **warning**, section omitted. |
| `hypatia` | `databases.compute_hypatia_data(simbad)` (`databases.py:1376`) | `{"error"}` / empty abundances → **warning**, section omitted. **All** measured species rendered, grouped by family (decision #2). |
| `gcns` | `simbad["gcns"]` (M5 block — no extra call) | `None` → **warning** ("no Gaia id / not in GCNS"), section omitted. |

`compute_simbad_lookup` is the only network call shared across sections; the rest each add
their own network round-trip (NASA/HWC/Hypatia). The GUI runs the whole thing on a background
thread (§7); `query.py` is synchronous.

### 1b. Sol path — `_assemble_sol() -> (data, warnings, notes)`

Triggered by `star.strip().lower() in {"sol", "sun"}` (the app-wide Sol convention). **Fully
offline** (local DB + constants). Maps each section to its Sol-special-case source:

| Section key | Sol source (verified) | Notes |
|---|---|---|
| `identity` | Hardcoded solar constants | G2V, V −26.74, distance ≡ 0 (frame origin), designations `—`. |
| `regions` | `regions.compute_sol_regions()` (`regions.py:344`) | **Same flat dict shape** as the normal path → the regions/HZ renderers are unchanged. |
| `habitable_zone` | `equations.compute_habitable_zone(5778, L)` ×3 | Same as normal, with Sol's region luminosities. |
| `planets` | `science.compute_solar_system_tables()` (`science.py:38`) | Real Solar System: `planets` + `dwarf_planets` + `asteroids` sub-tables (decision #3 generalizes: show all real bodies). `moons` is **opt-in only** (decision #13). |
| `hypatia` | Solar zero-point baseline (`_sol_compare_entry` pattern, `databases.py:3051`) | Every `[X/H] ≡ 0.0`, `n=0`; U/V/W ≡ 0. Rendered with the same family grouping. |
| `gcns` | — | **N/A** → a `notes[]` entry, **not** a warning. Excluded from the default section list. |
| `moons` | `compute_solar_system_tables()["moons"]` | **Off by default**; opt-in via `--sections … moons`. Per-planet moon sub-tables. |

> Factor the Sun Hypatia baseline out of `_sol_compare_entry` into a small shared helper
> (e.g. `databases._sun_hypatia_baseline()`) so Q and `compare_stars` share one definition;
> `_sol_compare_entry` calls it. (Refactor-in-place, byte-identical output — guard with the
> existing `test_comparison.py` Sol assertions.)

---

## 2. `core/report.py` — public API

```python
_ALL_SECTIONS   = ["identity", "regions", "habitable_zone", "planets", "hypatia", "gcns"]
_SECTION_ORDER  = ["identity", "regions", "habitable_zone", "planets", "hypatia", "gcns", "moons"]
_OPTIN_SECTIONS = {"moons"}        # never in the default set; valid only when explicitly named
_FORMATS        = {"markdown", "html", "json"}

def build_system_dossier(star: str, sections: list[str] = None,
                         fmt: str = "markdown") -> dict:
    """Compose a system dossier from existing readers. Pure (no Qt/I/O)."""
```

**Control flow**
1. **Validate** `fmt ∈ _FORMATS` and every requested `section ∈ _SECTION_ORDER` → else
   `{"error": "unknown format 'x'"}` / `{"error": "unknown section 'x'"}` (exit 1 via `_out`).
2. **Resolve the section set.** `sections=None` → `_ALL_SECTIONS` (Sol drops `gcns`).
   Explicitly-named-but-unavailable section → render available + a warning (decision #11).
3. **Assemble** via `_assemble_sol()` or `_assemble_star()` → `(data, warnings, notes)`.
   A `{"error"}` from `compute_simbad_lookup` returns immediately (hard error).
4. **Render** the selected, available sections in `_SECTION_ORDER`:
   - `fmt="markdown"` / `"html"` → `document` string (warnings/notes footer appended — decision #10).
   - `fmt="json"` → `data` dict (structured section dicts; **no** rendered string — decision #4).
5. **Return the envelope.**

**Envelope shapes**
```python
# markdown / html
{"star", "fmt", "sections": [rendered keys], "warnings": [...], "notes": [...], "document": str}
# json
{"star", "fmt": "json", "sections": [...], "warnings": [...], "notes": [...], "data": {...}}
```

**Internal structure** — one builder per section returning a plain dict (the json `data`
payload), and one renderer per format consuming those dicts:
- `_identity_data(simbad|sol) -> dict`, `_regions_data`, `_hz_data`, `_planets_data`,
  `_hypatia_data`, `_gcns_data`, `_moons_data` — pure dict shaping (designation subset,
  number rounding, label maps). The regions builder pulls the **full Phase P surface**
  (decision #9): system regions + the 10 alt-solvent bands (`ffInner…phOuter`,
  `co2*`/`s*`/`wa*`/`sa*`) + the ice fronts (`iceLineNH3/CO2/N2/CO`) + `snowLine`/`lh2Line`.
- `_render_markdown(sections_data, star, warnings, notes) -> str` — hand-rolled f-strings
  (no Jinja; house style), one `## Heading` + table per section, warnings/notes footer.
- `_render_html(...) -> str` — same content; self-contained `<style>`, `<table>` markup.
- `_render_json(...)` — returns the merged `data` dict directly.

---

## 3. Section render spec (the column contracts)

Mirror the mockup exactly. Key sources (all from the regions/simbad/reader dicts):

- **identity** — `main_id`, common name (`designations["NAME"]` stripped), `sp_type`,
  curated designations (`NAME, HD, HIP, GJ, HR, Gaia EDR3`), `ra`/`dec`, `vmag`, `plx_value`,
  `parsecs`+`ly`. Sol: hardcoded.
- **regions** — Stellar Properties table (`temp, stellarMass, stellarRadius, bcLuminosity,
  luminosityFromMass, calculatedLuminosity, mainSeqLifeSpan`); System Regions table
  (`sysilGrav, sysilSunlight, hzil, hzol, snowLine, lh2Line, sysol`); **Alternate Solvent
  Habitable Zones** (10 bands, inner/outer AU, sorted inner→outer, CO₂ flagged
  pressure-conditional); **Condensation / Ice Lines** (`snowLine` + the 4 ice fronts).
- **habitable_zone** — 6 Kopparapu zones × 3 luminosity columns.
- **planets** — *NASA pscomppars* sub-table (`pl_bmasse, pl_rade, pl_orbsmax, pl_orbper,
  pl_orbeccen, pl_orbincl, discoverymethod`, sorted by `pl_orbsmax`) then *HWC* sub-table
  (`P_MASS, P_SEMI_MAJOR_AXIS, P_TYPE, P_HABZONE_CON, P_ESI, P_HABITABLE`). Sol: Planets /
  Dwarf Planets / Asteroids tables from `compute_solar_system_tables()` (column-aliased dicts).
- **hypatia** — properties line (`teff, logg, disk`, [Fe/H]) + per-family abundance tables
  (`element, [X/H] mean, ±std, n`) over **all** measured species, grouped by
  `core.hypatia_elements.CATEGORIES` order.
- **gcns** — `gaia_source_id, distance_method, dist_pc (+dist_lo/hi), light_years,
  phot_g/bp/rp, astrom_reliable_prob, wd_prob`, resolved-system pointer. Sol: the N/A note.

---

## 4. `query.py dossier` subcommand

Handler + subparser (single-star — decision #12), following the `cmd_solvent_zone` pattern:

```python
def cmd_dossier(args):
    _out(report.build_system_dossier(args.star, sections=args.sections, fmt=args.fmt))

# in build_parser():
p = sub.add_parser("dossier", help="Render a full system dossier (markdown/html/json)")
p.add_argument("--star", required=True, help="Star name, or 'Sol'/'Sun' for the Solar System")
p.add_argument("--fmt", choices=["markdown", "html", "json"], default="markdown")
p.add_argument("--sections", nargs="+",
               help="Subset of: identity regions habitable_zone planets hypatia gcns moons "
                    "(default: all available; 'moons' is Sol-only opt-in)")
p.set_defaults(func=cmd_dossier)
```

Add `import core.report as report` at the top. `_out` already prints the dict and sets the
exit code; for md/html the **document** field is the useful payload (consumers read
`result["document"]`); for json the **data** field. (No special stdout handling — `_out`
serializes the whole envelope, consistent with every other subcommand.)

> **Validation contract:** bad `--fmt`/unknown `--sections` value → argparse or core
> `{"error"}` (exit 1); SIMBAD-fail → `{"error"}` (exit 1); a real star missing a source →
> exit 0 with `warnings`. Sol → exit 0, fully offline. (Self-validating — Phase H contract.)

---

## 5. GUI — `DossierExportPanel` (`gui/panels/reports.py`)

A `ResultPanel` (no `DiagramToggleMixin` — it has no embedded viz tabs; it composes its own
document). New **"Reports"** nav category with one entry.

- **Form** (`build_inputs`): star `QLineEdit`; a row of section `QCheckBox`es (identity /
  regions / habitable_zone / planets / hypatia / gcns, all checked by default; a separate
  "moons (Sol only)" checkbox, unchecked); a `QButtonGroup` format radio (Markdown / HTML);
  **Generate** button; hidden red `_err` label.
- **Background generate** (`run_in_background`, since it runs network readers) →
  `build_system_dossier(star, sections, fmt)`. On result: render the **preview pane**
  (`QTextBrowser` — renders HTML; shows Markdown as monospace text) + show any
  `warnings`/`notes` in a muted label + reveal **Save to file…** (`QFileDialog`, default
  extension by fmt).
- **Option-A images (GUI-only).** When `fmt="html"` *and* `mpl_available()`, the panel
  enriches its own HTML: build the HZ-ring (`make_hz_canvas`) and abundance
  (`make_abundance_canvas`) Qt canvases from the already-fetched data, `figure.savefig(buf,
  format="png")`, base64-encode, and splice `<img>` tags into the document before
  preview/save. `core.report` never sees this — it's pure panel enrichment.
- **Batch mode** (decision #12 — GUI-only): a "Batch…" button opens a dialog with a
  multiline star list; iterates `build_system_dossier` per star (background), writes one file
  each to a chosen directory, reports a per-star success/warning summary. (The Phase S hook:
  "export a whole project at once.")
- **Registration:** export `DossierExportPanel` in `gui/panels/__init__.py`; add
  `("Reports", [("System Dossier Export", "DossierExportPanel")])` to `gui/nav.py` `NAVIGATION`.

---

## 6. Tests — `tests/test_report.py` (offline, mocked readers)

Pattern: `unittest.mock.patch` the `core.report` references to `compute_simbad_lookup` /
`compute_star_system_regions_from_simbad` / `compute_hypatia_data` /
`compute_planetary_systems_composite` / `compute_hwc`, and `compute_solar_system_tables` —
feed fixed fixtures (a Tau-Ceti-like dict + an empty-source dict). No network, no Qt.

| Test | Asserts |
|---|---|
| `test_markdown_shape` | All six sections render in `_SECTION_ORDER`; document is a non-empty str; envelope keys present. |
| `test_json_structured_only` | `fmt="json"` → `data` dict, **no** `document` key (decision #4). |
| `test_html_self_contained` | `fmt="html"` contains `<style>`, no external `src=`/`href=`; **no** `<img>` (images are GUI-only). |
| `test_section_selection` | `sections=["identity","gcns"]` renders only those (order preserved). |
| `test_unavailable_section_warns` | Requesting `planets` for a no-planet star → exit-0 envelope, section omitted, a `warnings[]` entry (decision #11). |
| `test_source_failure_isolation` | Hypatia `{"error"}` / regions white-dwarf `{"error"}` → warnings, dossier still renders other sections. |
| `test_sol_path` | `star="Sol"` (and `"sun"`) → offline (no SIMBAD call), planets from `compute_solar_system_tables`, Hypatia all-zero, `gcns` absent + a `notes[]` entry. |
| `test_sol_moons_optin` | `moons` absent by default; present only when explicitly requested (decision #13). |
| `test_full_phase_p_surface` | Regions section includes the 10 solvent bands + 4 ice fronts + snow line (decision #9). |
| `test_bad_args` | Unknown `fmt`/`section` → `{"error"}`; SIMBAD-fail fixture → `{"error"}` (the only hard errors). |
| `test_deterministic` | Same fixture → byte-identical document (no `Date.now`/RNG). |
| `test_query_dossier` | Subprocess `query.py dossier --star … [--fmt/--sections]` via a throwaway `SPACE_APP_DB`: happy path exit 0, json shape, argparse exit 2 for bad `--fmt`. (Mirrors `test_query_phase_n.py`.) |

---

## 7. Docs updates (same commit as code)

- **`docs/integration.md`** — new `dossier` row in the quick-reference table + a subcommand
  section (args, the md/html/json envelopes, the warnings/notes model, the Sol path, the
  "no images in `query.py html`" caveat). Bump the "61 subcommands" count to 62.
- **`docs/gui-architecture.md`** — new "Reports" nav category + `DossierExportPanel` in the
  panel-class table and the repo-structure tree (`panels/reports.py`); note the GUI-only
  base64 image enrichment and batch mode; add a Phase Q row to the Phase-completion table.
- **`future_phases.md`** — move Phase Q from "candidate" to a completed-style entry (pointer
  to `PHASE_Q_PLAN.md` + `docs/`); update the Q/R/S priority note.
- **`CLAUDE.md`** — add `tests/test_report.py` to the test inventory; add `core/report.py`
  to the `core/` description.

---

## 8. Build sequence (checkpoints — one at a time, stop for GUI verify)

The project's checkpoint cadence (memory: `phase-o-checkpoint-cadence`): each checkpoint
ends with a detailed GUI test plan; additive/non-breaking; suite stays green.

1. **Q-core-1 — `core/report.py` normal-star path** (identity/regions/HZ/hypatia/gcns +
   markdown renderer + warnings model) + the `_sun_hypatia_baseline` refactor. Tests:
   markdown/json/section-selection/source-isolation. *(No GUI yet — verify via `query.py`.)*
2. **Q-core-2 — planets section** (NASA + HWC dual sub-tables) + **full Phase P regions
   surface** + **HTML renderer**. Tests: planets dual-source, phase-P-surface, html-self-contained.
3. **Q-core-3 — Sol path** (`_assemble_sol`, solar-system planets/dwarfs/asteroids, moons
   opt-in, gcns→note). Tests: sol-path, sol-moons-optin.
4. **Q-query — `query.py dossier`** subcommand + `test_query_dossier` + `docs/integration.md`.
5. **Q-gui — `DossierExportPanel`** (form + preview + save + option-A base64 images + batch)
   + nav/registration + `docs/gui-architecture.md`. GUI verify: generate Tau Ceti (all
   sections, HTML images present) + Sol (offline, real planets, no GCNS) + a no-data star
   (warnings shown, dossier still renders) + Save-to-file + Batch over 2–3 stars.

---

## 9. Locked decisions (from `PHASE_Q_MOCKUP.md`)

| # | Decision |
|---|---|
| 1 | Section order `identity → regions → HZ → planets → hypatia → gcns` |
| 2 | Hypatia: all measured species, grouped by family |
| 3 | Planets: both shown — NASA pscomppars priority 1, HWC priority 2 |
| 4 | `fmt=json`: structured `data` only |
| 5 | HTML images: option A (GUI-only base64; core/query.py text-only) |
| 6 | Sol/Sun: dedicated reference-origin path |
| 7 | Add additive `notes` field (separate from `warnings`) |
| 8 | No worldbuilding-physics enrichment — pure composition |
| 9 | Full Phase P surface (all solvent bands + ice fronts) |
| 10 | Warnings/notes footer in the document too |
| 11 | Unavailable requested section → warnings + render available; only SIMBAD-fail is hard error |
| 12 | `query.py dossier` single-star; batch is GUI-only |
| 13 | Sol `moons` off by default, opt-in |

Minor defaults adopted: identity designations = curated subset (common name + HD/HIP/GJ/HR/Gaia);
HTML self-contained inline `<style>`; field-merge precedence = regions-computed stellar values win.

---

## 10. Validation contract (consolidated)

`build_system_dossier` **self-validates** (the Phase H contract — curated `{"error"}` messages,
**not** the Phase N raw-exception path). Three tiers:

| Tier | Trigger | Behavior |
|---|---|---|
| **Hard error** (`{"error"}`, exit 1) | bad `fmt` (∉ markdown/html/json); unknown `--sections` value; **SIMBAD lookup fails for a real star** (no such star / network) | Aborts the dossier; curated message. (`query.py`: a bad `--fmt` is caught earlier by argparse `choices` → exit 2.) |
| **Soft degrade — warning** (exit 0, `warnings[]`) | a per-source reader fails/returns nothing for a real star (no NASA+HWC planets; Hypatia empty; regions `{"error"}` on a white dwarf; no Gaia id for GCNS); a section is explicitly requested but unavailable | Section omitted; the rest of the dossier still renders. |
| **By-design note** (exit 0, `notes[]`) | GCNS-N/A on Sol (the reference origin); other intentional omissions | Section omitted; flagged as expected, **not** a failure. |

Plus the structural invariants the tests lock: **purity** (`core/report.py` imports no Qt and
does no file I/O — the save is GUI-only), **determinism** (no `Date.now`/RNG → same inputs
give a byte-identical document), and **format integrity** (`fmt=json` carries `data` and **no**
`document`; `fmt=html` is self-contained with **no** `<img>`/external assets — images are the
GUI's own option-A enrichment).

## 11. Success criteria (acceptance)

Phase Q is done when **all** of the following hold:

1. **One call → a complete dossier.** `query.py dossier --star "Tau Ceti"` returns a
   self-contained writeup spanning every available section (identity, regions + full Phase P
   surface, Kopparapu HZ, NASA+HWC planets, all Hypatia species, GCNS) — the single-call win
   for the downstream `scifiWorldBuilding` repo.
2. **Graceful degradation.** A star missing a source (no planets / no Hypatia / white-dwarf
   regions) still produces a dossier with the rest of its sections + `warnings[]` — never a
   crash or a hard error (only a non-existent star errors).
3. **Sol parity, offline.** `query.py dossier --star Sol` produces the **same-shaped** document
   with **no network**, using the real Solar System bodies (`compute_solar_system_tables`),
   the solar zero-point Hypatia baseline, and a GCNS-N/A `notes[]` entry; `--sections … moons`
   adds the satellite census.
4. **All three formats.** markdown (default), html (self-contained text+tables), and json
   (structured `data` only) each render correctly; the GUI HTML preview/save additionally
   carries the base64 HZ-ring + abundance figures when matplotlib is available.
5. **Nothing else changes.** No existing panel, subcommand, or output is altered; the
   `_sun_hypatia_baseline` refactor is byte-identical (guarded by `test_comparison.py`'s Sol
   assertions). `query.py` subcommand count → 62.
6. **Suite green.** `tests/test_report.py` passes offline (`QT_QPA_PLATFORM=offscreen`); the
   full suite remains green against the known 3 live-network skips baseline.

**Per-checkpoint acceptance** (gates §8): each checkpoint lands with its own tests passing and
a manual GUI verification (for Q-gui) before the next begins — the project's checkpoint cadence.
