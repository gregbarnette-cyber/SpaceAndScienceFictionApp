# tests/test_multiplicity.py — CR-2 multiplicity / SB flag (core, offline).
#
# Layer A: the SIMBAD otype → multiplicity-hint block. Layer B: multiplicity_summary composing
# otype + binary-orbit + GCNS (monkeypatched). Live-gated anchors exercise real stars.

import unittest
from unittest.mock import patch

import core.binary as binary
import core.databases as databases
from tests._netcheck import live_enabled, reachable

_ONLINE = live_enabled() and reachable("simbad.u-strasbg.fr", 443)


class OtypeBlockTest(unittest.TestCase):
    def test_spectroscopic(self):
        b = databases._simbad_multiplicity_block("SB*")
        self.assertTrue(b["is_multiple"] and b["sb_flag"])
        self.assertEqual(b["basis"], "spectroscopic")

    def test_eclipsing(self):
        b = databases._simbad_multiplicity_block("EB*")
        self.assertTrue(b["is_multiple"])
        self.assertFalse(b["sb_flag"])
        self.assertEqual(b["basis"], "eclipsing")

    def test_visual_multiple(self):
        self.assertEqual(databases._simbad_multiplicity_block("**")["basis"], "visual/multiple")

    def test_single_type(self):
        b = databases._simbad_multiplicity_block("PM*")
        self.assertFalse(b["is_multiple"])
        self.assertFalse(b["sb_flag"])

    def test_none_otype(self):
        self.assertIsNone(databases._simbad_multiplicity_block(None))


def _summary(otype, solutions, gcns=None, designations=None):
    sl = {"main_id": "Test", "designations": designations or {},
          "multiplicity": databases._simbad_multiplicity_block(otype)}
    bo = {"solutions": solutions, "route_tried": ["gaia-nss:two_body_orbit", "sb9", "wds", "orb6"]}
    with patch("core.databases.compute_simbad_lookup", return_value=sl), \
         patch("core.binary.binary_orbit", return_value=bo), \
         patch("core.databases.compute_gcns_system", return_value=(gcns or {"error": "none"})):
        return binary.multiplicity_summary(star="Test")


class MultiplicitySummaryTest(unittest.TestCase):
    def test_known_sb1_sb_flag_and_lower_bound(self):
        sols = [{"source": "sb9", "separation_au": None,
                 "companion": {"method": "spec-min", "m2_solar": 0.3}}]
        d = _summary("SB*", sols)
        self.assertTrue(d["is_multiple"])
        self.assertTrue(d["sb_flag"])
        sb1 = [c for c in d["components"] if c["basis"] == "SB1"][0]
        self.assertTrue(sb1["sb_flag"])
        self.assertEqual(sb1["m2_solar_lower"], 0.3)          # sin i=1 lower bound, labelled

    def test_known_single(self):
        d = _summary("PM*", [])
        self.assertFalse(d["is_multiple"])
        self.assertEqual(d["components"], [])
        self.assertEqual(d["n_components"], 1)
        self.assertFalse(d["sb_flag"])

    def test_wide_visual_binary(self):
        sols = [{"source": "wds", "separation_au": 150.0, "companion": None}]
        d = _summary("**", sols)
        self.assertTrue(d["is_multiple"])
        vis = [c for c in d["components"] if c["basis"] == "visual"][0]
        self.assertEqual(vis["sep_au"], 150.0)
        self.assertFalse(vis["sb_flag"])

    def test_sb_from_otype_when_orbit_split_empty(self):
        # binary-orbit found nothing, but SIMBAD otype says SB* → still sb_flag True.
        d = _summary("SB*", [])
        self.assertTrue(d["is_multiple"])
        self.assertTrue(d["sb_flag"])
        self.assertTrue(any(c["basis"] == "spectroscopic" for c in d["components"]))

    def test_sb2_basis(self):
        sols = [{"source": "sb9", "companion": {"method": "SB2", "mass_ratio_q": 0.9}}]
        d = _summary("SB*", sols)
        self.assertTrue(any(c["basis"] == "SB2" and c["sb_flag"] for c in d["components"]))

    def test_gcns_sets_n_components(self):
        gcns = {"system": {"n_components": 3, "pairs": [{"proj_sep_au": 40.0}]}}
        d = _summary("PM*", [], gcns=gcns, designations={"Gaia EDR3": "Gaia DR3 12345"})
        self.assertTrue(d["is_multiple"])
        self.assertEqual(d["n_components"], 3)

    def test_error_passthrough(self):
        with patch("core.databases.compute_simbad_lookup", return_value={"error": "no such star"}):
            self.assertIn("error", binary.multiplicity_summary(star="Nope"))

    def test_requires_an_identifier(self):
        self.assertIn("error", binary.multiplicity_summary())


@unittest.skipUnless(_ONLINE, "SIMBAD not reachable / SPACE_APP_RUN_LIVE unset")
class MultiplicityLiveTest(unittest.TestCase):
    def test_alpha_cen_is_multiple(self):
        d = binary.multiplicity_summary(star="alpha Centauri")
        self.assertNotIn("error", d)
        self.assertTrue(d["is_multiple"])


if __name__ == "__main__":
    unittest.main()
