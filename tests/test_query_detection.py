# tests/test_query_detection.py — CR-6 detection-completeness query.py contract (offline).

import unittest

import core.detection as detection
from tests._queryharness import make_env, run_query

_ENV = make_env("cr6_detection_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class DetectionCompletenessQueryTest(unittest.TestCase):
    def test_rv_map_and_parity(self):
        rc, d, _ = _run("detection-completeness", "--app-mag", "4.83", "--distance-pc", "10",
                        "--sp-type", "G2V", "--methods", "rv", "--sma-grid", "1.0")
        self.assertEqual(rc, 0)
        rv = [m for m in d["methods"] if m["method"] == "rv"][0]
        self.assertGreater(rv["detectable_vs_sma"][0]["min_mass_earth"], 1.0)   # Earth below 1 m/s floor
        ref = detection.compute_detection_completeness(
            app_mag=4.83, distance_pc=10.0, sp_type="G2V", methods=["rv"], sma_grid=[1.0])
        self.assertAlmostEqual(rv["detectable_vs_sma"][0]["min_mass_earth"],
                               ref["methods"][0]["detectable_vs_sma"][0]["min_mass_earth"], places=9)

    def test_transit_not_applicable_note(self):
        rc, d, _ = _run("detection-completeness", "--app-mag", "8", "--distance-pc", "20",
                        "--sp-type", "K0V", "--methods", "transit")
        self.assertEqual(rc, 0)
        t = d["methods"][0]
        self.assertFalse(t["applicable"])
        self.assertIn("note", t)

    def test_bad_distance_curated_exit1(self):
        rc, d, _ = _run("detection-completeness", "--app-mag", "5", "--distance-pc", "0", "--sp-type", "G2V")
        self.assertEqual(rc, 1)
        self.assertIn("error", d)

    def test_bad_method_argparse_exit2(self):
        rc, d, _ = _run("detection-completeness", "--app-mag", "5", "--distance-pc", "10",
                        "--sp-type", "G2V", "--methods", "xyz")
        self.assertEqual(rc, 2)
        self.assertIsNone(d)

    def test_faint_astrometry_uses_noise_model_and_v1_1_0(self):
        rc, d, _ = _run("detection-completeness", "--app-mag", "18", "--distance-pc", "10",
                        "--sp-type", "G2V", "--methods", "astrometry")
        self.assertEqual(rc, 0)
        a = [m for m in d["methods"] if m["method"] == "astrometry"][0]
        self.assertIn("noise-model", a["floor_source"])                 # G>15 → Gaia σϖ(G) model
        self.assertEqual(d["assumptions"]["reference_version"], "3a-v1.1.0-2026-08-15")

    def test_non_ms_wd_host_flagged_not_faked(self):
        # CR-6-AMEND: a white-dwarf host flags host_class + out_of_domain and does NOT fake MS params.
        rc, d, _ = _run("detection-completeness", "--app-mag", "12", "--distance-pc", "15",
                        "--sp-type", "DA2", "--methods", "rv")
        self.assertEqual(rc, 0)
        self.assertEqual(d["host_class"], "white_dwarf")
        self.assertTrue(d["assumptions"]["out_of_domain"])
        self.assertIsNone(d["star_mass_solar"])                    # not faked to a 1.6 M☉ A star
        self.assertFalse(d["methods"][0]["applicable"])

    def test_non_ms_wd_host_with_real_mr_computes(self):
        rc, d, _ = _run("detection-completeness", "--app-mag", "12", "--distance-pc", "15",
                        "--sp-type", "DA2", "--star-mass-solar", "0.6", "--star-radius-solar", "0.013",
                        "--methods", "rv")
        self.assertEqual(rc, 0)
        self.assertEqual(d["host_class"], "white_dwarf")
        self.assertEqual(d["star_mass_solar"], 0.6)
        self.assertIn("jitter 1.5", d["methods"][0]["floor_source"])   # flat jitter, not A-star 5.0

    def test_imaging_carries_h_band_caveat(self):
        rc, d, _ = _run("detection-completeness", "--app-mag", "4.83", "--distance-pc", "10",
                        "--sp-type", "G2V", "--methods", "imaging")
        self.assertEqual(rc, 0)
        im = [m for m in d["methods"] if m["method"] == "imaging"][0]
        self.assertEqual(im["contrast_band"], "H")
        self.assertIn("self-luminous", im["mechanism_caveat"].lower())


if __name__ == "__main__":
    unittest.main()
