# PHASE CR-8 PLAN — Batch exoplanet-archive pull (`planetary-systems-batch`)

**Source contract:** `scifiWorldBuilding-Claude/design-lab/star-system-analysis/spaceapp-change-request-CR8-batch-exoplanet-archive-pull.md`
**Status:** ✅ BUILT & green (2026-08-16) — WB-endorsed (MSG 060); awaiting WB re-gate (§5). Suite
**2913 passed / 55 skipped / 0 fail** offline; the 2 live anchors pass under `SPACE_APP_RUN_LIVE=1`.
All §8 build-time items resolved live: `ps` cross-ID column is `gaia_dr3_id` (not `gaia_id`),
`sy_gaiamag`/`pl_bmassprov` present; `IN(...)` chunked at 100 (no ceiling hit at 4 hosts). Uncommitted.
**Coordination:** channel is **build-time open** (`/home/greg/Claude/coordination-channel.md`); the CR's own §8
"no channel re-armed / queued for audit open" line is **superseded** (WB confirming the §8 edit on their side).
Validation §5 remains the shared re-gate. **WB MSG 060 locked in:** (a) the three load-bearing calls (`ps`-table,
new `planetary-systems-batch`, SIMBAD-first Mode A) all endorsed; (b) the **4-value `mass_kind` enum + raw
`pl_bmassprov` passthrough ACCEPTED** — do NOT collapse `M-R relationship` into `true_mass` (it is a radius-inferred
derived value, not a measurement; WB folds this shape into CR-8 §4 at re-gate); (c) the **gate-adjudication rule**
(§9 live-tests below) — HD 136352 identical, other-host `pscomppars`-back-fill divergence → `ps` wins, pass-with-note.

---

## 0. One-paragraph summary

Add a single `query.py` subcommand that returns the **full per-planet + per-system field set** of CR-8 §4 for a
**batch** of hosts (Mode A) *or* a property/ADQL selection (Mode B), in one consumer invocation, with per-value
provenance and a coverage manifest. It is a **LIVE** network calculator (Phase-AM / star-analysis-CR class) built on the
NASA Exoplanet Archive **`ps` (Planetary Systems)** table — deliberately **not** `pscomppars` — so that solution scope,
per-solution provenance, and genuine null/0 values are all available. The existing single-host `planetary-systems`
subcommand (`compute_planetary_systems_composite`, on `pscomppars`) is **left byte-identical**.

## 1. The load-bearing decision: `ps`, not `pscomppars`

The existing `planetary-systems --star` path queries `pscomppars` (composite: one blended row per planet). CR-8's
contract cannot be met from `pscomppars`; three requirements force the `ps` table:

| CR-8 requirement | `ps` column / property that satisfies it | `pscomppars` gap |
|---|---|---|
| `--solution-scope default\|all` (§3) | `default_flag` (1 = preferred); one row **per published solution** | exactly one composite row per planet |
| per-value provenance / citation (§4, §5.4) | `pl_refname` / `st_refname` — per-solution reflink HTML | composite blends solutions; no clean per-value cite |
| reported-0 vs unmeasured `e`; un-fabricated null incl (§4, §5.2) | `ps` preserves the genuine `null`/`0` per solution | composite back-fills across solutions |

Validation §5.1 (HD 136352 → planets b/c/d, incl **88.49 / 88.57 / 89.73°**, each citing **Delrez et al. 2021**) is
exactly the **default-flag `ps`** result — it pins the table choice.

## 2. Deliverable surface

- **New module `core/exoplanet_batch.py`** — `compute_exoplanet_batch(...)`. LIVE network. Pure data assembly; no Qt, no
  DB writes. Reuses `databases._query_tap`, `databases.compute_simbad_lookup`, `databases._get_archive_query_params`,
  `databases._adql_quote`, and `shared._route_error` / `shared._network_error_msg`.
- **New `query.py` subcommand `planetary-systems-batch`** — new command (per CR §7, "whether to extend or add is APP's
  call"); chosen new so the FULFILLED single-host `planetary-systems` contract is untouched.
- **Tests** — `tests/test_exoplanet_batch.py` (offline) + a `SPACE_APP_RUN_LIVE`-gated anchor in
  `tests/test_query_*` / a new live file (`_netcheck.live_enabled()` gate, host-reachability short-circuit — same
  pattern as `test_catalog_live.py`).
- **Docs** — `docs/integration.md` subcommand row + contract detail block; `docs/star-databases.md` note that the
  batch path is `ps`-backed (contrast the `pscomppars` single-host path); CLAUDE.md architecture-paragraph mention.
- **Coordination** — open `/home/greg/Claude/coordination-channel.md` at build start (WB's revised decision); post the
  build-underway note + the §5.1 anchor as the shared gate + the mass-provenance passthrough note (§7 below).

## 3. Subcommand interface

```
query.py planetary-systems-batch
    # ── selection (exactly one of Mode A / Mode B) ──
    --hosts NAME [NAME ...]                 # Mode A: host designations, mixed forms allowed
    --host-file PATH                        # Mode A convenience: one host per line (# comments/blank lines skipped)
    # Mode B (any of; all optional) — reuses the search-exoplanets filter set, built into ADQL over ps:
    --mass-min / --mass-max                 # pl_bmasse (M⊕)
    --radius-min / --radius-max             # pl_rade (R⊕)
    --period-min / --period-max             # pl_orbper (days)
    --teff-min / --teff-max                 # st_teff (K)
    --dist-max-pc                           # sy_dist (pc)
    --method                                # discoverymethod (exact)
    --spectral-classes ... / --spectral-refine
    --archive-query "ADQL"                  # Mode B raw escape hatch (WHERE body)
    # ── scope flags (both modes) ──
    --solution-scope {default,all}          # default: default
    --fields {core,full}                    # default: core
```

- **Mutual exclusion:** argparse group for `--hosts`/`--host-file` vs the Mode-B flags, plus a runtime guard →
  `{"error": "Supply exactly one of {host list, selection filter}."}` if both or neither present.
- **Mode-B host-naming guard:** a raw `--archive-query` that references `hostname`/`hd_name`/… is *permitted* (it is
  still a query, not a host *list*) but the manifest labels the mode `filter`; no special sanitization beyond the
  existing ADQL-literal escaping. CR §3 "expressible without naming specific hosts" is advisory to the consumer.

## 4. Internal flow

### Mode A — host list (SIMBAD-per-host; **locked** decision)
1. For each requested host string: `compute_simbad_lookup(host)` → canonical `main_id`, `designations{}`, cross-IDs,
   plus SIMBAD's own `sp_type`/`teff`/`fe_h` as fallbacks. (This per-host SIMBAD cost is justified by the output
   contract — the manifest's "canonical host it mapped to" and the per-host cross-IDs both need it.)
2. Pick an archive key per resolved host via `_get_archive_query_params` (HIP > HD > TIC > Gaia).
3. **Batch archive round-trips by column:** group resolved hosts by their chosen key column and issue one `ps` query
   per column with an `IN (...)` list (all HD names in one query, all HIP in another, …). Apply `default_flag = 1`
   unless `--solution-scope all`. Chunk any `IN`-list that risks the TAP URL length ceiling (see §8.2). Map returned
   rows back to their host by matching the key value.
4. **No silent loss (§5.3):** a host that fails SIMBAD resolution → manifest `resolved:false`. A host that resolves but
   returns zero `ps` rows → `resolved:true, planet_count:0` in `zero_planet[]`. Both still appear; resolvable hosts are
   all returned.

### Mode B — filter
1. Build an ADQL `WHERE` from the property flags (reuse `search_exoplanets`'s `_rng` + `spectral_adql` logic; mass on
   `pl_bmasse`, radius `pl_rade`, period `pl_orbper`, teff `st_teff`, dist `sy_dist`) **or** take `--archive-query`
   verbatim. Apply `default_flag` per scope.
2. One `ps` query; group returned rows by `hostname`.
3. Manifest echoes the selection back + total host/planet counts (§4 coverage, Mode B branch).

Both modes converge on a shared **group → serialize** step (§5).

## 5. Field mapping (`ps` columns → CR §4)

`_num()`/`_bool()`/`_parse_reflink()` helpers, all `None`-safe. Nulls stay explicit `null` (§6).

**Per planet (`core`):**
| CR field | ps source | note |
|---|---|---|
| planet name/letter | `pl_name` | |
| discovery method | `discoverymethod` | |
| orbital period (days) | `pl_orbper` | |
| semi-major axis (AU) | `pl_orbsmax` | |
| **inclination (deg)** | `pl_orbincl` | **null preserved** — never defaulted to 90 |
| **eccentricity** | `pl_orbeccen` | present `0` vs `null` = reported-vs-unmeasured (§5.2) |
| arg. periastron (deg) | `pl_orblper` | |
| mass (M⊕ **and** M_Jup) | `pl_bmasse`, `pl_bmassj` | + `mass_kind` (see below) |
| radius (R⊕) | `pl_rade` | null when non-transiting |
| transiting? | `tran_flag` → bool | |
| provenance | `pl_refname` → `{citation, refstr, href}` | |

**`mass_kind` flag:** derived from `pl_bmassprov` — `Mass` → `"true_mass"`, `Msini`/`Msin(i)/sin(i)` → `"msini"`,
`M-R relationship` → `"mass_radius_relation"`, else `"unknown"`. **The raw `pl_bmassprov` string is passed through
alongside**, so the binary-ish flag never lies about the M-R-relationship third category (§7 note to WB).

**Per host/system (`core`):** `resolved_host` (SIMBAD `main_id`) + `cross_ids{}` (from designations); `st_spectype`,
`st_teff` (K), `st_mass` (M☉), `st_rad` (R☉), `st_met` ([Fe/H] dex), `sy_dist` (pc); apparent magnitudes **band-labelled**
`{V: sy_vmag, K: sy_kmag, Gaia_G: sy_gaiamag}` (only bands present); `num_planets` = distinct `pl_name` returned (echo
`sy_pnum` too); provenance from `st_refname`. Missing stellar params fall back to SIMBAD values where the archive is null,
each tagged with its source.

**`--fields full`:** the above plus every remaining raw `ps` column on each planet/host row, untouched.

## 6. Output JSON

```jsonc
{ "mode": "hosts" | "filter",
  "solution_scope": "default" | "all",
  "field_scope": "core" | "full",
  "coverage": {
    "requested": [...],                 // Mode A: input strings
    "resolved_count": N,
    "unresolved": [{"input": "...", "reason": "..."}],
    "zero_planet": [{"input": "...", "resolved_host": "..."}],
    "selection_echo": "...",            // Mode B only
    "total_hosts": N, "total_planets": N
  },
  "hosts": [
    { "resolved_host": "...", "cross_ids": {...},
      "spectral_type": "...", "teff_k": ..., "mass_solar": ..., "radius_solar": ...,
      "fe_h_dex": ..., "distance_pc": ..., "magnitudes": {"V": ...}, "num_planets": N,
      "provenance": {"citation": "...", "refstr": "...", "href": "..."},
      "planets": [
        { "name": "...", "discovery_method": "...", "period_days": ..., "sma_au": ...,
          "inclination_deg": null, "eccentricity": ..., "arg_periastron_deg": ...,
          "mass_earth": ..., "mass_jupiter": ..., "mass_kind": "msini", "mass_prov_raw": "Msini",
          "radius_earth": null, "transiting": true,
          "provenance": {"citation": "...", "refstr": "...", "href": "..."} }
      ] } ] }
```

Failure → `shared._route_error(_network_error_msg(e, "NASA Exoplanet Archive"), route_tried=["nasa-tap:ps"])`.

## 7. Decided-unilaterally (within-contract; informed to WB, not negotiated)

- **Mass-kind passthrough** — `pl_bmassprov` has a third value (`M-R relationship`) that is neither a true mass nor
  m·sin i. Emit the derived `mass_kind` **and** the raw `mass_prov_raw`, so the flag never misrepresents an M-R-relation
  mass. → one-line note to WB when the channel opens.
- **Provenance object shape** — `{citation, refstr, href}` parsed from the reflink HTML; satisfies §5.4 "resolvable
  archive reference." Shape is APP's (output-format detail).
- **New subcommand vs extend** — new `planetary-systems-batch` (§7 of the CR leaves this to APP); single-host path
  untouched.

## 8. Build-time items to pin against the live TAP (`SPACE_APP_RUN_LIVE=1`)

1. **Exact `ps` column availability** — confirm `pl_bmassprov`, `sy_gaiamag`, and the cross-ID columns
   (`hd_name`/`hip_name`/`tic_id`/`gaia_id`) exist on `ps` (they do on `pscomppars`; standard NASA schema says `ps`
   too — pin it before trusting the mapping). Adjust `select` lists if any name differs.
2. **`IN(...)`-list ceiling** — the TAP `sync` endpoint takes the query as a GET param; a ~171-name `IN` list may hit a
   URL-length limit. If so, chunk the per-column `IN` lists (e.g. 50/query) and concatenate — transparent to the
   contract. Measure the real ceiling during build.

## 9. Tests

**Offline (`tests/test_exoplanet_batch.py`; mock `_query_tap` + `compute_simbad_lookup`):**
- `_parse_reflink` extracts citation + refstr from archive `<a refstr=… href=…>` HTML.
- `mass_kind` mapping incl. the `M-R relationship` → passthrough case.
- eccentricity present-`0` vs `null` distinction preserved; inclination `null` never defaulted.
- coverage manifest: unresolved host + zero-planet host both reported, resolvable hosts still returned (§5.3).
- Mode A / Mode B mutual-exclusion guard (both / neither → error).
- ADQL `WHERE` construction from Mode-B filters; `default_flag` applied per scope; `--fields full` widens columns.
- output nulls are explicit keys, not omitted (§6).

**Live-gated (`SPACE_APP_RUN_LIVE=1`):**
- §5.1 anchor: `--hosts "HD 136352"` → planets b/c/d, incl 88.49/88.57/89.73, each citing Delrez et al. 2021,
  `default_flag`-scoped.
- §5.1 batch≡single: batch values equal `planetary-systems --star "HD 136352"`'s corresponding fields (no rounding/drop).
  **This host is the anchor precisely because `ps`-default and `pscomppars` agree there** (Delrez 2021 is the complete
  default solution) — so the equality is exact and unambiguous.
- Mode B smoke: a small property filter returns grouped-by-host records with provenance.

**Gate-adjudication rule (WB MSG 060 — pinned).** The batch≡single equality is *anchored* on HD 136352 (must be
identical). For **any other host**, batch(`ps`-default) may legitimately diverge from single(`pscomppars`) on a field
that `pscomppars` **back-filled from a non-default solution** — this is **NOT a CR-8 failure**: the `ps` `default_flag`
value is the authoritative one, and the divergence is `pscomppars` doing its composite blend. Adjudication at re-gate:
*"is the difference a `pscomppars` back-fill? → `ps` wins, pass with a note,"* never an automatic fail. Do not "fix"
such a divergence by matching `pscomppars`.

## 10. Docs + coordination checklist

- [x] `docs/integration.md` — `planetary-systems-batch` row + full arg/field contract block (`ps`-backed).
- [x] `docs/star-databases.md` — batch path uses `ps` (per-solution + provenance), single-host uses `pscomppars`.
- [x] `docs/testing.md` — `test_exoplanet_batch.py` + `test_query_exoplanet_batch_live.py` entries.
- [x] `CLAUDE.md` — architecture-paragraph sentence + suite-count bump (2913/55).
- [x] Channel open (MSG 059–061; build underway, §5 gate, mass-provenance passthrough); MSG 062 = delivery/re-gate.
- [x] `venv/bin/python -m pytest` offline green (2913/55/0) + `SPACE_APP_RUN_LIVE=1` anchors pass (2/2).
- [ ] git commit (pending user go-ahead) + WB re-gate.
```
