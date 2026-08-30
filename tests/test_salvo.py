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


class SaturationStreamTest(unittest.TestCase):
    """CR-A (Packet 38.2): sustained-stream / saturation-over-dwell. Hand-derived + degenerate-to-layered
    anchors, all independent of the tool."""

    def test_hand_anchor_400_over_4(self):
        # WB pin: T=400 over N=4, one ring cap=20 regen=20 leak=0 → stream leaks 320, single pulse 380,
        # duration_advantage 60.
        r = S(mode="saturation-stream", stream_total=400, dwell_intervals=4, stream_rings="20:20:0")
        self.assertAlmostEqual(r["cumulative_leak"], 320.0)
        self.assertEqual(len(r["per_interval_leak"]), 4)
        for v in r["per_interval_leak"]:
            self.assertAlmostEqual(v, 80.0)
        self.assertAlmostEqual(r["equivalent_pulse_leak"], 380.0)
        self.assertAlmostEqual(r["duration_advantage"], 60.0)

    def test_degenerate_reproduces_layered(self):
        # N=1, regen=0, cap = δ·b₃ (=30) of a layered ring, σ=1 → cumulative_leak == survivors_to_target.
        lay = S(mode="layered-defense", inbound_salvo=100, rings="1:30:0.1, 1:30:0.1, 1:30:0.1")
        strm = S(mode="saturation-stream", stream_total=100, dwell_intervals=1,
                 stream_rings="30:0:0.1, 30:0:0.1, 30:0:0.1")
        self.assertAlmostEqual(strm["cumulative_leak"], lay["survivors_to_target"])
        self.assertAlmostEqual(strm["cumulative_leak"], 10.0)

    def test_degenerate_saturation_floor(self):
        # The leak floor: max(incoming − cap, leak·incoming) == incoming − min(cap, incoming − leak·incoming).
        lay = S(mode="layered-defense", inbound_salvo=20, rings="1:30:0.1")
        strm = S(mode="saturation-stream", stream_total=20, dwell_intervals=1, stream_rings="30:0:0.1")
        self.assertAlmostEqual(strm["cumulative_leak"], lay["survivors_to_target"])
        self.assertAlmostEqual(strm["cumulative_leak"], 2.0)          # max(20−30, 2)

    def test_regen_endpoints(self):
        # regen=0 one-shot: fires cap once then depletes (80 + 100·3 = 380); regen=cap full-recovers (320).
        one_shot = S(mode="saturation-stream", stream_total=400, dwell_intervals=4, stream_rings="20:0:0")
        full = S(mode="saturation-stream", stream_total=400, dwell_intervals=4, stream_rings="20:20:0")
        self.assertAlmostEqual(one_shot["cumulative_leak"], 380.0)
        self.assertAlmostEqual(full["cumulative_leak"], 320.0)

    def test_partial_regen(self):
        # cap=20, regen=10: leaks 80, 90, 90, 90 → 350 (reservoir settles at 10 after interval 1).
        r = S(mode="saturation-stream", stream_total=400, dwell_intervals=4, stream_rings="20:10:0")
        self.assertAlmostEqual(r["cumulative_leak"], 350.0)

    def test_profiles_sum_and_shape(self):
        for prof in ("flat", "ramp", "front-loaded"):
            r = S(mode="saturation-stream", stream_total=400, dwell_intervals=4,
                  stream_rings="20:20:0", profile=prof)
            self.assertAlmostEqual(sum(r["arrivals_per_interval"]), 400.0)
        ramp = S(mode="saturation-stream", stream_total=400, dwell_intervals=4,
                 stream_rings="20:20:0", profile="ramp")["arrivals_per_interval"]
        self.assertLess(ramp[0], ramp[-1])                            # increasing
        fl = S(mode="saturation-stream", stream_total=400, dwell_intervals=4,
               stream_rings="20:20:0", profile="front-loaded")["arrivals_per_interval"]
        self.assertGreater(fl[0], fl[-1])                             # decreasing

    def test_arrival_rate_equals_stream_total_flat(self):
        a = S(mode="saturation-stream", arrival_rate=100, dwell_intervals=4, stream_rings="20:20:0")
        b = S(mode="saturation-stream", stream_total=400, dwell_intervals=4, stream_rings="20:20:0",
              profile="flat")
        self.assertAlmostEqual(a["cumulative_leak"], b["cumulative_leak"])
        self.assertEqual(a["profile"], "flat")                        # forced flat + echoed (A6/R1-9)

    def test_duration_advantage_positive(self):
        r = S(mode="saturation-stream", stream_total=400, dwell_intervals=4, stream_rings="20:20:0")
        self.assertGreater(r["duration_advantage"], 0.0)              # §4.4 sign pin

    def test_target_staying(self):
        r = S(mode="saturation-stream", stream_total=400, dwell_intervals=4, stream_rings="20:20:0",
              target_staying=2.0)
        self.assertAlmostEqual(r["delta_target"], 160.0)             # 320 leakers / 2

    def test_validation(self):
        for kw in (
            dict(arrival_rate=100, stream_total=400, dwell_intervals=4, stream_rings="20:20:0"),  # both forms
            dict(stream_total=400, stream_rings="20:20:0"),                                       # no dwell
            dict(stream_total=400, dwell_intervals=3.5, stream_rings="20:20:0"),                  # non-int dwell
            dict(stream_total=400, dwell_intervals=0, stream_rings="20:20:0"),                    # dwell < 1
            dict(stream_total=400, dwell_intervals=4, stream_rings="junk"),                       # malformed
            dict(stream_total=400, dwell_intervals=4, stream_rings="-5:0:0"),                     # neg cap
            dict(stream_total=400, dwell_intervals=4, stream_rings="20:-1:0"),                    # neg regen
            dict(stream_total=400, dwell_intervals=4, stream_rings="20:20:2"),                    # leak > 1
            dict(stream_total=400, dwell_intervals=4, stream_rings="20:20:0", target_staying=0),  # staying ≤ 0
            dict(dwell_intervals=4, stream_rings="20:20:0"),                                      # neither form
            dict(arrival_rate=100, dwell_intervals=4, stream_rings="20:20:0", profile="ramp"),    # rate + shaped
            dict(stream_total=400, dwell_intervals=4, stream_rings="20:20:0", scouting=0.5),      # σ-free (CP1 #2)
        ):
            self.assertIn("error", S(mode="saturation-stream", **kw))


class LightLagTest(unittest.TestCase):
    """CR-B (Packet 38.2): opt-in σ/δ light-lag degradation. Degenerate reproduction, τ=R/c band,
    monotonicity, first-mover advantage, and the per-mode threading (σ pre-multiply / δ per-ring)."""

    FORCE = dict(a_force=10, b_force=10, alpha=3, beta=3, a1_staying=2, b1_staying=2,
                 a3_defense=2, b3_defense=2)

    # ── degenerate: light-lag reproduces the constant-σ/δ result ──
    def test_degenerate_scale_inf_force(self):
        base = S(**self.FORCE)
        ll = S(**self.FORCE, light_lag=True, range_m=1e6, decay_scale=1e30)
        self.assertAlmostEqual(ll["delta_a"], base["delta_a"])
        self.assertAlmostEqual(ll["delta_b"], base["delta_b"])

    def test_degenerate_floors_one_force(self):
        base = S(**self.FORCE)
        ll = S(**self.FORCE, light_lag=True, range_m=1e6, sigma_floor=1.0, delta_floor=1.0)
        self.assertAlmostEqual(ll["delta_a"], base["delta_a"])   # σ₀=δ₀=1, floor=1 → constant
        self.assertAlmostEqual(ll["delta_b"], base["delta_b"])

    def test_degenerate_layered(self):
        base = S(mode="layered-defense", inbound_salvo=100, rings="1:30:0.1, 1:30:0.1, 1:30:0.1")
        ll = S(mode="layered-defense", inbound_salvo=100, rings="1:30:0.1, 1:30:0.1, 1:30:0.1",
               light_lag=True, range_m=1e6, ring_ranges="1e6, 1e6, 1e6", decay_scale=1e30)
        self.assertAlmostEqual(ll["survivors_to_target"], base["survivors_to_target"])

    # ── τ = R/c band (with tolerance — exact c ⇒ 1e9 m → 3.3356 s, 3e8 m → 1.0007 s) ──
    def test_tau_band(self):
        r = S(**self.FORCE, light_lag=True, range_m=1e9)
        self.assertAlmostEqual(r["tau_s"]["a"], 1e9 / 299792458.0, places=9)
        self.assertTrue(3.0 < r["tau_s"]["a"] < 3.5)
        self.assertAlmostEqual(r["light_travel_time_s"], 1e9 / 299792458.0, places=9)
        r2 = S(**self.FORCE, light_lag=True, range_m=3e8)
        self.assertAlmostEqual(r2["tau_s"]["a"], 1.0, places=2)          # 1.0007, tolerance (R2-3)

    # ── monotonicity: outer (longer-range) ring gets lower δ_eff and higher τ ──
    def test_monotonicity_layered(self):
        r = S(mode="layered-defense", inbound_salvo=100, rings="0.9:30:0.1, 0.9:30:0.1, 0.9:30:0.1",
              light_lag=True, range_m=1e8, ring_ranges="1e9, 5e8, 1e8")
        de, ts = r["delta_effective"], r["tau_s"]
        self.assertLessEqual(de[0], de[1])
        self.assertLessEqual(de[1], de[2])                              # outer ≤ inner δ_eff
        self.assertGreater(ts[0], ts[2])                               # outer τ > inner τ

    # ── first-mover advantage ──
    def test_first_mover_grows_with_tau(self):
        cfg = dict(a_force=1000, b_force=1000, alpha=1, beta=1, a1_staying=1, b1_staying=1,
                   a3_defense=1, b3_defense=1)
        small = S(**cfg, light_lag=True, range_a_m=1e6, range_b_m=2e8)
        large = S(**cfg, light_lag=True, range_a_m=1e6, range_b_m=2e9)
        self.assertGreater(small["first_mover_advantage"], 0.0)        # B (longer τ) is second, loses more
        self.assertGreater(large["first_mover_advantage"], small["first_mover_advantage"])

    def test_first_mover_null_symmetric_simultaneous(self):
        r = S(**self.FORCE, light_lag=True, range_m=1e8)               # shared τ ⇒ symmetric
        self.assertIsNone(r["first_mover_advantage"])

    def test_first_mover_null_symmetric_first_strike(self):
        # Strike ORDER alone must NOT populate it — only τ asymmetry does (R1-1).
        r = S(mode="first-strike", first="a", **self.FORCE, light_lag=True, range_m=1e8)
        self.assertIsNone(r["first_mover_advantage"])

    def test_first_mover_null_layered_and_saturation(self):
        lay = S(mode="layered-defense", inbound_salvo=100, rings="0.9:30:0.1",
                light_lag=True, range_m=1e8, ring_ranges="1e8")
        strm = S(mode="saturation-stream", stream_total=400, dwell_intervals=4, stream_rings="20:20:0",
                 light_lag=True, range_m=1e8)
        self.assertIsNone(lay["first_mover_advantage"])
        self.assertIsNone(strm["first_mover_advantage"])

    # ── per-side ranges, agility coupling, power exponent ──
    def test_per_side_ranges(self):
        r = S(**self.FORCE, light_lag=True, range_a_m=1e6, range_b_m=1e9)
        self.assertNotAlmostEqual(r["tau_s"]["a"], r["tau_s"]["b"])
        self.assertLess(r["sigma_effective"]["b"], r["sigma_effective"]["a"])   # B longer τ → more decay

    def test_agility_coupling(self):
        default = S(**self.FORCE, light_lag=True, range_m=1e9)                  # target-agility defaults to ref
        explicit = S(**self.FORCE, light_lag=True, range_m=1e9, target_agility=49.0, agility_ref=49.0)
        self.assertAlmostEqual(default["sigma_effective"]["a"], explicit["sigma_effective"]["a"])
        high = S(**self.FORCE, light_lag=True, range_m=1e9, target_agility=98.0, agility_ref=49.0)
        self.assertLess(high["sigma_effective"]["a"], default["sigma_effective"]["a"])   # 2× agility → more decay

    def test_power_exponent(self):
        p2 = S(**self.FORCE, light_lag=True, range_m=1e9, sigma_decay="power", decay_exponent=2)
        p4 = S(**self.FORCE, light_lag=True, range_m=1e9, sigma_decay="power", decay_exponent=4)
        self.assertLess(p4["sigma_effective"]["a"], p2["sigma_effective"]["a"])

    # ── saturation-stream = σ pre-multiply only (no δ) ──
    def test_saturation_sigma_only(self):
        base = S(mode="saturation-stream", stream_total=400, dwell_intervals=4, stream_rings="20:20:0")
        ll = S(mode="saturation-stream", stream_total=400, dwell_intervals=4, stream_rings="20:20:0",
               light_lag=True, range_m=1e9)
        self.assertLess(ll["sigma_effective"], 1.0)
        self.assertIsNone(ll["delta_effective"])
        self.assertLess(ll["cumulative_leak"], base["cumulative_leak"])   # σ<1 scales arrivals down
        ll2 = S(mode="saturation-stream", stream_total=400, dwell_intervals=4, stream_rings="20:20:0",
                light_lag=True, range_m=1e9, ring_ranges="1e9")
        self.assertEqual(len(ll2["tau_s"]), 1)                            # per-ring τ echo

    def test_light_travel_time_per_side(self):
        # Only per-side ranges (no shared --range-m) → scalar = max per-side τ, never null (CP3 #1).
        r = S(**self.FORCE, light_lag=True, range_a_m=1e6, range_b_m=2e9)
        self.assertIsNotNone(r["light_travel_time_s"])
        self.assertAlmostEqual(r["light_travel_time_s"], max(r["tau_s"]["a"], r["tau_s"]["b"]))

    def test_decay_exponent_only_validated_for_power(self):
        # exp/linear ignore the exponent, so exponent=0 must NOT error there; power still rejects it (CP3 #6).
        self.assertNotIn("error", S(**self.FORCE, light_lag=True, range_m=1e8, sigma_decay="exp",
                                    decay_exponent=0))
        self.assertIn("error", S(**self.FORCE, light_lag=True, range_m=1e8, sigma_decay="power",
                                 decay_exponent=0))

    def test_lightlag_args_without_on_error(self):
        # A light-lag input passed while --light-lag off is a typo, not a silent no-op (CP3 #2).
        for kw in (dict(range_m=1e8), dict(range_a_m=1e8), dict(ring_ranges="1e8"),
                   dict(target_agility=10.0)):
            self.assertIn("error", S(**self.FORCE, **kw))

    def test_layered_scouting_decayed(self):
        # σ₀ = the provided --scouting (0.8), then decayed (R2-4), not reset to 1.0.
        r = S(mode="layered-defense", inbound_salvo=100, rings="0.9:30:0.1", scouting=0.8,
              light_lag=True, range_m=1e6, ring_ranges="1e6")
        self.assertLess(r["sigma_effective"], 0.8)
        self.assertGreater(r["sigma_effective"], 0.79)

    # ── backward-compat + determinism ──
    def test_backward_compat_off_is_clean(self):
        r = S(**self.FORCE)
        for k in ("sigma_effective", "delta_effective", "tau_s", "light_travel_time_s",
                  "first_mover_advantage"):
            self.assertNotIn(k, r)
        for k in ("light_lag", "range_m", "sigma_decay"):
            self.assertNotIn(k, r["resolved_inputs"])

    def test_determinism(self):
        kw = dict(mode="saturation-stream", stream_total=400, dwell_intervals=4, stream_rings="20:20:0",
                  light_lag=True, range_m=1e9, ring_ranges="1e9")
        self.assertEqual(S(**kw), S(**kw))
        kw2 = dict(light_lag=True, range_a_m=1e6, range_b_m=1e9, **self.FORCE)
        self.assertEqual(S(**kw2), S(**kw2))

    # ── validation ──
    def test_validation(self):
        F = self.FORCE
        cases = [
            dict(mode="break-even", a_force=1, b_force=1, alpha=2, beta=1, a1_staying=2, b1_staying=1,
                 a3_defense=2, b3_defense=1, light_lag=True, range_m=1e8),                 # rejected mode
            dict(mode="distribute", a_force=7, b_force=25, alpha=4, a1_staying=1, b1_staying=1,
                 fire_fraction=0.5, light_lag=True, range_m=1e8),                          # rejected mode
            dict(mode="solve-force", a_force=7, a1_staying=1, b1_staying=1, beta=4, solve_for="b",
                 target_delta=7, light_lag=True, range_m=1e8),                             # rejected mode
            dict(light_lag=True, **F),                                                     # no engagement range
            dict(mode="layered-defense", inbound_salvo=100, rings="1:30:0.1", light_lag=True),        # no range
            dict(mode="layered-defense", inbound_salvo=100, rings="1:30:0.1", light_lag=True,
                 range_m=1e8),                                                             # no ring-ranges
            dict(mode="layered-defense", inbound_salvo=100, rings="1:30:0.1, 1:30:0.1", light_lag=True,
                 range_m=1e8, ring_ranges="1e8"),                                          # ring-range count
            dict(light_lag=True, range_m=1e8, sigma_decay="bad", **F),                     # bad law
            dict(light_lag=True, range_m=1e8, decay_scale=0, **F),                         # scale ≤ 0
            dict(light_lag=True, range_m=1e8, sigma_decay="power", decay_exponent=0, **F),  # exponent ≤ 0 (power)
            dict(light_lag=True, range_m=1e8, sigma_floor=1.5, **F),                       # floor ∉ [0,1]
            dict(light_lag=True, range_m=1e8, agility_ref=0, **F),                         # agility-ref ≤ 0
            dict(light_lag=True, range_m=1e8, target_agility=-1, **F),                     # agility < 0
            dict(sigma_a=0.3, sigma_floor=0.5, light_lag=True, range_m=1e8, **F),          # floor > base σ (R2-1)
            dict(delta_a=0.3, delta_floor=0.5, light_lag=True, range_m=1e8, **F),          # floor > base δ (R2-1)
        ]
        for kw in cases:
            self.assertIn("error", S(**kw))


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

    def test_layered_scouting_none(self):
        # A defaulted optional forwarded as None → curated {"error"}, not a raw
        # TypeError (mirrors the beam-weapon-engagement None-guard fix).
        self._err(mode="layered-defense", inbound_salvo=100, rings="1:30:0.1",
                  scouting=None)

    def test_first_strike_needs_first(self):
        self._err(mode="first-strike", a_force=10, b_force=10, alpha=3, beta=3,
                  a1_staying=2, b1_staying=2)

    def test_determinism(self):
        kw = dict(a_force=10, b_force=13, alpha=3.1, beta=2.7, a1_staying=2, b1_staying=1.5,
                  a3_defense=2, b3_defense=1.8, sigma_a=0.8, leak_b=0.2)
        self.assertEqual(S(**kw), S(**kw))


if __name__ == "__main__":
    unittest.main()
