# tests/test_par_flux.py — Phase AA PAR / photosynthesis calculator (core).
#
# In-process tests for core.par_flux.compute_par_flux, offline (the spectral_type
# path reads the auto-seeded main_sequence_stars table; the star/SIMBAD path is
# mocked). Phase-N/T/V/W/X lineage: acceptance anchors + Teff/insolation-source
# paths + PPFD cross-check + band override + the validation matrix + determinism.
#
# SED model is BLACKBODY (the plan's mandate). The plan's M-dwarf band values
# (f_PAR 0.04–0.07 / deficit 6–10) are REAL-SED numbers; a blackbody reproduces
# them at Teff ≈ 2700 K (a late-M dwarf), not 3000 K — a 3000 K blackbody
# correctly gives ~0.081. Both are asserted below; the real-SED gap is documented
# in the module's model_note (Open-item #2 of completed_plans/PHASE_AA_PLAN.md).

import unittest
from unittest import mock

import core.par_flux as par_flux


class SunAnchorTest(unittest.TestCase):
    def test_solar_f_par_and_ppfd(self):
        r = par_flux.compute_par_flux(teff_k=5772, insolation_wm2=1361)
        self.assertNotIn("error", r)
        # Blackbody 400–700 nm for the Sun lands in [0.36, 0.40] (real solar ~0.40–0.45).
        self.assertGreaterEqual(r["par_fraction"], 0.36)
        self.assertLessEqual(r["par_fraction"], 0.40)
        # par_irradiance is exactly S · f_PAR (no independent 540 W/m² claim — that
        # is a real-SED figure; blackbody gives ~499 W/m²).
        self.assertAlmostEqual(r["par_irradiance_wm2"], 1361 * r["par_fraction"], places=6)
        # Full-sun PPFD anchor (~2000+ µmol/m²/s).
        self.assertGreater(r["ppfd_umol_m2_s"], 2000.0)
        # The Sun is its own G2 reference → deficit ≈ 1.
        self.assertAlmostEqual(r["par_deficit_vs_g2"], 1.0, places=3)

    def test_ppfd_cross_check_0219(self):
        # PPFD must reconcile with the standard PAR mean ≈ 0.219 J/µmol to within a
        # few percent (guards the photon-integral units — the one fiddly integral).
        r = par_flux.compute_par_flux(teff_k=5772, insolation_wm2=1361)
        ppfd_shortcut = r["par_irradiance_wm2"] / 0.219
        self.assertAlmostEqual(r["ppfd_umol_m2_s"], ppfd_shortcut, delta=ppfd_shortcut * 0.03)
        self.assertAlmostEqual(r["j_per_umol"], 0.219, delta=0.005)


class MDwarfDeficitTest(unittest.TestCase):
    def test_late_m_blackbody_band(self):
        # Blackbody reproduces the plan's red-dwarf band at Teff ≈ 2700 K.
        r = par_flux.compute_par_flux(teff_k=2700, insolation_wm2=1361)
        self.assertGreaterEqual(r["par_fraction"], 0.04)
        self.assertLessEqual(r["par_fraction"], 0.07)
        self.assertGreaterEqual(r["par_deficit_vs_g2"], 6.0)
        self.assertLessEqual(r["par_deficit_vs_g2"], 10.0)

    def test_3000k_blackbody_is_honest(self):
        # A 3000 K blackbody genuinely gives ~0.08 (real late-M SEDs sit lower —
        # documented in model_note; blackbody is OPTIMISTIC for red dwarfs).
        r = par_flux.compute_par_flux(teff_k=3000, insolation_wm2=1361)
        self.assertAlmostEqual(r["par_fraction"], 0.081, delta=0.005)
        self.assertLess(r["par_fraction"], 0.10)
        self.assertIn("blackbody", r["model_note"].lower())

    def test_deficit_monotonic(self):
        # Cooler star → larger deficit.
        hot = par_flux.compute_par_flux(teff_k=3900, insolation_wm2=1361)["par_deficit_vs_g2"]
        cool = par_flux.compute_par_flux(teff_k=3000, insolation_wm2=1361)["par_deficit_vs_g2"]
        self.assertGreater(cool, hot)
        self.assertGreater(hot, 1.0)


class TeffSourceTest(unittest.TestCase):
    def test_spectral_type_matches_teff(self):
        # G2V resolves to the main-sequence table Teff (5770); f_PAR matches the
        # direct 5772 K path to ~3 decimals.
        r_sp = par_flux.compute_par_flux(spectral_type="G2V", insolation_wm2=1361)
        r_t = par_flux.compute_par_flux(teff_k=5770, insolation_wm2=1361)
        self.assertNotIn("error", r_sp)
        self.assertAlmostEqual(r_sp["teff_k"], 5770.0, places=1)
        self.assertAlmostEqual(r_sp["par_fraction"], r_t["par_fraction"], places=4)

    def test_spectral_ceiling_rule(self):
        # G1 → the ceiling entry G2 (smallest subtype ≥ requested) → 5770 K.
        r = par_flux.compute_par_flux(spectral_type="G1V", insolation_wm2=1361)
        self.assertNotIn("error", r)
        self.assertAlmostEqual(r["teff_k"], 5770.0, places=1)

    def test_star_path_mocked(self):
        simbad = {"main_id": "Fake"}
        with mock.patch("core.databases.compute_simbad_lookup", return_value=simbad), \
             mock.patch("core.regions.compute_star_system_regions_from_simbad",
                        return_value={"temp": 5772.0, "bcLuminosity": 1.0}):
            r = par_flux.compute_par_flux(star="Fake Star", insolation_wm2=1361)
        self.assertNotIn("error", r)
        self.assertAlmostEqual(r["teff_k"], 5772.0, places=1)

    def test_star_simbad_error_propagates(self):
        with mock.patch("core.databases.compute_simbad_lookup",
                        return_value={"error": "No results found."}):
            r = par_flux.compute_par_flux(star="Nope", insolation_wm2=1361)
        self.assertEqual(r.get("error"), "No results found.")


class InsolationSourceTest(unittest.TestCase):
    def test_lum_dist_matches_direct(self):
        # luminosity_lsun=1, distance_au=1 → S ≈ 1361 W/m² (parity with direct).
        r = par_flux.compute_par_flux(teff_k=5772, luminosity_lsun=1.0, distance_au=1.0)
        self.assertNotIn("error", r)
        self.assertAlmostEqual(r["insolation_wm2"], 1361.0, delta=2.0)
        r_direct = par_flux.compute_par_flux(teff_k=5772, insolation_wm2=r["insolation_wm2"])
        self.assertAlmostEqual(r["par_irradiance_wm2"], r_direct["par_irradiance_wm2"], places=6)

    def test_inverse_square(self):
        near = par_flux.compute_par_flux(teff_k=5772, luminosity_lsun=1.0, distance_au=1.0)
        far = par_flux.compute_par_flux(teff_k=5772, luminosity_lsun=1.0, distance_au=2.0)
        self.assertAlmostEqual(far["insolation_wm2"] * 4.0, near["insolation_wm2"], delta=2.0)


class BandOverrideTest(unittest.TestCase):
    def test_wider_band_raises_f_par(self):
        default = par_flux.compute_par_flux(teff_k=5772, insolation_wm2=1361)
        wide = par_flux.compute_par_flux(teff_k=5772, insolation_wm2=1361, par_band_nm=(400, 750))
        self.assertGreater(wide["par_fraction"], default["par_fraction"])
        self.assertEqual(wide["band_nm"], [400.0, 750.0])


class ValidationMatrixTest(unittest.TestCase):
    def test_curated_errors(self):
        cases = [
            dict(teff_k=0, insolation_wm2=1361),                     # teff ≤ 0
            dict(teff_k=5772, insolation_wm2=0),                     # insolation ≤ 0
            dict(teff_k=5772),                                       # no insolation source
            dict(teff_k=5772, luminosity_lsun=1, distance_au=1, insolation_wm2=1361),  # two insolation
            dict(insolation_wm2=1361),                               # no Teff source
            dict(teff_k=5772, spectral_type="G2V", insolation_wm2=1361),  # two Teff
            dict(teff_k=5772, insolation_wm2=1361, par_band_nm=(700, 400)),  # band lo ≥ hi
            dict(teff_k=5772, insolation_wm2=1361, par_band_nm=(0, 700)),    # band ≤ 0
            dict(teff_k=5772, luminosity_lsun=1, distance_au=0),     # distance ≤ 0
            dict(teff_k=5772, luminosity_lsun=0, distance_au=1),     # luminosity ≤ 0
            dict(teff_k=5772, luminosity_lsun=1),                    # partial lum+dist (no distance)
            dict(spectral_type="ZZ9", insolation_wm2=1361),          # unresolvable spectral type
        ]
        for kw in cases:
            r = par_flux.compute_par_flux(**kw)
            self.assertIn("error", r, msg=f"expected error for {kw}")
            self.assertIsInstance(r["error"], str)


class DeterminismTest(unittest.TestCase):
    def test_deep_equal_on_repeat(self):
        a = par_flux.compute_par_flux(teff_k=4200, luminosity_lsun=0.3, distance_au=0.5)
        b = par_flux.compute_par_flux(teff_k=4200, luminosity_lsun=0.3, distance_au=0.5)
        self.assertEqual(a, b)


class C1RealSedTest(unittest.TestCase):
    """Phase AD (C1) — the --sed real BT-Settl f_PAR table path."""

    def test_default_is_blackbody(self):
        # bare call (no sed) must stay blackbody — backward-compatible (user decision)
        d = par_flux.compute_par_flux(teff_k=3000, insolation_wm2=1361)
        self.assertTrue(d["sed_model"].startswith("blackbody"))
        d2 = par_flux.compute_par_flux(teff_k=3000, insolation_wm2=1361, sed="blackbody")
        self.assertEqual(d, d2)                       # explicit blackbody == default

    def test_m_dwarf_real_below_blackbody(self):
        bb = par_flux.compute_par_flux(teff_k=3000, insolation_wm2=1361, sed="blackbody")
        rl = par_flux.compute_par_flux(teff_k=3000, insolation_wm2=1361, sed="real")
        self.assertLess(rl["par_fraction"], 0.081)    # real 3000 K well below blackbody ~0.081
        self.assertLess(rl["par_fraction"], bb["par_fraction"])
        self.assertAlmostEqual(rl["par_fraction"], 0.0228, places=4)   # table node
        self.assertGreater(rl["par_deficit_vs_g2"], bb["par_deficit_vs_g2"])  # larger deficit
        self.assertEqual(rl["sed_model"], par_flux._SED_MODEL_REAL)
        self.assertIn("BT-Settl", rl["model_note"])

    def test_sun_real_above_blackbody(self):
        bb = par_flux.compute_par_flux(teff_k=5772, insolation_wm2=1361, sed="blackbody")
        rl = par_flux.compute_par_flux(teff_k=5772, insolation_wm2=1361, sed="real")
        # real solar f_PAR ≈ 0.39 (matches ASTM ~0.39; plan's 0.40–0.45 was slightly high),
        # sits just above the blackbody ~0.37, and the G2 self-deficit is 1.0
        self.assertAlmostEqual(rl["par_fraction"], 0.389, delta=0.01)
        self.assertGreater(rl["par_fraction"], bb["par_fraction"])
        self.assertAlmostEqual(rl["par_deficit_vs_g2"], 1.0, places=6)

    def test_real_interpolates_between_nodes(self):
        import core.par_flux_tables as t
        # a Teff between grid nodes interpolates linearly
        lo, hi = 4000, 4400
        mid = par_flux.compute_par_flux(teff_k=4200, insolation_wm2=1361, sed="real")
        expect = (t._REAL_SED_FPAR[lo] + t._REAL_SED_FPAR[hi]) / 2
        self.assertAlmostEqual(mid["par_fraction"], expect, places=6)

    def test_band_fixed_and_out_of_range(self):
        # non-default band with --sed real → error (band-fixed table)
        self.assertIn("error", par_flux.compute_par_flux(
            teff_k=3000, insolation_wm2=1361, sed="real", par_band_nm=(400.0, 750.0)))
        # off the grid → error (directs to blackbody)
        self.assertIn("error", par_flux.compute_par_flux(
            teff_k=2000, insolation_wm2=1361, sed="real"))
        self.assertIn("error", par_flux.compute_par_flux(
            teff_k=8000, insolation_wm2=1361, sed="real"))
        # default band with real is fine
        self.assertNotIn("error", par_flux.compute_par_flux(
            teff_k=3000, insolation_wm2=1361, sed="real"))

    def test_bad_sed_value(self):
        self.assertIn("error", par_flux.compute_par_flux(
            teff_k=3000, insolation_wm2=1361, sed="bogus"))

    def test_determinism(self):
        kw = dict(teff_k=4200, insolation_wm2=1361, sed="real")
        self.assertEqual(par_flux.compute_par_flux(**kw), par_flux.compute_par_flux(**kw))


class C1TableIntegrityTest(unittest.TestCase):
    """Golden pin on the bundled BT-Settl f_PAR table (drift guard)."""

    def test_table_golden_and_monotone(self):
        import core.par_flux_tables as t
        # monotonic increasing with Teff (redder → less visible-band flux)
        teffs = sorted(t._REAL_SED_FPAR)
        vals = [t._REAL_SED_FPAR[k] for k in teffs]
        self.assertEqual(vals, sorted(vals))
        # a few pinned nodes (computed from BT-Settl at build)
        self.assertAlmostEqual(t._REAL_SED_FPAR[2600], 0.0044, places=4)
        self.assertAlmostEqual(t._REAL_SED_FPAR[3000], 0.0228, places=4)
        self.assertAlmostEqual(t._REAL_SED_FPAR[5800], 0.3910, places=4)
        self.assertAlmostEqual(t._REAL_SED_FPAR[7000], 0.4436, places=4)
        self.assertEqual((t._REAL_TEFF_MIN, t._REAL_TEFF_MAX), (2600, 7000))
        self.assertEqual(t._REAL_BAND_NM, (400.0, 700.0))

    def test_real_f_par_bounds(self):
        import core.par_flux_tables as t
        self.assertIsNone(t.real_f_par(2000))
        self.assertIsNone(t.real_f_par(9000))
        self.assertEqual(t.real_f_par(3000), 0.0228)   # exact node


if __name__ == "__main__":
    unittest.main()
