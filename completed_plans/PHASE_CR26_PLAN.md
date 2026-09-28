# PHASE CR-26 — exclusion per-star wind model: supplied → measured → X-ray → non-detection → class-default tier ladder

**Status: COMPLETE — FULFILLED 2026-09-28 (WB MSG 317, Greg signed); committed + pushed to `main` as `a2a0ae0` (MSG 318).** Re-gate history: RED (MSG 311) → fixed; RG8/RG9 (MSG 315) → fixed; GREEN (MSG 317).
- Build log: §12b. Suite 3767 passed / 110 skipped / 0 failures (after the re-gate fixes RG1–RG9); `test_cr26_live.py` 7 passed / 1 skipped.
- Build-complete report posted as MSG 308; WB acknowledged in MSG 309 (the re-gate runs in a fresh WB session).
- **Git-held, and the working tree must stay unchanged until GREEN** (WB MSG 309). Nothing is committed.

**Contract:** WB `design-lab/star-system-analysis/spaceapp-change-request-CR26-xray-tier-wind-model.md`, cited as `§26.N` and `A0–A8`. **The spec is the contract.** The channel rulings fill its gaps, and the re-gate checks them.

**Out of scope:**
- CR-24;
- the FROZEN `compute_exclusion_boundary` body (never edited);
- any change to a WB data file.

---

## 0. Ground truth (verified 2026-09-26)

- **Data files.** The six WB CSVs match the spec md5s. `M0–M3.5` uses U+2013 throughout. Row counts:

  | File | Rows |
  |---|---|
  | measured | 36 |
  | class states | 17 |
  | fork-8 | 5 |
  | fork-9 | 455 (5 × 91; 3.50–8.00 in steps of 0.05) |
  | subtype radii | 40 |
  | half-width | 601 (2.00–8.00 in steps of 0.01) |

- **HEASARC TAP.** `https://heasarc.gsfc.nasa.gov/xamin/vo/tap`, via pyvo `run_sync`. The tables and columns follow W4's `w4_xmatch.py`:
  - `rass2rxs`: `ra, dec, count_rate, onerxs_count_rate, exposure, time`
  - `erass1main`: `ra, dec, b1_flux, b1_count_rate, b1_exposure, time`
  - `xmmssc`: `ra, dec, ep_1_flux, ep_2_flux, ep_3_flux, ep_det_ml, sum_flag, time, end_time`

  A cold query takes about 2 s.

- **How the code chooses a wind today.**
  - **Wall Ṁ:** `exclusion_wall.resolve_wind_inputs` (`core/exclusion_wall.py:542`) picks the supplied rate, else the `wind_class` row, else none. The CR-22 CP4 rule lets `--wind-speed` override a class-default Wood source (`:577`).
  - **Standoff Ṁ:** the FROZEN generator (`core/exclusion_boundary.py:106-118`) picks the supplied rate, else `_WIND_STATE_MAP[ws]`. At γ>0 with neither, it errors. At γ=0, `wind_term = 1.0` (`:125`).
  - **MS bin:** `_ms_wind` (`:237`), with its colour taken from `detection._sp_letter` (case-insensitive).
  - **Composition:** `compose_exclusion_system` (`core/exclusion_system.py:291`) runs these steps in order:
    1. `_classify_component` (`:252`, called at `:319`);
    2. `_component_rex` (called at `:357`);
    3. the wall loop;
    4. the zones;
    5. `_combined_wind_wall` (`:235`);
    6. the point mass (`:425-436`).
  - **Callers:** only `query.py` and `core/exclusion_{boundary,system}.py` call the four touched functions.

- **Identity and astrometry.**
  - `compute_simbad_lookup` returns J2000 ra/dec, `plx_value` and designations. It returns no PM, no parallax error and no G.
  - On `exclusion-boundary --star`, an MS star exits with "Parallax not available" before any wind code runs.
  - On `exclusion-system --star`, the component dicts carry no ra/dec, no parallax, no Gaia id and no **resolved** `main_id`:
    - component A gets the head's `main_id` (`* alf Cen`, `*  70 Oph`);
    - component B gets the candidate string (`HD 1326 B` versus SIMBAD's `HD   1326B`).

- **The `gcns_stars` table.**
  - 332,571 rows; maximum `dist_pc` 119.31.
  - No ra/dec index. A 0.1° box scan takes about 0.10 s.
  - 1,259 `missing_10mas` rows. Each has a J2000 position, NULL G, PM, parallax error and source_id, and a padded `star_name` (`*  10 Tau`).
  - 431 main rows have a NULL G.
  - 12 missing rows sit within 2″ of a main row at J2000. A name match settles 4 of them.
  - The table is **never auto-seeded**, so the harness DBs have it empty.

- **Plumbing.**
  - `shared._bounded_call(retries=N)` makes N total attempts. `fatal=` re-raises immediately.
  - `catalog_cache._is_empty` treats any dict with an empty `rows` list as empty, so such a dict is never cached.
  - `catalog.vizier_query` is only socket-timeout bounded and flattens every error. It is not CR-19-compliant.
  - `catalog.gaia_tap` is CR-19-bounded, and `SPACE_APP_GAIA_FORCE_UNREACHABLE` sits inside it.
  - There is no runtime md5 check anywhere in `core/` today. CR-26 adds the first one.

## R. Rulings index (channel MSG 285–302). Each is folded into the body at the § given.

| Ruling | Substance | Body |
|---|---|---|
| Q1 | At γ>0 the tier rate feeds the standoff. An in-scope star with no `--wind-state` no longer errors. An upper-bound rate gets a note. Non-ladder tiers keep today's input. `none` still errors. | §3c, §5d |
| Q2 | A component without its own parallax borrows the primary's, with a note. No usable parallax at all → `xray.status: not_run` + a note, the class default, and no `not_authoritative`. | §4.1, §2h |
| Q3 | A target beyond GCNS reach (by its distance) → blend not run + a note; no flag. | §4.5 |
| Q4 + G2 | `tiers` lists the in-scope tiers below the used one, with their statuses. Each entry carries its own `log_fx` and `flags`, and the partial-failure rule applies per entry. | §2h |
| Q5 | `sp` is an alias of `sp_type`. | §5c |
| R1 | TIC is `IV/39/tic82` at 5″, J2000. A non-Gaia star uses SIMBAD's J2000 position. | §4.4 |
| R2 / G13 | Dedup: main-vs-main by position + \|ΔG\| ≤ 0.5, or by name. Missing-vs-main by name, or by the same SIMBAD `main_id`. | §4.5 |
| R3 | Partner mass from the mass chain, else 2 M☉ + a note. | §4.5 |
| R4 | The partner family is GCNS + the partner SIMBAD lookups. An empty table counts as failed. The partial case is defined. | §4.5 |
| R5 | An evolved measured host: v 400 forced; t_phase and medium from its evolved row. | §3a |
| R6 | A lookup that answered with no PM → zero PM + a note. | §4.1 |
| R7 | A `wind_model` skeleton on non-ladder results. | §2h |
| R8 | §26.8 text: no content shortened. | §2i |
| R9 / G6 | One hook per resolve family, incl. the rung-list hook. Every rung is queried. | §4.2, §4.8 |
| R10 | Tiers 2–5: v 400 is forced even over `--wind-speed` (+ a note). Other tiers keep the CP4 rule. | §3a |
| R11 / H8 | The γ>0 point mass sums each member's standoff-input rate (a `wind_state` member contributes its legacy-map rate). At γ=0 it is byte-identical. | §5d |
| R12 | `radius_pair_ambiguous` uses a SIMBAD 5″ cone (stars only) + a GCNS neighbour. | §4.4 |
| G1 | A `missing_10mas` partner takes its parallax ± error and PM from SIMBAD, propagated from J2000. α Cen passes (M). | §4.5 |
| G3 | XMM G: Gaia → SIMBAD → none (the guard fails). The floor is tested on the system F_X. | §2d, §4.2 |
| G4 | `measured_system_edges` | §5d |
| G5 | The `limit_survey` enum; `regime` on every relation construction; `wall_band_wind_routes`. | §2b, §3b, §4.3 |
| G7 | Which disclosures each tier carries. | §2i |
| G8 | mass + `wind_state=` with no class → `legacy_row`. | §5c |
| G9 | A demoted XMM match reads `detection` in `rungs`. | §4.2 |
| G10 | `wind_class=quiet/solar/active` is a state selector. Any other `wind_class` row → `noncoronal_row` + a bypass note. | §2f, §5c |
| G11 | The supplied tier keeps the CR-25 identity row (byte-identical). | §3a |
| G12 | A letterless head is matched on its A candidate + a note. The ladder runs at the head's position. | §5b |
| G14 | Exit 2 outside `log_fx` ∈ [0, 12], radius ≤ 2000, prot ≤ 1e5. | §5a, §5c |
| H1 | A failed identity lookup → match the measured table on the head/candidate string + a note. `not_authoritative` **only when that string match finds no row**. Own hook. | §4.7 |
| H2 | `blend_mixed_class` compares class bins. A partner with no class is not "mixed". | §2d |
| H3 | An in-scope star whose tier is `none`, at γ>0: today's standoff input. A `--wind-state` feeds the standoff through the legacy map (with the H3 note); without one, it errors. | §3c |
| H4 | `--component main_id=` with a measured hit: the row's `sp_type_simbad` supplies the class **only if** the caller gave no `class=`/`sp=`. A caller's class wins, with a note if it disagrees. No row → G8. | §5c |
| H5 | `below_fit_range` on `upper_limit_only` with a limit < 4.03 (disclosure only). | §2e |
| H6 | A failed SIMBAD-G fetch while XMM is the candidate → the XMM rung is `failed`. Only an answered "no G" demotes it. The hook is named in the build report. | §4.1, §4.2 |
| H7 | Am-type strings (`kA5hF0mF2`) read as their first upper-case letter (A): out of scope → `noncoronal_row` on the `a_dwarf` row + a note that the lower-case Am prefix was skipped. This is the one deliberate value change to a non-coronal output. | §2a, §5b |
| J1 | A field star gets no area share; the system F_X is taken over the target + real partners only. | §2d |
| J2 | `hot` binds at tier 5 → o_hot with `wind_class: o_hot`. Under a data tier it is an unused flag, and the label is the otherwise-selected state. | §2f |
| J3 | The (S) SIMBAD parent counts only if it is multiple-star-family (`**`, `SB*`, `EB*`, `El*`, candidates); not a cluster, association or group. | §4.5 |
| K1 (MSG 302) | On a no-network path (`--component`, `--spectral-type`), the lower X-ray tiers in `tiers` read `not_reachable`. No new enum value. | §2h |
| K2 (MSG 302) | An F/G/K star with no subtype digit: each catalog radius is checked at 0.3 dex against the class median (rejections listed in `rejected`); `subtype_median_rsun: null`; a supplied radius gets the > 0.3-dex note against the same class median. | §2g |
| K3 (MSG 302) | On the H1 degraded path only, the string fallback also tries the candidate with the space before a trailing capital A–D removed (`HD 1326 B` → `HD 1326B`). | §4.7 |

---

## 1. Vendored data and the loader — `data/cr26/` + `core/stellar_wind_tables.py` (new)

- **Vendoring.** `cp` the six CSVs byte-identical into `data/cr26/` and commit them.
- **Line endings (round-4 HIGH).** `.gitattributes` has `* text=auto` and `*.csv text`, so a native-Windows checkout would get CRLF copies and fail the md5 check. **Append** `data/cr26/*.csv -text` to `.gitattributes`, after the `*.csv text` line (`:8`; the last matching line wins), **before** the files are `git add`ed, in the same commit. Tests assert that `git check-attr text data/cr26/<file>` reads `unset` and that the vendored bytes contain no `\r` (the WB files have none).
- **Pinned md5s.** `CR26_MD5` holds the spec's six md5s. The data directory defaults to `data/cr26/`; `SPACE_APP_CR26_DATA_DIR` overrides it.
- **Loading.** `load_cr26_tables()` is memoised, keyed on the resolved directory; `clear_cr26_cache()` resets it. It reads bytes, checks the md5 **before parsing**, then parses as utf-8 `csv`.
- **Failure.** A mismatched or missing file raises `Cr26DataError`, which surfaces as a curated error (exit 1). The model never computes from an unverified table.
  - Where it is caught: `cmd_exclusion_boundary` and `cmd_exclusion_system` in `query.py` catch `Cr26DataError` → `{"error": …}` + exit 1. `compute_exclusion_system`'s existing curated-error return also catches it, so core callers get the same dict (L-10).
- **Structural self-check.** The loader also checks:
  - the row counts;
  - the five class bins, with the en dash;
  - that the fork-9 grid is contiguous;
  - that `measured_rule == point_combined` exactly when `wood_scope == combined_unsplit`.
- **Parsed structures.**
  - `MEASURED[collapsed main_id]`, with a duplicate-key check;
  - `CLASS_STATES[(bin, state)]`, incl. the M4+ modes;
  - `FORK8[bin]`;
  - `FORK9[bin]`, a dict keyed by the integer grid index `round(limit × 20)` (70–160), read by §2e's `floor(limit × 20 + 1e-9)` (one keying — L-9);
  - `SUBTYPE_R[(letter, int)]`;
  - `HW[int(round(x*100))]`.
- **Empty cells** parse to `None`.

## 2. The pure model — `core/stellar_wind.py` (new; no network, no I/O beyond §1, no Qt)

The model maps a `StarWindInputs` to a `WindModel`.

**`StarWindInputs` holds:**
- identity: `sp_type`, `main_id`, domain, the subdwarf flag;
- supplied inputs: rate, `log_fx`, `log_fx_limit`, radius, `prot_days`, `wind_state`, `wind_class`, and the active-otype match;
- lookup results: the ladder, the survey limit, the radius candidates, the partners;
- the status of each resolve family.

**Overflow guard:** every power of ten goes through `_pow10`, which returns a curated error instead of raising.

### 2a. Parsing, scope, bins (§26.1 scope, §26.3.5, §26.5)
- **`parse_sp(sp)` → `(letter, subtype|None, is_subdwarf)`.**
  - Strip one leading sd-family or dwarf prefix. Prefixes are matched longest first over `esd, usd, d/sd, s/sd, (sd), sd:, sd, d`. This list is a new **named constant in `core.shared`**, `_SP_DWARF_SUBDWARF_PREFIXES`, beside `_SP_CLASS_PREFIXES`, so there is still one parser and no local prefix map. It is the sd-family plus `d` subset of `_SP_CLASS_PREFIXES`, and a test asserts the subset. The spec's minimum is `esd, usd, sd, d`; the other forms are its spelling variants. `k`, `h` and `kn` are excluded because they are Am-type metallic-line prefixes, not dwarf markers (H7).
  - The letter is the first **upper-case** `[OBAFGKM]`. The subtype is the number directly after it, decimals allowed.
  - A range takes its first type. Anything after the subtype is ignored.
  - Test pins:

    | Input | Result |
    |---|---|
    | `dM6` | M6 |
    | `K2+V` | K2 |
    | `M4.0Ve` | M4 |
    | `K7-M0` | K7 |
    | `F1-F2V` | F1 |
    | `sdM1` | M1, subdwarf |
    | `esdK7` | K7, subdwarf |
    | `M` / `M V` | (M, None) |
    | `kA5hF0mF2` | A (H7) |
    | `A0mA1` | A |

- **Scope.** A star is in scope when its domain is `main_sequence` **and** its `parse_sp` letter is F, G, K or M. The measured tier also applies on the `evolved` domain when a measured row matches. `parse_sp` is the **only** letter source for CR-26 scope.
- **H7 (Am-type strings).** An MS star whose parse letter is outside FGKM, but whose CR-25 colour letter is inside it, takes `noncoronal_row` on the row for its parse letter (A → `a_dwarf`). It gets the note "the lower-case Am/peculiarity prefix was skipped; read as <letter>".
- **Class bins.** F, G, K, `M0–M3.5` (M below 4.0) and `M4+` (M at 4.0 or above). An M star with no subtype gets no bin (`None`).
- **Radii.** `subtype_median` reads `SUBTYPE_R` at the floored subtype. The class median comes from the file.

### 2b. Relation, `hw`, regimes, widening (§26.3.6–.8)
- **Relation.** `per_area_log(x) = 0.245 + 0.592·(x − 5)`, and Ṁ[Ṁ⊙] = 10^per_area_log × R², with Ṁ⊙ = 2e-14.
- **Half-width.** `hw(x)` is read at the nearest 0.01 grid point, clamped to [2.00, 8.00].
- **Regime.** Quiet below 4.85; mid from 4.85 up to 6.0; active at 6.0 and above.
  - The `regime` field is set on every relation construction (G5). For `upper_limit_only` it is evaluated at the limit. It is null otherwise.
- **Regime bands.**

  | Regime | Band (dex) |
  |---|---|
  | quiet | −0.50 / +0.30 |
  | mid | −√(0.85²+hw²) / +√(1.20²+hw²) |
  | active | ±√(1.20²+hw²), plus `active_bimodal` |

- **Widening**, applied in the §26.3.8 table order:
  1. `fast_rotator` (a supplied prot of 0.5 d or less) or `above_fit_range` (X-ray tier only, x > 7.2 strictly): hi = max(hi, √(2.0²+hw²)).
  2. `extrapolated` f_dwarf: lo −= 0.63.
  3. `extrapolated` late_m (M, subtype 4.5 or later): both edges widened in quadrature by 0.2.

  `extrapolation_class` records which applied. Widening covers the relation tiers only, evaluated at the point's F_X; the measured tier is never widened.
- **`below_fit_range`.** Set when the point's F_X is below 4.03 on any relation tier. It triggers no widening. It is also set on an `upper_limit_only` result whose limit is below 4.03 (H5).
- **Blends.** For a blend, every F_X-conditioned flag and band uses the system F_X.
- **`regime_edge` note.** Only when `band_construction` is `regime`, and |x−4.85| or |x−6.0| is under 0.15. The note gives the neighbouring regime's band. Pins: F active 5.9449 and G active 6.1355 both carry it.

### 2c. Measured tier (§26.2)
- **Match.** The whitespace-collapsed `main_id` must equal the row key exactly.
- **Rules**, by `measured_rule`:

  | Rule | Value and outputs |
  |---|---|
  | `point` | Wood's value. **No area share** (36 Oph 8.5 / 6.5; ξ Boo 0.5 / 4.5). |
  | `point_combined` | W × R_i² / ΣR² over the row group, using Wood's radii. Flag `measured_combined_split`. |
  | `upper_limit` | The limit. `mass_loss_upper_limit` set; flag `measured_upper_limit`. |
  | `point_span_both` | Band [min(W, K_c), max(W, K_c)], where `K_c = K_system × W_c / ΣW_system` for a `combined_system` scope. `band_construction: measured_span`. |
  | `point_method_conflict` | Flag `method_conflict`. |
  | `point_method_mixed_system_edge` | Flag `method_mixed`. `wind_model.measured.system_upper_edge_mdot_sun` set, plus the boundary note. |

- **Null fields.** `per_area_log`, `log_fx`, `regime` and `state` are all null on a measured result.
- **T12.** On an `upper_limit` row, `tiers.xray` gets a below/above-the-limit comparison note.

### 2d. X-ray tier (§26.3)
- **Blend arithmetic.** System F_X = f·d² / Σ R² over the target and its partners. Each star gets relation(system F_X) × its own R².
- **Blend flags.**

  | Flag | When |
  |---|---|
  | `blended_source` | At least one partner (the partners are named). |
  | `blend_mixed_class` | A partner's **class bin** differs from the target's. A partner with no class does not count (H2). |
  | `blend_partner_by_designation` | Test (S) alone qualified the partner. |
  | `blend_partner_radius_unchecked` | A partner with no class used an unchecked catalog radius. |
  | `blend_partner_radius_missing` | A partner has no radius; the target keeps its own-area F_X. |
  | `field_star_in_beam` | A star in the beam failed (P), (M) and (S). It is named and gets **no area share**. The system F_X is taken over the target plus its real partners only; with no real partners, over the target's own area (J1, MSG 298). |
  | `wd_partner_in_beam` | A partner with `wd_prob` ≥ 0.5, or SIMBAD otype `WD*`. |
  | `xmm_rung` | The flux came from the XMM rung. |

- **F_X fields.** `log_fx` is the own-area F_X. `system_log_fx` is added when the source is blended.
- **Conversion constants:** 1RXS 6e-12; 2RXS −0.063 dex; eRASS1 +0.052 dex; XMM +0.087 dex.
- **`xmm_guard(g, sum_flag, det_ml, logfx_eval)`** checks the guard first, then the floor:
  1. `xmm_guard_demoted` when G is None or ≤ 7, `sum_flag` > 1, or `det_ML` < 15.
  2. Otherwise `xmm_floor_demoted` when `logfx_eval` < 3.5. `logfx_eval` is the system F_X on a blend (G3b).
  3. Otherwise `kept`.

### 2e. Non-detection (§26.4)
- **Row lookup.** Use the fork-9 row at the largest grid value not above the limit. A limit below 3.50 gives `upper_limit_only`; a limit above 8.00 uses the 8.00 row.
- **`defined`** status:
  - point = 10^point × R²;
  - `log_fx` = `conditional_logFX`, with `log_fx_kind: conditional_below_limit`;
  - `band_construction: truncated_mixture`, widened at `conditional_logFX`;
  - `below_fit_range` when `conditional_logFX` < 4.03;
  - flag `xray_upper_limit`.
- **`upper_limit_only`** status:
  - value = the line at the limit × R²;
  - `mass_loss_upper_limit` set, `log_fx_kind: survey_limit`, `log_fx` = the limit;
  - no band;
  - flag `xray_upper_limit`, plus `below_fit_range` when the limit is below 4.03 (H5).
- **M4+ bimodality.** `bimodal_class` **and the two `modes`** (Ṁ = relation(mode F_X) × R²) are emitted only when the limit is ≥ 6.2633.
- **Floor reading, float-safe:** the grid index is `floor(limit × 20 + 1e-9)`, so a computed 4.6999999 reads the 4.70 row. Pinned by a test with a limit exactly on a grid value.
- **`limit_survey`** is one of RASS, eRASS1 or supplied.
- **No class bin** → this tier is not reachable.

### 2f. Class default (§26.5)
- **State precedence:**
  1. An in-scope `wind_class` of quiet, solar or active (G10; it beats `wind_state`).
  2. `wind_state`.
  3. A CR-25 active-otype match on an MS K/M star (`otype_auto`).
  4. Otherwise typical (`class_default`).

  Steps 1 and 2 are recorded as `manual`.
- **`hot`** binds at **tier 5 only**: `noncoronal_row` on the o_hot row, state null, `wind_class: o_hot` (J2, MSG 298). When a data tier sets the rate, `hot` is an unused `--wind-state` (note + stderr), and the label is the state the star would otherwise get.
- **Any other `wind_class` row** → `noncoronal_row` on that row, with the note "the caller's wind_class bypassed the CR-26 ladder".
- **Rate.** Ṁ = 10^(the state's `point_log_Mdot_per_A`, 4 dp, from the class-states file) × R².
- **Output fields (G5).** `log_fx` = the state's F_X, `log_fx_kind: class_state`, `state` = the selected state. `regime` = the regime of the state's F_X on every class state, the typical `class_mixture` included (G5: every relation construction; only the `regime_edge` note is regime-band-only).
- **Band.**
  - Typical: fork-8 (`class_mixture`).
  - Quiet or active: the file's band (`regime`).
  - Then widening, evaluated at the state's F_X.
- **Flags.**
  - G quiet: `marginal_state` + `below_fit_range`.
  - M4+: `bimodal_class` + `modes[{name, weight, log_fx, mass_loss_msun_yr}]`.
  - A state F_X of 6.0 or above: `active_bimodal`.
- **`wind_class` label.** Every in-scope star is labelled quiet, solar or active, whatever tier set the rate. An evolved measured host keeps its CR-25 label.
- **`subtype_unknown`** (an M star with no digit):
  - `tiers.class_default` and `tiers.xray_nondetection` are `not_reachable`.
  - The X-ray tier still runs, with an unchecked catalog radius (`radius_unchecked`) and **no** late-M widening.
  - With no usable X-ray value, `mass_loss_tier` is `none`, flagged `subtype_unknown` (+ `not_authoritative` if a lookup failed). "No usable value" covers: no detection; a limit only; **a detection but no radius (neither supplied nor catalog)**; a failed lookup. A supplied `--radius-rsun` / `radius_rsun=` with a detection or `--log-fx` is usable (§26.5).
  - `--wind-state` does not set the rate. The H3 note says so: "`--wind-state` did not set the wind rate (the wall is null); it still feeds the γ > 0 standoff through the legacy map, as before."
- **No spectral type at all** → no tier, and a null wall.

### 2g. Radius selection (§26.3.5)
- **Chain order:**
  1. supplied (with a note if more than 0.3 dex from the median);
  2. TIC, then `gaia_flame`, then `gaia_gspphot` — each accepted only within 0.3 dex of the subtype median, otherwise listed in `rejected`;
  3. `subtype_median`, or `subtype_median_replaced_outlier` when a catalog value was rejected;
  4. `class_median`.
- **Unchecked radii.** An M star with no subtype, or a partner with no class, takes the first catalog value unchecked (`radius_unchecked`, or `blend_partner_radius_unchecked` for a partner).
- **F/G/K with no subtype digit** (`K`, `G V`, a partner typed `K`) **(K2, MSG 302)**: each catalog value is checked at 0.3 dex against the **class median** (F 1.4100 / G 0.9760 / K 0.7085); a rejected value is listed in `rejected`. `subtype_median_rsun: null`, and the chain falls back to `class_median`. No new flag. A supplied radius on such a star gets the > 0.3-dex off-median note against the same class median.
- **`radius_pair_ambiguous`** requires both of these:
  - the radius came from TIC, `gaia_flame` or `gaia_gspphot`; **and**
  - one of: another star in the SIMBAD 5″ cone (R12); a GCNS neighbour within 5″; a lettered `main_id` — either a space-separated capital A–D at the end (`* 61 Cyg B`, `GJ 1245 B`), or a capital A–D directly after the catalogue number (`HD 156384C`). Both forms are pinned.

  Pins: α Cen A → no; 61 Cyg B → yes; 70 Oph A → yes.
- **Status.** `status` records each family's failures. A subdwarf gets a note.

### 2h. Assembly — `resolve_wind_model(inputs, *, state_sel) → WindModel`
- **Precedence:** supplied → measured → xray → xray_nondetection → class_default → noncoronal_row. The caller sets the other three states: `object_preset`, `legacy_row` and `none`.
- **What the model returns (import direction, M-5).** `resolve_wind_model` returns the tier, the label and the CR-26 rates only, computed from the §1 tables. It never imports `exclusion_wall`, `exclusion_boundary` or `detection`.
  - The non-coronal row rate (G10, o_hot, `noncoronal_row`) is filled by `exclusion_wall.resolve_wind_inputs`, which owns `_WIND_ROWS`. The legacy-map `standoff_rate` is filled by `compute_two_layer_boundary` and by compose (R11), because `_WIND_STATE_MAP` lives in `exclusion_boundary.py:42`, which imports `exclusion_wall` (`:30`) and so cannot be imported back (round-5 L-2). Every tier's `standoff_rate` has an owner: the model for tiers 2–5, and today's frozen arguments for the rest.
  - The CR-25 colour letter that H7 needs is passed in as a `StarWindInputs` field (`cr25_letter`), computed from `detection._sp_letter` by whoever builds the inputs: the orchestrator and `deterministic_inputs`. Both live in `core/xray_catalog.py` (not in the `stellar_wind` leaf) and import `detection` lazily.
- **`ladder_outcome(rungs, astrom_status, limit_status, g_status)`** is pure and table-tested:
  - **Flux.** The first rung that answered with a kept detection supplies the flux.
    - A rung above it that failed → the value stands, flagged `not_authoritative`.
    - A rung below it that failed → recorded in `rungs` only.
  - **XMM demotion.** A demoted XMM candidate sends the star down the non-detection path. But a failed SIMBAD-G fetch for that candidate makes the XMM rung `failed` instead (H6).
  - **No detection.** Any failure → the class default + `not_authoritative`, never the non-detection path. Failures here: a failed rung, the survey-limit query, the astrometry lookup, or the G fetch.
  - **`xray.status`.**
    - `ok` when every query the result depends on answered; otherwise the first failure's code.
    - `not_run` in five cases: no identity; a supplied `log_fx`/`log_fx_limit`; the star is out of scope; no usable distance; network disabled (`allow_network=False` — the `--component` and `--spectral-type` paths, and the conftest default for in-process `--star` tests). The last case gives the class default (or the measured tier on a table hit) with **no** `not_authoritative`, and a note.
- **`tiers`** (Q4 + G2) lists the in-scope tiers below the used one.
  - Entry shape: `{mass_loss_msun_yr, mass_loss_band_msun_yr, used: false, status, log_fx, flags}`.
  - Statuses:

    | Status | When |
    |---|---|
    | `not_reachable` | No measured row; `xray_nondetection` when a detection exists; `xray` when none does; `class_default` under `subtype_unknown`; and **(K1, MSG 302)** `xray` / `xray_nondetection` on a no-network path (`--component`, `--spectral-type`, or `allow_network=False`) when the caller supplied no `log_fx` / `log_fx_limit` for them. |
    | `failed` | A failure that leaves the entry no value. |
    | `upper_limit_only` | The entry is a non-detection bound: `mass_loss_msun_yr` = the bound, band null (e.g. a 107 Psc-type `tiers.xray_nondetection` under a supplied or measured star). |
    | `ok` | The entry has a value. If a failure could have changed that value, the entry's own `flags` carry `not_authoritative`. The top level carries `not_authoritative` only when the used value depended on the failure. |
  - `class_default` is evaluated at the selected state.
  - An evolved measured host lists only `noncoronal_row`. So does a supplied-rate star outside the CR-26 scope (a `supplied` result, not an R7 one).
- **`wind_model` keys** (§26.7, exactly):
  - `model`, `per_area_log`, `log_fx`, `log_fx_kind`, `regime`, `band_construction`, `class_bin`;
  - `state` — null unless the class default set the rate;
  - `flags`, `extrapolation_class`, `modes`;
  - `xray` = `{status, rung, detection, source_id, epoch, separation_arcsec, flux_fit_scale, log_fx, system_log_fx, limit_log_fx, limit_survey, erass1_footprint, blended_source[], xmm_guard?, rungs[]}`;
  - `radius`, `measured`, `tiers`, `notes`.

  `xray` and `radius` always describe the ladder run. After an astrometry failure, `rungs` reads `not_queried` for all three. A schema test checks every key and every enum value on every path.
- **R7 skeleton** (non-ladder results):
  - `model: "cr26"`, `xray.status: not_run`, `flags: []`, null bands, `tiers: {}`;
  - `notes` carries the ignored-input entries and CR-25's `hot` mismatch note;
  - no disclosures.
- **Top-level fields.**
  - `mass_loss_msun_yr` (the point, or the bound) and `mass_loss_tier`. When neither `wind_model` nor `mass_loss_tier` is passed to `compute_two_layer_boundary`, **it derives the tier itself**, in this order (M-7, round-5 MED-1 / L-4): `object_preset` when `wind_class_provenance == "object_preset"` (the `--object` path passes a preset rate in `mass_loss_msun_yr`, so this check must come first; `query.py`'s `--object` branch also passes `mass_loss_tier="object_preset"` explicitly); else `supplied` with a rate; else `legacy_row` with a `wind_state`, or when `resolve_wind_inputs` took a class-row rate (e.g. a direct `compute_two_layer_boundary(sp_type="G2V")` call: the legacy wind-class row, provenance `class_default`, as today); else `none`. `query.py` passes nothing extra on the bare-mass path, so `test_query_exclusion_system.py:176`'s CLI-vs-core equality holds.
  - `mass_loss_provenance`:

    | Tier | Provenance |
    |---|---|
    | measured, xray, xray_nondetection | the tier name |
    | tier 5 | `class_default` |
    | supplied | `supplied` |
    | `noncoronal_row`, `legacy_row`, `object_preset`, `none` (`tier=None` paths) | today's value, byte-identical (`class_default`, `supplied` or `none`, per `resolve_wind_inputs`) |
  - `mass_loss_band_msun_yr`, `mass_loss_band_dex`, `mass_loss_upper_limit`.
  - `wind_class` (the label).
  - `standoff_rate` (internal only).
- **Notes** (fixed strings, each tested):
  - unused inputs: `wind_state` / `wind_class`; the G10 bypass; an ignored `--mass-loss-source`; an ignored `--wind-speed` (R10); ignored CR-26 inputs;
  - T12; 61 Cyg's system edge;
  - Q2 (borrowed parallax / no distance); Q3 (beyond GCNS); R3 (2 M☉); R4, G13 and H1 (a lookup failed); R6 (zero PM);
  - G12 (head read as A); H3 (unused `--wind-state` still feeds the standoff); H4 (caller class disagrees with the row); H7 (Am prefix skipped);
  - a subdwarf radius; a supplied radius off the median;
  - Q1 (the γ>0 standoff is an upper bound); R11 (the γ>0 point mass is an upper bound);
  - `regime_edge`.

### 2i. Disclosures (§26.8; R8, G7)
- **Text.** `DISCLOSURES` holds items 1–15 and the measured set **verbatim** from the spec. Only the cross-references and ruling tags are dropped; long items may be split into sentences.
- **Selection on tiers 3–5.**
  - Always: items 1 (worded by tier), 2, 3, 4, 5, 6, 7, 9 and 10.
  - Conditional:

    | Item | When |
    |---|---|
    | 8 | G quiet |
    | 11 | per flag |
    | 12 | `xmm_rung` |
    | 13 | `below_fit_range` |
    | 14 | the state came from `otype_auto` |
    | — | (item 15 is not a tier-3–5 item; see below) |
- **Item 15** goes on **every member, whatever its tier**, of a zone whose `combined_wind_wall_band_wind_au` is **non-null**, and on no one else.
- **Measured set.**
  - Always: Wood's ×2 systematic and the ISM note.
  - Combined astrosphere: on `point_combined`.
  - Method text: with the method flags.
  - Kislyakova text: on `point_span_both` / `method_mixed`.
  - v 400: on evolved hosts.
- **Test.** `tests/data/cr26_spec_disclosures.txt` holds the spec's §26.8 text, copied in. A normaliser strips the `§` references and ruling tags. Every number and qualifier token of every item must appear in the emitted text.

## 3. Wall wiring — `core/exclusion_wall.py` + `core/exclusion_boundary.py`

### 3a. `resolve_wind_inputs(..., tier=None, identity_row=None)` — additive
- **Tiers measured / xray / xray_nondetection / class_default:**
  - wdot = the tier rate; `prov.mass_loss` = the tier name;
  - source `astrosphere_wood`, with `prov.mass_loss_source = class_default`;
  - **v = 400 forced even over a supplied `wind_speed`**, recorded as `astrosphere_wood_forced` (R10);
  - a supplied `mass_loss_source` is ignored, with a note;
  - t_phase and the medium come from `wind_row_for(label)` (v 400, t_phase None), or from the evolved row for an evolved measured host (R5).
- **Tier `supplied`:** today's code path, with `identity_row` = **CR-25's final `classify_wind` `wind_class`**, i.e. after `wind_state`, otype and any explicit `wind_class` are applied, not just the colour default. For a plain F dwarf that is `f_dwarf` (v 500). This is byte-identical (G11).
- **`tier=None`** (`object_preset` / `legacy_row` / `noncoronal_row` / `none`): today's code path, byte-identical.

### 3b. Wind-band walls — `ew.wind_band_walls(inputs, wm, standoff)`
- **`wall_band_wind_au`** = [lo edge of `compute_wall` at Ṁ·10^lo, hi edge of `compute_wall` at Ṁ·10^hi]. Both use the same inputs.
- **`wall_band_wind_routes`** = [lo, hi] routes, emitted only when they differ.
- **`wall_band_wind_exceeds_standoff`** = hi > the standoff; null when there is no standoff.
- **No band, or an upper bound:** both fields are null.
- **`wall_is_upper_bound`** is always a bool.

### 3c. `compute_two_layer_boundary(..., wind_model=None, mass_loss_tier=None)` — additive
- **At γ=0** the frozen generator is called with exactly today's arguments, so the standoff and its error paths are byte-identical.
- **At γ>0:**
  - Tiers 2–5: `mass_loss_msun_yr = wm.standoff_rate` (the point, or the bound) with `wind_state=None`. An upper-bound rate gets the Q1 note.
  - Every other tier, including an in-scope star whose tier is `none`: today's arguments (H3). A `--wind-state` feeds the standoff through the legacy map, with the H3 note; with no wind input, it errors as today.
- **Validation placement (M-6, round-5 MED-2).** The pre-orchestrator checks mirror the frozen generator's **order and conditions** exactly (`exclusion_boundary.py:104-118`): alpha/beta/gamma < 0, dial ≤ 0, calibration ≤ 0, β ≠ 0 with L ≤ 0; then `mass_loss_msun_yr ≤ 0` ("`--mass-loss-msun-yr must be > 0.`"); then an unknown `wind_state` **only when no rate is supplied**, with the message verbatim (`"Unknown --wind-state '<x>'…"`). They run **after domain classification and only on the MS / evolved-with-mass branch**, i.e. exactly where the frozen generator runs them today. So a supplied rate + a bad state stays exit 0, and a windless or unmodeled body keeps today's exit 0.
  - On `exclusion-boundary` the CLI's `--wind-state` has argparse `choices` (`query.py:3391`), so a bad string exits 2 before any of this; the `wind_state` check is reachable only through direct core calls and is tested in-process.
  - **γ>0 compose regression guard.** At γ>0 a tier-2–5 component calls the frozen generator with `wind_state=None`, so a component's own bad `wind_state=` would no longer be rejected there. Compose therefore validates each MS / evolved-with-mass component's own `wind_state` before the model, **at any γ**, under the frozen condition (only when the component supplies no rate), so today's rejection is preserved rather than lost. Pinned by the existing γ=0 test (`test_cr25.py:1236-1237`) plus a new γ>0 variant.
- **Direct `compute_two_layer_boundary` calls** with no `wind_model` take the `tier=None` path, which is today's behaviour, byte-identical. That keeps `test_query_exclusion_system.py:176`'s bare-mass equality and the direct-call tests green.
- **`compose_exclusion_system` always runs the model (M-1).** An in-scope component without `wind_inputs` gets `deterministic_inputs(c)` (§5d.2), so `--component` dicts, which arrive plain, get CR-26. Direct `compose` calls on in-scope plain dicts therefore change value; the affected tests are listed in §7.14. The asymmetry with bare `compute_two_layer_boundary` calls is documented in `docs/integration.md`.
- **Output.** Every §26.7 field plus `wind_model`; without a `wind_model`, the R7 skeleton.
- **`with_gamma_caveat`** fires only when a `wind_state` actually fed the standoff.

### 3d. `wind_class` / `f_dwarf`
- `_ms_wind` and `classify_wind` are **unchanged**. The CR-26 label replaces the output `wind_class` for in-scope stars.
- `f_dwarf` is retired as an emitted default. An explicit caller `wind_class=f_dwarf` goes to `noncoronal_row` with the G10 note.

## 4. Network layer — `core/xray_catalog.py` (new) + the SIMBAD helpers in `core/databases.py`

**Discipline, for every family:**
- **Retries.** `shared._bounded_call(retries=2, fatal=<AnsweredError>)`: one retry; an error the service answered is never retried. (Identity is the exception; see §4.6.)
- **Isolation.** Each family has its own circuit breaker and its own TAP seam function. The new SIMBAD helpers never reuse `_simbad_otypes_tap` / `_simbad_otypes_down`.
  - **One shared breaker (L-6).** Astrometry step 2 and the Gaia radius both go through `catalog.gaia_tap`, so they share CR-19's `_gaia_sync_down` (`catalog.py:188`) with the FLAME mass tier. A Gaia outage that trips it during the mass chain also short-circuits those two steps. That is the intended behaviour, and it is documented beside §4.1's hook note.
- **Caching.**
  - `catalog_cache.cached` is used with a producer that raises on failure, so a degraded answer is never cached.
  - Every answer uses the shape `{"answered": True, "sources": [...]}`, with no `rows` key, so an answered-empty result is cached. A test checks that the file is written.
  - `SPACE_APP_CATALOG_CACHE_DIR` sets the cache location.
- **Status mapping.** Exceptions map to timeout / unreachable / error the same way as the `fetch_star_otypes` except-chain.
- **Order and imports.** Hooks are checked before the cache or network. Imports are lazy. Tests patch by module attribute.

### 4.1 Astrometry — `star_astrometry(identity)` (family: astrometry)
- **Sources**, tried in order:
  1. The local GCNS main row by `gaia_source_id`: J2016.0, PM, parallax ± error, G.
  2. Live Gaia DR3 `gaia_source` via `catalog.gaia_tap`.
  3. SIMBAD via `databases.simbad_astrometry(main_id)`: one bounded query on `basic` + `flux` giving J2000 ra/dec, PM, `plx_value` / `plx_err`, and G (`filter='G'`).

  If step 2 fails, step 3 is tried, with a note.
- **Failure.** The family fails only when every applicable step failed. That counts as a failed X-ray lookup: the class default + `not_authoritative`, and `rungs` reads `not_queried` for all three.
- **Missing PM.** R6 (zero PM) applies only to an answered lookup that had no PM.
- **G for the XMM guard.** Gaia, else SIMBAD `flux` G. When the SIMBAD fetch that would supply G fails, the H6 rule applies. That fetch belongs to this family, so the re-gate uses the hook below; it is named in the build report.
- **Distance** = SIMBAD `plx_value`. On `exclusion-system`, a component with none borrows the primary's (with a note). No parallax at all → Q2 (`not_run`).
- **Hook:** `SPACE_APP_XRAY_ASTROM_FORCE_UNREACHABLE`.
  - The value `g` (case-insensitive) fails **only** the SIMBAD-G fetch, so the re-gate can reach H6 on a non-Gaia star (spec MED-2). Any other non-empty value fails steps 2 and 3.
  - The hook **never** blocks the local GCNS step 1.
  - The CR-19 `SPACE_APP_GAIA_FORCE_UNREACHABLE` also fails step 2, because it sits inside `gaia_tap`. That coupling is one-way and documented.
- **All steps failed (APP-decided; FYI to WB in MSG 301).** The class default + `not_authoritative`; all three `rungs` read `not_queried`; `xray.status` = the failure code.

### 4.2 Ladder — `xray_ladder(astrom, d_pc)` (family: xray)
- **Pre-filter cone.** The match radius + |μ|·max|epoch − ref| + a margin. The centres sit at 2RXS 1990.8 / eRASS1 2020.2 / XMM 2011.0.
- **2RXS.** Re-propagate to each row's `time` and take the nearest match within 60″. The flux is `onerxs_count_rate` × 6e-12 (rung `2RXS_1RXS`); otherwise `count_rate` × 10^−0.063 × 6e-12 (rung `2RXS`).
- **eRASS1.** Only where Galactic l ≥ 180°; otherwise the rung reads `out_of_footprint`. Like 2RXS, each row is re-propagated to its own `time` ("at the source's epoch", §26.3.1); the 2020.2 centre is only the pre-filter. The nearest match within 15″; flux `b1_flux` × 10^0.052.
- **XMM.**
  - Match: the nearest source within 10″ + |μ|·(end − time)/2, evaluated at the midpoint epoch.
  - Flux: the soft band sum, × 10^0.087.
  - `xmm_guard` is evaluated only when no earlier rung detected the star (G6).
  - A demoted match reads `detection` in `rungs`, with `xmm_guard.result` set (G9).
- **All three rungs are queried.** The first answered, kept detection supplies the flux (F1).
- **Rung statuses:** `rungs[{rung, status}]`, with status ∈ {detection, no_detection, timeout, unreachable, error, not_queried, out_of_footprint}.
- **Fallback disclosure.** Flags and the guard record stay on every fallback path.
- **Hook: `SPACE_APP_XRAY_FORCE_UNREACHABLE`.**
  - A list of 2RXS / eRASS1 / XMM (case-insensitive) fails just those rungs.
  - Any other non-empty value, including `0`, fails all three.
  - Unset or empty: off.
- **Timeout:** `SPACE_APP_XRAY_TIMEOUT` (default 30 s; 0 or below means unbounded).

### 4.3 Survey limit — `survey_limit(astrom, d_pc, R)` (family: xray_limit)
- **When it runs:** only when no rung kept a detection.
- **RASS limit.** The median `exposure` within 1°, or 380.15 s when none. f = 6/E × 10^−0.063 × 6e-12.
- **eRASS1 limit** (inside the footprint only). The median `b1_exposure`, and the median `b1_flux/b1_count_rate` (count_rate > 0), within 0.5°. When no source lies within 0.5° there is no eRASS1 limit.
- **Result.** The deeper of the two limits is used. `limit_log_fx` is at the star's own area; `limit_survey` is RASS or eRASS1.
- **Failure.** A failed query → no limit: the class default + `not_authoritative`, with `limit_log_fx` null (N4).
- **Hook:** `SPACE_APP_XRAY_LIMIT_FORCE_UNREACHABLE`.

### 4.4 Radius candidates — `radius_candidates(astrom, gaia_id, main_id)` (family: radius)
- **TIC.** Its own `_bounded_call` around `Vizier(columns=[…]).query_region("IV/39/tic82", 5″)` at J2000. The J2000 position is the Gaia position propagated back, or SIMBAD's for a non-Gaia star. Take `Rad` of the nearest row; the column names are probed live at CP2. Call it with `cache=False` (astroquery's own cache is the known residual-cache problem).
- **Gaia.** `catalog.gaia_astrophysical(source_id=sid)` (keyword — the first positional is `star`, which would trigger a SIMBAD lookup; L-1) for `radius_flame` / `radius_gspphot`. This is bounded, and usually a cache hit.
- **SIMBAD cone** (R12). `databases.simbad_cone_stars(ra, dec, 5″)` counts objects that meet all of:
  - a stellar otype;
  - not the target (by `oid`);
  - not an X-ray, IR or radio record;
  - not a `**` entry.
- **GCNS neighbour** within 5″ (local).
- **Hooks.** `SPACE_APP_TIC_FORCE_UNREACHABLE` covers TIC and the SIMBAD cone. `SPACE_APP_GAIA_RADIUS_FORCE_UNREACHABLE` is checked at this call site only.
- **Failures** are recorded in `radius.status` only.
- **Timeout:** `SPACE_APP_TIC_TIMEOUT` (30 s).

### 4.5 Blend partners — `blend_partners(astrom, matched_source, d_pc, target, catalog)` (family: blend)
- **Reach.** `gcns_reach()` returns the maximum `dist_pc`, memoised per DB path.
  - An empty or missing table counts as **failed** (R4): no blend, `not_authoritative`, a note.
  - A target beyond the reach → blend not run, with a note (Q3).
- **Candidates.** GCNS rows within the matched source's radius, at the source's epoch.
  - Main rows are propagated from J2016.0.
  - Missing rows start at J2000 and move by their SIMBAD PM.
  - The SQL uses a dec band plus an RA window (wrap-safe, 1/cos δ), with bound parameters.
- **Missing-row astrometry (G1).** One bounded `simbad_astrometry` call per missing row, returning parallax ± error, PM, G and `main_id`. A failure falls under R4's partial rule.
- **Dedup, main vs main — never merged (L1, agreed MSG 306).** Two main-table rows are distinct Gaia DR3 sources. The original rule (within 2″ and |ΔG| ≤ 0.5, or a shared collapsed name) deleted real companions: 41 GCNS `star_name`s are each shared by two different sources (e.g. the 0.45″ `HD 281650` pair).
- **Dedup, missing vs main** (G13). Two rows are the same star when they sit within 2″ at J2000 and either:
  - their collapsed names match; or
  - both resolve to the same SIMBAD `main_id` (a bounded lookup, made only for such pairs).

  A failed lookup → treated as distinct, with `not_authoritative`.
- **Target removal** (after the dedup, so the target's own `missing_10mas` copy merges into its main row first). The target is removed **by source_id only** when it has one (never on a name match against another main row — L1). A target with no source_id removes a `missing_10mas` row by G13 in full, and a **main** row only by G13's identity half (the row's `Gaia DR3 <sid>` resolves to the target's own `main_id` — MSG 306).
- **S1 (MSG 306) — a system entry is not a star.** A `missing_10mas` row within 2″ of a main row whose name begins `** `, or which resolves in SIMBAD to otype `**`, is that row's system entry: dropped with the duplicates (`** LDS 823`, `** LDS 9146`, `CD-38 1297`).
- **S2 (MSG 306) — on a letterless head the blend's target is the resolved A component** (its `source_id`, else its `main_id`), never the head; on a failed H1 lookup the A candidate string serves the name half. Otherwise α Cen A / 70 Oph A would stay in their own beam and blend with themselves.
- **S3 (MSG 306) — a partner never takes a radius from a star already in the blend.** A partner's TIC match that is the target's own object (its TIC or Gaia id) or another blend member is rejected (the partner then has no radius → `blend_partner_radius_missing`). HD 182488B / HD 49197B would otherwise count their primary's area twice.
- **Partner tests.** A partner must pass one of:
  - **(P) parallax:** |Δϖ| ≤ 3√(σ₁²+σ₂²). Not evaluable when a parallax or its error is missing, or a parallax is ≤ 0.
  - **(M) proper motion:** |Δμ| ≤ 1000·42.12·√(M_tot/s_AU)/(4.74047·d_pc).
    - The partner's mass comes from `stellar_mass.resolve_component_mass({"name": <SIMBAD main_id>, "designations": {"Gaia EDR3": "Gaia DR3 <sid>"}}, catalog)`.
    - If either mass is unavailable, **M_tot = 2 M☉** (the total, not the partner's mass) + a note (R3; a partner FLAME failure also counts as R3).
    - No PM → not evaluable.
  - **(S) same system:** the same GCNS `system_id`; or the same SIMBAD parent (`databases.simbad_parent(oid)`, via `h_link`) **whose otype is in the multiple-star family** (`**`, `SB*`, `EB*`, `El*`, `**?`, `SB?`, `EB?`), so cluster, association and moving-group parents don't count (J3, MSG 298); or a component-letter designation.

  α Cen B passes (M) on its SIMBAD PM.
- **Partner metadata.**
  - Name: SIMBAD `main_id` (resolved by `Gaia DR3 <sid>`), else the GCNS identifier.
  - Spectral type: GCNS, else SIMBAD, else none.
  - WD status (`wd_partner_in_beam`): the GCNS `wd_prob` column ≥ 0.5, or the SIMBAD otype `WD*` from the partner's identity lookup.
  - Radius: the §4.4 chain.
- **Hook:** `SPACE_APP_BLEND_FORCE_UNREACHABLE` → no blend processing, `not_authoritative`, a note (A7).
- **R4 partial.** When a partner lookup fails, blend on whatever (P)/(M) still decide, name the partners by their GCNS identifier, and flag `not_authoritative` with a note.
- **`--component`** never blends.

### 4.6 SIMBAD helpers (new, in `core/databases.py`)
- **Shared plumbing.** One new seam `_simbad_cr26_tap(adql)` and one breaker, bounded by `SPACE_APP_SIMBAD_TIMEOUT`.
- **Helpers:**
  - `simbad_astrometry(ident)`;
  - `simbad_cone_stars(ra, dec, r)`;
  - `simbad_parent(oid)`.
- **Identity** (a component's own `main_id`, the G12 A candidate, and the G13 "same `main_id`" lookup) uses the **existing** `databases.compute_simbad_lookup`. No new identity helper is added. That keeps designation parsing in `core.shared` (the one-parser guardrail) and means the existing test mocks of `compute_simbad_lookup` already cover it.
  - **Adapter `_identity_lookup(ident)` (M-4).** `compute_simbad_lookup` never raises: it returns `{"error": …}` both for a network failure (`databases.py:245-247`, via `_network_error_msg`) and for an answered empty result (`"No results found for …"`, `:249-250`). The adapter tells them apart:
    - `"No results found"` → **answered, no object** (returns `None`; never sets `not_authoritative`; e.g. a nonexistent `* eps Eri A` candidate);
    - any other `error` → raises a retryable `_IdentityFailed`, mapped to timeout / unreachable / error;
    - otherwise → the record.
  - It runs under `_bounded_call(retries=1, …)` + the identity hook. `retries=1` because `compute_simbad_lookup` already retries internally (`_with_retries`: 3 tries × 2 queries) and carries its own `_timeout_ctx(30)`; so `SPACE_APP_SIMBAD_TIMEOUT` on the outer `_bounded_call` is the real wall-clock bound (documented).
  - The "No results found" prefix becomes a shared constant in `databases.py`, used by both `compute_simbad_lookup` and the adapter, with a drift test. Existing test fakes that return other strings (`"No results for …"`, `test_cr23.py:22`; `"nope"`, `test_cr25.py:1082`) are read as failures by the adapter; where such a fake reaches CR-26 code, it is updated to the constant (round-5 L-5).
- **Hooks.** Each call is checked against its **caller's** family hook: astrometry, radius, blend, or identity (`SPACE_APP_SIMBAD_IDENT_FORCE_UNREACHABLE`).

### 4.7 Orchestrator — `resolve_star_wind_inputs(identity, supplied, *, catalog, allow_network=True) → StarWindInputs`
- **All identity resolution happens here, behind `allow_network`** (round-3 HIGH). The callers pass the unresolved strings plus the `sl` / `comp_sl` they already hold:
  - A: `_identity_lookup(cand)` for each `cand` in `sorted(component_candidate_ids(head, "A"))`, taking the first answered record. `component_candidate_ids` returns a **set** (`stellar_mass.py:149-162`), so the order is made deterministic; an empty set → no A identity (L-2). This is independent of the CR-25 K/M gate. When CR-25 already resolved the A candidate, its main_id is reused. `resolve_star_wind` has no `source_main_id` key; the value lives only in `cls_kw["wind_otype_source"]`, and only when the source is not self and the K/M gate fired, so it is reused only in that case (L-3).
  - B: the `comp_sl` that `_resolve_system_from_star` already fetched (`exclusion_system.py:815`), which is no longer discarded.
- **Signature:** `resolve_star_wind_inputs(identity, supplied, *, catalog, allow_network=True, db_path=None)`. `db_path` defaults to `core.db._DB_PATH`.
- **Letterless head on `exclusion-boundary --star`, with no measured row** (G12): match the resolved A candidate, with a note. The ladder still runs at the head's position.
- **A failed identity lookup** (H1): match the measured table on the head/candidate string, with a note.
  - `not_authoritative` is set **only when the string match finds no row**.
  - A string hit takes the measured tier with the note alone.
  - **(K3, MSG 302)** On this degraded path only, the string match also tries the candidate with the space before a trailing capital A–D removed (`HD 1326 B` → `HD 1326B`, so GJ 15 B, GJ 860 B and the G12 A candidate `HD 239960 A` → row `HD 239960A` (GJ 860 A) still hit). The normal §2c exact match is unchanged.
  - Hook: `SPACE_APP_SIMBAD_IDENT_FORCE_UNREACHABLE`.
- **Supplied inputs replace lookups:**

  | Supplied | Effect |
  |---|---|
  | `log_fx` | No ladder, limit or blend (`rung: supplied`, `xray.status: not_run`). **The radius family still runs** (unless `radius_rsun` is also given), at the SIMBAD J2000 position from `sl` plus the Gaia id from the designations, so no astrometry lookup is needed. |
  | `log_fx_limit` | No ladder or limit (`limit_survey: supplied`). The radius family still runs, as above. |
  | `radius_rsun` | No radius queries. |
  | `prot_days` | Feeds `fast_rotator`. |

- **Reachable-tier lookups.** Measured and supplied-rate stars still run the ladder, and the limit if there is no detection, so that `tiers` is filled. An evolved measured host, or an out-of-scope star, runs none of them.
- **`allow_network=False`** (the `--component` and `--spectral-type` paths, and the conftest default) calls no fetcher; `xray.status` is `not_run`.
  - The measured-table match is a pure lookup, so it **still applies** offline. A mocked `--star` fixture whose `main_id` is a measured row takes the measured tier (M-2): `V* EV Lac`, `* eps Eri`, `* tau Cet`, `NAME Barnard's star`, `NAME Proxima Centauri`, `* alf Cen A`, `* alf Cen B` (round-5 L-1).
  - The lower X-ray tiers with no supplied input read `not_reachable` in `tiers` (K1, MSG 302); a supplied `log_fx=` / `log_fx_limit=` still feeds its own tier.

### 4.8 Hooks and timeouts
| Family | Hook | Timeout |
|---|---|---|
| X-ray catalog rungs | `SPACE_APP_XRAY_FORCE_UNREACHABLE[=rungs]` | `SPACE_APP_XRAY_TIMEOUT` |
| survey limit / local exposure | `SPACE_APP_XRAY_LIMIT_FORCE_UNREACHABLE` | same |
| astrometry (live Gaia + SIMBAD; never the local GCNS step) | `SPACE_APP_XRAY_ASTROM_FORCE_UNREACHABLE` (`=g`: the SIMBAD-G fetch only — H6) | CR-19 / SIMBAD |
| radius: TIC + SIMBAD cone | `SPACE_APP_TIC_FORCE_UNREACHABLE` | `SPACE_APP_TIC_TIMEOUT` |
| radius: Gaia | `SPACE_APP_GAIA_RADIUS_FORCE_UNREACHABLE` | CR-19 |
| blend partners (GCNS + partner SIMBAD) | `SPACE_APP_BLEND_FORCE_UNREACHABLE` | SIMBAD |
| identity (A candidate, component `main_id`) | `SPACE_APP_SIMBAD_IDENT_FORCE_UNREACHABLE` | SIMBAD |

`SPACE_APP_CATALOG_CACHE=0` disables the cache, and `SPACE_APP_CATALOG_CACHE_DIR` redirects it.

## 5. Entry points — `query.py` + `core/exclusion_system.py`

`core/` stays I/O-free. `query.py` emits the stderr warning, based on the result fields.

### 5a. `exclusion-boundary` flags
- **New flags:** `--radius-rsun`, `--log-fx`, `--log-fx-limit` (mutually exclusive with `--log-fx`), `--prot-days`.
- **Validation.** argparse `type=` validators exit 2 when a value is non-finite or outside its G14 range:
  - `log_fx` / `log_fx_limit` outside [0, 12];
  - radius ≤ 0 or > 2000;
  - prot ≤ 0 or > 1e5.
- **Cheap checks (M-6):** `--alpha`, `--dial`, `--beta`, `--calibration-au`, `--mass-loss-msun-yr ≤ 0`, then the `wind_state` string only when no rate is supplied — the frozen order and conditions (§3c). They run **after domain classification and only on the MS / evolved-with-mass branch**, just before the orchestrator. On `--star` that is after SIMBAD, the mass chain and the CR-25 otype fetch (all pre-existing network), but **before any CR-26 network call**; a supplied star with a bad rate therefore never runs the ladder. A windless, unmodeled or evolved-no-mass body returns before them, exactly as today (e.g. `--star <WD> --alpha -1` and `--spectral-type DA --beta 1 --luminosity-lsun 0` stay exit 0). Pinned by tests.
- **Test compatibility.** Every new attribute is read with `getattr(args, name, None)`.
- **Help text:** the ladder, the `--wind-state` change, and "research-grade; standoff unchanged at γ=0".

### 5b. `cmd_exclusion_boundary` paths
**General rule, on every path:** a supplied rate (`--mass-loss-msun-yr` / `mass_loss_msun_yr=`) → `mass_loss_tier: supplied`, with the value and code path unchanged (§3a). An out-of-scope star with a supplied rate lists `tiers: {noncoronal_row}`. The table below covers the no-supplied-rate case. An A0-style test covers bare `--mass-msun --mass-loss-msun-yr`.

| Path | Tier logic |
|---|---|
| bare `--mass-msun` | `legacy_row` with `--wind-state` (hot keeps the legacy o_hot + the CR-25 note); otherwise `none`. CR-26 inputs are ignored, with a note. |
| `--object` | `object_preset`, unchanged; CR-26 inputs are ignored, with a note. |
| `--spectral-type` | In scope: supplied, else `--log-fx` (xray), else `--log-fx-limit` (non-detection), else the class default. No network. Out of scope: `noncoronal_row` (H7 row rule). |
| `--star` windless / unmodeled | Unchanged, plus the R7 skeleton. |
| `--star` evolved | A measured row (incl. the G12 A candidate) → the measured tier (R5). Otherwise `noncoronal_row`, byte-identical except for the additive fields. |
| `--star` MS | In scope → the orchestrator, after the mass resolves. Otherwise `noncoronal_row`. |

When a data tier sets the rate, an unused `--wind-state` prints a one-line stderr warning (exit 0). 61 Cyg A gets its system-edge note.

### 5c. `exclusion-system`
- **New `--component` keys:**
  - numeric: `radius_rsun`, `log_fx`, `log_fx_limit`, `prot_days`;
  - string: `main_id`;
  - alias `sp` → `sp_type`.
- **Validation.**
  - An argparse `type=` validator on `--component` returns the raw string unchanged. It exits 2 on a CR-26 key outside its G14 range, or on `log_fx` and `log_fx_limit` given together.
  - Unknown keys and the existing numeric keys keep exit 1 via the core parser (tests `test_query_exclusion_system.py:63,:197`). This mismatch is documented.
  - **New system flag `--prot-days`** (exit-2 validated like the key). It passes `cmd_exclusion_system` → `compute_exclusion_system(prot_days=…)` and reaches every component lacking its own `prot_days=`; a component key wins. On a non-ladder component it is ignored, with a note. Covered by a wiring test.
- **`--component` path** (deterministic, `allow_network=False`, never a socket):
  - The measured tier matches on `main_id=`. When the caller gives no `class=`/`sp=`, the row's `sp_type_simbad` supplies class and domain. A caller's class wins, with a note if it disagrees (H4). No row → G8.
  - **H4 injection point (M-8).** The row's `sp_type_simbad` is written into the spec **in the `--component` loop of `compute_exclusion_system` (`:915`), before `_resolve_component_mass` / `_component_domain`**, so the evolved rows (`* del Pav` G8IV, `* del Eri` K0+IV, `* lam And` G8IVk, `* d UMa` G5III-IV) classify as evolved, not bare MS. The injected `sp_type` also reaches the mass chain's caution flag, though not the mass value.
  - **"The caller gave a class"** means any of `class=`, `sp=`, `sp_type=`, `type=`, `sptype=` (the last four collapse to `sp_type`). Because `class=` may be a tag (`giant`, `wd`), "disagrees" is decided by `parse_sp` letter, or by domain when the caller's class has no letter.
  - **Parser keys.** `_parse_component_spec` (`exclusion_system.py:577-588`) gets `main_id` in `_known`; `radius_rsun`, `log_fx`, `log_fx_limit`, `prot_days` in `_num` and `_known`; and `sp` → `sp_type` in `_alias`.
  - `main_id=` is an identity key for the measured table only. It does **not** feed the mass chain, which still reads `mass=` / `name=` / `id=` as today. A `main_id=` component without `mass=` or a resolvable `name=` therefore errors as a bare component does today, **except** a lone evolved-row component (`* del Pav` etc.): the injected `sp_type` makes the lone-out-of-domain tolerance (`:922-928`) apply, so it exits 0 with `unresolved_out_of_domain` (round-5 L-3; pinned by a test). `name=` keeps its existing meaning (the catalog-mass name); the two keys may name the same star.
  - The `log_fx=`, `log_fx_limit=`, `radius_rsun=` and `prot_days=` keys work as their flags do.
  - The class-default state follows §2f: `wind_class=` state selector > `wind_state=` > the system `--wind-state` > `otype=` > typical.
  - mass + `wind_state=` with no class and no measured hit → `legacy_row` (G8).
- **`--star` path.**
  - `_resolve_system_from_star` / `_single_body_component` attach each component's resolved SIMBAD record and call the orchestrator after the CR-23 mass and the CR-25 otype. The result is stored as `c["wind_inputs"]`.
  - Blends follow §4.5. The measured tier beats the blend value star by star.
- **System `--wind-state`.** Its reach is unchanged: MS components that lack their own. It binds at tier 5 only.
- **stderr.** One line, naming the reached components whose rate a data tier set. A component's own unused key gets a note only.

### 5d. `compose_exclusion_system` — where the model runs
1. **Classify.** `_classify_component` gives the effective `wind_state`, the explicit `wind_class`, and the domain.
2. **Model.** `resolve_wind_model(c.get("wind_inputs") or deterministic_inputs(c), state_sel=…)`.
   - This is the one rule (§3c): compose **always** runs the model. `--component` dicts arrive plain and take `deterministic_inputs(c)`, which honours `main_id=`, `log_fx=`, `log_fx_limit=`, `radius_rsun=`, `prot_days=` and `otype=` with no network.
   - A plain dict with an in-scope `sp_type` and none of those keys gets the deterministic class default. (The in-scope direct-compose cases are in `test_cr25.py`; `test_exclusion_system.py`'s direct compose calls use out-of-scope classes or assert only the γ=0 standoff and point mass, so they don't change.)
   - **Per-component cheap checks** (§3c order and conditions) run on MS / evolved-with-mass components **before** the model and before the `--star` orchestrator (in `_resolve_system_from_star`), because `_compose_arg_error` (`:281-288`) checks only phase and alpha and a bad `--dial` / `--calibration-au` / `--beta` / `--gamma` is otherwise caught only in `_component_rex`, after the network. An all-windless system stays exit 0.
   - Out of scope → the R7 skeleton.
3. **Standoff.** `_component_rex(c, …, standoff_rate=…)`, applying Q1 / H3 exactly as §3c does.
4. **Walls.** `resolve_wind_inputs(tier=wm, identity_row=…)` + `wind_band_walls`.
5. **Zones.** Eligibility is unchanged in rule, but it now runs on the CR-26 point rates (GJ 65 → `periastron`).
6. **Combined wind** (`_combined_wind_wall`):
   - `combined_wind_wall_band_wind_au` from Σ Ṁ_i·10^lo_i and Σ Ṁ_i·10^hi_i. A member with no band contributes its point to both sums. v, the medium and t_phase come from the member with the largest point rate.
   - `combined_wind_band_exceeds_standoff`, compared against `max_standoff`; null when either side is null.
   - `combined_wind_wall_is_upper_bound`: true when any member's rate is an upper bound, and the two band fields are then null. Null when the combined wall is null.
   - Disclosure item 15 goes into each member's notes.
7. **Point mass** (R11 / H8).
   - At γ=0: today's arguments exactly.
   - At γ>0: Σ of each member's standoff-input rate (tier rate / legacy-map rate / supplied rate). An upper-bound member gets the R11 note.
8. **`measured_system_edges`** (G4): `[{members, system_upper_edge_mdot_sun: 9.6, source: "kislyakova2024"}]` when both 61 Cyg components resolve; `[]` otherwise.

## 6. Files touched

- **New code:** `core/stellar_wind_tables.py`, `core/stellar_wind.py`, `core/xray_catalog.py`.
- **New data:** `data/cr26/*.csv` (6).
- **`.gitignore`** — `data/` becomes `data/*` + `!data/cr26/`, so the vendored CSVs are tracked while every other `data/` file (the DB, caches, dust maps) stays ignored (found at build step 1: nothing under `data/` was tracked).
- **`.gitattributes`** — `data/cr26/*.csv -text`, added before the CSVs are staged (round-4 HIGH).
- **New tests:** `tests/conftest.py`, `tests/data/cr26_spec_disclosures.txt`, `tests/test_cr26_model.py`, `tests/test_cr26_network.py`, `tests/test_cr26_wiring.py`, `tests/test_cr26_live.py`.
- **Edited:**
  - `core/exclusion_wall.py`
  - `core/exclusion_boundary.py` — wrapper only; the FROZEN body is untouched.
  - `core/exclusion_system.py`
  - `core/databases.py` — the three SIMBAD helpers (§4.6), the seam and the breaker. Identity reuses `compute_simbad_lookup` through the `xray_catalog._identity_lookup` adapter.
  - `core/catalog_cache.py` — `SPACE_APP_CATALOG_CACHE_DIR`.
  - `query.py` — incl. `exclusion-system --prot-days`.
  - `core/shared.py` — the named `_SP_DWARF_SUBDWARF_PREFIXES` subset constant.
  - `pytest.ini` — the `cr26_network` marker.
  - `core/db.py` — an ra/dec index **only if** the CP2 scan takes over 1 s (currently 0.10 s).
- **Docs:**
  - `docs/integration.md` — the CR-26 block: flags, keys, fields, enums, hooks, exit codes, and the behaviour changes incl. H7;
  - `docs/testing.md`, `docs/core-modules.md`, `docs/calculators.md`;
  - `CLAUDE.md` — the test count, plus the guardrail "CR-26 data files are WB-owned — byte-identical, md5-checked at load; never edit".

## 7. Tests

### Isolation
- A `tests/conftest.py` **autouse** fixture does two things:
  1. It wraps `core.xray_catalog.resolve_star_wind_inputs` so that `allow_network` is **forced** to False: `lambda *a, **k: orig(*a, **{**k, "allow_network": False})`, not `functools.partial`, which an explicit `allow_network=True` would override. Callers always go through the module attribute, never `from … import`.
  2. It patches every CR-26 network seam with a stub that **appends to a module-level leak list** and raises: `databases._simbad_cr26_tap`, the HEASARC seam, the TIC seam, `xray_catalog._identity_lookup`, and three new thin wrappers owned by `xray_catalog` through which CR-26 makes its Gaia and partner-mass calls — `_gaia_astrom_seam` (→ `catalog.gaia_tap`), `_gaia_radius_seam` (→ `catalog.gaia_astrophysical`) and `_partner_mass_seam` (→ `stellar_mass.resolve_component_mass`). The underlying functions stay unpatched, because existing tests use and mock them (round-5 MED-3). The fixture's teardown calls `pytest.fail()` when the list is non-empty; autouse fixtures apply to the `unittest.TestCase` classes pytest collects. A raised `AssertionError` alone would be swallowed: the family except-chains catch `Exception` (cf. `databases.py:627`), and `_call_with_watchdog` returns `None` on a `BaseException` (`shared.py:1295-1308`). So a leak fails the test, and never reaches the network (M-3).
- Tests marked `@pytest.mark.cr26_network` opt out and mock the seams. `test_cr26_live.py` is in-process, so it carries that marker too.
- `SPACE_APP_CATALOG_CACHE_DIR` is read once, when `_CACHE_DIR` is initialised (at import, which is enough for subprocesses). In-process tests keep monkeypatching `_CACHE_DIR`, so the existing `test_catalog_cache.py` / `test_cr25.py` patches are unaffected. The tmp-cache + `clear_cr26_cache()` + hook-popping setup is scoped to the `test_cr26_*` files.
- Offline subprocess tests never use `--star`.
- A socket guard runs in the offline `test_cr26_*` classes.

### Test groups
1. **Tables:**
   - md5 pass and mismatch;
   - row counts; en dash; fork-9 top rows equal fork-8;
   - `hw` pins;
   - repo copies match the pinned md5s, and contain no `\r` (the `.gitattributes` `-text` rule);
   - the rule ↔ scope check.
2. **Parsing and scope:**
   - every §2a pin;
   - bins; M4.0 → M4+; `subtype_unknown`; the subdwarf note;
   - H7 `kA5hF0mF2` → `a_dwarf` + note; `A0mA1` → A.
3. **Relation, band, widening, flags:**
   - A1 exact;
   - every §26.3.8 example;
   - regime edges (4.84 / 4.86 / 5.99 / 6.01, F active, G active), and no edge note on the mixtures;
   - `below_fit_range` (3.9947, 3.90, a fork-9 conditional below 4.03, and H5 on `upper_limit_only`);
   - `above_fit_range` strictly above 7.2; `fast_rotator` at 0.5;
   - blend flags evaluated on the system F_X;
   - `blend_mixed_class` by bin (H2).
4. **Measured:**
   - A2 in full;
   - ξ Boo A 0.5 and 36 Oph A 8.5;
   - whitespace-collapsed matching;
   - every rule; the T12 direction note.
5. **Class default:**
   - A5 at ±0.001 dex / walls ±6 %;
   - states, modes, labels;
   - G10 (`wind_class=solar` beats `wind_state=active`; `wind_class=f_dwarf` → noncoronal + note);
   - `hot`;
   - the `subtype_unknown` branches (detection + catalog radius; limit only → `none`; failed rung → `none` + `not_authoritative`; `--wind-state` → the H3 note);
   - no spectral type → a null wall.
6. **Non-detection:**
   - A4b exact;
   - A4 with the back-derived radii (HD 349726 R ≈ 0.336, ρ CrB R ≈ 1.318);
   - grid boundaries; limits below 3.50 and above 8.00;
   - the bimodal gate.
7. **Radius:**
   - every rung; rejection; K2 (F/G/K with no digit → class-median check, `rejected`, the supplied-radius note);
   - VB 10;
   - the `radius_pair_ambiguous` gate (α Cen A no, 61 Cyg B yes, 70 Oph A yes);
   - `radius_unchecked`; the off-median note; failed families recorded.
8. **`ladder_outcome`:** the exhaustive table, including:
   - XMM demotion;
   - `not_queried`;
   - a failed astrometry lookup;
   - a failed limit;
   - H6 (a failed G fetch vs an answered "no G").
9. **Tiers and schema:**
   - Q4 + G2 per case: the entry-level `not_authoritative` with an unflagged top level, and `failed` with no value;
   - A3b row 3;
   - the evolved host; a supplied out-of-scope star → `{noncoronal_row}`;
   - the full schema test.
10. **Disclosures:**
    - the R8 token check;
    - the G7 selection.
11. **A3 offline pins.** Each A3 row, given its rung, flux, distance, radius and partners, must produce the spec's Ṁ, band, walls and flags:
    - 61 Cyg B 0.6290 and α Cen A 0.9156 (both on the system F_X);
    - DENIS (a kept XMM detection);
    - ι Psc −1.49;
    - VB 10;
    - Wolf 359, Ross 128, Ross 248, σ Dra, AD Leo;
    - 70 Oph A.
12. **Network** (`cr26_network`, mocked seams):
    - **matching:** propagation (2RXS **and eRASS1** per row `time`); the widened pre-filter (Barnard's); nearest match; footprint; XMM tolerance; conversions;
    - **XMM:** guard order; G3 (G from Gaia → SIMBAD → none; floor on the system F_X); G6 (a lower detection is recorded but not used; no `xmm_guard` after an earlier detection); G9;
    - **survey limit:** medians, 380.15 s, deeper-wins, N4;
    - **astrometry:** the fallback from step 2 to 3; an all-failed lookup counts as a failed X-ray lookup (all rungs `not_queried`); R6; H6 via `SPACE_APP_XRAY_ASTROM_FORCE_UNREACHABLE=g` on a non-Gaia star with XMM as the candidate → the XMM rung `failed`; the hook never blocks the local GCNS step;
    - **blend dedup:** main-vs-main incl. NULL G; G13 (name / same `main_id` / different `main_id` / failed lookup / no-source_id self-removal);
    - **blend partners:** (P) / (M) / (S) incl. α Cen via G1; field star; WD; missing radius; R3; R4 partial; empty table → failed; the reach cut;
    - **identity:** the `_identity_lookup` adapter ("No results found" → answered-empty, never `not_authoritative`; a network error → failed, one attempt at the outer layer); H1 (failed identity with a string hit → note only; no hit → `not_authoritative`); K3 (`HD 1326 B` hits `HD 1326B`, and `HD 239960 A` hits `HD 239960A`, on the degraded path only);
    - **plumbing:** every hook incl. the rung list and `=0`; retry once; the breaker; the cache (answered-empty written, a failure never written).
13. **Wiring** (in-process + offline subprocess):
    - A0 byte-identity, incl. bare `--mass-msun --mass-loss-msun-yr` → `supplied`;
    - `exclusion-system --prot-days`: its reach, and the component key winning;
    - `--star --log-fx` still runs the radius family (mocked);
    - `tiers` `upper_limit_only`;
    - J1 / J2 / J3 defaults;
    - Q1 / H3 at γ>0;
    - R10; G11 (a supplied F dwarf keeps v 500); G12 (mocked);
    - G14 range boundaries on every path; the component exit-1 keys unchanged;
    - stderr printed once, with the component names;
    - `--component` opens no socket;
    - A6, all four bullets:
      - the GJ 65 zone, exact;
      - 61 Cyg composition + `measured_system_edges`;
      - ε Eri via `main_id=`, offline, with `mass=0.82` → `wall_band_wind_exceeds_standoff` **false** (standoff 43.875 > band top 43.818; A2's `true` comes from the catalog mass ≈ 0.811 and is pinned live only);
      - a system `--wind-state quiet` reaching only the class-default component, with its note;
    - H4 (caller class wins + the disagreement note; a `main_id=` hit on an evolved row classifies as evolved); G8; H8;
    - **offline `query.py` anchors (spec MED-4)**, as subprocess runs with no network: `exclusion-boundary --spectral-type` A3b rows 1–2 (`--log-fx` / `--radius-rsun` / `--prot-days`), A4b row 2 (`--log-fx-limit`) and one A5 row; `exclusion-system --component` A4b row 1 and the A5 `otype=Er*` bullet (active state, `otype_auto`, disclosure item 14);
    - **combined-wind null rules:** a zone with an upper-bound member (`log_fx_limit=` below the class grid → `upper_limit_only`) → `combined_wind_wall_is_upper_bound: true` and both band fields null; a zone with a supplied (no-band) member contributing its point to both sums; item 15 present only when the band is non-null;
    - M-6 (in-process, Namespace / direct core calls — the CLI's `--wind-state` choices exit 2 first): a windless / unmodeled body with a bad `alpha` / `wind_state` keeps exit 0; a supplied rate + a bad `wind_state` stays exit 0; `--mass-loss-msun-yr -1` on an in-scope star errors before any CR-26 seam is touched; the γ>0 variant of `test_cr25.py:1237`; exclusion-system per-component cheap checks before the orchestrator;
    - `--object` tier: `sun`, `m-dwarf`, `o-star` → `object_preset` (round-5 MED-1);
    - a lone `--component main_id=* del Pav` with no mass → exit 0, `unresolved_out_of_domain`;
    - K1: `tiers` on the `--component` measured path reads `not_reachable` for the X-ray tiers;
    - A7 per hook (these tests are `cr26_network`).
14. **Existing tests updated as contracted changes.** Each one is listed at CP3/CP4 against its §Consequences clause:
    - `test_cr25.py:849` (`test_q7_gamma_standoff_untouched`) and `:1117-1135`;
    - **live:** `test_cr25_live.py`
      - EV Lac `_WALL_ACTIVE`/`_WALL_QUIET` (`:61-90`) — EV Lac is now measured;
      - the M4V active `1e-13` (`:113`, `:144`);
      - τ Cet wall 6.0 (`:101`) — now measured ≤ 0.1;
      - the γ>0 pins (`:116-125`);
      - the degrade `wind_class "quiet"` (`:130`);
    - **live:** `test_query_exclusion_system_live.py` (in-scope anchors);
    - **live files on throwaway DBs (M-9).** `test_cr25_live.py:15` and `test_query_exclusion_system_live.py:21` run with an empty `gcns_stars`, so under R4 the blend family reads failed and every X-ray-tier star is `not_authoritative`. Their in-scope re-pins assert **the tier and the flags only**. The value pins live in `test_cr26_live.py`, on the real DB;
    - **offline:** the mocked in-process `--star` tests. Under the conftest-forced `allow_network=False`, a fixture whose `main_id` is a measured row takes the **measured tier** (`V* EV Lac` point; `* eps Eri` `point_span_both`; `* tau Cet` / `NAME Barnard's star` `upper_limit`; `NAME Proxima Centauri`, `* alf Cen A`, `* alf Cen B` per their rows; M-2); every other in-scope fixture takes the `not_run` class default. Their wind assertions are updated to that; their mass/standoff assertions stay unchanged. The build lists every affected test **by name** at CP3/CP4. Known sites (round-5 L-1): `test_exclusion_system.py:374-391, :421, :431, :453, :482`; `test_cr25.py:719-747, :755-848, :861-884, :918-1088, :1105` (α Cen B `wind_class "quiet"`), `:1144-1152` (M4V `--component` rate 1e-16 → the CR-26 class default), `:1159-1172` (EQ Peg label); `test_cr23.py:64-251`;
    - **direct `compose_exclusion_system` calls on in-scope plain dicts** (M-1; the in-scope ones are in `test_cr25.py`) now get the deterministic class default; their wind assertions are updated;
    - every CR-22/23/25 assertion on an in-scope star's `wind_class`, rate, wall, provenance, or the f_dwarf label;
    - any fixture that uses an Am-type string (H7).
15. **Live** (`test_cr26_live.py`). Gated on `SPACE_APP_RUN_LIVE=1` + HEASARC reachability, with the cache off and `SPACE_APP_WB_MASS_CATALOG`. `core.db._DB_PATH` is monkeypatched to the real DB (neither entry point passes a `db_path=` through; connecting re-runs the idempotent `CREATE … IF NOT EXISTS`; L-8). Skips if `gcns_stars` is empty. Covers:
    - A3 (±0.05 dex / ±6 %) and the A4 limits;
    - A2 via `--star`:
      - ε Eri on both subcommands (α 0.4 → true; α 1/3 → false);
      - δ Pav;
      - Proxima + T12;
      - EV Lac `tiers.xray` 3.77 @ 7.155;
    - A3b rows 1–2 (also pinned offline in group 13); A6 61 Cyg; the A0 standoffs, incl. the A0 named case Procyon → `noncoronal_row`, byte-identical at 55.53.

## 8. `/code-review high` checkpoints (each checkpoint's findings are triaged and folded before the next)

- **CP1 — data + pure model** (§1–§2, tests 1–11). Focus:
  - md5 checked before parsing; the en dash; `.gitattributes` `-text` on `data/cr26/*.csv`;
  - every formula vs the spec: widening order, floor reading, area share on `point_combined` only, K_c;
  - flags evaluated on the system F_X;
  - `tiers` and G2;
  - `ladder_outcome` vs §26.1;
  - R8 text fidelity;
  - the schema;
  - no network imports.
- **CP2 — network** (§4, test 12, plus a live probe of the TIC columns, 3 ladder stars and the α Cen / 61 Cyg partner resolution). Focus:
  - per-family CR-19 discipline;
  - the cache sentinel;
  - hook order;
  - epochs (J2000 for missing rows);
  - G1 / G13 dedup safety;
  - the (M) units;
  - bound SQL parameters;
  - separate SIMBAD seams and breakers;
  - lazy imports.
- **CP3 — `exclusion-boundary`** (§3, §5a/b, test 13 boundary half, the test-14 list). Focus:
  - γ=0 byte-identity; Q1 / H3;
  - `tier=None` and `supplied` byte-identity;
  - R10;
  - every path emits every field;
  - exit 2 vs exit 1;
  - the cheap checks: frozen order and conditions, after classification, before any CR-26 network call; the exclusion-system per-component checks before the orchestrator;
  - the stderr warning;
  - H7.
- **CP4 — `exclusion-system`** (§5c/d, test 13 system half, the test-14 list). Focus:
  - the model runs before `_component_rex`;
  - resolved component identities;
  - parity with `exclusion-boundary`;
  - measured beats blend;
  - zones on CR-26 rates;
  - the combined band and its null rules;
  - R11 / H8;
  - `measured_system_edges`;
  - no network on `--component`;
  - H4;
  - stderr printed once.
- **CP5 — whole CR** (full suite, APP live pre-check, docs). Focus:
  - cross-subcommand parity;
  - docs vs code;
  - the A0–A8 table;
  - no CR-24 creep;
  - `git diff` shows the FROZEN body untouched.

## 9. Re-gate pre-check (APP, before build-complete)
- **Setup:** the APP venv, `SPACE_APP_CATALOG_CACHE=0`, `--star-mass-catalog <WB catalog>` on every `--star` call, `--gaia-timeout 120`.
- **Tolerances:**

  | Anchors | Tolerance |
  |---|---|
  | A0 | exact |
  | A1, A2, A3b, A4b, A6 | exact / ±0.02 dex |
  | A5 | ±0.001 dex |
  | A3, A4 | ±0.05 dex, walls ±6 % (a regime flip is recomputed at the live regime) |

- **A7:** exercised through each hook. The build report names the H6 hook: `SPACE_APP_XRAY_ASTROM_FORCE_UNREACHABLE=g` (SIMBAD-G fetch only), and states the astrometry all-failed degrade result (§4.1).
- **A8:** the whole exclusion battery, annotated against §Consequences.
- **md5s:** printed.

## 10. Risks / accepted caveats
- **Contracted behaviour changes:**
  - walls move;
  - `wind_class` goes from quiet to solar;
  - `--wind-state` binds at tier 5 only;
  - f_dwarf is retired as a default;
  - γ>0 standoffs move for in-scope stars;
  - Am-type strings take `a_dwarf` (H7);
  - the γ>0 point mass for a system with **no** in-scope member also changes: today one supplied rate + one `wind_state` member gives `wind_in` = the supplied sum only (`exclusion_system.py:433-435`); under R11 / H8 the `wind_state` member adds its legacy-map rate (L-7);
  - direct `compose_exclusion_system` calls on in-scope plain dicts now get CR-26 (M-1).
- **WB-ref drift** is reported to WB with the live row, never fixed locally.
- **Outages** degrade to the class default + `not_authoritative`. That is correct, but it blocks the live pre-check.
- **Latency** is about 15–25 s per star cold, plus the SIMBAD identity and partner calls (accepted).
- **The first runtime md5 check:** a corrupt checkout turns every in-scope call into a curated error, by design.
- **`--component` exit codes:** existing keys exit 1, CR-26 keys exit 2 (documented).

- **Live-suite time:** each in-scope `--star` adds about 15–25 s cold. The CLAUDE.md live-suite estimate is updated at CP5.
- **Import direction:** `stellar_wind` is a leaf that imports only `stellar_wind_tables` and `shared`. `exclusion_wall` / `exclusion_boundary` / `exclusion_system` import it, never the other way. The non-coronal rates are filled by `exclusion_wall`, the legacy-map rate by `exclusion_boundary` / compose, and the CR-25 colour letter by `xray_catalog` (§2h, M-5, round-5 L-2). `xray_catalog` imports `stellar_wind`, `databases`, `catalog`, `stellar_mass` and `detection` lazily (`detection` imports only calculators / tables / shared, so no cycle).
- **Cheap checks** mirror the frozen generator's validation, **order, conditions** and messages exactly (§3c): alpha/beta/gamma < 0, dial ≤ 0, calibration ≤ 0, β ≠ 0 with L ≤ 0, `mass_loss_msun_yr ≤ 0`, then `wind_state` only without a rate. They run only on the MS / evolved-with-mass branch, where the frozen generator would run them, so no path that exits 0 today starts to exit 1 (M-6). Compose's component `wind_state` check exists so that no path that exits 1 today starts to exit 0 either (the γ>0 tier-2–5 case). `exclusion-boundary` gets no canon-band alpha check.

## 11. Build sequence (after the round-4 fold, WB's K1–K3 answer, and Greg's go)
1. §1 + §2 + tests 1–11 → **CP1**.
2. §4 + test 12 + the live probe → **CP2**.
3. §3 + §5a/b + tests 13/14 (boundary) → **CP3**.
4. §5c/d + tests 13/14 (system) → **CP4**.
5. The no-socket offline run; then the full `venv/bin/python -m pytest -q` (**one heavy job at a time**); then the live battery.
6. Docs → **CP5**.
7. Build-complete MSG → WB re-gate → Greg's flip → commit CR-26-only on `main` + push + SHA → move the plan to `completed_plans/` + a memory note.

## 12. Review record
- **Round 1:**
  - Findings: code review 5 HIGH / 8 MED / 9 LOW; spec review 2 HIGH / 8 MED / 9 LOW.
  - The HIGHs:
    - measured `point` rows were area-shared;
    - the cache sentinel was never cached;
    - `retries=1` meant no retry;
    - components had no resolved identity or astrometry;
    - offline tests would open sockets;
    - an astrometry failure had no degrade rule.
  - All were folded in. The spec gaps went to WB as G1–G14 (MSG 291), ruled in MSG 292.
- **Round 2:**
  - Findings: code review 1 HIGH / 6 MED / 9 LOW, plus 20 places where the body contradicted the rulings; spec review 0 HIGH / 4 MED / 8 LOW.
  - The HIGH: where the model runs relative to the γ>0 standoff (now §5d).
  - This v2 rewrite reconciles every contradiction. The spec gaps went to WB as H1–H8 (MSG 294), ruled in MSG 295.
- **Round 3:**
  - Findings: code review 1 HIGH / 3 MED / 8 LOW; spec review 0 HIGH / 4 MED / 8 LOW.
  - The HIGH: CR-26 identity lookups sat outside the offline switch, so existing `--star` tests would reach SIMBAD. Fixed: all identity resolution now runs inside the orchestrator behind `allow_network`, via the existing (mocked) `compute_simbad_lookup`, and the conftest makes every new seam raise.
  - MEDs fixed: `exclusion-system --prot-days` added; the §7.14 live and equality tests listed; `tiers` `upper_limit_only`; `--log-fx` keeps the radius chain; the supplied tier on every path.
  - All LOWs folded.
  - Three spec gaps went to WB as J1–J3 (MSG 297), agreed as defaulted in MSG 298.
- **Round 4** (fresh eyes on v2.1, 2026-09-27):
  - Findings: code review 1 HIGH / 9 MED / 10 LOW; spec review 0 HIGH / 4 MED / 8 LOW. Nothing HIGH in the model, the wiring or the spec conformance. All six md5s, every ruling Q1–J3, and every recomputed anchor (A3b rows 1–2, A3, A4, A4b, A5, A6) check out.
  - The HIGH (both reviewers): `.gitattributes` `*.csv text` would give a Windows checkout CRLF copies that fail the md5 check. Fixed with `data/cr26/*.csv -text` + a no-`\r` test (§1, §6).
  - MEDs fixed:
    - §3c vs §5d.2 plain-dict contradiction → compose always runs the model (M-1);
    - the offline mocked `--star` fixtures whose `main_id` is a measured row take the measured tier (M-2);
    - conftest leak detection via a leak list + teardown `pytest.fail` (M-3);
    - a `compute_simbad_lookup` adapter that tells "No results found" from a failure (M-4);
    - the model returns CR-26 rates only; the caller fills non-coronal / legacy rates and the CR-25 letter (M-5);
    - cheap checks only on the MS / evolved-with-mass branch (M-6);
    - `compute_two_layer_boundary` derives `mass_loss_tier` itself (M-7);
    - the H4 injection point in the `--component` loop (M-8);
    - existing live files on throwaway DBs assert only tier + flags (M-9);
    - the H6 hook value `=g` (spec MED-2);
    - offline `query.py` subprocess anchors for the `--spectral-type` / `--component` wiring (spec MED-4).
  - All LOWs folded: stale line refs; `gaia_astrophysical(source_id=)`; the candidate set; `sw_a`; the helper count; the shared Gaia breaker; the R11 no-in-scope change; the `_DB_PATH` monkeypatch; one fork-9 keying; the `Cr26DataError` catch site; the A6 ε Eri `false`; the combined-null tests; eRASS1 epoch; M_tot = 2 M☉; `subtype_unknown` wording; class-default output fields; Procyon A0 and the A5 `otype=` test; the `wd_partner_in_beam` source.
  - Spec gaps K1–K3 went to WB in MSG 301, with two FYIs (the astrometry all-failed degrade; the `=g` hook). WB agreed as defaulted in MSG 302, adding the K2 supplied-radius note; both FYIs go on the re-gate's hook list.
- **Round 5** (scoped code review of the round-4 fixes only, 2026-09-27):
  - Findings: 0 HIGH / 3 MED / 7 LOW. All folded; none is a spec gap, so nothing went to WB.
  - MED-1: self-derived `mass_loss_tier` would label `--object` presets `supplied` (the preset rate travels in `mass_loss_msun_yr`). Fixed: `object_preset` is checked first, and `--object` also passes it explicitly (§2h).
  - MED-2: the cheap checks didn't mirror the frozen generator's order and conditions (`mass_loss ≤ 0` first; `wind_state` only without a rate); the CLI's `--wind-state` `choices` make the planned exit-0 test unreachable; and at γ>0 compose would stop rejecting a component's bad `wind_state=`. Fixed in §3c / §5a / §5d / §10 / §7.13.
  - MED-3: the leak list missed CR-26's Gaia and partner-mass calls. Fixed: three `xray_catalog`-owned wrapper seams on the leak list (§7 isolation).
  - LOWs: the full list of measured fixtures and affected test sites (Proxima, α Cen A/B, more `test_cr25` lines; the build names tests); the legacy map's owner is `exclusion_boundary` / compose, and `deterministic_inputs` + `cr25_letter` live in `xray_catalog` (lazy `detection` import); the `--component` parser keys, "caller gave a class" incl. `type=`/`sptype=`, tag-aware "disagrees", and the lone evolved `main_id=` exit-0 case; the direct-call `legacy_row` derivation; the "No results found" constant + drift test and the real SIMBAD timeout bound; `.gitattributes` **append** + a `git check-attr` test; and the stale "before any network" / "offline tests only" wording.

## 12b. Build log (2026-09-27, Greg's go; WB told "build started" in MSG 304)
- **Step 1 (§1–§2) → CP1.** `core/stellar_wind_tables.py`, `core/stellar_wind.py`, `core.shared._SP_DWARF_SUBDWARF_PREFIXES` + `core.shared.collapse_ws`, `data/cr26/` (+ `.gitignore`/`.gitattributes`), `tests/test_cr26_model.py` (72).
  - CP1 `/code-review high`: 10 findings, 9 fixed — out-of-scope supplied rate → `supplied` + `tiers {noncoronal_row}`; a supplied `log_fx`/`log_fx_limit` never falls through to the ladder; `xmm_guard` demotes a missing `sum_flag`; no spectral type → `none`; `hw` rounds half up; item 9 verbatim; `subtype_unknown` note once; one whitespace normaliser (`core.shared.collapse_ws`, used by `databases._wskey` too); dead code removed.
  - **Not changed (decided):** under H6 (a failed SIMBAD-G fetch) `xray.xmm_guard` stays **absent** — the guard is never evaluated, and a `result` outside the spec's `{kept, xmm_guard_demoted, xmm_floor_demoted}` enum would be worse; the XMM rung's own status (`timeout`/`unreachable`/`error`) carries the reason.
  - Live probe (step 2 preview): Wolf 359 0.1141 (A3 0.1141), AD Leo 3.5506 (3.5504), 61 Cyg B 0.6290 blended with 61 Cyg A + `radius_pair_ambiguous` (A3 0.6290), α Cen A `tiers.xray` 0.9169 + `blended_source`/`blend_mixed_class` (A3 0.9156).

- **Step 2 (§4) → CP2.** `core/xray_catalog.py`, the CR-26 SIMBAD helpers in `core/databases.py`, `SPACE_APP_CATALOG_CACHE_DIR`, `tests/conftest.py`, `tests/test_cr26_network.py` (47).
  - CP2 `/code-review high`: 10 findings, all fixed — main-vs-main rows never merged + the target removed by source_id only (**L1 → WB MSG 305**, built as defaulted); a null-flux matched source → the rung reads `error`; SIMBAD PM fills a Gaia row lacking PM; the identity family gets its breaker, and G13 uses the blend-family `simbad_astrometry` (the missing row's `main_id` is already fetched); one SIMBAD breaker **per family** (astrometry / radius / blend); plumbing tests added; the conftest redirects the catalog cache so a warm live cache cannot hide a leak; one read-only GCNS connect helper (a proper file URI; an empty table is not memoised); `_plain` reused, the stellar-otype filter made explicit.
- **Step 3 (§3, §5a/b) → CP3.** `exclusion_wall.resolve_wind_inputs(tier=…)` + `wind_band_walls`; `exclusion_boundary.standoff_arg_error` / `derive_mass_loss_tier` / `compute_two_layer_boundary(wind_model=…, mass_loss_tier=…, cr26_notes=…)`; `query.py` `exclusion-boundary` (new flags, exit-2 validators, the returning `_exclusion_boundary_result`, `Cr26DataError` → exit 1, the stderr line). Seven `test_cr25.py` boundary tests updated as contracted changes (EV Lac/τ Cet measured, K/M `solar`, Q1). `tests/test_cr26_wiring.py` (boundary half).
  - H3 is not reachable through `--spectral-type "M V"` (no main-sequence table row → the pre-existing "Could not resolve spectral type" error); it is pinned through the core call and applies on `--star` / `--component`.

  - CP3 `/code-review high`: 10 findings, all fixed — the H7 row replaces only a CR-25 colour-default / otype-auto bin (an explicit `--wind-state` is honoured as on a real A star) and the `tiers.noncoronal_row` rate follows the H7 row; ignored-input notes whenever the star is outside the CR-26 scope (incl. a supplied rate and an evolved measured host); a star with **no spectral type** keeps today's path (`legacy_row` / `none`, §26.5 "keeps today's behaviour"); `--object` + a user rate → `supplied`; windless/unmodeled keep passed notes; `derive_mass_loss_tier` → `legacy_row` for a coarse F/G/K/M bin (as M-7 specifies), `noncoronal_row` for A/B/O; parallax must be > 0 for a distance; one ladder-tier tuple (`stellar_wind.LADDER_TIERS`); the evolved `--star` path networks only when a G12 candidate could still find a measured row.
- **Step 4 (§5c/d) → CP4.** `compose_exclusion_system` runs the model per component before the standoff (`_component_model`, `_combined_wind_band`, `_measured_system_edges`, R11/H8 point mass, the any-γ own-`wind_state` check), `compute_exclusion_system(prot_days=…)` (H4 injection before the mass chain, per-component cheap checks, then the orchestrator for `--star` components; component A resolved through its A candidate — G12 falls back to the head), `_parse_component_spec` keys, `query.py` `--prot-days` + the exit-2 `--component` type + the once-only stderr line. Ten `test_cr25.py` system tests updated as contracted changes.

  - CP4 `/code-review high`: 10 findings, 9 fixed — H1 on a failed B lookup: the matched row supplies the class (else B was discarded as typeless); component A's candidate is `xray_catalog.a_candidate` (None when the head already names A — parity with `exclusion-boundary`); the component-A note names the candidate; the H7 guard + `tiers.noncoronal_row` fix in compose too; the three combined-band zone fields are always present (null with `combined_wind_wall_au`); B is not looked up twice; the system `--prot-days` gets its ignored note on out-of-scope components; the cheap checks give the system `--wind-state` to MS components only; parallax > 0. **Not changed:** a ladder member's `standoff_rate` is never None (every ladder tier has a rate), so the R11 sum cannot diverge from its standoff.
- **Pre-existing fix that rides along (disclosed):** astroquery's `astroquery.gaia` import (a module-level `GaiaClass()`) and every fresh `GaiaClass()` print the ESA archive banner ("In preparation for Gaia DR4, …") to **stdout**, corrupting `query.py`'s JSON on every Gaia path (CR-19/CR-23 FLAME included, now CR-26's astrometry/radius too). `core/catalog.py` imports it with stdout diverted to stderr (`_import_gaia`, in the caller's thread) and builds clients with `show_server_messages=False`; the CR-19 test fake accepts the keyword. Found in the step-4 live probe.
- **Live probe notes:** `--star "61 Cyg"` / `"61 Cygni"` do not resolve in SIMBAD (pre-existing identity behaviour — the spec's A6 allows "or both components"; the offline A6 61 Cyg test composes the two components). α Cen system: A/B measured 0.46/1.54, `tiers.xray` blended, standoffs 48.9669/45.7214 exact. Wolf 359 `exclusion-boundary`: 0.1141, wall 2.03 [1.35–2.70] {0.48–11.26} — A3 exact.

- **WB MSG 306:** L1 agreed (R2's "or a shared `star_name`" retired); S1–S3 folded (tests in `test_cr26_network.py`: 4 new) — suite 3740 / 110 / 0.

- **Step 5–6 → CP5 (whole CR + docs).** Full offline suite green (3740 / 110 / 0 before CP5). Live battery: 21 passed, 4 failed. **All four failures were the live test's design, not CR-26:** `exclusion-boundary --star` stops before CR-26 on the pre-existing no-V / no-Teff regions gap (ρ CrB, Ross 248, 70 Oph A, VB 10), `DENIS J1048-3956` does not resolve as written, VB 10 / DENIS / LEHPM 3396 have no resolvable mass on either subcommand (the pre-existing mass-chain gap), and `61 Cyg` has no SIMBAD system object. Re-routed through `exclusion-system --star`: ρ CrB 0.8587 (exact, `xmm_guard_demoted`), HD 349726 0.1116 (exact, `xmm_floor_demoted`), HD 192310 0.4612, 107 Psc ≤ 0.3548, Ross 248 0.1701 (A3 0.1654, 0.012 dex), 70 Oph A `tiers.xray` 2.7933 blended (A3 2.7883); σ Dra 1.4661 and ι Psc 4.272 exact on `exclusion-boundary`. The unreachable ones are pinned offline (`A3OfflineTest` / `NonDetectionTest`), and the 61 Cyg system test is skipped with the reason.
  - CP5 `/code-review high`: 10 findings, all fixed — **the Gaia banner fix had moved the first `astroquery.gaia` import (a network call) outside the CR-19 bound**; it now runs inside the bounded attempt with stdout diverted (`catalog._gaia_stdout_to_stderr`); a component with no SIMBAD identity and no Gaia id → `not_run` (`no_identity`), not `error`; a windless / unmodeled body with a supplied rate → `noncoronal_row` on both subcommands + an "ignored" note (and a windless `--object` preset stays `object_preset`); `erass1_footprint` is null unless the eRASS1 rung was evaluated; `exclusion-system` keeps a typeless component's notes; the supplied-flux radius path uses the local GCNS row's J2016 position + PM; the conftest uses one session-scoped tmp cache dir; docs (the live-run count, the plan path, the MSG range); the R11 note is not repeated on a lone zone; the dead `wind_state_is_system` field is dropped.

- **Re-gate RED (WB MSG 311, 2026-09-28) → fixed.** RG1 (a `source_id` target with no GCNS main row blended with its own `missing_10mas` copy — G13 now runs on every missing row), RG4 (the degraded H1 blend target keeps the star's own `source_id`; name half = candidate + head, K3 both sides, degraded path only), RG2 (H4 note on letter **or** domain, domain classed with the component's otype), RG3 (a `** …` / otype-`**` missing row — or the target's own copy by SIMBAD identity — is not a 5″ neighbour; radius-family lookup, honours the TIC hook), RG5 (`failed` xray tiers when the failed lookup left `no_identity`; `not_authoritative` on an H1-miss `none`, surfaced through both callers' typeless path), RG7 (radius families `not_queried` after an astrometry all-fail). Targeted `/code-review high`: 10 findings — 7 fixed, #5 → WB as N1 (MSG 312, S1 without a main row), #3 kept as WB's RG4 rule (stated to WB), #9 subsumed by #8. Re-vendor (Greg ran the copy): class_states `0502174c…`, fork8 `c5e900c5…`, fork9 `1e333643…`; item 9 → 0.08–0.27, `marginal_state` → 14 %; the class numbers quoted in this plan (e.g. §4's K class median 0.7085 → 0.7090) are superseded by the files. Suite 3759 / 110 / 0; live `test_cr26_live` + `test_cr25_live` 18 passed / 1 skipped (61 Cyg). WB MSG 313: N1 → keep S1 as scoped (system rows can be the only GCNS record of real stars — GJ 667 AB); the RG4 reading agreed. No change.
- **Whole-gate re-run (WB MSG 315): GREEN on all of MSG 311**, plus two disclosure defects → fixed. RG8: each blend-partner radius-lookup failure (TIC / Gaia call failed or timed out, or the family forced unreachable) → a `wind_model.notes` entry naming the partner, the family and the status (`xray_catalog.NOTE_PARTNER_RADIUS`; no flag), kept even when the XMM guard demotes. RG9: an H1 no-row miss carries its note + `not_authoritative` whatever tier sets the rate (non-coronal and G10 returns included), and on the evolved route both subcommands keep them when they discard the model (`stellar_wind.h1_carry` on the new `h1_miss` marker; `cr26_flags` on `compute_two_layer_boundary`). Targeted `/code-review high`: 10 findings — 8 folded (incl. 4 tests), the radius-family reuse refactor skipped (no behaviour), the count finding done here. Suite 3767 / 110 / 0.

## 13. Session hand-off (2026-09-27, end of the build session)

**State:**
- CR-26 is built through CP5 and **uncommitted**. `git status` shows the CR-26 files modified or untracked; see the §6 file list, plus `.gitignore`, `core/catalog.py` (the Greg-approved Gaia banner fix), `tests/conftest.py`, `tests/data/` and `data/cr26/`.
- **Do not change the working tree** until WB re-gates GREEN (MSG 309). WB is running a 6-step re-gate plan with its own data harvester in a fresh WB session.
- **Channel:** the last APP message is MSG 308 (build complete) and the last WB message is MSG 309. Re-arm the watcher with `last=309`.
- **If WB reports RED:** triage each finding. A genuine CR-26 defect gets fixed, with a test, a targeted `/code-review`, and the suite re-run (one heavy job at a time); then post the fix MSG. A spec question goes back to WB first.
- **When WB reports GREEN:** Greg signs the FULFILLED flip. Then:
  1. commit CR-26 only, directly on `main` (no branch), with the attribution lines;
  2. push, and post the SHA to WB;
  3. `git mv PHASE_CR26_PLAN.md completed_plans/` and index it in `completed_plans/README.md`; fix the plan-path mentions in `docs/integration.md` and `docs/testing.md` (both say "moves to `completed_plans/` at the CR close");
  4. update the memory note.
- CR-24 is next in WB's chain; don't touch it until asked.

**Channel watcher** (a background shell; exits on a new non-APP MSG; re-arm with the new `last` after each one):
```bash
while true; do hit=$(grep -E '^## MSG [0-9]+' /home/greg/Claude/coordination-channel.md | grep -v 'FROM: APP ·' | awk -v l=309 '{n=$3+0; if (n>l) print}' | head -5); [ -n "$hit" ] && { echo "$hit"; exit 0; }; sleep 15; done
```

**Where everything is:**

| What | Where |
|---|---|
| Contract (spec) | `/home/greg/Claude/scifiWorldBuilding-Claude/design-lab/star-system-analysis/spaceapp-change-request-CR26-xray-tier-wind-model.md` |
| Data (WB-owned; vendored in `data/cr26/`) | `/home/greg/Claude/scifiWorldBuilding-Claude/research/exclusion-boundary-medium-physics/cr26-w5-data/` |
| Channel (rulings MSG 285–309) | `/home/greg/Claude/coordination-channel.md` |
| APP contract docs | `docs/integration.md` — the CR-26 block after CR-25 |
