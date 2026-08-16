# tests/test_debris_disk.py — CR-1 debris-disk / IR-excess (core).
#
# Offline: the pure parsers (Chen/Cotten column mapping + the Cotten τ×1e-4 scale + warm/cold
# classification) + the Planck band-fraction. Live-gated: the Vega/Fomalhaut/HD 69830/Tau Ceti
# anchors + the per-star WISE upper limit.

import unittest

import core.debris_disk as dd
from tests._netcheck import live_enabled, reachable

_ONLINE = live_enabled() and reachable("simbad.u-strasbg.fr", 443)


class HelperTest(unittest.TestCase):
    def test_planck_band_fraction_reasonable(self):
        frac = dd._planck_band_fraction(5778.0)
        self.assertTrue(1e-5 < frac < 1e-2)              # W4 RJ tail of a solar photosphere
        # A cool star emits a larger fraction of its bolometric flux in the 22 µm band.
        self.assertGreater(dd._planck_band_fraction(3500.0), frac)

    def test_classify(self):
        self.assertEqual(dd._classify(300.0), "warm")
        self.assertEqual(dd._classify(50.0), "cold")
        self.assertEqual(dd._classify(130.0), "warm")
        self.assertEqual(dd._classify(None), "cold")


class ChenParseTest(unittest.TestCase):
    def test_two_temp(self):
        comps = dd._chen_components({"Tgr1": 150, "D1": 5, "LIR/L*1": 1e-4,
                                     "Tgr2": 50, "D2": 80, "LIR2/L*": 2e-5})
        self.assertEqual([c["type"] for c in comps], ["warm", "cold"])
        self.assertEqual(comps[0]["L_IR_over_Lstar"], 1e-4)
        self.assertEqual(comps[1]["T_dust_K"], 50.0)

    def test_single_temp_classified_by_temperature(self):
        self.assertEqual(dd._chen_components({"Tgr": 40, "D": 60, "LIR/L*": 3e-5})[0]["type"], "cold")
        self.assertEqual(dd._chen_components({"Tgr": 300, "D": 1, "LIR/L*": 2e-4})[0]["type"], "warm")

    def test_empty_row(self):
        self.assertEqual(dd._chen_components({"Tgr": None}), [])


class CottenParseTest(unittest.TestCase):
    def test_tau_scaled_by_1e_minus_4(self):
        comps, tau = dd._cotten_components({"Tau": 0.72, "Td1": 70, "Rd1": 60})
        self.assertAlmostEqual(tau, 7.2e-5)              # 0.72 × 1e-4 (pinned live)
        self.assertEqual(comps[0]["type"], "cold")       # 70 K classified cold, not forced warm
        self.assertAlmostEqual(comps[0]["L_IR_over_Lstar"], 7.2e-5)

    def test_two_belt(self):
        comps, tau = dd._cotten_components({"Tau": 6.45, "Td1": 500, "Rd1": 0.2,
                                            "Tdt2": 70, "Rd2": 10.7})
        self.assertEqual([c["type"] for c in comps], ["warm", "cold"])
        self.assertAlmostEqual(tau, 6.45e-4)
        self.assertIn("Herschel", comps[1]["note"])

    def test_single_warm(self):
        comps, _ = dd._cotten_components({"Tau": 3.89, "Td1": 300, "Rd1": 0.6})
        self.assertEqual(comps[0]["type"], "warm")


class ValidationTest(unittest.TestCase):
    def test_requires_coords_or_star(self):
        self.assertIn("error", dd.debris_disk())


@unittest.skipUnless(_ONLINE, "SIMBAD/VizieR not reachable / SPACE_APP_RUN_LIVE unset")
class DebrisDiskLiveTest(unittest.TestCase):
    def test_vega_detected_in_range(self):
        d = dd.debris_disk(star="Vega")
        self.assertEqual(d["detection"], "detected")
        self.assertTrue(1e-5 < d["system_L_IR_over_Lstar"] < 1e-4)   # Vega ~2–3e-5

    def test_fomalhaut_detected(self):
        self.assertEqual(dd.debris_disk(star="Fomalhaut")["detection"], "detected")

    def test_tau_ceti_two_belt(self):
        types = {c["type"] for c in dd.debris_disk(star="HD 10700")["components"]}
        self.assertEqual(types, {"warm", "cold"})

    def test_disk_free_is_upper_limit_not_null(self):
        d = dd.debris_disk(star="18 Scorpii")
        self.assertEqual(d["detection"], "upper_limit")
        self.assertIsNotNone(d["upper_limit_L_IR_over_Lstar"])       # never null


if __name__ == "__main__":
    unittest.main()
