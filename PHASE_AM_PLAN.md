# Phase AM — `query.py` Catalog-Access Tier (VizieR + Gaia TAP + X-Match/HEASARC) & Binary-Census Subcommands

Implements `research/query-api-methods/catalog-access-and-binary-census-request.md` from the sibling
`scifiWorldBuilding-Claude` repo (spec created 2026-07-23, technical claims live-verified against
astroquery 0.4.11). This is the **first `query.py` subcommand family that makes LIVE NETWORK queries to
CDS VizieR and the ESA Gaia TAP archive** — same class as the GCNS import and the dust query path, not
the pure-math calculator packs. It is **`query.py`-only** (no CLI menu option, no GUI panel), like the
dust *query* subcommands and the Phase U–AL calculator packs.

> **Scope decision (2026-07-23):** built **AM-0 → AM-4** (all seven subcommands). Originally
> `besancon-query` was deferred, but a follow-on research pass (below) found the spec's fragility premise
> obsolete — the modern Besançon service is a clean UWS 1.0 REST API, not the dead 2003 email/FTP path —
> so it was built too.
>
> **Besançon research finding (2026-07-23, supersedes spec §4.4.2 caveats).** `astroquery.besancon` is
> the fragile path the spec assumed: it POSTs the legacy `modele_form.php` and polls
> `ftp://sasftp.obs-besancon.fr/modele/modele2003/` — the **2003 model**, email-gated, FTP-blocked on
> many networks, and its own tests are disabled. **But the current site also exposes a modern
> `galmod_client.py` "web-service mode": a UWS 1.0 REST job service at `https://model.obs-besancon.fr/ws/`
> running the renewed `m1612` model, authenticated by a BGM account (HTTP Basic Auth), not email.** This
> is the *same* async-job pattern we already run for Gaia TAP. `core/besancon.py` drives `/ws/` directly
> (no `astroquery.besancon`), dissolving three of the four §4.4.2 caveats (email→account, 2003→m1612,
> FTP→REST). Verified live 2026-07-23: `/ws/jobs` 401→200 with creds; a small run returns the m1612
> catalogue (per-star Age/Mass/[M/H]/[a/Fe]/Pop/Dist/UVW). **Register:**
> `https://model.obs-besancon.fr/ws/subscribe.php` → `BESANCON_USER`/`BESANCON_PASS` in `~/.zshenv`.
>
> **Ban-risk / limits check (2026-07-23):** no published rate limits, no API rate-limit headers, no job
> quota — but the servers are individually hosted ("not meant to handle large or repeated requests"). So
> the safeguards are courtesy, not enforced, and are baked into `core/besancon.py`: **30-day result cache**
> (identical query never re-runs the model), **30 s poll cadence** (the reference client's value), one job
> at a time, **always-DELETE cleanup** (verified: 0 jobs left on server), `sendmail=0`, **`SOLI` capped at
> 10 deg²**, server-side `EXECUTIONDURATION`, identifying `User-Agent`, and **no live CI** (offline fixture
> tests only). Output carries a `verify_against_observation` flag — T9's observational cross-check still
> lives in the sibling repo's T8 work (the tool produces the model distribution; the research validates it).

## 0. Evaluation of the spec against this codebase (what fits, what changes, risks)

**Verified against the live venv / codebase 2026-07-23:**

- **No new pip dependency.** `astroquery` is already a base dep (`requirements.txt`; `core/databases.py`
  imports it unconditionally). All submodules the spec needs — `vizier`, `gaia`, `xmatch`, `heasarc`,
  `besancon` — import cleanly on the 0.4.11 install, as do `pyvo` + `astropy.units`/`astropy.table`.
  **Unlike the dust path there is no optional extra, no `requirements-*.txt`, and no import gate for
  app-importability** (astroquery is already hard-required). The only gate is *network reachability*, for
  tests (mirrors `tests/_netcheck.py`).
- **Identity resolution is fully reusable.** `databases.compute_simbad_lookup(star)` already returns
  `main_id, ra, dec, sp_type, plx_value, teff, designations{…}`. The Gaia `source_id` is
  `designations["Gaia EDR3"]` (the SIMBAD `Gaia DR3` id, DR3≡EDR3), HIP is `designations["HIP"]`. So the
  spec's §3.1-step-1 "resolve identity via the existing SIMBAD path" needs **zero new resolution code** —
  the binary/astrophysical subcommands consume `compute_simbad_lookup` verbatim (the stated non-goal 7c).
- **Network discipline already exists.** `core/shared.py` ships `_with_retries` (honors `Retry-After`),
  `_timeout_ctx`, `_network_error_msg`. The spec's `{"error": …, "route_tried": […]}` contract is a thin
  additive extension of the existing `{"error": …}` shape.
- **Caching has precedents but no generic helper.** OEC uses a 7-day file cache; planet-positions use a
  30-min in-memory TTL. The spec wants "cache by (catalog/table + query hash) with a TTL." → build one
  small generic module `core/catalog_cache.py`.
- **Gaia TAP async discipline already proven.** `databases._gcns_fetch` runs the pyvo `TAPService`
  async-job pattern (submit→run→wait→fetch) with a timeout. The spec's §5 rule (sync `launch_job` caps at
  2000 rows → population pulls MUST use async with timeout+retry) is exactly what that code already
  encodes; the Gaia gateway reuses the same discipline.

**Risks / spec adaptations to flag:**

1. **`besancon-query` (Tier 3) — originally the fragile outlier; now RESOLVED.** The spec assumed
   `astroquery.besancon` (old 2003 interface, email-gated async). **A follow-on research pass found the
   modern UWS `/ws/` REST service (m1612, account-authenticated) — see the Besançon research finding in
   §0 — so `besancon-query` was built against that instead** and is no longer fragile. Its in-repo test
   is (a) input/credential validation and (b) the fixture-parsing + derived-`age_dist` summary math
   (offline). The T9 observational cross-check (vs the sibling repo's `canon/local-stellar-census.md`)
   stays in the sibling repo's T8 — the tool carries a `verify_against_observation` flag, it does not
   self-certify. (The §3.3 companion-mass filter + gateways are independent of it regardless.)
2. **Live expected values (T1–T9) can drift** with catalog contents. Handle like the existing `*_live.py`
   suite: **gated on reachability + tolerant** (±5 % masses, catalogue precision on periods), kept OUT of
   the default offline run.
3. **Cache must never store errors** (the `fetch_body_properties` lesson) — cache only successful, non-
   empty results.
4. **Lazy imports, always.** Every `astroquery.*` / `pyvo` import lives *inside* the core function or the
   `cmd_*` handler, never at `query.py` / `core.catalog` module top-level — preserves the ~0.5 s
   non-catalog `query.py` startup (the documented dust-module rationale) and keeps offline invocations of
   other subcommands unaffected.

**Bottom line:** the spec is a strong fit. The heavy lifting is (a) one reusable companion-mass classifier
(the load-bearing §3.3 helper the spec's §8 warns must be codified), (b) thin cached astroquery gateways,
and (c) two binary orchestrators that encode the tool-split. No dependency churn, no GUI, no app-
importability gate.

## 1. Module layout (new files)

| File | Contents |
|---|---|
| `core/catalog_cache.py` | Generic hash+TTL file cache under `data/catalog_cache/` (gitignored). `cache_key(service, params)`, `cache_get(key, ttl_s)`, `cache_put(key, obj)`. JSON-on-disk; skips errors/empties. |
| `core/catalog.py` | Tier-1 generic gateways + Tier-3 gaia-astrophysical: `vizier_query(...)`, `gaia_tap(...)`, `xmatch_query(...)`, `heasarc_query(...)`, `gaia_astrophysical(...)`. All lazy-import astroquery, wrap in `_with_retries`/`_timeout_ctx`, cache, return the standard JSON/`error` shape. |
| `core/binary.py` | The §3.3 **companion-mass classifier** (pure math, offline-testable) + the two Tier-2 orchestrators `binary_orbit(...)` and `close_binary_census(...)` (reuse `core.catalog` gateways + `compute_simbad_lookup` + `xmatch_query`). |
| `core/besancon.py` *(built)* | `besancon_query(...)` — drives the modern Besançon **UWS 1.0 REST service** (`/ws/`, m1612) directly: create → params → RUN → poll 30 s → retrieve → DELETE, account auth (`BESANCON_USER`/`BESANCON_PASS`), + the derived `age_dist` summary. Separate module for the UWS job lifecycle + safeguards. |

**Extended:** `core/shared.py` (add a `_route_error(msg, route_tried)` helper for the `{"error",
"route_tried"}` shape); `query.py` (7 handlers + subparsers); `docs/integration.md` (the live contract);
`.gitignore` (`data/catalog_cache/`); `tests/_netcheck.py` (add `cds_reachable`/`esa_gaia_reachable`).

## 2. Build phases (engineering order — layering, not spec priority)

The spec's delivery priority is P1 binary → P2 gateways → P3 population, but the **binary orchestrators
call the gateways internally**, so the gateways are built first as the substrate. Each phase is
independently shippable and testable.

### AM-0 — Foundation (cache + contract + the companion-mass classifier)
- `core/catalog_cache.py` (hash+TTL JSON file cache; unit-tested offline).
- `core/shared._route_error` (additive `route_tried` on the error dict).
- `core/binary.py` **classifier** (the load-bearing pure-math piece — no network):
  - `companion_mass_from_thiele_innes(A,B,F,G, parallax_mas, period_yr, m1_solar)` → `a0_mas, a1_au,
    mass_function, m2_solar` via `u=½(A²+B²+F²+G²)`, `v=AG−BF`, `a₀=√(u+√(u²−v²))`, `a₁=a₀/ϖ`,
    `f=a₁³/P_yr²`, cubic solve for M₂ (M₁ from spectral type). Emits the *under-estimate-when-secondary-
    luminous* caveat.
  - `companion_mass_from_sb1(K1_kms, period_d, ecc, m1_solar)` → `f(m)=1.0361e-7·K1³·P·(1−e²)^1.5`,
    cubic → **M₂,min** (labelled sin i = 1 lower bound).
  - `classify_companion(m2_solar, a0_mas=None)` → `stellar` (>0.075) / `brown-dwarf` (0.013–0.075) /
    `planet` (<0.013 M☉); `low-significance` flag when `a0 ≲ 1 mas`.
  - `verification_tag(source, ...)` → the paste-ready `[V-PRIMARY-Gaia-DR3-NSS …]` / `[V-SECONDARY SB9
    gr<N> <bibcode>]` strings.
  - `m1_from_spectral_type(sp)` — reuse the existing main-sequence table (`science.py` /
    `main_sequence_stars` DB) for M₁; fall back to a coarse OBAFGKM mass ladder.
- **Tests (offline, always-run):** `tests/test_binary.py` — the classifier against fixed Thiele-Innes /
  SB1 inputs (the a₀→mass math), the three thresholds, the `low-significance` flag, tag formatting;
  `tests/test_catalog_cache.py` — key stability, TTL expiry, error/empty not cached.

### AM-1 — Tier 1 gateways (P2): `vizier-query`, `gaia-tap`, `heasarc-query`
Thin cached wrappers, standard JSON + `error`. Built before Tier 2 because Tier 2 reuses them.
- `vizier_query(catalog, columns=None, filters=None, cone=None, row_limit=2000)` — `astroquery.vizier`;
  finite default ROW_LIMIT, `--row-limit -1` unlimited; trims columns by default. Reuse target: **`B/cb/cbdata`**
  (Ritter & Kolb CVs — the §7.3 population), `B/sb9`, `B/wds`, `B/orb6`, `B/gcvs`, `I/311/hip2`.
- `gaia_tap(adql=None, table=None, where=None, columns=None, cone=None, row_limit=2000)` —
  `astroquery.gaia`; **sync `launch_job` for small/by-id (≤2000-row cap), async `launch_job_async` +
  timeout+retry for population** (spec §5); guard unbounded scans.
- `heasarc_query(mission/table, cone=None, …)` — `astroquery.heasarc`; X-ray catalogs (RASS/Chandra/XMM)
  for the activity/flare + CV/compact-object ID story.
- `xmatch_query(table_or_coords, cat2, max_arcsec, colRA/colDec)` — `astroquery.xmatch` (also the census
  cross-match engine; exposed as an internal helper, optionally a subcommand).
- **Handlers + subparsers** for `vizier-query`, `gaia-tap`, `heasarc-query`.
- **Tests:** `tests/test_catalog_live.py` (gated) — **T6** `vizier-query --catalog B/cb/cbdata` → GK Per
  `Orb.Per = 1.996803 d`; a small `gaia-tap` by-id sanity pull; **T8** the X-Match anchor (Capella → HIP
  24608, Plx 76.2 mas).

### AM-2 — Tier 2 (P1): `binary-orbit --star`
The encoded tool-split (spec §3.1), reusing AM-0/AM-1:
1. `compute_simbad_lookup` → coords, `source_id`, HIP, sp_type, parallax.
2. Gaia NSS (4 tables) by `source_id` via `gaia_tap`; pull Thiele-Innes for `nss_two_body_orbit`.
3. SB9 (`B/sb9`) by name/cone via `vizier_query` → Period / e / Grade / Ref bibcode.
4. WDS (`B/wds`) + orb6 via `vizier_query` → separation / PA / visual period.
5. Merge; **per-solution** `source, period_d, eccentricity, grade, primary_ref, separation_*`, the
   `companion` block (§3.3 classify), and the `verification` tag. **No solution → explicit `{"solutions":
   [], "route_tried": [...]}`**, never a silent empty (failed-tool ≠ absent-capability).
- **Tests (gated live):** **T1** δ Tri (SB9 P=10.020 d gr4 + Gaia NSS; stellar); **T2** GJ 876 → the
  61.36 d solution classified **`planet`** (the planet-filter regression); **T3** HD 110833 → method
  M₂≈0.16 M☉ vs Gaia `binary_masses.m2=0.171` within ~7 % (the load-bearing method-correctness anchor);
  **T4** Capella (SB9 104.02 d gr5, SB2, 42.8 ly via Hipparcos — the bright route Gaia saturates on).

### AM-3 — Tier 2 (P1): `close-binary-census`
The systematic population sweep (spec §3.2) as one reproducible call:
- Gaia NSS `nss_two_body_orbit ⋈ gaia_source`, parallax cut from `--dist-max-ly`, `0<period<--period-max-d`
  (async pull). SB9 all orbits in range ⋈ `main`, **X-Match (`xmatch_query`) to Hipparcos + Gaia** for
  parallax → distance cut. Dedup Gaia↔SB9 twins; honor `--exclude-known <file>`. Classify + `--drop-planets`
  (default on) + `--separate-wide`. Emit an **honest `coverage` block** (catalogs swept / not, residual
  incompleteness) + counts by class. NSS EB/compact tables are **not** primary sources (spec §3.2 note).
- **Test (gated live):** **T5** `--dist-max-ly 65 --period-max-d 365` reproduces reservoir §11 (≈50 new
  systems: 39 stellar/10 BD/1 WD; 5 planetary companions excluded incl. GJ 876, ι Hor). Tolerant count
  assertions (catalog drift).

### AM-4 — Tier 3 (P3): `gaia-astrophysical` + `besancon-query` — **BOTH BUILT**
- `gaia-astrophysical --star` — resolve → `source_id`, pull `gaiadr3.astrophysical_parameters`
  **by source_id** (no ra/dec cols): GSP-Phot `teff/logg/mh/radius` + FLAME `mass/radius/lum/age
  (+lower/upper)/evolstage`. **Emit the FLAME model-dependence caveat on every age.** Test **T7** (gated):
  η Cas A → `age_flame≈10.06 [8.90–11.19] Gyr, mass≈0.96, radius≈1.14, Teff≈5726 K`.
- `besancon-query` — **built against the modern UWS `/ws/` service (m1612), NOT `astroquery.besancon`**
  (see the Besançon research finding in §0). `core/besancon.py` drives the UWS job lifecycle directly
  (create → params → RUN → poll 30 s → retrieve → DELETE), account auth from `BESANCON_USER`/`BESANCON_PASS`,
  → raw synthetic catalogue + derived `age_dist` summary (histogram, mass-conditional age,
  thin/thick/halo/bulge mix, AMR), flagged **verify_against_observation**. Offline test =
  fixture-parsing + the derived-summary math (`tests/test_besancon.py`); the T9 observational cross-check
  stays in the sibling repo's T8. All safeguards baked in (30-day cache, 30 s cadence, DELETE cleanup,
  `SOLI` cap, `sendmail=0`, no live CI) — see §0.

## 3. Cross-cutting contract (spec §5 — applies to every subcommand)
- **`{"error", "route_tried"}`** on any failure (network, 408/500, empty, bad id) — never a bare
  exception; a blocked route enumerates the alternatives tried.
- **Cache** every successful catalog response by (service+table+query hash) with a TTL (default 7 d, tune
  per catalog); never cache errors/empties.
- **Sync ≤2000 rows / async for population** (Gaia), timeout+cancel, retry the intermittent async 500.
- **Offline-graceful** — no network → immediate `error` shape; other `query.py` subcommands unaffected
  (lazy imports).
- **Units + provenance on every field** — period (d), separation (arcsec/AU), mass (M☉+M_Jup), parallax
  (mas), distance (ly+pc), + catalog/grade/verification tag per orbit row.

## 4. Testing summary
- **Offline, always-run:** `test_binary.py` (classifier math, thresholds, tags), `test_catalog_cache.py`
  (TTL/hash/no-error-cache), besancon derived-summary math over a fixture (if built).
- **Gated live** (`test_catalog_live.py`, `@skipUnless` on `cds_reachable`/`esa_gaia_reachable`): T1–T8
  (subset), each independence-labelled per skill v0.1.32 (T3 `[independent-tool]`, T6/T1/T4/T5
  `[catalogue]`, T8 `[independent-tool]`, T2/T7 `[literature]`/`[catalogue]`).
- Add `tests/_netcheck.cds_reachable()` (`cdsarc.cds.unistra.fr` / `vizier.cds.unistra.fr`) and
  `esa_gaia_reachable()` (`gea.esac.esa.int`).
- Document each new file in `docs/testing.md`.

## 5. Deliverables checklist — BUILT 2026-07-23 (all seven subcommands)
- [x] `core/catalog_cache.py` + `core/catalog.py` + `core/binary.py` + `core/besancon.py`
- [x] 7 `query.py` handlers + subparsers: `vizier-query`, `gaia-tap`, `heasarc-query`, `binary-orbit`,
      `close-binary-census`, `gaia-astrophysical`, `besancon-query`
- [x] `core/shared._route_error`; `data/catalog_cache/` covered by the existing `data/` gitignore rule
- [x] `docs/integration.md` — the "Catalog-access tier (Phase AM)" section (live contract the sister repo reads)
- [x] `tests/test_binary.py`, `tests/test_catalog_cache.py`, `tests/test_besancon.py` (offline, always-run — 39 tests),
      `tests/test_catalog_live.py` (gated; T1–T8 anchors), `tests/_netcheck.py` helpers, `docs/testing.md` entries
- [x] CLAUDE.md architecture-paragraph note (catalog-access tier)

**Verification (2026-07-23):** offline suite green (**1983 passed / 1 skipped / 0 failed**; +39 catalog/besancon offline tests, incl. the §3.3 `binary_masses` cross-check + `--include` honesty);
live anchors reproduced against the authorities — **T6** GK Per Orb.Per=1.996803, **T8** Capella→HIP
24608 Plx 76.2, **T1** δ Tri SB9 10.020 d gr4, **T2** GJ 876 61.36 d → class `planet`, **T3** HD 110833
a₀→mass 0.156 M☉ (vs Gaia 0.171), **T4** Capella SB9 104.02 d gr5 / 42.8 ly (NSS saturates → skipped),
**T5** census 65 ly/365 d → 62 systems (55 stellar / 7 BD, 3 planets excluded incl. GJ 876), **T7**
η Cas A FLAME age 10.06 [8.90–11.19] Gyr, HEASARC rassbsc cone OK, **besancon-query** m1612 live run OK
(age_dist derived; cache hit 0.2 s; 0 jobs left on server).

**Note on T9:** `besancon-query` produces the model `age_dist`; the T9 observational cross-check
(vs `canon/local-stellar-census.md`) remains the sibling repo's T8 responsibility — the tool carries a
`verify_against_observation` flag, it does not self-certify against observation.

**Post-build refinements (2026-07-23, spec-completeness pass):**
- **§3.3 Gaia `binary_masses` cross-check** — `binary-orbit` now attaches the independent
  `gaiadr3.binary_masses` mass (`catalog.gaia_binary_masses`, per-source with retries) to each NSS
  companion as `companion.binary_masses` (m1/m2 +bounds, fluxratio, combination_method, m1_ref,
  `agreement_pct`). Our Thiele-Innes/SB1 stays primary; Gaia cross-checks it, or **fills** where our
  method produced no mass but Gaia's `m2` is non-null. Verified live: HD 110833 → our 0.156 vs Gaia
  0.171, 8.8 % agreement.
- **`close-binary-census --include` honesty** — `wds`/`cv` are known but not yet wired as sweep sources
  (both reachable via `vizier-query`). A requested-but-unimplemented source is now reported under
  `coverage.requested_not_implemented` (never silently dropped), and an unknown `--include` token → a
  curated error. Offline-tested (mocked sweeps).

**Still deferred (documented, minor / by-design):** `binary-orbit` queries `nss_two_body_orbit` only
(the 3 period-less NSS tables can't qualify a *close* pair per spec §3.2); `close-binary-census` does
not per-system SIMBAD-resolve (a deliberate perf tradeoff — `binary-orbit` gives the resolution); the
`wds`/`cv` census *sweep* wiring; and the §4.3(B) other-packet services (jplhorizons/mpc/hitran/… —
explicitly future packets, not this spec).
