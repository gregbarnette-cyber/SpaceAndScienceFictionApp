# Spectral-Class Prefix Plan — search chips (Part 1) + colour/legend (Part 2)

**Status: BOTH PARTS BUILT (2026-07-27).** Suite 2100 passed / 1 skipped
(baseline before this work: 2084).

One workstream, two commits. The reported symptom was that Wolf 359 (`dM6`) and
Ross 128 (`dM4`) did not appear under the **M** chip in the GUI Star Systems
Search, while white dwarfs (`LAWD 37` = `DQ`, `Wolf 28` = `DZ7.5`) filtered
correctly and had to stay that way. Investigation found the same wrong assumption
in the colour/legend layer (Part 2) and two independent latent bugs along the way.

Both parts were adversarially reviewed before and after implementation; the
review findings and the corrections they forced are recorded inline below, because
several of the *first* numbers in this plan were wrong and the corrected ones are
the load-bearing record.

---

# PART 1 — search chips (`spectral_where`, `substellar`)

carries a lowercase luminosity prefix do not appear under the `M` chip. Reported
examples (verified in `data/space_app.db`):

| star_name (DB) | spectral_type | today |
|---|---|---|
| `Wolf  359` | `dM6` | falls into **Other** |
| `Ross  128` | `dM4` | falls into **Other** |
| `LAWD 37`   | `DQ`   | Other (**correct** — white dwarf) |
| `Wolf   28` | `DZ7.5`| Other (**correct** — white dwarf) |

## 2. Root cause

`core/shared.py:330 spectral_where()` matches a chip letter with a strict
leading-character test:

```python
sub.append(f"{column} LIKE ?"); params.append(f"{letter}%")     # 'M%'
```

`dM6` starts with `d`, so it fails `LIKE 'M%'`. It then also fails the `Other`
branch's `NOT (LIKE 'O%' OR … 'M%')`, so it lands in Other. The rows are not
missing from the app — they are **mis-bucketed**.

### 2.1 The constraint that dictates the design

**SQLite `LIKE` is case-insensitive for ASCII; `GLOB` is case-sensitive.** Any fix
expressed with `LIKE` cannot distinguish the *dwarf* prefix `d` from the
*degenerate* (white dwarf) prefix `D`. The fix must use `GLOB` (or `substr()=`,
which is also case-sensitive on TEXT).

Verified: `spectral_type GLOB 'dM*'` matches 0 rows that are also `GLOB 'D*'`.

### 2.2 What the prefixes mean

- `d` = dwarf (main sequence, ≈ lum. class V); `sd` = subdwarf (VI);
  `esd`/`usd` = extreme/ultra subdwarf (metal-poor halo). Yerkes/Gliese-era notation.
- `k` / `h` / `m` = **Am/Ap chemically-peculiar** notation (Ca II K-line type /
  hydrogen-line type / metallic-line type). NOT luminosity prefixes and NOT a
  binarity marker — SIMBAD confirms these appear on singles and binaries alike
  (`* iot Cen` kA1.5hA3mA3Va → otype `PM*`; `* b Leo` kA1VmA3V → `Pe*`;
  `* 65 UMa` hA5VkA2mA3 → `SB*`; `HD 31925` hF5gF5mF3 → `**`).
  The binarity marker on these records is the **`+`** (`* alf Psc`
  `kA0hA7Sr+kA2hF2mF2(IV)`), not the k/h/m.
- Uppercase `D…` = degenerate / white dwarf. **Must stay in Other.**

### 2.3 Key correction to an earlier assumption

There is **no asymmetry** between `dM6` and `kA5hF0mF2`. Both are handled
correctly by the Python parser and incorrectly by the SQL:

| type | `core.shared._parse_spectral_class` | `spectral_where` |
|---|---|---|
| `dM6` | `('M', 6.0)` ✓ | no match ✗ |
| `sdM3.0` | `('M', 3.0)` ✓ | no match ✗ |
| `kA5hF0mF2` | `('A', 5.0)` ✓ | no match ✗ |
| `DA` / `DZ7.5` / `DQ` | `(None, None)` ✓ | no match ✓ |
| `L0` / `T8` | `(None, None)` ✓ | no match ✓ |
| `M3+` | `('M', 3.0)` ✓ | match ✓ |
| `DA+dM` | `(None, None)` ✓ | no match ✓ |

`_SP_PATTERN = (?<![A-Z])([OBAFGKM])(\d+(?:\.\d+)?)` — the negative lookbehind lets
lowercase `d` through but blocks the `A` in `DA`. So the app's *physics* path
(BC/Teff/HZ/HR/`binary.m1_from_spectral_type`) already classifies these correctly;
**only search is wrong.** The goal is to make the SQL agree with the Python.

Known divergence to document: `_SP_PATTERN` requires a digit, so `dMe` (6 rows) and
`sdK` (4 rows) → `(None, None)` in Python, but `GLOB 'dM*'`/`'sdK*'` will match them.
The SQL is deliberately slightly more inclusive for digit-less types.

## 3. Data census (source of the prefix list)

Distinct text preceding the first uppercase OBAFGKM letter, over
`star_systems` (256,003 rows; 70,930 typed) + `gcns_stars` (332,571 rows; 55,350 typed):

| prefix | rows | disposition |
|---|---|---|
| `''` | 100,864 | already matched |
| `'D'`,`'DZ'`,`'D+d'`,`'DC+'`,`'DQ'`,`'D+'`,`'DC/D'`,`'DZ+'`,`'DZQ'`,`'DC+D'`,`'DCe+'`,`'DQ+'`,`'DC5'`,`'DC'` | ~13,428 | **stay Other** (white dwarfs / WD composites) |
| `'d'` | 4,737 | → strip |
| `'sd'` | 429 | → strip |
| `'k'` | 204 | → strip |
| `'esd'` | 161 | → strip |
| `'usd'` | 68 | → strip |
| `'d/sd'` | 22 | → strip |
| `'sd:'` | 16 | → strip |
| `'h'` | 8 | → strip |
| `'s/sd'` | 2 | → strip |
| `'(sd)'` | 2 | → strip |
| `'kn'` | 1 | → strip |
| `'('` | 4 | left in Other (ambiguous) |

Rows with no uppercase OBAFGKM anywhere (`D`, `DC`, `DC:`, `DZ`, `L0`, `DQ`, `L1`, …)
stay in Other — correct.

## 4. Design (agreed: option (a), GLOB — no schema change)

`_SP_CLASS_PREFIXES = ("", "d", "sd", "esd", "usd", "k", "h", "kn", "d/sd", "sd:", "s/sd", "(sd)")`

For chip letter `X`, emit `(<col> GLOB ?  OR <col> GLOB ? …)` with params
`f"{p}{X}*"` for each prefix `p`. `Other` becomes the **exact complement**
`(<col> IS NULL OR NOT (<the same 7×12 expression>))`, so a star can never appear
under both a letter chip and Other.

None of the prefix strings contain GLOB metacharacters (`*`, `?`, `[`, `]`), so they
are safe to interpolate as *parameters* (keep `?` binding, as today).

Rejected alternative (b): a materialized `spectral_class` column on `star_systems`
populated by the canonical Python parser + `_migrate_schema` backfill. More exact and
indexable, but a schema change + migration, and useless for the live-ADQL
`search_exoplanets`. Logged as a possible future refactor.

### Measured behaviour + perf (`star_systems`, 256k rows)

- chip `M`: 17,685 → **20,392** (+2,707: `dM` 2,394 · `sdM` 194 · `esdM` 75 · `usdM` 28 · misc)
- chip `A`: 1,389 → **1,492** (+103) · chip `F`: 8,182 → **8,190** (+8) — the `kA…`/`hF…` Am/Ap stars
- chip `K`: 10,939 → **10,864** (**−75**) — see 4.1, this is a *net loss*
- chip `B` +4 · `O` +1 · `G` +5

### 4.1 SECOND EXISTING BUG (found in adversarial review — was missed in the first analysis)

`LIKE 'K%'` is case-insensitive, so it **already matches the 107 lowercase `k…` Am/Ap rows**
(`kA5hF0mF2III`, `kA1.5hA3mA3Va`, …). Those are **A/F stars currently mis-filed under chip K**
— a second pre-existing bug, independent of the reported `dM` one.

Switching to case-sensitive `GLOB` evicts them from K no matter what, so chip K
**loses 107 and gains 32 → net −75**. The only real choice is where they land:

| `k`/`h` in prefix list? | `kA5hF0mF2` goes | verdict |
|---|---|---|
| yes (chosen) | chip **A** | correct |
| no | **Other** | still better than K, but wrong |

Including them is right. But this is a **user-visible loss of results from chip K**
and must be called out in the release note — the first draft of this plan recorded
chip K as "+21", wrong in **sign**.
- worst case, all 7 chips (84 GLOB terms): **1.01 s**; `Other` complement: 0.96 s;
  realistic single chip `M` (12 terms): **0.167 s**. No index on `spectral_type`
  today, so this is a full scan either way — no regression.
- invariants verified: `M-chip ∩ Other = 0`; white dwarfs still Other (15,144);
  `L`/`T`/`Y` still Other (**1,168** — the first draft said 1,164).
### 4.0 Per-chip verification — ALL SEVEN chips, all three tables

Every gained/lost row inspected individually (not just aggregate counts):

| chip | star_systems | gcns_stars | hwc | what moves |
|---|---|---|---|---|
| `O` | 6 → 7 (+1) | 4 → 5 (+1) | 0 | `sdOBe` (hot subdwarf — see 4.2) |
| `B` | 150 → 154 (+4) | 134 → 138 (+4) | 10 → 11 (+1) | `sdB`×2, `kB8hB8HeA0VSi`, `kB8hA0III(CrEu)`; hwc `sdBV` |
| `A` | 1,389 → 1,492 (+103) | 1,312 → 1,406 (+94) | 21 | Am/Ap `kA…`, incl. the sole `kn` row `knA2h(eA)VSr((Eu))` |
| `F` | 8,182 → 8,190 (+8) | 8,013 → 8,021 (+8) | 251 | `sdF8`, `sdF2`, `kF0…`, `kF3…` |
| `G` | 13,475 → 13,480 (+5) | 13,195 → 13,200 (+5) | 717 | `sdG0`×2, `sdG2`, `sdG`, `sd:G3` |
| `K` | 10,939 → **10,864 (−75)** | 10,555 → **10,489 (−66)** | 575 | +`esdK7`/`sdK7`/`usdK7`… − 107 `k…` Am rows (see 4.1) |
| `M` | 17,685 → 20,392 (+2,707) | 16,032 → 18,676 (+2,644) | 441 → **440 (−1)** | +`dM*`/`sdM*`/`esdM*`/`usdM*`; −`m4.3`; hwc −`m3 V` |

`sd:G3` is the **only** row in either table that justifies the `sd:` prefix, and
`knA2h(eA)VSr((Eu))` the only one justifying `kn` — both earn their place.
hwc `A`/`F`/`G`/`K` are entirely unchanged (no `k`-prefixed rows in that table).

### 4.0b Partition invariant — PROVEN on real data

```
star_systems   chips= 54579  other=201424  sum=256003 = total   overlap=0
gcns_stars     chips= 51935  other=280636  sum=332571 = total   overlap=0
hwc            chips=  2015  other=  3584  sum=  5599 = total   overlap=0
pairwise chip overlaps (all 21 letter pairs × 3 tables): none
```

Chips ∪ Other = every row exactly once. No star can appear under two chips, and none
can appear under both a chip and Other.

- blanks/NULLs: `star_systems` has 185,073 `''` types; `'' LIKE 'O%'` = 0 and
  `'' GLOB 'dO*'` = 0, so blanks stay in Other under **both** old and new
  expressions. **No behaviour change for blank/NULL** — verified, not an omission.

### 4.1b Am/Ap stars — DECIDED: option (a), first letter (user, 2026-07-27)

Of the 111 `k…`/`h…` Am/Ap rows, **37 have a first letter that disagrees with their
hydrogen-line type** — all A→F (`kA5hF0mF2III`, `kA2.5hF2mF2(IV)`, `kA7hF3mF5(III)`, …).
Astronomically the **h (hydrogen-line) type is the better temperature proxy** for an
Am star (Ca K reads too early because Ca is weak; metals read too late), so
`kA5hF0mF2` is physically an F0 star and this rule files it under **A**.

Options weighed:

| | `kA5hF0mF2` → | pro | con |
|---|---|---|---|
| **(a) first letter — CHOSEN** | chip **A** | matches the rest of the app exactly (`_SP_PATTERN.search` → `A5`, which already drives BC/Teff/HZ/HR/hyper-limit) | 37 stars astronomically mis-classed |
| (b) h-type preference | chip **F** | astronomically correct | search would disagree with regions/HR unless `_SP_PATTERN` changes app-wide — a much larger, separate change |
| (c) drop `k`/`h` from list | **Other** | smallest change | 111 stars left unclassified |

**Rationale for (a):** self-consistency with the existing app is the goal of this
change; (b) is really an app-wide `_SP_PATTERN` change and should be its own commit
with its own test pass. Logged as a possible follow-up, not scheduled.

### 4.2 `sd` + `B`/`O` — semantic overreach, accepted with a note

`sdB`/`sdO` are **hot subdwarfs** (stripped core-He-burning EHB stars), not B/O dwarfs.
The rule sends `sdOBe` to chip `O` and `sdB` to chip `B`. Affected: 3 rows in
`star_systems`, 3 in `gcns_stars`, 1 in `hwc` (`sdBV`). Too few to justify a
special case; documented rather than excluded.

Note: `LIKE 'M%'` currently over-matches by exactly **1** row (a lowercase `m4.3`),
which `GLOB` correctly excludes. Net chip-M delta is therefore +2,707.

## 5. Changes

### Part 1a — `core/shared.py`
1. Add `_SP_CLASS_PREFIXES` next to `_SPECTRAL_CHIP_LETTERS`, with a comment
   explaining the `LIKE`-is-case-insensitive constraint and why `GLOB` is required.
2. Add `spectral_leading_class(sp) -> str | None` — the canonical Python helper
   (strip a known prefix, return the OBAFGKM letter, `None` otherwise). Used by
   Part 2; keeps one definition of "leading class".
3. Rewrite the letter-chip branch of `spectral_where()` to emit GLOB terms.
4. Rewrite the `Other` branch as the exact complement of that expression.
5. `spectral_adql()` — **DECISION CHANGED to: leave it alone.** The first draft
   called this "cosmetic". It is not:
   - `_query_tap` (`core/databases.py:325-346`) sends ADQL as a **`requests.get`
     URL parameter**. 7 letters × 12 prefixes = 84 inline `LIKE` terms, and the
     `Other` complement repeats the whole expression → **~6 KB of query string**.
     IPAC TAP GET-length tolerance is **untested** (no network call made).
   - The first draft justified it with "TAP/**Postgres** LIKE is case-sensitive".
     Wrong attribution — the NASA archive is IPAC's TAP, not Postgres. ADQL `LIKE`
     is case-sensitive per the standard, but that is **unverified here**.
   - NASA `st_spectype` uses modern MK with essentially no `d`-prefixes, so the
     benefit is ~zero against a real GET-length + untested-semantics risk.
   Revisit only with a live probe against IPAC.

### Part 1b — `core/databases.py::compute_substellar_census` (line 3736)
Live bug, worse than the reported one. It builds `spectral_type LIKE ?` from a
caller-supplied prefix, so `--classes D` returns:

```
LIKE 'D%'  →  4,918  =  2,561 real white dwarfs (GLOB 'D*')
                      + 2,357 lowercase-d M dwarfs (GLOB 'd*')
```

Fix: switch to `GLOB` and extend each requested class with the same prefix list.
Also recovers rows the defaults silently miss:
- default `L/T/Y`: 824 found, **18 missed** (`sdL0`, `esdL7`, `sdL`, …)
- `--include-late-m` (`M7/M8/M9`): 2,616 found, **73 missed** (`dM7` ×44, `dM8` ×5,
  `sdM7.0` ×4, `sdM9` ×3, …) — the first draft said 64.

Contract-visible (`--classes D` changes meaning) → `docs/integration.md` note required.

### Callers inheriting the fix (no edits needed)
`core/databases.py:3334` `search_star_systems`, `:3419` `search_hwc`,
`:3484` `search_exoplanets`. The three GUI panels
(`gui/panels/search.py` `StarSystemsSearchPanel` / `HwcSearchPanel` /
`NasaExoplanetSearchPanel`) only render `spectral_type` as a table column and do not
re-derive a class from results — verified.

## 6. Explicitly OUT of scope

- **`oec-search --spectral-type`** (`core/databases.py:1023`,
  `sp.upper().startswith(q)`). Its documented contract *requires* `DA` → white
  dwarfs as a prefix match (`docs/integration.md:281`). It has its own latent bug
  (`.upper()` makes `dM6` → `DM6`, so `--spectral-type D` matches M dwarfs), but
  fixing it changes a published contract. Separate decision.
- **Part 2 — the colour/legend bug.** `sp[:1].upper()` → `dM6` maps to `"D"`, so
  Wolf 359 / Ross 128 render white-dwarf blue and get a bogus `D` legend entry.
  Sites: `core/viz.py` ×5 (incl. `:1706 _sp_color`, `:1757 sp_class`),
  `gui/visualizations/plot_helpers.py` ×6 (1060, 1171, 1321, 1397, 1481, 1587,
  1865, 2083, 2282, 2432 — legend + hover paths), `gui/visualizations/star_map.py:150`,
  `gui/panels/gcns.py:65`, and a second palette `core/calculators.py:1562
  _star_map_color` (route maps). `gcns_stars` holds 2,812 lowercase-prefixed rows,
  so the GCNS panels are affected identically. Separate commit.
- **Parser duplication.** `_SP_PATTERN` is duplicated byte-identically in
  `core/shared.py:29`, `core/regions.py:15`, `main.py:1303`; a fourth, divergent
  parser lives in `core/generate.py:173`
  (`^\s*([OBAFGKMobafgkm])(\d+(?:\.\d+)?)?` — anchored + lowercase-accepting, so
  `dM6` → no match, `m5.5` → M). generate.py only parses the bundled
  main-sequence CSV, so it is not exposed to catalog strings today. Note only.

## 7. GCNS audit result

`gcns_stars.spectral_type` is copied verbatim from `star_systems` by the opt-58
SIMBAD cross-match (`core/databases.py:2325`), so the `dM`/`sdM` strings propagate
in: **2,812** lowercase-prefixed rows of 55,350 typed.

Clean (no spectral predicate — filter on `light_years`/`gaia_source_id`/`wd_prob`,
display `spectral_type` as passthrough): `gcns-within-sol`, `gcns-source`,
`gcns-system`, `gcns-distance`, `gcns-travel-time`, `gcns-stars-within-star`.
`solar-analogs` filters Teff/log g/[Fe/H] off `hypatia_cache` — no spectral predicate.
Affected: **`substellar` only** (Part 1b) + the GUI colour path (Part 2).

## 8. Tests

`tests/test_search.py:24–59` pins the exact SQL fragment and params — it will fail by
construction and must be updated in lockstep (that is the guardrail, not an obstacle).

New/updated cases (DB-backed, using the existing tmp-DB monkeypatch pattern):
- `dM6`, `dM4`, `sdM3.0`, `esdM2.0`, `usdM0.0` → chip `M`
- `sdK7` → chip `K`; `kA5hF0mF2`, `hA5VkA2mA3` → chip `A`
- **regression pins:** `DA`, `DZ7.5`, `DQ`, `DA+DA`, `DA+dM` → `Other`, never `M`/`A`
- `L0`, `T8` → `Other`
- `M3+`, `M5.5Ve` → chip `M` (unchanged)
- invariant: letter-chip result ∩ `Other` result = ∅
- `spectral_adql` prefixed-term shape + refine sanitisation (unchanged behaviour)
- Part 1b: `substellar --classes D` returns only `GLOB 'D*'` rows, no `dM*`

## 9. Docs

- `docs/integration.md:2723–2725` — "OR-ed leading-letter matches" → describe prefix
  handling; add the `substellar --classes` note.
- `docs/integration.md:2809` — says `substellar` "Selects rows whose `spectral_type`
  **begins with** one of `classes`". After the fix `--classes L` returns `sdL0`,
  which does not begin with `L`. Reword. (Missed in the first draft.)
- `docs/star-databases.md` — Phase G "Shared spectral-class control" section.
- `CLAUDE.md` — no change expected (no new module/subcommand).

## 10b. PART 2 DESIGN (written after Part 1 shipped — Part 1 changed its shape)

**Status: designed, NOT reviewed, NOT implemented.** Part 2 has had *site discovery*
(the breadth sweep, §11) but no design review, because until Part 1 landed there was
no design to review — only a list of sites.

### 10b.1 Part 1 set a TRAP for Part 2 — the naive substitution is a regression

The obvious Part 2 move is `sp[:1].upper()` → `spectral_leading_class(sp)`. **That is
wrong.** `spectral_leading_class` is deliberately OBAFGKM-only (correct for chips,
where `D`/`L`/`T` must fall into "Other"), but `core.viz._SPECTRAL_COLORS` is keyed on
**11** letters — `O B A F G K M L T W D`. Verified:

| type | today `[:1].upper()` | naive swap | result |
|---|---|---|---|
| `dM6` | `D` → white-dwarf blue | `M` → orange | fixed |
| `DA` / `DZ7.5` / `DQ` | `D` → `#B0C4DE` | `None` → **grey** | **REGRESSION** |
| `L0` | `L` → `#FF4500` | `None` → **grey** | **REGRESSION** |
| `T8` | `T` → `#CD853F` | `None` → **grey** | **REGRESSION** |
| `WR…` | `W` → `#E040FB` | `None` → **grey** | **REGRESSION** |

Every white dwarf, brown dwarf and Wolf-Rayet star on every star chart would go grey.

### 10b.2 Design: parameterize the letter set (prototyped, verified)

One function, two letter sets — not two functions:

```python
def spectral_leading_class(sp_str, letters=_SPECTRAL_CHIP_LETTERS):
    ...  # unchanged body; `letters` is the only new knob
```

- **search chips** — `letters=_SPECTRAL_CHIP_LETTERS` (default, current behaviour,
  byte-identical → Part 1 stays untouched and its tests keep passing)
- **colour / legend** — `letters=` the palette keys (`O B A F G K M L T W D`)

Prototype verified across all cases: `dM6`→M, `sdM3.0`→M, `kA5hF0mF2`→A, `DA`→D,
`DZ7.5`→D, `DA+dM`→D, `L0`→L, `T8`→T, **`sdL0`→L**, **`esdL7`→L** (both colour
*grey* today, since `s`/`e` aren't palette keys — a bonus fix), `''`→None.

**One accepted regression:** `m4.3` (1 row) colours orange today via `[:1].upper()`
and would become grey. It is already excluded from chip M by Part 1, so grey is at
least *consistent* with search. Note, don't fix.

### 10b.3 Scope

- `core/shared.py` — add the `letters` parameter (+ a palette-letter constant, or the
  caller passes it).
- 14 call sites: `core/viz.py` ×5 (incl. `:1706 _sp_color`, `:1757 sp_class`),
  `gui/visualizations/plot_helpers.py` ×10 legend/hover paths,
  `gui/visualizations/star_map.py:150`, `gui/panels/gcns.py:65`,
  `core/calculators.py:1562 _star_map_color` (a **second, separate palette** — must be
  reconciled or left alone deliberately), `generate_star_map_html.py:38`.
- `tests/test_viz_phase_o.py` — ~12 assertions that pin the WRONG behaviour (§11).

### 10b.4 Open questions for review

1. `core/calculators.py:1562` has its own palette dict with different hex values and
   no `L`/`T`/`W` keys. Unify with `_SPECTRAL_COLORS`, or leave and just fix its
   letter derivation? Unifying changes route-map colours — a visual change beyond
   the stated bug.
2. The O16 legend groups by class letter. After the fix a chart can gain a "Class M"
   entry and lose a spurious "Class D" one. Any GUI code keying off legend *order* or
   *count* rather than label?
3. Does `sp_class` (`core/viz.py:1757`, Night Sky) feed anything other than colour —
   e.g. sorting or filtering — where a `None` would now propagate?

## 11. Part 2 addenda (from the breadth sweep — all verified)

- **A FOURTH parser variant**, previously unlisted: `core/science.py:155`
  `compute_hyper_limit_for_spectral_type` inlines its own
  `(?<![A-Z])([OBAFGKM])(\d+(?:\.\d+)?)?` — note the **trailing `?`** making digits
  optional, so it is *not* a copy of `_SP_PATTERN`. Verified divergence:
  `dMe` → `M` and `sdK` → `K` here, but `None` in `core/shared.py`. It backs the
  Honorverse hyper-limit ring (`core/viz.py:511`, `gui/panels/diagram_tabs.py:194`,
  `gui/panels/catalogs.py:387`) and imports nothing from shared/regions.
  Part 1 does not touch `_SP_PATTERN`, so there is **no drift risk from this change**
  — but any future consolidation must include this file.
- **`generate_star_map_html.py:38`** — root-level script with the same
  `sp[:1].upper()` colour bug (`sdM3.0` → `S` → grey; `kA5hF0mF2` → `K`). Outside
  the `core/`+`gui/` sweep of the first pass.
- **Test fixtures pin the WRONG behaviour.** `tests/test_viz_phase_o.py` uses
  **Wolf 359 / `dM6`** as its fixture with explicit comments `# dM → "D" bucket`
  (lines 490, 620, 723, 830) and asserts a `"Class D"` legend entry that Wolf 359
  inflates (737, 749, 783, 807, 846, 858, 872). ~12 assertions must be rewritten
  when Part 2 lands. This is a real cost the first draft did not budget.

## 10. Risks

1. **`search_hwc` LOSES a row from chip M.** The first draft said `m3 V` "stays
   Other" — wrong. It is in chip **M today** (`'m3 V' LIKE 'M%'` → match, because
   LIKE is case-insensitive) and **moves to Other** under GLOB, since bare lowercase
   `m` is not in the prefix list. `sdBV` moves the other way (Other → chip B).
   Both are behaviour changes; neither was described correctly. hwc M-chip: 441 → 440.
   *Open question:* add bare lowercase letters to the prefix list? Dangerous for `G`
   (`gF5` = giant F5, not G-class) — so it would have to be per-letter. 2 rows
   total; recommend documenting, not fixing.
2. **Chip K loses 75 rows** (see 4.1) — the only chip that shrinks. Needs a release note.
3. `Other` shrinks by **5,443** rows across the two tables (`star_systems` −2,753,
   `gcns_stars` −2,690) — the first draft said ~5,650. Any workflow using Other as
   "everything unusual" sees fewer results. Intended.
3. Worst-case all-chips query goes from ~7 LIKE terms to 84 GLOB terms (0.2 s → 1.0 s).
   Acceptable for a 500-capped interactive search; noted, not optimised.
4. Ultra-rare prefixes (`'('` ×4) remain in Other by design.

---

# PART 2 — colour / legend

## 1. The bug

Every place that colours or groups a star by spectral class derives the letter with a
naive `sp[:1].upper()`. For a type carrying a lowercase luminosity prefix that yields
the **wrong letter**:

| type | `[:1].upper()` | should be | today's effect |
|---|---|---|---|
| `dM6` (Wolf 359) | `D` | `M` | painted **white-dwarf blue**; filed under a bogus "Class D" legend entry |
| `dM4` (Ross 128) | `D` | `M` | same |
| `sdM3.0` | `S` | `M` | not a palette key → **grey** |
| `esdL7` | `E` | `L` | **grey** |
| `kA5hF0mF2` | `K` | `A` | painted as a K star |
| `DA`, `DZ7.5` | `D` | `D` | correct (coincidence) |

Affects `star_systems` (2,893 lowercase-prefixed rows) and `gcns_stars` (2,812), so
both the Star Databases charts and every GCNS panel.

## 2. Part 1 planted a trap — the obvious fix is a regression

The natural move is `sp[:1].upper()` → `core.shared.spectral_leading_class(sp)`.
**That would break more than it fixes.** `spectral_leading_class` is deliberately
**OBAFGKM-only** (correct for search chips, where `D`/`L`/`T` must fall into "Other"),
but `core.viz._SPECTRAL_COLORS` is keyed on **11** letters:
`O B A F G K M L T W D`. Measured:

```
dM6      D->#B0C4DE  =>  M->#FF8D3F   FIXED
DA       D->#B0C4DE  =>  None->grey   *** REGRESSION
DZ7.5    D->#B0C4DE  =>  None->grey   *** REGRESSION
L0       L->#FF4500  =>  None->grey   *** REGRESSION
T8       T->#CD853F  =>  None->grey   *** REGRESSION
WR…      W->#E040FB  =>  None->grey   *** REGRESSION
```

Every white dwarf, brown dwarf and Wolf-Rayet star on every chart would turn grey.

## 3. Design — parameterize the letter set (prototyped)

One function, two letter sets. **Additive**: the default keeps Part 1 byte-identical.

```python
_SP_DISPLAY_LETTERS = ("O","B","A","F","G","K","M","L","T","Y","W","D")  # palette keys + Y

def spectral_leading_class(sp_str, letters=_SPECTRAL_CHIP_LETTERS):
    ...  # body unchanged; `letters` is the only new knob
```

- search chips → `letters=_SPECTRAL_CHIP_LETTERS` (default; unchanged)
- colour / legend → `letters=_SP_DISPLAY_LETTERS`

Prototype verified: `dM6`→M · `sdM3.0`→M · `kA5hF0mF2`→A · `DA`→D · `DZ7.5`→D ·
`DA+dM`→D · `L0`→L · `T8`→T · **`sdL0`→L** · **`esdL7`→L** (grey today — bonus fix) ·
`''`→None.

Why it works without a second function: the loop tries `''` first, and `DA`'s leading
`D` **is** in the display set → returns `D` immediately; `dM6`'s leading `d` is not
(case-sensitive), so it falls through to the `d` prefix → `M`.

**CORRECTED — the draft said "1 row". It is 29, and it includes a class the plan
never mentioned.** Row-weighted census over `star_systems` + `gcns_stars`:

```
rows RECOLOURED by the fix: 5,717      rows that become GREY: 29
  D -> M   4755  (dM*, d/sdM0 …)         D -> GREY  16   dC, dC:, dC-J_CH5  <-- CARBON DWARFS
  S -> M    393  (sdM*)                  C -> GREY   4   C-H, C9,5e
  K -> A    193  (kA…)                   ( -> GREY   4   (F), (G)
  E -> M    147  (esdM*)                 N -> GREY   2   N
  U -> M     56  (usdM*)                 M -> GREY   2   m4.3
  S -> K 34 · S -> L 30 · S -> G 10 …    S -> GREY   1   sd
```

**`dC`/`dC:`/`dC-J_CH5` are carbon dwarfs** (16 rows). Today `[:1].upper()` → `D`
paints them white-dwarf blue (wrong); the proposed set sends them to grey (honest,
but they lose their dot colour *and* their legend filterability). `C`/`N` (6 rows)
are real carbon-star classes that today have their own filterable legend entry and
would collapse into the unfilterable `"?"` bucket.

**→ NEW OPEN QUESTION (Q7):** should the display set also carry the carbon/S-type
classes `C N R S`, with palette entries, so `dC` → `C` rather than grey? That is the
only option that is strictly better than today for those rows. Case-sensitivity makes
it safe (`sdM3.0` still → M; a genuine `S5/2` → S). Cost: 4 new palette colours.

**Open:** should `Y` be added to `_SPECTRAL_COLORS`? It is in the display set above but
has **no palette entry**, so Y dwarfs → grey either way. Either add a colour or drop
`Y` from the set. Recommend adding `"Y": <colour>` (a Y dwarf is a real class, and
`substellar` already censuses L/T/Y).

## 4. Sites (15 — verified by grep, one line each)

**`core/viz.py` (5)**
- `:141`, `:448`, `:470` — inlined `_SPECTRAL_COLORS.get(sp[0].upper() …)` in
  `prepare_star_map` / `prepare_star_map_from_result` / (opt-18 path). Should route
  through the shared helper rather than repeat the expression.
- `:1706 _sp_color()` — the canonical colour helper.
- `:1757 sp_class` — Night Sky. **NOT colour**: it is emitted in the result dict and
  documented at `:1723`. Consumers: `plot_helpers.py:4402` (docstring) and
  `tests/test_viz_phase_o.py:265,414-415`. Verify whether anything *groups* on it.

**`gui/visualizations/plot_helpers.py` (10)** — legend/hover/label paths:
`1060`, `1171` (`cls = (sp[0].upper() if sp else "?")`), `1321`, `1481`
(`s["sp_type"][0].upper()`), `1397`, `1587`, `2083`, `2432`
(`name_cls = {…[:1].upper() or "?"}`), `1865`, `2282`.
Note all use `"?"` as the unknown bucket → map `None` → `"?"` to preserve that.

**Other (2)**
- `gui/visualizations/star_map.py:150` — `cls = s["sp_type"][0].upper() …`
- `gui/panels/gcns.py:65` — `_sp_color` duplicate for GCNS panels.

**Second palette (1) — `core/calculators.py:1562 _star_map_color`.** A *separate* dict
used by route-planning maps, and it **disagrees with `_SPECTRAL_COLORS`**:

> **RESOLVED 2026-07-27 — this palette no longer exists.** Part 2 left it in place
> (additive-only) rather than repaint route maps mid-fix, deferring unification to the
> route-chart refactor. That refactor's Phase 3 **deleted** `_star_map_color`; the one
> palette now lives in `core/shared.py` (`_SPECTRAL_COLORS` + `sp_color`) beside the
> `spectral_leading_class` rule, with `core.viz` re-exporting the historical names.
> The table below is the historical record of the divergence that was closed. See
> `completed_plans/ROUTE_CHART_REFACTOR_PLAN.md` §0b.

| letter | viz `_SPECTRAL_COLORS` | calculators `_star_map_color` |
|---|---|---|
| G | `#FFF4EA` | `#fff4c2` |
| M | `#FF8D3F` | `#ff9d6c` |
| D | `#B0C4DE` | `#dfe6ff` |
| default | `#AAAAAA` | `#cccccc` |
| L / T / W | present | **absent** → brown dwarfs already grey on route maps |

**Root-level script (1)** — `generate_star_map_html.py:38` (`spectral_color`) and `:136`
(hard-coded legend letter tuple `("O","B","A","F","G","K","M","L","T","D")`).

## 4b. ATOMICITY — the 17 sites are COUPLED, not independent (added post-review)

Site count corrected: **17** in-scope (`viz.py` 5 + `plot_helpers.py` 10 +
`star_map.py` 1 + `gcns.py` 1), plus `_star_map_color` and the root script = 19 edit
points. The draft said 15. Every cited line number verified exact.

**A partial conversion silently breaks legend filtering.** The sites agree only by
producing the *same class string*:

- `name_cls` (`1397`, `1587`, `2083`, `2432`) feeds `_attach_highlight_2d/3d`, which
  tests `name_cls.get(name) not in hidden` (`plot_helpers.py:913`, `:981`).
- `hidden` is populated by the legend loops at `1060`/`1171`
  (`hidden.discard(cls) if vis else hidden.add(cls)`, `:1099`).
- `label_groups` (`1834`/`1867`, `2238`/`2284`) is keyed by the class from
  `1865`/`2282` and read by `_apply_labels` using the **legend's** `cls` (`:1089`).

Convert a subset and `dM6` is `"M"` in one map and `"D"` in the other: legend
filtering stops hiding that star's label and stops suppressing its O15 highlight
ring — **no error, no test failure**. → §6b gains a cross-site agreement test.

## 4c. Legend buckets TODAY — more junk classes than the draft admitted

The draft claimed the only artefact was "a bogus Class D entry". Actual buckets from
`sp[0].upper()` across both tables:

```
'(' 6 · 'C' 4 · 'D' 22481 · 'E' 167 · 'H' 8 · 'N' 2 · 'S' 479 · 'U' 68 · 'W' 2 · 'Y' 44
```

So charts today can show filterable **"Class S" (479), "Class E" (167), "Class U"
(68), "Class H" (8), "Class ("(6)** — all grey, all meaningless. The fix removes
these, which is the point, but the draft never quantified them.

Row-weighted, the naive-swap trap in §2 would grey **19,674 rows**
(`D` 17,722 · `L` 1,535 · `T` 413 · `W` 2 · `M` 2), not merely "some letters".

## 5. Legend-order risk — CHECKED, low

`plot_helpers.py:1058-1070` builds `groups` keyed by class letter and iterates
`for cls in sorted(groups)`, storing `all_colls[cls]` / `index_maps[cls]` **by label**,
not by position. Toggle state is looked up by `cls`. So gaining a "Class M" entry and
losing a spurious "Class D" one is safe — nothing indexes the legend positionally.
(Pre-existing quirk, out of scope: `sorted()` is alphabetical `A B D F G K M O`, not
temperature order.)

## 6. Tests — the Part 1 review's lessons applied up front

Part 1's review found the change had **zero** coverage: reverting it left the suite
green. Part 2 must not repeat that. **Every change below needs a test that FAILS when
the change is reverted, and I will prove it by actually reverting.**

### 6a. Fixtures that pin the WRONG behaviour (must be rewritten)

`tests/test_viz_phase_o.py` uses **Wolf 359 / `dM6`** as its fixture with explicit
`# dM → "D" bucket` comments:

- **Legend/bucket assertions — WILL break (derive class from `sp_type`):**
  `737`, `846` (`entries == {"Class A","Class D","Class G","Class K"}`),
  `749`, `858`, `783`, `807`, `872` (`texts.index("Class D")` → `ValueError`),
  `791`, `873` (`_o16_cls == "D"` — these fail only *because* 783/872 raise first
  in the same test; if 783/872 were patched to "Class M" without updating 791/873,
  those would then fail correctly on their own. No silent-pass risk.)

- **`763` — CORRECTED: the plan had this wrong, in the dangerous direction.**
  `test_hit_skips_hidden_class` passes `["dM6","K1V",""]` as sp_types but **never
  reads a legend label** — it locates the target collection purely by x-coordinate
  (`abs(offs[0][0] - 4.0) < 1e-6`) and asserts hide/hit behaviour. It will
  **silently keep passing** after the fix while its comment (`# hide the D-class
  dot`) becomes false. This is precisely the "blesses the bug" case — worse than a
  failure, because nothing surfaces it. It would not fail if the fix were reverted
  either, so by §6's own standard it is not a guard at all.
  **Action:** rewrite it to assert the derived class letter directly (or key the
  hidden collection by class rather than by x), so it actually pins behaviour.
- **Fixture `color` values — will NOT auto-break** (`490-493`, `620-621`, `723-724`,
  `830-831`, `1105` pass a pre-computed `"color": "#dfe6ff"` as *input*). They become
  semantically stale and should be corrected to the M colour so the fixture stops
  documenting the bug.
- `612` is a table-row assertion (`["Wolf 359","GJ 406","dM6","7.860"]`) — unaffected.

### 6b. New tests

1. `spectral_leading_class` with `letters=_SP_DISPLAY_LETTERS`: `dM6`→M, `sdL0`→L,
   `esdL7`→L, `DA`/`DZ7.5`/`DA+dM`→**D**, `L0`→L, `T8`→T, `m4.3`→None.
2. **Regression pin (the Part 1 trap):** assert `DA`/`L0`/`T8` still get their
   *non-grey* palette colour. This is the test that would have caught the naive swap.
3. Default-arg guard: `spectral_leading_class(x)` unchanged for all Part 1 samples →
   Part 1's `test_sql_and_python_rules_agree` must still pass untouched.
4. Colour parity: `_sp_color("dM6") == _SPECTRAL_COLORS["M"]` and
   `_sp_color("DA") == _SPECTRAL_COLORS["D"]`.
5. Legend: a star list containing `dM6` produces a **"Class M"** entry and **no**
   "Class D" unless a real `D…` star is present.
6. If `core/calculators.py:1562` is touched: same pins for `_star_map_color`.

## 6c. Additional required tests (from review)

7. **Cross-site agreement (§4b):** for a `dM6` star, assert the legend `cls`,
   `name_cls`, and `label_groups` key are all `"M"` — catches a partial conversion.
8. **`sp_class` pin (`viz.py:1757`):** `prepare_sky_from_star` with a `dM6` star →
   `sp_class == "M"`. Its only existing assertions are all `"G"`, so it is currently
   revert-green — the exact shape of Part 1's D1 defect.
9. **`_star_map_color`** has no derivation coverage at all today (only an
   empty-string fallback test at `test_viz_phase_o.py:2056`).
10. **Rewrite `test_hit_skips_hidden_class` (`763`)** — see §6a; today it would not
    fail if either the fix *or* its revert were applied.

## 7. Open questions — REVIEWER RECOMMENDATIONS RECORDED

**Q1 (unify the two palettes?) → NO; extend additively.** Unifying repaints every
route-planning map plus opts 17/20/21 (G/M/D/default all differ) for a reason
unrelated to this bug, and invalidates fixture `1105`. Instead add `L`/`T`/`W`/`Y`
keys to `_star_map_color` and fix its letter derivation — those letters fall through
to `#cccccc` today, so **only dots that are already grey change**. Zero existing
colours move; brown dwarfs stop being invisible on route maps. File full unification
as a separate visual-change ticket. *(Needs the user's sign-off — see §9.)*

**Q2 (`Y`) → KEEP in the display set AND add a palette colour.** Dropping `Y` is a
regression: 44 rows lead with `Y` today and already produce a *filterable* "Class Y"
entry; dropping it collapses them into the unfilterable `"?"` bucket. Keeping `Y`
without a colour preserves today exactly (grey but filterable); adding one is
strictly better. Suggested continuation of the M→L→T ramp: `#8B4A32`.
**Resolve BEFORE writing the constant** — the draft's prototype used a 12-letter set
against an 11-key palette, baking the mismatch into the code.

**Q3 (does `sp_class` feed anything?) → NO. Safe to change.** Full sweep: two
docstrings, the hard-coded Sol `"sp_class": "G"`, three tests all expecting `"G"`,
and an unrelated local of the same name in the Honorverse CSV parsers
(`databases.py:2220`, `db.py:624`, `main.py:5295`). `make_sky_canvas` colours from
`s["color"]` and never reads `sp_class`. `prepare_sky_from_star` is **not** exposed
by `query.py`, so it is not a JSON contract.

**Q4 (collapse `viz.py:141/448/470` into `_sp_color`?) → YES.** Three byte-identical
copies of what `_sp_color` already does with the same `#AAAAAA` default; ~3-line
diff. Four un-routed copies is exactly how this bug survived. Bonus: the inline
copies use `sp[0]` with no `.strip()` while `_sp_color` uses `.strip()[:1]` —
routing removes that asymmetry.

**Q5 (`generate_star_map_html.py`) → EXCLUDE.** Standalone root script, not imported
by the app; its `:136` hard-coded legend tuple would need a paired edit for no
app-visible benefit. Add a pointer comment, log as follow-up. (That tuple is already
missing `W` and `Y`.)

**Q6 (other `color` consumers?) → NONE.** `color` is not persisted to the DB and not
in any `query.py` contract; §6a's fixture list is complete.

**Q7 (carbon/S-type classes) → OPEN, needs a decision.** See §3.

## 8. Verified CLEAN by review (do not re-litigate)

- **The `letters=` design is structurally safe, not just empirically.** Widening the
  set can only let an *earlier* prefix qualify; in every containment pair the shorter
  member is earlier (`'' ⊂ all`, `d ⊂ d/sd`, `sd ⊂ sd:`, `k ⊂ kn`) and the joining
  characters are `d s e u k h ( / : n` — **never uppercase**. So DISPLAY can never
  override a CHIP answer. Empirically: 0 disagreements over all 3,827 distinct real
  values; 0 over 20,495 synthetic `p1+p2+char+tail` strings including D/L/T/W/Y/C/R/N/S.
- **Additive claim holds:** default-arg results identical over all 3,827 real values →
  Part 1 stays byte-identical.
- Second-palette table, legend-order analysis (incl. pick/toggle handlers), and the
  §6a fixture sort (apart from `763`) all CONFIRMED.
- `plot_helpers.py:4385` (HR secondary axis) **checked and correctly excluded** — its
  `points` come from `prepare_hr_main_sequence`, whose labels are clean MK strings
  from the bundled CSV, never catalogue types.

## 8b. PALETTE — measured, not eyeballed (supersedes the Q2/Q7 colour guesses)

Ran `dataviz/scripts/validate_palette.js` (OKLab ΔE, CVD sim, contrast) against the
dark star-chart surface. Three findings, in order of importance:

**1. The EXISTING 11-colour palette already fails every check.** Not a regression I
introduce — a property of the palette as shipped:

```
[FAIL] CVD separation      worst adjacent  #FFF4EA(G) ↔ #F8F7FF(F)  ΔE 2.7 deutan
[FAIL] Normal-vision floor worst adjacent  #FFF4EA(G) ↔ #F8F7FF(F)  ΔE 2.7  (floor is 15)
[FAIL] Chroma floor        6 of 11 read as gray
[PASS] Contrast vs surface all 11 ≥ 3:1
```

F and G stars *really are* both near-white. This palette is **physically motivated**
— it approximates true stellar colour — so the validator's standard remedy
("re-step onto passing values") is inapplicable: you cannot recolour a G dwarf
without lying about the physics.

**2. Therefore colour is NOT the identity channel here, and never was.** Identity is
carried by **secondary encoding** that already exists: the O16 per-class legend
(text labels), the hover tooltip, and the click info box showing the full spectral
type. The skill permits sub-floor ΔE *only* with secondary encoding — this chart
qualifies. That is what makes the existing F/G pair tolerable, and it is the same
allowance any addition relies on.

**3. The warm end is saturated — my "add 4 carbon reds" recommendation was WRONG.**
Every candidate carbon red fails the normal-vision floor against T `#CD853F`:

```
#E8563C ↔ #CD853F  ΔE 10.6      #F0603F ↔ #CD853F  ΔE  9.6
#D94F2B ↔ #CD853F  ΔE 11.3   (best)        floor = 15
```
and the physically-realistic dark reds (`#B5341F`, `#9E2B1C`, `#8B4A32`) additionally
fail **contrast < 3:1** against the dark navy chart — nearly invisible dots.

**REVISED decision:**
- **Add the letters `C N R S Y` to the display set** — this is the part that matters.
  It stops `dC` being painted as a white dwarf and gives each its own **filterable,
  text-labelled legend entry**. Verified: adding them changes exactly **6** distinct
  values across all three tables, all `None → C/N`; nothing already resolving to an
  OBAFGKM/DLTWY letter is disturbed.
- **One carbon colour, not four.** `C`, `N`, `R` are the *same modern class* (R and N
  were merged into C), so they share `#D94F2B` — best measured candidate, contrast
  PASS, ΔE 11.3 vs T, legal under secondary encoding.
- **`Y` → `#A9746E`** (contrast PASS). 44 rows, currently grey-but-filterable, so
  this is a strict improvement.
- **`S` → no palette entry** (grey but filterable). 0 rows in every table today;
  revisit if a catalogue rebuild produces any.
- **Record in a code comment** that this palette is physically motivated, fails the
  generic categorical checks by construction, and depends on the legend/hover for
  identity — so no future contributor "fixes" it by re-stepping the hues.

## 9. DECISIONS — APPROVED BY USER 2026-07-27 (with one revision)

1. **Q1 — APPROVED: additive-only.** Add `L`/`T`/`W`/`Y` (+ the new `C`) keys to
   `_star_map_color` and fix its letter derivation. Those letters fall through to
   `#cccccc` today, so **only already-grey dots change** — zero existing colours
   move, no fixture invalidated (incl. `1105`), brown dwarfs stop being invisible on
   route maps and opts 17/20/21. Full unification of the two palettes → separate
   visual-change ticket.
2. **Q2 — APPROVED, colour revised.** `Y` stays in the display set (dropping it
   would collapse 44 filterable rows into the unfilterable `"?"` bucket). Colour
   `#A9746E`, **not** the originally-suggested `#8B4A32`, which the validator failed
   on both chroma floor and contrast (< 3:1 on the dark chart → near-invisible).
3. **Q7 — APPROVED IN PRINCIPLE, scope reduced.** Add `C N R S` to the display set
   (the bucketing/legend fix, which is the real win), but **one shared carbon colour
   `#D94F2B`** for `C`/`N`/`R` rather than four — they are the same modern class, and
   §8b shows four distinguishable warm hues do not exist here. `S` gets no palette
   entry (0 rows).

## 9b. FINAL letter sets and palette deltas

```python
_SPECTRAL_CHIP_LETTERS  = O B A F G K M                      # unchanged (Part 1)
_SP_DISPLAY_LETTERS     = O B A F G K M L T Y W D C N R S    # chips + degenerate/
                                                             # brown/WR/carbon/S
_SPECTRAL_COLORS  += {"Y": "#A9746E", "C": "#D94F2B", "N": "#D94F2B", "R": "#D94F2B"}
_star_map_color   += {"L","T","W","Y","C","N","R"}           # additive only —
                                                             # these are grey today
```

## 10. Superseded open questions

1. **Unify the two palettes, or only fix `_star_map_color`'s letter derivation?**
   Unifying changes route-map colours (G/M/D/default all differ) — a visual change
   beyond the stated bug. Fixing only the derivation leaves two palettes that disagree
   and leaves route maps with no L/T/W. Which is right?
2. **`Y` has no palette entry.** Add a colour, or drop `Y` from the display set?
3. **Does `sp_class` (`core/viz.py:1757`) feed anything that groups/sorts/filters**,
   where `None` (or a changed letter) would propagate beyond colour?
4. **Should the three inlined sites (`viz.py:141/448/470`) be collapsed into
   `_sp_color`?** Reduces four copies to one, but widens the diff.
5. **Is `generate_star_map_html.py` in scope at all?** It is a standalone root script,
   not imported by the app. Its `:136` legend letter tuple is hard-coded and would
   need a matching edit.
6. Any consumer of the emitted `color` value (persisted, compared, or asserted
   elsewhere) that a colour change would break — beyond the fixtures in 6a?

## 8. Out of scope (unchanged from Part 1)

- `oec-search --spectral-type` (`core/databases.py:1023`) — documented contract
  requires `DA` → white dwarfs as a prefix match; its `.upper()` bug is separate.
- The four-way `_SP_PATTERN` duplication (`core/shared.py:29`, `core/regions.py:15`,
  `main.py:1303`, and the digit-optional variant at `core/science.py:155`).
- The Am-star h-type question (Part 1 §4.1b — decided: first letter).

---

# AS-BUILT — deviations found during implementation (2026-07-27)

Everything above is the plan **as reviewed**. Three things changed once the code ran.

## 1. `R` and `S` were REMOVED from the display set — a bug the reviewers missed

The plan (and the user's approval) had `_SP_DISPLAY_LETTERS` carrying the carbon/S
sequence `C N R S`. The existing suite failed immediately on:

```
tests/test_viz_phase_o.py::O10aHyperLimitsPrepTest::test_prep
  AssertionError: '#D94F2B' != '#AAAAAA'   for "Red Giant"
```

**`"Red Giant"` is a row LABEL in the Honorverse hyper-limit table** (`spTypeHyperLM.csv`),
not a spectral type — and `core.viz.prepare_hyper_limits` feeds that column through
the same `_sp_color` helper. With `R` in the set it resolved to carbon class R and
turned red. `"Supergiant"` would likewise have hit `S`.

Both review agents missed this because both validated against catalogue
`spectral_type` values only; the label strings live in a different table. The
existing test suite caught it on the first run.

**Resolution:** `R` and `S` are excluded. Both have **zero rows** in `star_systems`,
`gcns_stars` and `hwc`, so they bought nothing while creating false positives on any
descriptive label starting with those letters. Final set:

```python
_SP_DISPLAY_LETTERS = ("O","B","A","F","G","K","M","L","T","Y","W","D","C","N")
```

Carbon dwarfs (`dC`, `dC:`, `dC-J_CH5` — 16 rows) still resolve via `C`, which was
the point of the carbon addition. Pinned by
`test_search.py::test_non_spectral_labels_do_not_resolve`.

## 2. Palette colours were chosen by measurement, not by eye

Ran the dataviz validator (OKLab ΔE + CVD sim + contrast) rather than picking hexes.
It rejected the originally-proposed values and reshaped the decision — see §8b of
Part 2. Final: `Y #A9746E`, `C`/`N` `#D94F2B` (one shared carbon hue, because four
distinguishable warm hues do not exist beside M/L/T). The originally-suggested
`Y #8B4A32` failed both the chroma floor and 3:1 contrast on the dark chart.

## 3. Test-guard proof (the Part 1 review's D1 lesson, applied)

Every change is guarded by a test that FAILS when the change is reverted, and this
was **verified by actually reverting**, not assumed:

| reverted change | result |
|---|---|
| `compute_substellar_census` GLOB → LIKE | 5 failures in `test_query_phase_t.py` |
| `_SP_DISPLAY_LETTERS` → chip set | 3 failures in `test_search.py` |

`test_hit_skips_hidden_class` was rewritten: it previously located dots by
x-coordinate and never read a legend label, so it passed identically whether `dM6`
bucketed as D or M — it would not have failed on the fix *or* its revert.

## 4. Final scope as shipped

| file | change |
|---|---|
| `core/shared.py` | `_SP_CLASS_PREFIXES`, `_SP_DISPLAY_LETTERS`, `spectral_leading_class(sp, letters=…)`, GLOB rewrite of `spectral_where` |
| `core/databases.py` | `compute_substellar_census` LIKE→GLOB + class-token validation |
| `core/viz.py` | palette `+Y/C/N`, `_sp_color` prefix-aware, 3 inline copies collapsed, `sp_class` fixed |
| `gui/visualizations/plot_helpers.py` | `_display_class` helper + 10 coupled sites |
| `gui/visualizations/star_map.py`, `gui/panels/gcns.py` | 2 sites |
| `core/calculators.py` | `_star_map_color` prefix-aware + additive `L/T/W/Y/C/N` |
| tests | `test_search.py`, `test_query_phase_t.py`, `test_viz_phase_o.py` |
| docs | `docs/star-databases.md`, `docs/integration.md` |

**Deliberately NOT changed:** `spectral_adql` (live NASA TAP — GET-length risk, no
`d`-prefixes in `st_spectype`); `oec-search --spectral-type` (its documented contract
requires `DA` → white dwarfs); the four-way `_SP_PATTERN` duplication
(`core/shared.py:29`, `core/regions.py:15`, `main.py:1303`, and the digit-optional
variant `core/science.py:155`); palette unification (→ `completed_plans/ROUTE_CHART_REFACTOR_PLAN.md`).
