# tests/test_warp.py — Phase AH (Group N) core calculators.
#
# AH·1 checkpoint: N1 alcubierre-energy, 'original' formulation only — the numeric T⁰⁰ integral.
# Golden pins: the 3.4e45 J anchor (energy_j; energy_kg_equiv = E/c² ≈ -3.75e28), the ∝1/Δ scaling,
# a convergence pin (the value is resolution-stable), determinism, and the self-validating error
# matrix. No network/Qt/DB.

import unittest

import core.warp as warp


class AlcubierreEnergyOriginalTest(unittest.TestCase):
    def test_anchor(self):
        d = warp.compute_alcubierre_energy(bubble_radius_m=100, velocity_c=1.0, wall_thickness_m=10)
        # energy_j is the joule value; energy_kg_equiv = energy_j / c² (mass-equivalent).
        self.assertAlmostEqual(d["energy_j"], -3.373e45, delta=2e42)
        self.assertAlmostEqual(d["energy_kg_equiv"], -3.753e28, delta=2e25)
        from core.equations import _C_MS
        self.assertAlmostEqual(d["energy_kg_equiv"], d["energy_j"] / _C_MS ** 2, delta=1)
        self.assertLess(d["energy_j"], 0)                       # always negative → exotic
        self.assertEqual(d["energy_condition_status"], "NEC-violating-exotic")
        self.assertEqual(d["formulation"], "original")

    def test_pfenning_ford_solar_mass_anchor(self):
        # Δ=1 m ⇒ ≈ 0.19 M☉ (Pfenning & Ford 1997 "~a quarter of a solar mass").
        d = warp.compute_alcubierre_energy(bubble_radius_m=100, velocity_c=1.0, wall_thickness_m=1)
        solar_masses = abs(d["energy_kg_equiv"]) / 1.989e30
        self.assertAlmostEqual(solar_masses, 0.19, delta=0.02)

    def test_inverse_delta_scaling(self):
        # E ∝ 1/Δ: a 10× thinner wall → ~10× the magnitude
        e10 = warp.compute_alcubierre_energy(bubble_radius_m=100, velocity_c=1.0, wall_thickness_m=10)["energy_kg_equiv"]
        e1 = warp.compute_alcubierre_energy(bubble_radius_m=100, velocity_c=1.0, wall_thickness_m=1)["energy_kg_equiv"]
        self.assertAlmostEqual(abs(e1 / e10), 10.0, delta=0.1)

    def test_velocity_squared_scaling(self):
        # E ∝ v_s² : doubling v_s → 4× the magnitude
        e1 = warp.compute_alcubierre_energy(bubble_radius_m=100, velocity_c=1.0, wall_thickness_m=10)["energy_kg_equiv"]
        e2 = warp.compute_alcubierre_energy(bubble_radius_m=100, velocity_c=2.0, wall_thickness_m=10)["energy_kg_equiv"]
        self.assertAlmostEqual(abs(e2 / e1), 4.0, delta=0.01)

    def test_convergence_and_determinism(self):
        # The public value is resolution-stable (deterministic; pinned to high precision)
        a = warp.compute_alcubierre_energy(bubble_radius_m=100, velocity_c=1.0, wall_thickness_m=10)
        b = warp.compute_alcubierre_energy(bubble_radius_m=100, velocity_c=1.0, wall_thickness_m=10)
        self.assertEqual(a["energy_kg_equiv"], b["energy_kg_equiv"])
        # cross-check the standalone helper against a 4× finer manual Simpson integration
        import math
        from core.equations import _G, _C_MS
        ref, n, _ = warp._alcubierre_energy_j(100.0, _C_MS, 10.0)
        fine = _fine_integral(100.0, _C_MS, 10.0, n * 4)
        self.assertAlmostEqual(ref / fine, 1.0, delta=1e-6)

    def test_subluminal_flag(self):
        self.assertTrue(warp.compute_alcubierre_energy(bubble_radius_m=100, velocity_c=0.5, wall_thickness_m=10)["subluminal"])
        self.assertFalse(warp.compute_alcubierre_energy(bubble_radius_m=100, velocity_c=1.0, wall_thickness_m=10)["subluminal"])
        self.assertFalse(warp.compute_alcubierre_energy(bubble_radius_m=100, velocity_c=2.0, wall_thickness_m=10)["subluminal"])

    def test_errors(self):
        self.assertIn("error", warp.compute_alcubierre_energy(velocity_c=1, wall_thickness_m=10))       # no radius
        self.assertIn("error", warp.compute_alcubierre_energy(bubble_radius_m=100, wall_thickness_m=10))  # no velocity
        self.assertIn("error", warp.compute_alcubierre_energy(bubble_radius_m=100, velocity_c=1))        # no wall
        self.assertIn("error", warp.compute_alcubierre_energy(bubble_radius_m=-1, velocity_c=1, wall_thickness_m=10))
        self.assertIn("error", warp.compute_alcubierre_energy(bubble_radius_m=100, velocity_c=1,
                                                              wall_thickness_m=10, formulation="banana"))  # unknown


class AlcubierreLadderRegimeTest(unittest.TestCase):
    # AH·2: reduction-formulation ladder + Santiago–Schuster–Visser NEC regime flag.
    def test_regime_truth_table(self):
        expected = {
            "original":        ("NEC-violating-exotic", "NEC-violating-exotic"),
            "van-den-broeck":  ("NEC-violating-exotic", "NEC-violating-exotic"),
            "krasnikov":       ("NEC-violating-exotic", "NEC-violating-exotic"),
            "white":           ("NEC-violating-exotic", "NEC-violating-exotic"),
            "bobrick-martire": ("positive-energy-possible", "NEC-violating-exotic"),
            "physical-2024":   ("positive-energy-possible", "NEC-violating-exotic"),
            "lentz":           ("NEC-violating-exotic", "NEC-violating-exotic"),
        }
        for f, (sub_status, super_status) in expected.items():
            sub = warp.compute_alcubierre_energy(bubble_radius_m=100, velocity_c=0.5, wall_thickness_m=10, formulation=f)
            sup = warp.compute_alcubierre_energy(bubble_radius_m=100, velocity_c=2.0, wall_thickness_m=10, formulation=f)
            self.assertEqual(sub["energy_condition_status"], sub_status, f)
            self.assertEqual(sup["energy_condition_status"], super_status, f)

    def test_reductions_report_not_compute(self):
        for f in ("van-den-broeck", "krasnikov", "white", "bobrick-martire", "physical-2024", "lentz"):
            d = warp.compute_alcubierre_energy(bubble_radius_m=100, velocity_c=0.5, wall_thickness_m=10, formulation=f)
            self.assertIsNone(d["energy_j"], f)                 # reported, not recomputed
            self.assertIsNone(d["energy_kg_equiv"], f)
            self.assertTrue(d["published_figure"], f)          # non-empty literature string
            self.assertTrue(d["source"], f)

    def test_original_is_computed(self):
        d = warp.compute_alcubierre_energy(bubble_radius_m=100, velocity_c=1.0, wall_thickness_m=10, formulation="original")
        self.assertIsNotNone(d["energy_j"])
        self.assertIsNone(d["published_figure"])

    def test_contested_flags(self):
        self.assertTrue(warp.compute_alcubierre_energy(bubble_radius_m=10, velocity_c=10, wall_thickness_m=1, formulation="white")["contested"])
        self.assertTrue(warp.compute_alcubierre_energy(bubble_radius_m=100, velocity_c=2, wall_thickness_m=10, formulation="lentz")["contested"])
        self.assertFalse(warp.compute_alcubierre_energy(bubble_radius_m=100, velocity_c=0.5, wall_thickness_m=10, formulation="bobrick-martire")["contested"])

    def test_formulations_list(self):
        self.assertEqual(warp.FORMULATIONS[0], "original")
        self.assertEqual(set(warp.FORMULATIONS), {"original", "van-den-broeck", "krasnikov",
                                                  "white", "bobrick-martire", "physical-2024", "lentz"})


class WarpMetricTest(unittest.TestCase):
    # AH·3: N2 warp-metric — shape function, expansion scalar, wall geometry, natario variant.
    def test_shape_function_anchors(self):
        inside = warp.compute_warp_metric(bubble_radius_m=100, wall_thickness_sigma=0.1, velocity_c=1, r_eval_m=0)
        self.assertAlmostEqual(inside["f_at_r"], 1.0, places=6)          # flat interior
        outside = warp.compute_warp_metric(bubble_radius_m=100, wall_thickness_sigma=0.1, velocity_c=1, r_eval_m=1000)
        self.assertAlmostEqual(outside["f_at_r"], 0.0, places=6)         # flat exterior

    def test_theta_antisymmetric_and_extrema(self):
        d = warp.compute_warp_metric(bubble_radius_m=100, wall_thickness_sigma=0.1, velocity_c=1, r_eval_m=100)
        self.assertLess(d["theta_at_r"], 0)                              # contraction ahead (forward axis)
        # max expansion (behind) and max contraction (ahead) are equal magnitude, opposite sign
        self.assertAlmostEqual(d["max_expansion"], -d["max_contraction"], places=3)
        self.assertGreater(d["max_expansion"], 0)

    def test_wall_region(self):
        d = warp.compute_warp_metric(bubble_radius_m=100, wall_thickness_sigma=0.1, velocity_c=1)
        self.assertLess(d["wall_inner_m"], 100)
        self.assertGreater(d["wall_outer_m"], 100)
        # symmetric about R
        self.assertAlmostEqual(100 - d["wall_inner_m"], d["wall_outer_m"] - 100, places=6)

    def test_natario_zero_expansion(self):
        d = warp.compute_warp_metric(bubble_radius_m=100, wall_thickness_sigma=0.1, velocity_c=1,
                                     r_eval_m=100, variant="natario")
        self.assertEqual(d["theta_at_r"], 0.0)
        self.assertEqual(d["max_expansion"], 0.0)
        self.assertEqual(d["max_contraction"], 0.0)
        self.assertIsNotNone(d["f_at_r"])                               # shape still reported

    def test_profile(self):
        d = warp.compute_warp_metric(bubble_radius_m=100, wall_thickness_sigma=0.1, velocity_c=1, profile=True)
        self.assertTrue(len(d["profile"]) > 100)
        self.assertAlmostEqual(d["profile"][0]["f"], 1.0, places=4)     # starts flat interior
        self.assertAlmostEqual(d["profile"][-1]["f"], 0.0, places=4)    # ends flat exterior
        # without --profile the key is null
        self.assertIsNone(warp.compute_warp_metric(bubble_radius_m=100, wall_thickness_sigma=0.1, velocity_c=1)["profile"])

    def test_errors(self):
        self.assertIn("error", warp.compute_warp_metric(wall_thickness_sigma=0.1, velocity_c=1))       # no radius
        self.assertIn("error", warp.compute_warp_metric(bubble_radius_m=100, velocity_c=1))            # no sigma
        self.assertIn("error", warp.compute_warp_metric(bubble_radius_m=100, wall_thickness_sigma=0.1))  # no velocity
        self.assertIn("error", warp.compute_warp_metric(bubble_radius_m=-1, wall_thickness_sigma=0.1, velocity_c=1))
        self.assertIn("error", warp.compute_warp_metric(bubble_radius_m=100, wall_thickness_sigma=0.1,
                                                        velocity_c=1, r_eval_m=-5))


def _fine_integral(R, v_ms, wall, n):
    """Independent high-resolution Simpson of the same integrand (test cross-check)."""
    import math
    from core.equations import _G, _C_MS
    sigma = 1.0 / wall
    tsr = math.tanh(sigma * R)
    upper = R + 40.0 * wall
    if n % 2:
        n += 1
    h = upper / n

    def sech2(x):
        if abs(x) > 300:
            return 0.0
        ch = math.cosh(x)
        return 1.0 / (ch * ch)

    def ig(r):
        df = sigma * (sech2(sigma * (r + R)) - sech2(sigma * (r - R))) / (2.0 * tsr)
        return df * df * r * r

    tot = ig(0.0) + ig(upper)
    for i in range(1, n):
        tot += (4.0 if i % 2 else 2.0) * ig(i * h)
    return -(_C_MS ** 2 * v_ms ** 2 / (12.0 * _G)) * tot * h / 3.0


if __name__ == "__main__":
    unittest.main()
