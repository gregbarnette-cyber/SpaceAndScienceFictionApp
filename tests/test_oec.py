# tests/test_oec.py — offline coverage for the Open Exoplanet Catalogue rebuild
# (core/databases.py: _norm_oec_name, _oec_node generic capture, compute_oec /
# compute_oec_planet, and the shared display formatters).
#
# Uses a hand-built fixture XML covering every real topology class (single star,
# S-type binary, P-type circumbinary, hierarchical depth-2, rogue, zero-planet)
# plus the hazards the mockup surfaced: multi-<list> on a binary planet, an
# arcsec+AU separation, a bound-only (upperlimit) value, mass type="msini", a
# satellite (moon), an unnamed binary, and alias resolution. No network, no Qt —
# _oec_get_root is monkeypatched to parse the fixture (the index is still built).

import unittest
import xml.etree.ElementTree as ET

import core.databases as databases

# One <system> per topology class.
_FIXTURE = """<systems>
  <system>
    <name>Single Star</name>
    <name>HD 1</name>
    <distance errorminus="0.1" errorplus="0.1">10.0</distance>
    <constellation>Testus</constellation>
    <star>
      <name>HD 1</name>
      <spectraltype>G2V</spectraltype>
      <mass errorminus="0.05" errorplus="0.05">1.0</mass>
      <radius>1.0</radius>
      <temperature>5800</temperature>
      <planet>
        <name>HD 1 b</name>
        <mass type="msini" errorminus="0.01" errorplus="0.01">0.5</mass>
        <period>100</period>
        <eccentricity upperlimit="0.2"/>
        <list>Confirmed planets</list>
      </planet>
    </star>
  </system>

  <system>
    <name>Binary S</name>
    <distance>5.0</distance>
    <binary>
      <name>Binary S</name>
      <separation unit="arcsec">80</separation>
      <separation unit="AU">400</separation>
      <star>
        <name>BS A</name>
        <spectraltype>K0V</spectraltype>
        <planet>
          <name>BS A b</name>
          <mass>1.2</mass>
          <list>Confirmed planets</list>
          <list>Planets in binary systems, S-type</list>
        </planet>
      </star>
      <star>
        <name>BS B</name>
        <spectraltype>DA2</spectraltype>
      </star>
    </binary>
  </system>

  <system>
    <name>Circumbinary</name>
    <binary>
      <name>CB AB</name>
      <semimajoraxis>0.2</semimajoraxis>
      <planet>
        <name>CB AB b</name>
        <mass>0.3</mass>
        <list>Planets in binary systems, P-type</list>
      </planet>
      <star><name>CB A</name></star>
      <star><name>CB B</name></star>
    </binary>
  </system>

  <system>
    <name>Hierarchy</name>
    <binary>
      <name>Outer</name>
      <separation unit="arcsec">40</separation>
      <separation unit="AU">800</separation>
      <binary>
        <name>Inner AC</name>
        <separation unit="AU">70</separation>
        <star><name>Inner A</name><spectraltype>G2V</spectraltype></star>
        <star><name>Inner C</name></star>
      </binary>
      <star>
        <name>Outer B</name>
        <planet>
          <name>Outer B b</name>
          <mass>1.7</mass>
          <radius>1.1</radius>
          <list>Confirmed planets</list>
          <satellite>
            <name>Outer B b I</name>
            <mass>0.01</mass>
            <radius>0.3</radius>
          </satellite>
        </planet>
      </star>
    </binary>
  </system>

  <system>
    <name>Rogue One</name>
    <distance>3.0</distance>
    <planet>
      <name>Rogue One</name>
      <mass errorminus="2" errorplus="2">6.0</mass>
      <list>Orphan planets</list>
    </planet>
  </system>

  <system>
    <name>Zero Planet</name>
    <binary>
      <eccentricity>0.4</eccentricity>
      <star><name>ZP A</name><spectraltype>K5V</spectraltype></star>
      <star><name>ZP B</name><spectraltype>K7V</spectraltype></star>
    </binary>
  </system>
</systems>"""


class OecTestBase(unittest.TestCase):
    def setUp(self):
        self._root = ET.fromstring(_FIXTURE)
        self._saved_get_root = databases._oec_get_root
        self._saved_data = databases._OEC_DATA
        databases._oec_get_root = lambda force_refresh=False: self._root
        databases._OEC_DATA = None            # force a rebuild off the fixture

    def tearDown(self):
        databases._oec_get_root = self._saved_get_root
        databases._OEC_DATA = self._saved_data

    def _system(self, name):
        r = databases.compute_oec(name, allow_simbad=False)
        self.assertNotIn("error", r, r.get("error"))
        return r["system"]

    @staticmethod
    def _find(node, tag, name_sub=None):
        out = []
        def walk(n):
            if n["tag"] == tag and (name_sub is None or
                                    any(name_sub in x for x in n.get("names", []))):
                out.append(n)
            for c in n.get("children", []):
                walk(c)
        walk(node)
        return out


class NormNameTests(unittest.TestCase):
    def test_norm_strips_and_lowercases(self):
        n = databases._norm_oec_name
        self.assertEqual(n("HD 209458"), n("HD209458"))
        self.assertEqual(n("K2 18"), n("K2-18"))
        self.assertEqual(n("* alf Cen"), n("alfCen"))
        self.assertEqual(n("NAME Proxima"), "proxima")
        self.assertEqual(n(""), "")

    def test_name_variants_strips_planet_letter(self):
        self.assertIn("HD 1", databases._oec_name_variants("HD 1 b"))


class ResolutionTests(OecTestBase):
    def test_resolves_by_primary_name(self):
        self.assertEqual(self._system("Single Star")["names"][0], "Single Star")

    def test_resolves_by_alias(self):
        self.assertEqual(self._system("HD 1")["names"][0], "Single Star")

    def test_planet_name_resolves_to_system(self):
        # 'HD 1 b' → letter-stripped 'HD 1' → the system
        self.assertEqual(self._system("HD 1 b")["names"][0], "Single Star")

    def test_not_found_message(self):
        r = databases.compute_oec("Nonexistent Star", allow_simbad=False)
        self.assertIn("error", r)
        self.assertIn("not in the Open Exoplanet Catalogue", r["error"])


class NodeModelTests(OecTestBase):
    def test_msini_type_preserved(self):
        planet = self._find(self._system("Single Star"), "planet")[0]
        self.assertEqual(planet["fields"]["mass"]["type"], "msini")

    def test_upperlimit_bound_only(self):
        planet = self._find(self._system("Single Star"), "planet")[0]
        ecc = planet["fields"]["eccentricity"]
        self.assertEqual(ecc.get("value"), "")
        self.assertEqual(ecc.get("upperlimit"), "0.2")

    def test_separation_multivalued(self):
        binary = self._find(self._system("Binary S"), "binary")[0]
        sep = binary["fields"]["separation"]
        self.assertIsInstance(sep, list)
        self.assertEqual({x["unit"] for x in sep}, {"arcsec", "AU"})

    def test_multi_list_status(self):
        planet = self._find(self._system("Binary S"), "planet")[0]
        self.assertIsInstance(planet["fields"]["list"], list)
        self.assertEqual(len(databases.oec_statuses(planet["fields"])), 2)

    def test_hierarchical_depth_two(self):
        sys = self._system("Hierarchy")
        outer = sys["children"][0]
        self.assertEqual(outer["tag"], "binary")
        self.assertTrue(any(c["tag"] == "binary" for c in outer["children"]))

    def test_satellite_captured_as_node(self):
        planet = self._find(self._system("Hierarchy"), "planet")[0]
        moons = [c for c in planet.get("children", []) if c["tag"] == "satellite"]
        self.assertEqual(len(moons), 1)
        self.assertEqual(moons[0]["names"][0], "Outer B b I")

    def test_zero_planet_system_returns_tree(self):
        sys = self._system("Zero Planet")            # not an error
        self.assertEqual(len(self._find(sys, "planet")), 0)
        self.assertEqual(len(self._find(sys, "star")), 2)


class PlanetChainTests(OecTestBase):
    def test_attached_to_star(self):
        r = databases.compute_oec_planet("HD 1 b")
        self.assertEqual(r["attached_to"], "star")
        self.assertEqual([c["tag"] for c in r["host_chain"]], ["system", "star"])

    def test_attached_to_binary_circumbinary(self):
        r = databases.compute_oec_planet("CB AB b")
        self.assertEqual(r["attached_to"], "binary")

    def test_attached_to_system_rogue(self):
        r = databases.compute_oec_planet("Rogue One")
        self.assertEqual(r["attached_to"], "system")
        self.assertEqual([c["tag"] for c in r["host_chain"]], ["system"])


class FormatterTests(unittest.TestCase):
    def test_bound_only_uses_attribute_value(self):
        self.assertEqual(databases.oec_format_field({"value": "", "upperlimit": "0.33"}), "<= 0.33")
        self.assertEqual(databases.oec_format_field({"value": "", "lowerlimit": "2"}, "d"), ">= 2 d")

    def test_value_with_symmetric_error(self):
        self.assertEqual(
            databases.oec_format_field({"value": "0.5", "errorminus": "0.1", "errorplus": "0.1"}, "AU"),
            "0.5 ±0.1 AU")

    def test_list_field_uses_first(self):
        self.assertEqual(
            databases.oec_format_field([{"value": "80", "unit": "arcsec"}, {"value": "400", "unit": "AU"}]),
            "80 arcsec")

    def test_unnamed_binary_label_synthesized(self):
        node = {"tag": "binary", "names": [],
                "children": [{"tag": "star", "names": ["ZP A"]},
                             {"tag": "star", "names": ["ZP B"]}]}
        self.assertEqual(databases.oec_binary_label(node), "Binary (A + B)")


if __name__ == "__main__":
    unittest.main()
