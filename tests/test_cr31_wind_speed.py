# tests/test_cr31_wind_speed.py — CR-31: an explicit --wind-speed over a Wood-convention class / preset rate
# (legacy_row / object_preset) is ignored — v_wind 400 forced, astrosphere_wood_forced, CR-26's ignored-input note
# naming the path (CR-31.1); the `supplied` tier stays honoured, with a rescale note when a row-defaulted Wood
# source meets another speed (CR-31.2); every call WITHOUT --wind-speed is byte-identical (a pre-change snapshot).
# Offline: no path here resolves a star.

import json
import os
import unittest

from core import exclusion_boundary as eb
from core import exclusion_system as es
from core import exclusion_wall as ew
from tests._cr24strip import strip
from tests._queryharness import run_query_inproc

_FIX = os.path.join(os.path.dirname(__file__), "fixtures", "cr31_no_wind_speed_baseline.json")


def _eb(*args):
    code, p, err = run_query_inproc("exclusion-boundary", "--alpha", "0.4", *args)
    assert code == 0 and p is not None, err
    return p


def _es_comp(*args):
    code, p, err = run_query_inproc("exclusion-system", "--alpha", "0.4", *args)
    assert code == 0 and p is not None, err
    return p["zones"][0]["components"][0]


def _forced_note(v, kind, tier):
    return ew.NOTE_CR31_FORCED.format(v=v, kind=kind, tier=tier)


class Cr311ForcedTest(unittest.TestCase):
    """CR-31 acc 1 (+ the Q8 spellings): the relaxation cases return the Wood wall (not 4.243 / 9.487)."""

    def test_legacy_row_and_object_preset_boundary(self):
        for args, wall, kind, tier in (
                (("--mass-msun", "1.0", "--wind-state", "solar"), 6.0, "class", "legacy_row"),
                (("--mass-msun", "0.3", "--wind-state", "active"), 13.416, "class", "legacy_row"),
                (("--object", "m-dwarf"), 13.416, "preset", "object_preset"),
                (("--object", "sun"), 6.0, "preset", "object_preset")):
            with self.subTest(args=args):
                p = _eb(*args, "--wind-speed", "800")
                self.assertAlmostEqual(p["wall_au"], wall, places=3)
                self.assertEqual(p["wind_speed_kms"], 400.0)
                self.assertEqual(p["wind_speed_provenance"], "astrosphere_wood_forced")
                self.assertEqual(p["mass_loss_tier"], tier)
                self.assertIn(_forced_note(800, kind, tier), p["wind_model"]["notes"])

    def test_wood_row_under_noncoronal_row_is_forced(self):
        """WB MSG 332: the force keys on the rate (a Wood class row's own), whatever the tier label."""
        p = _eb("--spectral-type", "A1V", "--wind-state", "solar", "--wind-speed", "800")
        self.assertEqual(p["mass_loss_tier"], "noncoronal_row")
        self.assertAlmostEqual(p["wall_au"], 6.0, places=6)
        self.assertEqual(p["wind_speed_provenance"], "astrosphere_wood_forced")
        self.assertIn(_forced_note(800, "class", "noncoronal_row"), p["wind_model"]["notes"])
        for spec in ("id=A,mass=1.0,class=A1V,wind_state=solar,wind_speed=800",
                     "id=G,mass=1.5,class=K0III,wind_class=solar,wind_speed=800"):
            with self.subTest(spec=spec):
                c = _es_comp("--component", spec)
                self.assertEqual(c["mass_loss_tier"], "noncoronal_row")
                self.assertIn(_forced_note(800, "class", "noncoronal_row"), c["wind_model"]["notes"])
        # a typeless --star (an identity, no sp_type): the same forcing through the core path
        r = eb.compute_two_layer_boundary(mass_msun=1.0, object_name="HD 12345", wind_state="solar",
                                          wind_speed=800.0, alpha=0.4)
        self.assertEqual((r["wind_speed_provenance"], r["wall_au"]), ("astrosphere_wood_forced", 6.0))

    def test_wind_speed_400_is_forced_too(self):
        p = _eb("--mass-msun", "1.0", "--wind-state", "solar", "--wind-speed", "400")
        self.assertEqual(p["wind_speed_provenance"], "astrosphere_wood_forced")
        self.assertIn(_forced_note(400, "class", "legacy_row"), p["wind_model"]["notes"])
        self.assertAlmostEqual(p["wall_au"], 6.0, places=6)

    def test_exclusion_system_spellings(self):
        for comps, extra, wall in (
                (("id=S,mass=1.0",), ("--wind-state", "solar", "--wind-speed", "800"), 6.0),
                (("id=S,mass=1.0,wind_state=solar",), ("--wind-speed", "800"), 6.0),
                (("id=S,mass=1.0,wind_state=solar,wind_speed=800",), (), 6.0),
                (("id=S,mass=0.3,wind_class=active,wind_speed=800",), (), 13.416)):
            with self.subTest(comps=comps, extra=extra):
                args = [a for c in comps for a in ("--component", c)] + list(extra)
                c = _es_comp(*args)
                self.assertAlmostEqual(c["wall_au"], wall, places=3)
                self.assertEqual(c["mass_loss_tier"], "legacy_row")
                self.assertIn(_forced_note(800, "class", "legacy_row"), c["wind_model"]["notes"])

    def test_exclusion_system_forced_inputs_reach_the_combined_zone(self):
        """No per-component speed echo exists yet (CR-24 D6 adds it): the forced inputs (not the stale ones) must
        reach c['wall_inputs'] → the combined-wind zone wall — the summed 2×2e-14 at 400 km/s is 6·√2 = 8.485."""
        pair = ["id=A,mass=1.0,wind_state=solar,wind_speed=800,pair=AB,sma=2,ecc=0",
                "id=B,mass=1.0,wind_state=solar,wind_speed=800,pair=AB,sma=2,ecc=0"]
        r = es.compute_exclusion_system(component_specs=pair, alpha=0.4)
        self.assertNotIn("error", r)
        wz = [z for z in r["wall_zones"] if z.get("combined_wind_wall_au") is not None]
        self.assertTrue(wz)
        self.assertAlmostEqual(wz[0]["combined_wind_wall_au"], 6.0 * 2 ** 0.5, places=6)


class Cr312UnchangedTest(unittest.TestCase):
    """CR-31 acc 2 / 3: the supplied tier honoured (+ the rescale note where a row-defaulted Wood source meets
    another speed); an explicit source; the non-Wood rows; the CR-26 tiers."""

    def test_supplied_tier(self):
        p = _eb("--mass-msun", "1.0", "--mass-loss-msun-yr", "2e-14", "--wind-speed", "800")
        self.assertAlmostEqual(p["wall_au"], 4.243, places=3)
        self.assertEqual((p["wind_speed_kms"], p["wind_speed_provenance"]), (800.0, "supplied"))
        self.assertEqual((p["mass_loss_source"], p["mass_loss_source_provenance"]), ("recipe", "assumed"))
        self.assertFalse([n for n in p["wind_model"]["notes"] if "unrescaled" in n])

    def test_rescale_note_on_every_producing_path(self):
        note = ew.NOTE_CR31_RESCALE.format(v=800)
        for args in (("--mass-msun", "1.0", "--wind-state", "solar"), ("--spectral-type", "K2V"),
                     ("--object", "m-dwarf")):
            with self.subTest(args=args):
                p = _eb(*args, "--mass-loss-msun-yr", "4e-14", "--wind-speed", "800")
                self.assertEqual(p["mass_loss_tier"], "supplied")
                self.assertEqual((p["wind_speed_kms"], p["wind_speed_provenance"]), (800.0, "supplied"))
                self.assertEqual((p["mass_loss_source"], p["mass_loss_source_provenance"]),
                                 ("astrosphere_wood", "class_default"))
                self.assertAlmostEqual(p["wall_au"], 6.0, places=6)
                self.assertIn(note, p["wind_model"]["notes"])
        c = _es_comp("--component", "id=S,mass=1.0,wind_state=solar,mass_loss_msun_yr=4e-14,wind_speed=800")
        self.assertEqual(c["mass_loss_tier"], "supplied")
        self.assertAlmostEqual(c["wall_au"], 6.0, places=6)
        self.assertIn(note, c["wind_model"]["notes"])

    def test_no_rescale_note_at_400(self):
        p = _eb("--mass-msun", "1.0", "--wind-state", "solar", "--mass-loss-msun-yr", "4e-14", "--wind-speed", "400")
        self.assertFalse([n for n in p["wind_model"]["notes"] if "unrescaled" in n])

    def test_explicit_wood_source_forced_without_a_cr31_note(self):
        for extra in ((), ("--wind-state", "solar")):
            with self.subTest(extra=extra):
                p = _eb("--mass-msun", "1.0", *extra, "--mass-loss-msun-yr", "2e-14", "--wind-speed", "800",
                        "--mass-loss-source", "astrosphere_wood")
                self.assertEqual((p["wind_speed_kms"], p["wind_speed_provenance"]),
                                 (400.0, "astrosphere_wood_forced"))
                self.assertAlmostEqual(p["wall_au"], 6.0, places=6)
                self.assertFalse([n for n in p["wind_model"]["notes"] if "Wood-convention" in n or "unrescaled" in n])

    def test_non_wood_rows_honoured(self):
        p = _eb("--object", "o-star", "--wind-speed", "800")
        self.assertEqual(p["wind_speed_provenance"], "supplied")
        p = _eb("--mass-msun", "1.0", "--wind-state", "hot", "--wind-speed", "800")
        self.assertEqual(p["wind_speed_provenance"], "supplied")
        c = _es_comp("--component", "id=S,mass=1.0", "--wind-state", "hot", "--wind-speed", "800")
        self.assertFalse([n for n in c["wind_model"]["notes"] if "Wood-convention" in n])
        p = _eb("--spectral-type", "A1V", "--wind-speed", "800")          # noncoronal_row: CR-22's rule
        self.assertEqual((p["mass_loss_tier"], p["wind_speed_provenance"]), ("noncoronal_row", "supplied"))
        self.assertAlmostEqual(p["wall_au"], 3.000, places=3)

    def test_cr26_tier_unchanged(self):
        from core import stellar_wind as sw
        p = _eb("--spectral-type", "K2V", "--wind-speed", "800")
        self.assertAlmostEqual(p["wall_au"], 6.399, places=3)
        self.assertIn(sw.NOTE_IGNORED_SPEED.format(v=800), p["wind_model"]["notes"])
        self.assertFalse([n for n in p["wind_model"]["notes"] if "Wood-convention class" in n])

    def test_direct_core_object_preset_guards(self):
        """CP2: an unknown / mis-cased preset with a user rate is the caller's rate (supplied, honoured); a caller
        passing mass_loss_tier='object_preset' with a user rate is not forced either."""
        r = eb.compute_two_layer_boundary(mass_msun=1.0, object_name="Sun", wind_class="solar",
                                          wind_class_provenance="object_preset", mass_loss_msun_yr=4e-14,
                                          wind_speed=800.0, alpha=0.4)
        self.assertEqual((r["mass_loss_tier"], r["wind_speed_provenance"]), ("supplied", "supplied"))
        r = eb.compute_two_layer_boundary(mass_msun=0.3, object_name="m-dwarf", wind_class="active",
                                          wind_class_provenance="object_preset", mass_loss_msun_yr=4e-14,
                                          mass_loss_tier="object_preset", wind_speed=800.0, alpha=0.4)
        self.assertEqual(r["wind_speed_provenance"], "supplied")

    def test_direct_core_object_preset_with_a_user_rate_is_supplied(self):
        """CP0 F-B8: derive_mass_loss_tier no longer calls a user rate on an object_preset bin the preset's."""
        self.assertEqual(eb.derive_mass_loss_tier("main_sequence", "object_preset", 4e-14, None, 4e-14,
                                                  object_name="m-dwarf"), "supplied")
        self.assertEqual(eb.derive_mass_loss_tier("main_sequence", "object_preset", 1e-13, None, 1e-13,
                                                  object_name="m-dwarf"), "object_preset")
        self.assertEqual(eb.derive_mass_loss_tier("main_sequence", "object_preset", None, None, None,
                                                  object_name="m-dwarf"), "object_preset")


class Cr31ByteIdentityTest(unittest.TestCase):
    """Every call without --wind-speed on the CR-31 paths is byte-identical to the pre-CR-31 snapshot."""

    def test_no_wind_speed_byte_identical(self):
        with open(_FIX, encoding="utf-8") as fh:
            cases = json.load(fh)
        for case in cases:
            with self.subTest(args=case["args"]):
                code, payload, err = run_query_inproc(*case["args"])
                self.assertEqual(code, case["exit"])
                # from CR-24 (stage 3) on: CR-24's additive keys are stripped by name (the shared A0 helper)
                self.assertEqual(strip(json.loads(json.dumps(payload, default=str))), case["payload"])


if __name__ == "__main__":
    unittest.main()
