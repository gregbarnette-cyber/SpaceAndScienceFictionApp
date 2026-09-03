# PHASE CR-19 PLAN (v3 — final, Scope A) — bound the **sync `gaia_tap` gateway** (fail-fast + retry-once + degrade-with-flag)

**Status:** FINAL DRAFT (2 plan-review rounds folded in). Contract LOCKED — WB MSG 203 (Q1–Q5) + MSG 205 (Scope A +
`gaia_status` + unreachable-TAP re-gate), Greg confirmed. **Build held for Greg's go.**
Channel: `/home/greg/Claude/coordination-channel.md` (201 reopen → 202 Qs → 203 locked → 204 scope-gap → 205 Scope A).
Spec: `scifiWorldBuilding-Claude/.../spaceapp-change-request-CR19-querypy-gaia-tap-timeout.md`.
v3 line-level corrections + per-branch marker propagation are from the two focused re-reviews.

## 0. Summary

Multiple **sync** Gaia-archive TAP calls have **no real wall-clock timeout** → the mass/identity resolvers hang for
minutes when the archive stalls. **Scope A (locked):** bound **every per-source SYNC `gaia_tap` call** at the one gateway
(FLAME + NSS + `binary_masses` + coords) with a wall-clock watchdog + one retry, then **degrade** (FLAME → tier-4
L-inversion; NSS/coords → the existing honest "no orbit / no companion" path) with a **visible marker + stderr warning**.
**Async census stays unbounded.** **No success-path value changes** on a reachable TAP (the frozen CR-13/14/15.4/16
battery + `ε Eri → gaia_flame 0.811` — which already exercises `binary_orbit` + FLAME — stays byte-identical). Only the
bounded/degrade branch is new.

## 0.1 Locked contract

- **Q1/Q2:** `flame_status` string `"timeout"`/`"unreachable"`, **degrade-only** on the mass block; no boolean;
  `mass_provenance` stays `ms_luminosity_inversion`; success + genuine-miss → **no key**. Never `"miss"`.
- **Q3:** `detection-completeness --star` OUT (NASA archive M★). On `exclusion-system --star` + `binary-stability-auto`:
  **attach `flame_status` to the per-component provenance since one IS exposed** (`mass_provenance_a`/`_b`) — see §2.5(C3).
  Universal stderr on every degrade.
- **Q4:** documented re-gate `SPACE_APP_CATALOG_CACHE=0 … --gaia-timeout 1`. Document in notes.
- **Q5:** default **60 s**; `--gaia-timeout <s>`; env `SPACE_APP_GAIA_TIMEOUT`; `0`=disable; retry→1 (2 attempts).
- **① Scope A:** bound the **sync `gaia_tap` gateway generically**. **Async untouched** (`binary.py:1080`).
- **② `gaia_status`:** string `"timeout"`/`"unreachable"`, **degrade-only**, on the **binary/orbit/multiplicity block**;
  a genuine no-rows result gets **no key**. Consumer: *`gaia_status` present ⇒ a Gaia call was bounded out → a
  negative (no-orbit / single) conclusion here is degraded, NOT authoritative.* Two keys / two blocks. Universal stderr.
- **③ Re-gate:** WB tests **both** a forced short bound **and** a genuinely blocked TAP, across **all four** sync sites.
  APP exposes `SPACE_APP_GAIA_FORCE_UNREACHABLE=1`.

## 1. Root cause + call map (verified in-code, HEAD `102267f`; WB re-verified MSG 205; lines re-checked in v3)

Gateway **`catalog.gaia_tap`** (`catalog.py:172`); only bound is `_timeout_ctx(300)`=`socket.setdefaulttimeout`
(`shared.py:1266`, reset by any dribble → wall-clock-unbounded) × `_with_retries(retries=3)` (`shared.py:1243`).
Sync callers that hang:
- **FLAME:** `gaia_astrophysical` (`catalog.py:291`, query at `:310`) — consumed by (a) `report._resolve_star_mass_block`
  (`:997`, via memoized `_gaia_astro` `:773`; **note** `_gaia_astro` is also read at `:1109` luminosity_consistency +
  `:1181` age — same memo, no extra call), (b) `databases._flame_mass_for` (`:4093`), and (c) **per-component**
  `stellar_mass.resolve_component_mass` (`stellar_mass.py:204`, **not** memoized, up to 2×) used by
  `binary_stability_auto`, `report._multiplicity_data_star` (via `resolve_binary_components` `:706`),
  `exclusion_system._resolve_system_from_star` (`:529/:545`).
- **coords:** `_resolve_binary_identity` → `gaia_tap(gaia_source)` (`binary.py:283`); returns `(ident, error)`.
- **NSS:** `_nss_two_body_solutions` → `gaia_tap(nss_two_body_orbit)` (`binary.py:333`); returns `(list, error)`.
- **binary_masses:** `gaia_binary_masses` → `gaia_tap(binary_masses)` (`binary.py:338`→`catalog.py:342`); returns
  `row|None`, **swallows** an error at `catalog.py:346`.
- **`binary_orbit`** (`binary.py:647`, builds `result` at `:705`) makes coords+NSS+binary_masses. Consumers (FOUR):
  `binary_stability_auto` (call at **`:1005`**, returns `out` from `stability_from_solutions`),
  `report._multiplicity_data_star` (**`:663`**, early-returns `:665/:667/:675`),
  `exclusion_system._resolve_system_from_star` (**`:504`**, returns a `(components, notes)` **tuple**, returns
  `:484/:492/:500/:517/:521`), and the **standalone `multiplicity` subcommand** `multiplicity_summary` (call at
  **`:413`**, builds its own `out` at `:509-515`). The standalone `binary-orbit` reader `_out`s the raw dict → carries
  `gaia_status` for free.
- **compare-stars** never calls `binary_orbit` (verified) → FLAME-only.
- **Generic `gaia-tap` subcommand** `cmd_gaia_tap` (`query.py:1246`) forwards `use_async=args.use_async` → **sync by
  default** → also caught by the sync bound (§2.7 B4).
- **Async (leave as-is):** `close_binary_census` → `gaia_tap(use_async=True)` (`binary.py:1080`) — the **only** internal
  async gaia_tap; a user `gaia-tap --async` likewise stays unbounded.
- Healthy latency: ε Eri 3.6 s / GJ 1002 5.8 s / HD 190360 4.6 s ⇒ 60 s = ~10× headroom (no false-degrade).

## 2. Design (the "how" — APP owns it)

### 2.1 Wall-clock watchdog — daemon thread (NOT `ThreadPoolExecutor`)

`shared._call_with_watchdog(fn, *, timeout)`: run `fn` in `threading.Thread(daemon=True)`, `join(timeout)`; alive →
abandon + raise `_WatchdogTimeout(Exception)`; finished-with-exception → **re-raise the original exception**; else return.
**Not `ThreadPoolExecutor`** (its workers are atexit-joined → would re-hang at exit). **No `socket.setdefaulttimeout`
mutation in the bounded path** (astroquery 0.4.11 exposes no per-request/`Gaia.TIMEOUT` bound; mutating the process-global
from an abandoned worker's late `finally` corrupts a later GUI call). The abandoned daemon lingers harmlessly.

### 2.2 Fresh Gaia client per attempt + bounded retry (retries=2)

`catalog._bounded_gaia_call(attempt_fn, *, timeout, retries=2)`: each attempt runs `attempt_fn` under
`_call_with_watchdog(timeout)`; on `_WatchdogTimeout` record `kind="timeout"`, backoff, retry else raise; on a network
exception record `kind="unreachable"`, backoff, retry else re-raise; success → return. **`attempt_fn` builds a fresh
`GaiaClass()` per call** (abandoned attempt-1 must not share astroquery's global `Gaia` session with attempt-2). The whole
attempt (`launch_job` + `get_results()` + shape) is inside the watchdog. Anonymous single-source `GaiaClass().launch_job`
≡ shared `Gaia` — asserted by a **live-gated** equivalence test (R5), since the offline suite patches `_attempt`.

### 2.3 `gaia_tap` — bound the SYNC path; ASYNC + disabled = byte-identical legacy

- `bound = _gaia_sync_timeout()` iff `not use_async`, else `None`.
- **`bound is None`** (async, or disabled via `0`/env/CLI): run the **current `_run` body verbatim** → byte-identical
  (async keeps its `ROW_LIMIT` save/restore + `retries=3, base_delay=3.0` — untouched).
- **`bound` set** (sync, enabled): circuit-breaker gate (§2.4) → else
  `catalog_cache.cached("gaia", params, lambda: _bounded_gaia_call(_attempt, timeout=bound, retries=2))` — **`params`
  unchanged** (cached rows still found); a cache HIT short-circuits with no bound. `except _WatchdogTimeout:` →
  `err["gaia_bound_reason"]="timeout"`; `except Exception as e:` → `_network_error_msg` + (bound set) `="unreachable"`;
  trip breaker (timeout only, §2.4) + `_warn` (§2.6) + return err.
- `gaia_bound_reason ∈ {"timeout","unreachable"}` is the **internal transport key**, on the *error* dict only (failure +
  bound-set only ⇒ never on success, never for non-bounded callers). Callers map it to `flame_status`/`gaia_status`.

### 2.4 Per-process circuit-breaker (aggregate bound)

Flag `catalog._gaia_sync_down` (+ recorded reason). **Trip only on a `timeout`** (the sustained stall — a blackholed host
manifests as a watchdog timeout; a fast `unreachable`/RST is cheap per-call and does NOT trip, so a transient blip can't
disable Gaia for the run — R4). When open, a subsequent bounded sync call **checks `cache_get` FIRST** (a cached row is
valid regardless of the breaker — R2); **only a cache miss** short-circuits to the recorded bounded error (no watchdog),
capping a fully-stalled subcommand at ~one timeout window. `catalog.reset_gaia_sync_circuit()` re-arms; **query.py never
resets** (one process = one run); **the GUI resets at the start of each user operation** (wiring TODO at CP1). `_warn`
fires on the **first** trip (+ a "further Gaia calls skipped" note) to avoid spam.

### 2.5 Marker surfacing — precise, per-branch (degrade-only)

**FLAME → `flame_status`.** `gaia_astrophysical` returns its error dict carrying `gaia_bound_reason`; the wrappers set
`flame_status` when provenance fell to `MS_INVERSION` **and** the reason is present:
- `report._resolve_star_mass_block` (`:997`) → `mass_block["flame_status"]`. (The `_assemble_sol` site `:1208` is
  `flame_mass=None` offline — **dropped**, confirmed dead.)
- `databases._flame_mass_for` (`:4085`, single caller — verified) → return `(mass_or_None, flame_status_or_None)`;
  `compare_stars` (`:4238`) sets `entry["flame_status"]`.
- **(C3 — per-component, honoring Q3(b)):** `stellar_mass.resolve_component_mass` (`:177`, returns `(mass, prov, note)`)
  → extend to return the FLAME reason; `exclusion_system` + `binary`'s `resolve_binary_components` attach a per-component
  `flame_status` alongside the exposed `mass_provenance_a`/`_b` (degrade-only), so a per-component FLAME timeout in
  `exclusion-system --star` / `binary-stability-auto` is flagged on the mass path — matching the MSG 205 re-gate wording.
  **Confirm the exact per-component shape with WB** (`flame_status_a`/`_b` vs a `resolution_notes` entry) in the
  plan-finalized note; default = `flame_status_a`/`_b`. Byte-identity holds (reachable TAP never degrades).

**coords/NSS/binary_masses → `gaia_status`** (binary block). Propagate the reason UP, and **each consumer captures
`bo.get("gaia_status")` BEFORE its error/empty/success branching**, attaching it to **every** degraded return:
- `_resolve_binary_identity` (`:257`) → return `(ident, error, gaia_status)` (carry the reason even when `ident is None`
  so a coords-timeout is flagged on the route_error).
- `_nss_two_body_solutions` (`:329`) → return `(list, error, gaia_status)`; **`gaia_binary_masses` (`catalog.py:332`)
  return contract → `(row_or_None, gaia_status)`** (R3/B3), threaded at `binary.py:338` and echoed to `_apply_binary_masses`
  (`:362`). A `binary_masses`-only timeout (NSS succeeded) **does** set `gaia_status` (per WB's inclusion of
  `binary_masses`); semantics per R9 (present-with-solutions ⇒ treat a *negative* cautiously, not "orbit is wrong").
- `binary_orbit` (`:647`) → `result["gaia_status"] = reason` (precedence `timeout` > `unreachable`) when any sub-call was
  bounded; and attach it to the early `_route_error` (`:657`) when identity failed on a bounded coords call. Degrade-only.
- **Four consumers, per-branch:**
  - `binary_stability_auto` (call `:1005`): `:1006 if "error" in result: return result` carries it for free; the
    **empty-solutions** branch (identity OK, bounded NSS) must set `out["gaia_status"] = result.get("gaia_status")` before
    returning `out` (`~:1038`).
  - `report._multiplicity_data_star` (`:663`): capture `gs = result.get("gaia_status")` right after the call; attach to
    the returned `data`/multiplicity block on **every** path incl. the early returns `:665/:667/:675`.
  - `exclusion_system._resolve_system_from_star` (`:504`, returns `(components, notes)` tuple): capture `gs` before the
    `bo.get("solutions", [])` read (`:505`); thread it out (append to `notes` as a structured entry **and** surface a
    `gaia_status` on the composed `exclusion-system --star` result) so a bounded coords/NSS no-orbit does NOT become a
    silent false single-body with mis-set exclusion radii.
  - **`multiplicity_summary` (`:374`, the standalone `multiplicity` subcommand):** capture `bo.get("gaia_status")` and set
    it on the `out` dict (`:509-515`) — else it ships `is_multiple:false` with no marker (B1). Added to scope.

### 2.6 Universal stderr — one `_warn()` seam, central emit in `gaia_tap`

`catalog._warn(msg)` (mockable module seam → `sys.stderr`), called **once per bounded sync call** from `gaia_tap`,
naming the query/table + reason (+ "→ degrading"). First `core/` stderr write — justified by Q3 (universal, non-silent),
safe (separate stream from stdout JSON), documented as an architectural exception. Emitted **only** when `bound` set (⇒
never on legacy/async). The breaker collapses repeats to one warning + a skipped-note (§2.4).

### 2.7 `--gaia-timeout` / env / hooks

- `_GAIA_TIMEOUT_OVERRIDE=None`; `set_gaia_timeout(v)`; `_gaia_sync_timeout()` → override → env
  `SPACE_APP_GAIA_TIMEOUT` → **60**. Parsing (R8): a value that **parses to ≤0 ⇒ disabled (`None`)**; a **non-numeric env
  ⇒ ignored → default 60** (try/except).
- `--gaia-timeout <seconds>` on the four subparsers (`dossier` `query.py:4121`, `compare-stars` `:4030`,
  `exclusion-system` `:3251`, `binary-stability-auto` `:3657`) + `set_gaia_timeout(getattr(args,'gaia_timeout',None))` at
  dispatch (`args.func(args)` `:4316`). Precedence CLI > env > 60.
- **`cmd_gaia_tap` (B4):** the generic `gaia-tap` sync path gets the **default** bound (improvement — it stops hanging;
  byte-identical on a fast success; a deliberately-heavy sync pull uses `--async` [unbounded] or
  `SPACE_APP_GAIA_TIMEOUT=0`). No `--gaia-timeout` flag on it. Documented, not a defect.
- **`gaia-astrophysical` / `binary-orbit` / `multiplicity` readers** also get the default bound. **C4:** the standalone
  `gaia-astrophysical` reader must **strip the internal `gaia_bound_reason`** from its returned error dict (internal-only)
  — or expose it as `flame_status` there; decide at CP2 (default: strip).
- **Test hook:** `SPACE_APP_GAIA_FORCE_UNREACHABLE=1` ⇒ the bounded sync path raises a simulated ConnectionError with no
  network (deterministic `"unreachable"` across all four sync sites) — for WB's blocked-TAP re-gate + offline tests.

## 3. Behavior matrix

| Situation | Bounded | Result | Marker | stderr |
|---|---|---|---|---|
| Reachable, FLAME row | no | `gaia_flame` | none | none |
| Reachable, genuine FLAME miss | no | `ms_luminosity_inversion` | none | none |
| Reachable, genuine no-orbit | no | honest empty `solutions`+`note` | none | none |
| FLAME stall (dossier/compare/excl/binary) | watchdog | inversion | `flame_status` (mass block / per-component) | 1 |
| coords/NSS/binary_masses stall | watchdog | degraded no-orbit/no-companion | `gaia_status` (binary block, all 4 consumers) | 1 |
| conn/job error after retry | raises | degraded | `…:"unreachable"` | 1 |
| breaker open (timeout earlier), cache miss | short-circuit | degraded | recorded reason | note |
| breaker open, cache HIT | no | cached value | none | none |
| tier-1/2 mass, or cache hit | never made | as today | none | none |
| `--gaia-timeout 0` / async | legacy | as today | none | none |

## 4. Byte-identity guarantees

1. Markers set only when `gaia_bound_reason` present ⇒ only on a bounded error ⇒ never on success/genuine-empty. **No key
   on the happy path** (positive test: a success result has no `flame_status`/`gaia_status` key at all — F10).
2. Reachable-TAP: bound never fires (~4–6 s ≪ 60 s); the frozen battery already exercises `binary_orbit` + FLAME →
   byte-identical.
3. Async + disabled: legacy `_run` verbatim. 4. Cache key unchanged. 5. `resolve_mass` untouched; fresh `GaiaClass`
   equivalence live-gated.

## 5. Change surface

- `core/shared.py` — `_call_with_watchdog` + `_WatchdogTimeout`.
- `core/catalog.py` — `_bounded_gaia_call`, `_attempt` (fresh `GaiaClass`), `gaia_tap` sync-bound branch +
  `gaia_bound_reason`, circuit-breaker (`_gaia_sync_down`/`reset_gaia_sync_circuit`, cache-first + timeout-only-trip),
  `_warn`, `_GAIA_TIMEOUT_OVERRIDE`/`set_gaia_timeout`/`_gaia_sync_timeout`, `SPACE_APP_GAIA_FORCE_UNREACHABLE`,
  `gaia_astrophysical` passthrough, **`gaia_binary_masses` tuple return**.
- `core/binary.py` — `_resolve_binary_identity` (3-tuple), `_nss_two_body_solutions` (3-tuple) + `_apply_binary_masses`
  call update, `binary_orbit` (`result["gaia_status"]` + route_error), `binary_stability_auto` (empty-branch copy),
  **`multiplicity_summary` (out-dict copy)**, `resolve_binary_components` (per-component `flame_status`).
- `core/report.py` — `flame_status` on the mass block (`_resolve_star_mass_block` only); `gaia_status` capture-before-
  branch in `_multiplicity_data_star` (all returns incl. `:665/:667/:675`).
- `core/databases.py` — `_flame_mass_for` tuple; `compare_stars` `entry["flame_status"]`.
- `core/exclusion_system.py` — `gaia_status` through `_resolve_system_from_star` (tuple return) + per-component
  `flame_status` via `resolve_component_mass`.
- `core/stellar_mass.py` — `resolve_component_mass` returns the FLAME reason (for C3).
- `query.py` — `--gaia-timeout` on the four subparsers + `set_gaia_timeout` at dispatch; strip `gaia_bound_reason` on the
  `gaia-astrophysical` reader (C4).
- `tests/test_cr19.py` — offline suite (§7) + a live-gated equivalence test.
- Docs — `docs/integration.md` (CR-19: `flame_status`, `gaia_status`, `--gaia-timeout`/env, degrade contract, re-gate
  incl. `SPACE_APP_CATALOG_CACHE=0` + `SPACE_APP_GAIA_FORCE_UNREACHABLE`); `docs/testing.md`; `CLAUDE.md`;
  `PHASE_CR19_PLAN.md` → `completed_plans/` + README (on completion).

## 6. `/code-review` checkpoints

- **CP1 — resilience layer (§2.1–2.4, 2.6).** Focus: watchdog (daemon/no-TPE/no-socket-global/fresh-`GaiaClass`/whole-
  attempt); async+disabled byte-identical; timeout-vs-unreachable + except-order + re-raise-original; **circuit-breaker
  (cache-first, timeout-only-trip, GUI-reset seam)**; cache non-poisoning; the single `_warn`.
- **CP2 — marker surfacing + CLI (§2.5, 2.7).** Focus: **per-branch `gaia_status` capture in all FOUR consumers**
  (error/empty/success, incl. the tuple return + `multiplicity_summary`); `binary_masses` reason ripple; `flame_status`
  on the mass block + **per-component (C3)**; NO key on success/genuine-empty; env/`0`/non-numeric; `--gaia-timeout` ×4;
  `cmd_gaia_tap` + `gaia-astrophysical` reader (C4); force-unreachable hook.
- **CP3 — final full diff.**
- **Local frozen-battery byte-identity spot-check** (pre-handoff): §7.3.

## 7. Test plan (`tests/test_cr19.py`, offline — no network; one live-gated equivalence test)

### 7.1 Unit
- `_call_with_watchdog`: slow → `_WatchdogTimeout` within ~timeout; fast → value; raising → original re-raised.
- `_bounded_gaia_call`: 2 attempts on repeated timeout → raise; 2 on ConnectionError → re-raise; timeout-then-success → ok.
- `_gaia_sync_timeout`: override>env>60; ≤0 → None; non-numeric env → 60.
- Circuit-breaker: trips on **timeout** only (not on `unreachable`); when open, **cache HIT returns cached** (no
  short-circuit) and **cache MISS short-circuits** (watchdog not invoked); `reset_gaia_sync_circuit()` re-arms.

### 7.2 Integration (monkeypatched / `SPACE_APP_GAIA_FORCE_UNREACHABLE`)
- FLAME timeout/unreachable → error + `gaia_bound_reason` + one `_warn`; success/miss → no marker.
- **dossier:** FLAME timeout → `regions.mass.flame_status`; coords/NSS timeout → `multiplicity.gaia_status`; success →
  **neither key present** (positive).
- **compare-stars:** per-star `flame_status` on timeout; absent on success.
- **exclusion-system --star:** bounded coords/NSS → result carries `gaia_status` (NOT a silent single-body); a
  per-component FLAME timeout → `flame_status_a`/`_b` (C3); returns bounded; stderr fired.
- **binary-stability-auto:** empty-solutions (bounded NSS) → `out["gaia_status"]`; route_error (bounded coords) → marker;
  per-component FLAME timeout → per-component `flame_status`.
- **standalone `multiplicity`:** bounded call → `gaia_status` present, `is_multiple` not asserted as a genuine single.
- **`binary_masses`-only timeout** (NSS succeeded) → `gaia_status` set with solutions present (R9 semantics).
- **breaker aggregate:** a stalled multi-call dossier makes ~1 watchdog wait then short-circuits the rest (bounded total).
- `resolve_mass(flame_mass=n)` untouched → `gaia_flame`, no key.

### 7.3 Byte-identity + knobs + live
- `--gaia-timeout 0` / async → legacy path (spy: watchdog not used). Generic sync `gaia_tap` → bounded but success
  byte-identical.
- **Live-gated (R5, `SPACE_APP_RUN_LIVE`):** fresh `GaiaClass().launch_job` ≡ shared `Gaia` for a real FLAME/NSS query.
- **Local battery spot-check (pre-handoff):** reachable → `dossier "epsilon Eri"` `gaia_flame 0.811`; CR-13/14/15.4/16
  anchors byte-identical (Sirius 2.063/0.4577/2.3136/74.142; α Cen B 1.079/0.909/2.749/86.652; excl α Cen 48.967/45.721
  {54.097,65.168}; Proxima cat 20.482; binary-orbit α Cen seq 815; Sirius B 2.063/0.4577; Procyon B = Procyon).
  Forced-degrade (Q4/③): `SPACE_APP_CATALOG_CACHE=0 … --gaia-timeout 1` **and** `SPACE_APP_GAIA_FORCE_UNREACHABLE=1` on
  ε Eri + a binary star → bounded + flagged across all four sync sites.

## 8. Re-gate handoff (WB, sister venv)

Reachable-TAP battery byte-identical + ε Eri 0.811; **and** a forced-short-bound + a blocked-TAP run
(`SPACE_APP_GAIA_FORCE_UNREACHABLE=1`) exercising **all four** sync sites → bounded + flagged (`flame_status` mass path
incl. per-component; `gaia_status` binary path incl. the standalone `multiplicity`) + stderr, never hanging; tier-2
cataloged star never enters FLAME. Then Greg's one FULFILLED flip → commit+push. Re-gate commands + the hook ship in the
docs.

## 9. Risks / edge cases

- **Abandoned daemon thread** runs the slow call to completion (no socket-global bound) — harmless daemon; dies with
  query.py; rare bounded GUI leak. Never `ThreadPoolExecutor`.
- **Circuit-breaker + GUI reset** must be wired per user operation (CP1 TODO).
- **Fresh `GaiaClass` equivalence** — live-gated test (R5).
- **`gaia_status` present ⇏ result wrong (R9):** with solutions present it means "a Gaia call was bounded; treat a
  *negative* conclusion cautiously." Document in the field notes.
- **Worker-thread astroquery module-globals (R10):** fresh `GaiaClass` fixes the session race; astropy/astroquery
  module-level config/logger writes during `launch_job` are mostly reads — low-probability abandoned-vs-retry race; note.
- **C3 shape** — confirm per-component `flame_status_a`/`_b` (vs a `resolution_notes` entry) with WB in the finalized note.
- **Non-MS host + FLAME timeout:** `mass_solar=None`, provenance `MS_INVERSION`, `flame_status` set — defined/acceptable.
- **Multiple bounded calls ⇒ multiple stderr** is contract-correct; the breaker collapses to one + a note.

## 10. Out of scope

`detection-completeness --star` (no FLAME); the **async** census (`use_async=True`); any success-path value; new WB data;
`resolve_mass`, the tier ladder, the mass catalog. `--gaia-timeout 0` restores today's unbounded path.

## 11. Addendum — `exclusion-system --component` uniform surface (WB MSG 209, post-CP3)

Greg's pre-flip request (forward-proofing the programmatic mass-resolving mode a TR-4 consumer may wire):
`compute_exclusion_system`'s `--component` branch passes `status_out` per component and surfaces a **positional**
per-component **`flame_status_<a+i>`** (`flame_status_a`/`_b`/…) `{"timeout"|"unreachable"}` on a bounded FLAME resolve —
on the composed result **and** on the no-mass error return — **degrade-branch-only**, matching the `--star` C3
convention. A **CLI-string** `--component` carries no `designations` (not a `_parse_component_spec` `_known` key) → never
resolves via FLAME → FLAME-free / deterministic / byte-identical, no marker (the skill's no-network re-gate fallback is
untouched). `--star` is unchanged (its re-gate stands). **Re-gate anchor:** a programmatic **dict** spec carrying
`designations` (triggers FLAME) + `luminosity_lsun` (inversion fallback) under `SPACE_APP_GAIA_FORCE_UNREACHABLE=1` →
`flame_status_a: "unreachable"` on the composed result; an explicit-mass component → no marker. Tests:
`test_cr19.py::ExclusionComponentFlameTest`. One clean quick `/code-review`.
