# PHASE K — Honorverse Expansion · Implementation Plan

> **Status:** plan written 2026-06-13. Mockup-gated (`mockups/phase-k.html`) — no code until the mockup is approved.
>
> **Scope: GUI-only feature work + a behavior-preserving data refactor.** Three new interactive calculators
> (`compute_hyper_translation_time`, `compute_impeller_wedge` in `core/science.py`; `compute_missile_intercept` in
> `core/calculators.py`), three new panels in `gui/panels/honorverse.py` under the existing **"Science Fiction"** nav
> category, and a one-time **centralization of the Honorverse data tables** into module-level constants so the new
> calculators and the existing display functions share one source. The three core functions **self-validate** (the
> Phase H `{"error": str}` contract). Pure math, **no network, no DB writes** (opt 14's hyper-limit table is the only
> DB read and Phase K does not touch it). Optional `query.py` subcommands are specified but gated on a build-time call.
>
> **Companion mockup:** [`mockups/phase-k.html`](mockups/phase-k.html) — interactive (client-side JS) over the real
> 24-band / 6-mass-band data.

---

## 0. Current state (what the brainstorm got wrong)

The `future_phases.md` Phase K brainstorm assumed the band/mass tables are *"hardcoded in `main.py`"* and need extracting.
**That is out of date.** The canonical tables already live in **`core/science.py`**:

- `compute_honorverse_acceleration_table()` — 6 mass-band rows; values are **display strings** (`"550 g"`), built from a local `raw` tuple list.
- `compute_honorverse_effective_speed()` — returns `{"bands": [...Alpha–Iota, Table 1...], "expanded_bands": [...Alpha–Omega, 24 bands, Table 2...]}`, built from local `band_data` / `expanded_data` tuple lists. Each expanded band: `{band, warship_xc, warship_ly_hr, merchant_xc, merchant_ly_hr, merchant_note}`.

The **GUI panels (15/16) already call these core functions**; only the **CLI `main.py` opts 15/16 still carry inline
duplicate tuple lists**. So the refactor is: hoist the tuples to module-level constants in `core/science.py`, point the
existing display functions at them, and (optionally) de-duplicate the CLI.

**Two data facts the calculators must honor:**
1. **Iota-merchant note.** Table 1 (`band_data`) marks Iota merchant *"Currently Unattainable"* (`merchant_xc = 0`); the 24-band Table 2 (`expanded_data`) gives every band a value. **K1 uses Table 2** (the only full-band source); the `" *"` note (Epsilon onward) means *"merchantmen do not normally operate in this band"* and is surfaced as a footnote — **not** as N/A. A band with `xc == 0` (defensive) still renders `travel_time = "N/A"`. *(Resolved 2026-06-13: the Table-2 expansion was corrected — see the box below — so its Iota multiplier now matches Table 1's canon 6000; the two tables agree on the multiplier basis, Table 1 merely displays Iota as unattainable.)*
2. **Accel values are strings.** `compute_honorverse_acceleration_table()` returns `"550 g"`. K2 needs the **number**. The refactor stores numeric g + numeric mass boundaries in the constant; the display function formats back to `"550 g"` (byte-identical output).

> **Source-data correction applied 2026-06-13 (before this phase builds).** The maintainer-authored 24-band Table 2 had two issues, both now fixed in `core/science.py`'s `expanded_data`: (a) a **−0.3 merchant transcription drift** from Pi (Π) through Omega (Π's merchant was `5321.2`, should be `5321.5 = ⅚ × warship`), and (b) the **Iota multiplier was smoothed to 5705** rather than the canon **6000** (Pearls of Weber). The fix re-anchors Iota = 6000 (warship `3600` / merchant `3000`) and shifts Iota–Omega up by a constant +295 multiplier (+177 warship, +147.5 merchant), preserving the band-to-band increments; merchant is now exactly `½ × multiplier` for all 24 bands, and Theta→Iota shows the canon +600 warship jump (= 0.6 × the +1000 multiplier jump). The **K0 parity test below locks the corrected values.** No tests referenced the old numbers (the change is data-only; opts 14/15 unaffected, opt 16's table simply shows the corrected speeds).

---

## 1. What gets built

| # | Feature | New panel | New core function | Module |
|---|---|---|---|---|
| **K0** | Data centralization (refactor) | — | `_HONORVERSE_ACCEL_BANDS`, `_HONORVERSE_BANDS`, `_HONORVERSE_EXPANDED_BANDS` constants + `get_*` accessors | `core/science.py` |
| **K1** | Hyper Translation Time | `HonorverseHyperTimePanel` | `compute_hyper_translation_time(distance_ly, ship_type)` | `core/science.py` |
| **K2** | Impeller Wedge Geometry | `HonorverseImpellerPanel` | `compute_impeller_wedge(ship_mass_tons, ship_type, wedge_power_pct)` | `core/science.py` |
| **K3** | Missile Intercept | `HonorverseMissilePanel` | `compute_missile_intercept(launcher_vel_xc, missile_accel_g, missile_delta_v_xc, target_vel_xc, range_lm)` | `core/calculators.py` |

All three calculators are **new, self-validating** functions (bad input → `{"error": str}`, never an exception leak), so
the GUI red-error label and any future `query.py` subcommand both work. Each is pure math; none needs a background thread.

---

## 2. K0 — Data centralization (WP1, behavior-preserving)

The single highest-risk item is the refactor, because it must not change opt 15/16 output. Do it first, guarded by a
parity test.

### 2a. `_HONORVERSE_EXPANDED_BANDS` (Table 2, 24 bands) — module-level
A list of dicts (or namedtuples) at module scope, lifted verbatim from the current `expanded_data`:
`{"band": str, "warship_xc": float, "merchant_xc": float, "note": str}` for Alpha … Omega (37.2/31.0 … 9949.2/8291.0, post-correction).
`compute_honorverse_effective_speed()` builds its `expanded_bands` from this constant (computing `*_ly_hr` as today via
`/ 8765.8128`). `get_honorverse_expanded_bands()` returns a copy for external callers. *(Table 1 `bands` Alpha–Iota stays
as-is, lifted to `_HONORVERSE_BANDS` the same way — K1 doesn't use it, but centralizing both removes the duplication.)*

### 2b. `_HONORVERSE_ACCEL_BANDS` (6 mass bands) — module-level, **numeric**
The current rows carry string g-values and a combined label. Replace with numeric fields + a derived label:
```
{"mass_min": 0,         "mass_max": 79_999,    "label": "0–79,999 (FG/DD)",
 "warship_normal_g": 550, "merchant_normal_g": 253, "warship_hyper_g": 5280, "merchant_hyper_g": 2429}
… 6 rows through "7,000,000–8,499,999 (SD)" (420/190/4053/1860) …
```
`compute_honorverse_acceleration_table()` is refactored to read this constant and **format the numbers back to the exact
strings it returns today** (`f"{g} g"`), so opt 15's table output is byte-identical. `get_honorverse_accel_bands()`
returns the numeric rows for K2. *(Mass boundaries are made explicit here rather than parsed from the label, so K2's band
selection is unambiguous — the current labels even have a transcription quirk, "80-499,999", that we don't want to parse.)*

### 2c. CLI de-duplication (optional, in-scope as a no-behavior-change refactor)
`main.py` opts 15/16 currently hold inline copies of these tuples. Refactor them to call
`core.science.compute_honorverse_acceleration_table()` / `compute_honorverse_effective_speed()` (the GUI already does).
This removes the duplication so the constants are the *only* source. **Gated by the parity test** (opt 15/16 output must
not change). If risk-averse, this can be deferred — the constants are authoritative regardless; mark it the last WP.

---

## 3. K1 — `compute_hyper_translation_time(distance_ly, ship_type)` (WP2)

Travel time for a given distance across all 24 hyper bands.

**Validation** (→ `{"error": str}`):
- `distance_ly > 0` (else `"Distance must be positive."`).
- `ship_type` normalized lower-case ∈ `{"warship", "merchantship"}` (else `"Ship type must be 'warship' or 'merchantship'."`).

**Algorithm:** for each band in `_HONORVERSE_EXPANDED_BANDS`, pick `speed_xc` = `warship_xc` or `merchant_xc` by ship type;
`speed_ly_hr = speed_xc / 8765.8128`; `travel_hours = distance_ly / speed_ly_hr` (→ `None` if `speed_xc == 0`);
`travel_time = format_travel_time(travel_hours)` (or `"N/A"` when `None`). Carry the band's `note` so the panel can append
the merchantmen footnote.

**Returns:**
```
{"distance_ly": float, "ship_type": str,
 "bands": [{"band": str, "speed_xc": float, "speed_ly_hr": float,
            "travel_hours": float | None, "travel_time": str, "note": str}],
 "footnote": str | None}
```
`footnote` is the merchantmen-don't-normally-use note when any returned band carries `" *"` and `ship_type == "merchantship"`, else `None`.

**GUI — `HonorverseHyperTimePanel`:** distance `QLineEdit` + ship-type `QComboBox` (Warship / Merchantship). Pure math.
Results via `make_table()` (Band | Speed (×c) | Speed (ly/hr) | Travel Time); `" *"` bands' rows in gray with the footnote
label below; `N/A` rows gray. Reuses the established `ResultPanel` pattern (no `DiagramToggleMixin`).

---

## 4. K2 — `compute_impeller_wedge(ship_mass_tons, ship_type, wedge_power_pct)` (WP3)

Effective acceleration and max velocities for a ship at a given wedge power.

**Validation** (→ `{"error": str}`):
- `ship_mass_tons > 0`; `0 < wedge_power_pct ≤ 100`; `ship_type ∈ {"warship", "merchantship"}`.

**Algorithm:**
- Select the mass band: first row with `mass_min ≤ ship_mass_tons ≤ mass_max`; a mass **above the top band clamps to the
  heaviest band** (documented behavior, not an error) — record `clamped: bool`.
- `base_accel_g` = `warship_normal_g` or `merchant_normal_g` from the band.
- `effective_accel_g = base_accel_g × wedge_power_pct / 100`.
- `max_vel_normal_xc = (0.8 if warship else 0.6) × wedge_power_pct / 100` (canon cap ≈ 0.8c warship / 0.6c merchant at full power).
- `max_vel_hyper_xc = max_vel_normal_xc` (hyper bands multiply at translation, not via the wedge — documented).
- `time_to_max_vel`: `t_s = (max_vel_normal_xc × _C_MS) / (effective_accel_g × _G_MS2)`; `format_travel_time(t_s / 3600)`.

**Returns:**
```
{"ship_mass_tons": float, "mass_band": str, "clamped": bool, "ship_type": str, "wedge_power_pct": float,
 "base_accel_g": float, "effective_accel_g": float,
 "max_vel_normal_xc": float, "max_vel_hyper_xc": float,
 "time_to_max_vel": str}
```

**GUI — `HonorverseImpellerPanel`:** mass `QLineEdit`, ship-type `QComboBox`, wedge-power `QSlider` (1–100) + live
`QLabel` readout. Recompute on slider move (cheap, no thread); a small "clamped to heaviest band" note when `clamped`.
Results table: the key/value rows above.

---

## 5. K3 — `compute_missile_intercept(...)` (WP4)

Whether a missile from a moving launcher intercepts a moving target. 1D head-on non-relativistic model (valid at these
×c scales). In `core/calculators.py` (reuses `_G_MS2`, `_C_MS`, `_M_PER_LM`).

**Validation** (→ `{"error": str}`): `range_lm > 0`; `missile_accel_g > 0`; `missile_delta_v_xc > 0`. (`launcher_vel_xc`
and `target_vel_xc` may be any sign/zero — `target_vel_xc > 0` = receding same-direction, `< 0` = head-on closing.)

**Physics:**
- `v_launcher = launcher_vel_xc × _C_MS`; `v_target = target_vel_xc × _C_MS`; `dv = missile_delta_v_xc × _C_MS`;
  `accel = missile_accel_g × _G_MS2`; `range_m = range_lm × _M_PER_LM`.
- `t_burn = dv / accel`; `v_burnout = v_launcher + dv`.
- `d_burn_missile = v_launcher × t_burn + 0.5 × accel × t_burn²`; target moves `v_target × t_burn` in the same frame.
- `v_close = v_burnout − v_target`. If `v_close ≤ 0` → **no intercept** (missile never catches the target post-burn).
- Closing distance during burn `= d_burn_missile − v_target × t_burn`; if `≥ range_m` → intercept **in the burn phase**
  (linear-in-time approximation for `t_impact`); else coast: `t_coast = (range_m − closing_during_burn) / v_close`,
  `t_impact = t_burn + t_coast`, phase `"coast"`.

**Returns:**
```
{"intercepts": bool, "intercept_phase": "burn" | "coast" | None,
 "time_to_impact_s": float | None, "time_to_impact_str": str | None,
 "v_burnout_xc": float, "v_close_xc": float, "range_at_burnout_lm": float, "burn_duration_s": float}
```
`intercepts == False` (with `intercept_phase = None`, times `None`) is a **normal result**, not an error.

**GUI — `HonorverseMissilePanel`:** five `QLineEdit` inputs. Verdict label (green "Intercept" / red "No intercept") +
profile table (Burnout velocity ×c, Closing velocity ×c, Range at burnout LM, Burn duration, Time to impact, Phase).

---

## 6. GUI wiring (WP5) — `gui/panels/honorverse.py` + nav + exports

- Three new classes in the existing `gui/panels/honorverse.py` alongside `HonorverseHyperPanel` /
  `HonorverseAccelPanel` / `HonorverseSpeedPanel`, all plain `ResultPanel` (no diagrams).
- `gui/panels/__init__.py` — export `HonorverseHyperTimePanel`, `HonorverseImpellerPanel`, `HonorverseMissilePanel`.
- `gui/nav.py` — extend the **"Science Fiction"** category (currently 3 entries) with: *Hyper Translation Time*,
  *Impeller Wedge*, *Missile Intercept*.

---

## 7. Optional `query.py` subcommands (WP-opt, build-time decision)

K's functions are clean factual calculators and fit the "factual-answer" exposure principle. If wanted:
`honorverse-hyper-time --distance-ly … --ship-type warship|merchantship`,
`honorverse-impeller --mass-tons … --ship-type … --wedge-power-pct …`,
`honorverse-missile --launcher-vel-xc … --missile-accel-g … --missile-delta-v-xc … --target-vel-xc … --range-lm …`.
Self-validating → curated `{"error"}` exit 1; argparse exit 2. **Not required for the GUI phase** — decide at build time.

---

## 8. Validation matrix (all → `{"error": str}` + red GUI label)

| Condition | K1 Hyper-Time | K2 Impeller | K3 Missile |
|---|---|---|---|
| Bad numeric | `distance_ly ≤ 0` | `ship_mass_tons ≤ 0`; `wedge_power_pct ∉ (0,100]` | `range_lm ≤ 0`; `missile_accel_g ≤ 0`; `missile_delta_v_xc ≤ 0` |
| Bad enum | `ship_type ∉ {warship, merchantship}` | same | — |
| Mass above top band | n/a | **clamp to heaviest** (not an error; `clamped=True`) | n/a |
| Non-error "negative" result | a 0-speed band → `travel_time="N/A"` (a value) | n/a | `intercepts=False` (a value) |

---

## 9. Tests — `tests/test_honorverse_expansion.py` (offline, pure math)

- **Refactor parity (K0):** assert `compute_honorverse_acceleration_table()` returns the exact 6-row string output it
  returns today (`"550 g"` …) after the numeric-constant refactor, and `compute_honorverse_effective_speed()` returns
  the same `bands` / `expanded_bands` (lock all 24 expanded bands + Table-1 9 bands by value). This proves the refactor
  is non-destructive **before** the calculators are added.
- **K1:** a known distance at a known band → hand-checked `speed_ly_hr = speed_xc / 8765.8128` and `travel_hours`;
  24 bands returned; merchant footnote present for `" *"` bands; `ship_type` case-insensitive; bad distance / bad
  ship_type → `{"error"}`. (Anchor: Alpha warship 37.2×c over 10 ly.)
- **K2:** band selection at each of the 6 boundaries (incl. exact-boundary values); mass above 8.5M → `clamped=True` at
  the SD band; `effective_accel_g = base × pct/100`; `max_vel_normal_xc` scaling (warship 0.8 / merchant 0.6);
  `time_to_max_vel` formatting; bad mass / bad pct / bad ship_type → `{"error"}`.
- **K3:** a clean intercept (closing, range covered) → `intercepts=True`, `intercept_phase ∈ {burn, coast}`, positive
  `time_to_impact_s`; a `v_close ≤ 0` case (target outruns burnout) → `intercepts=False, phase=None`; a burn-phase
  intercept (very short range) vs a coast-phase intercept; head-on (`target_vel_xc < 0`) closes faster than same-direction;
  bad range / accel / delta-v → `{"error"}`.

All offline, no network, no DB writes. (The opt-14 hyper-limit DB read is untouched and already covered elsewhere.)

---

## 10. Work-package order

1. **WP1 (K0)** constants + refactor `compute_honorverse_*` to read them → **parity test green** (no calculators yet).
2. **WP2 (K1)** `compute_hyper_translation_time` → its tests green.
3. **WP3 (K2)** `compute_impeller_wedge` → tests green.
4. **WP4 (K3)** `compute_missile_intercept` → tests green.
5. **WP5** panels + nav + exports.
6. **WP6 (docs)** `docs/science-and-scifi.md` (the three functions + the constants + the Table-1/2 reconciliation note);
   `docs/gui-architecture.md` (3 panel→nav rows); mark Phase K ✅ in `future_phases.md` at completion.
7. **WP-opt** CLI de-duplication (opts 15/16 → call core) and/or `query.py` subcommands — last, each behind its own gate.
8. Full suite: `pytest`.

---

## 11. Success criteria

- [ ] **Parity:** opts 15 and 16 (CLI and GUI) produce byte-identical output after the K0 refactor; the parity test is green.
- [ ] K1 returns 24 bands with correct `speed_ly_hr` / travel times; merchant `" *"` bands carry the footnote (not N/A);
      a 0-speed band → `"N/A"`; self-validates.
- [ ] K2 selects the correct mass band (incl. boundaries), clamps above the top band without error, and scales
      `effective_accel_g` / `max_vel` correctly; self-validates.
- [ ] K3's intercept and no-intercept (`v_close ≤ 0`) paths both work and never raise; burn-vs-coast phase is correct;
      self-validates.
- [ ] Three new "Science Fiction" nav entries; impeller slider updates live; missile shows a green/red verdict.
- [ ] No behavior change to opts 14/15/16 or any other feature; only `core/science.py`, `core/calculators.py`, `gui/`,
      docs (and optionally `main.py` for the de-dup) are edited.
- [ ] Whole suite green; all new tests offline (pure math, no network/DB-write).

---

## 12. Out of scope

- Relativistic missile/velocity corrections (the 1D non-relativistic model is canon-appropriate at ≤ ~0.8c).
- 2D/3D missile geometry (lateral target motion, evasion) — the model is deliberately 1D head-on.
- Changing any opt-14/15/16 **values** or the hyper-limit DB table (Phase K is additive + a presentation-neutral refactor).
- ~~Resolving the Table-1-vs-Table-2 Iota-merchant data discrepancy~~ — **done 2026-06-13** (Iota re-anchored to the canon
  6000 multiplier + the Pi–Omega merchant drift fixed; see the §0 correction box). Table 1 still *displays* Iota merchant
  as "unattainable" by design — that is a presentation choice, not a data mismatch.
- `DiagramToggleMixin` / visualizations (a hyper-band bar chart belongs to **Phase O10**, not K).
