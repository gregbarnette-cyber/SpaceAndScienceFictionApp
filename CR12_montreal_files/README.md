# CR-12 source archive — Bédard 2020 Montreal WD cooling sequences

Frozen copies of the public Montreal (Bergeron group) white-dwarf **evolutionary
sequences** that CR-12 uses to re-derive the `cooling-hz --track wd` cooling-age grid in
`core/cooling_tables.py`.

## Why these are committed here

CR-11.1 transcribed the ≥1.05 M☉ tail from these same files, but pulled them on a **different
machine** and never committed them — so when CR-12 needed to re-derive the ≤1.00 half, the
source data was gone and had to be re-fetched. Archiving the exact frozen files (with an md5
manifest) makes the CR-12 build **reproducible** and gives WB's independent re-gate the **same
frozen source** to re-derive against (WB re-derives from the seq files, not from the tool's
table). This closes the CR-11.1 "lost on another machine" gap.

## Provenance

- **Source:** `https://www.astro.umontreal.ca/~bergeron/CoolingModels/CoolingModels/seq_XXX_thick.txt`
  (http → 302 → https; fetch with `curl -sL`).
- **Model generation:** Bédard, Bergeron, Brassard & Fontaine 2020, **ApJ 901, 93** — Montreal
  DA **thick-H** (`q_H = M_H/M* = 1e-4`), **equimassic C/O core**, He mantle. 23 published
  sequences at **0.05 M☉ spacing, 0.20–1.30 M☉**.
- **Fetched:** 2026-08-26 (CR-12). See `MANIFEST.txt` for the per-file **md5 + model count + byte
  size** of all 19 files (0.40–1.30 M☉ — the tool's grid range).
- **Frozen-source cross-check:** this pull reproduces the verification's `wd-cooling-grid-verification.md`
  §3.1 verbatim pins **byte-for-byte** — e.g. `seq_100_thick.txt` model rows 64/65:
  `Teff=26239.5864 Age=1.054917E+08` and `Teff=25827.3842 Age=1.116121E+08` (→ interp 0.1095 Gyr
  at 25970 K). `seq_100/105/115` share a byte size by coincidence (same model count) but are
  distinct md5s / distinct data.

## File format

Fixed-width text; **3 lines per model**. The **first** line of each model carries the columns
CR-12 reads:

```
#Mod        Teff[K]      Log(g)        R[cm]         Age[yr]        L[erg/s]
```

The 2nd/3rd lines per model (Log(Tc)/Log(Pc)/…, Lnu/Log(H/*)/…) are core/abundance detail CR-12
does not use. Unit conversions applied in the transcription:

- `teff_k   = Teff`
- `radius_rsun = R_cm / 6.957e10`   (R☉ = 6.957e10 cm)
- `age_gyr  = Age_yr / 1e9`         (Age is **linear years**, not log)
- `log10_l  = log10(L_erg_s / 3.828e33)`   (L☉ = 3.828e33 erg/s)

## What consumes this

**Nothing at runtime.** The app ships the *bundled, resampled* `_WD_COOLING` table in
`core/cooling_tables.py`; these raw files are **provenance + reproducibility only**. `transcribe.py`
(added at build) regenerates `_WD_COOLING` from these files deterministically, so the table can be
rebuilt/audited without a network fetch.

## Lifecycle

Created at the repo root for **CR-12** (FULFILLED both sides, 2026-08-26 — plus the CR-12.4 ONe-core follow-up).
`PHASE_CR12_PLAN.md` moved to `completed_plans/` at FULFILLED (the standard plan move); **this directory stays at the
repo root** as committed reproducibility data — matching the repo's data-at-root convention (`gouldDesignations.csv`,
`missionExocat.csv`, etc.) and keeping the `core/cooling_tables.py` provenance reference valid. Not gitignored (only
`data/` is).
