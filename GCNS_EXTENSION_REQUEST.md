# Feature Request: Extend the local catalog with GCNS for completeness + real distances

Status: **IMPLEMENTED** (2026-06-05). Written by the consuming project (a hard-SF worldbuilding repo that reads `starSystems.csv` via `query.py` and directly). Self-contained — no access to the other repo is needed to act on this.

> **Implementation note.** Shipped as menu **option 58 (Import GCNS Data)** — `core.databases.compute_gcns_ingest`. Rather than overwriting `starSystems.csv`, GCNS is ingested into an **isolated** `gcns_stars` table (the SIMBAD-built `star_systems` table and opts 50/51 are left untouched), with the SIMBAD identity layer attached by exact-key cross-match. The two-layer schema, uncertainties, provenance, and all hard constraints below are honoured. Exposed via `query.py` subcommands `gcns-within-sol`, `gcns-source`, and `gcns-system`. The "expose resolved-systems info" item (Hard constraints, multiplicity) was **also implemented** — `gcns.resolvedss` is ingested into `gcns_systems` / `gcns_system_members` / `gcns_system_pairs` and queried via `gcns-system --id`. See `docs/star-databases.md` ("Import GCNS Data Feature (opt 58)") and `docs/integration.md` (GCNS subcommand contract) for the as-built details.

## TL;DR

`starSystems.csv` is currently built from SIMBAD criteria queries (opts 50/51 in `docs/star-databases.md`). An audit of the file shows it is **materially incomplete and stores distances without uncertainties**. Please add a path that ingests the **Gaia Catalogue of Nearby Stars (GCNS)** as the astrometric/completeness backbone, cross-matched with the existing SIMBAD data on Gaia source_id, producing a more complete catalog with **Bayesian distances + uncertainties** while preserving SIMBAD spectral types and common names. GCNS does **not** provide spectral types or Johnson V, and does **not** fix the cold brown-dwarf tail — those limits are called out below so they aren't accidentally "solved" by overwriting good SIMBAD data with nothing.

## Why (audit findings on the current `starSystems.csv`)

Measured directly from the file (253,608 rows, 9 columns):

- **Incomplete vs the definitive census.** It holds **253,608** objects to ~100 pc; the **GCNS holds 331,312** to the same 100 pc — so it is **~77% complete, missing ~78,000 objects**, concentrated in faint cool/substellar dwarfs.
- **Distances are derived from parallax with no uncertainty.** `Parsecs = 1000/parallax` and `Light Years = parsecs × 3.26156` hold for **every** row (confirmed: 0 inconsistencies). The two distance columns are pure functions of `plx_value`; there are **no error bars**, and raw `1/ϖ` is biased for low-S/N parallaxes (Bailer-Jones).
- **Selection:** a hard parallax cut at ϖ ≈ 10 mas → a ~100 pc (≈326 ly) volume sample. Min parallax 9.9901 mas; max distance 326.479 ly (only 6 objects at the edge — a clean cut, not a pile-up).
- **Sparse non-astrometric data:** Spectral Type **72.2% blank**; Apparent Magnitude (Johnson V) **72.5% blank**; 39.3% of `Star Name`s are bare `Gaia …` IDs.
- **Provenance:** Gaia IDs in 98.9% of rows (so SIMBAD's nearby-star astrometry is already Gaia EDR3 under the hood); but SIMBAD is, per CDS, "not a catalogue and should not be used as a catalogue" — it's literature-driven, which is why the faint Gaia-detected objects are missing.
- **Rows ≠ systems:** 1,448 component rows (names ending A/B/C) + 999 composite spectral types (`+`).

## Goal

Produce a local-catalog build that is (a) **complete for stars to 100 pc** (GCNS), (b) carries **distances with uncertainties**, and (c) **keeps** SIMBAD's spectral types and common names where they exist — without silently mixing photometric systems or fabricating classifications.

## Requested work

### 1. Add a GCNS ingestion path
Pull the GCNS via any of these (all astroquery/pyvo-friendly; pick what fits the codebase):
- **VizieR** catalog `J/A+A/649/A6`, table `table1c` (GCNS main, 331,312 rows). Use `astroquery.vizier` with `ROW_LIMIT=-1` (VizieR truncates by default).
- **GAVO TAP** at `https://dc.g-vo.org/tap` — tables `gcns.main` (331,312), `gcns.missing_10mas` (1,258 known-nearby objects Gaia EDR3 missed), `gcns.resolvedss` (resolved binaries). ADQL.
- **Gaia ESA Archive** (`astroquery.gaia`) — GCNS value-added table, or `gaiadr3.gaia_source` with `parallax > 10` **plus** GCNS-style spurious-source cleaning (do **not** hand-roll the cleaning if you can pull GCNS, which already did random-forest spurious removal + Bayesian distances).

Recommended: **GCNS `main` + `missing_10mas`**. Prefer it over raw `gaia_source` so you inherit the vetting and Bayesian distances.

### 2. Cross-match to existing SIMBAD rows
Join GCNS `source_id` ↔ the Gaia EDR3 IDs already parsed into `Star Designations` (the build already extracts "Gaia EDR3" IDs). **Caution:** Gaia **EDR3 and DR3 source_ids are identical**, but **DR2 source_ids differ** — match on EDR3/DR3 only; do not match DR2 IDs positionally without care. Use the join to (a) dedup, (b) identify the ~78k GCNS objects not currently in the file, (c) attach SIMBAD spectral type + `main_id` name to GCNS rows where available.

### 3. Merge into a two-layer schema
- **GCNS = astrometric/completeness backbone:** `source_id`, Bayesian distance percentiles (dist 16/50/84, pc), `parallax` + `parallax_error`, Gaia `G/BP/RP`, probability-of-being-a-white-dwarf, probability-of-reliable-astrometry, radial velocity where present, galactic kinematics.
- **SIMBAD = identity/classification layer:** `Spectral Type`, common `Star Name`, Johnson `V` — joined on source_id; left blank for Gaia-only rows (do **not** fabricate).

### 4. Preserve uncertainties and provenance (the current file drops both)
Add columns; keep the existing nine for backward compatibility (or version the file — see §6). Suggested additions:

| Column | Source | Notes |
|---|---|---|
| `gaia_source_id` | GCNS | EDR3/DR3 source_id (join key) |
| `dist_pc` | GCNS | Bayesian median (dist_50) |
| `dist_lo_pc`, `dist_hi_pc` | GCNS | 16th/84th percentiles |
| `parallax_error` | GCNS/Gaia | mas |
| `phot_g_mean_mag`, `phot_bp_mean_mag`, `phot_rp_mean_mag` | GCNS | **Gaia bands — NOT Johnson V** |
| `wd_prob` | GCNS | probability white dwarf |
| `astrom_reliable_prob` | GCNS | probability of reliable astrometry |
| `rv_kms` | GCNS | where available |
| `in_gcns`, `in_simbad` | derived | provenance flags |
| `distance_method` | derived | `gcns_bayesian` vs `simbad_plx_inversion` |
| `snapshot_date`, `gcns_version` | build | reproducibility |

### 5. Keep `query.py` working
Either extend the existing subcommands to expose the richer fields (distance-with-uncertainty, completeness/provenance flags) or, at minimum, keep the current `query.py` contract working against the extended CSV. Document any schema change in `docs/`.

## Hard constraints / do-nots

- **Do not mix Gaia G with Johnson V.** Keep `G/BP/RP` separate from the SIMBAD `V` column. If you add a G→V estimate, mark it derived/approximate (color-dependent) — never overwrite measured V.
- **Do not fabricate spectral types.** GCNS has none; most faint Gaia-only objects have no published type anywhere. Leave blank.
- **Do not silently replace SIMBAD distances with GCNS for matched rows without a flag.** Carry `distance_method` so consumers know which basis a row uses.
- **Mind multiplicity:** rows ≠ systems. Don't collapse components silently; expose the resolved-systems info (`gcns.resolvedss`) if practical. ✅ **Done** — `gcns.resolvedss` is ingested into `gcns_systems`/`gcns_system_members`/`gcns_system_pairs` (systems = connected components over the resolved pairs); `gcns_stars` component rows are never collapsed (linkage is join-only via `system_id`); queryable through `query.py gcns-system --id`.

## Known limits to document (not fix)

- **Substellar incompleteness is fundamental.** GCNS (Gaia-only) is ~95% complete only to ~M7–M8; L/T/Y dwarfs are too faint for Gaia beyond ~10–25 pc. If a more complete cold-dwarf census is wanted, add the IR-parallax samples **Best et al. 2021** and **Kirkpatrick et al. 2021** (as CNS5 did), flagged as supplementary — but accept that beyond ~25 pc the substellar census stays partial. Document this; do not imply completeness.
- Snapshot/version: GCNS is Gaia EDR3-based and static; record the GCNS/VizieR version and pull date.

## Acceptance criteria

1. Build reaches **≥ 331,312** sources within 100 pc (GCNS main), optionally + `missing_10mas`.
2. **Every row has a distance with an uncertainty** (lo/hi).
3. Cross-match statistics reported: counts of SIMBAD-matched vs Gaia-only; how many new objects added vs the old 253,608.
4. Spectral-type and V coverage reported (expected to stay low — that's fine and expected).
5. No Gaia-band magnitude written into the Johnson `V` column.
6. Provenance + snapshot date recorded; `docs/` updated; `query.py` contract preserved or its changes documented.

## References

- **GCNS:** Gaia Collaboration (Smart et al.) 2021, *A&A* 649, A6; VizieR `J/A+A/649/A6`; GAVO `https://dc.g-vo.org/browse/gcns`; ESA `https://www.cosmos.esa.int/web/gaia/edr3-gcns`. 331,312 sources to 100 pc (= 326 ly); ~95% complete to ~M7–M8; Bayesian distances; no spectral types.
- **Distances from parallax:** Bailer-Jones, "Estimating distances from parallaxes" (2015 *PASP* 127; 2018 *AJ* 156, 58) — inverting parallax is biased for noisy parallaxes; use Bayesian distances.
- **Substellar completeness:** Golovin et al. 2023 *A&A* 670, A19 (CNS5); Best et al. 2021; Kirkpatrick et al. 2021.
- **SIMBAD:** Wenger et al. 2000, *A&AS* 143, 9 — bibliographic database, "not a catalogue."
- **Current build:** this repo's `docs/star-databases.md`, menu options 50 (`query_star_systems_csv`) and 51 (`export_star_systems_csv`).
