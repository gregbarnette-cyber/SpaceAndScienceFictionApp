# tests/test_sensing.py — Phase AP (Group S) sensing/detection core calculators.
#
# Offline golden-pin tests for core.sensing (S2 angular-resolution, S1 point-source-detection,
# S3 radar-range): every acceptance anchor from the request spec's §E table + the self-validating
# error matrix + the S1↔S2 shared-kernel cross-check + the behaviour-preserving direct-imaging
# refactor onto the S2 kernel. No network, no Qt, no numpy.
#
# NOTE (WB coordination-channel MSG 016): --flux-floor-w-m2 is an IRRADIANCE floor →
# R_max = √(L/(4π·floor)), aperture-INDEPENDENT. The spec's printed 10.1 AU pin was a 10×
# arithmetic slip; the correct §E row-4 pin is 4.04 AU (verified below).

import math
import unittest

import core.sensing as S
import core.calculators as calc

_SIGMA = 5.670374419e-8
_HC = 6.62607015e-34 * 299792458.0
_AU = 1.496e11              # the spec anchors use the rounded AU
_ARCSEC = 206_264.806


# ─────────────────────────────── S2 — angular-resolution ───────────────────────────────

class AngularResolutionAnchors(unittest.TestCase):
    def test_ir_1m(self):
        r = S.compute_angular_resolution(aperture_m=1.0, wavelength_m=10e-6, range_m=_AU)
        self.assertAlmostEqual(r["angular_resolution_rad"], 1.22e-5, places=9)
        self.assertAlmostEqual(r["angular_resolution_arcsec"], 2.5164306332, places=6)
        self.assertAlmostEqual(r["linear_resolution_m"], 1.22e-5 * _AU, places=3)  # ~1825 km

    def test_jwst_class(self):
        r = S.compute_angular_resolution(aperture_m=6.5, wavelength_m=2e-6)
        self.assertAlmostEqual(r["angular_resolution_rad"], 3.754e-7, places=9)
        self.assertAlmostEqual(r["angular_resolution_arcsec"], 0.0774286348677, places=7)
        self.assertIsNone(r["linear_resolution_m"])

    def test_frequency_equivalent_to_wavelength(self):
        lam = 0.03
        rf = S.compute_angular_resolution(aperture_m=1.0, frequency_hz=299792458.0 / lam)
        rw = S.compute_angular_resolution(aperture_m=1.0, wavelength_m=lam)
        self.assertAlmostEqual(rf["angular_resolution_rad"], rw["angular_resolution_rad"], places=12)

    def test_criteria_coefficients(self):
        for crit, k in (("rayleigh", 1.22), ("dawes", 1.02), ("sparrow", 0.94)):
            r = S.compute_angular_resolution(aperture_m=1.0, wavelength_m=1e-6, criterion=crit)
            self.assertAlmostEqual(r["coefficient"], k, places=6)
            self.assertAlmostEqual(r["angular_resolution_rad"], k * 1e-6, places=15)

    def test_coefficient_override(self):
        r = S.compute_angular_resolution(aperture_m=2.0, wavelength_m=1e-6, coefficient=1.0)
        self.assertEqual(r["criterion"], "custom")
        self.assertAlmostEqual(r["angular_resolution_rad"], 0.5e-6, places=15)

    def test_resolvable_and_resolved(self):
        # θ = 1e-6 rad at R = 1e6 m → resolves anything subtending ≥ 1 m.
        r = S.compute_angular_resolution(aperture_m=1.0, wavelength_m=1e-6, range_m=1e6,
                                         separation_m=2.0, object_size_m=0.5)
        self.assertTrue(r["resolvable"])           # 2/1e6 = 2e-6 ≥ 1e-6
        self.assertEqual(r["resolved_or_point"], "point")   # 0.5/1e6 = 5e-7 < 1e-6

    def test_errors(self):
        self.assertIn("error", S.compute_angular_resolution(aperture_m=0, wavelength_m=1e-6))
        self.assertIn("error", S.compute_angular_resolution(aperture_m=1))          # no λ/f
        self.assertIn("error", S.compute_angular_resolution(aperture_m=1, wavelength_m=1e-6,
                                                            frequency_hz=1e9))       # both
        self.assertIn("error", S.compute_angular_resolution(aperture_m=1, wavelength_m=1e-6,
                                                            criterion="bogus"))
        self.assertIn("error", S.compute_angular_resolution(aperture_m=1, wavelength_m=1e-6,
                                                            coefficient=-1))
        self.assertIn("error", S.compute_angular_resolution(aperture_m=1, wavelength_m=1e-6,
                                                            range_m=-1))


# ─────────────────────────── S1 — point-source-detection ───────────────────────────

class PointSourceDetectionAnchors(unittest.TestCase):
    def test_luminosity_from_temp_area(self):
        r = S.compute_point_source_detection(source_temp_k=300, source_area_m2=1000, emissivity=1.0,
                                             rx_aperture_m=1.0, flux_floor_w_m2=1e-19)
        self.assertAlmostEqual(r["source_luminosity_w"], _SIGMA * 1000 * 300 ** 4, places=3)
        self.assertAlmostEqual(r["source_luminosity_w"], 459300.327939, places=3)

    def test_irradiance_and_received_power_and_photons(self):
        L = _SIGMA * 1000 * 300 ** 4
        r = S.compute_point_source_detection(source_temp_k=300, source_area_m2=1000,
                                             rx_aperture_m=1.0, range_m=_AU, wavelength_m=10e-6)
        e = L / (4 * math.pi * _AU ** 2)
        a_rx = math.pi * 0.25
        self.assertAlmostEqual(r["irradiance_w_m2"], e, places=24)
        self.assertAlmostEqual(r["received_power_w"], e * a_rx * 0.8, places=24)
        self.assertAlmostEqual(r["photon_rate_hz"], (e * a_rx * 0.8) * 10e-6 / _HC, places=6)
        self.assertAlmostEqual(r["photon_rate_hz"], 51.66, delta=0.1)

    def test_flux_floor_is_irradiance_and_aperture_independent(self):
        # WB MSG 016 ruling (A): R_max = √(L/(4π·floor)) — no aperture term. §E row 4 = 4.04 AU.
        L = _SIGMA * 1000 * 300 ** 4
        expected = math.sqrt(L / (4 * math.pi * 1e-19))
        r1 = S.compute_point_source_detection(source_temp_k=300, source_area_m2=1000,
                                              rx_aperture_m=1.0, flux_floor_w_m2=1e-19)
        r2 = S.compute_point_source_detection(source_temp_k=300, source_area_m2=1000,
                                              rx_aperture_m=10.0, flux_floor_w_m2=1e-19)
        self.assertAlmostEqual(r1["max_detection_range_m"], expected, places=1)
        self.assertAlmostEqual(r1["max_detection_range_m"] / 1.496e11, 4.04, places=2)
        self.assertEqual(r1["detection_regime"], "flux-floor")
        # aperture-independent: 1 m and 10 m give the same range
        self.assertAlmostEqual(r1["max_detection_range_m"], r2["max_detection_range_m"], places=1)

    def test_source_power_direct(self):
        r = S.compute_point_source_detection(source_power_w=4.593e5, rx_aperture_m=1.0,
                                             range_m=_AU, wavelength_m=10e-6)
        self.assertAlmostEqual(r["source_luminosity_w"], 4.593e5, places=3)

    def test_photon_rate_bandcentre_note(self):
        # WB MSG 022 ruling (A): the model_note must state n is a band-centre (narrow-band)
        # conversion of the bolometric P_rx, not an in-band Planck integral.
        r = S.compute_point_source_detection(source_power_w=1e6, rx_aperture_m=1.0,
                                             range_m=_AU, band="thermal-ir", background="cmb")
        self.assertIn("band-centre", r["model_note"])
        self.assertIn("bolometric", r["model_note"])

    def test_detector_limited_snr(self):
        r = S.compute_point_source_detection(source_power_w=4.593e5, rx_aperture_m=1.0,
                                             range_m=_AU, wavelength_m=10e-6, nep_w_rthz=1e-19,
                                             integration_s=1.0)
        # SNR = P_rx / (NEP·√(1/2t))
        p_rx = r["received_power_w"]
        self.assertAlmostEqual(r["snr"], p_rx / (1e-19 * math.sqrt(0.5)), places=6)
        self.assertEqual(r["detection_regime"], "detector-limited")

    def test_detector_limited_range_solve_scales_inverse_square(self):
        base = S.compute_point_source_detection(source_power_w=4.593e5, rx_aperture_m=1.0,
                                                wavelength_m=10e-6, nep_w_rthz=1e-19,
                                                snr_threshold=5.0)
        self.assertEqual(base["detection_regime"], "detector-limited")
        self.assertIsNotNone(base["max_detection_range_m"])
        # at exactly max range, SNR == threshold
        at = S.compute_point_source_detection(source_power_w=4.593e5, rx_aperture_m=1.0,
                                              wavelength_m=10e-6, nep_w_rthz=1e-19,
                                              range_m=base["max_detection_range_m"])
        self.assertAlmostEqual(at["snr"], 5.0, places=4)

    def test_background_limited_needs_band(self):
        # background mode with a bare --wavelength-m (no Δλ) → error (WB MSG 016 partition)
        self.assertIn("error", S.compute_point_source_detection(
            source_power_w=4.593e5, rx_aperture_m=1.0, range_m=_AU, wavelength_m=10e-6,
            background="cmb"))
        # with a band it works
        ok = S.compute_point_source_detection(source_power_w=4.593e5, rx_aperture_m=1.0,
                                              range_m=_AU, band="thermal-ir", background="cmb")
        self.assertEqual(ok["detection_regime"], "background-limited")
        self.assertIsNotNone(ok["snr"])
        self.assertIn("cmb", ok["background_used"])

    def test_resolved_flag(self):
        r = S.compute_point_source_detection(source_power_w=1e6, rx_aperture_m=1.0, range_m=1e6,
                                             wavelength_m=1e-6, source_size_m=100.0)
        # θ_s = 100/1e6 = 1e-4 ≫ θ_res = 1.22e-6 → resolved
        self.assertEqual(r["resolved_or_point"], "resolved")
        # spec: a resolved source flags the point-source law as a LOWER BOUND (model_note carve-out).
        self.assertIn("LOWER BOUND", r["model_note"])
        # a genuine point source carries no such caveat.
        pt = S.compute_point_source_detection(source_power_w=1e6, rx_aperture_m=1.0, range_m=1e12,
                                              wavelength_m=1e-6, source_size_m=1.0)
        self.assertEqual(pt["resolved_or_point"], "point")
        self.assertNotIn("LOWER BOUND", pt["model_note"])

    def test_errors(self):
        f = S.compute_point_source_detection
        self.assertIn("error", f(rx_aperture_m=1.0, flux_floor_w_m2=1e-19))            # no source
        self.assertIn("error", f(source_power_w=1e5, source_temp_k=300,
                                 source_area_m2=1, rx_aperture_m=1, flux_floor_w_m2=1e-19))  # both
        self.assertIn("error", f(source_power_w=1e5, rx_aperture_m=0, flux_floor_w_m2=1e-19))
        self.assertIn("error", f(source_temp_k=300, source_area_m2=1, emissivity=1.5,
                                 rx_aperture_m=1, flux_floor_w_m2=1e-19))
        self.assertIn("error", f(source_power_w=1e5, rx_aperture_m=1,
                                 flux_floor_w_m2=1e-19, nep_w_rthz=1e-19))              # two floors
        self.assertIn("error", f(source_power_w=1e5, rx_aperture_m=1))                 # solve, no floor


# ─────────────────────────────── S3 — radar-range ───────────────────────────────

class RadarRangeAnchors(unittest.TestCase):
    def test_received_power(self):
        r = S.compute_radar_range(tx_power_w=1e9, tx_aperture_m=10, wavelength_m=0.03,
                                  target_rcs_m2=100, range_m=1e9)
        self.assertAlmostEqual(r["received_power_w"], 5.45415391e-20, delta=1e-28)

    def test_max_range(self):
        r = S.compute_radar_range(tx_power_w=1e9, tx_aperture_m=10, wavelength_m=0.03,
                                  target_rcs_m2=100, min_detectable_power_w=1e-18)
        self.assertAlmostEqual(r["max_range_m"], 4.83261110e8, delta=10.0)

    def test_gain_default(self):
        r = S.compute_radar_range(tx_power_w=1e9, tx_aperture_m=10, wavelength_m=0.03,
                                  target_rcs_m2=100, range_m=1e9)
        self.assertAlmostEqual(r["tx_gain"], (math.pi * 10 / 0.03) ** 2, places=3)
        self.assertAlmostEqual(r["rx_gain"], r["tx_gain"], places=6)   # monostatic default

    def test_snr_with_noise_temp(self):
        r = S.compute_radar_range(tx_power_w=1e9, tx_aperture_m=10, wavelength_m=0.03,
                                  target_rcs_m2=100, range_m=1e6, system_noise_temp_k=290,
                                  integration_s=1.0)
        self.assertIsNotNone(r["snr"])

    def test_errors(self):
        f = S.compute_radar_range
        self.assertIn("error", f(tx_power_w=0, tx_aperture_m=10, wavelength_m=0.03,
                                 target_rcs_m2=1, range_m=1e6))
        self.assertIn("error", f(tx_power_w=1e9, tx_aperture_m=10, target_rcs_m2=1, range_m=1e6))
        self.assertIn("error", f(tx_power_w=1e9, tx_aperture_m=10, wavelength_m=0.03,
                                 target_rcs_m2=1))                       # neither range nor P_min
        self.assertIn("error", f(tx_power_w=1e9, tx_aperture_m=10, wavelength_m=0.03,
                                 target_rcs_m2=1, range_m=1e6,
                                 min_detectable_power_w=1e-18))          # both


# ─────────────── shared kernel + direct-imaging behaviour-preserving refactor ───────────────

class SharedKernelTest(unittest.TestCase):
    def test_s2_kernel_is_the_direct_imaging_iwa(self):
        # direct-imaging uses the 1·λ/D convention (coefficient 1.0) via the S2 kernel.
        self.assertAlmostEqual(S._rayleigh_theta(2e-6, 6.5, 1.0), 2e-6 / 6.5, places=15)

    def test_direct_imaging_iwa_byte_identical(self):
        # Behaviour-preserving: iwa_arcsec == (λ_m/D)·206265 exactly (coefficient 1.0), unchanged.
        r = calc.compute_direct_imaging(sma_au=1, distance_pc=10, planet_radius_earth=1,
                                        telescope_diameter_m=6.5, wavelength_um=2)
        self.assertAlmostEqual(r["iwa_arcsec"], (2e-6 / 6.5) * _ARCSEC, places=10)
        self.assertTrue(r["resolvable"])
        self.assertAlmostEqual(r["angular_sep_arcsec"], 0.1, places=10)

    def test_direct_imaging_no_telescope_still_none(self):
        r = calc.compute_direct_imaging(sma_au=1, distance_pc=10, planet_radius_earth=1)
        self.assertIsNone(r["iwa_arcsec"])
        self.assertIsNone(r["resolvable"])


if __name__ == "__main__":
    unittest.main()
