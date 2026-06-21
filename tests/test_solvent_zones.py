# tests/test_solvent_zones.py — Phase P solvent-zone (P4) core + query.py contracts.
#
# Offline. Covers compute_solvent_zone (M1 surface model): the legacy alt-HZ
# divisor anchors at A=0.3, the corrected (1−A)^0.25 albedo exponent, custom
# ranges, the CO2 pressure-conditional flag, the corrected hydrogen band, the
# validation matrix, and the `solvent-zone` query.py subcommand (subprocess
# happy-path/parity + the exit-code matrix). compute_ice_lines (P5) and its
# `ice-lines` subcommand get added here when P5 lands.

import json
import math
import os
import subprocess
import sys
import unittest
from pathlib import Path

from core.equations import compute_solvent_zone, compute_ice_lines, get_solvents

_REPO = Path(__file__).resolve().parent.parent
_ENV = {"SPACE_APP_DB": "/tmp/phase_p_throwaway.db", "PATH": os.environ.get("PATH", "")}


def _run(*cmd_args):
    """Run query.py with args; return (returncode, parsed_stdout_or_None, stderr)."""
    proc = subprocess.run(
        [sys.executable, str(_REPO / "query.py"), *cmd_args],
        capture_output=True, text=True, cwd=str(_REPO), env=_ENV,
    )
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        payload = None
    return proc.returncode, payload, proc.stderr


# ── M1 anchors: reproduce the legacy alternate-HZ divisors at A=0.3 ───────────

class SolventZoneM1AnchorTest(unittest.TestCase):
    # Legacy alt-HZ divisors (core/regions.py) the M1 model must reproduce.
    # (key: (inner divisor = boil S_eff, outer divisor = freeze S_eff))
    _LEGACY = {
        "water":   (2.8,   0.8),
        "ammonia": (0.48,  0.21),
        "methane": (0.023, 0.0094),
    }

    def test_reproduces_legacy_divisors_within_tolerance(self):
        # Precise CRC temps vs the rounded legacy divisors → within ~5%.
        for key, (din, dout) in self._LEGACY.items():
            r = compute_solvent_zone(1.0, key)
            self.assertNotIn("error", r)
            self.assertAlmostEqual(r["s_eff_inner"], din, delta=din * 0.05)
            self.assertAlmostEqual(r["s_eff_outer"], dout, delta=dout * 0.05)
            self.assertAlmostEqual(r["inner_au"], math.sqrt(1.0 / din), delta=math.sqrt(1.0 / din) * 0.05)
            self.assertAlmostEqual(r["outer_au"], math.sqrt(1.0 / dout), delta=math.sqrt(1.0 / dout) * 0.05)

    def test_tref_is_288_and_round_trips_edge_temps(self):
        for key in self._LEGACY:
            r = compute_solvent_zone(1.0, key, albedo=0.3)
            self.assertAlmostEqual(r["t_ref_k"], 288.0, delta=0.1)
            # t_eq_* reconstruct the input edge temps (round-trip).
            self.assertAlmostEqual(r["t_eq_inner"], r["t_high_k"], places=6)
            self.assertAlmostEqual(r["t_eq_outer"], r["t_low_k"], places=6)

    def test_inner_is_boil_outer_is_freeze(self):
        r = compute_solvent_zone(1.0, "water")
        self.assertLess(r["inner_au"], r["outer_au"])      # boiling edge is closer in
        self.assertAlmostEqual(r["t_eq_inner"], 373.15, places=4)
        self.assertAlmostEqual(r["t_eq_outer"], 273.15, places=4)


# ── M1 albedo exponent: (1−A)^0.25 (NOT the legacy (1−A)²) ────────────────────

class SolventZoneAlbedoTest(unittest.TestCase):
    def test_tref_at_zero_albedo_is_3149(self):
        r = compute_solvent_zone(1.0, "water", albedo=0.0)
        self.assertAlmostEqual(r["t_ref_k"], 314.9, delta=0.1)

    def test_band_shifts_by_fourth_root_law(self):
        # inner_au ∝ T_ref² ∝ (1−A)^0.5, so A=0 vs A=0.3 → ratio sqrt(1/0.7).
        a0 = compute_solvent_zone(1.0, "water", albedo=0.0)
        a3 = compute_solvent_zone(1.0, "water", albedo=0.3)
        ratio = a0["inner_au"] / a3["inner_au"]
        self.assertAlmostEqual(ratio, math.sqrt(1.0 / 0.7), places=4)
        # ... and decisively NOT the legacy (1−A)² law (that would be 0.49).
        self.assertNotAlmostEqual(ratio, 0.49, places=2)


# ── Custom range, CO2, hydrogen ──────────────────────────────────────────────

class SolventZoneVariantsTest(unittest.TestCase):
    def test_custom_range_matches_named_solvent(self):
        named = compute_solvent_zone(1.0, "water")
        custom = compute_solvent_zone(1.0, t_low_k=273.15, t_high_k=373.15)
        self.assertAlmostEqual(custom["inner_au"], named["inner_au"], places=9)
        self.assertAlmostEqual(custom["outer_au"], named["outer_au"], places=9)

    def test_co2_pressure_conditional(self):
        r = compute_solvent_zone(1.0, "co2")
        self.assertTrue(r["pressure_conditional"])
        self.assertEqual(r["assumed_pressure_atm"], 5.2)
        self.assertAlmostEqual(r["t_high_k"], 304.1, places=4)   # critical
        self.assertAlmostEqual(r["t_low_k"], 216.6, places=4)    # triple

    def test_hydrogen_uses_cryogenic_band_not_legacy_64k(self):
        r = compute_solvent_zone(1.0, "hydrogen", albedo=0.3)
        # ~200–440 AU at L=1, A=0.3 — the corrected P1a band.
        self.assertAlmostEqual(r["inner_au"], 202.0, delta=3.0)
        self.assertAlmostEqual(r["outer_au"], 436.0, delta=4.0)
        # Edge temps are cryogenic (13.8 / 20.3 K), NOT the legacy ~64 K.
        self.assertLess(r["t_eq_inner"], 21.0)
        self.assertLess(r["t_eq_outer"], 14.5)


# ── Validation matrix ────────────────────────────────────────────────────────

class SolventZoneValidationTest(unittest.TestCase):
    def test_errors(self):
        cases = [
            dict(luminosity_solar=0.0, solvent="water"),
            dict(luminosity_solar=-1.0, solvent="water"),
            dict(luminosity_solar=1.0, solvent="water", albedo=1.0),
            dict(luminosity_solar=1.0, solvent="water", albedo=-0.1),
            dict(luminosity_solar=1.0, t_low_k=400.0, t_high_k=300.0),  # low >= high
            dict(luminosity_solar=1.0, solvent="unobtanium"),
            dict(luminosity_solar=1.0),                                  # neither
            dict(luminosity_solar=1.0, t_low_k=100.0),                   # one of pair
        ]
        for kw in cases:
            self.assertIn("error", compute_solvent_zone(**kw), kw)

    def test_all_named_solvents_compute(self):
        for s in get_solvents():
            r = compute_solvent_zone(1.0, s["key"])
            self.assertNotIn("error", r, s["key"])
            self.assertGreater(r["inner_au"], 0)
            self.assertGreater(r["outer_au"], r["inner_au"])


# ── query.py solvent-zone subcommand contracts (subprocess) ──────────────────

class SolventZoneQueryTest(unittest.TestCase):
    def test_happy_path_and_parity(self):
        rc, payload, _ = _run("solvent-zone", "--luminosity", "1.0", "--solvent", "water")
        self.assertEqual(rc, 0)
        core = compute_solvent_zone(1.0, "water")
        self.assertAlmostEqual(payload["inner_au"], core["inner_au"], places=6)
        self.assertAlmostEqual(payload["outer_au"], core["outer_au"], places=6)
        self.assertEqual(payload["name"], "Water")

    def test_custom_range_happy_path(self):
        rc, payload, _ = _run("solvent-zone", "--luminosity", "1.0",
                              "--t-low", "273.15", "--t-high", "373.15")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(payload["inner_au"], math.sqrt(1.0 / 2.8), delta=0.01)

    def test_albedo_flag(self):
        rc, payload, _ = _run("solvent-zone", "--luminosity", "1.0",
                              "--solvent", "water", "--albedo", "0.0")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(payload["t_ref_k"], 314.9, delta=0.1)

    def test_out_of_range_is_exit_1(self):
        rc, payload, _ = _run("solvent-zone", "--luminosity", "0", "--solvent", "water")
        self.assertEqual(rc, 1)
        self.assertIn("error", payload)

    def test_unknown_solvent_is_exit_1(self):
        rc, payload, _ = _run("solvent-zone", "--luminosity", "1", "--solvent", "zzz")
        self.assertEqual(rc, 1)
        self.assertIn("error", payload)

    def test_both_mutex_is_exit_2(self):
        rc, _, _ = _run("solvent-zone", "--luminosity", "1", "--solvent", "water",
                        "--t-low", "100", "--t-high", "200")
        self.assertEqual(rc, 2)

    def test_neither_is_exit_2(self):
        rc, _, _ = _run("solvent-zone", "--luminosity", "1")
        self.assertEqual(rc, 2)

    def test_missing_luminosity_is_exit_2(self):
        rc, _, _ = _run("solvent-zone", "--solvent", "water")
        self.assertEqual(rc, 2)


# ── P5: compute_ice_lines (M2 equilibrium model) ─────────────────────────────

class IceLinesTest(unittest.TestCase):
    def test_tref_and_water_snow_line_anchor(self):
        r = compute_ice_lines(1.0)               # default albedo 0.0
        self.assertNotIn("error", r)
        self.assertAlmostEqual(r["t_ref_k"], 278.5, places=3)
        water = r["lines"][0]
        self.assertEqual(water["kind"], "snow_line")
        self.assertAlmostEqual(water["t_cond_k"], 170.0, places=3)
        self.assertAlmostEqual(water["au"], 2.68, delta=0.02)   # canonical snow line

    def test_front_anchors_and_disk_flags(self):
        by_t = {ln["t_cond_k"]: ln for ln in compute_ice_lines(1.0)["lines"]}
        self.assertAlmostEqual(by_t[70.0]["au"], 15.8, delta=0.1)   # CO2
        self.assertAlmostEqual(by_t[80.0]["au"], 12.1, delta=0.1)   # NH3
        # The deep-cold N2/CO fronts are disk-set; CO2/NH3/water are not.
        self.assertTrue(by_t[22.0]["disk_line"])   # N2
        self.assertTrue(by_t[20.0]["disk_line"])   # CO
        self.assertFalse(by_t[70.0]["disk_line"])  # CO2
        self.assertFalse(by_t[170.0]["disk_line"]) # water

    def test_single_canonical_water_line_no_dual(self):
        r = compute_ice_lines(1.0)
        snow = [ln for ln in r["lines"] if ln["kind"] == "snow_line"]
        self.assertEqual(len(snow), 1)             # no dual / formation line
        self.assertEqual(len(r["lines"]), 5)

    def test_lines_ordered_inner_to_outer(self):
        aus = [ln["au"] for ln in compute_ice_lines(1.0)["lines"]]
        self.assertEqual(aus, sorted(aus))

    def test_albedo_scales_tref(self):
        r = compute_ice_lines(1.0, albedo=0.3)
        self.assertAlmostEqual(r["t_ref_k"], 278.5 * (0.7 ** 0.25), places=3)

    def test_validation(self):
        self.assertIn("error", compute_ice_lines(0.0))
        self.assertIn("error", compute_ice_lines(-1.0))
        self.assertIn("error", compute_ice_lines(1.0, albedo=1.0))
        self.assertIn("error", compute_ice_lines(1.0, albedo=-0.1))


class IceLineDiagramPrepTest(unittest.TestCase):
    def test_shape_and_colors(self):
        import core.viz
        d = core.viz.prepare_ice_line_diagram(compute_ice_lines(1.0))
        self.assertEqual(len(d["lines"]), 5)
        water = next(l for l in d["lines"] if l["kind"] == "snow_line")
        self.assertEqual(water["color"], "#4499FF")
        self.assertTrue(all("color" in l and "disk_line" in l for l in d["lines"]))

    def test_error_passthrough(self):
        import core.viz
        self.assertIn("error", core.viz.prepare_ice_line_diagram({"error": "x"}))


# ── V6 / V7: orbital-overlay data (prepare_orbit_overlays) ────────────────────

class OrbitOverlayPrepTest(unittest.TestCase):
    def test_snow_au_and_solvent_options(self):
        import core.viz
        d = core.viz.prepare_orbit_overlays(1.0)
        self.assertAlmostEqual(d["snow_au"], 2.68, delta=0.02)   # M2 water snow line
        keys = [o["key"] for o in d["solvent_options"]]
        self.assertEqual(keys[:3], ["water", "ammonia", "methane"])
        # All solvent zones default OFF → the orbital diagram is byte-identical
        # until the user ticks one (opt-in overlay).
        on = [o["key"] for o in d["solvent_options"] if o["default"]]
        self.assertEqual(on, [])
        for o in d["solvent_options"]:
            self.assertGreater(o["outer_au"], o["inner_au"])
            self.assertTrue(o["color"].startswith("#"))

    def test_bad_luminosity_errors(self):
        import core.viz
        self.assertIn("error", core.viz.prepare_orbit_overlays(None))
        self.assertIn("error", core.viz.prepare_orbit_overlays(0))


class IceLinesQueryTest(unittest.TestCase):
    def test_happy_path_and_parity(self):
        rc, payload, _ = _run("ice-lines", "--luminosity", "1.0")
        self.assertEqual(rc, 0)
        core = compute_ice_lines(1.0)
        self.assertAlmostEqual(payload["t_ref_k"], core["t_ref_k"], places=6)
        self.assertEqual(len(payload["lines"]), 5)
        self.assertAlmostEqual(payload["lines"][0]["au"], core["lines"][0]["au"], places=6)

    def test_albedo_flag(self):
        rc, payload, _ = _run("ice-lines", "--luminosity", "1.0", "--albedo", "0.3")
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(payload["t_ref_k"], 278.5 * (0.7 ** 0.25), places=3)

    def test_out_of_range_is_exit_1(self):
        rc, payload, _ = _run("ice-lines", "--luminosity", "0")
        self.assertEqual(rc, 1)
        self.assertIn("error", payload)

    def test_missing_luminosity_is_exit_2(self):
        rc, _, _ = _run("ice-lines")
        self.assertEqual(rc, 2)


# ── P6 / V5: solvent reference data (prepare_solvent_ranges) ─────────────────

class SolventRangesPrepTest(unittest.TestCase):
    def test_shape_and_sort(self):
        import core.viz
        d = core.viz.prepare_solvent_ranges()
        n = len(get_solvents())
        for key in ("names", "lo", "hi", "colors", "plausibility",
                    "pressure_conditional", "assumed_pressure_atm", "citation"):
            self.assertEqual(len(d[key]), n, key)
        # Sorted by freezing point (lo) ascending — coldest first.
        self.assertEqual(d["lo"], sorted(d["lo"]))
        # Every bar spans freeze→boil (hi > lo).
        for l, h in zip(d["lo"], d["hi"]):
            self.assertLess(l, h)

    def test_plausibility_colors(self):
        import core.viz
        self.assertEqual(core.viz.solvent_plausibility_color("water"), "#2e8b57")
        self.assertEqual(core.viz.solvent_plausibility_color("sulfuric_acid"), "#2e8b57")
        self.assertEqual(core.viz.solvent_plausibility_color("ammonia"), "#b8860b")
        self.assertEqual(core.viz.solvent_plausibility_color("hydrogen"), "#8899aa")  # other


# ── P2 / P3: additive bands + ice fronts in core/regions.py ──────────────────

class RegionsP2P3Test(unittest.TestCase):
    def setUp(self):
        import core.regions
        self.d = core.regions.compute_sol_regions()

    def test_p2_solvent_band_keys_present(self):
        for k in ("co2Inner", "co2Outer", "sInner", "sOuter",
                  "waInner", "waOuter", "saInner", "saOuter"):
            self.assertIn(k, self.d)
            self.assertGreater(self.d[k], 0)
        # Inner edge (boil) is closer in than the outer edge (freeze).
        self.assertLess(self.d["co2Inner"], self.d["co2Outer"])
        self.assertLess(self.d["sInner"], self.d["sOuter"])

    def test_p2_bands_match_compute_solvent_zone(self):
        # The regions bands are derived from compute_solvent_zone at A=0.3.
        L = self.d["bcLuminosity"]
        for key, ik, ok in (("co2", "co2Inner", "co2Outer"),
                            ("sulfur", "sInner", "sOuter"),
                            ("water_ammonia", "waInner", "waOuter"),
                            ("sulfuric_acid", "saInner", "saOuter")):
            z = compute_solvent_zone(L, key)
            self.assertAlmostEqual(self.d[ik], z["inner_au"], places=9)
            self.assertAlmostEqual(self.d[ok], z["outer_au"], places=9)

    def test_p3_ice_front_keys_present(self):
        for k in ("iceLineNH3", "iceLineCO2", "iceLineN2", "iceLineCO"):
            self.assertIn(k, self.d)
            self.assertGreater(self.d[k], 0)
        # M2 fronts match compute_ice_lines at the star's luminosity.
        ice = {int(round(l["t_cond_k"])): l["au"]
               for l in compute_ice_lines(self.d["bcLuminosity"])["lines"]}
        self.assertAlmostEqual(self.d["iceLineCO2"], ice[70], places=9)
        self.assertAlmostEqual(self.d["iceLineN2"], ice[22], places=9)

    def test_sound_bands_untouched(self):
        # The sound Asimov bands keep their hardcoded divisors (regression guard).
        # Hydrogen (ph) and snowLine ARE changed by P1 — see test_worldbuilding.
        L = self.d["bcLuminosity"]
        self.assertAlmostEqual(self.d["prwInner"], math.sqrt(L / 2.8), places=9)
        self.assertAlmostEqual(self.d["prwOuter"], math.sqrt(L / 0.8), places=9)
        self.assertAlmostEqual(self.d["praInner"], math.sqrt(L / 0.48), places=9)
        self.assertAlmostEqual(self.d["pmOuter"], math.sqrt(L / 0.0094), places=9)
        self.assertAlmostEqual(self.d["ffInner"], math.sqrt(L / 52.0), places=9)
        self.assertAlmostEqual(self.d["fsOuter"], math.sqrt(L / 3.2), places=9)
        # lh2Line value unchanged (P1b is relabel-only).
        self.assertAlmostEqual(self.d["lh2Line"], math.sqrt(L / 0.0025), places=9)


# ── P1: value corrections (hydrogen / snow line / planetary temperature) ─────

class RegionsP1Test(unittest.TestCase):
    def setUp(self):
        import core.regions
        self.regions = core.regions
        self.d = core.regions.compute_sol_regions()

    def test_p1a_hydrogen_divisors_corrected(self):
        L = self.d["bcLuminosity"]
        # Corrected to the real H₂ 1-atm liquid range (~200–440 AU at solar L).
        self.assertAlmostEqual(self.d["phInner"], math.sqrt(L / 0.0000247), places=6)
        self.assertAlmostEqual(self.d["phOuter"], math.sqrt(L / 0.0000053), places=6)
        self.assertGreater(self.d["phInner"], 150)     # far out — NOT the legacy ~20 AU
        self.assertLess(self.d["phInner"], self.d["phOuter"])

    def test_p1c_snow_line_is_canonical(self):
        L = self.d["bcLuminosity"]
        # Corrected divisor 0.04 → 0.139 (170 K canonical water snow line).
        self.assertAlmostEqual(self.d["snowLine"], math.sqrt(L / 0.139), places=6)
        # The M2 implied temperature at the snow line is ~170 K (L-independent).
        from core.equations import implied_edge_temp
        self.assertAlmostEqual(
            implied_edge_temp(self.d["snowLine"], L, "equilibrium"), 170.0, delta=1.0)
        # It moved INWARD from the legacy 5-AU (0.04-divisor) placement.
        self.assertLess(self.d["snowLine"], math.sqrt(L / 0.04))
        # A bcLum≈1 star puts it at the canonical ~2.68 AU.
        one = self.regions.compute_star_system_regions(
            vmag=-0.15, boloLum=0.0, temp=5778, plx=1000.0)   # bcLum ≈ 1
        self.assertAlmostEqual(one["bcLuminosity"], 1.0, delta=0.02)
        self.assertAlmostEqual(one["snowLine"], 2.68, delta=0.03)

    def test_p1e_planetary_temperature_albedo_exponent(self):
        # At A=0.3, S=1 → unchanged 288 K (opt 8/13 default regression guard).
        a3 = self.regions.compute_star_system_regions(
            vmag=5.0, boloLum=-0.1, temp=5500, plx=100, bond_albedo=0.3)
        self.assertAlmostEqual(a3["planetaryTemperature"], 288.0, delta=0.1)
        # At A=0.7 → ~233 K (the (1−A)^0.25 law), NOT the legacy ~123 K.
        a7 = self.regions.compute_star_system_regions(
            vmag=5.0, boloLum=-0.1, temp=5500, plx=100, bond_albedo=0.7)
        self.assertAlmostEqual(a7["planetaryTemperature"], 233.0, delta=1.0)
        self.assertGreater(a7["planetaryTemperature"], 200)   # not the buggy collapse
        # Celsius / Fahrenheit derive from it.
        self.assertAlmostEqual(a7["planetaryTemperatureC"], 233.06 - 273.15, delta=1.0)


# ── V1 / V2: alt-HZ 10 bands + system-regions relabels ───────────────────────

class AltHzAndSystemDiagramTest(unittest.TestCase):
    def setUp(self):
        import core.regions, core.viz
        self.d = core.regions.compute_sol_regions()
        self.viz = core.viz

    def test_alt_hz_has_ten_bands(self):
        alt = self.viz.prepare_alt_hz_diagram(self.d)
        self.assertEqual(len(alt["zones"]), 10)
        labels = [z["label"] for z in alt["zones"]]
        for lbl in ("Carbon Dioxide (≥5.2 atm)", "Liquid Sulfur",
                    "Water-Ammonia Eutectic", "Sulfuric Acid"):
            self.assertIn(lbl, labels)

    def test_alt_hz_backcompat_six_when_no_p2_keys(self):
        # An older/partial dict (no co2Inner) still yields the original six.
        partial = {k: v for k, v in self.d.items() if not k.startswith(("co2", "s", "wa", "sa"))}
        # keep the six required inner/outer keys
        for k in ("ffInner", "ffOuter", "fsInner", "fsOuter", "prwInner", "prwOuter",
                  "praInner", "praOuter", "pmInner", "pmOuter", "phInner", "phOuter"):
            partial[k] = self.d[k]
        alt = self.viz.prepare_alt_hz_diagram(partial)
        self.assertEqual(len(alt["zones"]), 6)

    def test_system_regions_relabels(self):
        sr = self.viz.prepare_system_regions_diagram(self.d)
        labels = [r["label"] for r in sr["regions"]]
        self.assertIn("Water snow line", labels)
        self.assertIn("N₂/CO (1-atm)", labels)
        self.assertNotIn("Snow Line", labels)
        self.assertNotIn("LH₂ Line", labels)


if __name__ == "__main__":
    unittest.main()
