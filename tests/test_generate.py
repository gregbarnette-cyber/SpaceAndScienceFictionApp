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
    "snow_line_au", "source", "grounding", "multiplicity",
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


def _readers(simbad, regions, nasa, hwc):
    """Context manager patching all four readers in core.generate's namespace."""
    stack = ExitStack()
    stack.enter_context(mock.patch("core.generate.compute_simbad_lookup", return_value=simbad))
    stack.enter_context(mock.patch("core.generate.compute_star_system_regions_from_simbad",
                                   return_value=regions))
    stack.enter_context(mock.patch("core.generate.compute_planetary_systems_composite",
                                   return_value=nasa))
    stack.enter_context(mock.patch("core.generate.compute_hwc", return_value=hwc))
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


if __name__ == "__main__":
    unittest.main()
