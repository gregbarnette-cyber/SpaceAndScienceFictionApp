# PHASE CR-30: a cited main-sequence reference table for every numeric consumer — S1, its relations, MIST v2.5, the hydrogen-burning limit and placement

**Status:** PLAN — CP0 (plan review) pending; **no code until Greg's go**.
**Contract:** WB `design-lab/star-system-analysis/spaceapp-change-request-CR30-main-sequence-reference-table.md` (APPROVED
FOR FIRE, session 120; scope-locked by Greg's rulings 1–169 and pre-fire rulings 1–32). Where this plan and the contract
differ, the contract wins; the Q&A rulings (MSG 361) supplement it.
**Channel:** MSG 356 (ping), 357 (APP ready), 358 (hand-off), 359 (stand-up), 360 (APP's Q1–Q36 + F1–F7), 361 (WB's
answers; Greg ruled Q9, Q18, Q21, Q23, Q33, Q36; the spec file unchanged).
**Base:** `2c22208`, tree clean. Suite 3913 / 118 / 626.
**WB baseline:** 1070 cases / 1031 distinct runs on `2c22208` (two passes), scored by the kit's field-keyed rules.
**Name map:** `PHASE_CR30_NAME_MAP.json` (repo root, beside this plan; WB's scorer's field-name input — F1's request).

CR-30 is one CR → **one commit**, git-held until WB's re-gate is GREEN and Greg signs FULFILLED. Seven sub-CRs, built in
**six stages** with a `/code-review high` checkpoint after each (§9).

---

## 0. Ground truth (verified at `2c22208` — four evaluation sweeps, MSG 360; drift confirmed by WB, MSG 361)

**The old table and its readers.** `propertiesOfMainSequenceStars.csv` (repo root; 24 rows O5–M8; "810,000" / "61,000"
strings) is read by:
- `core/db.py` `_STATIC_TABLES` L465 → `_seed_main_sequence` L495. TEXT columns; auto-seed fires only on an **empty**
  table (L476–479), so today's `data/space_app.db` holds the old rows indefinitely.
- `core/databases.py` `import_main_sequence_csv` L2140 (DELETE + INSERT; doesn't clear `regions._MAIN_SEQUENCE_DATA`).
- `core/regions.py` `_load_main_sequence_data` L20 (SQL L47) → `_lookup_spectral_type` (ceiling rule; `_SP_PATTERN`
  needs a digit; load errors swallowed → "Could not find spectral type").
- `core/shared.py` L862–889 divergent loader + lookup (clamps; tests only).
- `core/science.py` `compute_main_sequence_table` L11–32 → GUI `MainSequencePanel` (`gui/panels/science_tables.py`
  L220, reads L247–255), `query.py cmd_main_sequence` L2077, `core/generate.py` `_usable_ms_rows` L189–212 (own parse
  L174: letter-only → subtype 0).
- `core/viz.py` `prepare_hr_main_sequence` L1880 (DB direct), lookups L1936 / L1986; `core/par_flux.py` L147;
  `core/generate.py` L1932 (message).
- `main.py` L1118 / L1308 / L1358 / L1625 / L2461 / L5139.

**The legacy luminosity** `2.52 ** (4.85 - M_bol)`: `core/regions.py` L149; `main.py` L1169 / L1689 / L1767 / L5205.
No other runtime hit (`4.85` elsewhere is unrelated: `stellar_wind.py` L28, a cooling value, a comment).

**Gillett's relations** (every runtime site):
- `L^0.2632`: `regions.py` L150, `stellar_mass.py` L193, `main.py` L1170 / L1690 / L1768 / L5206.
- `M^3.5`: `regions.py` L151, `report.py` L1090, `stellar_mass.py` L382, `formation.py` L167, `main.py` L1171 /
  L1691 / L1769 / L5207.
- `M^0.57 / M^0.8`: `regions.py` L153, `report.py` L1089, `databases.py` L4753, `main.py` L1172 / L1692 / L1770 /
  L5208.
- `1e10·M^-2.5`: `regions.py` L156, `report.py` L1091, `stellar_mass.py` L383, `equations.py` L1071, `main.py`
  L1175 / L1695 / L1773 / L5211.
- Uncited consumers: `generate.py` L2124–2131 (real-anchor mass / radius → L2172 / L2197 / L2262);
  `databases.py` L4703 → L4711 (compare-stars L = R²(T/5778)⁴ → HZ L4757–4762) and the second region call at L4724;
  the trust flag `report.py` L1144 / L1179; text labels `report.py` L442, `exclusion_boundary.py` L469,
  `databases.py` L4611 / L4718, `oec_derived.py` L143.
- `stellar_mass.mass_dependent_outputs` L362–386 has no runtime caller (tests only).
- Print sites that crash on None: `sol_regions.py` L94–95 / L98 / L191, `star_regions.py` L263–264 / L267 / L355,
  `main.py` L1042–1043 / L1046.

**The region step** `compute_star_system_regions_from_simbad` (`regions.py` L294–362): rejects types without
OBAFGKM + digit; Teff (L341) → V (L345) → parallax (L349) checks, each returning `{"error"}`; Sol `compute_sol_regions`
L365–389 (V −26.74, BC −0.07, M_V 4.83, Teff 5778). Callers: `star-regions` (query.py L164), `star-regions-manual`
(L171), `exclusion-boundary --star` (L1168 — non-fatal since CR-27.3, the curated mass error L1181–1191 embeds
`reg_reason`), the dossier (`report.py` L1131; Sol L1266), `exclusion_system.py` L1168 (single-body retry), `par_flux`
L165, `generate` L2124, `compare_stars` (`databases.py` L4697 / L4723, errors swallowed), the GUI star-regions panel.

**Class parsing — three readers:** `shared.luminosity_class` L1036 (CR-10.5 guard; `report.py` L1131–1132 / L1142 /
L1183); `detection._LUM_CLASS_RE` L43 → `_host_class` L64 and `exclusion_wall._classify_identity` L380 (direct use L444).
`"M8 INT-G"` reads class I in both (→ HEAD's "evolved"); `"kA2hA5mA7V"` reads A2; `_sp_letter` (detection.py L54)
scans every character (`L5gamma` → G).

**2MASS today:** identifiers only. `Simbad.query_objectids` (`databases.py` L282, inside the lookup's `try`; except
L289–290) → `_designation_ids_from_rows` → `shared._match_designations` L270 (first match wins per key: a second
2MASS id is invisible). **No J / Ks fetch anywhere; no II/246 query.** `_norm_2mass` `databases.py` L2837. Force-failure
hooks: `xray_catalog.py` L13–19 table, checks at the seams (`_hook(...)` L182 / L340 / L464, `databases.py` L668,
`catalog.py` L441, `ism_velocity.py` L549). `catalog.py` L145–147: an empty VizieR result → `"rows": []`.

**The mass ladder:** `stellar_mass.resolve_mass` L69 (manual → catalog → FLAME → inversion; caution L113 / L131);
`resolve_component_mass` L178–232 → `(mass, prov, note)` (CR-14.3 arity), inversion from `spec["luminosity_lsun"]`
L193; `resolve_binary_components` L291 (falls to orbit masses L326 / L345). Dossier `_resolve_star_mass_block`
`report.py` L1054 keeps `cat_row`; `_patch_regions_for_mass` L1089–1096 runs only when `reg_ok` and prov ≠ inversion;
`_attach_mass_block` L1099–1103 only `if "regions" in data`. Sol's dossier `stellarMass` is ≈ 1.022 (not pinned).
`exclusion-system` single body L1148–1183: catalog / FLAME first, the region retry (L1165–1173) only for a
`main_sequence` domain; the error L1177 omits the region reason. `--component` parse `_parse_component_spec` L973
(unknown key → error; `lum=` → `luminosity_lsun`); `_cr26_component` query.py L832.

**The catalog:** `stellar_mass_tables.load_mass_catalog` L79 (dict with `stars` list; `schema_version` unread);
`match_mass` L100 (first row whose `main_id` / `aliases` match; skips a non-finite mass). New fields silently ignored
today. `_SEED_CATALOG` L28 (4 rows, schema 1.0.0). WB's catalog (23 rows, schema 1.1.0, md5 `f8715a50…`) and test
catalog (25 rows, `efa69ebb…`) are clean under §4.2's validation (WB scripted, MSG 361 A24).

**The domain:** identity-only, decided **before** mass. `_component_domain` → `classify_domain_wind` →
`classify_wind` → `_classify_identity` (preset → `_WINDLESS_TAGS` {brown-dwarf, bd, wd, rogue} → WR / AGB → empty →
W / C → `_host_class` wd / bd windless L425–426 → sdO / sdB unmodeled → IV / I–III evolved → main_sequence).
`_classify_off_ms` L1064–1074 (L1072: the BD otype test **and** the L/T/Y letter test) feeds `_is_secondary_component`
L1054–1061 and the class tag (L1158 single body, L1326 companion). `exclusion-boundary` returns before any catalog
load on windless (`--spectral-type` L1050; `--star` L1108). Enum: `exclusion_wall.py` L61–64.

**`binary.py`:** `_MJUP_PER_MSUN` L25, `_STELLAR_MIN_MSUN = 0.075` L26, `_MS_MASS_ANCHORS` L36–45, `_DEFAULT_M1_MSUN`
L46; `classify_companion` L156–171 (`>` L164); SB1 caveat L152 / L996; `_NOTE_M1_UNKNOWN` L346–347; M₁ sites L374 (NSS),
L674 (SB9, `Sp1` fallback), L936 (stability tiers 2–3, identity type only), L1428 (census SB9); bulk NSS census L1257
(1.0 M☉); `binary_masses` fill L403 (L322–329); `multiplicity` `m2_solar_lower` L533–559; `_resolve_binary_identity`
L265 (no otype). `_companion_from_row` raises on a null M₁ (census row dropped).

**`detection-completeness`:** `_host_class` L74–75 (leading L/T/Y → brown_dwarf); `_resolve_star_mr` L170–182;
`_MS_MASS_RADIUS` `detection_tables.py` L133; non-MS branch L280–293; `_resolve_star_mr` call L295; activity bump L128;
query.py L1605–1615 archive injection (MS host: archive mass only; non-MS: both); argparse L3277–3301 (no catalog, no
age). Archive `exoplanet_batch.fetch_archive_stellar_mass` L1017.

**Census:** `compute_substellar_census` `databases.py` L4424; help `query.py` L4088.

**Isolation pattern:** `tests/conftest.py` stubs module-level network seams per marker (`_cr26_network_isolation`,
`_cr24_velocity_isolation`, `_cr27_identity_isolation`) plus the `_cr26_socket_guard`. Vendored data pattern:
`stellar_wind_tables.py` / `ism_velocity_tables.py` `_read_verified` (md5 then DictReader; `SPACE_APP_CR2x_DATA_DIR`
override; curated `Cr2xDataError`; no `#` skip — CR-30 adds it).

**FROZEN:** `compute_exclusion_boundary` is untouched — every CR-30 behaviour is layered in the callers
(`compute_two_layer_boundary`, `exclusion_system`, `query.py`), feeding it a mass as today.

---

## R. WB answers index (MSG 361). Each is folded into the body at the § given.

| Q | Ruling | § |
|---|---|---|
| 1 | one class parse feeds all three readers; CR-10.5 guard otherwise unchanged | 2.2 |
| 2 | generator reads S1 via the verified loader, keeps its letter-only rule (93 L9) and draws; seeds re-baselined | 2.4 |
| 3 | every `main.py` region / relation / lifetime computation delegates to `core/` | 2.4, 3.5, 4.6 |
| 4 | `main-sequence` keys = S1's header + `*_computed`; `bc_key` kept (now the type read) | 2.4 |
| 5 | letter-only O/B/A/M on `--star` → region-step failure with the curated reason | 2.3 |
| 6 | J / Ks from VizieR II/246 by designation (Jmag/e_Jmag/Kmag/e_Kmag/Qflg/Rflg); an id with no II/246 row = failed lookup | 3.2 |
| 7 | a raising `query_objectids` stays the SIMBAD error; an **empty** result → marker only for type letter K / M (letter-only included); no type → no marker | 3.2 |
| 8 | exit 0 + `not_authoritative` + marker; `compare-stars` per star | 3.3 |
| 9 (Greg) | `star-regions` keeps its region-step error exit; the no-V M_Ks mass is the dossier's and the exclusion subcommands' | 4.2 |
| 10 | `mass_provenance` `ms_mks_relation`; patch on an M_Ks mass; no CR-11.2 caution | 4.2 |
| 11 | M_Ks tier inside `resolve_component_mass` at the L route's position → ahead of the orbit fallback; S13 binary disclosure always | 4.2 |
| 12–17 | trust-flag R(M) at the adopted mass; compare-stars L from R(M), null R → null L; additive region reason on the exclusion-system error; generator anchor mass / R(M); the `< 0.8` line stays CR-34's, labels re-pointed to MIST; every print site renders status | 4.3–4.6 |
| 18 (Greg) | **below** a route's domain if below at **either** node; **above** only if above at **both**; inside at one / above at the other → the in-domain node's factor sets the reading, the factor stays null ("outside the table at the <t> Gyr node"), the output names the node; route-unknown per route. 61 Cyg B at 0.03 → "≤ X" (1.127615 at 0.025) | 5.4 |
| 19 | null reasons: distinct, each once, incl. "outside the table at the <t> Gyr node" | 5.4 |
| 20 | no SIMBAD types into `binary.py` (B governs) | 6.2 |
| 21 (Greg) | a `--component otype=` whose first code is pre-MS sets E | 5.5 |
| 22 | a system entry's pre-MS signal reads component A's primary type | 5.5 |
| 23 (Greg) | one call age applies to every component the call resolves | 5.3 |
| 24 | invalid new catalog fields → loud load error naming row + field | 5.2 |
| 25 | `star-regions` no catalog tier; signals = the call's age, the designations **and SIMBAD's primary type** | 5.6 |
| 26 | `compare-stars` places the ladder's `mass_solar` | 5.6 |
| 27 | 5th domain value `undetermined_no_mass`; boundary = main_sequence + `windless_alternative` + `placement` | 6.1 |
| 28 | L0–L5 go down the ladder (no inference route); T/Y/L6+/logL<−4.3 run the ladder (no inference) for the conflict flag, then windless | 6.1 |
| 29–31 | identity routing keeps the L/T/Y letter test; user-asserted BD tags win; an L type has no colour letter | 6.1, 2.2 |
| 32 | designation at all four M₁ sites; call / catalog age at the stability layer; "≤ Y" follows the M₁ that solved Y; a relation-basis catalog M₁ read "≤ X" gives "≤" on M₂; measured / model / FLAME / supplied M₁ none | 6.2 |
| 33 (Greg) | propagate: the dossier's age reaches its multiplicity block; L1317 guard = propagate "≤", never re-inject | 6.2 |
| 34–35 | null-M₁ consequences disclosed; `Sp1` fallback kept; `--ra/--dec` = "no SIMBAD lookup"; census null-M₁ row kept, `unknown` | 6.2 |
| 36 (Greg) | SB2-ratio / equal-mass M₂ under "≤ M₁" → "≤ Y", "undetermined — at most <class(Y)>"; `m2_solar_lower_direction`; detection catalog tier no FLAME, `--star` only | 6.2, 6.3 |
| F1 | the name map (JSON) — incl. detection's catalog-tier `star_mass_provenance` (**`catalog`**) | name map |
| F2 | age flags also on `exclusion-boundary --spectral-type` and `detection-completeness --sp-type` — **confirmed** | 5.3 |
| F3 | `SPACE_APP_2MASS_FORCE_UNREACHABLE` | 3.2 |
| F4 | `twomass_status` **only on a degrade** (`unreachable` / `empty` / `ids_failed`) + `not_authoritative`; more than one id → its own key **`twomass_ids_multiple`** (a list; a disclosure, not a degrade) | 3.2 |
| F5–F7 | storage `data/cr30/` + one verified loader, DB as display mirror; one Utilities import; disclosures on the output / in the docs note | 1, 7 |

---

## 1. CR-30.1 — the data files (Stage 1)

### 1.1 Vendoring
- `data/cr30/`: `cr30_mamajek2022_dwarf_sequence.csv` (`2b7746f6…`), `cr30_mist_v25_ms_lifetime.csv` (`b2125376…`),
  `cr30_bhac15_overread_factor.csv` (`1ce818ca…`) — `cp` from WB's `cr30-data/` (**Greg runs the copy if auto mode
  blocks it**, as on CR-26), md5-checked after copy; S1's raw file
  (`/home/greg/Claude/source-pdfs/mamajek-EEM_dwarf_UBVIJHK_colors_Teff-2022.04.16.txt`, `afa3e0c8…`) beside them;
  `data/cr30/MANIFEST.txt` (the CR-12 pattern: each file, md5, source, role; "nothing parses the raw file at run time").
- `propertiesOfMainSequenceStars.csv` (repo root) stays **unedited** in the repo (re-gate baseline), read by nothing at run
  time.

### 1.2 One verified loader — `core/ms_reference_tables.py` (new; stdlib only)
- `Cr30DataError(Exception)` (curated, exit 1 as CR-24 / CR-26); `SPACE_APP_CR30_DATA_DIR` override.
- `_read_verified(name)`: md5 the bytes before parsing → mismatch / missing → `Cr30DataError`; skip `#` lines; DictReader
  by header name; per-file structure checks (S1: 87 rows, the nine columns, `SpT` unique and in S1 order, every `Msun`
  present and distinct; MIST: 171 rows, `ms_duration_yr == t_end_yr − t_zams_yr` as written, masses strictly
  increasing; factor: 888 rows, routes ⊆ {mks, luminosity, type}, the eleven age nodes) → `Cr30DataError` on any
  failure. An empty cell → `None` for that cell only.
- Cached accessors: `s1_rows()`, `mist_tracks()`, `factor_rows()`; values parsed from the files' strings as floats at
  load (S1 strings kept alongside for display).

### 1.3 The DB mirror (acceptance 2) — *revised at CP0 (T3 / T4 / H1 / L2 / L3)*
- **`main_sequence_stars` is left untouched** (schema, rows, seed) and **read by nothing at run time** — so a pre-CR-30
  table cannot supply a value after CR-30 (acceptance 2), no migration ever writes a user DB, and the `2c22208`
  baseline worktree keeps reading its own table. It is dropped from the auto-seed list and from opt 57's status list
  (a dead table, disclosed); it is never deleted.
- Three **new** display-mirror tables — `ms_reference_s1`, `ms_reference_mist`, `ms_reference_factor` — each with a
  `source_md5` column, created by `_create_schema`; seeded in `_auto_seed` (so the 25 test files that stub `_auto_seed`
  stay unaffected) from the verified loader, only when empty or when the stored md5 ≠ the verified md5 (re-check inside
  `BEGIN IMMEDIATE`); a loader failure there is caught on the existing warning path (`get_conn` never raises
  `Cr30DataError`).
- **No runtime value is read from any DB table.** `regions`, `viz`, the generator and `compute_main_sequence_table`
  (`main-sequence`, the GUI panel) read the loader; the mirrors are display / status only.
- `import_main_sequence_csv` → `import_cr30_reference_tables()`: verifies the three files, re-seeds the three mirrors,
  clears the loader cache. `core.db.get_table_status` lists the three new tables.

### 1.4 GUI (ruling 82, F6)
- `gui/nav.py` Utilities: "Import Main Sequence Star Props" → **"Import CR-30 Reference Tables"** (one option, all
  three); `gui/panels/csv_utility.py` L270–287 panel rewritten to call `import_cr30_reference_tables` and show the three
  md5s + row counts. `DbStatusPanel` (opt 57) lists the two new tables.
- `MainSequencePanel` shows S1's columns + `Mbol (computed)`, `density (computed)`, `MS lifetime (computed, MIST v2.5)`.

### 1.5 Tests (offline; `tests/test_cr30_data.py`, new)
md5 pass / mismatch / missing / `#`-skip / bad-structure → `Cr30DataError`; 87 / 171 / 888 rows; M9.5V `B-V` None; a
pre-CR-30 DB (old `main_sequence_stars` rows) is left untouched and no runtime value is read from it (acceptance 2); a mirror with a
stale `source_md5` is re-seeded; the import loads all three and clears the cache; no runtime module reads
`propertiesOfMainSequenceStars.csv` (a grep test over `core/`, `gui/`, `query.py`, `main.py` — acceptance 3, with
`2.52 **` / `4.85 -` region-formula patterns).

---

## 2. CR-30.2 — reading a spectral type (Stage 1)

### 2.1 One parse — `core/shared.py` `parse_spectral_type(raw) -> SpParse` (shared owns spectral handling)
Returns: `raw`, `read` (the type read, e.g. `M8`, `A5`), `letter`, `subtype` (float), `lum_class_token` (`V`, `IV`,
`III`, `sd`, …, or None), `subdwarf`, `gravity` (`VL-G` / `INT-G` / `FLD-G` / `beta` / `gamma` / `delta` normalised, β →
beta), `youth_from_gravity` (VL-G, INT-G, beta, gamma), `pre_ms_from_gravity` (delta), `am_h_form` (bool).
Order: (1) strip gravity designations (`VL-G`, `INT-G`, `FLD-G`, `β γ δ`, `beta gamma delta`, attached or spaced); (2)
the Am form — an explicit `h<type>` wins; (3) letter + subtype (`L5gamma` → L5); (4) the class token; with the youth
flag set, a `III` / `IV` on M5+ or L is a low-gravity designation → `lum_class_token` None and `low_gravity_class` set
(ruling 133 M5; the flag here is the parse's own gravity flag **or** a caller-passed youth flag — §5.3).

**Every reader in reach switches to it** (Q1): `shared.luminosity_class` (the CR-10.5 guard's rule I–IV → withhold kept),
`detection._LUM_CLASS_RE` users (`_host_class`, `_classify_identity` L444), `detection._sp_letter` (letter from
`parse.letter`; **L / T / Y → no colour letter**, Q31), `binary.m1_from_spectral_type`, `_classify_off_ms`, the census,
`par_flux` L147, `viz` L1936 / L1986, `regions`. Spectral-class SQL (`spectral_where`, GLOB) is untouched.

### 2.2 The S1 lookup — `core/ms_sequence.py` (new, pure) `s1_at(parse) -> S1Read`
- Exact row (`<read>V`) → as published. Otherwise linear interpolation in subtype along S1's ordered rows, across class
  edges (G9.5 between G9V and K0V; K2.25 → fraction 0.25 K2V–K3V); `logL` in log, every other column linearly; a
  placeholder cell → that column None. Output: `s1_rows [a, b]`, `s1_fraction`.
- Letter-only F / G / K → F5V / G5V / K5V, `subtype_unknown`, span note (F 4.8×, G 2.5×, K 5.8×); M / O / B / A → None
  with `subtype_unknown` and the reason; outside O3V–M9.5V (incl. L / T / Y) → None with its reason.
- Every S1-derived output carries `sp_type_read`, `sp_type_raw`, `lum_class_token`, `s1_class_v_flag` (always present on
  an S1 read: S1 is a class-V table; `lum_class_token` says what the star's class is — the flag changes no value),
  `subdwarf_flag`, `gravity_designation`.

### 2.3 Callers
- `exclusion-boundary --spectral-type` (query.py L1044–1060): parse → `classify_wind` on the parse (so `"M8 INT-G"` is
  not evolved) → `s1_at` → mass = S1 `Msun` (ruling 93 L4, disclosed), L = 10^logL; letter-only M/O/B/A → curated error
  "spectral type 'M' has no subtype — S1 needs one (e.g. M4V)"; letter-only K → K5V + `subtype_unknown`.
- Region step `_from_simbad`: parse instead of `_SP_PATTERN`; a letter-only O / B / A → region-step failure with the
  curated reason (Q5); a letter-only **M** → the colour route where V − J is in span, else the same failure; a
  letter-only **K** → the colour route where in span, else K5V with `subtype_unknown` (ruling 21 — never a failure);
  `bc_key` = the type read.

### 2.4 Tables and other readers
- `compute_main_sequence_table` → S1's 87 rows, keys = S1's header + `Mbol_computed` (Mv + BCv), `density_computed`
  (from M, R, in g cm⁻³ and ρ☉), `ms_lifetime_gyr_computed` (§4.4) — `query.py main-sequence`, the GUI panel.
- `viz.prepare_hr_main_sequence` reads the loader (not the DB).
- Generator: `_usable_ms_rows` from S1 rows via the loader; its own letter-only rule and draw kept (93 L9, Q2); seeded
  tests re-baselined (deliberate change, listed).
- `main.py`: the lookup / loader / import / display options delegate to the `core/` functions (Q3).

### 2.5 Tests (`tests/test_cr30_parse.py`, new)
CR-30.2 acceptance 1–6 offline: G9.5V (BC −0.1775, logL −0.30, 0.89), K2.25V (0.81, −0.46, −0.28875), B8.5V (105.925),
`K` / `M`, `kA2hA5mA7V` → A5, `A0mA1Va` → A0, `"M8 INT-G"` / `"L3beta"` / `"M8.5 VL-G"` / `"M8 III VL-G"`, M8.5V / M9V /
O5V / O9.5V / B0V resolve; `_sp_letter("L3beta")` None; the CR-10.5 guard on `"M8 INT-G"` → not withheld; every reader
uses the one parse (a grep test: no `_LUM_CLASS_RE` / `_SP_PATTERN` left).

---

## 3. CR-30.3 — the region luminosity, Sol and the colour route (Stage 2)

### 3.1 The formula
`regions.compute_star_system_regions` L149: `bcLuminosity = 10 ** (-0.4 * (M_bol - 4.74))`, `M_BOL_SUN_S1 = 4.74` named
as the vendored table's property; region divisors unchanged. `star-regions-manual` runs the same function (ruling 10).
Sol: `compute_sol_regions` takes V☉ −26.76, M_V☉ 4.81, BC −0.07 → 1.0000 L☉; `temp = 5778.0` disclosed; **mass pinned
1.000** (dossier Sol path too).

### 3.2 2MASS — `core/twomass.py` (new; all network through module-level seams for conftest)
- `twomass_ids(main_id, ident_rows)`: from the **raw** `query_objectids` rows (not the collapsed designations dict),
  the identifiers under the acronym `2MASS` (`2MASS J…`; not `2MASSI` / `2MASSW`). Needs the rows: `compute_simbad_lookup`
  keeps them on an internal key (`_ident_ids`, stripped from JSON output) so no second query is made.
- Status (Q7, F4): `query_objectids` raising → today's SIMBAD error (unchanged); returning empty / None for a star with
  type letter K or M (letter-only included) → degrade `twomass_status: "ids_failed"` + `not_authoritative`; no type, or
  another letter → no marker, no route. Exactly one id → fetch; none → no route (subtype / L route, disclosed "no 2MASS
  identifier in SIMBAD"); more than one → no route, `twomass_ids_multiple: [ids]` (disclosure, not degrade).
- `fetch_jks(designation)`: VizieR **II/246** by `_2MASS` designation → `j, e_j, ks, e_ks, ph_qual (Qflg), rd_flg
  (Rflg)`; retries as `catalog.py`'s VizieR calls. Empty rows → `twomass_status: "empty"`; exception after retries →
  `"unreachable"`; `SPACE_APP_2MASS_FORCE_UNREACHABLE=1` → `"unreachable"` at the seam (F3). Fetched once per lookup and
  shared by the colour route and the M_Ks route.

### 3.3 The colour route (`ms_sequence.colour_route_luminosity`)
Gate: letter K / M (letter-only included), no class token I–IV (giants → subtype route + class flag; a flagged late-M /
L III/IV read as low gravity is a dwarf here), V − J ∈ [2.53, 6.98]. L = mean of the BC_V and BC_K paths (Mann 2015
Table 3 base rows, the contract's coefficients), M_bol at zero point 4.755 (×1.014 disclosed); no [Fe/H]. Output:
`lum_route` (`colour` / `subtype`), `lum_colour_lsun`, `lum_subtype_lsun`, `lum_colour_paths {bc_v, bc_k}`,
`v_minus_j`, `twomass {…}` (quality < A flagged per band with its error), `lum_route_disagreement` (max/min > 1.40),
`subdwarf_flag`. The region L **is** the colour route's where it applies; the subtype route's L reported beside it.
A failed lookup → `not_authoritative` + `twomass_status`, the region L null, **never the subtype L** (exit 0, Q8).
- The route lives inside `compute_star_system_regions_from_simbad`, so every caller takes it (Q8). Callers that swallowed
  errors surface the marker: `compare_stars` per star (L4697 / L4723); the dossier / both exclusion subcommands copy
  `not_authoritative` + `twomass_status` to the top level.

### 3.4 Tests (`tests/test_cr30_luminosity.py`, new; `twomass` seam stubbed by conftest unless marked `cr30_twomass`)
`sol-regions` 1.0000; Proxima two paths 0.0015246 / 0.0016195 → 0.001572, subtype 0.001274, ratio 1.234, no flag (fixture
inputs); HD 4628 out of span; VB 10 upper gate → 0.0006032; Aldebaran → subtype route + class flag; Ross 145 / G 208-45
flag, BD-11 3759 doesn't (ratio fixtures at 6.009 / 1.469 / 1.338); `star-regions-manual` Lacaille inputs → 0.03646;
forced failure → marker on `star-regions` and `exclusion-boundary`; `ids_failed` on an empty identifier query for a K/M
star, none for a no-type star; `twomass_ids_multiple` on two ids (Lalande) → subtype route, no `twomass_status`;
`2MASSI` ignored (DENIS J1048 one id).

---

## 4. CR-30.4 + 30.5 — the relations and the MIST lifetime (Stage 3)

### 4.1 Relations (`core/ms_sequence.py`)
- `mass_from_luminosity(L)`: S12 Table 4 inverted from log L −1.066 to 5.37775 with the midpoint switches (0.72 →
  −0.790308, 1.05 → 0.108209, 2.40 → 1.628616; lower segment below, higher at / above), the 7 M☉ gap → 7.0; S1's
  sequence (log M linear in log L) below the switch and above 31 M☉; log L < −3.57 → None with the reason. Returns
  `{mass, relation, segment, switch_band}`.
- `luminosity_from_mass(M)`: S12 forward 0.615–31 by S12's ranges with inclusive upper edges; S1 (log L linear in log M)
  below 0.615 and above 31; None outside 0.078–59 with the reason.
- `radius_from_mass(M)`: S1's (Msun, R) pairs sorted by Msun, log R linear in log M; None outside 0.078–59.
- `mks_mass(m_ks)`: S13 n = 5 (a₀…a₅ verbatim, zero point 7.5) inside [4.5, 10.5] inclusive, else None (never clipped).

### 4.2 The M_Ks tier (ruling 52, 164; Q9–Q11)
- One function `stellar_mass.mks_route(sl_or_spec, plx)` → `{mass, m_ks, twomass…, status}` for type letter K / M with
  one 2MASS id and a parallax; reuses §3.2's fetch.
- **Region path:** `regions.compute_star_system_regions_from_simbad` sets `stellarMass` from the M_Ks route where it
  resolves (else the L route), with `mass_route`, `mass_mks_solar`, `mass_lroute_solar`, `m_ks`; everything fed by
  `stellarMass` (sysilGrav, sysol, planetaryYear, R(M), L(M), lifetime) follows it.
- **Component resolver:** `resolve_component_mass` gains the M_Ks tier at the inversion position (manual → catalog →
  FLAME → **M_Ks → L route**), ahead of `resolve_binary_components`' orbit fallback (Q11). Arity `(mass, prov, note)`
  kept; a new `detail_out` dict kwarg (like `status_out`) carries route, basis, interval, the catalog row, M_Ks, the L
  route's mass, twomass status — the placement input (§5).
- **Region-step failure doesn't stop it** (F1): the region step returns its error **and** the M_Ks inputs it gathered
  (designations, parallax); the mass chain runs the M_Ks route regardless. `exclusion-boundary --star` (query.py
  L1157–1191) and `exclusion_system` single body (L1148–1183 — now runs the M_Ks route for a main_sequence-or-placed
  domain even when the region step fails) and the dossier (§4.5). `star-regions` keeps its error exit (Q9, Greg).
- Provenance `ms_mks_relation` (Q10): triggers `_patch_regions_for_mass`; no CR-11.2 caution; every M_Ks output carries
  S13's unresolved-binary disclosure and, where CR-26's class is `active` / an activity otype / `--activity active`, the
  ≈ 2 % activity caveat.
- The `exclusion-system` single-body mass error gains the region step's reason (additive, Q14).

### 4.3 Every relation site (record §14.4 + the uncited ones)
`regions.py` L150–156 (+ L165 / L178 / L188 consumers), `report.py` L1089–1091 (`_patch_regions_for_mass`) and the trust
flag L1144 / L1179 (R(M) at the adopted mass, Q12), `stellar_mass.py` L193 / L382–383, `databases.py` L4703–4711 /
L4724 / L4753 (compare-stars L from R(M), null R → null L with reason, Q13; the M_Ks tier on both region calls),
`formation.py` L167, `generate.py` L2124–2131 (Q15), the CR-11.2 caution text L131 / `report.py` L442 rewritten (O–B
tail, 84th pct 1.165), labels `exclusion_boundary.py` L469, `databases.py` L4611 / L4718. Sol pins 1.000 M☉.
**Null handling (M5):** a null mass nulls every derived field; every print site renders the status text — the GUI
`sol_regions.py` L94–95 / L191, `star_regions.py` L263–264 / L355, `main.py` L1042–1043 (Q17).

### 4.4 The MIST lifetime (`ms_sequence.ms_lifetime(M)`)
log t linear in log M between tracks (the 1.15 → 1.16 reversal kept); 0.10–300 M☉; > 300 → None + status; each value
names its end point (`first_Xc_lt_1e-4` / `first_Xc_lt_1e-2`; 0.60–0.65 interpolated "from a 10⁻² track to a 10⁻⁴
track"); non-rotating set named in the note. The per-status treatment (below 0.10 "≥ t(0.10)", boundary "if stellar,
≥ t(M_hi)", substellar null, "≥ t(X)", pre-MS) is §5.7 — Stage 3 ships the plain value and the `< 0.10` / `> 300`
handling; Stage 4 wires placement into it.
Sites: `regions.py` L156, `report.py` L1091 / L394, `stellar_mass.py` L383, `equations.py` L1071
(`compute_stellar_evolution` t_MS; stage fractions and `< 0.8` line CR-34's), GUI computed lifetime, the four "≥" print
sites (`report.py` L394, `main.py` L1046, `sol_regions.py` L98, `star_regions.py` L267). `ms_end_gyr` consumers checked:
generator `_ms_end_gyr` L1012–1018 (age clamp, seeds re-baselined), `oec_derived.py` L143 label → MIST + L226–253
Hubble qualifier keyed off the MIST value, `comparison.py` L480–498 "> 13.8 Gyr" keyed off the MIST value (Q16), `viz.py`
L1566.

### 4.5 The dossier on a failed region step (F4)
`report.py`: the mass block attaches even without a regions section — `data["mass"]` (the resolved mass, its placement,
#26) with `data["regions"] = {"error": <step reason>, ...nulls}`; `_attach_mass_block` no longer requires `regions`.

### 4.6 `main.py`
Every region / relation / lifetime computation (L1169–1175, L1689–1695, L1767–1773, L5185–5211) delegates to `core/`
(`compute_star_system_regions`, `compute_sol_regions`, `ms_sequence.*`); the "≥" print site L1046 renders the status.

### 4.7 Tests (`tests/test_cr30_relations.py`, `tests/test_cr30_lifetime.py`, new)
CR-30.4 acceptance 1–9 and CR-30.5 1–4 as hand anchors + in-process calls with stubbed SIMBAD / 2MASS (G 113-20 0.4389,
HD 219134 0.8042, 61 Cyg B 0.6224 / 39.29 AU, LEHPM 3396 exit 1, the three no-V stars, HD 239960B exit 1, Lalande
0.3975 / 32.84, DENIS J1048 0.0804 / 17.33, forced Ks failure → marker never the L route; MIST 8.894 / 4.092 / 1.064 /
440.86 / 50.31 / 2.304 Myr / null at 301; Procyon 2.473 + Subgiant Branch; print sites with None).

---

## 5. CR-30.6 — the hydrogen-burning limit and placement (Stage 4)

### 5.1 `core/placement.py` (new, pure)
- `HBL_MSUN = 0.075` (inclusive; the one constant — `binary._STELLAR_MIN_MSUN` imports it), `BAND_LO = 0.067`,
  `MARGIN = 0.080`, `PRE_MS_SPLIT = 0.625504`, `CUT_NODES` (the eleven six-decimal values, held 0.625–0.8, 0.080 from
  0.8), `NO_AGE_CUT = 0.309062`.
- `MassReading(lo, hi, x, basis, kind, route)` — inference zero-width; supplied zero-width no margin; FLAME / archive
  zero-width with margin.
- `place(reading, signals) -> Placement`: band (stellar needs lo ≥ 0.075; substellar iff hi < 0.067) and margin (X >
  0.080 for margin-taking rows), the youth cut on lo (stellar iff lo > cut) for youth-rule rows, the override (T / Y,
  L > L5, log L < −4.3 → substellar; conflict flag on a stellar mass with any trigger), E (pre-MS; E governs D), and the
  reading (§5.4). Returns the §F fields (the name map's `placement` object).

### 5.2 The catalog fields (C; Q24)
`stellar_mass_tables`: `load_mass_catalog` validates `mass_basis` ∈ the six, `mass_interval {lo ≤ hi, kind ∈ three}`
with lo ≤ X ≤ hi, `age_interval {lo_gyr ≤ hi_gyr or a null bound, basis ∈ four, grade ∈ {member, candidate}}` →
`MassCatalogError` (curated, exit 1) naming the row and field. Absent fields: basis → `relation` + "basis unknown";
interval → `mass ± mass_uncertainty_solar` else zero-width; age → none. `_SEED_CATALOG`: Sirius A / α Cen A / α Cen B
`dynamical`, Vega `interferometric`, `sigma_1` intervals from `mass_uncertainty_solar`, no age. `match_mass` returns the
row (the matched row now reaches placement through `detail_out`).

### 5.3 The age input (ruling 141; F2; Q23)
Flags `--age-lo-gyr` (omitted = no lower bound), `--age-hi-gyr` (giving an age requires it), `--age-basis
{membership,lithium,gravity_class,model_fit}` (required with an age) on: `exclusion-boundary` (`--star` and
`--spectral-type`), `exclusion-system` (`--star`; and per component keys `age_lo=`, `age_hi=`, `age_basis=` added to
`_parse_component_spec`'s known keys), `dossier`, `star-regions`, `detection-completeness` (`--star` and `--sp-type`),
`binary-stability-auto`; `compare-stars` repeatable `--star-age NAME LO HI BASIS` (`LO` may be `none`; NAME matches a
`--stars` entry, Sol included). Validation: lo ≤ hi, finite, ≥ 0 → curated error. One call age applies to every
component the call resolves (Q23).

### 5.4 The youth rule, the factor and the reading (D; Q18–Q19)
- Flag triggers: call age (hi ≤ 1), catalog age (hi ≤ 1, grade member / candidate), gravity designation. Not: hi > 1 or
  no hi, activity, rotation, `--activity young`, FLAME's age.
- Sizing age: a flagging age with lo whose basis ≠ model_fit; smallest t_lo of the call's and the catalog's; the output
  names the source. No sizing age → cut 0.309062, reading at t_lo 0.01.
- `overread_factor(route, x, t_lo)`: from `factor_rows()`; at each bracketing node linear in log X between the two rows
  bracketing X; linear in t_lo between nodes; held 0.625–0.8; none from 0.8. Null with the reasons (distinct, once; incl.
  "outside the table at the <t> Gyr node").
- **Domain per node (Greg, Q18):** below the route's domain if X is below the domain at either node read; above only if
  above at both; inside at one / above at the other → the in-domain node's factor sets the reading (≥ 1.01 "≤ X", (0.99,
  1.01) "no measurable over-read", ≤ 0.99 "under-reads"), the factor reported null with "outside the table at the <t>
  Gyr node", the output names `reading_node_gyr`. Route-unknown: per route, same rules; "≤ X" iff ≥ 1 route has a factor
  (or an in-domain node factor) and every such ≥ 1.01, or X below every route's domain, or placed boundary below 0.8;
  plain X above every route's domain.
- The boundary clause: placed boundary below t_lo 0.8 → "≤ X". From 0.8: X with the caveat (incl. boundary rows).
- Every inferred mass of a flagged star carries the youth caveat worded with the age; X ÷ factor reported.

### 5.5 Pre-MS (E; Q21–Q22)
Signals: SIMBAD primary `otype` ∈ {`Y*O`, `Y*?`, `TT*`, `TT?`, `Or*`, `Ae*`, `Ae?`} (component A's on a system entry,
Q22), a `--component otype=` whose first code is one of them (Q21), δ, a flagging non-model-fit age with t_lo < 0.01.
X ≤ 0.625504 → status boundary + `pre_ms`, boundary's treatment; X > 0.625504 → "stellar, pre-main-sequence", no bound;
only on youth-rule rows; measured / model / supplied keep their placement with the pre-MS status, #26 "pre-MS — not on
the main sequence".

### 5.6 Where placement is attached
`exclusion-boundary` (top-level `placement`), `exclusion-system` (`components[].placement`), `dossier`
(`mass.placement`), `compare-stars` (per star, on `mass_solar`, Q26), `star-regions` (on the region-path mass; signals
= age, designations, SIMBAD primary type — Q25; no catalog tier), `detection-completeness` (`star_placement`),
`binary-stability-auto` / `binary-orbit` / `multiplicity` (§6.2). Directions on derived values: r_ex, L(M), R(M) "upper
bound" fields, lifetime "≥". A boundary catalog row: `r_ex_interval_au [lo, hi]`.

### 5.7 The lifetime by status (CR-30.5 range rules)
`ms_sequence.lifetime_for_placement(placement)` → `{ms_lifetime_*, direction, status, note}` used at every lifetime
site: stellar < 0.10 → ≥ t(0.10) 3.3049e12 yr; boundary → null + "if stellar, ≥ t(M_hi)" (M_hi = max(0.10, X if "≤ X"
else hi)) + the MIST 0.10 → 0.15 step disclosure; substellar → null; "≤ X" stellar → "≥ t(X)"; pre-MS per E.

### 5.8 Tests (`tests/test_cr30_placement.py`, `tests/test_cr30_age_input.py`, new)
CR-30.6 acceptance 1–12 (T1–T25 driven from the test catalog fixture copied into `tests/fixtures/cr30/` with its md5
checked; every factor / cut anchor; Greg's Q18 cases incl. 61 Cyg B at 0.03 → "≤ X" via 1.127615; the age flags on all
seven subcommands' argument paths; catalog validation errors; the seed's bases).

---

## 6. CR-30.7 — placement's consumers (Stage 5)

### 6.1 The exclusion domain (A; Q27–Q31)
- `exclusion_wall.UNDETERMINED_NO_MASS = "undetermined_no_mass"` (5th value).
- Identity classification: `_host_class` / `_classify_identity` send to windless only T / Y / L > L5 (the parse) and a
  white dwarf; L0–L5 → main_sequence-for-now (domain decided after mass). User-asserted `class=brown-dwarf|bd` and
  `--object brown-dwarf` keep windless (Q30). `_classify_off_ms`: the BD **otype** test no longer sets the domain tag;
  the L/T/Y letter test stays for `_is_secondary_component`'s routing (Q29); test L251 re-pinned.
- **Order (Q28):** `exclusion-boundary --star` / `--spectral-type` and `exclusion-system` run the mass ladder before
  the windless return for every type: L0–L5 → ladder (catalog → FLAME → supplied; no inference route) → placed, or
  `undetermined_no_mass` (standoff null, exit 0); T / Y / L6+ / log L < −4.3 → ladder without inference (for the
  conflict flag) → windless free harbor.
- By status: stellar → main-sequence standoff (L type: no wall unless `--wind-state`); substellar → windless; boundary →
  domain main_sequence, operative standoff from X, the CR-26 wall, `windless_alternative`, catalog `r_ex_interval_au`;
  "≤ X" / pre-MS → standoff with `r_ex_direction`.
- Reach of "≤ X": single body (L1173), binary fallback (L1317 — propagate "≤", never re-inject), `exclusion-boundary
  --star`. The FROZEN generator is called with the placed X as today.

### 6.2 `core/binary.py` (B; Q20, Q32–Q36)
- `classify_companion`: ≥ 0.075 stellar; [0.067, 0.075) "boundary — star or brown dwarf uncertain"; SB1 minimum < 0.075
  → "undetermined (minimum mass)", ≥ 0.075 stellar + "true M₂ ≥ this". `tests/test_binary.py` L86 re-pinned.
- `m1_from_spectral_type` → S1 via the parse (`_MS_MASS_ANCHORS` and `_DEFAULT_M1_MSUN` retired on the four sites; the
  bulk NSS census keeps its disclosed 1.0 L1257); `Sp1` fallback kept (Q35); null M₁ with the reason-specific caveat
  (no type in SIMBAD = CR-27's `_NOTE_M1_UNKNOWN` byte-identical; letter-only; unreadable; outside S1's span; no SIMBAD
  lookup — `--source-id` / `--ra --dec`); class `unknown` unless Gaia `binary_masses` M₂ fills. `_companion_from_row`:
  null M₁ → row kept, `unknown` + caveat (counted under `unknown`, Q35).
- Flagged primary: the gravity designation at all four sites; the call / catalog age at the `binary-stability-auto`
  layer and the dossier's multiplicity block (Q33) after selection; M₁ "≤" → M₂ "≤ Y": true mass "undetermined — at
  most <class(Y)>" (substellar iff Y < 0.067); SB1 minimum "undetermined (minimum mass)" whatever Y, caveat withheld;
  SB2-ratio / equal-mass M₂ → "≤ Y", "undetermined — at most <class(Y)>" (Q36); unbounded pre-MS primary →
  "undetermined — pre-MS primary"; M₁ without "≤" → Y plain. A catalog M₁ via CR-14.3's chain: relation-basis read "≤
  X" → "≤" on M₂; measured / model / FLAME / supplied → none (Q32). `multiplicity` `m2_solar_lower_direction` (Q36).
  No SIMBAD types into `binary.py` (Q20).
- `binary-stability-auto` null M₁ → the no-masses result (`elements` null, no radii, no verdict), disclosed; the same
  consequence on `exclusion-system --star` (single-body fall-through) and the dossier stability block, disclosed (Q34).

### 6.3 `detection-completeness` (C)
- `_resolve_star_mr`: S1 mass / radius at the subtype (`_MS_MASS_RADIUS` retired); an MS host's archive radius first
  (query.py L1605–1615 injects it now); a mass without radius → R(M).
- `--star-mass-catalog` (default = the internal seed); tiers manual → catalog → archive (no FLAME), catalog matched on
  `--star` only; `star_mass_provenance` `catalog`; catalog mass beside archive planet parameters disclosed; a non-MS host
  takes a catalog mass only with a radius tier, else skips with "catalog mass not applied".
- Archive mass placed relation-basis ("basis unknown — archive `st_mass`"), margin + youth rule.
- The explicit branch: no tier mass and L0–L5, or an inference placed boundary (band / margin, youth cut, pre-MS split),
  or a null radius → exit 0, methods `applicable: false`, `host_class` null, note naming the status and the two flags,
  `star_mass_solar` the placed reading, `star_mass_provenance` its tier, `star_radius_solar` null + reason,
  `assumptions.out_of_domain` true.
- `--activity` jitter only (L128).

### 6.4 The census (D)
`compute_substellar_census`: label "an L/T/Y census by spectral type"; the note states ruling 78's rule; each row
`placement_status_by_type` ∈ {`substellar`, `undetermined_by_type`} by the parse (L > L5 / T / Y → substellar; else
undetermined); no youth or pre-MS read. `query.py` L4088 help + `docs/query-commands-index.md` re-labelled.

### 6.5 Tests (`tests/test_cr30_consumers.py`, new; `tests/test_binary.py`, `tests/test_exclusion_system.py`, detection tests re-pinned)
CR-30.7 acceptance 1–6 with stubbed SB9 / NSS / archive fixtures (HIP 76901 0.044186, i Cen 0.078188, alf Tri 0.075331,
LP 120-4 0.070400, HD 37737 18.7, 29 CMa 28, lam Lib 5.4, a Car 7.3, HD 198812 / BD-01 1701 / the source-id null M₁,
the L0 17.18 AU, L2 `undetermined_no_mass`, LHS 288 0.156, the explicit-branch cases, the census rows).

---

## 7. Disclosures and docs (Stage 6)
- On the output: per-run disclosures in each result's `notes` (the existing lists) beside the value they qualify.
- Every-run disclosures: the subcommand notes in `docs/integration.md` (a new **CR-30 block**: data files + md5s, the
  parse, the luminosity routes, the relations, MIST, placement, the age input, the hooks, the markers, every new key)
  and a static `cr30_disclosures` key on the outputs that read S1 / MIST / the factor.
- `docs/testing.md` (new files + suite history), `CLAUDE.md` (suite count; a guardrail line: "S1 / MIST / factor are
  WB-owned, md5-checked, never edited; `core/ms_sequence.py` is the one relations module; `placement.HBL_MSUN` the one
  limit"), `docs/core-modules.md`, `docs/query-commands-index.md`, `docs/calculators.md` / `docs/star-system-regions.md`
  / `docs/science-and-scifi.md` (opt 12 / opt 54 relabel), `docs/gui-architecture.md` (the import panel).

## 8. Deliberate changes (the build report lists each with its test)
1. Every non-FLAME `--star` region luminosity and everything it feeds (S1 BC + 4.74; colour route for K/M dwarfs).
2. `sol-regions` 1.086741 → 1.0000; the dossier Sol mass pinned 1.000.
3. Every inversion mass (S12 / S1 / M_Ks), L(M), R(M), the trust flag, compare-stars' R-derived L and HZ, the
   generator's real anchor and seeded draws.
4. Every lifetime / `ms_end_gyr` / `stellar-evolution` stage (MIST); Procyon A → Subgiant Branch.
5. New resolutions: M8.5V+, O5V/O9.5V/B0V, letter-only K, gravity-designated types, no-V K/M stars on the M_Ks route.
6. Placement fields on every placed output; the 5th domain value; L0–L5 no longer the free harbor; boundary's windless
   alternative.
7. `binary.py`: S1 M₁ everywhere; the classifier edge and band; null M₁ instead of 1.0; directions under a flagged M₁.
8. `detection-completeness`: S1 radii; the catalog tier; the explicit branch.
9. The census status per row and its label.
10. `main-sequence` keys and rows; the GUI import option; three new DB mirror tables (`main_sequence_stars` untouched, unread — §13.1).
11. The fixtures `cr24_a0_baseline.json` / `cr31_no_wind_speed_baseline.json` entries resting on `spectral_type_table`
    masses re-baselined (CR-30.2), with the strip step for the new additive keys (the CR-27 `_cr24strip.py` pattern).
12. Order: the mass ladder runs before the windless / L0–L5 domain decision (one extra catalog / FLAME step for those
    types).

**Byte-identical (asserted by test where offline, and in the §10 live pre-check):** Sol 47.5 / wall 6.0
(`--object sun`); the `brown-dwarf` / `rogue-planet` presets; `--mass-msun 0.3 --alpha 0.4` 29.345540401952064; α Cen A
48.966852301574924 / B 45.72136239364217 (composed), Sirius A 63.45901120705829, ε Eri 43.68623962821011, BL Cet
20.509168118090486, Proxima 20.482354346604538 and their walls — **values identical, keys additive only**; `simbad-lookup`
on every card (the `_ident_ids` internal key never emitted).

## 9. `/code-review` checkpoints (`/code-review high` on the working tree; findings triaged and folded before the next stage)

| CP | After | Focus |
|---|---|---|
| **CP0** | this plan | 3 independent plan-review agents: contract coverage (every CR-30.1–30.7 acceptance item and MSG 361 ruling mapped to a § and a test); code correctness / ordering / byte-identity / FROZEN; tests, isolation, memory safety |
| **CP1** | Stage 1 (§1–§2) | the md5 gate and loud failures; no runtime DB read and the mirrors' md5 re-seed on a real old DB copy; the one parse on every reader; interpolation rules; no runtime old-file read |
| **CP2** | Stage 2 (§3) | the formula and Sol; the 2MASS seam, statuses and hook; the colour-route gate; marker propagation through every caller incl. the swallowing ones |
| **CP3** | Stage 3 (§4) | S12 switches / gap / no clamp; M_Ks gate and placement in both chains; region-failure decoupling; every Gillett site gone (grep); MIST interpolation; null handling at every print site |
| **CP4** | Stage 4 (§5) | the placement rule against T1–T25; the factor's node rules (Greg's Q18); sizing ages; pre-MS; catalog validation; the age flags on all seven subcommands |
| **CP5** | Stage 5 (§6) | domain ordering and the 5th value; byte-identity of the catalog / FLAME standoffs; binary classifier / null M₁ / directions; detection branch; census |
| **CP6** | the whole diff, before the build report | cross-section review, the full default suite, the §10 live pre-check |

## 10. Live pre-check (APP, before the build report; one heavy job at a time; `SPACE_APP_CATALOG_CACHE=0 --gaia-timeout 120 --star-mass-catalog <WB cat>`)
- Every CR-30.1–30.7 acceptance call named in the contract, live, on the build (incl. the three forced-failure paths
  with `SPACE_APP_2MASS_FORCE_UNREACHABLE=1`, the age input on each of the seven subcommands, `detection-completeness
  --star-mass-catalog`).
- The byte-identical list (§8) against a `git worktree add` baseline at `2c22208` (`SPACE_APP_DB` = separate copies of the
  pre-CR-30 snapshot for each run, never the main file — §13.1); baseline sweep, build sweep and
  the full suite strictly one after another.
- The GUI import once (offscreen smoke: the panel imports all three tables; Greg confirms in the real GUI).

## 11. Risks and accepted caveats
- **Size.** The largest CR to date (~25 code sites, 4 new modules, an age input on 7 subcommands). Six stages / six
  checkpoints; each stage's tests red-first.
- **Network.** One new VizieR II/246 call per K / M `--star` with one 2MASS id (shared by both routes); bounded by the
  existing VizieR retry; throttling surfaces as the marker, never a silent value.
- **The suite's memory.** New tests are pure / stubbed; no heavy data; the default run stays socket-free (conftest
  stubs `twomass` seams; `cr30_twomass` marker for seam tests).
- **The DB** gains three mirror tables on first connect (seeded data only); `main_sequence_stars` is never written.
  `data/space_app.db` is snapshotted before Stage 1 regardless (§14 T3).
- **Live catalog drift.** Anchors rest on SIMBAD / 2MASS / Gaia / SB9 / the archive at the review; a moved value is
  checked against a fresh read first.
- **Hand anchors** (relation grid values, cut nodes, the split edge, factor-table reads) are unit tests only.

## 12. Build sequence (after the CP0 fold and Greg's go)
1. Stage 1 (§1 + §2) with tests red first → **CP1**.
2. Stage 2 (§3) → **CP2**.
3. Stage 3 (§4) → **CP3**.
4. Stage 4 (§5) → **CP4**.
5. Stage 5 (§6) → **CP5**.
6. Docs (§7), **CP6**, the full default suite, the §10 live pre-check, the name map re-checked against the built
   outputs, then the build report on the channel (fingerprint `git diff 2c22208 | md5sum` + `write-tree`), git-held.
7. WB re-gate → Greg's FULFILLED → one commit (CR-30 only; this plan and the name map excluded, moved to
   `completed_plans/` in a close-out docs commit) → push → SHA to the channel.

## 13. CP0 amendments (2026-10-15) — these govern over §1–§12 where they differ

Three independent plan-review agents (A: contract coverage; B: code correctness, ordering, byte-identity; C: tests,
isolation, safety). Every finding is folded here, or in the body where noted. **Items marked ⟶WB are in MSG 362's
round-2 questions; they stay open until WB rules.**

### 13.1 Data, DB and process
- **T3 / H1: the DB.** See revised §1.3: no migration; new mirror tables; `main_sequence_stars` untouched.
  **Before Stage 1:** `cp data/space_app.db` → `data/space_app.pre-cr30.db` (a snapshot; never edited). §10: the baseline
  worktree runs with `SPACE_APP_DB=<the snapshot copy>`, the build sweep with `SPACE_APP_DB=<a second copy>`; the main
  file is never pointed at. `test_viz_phase_o.py` `O2PanelWiringSmokeTest` (L430–455) moves to a tmp-seeded DB.
- **T4: tests that rewrite the schema.** `test_regions.py` L37, `test_viz_phase_o.py` L320, `test_gould.py` L67 and
  `test_sol_result_row.py` L174 are rewritten to the loader / the new mirror. Plus a test that `get_conn` works with
  `data/cr30` missing.
- **T10: git tracking.** `.gitignore` gains `!data/cr30/`. `.gitattributes` gains `data/cr30/* -text` and
  `tests/fixtures/cr30/* -text`. A test asserts that the vendored files are tracked (`git ls-files`, skipped outside a
  checkout).
- **L1:** the old CSV lives at the repo root, so the acceptance-3 grep matches `propertiesOfMainSequenceStars`
  anywhere. (Body fixed.)
- **C15:** the `core/shared.py` L862–889 loader and lookup are **deleted** (tests-only today; `test_shared` P7.1 is
  re-pointed). A grep test checks that no runtime module runs `FROM main_sequence_stars`.
- **T11:** the full default suite runs **before every CP**, one heavy job at a time; pass / skip / subtest counts are
  recorded per stage in the build log.

### 13.2 2MASS identifiers, isolation and the marker
- **T2 / M1: identifiers out-of-band.** `compute_simbad_lookup`'s dict is **unchanged**, so the CR-27 whole-dict fixture
  and every serialiser stay byte-identical. The raw `2MASS J…` strings are taken from `_designation_ids_from_rows(ids_result)`
  before `_match_designations` collapses them (`databases.py` L282 / L407–409). They are stored in a per-thread memo
  that the twomass seam reads: `databases.simbad_twomass_ids(main_id)` → `list[str]`, `[]`, or the sentinel
  `NOT_LOOKED_UP`. This is the `simbad_lookup_ex` pattern, so never call it through `_bounded_call` / `run_in_thread`.
  A missing memo means "not looked up": no route and no marker. That is distinct from an empty query (`ids_failed`).
  A test checks that no `query.py` output carries a `_`-prefixed key.
- **T1: the conftest default.** `_cr30_twomass_isolation` (autouse; the CR-24 / CR-27 pattern):
  - For tests not marked `cr30_twomass`, the high-level `twomass.resolve(...)` returns "not run", meaning no ids, no
    status and no marker, so the subtype / L route runs as at HEAD.
  - The VizieR and memo seams underneath are leak stubs.
  - `cr30_twomass` is registered in `pytest.ini`, and `test_cr30_` is added to `_cr26_socket_guard`'s prefixes.
  - `delenv` runs for `SPACE_APP_2MASS_FORCE_UNREACHABLE` and `SPACE_APP_CR30_DATA_DIR`.
  - Callers tolerate an empty `detail_out` (for mocks using `return_value=`).
- **M2: once per star.** A per-process memo keyed by 2MASS designation (and its status) covers both region calls in
  `compare-stars`, the exclusion-system retry and the dossier. The dossier's fetch is gated on regions or the mass
  being requested, so `--sections identity` stays network-free.
- **L6:** the 2MASS fetch and the parallax capture happen **before** the region step's Teff → V → parallax early
  returns. The failed step's result carries `mks_inputs {twomass_ids, plx_mas}`.
- **C11:** `ids_failed`, `empty` and `unreachable` behave the same way. The region L is null, the L-route mass is null,
  and there is no subtype or L fallback; `not_authoritative` + `twomass_status` are set. Tested for each status.
- **C1 / M3: marker carriers.** `query._resolve_star_teff_lum` (L1243–1259, behind `circumbinary-hz --star1/--star2`
  and `dyson-collector --star`), `par-flux --star` (L165) and `generate-system`'s real anchor (L2124) are added to §0
  and §3.3. Shape: on a 2MASS degrade, exit 0 with `not_authoritative` + `twomass_status` on the result (top level;
  per star on `circumbinary-hz`). The result is never the generic "Could not derive…", which stays for the non-2MASS
  causes. There is one forced-failure test per caller, and each is added to the name map's `twomass_markers.where`.

### 13.3 The M_Ks tier
- **H2: `resolve_mass`.** It gains `mks_mass=` (`ms_mks_relation`, no CR-11.2 caution) at the inversion position,
  ahead of `inversion_mass`. `resolve_component_mass` delegates to it. The dossier (`_resolve_star_mass_block`) and
  `compare-stars` (L4724–4735) pass the region step's `mass_mks_solar`, or, when the region step failed, an M_Ks mass
  computed from its `mks_inputs` (L6). The region-path L-route mass stays the `inversion_mass`.
- **H3: the spec keys.** `spec["twomass_ids"]`, `spec["plx_mas"]` and `spec["sp_type"]` are the M_Ks inputs. They are
  widened on every caller that has a SIMBAD identity: `exclusion_system` L1163 / L1315 / L1333 / L1485, and
  `stellar_mass` L324 / L343. `--component` specs carry none, so they get no tier. The `_resolve_component_mass`
  delegate (`exclusion_system` L959–964) forwards `detail_out`. CR-26's `xray_catalog._partner_mass_seam` (L174) is
  **⟶WB Q37** (APP proposes: no M_Ks tier there; the CR-26 wind-partner path stays byte-identical, disclosed).
- **C3: the M_Ks mass beside a higher tier.** For a K / M star with exactly one 2MASS id and a parallax,
  `mass_mks_solar` is computed and reported **beside** a catalog or FLAME win, as Wolf 359's 0.1103 is, but it is not
  adopted (CR-30.4 acc 6). It is a test in §4.7.

### 13.4 Parse and identity
- **H4: split `_classify_off_ms`.** `_is_secondary_component` gets a pure routing predicate (the WD / BD otype tests and
  the L/T/Y letter, unchanged; Q29). The class tag never auto-assigns `brown-dwarf` from an L0–L5 letter or a BD
  otype, so only an explicit `--component class=` / `--object` reaches `_WINDLESS_TAGS` (Q30). The auto tag for
  T / Y / L > L5 is the placement override, not the tag. `test_exclusion_system.py` L250–251 is re-pinned.
- **M4: a prefix rule table** in §2.1:
  - `D…` → degenerate (WD).
  - `sd` / `esd` / `usd` → subdwarf, letter after.
  - `d` → dwarf prefix stripped.
  - `K7-M0` → the first type.
  - `IV-V` → the first token (`IV`).
  - `:` and `+…` dropped.
  - lower-case Am prefixes `k`/`h`/`m` read by the Am rule.
  - `e` / `n` / `p` / `var` suffixes ignored.

  **CP1 gate:** old vs new readers (letter, subtype, class token, `_host_class`, `_sp_letter` colour,
  `luminosity_class`) are run over every distinct `sp_type` in `star_systems` (read-only, on the snapshot DB) plus the
  anchors. Every diff is listed as deliberate (a contract rule) or fixed.
- **M4 / T9: the Am h-type versus CR-26 `stellar_wind.parse_sp`.** This is **⟶WB Q38**. `_sp_letter` is in CR-30's
  one-parse reach and feeds the CR-25 colour, RV jitter and CR-26 H7's `cr25_letter`. `parse_sp` (CR-26's letter
  source; `kA5hF0mF2` → A by design, NOTE H7) is not on the contract's list. APP proposes keeping `parse_sp` unchanged
  and letting `_sp_letter` take the h-type. That moves an Am star's CR-25 colour and RV jitter (A → F), and the H7
  check then sees `cr25_letter` F against `parse_sp` A. APP would pin both and disclose the split. `test_cr26_wiring`
  L176 / L505 and `test_cr26_model` L126 are re-pinned or kept accordingly.
- **M5: the binary gates.** `_secondary_needs_primary_sp` (L785), the L815 primary check and `_m1_decodes` (L356–358)
  are redefined as "the S1 read yields an M₁" (that is, `s1_at(parse).Msun is not None`). The CR-16 Sirius B battery
  and the CR-27 zero-flux binary tests are pinned byte-identical.
- **T8: the CR-25 oracle.** `test_cr25.py` `Cr25ByteIdentityOracleTest` inlines frozen pre-CR-30 copies of
  `_host_class`, `_sp_letter` and `_LUM_CLASS_RE`, and adds a CR-30 intended-drift clause: L0–L5, the gravity types,
  the Am h-type, and L/T/Y with no colour letter.

### 13.5 Placement, domain and consumers
- **M8: the reorder's scope.** The mass-ladder-before-windless reorder applies **only** to an L / T / Y leading type or a
  BD otype. WD, sdO / sdB, the presets and `--object` stay byte-identical and keep their early return. On
  `--spectral-type` there is no identity, so `--spectral-type L3` → `undetermined_no_mass` (no standoff, exit 0) and
  `--spectral-type T7` → windless as today, with the override reported. `--mass-msun` precedence is unchanged.
- **C6: supplied-mass placement.** `exclusion-boundary --mass-msun` gets `placement` (supplied, band only): 0.3 →
  stellar, with the standoff and wall byte-identical and additive keys only. 0.07 → boundary: the operative standoff
  is unchanged and the `windless_alternative` is added. `--object` presets are not placed. There is a test at 0.07, and
  the name map gains `--mass-msun` under `placement_carriers`.
- **M7: the 5th domain value.** Every domain-branch site gets an `undetermined_no_mass` case (null standoff, no wall,
  exit 0, `domain_note`): `compute_two_layer_boundary` / `resolve_wind_inputs` (`exclusion_boundary` L334–417,
  `exclusion_wall` L550), the composer and every `WINDLESS` / `UNMODELED` comparison site. That's about 20, listed in
  the CP5 build log, with one test per site class.
- **C7: ages on `exclusion-system --component`.** The call flags `--age-*` are valid with `--component` and apply to
  every component (Q23). A component's `age_lo=` / `age_hi=` / `age_basis=` keys **replace** the call age for that
  component (**⟶WB Q39** to confirm). Both forms are tested.
- **C8:** under E, X < 0.067 → substellar (78 (i) / (iii) on top) before the boundary split. Tested.
- **C9:** `r_ex_direction` is `upper_bound` iff `reading == le_x`, and null otherwise ("stellar, pre-main-sequence" and
  a flagged inference read without "≤" included). Tested on TW Hya and on G 44-42 `[0.005, 5]`.
- **C10: the youth-rule rows**, enumerated in §5.1. Inferences, relation-basis rows and archive masses take the youth
  rule. Model, model-age-inconsistent, FLAME, dynamical / interferometric / asteroseismic and supplied rows never do
  (T22 is the trap).
- **C20:** a missing designation never clears the flag (one line in §2.1 / §5.4).
- **C4: `detection-completeness` directions.** When the host mass reads "≤ X", each method's limit gains
  `limit_direction: "upper_bound"`, and the result carries `star_radius_bound_note` ("a flagged host's radius carries
  no bound"). Tested on TRAPPIST-1 `[0.3, 1]`.
- **C14:** the binary-orbit identity block carries `lum_class_token` / `s1_class_v_flag`, tested on HD 37737 and 29 CMa.
- **C16:** the bulk Gaia-NSS census rows gain `m1_assumed_note` (the 1.0 M☉ assumption), which is new.
- **C26:** `sb1_caveat_withheld: true` is set where "true M₂ ≥ this" is withheld.
- **M6: an explicit null-M₁ branch** before each `companion_mass_*` `try` (NSS L379–395, SB9 L683–697,
  `_companion_from_row` L1216–1232), mirroring `_m1_unknown_companion`: class `unknown` plus the reason caveat. Never
  a swallowed `ValueError`. §0 is corrected: today the census row is kept with `companion: None` and counted `unknown`
  (L1615).
- **M9: composed α Cen.** An offline fixture test at CP5 covers the composed α Cen A / B standoffs through the
  S1-M₁ selection and `recompute_sma_kepler3`. If the last ulps drift, APP takes it to WB before the live pre-check.
- **L4: the dossier mass block** takes one path on both branches, `data["regions"]["mass"]`. On a failed region step
  that is `regions = {"error": <reason>, "mass": {...}}`, with every other region key absent. `_regions_data` /
  `_hz_data` / `_trust_flag` are null-guarded.
- **L5: byte-identity scoped.** The §8 list covers the **standoff and wall values** under WB's 23-row catalog
  (`f8715a50…`). `luminosity_lsun` (`regions_bc`) moves with the region L by design. When the colour route fails on a
  catalog / FLAME-mass star, the luminosity takes the marker. FLAME L never stands in (it would be the silent switch
  the contract forbids). Additive keys and CR-30 notes appear on byte-identical paths only where CR-30 information
  applies.

### 13.6 Disclosures, name map and tests
- **C5: the disclosure inventory.** §7 gains a table. Every contract disclosure is mapped either to an output note (with
  its subcommand and condition) or to docs only. The table is built at Stage 6 and checked at CP6. The name map gains
  `cr30_disclosures` and the per-note conditions.
- **C12 / C13 / C25: the name map.** Dot paths per carrier, with the complete carrier lists (`par-flux
  --spectral-type`, `compare-stars stars[]`, `circumbinary-hz`, `dyson-collector`, `generate-system`, the binary
  identity). New keys: `luminosity_from_mass_relation`, `radius_from_mass_relation`, separate
  `luminosity_from_mass_null_reason` / `radius_from_mass_null_reason`, and the `main-sequence` row keys. The explicit
  branch's L0–L5 note reads "undetermined — no mass". (Updated in the JSON with this fold.)
- **T5:** `_queryharness.save/restore_main_sequence_cache` → `save/restore_cr30_cache`.
- **T6: the fixtures.** `_cr24strip.py` gains `CR30_KEYS`, applied at every depth (components and `zones[].components[]`),
  plus a CR-30 note-prefix filter. The 7 + 3 `spectral_type_table` cases get expected values re-derived from the FROZEN
  generator at S1's mass / L, and every non-mass-derived key is asserted unchanged. `_LUM_PROVS` is extended only if a
  new value appears.
- **T7: the re-pin work list.** §8a (below) lists file → stage → reason; each file is flipped red-first in its stage.
- **T12:** an offscreen Qt test of the new import panel (tmp DB, three md5s + row counts, and `get_table_status`
  listing the new tables). It constructs few panels.
- **T13:** subprocess tests never run a live K / M `--star`. Marker paths use `make_env(SPACE_APP_2MASS_FORCE_UNREACHABLE=1)`.
  Network anchors go in `test_cr30_live.py`, gated on `_netcheck.live_enabled()`.
- **T14 / C22: the live pre-check** is scripted as one sequential runner (per-call timeouts, stored outputs, scope and
  duration recorded in the build report; about 1–2 h). WB re-runs the 171-star benchmark (30.3 acc 5) and the S1
  cell-by-cell diff (30.1 acc 1). APP doesn't.
- **C17 / C18 / C19 / C21 / C23 / C24:**
  - The named anchors are listed in each stage's tests.
  - The 30.5 acc 2 / 4 and 30.6 acc 1 / 9 / 10 tests move to Stage 4 / 5.
  - `stellar-evolution`'s 0.1–20 guard stays unchanged.
  - The SIMBAD otype is disclosed on `_classify_off_ms`, with the L94–95 no-standoff return cited.
  - `_ident_ids` is moot (13.2).
  - `circumbinary-hz` / `dyson-collector` are added to §8.

### 8a. The re-pin work list (T7; ~35 files, ~110–160 methods; each flipped red-first in its stage)
| Stage | Files |
|---|---|
| 1 | `test_regions`, `test_shared` (P7.1), `test_sol_result_row`, `test_viz_phase_o`, `test_query_expanded` (24 → 87 rows), `test_generate`, `test_query_generate`, `test_feasibility`, `test_projects`, `test_shared_luminosity_class`, `test_cr25` (oracle T8), `test_cr26_wiring` / `test_cr26_model` (per Q38) |
| 2 | `test_report` (Sol), `test_query_exposure_additions`, region-luminosity pins in `test_cr23` / `test_cr27_exclusion` |
| 3 | `test_stellar_mass`, `test_formation`, `test_comparison`, `test_oec_derived`, `test_cr23`, `test_cr25` (`_rex`), `test_cr27_exclusion`, `test_exclusion_system`, `test_query_exclusion_system`, `test_query_stellar_mass_live` (Sirius > 2.3) |
| 4 | the fixtures (T6), the catalog tests |
| 5 | `test_binary`, `test_cr20`, `test_binary_stability_auto`, `test_multiplicity`, `test_detection`, `test_query_detection`, `test_cr22` (L3 windless → ladder), `test_cr25` (L5 list), `test_exclusion_system` (L250–251), `test_query_phase_t` (census) |

## 14. Review record
**CP0, 2026-10-15:** three independent agents. **Findings:** 26 from A, 19 from B, 15 from C. **Fold status:** all
folded in §13 or the body. Q37–Q39 are open with WB (MSG 362).

The HIGH findings:

| ID | Finding | Fold |
|---|---|---|
| A-C1 / B-M3 | 2MASS marker lost on `circumbinary-hz` / `dyson-collector` / `par-flux` / `generate-system` | 13.2 |
| A-C2 | letter-only K read as a failure | §2.3 (body) |
| A-C3 | Wolf 359's M_Ks mass beside the catalog row | 13.3 |
| A-C4 | detection limit directions | 13.5 |
| A-C5 | no disclosure inventory | 13.6 |
| B-H1 / C-T3 | DB migration breaks the baseline and writes the real DB in pytest | §1.3 (body), 13.1 |
| B-H2 | the M_Ks tier missing from `resolve_mass` (dossier, compare-stars) | 13.3 |
| B-H3 | `resolve_component_mass` has no M_Ks inputs; six callers; CR-26 partner seam | 13.3, Q37 |
| B-H4 | the auto class tag keeps L0–L5 windless | 13.4 |
| C-T1 | 2MASS default for unmarked tests | 13.2 |
| C-T2 | `_ident_ids` breaks the CR-27 whole-dict fixture | 13.2 |

## 15. Build log (Greg's go 2026-10-15 — MSG 363 relayed, confirmed in-session "proceed"; MSG 364 "build started")

### Stage 1 — CR-30.1 + 30.2 (data, loader, the one parse, S1's lookup, every reader switched)
- **Snapshot:** `data/space_app.pre-cr30.db` (byte copy of `data/space_app.db`, 272,814,080 B; never edited). Vendored
  `data/cr30/` (three CSVs + S1's raw file + `MANIFEST.txt`); md5s match the contract. `.gitignore` `!data/cr30/`,
  `.gitattributes` `data/cr30/* -text`, `tests/fixtures/cr30/* -text`.
- **New:** `core/ms_reference_tables.py` (md5 → `#` skip → header-checked DictReader → structural checks →
  `Cr30DataError`; `SPACE_APP_CR30_DATA_DIR`), `core/ms_sequence.py` (`s1_at` — exact / interpolated in subtype across
  class edges, logL in log, never into a placeholder, letter-only F/G/K at F5V/G5V/K5V, `L_lsun`; `ms_lifetime`;
  `s1_display_rows`), `core/shared.parse_spectral_type` (`SpParse`; gravity strip → Am h-type → prefix + letter +
  subtype → class token; low-gravity III/IV on M5+/L when youth-flagged; legacy fallback for composites).
- **Readers switched:** `regions` (the region step, `_lookup_s1`, `_s1_fields`), `query.py` `--spectral-type` (S1 Msun /
  L; curated letter-only error), `par_flux`, `viz` (HR from S1), `science.compute_main_sequence_table` (S1 + computed
  columns), the generator (`_usable_ms_rows` on S1; own letter-only rule kept), `detection._sp_letter` / `_host_class`,
  `exclusion_wall._classify_identity` (giant class via the parse), `shared.luminosity_class` (via the parse),
  `main.py` (region / Sol / manual / semi-manual computations delegate to `core.regions`; the old loader / lookup
  deleted; table + import options), GUI (opt 12 panel S1 columns; opt 54 "Import CR-30 Reference Tables"; opt 57 lists
  the three mirrors). `shared._lookup_spectral_type` / `_load_main_sequence_data` deleted; `shared._parse_spectral_class`
  is a thin view of the parse. DB: three mirror tables + `seed_cr30_mirrors` (md5-stamped, `BEGIN IMMEDIATE`);
  `main_sequence_stars` left untouched, dropped from auto-seed and status; `databases.import_cr30_reference_tables`.
- **CP1 census gate (§13.4 M4)** over all 3,620 distinct `sp_type` values (136,503 rows) in `star_systems` +
  `gcns_stars` (snapshot DB, read-only): `_host_class` 0 diffs, `luminosity_class` 0 diffs; parse (letter, subtype) 84
  distinct / 167 rows — **all Am h-type strings** (ruling 19); `_sp_letter` 119 distinct / 254 rows — the Am h-types
  (the old scan read their lower-case `k` as K) and 15 L-type gravity strings → no colour letter (Q31). A first pass
  also moved 19 composites (`D+dM3`, `DA+M4`, `M?+M5V`, `Am+F7/8V`, `A(7m)A9-F0` …) — fixed by the legacy fallback
  (a missing / degenerate / letter-only leading read defers to the first full OBAFGKM+subtype type, as before) and the
  legacy colour scan for a degenerate lead or a fallback read; re-run → 0 such diffs.
- **Tests:** new `test_cr30_data.py` (15), `test_cr30_parse.py`; rewritten `test_regions.py`, `test_shared.py`
  (retired-lookup class); re-pinned to S1 `test_viz_phase_o` (HR from S1; O2 smoke on a tmp DB — T3), `test_sol_result_row`,
  `test_generate` / `test_query_generate` (K2V 5100 K / 0.82), `test_query_expanded` (87 rows), `test_par_flux`
  (S1 interpolation), `test_cr27_exclusion` (S1 M5V 0.00302 L☉ / 22.935 AU); `test_cr25` oracle — frozen pre-CR-30
  helpers + the intended-drift clause (T8); `_queryharness` cache helpers → the CR-30 cache (T5); `_cr24strip.cr30_run`
  replays the 9 `spectral_type_table` fixture cases under the baseline's own M / L → byte-identical, plus the S1
  assertion (T6); conftest: CR-30 env isolation, the `cr30_twomass` default + II/246 leak stub, `test_cr30_` socket
  guard.
- **Suite:** 3943 passed / 118 skipped / 626 subtests / **0 failed** (first pass 36 failed — every one an old-table pin).
- **CP1 (`/code-review high`, 2026-10-15) — 9 findings, all triaged:**

  | # | Finding | Fold |
  |---|---|---|
  | 1 | `seed_cr30_mirrors` took `BEGIN IMMEDIATE` on every connect | a plain-read md5 check first; the write lock only when a reseed is needed (test: a held write lock doesn't block) |
  | 2 | carbon / S / R giants (`C5II`, `S4/2III`) lost their luminosity class | the parse returns CR-10.5's class even with no class letter (test) |
  | 3 | the import reported success on a failed mirror seed | `force=True` raises; the import checks all three were written (test) |
  | 4 | the gravity regex was unanchored (`F0IIIp(delta Del)` → pre-MS) | parenthesised notes ignored; a Greek / word token must be a suffix, never letter-adjacent or before a capitalised word (test) |
  | 5 | `s1_at` rebuilt its index per call | memoised per loaded table |
  | 6 | `fetch_jks` memoised only `ok` | failures memoised too, with a 300 s TTL (both routes share one attempt) |
  | 7 | `par-flux` dropped the letter-only disclosure | the S1 fields ride on its output (test) |
  | 8 | `_sp_letter('gK0')` → G (a pre-existing scan bug) | a fallback read with no lead letter takes the parse's letter (test); census unchanged |
  | 9 | the CLAUDE.md / `docs/testing.md` suite count is not updated | deferred to Stage 6 docs (planned) |

### Stage 2 — CR-30.3 (the zero point, Sol, the colour route, the 2MASS markers)
- **Formula:** `compute_star_system_regions` L = `ms_sequence.luminosity_from_mbol(M_bol)` (10^(−0.4 (M_bol − 4.74)),
  `M_BOL_SUN_S1`); `lum_override=` for the colour route (M_bol / effective BC restated on 4.74). The legacy P1.5 D2
  comment block retired with the formula. `star-regions-manual` and `main.py` run the same function.
- **Sol:** V☉ −26.76, M_V☉ 4.81, BC −0.07 → 1.0000 L☉; `sol_constants_note` (temp 5778 disclosed).
- **2MASS (`core/twomass.py`, new):** identifiers out-of-band — `databases._remember_twomass_ids` /
  `simbad_twomass_ids` (a process memo keyed by main_id; the lookup dict unchanged); `2MASS J…` only; VizieR II/246 by
  designation through `_ii246_seam` (`catalog.vizier_query`), J / Ks at 2MASS's 3-decimal precision; statuses
  `ok` / `no_id` / `multiple` / `not_looked_up` / `not_applicable` and the degrades `unreachable` / `empty` /
  `ids_failed`; `SPACE_APP_2MASS_FORCE_UNREACHABLE`; per-designation memo (failures 300 s).
- **Colour route (`ms_sequence.colour_gate` / `colour_route_luminosity`):** K / M, no class I–IV, V − J ∈ [2.53, 6.98];
  Mann 2015 base rows, zero point 4.755; both paths, the subtype L beside it, `lum_route_disagreement` > 1.40, the
  quality-below-A bands; `twomass_ids_multiple` a disclosure. Letter-only K / M take it where in span.
- **Markers (exit 0, `not_authoritative` + `twomass_status`, never a substituted route):** `star-regions`,
  `circumbinary-hz` (per star), `dyson-collector`, `exclusion-boundary --star` (result and mass error; luminosity
  null, no FLAME stand-in — §13.5 L5), `exclusion-system` single-body mass error (+ the region reason, Q14),
  `compare-stars` per star, `par-flux --star` (SIMBAD Teff used — no value moves), `generate-system` real anchor,
  the dossier (top level; the 2MASS call gated on `regions` being requested — §13.2 M2). The GUI star-regions panel
  shows the degrade reason as its error.
- **Live checks (2026-10-15):** II/246 by designation (Proxima J 5.357 Ks 4.384 AAE; Aldebaran J −2.095 CCB — WB's
  quote); `star-regions --star "Proxima Centauri"` → 0.0015721 L☉ by the colour route, paths 0.0015246 / 0.0016195,
  subtype 0.0012741, no flag; forced failure → `star-regions` exit 0 marker / null L; `exclusion-boundary --star
  Proxima --star-mass-catalog <WB cat> --alpha 0.4` exit 0 marker, r_ex 20.482354346604538 (byte-identical),
  luminosity null.
- **Tests:** `test_cr30_luminosity.py` (28 — the zero point, Sol, Lacaille, Proxima, VB 10, HD 4628, Aldebaran, the
  1.40 flag, letter-only M, multiple ids, the three degrades, the real resolution under `cr30_twomass`, the marker on
  every carrier, the dossier's identity-only gate); the legacy-formula grep added to `test_cr30_data.py`;
  `test_solvent_zones` bcLum≈1 input re-pinned to 4.74.
- **Suite:** 3978 passed / 118 skipped / 626 subtests / 0 failed.
- **CP2 (`/code-review high`, 2026-10-15) — 10 findings, all triaged:**

  | # | Finding | Fold |
  |---|---|---|
  | 1 | `generate-system`'s degrade had no `error` but `star: None` → every consumer crashed | now an error that carries the marker (no anchor L → no system; exit 1) — a deliberate departure from the "exit 0" carrier rule, reported to WB |
  | 2 | `exclusion-boundary --star --beta>0` lost the marker in the β error | the β error carries the marker (test) |
  | 3 | the dossier's 2MASS gate missed `habitable_zone` | gated on `regions` or `habitable_zone` (every `reg` consumer) |
  | 4 | the project dossier dropped a member's marker | `_member_marker` on member rows (per-file and combined) |
  | 5 | a 2MASS outage marked giants / K dwarfs whose L can't use 2MASS | **partly folded:** class I–IV skip the lookup (neither route applies); a K/M dwarf keeps it — the M_Ks route needs Ks for every K/M (Q7), so fail-loud there is the contract's |
  | 6 | `circumbinary-hz` swallowed a hard star2 error; one status for two | a non-2MASS error reported as itself; distinct statuses listed (test) |
  | 7 | the force hook lost to a cached `ok`; a forced failure was memoised | the hook is checked first and never memoised (test) |
  | 8 | the marker triplet hand-built seven times; compare-stars ran the region step twice | `twomass.degrade_marker` everywhere; compare-stars reuses one region step |
  | 9 | `_region_lum_fields` duplicated the field lists | `regions.S1_FIELD_KEYS` / `REGION_LUM_KEYS` / `region_lum_fields` |
  | 10 | two Sol V magnitudes (`sol-regions` −26.76 vs `shared._SOL_APP_MAG` −26.74 for the HR / sky Sol row) | **not changed** — ruling 22 scopes the Willmer constants to `compute_sol_regions` (sol-regions, Sol dossier); the HR / sky Sol rows are outside CR-30 and byte-identity-pinned. FYI to WB in the build report |

### Stage 3 — CR-30.4 + 30.5 (the relations, the M_Ks tier, the MIST lifetime at every site)
- **Relations (`core/ms_sequence.py`):** `mass_from_luminosity` (S12 inverted −1.066 → 5.37775 with the midpoint
  switches −0.790308 / 0.108209 / 1.628616 and the 3.4455–3.5262 gap → 7.0; S1 below the switch and above 31 M☉; no
  clamp below −3.57 — the relation / segment / switch band reported), `luminosity_from_mass` (S12 forward from
  0.615391 M☉ by inclusive upper edges; S1 outside; null outside 0.078–59), `radius_from_mass` (S1 sorted by mass;
  null outside), `mks_mass` (S13 n = 5, gate 4.5–10.5 inclusive, never clipped). Every CR-30.4 acceptance 1–5 / 9
  value and every S13 hand anchor reproduced to the stated digits.
- **The M_Ks tier (ruling 52, 164; Q10–Q11):** `regions.mks_route` (K / M dwarf, one 2MASS id, a parallax; giants
  excluded); the region step sets `stellarMass` from it (else the L route) with `mass_route` / `mass_relation` /
  `mass_segment` / `mass_switch_band` / `mass_mks_solar` / `mass_lroute_solar` / `m_ks`, and carries `mks` on a failed
  step (no Teff / V). `stellar_mass.resolve_mass(mks_mass=)` (`ms_mks_relation`, after FLAME, ahead of the L route; no
  caution); `resolve_component_mass` takes `spec["mks"]`, the L route via `mass_from_luminosity`, a `detail_out`
  side channel (route, M_Ks beside a higher tier, the catalog row), and never falls to the L route on a 2MASS
  degrade. Wired: `exclusion-boundary --star` (from the region step, failed or not), `exclusion-system` single
  body / composed A / composed B (`_mks_for`), `resolve_binary_components` A (when the record has a parallax) / B, the
  dossier and `compare-stars` (`mks_mass=`; the M_Ks mass reported beside a catalog / FLAME win). CR-26's partner
  seam untouched (Q37). The caution now fires for an O / B L-route mass only ("the A-star over-read is gone").
- **Everything a mass feeds:** the region step's R(M) / L(M) / lifetime / 0.2·M / 40·M / planetary year /
  calculated L (null with the mass); `report._patch_regions_for_mass`; the trust flag's calculated L on R(M) at the
  adopted mass (Q12); `compare-stars` R(M) (catalog parity) and its R-derived L (null R → null L + reason, Q13);
  `formation --ms-luminosity`; `stellar_mass.mass_dependent_outputs`; the generator's real anchor (a null mass / radius
  → an error). Sol pinned 1.000 M☉ (`mass_override`).
- **The lifetime (CR-30.5):** `ms_sequence.ms_lifetime` (log–log between tracks; end point named; 0.10–300) at the
  region step, `_patch_regions_for_mass`, `mass_dependent_outputs`, `compute_stellar_evolution` (t_MS; the 0.1–20
  guard and the `< 0.8` line untouched — CR-34). Labels re-pointed to MIST (`oec_derived` source + Hubble-time comment;
  `comparison` "> 13.8 Gyr" keyed off the MIST value — Q16). The per-placement treatments (≥, "if stellar") are
  Stage 4's.
- **F4:** a failed region step on the dossier still reports the mass (a `region_step_failed` regions block with the
  step's reason and the mass-derived values; HZ warned) — placement + #26 attach in Stage 4.
- **Null-safe print sites (M5):** `shared.fmt_num`; GUI `star_regions` / `sol_regions` (mass, radius, lifespan,
  planetary year, the HZ tables' L(M) / calculated L, the HZ diagram), `main.py` (stellar table, planetary year,
  L(M), the calculated-HZ table); the dossier's HZ builder.
- **Tests:** `test_cr30_relations.py` (23); re-pinned `test_comparison` (MIST ms_end; R(2.063) 2.1418),
  `test_cr23` (the L route; the caution case moved to a B3V), `test_cr25` / `test_cr27_exclusion` /
  `test_exclusion_system` (the L route), `test_formation` (L(2.0)), `test_oec_derived` (8.98 Gyr), `test_stellar_mass`
  (no caution for Sirius / Vega, B3V cautioned; MIST / S12 / R(M) downstream).
- **Suite:** 4005 passed / 118 skipped / 626 subtests / 0 failed (first pass 20 failed — every one an old-formula pin).
- **Live spot-check (2026-10-15, WB catalog, `SPACE_APP_CATALOG_CACHE=0`):** `exclusion-boundary --star` G 113-20
  0.43888 (`ms_mks_relation`, M_Ks 6.0096); 61 Cyg B 0.62242 (L route 0.61827), r_ex 39.294; HD 219134 0.80416 (L
  route; M_Ks 4.1825 outside the gate); LP 247-13 0.48416 with no V (`region_step_note` the V reason); 2MASS
  J23590836+2338311 0.07962 with no Teff.
- **CP3 (`/code-review high`, 2026-10-15) — 10 findings, all folded:**

  | # | Finding | Fold |
  |---|---|---|
  | 1 | GUI star-regions still formatted L(M) / 0.2·M / 40·M from a null mass | `_au_lm4` / `_au_lm3` / L(M) null-safe (both panels) |
  | 2 | `main.py`'s regions `au_fmt` (two copies) not null-safe | guarded |
  | 3 | the HZ guard returned from the whole diagrams builder | only the calculated-L HZ tab is skipped; `prepare_system_regions_diagram` drops null rings (test) |
  | 4 | `switch_band` never reported the lower-mass half of each dual band | one overlap test per break (test) |
  | 5 | the M_Ks activity caveat was never emitted | `mks_route` (SIMBAD active otype) + `exclusion-boundary` (CR-25's full-list wind otype) → `mks_activity_caveat` (test) |
  | 6 | markdown / HTML dossier dropped the M_Ks note (S13's binary disclosure) | rendered for `ms_mks_relation` and in the F4 block |
  | 7 | a component's 2MASS degrade fell silently to the orbit mass in both binary composers | `not_authoritative` + `twomass_status_a/_b` on `exclusion-system`, `binary-stability-auto`, the dossier multiplicity block (test) |
  | 8 | `compare-stars` never emitted `mass_mks_solar` beside a higher tier | emitted + the S13 disclosure |
  | 9 | `stellar-evolution` NaN → TypeError | the range guard rejects NaN (test) |
  | 10 | a null R(M) discarded an archive `st_lum` in `compare-stars` | only a missing L takes the null + reason |

### Stage 4 — CR-30.6 (placement) — IN PROGRESS (checkpoint written 2026-10-15 before an auto-compact)
**Done (code + verified by hand, not yet in pytest files):**
- `core/placement.py` (new): constants (HBL 0.075 inclusive, band 0.067, margin 0.080, split 0.625504, override
  log L −4.3, deadband 1.01/0.99, the 11 cut nodes, NO_AGE_CUT 0.309062, PRE_MS_OTYPES); `cut_at` (0.1824 at 0.04,
  0.09974 / 0.09783 at 0.251 / 0.271, 0.08342 held, 0.080 from 0.8); `overread_factor` (Greg's Q18 node rule — every
  acc-11 / acc-12 factor anchor reproduced, incl. 61 Cyg B @0.03 → reading 1.127615 at the 0.025 node, factor null
  "outside the table at the 0.05 Gyr node"); `reading_for` (known route + route-unknown, boundary / below-domain /
  above-domain / deadband clauses); `mass_reading`, `reading_from_catalog_row`; `place(reading, parse, log_l,
  call_age, catalog_age, otype, otype_source)` → the name map's placement object incl. `lifetime`;
  `lifetime_for_placement` (≥ t(0.10), boundary "if stellar ≥ t(M_hi)", pre-MS, substellar null).
- Verified: T1–T25 all as `test_expected` (T18 both call ages, T19 / T20 route-unknown, T15 TT*, T14 / T21 / T24
  lifetimes 1380.1 / 725.9 / 2902.4 Gyr), Wolf 359 2934.8 Gyr + x_equals_hi, M9V 0.079 boundary, M8V 0.085 stellar,
  M8 VL-G boundary, M7 VL-G [0.5,1] stellar ≤X, supplied 0.0669 substellar / 0.067 boundary, T7 / L6 / L5 / log L
  overrides + conflict flags, RX J0506 0.4631 ≤X 109.8 Gyr, TW Hya pre-MS stellar, M8 delta 3304.9, K8/K7 delta split,
  G 44-42 membership [0.005,0.02] 618.79 / model-fit not pre-MS / [0.005,5] stellar, LP 816-60 ≥ t(0.10).
- `core/stellar_mass_tables.py`: seed schema 1.1.0 with `mass_basis` / `mass_interval` (sigma_1) on the four rows;
  `validate_cr30_fields` called by `load_mass_catalog` (loud error naming row + field); WB's 23-row and 25-row
  catalogs load clean.

**Done in the second Stage-4 session (2026-10-15/16):**
- `binary._STELLAR_MIN_MSUN` is `placement.HBL_MSUN` (the one constant; tested `is`).
- `placement.age_input` (one validator: nothing → none; hi + basis required; finite ≥ 0; lo ≤ hi; `age input: …`
  curated errors) and `placement.place_resolved` (the bridge from a resolved mass's provenance: catalog → the row's
  basis / interval / age; `gaia_flame`; M_Ks / L / type routes → inference with the route; `manual` → supplied;
  `archive` → basis unknown). `place` now words the youth caveat only on youth-rule rows (a supplied / measured row
  carries the flag but no "inferred mass over-reads" caveat).
- `query.py`: `_add_age_flags` on the six `--age-*` subcommands + `compare-stars --star-age NAME LO HI BASIS`
  (`_star_ages`: NAME must match a `--stars` entry, once; `LO` may be `none`); `_call_age` validates before any network.
  `exclusion-boundary`: `placement` on `--mass-msun` (supplied, band), `--spectral-type` (type route), the evolved and
  MS `--star` paths (catalog row via `detail_out`, log L of the luminosity used, SIMBAD primary otype — component A's on
  a system entry); an age with `--mass-msun` / `--object` is a curated error; `--object` is not placed;
  `_exclusion_place_extras` adds `windless_alternative` on boundary and `r_ex_interval_au` (r_ex ∝ M^α at the row's
  lo / hi) on a boundary catalog row. `exclusion-system`: `age=` through `compute_exclusion_system`; component keys
  `age_lo=` / `age_hi=` / `age_basis=` replace the call age (Q39); a private `_cr30` side channel (catalog row, otype,
  otype source) on every component path (single body, binary A — the head's otype, Q22 — / B, `--component` — Q21),
  placed before compose and attached on `zones[].components[].placement` (a WD / rogue component → `placement: null`).
  Dossier: `regions.mass.placement` (catalog row via the memo, region L, SIMBAD otype; FLAME age never a signal) and
  the #26 lifetime on `regions.stellar` (also the F4 failed-step block); markdown / HTML render a non-plain placement.
  `compare-stars`: `stars[].placement` (+ `age_input`), Sol included. `star-regions`: top-level `placement` on the
  region-path mass (M_Ks / L route; no catalog tier), `mainSeqLifeSpan` + `ms_lifetime_*` by status.
  `detection-completeness` / `binary-stability-auto`: the age validated (exit 1) — their placement is Stage 5.
- WB's test catalog copied byte-identical to `tests/fixtures/cr30/cr30_test_mass_catalog.json` (md5 `efa69ebb…`).
- Tests: `tests/test_cr30_placement.py` (49 + 25 subtests: every CR-30.6 acceptance hand anchor in items 1–12, T1–T25,
  Q18's 61 Cyg B, the lifetimes, the r_ex interval) and `tests/test_cr30_age_input.py` (33 + 31 subtests: the validator,
  the flags on all seven subcommands, Q39, Q21, the band / override component calls, star-regions / dossier /
  compare-stars carriers, catalog validation errors, the seed bases + Sirius A dynamical offline).

- **Suite (pre-CP4):** 4091 passed / 118 skipped / 637 subtests / 46 failed — all four byte-identity fixtures seeing the
  additive keys (`test_cr24_wiring` A0, `test_cr31_wind_speed`, `test_query_exclusion_system` C6 mass guard,
  `test_report` CR-10.5 stellar table). Folded: `placement` / `age_input` added to `_cr24strip.CR30_KEYS`; the C6 test
  pops and asserts `placement.basis == supplied`; the dossier test compares the base keys and asserts
  `ms_lifetime_status == value`.
- **CP4 (`/code-review high`, 2026-10-16) — 10 findings, all folded:**

  | # | Finding | Fold |
  |---|---|---|
  | 1 | a σ interval with σ ≥ X gave a negative lo → complex `r_ex_interval_au` | the derived σ interval's lo floors at 0; `boundary_extras` uses max(lo, 0) (test) |
  | 2 | unknown provenances (the CR-14.2 orbit fallbacks) placed as the tool's inference | `binary_orbit_m1` → type route; `_m2` / equal split → relation, basis unknown; `binary_orbit_sb1_min` → a lower bound (`ge_x`; ≥ 0.075 stellar, else "undetermined (minimum mass)"; lifetime `≤ t(X)`; no windless alternative); any other → relation, basis unknown (test) |
  | 3 | `mass_uncertainty_solar` unvalidated (crash / NaN interval) | `validate_cr30_fields` requires finite ≥ 0 (test) |
  | 4 | placements keyed by component id collided on duplicate ids | the placement rides on the component through compose (`_placement` → `_placement_field`); a bare compose emits no key (tests) |
  | 5 | binary path A's pre-MS otype read the head | `_a_otype`: component A's own record via `resolve_star_identity` (the head's only on a failed A lookup) (test) |
  | 6 | `dossier --star Sol` accepted and dropped the age; no placement | Sol placed (G2V, the call's age) with its lifetime, as compare-stars (test) |
  | 7 | the catalog enums duplicated `placement`'s sets | `stellar_mass_tables` derives them from `core.placement` (test) |
  | 8 | boundary extras and the lifetime copy duplicated across carriers | `placement.boundary_extras` / `placement.apply_lifetime` — one copy each, used by both exclusion subcommands, star-regions and the dossier |
  | 9 | `resolve_component_mass` matched the catalog three times | matched once, passed as `catalog_row`, reused for `detail_out` (test) |
  | 10 | the CR-10.5 consistency comment / `_inversion_radius` name contradicted Q12 | renamed `_adopted_radius`; comment states R(M) at the adopted mass |

**Remaining in Stage 4 (do next, in order):**
1. ~~`binary._STELLAR_MIN_MSUN`~~ done. Items 2–6 done.
- **Suite (post-CP4):** **4101 passed / 118 skipped / 686 subtests / 0 failed** (2026-10-16). (An intermediate run
  showed one `test_query_phase_t` transit-signal failure caused by editing `query.py` while a subprocess test spawned —
  passes alone and in this clean run.) **Stage 4 COMPLETE.**

### Stage 5 — CR-30.7 (placement's consumers) — COMPLETE 2026-10-16 (CP5 folded)
- **A (domain):** `detection._host_class` → `brown_dwarf` only for T / Y / L > L5 (L0–L5 and letter-only L → placed by
  mass). `exclusion_wall.UNDETERMINED_NO_MASS` (5th value) + `NOTE_SUBSTELLAR_PLACED`; `compute_two_layer_boundary`'s
  undetermined branch (null standoff / wall, `wall_route` `none_undetermined`, `domain_note`). `exclusion-boundary`:
  `--mass-msun` placed substellar → the free harbor (mass echoed); `--spectral-type` L0–L5 → undetermined (exit 0),
  T / Y / L6+ → windless + the override's placement; `--star` T / Y / L6+ → the ladder without inference (catalog →
  FLAME) for the conflict flag, then the free harbor (`mass_msun` stays null); `--star` L0–L5 → no M_Ks / L route,
  no mass → undetermined; any mass placed substellar → the free harbor. WD / sdO / presets keep their early returns.
  `exclusion-system`: `_classify_off_ms` sets only `wd` (H4); `_routes_off_ms` keeps the CR-13 routing; compose's
  `_domain_by_placement` (substellar → windless, undetermined → the 5th value, `forcing_class` null); single body and
  `--component` L0–L5 with no mass pass through to undetermined; placement runs before the CR-26 inputs
  (`_placed_domain`).
- **B (`binary.py`):** `m1_read` / `m1_from_spectral_type` = S1 (anchor ladder + 1.0 default retired; the census keeps
  `_CENSUS_M1_MSUN` with `m1_assumed_note`); null M₁ with reasons (`no_spectral_type` = CR-27's text,
  `letter_only_type`, `unreadable_type`, `outside_s1_mass_span`, `no_simbad_lookup`) at NSS / SB9 / census rows;
  `classify_companion` ≥ 0.075 stellar, [0.067, 0.075) boundary, SB1 minimum < 0.075 "undetermined (minimum mass)";
  `flag_companion` (type-string signals at binary-orbit); `apply_primary_directions` (`placement_a`, `m1_direction` /
  `m2_direction`, `m2_class`, `sb1_caveat_withheld`, the null-M₁ no-masses note) on `binary-stability-auto` (age) and
  the dossier multiplicity block (age, Q33); `multiplicity` `m2_solar_lower_direction`; identity `lum_class_token` /
  `s1_class_v_flag` / `m1_null_reason` (C14); `_m1_decodes` / the CR-16 gates read S1 (M5).
- **C (detection):** `_resolve_star_mr` → S1 mass + radius at the subtype, R(M) for a mass without radius
  (`_MS_MASS_RADIUS` deleted); `star_placement`; the explicit branch (`_explicit_branch`); `limit_direction` +
  `star_radius_bound_note` under "≤ X"; `--star-mass-catalog` (seed default) — manual → catalog → archive, the archive
  radius beside an MS host's mass (ruling 95), a non-MS host's catalog mass only with a radius
  (`catalog_mass_not_applied` + note), the catalog-beside-archive and archive-basis notes; SIMBAD otype → E.
- **D (census):** `placement_status_by_type` per row, `census_label`, `placement_note`; help + query index relabelled.
- **Re-pins:** `test_binary` (classifier edge, S1 M₁, null reasons), `test_binary_stability_auto` (SB9 mock kwargs),
  `test_cr22` (L3 → L6 windless), `test_cr25` (L5 into the intended-drift set + its assertions), `test_cr27_simbad`
  (sp-less M₁ null), `test_detection` (S1 M / R, A0V 2.18, L5 → branch, `_host_class` L5 / L6),
  `test_exclusion_system` L251 (H4), `test_query_exclusion_system` (1e-9 / 5e-324 → the free harbor).
- **Tests:** `tests/test_cr30_consumers.py` (35 + 3 subtests: CR-30.7 acceptance 1–6 offline, the composed α Cen M9
  check — standoffs byte-identical, SMA within 1e-12 — and C14).
- **Suite (pre-CP5):** 4136 passed / 118 skipped / 696 subtests / 0 failed (2026-10-16).
- **CP5 (`/code-review high`, 2026-10-16) — 10 findings, all folded:**

  | # | Finding | Fold |
  |---|---|---|
  | 1 | an `undetermined_no_mass` member merged with a star → TypeError in `_zone_envelope` (None mass summed) | a massless member adds no barycentre weight (test: G2V + L3 pair, exit 0) |
  | 2 | placement substellar while the domain stayed main_sequence (`--spectral-type` + a low L; `--star` decision on a different L than reported) | the reroute runs on every path with the luminosity the placement reports (by mass first, then on `lum_eff`) (test) |
  | 3 | `derive_mass_loss_tier` missed the 5th value (`supplied` on exclusion-system vs `noncoronal_row`) | undetermined joins windless / unmodeled (test) |
  | 4 | the null-M₁ note overwrote "no orbital solution found … does not imply single" | the M₁ note only where an orbit exists (test) |
  | 5 | `--component` L0–L5 with `lum=` took the luminosity route (Q28 breach) | an L0–L5 component's mass resolve never sees `lum=` (test) |
  | 6 | the `--star` standoff pre-check classified before placement | it reads `_placed_domain` |
  | 7 | the binary path's A-otype lookup was a second SIMBAD identity call, not reused; failure silent | `_a_otype` runs the CR-27.4 identity step once and hands its answer to CR-26's A lookup (`a_prefetch`); a failed lookup is noted (test) |
  | 8 | the T / Y / L6+ ladder hid a bounded FLAME fetch | `flame_status` surfaced (test) |
  | 9 | the detection branch blamed placement for any null; an unreadable type no longer errored | an unreadable type with no mass is the curated error again; the note names its cause — the placement (with S1's reason) or the null radius (test) |
  | 10 | the domain-after-placement rule implemented twice | `exclusion_wall.placed_domain_kw` — the one rule both subcommands use |
- **Suite (post-CP5):** **4144 passed / 118 skipped / 696 subtests / 0 failed** (2026-10-16). **Stage 5 COMPLETE.**

### Stage 6 — docs, name-map re-check, CP6, live pre-check, build report — COMPLETE 2026-10-16 (build report MSG 365)
2. The age input (plan §5.3): argparse `--age-lo-gyr` / `--age-hi-gyr` / `--age-basis` (basis required with an age;
   lo ≤ hi; finite ≥ 0) on exclusion-boundary (--star and --spectral-type), exclusion-system (call level + per
   component keys `age_lo=` / `age_hi=` / `age_basis=` in `_parse_component_spec` `_known` — component replaces call,
   Q39), dossier, star-regions, detection-completeness (--star / --sp-type; wiring in Stage 5), binary-stability-auto
   (Stage 5); compare-stars `--star-age NAME LO HI BASIS` (repeatable, LO may be `none`). One helper in query.py
   building `{"lo_gyr","hi_gyr","basis"}`.
3. Attach `placement` (plan §5.6): exclusion-boundary (`placement` top level — inference: route from `_md`
   mass_route; catalog: `_md["catalog_row"]` → `reading_from_catalog_row`; FLAME → basis gaia_flame; manual
   `--mass-msun` → supplied, band only; `--spectral-type` → inference route "type"; log L = log10 of the luminosity
   used; otype = SIMBAD `ot` (component A's on a system entry, Q22)); exclusion-system `components[].placement`
   (component `otype=` first code is a pre-MS signal, Q21; one call age to every resolved component, Q23); dossier
   `regions.mass.placement` (reading from mass block provenance; age; SIMBAD otype; FLAME age never a signal) and the
   #26 lifetime treatment on `regions.stellar.main_seq_lifespan_yr` + `ms_lifetime_*` fields (also the F4
   region_step_failed block); compare-stars `stars[].placement` (on `mass_solar`, Q26); star-regions top-level
   `placement` on the region-path mass (no catalog tier; age + designations + SIMBAD primary otype, Q25).
   Directions: `r_ex_direction` upper_bound iff reading le_x; a boundary catalog row `r_ex_interval_au [lo, hi]`.
4. Tests: `tests/test_cr30_placement.py` (the anchors above + T1–T25 from a copy of the test catalog in
   `tests/fixtures/cr30/` with its md5 `efa69ebb…` checked) and `tests/test_cr30_age_input.py` (the flags on all
   seven subcommands; validation errors; catalog validation errors; seed bases — Sirius A dynamical on
   `exclusion-boundary --star "Sirius A"` offline-stubbed).
5. Add `placement` / CR-30 keys to `tests/_cr24strip.CR30_KEYS` if the byte-identity fixtures break.
6. Full suite → CP4 (`/code-review high`) → fold → record in this log.

**Stage 5 (CR-30.7) — plan §6 + §13.5 — not started.** **Stage 6 (docs, name-map re-check, CP6, live pre-check,
build report MSG to WB) — not started.** Git-held throughout; commit only after WB GREEN + Greg FULFILLED.
- **Docs (2026-10-16):** a docs agent wrote the `docs/integration.md` CR-30 block (data + md5s, the parse, the
  luminosity routes + markers, the relations, MIST, placement, the age input, the consumers, the `cr30_disclosures`
  topic table and the **disclosure inventory table** — §13.6 C5), the per-subcommand CR-30 notes, `docs/testing.md`
  (seven offline files + `test_cr30_live.py`), `CLAUDE.md` (guardrail, the `core/` map, the opt-54 label),
  `docs/core-modules.md`, `docs/query-commands-index.md` (19 one-liners), `docs/star-system-regions.md`,
  `docs/science-and-scifi.md`, `docs/gui-architecture.md`; I fixed `docs/star-databases.md` (opt 54, the static-table
  line, the inversion wording) and `docs/equations.md` (T_ms → MIST). Its contradictions report was folded: the
  `main-sequence` list output carries no disclosure block (documented); `binary-orbit identity.s1_class_v_flag` now means
  "S1 seeded M₁" everywhere; the name map's stale names fixed; `main.py`'s opt-54 label; `tests/test_cr30_live.py` written
  (8 opt-in anchors, plan §13.6 T13). (`tests/test_cr30_lifetime.py` was never split out — the MIST tests live in
  `test_cr30_relations.py`.)
- **`cr30_disclosures` (§7, C5):** `ms_sequence.CR30_DISCLOSURES` (topics s1 / luminosity / relations / lifetime / hbl /
  youth), attached by `query._out` per call only where the call reads S1 / MIST / the factor (`_cr30_topics`; a numeric
  call carries none). Re-pins: `test_query_generate` key sets, the C6 mass-guard test; `_cr24strip.CR30_KEYS`.
- **Name map re-checked** against the built outputs (status line updated; paths, the dossier's one path
  `data.regions.mass.placement` — WB MSG 363's request, readings / bases / directions / lifetime statuses as built,
  `cr30_disclosures` by subcommand, the catalog-field error shape).
- **CP6 (`/code-review high`, the whole diff vs 2c22208, 2026-10-16) — 10 findings:**

  | # | Finding | Fold |
  |---|---|---|
  | 1 | binary components marked `not_authoritative` / `twomass_status_a/_b` on an M_Ks degrade even when a catalog / FLAME mass won (α Cen under a VizieR outage); 2MASS fetched before the higher tiers | the M_Ks tier is a lazy callable on every binary / single-body path, fetched only when manual / catalog / FLAME miss; the marker only when that tier was reached (test) |
  | 2 | `classify_companion(minimum=True)` turned planetary SB1 minima into "undetermined (minimum mass)", leaking them past every planet filter | the class stays the contract's; `binary.is_planetary_companion` (class `planet`, or an SB1 minimum < 0.013) drives the three filters — census `drop_planets`, `is_orbit_solution`, the dossier's stellar list (test) |
  | 3 | compare-stars drops bcLuminosity when R(M) is null | **no behaviour change** — Q13's ruling (a null R(M) → a null L with its reason); the comment now says the reported L is R(M)²(T/5778)⁴ and bcLuminosity only seeds it |
  | 4 | the CR-30 mirror-seed warnings went to stdout (ahead of query.py's JSON) | `core.shared._stderr_warn` (test) |
  | 5 | a no-parallax K / M star made a VizieR call and a degrade masked "Parallax not available" | no 2MASS lookup without a parallax (test) |
  | 6 | exclusion-system's log L < −4.3 override read only an L-route component's L | `_override_lum`: the region L for a late-M / L / T / Y component (the only types that can reach it), single body and binary A / B (test) |
  | 7 | dead `hot_ms`, unused `_parse_spectral_class` import, stale T_ms comment | removed / rewritten |
  | 8 | CLAUDE.md / docs stale (opt-54 CLI label, live-file list, testing.md "no new live file"); the suite count | fixed; the count is filled from the final suite run |
  | 9 | `_s1_pairs` rebuilt per call; `_node_rows` scanned 888 rows per node | memoised per loaded table |
  | 10 | `exclusion-system` with supplied masses only carried all six topics | per call: `hbl` only when every component is a supplied `mass=` (test) |

  Re-pin from the fold: `test_binary_stability_auto` CR-16 trigger guard → the S1 gate (§13.4 M5).
- **Post-CP6 suite:** 4155 passed / 126 skipped (118 + `test_cr30_live`'s 8) / 696 subtests / 0 failed.
- **Live pre-check (plan §10), 2026-10-15 / 16, on `live/build.db` (a copy), `SPACE_APP_CATALOG_CACHE=0`, strictly
  sequential (scratchpad `live/runner*.py`; outputs as JSON per call):**
  - **Byte-identity (§8) vs the `2c22208` worktree baseline (12 cases):** every standoff / wall value identical — Sol 47.5 /
    wall 6.0, the presets, `--mass-msun 0.3` 29.345540401952064, α Cen A 48.966852301574924 / B 45.72136239364217, Sirius A
    63.45901120705829, ε Eri 43.68623962821011, BL Cet 20.509168118090486, Proxima 20.482354346604538; `simbad-lookup`
    tau Cet / Wolf 359 / GJ 65 identical; keys additive. Deliberate: `luminosity_lsun` (CR-30.3 — the reported L, not
    the standoff's input); α Cen's `separations_au` and `wall_envelope_au.periastron` move by 1 ulp (S1's G2V M₁ 1.0 for
    the old 1.02 anchor in the orbit-selected a_bin, rescaled by CR-15.3's `(M_pref/M_sel)^⅓` — mathematically
    invariant; relative 2×10⁻¹⁶, inside MSG 363's R7 1×10⁻¹²).
  - **Sweep 1 (108 calls) + the binary-orbit re-run (12) + sweep 2 (99 calls the first missed):** every non-zero exit is
    a contract-required error (`--spectral-type M`; LEHPM 3396 and HD 239960B's mass error, as at HEAD; the two forced
    2MASS failures carrying `not_authoritative` + `twomass_status`, never the L route's value). Two agents cross-checked
    every covered acceptance item against the contract; no live catalog drift.
  - **Defects found and fixed (tests in `test_cr30_consumers.py::LivePrecheckFixesTest`):**

    | # | Finding | Fix |
    |---|---|---|
    | 1 | a pre-MS (E) placement reported `cut_msun` 0.08 beside its t_lo (RX J0506.2+0439 at 0.05–0.1 Gyr; contract 0.163074) | the cut is computed wherever the youth rule applies, before the status branch |
    | 2 | `binary-stability-auto` withheld the SB1 caveat on `elements` only — `selected_solution.companion` and `resolution_notes` still said "true M₂ ≥ this" (HIP 76901); LP 120-4's printed orbit kept `boundary` | `apply_primary_directions` flags the selected orbit's companion (`flag_companion`) and swaps the resolution note (`NOTE_SB1_MIN_RESOLUTION_FLAGGED`); an unflagged primary untouched |
    | 3 | the detection explicit branch on a tier mass placed boundary named only the null radius (DENIS-P J082303.1-491201) | the note names the placement first, then the radius |
    | 4 | the dossier's `regions` dropped the type-read / L-route keys and the mass-route keys (Lalande 21185: "the route named"), and `stellar` dropped the R(M) / L(M) null reasons (tau Cet `--mass-solar` 0.077 / 60) | `_regions_data` + `regions.region_lum_fields`; `stellar.*_relation` / `*_null_reason`; `_dossier_mass_route_fields` on `regions.mass` (route keys null under a tier above inference; Sol pinned); the failed-region path too |
    | 5 | `stellar-evolution` 0.62 M☉ not labelled interpolated (contract CR-30.5 acceptance 1) | additive `t_ms_gyr` + `ms_lifetime_end_point`; name map + integration.md updated |

    | 6 | (re-check) a dossier on a failed region step (SCR J1845-6357, no Teff) gave `mass_route` null on an M_Ks mass — the failed step carries no route record | the route keys follow the adopted tier (`mks` → `Mann2019_n5`; Sol `sol_pinned`); relation / segment from the region step only where its route matches |

    Live re-check of the fixes (11 calls, 2026-10-16): all exit 0 — Lalande names the subtype route and the two 2MASS ids
    on a catalog mass; tau Cet 0.077 / 60 null R(M) / L(M) with reasons; G 113-20 `mks` / `Mann2019_n5` 0.43888;
    `stellar-evolution` 0.62 → 50.312 Gyr `interpolated_1e-2_to_1e-4`; LP 120-4 "at most boundary" on `elements` and the
    selected orbit; `bsa_srcid` elements null with the no-masses note (Gaia's `binary_masses` M₁ 0.2282 is on
    `binary-orbit`'s companion block — `binary-stability-auto` has no cross-check block on a null selection, as BD-01 1701);
    Lalande without a catalog 0.3975 / 32.84 AU; α Cen and Proxima's standoffs still byte-identical.
    Also: `binary-orbit` takes no `--gaia-timeout` — the sweep's argv and `test_cr30_live`'s HIP 76901 call fixed.
- **Final suite (post-fix, incl. fix 6):** **4159 passed / 126 skipped / 698 subtests / 0 failed** (5 m 21 s). CLAUDE.md and
  `docs/testing.md` updated.
- **GUI import (plan §10):** Greg ran option 54 "Import CR-30 Reference Tables" in the real GUI, 2026-10-16 — completed;
  `data/space_app.db` mirrors `ms_reference_s1` 87 / `ms_reference_mist` 171 / `ms_reference_factor` 888 rows;
  `main_sequence_stars` (24 rows) untouched.

### 15.R1 — WB re-gate 1 (MSG 366, 2026-10-17): NOT GREEN, 10 items → fixed

WB ran 1070 live runs on tree `6c1d2800` and listed 10 items to fix. It accepted MSG 365's three points: generate-system's
2MASS degrade as error + marker; the two Sol V magnitudes, which are routed to CR-28 + CR-33; and `bsa_srcid`.

| # | Item | Fix |
|---|---|---|
| F-1 a (HIGH) | `binary-stability-auto` skipped the M_Ks tier (its reduced record has no parallax) | `resolve_binary_components._prim_mks` widens a record with no `plx_value` by one SIMBAD lookup of `main_id`, lazily, only when the tier is reached |
| F-1 b (HIGH, Greg) | SB1 M₂ kept at the orbit's M₁ | `binary.sb1_m2_at`: re-solved from the orbit's mass function at the settled M₁ (every tier) on bsa / dossier / exclusion-system; the printed `selected_solution.companion` follows, with its class (`apply_primary_directions`) |
| F-5 (HIGH) | dossier gave a WD MS values (Sirius B, Procyon B) | failed-step branch only on a missing Teff / V / parallax or a 2MASS degrade (`regions.is_input_failure`; `ERR_NO_*` constants) |
| F-2 | compare-stars: M_Ks mass moved the archive mass / radius | override takes a measured mass only (manual / catalog / FLAME whitelist) |
| F-9 (Greg) | exclusion-system M_Ks single body lost the β term's L | an M_Ks MS body keeps the region L as `luminosity_lsun` (catalog / FLAME gap left, routed to CR-28 + CR-33) |
| F-3 (Greg) | null mass didn't name its reason | `resolve_component_mass`: a supplied L below M9.5V names the L route's reason, no "or lum=" hint |
| F-6 | L3beta lost the type-read keys | `query._with_type_read` on every no-S1-row `--spectral-type` output |
| F-4 | `lum_route_note` unnamed | name map + `docs/integration.md` |
| F-7 (Greg) | detection explicit branch dropped HEAD's fields | `_explicit_branch` keeps `assumptions.{mag_domain, sma_grid_au, albedo, monotonicity, host_class_note}`, `baseline_yr`, imaging `contrast_band` / `mechanism_caveat`; it now runs after the grid / method validation |
| F-8 (Greg) | forced 2MASS failure dropped L-independent star-regions fields | `regions.l_independent_fields` (shared `_distance_values` / `_eeo_temperatures` with the region step) + `hypatia` on the degrade path |

- **Tests:** `test_cr30_consumers.py::RegateFixesTest` (12). First suite run: 4168 / 126 / 698 / 0.
- **`/code-review high` (the MSG 366 fixes only), 10 findings.**
  - Folded:
    - #2: the F-5 gate dropped the 2MASS-degrade dossier → `is_input_failure`.
    - #3: the printed companion was stale.
    - #5: the windless / evolved `--spectral-type` branch had no type read.
    - #8: duplicated formulas → shared helpers.
    - #9: F-2 used an exclude-list → whitelist.
    - #10: suite counts.
  - Not folded:
    - #1: an M_Ks body with a failed region step gets `or 1.0` in β. That is the same pre-existing catalog / FLAME
      gap Greg routed to CR-28 + CR-33; disclosed to WB.
    - #4: use the identity's parallax instead of a lookup. Rejected — `parallax_mas` can be Gaia-filled, which would
      split bsa from the dossier, and component B already makes the same lazy SIMBAD lookup.
    - #6: the L-type `lum=` hint. Outside MSG 366; `lum=inf` keeps NaN's CR-22.6 message.
    - #7: string-keyed branching. The errors are single module constants; an `error_kind` key would be an unrequested
      output key.
- **Live re-check:** 19 calls, `cr30-live-precheck/runner4.py` on a DB copy, `SPACE_APP_CATALOG_CACHE=0`. All behave
  as fixed: HIP 76901 0.25865 / 0.0545752 on bsa / dossier / exclusion-system; Sirius B / Procyon B with no MS values;
  SCR J1845 still reported; GJ 1061 0.12 / 0.156 kept; EZ Aqr β 0.5 1.4756 on both subcommands; δ Pav 47.33
  unchanged. α Cen 48.966852301574924 / 45.72136239364217 and Proxima 20.482354346604538 byte-identical.
- **Final suite:** 4171 passed / 126 skipped / 701 subtests / 0 failed. The interim run had one CR-19 watchdog
  wall-clock flake (1.83 s vs 1.5 s under load; 3/3 in isolation; untouched code).

### 15.R2 — WB re-gate 2 (MSG 368, 2026-10-17): all 10 MSG 366 fixes hold; 1 item (O-1, MED) → fixed

WB re-ran the whole population (1070 + 8 extras) on tree `488f8f35`. Only 31 cases differ from the first build: the
fixes (16) and SIMBAD drift (15). Greg accepted:
- the F-5 gate including the 2MASS degrade;
- F-7's per-method keys on the L-type branch;
- the three left-as-is items: the failed-region-step M_Ks body → CR-28 + CR-33, the "or lum=" hint accepted, `lum=inf`
  → CR-28.

O-2 (catalogs answering empty with no marker) is routed to CR-28 + CR-33; nothing for CR-30.

- **O-1.** A failed SIMBAD lookup on the binary paths fell to the orbit's mass in silence. Fix:
  - `stellar_mass.simbad_service_failed` separates a service error from SIMBAD's "No results found".
  - `mark_simbad_failure` sets `not_authoritative` + `simbad_status_<a|b>: "failed"`.
  - Where it is set in `resolve_binary_components`:
    - A's widening lookup in `_prim_mks`, which runs only when the M_Ks tier is reached; a raising lookup counts too;
    - B's record, when no manual / catalog / FLAME tier gave B a mass.
  - `binary_stability_auto` also marks a failed primary lookup on coordinate / source-id input.
  - Propagated on `binary-stability-auto` (top level) and the dossier `multiplicity` block.
  - `exclusion-system --star`: B's failed lookup is **always** marked, because B's record also carries its WD / BD class
    for the domain guard. Its note `NOTE_SIMBAD_FAILED_B`, with the `--component class=` hint, replaces "companion
    nature not confirmed". `comp_failed` now reuses the helper.
- **`/code-review high` (the O-1 change only), 10 findings.**
  - Folded:
    - #1: a catalog-mass B with a failed lookup lost every disclosure → always marked on exclusion-system.
    - #2: the coordinate-input primary lookup.
    - #4: the note's MS / override hint.
    - #5: the contract doc.
    - #6: `comp_failed` reuses the helper.
    - #8: a raising lookup.
    - #9: a dossier test.
    - #10: the dead `simbad_status_a` key on exclusion-system.
  - Not folded:
    - #3: a failed CR-16 primary lookup inside `binary_orbit` falls to "no redirect". This is pre-existing CR-16
      behaviour outside O-1's two lookups, and marking it would need a new key on the orbit identity; disclosed to WB.
    - #7: move the B gate into the shared chain. The two resolvers' rules now differ deliberately (exclusion-system's
      class guard).
- **Tests:** `SimbadFailLoudTest` (9).
- **Suite:** 4180 passed / 126 skipped / 703 subtests / 0 failed.
- **Live check** (`runner5.py`, 5 calls): HIP 76901 0.25865 / 0.0545752 on all three paths; α Cen 48.966852301574924 /
  45.72136239364217; Sirius A 63.45901120705829. No spurious markers when SIMBAD answers.

### 15.R3 — WB re-gate 3 (MSG 371, 2026-10-18): GREEN; Greg FULFILLED → committed

WB re-gated tree `ebb5dd9a` (diff md5 `5c1117df…`): O-1 live on every path named in MSG 369, and the whole
population (1070 + 8 extras) value-identical to the fix round's healthy run. Greg signed CR-30 FULFILLED 2026-10-18.
Committed as `f4765c8` (tree `ebb5dd9a`, parent `2c22208`). This plan and the name map moved to `completed_plans/`
in a separate close-out commit. Routed to CR-28 + CR-33, no CR-30 action: O-3 (`binary-orbit --star` + coordinates
with a failed lookup, unmarked, `m1_null_reason` `no_spectral_type`) and O-4 (the dossier reads a NASA Exoplanet
Archive error as "no planets", `core/report.py`).
