# PHASE S — Project Workspaces (Campaign / Novel Manager) · Implementation Plan

> **Scope.** S is the **last planned forward-looking phase** (A–S; J declined). It turns the app
> into a lightweight **worldbuilding workspace**: named projects that collect curated real
> (SIMBAD-looked-up) + procedurally-generated (R) systems with freeform notes, reopen any member
> later, and **export the whole project as one multi-system dossier**. **No new astronomy, no new
> physics** — S is persistence + composition over Q's `build_system_dossier` and R's
> `generate_system`, both reused verbatim. Phase **J** (a flat global favorites list) was declined;
> S is the project-scoped home that supersedes it.
>
> **Source files:** edits to `core/db.py` (two additive tables via `_migrate_schema` + two
> `get_table_status` rows), new `core/projects.py` (self-validating CRUD), an additive
> `core/report.py::build_generated_dossier` (the R→Q "Send to Dossier" link), new
> `gui/panels/projects.py` (`ProjectPanel`), +1 "Add to project" button each on `gui/panels/simbad.py`
> + `gui/panels/generator.py`, `gui/nav.py` (+ a "Projects" category) + `gui/panels/__init__.py`,
> `gui/panels/csv_utility.py` (`DbStatusPanel` rows), `query.py` (`project-list` / `project-get`),
> `docs/` updates, new `tests/test_projects.py` (+ additions to `tests/test_report.py`,
> `tests/test_query_*`, the panel smokes).
>
> **Companion mockups (approved 2026-06-24):** `PHASE_S_MOCKUP.md` (design + analysis) and
> `PHASE_S_MOCKUP.html` (master-detail layout). **No code until this plan is signed off** (house rule).

---

## 0. Decisions carried in (locked 2026-06-24 — user took the recommendations)

| # | Decision |
|---|---|
| D1 — generated-member persistence | **Store a `generated_spec` JSON blob** (seed + mode + spectral_class + n_planets + anchor_star + constraints + companion + research_policy) — reopening re-runs `generate_system(**spec)` → byte-identical (the R determinism contract). Keep `generated_seed INTEGER` as a denormalised display/convenience column. **Not** a bare seed (can't reproduce a sampled class/count or a constrained system) and **not** a frozen body (would drift from the engine / bloat the DB). |
| D6 — the R→Q link | **Build the generated-system dossier in S:** additive `core/report.py::build_generated_dossier(result, sections=None, fmt="markdown")` — pure composition over a `generate_system` result dict (identity + star props + the generated planet table + Source/grounding provenance), **no re-analysis**. This is the long-deferred "Send to Dossier" handoff; S is its natural home (a generated member has no other writeup path, and `build_system_dossier` needs a SIMBAD-resolvable name). |
| D3 — export layout | **Offer both** in the export dialog — one **combined** multi-system document (default) or one file **per member** (Q-batch style). |
| D5 — "Add to project" reach | **`SimbadPanel` + `SystemGeneratorPanel`** (the primary real + generated sources). Other panels (HWC/NASA/GCNS) are thin additive follow-ons, out of S scope. |
| D2 — member key / collisions | `star_name` is the per-project PK; a collision on add (two `Gen-88`s) gets a **`" (2)"` suffix**. The spec, not the name, carries reproduction. |
| D4 — `query.py` surface | **Read-only `project-list` / `project-get` only** (mutations stay GUI-only — the "no DB-write subcommands" principle). No `project-dossier` reader in S (export spans network + offline members → GUI-first; additive later if the consumer asks). |
| D7 — nav placement | **New top-level "Projects"** nav category (a workspace, not a report; export lives inside it). |

Standing invariants: **no existing behaviour changes** (additive tables + nav category + ≤1 button
per touched panel; new tables not auto-seeded); generated members reproduce **byte-identically** from
their stored spec; full suite stays green at each checkpoint.

---

## 1. Design summary (the one rule)

`core/projects.py` and `core/report.py::build_generated_dossier` stay **pure** (no Qt). The only I/O
is SQLite (via the existing `core.db.get_conn()`, tmp-swappable through `_DB_PATH` for tests) and, in
the export path, the network reads Q/R already own. **A generated member persists its spec, never a
frozen body** — so it can never drift from the generator; reopening / exporting re-runs
`generate_system(**spec)` and relies on the R1/R2/R3 determinism contract (already test-guarded).

Public surface:

```python
# core/projects.py — all self-validating ({"error": str} on bad input)
create_project(name, description="") -> dict
list_projects() -> list                       # [{project_id, name, description, created_date, member_count}]
get_project(name) -> dict                      # {project:{...}, members:[{star_name, note, source,
                                               #   generated_seed, generated_spec(parsed), added_date}]}
add_member(name, star_name, note="", source="looked_up", seed=None, spec=None) -> dict   # INSERT OR REPLACE
update_note(name, star_name, note) -> dict
remove_member(name, star_name) -> dict
rename_project(old, new) -> dict
delete_project(name) -> dict                   # cascades to project_members (one transaction)

# core/report.py (additive — the R→Q link)
build_generated_dossier(result, sections=None, fmt="markdown") -> dict   # result = a generate_system dict
```

---

## 2. Data model — `core/db.py` (additive, not auto-seeded)

Two tables added in `_create_schema` (declared alongside the GCNS/Hypatia tables; empty until used)
and picked up on existing DBs by the idempotent `_migrate_schema` (the GCNS `ALTER`/`CREATE IF NOT
EXISTS` precedent):

```sql
CREATE TABLE IF NOT EXISTS projects (
    project_id   INTEGER PRIMARY KEY,
    name         TEXT UNIQUE NOT NULL,
    description  TEXT,
    created_date TEXT
);
CREATE TABLE IF NOT EXISTS project_members (
    project_id     INTEGER NOT NULL,
    star_name      TEXT NOT NULL,
    note           TEXT,
    source         TEXT NOT NULL,        -- 'looked_up' | 'generated'
    generated_seed INTEGER,              -- generated only (display convenience)
    generated_spec TEXT,                 -- generated only: JSON of the generate_system params (D1)
    added_date     TEXT,
    PRIMARY KEY (project_id, star_name)
);
CREATE INDEX IF NOT EXISTS idx_project_members_pid ON project_members(project_id);
```

`get_table_status()` gains two rows (**Projects**, **Project Members**). Neither table is
auto-seeded. `created_date`/`added_date` are provenance timestamps (`datetime.date.today()`-style,
like GCNS `snapshot_date`) — not part of any reproduced body, so determinism of generated members is
unaffected.

---

## 3. `core/projects.py` — self-validating CRUD

- **Validation (Phase-H contract → curated `{"error": str}`):** blank name → error; duplicate name
  on `create`/`rename` → error; unknown project on `get`/`add_member`/`update_note`/`remove_member`/
  `rename`/`delete` → error; blank `star_name` on add → error. `source ∈ {looked_up, generated}`.
- **Idempotency:** `add_member` uses `INSERT OR REPLACE` on the `(project_id, star_name)` PK (re-add
  updates note/spec). `remove_member`/`delete_project` are no-error no-ops when absent (idempotent),
  except `delete_project` of an unknown name returns `{"error"}` (a clear miss, not a silent no-op).
- **D2 collision suffix:** `add_member` resolves a `star_name` already present (and not the same
  source/seed) by appending `" (2)"`, `" (3)"`, … The chosen final name is returned in the result so
  the GUI can show it.
- **`generated_spec`** is stored as `json.dumps(spec)`; `get_project` returns it parsed. The spec is
  whatever `SystemGeneratorPanel` snapshots (the same `_last_params`-style dict R already builds).
- **DB isolation:** tests monkeypatch `core.db._DB_PATH` to a tmp file (the `test_db_backups.py`
  pattern); auto-seed is irrelevant (these tables aren't seeded).

---

## 4. `core/report.py::build_generated_dossier` (the R→Q link, D6)

Additive, **pure composition** over a `generate_system` result dict (no SIMBAD, no re-analysis):
- **Input:** a result dict from `generate_system` (synthetic or real-anchor; with or without a
  feasibility envelope).
- **Sections** (a subset of Q's vocabulary that a generated dict can fill): `identity` (name,
  spectral class, mode, seed, grounding/provenance), `star` (teff/mass/radius/luminosity/HZ/snow
  line), `planets` (the generated planet table — a_au, mass, radius, type, t_eq, in_hz, source,
  moons), and — when present — `feasibility` (the four-layer constraint summary). `notes`/`warnings`
  carried through.
- **Formats:** `markdown` / `html` / `json` (same three as `build_system_dossier`; json = structured
  data only; html self-contained text+tables, no `<img>` — matching Q's `query.py` contract).
- **Self-validating:** a bad `fmt`/`sections`, or a result carrying `{"error"}`, → `{"error"}`.
- **Refactor note:** factor any shared renderer helpers out of `build_system_dossier` only if
  byte-identical (guarded by `test_report.py`); otherwise keep the generated composer self-contained.

This is the **only** new "astronomy-adjacent" code in S, and it's pure presentation over an existing
dict.

---

## 5. GUI — `ProjectPanel` + entry points (`gui/panels/projects.py`)

New **"Projects"** nav category (top-level). `ProjectPanel(ResultPanel)` — master-detail:
- **Left:** project list (create / rename / delete; member-count per row). Selecting a project loads
  its members.
- **Right:** member table — *Star · Note · Source (looked-up / generated · seed N) · Added* — with
  **inline note editing** (double-click → `update_note`), per-row **Open** (real → embed a
  `SimbadPanel` set to the name + `_search()`; generated → re-run `generate_system(**spec)` and show
  it via an embedded generator/result view), and **Remove** (`remove_member`).
- **Export Project Dossier** → a small dialog (format radio · Q `--sections` · **combined vs
  per-file**, D3) → the §6 fan-out on `run_in_background` (real members hit the network; generated
  synthetic ones don't).
- **Entry points (additive, guarded — panels unchanged until clicked):**
  - `SimbadPanel` → **"Add to project ▾"** (pick/-create project → `add_member(source="looked_up")`).
  - `SystemGeneratorPanel` → **"Add to project ▾"** (snapshot the current generation spec →
    `add_member(source="generated", seed=…, spec=…)`); disabled until a successful generation.
- `DbStatusPanel` (opt 57) appends **Projects** / **Project Members** rows (via `get_table_status`).
- Register `ProjectPanel` in `gui/nav.py` + `gui/panels/__init__.py`.

---

## 6. Export composition (the §5 button)

For each member in project order:
- `source == "looked_up"` → `report.build_system_dossier(star_name, sections, fmt)` (verbatim Q;
  handles `Sol`/`Sun` offline).
- `source == "generated"` → `generate_system(**generated_spec)` then
  `report.build_generated_dossier(result, sections, fmt)` (S-C2).
Then **combine** (D3): a project title/description header + each member's section concatenated (one
document), **or** one file per member (Q-batch style). A per-member failure becomes a warning line in
the combined doc (or a skipped file + status note), never aborts the whole export — the Q
three-tier-validation spirit.

---

## 7. `query.py` — read-only `project-list` / `project-get` (D4)

- **`project-list`** → `core.projects.list_projects()` → the list shape above.
- **`project-get --name <name>`** → `core.projects.get_project(name)` (members' `generated_spec`
  echoed as parsed JSON), or `{"error"}` exit 1 (unknown name); argparse exit 2 for a missing
  `--name`.
Both local-DB reads (no network), overridable via `SPACE_APP_DB` (the subprocess-test pattern). No
mutation/export subcommand (D4).

---

## 8. Tests (offline; tmp DB)

- **`tests/test_projects.py`** (new; `core.db._DB_PATH` tmp-swap):
  - CRUD round-trips; unique-name enforcement (create + rename); unknown-project errors; blank-name/
    blank-star errors; membership idempotency (`INSERT OR REPLACE`); the **D2 collision suffix**;
    `get_project` shape; `delete_project` cascade (members gone, one transaction); `list_projects`
    member-count.
  - **Generated-spec round-trip (headline):** `add_member(spec=…)` → `get_project` returns the parsed
    spec → `generate_system(**spec)` is **deep-equal** to the original generation (the R determinism
    contract, in the workspace).
- **`tests/test_report.py`** (additions): `build_generated_dossier` — md/html/json shapes; a
  synthetic + a real-anchor (mocked) result render; a feasibility-envelope result includes the
  four-layer summary; bad-fmt / error-result → `{"error"}`; determinism.
- **`tests/test_query_projects.py`** (new; subprocess, throwaway `SPACE_APP_DB`): `project-list` /
  `project-get` happy paths + parsed-spec echo; unknown-name exit 1; argparse exit 2. (Seed the tmp
  DB in-process via `core.projects` before the subprocess read.)
- **`tests/test_projects_panel.py`** (new; offscreen GUI smoke): `ProjectPanel` construction,
  create/select/member-render, inline-note edit, Open routing (real vs generated), the export dialog
  + a mocked fan-out, nav/export registration; the two "Add to project" buttons on `SimbadPanel` /
  `SystemGeneratorPanel` (add → membership written); the `DbStatus` rows.

---

## 9. Numbered checkpoints (one at a time; full suite green at each; stop for review)

> Run headless: `QT_QPA_PLATFORM=offscreen venv/bin/python -m unittest discover -s tests -q`.
> **3 live-network failures are the expected baseline.** Each checkpoint ends with a GUI test plan
> where relevant.

| CP | Deliverable | Gate |
|---|---|---|
| **S-C1** | `core/db.py` two additive tables (`_migrate_schema`) + `get_table_status` rows + `core/projects.py` CRUD (incl. D2 suffix) + `tests/test_projects.py` (incl. the generated-spec round-trip) | suite green; pure/offline |
| **S-C2** | `core/report.py::build_generated_dossier` (the R→Q link, D6) + `tests/test_report.py` additions | suite green |
| **S-C3** | `query.py project-list` / `project-get` (read-only) + `tests/test_query_projects.py` | suite green |
| **S-C4** | `ProjectPanel` (master-detail, inline notes, Open, Remove) + "Projects" nav category + headless smokes | suite green |
| **S-C5** | **Export Project Dossier** (the §6 fan-out: real → Q, generated → S-C2; combined + per-file, D3) + the export dialog + smokes | suite green |
| **S-C6** | **"Add to project"** on `SimbadPanel` + `SystemGeneratorPanel` + `DbStatus` rows + smokes; **manual GUI verify** | suite green; **manual GUI verify** |
| **S-C7** | Docs (`CLAUDE.md` test inventory + the new tables/category, `docs/gui-architecture.md` panel + nav + DbStatus, `docs/integration.md` the two readers + `build_generated_dossier`, `future_phases.md` S→done / roadmap complete) + final full-suite green | suite green |

---

## 10. Success criteria (S)

A worldbuilder can create named projects, add real (looked-up) and procedurally-generated systems
with freeform notes, reopen any member later (generated ones re-creating **byte-identically** from
their stored spec), and **export an entire project as one multi-system dossier** (real members via Q,
generated members via the new R→Q `build_generated_dossier`). Projects persist across sessions in two
additive, not-auto-seeded tables; `query.py project-list`/`project-get` let the sibling repo drive a
whole setting read-only; mutations stay GUI-only; the generated-member determinism contract holds
(add → reopen → export are deep-equal to the original generation). **No existing behaviour changes**
(additive tables + nav category + ≤1 button per touched panel); suite green (offscreen, 3 live-net
baseline). **Phase S completes the planned roadmap (A–S; J declined).**
