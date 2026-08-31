# tests/test_binary_stability_auto.py — CR-3 auto-pipe binary-orbit → Holman-Wiegert (core).
#
# Offline tests monkeypatch binary.binary_orbit with synthetic solution dicts to exercise the
# tiered element extractor + the stability wiring; one live-gated anchor reproduces the 36 Oph card.

import math
import unittest
from unittest.mock import patch

import core.binary as binary
from tests._netcheck import live_enabled, reachable

_ONLINE = live_enabled() and reachable("simbad.u-strasbg.fr", 443)


def _fake(solutions, sp_type=None, query="X"):
    return {"query": query, "identity": {"sp_type": sp_type, "ra": 1.0, "dec": 2.0},
            "solutions": solutions, "route_tried": ["gaia-nss:two_body_orbit", "sb9", "wds", "orb6"]}


def _run(fake, **kw):
    # CR-14.3: binary_stability_auto now resolves per-component masses through the chain, which does a
    # SIMBAD lookup for the primary/secondary. These are offline stability-math unit tests, so stub the
    # lookup to an offline miss → the chain finds no measured mass → the orbit masses stand (L3 fallback),
    # which is exactly the path these assertions pin. (The catalog-aware chain has its own tests.)
    with patch("core.binary.binary_orbit", return_value=fake), \
         patch("core.databases.compute_simbad_lookup", return_value={"error": "offline (test stub)"}):
        return binary.binary_stability_auto(star="X", **kw)


class ElementExtractionTest(unittest.TestCase):
    def test_tier1_absolute_masses_plus_period(self):
        # M_tot=1.5, P=25.82 yr → a_bin ≈ 10 AU; test 0.5 AU S-type stable.
        p_d = math.sqrt(10.0 ** 3 / 1.5) * 365.25
        sol = {"source": "gaia-nss:two_body_orbit", "period_d": p_d, "eccentricity": 0.0,
               "grade": 50.0, "companion": {"m1_solar": 1.0, "m2_solar": 0.5, "method": "astrom"}}
        d = _run(_fake([sol]), test_sma_au=0.5)
        self.assertAlmostEqual(d["elements"]["sma_au"], 10.0, delta=0.05)
        self.assertEqual(d["elements"]["m2_solar"], 0.5)
        self.assertIn("companion classifier", d["elements"]["mass_basis"])
        self.assertEqual(d["test_verdict"], "stable")
        self.assertFalse(d["e_out_of_hw_range"])

    def test_tier2_sb2_mass_ratio(self):
        sol = {"source": "sb9", "period_d": 400.0, "eccentricity": 0.1, "grade": 4,
               "companion": {"method": "SB2", "mass_ratio_q": 0.8}}
        d = _run(_fake([sol], sp_type="G0V"))
        m1 = binary.m1_from_spectral_type("G0V")
        self.assertAlmostEqual(d["elements"]["m1_solar"], m1)
        self.assertAlmostEqual(d["elements"]["m2_solar"], m1 * 0.8)
        self.assertIn("SB2 mass ratio", d["elements"]["mass_basis"])

    def test_tier3_36oph_like_visual_equal_mass(self):
        # orb6 visual pair, no companion masses; K1V primary; P=471 yr; e=0.92 → the 36 Oph card.
        sol = {"source": "orb6", "period_d": None, "eccentricity": 0.92, "grade": 3,
               "visual_period": 471.0, "visual_period_unit": "y", "separation_arcsec": 4.5}
        d = _run(_fake([sol], sp_type="K1V"), test_sma_au=1.0)
        self.assertAlmostEqual(d["elements"]["m1_solar"], d["elements"]["m2_solar"])   # equal-mass
        self.assertTrue(48.0 <= d["elements"]["sma_au"] <= 75.0)                        # a ≈ 72 AU
        self.assertTrue(0.30 <= d["stype_critical_au"] <= 0.47)                         # S-type crit
        self.assertTrue(202.0 <= d["ptype_critical_au"] <= 316.0)                       # P-type crit
        self.assertEqual(d["test_verdict"], "unstable")                                 # 1 AU unstable
        self.assertTrue(d["e_out_of_hw_range"])                                         # e=0.92 > 0.8
        self.assertIn("equal-mass", d["elements"]["mass_basis"])


class HonestEmptyAndEdgeTest(unittest.TestCase):
    def test_no_solutions_is_honest_empty(self):
        d = _run(_fake([]))
        self.assertIsNone(d["elements"])
        self.assertIn("no orbital solution", d["note"])

    def test_wds_only_no_period_is_honest_empty(self):
        sol = {"source": "wds", "period_d": None, "eccentricity": None,
               "separation_arcsec": 3.0, "separation_au": 20.0, "companion": None}
        d = _run(_fake([sol], sp_type="K1V"))
        self.assertIsNone(d["elements"])
        self.assertIn("masses + period", d["note"])

    def test_test_sma_none_gives_crit_no_verdict(self):
        sol = {"source": "gaia-nss:two_body_orbit", "period_d": 3650.0, "eccentricity": 0.2,
               "companion": {"m1_solar": 1.0, "m2_solar": 0.8, "method": "astrom"}}
        d = _run(_fake([sol]))
        self.assertIsNotNone(d["stype_critical_au"])
        self.assertIsNone(d["test_verdict"])
        self.assertIsNone(d["orbit_type"])

    def test_ecc_assumed_when_absent(self):
        sol = {"source": "orb6", "eccentricity": None, "visual_period": 100.0,
               "visual_period_unit": "y", "companion": None}
        d = _run(_fake([sol], sp_type="G2V"))
        self.assertEqual(d["elements"]["ecc"], 0.0)
        self.assertIn("assumed circular", d["note"])

    def test_bad_test_sma_errors(self):
        self.assertIn("error", binary.binary_stability_auto(star="X", test_sma_au=0))

    def test_binary_orbit_error_propagates(self):
        with patch("core.binary.binary_orbit", return_value={"error": "unresolvable"}):
            self.assertIn("error", binary.binary_stability_auto(star="X"))

    def test_period_unit_conversion(self):
        self.assertAlmostEqual(binary._solution_period_yr(
            {"visual_period": 2.0, "visual_period_unit": "c"}), 200.0)   # centuries
        self.assertAlmostEqual(binary._solution_period_yr(
            {"period_d": 365.25}), 1.0)
        # orb6 'm' is MINUTES, not months: 525960 min = 1 yr.
        self.assertAlmostEqual(binary._solution_period_yr(
            {"visual_period": 525960.0, "visual_period_unit": "m"}), 1.0)


@unittest.skipUnless(_ONLINE, "SIMBAD/VizieR not reachable / SPACE_APP_RUN_LIVE unset")
class BinaryStabilityAutoLiveTest(unittest.TestCase):
    def test_36_ophiuchi_live_honest_null_or_card(self):
        # 36 Oph's visual orbit is NOT in a period-bearing route binary_orbit reaches (only WDS
        # projected separations; it is absent from orb6 even at a 0.2° cone), so the live bare-name
        # path correctly returns an HONEST NULL — find≠fabricate, not the 0.30–0.47 AU anchor. The
        # tier-3 anchor numbers are pinned offline (test_tier3_36oph_like_visual_equal_mass) and by
        # WB's manual binary-stability byte-match. This test accepts either outcome, both correct.
        d = binary.binary_stability_auto(star="36 Ophiuchi", test_sma_au=1.0)
        self.assertNotIn("error", d)
        if d.get("elements") is None:
            self.assertIsNotNone(d.get("note"))               # honest null, not a silent empty
            self.assertIsNone(d["stype_critical_au"])
        else:                                                  # if a period-bearing orbit is ever reached
            self.assertTrue(0.20 <= d["stype_critical_au"] <= 0.55)
            self.assertEqual(d["test_verdict"], "unstable")


class Cr14SharedSelectorTest(unittest.TestCase):
    """CR-14.1/.4 — the shared degenerate-q solution selector (binary.select_stability_elements)."""
    _P = 29174.0

    def _sb2(self, q):
        return {"companion": {"method": "SB2", "mass_ratio_q": q}, "period_d": self._P,
                "eccentricity": 0.52, "source": "sb9", "grade": "a"}

    def _sb1(self, m1, m2):
        return {"companion": {"m1_solar": m1, "m2_solar": m2, "method": "spec-min"},
                "period_d": 18300.0, "eccentricity": 0.59, "source": "sb9", "grade": "a"}

    def _abs(self, m1, m2):
        return {"companion": {"m1_solar": m1, "m2_solar": m2, "method": "astrom"},
                "period_d": 9000.0, "eccentricity": 0.1, "source": "gaia-nss", "grade": 50.0}

    def test_real_ratio_wins_over_degenerate(self):     # CR-14.1
        sel, _ = binary.select_stability_elements([self._sb2(1.0), self._sb2(0.84)], "G2V")
        self.assertAlmostEqual(sel["m2_solar"] / sel["m1_solar"], 0.84, places=5)
        self.assertEqual(sel["mass_prov_b"], "binary_orbit_m2")
        # M3: the selected solution is exposed (real-ratio one), for multiplicity_basis
        self.assertAlmostEqual(sel["selected_solution"]["companion"]["mass_ratio_q"], 0.84)

    def test_clean_astrometric_abs_beats_sb2(self):     # CR-14.4 (b) improvement
        sel, _ = binary.select_stability_elements([self._abs(1.0, 0.5), self._sb2(0.84)], "G2V")
        self.assertAlmostEqual(sel["m2_solar"] / sel["m1_solar"], 0.5, places=5)  # tier-1 abs wins
        self.assertIn("companion classifier", sel["mass_basis"])

    def test_sb1_minimum_still_yields_to_real_sb2(self):  # CR-14.4 preserves CR-13
        sel, _ = binary.select_stability_elements([self._sb1(1.0, 0.5), self._sb2(0.84)], "G2V")
        self.assertAlmostEqual(sel["m2_solar"] / sel["m1_solar"], 0.84, places=5)

    def test_filtered_empty_retry_falls_back_to_full(self):  # M5 retry fallback
        # A lone degenerate solution: pool empties → retry on the full list → still resolves (flagged).
        sel, _ = binary.select_stability_elements([self._sb2(1.0)], "G2V")
        self.assertIsNotNone(sel)
        self.assertEqual(sel["mass_prov_b"], "binary_orbit_equal_split_unresolved")


class Cr14PreferredMassesTest(unittest.TestCase):
    """CR-14.3 — stability_from_solutions honors caller-supplied preferred (chain) masses (pure)."""
    def test_preferred_masses_override_and_recompute_sma(self):
        sol = {"companion": {"method": "SB2", "mass_ratio_q": 0.84}, "period_d": 29174.0,
               "eccentricity": 0.52, "source": "sb9", "grade": "a"}
        base, _ = binary.select_stability_elements([sol], "G2V")
        a0, mt0 = base["sma_au"], base["m1_solar"] + base["m2_solar"]
        stab = binary.stability_from_solutions("X", {"sp_type": "G2V"}, [sol], ["sb9"],
                                               preferred_masses=(1.079, "catalog", 0.909, "catalog", []))
        self.assertAlmostEqual(stab["elements"]["m1_solar"], 1.079)
        self.assertAlmostEqual(stab["elements"]["m2_solar"], 0.909)
        self.assertEqual(stab["elements"]["mass_provenance_a"], "catalog")
        self.assertAlmostEqual(stab["elements"]["sma_au"], a0 * ((1.079 + 0.909) / mt0) ** (1.0 / 3.0),
                               places=6)  # a ∝ M_tot^(1/3) at fixed period (L3)

    def test_no_preferred_masses_is_orbit_behavior(self):
        sol = {"companion": {"method": "SB2", "mass_ratio_q": 0.84}, "period_d": 29174.0,
               "eccentricity": 0.52, "source": "sb9", "grade": "a"}
        stab = binary.stability_from_solutions("X", {"sp_type": "G2V"}, [sol], ["sb9"])
        m1 = binary.m1_from_spectral_type("G2V")
        self.assertAlmostEqual(stab["elements"]["m1_solar"], m1)         # orbit-derived
        self.assertAlmostEqual(stab["elements"]["m2_solar"], m1 * 0.84)


class Cr14ChainWiringTest(unittest.TestCase):
    """CR-14.3 — binary_stability_auto routes per-component masses through the shared chain."""
    def _orbit(self, main_id="* alf Cen", sp="G2V"):
        sol = {"companion": {"method": "SB2", "mass_ratio_q": 0.84}, "period_d": 29174.0,
               "eccentricity": 0.52, "source": "sb9", "grade": "a"}
        return {"query": main_id, "identity": {"sp_type": sp, "main_id": main_id},
                "solutions": [sol], "route_tried": ["sb9"]}

    def test_catalog_mass_supersedes_orbit(self):        # seed has α Cen A/B
        def fake_lookup(name):
            # SIMBAD canonicalises "alpha Cen" → "* alf Cen"; the seed keys on the * alf Cen A/B rows.
            mid = "* alf Cen" if name.lower() in ("alpha cen", "alpha centauri") else name
            return {"main_id": mid, "sp_type": "G2V", "designations": {"MAIN_ID": mid}}
        with patch("core.binary.binary_orbit", return_value=self._orbit()), \
             patch("core.databases.compute_simbad_lookup", side_effect=fake_lookup):
            d = binary.binary_stability_auto(star="alpha Cen")
        self.assertAlmostEqual(d["elements"]["m1_solar"], 1.079)
        self.assertAlmostEqual(d["elements"]["m2_solar"], 0.909)
        self.assertEqual(d["elements"]["mass_provenance_a"], "catalog")
        self.assertEqual(d["elements"]["mass_provenance_b"], "catalog")

    def test_flame_tier_for_noncatalog_primary(self):    # CR-14.3 #4 generality
        def fake_lookup(name):
            return {"main_id": name, "sp_type": "G0V",
                    "designations": {"MAIN_ID": name, "Gaia EDR3": "12345"}}
        def fake_gaia(source_id=None):
            return {"parameters": {"mass_flame": 1.2}}
        with patch("core.binary.binary_orbit", return_value=self._orbit("HD 999999", "G0V")), \
             patch("core.databases.compute_simbad_lookup", side_effect=fake_lookup), \
             patch("core.catalog.gaia_astrophysical", side_effect=fake_gaia):
            d = binary.binary_stability_auto(star="HD 999999")
        self.assertEqual(d["elements"]["mass_provenance_a"], "gaia_flame")
        self.assertAlmostEqual(d["elements"]["m1_solar"], 1.2)

    def test_bad_catalog_path_is_curated_error(self):    # L6 loud bad-path
        d = binary.binary_stability_auto(star="X", star_mass_catalog="/no/such/catalog.json")
        self.assertIn("error", d)


class Cr14BinaryOrbitMarkerTest(unittest.TestCase):
    """CR-14.1 Q3=(a) — binary_orbit marks (never drops/reorders) a degenerate q≈1.0 solution."""
    def test_degenerate_solution_marked(self):
        deg = {"companion": {"method": "SB2", "mass_ratio_q": 1.0}, "period_d": 29650.0,
               "eccentricity": 0.53, "source": "sb9", "grade": "a"}
        real = {"companion": {"method": "SB2", "mass_ratio_q": 0.84}, "period_d": 29174.0,
                "eccentricity": 0.52, "source": "sb9", "grade": "a"}
        ident = {"ra": 1.0, "dec": 2.0, "sp_type": "G2V", "gaia_source_id": None,
                 "parallax_mas": None, "main_id": "X"}
        with patch("core.binary._resolve_binary_identity", return_value=(ident, None)), \
             patch("core.binary._sb9_solutions", return_value=([deg, real], None)), \
             patch("core.binary._wds_orb6_solutions", return_value=[]):
            r = binary.binary_orbit(star="X")
        self.assertTrue(r["solutions"][0].get("degenerate"))      # marked
        self.assertIsNone(r["solutions"][1].get("degenerate"))    # real one not marked
        self.assertEqual(len(r["solutions"]), 2)                  # neither dropped nor reordered


class Cr16TriggerTest(unittest.TestCase):
    """CR-16: the degenerate-secondary → primary-identity redirect trigger + helpers (pure, offline)."""

    def test_fires_for_degenerate_wd_secondary(self):
        for mid, sp in [("* alf CMa B", "DA1.9"), ("* alf CMi B", "DQZ"), ("* xyz B", "")]:
            self.assertTrue(binary._secondary_needs_primary_sp({"main_id": mid, "sp_type": sp}),
                            f"{mid}/{sp} should fire")

    def test_does_not_fire_for_ms_secondary_or_primary(self):
        # α Cen B (MS secondary), α Cen A (trailing A excluded), Sirius primary (no letter), Proxima (MS).
        # This is the OFFLINE guard that the frozen CR-13 exclusion + CR-14 α Cen anchors never get
        # redirected (exclusion's own α Cen A/B queries flow through binary_orbit; the gate protects them).
        for mid, sp in [("* alf Cen B", "K1V"), ("* alf Cen A", "G2V"),
                        ("* alf CMa", "A0mA1Va"), ("* alf Cen C", "M5.5V")]:
            self.assertFalse(binary._secondary_needs_primary_sp({"main_id": mid, "sp_type": sp}),
                             f"{mid}/{sp} must NOT fire")

    def test_parse_spectral_class_tuple_truthiness_guard(self):
        # _parse_spectral_class returns an ALWAYS-truthy 2-tuple; the trigger must test [0], never the tuple.
        self.assertIsNone(binary._parse_spectral_class("DA1.9")[0])
        self.assertIsNone(binary._parse_spectral_class("")[0])
        self.assertIsNotNone(binary._parse_spectral_class("K1V")[0])

    def test_is_secondary_component_and_strip_whitespace_safe(self):
        self.assertTrue(binary._is_secondary_component("* alf CMa B"))
        self.assertFalse(binary._is_secondary_component("* alf Cen A"))    # A excluded
        self.assertFalse(binary._is_secondary_component("* alf CMa"))
        # the strip must run on the .strip()ed id (a trailing space would defeat the $-anchor)
        self.assertEqual(binary._SECONDARY_RE.sub("", "* alf CMa B ".strip()), "* alf CMa")

    def test_redirected_primary_helper(self):
        self.assertEqual(binary.redirected_primary({"main_id": "x"}), (None, None, None))
        self.assertEqual(binary.redirected_primary(None), (None, None, None))
        prim = {"main_id": "* alf CMa", "sp_type": "A0mA1Va", "designations": {"HD": "HD 48915A"}}
        self.assertEqual(binary.redirected_primary({"primary": prim}), ("A0mA1Va", prim, "* alf CMa"))


class Cr16BinaryOrbitRedirectTest(unittest.TestCase):
    """CR-16 change A: binary_orbit resolves the primary for a degenerate secondary + uses its sp-type."""

    def _lookup(self, sec, pri):
        def fn(name):
            if name in ("Sirius B", sec["main_id"]):
                return sec
            if name == pri["main_id"]:
                return pri
            return {"error": "not-in-test"}
        return fn

    def test_wd_secondary_redirects_and_threads_primary_sp(self):
        cap = {}
        sec = {"main_id": "* alf CMa B", "sp_type": "DA1.9", "ra": 101.3, "dec": -16.7,
               "designations": {"MAIN_ID": "* alf CMa B"}, "plx_value": 374.0}
        pri = {"main_id": "* alf CMa", "sp_type": "A0mA1Va", "ra": 101.3, "dec": -16.7,
               "designations": {"MAIN_ID": "* alf CMa", "HD": "HD 48915A"}, "plx_value": 374.0}
        with patch("core.databases.compute_simbad_lookup", side_effect=self._lookup(sec, pri)), \
             patch("core.binary._sb9_solutions",
                   side_effect=lambda ra, dec, sp: (cap.__setitem__("sb9_sp", sp) or ([], None))), \
             patch("core.binary._nss_two_body_solutions", return_value=([], None)), \
             patch("core.binary._wds_orb6_solutions", return_value=[]):
            res = binary.binary_orbit(star="Sirius B")
        self.assertEqual(res["query"], "Sirius B")                          # query echo preserved
        self.assertEqual(res["identity"]["main_id"], "* alf CMa B")         # identity echo = secondary
        self.assertEqual(res["identity"]["primary"]["main_id"], "* alf CMa")
        self.assertEqual(res["identity"]["mass_resolved_via_primary"], "* alf CMa")
        self.assertEqual(cap["sb9_sp"], "A0mA1Va")                          # PRIMARY sp fed to companion mass

    def test_ms_secondary_no_redirect_and_no_extra_lookup(self):
        cap = {}
        sec = {"main_id": "* alf Cen B", "sp_type": "K1V", "ra": 219.9, "dec": -60.8,
               "designations": {"MAIN_ID": "* alf Cen B"}, "plx_value": 747.0}
        with patch("core.databases.compute_simbad_lookup",
                   return_value=sec) as m, \
             patch("core.binary._sb9_solutions",
                   side_effect=lambda ra, dec, sp: (cap.__setitem__("sb9_sp", sp) or ([], None))), \
             patch("core.binary._nss_two_body_solutions", return_value=([], None)), \
             patch("core.binary._wds_orb6_solutions", return_value=[]):
            res = binary.binary_orbit(star="alpha Cen B")
        self.assertNotIn("primary", res["identity"])          # no redirect
        self.assertEqual(cap["sb9_sp"], "K1V")                # queried sp used, unchanged
        self.assertEqual(m.call_count, 1)                     # only the queried lookup — no bare re-lookup


class Cr16StabilityAutoConsumeTest(unittest.TestCase):
    """CR-16 change B: binary_stability_auto consumes ident.primary → slot A = primary, slot B = secondary."""

    def test_redirected_primary_resolves_slot_a_from_catalog(self):
        # A binary_orbit result as change A would produce it: identity.primary attached, and the SB9
        # spec-min companion already computed at the PRIMARY sp (m1=2.18, m2=0.4577). No --star-mass-catalog
        # → the seed carries Sirius A (* alf CMa → 2.063) but NOT Sirius B, so slot A→catalog, slot B→orbit.
        p_d = 18276.7
        sol = {"source": "sb9", "period_d": p_d, "eccentricity": 0.59, "grade": 5,
               "companion": {"m1_solar": 2.18, "m2_solar": 0.4577, "method": "spec-min"}}
        fake = {"query": "Sirius B", "route_tried": ["sb9"], "solutions": [sol],
                "identity": {"main_id": "* alf CMa B", "sp_type": "DA1.9", "ra": 101.3, "dec": -16.7,
                             "designations": {"MAIN_ID": "* alf CMa B"},
                             "primary": {"main_id": "* alf CMa", "sp_type": "A0mA1Va",
                                         "designations": {"MAIN_ID": "* alf CMa", "HD": "HD 48915A"}}}}
        with patch("core.binary.binary_orbit", return_value=fake), \
             patch("core.databases.compute_simbad_lookup", return_value={"error": "offline"}):
            d = binary.binary_stability_auto(star="Sirius B")
        self.assertEqual(d["elements"]["m1_solar"], 2.063)                     # slot A → seed catalog primary
        self.assertEqual(d["elements"]["mass_provenance_a"], "catalog")
        self.assertAlmostEqual(d["elements"]["m2_solar"], 0.4577, places=4)    # slot B → orbit secondary
        self.assertEqual(d["mass_resolved_via_primary"], "* alf CMa")          # CR-16 transparency marker

    def test_absent_primary_is_unchanged(self):
        # No identity.primary (letter-symmetric / primary-named) → the CR-15.4 path, no new marker.
        sol = {"source": "sb9", "period_d": 400.0, "eccentricity": 0.1, "grade": 4,
               "companion": {"method": "SB2", "mass_ratio_q": 0.8}}
        with patch("core.binary.binary_orbit",
                   return_value=_fake([sol], sp_type="G0V", query="X")), \
             patch("core.databases.compute_simbad_lookup", return_value={"error": "offline"}):
            d = binary.binary_stability_auto(star="X")
        self.assertNotIn("mass_resolved_via_primary", d)


if __name__ == "__main__":
    unittest.main()
