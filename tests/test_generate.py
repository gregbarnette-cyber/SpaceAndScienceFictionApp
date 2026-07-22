# tests/test_generate.py — Phase R1 procedural generator.
#
# R1-C1 scope (offline, pure): the synthetic-realism priors provider
# (core.priors.DefaultPriors — the R3 seam) and the two new astronomy helpers in
# core.generate — _classify_planet (G3, mass-class + snow-line modifier +
# radius) and _equilibrium_temp (G4, the Phase P implied_edge_temp wrapper).
# Later checkpoints (C2 synthetic mode, C3 real-anchor, C4 query.py) append here.

import math
import unittest
from contextlib import ExitStack
from unittest import mock

from core.priors import DefaultPriors
from core.generate import (
    generate_system,
    _classify_planet,
    _equilibrium_temp,
    _radius_earth_for_type,
    _M_JUPITER_EARTH,
    _BROWN_DWARF_MIN_EARTH,
    _SUPER_JOVIAN_MIN_EARTH,
)
from core.equations import (
    _t_ref_equilibrium,
    _EARTH_RADIUS_KM,
    _KM_PER_AU,
    compute_star_luminosity,
    compute_habitable_zone,
    compute_roche_limit,
    compute_hill_sphere,
)


class TestDefaultPriors(unittest.TestCase):
    def setUp(self):
        self.p = DefaultPriors()

    def test_grounding_tag(self):
        self.assertEqual(DefaultPriors.grounding, "default-extrapolation")
        self.assertEqual(DefaultPriors.name, "DEFAULTS")

    def test_spectral_weights_ordering(self):
        w = self.p.spectral_class_weights
        # M ≫ K > G > F > A > B, all positive.
        self.assertTrue(all(v > 0 for v in w.values()))
        self.assertGreater(w["M"], w["K"])
        self.assertGreater(w["K"], w["G"])
        self.assertGreater(w["G"], w["F"])
        self.assertGreater(w["F"], w["A"])
        self.assertGreater(w["A"], w["B"])
        # O excluded (too rare / short-lived for stable systems).
        self.assertNotIn("O", w)

    def test_n_planet_dist_peaks_in_band(self):
        d = self.p.n_planet_dist
        self.assertTrue(all(v >= 0 for v in d.values()))
        peak = max(d, key=d.get)
        self.assertTrue(2 <= peak <= 6)

    def test_spacing_ratio_band(self):
        lo, hi = self.p.spacing_ratio
        self.assertLess(lo, hi)
        self.assertGreaterEqual(lo, 1.0)   # adjacent orbits must widen outward
        self.assertLessEqual(hi, 3.0)

    def test_mass_by_zone_shape(self):
        z = self.p.mass_by_zone
        for key in ("hot", "hz", "cold", "far"):
            self.assertIn(key, z)
            lo, hi = z[key]
            self.assertGreater(lo, 0.0)
            self.assertLess(lo, hi)

    def test_moon_priors(self):
        lo, hi = self.p.moon_count
        self.assertGreaterEqual(lo, 0)
        self.assertLessEqual(lo, hi)
        mlo, mhi = self.p.moon_mass_frac
        self.assertGreater(mlo, 0.0)
        self.assertLess(mlo, mhi)
        self.assertLess(mhi, 1.0)


class TestClassifyPlanet(unittest.TestCase):
    # No snow line → no modifier; classify purely by mass.
    def test_base_types_by_mass(self):
        self.assertEqual(_classify_planet(0.5, 1.0)[0], "rocky")
        self.assertEqual(_classify_planet(1.0, 1.0)[0], "rocky")
        self.assertEqual(_classify_planet(5.0, 1.0)[0], "super_earth")
        self.assertEqual(_classify_planet(17.0, 1.0)[0], "ice")
        self.assertEqual(_classify_planet(100.0, 1.0)[0], "gas")
        self.assertEqual(_classify_planet(800.0, 1.0)[0], "super_jovian")
        self.assertEqual(_classify_planet(5000.0, 1.0)[0], "brown_dwarf")

    def test_exact_boundaries_are_inclusive_lower(self):
        # Each threshold belongs to the heavier class (>=).
        self.assertEqual(_classify_planet(2.0, 1.0)[0], "super_earth")
        self.assertEqual(_classify_planet(2.0 - 1e-9, 1.0)[0], "rocky")
        self.assertEqual(_classify_planet(10.0, 1.0)[0], "ice")
        self.assertEqual(_classify_planet(10.0 - 1e-9, 1.0)[0], "super_earth")
        self.assertEqual(_classify_planet(50.0, 1.0)[0], "gas")
        self.assertEqual(_classify_planet(_SUPER_JOVIAN_MIN_EARTH, 1.0)[0], "super_jovian")
        self.assertEqual(_classify_planet(_SUPER_JOVIAN_MIN_EARTH - 1e-6, 1.0)[0], "gas")
        self.assertEqual(_classify_planet(_BROWN_DWARF_MIN_EARTH, 1.0)[0], "brown_dwarf")
        self.assertEqual(_classify_planet(_BROWN_DWARF_MIN_EARTH - 1e-6, 1.0)[0], "super_jovian")

    def test_snow_line_modifier(self):
        snow = 3.0
        # super-Earth at/beyond the snow line → ice (volatile envelope).
        self.assertEqual(_classify_planet(5.0, 3.0, snow)[0], "ice")   # a == snow (>=)
        self.assertEqual(_classify_planet(5.0, 4.0, snow)[0], "ice")
        # super-Earth inside the snow line → stays super_earth.
        self.assertEqual(_classify_planet(5.0, 1.0, snow)[0], "super_earth")
        # rocky beyond the snow line stays rocky (too light to hold an envelope).
        self.assertEqual(_classify_planet(1.0, 5.0, snow)[0], "rocky")
        # ice beyond/inside the snow line is unchanged.
        self.assertEqual(_classify_planet(17.0, 1.0, snow)[0], "ice")
        self.assertEqual(_classify_planet(17.0, 5.0, snow)[0], "ice")
        # gas beyond the snow line is unchanged.
        self.assertEqual(_classify_planet(100.0, 5.0, snow)[0], "gas")

    def test_no_modifier_when_snow_line_none(self):
        self.assertEqual(_classify_planet(5.0, 50.0, None)[0], "super_earth")

    def test_radius_positive_and_earthlike(self):
        # Earth → ~1 R⊕.
        _, r_earth = _classify_planet(1.0, 1.0)
        self.assertAlmostEqual(r_earth, 1.0, places=3)
        # Jupiter mass → ~11.2 R⊕.
        _, r_jup = _classify_planet(_M_JUPITER_EARTH, 1.0)
        self.assertAlmostEqual(r_jup, 11.2, places=1)
        # All radii strictly positive across the mass range.
        for m in (0.3, 2.0, 17.0, 100.0, 800.0, 5000.0):
            self.assertGreater(_classify_planet(m, 1.0)[1], 0.0)

    def test_radius_monotonic_within_rocky_branch(self):
        r1 = _radius_earth_for_type("rocky", 0.5)
        r2 = _radius_earth_for_type("rocky", 1.0)
        r3 = _radius_earth_for_type("rocky", 1.8)
        self.assertLess(r1, r2)
        self.assertLess(r2, r3)

    def test_giant_radius_nearly_flat(self):
        # Jovian branch is near-constant (degeneracy support): Saturn-mass and a
        # brown dwarf stay within ~Jupiter radius.
        r_gas = _radius_earth_for_type("gas", 95.0)
        r_bd = _radius_earth_for_type("brown_dwarf", _BROWN_DWARF_MIN_EARTH)
        self.assertTrue(8.0 < r_gas < 14.0)
        self.assertTrue(8.0 < r_bd < 13.0)


class TestEquilibriumTemp(unittest.TestCase):
    def test_earth_reference(self):
        # a=1, L=1, albedo=0.3 → Earth's textbook ~255 K equilibrium temp.
        t = _equilibrium_temp(1.0, 1.0, albedo=0.3)
        self.assertAlmostEqual(t, _t_ref_equilibrium(0.3), places=6)
        self.assertTrue(250.0 < t < 260.0)

    def test_zero_albedo_anchor(self):
        t = _equilibrium_temp(1.0, 1.0, albedo=0.0)
        self.assertAlmostEqual(t, 278.5, places=1)

    def test_decreases_with_distance(self):
        near = _equilibrium_temp(1.0, 1.0)
        far = _equilibrium_temp(2.0, 1.0)
        self.assertLess(far, near)
        # inverse-sqrt-AU scaling: T(2 AU) = T(1 AU) / sqrt(2).
        self.assertAlmostEqual(far, near / math.sqrt(2.0), places=6)

    def test_scales_with_luminosity(self):
        # T ∝ L^0.25.
        t1 = _equilibrium_temp(1.0, 1.0)
        t16 = _equilibrium_temp(1.0, 16.0)
        self.assertAlmostEqual(t16, t1 * 2.0, places=6)

    def test_guards_non_positive(self):
        self.assertIsNone(_equilibrium_temp(0.0, 1.0))
        self.assertIsNone(_equilibrium_temp(-1.0, 1.0))
        self.assertIsNone(_equilibrium_temp(1.0, 0.0))
        self.assertIsNone(_equilibrium_temp(1.0, -1.0))

    def test_hz_planet_in_expected_band(self):
        # A planet in the Sun's conservative HZ (~0.95–1.4 AU) lands in the
        # bare-equilibrium band ~200–290 K (greenhouse warms the *surface* above
        # this — that is the M1 surface model, not this M2 equilibrium one).
        for a in (0.95, 1.0, 1.4):
            t = _equilibrium_temp(a, 1.0)
            self.assertTrue(200.0 < t < 290.0)


_TOP_KEYS = {"seed", "mode", "anchor_star", "star", "planets", "warnings", "notes"}
_STAR_KEYS = {
    "name", "spectral_class", "teff", "mass_solar", "radius_solar", "luminosity",
    "hz_inner_au", "hz_outer_au", "hz_opt_inner_au", "hz_opt_outer_au",
    "snow_line_au", "feh", "feh_source", "source", "grounding", "multiplicity",  # R3-V2 F2
}
_PLANET_KEYS = {
    "name", "a_au", "mass_earth", "radius_earth", "ecc", "type", "t_eq_k",
    "in_hz", "hz_class", "source", "atmosphere", "moons",
}
_PLANET_TYPES = {"rocky", "super_earth", "ice", "gas", "super_jovian", "brown_dwarf"}


class TestSyntheticGeneration(unittest.TestCase):
    def test_determinism_sampled(self):
        # Same seed → byte-identical (deep-equal) output, no args.
        self.assertEqual(generate_system(88), generate_system(88))

    def test_determinism_full_args(self):
        a = generate_system(4173, spectral_class="K2V", n_planets=6)
        b = generate_system(4173, spectral_class="K2V", n_planets=6)
        self.assertEqual(a, b)

    def test_determinism_require_habitable(self):
        a = generate_system(7, spectral_class="G2V", require_habitable=True)
        b = generate_system(7, spectral_class="G2V", require_habitable=True)
        self.assertEqual(a, b)
        self.assertNotIn("error", a)

    def test_different_seeds_differ(self):
        self.assertNotEqual(generate_system(1), generate_system(2))

    def test_top_level_shape(self):
        r = generate_system(88, spectral_class="G2V", n_planets=4)
        self.assertEqual(set(r), _TOP_KEYS)
        self.assertEqual(r["mode"], "synthetic")
        self.assertIsNone(r["anchor_star"])
        self.assertEqual(r["seed"], 88)
        self.assertEqual(set(r["star"]), _STAR_KEYS)
        self.assertEqual(r["star"]["source"], "synthetic")
        self.assertEqual(r["star"]["grounding"], "default-extrapolation")
        self.assertIsNone(r["star"]["multiplicity"])
        self.assertIsInstance(r["warnings"], list)
        self.assertIsInstance(r["notes"], list)
        for p in r["planets"]:
            self.assertEqual(set(p), _PLANET_KEYS)
            self.assertEqual(p["source"], "synthetic")
            self.assertIn(p["type"], _PLANET_TYPES)
            self.assertGreater(p["radius_earth"], 0.0)
            self.assertGreater(p["mass_earth"], 0.0)

    def test_n_planets_honoured(self):
        self.assertEqual(len(generate_system(3, spectral_class="G2V", n_planets=7)["planets"]), 7)
        self.assertEqual(len(generate_system(3, spectral_class="G2V", n_planets=0)["planets"]), 0)

    def test_star_props_match_table_and_luminosity(self):
        # 'K2V' matches a table row exactly → no interpolation; teff/M/R are the
        # row values, and luminosity follows compute_star_luminosity.
        r = generate_system(88, spectral_class="K2V", n_planets=1)
        s = r["star"]
        self.assertEqual(s["spectral_class"], "K2V")
        self.assertAlmostEqual(s["teff"], 4800.0, places=1)
        self.assertAlmostEqual(s["mass_solar"], 0.72, places=2)
        self.assertAlmostEqual(s["radius_solar"], 0.78, places=2)
        expected_l = compute_star_luminosity(s["radius_solar"], s["teff"])["luminosity"]
        self.assertAlmostEqual(s["luminosity"], round(expected_l, 6), places=6)

    def test_star_hz_matches_kopparapu(self):
        r = generate_system(88, spectral_class="G2V", n_planets=1)
        s = r["star"]
        hz = {z["key"]: z["au"] for z in compute_habitable_zone(s["teff"], s["luminosity"])}
        self.assertAlmostEqual(s["hz_inner_au"], round(hz["rg"], 5), places=4)
        self.assertAlmostEqual(s["hz_outer_au"], round(hz["mg"], 5), places=4)
        self.assertAlmostEqual(s["hz_opt_inner_au"], round(hz["rv"], 5), places=4)
        self.assertAlmostEqual(s["hz_opt_outer_au"], round(hz["em"], 5), places=4)
        # Ordering: optimistic brackets conservative.
        self.assertLess(s["hz_opt_inner_au"], s["hz_inner_au"])
        self.assertLess(s["hz_outer_au"], s["hz_opt_outer_au"])

    def test_planets_ordered_and_teq_decreasing(self):
        r = generate_system(0, spectral_class="G2V", n_planets=6)
        ps = r["planets"]
        for i in range(1, len(ps)):
            self.assertGreater(ps[i]["a_au"], ps[i - 1]["a_au"])     # SMAs widen outward
            self.assertLess(ps[i]["t_eq_k"], ps[i - 1]["t_eq_k"])    # cooler farther out

    def test_hz_flags_consistent(self):
        r = generate_system(0, spectral_class="G2V", n_planets=8)
        s = r["star"]
        for p in r["planets"]:
            a = p["a_au"]
            if s["hz_inner_au"] <= a <= s["hz_outer_au"]:
                self.assertTrue(p["in_hz"])
                self.assertEqual(p["hz_class"], "conservative")
            elif s["hz_opt_inner_au"] <= a <= s["hz_opt_outer_au"]:
                self.assertTrue(p["in_hz"])
                self.assertEqual(p["hz_class"], "optimistic")
            else:
                self.assertFalse(p["in_hz"])
                self.assertIsNone(p["hz_class"])

    def test_atmosphere_only_on_terrestrial(self):
        r = generate_system(0, spectral_class="G2V", n_planets=8)
        for p in r["planets"]:
            if p["type"] in ("rocky", "super_earth"):
                self.assertIsNotNone(p["atmosphere"])
            else:
                self.assertIsNone(p["atmosphere"])

    def test_moons_within_roche_and_hill(self):
        # Find a giant with moons and verify each moon sits inside the stable
        # annulus: ≤ the ½-Hill limit (exact) and ≥ the densest-case fluid Roche.
        r = generate_system(0, spectral_class="G2V", n_planets=8)
        s = r["star"]
        checked = 0
        for p in r["planets"]:
            if not p["moons"]:
                continue
            hill = compute_hill_sphere(s["mass_solar"], p["mass_earth"], p["a_au"], p["ecc"])
            stable_au = hill["stable_orbit_limit_au"]
            # Densest plausible moon (3.5 g/cc) → smallest fluid Roche → loosest
            # necessary inner bound (the actual draw used a density in [1.2, 3.5]).
            roche_min = compute_roche_limit(p["mass_earth"], 3.5, p["radius_earth"])["fluid_au"]
            pradius_km = p["radius_earth"] * _EARTH_RADIUS_KM
            for m in p["moons"]:
                self.assertTrue(m["between_roche_and_hill"])
                self.assertGreater(m["a_planet_radii"], 1.0)          # outside the planet
                moon_au = m["a_planet_radii"] * pradius_km / _KM_PER_AU
                self.assertLessEqual(moon_au, stable_au + 1e-9)
                self.assertGreaterEqual(moon_au, roche_min - 1e-9)
                checked += 1
        self.assertGreater(checked, 0, "expected at least one giant with moons in this fixture")

    def test_require_habitable_delivers_conservative_rocky(self):
        r = generate_system(7, spectral_class="G2V", require_habitable=True)
        self.assertNotIn("error", r)
        self.assertTrue(any(
            p["type"] in ("rocky", "super_earth") and p["hz_class"] == "conservative"
            for p in r["planets"]))

    def test_sampled_class_format(self):
        sc = generate_system(123)["star"]["spectral_class"]
        # "<letter><integer subtype>V", e.g. "M1V".
        self.assertRegex(sc, r"^[BAFGKM]\d+V$")


class TestGenerateValidation(unittest.TestCase):
    def test_seed_must_be_int(self):
        self.assertIn("error", generate_system("nope"))
        self.assertIn("error", generate_system(1.5))

    def test_bad_spectral_class(self):
        self.assertIn("error", generate_system(1, spectral_class="Z9V"))

    def test_o_class_unsupported(self):
        r = generate_system(1, spectral_class="O5V")
        self.assertIn("error", r)
        self.assertIn("O", r["error"])

    def test_n_planets_range(self):
        self.assertIn("error", generate_system(1, spectral_class="G2V", n_planets=20))
        self.assertIn("error", generate_system(1, spectral_class="G2V", n_planets=-1))

    def test_require_habitable_zero_planets(self):
        self.assertIn("error", generate_system(1, spectral_class="G2V",
                                               n_planets=0, require_habitable=True))


# ── Real-anchor mode (R1-C3) — readers mocked; fully offline ──────────────────

def _simbad(gcns=None):
    return {"main_id": "Test Star", "sp_type": "G2V", "teff": 5778.0, "vmag": 5.0,
            "plx_value": 100.0, "designations": {"HD": "HD 1"}, "gcns": gcns}


def _regions(err=None):
    if err:
        return {"error": err}
    return {"temp": 5778.0, "stellarMass": 1.0, "stellarRadius": 1.0,
            "bcLuminosity": 1.0, "spectral_type": "G2V", "bc_key": "G2"}


def _nasa(planets):
    return {"planets": planets}


def _hwc(rows):
    return {"planet_rows": rows}


def _readers(simbad, regions, nasa, hwc, hypatia=None):
    """Context manager patching the readers in core.generate's namespace. ``hypatia``
    defaults to an error result → the real-anchor [Fe/H] uses the SIMBAD fallback
    (keeps existing tests offline and behaviour-stable)."""
    stack = ExitStack()
    stack.enter_context(mock.patch("core.generate.compute_simbad_lookup", return_value=simbad))
    stack.enter_context(mock.patch("core.generate.compute_star_system_regions_from_simbad",
                                   return_value=regions))
    stack.enter_context(mock.patch("core.generate.compute_planetary_systems_composite",
                                   return_value=nasa))
    stack.enter_context(mock.patch("core.generate.compute_hwc", return_value=hwc))
    stack.enter_context(mock.patch("core.generate.compute_hypatia_data",
                                   return_value=hypatia or {"error": "no hypatia"}))
    return stack


_EARTH_ROW = {"pl_name": "Test b", "pl_orbsmax": 1.0, "pl_bmasse": 1.0,
              "pl_rade": 1.0, "pl_orbeccen": 0.0}
_JUP_ROW = {"pl_name": "Test c", "pl_orbsmax": 5.2, "pl_bmasse": 317.8,
            "pl_rade": 11.0, "pl_orbeccen": 0.05}


class TestRealAnchor(unittest.TestCase):
    def test_determinism(self):
        with _readers(_simbad(), _regions(), _nasa([_EARTH_ROW]), {"error": "no hwc"}):
            a = generate_system(5, anchor_star="Test Star", n_planets=4)
            b = generate_system(5, anchor_star="Test Star", n_planets=4)
        self.assertEqual(a, b)
        self.assertEqual(a["mode"], "real_anchor")
        self.assertEqual(a["anchor_star"], "Test Star")

    def test_shape_and_star_provenance(self):
        with _readers(_simbad(), _regions(), {"error": "x"}, {"error": "y"}):
            r = generate_system(2, anchor_star="Test Star", n_planets=5)
        self.assertEqual(set(r), _TOP_KEYS)
        s = r["star"]
        self.assertEqual(s["source"], "observed")
        self.assertEqual(s["grounding"], "observed")
        self.assertEqual(s["spectral_class"], "G2V")
        self.assertIsInstance(s["multiplicity"], dict)
        self.assertAlmostEqual(s["mass_solar"], 1.0)

    def test_observed_and_synthetic_flags(self):
        with _readers(_simbad(), _regions(), _nasa([_EARTH_ROW, _JUP_ROW]), {"error": "x"}):
            r = generate_system(11, anchor_star="Test Star", n_planets=6)
        obs = [p for p in r["planets"] if p["source"] == "observed"]
        syn = [p for p in r["planets"] if p["source"] == "synthetic"]
        self.assertEqual(len(obs), 2)
        self.assertGreater(len(syn), 0)
        # Observed giants carry no fabricated moons.
        for p in obs:
            self.assertEqual(p["moons"], [])

    def test_synthetic_smas_avoid_observed(self):
        with _readers(_simbad(), _regions(), _nasa([_EARTH_ROW, _JUP_ROW]), {"error": "x"}):
            r = generate_system(11, anchor_star="Test Star", n_planets=8)
        obs_smas = [1.0, 5.2]
        for p in r["planets"]:
            if p["source"] == "synthetic":
                for o in obs_smas:
                    self.assertFalse((1.0 / 1.4) < (p["a_au"] / o) < 1.4,
                                     f"synthetic SMA {p['a_au']} collides with observed {o}")

    def test_no_observed_planets_warns_but_proceeds(self):
        with _readers(_simbad(), _regions(), {"error": "no exo"}, {"error": "no hwc"}):
            r = generate_system(2, anchor_star="Test Star", n_planets=5)
        self.assertTrue(any("No observed planets" in w for w in r["warnings"]))
        self.assertTrue(r["planets"])
        self.assertTrue(all(p["source"] == "synthetic" for p in r["planets"]))

    def test_observed_planet_radius_only_classifies(self):
        row = {"pl_name": "RadOnly", "pl_orbsmax": 0.5, "pl_bmasse": None,
               "pl_rade": 1.0, "pl_orbeccen": None}
        with _readers(_simbad(), _regions(), _nasa([row]), {"error": "x"}):
            r = generate_system(1, anchor_star="Test Star", n_planets=0)
        p = [x for x in r["planets"] if x["source"] == "observed"][0]
        self.assertEqual(p["type"], "rocky")
        self.assertIsNone(p["mass_earth"])          # mass unmeasured → reported None
        self.assertAlmostEqual(p["radius_earth"], 1.0, places=4)

    def test_hwc_dedup_by_sma_and_name(self):
        nasa = _nasa([_EARTH_ROW])  # at 1.0 AU
        hwc = _hwc([
            {"P_NAME": "Test b alt", "P_SEMI_MAJOR_AXIS": 1.0, "P_MASS": 1.0,
             "P_RADIUS": 1.0, "P_ECCENTRICITY": 0.0},          # same orbit → deduped
            {"P_NAME": "Test d", "P_SEMI_MAJOR_AXIS": 3.0, "P_MASS": 5.0,
             "P_RADIUS": 2.0, "P_ECCENTRICITY": 0.0},          # distinct → kept
        ])
        with _readers(_simbad(), _regions(), nasa, hwc):
            r = generate_system(1, anchor_star="Test Star", n_planets=0)
        obs = [p for p in r["planets"] if p["source"] == "observed"]
        self.assertEqual(len(obs), 2)                 # 1 NASA + 1 unique HWC

    def test_multiplicity_warns_and_caps_synthetic(self):
        with _readers(_simbad(gcns={"n_components": 2}), _regions(),
                      _nasa([_EARTH_ROW, _JUP_ROW]), {"error": "x"}):
            r = generate_system(3, anchor_star="Test Star", n_planets=8)
        mult = r["star"]["multiplicity"]
        self.assertTrue(mult["is_multiple"])
        self.assertEqual(mult["n_components"], 2)
        self.assertTrue(any("multiple" in w.lower() for w in r["warnings"]))
        # No synthetic body beyond min(outermost observed 5.2, 2 × HZ outer).
        cap = min(5.2, 2.0 * r["star"]["hz_outer_au"])
        for p in r["planets"]:
            if p["source"] == "synthetic":
                self.assertLessEqual(p["a_au"], cap + 1e-9)
        # Observed planet beyond the cap is retained (never capped).
        self.assertTrue(any(p["source"] == "observed" and p["a_au"] > cap
                            for p in r["planets"]))

    def test_require_habitable_satisfied_by_observed(self):
        with _readers(_simbad(), _regions(), _nasa([_EARTH_ROW]), {"error": "x"}):
            r = generate_system(9, anchor_star="Test Star", n_planets=0,
                                require_habitable=True)
        self.assertNotIn("error", r)
        self.assertTrue(any(p["source"] == "observed" and p["in_hz"]
                            and p["hz_class"] == "conservative" for p in r["planets"]))

    def test_simbad_error_propagates(self):
        with mock.patch("core.generate.compute_simbad_lookup",
                        return_value={"error": "No results found for 'zzz'"}):
            r = generate_system(1, anchor_star="zzz")
        self.assertIn("error", r)

    def test_regions_error_propagates(self):
        # e.g. a white-dwarf primary → regions can't derive HZ.
        with _readers(_simbad(), _regions(err="not a main-sequence class"),
                      {"error": "x"}, {"error": "y"}):
            r = generate_system(1, anchor_star="WD Star")
        self.assertIn("error", r)


# ── R3-C4 · research_policy wiring through generation ─────────────────────────
import os
import shutil
import tempfile

from core.research_priors import compute_research_priors_ingest

_FIX_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
_IDENTITY_FIX = os.path.join(_FIX_DIR, "research_priors_identity.json")
_SAMPLE_FIX = os.path.join(_FIX_DIR, "research_priors_sample.json")


class TestResearchPolicyWiring(unittest.TestCase):
    """The research_policy seam through core/generate.py (offline)."""

    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache, ignore_errors=True)

    def _ingest(self, fixture):
        res = compute_research_priors_ingest(path=fixture, cache_dir=self.cache)
        self.assertNotIn("error", res)

    def _strict(self, **kw):
        # Point the provider's default cache at our tmp cache, then run strict.
        with mock.patch("core.priors._DEFAULT_CACHE_DIR", self.cache):
            return generate_system(research_policy="strict", **kw)

    # ── permissive is the unchanged R1 path ──
    def test_default_equals_explicit_permissive(self):
        a = generate_system(7, spectral_class="K2V", n_planets=5)
        b = generate_system(7, spectral_class="K2V", n_planets=5,
                            research_policy="permissive")
        self.assertEqual(a, b)
        self.assertEqual(a["star"]["grounding"], "default-extrapolation")
        self.assertIn("DefaultPriors (grounding=default-extrapolation)", a["notes"][0])

    def test_unknown_policy_errors(self):
        r = generate_system(7, spectral_class="K2V", n_planets=3,
                            research_policy="bogus")
        self.assertIn("error", r)
        self.assertIn("research_policy", r["error"])

    # ── strict with the IDENTITY dataset == permissive except the badge ──
    def test_strict_identity_matches_permissive_except_grounding(self):
        self._ingest(_IDENTITY_FIX)
        perm = generate_system(42, spectral_class="G2V", n_planets=6)
        strict = self._strict(seed=42, spectral_class="G2V", n_planets=6)
        self.assertNotIn("error", strict)
        # sampling identical (identity values == DefaultPriors) → planets byte-equal
        self.assertEqual(strict["planets"], perm["planets"])
        # star equal except the grounding tag
        s_star = dict(strict["star"]); p_star = dict(perm["star"])
        self.assertEqual(s_star.pop("grounding"), "research-calibrated")
        self.assertEqual(p_star.pop("grounding"), "default-extrapolation")
        self.assertEqual(s_star, p_star)
        self.assertIn("ResearchPriors (grounding=research-calibrated, "
                      "dataset identity-2026-06-24)", strict["notes"][0])

    # ── strict with the PERTURBED sample: deterministic AND different ──
    def test_strict_sample_deterministic_and_different(self):
        self._ingest(_SAMPLE_FIX)
        r1 = self._strict(seed=99, spectral_class="K2V", n_planets=5)
        r2 = self._strict(seed=99, spectral_class="K2V", n_planets=5)
        self.assertEqual(r1, r2)                                   # determinism
        perm = generate_system(99, spectral_class="K2V", n_planets=5)
        self.assertNotEqual(r1["planets"], perm["planets"])        # sampling re-drawn
        self.assertEqual(r1["star"]["grounding"], "research-calibrated")
        self.assertIn("sample-2026-06-24", r1["notes"][0])

    # ── strict with no ingested dataset → curated error ──
    def test_strict_without_cache_errors(self):
        r = self._strict(seed=1, spectral_class="K2V", n_planets=3)  # empty cache
        self.assertIn("error", r)
        self.assertIn("strict", r["error"])

    # ── real-anchor: star stays observed; only the synthetic-infill note re-tags ──
    def test_real_anchor_note_retag_strict(self):
        self._ingest(_IDENTITY_FIX)
        with _readers(_simbad(), _regions(), _nasa([_EARTH_ROW]), {"error": "x"}):
            with mock.patch("core.priors._DEFAULT_CACHE_DIR", self.cache):
                r = generate_system(5, anchor_star="Tau Ceti",
                                    research_policy="strict", n_planets=2)
        self.assertNotIn("error", r)
        self.assertEqual(r["star"]["grounding"], "observed")
        self.assertIn("ResearchPriors (grounding=research-calibrated", " ".join(r["notes"]))


_V2_FIX = os.path.join(_FIX_DIR, "research_priors_v2_sample.json")


class TestMassModelDraw(unittest.TestCase):
    """Phase R3-V2 B1: the gated mass_model isolation-mass draw.

    The block-gated v2 path replaces the flat mass_by_zone draw with a physics
    draw (M_iso + a giant switch); with no block, the v1 path is byte-identical
    (proven by TestResearchPolicyWiring's identity test, which stays green).
    """

    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache, ignore_errors=True)

    def _strict(self, obj, **kw):
        import json
        p = os.path.join(self.cache, "src.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        res = compute_research_priors_ingest(path=p, cache_dir=self.cache)
        self.assertNotIn("error", res)
        with mock.patch("core.priors._DEFAULT_CACHE_DIR", self.cache):
            return generate_system(research_policy="strict", **kw)

    def _load_v2(self, drop_occ=False):
        import json
        with open(_V2_FIX, encoding="utf-8") as fh:
            o = json.load(fh)
        if drop_occ:
            # Grid-giant mode: drop occurrence_by_metallicity (roll always-True) AND
            # both decoupled populations (else giants come from those paths, not the
            # grid) → giants form on the pure B1 in-grid physics gate.
            # inner_giant_population must go with occurrence_by_metallicity regardless:
            # its occurrence_ref points into that block, so the contract rejects one
            # without the other.
            o.pop("occurrence_by_metallicity", None)
            o.pop("cold_giant_population", None)
            o.pop("inner_giant_population", None)
        return o

    def test_deterministic(self):
        v2 = self._load_v2()
        r1 = self._strict(v2, seed=42, spectral_class="G2V", n_planets=8)
        r2 = self._strict(v2, seed=42, spectral_class="G2V", n_planets=8)
        self.assertNotIn("error", r1)
        self.assertEqual(r1, r2)

    def test_mass_model_changes_masses_vs_stripped(self):
        # Same dataset with vs without mass_model → the v2 path is actually taken.
        import copy
        v2 = self._load_v2()
        stripped = copy.deepcopy(v2); stripped.pop("mass_model")
        r_full = self._strict(v2, seed=42, spectral_class="G2V", n_planets=8)
        r_strip = self._strict(stripped, seed=42, spectral_class="G2V", n_planets=8)
        self.assertNotEqual([p["mass_earth"] for p in r_full["planets"]],
                            [p["mass_earth"] for p in r_strip["planets"]])

    def test_no_giant_interior_to_snow_line(self):
        # Giants form only beyond the snow line (physics gate).
        v2 = self._load_v2(drop_occ=True)
        r = self._strict(v2, seed=42, spectral_class="G2V", n_planets=10)
        snow = r["star"]["snow_line_au"]
        giants_inside = [p for p in r["planets"]
                         if p["type"] in ("gas", "super_jovian", "brown_dwarf")
                         and p["a_au"] < snow]
        self.assertEqual(giants_inside, [])

    def test_giant_forms_beyond_snow_line(self):
        # A wide system (many planets around a warmer star) must land >=1 giant
        # beyond the snow line. Drop occ so the per-system roll is always-True (pure
        # physics), else the growth-race roll makes a single-seed giant probabilistic.
        v2 = self._load_v2(drop_occ=True)
        r = self._strict(v2, seed=7, spectral_class="F5V", n_planets=14)
        snow = r["star"]["snow_line_au"]
        giants = [p for p in r["planets"]
                  if p["type"] in ("gas", "super_jovian", "brown_dwarf")]
        self.assertTrue(giants, "expected at least one giant in a wide system")
        self.assertTrue(all(p["a_au"] >= snow for p in giants))

    def test_giant_ceiling_admits_super_jupiters_below_13mjup(self):
        # R3-V2 B6/L1: the giant ceiling is ~13 M_J (4131 M⊕), not the old 600 M⊕,
        # so super-Jupiters (2-13 M_J = 636-4131 M⊕) can form; none exceed the boundary.
        _M_JUP = 317.8
        masses = []
        for s in range(40):
            for p in self._strict(self._load_v2(drop_occ=True), seed=s,
                                  spectral_class="F5V", n_planets=14)["planets"]:
                if p["type"] in ("gas", "super_jovian", "brown_dwarf"):
                    masses.append(p["mass_earth"])
        self.assertTrue(masses)
        self.assertTrue(any(m >= 2 * _M_JUP for m in masses),
                        "no super-Jupiter formed — the giant ceiling is too low")
        self.assertTrue(all(m <= 13 * _M_JUP + 1 for m in masses),
                        "a giant exceeded the ~13 M_J planet/BD boundary")


class TestMetallicityConditioning(unittest.TestCase):
    """Phase R3-V2 B2: occurrence_by_metallicity + feh_dist conditioning (gated)."""

    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache, ignore_errors=True)

    def _gen(self, feh=None, drop_feh_dist=False, drop_corr=False, **kw):
        """Strict-generate with the v2 fixture, optionally forcing a (near-)fixed
        host [Fe/H] via a tight feh_dist, dropping feh_dist, or dropping the
        intra_system_correlation block (to isolate F2 from F3's mass chain)."""
        import json, copy
        with open(_V2_FIX, encoding="utf-8") as fh:
            o = copy.deepcopy(json.load(fh))
        if drop_corr:
            o.pop("intra_system_correlation", None)
        if drop_feh_dist:
            o.pop("feh_dist", None)
        elif feh is not None:
            o["feh_dist"] = {"mean": feh, "sigma": 0.001, "min": -2.0, "max": 1.0}
        p = os.path.join(self.cache, "s.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(o, fh)
        res = compute_research_priors_ingest(path=p, cache_dir=self.cache)
        self.assertNotIn("error", res)
        with mock.patch("core.priors._DEFAULT_CACHE_DIR", self.cache):
            return generate_system(research_policy="strict", **kw)

    def _giants(self, feh, seeds=25):
        n = 0
        for s in range(seeds):
            r = self._gen(feh=feh, seed=s, spectral_class="F5V", n_planets=14)
            n += sum(1 for p in r["planets"]
                     if p["type"] in ("gas", "super_jovian", "brown_dwarf"))
        return n

    def test_giant_occurrence_rises_with_metallicity(self):
        self.assertGreater(self._giants(0.4), self._giants(-0.8))

    def test_superearth_floor_suppresses_below_floor(self):
        # Isolate the F2 floor from F3's mass chain (which suppresses super-Earths
        # generally) by dropping intra_system_correlation.
        def se(feh):
            return sum(sum(1 for p in self._gen(feh=feh, drop_corr=True, seed=s,
                                                spectral_class="K2V", n_planets=10)["planets"]
                           if p["type"] == "super_earth") for s in range(25))
        self.assertLess(se(-0.8), se(0.3))   # below the -0.5 floor → suppressed

    def test_count_rises_with_metallicity(self):
        def mean_count(feh):
            return sum(len(self._gen(feh=feh, seed=s, spectral_class="M2V")["planets"])
                       for s in range(30)) / 30
        self.assertGreater(mean_count(0.4), mean_count(-0.8))

    def test_feh_recorded_and_deterministic(self):
        r1 = self._gen(feh=0.25, seed=5, spectral_class="G2V", n_planets=6)
        r2 = self._gen(feh=0.25, seed=5, spectral_class="G2V", n_planets=6)
        self.assertEqual(r1, r2)
        self.assertAlmostEqual(r1["star"]["feh"], 0.25, places=2)

    def test_feh_none_without_feh_dist(self):
        # occurrence_by_metallicity present but no feh_dist → synthetic feh None,
        # conditioning inert.
        r = self._gen(drop_feh_dist=True, seed=5, spectral_class="G2V", n_planets=4)
        self.assertIsNone(r["star"]["feh"])

    def test_real_anchor_prefers_hypatia(self):
        # Hypatia-preferred: even when SIMBAD has [Fe/H], Hypatia's value wins + is tagged.
        sim = dict(_simbad()); sim["fe_h"] = -0.33
        hyp = {"abundances": [{"element": "Fe", "mean": 0.12},
                              {"element": "Fe_II", "mean": 9.9}]}   # ionized excluded
        with _readers(sim, _regions(), _nasa([_EARTH_ROW]), {"error": "x"}, hypatia=hyp):
            r = self._gen(seed=5, anchor_star="Test Star", n_planets=2)
        self.assertAlmostEqual(r["star"]["feh"], 0.12, places=2)
        self.assertEqual(r["star"]["feh_source"], "hypatia")

    def test_real_anchor_falls_back_to_simbad(self):
        # No Hypatia value → SIMBAD mesfe_h.fe_h fallback, tagged "simbad".
        sim = dict(_simbad()); sim["fe_h"] = -0.33
        with _readers(sim, _regions(), _nasa([_EARTH_ROW]), {"error": "x"}):  # hypatia error
            r = self._gen(seed=5, anchor_star="Test Star", n_planets=2)
        self.assertAlmostEqual(r["star"]["feh"], -0.33, places=2)
        self.assertEqual(r["star"]["feh_source"], "simbad")

    def test_real_anchor_no_feh_source_none(self):
        # Neither source has [Fe/H] → feh None, feh_source None (F2 inert).
        with _readers(_simbad(), _regions(), _nasa([_EARTH_ROW]), {"error": "x"}):
            r = self._gen(seed=5, anchor_star="Test Star", n_planets=2)
        self.assertIsNone(r["star"]["feh"])
        self.assertIsNone(r["star"]["feh_source"])

    def test_synthetic_feh_source_tag(self):
        r = self._gen(feh=0.2, seed=5, spectral_class="G2V", n_planets=3)
        self.assertEqual(r["star"]["feh_source"], "feh_dist")
        r2 = self._gen(drop_feh_dist=True, seed=5, spectral_class="G2V", n_planets=3)
        self.assertIsNone(r2["star"]["feh_source"])

    def test_giant_fraction_at_clamps_to_grid(self):
        from core.generate import _giant_fraction_at
        occ = {"feh_grid": [-0.5, 0.0, 0.5], "giant_fraction": [0.003, 0.03, 0.30]}
        self.assertEqual(_giant_fraction_at(occ, -1.0), 0.003)   # below → hold endpoint
        self.assertEqual(_giant_fraction_at(occ, 1.0), 0.30)     # above → hold endpoint
        self.assertAlmostEqual(_giant_fraction_at(occ, 0.25), (0.03 + 0.30) / 2)


class TestIntraSystemCorrelation(unittest.TestCase):
    """Phase R3-V2 B3: intra_system_correlation (peas-in-a-pod joint draws)."""

    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache, ignore_errors=True)

    def _gen(self, drop_corr=False, **kw):
        import json, copy
        with open(_V2_FIX, encoding="utf-8") as fh:
            o = copy.deepcopy(json.load(fh))
        if drop_corr:
            o.pop("intra_system_correlation", None)
        p = os.path.join(self.cache, "s.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(o, fh)
        self.assertNotIn("error", compute_research_priors_ingest(path=p, cache_dir=self.cache))
        with mock.patch("core.priors._DEFAULT_CACHE_DIR", self.cache):
            return generate_system(research_policy="strict", **kw)

    def test_deterministic_and_changes_output(self):
        r1 = self._gen(seed=11, spectral_class="G2V", n_planets=8)
        r2 = self._gen(seed=11, spectral_class="G2V", n_planets=8)
        self.assertEqual(r1, r2)
        stripped = self._gen(drop_corr=True, seed=11, spectral_class="G2V", n_planets=8)
        self.assertNotEqual(r1["planets"], stripped["planets"])

    def test_period_ratio_floor_respected(self):
        prd_min = 1.2
        for s in range(20):
            ps = self._gen(seed=s, spectral_class="K2V", n_planets=8)["planets"]
            for i in range(1, len(ps)):
                period_ratio = (ps[i]["a_au"] / ps[i - 1]["a_au"]) ** 1.5
                self.assertGreaterEqual(period_ratio, prd_min - 1e-6)

    def test_adjacent_masses_more_similar_than_independent(self):
        import math, statistics

        def dispersion(drop):
            d = []
            for s in range(40):
                ps = self._gen(drop_corr=drop, seed=s, spectral_class="K2V",
                               n_planets=8)["planets"]
                for i in range(1, len(ps)):
                    m1, m2 = ps[i - 1]["mass_earth"], ps[i]["mass_earth"]
                    if m1 and m2 and m1 > 0 and m2 > 0:
                        d.append(abs(math.log(m2 / m1)))
            return statistics.median(d)

        self.assertLess(dispersion(False), dispersion(True))   # correlated < independent

    def test_ordering_biased_outer_larger(self):
        outer_larger = pairs = 0
        for s in range(40):
            ps = self._gen(seed=s, spectral_class="K2V", n_planets=8)["planets"]
            for i in range(1, len(ps)):
                a, b = ps[i - 1], ps[i]
                if (a["type"] not in _PLANET_TYPES - {"rocky", "super_earth", "ice"}
                        and b["type"] in ("rocky", "super_earth", "ice")
                        and a["type"] in ("rocky", "super_earth", "ice")):
                    pairs += 1
                    outer_larger += b["mass_earth"] > a["mass_earth"]
        self.assertGreater(outer_larger / pairs, 0.55)   # biased above 50/50

    def test_no_gas_giant_inside_snow_line_preserved(self):
        # Scoped to GRID-GROWN giants. The v2.3 inner_giant_population places giants
        # interior to the snow line by design (a decoupled, tagged sub-population that
        # bypasses the B1 gate); those carry giant_zone and are excluded here. The gate
        # itself is unchanged — that is what this test still guards.
        for s in range(20):
            r = self._gen(seed=s, spectral_class="F5V", n_planets=14)
            snow = r["star"]["snow_line_au"]
            inside = [p for p in r["planets"]
                      if p["type"] in ("gas", "super_jovian", "brown_dwarf")
                      and p["a_au"] < snow and not p.get("giant_zone")]
            self.assertEqual(inside, [])

    def test_spacing_ratio_draw_uses_period_ratio(self):
        import random
        from core.generate import _spacing_ratio_draw
        from core.priors import ResearchPriors, DefaultPriors
        import json
        with open(_V2_FIX, encoding="utf-8") as fh:
            pr = ResearchPriors.from_contract(json.load(fh))
        # with correlation → SMA ratio = period_ratio^(2/3), floor at 1.2^(2/3).
        for seed in range(50):
            self.assertGreaterEqual(_spacing_ratio_draw(random.Random(seed), pr),
                                    1.2 ** (2 / 3) - 1e-9)
        # DefaultPriors (no block) → the flat spacing band.
        d = DefaultPriors()
        lo, hi = d.spacing_ratio
        for seed in range(20):
            v = _spacing_ratio_draw(random.Random(seed), d)
            self.assertTrue(lo <= v <= hi)


class TestL2DiskMassAndOccurrence(unittest.TestCase):
    """R3-V2 L2 (v2.1): disk-mass lever + saturating growth-race giant occurrence."""

    _DMD = {"dist": "lognormal", "log10_mean": 0.4, "log10_sigma": 0.25,
            "min": 1.0, "max": 5.0}

    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache, ignore_errors=True)

    def _gen(self, feh=None, disk=False, seed=0, sc="G2V", n=None):
        import json, copy
        with open(_V2_FIX, encoding="utf-8") as fh:
            o = copy.deepcopy(json.load(fh))
        if feh is not None:
            o["feh_dist"] = {"mean": feh, "sigma": 0.001, "min": -2.0, "max": 1.0}
        if disk:
            o["mass_model"]["disk"]["disk_mass_dist"] = dict(self._DMD)
        p = os.path.join(self.cache, "s.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(o, fh)
        self.assertNotIn("error", compute_research_priors_ingest(path=p, cache_dir=self.cache))
        with mock.patch("core.priors._DEFAULT_CACHE_DIR", self.cache):
            return generate_system(seed, spectral_class=sc, n_planets=n,
                                   research_policy="strict")

    def _small_median(self, disk):
        import statistics
        m = [p["mass_earth"] for s in range(80)
             for p in self._gen(feh=0.0, disk=disk, seed=s)["planets"]
             if p["type"] in ("rocky", "super_earth")]
        return statistics.median(m)

    def test_disk_mass_lever_raises_small_planet_mass(self):
        # The per-system disk-mass multiplier (median ~2.5x MMSN) lifts Sigma_solid
        # -> M_iso -> heavier small planets than the scalar-fallback (1.0 MMSN).
        self.assertGreater(self._small_median(disk=True), self._small_median(disk=False))

    def test_disk_mass_lever_deterministic(self):
        r1 = self._gen(feh=0.1, disk=True, seed=5, n=6)
        r2 = self._gen(feh=0.1, disk=True, seed=5, n=6)
        self.assertEqual(r1, r2)

    def test_saturating_occurrence_monotonic(self):
        # Giant occurrence rises with [Fe/H] under the growth-race roll (wide systems).
        def occ(feh):
            return sum(any(p["type"] in ("gas", "super_jovian", "brown_dwarf")
                           for p in self._gen(feh=feh, disk=True, seed=s,
                                              sc="F5V", n=14)["planets"])
                       for s in range(60))
        self.assertGreater(occ(0.5), occ(-0.5))

    def test_occ_eff_curve_hits_anchors(self):
        # The saturating curve occ = C*x/(K+x) matches Packet 3.5's 10/25/1.4% anchors.
        from core.generate import _occ_eff
        self.assertAlmostEqual(_occ_eff(0.0), 0.10, places=2)
        self.assertAlmostEqual(_occ_eff(0.5), 0.25, places=2)
        self.assertAlmostEqual(_occ_eff(-0.5), 0.014, places=3)


class TestDecoupledColdGiants(unittest.TestCase):
    """R3-V2 v2.2 (L2): the decoupled cold-giant population — placed from the debiased
    occurrence curve, independent of the detection-biased inner n_planet_dist grid."""

    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache, ignore_errors=True)

    def _gen(self, feh, seed, drop_cgp=False, sc="G2V", n=None):
        import json, copy
        with open(_V2_FIX, encoding="utf-8") as fh:
            o = copy.deepcopy(json.load(fh))
        o["feh_dist"] = {"mean": feh, "sigma": 0.001, "min": -2.0, "max": 1.0}
        if drop_cgp:
            o.pop("cold_giant_population", None)
        p = os.path.join(self.cache, "s.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(o, fh)
        self.assertNotIn("error", compute_research_priors_ingest(path=p, cache_dir=self.cache))
        with mock.patch("core.priors._DEFAULT_CACHE_DIR", self.cache):
            return generate_system(seed, spectral_class=sc, n_planets=n,
                                   research_policy="strict")

    def _giants(self, r):
        # COLD giants only. The v2.3 inner population is a separate roll against a
        # different (FV05 close-in, ~3%-solar) occurrence number, so counting it here
        # would inflate this class's ~10%-solar cold-giant occurrence targets.
        return [p for p in r["planets"]
                if p["type"] in ("gas", "super_jovian", "brown_dwarf")
                and not p.get("giant_zone")]

    def test_occurrence_tracks_curve_at_solar(self):
        # Realized per-star cold-giant occurrence ~ occ_eff(0) = 10% (placement no
        # longer caps it, since giants are decoupled from the inner grid).
        N = 300
        occ = sum(bool(self._giants(self._gen(0.0, s))) for s in range(N)) / N
        self.assertGreater(occ, 0.05)     # far above the ~0.5% placement-capped grid value
        self.assertLess(occ, 0.16)        # near the 10% curve target

    def test_occurrence_rises_with_metallicity(self):
        def occ(feh):
            return sum(bool(self._giants(self._gen(feh, s))) for s in range(120))
        self.assertGreater(occ(0.5), occ(-0.5))

    def test_cold_giants_only_beyond_snow_line(self):
        for s in range(60):
            r = self._gen(0.3, s)
            snow = r["star"]["snow_line_au"]
            self.assertTrue(all(p["a_au"] >= snow for p in self._giants(r)))

    def test_decoupled_lifts_occurrence_vs_grid(self):
        # With the block, occurrence is much higher than the grid-only (placement-capped)
        # path — the whole point of the bias correction.
        def occ(drop):
            return sum(bool(self._giants(self._gen(0.0, s, drop_cgp=drop)))
                       for s in range(200))
        self.assertGreater(occ(False), occ(True))

    def test_multiplicity_conditional_count(self):
        # Giant-forming systems carry ~1-2 giants on average (Bryan/Rosenthal ~1.47).
        counts = [len(self._giants(self._gen(0.3, s))) for s in range(200)]
        counts = [c for c in counts if c]     # conditional on >=1
        self.assertTrue(counts)
        self.assertLess(sum(counts) / len(counts), 2.2)


class TestDecoupledInnerGiants(unittest.TestCase):
    """R3-V2 v2.3: the decoupled close-in giant population (warm + hot Jupiters interior
    to the snow line), with in-situ vs migrated formation_channel tags. Mirrors the cold
    block, but rolls against the LITERAL FV05 giant_fraction in its native close-in
    domain — a separate roll over a disjoint SMA zone (no double-count)."""

    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache, ignore_errors=True)

    def _gen(self, feh, seed, drop_igp=False, sc="G2V", n=None):
        import json, copy
        with open(_V2_FIX, encoding="utf-8") as fh:
            o = copy.deepcopy(json.load(fh))
        o["feh_dist"] = {"mean": feh, "sigma": 0.001, "min": -2.0, "max": 1.0}
        if drop_igp:
            o.pop("inner_giant_population", None)
        p = os.path.join(self.cache, "s.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(o, fh)
        self.assertNotIn("error", compute_research_priors_ingest(path=p, cache_dir=self.cache))
        with mock.patch("core.priors._DEFAULT_CACHE_DIR", self.cache):
            return generate_system(seed, spectral_class=sc, n_planets=n,
                                   research_policy="strict")

    def _inner(self, r):
        return [p for p in r["planets"] if p.get("giant_zone")]

    def _sweep(self, feh=0.3, n=250):
        out = []
        for s in range(n):
            out.extend(self._inner(self._gen(feh, s)))
        return out

    def test_gated_off_without_the_block(self):
        for s in range(40):
            self.assertEqual(self._inner(self._gen(0.3, s, drop_igp=True)), [])

    def test_inner_giants_are_interior_to_snow_line(self):
        for s in range(120):
            r = self._gen(0.3, s)
            snow = r["star"]["snow_line_au"]
            for p in self._inner(r):
                self.assertLessEqual(p["a_au"], snow + 1e-9)
                self.assertGreaterEqual(p["a_au"], 0.02 - 1e-9)

    def test_mass_within_block_range(self):
        _M_JUP = 317.8
        giants = self._sweep()
        self.assertTrue(giants)
        for p in giants:
            self.assertGreaterEqual(p["mass_earth"], 0.3 * _M_JUP - 1e-6)
            self.assertLessEqual(p["mass_earth"], 13.0 * _M_JUP + 1e-6)

    def test_every_inner_giant_carries_a_channel_tag(self):
        giants = self._sweep()
        self.assertTrue(giants)
        self.assertTrue(all(p.get("formation_channel") for p in giants))

    def test_eccentricity_and_channel_agree_in_warm_zone(self):
        """Gotcha 3: a scattering-tagged giant at e~0, or a circular-tagged one at
        e~0.6, is wrong. In the warm zone the tag and e must be on the same side."""
        excited = ("scattering", "high_e")
        for p in self._sweep():
            if p["giant_zone"] != "warm":
                continue
            is_excited = any(m in p["formation_channel"].lower() for m in excited)
            if is_excited:
                self.assertGreaterEqual(p["ecc"], 0.1)
            else:
                self.assertLess(p["ecc"], 0.1)

    def test_hot_zone_is_tidally_circularized(self):
        hots = [p for p in self._sweep() if p["giant_zone"] == "hot"]
        self.assertTrue(hots)
        self.assertTrue(all(p["ecc"] < 0.2 for p in hots))

    def test_hot_zone_uses_full_channel_mix(self):
        """The hot mix is 80% migrated / 20% in-situ. Eccentricity carries no channel
        information there (tides erase it), so the draw must NOT be e-gated — that bug
        handed every hot Jupiter to the 20% in-situ channel."""
        hots = [p for p in self._sweep(n=400) if p["giant_zone"] == "hot"]
        self.assertTrue(hots)
        migrated = sum("migrated" in p["formation_channel"] for p in hots)
        self.assertGreater(migrated, 0.5 * len(hots))

    def test_occurrence_rises_with_metallicity_and_holds_endpoints(self):
        from core.generate import _interp_giant_fraction
        occ = {"feh_grid": [-0.5, -0.25, 0.0, 0.25, 0.5],
               "giant_fraction": [0.003, 0.0095, 0.03, 0.0949, 0.30]}
        self.assertAlmostEqual(_interp_giant_fraction(occ, 0.0), 0.03, places=4)
        # Endpoints HELD — no extrapolation past the fitted +-0.5 domain.
        self.assertAlmostEqual(_interp_giant_fraction(occ, -3.0), 0.003, places=4)
        self.assertAlmostEqual(_interp_giant_fraction(occ, 3.0), 0.30, places=4)
        self.assertGreater(len(self._sweep(feh=0.5, n=120)),
                           len(self._sweep(feh=-0.5, n=120)))

    def test_grid_giant_switch_is_not_relaxed(self):
        """Gotcha 1: the B1 'giants form beyond the snow line' gate stays true for the
        GROWN population. Any giant interior to the snow line must be a tagged member of
        the decoupled sub-population, never a grid-grown one."""
        for s in range(120):
            r = self._gen(0.3, s, sc="F5V", n=12)
            snow = r["star"]["snow_line_au"]
            for p in r["planets"]:
                if (p["type"] in ("gas", "super_jovian", "brown_dwarf")
                        and p["a_au"] < snow):
                    self.assertTrue(p.get("giant_zone"),
                                    f"untagged giant inside the snow line: {p['name']}")


class TestV2ProvenanceNotes(unittest.TestCase):
    """Phase R3-V2 B5: notes name the active v2 sampling blocks + host [Fe/H]."""

    def setUp(self):
        self.cache = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.cache, ignore_errors=True)

    def _strict(self, fixture, **kw):
        self.assertNotIn("error", compute_research_priors_ingest(path=fixture, cache_dir=self.cache))
        with mock.patch("core.priors._DEFAULT_CACHE_DIR", self.cache):
            return generate_system(research_policy="strict", **kw)

    def test_v2_note_names_blocks_and_feh(self):
        r = self._strict(_V2_FIX, seed=42, spectral_class="G2V", n_planets=6)
        note = next((n for n in r["notes"] if n.startswith("v2 physics in effect")), None)
        self.assertIsNotNone(note)
        for b in ("mass_model", "occurrence_by_metallicity", "intra_system_correlation"):
            self.assertIn(b, note)
        self.assertIn("[Fe/H]", note)

    def test_permissive_has_no_v2_note(self):
        r = generate_system(42, spectral_class="G2V", n_planets=6)
        self.assertFalse(any("v2 physics" in n for n in r["notes"]))

    def test_v1_dataset_has_no_v2_note(self):
        # identity fixture carries no v2 blocks → no v2 note under strict.
        r = self._strict(_IDENTITY_FIX, seed=42, spectral_class="G2V", n_planets=6)
        self.assertFalse(any("v2 physics" in n for n in r["notes"]))


if __name__ == "__main__":
    unittest.main()
