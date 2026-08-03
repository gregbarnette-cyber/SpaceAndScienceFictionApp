# Phase AP / AQ / AR — Sensing (S) · Strategic-Geography (T) · Compute/Beamrider (U)

**Status: Complete (built 2026-08-02) — 7 new `query.py` subcommands + 1 behaviour-preserving refactor.**
**Source spec:** `scifiWorldBuilding-Claude/research/query-api-methods/sensing-detection-and-strategic-geography-calculators-request.md`
**Requester groupings:** "Group S / T / U" · **Repo phases:** **AP** (S) · **AQ** (T) · **AR** (U) — next free letters after AO.

Pre-staged the same way Group F preceded Pkt 13 (Phase V), Group Q preceded Pkt 25 (Phase AK), and
Group R preceded Pkt 27 (Phase AL). Serves the sibling repo's **Packet 30** (Sensing/Navigation/
Mapping/Surveillance — priority), **Packets 32/38** (Interstellar Economics / Strategic Geography /
Warfare), and **Packets 29/33** (Computation / Star-System Infrastructure).

## Contract (inherited — Phase V / Group Q/R)

Every item is **pure-math, self-validating, `query.py`-only**: no network (Group T reads the existing
`star_systems` catalog through the routing helpers — same read path as `jump-network`, no new dataset;
a star given by *name* resolves DB-first, SIMBAD only on a miss), no DB write, no GUI, no CLI menu, no
RNG, no wall-clock, no numpy. Bad input → curated `{"error": str}` (exit 1); malformed args → argparse
(exit 2). Every result dict carries a `model_note`. Every first-principles constant is caller-overridable;
bundled background/band presets are "transcribed, not fitted" with a source note + override flag.

## Item map

| ID | Subcommand | Module | Kind |
|----|-----------|--------|------|
| S2 | `angular-resolution` | `core/sensing.py` | Rayleigh/Dawes/Sparrow θ=k·λ/D (shared kernel) |
| S1 | `point-source-detection` | `core/sensing.py` | receiver-side detection range / SNR |
| S3 | `radar-range` | `core/sensing.py` | active radar range equation (R⁻⁴) |
| B  | `direct-imaging` (refactor) | `core/calculators.py` | IWA now calls the S2 kernel (coefficient 1.0) — no output change |
| T1 | `network-centrality` | `core/strategic_geography.py` | degree/betweenness/articulation/bridges/min-cut |
| T2 | `arrival-corridors` | `core/strategic_geography.py` | FTL-emergence picket geometry |
| U1 | `landauer-limit` | `core/thermal.py` | E_bit = k_B·T·ln2 |
| U2 | `beamrider-relay-spacing` | `core/power.py` | inverts `beamed-power-delivery` |

Group-U functions are placed **by domain, not in a junk "Group U" module** — the same house convention
that put Group R's `heat-pump` in `thermal.py` and its storage ceilings in `energy_storage.py`.

## Key decisions

- **D1 — flux-floor definition (routed to WB, not decided unilaterally).** The spec was
  self-contradictory: `--flux-floor-w-m2` named a W/m² floor but the formula (`R_max=√(L·A_rx·η/(4π·P_floor))`)
  and prose treated it as received power in W, and the printed pin (10.1 AU) was a 10× arithmetic slip.
  Raised via the append-only cross-repo channel `/home/greg/Claude/coordination-channel.md` (MSG 015);
  **WB ruled (A) in MSG 016:** it is an **irradiance floor → `R_max=√(L/(4π·floor))`, aperture-independent**.
  Corrected pin **4.04 AU**; WB fixed the three spec defect sites on their side. Riders adopted: (1) the
  `model_note` states `--rx-aperture-m`/`--optical-efficiency`/`--quantum-efficiency` are inert for the
  flux-floor solve (use the SNR path for an aperture-dependent range); (2) `--background` modes require a
  band (`--band` or `--band-min-m/--band-max-m`) since a bare `--wavelength-m` has no Δλ.
- **D2 — S2 as a shared kernel.** `sensing._rayleigh_theta` is the single home of the diffraction
  coefficient. `direct-imaging` calls it at **coefficient 1.0** (its historical 1·λ/D IWA convention),
  a behaviour-preserving DRY refactor — the existing `test_calculators.py` pins are unchanged. `sensing.py`
  imports only `core.equations`, so `core.calculators` importing it introduces no cycle.
- **D3 — T1 scale guard: cap + graceful null.** Degree/articulation/bridges/components (all O(V+E),
  iterative — survive the 256k catalog) run on any node set; **betweenness (Brandes) and min-cut
  (Edmonds–Karp) are capped at `_BETWEENNESS_CAP = 2000` nodes** — above it they return `null` with a
  `model_note`, never hang.
- **D3b — T1 `--weight {hops,distance,dust}` all built** (2026-08-02, user- + WB-directed — an earlier
  `hops`/`distance`-only cut was a spec violation of the no-defer rule and was corrected). `dust`
  weights each edge by the integrated A_V from the **dust-routing layer's own cost** (`dust_routing._seg`),
  floored positive so Brandes' tie logic holds; the graph layer never imports `dustmaps` (lazy, via
  `core.dust`), so the module stays importable on Windows and returns a curated error there. Min-cut
  stays topological (weight-independent). Golden pin (WB MSG 018 request): a dust wall on one corridor
  of a 4-cycle moves the S–T chokepoint from tied to the clear-corridor node (`betweenness D=1, M=0`).
- **D3c — min-cut endpoints resolve local-first** (WB MSG 018 note): a `--from`/`--to` already in the
  node set is matched by name before any SIMBAD call, so a `--within-ly` min-cut runs without astroquery.
- **D4 — T2 bearings in galactic (l,b).** Implemented via the standard J2000 equatorial→galactic
  rotation (`_EQ2GAL`); not load-bearing for any pin (both T2 anchors are frame-invariant), so it is
  display metadata on the bearing.

## Golden pins (verified §E + WB-corrected)

| Cell | Scenario | Pin |
|---|---|---|
| S1 | T=300 K, A=1000 m², ε=1 | L = 4.593×10⁵ W |
| S1 | L above, R = 1 AU, D=1 m, η=0.8, λ=10 µm | E=1.633×10⁻¹⁸ W/m²; P_rx=1.026×10⁻¹⁸ W; n=51.7 /s |
| S1 | **flux-floor (irradiance) 1e-19 W/m²** | **R_max = 4.04 AU (WB MSG 016; the 10.1 AU pin was retired)** |
| S2 | D=1 m, λ=10 µm | θ=1.22×10⁻⁵ rad = 2.516″; x_res(1 AU)=1825 km |
| S2 | D=6.5 m, λ=2 µm | θ=3.754×10⁻⁷ rad = 0.0774″ |
| S3 | 1 GW, 10 m dishes, λ=0.03, σ=100, R=1 Gm | P_rx=5.45×10⁻²⁰ W; R_max(P_min 1e-18)=4.83×10⁸ m |
| T1 | chain A–B–C–D | artic [B,C]; bridges [AB,BC,CD]; betweenness [0,2,2,0]; min-cut(A,D)=1 |
| T2 | 3 origins 90° apart, hw 5° | 3 corridors; coverage 0.57 % of sky |
| U1 | T=300 K | E_bit=2.871×10⁻²¹ J; 1 W → 3.483×10²⁰ bit/s; CMB → 2.608×10⁻²³ J |
| U2 | λ=1 µm, D_t=D_r=1000 m, thr=0.5 | L_t=4.10×10¹¹ m; L_relay=5.80×10¹¹ m ≈ 3.87 AU; 4 ly → 65,292 relays |

## Tests

`tests/test_sensing.py` + `tests/test_query_sensing.py` (S), `tests/test_strategic_geography.py` +
`tests/test_query_strategic_geography.py` (T, DB-free pure-core anchors + seeded-DB integration +
scale guard), and the U additions in `tests/test_thermal.py`/`test_power.py` (+ their `test_query_*`
siblings). See `docs/testing.md`.

## Docs / follow-ups

Contract mirrored into `docs/integration.md` (three new family sections) + the sibling repo's
`query-py-capability-cheatsheet.md` (new §18). **WB verified all 12 §E anchors + the flux-floor ruling +
the dust-weight cell live (coordination channel MSG 018/020) and flipped the source spec to
`Status: Deprecated — FULFILLED` on their side (2026-08-02).** Follow-ups → a new `*-followups.md`.

**Final interpretation point (MSG 021/022, ruled A):** S1's photon-rate "∫ over the band" is
descriptive, not a pinned deliverable — **band-centre λ (narrow-band conversion of the bolometric
`P_rx`) is the complete intended model** (no §E band-integral anchor; the anchor + the background term
both use band-centre λ; `E`/`P_rx` are bolometric). Added the one-line `model_note` boundary WB asked
for. **Conditional follow-up (NOT built — build only if a Pkt-30 wide-band detector case needs true
in-band counts):** a coherent band-limited radiometry mode would integrate `E`/`P_rx`/`n` **all** over
`[λmin,λmax]` (Planck-limited power + in-band photons, same band) — a *new quantity*, not a retrofit of
the bolometric model (option B, which mixes bolometric `P_rx` with an in-band `n`, was correctly
rejected). Route to a `*-followups.md` if ever needed.

**Verification note (memory-safe default):** the full `pytest -q` first OOM-crashed the 8 GB WSL box
because it loaded the real multi-GB dust cube mid-sweep. **Fixed** by gating *both* real-map loaders
(`test_dust_query.py::DustRealAnchorTest` and the live `network-centrality --weight dust` subprocess
test) behind the shared `tests/_dustcheck.heavy_dust_enabled()` opt-in (`SPACE_APP_RUN_HEAVY_DUST=1`).
A routine `pytest -q` now **auto-skips them → memory-safe by default** (validated live: 2685 passed /
3 skipped / 0 failures, ~2.2 GB peak, 10:12); the dust logic stays fully covered offline by mocked tests
(`DustEngineMathTest`, `test_dust_routing`, `DustWeightTest`). Run the real-map anchors on demand with
`SPACE_APP_RUN_HEAVY_DUST=1`. Only the **git commit** remains (both repos uncommitted per house pattern).
