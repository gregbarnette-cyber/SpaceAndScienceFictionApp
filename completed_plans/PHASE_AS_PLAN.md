# Phase AS (Packet 34) — Radiation dose → per-clade biological-ceiling converter

**Status: COMPLETE — built 2026-08-13.** One `query.py`-only, pure-math, self-validating
calculator for the sibling `scifiWorldBuilding-Claude` repo. Implements
`research/query-api-methods/radiation-dose-per-clade-ceiling-converter-request.md` **in full,
with no v2 / optional / deferred hedges** (its §0 + §6 mandate). No GUI, no CLI menu, no DB, no
RNG, no time, no network, no numpy. Phase-N/T/U…AR lineage.

## What was built

- **`core/radiation_tables.py`** — all bundled static data, isolated like
  `shielding_tables.py` / `cooling_tables.py`, every number carrying a source + confidence tag:
  the acute anchors (ARS/LD50, S1/S3/S4), the RBE(LET) grid (order-of-magnitude, S8), the ICRP
  60/103 Q(LET) relation, the fluence→dose constant, the clade ladder + lever specs (S11/S12/
  S14/S15/S61), the policy anchors (600/1000 mSv @ 3% REID, S5), the DMF cap (S10), DDREF, the
  SEU defaults, and the `PROVENANCE_LEGEND`.
- **`core/radiation.py`** — `compute_radiation_ceiling(...)`, pure logic (imports only the tables
  module). Resolves the exposure (absorbed dose, fluence, or a composite LET spectrum),
  composes the clade `(m_A, m_B)` from lever-tagged biology with the p53-trade enforcement,
  scores both axes independently, and takes the SEU path for `upload` / cyborg hardware fraction.
- **`query.py`** — import + `cmd_radiation_ceiling` + the `radiation-ceiling` subparser.
- **`tests/test_radiation.py`** + **`tests/test_query_radiation.py`** — the 8 §3 acceptance cases,
  every §3 edge, the validation matrix, determinism, the subprocess contract + exit-code matrix.
- Docs: `docs/integration.md` (contract row + detailed section), `docs/testing.md`, `CLAUDE.md`
  (core paragraph), `docs/gui-architecture.md` (roadmap row), this file + `completed_plans/README.md`.

## The model (governing relations)

**Two independent axes that never collapse to a scalar; a clade carries a modifier PAIR.**

- **Axis A — acute / deterministic (Gy, RBE-weighted).** `D_A = D_absorbed × RBE(LET)`;
  `ceiling = LD50_ref(3.75) × m_A × DMF`; report margin, `fraction_of_ceiling`, ARS band
  (`none/mild/ars-onset/ld50-region/supralethal`). A **chronic** exposure does NOT bind the acute
  ceiling (§2.1) — Axis A returns `applicable:false` + an optional tissue-reaction-rate check.
- **Axis B — stochastic / cancer (Sv, ICRP-Q-weighted).** `H = D_absorbed × Q(LET)`;
  `REID% = 3.0 × (H_eff_mSv / 600) × m_B_slope`, `H_eff = H/DDREF` for chronic. The reported REID
  scales from ONE science anchor (600 mSv → 3% REID, S5); the **selected career budget** (600 /
  1000 mSv) is a policy knob. A clade with better repair (`m_b<1`) reaches the policy REID
  acceptance at a larger dose → `clade_adjusted_budget = budget / m_b`.
- **RBE(LET) vs Q(LET) kept distinct** (§1.2). RBE is a bundled order-of-magnitude grid (peak
  ~100–200 keV/µm; high-LET elevated + uncertain, S8). Q is ICRP 60/103 (`Q=1` L≤10; `0.32L−2.2`
  10–100; `300/√L` >100; peak 29.8 at L=100).
- **Coupling (§2.3) is lever-tagged.** `repair-fidelity` may improve both axes; `p53` forces the
  trade (`f_a>1 ⇒ f_b≥1`), and a p53 lever improving both is a **hard block** unless
  `--allow-p53-double-improve` (S15 abstract-only — re-open before canon). `m_A` is **signed**: a
  lever factor < 1 lowers the ceiling below baseline (the S14 repair-disorder hypersensitivity,
  fatal ~3 Gy).
- **Clades (§2.4):** `baseline-human` (1.0, 1.0, physics-limit) · `gene-mod` (Dsup repair-fidelity
  lever f_a=2.0/f_b=0.7, extrapolation — NOT the ~3000× Deinococcus figure) · `cyborg` (bio
  fraction governs A/B + hardware→SEU) · `upload` (N/A both axes → SEU only, required-breakthrough)
  · `custom` (baseline + caller `--lever`).
- **SEU path (§2.5):** `upsets = fluence × per-bit cross-section × bits` vs an ECC margin, labelled
  a *different physical quantity* — never a Gy/Sv. The ECC scheme is not modelled.
- **Provenance:** every number carries a tag ∈ {physics-limit, present-datapoint, policy,
  required-breakthrough, extrapolation}; the legend rides in every response.

## Acceptance (§3) — all reproduced exactly (see `tests/test_radiation.py`)

| # | Result |
|---|---|
| 1 | baseline acute 4 Gy photon → `fraction_of_ceiling = 1.0667`, band `ld50-region` |
| 2 | baseline chronic 600 mSv low-LET → **REID 3.0% exactly**; Axis A not triggered |
| 3 | equal absorbed Gy: HZE (Q 29.8) → REID 14.9% vs photon (Q 1) → 0.5% |
| 4 | gene-mod Dsup → ceiling 7.5 Gy (~2×), tag `extrapolation` (not 3000×) |
| 5 | mis-engineered `custom` (repair-fidelity f_a 0.8) → ceiling 3.0 Gy < baseline |
| 6 | upload → A/B `applicable:false`, no Gy/Sv keys, `seu_budget` populated |
| 7 | p53 trade enforced (both worsen; double-improve blocked); repair-fidelity may improve both |
| 8 | >5000 Gy blocked w/o `--allow-required-breakthrough`; DMF clamped 3×; budget tagged `policy` |
| edges | zero dose → full margin both; fluence w/o quality → error; off-table LET → `out_of_range_let`; composite `--let-spectrum` dose-weights RBE & Q; acute scores both axes; `--ddref 2` halves chronic REID |

Full offline suite after the build: **2687 passed, 42 skipped, 494 subtests, 0 failures**
(was 2659; +28 new).

## Decisions taken (all ACCEPTED by the sister repo — see Review outcome below)

The append-only cross-repo channel is at **lowercase `/home/greg/claude/coordination-channel.md`**
(the file resolves lowercase on this machine; the folder casing varies by machine per
`docs/integration.md`'s invocation note). None blocked the build; each was implemented to pass §3
and offered for iteration per §5 — all four were accepted unchanged in the 2026-08-13 review.

1. **DDREF application point / case-2 exactness.** `H = Σ D×Q`; for chronic `H_eff = H/DDREF`;
   REID and budget-fraction use `H_eff`. **DDREF default = 1.0 (inert)** so "chronic 600 mSv → 3%
   REID exactly" reproduces on defaults; the disputed ~2× is opt-in via `--ddref 2` and flagged
   uncertain. (The alternative — default 2 with case 2 stated as an already-effective dose — is
   equivalent but breaks the acceptance literal on defaults.)
2. **"Signed `m_A`"** = a composed acute multiplier allowed **below 1.0** (a lower ceiling), not a
   literal negative (a negative ceiling is unphysical). Case 5 uses `f_a = 0.8` → 3.0 Gy.
3. **p53 hard-block** default-on but overridable (`--allow-p53-double-improve`), matching S15's own
   "abstract-only; re-open before canon" hedge.
4. **Flag / subcommand shapes** — `radiation-ceiling`; the `--lever {repair-fidelity,p53}
   --lever-m-a/--lever-m-b` custom-clade mechanism (cases 5 & 7); the `--let-spectrum "L:f,…"`
   composite form (the GCR/HZE case 3). Offered for iteration.

## Boundary honoured (§5 — locked out of scope, not deferred)

No shielding (→ `shielding-attenuation`), no trajectory dose accumulation (→ relativistic
`travel-time`/flux + `time-dilation`/`lorentz-factor`), no flight Sv/yr magnitude, no
dose→cruise-velocity mapping. The tool converts a *given* exposure to a per-clade ceiling and
asserts no flight-dose figure of its own.

## Review outcome (2026-08-13, coordination channel)

The research side (Packet 34) reviewed the build: **all 4 decisions ACCEPTED**, every anchor
verified against its pins, all 8 §3 cases reproduced live. It returned **two required
provenance-tag corrections** (tag-only, no numbers moved), both verified here against request §4
and applied:

- **F1** — `axis_b.provenance.reid_percent`: `physics-limit` → **`extrapolation`** (REID is a linear
  LNT projection off the 600 mSv @ 3% *policy* anchor, not a measured limit).
- **F2** — `axis_b.provenance.clade_adjusted_budget_sv`: `physics-limit` (via `clade_conf`) →
  **`policy`** (it is `600 mSv / m_b`, a policy budget). `_score_axis_b` lost its now-dead `clade_conf`
  param. `q_used` stays `physics-limit` (the ICRP Q factor genuinely is).

Plus three optional clarity items adopted (reviewer's discretion): an additive
`axis_a.ars_band_note` (the ARS band is absolute baseline-photon-equivalent, can diverge from the
clade-relative `fraction_of_ceiling`), an additive `axis_b.ddref_note` + `--ddref` help caveat (a
`--ddref > 1` disagrees with the NASA policy pairing, since the anchor already embeds low-dose-rate
effectiveness), and the DDREF source string. `REPAIR_DISORDER_FATAL_GY` kept as a documentation
anchor (consistent with the also-unused `VIC_THRESHOLD_GY`). New golden pins:
`test_policy_rooted_axis_b_numbers_are_not_physics_limit`, `test_ddref_note_surfaced_only_when_non_default`,
`test_acute_axis_a_carries_baseline_photon_equivalent_band_note`. Full suite after the fixes:
**2690 passed / 42 skipped / 494 subtests / 0 failures.**

The research side amended its own request §1.4 (DDREF default 1.0 + double-count caveat) and §2.1/§2.4
("signed" → "sub-unity m_A"), resolving the two spec contradictions decisions 1 & 2 surfaced.

## Delivery — CLOSED (2026-08-13)

`research` independently re-verified F1/F2 at the live tool and, per the coordination-channel
ownership rule, **flipped its own request file** (`radiation-dose-per-clade-ceiling-converter-request.md`)
to **`status: Deprecated` — fulfilled** with the DELIVERED banner + acceptance output. It logged the
Decision-3 tightening trigger (p53 block → unconditional + strict `f_b>1` once S15 re-opens) and the
optional `repair-deficiency` alias for the S15 re-open. Channel STATUS: **closed**. App-side code, tests,
and docs are complete; nothing pending on either side.
