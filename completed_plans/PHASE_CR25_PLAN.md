# PHASE CR-25 — exclusion wind-wiring fix ("2a"): thread `wind_state`, fetch the full SIMBAD otype list, restore the 3-bin model, + `wind_class_provenance`

**Status: ✅ FULFILLED (Greg signed, WB MSG 269, 2026-09-24) — built, CP1–CP4 folded, suite 3554/102/0, APP live 11/11, WB independent live re-gate GREEN (~80 cases, both subcommands). Committed CR-25-only on `main`.** Q&A closed
(MSG 264); plan-reviewed (2 agents, all findings folded — §12); E1–E6 all ACKED + one additive ask
(`wind_otype_source`, §3a) in MSG 266. Git-hold until WB independent re-gate GREEN + Greg's FULFILLED flip;
commit **CR-25-only** on `main`.
Contract (the contract wins over this plan and over MSG 262 where they differ):
`scifiWorldBuilding-Claude/design-lab/star-system-analysis/spaceapp-change-request-CR25-exclusion-wind-wiring-fix.md`.
Channel: MSG 260 (ping) / 261 (ready) / 262 (hand-off) / 263 (APP eval + 8 Qs) / 264 (rulings).
First CR of the locked chain **CR-25 → CR-26 → CR-24** — **do not touch CR-24** (V_ISM / `bow_shock` flip) or
any CR-26 magnitude calibration (the `quiet` bin stays `1e-16`).

CR-25 is **code-only** and a **bug fix**. The classifier logic is mostly right; its call sites drop the wind
input. Four sub-CRs ship together, nothing deferred:
**CR-25.1** thread `wind_state` (bin override) · **CR-25.2** full-otype-list active auto-detect ·
**CR-25.3** `wind_class_provenance` surface · **CR-25.4** `exclusion-system` coverage (REQUIRED).

---

## 0. Confirmed diagnosis (APP, code + live probes, 2026-09-24)

| Defect | Site | Confirmed |
|---|---|---|
| (i) `--wind-state` dropped | `query.py:808` (`--spectral-type`) / `:836` (`--star`) call `classify_domain_wind` without `wind_state` and pass a **pre-classified** `domain`/`wind_class` into `compute_two_layer_boundary`, so its own `wind_state`-aware classify never runs | ✅ |
| (ii-a) no otype list | `databases.compute_simbad_lookup` requests only the primary `otype` (`databases.py:241`); it is `PM*` for 5 of 6 flares | ✅ |
| (ii-b) matcher too narrow | `exclusion_wall._is_flare_otype` (`:177-179`): substrings `"flare"`/`"uv cet"` + exact `fl*`/`uv*` only; no `Er*`/`BY*`/`RS*` | ✅ |
| (ii-c) partial bin override | `_ms_wind_class` (`:158-174`): for a K/M colour only `wind_state == "active"` is read; for G/F/A/B/O the colour always wins. (With **no** colour, all four states already map — `:174`.) | ✅ |
| (iii) `exclusion-system` | no `--wind-state` arg (`query.py:3403-3448`); `_single_body_component` (`exclusion_system.py:615-616`) and the binary A/B specs (`:730-738`) carry **no `otype`**, so compose's classify sees `otype=None` — the contract's defect 3(b) | ✅ |

**Probe facts the plan relies on** `[V-PRIMARY: SIMBAD TAP, APP probes]`:
- **One-query route (verified live):** `SELECT b.main_id, o.otype FROM ident AS i JOIN basic AS b ON b.oid = i.oidref JOIN otypes AS o ON o.oidref = b.oid WHERE i.id = '<head>' OR i.id = '<cand>'`. SIMBAD TAP **normalizes `ident.id =` comparisons**, which is also how astroquery 0.4.11's `query_object` resolves names (`core.py:643-655`). A literal `IN (…)` or a `basic.main_id =` match does **not** normalize. One call both resolves the A-candidate and returns one row per code for each object, in 0.3–6 s. Live results:
  - `G 272-61` → rows for **`G 272-61A`** {`*`,`**`,`Er*`,`PM*`,`V*`} + the head {…`UV`,`V*`,`X`, no active code}
  - `BD+19  5116` → distinct `BD+19  5116A`
  - `* alf Cen` → distinct `* alf Cen A` {`*`,`**`,`NIR`,`PM*`,`UV`}
  - `* alf CMa` → the head only (the A-candidate is the same object)
  - `V* EV Lac` → the head only (candidate unresolved)
  - `NAME Barnard's star` (escaped `''`) → the head {…`BY*`…}
- **α Cen B** (`* alf Cen B`) = {`*`,`**`,`PM*`}: no active code, so it stays `quiet` and α Cen's `wall_zones` are unchanged.
- The WB-table lists match for all 9 stars. **G stars with active codes exist:** κ¹ Cet `G5V` `BY*`; EK Dra `G5V…` `BY*`+`Er*`. This is why the Q1 K/M gate is needed.

## R. Rulings (Greg via WB, MSG 264) — all APP recommendations accepted

| Q | Ruling |
|---|---|
| Q1 | Otype auto-detect on **MS K/M only**. The G/F/A/B/O defaults are unaffected and O/B stars are never demoted. An explicit `--wind-state` still works on any colour. |
| Q2 | Per-component attribution. Component A takes the A-candidate object's list, **resolved through SIMBAD's name normalization**. It falls back to the head's list + a `resolution_notes` line only if the candidate genuinely doesn't resolve. B takes its own list. **Never union.** `exclusion-boundary --star` follows the same rule. New anchor: `exclusion-boundary --star "GJ 65"` → `active` (`Er*` via `G 272-61A`). |
| Q3 | (a) `--wind-state` is **ignored** on evolved/windless/unmodeled hosts, the identity provenance is kept, and a `wind_class_note` is added. (b) The system `exclusion-system --wind-state` reaches **all MS components**: `--star`-resolved ones **and** `--component` specs with no `wind_state=`. A component's own value wins. |
| Q4 | `wind_class_provenance` is on every output and every component. Enum `{manual, otype_auto, class_default, object_preset}` + `null` (§3). |
| Q5 | `wind_otype` = sorted matched codes or `null`, shown whenever the list matched (**even under `manual`**). `wind_class_note` = string or `null`. The full list is not surfaced. |
| Q6 | One bounded SIMBAD TAP call (`shared._call_with_watchdog`, 30 s per attempt, retried once, successes cached). It runs **only for MS K/M** (also under `manual`). On failure it degrades to the **primary** otype and adds `otype_status ∈ {timeout, unreachable, error}`, only when degraded (`_a`/`_b` on the binary path). Env `SPACE_APP_SIMBAD_TIMEOUT` (0 = unbounded) + hook `SPACE_APP_SIMBAD_OTYPES_FORCE_UNREACHABLE=1`. No CLI flag. |
| Q7 | The FROZEN standoff is **untouched**. An `otype_auto` bin feeds the **WALL only**, so `--gamma>0` + auto-detect + no flag still returns the curated error. The `hot` standoff Ẇ 1e-6 vs wall `o_hot` 5e-7 mismatch is documented, not changed (a CR-26 input). |
| Q8 | `wind_class_note` in **both directions**: `hot` on an F/G/K/M MS star, and `quiet`/`solar`/`active` on an O/B MS star. |
| FYI | (i) Legacy long names kept. (ii) WR/AGB detection stays on the primary otype. (iii) `--component otype=BY*\|Er*`. (iv) The merge and `wall_zones` logic is untouched. |

---

## 1. Classifier core — `core/exclusion_wall.py` (CR-25.1 / .2 / .3)

### 1a. Active-otype matcher (CR-25.2)
```python
_ACTIVE_OTYPE_CODES = ("BY*", "Er*", "Fl*", "RS*", "UV*")      # canonical casing, sorted
_ACTIVE_LEGACY = (("flare", "Fl*"), ("uv cet", "UV*"))          # FYI (i): long-name aliases kept

def _otype_codes(otype=None, otypes=None):
    """→ list of stripped codes: the fetched ``otypes`` iterable if given, else ``otype`` split on '|'
    (FYI iii). A plain primary otype (no '|') → a 1-element list."""

def active_otype_matches(otype=None, otypes=None):
    """Sorted canonical codes from the active set. EXACT whole-code match, case-insensitive
    (``er*`` ≡ ``Er*``); so ``UV`` (the UV-source flag) never matches ``UV*``, and ``Ro*``/``V*``/
    ``Em*``/``PM*`` never match. A legacy long name maps to its code (``Flare Star`` → ``Fl*``)."""
```
`_is_flare_otype(otype)` becomes `bool(active_otype_matches(otype=otype))`. That is a strict superset of
today's matcher: the only additions are `BY*`/`Er*`/`RS*`, plus the `|` form.
**WR/AGB (FYI ii):** `_is_wr_otype`/`_is_agb_otype` keep their exact semantics on a plain primary otype. For
the new `|` form (which has no primary) they are applied to **each** split code, any-match (`C*|BY*` →
AGB). This is reachable only through the new syntax.

### 1b. `_ms_wind` — the MS bin precedence (CR-25.1 + Q1 + Q5 + Q8)
`_ms_wind(colour, wind_state, otype, otypes) → (wind_class, provenance, wind_otype, wind_class_note)`.
`_ms_wind_class` is kept as a `[0]` wrapper.
```
ws      = wind_state.strip().lower() if it is in _WIND_STATE_CLASS else None
matched = active_otype_matches(otype, otypes) if colour in ("K","M") else []     # Q1 gate
1. ws   → wc = _WIND_STATE_CLASS[ws]; prov "manual"; note = Q8 mismatch (below) or None
2. elif matched → "active"; prov "otype_auto"
3. elif colour  → colour default (O→o_hot, B→b_hot, A→a_dwarf, F→f_dwarf, G→solar, K/M→quiet); "class_default"
4. else (no colour, no ws) → None; prov None
wind_otype = matched or None                       # Q5: shown even when step 1 wins
```
**Q8 notes.** The text is exact and lives in shared constants, so both subcommands emit identical wording.
The article comes from the colour letter: "an" for A/F/M/O, "a" for B/G/K.
- `hot` on F/G/K/M: `"explicit wind_state 'hot' → o_hot (a line-driven hot-star wind) on {a/an} {X}-type main-sequence star — physically inconsistent; honored as an explicit override"`
- `quiet`/`solar`/`active` on O/B: `"explicit wind_state '{ws}' → {wc} (a cool-star wind bin) on {a/an} {X}-type main-sequence star — physically inconsistent; honored as an explicit override"`
- Colour A and a colourless bare mass get no note (Q8 is literal).
- The wording says `wind_state`, not `--wind-state`, because it also covers `--component wind_state=`.

### 1c. `_classify_identity` contract + the new `classify_wind` (pinned order)
`_classify_identity(sp_type, otype, class_tag, object_name) → (domain, default_wc, class_note, ms_colour)` is
computed **without `wind_state`**:
- On every MS branch: `default_wc=None`, and `ms_colour` = the colour the branch used to pass to
  `_ms_wind_class`:
  - the `_MS_TAGS` class_tag → `_sp_letter(sp)`;
  - the cool subdwarf → `colour or "K"`;
  - the lum-V / sd-prefix end branch → `colour` (may be `None`).
- On non-MS branches: `ms_colour=None` and `default_wc` is today's value.
- No identity → `(None, None, None, None)`.

```python
def classify_wind(sp_type=None, otype=None, class_tag=None, wind_class=None, object_name=None,
                  wind_state=None, otypes=None):
    """→ {domain, wind_class, class_note, wind_class_provenance, wind_otype, wind_class_note}."""
```
Order (each step returns):
1. `dom, wc0, cnote, colour = _classify_identity(…)`. If `dom == MAIN_SEQUENCE` or `dom is None`:
   `ms = _ms_wind(colour, wind_state, otype, otypes)`, computed **exactly once**.
2. **Explicit `wind_class`** (a valid emitted string: `--component wind_class=` or an `--object` preset).
   The domain logic is kept byte-identical to today (`exclusion_wall.py:218-224`, including the
   windless/unmodeled re-infer branch).
   - `wind_class` = the explicit value; provenance `"manual"`; `wind_otype` = `ms[2]` (identity matches).
   - `wind_class_note` = `"wind_state '{ws}' not applied — superseded by the explicit wind_class '{wc}'"`
     when a valid `ws` was given, else `None`. **No Q8 or Q3a note in this branch.**
   - The `--object` caller relabels the provenance `object_preset` (§4b).
3. `dom is None` (bare mass) → `(MAIN_SEQUENCE, ms[0], None, ms[1], ms[2], ms[3])`.
4. `dom == MAIN_SEQUENCE` → `(dom, ms[0], cnote, ms[1], ms[2], ms[3])`.
5. Non-MS (`evolved`/`windless`/`unmodeled`) → `(dom, wc0, cnote, "class_default" if wc0 else None, None,
   Q3a note if a valid ws else None)`. **Q3a note:** `"wind_state '{ws}' does not set the wind bin of
   {an evolved | a windless (free-harbor) | an unmodeled} host — the identity-derived wind class stands"`.
   It describes the **bin/wall** only, so it stays accurate on `exclusion-boundary`, whose frozen
   standoff still consumes `--wind-state` at γ>0 (untouched, Q7).

`classify_domain_wind(…, otypes=None)` is kept as a **wrapper** returning `(domain, wind_class,
class_note)`, so every existing caller and test (`_component_domain`, the CR-22 classifier tests) sees a
byte-identical 3-tuple.

### 1d. Fetch-relevance gate
```python
def otype_list_relevant(sp_type=None, otype=None, class_tag=None, object_name=None):
    dom, _wc, _n, colour = _classify_identity(sp_type, otype, class_tag, object_name)
    return dom == MAIN_SEQUENCE and colour in ("K", "M")      # pure; no network
```

---

## 2. The otype-list fetch — `core/databases.py` (CR-25.2 route + Q2 + Q6)

```python
def fetch_star_otypes(main_id, primary_otype=None, component_rule=True):
    """Full SIMBAD otype list for a resolved star →
         {"codes": [str,…] | [primary] on degrade, "source_main_id": str|None,
          "source_is_self": bool, "status": None | "timeout" | "unreachable" | "error",
          "fallback_to_head": bool}
    Returns None (no fetch, no network) when main_id is falsy."""
```
- **Q2 A-candidate rule** (`component_rule=True`): applies when `main_id` is **letterless** (no trailing
  `\s[A-Z]$`). Then `cand = next(iter(stellar_mass.component_candidate_ids(main_id, "A")), None)`, with
  `stellar_mass` imported lazily, and the query is `WHERE i.id = '<head>' OR i.id = '<cand>'`.
  - A main_id that already ends in a component letter (`* alf Cen B`) is its own object: no candidate,
    so a B-named star never inherits A's list.
  - `component_rule=False` (binary component B, already resolved) → `WHERE i.id = '<main_id>'`.
  - Both ids are escaped `'` → `''`.
- **Result interpretation** (rows grouped by `b.main_id`; `own` = the group whose whitespace-collapsed
  main_id equals the head's; `others` = the rest):
  - with a candidate, **exactly one `others` group** → the distinct A object: `codes` = its list,
    `source_main_id` = its main_id, **`source_is_self=False`**. (Every other outcome → `source_is_self=True`,
    because the list is the resolved star's own.)
  - `own` exists → the head's list. `fallback_to_head = (component_rule and cand is not None)`, i.e. the
    candidate did not resolve to a distinct object.
  - no `own` but exactly one group → that group. This covers a head resolved under a different main_id
    string, e.g. `compute_simbad_lookup`'s masked-main_id fallback (`databases.py:274`); `ident.id`
    normalization still finds it.
  - **zero rows, or more than one `others` group → raise the private `_OtypeResultError`.** Every SIMBAD
    object has ≥1 otype row, so zero rows means something is wrong.
- **Bound / retry:**
  - `_simbad_otype_timeout()`: env `SPACE_APP_SIMBAD_TIMEOUT` > default **30 s**. A value ≤ 0 → `None`
    (unbounded: the watchdog joins forever). Non-numeric → the default. Same rules as
    `catalog._gaia_sync_timeout`.
  - Calls go through **`catalog._bounded_gaia_call(attempt, timeout=…, retries=2)`**, reused as-is. It is
    generic: the watchdog, retry-once, a backoff, and HTTP `Retry-After` respect (pyvo raises
    `DALRateLimitError` on 429).
  - The attempt builds a **fresh `Simbad()`** and calls `query_tap(adql)`. A fresh instance means its own
    `requests.Session`, so an abandoned daemon attempt shares no state (mirrors CR-19's fresh `GaiaClass`).
  - **No `_make_simbad(timeout=…)`:** astroquery 0.4.11 never reads `.TIMEOUT` (`core.py:146-165`). The
    watchdog is the only bound.
  - No process-global `_timeout_ctx`, and **no circuit-breaker** (at most 2 calls per run).
- **Status classification** (CR-19 convention, `catalog.py:372-376`):
  - `shared._WatchdogTimeout` → `timeout`;
  - `_OtypeResultError` → `error`;
  - **any other exception → `unreachable`.** pyvo wraps network failures as `DALServiceError`
    ("…Connection failed", no cause, `vosi.py:102-123`) or as `DALFormatError` with the requests error in
    `.cause` (`query.py:258-263`). These are not `requests`/`OSError` types, so classifying by exception
    type would mislabel an outage as `error`.
- **Cache discipline** (`catalog_cache._is_empty` only rejects None/empty/`"error"`-keyed/empty-`rows`, so
  it would accept `{"codes": []}`):
  - `catalog_cache.cached("simbad_otypes", {"main_id", "component_rule"}, producer)` wraps **only the
    bounded seam**.
  - The producer **raises** on failure and on an empty list, so a degrade or an empty result can never be
    cached. The degrade dict is built **outside** `cached()`, as in CR-19 `catalog.py:357-376`.
  - Cached value: `{"codes", "source_main_id", "fallback_to_head"}`. 7-day TTL; `SPACE_APP_CATALOG_CACHE=0`
    disables it.
- **Degrade:**
  - `codes = [primary_otype]` if it is truthy, else `[]`;
  - `source_main_id=None`;
  - **`fallback_to_head=False`**, so a network failure never adds the "no distinct SIMBAD object" note;
  - one stderr line `[simbad] otype list bounded (<status>) — degrading to the primary otype: <main_id>`.
- **Test hook** `SPACE_APP_SIMBAD_OTYPES_FORCE_UNREACHABLE=1` is checked **first, before the cache and any
  network**. It returns the `unreachable` degrade, so WB's re-gate is deterministic even with a warm cache.
- `compute_simbad_lookup` / `simbad-lookup` are **unchanged**. Only the exclusion paths fetch.

---

## 3. `wind_class_provenance` table (Q4 — the contract surface)

| Path / case | `wind_class_provenance` | `wind_otype` | `wind_class_note` |
|---|---|---|---|
| `--star` MS K/M, no flag, list hits active set | `otype_auto` | matched codes (EV Lac `["Er*"]`) | — |
| `--star` MS K/M, no flag, no hit | `class_default` | `null` | — |
| MS any colour + `wind_state` (flag, own, or system-injected) | `manual` | matched (K/M) or `null` | Q8 note on a colour mismatch |
| `--star`/`--spectral-type` MS G/F/A/B/O, no flag | `class_default` | `null` (no fetch, Q1) | — |
| evolved (lum class or WR/AGB otype) | `class_default` | `null` | Q3a note if a wind_state was given |
| windless / unmodeled | `null` | `null` | Q3a note if a wind_state was given |
| bare `--mass-msun` | `null`, or `manual` with `--wind-state` | `null` | — |
| `--object sun`/`m-dwarf`/`o-star` | `object_preset` | `null` | "superseded" note if `--wind-state` was given |
| `--object brown-dwarf`/`rogue-planet` | `null` | `null` | Q3a note if `--wind-state` was given |
| `--component wind_class=` | `manual` | identity matches | "superseded" note if a wind_state was also present |
| `--component wind_state=` on an **MS** component | `manual` | matched (K/M) | Q8 note if mismatched |
| `--component otype=Er*` (K/M, no wind_state) | `otype_auto` | `["Er*"]` | — (no fetch; the given codes are used) |

**Independent rate axis:** `mass_loss_provenance` (CR-22 `{supplied, class_default, none}`) is **unchanged
and never folded in**. A `--mass-loss-msun-yr` run keeps its identity-derived label. So EV Lac with
`--mass-loss-msun-yr 1e-13` now reports `wind_class: active` / `otype_auto` with Ẇ `supplied`. That is the
contract's "stays identity-derived" principle once the identity pass works; the contract's parenthetical
showing a `quiet` label was captured while the otype path was broken. This is **flagged to WB as a contract
erratum (§9-E1)**.

---

### 3a. `wind_otype_source` (MSG 266 additive ask, Greg-approved)
A fourth sibling field on every output / component: **`wind_otype_source`**.
- **Value:** the main_id of the object whose otype list was consulted, **when that object is not the
  resolved star or component itself**. Example: `exclusion-boundary --star "GJ 65"` → `wind_otype ["Er*"]`,
  `wind_otype_source "G 272-61A"` (the head `G 272-61` has no `Er*`).
- **`null` otherwise:** the star's own list (EV Lac), a degrade, no fetch, or `--component otype=`.
- It is derived from the fetch's `source_is_self` flag, not by string comparison, so the masked-main_id
  case is correctly `null`.
- APP emits it whenever the consulted list came from another object, **even when nothing matched**
  (`wind_otype null`). A head carrying `BY*` whose A object is quiet then explains itself; this is a
  superset of "supplied `wind_otype`", flagged in the build-complete MSG.

## 4. `exclusion-boundary` wiring (CR-25.1 + .2 + .3) — `query.py` + `core/exclusion_boundary.py`

### 4a. `compute_two_layer_boundary` (additive kwargs)
New kwargs: `otypes=None, wind_class_provenance=None, wind_otype=None, wind_class_note=None,
wind_otype_source=None`.
- `domain is None` (bare mass, `--object`): classify via `ew.classify_wind(…, otypes=otypes,
  wind_state=wind_state)`. A caller-passed `wind_class_provenance` **wins** (that is how `--object`
  becomes `object_preset`).
- Pre-classified (`--star`, `--spectral-type`): the passed fields are used.
- All four fields (incl. `wind_otype_source`, §3a) are emitted in **`base`**, so the windless and
  unmodeled early returns carry them too.
- **No other key or value changes.** The frozen `compute_exclusion_boundary` call is untouched (Q7).

### 4b. `cmd_exclusion_boundary` paths
- **`--spectral-type`:** `ew.classify_wind(sp_type=…, wind_state=args.wind_state)`, with the three fields
  threaded through `cls_kw` into every `two_layer` call. This is the defect-(i) fix. No otype, so no fetch.
- **`--star`** (after `sl`):
  1. If `sl["main_id"]` is truthy and `ew.otype_list_relevant(sp_type=sp, otype=ot)`:
     `fx = databases.fetch_star_otypes(sl["main_id"], primary_otype=ot)`, called as a **module attribute**
     so the test mocks bind. Otherwise `fx = None` (no network).
  2. `ew.classify_wind(sp_type=sp, otype=ot, otypes=fx["codes"] if fx else None,
     wind_state=args.wind_state)`.
  3. The fields are threaded into every downstream `two_layer` call (windless/unmodeled, evolved, MS).
  4. `wind_otype_source = fx["source_main_id"] if fx and not fx["status"] and not fx["source_is_self"]
     else None`, threaded like the other three fields.
  5. If `fx` has a status, top-level **`otype_status`** is set (a degrade-only key, placed like CR-23's
     `flame_status`).
  6. A candidate fallback to the head is **silent** here, and on every single-body path (§5b): the
     resolved target *is* the star (12/12 probed single stars don't resolve a distinct A), so a note there
     would be misleading. **Flagged to WB (§9-E3).**
- **`--object`:** passes `wind_class_provenance="object_preset"` when `_OBJECT_WIND_CLASS[key]` is not
  `None`. Windless presets get `null`.
- **`--mass-msun`:** unchanged call. The internal classify now emits `manual` or `null`.
- **Help text:** `--wind-state` changes from "a W-dot when the rate is unknown" to "sets the wind_class bin
  (overrides colour + otype auto-detect on MS stars; wall + γ>0 standoff Ẇ when no --mass-loss-msun-yr)".

---

## 5. `exclusion-system` coverage (CR-25.4 — REQUIRED) — `query.py` + `core/exclusion_system.py`

### 5a. System-level `--wind-state` (Q3b — MS components only)
- **Parser:** add `--wind-state {quiet,solar,active,hot}` to `exclusion-system`. `cmd_exclusion_system`
  passes `wind_state=args.wind_state` → `compute_exclusion_system(…, wind_state=…)` →
  `compose_exclusion_system(…, system_wind_state=…)` (a new additive kwarg).
- **Injection lives in compose** (it needs the domain):
  1. For each component **without its own `wind_state` and without its own `wind_class`**, compose first
     classifies it with the component's own inputs.
  2. **MS domain** → set `c["wind_state"] = system_wind_state`, then re-classify. The bin then honours it,
     and so do `_component_rex` and the point-mass calculation at γ>0 (inert at γ=0). This is exactly the
     `exclusion-boundary` MS behaviour.
  3. **Non-MS domain** → do **not** set `wind_state`, so neither the wall nor the γ>0 standoff sees it. Add
     `wind_class_note: "system --wind-state '{ws}' not applied: {an evolved|a windless (free-harbor)|an
     unmodeled} host — the identity-derived wind class stands"`.
  4. A component with its own `wind_class` is not injected. It gets the "superseded" note:
     `"system --wind-state '{ws}' not applied — superseded by the explicit wind_class '{wc}'"`.
  5. A component's own `wind_state=` always wins, and no note is emitted.
- **Deliberate γ>0 divergence (§10 R6, flagged §9-E4):** `exclusion-boundary --star <evolved> --wind-state X
  --gamma>0` feeds X into the frozen standoff (pre-existing; frozen and untouched). The `exclusion-system`
  system flag, per Q3b's "MS components", does not. At γ=0 both are identical.
- **Help:** the new `--wind-state` help, plus the `--component` help, now list `wind_class` and `otype`
  (`otype=BY*|Er*` uses `|`).

### 5b. Otype threading on the `--star` resolve (`_resolve_system_from_star`) — the contract's defect 3(b)
**Primary `otype` on every `--star` component is REQUIRED** (contract §"What CR-25 is" 3(b): the spec is
built "without an `otype` key, so `classify_domain_wind(otype=None)` drops even the primary otype").
- **Single-body paths** (`_single_body_component`: the named secondary, off-MS, no-orbit and wide member):
  - `comp["otype"] = sl["otype"]`.
  - **After the mass has succeeded** (so the `Wolf 9999` mass-error path at `test_exclusion_system.py:501`
    never fetches): if `sl["main_id"]` is truthy and
    `otype_list_relevant(sp, sl otype, class_tag)` → `fx = databases.fetch_star_otypes(main_id,
    primary_otype=sl otype)`, then `comp["otypes"] = fx["codes"]`, and `status_out["otype_status"] =
    fx["status"]` if set.
  - Both single-body meta builders (the named-secondary return `:658` and the no-orbit/wide return
    `:681-684`) propagate `otype_status`.
- **Binary path, component A** (the head `sl`):
  - `comp["otype"] = sl["otype"]`.
  - If relevant (head sp/otype): `fetch_star_otypes(main_id, primary_otype=sl otype)` with the
    **A-candidate rule**, then `comp["otypes"]`.
  - If `fx["fallback_to_head"]`, append `resolution_notes: "component A otype list taken from the system
    head '<head>' (no distinct '<cand>' SIMBAD object)"`. This is Q2's note; here the target is known to
    be a system.
  - Status → meta `otype_status_a`.
- **Binary path, component B:**
  - `comp["otype"] = comp_otype`.
  - If `comp_ok` and relevant (`comp_sp`/`comp_otype`/`comp_class`):
    `fetch_star_otypes(comp_sl["main_id"], primary_otype=comp_otype, component_rule=False)`.
  - Status → meta `otype_status_b`.
- `compute_exclusion_system` adds `otype_status`, `otype_status_a` and `otype_status_b` to its degrade-key
  loop (only when degraded, like `flame_status*`).
- **Intended side-effect (R3, §9 E5):** compose's WR/AGB-by-otype now agrees with the domain decision
  `_single_body_component` already makes with that otype, and with `exclusion-boundary`, which already
  classifies with `otype=ot`. An otype-only WR/AGB star on `exclusion-system --star` now gives an evolved
  result instead of "needs a positive mass_solar". No anchor is affected: the α Cen / Sirius heads are
  `SB*`, and B's otype is already used for its `class`.

### 5c. `compose_exclusion_system`
- **Classification:** each component is classified with `ew.classify_wind(sp_type, otype, class_tag,
  wind_class, wind_state, otypes=c.get("otypes"))`, with the §5a injection applied.
- **Emitted per component** (in each zone's `components[]` entry, next to `wind_class`):
  `wind_class_provenance`, `wind_otype`, `wind_class_note`, `wind_otype_source` (§3a; carried on the
  resolved component dict as `otypes_source`), plus an additive per-component
  **`mass_loss_msun_yr`**: the resolved Ẇ (`wall_inputs["wdot"]`), or `null` for windless/unmodeled. This
  satisfies the contract's CR-25.4 Output "per-component wind_class, **Ẇ**, wall…", which today has no
  field (flagged §9-E2).
- **`--component` specs** go through unchanged. The `otype=` string is split on `|` by the matcher, and
  there is **no fetch** on `--component` (the user supplied the identity). `_parse_component_spec` needs no
  change.
- **Merge / `wall_zones` / separations / point-mass logic untouched** (FYI iv). Only the per-component
  inputs they read change.

---

## 6. Files touched

| File | Change |
|---|---|
| `core/exclusion_wall.py` | matcher + `\|` form + WR/AGB-per-code; `_ms_wind` + Q8 notes; `_classify_identity` 4-tuple; `classify_wind` + wrapper; `otype_list_relevant` |
| `core/databases.py` | `fetch_star_otypes` + the seam + `_OtypeResultError` + `_simbad_otype_timeout` + the `[simbad]` warn (reuses `catalog._bounded_gaia_call`, imported lazily) |
| `core/exclusion_boundary.py` | `compute_two_layer_boundary`: 4 additive kwargs, emitted in `base` (the frozen generator is untouched) |
| `core/exclusion_system.py` | `system_wind_state` injection; otype/otypes threading (single-body + binary A/B); `otype_status*` meta; compose emits the fields + per-component `mass_loss_msun_yr` |
| `query.py` | `exclusion-boundary` `--spectral-type`/`--star`/`--object` wiring + help; `exclusion-system --wind-state` arg + pass-through + help |
| `tests/test_cr25.py` | **new**, offline (§7) |
| `tests/test_cr25_live.py` | **new**, live-gated anchors |
| `tests/test_cr23.py` | add a `core.databases.fetch_star_otypes` mock in `_mocks` (`:66-74`, covering the ε Eri K2V `exclusion-boundary` tests `:76/91/104/116`) and in `_sys_star` (`:159-175`, covering `:177/184`) |
| `tests/test_exclusion_system.py` | add the mock in the Cr13 `_run` helper (`:376-393`, covering Proxima `:416/426/436` and α Cen B `:443/475`) |
| `docs/integration.md` | CR-25 blocks on the `exclusion-boundary` + `exclusion-system` sections |
| `docs/testing.md` | `test_cr25.py` / `test_cr25_live.py` entries |
| `CLAUDE.md` | the test-count line + a concise CR-25 summary |

No change is needed (audited): `test_stellar_mass.py:258` (a G2V head, B lookup errors), `test_cr22`,
`test_query_exclusion_system` (`--component` only), `test_cr19:380-400`, `test_group_q` (frozen generator).

---

## 7. Test plan — new `tests/test_cr25.py` (offline; no socket; cache isolated)

**Isolation:** use the `_CatalogStateMixin` pattern (`test_cr19.py:53-68`):
- `SPACE_APP_CATALOG_CACHE=0`;
- pop `SPACE_APP_SIMBAD_TIMEOUT` and `SPACE_APP_SIMBAD_OTYPES_FORCE_UNREACHABLE`;
- the cache-hit/cache-discipline tests point `catalog_cache._CACHE_DIR` at a tmp dir
  (`test_catalog_cache.py:20-21`).

This way the tests never write made-up lists into the real `data/catalog_cache/`, and a warm cache can't
mask a missing mock.

**Test groups:**
1. **Matcher.**
   - Each of the 5 codes hits.
   - The traps miss: `UV`, `Ro*`, `V*`, `PM*`, `**`, `Em*`.
   - Case-insensitive whole-code matching; the legacy `Flare Star`/`UV Cet` names; the `|` form; list input;
     sorted canonical output.
   - The live-probe lists (the 9 WB stars, GJ 65 A/B, κ¹ Cet, EK Dra, α Cen B) as literal fixtures.
   - WR/AGB per code on the `|` form (`C*|BY*` → AGB), while a plain otype is byte-identical.
2. **Precedence** (`classify_wind`).
   - manual > otype > colour, each way.
   - EV Lac + `quiet` → quiet/manual with `wind_otype ["Er*"]` still shown.
   - τ Cet + `active` → active/manual.
   - κ¹ Cet / EK Dra → `solar`/`class_default`, `wind_otype null` (Q1).
   - O/B + `Er*` → not demoted.
   - Cool subdwarf `sdM1` + `Er*` → active. (`sdM1` takes the sd-prefix MS branch, colour M,
     `exclusion_wall.py:308`. The `colour or "K"` fallback is covered by mocking `_host_class`.)
3. **Q8 notes.** `hot` on F/G/K/M; `quiet`/`solar`/`active` on O/B; none on A or a colourless bare mass.
   The exact text is pinned, including the article ("an F", "an M", "an O", "a B").
4. **Q3a and "superseded" notes.**
   - `wind_state` on K0III (evolved, `class_default`), DA2 (windless, `null`) and sdB (unmodeled, `null`):
     the class is unchanged and the note is present.
   - An explicit `wind_class` + `wind_state` → the "superseded" note, and **no** Q8 note (the leak guard).
   - An explicit `wind_class` over a windless identity → no Q3a note.
5. **Provenance table (§3)**: one assertion per row.
6. **Back-compat / byte identity.**
   - `classify_domain_wind` is still a 3-tuple, and the CR-22 assertions hold.
   - `_component_domain` is unchanged.
   - An **oracle sweep:** the pre-CR-25 functions are copied into the test verbatim and compared with the
     new 3-tuple over a grid. The grid:
     - {every `_classify_identity` branch: the sp_type set, class_tags incl. `dwarf`/`giant`/`wd`, the
       WR/AGB otypes, object presets, a bare mass};
     - × `wind_state` ∈ {None, `active`};
     - × otype ∈ {None, `star`, `PM*`, `Flare Star`, `UV*`, `UV Cet …`};
     - plus the colourless cases (bare mass, `class=dwarf`) × all four states.

     Every cell must match, apart from the deliberately-changed ones: K/M + a non-`active` state, and
     non-K/M + a state, which are asserted separately.
7. **Fetch** (seam mocked at `Simbad().query_tap` / a fake table).
   - A distinct A-candidate → the A list; the same object → the head list, `fallback_to_head=True`;
     unresolved (only head rows) → the head list, `fallback_to_head=True`.
   - A letter-suffixed main_id → no candidate in the ADQL.
   - `component_rule=False` → a single id.
   - Apostrophe escaping (`NAME Barnard's star`).
   - A head that resolves under a different main_id → used.
   - Zero rows → `error`, primary fallback.
   - A watchdog timeout → `timeout`.
   - **A real `pyvo.dal.DALServiceError("Unable to access the capabilities endpoint … Connection failed")`
     and a `DALFormatError(requests.ConnectionError())` → `unreachable`.**
   - Retry-once: a failure then a success → no status.
   - The hook short-circuits before the cache and the seam.
   - `SPACE_APP_SIMBAD_TIMEOUT=0` → unbounded; non-numeric → the default.
   - A falsy main_id → `None`, no call.
   - **Cache discipline:** a degrade and an empty list never reach `cache_put`, and a cache hit skips the
     seam (tmp `_CACHE_DIR`).
   - A degrade has `fallback_to_head=False`.
8. **Gate** (`otype_list_relevant`).
   - K/M MS → true.
   - G/F/A/B/O, evolved, windless, unmodeled and colourless → false.
   - A G `--star` never calls the fetch.
9. **`exclusion-boundary` wiring.** In-process `query.cmd_exclusion_boundary`, using the CR-23
   `_run_boundary` pattern; `compute_simbad_lookup`/regions/FLAME/fetch are mocked.
   - `--spectral-type M4V --wind-state active` → active/manual/13.416.
   - `--star` EV Lac fixture, no flag → active/`otype_auto`/`["Er*"]`/13.416. With `quiet` → 0.424/manual.
   - With `--mass-loss-msun-yr 1e-13` → `supplied` + `otype_auto` (E1).
   - A GJ 65 fixture (the fetch returns the `G 272-61A` list) → active, `wind_otype_source "G 272-61A"`.
     EV Lac → `wind_otype_source null`; a degrade → `null`; no fetch (G) → `null`. A distinct A object
     with no active code → `wind_otype null` + `wind_otype_source` set (§3a).
   - τ Cet → solar 6.0, **no fetch call**.
   - `--spectral-type DA2|K0III|sdB --wind-state active` → Q3a note on the early and evolved returns.
   - The hook → `otype_status unreachable` + quiet. A primary-`BY*` fixture under the hook → still active.
   - `--object m-dwarf --wind-state quiet` → active, `object_preset`, "superseded" note.
   - `--gamma 0.2`: auto-detect with no flag → the curated error. `quiet` / `active` → standoffs equal to
     the pre-CR-25 values, and the wall changes only under `active`.
   - **The γ=0 `r_ex_au` is identical to the pre-CR-25 value in every case.**
10. **`exclusion-system` wiring** (resolver/binary-orbit/fetch mocked).
    - `--star` EV Lac single body → active/`otype_auto`, r_ex 30.38 @α=0.4, `mass_loss_msun_yr` 1e-13.
    - `--wind-state quiet` → quiet/manual.
    - `--component` cases, showing *fixed ≠ broken*:
      - **G2V + `wind_state=active` → active/manual (was solar);**
      - **M4V + `wind_state=solar` → solar/manual (was quiet);**
      - M4V + `wind_state=active` → active/manual;
      - G2V + `wind_state=solar` → solar/manual;
      - `class=M4V,otype=BY*|Er*` → active/`otype_auto`/`["BY*","Er*"]`.
    - System `--wind-state active` + a component with its own `wind_state=quiet` → the own value wins.
    - System `--wind-state` + a WD / K0III component → not injected, with the note. At γ>0 the evolved
      component still errors as before (E4).
    - System `--wind-state` + a component with its own `wind_class=` → the superseded note.
    - A binary with a distinct A-candidate → A's list only, B's own list, no union (an A-active + B-quiet
      split holds).
    - A binary with an unresolved candidate → the head list + the `resolution_notes` line.
    - `otype_status` on the **single-body** degrade; `otype_status_a` / `_b` on the binary degrade.
    - `Wolf 9999` (mass error) → no fetch.
    - **R3:** an `M5e` single body with otype `Mi*` → evolved, with no "needs a positive mass_solar" error.
    - The merged α Cen fixture (B = {`*`,`**`,`PM*`}) → standoffs, zones, `wall_zones` and the point mass
      are byte-identical to pre-CR-25 (only the additive per-component keys differ).
11. **No-socket guard** (a one-off build verification): once the §6 mocks are added, the whole offline
    exclusion set (`test_cr22`/`23`/`25`, `test_exclusion_system`, `test_query_exclusion_system`,
    `test_stellar_mass`, `test_group_q`, `test_cr19`) is run with `SPACE_APP_CATALOG_CACHE=0` and
    `socket.socket.connect` monkeypatched to raise. Nothing may connect.

**Live anchors — `tests/test_cr25_live.py`.** Gated like `test_query_exclusion_system_live.py`. Run with
`SPACE_APP_CATALOG_CACHE=0` so a warm cache can't substitute for SIMBAD; `--star-mass-catalog` where
relevant (WB's catalog path via env, else the internal seed).

**`exclusion-boundary`:**
- EV Lac:
  - default → active/`otype_auto`/`["Er*"]`/≈13.42, `wind_otype_source null`;
  - `--wind-state active` → `manual` + `["Er*"]`/13.42;
  - `quiet` → 0.424;
  - `--mass-loss-msun-yr 1e-13` → label active + `supplied`.
- Active by `Er*`: Proxima, Wolf 359, Ross 154, AD Leo. AU Mic → active. GJ 65 → active,
  `wind_otype_source "G 272-61A"`.
- Active by `BY*`: Barnard's (**no `otype_status`**) and ε Eri, whose standoff stays 43.69 @0.4.
- Unchanged: τ Cet solar 6.0 (+ `--wind-state active` → active); κ¹ Cet and EK Dra solar; Kapteyn's quiet.
- `--spectral-type M4V --wind-state active` → active.
- Q7 (EV Lac, α=0.4, γ=0.2): no flag → curated error; `quiet` → 10.529; `active` → 41.918.
- Degrade hook: EV Lac quiet + `otype_status`; Barnard's and ε Eri still active.

**`exclusion-system`:**
- EV Lac → active, `mass_loss_msun_yr` 1e-13, r_ex 30.38 @0.4; `--wind-state quiet` → quiet.
- `--component` G2V/active and M4V/solar.
- α Cen A 48.9669 / B 45.7214; B quiet; `wall_zones` unchanged.
- Sirius A 63.46 + B windless; Proxima 20.4824 (catalog).

## 8. `/code-review high` checkpoints

- **CP1 — classifier core + fetch helper** (after §1 + §2 + test groups 1–8). Focus:
  - the pinned `classify_wind` order, with no note leaking from an explicit `wind_class`;
  - the K/M gate and the exact-code guards;
  - the oracle sweep;
  - the 3-tuple back-compat;
  - the single-query ADQL and escaping;
  - status classification against the real pyvo exception types;
  - the cache discipline (the producer raises, degrades are built outside `cached()`);
  - hook ordering;
  - the letter guard;
  - the lazy imports (`stellar_mass` has no module-level `databases` import; its `databases`/`binary`/
    `catalog` imports are all inside functions, `stellar_mass.py:201/282`, so there is no import cycle.
    The new code imports `stellar_mass` + `catalog` lazily too).
- **CP2 — `exclusion-boundary` wiring** (after §4 + group 9). Focus:
  - every path emits the three fields, including the early returns;
  - `object_preset`;
  - no fetch on non-K/M or a falsy main_id;
  - `otype_status` only when degraded;
  - γ=0 `r_ex` byte-identity and Q7 at γ>0;
  - `mass_loss_provenance` untouched;
  - help text.
- **CP3 — `exclusion-system` coverage** (after §5 + group 10 + the §6 audit mocks). Focus:
  - MS-only injection and the three note cases;
  - never-union attribution; A-candidate vs head + the note;
  - fetch after mass success; both single-body meta builders;
  - `otype_status*`;
  - the R3 otype threading;
  - per-component `mass_loss_msun_yr`;
  - zones / `wall_zones` / point mass byte-identical;
  - no fetch on `--component`.
- **CP4 — whole-CR final pass** (after the no-socket run + the full suite + the docs). Focus:
  - cross-subcommand parity (the same star gives the same `wind_class` / provenance / `wind_otype`);
  - the docs match the code;
  - no CR-24 / CR-26 creep.

Each checkpoint's findings are triaged and folded in before the next.

## 9. Re-gate expectations (WB, live, sister venv — MSG 262 + 264 + review additions)

**Byte-identical standoffs at γ=0** (for `exclusion-boundary`, tag every value with its α):
- @α=0.4: α Cen A 48.9669 / B 45.7214; Sirius A 63.46 + B windless; ε Eri 43.69; Proxima 20.4824
  (catalog); EV Lac 30.38.
- @α=1/3: EV Lac 32.73.
- Sol 47.5 (`--object sun`, wall 6.0, `object_preset`).

**Changed walls (`wind_term`, α-independent):**
- 0.424 → **13.42** (both subcommands): EV Lac, Proxima, Wolf 359, Ross 154, AD Leo, AU Mic, GJ 65
  (`exclusion-boundary` via `G 272-61A`; on `exclusion-system --star "GJ 65"`, whatever topology
  binary-orbit returns, every K/M component takes its own A or B list and reads active).
- Barnard's → active `BY*` (the documented false-active); ε Eri → active `BY*` (a true active).

**Unchanged:**
- τ Cet solar 6.0; κ¹ Cet / EK Dra solar (Q1); Kapteyn's quiet 0.424.
- α Cen B quiet; α Cen `wall_zones` unchanged.

**Overrides:**
- `--wind-state active` → 13.42; `quiet` → 0.424.
- `--spectral-type M4V --wind-state active` → active.
- `tau Cet --wind-state active` → active.
- `--object m-dwarf --wind-state quiet` → still active (+ the superseded note).

**MSG 266 addition:** `exclusion-boundary --star "GJ 65"` → `wind_otype ["Er*"]`, `wind_otype_source
"G 272-61A"`; EV Lac → `wind_otype_source null`.

**Errata / items flagged for WB (E1–E6 all ACKED, MSG 266):**
- **E1:** EV Lac `--mass-loss-msun-yr 1e-13` → label **`active`/`otype_auto`** + Ẇ `supplied`, wall 13.42.
  The contract's "`quiet` label" parenthetical predates the otype fix; the principle it states (the label
  stays identity-derived) is kept.
- **E2:** a per-component **`mass_loss_msun_yr`** is added to `exclusion-system` components, so the CR-25.4
  "Ẇ" anchor is readable (additive).
- **E3:** the Q2 fallback note is emitted **only on the `exclusion-system` binary path** (component A of a
  known system). It is silent on `exclusion-boundary --star` and on the single-body `exclusion-system`
  paths, because the resolved target *is* the star and a candidate miss is the normal single-star case.
- **E4:** the system `exclusion-system --wind-state` reaches **MS components only**. At γ>0 an evolved
  component is not fed the flag, whereas `exclusion-boundary`'s frozen standoff does consume it on an
  evolved host (pre-existing; frozen; untouched). They are identical at γ=0.
- **E5:** R3, the primary-otype threading, is required by contract 3(b). Consequence: an otype-only WR/AGB
  star on `exclusion-system --star` classifies evolved, as `exclusion-boundary` already does.
- **E6:** CR-25.4 acceptance 3 as written (`M4V/active` → active, `G2V/solar` → solar) **already passes on
  today's code**, so it cannot detect a regression. Use `G2V/active` → active and `M4V/solar` → solar,
  which fail today and pass after CR-25.

**Degrade:** `SPACE_APP_SIMBAD_OTYPES_FORCE_UNREACHABLE=1` → EV Lac quiet + `otype_status: unreachable`;
Barnard's / ε Eri still active via the primary `BY*`.

**Other:**
- `--component otype=BY*|Er*` → active/`otype_auto`.
- A Q8 note in each direction; a Q3a note on windless and evolved hosts.
- `mass_loss_provenance` is unchanged from CR-22 everywhere.

## 10. Risks / accepted caveats

- **R1 — the 3-bin proxy over-states Wood-quiet flare/BY stars** (Barnard's, Proxima, Lalande 21185). This
  is documented; the exact override is `--mass-loss-msun-yr <Ṁ×2e-14>`, and CR-26 retires the proxy.
- **R2 — `Er*` is a SIMBAD parent category** (it also covers FU Ori, R CrB). Harmless under the K/M-MS
  gate.
- **R3 — primary-otype threading** (§5b, E5). Required by the contract; intended. It changes
  `exclusion-system --star` only for otype-only WR/AGB stars (no anchor).
- **R4 — the head-fallback degrade is imprecise.** *(Superseded at CP3, §13 deviation (a).)* A degraded
  component-A fetch now falls back to **nothing**, because binary A carries no head primary otype. It keeps the
  pre-CR-25 colour default, flagged by `otype_status_a`. The only head-list use is Q2's ruled fallback, when the
  A-candidate genuinely does not resolve; that case gets a `resolution_notes` line.
- **R5 — latency.** A K/M `--star` adds one SIMBAD TAP call (~0.3–6 s, bounded at 30 s × 2, cached for
  7 days). G and hotter add nothing.
- **R6 — the γ>0 evolved divergence** (E4) is documented.
- **R7 — the frozen `hot` mismatch** (standoff 1e-6 vs wall 5e-7 at γ>0) is documented, not changed
  (Q7 → CR-26).
- **R8 — offline-test socket leakage / cache poisoning.** Mitigated by the §6 mocks, the §7 isolation and
  the §7-11 no-socket run.

## 11. Build sequence (after Greg's go)

1. §1 classifier + §2 fetch + test groups 1–8 → run → **CP1** → fold.
2. §4 `exclusion-boundary` wiring + group 9 → **CP2** → fold.
3. §5 `exclusion-system` coverage + group 10 + the §6 audit mocks → **CP3** → fold.
4. The no-socket offline run; the full `venv/bin/python -m pytest -q` (**one heavy job at a time**); then
   the live battery on the APP venv (`SPACE_APP_RUN_LIVE=1 SPACE_APP_CATALOG_CACHE=0`, `test_cr25_live.py`
   + the exclusion live files).
5. Docs (§6) → **CP4** → fold.
6. Post the build-complete MSG (suite numbers + the APP live pre-check table + E1–E6) → WB re-gate →
   Greg's FULFILLED flip → commit CR-25-only on `main` + push + post the SHA. Then move this plan to
   `completed_plans/` and write the memory note.

## 12. Plan-review record (2026-09-24 — two read-only agents; all findings folded)

- **Code-grounded reviewer — 3 HIGH, 5 MED, 10 LOW.**
  - HIGH: pyvo exception types → CR-19 status classification (§2). An unresolved candidate must not
    degrade → the single-query route removes `query_object` entirely (§2). A degrade or empty result must
    not be cached → the producer raises and degrades are built outside `cached()` (§2).
  - MED: test cache isolation (§7). The single-query route (verified live, §0). The note leak (§1c). The
    injection scope (§5a / E4). The ambiguous `_classify_identity` contract → a 4-tuple (§1c).
  - LOW: fetch after mass success + both meta builders (§5b); a/an grammar (§1b); the sdM1 rationale
    (§7-2); falsy main_id (§2); WR/AGB on the `|` form (§1a); `fallback_to_head=False` on a degrade (§2);
    E3; `_bounded_gaia_call` backoff reuse (§2); `_make_simbad` timeout dropped (§2); the precise audit
    list (§6).
- **Spec-conformance reviewer — 0 HIGH, 8 MED, 14 LOW.**
  - MED: fixed-vs-broken `--component` tests + E6 (§7-10, §9). E1 erratum (§3, §9). MS-only injection
    (§5a). Per-component Ẇ (E2). Expanded live anchors (§7). α Cen B verified (§0/§9). R3 required, not
    optional (§5b/E5). The Q2 note scope (E3).
  - LOW: one-query route (§0/§2); the import claim corrected (§8 CP1); the stale Q8 note (§1c); table rows
    (§3); Q3a wording (§1c); cache isolation (§7); empty lists never cached (§2); wiring-test gaps (§7-9/10);
    a wider oracle sweep (§7-6); §0 row (ii-c) fixed; `exclusion-boundary` help (§4b); the GJ 65
    `exclusion-system` expectation (§9); Q7 pins (§7 live); Barnard's no-`otype_status` (§7 live).

## 13. Build log (2026-09-24) — checkpoint findings + deviations from §1–§5

**CP1** (classifier + fetch) — 10 findings, all folded:
- **Component-letter guard.** Widened to `[\s\d][A-Z]$`, because SIMBAD's own component ids have no space
  (`G 272-61B`).
- **`fallback_to_head` accuracy.** The query now selects `i.id` (the matched stored identifier). An A-candidate
  that resolves *to the head itself* (Sirius `* alf CMa A`, live-verified) is no longer a "fallback".
- **Raw-main_id cases.** The candidate-only and head-alias+candidate cases are now attributed correctly.
- **No retry on a deterministic result.** Only the network rows are bounded and cached; interpretation runs
  outside the retry, so an empty result is never retried.
- **pyvo directly.** The fetch uses `TAPService(...).run_sync` (no capabilities round-trip, no astroquery
  `lru_cache` pinning).
- **Circuit-breaker.** A per-process breaker trips on a timeout (60 s cooldown, cache-first).
- **Dead code.** `_ms_wind_class` / `_is_flare_otype` removed.
- **Shared helpers.** `_bounded_call`, `_env_timeout` and `_stderr_warn` moved to `core/shared.py`; CR-19's
  `catalog._bounded_gaia_call`, `_gaia_sync_timeout` and `_warn` are now thin wrappers (behaviour-identical;
  `test_cr19` green).
- **`main_id` stripping.** Normalized once on entry.

**CP2** (`exclusion-boundary`) — 7 findings, all folded:
- **Fetch placement.** The otype fetch moved into the MS branch after the mass resolves, through the shared
  `exclusion_system.resolve_star_wind` (one fetch→classify helper for both subcommands).
- **One identity pass.** `classify_wind` carries an `otype_list_relevant` flag.
- **Preset note.** Reworded ("the --object preset's wind_class … is fixed").
- **Help text.** `--wind-state` help corrected.
- **Pre-classify contract.** Documented: a pre-classifying caller owns the CR-25 fields.
- **Tests.** Non-MS `--star` branches are now tested by value, plus falsy-main_id no-fetch.

**CP3** (`exclusion-system`) — 10 findings, 9 folded, 1 declined:
- **Bin-scoped notes.** They say "does not set the wind bin", not "not applied". One shared
  `exclusion_wall.with_gamma_caveat` appends the γ>0 standoff caveat *only when a standoff exists* and the
  wind_state did not set the bin. It is used by both `two_layer` and compose (the two copies had drifted).
- **Withheld-flag error.** A system `--wind-state` withheld from a non-MS component now explains itself in the
  γ>0 "no wind input" error.
- **Per-component `mass_loss_provenance`.** Added.
- **Early argument checks.** `--alpha` / `--phase` are validated before any `--star` network call.
- **Queried candidate reported.** The fetch result now carries the `candidate` that was actually queried (the
  fallback note uses it).
- **`otype_list_relevant` function removed.** The flag lives on `classify_wind`.
- **`exclusion-system --wind-state` help.** Corrected.
- **Declined:** batching binary A+B into one TAP query. Two calls keep per-component status/caching simple, at
  about a second of extra latency.

**CP4** (whole-CR final pass) — 9 findings, all addressed:
- **Deterministic query failures.** A SIMBAD query error (`DALQueryError`) or a renamed result column now becomes
  `otype_status: "error"` and is never retried (`shared._bounded_call` gained `fatal=`).
- **Mixed-case own `wind_state`.** A component's own `wind_state=Active` is normalized before it reaches the FROZEN
  standoff; an unrecognized value still gets the curated error.
- **Cache key.** Now carries the queried A-candidate.
- **Fewer identity passes.** `resolve_star_wind(cw=…)` reuses `exclusion-boundary`'s classification.
- **Import tidy-up.**
- **Docs.** The E5 classification change is stated, and "γ=0 byte-identical" is qualified to cover every star
  whose classification is unchanged. The GJ 65 `wind_otype_source` example is caveated, since GJ 65 is itself
  unreachable (pre-existing).
- **R4 corrected.**
- **Q2 head-list fallback kept for binary A** (the reviewer's first finding). The reviewer noted it can carry a
  companion's code. That is the Q2 ruling (the head's list + a `resolution_notes` line, only when the A-candidate
  genuinely does not resolve); the docs now describe it precisely.

Final: suite **3554 passed / 102 skipped / 0 failures** (the baseline 3465/91 + 89 offline + 11 live-gated);
CR-25 live battery 11/11. **Pre-existing, not CR-25** (both reproduced identically on baseline `d2f20ac` with the
CR-25 tree stashed):
- 2 stale live asserts in `test_query_exclusion_system_live.py` (Sirius `out_of_domain` / `"white dwarf"` —
  pre-CR-22 strings).
- The Qt `QThread destroyed` core dump at interpreter exit after the suite reports.

**Deviations from §5 (reported to WB in the build-complete MSG):**
- **(a) Binary component A carries NO primary otype** (plan §5b said the head's). The head's primary is a
  system-level code that can be the companion's (EQ Peg-style: head `Er*`), so a degraded A fetch now falls back
  to nothing (the pre-CR-25 A), not to it. Single bodies and binary B keep their own primary (R3 stands there).
- **(b) The system `--wind-state` IS applied to an MS component with an explicit `wind_class=`** (plan §5a said
  "not injected"). The bin stays the explicit wind_class (a bin-scoped "superseded" note), but the γ>0 standoff
  Ẇ takes the flag, exactly as `exclusion-boundary --wind-state` does. At γ=0 there is no numeric difference.

**GJ 65 (MSG 264 anchor) — unreachable on both subcommands, and this is pre-existing (not CR-25):**
- `exclusion-boundary --star "GJ 65"` → "Temperature not available". `regions` needs a Teff that `G 272-61`
  lacks — the same class as Vega's no-Teff error — and it fires before the mass tiers or the wind.
- `exclusion-system --star "GJ 65"` → "could not resolve a mass", even with WB's catalog: the catalog lists
  `G 272-61A`/`B` but the resolved head is `G 272-61`, and binary-orbit finds no usable orbit.
- The CR-25 logic itself is verified two ways: live `fetch_star_otypes("G 272-61")` → the `G 272-61A` list
  (`Er*`), and the offline end-to-end fixture `Cr25BoundaryWiringTest.test_gj65_list_from_the_a_component`.


## 14. Re-gate result — ✅ FULFILLED (WB MSG 269, Greg signed, 2026-09-24)

WB ran `query.py` itself on the sister venv against the uncommitted CR-25 tree (`SPACE_APP_CATALOG_CACHE=0`,
`--star-mass-catalog`, `--gaia-timeout 120`, ~80 cases).

- **No-regression battery:** exact on the CR-13/14/16/22/23 cases — Sol 47.5 / 6.0; α Cen
  48.966852301574924 / 45.72136239364217; Sirius A 63.4590112071 + B windless; δ Pav 47.3285360708; Procyon A
  55.5345661307; ε Eri 43.6862396282 (`exclusion-boundary` == `exclusion-system`); Proxima 20.4823543466; EV Lac
  32.7303444098 @⅓ / 30.3809932625 @0.4; the windless paths; the >1.38 M☉ WD refuse.
- **CR-25 behaviour (all GREEN):**
  - The active K/M set now reads active, including EZ Aqr, Ross 248, Ross 128 and Lalande 21185 → 13.416407864998739.
  - Unchanged: τ Cet, κ¹ Cet, EK Dra, Kapteyn's, Lacaille 9352, ε Indi, σ Dra, α Cen B, 70 Oph A+B.
  - `wind_otype` agrees with WB's own astroquery SIMBAD lists.
  - Also verified: the overrides, the E6 pair, the notes, E1, the Q7 pins (10.5292144049 / 41.9175575489), the
    degrade hook on both subcommands (70 Oph `_a`/`_b`), no cache poisoning, and `wind_otype_source` (EQ Peg →
    `BD+19  5116A`; 70 Oph A → `* 70 Oph A` with no match).
- **Deviations (a) and (b):** both ACKED, verified live.
- **GJ 65:** disposition accepted (fetch-level evidence + `--component … otype=Er*`). WB logs the GJ 65 `--star`
  Teff/mass gap and `simbad-lookup "61 Cyg"` as a tooling OQ for a later CR.
- **Follow-up asked:** fix the 2 stale Sirius B live tests in a separate commit after this one.
- **Next in the chain:** CR-26; CR-24 stays parked.
