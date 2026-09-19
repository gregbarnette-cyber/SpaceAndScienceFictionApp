"""CR-22 — two-layer exclusion boundary (standoff + research-grade physical WALL).

Step-1 (CP1) battery: the pure-math wall engine + the four-value domain/wind classifier in
``core.exclusion_wall``. Later CR-22 steps add single-body (exclusion-boundary) and multi-star
(exclusion-system) integration tests. Research-grade wall values are checked with banded tolerances;
classifier mappings are exact. See PHASE_CR22_PLAN.md.
"""

import math
import unittest

from core import exclusion_wall as ew
from core import exclusion_boundary as xb
from core import exclusion_system as es

_LY_AU = 63241.077     # AU per light-year (for ly-scale wall assertions)


class WallPhysicsTest(unittest.TestCase):
    """compute_wall — the route/band/cap physics against the spec's validation anchors."""

    def test_sol_bow_wave(self):
        # --object sun: Ẇ 2e-14, v 400, V_ISM 26, c_ms 20 → M_f 1.3 < 1.5 → bow wave, wall 4–8 (mid 6).
        w = ew.compute_wall(2e-14, 400.0, v_ism=26.0, c_ms=20.0, n_cloud=0.1, r_ex=47.5,
                            wind_class="solar", t_phase=None)
        self.assertEqual(w["wall_route"], "wind_term")
        self.assertAlmostEqual(w["wall_band_au"][0], 4.0, places=6)
        self.assertAlmostEqual(w["wall_band_au"][1], 8.0, places=6)
        self.assertAlmostEqual(w["wall_au"], 6.0, places=6)
        self.assertAlmostEqual(w["r_ap_au"], 120.0, places=6)   # the heliopause anchor reproduces
        self.assertTrue(w["verdict_marginal"])                  # M_f 1.156–1.857 straddles 1.5
        self.assertIn("research-grade", w["wall_note"])
        # hazard: 8 < 47.5 → does not exceed the standoff
        exceeds, ratio = ew.hazard_flags(w["wall_band_au"][1], w["wall_au"], 47.5)
        self.assertFalse(exceeds)
        self.assertAlmostEqual(ratio, 6.0 / 47.5, places=6)

    def test_barnards_apex_inside_standoff(self):
        # M4V quiet, high V_ISM 121: a shock exists (M_f=6) but r_ap≪r_ex → wind term stands, wall ≲1.
        w = ew.compute_wall(1e-16, 400.0, v_ism=121.0, c_ms=20.0, r_ex=22.8, wind_class="quiet")
        self.assertEqual(w["wall_route"], "wind_term")
        self.assertLess(w["wall_au"], 1.0)

    def test_ev_lac_bow_shock(self):
        # moderate binder: M_f 2.25 ≥ 1.5, r_ap 69.3 > r_ex 30.1 → bow shock, wall ≈ 2.5–5.0.
        w = ew.compute_wall(2e-14, 400.0, v_ism=45.0, c_ms=20.0, r_ex=30.1, wind_class="active")
        self.assertEqual(w["wall_route"], "bow_shock")
        self.assertGreater(w["r_ap_au"], 30.1)
        self.assertTrue(2.4 <= w["wall_band_au"][0] and w["wall_band_au"][1] <= 5.2)

    def test_epsilon_oph_giant_mild_oort_uncapped(self):
        # G-giant: wind term ~566–1131 AU (Oort-scale) < r_ap ~4243 → NOT capped, exceeds standoff.
        wdot, v, tph, _src = ew.wind_row_for("giant_mild")
        w = ew.compute_wall(wdot, v, v_ism=26.0, c_ms=20.0, r_ex=61.0, wind_class="giant_mild",
                            t_phase=tph)
        self.assertEqual(w["wall_route"], "wind_term")
        self.assertTrue(500 < w["wall_band_au"][0] < 700)
        self.assertTrue(1000 < w["wall_band_au"][1] < 1200)
        self.assertGreater(w["r_ap_au"], w["wall_band_au"][1])   # r_ap clears the wall → no cap
        exceeds, _ = ew.hazard_flags(w["wall_band_au"][1], w["wall_au"], 61.0)
        self.assertTrue(exceeds)                                 # Oort wall ≫ 61 AU standoff

    def test_37_oph_m_giant_capped_astropause(self):
        # M2III: wind term ~46k–92k AU overshoots r_ap ~52k → capped at r_ap ≈ 0.8 ly.
        wdot, v, tph, _src = ew.wind_row_for("giant_overwindy", "M2III")
        w = ew.compute_wall(wdot, v, v_ism=26.0, c_ms=20.0, r_ex=56.0, wind_class="giant_overwindy",
                            t_phase=tph)
        self.assertEqual(w["wall_route"], "capped_astropause")
        self.assertAlmostEqual(w["wall_band_au"][1], w["r_ap_au"], places=3)   # capped at r_ap
        self.assertAlmostEqual(w["wall_band_au"][1] / _LY_AU, 0.82, delta=0.1)  # ~0.8 ly

    def test_rsg_capped_few_ly(self):
        wdot, v, tph, _src = ew.wind_row_for("rsg_overwindy")
        w = ew.compute_wall(wdot, v, v_ism=26.0, c_ms=20.0, r_ex=60.0, wind_class="rsg_overwindy",
                            t_phase=tph)
        self.assertEqual(w["wall_route"], "capped_astropause")
        self.assertAlmostEqual(w["wall_band_au"][1] / _LY_AU, 4.24, delta=0.5)  # ~4 ly cap (r_ap)

    def test_wind_speed_scales_as_inverse_sqrt(self):
        # identical Ẇ, v_wind 15 vs 1500, low V_ISM so neither caps → walls differ by √100 = 10×.
        slow = ew.compute_wall(1e-13, 15.0, v_ism=5.0, c_ms=20.0, r_ex=None, t_phase=None)
        fast = ew.compute_wall(1e-13, 1500.0, v_ism=5.0, c_ms=20.0, r_ex=None, t_phase=None)
        self.assertEqual(slow["wall_route"], "wind_term")
        self.assertEqual(fast["wall_route"], "wind_term")
        self.assertAlmostEqual(slow["wall_au"] / fast["wall_au"], 10.0, places=4)

    def test_wind_time_cap_unit_conversion(self):
        # a short user t_phase (below the r_ap/v_wind crossover) makes the wind-time bound bind.
        w = ew.compute_wall(1e-7, 15.0, v_ism=26.0, c_ms=20.0, r_ex=56.0,
                            wind_class="giant_overwindy", t_phase=1.0e4)
        self.assertEqual(w["wall_route"], "capped_windtime")
        expect_au = (15.0 * 1000.0 * 1.0e4 * 3.15576e7) / 149_597_870_700.0
        self.assertAlmostEqual(w["wall_band_au"][1], expect_au, places=2)

    def test_none_no_wind(self):
        w = ew.compute_wall(0.0, 400.0)
        self.assertIsNone(w["wall_au"])
        self.assertEqual(w["wall_route"], "none_no_wind")
        self.assertIn("research-grade", w["wall_note"])


class CmsFromBFieldTest(unittest.TestCase):
    def test_anchor_20(self):
        c_ms, band = ew.c_ms_from_bfield(3.0, 0.095, 6300.0)
        self.assertTrue(18.0 <= c_ms <= 23.0)   # v_A≈18, c_s≈12 → c_ms≈20–22 (spec 20±2)
        self.assertEqual(len(band), 2)

    def test_bad_inputs(self):
        self.assertEqual(ew.c_ms_from_bfield(0, 0.1, 6300), (None, None))


class WindRowTest(unittest.TestCase):
    def test_giant_overwindy_colour_split(self):
        self.assertEqual(ew.wind_row_for("giant_overwindy", "K0III")[:2], (1e-9, 30.0))
        self.assertEqual(ew.wind_row_for("giant_overwindy", "M2III")[:2], (1e-7, 15.0))
        self.assertEqual(ew.wind_row_for("giant_overwindy", None)[:2], (1e-7, 15.0))  # conservative

    def test_named_rows_and_none(self):
        self.assertEqual(ew.wind_row_for("solar"), (2e-14, 400.0, None, "astrosphere_wood"))
        self.assertIsNone(ew.wind_row_for(None))
        self.assertIsNone(ew.wind_row_for("windless_free_harbor"))


class ClassifierMainSequenceTest(unittest.TestCase):
    def test_v_by_colour(self):
        for sp, wc in [("O5V", "o_hot"), ("B2V", "b_hot"), ("A0V", "a_dwarf"),
                       ("F5V", "f_dwarf"), ("G2V", "solar"), ("K3V", "quiet"), ("M4V", "quiet")]:
            dom, w, _n = ew.classify_domain_wind(sp_type=sp)
            self.assertEqual((dom, w), (ew.MAIN_SEQUENCE, wc), sp)

    def test_km_active_upgrade(self):
        self.assertEqual(ew.classify_domain_wind(sp_type="M4V", wind_state="active")[1], "active")
        self.assertEqual(ew.classify_domain_wind(sp_type="K5V", otype="Flare Star")[1], "active")

    def test_bare_mass_no_colour(self):
        dom, w, _n = ew.classify_domain_wind(class_tag="dwarf")
        self.assertEqual(dom, ew.MAIN_SEQUENCE)
        self.assertIsNone(w)     # no colour → no wall (none_no_wind downstream)


class ClassifierEvolvedTest(unittest.TestCase):
    def test_subgiant_and_ob_exception(self):
        self.assertEqual(ew.classify_domain_wind(sp_type="G8IV")[:2], (ew.EVOLVED, "subgiant_mild"))
        self.assertEqual(ew.classify_domain_wind(sp_type="F5IV-V")[:2], (ew.EVOLVED, "subgiant_mild"))
        self.assertEqual(ew.classify_domain_wind(sp_type="B3IV")[:2], (ew.EVOLVED, "b_hot"))   # table wins
        self.assertEqual(ew.classify_domain_wind(sp_type="O7IV")[:2], (ew.EVOLVED, "o_hot"))

    def test_giants_by_colour(self):
        self.assertEqual(ew.classify_domain_wind(sp_type="G9.5IIIb")[:2], (ew.EVOLVED, "giant_mild"))
        self.assertEqual(ew.classify_domain_wind(sp_type="F0III")[:2], (ew.EVOLVED, "giant_mild"))
        self.assertEqual(ew.classify_domain_wind(sp_type="K0III")[:2], (ew.EVOLVED, "giant_overwindy"))
        self.assertEqual(ew.classify_domain_wind(sp_type="M2III")[:2], (ew.EVOLVED, "giant_overwindy"))

    def test_supergiants(self):
        self.assertEqual(ew.classify_domain_wind(sp_type="B0Ia")[:2], (ew.EVOLVED, "bsg_overwindy"))
        self.assertEqual(ew.classify_domain_wind(sp_type="G2Iab")[:2], (ew.EVOLVED, "bsg_overwindy"))
        self.assertEqual(ew.classify_domain_wind(sp_type="M2Iab")[:2], (ew.EVOLVED, "rsg_overwindy"))
        self.assertEqual(ew.classify_domain_wind(sp_type="K5Ia")[:2], (ew.EVOLVED, "rsg_overwindy"))

    def test_wr_and_agb_via_otype(self):
        self.assertEqual(ew.classify_domain_wind(otype="Wolf-Rayet")[:2], (ew.EVOLVED, "wr_overwindy"))
        self.assertEqual(ew.classify_domain_wind(sp_type="M7III", otype="Mira Cet type")[:2],
                         (ew.EVOLVED, "agb_overwindy"))

    def test_coarse_component_tags(self):
        self.assertEqual(ew.classify_domain_wind(class_tag="giant")[:2],
                         (ew.EVOLVED, "giant_overwindy"))     # bare giant → conservative
        self.assertEqual(ew.classify_domain_wind(class_tag="subgiant")[:2],
                         (ew.EVOLVED, "subgiant_mild"))
        self.assertEqual(ew.classify_domain_wind(class_tag="supergiant")[:2],
                         (ew.EVOLVED, "rsg_overwindy"))
        self.assertEqual(ew.classify_domain_wind(class_tag="agb")[:2], (ew.EVOLVED, "agb_overwindy"))
        self.assertEqual(ew.classify_domain_wind(class_tag="wolf-rayet")[:2],
                         (ew.EVOLVED, "wr_overwindy"))

    def test_explicit_wind_class(self):
        self.assertEqual(ew.classify_domain_wind(wind_class="giant_overwindy")[:2],
                         (ew.EVOLVED, "giant_overwindy"))
        self.assertEqual(ew.classify_domain_wind(wind_class="solar")[:2], (ew.MAIN_SEQUENCE, "solar"))


class ClassifierWindlessAndUnmodeledTest(unittest.TestCase):
    def test_windless(self):
        for kw in (dict(object_name="brown-dwarf"), dict(object_name="rogue-planet"),
                   dict(class_tag="wd"), dict(class_tag="brown-dwarf"),
                   dict(sp_type="DA2"), dict(sp_type="T5"), dict(sp_type="L3")):
            dom, w, note = ew.classify_domain_wind(**kw)
            self.assertEqual(dom, ew.WINDLESS, kw)
            self.assertIsNone(w)
            self.assertIn("free harbor", note)

    def test_hot_subdwarf_unmodeled(self):
        for sp in ("sdB", "sdO", "sdB1", "sdO2VII"):   # hot subdwarfs → honest null, NOT windless
            dom, w, note = ew.classify_domain_wind(sp_type=sp)
            self.assertEqual((dom, w), (ew.UNMODELED, None), sp)
            self.assertIn("hot subdwarf", note)

    def test_cool_subdwarf_is_main_sequence(self):
        # lum-VI cool subdwarf → a metal-poor MS fusing star with a wind (WB MSG 242 Item 2)
        dom, w, note = ew.classify_domain_wind(sp_type="M1VI")
        self.assertEqual(dom, ew.MAIN_SEQUENCE)
        self.assertEqual(w, "quiet")
        self.assertEqual(note, "cool subdwarf")

    def test_sd_prefix_cool_dwarf_stays_ms(self):
        # sd/esd/usd cool subdwarf (no roman lum class) → main_sequence + the colour wind_class, PLUS
        # the "cool subdwarf" class_note (WB MSG 244 — consistent with the M1VI form + --star path).
        for sp, wc in [("sdM3.0", "quiet"), ("sdK5", "quiet"), ("sdG2", "solar"),
                       ("esdM1", "quiet"), ("usdK7", "quiet")]:
            dom, w, note = ew.classify_domain_wind(sp_type=sp)
            self.assertEqual((dom, w, note), (ew.MAIN_SEQUENCE, wc, "cool subdwarf"), sp)
        # a plain dwarf prefix (d, not sd) is NOT a subdwarf → no note
        self.assertIsNone(ew.classify_domain_wind(sp_type="dM6")[2])


class Cp1FixTest(unittest.TestCase):
    """Regressions for the CP1 /code-review findings."""

    def test_wr_and_carbon_from_sptype_without_otype(self):
        # CP1-2: the most extreme wind drivers must not fall through to MS/none_no_wind.
        self.assertEqual(ew.classify_domain_wind(sp_type="WN5")[:2], (ew.EVOLVED, "wr_overwindy"))
        self.assertEqual(ew.classify_domain_wind(sp_type="WC6")[:2], (ew.EVOLVED, "wr_overwindy"))
        self.assertEqual(ew.classify_domain_wind(sp_type="C-N5")[:2], (ew.EVOLVED, "agb_overwindy"))

    def test_compute_wall_guards_bad_medium_inputs(self):
        # CP1-3: composing with c_ms_from_bfield's (None,None) failure must not crash.
        c_ms, _band = ew.c_ms_from_bfield(0, 0.1, 6300)      # -> (None, None)
        w = ew.compute_wall(1e-14, 400.0, v_ism=26.0, c_ms=c_ms, n_cloud=0.1)
        self.assertIsNone(w["wall_au"])
        self.assertEqual(w["wall_route"], "none_no_wind")
        self.assertEqual(ew.compute_wall(1e-14, 400.0, n_cloud=0.0)["wall_route"], "none_no_wind")
        self.assertEqual(ew.compute_wall(1e-14, 400.0, v_ism=0.0)["wall_route"], "none_no_wind")

    def test_explicit_wind_class_keeps_identity_domain(self):
        # CP1-1: an explicit wind_class overrides the ROW but the domain still comes from sp_type.
        dom, w, _n = ew.classify_domain_wind(sp_type="B3IV", wind_class="quiet")
        self.assertEqual((dom, w), (ew.EVOLVED, "quiet"))
        # a bare o_hot with no identity defaults to main_sequence (documented)
        self.assertEqual(ew.classify_domain_wind(wind_class="o_hot")[:2], (ew.MAIN_SEQUENCE, "o_hot"))
        # ...but an O subgiant with its sp_type re-classifies evolved
        self.assertEqual(ew.classify_domain_wind(sp_type="O7IV")[:2], (ew.EVOLVED, "o_hot"))

    def test_uv_variable_otype_upgrades_to_active(self):
        # CP1-4: SIMBAD's UV-variable short otype is 'UV*'.
        self.assertEqual(ew.classify_domain_wind(sp_type="M3V", otype="UV*")[1], "active")

    def test_verdict_marginal_not_flagged_for_committed_offband_cms(self):
        # CP1-7: a user-committed c_ms outside the LIC band does not get the band-straddle flag.
        w = ew.compute_wall(2e-14, 400.0, v_ism=26.0, c_ms=35.0, r_ex=47.5, wind_class="solar")
        self.assertFalse(w["verdict_marginal"])


class TwoLayerSingleBodyTest(unittest.TestCase):
    """compute_two_layer_boundary — the single-body orchestrator (offline; no network)."""

    def test_standoff_byte_identical_to_frozen(self):
        # the two-layer standoff must equal the FROZEN generator's r_ex for every mass.
        for m in (1.0, 0.1, 2.063, 10.0):
            two = xb.compute_two_layer_boundary(mass_msun=m, sp_type="G2V", alpha=0.4)
            frozen = xb.compute_exclusion_boundary(mass_msun=m, alpha=0.4)
            self.assertAlmostEqual(two["standoff_au"], frozen["r_ex_au"], places=9, msg=m)
            self.assertEqual(two["r_ex_au"], frozen["r_ex_au"])

    def test_ms_gets_wall(self):
        r = xb.compute_two_layer_boundary(mass_msun=1.0, sp_type="G2V", alpha=0.4)
        self.assertEqual((r["domain"], r["wind_class"]), (ew.MAIN_SEQUENCE, "solar"))
        self.assertAlmostEqual(r["standoff_au"], 47.5, places=6)
        self.assertAlmostEqual(r["wall_au"], 6.0, places=6)
        self.assertFalse(r["wall_exceeds_standoff"])
        self.assertNotIn("standoff_note", r)              # MS carries no out-of-domain note

    def test_windless_free_harbor(self):
        r = xb.compute_two_layer_boundary(class_tag="wd", alpha=0.4)
        self.assertEqual(r["domain"], ew.WINDLESS)
        self.assertIsNone(r["standoff_au"])
        self.assertIsNone(r["r_ex_au"])
        self.assertEqual(r["forcing_class"], "free_harbor")
        self.assertEqual(r["wall_route"], "none_windless")

    def test_hot_subdwarf_unmodeled(self):
        r = xb.compute_two_layer_boundary(sp_type="sdB", alpha=0.4)
        self.assertEqual(r["domain"], ew.UNMODELED)
        self.assertIsNone(r["standoff_au"])
        self.assertEqual(r["wall_route"], "none_unmodeled")
        self.assertIn("hot subdwarf", r["wall_reason"])

    def test_evolved_subgiant_with_measured_mass(self):
        # δ Pav (G8IV, 0.991 M☉) → evolved/subgiant_mild, standoff ≈ 47.3 + note, wall ~7–14, not exceeding.
        r = xb.compute_two_layer_boundary(mass_msun=0.991, sp_type="G8IV", alpha=0.4,
                                          mass_provenance="catalog")
        self.assertEqual((r["domain"], r["wind_class"]), (ew.EVOLVED, "subgiant_mild"))
        self.assertAlmostEqual(r["standoff_au"], 47.5 * 0.991 ** 0.4, places=4)
        self.assertIn("outside its canon MS domain", r["standoff_note"])
        self.assertEqual(r["mass_provenance"], "catalog")
        self.assertFalse(r["wall_exceeds_standoff"])       # subgiant wall stays inside the standoff

    def test_evolved_giant_exceeds_standoff(self):
        # ε Oph (G9.5IIIb, 1.85 M☉) → evolved/giant_mild, standoff ≈ 60.8, Oort wall exceeds the standoff.
        r = xb.compute_two_layer_boundary(mass_msun=1.85, sp_type="G9.5IIIb", alpha=0.4)
        self.assertEqual((r["domain"], r["wind_class"]), (ew.EVOLVED, "giant_mild"))
        self.assertAlmostEqual(r["standoff_au"], 47.5 * 1.85 ** 0.4, places=3)
        self.assertTrue(r["wall_exceeds_standoff"])
        self.assertGreater(r["wall_to_standoff_ratio"], 1.0)

    def test_evolved_m_giant_capped(self):
        # 37 Oph (M2III, 1.5 M☉ estimate) → evolved/giant_overwindy, capped ly-scale wall.
        r = xb.compute_two_layer_boundary(mass_msun=1.5, sp_type="M2III", alpha=0.4)
        self.assertEqual((r["domain"], r["wind_class"]), (ew.EVOLVED, "giant_overwindy"))
        self.assertAlmostEqual(r["standoff_au"], 47.5 * 1.5 ** 0.4, places=3)
        self.assertEqual(r["wall_route"], "capped_astropause")
        self.assertTrue(r["wall_exceeds_standoff"])

    def test_evolved_no_mass_emits_wall_no_standoff(self):
        # v_ism 45 → M_f 2.25 ≥ 1.5, so a shock could exist but there is no standoff to test it against.
        r = xb.compute_two_layer_boundary(sp_type="G8IV", v_ism=45.0, alpha=0.4)   # no mass
        self.assertEqual(r["domain"], ew.EVOLVED)
        self.assertIsNone(r["standoff_au"])
        self.assertIn("no measured mass", r["standoff_note"])
        self.assertIsNotNone(r["wall_au"])                  # mass-free wind-term wall still emitted
        self.assertIn("untested", r["wall_reason"])         # bow-shock binding untested (no standoff)

    def test_wind_input_echoes_and_provenance(self):
        r = xb.compute_two_layer_boundary(mass_msun=1.0, sp_type="G2V", alpha=0.4)
        self.assertEqual(r["v_ism_kms"], 26.0)
        self.assertEqual(r["v_ism_provenance"], "assumed")
        self.assertEqual(r["c_ms_kms"], 20.0)
        self.assertEqual(r["c_ms_provenance"], "assumed")
        self.assertEqual(r["wind_speed_provenance"], "astrosphere_wood_forced")  # solar preset forces 400
        self.assertEqual(r["wind_speed_kms"], 400.0)

    def test_astrosphere_wood_double_handling(self):
        # supplied --wind-speed 800 is IGNORED when mass_loss_source=astrosphere_wood (forces 400).
        r = xb.compute_two_layer_boundary(mass_msun=1.0, sp_type="G2V", alpha=0.4,
                                          mass_loss_msun_yr=8e-13, wind_speed=800.0,
                                          mass_loss_source="astrosphere_wood")
        self.assertEqual(r["wind_speed_kms"], 400.0)
        self.assertEqual(r["wind_speed_provenance"], "astrosphere_wood_forced")

    def test_frozen_error_propagates(self):
        r = xb.compute_two_layer_boundary(mass_msun=1.0, sp_type="G2V", alpha=-0.5)
        self.assertIn("error", r)


class Cp2FixTest(unittest.TestCase):
    """Regressions for the CP2 /code-review findings."""

    def test_gamma_standoff_needs_a_wdot(self):
        # CP2-1: with --gamma set, the standoff needs a W-dot; query.py now feeds the object preset's.
        ok = xb.compute_two_layer_boundary(mass_msun=20.0, wind_class="o_hot", alpha=0.4,
                                           gamma=0.5, mass_loss_msun_yr=1e-6)
        self.assertNotIn("error", ok)
        self.assertGreater(ok["standoff_au"], 0)
        err = xb.compute_two_layer_boundary(mass_msun=20.0, wind_class="o_hot", alpha=0.4, gamma=0.5)
        self.assertIn("error", err)                    # no W-dot → the frozen gamma guard fires

    def test_wind_state_drives_the_wall_consistently(self):
        # CP2-2: a bare --wind-state (no sp_type) now yields a wall + a matching W-dot echo.
        r = xb.compute_two_layer_boundary(mass_msun=1.0, wind_state="active", alpha=0.4)
        self.assertEqual(r["wind_class"], "active")
        self.assertIsNotNone(r["wall_au"])
        self.assertEqual(r["mass_loss_msun_yr"], 1e-13)   # active row Ẇ, echoed (not None)

    def test_supplied_wdot_without_windspeed_still_gets_a_wall(self):
        # CP2-4: an explicit Ẇ with no wind_class/wind-speed assumes v_wind=400 rather than dropping it.
        r = xb.compute_two_layer_boundary(mass_msun=1.0, mass_loss_msun_yr=1e-13, alpha=0.4)
        self.assertIsNotNone(r["wall_au"])
        self.assertEqual(r["wind_speed_kms"], 400.0)
        self.assertEqual(r["wind_speed_provenance"], "assumed")

    def test_evolved_no_mass_note_keeps_resolver_hint(self):
        # CP2-6: the resolver's specific mass hint is preserved, not replaced by the generic note.
        r = xb.compute_two_layer_boundary(sp_type="G8IV", mass_note="give mass=… or a catalog row",
                                          alpha=0.4)
        self.assertIn("no measured mass", r["standoff_note"])
        self.assertIn("give mass", r["standoff_note"])


class Cr225MultiStarWallTest(unittest.TestCase):
    """CR-22.5 multi-star wall merge — wall_zones, combined-wind, phase-eligibility, mixed-domain
    (compose-level, offline; the PINNED Wood 2005 Ṁ passed explicitly per component, overriding the
    class default — the 'measured overrides' rule)."""

    def _zone_for(self, wall_zones, member):
        return next((z for z in wall_zones if member in z["members"]), None)

    def test_alpha_cen_envelope_peri_only(self):
        # Wood Ṁ = 2 → ~1 each (2e-14); walls ~4–8; sep peri 11.2 / apo 35.6 → overlap near peri only.
        comps = [
            {"id": "A", "mass_solar": 1.079, "sp_type": "G2V", "mass_loss_msun_yr": 2e-14,
             "pair": "AB", "sma_au": 23.4, "ecc": 0.52},
            {"id": "B", "mass_solar": 0.909, "sp_type": "K1V", "mass_loss_msun_yr": 2e-14,
             "pair": "AB", "sma_au": 23.4, "ecc": 0.52}]
        r = es.compose_exclusion_system(comps, phase="both", alpha=0.4)
        # standoff anchors unchanged (byte-identity)
        c = {x["id"]: x for x in r["zones"][0]["components"]}
        self.assertAlmostEqual(c["A"]["r_ex_au"], 48.97, places=1)
        self.assertAlmostEqual(c["B"]["r_ex_au"], 45.72, places=1)
        wz = self._zone_for(r["wall_zones"], "A")
        self.assertIsNotNone(wz)
        self.assertIsNotNone(wz["wall_envelope_au"]["periastron"])   # walls overlap near peri
        self.assertIsNone(wz["wall_envelope_au"]["apastron"])        # not at apo (absence reported)
        self.assertIsNotNone(wz["combined_wind_wall_au"])
        self.assertEqual(wz["combined_wind_phase"], "periastron")

    def test_70_oph_danger_case(self):
        # Wood Ṁ = 100 → ~50 each (1e-12); per-component walls ~28–57; overlap all phases; combined ~40–80.
        comps = [
            {"id": "A", "mass_solar": 0.90, "sp_type": "K0V", "mass_loss_msun_yr": 1e-12,
             "pair": "OphAB", "sma_au": 23.3, "ecc": 0.50},
            {"id": "B", "mass_solar": 0.70, "sp_type": "K5V", "mass_loss_msun_yr": 1e-12,
             "pair": "OphAB", "sma_au": 23.3, "ecc": 0.50}]
        r = es.compose_exclusion_system(comps, phase="both", alpha=0.4)
        c = {x["id"]: x for x in r["zones"][0]["components"]}
        self.assertTrue(28 <= c["A"]["wall_band_au"][1] <= 57)       # per-component wall band-hi
        wz = self._zone_for(r["wall_zones"], "A")
        self.assertIsNotNone(wz["wall_envelope_au"]["periastron"])   # overlap at BOTH phases
        self.assertIsNotNone(wz["wall_envelope_au"]["apastron"])
        self.assertTrue(40 <= wz["combined_wind_wall_au"] <= 80)
        self.assertTrue(wz["wall_exceeds_standoff"])                 # band-hi wall > the ~41–46 standoffs

    def test_61_cyg_no_envelope(self):
        # Wood Ṁ = 0.5 (1e-14), weak; wide ~84 AU → walls never overlap → NO wall_zone at any phase.
        comps = [
            {"id": "A", "mass_solar": 0.70, "sp_type": "K5V", "mass_loss_msun_yr": 1e-14,
             "pair": "CygAB", "sma_au": 84.0, "ecc": 0.40},
            {"id": "B", "mass_solar": 0.63, "sp_type": "K7V", "mass_loss_msun_yr": 1e-14,
             "pair": "CygAB", "sma_au": 84.0, "ecc": 0.40}]
        r = es.compose_exclusion_system(comps, phase="both", alpha=0.4)
        self.assertEqual(r["wall_zones"], [])                        # no wall merge (report absence)

    def test_sirius_mixed_domain(self):
        # A = a_dwarf small wall; B = windless WD (no wall) → walls don't overlap → no wall_zone.
        comps = [
            {"id": "A", "mass_solar": 2.063, "sp_type": "A0mA1Va", "pair": "AB", "sma_au": 19.8, "ecc": 0.59},
            {"id": "B", "mass_solar": 1.018, "class": "wd", "pair": "AB", "sma_au": 19.8, "ecc": 0.59}]
        r = es.compose_exclusion_system(comps, phase="both", alpha=0.4)
        c = {x["id"]: x for x in r["zones"][0]["components"]}
        self.assertIsNotNone(c["A"]["wall_au"])                      # A (a_dwarf) has a small wall
        self.assertIsNone(c["B"]["wall_au"])                         # B windless → no wall
        self.assertEqual(c["B"]["domain"], "windless_free_harbor")
        self.assertEqual(r["wall_zones"], [])                        # walls don't overlap the separation

    def test_ms_plus_giant_wall_not_dropped(self):
        # a K-giant contributes a large (Oort-scale) wall that must NOT be dropped (the CR-22.2 flip).
        comps = [
            {"id": "A", "mass_solar": 1.0, "sp_type": "G2V", "mass_loss_msun_yr": 2e-14,
             "pair": "AB", "sma_au": 500.0, "ecc": 0.1},
            {"id": "G", "mass_solar": 1.5, "sp_type": "K0III", "pair": "AB", "sma_au": 500.0, "ecc": 0.1}]
        r = es.compose_exclusion_system(comps, phase="both", alpha=0.4)
        cg = next(x for c in r["zones"] for x in c["components"] if x["id"] == "G")
        self.assertEqual(cg["domain"], "evolved")
        self.assertIsNotNone(cg["wall_au"])                          # giant wall present, not dropped
        self.assertTrue(cg["wall_exceeds_standoff"])                 # Oort-scale wall > its standoff


class Cp3FixTest(unittest.TestCase):
    """Regressions for the CP3 /code-review findings."""

    def test_component_domain_forwards_otype(self):
        # CP3-1: an AGB/Mira with a bare (lum-class-less) sp_type must classify EVOLVED via otype,
        # never fall through to MS (which would fabricate an MS mass — the CR-6-AMEND/F1 guard).
        self.assertEqual(es._component_domain(sp_type="M7", otype="Mira")[0], "evolved")
        self.assertEqual(es._component_domain(sp_type="M7")[0], "main_sequence")   # otype is load-bearing
        self.assertEqual(es._component_domain(sp_type="WN5")[0], "evolved")        # WR from sp_type

    def test_combined_wind_evolved_is_capped(self):
        # CP3-2: a tight AGB pair's combined-wind wall stays ly-scale (capped), not unbounded.
        comps = [
            {"id": "A", "mass_solar": 1.2, "sp_type": "M7III", "mass_loss_msun_yr": 1e-6,
             "wind_class": "agb_overwindy", "pair": "AB", "sma_au": 30.0, "ecc": 0.1},
            {"id": "B", "mass_solar": 1.1, "sp_type": "M6III", "mass_loss_msun_yr": 1e-6,
             "wind_class": "agb_overwindy", "pair": "AB", "sma_au": 30.0, "ecc": 0.1}]
        r = es.compose_exclusion_system(comps, phase="both", alpha=0.4)
        wz = next((z for z in r["wall_zones"] if "A" in z["members"]), None)
        self.assertIsNotNone(wz)
        self.assertIsNotNone(wz["combined_wind_band_au"])
        self.assertLess(wz["combined_wind_band_au"][1], 3e5)      # capped at the astropause, ly-scale


class Cp4FixTest(unittest.TestCase):
    """Regressions for the CP4 /code-review findings."""

    def test_explicit_windspeed_over_class_default_astrosphere_wood(self):
        # CP4-1: an explicit --wind-speed on a class-default astrosphere_wood MS star is HONORED.
        inputs, prov = ew.resolve_wind_inputs("main_sequence", "active", "M4V", wind_speed=250.0)
        self.assertEqual(inputs["v_wind"], 250.0)
        self.assertEqual(prov["wind_speed"], "supplied")
        # but an EXPLICIT --mass-loss-source astrosphere_wood still forces 400 (spec validation #4)
        i2, p2 = ew.resolve_wind_inputs("main_sequence", "solar", "G2V", wind_speed=800.0,
                                        mass_loss_source="astrosphere_wood")
        self.assertEqual(i2["v_wind"], 400.0)
        self.assertEqual(p2["wind_speed"], "astrosphere_wood_forced")

    def test_bad_bfield_falls_back_to_explicit_cms(self):
        # CP4-4: a non-positive --b-field falls back to an accompanying explicit --c-ms (not None).
        inputs, prov = ew.resolve_wind_inputs("main_sequence", "solar", "G2V", b_field=-1.0, c_ms=20.0)
        self.assertEqual(inputs["c_ms"], 20.0)
        self.assertEqual(prov["c_ms"], "supplied")

    def test_bfield_derived_band_used_for_marginal(self):
        # CP4-3: a b-field-derived c_ms carries its OWN ±band for the verdict_marginal straddle.
        inputs, prov = ew.resolve_wind_inputs("main_sequence", "solar", "G2V", b_field=6.0)
        self.assertEqual(prov["c_ms"], "b_field_derived")
        self.assertNotEqual(tuple(inputs["c_ms_band"]), tuple(ew._C_MS_BAND))
        self.assertTrue(inputs["c_ms_band"][0] <= inputs["c_ms"] <= inputs["c_ms_band"][1])

    def test_apastron_only_no_spurious_wall_zone(self):
        # CP4-2: walls overlap at peri but not apo → phase='apastron' reports NO wall_zone.
        comps = [
            {"id": "A", "mass_solar": 1.0, "sp_type": "G2V", "mass_loss_msun_yr": 1e-13,
             "pair": "AB", "sma_au": 25.0, "ecc": 0.6},
            {"id": "B", "mass_solar": 1.0, "sp_type": "G2V", "mass_loss_msun_yr": 1e-13,
             "pair": "AB", "sma_au": 25.0, "ecc": 0.6}]
        self.assertEqual(es.compose_exclusion_system(comps, phase="apastron", alpha=0.4)["wall_zones"], [])
        self.assertEqual(len(es.compose_exclusion_system(comps, phase="periastron", alpha=0.4)["wall_zones"]), 1)


class HazardFlagsTest(unittest.TestCase):
    def test_flags(self):
        self.assertEqual(ew.hazard_flags(8.0, 6.0, 47.5)[0], False)
        self.assertTrue(ew.hazard_flags(1131.0, 848.0, 61.0)[0])
        self.assertEqual(ew.hazard_flags(None, None, 47.5), (None, None))
        self.assertEqual(ew.hazard_flags(8.0, 6.0, None), (None, None))


if __name__ == "__main__":
    unittest.main()
