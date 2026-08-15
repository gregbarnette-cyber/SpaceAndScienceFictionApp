# tests/test_salvo.py — Phase AT (Packet 38.1) W1 salvo-exchange core acceptance.
#
# The Hughes Ch. 13 golden pins (V1–V8 + the recovered-composite grand-melee/melee/distribute/wave
# pins from WB MSG 025, and the layered-defense pins from WB MSG 027), plus the validation matrix
# and determinism. All literature (Hughes) + hand-derived; each anchor is independent of the tool.

import math
import unittest

from core.salvo import compute_salvo_exchange as S


class SalvoGoldenPinTest(unittest.TestCase):
    def test_v1_basic_case(self):
        r = S(a_force=10, b_force=10, alpha=3, beta=3, a1_staying=2, b1_staying=2,
              a3_defense=2, b3_defense=2)
        self.assertAlmostEqual(r["delta_a"], 5.0)
        self.assertAlmostEqual(r["delta_b"], 5.0)
        self.assertAlmostEqual(r["frac_loss_a"], 0.5)
        self.assertAlmostEqual(r["exchange_ratio"], 1.0)

    def test_v2_victory_with_more_numbers(self):
        r = S(a_force=10, b_force=15, alpha=3, beta=3, a1_staying=2, b1_staying=2,
              a3_defense=2, b3_defense=2)
        self.assertAlmostEqual(r["delta_b"], 0.0)
        self.assertAlmostEqual(r["delta_a"], 10.0)          # 12.5 clamped to 10
        self.assertAlmostEqual(r["overkill_a"], 2.5)
        self.assertAlmostEqual(r["survivors_a"], 0.0)

    def test_v3_single_heavy_attacker(self):
        r = S(a_force=3, b_force=1, alpha=0, beta=6, a1_staying=1, b1_staying=1,
              a3_defense=1, b3_defense=0)
        self.assertAlmostEqual(r["delta_a"], 3.0)

    def test_v4_double_staying_halves_delta(self):
        # Doubling the defender's staying power halves the delta inflicted (un-clamped).
        base = S(a_force=1, b_force=3, alpha=6, beta=0, a1_staying=1, b1_staying=1,
                 a3_defense=0, b3_defense=1)
        doubled = S(a_force=1, b_force=3, alpha=6, beta=0, a1_staying=1, b1_staying=2,
                    a3_defense=0, b3_defense=1)
        self.assertAlmostEqual(base["delta_b"], 3.0)
        self.assertAlmostEqual(doubled["delta_b"], 1.5)     # halved

    def test_v5_solve_force_composite(self):
        # Hughes composite (WB MSG 025): S=7 defender, per-T β=3.88, solve ΔS=7 → T=3.61 → ceil 4.
        r = S(mode="solve-force", a_force=7, a1_staying=1, b1_staying=1, a3_defense=1,
              beta=3.88, alpha=1, solve_for="b", target_delta=7, target_side="a")
        self.assertAlmostEqual(r["required_force_exact"], 14 / 3.88, places=6)
        self.assertEqual(r["integer_wave"], 4)

    def test_v6_aegis_annihilation_and_needed(self):
        # ΔB/B=1 → 12 destroyed; ΔA/A=1 with a1=2 → B needs 3.
        r1 = S(mode="solve-force", a_force=1, alpha=24, a1_staying=1, b1_staying=1, b3_defense=1,
               beta=1, solve_for="b", target_frac_loss=1.0, target_side="b")
        self.assertAlmostEqual(r1["required_force_exact"], 12.0)
        r2 = S(mode="solve-force", a_force=1, a1_staying=2, b1_staying=1, a3_defense=16, beta=6,
               alpha=1, solve_for="b", target_frac_loss=1.0, target_side="a")
        self.assertAlmostEqual(r2["required_force_exact"], 3.0)

    def test_v7_break_even_numerical_superiority(self):
        # A quality 2× B on α, a₃, a₁ → B must be 2× as numerous for parity.
        r = S(mode="break-even", a_force=1, b_force=1, alpha=2, beta=1, a1_staying=2, b1_staying=1,
              a3_defense=2, b3_defense=1)
        self.assertAlmostEqual(r["break_even_force_ratio"], 2.0)

    def test_v8_leaker_floor(self):
        # 90% effective defense (L=0.10), B fires 12 good ASCMs at A=1 → ≈1.2 leaks (a1=1).
        r = S(a_force=1, b_force=1, alpha=0, beta=12, a1_staying=1, b1_staying=1,
              a3_defense=1000, b3_defense=0, leak_b=0.10)   # defence overwhelms raw → floor binds
        self.assertAlmostEqual(r["delta_a"], 1.0)           # clamped from 1.2 (floor 0.1·12)
        self.assertAlmostEqual(r["overkill_a"], 0.2, places=6)

    def test_composite_grand_melee_and_melee(self):
        # One simultaneous call reproduces both Hughes results: T annihilates S 12.9×; S does 0 to T.
        r = S(a_force=7, b_force=25, alpha=30 / 7, beta=97 / 25, a1_staying=1, b1_staying=1.5,
              a3_defense=1, b3_defense=1.5)
        self.assertAlmostEqual(r["delta_a"] + r["overkill_a"], 90.0)   # un-clamped 90
        self.assertAlmostEqual(r["delta_a"], 7.0)                      # clamp to force
        self.assertAlmostEqual(90.0 / 7.0, 12.857, places=2)
        self.assertAlmostEqual(r["delta_b"], 0.0)

    def test_distribute_concentration_of_fire(self):
        for f, expected in ((12 / 25, 8.0), (10 / 25, 10.0)):
            r = S(mode="distribute", a_force=7, b_force=25, alpha=30 / 7, a1_staying=1,
                  b1_staying=1.5, b3_defense=1.5, fire_fraction=f)
            self.assertAlmostEqual(r["delta_b"], expected)

    def test_sequential_two_sided_wave(self):
        # T's wave of 4 vs S=7 (composite): mutual annihilation. S's offence kills the 4-ship wave
        # (ΔT=16 → clamp 4, overkill 12) AND the wave's FULL salvo kills S (Δ=8.52 → clamp 7, overkill
        # 1.52), reduced only by S's defence a₃=1.0 (simultaneous). WB MSG 025 + 029.
        r = S(mode="sequential-waves", first="a", a_force=25, b_force=7, alpha=3.88, beta=30 / 7,
              a1_staying=1.5, b1_staying=1.0, a3_defense=1.5, b3_defense=1.0, wave_size=4, n_waves=1)
        w = r["waves"][0]
        self.assertAlmostEqual(w["wave_losses"], 4.0)
        self.assertAlmostEqual(w["wave_overkill"], 12.0)
        self.assertAlmostEqual(w["defender_delta"], 7.0)          # WB MSG 029: NOT 0
        self.assertAlmostEqual(w["defender_overkill"], 1.52, places=2)

    def test_sequential_defender_damage_matches_simultaneous(self):
        # WB MSG 029: a wave's effect on the defender equals the base simultaneous result.
        # S=50 defender vs a 15-ship wave → Δ_S = (3.88·15 − 1.0·50)/1.0 = 8.2.
        r = S(mode="sequential-waves", first="a", a_force=15, b_force=50, alpha=3.88, beta=30 / 7,
              a1_staying=1.5, b1_staying=1.0, a3_defense=1.5, b3_defense=1.0, wave_size=15, n_waves=1)
        self.assertAlmostEqual(r["waves"][0]["defender_delta"], 8.2, places=2)

    def test_sequential_defender_preempts(self):
        # Out-ranging (opt-in): defender offence annihilates the wave first → no survivors deliver.
        r = S(mode="sequential-waves", first="a", a_force=25, b_force=7, alpha=3.88, beta=30 / 7,
              a1_staying=1.5, b1_staying=1.0, a3_defense=1.5, b3_defense=1.0, wave_size=4, n_waves=1,
              defender_preempts=True)
        self.assertAlmostEqual(r["waves"][0]["wave_losses"], 4.0)     # wave annihilated
        self.assertAlmostEqual(r["waves"][0]["defender_delta"], 0.0)  # today's out-ranging behaviour

    def test_sequential_defender_magazine_runs_dry(self):
        # A 1-salvo magazine: wave 2 gets NO defender offence (defender_fired False, wave_losses 0),
        # but the wave's salvo still damages the defender via a₃ (defence reloads — shot-your-bolt).
        r = S(mode="sequential-waves", first="a", a_force=8, b_force=10, alpha=3.88, beta=30 / 7,
              a1_staying=1.5, b1_staying=2.0, a3_defense=1.5, b3_defense=1.0, wave_size=4, n_waves=2,
              defender_magazine=1)
        self.assertTrue(r["waves"][0]["defender_fired"])
        self.assertFalse(r["waves"][1]["defender_fired"])
        self.assertAlmostEqual(r["waves"][1]["wave_losses"], 0.0)
        self.assertGreater(r["waves"][1]["defender_delta"], 0.0)      # still takes wave damage

    def test_layered_defense_cascade(self):
        r = S(mode="layered-defense", inbound_salvo=100, rings="1:30:0.1, 1:30:0.1, 1:30:0.1")
        self.assertAlmostEqual(r["survivors_to_target"], 10.0)
        self.assertAlmostEqual(r["rings"][0]["leaked"], 70.0)
        self.assertAlmostEqual(r["rings"][1]["leaked"], 40.0)

    def test_layered_saturation_floor(self):
        r = S(mode="layered-defense", inbound_salvo=20, rings="1:30:0.1")
        self.assertAlmostEqual(r["survivors_to_target"], 2.0)   # max(20-30, 2)

    def test_layered_target_staying(self):
        r = S(mode="layered-defense", inbound_salvo=100, rings="1:30:0.1, 1:30:0.1, 1:30:0.1",
              target_staying=2.0)
        self.assertAlmostEqual(r["delta_target"], 5.0)          # 10 leakers / 2

    def test_first_strike_two_pulses(self):
        r = S(mode="first-strike", first="a", a_force=10, b_force=10, alpha=3, beta=3,
              a1_staying=2, b1_staying=2, a3_defense=2, b3_defense=2)
        self.assertAlmostEqual(r["delta_b"], 5.0)               # pulse 1
        self.assertAlmostEqual(r["delta_a"], 0.0)               # pulse 2 (5 survivors can't hurt A)
        self.assertEqual(len(r["pulses"]), 2)

    def test_salvo_hitprob_derivation(self):
        # α = a2·H : salvo 6 × H 0.5 = 3 reproduces V1.
        r = S(a_force=10, b_force=10, a_salvo=6, a_hitprob=0.5, b_salvo=6, b_hitprob=0.5,
              a1_staying=2, b1_staying=2, a3_defense=2, b3_defense=2)
        self.assertAlmostEqual(r["delta_b"], 5.0)


class SalvoValidationTest(unittest.TestCase):
    def _err(self, **kw):
        r = S(**kw)
        self.assertIn("error", r)

    def test_bad_mode(self):
        self._err(mode="nuke", a_force=1, b_force=1, alpha=1, beta=1, a1_staying=1, b1_staying=1)

    def test_missing_staying(self):
        self._err(a_force=10, b_force=10, alpha=3, beta=3)      # no staying power

    def test_sigma_out_of_range(self):
        self._err(a_force=1, b_force=1, alpha=1, beta=1, a1_staying=1, b1_staying=1, sigma_a=1.5)

    def test_both_striking_forms(self):
        self._err(a_force=1, b_force=1, alpha=3, a_salvo=6, a_hitprob=0.5, beta=1,
                  a1_staying=1, b1_staying=1)

    def test_solve_force_needs_target(self):
        self._err(mode="solve-force", a_force=7, a1_staying=1, b1_staying=1, beta=4, solve_for="b")

    def test_solve_force_two_targets(self):
        self._err(mode="solve-force", a_force=7, a1_staying=1, b1_staying=1, beta=4, solve_for="b",
                  target_delta=7, target_frac_loss=1.0)

    def test_distribute_bad_fraction(self):
        self._err(mode="distribute", a_force=7, b_force=25, alpha=4, a1_staying=1, b1_staying=1,
                  fire_fraction=1.5)

    def test_layered_malformed_rings(self):
        self._err(mode="layered-defense", inbound_salvo=100, rings="junk")

    def test_first_strike_needs_first(self):
        self._err(mode="first-strike", a_force=10, b_force=10, alpha=3, beta=3,
                  a1_staying=2, b1_staying=2)

    def test_determinism(self):
        kw = dict(a_force=10, b_force=13, alpha=3.1, beta=2.7, a1_staying=2, b1_staying=1.5,
                  a3_defense=2, b3_defense=1.8, sigma_a=0.8, leak_b=0.2)
        self.assertEqual(S(**kw), S(**kw))


if __name__ == "__main__":
    unittest.main()
