# tests/test_shared_luminosity_class.py — CR-10.5 Part 1 luminosity-class token parser (offline).

import unittest

from core.shared import luminosity_class as lc


class LuminosityClassTest(unittest.TestCase):
    def test_wb_validation_strings(self):
        # The three exact strings WB re-gates CR-10.5 Part 1 against.
        self.assertEqual(lc("F8Ib"), ("Ib", True))            # Polaris — supergiant, suffix kept
        self.assertEqual(lc("K0IIIb"), ("III", True))         # Pollux — giant, sub-suffix dropped
        self.assertEqual(lc("M1-M2Ia-Iab"), ("Ia-Iab", True))  # Betelgeuse — compound span verbatim

    def test_boundary_IIIb_is_not_Ib(self):
        # The load-bearing token-boundary test: "Ib" must NOT match inside "IIIb".
        token, evolved = lc("K0IIIb")
        self.assertEqual(token, "III")
        self.assertNotEqual(token, "Ib")
        self.assertTrue(evolved)

    def test_ms_dwarf_not_evolved(self):
        for sp in ("G6V", "G2V", "M5.5Ve", "A0V", "K2V"):
            token, evolved = lc(sp)
            self.assertEqual(token, "V", sp)
            self.assertFalse(evolved, sp)

    def test_colon_form_boundary(self):
        self.assertEqual(lc("G8:V"), ("V", False))            # colon satisfies the [^A-Za-z] boundary

    def test_subgiant_and_giant_evolved(self):
        self.assertEqual(lc("K0IV"), ("IV", True))
        self.assertEqual(lc("K2III"), ("III", True))
        self.assertEqual(lc("K0III"), ("III", True))

    def test_supergiant_suffix_variants(self):
        self.assertEqual(lc("O9.5Ia"), ("Ia", True))
        self.assertEqual(lc("F5Iab"), ("Iab", True))
        self.assertEqual(lc("M2Ia"), ("Ia", True))

    def test_bright_giant_II(self):
        self.assertEqual(lc("G5II"), ("II", True))

    def test_no_class_or_degenerate_or_blank(self):
        for sp in ("DA2", "DA", "sdB", "L5", "T6", "", None):
            self.assertEqual(lc(sp), (None, False), sp)

    def test_range_span_is_evolved_if_any_evolved_unit(self):
        # A IV-V range carries a subgiant unit → evolved; the span is returned verbatim.
        token, evolved = lc("B2IV-V")
        self.assertEqual(token, "IV-V")
        self.assertTrue(evolved)


if __name__ == "__main__":
    unittest.main()
