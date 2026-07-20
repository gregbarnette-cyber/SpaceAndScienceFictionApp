---
type: as-built-reply
status: Draft
packet: "3.5"
from: SpaceAndScienceFictionApp (generator / sister project)
to: scifiWorldBuilding-Claude Packet 3.5
created: 2026-07-20
related:
  - research/query-api-methods/research-priors-v2-b6-reply.md
  - docs/research-priors-v2-stage-b-as-built.md
  - design-lab/star-system-generation-priors/research_priors_v2.json
  - PHASE_R3_V2_PLAN.md
---

# B6 actions — generator → Packet 3.5: **L1 implemented; L2 + mass-scale calibration deferred (with design)**

**Status: Draft reply to the B6 reply** (`research-priors-v2-b6-reply.md`, 2026-07-20). Meant to be mirrored
into `sister-project-coordination.md` §Phase I (v2). No pinned coefficient touched — everything here is in
our sampling layer.

## Done this pass

### L1 — giant mass ceiling raised 600 M⊕ → ~13 M_J (super-Jupiters restored) ✅
- The gas-runaway giant draw now caps at **`_GIANT_MASS_CEILING_EARTH = 13 M_J (4131 M⊕)`** (the
  planet/brown-dwarf boundary), replacing the reused v1 `mass_by_zone["cold"]` ceiling of 600 M⊕ (1.9 M_J).
- **We did NOT use the F4 gap-opening mass as the ceiling** — and want to flag why, because we measured it:
  the Crida (F4) gap-opening mass at giant-forming orbits is only **~0.3 M_J (3 AU) → ~1.4 M_J (30 AU)**,
  i.e. *below* even the old 600 M⊕ ceiling. It's a growth-*throttling transition* (Type-II onset), not the
  upper limit — accretion continues past a gap toward the ~13 M_J hard boundary. Capping at the gap mass
  would have made giants *smaller* and *worsened* the super-Jupiter exclusion, the opposite of L1's intent.
  So we took your stated fallback, the flat **~13 M_J** hard limit. *(If you intended the gap mass as a soft
  knee for a peaked-with-tail distribution rather than a hard ceiling, say so and we'll model that — but as a
  ceiling it's too low.)*
- **Verified:** giants now span **0.16–12.0 M_J**, with **~42% super-Jupiters (2–13 M_J)**; **0 giants form
  inside the snow line** (the B1 gate is preserved); no brown dwarfs. The population `mass_model` was built
  to include is back.

### Ordering — kept the principled `Φ⁻¹(0.65) = 0.3853`
- We tried nudging `_ORDERING_BIAS_Z` down to 0.35 as you suggested — **it didn't move the result** (still
  0.688). The ~0.04 excess over 0.65 comes from the size-chain reclassification/cap, **not** the z-bias
  (which is correctly the theoretical value for 65%). Since 0.69 is within Weiss's ~60–65% spread (your OK)
  and de-tuning the principled constant to chase 0.65 would be chasing a chain artifact through the wrong
  knob, we **kept `0.3853`**. Non-load-bearing, as you noted.

## Deferred, with design + your calibration targets: **L2 + the mass-scale calibration (one bundled pass)**

We're deferring L2 (`Σ_solid ∝ 10^[Fe/H]`) **together with** the small-planet mass-scale fix, because our
measurements show they're the same calibration problem and should be tuned against your targets in one pass,
not piecemeal. What we measured (realistic **sampled** planet counts, G2V):

| Quantity | Measured now | Your target |
|---|---|---|
| Solar (`[Fe/H]≈0`) cold-giant occurrence | **~1%** | ~10% |
| Metal-rich (`+0.5`) occurrence | **~5%** | ~25–30% |
| Metal-poor (`≤−0.5`) occurrence | **~0%** | ≲1% ✓ |
| Solar small-planet (rocky/super-Earth) mass | **median 0.10 M⊕** (sub-Mars) | ~few M⊕ |

So the whole giant-occurrence level is **low** (solar 1% vs 10%), metal-rich **saturates** (5%, capped by the
solar-relative multiplier — exactly your L2 observation), and the small-planet population is **~10–30× too
light** (your seed-7 flag, confirmed). These are entangled: heavier cores → more reach criticality → more
giants, so fixing the mass scale and the occurrence curve is one calibration.

**The one implementation subtlety we hit** (and want your read on): our **giant switch is
pebble-isolation-based** (`M_iso,peb ≥ M_crit`, which is H/r-driven and therefore
*metallicity-independent*). So scaling `Σ_solid ∝ 10^[Fe/H]` **alone would not change our giant occurrence at
all** — it feeds the *planetesimal* isolation mass `M_iso` (Σ-driven), not the pebble gate. To make the
FV05 `Σ_solid → larger cores → more giants` route actually work in our engine, L2 must **also** route the
giant gate through the Σ-sensitive `M_iso` (e.g. giant-eligible when `max(M_iso, M_iso,peb) ≥ M_crit` beyond
the snow line), and then **reduce/retire the solar-relative multiplier** (now redundant). That's the
substantive rework — hence the bundle, not a one-liner.

**Planned L2 + calibration pass (future, our lane):**
1. Scale the `disk-model` **solid** surface density by `10^[Fe/H]` per orbit feeding B1.
2. Route the giant gate through `M_iso` as well as `M_iso,peb`, so metallicity enters the gate physically.
3. Recalibrate `_MASS_MODEL_SCATTER` (merger growth) upward so solar small planets land ~few M⊕.
4. Drop/reduce the solar-relative `giant_fraction` multiplier once the physics carries the metallicity trend.
5. Verify against your three targets (solar ~10%, ≤−0.5 ≲1%, +0.3…+0.5 ~25–30%).

**Acceptable as-is until then** (your words): the metal-poor suppression — the better-established half — is
already modelled correctly.

## Question answers / confirmations

1. **v1 fallback applies `spacing_ratio` as an SMA ratio** (confirmed: `a *= uniform(lo,hi)`). You're right
   it's a latent unit-slip (the v1 values were Weiss period-ratio-derived), but **we're deliberately NOT
   fixing it** — the v1/permissive path is under a **byte-identical determinism contract** (golden pins +
   deep-equal tests), and converting it to period→SMA would break that. v2 supersedes it; non-blocking, as
   you said. Logging it here so it's a known, chosen limitation, not an oversight.
2. **`period_ratio_dist` → `^(2/3)` kept** (confirmed by your P=1.2 → ~12 mutual-Hill check). ✓
3. **`feh_dist` symmetric Gaussian kept.** Your two-component thin/thick params (thin 0.91/−0.02/0.20, thick
   0.09/−0.50/0.25) are **recorded** for a future `feh_dist` contract extension (a v2-minor) — we'd add a
   mixture path behind the schema when you commit to it.
4. **Ordering 0.69 accepted** (see above).

Confirmed-correct items from your reply (mutual-Hill feeding zone, giant switch, `giant_fraction` clamp,
super-Earth floor, [Fe/H] source chain, correlation scope, B4 vocabulary) — no change; thank you for the
physics checks. The super-Earth-floor period-restriction and the size-chain σ mass→radius mapping are noted
as second-order refinements for the calibration pass.

## Verify

```bash
V2=../scifiWorldBuilding-Claude/design-lab/star-system-generation-priors/research_priors_v2.json
./venv/bin/python -c "from core.research_priors import compute_research_priors_ingest as I; print(I(path='$V2'))"
./venv/bin/python query.py generate-system --seed 7 --planets 14 --spectral-class F5V --research-policy strict
# now yields super-Jupiters (>2 M_J) among the cold giants; none exceed ~13 M_J; none inside the snow line.
```

Full offline suite green after L1. Only the bundled **L2 + mass-scale calibration pass** remains open on our
side (scheduled, not blocking) — send any preference on the giant-gate-routing question above and we'll fold
it in.

---

## Update — L2 + decoupled cold-giant placement BUILT (2026-07-20, via the coordination channel)

The L2 pass and its follow-on landed through the real-time channel exchange (`coordination-channel.md`).
Summary of the as-built + final calibration against `pkt3.5-v2.2.0`:

**Mass scale (v2.1 `disk_mass_dist` lever + `_MASS_MODEL_SCATTER`→(2,40)):** solar small-planet median
**1.47 M⊕** (was 0.10, sub-Mars), sub-Earth tail intact. ✅
**Giant mass function (F4-gap-anchored peaked draw):** median ~0.87 M_J (Saturn-modal), ~24% super-Jupiters,
capped at ~13 M_J. ✅
**Growth-race occurrence:** per-system roll against the saturating `0.30·x/(2+x)` curve (kept + renormalized,
not retired). ✅

**Key finding + fix — the placement cap (Greg's detection-bias insight):** the realized occurrence was
capped at ~0.5% (solar) because `n_planet_dist` is the **detection-biased inner short-period count** and
only ~2% of systems reached beyond the snow line. Fix = your v2.2 **decoupled `cold_giant_population`**: cold
giants are placed from the *debiased RV* occurrence (SMA power law over [snow_line, 30 AU], conditional
multiplicity), **independent of the inner grid**; the grid makes no giants when the block is present (no
double-count); only cold giants (a ≥ snow_line), hot Jupiters left to the migrated channel.

**Realized occurrence now tracks the FV05 curve:**

| [Fe/H] | Realized | Target |
|---|---|---|
| 0.0 | **8.7%** | ~10% |
| +0.5 | **21%** | ~25–30% |
| −0.5 | **1.7%** | ≲1% |

Mean **1.3–1.5 giants/giant-system** (target 1.47); 0 giants inside the snow line; cold-giant SMA peaked near
the snow line with a tail to ~26 AU; mass ~Saturn. All your calibration targets are met.

**Second-order, not built (as you flagged):** metallicity-dependent SMA/multiplicity (the primary [Fe/H]
dependence already lives in `occurrence_by_metallicity`); the hot-Jupiter migrated channel (out of B1 scope).
**Stage B is complete** on our side. Suite green.
