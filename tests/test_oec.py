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

import os
# Qt must run headless for the Phase-3b canvas smoke tests. Set before any PySide6
# import (harmless for the offline majority of this module).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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


# ── Phase 4: structural search + census (compute_oec_search / _census / _status) ──
class OecSearchTests(OecTestBase):
    def _names(self, **kw):
        r = databases.compute_oec_search(**kw)
        self.assertNotIn("error", r, r.get("error"))
        return sorted(s["name"] for s in r["systems"])

    def test_no_filters_returns_all_systems(self):
        r = databases.compute_oec_search()
        self.assertEqual(r["count"], 6)
        self.assertFalse(r["capped"])
        self.assertEqual(r["filters"], {})

    def test_min_and_max_stars(self):
        self.assertEqual(self._names(min_stars=2),
                         ["Binary S", "Circumbinary", "Hierarchy", "Zero Planet"])
        self.assertEqual(self._names(max_stars=1), ["Rogue One", "Single Star"])

    def test_circumbinary_flag(self):
        self.assertEqual(self._names(circumbinary=True), ["Circumbinary"])

    def test_status_substring(self):
        self.assertEqual(self._names(status="P-type"), ["Circumbinary"])
        self.assertEqual(self._names(status="Orphan"), ["Rogue One"])

    def test_mass_range_jupiter_units(self):
        # BS A b 1.2, Outer B b 1.7, Rogue One 6.0 pass; HD 1 b (msini 0.5) + CB AB b 0.3 don't.
        self.assertEqual(self._names(mass_min=1.0),
                         ["Binary S", "Hierarchy", "Rogue One"])

    def test_spectral_type_prefix(self):
        self.assertEqual(self._names(spectral_type="K"), ["Binary S", "Zero Planet"])
        self.assertEqual(self._names(spectral_type="G"), ["Hierarchy", "Single Star"])
        self.assertEqual(self._names(spectral_type="DA"), ["Binary S"])  # DA2 white dwarf

    def test_matched_planets_narrow_when_planet_filter_set(self):
        r = databases.compute_oec_search(mass_min=1.0)
        hier = next(s for s in r["systems"] if s["name"] == "Hierarchy")
        self.assertEqual([p["name"] for p in hier["planets"]], ["Outer B b"])

    def test_all_planets_returned_without_planet_filter(self):
        r = databases.compute_oec_search(min_stars=1)
        single = next(s for s in r["systems"] if s["name"] == "Single Star")
        self.assertEqual([p["name"] for p in single["planets"]], ["HD 1 b"])
        self.assertEqual(single["planets"][0]["mass_type"], "msini")   # msini surfaced

    def test_planet_filters_are_conjunctive(self):
        # P-type AND mass ≥ 1.0 → CB AB b (0.3) fails the mass cut → no system matches.
        self.assertEqual(databases.compute_oec_search(status="P-type", mass_min=1.0)["count"], 0)

    def test_inverted_ranges_error(self):
        self.assertIn("error", databases.compute_oec_search(min_stars=3, max_stars=1))
        self.assertIn("error", databases.compute_oec_search(mass_min=5, mass_max=1))
        self.assertIn("error", databases.compute_oec_search(sma_min=9, sma_max=1))

    def test_limit_caps_and_flags(self):
        r = databases.compute_oec_search(limit=2)
        self.assertEqual(len(r["systems"]), 2)
        self.assertEqual(r["cap"], 2)
        self.assertTrue(r["capped"])
        self.assertEqual(r["count"], 6)
        self.assertIn("error", databases.compute_oec_search(limit=0))


class OecCensusTests(OecTestBase):
    def test_counts_and_distributions(self):
        c = databases.compute_oec_census()
        self.assertEqual(c["n_systems"], 6)
        self.assertEqual(c["n_stars"], 10)
        self.assertEqual(c["n_planets"], 5)
        self.assertEqual(c["n_binaries"], 5)
        self.assertEqual(c["n_satellites"], 1)
        self.assertEqual(c["stars_per_system"], {"0": 1, "1": 1, "2": 3, "3": 1})
        self.assertEqual(c["planets_per_system"], {"0": 1, "1": 5})
        self.assertEqual(c["binary_depth"], {"0": 2, "1": 3, "2": 1})
        self.assertEqual(c["planet_attachment"], {"star": 3, "binary": 1, "system": 1})
        self.assertEqual(c["circumbinary_systems"], 1)
        self.assertEqual(c["rogue_systems"], 1)
        self.assertEqual(c["planetless_systems"], 1)
        self.assertEqual(c["status_counts"]["Confirmed planets"], 3)
        self.assertEqual(c["status_counts"]["Planets in binary systems, P-type"], 1)

    def test_status_snapshot(self):
        s = databases.compute_oec_status()
        self.assertEqual(s["n_systems"], 6)
        self.assertEqual(s["n_stars"], 10)
        self.assertEqual(s["n_planets"], 5)
        self.assertEqual(s["source"], databases._OEC_URL)
        self.assertEqual(s["staleness_window_days"], databases._OEC_CACHE_MAX_AGE_DAYS)


# ── Phase 3: System Architecture map layout (core.viz.prepare_oec_architecture) ──
# prepare_oec_architecture is pure over a node dict (no DB/Qt), so the precise
# barycenter/Kepler math is unit-tested with hand-built nodes; topology integration
# runs off the shared fixture via OecTestBase.

import core.viz as viz


def _n(tag, names=None, fields=None, children=None):
    return {"tag": tag, "names": names or [],
            "fields": fields or {}, "children": children or []}


def _f(value, **attrs):
    return {"value": ("" if value is None else str(value)), **attrs}


def _sys(children, **fields):
    return _n("system", ["Sys"], fields, children)


class ArchitectureMathTests(unittest.TestCase):
    def _one(self, stars, name):
        return next(s for s in stars if s["name"] == name)

    def test_mass_weighted_barycenter_offsets(self):
        # binary sma=3 AU, m1=2, m2=1 → heavier star 1 AU out, lighter 2 AU out,
        # and the mass-weighted centroid sits at the origin (m1·r1 == m2·r2).
        binary = _n("binary", ["Pair"], {"semimajoraxis": _f(3)}, [
            _n("star", ["Heavy"], {"mass": _f(2.0)}),
            _n("star", ["Light"], {"mass": _f(1.0)}),
        ])
        r = viz.prepare_oec_architecture(_sys([binary]))
        self.assertNotIn("error", r)
        heavy, light = self._one(r["stars"], "Heavy"), self._one(r["stars"], "Light")
        self.assertAlmostEqual(heavy["r_au"], 1.0, places=6)
        self.assertAlmostEqual(light["r_au"], 2.0, places=6)
        self.assertAlmostEqual(2.0 * heavy["r_au"], 1.0 * light["r_au"], places=6)

    def test_kepler_from_period_rung(self):
        # period-only binary (P=365.25 d = 1 yr, m1=m2=0.5 → tot=1) → a = ∛(1·1²) = 1 AU.
        binary = _n("binary", ["KPair"], {"period": _f(365.25)}, [
            _n("star", ["KA"], {"mass": _f(0.5)}),
            _n("star", ["KB"], {"mass": _f(0.5)}),
        ])
        r = viz.prepare_oec_architecture(_sys([binary]))
        self.assertEqual(len(r["edges"]), 1)
        self.assertTrue(r["edges"][0]["derived"])
        self.assertIn("from period", r["edges"][0]["label"])
        self.assertTrue(r["flags"]["any_derived"])
        # both components 0.5 AU from the barycenter
        for s in r["stars"]:
            self.assertAlmostEqual(s["r_au"], 0.5, places=6)

    def test_missing_mass_equal_split_flagged(self):
        binary = _n("binary", ["NoMass"], {"semimajoraxis": _f(4)}, [
            _n("star", ["NA"]), _n("star", ["NB"]),
        ])
        r = viz.prepare_oec_architecture(_sys([binary]))
        self.assertTrue(r["edges"][0]["fallback"])
        self.assertTrue(r["flags"]["any_fallback"])
        for s in r["stars"]:                       # equal split → both 2 AU out
            self.assertAlmostEqual(s["r_au"], 2.0, places=6)

    def test_no_separation_schematic_fallback(self):
        # no sma/sep/period and no masses → schematic placeholder, not stacked.
        binary = _n("binary", ["Sch"], {"eccentricity": _f(0.4)}, [
            _n("star", ["SA"]), _n("star", ["SB"]),
        ])
        r = viz.prepare_oec_architecture(_sys([binary]))
        self.assertTrue(r["flags"]["any_schematic"])
        self.assertIn("schematic", r["edges"][0]["label"])
        # placed apart (not both on the barycenter)
        self.assertGreater(max(s["r_au"] for s in r["stars"]), 0.0)

    def test_separation_prefers_au_over_arcsec(self):
        # both units present → AU-direct wins (not the arcsec projection).
        binary = _n("binary", ["Two"],
                    {"separation": [_f(80, unit="arcsec"), _f(400, unit="AU")]}, [
            _n("star", ["TA"], {"mass": _f(1.0)}),
            _n("star", ["TB"], {"mass": _f(1.0)}),
        ])
        r = viz.prepare_oec_architecture(_sys([binary], distance=_f(5.0)))
        self.assertFalse(r["edges"][0]["proj"])
        self.assertIn("400", r["edges"][0]["label"])

    def test_arcsec_projected_via_distance(self):
        binary = _n("binary", ["Two"], {"separation": [_f(80, unit="arcsec")]}, [
            _n("star", ["TA"], {"mass": _f(1.0)}),
            _n("star", ["TB"], {"mass": _f(1.0)}),
        ])
        r = viz.prepare_oec_architecture(_sys([binary], distance=_f(5.0)))
        self.assertTrue(r["edges"][0]["proj"])
        self.assertTrue(r["flags"]["any_proj"])
        # 80 arcsec × 5 pc = 400 AU total → 200 AU each (equal masses)
        for s in r["stars"]:
            self.assertAlmostEqual(s["r_au"], 200.0, places=4)


class ArchitectureTopologyTests(OecTestBase):
    def _arch(self, name):
        return viz.prepare_oec_architecture(self._system(name))

    def test_single_star_at_barycenter_no_rings(self):
        r = self._arch("Single Star")
        self.assertEqual(len(r["stars"]), 1)
        self.assertAlmostEqual(r["stars"][0]["r_au"], 0.0)
        self.assertEqual(len(r["stars"][0]["planets"]), 1)
        self.assertEqual(r["rings"], [])          # single star → no barycentric scale

    def test_hierarchy_places_all_three_stars(self):
        r = self._arch("Hierarchy")
        names = {s["name"] for s in r["stars"]}
        self.assertEqual(names, {"Inner A", "Inner C", "Outer B"})
        self.assertEqual(len(r["edges"]), 2)       # inner + outer binary connectors
        self.assertTrue(r["handles"])              # binary barycenters → recenter handles

    def test_rogue_system_has_no_placeable_stars(self):
        r = self._arch("Rogue One")
        self.assertIn("error", r)

    def test_focus_recenter_on_subsystem(self):
        system = self._system("Hierarchy")
        inner = self._find(system, "binary", "Inner AC")[0]
        r = viz.prepare_oec_architecture(system, focus_node=inner)
        self.assertIn("subsystem barycenter", r["focus_label"])
        self.assertEqual({s["name"] for s in r["stars"]}, {"Inner A", "Inner C"})
        # focus_node is the binary, so none of its component stars are flagged is_focus
        self.assertFalse(any(s["is_focus"] for s in r["stars"]))

    def test_focus_on_star_flags_is_focus(self):
        system = self._system("Hierarchy")
        outer_b = self._find(system, "star", "Outer B")[0]
        r = viz.prepare_oec_architecture(system, focus_node=outer_b)
        focused = [s for s in r["stars"] if s["is_focus"]]
        self.assertEqual([s["name"] for s in focused], ["Outer B"])

    def test_white_dwarf_spectral_color_not_obafgkm(self):
        r = self._arch("Binary S")
        wd = next(s for s in r["stars"] if s["name"] == "BS B")   # DA2 white dwarf
        self.assertEqual(wd["sp_type"], "DA2")
        self.assertEqual(wd["color"], viz._SPECTRAL_COLORS["D"])

    def test_star_hosts_emit_no_circumbinary_centers(self):
        # Fixtures whose planets hang off <star> nodes must yield no P-type centers.
        for name in ("Single Star", "Hierarchy", "Binary S"):
            self.assertEqual(self._arch(name)["centers"], [], name)

    def test_fixture_circumbinary_center(self):
        r = self._arch("Circumbinary")
        self.assertEqual(len(r["centers"]), 1)
        c = r["centers"][0]
        self.assertEqual(c["label"], "CB AB")
        self.assertEqual([p["name"] for p in c["planets"]], ["CB AB b"])
        # the P-type planet rides the binary, never a component star
        self.assertTrue(all(len(s["planets"]) == 0 for s in r["stars"]))

    def test_planet_dicts_carry_node_for_click_dialog(self):
        # Every planet dict (star-ring + circumbinary) carries its full node so a click
        # can populate an info dialog (mirrors the star "node" ref).
        p = self._arch("Single Star")["stars"][0]["planets"][0]
        self.assertIn("node", p)
        self.assertEqual(p["node"]["tag"], "planet")
        cb = self._arch("Circumbinary")["centers"][0]["planets"][0]
        self.assertEqual(cb["node"]["tag"], "planet")


# ── Phase 3b: circumbinary (P-type) planet rings — the `centers` payload ──────────
class ArchitectureCentersTests(unittest.TestCase):
    """`prepare_oec_architecture` emits a `centers` entry (keyed to the binary
    barycenter) for every <binary> carrying direct <planet> children."""

    def _cb_system(self):
        return _sys([
            _n("binary", ["CB AB"], {"semimajoraxis": _f(0.2)}, [
                _n("planet", ["CB AB b"],
                   {"mass": _f(0.33), "semimajoraxis": _f(0.7),
                    "list": _f("Planets in binary systems, P-type")}),
                _n("star", ["CB A"], {"mass": _f(1.0)}),
                _n("star", ["CB B"], {"mass": _f(0.9)}),
            ]),
        ])

    def test_center_emitted_at_top_level_barycenter(self):
        r = viz.prepare_oec_architecture(self._cb_system())
        self.assertEqual(len(r["centers"]), 1)
        c = r["centers"][0]
        self.assertEqual(c["label"], "CB AB")
        self.assertEqual([p["name"] for p in c["planets"]], ["CB AB b"])
        self.assertIn("Planets in binary systems, P-type", c["planets"][0]["status"])
        # a top-level circumbinary's barycenter sits at the display origin
        self.assertAlmostEqual(c["x"], 0.0, places=6)
        self.assertAlmostEqual(c["y"], 0.0, places=6)

    def test_planet_absent_from_component_stars(self):
        r = viz.prepare_oec_architecture(self._cb_system())
        self.assertTrue(all(len(s["planets"]) == 0 for s in r["stars"]))
        self.assertEqual({s["name"] for s in r["stars"]}, {"CB A", "CB B"})

    def test_center_survives_focus_on_binary(self):
        system = self._cb_system()
        binary = system["children"][0]
        r = viz.prepare_oec_architecture(system, focus_node=binary)
        self.assertEqual(len(r["centers"]), 1)
        self.assertEqual(len(r["centers"][0]["planets"]), 1)

    def test_nested_circumbinary_keyed_to_its_own_barycenter(self):
        # A circumbinary pair that is itself the secondary of a wider binary: the
        # center must ride the inner pair's (offset) barycenter, not the origin.
        inner = _n("binary", ["Inner"], {"semimajoraxis": _f(0.3)}, [
            _n("planet", ["Inner b"], {"mass": _f(0.2)}),
            _n("star", ["IA"], {"mass": _f(1.0)}),
            _n("star", ["IB"], {"mass": _f(1.0)}),
        ])
        outer = _n("binary", ["Outer"], {"separation": _f(500, unit="AU")}, [
            inner,
            _n("star", ["Wide"], {"mass": _f(2.0)}),
        ])
        r = viz.prepare_oec_architecture(_sys([outer]))
        labels = {c["label"] for c in r["centers"]}
        self.assertEqual(labels, {"Inner"})
        inner_center = next(c for c in r["centers"] if c["label"] == "Inner")
        self.assertGreater(inner_center["x"] ** 2 + inner_center["y"] ** 2, 1e-6)


# ── Phase 3b: interactive Architecture canvas (headless smoke + pick wiring) ──────
def _oec_mpl_ok():
    try:
        from gui.visualizations.plot_helpers import mpl_available
        return mpl_available()
    except Exception:
        return False


@unittest.skipUnless(_oec_mpl_ok(), "matplotlib/PySide6 not available")
class ArchitectureCanvasTests(OecTestBase):
    """The interactive canvas (Phase-3b) builds for every topology in both modes, and
    a simulated pick on a star / ◆ handle fires the recenter callback with that node."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _build(self, name, on_select):
        from gui.visualizations.plot_helpers import make_oec_architecture_canvas
        data = viz.prepare_oec_architecture(self._system(name))
        return make_oec_architecture_canvas(None, data, on_select=on_select)

    def test_builds_for_all_topologies_interactive_and_static(self):
        for name in ("Single Star", "Binary S", "Circumbinary",
                     "Hierarchy", "Zero Planet"):
            canvas, toolbar = self._build(name, on_select=lambda n: None)
            self.assertIsNotNone(canvas, name)
            self.assertIsNotNone(toolbar, name)
            static, _ = self._build(name, on_select=None)
            self.assertIsNotNone(static, name)

    def _pick(self, canvas, artist):
        from matplotlib.backend_bases import PickEvent, MouseEvent
        me = MouseEvent("button_press_event", canvas, 10, 10, button=1)
        canvas.callbacks.process("pick_event",
                                 PickEvent("pick_event", canvas, me, artist))

    def test_pick_on_star_fires_on_select_with_node(self):
        clicked = []
        canvas, _ = self._build("Binary S", on_select=clicked.append)
        ax = canvas.figure.axes[0]
        star_art = next(a for a in ax.collections
                        if getattr(a, "_oec_node", None) is not None
                        and a._oec_node["tag"] == "star")
        self._pick(canvas, star_art)
        self.assertEqual(len(clicked), 1)
        self.assertEqual(clicked[0]["tag"], "star")

    def test_pick_on_binary_handle_recenters(self):
        clicked = []
        canvas, _ = self._build("Hierarchy", on_select=clicked.append)
        ax = canvas.figure.axes[0]
        handle = next(a for a in ax.collections
                      if getattr(a, "_oec_node", None) is not None
                      and a._oec_node["tag"] == "binary")
        self._pick(canvas, handle)
        self.assertEqual(len(clicked), 1)
        self.assertEqual(clicked[0]["tag"], "binary")

    def test_circumbinary_canvas_draws_planet_ring(self):
        # The P-type planet ring is an added Circle patch on the circumbinary canvas.
        cb, _ = self._build("Circumbinary", on_select=None)
        single, _ = self._build("Single Star", on_select=None)
        # Both have one reference scale ring; the circumbinary adds its planet ring.
        self.assertGreater(len(cb.figure.axes[0].patches),
                           len(single.figure.axes[0].patches))

    def test_reset_view_restores_default_extent(self):
        canvas, _ = self._build("Hierarchy", on_select=lambda n: None)
        self.assertTrue(hasattr(canvas, "reset_view"))
        ax = canvas.figure.axes[0]
        (x0, x1) = ax.get_xlim()
        ax.set_xlim(0.1, 0.2)          # simulate a scroll-wheel zoom
        ax.set_ylim(0.1, 0.2)
        canvas.reset_view()
        self.assertAlmostEqual(ax.get_xlim()[0], x0, places=6)
        self.assertAlmostEqual(ax.get_xlim()[1], x1, places=6)

    def _canvas_pc(self, name, **kw):
        from gui.visualizations.plot_helpers import make_oec_architecture_canvas
        data = viz.prepare_oec_architecture(self._system(name))
        return make_oec_architecture_canvas(None, data, **kw)[0]

    def test_planet_click_fires_on_planet_click_not_recenter(self):
        clicked, recentered = [], []
        canvas = self._canvas_pc("Single Star", on_select=recentered.append,
                                 on_planet_click=clicked.append)
        ax = canvas.figure.axes[0]
        parts = [a for a in ax.collections if getattr(a, "_oec_planet", None) is not None]
        self.assertEqual(len(parts), 1)               # HD 1 b
        self._pick(canvas, parts[0])
        self.assertEqual(len(clicked), 1)
        self.assertEqual(clicked[0]["name"], "HD 1 b")
        self.assertEqual(clicked[0]["host"], "HD 1")
        self.assertIn("node", clicked[0])
        self.assertEqual(recentered, [])              # a planet click is NOT a recenter

    def test_circumbinary_planet_click_host_is_binary_label(self):
        clicked = []
        canvas = self._canvas_pc("Circumbinary", on_planet_click=clicked.append)
        ax = canvas.figure.axes[0]
        parts = [a for a in ax.collections if getattr(a, "_oec_planet", None) is not None]
        self.assertEqual(len(parts), 1)
        self._pick(canvas, parts[0])
        self.assertEqual(clicked[0]["name"], "CB AB b")
        self.assertEqual(clicked[0]["host"], "CB AB")   # the binary label

    def test_planets_not_pickable_without_on_planet_click(self):
        canvas = self._canvas_pc("Single Star", on_select=lambda n: None)
        ax = canvas.figure.axes[0]
        self.assertFalse(any(getattr(a, "_oec_planet", None) is not None
                             for a in ax.collections))

    def test_planet_info_dialog_renders_fields(self):
        from PySide6.QtWidgets import QLabel, QDialog
        from gui.panels.catalogs import _show_oec_planet_dialog
        data = viz.prepare_oec_architecture(self._system("Single Star"))
        planet = dict(data["stars"][0]["planets"][0], host="HD 1")
        dlg = _show_oec_planet_dialog(None, planet)
        self.assertIsInstance(dlg, QDialog)
        self.assertIn("HD 1 b", dlg.windowTitle())
        texts = [l.text() for l in dlg.findChildren(QLabel)]
        self.assertTrue(any("M·sin i" in t for t in texts))          # msini surfaced
        self.assertTrue(any("Confirmed planets" in t for t in texts))  # status
        dlg.close()


class _FakeNav:
    def show(self): pass
    def hide(self): pass


class _FakeWindow:
    def __init__(self):
        self.nav_tree = _FakeNav()

    def statusBar(self):
        class _SB:
            def showMessage(self, *a): pass
        return _SB()


@unittest.skipUnless(_oec_mpl_ok(), "matplotlib/PySide6 not available")
class OecPanelRecenterTests(OecTestBase):
    """The Phase-3b panel wiring: `_on_arch_select` / `_on_arch_reset` update the map
    focus + host, keep the Architecture map (viz tab 0) selected, and don't leave
    diagram mode. Drives the real `OecPanel` headless via the `_FakeWindow` harness."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self, name):
        from gui.panels.catalogs import OecPanel, _oec_collect_hosts
        panel = OecPanel(_FakeWindow())
        system = self._system(name)
        # Feed the render path directly (bypass the network/thread) with empty Hypatia
        # so _render_host stays offline.
        panel._on_oec_result({"system": system, "_hypatia": {}})
        panel._collect_hosts = _oec_collect_hosts
        return panel, system

    def _flush(self):
        # Run the QTimer.singleShot(0, …) deferred rebuild.
        self.app.processEvents()

    def _arch_tab_index(self, panel):
        w = panel._viz_tabs_widget
        return next((i for i in range(w.count())
                    if w.tabText(i) == "Architecture"), None)

    def test_initial_state_focus_none_arch_tab_present(self):
        panel, _ = self._panel("Hierarchy")
        self.assertIsNone(panel._oec_focus)
        self.assertEqual(self._arch_tab_index(panel), 0)

    def test_select_host_star_sets_focus_and_host(self):
        panel, system = self._panel("Hierarchy")
        outer_b = self._find(system, "star", "Outer B")[0]   # the planet host
        panel._on_arch_select(outer_b)
        self._flush()
        self.assertIs(panel._oec_focus, outer_b)
        self.assertEqual(panel._oec_host_idx, 0)
        # architecture map still at viz tab 0 and now selected
        self.assertEqual(self._arch_tab_index(panel), 0)
        self.assertEqual(panel._viz_tabs_widget.currentIndex(), 0)

    def test_select_non_host_component_recenters_only(self):
        panel, system = self._panel("Hierarchy")
        inner_a = self._find(system, "star", "Inner A")[0]   # no planets
        prev_host = panel._oec_host_idx
        panel._on_arch_select(inner_a)
        self._flush()
        self.assertIs(panel._oec_focus, inner_a)
        self.assertEqual(panel._oec_host_idx, prev_host)     # host tabs untouched

    def test_select_binary_handle_recenters(self):
        panel, system = self._panel("Hierarchy")
        inner = self._find(system, "binary", "Inner AC")[0]
        panel._on_arch_select(inner)
        self._flush()
        self.assertIs(panel._oec_focus, inner)

    def test_reset_returns_to_barycenter(self):
        panel, system = self._panel("Hierarchy")
        outer_b = self._find(system, "star", "Outer B")[0]
        panel._on_arch_select(outer_b)
        self._flush()
        self.assertIsNotNone(panel._oec_focus)
        panel._on_arch_reset()
        self._flush()
        self.assertIsNone(panel._oec_focus)
        self.assertEqual(self._arch_tab_index(panel), 0)

    def test_reset_without_focus_is_pure_zoom_reset(self):
        # No focus set → Reset diagram must reset the canvas view without tearing down
        # the detail tabs (host index unchanged, no rebuild needed).
        panel, _ = self._panel("Hierarchy")
        self.assertIsNone(panel._oec_focus)
        prev_host = panel._oec_host_idx
        ax = panel._arch_canvas.figure.axes[0]
        default = ax.get_xlim()
        ax.set_xlim(0.1, 0.2)                 # simulate a zoom on the whole-system view
        panel._on_arch_reset()
        self.assertIsNone(panel._oec_focus)
        self.assertEqual(panel._oec_host_idx, prev_host)
        self.assertAlmostEqual(ax.get_xlim()[0], default[0], places=6)

    def test_breadcrumb_reflects_focus(self):
        import core.viz as _viz
        panel, system = self._panel("Hierarchy")
        whole = _viz.prepare_oec_architecture(system)
        self.assertIn("whole-system", panel._arch_breadcrumb(whole))
        outer_b = self._find(system, "star", "Outer B")[0]
        panel._oec_focus = outer_b
        focused = _viz.prepare_oec_architecture(system, focus_node=outer_b)
        self.assertIn("Outer B", panel._arch_breadcrumb(focused))

    def test_clicking_planet_opens_dialog_parented_to_panel(self):
        from PySide6.QtWidgets import QDialog
        from matplotlib.backend_bases import PickEvent, MouseEvent
        panel, _ = self._panel("Single Star")
        canvas = panel._arch_canvas
        ax = canvas.figure.axes[0]
        parts = [a for a in ax.collections if getattr(a, "_oec_planet", None) is not None]
        self.assertTrue(parts)
        me = MouseEvent("button_press_event", canvas, 10, 10, button=1)
        canvas.callbacks.process("pick_event",
                                 PickEvent("pick_event", canvas, me, parts[0]))
        dialogs = panel.findChildren(QDialog)
        self.assertTrue(dialogs)
        self.assertIn("HD 1 b", dialogs[0].windowTitle())
        dialogs[0].close()


if __name__ == "__main__":
    unittest.main()
