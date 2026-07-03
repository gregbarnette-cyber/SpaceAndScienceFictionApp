# tests/test_query_thermal.py — Phase V power/thermal/shielding query.py contract.
#
# Offline subprocess tests mirroring tests/test_query_cooling_hz.py: happy-path JSON
# shape, core parity (subprocess == in-process), and the self-validating exit-code
# matrix (curated {"error"} -> exit 1; argparse -> exit 2).

import json
import os
import pathlib
import subprocess
import sys
import unittest

import core.thermal as thermal

_REPO = pathlib.Path(__file__).resolve().parent.parent
_ENV = {"SPACE_APP_DB": "/tmp/phase_v_throwaway.db", "PATH": os.environ.get("PATH", "")}


def _run(*cmd_args):
    proc = subprocess.run(
        [sys.executable, str(_REPO / "query.py"), *cmd_args],
        capture_output=True, text=True, cwd=str(_REPO), env=_ENV,
    )
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        payload = None
    return proc.returncode, payload, proc.stderr


class WasteHeatTest(unittest.TestCase):
    def test_happy_and_parity(self):
        rc, d, _ = _run("waste-heat", "--input-power-watts", "3e9", "--efficiency", "0.4")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["useful_power_w"], 1.2e9, places=0)
        self.assertAlmostEqual(d["waste_heat_w"], 1.8e9, places=0)
        ref = thermal.compute_waste_heat(input_power_watts=3e9, efficiency=0.4)
        self.assertAlmostEqual(d["waste_heat_w"], ref["waste_heat_w"], places=3)

    def test_carnot(self):
        rc, d, _ = _run("waste-heat", "--useful-power-watts", "1e9", "--efficiency", "0.9",
                        "--hot-temp-k", "1500", "--cold-temp-k", "300")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["carnot_efficiency"], 0.8, places=6)
        self.assertTrue(d["carnot_limited"])

    def test_transient_c9(self):
        rc, d, _ = _run("waste-heat", "--peak-w", "3e9", "--mean-w", "1e9", "--duty", "0.5",
                        "--pulse-period-s", "100", "--storage-mass-kg", "1000",
                        "--specific-heat-jkgk", "500")
        self.assertEqual(rc, 0)
        self.assertEqual(d["mode"], "transient")
        self.assertAlmostEqual(d["temp_swing_k"], 2e5, places=3)
        ref = thermal.compute_waste_heat(peak_w=3e9, mean_w=1e9, duty=0.5, pulse_period_s=100,
                                         storage_mass_kg=1000, specific_heat_jkgk=500)
        self.assertAlmostEqual(d["temp_swing_k"], ref["temp_swing_k"], places=3)


class RadiatorAreaTest(unittest.TestCase):
    def test_gigawatt_kilometre(self):
        rc, d, _ = _run("radiator-area", "--heat-watts", "1e9", "--radiator-temp-k", "300",
                        "--emissivity", "0.9", "--sides", "2")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["radiator_area_km2"], 1.21, delta=0.01)
        self.assertAlmostEqual(d["blackside_flux_wm2"], 459.3, delta=0.5)
        self.assertIn("scaling_note", d)


class ShieldingTest(unittest.TestCase):
    def test_photon_water(self):
        rc, d, _ = _run("shielding-attenuation", "--material", "water",
                        "--energy-mev", "1.0", "--areal-density-gcm2", "20")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["transmitted_fraction"], 0.2431, places=3)
        self.assertAlmostEqual(d["half_value_layer_gcm2"], 9.80, delta=0.05)
        self.assertFalse(d["is_order_of_magnitude"])

    def test_gcr_caveat(self):
        rc, d, _ = _run("shielding-attenuation", "--mode", "gcr", "--material", "water",
                        "--areal-density-gcm2", "30")
        self.assertEqual(rc, 0)
        self.assertTrue(d["is_order_of_magnitude"])
        self.assertTrue(d["buildup_caveat"])

    def test_csda_proton_c6(self):
        rc, d, _ = _run("shielding-attenuation", "--particle", "proton", "--material", "water",
                        "--energy-mev", "100", "--areal-density-gcm2", "5")
        self.assertEqual(rc, 0)
        self.assertEqual(d["mode"], "csda")
        self.assertAlmostEqual(d["csda_range_gcm2"], 7.718, places=3)
        self.assertFalse(d["stops_primary"])
        ref = thermal.compute_shielding_attenuation(particle="proton", material="water",
                                                    energy_mev=100, areal_density_gcm2=5)
        self.assertAlmostEqual(d["csda_range_gcm2"], ref["csda_range_gcm2"], places=6)

    def test_layers_c7(self):
        rc, d, _ = _run("shielding-attenuation", "--layers", "water:10, lead:5", "--energy-mev", "1.0")
        self.assertEqual(rc, 0)
        self.assertEqual(len(d["layers"]), 2)
        self.assertIn("total_transmitted_fraction", d)


class ExitCodeMatrixTest(unittest.TestCase):
    def test_curated_errors_exit_1(self):
        for args in (
            ("waste-heat",),                                                         # no power anchor, not transient
            ("waste-heat", "--input-power-watts", "1e9", "--efficiency", "1.5"),     # eta>1
            ("waste-heat", "--input-power-watts", "1e9"),                            # no efficiency anchor
            ("waste-heat", "--input-power-watts", "1e9", "--hot-temp-k", "300", "--cold-temp-k", "1500"),
            ("radiator-area", "--heat-watts", "1e6", "--radiator-temp-k", "300", "--sink-temp-k", "350"),
            ("radiator-area", "--radiator-temp-k", "300"),                           # no heat anchor
            ("shielding-attenuation", "--material", "unobtainium", "--energy-mev", "1.0",
             "--areal-density-gcm2", "10"),                                          # off-grid material
            ("shielding-attenuation", "--areal-density-gcm2", "10", "--material", "water"),  # no energy
            ("shielding-attenuation", "--mode", "gcr", "--areal-density-gcm2", "10",
             "--material", "lead"),                                                  # no bundled GCR Λ
            ("shielding-attenuation", "--particle", "alpha", "--material", "water",
             "--energy-mev", "100", "--areal-density-gcm2", "5"),                    # C6 no bundled alpha
            ("shielding-attenuation", "--layers", "water 20", "--energy-mev", "1.0"),  # C7 malformed token
            ("shielding-attenuation", "--layers", "unobtainium:10", "--energy-mev", "1.0"),  # C7 bad material
            ("waste-heat", "--peak-w", "3e9", "--mean-w", "1e9", "--duty", "0.5",
             "--pulse-period-s", "100", "--storage-mass-kg", "1000"),               # C9 incomplete set
            ("waste-heat", "--peak-w", "1e9", "--mean-w", "3e9", "--duty", "0.5",
             "--pulse-period-s", "100", "--storage-mass-kg", "1000",
             "--specific-heat-jkgk", "500"),                                         # C9 peak<mean
        ):
            rc, d, _ = _run(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_argparse_errors_exit_2(self):
        for args in (
            ("waste-heat", "--input-power-watts", "1e9", "--useful-power-watts", "1e9"),  # mutex both
            ("waste-heat", "--input-power-watts", "abc", "--efficiency", "0.4"),      # non-numeric
            ("radiator-area", "--heat-watts", "1e9"),                                 # missing required temp
            ("radiator-area", "--heat-watts", "1e9", "--radiator-temp-k", "300", "--sides", "3"),  # bad choice
            ("shielding-attenuation", "--mode", "bogus", "--areal-density-gcm2", "10"),  # bad choice
            ("shielding-attenuation", "--particle", "muon", "--areal-density-gcm2", "10"),  # bad particle choice
        ):
            rc, d, _ = _run(*args)
            self.assertEqual(rc, 2, args)


if __name__ == "__main__":
    unittest.main()
