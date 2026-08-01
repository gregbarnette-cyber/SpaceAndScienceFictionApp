# Completed Plans

Implementation plans and mockups for work that is **built and shipped** — kept as the
historical record: the rationale, the measured numbers, and (where it matters) the
corrections that reviews forced.

Two entries are **`.html`, not `.md`** — the interactive Honorverse hyper-limit diagram
mockups (open them in a browser; they are self-contained, with no external assets).

Consolidated here 2026-07-27. This folder replaces the former `archive/` directory,
which held the pre-`PHASE_*`-era plans under a separate convention; those files are now
in here too, with the same history (moved with `git mv`).

**Still at the repo root** — not complete, so not here:

- `future_phases.md` — the forward-looking roadmap.
- `IMPROVEMENT_PLAN.md` — 8 phases shipped, but P4.6 is **PARTIALLY DONE**: the
  sexagesimal RA/Dec parser was never consolidated (4 copies across 6 call sites, with
  three different failure contracts). Stays at root until that closes.

> **Status headers in these files are unreliable.** Several read *"Proposed"* or
> *"Planned"* for phases that shipped long ago (e.g. `PHASE_AA`, `PHASE_V`, `PHASE_Y`,
> `PHASE_Z`, `PHASE_AD`, `PHASE_T`, `PHASE_OEC`). Completion here was verified against
> the shipped modules — `core/par_flux.py`, `core/thermal.py`, `core/formation.py`, … —
> not against the headers. Trust the code, then `CLAUDE.md`.

## Index (50 files)

| File | Title |
|---|---|
| [CONSISTENCY_PLAN.md](CONSISTENCY_PLAN.md) | Consistency Fix Plan |
| [GCNS_EXTENSION_REQUEST.md](GCNS_EXTENSION_REQUEST.md) | Feature Request: Extend the local catalog with GCNS for completeness + real distances |
| [JUMP_ROUTE_WAYPOINTS_PLAN.md](JUMP_ROUTE_WAYPOINTS_PLAN.md) | Jump-Route Waypoints — required `via` stars on the Phase I-OPTS B planner — built 2026-07-31 (all four phases; both `/code-review` checkpoints run, §12/§13 record the findings) |
| [INTEGRATION_PLAN.md](INTEGRATION_PLAN.md) | Integration Plan: SpaceAndScienceFictionApp → ScienceFictionResearch |
| [HYPER_LIMITS_DIAGRAM_MOCKUP.html](HYPER_LIMITS_DIAGRAM_MOCKUP.html) | Honorverse Hyper Limits (opt 14) — five diagram options for the 44-row bar chart (range bands / sequence line / class rings / reference-line strip / drill-down). **Open in a browser** — self-contained, interactive. Round 1 of the review that shipped the Class Rings + Class Sectors tabs, 2026-07-31 |
| [HYPER_LIMITS_RINGS_MOCKUP.html](HYPER_LIMITS_RINGS_MOCKUP.html) | Honorverse Hyper Limits (opt 14) — round 2: four ways to fit all 44 limits into the ring idiom (ghost rings / class sectors / drill-down / filtered). V1 + V2 were the ones built; records the measured density problem (40 of 44 limits inside 1.11–3.18 AU) |
| [PHASE_AA_PLAN.md](PHASE_AA_PLAN.md) | Phase AA — PAR / Photosynthesis by Stellar Type (`par-flux`) |
| [PHASE_AB_PLAN.md](PHASE_AB_PLAN.md) | Phase AB — Planetary Energy Balance / Terraforming (`equilibrium-temp`, `insolation-shif |
| [PHASE_AC_PLAN.md](PHASE_AC_PLAN.md) | Phase AC — ISM-Drag / Magnetic-Sail Calculators (Group K) |
| [PHASE_AD_PLAN.md](PHASE_AD_PLAN.md) | Phase AD — Calculator Completeness Follow-ups (Pkts 16–19) |
| [PHASE_AE_PLAN.md](PHASE_AE_PLAN.md) | Phase AE–AI — Exotic-Physics / Relativity / FTL-Precursor Calculators (Pkts 20–24) |
| [PHASE_AJ_PLAN.md](PHASE_AJ_PLAN.md) | PHASE AJ (Group P) — Planet-Formation Calculators — Implementation Plan |
| [PHASE_AK_PLAN.md](PHASE_AK_PLAN.md) | PHASE AK (Group Q) — Metric-Drive Power/Fuel + Exclusion-Boundary Calculators — Implemen |
| [PHASE_AL_PLAN.md](PHASE_AL_PLAN.md) | Phase AL — Power Generation / Storage / Thermal Calculators (Group R; Pkt 27) |
| [PHASE_AM_PLAN.md](PHASE_AM_PLAN.md) | Phase AM — `query.py` Catalog-Access Tier (VizieR + Gaia TAP + X-Match/HEASARC) & Binary |
| [PHASE_AN_PLAN.md](PHASE_AN_PLAN.md) | Phase AN — Bayer & Flamsteed Designations — built 2026-07-29 (carries a live D4 deferral: `star_systems.designations` needs an option-50 rebuild) |
| [PHASE_AO_PLAN.md](PHASE_AO_PLAN.md) | Phase AO — Gould Designations (Uranometria Argentina) — built 2026-07-29 |
| [PHASE_H_PLAN.md](PHASE_H_PLAN.md) | Phase H — Worldbuilding Calculators · Implementation Plan |
| [PHASE_I_OPTS_PLAN.md](PHASE_I_OPTS_PLAN.md) | PHASE I-OPTS — Route Planning: Four New Options · Implementation Plan |
| [PHASE_I_PLAN.md](PHASE_I_PLAN.md) | PHASE I — Multi-System / Route Planning · Implementation Plan |
| [PHASE_K_PLAN.md](PHASE_K_PLAN.md) | PHASE K — Honorverse Expansion · Implementation Plan |
| [PHASE_L_PLAN.md](PHASE_L_PLAN.md) | Phase L — Exoplanet Comparison Dashboard — Implementation Plan |
| [PHASE_M_PLAN.md](PHASE_M_PLAN.md) | Phase M — GCNS Interactive Surfacing · Implementation Plan |
| [PHASE_N_PLAN.md](PHASE_N_PLAN.md) | PHASE N — query.py Integration Expansion · Implementation Plan |
| [PHASE_OEC_PLAN.md](PHASE_OEC_PLAN.md) | Phase OEC — Open Exoplanet Catalogue Rebuild (menu option 7) |
| [PHASE_O_PLAN.md](PHASE_O_PLAN.md) | PHASE O — Visualization Expansion · Implementation Plan |
| [PHASE_P_PLAN.md](PHASE_P_PLAN.md) | PHASE P — Snow Lines & Alternative-Solvent Habitable Zones · Implementation Plan |
| [PHASE_Q_MOCKUP.md](PHASE_Q_MOCKUP.md) | Phase Q — Dossier Mockup |
| [PHASE_Q_PLAN.md](PHASE_Q_PLAN.md) | PHASE Q — System Dossier Export & Reporting · Implementation Plan |
| [PHASE_R2_MOCKUP.md](PHASE_R2_MOCKUP.md) | PHASE R2 — Constraint / Feasibility Engine · Analysis + Mockup |
| [PHASE_R2_PLAN.md](PHASE_R2_PLAN.md) | PHASE R2 — Constraint / Feasibility Engine · Implementation Plan |
| [PHASE_R3_MOCKUP.md](PHASE_R3_MOCKUP.md) | PHASE R3 — Research-Priors Hook · Analysis + Mockup |
| [PHASE_R3_PLAN.md](PHASE_R3_PLAN.md) | PHASE R3 — Research-Priors Hook · Implementation Plan |
| [PHASE_R3_V2_PLAN.md](PHASE_R3_V2_PLAN.md) | PHASE R3-V2 — Research-Priors Contract v2 (schema_version "2.0") |
| [PHASE_R_MOCKUP.md](PHASE_R_MOCKUP.md) | Phase R — Procedural System Generation & Feasibility Mockup |
| [PHASE_R_PLAN.md](PHASE_R_PLAN.md) | PHASE R1 — Procedural System Generation (engine + panel) · Implementation Plan |
| [PHASE_S_MOCKUP.md](PHASE_S_MOCKUP.md) | PHASE S — Project Workspaces (Campaign / Novel Manager) · Analysis + Mockup |
| [PHASE_S_PLAN.md](PHASE_S_PLAN.md) | PHASE S — Project Workspaces (Campaign / Novel Manager) · Implementation Plan |
| [PHASE_T_PLAN.md](PHASE_T_PLAN.md) | Phase T — `query.py` Research-Tooling Extensions — Build Plan |
| [PHASE_U_PLAN.md](PHASE_U_PLAN.md) | Phase U — Cooling-Primary HZ-Residence Calculator (`cooling-hz`) |
| [PHASE_V_PLAN.md](PHASE_V_PLAN.md) | Phase V — Power / Thermal / Shielding Calculators (`waste-heat` / `radiator-area` / `shi |
| [PHASE_W_PLAN.md](PHASE_W_PLAN.md) | Phase W — Rotating-Habitat Comfort Calculator (`spin-comfort`) |
| [PHASE_X_PLAN.md](PHASE_X_PLAN.md) | PHASE_X_PLAN.md — Closed-Loop Life-Support & Bioregenerative Calculators |
| [PHASE_Y_PLAN.md](PHASE_Y_PLAN.md) | Phase Y — STL Mission Energetics (`rocket-equation`, `beam-sail`) |
| [PHASE_Z_PLAN.md](PHASE_Z_PLAN.md) | Phase Z — Rotating-Structure & Megastructure Scale (`spin-stress`, `tether-taper`, `dyso |
| [ROUTE_FIND_PLAN.md](ROUTE_FIND_PLAN.md) | Route-Find — the O18 Find-Star box moved to the shared builder and wired to all 7 Route Planning panels |
| [ROUTE_CHART_REFACTOR_PLAN.md](ROUTE_CHART_REFACTOR_PLAN.md) | Route-Chart Refactor — the 7 Route Planning maps onto the shared builder (Phases 1–2) + the one-palette unification (Phase 3) |
| [SPECTRAL_CLASS_PLAN.md](SPECTRAL_CLASS_PLAN.md) | Spectral-Class Prefix Plan — search chips (Part 1) + colour/legend (Part 2) |
| [future_phases_archive.md](future_phases_archive.md) | Archived Phases — Space & Science Fiction App |
| [hypatia_implementation.md](hypatia_implementation.md) | Hypatia Catalog Integration — Phase 1: Option 8 (Star System Regions Auto) |
