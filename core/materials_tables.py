"""Phase Z — bundled material-strength + body-parameter tables (isolated static data).

For ``core.megastructure`` (Group H of the settlement/propulsion/astrobiology/terraforming
request; Packet 17). Isolated in its own module (like ``core.shielding_tables`` /
``core.spin_tables``) because these numbers are **present-day / near-term ancestors, not
2,500-yr ceilings** — the megastructure *physics* is durable (hoop stress σ=ρv²; the Pearson
uniform-stress taper); the material strengths are calibrated ancestors the setting improves
upon, and every value is caller-overridable (``--density-kgm3`` / ``--tensile-strength-mpa``).
Per the Mature-Technology Assumption, keep the two layers separate.

**Values RESEARCHED 2026-07-02 (WebSearch, cross-checked against the H1/H2 acceptance anchors):**
the two anchor-pinned rows — ``structural-steel`` (σ 400 MPa, ρ 7850 → v_max ≈ 226 m/s) and
``carbon-fiber`` (σ 4000 MPa, ρ 1600 → v_max ≈ 1580 m/s) — reproduce the request's H1 anchors, and
the taper closed form + the ``cnt-theoretical`` value together reproduce the canonical CNT taper
≈ 1.9. Sources in ``_SOURCES``. ``specific strength σ/ρ`` is the sole figure of merit (thin shell;
independent of thickness).

Two deviations from the request's first-draft provisional values (documented):
  * ``cnt-theoretical`` / ``graphene-theoretical`` bundled at the *literature theoretical /
    measured-intrinsic* strengths (CNT 100 GPa, graphene 130 GPa), not the conservative 50 GPa —
    the keys are named ``-theoretical``. Both HARD-flagged that bulk macroscopic material is 1–2
    orders of magnitude weaker.
  * ``carbon-fiber`` is the RAW FILAMENT figure of merit (T700-class ~4900 MPa), not a resin-matrix
    laminate (~600–1500 MPa) — stated in the flag so it isn't mistaken for a buildable panel.
"""

# material -> {rho (kg/m³), sigma_mpa (tensile, MPa), flag (caveat or None)}.
_MATERIALS = {
    "structural-steel":    {"rho": 7850, "sigma_mpa": 400,
                            "flag": None},
    "titanium-alloy":      {"rho": 4430, "sigma_mpa": 950,
                            "flag": None},
    "aluminium-alloy":     {"rho": 2700, "sigma_mpa": 500,
                            "flag": None},
    "carbon-fiber":        {"rho": 1600, "sigma_mpa": 4000,
                            "flag": "RAW FILAMENT (T700-class ~4900 MPa); resin-matrix laminate "
                                    "is far lower (~600-1500 MPa)."},
    "kevlar":              {"rho": 1440, "sigma_mpa": 3600,
                            "flag": None},
    "uhmwpe":              {"rho": 970,  "sigma_mpa": 2700,
                            "flag": None},
    "basalt-fiber":        {"rho": 2700, "sigma_mpa": 4100,
                            "flag": None},
    "silicon-carbide":     {"rho": 3200, "sigma_mpa": 400,
                            "flag": "BRITTLE: compressive (~2500 MPa) >> tensile (~350-400 MPa); "
                                    "the tensile figure limits a spinning shell."},
    "cnt-theoretical":     {"rho": 1350, "sigma_mpa": 100000,
                            "flag": "THEORETICAL: intrinsic 100-200 GPa (armchair ~120/zigzag ~94); "
                                    "single-tube measured ~63 GPa, defect-free bundles >80 GPa "
                                    "(Nature Nanotech 2018); BULK yarns ~1-8 GPa are FAR lower. "
                                    "MTA/extrapolated."},
    "graphene-theoretical":{"rho": 2200, "sigma_mpa": 130000,
                            "flag": "THEORETICAL: measured intrinsic ~130 GPa (Lee et al., Science "
                                    "2008); BULK material far weaker. MTA/extrapolated."},
}

# body -> R_km (mean surface radius), Rs_km (synchronous-orbit radius from centre),
#         g0 (surface gravity, m/s²), rot_h (rotation period, h; informational — ω is derived
#         from R/Rs via Kepler in the taper), note (optional caveat).
_BODIES = {
    "earth": {"R_km": 6371, "Rs_km": 42164, "g0": 9.81, "rot_h": 23.934, "note": None},
    "mars":  {"R_km": 3390, "Rs_km": 20428, "g0": 3.71, "rot_h": 24.623, "note": None},
    "ceres": {"R_km": 473,  "Rs_km": 1192,  "g0": 0.28, "rot_h": 9.074,  "note": None},
    "moon":  {"R_km": 1737, "Rs_km": 88400, "g0": 1.62, "rot_h": 655.7,
              "note": "the naive lunar-synchronous radius (~88 400 km) lies beyond the Hill sphere "
                      "/ near Earth-Moon L1; a real lunar elevator is the Pearson L1/L2 form, not "
                      "this simple synchronous taper. Taper reported with this caveat."},
}

_SOURCES = (
    "Hoop stress σ=ρv² (mechanics of materials); Pearson (1975) uniform-constant-stress space-"
    "elevator taper (Aravind, 'The Physics of the Space Elevator', Am. J. Phys. 2007; ISEC "
    "literature); Dyson collector A=f·4πR² (standard geometry). Material ρ/σ (researched "
    "2026-07-02): metal-strength charts (steel UTS 300-900, Ti-6Al-4V ~950, Al-alloy ~500) & "
    "density references (steel 7850 / Al 2700); Kevlar 49 ~3620 MPa/1440; basalt continuous fiber "
    "3000-4840 MPa/~2750; CNT single-tube ~63 GPa & bundles >80 GPa (Bai et al., Nature "
    "Nanotechnology 2018), theoretical 100-200 GPa; graphene intrinsic ~130 GPa (Lee, Wei, Kysar "
    "& Hone, Science 2008). Synchronous radii / rotation are standard astronomical values."
)

_MODEL_NOTE = (
    "Megastructure scale from material strength. σ/ρ (specific strength) is the sole figure of "
    "merit for a thin spinning shell (independent of thickness). Material strengths are IDEAL / "
    "present-day-to-near-term ancestors under the Mature-Technology Assumption — every value is "
    "caller-overridable (--density-kgm3 / --tensile-strength-mpa). Nanomaterials (cnt/graphene) "
    "are bundled at their THEORETICAL/measured-intrinsic strengths and HARD-flagged that bulk "
    "material is 1-2 orders weaker; carbon-fiber is the RAW FILAMENT value, not a laminate. Full "
    "megastructure economics / ring-shell dynamics / station-keeping defer to later packets; this "
    "is the material size-limit envelope only. " + _SOURCES
)
