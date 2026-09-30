# PHASE CR-24 + CR-31 + CR-32: per-star V_ISM, `--wind-speed` on the Wood class paths, and Gaia-timeout stdout

**Status: COMPLETE — built 2026-09-30; WB re-gate GREEN + Greg's three FULFILLED lines (MSG 337); committed + pushed CR-32 `05a80c9`, CR-31 `cbe9571`, CR-24 `94f709d`.** This covers one build round, one WB re-gate and three FULFILLED lines. It
lands as **three sequential commits on `main`, in the order CR-32 → CR-31 → CR-24** (Greg, Q9, channel MSG 323).

**Contracts.** These live in the WB repo `scifiWorldBuilding-Claude`, under `design-lab/star-system-analysis/`. The
contracts are the authority; this plan is APP's build of them.
- `spaceapp-change-request-CR24-exclusion-vism-vectorial-derive.md`, cited as **§CR-24.n**, A0–A9, **§Units**,
  **§What**.
- `spaceapp-change-request-CR31-wind-speed-on-wood-class-paths.md`, cited as **CR-31.n** and **CR-31 acc n**.
- `spaceapp-change-request-CR32-gaia-timeout-stdout.md`, cited as **CR-32.n** and **CR-32 acc n**.

**Data.** `research/exclusion-boundary-medium-physics/cr24-data/cr24_wood2021_vism.csv` in the WB repo. Its md5 is
`ffd164238d055d9134fe65bb9f9df097`, and it has 36 rows. It is WB-owned: APP vendors it byte-identical and never edits it.

**Channel.** MSG 319 (ping), 320 (ack), 321 (hand-off), 322 (APP questions), 323 (Greg's Q9 ruling), 324 (WB answers,
Greg-approved).

---

## 0. Ground truth (verified 2026-09-30 at HEAD `520b7b4`, tree clean)

- `argparse` has `allow_abbrev` on, and it is never set in the repo. So `--cloud` resolves today as an abbreviation of
  `--cloud-temp` on both exclusion subcommands (A5's trap).
- `compute_simbad_lookup` (`core/databases.py:217`) fetches no PM, no RV and no RV grade. `simbad_astrometry`
  (`databases.py:701`) fetches PM and parallax through the CR-26 TAP seam `_simbad_cr26_tap`, but not the RV. No
  code anywhere fetches `rvz_radvel` or `rvz_qual`. No code does SkyCoord velocity transforms.
  `core/kinematics.py` reads Hypatia UVW and is unrelated.
- **Live TAP probe (2026-09-30).** The query was `SELECT b.main_id, b.ra, b.dec, b.pmra, b.pmdec, b.plx_value,
  b.rvz_radvel, b.rvz_qual, b.rvz_type FROM basic b JOIN ident i ON i.oidref = b.oid WHERE i.id IN (…)`. Results:
  - `V* EZ Aqr` gives grade D.
  - `HD 239960B` gives grade E.
  - `* 70 Oph A` gives grade A.
  - `*  70 Oph` gives grade A.
  - The columns exist on SIMBAD TAP `basic`, so the "Open item: how SIMBAD returns `rvz_qual`" is answered: the
    `basic.rvz_qual` column.
- `_simbad_cr26_call` (`databases.py:667`) is bounded, retries once, has a per-family breaker, and caches **answers
  only**. A timeout, unreachable or error result is never cached (`catalog_cache.cached` stores only a returned
  value). WB's MSG 324 check is confirmed by construction, and a test will pin it (§5, T-V6).
- `resolve_wind_inputs` has two production callers:
  - `core/exclusion_boundary.py:332`, which serves every `exclusion-boundary` path.
  - `core/exclusion_system.py:523`, which serves every component.
- The two branches of `resolve_wind_inputs`:
  - The **legacy branch** carries the CP4-finding-1 relaxation at `exclusion_wall.py:595-601`.
  - The **ladder branch** forces 400 km/s.
  - `mass_loss_tier` is derived **after** the resolve (`eb.derive_mass_loss_tier`). The one exception is `--object`:
    `query.py:936` passes the tier `object_preset` explicitly.
- `_combined_wind_wall` (`exclusion_system.py:244`) and `_combined_wind_band` (`:343`) both pass `r_ex=None`. They
  take only v_wind, v_ism, c_ms, n_cloud and t_phase from the dominant member, which is the `max()` by wdot, so the
  first-listed member wins a tie. f_shock, m_shock_min and c_ms_band are **not** passed and default.
- The measured-tier ISM note (`DISCLOSURE_MEASURED["ism"]`, `stellar_wind.py:150`) is emitted from exactly one
  place, `_measured_disclosures`.
- CR-26 `measured_result` does not record which id hit (`stellar_wind.py:518-560`). The tier result carries
  `measured.row_key`, though.
- **The head → A-record lookup on `exclusion-boundary`** (`xray_catalog.py:971`) runs **only when the head is not
  itself a measured row**. CR-24 needs the head's A record for velocity in every case, so CR-24 resolves it itself
  (§3.3).
- **CR-32:**
  - `_gaia_stdout_to_stderr()` = `contextlib.redirect_stdout(sys.stderr)` is entered inside `_attempt` on the
    `_call_with_watchdog` daemon thread. It is also entered on the legacy/async path (`catalog.py:311`). It is the
    only stdout reassignment in production code.
  - `query.py` writes its result once, via `_out()` → `print(json.dumps(...))` (`query.py:78`).
- Suite baseline: **3767 passed, 110 skipped, 519 subtests, 0 failures**.

## R. Rulings index (channel). Each ruling is folded into the body at the § given.

| # | Ruling | Where |
|---|---|---|
| Q1 | A failed A-record lookup (timeout, unreachable or error) makes the head's velocity `unavailable`, with the failure status, and never falls back to the system record. "Does not resolve" means answered-empty only. A measured row matched through CR-26's table hit still sets step 4. | §3.3 |
| Q2 | On `--star`, a measured-row star always runs the lookup and the derive, whichever step set V_ISM. The different-route note compares the derive with the V_ISM the wall used. | §3.4 |
| Q3 | The ⚑1 fallback applies only when `exclusion-system --star` resolved ≥ 2 components. A single component uses its own record. The letterless-head rule applies at any component count. The D-C1 note needs ≥ 2. | §3.3 |
| Q4 | The cut, `clic_domain` and UVW's d all use the **velocity record's** parallax, with no substitution. With none, v★ is `unavailable` and precedence falls through to step 4, else step 6. A fallback component keeps its own PM and parallax. | §3.2, §3.4 |
| Q5 | The zone lower-bound case gets a test-only env hook, not a public key. Under the hook, every A6-scored field reads as a real lower bound. | §3.8 |
| Q6 | The RV-injection hook has a per-record form `"<main_id>=<rv>[:<g>]"` (several allowed); a bare `"<rv>[:<g>]"` means every lookup. | §3.8 |
| Q7 | `measured_row` `v_ism_kms` is emitted as a float. | §3.4 |
| Q8 | CR-31 keys on the **condition**, not a list of spellings: tier `legacy_row` or `object_preset` **and** the rate is that path's Wood row or preset rate. The system-level `--wind-state` and `--wind-speed` spellings are included. o-star and `hot` are excluded. Note wording: "a Wood-convention class rate (legacy_row)" and "a Wood-convention preset rate (object_preset)". | §2 |
| Q9 | Three sequential commits, CR-32 → CR-31 → CR-24 (Greg). | §7 |
| Q10 | Acceptance 2 adds `gaia-tap` and `gaia-astrophysical`. WB also runs banner-off and byte-identity checks on `close-binary-census`. The stdout proxy must pass through `encoding`, `buffer`, `isatty`, `fileno` and `flush`. | §1 |
| open items | The RV comes from a new bounded SIMBAD TAP velocity family. Each component uses its CR-26-resolved record. The DQ3 interval is found by exact breakpoints. The data is vendored under `data/cr24/`, md5-pinned. Bad new inputs exit 2. The velocity family caches successes only. | §3 |

---

## 1. CR-32: keep every result on stdout (commit 1)

**Root cause.** `contextlib.redirect_stdout` swaps the **process-global** `sys.stdout`. A watchdog-abandoned attempt
never runs its `__exit__`, so stdout stays pointed at stderr. There is a subtler failure too (CR-32 acc 2). A retry
entered while the abandoned attempt is still inside its redirect saves *stderr* as "the old stdout" and "restores"
it on exit.

**Fix: a thread-scoped diversion, `core/catalog.py`.**
- **`_ThreadRoutedStdout`** is a small proxy class. It holds the wrapped stream. `write` and `writelines` check a
  module-level `threading.local()` flag and write to `sys.stderr` when the **current thread** is diverted, else to
  the wrapped stream. `__getattr__` passes every other attribute through (`encoding`, `buffer`, `isatty`, `fileno`,
  `flush`, `errors`, `closed`, …; WB's MSG 324 watch-out). `flush` flushes both streams.
- **`_gaia_stdout_to_stderr()`** keeps its name and its call sites. It becomes a context manager that:
  1. Installs the proxy **once**, lazily: if `sys.stdout` is not already a `_ThreadRoutedStdout`, it wraps the
     current `sys.stdout`. The install happens under a lock, so two concurrent attempts cannot double-wrap.
  2. Sets the thread-local flag on entry and restores the flag's previous value on exit.
  3. **Never** reassigns `sys.stdout` back. The proxy is transparent for every non-diverted thread, so leaving it
     installed is safe. It is also what makes an abandoned attempt harmless: its flag stays set on its own daemon
     thread, so its late banner still goes to stderr.
- **Why the lazy wrap is safe with the test harness.** `tests/_queryharness.run_query_inproc` and
  `test_cr26_wiring.py:494` use `redirect_stdout(StringIO)`. The proxy then wraps the StringIO. When the harness
  exits, `redirect_stdout` puts back its saved stream and the proxy is dropped with it.
- **GUI.** The same functions run in-process, and the proxy is transparent to the Qt thread. No GUI change is needed.
- **The proxy's specification (CP0 F-B4, F-B5):**
  - It resolves `sys.stderr` **at write time**, not at install, so a harness `redirect_stderr` still sees the
    banner.
  - `write` returns the wrapped stream's return value. `writelines` is routed as well.
  - A write to `.buffer` from a diverted thread goes around the routing. That is no worse than today and is an
    accepted caveat.
  - **`None` streams (a `pythonw` GUI launch):** if `sys.stdout is None`, the proxy is not installed and the
    diversion is a no-op. A diverted write while `sys.stderr is None` is dropped. Both cases are tested.
- **Widen the legacy/async diversion (CP0 F-B2).** Today `close-binary-census` (async path) diverts only the import.
  `launch_job_async` writes astroquery's `INFO: Query finished.` log line to stdout, outside the diversion. With a
  thread-scoped diversion, `_run` can safely cover `launch_job(_async)` + `get_results` too, so that line moves to
  stderr. This is disclosed to WB as the one intended stdout change on that subcommand (MSG 325; accepted MSG 326).
- **Retry-then-success hook (CR-32 acc 2; CP0 F-B1).** `SPACE_APP_GAIA_FORCE_FIRST_ATTEMPT_TIMEOUT=1`.
  - The **first** attempt of each bounded call runs inside the diversion, and **before** the astroquery import.
    That placement avoids leaving an abandoned thread holding the module import lock. The attempt:
    1. prints the marker line `"[SPACE_APP test hook] late banner from the abandoned attempt"` once its own
       watchdog has fired (it waits on the watchdog's expiry);
    2. then **blocks forever on a never-set Event**. It never leaves the diversion, which is exactly the abandoned
       state of the bug.
  - Under the hook, the first attempt gets its own short watchdog (0.5 s). The retry keeps the configured bound, so
    a live re-gate retry can still finish at the default 60 s. No hook value can silently do nothing.
  - The retry runs normally. The attempt counter is a closure `nonlocal`, one per `gaia_tap` call.
  - The breaker does not trip, since `_trip_gaia_circuit` runs only on a final timeout. This is pinned by a test.
  - Offline tests stub the TAP job. The re-gate runs it live.
  - **Red-first:** T32-1, T32-2 and T32-6 are run on the unfixed tree and must fail there (§10).
- **Unchanged (CR-32.3):**
  - The markers, the bound, the retry and the circuit breaker.
  - Every exit code and value.
  - The legacy/async `_run` path keeps the same context manager, now thread-scoped (it runs on the main thread, so
    behaviour there is identical).

**Subcommands covered (CR-32.1, Q10).** `exclusion-system --star`, `exclusion-boundary --star`, `dossier`,
`compare-stars`, `binary-orbit`, `binary-stability-auto`, `multiplicity`, `gaia-tap` (sync), `gaia-astrophysical`,
and `close-binary-census` (async path; banner and byte-identity only). The fix sits at the single gateway, so every
path is covered by construction. The tests pin each subcommand (§5).

**Files:** `core/catalog.py`; `tests/test_cr32_stdout.py` (new); `tests/test_cr26_wiring.py` (the existing banner
test is adapted if it asserts `sys.stdout is sys.stderr` inside the attempt; its intent is kept);
`docs/integration.md` (CR-32 note under the CR-19 section); `docs/testing.md`; CLAUDE.md count.

## 2. CR-31: force 400 on `legacy_row` / `object_preset` Wood rates, plus the CR-31.2 rescale note (commit 2)

**One shared helper, `core/exclusion_wall.py`:**

```
cr31_wind_speed(tier, inputs, prov, wind_speed, *, resolve) -> (inputs, prov, note | None)
```

- **CR-31.1 (force).** The condition is:
  - `tier ∈ {"legacy_row", "object_preset"}`,
  - **and** `inputs["mass_loss_source"] == "astrosphere_wood"` with `prov["mass_loss_source"] == "class_default"`
    (the source came from a Wood row, `quiet`, `solar` or `active`; the `--object` sun and m-dwarf presets map to
    those rows),
  - **and** `prov["wind_speed"] == "supplied"`.

  When it holds, the helper **re-resolves** through `resolve(wind_speed=None)`. That path already gives
  `v_wind` 400 with `astrosphere_wood_forced`, because the Wood row plus no speed is today's forced path. It then
  returns the note in CR-26's ignored-input form:
  - `legacy_row`: "--wind-speed {v:g} ignored: a Wood-convention class rate (legacy_row) forces v_wind = 400 km/s —
    to use another speed, supply the rate (--mass-loss-msun-yr) with it"
  - `object_preset`: "… a Wood-convention preset rate (object_preset) …"

  **Rate guards (CP0 F-B8):**
  - For `legacy_row`, the helper also requires `prov["mass_loss"] == "class_default"`: the rate is the row's.
  - For `object_preset`, the preset rate travels as `mass_loss_msun_yr`. `query.py` sets `object_preset` only when
    no user rate was given. But `derive_mass_loss_tier` returns `object_preset` **before** it checks for a rate
    (`exclusion_boundary.py:213`), so a direct core caller with a user rate would be forced.
  - The fix reorders `derive_mass_loss_tier` so that "a rate that is not the preset's → `supplied`" is checked
    first. `query.py` always passes the tier explicitly, so this is byte-identical for it. The helper then keys on
    the tier.

  o-star and `hot` map to `o_hot`, which is `recipe`, so the source condition excludes them (Q8).

  **`--wind-speed 400` on these paths** is forced too. The value is unchanged, but provenance goes from `supplied` to
  `astrosphere_wood_forced`, and the ignore note is added. This matches CR-26's `NOTE_IGNORED_SPEED`, which fires at
  any value. It is disclosed to WB (MSG 325; accepted MSG 326) and in `docs/integration.md`.

  The combined-zone wall takes the dominant member's `v_wind`, so a forced 400 moves it too. That is expected.
- **CR-31.2 (the rescale note, nothing else changes).** The condition is:
  - `tier == "supplied"`,
  - **and** the source is `astrosphere_wood` with provenance `class_default` (row-defaulted, not an explicit
    `--mass-loss-source`),
  - **and** `prov["wind_speed"] == "supplied"`,
  - **and** `v_wind != 400`.

  The helper returns the note and leaves the inputs untouched: "the supplied rate is paired with {v:g} km/s
  unrescaled; a Wood-convention rate (an astrosphere measures Ṁ·V_w at 400 km/s) must be supplied × 400/v". An
  explicit `--mass-loss-source astrosphere_wood` already forces 400 (source provenance `supplied`), so it never
  reaches this note.
- **Where the tier is known.** The tier is derived after the first resolve, and the helper runs after that
  derivation:
  - `compute_two_layer_boundary` computes `tier` (`mass_loss_tier` or `derive_mass_loss_tier`), then calls the
    helper. If the helper re-resolved, the `inputs` and `prov` used by the wall, the echo and the band walls are the
    forced ones.
  - `exclusion_system` does the same in its per-component wall loop. There the tier is derived at `:547`, so the
    derivation moves **before** the `compute_wall` call. It keeps the `if tier is None:` guard. Its wdot is
    exactly today's `inputs["wdot"] if domain in (MS, EVOLVED) else None`, which is identical under forcing, since
    forcing changes v_wind only. The CR-31 note is appended to `c["cr26_notes"]` **before** the `_cr26_fields` call
    (CP0 F-B9).
  - The note goes into `extra_notes` / `c["cr26_notes"]` and so into `wind_model.notes`. Legacy and preset paths
    carry CR-26's skeleton `wind_model`.
- **System-level spellings (Q8).** `_comp_wind_params` already resolves the system `--wind-speed` into
  `wind_speed`, and CR-25.4 carries the system `--wind-state` into the component's row. Because the condition is on
  the resolved inputs, every spelling is covered:
  - `--component "id=S,mass=1.0" --wind-state solar --wind-speed 800`
  - `id=S,mass=1.0,wind_state=solar,wind_speed=800`
  - `id=S,mass=0.3,wind_class=active,wind_speed=800`
  - `--mass-msun 1.0 --wind-state solar --wind-speed 800`
  - `--object sun|m-dwarf --wind-speed 800`
- **Unchanged.** The ladder tiers are already forced, and their note is untouched. So is `noncoronal_row`. The
  `supplied` tier with an explicit non-Wood source or an explicit Wood source is unchanged, and so is every call
  without `--wind-speed`.

**Files:** `core/exclusion_wall.py`, `core/exclusion_boundary.py`, `core/exclusion_system.py`,
`tests/test_cr31_wind_speed.py` (new), `docs/integration.md`, `docs/testing.md`, CLAUDE.md count.

---

## 3. CR-24: per-star V_ISM (commit 3)

### 3.1 Vendored data and loader: `data/cr24/cr24_wood2021_vism.csv` + `core/ism_velocity_tables.py` (new)
- The file is copied byte-identical from WB. Auto mode blocks cp-from-WB, so **Greg runs the copy** (as in CR-26)
  and APP verifies the md5.
- `.gitattributes` gets `data/cr24/*.csv -text`.
- The loader follows the `core/stellar_wind_tables.py` pattern:
  - `CR24_MD5 = {"cr24_wood2021_vism.csv": "ffd164238d055d9134fe65bb9f9df097"}`, with a row count of 36.
  - `SPACE_APP_CR24_DATA_DIR` overrides the data directory.
  - Reads are md5-verified, then parsed with `csv.DictReader`, with structural checks: unique `row_key`,
    float-parsable `wood2021_vism_kms`, and θ.
  - A **cross-check against CR-26's MEASURED table.** The `row_key` sets must be equal, and each row's
    `simbad_main_id` must match CR-26's after whitespace collapse. This is the "keyed by the same `row_key`"
    promise.
  - Results are memoised per directory.
  - Any failure raises `Cr24DataError`, which the exclusion callers turn into `{"error"}` (exit 1), like
    `Cr26DataError`.
- The same module holds **the 15 R&L 2008 Table 16 clouds** (V0, l0, b0, χ²; §Units, transcribed from the spec
  table) and **the nine-cloud DQ2 set**: LIC, Leo, Eri, G, Mic, Aur, Blue, NGP, Hyades. The set is **derived in
  code** as the clouds within 15 km/s of the LIC vector, then asserted equal to that list. A test pins the
  |v_cloud − v_LIC| values quoted in §Units to ±0.01.
- Cartesian vectors are computed from (V0, l0, b0) as U = V0·cos b·cos l, V = V0·cos b·sin l, W = V0·sin b. The
  rounded triple is never stored (A5's rule).

### 3.2 The pure velocity math: `core/ism_velocity.py` (new; no network, no Qt)
- **`space_velocity(ra, dec, plx_mas, pmra, pmdec, rv)`** returns `(U, V, W)`. It uses astropy
  `SkyCoord(ra, dec, distance=1000/plx pc, pm_ra_cosdec, pm_dec, radial_velocity, frame="icrs").galactic.velocity`,
  the heliocentric **Galactic** frame (never LSR or GalacticLSR), in km/s. A test pins the frame against
  Johnson & Soderblom 1987 hand matrices.
- **`rv_gate(rv, grade, uvw_with_rv)`** returns `(passes, reason)`:
  - Grade D or E gives `reason = "grade"`.
  - |v★| > 1000 gives `reason = "ceiling"`.
  - A missing RV gives `reason = "missing"`.
- **`sky_plane_floor(v_rv0, v_cloud, los_unit)`** returns |P⊥(v★_t − v_cloud)|, where d = v★_t − v_cloud and the
  result is √(|d|² − (d·l̂)²). l̂ is the heliocentric Galactic line-of-sight unit vector from (ra, dec). This is
  **not** the naive |v★_t − v_cloud|; the anchors are 70 Oph B 33.4 against 40.0, and σ Dra 67.47.
- **`resolve_velocity(record, *, primary_rv=None)`** returns the `space_velocity` object, `velocity_provenance`
  and the notes:
  - `uvw`: PM, parallax and a gated-pass RV (own, or the primary's with `rv_source: primary`).
  - `tangential_lower_bound`: PM and parallax, but the RV is missing or gated.
  - `unavailable`: PM or parallax missing, or plx ≤ 0 (Q4; no substitution).
  - `space_velocity` = `{U, V, W, total, convention, pmra, pmdec, plx, rv, rv_grade, rv_used, rv_source}`. Under
    `tangential_lower_bound` it takes the RV-0 UVW plus `rv_used: false`. It is null when `unavailable`.
  - **Echo semantics (CP0 F-A3; A3 pins 70 Oph B):**
    - `rv` and `rv_grade` always echo the component's **own** SIMBAD values.
    - `rv_used` is whether the component's **own** RV passed the gate.
    - `rv_source` is `own` when its own RV set the vector, `primary` under the ⚑1 fallback, and `null` when no RV
      was used (`tangential_lower_bound`).
    - So 70 Oph B reads `rv` −10.0, `rv_grade` E, `rv_used: false`, `rv_source: primary`, `uvw`.
  - **A null `rvz_qual` with an RV present (F3, ruled MSG 326):** only D and E are gated, so it passes the grade
    rule. It is still ceiling-checked, and the note names the missing grade.
  - **An unusable PM or parallax (F4, ruled MSG 326).** PM and parallax are treated as unusable when **either**:
    - the sky-plane floor is ≥ 1000 km/s, **or**
    - the heliocentric speed at RV 0 is > 1000 km/s. No RV could then pass the ceiling, since |v★|² =
      |v★_t|² + RV².

    The result is `velocity_provenance: unavailable`, with a note naming the quantity that fired. Precedence falls
    through to step 4, else step 6.
- **`v_ism_from(vel, cloud)`**:
  - `uvw` gives |v★ − v_cloud|.
  - `tangential_lower_bound` gives the sky-plane floor against that cloud.
- All new numbers are emitted **unrounded** (§CR-24.5 Precision).

### 3.3 The velocity lookup and whose record: `core/ism_velocity.py` network half
- **The seam.** A new `databases.simbad_velocity(ident, family="velocity")` runs through the existing
  `_simbad_cr26_call`. That call is bounded by `SPACE_APP_SIMBAD_TIMEOUT`, retries once, has the per-family
  breaker `velocity`, and caches answers only (§0). The ADQL is:

  ```
  SELECT TOP 1 b.oid, b.main_id, b.ra, b.dec, b.pmra, b.pmdec, b.plx_value, b.rvz_radvel, b.rvz_qual
  FROM basic b
  WHERE b.main_id = '<raw resolved main_id>'
  ```

  The `main_id` is always one already returned by the identity resolver. See the CP0 F-A1 bullet below.

  The cache service name is `simbad_cr24_velocity`. It returns `(row, None)`, `(None, None)` for answered-empty,
  or `(None, code)`.
  - A module-level seam, `ism_velocity._velocity_seam = databases.simbad_velocity`, is added to
    `tests/conftest.py` `_SEAMS`, so no offline test can reach it.
  - Hook `SPACE_APP_SIMBAD_VELOCITY_FORCE_UNREACHABLE` fails **only** the velocity lookup, per A7. Identity
    resolution and CR-26 are untouched, so a measured row still matches.
  - `velocity_status ∈ {ok, timeout, unreachable, error}` maps from the call's code.
  - A velocity row with no RV passes `rv = None`. `rvz_radvel` is read in km/s whatever the `rvz_type`.
- **The velocity query is by raw `main_id` (CP0 F-A1 / F-C1, HIGH).**
  - `a_candidate` collapses whitespace, giving `'* 70 Oph A'`. SIMBAD `ident` stores `'*  70 Oph A'`. The exact
    `ident.id =` match misses it: live, `'* 70 Oph A'`, `'* 61 Cyg A'` and `'HD 239960 A'` all come back empty.
  - So the velocity TAP always queries by the **raw, uncollapsed SIMBAD `main_id`** of a record already resolved by
    the identity resolver: `WHERE b.main_id = '<raw main_id>'`, on `basic` only. A collapsed or candidate string
    is **never** sent to the velocity query.
  - An offline test pins that the seam receives `'*  70 Oph A'`.
- **Whose record (§CR-24.1; D-W2-1, D-G2-2, D-C1, B-1; Q1, Q3).**
  - **A letterless head, on both subcommands.** A head is a target where `xray_catalog.a_candidate(main_id)` is
    not None.
    1. The A candidate is resolved with **CR-26's own resolver**, `xray_catalog._identity_lookup(cand)`. That is
       astroquery `query_object`, which normalizes the id's spacing. It is bounded, has its own `identity`
       breaker, and has the `SPACE_APP_SIMBAD_IDENT_FORCE_UNREACHABLE` hook.
       - CR-26 already made this call when the head is not itself a measured row. CR-24 then **reuses** the
         result: `StarWindInputs` gains internal `a_record` / `a_record_status` fields, which are never emitted.
       - Otherwise, when the head is a row, or on `exclusion-system` component A out of scope, CR-24 calls it
         itself.
    2. A resolved record whose **collapsed `main_id` differs** from the head's (CR-26's comparison,
       `xray_catalog.py:972`) is **the A record**. The head's velocity, and its parallax for the cut and d, come
       from it, queried by its raw `main_id`.
    3. A record whose collapsed `main_id` **equals** the head's is "a head whose A candidate resolves to itself"
       (Sirius, Procyon; CP0 F-A4). The head keeps its own record, and **no** D-C1 note is added.
    4. An **answered-empty** result means "does not resolve" (EZ Aqr). The head keeps its own record, and the D-C1
       note is added on `exclusion-system --star` when ≥ 2 components were resolved.
    5. A **failed** lookup (timeout, unreachable or error) gives `unavailable`. The `velocity_status` is the
       identity failure's code, with the failed-lookup note naming the A candidate. It **never** falls back to the
       head's record (Q1).
  - **A7.** `SPACE_APP_SIMBAD_VELOCITY_FORCE_UNREACHABLE` fails only the velocity TAP. Identity resolution is its own
    family, as A7 requires ("identity resolution unaffected").
  - **Call count.** One identity lookup, often the cached or reused CR-26 one, plus one velocity TAP per record.
  - **`exclusion-boundary --star <X>`, not a letterless head.** The lookup uses X's resolved `main_id`: the named
    record only, with no fallback.
  - **`exclusion-system --star`, ≥ 2 components** (the binary branch of `_resolve_system_from_star`).
    - The primary is the head. Its velocity comes from the A record, as above.
    - Component B uses its own record, by `comp_sl`'s raw `main_id`. When `comp_failed` (its identity lookup
      failed), B's velocity is `unavailable` with that status. The candidate string is never sent to the TAP.
    - If B's RV is missing or gated, B takes **the A record's RV** when that RV passes the gate
      (`rv_source: primary`, the note naming the A record). It keeps its own PM and parallax. The A record here is
      the one resolved above, even when the emitted primary is the system record (70 Oph).
    - B is `tangential_lower_bound` when:
      - the A record has no usable RV;
      - the A lookup failed; or
      - the A candidate is **answered-empty**. No A record resolves, so B never borrows the head's own, possibly
        blended, record (§CR-24.1; B-1, D-C1; WB MSG 328).

      A **same-record** head (Sirius, Procyon) is different: its A record *is* its own record, which B may borrow.
      The fallback runs one way: A never borrows B's RV (D-W3-3).
    - **The D-C1 note** is added **only** when the A candidate is answered-empty (not same-record) and the emitted
      primary is the head's own record: "the primary '<id>' is the target's own SIMBAD record (no separate A
      component resolves) — its own RV is used; it may be a blend".
  - **`exclusion-system --star`, one component** (`_single_body_component`: a secondary, a WD or BD, a wide
    pair, or no orbit). The component uses its own record, or the A record if it is a letterless head. There is
    no fallback (Q3).
  - **`--component`, `--spectral-type`, bare `--mass-msun`, `--object`.** No lookup:
    `velocity_status: not_run`, `velocity_provenance: null`, `space_velocity: null`.
- **When the lookup runs (Q2; CP0 F-A10).**
  - It runs on every `--star` target and on every `exclusion-system --star` component, windless and unmodeled
    included. A2 has Luhman 16 and WISE 0855 reporting their velocity but no V_ISM, and A9 covers Sirius B.
  - The one exception is a **non-measured** star where step 1 or 2 set V_ISM, which gives `not_run`.
  - The **velocity fields** are on every result and component. The **V_ISM fields** follow the medium block's
    presence.
  - **Cost.** One extra bounded TAP call per head, plus one per component. This is well within the CR-26 budget.
    Parallel `--star` runs are noted by A8 as flaky and are re-run, not scored.

### 3.4 The V_ISM precedence: `ism_velocity.resolve_v_ism(...)` (pure)

**Inputs:**
- supplied `v_ism`
- `lb_cavity`
- `cloud`
- `clic_max_pc`
- the CR-26 model's used tier
- the matched measured `row_key`
- the velocity result, with the velocity record's parallax distance
- `path_has_lookup`

**Steps (⚑8 table):**
1. `supplied`.
2. `--lb-cavity`: 26 with `assumed`.
3. `--cloud`, when v★ resolves. On a step-4 star it needs `uvw`; a floor falls through with the D-W3-2 note.
4. **The measured row: the CR-26 model's used tier is `measured`.** The `row_key` is taken from
   `wind_model.measured.row_key`, which is CR-26's own table hit, including a letterless head's A read and an H1
   string match. It is looked up in the CR-24 table (§3.1 guarantees the key exists). The result is
   `wood2021_vism_kms` as a float with `measured_row` (Q7). `--component main_id=` reaches it the same way, through
   its offline CR-26 model.
5. **The LIC derive:** `--star` only, when d (from the velocity record's plx) ≤ `clic_max_pc` and v★ resolves.
6. 26 with `assumed`.

**Outputs:**
- `v_ism_kms`, `v_ism_provenance`, `v_cloud_used`, `v_cloud_chi2` and `m_f` (computed in §3.6).
- `v_ism_derived_kms`: measured-row stars only. It is the step-3 or step-5 derive, or null when v★ is
  `unavailable`, or when the star is beyond the cut with no `--cloud`. It is computed whichever step set V_ISM (Q2).
- `clic_domain`: set when step 3 or 5 set V_ISM, split at 7 pc using d.
- A **mode**: `point` or `lower_bound` (`derived_tangential_lower_bound`).
- **Null and default rules, stated explicitly (CP0 F-A9):**
  - `v_ism_range_kms` and `wall_range_vism_au` are null for `measured_row`, `supplied` and `assumed`.
  - `wall_route_provisional` is `false`, never null or absent, whenever the medium block is present and the
    mode is `point`.
  - `v_ism_derived_kms` is null whenever `velocity_status` is `not_run`, and on every non-measured star.
  - `v_cloud_used` and `v_cloud_chi2` are null unless step 3 or 5 set V_ISM.
  - `m_f` is always V_ISM / c_ms at `v_ism_kms`.
  - On every zone that carries `combined_wind_wall_au`, `combined_wind_route_provisional` is `false` and
    `combined_wind_wall_range_vism_au` is null, unless the zone is in lower-bound mode.
- **The no-identity paths (`--spectral-type`, bare `--mass-msun`, `--object`) use steps 1 or 6 only** (CP0 F-A11).
  `--lb-cavity` there is ignored with a note, 26 either way. **`--component`** runs no lookup, but takes steps 1,
  2, 4 or 6: `v_ism=`, `lb_cavity=` or the system `--lb-cavity`, a measured `main_id=` (A4), else 26 (WB MSG 328).

**Notes (§CR-24.5 list):**
- the gated RV (grade form or ceiling form)
- the primary RV used
- a failed lookup
- "beyond --clic-max-pc — V_ISM assumed 26"
- `beyond_7pc`
- `--lb-cavity` or `--v-ism` over a measured row, naming the row's value
- `--cloud` over a measured row, in both the `uvw` form (the row's value named) and the floor form (row kept)
- ignored flags on no-lookup paths
- the D-C1 note

**The ⚑4 note replacement.** `DISCLOSURE_MEASURED["ism"]` becomes a template: "A measured Ṁ was inferred at the
V_ISM Wood 2021 Table 3 lists for this star ({n} km/s); this run uses {v} km/s ({prov})." `_measured_disclosures`
leaves a placeholder token, which the wiring (§3.6) fills once V_ISM is known. **Every** measured-tier result gets
the new wording, whatever V_ISM (A0 exception). `tests/test_cr26_model.py:712`'s token check is updated to match
(its "CR-24" token goes).

**The different-route note.** When `v_ism_derived_kms` is `derived`, not a floor, the route is computed at the
derive. If it differs from the wall's route at the V_ISM the wall used, the note reads: "the derived V_ISM {d} km/s
would set route {r1}; the wall uses {v} km/s ({prov}) → {r2}".

### 3.5 The range evaluator: `ism_velocity.wall_over_interval(...)` (pure, exact)

The wall model is piecewise in V. Within each piece it is constant (`wind_term`) or monotone decreasing
(`bow_shock`: wt/√C(M_f), where C rises with M_f; capped: ∝ 1/V). So the extremes over [a, b] sit at the interval
ends and at the **route boundaries**, taken one-sidedly.

**`breakpoints(rate, v_wind, medium, r_ex)`** returns the three route-change speeds in (a, b). The CP0 math review
proved these sufficient: every cap onset and every edge-crossing is a continuous kink, not an extremum.
- the shock threshold V = M_shock_min·c_ms
- the r_ap = r_ex speed
- the burial speed, where f·r_ap = r_ex

When `r_ex` is None there is no standoff, so none of the bow-shock breakpoints exist. No bisection is needed. The
cap onsets, about 390·(v_wind/400) on the wind-term branch and about 779·(v_wind/400) on the bow-shock branch, are
used only in tests.

**`extremes(extract, fn, a, b, bps)`** evaluates `fn(V)` (a `compute_wall` call) at a, at b, and at each breakpoint
±ε, with ε = 1e-9·V. `extract` is a scalar extractor (CP0 F-C3): `wall_au` for the wall, `wall_band_au[0]` for a
lower band edge, `wall_band_au[1]` for an upper edge. It returns:
- the max, with its route and the **lowest** V that gives it (O-2)
- the min, with its route, its V, and which kind set it (CP0 F-C5):
  - `at_vmax`, with the route at V_max. This is capped when the cap binds there, otherwise the uncapped wall.
  - `just_under_burial`
- A prototype of this evaluator on the real `compute_wall` reproduced every A3 and A6 anchor, including 13.6727
  (A6 floor-45 edge), 1.9062, 1.4149 and 1.3685. A dense grid alone misses A6's capped peak at the ±0.5 %
  tolerance, which confirms the exact form.

**Provisional and branch use the pre-cap route (CP0 F-C2 / F-A5).**
- `compute_wall` gains an additive internal key, `wall_route_precap`: the route before the astropause or windtime
  cap overwrote it. Callers copy keys explicitly, so it never leaks into output.
- `wall_route_provisional` = r_ex is not None **and** the burial speed > max(floor, M_shock_min·c_ms) **and**
  max(floor, M_shock_min·c_ms) < V_max. The last condition is WB MSG 328: a supplied `--m-shock-min` or `--c-ms` can
  lift the threshold past 1000. A test covers exactly that case (threshold > 1000, burial speed above it → false),
  and the cross-check set includes it. This is the contract's own closed form (D-W3-1). A test cross-checks it against "a pre-cap
  `bow_shock`/`bow_shock_marginal` in the evaluated set".
- The DQ2 `cloud_set_branch` test and the zone's `geometry_marginal` also compare **pre-cap** routes: `wind_term`
  against bow-shock.
- A post-cap label would miss a bow-shock that is always capped (constructed case: Ṁ 4 Ṁ☉, r_ex 1 AU).
- No card star is affected. Confirmed by WB (F2, MSG 326).

**The lower-bound note (CP0 F-A6).** Every lower-bound result, single star or zone, carries the note. Its text:
- When `wall_route_provisional` is true: "V_ISM is a lower bound (no usable RV) — the route is provisional; the
  wall is the largest the bound allows; `v_ism_kms`, `m_f` and `r_ap_au` are at the floor, the wall and its band
  at {V} km/s".
- The zone form reads "the zone's medium member '<id>' has a lower-bound V_ISM …".
- When `wall_route_provisional` is false (A6's floor-200 case), "the route is provisional" becomes "no bow-shock
  route is possible above the floor", and every other clause is kept. The note never contradicts the flag (F1,
  ruled MSG 326).

**`verdict_marginal` under DQ3 (CP0 F-A7).**
- The three existing triggers are taken from the **floor** `compute_wall` call only.
- The call at the max's V supplies only the wall, band, route and reason fields.
- Its own `verdict_marginal` is discarded. At EZ Aqr's max it fires `apex_near_standoff`, and A3 requires
  `[lower_bound_provisional]` alone.
- `verdict_marginal = bool(reasons)`.

It serves:
- **DQ3, single star:** `wall_au`, the reported route, `wall_band_au`, `wall_reason`, `wall_exceeds_standoff` and
  `wall_to_standoff_ratio`, all at the max's V. `v_ism_kms`, `m_f` and `r_ap_au` stay at the floor (O-2).
  `wall_range_vism_au` = [min, max].
- The lower-edge note, per D-G2-1, names which kind set the min.
- **`wall_route_provisional`** is true when a bow-shock route (`bow_shock` or `bow_shock_marginal`) occurs anywhere
  in the evaluated set (D-W3-1). A route change caused only by the cap does not count.
- **D-C3 band edges:** each edge of `wall_band_wind_au` gets its own `extremes` at its own rate, and takes its max.
  Its route is taken at that V. `wall_band_wind_routes` is reported when the two routes differ, and
  `wall_band_wind_exceeds_standoff` uses the upper edge.
- **Zone lower bound (D-W2-2):** the same function with the zone's comparator.

**Tests and cross-check.** A dense-grid test (10⁵ points) checks every anchor to within the anchors' tolerances. It
catches a missed breakpoint. The exact form is needed for A6's ±0.5 %.

**DQ2 cloud-set range.** For a `derived` V_ISM, `v_ism_from` is evaluated for each of the 9 clouds, using the same
velocity (`uvw`). This gives `v_ism_range_kms` = [min, max] and `wall_range_vism_au` = [min, max] of `compute_wall`
at each. `cloud_set_branch` is set when the branch set {wind_term} ∪ {bow_shock, bow_shock_marginal} is mixed. The
note names the clouds whose branch differs from the point's, and states the set's scope (LIC-like vectors at the
default medium, not a bound).

### 3.5b The one shared application helper (CP0 F-A2, HIGH)
`exclusion-system` components compute their wall directly (`exclusion_system.py:519-557`), not through
`compute_two_layer_boundary`. So the V_ISM application lives in **one helper**,
`ism_velocity.apply_v_ism(inputs, prov, v_ism_res, *, r_ex, wind_class, cr26, standoff)`. Both
`compute_two_layer_boundary` and the per-component loop call it, in place of their bare `compute_wall` plus
`wind_band_walls`.

**Its output:**
- the reported wall dict (point, or the DQ3 max at O-2's V)
- the `wall_band_wind_*` fields (D-C3 per edge under a lower bound)
- `wall_range_vism_au`, `wall_route_provisional`, `verdict_marginal` and `verdict_marginal_reasons`
- `r_ap_au` and `m_f` at `v_ism_kms`
- the notes

**What the per-component values feed.** Under DQ3, `c["wall"]`, `c["wall_band_hi"]`, the hazard flags and the
zone inputs take the **reported** wall (O-2). They feed `_wall_envelope`, zone eligibility and `combined_wind_phase`
(§CR-24.3). A3's EZ Aqr anchor runs on `exclusion-system --star`, so it exercises this path.

### 3.6 Wiring `exclusion-boundary` (`query.py` + `core/exclusion_boundary.py`)
- **Flags (both subcommands):**
  - `--cloud NAME`: validated against the 15 names. An unknown name gives a usage error, exit 2, listing all 15
    names. `--cloud 300` is therefore an error and never sets `cloud_temp_k` (A5).
  - `--clic-max-pc PC`: finite and > 0, else exit 2. Default 15.
  - `--lb-cavity`: `store_true`.
  - Existing `--v-ism`: gains finite and > 0 validation, exit 2. This is a new exit-2 case; today a ≤ 0 value runs
    the "invalid medium" wall.
- **`--star` paths** (the MS branch, the evolved branch, and windless or unmodeled for the velocity fields):
  1. After the CR-26 model is built, run §3.3 (velocity) and §3.4 (precedence).
  2. Pass `v_ism` plus a new `v_ism_provenance` override into `compute_two_layer_boundary`, then into
     `resolve_wind_inputs`, then into `_medium`. The override is additive: absent means today's
     supplied/assumed.
  3. In `lower_bound` mode, `compute_two_layer_boundary` receives `v_ism_interval=(floor, 1000)` and applies §3.5
     after its point `compute_wall`.
  4. In `point` + `derived` mode, it receives the cloud-set V list for DQ2.
  5. The evolved branch, which drops a non-measured model, keeps the velocity and V_ISM fields. They don't depend
     on the model.
- **No-lookup paths** (`--spectral-type`, bare `--mass-msun`, `--object`):
  - `velocity_status: not_run`, and V_ISM by step 1, 2 or 6.
  - `--cloud` and `--clic-max-pc` are ignored with a note, and so is `--lb-cavity`.
  - `--lb-cavity` on a no-identity path is noted as ignored, since the value is 26 either way.
- **New output fields**, on every result where the medium block is present:
  - V_ISM fields: `v_cloud_used`, `v_cloud_chi2`, `v_ism_derived_kms`, `v_ism_range_kms`, `clic_domain`, `m_f`,
    `wall_range_vism_au`, `wall_route_provisional`, `verdict_marginal_reasons`.
  - Velocity fields, on **every** result, including windless and unmodeled: `velocity_provenance`,
    `velocity_status`, `space_velocity`.
- **`verdict_marginal_reasons`.** `compute_wall` gains an additive return key listing its three existing triggers
  in order (`c_ms_straddle`, `bow_shock_marginal`, `apex_near_standoff`). Callers copy explicit keys, so the new key
  never leaks. The wiring appends `cloud_set_branch` and `lower_bound_provisional`. Under DQ3 the three existing
  triggers are the ones at the floor, per the §CR-24.5 table's "evaluated at `v_ism_kms`".
  `verdict_marginal = bool(reasons)`.
- **Notes home.** New notes go to `wind_model.notes`, through the existing `cr26_notes` / `extra_notes` channel.
- **The windless and unmodeled early returns** gain only the three velocity fields. There is no medium block and
  there are no V_ISM fields there (§CR-24.5 presence).

### 3.7 Wiring `exclusion-system` (`core/exclusion_system.py`)
- **`_resolve_system_from_star`.** Each component dict gets the internal `velocity_ident` plan from §3.3: its
  record, whether it is a letterless head, and the primary link. The velocity lookups run in the compose step,
  after the CR-26 models exist, because step 4 needs the used tier.
- **System flags.** `--cloud`, `--lb-cavity` and `--clic-max-pc` join `system_wind`.
  - On `--star` they reach every component.
  - On `--component`, `--lb-cavity` reaches components that lack their own `lb_cavity=`, while `--cloud` and
    `--clic-max-pc` are ignored with a note (§CR-24.2).
  - `_parse_component_spec` gains the `lb_cavity` key (true/false, case-insensitive). It is also validated in the
    argparse `_cr26_component` type, so a bad value exits 2.
  - `v_ism=` gains finite and > 0 validation there, also exit 2.
- **The D6 medium echo.** Every component whose domain is MS or EVOLVED gets `eb._wind_echo(c["wall_inputs"],
  c["wall_prov"])` merged into its emitted dict. That includes `none_no_wind`. Windless and unmodeled components
  get none. The keys and presence are exactly `exclusion-boundary`'s, and A9 checks this key by key.
  - `mass_loss_msun_yr` and `mass_loss_provenance` are already emitted; the echo writes the same values, and a
    test asserts they are equal.
  - After CR-31, this is where CR-31 acc 1's `wind_speed_kms` 400 `astrosphere_wood_forced` shows.
- **D5, the zone route (§CR-24.4).**
  - `_combined_wind_wall` and `_combined_wind_band` take `r_ex = comparator` (the zone's largest member
    standoff, the same one `wall_exceeds_standoff` and `combined_wind_band_exceeds_standoff` compare against).
  - They take the **medium member's full medium**: v_ism, c_ms, n_cloud, f_shock, m_shock_min and c_ms_band.
  - The medium member is chosen by the largest point rate, then the larger mass, then the first listed (DQ4).
  - Each band edge gets its own route.
  - New zone fields:
    - `combined_wind_wall_route`
    - `combined_wind_wall_band_wind_routes` (when the edge routes differ)
    - `combined_wind_route_comparator_au`
    - `combined_wind_route_geometry_marginal`
    - `combined_wind_medium_member`
    - `combined_wind_route_provisional`
    - `combined_wind_wall_range_vism_au`
  - **The long axis.** This is the zone's **standoff envelope** at the larger of periastron and apastron. It is
    computed by the **existing** `_zone_envelope(members, "peri")` and `(members, "apo")` (`exclusion_system.py:131`),
    both always evaluated whatever `--phase` is, and maxed. No new envelope code is written (CP0 F-A12 / F-C9).
    Verified offline on A6: `long_axis_au.apastron` = 24.912859 ✔. For 70 Oph, A6 quotes 76.16, and the build
    pre-check re-derives it.
  - **The medium member supplies the medium inputs only (CP0 F-A17).** Those are v_ism, c_ms, n_cloud, f_shock,
    m_shock_min and c_ms_band. `v_wind` and `t_phase` stay with today's dominant member (the `max()` by rate,
    first listed on a tie). An equal-rate pair of different masses therefore keeps today's v_wind and t_phase, and
    A0 holds. The two choices coincide except on an exact rate tie.
  - `geometry_marginal` is true when `compute_wall` at the long axis gives a different route from the comparator.
    Under a lower-bound medium, both are taken at the reported wall's V (O-2).
  - **A0.** At M_f < M_shock_min, which covers every V_ISM < 30 at the default medium, passing r_ex changes
    nothing: the route is `wind_term` either way. Passing f_shock, m_shock_min and c_ms_band from the medium member
    changes nothing at the defaults. The zone's `verdict_marginal` is still discarded. A test pins byte-identity
    for A6's no-`v_ism=` case (3.702; [0.590, 20.643]; true).
- **Zone lower-bound medium (D-W2-2).** When the medium member is in `lower_bound` mode, §3.5 is evaluated for the
  combined wall against the comparator:
  - `combined_wind_wall_au` is the max, and `combined_wind_band_au` is taken at the same V.
  - Each combined band edge gets its own max (D-C3).
  - `combined_wind_route_provisional` and `combined_wind_wall_range_vism_au` are set, and the zone note and
    lower-edge note are added.
  - A `derived` medium member gets no zone range (the member's own fields are the signal).

### 3.8 Test hooks (test-only; documented as such in `docs/integration.md`, not in the contract surface)
- **`SPACE_APP_SIMBAD_VELOCITY_FORCE_UNREACHABLE=1`** fails the velocity family only (A7).
- **`SPACE_APP_CR24_INJECT_RV`**:
  - Its form is `"<rv>[:<grade>]"` (every lookup) or `"<main_id>=<rv>[:<grade>]"`, with several entries allowed,
    comma-separated (Q6).
  - The `main_id` match collapses whitespace on **both** the hook key and the returned `main_id` (CP0 F-A14), so
    `* 70 Oph A` matches `*  70 Oph A`.
  - It replaces `rvz_radvel` and `rvz_qual` **after** the fetch and **before** the gate. The default grade is A.
  - Its uses: the A3 ceiling and σ Dra cases, and D-W3-3 (a gated RV on `* alf Cen A` only, then the head goes to
    `tangential_lower_bound` and does not borrow B's).
- **`SPACE_APP_CR24_COMPONENT_VISM_FLOOR="<id>=<km/s>[,…]"`** (Q5):
  - It puts a `--component` without `v_ism=` or `lb_cavity=` into `lower_bound` mode at that floor.
  - Every field then reads as a real lower bound: `derived_tangential_lower_bound`, `v_ism_range_kms`
    [floor, 1000], the DQ3 wall and band, the zone fields, and the notes.
  - `velocity_status` stays `not_run`, because no lookup ran, and `clic_domain` is null, since there is no
    distance. Both are disclosed in `docs/integration.md` as the hook's tells.
  - **Precedence slot (CP0 F-A13):** the hook sits **below step 4**, so a measured `main_id=` still takes the row,
    and above step 6.
  - It reads `v_cloud_used` LIC and `v_cloud_chi2` 2.2, as a default derive would.
- **`SPACE_APP_GAIA_FORCE_FIRST_ATTEMPT_TIMEOUT=1`**: CR-32 (§1).

---

## 4. Files touched

| File | CR | Change |
|---|---|---|
| `core/catalog.py` | 32 | thread-routed stdout proxy; `_gaia_stdout_to_stderr` rewritten; first-attempt hook |
| `core/exclusion_wall.py` | 31, 24 | `cr31_wind_speed` (31); `compute_wall` `verdict_marginal_reasons` key; `_medium` `v_ism_provenance` override (24) |
| `core/exclusion_boundary.py` | 31, 24 | CR-31 helper call; V_ISM plumbing, DQ2 and DQ3 application, new fields |
| `core/exclusion_system.py` | 31, 24 | CR-31 helper call and tier-derive move; velocity per component; D6 echo; D5 zone; new fields; `lb_cavity` key |
| `core/stellar_wind.py` | 24 | ⚑4 note template (`DISCLOSURE_MEASURED["ism"]`) |
| `core/databases.py` | 24 | `simbad_velocity` (CR-26 TAP family) |
| `core/ism_velocity.py` (new) | 24 | resolver, gate, floor, precedence, range evaluator |
| `core/ism_velocity_tables.py` (new) | 24 | CSV loader, md5, cross-check; the 15 clouds; the DQ2 set |
| `data/cr24/cr24_wood2021_vism.csv` (new, WB-owned) | 24 | vendored byte-identical |
| `.gitattributes` | 24 | `data/cr24/*.csv -text` |
| `query.py` | 24 | flags, validators (exit 2), `--star` wiring, `lb_cavity` in `_cr26_component` |
| `tests/conftest.py` | 24 | `_velocity_seam` added to `_SEAMS` |
| `tests/test_cr32_stdout.py` (new) | 32 | §5 |
| `tests/test_cr31_wind_speed.py` (new) | 31 | §5 |
| `tests/test_cr24_*.py` (new: `tables`, `velocity`, `range`, `wiring`, `system`, `live`) | 24 | §5 |
| `tests/test_cr26_model.py`, `tests/test_cr26_wiring.py` | 24, 32 | ⚑4 token update; banner test adapted |
| `docs/integration.md`, `docs/testing.md`, `docs/core-modules.md`, `docs/query-commands-index.md` (flags), CLAUDE.md | all | contract, test catalog, suite count, core map |

## 5. Tests (offline unless marked; every CR-24 network seam is stubbed through conftest)

**CR-32 (`test_cr32_stdout.py`)**
- **T32-1.** An attempt is abandoned inside the diversion (a stub `GaiaClass` that blocks on an Event, plus a tiny
  bound). Afterwards, `sys.stdout` writes from the main thread reach the real stdout, and a late print from the
  abandoned thread reaches stderr.
- **T32-2.** Retry-then-success under the first-attempt hook with a stub job. The result is not degraded. Main-thread
  output reaches stdout, and the late marker line goes to stderr.
- **T32-3.** Proxy attribute passthrough: `encoding`, `buffer`, `isatty`, `fileno`, `flush`, and `print(file=…)`.
- **T32-4.** Nested and concurrent diversion. Two threads divert at once, and the main thread is unaffected. The
  install is idempotent (no double wrap).
- **T32-5** (CP0 F-B3). Every subcommand in §1 runs **in-process** through `run_query_inproc`, not as a subprocess,
  which would escape the conftest stubs and reach SIMBAD, VizieR and SB9. The setup:
  - the conftest stubs
  - a fake `astroquery.gaia` in `sys.modules`, the `test_cr26_wiring.py:476` pattern
  - `SPACE_APP_CATALOG_CACHE=0`, because a cache hit bypasses `_attempt`
  - `reset_gaia_sync_circuit()`
  - the first-attempt hook

  stdout parses as JSON, carries no banner, and the late marker is on stderr. Only `gaia-tap` and
  `gaia-astrophysical`, which reach Gaia directly, also get a subprocess case with a `sitecustomize` Gaia stub.
- **T32-6.** A stub async job calls astroquery's `log.info("Query finished.")`. On `close-binary-census`'s path it
  lands on stderr (CP0 F-B2).
- **T32-7.** The `None`-stream guards (F-B5). The harness holds its redirect open until the late marker is seen
  (an Event), which removes the race (F-B4).
- The live cases (acc 1 and 2) are in `test_cr32_live.py`, gated on `SPACE_APP_RUN_LIVE=1`.
- The existing CR-26 banner test still passes: the banner goes to stderr and stdout stays clean.

**CR-31 (`test_cr31_wind_speed.py`)**
- CR-31 acc 1 and 2, table-driven, in-process through `run_query_inproc`. These cases need no network.
  - The **forced** cases give walls 6.0 and 13.416, `astrosphere_wood_forced`, and the path-named note. They are:
    - `--mass-msun 1.0 --wind-state solar --wind-speed 800`
    - `--object m-dwarf --wind-speed 800`
    - `--object sun --wind-speed 800`
    - the three `exclusion-system` spellings from Q8
  - The **supplied** cases: `--mass-msun 1.0 --mass-loss-msun-yr 2e-14 --wind-speed 800` (4.243, no note);
    `--wind-state solar --mass-loss-msun-yr 4e-14 --wind-speed 800` (6.0 plus the rescale note); `--spectral-type
    K2V …` and `--object m-dwarf --mass-loss-msun-yr 4e-14 …` (plus the note); `--mass-loss-source
    astrosphere_wood` (forced, no rescale note).
  - `--wind-speed 400` on a supplied Wood pairing gives no rescale note.
  - `--object o-star --wind-speed 800` and `--wind-state hot` are honoured as today.
  - `noncoronal_row` gives A1V 3.000 at 800, unchanged.
  - A ladder tier gets the CR-26 note, unchanged.
- **Added (CP0 F-B7):**
  - `exclusion-system --component "id=S,mass=1.0,wind_state=solar,mass_loss_msun_yr=4e-14,wind_speed=800"` gives
    tier `supplied`, wall 6.0 and the rescale note.
  - A `--star` supplied case, offline through the stubbed seams: the CR-26 model's `supplied` tier plus the
    rescale note.
  - `--wind-speed 400` on `legacy_row` is forced, `astrosphere_wood_forced`, with the note.
  - `--wind-state solar --mass-loss-source astrosphere_wood --wind-speed 800` is forced, with no CR-31 note.
  - A system-level `--wind-state hot --wind-speed 800` component is honoured.
  - The F-B8 direct core call (`object_preset` provenance plus a user rate) goes to `supplied` and is not forced.
- **Stage-2 assertions on `exclusion-system` (CP0 F-B6a).** The D6 echo does not exist until stage 3, so stage 2
  asserts through core in-process: `c["wall_prov"]["wind_speed"]`, the wall and the note. The echo assertions
  (`wind_speed_kms` 400, `astrosphere_wood_forced`) are added in stage 3.
- **Byte-identity.** Every case without `--wind-speed` is compared against a pre-change JSON snapshot. The snapshots
  are captured into the test fixtures before the change. **From stage 3 on**, this comparison uses the same shared
  by-name strip of CR-24's additive keys as the A0 harness (CP0 F-B6b). One helper, `tests/_cr24strip.py`, is
  introduced in stage 3 and applied to the CR-31 snapshot test at the same time.

**CR-24**
- **`test_cr24_tables.py`:**
  - The md5, the row count, the no-`\r` rule and the `git check-attr` rule.
  - `row_key` equality with CR-26 MEASURED, and the `simbad_main_id` match.
  - The override dir, and `Cr24DataError` → exit 1.
  - The 15 vectors against V0, l0, b0.
  - The DQ2 set derived equals the 9 names, and each |Δ| in §Units is within 0.01.
- **`test_cr24_velocity.py`:**
  - The frame: Galactic, not LSR, against JS87.
  - A2 `[WB-ref]` UVW from the reference astrometry: Barnard's, Kapteyn's and EV Lac to ±1.
  - The gate: grade D and E, the ceiling, and missing.
  - The floor against the naive value: 70 Oph B 33.4 against 40.0, σ Dra 67.47.
  - `unavailable` rules.
  - Record selection:
    - head → A through `_identity_lookup`
    - the velocity seam receives the **raw** `'*  70 Oph A'` (F-A1)
    - same-record gives no D-C1 note (Sirius)
    - answered-empty gives the note (EZ Aqr, ≥ 2 components)
    - failed gives `unavailable` (Q1)
    - single component (Q3)
    - the ≥ 2 fallback, one way (D-W3-3)
  - The `rv_used` / `rv_source` echo semantics (F-A3).
  - A null grade.
  - A floor ≥ V_max.
  - The ⚑4 placeholder never leaks into any emitted note, on every path (F-A16).
  - The injection hook in both forms.
  - **T-V6:** a failed velocity call is never cached, and a success is.
- **`test_cr24_range.py`** (pure `[hand]` anchors):
  - EZ Aqr (floor 34.9): 2.632 `wind_term`, range [1.369, 2.632], band [1.755, 3.509], wind band [0.618, 14.639],
    provisional, reasons.
  - The EZ Aqr V_max-390 variant: 1.415.
  - σ Dra hook: 7.265, wind band [1.792, 29.37], routes.
  - The A6 zone at floors 34.9, 45 and 200: 3.702; [2.468, 4.936]; [0.590, 14.542] / [0.590, 13.673]; range
    [1.906, 3.702] at ±0.5 % / [1.925, 3.702]; provisional true / true / false; the lower-edge kind.
  - The dense-grid cross-check.
  - DQ2: Sirius A, Wolf 359, Ross 248 and Procyon A ranges and reasons. These use the reference UVW from WB's
    Appendix A, fixed in the test as inputs.
- **`test_cr24_wiring.py`** (`exclusion-boundary`, stubbed seams plus stubbed identity):
  - The precedence steps 1–6 and every override note.
  - `--cloud` step 3 against a measured row: `uvw` against a floor (D-W3-2).
  - The `clic_domain` flag and the 7 pc note.
  - The cut note.
  - The ⚑4 wording on every measured-tier result.
  - The different-route note.
  - Presence (windless and unmodeled: velocity fields only).
  - The exit-2 validators, including `--cloud 300` never setting `cloud_temp_k`.
  - `--cloud` and `--clic-max-pc` ignored on no-lookup paths.
  - A7 (velocity hook, row still matches).
  - A4 EV Lac 3.786 and the GJ 887 and ε Ind points (hand).
  - The 70 Oph `exclusion-boundary` head → A: 30.67, `measured_row`.
- **`test_cr24_system.py`:**
  - D6 echo parity against `exclusion-boundary`, key by key (A9 cases, offline), and none on windless or unmodeled.
  - `c_ms=15` supplied.
  - `lb_cavity=` precedence and the system flag.
  - D5 zone: A6 `v_ism=45` (2.336; [1.557, 3.115]; [0.590, 13.03]; routes; false; comparator 20.51; long axis
    24.91; member A), `v_ism=125` (1.921, geometry_marginal true), and the A 25 / B 45 case (3.702, member A).
  - The tie-break rules.
  - A0 byte-identity without `v_ism=`.
  - The 70 Oph fallback (B → `rv_source: primary` from `* 70 Oph A`, 35.6) and the head from the A record (36.4),
    with stubbed velocity rows carrying the reference astrometry.
  - The D-C1 note.
  - `--component main_id=* eps Eri` → 27 `measured_row`, `not_run`, no network.
- **`test_cr24_live.py`** (gated `SPACE_APP_RUN_LIVE=1`): A1 (27 of 27, median ≤ 0.7), A2 and A5 spot checks.
- **Byte-identity harness (A0).** The CR-26 A8-style offline cases are snapshotted before the CR-24 edits
  (`--spectral-type`, `--mass-msun`, `--object`, and `--component` without `main_id=`). After CR-24 they must be
  equal but for the additive keys, which the harness strips by name.

## 6. `/code-review` checkpoints (`/code-review high` on the working tree; findings triaged and folded before the next stage)

| CP | After | Scope focus |
|---|---|---|
| **CP0** | this plan | 2–3 independent plan-review agents (now): contract coverage A0–A9, CR-31 acc 1–5, CR-32 acc 1–5; the §3.3 record design; the §3.5 exactness; the commit split |
| **CP1** | CR-32 built | thread safety of the proxy; harness interaction; every Gaia path; no stdout regressions |
| **CP2** | CR-31 built | the condition against Q8's spellings; byte-identity without `--wind-speed`; the tier-derive move in `exclusion_system` |
| **CP3** | CR-24 pure layer (§3.1, §3.2, §3.4, §3.5) | math, frame, floor, gate, evaluator breakpoints, data cross-check |
| **CP4** | CR-24 wiring (§3.3, §3.6–§3.8) | precedence end to end, record choice, D5 and D6, presence, notes, exit codes, A0 |
| **CP5** | whole bundle, before the build report | a cross-CR review of the combined diff, plus the three stage patches applied in order on a clean worktree, each passing the suite |

## 7. The three-commit mechanics (Greg, Q9; reworked per CP0 F-B10)

Each stage is snapshotted as a **git tree object**, not as patches or tarballs. This needs no branch, so the
main-only rule holds, and the working tree is never touched.

1. **Snapshot each stage** (end of stage K). Write the tree to a scratch index:
   `GIT_INDEX_FILE=<scratch>/idxK git add -A -- . ':!PHASE_CR24_31_32_PLAN.md'`, then
   `GIT_INDEX_FILE=<scratch>/idxK git write-tree` gives `treeK`. `treeK` and its fingerprint
   (`git diff 520b7b4 treeK | md5sum`) are recorded in §12. The plan file is excluded from every stage and is
   committed in the close-out docs commit, as with CR-26.
2. **Per-stage docs.** Each stage writes its own CLAUDE.md suite count and `docs/testing.md` history entry, so each
   commit is truthful on its own. Stage K+1 then edits them forward.
3. **A later fix to an earlier stage** (e.g. CP4 touching `catalog.py`) is made in the working tree. `treeK..tree3`
   are then re-snapshotted, so the fix does not leak into a later stage's delta. Each earlier stage is rebuilt in a
   throwaway worktree from `treeK-1` + that stage's changes + the fix, and re-snapshotted there. The throwaway
   worktree is removed afterwards.
4. **CP5 check.** A throwaway `git worktree` is set up at `520b7b4`:
   - First run the baseline suite there with the **main** `venv/bin/python`. A worktree has no gitignored
     `data/space_app.db`, `data/dust/` or cache, so its counts are compared against this baseline, not against
     3767.
   - Then `git read-tree -u --reset treeK` for K = 1, 2, 3, running the suite at each.
   - `tree3` must equal the working tree WB re-gates: the working-tree `write-tree` must equal `tree3`.
5. **After GREEN plus each FULFILLED line:**
   - `sha1 = git commit-tree tree1 -p 520b7b4 -m <CR-32 msg>`, then `sha2 = … tree2 -p sha1`, then
     `sha3 = … tree3 -p sha2`.
   - `git update-ref refs/heads/main sha3 520b7b4`, then `git reset -q` (mixed; the working tree is untouched and
     already equals tree3).
   - Push per CR with `git push origin shaK:main`, in order. Greg runs the push if auto mode blocks it.
   - Each SHA is posted to the channel.
   - If a FULFILLED line lags, only the SHAs up to it are pushed.

## 8. Re-gate pre-check (APP, live, before the build report; one heavy job at a time)
- A1: the 27-star run, reporting the median and the largest.
- A2, A4, A5: the hand and WB-ref values.
- A3: EZ Aqr, GJ 860 B, 70 Oph (both subcommands), α Cen, and σ Dra through the hook.
- A6: by construction through the floor hook; 70 Oph live (41.10; 76.16 long axis).
- A7.
- CR-31 acc 1–3.
- CR-32 acc 1–3 on every §1 subcommand, including `gaia-tap`, `gaia-astrophysical` and `close-binary-census`.
- A0: the no-lookup paths are diffed against `git archive 520b7b4`.
- Every letterless head in the A8 battery: the velocity record's `main_id` equals CR-26's A read wherever CR-26 made
  one (70 Oph → 36.44).
- `close-binary-census`: stdout is JSON only, and the INFO line is on stderr.
- CR-32 red-first: T32-1, T32-2 and T32-6 fail on stage-0 code.

## 9. Risks and accepted caveats
- **Resolver agreement.** The velocity record is resolved by CR-26's own `_identity_lookup` and queried by raw
  `main_id`, so it cannot diverge from CR-26's A read. The §8 pre-check still confirms this on every A8 letterless
  head.
- **Live SIMBAD astrometry drift** is within A's ±1 km/s tolerance. The A1 median is a live check.
- **A new exit-2 on `--v-ism ≤ 0`, non-finite.** Today such a value runs to an "invalid medium" null wall with
  exit 0. The contract rules exit 2, and this is disclosed in the build report.
- **The stdout proxy stays installed for the process lifetime** once a Gaia call ran. It is transparent to every
  non-diverted thread, and the attribute passthrough is tested.
- **Cost:** one or two extra bounded SIMBAD TAP calls per `--star` target or component.

## 10. Build sequence (after the CP0 fold and Greg's go)
1. Stage 1, CR-32: write the tests first and confirm T32-1, T32-2 and T32-6 are **red** on the unfixed code. Then
   code, then **CP1**, then snapshot `tree1`.
2. Stage 2, CR-31: capture the byte-identity snapshots, then code and tests, then **CP2**, then snapshot.
3. Stage 3, CR-24:
   - Capture the A0 snapshots first.
   - Greg copies the CSV from WB (md5 verified).
   - Build the pure layer and its tests, then **CP3**.
   - Build the wiring and its tests, then **CP4**.
   - Docs, then snapshot.
4. **CP5**, the three-stage worktree check, the §8 live pre-check, then the build report on the channel (fingerprints
   per stage and cumulative, suite count, the ruling-by-ruling map). All still git-held.
5. WB re-gate, then Greg's three FULFILLED lines, then the three commits and the push (§7), then the close-out docs.

## 11. Review record

**CP0 (2026-09-30).** Three independent plan-review agents ran:
- (A) CR-24 contract coverage: 3 HIGH, 4 MED, 9 LOW.
- (B) CR-31, CR-32 and the commit mechanics against the code: 1 HIGH, 6 MED, 4 LOW.
- (C) CR-24 math and record design, with a prototype evaluator and live TAP checks: 1 HIGH, 2 MED, 5 LOW, plus
  confirmations.

All findings are folded, as follows.

**HIGH:**
- A1 = C1, 70 Oph's double-space `ident` miss: the velocity TAP queries by raw resolved `main_id`, and the A record
  is resolved by CR-26's `_identity_lookup` (§3.3).
- A2, the per-component wall path skipped DQ2/DQ3: fixed by the one shared helper (§3.5b).
- A3, the `rv_used` semantics: stated in §3.2.
- B1, the retry hook did not reproduce the bug: the first attempt blocks forever inside the diversion, with its
  own short watchdog, and the tests run red-first (§1).

**MED:**
- A4, same-record gets no D-C1 note: §3.3.
- A5 = C2, the pre-cap route for provisional and branch: §3.5.
- A6, the lower-bound note text: §3.5, with the false-provisional wording asked of WB.
- A7, the floor-only triggers: §3.5.
- B2, the INFO log line on the async path: §1, disclosed to WB.
- B3, in-process T32-5: §5.
- B4, the proxy details: §1.
- B6, the stage-2 assertions and the shared strip helper: §5.
- B7, the added CR-31 cases: §5.
- B10, tree-object commits: §7.
- C3, the band-edge extractor: §3.5.

**LOW:**
- A8 = C5, the min kind and floor ≥ V_max (asked of WB): §3.2, §3.5.
- A9, the null and default rules: §3.4.
- A10, the velocity fields on windless components: §3.3.
- A11, no-lookup steps 1 and 6: §3.4.
- A12 = C9, reuse `_zone_envelope`: §3.7.
- A13, the floor hook's slot and values: §3.8.
- A14, the hook key is collapsed: §3.8.
- A15, a null grade (asked of WB): §3.2.
- A16, the placeholder leak test: §5.
- A17, the medium member supplies the medium only: §3.7.
- B5, `None` streams: §1.
- B8, the `object_preset` guard: §2.
- B9, the tier-move details: §2.
- B11, the breaker is not tripped: §1.
- C4, no bisection: §3.5.
- C8, call count: §3.3.

**Confirmations:**
- The prototype evaluator on the real `compute_wall` reproduced every A3 and A6 anchor.
- The sky-plane floor and the Galactic (not LSR) frame are verified live: EZ Aqr 34.943; 70 Oph B 33.431 against
  naive 40.039.
- The head derives are verified: α Cen A 18.165; 70 Oph A 36.438.
- The Q8 condition catches every WB spelling, verified by offline probes.
- A0 zone byte-identity is verified: 3.7021; [0.5902, 20.6428]; true.

 **WB's rulings on the open items (MSG 326):** F1–F4 are ruled and folded; F4 adds the RV-0 speed test. Both FYIs are
accepted: `close-binary-census` stdout is scored as JSON-only, and the `--wind-speed 400` provenance change is
scored as intended. The items asked of WB were:
- the false-provisional lower-bound note wording
- a null `rvz_qual`
- a floor ≥ 1000
- the pre-cap route for provisional and branch
- FYIs: the `close-binary-census` INFO line moving to stderr, and `--wind-speed 400` becoming
  `astrosphere_wood_forced` on the CR-31 paths

## 12. Build log (2026-09-30, Greg's go; WB told "build started" in MSG 330)

| Stage | Tree | Fingerprint (`git diff` prev→tree) | Default suite |
|---|---|---|---|
| base `520b7b4` | — | — | 3767 passed / 110 skipped / 519 subtests |
| 1 CR-32 | `9527b2bfbed06706609415ce158a274e69baf33b` | `128280bb2c277386e045e8c3cc586cff` | 3778 / 114 / 519 |
| 2 CR-31 | `bb0e31e69a737fdfe35fde471857c66fac143338` | `087194667afd4689e19203cdcee3c53a` | 3792 / 114 / 561 |
| 3 CR-24 | `cbee6cdb4ebdf8e0875608c02392402a7e6dab97` | `1d484e50a7ec4e7dfdb4bafb0be8a7a2` | 3850 / 118 / 609 |

The cumulative fingerprint (`git diff 520b7b4 tree3 | md5sum`) is `553bfd67852087695f873833a58a9299`. tree3 equals the working
tree, excluding this plan file. The CP5 dry run applied each tree in turn in a throwaway worktree and ran the suite at
each stage: base 3767, tree1 3778, tree2 3792, and the pre-CP5 tree3 3849, all green. The final tree3 = 3850 was run
on the working tree.

**Checkpoints:**
- **CP1 (CR-32):** 10 findings, 8 fixed.
  - The hook is now the bounded call's own first attempt, via `first_timeout`.
  - The proxy is installed on the caller's thread.
  - Recursion guards were added, and `isatty` / `encoding` follow the target.
  - T32-1 waits for both threads, and T32-6 uses astroquery's real `log.info`.
  - The docs were updated.
  - Accepted: an abandoned thread writing after a harness swap (live-only), and daemon-thread writes at exit (existing
    behaviour).
- **CP2 (CR-31):** 8 findings.
  - The Wood row under `noncoronal_row` went to WB (MSG 331) and was ruled in MSG 332: force keyed on the rate.
  - `object_preset` guards were added (unknown preset, caller-passed tier).
  - The core-provenance test became a combined-zone check.
  - The byte-identity baseline grew to 27 cases, captured from a `520b7b4` worktree.
  - The redundant gate was removed.
  - Declined: moving the rule into `resolve_wind_inputs`, because the tier is only known after the resolve.
- **CP3 + CP4 (CR-24), run as one review since both layers were built together:** 10 findings, all fixed.
  - Windless components get no V_ISM notes.
  - F4 now produces `unavailable` with no fallback derive.
  - CR-26's A-candidate identity result is reused (`a_record`).
  - A failed companion reports its failure class.
  - The D-C1 note appears only when the head's own RV is used.
  - The `--lb-cavity` note wording was corrected.
  - A head fetched only for the lend reports it.
  - The apex constant is read from `compute_wall`.
  - One boolean vocabulary, and dead parameters removed.
- **CP5 (cross-CR):** 10 findings.
  - Fixed: the ignored-flag notes on a skipped `--star` lookup (new `ism_velocity.star_v_ism`, shared by both
    subcommands); None guards on the zone lower-bound paths; the note order matched across the subcommands; the live
    count in CLAUDE.md; the guardrail reworded to name the zone helpers; `V_ISM_ASSUMED = ew._V_ISM_DEF`; a lazy head
    lend (the head is fetched only when B's own RV fails the gate); tree3 re-snapshotted.
  - Accepted: the CR-32 harness-swap caveat, as in CP1.

**Rulings added during the build:**
- MSG 332: CR-31 force keyed on the rate, whatever the tier.
- MSG 335: A1 scored 24 of 24 (23 on `exclusion-boundary`, plus 70 Oph A via `exclusion-system`). GJ 338 A / B and GJ 892
  are blocked by an existing regions error and handed to CR-27.

**Deviations from the plan:**
- CP3 and CP4 were merged.
- T32-5 runs in-process for `gaia-tap` / `gaia-astrophysical` only. Every other Gaia subcommand is covered by the
  single-gateway structural test plus `test_cr32_live.py`, because an in-process run of those would need their
  SIMBAD / VizieR stubs.
- The byte-identity fixtures were captured from the pre-change code: CR-31 in a `520b7b4` worktree, and CR-24 A0 from
  the stage-2 tree.

**Live pre-check (§8), all green:**
- A1: 23 of 23 on `exclusion-boundary` + 70 Oph A 36.44 on `exclusion-system`; median 0.45, max 61 Cyg A +2.42.
- A2 / A3 / A4 / A5 anchors: EV Lac 3.786, Wolf 359 1.268, σ Dra 4.023, EZ Aqr 2.6317611601220543 [1.369, 2.632],
  70 Oph 30.671 / 36.44 / 35.62, zone 41.10, Sirius [23.9, 50.1] `cloud_set_branch`, Procyon, Ross 248 [1.331, 2.474] +
  Blue / Eri / Aur / Mic, HD 69830 78.0 `beyond_7pc`, GJ 887 2.291, Kapteyn `--clic-max-pc 3` → 26, Wolf 359
  `--cloud G` 45.8, λ And 53 `measured_row`, Ross 154 11.3 / 4.189.
- CR-31 acc 1–3 offline.
- `--cloud 300` → exit 2.
