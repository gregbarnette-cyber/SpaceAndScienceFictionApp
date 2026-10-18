"""CR-30.2 — the one spectral-type parse and S1's lookup (interpolation, letter-only, Am, gravity designations).

Offline: the ``--spectral-type`` path makes no network call; ``run_query_inproc`` never touches the DB.
"""
import pathlib
import re
import unittest

from core import detection, ms_sequence, shared
from tests._queryharness import run_query_inproc

_REPO = pathlib.Path(__file__).resolve().parent.parent


def _eb(*args):
    return run_query_inproc("exclusion-boundary", *args)


class ParseTest(unittest.TestCase):
    def test_gravity_designations_stripped_and_flagged(self):
        cases = {
            "M8 INT-G": ("M8", "INT-G", True, False),
            "L3beta": ("L3", "beta", True, False),
            "M8.5 VL-G": ("M8.5", "VL-G", True, False),
            "L5gamma": ("L5", "gamma", True, False),
            "M8 delta": ("M8", "delta", False, True),
            "M8 FLD-G": ("M8", "FLD-G", False, False),
            "L0γ": ("L0", "gamma", True, False),
        }
        for raw, (read, grav, youth, prems) in cases.items():
            p = shared.parse_spectral_type(raw)
            self.assertEqual((p.read, p.gravity, p.youth_from_gravity, p.pre_ms_from_gravity),
                             (read, grav, youth, prems), raw)

    def test_int_g_is_not_class_i_and_vl_g_has_no_class_v(self):
        self.assertIsNone(shared.parse_spectral_type("M8 INT-G").lum_class_token)
        self.assertEqual(shared.luminosity_class("M8 INT-G"), (None, False))
        self.assertIsNone(shared.parse_spectral_type("M8.5 VL-G").lum_class_token)

    def test_low_gravity_iii_on_flagged_late_m(self):
        p = shared.parse_spectral_type("M8 III VL-G")
        self.assertTrue(p.low_gravity_class)
        self.assertIsNone(p.lum_class_token)
        self.assertEqual(shared.luminosity_class("M8 III VL-G"), (None, False))
        # unflagged, or an early M: III stays a giant
        self.assertEqual(shared.luminosity_class("M8III"), ("III", True))
        self.assertEqual(shared.luminosity_class("M3 III", youth=True), ("III", True))
        self.assertEqual(shared.luminosity_class("M5 III", youth=True), (None, False))

    def test_am_form(self):
        self.assertEqual(shared.parse_spectral_type("kA2hA5mA7V").read, "A5")
        self.assertTrue(shared.parse_spectral_type("kA2hA5mA7V").am_h_form)
        self.assertEqual(shared.parse_spectral_type("A0mA1Va").read, "A0")
        self.assertEqual(shared.parse_spectral_type("kA5hF0mF2").read, "F0")

    def test_prefixes_and_forms(self):
        for raw, read in (("dM6", "M6"), ("sdM3.0", "M3"), ("K7-M0V", "K7"), ("M5.5Ve", "M5.5"),
                          ("M2+V", "M2"), ("G8:V", "G8"), ("K", "K"), ("DA2", "D"), ("T7", "T7")):
            self.assertEqual(shared.parse_spectral_type(raw).read, read, raw)
        self.assertTrue(shared.parse_spectral_type("sdM3.0").subdwarf)
        self.assertEqual(shared.parse_spectral_type("sdM3.0").lum_class_token, "sd")
        self.assertEqual(shared.parse_spectral_type("F5IV-V+DQZ").lum_class_core, "IV")

    def test_l_type_has_no_colour_letter(self):
        self.assertIsNone(detection._sp_letter("L3beta"))
        self.assertIsNone(detection._sp_letter("L5gamma"))
        self.assertIsNone(detection._sp_letter("L0 VL-G"))
        self.assertEqual(detection._sp_letter("kA5hF0mF2"), "F")      # Q38: the h type
        self.assertEqual(detection._sp_letter("DA2"), "A")            # unparseable as OBAFGKM → legacy scan

    def test_cr10_5_guard_unchanged_otherwise(self):
        for raw, want in (("F8Ib", ("Ib", True)), ("K0IIIb", ("III", True)), ("M1-M2Ia-Iab", ("Ia-Iab", True)),
                          ("G6V", ("V", False)), ("G8:V", ("V", False)), ("DA2", (None, False)),
                          ("", (None, False)), (None, (None, False))):
            self.assertEqual(shared.luminosity_class(raw), want, raw)


class Cp1ParseFixesTest(unittest.TestCase):
    """CP1 (2026-10-15) findings, pinned."""

    def test_peculiarity_notes_and_star_names_are_not_gravity(self):
        p = shared.parse_spectral_type("F0IIIp(delta Del)")
        self.assertIsNone(p.gravity)
        self.assertFalse(p.pre_ms_from_gravity)
        self.assertEqual(shared.luminosity_class("F0IIIp(delta Del)"), ("III", True))
        self.assertIsNone(shared.parse_spectral_type("F0V gamma Dor").gravity)
        self.assertEqual(shared.parse_spectral_type("M8 delta").gravity, "delta")      # a trailing suffix still is

    def test_carbon_s_r_giants_keep_their_class(self):
        for t, tok in (("C5II", "II"), ("S4/2III", "III"), ("R5III", "III"), ("C-N5III", "III")):
            self.assertEqual(shared.luminosity_class(t), (tok, True), t)
            self.assertEqual(detection._host_class(t), "giant", t)

    def test_unknown_lowercase_prefix_colour(self):
        self.assertEqual(detection._sp_letter("gK0"), "K")
        self.assertEqual(detection._sp_letter("Am+F7/8V"), "A")
        self.assertEqual(detection._sp_letter("DA+M6"), "A")


class S1LookupTest(unittest.TestCase):
    def test_g95v_across_the_class_edge(self):
        r = ms_sequence.s1_at("G9.5V")
        self.assertAlmostEqual(r["BCv"], -0.1775, places=10)
        self.assertAlmostEqual(r["logL"], -0.30, places=10)
        self.assertAlmostEqual(10 ** r["logL"], 0.501, places=3)
        self.assertAlmostEqual(r["Msun"], 0.89, places=10)
        self.assertEqual(r["s1_rows"], ["G9V", "K0V"])
        self.assertAlmostEqual(r["s1_fraction"], 0.5)

    def test_quarter_subtype(self):
        r = ms_sequence.s1_at("K2.25V")
        self.assertEqual(r["s1_rows"], ["K2V", "K3V"])
        self.assertAlmostEqual(r["s1_fraction"], 0.25)
        self.assertAlmostEqual(r["Msun"], 0.81, places=10)
        self.assertAlmostEqual(r["logL"], -0.46, places=10)
        self.assertAlmostEqual(10 ** r["logL"], 0.3467, places=4)
        self.assertAlmostEqual(r["BCv"], -0.28875, places=10)

    def test_logl_interpolated_in_log(self):
        r = ms_sequence.s1_at("B8.5V")
        self.assertAlmostEqual(10 ** r["logL"], 105.925, places=2)

    def test_letter_only(self):
        k = ms_sequence.s1_at("K")
        self.assertTrue(k["subtype_unknown"])
        self.assertEqual(k["s1_rows"], ["K5V"])
        self.assertAlmostEqual(k["Msun"], 0.70)
        self.assertIn("5.8x", k["subtype_span_note"])
        self.assertIn("4.8x", ms_sequence.s1_at("F")["subtype_span_note"])
        self.assertIn("2.5x", ms_sequence.s1_at("G")["subtype_span_note"])
        for letter in "MOBA":
            r = ms_sequence.s1_at(letter)
            self.assertTrue(r["subtype_unknown"])
            self.assertIsNone(r["Msun"])

    def test_rows_past_m8_and_hot_rows_resolve(self):
        self.assertAlmostEqual(ms_sequence.s1_at("M8.5V")["Msun"], 0.080)
        self.assertAlmostEqual(ms_sequence.s1_at("M9V")["Msun"], 0.079)
        for t in ("O5V", "O9.5V", "B0V"):
            self.assertIsNotNone(ms_sequence.s1_at(t)["Msun"], t)

    def test_outside_span_null_with_reason(self):
        for t in ("L3", "T7", "DA2"):
            r = ms_sequence.s1_at(t)
            self.assertIsNone(r["Msun"])
            self.assertTrue(r["s1_null_reason"])

    def test_never_into_a_placeholder_cell(self):
        # M9.5V's B-V is S1's placeholder: a type between M9V and M9.5V reads B-V null, the rest interpolated
        r = ms_sequence.s1_at("M9.25V")
        self.assertIsNone(r["B-V"])
        self.assertIsNotNone(r["BCv"])


class SpectralTypeCallTest(unittest.TestCase):
    """CR-30.2 acceptance 1–6 on ``exclusion-boundary --spectral-type`` (offline)."""

    def test_g95v_and_k225v(self):
        code, out, _ = _eb("--spectral-type", "G9.5V", "--alpha", "0.4")
        self.assertEqual(code, 0, out)
        self.assertAlmostEqual(out["mass_msun"], 0.89, places=6)
        self.assertEqual(out["s1_rows"], ["G9V", "K0V"])
        code, out, _ = _eb("--spectral-type", "K2.25V", "--alpha", "0.4")
        self.assertEqual(code, 0, out)
        self.assertAlmostEqual(out["mass_msun"], 0.81, places=6)
        self.assertAlmostEqual(out["luminosity_lsun"], 0.3467, places=4)
        self.assertAlmostEqual(out["s1_fraction"], 0.25)

    def test_b85v(self):
        code, out, _ = _eb("--spectral-type", "B8.5V", "--alpha", "0.4")
        self.assertEqual(code, 0, out)
        self.assertAlmostEqual(out["luminosity_lsun"], 105.9, places=1)

    def test_letter_only(self):
        code, out, _ = _eb("--spectral-type", "K", "--alpha", "0.4")
        self.assertEqual(code, 0, out)
        self.assertAlmostEqual(out["mass_msun"], 0.70, places=6)
        self.assertTrue(out["subtype_unknown"])
        self.assertIn("5.8x", out["subtype_span_note"])
        code, out, _ = _eb("--spectral-type", "M", "--alpha", "0.4")
        self.assertEqual(code, 1)
        self.assertIn("no subtype", out["error"])

    def test_am_parse(self):
        code, out, _ = _eb("--spectral-type", "kA2hA5mA7V", "--alpha", "0.4")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["sp_type_read"], "A5")
        code, out, _ = _eb("--spectral-type", "A0mA1Va", "--alpha", "0.4")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["sp_type_read"], "A0")

    def test_gravity_type_not_evolved(self):
        code, out, _ = _eb("--spectral-type", "M8 INT-G", "--alpha", "0.4")
        self.assertEqual(code, 0, out)
        self.assertNotEqual(out.get("domain"), "evolved")
        self.assertEqual(out["sp_type_read"], "M8")
        self.assertEqual(out["gravity_designation"], "INT-G")
        self.assertAlmostEqual(out["mass_msun"], 0.085, places=6)

    def test_rows_past_m8_and_hot_types_resolve(self):
        for t, m in (("M8.5V", 0.080), ("M9V", 0.079)):
            code, out, _ = _eb("--spectral-type", t, "--alpha", "0.4")
            self.assertEqual(code, 0, (t, out))
            self.assertAlmostEqual(out["mass_msun"], m, places=6)
        for t in ("O5V", "O9.5V", "B0V"):
            code, out, _ = _eb("--spectral-type", t, "--alpha", "0.4")
            self.assertEqual(code, 0, (t, out))


class OneParseTest(unittest.TestCase):
    """Every spectral-type read in reach uses the one parse — no private regex / ceiling lookup left."""

    def test_no_private_class_parsers_left(self):
        for rel in ("core/regions.py", "core/detection.py", "core/exclusion_wall.py", "core/viz.py",
                    "core/par_flux.py", "main.py"):
            src = (_REPO / rel).read_text(encoding="utf-8")
            self.assertNotIn("_LUM_CLASS_RE", src, rel)
            self.assertNotIn("_lookup_spectral_type", src, rel)
            self.assertIsNone(re.search(r"^_SP_PATTERN\s*=", src, re.M), rel)


if __name__ == "__main__":
    unittest.main()
