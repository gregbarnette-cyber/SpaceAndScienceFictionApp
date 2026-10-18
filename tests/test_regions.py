# tests/test_regions.py — CR-30.2 replaced the pre-CR-30 _lookup_spectral_type ceiling rule (over the retired
# main_sequence_stars table) with S1's lookup by the one parse. This file pins the region step's view of it:
# the S1 read (exact / interpolated / letter-only / out of span), the type-read fields on the region output,
# and white-dwarf rejection. The interpolation rules themselves are pinned in tests/test_cr30_parse.py.
import unittest

from core import regions


class S1RegionLookupTest(unittest.TestCase):
    def test_exact_row(self):
        s1, p = regions._lookup_s1("G2V")
        self.assertEqual(s1["s1_rows"], ["G2V"])
        self.assertEqual(s1["BCv"], -0.085)
        self.assertEqual(p.read, "G2")

    def test_half_subtype_interpolates_not_ceiling(self):
        # pre-CR-30: G1 → the G2 row (ceiling). Now G1V is an S1 row itself; G1.5 interpolates G1V–G2V.
        s1, _ = regions._lookup_s1("G1.5V")
        self.assertEqual(s1["s1_rows"], ["G1V", "G2V"])
        self.assertAlmostEqual(s1["s1_fraction"], 0.5)

    def test_cross_letter_interpolation(self):
        s1, _ = regions._lookup_s1("F9.5V")
        self.assertEqual(s1["s1_rows"], ["F9.5V"])            # S1 carries F9.5V
        s1, _ = regions._lookup_s1("G9.5V")
        self.assertEqual(s1["s1_rows"], ["G9V", "K0V"])

    def test_white_dwarf_not_matched(self):
        s1, p = regions._lookup_s1("DA1.9")
        self.assertIsNone(s1["BCv"])
        self.assertEqual(p.letter, "D")

    def test_hot_rows_now_resolve(self):
        s1, _ = regions._lookup_s1("O5V")
        self.assertEqual(s1["Msun"], 43.0)

    def test_region_step_letter_only_m_fails_curated(self):
        r = regions.compute_star_system_regions_from_simbad(
            {"main_id": "X", "sp_type": "M", "teff": 3200.0, "vmag": 10.0, "plx_value": 100.0})
        self.assertIn("error", r)
        self.assertIn("S1 needs a subtype", r["error"])

    def test_region_step_letter_only_k_reads_k5v(self):
        r = regions.compute_star_system_regions_from_simbad(
            {"main_id": "X", "sp_type": "K", "teff": 4400.0, "vmag": 6.0, "plx_value": 100.0})
        self.assertNotIn("error", r)
        self.assertTrue(r["subtype_unknown"])
        self.assertEqual(r["s1_rows"], ["K5V"])
        self.assertEqual(r["boloLum"], -0.63)

    def test_region_output_carries_the_type_read(self):
        r = regions.compute_star_system_regions_from_simbad(
            {"main_id": "X", "sp_type": "kA2hA5mA7V", "teff": 8000.0, "vmag": 4.0, "plx_value": 50.0})
        self.assertEqual(r["sp_type_read"], "A5")
        self.assertEqual(r["sp_type_raw"], "kA2hA5mA7V")
        self.assertTrue(r["s1_class_v_flag"])
        self.assertEqual(r["bc_key"], "A5")


if __name__ == "__main__":
    unittest.main()
