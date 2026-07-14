# tests/test_group_q.py — Phase AK (Group Q) core calculators.
#
# Offline golden-pin tests for core.metric_drive (Q1 metric-drive-power) and
# core.exclusion_boundary (Q2 exclusion-boundary): every acceptance anchor from the request spec
# (metric-drive-power-and-exclusion-boundary-calculators-request.md) + the self-validating error
# matrix + the required cross-checks (Q1 beam side vs beam-sail's reflecting-sail momentum; the
# auto-calibration vs explicit-dial equality). No network, no Qt, no numpy.

import math
import unittest

import core.metric_drive as md
import core.exclusion_boundary as xb
import core.propulsion as propulsion
from core.equations import _C_MS, _STANDARD_GRAVITY


# ─────────────────────────────── Q1 — metric-drive-power ───────────────────────────────

class MetricDrivePowerAnchors(unittest.TestCase):
    def test_anchor1_power_gw_per_n(self):
        # --thrust-n 1 --k 3 → power_gw_per_n = 0.9 (P = 3·1·c = 8.988e8 W).
        r = md.compute_metric_drive_power(thrust_n=1.0, k=3.0)
        self.assertAlmostEqual(r["power_gw_per_n"], 0.899377374, places=6)
        self.assertAlmostEqual(r["propulsion_power_w"], 3.0 * _C_MS, places=0)
        self.assertIn("model_note", r)

    def test_anchor2_9pw_at_1g(self):
        # 1000 t @ 1 g → F = 9.81e6 N, P ≈ 8.83e15 W (≈ 9 PW).
        r = md.compute_metric_drive_power(mass_tonnes=1000.0, accel_g=1.0, k=3.0)
        self.assertAlmostEqual(r["thrust_n"], 1e6 * _STANDARD_GRAVITY, places=0)
        self.assertAlmostEqual(r["propulsion_power_w"], 8.8199e15, delta=1e12)

    def test_anchor3_50g(self):
        r = md.compute_metric_drive_power(mass_tonnes=1000.0, accel_g=50.0, k=3.0)
        self.assertAlmostEqual(r["propulsion_power_w"], 4.4099e17, delta=1e14)

    def test_anchor4_1g_day_leg(self):
        # Δv = 9.81·86400 = 8.476e5 m/s, Δη ≈ 2.826e-3, f_rad ≈ 0.00844 (0.84 %).
        r = md.compute_metric_drive_power(mass_tonnes=1000.0, accel_g=1.0,
                                          duration_days=1.0, k=3.0, fuel="d-t")
        self.assertAlmostEqual(r["rapidity_delta"], 2.826e-3, delta=1e-5)
        self.assertAlmostEqual(r["radiated_mass_fraction"], 0.00844, delta=1e-4)
        # d-t: f_conv = 0.00375, fuel_mass_fraction ≈ 2.25 (ruinous).
        self.assertAlmostEqual(r["fuel_mass_fraction"], 2.251, delta=1e-2)
        self.assertAlmostEqual(r["fuel_mass_kg"], 2.251 * 1e6, delta=1e4)

    def test_anchor4_antimatter_ideal_vs_realistic(self):
        base = dict(mass_tonnes=1000.0, accel_g=1.0, duration_days=1.0, k=3.0, fuel="antimatter-pp")
        ideal = md.compute_metric_drive_power(eta_dir=1.0, **base)      # η_dir 1.0 → ≈ 0.84 %
        self.assertAlmostEqual(ideal["fuel_mass_fraction"], 0.00844, delta=1e-4)
        self.assertEqual(ideal["f_conv"], 1.0)
        realistic = md.compute_metric_drive_power(**base)              # default η_dir 0.5 → ≈ 1.69 %
        self.assertAlmostEqual(realistic["fuel_mass_fraction"], 0.01689, delta=1e-4)
        self.assertEqual(realistic["eta_dir"], 0.5)

    def test_anchor5_constant_velocity(self):
        r = md.compute_metric_drive_power(thrust_n=0.0, k=3.0)
        self.assertEqual(r["propulsion_power_w"], 0.0)
        self.assertEqual(r["radiated_mass_fraction"], 0.0)
        self.assertEqual(r["rapidity_delta"], 0.0)

    def test_anchor6_beam_crossover(self):
        r = md.compute_metric_drive_power(thrust_n=1.0, k=3.0, beam_compare=True)
        b = r["beam_vs_onboard"]
        self.assertAlmostEqual(b["beam_power_gw_per_n"], 0.149896229, places=6)
        self.assertAlmostEqual(b["onboard_power_gw_per_n"], 0.899377374, places=6)
        self.assertEqual(b["crossover_k"], 0.5)
        self.assertEqual(b["winner"], "beam")
        r2 = md.compute_metric_drive_power(thrust_n=1.0, k=0.4, beam_compare=True)
        self.assertEqual(r2["beam_vs_onboard"]["winner"], "onboard")

    def test_anchor7_turn_penalty(self):
        # --turn --integrated-rapidity 0.02 uses 0.02 > the collinear 0.01 case.
        turn = md.compute_metric_drive_power(rapidity=0.01, turn=True,
                                             integrated_rapidity=0.02, k=3.0)
        collinear = md.compute_metric_drive_power(rapidity=0.01, k=3.0)
        self.assertEqual(turn["rapidity_delta"], 0.02)
        self.assertGreater(turn["radiated_mass_fraction"], collinear["radiated_mass_fraction"])

    def test_relativistic_delta_v(self):
        # Δv → 0.9c uses exact atanh: f_rad → 1 − e^(−3·1.472) ≈ 0.988.
        r = md.compute_metric_drive_power(delta_v_c=0.9, k=3.0)
        self.assertAlmostEqual(r["rapidity_delta"], math.atanh(0.9), places=6)
        self.assertAlmostEqual(r["radiated_mass_fraction"], 0.988, delta=1e-3)

    def test_fuel_keys_reuse_ism_tables(self):
        # DRY: pp/dd f-values must equal core.ism_drag_tables._FUSION.
        from core.ism_drag_tables import _FUSION
        self.assertEqual(md._FIELD_FUEL["pp"]["f"], _FUSION["pp"]["f"])
        self.assertEqual(md._FIELD_FUEL["dd"]["f"], _FUSION["dd"]["f"])


class MetricDrivePowerErrors(unittest.TestCase):
    def _err(self, **kw):
        r = md.compute_metric_drive_power(**kw)
        self.assertIn("error", r)
        return r

    def test_k_zero_forbidden(self):
        self._err(thrust_n=1.0, k=0.0)                    # reactionless forbidden

    def test_contradictory_thrust(self):
        self._err(mass_tonnes=1000.0, thrust_n=1.0, accel_g=1.0)

    def test_contradictory_rapidity_sources(self):
        self._err(rapidity=0.01, delta_v_c=0.1)

    def test_rapidity_and_leg(self):
        self._err(mass_tonnes=1.0, rapidity=0.01, accel_g=1.0, duration_days=1.0)

    def test_fconv_nonpositive(self):
        self._err(rapidity=0.01, f_conv=0.0)

    def test_eta_dir_without_fuel(self):
        self._err(rapidity=0.01, eta_dir=0.5)

    def test_turn_without_integrated(self):
        self._err(rapidity=0.01, turn=True)

    def test_integrated_below_net(self):
        self._err(rapidity=0.05, turn=True, integrated_rapidity=0.01)

    def test_superluminal_delta_v(self):
        self._err(delta_v_c=1.0)

    def test_both_mass_units(self):
        self._err(mass_kg=1.0, mass_tonnes=1.0, thrust_n=1.0)

    def test_unknown_fuel(self):
        self._err(rapidity=0.01, fuel="unobtainium")


class MetricDriveSelfConsistent(unittest.TestCase):
    """R6 (Phase AL) — the self-consistent fuel-bill / feasibility-wall anchors
    (metric-drive-power-followups.md; all 7 hand-derived 2026-07-13)."""

    def _leg(self, days, fuel, k, **kw):
        return md.compute_metric_drive_power(
            mass_tonnes=1000.0, accel_g=1.0, duration_days=days,
            fuel=fuel, k=k, self_consistent=True, **kw)

    def test_anchor1_dt_1gday_k3_infeasible(self):
        r = self._leg(1, "d-t", 3)
        self.assertFalse(r["feasible"])
        self.assertIsNone(r["fuel_mass_fraction_sc"])
        self.assertAlmostEqual(r["k_wall"], 1.3293, places=3)
        self.assertAlmostEqual(r["lifetime_delta_v_budget_kms"], 375.4, delta=0.1)

    def test_anchor2_dt_1gday_k1(self):
        r = self._leg(1, "d-t", 1)
        self.assertTrue(r["feasible"])
        self.assertAlmostEqual(r["fuel_mass_fraction_sc"], 3.0422, places=3)
        # first-order field must stay unchanged (0.753 at k=1).
        self.assertAlmostEqual(r["fuel_mass_fraction"], 0.7526, places=3)

    def test_anchor3_antimatter_25gday_k3(self):
        r = self._leg(25, "antimatter-pp", 3)
        self.assertAlmostEqual(r["fuel_mass_fraction_sc"], 0.5291, places=3)
        self.assertAlmostEqual(r["fuel_mass_fraction"], 0.383, places=2)

    def test_anchor4_antimatter_50gday(self):
        self.assertAlmostEqual(self._leg(50, "antimatter-pp", 3)["fuel_mass_fraction_sc"],
                               1.3481, places=3)
        self.assertAlmostEqual(self._leg(50, "antimatter-pp", 1)["fuel_mass_fraction_sc"],
                               0.3291, places=3)

    def test_anchor5_vent_dt_1gday_k3(self):
        r = self._leg(1, "d-t", 3, ash="vent")
        self.assertTrue(r["feasible"])
        self.assertIsNone(r["k_wall"])
        self.assertAlmostEqual(r["fuel_mass_fraction_sc"], 8.5929, places=3)

    def test_anchor6_small_delta_eta_agrees_with_first_order(self):
        # sc → first-order as Δη → 0 (rapidity 1e-5, keep mode).
        r = md.compute_metric_drive_power(rapidity=1e-5, fuel="d-t", k=3.0,
                                          self_consistent=True)
        fo, sc = r["fuel_mass_fraction"], r["fuel_mass_fraction_sc"]
        self.assertLess(abs(sc - fo) / fo, 0.01)

    def test_anchor7_vent_without_self_consistent_errors(self):
        r = md.compute_metric_drive_power(rapidity=0.01, fuel="d-t", ash="vent")
        self.assertIn("error", r)

    def test_keep_requires_fuel_preset(self):
        # --f-conv alone can't split f from η_dir for keep mode.
        r = md.compute_metric_drive_power(rapidity=0.01, f_conv=0.001, self_consistent=True)
        self.assertIn("error", r)

    def test_no_maneuver_errors(self):
        r = md.compute_metric_drive_power(thrust_n=1.0, fuel="d-t", self_consistent=True)
        self.assertIn("error", r)

    def test_back_compat_no_sc_keys_by_default(self):
        r = md.compute_metric_drive_power(mass_tonnes=1000.0, accel_g=1.0, duration_days=1.0,
                                          fuel="d-t")
        self.assertNotIn("feasible", r)
        self.assertNotIn("fuel_mass_fraction_sc", r)


class MetricDriveBeamCrossCheck(unittest.TestCase):
    """Q1's beam side must agree with beam-sail's reflecting-sail momentum (2P/c)."""

    def test_reflecting_sail_momentum_matches(self):
        # A reflecting sail (R=1) on power P gives thrust 2P/c → beam power per newton = c/2.
        bs = propulsion.compute_beam_sail(beam_power_w=1e9, sail_mass_kg=1.0, reflectivity=1.0)
        beam_power_per_n = 1e9 / bs["thrust_n"]           # W per N of thrust
        md_beam = md.compute_metric_drive_power(thrust_n=1.0, k=3.0, beam_compare=True)
        self.assertAlmostEqual(md_beam["beam_vs_onboard"]["beam_power_gw_per_n"] * 1e9,
                               beam_power_per_n, delta=1.0)
        self.assertAlmostEqual(beam_power_per_n, _C_MS / 2.0, delta=1.0)


# ─────────────────────────────── Q2 — exclusion-boundary ───────────────────────────────

class ExclusionBoundaryAnchors(unittest.TestCase):
    def test_anchor1_sun(self):
        r = xb.compute_exclusion_boundary(mass_msun=1.0)      # defaults: α 1/3, cal 47.5
        self.assertAlmostEqual(r["r_ex_au"], 47.5, places=6)
        self.assertIn(r["forcing_class"], ("checkpoint", "harbor"))
        self.assertIn("model_note", r)

    def test_anchor2_tenth_msun_scan(self):
        r = xb.compute_exclusion_boundary(mass_msun=0.1, scan_alpha=True)
        self.assertAlmostEqual(r["r_ex_au_alpha_third"], 47.5 * 0.1 ** (1 / 3), places=4)
        self.assertAlmostEqual(r["r_ex_au_alpha_half"], 47.5 * 0.1 ** 0.5, places=4)
        self.assertAlmostEqual(r["r_ex_au_alpha_third"], 22.05, delta=0.01)
        self.assertEqual(r["forcing_class"], "checkpoint")

    def test_anchor3_ten_msun_harbor(self):
        r = xb.compute_exclusion_boundary(mass_msun=10.0, scan_alpha=True)
        self.assertAlmostEqual(r["r_ex_au_alpha_third"], 102.34, delta=0.02)
        self.assertAlmostEqual(r["r_ex_au_alpha_half"], 150.21, delta=0.02)
        self.assertEqual(r["forcing_class"], "harbor")

    def test_anchor4_brown_dwarf_optional(self):
        r = xb.compute_exclusion_boundary(mass_msun=0.0008)
        self.assertLess(r["r_ex_au"], 10.0)
        self.assertIn(r["forcing_class"], ("optional", "checkpoint"))

    def test_anchor5_explicit_dial_overrides(self):
        r = xb.compute_exclusion_boundary(mass_msun=1.0, dial=100.0, alpha=0.5)
        self.assertAlmostEqual(r["r_ex_au"], 100.0, places=6)
        self.assertEqual(r["dial"], 100.0)

    def test_anchor6_wind_term_solar_is_unity(self):
        r = xb.compute_exclusion_boundary(mass_msun=1.0, gamma=0.5,
                                          mass_loss_msun_yr=2e-14, calibration_au=47.5)
        self.assertAlmostEqual(r["r_ex_au"], 47.5, places=6)
        # A hot-star wind pushes it far out.
        hot = xb.compute_exclusion_boundary(mass_msun=1.0, gamma=0.5, mass_loss_msun_yr=1e-6)
        self.assertGreater(hot["r_ex_au"], 47.5)

    def test_autocal_equals_explicit_sun_dial(self):
        # Auto-calibration and an explicit --dial 47.5 give the identical Sun row.
        auto = xb.compute_exclusion_boundary(mass_msun=1.0)
        explicit = xb.compute_exclusion_boundary(mass_msun=1.0, dial=47.5)
        self.assertEqual(auto["r_ex_au"], explicit["r_ex_au"])

    def test_alpha_edges_bracket_default(self):
        r = xb.compute_exclusion_boundary(mass_msun=5.0, scan_alpha=True)
        self.assertLess(r["r_ex_au_alpha_third"], r["r_ex_au_alpha_half"])  # M>1 → half > third


class ExclusionBoundaryErrors(unittest.TestCase):
    def _err(self, **kw):
        r = xb.compute_exclusion_boundary(**kw)
        self.assertIn("error", r)
        return r

    def test_anchor7_wind_exponent_without_wind(self):
        r = self._err(mass_msun=1.0, gamma=0.5)
        self.assertIn("wind exponent set without", r["error"])

    def test_mass_nonpositive(self):
        self._err(mass_msun=0.0)

    def test_negative_exponent(self):
        self._err(mass_msun=1.0, alpha=-0.5)

    def test_dial_nonpositive(self):
        self._err(mass_msun=1.0, dial=0.0)

    def test_calibration_nonpositive(self):
        self._err(mass_msun=1.0, calibration_au=0.0)

    def test_beta_without_luminosity(self):
        self._err(mass_msun=1.0, beta=0.5, luminosity_lsun=0.0)


if __name__ == "__main__":
    unittest.main()
