# tests/test_oec_derived.py — the OEC System View derived layer (core/oec_derived.py).
#
# Pure math + contract tests; no Qt, no network, no DB — these always run.
#
# Stage 1b covers the star-side minimum (`luminosity_lsun`, `hz_bounds`):
#   T8 — numeric anchors (Sol-like, tau Ceti)
#   T9 — the §D.2 contract: None + a non-empty reason, never a raise, never a 0,
#        every entry carrying `source`, and no `{"error"}` dict reaching a caller.

import unittest

from core import oec_derived


class DerivedContractTests(unittest.TestCase):
    """Shape rules that hold for every entry of every kind."""

    def _all_entries(self, result):
        for key, entry in result.items():
            yield key, entry

    def test_every_entry_has_the_four_contract_keys(self):
        r = oec_derived.derive("star", {"radius": 1.0, "temperature": 5778.0})
        self.assertTrue(r)
        for key, entry in self._all_entries(r):
            self.assertEqual(set(entry), {"value", "unit", "reason", "source"}, key)

    def test_every_entry_carries_a_source(self):
        for values in ({"radius": 1.0, "temperature": 5778.0}, {}, {"radius": 0.0}):
            for key, entry in self._all_entries(oec_derived.derive("star", values)):
                self.assertTrue(entry["source"], f"{key} has no source")

    def test_no_error_key_ever_reaches_the_caller(self):
        for values in ({}, {"temperature": 40000.0, "radius": 5.0},
                       {"radius": -1.0, "temperature": 5000.0}):
            for key, entry in self._all_entries(oec_derived.derive("star", values)):
                self.assertNotIn("error", entry, key)

    def test_unknown_kind_returns_empty(self):
        self.assertEqual(oec_derived.derive("nonsense", {}), {})
        self.assertEqual(oec_derived.derive("system", {}), {})

    def test_satellites_are_not_routed_through_the_planet_path(self):
        """A `<satellite>`'s `semimajoraxis` is **planet-centric**, so the planet
        derivation's Kepler recovery, insolation, Hill radius and RV amplitude —
        all of which assume a star at the focus — would answer a different
        question. (Not a unit problem: OEC catalogues satellite mass/radius in
        Jupiter units, exactly like a planet's — R3, 2026-08-02.)"""
        self.assertEqual(oec_derived.derive("satellite", {"mass": 0.01,
                                                          "radius": 0.3}), {})

    def test_missing_input_is_none_with_a_reason_not_zero(self):
        r = oec_derived.derive("star", {})
        for key, entry in self._all_entries(r):
            self.assertIsNone(entry["value"], key)
            self.assertTrue(entry["reason"], f"{key} has no reason")
            self.assertNotEqual(entry["value"], 0, key)


class LuminosityTests(unittest.TestCase):
    def test_sol_like_anchor(self):
        r = oec_derived.derive("star", {"radius": 1.0, "temperature": 5778.0})
        self.assertAlmostEqual(r["luminosity_lsun"]["value"], 1.000, places=3)
        self.assertEqual(r["luminosity_lsun"]["unit"], "L☉")
        self.assertIsNone(r["luminosity_lsun"]["reason"])

    def test_tau_ceti_anchor(self):
        # tau Ceti (OEC): R = 0.793 R☉, Teff = 5344 K  →  L = 0.4602 L☉
        r = oec_derived.derive("star", {"radius": 0.793, "temperature": 5344.0})
        self.assertAlmostEqual(r["luminosity_lsun"]["value"], 0.4602, places=3)

    def test_missing_radius_and_missing_temperature_each_state_their_reason(self):
        no_r = oec_derived.derive("star", {"temperature": 5344.0})["luminosity_lsun"]
        self.assertIsNone(no_r["value"])
        self.assertIn("radius", no_r["reason"])
        no_t = oec_derived.derive("star", {"radius": 0.793})["luminosity_lsun"]
        self.assertIsNone(no_t["value"])
        self.assertIn("temperature", no_t["reason"])

    def test_zero_and_negative_inputs_are_rejected(self):
        for values in ({"radius": 0.0, "temperature": 5000.0},
                       {"radius": 1.0, "temperature": 0.0},
                       {"radius": -1.0, "temperature": 5000.0}):
            e = oec_derived.derive("star", values)["luminosity_lsun"]
            self.assertIsNone(e["value"], values)
            self.assertTrue(e["reason"], values)

    def test_non_numeric_input_does_not_raise(self):
        e = oec_derived.derive("star", {"radius": "n/a", "temperature": None})
        self.assertIsNone(e["luminosity_lsun"]["value"])


class HabitableZoneGateTests(unittest.TestCase):
    """§D.2's headline: `compute_habitable_zone` RAISES above ~10 700 K. The gate
    lives here, never in the caller."""

    def test_tau_ceti_conservative_bounds(self):
        r = oec_derived.derive("star", {"radius": 0.793, "temperature": 5344.0})
        hz = r["hz_bounds"]["value"]
        self.assertAlmostEqual(hz["conservative_inner_au"], 0.661, places=2)
        self.assertAlmostEqual(hz["conservative_outer_au"], 1.182, places=2)
        self.assertEqual(len(hz["zones"]), 6)
        self.assertLess(hz["optimistic_inner_au"], hz["conservative_inner_au"])
        self.assertGreater(hz["optimistic_outer_au"], hz["conservative_outer_au"])

    def test_hot_host_returns_a_reason_and_does_not_raise(self):
        for teff in (7200.1, 8000.0, 10000.0, 10700.0, 40000.0):
            e = oec_derived.derive("star", {"radius": 2.0, "temperature": teff})["hz_bounds"]
            self.assertIsNone(e["value"], teff)
            self.assertIn("Kopparapu", e["reason"], teff)

    def test_cool_host_below_the_floor_is_gated(self):
        e = oec_derived.derive("star", {"radius": 0.1, "temperature": 2400.0})["hz_bounds"]
        self.assertIsNone(e["value"])
        self.assertIn("Kopparapu", e["reason"])

    def test_gate_boundaries_are_inclusive(self):
        for teff in (2600.0, 7200.0):
            e = oec_derived.derive("star", {"radius": 1.0, "temperature": teff})["hz_bounds"]
            self.assertIsNotNone(e["value"], teff)

    def test_no_radius_means_no_luminosity_so_no_hz(self):
        e = oec_derived.derive("star", {"temperature": 5344.0})["hz_bounds"]
        self.assertIsNone(e["value"])
        self.assertIn("luminosity", e["reason"])


# ── Stage 4a — the rest of the star-side derived layer ──────────────────────
# tau Ceti (OEC): M = 0.783 M☉, R = 0.793 R☉, Teff = 5344 K, V = 3.50,
# B = 4.22, K = 1.68, d = 3.6502 pc. Anchors computed independently.
_TAU = {"mass": 0.783, "radius": 0.793, "temperature": 5344.0,
        "magV": 3.50, "magB": 4.22, "magK": 1.68, "age": 5.8}
_TAU_SYS = {"distance": 3.6502}


def _tau(**over):
    v = dict(_TAU)
    v.update(over)
    return oec_derived.derive("star", v, system_values=_TAU_SYS)


class ScaleConstantTests(unittest.TestCase):
    """The three scale constants are DERIVED from `core.equations`, not typed —
    the repo already carries three solar-Teff conventions and must not gain a
    fourth solar-radius one."""

    def test_constants_match_their_textbook_values(self):
        self.assertAlmostEqual(oec_derived._LOG_G_SUN, 4.438, places=3)
        self.assertAlmostEqual(oec_derived._RHO_SUN_GCC, 1.410, places=3)
        self.assertAlmostEqual(oec_derived._ANG_DIAM_MAS, 9.301, places=3)


class StarDerivedAnchorTests(unittest.TestCase):
    def test_tau_ceti_anchors(self):
        r = _tau()
        self.assertAlmostEqual(r["luminosity_lsun"]["value"], 0.4602, places=4)
        self.assertAlmostEqual(r["log_g"]["value"], 4.533, places=3)
        self.assertAlmostEqual(r["mean_density_gcc"]["value"], 2.214, places=3)
        self.assertAlmostEqual(r["abs_mag_v"]["value"], 5.688, places=3)
        self.assertAlmostEqual(r["angular_diameter_mas"]["value"], 2.021, places=3)
        self.assertAlmostEqual(r["light_years"]["value"], 11.9053, places=3)
        self.assertAlmostEqual(r["parallax_mas"]["value"], 273.96, places=2)
        self.assertAlmostEqual(r["b_minus_v"]["value"], 0.72, places=6)
        self.assertAlmostEqual(r["v_minus_k"]["value"], 1.82, places=6)

    def test_evolution_for_a_sun_like_star(self):
        r = oec_derived.derive("star", {"mass": 1.0, "radius": 1.0,
                                        "temperature": 5778.0, "age": 4.6})
        self.assertAlmostEqual(r["ms_lifetime_gyr"]["value"], 10.1, places=1)
        self.assertEqual(r["stage"]["value"], "Main Sequence")

    def test_stage_needs_a_catalogued_age(self):
        r = oec_derived.derive("star", {"mass": 1.0})
        self.assertIsNone(r["stage"]["value"])
        self.assertIn("age", r["stage"]["reason"])
        self.assertIsNotNone(r["ms_lifetime_gyr"]["value"])

    def test_ice_lines_are_a_list_with_the_water_snow_line(self):
        r = _tau()["ice_lines"]
        self.assertIsInstance(r["value"], list)
        snow = next(l for l in r["value"] if l["kind"] == "snow_line")
        self.assertAlmostEqual(snow["t_cond_k"], 170.0, places=1)
        # 2.68 AU at L = 1; tau Ceti is fainter, so its snow line is closer in
        self.assertAlmostEqual(snow["au"], 2.68 * (0.4602 ** 0.5), places=2)


class StarDerivedGateTests(unittest.TestCase):
    """§D.2 — every gate, on every Stage-4a key."""

    def test_no_distance_gates_the_distance_block(self):
        r = oec_derived.derive("star", _TAU, system_values={})
        for key in ("light_years", "parallax_mas", "angular_diameter_mas",
                    "abs_mag_v"):
            self.assertIsNone(r[key]["value"], key)
            self.assertTrue(r[key]["reason"], key)

    def test_zero_distance_does_not_divide_by_zero(self):
        r = oec_derived.derive("star", _TAU, system_values={"distance": 0})
        self.assertIsNone(r["parallax_mas"]["value"])
        self.assertIn("zero", r["parallax_mas"]["reason"])

    def test_zero_radius_does_not_take_log_of_zero(self):
        r = _tau(radius=0.0)
        for key in ("log_g", "mean_density_gcc", "angular_diameter_mas"):
            self.assertIsNone(r[key]["value"], key)

    def test_mass_outside_the_evolution_domain_is_unwrapped_to_a_reason(self):
        for mass in (0.05, 25.0):
            r = oec_derived.derive("star", {"mass": mass})["ms_lifetime_gyr"]
            self.assertIsNone(r["value"], mass)
            self.assertTrue(r["reason"], mass)
            self.assertNotIn("error", r)

    def test_missing_magnitudes_gate_the_colours(self):
        r = _tau(magB=None, magK=None)
        self.assertIsNone(r["b_minus_v"]["value"])
        self.assertIsNone(r["v_minus_k"]["value"])
        self.assertIsNotNone(r["abs_mag_v"]["value"])       # V alone still works

    def test_every_stage_4a_key_carries_a_source(self):
        for values in (_TAU, {}, {"mass": 0.0, "radius": 0.0}):
            for key, entry in oec_derived.derive(
                    "star", values, system_values=_TAU_SYS).items():
                self.assertTrue(entry["source"], key)
                self.assertNotIn("error", entry, key)

    def test_a_hot_star_produces_everything_except_the_hz(self):
        """The D.2 raise path must gate only what it has to."""
        r = oec_derived.derive("star", {"mass": 2.1, "radius": 1.8,
                                        "temperature": 9000.0},
                               system_values={"distance": 25.0})
        self.assertIsNone(r["hz_bounds"]["value"])          # Kopparapu-gated
        # Everything that does NOT depend on the Kopparapu polynomial still works
        self.assertIsNotNone(r["ice_lines"]["value"])
        self.assertIsNotNone(r["luminosity_lsun"]["value"])
        self.assertIsNotNone(r["log_g"]["value"])
        self.assertIsNotNone(r["angular_diameter_mas"]["value"])


class LowMassLifetimeTests(unittest.TestCase):
    """A < 0.8 M☉ star's `T_ms = 10¹⁰·M^−2.5` is a formal extrapolation: Kepler-16 B
    (0.20 M☉) computes 564 Gyr, a figure with no physical content."""

    def test_a_low_mass_star_carries_the_hubble_qualifier(self):
        e = oec_derived.derive("star", {"mass": 0.20})["ms_lifetime_gyr"]
        self.assertIsNotNone(e["value"])            # raw figure kept for consumers
        self.assertGreater(e["value"], oec_derived.HUBBLE_GYR)
        self.assertIn("Hubble", e["reason"])

    def test_a_solar_mass_star_carries_no_qualifier(self):
        e = oec_derived.derive("star", {"mass": 1.0})["ms_lifetime_gyr"]
        self.assertIsNone(e["reason"])

    def test_the_qualifier_keys_on_the_value_not_the_low_mass_flag(self):
        """`T_ms` crosses 13.8 Gyr at ≈0.883 M☉ but `low_mass` is set only below
        0.8, so the 0.80–0.88 band showed a bare bound with no explanation."""
        for mass in (0.81, 0.85, 0.88):
            e = oec_derived.derive("star", {"mass": mass})["ms_lifetime_gyr"]
            self.assertGreater(e["value"], oec_derived.HUBBLE_GYR, mass)
            self.assertTrue(e["reason"], f"{mass} M☉ has a bound with no qualifier")
            self.assertIn("Hubble", e["reason"], mass)
            self.assertNotIn("M < 0.8", e["reason"], mass)   # not a low-mass star

    def test_below_the_flag_the_qualifier_also_names_the_range(self):
        e = oec_derived.derive("star", {"mass": 0.79})["ms_lifetime_gyr"]
        self.assertIn("M < 0.8", e["reason"])

    def test_no_star_shows_a_bound_without_a_reason(self):
        """Whatever the mass, a displayed '> 13.8 Gyr' always carries its why."""
        m = 0.10
        while m <= 20.0:
            e = oec_derived.derive("star", {"mass": round(m, 2)})["ms_lifetime_gyr"]
            if e["value"] is not None and e["value"] > oec_derived.HUBBLE_GYR:
                self.assertTrue(e["reason"], f"{m} M☉")
            m += 0.01

    def test_a_qualifier_is_not_an_absence(self):
        """`reason` beside a value means 'caveat', not 'missing' — the two must not
        be conflated by any consumer."""
        e = oec_derived.derive("star", {"mass": 0.20})["ms_lifetime_gyr"]
        self.assertTrue(e["reason"] and e["value"] is not None)


class CircumbinaryHzTests(unittest.TestCase):
    """D9 — the P-type HZ from combined light, behind the same D.2 gate."""

    def _binary(self, comps):
        return oec_derived.derive("binary", {"components": comps})["hz_circumbinary"]

    def test_two_sun_like_components(self):
        e = self._binary([{"radius": 1.0, "temperature": 5778.0},
                          {"radius": 1.0, "temperature": 5778.0}])
        self.assertAlmostEqual(e["value"]["combined_lum"], 2.0, places=3)
        self.assertAlmostEqual(e["value"]["eff_teff"], 5778.0, places=1)
        # brighter pair → HZ further out than a single Sun's 0.99 AU
        self.assertGreater(e["value"]["conservative_inner_au"], 0.99)

    def test_one_component_is_not_enough(self):
        e = self._binary([{"radius": 1.0, "temperature": 5778.0}])
        self.assertIsNone(e["value"])
        self.assertIn("both components", e["reason"])

    def test_a_hot_pair_is_gated_before_the_raising_call(self):
        e = self._binary([{"radius": 2.0, "temperature": 11000.0},
                          {"radius": 2.0, "temperature": 11000.0}])
        self.assertIsNone(e["value"])
        self.assertIn("Kopparapu", e["reason"])

    def test_a_cool_pair_is_gated_too(self):
        e = self._binary([{"radius": 0.2, "temperature": 2400.0},
                          {"radius": 0.2, "temperature": 2400.0}])
        self.assertIsNone(e["value"])
        self.assertIn("Kopparapu", e["reason"])

    def test_stars_do_not_get_a_circumbinary_hz(self):
        self.assertNotIn("hz_circumbinary", _tau())


# ── Stage 4b — the planet-side derived layer ────────────────────────────────
# tau Ceti host: M = 0.783 M☉, R = 0.793 R☉, Teff = 5344 K (→ L = 0.4602 L☉).
_TAU_HOST = {"mass": 0.783, "radius": 0.793, "temperature": 5344.0}
# tau Cet e: a = 0.538 AU, e = 0.18, P = 162.87 d, M·sin i = 3.941 M⊕.
_TAU_E = {"mass": 3.941 / 317.828, "mass_type": "msini", "semimajoraxis": 0.538,
          "eccentricity": 0.18, "period": 162.87}
# tau Cet g: P = 20.00 d, no semi-major axis at all — the recovery case.
_TAU_G = {"mass": 1.751 / 317.828, "mass_type": "msini", "period": 20.0,
          "eccentricity": 0.06}


def _planet(values, host=None):
    return oec_derived.derive("planet", values, host_values=host or _TAU_HOST)


class PlanetScaleConstantTests(unittest.TestCase):
    def test_jupiter_constants_use_the_equatorial_radius(self):
        # A *mean*-radius density constant would be 1.326 — a 22% error (§D.1)
        self.assertAlmostEqual(oec_derived._RHO_JUP_GCC, 1.240, places=3)
        self.assertAlmostEqual(oec_derived._G_JUP_EARTH_G, 2.527, places=3)


class PlanetAnchorTests(unittest.TestCase):
    def test_tau_ceti_e_anchors(self):
        r = _planet(_TAU_E)
        self.assertAlmostEqual(r["insolation_searth"]["value"], 1.590, places=3)
        self.assertAlmostEqual(r["peri_distance_au"]["value"], 0.441, places=3)
        self.assertAlmostEqual(r["apo_distance_au"]["value"], 0.635, places=3)
        # K = 0.552 at e = 0.18. The e = 0 value is 0.543 — a test that passes
        # against both is not testing the eccentricity path.
        self.assertAlmostEqual(r["rv_semi_amplitude_ms"]["value"], 0.552, places=3)
        self.assertNotAlmostEqual(r["rv_semi_amplitude_ms"]["value"], 0.543, places=3)
        self.assertIn("Optimistic", r["hz_verdict"]["value"])

    def test_tau_ceti_g_recovers_its_semi_major_axis(self):
        r = _planet(_TAU_G)
        self.assertAlmostEqual(r["sma_au"]["value"], 0.1329, places=4)
        self.assertIn("Kepler", r["sma_au"]["source"])

    def test_the_days_to_years_conversion_is_applied(self):
        """Feeding days straight into Kepler III overstates `a` by 365.25^⅔ ≈ 51×."""
        r = _planet({"period": 365.25}, host={"mass": 1.0})
        self.assertAlmostEqual(r["sma_au"]["value"], 1.0, places=6)

    def test_a_catalogued_sma_wins_and_is_marked_as_catalogued(self):
        r = _planet(_TAU_E)
        self.assertEqual(r["sma_au"]["value"], 0.538)
        self.assertEqual(r["sma_au"]["source"], "catalogued")

    def test_jupiter_at_one_au_bulk_properties(self):
        r = _planet({"mass": 1.0, "radius": 1.0, "semimajoraxis": 1.0},
                    host={"mass": 1.0, "radius": 1.0, "temperature": 5778.0})
        self.assertAlmostEqual(r["density_gcc"]["value"], 1.240, places=3)
        self.assertAlmostEqual(r["surface_gravity_g"]["value"], 2.527, places=3)
        self.assertAlmostEqual(r["insolation_searth"]["value"], 1.0, places=3)

    def test_transit_and_hill_for_a_jupiter_analogue(self):
        r = _planet({"mass": 1.0, "radius": 1.0, "semimajoraxis": 1.0},
                    host={"mass": 1.0, "radius": 1.0, "temperature": 5778.0})
        # (R♃/R☉)² = (11.209/109.17)² ≈ 1.05e-2 → ~10 500 ppm
        self.assertAlmostEqual(r["transit_depth_ppm"]["value"], 10547, delta=200)
        self.assertAlmostEqual(r["transit_prob"]["value"], 0.00465, delta=0.0005)
        self.assertGreater(r["hill_radius_au"]["value"], 0.0)
        self.assertLess(r["moon_limit_au"]["value"], r["hill_radius_au"]["value"])


class PlanetMsiniTests(unittest.TestCase):
    """§D.1 — an msini mass already carries sin i; passing a catalogued
    inclination too would double-count it."""

    def test_inclination_is_forced_to_90_for_an_msini_mass(self):
        base = dict(_TAU_E)
        base["inclination"] = 30.0                 # would halve K if applied
        forced = _planet(base)["rv_semi_amplitude_ms"]["value"]
        self.assertAlmostEqual(forced, _planet(_TAU_E)["rv_semi_amplitude_ms"]["value"],
                               places=9)
        self.assertIn("double-counting",
                      _planet(base)["rv_semi_amplitude_ms"]["source"])

    def test_a_true_mass_does_use_the_catalogued_inclination(self):
        true_mass = {k: v for k, v in _TAU_E.items() if k != "mass_type"}
        edge_on = _planet(true_mass)["rv_semi_amplitude_ms"]["value"]
        true_mass["inclination"] = 30.0
        inclined = _planet(true_mass)["rv_semi_amplitude_ms"]["value"]
        self.assertLess(inclined, edge_on)
        self.assertAlmostEqual(inclined, edge_on * 0.5, places=6)   # sin 30° = ½


class PlanetGateTests(unittest.TestCase):
    def test_exactly_one_of_period_or_sma_is_passed_to_the_rv_calculator(self):
        """`compute_rv_semi_amplitude` errors when given both — and tau Cet e
        carries both."""
        e = _planet(_TAU_E)["rv_semi_amplitude_ms"]
        self.assertIsNotNone(e["value"])
        self.assertIsNone(e["reason"])

    def test_unbound_eccentricity_is_gated(self):
        for ecc in (1.0, 1.2, -0.1):
            v = dict(_TAU_E, eccentricity=ecc)
            r = _planet(v)
            self.assertIsNone(r["peri_distance_au"]["value"], ecc)
            self.assertIn("bound orbit", r["peri_distance_au"]["reason"])
            # …but a bad eccentricity must not poison the rest
            self.assertIsNotNone(r["insolation_searth"]["value"], ecc)

    def test_a_negative_periastron_distance_can_never_be_returned(self):
        for ecc in (0.0, 0.5, 0.99, 1.0, 5.0):
            v = _planet(dict(_TAU_E, eccentricity=ecc))["peri_distance_au"]["value"]
            if v is not None:
                self.assertGreater(v, 0.0, ecc)

    def test_a_rogue_planet_has_no_host_so_states_reasons(self):
        r = oec_derived.derive("planet", {"mass": 6.0}, host_values={})
        for key in ("sma_au", "insolation_searth", "hz_verdict",
                    "rv_semi_amplitude_ms", "hill_radius_au"):
            self.assertIsNone(r[key]["value"], key)
            self.assertTrue(r[key]["reason"], key)

    def test_insolation_survives_a_host_outside_the_kopparapu_range(self):
        """S = L/a² needs no polynomial, so it is reported even when the verdict
        cannot be."""
        r = _planet({"semimajoraxis": 1.0},
                    host={"mass": 2.1, "radius": 1.8, "temperature": 9000.0})
        self.assertIsNotNone(r["insolation_searth"]["value"])
        self.assertIsNone(r["hz_verdict"]["value"])
        self.assertIn("Kopparapu", r["hz_verdict"]["reason"])

    def test_every_planet_key_carries_a_source_and_never_an_error_key(self):
        for values in (_TAU_E, _TAU_G, {}, {"mass": 0, "radius": 0}):
            for key, entry in _planet(values).items():
                self.assertTrue(entry["source"], key)
                self.assertNotIn("error", entry, key)

    def test_retention_lists_gases_not_an_error_dict(self):
        r = _planet({"mass": 1.0, "radius": 1.0, "temperature": 255.0})
        self.assertIsInstance(r["retention"]["value"], list)
        self.assertTrue(all("status" in g for g in r["retention"]["value"]))
        self.assertGreater(r["escape_velocity_kms"]["value"], 0)


class BinaryStabilityTests(unittest.TestCase):
    def test_alpha_centauri_ab(self):
        r = oec_derived.derive("binary", {
            "components": [{"mass": 1.1}, {"mass": 0.907}],
            "semimajoraxis": 23.518, "eccentricity": 0.5179})
        self.assertAlmostEqual(r["mass_ratio"]["value"], 0.452, places=3)
        self.assertAlmostEqual(r["stype_critical_au"]["value"], 2.795, places=2)
        self.assertIn("catalogued semi-major axis", r["stype_critical_au"]["source"])

    def test_separation_is_selected_by_unit_never_by_position(self):
        """A binary's `separation` repeats in AU and arcsec; taking 'the first'
        would mix the units."""
        r = oec_derived.derive("binary", {
            "components": [{"mass": 1.0}, {"mass": 1.0}],
            "separation_au": 400.0, "separation_arcsec": 80.0})
        self.assertIn("separation (AU)", r["stype_critical_au"]["source"])
        # 0.274 × 400 AU, not × 80
        self.assertAlmostEqual(r["stype_critical_au"]["value"], 0.274 * 400, delta=1)

    def test_the_pair_sma_is_recovered_from_the_period(self):
        """61 Cygni has a period but no `semimajoraxis`."""
        r = oec_derived.derive("binary", {
            "components": [{"mass": 0.7}, {"mass": 0.63}],
            "period": 247634.21, "total_mass": 1.33, "eccentricity": 0.49})
        self.assertIsNotNone(r["stype_critical_au"]["value"])
        self.assertIn("Kepler III", r["stype_critical_au"]["source"])

    def test_an_arcsec_only_separation_is_not_silently_converted(self):
        """arcsec → AU needs the distance and gives a PROJECTED separation, not a."""
        r = oec_derived.derive("binary", {
            "components": [{"mass": 1.0}, {"mass": 1.0}],
            "separation_arcsec": 80.0})
        self.assertIsNone(r["stype_critical_au"]["value"])
        self.assertIn("no semi-major axis", r["stype_critical_au"]["reason"])

    def test_one_mass_is_not_enough(self):
        r = oec_derived.derive("binary", {"components": [{"mass": 1.0}],
                                          "semimajoraxis": 20.0})
        self.assertIsNone(r["stype_critical_au"]["value"])
        self.assertIn("both components", r["stype_critical_au"]["reason"])

    def test_stability_and_hz_do_not_short_circuit_each_other(self):
        """Masses but no temperatures → critical SMAs and no HZ, and vice versa."""
        r = oec_derived.derive("binary", {
            "components": [{"mass": 1.0}, {"mass": 1.0}], "semimajoraxis": 20.0})
        self.assertIsNotNone(r["stype_critical_au"]["value"])
        self.assertIsNone(r["hz_circumbinary"]["value"])
        r2 = oec_derived.derive("binary", {
            "components": [{"radius": 1.0, "temperature": 5778.0},
                           {"radius": 1.0, "temperature": 5778.0}],
            "semimajoraxis": 0.2})
        self.assertIsNotNone(r2["hz_circumbinary"]["value"])
        self.assertIsNone(r2["stype_critical_au"]["value"])


if __name__ == "__main__":
    unittest.main()
