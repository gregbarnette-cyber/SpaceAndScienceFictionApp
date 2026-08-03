# tests/test_query_power.py — Phase AL (Group R) query.py contract.
#
# Offline subprocess tests mirroring tests/test_query_thermal.py: happy-path JSON shape, core parity
# (subprocess == in-process), and the self-validating exit-code matrix (curated {"error"} -> exit 1;
# argparse -> exit 2) for the 10 Phase-AL subcommands (R1/R2/R3/R4/R7/R8/R9/R10 + T1/T2). The R6
# self-consistent metric-drive extension is covered in tests/test_group_q.py.

import unittest

import core.power as power
import core.energy_storage as energy_storage
import core.power_tables as power_tables
import core.thermal as thermal
from tests._queryharness import make_env, run_query, run_query_inproc

_ENV = make_env("phase_al_throwaway.db")


def _run(*cmd_args):
    return run_query(*cmd_args, env=_ENV)


class HappyPathTest(unittest.TestCase):
    def test_annihilation_power_train(self):
        rc, d, _ = _run("annihilation-power-train", "--mass-flow-kgs", "1e-9")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["power_directed_w"], 4.4937759e7, delta=1e2)
        ref = power.compute_annihilation_power_train(mass_flow_kgs=1e-9)
        self.assertAlmostEqual(d["power_gamma_w"], ref["power_gamma_w"], places=3)

    def test_antimatter_production(self):
        rc, d, _ = _run("antimatter-production", "--stored-mass-kg", "1e-9",
                        "--production-efficiency", "1e-4")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["threshold_floor_efficiency"], 1.0 / 3.0, places=6)
        self.assertAlmostEqual(d["energy_in_j"], 8.9875518e11, delta=1e6)

    def test_reactor_net_power(self):
        rc, d, _ = _run("reactor-net-power", "--gross-power-w", "1e9",
                        "--thermal-efficiency", "0.4", "--q-plasma", "10")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["net_power_w"], 3.6e8, places=1)
        self.assertAlmostEqual(d["engineering_breakeven_q"], 2.5, places=6)

    def test_beamed_power_delivery(self):
        rc, d, _ = _run("beamed-power-delivery", "--wavelength-m", "1e-6", "--tx-aperture-m", "10",
                        "--rx-aperture-m", "100", "--range-m", "1.496e11")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["capture_fraction"], 7.505e-6, delta=1e-8)

    def test_fusion_lawson(self):
        rc, d, _ = _run("fusion-lawson", "--fuel", "d-t", "--triple-product", "3e21")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["q_fusion"], 1.0, places=6)
        self.assertTrue(d["ignited"])

    def test_heat_pump(self):
        rc, d, _ = _run("heat-pump", "--cold-temp-k", "300", "--hot-temp-k", "320",
                        "--heat-lifted-w", "1")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["cop_cool_carnot"], 15.0, places=6)
        ref = thermal.compute_heat_pump(cold_temp_k=300, hot_temp_k=320, heat_lifted_w=1.0)
        self.assertAlmostEqual(d["heat_rejected_w"], ref["heat_rejected_w"], places=6)

    def test_flywheel_storage(self):
        rc, d, _ = _run("flywheel-storage", "--tensile-strength-pa", "5e9",
                        "--density-kgm3", "1800", "--shape-factor", "0.5")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["specific_energy_j_kg"], 1.388889e6, delta=1.0)

    def test_smes_storage(self):
        rc, d, _ = _run("smes-storage", "--field-t", "20")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["energy_density_j_m3"], 1.5915e8, delta=1e4)

    def test_energy_storage_lookup_and_compute(self):
        rc, d, _ = _run("energy-storage", "--class", "li-ion")
        self.assertEqual(rc, 0)
        self.assertEqual(d["class"], "li-ion")
        rc, d, _ = _run("energy-storage", "--mass-kg", "1000", "--specific-heat-jkgk", "4186",
                        "--delta-t-k", "100")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["stored_energy_j"], 4.186e8, places=1)

    def test_reactor_power(self):
        rc, d, _ = _run("reactor-power", "--class", "fusion", "--gross-power-w", "1e9")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["core_mass_kg"], 2.0e5, places=1)
        self.assertIn("thermal_pointer", d)


class ExitCodeMatrixTest(unittest.TestCase):
    def test_curated_errors_exit_1(self):
        for args in (
            ("annihilation-power-train",),                                        # no anchor
            ("annihilation-power-train", "--mass-flow-kgs", "-1"),                # <= 0
            ("antimatter-production", "--stored-mass-kg", "1e-9"),                # no efficiency
            ("antimatter-production", "--stored-mass-kg", "1e-9",
             "--production-efficiency", "1.5"),                                   # eff > 1
            ("reactor-net-power", "--gross-power-w", "1e9", "--thermal-efficiency", "1.5"),
            ("reactor-net-power", "--gross-power-w", "1e9", "--thermal-efficiency", "0.4",
             "--recirculating-fraction", "1.0"),                                  # recirc >= 1
            ("beamed-power-delivery", "--tx-aperture-m", "10", "--rx-aperture-m", "100",
             "--range-m", "1e11"),                                                # no wavelength/freq
            ("fusion-lawson", "--fuel", "d-t"),                                   # no triple/parts
            ("fusion-lawson", "--fuel", "d-t", "--density-m3", "1e21", "--temp-kev", "3"),  # partial
            ("heat-pump", "--cold-temp-k", "320", "--hot-temp-k", "300", "--heat-lifted-w", "1"),
            ("heat-pump", "--cold-temp-k", "300", "--hot-temp-k", "320"),         # no load anchor
            ("flywheel-storage", "--tensile-strength-pa", "0", "--density-kgm3", "1800"),
            ("smes-storage", "--field-t", "20", "--tensile-strength-pa", "5e9"),  # sigma w/o rho
            ("energy-storage", "--class", "nope"),                               # unknown class
            ("reactor-power", "--class", "nope"),                                # unknown class
        ):
            rc, d, _ = run_query_inproc(*args)
            self.assertEqual(rc, 1, args)
            self.assertIn("error", d, args)

    def test_argparse_errors_exit_2(self):
        for args in (
            ("annihilation-power-train", "--mass-flow-kgs", "1e-9", "--power-total-w", "1"),  # mutex
            ("annihilation-power-train", "--species", "muon"),                   # bad choice
            ("antimatter-production", "--stored-mass-kg", "1e-9", "--stored-energy-j", "1",
             "--production-efficiency", "1e-4"),                                  # mutex
            ("reactor-net-power", "--gross-power-w", "1e9"),                      # missing required
            ("beamed-power-delivery", "--wavelength-m", "1e-6", "--frequency-hz", "1e14",
             "--tx-aperture-m", "10", "--rx-aperture-m", "100", "--range-m", "1e11"),  # mutex
            ("fusion-lawson", "--fuel", "unobtainium", "--triple-product", "3e21"),  # bad choice
            ("heat-pump", "--cold-temp-k", "300", "--hot-temp-k", "320",
             "--heat-lifted-w", "1", "--work-w", "1"),                           # mutex
            ("flywheel-storage", "--density-kgm3", "1800"),                      # missing required
        ):
            rc, d, _ = run_query_inproc(*args)
            self.assertEqual(rc, 2, args)


class BeamriderQueryTest(unittest.TestCase):
    """U2 (Phase AR) beamrider-relay-spacing query.py contract."""

    def test_happy(self):
        rc, d, _ = _run("beamrider-relay-spacing", "--wavelength-m", "1e-6",
                        "--tx-aperture-m", "1000", "--rx-aperture-m", "1000",
                        "--total-range-ly", "4")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d["relay_spacing_m"], 5.79595722e11, delta=1e5)
        self.assertEqual(d["n_relays"], 65292)

    def test_curated_error_exit_1(self):
        rc, d, _ = _run("beamrider-relay-spacing", "--wavelength-m", "1e-6",
                        "--tx-aperture-m", "0", "--rx-aperture-m", "1000")
        self.assertEqual(rc, 1)
        self.assertIn("error", d)

    def test_argparse_exit_2(self):
        rc, _d, _ = _run("beamrider-relay-spacing", "--tx-aperture-m", "1000",
                         "--rx-aperture-m", "1000")   # no λ/f (required group)
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
