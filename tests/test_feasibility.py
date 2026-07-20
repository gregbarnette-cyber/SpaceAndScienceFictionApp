# tests/test_feasibility.py — Phase R2 constraint / feasibility engine.
#
# R2-C1 scope (offline, pure): the two new-physics helper groups in
# core.feasibility — G1 packing stability (mutual_hill, the Gladman 2√3 floor +
# Chambers Δ≥10 long-term threshold) and G2 resonance / co-orbital diagnostics
# (period_ratio, nearest_mmr, in_mmr, the Gascheau/Routh co-orbital criterion).
# Anchored to known Solar-System / textbook cases. Later checkpoints (C2 evaluator,
# C3 alternatives+origin, C4 nbody, C5 multi-star) append here.

import math
import unittest
from contextlib import ExitStack
from unittest import mock

from core.feasibility import (
    mutual_hill, period_ratio, nearest_mmr, in_mmr, gascheau_coorbital_stable,
    _DELTA_HILL_CRIT, _DELTA_LONG_TERM, _GASCHEAU_CRIT_MU,
    evaluate_feasibility, validate_constraints, _derived_from_star, _resolve_ref,
    _rule_planet_at_location, _rule_trojan, _rule_moon, _rule_resonance,
    _origin_hypotheses, _alternatives, _resonant_au, _RULE_REGISTRY,
    _rule_habitable_world, _rule_alt_solvent_world, _rule_architecture,
    _nbody_confirm, _binary_gate,
)
from core.generate import generate_system


class TestMutualHillPacking(unittest.TestCase):
    """G1 — mutual Hill radius + Gladman/Chambers separation Δ."""

    def test_thresholds(self):
        self.assertAlmostEqual(_DELTA_HILL_CRIT, 2.0 * math.sqrt(3.0), places=6)
        self.assertEqual(_DELTA_LONG_TERM, 10.0)

    def test_terrestrial_pairs_well_separated(self):
        # Earth–Venus and Earth–Mars are tens of mutual Hill radii apart → both
        # comfortably long-term stable (Δ ≫ 10).
        ev = mutual_hill(1.0, 0.815, 1.0, 0.723, 1.0)
        em = mutual_hill(1.0, 0.107, 1.0, 1.524, 1.0)
        self.assertGreater(ev["delta"], 10.0)
        self.assertGreater(em["delta"], 10.0)
        self.assertTrue(ev["hill_stable"] and ev["long_term_stable"])
        self.assertTrue(em["hill_stable"] and em["long_term_stable"])

    def test_jupiter_saturn_in_gray_band(self):
        # Jupiter–Saturn sit only ~8 mutual Hill radii apart: above the 2√3 Hill
        # floor but below the Δ≥10 long-term threshold → the "marginal" band.
        js = mutual_hill(317.8, 95.2, 5.204, 9.583, 1.0)
        self.assertTrue(_DELTA_HILL_CRIT < js["delta"] < _DELTA_LONG_TERM)
        self.assertTrue(js["hill_stable"])
        self.assertFalse(js["long_term_stable"])

    def test_packed_pair_violates_hill_floor(self):
        # Two Earths only 0.02 AU apart → Δ < 2√3 → not even Hill-stable.
        packed = mutual_hill(1.0, 1.0, 1.0, 1.02, 1.0)
        self.assertLess(packed["delta"], _DELTA_HILL_CRIT)
        self.assertFalse(packed["hill_stable"])
        self.assertFalse(packed["long_term_stable"])

    def test_r_hill_positive_and_symmetric(self):
        a = mutual_hill(1.0, 2.0, 1.0, 1.5, 1.0)
        b = mutual_hill(2.0, 1.0, 1.5, 1.0, 1.0)   # order-swapped
        self.assertGreater(a["r_hill_mutual_au"], 0)
        self.assertAlmostEqual(a["delta"], b["delta"], places=10)

    def test_bad_input(self):
        self.assertIn("error", mutual_hill(0, 1, 1, 2, 1))
        self.assertIn("error", mutual_hill(1, 1, 1, 2, 0))
        self.assertIn("error", mutual_hill(1, 1, -1, 2, 1))


class TestResonance(unittest.TestCase):
    """G2 — period ratio, nearest MMR, MMR membership."""

    def test_period_ratio_mass_independent(self):
        # Same star → stellar mass cancels; ratio is (a_out/a_in)^1.5.
        r1 = period_ratio(1.0, 1.587)
        r2 = period_ratio(1.0, 1.587, star_mass_solar=0.5)
        self.assertAlmostEqual(r1, r2, places=12)
        self.assertAlmostEqual(r1, 2.0, places=2)        # 1.587 AU ↔ a 2:1 with 1.0 AU

    def test_period_ratio_orientation(self):
        self.assertAlmostEqual(period_ratio(1.587, 1.0), period_ratio(1.0, 1.587), places=12)
        self.assertGreaterEqual(period_ratio(1.0, 4.0), 1.0)

    def test_period_ratio_bad_input(self):
        with self.assertRaises(ValueError):
            period_ratio(0, 1.0)

    def test_nearest_mmr_canonical(self):
        self.assertEqual(nearest_mmr(2.0)["ratio_str"], "2:1")
        self.assertEqual(nearest_mmr(1.5)["ratio_str"], "3:2")
        self.assertEqual(nearest_mmr(5.0 / 3.0)["ratio_str"], "5:3")
        # ratio < 1 is inverted before matching.
        self.assertEqual(nearest_mmr(0.5)["ratio_str"], "2:1")

    def test_nearest_mmr_offset_sign(self):
        # Slightly wide of exact 2:1 → small positive signed offset.
        m = nearest_mmr(2.05)
        self.assertEqual(m["ratio_str"], "2:1")
        self.assertGreater(m["offset_frac"], 0)
        self.assertLess(abs(m["offset_frac"]), 0.05)

    def test_nearest_mmr_bad_input(self):
        self.assertIn("error", nearest_mmr(0))

    def test_in_mmr_two_to_one(self):
        # 1.0 & 1.587 AU → within tolerance of 2:1; 1.0 & 2.0 AU → not.
        self.assertTrue(in_mmr(1.0, 1.587, ratio="2:1"))
        self.assertFalse(in_mmr(1.0, 2.0, ratio="2:1"))

    def test_in_mmr_neptune_pluto_3_2(self):
        # Neptune 30.07 AU / Pluto 39.48 AU sit in the 3:2 resonance.
        self.assertTrue(in_mmr(30.07, 39.48, ratio="3:2"))

    def test_in_mmr_order_independent_and_malformed(self):
        self.assertTrue(in_mmr(1.587, 1.0, ratio="1:2"))   # same as 2:1
        self.assertFalse(in_mmr(1.0, 1.587, ratio="garbage"))
        self.assertFalse(in_mmr(1.0, 1.587, ratio="0:1"))


class TestGascheauCoorbital(unittest.TestCase):
    """G2 — Gascheau/Routh L4/L5 co-orbital stability."""

    def test_criterion_value(self):
        self.assertAlmostEqual(_GASCHEAU_CRIT_MU, 0.5 * (1.0 - math.sqrt(23.0 / 27.0)),
                               places=9)
        self.assertAlmostEqual(_GASCHEAU_CRIT_MU, 0.03852, places=4)

    def test_jupiter_trojan_stable(self):
        # Jupiter (317.8 M⊕) + a ~massless Trojan around the Sun: ratio ≈ 9.5e-4 ≪ μ_crit.
        r = gascheau_coorbital_stable(317.8, 0.0, 1.0)
        self.assertTrue(r["stable"])
        self.assertLess(r["mass_ratio"], _GASCHEAU_CRIT_MU)

    def test_massive_host_unstable(self):
        # A ~50 M_Jupiter host (≈ 15890 M⊕) exceeds the Gascheau limit → L4/L5 unstable.
        r = gascheau_coorbital_stable(50 * 317.8, 0.0, 1.0)
        self.assertFalse(r["stable"])
        self.assertGreater(r["mass_ratio"], _GASCHEAU_CRIT_MU)

    def test_bad_input(self):
        self.assertIn("error", gascheau_coorbital_stable(0, 0, 1))
        self.assertIn("error", gascheau_coorbital_stable(1, -1, 1))
        self.assertIn("error", gascheau_coorbital_stable(1, 0, 0))


class TestDeterminism(unittest.TestCase):
    """Pure helpers (no RNG) — repeated calls are byte-identical."""

    def test_repeatable(self):
        self.assertEqual(mutual_hill(1.0, 0.8, 1.0, 1.5, 1.0),
                         mutual_hill(1.0, 0.8, 1.0, 1.5, 1.0))
        self.assertEqual(nearest_mmr(1.5), nearest_mmr(1.5))
        self.assertEqual(gascheau_coorbital_stable(317.8, 0.01, 1.0),
                         gascheau_coorbital_stable(317.8, 0.01, 1.0))


# ── R2-C2 · spec validator + rule registry + evaluate_feasibility ────────────

def _pl(name, a, mass, ptype="rocky", radius=1.0, ecc=0.02, in_hz=False,
        hz_class=None, source="synthetic"):
    return {"name": name, "a_au": a, "mass_earth": mass, "radius_earth": radius,
            "ecc": ecc, "type": ptype, "in_hz": in_hz, "hz_class": hz_class,
            "source": source, "atmosphere": None, "moons": []}


def _base(planets):
    star = {"name": "Test", "spectral_class": "G2V", "teff": 5800.0, "mass_solar": 1.0,
            "radius_solar": 1.0, "luminosity": 1.0, "hz_inner_au": 0.95, "hz_outer_au": 1.37,
            "hz_opt_inner_au": 0.75, "hz_opt_outer_au": 1.77, "snow_line_au": 2.7,
            "source": "synthetic", "grounding": "default-extrapolation", "multiplicity": None}
    return {"seed": 1, "mode": "synthetic", "anchor_star": None, "star": star,
            "planets": planets, "warnings": [], "notes": []}


def _has_layers(res):
    return all(k in res for k in ("id", "type", "verdict", "layer1", "layer2", "layer3", "layer4"))


class TestRulePlanetAtLocation(unittest.TestCase):
    def test_isolated_feasible(self):
        base = _base([])
        c = {"type": "planet_at_location", "mass_earth": 1.0, "location": {"kind": "at", "au": 1.0}}
        r = _rule_planet_at_location(c, base, _derived_from_star(base["star"]))
        self.assertEqual(r["verdict"], "feasible")
        self.assertEqual(r["layer2"]["mechanism"], "isolated")

    def test_far_neighbours_feasible(self):
        base = _base([_pl("Test b", 0.3, 1.0), _pl("Test c", 5.0, 1.0)])
        c = {"type": "planet_at_location", "mass_earth": 1.0, "location": {"kind": "at", "au": 1.0}}
        r = _rule_planet_at_location(c, base, _derived_from_star(base["star"]))
        self.assertEqual(r["verdict"], "feasible")
        self.assertGreaterEqual(r["layer1"]["metrics"]["min_delta"], 10.0)

    def test_between_tight_giants_infeasible(self):
        base = _base([_pl("Test b", 2.0, 300.0, "gas", 10.0),
                      _pl("Test c", 2.6, 300.0, "gas", 10.0)])
        c = {"type": "planet_at_location", "mass_earth": 1.0,
             "location": {"kind": "between", "ref_a": "b", "ref_b": "c"}}
        r = _rule_planet_at_location(c, base, _derived_from_star(base["star"]))
        self.assertEqual(r["verdict"], "infeasible")
        self.assertIsNone(r["layer2"]["mechanism"])
        self.assertLess(r["layer1"]["metrics"]["min_delta"], _DELTA_HILL_CRIT)


class TestRuleTrojan(unittest.TestCase):
    def test_jupiter_host_feasible(self):
        base = _base([_pl("Test b", 5.0, 317.8, "gas", 11.0)])
        c = {"type": "trojan", "host": "b", "companion_type": "terrestrial", "point": "L4"}
        r = _rule_trojan(c, base, _derived_from_star(base["star"]))
        self.assertEqual(r["verdict"], "feasible")
        self.assertEqual(r["layer2"]["mechanism"], "trojan")

    def test_massive_host_infeasible(self):
        base = _base([_pl("Test b", 5.0, 50 * 317.8, "super_jovian", 12.0)])
        c = {"type": "trojan", "host": "b", "companion_type": "terrestrial", "point": "L5"}
        r = _rule_trojan(c, base, _derived_from_star(base["star"]))
        self.assertEqual(r["verdict"], "infeasible")

    def test_unresolvable_host_not_evaluated(self):
        base = _base([_pl("Test b", 5.0, 317.8, "gas", 11.0)])
        c = {"type": "trojan", "host": "zzz", "companion_type": "terrestrial", "point": "L4"}
        r = _rule_trojan(c, base, _derived_from_star(base["star"]))
        self.assertEqual(r["verdict"], "not_evaluated")


class TestRuleMoon(unittest.TestCase):
    def test_giant_moon_feasible(self):
        base = _base([_pl("Test b", 5.0, 317.8, "gas", 11.0)])
        c = {"type": "moon", "host": "b", "mass_earth": 0.05}
        r = _rule_moon(c, base, _derived_from_star(base["star"]))
        self.assertEqual(r["verdict"], "feasible")
        self.assertGreater(r["layer1"]["metrics"]["stable_outer_au"],
                           r["layer1"]["metrics"]["roche_fluid_au"])

    def test_terraformable_moon_marginal(self):
        base = _base([_pl("Test b", 1.0, 317.8, "gas", 11.0, in_hz=True)])
        c = {"type": "moon", "host": "b", "mass_earth": 1.0, "terraformable": True}
        r = _rule_moon(c, base, _derived_from_star(base["star"]))
        self.assertEqual(r["verdict"], "marginal")
        self.assertIn("tidal", r["layer1"]["reason"].lower())


class TestRuleResonance(unittest.TestCase):
    def test_two_to_one_feasible(self):
        base = _base([_pl("Test b", 1.0, 5.0), _pl("Test c", 1.587, 5.0)])
        c = {"type": "resonance", "bodies": ["b", "c"], "ratio": "2:1"}
        r = _rule_resonance(c, base, _derived_from_star(base["star"]))
        self.assertEqual(r["verdict"], "feasible")
        self.assertEqual(r["layer2"]["mechanism"], "mean_motion_resonance")

    def test_mismatch_infeasible(self):
        base = _base([_pl("Test b", 1.0, 5.0), _pl("Test c", 2.0, 5.0)])
        c = {"type": "resonance", "bodies": ["b", "c"], "ratio": "2:1"}
        r = _rule_resonance(c, base, _derived_from_star(base["star"]))
        self.assertEqual(r["verdict"], "infeasible")
        self.assertIsNotNone(r["layer1"]["metrics"]["nearest_mmr"])


class TestRefResolution(unittest.TestCase):
    def test_letter_and_symbolic(self):
        planets = [_pl("Test b", 0.5, 1.0), _pl("Test c", 5.0, 300.0, "gas"),
                   _pl("Test d", 30.0, 1.0)]
        d = _derived_from_star(_base(planets)["star"])
        self.assertEqual(_resolve_ref("b", planets, d)["name"], "Test b")
        self.assertEqual(_resolve_ref("outermost", planets, d)["name"], "Test d")
        self.assertEqual(_resolve_ref("giant", planets, d)["name"], "Test c")
        self.assertEqual(_resolve_ref("Test c", planets, d)["name"], "Test c")
        self.assertIsNone(_resolve_ref("zzz", planets, d))


class TestEvaluateFeasibility(unittest.TestCase):
    _CONS = [{"type": "planet_at_location", "planet_type": "terrestrial",
              "mass_earth": 1.0, "location": {"kind": "in_hz"}}]

    def test_shape_and_layers(self):
        r = evaluate_feasibility(7, spectral_class="G2V", n_planets=4, constraints=self._CONS)
        self.assertIn("feasible", r)
        self.assertIn("star", r)
        self.assertEqual(len(r["constraints"]), 1)
        res = r["constraints"][0]
        self.assertTrue(_has_layers(res))
        self.assertEqual(res["id"], "c1")
        self.assertEqual(res["layer3"]["grounding"], "default-extrapolation")

    def test_determinism(self):
        a = evaluate_feasibility(7, spectral_class="G2V", n_planets=4, constraints=self._CONS)
        b = evaluate_feasibility(7, spectral_class="G2V", n_planets=4, constraints=self._CONS)
        self.assertEqual(a, b)

    def test_unknown_type_not_evaluated(self):
        r = evaluate_feasibility(7, spectral_class="G2V", n_planets=3,
                                 constraints=[{"type": "frobnicate"}])
        self.assertEqual(r["constraints"][0]["verdict"], "not_evaluated")
        self.assertIn("star", r)        # base still rendered

    def test_unresolvable_ref_not_evaluated(self):
        r = evaluate_feasibility(7, spectral_class="G2V", n_planets=3,
                                 constraints=[{"type": "trojan", "host": "zzz",
                                               "companion_type": "terrestrial", "point": "L4"}])
        self.assertEqual(r["constraints"][0]["verdict"], "not_evaluated")

    def test_delegation_via_generate_system(self):
        via_gen = generate_system(7, spectral_class="G2V", n_planets=4, constraints=self._CONS)
        direct = evaluate_feasibility(7, spectral_class="G2V", n_planets=4, constraints=self._CONS)
        self.assertEqual(via_gen, direct)
        self.assertIn("feasible", via_gen)

    def test_base_error_passthrough(self):
        r = evaluate_feasibility(7, spectral_class="Z9V", n_planets=2, constraints=self._CONS)
        self.assertIn("error", r)


class TestZeroConstraintParity(unittest.TestCase):
    def test_r1_path_byte_identical(self):
        base = generate_system(7, spectral_class="G2V", n_planets=4)
        self.assertEqual(base, generate_system(7, spectral_class="G2V", n_planets=4,
                                               constraints=None))
        self.assertEqual(base, generate_system(7, spectral_class="G2V", n_planets=4,
                                               constraints=[]))
        self.assertNotIn("feasible", base)


class TestValidation(unittest.TestCase):
    def test_constraints_required_nonempty(self):
        self.assertIn("error", evaluate_feasibility(1, constraints=None))
        self.assertIn("error", evaluate_feasibility(1, constraints=[]))
        self.assertIn("error", validate_constraints("nope", None))

    def test_missing_type(self):
        self.assertIn("error", validate_constraints([{"planet_type": "terrestrial"}], None))

    def test_bad_companion(self):
        cons = [{"type": "planet_at_location", "mass_earth": 1.0, "location": {"kind": "in_hz"}}]
        self.assertIn("error", evaluate_feasibility(
            7, spectral_class="G2V", n_planets=2, constraints=cons,
            companion={"mass_solar": -1, "sma_au": 5}))


# ── R2-C3 · Layer-3 origin (tagged) ──────────────────────────────────────────

class TestLayer3Origin(unittest.TestCase):
    def test_planet_infeasible_low_plausibility(self):
        res = {"verdict": "infeasible", "layer1": {"metrics": {"target_au": 2.3}},
               "layer2": {"mechanism": None}}
        o = _origin_hypotheses({"type": "planet_at_location"}, _base([]),
                               {"snow_line": 2.7}, res)
        self.assertTrue(o["hypotheses"][0]["pathway"].lower().startswith("captured"))
        self.assertEqual(o["hypotheses"][0]["plausibility"], "low")
        self.assertEqual(o["grounding"], "default-extrapolation")

    def test_planet_feasible_beyond_snow_line_high(self):
        res = {"verdict": "feasible", "layer1": {"metrics": {"target_au": 5.0}},
               "layer2": {"mechanism": None}}
        o = _origin_hypotheses({"type": "planet_at_location"}, _base([]),
                               {"snow_line": 2.7}, res)
        self.assertIn("snow line", o["hypotheses"][0]["pathway"])
        self.assertEqual(o["hypotheses"][0]["plausibility"], "high")

    def test_resonance_feasible_pathway(self):
        res = {"verdict": "feasible", "layer1": {"metrics": {}},
               "layer2": {"mechanism": "mean_motion_resonance"}}
        o = _origin_hypotheses({"type": "resonance"}, _base([]), {}, res)
        self.assertIn("migration", o["hypotheses"][0]["pathway"])

    def test_all_hypotheses_tagged(self):
        for t, mech in (("trojan", "trojan"), ("moon", "bound_satellite")):
            res = {"verdict": "feasible", "layer1": {"metrics": {}}, "layer2": {"mechanism": mech}}
            o = _origin_hypotheses({"type": t}, _base([]), {"snow_line": 2.7}, res)
            self.assertTrue(all(h["grounding"] == "default-extrapolation"
                                for h in o["hypotheses"]))


# ── R2-C3 · Layer-4 alternatives (deterministic, spec_patch re-runs) ─────────

class TestLayer4Alternatives(unittest.TestCase):
    def _alts(self, c, planets):
        base = _base(planets)
        derived = _derived_from_star(base["star"])
        rule = _RULE_REGISTRY[c["type"]]
        res = rule(c, base, derived)
        l4 = _alternatives(c, base, derived, rule, res["verdict"])
        return base, derived, rule, res, l4

    def _assert_shape(self, l4):
        self.assertLessEqual(len(l4["alternatives"]), 3)
        for alt in l4["alternatives"]:
            self.assertEqual(set(alt), {"change", "result", "spec_patch"})

    def test_planet_mass_relaxation_flips_to_feasible(self):
        # 50 M⊕ between two Earth-mass neighbours is infeasible; a test-particle clears it.
        planets = [_pl("Test b", 1.0, 1.0), _pl("Test c", 1.3, 1.0)]
        c = {"type": "planet_at_location", "planet_type": "gas", "mass_earth": 50.0,
             "location": {"kind": "between", "ref_a": "b", "ref_b": "c"}}
        base, derived, rule, res, l4 = self._alts(c, planets)
        self.assertEqual(res["verdict"], "infeasible")
        self.assertTrue(l4["alternatives"])
        self._assert_shape(l4)
        flipped = any(rule({**c, **a["spec_patch"]}, base, derived)["verdict"] == "feasible"
                      for a in l4["alternatives"])
        self.assertTrue(flipped)

    def test_trojan_host_swap_alternative(self):
        planets = [_pl("Test heavy", 5.0, 50 * 317.8, "super_jovian", 12.0),
                   _pl("Test jove", 8.0, 317.8, "gas", 11.0)]
        c = {"type": "trojan", "host": "Test heavy", "companion_type": "terrestrial", "point": "L4"}
        base, derived, rule, res, l4 = self._alts(c, planets)
        self.assertEqual(res["verdict"], "infeasible")
        flipped = any(rule({**c, **a["spec_patch"]}, base, derived)["verdict"] == "feasible"
                      for a in l4["alternatives"])
        self.assertTrue(flipped)

    def test_resonance_ratio_snap_alternative(self):
        # Two planets near 3:2 but asked for 2:1 → alternative snaps the ratio to 3:2.
        planets = [_pl("Test b", 1.0, 5.0), _pl("Test c", 1.32, 5.0)]
        c = {"type": "resonance", "bodies": ["b", "c"], "ratio": "2:1"}
        base, derived, rule, res, l4 = self._alts(c, planets)
        self.assertEqual(res["verdict"], "infeasible")
        self.assertTrue(l4["alternatives"])
        flipped = any(rule({**c, **a["spec_patch"]}, base, derived)["verdict"] == "feasible"
                      for a in l4["alternatives"])
        self.assertTrue(flipped)

    def test_feasible_constraint_has_no_alternatives(self):
        # Through the full evaluator: a feasible constraint carries an empty Layer-4.
        r = evaluate_feasibility(7, spectral_class="G2V", n_planets=4, constraints=[
            {"type": "planet_at_location", "planet_type": "terrestrial",
             "mass_earth": 1.0, "location": {"kind": "in_hz"}}])
        res = r["constraints"][0]
        if res["verdict"] == "feasible":
            self.assertEqual(res["layer4"]["alternatives"], [])
            self.assertTrue(res["layer3"]["hypotheses"])

    def test_alternatives_deterministic(self):
        planets = [_pl("Test b", 1.0, 1.0), _pl("Test c", 1.3, 1.0)]
        c = {"type": "planet_at_location", "planet_type": "gas", "mass_earth": 50.0,
             "location": {"kind": "between", "ref_a": "b", "ref_b": "c"}}
        a1 = self._alts(c, planets)[4]
        a2 = self._alts(c, planets)[4]
        self.assertEqual(a1, a2)


class TestResonantAu(unittest.TestCase):
    def test_interior_2_1(self):
        # A body in interior 2:1 with a neighbour at 2.0 AU sits at 2.0 / 2^(2/3).
        au = _resonant_au(2.0, "2:1", interior=True)
        self.assertAlmostEqual(au, 2.0 / (2.0 ** (2.0 / 3.0)), places=6)
        self.assertLess(au, 2.0)

    def test_exterior_2_1(self):
        au = _resonant_au(2.0, "2:1", interior=False)
        self.assertGreater(au, 2.0)


# ── R2-C3 · stretch-vocab rules (D1) ─────────────────────────────────────────

class TestStretchVocab(unittest.TestCase):
    def test_habitable_world_feasible_and_relax(self):
        base = _base([_pl("Test b", 1.0, 1.0, "rocky", in_hz=True, hz_class="conservative")])
        d = _derived_from_star(base["star"])
        self.assertEqual(_rule_habitable_world({"type": "habitable_world"}, base, d)["verdict"],
                         "feasible")
        # Optimistic-only world fails the conservative requirement but the relax alt flips it.
        base2 = _base([_pl("Test b", 1.0, 1.0, "rocky", in_hz=True, hz_class="optimistic")])
        d2 = _derived_from_star(base2["star"])
        c = {"type": "habitable_world"}
        res = _rule_habitable_world(c, base2, d2)
        self.assertEqual(res["verdict"], "infeasible")
        l4 = _alternatives(c, base2, d2, _rule_habitable_world, res["verdict"])
        flipped = any(_rule_habitable_world({**c, **a["spec_patch"]}, base2, d2)["verdict"]
                      == "feasible" for a in l4["alternatives"])
        self.assertTrue(flipped)

    def test_alt_solvent_world(self):
        # Water liquid band at L=1 ≈ 0.60–1.11 AU → a world at 0.8 AU sits in it.
        base = _base([_pl("Test b", 0.8, 1.0, "rocky")])
        d = _derived_from_star(base["star"])
        r = _rule_alt_solvent_world({"type": "alt_solvent_world", "solvent": "water"}, base, d)
        self.assertEqual(r["verdict"], "feasible")
        # Nothing in the band → infeasible, band reported.
        base2 = _base([_pl("Test b", 30.0, 1.0, "ice")])
        d2 = _derived_from_star(base2["star"])
        r2 = _rule_alt_solvent_world({"type": "alt_solvent_world", "solvent": "water"}, base2, d2)
        self.assertEqual(r2["verdict"], "infeasible")
        self.assertIn("band_inner_au", r2["layer1"]["metrics"])

    def test_alt_solvent_world_bad_solvent(self):
        base = _base([_pl("Test b", 0.8, 1.0, "rocky")])
        d = _derived_from_star(base["star"])
        self.assertEqual(_rule_alt_solvent_world({"type": "alt_solvent_world"}, base, d)["verdict"],
                         "not_evaluated")

    def test_architecture_rules(self):
        base = _base([_pl("Test b", 5.0, 317.8, "gas", 11.0)])   # giant beyond snow (2.7)
        d = _derived_from_star(base["star"])
        self.assertEqual(_rule_architecture(
            {"type": "architecture", "rule": "giant_beyond_snow_line"}, base, d)["verdict"],
            "feasible")
        self.assertEqual(_rule_architecture(
            {"type": "architecture", "rule": "no_hot_jupiter"}, base, d)["verdict"], "feasible")
        # A hot Jupiter fails no_hot_jupiter and there's no giant beyond the snow line.
        hot = _base([_pl("Test b", 0.05, 317.8, "gas", 11.0)])
        dh = _derived_from_star(hot["star"])
        self.assertEqual(_rule_architecture(
            {"type": "architecture", "rule": "no_hot_jupiter"}, hot, dh)["verdict"], "infeasible")
        self.assertEqual(_rule_architecture(
            {"type": "architecture", "rule": "giant_beyond_snow_line"}, hot, dh)["verdict"],
            "infeasible")
        self.assertEqual(_rule_architecture(
            {"type": "architecture", "rule": "frobnicate"}, base, d)["verdict"], "not_evaluated")

    def test_stretch_types_registered(self):
        for t in ("habitable_world", "alt_solvent_world", "architecture"):
            self.assertIn(t, _RULE_REGISTRY)


# ── R2-C4 · N-body confirmation of marginal packing verdicts ─────────────────

class TestNbodyConfirm(unittest.TestCase):
    def _marginal_res(self, target_au):
        return {"id": "c1", "type": "planet_at_location", "verdict": "marginal",
                "layer1": {"stable": None, "reason": "marginal.",
                           "metrics": {"target_au": target_au, "min_delta": 5.0}},
                "layer2": {"mechanism": "hill_packing", "checked": ["hill_packing"], "note": "gray band"},
                "layer3": {"hypotheses": [], "grounding": "default-extrapolation"},
                "layer4": {"alternatives": []}}

    def test_confirm_upgrades_to_feasible(self):
        # A body at 5 AU among widely-spaced light neighbours survives the screen.
        base = _base([_pl("Test b", 1.0, 1.0), _pl("Test c", 10.0, 1.0)])
        d = _derived_from_star(base["star"])
        c = {"type": "planet_at_location", "planet_type": "terrestrial", "mass_earth": 1.0,
             "location": {"kind": "at", "au": 5.0}}
        out = _nbody_confirm(self._marginal_res(5.0), c, base, d)
        self.assertEqual(out["verdict"], "feasible")
        self.assertIn("nbody", out["layer2"]["checked"])
        self.assertIn("N-body", out["layer1"]["reason"])
        self.assertEqual(out["layer1"]["metrics"]["nbody_orbits"], 200)

    def test_confirm_downgrades_to_infeasible(self):
        # A body crammed between two close giants triggers a close encounter.
        base = _base([_pl("Test b", 1.0, 300.0, "gas", 10.0),
                      _pl("Test c", 1.1, 300.0, "gas", 10.0)])
        d = _derived_from_star(base["star"])
        c = {"type": "planet_at_location", "planet_type": "gas", "mass_earth": 300.0,
             "location": {"kind": "at", "au": 1.05}}
        out = _nbody_confirm(self._marginal_res(1.05), c, base, d)
        self.assertEqual(out["verdict"], "infeasible")
        self.assertIn("N-body", out["layer1"]["reason"])

    def test_non_packing_type_unchanged(self):
        base = _base([_pl("Test b", 5.0, 317.8, "gas", 11.0)])
        d = _derived_from_star(base["star"])
        res = {"type": "moon", "verdict": "marginal",
               "layer1": {"metrics": {}}, "layer2": {"checked": []}}
        self.assertIs(_nbody_confirm(res, {"type": "moon"}, base, d), res)

    def test_evaluator_nbody_flag_wires_through(self):
        # nbody=True is accepted by evaluate_feasibility and stays deterministic;
        # nbody=False leaves verdicts unchanged for the same spec.
        cons = [{"type": "planet_at_location", "planet_type": "terrestrial",
                 "mass_earth": 1.0, "location": {"kind": "in_hz"}}]
        a = evaluate_feasibility(7, spectral_class="G2V", n_planets=4, constraints=cons, nbody=True)
        b = evaluate_feasibility(7, spectral_class="G2V", n_planets=4, constraints=cons, nbody=True)
        self.assertEqual(a, b)
        self.assertIn("feasible", a)


# ── R2-C5 · multi-star S/P-type gate ─────────────────────────────────────────

def _readers_multiple():
    """Patch the R1 real-anchor readers to a single-companion Gaia-multiple system."""
    stack = ExitStack()
    sb = {"main_id": "Bin Star", "sp_type": "G2V", "teff": 5778.0, "vmag": 5.0,
          "plx_value": 100.0, "designations": {"HD": "HD 1"}, "gcns": {"n_components": 2}}
    rg = {"temp": 5778.0, "stellarMass": 1.0, "stellarRadius": 1.0, "bcLuminosity": 1.0,
          "spectral_type": "G2V", "bc_key": "G2"}
    stack.enter_context(mock.patch("core.generate.compute_simbad_lookup", return_value=sb))
    stack.enter_context(mock.patch("core.generate.compute_star_system_regions_from_simbad",
                                   return_value=rg))
    stack.enter_context(mock.patch("core.generate.compute_planetary_systems_composite",
                                   return_value={"error": "x"}))
    stack.enter_context(mock.patch("core.generate.compute_hwc", return_value={"error": "y"}))
    return stack


class TestBinaryGate(unittest.TestCase):
    _COMP = {"mass_solar": 0.5, "sma_au": 20.0}   # binary/2 = 10 AU S/P boundary

    def test_binary_gate_regimes(self):
        self.assertTrue(_binary_gate(2.0, 1.0, self._COMP)["is_stable"])     # S-type, inside crit
        self.assertFalse(_binary_gate(9.0, 1.0, self._COMP)["is_stable"])    # S-type, outside crit
        self.assertFalse(_binary_gate(30.0, 1.0, self._COMP)["is_stable"])   # P-type, inside crit
        self.assertTrue(_binary_gate(60.0, 1.0, self._COMP)["is_stable"])    # P-type, outside crit
        self.assertIsNone(_binary_gate(5.0, 1.0, None))

    def test_rule_infeasible_in_unstable_binary_region(self):
        base = _base([])
        d = _derived_from_star(base["star"]); d["companion"] = self._COMP
        c = {"type": "planet_at_location", "planet_type": "terrestrial",
             "mass_earth": 1.0, "location": {"kind": "at", "au": 9.0}}
        r = _rule_planet_at_location(c, base, d)
        self.assertEqual(r["verdict"], "infeasible")
        self.assertIn("Binary truncation", r["layer1"]["reason"])
        self.assertIn("binary_stability", r["layer2"]["checked"])
        self.assertEqual(r["layer1"]["metrics"]["binary_orbit_type"], "S-type")

    def test_rule_feasible_in_stable_binary_region(self):
        base = _base([])
        d = _derived_from_star(base["star"]); d["companion"] = self._COMP
        c = {"type": "planet_at_location", "planet_type": "terrestrial",
             "mass_earth": 1.0, "location": {"kind": "at", "au": 2.0}}
        r = _rule_planet_at_location(c, base, d)
        self.assertEqual(r["verdict"], "feasible")
        self.assertIn("stable region", r["layer1"]["reason"])
        self.assertIn("binary_stability", r["layer2"]["checked"])

    def test_no_companion_leaves_rule_unchanged(self):
        base = _base([])
        d = _derived_from_star(base["star"])           # no companion key
        c = {"type": "planet_at_location", "planet_type": "terrestrial",
             "mass_earth": 1.0, "location": {"kind": "at", "au": 9.0}}
        r = _rule_planet_at_location(c, base, d)
        self.assertEqual(r["verdict"], "feasible")     # isolated, no binary gate
        self.assertNotIn("binary_stability", r["layer2"]["checked"])

    def test_evaluator_companion_note_and_determinism(self):
        cons = [{"type": "planet_at_location", "planet_type": "terrestrial",
                 "mass_earth": 1.0, "location": {"kind": "at", "au": 9.0}}]
        a = evaluate_feasibility(7, spectral_class="G2V", n_planets=3,
                                 constraints=cons, companion=self._COMP)
        b = evaluate_feasibility(7, spectral_class="G2V", n_planets=3,
                                 constraints=cons, companion=self._COMP)
        self.assertEqual(a, b)
        self.assertFalse(a["feasible"])
        self.assertEqual(a["constraints"][0]["verdict"], "infeasible")
        self.assertTrue(any("companion hint" in n for n in a["notes"]))

    def test_bad_companion_ecc_rejected(self):
        cons = [{"type": "planet_at_location", "mass_earth": 1.0, "location": {"kind": "in_hz"}}]
        self.assertIn("error", evaluate_feasibility(
            7, spectral_class="G2V", n_planets=2, constraints=cons,
            companion={"mass_solar": 0.5, "sma_au": 20.0, "ecc": 1.5}))

    def test_no_hint_real_anchor_multiple_note(self):
        cons = [{"type": "planet_at_location", "planet_type": "terrestrial",
                 "mass_earth": 1.0, "location": {"kind": "in_hz"}}]
        with _readers_multiple():
            r = evaluate_feasibility(3, anchor_star="Bin Star", n_planets=2, constraints=cons)
        self.assertEqual(r["mode"], "real_anchor")
        self.assertTrue(any("known multiple" in n.lower() and "companion" in n.lower()
                            for n in r["notes"]))

    def test_hint_overrides_safe_cap_note(self):
        cons = [{"type": "planet_at_location", "planet_type": "terrestrial",
                 "mass_earth": 1.0, "location": {"kind": "in_hz"}}]
        with _readers_multiple():
            r = evaluate_feasibility(3, anchor_star="Bin Star", n_planets=2,
                                     constraints=cons, companion={"mass_solar": 0.5, "sma_au": 50.0})
        self.assertTrue(any("supplied companion hint" in n for n in r["notes"]))
        self.assertFalse(any("known multiple" in n.lower() for n in r["notes"]))


# ── R3-C5 · Layer-3 research-priors calibration ──────────────────────────────
import json as _json
import os as _os
import shutil as _shutil
import tempfile as _tempfile
from unittest import mock as _mock

from core.priors import ResearchPriors
from core.research_priors import compute_research_priors_ingest

_FIXD = _os.path.join(_os.path.dirname(__file__), "fixtures")
_SAMPLE_FIX = _os.path.join(_FIXD, "research_priors_sample.json")
_IDENTITY_FIX = _os.path.join(_FIXD, "research_priors_identity.json")

# A feasible body beyond the snow line (drives the in_situ_beyond_snow context).
_RES_BEYOND = {"verdict": "feasible", "layer1": {"metrics": {"target_au": 5.0}},
               "layer2": {"mechanism": None}}
_DERIVED = {"snow_line": 2.7}


class TestLayer3Calibration(unittest.TestCase):
    """_origin_hypotheses reads ResearchPriors.origin_priors with per-key fallback."""

    def test_calibrated_context_uses_dataset_and_grounding(self):
        prov = ResearchPriors.from_file(_SAMPLE_FIX)
        o = _origin_hypotheses({"type": "planet_at_location"}, _base([]),
                               _DERIVED, _RES_BEYOND, prov)
        # sample calibrates in_situ_beyond_snow with TWO pathways
        self.assertTrue(any("modest inward migration" in h["pathway"]
                            for h in o["hypotheses"]))
        self.assertTrue(all(h["grounding"] == "research-calibrated"
                            for h in o["hypotheses"]))
        self.assertEqual(o["grounding"], "research-calibrated")

    def test_absent_context_falls_back_to_heuristic_even_under_research(self):
        with open(_SAMPLE_FIX, encoding="utf-8") as _fh:
            contract = _json.load(_fh)
        del contract["origin_priors"]["planet_at_location:in_situ_beyond_snow"]
        prov = ResearchPriors.from_contract(contract)
        o = _origin_hypotheses({"type": "planet_at_location"}, _base([]),
                               _DERIVED, _RES_BEYOND, prov)
        # the omitted context → heuristic pathway, tagged default-extrapolation,
        # even though the provider itself is research-calibrated (honest mixing)
        self.assertEqual(len(o["hypotheses"]), 1)
        self.assertIn("snow line", o["hypotheses"][0]["pathway"])
        self.assertEqual(o["hypotheses"][0]["grounding"], "default-extrapolation")
        self.assertEqual(o["grounding"], "research-calibrated")   # top-level = provider

    def test_default_provider_byte_identical_to_r2(self):
        # priors=None → DefaultPriors → the pre-R3 heuristic output exactly.
        o = _origin_hypotheses({"type": "planet_at_location"}, _base([]),
                               _DERIVED, _RES_BEYOND)
        self.assertEqual(o["grounding"], "default-extrapolation")
        self.assertEqual(o["hypotheses"][0]["pathway"],
                         "in-situ accretion beyond the snow line")
        self.assertEqual(o["hypotheses"][0]["grounding"], "default-extrapolation")


class TestEvaluateFeasibilityResearchPolicy(unittest.TestCase):
    """research_policy threaded through evaluate_feasibility's base build + Layer-3."""

    _CONS = [{"type": "planet_at_location", "planet_type": "terrestrial",
              "mass_earth": 1.0, "location": {"kind": "in_hz"}}]

    def setUp(self):
        self.cache = _tempfile.mkdtemp()
        self.addCleanup(_shutil.rmtree, self.cache, ignore_errors=True)

    def _strict(self, **kw):
        with _mock.patch("core.priors._DEFAULT_CACHE_DIR", self.cache):
            return evaluate_feasibility(research_policy="strict", constraints=self._CONS, **kw)

    def test_permissive_layer3_default_grounded(self):
        r = evaluate_feasibility(7, spectral_class="G2V", n_planets=4, constraints=self._CONS)
        self.assertEqual(r["constraints"][0]["layer3"]["grounding"], "default-extrapolation")
        self.assertTrue(any("grounding=default-extrapolation" in n for n in r["notes"]))

    def test_strict_calibrated_and_deterministic(self):
        compute_research_priors_ingest(path=_SAMPLE_FIX, cache_dir=self.cache)
        a = self._strict(seed=7, spectral_class="G2V", n_planets=4)
        b = self._strict(seed=7, spectral_class="G2V", n_planets=4)
        self.assertEqual(a, b)                                      # determinism
        self.assertEqual(a["constraints"][0]["layer3"]["grounding"], "research-calibrated")
        self.assertEqual(a["star"]["grounding"], "research-calibrated")   # base sampling too (D5)
        self.assertTrue(any("dataset sample-2026-06-24" in n for n in a["notes"]))

    def test_strict_without_cache_errors(self):
        r = self._strict(seed=7, spectral_class="G2V", n_planets=4)   # empty cache
        self.assertIn("error", r)
        self.assertIn("strict", r["error"])


class TestLayer3MetallicityVariant(unittest.TestCase):
    """R3-V2 B4: metallicity-qualified origin keys ('<key>:metal_rich'/':metal_poor')
    are preferred when the host [Fe/H] falls in that tail; else the base key."""

    _RICH_PATHWAY = "metal-rich rapid core+gas accretion"

    def _prov(self):
        with open(_SAMPLE_FIX, encoding="utf-8") as fh:
            c = _json.load(fh)
        c["origin_priors"]["planet_at_location:in_situ_beyond_snow:metal_rich"] = [
            {"pathway": self._RICH_PATHWAY, "plausibility": "high"}]
        return ResearchPriors.from_contract(c)

    def _hyps(self, feh):
        o = _origin_hypotheses({"type": "planet_at_location"}, _base([]),
                               {"snow_line": 2.7, "feh": feh}, _RES_BEYOND, self._prov())
        return [h["pathway"] for h in o["hypotheses"]]

    def test_metal_rich_prefers_qualified_key(self):
        self.assertTrue(any(self._RICH_PATHWAY in p for p in self._hyps(0.3)))

    def test_neutral_uses_base_key(self):
        self.assertFalse(any(self._RICH_PATHWAY in p for p in self._hyps(0.0)))

    def test_absent_feh_uses_base_key(self):
        self.assertFalse(any(self._RICH_PATHWAY in p for p in self._hyps(None)))

    def test_undefined_variant_falls_back_to_base(self):
        # metal_poor host but the dataset defines no ':metal_poor' variant → base key.
        self.assertFalse(any(self._RICH_PATHWAY in p for p in self._hyps(-0.9)))
        self.assertTrue(self._hyps(-0.9))   # base key still yields hypotheses


if __name__ == "__main__":
    unittest.main()
